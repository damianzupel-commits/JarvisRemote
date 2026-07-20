from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    # network_candidates depende de las interfaces de red de la máquina que
    # corre el test, así que se valida su forma en vez de un valor fijo.
    assert body["status"] == "ok"
    assert body["phone_connected"] is False
    assert isinstance(body["network_candidates"], list)


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
