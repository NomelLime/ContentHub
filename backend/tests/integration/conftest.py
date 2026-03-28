"""
Папка integration/ — живые HTTP-тесты без поднятия TestClient(main).

Переопределяет autouse reset_rate_limiter из ../conftest.py (иначе каждый тест
тянул client → lifespan ContentHub и ломал импорт integrations).
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    yield
