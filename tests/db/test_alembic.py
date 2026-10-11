import os
import subprocess
import sys
from tests.paths import PROJECT_ROOT


def test_offline_migrations_accept_percent_encoded_password() -> None:
    env = os.environ.copy()
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
