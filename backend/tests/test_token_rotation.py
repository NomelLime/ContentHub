"""
Дополнение к tests/test_auth.py — тесты token rotation (FIX#6).
Добавить в класс TestRefresh.
"""


class TestRefreshTokenRotation:
    """[FIX#6] Проверяем что refresh token ротируется при каждом /refresh."""

    def test_refresh_rotates_cookie(self, client):
        """После /refresh в cookie — новый токен, старый инвалидирован."""
        # Login
        login_resp = client.post("/api/auth/login", json={
            "username": "testadmin",
            "password": "testpass123",
        })
        assert login_resp.status_code == 200
        old_cookie = client.cookies.get("refresh_token")
        assert old_cookie is not None

        # Первый refresh — получаем новый токен
        r1 = client.post("/api/auth/refresh")
        assert r1.status_code == 200
        new_cookie = client.cookies.get("refresh_token")
        assert new_cookie is not None
        # Cookie должен измениться (rotation)
        assert new_cookie != old_cookie

        # Второй refresh с новым cookie — должен работать
        r2 = client.post("/api/auth/refresh")
        assert r2.status_code == 200
        assert "access_token" in r2.json()

    def test_old_refresh_token_invalid_after_rotation(self, client):
        """После rotation старый refresh token не должен работать (replay protection)."""
        # Login
        login_resp = client.post("/api/auth/login", json={
            "username": "testadmin",
            "password": "testpass123",
        })
        assert login_resp.status_code == 200
        old_cookie = client.cookies.get("refresh_token")

        # Делаем refresh — старый токен ротируется
        r1 = client.post("/api/auth/refresh")
        assert r1.status_code == 200

        # Подставляем старый cookie вручную
        client.cookies.set("refresh_token", old_cookie, path="/api/auth")
        r2 = client.post("/api/auth/refresh")
        # Старый токен больше не существует в БД → 401
        assert r2.status_code == 401

    def test_refresh_returns_role(self, client):
        """Ответ /refresh содержит role для FIX#3 (in-memory role restoration)."""
        client.post("/api/auth/login", json={
            "username": "testadmin",
            "password": "testpass123",
        })
        resp = client.post("/api/auth/refresh")
        assert resp.status_code == 200
        data = resp.json()
        assert "role" in data
        assert data["role"] == "admin"

    def test_logout_then_refresh_returns_401(self, client):
        """После logout старый refresh token инвалидирован."""
        client.post("/api/auth/login", json={
            "username": "testadmin",
            "password": "testpass123",
        })
        # Logout удаляет сессию из БД
        logout_resp = client.post("/api/auth/logout")
        assert logout_resp.status_code == 200

        # Refresh после logout → 401 (сессия удалена)
        refresh_resp = client.post("/api/auth/refresh")
        assert refresh_resp.status_code == 401
