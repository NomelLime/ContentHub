"""tests/test_analytics.py — аналитика: воронка и plan-quality без падений."""
from __future__ import annotations

from tests.conftest import auth_headers


class TestAnalytics:
    def test_funnel_requires_auth(self, client):
        resp = client.get("/api/analytics/funnel?days=7")
        assert resp.status_code == 401

    def test_funnel_ok_for_viewer(self, client, viewer_token):
        resp = client.get(
            "/api/analytics/funnel?days=14",
            headers=auth_headers(viewer_token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("days") == 14
        assert isinstance(data.get("funnel"), list)

    def test_plan_quality_ok_for_viewer(self, client, viewer_token):
        """Раньше падал NameError: cfg не был импортирован в analytics.py."""
        resp = client.get(
            "/api/analytics/plan-quality?limit=5",
            headers=auth_headers(viewer_token),
        )
        assert resp.status_code == 200, resp.text
        assert isinstance(resp.json(), list)
