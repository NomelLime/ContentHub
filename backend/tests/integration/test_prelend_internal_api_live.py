"""
Живые проверки PreLend Internal API (HTTP к PL_INTERNAL_API_URL).

Запуск (PowerShell):
    cd ContentHub/backend
    $env:PL_INTERNAL_API_INTEGRATION="1"
    python -m pytest tests/integration/test_prelend_internal_api_live.py -v

Опционально PUT (нужна запись в config/ на VPS, пользователь www-data):
    $env:PL_INTERNAL_API_LIVE_WRITE="1"

Переменные: PL_INTERNAL_API_URL, PL_INTERNAL_API_KEY (как в backend/.env).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
import requests

pytestmark = pytest.mark.integration

if os.getenv("PL_INTERNAL_API_INTEGRATION", "").lower() not in ("1", "true", "yes"):
    pytest.skip(
        "Живые тесты Internal API отключены. "
        "Задайте PL_INTERNAL_API_INTEGRATION=1 и поднимите туннель/сервис на :9090.",
        allow_module_level=True,
    )


def _base() -> str:
    return os.getenv("PL_INTERNAL_API_URL", "http://localhost:9090").rstrip("/")


def _headers() -> dict:
    h: dict = {}
    key = os.getenv("PL_INTERNAL_API_KEY", "").strip()
    if key:
        h["X-API-Key"] = key
    return h


def _ensure_orchestrator_on_path() -> None:
    """integrations.prelend_client живёт в репозитории Orchestrator (рядом с ContentHub)."""
    here = Path(__file__).resolve()
    for p in [here, *here.parents]:
        orc = p / "Orchestrator"
        if orc.is_dir() and (orc / "integrations").is_dir():
            s = str(orc)
            if s not in sys.path:
                sys.path.append(s)
            return


def test_live_health():
    r = requests.get(f"{_base()}/health", timeout=15)
    assert r.status_code == 200, (
        f"GET /health → {r.status_code}\n"
        f"Тело: {r.text[:1200]}\n"
        "Проверьте: сервис prelend-internal-api, порт, SSH -L 9090:127.0.0.1:9090."
    )
    body = r.json()
    assert body.get("status") == "ok", body
    auth = body.get("auth", "")
    key_set = bool(os.getenv("PL_INTERNAL_API_KEY", "").strip())
    if "enabled" in str(auth) and not key_set:
        pytest.fail(
            "На сервере включён API-ключ (auth=enabled), а PL_INTERNAL_API_KEY в окружении пуст. "
            "Задайте тот же ключ, что в systemd Environment=PL_INTERNAL_API_KEY."
        )


def test_live_get_config_settings():
    r = requests.get(f"{_base()}/config/settings", headers=_headers(), timeout=20)
    if r.status_code == 403:
        pytest.fail(
            "403 на GET /config/settings — неверный или пустой X-API-Key.\n"
            "Сравните PL_INTERNAL_API_KEY в ContentHub backend/.env с ключом на машине, "
            "куда указывает URL (через туннель — это VPS). После смены ключа: "
            "systemctl restart prelend-internal-api и перезапуск uvicorn ContentHub."
        )
    assert r.status_code == 200, (
        f"GET /config/settings → {r.status_code}\n{r.text[:1500]}"
    )
    data = r.json()
    assert isinstance(data, dict), data
    assert any(k in data for k in ("cloak_template", "default_offer_url")), (
        f"Неожиданная форма settings: ключи {list(data)[:25]}"
    )


def test_live_get_config_advertisers():
    r = requests.get(f"{_base()}/config/advertisers", headers=_headers(), timeout=20)
    assert r.status_code == 200, f"{r.status_code} {r.text[:800]}"
    data = r.json()
    assert isinstance(data, list), type(data)


def test_live_get_agents():
    r = requests.get(f"{_base()}/agents", headers=_headers(), timeout=20)
    assert r.status_code == 200, f"{r.status_code} {r.text[:800]}"
    assert isinstance(r.json(), list)


def test_live_get_metrics():
    r = requests.get(f"{_base()}/metrics", params={"period_hours": 24}, headers=_headers(), timeout=30)
    assert r.status_code == 200, f"{r.status_code} {r.text[:800]}"
    data = r.json()
    assert "geo_breakdown" in data
    assert isinstance(data["geo_breakdown"], list)


@pytest.mark.skipif(
    os.getenv("PL_INTERNAL_API_LIVE_WRITE", "").lower() not in ("1", "true", "yes"),
    reason="PUT в config/ на VPS: задайте PL_INTERNAL_API_LIVE_WRITE=1 (нужны права записи www-data)",
)
def test_live_put_settings_roundtrip_readonly_safe():
    base = _base()
    h = _headers()
    r1 = requests.get(f"{base}/config/settings", headers=h, timeout=20)
    assert r1.status_code == 200, r1.text
    payload = r1.json()
    r2 = requests.put(
        f"{base}/config/settings",
        params={"source": "contenthub_pytest_live"},
        headers={**h, "Content-Type": "application/json"},
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        timeout=30,
    )
    if r2.status_code == 400:
        pytest.fail(
            f"PUT /config/settings отклонён валидацией (400): {r2.text[:2000]}\n"
            "Часто: в JSON есть ключи вне whitelist Internal API на сервере — обновите PreLend на VPS."
        )
    if r2.status_code == 500 and "Permission denied" in r2.text:
        pytest.skip(
            "На VPS нет прав на запись в config/ (tmp в каталоге). "
            "chown www-data или запускайте без PUT-теста."
        )
    assert r2.status_code == 200, f"PUT /config/settings → {r2.status_code}\n{r2.text[:1500]}"
    r3 = requests.get(f"{base}/config/settings", headers=h, timeout=20)
    assert r3.status_code == 200


def test_live_prelend_client_matches_env_config():
    """Тот же URL/ключ, что в config.py после load_dotenv(backend/.env)."""
    _ensure_orchestrator_on_path()
    import config as cfg
    from integrations.prelend_client import PreLendClient

    client = PreLendClient(
        base_url=cfg.PL_INTERNAL_API_URL,
        api_key=cfg.PL_INTERNAL_API_KEY or "",
        timeout=15,
    )
    assert client.is_available(), (
        f"PreLendClient.is_available() == False для base_url={client.base_url!r}. "
        "Проверьте туннель и PL_INTERNAL_API_URL в backend/.env."
    )
    health = client.get_health()
    assert health and health.get("status") == "ok", health
