"""Document retrieval, extraction, crawling, and ranking for CKAN links.

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
import ipaddress
import logging
import os
import re
import socket
import ssl
import time
from collections import deque
from dataclasses import dataclass
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
MAX_CRAWL_PAGES = 25
MAX_CRAWL_DEPTH = 4
DEFAULT_DELAY = 0.3  # politeness delay between requests (seconds)
CACHE_TTL = 1800  # seconds
MAX_REDIRECTS = 5
MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024
MAX_ROBOTS_BYTES = 256 * 1024
MAX_PDF_PAGES = 100
MAX_PDF_TEXT_CHARS = 2_000_000

_CACHE: dict = {}


class DocumentSecurityError(ValueError):
    """Raised when an outbound document request violates the SSRF policy."""


class DocumentLimitError(ValueError):
    """Raised when a document exceeds a configured resource bound."""


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
    """Extract bounded text from a bounded-size PDF byte string."""
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise DocumentLimitError(f"PDF exceeds the {MAX_DOWNLOAD_BYTES}-byte download limit")
    reader = PdfReader(io.BytesIO(data))
    if len(reader.pages) > MAX_PDF_PAGES:
        raise DocumentLimitError(f"PDF exceeds the {MAX_PDF_PAGES}-page limit")
    parts = []
    chars = 0
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:  # pragma: no cover - per-page extraction is best-effort
            continue
        chars += len(text)
        if chars > MAX_PDF_TEXT_CHARS:
            raise DocumentLimitError(
                f"PDF extracted text exceeds the {MAX_PDF_TEXT_CHARS}-character limit"
            )
        parts.append(text)
    return "\n\n".join(p.strip() for p in parts if p.strip())


def extract_links(html: str, base_url: str) -> list[str]:
    """Return absolute hrefs found in an HTML document."""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("mailto:", "javascript:", "tel:", "#")):
            continue
        links.append(urljoin(base_url, href))
    return links


_MD_LINK_INLINE = re.compile(r"\[([^\]]+)\]\((?:https?://)?[^)\s]+\)")
_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$", flags=re.MULTILINE)


def _clean_heading(text: str) -> str:
    """Flatten inline markdown links in a heading to their visible text.

    markdownify sometimes renders a heading as ``[Standards](https://...)``;
    keeping the raw form makes citations noisy, so reduce it to ``Standards``.
    """
    return _MD_LINK_INLINE.sub(r"\1", text).strip()


def _first_heading(markdown: str) -> str | None:
    m = _HEADING_RE.search(markdown)
    return _clean_heading(m.group(1)) if m else None


def _title_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    return path.rsplit("/", 1)[-1] or url


# --- URL discovery & scoping ---

_MD_LINK_RE = re.compile(r"\]\((https?://[^)\s]+)\)")


def discover_doc_urls(package: dict) -> list[str]:
    """Pull candidate document URLs from a CKAN package: information_url + notes links."""
    urls: list[str] = []
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


def _scope_prefix(seed: str) -> tuple[str, str]:
    """Return (host, path-prefix-directory) used to keep the crawl on-topic."""
    p = urlparse(seed)
    path = p.path if p.path.endswith("/") else p.path.rsplit("/", 1)[0] + "/"
    return p.netloc.lower(), path


def _in_any_scope(url: str, prefixes: list[tuple[str, str]]) -> bool:
    p = urlparse(url)
    host, path = p.netloc.lower(), p.path
    return any(host == h and path.startswith(prefix) for h, prefix in prefixes)


# --- SSRF guard ---


def _doc_allowed_hosts() -> set:
    """Optional explicit host allowlist from CKAN_DOC_ALLOWED_HOSTS (comma-separated)."""
    raw = os.getenv("CKAN_DOC_ALLOWED_HOSTS", "")
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def is_safe_url(url: str) -> bool:
    """Guard outbound document fetches against SSRF.

    Rejects non-http(s) URLs and any host that resolves to a non-public address
    (private, loopback, link-local, or reserved — e.g. the cloud metadata endpoint
    169.254.169.254). If CKAN_DOC_ALLOWED_HOSTS is set, ONLY those hosts pass
    (explicit allowlist for locked-down deployments).
    """
    try:
        p = urlparse(url)
        port = p.port
    except ValueError:
        return False
    if (
        p.scheme not in ("http", "https")
        or not p.hostname
        or p.username is not None
        or p.password is not None
        or port == 0
    ):
        return False
    host = p.hostname.lower()

    allow = _doc_allowed_hosts()
    if allow and host not in allow:
        return False

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for *_, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if not ip.is_global or ip.is_reserved:
            return False
    return True


class PublicAddressResolver(aiohttp.abc.AbstractResolver):
    """Resolve only globally routable addresses at connection time."""

    async def resolve(
        self,
        host: str,
        port: int = 0,
        family: socket.AddressFamily = socket.AF_UNSPEC,
    ) -> list[dict]:
        loop = asyncio.get_running_loop()
        infos = await loop.run_in_executor(
            None,
            lambda: socket.getaddrinfo(
                host,
                port,
                type=socket.SOCK_STREAM,
                family=family,
            ),
        )
        resolved = []
        for address_family, _socktype, protocol, _, sockaddr in infos:
            address = ipaddress.ip_address(sockaddr[0])
            if not address.is_global or address.is_reserved:
                raise DocumentSecurityError(f"refused non-public address for document host {host}")
            resolved.append(
                {
                    "hostname": host,
                    "host": str(address),
                    "port": port,
                    "family": address_family,
                    "proto": protocol,
                    "flags": socket.AI_NUMERICHOST,
                }
            )
        if not resolved:
            raise DocumentSecurityError(f"document host {host} did not resolve")
        return resolved

    async def close(self) -> None:
        return None


def create_safe_session() -> aiohttp.ClientSession:
    """Create a session whose connector revalidates DNS at connection time."""
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    return aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(
            ssl=ssl_context,
            resolver=PublicAddressResolver(),
        ),
        timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
    )


async def _read_limited(response: aiohttp.ClientResponse, max_bytes: int) -> bytes:
    declared = response.content_length
    if declared is not None and declared > max_bytes:
        raise DocumentLimitError(f"response exceeds the {max_bytes}-byte limit")
    chunks = []
    size = 0
    async for chunk in response.content.iter_chunked(64 * 1024):
        size += len(chunk)
        if size > max_bytes:
            raise DocumentLimitError(f"response exceeds the {max_bytes}-byte limit")
        chunks.append(chunk)
    return b"".join(chunks)


async def _request_with_redirects(
    session: aiohttp.ClientSession,
    url: str,
    max_bytes: int = MAX_DOWNLOAD_BYTES,
) -> tuple[str, str, bytes]:
    """GET a public URL, revalidating every redirect target before following it."""
    current = canonicalize(url)
    for redirect_count in range(MAX_REDIRECTS + 1):
        if not is_safe_url(current):
            raise DocumentSecurityError("URL does not resolve to an allowed public http(s) address")
        async with session.get(
            current,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=False,
        ) as response:
            if response.status in {301, 302, 303, 307, 308}:
                location = response.headers.get("Location")
                if not location:
                    response.raise_for_status()
                if redirect_count == MAX_REDIRECTS:
                    raise DocumentSecurityError("document redirect limit exceeded")
                current = canonicalize(urljoin(current, location))
                continue
            response.raise_for_status()
            body = await _read_limited(response, max_bytes)
            return current, response.headers.get("Content-Type", "").lower(), body
    raise DocumentSecurityError("document redirect limit exceeded")


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
            if not is_safe_url(robots_url):
                raise DocumentSecurityError("unsafe robots URL")
            async with session.get(
                robots_url,
                headers={"User-Agent": USER_AGENT},
                allow_redirects=False,
            ) as response:
                if response.status == 200:
                    body = await _read_limited(response, MAX_ROBOTS_BYTES)
                    rp.parse(
                        body.decode(response.charset or "utf-8", errors="replace").splitlines()
                    )
                else:
                    rp.parse([])
        except Exception:
            rp.parse([])
        cache[host] = rp
    return rp.can_fetch(USER_AGENT, url)


async def fetch_document(session: aiohttp.ClientSession, url: str) -> tuple[str, object]:
    """Fetch a URL, returning ("html", text) or ("pdf", bytes)."""
    final_url, content_type, body = await _request_with_redirects(session, url)
    if "pdf" in content_type or final_url.lower().endswith(".pdf"):
        return "pdf", body
    return "html", body.decode("utf-8", errors="replace")


async def crawl(
    seed_urls: list[str],
    max_pages: int = DEFAULT_MAX_PAGES,
    max_depth: int = DEFAULT_MAX_DEPTH,
    session: aiohttp.ClientSession | None = None,
    obey_robots: bool = True,
    delay: float = DEFAULT_DELAY,
) -> list[Page]:
    """Breadth-first crawl scoped to each seed's host + path prefix."""
    if not 1 <= max_pages <= MAX_CRAWL_PAGES:
        raise DocumentLimitError(f"max_pages must be between 1 and {MAX_CRAWL_PAGES}")
    if not 0 <= max_depth <= MAX_CRAWL_DEPTH:
        raise DocumentLimitError(f"max_depth must be between 0 and {MAX_CRAWL_DEPTH}")
    prefixes = [_scope_prefix(s) for s in seed_urls]
    own_session = session is None
    if own_session:
        session = create_safe_session()

    pages: list[Page] = []
    robots_cache: dict = {}
    queue: deque = deque((canonicalize(u), 0) for u in seed_urls)
    seen = {url for url, _ in queue}

    try:
        while queue and len(pages) < max_pages:
            url, depth = queue.popleft()
            if not is_safe_url(url):
                logger.warning("SSRF guard: skipping non-public URL %s", url)
                continue
            if obey_robots and not await _allowed(session, url, robots_cache):
                logger.info("robots.txt disallows %s", url)
                continue
            try:
                ctype, body = await fetch_document(session, url)
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
    seed_urls: list[str],
    max_pages: int = DEFAULT_MAX_PAGES,
    max_depth: int = DEFAULT_MAX_DEPTH,
    session: aiohttp.ClientSession | None = None,
) -> list[Page]:
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
# Cap on a section's length before it is chunked on paragraph boundaries. Keeping
# sections small grows the retrieval corpus, which (a) restores meaningful BM25 IDF
# on tiny per-dataset docs and (b) yields tighter, more quotable citations.
MAX_SECTION_CHARS = 1200


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _emit_sections(url: str, heading: str, body: str) -> list[Section]:
    """Turn a heading's body into one or more Sections.

    Short bodies stay whole; long bodies are packed into chunks of <= ~MAX_SECTION_CHARS
    on blank-line paragraph boundaries (never splitting mid-paragraph)."""
    body = body.strip()
    if not body:
        return []
    if len(body) <= MAX_SECTION_CHARS:
        return [Section(url, heading, body)]

    out: list[Section] = []
    chunk: list[str] = []
    size = 0
    for para in re.split(r"\n\s*\n", body):
        para = para.strip()
        if not para:
            continue
        if chunk and size + len(para) > MAX_SECTION_CHARS:
            out.append(Section(url, heading, "\n\n".join(chunk)))
            chunk, size = [], 0
        chunk.append(para)
        size += len(para)
    if chunk:
        out.append(Section(url, heading, "\n\n".join(chunk)))
    return out


def split_sections(page: Page) -> list[Section]:
    """Split a page's text into heading-anchored sections for citation.

    Long bodies under one heading are further chunked on paragraph boundaries
    (see `_emit_sections`) so the retrieval corpus stays granular."""
    sections: list[Section] = []
    heading = page.title or _title_from_url(page.url)
    buf: list[str] = []

    def flush():
        body = "\n".join(buf).strip()
        sections.extend(_emit_sections(page.url, heading, body))

    for line in page.text.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            flush()
            heading = _clean_heading(m.group(1))
            buf = []
        else:
            buf.append(line)
    flush()
    return sections


def rank_sections(pages: list[Page], query: str, k: int = 5) -> list[Section]:
    """Return the top-k sections most relevant to `query` via BM25 (score > 0)."""
    sections: list[Section] = []
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

    ranked = sorted(zip(scores, sections, strict=True), key=lambda t: t[0], reverse=True)
    return [s for score, s in ranked[:k] if score > 0]
