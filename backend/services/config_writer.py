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
from typing import Any, Dict, List, Optional, Tuple

import config as cfg

logger = logging.getLogger(__name__)


def _trust_pl_local_fallback() -> bool:
    """Пропуск сверки с Internal API после локальной записи (dev / без туннеля к VPS)."""
    return bool(
        getattr(cfg, "PL_SETTINGS_TRUST_LOCAL_FALLBACK", False)
        or getattr(cfg, "PL_TRUST_LOCAL_FALLBACK", False)
    )


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
    """
    Перезаписывает PreLend/config/settings.json.

    Основной путь: через Internal API.
    Fallback (для legacy Internal API): прямая локальная запись файла.
    """
    from integrations.prelend_client import get_client
    client = get_client()
    ok = client.write_settings(data, source=f"contenthub:{username}")
    if ok:
        return

    # Legacy fallback: если Internal API недоступен/несовместим, пишем локально.
    try:
        atomic_write_json(cfg.PL_SETTINGS, data)
        _git_commit(
            repo_dir=cfg.PRELEND_DIR,
            file_path=cfg.PL_SETTINGS,
            message=f"[ContentHub:{username}] PL settings update (fallback local write)",
        )
        logger.warning("[ConfigWriter] write_pl_settings: использован fallback на локальную запись")
        if _trust_pl_local_fallback():
            logger.warning(
                "[ConfigWriter] trust local fallback — пропуск сверки settings с Internal API "
                "(CONTENTHUB_PL_*_TRUST_LOCAL_FALLBACK или CONTENTHUB_PL_TRUST_LOCAL_FALLBACK)"
            )
            return
        # Подтверждаем, что API видит те же данные (иначе UI и прод на VPS разъедутся).
        remote = client.get_settings()
        if not remote:
            raise RuntimeError(
                "Internal API не вернул settings после локальной записи. "
                "Проверьте PL_INTERNAL_API_URL, SSH-туннель на порт 9090 и PL_INTERNAL_API_KEY. "
                "Для локальной разработки без VPS: CONTENTHUB_PL_TRUST_LOCAL_FALLBACK=1 в backend/.env"
            )
        mismatches = [k for k, v in data.items() if remote.get(k) != v]
        if mismatches:
            raise RuntimeError(
                "Локальный settings.json обновлён, но Internal API отдаёт другие значения "
                f"(поля: {mismatches[:12]}{'…' if len(mismatches) > 12 else ''}). "
                "Обычно: нет туннеля к VPS, другой API-ключ или на VPS отклонён PUT (лишние ключи в JSON). "
                "См. логи PreLend internal_api."
            )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("Не удалось записать PL settings через Internal API и локально") from exc


def write_pl_advertisers(data: List[Dict], username: str = "contenthub") -> None:
    """
    Перезаписывает PreLend/config/advertisers.json.

    Основной путь: через Internal API.
    Fallback (для legacy Internal API): прямая локальная запись файла.
    """
    from integrations.prelend_client import get_client
    client = get_client()
    ok = client.write_advertisers(data, source=f"contenthub:{username}")
    if ok:
        return
    try:
        atomic_write_json(cfg.PL_ADVERTISERS, data)
        _git_commit(
            repo_dir=cfg.PRELEND_DIR,
            file_path=cfg.PL_ADVERTISERS,
            message=f"[ContentHub:{username}] PL advertisers update (fallback local write)",
        )
        logger.warning("[ConfigWriter] write_pl_advertisers: использован fallback на локальную запись")
        if _trust_pl_local_fallback():
            logger.warning("[ConfigWriter] trust local fallback — пропуск сверки advertisers с API")
            return
        remote = client.get_advertisers()
        if not isinstance(remote, list) or len(remote) != len(data):
            raise RuntimeError(
                "Локальный advertisers.json обновлён, но GET /config/advertisers с API пустой или другой длины. "
                "Проверьте туннель :9090 и PL_INTERNAL_API_KEY. "
                "Или CONTENTHUB_PL_TRUST_LOCAL_FALLBACK=1 в backend/.env для работы только с локальным PreLend."
            )
        local_map = {str(a.get("id")): a for a in data}
        for r in remote:
            rid = str(r.get("id"))
            if rid not in local_map:
                raise RuntimeError(
                    "Internal API вернул другой набор id рекламодателей после локальной записи."
                )
            l = local_map[rid]
            if r.get("template") != l.get("template") or r.get("status") != l.get("status"):
                raise RuntimeError(
                    f"API не подтвердил запись advertisers (расхождение template/status у id={rid}). "
                    "Проверьте Internal API / туннель."
                )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("Не удалось записать PL advertisers через Internal API и локально") from exc


def write_pl_advertiser(advertiser_id: str, updates: Dict, username: str = "contenthub") -> bool:
    """Обновляет одного рекламодателя. Возвращает True при успехе."""
    from integrations.prelend_client import get_client
    client = get_client()
    advertisers = client.get_advertisers()
    target = next((a for a in advertisers if a.get("id") == advertiser_id), None)
    if target is None:
        return False
    target.update(updates)
    if client.write_advertisers(advertisers, source=f"contenthub:{username}"):
        return True
    # Fallback на локальную запись
    try:
        atomic_write_json(cfg.PL_ADVERTISERS, advertisers)
        _git_commit(
            repo_dir=cfg.PRELEND_DIR,
            file_path=cfg.PL_ADVERTISERS,
            message=f"[ContentHub:{username}] PL advertiser {advertiser_id} update (fallback local write)",
        )
        logger.warning(
            "[ConfigWriter] write_pl_advertiser(%s): использован fallback на локальную запись",
            advertiser_id,
        )
        if _trust_pl_local_fallback():
            logger.warning(
                "[ConfigWriter] trust local fallback — пропуск сверки рекламодателя %s с API",
                advertiser_id,
            )
            return True
        remote = client.get_advertisers()
        r_target = next((a for a in remote if a.get("id") == advertiser_id), None) if isinstance(remote, list) else None
        if not isinstance(r_target, dict):
            raise RuntimeError(
                f"Локально обновлён '{advertiser_id}', но Internal API не вернул эту запись в списке. "
                "Проверьте PL_INTERNAL_API_URL, SSH-туннель на 9090 и ключ. "
                "Или CONTENTHUB_PL_TRUST_LOCAL_FALLBACK=1 для локального PreLend без VPS."
            )
        mismatched = [k for k, v in updates.items() if r_target.get(k) != v]
        if mismatched:
            raise RuntimeError(
                f"Локально обновлён '{advertiser_id}', но API отдаёт другие значения для полей: {mismatched}. "
                "Часто: PUT /config/advertisers на VPS не прошёл (сеть/ключ), а чтение идёт с другого источника. "
                "Проверьте логи prelend-internal-api и туннель."
            )
        return True
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(
            f"Не удалось записать рекламодателя '{advertiser_id}' через Internal API и локально"
        ) from exc


def write_pl_geo_data(data: Dict, username: str = "contenthub") -> None:
    """Перезаписывает PreLend/config/geo_data.json через Internal API."""
    from integrations.prelend_client import get_client
    ok = get_client().write_geo_data(data, source=f"contenthub:{username}")
    if not ok:
        raise RuntimeError("Не удалось записать PL geo_data через Internal API")


def write_pl_splits(data: List[Dict], username: str = "contenthub") -> None:
    """Перезаписывает PreLend/config/splits.json через Internal API."""
    from integrations.prelend_client import get_client
    ok = get_client().write_splits(data, source=f"contenthub:{username}")
    if not ok:
        raise RuntimeError("Не удалось записать PL splits через Internal API")


# ──────────────────────────────────────────────────────────────────────────────
# История конфигов (git log / show / revert по отслеживаемым файлам)
# ──────────────────────────────────────────────────────────────────────────────

# Ключ → (корень git-репозитория, путь к файлу относительно корня)
_CONFIG_TRACKED: Dict[str, Tuple[Path, str]] = {
    "sp_env":         (cfg.SHORTS_PROJECT_DIR, ".env"),
    "pl_settings":    (cfg.PRELEND_DIR, "config/settings.json"),
    "pl_advertisers": (cfg.PRELEND_DIR, "config/advertisers.json"),
}


def list_config_history_targets() -> List[str]:
    return list(_CONFIG_TRACKED.keys())


def _resolve_tracked(target_key: str) -> Tuple[Path, Path]:
    if target_key not in _CONFIG_TRACKED:
        raise KeyError(target_key)
    repo, rel = _CONFIG_TRACKED[target_key]
    abspath = (repo / rel).resolve()
    return repo.resolve(), abspath


def _git_rel_path(repo: Path, abspath: Path) -> str:
    return str(abspath.resolve().relative_to(repo.resolve()))


def git_config_log(target_key: str, limit: int = 40) -> List[Dict[str, Any]]:
    """Список коммитов, затрагивавших файл (новые сверху)."""
    repo, abspath = _resolve_tracked(target_key)
    if not (repo / ".git").is_dir():
        return []
    rel = _git_rel_path(repo, abspath)
    cp = subprocess.run(
        [
            "git", "log", "-n", str(limit), "--format=%H%x1f%ct%x1f%s", "--", rel,
        ],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    if cp.returncode != 0:
        logger.warning("[ConfigWriter] git log: %s", (cp.stderr or "")[:400])
        return []
    rows: List[Dict[str, Any]] = []
    for line in cp.stdout.strip().splitlines():
        parts = line.split("\x1f", 2)
        if len(parts) != 3:
            continue
        rows.append(
            {
                "commit":       parts[0],
                "committed_ts": int(parts[1]),
                "subject":      parts[2],
            }
        )
    return rows


def git_config_show(target_key: str, commit: str, max_bytes: int = 400_000) -> str:
    """Содержимое файла на указанном коммите (`git show commit:path`)."""
    repo, abspath = _resolve_tracked(target_key)
    rel = _git_rel_path(repo, abspath)
    spec = f"{commit.strip()}:{rel}"
    cp = subprocess.run(
        ["git", "show", spec],
        cwd=str(repo),
        capture_output=True,
    )
    if cp.returncode != 0:
        err = (cp.stderr or b"").decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"git show не удался: {err}")
    data = cp.stdout
    if len(data) > max_bytes:
        return data[:max_bytes].decode("utf-8", errors="replace") + "\n\n… [обрезано]"
    return data.decode("utf-8", errors="replace")


def git_config_revert_to_commit(target_key: str, commit: str, username: str) -> None:
    """
    Восстанавливает файл из коммита в рабочее дерево и делает git commit.
    Для pl_* после этого может понадобиться синхронизация с Internal API вручную,
    если запись шла только на VPS.
    """
    repo, abspath = _resolve_tracked(target_key)
    rel = _git_rel_path(repo, abspath)
    c = commit.strip()
    if len(c) < 7:
        raise ValueError("Некорректный hash коммита")

    cp = subprocess.run(
        ["git", "checkout", c, "--", rel],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    if cp.returncode != 0:
        raise RuntimeError((cp.stderr or cp.stdout or "git checkout failed")[:500])

    _git_commit(
        repo_dir=repo,
        file_path=abspath,
        message=f"[ContentHub:{username}] revert {target_key} to {c[:7]}",
    )

    # Для SP .env достаточно файла. Для PL JSON — пробуем отправить на API как при обычной записи.
    if target_key == "pl_settings":
        import json as _json
        from integrations.prelend_client import get_client

        payload = _json.loads(abspath.read_text(encoding="utf-8"))
        if not get_client().write_settings(payload, source=f"contenthub:{username}:revert"):
            logger.warning(
                "[ConfigWriter] revert pl_settings: локальный git ok, Internal API write не подтверждён"
            )
    elif target_key == "pl_advertisers":
        import json as _json
        from integrations.prelend_client import get_client

        payload = _json.loads(abspath.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise RuntimeError("advertisers.json должен быть массивом")
        if not get_client().write_advertisers(payload, source=f"contenthub:{username}:revert"):
            logger.warning(
                "[ConfigWriter] revert pl_advertisers: локальный git ok, Internal API write не подтверждён"
            )


# ──────────────────────────────────────────────────────────────────────────────
# Orchestrator — патчи через DB (не через файлы)
# ──────────────────────────────────────────────────────────────────────────────

def approve_patch(patch_id: int) -> bool:
    """Одобряет патч в orchestrator.db (status → 'approved').
    Возвращает False если патч не найден, уже обработан или произошёл race."""
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
        if cur.rowcount == 0:
            logger.warning(
                "[ConfigWriter] Патч #%d: rowcount=0 при approve — "
                "уже обработан (race с Telegram или другим оператором)",
                patch_id,
            )
        return cur.rowcount > 0


def reject_patch(patch_id: int) -> bool:
    """Отклоняет патч в orchestrator.db (status → 'rejected').
    Возвращает False если патч не найден, уже обработан или произошёл race."""
    import sqlite3
    if not cfg.ORC_DB.exists():
        return False
    with sqlite3.connect(str(cfg.ORC_DB)) as conn:
        cur = conn.execute(
            "UPDATE pending_patches SET status='rejected' WHERE id=? AND status='pending'",
            (patch_id,),
        )
        conn.commit()
        if cur.rowcount == 0:
            logger.warning(
                "[ConfigWriter] Патч #%d: rowcount=0 при reject — "
                "уже обработан (race с Telegram или другим оператором)",
                patch_id,
            )
        return cur.rowcount > 0
