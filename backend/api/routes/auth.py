"""
api/routes/auth.py — аутентификация.

Хранение токенов:
  access_token  — возвращается в JSON (фронт хранит в JS-переменной, не localStorage)
  refresh_token — httpOnly cookie (JS не имеет доступа, CSRF-защита через samesite=lax)

POST /api/auth/login          → {access_token, role} + устанавливает cookie
POST /api/auth/refresh        → {access_token, role} — читает cookie, не JSON body
POST /api/auth/logout         → удаляет cookie + сессию из БД
POST /api/auth/change-password → смена пароля (admin или себе)

GET  /api/auth/users          → список пользователей (только admin)
POST /api/auth/users          → создать пользователя (только admin)
PUT  /api/auth/users/{id}     → изменить роль (только admin)
"""

from __future__ import annotations

import hashlib
import time as _time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from db.connection import get_db
from services.auth import (
    create_access_token,
    create_refresh_token,
    get_user_by_username,
    hash_password,
    require_admin,
    require_viewer,
    verify_password,
)
import config as cfg

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── Rate limiting для /login ───────────────────────────────────────────────────
# In-memory: сбрасывается при рестарте — приемлемо для localhost-деплоя.
# Защита по username: предотвращает перебор пароля конкретного пользователя.

_MAX_LOGIN_ATTEMPTS = 5
_LOGIN_WINDOW_SEC   = 60
_login_failures: dict[str, list[float]] = defaultdict(list)


def _check_login_rate(username: str) -> None:
    """Проверяет rate limit. Бросает HTTPException(429) при превышении."""
    now = _time.time()
    _login_failures[username] = [
        t for t in _login_failures[username] if now - t < _LOGIN_WINDOW_SEC
    ]
    if len(_login_failures[username]) >= _MAX_LOGIN_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Слишком много неудачных попыток входа. "
                f"Подождите {_LOGIN_WINDOW_SEC} секунд."
            ),
        )


def _record_login_failure(username: str) -> None:
    _login_failures[username].append(_time.time())


def _clear_login_failures(username: str) -> None:
    _login_failures.pop(username, None)


# ── Эндпоинты ─────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginRequest):
    """
    Аутентификация. Возвращает access_token в JSON.
    Refresh token устанавливается как httpOnly cookie (JS не видит).
    """
    _check_login_rate(body.username)

    user = get_user_by_username(body.username)
    if not user or not verify_password(body.password, user["password_hash"]):
        _record_login_failure(body.username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")

    if user["password_hash"] == "__CHANGE_ME__":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Установите пароль администратора: POST /api/auth/change-password",
        )

    _clear_login_failures(body.username)

    access_token              = create_access_token(user["id"], user["username"], user["role"])
    raw_refresh, hashed_refresh = create_refresh_token()

    exp = datetime.now(timezone.utc) + timedelta(days=cfg.REFRESH_TOKEN_EXPIRE_DAYS)
    with get_db() as db:
        db.execute(
            "INSERT INTO sessions (user_id, token_hash, expires_at) VALUES (?,?,?)",
            (user["id"], hashed_refresh, exp.isoformat()),
        )
        db.execute(
            "UPDATE users SET last_login=? WHERE id=?",
            (datetime.now(timezone.utc).isoformat(), user["id"]),
        )
        db.commit()

    # access_token — в JSON (фронт хранит в JS-переменной)
    # refresh_token — в httpOnly cookie (браузер отправляет автоматически)
    response = JSONResponse(content={
        "access_token": access_token,
        "token_type":   "bearer",
        "role":         user["role"],
    })
    response.set_cookie(
        key      = "refresh_token",
        value    = raw_refresh,
        httponly = True,                                     # JS не видит
        secure   = cfg.COOKIE_SECURE,                       # True для HTTPS
        samesite = "lax",                                    # защита от CSRF
        max_age  = cfg.REFRESH_TOKEN_EXPIRE_DAYS * 86_400,
        path     = "/api/auth",                              # cookie только для auth endpoints
    )
    return response


@router.post("/refresh")
def refresh(
    response: Response,
    refresh_token: Optional[str] = Cookie(None, alias="refresh_token"),
):
    """
    Обновляет access_token. Refresh token берётся из httpOnly cookie — не из тела запроса.
    Вызывается автоматически фронтендом при истёкшем access_token или при загрузке страницы.
    """
    if not refresh_token:
        raise HTTPException(401, detail="Refresh cookie отсутствует")

    hashed = hashlib.sha256(refresh_token.encode()).hexdigest()
    with get_db() as db:
        row = db.execute(
            """SELECT s.user_id, s.expires_at, u.username, u.role
               FROM sessions s JOIN users u ON s.user_id = u.id
               WHERE s.token_hash = ?""",
            (hashed,),
        ).fetchone()

    if not row:
        raise HTTPException(401, detail="Refresh token не найден")

    exp = datetime.fromisoformat(row["expires_at"])
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        raise HTTPException(401, detail="Refresh token истёк")

    access_token = create_access_token(row["user_id"], row["username"], row["role"])
    return {"access_token": access_token, "token_type": "bearer", "role": row["role"]}


@router.post("/logout")
def logout(
    response: Response,
    refresh_token: Optional[str] = Cookie(None, alias="refresh_token"),
):
    """Удаляет сессию из БД и очищает httpOnly cookie."""
    if refresh_token:
        hashed = hashlib.sha256(refresh_token.encode()).hexdigest()
        with get_db() as db:
            db.execute("DELETE FROM sessions WHERE token_hash = ?", (hashed,))
            db.commit()

    response.delete_cookie(
        key      = "refresh_token",
        path     = "/api/auth",
        httponly = True,
        samesite = "lax",
    )
    return {"success": True}


class ChangePasswordRequest(BaseModel):
    username:     str
    new_password: str
    old_password: Optional[str] = None


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    user: Annotated[dict, Depends(require_viewer)],
):
    target = get_user_by_username(body.username)
    if not target:
        raise HTTPException(404, detail="Пользователь не найден")

    if user["role"] != "admin" and user["username"] != body.username:
        raise HTTPException(403, detail="Нет прав менять чужой пароль")

    if target["password_hash"] != "__CHANGE_ME__" and user["role"] != "admin":
        if not body.old_password or not verify_password(body.old_password, target["password_hash"]):
            raise HTTPException(400, detail="Неверный текущий пароль")

    new_hash = hash_password(body.new_password)
    with get_db() as db:
        db.execute("UPDATE users SET password_hash=? WHERE username=?", (new_hash, body.username))
        db.commit()
    return {"success": True}


# ── Управление пользователями (только admin) ──────────────────────────────────

@router.get("/users")
def list_users(user: Annotated[dict, Depends(require_admin)]):
    with get_db() as db:
        rows = db.execute(
            "SELECT id, username, role, created_at, last_login FROM users"
        ).fetchall()
    return [dict(r) for r in rows]


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role:     str = "viewer"


@router.post("/users", status_code=201)
def create_user(
    body: CreateUserRequest,
    user: Annotated[dict, Depends(require_admin)],
):
    if body.role not in ("admin", "operator", "viewer"):
        raise HTTPException(400, detail="Роль должна быть: admin, operator, viewer")
    with get_db() as db:
        try:
            db.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
                (body.username, hash_password(body.password), body.role),
            )
            db.commit()
        except Exception:
            raise HTTPException(409, detail=f"Пользователь '{body.username}' уже существует")
    return {"success": True, "username": body.username, "role": body.role}


class UpdateUserRequest(BaseModel):
    role: str


@router.put("/users/{user_id}")
def update_user(
    user_id: int,
    body: UpdateUserRequest,
    current_user: Annotated[dict, Depends(require_admin)],
):
    if body.role not in ("admin", "operator", "viewer"):
        raise HTTPException(400, detail="Роль должна быть: admin, operator, viewer")
    with get_db() as db:
        cur = db.execute("UPDATE users SET role=? WHERE id=?", (body.role, user_id))
        db.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, detail="Пользователь не найден")
    return {"success": True, "user_id": user_id, "new_role": body.role}
