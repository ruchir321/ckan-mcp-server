"""Offline tests for ckan_read_web_document (HTTP mocked with aioresponses)."""

from aioresponses import aioresponses

from ckan_mcp_server import server

SAMPLE_HTML = """
<html>
  <head><title>Doc</title><style>.x{}</style></head>
  <body>
    <nav>menu noise</nav>
    <h1>Apartment Building Standards</h1>
    <p>Tenants must have heat.</p>
    <script>console.log('noise')</script>
    <footer>footer noise</footer>
  </body>
</html>
"""

URL = "https://example.test/doc"


async def test_converts_html_to_markdown_and_strips_boilerplate():
    with aioresponses() as m:
        m.get(URL, status=200, body=SAMPLE_HTML, content_type="text/html")
        result = await server.ckan_read_web_document(url=URL)
    assert "# Apartment Building Standards" in result
    assert "Tenants must have heat." in result
    # nav/script/style/footer content should be removed.
    assert "menu noise" not in result
    assert "console.log" not in result
    assert "footer noise" not in result


async def test_truncates_to_max_chars():
    with aioresponses() as m:
        m.get(URL, status=200, body=SAMPLE_HTML, content_type="text/html")
        result = await server.ckan_read_web_document(url=URL, max_chars=10)
    assert result.endswith("...[Content truncated due to length]...")


async def test_failed_fetch_returns_error_string():
    with aioresponses() as m:
        m.get(URL, status=404)
        result = await server.ckan_read_web_document(url=URL)
    assert result.startswith("Failed to fetch or parse the document")
