from app.codebase.indexer import build_index
from app.codebase.languages import detect_language


def _make_sample_project(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text(
        "import os\n\n"
        "class Greeter:\n"
        "    def greet(self, name):\n"
        "        return f'hola {name}'\n\n"
        "def main():\n"
        "    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "util.js").write_text(
        "function helper(x) { return x + 1; }\n\n"
        "class Widget {\n"
        "    render() { return null; }\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Sample\n", encoding="utf-8")

    ignored = tmp_path / "node_modules" / "somepkg"
    ignored.mkdir(parents=True)
    (ignored / "index.js").write_text("function shouldBeIgnored() {}\n", encoding="utf-8")

    (tmp_path / ".gitignore").write_text("ignored_by_gitignore.py\n", encoding="utf-8")
    (tmp_path / "ignored_by_gitignore.py").write_text("def also_ignored(): pass\n", encoding="utf-8")

    return tmp_path


def test_detect_language_by_extension():
    assert detect_language("main.py") == "Python"
    assert detect_language("app.tsx") == "TypeScript (TSX)"
    assert detect_language("Dockerfile") == "Dockerfile"
    assert detect_language("no_extension") is None


def test_build_index_detects_languages_and_counts_files(tmp_path):
    root = _make_sample_project(tmp_path)
    index = build_index(root)

    paths = {f.path for f in index.files}
    assert "src/main.py" in paths
    assert "src/util.js" in paths
    assert "README.md" in paths

    languages = {s.language for s in index.languages}
    assert "Python" in languages
    assert "JavaScript" in languages


def test_build_index_respects_default_ignored_dirs(tmp_path):
    root = _make_sample_project(tmp_path)
    index = build_index(root)

    assert not any("node_modules" in f.path for f in index.files)


def test_build_index_respects_gitignore(tmp_path):
    root = _make_sample_project(tmp_path)
    index = build_index(root)

    assert not any(f.path == "ignored_by_gitignore.py" for f in index.files)


def test_python_file_symbols_extracted_via_treesitter(tmp_path):
    root = _make_sample_project(tmp_path)
    index = build_index(root)

    main_py = next(f for f in index.files if f.path == "src/main.py")
    assert main_py.parsed is True
    kinds_names = {(s.kind, s.name) for s in main_py.symbols}
    assert ("class", "Greeter") in kinds_names
    assert ("function", "greet") in kinds_names
    assert ("function", "main") in kinds_names


def test_javascript_file_symbols_extracted_via_treesitter(tmp_path):
    root = _make_sample_project(tmp_path)
    index = build_index(root)

    util_js = next(f for f in index.files if f.path == "src/util.js")
    assert util_js.parsed is True
    kinds_names = {(s.kind, s.name) for s in util_js.symbols}
    assert ("function", "helper") in kinds_names
    assert ("class", "Widget") in kinds_names


def test_unsupported_language_falls_back_to_regex(tmp_path):
    (tmp_path / "app.dart").write_text("class Foo {\n  void bar() {}\n}\n", encoding="utf-8")
    index = build_index(tmp_path)

    dart_file = next(f for f in index.files if f.path == "app.dart")
    assert dart_file.language == "Dart"
    assert dart_file.parsed is False
    names = {s.name for s in dart_file.symbols}
    assert "Foo" in names


def test_primary_language_is_the_one_with_most_lines(tmp_path):
    root = _make_sample_project(tmp_path)
    index = build_index(root)
    assert index.primary_language in {"Python", "JavaScript"}


def test_build_index_raises_for_missing_directory(tmp_path):
    import pytest

    with pytest.raises(NotADirectoryError):
        build_index(tmp_path / "does-not-exist")
