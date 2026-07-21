"""Ventana de chat (Tkinter, stdlib) para hablarle a Jarvis desde la PC.

Pega al mismo `POST /api/chat` que usa la app Android, así que ve las mismas
tools: filesystem/browser locales (target="pc") y, si el celular está
conectado por WS al backend, también las de target="phone" (tocar, escribir,
leer pantalla, etc. en el celular) — control bidireccional real desde un
único backend.

Corre en su propio hilo con su propio `tk.Tk()`, separado del loop de
pystray (que ya ocupa el hilo principal en `tray.py`).
"""

import threading
import tkinter as tk
from tkinter import scrolledtext

import requests

import config

_lock = threading.Lock()
_active_root: tk.Tk | None = None

PHONE_STATUS_POLL_SECONDS = 5


def open_chat_window(icon=None, item=None) -> None:
    """Abre la ventana de chat, o trae al frente la que ya está abierta."""
    global _active_root
    with _lock:
        root = _active_root
    if root is not None:
        try:
            root.deiconify()
            root.lift()
            root.focus_force()
            return
        except tk.TclError:
            pass  # la ventana ya se cerró; sigue abajo y crea una nueva
    threading.Thread(target=_run_window, daemon=True).start()


def _run_window() -> None:
    global _active_root
    root = tk.Tk()
    with _lock:
        _active_root = root
    root.title("Jarvis - Chat (PC)")
    root.geometry("480x600")

    conversation_id: list[str | None] = [None]

    phone_status_label = tk.Label(
        root, text="Celular: consultando...", fg="gray", anchor="w"
    )
    phone_status_label.pack(fill="x", padx=8, pady=(8, 0))

    history = scrolledtext.ScrolledText(root, wrap="word", state="disabled")
    history.pack(fill="both", expand=True, padx=8, pady=(4, 4))

    entry_frame = tk.Frame(root)
    entry_frame.pack(fill="x", padx=8, pady=(0, 8))

    entry = tk.Entry(entry_frame)
    entry.pack(side="left", fill="x", expand=True)
    entry.focus_set()

    send_button = tk.Button(entry_frame, text="Enviar")
    send_button.pack(side="left", padx=(6, 0))

    def _append(text: str) -> None:
        history.configure(state="normal")
        history.insert("end", text + "\n")
        history.configure(state="disabled")
        history.see("end")

    def _send(_event=None) -> None:
        message = entry.get().strip()
        if not message:
            return
        entry.delete(0, "end")
        send_button.configure(state="disabled")
        _append(f"Vos: {message}")

        def _worker() -> None:
            try:
                resp = requests.post(
                    config.CHAT_URL,
                    json={"message": message, "conversation_id": conversation_id[0]},
                    headers={"Authorization": f"Bearer {config.API_KEY}"},
                    timeout=180,
                )
                if resp.status_code == 401:
                    root.after(
                        0, _append, "Jarvis: error 401 (API_KEY inválida — revisá backend/.env)."
                    )
                    return
                resp.raise_for_status()
                data = resp.json()
                conversation_id[0] = data.get("conversation_id")
                tool_calls = data.get("tool_calls") or []
                if tool_calls:
                    names = ", ".join(tc.get("tool", "?") for tc in tool_calls)
                    root.after(0, _append, f"[tools ejecutadas: {names}]")
                root.after(0, _append, f"Jarvis: {data.get('reply', '')}")
            except requests.RequestException as exc:
                root.after(0, _append, f"Jarvis: error de conexión ({exc}).")
            finally:
                root.after(0, lambda: send_button.configure(state="normal"))

        threading.Thread(target=_worker, daemon=True).start()

    send_button.configure(command=_send)
    entry.bind("<Return>", _send)

    stop_polling = threading.Event()

    def _set_phone_status(connected: bool | None) -> None:
        if connected is True:
            phone_status_label.configure(text="Celular: conectado", fg="#1a7f37")
        elif connected is False:
            phone_status_label.configure(text="Celular: desconectado", fg="#b91c1c")
        else:
            phone_status_label.configure(text="Celular: sin datos (backend no responde)", fg="gray")

    def _poll_phone_status() -> None:
        while not stop_polling.is_set():
            try:
                resp = requests.get(config.HEALTH_URL, timeout=5)
                resp.raise_for_status()
                connected = bool(resp.json().get("phone_connected"))
                root.after(0, _set_phone_status, connected)
            except requests.RequestException:
                root.after(0, _set_phone_status, None)
            stop_polling.wait(PHONE_STATUS_POLL_SECONDS)

    threading.Thread(target=_poll_phone_status, daemon=True).start()

    def _on_close() -> None:
        global _active_root
        stop_polling.set()
        with _lock:
            _active_root = None
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", _on_close)

    if not config.API_KEY:
        _append("[!] backend/.env no tiene API_KEY seteado - las requests van a fallar con 401.")

    root.mainloop()
