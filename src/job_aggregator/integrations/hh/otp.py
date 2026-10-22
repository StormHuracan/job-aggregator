"""Async-адаптация OTP-протокола operations/authorize.py из hh-applicant-tool 2.0.1.

CLI библиотеки требует input() и GUI для капчи, поэтому сетевые шаги выполняются
через aiohttp. OAuth URL и обмен кода остаются в существующем SDK-адаптере.
"""

import asyncio
import base64
import html
import json
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from secrets import token_urlsafe
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlsplit

import aiohttp
from hh_applicant_tool.constants import BROWSER_USER_AGENT
from hh_applicant_tool.operations.authorize import Operation

from job_aggregator.integrations.hh.client import HHOAuthClient
from job_aggregator.integrations.hh.errors import (
    HHIntegrationError,
    HHPermanentRequestError,
    HHRateLimitError,
    HHTemporaryError,
)
from job_aggregator.schemas.hh_token import HHAccountTokenData

logger = logging.getLogger(__name__)


class OTPInvalidCode(HHIntegrationError):
    """HH отклонил код; его можно ввести повторно в той же сессии."""


@dataclass(frozen=True)
class OTPPrompt:
    step: str
    captcha_image: str | None = None


@dataclass(frozen=True)
class _Reply:
    status: int
    headers: Mapping[str, str]
    body: bytes

    def json(self) -> dict:
        try:
            value = json.loads(self.body)
        except ValueError, UnicodeDecodeError:
            raise HHPermanentRequestError("HH invalid response") from None
        if not isinstance(value, dict):
            raise HHPermanentRequestError("HH invalid response")
        return value


def _hh_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise HHPermanentRequestError("HH invalid redirect") from None
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not (parsed.hostname == "hh.ru" or parsed.hostname.endswith(".hh.ru"))
        or port not in (None, 443)
        or parsed.username
        or parsed.password
    ):
        raise HHPermanentRequestError("HH invalid redirect")
    return url


def _nested(data: dict, key: str) -> dict:
    value = data.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise HHPermanentRequestError("HH invalid response")
    return value


class HHOTPClient:
    """Один вход, один изолированный cookie jar; close обязателен после окончания."""

    def __init__(self) -> None:
        self._http = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=20, connect=5),
            headers={
                "User-Agent": BROWSER_USER_AGENT,
                "Accept-Language": "ru-RU,ru;q=0.9",
            },
        )
        self._state = token_urlsafe(32)
        self._authorize_url = HHOAuthClient().get_authorization_url("", self._state)
        self._origin = "https://hh.ru"
        self._username = ""
        self._xsrf = ""
        self._trust = ""
        self._captcha_state = ""
        self._captcha_key = ""
        self._captcha_step = "send"
        self._ready = False

    async def close(self) -> None:
        await self._http.close()

    async def _request(self, method: str, url: str, **kwargs) -> _Reply:
        try:
            async with self._http.request(
                method, _hh_url(url), allow_redirects=False, **kwargs
            ) as response:
                if response.status == 429:
                    raise HHRateLimitError("HH rate limit")
                if response.status >= 500:
                    raise HHTemporaryError("HH unavailable")
                try:
                    body = await response.content.readexactly(1024 * 1024 + 1)
                except asyncio.IncompleteReadError as incomplete:
                    body = incomplete.partial
                if len(body) > 1024 * 1024:
                    raise HHPermanentRequestError("HH response too large")
                return _Reply(response.status, response.headers, body)
        except aiohttp.ClientError, TimeoutError:
            raise HHTemporaryError("HH network error") from None

    async def start(self, username: str) -> OTPPrompt:
        self._username = username
        url = self._authorize_url
        for _ in range(6):
            response = await self._request("GET", url)
            if response.status in (301, 302, 303, 307, 308):
                url = _hh_url(urljoin(url, response.headers.get("Location", "")))
                continue
            break
        else:
            raise HHPermanentRequestError("HH redirect limit")
        if response.status != 200:
            raise HHPermanentRequestError("HH login page unavailable")
        self._origin = "https://" + urlsplit(url).netloc
        try:
            match = re.search(
                r'<template\b[^>]*\bid=[\'"]HH-Lux-InitialState[\'"][^>]*>(.*?)</template>',
                response.body.decode(),
                re.DOTALL,
            )
            data = json.loads(html.unescape(match[1]))
            self._xsrf = data["xsrfToken"]
            public_key = data["loginTrustFlagsSecret"]
            if (
                not isinstance(self._xsrf, str)
                or not self._xsrf
                or not isinstance(public_key, str)
            ):
                raise ValueError
            # SDK зафиксирован на 2.0.1; этот helper создаёт RSA trust flags без I/O.
            self._trust = Operation()._login_trust_flags(public_key)
        except ValueError, KeyError, TypeError, AttributeError:
            raise HHPermanentRequestError("HH login page changed") from None
        return await self._send_code()

    @property
    def _backurl(self) -> str:
        return self._authorize_url + "&skip_choose_account=true"

    @property
    def _failurl(self) -> str:
        return (
            "/account/login?backurl="
            + quote(self._backurl, safe="")
            + "&oauth=true&response_type=code"
        )

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "X-Xsrftoken": self._xsrf,
            "X-Requested-With": "XMLHttpRequest",
            "x-hhtmfrom": "",
            "x-hhtmsource": "account_login",
            "Referer": self._origin + "/account/login",
        }

    async def _send_code(self) -> OTPPrompt:
        payload = {
            "_xsrf": self._xsrf,
            "failUrl": self._failurl,
            "remember": "yes",
            "username": self._username,
            "password": "",
            "isBot": "false",
            "login": self._username,
            "otpType": "email" if "@" in self._username else "phone",
            "operationType": "applicant_otp_auth",
            "authScenario": "APPLICANT_AUTH",
            "loginTrustFlags": self._trust,
        }
        if self._captcha_state:
            payload["captchaState"] = self._captcha_state
        response = await self._request(
            "POST",
            self._origin + "/account/otp_generate",
            data=payload,
            headers=self._headers,
        )
        data = response.json()
        if data.get("success") is True and response.status == 200:
            self._ready = True
            self._captcha_state = ""
            return OTPPrompt("code")
        if _nested(data, "hhcaptcha").get("captchaState"):
            return await self._captcha(data["hhcaptcha"]["captchaState"], "send")
        raise HHPermanentRequestError("HH could not send OTP")

    async def _captcha(self, state: str, step: str) -> OTPPrompt:
        if not isinstance(state, str) or not state:
            raise HHPermanentRequestError("HH invalid captcha")
        self._captcha_state, self._captcha_step = state, step
        response = await self._request(
            "POST",
            self._origin + "/captcha?lang=RU",
            headers=self._headers,
        )
        key = response.json().get("key")
        if response.status != 200 or not isinstance(key, str) or not key:
            raise HHPermanentRequestError("HH invalid captcha")
        self._captcha_key = key
        image = await self._request(
            "GET",
            self._origin + "/captcha/picture?" + urlencode({"key": key}),
            headers=self._headers,
        )
        mime = image.headers.get("Content-Type", "").split(";")[0].lower()
        if (
            image.status != 200
            or mime not in ("image/png", "image/jpeg", "image/webp")
            or not image.body
        ):
            raise HHPermanentRequestError("HH invalid captcha image")
        encoded = base64.b64encode(image.body).decode()
        return OTPPrompt("captcha", f"data:{mime};base64,{encoded}")

    async def solve_captcha(self, text: str) -> OTPPrompt:
        if not self._captcha_state:
            raise HHPermanentRequestError("HH captcha not pending")
        payload = {
            "captchaText": text,
            "captchaKey": self._captcha_key,
            "captchaState": self._captcha_state,
            "backurl": "/",
            "fialurl": "/account/captcha?state=" + self._captcha_state,
        }
        url = self._origin + "/account/captcha"
        method = "POST"
        response = await self._request(
            "POST",
            url,
            headers=self._headers,
            data=payload,
            params=payload,
        )
        # requests в SDK следует редиректам автоматически. Здесь каждый hop
        # проверяется отдельно, чтобы ответ капчи не ушёл за пределы HH.
        for _ in range(6):
            logger.info("HH OTP captcha response: status=%d", response.status)
            if response.status not in (301, 302, 303, 307, 308):
                break
            location = response.headers.get("Location")
            if not location:
                raise HHPermanentRequestError("HH captcha redirect missing")
            url = _hh_url(urljoin(url, location))
            if response.status in (301, 302, 303):
                method = "GET"
            response = await self._request(
                method,
                url,
                headers=self._headers,
                **({"data": payload} if method == "POST" else {}),
            )
        else:
            raise HHPermanentRequestError("HH captcha redirect limit")
        if response.status == 403:
            return await self._captcha(self._captcha_state, self._captcha_step)
        if response.status != 200:
            raise HHPermanentRequestError("HH captcha rejected")
        if self._captcha_step == "send":
            return await self._send_code()
        self._captcha_state = ""
        return OTPPrompt("code")

    async def confirm(self, code: str) -> HHAccountTokenData | OTPPrompt:
        if not self._ready or self._captcha_state:
            raise HHPermanentRequestError("HH OTP not pending")
        response = await self._request(
            "POST",
            self._origin + "/account/login/by_code",
            headers=self._headers,
            data={
                "_xsrf": self._xsrf,
                "failUrl": self._failurl,
                "remember": "yes",
                "username": self._username,
                "password": "",
                "code": code,
                "backurl": self._backurl,
                "operationType": "applicant_otp_auth",
                "authScenario": "APPLICANT_AUTH",
            },
        )
        data = response.json()
        if _nested(data, "hhcaptcha").get("captchaState"):
            return await self._captcha(data["hhcaptcha"]["captchaState"], "verify")
        if (
            data.get("success") is not True
            or _nested(data, "verification").get("success") is not True
        ):
            raise OTPInvalidCode("HH OTP rejected")
        backurl = data.get("backurl")
        if not isinstance(backurl, str):
            raise HHPermanentRequestError("HH invalid return URL")
        url = _hh_url(urljoin(self._origin, backurl))
        for _ in range(6):
            response = await self._request("GET", url)
            location = response.headers.get("Location", "")
            if response.status not in (301, 302, 303, 307, 308) or not location:
                raise HHPermanentRequestError("HH missing OAuth response")
            redirect = urlsplit(location)
            if redirect.scheme == "hhandroid" and redirect.netloc == "oauthresponse":
                try:
                    params = parse_qs(redirect.query, max_num_fields=10)
                    (auth_code,) = params.get("code", [])
                    if params.get("state", [self._state]) != [self._state]:
                        raise ValueError
                except ValueError:
                    raise HHPermanentRequestError("HH invalid OAuth response") from None
                return await HHOAuthClient().exchange_code(auth_code, "")
            url = _hh_url(urljoin(url, location))
        raise HHPermanentRequestError("HH redirect limit")
