import asyncio
import logging
from contextlib import closing
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_aggregator.db.models.user import User
from job_aggregator.db.repositories.hh_account import HHAccountRepository
from job_aggregator.integrations.hh.client import HHAPIClient
from job_aggregator.integrations.hh.errors import (
    HHAuthenticationError,
    HHIntegrationError,
)
from job_aggregator.schemas.hh_token import HHAccountTokenData

logger = logging.getLogger(__name__)


class HHAccountNotConnectedError(HHAuthenticationError):
    """У пользователя нет персонального подключения HH.ru."""


class AuthorizedHHAPIClient:
    """Запросы одного владельца с отдельной транзакцией его HH-токенов."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        user_id: int,
        *,
        allow_token_refresh: bool,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._user_id = user_id
        self._allow_token_refresh = allow_token_refresh
        self._client_id = client_id
        self._client_secret = client_secret

    async def request(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Отмена достигает caller после завершения SDK и транзакции токенов.

        SDK выполняется в потоке и не останавливается отменой coroutine.
        До его завершения нельзя отпускать блокировку владельца.
        """
        sdk_started = asyncio.Event()
        operation = asyncio.create_task(
            self._request(method, endpoint, params, sdk_started)
        )
        try:
            return await asyncio.shield(operation)
        except asyncio.CancelledError:
            if not sdk_started.is_set():
                # Отменённый waiter не должен начинать HTTP, когда получит lock.
                operation.cancel()
            while not operation.done():
                try:
                    await asyncio.shield(operation)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            if not operation.cancelled():
                error = operation.exception()
                if error is not None:
                    logger.error(
                        "Cancelled HH request failed: %s", type(error).__name__
                    )
            raise

    async def _request(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        endpoint: str,
        params: dict[str, Any] | None,
        sdk_started: asyncio.Event,
    ) -> Any:
        request_error: HHIntegrationError | None = None
        result: Any = None
        async with self._session_factory.begin() as session:
            owner = await session.scalar(
                select(User.id)
                .where(User.id == self._user_id)
                # NO KEY UPDATE сериализует запросы владельца, но совместим
                # с FK-проверкой новой позиции сбора в другой транзакции.
                .with_for_update(key_share=True)
            )
            repository = HHAccountRepository(session)
            account = await repository.get_by_user_id(self._user_id)
            if owner is None or account is None:
                raise HHAccountNotConnectedError("HH account is not connected")
            tokens = HHAccountTokenData(
                access_token=account.access_token,
                refresh_token=account.refresh_token,
                access_expires_at=account.access_expires_at,
            )
            with closing(
                HHAPIClient(
                    tokens,
                    allow_token_refresh=self._allow_token_refresh,
                    client_id=self._client_id,
                    client_secret=self._client_secret,
                )
            ) as client:
                sdk_started.set()
                try:
                    result = await client.request(method, endpoint, params)
                except HHIntegrationError as error:
                    # Ошибка повторного HTTP-запроса не должна откатить refresh.
                    request_error = error
                current_tokens = client.get_current_tokens()
                if current_tokens != tokens:
                    await repository.save(self._user_id, current_tokens)

        if request_error is not None:
            raise request_error
        return result
