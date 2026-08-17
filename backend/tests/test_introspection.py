import hashlib

import pytest

from app import audit_log
from app.introspection import analyzer
from app.obsidian import embeddings, vault


@pytest.fixture(autouse=True)
def _tmp_vault(tmp_path, monkeypatch):
    monkeypatch.setattr(vault.settings, "obsidian_vault_path", str(tmp_path / "vault"))
    monkeypatch.setattr(embeddings.settings, "obsidian_embeddings_path", str(tmp_path / "embeddings.json"))
    return tmp_path / "vault"


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _write_entry(conv_id: str, path: str, content: str, ts: str, ok: bool = True, error: str | None = None) -> dict:
    entry = {
        "timestamp": ts,
        "target": "agent",
        "tool": "fs_write_file",
        "conversation_id": conv_id,
        "arguments": {"path": path, "append": False, "content_sha256": _hash(content), "content_length": len(content)},
        "ok": ok,
    }
    if ok:
        entry["result"] = {"path": path, "bytes_written": len(content)}
    else:
        entry["error"] = error or "bloqueado"
    return entry


def test_find_repeated_identical_writes_detects_a_run_at_or_above_threshold(monkeypatch):
    entries = [_write_entry("c1", "a.json", "{}", f"t{i}") for i in range(3)]
    monkeypatch.setattr(audit_log, "read_entries", lambda **kw: entries)

    findings = analyzer.analyze_conversation("c1")

    assert len(findings) == 1
    assert findings[0].pattern == "reescritura_identica_repetida"
    assert findings[0].path == "a.json"
    assert len(findings[0].evidence) == 3


def test_find_repeated_identical_writes_ignores_short_runs(monkeypatch):
    entries = [_write_entry("c1", "a.json", "{}", f"t{i}") for i in range(2)]
    monkeypatch.setattr(audit_log, "read_entries", lambda **kw: entries)

    findings = analyzer.analyze_conversation("c1")

    assert findings == []


def test_find_repeated_identical_writes_ignores_different_content(monkeypatch):
    entries = [_write_entry("c1", "a.json", f"content-{i}", f"t{i}") for i in range(4)]
    monkeypatch.setattr(audit_log, "read_entries", lambda **kw: entries)

    findings = analyzer.analyze_conversation("c1")

    assert findings == []


def test_find_repeated_identical_writes_ignores_different_paths(monkeypatch):
    entries = [_write_entry("c1", f"file-{i}.json", "{}", f"t{i}") for i in range(4)]
    monkeypatch.setattr(audit_log, "read_entries", lambda **kw: entries)

    findings = analyzer.analyze_conversation("c1")

    assert findings == []


def test_find_abandoned_blocked_writes_detects_a_never_retried_block(monkeypatch):
    entries = [_write_entry("c1", "Main.java", "code", "t0", ok=False, error="obsidian gate")]
    monkeypatch.setattr(audit_log, "read_entries", lambda **kw: entries)

    findings = analyzer.analyze_conversation("c1")

    assert len(findings) == 1
    assert findings[0].pattern == "archivo_bloqueado_abandonado"
    assert findings[0].path == "Main.java"


def test_find_abandoned_blocked_writes_ignores_a_successfully_retried_block(monkeypatch):
    entries = [
        _write_entry("c1", "Main.java", "code", "t0", ok=False, error="obsidian gate"),
        _write_entry("c1", "Main.java", "code fixed", "t1", ok=True),
    ]
    monkeypatch.setattr(audit_log, "read_entries", lambda **kw: entries)

    findings = analyzer.analyze_conversation("c1")

    assert findings == []


def test_find_abandoned_blocked_writes_ignores_a_block_retried_after_other_files(monkeypatch):
    """El bloqueo se retoma DESPUÉS de que se escribieron otros archivos en el
    medio -- no tiene que importar el orden relativo a otros paths, solo que
    haya una escritura exitosa posterior AL MISMO path."""
    entries = [
        _write_entry("c1", "Main.java", "code", "t0", ok=False, error="obsidian gate"),
        _write_entry("c1", "Other.java", "x", "t1", ok=True),
        _write_entry("c1", "Main.java", "code fixed", "t2", ok=True),
    ]
    monkeypatch.setattr(audit_log, "read_entries", lambda **kw: entries)

    findings = analyzer.analyze_conversation("c1")

    assert findings == []


def test_analyze_conversation_only_considers_matching_conversation_id(monkeypatch):
    def fake_read_entries(**kwargs):
        assert kwargs.get("conversation_id") == "c1"
        return []

    monkeypatch.setattr(audit_log, "read_entries", fake_read_entries)

    analyzer.analyze_conversation("c1")


def test_write_finding_note_saves_a_note_with_expected_structure(_tmp_vault, monkeypatch):
    entries = [_write_entry("c1", "src/sneaky_sword.json", "{}", f"t{i}") for i in range(3)]
    monkeypatch.setattr(audit_log, "read_entries", lambda **kw: entries)
    findings = analyzer.analyze_conversation("c1")
    assert len(findings) == 1

    note = analyzer.write_finding_note(findings[0])

    assert note.author == "jarvis"
    assert "autodiagnostico" in note.tags
    assert "reescritura_identica_repetida" in note.tags
    assert "sneaky_sword.json" in note.content
    assert findings[0].hypothesis in note.content
    assert findings[0].suggested_fix in note.content
    saved = vault.read_note(note.id)
    assert saved.content == note.content


def test_analyzer_detects_the_two_real_bugs_found_in_v6(monkeypatch):
    """Prueba de extremo a extremo con la evidencia REAL de la sesión v6
    (2026-08-10, test del mod de Minecraft con veneno al golpear): los mismos
    dos bugs que se reconstruyeron a mano leyendo `backend_restart5.log` línea
    por línea. Los timestamps y paths acá son los reales de esa corrida --
    reexpresados como entradas de `audit_log` (el hook estructurado no
    existía todavía durante v6, así que no hay un `audit.log` real de esa
    corrida; esto reproduce la misma secuencia de eventos con el formato que
    el analyzer sí consume hoy).

    Bug 1: `sneaky_sword.json` reescrito con contenido idéntico 14 veces
    seguidas entre 21:28:02 y 21:35:42, sin ningún progreso real.
    Bug 2: `SpadeMod.java` (con el AttackEntityCallback correcto) bloqueado a
    las 21:23:01 por el guardrail de pending-file y nunca retomado en el
    resto de la sesión."""
    conv_id = "minecraft-mod-test-v6"
    same_model_json = (
        '{\n  "parent": "item/handheld",\n  "textures": {\n    "layer0": "spade_mod:item/sneaky_sword"\n  }\n}'
    )
    spademod_java = (
        "package net.dam.spademod;\n\npublic class SpadeMod implements ModInitializer {\n"
        "    // AttackEntityCallback.EVENT.register(...)\n}"
    )
    fabric_mod_json = '{"schemaVersion": 1, "id": "spade_mod"}'

    entries = [
        # fabric.mod.json bloqueado (gate de Obsidian) a las 20:54
        _write_entry(conv_id, "fabric.mod.json", fabric_mod_json, "2026-08-10T20:54:46Z", ok=False, error="Obsidian gate"),
        # SpadeMod.java bloqueado (pending-file: fabric.mod.json seguía pendiente) a las 21:23
        _write_entry(
            conv_id, "SpadeMod.java", spademod_java, "2026-08-10T21:23:01Z", ok=False,
            error="Todavía tenés pendiente reintentar 'fabric.mod.json'",
        ),
        # fabric.mod.json reintentado con éxito a las 21:24 -- SpadeMod.java NUNCA se retoma después de esto
        _write_entry(conv_id, "fabric.mod.json", fabric_mod_json, "2026-08-10T21:24:00Z", ok=True),
        _write_entry(conv_id, "ModConstants.java", "package x;", "2026-08-10T21:25:00Z", ok=True),
        _write_entry(conv_id, "SpadeModItems.java", "package x;", "2026-08-10T21:26:00Z", ok=True),
        _write_entry(conv_id, "en_us.json", "{}", "2026-08-10T21:26:55Z", ok=True),
        _write_entry(conv_id, "es_es.json", "{}", "2026-08-10T21:27:28Z", ok=True),
        # 14 reescrituras idénticas seguidas del mismo item model
        *[
            _write_entry(conv_id, "sneaky_sword.json", same_model_json, f"2026-08-10T21:{28 + i}:00Z")
            for i in range(14)
        ],
    ]
    monkeypatch.setattr(audit_log, "read_entries", lambda **kw: entries)

    findings = analyzer.analyze_conversation(conv_id)

    by_pattern = {f.pattern: f for f in findings}
    assert "reescritura_identica_repetida" in by_pattern
    loop_finding = by_pattern["reescritura_identica_repetida"]
    assert loop_finding.path == "sneaky_sword.json"
    assert len(loop_finding.evidence) == 14

    assert "archivo_bloqueado_abandonado" in by_pattern
    abandoned = [f for f in findings if f.pattern == "archivo_bloqueado_abandonado"]
    assert any(f.path == "SpadeMod.java" for f in abandoned)
    # fabric.mod.json SÍ se retomó -- no debería aparecer como abandonado
    assert not any(f.path == "fabric.mod.json" for f in abandoned)
