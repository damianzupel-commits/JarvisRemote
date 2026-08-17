import pytest

from app.obsidian import embeddings


@pytest.fixture(autouse=True)
def _tmp_index(tmp_path, monkeypatch):
    monkeypatch.setattr(embeddings.settings, "obsidian_embeddings_path", str(tmp_path / "embeddings.json"))
    return tmp_path / "embeddings.json"


def test_cosine_similarity_identical_vectors_is_one():
    assert embeddings.cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert embeddings.cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_opposite_vectors_is_minus_one():
    assert embeddings.cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_cosine_similarity_handles_zero_vector_without_dividing_by_zero():
    assert embeddings.cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


def test_cosine_similarity_mismatched_dimensions_returns_zero():
    assert embeddings.cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0]) == 0.0


def test_get_embedding_empty_text_returns_none_without_calling_server():
    assert embeddings.get_embedding("   ") is None


def test_get_embedding_returns_none_when_server_unreachable(monkeypatch):
    monkeypatch.setattr(embeddings.settings, "embedding_base_url", "http://127.0.0.1:1")  # puerto que nadie escucha
    assert embeddings.get_embedding("hola") is None


def test_load_index_missing_file_returns_empty_dict(_tmp_index):
    assert embeddings.load_index() == {}


def test_save_and_load_index_roundtrip(_tmp_index):
    embeddings.save_index({"jarvis/nota": [0.1, 0.2, 0.3]})
    assert embeddings.load_index() == {"jarvis/nota": [0.1, 0.2, 0.3]}


def test_load_index_corrupt_file_returns_empty_dict(_tmp_index):
    _tmp_index.parent.mkdir(parents=True, exist_ok=True)
    _tmp_index.write_text("no es json{{{", encoding="utf-8")
    assert embeddings.load_index() == {}


def test_update_note_embedding_writes_vector_when_server_available(_tmp_index, monkeypatch):
    monkeypatch.setattr(embeddings, "get_embedding", lambda text: [1.0, 0.0])
    embeddings.update_note_embedding("jarvis/nota", "contenido")
    assert embeddings.load_index() == {"jarvis/nota": [1.0, 0.0]}


def test_update_note_embedding_is_noop_when_server_unavailable(_tmp_index, monkeypatch):
    monkeypatch.setattr(embeddings, "get_embedding", lambda text: None)
    embeddings.update_note_embedding("jarvis/nota", "contenido")
    assert embeddings.load_index() == {}


def test_remove_note_embedding_deletes_entry(_tmp_index):
    embeddings.save_index({"jarvis/a": [1.0], "jarvis/b": [2.0]})
    embeddings.remove_note_embedding("jarvis/a")
    assert embeddings.load_index() == {"jarvis/b": [2.0]}


def test_remove_note_embedding_missing_key_is_noop(_tmp_index):
    embeddings.save_index({"jarvis/b": [2.0]})
    embeddings.remove_note_embedding("jarvis/no-existe")
    assert embeddings.load_index() == {"jarvis/b": [2.0]}


def test_reindex_all_indexes_notes_with_successful_embeddings(_tmp_index, monkeypatch):
    monkeypatch.setattr(embeddings, "get_embedding", lambda text: [float(len(text)), 0.0])

    summary = embeddings.reindex_all([("jarvis/a", "hola"), ("jarvis/b", "mundo")])

    assert summary == {"indexed": 2, "skipped": 0}
    assert embeddings.load_index() == {"jarvis/a": [4.0, 0.0], "jarvis/b": [5.0, 0.0]}


def test_reindex_all_skips_notes_without_embedding_and_replaces_index(_tmp_index, monkeypatch):
    embeddings.save_index({"jarvis/viejo": [9.0, 9.0]})

    def fake_get_embedding(text: str):
        return None if text == "falla" else [1.0]

    monkeypatch.setattr(embeddings, "get_embedding", fake_get_embedding)

    summary = embeddings.reindex_all([("jarvis/ok", "bien"), ("jarvis/mal", "falla")])

    assert summary == {"indexed": 1, "skipped": 1}
    # El índice viejo se reemplaza entero -- no quedan entradas huérfanas de notas borradas.
    assert embeddings.load_index() == {"jarvis/ok": [1.0]}
