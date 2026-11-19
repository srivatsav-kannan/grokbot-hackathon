import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "fairlot.db"))
    monkeypatch.setenv("GROK_API_KEY", "")
    from backend.app.main import app

    with TestClient(app) as test_client:
        yield test_client
