from unittest.mock import AsyncMock, MagicMock, patch

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from job_aggregator.jobs.collection import (
    register_collection_job,
    run_scheduled_collection,
)


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
