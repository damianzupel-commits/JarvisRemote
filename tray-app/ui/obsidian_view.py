"""Vista de la pestaña "Obsidian" -- dibuja el grafo de notas del vault del
backend (`app/obsidian/vault.py`, vía `/api/obsidian/graph`), coloreadas por
autor (Jarvis vs. humano) para que las dos autorías se distingan a simple
vista sin mezclarse, con edges por los wikilinks `[[...]]` reales entre notas
(mismo criterio que el grafo real de Obsidian). Las notas humanas se pueden
crear/editar/borrar desde acá; las de Jarvis son de solo lectura (las escribe
la tool `obsidian_save_note`, ver backend/app/tools/obsidian.py)."""

import requests
from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import config
from ui.colors import color_for_author
from ui.graph_view import GraphView

_AUTHOR_LABELS = {"jarvis": "Jarvis", "human": "Humano"}
_AUTH_HEADER = {"Authorization": f"Bearer {config.API_KEY}"}


class ObsidianBridge(QObject):
    graph_ready = Signal(dict)
    note_ready = Signal(dict)
    saved = Signal()
    deleted = Signal()
    error = Signal(str)


class GraphFetchThread(QThread):
    """`retry=True` reintenta unas cuantas veces antes de rendirse -- lo usa
    solo la carga inicial (`ObsidianView.__init__`), porque `tray.py` arranca
    la ventana y el subproceso del backend en paralelo (ver `main()`), así
    que ese primer pedido puede pegarle a un backend que todavía no levantó
    el puerto (mismo bug real que tenía CodebaseView, ver RecentProjectsThread
    en codebase_view.py). Los refrescos disparados por el usuario (filtro de
    autor, guardar/borrar una nota) no lo necesitan -- para esos ya sabemos
    que el backend está arriba porque algo anterior le pegó con éxito."""

    _MAX_ATTEMPTS = 10
    _RETRY_DELAY_SECONDS = 1.5

    def __init__(self, bridge: ObsidianBridge, retry: bool = False):
        super().__init__()
        self._bridge = bridge
        self._max_attempts = self._MAX_ATTEMPTS if retry else 1

    def run(self) -> None:
        for attempt in range(1, self._max_attempts + 1):
            try:
                resp = requests.get(config.OBSIDIAN_GRAPH_URL, headers=_AUTH_HEADER, timeout=30)
                resp.raise_for_status()
                self._bridge.graph_ready.emit(resp.json())
                return
            except requests.RequestException as exc:
                if attempt == self._max_attempts:
                    self._bridge.error.emit(f"No pude cargar las notas: {exc}")
                    return
                self.msleep(int(self._RETRY_DELAY_SECONDS * 1000))


class GetNoteThread(QThread):
    def __init__(self, note_id: str, bridge: ObsidianBridge):
        super().__init__()
        self._note_id = note_id
        self._bridge = bridge

    def run(self) -> None:
        try:
            resp = requests.get(f"{config.OBSIDIAN_NOTES_URL}/{self._note_id}", headers=_AUTH_HEADER, timeout=30)
            resp.raise_for_status()
            self._bridge.note_ready.emit(resp.json())
        except requests.RequestException as exc:
            self._bridge.error.emit(f"No pude abrir la nota: {exc}")


class SaveNoteThread(QThread):
    def __init__(self, title: str, content: str, tags: list[str], note_id: str | None, bridge: ObsidianBridge):
        super().__init__()
        self._payload = {"title": title, "content": content, "tags": tags, "note_id": note_id}
        self._bridge = bridge

    def run(self) -> None:
        try:
            resp = requests.post(config.OBSIDIAN_NOTES_URL, json=self._payload, headers=_AUTH_HEADER, timeout=30)
            resp.raise_for_status()
            self._bridge.saved.emit()
        except requests.RequestException as exc:
            self._bridge.error.emit(f"No pude guardar la nota: {exc}")


class DeleteNoteThread(QThread):
    def __init__(self, note_id: str, bridge: ObsidianBridge):
        super().__init__()
        self._note_id = note_id
        self._bridge = bridge

    def run(self) -> None:
        try:
            resp = requests.delete(f"{config.OBSIDIAN_NOTES_URL}/{self._note_id}", headers=_AUTH_HEADER, timeout=30)
            resp.raise_for_status()
            self._bridge.deleted.emit()
        except requests.RequestException as exc:
            self._bridge.error.emit(f"No pude borrar la nota: {exc}")


class NoteEditorDialog(QDialog):
    def __init__(self, parent=None, note: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Editar nota" if note else "Nueva nota")
        self.note_id = note["id"] if note else None

        layout = QVBoxLayout(self)

        self.title_input = QLineEdit(note["title"] if note else "")
        self.title_input.setPlaceholderText("Título")
        layout.addWidget(self.title_input)

        self.tags_input = QLineEdit(", ".join(note.get("tags", [])) if note else "")
        self.tags_input.setPlaceholderText("Tags separados por coma")
        layout.addWidget(self.tags_input)

        self.content_input = QTextEdit(note.get("content", "") if note else "")
        self.content_input.setPlaceholderText("Contenido en Markdown...")
        layout.addWidget(self.content_input, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.resize(480, 420)

    def data(self) -> dict:
        tags = [t.strip() for t in self.tags_input.text().split(",") if t.strip()]
        return {
            "title": self.title_input.text().strip(),
            "content": self.content_input.toPlainText(),
            "tags": tags,
            "note_id": self.note_id,
        }


class ObsidianView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("obsidianView")

        self._bridge = ObsidianBridge()
        self._bridge.graph_ready.connect(self._on_graph_ready)
        self._bridge.note_ready.connect(self._on_note_ready)
        self._bridge.saved.connect(self._on_saved)
        self._bridge.deleted.connect(self._on_deleted)
        self._bridge.error.connect(self._on_error)
        self._threads: list[QThread] = []
        self._current_note: dict | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addLayout(self._build_toolbar())

        self.status_label = QLabel("")
        self.status_label.setObjectName("obsidianStatus")
        layout.addWidget(self.status_label)

        splitter = QSplitter(Qt.Horizontal)
        self.graph_view = GraphView()
        self.graph_view.node_clicked.connect(self._on_node_clicked)
        splitter.addWidget(self.graph_view)

        self.detail_panel = self._build_detail_panel()
        splitter.addWidget(self.detail_panel)
        splitter.setSizes([280, 400])
        layout.addWidget(splitter, stretch=1)

        self.refresh_notes(retry=True)

    # ------------------------------------------------------------- layout

    def _build_toolbar(self) -> QHBoxLayout:
        row = QHBoxLayout()

        self.author_filter = QComboBox()
        self.author_filter.addItem("Todos", userData=None)
        self.author_filter.addItem("Jarvis", userData="jarvis")
        self.author_filter.addItem("Humano", userData="human")
        self.author_filter.currentIndexChanged.connect(lambda _i: self.refresh_notes())
        row.addWidget(self.author_filter)

        row.addStretch()

        new_note_button = QPushButton("+ Nueva nota")
        new_note_button.setObjectName("sendButton")
        new_note_button.clicked.connect(self._on_new_note_clicked)
        row.addWidget(new_note_button)

        return row

    def _build_detail_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        self.detail_title = QLabel("")
        self.detail_title.setObjectName("obsidianDetailTitle")
        self.detail_title.setWordWrap(True)
        layout.addWidget(self.detail_title)

        self.detail_meta = QLabel("")
        self.detail_meta.setObjectName("obsidianDetailMeta")
        layout.addWidget(self.detail_meta)

        self.detail_content = QTextEdit()
        self.detail_content.setReadOnly(True)
        layout.addWidget(self.detail_content, stretch=1)

        actions_row = QHBoxLayout()
        self.edit_button = QPushButton("Editar")
        self.edit_button.clicked.connect(self._on_edit_clicked)
        self.edit_button.setEnabled(False)
        actions_row.addWidget(self.edit_button)

        self.delete_button = QPushButton("Borrar")
        self.delete_button.clicked.connect(self._on_delete_clicked)
        self.delete_button.setEnabled(False)
        actions_row.addWidget(self.delete_button)
        actions_row.addStretch()
        layout.addLayout(actions_row)

        return panel

    # ------------------------------------------------------------- datos

    def refresh_notes(self, retry: bool = False) -> None:
        self.status_label.setText("Cargando notas...")
        thread = GraphFetchThread(self._bridge, retry=retry)
        self._threads.append(thread)
        thread.start()

    def _on_graph_ready(self, graph: dict) -> None:
        author = self.author_filter.currentData()
        nodes = graph["nodes"] if not author else [n for n in graph["nodes"] if n["author"] == author]
        node_ids = {n["id"] for n in nodes}
        edges = [e for e in graph["edges"] if e["source"] in node_ids and e["target"] in node_ids]

        self.status_label.setText(f"{len(nodes)} notas")
        self.graph_view.set_graph(
            nodes,
            edges,
            id_key="id",
            color_fn=lambda n: color_for_author(n["author"]),
            label_fn=lambda n: n["title"],
        )

    def _on_node_clicked(self, note_id: str) -> None:
        thread = GetNoteThread(note_id, self._bridge)
        self._threads.append(thread)
        thread.start()

    def _on_note_ready(self, note: dict) -> None:
        self._current_note = note
        self.detail_title.setText(note["title"])
        self.detail_title.setStyleSheet(f"color: {color_for_author(note['author'])}; font-size: 16px; font-weight: 600;")
        tags = ", ".join(note.get("tags", []))
        self.detail_meta.setText(f"{_AUTHOR_LABELS.get(note['author'], note['author'])} · {tags or 'sin tags'}")
        self.detail_content.setPlainText(note.get("content", ""))
        is_human = note["author"] == "human"
        self.edit_button.setEnabled(is_human)
        self.delete_button.setEnabled(is_human)

    def _on_error(self, message: str) -> None:
        self.status_label.setText(message)

    # ------------------------------------------------------------- crear/editar/borrar

    def _on_new_note_clicked(self) -> None:
        dialog = NoteEditorDialog(self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.data()
            if not data["title"]:
                return
            self._save_note(data)

    def _on_edit_clicked(self) -> None:
        if not self._current_note:
            return
        dialog = NoteEditorDialog(self, note=self._current_note)
        if dialog.exec() == QDialog.Accepted:
            self._save_note(dialog.data())

    def _save_note(self, data: dict) -> None:
        thread = SaveNoteThread(data["title"], data["content"], data["tags"], data["note_id"], self._bridge)
        self._threads.append(thread)
        thread.start()

    def _on_saved(self) -> None:
        self.refresh_notes()

    def _on_delete_clicked(self) -> None:
        if not self._current_note:
            return
        thread = DeleteNoteThread(self._current_note["id"], self._bridge)
        self._threads.append(thread)
        thread.start()

    def _on_deleted(self) -> None:
        self._current_note = None
        self.detail_title.setText("")
        self.detail_meta.setText("")
        self.detail_content.setPlainText("")
        self.edit_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.refresh_notes()
