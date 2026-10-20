import asyncio
import logging

import pytest
from sqlalchemy.exc import OperationalError

from job_aggregator.db.repositories.vacancy import VacancySaveError, VacancyUpsertResult
from job_aggregator.integrations.hh.dto import HHVacancyPage, HHVacancySearchParams
from job_aggregator.integrations.hh.errors import HHTemporaryError
from job_aggregator.schemas.collection import CollectionRunResponse
from job_aggregator.services.collection import VacancyCollectionService
from tests.factories import make_vacancy_data
from tests.fakes.hh import FakeHHClient
from tests.fakes.vacancy import FakeVacancyRepository


async def test_empty_page_returns_zero_counts() -> None:
    params = HHVacancySearchParams(text="python", page=2)
    client = FakeHHClient(pages={2: HHVacancyPage(items=[], page=2, found=0, pages=3)})
    repo = FakeVacancyRepository([])

    result = await VacancyCollectionService(client, repo).collect(params)

    assert result == CollectionRunResponse(created=0, updated=0, skipped=0, failed=0)
    assert client.calls == [params]
    assert repo.calls == []


async def test_search_failure_does_not_start_persistence(
    caplog: pytest.LogCaptureFixture,
) -> None:
    error = HHTemporaryError("external failure")
    client = FakeHHClient(pages={}, error=error)
    repo = FakeVacancyRepository([])
    params = HHVacancySearchParams(text="python")

    with pytest.raises(HHTemporaryError) as caught:
        await VacancyCollectionService(client, repo).collect(params)

    assert caught.value is error
    assert client.calls == [params]
    assert repo.calls == []
    assert "Collection failed: HHTemporaryError" in caplog.text
    assert "external failure" not in caplog.text


@pytest.mark.parametrize(
    "error",
    [
        OperationalError("SQL", {}, Exception("connection lost")),
        RuntimeError("programming error"),
        asyncio.CancelledError(),
    ],
)
async def test_fatal_persistence_failure_stops_collection(error: BaseException) -> None:
    items = [make_vacancy_data(external_id=str(index)) for index in range(3)]
    client = FakeHHClient(
        pages={0: HHVacancyPage(items=items, page=0, found=3, pages=1)}
    )
    repo = FakeVacancyRepository([VacancyUpsertResult.CREATED, error])

    with pytest.raises(type(error)) as caught:
        await VacancyCollectionService(client, repo).collect(
            HHVacancySearchParams(text="python")
        )

    assert caught.value is error
    assert repo.calls == items[:2]


async def test_collection_logs_counts_without_payload_or_error_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "test-payload-must-not-appear"
    item = make_vacancy_data(title=secret, raw_data={"token": secret})
    client = FakeHHClient(
        pages={0: HHVacancyPage(items=[item], page=0, found=1, pages=1)}
    )
    repo = FakeVacancyRepository([VacancySaveError(secret)])

    with caplog.at_level(logging.INFO):
        await VacancyCollectionService(client, repo).collect(
            HHVacancySearchParams(text=secret)
        )

    assert "Collection started" in caplog.text
    assert "received=1 created=0 updated=0 skipped=0 failed=1" in caplog.text
    assert secret not in caplog.text
    assert repo.calls == [item]


async def test_mixed_results_and_repeated_items_are_counted() -> None:
    params = HHVacancySearchParams(text="python")
    item = make_vacancy_data()
    items = [item, item, make_vacancy_data(external_id="bad"), item]
    client = FakeHHClient(
        pages={0: HHVacancyPage(items=items, page=0, found=4, pages=1)}
    )
    repo = FakeVacancyRepository(
        [
            VacancyUpsertResult.CREATED,
            VacancyUpsertResult.UPDATED,
            VacancySaveError("bad item"),
            VacancyUpsertResult.UNCHANGED,
        ]
    )

    result = await VacancyCollectionService(client, repo).collect(params)

    assert result == CollectionRunResponse(created=1, updated=1, skipped=1, failed=1)
    assert repo.calls == items
    assert client.calls == [params]
