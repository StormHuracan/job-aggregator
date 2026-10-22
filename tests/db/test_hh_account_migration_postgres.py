import asyncio
import os
import subprocess
import sys

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_aggregator.db.base import Base
from job_aggregator.db.models.hh_account import HHAccount
from job_aggregator.db.models.hh_account_token import HHAccountToken
from job_aggregator.db.models.user import User
from job_aggregator.db.session import create_engine_and_factory
from tests.factories import make_token_data
from tests.paths import PROJECT_ROOT


async def test_migration_preserves_legacy_tokens_and_enforces_constraints(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Миграция проверяется исключительно на TEST_DATABASE_URL, не рабочей БД."""
    url = os.environ["TEST_DATABASE_URL"]
    engine, factory = create_engine_and_factory(url)
    env = {**os.environ, "DATABASE_URL": url}

    async def migrate(revision: str, direction: str = "upgrade") -> None:
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

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        await migrate("f31a8b7d4c2e")
        async with factory.begin() as session:
            session.add(HHAccountToken(**make_token_data().model_dump()))
        await migrate("head")
        async with engine.connect() as conn:
            tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
            assert "hh_accounts" in tables
            columns = await conn.run_sync(
                lambda c: inspect(c).get_columns("hh_accounts")
            )
            assert all(not column["nullable"] for column in columns)
            dates = {"access_expires_at", "created_at", "updated_at"}
            assert all(c["type"].timezone for c in columns if c["name"] in dates)
        async with factory.begin() as session:
            legacy = await session.scalar(select(HHAccountToken))
            assert legacy is not None and legacy.access_token == "access-1"
            assert legacy.refresh_token == "refresh-1"
            assert legacy.access_expires_at == make_token_data().access_expires_at
            assert await session.scalar(select(HHAccount)) is None
            user = User(hh_user_id="42", display_name="Пользователь")
            session.add(user)
            await session.flush()
            user_id = user.id
            session.add(HHAccount(user_id=user_id, **make_token_data().model_dump()))
        async with factory() as session:
            session.add(HHAccount(user_id=user_id, **make_token_data().model_dump()))
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()
            session.add(
                HHAccount(user_id=user_id + 1, **make_token_data().model_dump())
            )
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()
        await migrate("f31a8b7d4c2e", "downgrade")
        async with engine.connect() as conn:
            tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
            assert "hh_accounts" not in tables
        async with factory() as session:
            legacy = await session.scalar(select(HHAccountToken))
            assert legacy is not None and legacy.access_token == "access-1"
    finally:
        await engine.dispose()
