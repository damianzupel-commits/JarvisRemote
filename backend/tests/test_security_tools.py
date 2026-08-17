"""Tests de las tools expuestas al LLM (`app/tools/security_scan.py`). Los
escáneres reales ya se prueban sin mockear en test_security_scanners.py; acá
se mockean `scanners.run_*` para probar de forma determinística la capa de
orquestación (runner), cache (store) y las tools en sí -- que es donde vive la
lógica propia de Jarvis, no la de Semgrep/Bandit."""

import shutil
import subprocess

import pytest

from app.codebase import store as codebase_store
from app.obsidian import vault
from app.quality import scanners as quality_scanners, store as quality_store
from app.security import scanners, store as security_store
from app.security import triage as security_triage
from app.security.models import Finding, ScanResult
from app.testing import store as test_store
from app.tools import security_scan


@pytest.fixture(autouse=True)
def _tmp_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(codebase_store.settings, "codebase_index_dir", str(tmp_path / "codebase_cache"))
    monkeypatch.setattr(security_store.settings, "security_scan_dir", str(tmp_path / "security_cache"))
    monkeypatch.setattr(quality_store.settings, "quality_scan_dir", str(tmp_path / "quality_cache"))
    monkeypatch.setattr(test_store.settings, "test_run_dir", str(tmp_path / "test_run_cache"))


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "app.py").write_text("print('hola')\n", encoding="utf-8")
    return root


def test_security_scan_project_aggregates_and_sorts_by_severity(project, monkeypatch):
    findings = [
        Finding(id="a", tool="semgrep", file="app.py", line=10, end_line=10, severity="low", rule_id="r1", message="low sev"),
        Finding(id="b", tool="semgrep", file="app.py", line=5, end_line=5, severity="critical", rule_id="r2", message="crit sev", cwe=["CWE-89"], owasp=["A03:2021"]),
    ]
    monkeypatch.setattr(scanners, "run_semgrep", lambda root: findings)
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: None)
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)

    result = security_scan.security_scan_project(str(project))

    assert result["total_findings"] == 2
    assert result["tools_run"] == ["semgrep"]
    assert "bandit" in result["tools_skipped"]
    assert result["findings"][0]["id"] == "b"  # critical primero
    assert result["findings"][1]["id"] == "a"
    assert result["findings_by_severity"] == {"low": 1, "critical": 1}


def test_security_scan_project_passes_python_files_to_bandit(project, monkeypatch):
    """Regresión: el indexador de Codebase marca los .py como language='Python'
    (con mayúscula) -- runner.scan_project tiene que filtrar por ese mismo
    valor exacto, si no Bandit nunca recibe archivos y se salta siempre (bug
    real encontrado al hacer dogfooding del propio repo)."""
    captured = {}

    def _run_bandit(root, python_files):
        captured["python_files"] = python_files
        return None

    monkeypatch.setattr(scanners, "run_semgrep", lambda root: [])
    monkeypatch.setattr(scanners, "run_bandit", _run_bandit)
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)

    security_scan.security_scan_project(str(project))

    assert captured["python_files"] == ["app.py"]


def test_security_scan_project_uses_cache_unless_refresh(project, monkeypatch):
    calls = {"n": 0}

    def _run(root):
        calls["n"] += 1
        return []

    monkeypatch.setattr(scanners, "run_semgrep", _run)
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: None)
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)

    security_scan.security_scan_project(str(project))
    security_scan.security_scan_project(str(project))
    assert calls["n"] == 1

    security_scan.security_scan_project(str(project), refresh=True)
    assert calls["n"] == 2


def test_security_get_finding_returns_code_context(project, monkeypatch):
    (project / "app.py").write_text("\n".join(f"line{i}" for i in range(1, 21)) + "\n", encoding="utf-8")
    finding = Finding(id="xyz", tool="bandit", file="app.py", line=10, end_line=10, severity="high", rule_id="B608", message="sqli")
    monkeypatch.setattr(scanners, "run_semgrep", lambda root: [])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: [finding])
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)

    security_scan.security_scan_project(str(project))
    result = security_scan.security_get_finding(str(project), "xyz", context_lines=2)

    assert result["finding"]["id"] == "xyz"
    context_lines = {c["line"]: c["text"] for c in result["code_context"]}
    assert context_lines[10] == "line10"
    assert set(context_lines) == {8, 9, 10, 11, 12}


def test_security_get_finding_raises_for_unknown_id(project):
    with pytest.raises(ValueError):
        security_scan.security_get_finding(str(project), "no-existe")


def test_security_scan_project_file_filter_returns_only_that_files_findings(project, monkeypatch):
    """Bug real (2026-08-03): en un proyecto con muchos hallazgos, el resumen
    global (recortado por severidad + tamaño de mensaje, ver app/agent.py::
    _cap_tool_result) puede dejar afuera el hallazgo puntual de severidad media/
    baja que el usuario pidió auditar en un archivo específico -- el modelo
    real (jarvis-text-v2) se topó justo con esto: security_scan_project no
    mostró el B608 de introduction/views.py:158 en el top recortado y el modelo
    no tenía forma de pedir ESE archivo puntual. 'file' resuelve ese gap."""
    findings = [
        Finding(id="a", tool="bandit", file="introduction/views.py", line=158, end_line=158, severity="medium", rule_id="B608", message="sqli"),
        Finding(id="b", tool="trivy", file="requirements.txt", line=1, end_line=None, severity="critical", rule_id="CVE-1", message="otra cosa"),
    ]
    monkeypatch.setattr(scanners, "run_semgrep", lambda root: [])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: findings[:1])
    monkeypatch.setattr(scanners, "run_trivy", lambda root: findings[1:])

    result = security_scan.security_scan_project(str(project), file="introduction/views.py")

    assert result["file"] == "introduction/views.py"
    assert [f["id"] for f in result["findings"]] == ["a"]
    assert result["findings_omitted"] == 0
    # el filtro no toca el resumen agregado -- sigue reflejando TODO el proyecto
    assert result["total_findings"] == 2
    assert result["findings_by_severity"] == {"medium": 1, "critical": 1}


def test_security_scan_project_file_filter_normalizes_windows_separators(project, monkeypatch):
    finding = Finding(id="a", tool="bandit", file="introduction/views.py", line=158, end_line=158, severity="medium", rule_id="B608", message="sqli")
    monkeypatch.setattr(scanners, "run_semgrep", lambda root: [])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: [finding])
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)

    result = security_scan.security_scan_project(str(project), file="introduction\\views.py")

    assert result["file"] == "introduction/views.py"
    assert [f["id"] for f in result["findings"]] == ["a"]


def test_security_scan_project_file_filter_empty_when_no_findings_in_file(project, monkeypatch):
    finding = Finding(id="a", tool="bandit", file="other.py", line=1, end_line=1, severity="low", rule_id="X", message="x")
    monkeypatch.setattr(scanners, "run_semgrep", lambda root: [])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: [finding])
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)

    result = security_scan.security_scan_project(str(project), file="clean.py")

    assert result["findings"] == []
    assert result["findings_omitted"] == 0


def test_security_get_finding_by_file_and_rule_id(project, monkeypatch):
    # Caso real: en vez de pasar el finding_id exacto (hash interno, fácil de
    # citar mal de memoria), se identifica el hallazgo por file+rule_id.
    finding = Finding(id="abc123", tool="bandit", file="app.py", line=10, end_line=10, severity="medium", rule_id="B608", message="sqli")
    monkeypatch.setattr(scanners, "run_semgrep", lambda root: [])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: [finding])
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)
    monkeypatch.setattr(vault, "search_notes", lambda query, limit=5: [])

    security_scan.security_scan_project(str(project))
    result = security_scan.security_get_finding(str(project), file="app.py", rule_id="B608")

    assert result["finding"]["id"] == "abc123"


def test_security_get_finding_disambiguates_with_line(project, monkeypatch):
    # Caso real: pygoat tenía DOS hallazgos B608 en el mismo archivo, líneas
    # 158 y 864 -- sin 'line' para desambiguar, no hay que adivinar cuál es.
    (project / "app.py").write_text("\n".join(f"line{i}" for i in range(1, 900)) + "\n", encoding="utf-8")
    f1 = Finding(id="f1", tool="bandit", file="app.py", line=158, end_line=158, severity="medium", rule_id="B608", message="sqli 1")
    f2 = Finding(id="f2", tool="bandit", file="app.py", line=864, end_line=864, severity="medium", rule_id="B608", message="sqli 2")
    monkeypatch.setattr(scanners, "run_semgrep", lambda root: [])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: [f1, f2])
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)
    monkeypatch.setattr(vault, "search_notes", lambda query, limit=5: [])

    security_scan.security_scan_project(str(project))

    with pytest.raises(ValueError):
        security_scan.security_get_finding(str(project), file="app.py", rule_id="B608")

    result = security_scan.security_get_finding(str(project), file="app.py", rule_id="B608", line=864)
    assert result["finding"]["id"] == "f2"


def test_security_get_finding_includes_obsidian_notes(project, monkeypatch):
    # Bug real 2026-08-09: obsidian_search_notes nunca se llamó en una corrida
    # completa de audit+fix -- ahora security_get_finding lo dispara solo.
    finding = Finding(
        id="abc", tool="bandit", file="app.py", line=10, end_line=10, severity="medium",
        rule_id="B608", message="sqli", cwe=["CWE-89"], owasp=["A03:2021"],
    )
    monkeypatch.setattr(scanners, "run_semgrep", lambda root: [])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: [finding])
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)

    captured_query = {}

    class _FakeNote:
        title = "SQL Injection 101"
        tags = ["seguridad", "owasp"]
        content = "x" * 1000  # más largo que el preview -- debe truncarse

    def _fake_search(query, limit=5):
        captured_query["query"] = query
        captured_query["limit"] = limit
        return [_FakeNote()]

    monkeypatch.setattr(vault, "search_notes", _fake_search)

    security_scan.security_scan_project(str(project))
    result = security_scan.security_get_finding(str(project), "abc")

    assert "B608" in captured_query["query"]
    assert "CWE-89" in captured_query["query"]
    assert result["obsidian_notes"][0]["title"] == "SQL Injection 101"
    assert len(result["obsidian_notes"][0]["content_preview"]) == 600
    assert result["obsidian_notes"][0]["truncated"] is True


def test_security_get_finding_obsidian_failure_does_not_break_result(project, monkeypatch):
    finding = Finding(id="abc", tool="bandit", file="app.py", line=10, end_line=10, severity="medium", rule_id="B608", message="sqli")
    monkeypatch.setattr(scanners, "run_semgrep", lambda root: [])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: [finding])
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)

    def _boom(query, limit=5):
        raise RuntimeError("LM Studio caído")

    monkeypatch.setattr(vault, "search_notes", _boom)

    security_scan.security_scan_project(str(project))
    result = security_scan.security_get_finding(str(project), "abc")

    assert result["finding"]["id"] == "abc"
    assert result["obsidian_notes"] == []


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=15)


@pytest.fixture
def git_project(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "app.py").write_text(
        "def login(name, password):\n"
        "    sql_query = \"SELECT * FROM users WHERE user='\" + name + \"'\"\n"
        "    return sql_query\n",
        encoding="utf-8",
    )
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial")
    return root


pytestmark_git = pytest.mark.skipif(shutil.which("git") is None, reason="git no está instalado")

_OLD_SNIPPET = "sql_query = \"SELECT * FROM users WHERE user='\" + name + \"'\""
_NEW_SNIPPET = "sql_query = None  # TODO: usar el ORM"


@pytestmark_git
def test_security_audit_find_fix_verify_applies_commits_and_confirms_resolution(git_project, monkeypatch):
    finding = Finding(id="f1", tool="bandit", file="app.py", line=2, end_line=2, severity="medium", rule_id="B608", message="sqli")
    monkeypatch.setattr(scanners, "run_semgrep", lambda root, scan_target=None: [])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: [finding])
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)
    monkeypatch.setattr(quality_scanners, "run_ruff", lambda root, python_files: None)
    monkeypatch.setattr(quality_scanners, "run_mypy", lambda root, python_files: None)

    security_scan.security_scan_project(str(git_project))  # cachea el hallazgo original

    # Tras el fix, bandit ya no encuentra el B608 -- se "resolvió" de verdad.
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: [])

    result = security_scan.security_audit_find_fix_verify(
        path=str(git_project), file="app.py", rule_id="B608",
        old_snippet=_OLD_SNIPPET, new_snippet=_NEW_SNIPPET,
        commit_message="fix: SQL injection en app.py:2",
    )

    assert result["applied"] is True
    assert result["committed"] is True
    assert result["commit_hash"]
    assert result["finding_resolved"] is True
    assert (git_project / "app.py").read_text(encoding="utf-8") == (
        "def login(name, password):\n" "    sql_query = None  # TODO: usar el ORM\n" "    return sql_query\n"
    )
    # commit real en git, no solo en el archivo
    log = _git(git_project, "log", "--oneline", "-1")
    assert "fix: SQL injection" in log.stdout
    # git_project no tiene ninguna suite de tests real -- 'tests' debe decirlo
    # explícitamente en vez de quedar ausente o marcado como si hubiera pasado.
    assert result["tests"]["detected"] is False


@pytestmark_git
def test_security_audit_find_fix_verify_runs_the_real_test_suite_after_the_fix(git_project, monkeypatch):
    """Paso de 'testear real' agregado 2026-08-10 -- si el proyecto SÍ tiene una
    suite de tests real, security_audit_find_fix_verify la corre de verdad
    (sin mockear pytest) después de aplicar y commitear el fix, y el resultado
    refleja si quedó en verde."""
    (git_project / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (git_project / "tests").mkdir()
    (git_project / "tests" / "test_login.py").write_text(
        "from app import login\n\ndef test_login_runs_without_error():\n    login('a', 'b')\n",
        encoding="utf-8",
    )
    _git(git_project, "add", "-A")
    _git(git_project, "commit", "-q", "-m", "add real test suite")

    finding = Finding(id="f1", tool="bandit", file="app.py", line=2, end_line=2, severity="medium", rule_id="B608", message="sqli")
    monkeypatch.setattr(scanners, "run_semgrep", lambda root, scan_target=None: [])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: [finding])
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)
    monkeypatch.setattr(quality_scanners, "run_ruff", lambda root, python_files: None)
    monkeypatch.setattr(quality_scanners, "run_mypy", lambda root, python_files: None)
    security_scan.security_scan_project(str(git_project))
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: [])

    result = security_scan.security_audit_find_fix_verify(
        path=str(git_project), file="app.py", rule_id="B608",
        old_snippet=_OLD_SNIPPET, new_snippet=_NEW_SNIPPET,
        commit_message="fix: SQL injection en app.py:2",
    )

    assert result["tests"]["detected"] is True
    assert result["tests"]["language"] == "Python"
    assert result["tests"]["passed"] is True
    assert "1 passed" in result["tests"]["stdout"]


@pytestmark_git
def test_security_audit_find_fix_verify_finding_not_resolved_if_scanner_still_flags_it(git_project, monkeypatch):
    finding = Finding(id="f1", tool="bandit", file="app.py", line=2, end_line=2, severity="medium", rule_id="B608", message="sqli")
    monkeypatch.setattr(scanners, "run_semgrep", lambda root, scan_target=None: [])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: [finding])
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)
    monkeypatch.setattr(quality_scanners, "run_ruff", lambda root, python_files: None)
    monkeypatch.setattr(quality_scanners, "run_mypy", lambda root, python_files: None)

    security_scan.security_scan_project(str(git_project))
    # el rescan post-fix SIGUE encontrando el mismo B608 (fix cosmético que no
    # arregló nada de verdad) -- finding_resolved tiene que reflejar eso.

    result = security_scan.security_audit_find_fix_verify(
        path=str(git_project), file="app.py", rule_id="B608",
        old_snippet=_OLD_SNIPPET, new_snippet=_NEW_SNIPPET,
        commit_message="fix cosmético",
    )

    assert result["applied"] is True
    assert result["finding_resolved"] is False


def test_security_audit_find_fix_verify_raises_when_finding_not_found(project):
    with pytest.raises(ValueError):
        security_scan.security_audit_find_fix_verify(
            path=str(project), file="app.py", rule_id="B608",
            old_snippet="x", new_snippet="y", commit_message="fix",
        )


@pytestmark_git
def test_security_audit_find_fix_verify_does_not_commit_if_snippet_mismatches(git_project, monkeypatch):
    finding = Finding(id="f1", tool="bandit", file="app.py", line=2, end_line=2, severity="medium", rule_id="B608", message="sqli")
    monkeypatch.setattr(scanners, "run_semgrep", lambda root, scan_target=None: [])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: [finding])
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)

    security_scan.security_scan_project(str(git_project))
    head_before = _git(git_project, "rev-parse", "HEAD").stdout

    with pytest.raises(Exception):
        security_scan.security_audit_find_fix_verify(
            path=str(git_project), file="app.py", rule_id="B608",
            old_snippet="esto no aparece en el archivo", new_snippet="y",
            commit_message="fix",
        )

    assert _git(git_project, "rev-parse", "HEAD").stdout == head_before


def test_security_get_finding_error_lists_real_candidate_lines(project, monkeypatch):
    # Bug real 2026-08-09 (round 2): el modelo probó líneas inventadas (42,
    # 100, 142...) 2-3 veces antes de acertar porque el error anterior no
    # decía CUÁLES eran las líneas reales -- ahora el mensaje las lista.
    f1 = Finding(id="a", tool="bandit", file="app.py", line=158, end_line=158, severity="medium", rule_id="B608", message="sqli 1")
    f2 = Finding(id="b", tool="bandit", file="app.py", line=864, end_line=864, severity="medium", rule_id="B608", message="sqli 2")
    monkeypatch.setattr(scanners, "run_semgrep", lambda root: [])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: [f1, f2])
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)

    security_scan.security_scan_project(str(project))

    with pytest.raises(ValueError, match=r"158.*864|864.*158"):
        security_scan.security_get_finding(str(project), file="app.py", rule_id="B608", line=42)


def test_security_audit_find_fix_verify_error_lists_real_candidate_lines(project, monkeypatch):
    f1 = Finding(id="a", tool="bandit", file="app.py", line=158, end_line=158, severity="medium", rule_id="B608", message="sqli 1")
    f2 = Finding(id="b", tool="bandit", file="app.py", line=864, end_line=864, severity="medium", rule_id="B608", message="sqli 2")
    monkeypatch.setattr(scanners, "run_semgrep", lambda root: [])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: [f1, f2])
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)

    security_scan.security_scan_project(str(project))

    with pytest.raises(ValueError, match=r"158.*864|864.*158"):
        security_scan.security_audit_find_fix_verify(
            path=str(project), file="app.py", rule_id="B608", line=42,
            old_snippet="x", new_snippet="y", commit_message="fix",
        )


def test_security_get_finding_tolerates_wrong_line_when_unambiguous(project, monkeypatch):
    finding = Finding(id="a", tool="bandit", file="app.py", line=158, end_line=158, severity="medium", rule_id="B608", message="sqli")
    monkeypatch.setattr(scanners, "run_semgrep", lambda root: [])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: [finding])
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)
    monkeypatch.setattr(vault, "search_notes", lambda query, limit=5: [])

    security_scan.security_scan_project(str(project))
    # un solo B608 en el archivo -- la línea equivocada no debería bloquearlo.
    result = security_scan.security_get_finding(str(project), file="app.py", rule_id="B608", line=42)
    assert result["finding"]["id"] == "a"
    assert result["finding"]["line"] == 158


@pytestmark_git
def test_security_audit_find_fix_verify_rejects_target_drift_without_confirm(git_project, monkeypatch):
    # Caso real: el modelo pidió arreglar B608, no lo encontró a la primera,
    # y terminó aplicando el fix sobre un hallazgo DISTINTO (B602) sin
    # avisar. Si declara qué pidió el usuario (requested_rule_id) y el
    # rule_id que está por aplicar no coincide, la tool tiene que rechazarlo
    # SIN escribir nada -- no silenciosamente sustituir el objetivo.
    finding = Finding(id="f1", tool="bandit", file="app.py", line=2, end_line=2, severity="high", rule_id="B602", message="shell=True")
    monkeypatch.setattr(scanners, "run_semgrep", lambda root, scan_target=None: [])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: [finding])
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)

    security_scan.security_scan_project(str(git_project))
    head_before = _git(git_project, "rev-parse", "HEAD").stdout

    with pytest.raises(ValueError, match="B608"):
        security_scan.security_audit_find_fix_verify(
            path=str(git_project), file="app.py", rule_id="B602",
            old_snippet=_OLD_SNIPPET, new_snippet=_NEW_SNIPPET, commit_message="fix",
            requested_rule_id="B608",
        )

    # nada se escribió ni commiteó -- el rechazo pasó ANTES de tocar el archivo
    assert _git(git_project, "rev-parse", "HEAD").stdout == head_before


@pytestmark_git
def test_security_audit_find_fix_verify_allows_target_drift_with_explicit_confirm(git_project, monkeypatch):
    # Mismo caso, pero con confirm_target_change=true -- el desvío es
    # intencional y declarado, se deja pasar.
    finding = Finding(id="f1", tool="bandit", file="app.py", line=2, end_line=2, severity="high", rule_id="B602", message="shell=True")
    monkeypatch.setattr(scanners, "run_semgrep", lambda root, scan_target=None: [])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: [])  # ya no aparece tras el fix
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)
    monkeypatch.setattr(quality_scanners, "run_ruff", lambda root, python_files: None)
    monkeypatch.setattr(quality_scanners, "run_mypy", lambda root, python_files: None)

    # sembrar la cache con el hallazgo real usando bandit temporalmente
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: [finding])
    security_scan.security_scan_project(str(git_project))
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: [])

    result = security_scan.security_audit_find_fix_verify(
        path=str(git_project), file="app.py", rule_id="B602",
        old_snippet=_OLD_SNIPPET, new_snippet=_NEW_SNIPPET, commit_message="fix",
        requested_rule_id="B608", confirm_target_change=True,
    )

    assert result["applied"] is True
    assert result["committed"] is True


def test_security_audit_find_fix_verify_no_drift_when_target_matches_request(project, monkeypatch):
    finding = Finding(id="f1", tool="bandit", file="app.py", line=2, end_line=2, severity="medium", rule_id="B608", message="sqli")
    monkeypatch.setattr(scanners, "run_semgrep", lambda root: [])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: [finding])
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)
    security_scan.security_scan_project(str(project))

    # mismo rule_id que lo pedido -- no debería llegar a la excepción de
    # desvío (falla más adelante, en apply_fix, porque 'project' no es un
    # repo git -- pero eso confirma que el chequeo de fidelidad NO se disparó).
    with pytest.raises(Exception) as exc_info:
        security_scan.security_audit_find_fix_verify(
            path=str(project), file="app.py", rule_id="B608",
            old_snippet="x", new_snippet="y", commit_message="fix",
            requested_rule_id="B608",
        )
    assert "Ibas a aplicar el fix sobre" not in str(exc_info.value)


# ------------------------------------------------------------- cascada (reparación masiva)

def test_cascade_key_groups_trivy_findings_by_file_and_package():
    a = Finding(id="a", tool="trivy", file="requirements.txt", line=1, end_line=None, severity="critical", rule_id="CVE-1", message="django 3.2.18: SQLi")
    b = Finding(id="b", tool="trivy", file="requirements.txt", line=1, end_line=None, severity="high", rule_id="CVE-2", message="django 3.2.18: otro CVE")
    c = Finding(id="c", tool="trivy", file="requirements.txt", line=1, end_line=None, severity="high", rule_id="CVE-3", message="pillow 9.4.0: otro paquete")
    assert security_scan._cascade_key(a) == security_scan._cascade_key(b)  # mismo paquete -- mismo grupo
    assert security_scan._cascade_key(a) != security_scan._cascade_key(c)  # paquete distinto -- grupo distinto


def test_cascade_key_groups_code_pattern_findings_by_rule_id_project_wide():
    a = Finding(id="a", tool="semgrep", file="a.py", line=1, end_line=1, severity="high", rule_id="missing-user", message="x")
    b = Finding(id="b", tool="semgrep", file="b.py", line=1, end_line=1, severity="high", rule_id="missing-user", message="x")
    # mismo rule_id, ARCHIVOS DISTINTOS -- igual es el mismo grupo (causa raíz compartida).
    assert security_scan._cascade_key(a) == security_scan._cascade_key(b)


def test_cascade_sizes_counts_group_membership():
    findings = [
        Finding(id="a", tool="trivy", file="req.txt", line=1, end_line=None, severity="critical", rule_id="CVE-1", message="django 3.2.18: x"),
        Finding(id="b", tool="trivy", file="req.txt", line=1, end_line=None, severity="high", rule_id="CVE-2", message="django 3.2.18: y"),
        Finding(id="c", tool="bandit", file="a.py", line=1, end_line=1, severity="low", rule_id="B101", message="z"),
    ]
    sizes = security_scan._cascade_sizes(findings)
    assert sizes[security_scan._cascade_key(findings[0])] == 2  # los dos de django
    assert sizes[security_scan._cascade_key(findings[2])] == 1  # el bandit, solo


def test_security_scan_project_prioritizes_cascade_size_over_severity(project, monkeypatch):
    # Caso real que motivó esto: dos CVEs críticos de django (cascade_size=2)
    # tienen que aparecer ANTES que un hallazgo aislado de mayor severidad
    # nominal pero cascade_size=1 -- el orden prioriza "resolver más terreno
    # por fix aplicado", no severidad pura.
    isolated_critical = Finding(id="iso", tool="bandit", file="a.py", line=1, end_line=1, severity="critical", rule_id="B999", message="aislado")
    django_1 = Finding(id="d1", tool="trivy", file="requirements.txt", line=1, end_line=None, severity="high", rule_id="CVE-1", message="django 3.2.18: uno")
    django_2 = Finding(id="d2", tool="trivy", file="requirements.txt", line=1, end_line=None, severity="high", rule_id="CVE-2", message="django 3.2.18: dos")
    monkeypatch.setattr(scanners, "run_semgrep", lambda root: [])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: [isolated_critical])
    monkeypatch.setattr(scanners, "run_trivy", lambda root: [django_1, django_2])

    result = security_scan.security_scan_project(str(project))

    ids_in_order = [f["id"] for f in result["findings"]]
    assert ids_in_order.index("d1") < ids_in_order.index("iso")
    assert ids_in_order.index("d2") < ids_in_order.index("iso")


def test_security_scan_project_findings_include_cascade_fields(project, monkeypatch):
    django_1 = Finding(id="d1", tool="trivy", file="requirements.txt", line=1, end_line=None, severity="high", rule_id="CVE-1", message="django 3.2.18: uno")
    django_2 = Finding(id="d2", tool="trivy", file="requirements.txt", line=1, end_line=None, severity="high", rule_id="CVE-2", message="django 3.2.18: dos")
    monkeypatch.setattr(scanners, "run_semgrep", lambda root: [])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: None)
    monkeypatch.setattr(scanners, "run_trivy", lambda root: [django_1, django_2])

    result = security_scan.security_scan_project(str(project))

    by_id = {f["id"]: f for f in result["findings"]}
    assert by_id["d1"]["cascade_size"] == 2
    assert by_id["d1"]["cascade_group"] == by_id["d2"]["cascade_group"]


def test_security_scan_project_file_filter_also_includes_cascade_fields(project, monkeypatch):
    finding = Finding(id="a", tool="bandit", file="app.py", line=1, end_line=1, severity="low", rule_id="B101", message="x")
    monkeypatch.setattr(scanners, "run_semgrep", lambda root: [])
    monkeypatch.setattr(scanners, "run_bandit", lambda root, python_files: [finding])
    monkeypatch.setattr(scanners, "run_trivy", lambda root: None)

    result = security_scan.security_scan_project(str(project), file="app.py")

    assert result["findings"][0]["cascade_size"] == 1


def test_security_scan_project_excludes_findings_triaged_as_false_positive(project):
    real_finding = Finding(id="a", tool="semgrep", file="app.py", line=5, end_line=5, severity="high", rule_id="r1", message="real")
    fp_finding = Finding(
        id="b", tool="semgrep", file="app.py", line=10, end_line=10, severity="high", rule_id="r2", message="fp",
        triage_status="false_positive", triage_reasoning="usa PreparedStatement",
    )
    security_store.save_scan(ScanResult(
        root=str(project), scanned_at="x", tools_run=["semgrep"], tools_skipped={}, findings=[real_finding, fp_finding],
    ))

    result = security_scan.security_scan_project(str(project))

    assert result["total_findings"] == 1
    assert result["findings"][0]["id"] == "a"
    assert result["findings_by_severity"] == {"high": 1}
    assert "1 hallazgo(s) más" in result["triaged_false_positives"]


def test_security_scan_project_shows_no_triage_message_when_nothing_was_triaged(project):
    finding = Finding(id="a", tool="semgrep", file="app.py", line=5, end_line=5, severity="high", rule_id="r1", message="real")
    security_store.save_scan(ScanResult(root=str(project), scanned_at="x", tools_run=["semgrep"], tools_skipped={}, findings=[finding]))

    result = security_scan.security_scan_project(str(project))

    assert "triaged_false_positives" not in result


@pytest.mark.anyio
async def test_security_triage_findings_updates_the_cached_scan(project, monkeypatch):
    findings = [
        Finding(id="a", tool="semgrep", file="app.py", line=5, end_line=5, severity="high", rule_id="r1", message="m1"),
        Finding(id="b", tool="semgrep", file="app.py", line=10, end_line=10, severity="high", rule_id="r2", message="m2"),
    ]
    security_store.save_scan(ScanResult(root=str(project), scanned_at="x", tools_run=["semgrep"], tools_skipped={}, findings=findings))

    async def fake_triage_findings(root, pending):
        return [
            Finding(**{**f.to_dict(), "triage_status": "false_positive" if f.id == "b" else "real", "triage_reasoning": "x"})
            for f in pending
        ]

    monkeypatch.setattr(security_triage, "triage_findings", fake_triage_findings)

    result = await security_scan.security_triage_findings(str(project))

    assert result["triaged_now"] == 2
    assert result["reclassified_as_real"] == 1
    assert result["reclassified_as_false_positive"] == 1
    assert result["still_pending"] == 0
    assert result["false_positives"][0]["rule_id"] == "r2"

    saved = security_store.load_scan(project)
    by_id = {f.id: f for f in saved.findings}
    assert by_id["a"].triage_status == "real"
    assert by_id["b"].triage_status == "false_positive"


@pytest.mark.anyio
async def test_security_triage_findings_raises_without_a_prior_scan(project):
    with pytest.raises(ValueError):
        await security_scan.security_triage_findings(str(project))


@pytest.mark.anyio
async def test_security_triage_findings_skips_already_triaged_unless_forced(project, monkeypatch):
    already = Finding(id="a", tool="semgrep", file="app.py", line=5, end_line=5, severity="high", rule_id="r1", message="m1", triage_status="real", triage_reasoning="ya revisado")
    pending = Finding(id="b", tool="semgrep", file="app.py", line=10, end_line=10, severity="high", rule_id="r2", message="m2")
    security_store.save_scan(ScanResult(root=str(project), scanned_at="x", tools_run=["semgrep"], tools_skipped={}, findings=[already, pending]))

    calls = []

    async def fake_triage_findings(root, findings):
        calls.append([f.id for f in findings])
        return [Finding(**{**f.to_dict(), "triage_status": "real", "triage_reasoning": "x"}) for f in findings]

    monkeypatch.setattr(security_triage, "triage_findings", fake_triage_findings)

    result = await security_scan.security_triage_findings(str(project))
    assert calls == [["b"]]  # solo el pendiente
    assert result["triaged_now"] == 1

    calls.clear()
    await security_scan.security_triage_findings(str(project), force=True)
    assert calls == [["a", "b"]]  # con force, los dos


@pytest.mark.anyio
async def test_security_triage_findings_respects_limit(project, monkeypatch):
    findings = [
        Finding(id=str(i), tool="semgrep", file="app.py", line=i, end_line=i, severity="high", rule_id="r", message="m")
        for i in range(5)
    ]
    security_store.save_scan(ScanResult(root=str(project), scanned_at="x", tools_run=["semgrep"], tools_skipped={}, findings=findings))

    async def fake_triage_findings(root, pending):
        return [Finding(**{**f.to_dict(), "triage_status": "real", "triage_reasoning": "x"}) for f in pending]

    monkeypatch.setattr(security_triage, "triage_findings", fake_triage_findings)

    result = await security_scan.security_triage_findings(str(project), limit=2)

    assert result["triaged_now"] == 2
    assert result["still_pending"] == 3
