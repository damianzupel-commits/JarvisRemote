import pytest
from fastapi.testclient import TestClient

from app.codebase import store
from app.config import settings
from app.main import app

client = TestClient(app)
AUTH = {"Authorization": f"Bearer {settings.api_key}"}


@pytest.fixture(autouse=True)
def _tmp_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(store.settings, "codebase_index_dir", str(tmp_path / "cache"))


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
