import asyncio
from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from job_aggregator.core.config import Settings, get_settings
from job_aggregator.jobs.scheduler import create_scheduler
from job_aggregator.main import create_app


async def fake_job() -> None:
    """Тестовая job без логики."""


def test_create_scheduler_returns_not_running_scheduler() -> None:
    scheduler = create_scheduler(Settings())

    assert scheduler.running is False


async def test_jobs_do_not_overlap_and_skip_missed_runs() -> None:
    scheduler = create_scheduler(Settings())
    scheduler.start(paused=True)

    try:
        job = scheduler.add_job(fake_job, "interval", minutes=1)

        assert job.max_instances == 1
        assert job.coalesce is True
    finally:
        scheduler.shutdown()


def test_job_interval_is_taken_from_settings() -> None:
    settings = Settings(scheduler_interval_minutes=15)
    scheduler = create_scheduler(settings)

    job = scheduler.add_job(
        fake_job, "interval", minutes=settings.scheduler_interval_minutes
    )

    assert job.trigger.interval == timedelta(minutes=15)


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Iterator[None]:
    """Сбрасывает кэш настроек до и после каждого теста."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_scheduler_runs_during_app_lifespan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCHEDULER_ENABLED", "TRUE")
    app = create_app()

    with TestClient(app):
        scheduler = app.state.scheduler
        assert scheduler.running is True

    assert scheduler.running is False


def test_scheduler_is_not_created_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCHEDULER_ENABLED", "FALSE")
    app = create_app()

    with TestClient(app):
        assert app.state.scheduler is None


async def test_async_job_runs_in_app_event_loop() -> None:
    executed = asyncio.Event()
    test_loop = asyncio.get_running_loop()
    job_loops: list[asyncio.AbstractEventLoop] = []

    async def set_flag_job() -> None:
        job_loops.append(asyncio.get_running_loop())
        executed.set()

    scheduler = create_scheduler(Settings())
    scheduler.start()

    try:
        scheduler.add_job(set_flag_job)
        await asyncio.wait_for(executed.wait(), timeout=1)
    finally:
        scheduler.shutdown()

    assert job_loops == [test_loop]
