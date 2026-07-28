import pytest

from app.obsidian import vault
from app.tools import obsidian


@pytest.fixture(autouse=True)
def _tmp_vault(tmp_path, monkeypatch):
    monkeypatch.setattr(vault.settings, "obsidian_vault_path", str(tmp_path / "vault"))


def test_obsidian_save_note_always_authored_by_jarvis():
    result = obsidian.obsidian_save_note(title="Idea", content="algo interesante", tags=["idea"])

    assert result["author"] == "jarvis"
    assert result["id"] == "jarvis/idea"


def test_obsidian_save_note_has_no_author_parameter():
    # La tool no expone `author` en su firma -- así el LLM no puede escribir
    # notas humanas por accidente ni a propósito.
    import inspect

    params = inspect.signature(obsidian.obsidian_save_note).parameters
    assert "author" not in params


def test_obsidian_list_notes_filters_by_author():
    obsidian.obsidian_save_note(title="J1", content="a")
    vault.save_note(title="H1", content="b", author="human")

    result = obsidian.obsidian_list_notes(author="jarvis")
    assert [n["title"] for n in result["notes"]] == ["J1"]


def test_obsidian_search_notes_returns_matches():
    obsidian.obsidian_save_note(title="Ollama GPU", content="usa Vulkan en AMD")

    result = obsidian.obsidian_search_notes(query="Ollama Vulkan")
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "Ollama GPU"
