from unittest.mock import MagicMock

import requests
from hh_applicant_tool.api import errors as hh_errors

from job_aggregator.integrations.hh.errors import (
    HHAuthenticationError,
    HHIntegrationError,
    HHPermanentRequestError,
    HHRateLimitError,
    HHTemporaryError,
    classify_error,
)


def _api_error(cls: type[hh_errors.ApiError]) -> hh_errors.ApiError:
    return cls(MagicMock(status_code=400), {})


def test_hierarchy() -> None:
    assert issubclass(HHTemporaryError, HHIntegrationError)
    assert issubclass(HHRateLimitError, HHTemporaryError)
    assert issubclass(HHAuthenticationError, HHIntegrationError)
    assert issubclass(HHPermanentRequestError, HHIntegrationError)
    # Постоянные ошибки не считаются retryable
    assert not issubclass(HHAuthenticationError, HHTemporaryError)
    assert not issubclass(HHPermanentRequestError, HHTemporaryError)


def test_limit_exceeded_is_rate_limit() -> None:
    result = classify_error(_api_error(hh_errors.LimitExceeded))
    assert isinstance(result, HHRateLimitError)
    assert isinstance(result, HHTemporaryError)


def test_forbidden_is_authentication() -> None:
    result = classify_error(_api_error(hh_errors.Forbidden))
    assert isinstance(result, HHAuthenticationError)


def test_captcha_required_is_permanent() -> None:
    result = classify_error(_api_error(hh_errors.CaptchaRequired))
    assert isinstance(result, HHPermanentRequestError)


def test_internal_server_error_is_temporary() -> None:
    result = classify_error(_api_error(hh_errors.InternalServerError))
    assert isinstance(result, HHTemporaryError)


def test_bad_gateway_is_temporary() -> None:
    result = classify_error(_api_error(hh_errors.BadGateway))
    assert isinstance(result, HHTemporaryError)


def test_redirect_is_permanent() -> None:
    result = classify_error(_api_error(hh_errors.Redirect))
    assert isinstance(result, HHPermanentRequestError)


def test_bad_request_is_permanent() -> None:
    result = classify_error(_api_error(hh_errors.BadRequest))
    assert isinstance(result, HHPermanentRequestError)


def test_resource_not_found_is_permanent() -> None:
    result = classify_error(_api_error(hh_errors.ResourceNotFound))
    assert isinstance(result, HHPermanentRequestError)


def test_generic_api_error_is_permanent() -> None:
    result = classify_error(_api_error(hh_errors.ApiError))
    assert isinstance(result, HHPermanentRequestError)


def test_bad_response_is_permanent() -> None:
    result = classify_error(hh_errors.BadResponse("json decode failed"))
    assert isinstance(result, HHPermanentRequestError)


def test_timeout_is_temporary() -> None:
    result = classify_error(requests.Timeout("timed out"))
    assert isinstance(result, HHTemporaryError)


def test_connection_error_is_temporary() -> None:
    result = classify_error(requests.ConnectionError("connection refused"))
    assert isinstance(result, HHTemporaryError)


def test_unknown_error_is_permanent() -> None:
    result = classify_error(RuntimeError("something unexpected"))
    assert isinstance(result, HHPermanentRequestError)


def test_message_does_not_leak_sensitive_data() -> None:
    sensitive = (
        "access_token=SECRET-TOKEN "
        "authorization_code=SECRET-CODE "
        "client_secret=SECRET-CLIENT"
    )
    result = classify_error(hh_errors.BadResponse(sensitive))

    message = str(result)
    assert "SECRET-TOKEN" not in message
    assert "SECRET-CODE" not in message
    assert "SECRET-CLIENT" not in message
    assert "access_token" not in message
    assert "authorization_code" not in message
    assert "client_secret" not in message
