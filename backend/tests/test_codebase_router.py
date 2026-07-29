import pytest
from fastapi.testclient import TestClient

from app.codebase import store
from app.config import settings
from app.findings.models import Finding, ScanResult
from app.main import app
from app.quality import store as quality_store
from app.security import store as security_store

client = TestClient(app)
AUTH = {"Authorization": f"Bearer {settings.api_key}"}


@pytest.fixture(autouse=True)
def _tmp_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(store.settings, "codebase_index_dir", str(tmp_path / "cache"))
    monkeypatch.setattr(security_store.settings, "security_scan_dir", str(tmp_path / "sec"))
    monkeypatch.setattr(quality_store.settings, "quality_scan_dir", str(tmp_path / "qual"))


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "a.py").write_text("def foo():\n    pass\n", encoding="utf-8")
    return root


def test_get_index_requires_auth(project):
    resp = client.get("/api/codebase/index", params={"path": str(project)})
    assert resp.status_code == 401


def test_get_index_builds_and_returns_full_index(project):
    resp = client.get("/api/codebase/index", params={"path": str(project)}, headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["file_count"] == 1
    assert body["files"][0]["path"] == "a.py"


def test_get_index_404_for_nonexistent_path(tmp_path):
    resp = client.get("/api/codebase/index", params={"path": str(tmp_path / "nope")}, headers=AUTH)
    assert resp.status_code == 404


def test_recent_projects_lists_previously_indexed(project):
    client.get("/api/codebase/index", params={"path": str(project)}, headers=AUTH)

    resp = client.get("/api/codebase/recent", headers=AUTH)
    assert resp.status_code == 200
    roots = [p["root"] for p in resp.json()["projects"]]
    assert str(project.resolve()) in roots


def test_get_graph_requires_auth(project):
    resp = client.get("/api/codebase/graph", params={"path": str(project)})
    assert resp.status_code == 401


def test_get_graph_404_for_nonexistent_path(tmp_path):
    resp = client.get("/api/codebase/graph", params={"path": str(tmp_path / "nope")}, headers=AUTH)
    assert resp.status_code == 404


def test_get_graph_returns_nodes_and_resolved_edges(tmp_path):
    root = tmp_path / "proj2"
    (root / "app").mkdir(parents=True)
    (root / "app" / "__init__.py").write_text("", encoding="utf-8")
    (root / "app" / "main.py").write_text("from app.utils import helper\n", encoding="utf-8")
    (root / "app" / "utils.py").write_text("def helper():\n    pass\n", encoding="utf-8")

    resp = client.get("/api/codebase/graph", params={"path": str(root)}, headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    paths = {n["path"] for n in body["nodes"]}
    assert paths == {"app/__init__.py", "app/main.py", "app/utils.py"}
    assert body["edges"] == [{"source": "app/main.py", "target": "app/utils.py"}]


def test_get_graph_nodes_have_no_severity_when_project_never_scanned(tmp_path):
    root = tmp_path / "proj3"
    root.mkdir()
    (root / "a.py").write_text("VALUE = 1\n", encoding="utf-8")

    resp = client.get("/api/codebase/graph", params={"path": str(root)}, headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["security_scanned"] is False
    assert body["quality_scanned"] is False
    assert all(n["severity"] is None for n in body["nodes"])
    assert all(n["finding_count"] == 0 for n in body["nodes"])


def test_get_graph_nodes_carry_max_severity_from_cached_scans(tmp_path):
    root = tmp_path / "proj4"
    root.mkdir()
    (root / "a.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "b.py").write_text("VALUE = 2\n", encoding="utf-8")

    security_store.save_scan(
        ScanResult(
            root=str(root.resolve()),
            scanned_at="2026-07-29T00:00:00+00:00",
            tools_run=["bandit"],
            tools_skipped={},
            findings=[
                Finding(
                    id="f1", tool="bandit", file="a.py", line=1, end_line=None,
                    severity="critical", rule_id="B1", message="hallazgo crítico",
                )
            ],
        )
    )

    resp = client.get("/api/codebase/graph", params={"path": str(root)}, headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    by_path = {n["path"]: n for n in body["nodes"]}
    assert by_path["a.py"]["severity"] == "critical"
    assert by_path["a.py"]["finding_count"] == 1
    assert by_path["b.py"]["severity"] is None
    assert body["security_scanned"] is True
    assert body["quality_scanned"] is False


def test_get_file_requires_auth(project):
    resp = client.get("/api/codebase/file", params={"path": str(project), "file": "a.py"})
    assert resp.status_code == 401


def test_get_file_returns_content_and_language(project):
    resp = client.get("/api/codebase/file", params={"path": str(project), "file": "a.py"}, headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["content"] == "def foo():\n    pass\n"
    assert body["language"] == "Python"
    assert body["path"] == "a.py"


def test_get_file_404_when_project_path_invalid(tmp_path):
    resp = client.get("/api/codebase/file", params={"path": str(tmp_path / "nope"), "file": "a.py"}, headers=AUTH)
    assert resp.status_code == 404


def test_get_file_404_when_file_missing(project):
    resp = client.get("/api/codebase/file", params={"path": str(project), "file": "no-existe.py"}, headers=AUTH)
    assert resp.status_code == 404


def test_get_file_rejects_path_traversal_outside_project(project):
    resp = client.get(
        "/api/codebase/file",
        params={"path": str(project), "file": "../../../../etc/passwd"},
        headers=AUTH,
    )
    assert resp.status_code == 400


def test_get_file_works_for_a_file_in_a_subdirectory(project):
    (project / "src").mkdir()
    (project / "src" / "util.py").write_text("VALUE = 1\n", encoding="utf-8")

    resp = client.get("/api/codebase/file", params={"path": str(project), "file": "src/util.py"}, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["content"] == "VALUE = 1\n"


def test_get_file_413_when_file_too_large(project, monkeypatch):
    from app.routers import codebase as codebase_router

    monkeypatch.setattr(codebase_router, "MAX_FILE_SIZE_BYTES", 5)

    resp = client.get("/api/codebase/file", params={"path": str(project), "file": "a.py"}, headers=AUTH)
    assert resp.status_code == 413


def test_get_file_has_no_findings_when_project_never_scanned(project):
    resp = client.get("/api/codebase/file", params={"path": str(project), "file": "a.py"}, headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["findings"] == []
    assert body["security_scanned"] is False
    assert body["quality_scanned"] is False


def test_get_file_returns_findings_sorted_by_severity_descending(project):
    security_store.save_scan(
        ScanResult(
            root=str(project.resolve()),
            scanned_at="2026-07-29T00:00:00+00:00",
            tools_run=["bandit"],
            tools_skipped={},
            findings=[
                Finding(id="low", tool="bandit", file="a.py", line=5, end_line=None, severity="low", rule_id="B1", message="bajo"),
                Finding(id="crit", tool="bandit", file="a.py", line=1, end_line=None, severity="critical", rule_id="B2", message="crítico"),
                Finding(id="other-file", tool="bandit", file="b.py", line=1, end_line=None, severity="critical", rule_id="B3", message="no es de a.py"),
            ],
        )
    )

    resp = client.get("/api/codebase/file", params={"path": str(project), "file": "a.py"}, headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert [f["id"] for f in body["findings"]] == ["crit", "low"]
    assert body["security_scanned"] is True


def test_get_file_excludes_known_noise_from_findings(project):
    security_store.save_scan(
        ScanResult(
            root=str(project.resolve()),
            scanned_at="2026-07-29T00:00:00+00:00",
            tools_run=["bandit"],
            tools_skipped={},
            findings=[
                Finding(id="real", tool="bandit", file="a.py", line=1, end_line=None, severity="high", rule_id="B608", message="sqli real"),
                Finding(id="noise", tool="bandit", file="a.py", line=2, end_line=None, severity="low", rule_id="B101", message="assert en test"),
            ],
        )
    )

    resp = client.get("/api/codebase/file", params={"path": str(project), "file": "a.py"}, headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert [f["id"] for f in body["findings"]] == ["real"]
    assert body["findings_noise_omitted"] == 1
