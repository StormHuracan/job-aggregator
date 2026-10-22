import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from job_aggregator.integrations.hh.client import HHOAuthClient
from job_aggregator.integrations.hh.errors import (
    HHPermanentRequestError,
    HHRateLimitError,
    HHTemporaryError,
)
from job_aggregator.integrations.hh.otp import (
    HHOTPClient,
    OTPInvalidCode,
    _hh_url,
    _Reply,
)
from tests.factories import make_token_data


def response(data, status=200, headers=None):
    return _Reply(status, headers or {}, json.dumps(data).encode())


@pytest.fixture
async def otp(monkeypatch):
    """Изолирует только сеть и RSA-helper SDK; протокол адаптера остаётся реальным."""
    monkeypatch.setattr(
        "job_aggregator.integrations.hh.otp.Operation._login_trust_flags",
        lambda self, key: "encrypted-flags",
    )
    client = HHOTPClient()
    client._request = AsyncMock()
    try:
        yield client
    finally:
        await client.close()


def login_page():
    body = (
        '<template id="HH-Lux-InitialState">'
        + json.dumps(
            {"xsrfToken": "private-xsrf", "loginTrustFlagsSecret": "public-key"}
        )
        + "</template>"
    )
    return _Reply(200, {}, body.encode())


@pytest.mark.parametrize(
    "username,kind", [("79991234567", "phone"), ("user@example.test", "email")]
)
async def test_start_sends_otp_with_isolated_context(otp, username, kind):
    otp._request.side_effect = [login_page(), response({"success": True})]
    result = await otp.start(username)
    assert result.step == "code"
    sent = otp._request.call_args.kwargs
    assert sent["data"]["otpType"] == kind
    assert sent["data"]["username"] == username
    assert sent["headers"]["X-Xsrftoken"] == "private-xsrf"
    assert sent["data"]["loginTrustFlags"] == "encrypted-flags"
    assert "client_secret" not in sent["data"]


async def test_confirm_captures_mobile_redirect_and_exchanges_code(otp, monkeypatch):
    tokens = make_token_data()
    exchange = AsyncMock(return_value=tokens)
    monkeypatch.setattr(HHOAuthClient, "exchange_code", exchange)
    otp._request.side_effect = [
        login_page(),
        response({"success": True}),
        response(
            {
                "success": True,
                "verification": {"success": True},
                "backurl": "/oauth/authorize",
            }
        ),
        _Reply(
            302,
            {
                "Location": f"hhandroid://oauthresponse?code=private-code&state={otp._state}"
            },
            b"",
        ),
    ]
    await otp.start("79991234567")
    assert await otp.confirm("123456") == tokens
    exchange.assert_awaited_once_with("private-code", "")
    assert otp._request.call_args_list[2].kwargs["data"]["code"] == "123456"


async def test_wrong_code_can_be_retried(otp):
    otp._request.side_effect = [
        login_page(),
        response({"success": True}),
        response({"success": False, "error": {"key": "CODE_INVALID"}}),
    ]
    await otp.start("79991234567")
    with pytest.raises(OTPInvalidCode):
        await otp.confirm("1111")
    assert otp._ready is True


async def test_captcha_is_presented_and_manual_answer_retries_send(otp):
    otp._request.side_effect = [
        login_page(),
        response({"hhcaptcha": {"captchaState": "private-captcha"}}),
        response({"key": "image-key"}),
        _Reply(200, {"Content-Type": "image/png"}, b"png"),
        response({}),
        response({"success": True}),
    ]
    prompt = await otp.start("user@example.test")
    assert prompt.step == "captcha"
    assert prompt.captcha_image.startswith("data:image/png;base64,")
    assert (await otp.solve_captcha("answer")).step == "code"
    assert otp._request.call_args_list[-2].kwargs["data"]["captchaText"] == "answer"
    assert otp._request.call_args.kwargs["data"]["captchaState"] == "private-captcha"


@pytest.mark.parametrize(
    "url",
    [
        "http://hh.ru/login",
        "https://hh.ru.evil.test/",
        "https://127.0.0.1/",
        "https://hh.ru:8443/",
        "https://user:password@hh.ru/",
    ],
)
def test_non_hh_redirects_are_rejected(url):
    with pytest.raises(HHPermanentRequestError):
        _hh_url(url)


async def test_login_page_changes_are_safe(otp):
    otp._request.return_value = _Reply(200, {}, b"<html>private-raw-body</html>")
    with pytest.raises(HHPermanentRequestError) as error:
        await otp.start("user@example.test")
    assert "private" not in str(error.value)


@pytest.mark.parametrize(
    "status,error", [(429, HHRateLimitError), (503, HHTemporaryError)]
)
async def test_http_status_mapping(monkeypatch, status, error):
    http = MagicMock()
    reply = AsyncMock()
    reply.status = status
    reply.headers = {}
    reply.content.read.return_value = b"private-body"
    http.request.return_value.__aenter__ = AsyncMock(return_value=reply)
    http.close = AsyncMock()
    monkeypatch.setattr(
        "job_aggregator.integrations.hh.otp.aiohttp.ClientSession",
        lambda **kwargs: http,
    )
    client = HHOTPClient()
    try:
        with pytest.raises(error) as cause:
            await client._request("GET", "https://hh.ru/")
        assert "private" not in str(cause.value)
        assert http.request.call_args.kwargs["allow_redirects"] is False
    finally:
        await client.close()
