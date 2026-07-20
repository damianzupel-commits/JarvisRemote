"""Tray app de Windows: arranca/para el backend y muestra su estado en la bandeja."""

import os
import threading
import time
import webbrowser

import pystray
import requests

import config
import process_manager
from chat_window import open_chat_window
from icon import build_image

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
            pystray.MenuItem("Abrir chat", open_chat_window),
            pystray.MenuItem("Abrir documentación de la API", _on_open_docs),
            pystray.MenuItem("Ver logs", _on_open_logs),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", _on_quit),
        ),
    )

    threading.Thread(target=_poll_health, args=(icon,), daemon=True).start()
    # Autoarranca el backend al abrir la tray app.
    threading.Thread(target=_on_start, args=(icon,), daemon=True).start()

    icon.run()


if __name__ == "__main__":
    main()
