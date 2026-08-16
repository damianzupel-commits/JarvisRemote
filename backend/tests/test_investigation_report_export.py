"""Tests de app/investigation/report_export.py -- paso 8, último del orden
de implementación (spec sección 7: export a Markdown y PDF). Sin mocks:
grafo real, PNG real vía matplotlib, PDF real vía fpdf2 -- se valida
contra las firmas binarias reales de ambos formatos, no contra un stub."""

from __future__ import annotations

import pytest

from app.investigation import case_store, keys, report_export
from app.investigation.models import DerivadaPor, EdgeType, make_archivo, make_edge, make_evento, make_persona


@pytest.fixture()
def keys_dir(tmp_path):
    d = tmp_path / "keys"
    keys.ensure_keypair(d)
    return d


@pytest.fixture()
def cases_dir(tmp_path):
    d = tmp_path / "cases"
    case_store.create_case(d, "caso-1", "Caso de prueba")
    return d


def _populate_case(cases_dir, keys_dir):
    a = make_persona(etiqueta="Juan Perez", confianza=0.7)
    b = make_persona(etiqueta="Maria Lopez", confianza=0.6)
    archivo = make_archivo(nombre="chat.txt", sha256="a" * 64, tamano=100, mime="text/plain")
    evento = make_evento(timestamp_utc="2026-08-12T10:00:00+00:00", descripcion="Mensaje real", fuente="whatsapp_export")
    for n in (a, b, archivo, evento):
        case_store.add_node(cases_dir, keys_dir, "caso-1", n)

    edge_manual = make_edge(
        tipo=EdgeType.USA, origen=a.id, destino=archivo.id, artefacto_origen=archivo.id,
        confianza=0.9, derivada_por=DerivadaPor.PARSER,
    )
    edge_modelo = make_edge(
        tipo=EdgeType.MISMO_QUE, origen=a.id, destino=b.id, artefacto_origen="fusion_analisis",
        confianza=0.75, derivada_por=DerivadaPor.MODELO,
    )
    case_store.add_edge(cases_dir, keys_dir, "caso-1", edge_manual)
    case_store.add_edge(cases_dir, keys_dir, "caso-1", edge_modelo)
    return a, b, archivo, evento, edge_manual, edge_modelo


# --- render_graph_png --------------------------------------------------------------

def test_render_graph_png_returns_none_for_an_empty_graph():
    assert report_export.render_graph_png([], []) is None


def test_render_graph_png_returns_a_real_png(cases_dir, keys_dir):
    a, b, archivo, evento, *_ = _populate_case(cases_dir, keys_dir)
    nodes = case_store.read_nodes(cases_dir, "caso-1")
    edges = case_store.read_edges(cases_dir, "caso-1")

    png_bytes = report_export.render_graph_png(nodes, edges)

    assert png_bytes is not None
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")  # firma real de PNG
    assert len(png_bytes) > 1000  # no un PNG vacío/trivial


# --- build_report_data --------------------------------------------------------------

def test_build_report_data_raises_for_unknown_case(cases_dir, keys_dir):
    with pytest.raises(case_store.CaseNotFoundError):
        report_export.build_report_data(cases_dir, keys_dir, "no-existe")


def test_build_report_data_aggregates_entities_with_confidence(cases_dir, keys_dir):
    _populate_case(cases_dir, keys_dir)

    data = report_export.build_report_data(cases_dir, keys_dir, "caso-1")

    assert data.node_count == 4
    etiquetas = {e.etiqueta for e in data.entities}
    assert "Juan Perez" in etiquetas
    assert "Maria Lopez" in etiquetas


def test_build_report_data_lists_artifacts_with_real_hashes(cases_dir, keys_dir):
    _populate_case(cases_dir, keys_dir)

    data = report_export.build_report_data(cases_dir, keys_dir, "caso-1")

    assert len(data.artifacts) == 1
    assert data.artifacts[0].sha256 == "a" * 64
    assert data.artifacts[0].nombre == "chat.txt"


def test_build_report_data_includes_timeline_entries(cases_dir, keys_dir):
    _populate_case(cases_dir, keys_dir)

    data = report_export.build_report_data(cases_dir, keys_dir, "caso-1")

    assert any(e.description == "Mensaje real" for e in data.timeline_entries)


def test_build_report_data_only_lists_model_derived_edges_in_the_model_section(cases_dir, keys_dir):
    a, b, archivo, evento, edge_manual, edge_modelo = _populate_case(cases_dir, keys_dir)

    data = report_export.build_report_data(cases_dir, keys_dir, "caso-1")

    model_edge_ids = {m.edge_id for m in data.model_generated_edges}
    assert edge_modelo.id in model_edge_ids
    assert edge_manual.id not in model_edge_ids


def test_build_report_data_excludes_retracted_nodes(cases_dir, keys_dir):
    a, b, archivo, evento, *_ = _populate_case(cases_dir, keys_dir)
    case_store.retract_node(cases_dir, keys_dir, "caso-1", b.id, "duplicado")

    data = report_export.build_report_data(cases_dir, keys_dir, "caso-1")

    assert data.node_count == 3
    assert all(e.node_id != b.id for e in data.entities)


# --- render_markdown / render_pdf ----------------------------------------------------

def test_render_markdown_includes_all_required_sections(cases_dir, keys_dir):
    _populate_case(cases_dir, keys_dir)
    data = report_export.build_report_data(cases_dir, keys_dir, "caso-1")

    md = report_export.render_markdown(data)

    assert "# Informe del caso" in md
    assert "## Grafo" in md
    assert "data:image/png;base64," in md  # grafo renderizado, embebido de verdad
    assert "## Entidades" in md
    assert "Juan Perez" in md
    assert "## Timeline" in md
    assert "## Anexo de artefactos" in md
    assert "a" * 64 in md  # hash real del artefacto
    assert "Generado por el modelo" in md


def test_render_pdf_produces_a_real_valid_pdf(cases_dir, keys_dir):
    _populate_case(cases_dir, keys_dir)
    data = report_export.build_report_data(cases_dir, keys_dir, "caso-1")

    pdf_bytes = report_export.render_pdf(data)

    assert pdf_bytes.startswith(b"%PDF")
    assert b"%%EOF" in pdf_bytes[-1024:]
    assert len(pdf_bytes) > 2000  # incluye la imagen del grafo, no deberia ser trivial


def test_render_pdf_works_even_for_an_empty_case(cases_dir, keys_dir):
    """Un caso recien creado, sin nodos -- no debe explotar por no tener
    imagen de grafo para embeber."""
    data = report_export.build_report_data(cases_dir, keys_dir, "caso-1")

    pdf_bytes = report_export.render_pdf(data)

    assert pdf_bytes.startswith(b"%PDF")


# --- export_report -------------------------------------------------------------------

def test_export_report_writes_both_files_to_disk(cases_dir, keys_dir):
    _populate_case(cases_dir, keys_dir)

    result = report_export.export_report(cases_dir, keys_dir, "caso-1")

    from pathlib import Path

    md_path = Path(result["markdown_path"])
    pdf_path = Path(result["pdf_path"])
    assert md_path.is_file()
    assert pdf_path.is_file()
    assert md_path.read_text(encoding="utf-8").startswith("# Informe del caso")
    assert pdf_path.read_bytes().startswith(b"%PDF")


def test_export_report_does_not_commit_reports_to_git(cases_dir, keys_dir):
    import subprocess

    _populate_case(cases_dir, keys_dir)
    report_export.export_report(cases_dir, keys_dir, "caso-1")

    case_dir = case_store.case_dir_for(cases_dir, "caso-1")
    status = subprocess.run(["git", "-C", str(case_dir), "status", "--short"], capture_output=True, text=True)
    assert "reports/" in status.stdout  # aparecen como untracked, no committeados
