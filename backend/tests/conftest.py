"""
tests/conftest.py — Общие фикстуры для тестов ContentHub.
Каждый тест получает изолированную in-memory/temp БД.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Задаём env ДО импорта config/main — иначе EnvironmentError на GITHUB_ROOT
os.environ.setdefault("GITHUB_ROOT", "/tmp/test-contenthub-projects")
os.environ.setdefault("CONTENTHUB_SECRET_KEY", "test-secret-key-for-tests-only-32ch!")

# Добавляем backend/ в sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from main import app                        # noqa: E402
from db.connection import init_db, get_db  # noqa: E402
from services.auth import hash_password    # noqa: E402


@pytest.fixture(scope="function")
def client(tmp_path, monkeypatch):
    """Создаёт тестовый FastAPI клиент с изолированной SQLite БД."""
    import config as cfg
    monkeypatch.setattr(cfg, "CONTENTHUB_DB", tmp_path / "test.db")

    init_db()

    # Создаём тестовых пользователей
    with get_db() as db:
        db.execute(
            "INSERT OR REPLACE INTO users (username, password_hash, role) VALUES (?,?,?)",
            ("testadmin", hash_password("testpass123"), "admin"),
        )
        db.execute(
            "INSERT OR REPLACE INTO users (username, password_hash, role) VALUES (?,?,?)",
            ("testviewer", hash_password("viewerpass"), "viewer"),
        )
        db.execute(
            "INSERT OR REPLACE INTO users (username, password_hash, role) VALUES (?,?,?)",
            ("testoperator", hash_password("operatorpass"), "operator"),
        )
        db.commit()

    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_token(client) -> str:
    """Возвращает access_token для admin."""
    resp = client.post("/api/auth/login", json={
        "username": "testadmin",
        "password": "testpass123",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
def viewer_token(client) -> str:
    """Возвращает access_token для viewer."""
    resp = client.post("/api/auth/login", json={
        "username": "testviewer",
        "password": "viewerpass",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
def operator_token(client) -> str:
    """Возвращает access_token для operator."""
    resp = client.post("/api/auth/login", json={
        "username": "testoperator",
        "password": "operatorpass",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def reset_rate_limiter(client):
    """Очищает login_failures в SQLite между тестами (rate limit). Зависит от client — init_db уже выполнен."""
    from db.connection import get_db as _get_db

    with _get_db() as db:
        db.execute("DELETE FROM login_failures")
        db.commit()
    yield
    with _get_db() as db:
        db.execute("DELETE FROM login_failures")
        db.commit()
