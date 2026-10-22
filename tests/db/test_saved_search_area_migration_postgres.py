import asyncio
import os
import subprocess
import sys

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_aggregator.db.base import Base
from job_aggregator.db.models.saved_search import SavedSearch
from job_aggregator.db.models.user import User
from job_aggregator.db.repositories.saved_search import UserSavedSearchRepository
from tests.paths import PROJECT_ROOT


async def test_area_migration_preserves_searches_and_accepts_255_characters(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Проверяет расширение и обратимость на отдельной TEST_DATABASE_URL."""
    engine = pg_session_factory.kw["bind"]
    env = {**os.environ, "DATABASE_URL": os.environ["TEST_DATABASE_URL"]}

    async def migrate(direction: str, revision: str) -> None:
        result = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "-m", "alembic", direction, revision],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    await migrate("upgrade", "5a2d3c72bc8f")

    async with pg_session_factory.begin() as session:
        user = User(hh_user_id="area-migration", display_name="Пользователь")
        session.add(user)
        await session.flush()
        user_id = user.id
        legacy = await UserSavedSearchRepository(session).create(
            user_id,
            name="Существующий поиск",
            text="python",
            area="я" * 100,
            min_salary=None,
            max_salary=None,
        )
        legacy_id = legacy.id

    await migrate("upgrade", "head")
    async with pg_session_factory.begin() as session:
        legacy = await session.get(SavedSearch, legacy_id)
        assert legacy is not None and legacy.area == "я" * 100
        for length in (101, 255):
            await UserSavedSearchRepository(session).create(
                user_id,
                name=f"Регион {length}",
                text="python",
                area="я" * length,
                min_salary=None,
                max_salary=None,
            )

    async with pg_session_factory() as session:
        searches = await UserSavedSearchRepository(session).list_for_user(user_id)
        assert [len(search.area) for search in searches] == [100, 101, 255]

    # Сужение area до 100 живёт в c47e92ab6130, а не в текущей голове.
    async with pg_session_factory.begin() as session:
        await session.execute(delete(SavedSearch).where(SavedSearch.id != legacy_id))
    await migrate("downgrade", "5a2d3c72bc8f")
    async with engine.connect() as connection:
        length = await connection.scalar(
            text(
                "SELECT character_maximum_length FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'saved_searches' "
                "AND column_name = 'area'"
            )
        )
        assert length == 100
    await migrate("upgrade", "head")
    async with pg_session_factory() as session:
        assert await session.scalar(select(SavedSearch.area)) == "я" * 100
