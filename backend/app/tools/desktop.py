"""Tools de control de escritorio de la PC: mouse, teclado, ventanas y captura de
pantalla de CUALQUIER app corriendo en la sesión de Windows del usuario.

Combina `pywinauto` (UI Automation de Windows — árbol semántico de controles,
similar en espíritu al Accessibility Service de Android) con `pyautogui`
(mouse/teclado/captura por coordenadas, más simple, usado como respaldo cuando
no hace falta o no conviene apuntar por control).

Es tan invasivo como el Accessibility Service del celular (ver `phone.py`): la
IA puede ver y accionar sobre cualquier cosa en pantalla, incluidas apps de
banca, contraseñas y 2FA. Riesgo asumido explícitamente por el usuario para la
PC, igual que ya lo había aceptado para el celular. Se puede apagar entero con
`DESKTOP_CONTROL_ENABLED=false` en `backend/.env` (ver `config.py`).

Cada acción se loguea (función, argumentos, timestamp) vía el logger
`jarvis.desktop`, como rastro de auditoría dado el nivel de riesgo.

Limitación real de Windows (no un bug de este módulo): ventanas elevadas (UAC,
"Ejecutar como administrador", instaladores, Task Manager elevado) no se
pueden controlar desde un proceso no elevado por UIPI (User Interface
Privilege Isolation). Se detecta y se devuelve un error claro donde se puede
(`ElevatedWindowError`), pero pyautogui en particular puede mandar clicks/teclas
"al vacío" sin tirar ningún error cuando el foco está en una ventana elevada —
eso no se puede detectar de forma confiable desde acá.

`desktop_launch_app` tiene un blocklist de utilidades de Windows obviamente
destructivas (`_check_launch_blocklist`) — mitigación de "evitar el desastre
obvio" por matching de texto, no un sandbox real. El resto de las tools
(click, type, scroll) no tienen un análogo: no hay forma razonable de inferir
intención destructiva de coordenadas o texto genérico.
"""

import logging
import os
import re
import subprocess
import time
from functools import wraps
from typing import Optional

import pyautogui
from pywinauto import Desktop

from ..config import settings
from . import register_tool

logger = logging.getLogger("jarvis.desktop")

# Blocklist liviano para desktop_launch_app: mitigación de "evitar el desastre
# obvio" análoga a la de phone_run_command (ver phone_link._check_command_blocklist),
# NO un sandbox real. Bloquea lanzar utilidades de Windows conocidas por ser
# destructivas (formatear, borrar particiones/shadow copies, tocar la config de
# arranque) por nombre/patrón. El resto de las tools de escritorio (click, type,
# scroll) no tienen un análogo razonable acá: no hay forma de inferir "intención
# destructiva" a partir de coordenadas o texto genérico tipeado.
_DESTRUCTIVE_LAUNCH_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("format (formatear un disco)", re.compile(r"\bformat(\.com)?\b", re.IGNORECASE)),
    ("diskpart (partición de discos)", re.compile(r"\bdiskpart(\.exe)?\b", re.IGNORECASE)),
    ("cipher /w (borrado seguro de espacio libre)", re.compile(r"\bcipher\b[^\n]*\s/w\b", re.IGNORECASE)),
    ("vssadmin delete (borra shadow copies/backups)", re.compile(r"\bvssadmin\b[^\n]*\bdelete\b", re.IGNORECASE)),
    ("bcdedit (config de arranque)", re.compile(r"\bbcdedit(\.exe)?\b", re.IGNORECASE)),
]


class DestructiveLaunchBlockedError(PermissionError):
    """El path_or_name matcheó el blocklist de utilidades obviamente destructivas."""


def _check_launch_blocklist(path_or_name: str) -> None:
    for name, pattern in _DESTRUCTIVE_LAUNCH_PATTERNS:
        if pattern.search(path_or_name):
            logger.warning("desktop_launch_app: lanzamiento BLOQUEADO (%s): %r", name, path_or_name)
            raise DestructiveLaunchBlockedError(
                f"Lanzamiento rechazado por el blocklist de seguridad (patrón: {name}). "
                "Es una mitigación de 'evitar el desastre obvio' por matching de texto, "
                "no un sandbox real."
            )

# Cuánto esperar (polling) a que aparezca una ventana nueva después de lanzar
# una app, y con qué intervalo. Ver desktop_launch_app: el estado de foco no
# se puede asumir por default (una app puede heredar estado minimizado de una
# sesión anterior), así que se detecta la ventana nueva y se fuerza al frente.
_WINDOW_APPEAR_TIMEOUT = 5.0
_WINDOW_APPEAR_POLL_INTERVAL = 0.3

# Comportamiento de pyautogui: no interrumpir la escritura por typos, y dejar
# el fail-safe (mover el mouse a una esquina aborta) en su default `True` como
# red de seguridad manual para el usuario.
pyautogui.PAUSE = 0.05

_ELEVATION_MARKERS = ("access is denied", "-2147024891", "el acceso es denegado")


class DesktopControlDisabled(RuntimeError):
    pass


class ElevatedWindowError(RuntimeError):
    pass


def _check_enabled() -> None:
    if not settings.desktop_control_enabled:
        raise DesktopControlDisabled(
            "Control de escritorio deshabilitado. Setear DESKTOP_CONTROL_ENABLED=true "
            "en backend/.env para habilitarlo."
        )


def _reraise_if_elevation(exc: Exception) -> None:
    text = str(exc).lower()
    if any(marker in text for marker in _ELEVATION_MARKERS):
        raise ElevatedWindowError(
            "No se pudo interactuar con la ventana: probablemente está elevada "
            "(ejecutada como administrador / UAC) y Windows (UIPI) bloquea la "
            "entrada de un proceso no elevado. No hay forma de controlarla desde acá."
        ) from exc


def _audited(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        _check_enabled()
        logger.info("desktop_action name=%s args=%s kwargs=%s", fn.__name__, args, kwargs)
        try:
            return fn(*args, **kwargs)
        except (DesktopControlDisabled, ElevatedWindowError):
            raise
        except Exception as exc:
            _reraise_if_elevation(exc)
            logger.warning("desktop_action failed name=%s error=%s", fn.__name__, exc)
            raise

    return wrapper


def _process_name(pid: int) -> Optional[str]:
    try:
        import win32api
        import win32con
        import win32process

        handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        try:
            return win32process.GetModuleFileNameEx(handle, 0).rsplit("\\", 1)[-1]
        finally:
            win32api.CloseHandle(handle)
    except Exception:
        return None


def _enum_visible_titled_windows() -> dict:
    """hwnd -> (título, pid) de las ventanas top-level visibles con título no vacío.

    Usa `win32gui.EnumWindows` directo (no pywinauto/UIA) a propósito: es mucho
    más liviano, porque esto se llama repetidas veces en un loop de polling
    justo después de lanzar una app (ver `_wait_for_new_window`).
    """
    import win32gui
    import win32process

    results: dict = {}

    def _callback(hwnd, _):
        title = win32gui.GetWindowText(hwnd)
        if title and win32gui.IsWindowVisible(hwnd):
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            results[hwnd] = (title, pid)

    win32gui.EnumWindows(_callback, None)
    return results


def _wait_for_new_window(before: dict, timeout: float = _WINDOW_APPEAR_TIMEOUT):
    """Poll hasta `timeout` segundos esperando que aparezca una ventana top-level
    visible con título que no estuviera en el snapshot `before`. Devuelve
    (hwnd, título, pid) de la primera que aparece, o None si no aparece ninguna
    dentro del timeout (ej. porque la acción reutilizó una ventana ya abierta,
    como una URL que abre una pestaña nueva en un navegador ya corriendo).
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        after = _enum_visible_titled_windows()
        new_hwnds = [h for h in after if h not in before]
        if new_hwnds:
            hwnd = new_hwnds[0]
            title, pid = after[hwnd]
            return hwnd, title, pid
        time.sleep(_WINDOW_APPEAR_POLL_INTERVAL)
    return None


def _foreground_window(hwnd: int) -> bool:
    """Fuerza la ventana a primer plano sin importar su estado previo (minimizada,
    heredado de una sesión anterior, etc.) y confirma si realmente quedó al
    frente. Windows puede bloquear el foreground-switch (política de
    "foreground lock") de dos formas distintas: devolviendo FALSE en silencio
    (por eso se verifica con GetForegroundWindow en vez de asumir éxito), o
    lanzando un pywintypes.error con winerror 0 y sin mensaje — un quirk
    conocido de SetForegroundWindow/ShowWindow vía pywin32 cuando el API de
    Win32 devuelve FALSE sin setear un código de error real. Ambos casos se
    tratan igual: no encontró foco real, no es una excepción de la tool.
    """
    import pywintypes
    import win32con
    import win32gui

    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
    except pywintypes.error as exc:
        logger.warning("_foreground_window: SetForegroundWindow/ShowWindow rechazado: %s", exc)
        return False
    return win32gui.GetForegroundWindow() == hwnd


def _find_window(title: str):
    windows = Desktop(backend="uia").windows()
    matches = [w for w in windows if title.lower() in (w.window_text() or "").lower()]
    if not matches:
        raise ValueError(f"No se encontró ninguna ventana con título que contenga '{title}'")
    return matches[0]


def _find_window_by_pid(pid: int):
    """Busca por pid exacto en vez de por substring de título — a diferencia de
    `_find_window`, no tiene ambigüedad posible: sirve para apuntar a la ventana
    de un proceso específico (ej. el que acaba de lanzar desktop_launch_app)
    cuando hay varias ventanas de apps similares abiertas (ej. varios Bloc de
    notas). Si el proceso tiene varias ventanas top-level, prioriza la primera
    visible y no minimizada.
    """
    windows = [w for w in Desktop(backend="uia").windows() if w.process_id() == pid]
    if not windows:
        raise ValueError(f"No se encontró ninguna ventana top-level para el pid {pid}")
    for w in windows:
        try:
            if w.is_visible() and not w.is_minimized():
                return w
        except Exception:
            continue
    return windows[0]


@register_tool(
    name="desktop_screenshot",
    description=(
        "Saca una captura de pantalla completa del escritorio de la PC (todos los monitores) "
        "y la guarda en disco. Sirve para ver qué hay en pantalla antes de decidir dónde clickear."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Ruta donde guardar el PNG (default 'desktop_screenshot.png').",
            }
        },
        "required": [],
    },
)
@_audited
def desktop_screenshot(path: str = "desktop_screenshot.png") -> dict:
    image = pyautogui.screenshot()
    image.save(path)
    return {"screenshot_path": path, "width": image.width, "height": image.height}


@register_tool(
    name="desktop_list_windows",
    description=(
        "Lista las ventanas visibles actualmente abiertas en la PC (título, proceso, pid). "
        "Sirve para saber qué apps hay abiertas antes de enfocar una con desktop_focus_window."
    ),
    parameters={"type": "object", "properties": {}, "required": []},
)
@_audited
def desktop_list_windows() -> dict:
    windows = []
    for w in Desktop(backend="uia").windows():
        title = w.window_text() or ""
        if not title:
            continue
        pid = w.process_id()
        windows.append({"title": title, "pid": pid, "process": _process_name(pid)})
    return {"windows": windows}


@register_tool(
    name="desktop_focus_window",
    description=(
        "Trae al frente (foco) una ventana, por 'pid' exacto o por 'title' (substring, case-"
        "insensitive). PREFERÍ 'pid' siempre que lo tengas — por ejemplo el que devolvió "
        "desktop_launch_app si tuviste que reintentar el foco porque vino con focused=false: "
        "apunta exacto a esa ventana sin ambigüedad. 'title' es un matching por substring y puede "
        "agarrar la ventana equivocada si hay varias instancias de la misma app abiertas (ej. varios "
        "Bloc de notas de intentos anteriores) — usalo solo cuando no tengas un pid específico. Si se "
        "pasan los dos, 'pid' tiene prioridad y 'title' se ignora. El resultado incluye el proceso "
        "dueño de la ventana matcheada; revisar ese campo antes de asumir que se encontró la app "
        "correcta, en vez de confiar ciegamente en que no haya tirado error."
    ),
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Texto a buscar (case-insensitive) dentro del título de la ventana. Ignorado si se pasa 'pid'.",
            },
            "pid": {
                "type": "integer",
                "description": (
                    "PID exacto del proceso dueño de la ventana a enfocar — más confiable que "
                    "'title' cuando hay varias ventanas similares. Tiene prioridad sobre 'title' "
                    "si se pasan ambos."
                ),
            },
        },
        "required": [],
    },
)
@_audited
def desktop_focus_window(title: Optional[str] = None, pid: Optional[int] = None) -> dict:
    if pid is not None:
        window = _find_window_by_pid(pid)
    elif title is not None:
        window = _find_window(title)
    else:
        raise ValueError("Hay que pasar 'title' o 'pid'.")
    window.set_focus()
    resolved_pid = window.process_id()
    return {"focused": window.window_text(), "pid": resolved_pid, "process": _process_name(resolved_pid)}


@register_tool(
    name="desktop_click",
    description=(
        "Hace click con el mouse en coordenadas de pantalla (píxeles, origen arriba-izquierda). "
        "Usar desktop_screenshot o desktop_list_windows/desktop_click_element antes si no se sabe "
        "dónde está el elemento a clickear."
    ),
    parameters={
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "Coordenada X en píxeles."},
            "y": {"type": "integer", "description": "Coordenada Y en píxeles."},
            "button": {
                "type": "string",
                "enum": ["left", "right", "middle"],
                "description": "Botón del mouse (default 'left').",
            },
            "double": {
                "type": "boolean",
                "description": "Si es true, hace doble click en vez de uno simple. Default false.",
            },
        },
        "required": ["x", "y"],
    },
)
@_audited
def desktop_click(x: int, y: int, button: str = "left", double: bool = False) -> dict:
    if double:
        pyautogui.doubleClick(x, y, button=button)
    else:
        pyautogui.click(x, y, button=button)
    return {"x": x, "y": y, "button": button, "double": double}


@register_tool(
    name="desktop_click_element",
    description=(
        "Hace click en un control (botón, item de menú, etc.) dentro de una ventana, identificándolo "
        "por su nombre/texto visible en vez de por coordenadas fijas — más robusto porque no depende "
        "de la resolución ni de la posición de la ventana. Usa UI Automation de Windows por debajo. "
        "El resultado incluye el proceso dueño de la ventana matcheada (revisar por posibles falsos "
        "positivos de matching por substring, igual que en desktop_focus_window)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "window_title": {
                "type": "string",
                "description": "Texto a buscar dentro del título de la ventana que contiene el control.",
            },
            "control_name": {
                "type": "string",
                "description": "Nombre/texto visible del control a clickear dentro de esa ventana.",
            },
        },
        "required": ["window_title", "control_name"],
    },
)
@_audited
def desktop_click_element(window_title: str, control_name: str) -> dict:
    window = _find_window(window_title)
    window.set_focus()
    # `_find_window` devuelve un UIAWrapper "crudo" (de Desktop().windows()), no una
    # WindowSpecification de pywinauto (la que se obtiene de Application().window(...)
    # y sí soporta indexado `[]` o `.child_window(...)` de forma perezosa). Un
    # UIAWrapper no tiene ninguno de los dos — lo que sí tiene es `.descendants(...)`,
    # que recorre el árbol de UI Automation desde acá y devuelve directamente wrappers
    # ya resueltos (con `.click_input()` disponible). Bugs reales encontrados en dos
    # intentos sucesivos contra un Notepad real (primero `window[...]`, después
    # `child_window`); los tests mockeados no los detectaban porque el doble de
    # prueba implementaba a mano lo que yo suponía que existía, replicando la
    # suposición equivocada en vez de la API real de pywinauto.
    matches = window.descendants(title=control_name)
    if not matches:
        raise ValueError(
            f"No se encontró ningún control con nombre '{control_name}' dentro de la ventana"
        )
    control = matches[0]
    control.click_input()
    pid = window.process_id()
    return {
        "window": window.window_text(),
        "control": control_name,
        "pid": pid,
        "process": _process_name(pid),
    }


@register_tool(
    name="desktop_type_text",
    description="Escribe texto en el campo/control que tenga el foco actualmente en la PC.",
    parameters={
        "type": "object",
        "properties": {"text": {"type": "string", "description": "Texto a escribir."}},
        "required": ["text"],
    },
)
@_audited
def desktop_type_text(text: str) -> dict:
    pyautogui.write(text)
    return {"typed_chars": len(text)}


@register_tool(
    name="desktop_press_key",
    description=(
        "Presiona una tecla o combinación de teclas (ej. 'enter', 'ctrl+s', 'alt+tab', 'ctrl+shift+esc')."
    ),
    parameters={
        "type": "object",
        "properties": {
            "combo": {
                "type": "string",
                "description": "Tecla o combinación separada por '+' (ej. 'ctrl+s').",
            }
        },
        "required": ["combo"],
    },
)
@_audited
def desktop_press_key(combo: str) -> dict:
    keys = [k.strip().lower() for k in combo.split("+") if k.strip()]
    if not keys:
        raise ValueError("combo vacío")
    if len(keys) == 1:
        pyautogui.press(keys[0])
    else:
        pyautogui.hotkey(*keys)
    return {"combo": combo, "keys": keys}


@register_tool(
    name="desktop_move_mouse",
    description="Mueve el cursor del mouse a coordenadas de pantalla dadas, sin clickear.",
    parameters={
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "Coordenada X en píxeles."},
            "y": {"type": "integer", "description": "Coordenada Y en píxeles."},
        },
        "required": ["x", "y"],
    },
)
@_audited
def desktop_move_mouse(x: int, y: int) -> dict:
    pyautogui.moveTo(x, y)
    return {"x": x, "y": y}


@register_tool(
    name="desktop_scroll",
    description="Scrollea la rueda del mouse una cantidad de 'clicks' dada (positivo = arriba, negativo = abajo).",
    parameters={
        "type": "object",
        "properties": {
            "amount": {
                "type": "integer",
                "description": "Cantidad de clicks de scroll (positivo arriba, negativo abajo).",
            },
            "x": {"type": "integer", "description": "X donde scrollear (default: posición actual)."},
            "y": {"type": "integer", "description": "Y donde scrollear (default: posición actual)."},
        },
        "required": ["amount"],
    },
)
@_audited
def desktop_scroll(amount: int, x: Optional[int] = None, y: Optional[int] = None) -> dict:
    if x is not None and y is not None:
        pyautogui.scroll(amount, x=x, y=y)
    else:
        pyautogui.scroll(amount)
    return {"amount": amount, "x": x, "y": y}


@register_tool(
    name="desktop_launch_app",
    description=(
        "Lanza un programa, documento o URL en la PC, y DEJA SU VENTANA AL FRENTE CON FOCO DE "
        "TECLADO ANTES DE DEVOLVER EL RESULTADO (no hace falta llamar a desktop_focus_window "
        "después — aunque no está de más si algo más le roba el foco mientras tanto). ESTA es la "
        "forma correcta de abrir una app — NO simular Win+buscar+escribir+enter con "
        "desktop_press_key/desktop_type_text: esa secuencia es frágil (la tecla Windows simulada "
        "no siempre abre el menú Inicio de verdad) y ya falló en la práctica. Usa os.startfile de "
        "Windows por debajo, que resuelve nombres de apps registradas (App Paths), rutas absolutas "
        "a un .exe, documentos, o URLs — lo mismo que resolvería Win+R. Si la ventana estaba "
        "minimizada por un estado heredado de una sesión anterior, se restaura igual. Si la acción "
        "reutiliza una ventana ya abierta (ej. una URL que abre una pestaña nueva en un navegador "
        "ya corriendo), puede no detectar ninguna ventana 'nueva' — en ese caso el resultado incluye "
        "'focused': false y una advertencia, en vez de asumir éxito silencioso. Windows también puede "
        "bloquear el cambio de foco por su propia política de seguridad aunque la ventana nueva se "
        "haya detectado bien — en ese caso el resultado igual incluye el 'pid' del proceso lanzado: "
        "SI 'focused' da false, reintentá con desktop_focus_window(pid=<ese pid>) — NO con 'title', "
        "porque si hay varias ventanas de la misma app abiertas (ej. varios Bloc de notas de intentos "
        "anteriores) el matching por título puede agarrar la ventana equivocada, no la que se acaba de "
        "lanzar. Ejemplos válidos: 'notepad', 'notepad.exe', 'calc', "
        "'C:\\\\Windows\\\\System32\\\\notepad.exe', 'https://google.com'. Hay un blocklist de "
        "utilidades de Windows obviamente destructivas (format, diskpart, cipher /w, vssadmin "
        "delete, bcdedit) que rechaza el lanzamiento antes de intentarlo — mitigación de 'evitar "
        "el desastre obvio', no un sandbox real."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path_or_name": {
                "type": "string",
                "description": "Nombre de la app, ruta absoluta al ejecutable/documento, o URL a abrir.",
            }
        },
        "required": ["path_or_name"],
    },
)
@_audited
def desktop_launch_app(path_or_name: str) -> dict:
    _check_launch_blocklist(path_or_name)
    before = _enum_visible_titled_windows()

    try:
        os.startfile(path_or_name)
        method = "os.startfile"
    except OSError as exc:
        # Fallback: invocar el comando `start` de cmd.exe, que resuelve App Paths igual que Win+R.
        # Se pasa como lista de argv (shell=False) en vez de una string armada a mano con
        # shell=True, para que `path_or_name` no pueda inyectar metacaracteres de shell.
        try:
            subprocess.Popen(["cmd", "/c", "start", "", path_or_name])
            method = "subprocess_start_fallback"
        except Exception as fallback_exc:
            raise RuntimeError(
                f"No se pudo lanzar '{path_or_name}': os.startfile falló ({exc}) y el fallback "
                f"con 'start' también falló ({fallback_exc})."
            ) from fallback_exc

    found = _wait_for_new_window(before)
    if found is None:
        return {
            "launched": path_or_name,
            "method": method,
            "focused": False,
            "warning": (
                f"El proceso se lanzó pero no se detectó ninguna ventana nueva dentro de "
                f"{_WINDOW_APPEAR_TIMEOUT}s. Puede que la app haya reutilizado una ventana ya "
                "abierta (ej. una pestaña nueva en un navegador ya corriendo), o que haya tardado "
                "más de lo esperado en abrir. No asumir que quedó enfocada."
            ),
        }

    hwnd, title, pid = found
    focused = _foreground_window(hwnd)
    result = {
        "launched": path_or_name,
        "method": method,
        "focused": focused,
        "window_title": title,
        "pid": pid,
        "process": _process_name(pid),
    }
    if not focused:
        result["warning"] = (
            "Se encontró la ventana nueva pero Windows bloqueó traerla al frente "
            "(SetForegroundWindow); puede no tener foco de teclado real."
        )
    return result
