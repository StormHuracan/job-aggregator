from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import pytest
from hh_applicant_tool import api as hh_api
from requests import ConnectionError, PreparedRequest, Response
from requests.adapters import HTTPAdapter

from job_aggregator.integrations.hh.client import HHAPIClient, HHOAuthClient
from job_aggregator.integrations.hh.errors import HHIntegrationError
from job_aggregator.schemas.hh_token import HHAccountTokenData


def _dto(
    access: str = "USER-access", expires_at: datetime | None = None
) -> HHAccountTokenData:
    return HHAccountTokenData(
        access_token=access,
        refresh_token="USER-refresh",
        access_expires_at=expires_at or datetime(2030, 1, 1, tzinfo=UTC),
    )


class _FakeApiClient:
    instances: list["_FakeApiClient"] = []

    def __init__(self, **kwargs: Any) -> None:
        self.init_kwargs = kwargs
        self._access_token = kwargs.get("access_token") or ""
        self._refresh_token = kwargs.get("refresh_token") or ""
        self._access_expires_at = int(kwargs.get("access_expires_at") or 0)
        self.request_calls: list[tuple[str, str, dict | None]] = []
        self.raise_error: Exception | None = None
        self.response: Any = {"ok": True}
        _FakeApiClient.instances.append(self)

    def request(self, method: str, endpoint: str, params: dict | None = None) -> Any:
        self.request_calls.append((method, endpoint, params))
        if self.raise_error is not None:
            raise self.raise_error
        return self.response

    def get_access_token(self) -> dict[str, Any]:
        return {
            "access_token": self._access_token,
            "refresh_token": self._refresh_token,
            "access_expires_at": self._access_expires_at,
        }


class _FakeOAuthClient:
    instances: list["_FakeOAuthClient"] = []
    fail_codes: set[str] = set()
    fail_error: Exception | None = None

    def __init__(self, **kwargs: Any) -> None:
        self.init_kwargs = kwargs
        self.authenticate_result: dict[str, Any] = {
            "access_token": "USER-new-access",
            "refresh_token": "USER-new-refresh",
            "access_expires_at": int(datetime(2030, 1, 1, tzinfo=UTC).timestamp()),
        }
        _FakeOAuthClient.instances.append(self)

    @property
    def authorize_url(self) -> str:
        client_id = self.init_kwargs.get("client_id") or "default-client"
        redirect = self.init_kwargs.get("redirect_uri") or ""
        params = urlencode({"client_id": client_id, "redirect_uri": redirect})
        return f"https://hh.ru/oauth/authorize?{params}"

    def authenticate(self, code: str) -> dict[str, Any]:
        if code in _FakeOAuthClient.fail_codes:
            if _FakeOAuthClient.fail_error is not None:
                raise _FakeOAuthClient.fail_error
            raise hh_api.BadResponse("oauth boom")
        return self.authenticate_result


@pytest.fixture(autouse=True)
def _reset_fakes() -> None:
    _FakeApiClient.instances.clear()
    _FakeOAuthClient.instances.clear()


@pytest.fixture
def fake_api(monkeypatch: pytest.MonkeyPatch) -> type[_FakeApiClient]:
    monkeypatch.setattr(hh_api, "ApiClient", _FakeApiClient)
    return _FakeApiClient


async def test_real_sdk_uses_bounded_socket_timeouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[Any] = []

    def send(self: HTTPAdapter, request: PreparedRequest, **kwargs: Any) -> Response:
        seen.append(kwargs.get("timeout"))
        response = Response()
        response.status_code = 200
        response._content = b'{"ok": true}'
        response.request = request
        response.url = request.url
        return response

    monkeypatch.setattr(HTTPAdapter, "send", send)
    client = HHAPIClient(_dto(), allow_token_refresh=False)
    assert await client.request("GET", "/vacancies") == {"ok": True}
    assert seen == [(5, 30)]
    client.close()


@pytest.fixture
def fake_oauth(monkeypatch: pytest.MonkeyPatch) -> type[_FakeOAuthClient]:
    monkeypatch.setattr(hh_api, "OAuthClient", _FakeOAuthClient)
    return _FakeOAuthClient


async def test_api_client_passes_tokens_as_unix_timestamp(
    fake_api: type[_FakeApiClient],
) -> None:
    tokens = _dto(expires_at=datetime(2030, 1, 1, tzinfo=UTC))
    HHAPIClient(
        tokens,
        allow_token_refresh=True,
        client_id="cid",
        client_secret="cs",
    )

    kwargs = fake_api.instances[-1].init_kwargs
    assert kwargs["access_token"] == "USER-access"
    assert kwargs["refresh_token"] == "USER-refresh"
    assert kwargs["access_expires_at"] == int(
        datetime(2030, 1, 1, tzinfo=UTC).timestamp()
    )
    assert kwargs["client_id"] == "cid"
    assert kwargs["client_secret"] == "cs"


async def test_api_client_without_refresh_does_not_pass_refresh_token(
    fake_api: type[_FakeApiClient],
) -> None:
    HHAPIClient(_dto(), allow_token_refresh=False)
    kwargs = fake_api.instances[-1].init_kwargs
    assert "refresh_token" not in kwargs


async def test_api_client_request_delegates_to_library(
    fake_api: type[_FakeApiClient],
) -> None:
    client = HHAPIClient(_dto(), allow_token_refresh=True)
    result = await client.request("GET", "/vacancies", {"text": "python"})

    assert result == {"ok": True}
    assert fake_api.instances[-1].request_calls == [
        ("GET", "/vacancies", {"text": "python"})
    ]


async def test_api_client_returns_updated_tokens_after_refresh(
    fake_api: type[_FakeApiClient],
) -> None:
    client = HHAPIClient(_dto(), allow_token_refresh=True)
    fake = fake_api.instances[-1]

    def request_and_refresh(
        method: str, endpoint: str, params: dict | None = None
    ) -> Any:
        fake._access_token = "USER-refreshed"
        fake._access_expires_at = int(datetime(2031, 1, 1, tzinfo=UTC).timestamp())
        return {"ok": True}

    fake.request = request_and_refresh  # type: ignore[assignment]

    await client.request("GET", "/vacancies")

    current = client.get_current_tokens()
    assert current.access_token == "USER-refreshed"
    assert current.refresh_token == "USER-refresh"
    assert current.access_expires_at == datetime(2031, 1, 1, tzinfo=UTC)


async def test_api_client_keeps_refreshed_tokens_when_request_fails(
    fake_api: type[_FakeApiClient],
) -> None:
    client = HHAPIClient(_dto(), allow_token_refresh=True)
    fake = fake_api.instances[-1]

    def request_refresh_then_fail(
        method: str, endpoint: str, params: dict | None = None
    ) -> Any:
        fake._access_token = "USER-refreshed"
        fake._access_expires_at = int(datetime(2031, 1, 1, tzinfo=UTC).timestamp())
        raise hh_api.BadResponse("second request failed")

    fake.request = request_refresh_then_fail  # type: ignore[assignment]

    with pytest.raises(HHIntegrationError):
        await client.request("GET", "/vacancies")

    assert client.get_current_tokens().access_token == "USER-refreshed"


async def test_api_client_wraps_library_errors(
    fake_api: type[_FakeApiClient],
) -> None:
    client = HHAPIClient(_dto(), allow_token_refresh=False)
    original = hh_api.BadResponse("boom with sensitive info")
    fake_api.instances[-1].raise_error = original

    with pytest.raises(HHIntegrationError) as exc_info:
        await client.request("GET", "/vacancies")

    assert exc_info.value.__cause__ is original
    assert "sensitive info" not in str(exc_info.value)


def test_oauth_client_builds_authorization_url(
    fake_oauth: type[_FakeOAuthClient],
) -> None:
    client = HHOAuthClient(client_id="cid", client_secret="cs")
    url = client.get_authorization_url("https://example.com/callback", "test-state")

    assert url.startswith("https://hh.ru/oauth/authorize?")
    assert "client_id=cid" in url
    assert "redirect_uri=https%3A%2F%2Fexample.com%2Fcallback" in url
    assert fake_oauth.instances[-1].init_kwargs["state"] == "test-state"


async def test_oauth_client_exchanges_code(
    fake_oauth: type[_FakeOAuthClient],
) -> None:
    client = HHOAuthClient(client_id="cid", client_secret="cs")
    tokens = await client.exchange_code("code-123", "https://example.com/cb")

    assert tokens.access_token == "USER-new-access"
    assert tokens.refresh_token == "USER-new-refresh"
    assert tokens.access_expires_at == datetime(2030, 1, 1, tzinfo=UTC)


async def test_oauth_client_wraps_library_errors(
    fake_oauth: type[_FakeOAuthClient],
) -> None:
    client = HHOAuthClient(client_id="cid", client_secret="cs")
    original = hh_api.BadResponse("oauth boom with code and client_secret")
    _FakeOAuthClient.fail_codes = {"bad"}
    _FakeOAuthClient.fail_error = original
    try:
        with pytest.raises(HHIntegrationError) as exc_info:
            await client.exchange_code("bad", "https://example.com/cb")
    finally:
        _FakeOAuthClient.fail_codes = set()
        _FakeOAuthClient.fail_error = None

    assert exc_info.value.__cause__ is original
    message = str(exc_info.value)
    assert "oauth boom" not in message
    assert "client_secret" not in message


async def test_api_client_retries_temporary_library_error(
    fake_api: type[_FakeApiClient],
) -> None:
    delays: list[float] = []

    async def record_sleep(seconds: float) -> None:
        delays.append(seconds)

    client = HHAPIClient(_dto(), allow_token_refresh=False, retry_sleep=record_sleep)
    fake = fake_api.instances[-1]
    calls = 0

    def fail_twice_then_answer(
        method: str, endpoint: str, params: dict | None = None
    ) -> Any:
        nonlocal calls
        calls += 1
        if calls <= 2:
            raise ConnectionError("network down")
        return {"ok": True}

    fake.request = fail_twice_then_answer  # type: ignore[assignment]

    result = await client.request("GET", "/vacancies")

    assert result == {"ok": True}
    assert calls == 3
    assert delays == [0.5, 1.0]


@pytest.mark.parametrize("invalid_id", [True, False, [], {}, 1.5, "", " ", None, -1, 0])
async def test_current_user_rejects_invalid_identity(fake_api, invalid_id) -> None:
    from job_aggregator.integrations.hh.errors import HHPermanentRequestError

    client = HHAPIClient(_dto(), allow_token_refresh=False)
    fake_api.instances[-1].response = {"id": invalid_id, "first_name": "Иван"}
    try:
        with pytest.raises(HHPermanentRequestError):
            await client.get_current_user()
    finally:
        client.close()


@pytest.mark.parametrize(
    ("payload", "expected_id", "expected_name"),
    [
        (
            {
                "id": "123",
                "first_name": " Иван ",
                "middle_name": "Иванович",
                "last_name": "Иванов",
            },
            "123",
            "Иван Иванович Иванов",
        ),
        ({"id": 123, "first_name": None, "last_name": " "}, "123", "123"),
    ],
)
async def test_current_user_normalizes_profile(
    fake_api, payload, expected_id, expected_name
) -> None:
    client = HHAPIClient(_dto(), allow_token_refresh=False)
    fake_api.instances[-1].response = payload
    try:
        profile = await client.get_current_user()
        assert profile.hh_user_id == expected_id
        assert profile.display_name == expected_name
        assert fake_api.instances[-1].request_calls == [("GET", "/me", None)]
    finally:
        client.close()


@pytest.mark.parametrize(
    "payload",
    [
        [],
        None,
        {"id": "123", "first_name": {}},
        {"id": "x" * 256},
        {"id": "123", "last_name": "x" * 256},
    ],
)
async def test_current_user_rejects_malformed_profile(fake_api, payload) -> None:
    from job_aggregator.integrations.hh.errors import HHPermanentRequestError

    client = HHAPIClient(_dto(), allow_token_refresh=False)
    fake_api.instances[-1].response = payload
    try:
        with pytest.raises(HHPermanentRequestError, match="HH invalid profile"):
            await client.get_current_user()
    finally:
        client.close()


async def test_oauth_exchange_uses_bounded_timeout_and_closes_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = []
    closed = []
    from requests import Session

    original_close = Session.close

    def close(session) -> None:
        closed.append(session)
        original_close(session)

    def send(adapter, request, **kwargs):
        seen.append(kwargs.get("timeout"))
        response = Response()
        response.status_code = 200
        response._content = (
            b'{"access_token":"test-access","refresh_token":"test-refresh",'
            b'"expires_in":3600}'
        )
        response.request = request
        response.url = request.url
        return response

    monkeypatch.setattr(Session, "close", close)
    monkeypatch.setattr(HTTPAdapter, "send", send)
    result = await HHOAuthClient(
        client_id="test-id", client_secret="test-secret"
    ).exchange_code("test-code", "https://example.test/callback")
    assert result.access_token == "test-access"
    assert seen == [(5, 30)]
    assert len(closed) == 1


@pytest.mark.parametrize(
    "response_body",
    [b"[]", b"{}", b'{"access_token":"a","refresh_token":"r","expires_in":"invalid"}'],
)
async def test_malformed_oauth_response_is_safe(
    monkeypatch: pytest.MonkeyPatch, response_body: bytes
) -> None:
    from job_aggregator.integrations.hh.errors import HHPermanentRequestError

    def send(adapter, request, **kwargs):
        response = Response()
        response.status_code = 200
        response._content = response_body
        response.request = request
        response.url = request.url
        return response

    monkeypatch.setattr(HTTPAdapter, "send", send)
    with pytest.raises(HHPermanentRequestError, match="HH invalid token response"):
        await HHOAuthClient(
            client_id="test-id", client_secret="test-secret"
        ).exchange_code("private-code", "https://example.test/callback")


async def test_oauth_network_failure_is_not_retried_and_closes_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from requests import Session

    from job_aggregator.integrations.hh.errors import HHTemporaryError

    closed = []
    attempts = []
    original_close = Session.close

    def close(session: Session) -> None:
        closed.append(session)
        original_close(session)

    def send(adapter, request, **kwargs):
        attempts.append(request)
        raise ConnectionError("private-network-details")

    monkeypatch.setattr(Session, "close", close)
    monkeypatch.setattr(HTTPAdapter, "send", send)
    with pytest.raises(HHTemporaryError, match="HH network error"):
        await HHOAuthClient(
            client_id="test-id", client_secret="test-secret"
        ).exchange_code("private-code", "https://example.test/callback")
    assert len(attempts) == 1
    assert len(closed) == 1
