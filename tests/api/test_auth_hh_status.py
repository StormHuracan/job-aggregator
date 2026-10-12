from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from job_aggregator.api.dependencies import get_token_service
from job_aggregator.schemas.hh_token import HHAccountTokenData
from job_aggregator.services.tokens import TokenService
from tests.factories import make_token_data

ENDPOINT = "/auth/hh/status"
FUTURE_EXPIRY = datetime(2100, 1, 1, tzinfo=UTC)
PAST_EXPIRY = datetime(2000, 1, 1, tzinfo=UTC)


def _install_fake_token_service(
    client: TestClient, tokens: HHAccountTokenData | None
) -> MagicMock:
    fake = MagicMock(spec=TokenService)
    fake.get_current = AsyncMock(return_value=tokens)
    fake.save = AsyncMock()
    client.app.dependency_overrides[get_token_service] = lambda: fake
    return fake


def test_status_without_tokens(client: TestClient) -> None:
    fake = _install_fake_token_service(client, None)

    response = client.get(ENDPOINT)

    assert response.status_code == 200, response.text
    assert response.json() == {"connected": False, "access_expires_at": None}
    fake.get_current.assert_awaited_once()
    fake.save.assert_not_awaited()


def test_status_with_valid_token(client: TestClient) -> None:
    fake = _install_fake_token_service(
        client, make_token_data(access_expires_at=FUTURE_EXPIRY)
    )

    response = client.get(ENDPOINT)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["connected"] is True
    parsed = datetime.fromisoformat(body["access_expires_at"].replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)
    assert parsed == FUTURE_EXPIRY
    fake.get_current.assert_awaited_once()
    fake.save.assert_not_awaited()


def test_status_with_expired_token(client: TestClient) -> None:
    fake = _install_fake_token_service(
        client, make_token_data(access_expires_at=PAST_EXPIRY)
    )

    response = client.get(ENDPOINT)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["connected"] is True
    parsed = datetime.fromisoformat(body["access_expires_at"].replace("Z", "+00:00"))
    assert parsed == PAST_EXPIRY
    fake.get_current.assert_awaited_once()
    fake.save.assert_not_awaited()


def test_status_response_contains_no_secrets(client: TestClient) -> None:
    tokens = make_token_data(
        access_token="ACCESS-SECRET",
        refresh_token="REFRESH-SECRET",
        access_expires_at=FUTURE_EXPIRY,
    )
    _install_fake_token_service(client, tokens)

    response = client.get(ENDPOINT)

    assert response.status_code == 200, response.text
    assert set(response.json()) == {"connected", "access_expires_at"}
    for secret in (tokens.access_token, tokens.refresh_token):
        assert secret not in response.text


def test_status_does_not_touch_hh_or_write(client: TestClient) -> None:
    fake = _install_fake_token_service(
        client, make_token_data(access_expires_at=PAST_EXPIRY)
    )

    response = client.get(ENDPOINT)

    assert response.status_code == 200
    fake.save.assert_not_awaited()
    fake.get_current.assert_awaited_once()
