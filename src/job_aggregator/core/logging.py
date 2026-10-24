import logging
import re

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
HANDLER_NAME = "job_aggregator"


class _SuccessfulHealthLogFilter(logging.Filter):
    """Убирает шум liveness-проб, сохраняя ошибки и диагностику БД."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        return not (
            isinstance(args, tuple)
            and len(args) == 5
            and args[1:3] == ("GET", "/health")
            and args[4] == 200
        )


class _OAuthCallbackLogFilter(logging.Filter):
    """Не даёт access-логам записать одноразовый code и state из URL."""

    def filter(self, record: logging.LogRecord) -> bool:
        def redact(value: object) -> object:
            text = str(value)
            if "/auth/hh/callback" not in text:
                return value
            return re.sub(r'(/auth/hh/callback/?)\?[^\s"\']*', r"\1", text)

        record.msg = redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(redact(value) for value in record.args)
        return True


def configure_logging(log_level: str) -> None:
    """Настраивает логирование приложения.

    Повторный вызов не создает дублирующих обработчиков.
    DEBUG-сообщения hh_applicant_tool не выводятся, так как в них могут быть токены.
    """
    root = logging.getLogger()

    for handler in list(root.handlers):
        if handler.get_name() == HANDLER_NAME:
            root.removeHandler(handler)

    handler = logging.StreamHandler()
    handler.set_name(HANDLER_NAME)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(handler)

    root.setLevel(log_level.upper())

    hh_level = max(logging.INFO, root.level)
    logging.getLogger("hh_applicant_tool").setLevel(hh_level)

    for name in ("uvicorn.access", "httpx"):
        request_logger = logging.getLogger(name)
        if not any(
            isinstance(item, _OAuthCallbackLogFilter) for item in request_logger.filters
        ):
            request_logger.addFilter(_OAuthCallbackLogFilter())

    access_logger = logging.getLogger("uvicorn.access")
    if not any(
        isinstance(item, _SuccessfulHealthLogFilter) for item in access_logger.filters
    ):
        access_logger.addFilter(_SuccessfulHealthLogFilter())
