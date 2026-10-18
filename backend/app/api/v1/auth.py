from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app import schemas
from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import (
    COOKIE_NAME,
    SESSION_TTL,
    create_auth_session,
    current_user,
    delete_auth_session,
    hash_password,
    login_limiter,
    verify_password,
)
from app.db import get_db
from app.models import AuthSession, Organization, User

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+$")
    password: str = Field(min_length=1, max_length=200)


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)
    confirm_password: str = Field(min_length=8, max_length=200)


@router.post("/auth/change-password")
def change_password(body: ChangePasswordRequest, response: Response,
                    user: User = Depends(current_user), db: Session = Depends(get_db)):
    key = f"password:{user.id}"
    login_limiter.check(key)
    if not verify_password(user.password_hash, body.current_password):
        login_limiter.fail(key)
        raise ApiError(400, "invalid_current_password", "Mevcut veya geçici şifreniz hatalı.")
    if body.new_password != body.confirm_password:
        raise ApiError(422, "validation_error", "Yeni şifreler eşleşmiyor.",
                       {"fields": {"confirm_password": "Yeni şifreler eşleşmiyor."}})
    if body.new_password == body.current_password or not body.new_password.strip():
        raise ApiError(422, "validation_error", "Önceki şifrenizden farklı, en az 8 karakterli bir şifre seçin.",
                       {"fields": {"new_password": "Şifre önceki şifreyle aynı veya boş olamaz."}})
    changed = db.execute(update(User).where(User.id == user.id, User.password_hash == user.password_hash)
                         .values(password_hash=hash_password(body.new_password), must_change_password=False))
    if changed.rowcount != 1:
        db.rollback()
        raise ApiError(409, "password_changed", "Şifreniz başka bir oturumda değişti. Yeniden giriş yapın.")
    db.query(AuthSession).filter_by(user_id=user.id).delete()
    # Şifre, eski oturumların iptali ve yeni oturum tek transaction içinde yazılır.
    token = create_auth_session(db, user)
    login_limiter.reset(key)
    db.refresh(user)
    response.set_cookie(COOKIE_NAME, token, max_age=int(SESSION_TTL.total_seconds()), httponly=True,
                        samesite="lax", secure=get_settings().cookie_secure, path="/")
    response.headers["Cache-Control"] = "no-store"
    return schemas.me(user, db.get(Organization, user.org_id))


@router.post("/auth/login")
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    key = body.email.strip().lower()
    login_limiter.check(key)
    user = db.query(User).filter(func.lower(User.email) == key).one_or_none()
    if not verify_password(user.password_hash if user else None, body.password) or not user.active:
        login_limiter.fail(key)
        raise ApiError(401, "invalid_credentials", "E-posta veya şifre hatalı.")
    login_limiter.reset(key)
    token = create_auth_session(db, user)
    response.set_cookie(COOKIE_NAME, token, max_age=int(SESSION_TTL.total_seconds()), httponly=True,
                        samesite="lax", secure=get_settings().cookie_secure, path="/")
    return schemas.me(user, db.get(Organization, user.org_id))


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, _: User = Depends(current_user), db: Session = Depends(get_db)):
    delete_auth_session(db, request.cookies.get(COOKIE_NAME))
    response.delete_cookie(COOKIE_NAME, path="/")
    response.status_code = 204
    return response


@router.get("/me")
def get_me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return schemas.me(user, db.get(Organization, user.org_id))
