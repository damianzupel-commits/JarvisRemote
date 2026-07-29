"""Aplica un cambio puntual de código, con auditoría real.

Diseño deliberadamente conservador (ver README/nota de Obsidian de auditoría):
1. Quien genera `old_snippet`/`new_snippet` es el LLM (con un hallazgo real de
   security_scan_project/quality_scan_project, o directamente a pedido del
   usuario) -- este módulo NO llama al LLM ni "inventa" el cambio, solo hace
   el reemplazo mecánico + diff + commit. Mismo principio que separa escaneo
   (herramienta real) de interpretación (LLM con contexto real): acá también,
   generar el cambio es tarea del LLM, aplicarlo es tarea de código
   determinístico.
2. Nunca escribe nada sin pasar antes por un diff explícito: con `confirm=False`
   (el default) se devuelve el diff en modo dry-run sin tocar el archivo.
3. Si el proyecto es un repo git, cada cambio aplicado queda en su propio commit
   (nunca mezclado con otros cambios en stage) -- así es reversible con
   `git revert <hash>` sin afectar nada más. Se usa `git add -- <path>` seguido
   de `git commit -- <path>` (nunca `git add -A`/`git add .`) a propósito:
   ambos comandos van con el mismo pathspec puntual, así que solo tocan ESE
   archivo -- ignoran cualquier otra cosa que ya esté en stage o modificada,
   evitando arrastrar sin querer cambios en curso del usuario en otros
   archivos. El `git add` puntual es necesario para que esto funcione también
   con archivos nuevos que git todavía no conoce (ver `_git_commit_file`).
"""

from __future__ import annotations

import difflib
import subprocess
from pathlib import Path


class SnippetNotFoundError(ValueError):
    pass


class SnippetAmbiguousError(ValueError):
    pass


def _resolve_in_root(root: Path, file: str) -> Path:
    candidate = Path(file)
    target = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    if target != root and root not in target.parents:
        raise PermissionError(f"'{file}' está fuera de la raíz del proyecto ({root})")
    return target


def _is_git_repo(root: Path) -> bool:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def _git_commit_file(root: Path, file_rel: str, message: str) -> str | None:
    """Commitea solo los cambios de `file_rel` (pathspec, no todo el index).
    Devuelve el hash corto del commit, o None si no había nada que commitear.

    `git commit -- <pathspec>` por sí solo NO alcanza para un archivo nuevo
    que git todavía no conoce -- falla con "pathspec ... did not match any
    file(s) known to git" (bug real encontrado al hacer dogfooding de
    fs_write_file creando un archivo nuevo). Por eso primero se hace
    `git add -- <pathspec>`, que sí funciona tanto para archivos nuevos como
    modificados y, al ir con pathspec, solo mete al stage ESE archivo puntual
    -- no arrastra ningún otro cambio en curso que ya estuviera en stage."""
    add_proc = subprocess.run(
        ["git", "-C", str(root), "add", "--", file_rel],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if add_proc.returncode != 0:
        return None
    proc = subprocess.run(
        ["git", "-C", str(root), "commit", "-m", message, "--", file_rel],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        return None
    rev = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    return rev.stdout.strip() if rev.returncode == 0 else None


def commit_if_eligible(root: Path, file_rel: str, message: str) -> dict:
    """Commitea el estado YA escrito en disco de un solo archivo, si el
    proyecto es un repo git -- separado de `apply_fix` porque `fs_write_file`
    escribe contenido nuevo completo (no un reemplazo de snippet), así que no
    pasa por el diff mecánico de `apply_fix`, pero igual necesita el mismo
    resultado: commit propio, reversible con `git revert`."""
    if not _is_git_repo(root):
        return {
            "committed": False,
            "commit_hash": None,
            "note": "El proyecto no es un repo git -- escritura sin commit (no hay forma automática de revertirla).",
        }
    commit_hash = _git_commit_file(root, file_rel, message)
    if commit_hash:
        return {
            "committed": True,
            "commit_hash": commit_hash,
            "note": f"Commiteado como {commit_hash} -- revertible con 'git revert {commit_hash}'.",
        }
    return {
        "committed": False,
        "commit_hash": None,
        "note": "Es un repo git pero el commit no se pudo crear (revisar 'git status').",
    }


def apply_fix(
    *,
    root: str,
    file: str,
    old_snippet: str,
    new_snippet: str,
    commit_message: str,
    confirm: bool = False,
) -> dict:
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise NotADirectoryError(str(root_path))

    target = _resolve_in_root(root_path, file)
    if not target.is_file():
        raise FileNotFoundError(str(target))

    original = target.read_text(encoding="utf-8")
    occurrences = original.count(old_snippet)
    if occurrences == 0:
        raise SnippetNotFoundError(
            "El texto original (old_snippet) no aparece en el archivo -- puede que ya haya "
            "cambiado desde el escaneo. Volvé a leer el archivo antes de reintentar."
        )
    if occurrences > 1:
        raise SnippetAmbiguousError(
            f"El texto original aparece {occurrences} veces en el archivo -- agregá más contexto "
            "a old_snippet para que identifique un único lugar, como con una edición normal."
        )

    updated = original.replace(old_snippet, new_snippet, 1)
    file_rel = target.relative_to(root_path).as_posix()
    diff_text = "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"a/{file_rel}",
            tofile=f"b/{file_rel}",
        )
    )

    if not confirm:
        return {
            "applied": False,
            "file": file_rel,
            "diff": diff_text,
            "note": "Dry-run -- nada se escribió todavía. Volvé a llamar con confirm=true para aplicar y commitear.",
        }

    target.write_text(updated, encoding="utf-8")
    commit_info = commit_if_eligible(root_path, file_rel, commit_message)

    return {
        "applied": True,
        "file": file_rel,
        "diff": diff_text,
        "committed": commit_info["committed"],
        "commit_hash": commit_info["commit_hash"],
        "note": commit_info["note"],
    }
