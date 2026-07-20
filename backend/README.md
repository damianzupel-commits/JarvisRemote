# backend

Servicio FastAPI que conecta con LM Studio y expone `POST /api/chat` para
mandarle órdenes al modelo, con un framework de tools que el LLM puede invocar.

## Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt   # incluye requirements.txt + pytest/httpx
playwright install chromium
copy .env.example .env
```

Editá `.env`:
- `API_KEY`: poné un valor fijo (si lo dejás vacío se genera uno random en cada
  arranque y lo ves en la consola, pero no persiste).
- `HOST`: idealmente tu IP de Tailscale (`tailscale ip -4`), para que el server
  literalmente no escuche fuera de la VPN.
- `LMSTUDIO_BASE_URL` / `LMSTUDIO_MODEL`: revisá en LM Studio → Developer → Local
  Server qué puerto y nombre de modelo está usando.
- `FS_ALLOWED_ROOT`: carpeta raíz a la que quedan limitadas las tools de
  filesystem.

## Correr

En LM Studio: cargar el modelo de 30B y arrancar el "Local Server" (por defecto
`http://localhost:1234`).

```bash
python run.py
```

Probar:

```bash
curl http://localhost:8000/api/health

curl -X POST http://localhost:8000/api/chat \
  -H "Authorization: Bearer TU_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Listame los archivos de mi escritorio\"}"
```

## Tests

```bash
pytest
```

## Cómo está armado

- `app/config.py` — settings desde `.env` (host/puerto, API key, LM Studio, sandbox
  de filesystem, headless del browser, tope de iteraciones del agente).
- `app/auth.py` — dependency de FastAPI que valida el header `Authorization: Bearer`.
- `app/llm_client.py` — cliente OpenAI apuntando a LM Studio.
- `app/agent.py` — el loop del agente: manda mensajes + tool schemas a LM Studio,
  ejecuta las tool calls que pida el modelo, le devuelve los resultados, repite
  hasta que conteste en texto o se llegue a `MAX_AGENT_ITERATIONS`. Guarda historial
  en memoria por `conversation_id`.
- `app/tools/__init__.py` — registry de tools (`register_tool` / `get_tools` /
  `openai_tool_schemas` / `call_tool`). Soporta handlers sync y async.
- `app/tools/filesystem.py` — `fs_list_dir`, `fs_read_file`, `fs_write_file`,
  `fs_create_dir`, `fs_move_path`, `fs_delete_path` (deshabilitada por default).
  Todo sandboxeado a `FS_ALLOWED_ROOT`.
- `app/tools/browser.py` — `browser_open`, `browser_click`, `browser_type`,
  `browser_get_text`, `browser_screenshot`, `browser_close`, con Playwright
  (Chromium, una sola página persistente entre llamadas).
- `app/main.py` — endpoints `GET /api/health` y `POST /api/chat`.

## Agregar una tool nueva

1. Crear (o reusar) un módulo en `app/tools/`.
2. Definir una función sync o async, decorada con `@register_tool(name=..., description=..., parameters=<json-schema>)`.
3. Importar el módulo al final de `app/tools/__init__.py` si es un archivo nuevo.

No hace falta tocar `agent.py` ni `main.py`: el agente arma los schemas y despacha
las tool calls automáticamente contra el registry.

## Notas de seguridad

- El backend no valida quién está del otro lado más allá del Bearer token: la
  barrera principal es que solo es alcanzable a través de tu tailnet.
- `fs_delete_path` está apagada por default (`FS_ALLOW_DELETE=false`).
- Las tools de filesystem no pueden salir de `FS_ALLOWED_ROOT`.
- El modelo necesita soportar tool/function calling en el formato de LM Studio
  para que el loop de tools funcione (la mayoría de los modelos instruct
  modernos —Qwen2.5-Instruct, Llama-3.1-Instruct, Hermes, etc.— lo soportan).
