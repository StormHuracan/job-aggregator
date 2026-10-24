import os
import subprocess
import sys

from tests.paths import PROJECT_ROOT


def test_offline_migrations_accept_percent_encoded_password() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        filter(
            None,
            [str(PROJECT_ROOT / "src"), env.get("PYTHONPATH", "")],
        )
    )
    env["DATABASE_URL"] = "postgresql+asyncpg://test:sample%40password@localhost/test"

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_offline_migration_creates_user_and_session_constraints() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        filter(
            None,
            [str(PROJECT_ROOT / "src"), env.get("PYTHONPATH", "")],
        )
    )
    env["DATABASE_URL"] = "postgresql+asyncpg://test:sample%40password@localhost/test"

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "CREATE TABLE users" in result.stdout
    assert "UNIQUE (hh_user_id)" in result.stdout
    assert "CREATE TABLE user_settings" in result.stdout
    assert "default_pages_limit INTEGER DEFAULT 5 NOT NULL" in result.stdout
    assert "ck_user_settings_default_pages_limit_positive" in result.stdout
    assert "CREATE TABLE oauth_states" in result.stdout
    assert "UNIQUE (state_hash)" in result.stdout
    assert "CREATE TABLE user_sessions" in result.stdout
    assert "FOREIGN KEY(user_id) REFERENCES users (id)" in result.stdout
    assert "UNIQUE (token_hash)" in result.stdout
