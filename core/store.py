"""Small JSON-file store for the five-hour MVP."""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("TASKFORGE_DATA_DIR", PROJECT_ROOT / "data"))


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _path(name: str) -> Path:
    return DATA_DIR / name


def _write_items(path: Path, items: list[dict]) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
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
        _write_items(path, [])
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, list):
            LOGGER.warning("Ожидался список в %s", path)
            return []
        return [item for item in value if isinstance(item, dict)]
    except (OSError, json.JSONDecodeError):
        LOGGER.warning("Не удалось прочитать JSON %s; возвращён пустой список", path)
        return []


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
    tasks = load_tasks()
    saved = dict(task)
    saved.setdefault("id", _next_id(tasks, "t"))
    saved.setdefault("created_at", _now())
    for index, existing in enumerate(tasks):
        if existing.get("id") == saved["id"]:
            tasks[index] = saved
            break
    else:
        tasks.append(saved)
    _write_items(_path("tasks.json"), tasks)
    return saved


def update_task(task_id: str, task: dict) -> dict | None:
    if not isinstance(task_id, str) or not isinstance(task, dict):
        return None
    tasks = load_tasks()
    for index, existing in enumerate(tasks):
        if existing.get("id") == task_id:
            updated = dict(task)
            updated["id"] = task_id
            updated["created_at"] = existing.get("created_at", _now())
            tasks[index] = updated
            _write_items(_path("tasks.json"), tasks)
            return updated
    return None


def load_teams() -> list[dict]:
    return _read_items("teams.json")


def load_demo() -> dict:
    path = _path("demo.json")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        LOGGER.warning("Не удалось прочитать демонстрационный пример %s", path)
        return {}


def load_proposals(task_id: str | None = None) -> list[dict]:
    proposals = _read_items("proposals.json")
    if task_id is None:
        return proposals
    return [proposal for proposal in proposals if proposal.get("task_id") == task_id]


def save_proposal(proposal: dict) -> dict:
    if not isinstance(proposal, dict):
        return {}
    proposals = load_proposals()
    saved = dict(proposal)
    saved.setdefault("id", _next_id(proposals, "p"))
    saved.setdefault("created_at", _now())
    saved["status"] = "new"
    proposals.append(saved)
    _write_items(_path("proposals.json"), proposals)
    return saved


def update_proposal_status(proposal_id: str, status: str) -> dict | None:
    if status not in {"accepted", "rejected"}:
        return None
    proposals = load_proposals()
    for proposal in proposals:
        if proposal.get("id") == proposal_id:
            proposal["status"] = status
            _write_items(_path("proposals.json"), proposals)
            return proposal
    return None


def load_progress() -> list[dict]:
    return _read_items("progress.json")


def save_progress(progress: dict) -> dict:
    if not isinstance(progress, dict):
        return {}
    entries = load_progress()
    saved = dict(progress)
    saved.setdefault("id", _next_id(entries, "progress"))
    saved.setdefault("created_at", _now())
    saved.setdefault("status", "submitted")
    saved.setdefault("points", 0)
    entries.append(saved)
    _write_items(_path("progress.json"), entries)
    return saved


def update_progress_status(progress_id: str, status: str, points: int = 0) -> dict | None:
    if status not in {"confirmed", "rejected"}:
        return None
    entries = load_progress()
    for entry in entries:
        if entry.get("id") == progress_id and entry.get("status") == "submitted":
            entry["status"] = status
            entry["points"] = points if status == "confirmed" else 0
            entry["reviewed_at"] = _now()
            if not _write_items(_path("progress.json"), entries):
                return None
            return entry
    return None
