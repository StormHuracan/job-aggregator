from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.models.hh_account_token import HHAccountToken
from job_aggregator.schemas.hh_token import HHAcountTokenData


def _ensure_utc(value: datetime) -> datetime:
    """SQLite не хранит tz — доводим naive datetime до UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class TokenService:
    """Сервис хранения текущего набора OAuth-токенов HH.ru.

    Поддерживает один актуальный набор: сохранение обновляет существующую
    запись, а не создаёт дубликат. Не выполняет commit — транзакцию
    завершает вызывающая сторона.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_current(self) -> HHAcountTokenData | None:
        """Вернуть текущий набор токенов или None, если он не сохранён."""
        record = await self._session.scalar(
            select(HHAccountToken).order_by(HHAccountToken.id).limit(1)
        )
        if record is None:
            return None
        return HHAcountTokenData(
            access_token=record.access_token,
            refresh_token=record.refresh_token,
            access_expires_at=_ensure_utc(record.access_expires_at),
        )

    async def save(self, tokens: HHAcountTokenData) -> bool:
        """Сохранить набор токенов.

        Возвращает True, если запись создана или изменена, и False, если
        сохранённый набор полностью совпадает с переданным.
        """
        record = await self._session.scalar(
            select(HHAccountToken).order_by(HHAccountToken.id).limit(1)
        )

        if record is None:
            self._session.add(
                HHAccountToken(
                    access_token=tokens.access_token,
                    refresh_token=tokens.refresh_token,
                    access_expires_at=tokens.access_expires_at,
                )
            )
            await self._session.flush()
            return True

        if (
            record.access_token == tokens.access_token
            and record.refresh_token == tokens.refresh_token
            and _ensure_utc(record.access_expires_at) == tokens.access_expires_at
        ):
            return False

        record.access_token = tokens.access_token
        record.refresh_token = tokens.refresh_token
        record.access_expires_at = tokens.access_expires_at
        await self._session.flush()
        return True