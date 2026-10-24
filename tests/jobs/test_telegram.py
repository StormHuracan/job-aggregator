import hashlib
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from job_aggregator.db.models.saved_search import SavedSearch
from job_aggregator.db.models.saved_search_match import SavedSearchMatch
from job_aggregator.db.models.telegram_binding import TelegramBinding
from job_aggregator.db.models.telegram_bot_state import TelegramBotState
from job_aggregator.db.models.telegram_delivery import TelegramDelivery
from job_aggregator.db.models.telegram_link_token import TelegramLinkToken
from job_aggregator.db.models.user import User
from job_aggregator.db.models.vacancy import Vacancy
from job_aggregator.jobs.telegram import TelegramAPIError, TelegramBot


async def create_telegram_scenario(
    session,
    session_factory,
    *,
    connected_at: datetime | None = None,
    is_enabled: bool = True,
    matched_at: datetime | None = None,
    already_delivered: bool = False,
):
    now = datetime.now(UTC)

    user = User(
        hh_user_id=f"hh-telegram-{now.timestamp()}",
        display_name="Telegram test",
    )
    session.add(user)
    await session.flush()

    search = SavedSearch(
        name="Python developer",
        text="Python developer",
        user_id=user.id,
        is_enabled=is_enabled,
    )
    session.add(search)

    vacancy = Vacancy(
        source="hh",
        external_id=f"vacancy-{now.timestamp()}",
        title="Python Developer",
        company_name="Test Company",
        source_url="https://example.com/vacancy",
    )
    session.add(vacancy)
    await session.flush()

    session.add(
        TelegramBinding(
            user_id=user.id,
            chat_id=123456789,
            connected_at=connected_at or now - timedelta(minutes=1),
        )
    )

    match = SavedSearchMatch(
        saved_search_id=search.id,
        vacancy_id=vacancy.id,
        matched_at=matched_at or now,
    )
    session.add(match)
    await session.flush()

    if already_delivered:
        session.add(
            TelegramDelivery(
                saved_search_match_id=match.id,
                delivered_at=now,
            )
        )

    await session.commit()

    bot = TelegramBot(
        session_factory,
        SimpleNamespace(
            telegram_bot_token="test-token",
            telegram_bot_username="test_bot",
        ),
        client=AsyncMock(),
    )
    bot.send_message = AsyncMock()

    return bot, match.id


@pytest.fixture
def telegram_session_factory(sqlite_session):
    return async_sessionmaker(
        bind=sqlite_session.bind,
        expire_on_commit=False,
    )


@pytest.mark.asyncio
async def test_delivers_new_match(sqlite_session, telegram_session_factory):
    bot, match_id = await create_telegram_scenario(
        sqlite_session,
        telegram_session_factory,
    )

    await bot._deliver_pending()

    bot.send_message.assert_awaited_once()
    assert bot.send_message.await_args.args[0] == 123456789
    assert "Python Developer" in bot.send_message.await_args.args[1]

    async with telegram_session_factory() as session:
        delivery = await session.scalar(
            select(TelegramDelivery).where(
                TelegramDelivery.saved_search_match_id == match_id
            )
        )

    assert delivery is not None


@pytest.mark.asyncio
async def test_does_not_deliver_match_from_before_connection(
    sqlite_session,
    telegram_session_factory,
):
    now = datetime.now(UTC)
    bot, _ = await create_telegram_scenario(
        sqlite_session,
        telegram_session_factory,
        connected_at=now,
        matched_at=now - timedelta(minutes=1),
    )

    await bot._deliver_pending()

    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_does_not_deliver_match_for_disabled_search(
    sqlite_session,
    telegram_session_factory,
):
    bot, _ = await create_telegram_scenario(
        sqlite_session,
        telegram_session_factory,
        is_enabled=False,
    )

    await bot._deliver_pending()

    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_does_not_deliver_match_twice(
    sqlite_session,
    telegram_session_factory,
):
    bot, _ = await create_telegram_scenario(
        sqlite_session,
        telegram_session_factory,
        already_delivered=True,
    )

    await bot._deliver_pending()

    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_transient_error_does_not_record_delivery_and_can_retry(
    sqlite_session,
    telegram_session_factory,
):
    bot, match_id = await create_telegram_scenario(
        sqlite_session,
        telegram_session_factory,
    )
    bot.send_message.side_effect = TelegramAPIError(
        "Temporary Telegram error.",
        error_code=500,
    )

    await bot._deliver_pending()

    async with telegram_session_factory() as session:
        delivery = await session.scalar(
            select(TelegramDelivery).where(
                TelegramDelivery.saved_search_match_id == match_id
            )
        )

    assert delivery is None

    bot.send_message.side_effect = None

    await bot._deliver_pending()

    assert bot.send_message.await_count == 2

    async with telegram_session_factory() as session:
        delivery = await session.scalar(
            select(TelegramDelivery).where(
                TelegramDelivery.saved_search_match_id == match_id
            )
        )

    assert delivery is not None


@pytest.mark.asyncio
async def test_rate_limit_delays_delivery(
    sqlite_session,
    telegram_session_factory,
):
    bot, match_id = await create_telegram_scenario(
        sqlite_session,
        telegram_session_factory,
    )
    bot.send_message.side_effect = TelegramAPIError(
        "Too many requests.",
        error_code=429,
        retry_after=30,
    )

    await bot._deliver_pending()

    bot.send_message.assert_awaited_once()
    assert bot.retry_after_until[123456789] > 0

    # Пока действует ограничение, повторной отправки быть не должно.
    await bot._deliver_pending()

    bot.send_message.assert_awaited_once()

    async with telegram_session_factory() as session:
        delivery = await session.scalar(
            select(TelegramDelivery).where(
                TelegramDelivery.saved_search_match_id == match_id
            )
        )

    assert delivery is None


@pytest.mark.asyncio
async def test_blocked_user_binding_is_removed(
    sqlite_session,
    telegram_session_factory,
):
    bot, match_id = await create_telegram_scenario(
        sqlite_session,
        telegram_session_factory,
    )
    bot.send_message.side_effect = TelegramAPIError(
        "Bot was blocked by the user.",
        error_code=403,
    )

    await bot._deliver_pending()

    async with telegram_session_factory() as session:
        binding = await session.scalar(
            select(TelegramBinding).where(TelegramBinding.chat_id == 123456789)
        )
        delivery = await session.scalar(
            select(TelegramDelivery).where(
                TelegramDelivery.saved_search_match_id == match_id
            )
        )

    assert binding is None
    assert delivery is None


async def create_link_token(
    session,
    session_factory,
    token="test-token",
):
    user = User(
        hh_user_id=f"hh-{token}",
        display_name="Telegram user",
    )
    session.add(user)
    await session.flush()

    link_token = TelegramLinkToken(
        user_id=user.id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    session.add(link_token)
    await session.commit()

    bot = TelegramBot(
        session_factory,
        SimpleNamespace(
            telegram_bot_token="test-token",
            telegram_bot_username="test_bot",
        ),
        client=AsyncMock(),
    )
    bot.send_message = AsyncMock()

    return bot, user.id, link_token.id


@pytest.mark.asyncio
async def test_start_token_creates_binding_and_consumes_token(
    sqlite_session,
    telegram_session_factory,
):
    bot, user_id, token_id = await create_link_token(
        sqlite_session,
        telegram_session_factory,
    )

    result = await bot._process_update(
        {
            "update_id": 100,
            "message": {
                "text": "/start test-token",
                "chat": {"id": 123456789, "type": "private"},
            },
        }
    )

    assert result is not None
    assert "успешно привязан" in result[1]

    async with telegram_session_factory() as session:
        binding = await session.scalar(
            select(TelegramBinding).where(TelegramBinding.user_id == user_id)
        )
        token = await session.get(TelegramLinkToken, token_id)
        state = await session.get(TelegramBotState, 1)

    assert binding is not None
    assert binding.chat_id == 123456789
    assert token.consumed_at is not None
    assert state.update_offset == 101


@pytest.mark.asyncio
async def test_start_token_cannot_be_reused(
    sqlite_session,
    telegram_session_factory,
):
    bot, _, _ = await create_link_token(
        sqlite_session,
        telegram_session_factory,
    )

    await bot._process_update(
        {
            "update_id": 100,
            "message": {
                "text": "/start test-token",
                "chat": {"id": 123456789, "type": "private"},
            },
        }
    )

    result = await bot._process_update(
        {
            "update_id": 101,
            "message": {
                "text": "/start test-token",
                "chat": {"id": 987654321, "type": "private"},
            },
        }
    )

    assert result is not None
    assert "недействительна" in result[1]

    async with telegram_session_factory() as session:
        bindings = (await session.scalars(select(TelegramBinding))).all()

    assert len(bindings) == 1
    assert bindings[0].chat_id == 123456789


@pytest.mark.asyncio
async def test_help_command_returns_instructions(
    sqlite_session,
    telegram_session_factory,
):
    bot = TelegramBot(
        telegram_session_factory,
        SimpleNamespace(
            telegram_bot_token="test-token",
            telegram_bot_username="test_bot",
        ),
        client=AsyncMock(),
    )

    result = await bot._process_update(
        {
            "update_id": 200,
            "message": {
                "text": "/help",
                "chat": {"id": 123456789, "type": "private"},
            },
        }
    )

    assert result is not None
    assert "/stop" in result[1]
    assert "личном кабинете" in result[1]


@pytest.mark.asyncio
async def test_start_in_group_does_not_create_binding(
    sqlite_session,
    telegram_session_factory,
):
    bot, _, _ = await create_link_token(
        sqlite_session,
        telegram_session_factory,
    )

    result = await bot._process_update(
        {
            "update_id": 300,
            "message": {
                "text": "/start test-token",
                "chat": {"id": -100123, "type": "group"},
            },
        }
    )

    assert result is not None
    assert "личный чат" in result[1]

    async with telegram_session_factory() as session:
        binding = await session.scalar(select(TelegramBinding))

    assert binding is None


@pytest.mark.asyncio
async def test_duplicate_update_is_ignored(
    sqlite_session,
    telegram_session_factory,
):
    bot = TelegramBot(
        telegram_session_factory,
        SimpleNamespace(
            telegram_bot_token="test-token",
            telegram_bot_username="test_bot",
        ),
        client=AsyncMock(),
    )

    update = {
        "update_id": 400,
        "message": {
            "text": "/help",
            "chat": {"id": 123456789, "type": "private"},
        },
    }

    first_result = await bot._process_update(update)
    second_result = await bot._process_update(update)

    assert first_result is not None
    assert second_result is None

    async with telegram_session_factory() as session:
        state = await session.get(TelegramBotState, 1)

    assert state.update_offset == 401
