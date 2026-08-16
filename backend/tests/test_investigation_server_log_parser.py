"""Tests de app/investigation/server_log_parser.py (paso 6, logs de
servidor con detección de formato). Datos 100% sintéticos (IPs/usuarios
inventados) -- casos reales de git/log/case_store, sin mocks."""

from __future__ import annotations

import pytest

from app.investigation import case_store, keys, server_log_parser
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


_ACCESS_LOG = (
    '192.168.1.10 - - [12/Aug/2026:14:30:00 +0000] "GET /index.html HTTP/1.1" 200 1234 "-" "Mozilla/5.0"\n'
    '192.168.1.11 - - [12/Aug/2026:14:31:00 +0000] "POST /login HTTP/1.1" 403 512 "-" "curl/7.68.0"\n'
)

_AUTH_LOG = (
    "Aug 12 14:30:00 myserver sshd[12345]: Failed password for admin from 203.0.113.5 port 4444 ssh2\n"
    "Aug 12 14:31:00 myserver sshd[12346]: Accepted password for damian from 203.0.113.6 port 4445 ssh2\n"
    "Aug 12 14:32:00 myserver sshd[12347]: Invalid user test from 203.0.113.7 port 4446\n"
)


# --- detección de formato ---------------------------------------------------------

def test_detect_format_recognizes_access_log():
    assert server_log_parser.detect_format(_ACCESS_LOG) == "access_log"


def test_detect_format_recognizes_auth_log():
    assert server_log_parser.detect_format(_AUTH_LOG) == "auth_log"


def test_detect_format_returns_none_for_unrecognized_content():
    assert server_log_parser.detect_format("esto no es ningun log conocido\nnada que ver aca\n") is None


# --- access log (Apache/Nginx Combined Log Format) --------------------------------

def test_ingest_access_log_creates_host_and_evento_nodes(cases_dir, keys_dir, artifact_store_dir):
    created = server_log_parser.ingest_server_log(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        log_bytes=_ACCESS_LOG.encode("utf-8"), original_filename="access.log", ingested_by="damian",
    )

    hosts = [n for n in created if n.tipo == NodeType.HOST]
    eventos = [n for n in created if n.tipo == NodeType.EVENTO]
    assert {h.campos["ip_o_dominio"] for h in hosts} == {"192.168.1.10", "192.168.1.11"}
    assert len(eventos) == 2
    assert any("GET /index.html" in e.campos["descripcion"] for e in eventos)
    assert all(e.campos["fuente"] == "access_log" for e in eventos)


def test_ingest_access_log_parses_the_timestamp_correctly(cases_dir, keys_dir, artifact_store_dir):
    created = server_log_parser.ingest_server_log(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        log_bytes=_ACCESS_LOG.encode("utf-8"), original_filename="access.log", ingested_by="damian",
    )

    eventos = sorted((n for n in created if n.tipo == NodeType.EVENTO), key=lambda n: n.campos["timestamp_utc"])
    assert eventos[0].campos["timestamp_utc"].startswith("2026-08-12T14:30:00")


def test_the_same_host_across_two_different_log_files_resolves_to_the_same_node(cases_dir, keys_dir, artifact_store_dir):
    """A diferencia de chat_parser.py (donde una Persona necesita scope_key
    por archivo), Host SÍ tiene una clave natural globalmente estable (la
    IP) -- dos archivos DISTINTOS que mencionan la misma IP tienen que
    resolver al MISMO nodo Host, sin duplicar."""
    server_log_parser.ingest_server_log(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        log_bytes=_ACCESS_LOG.encode("utf-8"), original_filename="access1.log", ingested_by="damian",
    )
    other_log = '192.168.1.10 - - [13/Aug/2026:09:00:00 +0000] "GET /admin HTTP/1.1" 200 100 "-" "curl"\n'
    server_log_parser.ingest_server_log(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        log_bytes=other_log.encode("utf-8"), original_filename="access2.log", ingested_by="damian",
    )

    hosts = [n for n in case_store.read_nodes(cases_dir, "caso-1") if n.tipo == NodeType.HOST]
    ips = [h.campos["ip_o_dominio"] for h in hosts]
    assert ips.count("192.168.1.10") == 1  # un solo nodo Host para esa IP, en los dos archivos


# --- auth.log (SSH) ---------------------------------------------------------------

def test_ingest_auth_log_creates_host_cuenta_and_evento_nodes(cases_dir, keys_dir, artifact_store_dir):
    created = server_log_parser.ingest_server_log(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        log_bytes=_AUTH_LOG.encode("utf-8"), original_filename="auth.log", ingested_by="damian",
    )

    hosts = [n for n in created if n.tipo == NodeType.HOST]
    cuentas = [n for n in created if n.tipo == NodeType.CUENTA]
    eventos = [n for n in created if n.tipo == NodeType.EVENTO]
    assert len(hosts) == 3
    assert len(cuentas) == 3
    assert len(eventos) == 3
    assert {c.campos["handle"] for c in cuentas} == {"203.0.113.5:admin", "203.0.113.6:damian", "203.0.113.7:test"}
    assert any("Failed password" in e.campos["descripcion"] for e in eventos)
    assert any("Accepted password" in e.campos["descripcion"] for e in eventos)
    assert any("Invalid user" in e.campos["descripcion"] for e in eventos)


def test_ssh_username_is_scoped_by_ip_not_global(cases_dir, keys_dir, artifact_store_dir):
    """'admin' en el servidor A y 'admin' en el servidor B NO son la misma
    cuenta -- mismo criterio que remitentes de WhatsApp (nombre solo no es
    clave natural estable)."""
    log_two_servers = (
        "Aug 12 14:30:00 myserver sshd[1]: Failed password for admin from 10.0.0.1 port 1 ssh2\n"
        "Aug 12 14:31:00 myserver sshd[2]: Failed password for admin from 10.0.0.2 port 2 ssh2\n"
    )

    created = server_log_parser.ingest_server_log(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        log_bytes=log_two_servers.encode("utf-8"), original_filename="auth.log", ingested_by="damian",
    )

    cuentas = [n for n in created if n.tipo == NodeType.CUENTA]
    assert len(cuentas) == 2
    assert {c.campos["handle"] for c in cuentas} == {"10.0.0.1:admin", "10.0.0.2:admin"}


# --- errores y reingesta -----------------------------------------------------------

def test_unrecognized_format_raises_a_clear_error(cases_dir, keys_dir, artifact_store_dir):
    with pytest.raises(ValueError, match="No pude reconocer el formato"):
        server_log_parser.ingest_server_log(
            cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
            log_bytes=b"esto no es un log valido\nni esto tampoco\n", original_filename="mystery.log", ingested_by="damian",
        )


def test_reingesting_the_exact_same_log_bytes_processes_nothing_new(cases_dir, keys_dir, artifact_store_dir):
    server_log_parser.ingest_server_log(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        log_bytes=_ACCESS_LOG.encode("utf-8"), original_filename="access.log", ingested_by="damian",
    )

    second = server_log_parser.ingest_server_log(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        log_bytes=_ACCESS_LOG.encode("utf-8"), original_filename="access.log", ingested_by="damian",
    )

    assert second == []
    all_eventos = [n for n in case_store.read_nodes(cases_dir, "caso-1") if n.tipo == NodeType.EVENTO]
    assert len(all_eventos) == 2


def test_traceability_edges_point_to_the_archivo_node(cases_dir, keys_dir, artifact_store_dir):
    server_log_parser.ingest_server_log(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        log_bytes=_ACCESS_LOG.encode("utf-8"), original_filename="access.log", ingested_by="damian",
    )

    nodes = case_store.read_nodes(cases_dir, "caso-1")
    archivo = next(n for n in nodes if n.tipo == NodeType.ARCHIVO)
    eventos = [n for n in nodes if n.tipo == NodeType.EVENTO]
    edges = case_store.read_edges(cases_dir, "caso-1")

    for evento in eventos:
        assert any(e.origen == evento.id and e.destino == archivo.id for e in edges)
