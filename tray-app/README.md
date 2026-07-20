# tray-app

Tray app de Windows que arranca/administra el `backend` como subproceso y
muestra su estado desde un ícono en la bandeja del sistema.

## Setup

```bash
cd tray-app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Requiere que `backend/` ya tenga su propio venv con las dependencias instaladas
(ver `backend/README.md`) — la tray usa `backend/.venv/Scripts/python.exe` para
lanzar `run.py`. Si ese venv no existe, cae a `python` del PATH.

## Correr

```bash
python tray.py
```

(Para que no abra una consola visible, usar `pythonw.exe tray.py` en su lugar.)

Al arrancar:
- Autoarranca el backend como subproceso (`backend/run.py`), con stdout/stderr
  redirigidos a `tray-app/backend.log`.
- Empieza a hacer poll a `GET /api/health` cada `POLL_INTERVAL_SECONDS` (default 3s)
  y pinta el ícono según el estado: verde (corriendo), amarillo (iniciando),
  gris (detenido), rojo (caído / no responde).

Menú del ícono (click derecho / click):
- **Estado: ...** / **Backend: http://...** — informativos.
- **Iniciar backend** / **Detener backend**.
- **Abrir chat** — abre una ventana de chat (Tkinter) para hablarle a Jarvis
  desde la PC contra el mismo `POST /api/chat` que usa la app Android: mismas
  tools, incluidas las de `target="phone"` si el celular está conectado por
  WS (control bidireccional PC↔celular desde un único backend). Usa
  `API_KEY` de `backend/.env` (mismo `.env` que ya lee `config.py`).
- **Abrir documentación de la API** — abre `/docs` (Swagger) del backend en el navegador.
- **Ver logs** — abre `backend.log` con la app asociada a `.log` (normalmente el Bloc de notas).
- **Salir** — para el backend y cierra la tray.

## Cómo está armado

- `config.py` — lee `backend/.env` (mismo HOST/PORT que usa el backend) y arma
  las URLs de health/docs, y resuelve qué intérprete de Python usar para
  lanzar el backend.
- `process_manager.py` — `start()` / `stop()` / `is_running()` sobre un
  `subprocess.Popen` del backend.
- `icon.py` — dibuja el ícono (círculo de color + "J") con Pillow, sin
  depender de un archivo `.png` en el repo.
- `tray.py` — arma el menú de `pystray`, el thread de polling de salud, y
  conecta los callbacks del menú con `process_manager`.

## Arrancar con Windows (opcional, manual)

No lo automatizamos para no tocar la configuración de arranque de tu sistema
sin que lo hagas vos explícitamente. Si querés que la tray arranque sola con
Windows: creá un acceso directo a

```
pythonw.exe C:\Users\dam\Documents\JarvisRemote\tray-app\tray.py
```

(usando el `pythonw.exe` del venv de `tray-app`) y ponelo en tu carpeta de
inicio (`Win+R` → `shell:startup`).

## Notas

- La tray asume que `backend/.env` ya existe (copiado desde `.env.example`)
  con `HOST`/`PORT` configurados.
- Si `HOST` en `.env` es `0.0.0.0`, la tray igual le pega al backend por
  `127.0.0.1` (bind-all no es una dirección a la que se pueda conectar un cliente).
