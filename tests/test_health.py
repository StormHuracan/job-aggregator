from fastapi.testclient import TestClient
from job_aggregator.api.health import get_db_session
from unittest.mock import AsyncMock

async def test_health(client) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_DB(app, client) -> None:
    """Создает заглушку для проверки, подменной сессии
    и отвечает успешно, не ходит в реальную БД"""
    fake_session = AsyncMock()
    app.dependency_overrides[get_db_session] = lambda: fake_session
    response = await client.get("/health/db")
    assert response.status_code == 200
    fake_session.execute.assert_awaited_once()

def test_app_empty_substitutions(app) -> None:
    assert app.dependency_overrides == {}


def test_health_check_returns_ok(app) -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
