"""Cliente para Gemini Flash (Google AI Studio, free tier) -- usado por
app/tools/cloud_expert.py. Mismo patrón que app/llm_client.py (cliente
AsyncOpenAI reusado, sin escribir un cliente REST propio): Google publica un
endpoint OpenAI-compatible real para Gemini
(generativelanguage.googleapis.com/v1beta/openai/), así que apuntar el SDK de
OpenAI ahí funciona igual que con LM Studio/Ollama en local.

Cliente separado de `llm_client.client` a propósito -- son dos proveedores
distintos (local vs. cloud) con API keys, timeouts y modelos propios; nunca
deberían compartir instancia."""

from openai import AsyncOpenAI

from .config import settings

client = AsyncOpenAI(
    base_url=settings.google_ai_base_url,
    api_key=settings.google_ai_api_key or "sin-configurar",
    max_retries=0,
)
