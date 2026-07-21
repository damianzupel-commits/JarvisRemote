# JarvisRemote

Controlá tu LLM local ("Jarvis", servido con LM Studio) desde el celular, desde
cualquier lugar, con capacidad de ejecutar acciones reales en tu PC
(sistema de archivos, control del navegador, control invasivo del escritorio
completo, y lo que se agregue después).

## Arquitectura

```
Celular (Android) ──Tailscale VPN──▶ PC Windows
    │                                  │
    │ WebSocket saliente               ├─ backend (FastAPI, Python)
    │ (/ws/phone, foreground service)  │    ├─ habla con LM Studio (localhost:1234, OpenAI-compatible)
    └──────────────────────────────────▶    └─ expone tools que el LLM puede invocar, ruteadas por
                                       │         `target: pc|phone` (filesystem, browser y control
                                       │         invasivo de escritorio —mouse/teclado/ventanas— en PC;
                                       │         filesystem SAF + Accessibility Service + shell real
                                       │         vía Termux en el celular)
                                       │
                                       └─ tray-app (Python + pystray)
                                            corre/administra el backend y muestra estado
```

Además de `POST /api/chat` (celular → backend), el backend expone `/ws/phone`: una
conexión WebSocket **saliente desde el celular** (mantenida por un foreground service
en la app Android), autenticada con el mismo Bearer token. Mientras esté conectado, el
LLM puede invocar tools con `target="phone"` (`phone_open_app`, `phone_list_dir`,
`phone_read_file`, `phone_write_file`, `phone_tap`, `phone_swipe`, `phone_type_text`,
`phone_read_screen`, `phone_global_action`, `phone_run_command`) que se despachan al
celular y esperan la respuesta correlacionada por id (ver `backend/app/phone_link.py` y
`backend/app/tools/phone.py`). El control de pantalla usa el Accessibility Service de
Android (control total, riesgo asumido explícitamente); el filesystem del celular está
sandboxeado a una carpeta elegida una vez vía Storage Access Framework (mismo modelo
que `FS_ALLOWED_ROOT` para la PC); `phone_run_command` ejecuta shell real dentro de
Termux vía su Intent RUN_COMMAND — el nivel más invasivo posible, código arbitrario en
vez de solo UI, y requiere pasos manuales de setup (ver `android-app/README.md`).

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
6. ✅ Control invasivo de escritorio en la PC (paridad con el celular): `app/tools/desktop.py`
   (screenshot, listar/enfocar ventanas, click por coordenadas o por control de UI Automation,
   escribir texto, teclas/combos, mover mouse, scroll, `desktop_launch_app`), vía `pywinauto` +
   `pyautogui`. Flag `DESKTOP_CONTROL_ENABLED` (default `true`) y log de auditoría
   (`jarvis.desktop`) — ver `backend/README.md`. Validado en vivo contra el agente real corriendo
   (abrir el Bloc de notas y escribirle texto, de punta a punta) — encontró y arregló 3 bugs reales
   que los tests mockeados no detectaban: foco no garantizado al lanzar una app (ahora
   `desktop_launch_app` espera la ventana nueva y fuerza foreground), `SetForegroundWindow` de
   pywin32 lanzando excepción en vez de fallar en silencio, y matching de ventanas por substring de
   título ambiguo con varias instancias de la misma app (ahora `desktop_focus_window` acepta `pid`).
   ⬜ Más tools de PC (procesos, notificaciones, etc.) si hace falta más adelante.
7. ✅ Ejecución de shell REAL en el celular vía Termux: `phone_run_command`
   (`backend/app/tools/phone.py`) + `TermuxCommandRunner`/`TermuxResultService`
   (`android-app/.../phone/`), usando el Intent RUN_COMMAND de Termux. El nivel más invasivo
   posible del lado del celular — código arbitrario, no solo UI. Flag `PHONE_SHELL_ENABLED`
   (default `true`) y log de auditoría (`jarvis.phone_link`) — ver `backend/README.md`. Compila
   limpio (`gradlew.bat assembleDebug` → BUILD SUCCESSFUL) pero **no se pudo validar en vivo**:
   requiere que el usuario instale Termux desde F-Droid, configure `allow-external-apps=true`, y
   otorgue el permiso `com.termux.permission.RUN_COMMAND` — los tres son pasos manuales, ver
   `android-app/README.md` para el detalle y lo específico que falta probar (sobre todo si Termux
   preserva el extra de correlación al mandar el resultado por PendingIntent).
8. 🔶 Hotspot WiFi local como alternativa a Tailscale cuando el celular y la PC están en la
   misma habitación (sin depender de router externo ni de internet).
   - ✅ Backend: como ya escucha en `0.0.0.0` (default de `HOST`), acepta conexiones por
     cualquier interfaz simultáneamente — Tailscale y hotspot/LAN a la vez, sin config
     extra. `GET /api/health` ahora devuelve `network_candidates`: la lista de IPs propias
     detectadas (`backend/app/network_info.py`), clasificadas como `hotspot`
     (`192.168.137.0/24`, subnet default de Windows Mobile Hotspot/ICS), `lan` (resto de
     RFC1918) o `tailscale` (`100.64.0.0/10`), ordenadas conexión directa primero y
     Tailscale al final como fallback. Las IPs públicas nunca se listan.
   - ⬜ PC: crear el hotspot en sí con `netsh wlan set hostednetwork` o la API moderna
     "Mobile Hotspot" de Windows (`Windows.Networking.NetworkOperators` vía WinRT), con
     SSID/password fijos.
   - ⬜ App Android: hoy solo guarda una única `backendUrl` (ver
     `SettingsRepository.kt`) y no consume `network_candidates` todavía. Falta: guardar la
     última URL directa (`hotspot`/`lan`) vista en `network_candidates`, y al conectar
     (REST en `ApiClientProvider`/`ChatRepository`, WS en `PhoneLinkService`) probarla
     primero con timeout corto antes de caer a la `backendUrl` (Tailscale) guardada —
     mismo Bearer token para ambas, no hace falta que el backend distinga el origen.
   - No es prioridad inmediata: el foco actual es terminar de compilar el APK.
