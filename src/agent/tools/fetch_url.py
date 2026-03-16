from __future__ import annotations

import json
import logging
import os
import re
import tempfile

import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.sandbox.manager import SandboxManager

logger = logging.getLogger(__name__)

_MAX_TEXT_LENGTH = 6000

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class FetchUrlInput(BaseModel):
    url: str = Field(description="URL of the web page to read")


def _extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    content = soup.select_one("article") or soup.select_one("main") or soup.body
    if content is None:
        return ""

    text = content.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:_MAX_TEXT_LENGTH]


async def _fetch_with_httpx(url: str) -> str:
    async with httpx.AsyncClient(
        headers={"User-Agent": _USER_AGENT},
        timeout=15,
        follow_redirects=True,
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type and "text/plain" not in content_type:
            return ""
        return _extract_text(resp.text)


async def _fetch_with_playwright(url: str, sandbox: SandboxManager) -> str:
    script = f"""\
import json
from playwright.sync_api import sync_playwright

url = {json.dumps(url)}

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
    try:
        page = browser.new_page()
        page.goto(url, timeout=30000)
        page.wait_for_load_state("domcontentloaded")
        print(page.content())
    finally:
        browser.close()
"""
    workspace = tempfile.mkdtemp(prefix="fetchurl_")
    script_path = os.path.join(workspace, "_fetch.py")
    try:
        with open(script_path, "w") as f:
            f.write(script)
        result = await sandbox.execute(
            command="python /workspace/_fetch.py",
            workspace_path=workspace,
            timeout=60,
        )
        if result.exit_code == 0 and result.stdout.strip():
            return _extract_text(result.stdout)
        logger.warning(
            "Playwright fetch failed: exit=%d stderr=%s",
            result.exit_code,
            result.stderr[:500],
        )
        return ""
    except Exception as e:
        logger.warning("Playwright fetch error: %s", e)
        return ""
    finally:
        try:
            os.remove(script_path)
            os.rmdir(workspace)
        except OSError:
            pass


def make_fetch_url_tool(sandbox: SandboxManager):
    @tool(args_schema=FetchUrlInput)
    async def fetch_url(url: str) -> str:
        """Fetch a web page and extract readable text. Use after web_search to read promising links."""
        # 1. Try httpx (fast, in-process)
        try:
            text = await _fetch_with_httpx(url)
            if text and len(text.strip()) > 100:
                return text
        except Exception as e:
            logger.info("httpx fetch failed for %s: %s", url, e)

        # 2. Fallback: playwright in sandbox (handles JS-rendered pages)
        text = await _fetch_with_playwright(url, sandbox)
        if text and len(text.strip()) > 100:
            return text

        return "Failed to fetch page content."

    return fetch_url
