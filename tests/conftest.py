import pytest
from httpx import AsyncClient, ASGITransport
from job_aggregator.main import create_app
from datetime import UTC
from sqlalchemy import event
from job_aggregator.db.models.hh_account_token import HHAccountToken


@pytest.fixture
def app():
    """Создает отдельное приложение для теста и очищает dependency_overrides"""
    test_app = create_app()
    yield test_app
    test_app.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    """Предоставляет асинхронный HTTP клиент
    для запросов к тестовому приложению без внешней сети"""
    transport = ASGITransport(app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True)
def _sqlite_utc_datetimes():
    """SQLite теряет tz-info — восстанавливаем UTC при загрузке модели."""

    def _on_load(target, context):
        value = target.access_expires_at
        if value is not None and value.tzinfo is None:
            target.access_expires_at = value.replace(tzinfo=UTC)

    event.listen(HHAccountToken, "load", _on_load, propagate=True)
    yield
    event.remove(HHAccountToken, "load", _on_load)