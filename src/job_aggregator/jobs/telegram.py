import asyncio
import hashlib
import logging
from datetime import UTC, datetime

import aiohttp
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_aggregator.core.config import Settings
from job_aggregator.db.models.saved_search import SavedSearch
from job_aggregator.db.models.saved_search_match import SavedSearchMatch
from job_aggregator.db.models.telegram_binding import TelegramBinding
from job_aggregator.db.models.telegram_bot_state import TelegramBotState
from job_aggregator.db.models.telegram_delivery import TelegramDelivery
from job_aggregator.db.models.telegram_link_token import TelegramLinkToken
from job_aggregator.db.models.vacancy import Vacancy

logger = logging.getLogger(__name__)

POLL_TIMEOUT = 30
MAX_MESSAGE_LENGTH = 4096
DELIVERY_BATCH_SIZE = 100
MAX_CONSECUTIVE_DELIVERY_FAILURES = 3
DELIVERY_RETRY_COOLDOWN = 60


class TelegramAPIError(Exception):
    def __init__(
        self,
        message: str,
        *,
        error_code: int | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.retry_after = retry_after


class TelegramBot:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        client: aiohttp.ClientSession,
    ) -> None:
        if not settings.telegram_bot_token or not settings.telegram_bot_username:
            raise RuntimeError(
                "Telegram is enabled, but its token or username is missing."
            )

        self.session_factory = session_factory
        self.client = client
        self.api_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}"

        # Временные ограничения на отправку в отдельные чаты.
        self.retry_after_until: dict[int, float] = {}

        # Число последовательных ошибок для каждой доставки.
        self.delivery_failures: dict[int, int] = {}

        # Временная пауза после серии ошибок.
        self.delivery_retry_after_until: dict[int, float] = {}

    async def _request(
        self,
        method: str,
        payload: dict | None = None,
    ) -> dict:
        try:
            async with self.client.post(
                f"{self.api_url}/{method}",
                json=payload or {},
            ) as response:
                data = await response.json()

        except (aiohttp.ClientError, TimeoutError) as exc:
            raise TelegramAPIError("Telegram request failed.") from exc

        if not data.get("ok"):
            parameters = data.get("parameters") or {}
            raise TelegramAPIError(
                "Telegram API returned an error.",
                error_code=data.get("error_code"),
                retry_after=parameters.get("retry_after"),
            )

        return data.get("result", {})

    async def send_message(self, chat_id: int, text: str) -> None:
        await self._request(
            "sendMessage",
            {"chat_id": chat_id, "text": text},
        )

    async def _get_offset(self) -> int:
        async with self.session_factory() as session:
            async with session.begin():
                state = await session.get(TelegramBotState, 1)

                if state is None:
                    state = TelegramBotState(id=1, update_offset=0)
                    session.add(state)
                    await session.flush()

                return state.update_offset

    async def _process_update(
        self,
        update_data: dict,
    ) -> tuple[int, str] | None:
        update_id = update_data["update_id"]
        message = update_data.get("message")
        chat = (message or {}).get("chat") or {}

        chat_id = chat.get("id")
        chat_type = chat.get("type")
        text = ((message or {}).get("text") or "").strip()

        reply: str | None = None

        try:
            async with self.session_factory() as session:
                async with session.begin():
                    state = await session.get(TelegramBotState, 1)

                    if state is None:
                        state = TelegramBotState(id=1, update_offset=0)
                        session.add(state)
                        await session.flush()

                    # Offset хранит ID следующего ожидаемого обновления.
                    # Старые обновления повторно не применяем.
                    if update_id < state.update_offset:
                        return None

                    if chat_id is not None and text.startswith("/"):
                        command_parts = text.split(maxsplit=1)
                        command = command_parts[0].split("@")[0].lower()

                        if command in {"/start", "/help", "/stop"}:
                            if chat_type != "private":
                                reply = (
                                    "Для управления уведомлениями "
                                    "используйте личный чат с ботом."
                                )

                            elif command == "/start":
                                if len(command_parts) == 1:
                                    reply = (
                                        "Откройте личный кабинет, создайте "
                                        "ссылку Telegram и перейдите по ней, "
                                        "чтобы подключить уведомления."
                                    )
                                else:
                                    token = command_parts[1]
                                    token_hash = hashlib.sha256(
                                        token.encode()
                                    ).hexdigest()
                                    now = datetime.now(UTC)

                                    existing_chat = await session.scalar(
                                        select(TelegramBinding).where(
                                            TelegramBinding.chat_id == chat_id
                                        )
                                    )

                                    if existing_chat is not None:
                                        reply = (
                                            "Этот Telegram-чат уже привязан. "
                                            "Сначала отключите его командой /stop."
                                        )
                                    else:
                                        link_token = await session.scalar(
                                            select(TelegramLinkToken)
                                            .where(
                                                TelegramLinkToken.token_hash
                                                == token_hash,
                                                TelegramLinkToken.consumed_at.is_(None),
                                                TelegramLinkToken.expires_at > now,
                                            )
                                            .with_for_update()
                                        )

                                        if link_token is None:
                                            reply = (
                                                "Ссылка недействительна или "
                                                "устарела. Создайте новую "
                                                "в личном кабинете."
                                            )
                                        else:
                                            existing_user = await session.scalar(
                                                select(TelegramBinding).where(
                                                    TelegramBinding.user_id
                                                    == link_token.user_id
                                                )
                                            )

                                            if existing_user is not None:
                                                reply = (
                                                    "К аккаунту уже привязан "
                                                    "Telegram. Сначала отключите "
                                                    "его в личном кабинете."
                                                )
                                            else:
                                                link_token.consumed_at = now
                                                session.add(
                                                    TelegramBinding(
                                                        user_id=link_token.user_id,
                                                        chat_id=chat_id,
                                                        connected_at=now,
                                                    )
                                                )
                                                reply = (
                                                    "Telegram успешно привязан! "
                                                    "Буду присылать новые "
                                                    "подходящие вакансии."
                                                )

                            elif command == "/help":
                                reply = (
                                    "Я отправляю новые вакансии по вашим "
                                    "сохранённым поискам.\n"
                                    "Для подключения создайте ссылку "
                                    "в личном кабинете.\n"
                                    "Для отключения используйте /stop."
                                )

                            elif command == "/stop":
                                binding = await session.scalar(
                                    select(TelegramBinding).where(
                                        TelegramBinding.chat_id == chat_id
                                    )
                                )

                                if binding is not None:
                                    await session.execute(
                                        delete(TelegramLinkToken).where(
                                            TelegramLinkToken.user_id
                                            == binding.user_id,
                                            TelegramLinkToken.consumed_at.is_(None),
                                        )
                                    )
                                    await session.delete(binding)

                                reply = (
                                    "Telegram-уведомления отключены. "
                                    "Повторно подключить их можно "
                                    "через личный кабинет."
                                )

                    # Изменения привязки и offset фиксируются одной транзакцией.
                    state.update_offset = update_id + 1

        except IntegrityError:
            # Уникальные ограничения защищают от повторной привязки
            # одного пользователя или чата.
            async with self.session_factory() as session:
                async with session.begin():
                    state = await session.get(TelegramBotState, 1)

                    if state is None:
                        session.add(
                            TelegramBotState(
                                id=1,
                                update_offset=update_id + 1,
                            )
                        )
                    else:
                        state.update_offset = max(
                            state.update_offset,
                            update_id + 1,
                        )

            if chat_id is not None:
                reply = (
                    "Не удалось изменить привязку: "
                    "пользователь или чат уже связан с другим аккаунтом."
                )

        if chat_id is not None and reply is not None:
            return chat_id, reply

        return None

    async def _handle_update(self, update_data: dict) -> None:
        result = await self._process_update(update_data)

        if result is None:
            return

        chat_id, reply = result

        try:
            await self.send_message(chat_id, reply)
        except TelegramAPIError as exc:
            if exc.error_code == 403:
                # Если пользователь заблокировал бота, отключаем привязку.
                await self._remove_blocked_binding(chat_id)
            elif exc.error_code == 429 and exc.retry_after is not None:
                loop = asyncio.get_running_loop()
                self.retry_after_until[chat_id] = loop.time() + max(1, exc.retry_after)

            logger.warning("Telegram command reply failed.")

    async def _poll_updates(self, offset: int) -> list[dict]:
        return await self._request(
            "getUpdates",
            {
                "offset": offset,
                "timeout": POLL_TIMEOUT,
                "allowed_updates": ["message"],
            },
        )

    @staticmethod
    def _format_salary(
        salary_from: int | None,
        salary_to: int | None,
        currency: str | None,
    ) -> str:
        if salary_from is None and salary_to is None:
            return "Зарплата не указана"

        low = str(salary_from) if salary_from is not None else "не указана"
        high = str(salary_to) if salary_to is not None else "не указана"
        currency_text = f" {currency}" if currency else ""

        return f"Зарплата: {low}–{high}{currency_text}"

    @staticmethod
    def _format_message(
        search_name: str,
        title: str,
        company_name: str,
        area_name: str | None,
        salary_from: int | None,
        salary_to: int | None,
        salary_currency: str | None,
        source_url: str,
    ) -> str:
        salary = TelegramBot._format_salary(
            salary_from,
            salary_to,
            salary_currency,
        )

        details = (
            f"Новый результат поиска «{search_name}»\n\n"
            f"{title}\n"
            f"Компания: {company_name}\n"
            f"Город: {area_name or 'не указан'}\n"
            f"{salary}\n\n"
        )

        if len(source_url) >= MAX_MESSAGE_LENGTH:
            return source_url[: MAX_MESSAGE_LENGTH - 1] + "…"

        available = MAX_MESSAGE_LENGTH - len(source_url)

        if len(details) > available:
            details = details[: max(0, available - 1)] + "…"

        return details + source_url

    async def _remove_blocked_binding(self, chat_id: int) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                binding = await session.scalar(
                    select(TelegramBinding).where(TelegramBinding.chat_id == chat_id)
                )

                if binding is None:
                    return

                await session.execute(
                    delete(TelegramLinkToken).where(
                        TelegramLinkToken.user_id == binding.user_id,
                        TelegramLinkToken.consumed_at.is_(None),
                    )
                )
                await session.delete(binding)

        self.retry_after_until.pop(chat_id, None)

    def _record_delivery_failure(
        self,
        match_id: int,
        retry_at: float,
    ) -> None:
        failures = self.delivery_failures.get(match_id, 0) + 1

        if failures >= MAX_CONSECUTIVE_DELIVERY_FAILURES:
            self.delivery_failures[match_id] = 0
            self.delivery_retry_after_until[match_id] = (
                retry_at + DELIVERY_RETRY_COOLDOWN
            )
        else:
            self.delivery_failures[match_id] = failures

    async def _deliver_pending(self) -> None:
        loop = asyncio.get_running_loop()
        now = loop.time()

        # Удаляем истёкшие временные ограничения.
        for chat_id, retry_at in list(self.retry_after_until.items()):
            if retry_at <= now:
                self.retry_after_until.pop(chat_id, None)

        for match_id, retry_at in list(self.delivery_retry_after_until.items()):
            if retry_at <= now:
                self.delivery_retry_after_until.pop(match_id, None)

        excluded_chats = [
            chat_id
            for chat_id, retry_at in self.retry_after_until.items()
            if retry_at > now
        ]
        excluded_matches = [
            match_id
            for match_id, retry_at in self.delivery_retry_after_until.items()
            if retry_at > now
        ]

        statement = (
            select(
                SavedSearchMatch.id,
                SavedSearch.name,
                Vacancy.title,
                Vacancy.company_name,
                Vacancy.area_name,
                Vacancy.salary_from,
                Vacancy.salary_to,
                Vacancy.salary_currency,
                Vacancy.source_url,
                TelegramBinding.chat_id,
            )
            .join(
                SavedSearch,
                SavedSearch.id == SavedSearchMatch.saved_search_id,
            )
            .join(
                Vacancy,
                Vacancy.id == SavedSearchMatch.vacancy_id,
            )
            .join(
                TelegramBinding,
                TelegramBinding.user_id == SavedSearch.user_id,
            )
            .outerjoin(
                TelegramDelivery,
                TelegramDelivery.saved_search_match_id == SavedSearchMatch.id,
            )
            .where(
                SavedSearch.user_id.is_not(None),
                SavedSearch.is_enabled.is_(True),
                SavedSearchMatch.matched_at >= TelegramBinding.connected_at,
                TelegramDelivery.id.is_(None),
            )
            .order_by(SavedSearchMatch.matched_at, SavedSearchMatch.id)
            .limit(DELIVERY_BATCH_SIZE)
        )

        if excluded_chats:
            statement = statement.where(TelegramBinding.chat_id.not_in(excluded_chats))

        if excluded_matches:
            statement = statement.where(SavedSearchMatch.id.not_in(excluded_matches))

        async with self.session_factory() as session:
            rows = (await session.execute(statement)).all()

        for row in rows:
            (
                match_id,
                search_name,
                title,
                company_name,
                area_name,
                salary_from,
                salary_to,
                salary_currency,
                source_url,
                chat_id,
            ) = row

            message = self._format_message(
                search_name=search_name,
                title=title,
                company_name=company_name,
                area_name=area_name,
                salary_from=salary_from,
                salary_to=salary_to,
                salary_currency=salary_currency,
                source_url=source_url,
            )

            try:
                await self.send_message(chat_id, message)

            except TelegramAPIError as exc:
                if exc.error_code == 403:
                    await self._remove_blocked_binding(chat_id)
                    self.delivery_failures.pop(match_id, None)
                    self.delivery_retry_after_until.pop(match_id, None)

                elif exc.error_code == 429 and exc.retry_after is not None:
                    self.retry_after_until[chat_id] = loop.time() + max(
                        1, exc.retry_after
                    )

                else:
                    self._record_delivery_failure(match_id, loop.time())
                    logger.warning(
                        "Telegram notification failed for match id %s.",
                        match_id,
                    )

                continue

            except Exception:
                self._record_delivery_failure(match_id, loop.time())
                logger.warning(
                    "Unexpected Telegram delivery failure for match id %s.",
                    match_id,
                )
                continue

            try:
                async with self.session_factory() as session:
                    async with session.begin():
                        session.add(
                            TelegramDelivery(
                                saved_search_match_id=match_id,
                                delivered_at=datetime.now(UTC),
                            )
                        )

            except IntegrityError:
                # Уникальное ограничение не допускает дублирующую запись.
                pass

            self.delivery_failures.pop(match_id, None)
            self.delivery_retry_after_until.pop(match_id, None)

    async def run(self) -> None:
        offset = await self._get_offset()

        while True:
            try:
                updates = await self._poll_updates(offset)

                for item in updates:
                    await self._handle_update(item)

                # Offset в БД является источником истины.
                offset = await self._get_offset()

                await self._deliver_pending()

            except asyncio.CancelledError:
                raise

            except TelegramAPIError as exc:
                if exc.error_code == 429 and exc.retry_after is not None:
                    await asyncio.sleep(max(1, exc.retry_after))
                else:
                    logger.warning("Telegram polling request failed.")
                    await asyncio.sleep(5)

            except SQLAlchemyError:
                logger.exception("Database error in Telegram bot.")
                await asyncio.sleep(5)

            except Exception:
                logger.exception("Unexpected error in Telegram bot.")
                await asyncio.sleep(5)


async def run_telegram_bot(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    if not settings.telegram_enabled:
        return

    if not settings.telegram_bot_token or not settings.telegram_bot_username:
        raise RuntimeError("Telegram is enabled, but its token or username is missing.")

    timeout = aiohttp.ClientTimeout(total=POLL_TIMEOUT + 10)

    async with aiohttp.ClientSession(timeout=timeout) as client:
        bot = TelegramBot(session_factory, settings, client)
        await bot.run()
