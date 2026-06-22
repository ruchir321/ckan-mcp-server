"""Offline tests for document_scraper (crawler / extraction / ranking)."""

from aioresponses import aioresponses

import document_scraper as ds
from document_scraper import Page


# --- Minimal valid PDF builder (text-extractable) ---

def _make_pdf(text: str) -> bytes:
    objs = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 200]/Contents 4 0 R"
        b"/Resources<</Font<</F1 5 0 R>>>>>>",
    ]
    stream = b"BT /F1 18 Tf 20 100 Td (" + text.encode("latin-1") + b") Tj ET"
    objs.append(b"<</Length " + str(len(stream)).encode() + b">>\nstream\n" + stream + b"\nendstream")
    objs.append(b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>")

    pdf = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(pdf))
        pdf += str(i).encode() + b" 0 obj" + body + b"endobj\n"
    xref_pos = len(pdf)
    pdf += b"xref\n0 " + str(len(objs) + 1).encode() + b"\n0000000000 65535 f \n"
    for off in offsets:
        pdf += ("%010d 00000 n \n" % off).encode()
    pdf += (
        b"trailer<</Size " + str(len(objs) + 1).encode() + b"/Root 1 0 R>>\n"
        b"startxref\n" + str(xref_pos).encode() + b"\n%%EOF"
    )
    return pdf


# --- Pure helpers ---

def test_discover_doc_urls_dedups_and_orders():
    pkg = {
        "information_url": "https://x.test/a/",
        "notes": "see [bylaw](https://x.test/a/b) and again [dup](https://x.test/a/)",
    }
    assert ds.discover_doc_urls(pkg) == ["https://x.test/a/", "https://x.test/a/b"]


def test_discover_doc_urls_empty():
    assert ds.discover_doc_urls({"notes": "no links here"}) == []


def test_html_to_markdown_strips_boilerplate():
    html = "<nav>menu</nav><h1>Title</h1><p>Body text.</p><script>x()</script><footer>f</footer>"
    md = ds.html_to_markdown(html)
    assert "# Title" in md
    assert "Body text." in md
    assert "menu" not in md and "x()" not in md and "f" not in md.replace("Title", "")


def test_pdf_to_text():
    text = ds.pdf_to_text(_make_pdf("Hello PDF"))
    assert "Hello" in text


def test_scope_helpers():
    prefixes = [ds._scope_prefix("https://site.test/a/")]
    assert ds._in_any_scope("https://site.test/a/b", prefixes)
    assert not ds._in_any_scope("https://site.test/other/", prefixes)
    assert not ds._in_any_scope("https://elsewhere.test/a/", prefixes)


# --- Tier 1 ranking ---

def test_split_sections():
    page = Page("u", "T", "# Heating\nLandlords must provide heat.\n# Pests\nNo cockroaches.", "html")
    secs = ds.split_sections(page)
    headings = [s.heading for s in secs]
    assert headings == ["Heating", "Pests"]
    assert "heat" in secs[0].text


def test_rank_sections_returns_relevant_section():
    pages = [
        Page("u1", "Standards", "# Heating\nLandlords must provide heat between months.", "html"),
        Page("u1", "Standards", "# Registration\nBuildings of three or more storeys must register.", "html"),
    ]
    results = ds.rank_sections(pages, "how many storeys to register", k=1)
    assert len(results) == 1
    assert results[0].heading == "Registration"


def test_rank_sections_no_match_returns_empty():
    pages = [Page("u", "T", "# Heating\nLandlords must provide heat.", "html")]
    assert ds.rank_sections(pages, "zzzznonexistentterm", k=3) == []


# --- Crawler (mocked HTTP) ---

async def test_crawl_stays_in_scope_and_dedups():
    seed = "https://site.test/a/"
    seed_html = (
        '<a href="/a/b">b</a><a href="/a/b">dup</a>'
        '<a href="/other/x">out</a><a href="https://elsewhere.test/a/">ext</a>'
    )
    with aioresponses() as m:
        m.get(seed, body=seed_html, content_type="text/html")
        m.get("https://site.test/a/b", body="<p>child</p>", content_type="text/html")
        pages = await ds.crawl([seed], obey_robots=False, delay=0, max_depth=2)
    urls = sorted(p.url for p in pages)
    assert urls == ["https://site.test/a/", "https://site.test/a/b"]


async def test_crawl_respects_robots():
    seed = "https://site.test/a/"
    with aioresponses() as m:
        m.get("https://site.test/robots.txt", status=200,
              body="User-agent: *\nDisallow: /a/secret")
        m.get(seed, body='<a href="/a/secret">s</a><a href="/a/ok">o</a>',
              content_type="text/html")
        m.get("https://site.test/a/ok", body="<p>ok</p>", content_type="text/html")
        pages = await ds.crawl([seed], obey_robots=True, delay=0, max_depth=2)
    urls = {p.url for p in pages}
    assert "https://site.test/a/secret" not in urls
    assert "https://site.test/a/ok" in urls


async def test_crawl_extracts_pdf():
    seed = "https://site.test/a/"
    with aioresponses() as m:
        m.get(seed, body='<a href="/a/doc.pdf">doc</a>', content_type="text/html")
        m.get("https://site.test/a/doc.pdf", body=_make_pdf("Bylaw text"),
              content_type="application/pdf")
        pages = await ds.crawl([seed], obey_robots=False, delay=0, max_depth=2)
    pdf_pages = [p for p in pages if p.content_type == "pdf"]
    assert len(pdf_pages) == 1
    assert "Bylaw" in pdf_pages[0].text


async def test_crawl_respects_max_pages():
    seed = "https://site.test/a/"
    with aioresponses() as m:
        m.get(seed, body='<a href="/a/b">b</a><a href="/a/c">c</a>', content_type="text/html")
        m.get("https://site.test/a/b", body="<p>b</p>", content_type="text/html")
        m.get("https://site.test/a/c", body="<p>c</p>", content_type="text/html")
        pages = await ds.crawl([seed], obey_robots=False, delay=0, max_pages=1, max_depth=2)
    assert len(pages) == 1
