from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from job_aggregator.schemas.hh_token import HHAccountTokenData


def test_hh_account_token_data_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError):
        HHAccountTokenData(
            access_token="a",
            refresh_token="r",
            access_expires_at=datetime(2030, 1, 1, 12, 0, 0),
        )


def test_hh_account_token_data_normalizes_to_utc() -> None:
    tz = timezone(timedelta(hours=3))
    data = HHAccountTokenData(
        access_token="a",
        refresh_token="r",
        access_expires_at=datetime(2030, 1, 1, 12, 0, 0, tzinfo=tz),
    )
    assert data.access_expires_at.utcoffset() == timedelta(0)
