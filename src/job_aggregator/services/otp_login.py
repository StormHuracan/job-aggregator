import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from hashlib import sha256
from secrets import token_urlsafe
from time import monotonic

from job_aggregator.integrations.hh.otp import HHOTPClient, OTPPrompt
from job_aggregator.schemas.hh_token import HHAccountTokenData

OTP_TTL = 600
OTP_COOLDOWN = 60


class OTPExpired(Exception):
    """Попытка входа отсутствует, истекла или исчерпала число проверок."""


class OTPThrottled(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = max(1, retry_after)


def normalize_login(value: str) -> str:
    """Email или международный номер без форматирующих символов."""
    value = value.strip()
    if "@" in value:
        if len(value) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("invalid login")
        return value.lower()
    if not re.fullmatch(r"\+?[\d ()-]+", value, flags=re.ASCII):
        raise ValueError("invalid login")
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if not 10 <= len(digits) <= 15:
        raise ValueError("invalid login")
    return digits


@dataclass(repr=False)
class _Pending:
    client: HHOTPClient
    expires_at: float
    attempts: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class OTPLoginService:
    """Временные HH cookie jar одного worker, без токенов пользователя в браузере.

    Состояние нужно только во время входа. Рестарт процесса требует нового OTP.
    Лимиты и TTL ограничивают ресурсы; завершение/отмена/expiry закрывают HTTP.
    """

    def __init__(
        self,
        *,
        factory: Callable[[], HHOTPClient] = HHOTPClient,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._factory, self._clock = factory, clock
        self._pending: dict[str, _Pending] = {}
        self._limits: dict[str, list[float]] = {}

    async def close(self) -> None:
        entries = list(self._pending.values())
        self._pending.clear()
        await asyncio.gather(*(entry.client.close() for entry in entries))

    async def prune(self) -> None:
        """Закрывает истёкшие HTTP-контексты, даже если новых запросов нет."""
        now = self._clock()
        for key, entry in list(self._pending.items()):
            if entry.expires_at <= now and not entry.lock.locked():
                self._pending.pop(key, None)
                await entry.client.close()
        self._limits = {
            key: recent
            for key, times in self._limits.items()
            if (recent := [time for time in times if time > now - 600])
        }

    @staticmethod
    def _key(value: str) -> str:
        return sha256(value.encode()).hexdigest()

    async def start(self, username: str, remote: str) -> tuple[str, OTPPrompt]:
        await self.prune()
        now = self._clock()
        user_key, ip_key = self._key("user:" + username), self._key("ip:" + remote)
        user_times, ip_times = (
            self._limits.get(user_key, []),
            self._limits.get(ip_key, []),
        )
        if user_times and now - user_times[-1] < OTP_COOLDOWN:
            raise OTPThrottled(int(OTP_COOLDOWN - (now - user_times[-1])) + 1)
        if len(ip_times) >= 10:
            raise OTPThrottled(int(ip_times[0] + 600 - now) + 1)
        if len(self._pending) >= 100 or len(self._limits) >= 2000:
            raise OTPThrottled(60)
        self._limits[user_key] = [now]
        self._limits[ip_key] = [*ip_times, now]
        token = token_urlsafe(32)
        entry = _Pending(self._factory(), now + OTP_TTL)
        key = self._key(token)
        self._pending[key] = entry
        try:
            async with entry.lock:
                prompt = await entry.client.start(username)
            return token, prompt
        except BaseException:
            self._pending.pop(key, None)
            await entry.client.close()
            raise

    def _entry(self, token: str | None) -> _Pending:
        entry = self._pending.get(self._key(token or ""))
        if entry is None or entry.expires_at <= self._clock() or entry.attempts >= 5:
            raise OTPExpired
        return entry

    async def _discard(self, token: str | None) -> None:
        entry = self._pending.pop(self._key(token or ""), None)
        if entry is not None:
            await entry.client.close()

    async def confirm(
        self, token: str | None, code: str
    ) -> HHAccountTokenData | OTPPrompt:
        await self.prune()
        entry = self._entry(token)
        async with entry.lock:
            self._entry(token)
            entry.attempts += 1
            try:
                result = await entry.client.confirm(code)
            except asyncio.CancelledError:
                await self._discard(token)
                raise
            finally:
                if entry.attempts >= 5:
                    await self._discard(token)
            if isinstance(result, HHAccountTokenData):
                await self._discard(token)
            return result

    async def captcha(self, token: str | None, text: str) -> OTPPrompt:
        await self.prune()
        entry = self._entry(token)
        async with entry.lock:
            self._entry(token)
            entry.attempts += 1
            try:
                return await entry.client.solve_captcha(text)
            except asyncio.CancelledError:
                await self._discard(token)
                raise
            finally:
                if entry.attempts >= 5:
                    await self._discard(token)

    async def cancel(self, token: str | None) -> None:
        entry = self._pending.pop(self._key(token or ""), None)
        if entry:
            async with entry.lock:
                await entry.client.close()
