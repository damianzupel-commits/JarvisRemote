# JarvisRemote

Controlá tu LLM local ("Jarvis", servido con LM Studio) desde el celular, desde
cualquier lugar, con capacidad de ejecutar acciones reales en tu PC
(sistema de archivos, control del navegador, y lo que se agregue después).

## Arquitectura

```
Celular (Android) ──Tailscale VPN──▶ PC Windows
    │                                  │
    │ WebSocket saliente               ├─ backend (FastAPI, Python)
    │ (/ws/phone, foreground service)  │    ├─ habla con LM Studio (localhost:1234, OpenAI-compatible)
    └──────────────────────────────────▶    └─ expone tools que el LLM puede invocar, ruteadas por
                                       │         `target: pc|phone` (filesystem, browser en PC;
                                       │         filesystem SAF + Accessibility Service en el celular)
                                       │
                                       └─ tray-app (Python + pystray)
                                            corre/administra el backend y muestra estado
```

Además de `POST /api/chat` (celular → backend), el backend expone `/ws/phone`: una
conexión WebSocket **saliente desde el celular** (mantenida por un foreground service
en la app Android), autenticada con el mismo Bearer token. Mientras esté conectado, el
LLM puede invocar tools con `target="phone"` (`phone_open_app`, `phone_list_dir`,
`phone_read_file`, `phone_write_file`, `phone_tap`, `phone_swipe`, `phone_type_text`,
`phone_read_screen`, `phone_global_action`) que se despachan al celular y esperan la
respuesta correlacionada por id (ver `backend/app/phone_link.py` y
`backend/app/tools/phone.py`). El control de pantalla usa el Accessibility Service de
Android (control total, riesgo asumido explícitamente); el filesystem del celular está
sandboxeado a una carpeta elegida una vez vía Storage Access Framework (mismo modelo
que `FS_ALLOWED_ROOT` para la PC).

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
| Conexión local | Hotspot WiFi de la PC (sin router ni internet) como alternativa a Tailscale cuando están en la misma habitación — ver Roadmap | Evitar depender de Tailscale/internet cuando el celular está al lado de la PC |
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
4. ✅ Backend: `/ws/phone` + tools `target="phone"` (routing por campo `target`, ver `backend/app/phone_link.py`)
5. ✅ App Android: control total del celular — foreground service con WebSocket saliente,
   Accessibility Service (tap/swipe/type/read/global-action), filesystem vía SAF
   (`android-app/.../phone/`). Falta compilar y probar en un dispositivo real.
6. ⬜ Más tools de PC (procesos, shell, notificaciones, etc.) una vez que el loop básico esté probado
7. ⬜ Hotspot WiFi local como alternativa a Tailscale cuando el celular y la PC están en la
   misma habitación (sin depender de router externo ni de internet). Implementación
   planteada:
   - PC: crear el hotspot con `netsh wlan set hostednetwork` o la API moderna
     "Mobile Hotspot" de Windows (`Windows.Networking.NetworkOperators` vía WinRT), con
     SSID/password fijos guardados en la config del backend.
   - Backend: bindear también en la IP que le asigna la interfaz del hotspot (además de
     la IP de Tailscale), o escuchar en `0.0.0.0` puerto no expuesto a internet gracias a
     que el hotspot no tiene salida a internet.
   - App Android: al conectar, probar primero la URL LAN del hotspot (rápido timeout) y
     si falla, caer a la URL de Tailscale — mismo Bearer token para ambas, el backend no
     necesita distinguir el origen.
   - No es prioridad inmediata: el foco actual es terminar de compilar el APK.
