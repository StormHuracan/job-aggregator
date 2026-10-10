from datetime import UTC

import pytest
from sqlalchemy import event

from job_aggregator.db.models.hh_account_token import HHAccountToken


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
