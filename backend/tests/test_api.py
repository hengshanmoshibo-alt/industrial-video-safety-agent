import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def auth_headers(client: TestClient):
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "Admin123!"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_health(client: TestClient):
    assert client.get("/health").json()["status"] == "ok"


def test_seeded_chat_answers_refund(client: TestClient):
    session_resp = client.post("/api/chat/sessions", json={"visitor_name": "测试访客"})
    assert session_resp.status_code == 200
    conversation_id = session_resp.json()["id"]
    msg_resp = client.post(f"/api/chat/sessions/{conversation_id}/messages", json={"content": "我想退款，多久到账？"})
    assert msg_resp.status_code == 200
    messages = msg_resp.json()
    assert len(messages) == 2
    assert messages[1]["sender"] == "ai"
    assert messages[1]["sources"]


def test_admin_can_list_kb_documents(client: TestClient):
    resp = client.get("/api/kb/documents", headers=auth_headers(client))
    assert resp.status_code == 200
    assert len(resp.json()) >= 12


def test_handoff_flow(client: TestClient):
    conversation_id = client.post("/api/chat/sessions", json={}).json()["id"]
    resp = client.post(f"/api/chat/sessions/{conversation_id}/handoff")
    assert resp.status_code == 200
    assert resp.json()["status"] == "waiting_agent"
