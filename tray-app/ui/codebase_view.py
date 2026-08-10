"""Vista de la pestaña "Codebase" -- le pide al backend que indexe un
proyecto (`app/codebase/` del lado del backend, vía `/api/codebase/index`) y
dibuja el grafo de archivos relacionados por imports reales (coloreados por
lenguaje, vía `/api/codebase/graph`). El panel derecho usa las dos mitades
que separa el splitter: arriba el detalle de símbolos (funciones/clases/
imports) del archivo seleccionado, abajo su contenido real (vía
`/api/codebase/file`) para poder leer el código sin salir de la ventana --
click en un nodo del grafo llena ambos paneles a la vez."""

import requests
from PySide6.QtCore import QObject, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor, QTextFormat
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import config
from ui.colors import color_for_language, color_for_severity
from ui.graph_view import GraphView
from ui.widgets import NoMinWidthLabel

_SYMBOL_ICON = {"function": "🔧", "class": "🏛", "import": "📦"}
_FINDING_SEVERITY_ICON = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}
_SEVERITY_LABEL = {"critical": "crítico", "high": "alto", "medium": "medio", "low": "bajo", "info": "informativo"}
_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

# Cada cuánto se re-consulta el backend mientras hay un proyecto cargado, para
# reflejar solo/a los fixes aplicados desde el chat (code_apply_fix) sin que
# el usuario tenga que apretar "Reindexar" a mano -- ver _on_poll_tick. No es
# push real (el backend no tiene WebSocket/SSE para esto), pero a este
# intervalo el costo es bajo (ambos endpoints solo leen cache en disco, no
# reescanean nada) y la demora percibida es chica.
_POLL_INTERVAL_MS = 4000


def _highlight_color_for_severity(severity: str) -> QColor | None:
    """Mismo criterio de color que el halo del grafo 3D (`color_for_severity`,
    rojo/naranja/amarillo para critical/high/medium) -- "low"/"info" no llevan
    marca acá tampoco, consistente con que tampoco llevan halo. Alpha bajo
    porque esto es un fondo detrás de texto que hay que poder seguir leyendo,
    no un bloque sólido."""
    hex_color = color_for_severity(severity)
    if not hex_color:
        return None
    color = QColor(hex_color)
    color.setAlpha(80)
    return color


def _describe_resolved(resolved: list[dict]) -> str:
    """Mismo criterio que el backend (`app/tools/code_edit.py::_describe_cascade`)
    pero calculado acá con lo que ya se tiene en la UI -- puro diff de ids
    entre el findings list anterior y el nuevo (ver _update_findings), no hace
    falta que el backend nos mande la causalidad."""
    counts: dict[str, int] = {}
    for f in resolved:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    breakdown = ", ".join(
        f"{n} {_SEVERITY_LABEL.get(sev, sev)}"
        for sev, n in sorted(counts.items(), key=lambda kv: _SEVERITY_ORDER.get(kv[0], 9))
    )
    return f"✅ Se resolvieron {len(resolved)} hallazgo(s) en este archivo ({breakdown})."


class CascadeToast(QLabel):
    """Notificación temporal (\"toast\") que aparece cuando arreglar un
    hallazgo resuelve otros de rebote -- se autoesconde sola después de unos
    segundos, no hace falta cerrarla a mano. Pensada para que alguien sin
    conocimientos de programación note el efecto sin tener que comparar listas
    de hallazgos antes/después a mano."""

    _AUTO_HIDE_MS = 10000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cascadeToast")
        self.setWordWrap(True)
        self.setStyleSheet(
            "background: #14532d; color: #bbf7d0; border: 1px solid #22c55e; "
            "border-radius: 8px; padding: 8px 12px; font-size: 13px;"
        )
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text: str) -> None:
        self.setText(text)
        self.show()
        self._timer.start(self._AUTO_HIDE_MS)


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


class _HorizontalChipBar(QScrollArea):
    """Base de una fila horizontal de chips (idioma o severidad) que NUNCA
    debe forzar que la ventana principal crezca para acomodarla sin wrap --
    bug real reportado en vivo ("la ventana se ve ultra alargada, no entra en
    mi pantalla"): con un proyecto de muchos lenguajes (Luanti, C/C++, 9+
    lenguajes detectados) la fila sin wrap medía más de 1000px de ancho, y
    como `LanguageBar` era un QWidget plano dentro del layout, ese ancho se
    propagaba como tamaño preferido del contenedor -- la ventana (900px)
    crecía para acomodarlo (llegó a 1112px, confirmado en vivo) y Qt NUNCA la
    volvía a achicar sola (no hay "shrink to fit" automático para ventanas
    top-level), quedando agrandada para el resto de la sesión. Nada de esto
    tiene que ver con los paneles agregados en rondas anteriores (halo de
    severidad, panel de hallazgos) -- es un bug preexistente en este widget,
    confirmado con `LanguageBar`/`RiskLegend` reproduciendo el crecimiento
    incluso con esos paneles nuevos completamente sacados del layout.

    Envolver la fila en un QScrollArea (en vez de un QWidget con QHBoxLayout
    a secas) hace que el contenido interno pueda ser arbitrariamente ancho
    SIN que eso se propague hacia afuera como tamaño preferido -- lo que no
    entra, scrollea horizontalmente en vez de estirar la ventana. El
    `sizeHint()` fijo es la garantía adicional (cinturón y tirantes): no
    depende del contenido bajo ninguna circunstancia."""

    _FIXED_HEIGHT = 28

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self.setFixedHeight(self._FIXED_HEIGHT)

        inner = QWidget()
        self.setWidget(inner)
        self._layout = QHBoxLayout(inner)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(12)

    def sizeHint(self) -> QSize:
        return QSize(200, self._FIXED_HEIGHT)


class LanguageBar(_HorizontalChipBar):
    """Barra de desglose de lenguajes con leyenda, al estilo de la barra de
    lenguajes de GitHub -- un chip coloreado por lenguaje con su porcentaje
    de líneas de código."""

    def __init__(self, parent=None):
        super().__init__(parent)
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


class RiskLegend(_HorizontalChipBar):
    """Leyenda de la capa de severidad (halo alrededor del nodo, ver
    graph_view.py/graph3d.html) que se superpone al color de lenguaje
    (relleno) de LanguageBar -- aclara que son dos capas de color distintas.

    Si el proyecto todavía no tiene ningún escaneo cacheado (`security_scan_project`/
    `quality_scan_project` nunca corrieron), lo dice explícitamente en vez de
    mostrar la leyenda como si "sin halo" significara "sin hallazgos" -- mentira
    visual que el usuario pidió evitar."""

    _SEVERITIES = (("Crítico", "#ef4444"), ("Alto", "#f97316"), ("Medio", "#eab308"))

    def __init__(self, parent=None):
        super().__init__(parent)

        self._status_label = QLabel("")
        self._status_label.setObjectName("riskLegendStatus")
        self._status_label.setStyleSheet("color: #9aa0ab; font-size: 12px;")
        self._layout.addWidget(self._status_label)
        self._layout.addStretch()

        for label, color in self._SEVERITIES:
            chip = QLabel(f"◯  {label}")
            chip.setObjectName("severityChip")
            chip.setStyleSheet(f"color: {color}; font-size: 12px;")
            self._layout.addWidget(chip)

    def set_scan_status(
        self,
        security_scanned: bool,
        security_scanned_at: str | None,
        quality_scanned: bool,
        quality_scanned_at: str | None,
    ) -> None:
        if not security_scanned and not quality_scanned:
            self._status_label.setText(
                "Halo de riesgo: proyecto sin escanear todavía (correr security_scan_project / quality_scan_project) —"
            )
            return
        parts = []
        if security_scanned:
            parts.append(f"seguridad {(security_scanned_at or '')[:16]}")
        if quality_scanned:
            parts.append(f"calidad {(quality_scanned_at or '')[:16]}")
        self._status_label.setText("Halo de riesgo (" + ", ".join(parts) + ") —")


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
        # Path del archivo actualmente seleccionado en el panel de lectura --
        # separado de `_current_index` porque el polling (ver _on_poll_tick)
        # necesita re-consultarlo periódicamente sin depender de un click
        # nuevo del usuario.
        self._selected_file: str | None = None
        # Findings del archivo seleccionado, de la última vez que se
        # consultaron (por id) -- `None` significa "recién se seleccionó este
        # archivo, todavía no hay base para comparar" (no mostrar toast de
        # cascada al simplemente cambiar de archivo).
        self._last_findings_by_id: dict[str, dict] | None = None
        # True cuando el próximo `_on_graph_ready` tiene que hacer una carga
        # COMPLETA del grafo (nodos+edges, dispara el layout de fuerzas de
        # cero) -- solo corresponde la primera vez que se arma el grafo de un
        # índice nuevo (o tras un reindexado real). Los refrescos del polling
        # (ver _on_poll_tick) SOLO deben actualizar severidad in-place (ver
        # GraphView.update_severity) -- llamar a set_graph de nuevo ahí
        # reiniciaba el layout entero cada pocos segundos (bug real reportado
        # en vivo: el grafo "explotaba" reacomodándose durante el polling).
        self._graph_needs_full_reload = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addLayout(self._build_path_row())

        # NoMinWidthLabel, no QLabel a secas -- acá se muestran errores de
        # conexión al backend (ej. "HTTPConnectionPool... Max retries
        # exceeded"), que traen URLs y reprs de excepción larguísimos sin
        # espacios. Sin este fix, ese texto estira la ventana principal (ver
        # ui/widgets.py para el bug real, reportado en vivo más de una vez).
        self.status_label = NoMinWidthLabel("")
        self.status_label.setObjectName("codebaseStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.language_bar = LanguageBar()
        layout.addWidget(self.language_bar)

        self.risk_legend = RiskLegend()
        layout.addWidget(self.risk_legend)

        self.cascade_toast = CascadeToast()
        layout.addWidget(self.cascade_toast)

        splitter = QSplitter(Qt.Horizontal)
        self.graph_view = GraphView()
        self.graph_view.node_clicked.connect(self._on_node_clicked)
        splitter.addWidget(self.graph_view)

        right_panel = QSplitter(Qt.Vertical)
        self.findings_list = QListWidget()
        self.findings_list.setObjectName("findingsList")
        self.findings_list.itemDoubleClicked.connect(self._on_finding_double_clicked)
        right_panel.addWidget(self.findings_list)

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
        right_panel.setSizes([110, 90, 400])

        splitter.addWidget(right_panel)
        splitter.setSizes([460, 460])
        layout.addWidget(splitter, stretch=1)

        self._recent_thread = RecentProjectsThread(self._bridge)
        self._recent_thread.start()

        # Real-time-ish: mientras haya un proyecto cargado, re-consulta grafo
        # (halos) y archivo seleccionado (findings) cada _POLL_INTERVAL_MS --
        # así un fix aplicado desde el chat (code_apply_fix) se refleja acá
        # solo, sin que el usuario tenga que reindexar a mano.
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(_POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._on_poll_tick)
        self._poll_timer.start()

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
        # Índice nuevo (primera carga o reindexado real) -- el próximo grafo
        # que llegue tiene que ser una carga completa, la topología pudo
        # haber cambiado de verdad (archivos agregados/borrados).
        self._graph_needs_full_reload = True
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
        self.risk_legend.set_scan_status(
            security_scanned=bool(graph.get("security_scanned")),
            security_scanned_at=graph.get("security_scanned_at"),
            quality_scanned=bool(graph.get("quality_scanned")),
            quality_scanned_at=graph.get("quality_scanned_at"),
        )
        # `graph["nodes"]` (de /api/codebase/graph) trae la severidad por
        # path; `self._current_index["files"]` (de /api/codebase/index) trae
        # el resto de los datos que ya usaba el grafo (símbolos, tamaño). Se
        # arma un lookup en vez de mezclar las dos listas de nodos.
        severity_by_path = {n["path"]: n.get("severity") for n in graph.get("nodes", [])}
        if self._graph_needs_full_reload:
            self.graph_view.set_graph(
                self._current_index["files"],
                graph["edges"],
                id_key="path",
                color_fn=lambda f: color_for_language(f["language"]),
                label_fn=lambda f: f["path"].rsplit("/", 1)[-1],
                severity_color_fn=lambda f: color_for_severity(severity_by_path.get(f["path"])),
            )
            self._graph_needs_full_reload = False
        else:
            # Refresco de polling sobre un grafo ya cargado -- solo actualiza
            # el halo de los nodos que cambiaron de severidad, sin recrear el
            # dataset ni reiniciar el layout de fuerzas (ver
            # GraphView.update_severity para el porqué).
            self.graph_view.update_severity(
                {path: color_for_severity(sev) for path, sev in severity_by_path.items()}
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
        self.findings_list.clear()
        self.code_viewer.setPlainText("")
        self.code_viewer.setExtraSelections([])
        self._selected_file = None
        self._last_findings_by_id = None
        if self._current_index is None:
            return
        file_entry = next((f for f in self._current_index["files"] if f["path"] == path), None)
        if file_entry is None:
            return
        for sym in file_entry.get("symbols", []):
            icon = _SYMBOL_ICON.get(sym["kind"], "•")
            list_item = QListWidgetItem(f"{icon}  {sym['name']}   (línea {sym['line']})")
            self.symbol_list.addItem(list_item)

        self._selected_file = path
        self.code_viewer.setPlainText("Cargando...")
        self._file_thread = FileContentFetchThread(self._current_index["root"], path, self._bridge)
        self._file_thread.start()

    def _on_file_ready(self, data: dict) -> None:
        # Solo se pisa el contenido si cambió -- en un poll (ver
        # _on_poll_tick) que no trajo novedades, `setPlainText` con el mismo
        # texto igual resetea el scroll/cursor del usuario, molesto si está
        # leyendo el archivo mientras el polling sigue corriendo de fondo.
        if self.code_viewer.toPlainText() != data["content"]:
            self.code_viewer.setPlainText(data["content"])
        self._update_findings(data.get("findings", []))

    def _on_file_error(self, message: str) -> None:
        self.code_viewer.setPlainText(message)

    # ------------------------------------------------------------- hallazgos

    def _update_findings(self, findings: list[dict]) -> None:
        new_by_id = {f["id"]: f for f in findings}
        if self._last_findings_by_id is not None:
            resolved = [f for fid, f in self._last_findings_by_id.items() if fid not in new_by_id]
            if resolved:
                self.cascade_toast.show_message(_describe_resolved(resolved))
        self._last_findings_by_id = new_by_id
        self._render_findings_list(findings)
        self._apply_findings_highlights(findings)

    def _render_findings_list(self, findings: list[dict]) -> None:
        self.findings_list.clear()
        if not findings:
            return
        # Ya vienen ordenados por severidad descendente desde el backend
        # (`GET /api/codebase/file`, ver findings/severity_index.py).
        for f in findings:
            icon = _FINDING_SEVERITY_ICON.get(f["severity"], "•")
            label = _SEVERITY_LABEL.get(f["severity"], f["severity"])
            item = QListWidgetItem(f"{icon}  L{f['line']}  [{label}] {f['rule_id']}: {f['message']}")
            item.setData(Qt.UserRole, f["line"])
            self.findings_list.addItem(item)

    def _apply_findings_highlights(self, findings: list[dict]) -> None:
        """Resalta con fondo de color (mismo criterio que el halo del grafo)
        cada línea con hallazgo directamente en el visor de código -- antes
        el doble click solo hacía scroll hasta la línea, pero una vez ahí el
        código se veía plano, sin forma de distinguir a simple vista cuál era
        la línea problemática (reportado en vivo). Se aplica a TODOS los
        hallazgos del archivo abierto, no solo al que se clickeó, para que
        alcance con mirar el visor -- no hace falta volver a mirar la lista
        de arriba."""
        selections = []
        for f in findings:
            color = _highlight_color_for_severity(f["severity"])
            if color is None:
                continue
            start_line = f["line"]
            end_line = f.get("end_line") or start_line
            for line_no in range(start_line, end_line + 1):
                block = self.code_viewer.document().findBlockByLineNumber(max(0, line_no - 1))
                if not block.isValid():
                    continue
                fmt = QTextCharFormat()
                fmt.setBackground(color)
                fmt.setProperty(QTextFormat.FullWidthSelection, True)
                selection = QTextEdit.ExtraSelection()
                selection.format = fmt
                selection.cursor = QTextCursor(block)
                selections.append(selection)
        self.code_viewer.setExtraSelections(selections)

    def _on_finding_double_clicked(self, item: QListWidgetItem) -> None:
        # Doble click en un hallazgo salta el visor de código a esa línea --
        # "la línea exacta a corregir" que pidió el usuario, sin tener que
        # buscarla a mano en un archivo largo. El resaltado en sí ya está
        # aplicado a todas las líneas con hallazgo (ver
        # _apply_findings_highlights), así que acá solo hace falta mover el
        # cursor/scroll.
        line = item.data(Qt.UserRole)
        if line is None:
            return
        cursor = QTextCursor(self.code_viewer.document().findBlockByLineNumber(max(0, line - 1)))
        self.code_viewer.setTextCursor(cursor)
        self.code_viewer.ensureCursorVisible()

    # ------------------------------------------------------------- polling

    def _on_poll_tick(self) -> None:
        if self._current_index is None:
            return
        if self._graph_thread is None or not self._graph_thread.isRunning():
            self._graph_thread = GraphFetchThread(self._current_index["root"], self._bridge)
            self._graph_thread.start()
        if self._selected_file is not None and (self._file_thread is None or not self._file_thread.isRunning()):
            self._file_thread = FileContentFetchThread(self._current_index["root"], self._selected_file, self._bridge)
            self._file_thread.start()
