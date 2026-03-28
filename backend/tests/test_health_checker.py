"""
Тесты collect_system_health: все ок, PreLend down, ShortsProject degraded.
"""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch


def test_prelend_down_on_health_none():
    fake_client = MagicMock()
    fake_client.get_health.return_value = None

    with patch("services.health_checker._get_pl_client", return_value=fake_client):
        from services.health_checker import _collect_prelend

        pl = _collect_prelend()

    assert pl["status"] == "down"
    assert pl["api_available"] is False


def test_shorts_project_degraded_agents_in_error():
    from services import health_checker

    with TemporaryDirectory() as td:
        base = Path(td)
        mem = base / "agent_memory.json"
        mem.write_text(
            json.dumps(
                {
                    "agent_statuses": {
                        "x": {"status": "error"},
                        "y": {"status": "running"},
                    }
                }
            ),
            encoding="utf-8",
        )
        (base / "acc").mkdir()
        (base / "a.json").write_text("{}", encoding="utf-8")

        with patch.object(health_checker.cfg, "SP_AGENT_MEMORY", mem):
            with patch.object(health_checker.cfg, "SP_ACCOUNTS_ROOT", base / "acc"):
                with patch.object(health_checker.cfg, "SP_ANALYTICS_FILE", base / "a.json"):
                    with patch.object(health_checker.cfg, "SHORTS_PROJECT_DIR", base):
                        sp = health_checker._collect_shorts_project()

    assert sp["status"] == "degraded"
    assert "x" in sp["agents_in_error"]


def test_collect_all_prelend_ok_mocked():
    fake_client = MagicMock()
    fake_client.get_health.return_value = {"status": "ok"}
    fake_client.get_metrics.return_value = {"total_clicks": 5, "conversions": 1, "bot_pct": 2.0}

    with TemporaryDirectory() as td:
        base = Path(td)
        mem = base / "m.json"
        mem.write_text('{"agent_statuses": {"a": {"status": "ok"}}}', encoding="utf-8")
        (base / "acc").mkdir()
        (base / "a.json").write_text("{}", encoding="utf-8")

        with patch("services.health_checker._get_pl_client", return_value=fake_client):
            from services import health_checker

            with patch.object(health_checker.cfg, "PL_CLICKS_DB", base / "none.db"):
                with patch.object(health_checker.cfg, "SP_AGENT_MEMORY", mem):
                        with patch.object(health_checker.cfg, "SP_ACCOUNTS_ROOT", base / "acc"):
                            with patch.object(health_checker.cfg, "SP_ANALYTICS_FILE", base / "a.json"):
                                with patch.object(health_checker.cfg, "SHORTS_PROJECT_DIR", base):
                                    with patch.object(health_checker.cfg, "ORC_DB", base / "o.db"):
                                        h = health_checker.collect_system_health()

    assert h["prelend"]["api_available"] is True
    assert h["prelend"]["clicks_24h"] == 5
    assert h["shorts_project"]["status"] == "ok"
