"""
services/config_reader.py — чтение конфигов всех проектов.

Принципы:
  - Читает JSON-файлы напрямую
  - Для pipeline/config.py: парсит только строки с os.getenv() через regex
  - Не импортирует код проектов, только читает файлы
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

import config as cfg


# ──────────────────────────────────────────────────────────────────────────────
# ShortsProject
# ──────────────────────────────────────────────────────────────────────────────

# Regex для строк вида:  VAR = os.getenv("ENV_KEY", "default_val") [!= "0" | == "1" | ...]
_ENV_LINE_RE = re.compile(
    r'^(?P<var>[A-Z_]+)\s*=\s*'
    r'(?:int|float|str)?\(?os\.getenv\(\s*"(?P<env>[^"]+)"\s*,\s*"(?P<default>[^"]*)"',
    re.MULTILINE,
)

# Секции конфига SP, которые экспонируются в UI
SP_ENV_SECTIONS = {
    "vl": [
        ("CURATOR_VL_CHECK",       "Проверка качества видео (Curator VL)", "bool"),
        ("SCOUT_VL_FILTER",        "Фильтр thumbnail по VL (Scout)", "bool"),
        ("SCOUT_VL_MIN_SCORE",     "Мин. оценка thumbnail (1–10)", "int"),
        ("SCOUT_VL_MAX_CYCLE",     "Макс. проверок за цикл", "int"),
    ],
    "ab_test": [
        ("AB_TEST_ENABLED",        "A/B тестирование заголовков", "bool"),
        ("AB_TEST_COMPARE_AFTER_H","Часов до сравнения A/B вариантов", "int"),
    ],
    "upload": [
        ("DAILY_LIMIT_YOUTUBE",    "Дневной лимит YouTube", "int"),
        ("DAILY_LIMIT_TIKTOK",     "Дневной лимит TikTok", "int"),
        ("DAILY_LIMIT_INSTAGRAM",  "Дневной лимит Instagram", "int"),
    ],
    "tts": [
        ("TTS_ENABLED",            "TTS озвучка включена", "bool"),
        ("TTS_DEFAULT_LANG",       "Язык по умолчанию (en/ru/es/pt)", "str"),
        ("TTS_SPEED",              "Скорость озвучки (0.5–2.0)", "float"),
        ("TTS_VOLUME",             "Громкость голоса (0.1–2.0)", "float"),
        ("TTS_VOICE_OVER_MIX",     "Доля голоса в миксе (0–1)", "float"),
    ],
    "activity": [
        ("ACTIVITY_INTERVAL_MIN",  "Интервал активности (мин)", "int"),
        ("ACTIVITY_JITTER_SEC",    "Разброс интервала (сек)", "int"),
        ("ACTIVITY_HOURS_START",   "Начало окна активности (час)", "int"),
        ("ACTIVITY_HOURS_END",     "Конец окна активности (час)", "int"),
    ],
    "dedup": [
        ("DEDUP_FRAME_INTERVAL_SEC", "Интервал кадров для хэша (сек)", "float"),
        ("DEDUP_HAMMING_THRESHOLD",  "Порог Hamming (0=точные, 20=агрессивно)", "int"),
    ],
    "quarantine": [
        ("QUARANTINE_ERROR_THRESHOLD", "Ошибок до карантина", "int"),
        ("QUARANTINE_DURATION_HOURS",  "Длительность карантина (часов)", "int"),
    ],
    "subtitle": [
        ("SUBTITLE_ENABLED",       "Субтитры включены", "bool"),
        ("SUBTITLE_LANGUAGES",     "Языки субтитров (через запятую)", "str"),  # SP: SUBTITLE_LANGUAGES
        ("WHISPER_MODEL_SIZE",     "Размер Whisper модели (tiny/base/small/medium)", "str"),
    ],
    "voice_clone": [
        ("VOICE_CLONE_ENABLED",    "Голосовой клон включён", "bool"),
        ("VOICE_CLONE_MODEL",      "Модель (openvoice/rvc)", "str"),
    ],
    "trend_scout": [
        ("TREND_SCOUT_ENABLED",        "TrendScout агент включён", "bool"),
        ("TREND_SCOUT_INTERVAL_H",     "Интервал обновления трендов (часов)", "int"),   # SP: TREND_SCOUT_INTERVAL_H
        ("TREND_SCOUT_THRESHOLD",      "Порог тренда для приоритизации", "float"),      # SP: TREND_SCOUT_THRESHOLD
        ("TREND_SCOUT_TOP_N",          "Макс. кол-во трендовых KW за цикл", "int"),
    ],
}


def read_sp_env() -> Dict[str, Dict[str, Any]]:
    """
    Читает .env файл ShortsProject и возвращает секции с текущими значениями.
    """
    current_env: Dict[str, str] = {}

    env_file = cfg.SP_ENV_FILE
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                current_env[k.strip()] = v.strip().strip('"').strip("'")

    result: Dict[str, List[Dict]] = {}
    for section, fields in SP_ENV_SECTIONS.items():
        result[section] = []
        for env_key, label, ftype in fields:
            result[section].append({
                "env_key": env_key,
                "label":   label,
                "type":    ftype,
                "value":   current_env.get(env_key),   # None = используется дефолт
            })

    return result


# ──────────────────────────────────────────────────────────────────────────────
# PreLend
# ──────────────────────────────────────────────────────────────────────────────

def _read_json_file(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _pl_trust_local_fallback() -> bool:
    """Совпадает с config_writer: режим «только локальный клон PreLend», без сверки с VPS."""
    return bool(
        getattr(cfg, "PL_SETTINGS_TRUST_LOCAL_FALLBACK", False)
        or getattr(cfg, "PL_TRUST_LOCAL_FALLBACK", False)
    )


def _read_pl_config(api_method: str, local_path: Path, expected_type: type, default: Any) -> Any:
    """Единый паттерн чтения конфига PreLend: trust-local → API → fallback на диск."""
    if _pl_trust_local_fallback():
        raw = _read_json_file(local_path)
        return raw if isinstance(raw, expected_type) else default

    from integrations.prelend_client import get_client
    client = get_client()
    if client.is_available():
        data = getattr(client, api_method)()
        return data if isinstance(data, expected_type) else default
    raw = _read_json_file(local_path)
    return raw if isinstance(raw, expected_type) else default


def read_pl_settings() -> Dict:
    """Читает PreLend/config/settings.json через Internal API; trust-local или недоступность API — локальный файл."""
    return _read_pl_config("get_settings", cfg.PL_SETTINGS, dict, {})


def read_pl_advertisers() -> List[Dict]:
    """Читает advertisers.json: при trust-local или недоступном API — с диска, иначе через Internal API."""
    return _read_pl_config("get_advertisers", cfg.PL_ADVERTISERS, list, [])


def read_pl_geo_data() -> Dict:
    """Читает geo_data.json: trust-local или API недоступен — локальный файл."""
    return _read_pl_config("get_geo_data", cfg.PL_GEO_DATA, dict, {})


def read_pl_splits() -> List[Dict]:
    """Читает splits.json: trust-local или API недоступен — локальный файл."""
    return _read_pl_config("get_splits", cfg.PL_SPLITS, list, [])


def read_pl_templates() -> Dict[str, List[str]]:
    """
    Читает список доступных шаблонов PreLend.

    Основной источник: Internal API (/templates).
    Fallback (совместимость со старым Internal API): локальная файловая система.
    """
    from integrations.prelend_client import get_client

    data = get_client().get_templates()
    offers = data.get("offers", []) if isinstance(data, dict) else []
    cloaked = data.get("cloaked", []) if isinstance(data, dict) else []
    if offers or cloaked:
        return {"offers": offers, "cloaked": cloaked}

    templates_root = cfg.PRELEND_DIR / "templates"
    result: Dict[str, List[str]] = {"offers": [], "cloaked": []}
    for kind in ("offers", "cloaked"):
        folder = templates_root / kind
        if not folder.exists():
            continue
        result[kind] = sorted([p.stem for p in folder.glob("*.php") if p.is_file()])
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ──────────────────────────────────────────────────────────────────────────────

def read_orc_zones() -> List[Dict]:
    """Читает состояние зон из orchestrator.db."""
    if not cfg.ORC_DB.exists():
        return []
    with sqlite3.connect(str(cfg.ORC_DB)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT zone_name, enabled, confidence_score, last_applied_at FROM zones"
        ).fetchall()
        return [dict(r) for r in rows]


def read_orc_pending_patches() -> List[Dict]:
    """Читает незакрытые патчи из orchestrator.db."""
    if not cfg.ORC_DB.exists():
        return []
    with sqlite3.connect(str(cfg.ORC_DB)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT id, created_at, plan_id, repo, file_path, goal,
                      diff_preview, status, approved_at, applied_at, apply_result
               FROM pending_patches
               WHERE status IN ('pending', 'approved')
               ORDER BY created_at DESC""",
        ).fetchall()
        return [dict(r) for r in rows]


def read_orc_last_plan() -> Optional[Dict]:
    """Читает последний план эволюции."""
    if not cfg.ORC_DB.exists():
        return None
    with sqlite3.connect(str(cfg.ORC_DB)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM evolution_plans ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


# ──────────────────────────────────────────────────────────────────────────────
# Agent memory (SP и PL)
# ──────────────────────────────────────────────────────────────────────────────

def read_sp_agent_memory() -> Dict:
    """Читает agent_memory.json ShortsProject."""
    path = cfg.SP_AGENT_MEMORY
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_pl_agent_memory() -> Dict:
    """Читает agent_memory.json PreLend."""
    path = cfg.PL_AGENT_MEMORY
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
