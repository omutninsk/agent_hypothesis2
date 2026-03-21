from __future__ import annotations

import json
import logging
import os
import tempfile
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.sandbox.manager import SandboxManager

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
}


class WebSearchInput(BaseModel):
    query: str = Field(description="Search query")
    max_results: int = Field(default=5, description="Max results to return")


def _format_results(results: list[dict]) -> str:
    lines = []
    for r in results:
        lines.append(f"**{r['title']}**\n{r['url']}\n{r['body']}")
    return "\n\n".join(lines) if lines else ""


async def _search_ddg(query: str, max_results: int) -> list[dict]:
    from ddgs import DDGS

    try:
        raw = DDGS().text(query, max_results=max_results)
        return [
            {"title": r["title"], "url": r["href"], "body": r["body"]}
            for r in raw
        ]
    except Exception as e:
        logger.warning("DDG search failed: %s", e)
        return []


async def _search_google(query: str, max_results: int) -> list[dict]:
    url = f"https://www.google.com/search?q={quote_plus(query)}&num={max_results}&hl=en"
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS, timeout=15, follow_redirects=True
        ) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            logger.warning("Google returned status %d", resp.status_code)
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        results = []
        for g in soup.select("div.g"):
            title_el = g.select_one("h3")
            link_el = g.select_one("a[href]")
            snippet_el = g.select_one("div.VwiC3b") or g.select_one(
                "[data-sncf]"
            )
            if not title_el or not link_el:
                continue
            href = link_el.get("href", "")
            if not href.startswith("http"):
                continue
            results.append(
                {
                    "title": title_el.get_text(strip=True),
                    "url": href,
                    "body": snippet_el.get_text(strip=True)
                    if snippet_el
                    else "",
                }
            )
            if len(results) >= max_results:
                break
        return results
    except Exception as e:
        logger.warning("Google search failed: %s", e)
        return []


async def _search_yandex(query: str, max_results: int) -> list[dict]:
    url = f"https://yandex.ru/search/?text={quote_plus(query)}&numdoc={max_results}"
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS, timeout=15, follow_redirects=True
        ) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            logger.warning("Yandex returned status %d", resp.status_code)
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        results = []
        for item in soup.select("li.serp-item"):
            link_el = item.select_one("h2 a") or item.select_one("a")
            snippet_el = item.select_one(
                ".OrganicTextContentSpan"
            ) or item.select_one(".text-container")
            if not link_el:
                continue
            href = link_el.get("href", "")
            if not href.startswith("http"):
                continue
            results.append(
                {
                    "title": link_el.get_text(strip=True),
                    "url": href,
                    "body": snippet_el.get_text(strip=True)
                    if snippet_el
                    else "",
                }
            )
            if len(results) >= max_results:
                break
        return results
    except Exception as e:
        logger.warning("Yandex search failed: %s", e)
        return []


async def _search_playwright(
    query: str, max_results: int, sandbox: SandboxManager
) -> list[dict]:
    script = f"""\
import json
from playwright.sync_api import sync_playwright

query = {json.dumps(query)}
max_results = {max_results}

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
    try:
        page = browser.new_page()
        page.goto(
            f"https://www.google.com/search?q={{query}}&num={{max_results}}&hl=en",
            timeout=30000,
        )
        page.wait_for_load_state("domcontentloaded")
        results = []
        for el in page.query_selector_all("div.g"):
            title_el = el.query_selector("h3")
            link_el = el.query_selector("a[href]")
            if not title_el or not link_el:
                continue
            href = link_el.get_attribute("href") or ""
            if not href.startswith("http"):
                continue
            snippet = ""
            snippet_el = el.query_selector("div.VwiC3b")
            if snippet_el:
                snippet = snippet_el.inner_text()
            results.append({{"title": title_el.inner_text(), "url": href, "body": snippet}})
            if len(results) >= max_results:
                break
        print(json.dumps(results, ensure_ascii=False))
    finally:
        browser.close()
"""
    workspace = tempfile.mkdtemp(prefix="websearch_")
    script_path = os.path.join(workspace, "_search.py")
    try:
        with open(script_path, "w") as f:
            f.write(script)
        result = await sandbox.execute(
            command="python /workspace/_search.py",
            workspace_path=workspace,
            timeout=60,
        )
        if result.exit_code == 0 and result.stdout.strip():
            return json.loads(result.stdout.strip())
        logger.warning(
            "Playwright search failed: exit=%d stderr=%s",
            result.exit_code,
            result.stderr[:500],
        )
        return []
    except Exception as e:
        logger.warning("Playwright search error: %s", e)
        return []
    finally:
        try:
            os.remove(script_path)
            os.rmdir(workspace)
        except OSError:
            pass


def make_web_search_tool(sandbox: SandboxManager):
    @tool(args_schema=WebSearchInput)
    async def web_search(query: str, max_results: int = 5) -> str:
        """Search the web using multiple backends (DuckDuckGo, Google, Yandex). Use to research APIs, find solutions, check documentation before coding."""
        # 1. DDG (fastest)
        results = await _search_ddg(query, max_results)
        if results:
            logger.info("web_search: DDG returned %d results", len(results))
            return _format_results(results)

        # 2. Google via httpx
        results = await _search_google(query, max_results)
        if results:
            logger.info(
                "web_search: Google (httpx) returned %d results", len(results)
            )
            return _format_results(results)

        # 3. Yandex via httpx
        results = await _search_yandex(query, max_results)
        if results:
            logger.info(
                "web_search: Yandex (httpx) returned %d results", len(results)
            )
            return _format_results(results)

        # 4. Google via playwright in sandbox
        results = await _search_playwright(query, max_results, sandbox)
        if results:
            logger.info(
                "web_search: Playwright returned %d results", len(results)
            )
            return _format_results(results)

        return "No results found."

    return web_search
