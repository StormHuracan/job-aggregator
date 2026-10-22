import logging
from collections.abc import Iterator

import pytest

from job_aggregator.core.logging import HANDLER_NAME, configure_logging


def test_configure_logging_sets_root_level() -> None:
    configure_logging("INFO")

    assert logging.getLogger().level == logging.INFO


def test_hh_applicant_tool_debug_is_disabled() -> None:
    configure_logging("DEBUG")

    hh_logger = logging.getLogger("hh_applicant_tool")
    assert hh_logger.isEnabledFor(logging.DEBUG) is False


def test_repeated_configure_logging_does_not_duplicate_handlers() -> None:
    configure_logging("INFO")
    configure_logging("INFO")

    root = logging.getLogger()
    our_handlers = [h for h in root.handlers if h.get_name() == HANDLER_NAME]
    assert len(our_handlers) == 1


def test_log_record_has_expected_format(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")

    logging.getLogger("job_aggregator.test").info("Проверка формата")

    output = capsys.readouterr().err.strip()
    assert output.endswith(" INFO [job_aggregator.test] Проверка формата")


@pytest.fixture(autouse=True)
def restore_logging() -> Iterator[None]:
    """Возвращает настройки logging в исходное состояние после теста."""
    root = logging.getLogger()
    hh_logger = logging.getLogger("hh_applicant_tool")
    root_level = root.level
    hh_level = hh_logger.level

    yield

    for handler in list(root.handlers):
        if handler.get_name() == HANDLER_NAME:
            root.removeHandler(handler)
    root.setLevel(root_level)
    hh_logger.setLevel(hh_level)


@pytest.mark.parametrize("logger_name", ["uvicorn.access", "httpx"])
def test_callback_query_secrets_are_redacted(
    logger_name: str, caplog: pytest.LogCaptureFixture
) -> None:
    configure_logging("INFO")
    logger = logging.getLogger(logger_name)
    if logger_name == "uvicorn.access":
        logger.info(
            '%s - "%s %s HTTP/%s" %s',
            "127.0.0.1",
            "GET",
            "/api/auth/hh/callback?code=private-code&state=private-state",
            "1.1",
            303,
        )
    else:
        from httpx import URL

        logger.info(
            "HTTP Request: GET %s",
            URL(
                "https://example.test/api/auth/hh/callback?code=private-code&state=private-state"
            ),
        )
    assert "/api/auth/hh/callback" in caplog.text
    assert "private-code" not in caplog.text
    assert "private-state" not in caplog.text
