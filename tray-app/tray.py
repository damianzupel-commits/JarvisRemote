"""Tray app de Windows: arranca/para el backend y muestra su estado en la bandeja."""

import logging
import os
import threading
import time
import webbrowser

import pystray
import requests

import config
import process_manager
from icon import build_image
from ui.main_window import open_chat_window

# Sin esto, todo lo que loguea voice_listener.py (logger "jarvis.voice") se pierde
# en silencio: la tray corre con pythonw.exe (sin consola) y el logging de Python
# no escribe a ningún lado sin un handler configurado explícitamente. Bug real
# encontrado en la primera prueba de voz en PC: no había forma de saber si el
# usuario había llegado a probar el toggle o no.
logging.basicConfig(
    filename=str(config.TRAY_DIR / "voice.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

_state_lock = threading.Lock()
_state = "stopped"  # stopped | starting | running | error

_LABELS = {
    "running": "Estado: corriendo",
    "starting": "Estado: iniciando...",
    "stopped": "Estado: detenido",
    "error": "Estado: caído / sin respuesta",
}


def _set_state(new_state: str) -> None:
    global _state
    with _state_lock:
        _state = new_state


def _get_state() -> str:
    with _state_lock:
        return _state


def _poll_health(icon: pystray.Icon) -> None:
    while True:
        if process_manager.is_running():
            try:
                resp = requests.get(config.HEALTH_URL, timeout=2)
                _set_state("running" if resp.ok else "error")
            except requests.RequestException:
                _set_state("starting")
        else:
            _set_state("stopped")
        icon.icon = build_image(_get_state())
        time.sleep(config.POLL_INTERVAL_SECONDS)


def _label_estado(_item) -> str:
    return _LABELS.get(_get_state(), "Estado: desconocido")


def _label_backend_url(_item) -> str:
    return f"Backend: {config.BASE_URL}"


def _on_start(icon: pystray.Icon, _item=None) -> None:
    _set_state("starting")
    msg = process_manager.start()
    icon.notify(msg, title="Jarvis backend")


def _on_stop(icon: pystray.Icon, _item=None) -> None:
    msg = process_manager.stop()
    _set_state("stopped")
    icon.notify(msg, title="Jarvis backend")


def _on_open_docs(_icon, _item) -> None:
    webbrowser.open(config.DOCS_URL)


def _on_open_logs(icon: pystray.Icon, _item) -> None:
    if config.LOG_PATH.exists() and config.LOG_PATH.stat().st_size > 0:
        os.startfile(config.LOG_PATH)  # noqa: S606 (acción local, disparada por el propio usuario)
    else:
        icon.notify("Todavía no hay logs (arrancá el backend primero).", title="Jarvis backend")


def _on_quit(icon: pystray.Icon, _item) -> None:
    # El toggle de voz ahora vive en la ventana principal (ui/main_window.py) --
    # si está prendido, se apaga solo al cerrar esa ventana (MainWindow.closeEvent).
    process_manager.stop()
    icon.stop()


def main() -> None:
    config.LOG_PATH.touch(exist_ok=True)

    icon = pystray.Icon(
        "jarvis-tray",
        build_image("stopped"),
        "Jarvis Remote",
        menu=pystray.Menu(
            pystray.MenuItem(_label_estado, None, enabled=False),
            pystray.MenuItem(_label_backend_url, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Iniciar backend", _on_start),
            pystray.MenuItem("Detener backend", _on_stop),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Abrir Jarvis", open_chat_window, default=True),
            pystray.MenuItem("Abrir documentación de la API", _on_open_docs),
            pystray.MenuItem("Ver logs", _on_open_logs),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", _on_quit),
        ),
    )

    threading.Thread(target=_poll_health, args=(icon,), daemon=True).start()
    # Autoarranca el backend al abrir la tray app.
    threading.Thread(target=_on_start, args=(icon,), daemon=True).start()
    # Autoabre la ventana principal al arrancar, para no depender del doble
    # click en el ícono de bandeja cada vez que se reinicia la tray.
    threading.Thread(target=open_chat_window, args=(icon,), daemon=True).start()

    icon.run()


if __name__ == "__main__":
    main()
