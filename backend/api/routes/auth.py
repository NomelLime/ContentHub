"""
api/routes/auth.py — Аутентификация ContentHub.

[FIX#6] Token rotation при /refresh:
    Старая сессия удаляется, создаётся новая с новым токеном.
    Новый refresh_token устанавливается в cookie.
    Защита от replay-атак: украденный старый token после rotation становится недействительным.

[FIX#12] Pydantic response_model для всех endpoints.
"""

from __future__ import annotations

import collections
import hashlib
import time as _time
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import config as cfg
from db.connection import get_db
from services.auth import (
    create_access_token,
    create_refresh_token,
    get_user_by_username,
    hash_password,
    log_audit,
    require_operator,
    require_viewer,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ── Pydantic модели ────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str
    role:         str


class UserInfo(BaseModel):
    id:       int
    username: str
    role:     str
    last_login: Optional[str] = None


class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str = "viewer"


class UserRoleUpdateRequest(BaseModel):
    role: str


class SuccessResponse(BaseModel):
    success: bool
    message: str = ""


# ── Rate limiting ─────────────────────────────────────────────────────────────

_login_failures: dict[str, list[float]] = collections.defaultdict(list)
_MAX_LOGIN_ATTEMPTS = 5
_LOGIN_WINDOW_SEC   = 60


def _check_login_rate(username: str) -> None:
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

@router.get("/me", response_model=UserInfo)
def me(user: Annotated[dict, Depends(require_viewer)]) -> dict:
    """Возвращает данные текущего авторизованного пользователя."""
    return {"id": user["id"], "username": user["username"], "role": user["role"]}


@router.post("/login", response_model=TokenResponse)
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

    access_token                = create_access_token(user["id"], user["username"], user["role"])
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

    response = JSONResponse(content={
        "access_token": access_token,
        "token_type":   "bearer",
        "role":         user["role"],
    })
    response.set_cookie(
        key      = "refresh_token",
        value    = raw_refresh,
        httponly = True,
        secure   = cfg.COOKIE_SECURE,
        samesite = "lax",
        max_age  = cfg.REFRESH_TOKEN_EXPIRE_DAYS * 86_400,
        path     = "/api/auth",
    )
    return response


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    response: Response,
    refresh_token: Optional[str] = Cookie(None, alias="refresh_token"),
):
    """
    Обновляет access_token. Refresh token берётся из httpOnly cookie.

    [FIX#6] Token rotation:
        - Старая сессия удаляется (replay attack защита)
        - Создаётся новая сессия с новым refresh_token
        - Новый token устанавливается в cookie
        - Украденный старый token становится недействительным
    """
    if not refresh_token:
        raise HTTPException(401, detail="Refresh cookie отсутствует")

    old_hashed = hashlib.sha256(refresh_token.encode()).hexdigest()

    with get_db() as db:
        row = db.execute(
            """SELECT s.id, s.user_id, s.expires_at, u.username, u.role
               FROM sessions s JOIN users u ON s.user_id = u.id
               WHERE s.token_hash = ?""",
            (old_hashed,),
        ).fetchone()

    if not row:
        raise HTTPException(401, detail="Refresh token не найден")

    exp = datetime.fromisoformat(row["expires_at"])
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)

    if exp < datetime.now(timezone.utc):
        # Удаляем истёкшую сессию
        with get_db() as db:
            db.execute("DELETE FROM sessions WHERE id = ?", (row["id"],))
            db.commit()
        raise HTTPException(401, detail="Refresh token истёк")

    # [FIX#6] Token rotation: удаляем старую сессию, создаём новую
    new_raw, new_hashed = create_refresh_token()
    new_exp = datetime.now(timezone.utc) + timedelta(days=cfg.REFRESH_TOKEN_EXPIRE_DAYS)

    with get_db() as db:
        db.execute("DELETE FROM sessions WHERE id = ?", (row["id"],))
        db.execute(
            "INSERT INTO sessions (user_id, token_hash, expires_at) VALUES (?,?,?)",
            (row["user_id"], new_hashed, new_exp.isoformat()),
        )
        db.commit()

    access_token = create_access_token(row["user_id"], row["username"], row["role"])

    resp = JSONResponse(content={
        "access_token": access_token,
        "token_type":   "bearer",
        "role":         row["role"],
    })
    # [FIX#6] Устанавливаем новый refresh_token в cookie
    resp.set_cookie(
        key      = "refresh_token",
        value    = new_raw,
        httponly = True,
        secure   = cfg.COOKIE_SECURE,
        samesite = "lax",
        max_age  = cfg.REFRESH_TOKEN_EXPIRE_DAYS * 86_400,
        path     = "/api/auth",
    )
    return resp


@router.post("/logout", response_model=SuccessResponse)
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
    response.delete_cookie("refresh_token", path="/api/auth")
    return {"success": True, "message": "Выход выполнен"}


@router.get("/users", response_model=list[UserInfo])
def list_users(user: Annotated[dict, Depends(require_operator)]):
    """Список всех пользователей (admin/operator)."""
    with get_db() as db:
        rows = db.execute("SELECT id, username, role, last_login FROM users ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@router.post("/users", response_model=SuccessResponse)
def create_user(
    body: UserCreateRequest,
    user: Annotated[dict, Depends(require_operator)],
):
    """Создаёт нового пользователя (admin/operator)."""
    allowed_roles = {"viewer", "operator", "admin"}
    if body.role not in allowed_roles:
        raise HTTPException(400, detail=f"Недопустимая роль: {body.role}")
    if len(body.password) < 8:
        raise HTTPException(400, detail="Пароль должен быть не менее 8 символов")

    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM users WHERE username = ?",
            (body.username,),
        ).fetchone()
        if existing:
            raise HTTPException(409, detail="Пользователь с таким логином уже существует")

        db.execute(
            "INSERT INTO users (username, password_hash, role, last_login) VALUES (?,?,?,NULL)",
            (body.username, hash_password(body.password), body.role),
        )
        db.commit()

    log_audit(user, "user_create", "Auth", {"username": body.username, "role": body.role})
    return {"success": True, "message": "Пользователь создан"}


@router.put("/users/{user_id}/role", response_model=SuccessResponse)
def update_user_role(
    user_id: int,
    body: UserRoleUpdateRequest,
    user: Annotated[dict, Depends(require_operator)],
):
    """Меняет роль пользователя (admin/operator)."""
    allowed_roles = {"viewer", "operator", "admin"}
    if body.role not in allowed_roles:
        raise HTTPException(400, detail=f"Недопустимая роль: {body.role}")

    with get_db() as db:
        target = db.execute("SELECT id, username, role FROM users WHERE id = ?", (user_id,)).fetchone()
        if not target:
            raise HTTPException(404, detail="Пользователь не найден")

        db.execute("UPDATE users SET role = ? WHERE id = ?", (body.role, user_id))
        db.commit()

    log_audit(
        user,
        "user_role_update",
        "Auth",
        {"user_id": user_id, "username": target["username"], "old_role": target["role"], "new_role": body.role},
    )
    return {"success": True, "message": "Роль обновлена"}


@router.post("/change-password", response_model=SuccessResponse)
def change_password(
    body: dict,
    user: Annotated[dict, Depends(require_viewer)],
):
    """Смена пароля (любой авторизованный пользователь — своего)."""
    from services.auth import hash_password
    new_pwd = body.get("new_password", "")
    if len(new_pwd) < 8:
        raise HTTPException(400, detail="Пароль должен быть не менее 8 символов")
    with get_db() as db:
        db.execute(
            "UPDATE users SET password_hash=? WHERE id=?",
            (hash_password(new_pwd), user["id"]),
        )
        db.commit()
    log_audit(user, "password_change", None, {})
    return {"success": True, "message": "Пароль изменён"}
