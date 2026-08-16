import json

import pytest

from app.tools import reflect


@pytest.fixture(autouse=True)
def _tmp_reflections_path(tmp_path, monkeypatch):
    path = tmp_path / "reflections.jsonl"
    monkeypatch.setattr(reflect.settings, "reflections_path", str(path))
    return path


def test_save_appends_jsonl_entry_with_timestamp(_tmp_reflections_path):
    result = reflect.jarvis_reflect(action="save", insight="A Damian le gusta que confirme antes de matar procesos")

    assert result["saved"] is True
    assert "timestamp" in result

    lines = _tmp_reflections_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["insight"] == "A Damian le gusta que confirme antes de matar procesos"
    assert "timestamp" in entry


def test_save_without_insight_raises():
    with pytest.raises(ValueError):
        reflect.jarvis_reflect(action="save")


def test_query_without_topic_raises():
    with pytest.raises(ValueError):
        reflect.jarvis_reflect(action="query")


def test_invalid_action_raises():
    with pytest.raises(ValueError):
        reflect.jarvis_reflect(action="delete")


def test_query_returns_relevant_entries_by_keyword_overlap():
    reflect.jarvis_reflect(action="save", insight="Ollama usa Vulkan en esta GPU AMD, no ROCm")
    reflect.jarvis_reflect(action="save", insight="El usuario prefiere respuestas cortas sin resumen final")

    result = reflect.jarvis_reflect(action="query", topic="Ollama GPU Vulkan")

    assert result["topic"] == "Ollama GPU Vulkan"
    assert len(result["results"]) == 1
    assert "Vulkan" in result["results"][0]["insight"]


def test_query_returns_empty_list_when_no_match():
    reflect.jarvis_reflect(action="save", insight="Algo totalmente no relacionado")

    result = reflect.jarvis_reflect(action="query", topic="criptomonedas")

    assert result["results"] == []


def test_query_respects_limit():
    for i in range(10):
        reflect.jarvis_reflect(action="save", insight=f"reflexion numero {i} sobre testing")

    result = reflect.jarvis_reflect(action="query", topic="testing", limit=3)

    assert len(result["results"]) == 3


def test_query_orders_by_score_then_recency():
    reflect.jarvis_reflect(action="save", insight="testing es importante")
    reflect.jarvis_reflect(action="save", insight="testing de tools es muy importante hoy")

    result = reflect.jarvis_reflect(action="query", topic="testing tools importante hoy")

    insights = [r["insight"] for r in result["results"]]
    assert insights[0] == "testing de tools es muy importante hoy"


def test_query_returns_empty_when_file_does_not_exist(_tmp_reflections_path):
    assert not _tmp_reflections_path.exists()

    result = reflect.jarvis_reflect(action="query", topic="lo que sea")

    assert result["results"] == []


def test_query_skips_malformed_lines(_tmp_reflections_path):
    _tmp_reflections_path.parent.mkdir(parents=True, exist_ok=True)
    with _tmp_reflections_path.open("w", encoding="utf-8") as f:
        f.write("esto no es json valido\n")
        f.write(json.dumps({"timestamp": "2026-01-01T00:00:00+00:00", "insight": "testing valido"}) + "\n")

    result = reflect.jarvis_reflect(action="query", topic="testing")

    assert len(result["results"]) == 1
    assert result["results"][0]["insight"] == "testing valido"


# --- esquema extendido: tipo/contexto/vigente (rediseño 2026-08-13) -----------------

def test_save_defaults_tipo_and_contexto_when_not_specified(_tmp_reflections_path):
    result = reflect.jarvis_reflect(action="save", insight="algo sin clasificar")

    assert result["tipo"] == "leccion_aprendida"
    assert result["contexto"] == "general"
    assert result["vigente"] is True

    entry = json.loads(_tmp_reflections_path.read_text(encoding="utf-8").splitlines()[0])
    assert entry["tipo"] == "leccion_aprendida"
    assert entry["contexto"] == "general"
    assert entry["vigente"] is True


def test_save_accepts_explicit_tipo_and_contexto(_tmp_reflections_path):
    result = reflect.jarvis_reflect(
        action="save", insight="Damian prefiere clips cortos", tipo="preferencia_usuario", contexto="generacion_video",
    )

    assert result["tipo"] == "preferencia_usuario"
    assert result["contexto"] == "generacion_video"

    entry = json.loads(_tmp_reflections_path.read_text(encoding="utf-8").splitlines()[0])
    assert entry["tipo"] == "preferencia_usuario"
    assert entry["contexto"] == "generacion_video"


def test_save_raises_for_an_invalid_tipo(_tmp_reflections_path):
    with pytest.raises(ValueError, match="tipo inválido"):
        reflect.jarvis_reflect(action="save", insight="x", tipo="no_existe")


def test_query_filters_by_tipo(_tmp_reflections_path):
    reflect.jarvis_reflect(action="save", insight="decision real sobre arquitectura", tipo="decision_arquitectura")
    reflect.jarvis_reflect(action="save", insight="preferencia real del usuario", tipo="preferencia_usuario")

    result = reflect.jarvis_reflect(action="query", topic="real", tipo="decision_arquitectura")

    assert len(result["results"]) == 1
    assert result["results"][0]["tipo"] == "decision_arquitectura"


def test_query_filters_by_contexto(_tmp_reflections_path):
    reflect.jarvis_reflect(action="save", insight="algo del modulo real", contexto="modulo_investigacion")
    reflect.jarvis_reflect(action="save", insight="algo de escritorio real", contexto="desktop_control")

    result = reflect.jarvis_reflect(action="query", topic="real", contexto="desktop_control")

    assert len(result["results"]) == 1
    assert result["results"][0]["contexto"] == "desktop_control"


def test_query_excludes_non_vigente_entries_by_default(_tmp_reflections_path):
    reflect.jarvis_reflect(action="save", insight="reflexion vigente real", vigente=True)
    reflect.jarvis_reflect(action="save", insight="reflexion descartada real", tipo="ruido", vigente=False)

    result = reflect.jarvis_reflect(action="query", topic="real")

    assert len(result["results"]) == 1
    assert result["results"][0]["insight"] == "reflexion vigente real"


def test_query_can_explicitly_review_discarded_entries(_tmp_reflections_path):
    reflect.jarvis_reflect(action="save", insight="reflexion vigente real", vigente=True)
    reflect.jarvis_reflect(action="save", insight="reflexion descartada real", tipo="ruido", vigente=False)

    result = reflect.jarvis_reflect(action="query", topic="real", vigente=False)

    assert len(result["results"]) == 1
    assert result["results"][0]["insight"] == "reflexion descartada real"


def test_query_vigente_none_ignores_the_filter(_tmp_reflections_path):
    reflect.jarvis_reflect(action="save", insight="reflexion vigente real", vigente=True)
    reflect.jarvis_reflect(action="save", insight="reflexion descartada real", tipo="ruido", vigente=False)

    result = reflect.jarvis_reflect(action="query", topic="real", vigente=None)

    assert len(result["results"]) == 2


def test_query_results_include_the_new_fields(_tmp_reflections_path):
    reflect.jarvis_reflect(action="save", insight="entrada completa real", tipo="decision_arquitectura", contexto="modulo_investigacion")

    result = reflect.jarvis_reflect(action="query", topic="completa")

    entry = result["results"][0]
    assert entry["tipo"] == "decision_arquitectura"
    assert entry["contexto"] == "modulo_investigacion"
    assert entry["vigente"] is True


def test_query_treats_legacy_entries_without_new_fields_as_vigente_true(_tmp_reflections_path):
    """Retrocompatibilidad: una línea del esquema viejo (sin tipo/contexto/
    vigente) sigue siendo encontrable, y no se excluye por el filtro
    vigente=True default (se asume vigente si el campo no está)."""
    _tmp_reflections_path.parent.mkdir(parents=True, exist_ok=True)
    with _tmp_reflections_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": "2026-01-01T00:00:00+00:00", "insight": "entrada del esquema viejo real"}) + "\n")

    result = reflect.jarvis_reflect(action="query", topic="viejo real")

    assert len(result["results"]) == 1
    assert result["results"][0]["tipo"] == "leccion_aprendida"  # default aplicado a falta de dato real
    assert result["results"][0]["vigente"] is True


def test_concurrent_saves_do_not_silently_lose_entries(_tmp_reflections_path):
    """Bug real, grave, encontrado en testing adversarial (2026-08-13,
    "múltiples conversaciones consultando jarvis_reflect a la vez"): sin
    lock, cada `_save` abría su propio file handle en modo 'a' -- 50
    guardados concurrentes perdían una entrada en silencio de forma
    intermitente (confirmado en vivo, ~1 de cada 3 corridas: 49 líneas en
    vez de 50, SIN ningún error -- el caller recibía {"saved": True} igual
    para la entrada perdida). Windows no garantiza atomicidad entre
    `write()` de handles de append independientes, a diferencia de POSIX."""
    import threading

    def saver(i):
        reflect.jarvis_reflect(action="save", insight=f"insight numero {i} de la prueba de concurrencia real")

    threads = [threading.Thread(target=saver, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lines = [ln for ln in _tmp_reflections_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 50
    for line in lines:
        json.loads(line)  # ninguna línea corrupta/mezclada tampoco


def test_save_after_a_truncated_trailing_line_does_not_lose_the_new_entry(_tmp_reflections_path):
    """Bug real, grave, encontrado en testing adversarial (2026-08-13, "kill
    duro a mitad de un write"): un kill que interrumpe un write() deja la
    última línea SIN el '\\n' final -- antes de este fix, la SIGUIENTE
    entrada (perfectamente válida en sí misma) se pegaba directo al final
    de esa línea rota, sin separador, formando una sola línea inválida que
    ni siquiera el manejo tolerante de `_load_entries` podía salvar -- la
    entrada nueva se perdía en silencio junto con la vieja. Confirmado en
    vivo truncando una línea a mano y guardando la siguiente."""
    reflect.jarvis_reflect(action="save", insight="entrada valida antes del kill")

    # simula el kill duro: una línea real, sin el '\n' final
    with _tmp_reflections_path.open("a", encoding="utf-8") as f:
        f.write('{"timestamp": "2026-08-13T23:00:00", "insight": "linea truncada por un kill duro')

    reflect.jarvis_reflect(action="save", insight="entrada nueva despues del kill")

    result = reflect.jarvis_reflect(action="query", topic="entrada nueva despues kill", limit=10)
    assert any(r["insight"] == "entrada nueva despues del kill" for r in result["results"])
