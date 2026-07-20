import json
import logging

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect

from .agent import run_agent
from .auth import verify_api_key
from .config import settings
from .logging_config import configure_logging
from .models import ChatRequest, ChatResponse, ToolCallLog
from .phone_link import handle_incoming, is_phone_connected, register_phone, unregister_phone

configure_logging()
logger = logging.getLogger("jarvis.main")

app = FastAPI(title="Jarvis Remote Backend", version="0.1.0")


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "phone_connected": is_phone_connected()}


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
