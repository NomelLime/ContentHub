"""
config.py — конфигурация ContentHub.

Все пути к другим проектам вынесены сюда.
При деплое задаются через .env или переменные окружения.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
# Директория ContentHub
# ──────────────────────────────────────────────────────────────────────────────
BASE_DIR        = Path(__file__).parent
CONTENTHUB_DB   = BASE_DIR / "contenthub.db"

# ──────────────────────────────────────────────────────────────────────────────
# Пути к управляемым проектам
# ──────────────────────────────────────────────────────────────────────────────
GITHUB_ROOT = Path(os.getenv("GITHUB_ROOT", r"C:\Users\lemon\Documents\GitHub"))

SHORTS_PROJECT_DIR  = Path(os.getenv("SP_DIR",   str(GITHUB_ROOT / "ShortsProject")))
PRELEND_DIR         = Path(os.getenv("PL_DIR",   str(GITHUB_ROOT / "PreLend")))
ORCHESTRATOR_DIR    = Path(os.getenv("ORC_DIR",  str(GITHUB_ROOT / "Orchestrator")))

# ──────────────────────────────────────────────────────────────────────────────
# Файлы ShortsProject
# ──────────────────────────────────────────────────────────────────────────────
SP_CONFIG_PY        = SHORTS_PROJECT_DIR / "pipeline" / "config.py"
SP_ENV_FILE         = SHORTS_PROJECT_DIR / ".env"
SP_ANALYTICS_FILE   = SHORTS_PROJECT_DIR / "data" / "analytics.json"
SP_AGENT_MEMORY     = SHORTS_PROJECT_DIR / "data" / "agent_memory.json"
SP_ACCOUNTS_ROOT    = SHORTS_PROJECT_DIR / "accounts"

# ──────────────────────────────────────────────────────────────────────────────
# Файлы PreLend
# ──────────────────────────────────────────────────────────────────────────────
PL_SETTINGS         = PRELEND_DIR / "config" / "settings.json"
PL_ADVERTISERS      = PRELEND_DIR / "config" / "advertisers.json"
PL_GEO_DATA         = PRELEND_DIR / "config" / "geo_data.json"
PL_SPLITS           = PRELEND_DIR / "config" / "splits.json"
PL_CLICKS_DB        = PRELEND_DIR / "data" / "clicks.db"
PL_AGENT_MEMORY     = PRELEND_DIR / "data" / "agent_memory.json"

# ──────────────────────────────────────────────────────────────────────────────
# Файлы Orchestrator
# ──────────────────────────────────────────────────────────────────────────────
ORC_DB              = ORCHESTRATOR_DIR / "data" / "orchestrator.db"   # БД в data/, не в корне
ORC_AGENT_MEMORY    = ORCHESTRATOR_DIR / "data" / "agent_memory.json"

# ──────────────────────────────────────────────────────────────────────────────
# Безопасность / JWT
# ──────────────────────────────────────────────────────────────────────────────
_DEFAULT_SECRET     = "change-me-in-production-32-chars!"             # sentinel для startup-проверки
SECRET_KEY          = os.getenv("CONTENTHUB_SECRET_KEY", _DEFAULT_SECRET)
ACCESS_TOKEN_EXPIRE_MINUTES  = int(os.getenv("ACCESS_TOKEN_EXPIRE_MIN",  "60"))
REFRESH_TOKEN_EXPIRE_DAYS    = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))

# ──────────────────────────────────────────────────────────────────────────────
# Веб-сервер / CORS
# ──────────────────────────────────────────────────────────────────────────────
HOST            = os.getenv("CONTENTHUB_HOST", "0.0.0.0")
PORT            = int(os.getenv("CONTENTHUB_PORT", "8000"))
# CORS: в продакшне задать через ALLOWED_ORIGINS=https://yourdomain.com
# В dev по умолчанию — только локальный фронт Vite
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
] or ["http://localhost:5173"]

# ──────────────────────────────────────────────────────────────────────────────
# Интервал обновления метрик (секунды)
# ──────────────────────────────────────────────────────────────────────────────
METRICS_REFRESH_SEC     = int(os.getenv("METRICS_REFRESH_SEC",  "60"))
WS_BROADCAST_SEC        = int(os.getenv("WS_BROADCAST_SEC",     "5"))
