import asyncio
import logging
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import OperationalError

from job_aggregator.db.repositories.vacancy import VacancySaveError, VacancyUpsertResult
from job_aggregator.integrations.hh.client import HHClient
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


async def test_collect_pages_zero_or_negative_limit_rejected() -> None:
    client = FakeHHClient(pages={})
    repo = FakeVacancyRepository([])
    service = VacancyCollectionService(client, repo)

    with pytest.raises(ValueError, match="pages_limit должен быть больше нуля"):
        await service.collect_pages(HHVacancySearchParams(text="python"), 0)

    with pytest.raises(ValueError, match="pages_limit должен быть больше нуля"):
        await service.collect_pages(HHVacancySearchParams(text="python"), -1)

    assert client.calls == []
    assert repo.calls == []


async def test_collect_pages_stops_at_limit() -> None:
    params = HHVacancySearchParams(text="python")
    items = [make_vacancy_data(external_id=str(i)) for i in range(3)]

    client = FakeHHClient(
        pages={
            0: HHVacancyPage(items=items, page=0, found=9, pages=3),
            1: HHVacancyPage(items=items, page=1, found=9, pages=3),
            2: HHVacancyPage(items=items, page=2, found=9, pages=3),
        }
    )
    repo = FakeVacancyRepository([VacancyUpsertResult.CREATED] * 6)

    service = VacancyCollectionService(client, repo)
    # Лимит 2 страницы, значит будут запрошены 0 и 1
    result = await service.collect_pages(params, pages_limit=2)

    assert result.created == 6
    assert len(client.calls) == 2
    assert client.calls[0].page == 0
    assert client.calls[1].page == 1


async def test_collect_pages_stops_at_last_page_metadata() -> None:
    params = HHVacancySearchParams(text="python")
    items = [make_vacancy_data()]

    client = FakeHHClient(
        pages={
            0: HHVacancyPage(items=items, page=0, found=2, pages=2),
            1: HHVacancyPage(items=items, page=1, found=2, pages=2),
            2: HHVacancyPage(
                items=items, page=2, found=2, pages=2
            ),  # Не должна быть запрошена
        }
    )
    repo = FakeVacancyRepository([VacancyUpsertResult.CREATED] * 2)

    service = VacancyCollectionService(client, repo)
    result = await service.collect_pages(params, pages_limit=5)

    assert result.created == 2
    assert len(client.calls) == 2
    assert client.calls[0].page == 0
    assert client.calls[1].page == 1


async def test_collect_pages_stops_on_empty_page() -> None:
    params = HHVacancySearchParams(text="python")
    client = FakeHHClient(
        pages={
            0: HHVacancyPage(items=[make_vacancy_data()], page=0, found=2, pages=2),
            1: HHVacancyPage(items=[], page=1, found=2, pages=2),
            2: HHVacancyPage(
                items=[make_vacancy_data()], page=2, found=2, pages=2
            ),  # Не должна
        }
    )
    repo = FakeVacancyRepository([VacancyUpsertResult.CREATED])

    service = VacancyCollectionService(client, repo)
    result = await service.collect_pages(params, pages_limit=5)

    assert result.created == 1
    assert len(client.calls) == 2


async def test_collect_pages_start_from_non_zero_page() -> None:
    params = HHVacancySearchParams(text="python", page=2)
    client = FakeHHClient(
        pages={
            2: HHVacancyPage(items=[make_vacancy_data()], page=2, found=3, pages=3),
        }
    )
    repo = FakeVacancyRepository([VacancyUpsertResult.CREATED])

    service = VacancyCollectionService(client, repo)
    result = await service.collect_pages(params, pages_limit=2)

    assert result.created == 1
    assert len(client.calls) == 1
    assert client.calls[0].page == 2


async def test_collect_pages_continues_after_save_error() -> None:
    params = HHVacancySearchParams(text="python")
    client = FakeHHClient(
        pages={
            0: HHVacancyPage(items=[make_vacancy_data()], page=0, found=2, pages=2),
            1: HHVacancyPage(items=[make_vacancy_data()], page=1, found=2, pages=2),
        }
    )
    # На первой странице ошибка сохранения, на второй - успех
    repo = FakeVacancyRepository([VacancySaveError("bad"), VacancyUpsertResult.CREATED])

    service = VacancyCollectionService(client, repo)
    result = await service.collect_pages(params, pages_limit=2)

    assert result.created == 1
    assert result.failed == 1
    assert len(client.calls) == 2


async def test_collect_pages_propagates_infrastructure_error() -> None:
    params = HHVacancySearchParams(text="python")
    error = HHTemporaryError("network fail")
    client = FakeHHClient(pages={}, error=error)
    repo = FakeVacancyRepository([])

    service = VacancyCollectionService(client, repo)

    with pytest.raises(HHTemporaryError):
        await service.collect_pages(params, pages_limit=3)


async def test_progress_reports_actual_end_after_unchanged_page() -> None:
    item = make_vacancy_data()
    client = FakeHHClient(
        pages={
            2: HHVacancyPage(items=[item], page=2, found=4, pages=4),
            3: HHVacancyPage(items=[item], page=3, found=4, pages=4),
        }
    )
    service = VacancyCollectionService(
        client,
        FakeVacancyRepository(
            [VacancyUpsertResult.UNCHANGED, VacancyUpsertResult.CREATED]
        ),
    )
    result = await service.collect_pages_with_progress(
        HHVacancySearchParams(text="python", page=2), 5
    )
    assert [call.page for call in client.calls] == [2, 3]
    assert (result.created, result.skipped, result.next_page, result.exhausted) == (
        1,
        1,
        4,
        True,
    )


async def test_progress_stops_at_limit_and_handles_empty_shortened_results() -> None:
    client = FakeHHClient(
        pages={
            0: HHVacancyPage(items=[make_vacancy_data()], page=0, found=5, pages=5),
            1: HHVacancyPage(items=[], page=1, found=0, pages=0),
        }
    )
    service = VacancyCollectionService(
        client, FakeVacancyRepository([VacancyUpsertResult.CREATED])
    )
    first = await service.collect_pages_with_progress(
        HHVacancySearchParams(text="python"), 1
    )
    assert (first.next_page, first.exhausted) == (1, False)
    last = await service.collect_pages_with_progress(
        HHVacancySearchParams(text="python", page=1), 5
    )
    assert (last.next_page, last.exhausted) == (2, True)
    assert [call.page for call in client.calls] == [0, 1]


async def test_rejected_hh_page_does_not_exhaust_available_results():
    api = AsyncMock()
    api.request.side_effect = [
        {
            "items": [{"id": "bad", "name": "Python", "employer": {}}],
            "page": 0,
            "found": 2,
            "pages": 2,
        },
        {
            "items": [
                {
                    "id": "good",
                    "name": "Python",
                    "employer": {"name": "Компания"},
                    "alternate_url": "https://hh.ru/vacancy/good",
                }
            ],
            "page": 1,
            "found": 2,
            "pages": 2,
        },
    ]
    repository = FakeVacancyRepository([VacancyUpsertResult.CREATED])
    service = VacancyCollectionService(HHClient(api), repository)
    first = await service.collect_pages_with_progress(
        HHVacancySearchParams(text="python"), 1
    )
    assert (first.next_page, first.exhausted, first.failed) == (1, False, 1)
    second = await service.collect_pages_with_progress(
        HHVacancySearchParams(text="python", page=first.next_page), 1
    )
    assert (second.created, second.next_page, second.exhausted) == (1, 2, True)
    assert repository.calls[0].external_id == "good"
