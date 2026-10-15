from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.models.auth_session import OAuthState, UserSession

_OAUTH_STATE_TTL = timedelta(minutes=10)
_SESSION_TTL = timedelta(days=7)
_SESSION_RENEWAL_WINDOW = timedelta(days=1)


@dataclass(frozen=True, slots=True)
class SessionAuthentication:
    """Результат проверки cookie-сессии и возможный token для её ротации."""

    user_id: int
    replacement_token: str | None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _token_hash(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class AuthSessionService:
    """Создаёт и проверяет одноразовые OAuth state и серверные сессии.

    Сервис только flush-ит переданную сессию SQLAlchemy: границу транзакции
    определяет route handler или вызывающий use case.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._session = session
        self._clock = clock

    async def create_oauth_state(self) -> str:
        """Создать одноразовый state и сохранить только его hash."""
        state = token_urlsafe(32)
        self._session.add(
            OAuthState(
                state_hash=_token_hash(state),
                expires_at=self._now() + _OAUTH_STATE_TTL,
            )
        )
        await self._session.flush()
        return state

    async def consume_oauth_state(self, state: str) -> bool:
        """Одноразово подтвердить ещё не истёкший OAuth state."""
        now = self._now()
        oauth_state = await self._session.scalar(
            select(OAuthState)
            .where(OAuthState.state_hash == _token_hash(state))
            .with_for_update()
        )
        if (
            oauth_state is None
            or oauth_state.consumed_at is not None
            or _as_utc(oauth_state.expires_at) <= now
        ):
            return False

        oauth_state.consumed_at = now
        await self._session.flush()
        return True

    async def create_session(self, user_id: int) -> str:
        """Создать новую серверную сессию пользователя на семь дней."""
        token = token_urlsafe(32)
        await self._create_session_record(user_id, token, self._now())
        return token

    async def get_user_id(self, session_token: str) -> int | None:
        """Вернуть владельца действующей сессии без её продления."""
        session = await self._get_active_session(session_token, self._now())
        return None if session is None else session.user_id

    async def authenticate_session(
        self, session_token: str
    ) -> SessionAuthentication | None:
        """Проверить сессию и вернуть replacement token при rolling-продлении."""
        now = self._now()
        session = await self._get_active_session(session_token, now, lock=True)
        if session is None:
            return None

        replacement_token = None
        if _as_utc(session.expires_at) - now <= _SESSION_RENEWAL_WINDOW:
            replacement_token = token_urlsafe(32)
            session.revoked_at = now
            await self._create_session_record(session.user_id, replacement_token, now)
        return SessionAuthentication(
            user_id=session.user_id,
            replacement_token=replacement_token,
        )

    async def revoke_session(self, session_token: str) -> None:
        """Отозвать только сессию, соответствующую переданному token."""
        now = self._now()
        session = await self._get_active_session(session_token, now)
        if session is None:
            return
        session.revoked_at = now
        await self._session.flush()

    async def _create_session_record(
        self, user_id: int, token: str, now: datetime
    ) -> None:
        self._session.add(
            UserSession(
                user_id=user_id,
                token_hash=_token_hash(token),
                expires_at=now + _SESSION_TTL,
            )
        )
        await self._session.flush()

    async def _get_active_session(
        self,
        session_token: str,
        now: datetime,
        *,
        lock: bool = False,
    ) -> UserSession | None:
        statement = select(UserSession).where(
            UserSession.token_hash == _token_hash(session_token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
        if lock:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return now.astimezone(UTC)
