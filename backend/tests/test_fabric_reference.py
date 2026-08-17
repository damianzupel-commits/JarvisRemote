"""Tests de app/tools/fabric_reference.py -- la referencia curada de Fabric
API/Loom que se inyecta en opencode_run_task(fabric_reference=true). No hay
lógica que probar más allá de "el contenido está y trae lo que dos intentos
previos (v6 y el primer opencode_run_task) inventaron por separado" -- ver
docstring del módulo para la evidencia real de cada uno."""

from __future__ import annotations

from app.tools.fabric_reference import FABRIC_MOD_REFERENCE


def test_reference_is_nonempty_text():
    assert isinstance(FABRIC_MOD_REFERENCE, str)
    assert len(FABRIC_MOD_REFERENCE) > 500


def test_reference_gives_the_real_attack_event_class_that_was_hallucinated_twice():
    # Verificado contra el codigo fuente real de FabricMC/fabric (rama 1.21,
    # fabric-events-interaction-v0) -- ver docstring del modulo.
    assert "package net.fabricmc.fabric.api.event.player;" in FABRIC_MOD_REFERENCE
    assert "public interface AttackEntityCallback" in FABRIC_MOD_REFERENCE
    assert "ActionResult interact(PlayerEntity player, World world, Hand hand" in FABRIC_MOD_REFERENCE


def test_reference_states_yarn_mappings_explicitly_not_mojmap():
    assert "Yarn" in FABRIC_MOD_REFERENCE
    assert "PlayerEntity" in FABRIC_MOD_REFERENCE
    assert "mojmap" in FABRIC_MOD_REFERENCE or "Mojang" in FABRIC_MOD_REFERENCE


def test_reference_covers_fabric_mod_json_schema():
    assert "schemaVersion" in FABRIC_MOD_REFERENCE
    assert "entrypoints" in FABRIC_MOD_REFERENCE


def test_reference_covers_gradle_loom_config():
    assert "fabric-loom" in FABRIC_MOD_REFERENCE
    assert "yarn_mappings" in FABRIC_MOD_REFERENCE
    assert "modImplementation" in FABRIC_MOD_REFERENCE


def test_reference_warns_against_fake_wrapper_jar():
    # Bug real 2026-08-11: el intento anterior de opencode_run_task escribio un
    # gradle-wrapper.jar de 308 bytes (texto, no un binario real) -- gradlew
    # fallaba antes de arrancar. La referencia advierte explicitamente contra esto.
    assert "wrapper.jar" in FABRIC_MOD_REFERENCE
    assert "placeholder" in FABRIC_MOD_REFERENCE
