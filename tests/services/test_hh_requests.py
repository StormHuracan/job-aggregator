import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_aggregator.db.models.user import User
from job_aggregator.db.repositories.hh_account import HHAccountRepository
from job_aggregator.integrations.hh.client import HHClient
from job_aggregator.integrations.hh.dto import HHVacancySearchParams
from job_aggregator.integrations.hh.errors import HHPermanentRequestError
from job_aggregator.services import hh_requests
from job_aggregator.services.hh_requests import (
    AuthorizedHHAPIClient,
    HHAccountNotConnectedError,
)
from tests.factories import make_token_data
from tests.fakes.hh_requests import FakeHHAPIClient, FakeHHAPIFactory


@pytest.fixture
def session_factory(sqlite_session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    """Использует движок общей SQLite fixture, сохраняя отдельные сессии."""
    return async_sessionmaker(sqlite_session.bind, expire_on_commit=False)


@pytest.fixture
def api_factory(monkeypatch: pytest.MonkeyPatch) -> FakeHHAPIFactory:
    factory = FakeHHAPIFactory()
    monkeypatch.setattr(hh_requests, "HHAPIClient", factory)
    return factory


@pytest.fixture
async def user_id(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory.begin() as session:
        user = User(hh_user_id="owner", display_name="Owner")
        session.add(user)
        await session.flush()
        await HHAccountRepository(session).save(user.id, make_token_data())
        return user.id


async def test_request_uses_owner_tokens_and_returns_response(
    session_factory: async_sessionmaker[AsyncSession],
    user_id: int,
    api_factory: FakeHHAPIFactory,
) -> None:
    client = AuthorizedHHAPIClient(session_factory, user_id, allow_token_refresh=False)
    assert api_factory.instances == []

    result = await client.request("GET", "/vacancies", {"text": "python"})

    api = api_factory.instances[0]
    assert result is api.response
    assert api.tokens == make_token_data()
    assert api.allow_token_refresh is False
    assert api.calls == [("GET", "/vacancies", {"text": "python"})]
    assert api.closed


@pytest.mark.parametrize("failure", [False, True], ids=["success", "http-error"])
async def test_refreshed_tokens_are_committed_even_after_http_failure(
    session_factory: async_sessionmaker[AsyncSession],
    user_id: int,
    api_factory: FakeHHAPIFactory,
    failure: bool,
) -> None:
    replacement = make_token_data(
        access_token="new-access", refresh_token="new-refresh"
    )
    error = HHPermanentRequestError("HH request rejected")

    def configure(api: FakeHHAPIClient) -> None:
        api.replacement = replacement
        api.error = error if failure else None

    api_factory.configure = configure
    client = AuthorizedHHAPIClient(
        session_factory,
        user_id,
        allow_token_refresh=True,
        client_id="client-id",
        client_secret="client-secret",
    )

    if failure:
        with pytest.raises(HHPermanentRequestError) as caught:
            await client.request("GET", "/vacancies")
        assert caught.value is error
    else:
        await client.request("GET", "/vacancies")

    async with session_factory() as observer:
        account = await HHAccountRepository(observer).get_by_user_id(user_id)
        assert account is not None
        assert account.access_token == "new-access"
        assert account.refresh_token == "new-refresh"
    api = api_factory.instances[0]
    assert api.allow_token_refresh is True
    assert api.client_id == "client-id"
    assert api.client_secret == "client-secret"
    assert api.closed


@pytest.mark.parametrize("missing_user", [False, True])
async def test_missing_connection_does_not_make_http_request(
    session_factory: async_sessionmaker[AsyncSession],
    user_id: int,
    api_factory: FakeHHAPIFactory,
    missing_user: bool,
) -> None:
    async with session_factory.begin() as session:
        account = await HHAccountRepository(session).get_by_user_id(user_id)
        assert account is not None
        await session.delete(account)
    client = AuthorizedHHAPIClient(
        session_factory,
        9999 if missing_user else user_id,
        allow_token_refresh=False,
    )
    with pytest.raises(HHAccountNotConnectedError, match="HH account is not connected"):
        await client.request("GET", "/vacancies")
    assert api_factory.instances == []


async def test_hh_client_normalizes_authorized_response(
    session_factory: async_sessionmaker[AsyncSession],
    user_id: int,
    api_factory: FakeHHAPIFactory,
) -> None:
    def configure(api: FakeHHAPIClient) -> None:
        api.response = {
            "items": [
                {
                    "id": "42",
                    "name": "Python developer",
                    "alternate_url": "https://hh.ru/vacancy/42",
                    "employer": {"name": "Example"},
                }
            ],
            "page": 0,
            "pages": 1,
            "found": 1,
        }

    api_factory.configure = configure
    client = HHClient(
        AuthorizedHHAPIClient(
            session_factory,
            user_id,
            allow_token_refresh=False,
        )
    )
    page = await client.search_vacancies(HHVacancySearchParams(text="python"))
    assert page.found == 1
    assert page.items[0].external_id == "42"
    assert page.items[0].company_name == "Example"


async def test_failed_commit_does_not_return_success_and_can_be_retried(
    session_factory: async_sessionmaker[AsyncSession],
    user_id: int,
    api_factory: FakeHHAPIFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def configure(api: FakeHHAPIClient) -> None:
        api.replacement = make_token_data(
            access_token="rotated", refresh_token="rotated-refresh"
        )

    api_factory.configure = configure
    failed = False

    def fail_once(session: object) -> None:
        nonlocal failed
        if not failed:
            failed = True
            raise OperationalError("COMMIT", {}, Exception("test failure"))

    target = session_factory.class_.sync_session_class
    event.listen(target, "before_commit", fail_once)
    try:
        client = AuthorizedHHAPIClient(
            session_factory, user_id, allow_token_refresh=True
        )
        with pytest.raises(OperationalError):
            await client.request("GET", "/vacancies")
        async with session_factory() as session:
            account = await HHAccountRepository(session).get_by_user_id(user_id)
            assert account is not None
            assert account.access_token == "access-1"
        assert await client.request("GET", "/vacancies") == {"ok": True}
    finally:
        event.remove(target, "before_commit", fail_once)
    assert "rotated-refresh" not in caplog.text
    assert "access-1" not in caplog.text
