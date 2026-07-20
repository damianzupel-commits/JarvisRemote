from fastapi import Depends, FastAPI

from .agent import run_agent
from .auth import verify_api_key
from .logging_config import configure_logging
from .models import ChatRequest, ChatResponse, ToolCallLog

configure_logging()

app = FastAPI(title="Jarvis Remote Backend", version="0.1.0")


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse, dependencies=[Depends(verify_api_key)])
async def chat(req: ChatRequest) -> ChatResponse:
    conv_id, reply, tool_calls = await run_agent(req.message, req.conversation_id)
    return ChatResponse(
        conversation_id=conv_id,
        reply=reply,
        tool_calls=[ToolCallLog(**tc) for tc in tool_calls],
    )
