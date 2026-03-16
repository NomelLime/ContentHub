"""
services/auth.py — JWT аутентификация и управление пользователями.

Roles:
  admin    — полный доступ (конфиги, патчи, пользователи)
  operator — конфиги и патчи, без управления пользователями
  viewer   — только чтение
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import config as cfg
from db.connection import get_db

bearer_scheme = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"


# ──────────────────────────────────────────────────────────────────────────────
# Пароли
# ──────────────────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


# ──────────────────────────────────────────────────────────────────────────────
# JWT токены
# ──────────────────────────────────────────────────────────────────────────────

def create_access_token(user_id: int, username: str, role: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=cfg.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub":      str(user_id),
        "username": username,
        "role":     role,
        "exp":      exp,
        "type":     "access",
    }
    return jwt.encode(payload, cfg.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token() -> tuple[str, str]:
    """Возвращает (raw_token, hashed_token)."""
    raw   = secrets.token_hex(32)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, cfg.SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Зависимости FastAPI
# ──────────────────────────────────────────────────────────────────────────────

def _get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Не авторизован")

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Токен недействителен или истёк")

    return {
        "id":       int(payload["sub"]),
        "username": payload["username"],
        "role":     payload["role"],
    }


def require_viewer(user: dict = Depends(_get_current_user)) -> dict:
    """Минимальный доступ — любой авторизованный пользователь."""
    return user


def require_operator(user: dict = Depends(_get_current_user)) -> dict:
    if user["role"] not in ("operator", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Требуется роль operator или admin")
    return user


def require_admin(user: dict = Depends(_get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Требуется роль admin")
    return user


# ──────────────────────────────────────────────────────────────────────────────
# Вспомогательные функции
# ──────────────────────────────────────────────────────────────────────────────

def get_user_by_username(username: str) -> Optional[dict]:
    with get_db() as db:
        row = db.execute(
            "SELECT id, username, password_hash, role FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        return dict(row) if row else None


def log_audit(user: dict, action: str, project: Optional[str], detail: dict) -> None:
    """Записывает действие в audit_log."""
    with get_db() as db:
        db.execute(
            "INSERT INTO audit_log (user_id, username, action, project, detail_json) VALUES (?,?,?,?,?)",
            (user["id"], user["username"], action, project, json.dumps(detail, ensure_ascii=False)),
        )
        db.commit()
