
FROM ghcr.io/astral-sh/uv:0.9.10 AS uv

FROM python:3.13.11-slim-trixie

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=uv /uv /uvx /bin/

RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app app \
    && mkdir -p /app \
    && chown app:app /app

WORKDIR /app
COPY --chown=app:app pyproject.toml uv.lock README.md LICENSE ./
COPY --chown=app:app ckan_mcp_server ./ckan_mcp_server

USER app
RUN uv sync --frozen --no-dev

ENTRYPOINT ["ckan-mcp-server"]

