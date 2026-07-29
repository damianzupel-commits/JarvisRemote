"""Tests del auto-fix: dry-run por default, escritura + commit atómico por
archivo cuando se confirma, y los guardrails de snippet único. Usa un repo git
real (subprocess) en tmp_path, no mockeado -- lo que nos importa verificar acá
es justamente que el commit queda aislado y es revertible de verdad."""

import shutil
import subprocess

import pytest

from app.codeedit import fixer

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git no está instalado")


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=15)


@pytest.fixture
def git_project(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "query.py").write_text(
        "def get_user(username):\n"
        "    query = \"SELECT * FROM users WHERE username = '\" + username + \"'\"\n"
        "    return query\n",
        encoding="utf-8",
    )
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial")
    return root


_OLD = "query = \"SELECT * FROM users WHERE username = '\" + username + \"'\""
_NEW = 'query = "SELECT * FROM users WHERE username = ?"'


def test_apply_fix_dry_run_does_not_touch_file(git_project):
    result = fixer.apply_fix(
        root=str(git_project), file="query.py", old_snippet=_OLD, new_snippet=_NEW,
        commit_message="fix: sqli", confirm=False,
    )

    assert result["applied"] is False
    assert "SELECT * FROM users WHERE username = ?" in result["diff"]
    assert "SELECT * FROM users WHERE username = '\" + username" in (git_project / "query.py").read_text()


def test_apply_fix_confirmed_writes_and_commits(git_project):
    before_log = _git(git_project, "log", "--oneline").stdout.strip().splitlines()

    result = fixer.apply_fix(
        root=str(git_project), file="query.py", old_snippet=_OLD, new_snippet=_NEW,
        commit_message="fix: SQL injection en query.py (auto-fix Jarvis)", confirm=True,
    )

    assert result["applied"] is True
    assert result["committed"] is True
    assert result["commit_hash"]
    content = (git_project / "query.py").read_text()
    assert _NEW in content
    assert "+ username" not in content

    after_log = _git(git_project, "log", "--oneline").stdout.strip().splitlines()
    assert len(after_log) == len(before_log) + 1
    assert "auto-fix Jarvis" in after_log[0]

    # Revertible de verdad, no solo "en teoría".
    revert = _git(git_project, "revert", "--no-edit", result["commit_hash"])
    assert revert.returncode == 0
    assert _OLD in (git_project / "query.py").read_text()


def test_apply_fix_confirmed_without_git_still_writes(tmp_path):
    root = tmp_path / "proj_no_git"
    root.mkdir()
    (root / "query.py").write_text(_OLD + "\n", encoding="utf-8")

    result = fixer.apply_fix(
        root=str(root), file="query.py", old_snippet=_OLD, new_snippet=_NEW,
        commit_message="fix", confirm=True,
    )

    assert result["applied"] is True
    assert result["committed"] is False
    assert _NEW in (root / "query.py").read_text()


def test_apply_fix_raises_when_snippet_missing(git_project):
    with pytest.raises(fixer.SnippetNotFoundError):
        fixer.apply_fix(
            root=str(git_project), file="query.py", old_snippet="no existe esto",
            new_snippet="x", commit_message="fix", confirm=False,
        )


def test_apply_fix_raises_when_snippet_ambiguous(git_project):
    (git_project / "query.py").write_text("dup\ndup\n", encoding="utf-8")

    with pytest.raises(fixer.SnippetAmbiguousError):
        fixer.apply_fix(
            root=str(git_project), file="query.py", old_snippet="dup",
            new_snippet="x", commit_message="fix", confirm=False,
        )


def test_apply_fix_rejects_path_outside_root(git_project):
    with pytest.raises(PermissionError):
        fixer.apply_fix(
            root=str(git_project), file="../outside.py", old_snippet="x",
            new_snippet="y", commit_message="fix", confirm=False,
        )


def test_commit_if_eligible_commits_brand_new_untracked_file(git_project):
    """Regresión: `git commit -- <path>` por sí solo falla con "pathspec ...
    did not match any file(s) known to git" para un archivo que git nunca vio
    -- hace falta `git add -- <path>` primero (bug real encontrado al hacer
    dogfooding de fs_write_file creando un archivo nuevo en el repo real)."""
    (git_project / "new_note.md").write_text("contenido nuevo\n", encoding="utf-8")

    result = fixer.commit_if_eligible(git_project, "new_note.md", "chore: nuevo archivo")

    assert result["committed"] is True
    assert result["commit_hash"]

    log = _git(git_project, "log", "-1", "--name-only", "--format=").stdout.strip()
    assert log == "new_note.md"

    revert = _git(git_project, "revert", "--no-edit", result["commit_hash"])
    assert revert.returncode == 0
    assert not (git_project / "new_note.md").is_file()
