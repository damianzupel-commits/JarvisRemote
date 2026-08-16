"""Parsers de exports de mensajería (spec sección 2, paso 6 del orden de
implementación): WhatsApp (.txt) y Telegram (.json). Determinísticos --
igual que csv_parser.py, ningún LLM en el medio; la extracción de entidades
sobre texto libre (NER) es un paso APARTE y opcional (ver ner.py), este
parser solo estructura lo que el propio export ya trae con formato fijo.

Cada mensaje se convierte en un nodo `Evento` (así la timeline forense,
spec sección 4, tiene una entrada real por mensaje) + el remitente en un
nodo `Cuenta` (si el export trae un id de cuenta estable -- Telegram
`from_id`, la fuente más confiable) o `Persona` (si solo hay un nombre de
display, como en WhatsApp -- que puede repetirse entre contactos distintos,
así que NUNCA se trata como id de cuenta). Cada mensaje deja dos aristas
`aparece_en`: remitente -> Evento (quién participó) y Evento -> Archivo
(trazabilidad hacia el export de origen, mismo patrón que csv_parser.py).

IDs determinísticos dentro de un `scope_key` (no global): tanto el
remitente-por-nombre como el Evento de cada mensaje usan
`deterministic_node_id` con un `scope_key` como parte de la clave natural
-- así reingestar el MISMO conjunto de mensajes resuelve a los MISMOS
nodos (idempotente), pero NO fusiona automáticamente al mismo
remitente-por-nombre visto en OTRO scope (mismo criterio que el resto del
módulo: la fusión entre fuentes sigue siendo manual vía `mismo_que`,
decisión de Damian).

`scope_key` NO es lo mismo para los dos formatos, a propósito:
- **Telegram**: el propio export trae un id de chat estable (`data["id"]`)
  que NO cambia entre descargas sucesivas del mismo chat, aunque el
  archivo tenga bytes distintos (más mensajes) -- así que reingestar el
  mismo chat con mensajes nuevos agregados SÍ resuelve los mensajes viejos
  a los mismos nodos Evento/Persona, sin duplicar nada.
- **WhatsApp**: un export .txt plano NO trae ningún identificador de
  conversación, solo el contenido en sí -- así que `scope_key` cae al
  sha256 del propio archivo (ver `_store_export_artifact`). Limitación
  real y conocida (no un bug pendiente de arreglar en silencio): si Damian
  re-exporta la MISMA conversación de WhatsApp con mensajes nuevos, el
  archivo nuevo tiene un hash distinto, así que los mensajes viejos se
  vuelven a crear como nodos Evento nuevos (duplicados de contenido, cada
  uno correctamente trazable a SU PROPIO archivo de origen, pero
  duplicados en el grafo igual) -- WhatsApp no da ninguna señal real para
  hacer mejor que eso sin inventar una."""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import artifact_store, case_store, timeline
from .models import (
    DerivadaPor,
    EdgeType,
    Node,
    NodeType,
    deterministic_node_id,
    make_archivo,
    make_cuenta,
    make_edge,
    make_evento,
    make_persona,
)

_MAX_DESCRIPCION_CHARS = 2000

_WHATSAPP_IOS_RE = re.compile(
    r"^\[(?P<fecha>\d{1,2}/\d{1,2}/\d{2,4}),\s*(?P<hora>\d{1,2}:\d{2}(?::\d{2})?)\]\s*"
    r"(?P<sender>[^:]+):\s(?P<texto>.*)$"
)
_WHATSAPP_ANDROID_RE = re.compile(
    r"^(?P<fecha>\d{1,2}/\d{1,2}/\d{2,4}),\s*(?P<hora>\d{1,2}:\d{2}(?::\d{2})?)\s*[-–]\s*"
    r"(?P<sender>[^:]+):\s(?P<texto>.*)$"
)


def _parse_whatsapp_messages(text: str) -> list[dict]:
    """Líneas que no matchean ningún formato conocido (mensajes del sistema
    tipo "Los mensajes están cifrados...", o la continuación de un mensaje
    con salto de línea real) se anexan al mensaje anterior en vez de
    perderse o generar un mensaje fantasma sin remitente."""
    messages: list[dict] = []
    for line in text.splitlines():
        match = _WHATSAPP_IOS_RE.match(line) or _WHATSAPP_ANDROID_RE.match(line)
        if match:
            messages.append({
                "raw_timestamp": f"{match['fecha']} {match['hora']}",
                "sender": match["sender"].strip(),
                "sender_id": None,
                "texto": match["texto"],
            })
        elif messages:
            messages[-1]["texto"] += "\n" + line
    return messages


def _flatten_telegram_text(text) -> str:
    if isinstance(text, str):
        return text
    if isinstance(text, list):
        return "".join(part if isinstance(part, str) else str(part.get("text", "")) for part in text)
    return ""


def _parse_telegram_messages(data: dict) -> list[dict]:
    messages: list[dict] = []
    for msg in data.get("messages") or []:
        if not isinstance(msg, dict) or msg.get("type") != "message":
            continue  # mensajes de servicio (cambios de nombre de grupo, etc.) o entradas malformadas -- no son un mensaje real
        sender = msg.get("from") or msg.get("actor")
        if not sender:
            continue
        messages.append({
            "raw_timestamp": msg.get("date"),
            "sender": sender,
            "sender_id": msg.get("from_id") or msg.get("actor_id"),
            "texto": _flatten_telegram_text(msg.get("text")),
        })
    return messages


def _resolve_sender_node(scope_key: str, plataforma: str, sender: str, sender_id: str | None) -> Node:
    if sender_id:
        return make_cuenta(plataforma=plataforma, handle=str(sender_id))
    persona_id = deterministic_node_id(NodeType.PERSONA, f"{scope_key}:{plataforma}:{sender}")
    return make_persona(etiqueta=sender, confianza=0.5, node_id=persona_id)


def _ingest_messages(
    *, cases_dir: str | Path, keys_dir: str | Path, case_id: str, archivo_node: Node,
    messages: list[dict], plataforma: str, scope_key: str,
) -> list[Node]:
    created: list[Node] = []
    seen_sender_ids: set[str] = set()

    # `batch`: un solo commit git al final en vez de uno por mensaje -- ver
    # docstring de case_store.batch, bug real de performance encontrado
    # 2026-08-13.
    with case_store.batch(cases_dir, keys_dir, case_id, f"ingest_{plataforma}: {len(messages)} mensajes"):
        for msg in messages:
            try:
                normalized = timeline.normalize_timestamp(msg["raw_timestamp"])
            except (ValueError, TypeError, OverflowError):
                continue  # timestamp no parseable -- se descarta ESE mensaje, no el archivo entero

            sender_node = _resolve_sender_node(scope_key, plataforma, msg["sender"], msg.get("sender_id"))
            sender_node = case_store.add_node(cases_dir, keys_dir, case_id, sender_node)
            if sender_node.id not in seen_sender_ids:
                seen_sender_ids.add(sender_node.id)
                created.append(sender_node)

            evento_id = deterministic_node_id(
                NodeType.EVENTO, f"{scope_key}:{normalized.utc}:{msg['sender']}:{msg['texto'][:80]}"
            )
            evento = make_evento(
                timestamp_utc=normalized.utc, descripcion=msg["texto"][:_MAX_DESCRIPCION_CHARS],
                fuente=f"{plataforma}_export", node_id=evento_id,
            )
            evento = case_store.add_node(cases_dir, keys_dir, case_id, evento)
            created.append(evento)

            case_store.add_edge(cases_dir, keys_dir, case_id, make_edge(
                tipo=EdgeType.APARECE_EN, origen=sender_node.id, destino=evento.id,
                artefacto_origen=archivo_node.id, confianza=1.0, derivada_por=DerivadaPor.PARSER,
                timestamp=normalized.utc,
            ))
            case_store.add_edge(cases_dir, keys_dir, case_id, make_edge(
                tipo=EdgeType.APARECE_EN, origen=evento.id, destino=archivo_node.id,
                artefacto_origen=archivo_node.id, confianza=1.0, derivada_por=DerivadaPor.PARSER,
                timestamp=normalized.utc,
            ))
    return created


def _store_export_artifact(artifact_store_dir: str | Path, data: bytes, original_filename: str, mime: str, ingested_by: str):
    record = artifact_store.store_artifact(artifact_store_dir, data, original_filename, ingested_by)
    return make_archivo(nombre=original_filename, sha256=record.sha256, tamano=record.size, mime=record.mime or mime), record


def ingest_whatsapp_export(
    *, cases_dir: str | Path, keys_dir: str | Path, artifact_store_dir: str | Path, case_id: str,
    txt_bytes: bytes, original_filename: str, ingested_by: str,
) -> list[Node]:
    archivo_node, record = _store_export_artifact(artifact_store_dir, txt_bytes, original_filename, "text/plain", ingested_by)
    archivo_node = case_store.add_node(cases_dir, keys_dir, case_id, archivo_node)

    messages = _parse_whatsapp_messages(txt_bytes.decode("utf-8-sig", errors="replace"))
    already_processed = int(record.ingestion_marker) if record.ingestion_marker else 0
    new_messages = messages[already_processed:]

    created = _ingest_messages(
        cases_dir=cases_dir, keys_dir=keys_dir, case_id=case_id, archivo_node=archivo_node,
        messages=new_messages, plataforma="whatsapp", scope_key=archivo_node.campos["sha256"],
    )
    artifact_store.set_ingestion_marker(artifact_store_dir, record.sha256, marker=str(len(messages)))
    return created


def ingest_telegram_export(
    *, cases_dir: str | Path, keys_dir: str | Path, artifact_store_dir: str | Path, case_id: str,
    json_bytes: bytes, original_filename: str, ingested_by: str,
) -> list[Node]:
    archivo_node, record = _store_export_artifact(artifact_store_dir, json_bytes, original_filename, "application/json", ingested_by)
    archivo_node = case_store.add_node(cases_dir, keys_dir, case_id, archivo_node)

    try:
        data = json.loads(json_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"El export de Telegram no es JSON válido: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(
            f"El export de Telegram debería ser un objeto JSON (con 'messages' adentro), "
            f"no un {type(data).__name__} de nivel superior."
        )
    messages = _parse_telegram_messages(data)
    already_processed = int(record.ingestion_marker) if record.ingestion_marker else 0
    new_messages = messages[already_processed:]

    # id de chat de Telegram (estable entre descargas sucesivas del MISMO
    # chat, aunque el archivo tenga bytes distintos) -- ver docstring del
    # módulo. Si por lo que sea no viene (export raro/incompleto), cae al
    # hash del archivo como red de seguridad, mismo criterio que WhatsApp.
    chat_id = data.get("id")
    scope_key = str(chat_id) if chat_id is not None else archivo_node.campos["sha256"]

    created = _ingest_messages(
        cases_dir=cases_dir, keys_dir=keys_dir, case_id=case_id, archivo_node=archivo_node,
        messages=new_messages, plataforma="telegram", scope_key=scope_key,
    )
    artifact_store.set_ingestion_marker(artifact_store_dir, record.sha256, marker=str(len(messages)))
    return created
