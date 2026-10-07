import pytest
from pydantic import ValidationError

from job_aggregator.schemas.collection import (
    CollectionRunRequest,
    CollectionRunResponse,
)


def test_collection_run_request_valid() -> None:
    request = CollectionRunRequest(
        text="Python developer",
        area="Москва",
        pages_limit=3,
    )

    assert request.text == "Python developer"
    assert request.area == "Москва"
    assert request.pages_limit == 3


@pytest.mark.parametrize("text", ["", "   "])
def test_collection_run_request_invalid_text(text: str) -> None:
    with pytest.raises(ValidationError):
        CollectionRunRequest(
            text=text,
            area="Москва",
            pages_limit=3,
        )


@pytest.mark.parametrize("pages_limit", [0, -1])
def test_collection_run_request_invalid_pages_limit(pages_limit: int) -> None:
    with pytest.raises(ValidationError):
        CollectionRunRequest(
            text="Python developer",
            area="Москва",
            pages_limit=pages_limit,
        )


def test_collection_run_response_valid() -> None:
    response = CollectionRunResponse(
        created=10,
        updated=5,
        skipped=2,
        failed=0,
    )

    assert response.created == 10
    assert response.updated == 5
    assert response.skipped == 2
    assert response.failed == 0


@pytest.mark.parametrize("field", ["created", "updated", "skipped", "failed"])
def test_collection_run_response_rejects_negative_values(field: str) -> None:
    data = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
    }
    data[field] = -1

    with pytest.raises(ValidationError):
        CollectionRunResponse(**data)
