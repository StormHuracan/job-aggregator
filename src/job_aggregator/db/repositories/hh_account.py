from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.models.hh_account import HHAccount
from job_aggregator.db.models.user import User
from job_aggregator.schemas.hh_token import HHAccountTokenData


class HHAccountRepository:
    """Хранение токенов пользователя без завершения внешней транзакции."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: int) -> HHAccount | None:
        return await self._session.scalar(
            select(HHAccount).where(HHAccount.user_id == user_id)
        )

    async def save(self, user_id: int, tokens: HHAccountTokenData) -> bool:
        """Создать/обновить токены; вернуть False при полном совпадении.

        Блокировка владельца сериализует также первую вставку, когда HHAccount
        ещё не существует. Действует до commit/rollback вызывающей стороны.
        Отсутствующий пользователь отклоняется без записи токенов в SQL.
        """
        owner_id = await self._session.scalar(
            select(User.id).where(User.id == user_id).with_for_update(key_share=True)
        )
        if owner_id is None:
            raise ValueError("Пользователь не найден")

        record = await self._session.scalar(
            select(HHAccount)
            .where(HHAccount.user_id == user_id)
            .execution_options(populate_existing=True)
        )
        if record is None:
            self._session.add(HHAccount(user_id=user_id, **tokens.model_dump()))
        else:
            if (
                record.access_token == tokens.access_token
                and record.refresh_token == tokens.refresh_token
                and record.access_expires_at == tokens.access_expires_at
            ):
                return False
            record.access_token = tokens.access_token
            record.refresh_token = tokens.refresh_token
            record.access_expires_at = tokens.access_expires_at

        await self._session.flush()
        return True
