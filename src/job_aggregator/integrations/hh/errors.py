from __future__ import annotations

from hh_applicant_tool.api import errors as hh_errors
from requests import RequestException


class HHIntegrationError(Exception):
    """Базовая ошибка интеграции с HH.ru.

    Публичные сообщения не содержат токены, OAuth-secret, authorization code,
    query-параметры, тело ответа или другие секреты.
    """


class HHTemporaryError(HHIntegrationError):
    """Временный сбой (сеть, 5xx). Повторные попытки допустимы."""


class HHRateLimitError(HHTemporaryError):
    """Превышен лимит запросов к HH.ru. Повторные попытки допустимы."""


class HHAuthenticationError(HHIntegrationError):
    """Авторизация недействительна или отклонена.

    Повтор без получения новых токенов смысла не имеет.
    """


class HHPermanentRequestError(HHIntegrationError):
    """Постоянная ошибка: некорректный запрос или невалидный ответ."""


def classify_error(ex: BaseException) -> HHIntegrationError:
    """Преобразовать низкоуровневую ошибку в тип интеграционного слоя.

    Исходное исключение можно сохранить как причину через `raise ... from ex`;
    публичное сообщение возвращаемой ошибки — только безопасный generic-текст.
    """
    if isinstance(ex, hh_errors.LimitExceeded):
        return HHRateLimitError("HH rate limit exceeded")
    if isinstance(ex, hh_errors.Forbidden):
        return HHAuthenticationError("HH authentication failed")
    if isinstance(ex, hh_errors.CaptchaRequired):
        return HHPermanentRequestError("HH captcha required")
    if isinstance(ex, hh_errors.InternalServerError):
        return HHTemporaryError("HH service temporarily unavailable")
    if isinstance(ex, hh_errors.Redirect):
        return HHPermanentRequestError("HH unexpected redirect")
    if isinstance(ex, hh_errors.ApiError):
        return HHPermanentRequestError("HH request rejected")
    if isinstance(ex, RequestException):
        return HHTemporaryError("HH network error")
    if isinstance(ex, hh_errors.BadResponse):
        return HHPermanentRequestError("HH invalid response")
    return HHPermanentRequestError("HH integration failed")
