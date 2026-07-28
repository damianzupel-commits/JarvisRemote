import pytest

from app.codebase import store


@pytest.fixture(autouse=True)
def _tmp_cache_dir(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(store.settings, "codebase_index_dir", str(cache_dir))
    return cache_dir


def _make_project(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "a.py").write_text("def foo():\n    pass\n", encoding="utf-8")
    return project


def test_get_or_build_writes_cache_file(tmp_path, _tmp_cache_dir):
    project = _make_project(tmp_path)
    index = store.get_or_build(project)

    assert index.file_count == 1
    cached_files = list(_tmp_cache_dir.glob("*.json"))
    assert len(cached_files) == 1


def test_get_or_build_reuses_cache_without_refresh(tmp_path, _tmp_cache_dir):
    project = _make_project(tmp_path)
    first = store.get_or_build(project)

    (project / "b.py").write_text("def bar():\n    pass\n", encoding="utf-8")
    second = store.get_or_build(project)

    assert second.file_count == first.file_count == 1


def test_get_or_build_refresh_true_rebuilds(tmp_path, _tmp_cache_dir):
    project = _make_project(tmp_path)
    store.get_or_build(project)

    (project / "b.py").write_text("def bar():\n    pass\n", encoding="utf-8")
    refreshed = store.get_or_build(project, refresh=True)

    assert refreshed.file_count == 2


def test_load_cached_returns_none_when_never_indexed(tmp_path, _tmp_cache_dir):
    assert store.load_cached(tmp_path / "never-indexed") is None


def test_list_cached_projects_reports_indexed_projects(tmp_path, _tmp_cache_dir):
    project = _make_project(tmp_path)
    store.get_or_build(project)

    projects = store.list_cached_projects()
    assert len(projects) == 1
    assert projects[0]["file_count"] == 1
