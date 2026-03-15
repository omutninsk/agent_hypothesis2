from __future__ import annotations

import json
import logging
import re

from src.agent.core import build_llm
from src.config import Settings

logger = logging.getLogger(__name__)

_EXTRACT_CLAIMS_PROMPT = """Answer: {answer}

Extract 1-3 specific factual claims from this answer that can be verified \
(geographic locations, dates, statistics, named entities, outdated statistics \
presented as current, etc).
For each claim provide a short search query to verify it.
Write search queries in the same language as the answer.

Respond ONLY with JSON array: [{{"claim": "...", "search_query": "..."}}]
If no verifiable claims, respond: []"""

_VERIFY_PROMPT = """Verify these claims using search evidence:

{claims_with_evidence}

For each claim respond: confirmed / contradicted / uncertain.
If contradicted, provide the correct information from search results.
Write corrections in the same language as the original claim.

Respond ONLY with JSON array: [{{"claim": "...", "verdict": "confirmed|contradicted|uncertain", "correction": "..." or null}}]"""

_MAX_CLAIMS = 3


def _parse_json_array(text: str) -> list[dict]:
    """Extract a JSON array from LLM response, handling markdown code blocks."""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(\[.*?])\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    else:
        m = re.search(r"\[.*]", text, re.DOTALL)
        if m:
            text = m.group(0)
    return json.loads(text)


def _search_ddg(query: str, max_results: int = 3) -> str:
    """Run a DuckDuckGo search (sync, same approach as web_search tool)."""
    from duckduckgo_search import DDGS

    results = DDGS().text(query, max_results=max_results)
    lines = []
    for r in results:
        lines.append(f"{r['title']}: {r['body']}")
    return "\n".join(lines) if lines else "No results."


async def validate_response(
    settings: Settings,
    answer: str,
) -> list[dict]:
    """Extract factual claims from answer, verify via web search, return issues.

    Returns list of dicts with keys: claim, verdict, correction.
    Only contradicted/uncertain items are returned.
    Never raises — all errors are caught and logged.
    """
    try:
        answer_trimmed = answer[:2000]

        llm = build_llm(settings, react_mode=False)

        # Step 1: Extract claims
        extract_prompt = _EXTRACT_CLAIMS_PROMPT.format(answer=answer_trimmed)
        response = await llm.ainvoke(extract_prompt)
        raw = response.content if isinstance(response.content, str) else str(response.content)
        logger.info("Validation extract response: %.500s", raw)

        claims = _parse_json_array(raw)
        if not isinstance(claims, list) or not claims:
            logger.info("No verifiable claims found — skipping validation")
            return []

        claims = claims[:_MAX_CLAIMS]

        # Step 2: Web search for each claim
        claims_with_evidence: list[str] = []
        for item in claims:
            if not isinstance(item, dict):
                continue
            claim = str(item.get("claim", "")).strip()
            query = str(item.get("search_query", "")).strip()
            if not claim or not query:
                continue
            try:
                evidence = _search_ddg(query)
            except Exception:
                logger.warning("DDG search failed for query: %s", query, exc_info=True)
                evidence = "Search failed."
            claims_with_evidence.append(
                f"Claim: {claim}\nSearch results:\n{evidence}"
            )

        if not claims_with_evidence:
            return []

        # Step 3: Verify claims against evidence
        verify_prompt = _VERIFY_PROMPT.format(
            claims_with_evidence="\n\n".join(claims_with_evidence)
        )
        response = await llm.ainvoke(verify_prompt)
        raw = response.content if isinstance(response.content, str) else str(response.content)
        logger.info("Validation verify response: %.500s", raw)

        verdicts = _parse_json_array(raw)
        if not isinstance(verdicts, list):
            return []

        # Filter to only contradicted/uncertain
        issues: list[dict] = []
        for v in verdicts:
            if not isinstance(v, dict):
                continue
            verdict = str(v.get("verdict", "")).lower().strip()
            if verdict in ("contradicted", "uncertain"):
                issues.append({
                    "claim": str(v.get("claim", "")),
                    "verdict": verdict,
                    "correction": v.get("correction"),
                })

        logger.info("Validation found %d issues out of %d claims", len(issues), len(verdicts))
        return issues

    except Exception:
        logger.exception("Validation failed (non-fatal)")
        return []
