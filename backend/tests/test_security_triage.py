"""Tests del triage con LLM de hallazgos (app/security/triage.py) -- el
cliente del modelo se mockea (no depende de Ollama corriendo), lo que se
prueba es la lógica real: construcción del prompt con código real, parseo
tolerante del veredicto, y que un fallo de la llamada nunca se traduce en
perder un hallazgo real en silencio."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.findings.models import Finding
from app.obsidian import embeddings, vault
from app.security import triage, triage_reference


@pytest.fixture(autouse=True)
def _tmp_vault(tmp_path, monkeypatch):
    monkeypatch.setattr(vault.settings, "obsidian_vault_path", str(tmp_path / "vault"))
    monkeypatch.setattr(embeddings.settings, "obsidian_embeddings_path", str(tmp_path / "embeddings.json"))
    return tmp_path / "vault"


def _fake_response(content: str):
    message = SimpleNamespace(content=content)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _finding(**overrides) -> Finding:
    defaults = dict(
        id="f1", tool="semgrep", file="app.py", line=5, end_line=5,
        severity="high", rule_id="tainted-sql", message="posible SQL injection",
    )
    defaults.update(overrides)
    return Finding(**defaults)


def test_code_context_marks_the_exact_line(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "app.py").write_text("\n".join(f"line {i}" for i in range(1, 21)), encoding="utf-8")
    finding = _finding(file="app.py", line=10, end_line=10)

    context = triage._code_context(project, finding, context_lines=2)

    lines = context.splitlines()
    assert any(l.startswith(">>") and "10:" in l for l in lines)
    assert sum(1 for l in lines if l.startswith(">>")) == 1
    assert len(lines) == 5  # 2 antes + la marcada + 2 despues


def test_code_context_handles_missing_file_gracefully(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    finding = _finding(file="does_not_exist.py")

    context = triage._code_context(project, finding)

    assert "no se pudo leer" in context


def test_parse_verdict_extracts_clean_json():
    verdict = triage._parse_verdict('{"verdict": "false_positive", "reasoning": "usa PreparedStatement"}')

    assert verdict.verdict == "false_positive"
    assert "PreparedStatement" in verdict.reasoning


def test_parse_verdict_extracts_json_wrapped_in_extra_text():
    verdict = triage._parse_verdict(
        'Claro, analizando el codigo:\n{"verdict": "real", "reasoning": "sin sanitizar"}\nEso es todo.'
    )

    assert verdict.verdict == "real"


def test_parse_verdict_defaults_to_real_on_unparseable_response():
    """Nunca perder un hallazgo real por un fallo de parseo -- ante la duda,
    el default conservador es 'real', igual que le pide el system prompt al
    modelo."""
    verdict = triage._parse_verdict("no tengo idea, la verdad")

    assert verdict.verdict == "real"


def test_parse_verdict_rejects_an_invalid_verdict_value():
    verdict = triage._parse_verdict('{"verdict": "maybe", "reasoning": "no se"}')

    assert verdict.verdict == "real"


@pytest.mark.anyio
async def test_triage_finding_sends_real_code_context_to_the_model(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "app.py").write_text(
        "def login(name):\n    q = db.execute('SELECT * FROM users WHERE name=?', [name])\n    return q\n",
        encoding="utf-8",
    )
    finding = _finding(file="app.py", line=2, end_line=2, rule_id="tainted-sql-from-http-request")

    captured = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return _fake_response('{"verdict": "false_positive", "reasoning": "parametros bindeados, no concatenacion"}')

    monkeypatch.setattr(triage.client.chat.completions, "create", fake_create)

    verdict = await triage.triage_finding(project, finding)

    assert verdict.verdict == "false_positive"
    user_msg = captured["messages"][1]["content"]
    assert "db.execute" in user_msg
    assert finding.rule_id in user_msg
    assert captured["temperature"] == 0
    assert captured["max_tokens"] == triage._MAX_OUTPUT_TOKENS


@pytest.mark.anyio
async def test_triage_finding_injects_the_curated_reference_for_a_known_category(tmp_path, monkeypatch):
    """Bug real 2026-08-11 (primer resultado del triage: score 44.0% -> 37.6%,
    empeoró): el modelo confundía mitigaciones entre categorías distintas de
    vulnerabilidad -- ver el caso concreto de trustbound en
    app/security/triage_reference.py. Esto prueba que, para un rule_id que
    mapea a una categoría con nota curada, el contenido real de esa nota
    llega al prompt -- lookup determinístico, sin pasar por búsqueda."""
    triage_reference.ensure_reference_notes()
    project = tmp_path / "proj"
    project.mkdir()
    (project / "app.py").write_text("session.setAttribute('x', escapeHtml(param))\n", encoding="utf-8")
    finding = _finding(
        file="app.py", line=1, end_line=1,
        rule_id="java.lang.security.audit.tainted-session-from-http-request.tainted-session-from-http-request",
    )

    captured = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return _fake_response('{"verdict": "real", "reasoning": "el escape de HTML no mitiga trust boundary"}')

    monkeypatch.setattr(triage.client.chat.completions, "create", fake_create)

    await triage.triage_finding(project, finding)

    user_msg = captured["messages"][1]["content"]
    assert "CWE-501" in user_msg
    assert "NO mitiga" in user_msg
    assert "Referencia curada" in user_msg


@pytest.mark.anyio
async def test_triage_finding_omits_the_reference_for_a_category_without_a_curated_note(tmp_path, monkeypatch):
    triage_reference.ensure_reference_notes()
    project = tmp_path / "proj"
    project.mkdir()
    (project / "app.py").write_text("x = 1\n", encoding="utf-8")
    finding = _finding(
        file="app.py", line=1, end_line=1,
        rule_id="java.lang.security.audit.xss.no-direct-response-writer.no-direct-response-writer",
    )

    captured = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return _fake_response('{"verdict": "real", "reasoning": "x"}')

    monkeypatch.setattr(triage.client.chat.completions, "create", fake_create)

    await triage.triage_finding(project, finding)

    assert "Referencia curada" not in captured["messages"][1]["content"]


@pytest.mark.anyio
async def test_triage_finding_omits_the_reference_when_notes_were_never_created(tmp_path, monkeypatch):
    """Si nadie corrió ensure_reference_notes() todavía, el triage sigue
    funcionando exactamente como antes -- sin romper, sin referencia."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "app.py").write_text("x = 1\n", encoding="utf-8")
    finding = _finding(
        file="app.py", line=1, end_line=1,
        rule_id="java.lang.security.audit.tainted-session-from-http-request.tainted-session-from-http-request",
    )

    captured = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return _fake_response('{"verdict": "real", "reasoning": "x"}')

    monkeypatch.setattr(triage.client.chat.completions, "create", fake_create)

    await triage.triage_finding(project, finding)

    assert "Referencia curada" not in captured["messages"][1]["content"]


@pytest.mark.anyio
async def test_triage_findings_returns_new_findings_with_status_set(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "app.py").write_text("x = 1\n", encoding="utf-8")
    findings = [_finding(id="f1", line=1), _finding(id="f2", line=1, rule_id="other-rule")]

    responses = [
        '{"verdict": "real", "reasoning": "sin sanitizar"}',
        '{"verdict": "false_positive", "reasoning": "ya validado antes"}',
    ]

    async def fake_create(**kwargs):
        return _fake_response(responses.pop(0))

    monkeypatch.setattr(triage.client.chat.completions, "create", fake_create)

    triaged = await triage.triage_findings(project, findings)

    assert triaged[0].triage_status == "real"
    assert triaged[1].triage_status == "false_positive"
    assert triaged[1].triage_reasoning == "ya validado antes"
    # la lista original no se muto
    assert findings[0].triage_status is None


@pytest.mark.anyio
async def test_triage_findings_keeps_finding_as_real_when_the_model_call_fails(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "app.py").write_text("x = 1\n", encoding="utf-8")
    findings = [_finding(id="f1", line=1)]

    async def fake_create(**kwargs):
        raise RuntimeError("modelo no disponible")

    monkeypatch.setattr(triage.client.chat.completions, "create", fake_create)

    triaged = await triage.triage_findings(project, findings)

    assert triaged[0].triage_status == "real"
    assert "modelo no disponible" in triaged[0].triage_reasoning
