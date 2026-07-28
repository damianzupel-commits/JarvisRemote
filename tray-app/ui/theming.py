"""Utilidad de theming compartida entre main_window.py y settings_window.py.

Vive en su propio módulo (en vez de definirse en main_window.py e importarse
desde ahí) para que las dos ventanas puedan usarla sin crear un import
circular entre ellas (main_window importa SettingsDialog, así que
settings_window no puede a la vez importar de main_window).
"""

import ctypes
import sys


def force_dark_title_bar(widget) -> None:
    """Le pide a Windows que pinte la barra de título nativa (la que dibuja el
    propio SO, fuera del alcance de cualquier QSS) en oscuro, para que
    acompañe al resto de la ventana. Sin esto quedaba una franja blanca
    arriba de un contenido todo oscuro -- tema oscuro fijo pedido por Damian,
    sin opción de volver a claro. No existe en versiones viejas de Windows --
    si falla, se ignora, la ventana sigue siendo usable con la barra de
    título default."""
    if sys.platform != "win32":
        return
    try:
        hwnd = int(widget.winId())
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value)
        )
    except Exception:
        pass
