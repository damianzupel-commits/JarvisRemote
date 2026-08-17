"""Tests de app/skills.py -- arquitectura de skills (ítem 5 de la cola,
2026-08-12). Cubre: completitud real contra el registro de tools (nada se
cae por las grietas), clasificación determinística por palabras clave sobre
mensajes representativos reales de esta sesión, y el invariante crítico de
que CORE siempre incluye lo que el gate de obsidian de fs_write_file necesita
para poder desbloquearse (ver docstring de app/skills.py)."""

from __future__ import annotations

from app import skills
from app.tools import get_tools


def test_every_registered_tool_is_accounted_for_in_core_or_exactly_one_skill():
    # generate_video/generate_image (video_gen.py/image_gen.py) están
    # deshabilitadas a propósito en producción (no se importan en
    # app/tools/__init__.py, ver el comentario ahí -- riesgo real de
    # hardware, no un problema de estas tools puntualmente) y por eso no
    # tienen skill asignado; en la suite completa a veces SÍ aparecen
    # registradas como efecto secundario de que otro archivo de test las
    # importe directo antes que este (mismo caso ya conocido en
    # test_tools_registry.py) -- se excluyen acá por la misma razón, no por
    # un hueco real en la cobertura de skills.
    real_tool_names = set(get_tools().keys()) - {"generate_video", "generate_image"}
    known = set(skills.CORE_TOOL_NAMES)
    for skill in skills.SKILLS.values():
        known |= skill.tool_names

    missing = real_tool_names - known
    extra = known - real_tool_names
    assert not missing, f"tools registradas pero sin skill/core asignado: {missing}"
    assert not extra, f"skills.py referencia tools que ya no existen en el registro: {extra}"


def test_skills_are_pairwise_disjoint():
    names = list(skills.SKILLS)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            overlap = skills.SKILLS[a].tool_names & skills.SKILLS[b].tool_names
            assert not overlap, f"'{a}' y '{b}' comparten tools: {overlap}"


def test_core_is_disjoint_from_every_skill():
    for name, skill in skills.SKILLS.items():
        overlap = skills.CORE_TOOL_NAMES & skill.tool_names
        assert not overlap, f"CORE y '{name}' comparten tools: {overlap}"


def test_core_includes_what_the_fs_write_file_obsidian_gate_needs():
    """Invariante crítico (ver docstring del módulo): si fs_write_file está
    en CORE pero obsidian_search_notes/research_topic no, el gate de
    agent.py::_obsidian_gate_error podría bloquear una escritura sin darle
    al modelo ninguna tool real para desbloquearla -- un guardrail
    inescapable por accidente. Nunca debe pasar."""
    assert "fs_write_file" in skills.CORE_TOOL_NAMES
    assert "obsidian_search_notes" in skills.CORE_TOOL_NAMES
    assert "research_topic" in skills.CORE_TOOL_NAMES


def test_classify_matches_security_audit_for_a_real_style_message():
    matched = skills.classify("Escaneá el proyecto en C:\\proj con security_scan_project y reparalo")
    assert "security_audit" in matched


def test_classify_matches_desktop_control_for_a_real_style_message():
    matched = skills.classify("Sacame una captura de pantalla del escritorio ahora")
    assert "desktop_control" in matched


def test_classify_matches_phone_control_for_a_real_style_message():
    matched = skills.classify("Sacá una foto con la cámara del celular y decime qué ves")
    assert "phone_control" in matched


def test_classify_matches_code_delegation_for_a_real_style_message():
    matched = skills.classify("Delegá esto a OpenCode con la referencia curada de Fabric")
    assert "code_delegation" in matched


def test_classify_matches_web_forms_and_desktop_control_for_a_real_style_message():
    """Un pedido de registro tiene que activar los dos skills a la vez --
    web_forms (browser_generate_password/browser_preview_submit) Y
    desktop_control (browser_open/browser_type/browser_click, sin los cuales
    no se puede completar nada) -- ver el comentario en la lista de keywords
    de desktop_control en app/skills.py."""
    matched = skills.classify("Registrame en tenable.com, generá una contraseña para la cuenta")
    assert "web_forms" in matched
    assert "desktop_control" in matched
    scoped = skills.tools_for_active_skills(matched)
    assert "browser_open" in scoped
    assert "browser_generate_password" in scoped


def test_classify_is_accent_insensitive():
    with_accent = skills.classify("investigá la vulnerabilidad de sesión")
    without_accent = skills.classify("investiga la vulnerabilidad de sesion")
    assert with_accent == without_accent
    assert "security_audit" in with_accent


def test_classify_returns_empty_set_for_an_ambiguous_generic_message():
    matched = skills.classify("Hola, ¿cómo estás?")
    assert matched == set()


def test_classify_can_match_multiple_skills_at_once():
    matched = skills.classify(
        "Escaneá el proyecto de seguridad y después sacame una captura de pantalla del resultado"
    )
    assert "security_audit" in matched
    assert "desktop_control" in matched


def test_tools_for_active_skills_with_empty_set_returns_only_core():
    assert skills.tools_for_active_skills(set()) == skills.CORE_TOOL_NAMES


def test_tools_for_active_skills_is_a_superset_of_core():
    result = skills.tools_for_active_skills({"security_audit"})
    assert skills.CORE_TOOL_NAMES <= result
    assert "security_scan_project" in result
    assert "desktop_click" not in result  # no pedido, no deberia estar


def test_tools_for_active_skills_unions_multiple_skills():
    result = skills.tools_for_active_skills({"security_audit", "phone_control"})
    assert "security_scan_project" in result
    assert "phone_take_photo" in result
    assert "desktop_click" not in result


def test_prompt_for_active_skills_with_empty_set_is_just_core():
    assert skills.prompt_for_active_skills(set()) == skills.CORE_PROMPT


def test_prompt_for_active_skills_includes_the_skill_fragment():
    result = skills.prompt_for_active_skills({"desktop_control"})
    assert skills.CORE_PROMPT in result
    assert skills.SKILLS["desktop_control"].prompt_fragment in result
    assert skills.SKILLS["security_audit"].prompt_fragment not in result


def test_prompt_for_active_skills_is_deterministic_regardless_of_set_iteration_order():
    # sets no garantizan orden -- el prompt final tiene que ser idéntico
    # (mismo texto, mismo orden de fragmentos) sin importar en qué orden
    # Python haya iterado el set internamente, para no romper el cacheo de
    # prefijo del servidor de inferencia (ver docstring de la función).
    a = skills.prompt_for_active_skills({"security_audit", "phone_control", "desktop_control"})
    b = skills.prompt_for_active_skills({"desktop_control", "security_audit", "phone_control"})
    assert a == b


def test_skill_scoped_tool_schema_count_is_meaningfully_smaller_than_full_registry():
    """Evidencia real del objetivo del rediseño (reducir lo que se manda en
    cada llamada): para un mensaje de un solo dominio, el subconjunto de
    tools tiene que ser una fracción chica del total, no casi todo."""
    total = len(get_tools())
    matched = skills.classify("Sacame una captura de pantalla del escritorio")
    scoped = skills.tools_for_active_skills(matched)
    assert len(scoped) < total * 0.5
