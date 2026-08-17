"""Tests de research_topic (app/tools/research.py): investiga un tema
navegando páginas reales (vía app/tools/browser.py, mockeado -- nunca abre un
navegador de verdad) y guarda lo extraído como nota nueva en el vault. Reusa
el vault real en un tmp_path (como test_obsidian_vault.py) para verificar
contenido, wikilinks y el chequeo de "ya cubierto" contra datos reales, no
solo mocks del guardado."""

from urllib.parse import quote

import pytest
from playwright.async_api import Error as PlaywrightError

from app.obsidian import embeddings, vault
from app.tools import browser as browser_tool
from app.tools import research


def _ddg_href(target_url: str) -> str:
    return f"//duckduckgo.com/l/?uddg={quote(target_url, safe='')}&rut=abc123"


class _FakePage:
    def __init__(self, search_results: list[dict], page_content: dict[str, dict]):
        self.url = ""
        self._search_results = search_results
        self._page_content = page_content

    def is_closed(self) -> bool:
        return False

    async def goto(self, url, wait_until=None):
        self.url = url
        if url in self._page_content and self._page_content[url].get("raises"):
            raise PlaywrightError(f"no se pudo cargar {url}")

    async def title(self):
        return self._page_content.get(self.url, {}).get("title", "")

    async def inner_text(self, selector, timeout=None):
        return self._page_content.get(self.url, {}).get("text", "")

    async def eval_on_selector_all(self, selector, expression, arg=None):
        return self._search_results


@pytest.fixture(autouse=True)
def _tmp_vault(tmp_path, monkeypatch):
    monkeypatch.setattr(vault.settings, "obsidian_vault_path", str(tmp_path / "vault"))
    monkeypatch.setattr(embeddings.settings, "obsidian_embeddings_path", str(tmp_path / "embeddings.json"))
    return tmp_path / "vault"


@pytest.fixture(autouse=True)
def _reset_browser_module_state():
    browser_tool._playwright = None
    browser_tool._browser = None
    browser_tool._page = None
    yield
    browser_tool._playwright = None
    browser_tool._browser = None
    browser_tool._page = None


def _install_fake_page(search_results: list[dict], page_content: dict[str, dict]) -> _FakePage:
    fake_page = _FakePage(search_results, page_content)
    browser_tool._browser = object()  # sentinel no-None: alcanza para que _ensure_page no relance playwright
    browser_tool._page = fake_page
    return fake_page


# --- _resolve_ddg_url ---------------------------------------------------------


def test_resolve_ddg_url_unwraps_duckduckgo_redirect():
    href = _ddg_href("https://doc.rust-lang.org/book/ch04-00-understanding-ownership.html")
    assert research._resolve_ddg_url(href) == "https://doc.rust-lang.org/book/ch04-00-understanding-ownership.html"


def test_resolve_ddg_url_passes_through_direct_http_links():
    assert research._resolve_ddg_url("https://example.com/page") == "https://example.com/page"


def test_resolve_ddg_url_rejects_non_http_schemes():
    assert research._resolve_ddg_url("javascript:alert(1)") is None


def test_resolve_ddg_url_handles_empty_href():
    assert research._resolve_ddg_url("") is None


# --- _strip_navigation_noise ---------------------------------------------------


def test_looks_like_nav_line_flags_short_unpunctuated_lines():
    assert research._looks_like_nav_line("Adding an Item") is True
    assert research._looks_like_nav_line("Custom Item Tooltips") is True


def test_looks_like_nav_line_rejects_sentences_ending_in_punctuation():
    assert research._looks_like_nav_line("This is a real sentence about Fabric.") is False


def test_looks_like_nav_line_rejects_code_like_lines():
    # Bug real 2026-08-10: el heurístico de navegación NO debe comerse código
    # real solo porque la línea es corta -- una llave de cierre, una línea de
    # import, etc. tienen que sobrevivir siempre.
    assert research._looks_like_nav_line("}") is False
    assert research._looks_like_nav_line("import net.fabricmc.api.ModInitializer;") is False
    assert research._looks_like_nav_line("public class Foo {") is False


def test_looks_like_nav_line_rejects_blank_lines():
    assert research._looks_like_nav_line("") is False
    assert research._looks_like_nav_line("   ") is False


def test_looks_like_nav_line_rejects_very_long_lines():
    assert research._looks_like_nav_line("x" * 100) is False


def test_strip_navigation_noise_collapses_a_long_nav_block():
    # Bug real 2026-08-10: wiki.fabricmc.net/docs.fabricmc.net traen un sidebar
    # de navegación enorme (decenas de títulos de tutorial cortos) intercalado
    # con el contenido real -- eso diluía la señal útil dentro del tope de
    # caracteres por página, enterrando código real que sí hacía falta.
    nav_block = "\n".join(
        [
            "Introduction to Fabric and Modding",
            "Setting up a Development Environment",
            "Reading the Minecraft source",
            "Basic Conventions and Terminology",
            "Server and Client Side",
            "Creating a language file",
            "Adding an Item",
        ]
    )
    text = f"{nav_block}\n\nThis is the real explanation of how items work in Fabric.\n\npublic class ModItems {{\n}}\n"
    result = research._strip_navigation_noise(text)
    assert "[...enlaces de navegación del sitio omitidos...]" in result
    assert "Introduction to Fabric and Modding" not in result  # el bloque de nav quedó colapsado
    assert "This is the real explanation of how items work in Fabric." in result  # el contenido real sobrevive
    assert "public class ModItems" in result


def test_strip_navigation_noise_keeps_short_runs_of_short_lines_intact():
    # Una corrida CORTA de líneas breves (menos que el mínimo) no se considera
    # navegación -- no hay que ser demasiado agresivo con textos cortos legítimos.
    text = "Título\nSubtítulo\n\nTexto real de la página con una explicación larga y normal."
    result = research._strip_navigation_noise(text)
    assert result == text  # sin cambios, la corrida es demasiado corta para colapsarse


def test_strip_navigation_noise_never_touches_code_blocks():
    code = "\n".join(
        [
            "public class Foo {",
            "    public void bar() {",
            "    }",
            "}",
            "}",
            "}",
            "}",
            "}",
        ]
    )
    result = research._strip_navigation_noise(code)
    assert result == code  # las llaves de cierre nunca cuentan como navegación (ver _looks_like_nav_line)


# --- research_topic ------------------------------------------------------------


@pytest.mark.anyio
async def test_research_topic_saves_note_with_real_extracted_text_and_sources():
    url_a = "https://example.com/rust-ownership"
    url_b = "https://example.org/rust-borrowing"
    search_results = [
        {"href": _ddg_href(url_a), "text": "Rust ownership guide"},
        {"href": _ddg_href(url_b), "text": "Rust borrowing guide"},
    ]
    page_content = {
        url_a: {"title": "Understanding Ownership", "text": "Ownership is Rust's most unique feature."},
        url_b: {"title": "Borrowing Explained", "text": "References let you refer to a value without taking ownership."},
    }
    _install_fake_page(search_results, page_content)

    result = await research.research_topic(topic="Rust ownership", max_pages=4)

    assert result["status"] == "saved"
    assert {s["url"] for s in result["sources"]} == {url_a, url_b}

    note = vault.read_note(result["note"]["id"])
    assert "Ownership is Rust's most unique feature." in note.content
    assert "References let you refer to a value without taking ownership." in note.content
    assert url_a in note.content and url_b in note.content
    assert note.author == "jarvis"
    assert "investigacion" in note.tags
    # Encabezados jerárquicos, no un bloque de texto plano -- ## agrupa la
    # sección de fuentes, ### separa cada página dentro de esa sección.
    assert "## Fuentes" in note.content
    assert "### Understanding Ownership" in note.content
    assert "### Borrowing Explained" in note.content
    assert "## Notas relacionadas" in note.content
    # Sin categoría explícita, cae en 'general' -- y por construcción linkea
    # al índice de esa categoría, así nunca queda sin ningún link saliente.
    assert note.category == "general"
    assert "[[Índice: general]]" in note.content
    assert result["category_index"]["title"] == "Índice: general"


@pytest.mark.anyio
async def test_research_topic_respects_max_pages_limit():
    urls = [f"https://example.com/page{i}" for i in range(4)]
    search_results = [{"href": _ddg_href(u), "text": f"resultado {i}"} for i, u in enumerate(urls)]
    page_content = {u: {"title": f"Página {i}", "text": f"contenido real {i}"} for i, u in enumerate(urls)}
    _install_fake_page(search_results, page_content)

    result = await research.research_topic(topic="tema con muchos resultados", max_pages=2)

    assert len(result["sources"]) == 2


@pytest.mark.anyio
async def test_research_topic_clamps_max_pages_above_hard_limit():
    urls = [f"https://example.com/page{i}" for i in range(10)]
    search_results = [{"href": _ddg_href(u), "text": f"resultado {i}"} for i, u in enumerate(urls)]
    page_content = {u: {"title": f"Página {i}", "text": f"contenido real {i}"} for i, u in enumerate(urls)}
    _install_fake_page(search_results, page_content)

    result = await research.research_topic(topic="tema", max_pages=999)

    assert len(result["sources"]) == research._HARD_MAX_PAGES


@pytest.mark.anyio
async def test_research_topic_dedupes_repeated_search_result_urls():
    url = "https://example.com/same-page"
    search_results = [
        {"href": _ddg_href(url), "text": "resultado 1"},
        {"href": _ddg_href(url), "text": "resultado repetido"},
    ]
    page_content = {url: {"title": "Página", "text": "contenido real"}}
    _install_fake_page(search_results, page_content)

    result = await research.research_topic(topic="tema duplicado", max_pages=4)

    assert len(result["sources"]) == 1


@pytest.mark.anyio
async def test_research_topic_skips_pages_that_fail_to_load_and_keeps_the_rest():
    broken_url = "https://example.com/broken"
    ok_url = "https://example.com/ok"
    search_results = [
        {"href": _ddg_href(broken_url), "text": "rota"},
        {"href": _ddg_href(ok_url), "text": "funciona"},
    ]
    page_content = {
        broken_url: {"raises": True},
        ok_url: {"title": "Funciona", "text": "contenido real que sí carga"},
    }
    _install_fake_page(search_results, page_content)

    result = await research.research_topic(topic="tema con una página rota", max_pages=4)

    assert result["status"] == "saved"
    assert [s["url"] for s in result["sources"]] == [ok_url]


@pytest.mark.anyio
async def test_research_topic_returns_no_pages_found_status_when_every_page_fails():
    broken_url = "https://example.com/broken"
    search_results = [{"href": _ddg_href(broken_url), "text": "rota"}]
    page_content = {broken_url: {"raises": True}}
    _install_fake_page(search_results, page_content)

    result = await research.research_topic(topic="tema sin páginas disponibles", max_pages=4)

    assert result["status"] == "no_pages_found"
    assert vault.list_notes() == []


@pytest.mark.anyio
async def test_research_topic_rejects_blank_topic():
    with pytest.raises(ValueError):
        await research.research_topic(topic="   ")


@pytest.mark.anyio
async def test_research_topic_links_new_note_to_related_existing_notes(monkeypatch):
    # Vectores elegidos para dar coseno ~0.71 -- por encima de
    # `vault._SEMANTIC_MIN_SCORE` (0.4, alcanza para linkear) pero por debajo
    # de `research._ALREADY_COVERED_MIN_SCORE` (0.75, alcanza para no crear
    # nada nuevo), así el test ejercita el camino de "relacionado pero no
    # tan cubierto" y no el de "already_covered".
    existing_vector = [1.0, 1.0]
    query_vector = [1.0, 0.0]

    def fake_get_embedding(text: str):
        if "Ownership básico en Rust" in text:
            return existing_vector
        return query_vector

    monkeypatch.setattr(embeddings, "get_embedding", fake_get_embedding)
    vault.save_note(title="Ownership básico en Rust", content="apuntes previos sobre ownership", author="jarvis")

    url = "https://example.com/rust-ownership-deep-dive"
    search_results = [{"href": _ddg_href(url), "text": "deep dive"}]
    page_content = {url: {"title": "Deep dive", "text": "contenido real sobre ownership avanzado"}}
    _install_fake_page(search_results, page_content)

    result = await research.research_topic(topic="Rust ownership avanzado", max_pages=4)

    assert result["status"] == "saved"
    assert any(n["title"] == "Ownership básico en Rust" for n in result["linked_notes"])
    note = vault.read_note(result["note"]["id"])
    assert "[[Ownership básico en Rust]]" in note.content


@pytest.mark.anyio
async def test_research_topic_uses_explicit_category_and_creates_its_index():
    url = "https://example.com/dijkstra"
    search_results = [{"href": _ddg_href(url), "text": "dijkstra"}]
    page_content = {url: {"title": "Dijkstra's algorithm", "text": "Finds shortest paths from a source node."}}
    _install_fake_page(search_results, page_content)

    result = await research.research_topic(topic="Algoritmo de Dijkstra", max_pages=4, category="algoritmos")

    assert result["status"] == "saved"
    note = vault.read_note(result["note"]["id"])
    assert note.category == "algoritmos"
    assert "[[Índice: algoritmos]]" in note.content

    index_note = vault.read_note(result["category_index"]["id"])
    assert index_note.title == "Índice: algoritmos"
    assert "- [[Algoritmo de Dijkstra]]" in index_note.content


@pytest.mark.anyio
async def test_research_topic_reuses_and_extends_existing_category_index():
    url_a = "https://example.com/a"
    url_b = "https://example.com/b"
    page_content = {
        url_a: {"title": "A", "text": "contenido real A"},
        url_b: {"title": "B", "text": "contenido real B"},
    }

    _install_fake_page([{"href": _ddg_href(url_a), "text": "a"}], page_content)
    first = await research.research_topic(topic="Primer tema de algoritmos", max_pages=4, category="algoritmos")

    _install_fake_page([{"href": _ddg_href(url_b), "text": "b"}], page_content)
    second = await research.research_topic(topic="Segundo tema de algoritmos", max_pages=4, category="algoritmos")

    # Las dos notas comparten el MISMO índice de categoría (no se duplica).
    assert first["category_index"]["id"] == second["category_index"]["id"]

    index_note = vault.read_note(second["category_index"]["id"])
    assert "- [[Primer tema de algoritmos]]" in index_note.content
    assert "- [[Segundo tema de algoritmos]]" in index_note.content

    # El grafo real conecta ambas notas al índice -- ninguna quedó huérfana,
    # aunque no tengan nada semánticamente en común entre sí.
    graph = vault.build_graph()
    edge_pairs = {frozenset((e["source"], e["target"])) for e in graph["edges"]}
    assert frozenset((first["note"]["id"], first["category_index"]["id"])) in edge_pairs
    assert frozenset((second["note"]["id"], second["category_index"]["id"])) in edge_pairs


@pytest.mark.anyio
async def test_research_topic_defaults_category_to_general_when_blank():
    url = "https://example.com/x"
    search_results = [{"href": _ddg_href(url), "text": "x"}]
    page_content = {url: {"title": "X", "text": "contenido real x"}}
    _install_fake_page(search_results, page_content)

    result = await research.research_topic(topic="tema sin categoria", max_pages=4, category="   ")

    assert result["note"]["category"] == "general"


@pytest.mark.anyio
async def test_research_topic_skips_browsing_when_topic_already_well_covered(monkeypatch):
    def fake_find_related_notes(query, author=None, limit=5):
        existing = vault.save_note(title="Ya cubierto", content="nota existente muy relacionada", author="jarvis")
        return [(existing, 0.9)]

    monkeypatch.setattr(vault, "find_related_notes", fake_find_related_notes)

    async def _fail_if_called():
        raise AssertionError("no debería navegar si el tema ya está cubierto")

    monkeypatch.setattr(browser_tool, "_ensure_page", _fail_if_called)

    result = await research.research_topic(topic="tema ya cubierto", max_pages=4)

    assert result["status"] == "already_covered"
    assert result["related_note"]["title"] == "Ya cubierto"
    # Solo debe existir la nota preexistente -- no se creó una nueva.
    assert len(vault.list_notes(author="jarvis")) == 1
