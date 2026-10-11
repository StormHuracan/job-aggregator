# tests/test_auth_hh_status.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from job_aggregator.api.dependencies import get_token_service
from job_aggregator.main import app
from job_aggregator.schemas.hh_token import HHAccountTokenData

ENDPOINT = "/auth/hh/status"


@pytest.fixture
def client():
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _install_fake_token_service(tokens: HHAccountTokenData | None) -> MagicMock:
    """Подменяет TokenService моком с заданным результатом get_current()."""
    fake = MagicMock()  # без spec — см. объяснение ниже
    fake.get_current = AsyncMock(return_value=tokens)
    fake.save = AsyncMock()
    app.dependency_overrides[get_token_service] = lambda: fake
    return fake


def _make_tokens(access_expires_at: datetime) -> HHAccountTokenData:
    return HHAccountTokenData(
        access_token="ACCESS-SECRET",
        refresh_token="REFRESH-SECRET",
        access_expires_at=access_expires_at,
    )


# ---------- 1. Токенов нет ----------


def test_status_without_tokens(client):
    fake = _install_fake_token_service(None)

    r = client.get(ENDPOINT)

    assert r.status_code == 200, r.text
    assert r.json() == {"connected": False, "access_expires_at": None}
    fake.get_current.assert_awaited_once()
    fake.save.assert_not_awaited()


# ---------- 2. Действующий токен ----------


def test_status_with_valid_token(client):
    expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    fake = _install_fake_token_service(_make_tokens(expiry))

    r = client.get(ENDPOINT)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["connected"] is True

    parsed = datetime.fromisoformat(body["access_expires_at"].replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)
    assert parsed == expiry

    fake.get_current.assert_awaited_once()
    fake.save.assert_not_awaited()


# ---------- 3. Истёкший токен ----------


def test_status_with_expired_token(client):
    expiry = datetime.now(timezone.utc) - timedelta(hours=1)
    fake = _install_fake_token_service(_make_tokens(expiry))

    r = client.get(ENDPOINT)

    assert r.status_code == 200, r.text
    body = r.json()
    # истёкший access token — всё равно connected=True, срок фактический
    assert body["connected"] is True
    parsed = datetime.fromisoformat(body["access_expires_at"].replace("Z", "+00:00"))
    assert parsed == expiry
    assert parsed < datetime.now(timezone.utc)

    fake.get_current.assert_awaited_once()
    fake.save.assert_not_awaited()  # ← refresh/перезапись не выполняются


# ---------- 4. В ответе нет секретов и лишних полей ----------


def test_status_response_contains_no_secrets(client):
    expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
    _install_fake_token_service(_make_tokens(expiry))

    r = client.get(ENDPOINT)

    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) == {"connected", "access_expires_at"}
    for secret in ("ACCESS-SECRET", "REFRESH-SECRET"):
        assert secret not in r.text


# ---------- 5. Endpoint не пишет в хранилище и не запускает сбор ----------


def test_status_does_not_touch_hh_or_write(client):
    expiry = datetime.now(timezone.utc) - timedelta(days=1)
    fake = _install_fake_token_service(_make_tokens(expiry))

    client.get(ENDPOINT)

    # Единственный «побочный эффект», который реально может случиться — save().
    fake.save.assert_not_awaited()
    # и get_current вызван ровно один раз (никаких повторных чтений из БД)
    fake.get_current.assert_awaited_once()
