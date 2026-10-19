from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from job_aggregator.schemas.user import CurrentUserResponse, UserSettingsUpdate


def test_settings_update_without_area_leaves_it_unset() -> None:
    update = UserSettingsUpdate(default_pages_limit=10)

    assert update.model_fields_set == {"default_pages_limit"}


def test_settings_update_with_null_area_marks_it_as_set() -> None:
    update = UserSettingsUpdate(default_area=None)

    assert update.default_area is None
    assert update.model_fields_set == {"default_area"}


def test_settings_update_strips_area() -> None:
    update = UserSettingsUpdate(default_area="  Moscow  ")

    assert update.default_area == "Moscow"


@pytest.mark.parametrize(
    "payload",
    [
        {"default_pages_limit": 0},
        {"default_pages_limit": -1},
        {"default_area": ""},
        {"default_area": "   "},
        {"default_area": "x" * 256},
        {"is_admin": True},
    ],
)
def test_settings_update_rejects_invalid_payload(payload: dict) -> None:
    with pytest.raises(ValidationError):
        UserSettingsUpdate(**payload)


def _user_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": 1,
        "display_name": "Ivan",
        "hh_connected": True,
        "access_expires_at": None,
        "new_matches_count": 0,
        "settings": {"default_area": None, "default_pages_limit": 5},
    }
    payload.update(overrides)
    return payload


def test_current_user_converts_expiry_to_utc() -> None:
    moscow = timezone(timedelta(hours=3))
    user = CurrentUserResponse(
        **_user_payload(access_expires_at=datetime(2030, 1, 1, 15, 0, tzinfo=moscow))
    )

    assert user.access_expires_at == datetime(2030, 1, 1, 12, 0, tzinfo=UTC)


def test_current_user_rejects_naive_expiry() -> None:
    with pytest.raises(ValidationError):
        CurrentUserResponse(**_user_payload(access_expires_at=datetime(2030, 1, 1)))


def test_current_user_rejects_negative_matches_count() -> None:
    with pytest.raises(ValidationError):
        CurrentUserResponse(**_user_payload(new_matches_count=-1))


def test_current_user_does_not_serialize_secrets() -> None:
    user = CurrentUserResponse(
        **_user_payload(access_token="SECRET", refresh_token="SECRET")
    )

    data = user.model_dump()

    assert set(data) == {
        "id",
        "display_name",
        "hh_connected",
        "access_expires_at",
        "new_matches_count",
        "settings",
    }
