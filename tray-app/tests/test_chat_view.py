"""Tests de la vista de chat (pestaña "Chat", ver ui/chat_view.py). No arranca
VoiceListener de verdad (cargar whisper/VAD es lento y no hace falta para
probar el wiring de la UI)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from ui.chat_view import ChatView, Sidebar


def test_sidebar_has_no_image_or_video_utilities():
    # generate_image/generate_video se sacaron de la UI (no solo deshabilitadas
    # del lado del backend) por precaución de hardware -- ver Sidebar.TOOLS y
    # INFORME_COMPLETO.md, sección 4.5. No reactivar sin haber investigado la
    # causa del apagado primero.
    tooltips = [tooltip for _, tooltip, _ in Sidebar.TOOLS]
    assert "Generar imagen" not in tooltips
    assert "Generar video" not in tooltips


def test_sidebar_has_no_utility_buttons_only_voice(qtbot):
    sidebar = Sidebar()
    qtbot.addWidget(sidebar)

    tool_buttons = [
        b for b in sidebar.findChildren(QPushButton) if b.objectName() == "sidebarButton" and not b.isCheckable()
    ]
    assert tool_buttons == []


def test_sidebar_tool_click_emits_its_prompt_prefix(qtbot):
    sidebar = Sidebar()
    qtbot.addWidget(sidebar)
    received = []
    sidebar.tool_selected.connect(received.append)

    tool_buttons = [
        b for b in sidebar.findChildren(QPushButton) if b.objectName() == "sidebarButton" and not b.isCheckable()
    ]
    assert len(tool_buttons) == len(Sidebar.TOOLS)

    for button, (_, _, expected_prefix) in zip(tool_buttons, Sidebar.TOOLS):
        qtbot.mouseClick(button, Qt.LeftButton)
        assert received[-1] == expected_prefix


def test_sidebar_voice_button_is_checkable_and_toggles(qtbot):
    sidebar = Sidebar()
    qtbot.addWidget(sidebar)
    received = []
    sidebar.voice_toggled.connect(received.append)

    assert sidebar.voice_button.isCheckable()
    qtbot.mouseClick(sidebar.voice_button, Qt.LeftButton)
    qtbot.mouseClick(sidebar.voice_button, Qt.LeftButton)
    assert received == [True, False]


def test_tool_selected_prefills_and_focuses_the_message_input(qtbot):
    view = ChatView()
    qtbot.addWidget(view)

    view._on_tool_selected("Genera una imagen de: ")

    assert view.message_input.text() == "Genera una imagen de: "
    assert view.message_input.cursorPosition() == len("Genera una imagen de: ")


def test_add_system_message_appends_a_bubble(qtbot):
    view = ChatView()
    qtbot.addWidget(view)

    before = view._messages_layout.count()
    view.add_system_message("hola")

    assert view._messages_layout.count() == before + 1


def test_on_reply_hides_typing_indicator_and_adds_bubble(qtbot):
    view = ChatView()
    qtbot.addWidget(view)

    view._show_typing_indicator()
    assert view._typing_bubble is not None

    view._on_reply("assistant", "respuesta")

    assert view._typing_bubble is None
