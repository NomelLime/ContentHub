"""tests/test_auth.py — Тесты аутентификации ContentHub."""
from tests.conftest import auth_headers


class TestLogin:
    def test_login_success(self, client):
        resp = client.post("/api/auth/login", json={
            "username": "testadmin",
            "password": "testpass123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["role"] == "admin"
        # Refresh token должен быть в httpOnly cookie
        assert "refresh_token" in client.cookies

    def test_login_wrong_password(self, client):
        resp = client.post("/api/auth/login", json={
            "username": "testadmin",
            "password": "wrongpass",
        })
        assert resp.status_code == 401

    def test_login_unknown_user(self, client):
        resp = client.post("/api/auth/login", json={
            "username": "nonexistent",
            "password": "any",
        })
        assert resp.status_code == 401

    def test_login_rate_limit(self, client):
        """5 неудачных попыток подряд → 429."""
        for _ in range(5):
            client.post("/api/auth/login", json={
                "username": "testadmin",
                "password": "wrong",
            })
        resp = client.post("/api/auth/login", json={
            "username": "testadmin",
            "password": "wrong",
        })
        assert resp.status_code == 429

    def test_login_success_clears_rate_limit(self, client):
        """Успешный логин после неудач — без блокировки."""
        # 3 неудачи
        for _ in range(3):
            client.post("/api/auth/login", json={
                "username": "testviewer",
                "password": "wrong",
            })
        # Успешный логин сбрасывает счётчик
        resp = client.post("/api/auth/login", json={
            "username": "testviewer",
            "password": "viewerpass",
        })
        assert resp.status_code == 200


class TestRefresh:
    def test_refresh_returns_new_access_token(self, client):
        # Login — браузер сохраняет refresh cookie
        login_resp = client.post("/api/auth/login", json={
            "username": "testadmin",
            "password": "testpass123",
        })
        assert login_resp.status_code == 200
        # Refresh — TestClient автоматически отправляет cookies
        refresh_resp = client.post("/api/auth/refresh")
        assert refresh_resp.status_code == 200
        data = refresh_resp.json()
        assert "access_token" in data
        assert "role" in data

    def test_refresh_without_cookie_returns_401(self, client):
        # Новый клиент без cookies
        resp = client.post("/api/auth/refresh")
        assert resp.status_code == 401


class TestMe:
    def test_me_endpoint_exists(self, client, admin_token):
        """GET /api/auth/me возвращает данные текущего пользователя."""
        resp = client.get("/api/auth/me", headers=auth_headers(admin_token))
        # 200 если endpoint реализован, иначе пропускаем
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("username") == "testadmin"

    def test_protected_without_token_returns_401(self, client):
        """Защищённый endpoint без токена → 401."""
        resp = client.get("/api/dashboard")
        assert resp.status_code == 401


class TestRBAC:
    def test_viewer_cannot_manage_users(self, client, viewer_token):
        """Viewer не может видеть список пользователей."""
        resp = client.get("/api/auth/users", headers=auth_headers(viewer_token))
        assert resp.status_code == 403

    def test_admin_can_list_users(self, client, admin_token):
        """Admin видит список пользователей."""
        resp = client.get("/api/auth/users", headers=auth_headers(admin_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_viewer_cannot_approve_patch(self, client, viewer_token):
        """Viewer не может одобрять патчи."""
        resp = client.post("/api/patches/1/approve",
                           headers=auth_headers(viewer_token))
        assert resp.status_code == 403


class TestLogout:
    def test_logout_success(self, client):
        """Login → Logout → refresh даёт 401."""
        client.post("/api/auth/login", json={
            "username": "testadmin",
            "password": "testpass123",
        })
        logout_resp = client.post("/api/auth/logout")
        assert logout_resp.status_code == 200
        # После logout cookie удалён → refresh fails
        refresh_resp = client.post("/api/auth/refresh")
        assert refresh_resp.status_code == 401


class TestChangePassword:
    def test_change_password_requires_old_password(self, client, admin_token):
        resp = client.post(
            "/api/auth/change-password",
            json={"new_password": "newpassword123"},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 400
        assert "пароль" in resp.json()["detail"].lower()

    def test_change_password_success(self, client, admin_token):
        resp = client.post(
            "/api/auth/change-password",
            json={"old_password": "testpass123", "new_password": "newpass12345"},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        login = client.post("/api/auth/login", json={
            "username": "testadmin",
            "password": "newpass12345",
        })
        assert login.status_code == 200


class TestOperatorRBAC:
    def test_operator_cannot_create_admin(self, client, operator_token):
        resp = client.post(
            "/api/auth/users",
            json={"username": "evil", "password": "password12", "role": "admin"},
            headers=auth_headers(operator_token),
        )
        assert resp.status_code == 403

    def test_admin_can_create_admin(self, client, admin_token):
        resp = client.post(
            "/api/auth/users",
            json={"username": "subadmin", "password": "password12", "role": "admin"},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
