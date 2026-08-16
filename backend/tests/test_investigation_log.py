"""Tests de app/investigation/log.py -- log append-only, encadenado por hash
y firmado con Ed25519 real (misma clave real de test_investigation_keys.py,
no mockeada). Los tests de manipulación escriben directo al archivo .jsonl
para simular un ataque real (alguien editando el log a mano por fuera de
`append_entry`), no llaman a ninguna función "de manipular" porque a
propósito el módulo no expone ninguna."""

from __future__ import annotations

import json

import pytest

from app.investigation import keys, log


@pytest.fixture()
def keys_dir(tmp_path):
    d = tmp_path / "keys"
    keys.ensure_keypair(d)
    return d


def test_append_entry_creates_genesis_entry(tmp_path, keys_dir):
    log_path = tmp_path / "log.jsonl"

    entry = log.append_entry(log_path, keys_dir, op="ingest_artifact", payload={"sha256": "a" * 64})

    assert entry.seq == 0
    assert entry.prev_hash == log.GENESIS_HASH
    assert entry.op == "ingest_artifact"


def test_append_entry_chains_to_the_previous_entry(tmp_path, keys_dir):
    log_path = tmp_path / "log.jsonl"

    first = log.append_entry(log_path, keys_dir, op="ingest_artifact", payload={"a": 1})
    second = log.append_entry(log_path, keys_dir, op="create_node", payload={"b": 2})

    assert second.seq == 1
    assert second.prev_hash == first.entry_hash


def test_append_entry_writes_real_lines_to_disk(tmp_path, keys_dir):
    log_path = tmp_path / "log.jsonl"

    log.append_entry(log_path, keys_dir, op="ingest_artifact", payload={"a": 1})
    log.append_entry(log_path, keys_dir, op="create_node", payload={"b": 2})

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["op"] == "ingest_artifact"
    assert json.loads(lines[1])["op"] == "create_node"


def test_verify_chain_ok_on_untouched_log(tmp_path, keys_dir):
    log_path = tmp_path / "log.jsonl"
    for i in range(5):
        log.append_entry(log_path, keys_dir, op="create_node", payload={"i": i})

    result = log.verify_chain(log_path, keys_dir)

    assert result.ok is True
    assert result.entries_checked == 5
    assert result.broken_at_seq is None


def test_verify_chain_ok_on_empty_log(tmp_path, keys_dir):
    log_path = tmp_path / "log.jsonl"

    result = log.verify_chain(log_path, keys_dir)

    assert result.ok is True
    assert result.entries_checked == 0


def test_verify_chain_detects_payload_tampering(tmp_path, keys_dir):
    """Ataque real simulado: alguien edita el contenido de una entrada vieja
    directo en el archivo, por fuera de append_entry."""
    log_path = tmp_path / "log.jsonl"
    log.append_entry(log_path, keys_dir, op="create_node", payload={"monto": 100})
    log.append_entry(log_path, keys_dir, op="create_node", payload={"monto": 200})

    lines = log_path.read_text(encoding="utf-8").splitlines()
    entry0 = json.loads(lines[0])
    entry0["payload"]["monto"] = 999999  # manipulación directa
    lines[0] = json.dumps(entry0)
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = log.verify_chain(log_path, keys_dir)

    assert result.ok is False
    assert result.broken_at_seq == 0
    assert "modificada" in result.reason or "hash" in result.reason.lower()


def test_verify_chain_detects_a_deleted_middle_entry(tmp_path, keys_dir):
    log_path = tmp_path / "log.jsonl"
    log.append_entry(log_path, keys_dir, op="create_node", payload={"i": 0})
    log.append_entry(log_path, keys_dir, op="create_node", payload={"i": 1})
    log.append_entry(log_path, keys_dir, op="create_node", payload={"i": 2})

    lines = log_path.read_text(encoding="utf-8").splitlines()
    del lines[1]  # borra la entrada del medio -- rompe seq y prev_hash de la siguiente
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = log.verify_chain(log_path, keys_dir)

    assert result.ok is False
    assert result.broken_at_seq == 2  # la entrada que quedó (i=2) ahora aparece como segunda (index 1) con seq=2


def test_verify_chain_detects_a_forged_entry_with_correct_hash_chain_but_no_real_signature(tmp_path, keys_dir):
    """El ataque más sofisticado: alguien SIN la clave privada reescribe una
    entrada Y recalcula el hash/prev_hash de todo lo que sigue para que la
    cadena de hashes quede perfectamente consistente consigo misma -- pero
    no puede reproducir una firma válida sin la clave real. Esto es
    justamente lo que separa la firma del mero encadenamiento por hash (ver
    docstring del módulo)."""
    log_path = tmp_path / "log.jsonl"
    log.append_entry(log_path, keys_dir, op="create_node", payload={"monto": 100})

    lines = log_path.read_text(encoding="utf-8").splitlines()
    entry0 = json.loads(lines[0])
    entry0["payload"]["monto"] = 999999
    # Recalcula un entry_hash "consistente" con el contenido forjado -- pero
    # la firma sigue siendo la vieja, de un contenido distinto.
    import hashlib

    forged_content = {
        "seq": entry0["seq"], "timestamp": entry0["timestamp"], "op": entry0["op"],
        "payload": entry0["payload"], "prev_hash": entry0["prev_hash"],
    }
    forged_hash = hashlib.sha256(
        json.dumps(forged_content, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    entry0["entry_hash"] = forged_hash  # el atacante SÍ puede recalcular esto sin la clave
    lines[0] = json.dumps(entry0)
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = log.verify_chain(log_path, keys_dir)

    assert result.ok is False
    assert result.broken_at_seq == 0
    assert "firma" in result.reason.lower()


def test_verify_chain_with_wrong_public_key_fails(tmp_path, keys_dir, tmp_path_factory):
    log_path = tmp_path / "log.jsonl"
    log.append_entry(log_path, keys_dir, op="create_node", payload={"i": 0})

    other_keys_dir = tmp_path_factory.mktemp("otras_claves")
    keys.ensure_keypair(other_keys_dir)

    result = log.verify_chain(log_path, other_keys_dir)

    assert result.ok is False
    assert "firma" in result.reason.lower()


def test_read_entries_returns_empty_list_for_missing_file(tmp_path):
    assert log.read_entries(tmp_path / "no_existe.jsonl") == []


def test_log_module_exposes_no_edit_or_delete_function():
    """Chequeo estructural del invariante 'append-only de verdad' -- ver
    docstring del módulo: no puede existir ninguna función pública acá que
    permita editar/borrar una entrada ya escrita."""
    public_names = [name for name in dir(log) if not name.startswith("_")]
    forbidden = {"edit_entry", "delete_entry", "remove_entry", "update_entry", "overwrite_entry"}
    assert not (set(public_names) & forbidden)


# --- _last_entry: fix real de performance (2026-08-13) --------------------------------

def test_last_entry_returns_none_for_a_missing_file(tmp_path):
    assert log._last_entry(tmp_path / "no_existe.jsonl") is None


def test_last_entry_matches_read_entries_last_element(tmp_path, keys_dir):
    log_path = tmp_path / "log.jsonl"
    for i in range(30):
        log.append_entry(log_path, keys_dir, op="create_node", payload={"i": i})

    via_full_read = log.read_entries(log_path)[-1]
    via_tail_read = log._last_entry(log_path)

    assert via_tail_read == via_full_read


def test_append_entry_still_chains_correctly_across_many_entries(tmp_path, keys_dir):
    """Regresión end-to-end del bug real de performance: `append_entry` ya
    no relee el archivo entero para encadenar (usa `_last_entry`, que solo
    lee la cola) -- confirma que la cadena resultante sigue siendo
    perfectamente válida (mismo prev_hash/seq que antes), no solo rápida."""
    log_path = tmp_path / "log.jsonl"
    for i in range(50):
        log.append_entry(log_path, keys_dir, op="create_node", payload={"i": i})

    result = log.verify_chain(log_path, keys_dir)
    assert result.ok is True
    assert result.entries_checked == 50

    entries = log.read_entries(log_path)
    assert [e.seq for e in entries] == list(range(50))


# --- recuperación de una escritura interrumpida (2026-08-13) --------------------------

def _truncate_last_line(log_path, keys_dir, garbage: str):
    """Simula un kill duro real a mitad de un write() -- una línea sin
    cerrar, sin el '\\n' final, exactamente lo que deja una interrupción a
    mitad de escritura."""
    with log_path.open("a", encoding="utf-8") as f:
        f.write(garbage)


def test_read_entries_tolerates_a_truncated_final_line(tmp_path, keys_dir):
    """Bug real, grave, encontrado en testing adversarial (2026-08-13,
    'kill duro a mitad de un write'): antes de este fix, CUALQUIER lectura
    del log (incluida append_entry, vía _last_entry) reventaba con un
    JSONDecodeError crudo si la última línea estaba truncada -- el caso
    quedaba inutilizable para siempre hasta reparar el archivo a mano."""
    log_path = tmp_path / "log.jsonl"
    log.append_entry(log_path, keys_dir, op="create_node", payload={"i": 0})
    _truncate_last_line(log_path, keys_dir, '{"seq": 1, "timestamp": "x", "op": "create_node", "payload": {"roto')

    entries = log.read_entries(log_path)
    assert [e.payload for e in entries] == [{"i": 0}]


def test_verify_chain_tolerates_a_truncated_final_line(tmp_path, keys_dir):
    log_path = tmp_path / "log.jsonl"
    log.append_entry(log_path, keys_dir, op="create_node", payload={"i": 0})
    _truncate_last_line(log_path, keys_dir, '{"seq": 1, "timestamp": "x", "op": "create_node", "payload": {"roto')

    result = log.verify_chain(log_path, keys_dir)
    assert result.ok is True
    assert result.entries_checked == 1


def test_append_entry_recovers_cleanly_after_a_truncated_final_line(tmp_path, keys_dir):
    """El caso más importante: el log tiene que seguir aceptando escrituras
    NUEVAS después de una interrupción, encadenadas correctamente a la
    última entrada VÁLIDA (no a la línea rota) -- confirmado en vivo antes
    de este fix, esto reventaba con un JSONDecodeError crudo.

    Una vez que la línea rota queda en el MEDIO del archivo (ya no es la
    última), `verify_chain` la sigue marcando ok=False a propósito (ver
    docstring de CorruptedLogError) -- el caso sigue FUNCIONANDO para
    escrituras nuevas, pero un humano necesita revisar esa línea antes de
    confiar en la historia completa. Esto NO es una regresión: es la
    distinción deliberada entre "el kill me interrumpió, tolero la punta"
    y "hay basura real en el medio de mi historia, avisame"."""
    log_path = tmp_path / "log.jsonl"
    first = log.append_entry(log_path, keys_dir, op="create_node", payload={"i": 0})
    _truncate_last_line(log_path, keys_dir, '{"seq": 1, "timestamp": "x", "op": "create_node", "payload": {"roto')

    recovered = log.append_entry(log_path, keys_dir, op="create_node", payload={"i": 1})

    assert recovered.seq == 1  # encadenado a la entrada 0 real, no a la rota
    assert recovered.prev_hash == first.entry_hash

    result = log.verify_chain(log_path, keys_dir)
    assert result.ok is False  # la línea rota, ahora en el medio, se sigue marcando -- a propósito
    assert "no es JSON" in result.reason


def test_read_entries_raises_a_clear_error_for_corruption_that_is_not_the_last_line(tmp_path, keys_dir):
    """Una línea corrupta que NO es la última es una señal más seria que
    un kill a mitad de un write (podría ser manipulación real) -- nunca se
    saltea en silencio como la última línea sí se tolera."""
    log_path = tmp_path / "log.jsonl"
    first = log.append_entry(log_path, keys_dir, op="create_node", payload={"i": 0})
    _truncate_last_line(log_path, keys_dir, '{"seq": 1, "timestamp": "x", "op": "create_node", "payload": {"roto')
    log.append_entry(log_path, keys_dir, op="create_node", payload={"i": 2})  # ahora la línea rota queda en el medio

    with pytest.raises(log.CorruptedLogError):
        log.read_entries(log_path)
