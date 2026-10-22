import pytest
from pydantic import ValidationError

from job_aggregator.schemas.saved_search import SavedSearchCreate, SavedSearchUpdate


def test_create_schema_strips_required_strings() -> None:
    payload = SavedSearchCreate(name="  Python  ", text="  backend  ")

    assert payload.name == "Python"
    assert payload.text == "backend"


@pytest.mark.parametrize("field", ["name", "text"])
@pytest.mark.parametrize("value", ["", " ", "   ", "\t\n"])
def test_create_schema_rejects_blank_required_strings(field: str, value: str) -> None:
    payload = {"name": "Python", "text": "backend"}
    payload[field] = value

    with pytest.raises(ValidationError):
        SavedSearchCreate.model_validate(payload)


@pytest.mark.parametrize("field", ["name", "text", "area"])
def test_create_schema_rejects_strings_longer_than_255(field: str) -> None:
    payload = {"name": "Python", "text": "backend", "area": None}
    payload[field] = "x" * 256

    with pytest.raises(ValidationError):
        SavedSearchCreate.model_validate(payload)


def test_create_schema_accepts_trimmed_string_of_255_characters() -> None:
    payload = SavedSearchCreate(name=f" {'x' * 255} ", text="backend")

    assert payload.name == "x" * 255


@pytest.mark.parametrize("field", ["min_salary", "max_salary"])
def test_create_schema_rejects_negative_salary(field: str) -> None:
    with pytest.raises(ValidationError):
        SavedSearchCreate.model_validate(
            {"name": "Python", "text": "backend", field: -1}
        )


def test_create_schema_rejects_min_salary_above_max_salary() -> None:
    with pytest.raises(ValidationError):
        SavedSearchCreate(
            name="Python", text="backend", min_salary=5000, max_salary=1000
        )


def test_create_schema_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        SavedSearchCreate(name="Python", text="backend", user_id=123)


def test_update_schema_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        SavedSearchUpdate(is_enabled=False, name="Changed")
