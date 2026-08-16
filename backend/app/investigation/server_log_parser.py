"""Parser de logs de servidor con detección de formato (spec sección 2,
paso 6): access logs de Apache/Nginx (Combined Log Format, mismo formato
para ambos) y `auth.log` de Linux (intentos de login SSH). Determinístico,
mismo criterio que csv_parser.py/chat_parser.py -- ningún LLM en el medio.

Cada línea reconocida se convierte en un nodo `Host` (la IP, id
determinístico por ip -- ver `models.make_host`, ya resuelve dedup real
entre archivos sin necesitar ningún `scope_key` como chat_parser.py: una IP
es una clave natural estable globalmente, a diferencia del nombre de un
remitente de WhatsApp) y un nodo `Evento` (una entrada de timeline real por
línea de log). En `auth.log`, si la línea trae un usuario, también se crea
un nodo `Cuenta` (plataforma="ssh") -- el handle se arma como `IP:usuario`,
NUNCA solo `usuario`, porque un nombre de usuario como "root" o "admin" no
es una clave natural estable entre servidores distintos (mismo problema que
el nombre de un remitente de WhatsApp, mismo tipo de solución: acotar el
alcance a algo que sí es estable, acá el host de origen).

Detección de formato: se prueba cada línea no vacía contra los dos
patrones conocidos y se usa el que matchea a la MAYORÍA de las líneas de
muestra -- si ninguno matchea una fracción mínima razonable, se rechaza
en vez de adivinar (spec: nunca inventar estructura que el archivo no
tiene). Formato mixto (dos tipos de log concatenados en un mismo archivo)
no está soportado -- se ingesta con el formato ganador, las líneas del
otro formato simplemente no matchean y se ignoran (mismo criterio que una
línea corrupta cualquiera).

Limitación real y documentada (igual que WhatsApp en chat_parser.py):
`auth.log` clásico de syslog NO lleva año en el timestamp ("Aug 12
14:30:00") -- `dateutil` (vía `timeline.normalize_timestamp`) completa con
el año actual del sistema que corre el parser, que puede no ser el año
real del log si se analiza tiempo después de generado. No hay forma de
inferir el año real desde la línea sola sin inventar datos que el propio
archivo no tiene, así que esto queda como limitación conocida, no un bug
a "arreglar" adivinando."""

from __future__ import annotations

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
    make_host,
)

_MAX_DESCRIPCION_CHARS = 500

_APACHE_COMBINED_RE = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[(?P<fecha>[^\]]+)\] '
    r'"(?P<metodo>\S+) (?P<path>\S+)(?: \S+)?" (?P<status>\d{3}) (?P<size>\S+)'
)

_AUTH_SSH_RE = re.compile(
    r'^(?P<fecha>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+\S+\s+sshd\[\d+\]:\s+'
    r'(?P<resultado>Failed password|Accepted password|Invalid user)\s+'
    r'(?:for\s+)?(?:invalid user\s+)?(?P<usuario>\S+)\s+from\s+(?P<ip>\S+)\s+port\s+(?P<puerto>\d+)'
)

_MIN_MATCH_RATIO = 0.5  # al menos la mitad de las líneas no vacías tienen que matchear para aceptar un formato


def _score_format(lines: list[str], pattern: re.Pattern) -> float:
    non_empty = [ln for ln in lines if ln.strip()]
    if not non_empty:
        return 0.0
    matches = sum(1 for ln in non_empty if pattern.match(ln))
    return matches / len(non_empty)


def detect_format(text: str) -> str | None:
    lines = text.splitlines()
    scores = {"access_log": _score_format(lines, _APACHE_COMBINED_RE), "auth_log": _score_format(lines, _AUTH_SSH_RE)}
    best_format, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score < _MIN_MATCH_RATIO:
        return None
    return best_format


def _parse_access_log(text: str) -> list[dict]:
    entries = []
    for line in text.splitlines():
        match = _APACHE_COMBINED_RE.match(line)
        if not match:
            continue
        entries.append({
            "raw_timestamp": match["fecha"].replace(":", " ", 1),  # "12/Aug/2026:14:30:00 +0000" -> separa fecha y hora
            "ip": match["ip"],
            "usuario": None,
            "descripcion": f'{match["metodo"]} {match["path"]} -> {match["status"]} ({match["size"]} bytes)',
        })
    return entries


def _parse_auth_log(text: str) -> list[dict]:
    entries = []
    for line in text.splitlines():
        match = _AUTH_SSH_RE.match(line)
        if not match:
            continue
        entries.append({
            "raw_timestamp": match["fecha"],
            "ip": match["ip"],
            "usuario": match["usuario"],
            "descripcion": f'{match["resultado"]} para usuario "{match["usuario"]}" desde {match["ip"]} puerto {match["puerto"]}',
        })
    return entries


_PARSERS = {"access_log": _parse_access_log, "auth_log": _parse_auth_log}


def ingest_server_log(
    *, cases_dir: str | Path, keys_dir: str | Path, artifact_store_dir: str | Path, case_id: str,
    log_bytes: bytes, original_filename: str, ingested_by: str,
) -> list[Node]:
    text = log_bytes.decode("utf-8", errors="replace")
    log_format = detect_format(text)
    if log_format is None:
        raise ValueError(
            f"No pude reconocer el formato de '{original_filename}' -- ni Apache/Nginx (Combined Log Format) "
            "ni auth.log (SSH) matchean una fracción razonable de las líneas. Este parser no adivina formatos "
            "no soportados."
        )

    record = artifact_store.store_artifact(artifact_store_dir, log_bytes, original_filename, ingested_by)
    archivo_node = make_archivo(nombre=original_filename, sha256=record.sha256, tamano=record.size, mime=record.mime or "text/plain")
    archivo_node = case_store.add_node(cases_dir, keys_dir, case_id, archivo_node)

    entries = _PARSERS[log_format](text)
    already_processed = int(record.ingestion_marker) if record.ingestion_marker else 0
    new_entries = entries[already_processed:]

    created: list[Node] = []
    seen_ids: set[str] = set()
    archivo_sha256 = archivo_node.campos["sha256"]

    # `batch`: un solo commit git al final en vez de uno por línea -- ver
    # docstring de case_store.batch, bug real de performance encontrado
    # 2026-08-13 (un log de 50.000 líneas medía ~320ms/línea reales, ~4.4hs
    # proyectadas, casi todo overhead de subprocess de git).
    with case_store.batch(cases_dir, keys_dir, case_id, f"ingest_server_log: {original_filename} ({len(new_entries)} líneas)"):
        for entry in new_entries:
            try:
                normalized = timeline.normalize_timestamp(entry["raw_timestamp"])
            except (ValueError, TypeError, OverflowError):
                continue  # línea con timestamp no parseable -- se descarta ESA línea, no el archivo entero

            host_node = case_store.add_node(cases_dir, keys_dir, case_id, make_host(ip_o_dominio=entry["ip"]))
            if host_node.id not in seen_ids:
                seen_ids.add(host_node.id)
                created.append(host_node)

            evento_id = deterministic_node_id(
                NodeType.EVENTO, f"{archivo_sha256}:{normalized.utc}:{entry['ip']}:{entry['descripcion'][:80]}"
            )
            evento = case_store.add_node(cases_dir, keys_dir, case_id, make_evento(
                timestamp_utc=normalized.utc, descripcion=entry["descripcion"][:_MAX_DESCRIPCION_CHARS],
                fuente=log_format, node_id=evento_id,
            ))
            created.append(evento)

            case_store.add_edge(cases_dir, keys_dir, case_id, make_edge(
                tipo=EdgeType.APARECE_EN, origen=host_node.id, destino=evento.id,
                artefacto_origen=archivo_node.id, confianza=1.0, derivada_por=DerivadaPor.PARSER,
                timestamp=normalized.utc,
            ))
            case_store.add_edge(cases_dir, keys_dir, case_id, make_edge(
                tipo=EdgeType.APARECE_EN, origen=evento.id, destino=archivo_node.id,
                artefacto_origen=archivo_node.id, confianza=1.0, derivada_por=DerivadaPor.PARSER,
                timestamp=normalized.utc,
            ))

            if entry["usuario"]:
                cuenta_node = case_store.add_node(cases_dir, keys_dir, case_id, make_cuenta(
                    plataforma="ssh", handle=f"{entry['ip']}:{entry['usuario']}",
                ))
                if cuenta_node.id not in seen_ids:
                    seen_ids.add(cuenta_node.id)
                    created.append(cuenta_node)
                case_store.add_edge(cases_dir, keys_dir, case_id, make_edge(
                    tipo=EdgeType.APARECE_EN, origen=cuenta_node.id, destino=evento.id,
                    artefacto_origen=archivo_node.id, confianza=1.0, derivada_por=DerivadaPor.PARSER,
                    timestamp=normalized.utc,
                ))

    artifact_store.set_ingestion_marker(artifact_store_dir, record.sha256, marker=str(len(entries)))
    return created
