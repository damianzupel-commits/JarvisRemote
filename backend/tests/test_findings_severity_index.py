from app.findings import severity_index
from app.findings.models import Finding, ScanResult
from app.quality import store as quality_store
from app.security import store as security_store


def _finding(file: str, severity: str, tool: str = "semgrep", rule_id: str = "rule", line: int = 1) -> Finding:
    return Finding(
        id=f"{tool}-{file}-{line}-{rule_id}",
        tool=tool,
        file=file,
        line=line,
        end_line=None,
        severity=severity,
        rule_id=rule_id,
        message="hallazgo de prueba",
    )


def test_no_cached_scans_means_no_files_and_not_scanned(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()

    risk = severity_index.build_file_risk_index(root)

    assert risk["files"] == {}
    assert risk["security_scanned"] is False
    assert risk["quality_scanned"] is False
    assert risk["security_scanned_at"] is None
    assert risk["quality_scanned_at"] is None


def test_groups_findings_by_file_keeping_max_severity(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    root.mkdir()
    monkeypatch.setattr(security_store.settings, "security_scan_dir", str(tmp_path / "sec"))

    security_store.save_scan(
        ScanResult(
            root=str(root.resolve()),
            scanned_at="2026-07-29T00:00:00+00:00",
            tools_run=["semgrep"],
            tools_skipped={},
            findings=[
                _finding("app/main.py", "low", rule_id="r1"),
                _finding("app/main.py", "critical", rule_id="r2"),
                _finding("app/utils.py", "medium", rule_id="r3"),
            ],
        )
    )

    risk = severity_index.build_file_risk_index(root)

    assert risk["files"]["app/main.py"]["severity"] == "critical"
    assert risk["files"]["app/main.py"]["finding_count"] == 2
    assert risk["files"]["app/utils.py"]["severity"] == "medium"
    assert risk["security_scanned"] is True
    assert risk["quality_scanned"] is False


def test_combines_security_and_quality_scans_for_the_same_file(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    root.mkdir()
    monkeypatch.setattr(security_store.settings, "security_scan_dir", str(tmp_path / "sec"))
    monkeypatch.setattr(quality_store.settings, "quality_scan_dir", str(tmp_path / "qual"))

    security_store.save_scan(
        ScanResult(
            root=str(root.resolve()),
            scanned_at="2026-07-29T00:00:00+00:00",
            tools_run=["bandit"],
            tools_skipped={},
            findings=[_finding("app/main.py", "medium", tool="bandit", rule_id="b1")],
        )
    )
    quality_store.save_scan(
        ScanResult(
            root=str(root.resolve()),
            scanned_at="2026-07-29T00:05:00+00:00",
            tools_run=["ruff"],
            tools_skipped={},
            findings=[_finding("app/main.py", "high", tool="ruff", rule_id="q1")],
        )
    )

    risk = severity_index.build_file_risk_index(root)

    assert risk["files"]["app/main.py"]["severity"] == "high"
    assert risk["files"]["app/main.py"]["finding_count"] == 2
    assert risk["security_scanned"] is True
    assert risk["quality_scanned"] is True
    assert risk["security_scanned_at"] == "2026-07-29T00:00:00+00:00"
    assert risk["quality_scanned_at"] == "2026-07-29T00:05:00+00:00"
