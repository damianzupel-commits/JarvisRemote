import json
import logging
import time

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect

from .agent import run_agent
from .auth import verify_api_key
from .config import settings
from .llm_client import client
from .logging_config import configure_logging
from .models import ChatRequest, ChatResponse, ToolCallLog
from .network_info import network_candidates
from .phone_link import handle_incoming, is_phone_connected, register_phone, unregister_phone
from .routers.codebase import router as codebase_router
from .routers.obsidian import router as obsidian_router

configure_logging()
logger = logging.getLogger("jarvis.main")

app = FastAPI(title="Jarvis Remote Backend", version="0.1.0")
app.include_router(codebase_router)
app.include_router(obsidian_router)


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "phone_connected": is_phone_connected(),
        # Direcciones donde este backend es alcanzable ahora mismo, ordenadas
        # de conexión directa (hotspot WiFi de la PC / LAN) a Tailscale
        # (fallback). El celular usa esto para recordar la URL directa y
        # preferirla la próxima vez, sin dejar de tener Tailscale como red de
        # respaldo cuando no están en la misma red.
        "network_candidates": network_candidates(settings.port),
    }


# Timeout corto a propósito, distinto del timeout general del cliente
# (settings.llm_request_timeout_seconds, 1800s) -- un chequeo de salud tiene
# que responder rápido; si el LLM está genuinamente colgado, mejor reportar
# "no responde" en 30s que esperar hasta media hora.
_HEALTH_DEEP_TIMEOUT_SECONDS = 30.0


@app.get("/api/health/deep")
async def health_deep() -> dict:
    """A diferencia de /api/health (que solo confirma que el proceso HTTP
    responde), esto ejercita el loop del LLM de verdad -- un round-trip real
    y mínimo (sin tools, pocos tokens de salida) para confirmar que el modelo
    responde, no solo que el puerto está abierto.

    Prerequisito #3 de la Opción A (identificado en el informe de
    arquitectura 2026-08-10): un futuro watchdog que reinicia el backend
    después de un self-edit necesita poder distinguir "el proceso está up"
    de "el agente realmente funciona" -- un proceso con el loop del agente
    roto pasaría /api/health igual (no hace ninguna llamada real al modelo),
    así que ese endpoint solo no alcanza para verificar un self-restart."""
    start = time.monotonic()
    try:
        response = await client.chat.completions.create(
            model=settings.lmstudio_model,
            messages=[{"role": "user", "content": "Respondé solo con la palabra: ok"}],
            max_tokens=10,
            timeout=_HEALTH_DEEP_TIMEOUT_SECONDS,
        )
        elapsed = time.monotonic() - start
        content = (response.choices[0].message.content or "").strip()
        return {
            "status": "ok",
            "llm_reachable": True,
            "elapsed_seconds": round(elapsed, 2),
            "response_preview": content[:50],
        }
    except Exception as exc:
        elapsed = time.monotonic() - start
        return {
            "status": "error",
            "llm_reachable": False,
            "elapsed_seconds": round(elapsed, 2),
            "error": str(exc),
        }


@app.post("/api/chat", response_model=ChatResponse, dependencies=[Depends(verify_api_key)])
async def chat(req: ChatRequest) -> ChatResponse:
    conv_id, reply, tool_calls = await run_agent(req.message, req.conversation_id)
    return ChatResponse(
        conversation_id=conv_id,
        reply=reply,
        tool_calls=[ToolCallLog(**tc) for tc in tool_calls],
    )


def _check_bearer(authorization: str | None) -> bool:
    if not authorization or not authorization.startswith("Bearer "):
        return False
    return authorization.removeprefix("Bearer ").strip() == settings.api_key


@app.websocket("/ws/phone")
async def phone_ws(websocket: WebSocket) -> None:
    """Conexión saliente del celular. Se autentica con el mismo Bearer token que
    `/api/chat`, mandado como header `Authorization` en el handshake del WebSocket.

    Mientras esté conectado, las tools con `target="phone"` (ver `tools/phone.py`)
    se despachan acá adentro y esperan la respuesta correlacionada por id
    (ver `phone_link.dispatch_to_phone` / `handle_incoming`).
    """
    if not _check_bearer(websocket.headers.get("authorization")):
        await websocket.close(code=4401)
        return

    await websocket.accept()
    await register_phone(websocket)
    logger.info("phone_link: celular conectado")
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("phone_link: mensaje no-JSON ignorado")
                continue
            await handle_incoming(message)
    except WebSocketDisconnect:
        pass
    finally:
        await unregister_phone(websocket)
        logger.info("phone_link: celular desconectado")
