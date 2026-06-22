"""Focused document scraper for CKAN dataset external links.

CKAN datasets reference an authoritative prose/legal source in their metadata
(`information_url`, plus links inside `notes`). This module discovers those links,
crawls the linked page and its in-scope subpages (HTML + PDF), and exposes the
extracted text for grounded, citable retrieval.

Design (see plan): staged retrieval, per-dataset on demand. Tier 0 = fetch pages
for in-context reading; Tier 1 = section-aware BM25 keyword retrieval. No vector
store. An in-process TTL cache avoids re-crawling within a session.
"""

import asyncio
import io
import logging
import re
import ssl
import time
from collections import deque
from dataclasses import dataclass
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import aiohttp
import certifi
import markdownify
from bs4 import BeautifulSoup
from pypdf import PdfReader
from rank_bm25 import BM25Okapi

logger = logging.getLogger("mcp-ckan-server.scraper")

USER_AGENT = "MCP-CKAN-Server"
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_PAGES = 10
DEFAULT_MAX_DEPTH = 2
DEFAULT_DELAY = 0.3  # politeness delay between requests (seconds)
CACHE_TTL = 1800  # seconds

_CACHE: dict = {}


@dataclass
class Page:
    url: str
    title: str
    text: str
    content_type: str  # "html" | "pdf"


@dataclass
class Section:
    url: str
    heading: str
    text: str


# --- Extraction helpers ---

def html_to_markdown(html: str) -> str:
    """Convert an HTML document to clean Markdown, dropping boilerplate."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.extract()
    return markdownify.markdownify(str(soup), heading_style="ATX").strip()


def pdf_to_text(data: bytes) -> str:
    """Extract text from a PDF byte string."""
    reader = PdfReader(io.BytesIO(data))
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:  # pragma: no cover - per-page extraction is best-effort
            continue
    return "\n\n".join(p.strip() for p in parts if p.strip())


def extract_links(html: str, base_url: str) -> List[str]:
    """Return absolute hrefs found in an HTML document."""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("mailto:", "javascript:", "tel:", "#")):
            continue
        links.append(urljoin(base_url, href))
    return links


def _first_heading(markdown: str) -> Optional[str]:
    m = re.search(r"^#{1,6}\s+(.*)$", markdown, flags=re.MULTILINE)
    return m.group(1).strip() if m else None


def _title_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    return path.rsplit("/", 1)[-1] or url


# --- URL discovery & scoping ---

_MD_LINK_RE = re.compile(r"\]\((https?://[^)\s]+)\)")


def discover_doc_urls(package: dict) -> List[str]:
    """Pull candidate document URLs from a CKAN package: information_url + notes links."""
    urls: List[str] = []
    info_url = package.get("information_url")
    if info_url:
        urls.append(info_url)
    notes = package.get("notes") or ""
    urls.extend(_MD_LINK_RE.findall(notes))

    seen, ordered = set(), []
    for u in urls:
        c = canonicalize(u)
        if c not in seen:
            seen.add(c)
            ordered.append(u)
    return ordered


def canonicalize(url: str) -> str:
    """Normalize a URL for dedup: lowercase host, drop fragment."""
    p = urlparse(url)
    return urlunparse(p._replace(netloc=p.netloc.lower(), fragment=""))


def _scope_prefix(seed: str) -> Tuple[str, str]:
    """Return (host, path-prefix-directory) used to keep the crawl on-topic."""
    p = urlparse(seed)
    path = p.path if p.path.endswith("/") else p.path.rsplit("/", 1)[0] + "/"
    return p.netloc.lower(), path


def _in_any_scope(url: str, prefixes: List[Tuple[str, str]]) -> bool:
    p = urlparse(url)
    host, path = p.netloc.lower(), p.path
    return any(host == h and path.startswith(prefix) for h, prefix in prefixes)


# --- Crawler ---

async def _allowed(session: aiohttp.ClientSession, url: str, cache: dict) -> bool:
    """robots.txt check (per-host, cached). Missing/unreadable robots => allow."""
    p = urlparse(url)
    host = (p.scheme, p.netloc)
    rp = cache.get(host)
    if rp is None:
        rp = RobotFileParser()
        robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
        try:
            async with session.get(robots_url, headers={"User-Agent": USER_AGENT}) as r:
                rp.parse((await r.text()).splitlines() if r.status == 200 else [])
        except Exception:
            rp.parse([])
        cache[host] = rp
    return rp.can_fetch(USER_AGENT, url)


async def _fetch(session: aiohttp.ClientSession, url: str) -> Tuple[str, object]:
    """Fetch a URL, returning ("html", text) or ("pdf", bytes)."""
    async with session.get(url, headers={"User-Agent": USER_AGENT}) as resp:
        resp.raise_for_status()
        ctype = resp.headers.get("Content-Type", "").lower()
        if "pdf" in ctype or url.lower().endswith(".pdf"):
            return "pdf", await resp.read()
        return "html", await resp.text()


async def crawl(
    seed_urls: List[str],
    max_pages: int = DEFAULT_MAX_PAGES,
    max_depth: int = DEFAULT_MAX_DEPTH,
    session: Optional[aiohttp.ClientSession] = None,
    obey_robots: bool = True,
    delay: float = DEFAULT_DELAY,
) -> List[Page]:
    """Breadth-first crawl scoped to each seed's host + path prefix."""
    prefixes = [_scope_prefix(s) for s in seed_urls]
    own_session = session is None
    if own_session:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=ssl_context),
            timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
        )

    pages: List[Page] = []
    robots_cache: dict = {}
    queue: deque = deque((canonicalize(u), 0) for u in seed_urls)
    seen = {url for url, _ in queue}

    try:
        while queue and len(pages) < max_pages:
            url, depth = queue.popleft()
            if obey_robots and not await _allowed(session, url, robots_cache):
                logger.info("robots.txt disallows %s", url)
                continue
            try:
                ctype, body = await _fetch(session, url)
            except Exception as e:
                logger.warning("Failed to fetch %s: %s", url, e)
                continue

            if ctype == "pdf":
                pages.append(Page(url, _title_from_url(url), pdf_to_text(body), "pdf"))
            else:
                md = html_to_markdown(body)
                pages.append(Page(url, _first_heading(md) or _title_from_url(url), md, "html"))
                if depth < max_depth:
                    for link in extract_links(body, url):
                        c = canonicalize(link)
                        if c not in seen and _in_any_scope(c, prefixes):
                            seen.add(c)
                            queue.append((c, depth + 1))

            if delay:
                await asyncio.sleep(delay)
    finally:
        if own_session:
            await session.close()

    return pages


async def gather_dataset_pages(
    seed_urls: List[str],
    max_pages: int = DEFAULT_MAX_PAGES,
    max_depth: int = DEFAULT_MAX_DEPTH,
    session: Optional[aiohttp.ClientSession] = None,
) -> List[Page]:
    """crawl() with an in-process TTL cache keyed by seeds + crawl bounds."""
    key = (tuple(sorted(canonicalize(u) for u in seed_urls)), max_pages, max_depth)
    cached = _CACHE.get(key)
    now = time.time()
    if cached and now - cached[0] < CACHE_TTL:
        return cached[1]
    pages = await crawl(seed_urls, max_pages=max_pages, max_depth=max_depth, session=session)
    _CACHE[key] = (now, pages)
    return pages


# --- Tier 1 retrieval ---

_TOKEN_RE = re.compile(r"\w+")


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


def split_sections(page: Page) -> List[Section]:
    """Split a page's text into heading-anchored sections for citation."""
    sections: List[Section] = []
    heading = page.title or _title_from_url(page.url)
    buf: List[str] = []

    def flush():
        body = "\n".join(buf).strip()
        if body:
            sections.append(Section(page.url, heading, body))

    for line in page.text.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush()
            heading = m.group(2).strip()
            buf = []
        else:
            buf.append(line)
    flush()
    return sections


def rank_sections(pages: List[Page], query: str, k: int = 5) -> List[Section]:
    """Return the top-k sections most relevant to `query` via BM25 (score > 0)."""
    sections: List[Section] = []
    for pg in pages:
        sections.extend(split_sections(pg))
    if not sections:
        return []

    corpus = [_tokenize(f"{s.heading} {s.text}") for s in sections]
    q_tokens = _tokenize(query)
    bm25 = BM25Okapi(corpus)
    scores = list(bm25.get_scores(q_tokens))

    # BM25's IDF goes to zero on tiny corpora (a term present in most/all docs),
    # which would wrongly drop everything for a single short page. Fall back to a
    # plain query-term overlap count so small per-dataset corpora still retrieve.
    if not scores or max(scores) <= 0:
        q_set = set(q_tokens)
        scores = [sum(1 for tok in doc if tok in q_set) for doc in corpus]

    ranked = sorted(zip(scores, sections), key=lambda t: t[0], reverse=True)
    return [s for score, s in ranked[:k] if score > 0]
