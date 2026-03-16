from __future__ import annotations

import asyncio
import logging

from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

OBSERVATION_SUMMARIZE_THRESHOLD = 3000
CHUNK_SIZE = 2000
OVERLAP = 200

_MAP_PROMPT = "Summarize concisely. Keep facts, numbers, URLs:\n{chunk}\nSUMMARY:"
_REDUCE_PROMPT = "Combine into one summary. Keep facts:\n{summaries}\nCOMBINED:"


def _split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> list[str]:
    """Split text into chunks on line boundaries."""
    lines = text.split("\n")
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        line_len = len(line) + 1  # +1 for newline
        if current_len + line_len > chunk_size and current:
            chunks.append("\n".join(current))
            # Keep overlap: walk backwards from end until we have ~overlap chars
            overlap_lines: list[str] = []
            overlap_len = 0
            for prev_line in reversed(current):
                if overlap_len + len(prev_line) + 1 > overlap:
                    break
                overlap_lines.insert(0, prev_line)
                overlap_len += len(prev_line) + 1
            current = overlap_lines
            current_len = overlap_len
        current.append(line)
        current_len += line_len

    if current:
        chunks.append("\n".join(current))

    return chunks if chunks else [text]


async def summarize_text(
    llm: ChatOpenAI,
    text: str,
    max_output_chars: int = 1500,
) -> str:
    """Summarize text using map-reduce. Short text gets a single LLM call."""
    if len(text) <= CHUNK_SIZE:
        # Single call
        resp = await llm.ainvoke(_MAP_PROMPT.format(chunk=text))
        content = resp.content if isinstance(resp.content, str) else str(resp.content)
        return content[:max_output_chars]

    chunks = _split_into_chunks(text)
    sem = asyncio.Semaphore(3)

    async def _map_chunk(chunk: str) -> str:
        async with sem:
            resp = await llm.ainvoke(_MAP_PROMPT.format(chunk=chunk))
            return resp.content if isinstance(resp.content, str) else str(resp.content)

    summaries = await asyncio.gather(*[_map_chunk(c) for c in chunks])

    combined = "\n---\n".join(summaries)
    if len(combined) <= CHUNK_SIZE:
        resp = await llm.ainvoke(_REDUCE_PROMPT.format(summaries=combined))
        content = resp.content if isinstance(resp.content, str) else str(resp.content)
        return content[:max_output_chars]

    # Recursive reduce if still too long
    return await summarize_text(llm, combined, max_output_chars)


async def summarize_observation(llm: ChatOpenAI, observation: str) -> str:
    """Wrapper for core.py — adds [Summarized] prefix."""
    try:
        summary = await summarize_text(llm, observation)
        return f"[Summarized] {summary}"
    except Exception:
        logger.exception("Summarization failed, falling back to truncation")
        return observation[:5000] + "\n... (truncated)"
