import asyncio
from collections.abc import Callable
from typing import Any, Literal

from job_aggregator.integrations.hh.errors import HHIntegrationError
from job_aggregator.schemas.hh_token import HHAccountTokenData


class FakeHHAPIClient:
    """Управляемый ответ, refresh и ожидание на границе HTTP-адаптера."""

    def __init__(
        self,
        tokens: HHAccountTokenData,
        *,
        allow_token_refresh: bool,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        self.tokens = tokens
        self.initial_tokens = tokens.model_copy()
        self.allow_token_refresh = allow_token_refresh
        self.client_id = client_id
        self.client_secret = client_secret
        self.response: Any = {"ok": True}
        self.error: HHIntegrationError | None = None
        self.replacement: HHAccountTokenData | None = None
        self.started = asyncio.Event()
        self.release: asyncio.Event | None = None
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []
        self.closed = False

    async def request(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        self.calls.append((method, endpoint, params))
        self.started.set()
        if self.release is not None:
            await self.release.wait()
        if self.replacement is not None:
            self.tokens = self.replacement
        if self.error is not None:
            raise self.error
        return self.response

    def get_current_tokens(self) -> HHAccountTokenData:
        return self.tokens

    def close(self) -> None:
        self.closed = True


class FakeHHAPIFactory:
    """Создаёт независимый HTTP-double на каждый авторизованный запрос."""

    def __init__(self) -> None:
        self.instances: list[FakeHHAPIClient] = []
        self.configure: Callable[[FakeHHAPIClient], None] = lambda client: None

    def __call__(
        self,
        tokens: HHAccountTokenData,
        **kwargs: Any,
    ) -> FakeHHAPIClient:
        client = FakeHHAPIClient(tokens, **kwargs)
        self.configure(client)
        self.instances.append(client)
        return client
