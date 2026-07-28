import pytest

from app.codebase import store
from app.tools import codebase


@pytest.fixture(autouse=True)
def _tmp_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(store.settings, "codebase_index_dir", str(tmp_path / "cache"))


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "main.py").write_text(
        "class Greeter:\n    def greet(self):\n        pass\n\ndef helper():\n    pass\n",
        encoding="utf-8",
    )
    return root


def test_codebase_index_project_returns_summary(project):
    result = codebase.codebase_index_project(str(project))

    assert result["file_count"] == 1
    assert result["primary_language"] == "Python"
    assert any(l["language"] == "Python" for l in result["languages"])


def test_codebase_search_symbol_finds_partial_match(project):
    codebase.codebase_index_project(str(project))

    result = codebase.codebase_search_symbol(str(project), "gree")

    names = {m["name"] for m in result["matches"]}
    assert "Greeter" in names
    assert "greet" in names


def test_codebase_search_symbol_requires_prior_index(project):
    with pytest.raises(ValueError):
        codebase.codebase_search_symbol(str(project), "gree")


def test_codebase_file_outline_returns_symbols(project):
    codebase.codebase_index_project(str(project))

    result = codebase.codebase_file_outline(str(project), "main.py")

    assert result["language"] == "Python"
    names = {s["name"] for s in result["symbols"]}
    assert "Greeter" in names
    assert "helper" in names


def test_codebase_file_outline_missing_file_raises(project):
    codebase.codebase_index_project(str(project))

    with pytest.raises(FileNotFoundError):
        codebase.codebase_file_outline(str(project), "nope.py")
