from typing import Any

from job_aggregator.integrations.hh.errors import HHApplicantToolUnavailableError


def _load_oauth_client_class() -> type:
    try:
        from hh_applicant_tool.api.client import OAuthClient
    except ImportError as exc:
        raise HHApplicantToolUnavailableError(
            "Библиотека hh-applicant-tool недоступна. "
            "Установите совместимую версию или замените реализацию HHOAuthClient."
        ) from exc

    return OAuthClient


class HHOAuthClient:
    """Клиент авторизации HH.ru через изолированную обёртку."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
    ) -> None:
        oauth_client_class = _load_oauth_client_class()
        self._oauth_client = oauth_client_class(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri or "",
        )

    def get_authorize_url(self) -> str:
        """Получить URL для начала OAuth-авторизации пользователя HH.ru."""

        return str(self._oauth_client.authorize_url)

    def exchange_code(self, code: str) -> dict[str, Any]:
        """Обменять OAuth code на токены HH.ru."""

        return dict(self._oauth_client.authenticate(code))

    def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        """Обновить access token через refresh token HH.ru."""

        return dict(self._oauth_client.refresh_access_token(refresh_token))
