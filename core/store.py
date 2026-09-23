"""Atomic JSON storage for the live Sana workspace."""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if os.name == "nt":
    import msvcrt
else:
    import fcntl


LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("SANA_DATA_DIR") or PROJECT_ROOT / ".sana-data")


class DataStoreError(RuntimeError):
    """Existing data cannot be read safely."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _path(name: str) -> Path:
    return DATA_DIR / name


def _write_items(path: Path, items: list[dict]) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as temporary:
            json.dump(items, temporary, ensure_ascii=False, indent=2)
            temporary.write("\n")
            temp_path = Path(temporary.name)
        os.replace(temp_path, path)
        return True
    except (OSError, TypeError, ValueError):
        LOGGER.exception("Не удалось записать JSON-файл %s", path)
        try:
            if "temp_path" in locals():
                temp_path.unlink(missing_ok=True)
        except OSError:
            LOGGER.warning("Не удалось удалить временный файл %s", temp_path)
        return False


def _read_items(name: str) -> list[dict]:
    path = _path(name)
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, list):
            raise DataStoreError(f"Ожидался список в {path}")
        return [item for item in value if isinstance(item, dict)]
    except (OSError, json.JSONDecodeError) as exc:
        raise DataStoreError(f"Не удалось прочитать JSON {path}") from exc


@contextmanager
def _locked_items(name: str):
    """Serialize read-modify-write across threads and worker processes."""
    DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (_path(name + ".lock")).open("a+") as lock_file:
        if os.name == "nt":
            lock_file.seek(0)
            if not lock_file.read(1):
                lock_file.write("0")
                lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield _read_items(name)
        finally:
            if os.name == "nt":
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _next_id(items: list[dict], prefix: str) -> str:
    highest = 0
    for item in items:
        match = re.fullmatch(rf"{re.escape(prefix)}_(\d+)", str(item.get("id", "")))
        if match:
            highest = max(highest, int(match.group(1)))
    return f"{prefix}_{highest + 1:03d}"


def load_tasks() -> list[dict]:
    return _read_items("tasks.json")


def get_task(task_id: str) -> dict | None:
    if not isinstance(task_id, str):
        return None
    return next((task for task in load_tasks() if task.get("id") == task_id), None)


def save_task(task: dict) -> dict:
    if not isinstance(task, dict):
        return {}
    with _locked_items("tasks.json") as tasks:
        saved = dict(task)
        saved.setdefault("id", _next_id(tasks, "t"))
        saved.setdefault("created_at", _now())
        for index, existing in enumerate(tasks):
            if existing.get("id") == saved["id"]:
                saved["owner_token_hash"] = existing.get("owner_token_hash", "")
                tasks[index] = saved
                break
        else:
            tasks.append(saved)
        return saved if _write_items(_path("tasks.json"), tasks) else {}


def update_task(task_id: str, task: dict) -> dict | None:
    if not isinstance(task_id, str) or not isinstance(task, dict):
        return None
    with _locked_items("tasks.json") as tasks:
        for index, existing in enumerate(tasks):
            if existing.get("id") == task_id:
                updated = dict(task)
                updated["id"] = task_id
                updated["created_at"] = existing.get("created_at", _now())
                updated["owner_token_hash"] = existing.get("owner_token_hash", "")
                tasks[index] = updated
                return updated if _write_items(_path("tasks.json"), tasks) else None
    return None


def load_teams() -> list[dict]:
    return _read_items("teams.json")


def get_team(team_id: str) -> dict | None:
    return next((team for team in load_teams() if team.get("id") == team_id), None)


def save_team(team: dict) -> dict:
    if not isinstance(team, dict):
        return {}
    with _locked_items("teams.json") as teams:
        saved = dict(team)
        saved["id"] = _next_id(teams, "team")
        saved["created_at"] = _now()
        teams.append(saved)
        return saved if _write_items(_path("teams.json"), teams) else {}


def load_proposals(task_id: str | None = None) -> list[dict]:
    proposals = _read_items("proposals.json")
    if task_id is None:
        return proposals
    return [proposal for proposal in proposals if proposal.get("task_id") == task_id]


def save_proposal(proposal: dict) -> dict:
    if not isinstance(proposal, dict):
        return {}
    with _locked_items("proposals.json") as proposals:
        saved = dict(proposal)
        saved.setdefault("id", _next_id(proposals, "p"))
        saved.setdefault("created_at", _now())
        saved["status"] = "new"
        proposals.append(saved)
        return saved if _write_items(_path("proposals.json"), proposals) else {}


def update_proposal_status(proposal_id: str, status: str) -> dict | None:
    if status not in {"accepted", "rejected"}:
        return None
    with _locked_items("proposals.json") as proposals:
        for proposal in proposals:
            if proposal.get("id") == proposal_id and proposal.get("status") == "new":
                proposal["status"] = status
                return proposal if _write_items(_path("proposals.json"), proposals) else None
    return None


def load_progress() -> list[dict]:
    return _read_items("progress.json")


def save_progress(progress: dict) -> dict:
    if not isinstance(progress, dict):
        return {}
    with _locked_items("progress.json") as entries:
        saved = dict(progress)
        saved.setdefault("id", _next_id(entries, "progress"))
        saved.setdefault("created_at", _now())
        saved.setdefault("status", "submitted")
        saved.setdefault("points", 0)
        entries.append(saved)
        return saved if _write_items(_path("progress.json"), entries) else {}


def update_progress_status(progress_id: str, status: str, points: int = 0) -> dict | None:
    if status not in {"confirmed", "rejected"}:
        return None
    with _locked_items("progress.json") as entries:
        for entry in entries:
            if entry.get("id") == progress_id and entry.get("status") == "submitted":
                entry["status"] = status
                entry["points"] = points if status == "confirmed" else 0
                entry["reviewed_at"] = _now()
                return entry if _write_items(_path("progress.json"), entries) else None
    return None
