import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.obsidian import vault

client = TestClient(app)
AUTH = {"Authorization": f"Bearer {settings.api_key}"}


@pytest.fixture(autouse=True)
def _tmp_vault(tmp_path, monkeypatch):
    monkeypatch.setattr(vault.settings, "obsidian_vault_path", str(tmp_path / "vault"))


def test_list_notes_requires_auth():
    resp = client.get("/api/obsidian/notes")
    assert resp.status_code == 401


def test_create_note_is_always_human_authored():
    resp = client.post(
        "/api/obsidian/notes",
        json={"title": "Nota nueva", "content": "contenido", "tags": ["x"]},
        headers=AUTH,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["author"] == "human"
    assert body["id"] == "human/nota-nueva"


def test_list_notes_returns_created_note():
    client.post("/api/obsidian/notes", json={"title": "N1", "content": "c"}, headers=AUTH)

    resp = client.get("/api/obsidian/notes", headers=AUTH)
    titles = [n["title"] for n in resp.json()["notes"]]
    assert "N1" in titles


def test_graph_requires_auth():
    resp = client.get("/api/obsidian/graph")
    assert resp.status_code == 401


def test_graph_returns_nodes_and_edges():
    client.post("/api/obsidian/notes", json={"title": "Origen", "content": "ver [[Destino]]"}, headers=AUTH)
    client.post("/api/obsidian/notes", json={"title": "Destino", "content": ""}, headers=AUTH)

    resp = client.get("/api/obsidian/graph", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    titles = {n["title"] for n in body["nodes"]}
    assert {"Origen", "Destino"} <= titles
    assert len(body["edges"]) == 1


def test_get_note_returns_full_content():
    create = client.post("/api/obsidian/notes", json={"title": "N2", "content": "contenido completo"}, headers=AUTH)
    note_id = create.json()["id"]
    author, slug = note_id.split("/", 1)

    resp = client.get(f"/api/obsidian/notes/{author}/{slug}", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["content"] == "contenido completo"


def test_get_note_404_when_missing():
    resp = client.get("/api/obsidian/notes/human/no-existe", headers=AUTH)
    assert resp.status_code == 404


def test_delete_note_removes_it():
    create = client.post("/api/obsidian/notes", json={"title": "N3", "content": "c"}, headers=AUTH)
    note_id = create.json()["id"]
    author, slug = note_id.split("/", 1)

    resp = client.delete(f"/api/obsidian/notes/{author}/{slug}", headers=AUTH)
    assert resp.status_code == 200

    resp = client.get(f"/api/obsidian/notes/{author}/{slug}", headers=AUTH)
    assert resp.status_code == 404


def test_delete_note_rejects_jarvis_author():
    vault.save_note(title="De Jarvis", content="c", author="jarvis")

    resp = client.delete("/api/obsidian/notes/jarvis/de-jarvis", headers=AUTH)
    assert resp.status_code == 403
