import asyncio
from unittest.mock import AsyncMock

import pytest

from job_aggregator.integrations.hh.otp import OTPInvalidCode, OTPPrompt
from job_aggregator.services.otp_login import (
    OTPExpired,
    OTPLoginService,
    OTPThrottled,
    normalize_login,
)
from tests.factories import make_token_data


@pytest.fixture
async def flows():
    """Изолирует временные HTTP-контексты и управляемое время входа."""
    clock = [1000.0]
    clients = []

    def factory():
        client = AsyncMock()
        client.start.return_value = OTPPrompt("code")
        client.confirm.return_value = make_token_data()
        clients.append(client)
        return client

    service = OTPLoginService(factory=factory, clock=lambda: clock[0])
    try:
        yield service, clients, clock
    finally:
        await service.close()


async def test_success_is_single_use_and_users_are_isolated(flows):
    service, clients, _ = flows
    first, _ = await service.start("a@example.test", "one")
    second, _ = await service.start("b@example.test", "two")
    tokens = await service.confirm(first, "1234")
    assert tokens == make_token_data()
    clients[0].close.assert_awaited_once()
    clients[1].close.assert_not_awaited()
    with pytest.raises(OTPExpired):
        await service.confirm(first, "1234")
    assert await service.confirm(second, "5678") == tokens


async def test_five_wrong_codes_close_context(flows):
    service, clients, _ = flows
    token, _ = await service.start("a@example.test", "one")
    clients[0].confirm.side_effect = OTPInvalidCode("invalid")
    for _ in range(5):
        with pytest.raises(OTPInvalidCode):
            await service.confirm(token, "1234")
    clients[0].close.assert_awaited_once()
    with pytest.raises(OTPExpired):
        await service.confirm(token, "1234")


async def test_expiry_closes_idle_http_without_next_login(flows):
    service, clients, clock = flows
    token, _ = await service.start("a@example.test", "one")
    clock[0] += 601
    await service.prune()
    clients[0].close.assert_awaited_once()
    with pytest.raises(OTPExpired):
        await service.confirm(token, "1234")


async def test_cooldown_preserves_current_flow_and_ip_has_bound(flows):
    service, clients, clock = flows
    token, _ = await service.start("a@example.test", "one")
    with pytest.raises(OTPThrottled):
        await service.start("a@example.test", "one")
    clients[0].close.assert_not_awaited()
    assert (await service.confirm(token, "1234")).access_token
    for n in range(9):
        await service.start(f"{n}@example.test", "one")
    with pytest.raises(OTPThrottled):
        await service.start("last@example.test", "one")
    clock[0] += 601
    await service.start("last@example.test", "one")


async def test_concurrent_verify_only_consumes_once(flows):
    service, clients, _ = flows
    token, _ = await service.start("a@example.test", "one")
    results = await asyncio.gather(
        service.confirm(token, "1234"),
        service.confirm(token, "1234"),
        return_exceptions=True,
    )
    assert sum(isinstance(result, OTPExpired) for result in results) == 1
    clients[0].confirm.assert_awaited_once()


async def test_cancelled_verification_closes_flow(flows):
    service, clients, _ = flows
    token, _ = await service.start("a@example.test", "one")
    clients[0].confirm.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await service.confirm(token, "1234")
    clients[0].close.assert_awaited_once()
    with pytest.raises(OTPExpired):
        await service.confirm(token, "1234")


async def test_cancelled_cancel_does_not_lose_inflight_context(flows):
    service, clients, _ = flows
    token, _ = await service.start("a@example.test", "one")
    started, release = asyncio.Event(), asyncio.Event()

    async def slow_confirm(code):
        started.set()
        await release.wait()
        return make_token_data()

    clients[0].confirm.side_effect = slow_confirm
    verifying = asyncio.create_task(service.confirm(token, "1234"))
    await started.wait()
    cancelling = asyncio.create_task(service.cancel(token))
    await asyncio.sleep(0)
    cancelling.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelling
    release.set()
    await verifying
    await service.close()
    clients[0].close.assert_awaited_once()


@pytest.mark.parametrize(
    "value,expected",
    [
        (" USER@example.test ", "user@example.test"),
        ("8 (999) 123-45-67", "79991234567"),
    ],
)
def test_normalize_login(value, expected):
    assert normalize_login(value) == expected


@pytest.mark.parametrize(
    "value", ["x", "a@b", "123", "１２３４５６７８９０", "user@x.test\nsecret"]
)
def test_reject_invalid_login(value):
    with pytest.raises(ValueError):
        normalize_login(value)
