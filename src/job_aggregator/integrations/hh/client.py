from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, Literal

from hh_applicant_tool import api as hh_api

from job_aggregator.integrations.hh.errors import HHIntegrationError
from job_aggregator.schemas.hh_token import HHAccountTokenData

_ALLOWED_METHODS = Literal["GET", "POST", "PUT", "DELETE"]


def _dto_to_library_kwargs(tokens: HHAccountTokenData) -> dict[str, Any]:
    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "access_expires_at": int(tokens.access_expires_at.timestamp()),
    }


def _token_from_oauth_response(token: dict[str, Any]) -> HHAccountTokenData:
    return HHAccountTokenData(
        access_token=token["access_token"],
        refresh_token=token["refresh_token"],
        access_expires_at=datetime.fromtimestamp(
            int(token["access_expires_at"]), tz=UTC
        ),
    )


class HHAPIClient:
    """Изолированный async-клиент для запросов к API HH.ru.

    Синхронная библиотека hh-applicant-tool вызывается через asyncio.to_thread,
    чтобы не блокировать event loop. Конвертация HHAccountTokenData
    (aware UTC datetime) ↔ внутренний формат библиотеки (Unix timestamp)
    выполняется здесь и не выходит за границу адаптера.
    """

    def __init__(
        self,
        tokens: HHAccountTokenData,
        *,
        allow_token_refresh: bool,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        self._tokens = tokens
        self._allow_token_refresh = allow_token_refresh

        kwargs: dict[str, Any] = _dto_to_library_kwargs(tokens)
        if allow_token_refresh:
            kwargs["client_id"] = client_id
            kwargs["client_secret"] = client_secret
        else:
            kwargs.pop("refresh_token", None)

        self._client = hh_api.ApiClient(**kwargs)

    def get_current_tokens(self) -> HHAccountTokenData:
        """Текущие токены после последнего запроса."""
        return self._tokens

    async def request(
        self,
        method: _ALLOWED_METHODS,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        try:
            return await asyncio.to_thread(
                self._client.request, method, endpoint, params
            )
        except hh_api.BadResponse as ex:
            raise HHIntegrationError("HH API request failed") from ex
        finally:
            self._sync_tokens_from_library()

    def _sync_tokens_from_library(self) -> None:
        try:
            current = self._client.get_access_token()
        except Exception:
            return
        if not isinstance(current, dict):
            return
        access = current.get("access_token") or self._tokens.access_token
        refresh = current.get("refresh_token") or self._tokens.refresh_token
        expires_at = current.get("access_expires_at")
        if not isinstance(expires_at, int) or expires_at <= 0:
            expires_at = int(self._tokens.access_expires_at.timestamp())
        self._tokens = HHAccountTokenData(
            access_token=access,
            refresh_token=refresh,
            access_expires_at=datetime.fromtimestamp(expires_at, tz=UTC),
        )


class HHOAuthClient:
    """Изолированный async-клиент для OAuth-операций HH.ru."""

    def __init__(
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret

    def get_authorization_url(self, redirect_uri: str) -> str:
        client = hh_api.OAuthClient(
            client_id=self._client_id,
            client_secret=self._client_secret,
            redirect_uri=redirect_uri,
        )
        return client.authorize_url

    async def exchange_code(self, code: str, redirect_uri: str) -> HHAccountTokenData:
        client = hh_api.OAuthClient(
            client_id=self._client_id,
            client_secret=self._client_secret,
            redirect_uri=redirect_uri,
        )
        try:
            token = await asyncio.to_thread(client.authenticate, code)
        except hh_api.BadResponse as ex:
            raise HHIntegrationError("HH OAuth code exchange failed") from ex
        return _token_from_oauth_response(token)
