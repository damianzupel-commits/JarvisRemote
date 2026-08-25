"""Tests del sandbox de filesystem endurecido (Mejora 1, 2026-08-19):
achicar FS_ALLOWED_ROOT del HOME entero a la raíz del proyecto, permitir
VARIAS raíces (FS_ALLOWED_ROOTS) y enforzar la contención de path con
normalización de '..'/symlinks -- ver app/tools/filesystem.py::_resolve y
config.Settings.fs_allowed_roots.

Todo mockeado con tmp_path + monkeypatch de settings, sin tocar el disco real
del usuario ni depender de la config real del .env."""

from pathlib import Path

import pytest

from app.config import Settings, _PROJECT_ROOT, _split_paths, settings as real_settings
from app.tools import filesystem


@pytest.fixture
def single_root(tmp_path, monkeypatch):
    """Una sola raíz permitida = tmp_path/root (comportamiento de siempre)."""
    root = tmp_path / "root"
    root.mkdir()
    monkeypatch.setattr(filesystem.settings, "fs_allowed_root", str(root))
    monkeypatch.setattr(filesystem.settings, "fs_allowed_roots_extra", [])
    return root


# --- Enforcement de la raíz única -------------------------------------------


def test_relative_path_resolves_inside_root(single_root):
    target = filesystem._resolve("sub/dir/file.txt")
    assert target == (single_root / "sub" / "dir" / "file.txt")
    assert target.is_relative_to(single_root)


def test_dot_resolves_to_root_itself(single_root):
    assert filesystem._resolve(".") == single_root


def test_absolute_path_inside_root_is_accepted(single_root):
    inside = single_root / "ok.txt"
    assert filesystem._resolve(str(inside)) == inside


def test_absolute_path_outside_root_is_rejected(single_root, tmp_path):
    outside = tmp_path / "afuera" / "secreto.txt"
    with pytest.raises(PermissionError):
        filesystem._resolve(str(outside))


def test_escape_with_dotdot_is_rejected(single_root):
    # '..' tiene que normalizarse ANTES de comparar: este path apunta afuera
    # de la raíz y debe rechazarse, no colarse.
    with pytest.raises(PermissionError):
        filesystem._resolve("../../etc/passwd")


def test_sneaky_dotdot_that_stays_inside_is_allowed(single_root):
    # Un '..' que vuelve a caer DENTRO de la raíz es legítimo.
    (single_root / "a").mkdir()
    target = filesystem._resolve("a/../b.txt")
    assert target == (single_root / "b.txt")


@pytest.mark.skipif(not hasattr(Path, "symlink_to"), reason="symlinks no soportados")
def test_symlink_pointing_outside_root_is_rejected(single_root, tmp_path):
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (outside_dir / "target.txt").write_text("secreto", encoding="utf-8")
    link = single_root / "escape"
    try:
        link.symlink_to(outside_dir)
    except (OSError, NotImplementedError):
        pytest.skip("no se pueden crear symlinks en este entorno")
    # A través del symlink el path resuelto cae afuera de la raíz -> rechazado.
    with pytest.raises(PermissionError):
        filesystem._resolve("escape/target.txt")


# --- Multi-root (FS_ALLOWED_ROOTS) ------------------------------------------


def test_absolute_path_inside_secondary_root_is_accepted(tmp_path, monkeypatch):
    primary = tmp_path / "primary"
    secondary = tmp_path / "secondary"
    primary.mkdir()
    secondary.mkdir()
    monkeypatch.setattr(filesystem.settings, "fs_allowed_root", str(primary))
    monkeypatch.setattr(filesystem.settings, "fs_allowed_roots_extra", [str(secondary)])

    inside_secondary = secondary / "repo" / "main.py"
    assert filesystem._resolve(str(inside_secondary)) == inside_secondary
    # Y la raíz principal sigue funcionando.
    assert filesystem._resolve("x.txt") == (primary / "x.txt")


def test_path_outside_all_roots_is_rejected_with_multi_root(tmp_path, monkeypatch):
    primary = tmp_path / "primary"
    secondary = tmp_path / "secondary"
    primary.mkdir()
    secondary.mkdir()
    monkeypatch.setattr(filesystem.settings, "fs_allowed_root", str(primary))
    monkeypatch.setattr(filesystem.settings, "fs_allowed_roots_extra", [str(secondary)])

    with pytest.raises(PermissionError):
        filesystem._resolve(str(tmp_path / "tercera" / "x.txt"))


def test_relative_path_resolves_against_primary_not_secondary(tmp_path, monkeypatch):
    primary = tmp_path / "primary"
    secondary = tmp_path / "secondary"
    primary.mkdir()
    secondary.mkdir()
    monkeypatch.setattr(filesystem.settings, "fs_allowed_root", str(primary))
    monkeypatch.setattr(filesystem.settings, "fs_allowed_roots_extra", [str(secondary)])
    assert filesystem._resolve("rel.txt") == (primary / "rel.txt")


def test_no_allowed_roots_configured_rejects_everything(monkeypatch):
    monkeypatch.setattr(filesystem.settings, "fs_allowed_root", "")
    monkeypatch.setattr(filesystem.settings, "fs_allowed_roots_extra", [])
    with pytest.raises(PermissionError):
        filesystem._resolve("cualquier_cosa.txt")


# --- Config: default acotado + lista de raíces ------------------------------


def test_default_fs_allowed_root_is_project_root_not_home():
    """El default NUEVO es la raíz del proyecto, no el HOME entero. Chequeo
    estático de la fuente (no reload de config, ver test_llm_client.py para el
    porqué de no recargar el módulo settings)."""
    import inspect

    from app import config as config_module

    source = inspect.getsource(config_module)
    assert 'os.getenv("FS_ALLOWED_ROOT", str(_PROJECT_ROOT))' in source
    # Y _PROJECT_ROOT es efectivamente la raíz del repo (contiene backend/).
    assert (_PROJECT_ROOT / "backend").is_dir()


def test_fs_allowed_roots_property_combines_and_dedups(monkeypatch):
    s = Settings()
    monkeypatch.setattr(s, "fs_allowed_root", "/a")
    monkeypatch.setattr(s, "fs_allowed_roots_extra", ["/b", "/a", "/c"])
    # Principal primero, sin duplicar "/a".
    assert s.fs_allowed_roots == ["/a", "/b", "/c"]


def test_split_paths_accepts_comma_and_semicolon_not_drive_colon():
    assert _split_paths(None) == []
    assert _split_paths("") == []
    # Coma y punto y coma separan; el ':' de la letra de unidad NO parte la ruta.
    assert _split_paths(r"C:\uno, C:\dos ; C:\tres") == [r"C:\uno", r"C:\dos", r"C:\tres"]


def test_real_settings_default_root_is_within_project():
    """Con la config real (sin monkeypatch), la raíz por default cae dentro
    del proyecto -- salvo que el .env la override, en cuyo caso no aplica."""
    import os

    if os.getenv("FS_ALLOWED_ROOT"):
        pytest.skip("FS_ALLOWED_ROOT override por env/.env; el default no aplica")
    assert Path(real_settings.fs_allowed_root).resolve() == _PROJECT_ROOT.resolve()
