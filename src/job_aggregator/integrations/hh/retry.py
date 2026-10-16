import asyncio
from collections.abc import Awaitable, Callable

from job_aggregator.integrations.hh.errors import HHTemporaryError


async def retry_hh_request[T](
    operation: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    initial_delay_seconds: float = 0.5,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    """Выполняет запрос к HH.ru с повторами при временных ошибках.

    HHTemporaryError и HHRateLimitError повторяются до max_attempts раз,
    пауза перед каждой следующей попыткой удваивается. Остальные ошибки
    пробрасываются сразу, после последней попытки — исходная ошибка.
    """

    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")

    delay = initial_delay_seconds
    for attempt in range(1, max_attempts + 1):
        try:
            return await operation()
        except HHTemporaryError:
            if attempt == max_attempts:
                raise
            await sleep(delay)
            delay *= 2
