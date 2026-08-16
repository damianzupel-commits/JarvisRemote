"""Vista de la pestaña "Investigación" -- lista los casos del módulo de
investigación (`app/investigation/`, backend) en un selector, y dibuja el
grafo de entidades/aristas del caso elegido (vía
`/api/investigation/{case_id}/graph`) coloreado por tipo de entidad, con el
halo de centralidad+confianza (ver ui/investigation_colors.py). Sin panel de
edición -- a diferencia de Obsidian, esta vista es de solo lectura: crear/
editar el grafo pasa por el chat (tools investigation_*, ver
backend/app/tools/investigation.py), nunca desde acá directamente, mismo
principio que separa "el modelo propone, Damian confirma" del resto del
módulo."""

import requests
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QListWidget, QListWidgetItem, QSplitter, QVBoxLayout, QWidget

import config
from ui.graph_view import GraphView
from ui.investigation_colors import color_for_node_type, investigation_halo
from ui.widgets import NoMinWidthLabel

_AUTH_HEADER = {"Authorization": f"Bearer {config.API_KEY}"}

_CONTRADICTION_BG = QColor("#7f1d1d")  # mismo espíritu que CascadeToast (codebase_view.py): fondo rojo oscuro de alerta


class InvestigationBridge(QObject):
    cases_ready = Signal(list)
    graph_ready = Signal(dict)
    timeline_ready = Signal(dict)
    error = Signal(str)


class CasesFetchThread(QThread):
    """`retry=True` solo en la carga inicial -- mismo motivo real que
    ObsidianView.GraphFetchThread: tray.py arranca la ventana y el backend
    en paralelo, así que el primer pedido puede pegarle a un puerto que
    todavía no levantó."""

    _MAX_ATTEMPTS = 10
    _RETRY_DELAY_SECONDS = 1.5

    def __init__(self, bridge: InvestigationBridge, retry: bool = False):
        super().__init__()
        self._bridge = bridge
        self._max_attempts = self._MAX_ATTEMPTS if retry else 1

    def run(self) -> None:
        for attempt in range(1, self._max_attempts + 1):
            try:
                resp = requests.get(config.INVESTIGATION_CASES_URL, headers=_AUTH_HEADER, timeout=30)
                resp.raise_for_status()
                self._bridge.cases_ready.emit(resp.json()["cases"])
                return
            except requests.RequestException as exc:
                if attempt == self._max_attempts:
                    self._bridge.error.emit(f"No pude cargar los casos: {exc}")
                    return
                self.msleep(int(self._RETRY_DELAY_SECONDS * 1000))


class CaseGraphFetchThread(QThread):
    def __init__(self, case_id: str, bridge: InvestigationBridge):
        super().__init__()
        self._case_id = case_id
        self._bridge = bridge

    def run(self) -> None:
        try:
            resp = requests.get(
                f"{config.INVESTIGATION_GRAPH_URL}/{self._case_id}/graph", headers=_AUTH_HEADER, timeout=30
            )
            resp.raise_for_status()
            self._bridge.graph_ready.emit(resp.json())
        except requests.RequestException as exc:
            self._bridge.error.emit(f"No pude cargar el grafo del caso: {exc}")


class TimelineFetchThread(QThread):
    def __init__(self, case_id: str, entity_id: str | None, bridge: InvestigationBridge):
        super().__init__()
        self._case_id = case_id
        self._entity_id = entity_id
        self._bridge = bridge

    def run(self) -> None:
        try:
            params = {"entity_id": self._entity_id} if self._entity_id else {}
            resp = requests.get(
                f"{config.INVESTIGATION_GRAPH_URL}/{self._case_id}/timeline",
                headers=_AUTH_HEADER, params=params, timeout=30,
            )
            resp.raise_for_status()
            self._bridge.timeline_ready.emit(resp.json())
        except requests.RequestException as exc:
            self._bridge.error.emit(f"No pude cargar la timeline: {exc}")


class InvestigationView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("investigationView")

        self._bridge = InvestigationBridge()
        self._bridge.cases_ready.connect(self._on_cases_ready)
        self._bridge.graph_ready.connect(self._on_graph_ready)
        self._bridge.timeline_ready.connect(self._on_timeline_ready)
        self._bridge.error.connect(self._on_error)
        self._threads: list[QThread] = []
        self._current_case_id: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        self.case_selector = QComboBox()
        self.case_selector.currentIndexChanged.connect(self._on_case_selected)
        toolbar.addWidget(self.case_selector)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # NoMinWidthLabel, no QLabel a secas -- mensajes de error de conexión
        # (URLs/reprs largos sin espacios) no deben estirar la ventana
        # principal, ver ui/widgets.py.
        self.status_label = NoMinWidthLabel("Cargando casos...")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.graph_view = GraphView()
        self.graph_view.node_clicked.connect(self._on_node_clicked)

        # spec sección 4: la timeline corre "en paralelo al grafo" -- splitter
        # horizontal en vez de una pestaña aparte, para que seleccionar un
        # nodo y ver su timeline filtrada sea inmediato, sin cambiar de vista.
        self.timeline_list = QListWidget()
        self.timeline_list.setMinimumWidth(280)

        splitter = QSplitter()
        splitter.addWidget(self.graph_view)
        splitter.addWidget(self.timeline_list)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, stretch=1)

        self.refresh_cases(retry=True)

    def refresh_cases(self, retry: bool = False) -> None:
        thread = CasesFetchThread(self._bridge, retry=retry)
        self._threads.append(thread)
        thread.start()

    def _on_cases_ready(self, cases: list[dict]) -> None:
        self.case_selector.blockSignals(True)
        self.case_selector.clear()
        for case in cases:
            self.case_selector.addItem(case["titulo"], userData=case["id"])
        self.case_selector.blockSignals(False)

        if not cases:
            self.status_label.setText("Todavía no hay ningún caso -- creá uno desde el chat (investigation_create_case).")
            self.graph_view.set_graph([], [], id_key="id", color_fn=lambda n: "#9aa0ab", label_fn=lambda n: "")
            return

        self.status_label.setText(f"{len(cases)} caso(s)")
        self._load_case_graph(cases[0]["id"])

    def _on_case_selected(self, _index: int) -> None:
        case_id = self.case_selector.currentData()
        if case_id:
            self._load_case_graph(case_id)

    def _load_case_graph(self, case_id: str) -> None:
        self._current_case_id = case_id
        self.status_label.setText("Cargando grafo...")
        thread = CaseGraphFetchThread(case_id, self._bridge)
        self._threads.append(thread)
        thread.start()
        self._load_timeline(case_id)

    def _load_timeline(self, case_id: str, entity_id: str | None = None) -> None:
        thread = TimelineFetchThread(case_id, entity_id, self._bridge)
        self._threads.append(thread)
        thread.start()

    def _on_node_clicked(self, node_id: str) -> None:
        if self._current_case_id:
            self._load_timeline(self._current_case_id, entity_id=node_id)

    def _on_timeline_ready(self, data: dict) -> None:
        self.timeline_list.clear()
        for contradiction in data.get("contradictions", []):
            item = QListWidgetItem(f"⚠ {contradiction['reason']}")
            item.setBackground(_CONTRADICTION_BG)
            self.timeline_list.addItem(item)
        for entry in data.get("entries", []):
            text = f"[{entry['timestamp_utc']}] {entry['kind']}: {entry['description']}"
            self.timeline_list.addItem(QListWidgetItem(text))

    def _on_graph_ready(self, graph: dict) -> None:
        nodes = graph["nodes"]
        edges = graph["edges"]
        self.status_label.setText(f"{len(nodes)} entidad(es), {len(edges)} relación(es)")

        def _label(n: dict) -> str:
            campos = n.get("campos", {})
            return campos.get("etiqueta") or campos.get("handle") or campos.get("nombre") or campos.get("descripcion") or n["id"]

        self.graph_view.set_graph(
            nodes,
            edges,
            id_key="id",
            color_fn=lambda n: color_for_node_type(n["tipo"]),
            label_fn=_label,
            halo_fn=lambda n: investigation_halo(n["centrality"], n["confidence"]),
        )

    def _on_error(self, message: str) -> None:
        self.status_label.setText(message)
