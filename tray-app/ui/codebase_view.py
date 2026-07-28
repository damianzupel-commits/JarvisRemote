"""Vista de la pestaña "Codebase" -- le pide al backend que indexe un
proyecto (`app/codebase/` del lado del backend, vía `/api/codebase/index`) y
dibuja el grafo de archivos relacionados por imports reales (coloreados por
lenguaje, vía `/api/codebase/graph`). El panel derecho usa las dos mitades
que separa el splitter: arriba el detalle de símbolos (funciones/clases/
imports) del archivo seleccionado, abajo su contenido real (vía
`/api/codebase/file`) para poder leer el código sin salir de la ventana --
click en un nodo del grafo llena ambos paneles a la vez."""

import requests
from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import config
from ui.colors import color_for_language
from ui.graph_view import GraphView

_SYMBOL_ICON = {"function": "🔧", "class": "🏛", "import": "📦"}


class CodebaseBridge(QObject):
    index_ready = Signal(dict)
    index_error = Signal(str)
    recent_ready = Signal(list)
    graph_ready = Signal(dict)
    file_ready = Signal(dict)
    file_error = Signal(str)


class RecentProjectsThread(QThread):
    """Solo para precargar la pestaña al abrirla. `tray.py` arranca la
    ventana principal y el subproceso del backend en paralelo (ver
    `main()`), así que el primer intento puede pegarle a un backend que
    todavía no levantó el puerto -- reintenta unas cuantas veces con espera
    antes de rendirse en silencio (bug real: sin el reintento, la pestaña
    quedaba vacía la mayoría de las veces que la tray arrancaba en frío)."""

    _MAX_ATTEMPTS = 10
    _RETRY_DELAY_SECONDS = 1.5

    def __init__(self, bridge: CodebaseBridge):
        super().__init__()
        self._bridge = bridge

    def run(self) -> None:
        for attempt in range(1, self._MAX_ATTEMPTS + 1):
            try:
                resp = requests.get(
                    config.CODEBASE_RECENT_URL,
                    headers={"Authorization": f"Bearer {config.API_KEY}"},
                    timeout=10,
                )
                resp.raise_for_status()
                self._bridge.recent_ready.emit(resp.json()["projects"])
                return
            except requests.RequestException:
                if attempt == self._MAX_ATTEMPTS:
                    return
                self.msleep(int(self._RETRY_DELAY_SECONDS * 1000))


class IndexFetchThread(QThread):
    def __init__(self, path: str, refresh: bool, bridge: CodebaseBridge):
        super().__init__()
        self._path = path
        self._refresh = refresh
        self._bridge = bridge

    def run(self) -> None:
        try:
            resp = requests.get(
                config.CODEBASE_INDEX_URL,
                params={"path": self._path, "refresh": str(self._refresh).lower()},
                headers={"Authorization": f"Bearer {config.API_KEY}"},
                timeout=180,
            )
            resp.raise_for_status()
            self._bridge.index_ready.emit(resp.json())
        except requests.RequestException as exc:
            self._bridge.index_error.emit(f"No pude indexar el proyecto: {exc}")


class GraphFetchThread(QThread):
    def __init__(self, path: str, bridge: CodebaseBridge):
        super().__init__()
        self._path = path
        self._bridge = bridge

    def run(self) -> None:
        try:
            resp = requests.get(
                config.CODEBASE_GRAPH_URL,
                params={"path": self._path},
                headers={"Authorization": f"Bearer {config.API_KEY}"},
                timeout=180,
            )
            resp.raise_for_status()
            self._bridge.graph_ready.emit(resp.json())
        except requests.RequestException as exc:
            self._bridge.index_error.emit(f"No pude armar el grafo: {exc}")


class FileContentFetchThread(QThread):
    def __init__(self, root: str, file_path: str, bridge: CodebaseBridge):
        super().__init__()
        self._root = root
        self._file_path = file_path
        self._bridge = bridge

    def run(self) -> None:
        try:
            resp = requests.get(
                config.CODEBASE_FILE_URL,
                params={"path": self._root, "file": self._file_path},
                headers={"Authorization": f"Bearer {config.API_KEY}"},
                timeout=30,
            )
            resp.raise_for_status()
            self._bridge.file_ready.emit(resp.json())
        except requests.RequestException as exc:
            self._bridge.file_error.emit(f"No pude leer '{self._file_path}': {exc}")


class LanguageBar(QWidget):
    """Barra de desglose de lenguajes con leyenda, al estilo de la barra de
    lenguajes de GitHub -- un chip coloreado por lenguaje con su porcentaje
    de líneas de código."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(12)
        self._layout.addStretch()

    def set_languages(self, languages: list[dict]) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        total_lines = sum(l["line_count"] for l in languages) or 1
        for lang in languages:
            pct = round(100 * lang["line_count"] / total_lines)
            chip = QLabel(f"●  {lang['language']}  {pct}%")
            chip.setObjectName("languageChip")
            chip.setStyleSheet(f"color: {color_for_language(lang['language'])}; font-size: 12px;")
            self._layout.addWidget(chip)
        self._layout.addStretch()


class CodebaseView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("codebaseView")

        self._bridge = CodebaseBridge()
        self._bridge.index_ready.connect(self._on_index_ready)
        self._bridge.index_error.connect(self._on_index_error)
        self._bridge.recent_ready.connect(self._on_recent_ready)
        self._bridge.graph_ready.connect(self._on_graph_ready)
        self._bridge.file_ready.connect(self._on_file_ready)
        self._bridge.file_error.connect(self._on_file_error)
        self._fetch_thread: IndexFetchThread | None = None
        self._recent_thread: RecentProjectsThread | None = None
        self._graph_thread: GraphFetchThread | None = None
        self._file_thread: FileContentFetchThread | None = None
        self._current_index: dict | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addLayout(self._build_path_row())

        self.status_label = QLabel("")
        self.status_label.setObjectName("codebaseStatus")
        layout.addWidget(self.status_label)

        self.language_bar = LanguageBar()
        layout.addWidget(self.language_bar)

        splitter = QSplitter(Qt.Horizontal)
        self.graph_view = GraphView()
        self.graph_view.node_clicked.connect(self._on_node_clicked)
        splitter.addWidget(self.graph_view)

        right_panel = QSplitter(Qt.Vertical)
        self.symbol_list = QListWidget()
        right_panel.addWidget(self.symbol_list)

        self.code_viewer = QTextEdit()
        self.code_viewer.setObjectName("codeViewer")
        self.code_viewer.setReadOnly(True)
        self.code_viewer.setLineWrapMode(QTextEdit.NoWrap)
        self.code_viewer.setPlaceholderText("Click en un nodo del grafo para ver su código acá.")
        _code_font = QFont("Consolas")
        _code_font.setStyleHint(QFont.Monospace)
        _code_font.setPointSize(10)
        self.code_viewer.setFont(_code_font)
        right_panel.addWidget(self.code_viewer)
        right_panel.setSizes([120, 480])

        splitter.addWidget(right_panel)
        splitter.setSizes([460, 460])
        layout.addWidget(splitter, stretch=1)

        self._recent_thread = RecentProjectsThread(self._bridge)
        self._recent_thread.start()

    # ------------------------------------------------------------- layout

    def _build_path_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setObjectName("codebasePathInput")
        self.path_input.setPlaceholderText("Ruta de la carpeta del proyecto a analizar...")
        row.addWidget(self.path_input, stretch=1)

        browse_button = QPushButton("Examinar...")
        browse_button.clicked.connect(self._on_browse_clicked)
        row.addWidget(browse_button)

        self.index_button = QPushButton("Indexar")
        self.index_button.setObjectName("sendButton")
        self.index_button.clicked.connect(lambda: self._start_index(refresh=False))
        row.addWidget(self.index_button)

        self.reindex_button = QPushButton("Reindexar")
        self.reindex_button.clicked.connect(lambda: self._start_index(refresh=True))
        row.addWidget(self.reindex_button)

        return row

    # ------------------------------------------------------------- acciones

    def _on_browse_clicked(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Elegir carpeta del proyecto")
        if directory:
            self.path_input.setText(directory)

    def _start_index(self, refresh: bool) -> None:
        path = self.path_input.text().strip()
        if not path:
            return
        self.index_button.setEnabled(False)
        self.reindex_button.setEnabled(False)
        self.status_label.setText("Indexando, puede tardar un momento en proyectos grandes...")
        self._fetch_thread = IndexFetchThread(path, refresh, self._bridge)
        self._fetch_thread.start()

    def _on_index_ready(self, index: dict) -> None:
        self.index_button.setEnabled(True)
        self.reindex_button.setEnabled(True)
        self._current_index = index
        self.status_label.setText(
            f"{index['file_count']} archivos, lenguaje principal: {index.get('primary_language') or '—'}"
            " -- armando el grafo..."
        )
        self.language_bar.set_languages(index["languages"])
        self.symbol_list.clear()

        self._graph_thread = GraphFetchThread(index["root"], self._bridge)
        self._graph_thread.start()

    def _on_graph_ready(self, graph: dict) -> None:
        if self._current_index is None:
            return
        self.status_label.setText(
            f"{self._current_index['file_count']} archivos, "
            f"lenguaje principal: {self._current_index.get('primary_language') or '—'}"
        )
        self.graph_view.set_graph(
            self._current_index["files"],
            graph["edges"],
            id_key="path",
            color_fn=lambda f: color_for_language(f["language"]),
            label_fn=lambda f: f["path"].rsplit("/", 1)[-1],
        )

    def _on_index_error(self, message: str) -> None:
        self.index_button.setEnabled(True)
        self.reindex_button.setEnabled(True)
        self.status_label.setText(message)

    def _on_recent_ready(self, projects: list[dict]) -> None:
        # Solo al abrir la pestaña por primera vez -- si el usuario ya escribió
        # algo (o ya disparó un índice) no le pisamos el campo.
        if not projects or self.path_input.text().strip() or self._current_index is not None:
            return
        self.path_input.setText(projects[0]["root"])
        self._start_index(refresh=False)

    # ------------------------------------------------------------- grafo

    def _on_node_clicked(self, path: str) -> None:
        self.symbol_list.clear()
        self.code_viewer.setPlainText("")
        if self._current_index is None:
            return
        file_entry = next((f for f in self._current_index["files"] if f["path"] == path), None)
        if file_entry is None:
            return
        for sym in file_entry.get("symbols", []):
            icon = _SYMBOL_ICON.get(sym["kind"], "•")
            list_item = QListWidgetItem(f"{icon}  {sym['name']}   (línea {sym['line']})")
            self.symbol_list.addItem(list_item)

        self.code_viewer.setPlainText("Cargando...")
        self._file_thread = FileContentFetchThread(self._current_index["root"], path, self._bridge)
        self._file_thread.start()

    def _on_file_ready(self, data: dict) -> None:
        self.code_viewer.setPlainText(data["content"])

    def _on_file_error(self, message: str) -> None:
        self.code_viewer.setPlainText(message)
