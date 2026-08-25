"""Tests del sistema de DOS MODOS de operación (2026-08-19): SUPERVISADO vs
AUTÓNOMO, y su integración con el sandbox de filesystem ya existente.

Cubre las cuatro condiciones que definen el diseño:
  1. En SUPERVISADO, un path del HOME amplio se ACEPTA (no se pierde potencia).
  2. En AUTÓNOMO, ese MISMO path (fuera del proyecto) se RECHAZA, pero uno
     dentro del sandbox chico se acepta.
  3. El default ante entrada desconocida es AUTÓNOMO (fail-safe restrictivo).
  4. El agente NO puede escalarse el modo a sí mismo (auto-escalada bloqueada).

Todo mockeado con tmp_path + monkeypatch de settings, sin tocar disco real ni
el .env. El modo vive en un ContextVar, así que cada bloque `operating_as` se
limpia solo al salir."""

from pathlib import Path

import pytest

from app import operation_mode
from app.operation_mode import OperationMode, operating_as
from app.config import Settings
from app.tools import filesystem


@pytest.fixture
def two_tier_roots(tmp_path, monkeypatch):
    """Configura los dos niveles de sandbox sobre tmp_path:
      - HOME amplio  = tmp_path/home           (modo SUPERVISADO)
      - proyecto     = tmp_path/home/proyecto  (modo AUTÓNOMO, dentro del HOME)
      - afuera       = tmp_path/otro           (fuera de ambos... del proyecto)
    Devuelve las tres rutas."""
    home = tmp_path / "home"
    project = home / "proyecto"
    outside = tmp_path / "otro"
    for p in (home, project, outside):
        p.mkdir(parents=True)

    # Sandbox ACOTADO (autónomo) = solo el proyecto.
    monkeypatch.setattr(filesystem.settings, "fs_allowed_root", str(project))
    monkeypatch.setattr(filesystem.settings, "fs_allowed_roots_extra", [])
    # Sandbox AMPLIO (supervisado) = el HOME.
    monkeypatch.setattr(filesystem.settings, "fs_supervised_root", str(home))
    return home, project, outside


# --- 1 + 2: el modo decide qué raíces valen -------------------------------


def test_supervised_accepts_wide_home_path(two_tier_roots):
    home, project, _ = two_tier_roots
    target_in_home = home / "documentos" / "carta.txt"
    with operating_as(OperationMode.SUPERVISED, source="test"):
        # Un path del HOME amplio (fuera del proyecto) se acepta en supervisado.
        assert filesystem._resolve(str(target_in_home)) == target_in_home
        # Y el del proyecto también (supervisado ⊇ autónomo).
        assert filesystem._resolve(str(project / "x.py")) == (project / "x.py")


def test_autonomous_rejects_home_path_but_accepts_project(two_tier_roots):
    home, project, _ = two_tier_roots
    target_in_home = home / "documentos" / "carta.txt"
    with operating_as(OperationMode.AUTONOMOUS, source="test"):
        # El MISMO path del HOME (fuera del proyecto) se rechaza en autónomo.
        with pytest.raises(PermissionError):
            filesystem._resolve(str(target_in_home))
        # Pero uno dentro del proyecto (sandbox chico) se acepta.
        assert filesystem._resolve(str(project / "sub" / "y.py")) == (project / "sub" / "y.py")


def test_same_path_flips_acceptance_between_modes(two_tier_roots):
    """El punto central del diseño: el MISMO path cambia de aceptado a
    rechazado solo por cambiar de modo, sin tocar la config."""
    home, _, _ = two_tier_roots
    path = str(home / "algo.txt")
    with operating_as(OperationMode.SUPERVISED, source="test"):
        assert filesystem._resolve(path) == Path(path)
    with operating_as(OperationMode.AUTONOMOUS, source="test"):
        with pytest.raises(PermissionError):
            filesystem._resolve(path)


def test_effective_roots_switch_by_mode(two_tier_roots):
    home, project, _ = two_tier_roots
    with operating_as(OperationMode.SUPERVISED, source="test"):
        roots = operation_mode.effective_fs_roots()
        assert str(home) in roots  # amplio
    with operating_as(OperationMode.AUTONOMOUS, source="test"):
        roots = operation_mode.effective_fs_roots()
        assert roots == [str(project)]  # acotado, sin el HOME


# --- 3: default fail-safe ---------------------------------------------------


def test_default_process_mode_is_autonomous_when_env_unset(monkeypatch):
    monkeypatch.delenv("JARVIS_OPERATION_MODE", raising=False)
    assert operation_mode._env_default_mode() is OperationMode.AUTONOMOUS


def test_unknown_env_value_falls_back_to_autonomous(monkeypatch):
    monkeypatch.setenv("JARVIS_OPERATION_MODE", "banana-no-existe")
    assert operation_mode._env_default_mode() is OperationMode.AUTONOMOUS


def test_env_can_force_supervised(monkeypatch):
    monkeypatch.setenv("JARVIS_OPERATION_MODE", "supervised")
    assert operation_mode._env_default_mode() is OperationMode.SUPERVISED


def test_contextvar_default_is_autonomous_without_declaration(two_tier_roots):
    """Sin ningún operating_as, el modo efectivo es AUTÓNOMO (el restrictivo):
    es lo que ve cualquier entrada desatendida que no declara modo."""
    assert operation_mode.current_mode() is OperationMode.AUTONOMOUS
    home, _, _ = two_tier_roots
    with pytest.raises(PermissionError):
        filesystem._resolve(str(home / "z.txt"))


# --- 4: el agente no puede auto-escalar ------------------------------------


def test_agent_cannot_self_escalate_to_supervised():
    """Dentro de un turno del agente (agent_turn_active), un intento de escalar
    de AUTÓNOMO a SUPERVISADO -- Jarvis ampliándose los permisos a sí mismo --
    se rechaza en código."""
    with operating_as(OperationMode.AUTONOMOUS, source="test"):
        with operation_mode.agent_turn_active():
            with pytest.raises(PermissionError):
                with operating_as(OperationMode.SUPERVISED, source="agente-malicioso"):
                    pass  # no debería llegar acá
            # El modo NO cambió: sigue AUTÓNOMO.
            assert operation_mode.current_mode() is OperationMode.AUTONOMOUS


def test_deescalation_from_within_agent_is_allowed():
    """Bajar de SUPERVISADO a AUTÓNOMO desde adentro del turno SÍ se permite
    (solo REDUCE permisos, es seguro)."""
    with operating_as(OperationMode.SUPERVISED, source="test"):
        with operation_mode.agent_turn_active():
            with operating_as(OperationMode.AUTONOMOUS, source="acotar"):
                assert operation_mode.current_mode() is OperationMode.AUTONOMOUS


def test_entry_point_sets_supervised_before_agent_turn_is_active():
    """El caso legítimo: el punto de entrada declara SUPERVISADO ANTES de que el
    turno del agente esté activo, así que el guardrail no lo bloquea."""
    with operating_as(OperationMode.SUPERVISED, source="http_chat"):
        assert operation_mode.current_mode() is OperationMode.SUPERVISED
        with operation_mode.agent_turn_active():
            assert operation_mode.current_mode() is OperationMode.SUPERVISED


# --- Config: supervised_roots ⊇ allowed_roots -------------------------------


def test_supervised_roots_superset_of_autonomous(monkeypatch):
    s = Settings()
    monkeypatch.setattr(s, "fs_allowed_root", "/proj")
    monkeypatch.setattr(s, "fs_allowed_roots_extra", ["/extra"])
    monkeypatch.setattr(s, "fs_supervised_root", "/home")
    assert s.fs_allowed_roots == ["/proj", "/extra"]
    # El HOME va primero (resolución de rutas relativas) y se suman las acotadas.
    assert s.fs_supervised_roots == ["/home", "/proj", "/extra"]
    # Supervisado contiene todo lo de autónomo.
    assert set(s.fs_allowed_roots).issubset(set(s.fs_supervised_roots))
