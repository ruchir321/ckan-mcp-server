"""Offline tests for the dataset document tools."""

from aioresponses import aioresponses
from conftest import action_re

from ckan_mcp_server import server
from ckan_mcp_server.documents import Page

PACKAGE = {"success": True, "result": {"information_url": "https://site.test/p0"}}


def _fake_pages(pages):
    async def fake(seeds, max_pages=10, **_kwargs):
        return pages

    return fake


async def test_fetch_dataset_docs_caps_total_output(monkeypatch):
    pages = [Page(f"https://site.test/p{i}", f"P{i}", "x" * 50_000, "html") for i in range(3)]
    monkeypatch.setattr(server.documents, "gather_dataset_pages", _fake_pages(pages))
    with aioresponses() as m:
        m.get(action_re("package_show"), payload=PACKAGE)
        out = await server.ckan_fetch_dataset_docs("ds")
    assert server.MAX_DOCS_RESPONSE_CHARS == 60_000
    assert [len(p["text"]) for p in out["pages"]] == [30_000, 30_000, 0]
    assert [p["total_chars"] for p in out["pages"]] == [50_000, 50_000, 50_000]
    assert [p["truncated"] for p in out["pages"]] == [True, True, True]
    assert out["truncated"] is True
    assert "ckan_search_dataset_docs" in out["note"]


async def test_fetch_dataset_docs_leaves_small_pages_whole(monkeypatch):
    pages = [Page("https://site.test/p0", "P0", "short text", "html")]
    monkeypatch.setattr(server.documents, "gather_dataset_pages", _fake_pages(pages))
    with aioresponses() as m:
        m.get(action_re("package_show"), payload=PACKAGE)
        out = await server.ckan_fetch_dataset_docs("ds")
    assert out["pages"][0]["text"] == "short text"
    assert out["pages"][0]["truncated"] is False
    assert out["truncated"] is False
    assert "note" not in out
