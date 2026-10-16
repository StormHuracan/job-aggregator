import logging

import pytest

from job_aggregator.integrations.hh.errors import (
    HHAuthenticationError,
    HHRateLimitError,
    HHTemporaryError,
)
from job_aggregator.integrations.hh.retry import retry_hh_request


class RecordingSleep:
    """Записывает запрошенные паузы вместо реального ожидания."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


class FlakyOperation:
    """Бросает ошибки из списка по очереди, затем возвращает результат."""

    def __init__(self, errors: list[Exception], result: str = "ok") -> None:
        self.errors = errors
        self.result = result
        self.calls = 0

    async def __call__(self) -> str:
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return self.result


async def test_retries_temporary_error_until_success() -> None:
    operation = FlakyOperation([HHTemporaryError("x"), HHTemporaryError("x")])
    sleep = RecordingSleep()

    result = await retry_hh_request(operation, sleep=sleep)

    assert result == "ok"
    assert operation.calls == 3
    assert sleep.delays == [0.5, 1.0]


async def test_authentication_error_is_not_retried() -> None:
    operation = FlakyOperation([HHAuthenticationError("x")])
    sleep = RecordingSleep()

    with pytest.raises(HHAuthenticationError):
        await retry_hh_request(operation, sleep=sleep)

    assert operation.calls == 1
    assert sleep.delays == []


async def test_rate_limit_is_retried_until_attempts_exhausted() -> None:
    operation = FlakyOperation([HHRateLimitError("x")] * 5)
    sleep = RecordingSleep()

    with pytest.raises(HHRateLimitError):
        await retry_hh_request(operation, sleep=sleep)

    assert operation.calls == 3
    assert sleep.delays == [0.5, 1.0]


async def test_exhausted_attempts_raise_original_error() -> None:
    last_error = HHTemporaryError("last")
    operation = FlakyOperation(
        [HHTemporaryError("first"), HHTemporaryError("second"), last_error]
    )

    with pytest.raises(HHTemporaryError) as exc_info:
        await retry_hh_request(operation, sleep=RecordingSleep())

    assert exc_info.value is last_error


async def test_rejects_non_positive_max_attempts() -> None:
    operation = FlakyOperation([])

    with pytest.raises(ValueError):
        await retry_hh_request(operation, max_attempts=0)

    assert operation.calls == 0


async def test_rejects_non_positive_initial_delay() -> None:
    operation = FlakyOperation([])

    with pytest.raises(ValueError):
        await retry_hh_request(operation, initial_delay_seconds=0)

    assert operation.calls == 0


async def test_retry_attempt_is_logged_without_error_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    operation = FlakyOperation([HHTemporaryError("secret-token-123")])

    with caplog.at_level(logging.WARNING):
        await retry_hh_request(operation, sleep=RecordingSleep())

    assert "attempt 2 of 3" in caplog.text
    assert "HHTemporaryError" in caplog.text
    assert "secret-token-123" not in caplog.text
