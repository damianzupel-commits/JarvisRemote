"""Tests de app.findings.models.resolve_finding -- la búsqueda robusta de un
hallazgo puntual que reemplaza depender de que el LLM cite un finding_id (hash
interno) de memoria. Ver el docstring de la función para el bug real que la
motivó: el modelo alucinó un finding_id inexistente dos veces seguidas para
el mismo hallazgo real (B608 en pygoat)."""

from app.findings.models import Finding, candidate_lines, resolve_finding


def _finding(id_, file="app.py", line=10, rule_id="B608") -> Finding:
    return Finding(id=id_, tool="bandit", file=file, line=line, end_line=line, severity="medium", rule_id=rule_id, message="sqli")


def test_resolve_finding_by_exact_id():
    findings = [_finding("a"), _finding("b", line=20)]
    assert resolve_finding(findings, finding_id="b") is findings[1]


def test_resolve_finding_falls_back_when_id_unknown():
    # el caso real: el modelo pasa un finding_id que no existe -- en vez de
    # devolver None de una, intenta con file+rule_id si se pasaron también.
    findings = [_finding("real-id")]
    result = resolve_finding(findings, finding_id="id-alucinado", file="app.py", rule_id="B608")
    assert result is findings[0]


def test_resolve_finding_by_file_and_rule_id():
    findings = [_finding("a", file="other.py"), _finding("b", file="app.py")]
    assert resolve_finding(findings, file="app.py", rule_id="B608") is findings[1]


def test_resolve_finding_disambiguates_with_line():
    # caso real: dos hallazgos con la misma regla en el mismo archivo,
    # distinta línea (dos B608 en introduction/views.py de pygoat).
    findings = [_finding("a", line=158), _finding("b", line=864)]
    assert resolve_finding(findings, file="app.py", rule_id="B608", line=864) is findings[1]


def test_resolve_finding_ambiguous_without_line_returns_none():
    findings = [_finding("a", line=158), _finding("b", line=864)]
    assert resolve_finding(findings, file="app.py", rule_id="B608") is None


def test_resolve_finding_no_match_returns_none():
    findings = [_finding("a")]
    assert resolve_finding(findings, file="nope.py", rule_id="B608") is None
    assert resolve_finding(findings, finding_id="nope") is None


def test_resolve_finding_requires_both_file_and_rule_id():
    findings = [_finding("a")]
    assert resolve_finding(findings, file="app.py") is None
    assert resolve_finding(findings, rule_id="B608") is None


def test_resolve_finding_tolerates_wrong_line_when_unambiguous():
    # Bug real 2026-08-09 (round 2): en las 3 corridas del caso B608 en
    # pygoat, el modelo erró la línea (la inventó) 2-3 de cada 3 intentos.
    # Si SOLO hay un hallazgo real para (file, rule_id), una línea
    # equivocada no debería bloquear el resultado -- el resto del pedido
    # (file+rule_id) ya identifica sin ambigüedad de qué hallazgo se trata.
    findings = [_finding("a", line=158)]
    assert resolve_finding(findings, file="app.py", rule_id="B608", line=42) is findings[0]


def test_resolve_finding_does_not_guess_when_wrong_line_and_ambiguous():
    # Si hay DOS candidatos reales y la línea pedida no matchea ninguno, no
    # hay forma segura de elegir -- se mantiene None (no se adivina).
    findings = [_finding("a", line=158), _finding("b", line=864)]
    assert resolve_finding(findings, file="app.py", rule_id="B608", line=42) is None


def test_resolve_finding_exact_line_wins_even_with_other_candidates():
    findings = [_finding("a", line=158), _finding("b", line=864)]
    assert resolve_finding(findings, file="app.py", rule_id="B608", line=158) is findings[0]


def test_candidate_lines_returns_sorted_unique_lines():
    findings = [
        _finding("a", file="app.py", line=864, rule_id="B608"),
        _finding("b", file="app.py", line=158, rule_id="B608"),
        _finding("c", file="app.py", line=1, rule_id="F401"),  # otra regla, no cuenta
        _finding("d", file="other.py", line=5, rule_id="B608"),  # otro archivo, no cuenta
    ]
    assert candidate_lines(findings, file="app.py", rule_id="B608") == [158, 864]


def test_candidate_lines_empty_when_no_match():
    findings = [_finding("a", file="app.py", line=1, rule_id="B608")]
    assert candidate_lines(findings, file="nope.py", rule_id="B608") == []
