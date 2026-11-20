import pytest
from fastapi.testclient import TestClient


def sign_in(client, email="ada@fairlot.test", password="fairlot-demo-pass"):
    response = client.post(
        "/api/auth/signup",
        json={"email": email, "password": password},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == email
    assert "password" not in body
    return body


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "fairlot.db"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("FAIRLOT_BACKGROUND", "0")
    from backend.app.main import app

    with TestClient(app) as test_client:
        yield test_client
