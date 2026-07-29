"""Tests del circuito auditado de fs_write_file: si el archivo cae dentro de
un repo git ya indexado por Codebase, la escritura queda commiteada aparte y
de forma reversible -- ver la nota de Obsidian de auditoría y
app/codeedit/fixer.py::commit_if_eligible. Usa un repo git real (subprocess)
en tmp_path, no mockeado, para verificar que el commit queda de verdad."""

import shutil
import subprocess

import pytest

from app.codebase import store as codebase_store
from app.codebase.models import CodebaseIndex, FileEntry, LanguageStat
from app.tools import filesystem

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git no está instalado")


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=15)


def _seed_index(root):
    index = CodebaseIndex(
        root=str(root),
        indexed_at="2026-01-01T00:00:00+00:00",
        file_count=1,
        languages=[LanguageStat(language="Python", file_count=1, line_count=1)],
        primary_language="Python",
        files=[FileEntry(path="app.py", language="Python", size_bytes=10, line_count=1, symbols=[], parsed=False)],
    )
    codebase_store.save_cache(index)


@pytest.fixture(autouse=True)
def _tmp_codebase_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(codebase_store.settings, "codebase_index_dir", str(tmp_path / "codebase_cache"))


@pytest.fixture
def git_project(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "app.py").write_text("print('hola')\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial")
    monkeypatch.setattr(filesystem.settings, "fs_allowed_root", str(root))
    return root


def test_fs_write_file_commits_when_project_is_indexed_git_repo(git_project):
    _seed_index(git_project)
    before_log = _git(git_project, "log", "--oneline").stdout.strip().splitlines()

    result = filesystem.fs_write_file("app.py", "print('chau')\n")

    assert result["audited"] is True
    assert result["commit"]["committed"] is True
    commit_hash = result["commit"]["commit_hash"]
    assert commit_hash

    after_log = _git(git_project, "log", "--oneline").stdout.strip().splitlines()
    assert len(after_log) == len(before_log) + 1
    assert "fs_write_file" in after_log[0]

    revert = _git(git_project, "revert", "--no-edit", commit_hash)
    assert revert.returncode == 0
    assert (git_project / "app.py").read_text() == "print('hola')\n"


def test_fs_write_file_commits_brand_new_file(git_project):
    """Regresión: crear un archivo que git nunca vio (no solo modificar uno ya
    trackeado) también tiene que quedar commiteado -- ver
    test_codeedit_fixer.py::test_commit_if_eligible_commits_brand_new_untracked_file."""
    _seed_index(git_project)

    result = filesystem.fs_write_file("notes/new_note.md", "contenido nuevo\n")

    assert result["audited"] is True
    assert result["commit"]["committed"] is True
    log = _git(git_project, "log", "-1", "--name-only", "--format=").stdout.strip()
    assert log == "notes/new_note.md"


def test_fs_write_file_not_audited_when_project_not_indexed(git_project):
    # No se llama a _seed_index -- el repo existe pero Codebase nunca lo indexó.
    before_log = _git(git_project, "log", "--oneline").stdout.strip().splitlines()

    result = filesystem.fs_write_file("app.py", "print('chau')\n")

    assert result["audited"] is False
    assert "commit" not in result

    after_log = _git(git_project, "log", "--oneline").stdout.strip().splitlines()
    assert len(after_log) == len(before_log)


def test_fs_write_file_not_audited_when_no_git_repo(tmp_path, monkeypatch):
    root = tmp_path / "no_git_proj"
    root.mkdir()
    monkeypatch.setattr(filesystem.settings, "fs_allowed_root", str(root))

    result = filesystem.fs_write_file("app.py", "print('hola')\n")

    assert result["audited"] is False
    assert (root / "app.py").read_text() == "print('hola')\n"
