"""
services/config_writer.py — атомарная запись конфигов всех проектов.

Паттерн атомарной записи взят из Orchestrator/modules/config_enforcer.py:
  1. Пишем во временный файл
  2. os.replace() — атомарная замена (POSIX atomic)
  3. git commit для трекинга изменений

Для pipeline/config.py ShortsProject:
  Пишем в .env файл (все os.getenv()-backed переменные).
  Не трогаем сам config.py.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import config as cfg

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Базовый атомарный write
# ──────────────────────────────────────────────────────────────────────────────

def atomic_write_json(path: Path, data: Any) -> None:
    """
    Атомарная запись JSON через временный файл.
    При ошибке оставляет оригинальный файл нетронутым.
    """
    text = json.dumps(data, ensure_ascii=False, indent=2)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        os.write(fd, text.encode("utf-8"))
        os.close(fd)
        os.replace(tmp, str(path))
        logger.debug("[ConfigWriter] Записан: %s", path)
    except Exception:
        try:
            os.close(fd)
        except Exception:
            pass
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def atomic_write_text(path: Path, text: str) -> None:
    """Атомарная запись текстового файла."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        os.write(fd, text.encode("utf-8"))
        os.close(fd)
        os.replace(tmp, str(path))
        logger.debug("[ConfigWriter] Записан: %s", path)
    except Exception:
        try:
            os.close(fd)
        except Exception:
            pass
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def _git_commit(repo_dir: Path, file_path: Path, message: str) -> bool:
    """Делает git commit изменённого файла. Возвращает True при успехе."""
    try:
        subprocess.run(
            ["git", "add", str(file_path)],
            cwd=str(repo_dir), check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(repo_dir), check=True, capture_output=True,
        )
        logger.info("[ConfigWriter] git commit: %s", message)
        return True
    except subprocess.CalledProcessError as exc:
        # "nothing to commit" — не ошибка
        stderr = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else ""
        if "nothing to commit" in stderr or "nothing added" in stderr:
            return True
        logger.warning("[ConfigWriter] git commit не удался: %s", stderr[:200])
        return False


# ──────────────────────────────────────────────────────────────────────────────
# ShortsProject — запись через .env
# ──────────────────────────────────────────────────────────────────────────────

def write_sp_env(env_updates: Dict[str, str], username: str = "contenthub") -> None:
    """
    Обновляет переменные в .env файле ShortsProject.

    Если .env нет — создаёт.
    Существующие строки обновляются, новые добавляются в конец.
    """
    env_file = cfg.SP_ENV_FILE
    current: Dict[str, str] = {}
    lines: List[str] = []

    if env_file.exists():
        raw = env_file.read_text(encoding="utf-8").splitlines()
        for line in raw:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k, _, v = stripped.partition("=")
                current[k.strip()] = line  # сохраняем оригинальную строку
            lines.append(line)

    # Обновляем или добавляем
    for key, value in env_updates.items():
        new_line = f'{key}={value}'
        if key in current:
            # Заменяем в списке
            lines = [
                new_line if (l.strip().startswith(key + "=") or l.strip().startswith(key + " ="))
                else l
                for l in lines
            ]
        else:
            lines.append(new_line)

    atomic_write_text(env_file, "\n".join(lines) + "\n")
    _git_commit(
        repo_dir=cfg.SHORTS_PROJECT_DIR,
        file_path=env_file,
        message=f"[ContentHub:{username}] SP env update: {list(env_updates.keys())}",
    )


# ──────────────────────────────────────────────────────────────────────────────
# PreLend — JSON configs
# ──────────────────────────────────────────────────────────────────────────────

def write_pl_settings(data: Dict, username: str = "contenthub") -> None:
    """Перезаписывает PreLend/config/settings.json."""
    path = cfg.PL_SETTINGS
    atomic_write_json(path, data)
    _git_commit(
        repo_dir=cfg.PRELEND_DIR,
        file_path=path,
        message=f"[ContentHub:{username}] PL settings update",
    )


def write_pl_advertisers(data: List[Dict], username: str = "contenthub") -> None:
    """Перезаписывает PreLend/config/advertisers.json."""
    path = cfg.PL_ADVERTISERS
    atomic_write_json(path, data)
    _git_commit(
        repo_dir=cfg.PRELEND_DIR,
        file_path=path,
        message=f"[ContentHub:{username}] PL advertisers update",
    )


def write_pl_advertiser(advertiser_id: str, updates: Dict, username: str = "contenthub") -> bool:
    """Обновляет одного рекламодателя в advertisers.json. Возвращает True при успехе."""
    from services.config_reader import read_pl_advertisers
    advertisers = read_pl_advertisers()
    target = next((a for a in advertisers if a.get("id") == advertiser_id), None)
    if target is None:
        return False
    target.update(updates)
    write_pl_advertisers(advertisers, username=username)
    return True


def write_pl_geo_data(data: Dict, username: str = "contenthub") -> None:
    """Перезаписывает PreLend/config/geo_data.json."""
    path = cfg.PL_GEO_DATA
    # Создаём файл если нет
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, data)
    _git_commit(
        repo_dir=cfg.PRELEND_DIR,
        file_path=path,
        message=f"[ContentHub:{username}] PL geo_data update",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Orchestrator — патчи через DB (не через файлы)
# ──────────────────────────────────────────────────────────────────────────────

def approve_patch(patch_id: int) -> bool:
    """Одобряет патч в orchestrator.db (status → 'approved')."""
    import sqlite3
    from datetime import datetime, timezone
    if not cfg.ORC_DB.exists():
        return False
    with sqlite3.connect(str(cfg.ORC_DB)) as conn:
        cur = conn.execute(
            "UPDATE pending_patches SET status='approved', approved_at=? WHERE id=? AND status='pending'",
            (datetime.now(timezone.utc).isoformat(), patch_id),
        )
        conn.commit()
        return cur.rowcount > 0


def reject_patch(patch_id: int) -> bool:
    """Отклоняет патч в orchestrator.db (status → 'rejected')."""
    import sqlite3
    if not cfg.ORC_DB.exists():
        return False
    with sqlite3.connect(str(cfg.ORC_DB)) as conn:
        cur = conn.execute(
            "UPDATE pending_patches SET status='rejected' WHERE id=? AND status='pending'",
            (patch_id,),
        )
        conn.commit()
        return cur.rowcount > 0
