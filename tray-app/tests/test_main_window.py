"""Tests de la ventana principal: barra superior (selector de modelo,
ajustes) y las tres pestañas (Chat/Codebase/Obsidian). Los tests de contenido
de cada pestaña viven en test_chat_view.py/test_codebase_view.py/
test_obsidian_view.py -- acá solo se prueba el wiring de MainWindow."""

import requests

from ui.chat_view import ChatView
from ui.codebase_view import CodebaseView
from ui.main_window import MainWindow
from ui.obsidian_view import ObsidianView
from ui.settings_window import SettingsDialog


class _FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {"notes": [], "projects": [], "nodes": [], "edges": []}


def _no_network(monkeypatch):
    # ObsidianView pide su grafo de notas y CodebaseView pide el último
    # proyecto indexado apenas se construyen -- sin esto, cada test de
    # MainWindow intentaría pegarle al backend real.
    monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResponse())


def test_has_the_three_expected_tabs(qtbot, monkeypatch):
    _no_network(monkeypatch)
    win = MainWindow()
    qtbot.addWidget(win)

    labels = [win.tabs.tabText(i) for i in range(win.tabs.count())]
    assert len(labels) == 3
    assert "Chat" in labels[0]
    assert "Codebase" in labels[1]
    assert "Obsidian" in labels[2]

    assert isinstance(win.chat_view, ChatView)
    assert isinstance(win.codebase_view, CodebaseView)
    assert isinstance(win.obsidian_view, ObsidianView)


def test_model_selector_shows_the_three_tiers_with_friendly_labels(qtbot, monkeypatch):
    _no_network(monkeypatch)
    win = MainWindow()
    qtbot.addWidget(win)

    labels = [win.model_selector.itemText(i) for i in range(win.model_selector.count())]
    ids = [win.model_selector.itemData(i) for i in range(win.model_selector.count())]

    assert labels == ["Lite", "Medio", "Hard"]
    assert ids == ["jarvis-text-lite", "jarvis-text-v2", "jarvis-text-hard"]


def test_model_selector_preselects_the_tier_matching_the_env(qtbot, tmp_path, monkeypatch):
    _no_network(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text("LMSTUDIO_MODEL=jarvis-text-hard\n", encoding="utf-8")
    import config

    monkeypatch.setattr(config, "ENV_PATH", env_file)

    win = MainWindow()
    qtbot.addWidget(win)

    assert win.model_selector.currentText() == "Hard"
    assert win.model_selector.currentData() == "jarvis-text-hard"


def test_settings_icon_opens_a_dialog_separate_from_the_main_chat_view(qtbot, monkeypatch):
    _no_network(monkeypatch)
    win = MainWindow()
    qtbot.addWidget(win)

    assert win._settings_dialog is None  # no se crea hasta que se pide

    win._on_open_settings()

    assert isinstance(win._settings_dialog, SettingsDialog)
    assert win._settings_dialog.isVisible()
    assert win._settings_dialog is not win  # ventana aparte, no un panel embebido


def test_settings_icon_reuses_the_same_dialog_instead_of_duplicating(qtbot, monkeypatch):
    _no_network(monkeypatch)
    win = MainWindow()
    qtbot.addWidget(win)

    win._on_open_settings()
    first = win._settings_dialog
    win._on_open_settings()

    assert win._settings_dialog is first


def test_model_switch_message_goes_into_the_chat_tab(qtbot, monkeypatch):
    _no_network(monkeypatch)
    win = MainWindow()
    qtbot.addWidget(win)

    before = win.chat_view._messages_layout.count()
    win._on_model_switched("jarvis-text-hard")

    assert win.chat_view._messages_layout.count() == before + 1
