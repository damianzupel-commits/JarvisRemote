"""Tool `research_topic`: investigación web real que aprende al vault de
Obsidian (ver `app/obsidian/vault.py`).

Reusa el navegador Edge ya controlado por `app/tools/browser.py` (misma
página persistente, mismo `_ensure_page`) para buscar el tema en DuckDuckGo
(`html.duckduckgo.com`, la versión sin JS pensada para scraping) y visitar
hasta `max_pages` resultados reales, extrayendo el texto visible de cada
página con `browser_get_text`. El contenido de la nota que se guarda es ese
texto extraído (con la URL de cada fuente citada), nunca un resumen
inventado por el modelo -- así una nota de `research_topic` siempre es
trazable a páginas reales que de verdad se visitaron.

Antes de guardar, chequea el vault con `vault.find_related_notes` (búsqueda
semántica): si ya hay una nota con similitud muy alta, no crea una nota
nueva (evita contenido redundante) y devuelve la existente. Si hay notas
relacionadas pero no tan cubiertas, la nota nueva las linkea con
`[[wikilinks]]` en vez de quedar aislada del resto del grafo.
"""

from __future__ import annotations

from urllib.parse import parse_qs, quote_plus, urlparse

from playwright.async_api import Error as PlaywrightError

from ..obsidian import vault
from . import browser as browser_tool
from . import register_tool

_DEFAULT_MAX_PAGES = 4
_HARD_MAX_PAGES = 5
_MAX_CHARS_PER_PAGE = 3000

# Tope de líneas consecutivas "tipo menú de navegación" (cortas, sin
# puntuación de oración, sin caracteres de código) antes de considerarlas un
# bloque de navegación y colapsarlas -- ver `_strip_navigation_noise`.
_NAV_RUN_MIN_LINES = 6

# Umbral de similitud coseno desde el cual se considera que el vault YA
# cubre el tema lo suficiente como para no crear una nota nueva (más alto
# que `vault._SEMANTIC_MIN_SCORE`, que solo decide si linkear -- acá
# necesitamos confianza real de que es el mismo tema, no solo relacionado).
_ALREADY_COVERED_MIN_SCORE = 0.75


def _resolve_ddg_url(href: str) -> str | None:
    """DuckDuckGo (html.duckduckgo.com) envuelve cada resultado en un
    redirect propio (`//duckduckgo.com/l/?uddg=<url-real>&rut=...`) en vez de
    linkear directo -- hay que desenvolverlo para navegar a la página real."""
    if not href:
        return None
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com"):
        target = parse_qs(parsed.query).get("uddg")
        return target[0] if target else None
    if parsed.scheme in ("http", "https"):
        return href
    return None


async def _search_result_links(page, topic: str) -> list[tuple[str, str]]:
    search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(topic)}"
    await page.goto(search_url, wait_until="domcontentloaded")

    raw = await page.eval_on_selector_all(
        "a.result__a",
        "els => els.map(el => ({href: el.getAttribute('href'), text: el.textContent}))",
    )

    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        url = _resolve_ddg_url((item or {}).get("href") or "")
        if url is None or url in seen:
            continue
        seen.add(url)
        links.append((url, ((item or {}).get("text") or "").strip() or url))
    return links


def _looks_like_nav_line(line: str) -> bool:
    """True si una línea individual TIENE PINTA de ser parte de un menú de
    navegación / índice de sitio (corta, sin puntuación de oración, sin
    caracteres típicos de código) -- ver `_strip_navigation_noise`."""
    stripped = line.strip()
    if not stripped or len(stripped) > 80:
        return False
    if any(ch in stripped for ch in "{}();=<>"):
        return False  # tiene pinta de código, nunca es navegación
    return not stripped.endswith((".", ":", "?", "!"))


def _strip_navigation_noise(text: str, min_run: int = _NAV_RUN_MIN_LINES) -> str:
    """Colapsa corridas largas (>= `min_run` líneas seguidas) de líneas tipo
    menú/índice de sitio en un solo marcador, en vez de guardarlas todas.

    Bug real 2026-08-10, encontrado en un test real de creación de un mod de
    Fabric: `browser_get_text()` trae el texto VISIBLE completo de la página,
    que en sitios de documentación (wiki.fabricmc.net, docs.fabricmc.net)
    incluye un sidebar de navegación enorme -- decenas de líneas cortas tipo
    "Adding an Item", "Custom Item Tooltips", "Creating a Custom Portal" --
    intercaladas con el contenido real (código, explicaciones). Eso diluye
    la señal útil dentro del tope de `_MAX_CHARS_PER_PAGE`: en una corrida
    real, el código concreto que hacía falta (`Identifier.fromNamespaceAndPath`)
    terminó enterrado después de cientos de líneas de navegación. Acá se
    colapsan esas corridas ANTES de recortar por longitud, dejando más lugar
    real para el contenido sustancioso dentro del mismo presupuesto de
    caracteres. No toca código real: cualquier línea con caracteres típicos
    de código (`{`, `}`, `(`, `)`, `;`, `=`, `<`, `>`) nunca cuenta como
    navegación, así que un bloque de código con líneas cortas (ej. llaves de
    cierre apiladas) no se pierde."""
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        if _looks_like_nav_line(lines[i]):
            j = i
            while j < n and _looks_like_nav_line(lines[j]):
                j += 1
            if j - i >= min_run:
                out.append("[...enlaces de navegación del sitio omitidos...]")
                i = j
                continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


async def _visit_pages(candidates: list[tuple[str, str]], max_pages: int) -> list[dict]:
    visited: list[dict] = []
    for url, snippet_title in candidates:
        if len(visited) >= max_pages:
            break
        try:
            opened = await browser_tool.browser_open(url=url)
            text = (await browser_tool.browser_get_text())["text"].strip()
        except PlaywrightError:
            # Una página que no carga (timeout, DNS, bloqueo del sitio) no
            # debe tirar abajo toda la investigación -- se salta y se sigue
            # con la siguiente candidata real.
            continue
        if not text:
            continue
        text = _strip_navigation_noise(text)
        visited.append(
            {
                "url": opened["url"],
                "title": opened.get("title") or snippet_title,
                "text": text[:_MAX_CHARS_PER_PAGE],
            }
        )
    return visited


def _build_note_content(topic: str, visited: list[dict], related_titles: list[str], index_title: str) -> str:
    """Arma el Markdown de la nota con jerarquía real (## / ###), no un bloque
    de texto plano -- así se puede leer solo la sección que hace falta (ej.
    solo "## Fuentes" o una fuente puntual) en vez de la nota entera. La
    lista de wikilinks siempre incluye `index_title` (el hub de categoría,
    ver `vault.link_note_to_category_index`) además de las notas relacionadas
    que haya encontrado la búsqueda semántica -- así la nota nunca queda sin
    ningún link saliente, ni siquiera la primera de un tema nuevo."""
    parts = [f'Investigación automática de Jarvis sobre "{topic}", basada en {len(visited)} página(s) reales visitadas.']

    parts.append("\n## Fuentes")
    for page_data in visited:
        parts.append(f"\n### {page_data['title']}\nFuente: {page_data['url']}\n\n{page_data['text']}")

    related_links = list(dict.fromkeys([*related_titles, index_title]))
    parts.append("\n## Notas relacionadas\n" + "\n".join(f"- [[{title}]]" for title in related_links))
    return "\n".join(parts)


@register_tool(
    name="research_topic",
    description=(
        "Investiga un tema en la web de verdad (navega varias páginas reales con el navegador Edge "
        "automatizado, mismo que browser_open) y aprende lo que encuentra guardándolo como nota nueva "
        "en el vault de Obsidian, firmada como 'jarvis'. El contenido de la nota es texto extraído de "
        "verdad de esas páginas (con la fuente citada), nunca un resumen inventado. Antes de guardar, "
        "chequea el vault por notas relacionadas: si el tema ya está muy cubierto no crea nada nuevo "
        "(evita duplicar), y si hay notas relacionadas pero no tan cubiertas linkea la nota nueva a "
        "ellas con [[wikilinks]] (nunca queda una nota aislada del resto del vault). La nota queda "
        "organizada con encabezados (## Fuentes, ### cada página, ## Notas relacionadas), no como texto "
        "plano. Usar cuando el usuario pide investigar/aprender sobre algo puntual."
    ),
    parameters={
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "Tema a investigar (se usa como query de búsqueda y como título de la nota)."},
            "category": {
                "type": "string",
                "description": (
                    "Categoría temática principal del tema, una sola palabra/frase corta (ej. "
                    "'algoritmos', 'historia', 'redes'). Se usa para agrupar la nota con otras del mismo "
                    "tema en un índice común. Si no se manda, se guarda como 'general'."
                ),
            },
            "max_pages": {
                "type": "integer",
                "description": f"Máximo de páginas reales a visitar (default {_DEFAULT_MAX_PAGES}, tope {_HARD_MAX_PAGES}).",
            },
        },
        "required": ["topic"],
    },
)
async def research_topic(topic: str, max_pages: int = _DEFAULT_MAX_PAGES, category: str = "") -> dict:
    topic = topic.strip()
    if not topic:
        raise ValueError("'topic' no puede estar vacío")
    max_pages = max(1, min(int(max_pages), _HARD_MAX_PAGES))
    category = category.strip() or "general"

    related = vault.find_related_notes(topic, limit=5)
    if related and related[0][1] >= _ALREADY_COVERED_MIN_SCORE:
        note, score = related[0]
        return {
            "status": "already_covered",
            "topic": topic,
            "message": (
                f"El vault ya tiene una nota muy relacionada con '{topic}': '{note.title}' "
                f"({note.id}, similitud {score:.2f}). No se creó una nota nueva para evitar contenido redundante."
            ),
            "related_note": note.to_summary_dict(),
        }

    page = await browser_tool._ensure_page()
    candidates = await _search_result_links(page, topic)
    visited = await _visit_pages(candidates, max_pages)

    if not visited:
        return {
            "status": "no_pages_found",
            "topic": topic,
            "message": f"No se pudo extraer contenido real de ninguna página para '{topic}'. No se creó ninguna nota.",
        }

    index_note = vault.link_note_to_category_index(topic, category=category, author="jarvis")

    related_titles = [note.title for note, _ in related]
    content = _build_note_content(topic, visited, related_titles, index_note.title)
    note = vault.save_note(title=topic, content=content, author="jarvis", tags=["investigacion"], category=category)

    return {
        "status": "saved",
        "note": note.to_summary_dict(),
        "sources": [{"url": p["url"], "title": p["title"]} for p in visited],
        "linked_notes": [note.to_summary_dict() for note, _ in related],
        "category_index": index_note.to_summary_dict(),
    }
