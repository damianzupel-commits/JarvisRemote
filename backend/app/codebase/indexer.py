"""Construye el índice estructural de un proyecto: recorre el árbol de
archivos, detecta el lenguaje de cada uno y extrae sus símbolos (funciones,
clases, imports).

Símbolos: se usa tree-sitter (`tree_sitter_language_pack`) para los lenguajes
con query definida en `symbol_queries.py` -- da un AST real, no depende de que
el código esté bien indentado ni de que el estilo coincida con lo que un
regex anticipa. Para cualquier otro lenguaje detectado (o si tree-sitter
falla en un archivo puntual, ej. sintaxis inválida) se usa un extractor regex
genérico (`_extract_symbols_fallback`) para que el índice nunca deje un
archivo sin ningún intento de símbolos -- el pedido de Damian fue "ordenarlo
por completo", no "lo que tree-sitter sepa parsear".
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import pathspec
from tree_sitter import Query, QueryCursor

from .languages import (
    DEFAULT_IGNORED_DIRS,
    LANGUAGE_TO_GRAMMAR,
    MAX_FILE_SIZE_BYTES,
    detect_language,
)
from .models import CodebaseIndex, FileEntry, LanguageStat, Symbol
from .symbol_queries import SYMBOL_QUERIES

_FALLBACK_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("function", re.compile(r"^\s*(?:public|private|protected|static|async|export|func|fn|def)?\s*"
                             r"(?:function\s+)?(\w+)\s*\(", re.IGNORECASE)),
    ("class", re.compile(r"^\s*(?:public|private|protected|export)?\s*class\s+(\w+)", re.IGNORECASE)),
]


def _load_gitignore_spec(root: Path) -> pathspec.GitIgnoreSpec:
    lines: list[str] = []
    gitignore = root / ".gitignore"
    if gitignore.is_file():
        try:
            lines = gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = []
    return pathspec.GitIgnoreSpec.from_lines(lines)


def _iter_files(root: Path):
    spec = _load_gitignore_spec(root)
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(root)
        rel_posix = rel.as_posix()
        if any(part in DEFAULT_IGNORED_DIRS for part in rel.parts[:-1]):
            continue
        if spec.match_file(rel_posix):
            continue
        yield path, rel_posix


@lru_cache(maxsize=None)
def _grammar_resources(grammar: str):
    """Cargar el parser/language/query compilada de una gramática es caro (carga
    una biblioteca nativa) -- cacheado por proceso, así indexar un proyecto de
    cientos de archivos no repite ese costo por cada archivo del mismo lenguaje."""
    from tree_sitter_language_pack import get_language, get_parser

    parser = get_parser(grammar)
    lang = get_language(grammar)
    query = Query(lang, SYMBOL_QUERIES[grammar])
    return parser, query


def _extract_symbols_treesitter(grammar: str, source: bytes) -> list[Symbol] | None:
    try:
        parser, query = _grammar_resources(grammar)
    except Exception:
        return None

    try:
        tree = parser.parse(source)
        cursor = QueryCursor(query)
        captures = cursor.captures(tree.root_node)
    except Exception:
        return None

    symbols: list[Symbol] = []
    seen: set[tuple[str, str, int]] = set()
    for kind, nodes in captures.items():
        for node in nodes:
            line = node.start_point[0] + 1
            if kind == "import":
                name = node.text.decode("utf-8", errors="replace").strip().splitlines()[0][:120]
            else:
                name = node.text.decode("utf-8", errors="replace").strip()
            key = (kind, name, line)
            if key in seen:
                continue
            seen.add(key)
            symbols.append(Symbol(kind=kind, name=name, line=line))
    symbols.sort(key=lambda s: s.line)
    return symbols


def _extract_symbols_fallback(text: str) -> list[Symbol]:
    symbols: list[Symbol] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for kind, pattern in _FALLBACK_PATTERNS:
            match = pattern.match(line)
            if match:
                symbols.append(Symbol(kind=kind, name=match.group(1), line=lineno))
                break
    return symbols


def _index_file(path: Path, rel_posix: str) -> FileEntry:
    language = detect_language(path.name)
    try:
        size = path.stat().st_size
    except OSError:
        size = 0

    if size == 0 or size > MAX_FILE_SIZE_BYTES:
        return FileEntry(path=rel_posix, language=language, size_bytes=size, line_count=0)

    try:
        raw = path.read_bytes()
    except OSError:
        return FileEntry(path=rel_posix, language=language, size_bytes=size, line_count=0)

    text = raw.decode("utf-8", errors="replace")
    line_count = text.count("\n") + (1 if text and not text.endswith("\n") else 0)

    grammar = LANGUAGE_TO_GRAMMAR.get(language or "")
    symbols = _extract_symbols_treesitter(grammar, raw) if grammar else None
    parsed = symbols is not None
    if symbols is None:
        symbols = _extract_symbols_fallback(text) if language else []

    return FileEntry(
        path=rel_posix,
        language=language,
        size_bytes=size,
        line_count=line_count,
        symbols=symbols,
        parsed=parsed,
    )


def build_index(root: str | Path) -> CodebaseIndex:
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise NotADirectoryError(str(root_path))

    files: list[FileEntry] = []
    for path, rel_posix in _iter_files(root_path):
        files.append(_index_file(path, rel_posix))

    files.sort(key=lambda f: f.path)

    lang_totals: dict[str, LanguageStat] = {}
    for f in files:
        if not f.language:
            continue
        stat = lang_totals.setdefault(f.language, LanguageStat(language=f.language, file_count=0, line_count=0))
        stat.file_count += 1
        stat.line_count += f.line_count

    languages = sorted(lang_totals.values(), key=lambda s: s.line_count, reverse=True)
    primary_language = languages[0].language if languages else None

    return CodebaseIndex(
        root=str(root_path),
        indexed_at=datetime.now(timezone.utc).isoformat(),
        file_count=len(files),
        languages=languages,
        primary_language=primary_language,
        files=files,
    )
