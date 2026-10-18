import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.errors import ApiError, forbidden, unauthorized
from app.core.ids import utcnow
from app.db import get_db
from app.models import AuthSession, User

COOKIE_NAME = "pm_session"
SESSION_TTL = timedelta(days=7)
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "provamusteri"

_hasher = PasswordHasher()
# Sabit zamanlı karşılaştırma için: kullanıcı yoksa da hash doğrulaması yapılır.
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, InvalidHashError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_auth_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(token_hash=_token_hash(token), user_id=user.id, expires_at=utcnow() + SESSION_TTL))
    db.commit()
    return token


def delete_auth_session(db: Session, token: str | None) -> None:
    if token:
        db.query(AuthSession).filter_by(token_hash=_token_hash(token)).delete()
        db.commit()


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise unauthorized()
    row = db.get(AuthSession, _token_hash(token))
    if row is None or row.expires_at.replace(tzinfo=utcnow().tzinfo) < utcnow():
        raise unauthorized()
    user = db.get(User, row.user_id)
    if user is None or not user.active:
        raise unauthorized()
    if user.must_change_password and request.url.path not in {
        "/api/v1/me", "/api/v1/auth/change-password", "/api/v1/auth/logout",
    }:
        raise ApiError(403, "password_change_required", "Devam etmek için geçici şifrenizi yenileyin.")
    return user


def require_manager(user: User = Depends(current_user)) -> User:
    if user.role != "manager":
        raise forbidden()
    return user


class LoginRateLimiter:
    """Süreç içi basit sınır: e-posta başına dakikada 5 başarısız deneme."""

    def __init__(self, limit: int = 5, window_s: float = 60.0):
        self.limit, self.window_s = limit, window_s
        self._fails: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        q, now = self._fails[key], time.monotonic()
        while q and now - q[0] > self.window_s:
            q.popleft()
        if len(q) >= self.limit:
            raise ApiError(429, "rate_limited", "Çok fazla deneme. Lütfen bir dakika sonra tekrar deneyin.")

    def fail(self, key: str) -> None:
        self._fails[key].append(time.monotonic())

    def reset(self, key: str) -> None:
        self._fails.pop(key, None)


login_limiter = LoginRateLimiter()
