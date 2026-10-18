from typing import Final

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.models.user import User, UserSettings


class UnsetType:
    """Тип маркера «аргумент не передан» для частичного обновления."""

    def __repr__(self) -> str:
        return "UNSET"


UNSET: Final[UnsetType] = UnsetType()


class UserRepository:
    """Поиск и создание локальных пользователей после OAuth HH.ru.

    Репозиторий делает flush(), но не commit()/rollback(): транзакцией
    управляет вызывающий код.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: int) -> User | None:
        """Возвращает пользователя по id или None, если его нет."""
        return await self._session.get(User, user_id)

    async def _get_by_hh_user_id(self, hh_user_id: str) -> User | None:
        return await self._session.scalar(
            select(User).where(User.hh_user_id == hh_user_id)
        )

    async def get_or_create(self, hh_user_id: str, display_name: str) -> User:
        """Находит пользователя по hh_user_id или создаёт его вместе с настройками.

        При параллельном первом входе одного HH-профиля возвращается один
        пользователь: проигравший гонку ловит IntegrityError внутри savepoint
        и перечитывает созданную другим запросом запись.
        """

        existing = await self._get_by_hh_user_id(hh_user_id)
        if existing is not None:
            return existing

        try:
            async with self._session.begin_nested():
                user = User(hh_user_id=hh_user_id, display_name=display_name)
                self._session.add(user)
                await self._session.flush()

                self._session.add(UserSettings(user_id=user.id))
                await self._session.flush()
            return user
        except IntegrityError:
            existing = await self._get_by_hh_user_id(hh_user_id)
            if existing is None:
                raise
            return existing


class UserSettingsRepository:
    """Чтение и частичное обновление персональных настроек пользователя.

    Изменяющие методы делают flush(), но не commit()/rollback().
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(self, user_id: int) -> UserSettings:
        """Возвращает настройки пользователя или создаёт
        их со значениями по умолчанию.
        """
        existing = await self._session.get(UserSettings, user_id)
        if existing is not None:
            return existing

        try:
            async with self._session.begin_nested():
                settings = UserSettings(user_id=user_id)
                self._session.add(settings)
                await self._session.flush()
            return settings
        except IntegrityError:
            existing = await self._session.get(UserSettings, user_id)
            if existing is None:
                raise
            return existing

    async def update(
        self,
        user_id: int,
        *,
        default_area: str | None | UnsetType = UNSET,
        default_pages_limit: int | UnsetType = UNSET,
    ) -> UserSettings | None:
        """Меняет только переданные настройки; default_area=None очищает регион.

        Возвращает None, если пользователя нет.
        """
        if await self._session.get(User, user_id) is None:
            return None

        settings = await self.get_or_create(user_id)
        if default_area is not UNSET:
            settings.default_area = default_area
        if default_pages_limit is not UNSET:
            settings.default_pages_limit = default_pages_limit
        await self._session.flush()
        return settings
