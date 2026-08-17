from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import main as main_module
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


def test_health_deep_reports_ok_when_the_llm_responds(monkeypatch):
    """Bug real (informe de arquitectura 2026-08-10, corregido vía Opción C):
    /api/health no ejercitaba el loop del LLM en absoluto -- un proceso con
    el agente roto lo pasaba igual. /api/health/deep hace un round-trip real
    (acá mockeado, no dependemos de Ollama corriendo para este test)."""

    async def fake_create(**kwargs):
        message = SimpleNamespace(content="ok")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setattr(main_module.client.chat.completions, "create", fake_create)

    resp = client.get("/api/health/deep")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["llm_reachable"] is True
    assert body["response_preview"] == "ok"
    assert isinstance(body["elapsed_seconds"], (int, float))


def test_health_deep_reports_error_when_the_llm_call_fails(monkeypatch):
    async def fake_create(**kwargs):
        raise RuntimeError("modelo no responde")

    monkeypatch.setattr(main_module.client.chat.completions, "create", fake_create)

    resp = client.get("/api/health/deep")

    assert resp.status_code == 200  # nunca un 500 -- el fallo del LLM es DATA, no un error del endpoint
    body = resp.json()
    assert body["status"] == "error"
    assert body["llm_reachable"] is False
    assert "modelo no responde" in body["error"]


def test_health_deep_uses_a_short_timeout_distinct_from_the_general_client_timeout(monkeypatch):
    """El timeout de /api/health/deep tiene que ser corto (chequeo de salud
    rápido) e independiente del timeout general del cliente (1800s, ver bug
    real de v6) -- si no, un LLM colgado haría esperar el chequeo de salud
    hasta media hora."""
    captured = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        message = SimpleNamespace(content="ok")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setattr(main_module.client.chat.completions, "create", fake_create)

    client.get("/api/health/deep")

    assert captured["timeout"] == main_module._HEALTH_DEEP_TIMEOUT_SECONDS
    assert captured["timeout"] < settings.llm_request_timeout_seconds


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
