import pytest

from app.obsidian import vault


@pytest.fixture(autouse=True)
def _tmp_vault(tmp_path, monkeypatch):
    monkeypatch.setattr(vault.settings, "obsidian_vault_path", str(tmp_path / "vault"))
    return tmp_path / "vault"


def test_save_note_writes_markdown_with_frontmatter(_tmp_vault):
    note = vault.save_note(title="Primera nota", content="contenido de prueba", author="jarvis", tags=["idea"])

    assert note.id == "jarvis/primera-nota"
    path = _tmp_vault / "jarvis" / "primera-nota.md"
    assert path.is_file()
    raw = path.read_text(encoding="utf-8")
    assert "author: jarvis" in raw
    assert "contenido de prueba" in raw


def test_save_note_rejects_invalid_author():
    with pytest.raises(ValueError):
        vault.save_note(title="x", content="y", author="robot")


def test_save_note_avoids_overwriting_same_title(_tmp_vault):
    first = vault.save_note(title="Duplicada", content="uno", author="human")
    second = vault.save_note(title="Duplicada", content="dos", author="human")

    assert first.id != second.id
    assert vault.read_note(first.id).content == "uno"
    assert vault.read_note(second.id).content == "dos"


def test_jarvis_and_human_notes_stay_in_separate_folders(_tmp_vault):
    vault.save_note(title="Nota de Jarvis", content="a", author="jarvis")
    vault.save_note(title="Nota humana", content="b", author="human")

    assert (_tmp_vault / "jarvis" / "nota-de-jarvis.md").is_file()
    assert (_tmp_vault / "human" / "nota-humana.md").is_file()


def test_list_notes_filters_by_author(_tmp_vault):
    vault.save_note(title="J1", content="a", author="jarvis")
    vault.save_note(title="H1", content="b", author="human")

    jarvis_notes = vault.list_notes(author="jarvis")
    human_notes = vault.list_notes(author="human")

    assert [n.title for n in jarvis_notes] == ["J1"]
    assert [n.title for n in human_notes] == ["H1"]


def test_list_notes_without_filter_returns_both_authors(_tmp_vault):
    vault.save_note(title="J1", content="a", author="jarvis")
    vault.save_note(title="H1", content="b", author="human")

    all_notes = vault.list_notes()
    authors = {n.author for n in all_notes}
    assert authors == {"jarvis", "human"}


def test_search_notes_scores_by_keyword_overlap(_tmp_vault):
    vault.save_note(title="Ollama en GPU AMD", content="usa Vulkan no ROCm", author="jarvis")
    vault.save_note(title="Otra cosa", content="no relacionado", author="jarvis")

    results = vault.search_notes("Ollama GPU Vulkan")

    assert len(results) == 1
    assert results[0].title == "Ollama en GPU AMD"


def test_search_notes_can_filter_by_author(_tmp_vault):
    vault.save_note(title="Python tips", content="usar pathlib", author="jarvis")
    vault.save_note(title="Python notes", content="usar pathlib también", author="human")

    jarvis_only = vault.search_notes("Python pathlib", author="jarvis")
    assert len(jarvis_only) == 1
    assert jarvis_only[0].author == "jarvis"


def test_read_note_missing_raises():
    with pytest.raises(FileNotFoundError):
        vault.read_note("jarvis/no-existe")


def test_wikilinks_extracted_from_content(_tmp_vault):
    note = vault.save_note(title="Con links", content="ver [[Otra Nota]] y [[Tercera|alias]]", author="jarvis")
    assert set(note.links) == {"Otra Nota", "Tercera"}

    loaded = vault.read_note(note.id)
    assert set(loaded.links) == {"Otra Nota", "Tercera"}


def test_delete_note_removes_file(_tmp_vault):
    note = vault.save_note(title="Borrame", content="x", author="human")
    vault.delete_note(note.id)

    with pytest.raises(FileNotFoundError):
        vault.read_note(note.id)


def test_save_note_update_by_id_preserves_created_timestamp(_tmp_vault):
    note = vault.save_note(title="Editable", content="v1", author="human")
    updated = vault.save_note(title="Editable", content="v2", author="human", note_id=note.id)

    assert updated.id == note.id
    assert updated.created == note.created
    assert vault.read_note(note.id).content == "v2"


def test_save_note_update_rejects_mismatched_author(_tmp_vault):
    note = vault.save_note(title="Solo humano", content="v1", author="human")
    with pytest.raises(ValueError):
        vault.save_note(title="Solo humano", content="v2", author="jarvis", note_id=note.id)


def test_build_graph_resolves_wikilinks_to_note_ids(_tmp_vault):
    a = vault.save_note(title="Nota A", content="ver [[Nota B]] para más", author="jarvis")
    b = vault.save_note(title="Nota B", content="sin links", author="human")

    graph = vault.build_graph()

    assert {n["id"] for n in graph["nodes"]} == {a.id, b.id}
    assert graph["edges"] == [{"source": a.id, "target": b.id}]


def test_build_graph_ignores_links_to_titles_that_do_not_exist(_tmp_vault):
    vault.save_note(title="Sola", content="ver [[Nota inexistente]]", author="human")

    graph = vault.build_graph()

    assert graph["edges"] == []


def test_build_graph_matches_titles_case_insensitively(_tmp_vault):
    a = vault.save_note(title="Nota A", content="ver [[nota b]]", author="jarvis")
    b = vault.save_note(title="Nota B", content="", author="human")

    graph = vault.build_graph()

    assert graph["edges"] == [{"source": a.id, "target": b.id}]


def test_build_graph_dedupes_mutual_links_into_one_edge(_tmp_vault):
    a = vault.save_note(title="Nota A", content="[[Nota B]]", author="jarvis")
    b = vault.save_note(title="Nota B", content="[[Nota A]]", author="human")

    graph = vault.build_graph()

    assert len(graph["edges"]) == 1
    assert {graph["edges"][0]["source"], graph["edges"][0]["target"]} == {a.id, b.id}


def test_build_graph_ignores_self_links(_tmp_vault):
    a = vault.save_note(title="Nota A", content="me referencio a mí misma: [[Nota A]]", author="jarvis")

    graph = vault.build_graph()

    assert graph["edges"] == []
