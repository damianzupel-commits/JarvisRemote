"""Tests de las tools de navegador (app/tools/browser.py). Nunca deben lanzar
un browser de verdad -- todo lo de playwright va mockeado."""

import pytest

from app.tools import browser


@pytest.fixture(autouse=True)
def _reset_browser_module_state():
    browser._playwright = None
    browser._browser = None
    browser._page = None
    yield
    browser._playwright = None
    browser._browser = None
    browser._page = None


class _FakePage:
    def __init__(self):
        self.closed = False
        self.url = "https://example.com"

    def is_closed(self):
        return self.closed

    async def title(self):
        return "Example"

    async def goto(self, url, wait_until=None):
        self.url = url


class _FakeContext:
    def __init__(self, page):
        self._page = page

    async def new_page(self):
        return self._page


class _FakeBrowser:
    def __init__(self, page):
        self._page = page
        self.closed = False

    async def new_context(self):
        return _FakeContext(self._page)

    async def close(self):
        self.closed = True


class _FakeChromium:
    def __init__(self):
        self.launch_calls: list[dict] = []
        self._page = _FakePage()

    async def launch(self, **kwargs):
        self.launch_calls.append(kwargs)
        return _FakeBrowser(self._page)


class _FakePlaywright:
    def __init__(self):
        self.chromium = _FakeChromium()

    async def stop(self):
        pass


class _FakeAsyncPlaywrightFactory:
    def __init__(self, pw: _FakePlaywright):
        self._pw = pw

    async def start(self):
        return self._pw


@pytest.mark.anyio
async def test_ensure_page_launches_via_the_system_edge_channel(monkeypatch):
    """Regresión del bug real del 26/07: lanzar el Chromium propio de
    Playwright (sin firmar) fallaba siempre en esta PC con "spawn UNKNOWN"
    (WinError 14001, confirmado por SideBySide event id 33 en el visor de
    eventos) -- el fix es usar el Edge del sistema (channel="msedge"), que sí
    está firmado y no choca con el antivirus."""
    fake_pw = _FakePlaywright()
    monkeypatch.setattr(browser, "async_playwright", lambda: _FakeAsyncPlaywrightFactory(fake_pw))

    page = await browser._ensure_page()

    assert page is fake_pw.chromium._page
    assert fake_pw.chromium.launch_calls == [{"channel": "msedge", "headless": browser.settings.browser_headless}]


@pytest.mark.anyio
async def test_ensure_page_reuses_the_existing_open_page(monkeypatch):
    fake_pw = _FakePlaywright()
    browser._playwright = fake_pw
    browser._browser = _FakeBrowser(fake_pw.chromium._page)
    browser._page = fake_pw.chromium._page

    page = await browser._ensure_page()

    assert page is fake_pw.chromium._page
    assert fake_pw.chromium.launch_calls == []  # no relanza si ya hay una página abierta


@pytest.mark.anyio
async def test_ensure_page_opens_a_fresh_page_when_the_previous_one_closed(monkeypatch):
    fake_pw = _FakePlaywright()
    old_page = _FakePage()
    old_page.closed = True
    browser._playwright = fake_pw
    browser._browser = _FakeBrowser(fake_pw.chromium._page)
    browser._page = old_page

    page = await browser._ensure_page()

    assert page is fake_pw.chromium._page
    assert fake_pw.chromium.launch_calls == []  # el browser ya estaba vivo, no lo relanza


@pytest.mark.anyio
async def test_browser_open_navigates_and_returns_url_and_title(monkeypatch):
    fake_pw = _FakePlaywright()
    monkeypatch.setattr(browser, "async_playwright", lambda: _FakeAsyncPlaywrightFactory(fake_pw))

    result = await browser.browser_open(url="https://www.youtube.com")

    assert result == {"url": "https://www.youtube.com", "title": "Example"}


@pytest.mark.anyio
async def test_browser_close_tears_down_browser_and_page(monkeypatch):
    fake_pw = _FakePlaywright()
    fake_browser = _FakeBrowser(fake_pw.chromium._page)
    browser._playwright = fake_pw
    browser._browser = fake_browser
    browser._page = fake_pw.chromium._page

    result = await browser.browser_close()

    assert result == {"closed": True}
    assert fake_browser.closed is True
    assert browser._browser is None
    assert browser._page is None
