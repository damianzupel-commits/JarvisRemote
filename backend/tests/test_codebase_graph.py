from pathlib import Path

import pytest

from app.codebase.graph import build_edges
from app.codebase.indexer import build_index

_NODEGOAT_ROOT = Path(r"C:\Users\dam\Documents\test-scans\NodeGoat")


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_project(tmp_path):
    root = tmp_path

    _write(root / "app" / "__init__.py", "")
    _write(
        root / "app" / "main.py",
        "import os\n"
        "from app.utils import helper\n"
        "from .utils import helper\n"
        "from app.subpkg import store\n",
    )
    _write(root / "app" / "utils.py", "def helper():\n    pass\n")
    _write(root / "app" / "subpkg" / "__init__.py", "")
    _write(root / "app" / "subpkg" / "store.py", "def save():\n    pass\n")
    _write(
        root / "app" / "subpkg" / "thing.py",
        "from ..utils import helper\n",
    )

    _write(root / "frontend" / "src" / "foo.js", "export default function Foo() {}\n")
    _write(
        root / "frontend" / "src" / "index.js",
        "import Foo from './foo';\n"
        "import react from 'react';\n",
    )

    _write(root / "server" / "bar.js", "module.exports = function Bar() {};\n")
    _write(root / "server" / "baz.js", "module.exports = function Baz() {};\n")
    _write(
        root / "server" / "app.js",
        "const Bar = require('./bar');\n"
        "const { Baz } = require('./baz');\n"
        "const express = require('express');\n",
    )

    return root


def _edge_set(edges):
    return {(e["source"], e["target"]) for e in edges}


def test_absolute_and_relative_python_imports_resolve_to_the_same_deduped_edge(tmp_path):
    root = _make_project(tmp_path)
    index = build_index(root)
    edges = build_edges(index)

    # "from app.utils import helper" y "from .utils import helper" resuelven
    # al mismo archivo -- no debería haber dos edges idénticos.
    matching = [e for e in edges if e == {"source": "app/main.py", "target": "app/utils.py"}]
    assert len(matching) == 1


def test_from_package_import_submodule_targets_the_submodule_not_the_package(tmp_path):
    root = _make_project(tmp_path)
    index = build_index(root)
    edges = _edge_set(build_edges(index))

    assert ("app/main.py", "app/subpkg/store.py") in edges
    assert ("app/main.py", "app/subpkg/__init__.py") not in edges


def test_relative_dotted_import_resolves_up_one_level(tmp_path):
    root = _make_project(tmp_path)
    index = build_index(root)
    edges = _edge_set(build_edges(index))

    assert ("app/subpkg/thing.py", "app/utils.py") in edges


def test_stdlib_import_produces_no_edge(tmp_path):
    root = _make_project(tmp_path)
    index = build_index(root)
    edges = build_edges(index)

    assert all(e["source"] != "app/main.py" or "os" not in e["target"] for e in edges)


def test_js_relative_import_resolves(tmp_path):
    root = _make_project(tmp_path)
    index = build_index(root)
    edges = _edge_set(build_edges(index))

    assert ("frontend/src/index.js", "frontend/src/foo.js") in edges


def test_js_bare_package_import_produces_no_edge(tmp_path):
    root = _make_project(tmp_path)
    index = build_index(root)
    edges = build_edges(index)

    assert all(e["source"] != "frontend/src/index.js" or "react" not in e["target"] for e in edges)


def test_js_commonjs_require_resolves(tmp_path):
    root = _make_project(tmp_path)
    index = build_index(root)
    edges = _edge_set(build_edges(index))

    assert ("server/app.js", "server/bar.js") in edges
    # Destructurado (`const { Baz } = require(...)`) resuelve igual que la
    # forma directa (`const Bar = require(...)`).
    assert ("server/app.js", "server/baz.js") in edges


def test_js_require_bare_package_produces_no_edge(tmp_path):
    root = _make_project(tmp_path)
    index = build_index(root)
    edges = build_edges(index)

    assert all(e["source"] != "server/app.js" or "express" not in e["target"] for e in edges)


def test_no_self_edges(tmp_path):
    root = _make_project(tmp_path)
    index = build_index(root)
    edges = build_edges(index)

    assert all(e["source"] != e["target"] for e in edges)


def test_unresolvable_language_produces_no_edges(tmp_path):
    _write(tmp_path / "main.go", "package main\n\nimport \"fmt\"\n\nfunc main() {}\n")
    index = build_index(tmp_path)

    assert build_edges(index) == []


@pytest.mark.skipif(not _NODEGOAT_ROOT.is_dir(), reason="NodeGoat no está clonado en esta máquina")
def test_nodegoat_commonjs_project_now_produces_edges():
    # Caso real que motivó el soporte de `require()`: NodeGoat es Express/
    # CommonJS puro (sin `import ... from`), así que antes de soportar
    # `require()` el grafo de este proyecto daba 0 edges -- indistinguible en
    # la UI de un bug real. Ver conversación del 2026-07-29.
    index = build_index(_NODEGOAT_ROOT)
    edges = build_edges(index)

    assert len(edges) > 0
    node_ids = {f.path for f in index.files}
    assert all(e["source"] in node_ids and e["target"] in node_ids for e in edges)
