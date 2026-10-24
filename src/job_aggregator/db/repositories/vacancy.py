import builtins
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.exc import DataError, DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.models.vacancy import Vacancy
from job_aggregator.schemas.vacancy import VacancyData, VacancyListQuery


class VacancyUpsertResult(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


class VacancySaveError(Exception):
    """Данные вакансии отклонены без повреждения внешней транзакции."""


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
    - новая пара возвращает VacancyUpsertResult.CREATED;
    - изменённая существующая пара возвращает VacancyUpsertResult.UPDATED;
    - идентичные данные возвращают VacancyUpsertResult.UNCHANGED.

    Репозиторий не делает commit()/rollback() переданной сессии — транзакцией
    управляет вызывающий код. При гонке первых вставок одной пары используется
    SAVEPOINT (begin_nested), чтобы поймать IntegrityError, не откатывая
    изменения, уже сделанные вызывающим кодом в той же транзакции.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, vacancy: VacancyData) -> VacancyUpsertResult:
        """Изолирует ошибку данных вакансии, не завершая внешнюю транзакцию.

        VacancySaveError означает, что запись отклонена, но можно сохранять
        следующие элементы. Сбои соединения и постороннего flush пробрасываются.
        """
        # begin_nested() тоже делает flush: посторонние pending-изменения
        # нужно сохранить вне обработки ошибки именно текущей вакансии.
        await self._session.flush()
        try:
            async with self._session.begin_nested():
                return await self._upsert(vacancy)
        except DBAPIError as error:
            if error.connection_invalidated or not self._session.is_active:
                raise
            # asyncpg не все ошибки класса 22 переводит в SQLAlchemy DataError.
            sqlstate = getattr(error.orig, "sqlstate", None)
            data_error = isinstance(error, (DataError, IntegrityError)) or (
                isinstance(sqlstate, str) and sqlstate.startswith(("22", "23"))
            )
            if not data_error:
                raise
            raise VacancySaveError("Данные вакансии отклонены") from error

    async def _upsert(self, vacancy: VacancyData) -> VacancyUpsertResult:
        existing = await self._get(vacancy.source, vacancy.external_id)
        if existing is not None:
            changed = await self._apply(existing, vacancy)
            if changed:
                return VacancyUpsertResult.UPDATED
            return VacancyUpsertResult.UNCHANGED

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
            return VacancyUpsertResult.CREATED

        except IntegrityError:
            existing = await self._get(vacancy.source, vacancy.external_id)
            if existing is None:
                raise
            changed = await self._apply(existing, vacancy)
            if changed:
                return VacancyUpsertResult.UPDATED
            return VacancyUpsertResult.UNCHANGED

    async def get_by_external_id(self, source: str, external_id: str) -> Vacancy | None:
        """Найти вакансию по точной паре без управления транзакцией."""
        return await self._get(source, external_id)

    async def _get(self, source: str, external_id: str) -> Vacancy | None:
        return await self._session.scalar(
            select(Vacancy).where(
                Vacancy.source == source,
                Vacancy.external_id == external_id,
            )
        )

    async def _apply(self, record: Vacancy, data: VacancyData) -> bool:
        changed = False

        for field in _MUTABLE_FIELDS:
            if _values_differ(getattr(record, field), getattr(data, field)):
                setattr(record, field, getattr(data, field))
                changed = True

        if changed:
            await self._session.flush()

        return changed

    async def list(
        self,
        query: VacancyListQuery,
    ) -> tuple[builtins.list[Vacancy], int]:
        """Возвращает страницу вакансий и общее число подходящих под фильтры."""
        conditions = self._filters(query)

        total = await self._session.scalar(
            select(func.count()).select_from(Vacancy).where(*conditions)
        )

        page = await self._session.scalars(
            select(Vacancy)
            .where(*conditions)
            .order_by(
                Vacancy.published_at.desc().nulls_last(),
                Vacancy.id.asc(),
            )
            .limit(query.limit)
            .offset(query.offset)
        )

        return list(page), total or 0

    def _filters(self, query: VacancyListQuery) -> builtins.list[ColumnElement[bool]]:
        """Собирает условия выборки из заданных фильтров."""
        conditions: builtins.list[ColumnElement[bool]] = []

        if query.company is not None:
            conditions.append(Vacancy.company_name.ilike(f"%{query.company}%"))

        if query.area is not None:
            conditions.append(Vacancy.area_name.ilike(f"%{query.area}%"))

        if query.text is not None:
            pattern = f"%{query.text}%"
            conditions.append(
                or_(
                    Vacancy.title.ilike(pattern),
                    Vacancy.description.ilike(pattern),
                )
            )

        if query.salary_from is not None:
            conditions.append(Vacancy.salary_from >= query.salary_from)

        if query.salary_to is not None:
            conditions.append(Vacancy.salary_to <= query.salary_to)

        return conditions
