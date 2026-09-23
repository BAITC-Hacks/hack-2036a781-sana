"""Atomic JSON storage for the live Sana workspace."""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

if os.name == "nt":
    import msvcrt
else:
    import fcntl


LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
DATA_DIR = Path(os.getenv("SANA_DATA_DIR") or PROJECT_ROOT / ".sana-data")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
_INITIALIZED_URL = ""
_DATABASE_LOCK = threading.Lock()
_RECORD_TYPES = {"task", "team", "proposal", "progress"}


class DataStoreError(RuntimeError):
    """Existing data cannot be read safely."""


def _database_enabled() -> bool:
    return DATABASE_URL.startswith(("postgresql://", "postgres://"))


def initialize_database() -> None:
    """Create the compact JSONB schema once for the configured Neon database."""
    global _INITIALIZED_URL
    if not _database_enabled() or _INITIALIZED_URL == DATABASE_URL:
        return
    with _DATABASE_LOCK:
        if _INITIALIZED_URL == DATABASE_URL:
            return
        try:
            with psycopg.connect(DATABASE_URL, connect_timeout=10) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS sana_records (
                            record_type TEXT NOT NULL,
                            record_id TEXT NOT NULL,
                            payload JSONB NOT NULL,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            PRIMARY KEY (record_type, record_id)
                        )
                        """
                    )
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS sana_counters (
                            record_type TEXT PRIMARY KEY,
                            next_value BIGINT NOT NULL CHECK (next_value > 0)
                        )
                        """
                    )
                    cursor.execute(
                        """
                        CREATE INDEX IF NOT EXISTS sana_records_created_at_idx
                        ON sana_records (record_type, created_at DESC)
                        """
                    )
            _INITIALIZED_URL = DATABASE_URL
        except psycopg.Error as exc:
            raise DataStoreError("Не удалось подключиться к PostgreSQL.") from exc


def storage_backend() -> str:
    return "postgresql" if _database_enabled() else "json"


@contextmanager
def _database_connection():
    initialize_database()
    try:
        with psycopg.connect(
            DATABASE_URL,
            connect_timeout=10,
            row_factory=dict_row,
        ) as connection:
            yield connection
    except psycopg.Error as exc:
        raise DataStoreError("Операция PostgreSQL не выполнена.") from exc


def _database_load(record_type: str) -> list[dict]:
    if record_type not in _RECORD_TYPES:
        return []
    with _database_connection() as connection:
        rows = connection.execute(
            """
            SELECT payload
            FROM sana_records
            WHERE record_type = %s
            ORDER BY created_at, record_id
            """,
            (record_type,),
        ).fetchall()
    return [dict(row["payload"]) for row in rows if isinstance(row["payload"], dict)]


def _database_next_id(connection, record_type: str, prefix: str) -> str:
    row = connection.execute(
        """
        INSERT INTO sana_counters (record_type, next_value)
        VALUES (%s, 2)
        ON CONFLICT (record_type) DO UPDATE
        SET next_value = sana_counters.next_value + 1
        RETURNING next_value - 1 AS value
        """,
        (record_type,),
    ).fetchone()
    return f"{prefix}_{int(row['value']):03d}"


def _database_save(
    record_type: str,
    prefix: str,
    item: dict,
    *,
    force_new: bool = False,
    preserve_fields: tuple[str, ...] = (),
) -> dict:
    saved = dict(item)
    with _database_connection() as connection:
        if force_new or not saved.get("id"):
            saved["id"] = _database_next_id(connection, record_type, prefix)
        existing_row = connection.execute(
            """
            SELECT payload
            FROM sana_records
            WHERE record_type = %s AND record_id = %s
            FOR UPDATE
            """,
            (record_type, saved["id"]),
        ).fetchone()
        existing = existing_row["payload"] if existing_row else {}
        saved.setdefault("created_at", existing.get("created_at", _now()))
        for field in preserve_fields:
            if field in existing:
                saved[field] = existing[field]
        connection.execute(
            """
            INSERT INTO sana_records (record_type, record_id, payload)
            VALUES (%s, %s, %s)
            ON CONFLICT (record_type, record_id) DO UPDATE
            SET payload = EXCLUDED.payload, updated_at = NOW()
            """,
            (record_type, saved["id"], Jsonb(saved)),
        )
    return saved


def _database_update(
    record_type: str,
    record_id: str,
    item: dict,
    preserve_fields: tuple[str, ...] = (),
) -> dict | None:
    with _database_connection() as connection:
        row = connection.execute(
            """
            SELECT payload
            FROM sana_records
            WHERE record_type = %s AND record_id = %s
            FOR UPDATE
            """,
            (record_type, record_id),
        ).fetchone()
        if row is None:
            return None
        existing = row["payload"]
        updated = dict(item)
        updated["id"] = record_id
        updated["created_at"] = existing.get("created_at", _now())
        for field in preserve_fields:
            updated[field] = existing.get(field, "")
        connection.execute(
            """
            UPDATE sana_records
            SET payload = %s, updated_at = NOW()
            WHERE record_type = %s AND record_id = %s
            """,
            (Jsonb(updated), record_type, record_id),
        )
    return updated


def _database_transition(
    record_type: str,
    record_id: str,
    expected_status: str,
    updates: dict,
) -> dict | None:
    with _database_connection() as connection:
        row = connection.execute(
            """
            SELECT payload
            FROM sana_records
            WHERE record_type = %s AND record_id = %s
            FOR UPDATE
            """,
            (record_type, record_id),
        ).fetchone()
        if row is None or row["payload"].get("status") != expected_status:
            return None
        updated = {**row["payload"], **updates}
        connection.execute(
            """
            UPDATE sana_records
            SET payload = %s, updated_at = NOW()
            WHERE record_type = %s AND record_id = %s
            """,
            (Jsonb(updated), record_type, record_id),
        )
    return updated


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
    # Binary append mode lets Windows inspect the file length without reading a
    # byte that another process may already have locked.  Reading that byte
    # before msvcrt.locking raised PermissionError under concurrent requests.
    with (_path(name + ".lock")).open("a+b") as lock_file:
        if os.name == "nt":
            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"0")
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
    if _database_enabled():
        return _database_load("task")
    return _read_items("tasks.json")


def get_task(task_id: str) -> dict | None:
    if not isinstance(task_id, str):
        return None
    return next((task for task in load_tasks() if task.get("id") == task_id), None)


def save_task(task: dict) -> dict:
    if not isinstance(task, dict):
        return {}
    if _database_enabled():
        return _database_save(
            "task", "t", task, preserve_fields=("owner_token_hash",)
        )
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
    if _database_enabled():
        return _database_update(
            "task", task_id, task, preserve_fields=("owner_token_hash",)
        )
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
    if _database_enabled():
        return _database_load("team")
    return _read_items("teams.json")


def get_team(team_id: str) -> dict | None:
    return next((team for team in load_teams() if team.get("id") == team_id), None)


def save_team(team: dict) -> dict:
    if not isinstance(team, dict):
        return {}
    if _database_enabled():
        return _database_save("team", "team", team, force_new=True)
    with _locked_items("teams.json") as teams:
        saved = dict(team)
        saved["id"] = _next_id(teams, "team")
        saved["created_at"] = _now()
        teams.append(saved)
        return saved if _write_items(_path("teams.json"), teams) else {}


def load_proposals(task_id: str | None = None) -> list[dict]:
    proposals = (
        _database_load("proposal")
        if _database_enabled()
        else _read_items("proposals.json")
    )
    if task_id is None:
        return proposals
    return [proposal for proposal in proposals if proposal.get("task_id") == task_id]


def save_proposal(proposal: dict) -> dict:
    if not isinstance(proposal, dict):
        return {}
    if _database_enabled():
        saved = dict(proposal)
        saved["status"] = "new"
        return _database_save("proposal", "p", saved)
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
    if _database_enabled():
        return _database_transition(
            "proposal", proposal_id, "new", {"status": status}
        )
    with _locked_items("proposals.json") as proposals:
        for proposal in proposals:
            if proposal.get("id") == proposal_id and proposal.get("status") == "new":
                proposal["status"] = status
                return proposal if _write_items(_path("proposals.json"), proposals) else None
    return None


def load_progress() -> list[dict]:
    if _database_enabled():
        return _database_load("progress")
    return _read_items("progress.json")


def save_progress(progress: dict) -> dict:
    if not isinstance(progress, dict):
        return {}
    if _database_enabled():
        saved = dict(progress)
        saved.setdefault("status", "submitted")
        saved.setdefault("points", 0)
        return _database_save("progress", "progress", saved)
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
    if _database_enabled():
        return _database_transition(
            "progress",
            progress_id,
            "submitted",
            {
                "status": status,
                "points": points if status == "confirmed" else 0,
                "reviewed_at": _now(),
            },
        )
    with _locked_items("progress.json") as entries:
        for entry in entries:
            if entry.get("id") == progress_id and entry.get("status") == "submitted":
                entry["status"] = status
                entry["points"] = points if status == "confirmed" else 0
                entry["reviewed_at"] = _now()
                return entry if _write_items(_path("progress.json"), entries) else None
    return None
