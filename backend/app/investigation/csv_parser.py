"""Parser CSV genérico, end-to-end hasta el grafo (spec paso 2 de
implementación). Determinístico -- el modelo ya hizo su parte (proponer un
mapeo, ver column_mapping.py) en un paso ANTERIOR y separado; esto solo
aplica un mapeo YA CONFIRMADO fila por fila, sin ningún LLM en el medio.

Trazabilidad (criterio de aceptación de la spec: "todo nodo del grafo se
puede rastrear hasta un artefacto con hash verificable, en un clic"): cada
fila nueva genera, además del nodo de la entidad, una arista `aparece_en`
real hacia un nodo `Archivo` que representa el propio CSV -- ese es el
mecanismo que la spec ya define para esto (sección 1, tipos de arista), no
un campo nuevo inventado. El nodo Archivo tiene id determinístico por su
sha256 (ver models.make_archivo), así que reingestar el mismo CSV reusa el
MISMO nodo Archivo en vez de duplicarlo (case_store.add_node es idempotente
por id).

Reingesta incremental (decisión de Damian, ambigüedad #2): usa el
`ingestion_marker` del artefacto (ver artifact_store.py) para saber cuántas
filas ya se procesaron la vez anterior -- un número de fila simple alcanza
para CSV (a diferencia de un chat, donde hace falta un id/timestamp de
mensaje: acá el archivo se reemplaza entero en cada carga y las filas viejas
nunca cambian de posición, invariante razonable para un export CSV)."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Callable

from . import artifact_store, case_store
from .models import DerivadaPor, EdgeType, Node, NodeType, make_edge


_LIST_FIELDS = {"alias", "identificadores"}
_FLOAT_FIELDS = {"confianza", "monto", "tamano"}
_UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")


def _decode_csv_bytes(csv_bytes: bytes) -> str:
    """CSVs reales de un caso forense NO siempre vienen en UTF-8 -- exports
    de Excel en Windows son comúnmente UTF-16 (con BOM) o Windows-1252.
    Bug real encontrado en testing adversarial (2026-08-13): un CSV UTF-16
    tiraba un UnicodeDecodeError crudo sin decodificar nada, en vez de
    intentar codificaciones alternativas reales antes de rendirse.

    UTF-16 solo se intenta si hay un BOM real al principio del archivo (así
    es como Excel efectivamente lo marca) -- un intento "a ciegas" sin BOM
    es peligroso, porque `bytes.decode("utf-16")` sin BOM asume
    endianness nativa y casi siempre "tiene éxito" con basura en vez de
    fallar (bug real encontrado escribiendo el test de cp1252: texto
    Windows-1252 sin BOM se decodificaba silenciosamente como UTF-16
    corrupto, en vez de caer al fallback correcto)."""
    if csv_bytes.startswith(_UTF16_BOMS):
        try:
            return csv_bytes.decode("utf-16")
        except UnicodeDecodeError:
            pass
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return csv_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(
        "No pude decodificar el CSV con ninguna codificación conocida "
        "(probé UTF-16 con BOM, UTF-8 y Windows-1252) -- revisá la codificación del archivo original."
    )


def _make_functions() -> dict[NodeType, Callable[..., Node]]:
    # Import diferido (no al nivel de módulo) para no depender del orden de
    # definición de las funciones make_* dentro de models.py.
    from . import models

    return {
        NodeType.PERSONA: models.make_persona,
        NodeType.CUENTA: models.make_cuenta,
        NodeType.DISPOSITIVO: models.make_dispositivo,
        NodeType.HOST: models.make_host,
        NodeType.ARCHIVO: models.make_archivo,
        NodeType.TRANSACCION: models.make_transaccion,
        NodeType.EVENTO: models.make_evento,
        NodeType.ORGANIZACION: models.make_organizacion,
    }


def _coerce_value(field: str, value: str | None):
    if value is None or value == "":
        return [] if field in _LIST_FIELDS else None
    if field in _LIST_FIELDS:
        return [value]
    if field in _FLOAT_FIELDS:
        return float(value)
    return value


def make_node_from_row(node_type: NodeType, row: dict[str, str], column_mapping: dict[str, str], defaults: dict) -> Node:
    campos: dict = dict(defaults)
    for column, field in column_mapping.items():
        if column in row:
            campos[field] = _coerce_value(field, row[column])
    fn = _make_functions()[node_type]
    return fn(**campos)


def ingest_csv(
    *,
    cases_dir: str | Path,
    keys_dir: str | Path,
    artifact_store_dir: str | Path,
    case_id: str,
    csv_bytes: bytes,
    original_filename: str,
    node_type: NodeType,
    column_mapping: dict[str, str],
    defaults: dict | None = None,
    ingested_by: str,
) -> list[Node]:
    """Ingesta real, end-to-end: guarda el artefacto (hash + store de solo
    lectura), crea/reusa el nodo Archivo correspondiente, parsea el CSV con
    el mapeo YA CONFIRMADO, crea un Node por fila nueva + su arista
    `aparece_en` hacia el Archivo, y persiste todo en el caso (log firmado +
    estado materializado + commit git). Devuelve SOLO los nodos de entidad
    NUEVOS creados en esta llamada (no reprocesa filas ya vistas en una
    carga anterior del mismo artefacto, ni vuelve a devolver el nodo
    Archivo si ya existía)."""
    from . import models

    record = artifact_store.store_artifact(artifact_store_dir, csv_bytes, original_filename, ingested_by)
    archivo_node = models.make_archivo(nombre=original_filename, sha256=record.sha256, tamano=record.size, mime=record.mime or "text/csv")
    archivo_node = case_store.add_node(cases_dir, keys_dir, case_id, archivo_node)

    reader = csv.DictReader(io.StringIO(_decode_csv_bytes(csv_bytes)))
    header = reader.fieldnames or []
    missing_columns = [column for column in column_mapping if column not in header]
    if missing_columns and header:
        raise ValueError(
            f"El column_mapping referencia columnas que no existen en el CSV real: "
            f"{missing_columns}. Columnas encontradas en el archivo: {header}."
        )
    rows = list(reader)

    already_processed = 0
    if record.ingestion_marker is not None:
        already_processed = int(record.ingestion_marker)

    new_rows = rows[already_processed:]
    created: list[Node] = []
    # `batch`: un solo commit git al final en vez de uno por fila -- ver su
    # docstring, bug real de performance encontrado 2026-08-13.
    with case_store.batch(cases_dir, keys_dir, case_id, f"ingest_csv: {original_filename} ({len(new_rows)} filas)"):
        for row in new_rows:
            node = make_node_from_row(node_type, row, column_mapping, defaults or {})
            case_store.add_node(cases_dir, keys_dir, case_id, node)
            edge = make_edge(
                tipo=EdgeType.APARECE_EN, origen=node.id, destino=archivo_node.id,
                artefacto_origen=archivo_node.id, confianza=1.0, derivada_por=DerivadaPor.PARSER,
            )
            case_store.add_edge(cases_dir, keys_dir, case_id, edge)
            created.append(node)

    artifact_store.set_ingestion_marker(artifact_store_dir, record.sha256, marker=str(len(rows)))
    return created
