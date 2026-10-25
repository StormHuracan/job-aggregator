import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from job_aggregator.jobs.collection import (
    register_collection_job,
    run_scheduled_collection,
)
from job_aggregator.services.saved_searches import UserSearchCollectionResult


@patch("job_aggregator.jobs.collection.SavedSearchCollectionService")
@patch("job_aggregator.jobs.collection.UserSavedSearchRepository")
async def test_job_accepts_real_result_contract(
    mock_repo_cls, mock_service_cls, caplog
):
    mock_repo_cls.return_value.list_enabled_user_ids = AsyncMock(return_value=[1])
    mock_service_cls.return_value.collect_for_user = AsyncMock(
        return_value=UserSearchCollectionResult(1, [], 0, 0, 0, 0, 0)
    )
    with caplog.at_level(logging.INFO):
        await run_scheduled_collection(MagicMock(), MagicMock())
    assert "collection failed" not in caplog.text
    assert "succeeded=1, failed=0" in caplog.text


async def test_registered_job_tracks_active_collection_until_cancelled(monkeypatch):
    started = asyncio.Event()
    finished = asyncio.Event()

    async def blocked_collection(*args):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            finished.set()

    monkeypatch.setattr(
        "job_aggregator.jobs.collection.run_scheduled_collection", blocked_collection
    )
    scheduler = AsyncIOScheduler()
    settings = MagicMock(scheduler_interval_minutes=60)
    active = register_collection_job(scheduler, MagicMock(), settings)
    job = scheduler.get_job("collect_saved_searches")
    task = asyncio.create_task(job.func(*job.args))
    try:
        await asyncio.wait_for(started.wait(), 1)
        assert active
        for child in list(active):
            child.cancel()
        await asyncio.gather(*list(active), return_exceptions=True)
        assert finished.is_set()
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@patch("job_aggregator.jobs.collection.SavedSearchCollectionService")
@patch("job_aggregator.jobs.collection.UserSavedSearchRepository")
async def test_run_scheduled_collection_success(mock_repo_cls, mock_service_cls):
    mock_repo = mock_repo_cls.return_value
    mock_repo.list_enabled_user_ids = AsyncMock(return_value=[1, 2])

    mock_service = mock_service_cls.return_value
    mock_service.collect_for_user = AsyncMock(
        side_effect=[
            MagicMock(status="success", searches=[], new_matches=0),
            MagicMock(status="success", searches=[], new_matches=0),
        ]
    )

    session_factory = MagicMock()
    settings = MagicMock()

    await run_scheduled_collection(session_factory, settings)

    mock_repo.list_enabled_user_ids.assert_awaited_once()
    assert mock_service.collect_for_user.await_count == 2
    mock_service.collect_for_user.assert_any_await(1)
    mock_service.collect_for_user.assert_any_await(2)


@patch("job_aggregator.jobs.collection.SavedSearchCollectionService")
@patch("job_aggregator.jobs.collection.UserSavedSearchRepository")
async def test_run_scheduled_collection_continues_on_error(
    mock_repo_cls, mock_service_cls
):
    mock_repo = mock_repo_cls.return_value
    mock_repo.list_enabled_user_ids = AsyncMock(return_value=[1, 2])

    mock_service = mock_service_cls.return_value
    # Первый пользователь падает, второй успешно
    mock_service.collect_for_user = AsyncMock(
        side_effect=[
            Exception("Test error"),
            MagicMock(status="success", searches=[], new_matches=0),
        ]
    )

    await run_scheduled_collection(MagicMock(), MagicMock())

    assert mock_service.collect_for_user.await_count == 2


@patch("job_aggregator.jobs.collection.run_scheduled_collection")
def test_register_collection_job(mock_run_job):
    scheduler = AsyncIOScheduler()
    session_factory = MagicMock()
    settings = MagicMock()
    settings.scheduler_interval_minutes = 30

    register_collection_job(scheduler, session_factory, settings)

    job = scheduler.get_job("collect_saved_searches")
    assert job is not None
    assert isinstance(job.trigger, IntervalTrigger)
    assert job.trigger.interval.total_seconds() == 30 * 60
    assert job.max_instances == 1
    assert job.coalesce is True
