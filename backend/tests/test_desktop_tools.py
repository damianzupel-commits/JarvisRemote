"""Tests de las tools de escritorio (app/tools/desktop.py).

CRÍTICO: nunca se debe llamar de verdad a pyautogui/pywinauto acá (moverían el
mouse, tipearían teclas, etc. en la máquina que corre la suite). Todo lo que
toca hardware se mockea con monkeypatch.
"""

import pytest

from app.tools import desktop


class _FakeWindow:
    def __init__(
        self,
        title: str,
        pid: int = 1234,
        visible: bool = True,
        minimized: bool = False,
        descendants: list | None = None,
    ):
        self._title = title
        self._pid = pid
        self._visible = visible
        self._minimized = minimized
        self._descendants = descendants
        self.focused = False
        self.clicked_control = None
        self.last_descendants_title_query = None

    def window_text(self) -> str:
        return self._title

    def process_id(self) -> int:
        return self._pid

    def is_visible(self) -> bool:
        return self._visible

    def is_minimized(self) -> bool:
        return self._minimized

    def set_focus(self) -> None:
        self.focused = True

    def descendants(self, title: str):
        self.last_descendants_title_query = title
        self.clicked_control = title
        if self._descendants is not None:
            return self._descendants
        return [_FakeControl(title)]


class _FakeControl:
    def __init__(self, name: str):
        self.name = name
        self.clicked = False

    def click_input(self) -> None:
        self.clicked = True


@pytest.fixture(autouse=True)
def _desktop_control_enabled(monkeypatch):
    monkeypatch.setattr(desktop.settings, "desktop_control_enabled", True)


@pytest.fixture(autouse=True)
def _no_real_pyautogui(monkeypatch):
    """Reemplaza pyautogui por un mock que registra llamadas pero no toca nada real."""

    class _FakePyAutoGui:
        def __init__(self):
            self.calls = []

        def click(self, *a, **kw):
            self.calls.append(("click", a, kw))

        def doubleClick(self, *a, **kw):
            self.calls.append(("doubleClick", a, kw))

        def write(self, *a, **kw):
            self.calls.append(("write", a, kw))

        def press(self, *a, **kw):
            self.calls.append(("press", a, kw))

        def hotkey(self, *a, **kw):
            self.calls.append(("hotkey", a, kw))

        def moveTo(self, *a, **kw):
            self.calls.append(("moveTo", a, kw))

        def scroll(self, *a, **kw):
            self.calls.append(("scroll", a, kw))

        def screenshot(self, *a, **kw):
            self.calls.append(("screenshot", a, kw))

            class _FakeImage:
                width = 1920
                height = 1080

                def save(self, path):
                    pass

            return _FakeImage()

    fake = _FakePyAutoGui()
    monkeypatch.setattr(desktop, "pyautogui", fake)
    return fake


def test_desktop_control_disabled_blocks_every_action(monkeypatch):
    monkeypatch.setattr(desktop.settings, "desktop_control_enabled", False)
    with pytest.raises(desktop.DesktopControlDisabled):
        desktop.desktop_click(1, 2)
    with pytest.raises(desktop.DesktopControlDisabled):
        desktop.desktop_screenshot()


def test_desktop_screenshot_saves_and_returns_dimensions(_no_real_pyautogui):
    result = desktop.desktop_screenshot(path="out.png")
    assert result == {"screenshot_path": "out.png", "width": 1920, "height": 1080}
    assert _no_real_pyautogui.calls[0][0] == "screenshot"


def test_desktop_click_forwards_button_and_double(_no_real_pyautogui):
    result = desktop.desktop_click(10, 20, button="right", double=True)
    assert result == {"x": 10, "y": 20, "button": "right", "double": True}
    assert _no_real_pyautogui.calls == [("doubleClick", (10, 20), {"button": "right"})]


def test_desktop_type_text_forwards_to_pyautogui(_no_real_pyautogui):
    result = desktop.desktop_type_text("hola mundo")
    assert result == {"typed_chars": 10}
    assert _no_real_pyautogui.calls == [("write", ("hola mundo",), {})]


def test_desktop_press_key_splits_combo_into_hotkey(_no_real_pyautogui):
    result = desktop.desktop_press_key("ctrl+shift+esc")
    assert result == {"combo": "ctrl+shift+esc", "keys": ["ctrl", "shift", "esc"]}
    assert _no_real_pyautogui.calls == [("hotkey", ("ctrl", "shift", "esc"), {})]


def test_desktop_press_key_single_key_uses_press(_no_real_pyautogui):
    desktop.desktop_press_key("enter")
    assert _no_real_pyautogui.calls == [("press", ("enter",), {})]


def test_desktop_move_mouse(_no_real_pyautogui):
    result = desktop.desktop_move_mouse(5, 6)
    assert result == {"x": 5, "y": 6}
    assert _no_real_pyautogui.calls == [("moveTo", (5, 6), {})]


def test_desktop_scroll_without_coords(_no_real_pyautogui):
    desktop.desktop_scroll(-3)
    assert _no_real_pyautogui.calls == [("scroll", (-3,), {})]


def test_desktop_scroll_with_coords(_no_real_pyautogui):
    desktop.desktop_scroll(3, x=1, y=2)
    assert _no_real_pyautogui.calls == [("scroll", (3,), {"x": 1, "y": 2})]


def test_desktop_list_windows_reads_title_and_pid(monkeypatch):
    fake_windows = [_FakeWindow("Bloc de notas"), _FakeWindow("", pid=1)]
    monkeypatch.setattr(desktop, "Desktop", lambda backend: type(
        "D", (), {"windows": lambda self: fake_windows}
    )())
    monkeypatch.setattr(desktop, "_process_name", lambda pid: "notepad.exe" if pid == 1234 else None)

    result = desktop.desktop_list_windows()

    # La ventana con título vacío se filtra.
    assert result == {"windows": [{"title": "Bloc de notas", "pid": 1234, "process": "notepad.exe"}]}


def test_desktop_focus_window_sets_focus_and_reports_process(monkeypatch):
    window = _FakeWindow("Visual Studio Code", pid=42)
    monkeypatch.setattr(desktop, "_find_window", lambda title: window)
    monkeypatch.setattr(desktop, "_process_name", lambda pid: "Code.exe" if pid == 42 else None)

    result = desktop.desktop_focus_window("Visual Studio Code")

    assert window.focused is True
    assert result == {"focused": "Visual Studio Code", "pid": 42, "process": "Code.exe"}


def test_desktop_focus_window_surfaces_false_positive_substring_match(monkeypatch):
    """Regresión: un match por substring del título puede corresponder a una ventana de
    OTRO programa (ej. el propio buscador de Windows con el texto tipeado en su título,
    en vez de la app que se buscaba). El resultado tiene que exponer el proceso real para
    que quien lo lea (el LLM o un humano) note el falso positivo en vez de asumir éxito.
    """
    decoy_window = _FakeWindow("Buscar: Bloc de notas", pid=999)
    monkeypatch.setattr(desktop, "_find_window", lambda title: decoy_window)
    monkeypatch.setattr(desktop, "_process_name", lambda pid: "SearchHost.exe" if pid == 999 else None)

    result = desktop.desktop_focus_window("Bloc de notas")

    assert result["process"] == "SearchHost.exe"
    assert result["process"] != "notepad.exe"


def test_desktop_focus_window_by_pid_ignores_title_ambiguity(monkeypatch):
    """Regresión real de la prueba en vivo #4: con varias ventanas "Bloc de notas" abiertas
    (de intentos anteriores), buscar por título agarra cualquiera. Buscar por pid exacto no
    tiene esa ambigüedad."""
    old_leftover = _FakeWindow("Sin título: Bloc de notas", pid=40364)
    just_launched = _FakeWindow("Sin título: Bloc de notas", pid=32000)
    monkeypatch.setattr(
        desktop, "Desktop", lambda backend: type(
            "D", (), {"windows": lambda self: [old_leftover, just_launched]}
        )()
    )
    monkeypatch.setattr(desktop, "_process_name", lambda pid: "notepad.exe")

    result = desktop.desktop_focus_window(title="Sin título: Bloc de notas", pid=32000)

    assert just_launched.focused is True
    assert old_leftover.focused is False
    assert result == {"focused": "Sin título: Bloc de notas", "pid": 32000, "process": "notepad.exe"}


def test_desktop_focus_window_pid_takes_priority_over_title(monkeypatch):
    window_by_title = _FakeWindow("Calculadora", pid=1)
    window_by_pid = _FakeWindow("Otro título", pid=2)
    monkeypatch.setattr(desktop, "_find_window", lambda title: window_by_title)
    monkeypatch.setattr(desktop, "_find_window_by_pid", lambda pid: window_by_pid)
    monkeypatch.setattr(desktop, "_process_name", lambda pid: "otro.exe")

    result = desktop.desktop_focus_window(title="Calculadora", pid=2)

    assert window_by_pid.focused is True
    assert window_by_title.focused is False
    assert result["pid"] == 2


def test_desktop_focus_window_requires_title_or_pid():
    with pytest.raises(ValueError):
        desktop.desktop_focus_window()


def test_find_window_by_pid_prefers_visible_non_minimized_window(monkeypatch):
    minimized = _FakeWindow("Sin título: Bloc de notas", pid=5, minimized=True)
    hidden = _FakeWindow("", pid=5, visible=False)
    normal = _FakeWindow("Sin título: Bloc de notas", pid=5, minimized=False, visible=True)
    monkeypatch.setattr(
        desktop, "Desktop", lambda backend: type(
            "D", (), {"windows": lambda self: [minimized, hidden, normal]}
        )()
    )

    result = desktop._find_window_by_pid(5)

    assert result is normal


def test_find_window_by_pid_raises_when_no_window_for_that_pid(monkeypatch):
    monkeypatch.setattr(
        desktop, "Desktop", lambda backend: type(
            "D", (), {"windows": lambda self: [_FakeWindow("Otra cosa", pid=1)]}
        )()
    )
    with pytest.raises(ValueError):
        desktop._find_window_by_pid(999)


def test_desktop_click_element_focuses_and_clicks_control(monkeypatch):
    window = _FakeWindow("Calculadora", pid=7)
    monkeypatch.setattr(desktop, "_find_window", lambda title: window)
    monkeypatch.setattr(desktop, "_process_name", lambda pid: "CalculatorApp.exe" if pid == 7 else None)

    result = desktop.desktop_click_element("Calculadora", "Igual a")

    assert window.focused is True
    assert window.clicked_control == "Igual a"
    assert result == {
        "window": "Calculadora",
        "control": "Igual a",
        "pid": 7,
        "process": "CalculatorApp.exe",
    }


def test_desktop_click_element_raises_when_control_not_found(monkeypatch):
    window = _FakeWindow("Calculadora", pid=7, descendants=[])
    monkeypatch.setattr(desktop, "_find_window", lambda title: window)

    with pytest.raises(ValueError):
        desktop.desktop_click_element("Calculadora", "No existe")


def test_find_window_raises_value_error_when_no_match(monkeypatch):
    monkeypatch.setattr(desktop, "Desktop", lambda backend: type(
        "D", (), {"windows": lambda self: [_FakeWindow("Otra cosa")]}
    )())
    with pytest.raises(ValueError):
        desktop._find_window("no existe")


def test_elevation_error_is_detected_and_wrapped(monkeypatch):
    def _boom(title):
        raise RuntimeError("Access is denied (-2147024891)")

    monkeypatch.setattr(desktop, "_find_window", _boom)
    with pytest.raises(desktop.ElevatedWindowError):
        desktop.desktop_focus_window("alguna ventana elevada")


@pytest.fixture(autouse=True)
def _no_real_window_polling(monkeypatch):
    """Por default ninguna ventana "nueva" existe salvo que un test diga lo contrario —
    evita que desktop_launch_app dispare win32gui de verdad en tests que no lo cubren."""
    monkeypatch.setattr(desktop, "_enum_visible_titled_windows", lambda: {})


@pytest.mark.parametrize(
    "path_or_name",
    [
        "format",
        "format.com",
        "FORMAT C:",
        "diskpart",
        "diskpart.exe",
        "cipher /w:C:\\",
        "vssadmin delete shadows /all /quiet",
        "bcdedit /set {default} recoveryenabled no",
    ],
)
def test_desktop_launch_app_blocks_destructive_utilities(path_or_name, monkeypatch):
    monkeypatch.setattr(desktop.os, "startfile", lambda path: pytest.fail("no debería llegar acá"))

    with pytest.raises(desktop.DestructiveLaunchBlockedError):
        desktop.desktop_launch_app(path_or_name)


@pytest.mark.parametrize(
    "path_or_name",
    [
        "notepad",
        "notepad.exe",
        "calc",
        "chrome.exe",
        "C:\\Program Files\\MyFormatter\\formatter_tool.exe",
        "https://google.com",
    ],
)
def test_desktop_launch_app_allows_legitimate_names_that_look_similar(path_or_name, monkeypatch):
    """Casos pensados para no bloquearse por accidente — nombres de apps legítimas,
    incluida una que contiene 'format' como parte de otra palabra."""
    monkeypatch.setattr(desktop.os, "startfile", lambda path: None)
    monkeypatch.setattr(desktop, "_wait_for_new_window", lambda before: None)

    result = desktop.desktop_launch_app(path_or_name)

    assert result["launched"] == path_or_name


def test_desktop_launch_app_uses_startfile_by_default(monkeypatch):
    calls = []
    monkeypatch.setattr(desktop.os, "startfile", lambda path: calls.append(path))
    monkeypatch.setattr(desktop, "_wait_for_new_window", lambda before: (555, "Bloc de notas", 5284))
    monkeypatch.setattr(desktop, "_foreground_window", lambda hwnd: True)
    monkeypatch.setattr(desktop, "_process_name", lambda pid: "notepad.exe")

    result = desktop.desktop_launch_app("notepad")

    assert calls == ["notepad"]
    assert result == {
        "launched": "notepad",
        "method": "os.startfile",
        "focused": True,
        "window_title": "Bloc de notas",
        "pid": 5284,
        "process": "notepad.exe",
    }


def test_desktop_launch_app_falls_back_to_subprocess_when_startfile_fails(monkeypatch):
    def _boom(path):
        raise OSError("no se encontró la app")

    popen_calls = []
    monkeypatch.setattr(desktop.os, "startfile", _boom)
    monkeypatch.setattr(desktop.subprocess, "Popen", lambda args: popen_calls.append(args))
    monkeypatch.setattr(desktop, "_wait_for_new_window", lambda before: (1, "Algo Raro", 42))
    monkeypatch.setattr(desktop, "_foreground_window", lambda hwnd: True)
    monkeypatch.setattr(desktop, "_process_name", lambda pid: "algoraro.exe")

    result = desktop.desktop_launch_app("algo-raro")

    assert popen_calls == [["cmd", "/c", "start", "", "algo-raro"]]
    assert result["method"] == "subprocess_start_fallback"
    assert result["focused"] is True


def test_desktop_launch_app_raises_when_both_startfile_and_fallback_fail(monkeypatch):
    def _boom_startfile(path):
        raise OSError("no se encontró la app")

    def _boom_popen(args):
        raise RuntimeError("cmd.exe no disponible")

    monkeypatch.setattr(desktop.os, "startfile", _boom_startfile)
    monkeypatch.setattr(desktop.subprocess, "Popen", _boom_popen)

    with pytest.raises(RuntimeError):
        desktop.desktop_launch_app("algo-inexistente")


def test_desktop_launch_app_reports_unfocused_when_no_new_window_appears(monkeypatch):
    monkeypatch.setattr(desktop.os, "startfile", lambda path: None)
    monkeypatch.setattr(desktop, "_wait_for_new_window", lambda before: None)

    result = desktop.desktop_launch_app("https://google.com")

    assert result["launched"] == "https://google.com"
    assert result["focused"] is False
    assert "warning" in result
    assert "window_title" not in result


def test_desktop_launch_app_reports_unfocused_when_foreground_is_blocked(monkeypatch):
    monkeypatch.setattr(desktop.os, "startfile", lambda path: None)
    monkeypatch.setattr(desktop, "_wait_for_new_window", lambda before: (777, "Calculadora", 99))
    monkeypatch.setattr(desktop, "_foreground_window", lambda hwnd: False)
    monkeypatch.setattr(desktop, "_process_name", lambda pid: "CalculatorApp.exe")

    result = desktop.desktop_launch_app("calc")

    assert result["focused"] is False
    assert result["window_title"] == "Calculadora"
    assert "warning" in result


def test_wait_for_new_window_detects_window_that_appears_immediately(monkeypatch):
    before = {1: ("vieja", 10)}
    after = {1: ("vieja", 10), 2: ("Notepad nuevo", 5284)}
    monkeypatch.setattr(desktop, "_enum_visible_titled_windows", lambda: after)

    result = desktop._wait_for_new_window(before, timeout=1.0)

    assert result == (2, "Notepad nuevo", 5284)


def test_wait_for_new_window_detects_window_that_appears_after_a_few_polls(monkeypatch):
    before = {1: ("vieja", 10)}
    after = {1: ("vieja", 10), 2: ("Notepad nuevo", 5284)}
    calls = {"n": 0}

    def _fake_enum():
        calls["n"] += 1
        return before if calls["n"] < 3 else after

    monkeypatch.setattr(desktop, "_enum_visible_titled_windows", _fake_enum)
    monkeypatch.setattr(desktop.time, "sleep", lambda s: None)

    result = desktop._wait_for_new_window(before, timeout=5.0)

    assert result == (2, "Notepad nuevo", 5284)
    assert calls["n"] >= 3


def test_wait_for_new_window_times_out_when_nothing_new_appears(monkeypatch):
    before = {1: ("vieja", 10)}
    monkeypatch.setattr(desktop, "_enum_visible_titled_windows", lambda: before)
    monkeypatch.setattr(desktop.time, "sleep", lambda s: None)

    result = desktop._wait_for_new_window(before, timeout=0.05)

    assert result is None


def test_foreground_window_returns_false_when_set_foreground_raises_pywintypes_error(monkeypatch):
    """Regresión real encontrada en la prueba en vivo #3: SetForegroundWindow de pywin32 no
    devuelve un valor falsy en silencio cuando Windows bloquea el foreground-switch — lanza
    un pywintypes.error (a veces con winerror 0 y sin mensaje, un quirk conocido de esa API).
    _foreground_window tiene que tratar eso como "no se pudo enfocar", no dejar que reviente
    toda la tool call.
    """
    import pywintypes
    import win32gui

    monkeypatch.setattr(win32gui, "ShowWindow", lambda hwnd, cmd: None)

    def _boom(hwnd):
        raise pywintypes.error(0, "SetForegroundWindow", "No error message is available")

    monkeypatch.setattr(win32gui, "SetForegroundWindow", _boom)

    assert desktop._foreground_window(12345) is False


def test_desktop_tools_registered_with_pc_target():
    from app.tools import get_tools

    tools = get_tools()
    desktop_tool_names = {
        "desktop_screenshot",
        "desktop_list_windows",
        "desktop_focus_window",
        "desktop_click",
        "desktop_click_element",
        "desktop_type_text",
        "desktop_press_key",
        "desktop_move_mouse",
        "desktop_scroll",
        "desktop_launch_app",
    }
    assert desktop_tool_names <= tools.keys()
    for name in desktop_tool_names:
        assert tools[name].target == "pc"
