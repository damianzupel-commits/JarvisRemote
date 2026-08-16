"""Tests de app/investigation/chat_parser.py (paso 6, exports de
mensajería). Datos 100% sintéticos/inventados (nunca material real de
nadie, mismo criterio que el resto del módulo) -- casos reales de git/log/
case_store, sin mocks."""

from __future__ import annotations

import json

import pytest

from app.investigation import case_store, chat_parser, keys
from app.investigation.models import NodeType


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


@pytest.fixture()
def artifact_store_dir(tmp_path):
    return tmp_path / "artifacts"


# --- WhatsApp -------------------------------------------------------------------

_WHATSAPP_ANDROID_EXPORT = (
    "12/08/2026, 14:30 - Juan Perez: Hola como estas\n"
    "12/08/2026, 14:31 - Maria Lopez: Bien y vos?\n"
    "12/08/2026, 14:32 - Juan Perez: Todo bien\n"
    "gracias por preguntar\n"  # continuación multilinea del mensaje anterior
)

_WHATSAPP_IOS_EXPORT = (
    "[12/08/2026, 14:30:00] Juan Perez: Hola\n"
    "[12/08/2026, 14:31:00] Maria Lopez: Hola Juan\n"
)


def test_ingest_whatsapp_parses_android_format_and_creates_real_nodes(cases_dir, keys_dir, artifact_store_dir):
    created = chat_parser.ingest_whatsapp_export(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        txt_bytes=_WHATSAPP_ANDROID_EXPORT.encode("utf-8"), original_filename="chat.txt", ingested_by="damian",
    )

    personas = [n for n in created if n.tipo == NodeType.PERSONA]
    eventos = [n for n in created if n.tipo == NodeType.EVENTO]
    assert {p.campos["etiqueta"] for p in personas} == {"Juan Perez", "Maria Lopez"}
    assert len(eventos) == 3  # 3 mensajes reales (el 4to renglón es continuación del 3ro)
    assert any("Todo bien\ngracias por preguntar" in e.campos["descripcion"] for e in eventos)


def test_ingest_whatsapp_parses_ios_format(cases_dir, keys_dir, artifact_store_dir):
    created = chat_parser.ingest_whatsapp_export(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        txt_bytes=_WHATSAPP_IOS_EXPORT.encode("utf-8"), original_filename="chat_ios.txt", ingested_by="damian",
    )

    eventos = [n for n in created if n.tipo == NodeType.EVENTO]
    assert len(eventos) == 2
    assert eventos[0].campos["timestamp_utc"].startswith("2026-08-12T14:30:00")


def test_same_sender_name_resolves_to_the_same_persona_node_within_one_export(cases_dir, keys_dir, artifact_store_dir):
    chat_parser.ingest_whatsapp_export(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        txt_bytes=_WHATSAPP_ANDROID_EXPORT.encode("utf-8"), original_filename="chat.txt", ingested_by="damian",
    )

    nodes = case_store.read_nodes(cases_dir, "caso-1")
    juan_nodes = [n for n in nodes if n.tipo == NodeType.PERSONA and n.campos["etiqueta"] == "Juan Perez"]
    assert len(juan_nodes) == 1  # Juan aparece en 2 mensajes -- un solo nodo Persona, no dos


def test_reingesting_the_exact_same_whatsapp_bytes_processes_no_new_messages(cases_dir, keys_dir, artifact_store_dir):
    """Mismo hash -> mismo marker -- el caso simple de re-subir el archivo
    sin cambios (ver test_reingesting_the_same_unchanged_file_creates_no_duplicate_nodes
    en test_investigation_csv_parser.py, mismo criterio)."""
    chat_parser.ingest_whatsapp_export(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        txt_bytes=_WHATSAPP_ANDROID_EXPORT.encode("utf-8"), original_filename="chat.txt", ingested_by="damian",
    )

    second = chat_parser.ingest_whatsapp_export(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        txt_bytes=_WHATSAPP_ANDROID_EXPORT.encode("utf-8"), original_filename="chat.txt", ingested_by="damian",
    )

    assert second == []
    all_eventos = [n for n in case_store.read_nodes(cases_dir, "caso-1") if n.tipo == NodeType.EVENTO]
    assert len(all_eventos) == 3  # nada duplicado


def test_a_whatsapp_export_with_appended_messages_is_a_different_hash_and_reprocesses_from_scratch(cases_dir, keys_dir, artifact_store_dir):
    """Límite real y documentado (ver docstring de chat_parser.py): un export
    .txt de WhatsApp no trae ningún id de conversación estable, así que un
    archivo con mensajes nuevos agregados es simplemente un artefacto
    DISTINTO (hash distinto) -- se reprocesa entero, duplicando en el grafo
    los mensajes que ya estaban en la ingesta anterior (cada uno trazable a
    SU propio archivo de origen, pero duplicado igual). Distinto de Telegram,
    que sí puede evitar esto -- ver test_reingesting_a_telegram_chat_with_new_messages_only_creates_the_new_ones."""
    chat_parser.ingest_whatsapp_export(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        txt_bytes=_WHATSAPP_ANDROID_EXPORT.encode("utf-8"), original_filename="chat.txt", ingested_by="damian",
    )
    extended_export = _WHATSAPP_ANDROID_EXPORT + "12/08/2026, 15:00 - Juan Perez: Un mensaje nuevo\n"

    created_second_pass = chat_parser.ingest_whatsapp_export(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        txt_bytes=extended_export.encode("utf-8"), original_filename="chat.txt", ingested_by="damian",
    )

    eventos_segunda_pasada = [n for n in created_second_pass if n.tipo == NodeType.EVENTO]
    assert len(eventos_segunda_pasada) == 4  # las 4 del archivo nuevo, no solo el delta real

    all_eventos = [n for n in case_store.read_nodes(cases_dir, "caso-1") if n.tipo == NodeType.EVENTO]
    assert len(all_eventos) == 7  # 3 originales + 4 de la segunda pasada -- limitación real, no un bug


def test_reingesting_a_telegram_chat_with_new_messages_only_creates_the_new_ones(cases_dir, keys_dir, artifact_store_dir):
    """A diferencia de WhatsApp, Telegram SÍ trae un id de chat estable
    (`data["id"]`) que no cambia entre descargas -- así que acá sí se logra
    la deduplicación real entre archivos de hash distinto."""
    first_export = _telegram_export([
        {"id": 1, "type": "message", "date": "2026-08-12T14:30:00", "from": "Juan Perez", "from_id": "user1", "text": "Hola"},
    ])
    chat_parser.ingest_telegram_export(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        json_bytes=first_export, original_filename="telegram.json", ingested_by="damian",
    )
    second_export = _telegram_export([
        {"id": 1, "type": "message", "date": "2026-08-12T14:30:00", "from": "Juan Perez", "from_id": "user1", "text": "Hola"},
        {"id": 2, "type": "message", "date": "2026-08-12T14:35:00", "from": "Juan Perez", "from_id": "user1", "text": "Mensaje nuevo"},
    ])

    created_second_pass = chat_parser.ingest_telegram_export(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        json_bytes=second_export, original_filename="telegram2.json", ingested_by="damian",
    )

    eventos_segunda_pasada = [n for n in created_second_pass if n.tipo == NodeType.EVENTO]
    assert len(eventos_segunda_pasada) == 2  # el marker no sirve (archivo distinto), pero el scope por chat_id sí

    all_eventos = [n for n in case_store.read_nodes(cases_dir, "caso-1") if n.tipo == NodeType.EVENTO]
    assert len(all_eventos) == 2  # el mensaje 1 resolvió al MISMO nodo -- sin duplicar


def test_whatsapp_traceability_edges_point_to_the_archivo_node(cases_dir, keys_dir, artifact_store_dir):
    chat_parser.ingest_whatsapp_export(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        txt_bytes=_WHATSAPP_IOS_EXPORT.encode("utf-8"), original_filename="chat.txt", ingested_by="damian",
    )

    nodes = case_store.read_nodes(cases_dir, "caso-1")
    archivo = next(n for n in nodes if n.tipo == NodeType.ARCHIVO)
    eventos = [n for n in nodes if n.tipo == NodeType.EVENTO]
    edges = case_store.read_edges(cases_dir, "caso-1")

    for evento in eventos:
        assert any(e.origen == evento.id and e.destino == archivo.id for e in edges)


# --- Telegram -------------------------------------------------------------------

def _telegram_export(messages: list[dict]) -> bytes:
    return json.dumps({"name": "Chat de prueba", "type": "personal_chat", "id": 1, "messages": messages}).encode("utf-8")


def test_ingest_telegram_prefers_cuenta_node_when_from_id_is_present(cases_dir, keys_dir, artifact_store_dir):
    export = _telegram_export([
        {"id": 1, "type": "message", "date": "2026-08-12T14:30:00", "from": "Juan Perez", "from_id": "user123456789", "text": "Hola"},
    ])

    created = chat_parser.ingest_telegram_export(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        json_bytes=export, original_filename="telegram.json", ingested_by="damian",
    )

    cuentas = [n for n in created if n.tipo == NodeType.CUENTA]
    assert len(cuentas) == 1
    assert cuentas[0].campos["plataforma"] == "telegram"
    assert cuentas[0].campos["handle"] == "user123456789"


def test_ingest_telegram_skips_service_messages(cases_dir, keys_dir, artifact_store_dir):
    export = _telegram_export([
        {"id": 1, "type": "service", "date": "2026-08-12T14:30:00", "actor": "Juan Perez", "action": "create_group"},
        {"id": 2, "type": "message", "date": "2026-08-12T14:31:00", "from": "Juan Perez", "from_id": "user1", "text": "Hola"},
    ])

    created = chat_parser.ingest_telegram_export(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        json_bytes=export, original_filename="telegram.json", ingested_by="damian",
    )

    eventos = [n for n in created if n.tipo == NodeType.EVENTO]
    assert len(eventos) == 1


def test_ingest_telegram_flattens_structured_text_entities(cases_dir, keys_dir, artifact_store_dir):
    """Telegram a veces exporta "text" como una lista de fragmentos (texto
    plano + entidades como menciones/links), no un string simple."""
    export = _telegram_export([
        {"id": 1, "type": "message", "date": "2026-08-12T14:30:00", "from": "Juan Perez", "from_id": "user1",
         "text": ["Hola ", {"type": "mention", "text": "@maria"}, ", como estas"]},
    ])

    created = chat_parser.ingest_telegram_export(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        json_bytes=export, original_filename="telegram.json", ingested_by="damian",
    )

    evento = next(n for n in created if n.tipo == NodeType.EVENTO)
    assert evento.campos["descripcion"] == "Hola @maria, como estas"


def test_telegram_without_from_id_falls_back_to_persona(cases_dir, keys_dir, artifact_store_dir):
    export = _telegram_export([
        {"id": 1, "type": "message", "date": "2026-08-12T14:30:00", "from": "Juan Perez", "text": "Hola"},
    ])

    created = chat_parser.ingest_telegram_export(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        json_bytes=export, original_filename="telegram.json", ingested_by="damian",
    )

    assert any(n.tipo == NodeType.PERSONA and n.campos["etiqueta"] == "Juan Perez" for n in created)


# --- timeline real ----------------------------------------------------------------

def test_ingested_messages_produce_a_real_chronological_timeline(cases_dir, keys_dir, artifact_store_dir):
    from app.investigation import timeline as timeline_module

    chat_parser.ingest_whatsapp_export(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        txt_bytes=_WHATSAPP_ANDROID_EXPORT.encode("utf-8"), original_filename="chat.txt", ingested_by="damian",
    )

    nodes = case_store.read_nodes(cases_dir, "caso-1")
    edges = case_store.read_edges(cases_dir, "caso-1")
    entries = timeline_module.build_timeline(nodes, edges)

    evento_entries = [e for e in entries if e.kind == "evento"]
    assert len(evento_entries) == 3
    assert [e.timestamp_utc for e in evento_entries] == sorted(e.timestamp_utc for e in evento_entries)


# --- edge cases reales encontrados en testing adversarial (2026-08-13) ----------------

def test_ingest_whatsapp_handles_a_truly_empty_file(cases_dir, keys_dir, artifact_store_dir):
    created = chat_parser.ingest_whatsapp_export(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        txt_bytes=b"", original_filename="vacio.txt", ingested_by="damian",
    )
    assert created == []


def test_ingest_whatsapp_handles_a_file_with_only_unmatched_lines(cases_dir, keys_dir, artifact_store_dir):
    """Ninguna línea matchea nunca ningún formato conocido (nada de mensajes
    reales todavía) -- no debería haber nada a lo que "anexar" el texto."""
    created = chat_parser.ingest_whatsapp_export(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        txt_bytes="Los mensajes estan cifrados de extremo a extremo.\nOtra linea huerfana.".encode(),
        original_filename="huerfano.txt", ingested_by="damian",
    )
    assert created == []


def test_ingest_telegram_rejects_malformed_json_with_a_clear_error(cases_dir, keys_dir, artifact_store_dir):
    """Bug real: antes de este fix, un export de Telegram con JSON roto
    dejaba pasar un json.JSONDecodeError crudo sin contexto de qué archivo
    lo causó."""
    with pytest.raises(ValueError, match="no es JSON válido"):
        chat_parser.ingest_telegram_export(
            cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
            json_bytes=b'{"messages": [ESTO NO ES JSON VALIDO', original_filename="roto.json", ingested_by="damian",
        )


def test_ingest_telegram_rejects_a_non_object_top_level_json(cases_dir, keys_dir, artifact_store_dir):
    """Bug real: un JSON top-level que es una lista (en vez de un objeto)
    tiraba un AttributeError crudo ('list' object has no attribute 'get')."""
    with pytest.raises(ValueError, match="objeto JSON"):
        chat_parser.ingest_telegram_export(
            cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
            json_bytes=b"[1, 2, 3]", original_filename="lista.json", ingested_by="damian",
        )


def test_ingest_telegram_handles_an_explicit_null_messages_field(cases_dir, keys_dir, artifact_store_dir):
    """Bug real: `data.get("messages", [])` NO usa el default cuando la key
    existe con valor null explícito -- tiraba un TypeError crudo
    ('NoneType' object is not iterable) en vez de tratarlo como 0 mensajes."""
    created = chat_parser.ingest_telegram_export(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        json_bytes=b'{"id": 124, "messages": null}', original_filename="messagesnull.json", ingested_by="damian",
    )
    assert created == []


def test_ingest_telegram_skips_non_dict_entries_in_messages(cases_dir, keys_dir, artifact_store_dir):
    """Bug real: un elemento de `messages` que no es un objeto (ej. un
    string suelto, export corrupto) tiraba un AttributeError crudo -- ahora
    se descarta esa entrada puntual, igual que un mensaje de servicio."""
    created = chat_parser.ingest_telegram_export(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        json_bytes=b'{"id": 126, "messages": ["esto no es un mensaje real"]}',
        original_filename="raro.json", ingested_by="damian",
    )
    assert created == []
