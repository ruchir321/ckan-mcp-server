"""Deterministic, side-effect-free scorers for the civic-answer eval.

Pure functions so they can be unit-tested directly and reused as Langfuse
evaluators in `evals/run_eval.py`. Each returns a float in {0.0, 1.0} or None
when the metric does not apply to the given item kind.
"""

from typing import List, Optional


def _contains(haystack: str, needle: str) -> bool:
    return needle.lower() in (haystack or "").lower()


def retrieval_hit(passages, must_include: Optional[str]) -> Optional[float]:
    """Did retrieval surface the answer phrase at all? Isolates retrieval vs. synthesis failures."""
    if not must_include:
        return None
    return 1.0 if any(
        _contains(p.text, must_include) or _contains(p.heading, must_include) for p in passages
    ) else 0.0


def fact_recall(answer: str, citations, must_include: Optional[str]) -> Optional[float]:
    """Did the final answer (or a cited quote) contain the expected fact phrase?"""
    if not must_include:
        return None
    hay = (answer or "") + " " + " ".join(c.quote for c in citations)
    return 1.0 if _contains(hay, must_include) else 0.0


def citation_match(citations, source_url_contains: Optional[str]) -> Optional[float]:
    """Did the agent cite the expected source (URL substring)?"""
    if not source_url_contains:
        return None
    return 1.0 if any(_contains(c.url, source_url_contains) for c in citations) else 0.0


def refusal_correct(supported: bool, kind: str) -> Optional[float]:
    """For must-abstain items: 1.0 when the agent correctly declined to answer."""
    if kind != "abstain":
        return None
    return 1.0 if not supported else 0.0


def over_refusal(supported: bool, kind: str) -> Optional[float]:
    """For answerable items: 1.0 when the agent WRONGLY refused (a failure signal)."""
    if kind != "answerable":
        return None
    return 1.0 if not supported else 0.0
