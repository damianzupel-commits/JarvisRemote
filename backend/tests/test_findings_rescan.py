"""Tests de `app/findings/rescan.py::merge_file_findings` -- la lógica pura de
"reemplazar los hallazgos de un archivo puntual, calculando qué se resolvió/
persiste/apareció" que comparten security/runner.py y quality/runner.py."""

from pathlib import Path

from app.findings.models import Finding, ScanResult
from app.findings.rescan import merge_file_findings


def _finding(file: str, line: int, severity: str, rule_id: str, tool: str = "semgrep") -> Finding:
    return Finding(
        id=f"{tool}-{file}-{line}-{rule_id}",
        tool=tool, file=file, line=line, end_line=None,
        severity=severity, rule_id=rule_id, message="msg",
    )


def test_no_previous_scan_everything_new():
    new_findings = [_finding("app.py", 1, "high", "r1")]

    result, resolved, persisting, brand_new = merge_file_findings(
        None, Path("/proj"), "app.py", new_findings, ["semgrep"], {},
    )

    assert resolved == []
    assert persisting == []
    assert [f.id for f in brand_new] == [new_findings[0].id]
    assert result.findings == new_findings


def test_finding_gone_after_rescan_is_resolved():
    old = ScanResult(
        root="/proj", scanned_at="t0", tools_run=["semgrep"], tools_skipped={},
        findings=[_finding("app.py", 1, "critical", "r1"), _finding("app.py", 2, "low", "r2")],
    )

    result, resolved, persisting, brand_new = merge_file_findings(
        old, Path("/proj"), "app.py", [], ["semgrep"], {},
    )

    assert {f.id for f in resolved} == {old.findings[0].id, old.findings[1].id}
    assert persisting == []
    assert brand_new == []
    assert result.findings == []


def test_finding_still_present_is_persisting():
    shared = _finding("app.py", 1, "critical", "r1")
    old = ScanResult(root="/proj", scanned_at="t0", tools_run=[], tools_skipped={}, findings=[shared])

    result, resolved, persisting, brand_new = merge_file_findings(
        old, Path("/proj"), "app.py", [shared], [], {},
    )

    assert resolved == []
    assert [f.id for f in persisting] == [shared.id]
    assert brand_new == []


def test_cascade_scenario_fixing_one_resolves_others():
    """El escenario que pidió el usuario: arreglar 1 hallazgo crítico también
    resuelve, de rebote, otros de menor severidad en el mismo archivo -- se
    detecta puramente porque sus ids ya no aparecen en el rescan, sin inferir
    causalidad."""
    critical = _finding("app.py", 10, "critical", "sql-injection")
    low1 = _finding("app.py", 11, "low", "unused-var")
    low2 = _finding("app.py", 12, "low", "unused-import")
    medium = _finding("app.py", 20, "medium", "other-issue")
    old = ScanResult(
        root="/proj", scanned_at="t0", tools_run=[], tools_skipped={},
        findings=[critical, low1, low2, medium],
    )

    # Después del fix, solo persiste el de severidad media (no relacionado).
    result, resolved, persisting, brand_new = merge_file_findings(
        old, Path("/proj"), "app.py", [medium], [], {},
    )

    assert {f.id for f in resolved} == {critical.id, low1.id, low2.id}
    assert [f.id for f in persisting] == [medium.id]
    assert brand_new == []


def test_other_files_findings_are_untouched():
    other_file_finding = _finding("other.py", 1, "high", "r9")
    app_finding = _finding("app.py", 1, "high", "r1")
    old = ScanResult(
        root="/proj", scanned_at="t0", tools_run=[], tools_skipped={},
        findings=[other_file_finding, app_finding],
    )

    result, resolved, persisting, brand_new = merge_file_findings(
        old, Path("/proj"), "app.py", [], [], {},
    )

    assert result.findings == [other_file_finding]
    assert [f.id for f in resolved] == [app_finding.id]


def test_new_finding_introduced_by_the_fix():
    old = ScanResult(root="/proj", scanned_at="t0", tools_run=[], tools_skipped={}, findings=[])
    new_finding = _finding("app.py", 5, "medium", "new-rule")

    result, resolved, persisting, brand_new = merge_file_findings(
        old, Path("/proj"), "app.py", [new_finding], [], {},
    )

    assert resolved == []
    assert persisting == []
    assert [f.id for f in brand_new] == [new_finding.id]


def test_tools_run_and_skipped_are_merged_with_previous():
    old = ScanResult(
        root="/proj", scanned_at="t0", tools_run=["semgrep"], tools_skipped={"bandit": "no python"},
        findings=[],
    )

    result, *_ = merge_file_findings(old, Path("/proj"), "app.py", [], ["bandit"], {"trivy": "not installed"})

    assert set(result.tools_run) == {"semgrep", "bandit"}
    assert result.tools_skipped == {"bandit": "no python", "trivy": "not installed"}
