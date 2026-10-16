import asyncio
import logging
from collections.abc import Awaitable, Callable

from job_aggregator.integrations.hh.errors import HHTemporaryError

logger = logging.getLogger(__name__)


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

    if initial_delay_seconds <= 0:
        raise ValueError("initial_delay_seconds must be positive")

    delay = initial_delay_seconds
    for attempt in range(1, max_attempts + 1):
        try:
            return await operation()
        except HHTemporaryError as error:
            if attempt == max_attempts:
                raise
            logger.warning(
                "Retrying HH request: attempt %d of %d in %.1f s after %s",
                attempt + 1,
                max_attempts,
                delay,
                type(error).__name__,
            )
            await sleep(delay)
            delay *= 2
