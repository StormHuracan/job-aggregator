import asyncio
import os
import subprocess
import sys

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from job_aggregator.db.base import Base
from job_aggregator.db.models.user import User
from job_aggregator.db.repositories.collection_progress import (
    CollectionProgressRepository,
)
from tests.paths import PROJECT_ROOT


async def test_concurrent_first_runs_advance_without_losing_pages(pg_session_factory):
    async with pg_session_factory.begin() as session:
        session.add(User(id=1, hh_user_id="one", display_name="Один"))
    barrier = asyncio.Barrier(2)

    async def advance():
        async with pg_session_factory.begin() as session:
            await barrier.wait()
            progress = await CollectionProgressRepository(session).get_for_update(
                1, "a" * 64
            )
            start = progress.next_page
            await asyncio.sleep(0.02)
            progress.next_page += 1
            return start

    results = await asyncio.wait_for(asyncio.gather(advance(), advance()), timeout=5)
    assert sorted(results) == [0, 1]
    async with pg_session_factory() as session:
        progress = await CollectionProgressRepository(session).get_for_update(
            1, "a" * 64
        )
        assert progress.next_page == 2


async def test_new_position_rolls_back_and_foreign_key_is_not_hidden(
    pg_session_factory,
):
    async with pg_session_factory.begin() as session:
        session.add(User(id=1, hh_user_id="one", display_name="Один"))
    async with pg_session_factory() as session:
        repo = CollectionProgressRepository(session)
        progress = await repo.get_for_update(1, "a" * 64)
        progress.next_page = 3
        await session.flush()
        await session.rollback()
        progress = await repo.get_for_update(1, "a" * 64)
        assert progress.next_page == 0
        with pytest.raises(IntegrityError):
            await repo.get_for_update(999, "b" * 64)


async def test_progress_migration_preserves_users_and_is_reversible(pg_session_factory):
    engine = pg_session_factory.kw["bind"]
    env = {**os.environ, "DATABASE_URL": os.environ["TEST_DATABASE_URL"]}

    async def migrate(direction, revision):
        result = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "-m", "alembic", direction, revision],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    await migrate("upgrade", "36e60c2f8505")
    async with pg_session_factory.begin() as session:
        session.add(User(id=1, hh_user_id="preserved", display_name="Один"))
    await migrate("upgrade", "head")
    async with pg_session_factory.begin() as session:
        progress = await CollectionProgressRepository(session).get_for_update(
            1, "a" * 64
        )
        progress.next_page = 2
    await migrate("downgrade", "36e60c2f8505")
    async with pg_session_factory() as session:
        assert (
            await session.scalar(text("SELECT hh_user_id FROM users WHERE id=1"))
            == "preserved"
        )
        assert (
            await session.scalar(text("SELECT to_regclass('collection_progress')"))
            is None
        )
    await migrate("upgrade", "head")
