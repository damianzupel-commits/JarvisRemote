# JarvisRemote

Controlá tu LLM local ("Jarvis", servido con LM Studio) desde el celular, desde
cualquier lugar, con capacidad de ejecutar acciones reales en tu PC
(sistema de archivos, control del navegador, y lo que se agregue después).

## Arquitectura

```
Celular (Android) ──Tailscale VPN──▶ PC Windows
                                       │
                                       ├─ backend (FastAPI, Python)
                                       │    ├─ habla con LM Studio (localhost:1234, OpenAI-compatible)
                                       │    └─ expone tools que el LLM puede invocar
                                       │         (filesystem, browser automation, ...)
                                       │
                                       └─ tray-app (Python + pystray)
                                            corre/administra el backend y muestra estado
```

No hay ningún puerto expuesto a internet. El backend escucha en la IP privada que te da
Tailscale (`100.x.x.x`), y solo dispositivos dentro de tu tailnet (tu PC y tu celular)
pueden llegar a él. Además todas las requests requieren un Bearer token (API key).

## Repo

- **`backend/`** — servicio Python/FastAPI. Conecta con LM Studio, corre el loop del
  agente (tool calling), expone `POST /api/chat` autenticado. **Ya scaffoldeado, ver
  `backend/README.md`.**
- **`tray-app/`** — tray app de Windows (Python + pystray) que arranca/para el backend
  como subproceso y muestra su estado (corriendo / iniciando / caído). **Ya
  scaffoldeado, ver `tray-app/README.md`.**
- **`android-app/`** — app nativa Android (Kotlin + Jetpack Compose) que le pega al
  backend vía Tailscale: mandás un mensaje/orden, ves la respuesta y el log de tools
  ejecutadas. **Scaffoldeada pero no compilada en esta máquina** (no hay Android SDK
  instalado acá) — ver `android-app/README.md` para abrirla en Android Studio.

## Decisiones técnicas (ya tomadas)

| Pieza | Elección | Por qué |
|---|---|---|
| Modelo | 30B vía LM Studio, API OpenAI-compatible en `localhost:1234` | Ya definido por vos |
| Backend | Python + FastAPI | Ecosistema estándar para agentes LLM, Playwright para browser, mismo lenguaje que el tray |
| Tool calling | Formato "tools" de OpenAI (function calling) contra LM Studio | LM Studio expone ese mismo formato; requiere un modelo con soporte de tool calling |
| Auth | Bearer token estático (API key) por header `Authorization` | Simple, suficiente detrás de Tailscale |
| Acceso remoto | Tailscale (VPN mesh privada), backend bindeado a la IP de Tailscale | Pedido explícito: evitar exponer nada a internet |
| Tray app | Python + pystray | Mismo lenguaje que el backend, liviano, sin necesidad de Electron/.NET |
| App Android | Kotlin + Jetpack Compose, Retrofit/OkHttp | Stack nativo estándar actual para Android |

## Quickstart (backend)

Ver `backend/README.md` para el detalle. Resumen:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
copy .env.example .env    # y completar API_KEY, HOST (tu IP de tailscale), etc.
python run.py
```

## Roadmap

1. ✅ Backend: conexión a LM Studio + framework de tools (filesystem, browser)
2. ✅ Tray app de Windows que administra el backend
3. ✅ App Android (Kotlin + Compose) — scaffoldeada; falta compilarla en una máquina con Android Studio
4. ⬜ Más tools (procesos, shell, notificaciones, etc.) una vez que el loop básico esté probado
