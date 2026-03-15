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


TG_MSG_LIMIT = 4096


def split_message(text: str, limit: int = TG_MSG_LIMIT) -> list[str]:
    """Split text into chunks that fit Telegram's message limit.

    Splits on newlines to avoid breaking mid-sentence.
    """
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        # Find last newline within limit
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit  # no newline — hard cut
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks
