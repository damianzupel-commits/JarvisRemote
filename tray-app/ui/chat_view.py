"""Vista de chat -- pestaña "Chat" de la ventana principal (ver
`ui/main_window.py`). Contiene todo lo que antes vivía directo en el cuerpo
de `MainWindow` (sidebar de utilidades + columna de mensajes + input + voz);
se extrajo a su propio widget para que `MainWindow` pueda alojarla como una
pestaña más junto a Codebase y Obsidian, sin cambiar ningún comportamiento.
"""

import requests
from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import config
from ui.widgets import NoMinWidthLabel
from voice_listener import VoiceListener


class ChatBridge(QObject):
    """Recibe eventos desde hilos de trabajo (HTTP, voz) y los reemite como
    señales Qt -- así el hilo de la GUI es el único que toca los widgets."""

    reply_ready = Signal(str, str)  # (autor, texto)


class ChatRequestThread(QThread):
    def __init__(self, message: str, conversation_id: str, bridge: ChatBridge):
        super().__init__()
        self._message = message
        self._conversation_id = conversation_id
        self._bridge = bridge

    def run(self) -> None:
        try:
            resp = requests.post(
                config.CHAT_URL,
                json={"message": self._message, "conversation_id": self._conversation_id},
                headers={"Authorization": f"Bearer {config.API_KEY}"},
                timeout=600,
            )
            resp.raise_for_status()
            reply = resp.json().get("reply", "(sin respuesta)")
        except requests.RequestException as exc:
            reply = f"No pude conectarme con Jarvis: {exc}"
        self._bridge.reply_ready.emit("assistant", reply)


class Sidebar(QWidget):
    """Barra de accesos directos. `tools` es una lista de (icono, tooltip,
    prompt) -- agregar una utilidad nueva (ej. interpolación de frames) es
    agregar una tupla acá, nada más."""

    # Vacía a propósito: "Generar imagen"/"Generar video" se sacaron de la UI
    # (no solo deshabilitadas atrás) por precaución de hardware -- la PC se
    # apagó físicamente coincidiendo con generate_image/generate_video (ver
    # INFORME_COMPLETO.md, sección 4.5, y backend/app/tools/__init__.py,
    # donde esas dos tools están comentadas). No reactivar ninguna de las dos
    # puntas sin haber investigado la causa primero.
    TOOLS: list[tuple[str, str, str]] = []

    tool_selected = Signal(str)
    voice_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(64)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 16, 6, 16)
        layout.setSpacing(8)

        for icon, tooltip, prompt_prefix in self.TOOLS:
            btn = QPushButton(icon)
            btn.setObjectName("sidebarButton")
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, p=prompt_prefix: self.tool_selected.emit(p))
            layout.addWidget(btn)

        layout.addStretch()

        self.voice_button = QPushButton("🎙")
        self.voice_button.setObjectName("sidebarButton")
        self.voice_button.setToolTip("Activar/desactivar escucha continua (\"hey Jarvis\")")
        self.voice_button.setCheckable(True)
        self.voice_button.setCursor(Qt.PointingHandCursor)
        self.voice_button.toggled.connect(self.voice_toggled.emit)
        layout.addWidget(self.voice_button)


class ChatView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._bridge = ChatBridge()
        self._bridge.reply_ready.connect(self._on_reply)

        self._conversation_id: str | None = None
        self._voice_listener: VoiceListener | None = None
        self._typing_bubble: QWidget | None = None
        self._request_thread: ChatRequestThread | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.tool_selected.connect(self._on_tool_selected)
        self.sidebar.voice_toggled.connect(self._on_voice_toggled)
        layout.addWidget(self.sidebar)

        layout.addWidget(self._build_chat_column(), stretch=1)

        self._add_system_message('Decime qué necesitás, o tocá 🎙 para hablarme sin escribir.')

    # ------------------------------------------------------------- layout

    def _build_chat_column(self) -> QWidget:
        column = QWidget()
        column.setObjectName("chatArea")
        layout = QVBoxLayout(column)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self._messages_container = QWidget()
        self._messages_layout = QVBoxLayout(self._messages_container)
        self._messages_layout.addStretch()
        self.scroll_area.setWidget(self._messages_container)
        layout.addWidget(self.scroll_area, stretch=1)

        input_row = QHBoxLayout()
        self.message_input = QLineEdit()
        self.message_input.setObjectName("messageInput")
        self.message_input.setPlaceholderText("Escribile algo a Jarvis...")
        self.message_input.returnPressed.connect(self._on_send_clicked)
        input_row.addWidget(self.message_input, stretch=1)

        send_button = QPushButton("Enviar")
        send_button.setObjectName("sendButton")
        send_button.setCursor(Qt.PointingHandCursor)
        send_button.clicked.connect(self._on_send_clicked)
        input_row.addWidget(send_button)

        layout.addLayout(input_row)
        return column

    # ------------------------------------------------------------- chat

    def _add_bubble(self, author: str, text: str, object_name: str | None = None) -> QWidget:
        # NoMinWidthLabel, no QLabel a secas -- el texto acá es de chat (del
        # usuario o de Jarvis) y puede traer una URL/path/hash larguísimo sin
        # espacios, que sin este fix estira la ventana principal (ver
        # ui/widgets.py para el bug real).
        label = NoMinWidthLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        row = QHBoxLayout()
        if author == "user":
            label.setObjectName(object_name or "bubbleUser")
            row.addStretch()
            row.addWidget(label, stretch=0)
        else:
            label.setObjectName(object_name or "bubbleAssistant")
            row.addWidget(label, stretch=0)
            row.addStretch()

        wrapper = QWidget()
        wrapper.setLayout(row)
        self._messages_layout.insertWidget(self._messages_layout.count() - 1, wrapper)
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())
        return wrapper

    def _show_typing_indicator(self) -> None:
        self._hide_typing_indicator()
        self._typing_bubble = self._add_bubble("assistant", "Jarvis está pensando...", object_name="bubbleTyping")

    def _hide_typing_indicator(self) -> None:
        if self._typing_bubble is not None:
            self._messages_layout.removeWidget(self._typing_bubble)
            self._typing_bubble.deleteLater()
            self._typing_bubble = None

    def add_system_message(self, text: str) -> None:
        label = NoMinWidthLabel(text)
        label.setObjectName("bubbleSystem")
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignCenter)
        self._messages_layout.insertWidget(self._messages_layout.count() - 1, label)
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

    def _add_system_message(self, text: str) -> None:
        self.add_system_message(text)

    def _on_send_clicked(self) -> None:
        text = self.message_input.text().strip()
        if not text:
            return
        self.message_input.clear()
        self._send_message(text)

    def _send_message(self, text: str) -> None:
        self._add_bubble("user", text)
        self._show_typing_indicator()
        self._request_thread = ChatRequestThread(text, self._conversation_id, self._bridge)
        self._request_thread.start()

    def _on_tool_selected(self, prompt_prefix: str) -> None:
        self.message_input.setText(prompt_prefix)
        self.message_input.setFocus()
        self.message_input.setCursorPosition(len(prompt_prefix))

    def _on_reply(self, author: str, text: str) -> None:
        self._hide_typing_indicator()
        self._add_bubble(author, text)

    # ------------------------------------------------------------- voz

    def _on_voice_toggled(self, enabled: bool) -> None:
        if enabled:
            if self._voice_listener is None:
                # require_wake_word=False: prender este botón ya es la señal de
                # "escuchame" -- pedir además "hey Jarvis" sería redundante,
                # solo tiene sentido para una escucha pasiva en background (que
                # este botón no es).
                self._voice_listener = VoiceListener(
                    on_event=self._on_voice_event_threadsafe, require_wake_word=False
                )
            self._voice_listener.start()
            self.add_system_message("Escucha activada. Hablá directo, sin decir nada antes.")
        else:
            if self._voice_listener is not None:
                self._voice_listener.stop()
            self.add_system_message("Escucha desactivada.")

    def _on_voice_event_threadsafe(self, kind: str, text: str) -> None:
        # VoiceListener llama esto desde su propio hilo de audio -- nunca tocar
        # widgets acá directamente, todo pasa por la señal Qt (thread-safe).
        if kind == "wake":
            return
        labels = {"transcript": "user", "reply": "assistant", "error": "assistant"}
        self._bridge.reply_ready.emit(labels.get(kind, "assistant"), text)

    def shutdown(self) -> None:
        if self._voice_listener is not None:
            self._voice_listener.stop()
