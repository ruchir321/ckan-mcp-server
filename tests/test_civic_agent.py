"""Offline tests for the grounded civic-answer agent (no network, no API key).

CKAN HTTP is mocked with aioresponses; the LLM call is injected; Langfuse is a
no-op (no keys configured), so this runs fully offline.
"""

import pytest
from aioresponses import aioresponses

import document_scraper
from agent import scoring
from agent.grounded_agent import Citation, answer_question
from conftest import action_re

DOC_URL = "https://site.test/standards/"
DOC_HTML = """
<html><body>
<h1>Apartment Building Standards</h1>
<h2>Registration</h2>
<p>RentSafeTO applies to apartment buildings with three or more storeys and 10 or more units.</p>
</body></html>
"""


@pytest.fixture(autouse=True)
def _clear_doc_cache():
    document_scraper._CACHE.clear()
    yield
    document_scraper._CACHE.clear()


def _package_payload(info_url=DOC_URL):
    return {
        "success": True,
        "result": {"id": "x", "name": "x", "information_url": info_url, "notes": ""},
    }


async def test_answer_question_grounded_and_cited():
    def fake_llm(system, user, model):
        # The model only ever sees the retrieved passages.
        assert "three or more storeys" in user
        return (
            '{"supported": true, "answer": "Buildings with three or more storeys and 10+ units.",'
            ' "citations": [{"url": "https://site.test/standards/",'
            ' "quote": "three or more storeys and 10 or more units"}]}'
        )

    with aioresponses() as m:
        m.get(action_re("package_show"), payload=_package_payload())
        m.get(DOC_URL, body=DOC_HTML, content_type="text/html")
        result = await answer_question(
            "how many storeys to register", "apartment-building-evaluation", llm=fake_llm
        )

    assert result.supported is True
    assert any("site.test" in c.url for c in result.citations)
    assert "three or more storeys" in result.citations[0].quote
    assert result.passages  # retrieval actually ran


async def test_answer_question_abstains_when_unsupported():
    def fake_llm(system, user, model):
        return (
            '{"supported": false, "answer": "The City\'s documents don\'t cover this.",'
            ' "citations": []}'
        )

    with aioresponses() as m:
        m.get(action_re("package_show"), payload=_package_payload())
        m.get(DOC_URL, body=DOC_HTML, content_type="text/html")
        result = await answer_question("unrelated trivia question", "x", llm=fake_llm)

    assert result.supported is False
    assert result.citations == []


def test_deterministic_scorers():
    sections = [type("S", (), {"text": "three or more storeys", "heading": "Registration"})()]
    cits = [Citation("https://toronto.ca/x", "three or more storeys")]

    assert scoring.retrieval_hit(sections, "three or more storeys") == 1.0
    assert scoring.retrieval_hit(sections, "swimming pool") == 0.0
    assert scoring.fact_recall("answer text", cits, "three or more storeys") == 1.0
    assert scoring.citation_match(cits, "toronto.ca") == 1.0
    assert scoring.citation_match(cits, "ontario.ca") == 0.0
    assert scoring.refusal_correct(False, "abstain") == 1.0
    assert scoring.refusal_correct(True, "abstain") == 0.0
    assert scoring.refusal_correct(True, "answerable") is None
    assert scoring.over_refusal(False, "answerable") == 1.0
    assert scoring.over_refusal(True, "answerable") == 0.0
