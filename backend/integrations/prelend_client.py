"""
HTTP-клиент PreLend Internal API — код в Orchestrator/integrations/prelend_client.py.

Загружаем реализацию через importlib под уникальным именем модуля, иначе
`from integrations.prelend_client import …` разрешался бы в ЭТОТ же файл (циклический импорт).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_hub_backend = Path(__file__).resolve().parent.parent
_github_root = _hub_backend.parent.parent
_orc_pl_path = _github_root / "Orchestrator" / "integrations" / "prelend_client.py"

if not _orc_pl_path.is_file():
    raise ImportError(
        f"Orchestrator PreLend client not found: {_orc_pl_path}. "
        "Задайте GITHUB_ROOT или положите репозиторий Orchestrator рядом с ContentHub."
    )

_spec = importlib.util.spec_from_file_location(
    "orchestrator_prelend_client_impl",
    _orc_pl_path,
)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load spec for {_orc_pl_path}")

_mod = importlib.util.module_from_spec(_spec)
sys.modules["orchestrator_prelend_client_impl"] = _mod
_spec.loader.exec_module(_mod)

PreLendClient = _mod.PreLendClient
get_client = _mod.get_client

__all__ = ["PreLendClient", "get_client"]
