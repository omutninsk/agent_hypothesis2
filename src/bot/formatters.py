from __future__ import annotations

import html


def escape(text: str) -> str:
    return html.escape(text)


def truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... (truncated)"


def code_block(text: str, limit: int = 3900) -> str:
    text = truncate(text, limit)
    return f"<pre>{escape(text)}</pre>"
