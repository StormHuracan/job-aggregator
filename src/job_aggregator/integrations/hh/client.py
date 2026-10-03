from typing import Any

import anyio

from job_aggregator.integrations.hh.errors import HHApplicantToolUnavailableError


def _load_api_client_class() -> type:
    try:
        from hh_applicant_tool.api.client import ApiClient
    except ImportError as exc:
        raise HHApplicantToolUnavailableError(
            "Библиотека hh-applicant-tool недоступна. "
            "Установите совместимую версию или замените реализацию HHClient."
        ) from exc

    return ApiClient


class HHClient:
    """Клиент HH.ru, скрывающий детали сторонней библиотеки.

    Остальной проект должен работать с HH.ru только через этот класс или
    через контракты слоя `job_aggregator.integrations.hh`.
    """

    def __init__(
        self,
        access_token: str | None = None,
        refresh_token: str | None = None,
        access_expires_at: int = 0,
    ) -> None:
        api_client_class = _load_api_client_class()
        self._api_client = api_client_class(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_at=access_expires_at,
        )

    async def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Выполнить GET-запрос к HH API через изолированную обёртку."""

        def request() -> dict[str, Any]:
            result = self._api_client.get(endpoint, params or {})
            return dict(result)

        return await anyio.to_thread.run_sync(request)

    async def search_vacancies(
        self,
        text: str,
        page: int = 0,
        per_page: int = 20,
        area: str | None = None,
    ) -> dict[str, Any]:
        """Найти вакансии в HH.ru по тексту и базовым параметрам выдачи."""

        params: dict[str, Any] = {
            "text": text,
            "page": page,
            "per_page": per_page,
        }

        if area:
            params["area"] = area

        return await self.get("/vacancies", params)

    def get_token_data(self) -> dict[str, Any]:
        """Вернуть актуальные данные токена после возможного refresh внутри клиента."""

        return dict(self._api_client.get_access_token())
