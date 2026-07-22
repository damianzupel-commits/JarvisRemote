# JarvisRemote

Un asistente de IA **local** (no depende de ningún servicio en la nube — corre
enteramente en tu propia PC vía [LM Studio](https://lmstudio.ai)) al que le podés
dar órdenes desde tu celular o desde tu PC, y que puede **ejecutar acciones
reales** en ambos dispositivos: no solo chatea, controla.

> ⚠️ **Antes de instalar esto, leé la sección [Advertencias de
> seguridad](#️-advertencias-de-seguridad).** Este proyecto le da a un LLM
> control real y muy invasivo de tu PC y tu celular. No es un juguete — hay
> que entender el riesgo antes de prenderlo.

## Qué puede hacer

- **Control total de tu PC**: sistema de archivos (sandboxeado a una carpeta),
  control de navegador (Playwright), y control invasivo de escritorio completo
  — mouse, teclado, ventanas de cualquier programa abierto, lanzar
  aplicaciones.
- **Control total de tu Android** vía su Accessibility Service: tocar,
  deslizar, escribir y leer el contenido de **cualquier app en pantalla**
  (incluidas apps de banco o 2FA — el riesgo es real y hay que asumirlo
  explícitamente, ver más abajo).
- **Ejecución de shell real** en el celular (comandos arbitrarios, no solo UI)
  delegando en [Termux](https://termux.dev), vía su Intent `RUN_COMMAND`.
- **Visión**: puede sacar una foto o grabar un clip corto con la cámara del
  celular en silencio (sin abrir la app de Cámara) para "ver" el entorno —
  funciona con cualquier modelo de visión (VL) cargado en LM Studio (ej.
  Qwen3-VL). El video nunca se manda crudo al modelo: se extraen frames y se
  mandan como una secuencia de imágenes, el formato que sí soportan de forma
  confiable los modelos VL.
- **Acceso remoto de verdad, "desde cualquier lugar"**, sin exponer nada a
  internet: la conexión celular↔PC viaja por [Tailscale](https://tailscale.com)
  (VPN mesh privada), con failover automático a la red local (WiFi/hotspot)
  cuando ambos dispositivos están cerca, para menor latencia.
- **Roadmap**: integración con [Home Assistant](https://www.home-assistant.io)
  como hub central para que Jarvis controle dispositivos smart-home,
  impresión 3D, y builds propios (ESP32/Arduino) vía ESPHome — ver el informe
  completo para el detalle.

## Arquitectura

![Arquitectura de JarvisRemote](docs/arquitectura_jarvisremote.png)

Tres componentes:

- **`backend/`** — Python + FastAPI. Habla con LM Studio (API compatible con
  OpenAI), corre el loop del agente (tool calling), y expone `POST /api/chat`
  y `WS /ws/phone` — ambos autenticados con un Bearer token.
- **`tray-app/`** — Python + pystray. Administra el backend como subproceso
  (arrancar/parar/reiniciar si se cae) y tiene su propia ventana de chat.
- **`android-app/`** — Kotlin + Jetpack Compose. Chat contra el backend, más un
  foreground service que mantiene una conexión WebSocket saliente hacia
  `/ws/phone` para recibir y ejecutar tool calls en el celular.

No hay ningún puerto expuesto a internet: el backend escucha en tu IP privada
de Tailscale (o en la LAN local), y todas las requests requieren el Bearer
token. Ver el diagrama y el [informe completo](INFORME_COMPLETO.md) para el
detalle de cada pieza.

## Instalación rápida

Guía resumida — para el detalle completo (Termux, Tailscale, compilar la app
Android sin Android Studio, etc.) ver el [informe completo](INFORME_COMPLETO.md)
y el README de cada componente (`backend/README.md`, `tray-app/README.md`,
`android-app/README.md`).

```bash
# 1. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
copy .env.example .env    # completar API_KEY, HOST (tu IP de Tailscale), etc.
python run.py

# 2. LM Studio: cargar un modelo con soporte de tool calling (y de visión, si
#    querés que Jarvis "vea") y arrancar su servidor local (puerto 1234 default).

# 3. Tray app (opcional, recomendado): supervisa el backend en vez de correrlo suelto.
cd tray-app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python tray.py

# 4. App Android: compilar con Gradle (JDK 17 + Android SDK cmdline-tools,
#    no hace falta Android Studio completo) e instalar vía ADB. Ver
#    android-app/README.md para Tailscale, Termux y el Accessibility Service.
```

## ⚠️ Advertencias de seguridad

Este proyecto le da a un LLM **control real, no simulado**, sobre dos
dispositivos. Antes de usarlo:

- **El Accessibility Service del celular puede leer y accionar sobre
  cualquier app en pantalla**, incluidas apps de banco y 2FA. Hay un
  blocklist configurable de apps sensibles (ver Ajustes de la app), pero es
  una mitigación por nombre de paquete, **no una garantía completa** — el
  riesgo de fondo (control total de pantalla) sigue existiendo.
- **`phone_run_command` ejecuta código arbitrario** en el celular vía Termux.
  Hay un blocklist de patrones obviamente destructivos (`rm -rf /`, `mkfs`,
  fork bombs, etc.), pero es matching de texto — **no es un sandbox real**.
  Cualquier comando que no matchee esos patrones se ejecuta sin restricciones.
- **El control de escritorio de la PC** (mouse/teclado/ventanas) tiene el
  mismo nivel de invasividad que el celular, con la misma lógica de riesgo
  asumido.
- Ambas superficies invasivas (`DESKTOP_CONTROL_ENABLED`,
  `PHONE_SHELL_ENABLED`, `PHONE_CAMERA_ENABLED`) se pueden desactivar por
  variable de entorno sin tocar código si no las querés.
- Todas las acciones (tools del celular y de la PC) quedan registradas en un
  log de auditoría estructurado (`backend/audit.log`, JSON por línea) para
  poder revisar después qué hizo el agente.
- La conexión viaja por Tailscale (cifrada de punta a punta por WireGuard) o
  por LAN local en texto plano — TLS de extremo a extremo está preparado en
  el backend pero no viene activado por default (ver `backend/certs/README.md`
  antes de activarlo, corta el acceso hasta reconfigurar el lado Android).
- **No uses esto en un dispositivo con datos que no puedas permitirte
  perder o exponer**, y no lo conectes a una tailnet que comparta gente en la
  que no confiás. Es un proyecto personal pensado para que **su dueño**
  controle **sus propios** dispositivos.

## Licencia

[MIT](LICENSE) — usalo, modificalo, lo que quieras, sin garantía de ningún tipo.
