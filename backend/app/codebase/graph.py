"""Resuelve los símbolos "import" que ya extrae `indexer.py` a archivos reales
del proyecto indexado, para armar un grafo de relaciones (lo consume la
pestaña Codebase, ver `ui/graph_view.py`).

Deliberadamente conservador: solo resolvemos imports para los lenguajes donde
se puede hacer con confianza razonable a partir de texto (Python completo --
absolutos, relativos con puntos, y `from paquete import submódulo`-- y JS/TS/TSX
solo imports relativos, que son inequívocos, tanto ES modules (`import ... from
'./x'`) como CommonJS (`require('./x')`, ver symbol_queries.py para cómo se
extrae ese símbolo)). El resto de los lenguajes indexados quedan sin edges en
vez de inventar relaciones que no podemos verificar -- un grafo incompleto
pero honesto es mejor que uno que parece completo y está mal.

`_SuffixIndex` existe porque un repo indexado puede contener más de una raíz
de paquete Python real (ej. este mismo repo: backend/ y tray-app/ son cada
uno su propio root de imports) -- un import absoluto como "from app.codebase
import store" no matchea el path completo desde la raíz indexada
("backend/app/codebase/store.py"), pero sí su sufijo ("app/codebase/store.py").
"""

from __future__ import annotations

import re

from .languages import LANGUAGE_TO_GRAMMAR
from .models import CodebaseIndex

_PY_FROM_RE = re.compile(r"^from\s+([.\w]*)\s+import\s+(.+)$")
_PY_IMPORT_RE = re.compile(r"^import\s+(.+)$")
_JS_RELATIVE_RE = re.compile(r"""from\s+['"](\.[^'"]+)['"]""")
_JS_REQUIRE_RE = re.compile(r"""require\(\s*['"](\.[^'"]+)['"]\s*\)""")

_JS_SUFFIXES = ["", ".js", ".jsx", ".ts", ".tsx", "/index.js", "/index.jsx", "/index.ts", "/index.tsx"]

# Cuántos segmentos de la izquierda se toleran recortar al buscar por sufijo
# -- 2 alcanza para monorepos con un par de niveles de sub-proyectos sin
# empezar a matchear archivos genéricos (__init__.py, config.py) de cualquier
# lado del árbol.
_MAX_SUFFIX_STRIP = 2


class _SuffixIndex:
    def __init__(self, all_paths: set[str]):
        self.all_paths = all_paths
        self._by_suffix: dict[str, str] = {}
        for path in all_paths:
            parts = path.split("/")
            for i in range(0, min(len(parts), _MAX_SUFFIX_STRIP + 1)):
                suffix = "/".join(parts[i:])
                self._by_suffix.setdefault(suffix, path)

    def resolve(self, parts: list[str]) -> str | None:
        if not parts:
            return None
        candidate = "/".join(parts) + ".py"
        if candidate in self._by_suffix:
            return self._by_suffix[candidate]
        candidate_pkg = "/".join(parts) + "/__init__.py"
        if candidate_pkg in self._by_suffix:
            return self._by_suffix[candidate_pkg]
        return None


def _py_module_to_parts(module: str, from_dir: list[str]) -> list[str] | None:
    if module.startswith("."):
        dots = len(module) - len(module.lstrip("."))
        remainder = module[dots:]
        up = dots - 1
        if up > len(from_dir):
            return None
        base = from_dir[: len(from_dir) - up] if up > 0 else list(from_dir)
        return base + ([p for p in remainder.split(".") if p] if remainder else [])
    return [p for p in module.split(".") if p]


def _python_edges(file_path: str, import_text: str, index: _SuffixIndex) -> list[str]:
    from_dir = file_path.split("/")[:-1]
    text = import_text.strip()

    m = _PY_FROM_RE.match(text)
    if m:
        module, names_part = m.group(1), m.group(2)
        base_parts = _py_module_to_parts(module, from_dir)
        if base_parts is None:
            return []
        # "from paquete import submodulo" suele importar un submódulo real
        # (ej. "from app.codebase import store" -> app/codebase/store.py),
        # no solo un nombre dentro de paquete/__init__.py -- probamos eso
        # primero y solo si ningún nombre resuelve como submódulo caemos al
        # paquete en sí.
        names = [n.strip().split(" as ")[0].strip() for n in names_part.split(",")]
        targets = [t for name in names if name and name != "*" for t in [index.resolve(base_parts + [name])] if t]
        if targets:
            return targets
        base_target = index.resolve(base_parts)
        return [base_target] if base_target else []

    m = _PY_IMPORT_RE.match(text)
    if m:
        targets = []
        for mod in m.group(1).split(","):
            mod = mod.strip().split(" as ")[0].strip()
            parts = _py_module_to_parts(mod, from_dir) if mod else None
            target = index.resolve(parts) if parts else None
            if target:
                targets.append(target)
        return targets

    return []


def _js_edges(file_path: str, import_text: str, index: _SuffixIndex) -> list[str]:
    m = _JS_RELATIVE_RE.search(import_text) or _JS_REQUIRE_RE.search(import_text)
    if not m:
        return []
    parts = file_path.split("/")[:-1]
    for segment in m.group(1).split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if parts:
                parts.pop()
            continue
        parts.append(segment)
    base = "/".join(parts)
    for suffix in _JS_SUFFIXES:
        candidate = base + suffix
        if candidate in index.all_paths:
            return [candidate]
    return []


_RESOLVERS = {
    "python": _python_edges,
    "javascript": _js_edges,
    "typescript": _js_edges,
    "tsx": _js_edges,
}


def build_edges(index: CodebaseIndex) -> list[dict]:
    all_paths = {f.path for f in index.files}
    suffix_index = _SuffixIndex(all_paths)
    seen: set[tuple[str, str]] = set()
    edges: list[dict] = []
    for f in index.files:
        grammar = LANGUAGE_TO_GRAMMAR.get(f.language or "")
        resolver = _RESOLVERS.get(grammar or "")
        if resolver is None:
            continue
        for symbol in f.symbols:
            if symbol.kind != "import":
                continue
            for target in resolver(f.path, symbol.name, suffix_index):
                if target == f.path:
                    continue
                key = (f.path, target)
                if key in seen:
                    continue
                seen.add(key)
                edges.append({"source": f.path, "target": target})
    return edges
