import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from core import ai, store


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client(tmp_path, monkeypatch):
    source = PROJECT_ROOT / "data"
    for filename in ("tasks.json", "teams.json", "proposals.json", "demo.json"):
        shutil.copy(source / filename, tmp_path / filename)
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(ai, "_client", lambda: None)
    with TestClient(app) as test_client:
        yield test_client

