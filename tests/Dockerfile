
# Dockerfile for CKAN-MCP tests
#
# (C) Ondics GmbH
#

FROM python:3.13.4-slim-bookworm

ENV TZ="Europe/Berlin"

RUN apt-get update && apt-get install -y \
    vim \
    jq \
    git \
    procps \
    && rm -rf /var/lib/apt/lists/*



WORKDIR /app/tests

COPY tests/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY tests/ .
COPY *.py /app/
COPY *.txt /app/
COPY *.md /app/
COPY *.toml /app/
COPY .env /app/
CMD ["python", "test.py"]

