"""The grounded civic-answer agent.

Given a plain-language question, find the City of Toronto's authoritative document
for the relevant dataset, retrieve the most relevant passages, and answer ONLY from
them (with citations) — or abstain. Reuses `document_scraper` for retrieval and the
CKAN tools in `mcp_ckan_server` for discovery; no retrieval logic is re-implemented.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import document_scraper
import mcp_ckan_server as server
from agent import tracing

DEFAULT_MODEL = os.getenv("CIVIC_AGENT_MODEL", "claude-sonnet-4-6")

# The grounding discipline, kept verbatim in spirit with skills/toronto-open-data/SKILL.md.
GROUNDING_SYSTEM = (
    "You answer questions about City of Toronto open data ONLY from the source passages "
    "provided in the user message. Quote the supporting text verbatim and cite its source "
    "URL. If the passages do not contain the answer, set \"supported\" to false and do not "
    "guess or use outside knowledge.\n\n"
    "Respond with ONLY a JSON object, no prose, of the form:\n"
    '{"supported": <bool>, "answer": <string>, '
    '"citations": [{"url": <string>, "quote": <string>}]}'
)

# A callable (system, user, model) -> raw model text. Injectable for offline tests.
LLMFn = Callable[[str, str, str], str]


@dataclass
class Citation:
    url: str
    quote: str


@dataclass
class GroundedAnswer:
    question: str
    supported: bool
    answer: str
    citations: List[Citation] = field(default_factory=list)
    passages: list = field(default_factory=list)  # retrieved Sections (url/heading/text)
    dataset_id: Optional[str] = None


async def _resolve_seeds(question: str, dataset_id: Optional[str]):
    """Return (dataset_id, seed_urls). Discovers a dataset when none is pinned."""
    if dataset_id:
        return dataset_id, await server._dataset_doc_seeds(dataset_id)

    result = await server.ckan_package_search.fn(q=question, rows=5)
    for pkg in result.get("results", []):
        candidate = pkg.get("name") or pkg.get("id")
        try:
            return candidate, await server._dataset_doc_seeds(candidate)
        except Exception:
            continue  # no doc links on this dataset; try the next hit
    raise ValueError(f"No dataset with linked documents found for: {question!r}")


def _default_llm(system: str, user: str, model: str) -> str:
    """One Anthropic Messages call returning the raw text. Imported lazily."""
    import anthropic

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")


def _build_user_content(question: str, sections) -> str:
    blocks = [f"Question: {question}", "", "Source passages:"]
    for i, s in enumerate(sections, 1):
        blocks.append(f"[{i}] URL: {s.url}\nHeading: {s.heading}\n{s.text}")
    return "\n\n".join(blocks)


def _parse_response(raw: str) -> dict:
    """Tolerantly extract the JSON object from the model's reply."""
    text = raw.strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


async def answer_question(
    question: str,
    dataset_id: Optional[str] = None,
    *,
    k: int = 5,
    model: str = DEFAULT_MODEL,
    llm: Optional[LLMFn] = None,
) -> GroundedAnswer:
    """Answer a civic question grounded in the dataset's source documents, or abstain."""
    llm = llm or _default_llm

    with tracing.span("civic_agent.answer", metadata={"question": question, "model": model}):
        with tracing.span("resolve_dataset"):
            ds_id, seeds = await _resolve_seeds(question, dataset_id)

        with tracing.span("retrieve") as ret:
            pages = await document_scraper.gather_dataset_pages(seeds)
            sections = document_scraper.rank_sections(pages, question, k=k)
            ret.update(output={"sections": len(sections), "seeds": seeds})

        if not sections:
            return GroundedAnswer(
                question, False, "The City's documents don't cover this.", [], [], ds_id
            )

        user = _build_user_content(question, sections)
        with tracing.span("synthesize", as_type="generation", model=model) as gen:
            gen.update(input=user)
            raw = llm(GROUNDING_SYSTEM, user, model)
            gen.update(output=raw)

        data = _parse_response(raw)
        citations = [
            Citation(c.get("url", ""), c.get("quote", "")) for c in data.get("citations", [])
        ]
        return GroundedAnswer(
            question=question,
            supported=bool(data.get("supported")),
            answer=data.get("answer", ""),
            citations=citations,
            passages=sections,
            dataset_id=ds_id,
        )
