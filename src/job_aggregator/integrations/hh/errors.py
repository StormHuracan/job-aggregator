class HHIntegrationError(RuntimeError):
    """Базовая ошибка слоя интеграции с HH.ru."""


class HHApplicantToolUnavailableError(HHIntegrationError):
    """Сторонняя библиотека hh-applicant-tool недоступна в окружении."""
