from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def test_ws_phone_rejects_missing_auth():
    # El server cierra la conexión durante el handshake (antes de accept()), así
    # que Starlette levanta WebSocketDisconnect ya en el `__enter__` del context
    # manager — hay que envolver el `with` entero, no solo el receive.
    try:
        with client.websocket_connect("/ws/phone"):
            pass
        raised = False
    except Exception:
        raised = True
    assert raised


def test_ws_phone_rejects_bad_token():
    try:
        with client.websocket_connect(
            "/ws/phone", headers={"Authorization": "Bearer not-the-key"}
        ) as ws:
            ws.receive_text()
        raised = False
    except Exception:
        raised = True
    assert raised


def test_ws_phone_connects_and_marks_health_as_connected():
    # network_candidates depende de las interfaces de red de la máquina que
    # corre el test, así que se valida status/phone_connected puntualmente
    # en vez de comparar el dict completo.
    with client.websocket_connect(
        "/ws/phone", headers={"Authorization": f"Bearer {settings.api_key}"}
    ):
        resp = client.get("/api/health")
        body = resp.json()
        assert body["status"] == "ok"
        assert body["phone_connected"] is True

    resp = client.get("/api/health")
    body = resp.json()
    assert body["status"] == "ok"
    assert body["phone_connected"] is False
