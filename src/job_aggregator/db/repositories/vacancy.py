from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.models.vacancy import Vacancy
from job_aggregator.schemas.vacancy import VacancyData

_MUTABLE_FIELDS = (
    "title",
    "company_name",
    "area_name",
    "salary_from",
    "salary_to",
    "salary_currency",
    "description",
    "source_url",
    "published_at",
    "raw_data",
)


def _to_utc(value: datetime | None) -> datetime | None:
    """SQLite теряет tz — приводим naive datetime к UTC для сравнения."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _values_differ(current: Any, new: Any) -> bool:
    if isinstance(current, datetime) or isinstance(new, datetime):
        if not isinstance(current, datetime) or not isinstance(new, datetime):
            return True
        return _to_utc(current) != _to_utc(new)
    return current != new


class VacancyRepository:
    """Репозиторий сохранения и обновления вакансий.

    Идентичность вакансии определяется парой (source, external_id):
    - новая пара создаёт запись, upsert() возвращает True;
    - существующая пара обновляет изменяемые поля, upsert() возвращает False;
    - повторное сохранение идентичных данных тоже возвращает False.

    Репозиторий не делает commit()/rollback() переданной сессии — транзакцией
    управляет вызывающий код. При гонке первых вставок одной пары используется
    SAVEPOINT (begin_nested), чтобы поймать IntegrityError, не откатывая
    изменения, уже сделанные вызывающим кодом в той же транзакции.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, vacancy: VacancyData) -> bool:
        existing = await self._get(vacancy.source, vacancy.external_id)
        if existing is not None:
            await self._apply(existing, vacancy)
            return False

        try:
            async with self._session.begin_nested():
                self._session.add(
                    Vacancy(
                        source=vacancy.source,
                        external_id=vacancy.external_id,
                        title=vacancy.title,
                        company_name=vacancy.company_name,
                        area_name=vacancy.area_name,
                        salary_from=vacancy.salary_from,
                        salary_to=vacancy.salary_to,
                        salary_currency=vacancy.salary_currency,
                        description=vacancy.description,
                        source_url=vacancy.source_url,
                        published_at=vacancy.published_at,
                        raw_data=vacancy.raw_data,
                    )
                )
                await self._session.flush()
            return True
        except IntegrityError:
            existing = await self._get(vacancy.source, vacancy.external_id)
            if existing is None:
                raise
            await self._apply(existing, vacancy)
            return False

    async def _get(self, source: str, external_id: str) -> Vacancy | None:
        return await self._session.scalar(
            select(Vacancy).where(
                Vacancy.source == source,
                Vacancy.external_id == external_id,
            )
        )

    async def _apply(self, record: Vacancy, data: VacancyData) -> None:
        changed = False
        for field in _MUTABLE_FIELDS:
            if _values_differ(getattr(record, field), getattr(data, field)):
                setattr(record, field, getattr(data, field))
                changed = True
        if changed:
            await self._session.flush()
