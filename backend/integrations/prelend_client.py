"""
HTTP-клиент PreLend Internal API — код живёт в Orchestrator/integrations.
Добавляем Orchestrator в sys.path относительно корня репозитория (рядом с ContentHub).
"""
from __future__ import annotations

import sys
from pathlib import Path

_hub_backend = Path(__file__).resolve().parent.parent
_contenthub_root = _hub_backend.parent
_github_root = _contenthub_root.parent
_orc = _github_root / "Orchestrator"
if _orc.is_dir():
    s = str(_orc.resolve())
    if s not in sys.path:
        sys.path.insert(0, s)

from integrations.prelend_client import PreLendClient, get_client  # noqa: E402,F401
