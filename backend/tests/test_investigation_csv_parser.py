"""Tests de app/investigation/csv_parser.py -- end-to-end real (git, log
firmado, almacén de artefactos, todo real, nada mockeado: el parser en sí es
determinístico, no llama al modelo). Prueba el flujo completo del paso 2 de
la spec: CSV -> nodos reales en el grafo, con trazabilidad real hasta el
artefacto."""

from __future__ import annotations

import pytest

from app.investigation import case_store, csv_parser, keys
from app.investigation.models import EdgeType, NodeType


@pytest.fixture()
def env(tmp_path):
    keys_dir = tmp_path / "keys"
    cases_dir = tmp_path / "cases"
    artifact_dir = tmp_path / "artifacts"
    keys.ensure_keypair(keys_dir)
    case_store.create_case(cases_dir, "caso-1", "Caso de prueba")
    return {"keys_dir": keys_dir, "cases_dir": cases_dir, "artifact_dir": artifact_dir}


CSV_CONTENT = (
    "nombre,usuario_telegram\n"
    "Juan Perez,@juanp\n"
    "Maria Lopez,@marial\n"
).encode("utf-8")


def test_ingest_csv_creates_one_node_per_row(env):
    created = csv_parser.ingest_csv(
        cases_dir=env["cases_dir"], keys_dir=env["keys_dir"], artifact_store_dir=env["artifact_dir"],
        case_id="caso-1", csv_bytes=CSV_CONTENT, original_filename="contactos.csv",
        node_type=NodeType.CUENTA, column_mapping={"usuario_telegram": "handle"},
        defaults={"plataforma": "telegram"}, ingested_by="damian",
    )

    assert len(created) == 2
    assert created[0].campos["handle"] == "@juanp"
    assert created[0].campos["plataforma"] == "telegram"
    assert created[1].campos["handle"] == "@marial"


def test_ingest_csv_persists_nodes_into_the_real_case(env):
    csv_parser.ingest_csv(
        cases_dir=env["cases_dir"], keys_dir=env["keys_dir"], artifact_store_dir=env["artifact_dir"],
        case_id="caso-1", csv_bytes=CSV_CONTENT, original_filename="contactos.csv",
        node_type=NodeType.CUENTA, column_mapping={"usuario_telegram": "handle"},
        defaults={"plataforma": "telegram"}, ingested_by="damian",
    )

    nodes = case_store.read_nodes(env["cases_dir"], "caso-1")
    cuentas = [n for n in nodes if n.tipo == NodeType.CUENTA]
    assert len(cuentas) == 2


def test_ingest_csv_creates_a_real_archivo_node_and_traces_rows_to_it(env):
    """Criterio de aceptación de la spec: todo nodo se puede rastrear hasta
    un artefacto con hash verificable."""
    csv_parser.ingest_csv(
        cases_dir=env["cases_dir"], keys_dir=env["keys_dir"], artifact_store_dir=env["artifact_dir"],
        case_id="caso-1", csv_bytes=CSV_CONTENT, original_filename="contactos.csv",
        node_type=NodeType.CUENTA, column_mapping={"usuario_telegram": "handle"},
        defaults={"plataforma": "telegram"}, ingested_by="damian",
    )

    nodes = case_store.read_nodes(env["cases_dir"], "caso-1")
    archivo_nodes = [n for n in nodes if n.tipo == NodeType.ARCHIVO]
    assert len(archivo_nodes) == 1
    archivo = archivo_nodes[0]
    assert archivo.campos["nombre"] == "contactos.csv"
    assert len(archivo.campos["sha256"]) == 64

    edges = case_store.read_edges(env["cases_dir"], "caso-1")
    aparece_en_edges = [e for e in edges if e.tipo == EdgeType.APARECE_EN]
    assert len(aparece_en_edges) == 2
    assert all(e.destino == archivo.id for e in aparece_en_edges)
    cuentas = [n for n in nodes if n.tipo == NodeType.CUENTA]
    assert {e.origen for e in aparece_en_edges} == {c.id for c in cuentas}


def test_ingest_csv_stores_the_real_artifact_bytes(env):
    from app.investigation import artifact_store

    csv_parser.ingest_csv(
        cases_dir=env["cases_dir"], keys_dir=env["keys_dir"], artifact_store_dir=env["artifact_dir"],
        case_id="caso-1", csv_bytes=CSV_CONTENT, original_filename="contactos.csv",
        node_type=NodeType.CUENTA, column_mapping={"usuario_telegram": "handle"},
        defaults={"plataforma": "telegram"}, ingested_by="damian",
    )

    import hashlib

    sha256 = hashlib.sha256(CSV_CONTENT).hexdigest()
    assert artifact_store.read_artifact_bytes(env["artifact_dir"], sha256) == CSV_CONTENT


def test_reingesting_the_same_unchanged_file_creates_no_duplicate_nodes(env):
    csv_parser.ingest_csv(
        cases_dir=env["cases_dir"], keys_dir=env["keys_dir"], artifact_store_dir=env["artifact_dir"],
        case_id="caso-1", csv_bytes=CSV_CONTENT, original_filename="contactos.csv",
        node_type=NodeType.CUENTA, column_mapping={"usuario_telegram": "handle"},
        defaults={"plataforma": "telegram"}, ingested_by="damian",
    )
    second = csv_parser.ingest_csv(
        cases_dir=env["cases_dir"], keys_dir=env["keys_dir"], artifact_store_dir=env["artifact_dir"],
        case_id="caso-1", csv_bytes=CSV_CONTENT, original_filename="contactos.csv",
        node_type=NodeType.CUENTA, column_mapping={"usuario_telegram": "handle"},
        defaults={"plataforma": "telegram"}, ingested_by="damian",
    )

    assert second == []  # nada nuevo -- el marker ya cubria todas las filas
    nodes = case_store.read_nodes(env["cases_dir"], "caso-1")
    cuentas = [n for n in nodes if n.tipo == NodeType.CUENTA]
    assert len(cuentas) == 2  # no se duplico nada


def test_reingesting_with_new_rows_appended_only_processes_the_new_ones(env):
    """El caso real que motiva el ingestion_marker (decision de Damian): el
    archivo se recarga con mensajes/filas nuevas agregadas al final."""
    csv_parser.ingest_csv(
        cases_dir=env["cases_dir"], keys_dir=env["keys_dir"], artifact_store_dir=env["artifact_dir"],
        case_id="caso-1", csv_bytes=CSV_CONTENT, original_filename="contactos.csv",
        node_type=NodeType.CUENTA, column_mapping={"usuario_telegram": "handle"},
        defaults={"plataforma": "telegram"}, ingested_by="damian",
    )

    extended_csv = CSV_CONTENT + b"Carlos Ruiz,@carlosr\n"
    second = csv_parser.ingest_csv(
        cases_dir=env["cases_dir"], keys_dir=env["keys_dir"], artifact_store_dir=env["artifact_dir"],
        case_id="caso-1", csv_bytes=extended_csv, original_filename="contactos.csv",
        node_type=NodeType.CUENTA, column_mapping={"usuario_telegram": "handle"},
        defaults={"plataforma": "telegram"}, ingested_by="damian",
    )

    # Distinto contenido -> distinto hash -> se trata como un artefacto
    # NUEVO (separado), asi que esta vez procesa las 3 filas del archivo
    # extendido -- el marker de reingesta incremental es POR HASH, no por
    # nombre de archivo (mismo criterio que el resto del store).
    assert len(second) == 3


def test_reingesting_the_same_hash_after_a_marker_was_advanced_processes_only_the_delta(env):
    """Simula el caso real de incremento real: mismo artefacto (mismo hash),
    el marker ya avanzo manualmente a mitad de archivo (ej. un parser mas
    especifico que csv_parser ya proceso las primeras filas), y una segunda
    llamada con el MISMO hash debe respetar ese marker."""
    from app.investigation import artifact_store

    record = artifact_store.store_artifact(env["artifact_dir"], CSV_CONTENT, "contactos.csv", ingested_by="damian")
    artifact_store.set_ingestion_marker(env["artifact_dir"], record.sha256, marker="1")

    created = csv_parser.ingest_csv(
        cases_dir=env["cases_dir"], keys_dir=env["keys_dir"], artifact_store_dir=env["artifact_dir"],
        case_id="caso-1", csv_bytes=CSV_CONTENT, original_filename="contactos.csv",
        node_type=NodeType.CUENTA, column_mapping={"usuario_telegram": "handle"},
        defaults={"plataforma": "telegram"}, ingested_by="damian",
    )

    assert len(created) == 1  # solo la fila 2 (Maria), la 1 (Juan) ya estaba marcada como procesada
    assert created[0].campos["handle"] == "@marial"


def test_ingest_csv_coerces_confianza_to_float(env):
    csv_with_confidence = b"nombre,confianza\nJuan,0.8\n"

    created = csv_parser.ingest_csv(
        cases_dir=env["cases_dir"], keys_dir=env["keys_dir"], artifact_store_dir=env["artifact_dir"],
        case_id="caso-1", csv_bytes=csv_with_confidence, original_filename="personas.csv",
        node_type=NodeType.PERSONA, column_mapping={"nombre": "etiqueta", "confianza": "confianza"},
        defaults={}, ingested_by="damian",
    )

    assert created[0].campos["confianza"] == 0.8
    assert isinstance(created[0].campos["confianza"], float)


def test_ingest_csv_wraps_a_single_value_into_a_list_for_list_fields(env):
    csv_with_alias = b"nombre,confianza,alias_conocido\nJuan,0.5,El Profe\n"

    created = csv_parser.ingest_csv(
        cases_dir=env["cases_dir"], keys_dir=env["keys_dir"], artifact_store_dir=env["artifact_dir"],
        case_id="caso-1", csv_bytes=csv_with_alias, original_filename="personas.csv",
        node_type=NodeType.PERSONA,
        column_mapping={"nombre": "etiqueta", "confianza": "confianza", "alias_conocido": "alias"},
        defaults={}, ingested_by="damian",
    )

    assert created[0].campos["alias"] == ["El Profe"]


# --- edge cases reales encontrados en testing adversarial (2026-08-13) ----------------

def test_ingest_csv_decodes_a_real_utf16_file(env):
    """Bug real: exports de Excel en Windows son comúnmente UTF-16 con BOM
    -- antes de este fix, `csv_bytes.decode("utf-8-sig")` tiraba un
    UnicodeDecodeError crudo sin intentar nada más."""
    utf16_bytes = "nombre,usuario_telegram\nJuan Perez,@juanp\n".encode("utf-16")

    created = csv_parser.ingest_csv(
        cases_dir=env["cases_dir"], keys_dir=env["keys_dir"], artifact_store_dir=env["artifact_dir"],
        case_id="caso-1", csv_bytes=utf16_bytes, original_filename="contactos_utf16.csv",
        node_type=NodeType.CUENTA, column_mapping={"usuario_telegram": "handle"},
        defaults={"plataforma": "telegram"}, ingested_by="damian",
    )

    assert len(created) == 1
    assert created[0].campos["handle"] == "@juanp"


def test_ingest_csv_decodes_a_real_cp1252_file(env):
    """Windows-1252 (Latin-1 extendido) -- otra codificación real y común en
    exports locales, con caracteres fuera del rango ASCII (ñ, tildes)."""
    cp1252_bytes = "nombre,usuario_telegram\nMuñoz Peña,@munoz\n".encode("cp1252")

    created = csv_parser.ingest_csv(
        cases_dir=env["cases_dir"], keys_dir=env["keys_dir"], artifact_store_dir=env["artifact_dir"],
        case_id="caso-1", csv_bytes=cp1252_bytes, original_filename="contactos_cp1252.csv",
        node_type=NodeType.CUENTA, column_mapping={"usuario_telegram": "handle"},
        defaults={"plataforma": "telegram"}, ingested_by="damian",
    )

    assert created[0].campos["handle"] == "@munoz"


def test_ingest_csv_rejects_a_column_mapping_that_references_a_nonexistent_column(env):
    """Bug real: un column_mapping con una columna que no existe en el CSV
    real dejaba pasar la ejecución hasta romper adentro de make_cuenta() con
    un TypeError críptico ("missing required keyword-only argument") en vez
    de un error claro y accionable en el punto donde realmente está el
    problema."""
    with pytest.raises(ValueError, match="no existen en el CSV real"):
        csv_parser.ingest_csv(
            cases_dir=env["cases_dir"], keys_dir=env["keys_dir"], artifact_store_dir=env["artifact_dir"],
            case_id="caso-1", csv_bytes=b"nombre\nJuan\n", original_filename="malo.csv",
            node_type=NodeType.CUENTA, column_mapping={"columna_inexistente": "handle"},
            defaults={"plataforma": "telegram"}, ingested_by="damian",
        )


def test_ingest_csv_handles_a_truly_empty_file(env):
    created = csv_parser.ingest_csv(
        cases_dir=env["cases_dir"], keys_dir=env["keys_dir"], artifact_store_dir=env["artifact_dir"],
        case_id="caso-1", csv_bytes=b"", original_filename="vacio.csv",
        node_type=NodeType.CUENTA, column_mapping={"usuario_telegram": "handle"},
        defaults={"plataforma": "telegram"}, ingested_by="damian",
    )

    assert created == []


def test_ingest_csv_handles_a_header_only_file_with_no_data_rows(env):
    created = csv_parser.ingest_csv(
        cases_dir=env["cases_dir"], keys_dir=env["keys_dir"], artifact_store_dir=env["artifact_dir"],
        case_id="caso-1", csv_bytes=b"nombre,usuario_telegram\n", original_filename="solo_header.csv",
        node_type=NodeType.CUENTA, column_mapping={"usuario_telegram": "handle"},
        defaults={"plataforma": "telegram"}, ingested_by="damian",
    )

    assert created == []
