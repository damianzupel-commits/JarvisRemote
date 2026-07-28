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
