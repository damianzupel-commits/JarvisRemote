"""Ventana principal de Jarvis para PC (PySide6).

Reemplaza la vieja ventana de chat en Tkinter (chat_window.py). Diseño pedido
por el usuario: chat al centro (elemento principal), selector de modelo arriba
al centro, barra lateral izquierda con accesos directos a utilidades (generar
imagen/video, más adelante otras) y un toggle de voz continua en un extremo de
esa barra. Nada de configuración técnica cruda acá -- eso va a vivir en un
ícono de ajustes aparte (pendiente de definir con el usuario).

Además del chat, aloja dos pestañas más -- Codebase y Obsidian (ver
`ui/codebase_view.py` y `ui/obsidian_view.py`) -- que exponen del lado
visual las dos capacidades nativas del backend (`backend/app/codebase/` y
`backend/app/obsidian/`). El chat en sí se extrajo a `ui/chat_view.py` para
que quepa como una pestaña más sin cambiar su comportamiento.

Corre en su propio hilo con su propio QApplication, igual que chat_window.py
corría Tkinter en el suyo -- pystray sigue dueño del hilo principal en tray.py.
Solo puede existir un QApplication por proceso, así que abrir "chat" una
segunda vez no crea una instancia nueva: reusa la ventana ya viva.
"""

import threading

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import config
import process_manager
from ui.chat_view import ChatView
from ui.codebase_view import CodebaseView
from ui.investigation_view import InvestigationView
from ui.obsidian_view import ObsidianView
from ui.settings_window import SettingsDialog
from ui.theming import force_dark_title_bar

# Tema oscuro fijo, sin opción de cambiar a claro -- pedido explícito de
# Damian ("es lo que usa la mayoría de la gente"). Ver también
# _force_dark_title_bar() para que la barra de título nativa de Windows
# acompañe (si no, quedaba blanca arriba de un contenido oscuro).
STYLESHEET = """
QMainWindow, QWidget#chatArea { background: #14151a; }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QWidget#sidebar { background: #16171c; }
QWidget#topBar { background: #1b1c22; border-bottom: 1px solid #2a2b33; }
QComboBox {
    background: #262832; color: #e5e7eb; border: 1px solid #33343d; border-radius: 8px;
    padding: 6px 14px; font-size: 13px; min-width: 220px;
}
QComboBox QAbstractItemView {
    background: #262832; color: #e5e7eb; selection-background-color: #3b82f6;
    border: 1px solid #33343d;
}
QPushButton#sidebarButton {
    background: transparent; color: #9aa0ab; border: none;
    border-radius: 10px; padding: 12px; font-size: 22px; text-align: center;
}
QPushButton#sidebarButton:hover { background: #21232b; color: #ffffff; }
QPushButton#sidebarButton:checked { background: #3b82f6; color: #ffffff; }
QPushButton#settingsButton {
    background: transparent; border: none; border-radius: 8px;
    padding: 6px 10px; font-size: 18px; color: #9aa0ab;
}
QPushButton#settingsButton:hover { background: #262832; color: #ffffff; }
QLineEdit#messageInput {
    background: #1f2029; color: #e5e7eb; border: 1px solid #33343d; border-radius: 18px;
    padding: 10px 16px; font-size: 14px;
}
QPushButton#sendButton {
    background: #3b82f6; color: white; border: none; border-radius: 18px;
    padding: 10px 20px; font-size: 14px; font-weight: 600;
}
QPushButton#sendButton:hover { background: #2f6fd6; }
QLabel#bubbleUser {
    background: #3b82f6; color: white; border-radius: 14px; padding: 10px 14px;
    font-size: 14px;
}
QLabel#bubbleAssistant {
    background: #262832; color: #e5e7eb; border-radius: 14px; padding: 10px 14px;
    font-size: 14px; border: 1px solid #33343d;
}
QLabel#bubbleTyping {
    background: #262832; color: #8b8f9c; border-radius: 14px; padding: 10px 14px;
    font-size: 14px; font-style: italic; border: 1px solid #33343d;
}
QLabel#bubbleSystem {
    color: #7d8190; font-size: 12px; font-style: italic; padding: 4px 8px;
}
QTabWidget::pane { border: none; background: #14151a; }
QTabBar::tab {
    background: transparent; color: #9aa0ab; padding: 10px 18px; font-size: 13px;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected { color: #ffffff; border-bottom: 2px solid #3b82f6; }
QTabBar::tab:hover { color: #e5e7eb; }
QWidget#codebaseView, QWidget#obsidianView { background: #14151a; }
QLineEdit#codebasePathInput {
    background: #1f2029; color: #e5e7eb; border: 1px solid #33343d; border-radius: 8px;
    padding: 8px 12px; font-size: 13px;
}
QLabel#codebaseStatus, QLabel#obsidianStatus { color: #7d8190; font-size: 12px; }
QLabel#obsidianDetailMeta { color: #9aa0ab; font-size: 12px; }
QTreeWidget, QListWidget, QTextEdit {
    background: #1b1c22; color: #e5e7eb; border: 1px solid #2a2b33; border-radius: 8px;
}
"""


class ModelSwitchBridge(QObject):
    model_switch_done = Signal(str)


class ModelSwitchThread(QThread):
    def __init__(self, model_id: str, bridge: ModelSwitchBridge):
        super().__init__()
        self._model_id = model_id
        self._bridge = bridge

    def run(self) -> None:
        process_manager.set_active_model(self._model_id)
        self._bridge.model_switch_done.emit(self._model_id)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jarvis")
        self.resize(900, 680)

        self._model_bridge = ModelSwitchBridge()
        self._model_bridge.model_switch_done.connect(self._on_model_switched)

        self._settings_dialog: SettingsDialog | None = None
        self._model_thread: ModelSwitchThread | None = None

        central = QWidget()
        central.setObjectName("chatArea")
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_top_bar())

        self.tabs = QTabWidget()
        self.chat_view = ChatView()
        self.codebase_view = CodebaseView()
        self.obsidian_view = ObsidianView()
        self.investigation_view = InvestigationView()
        self.tabs.addTab(self.chat_view, "💬  Chat")
        self.tabs.addTab(self.codebase_view, "🗂  Codebase")
        self.tabs.addTab(self.obsidian_view, "🧠  Obsidian")
        self.tabs.addTab(self.investigation_view, "🔎  Investigación")
        root.addWidget(self.tabs, stretch=1)

        self.setCentralWidget(central)
        self.setStyleSheet(STYLESHEET)
        force_dark_title_bar(self)

    # ------------------------------------------------------------- layout

    def _build_top_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("topBar")
        bar.setFixedHeight(56)
        layout = QHBoxLayout(bar)
        layout.addStretch()

        self.model_selector = QComboBox()
        for model in config.AVAILABLE_MODELS:
            self.model_selector.addItem(model["label"], userData=model["id"])
        current = self._current_model_id()
        idx = self.model_selector.findData(current)
        if idx >= 0:
            self.model_selector.setCurrentIndex(idx)
        self.model_selector.currentIndexChanged.connect(self._on_model_selected)
        layout.addWidget(self.model_selector)

        layout.addStretch()

        settings_button = QPushButton("⚙")
        settings_button.setObjectName("settingsButton")
        settings_button.setToolTip("Configuración (permisos y conectores)")
        settings_button.setCursor(Qt.PointingHandCursor)
        settings_button.clicked.connect(self._on_open_settings)
        layout.addWidget(settings_button)
        layout.setContentsMargins(0, 0, 12, 0)
        return bar

    # ------------------------------------------------------------- ajustes

    def _on_open_settings(self) -> None:
        # Diálogo no-modal reusado -- así el usuario puede seguir chateando
        # mientras lo tiene abierto, y no se acumulan instancias si lo abre
        # varias veces desde el ícono.
        if self._settings_dialog is None:
            self._settings_dialog = SettingsDialog(self)
        self._settings_dialog.show()
        self._settings_dialog.raise_()
        self._settings_dialog.activateWindow()

    # ------------------------------------------------------------- modelo

    def _current_model_id(self) -> str:
        try:
            text = config.ENV_PATH.read_text(encoding="utf-8")
            for line in text.splitlines():
                if line.startswith("LMSTUDIO_MODEL="):
                    return line.split("=", 1)[1].strip()
        except OSError:
            pass
        return config.AVAILABLE_MODELS[0]["id"]

    def _on_model_selected(self, index: int) -> None:
        model_id = self.model_selector.itemData(index)
        if model_id == self._current_model_id():
            return
        self.model_selector.setEnabled(False)
        self.chat_view.add_system_message("Cambiando de modelo... puede tardar un momento.")
        self._model_thread = ModelSwitchThread(model_id, self._model_bridge)
        self._model_thread.start()

    def _on_model_switched(self, model_id: str) -> None:
        self.model_selector.setEnabled(True)
        label = next((m["label"] for m in config.AVAILABLE_MODELS if m["id"] == model_id), model_id)
        self.chat_view.add_system_message(f"Listo, ahora estoy usando el modelo: {label}.")

    def closeEvent(self, event) -> None:
        self.chat_view.shutdown()
        super().closeEvent(event)


_qt_thread: threading.Thread | None = None
_window: MainWindow | None = None
_lock = threading.Lock()


def open_chat_window(icon=None, item=None) -> None:
    global _qt_thread, _window
    with _lock:
        if _qt_thread is not None and _qt_thread.is_alive():
            if _window is not None:
                # QWidget no es thread-safe: pedirle que se muestre desde el
                # hilo de pystray directo rompería la regla de un solo hilo de
                # GUI. invokeMethod encola el show()/raise_() en el hilo de Qt.
                from PySide6.QtCore import QMetaObject

                QMetaObject.invokeMethod(_window, "show", Qt.QueuedConnection)
                QMetaObject.invokeMethod(_window, "raise_", Qt.QueuedConnection)
                QMetaObject.invokeMethod(_window, "activateWindow", Qt.QueuedConnection)
            return
        _qt_thread = threading.Thread(target=_run_qt_app, daemon=True)
        _qt_thread.start()


def _run_qt_app() -> None:
    global _window
    app = QApplication.instance() or QApplication([])
    _window = MainWindow()
    _window.show()
    app.exec()
