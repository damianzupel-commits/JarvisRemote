"""Dataclasses del índice de codebase, compartidas entre indexer/store/tools/router."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Symbol:
    kind: str  # "function" | "class" | "import"
    name: str
    line: int  # 1-indexed


@dataclass
class FileEntry:
    path: str  # relativo a la raíz del proyecto, separadores '/'
    language: str | None
    size_bytes: int
    line_count: int
    symbols: list[Symbol] = field(default_factory=list)
    parsed: bool = False  # True si se usó tree-sitter (no el fallback regex)


@dataclass
class LanguageStat:
    language: str
    file_count: int
    line_count: int


@dataclass
class CodebaseIndex:
    root: str
    indexed_at: str
    file_count: int
    languages: list[LanguageStat]
    primary_language: str | None
    files: list[FileEntry]

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "CodebaseIndex":
        files = [
            FileEntry(
                path=f["path"],
                language=f["language"],
                size_bytes=f["size_bytes"],
                line_count=f["line_count"],
                symbols=[Symbol(**s) for s in f.get("symbols", [])],
                parsed=f.get("parsed", False),
            )
            for f in data["files"]
        ]
        languages = [LanguageStat(**l) for l in data["languages"]]
        return CodebaseIndex(
            root=data["root"],
            indexed_at=data["indexed_at"],
            file_count=data["file_count"],
            languages=languages,
            primary_language=data.get("primary_language"),
            files=files,
        )
