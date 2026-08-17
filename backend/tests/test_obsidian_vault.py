import pytest

from app.obsidian import embeddings, vault
from app.obsidian.embeddings import get_embedding as _real_get_embedding


@pytest.fixture(autouse=True)
def _tmp_vault(tmp_path, monkeypatch):
    monkeypatch.setattr(vault.settings, "obsidian_vault_path", str(tmp_path / "vault"))
    monkeypatch.setattr(embeddings.settings, "obsidian_embeddings_path", str(tmp_path / "embeddings.json"))
    return tmp_path / "vault"


def test_save_note_writes_markdown_with_frontmatter(_tmp_vault):
    note = vault.save_note(title="Primera nota", content="contenido de prueba", author="jarvis", tags=["idea"])

    assert note.id == "jarvis/primera-nota"
    path = _tmp_vault / "jarvis" / "primera-nota.md"
    assert path.is_file()
    raw = path.read_text(encoding="utf-8")
    assert "author: jarvis" in raw
    assert "contenido de prueba" in raw


def test_save_note_persists_category_in_frontmatter(_tmp_vault):
    note = vault.save_note(title="Con categoría", content="x", author="jarvis", category="algoritmos")

    assert note.category == "algoritmos"
    assert vault.read_note(note.id).category == "algoritmos"


def test_save_note_defaults_category_to_empty_string(_tmp_vault):
    note = vault.save_note(title="Sin categoría", content="x", author="jarvis")

    assert note.category == ""
    assert vault.read_note(note.id).category == ""


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


# --- Búsqueda semántica -----------------------------------------------------
#
# El fixture autouse `_no_real_embeddings` en conftest.py deja
# `embeddings.get_embedding` devolviendo `None` por default (sin red) -- por
# eso los tests de arriba (keyword overlap puro) siguen pasando sin cambios:
# sin vector de query, search_notes cae 100% al camino de keyword, igual que
# antes de este módulo existir. Los tests de acá abajo prueban la capa
# semántica explícitamente, inyectando vectores fake (deterministas, sin
# red) salvo el último, que es el único que pega contra el LM Studio real de
# esta máquina y se salta solo si no está disponible.


def test_search_notes_finds_semantically_related_note_with_zero_word_overlap(_tmp_vault, monkeypatch):
    # Vectores fake armados a mano: la nota de autenticación queda cerca de
    # la query aunque no comparten ni una palabra; la de la receta queda
    # ortogonal (nada que ver). Esto prueba la lógica de ranking/umbral de
    # vault.search_notes, no la calidad de un modelo real (eso lo cubre el
    # test de integración de más abajo).
    auth_vector = [0.9, 0.1, 0.0]
    unrelated_vector = [0.0, 0.0, 1.0]
    query_vector = [1.0, 0.0, 0.0]

    def fake_get_embedding(text: str):
        if text == "bug de login":
            return query_vector
        if "Falla de autenticación" in text:
            return auth_vector
        return unrelated_vector

    monkeypatch.setattr(embeddings, "get_embedding", fake_get_embedding)

    vault.save_note(title="Falla de autenticación", content="el token no se valida bien al iniciar sesión", author="jarvis")
    # Título y contenido elegidos para no compartir ni una palabra (ni
    # siquiera un stopword como "de") con la query ni con la otra nota --
    # así el único motivo por el que la primera nota puede aparecer es la
    # similitud semántica, no un empate casual de keyword overlap.
    vault.save_note(title="Receta casera con harina y sal", content="agua, levadura, sal y tiempo para leudar", author="jarvis")

    results = vault.search_notes("bug de login")

    assert [n.title for n in results] == ["Falla de autenticación"]


def test_search_notes_orders_semantic_matches_above_keyword_only_matches(_tmp_vault, monkeypatch):
    query_vector = [1.0, 0.0]
    close_vector = [1.0, 0.0]

    # "Nota semántica" se guarda con embedding real en el índice.
    monkeypatch.setattr(embeddings, "get_embedding", lambda text: close_vector)
    vault.save_note(title="Nota semántica", content="contenido relacionado", author="jarvis")

    # "Nota keyword" no logra indexarse (simula LM Studio caído en ese momento)
    # pero comparte palabras con la query -- debe seguir apareciendo (fallback),
    # por debajo de la nota con match semántico real.
    monkeypatch.setattr(embeddings, "get_embedding", lambda text: None)
    vault.save_note(title="Nota keyword", content="nota semantica de respaldo", author="jarvis")

    # Al buscar, el servidor de embeddings ya volvió: solo se necesita el
    # vector de la query, los de las notas ya indexadas se leen del índice.
    monkeypatch.setattr(embeddings, "get_embedding", lambda text: query_vector)
    results = vault.search_notes("nota semantica")

    assert [n.title for n in results] == ["Nota semántica", "Nota keyword"]


def test_search_notes_ranks_curated_note_above_investigacion_note_at_equal_similarity(_tmp_vault, monkeypatch):
    # Bug real 2026-08-10 (test v5 del mod de Fabric): una nota nueva de
    # research_topic (tag "investigacion"), con título calcado de la query
    # que la generó, rankeó por delante de una nota más específica y curada
    # sobre el mismo tema -- el modelo nunca llegó a leer la nota específica
    # que sí tenía la respuesta. Con la MISMA similitud semántica exacta, la
    # nota sin el tag "investigacion" tiene que ganar el desempate.
    same_vector = [1.0, 0.0]
    monkeypatch.setattr(embeddings, "get_embedding", lambda text: same_vector)

    vault.save_note(
        title="Nota de investigación genérica",
        content="volcado crudo de research_topic",
        author="jarvis",
        tags=["investigacion"],
    )
    vault.save_note(
        title="Nota curada específica",
        content="guía puntual escrita a mano",
        author="jarvis",
        tags=["playbook"],
    )

    results = vault.search_notes("tema en común")

    assert [n.title for n in results] == ["Nota curada específica", "Nota de investigación genérica"]


def test_find_related_notes_does_not_apply_the_investigacion_penalty(_tmp_vault, monkeypatch):
    # `find_related_notes` la usa `research_topic` para decidir si un tema ya
    # está cubierto (ver _ALREADY_COVERED_MIN_SCORE) -- ahí necesita el score
    # real sin ajustar, no el penalizado de `search_notes` (penalizar de más
    # haría que un tema investigado antes parezca "menos cubierto" de lo que
    # está, generando notas duplicadas de research_topic sobre lo mismo).
    same_vector = [1.0, 0.0]
    monkeypatch.setattr(embeddings, "get_embedding", lambda text: same_vector)

    vault.save_note(
        title="Nota de investigación genérica",
        content="volcado crudo de research_topic",
        author="jarvis",
        tags=["investigacion"],
    )

    related = vault.find_related_notes("tema en común")

    assert len(related) == 1
    note, score = related[0]
    assert score == pytest.approx(1.0)  # sin penalizar


def test_search_notes_falls_back_to_pure_keyword_when_embeddings_server_down(_tmp_vault, monkeypatch):
    monkeypatch.setattr(embeddings, "get_embedding", lambda text: None)  # simula LM Studio caído

    vault.save_note(title="Ollama en GPU AMD", content="usa Vulkan no ROCm", author="jarvis")
    vault.save_note(title="Otra cosa", content="no relacionado", author="jarvis")

    results = vault.search_notes("Ollama GPU Vulkan")

    assert len(results) == 1
    assert results[0].title == "Ollama en GPU AMD"


def test_delete_note_removes_its_embedding(_tmp_vault, monkeypatch):
    monkeypatch.setattr(embeddings, "get_embedding", lambda text: [1.0, 0.0])
    note = vault.save_note(title="Borrame", content="x", author="jarvis")

    assert note.id in embeddings.load_index()
    vault.delete_note(note.id)
    assert note.id not in embeddings.load_index()


def test_reindex_all_backfills_embeddings_for_existing_notes(_tmp_vault, monkeypatch):
    # Las notas se guardan sin embedding (server caído durante el save)...
    monkeypatch.setattr(embeddings, "get_embedding", lambda text: None)
    vault.save_note(title="Nota vieja 1", content="contenido 1", author="jarvis")
    vault.save_note(title="Nota vieja 2", content="contenido 2", author="human")
    assert embeddings.load_index() == {}

    # ...y reindex_all() hace el backfill una vez que el server vuelve.
    monkeypatch.setattr(embeddings, "get_embedding", lambda text: [1.0, 0.0])
    summary = vault.reindex_all()

    assert summary == {"indexed": 2, "skipped": 0}
    index = embeddings.load_index()
    assert set(index.keys()) == {"jarvis/nota-vieja-1", "human/nota-vieja-2"}


# --- find_related_notes (usado por research_topic) --------------------------


def test_find_related_notes_returns_semantic_score_alongside_notes(_tmp_vault, monkeypatch):
    query_vector = [1.0, 0.0]
    close_vector = [0.9, 0.1]

    def fake_get_embedding(text: str):
        if "Tema" in text:
            return close_vector
        return query_vector

    monkeypatch.setattr(embeddings, "get_embedding", fake_get_embedding)
    vault.save_note(title="Tema relacionado", content="contenido", author="jarvis")

    results = vault.find_related_notes("consulta")

    assert len(results) == 1
    note, score = results[0]
    assert note.title == "Tema relacionado"
    assert score == pytest.approx(embeddings.cosine_similarity(query_vector, close_vector))


def test_find_related_notes_scores_keyword_only_matches_as_zero(_tmp_vault, monkeypatch):
    monkeypatch.setattr(embeddings, "get_embedding", lambda text: None)  # LM Studio caído
    vault.save_note(title="Ollama en GPU AMD", content="usa Vulkan no ROCm", author="jarvis")

    results = vault.find_related_notes("Ollama GPU Vulkan")

    assert len(results) == 1
    note, score = results[0]
    assert note.title == "Ollama en GPU AMD"
    assert score == 0.0


def test_find_related_notes_returns_empty_list_when_nothing_matches(_tmp_vault, monkeypatch):
    monkeypatch.setattr(embeddings, "get_embedding", lambda text: None)
    vault.save_note(title="Sin relación", content="contenido sin overlap", author="jarvis")

    assert vault.find_related_notes("tema completamente distinto xyz") == []


def test_find_related_notes_orders_by_score_descending(_tmp_vault, monkeypatch):
    query_vector = [1.0, 0.0]
    strong_vector = [1.0, 0.0]
    weak_vector = [0.6, 0.4]

    def fake_get_embedding(text: str):
        if "Fuerte" in text:
            return strong_vector
        if "Debil" in text:
            return weak_vector
        return query_vector

    monkeypatch.setattr(embeddings, "get_embedding", fake_get_embedding)
    vault.save_note(title="Debil", content="match parcial", author="jarvis")
    vault.save_note(title="Fuerte", content="match casi perfecto", author="jarvis")

    results = vault.find_related_notes("consulta")

    assert [note.title for note, _ in results] == ["Fuerte", "Debil"]


def test_find_related_notes_respects_limit(_tmp_vault, monkeypatch):
    monkeypatch.setattr(embeddings, "get_embedding", lambda text: None)
    for i in range(3):
        vault.save_note(title=f"Nota python {i}", content="python pathlib", author="jarvis")

    results = vault.find_related_notes("python pathlib", limit=2)

    assert len(results) == 2


# --- link_note_to_category_index (MOC/índice por categoría) -----------------


def test_link_note_to_category_index_creates_index_on_first_use(_tmp_vault):
    index_note = vault.link_note_to_category_index("Mi primera nota", category="algoritmos")

    assert index_note.title == "Índice: algoritmos"
    assert index_note.category == "algoritmos"
    assert "- [[Mi primera nota]]" in index_note.content
    assert vault.read_note(index_note.id).content == index_note.content


def test_link_note_to_category_index_appends_to_existing_index(_tmp_vault):
    first = vault.link_note_to_category_index("Nota uno", category="algoritmos")
    second = vault.link_note_to_category_index("Nota dos", category="algoritmos")

    assert first.id == second.id
    content = vault.read_note(second.id).content
    assert "- [[Nota uno]]" in content
    assert "- [[Nota dos]]" in content


def test_link_note_to_category_index_is_idempotent_for_the_same_note(_tmp_vault):
    vault.link_note_to_category_index("Nota repetida", category="algoritmos")
    vault.link_note_to_category_index("Nota repetida", category="algoritmos")

    content = vault.read_note("jarvis/indice-algoritmos").content
    assert content.count("[[Nota repetida]]") == 1


def test_link_note_to_category_index_keeps_separate_indexes_per_category(_tmp_vault):
    vault.link_note_to_category_index("Nota A", category="algoritmos")
    vault.link_note_to_category_index("Nota B", category="historia")

    algoritmos_index = vault.read_note("jarvis/indice-algoritmos")
    historia_index = vault.read_note("jarvis/indice-historia")
    assert "[[Nota A]]" in algoritmos_index.content
    assert "[[Nota B]]" not in algoritmos_index.content
    assert "[[Nota B]]" in historia_index.content


def _lmstudio_embeddings_reachable() -> bool:
    return _real_get_embedding("ping de disponibilidad") is not None


@pytest.mark.skipif(
    not _lmstudio_embeddings_reachable(),
    reason="requiere LM Studio real corriendo en localhost:1234 con un modelo de embeddings cargado",
)
def test_search_notes_relates_semantically_similar_notes_with_real_local_model(_tmp_vault, monkeypatch):
    """Único test que pega contra el LM Studio real de esta máquina (no un
    fake) -- prueba que dos frases con significado similar pero palabras
    totalmente distintas se relacionan de verdad, no solo que la lógica de
    merge/ranking funciona con vectores inventados."""
    monkeypatch.setattr(embeddings, "get_embedding", _real_get_embedding)

    vault.save_note(
        title="Horario preferido para reuniones de equipo",
        content="Prefiero que las reuniones de equipo arranquen temprano a la mañana, no me gusta juntarme tarde en el día.",
        author="jarvis",
    )
    vault.save_note(
        title="Receta de pan casero",
        content="Para el pan casero hace falta harina, agua, sal y levadura, y dejar leudar la masa un buen rato.",
        author="jarvis",
    )

    results = vault.search_notes("¿A qué hora del día le gusta juntarse el equipo para reunirse?")

    assert len(results) >= 1
    assert results[0].title == "Horario preferido para reuniones de equipo"
