import logging

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
HANDLER_NAME = "job_aggregator"


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
