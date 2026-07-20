from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "phone_connected": False}


def test_chat_requires_auth():
    resp = client.post("/api/chat", json={"message": "hola"})
    assert resp.status_code == 401


def test_chat_rejects_bad_token():
    resp = client.post(
        "/api/chat",
        json={"message": "hola"},
        headers={"Authorization": "Bearer not-the-key"},
    )
    assert resp.status_code == 401


def test_fs_list_dir_tool_respects_sandbox():
    from app.tools.filesystem import _resolve

    try:
        _resolve("../../outside")
    except PermissionError:
        pass
    else:
        raise AssertionError("se esperaba PermissionError al salir de FS_ALLOWED_ROOT")
