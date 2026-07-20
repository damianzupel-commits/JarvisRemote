"""Tools de control del navegador (browsing automation) via Playwright.

Se mantiene una única página de Chromium viva entre llamadas (lazy-launched la
primera vez que se usa una tool de browser), para que el agente pueda hacer
open -> click -> get_text -> ... en varios turnos sin perder el estado de la página.
"""

from typing import Optional

from playwright.async_api import Browser, Page, Playwright, async_playwright

from ..config import settings
from . import register_tool

_playwright: Optional[Playwright] = None
_browser: Optional[Browser] = None
_page: Optional[Page] = None


async def _ensure_page() -> Page:
    global _playwright, _browser, _page
    if _page is None or _page.is_closed():
        if _playwright is None:
            _playwright = await async_playwright().start()
        if _browser is None:
            _browser = await _playwright.chromium.launch(headless=settings.browser_headless)
        context = await _browser.new_context()
        _page = await context.new_page()
    return _page


@register_tool(
    name="browser_open",
    description="Abre una URL en el navegador automatizado (crea el navegador si no está corriendo).",
    parameters={
        "type": "object",
        "properties": {"url": {"type": "string", "description": "URL completa a abrir."}},
        "required": ["url"],
    },
)
async def browser_open(url: str) -> dict:
    page = await _ensure_page()
    await page.goto(url, wait_until="domcontentloaded")
    return {"url": page.url, "title": await page.title()}


@register_tool(
    name="browser_click",
    description="Hace click en el primer elemento que matchee el selector CSS dado.",
    parameters={
        "type": "object",
        "properties": {"selector": {"type": "string", "description": "Selector CSS."}},
        "required": ["selector"],
    },
)
async def browser_click(selector: str) -> dict:
    page = await _ensure_page()
    await page.click(selector, timeout=5000)
    return {"clicked": selector, "url": page.url}


@register_tool(
    name="browser_type",
    description="Escribe texto en un input/textarea que matchee el selector CSS dado.",
    parameters={
        "type": "object",
        "properties": {
            "selector": {"type": "string", "description": "Selector CSS del campo."},
            "text": {"type": "string", "description": "Texto a escribir."},
            "submit": {
                "type": "boolean",
                "description": "Si es true, presiona Enter después de escribir. Default false.",
            },
        },
        "required": ["selector", "text"],
    },
)
async def browser_type(selector: str, text: str, submit: bool = False) -> dict:
    page = await _ensure_page()
    await page.fill(selector, text, timeout=5000)
    if submit:
        await page.press(selector, "Enter")
    return {"selector": selector, "submitted": submit}


@register_tool(
    name="browser_get_text",
    description="Devuelve el texto visible de la página o de un elemento puntual.",
    parameters={
        "type": "object",
        "properties": {
            "selector": {
                "type": "string",
                "description": "Selector CSS del elemento (default 'body', es decir toda la página).",
            }
        },
        "required": [],
    },
)
async def browser_get_text(selector: str = "body") -> dict:
    page = await _ensure_page()
    text = await page.inner_text(selector, timeout=5000)
    max_chars = 8000
    return {"text": text[:max_chars], "truncated": len(text) > max_chars}


@register_tool(
    name="browser_screenshot",
    description="Saca una captura de pantalla de la página actual y la guarda en disco.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Ruta donde guardar el PNG (default 'last_screenshot.png').",
            }
        },
        "required": [],
    },
)
async def browser_screenshot(path: str = "last_screenshot.png") -> dict:
    page = await _ensure_page()
    await page.screenshot(path=path)
    return {"screenshot_path": path}


@register_tool(
    name="browser_close",
    description="Cierra el navegador automatizado y libera los recursos.",
    parameters={"type": "object", "properties": {}, "required": []},
)
async def browser_close() -> dict:
    global _browser, _page
    if _browser is not None:
        await _browser.close()
        _browser = None
        _page = None
    return {"closed": True}
