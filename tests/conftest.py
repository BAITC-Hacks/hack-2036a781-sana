import shutil
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from core import ai, store


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_OWNER_TOKEN = "owner-token-for-api-tests-with-enough-length"
TEST_TEAM_TOKEN = "team-token-for-api-tests-with-enough-length"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SANA_LEGACY_MODE", "1")
    source = PROJECT_ROOT / "data"
    for filename in ("tasks.json", "teams.json", "proposals.json", "demo.json"):
        shutil.copy(source / filename, tmp_path / filename)
    for filename, field, token in (
        ("tasks.json", "owner_token_hash", TEST_OWNER_TOKEN),
        ("teams.json", "team_token_hash", TEST_TEAM_TOKEN),
    ):
        path = tmp_path / filename
        rows = json.loads(path.read_text(encoding="utf-8"))
        for row in rows:
            row[field] = hashlib.sha256(token.encode("utf-8")).hexdigest()
        path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "DATABASE_URL", "")
    monkeypatch.setattr(ai, "_client", lambda: None)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def fresh_client(tmp_path, monkeypatch):
    monkeypatch.setenv("SANA_LEGACY_MODE", "1")
    """A real first run starts with no sample tasks or teams."""
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "DATABASE_URL", "")
    monkeypatch.setattr(ai, "_client", lambda: None)
    with TestClient(app) as test_client:
        yield test_client
