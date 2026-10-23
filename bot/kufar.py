import asyncio
import logging
import re
from urllib.parse import quote, urljoin

from playwright.async_api import Browser, Playwright, async_playwright

log = logging.getLogger("scraper")

BASE = "https://www.kufar.by"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

_EXTRACT_JS = """
els => els.map(a => {
  const q = s => a.querySelector(s);
  const t = q('h3[class*="styles_title"]');
  const p = q('span[class*="styles_price"]') || q('div[class*="styles_price_block"]');
  const i = q('img');
  const l = q('div[class*="styles_secondary"]');
  return {
    href:  a.getAttribute('href') || '',
    title: t ? t.innerText.trim() : '',
    price: p ? p.innerText.trim() : '',
    img:   i ? ([i.getAttribute('src'), i.getAttribute('data-src')].find(u => u && u.startsWith('http')) || '') : '',
    info:  l ? l.innerText.trim() : ''
  };
})
"""


def filter_stop_words(ads: list[dict], stop_words: list[str]) -> list[dict]:
    words = [w.strip().lower() for w in stop_words if w and w.strip()]
    if not words:
        return ads
    return [a for a in ads if not any(w in a["title"].lower() for w in words)]


class KufarScraper:
    """One shared headless Chromium for the whole bot (much lighter than one per search)."""

    def __init__(self, concurrency: int = 2):
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._lock = asyncio.Lock()
        self._sem = asyncio.Semaphore(concurrency)

    async def start(self) -> None:
        self._pw = await async_playwright().start()
        await self._launch()

    async def _launch(self) -> None:
        self._browser = await self._pw.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

    async def _get_browser(self) -> Browser:
        async with self._lock:
            if self._browser is None or not self._browser.is_connected():
                log.warning("browser is gone, restarting")
                try:
                    if self._browser:
                        await self._browser.close()
                except Exception:
                    pass
                await self._launch()
            return self._browser

    async def stop(self) -> None:
        try:
            if self._browser:
                await self._browser.close()
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass

    async def search(self, query: str, limit: int = 20, max_pages: int = 1) -> list[dict]:
        """Newest ads for a query. Returns [] on any failure (logged)."""
        async with self._sem:
            try:
                return await asyncio.wait_for(self._search(query, limit, max_pages), timeout=90)
            except Exception as e:
                log.error("search failed [%s]: %r", query, e)
                return []

    async def _search(self, query: str, limit: int, max_pages: int) -> list[dict]:
        browser = await self._get_browser()
        context = await browser.new_context(user_agent=USER_AGENT, locale="ru-RU")
        try:
            page = await context.new_page()
            # no images / media / fonts: the <img src> attribute is still in the DOM
            await page.route(
                "**/*",
                lambda route: route.abort()
                if route.request.resource_type in ("image", "media", "font")
                else route.continue_(),
            )
            ads: list[dict] = []
            seen: set[str] = set()
            encoded = quote(query.strip())

            for n in range(1, max_pages + 1):
                if len(ads) >= limit:
                    break
                url = f"{BASE}/l/r~belarus?query={encoded}&sort=lst.d&page={n}"
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                try:
                    await page.wait_for_selector(
                        'a[class*="styles_wrapper"]', state="attached", timeout=8000
                    )
                except Exception:
                    break  # no cards: end of results (or blocked)

                raw = await page.eval_on_selector_all('a[class*="styles_wrapper"]', _EXTRACT_JS)
                for r in raw:
                    href = r["href"]
                    m = re.search(r"/item/(\d+)", href)
                    if not m or m.group(1) in seen:
                        continue
                    seen.add(m.group(1))
                    img = r["img"] if r["img"].startswith("http") else None
                    ads.append({
                        "id": m.group(1),
                        "title": r["title"] or "Без названия",
                        "price": r["price"] or "Цена не указана",
                        "url": urljoin(BASE, href).split("?")[0],
                        "image": img,
                        "location": r["info"] or "Беларусь",
                    })
                    if len(ads) >= limit:
                        break
            return ads
        finally:
            await context.close()


scraper = KufarScraper()
