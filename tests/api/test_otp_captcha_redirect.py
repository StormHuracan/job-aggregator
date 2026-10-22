from unittest.mock import AsyncMock

from job_aggregator.integrations.hh.otp import HHOTPClient, OTPPrompt, _Reply
from job_aggregator.services.otp_login import OTPLoginService


async def test_captcha_acceptance_redirect_resumes_otp_instead_of_502(
    app, async_client
):
    """SDK следует 302 после принятой капчи; API должен продолжить тот же вход."""
    from job_aggregator.api.otp import _service

    hh = HHOTPClient()
    hh._captcha_state = "private-state"
    hh._captcha_key = "private-key"
    hh._request = AsyncMock(
        side_effect=[
            _Reply(302, {"Location": "/"}, b""),
            _Reply(200, {}, b"<html></html>"),
        ]
    )
    hh._send_code = AsyncMock(return_value=OTPPrompt("code"))
    hh.start = AsyncMock(
        return_value=OTPPrompt("captcha", "data:image/png;base64,cG5n")
    )
    service = OTPLoginService(factory=lambda: hh)
    app.dependency_overrides[_service] = lambda: service
    try:
        token, _ = await service.start("user@example.test", "test")
        async_client.cookies.set("hh_otp_login", token)
        response = await async_client.post(
            "/auth/hh/otp/captcha", json={"text": "private-answer"}
        )
        assert response.status_code == 200
        assert response.json()["step"] == "code"
        hh._send_code.assert_awaited_once()
    finally:
        await service.close()
