# Agent guidance

This file defines how coding agents should work in this repository.

Inspect source, tests, configuration, and relevant documentation before changing
behavior. Descriptions of the current implementation are not architectural
requirements; investigate discrepancies instead of enforcing stale documentation.

## Scope and repository layout

Run project commands from this repository's root and keep task artifacts here.
Do not write scratch files in the parent repositories directory or modify sibling
projects as part of this project's work.

- `ckan_mcp_server/server.py`: MCP tools, resources, and process lifecycle.
- `ckan_mcp_server/client.py`: CKAN API client.
- `ckan_mcp_server/documents.py`: document fetching, extraction, and search.
- `skills/toronto-open-data/`: Toronto-specific workflows and grounding guidance.
- `tests/`: automated validation.
- `README.md`, `pyproject.toml`, `Makefile`, and `.github/workflows/ci.yml`:
  usage, dependencies, and validation procedures.

Keep portal-specific guidance in the appropriate skill and reusable CKAN
mechanics in the server. Inspect the existing boundaries before moving behavior.

## Development environment

Use `uv` or the existing project virtual environment for Python execution and
dependency management; use Docker when the task requires container validation.
Never run bare `pip install` on the host.

The locked development dependency setup is `uv sync --all-extras --frozen`.
Do not install or update dependencies unnecessarily.

Before starting a server, inspect existing processes, listeners, and deployment
configuration. Avoid duplicate services and port conflicts. Scope service
operations to this repository and preserve unrelated running applications.

The server reads process environment variables and does not automatically load
dotenv files. Consult `env.sample` and the implementation for configuration.
Keep stdio protocol output free of diagnostic logging.

## Validation

Inspect `pyproject.toml`, the Makefile, CI, and existing tests to select checks
appropriate to the change. The current full check is `make check`, comprising:

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run pytest -q`

Run relevant checks before declaring a change complete. Broaden validation for
shared behavior changes; do not hardcode checks to a small fixed list of files.
Update tests when observable behavior changes, and check affected imports or
syntax where applicable. Report validation results and any unrun checks.
Distinguish offline tests from live portal or deployed-endpoint verification.

## Engineering and data handling

- Prefer the smallest coherent change that satisfies the task.
- Treat tests and explicit behavioral contracts as stronger evidence than
  descriptive implementation notes.
- Avoid duplicating logic; update documentation when durable responsibilities,
  behavior, or operating procedures change.
- Keep filesystem operations conservative. Do not delete or overwrite unrelated
  user files, and account for agent-created temporary artifacts before cleanup.
- Never expose, stage, or commit secrets or credentials. Read sensitive local
  configuration only when needed and report safe fields without secret values.
- Use sanitized fixtures and placeholders instead of personal data or
  machine-specific values in committed files.
- Keep local environment files, overrides, and generated artifacts untracked.
- If tracked files or history contain secrets or private data, report the issue
  and agree on remediation scope before destructive cleanup or history rewriting.

## Git workflow and handoff

Use coherent commits at meaningful checkpoints. Keep unrelated user or worktree
changes separate, and checkpoint before risky refactors or broad migrations.

Before each commit, inspect status and the working diff, stage intended paths
explicitly, review the staged diff, and run `git diff --cached --check`. Confirm
that staged content excludes secrets, private data, generated files, ignored
paths, and unrelated changes. Run relevant validation for the completed unit.
Identify any intentionally incomplete recovery checkpoint in its commit body.
After committing, inspect status and account for remaining changes.

Write short, specific, imperative commit subjects for a reader without the task
conversation. Add a body when needed to explain the reason, validation, or
remaining limitation; omit command transcripts and private values. End commit
messages with `Signed-off-by: <Agent> (<Model>)`, using the actual agent and model.
Do not rewrite or force-push shared history without explicit authorization.

Use commits as the development log. Update the owning documentation for durable
changes rather than creating a central chronological tracker or editing unrelated
shared files solely to record progress. Handoffs should identify deliverables,
validation, unresolved work, and the next action.
