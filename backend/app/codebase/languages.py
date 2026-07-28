"""Detección de lenguaje por extensión y mapeo a gramáticas de tree-sitter.

La detección por extensión (`EXTENSION_TO_LANGUAGE`) es la fuente de verdad
para "en qué lenguaje está escrito este archivo" -- funciona para cualquier
archivo, tenga o no soporte de tree-sitter. `LANGUAGE_TO_GRAMMAR` es más chico
a propósito: solo cubre los lenguajes para los que definimos queries de
símbolos en `symbol_queries.py`; el resto cae al extractor regex genérico
(ver `indexer.py::_extract_symbols_fallback`), así ningún lenguaje detectado
se queda sin ningún símbolo.
"""

from __future__ import annotations

EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".jsx": "JavaScript (JSX)",
    ".ts": "TypeScript",
    ".mts": "TypeScript",
    ".tsx": "TypeScript (TSX)",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".go": "Go",
    ".rs": "Rust",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".hh": "C++",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".m": "Objective-C",
    ".scala": "Scala",
    ".sh": "Shell",
    ".bash": "Shell",
    ".ps1": "PowerShell",
    ".sql": "SQL",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".less": "Less",
    ".vue": "Vue",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".xml": "XML",
    ".md": "Markdown",
    ".dart": "Dart",
    ".lua": "Lua",
    ".r": "R",
    ".jl": "Julia",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".erl": "Erlang",
    ".hs": "Haskell",
    ".clj": "Clojure",
    ".zig": "Zig",
    ".proto": "Protocol Buffers",
    ".gradle": "Gradle",
    ".dockerfile": "Dockerfile",
}

# Nombre exacto que espera `tree_sitter_language_pack.get_parser()` para cada
# lenguaje que tiene queries de símbolos definidas (ver symbol_queries.py).
LANGUAGE_TO_GRAMMAR: dict[str, str] = {
    "Python": "python",
    "JavaScript": "javascript",
    "JavaScript (JSX)": "javascript",
    "TypeScript": "typescript",
    "TypeScript (TSX)": "tsx",
    "Java": "java",
    "Kotlin": "kotlin",
    "Go": "go",
    "Rust": "rust",
    "C": "c",
    "C++": "cpp",
    "C#": "csharp",
    "Ruby": "ruby",
    "PHP": "php",
    "Swift": "swift",
}

# Carpetas que nunca aportan nada útil a un índice estructural y que además
# pueden ser enormes (venv/node_modules) -- se ignoran siempre, además de lo
# que diga el .gitignore del proyecto.
DEFAULT_IGNORED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        "venv",
        ".venv",
        "env",
        ".env",
        "dist",
        "build",
        "target",
        ".next",
        ".nuxt",
        "vendor",
        ".idea",
        ".vscode",
        ".gradle",
        "bin",
        "obj",
        ".dart_tool",
        ".tox",
        "coverage",
        ".cache",
    }
)

# Archivos por arriba de este tamaño no se leen para extracción de símbolos
# (probablemente generados/binarios/minificados) -- igual quedan en el
# inventario de archivos con su lenguaje detectado y tamaño.
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024


def detect_language(filename: str) -> str | None:
    lower = filename.lower()
    if lower == "dockerfile":
        return "Dockerfile"
    for ext, lang in EXTENSION_TO_LANGUAGE.items():
        if lower.endswith(ext):
            return lang
    return None
