"""Export de informe de caso a Markdown y PDF (spec sección 7, paso 8 --
último del orden de implementación): "resumen, grafo renderizado, timeline,
tabla de entidades con nivel de confianza, anexo de artefactos con sus
hashes, y apartado separado con todo lo generado por el modelo claramente
identificado."

Los dos formatos se generan desde la MISMA estructura intermedia
(`ReportData`) -- nunca se parsea el Markdown para armar el PDF ni al
revés, así los dos no pueden divergir en contenido, solo en presentación.
Todo dato del reporte sale de funciones ya existentes y ya testeadas del
módulo (graph_metrics, timeline) -- este archivo no recalcula nada, solo
junta y presenta.

"Grafo renderizado" es un requisito literal (una imagen, no una
descripción en texto) -- `render_graph_png` usa matplotlib con backend
"Agg" (no interactivo: este es código de servidor, nunca hay una pantalla
real detrás) + `networkx.spring_layout` para un PNG real embebido en los
dos formatos.

Apartado de generado-por-modelo: toda arista con `derivada_por=modelo`
(ver models.DerivadaPor) se agrupa en una sección aparte, nunca mezclada
con el resto -- mismo principio de todo el módulo (spec sección 5: "toda
salida del modelo se guarda etiquetada como tal"). Limitación real: el
`razon`/`texto_fuente` original de la propuesta que generó esa arista vive
en `proposals.jsonl`/`fusion_proposals.jsonl`, no en el Edge -- el reporte
muestra la arista en sí (tipo/origen/destino/confianza), no el
razonamiento completo del modelo que la propuso (para eso está el propio
archivo de propuestas, no este export)."""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # servidor sin pantalla -- nunca abrir una ventana real
import matplotlib.pyplot as plt
import networkx as nx
from fpdf import FPDF

from . import case_store, graph_metrics, timeline as timeline_module
from .models import DerivadaPor, Edge, Node, NodeType

_NODE_TYPE_COLORS: dict[NodeType, str] = {
    NodeType.PERSONA: "#4c72b0",
    NodeType.CUENTA: "#55a868",
    NodeType.DISPOSITIVO: "#c44e52",
    NodeType.HOST: "#8172b2",
    NodeType.ARCHIVO: "#937860",
    NodeType.TRANSACCION: "#ccb974",
    NodeType.EVENTO: "#64b5cd",
    NodeType.ORGANIZACION: "#da8bc3",
}


def _entity_label(node: Node) -> str:
    campos = node.campos
    return (
        campos.get("etiqueta") or campos.get("handle") or campos.get("nombre")
        or campos.get("ip_o_dominio") or campos.get("descripcion") or node.id
    )


@dataclass
class EntityRow:
    node_id: str
    tipo: str
    etiqueta: str
    confidence: float | None


@dataclass
class ArtifactRow:
    node_id: str
    nombre: str
    sha256: str
    tamano: int
    mime: str


@dataclass
class ModelGeneratedEdgeRow:
    edge_id: str
    tipo: str
    origen: str
    destino: str
    confianza: float


@dataclass
class ReportData:
    case_id: str
    titulo: str
    created_at: str
    generated_at: str
    node_count: int
    edge_count: int
    entities: list[EntityRow] = field(default_factory=list)
    artifacts: list[ArtifactRow] = field(default_factory=list)
    timeline_entries: list = field(default_factory=list)
    contradictions: list = field(default_factory=list)
    model_generated_edges: list[ModelGeneratedEdgeRow] = field(default_factory=list)
    graph_png: bytes | None = None


def render_graph_png(nodes: list[Node], edges: list[Edge]) -> bytes | None:
    g = graph_metrics.build_graph(nodes, edges)
    if g.number_of_nodes() == 0:
        return None  # nada que renderizar -- no se inventa una imagen vacía con sentido

    by_id = {n.id: n for n in nodes}
    colors = [_NODE_TYPE_COLORS.get(by_id[node_id].tipo, "#999999") for node_id in g.nodes]
    labels = {node_id: _entity_label(by_id[node_id]) for node_id in g.nodes}

    fig, ax = plt.subplots(figsize=(10, 7))
    layout = nx.spring_layout(g, seed=42)  # seed fija -- mismo grafo, mismo layout, reporte reproducible
    nx.draw_networkx_nodes(g, layout, node_color=colors, node_size=400, ax=ax)
    nx.draw_networkx_edges(g, layout, alpha=0.4, ax=ax)
    nx.draw_networkx_labels(g, layout, labels=labels, font_size=7, ax=ax)
    ax.set_axis_off()
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    return buf.getvalue()


def build_report_data(cases_dir: str | Path, keys_dir: str | Path, case_id: str) -> ReportData:
    case_dir = case_store.case_dir_for(cases_dir, case_id)
    if not case_dir.is_dir():
        raise case_store.CaseNotFoundError(f"El caso '{case_id}' no existe")

    import json
    case_info = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))

    all_nodes = case_store.read_nodes(cases_dir, case_id)
    all_edges = case_store.read_edges(cases_dir, case_id)
    nodes = [n for n in all_nodes if not n.retracted]
    edges = [e for e in all_edges if not e.retracted]

    confidence = graph_metrics.compute_confidence(nodes, edges)
    entities = [
        EntityRow(node_id=n.id, tipo=n.tipo.value, etiqueta=_entity_label(n), confidence=confidence.get(n.id))
        for n in nodes
    ]

    artifacts = [
        ArtifactRow(node_id=n.id, nombre=n.campos["nombre"], sha256=n.campos["sha256"], tamano=n.campos["tamano"], mime=n.campos["mime"])
        for n in nodes if n.tipo == NodeType.ARCHIVO
    ]

    timeline_entries = timeline_module.build_timeline(nodes, edges)
    contradictions = timeline_module.detect_contradictions(nodes, edges)

    model_generated_edges = [
        ModelGeneratedEdgeRow(edge_id=e.id, tipo=e.tipo.value, origen=e.origen, destino=e.destino, confianza=e.confianza)
        for e in edges if e.derivada_por == DerivadaPor.MODELO
    ]

    graph_png = render_graph_png(nodes, edges)

    return ReportData(
        case_id=case_id, titulo=case_info["titulo"], created_at=case_info["created_at"],
        generated_at=datetime.now(timezone.utc).isoformat(), node_count=len(nodes), edge_count=len(edges),
        entities=entities, artifacts=artifacts, timeline_entries=timeline_entries,
        contradictions=contradictions, model_generated_edges=model_generated_edges, graph_png=graph_png,
    )


def render_markdown(data: ReportData) -> str:
    lines = [
        f"# Informe del caso: {data.titulo}",
        "",
        f"- **Caso:** `{data.case_id}`",
        f"- **Creado:** {data.created_at}",
        f"- **Informe generado:** {data.generated_at}",
        f"- **Entidades vigentes:** {data.node_count}",
        f"- **Relaciones vigentes:** {data.edge_count}",
        "",
        "## Grafo",
        "",
    ]
    if data.graph_png:
        b64 = base64.b64encode(data.graph_png).decode("ascii")
        lines.append(f"![grafo del caso](data:image/png;base64,{b64})")
    else:
        lines.append("_Caso sin entidades todavía -- nada que renderizar._")
    lines.append("")

    lines.append("## Entidades")
    lines.append("")
    lines.append("| Tipo | Etiqueta | Confianza | id |")
    lines.append("|---|---|---|---|")
    for e in data.entities:
        conf = f"{e.confidence:.2f}" if e.confidence is not None else "_sin dato_"
        lines.append(f"| {e.tipo} | {e.etiqueta} | {conf} | `{e.node_id}` |")
    lines.append("")

    lines.append("## Timeline")
    lines.append("")
    if data.timeline_entries:
        lines.append("| Fecha/hora (UTC) | Tipo | Descripción |")
        lines.append("|---|---|---|")
        for entry in data.timeline_entries:
            lines.append(f"| {entry.timestamp_utc} | {entry.kind} | {entry.description} |")
    else:
        lines.append("_Sin eventos en la timeline todavía._")
    lines.append("")

    lines.append("### Contradicciones señaladas para revisión manual")
    lines.append("")
    if data.contradictions:
        for c in data.contradictions:
            lines.append(f"- **{c.entity_id}**: {c.reason}")
    else:
        lines.append("_Ninguna detectada._")
    lines.append("")

    lines.append("## Anexo de artefactos (hash verificable)")
    lines.append("")
    if data.artifacts:
        lines.append("| Nombre | SHA-256 | Tamaño (bytes) | MIME |")
        lines.append("|---|---|---|---|")
        for a in data.artifacts:
            lines.append(f"| {a.nombre} | `{a.sha256}` | {a.tamano} | {a.mime} |")
    else:
        lines.append("_Sin artefactos ingestados todavía._")
    lines.append("")

    lines.append("## Generado por el modelo (revisar aparte -- nunca dato verificado)")
    lines.append("")
    lines.append(
        "Toda relación de esta sección fue propuesta por el modelo y confirmada por un humano antes de "
        "entrar al grafo (nunca se escribe sola) -- se lista aparte para que quede claro qué es inferencia "
        "asistida y qué es hecho determinístico (parser/manual) en el resto de este informe."
    )
    lines.append("")
    if data.model_generated_edges:
        lines.append("| Tipo | Origen | Destino | Confianza |")
        lines.append("|---|---|---|---|")
        for m in data.model_generated_edges:
            lines.append(f"| {m.tipo} | `{m.origen}` | `{m.destino}` | {m.confianza:.2f} |")
    else:
        lines.append("_Ninguna relación generada por el modelo confirmada todavía._")
    lines.append("")

    return "\n".join(lines)


def _cell(pdf: FPDF, h: float, text: str) -> None:
    # Dos bugs reales encontrados probando esto con datos reales, en
    # cadena:
    # 1. fpdf2 en modo WORD (default) no puede envolver un token sin
    #    espacios más ancho que la línea -- un sha256 (64 caracteres) o un
    #    node_id ("persona-<32 hex>") tiran
    #    FPDFException("Not enough horizontal space to render a single
    #    character"). wrapmode="CHAR" permite cortar a mitad de palabra
    #    cuando hace falta, en vez de reventar.
    # 2. Pero el default de multi_cell (new_x=XPos.RIGHT) deja el cursor X
    #    en el borde DERECHO de la celda que acaba de dibujar, no de vuelta
    #    en el margen izquierdo -- pensado para seguir agregando celdas en
    #    la MISMA línea (ej. una fila de tabla), no para apilar bloques de
    #    texto completos uno debajo del otro (que es lo que hace este
    #    reporte, sección tras sección). Sin corregirlo, el siguiente
    #    multi_cell arranca casi sin ancho disponible (~0mm hasta el
    #    margen derecho) -- en modo WORD eso tira la MISMA excepción de
    #    arriba aunque el texto sea corto, y en modo CHAR (más tolerante)
    #    directamente CUELGA en un loop de line-breaking que nunca puede
    #    progresar con cero espacio real. new_x="LMARGIN" devuelve el
    #    cursor al margen izquierdo después de cada celda, que es lo que
    #    hace falta para apilar bloques verticalmente.
    pdf.multi_cell(0, h, text, new_x="LMARGIN", new_y="NEXT", wrapmode="CHAR")


def render_pdf(data: ReportData) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    _cell(pdf, 10, f"Informe del caso: {data.titulo}")
    pdf.set_font("Helvetica", "", 10)
    _cell(
        pdf, 6,
        f"Caso: {data.case_id}\nCreado: {data.created_at}\nInforme generado: {data.generated_at}\n"
        f"Entidades vigentes: {data.node_count} -- Relaciones vigentes: {data.edge_count}",
    )
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 13)
    _cell(pdf, 8, "Grafo")
    if data.graph_png:
        pdf.image(io.BytesIO(data.graph_png), w=180)
    else:
        pdf.set_font("Helvetica", "I", 10)
        _cell(pdf, 6, "Caso sin entidades todavía -- nada que renderizar.")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 13)
    _cell(pdf, 8, "Entidades")
    pdf.set_font("Helvetica", "", 9)
    for e in data.entities:
        conf = f"{e.confidence:.2f}" if e.confidence is not None else "sin dato"
        _cell(pdf, 5, f"[{e.tipo}] {e.etiqueta} -- confianza: {conf} -- id: {e.node_id}")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 13)
    _cell(pdf, 8, "Timeline")
    pdf.set_font("Helvetica", "", 9)
    if data.timeline_entries:
        for entry in data.timeline_entries:
            _cell(pdf, 5, f"{entry.timestamp_utc} [{entry.kind}] {entry.description}")
    else:
        _cell(pdf, 5, "Sin eventos en la timeline todavía.")
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 11)
    _cell(pdf, 6, "Contradicciones señaladas para revisión manual")
    pdf.set_font("Helvetica", "", 9)
    if data.contradictions:
        for c in data.contradictions:
            _cell(pdf, 5, f"{c.entity_id}: {c.reason}")
    else:
        _cell(pdf, 5, "Ninguna detectada.")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 13)
    _cell(pdf, 8, "Anexo de artefactos (hash verificable)")
    pdf.set_font("Helvetica", "", 9)
    if data.artifacts:
        for a in data.artifacts:
            _cell(pdf, 5, f"{a.nombre} -- sha256: {a.sha256} -- {a.tamano} bytes -- {a.mime}")
    else:
        _cell(pdf, 5, "Sin artefactos ingestados todavía.")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 13)
    _cell(pdf, 8, "Generado por el modelo (revisar aparte)")
    pdf.set_font("Helvetica", "", 9)
    if data.model_generated_edges:
        for m in data.model_generated_edges:
            _cell(pdf, 5, f"[{m.tipo}] {m.origen} -> {m.destino} -- confianza: {m.confianza:.2f}")
    else:
        _cell(pdf, 5, "Ninguna relación generada por el modelo confirmada todavía.")

    return bytes(pdf.output())


def export_report(cases_dir: str | Path, keys_dir: str | Path, case_id: str) -> dict:
    """Escribe ambos formatos a `{case_dir}/reports/{timestamp}.md|.pdf` --
    NO se commitea a git (mismo criterio que proposals.jsonl: un reporte es
    un derivado regenerable del estado real del caso en cualquier momento,
    no una fuente de verdad nueva)."""
    data = build_report_data(cases_dir, keys_dir, case_id)

    case_dir = case_store.case_dir_for(cases_dir, case_id)
    reports_dir = case_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    md_path = reports_dir / f"informe-{stamp}.md"
    pdf_path = reports_dir / f"informe-{stamp}.pdf"

    md_path.write_text(render_markdown(data), encoding="utf-8")
    pdf_path.write_bytes(render_pdf(data))

    return {"markdown_path": str(md_path), "pdf_path": str(pdf_path), "data": data}
