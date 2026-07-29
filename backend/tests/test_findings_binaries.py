"""Tests de app.findings.binaries.node_shim_argv -- resuelve el script real
detrás de un shim `.CMD` de npm (Windows) para poder invocarlo con `node.exe`
directo en vez del shim. Ver el docstring de la función para el bug real que
motivó esto: invocar el `.CMD` de ESLint vía `subprocess.run([exe, ...])` con
muchos argumentos se cuelga indefinidamente (confirmado real sobre NodeGoat,
timeout de 120s) -- saltear el shim lo baja a bajo un segundo."""

import json

import pytest

from app.findings import binaries


def test_node_shim_argv_returns_none_for_non_windows_shim(tmp_path):
    fake_exe = tmp_path / "eslint"  # sin extensión .cmd/.bat -> no es un shim de Windows
    fake_exe.write_text("", encoding="utf-8")
    assert binaries.node_shim_argv(str(fake_exe), "eslint", "eslint") is None


def test_node_shim_argv_resolves_script_from_package_json(tmp_path, monkeypatch):
    shim_dir = tmp_path
    pkg_dir = shim_dir / "node_modules" / "eslint"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "bin").mkdir()
    (pkg_dir / "bin" / "eslint.js").write_text("// fake entrypoint\n", encoding="utf-8")
    (pkg_dir / "package.json").write_text(
        json.dumps({"name": "eslint", "bin": {"eslint": "./bin/eslint.js"}}), encoding="utf-8"
    )
    fake_shim = shim_dir / "eslint.CMD"
    fake_shim.write_text("@echo off\n", encoding="utf-8")

    monkeypatch.setattr(binaries, "tool_path", lambda name: r"C:\fake\node.exe" if name == "node" else None)

    argv = binaries.node_shim_argv(str(fake_shim), "eslint", "eslint")

    assert argv is not None
    assert argv[0] == r"C:\fake\node.exe"
    assert argv[1] == str((pkg_dir / "bin" / "eslint.js").resolve())


def test_node_shim_argv_returns_none_without_node_installed(tmp_path, monkeypatch):
    pkg_dir = tmp_path / "node_modules" / "eslint"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "eslint.js").write_text("", encoding="utf-8")
    (pkg_dir / "package.json").write_text(
        json.dumps({"bin": {"eslint": "./eslint.js"}}), encoding="utf-8"
    )
    fake_shim = tmp_path / "eslint.CMD"
    fake_shim.write_text("", encoding="utf-8")

    monkeypatch.setattr(binaries, "tool_path", lambda name: None)

    assert binaries.node_shim_argv(str(fake_shim), "eslint", "eslint") is None


def test_chunk_paths_keeps_everything_in_one_batch_when_short():
    paths = [f"C:\\proj\\file{i}.py" for i in range(5)]
    batches = binaries.chunk_paths(paths, max_chars=10_000)
    assert batches == [paths]


def test_chunk_paths_splits_when_total_length_exceeds_limit():
    """Reproduce el bug real: bandit/ruff/mypy/eslint arman `[exe, *files, ...]`
    y se lo pasan a subprocess.run como una lista -- sobre un repo grande
    (743 archivos .py, SuperSaaSFastAPI) Windows rechazaba la línea de comando
    completa con `WinError 206`. Cada ruta simulada acá mide ~40 caracteres,
    así que un límite de 100 caracteres fuerza varios lotes de ~2 rutas."""
    paths = [f"C:\\proyecto\\carpeta\\archivo_{i:03d}.py" for i in range(10)]
    batches = binaries.chunk_paths(paths, max_chars=100)

    assert len(batches) > 1
    # ninguna ruta se pierde ni se duplica al repartir en lotes
    assert [p for batch in batches for p in batch] == paths
    # cada lote individual respeta el límite
    for batch in batches:
        assert sum(len(p) + 1 for p in batch) <= 100


def test_chunk_paths_never_drops_a_single_path_longer_than_the_limit():
    """Una ruta individual más larga que el límite todavía tiene que ir en su
    propio lote (no se puede partir un solo path) en vez de perderse."""
    long_path = "C:\\" + ("a" * 200) + ".py"
    batches = binaries.chunk_paths([long_path, "C:\\short.py"], max_chars=100)
    assert long_path in batches[0]
    assert sum(len(batch) for batch in batches) == 2


def test_chunk_paths_empty_input_returns_no_batches():
    assert binaries.chunk_paths([]) == []


@pytest.mark.timeout(30)
def test_node_shim_argv_resolves_real_eslint_install():
    """Contra la instalación real de ESLint en esta máquina (si está) --
    confirma que el bin resuelto existe de verdad, no solo que la lógica de
    parseo de package.json anda con fixtures fabricados."""
    exe = binaries.tool_path("eslint")
    if exe is None or not exe.lower().endswith((".cmd", ".bat")):
        pytest.skip("eslint no instalado como shim de Windows en este entorno")

    argv = binaries.node_shim_argv(exe, "eslint", "eslint")

    assert argv is not None
    assert argv[0].lower().endswith("node.exe")
    from pathlib import Path

    assert Path(argv[1]).is_file()
