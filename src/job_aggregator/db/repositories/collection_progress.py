import hashlib
import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.models.collection_progress import CollectionProgress


def collection_search_key(text: str, area: str | None) -> str:
    """Ключ точного поиска, независимый от лимита страниц и пробелов по краям."""
    canonical = json.dumps(
        [text.strip(), (area or "").strip() or None], ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


class CollectionProgressRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_update(self, user_id: int, search_key: str) -> CollectionProgress:
        """Создать/заблокировать позицию до внешнего commit/rollback.

        Блокируется только строка позиции, не User: HH обновляет токены владельца
        в отдельной транзакции. Конкурентная первая вставка изолирована SAVEPOINT.
        """
        query = (
            select(CollectionProgress)
            .where(
                CollectionProgress.user_id == user_id,
                CollectionProgress.search_key == search_key,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        progress = await self._session.scalar(query)
        if progress is not None:
            return progress
        await self._session.flush()
        try:
            async with self._session.begin_nested():
                self._session.add(
                    CollectionProgress(user_id=user_id, search_key=search_key)
                )
                await self._session.flush()
        except IntegrityError:
            # После ожидания победителя гонки читаем уже зафиксированную позицию.
            # FK и другие нарушения без существующей пары не маскируем.
            progress = await self._session.scalar(query)
            if progress is None:
                raise
            return progress
        progress = await self._session.scalar(query)
        assert progress is not None
        return progress
