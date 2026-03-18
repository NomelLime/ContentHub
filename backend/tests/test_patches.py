"""tests/test_patches.py — Тесты endpoints управления патчами."""
from tests.conftest import auth_headers


class TestPatches:
    def test_list_patches_viewer(self, client, viewer_token):
        """Viewer может читать список патчей."""
        resp = client.get("/api/patches", headers=auth_headers(viewer_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_patches_unauthenticated(self, client):
        """Неавторизованный запрос → 401."""
        resp = client.get("/api/patches")
        assert resp.status_code == 401

    def test_approve_patch_requires_operator(self, client, viewer_token):
        """Viewer не может одобрять патчи → 403."""
        resp = client.post("/api/patches/1/approve",
                           headers=auth_headers(viewer_token))
        assert resp.status_code == 403

    def test_reject_patch_requires_operator(self, client, viewer_token):
        """Viewer не может отклонять патчи → 403."""
        resp = client.post("/api/patches/1/reject",
                           headers=auth_headers(viewer_token))
        assert resp.status_code == 403

    def test_approve_nonexistent_patch(self, client, admin_token):
        """Несуществующий патч → 404 или 409."""
        resp = client.post("/api/patches/99999/approve",
                           headers=auth_headers(admin_token))
        assert resp.status_code in (404, 409)

    def test_diff_endpoint_exists(self, client, viewer_token):
        """GET /api/patches/{id}/diff → 404 для несуществующего (не 500)."""
        resp = client.get("/api/patches/99999/diff",
                          headers=auth_headers(viewer_token))
        assert resp.status_code == 404
