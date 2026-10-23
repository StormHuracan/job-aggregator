import asyncio
from typing import Any

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from job_aggregator.db.models.user import User
from job_aggregator.db.repositories.collection_progress import (
    CollectionProgressRepository,
)
from job_aggregator.db.repositories.hh_account import HHAccountRepository
from job_aggregator.services import hh_requests
from job_aggregator.services.hh_requests import AuthorizedHHAPIClient
from tests.factories import make_token_data
from tests.fakes.hh_requests import FakeHHAPIClient, FakeHHAPIFactory


@pytest.fixture
def api_factory(monkeypatch: pytest.MonkeyPatch) -> FakeHHAPIFactory:
    factory = FakeHHAPIFactory()
    monkeypatch.setattr(hh_requests, "HHAPIClient", factory)
    return factory


@pytest.fixture
async def owners(pg_session_factory: async_sessionmaker[AsyncSession]) -> list[int]:
    async with pg_session_factory.begin() as session:
        ids = []
        for name in ["a", "b"]:
            user = User(hh_user_id=name, display_name=name)
            session.add(user)
            await session.flush()
            await HHAccountRepository(session).save(
                user.id,
                make_token_data(access_token=f"owner-{name}"),
            )
            ids.append(user.id)
        return ids


async def _wait_for_blocked_request(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """Ждёт фактического ожидания PostgreSQL lock, а не задержки event loop."""

    async def wait() -> None:
        while True:
            async with factory() as session:
                count = await session.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE datname = current_database() "
                        "AND wait_event_type = 'Lock'"
                    )
                )
                if count:
                    return
            await asyncio.sleep(0.01)

    await asyncio.wait_for(wait(), 5)


async def test_new_collection_position_does_not_block_authorized_token_refresh(
    pg_session_factory,
    owners,
    api_factory,
):
    def configure(api):
        api.replacement = make_token_data(access_token="refreshed")

    api_factory.configure = configure
    async with pg_session_factory() as session:
        await CollectionProgressRepository(session).get_for_update(owners[0], "a" * 64)
        client = AuthorizedHHAPIClient(
            pg_session_factory, owners[0], allow_token_refresh=True
        )
        assert await asyncio.wait_for(client.request("GET", "/vacancies"), 1) == {
            "ok": True
        }
        await session.commit()
    async with pg_session_factory() as session:
        account = await HHAccountRepository(session).get_by_user_id(owners[0])
        assert account.access_token == "refreshed"


async def test_same_owner_waits_and_other_owner_is_independent(
    pg_session_factory: async_sessionmaker[AsyncSession],
    owners: list[int],
    api_factory: FakeHHAPIFactory,
) -> None:
    release = asyncio.Event()
    started = asyncio.Event()

    def configure(api: FakeHHAPIClient) -> None:
        if api.tokens.access_token == "owner-a":
            api.started = started
            api.release = release
            api.replacement = make_token_data(access_token="owner-a-new")

    api_factory.configure = configure
    first = asyncio.create_task(
        AuthorizedHHAPIClient(
            pg_session_factory,
            owners[0],
            allow_token_refresh=True,
        ).request("GET", "/vacancies")
    )
    second = None
    try:
        await asyncio.wait_for(started.wait(), 5)
        second = asyncio.create_task(
            AuthorizedHHAPIClient(
                pg_session_factory,
                owners[0],
                allow_token_refresh=True,
            ).request("GET", "/vacancies")
        )
        await _wait_for_blocked_request(pg_session_factory)
        assert len(api_factory.instances) == 1

        assert await asyncio.wait_for(
            AuthorizedHHAPIClient(
                pg_session_factory,
                owners[1],
                allow_token_refresh=True,
            ).request("GET", "/vacancies"),
            5,
        ) == {"ok": True}
        release.set()
        assert await asyncio.wait_for(asyncio.gather(first, second), 5) == [
            {"ok": True},
            {"ok": True},
        ]
        assert [api.initial_tokens.access_token for api in api_factory.instances] == [
            "owner-a",
            "owner-b",
            "owner-a-new",
        ]
    finally:
        release.set()
        await asyncio.gather(
            first, *([second] if second else []), return_exceptions=True
        )


@pytest.mark.parametrize("stage", ["save", "commit"])
async def test_persistence_failure_releases_owner_lock(
    pg_session_factory: async_sessionmaker[AsyncSession],
    owners: list[int],
    api_factory: FakeHHAPIFactory,
    stage: str,
) -> None:
    def configure(api: FakeHHAPIClient) -> None:
        api.replacement = make_token_data(access_token="new-access")

    api_factory.configure = configure
    failed = False

    def fail_once(*args: Any) -> None:
        nonlocal failed
        if stage == "save" and not args[2].startswith("UPDATE hh_accounts"):
            return
        if not failed:
            failed = True
            raise OperationalError("test operation", {}, Exception("test failure"))

    async with pg_session_factory() as session:
        engine = session.bind
        assert isinstance(engine, AsyncEngine)
    target = (
        engine.sync_engine
        if stage == "save"
        else pg_session_factory.class_.sync_session_class
    )
    event_name = "before_cursor_execute" if stage == "save" else "before_commit"
    event.listen(target, event_name, fail_once)
    try:
        client = AuthorizedHHAPIClient(
            pg_session_factory, owners[0], allow_token_refresh=True
        )
        with pytest.raises(OperationalError):
            await client.request("GET", "/vacancies")
        async with pg_session_factory() as session:
            account = await HHAccountRepository(session).get_by_user_id(owners[0])
            assert account is not None
            assert account.access_token == "owner-a"
        assert await asyncio.wait_for(client.request("GET", "/vacancies"), 5) == {
            "ok": True
        }
    finally:
        event.remove(target, event_name, fail_once)


async def test_cancellation_waits_for_sdk_and_token_commit(
    pg_session_factory: async_sessionmaker[AsyncSession],
    owners: list[int],
    api_factory: FakeHHAPIFactory,
) -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    def configure(api: FakeHHAPIClient) -> None:
        if api.tokens.access_token == "owner-a":
            api.started = started
            api.release = release
            api.replacement = make_token_data(access_token="rotated")

    api_factory.configure = configure
    first = asyncio.create_task(
        AuthorizedHHAPIClient(
            pg_session_factory,
            owners[0],
            allow_token_refresh=True,
        ).request("GET", "/vacancies")
    )
    second = None
    try:
        await asyncio.wait_for(started.wait(), 5)
        first.cancel()
        await asyncio.sleep(0)
        assert not first.done()
        second = asyncio.create_task(
            AuthorizedHHAPIClient(
                pg_session_factory,
                owners[0],
                allow_token_refresh=True,
            ).request("GET", "/vacancies")
        )
        await _wait_for_blocked_request(pg_session_factory)
        assert len(api_factory.instances) == 1
        first.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(first, 5)
        assert await asyncio.wait_for(second, 5) == {"ok": True}
        assert api_factory.instances[1].initial_tokens.access_token == "rotated"
    finally:
        release.set()
        await asyncio.gather(
            first, *([second] if second else []), return_exceptions=True
        )


async def test_cancelled_waiter_never_starts_http(
    pg_session_factory: async_sessionmaker[AsyncSession],
    owners: list[int],
    api_factory: FakeHHAPIFactory,
) -> None:
    release = asyncio.Event()
    started = asyncio.Event()

    def configure(api: FakeHHAPIClient) -> None:
        api.started = started
        api.release = release

    api_factory.configure = configure
    first = asyncio.create_task(
        AuthorizedHHAPIClient(
            pg_session_factory,
            owners[0],
            allow_token_refresh=True,
        ).request("GET", "/vacancies")
    )
    waiter = None
    try:
        await asyncio.wait_for(started.wait(), 5)
        waiter = asyncio.create_task(
            AuthorizedHHAPIClient(
                pg_session_factory,
                owners[0],
                allow_token_refresh=True,
            ).request("GET", "/vacancies")
        )
        await _wait_for_blocked_request(pg_session_factory)
        waiter.cancel()
        # Освобождаем первый запрос: отменённый waiter всё равно не должен
        # получить право на HTTP после снятия блокировки.
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(waiter, 5)
        await asyncio.wait_for(first, 5)
        assert len(api_factory.instances) == 1
    finally:
        release.set()
        await asyncio.gather(
            first, *([waiter] if waiter else []), return_exceptions=True
        )
