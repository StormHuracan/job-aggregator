from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from hh_applicant_tool import api as hh_api
from pydantic import ValidationError
from requests import PreparedRequest, RequestException, Response, Session

from job_aggregator.integrations.hh.dto import (
    HHVacancyPage,
    HHVacancySearchParams,
)
from job_aggregator.integrations.hh.errors import (
    HHPermanentRequestError,
    classify_error,
)
from job_aggregator.integrations.hh.retry import retry_hh_request
from job_aggregator.schemas.hh_token import HHAccountTokenData
from job_aggregator.schemas.vacancy import VacancyData

_ALLOWED_METHODS = Literal["GET", "POST", "PUT", "DELETE"]


class HHRequestClient(Protocol):
    async def request(
        self,
        method: _ALLOWED_METHODS,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> Any: ...


class _TimeoutSession(Session):
    def send(self, request: PreparedRequest, **kwargs: Any) -> Response:
        # SDK вызывает Session.send без timeout, в том числе при OAuth refresh.
        kwargs.setdefault("timeout", (5, 30))
        return super().send(request, **kwargs)


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
        retry_sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._tokens = tokens
        self._allow_token_refresh = allow_token_refresh
        self._retry_sleep = retry_sleep
        self._http_session = _TimeoutSession()

        kwargs: dict[str, Any] = _dto_to_library_kwargs(tokens)
        kwargs["session"] = self._http_session
        if allow_token_refresh:
            kwargs["client_id"] = client_id
            kwargs["client_secret"] = client_secret
        else:
            kwargs.pop("refresh_token", None)

        self._client = hh_api.ApiClient(**kwargs)

    def close(self) -> None:
        """Освобождает HTTP-соединения после последней операции клиента."""
        self._http_session.close()

    def get_current_tokens(self) -> HHAccountTokenData:
        """Текущие токены после последнего запроса."""
        return self._tokens

    async def request(
        self,
        method: _ALLOWED_METHODS,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        async def call_library() -> Any:
            try:
                return await asyncio.to_thread(
                    self._client.request, method, endpoint, params
                )
            except (hh_api.BadResponse, RequestException) as ex:
                raise classify_error(ex) from ex

        try:
            return await retry_hh_request(call_library, sleep=self._retry_sleep)
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

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        client = hh_api.OAuthClient(
            client_id=self._client_id,
            client_secret=self._client_secret,
            redirect_uri=redirect_uri,
            state=state,
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
        except (hh_api.BadResponse, RequestException) as ex:
            raise classify_error(ex) from ex
        return _token_from_oauth_response(token)


def _parse_published_at(value: Any) -> datetime | None:
    """ISO 8601 → aware UTC. Невалидное/naive значение → None."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC)


def _to_vacancy_data(item: Any) -> VacancyData | None:
    """Нормализовать элемент ответа HH в VacancyData.

    Обязательные поля: id, name, alternate_url, employer.name.
    Если чего-то нет — элемент отбрасывается (None).
    """
    if not isinstance(item, dict):
        return None

    external_id = item.get("id")
    title = item.get("name")
    source_url = item.get("alternate_url")
    employer = item.get("employer")
    company_name = employer.get("name") if isinstance(employer, dict) else None

    if not (external_id and title and source_url and company_name):
        return None

    area = item.get("area")
    area_name = area.get("name") if isinstance(area, dict) else None

    salary = item.get("salary")
    if isinstance(salary, dict):
        salary_from = salary.get("from")
        salary_to = salary.get("to")
        salary_currency = salary.get("currency")
    else:
        salary_from = None
        salary_to = None
        salary_currency = None

    snippet = item.get("snippet")
    description = snippet.get("responsibility") if isinstance(snippet, dict) else None

    return VacancyData(
        source="hh",
        external_id=str(external_id),
        title=str(title),
        company_name=str(company_name),
        area_name=area_name,
        salary_from=salary_from,
        salary_to=salary_to,
        salary_currency=salary_currency,
        description=description,
        source_url=str(source_url),
        published_at=_parse_published_at(item.get("published_at")),
        raw_data=item,
    )


class HHClient:
    """Высокоуровневый клиент поиска вакансий HH.ru.

    Инкапсулирует формат внешнего ответа и возвращает нормализованные
    VacancyData внутри HHVacancyPage. Токены, сессии и ORM-модели
    не сохраняются здесь — это ответственность сервисного слоя.
    """

    def __init__(self, api_client: HHRequestClient) -> None:
        self._api = api_client

    async def search_vacancies(self, params: HHVacancySearchParams) -> HHVacancyPage:
        query: dict[str, Any] = {
            "text": params.text,
            "page": params.page,
            "per_page": params.per_page,
        }
        if params.area:
            query["area"] = params.area

        response = await self._api.request("GET", "/vacancies", query)
        if not isinstance(response, dict):
            raise HHPermanentRequestError("Unexpected HH vacancies response")

        raw_items = response.get("items")
        if not isinstance(raw_items, list):
            raise HHPermanentRequestError("Unexpected HH vacancies response")

        items: list[VacancyData] = []
        for raw in raw_items:
            vacancy = _to_vacancy_data(raw)
            if vacancy is not None:
                items.append(vacancy)

        try:
            return HHVacancyPage(
                items=items,
                page=int(response.get("page", 0)),
                found=int(response.get("found", 0)),
                pages=int(response.get("pages", 0)),
            )
        except (TypeError, ValueError, ValidationError) as ex:
            raise HHPermanentRequestError("Unexpected HH vacancies response") from ex
