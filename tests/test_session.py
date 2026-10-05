from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.session import create_engine_and_factory, get_db_session


async def test_session_factory_yields_working_session() -> None:
    engine, factory = create_engine_and_factory("sqlite+aiosqlite:///:memory:")
    try:
        async with factory() as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1
    finally:
        await engine.dispose()


def test_dependency_provides_and_closes_session() -> None:
    engine, factory = create_engine_and_factory("sqlite+aiosqlite:///:memory:")

    test_app = FastAPI()
    test_app.state.session_factory = factory

    @test_app.get("/probe")
    async def probe(
        session: AsyncSession = Depends(get_db_session),
    ) -> dict[str, bool]:
        await session.execute(text("SELECT 1"))
        return {"ok": True}

    with TestClient(test_app) as client:
        response = client.get("/probe")
        assert response.status_code == 200
        assert response.json() == {"ok": True}