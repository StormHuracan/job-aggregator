import pytest


from httpx import AsyncClient, ASGITransport
from job_aggregator.main import create_app


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