from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine_and_factory(
    database_url: str,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(database_url, echo=False, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI-зависимость: выдаёт AsyncSession на запрос и закрывает после."""
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        yield session
