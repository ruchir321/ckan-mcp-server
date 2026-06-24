"""Optional Langfuse tracing — degrades to no-ops when Langfuse isn't configured.

ALL Langfuse SDK usage is isolated here so the rest of the agent stays SDK-agnostic
and fully offline-testable. Built against the Langfuse Python SDK v3 surface:
`Langfuse(...)`, `client.start_as_current_observation(as_type=..., name=..., model=...)`,
`observation.update(...)`, `client.flush()`.
"""

import contextlib
import os
from functools import lru_cache

try:  # Langfuse is an optional extra; absence must not break the agent.
    from langfuse import Langfuse
    _HAVE_LANGFUSE = True
except ImportError:  # pragma: no cover - exercised only when the extra is absent
    _HAVE_LANGFUSE = False


def _configured() -> bool:
    return _HAVE_LANGFUSE and bool(os.getenv("LANGFUSE_PUBLIC_KEY"))


@lru_cache(maxsize=1)
def get_client():
    """Return a configured Langfuse client, or None if unavailable/unconfigured."""
    if not _configured():
        return None
    return Langfuse(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        base_url=os.getenv("LANGFUSE_HOST", "http://localhost:3000"),
    )


class _NoopObservation:
    """Stand-in returned when tracing is disabled; mirrors the `.update()` API."""

    def update(self, **kwargs):
        return self


@contextlib.contextmanager
def span(name: str, *, as_type: str = "span", **kwargs):
    """Open a Langfuse span/generation as the current observation.

    No-ops (yields a dummy with `.update()`) when Langfuse is absent or unconfigured.
    Pass `as_type="generation"` and `model=...` for LLM calls.
    """
    client = get_client()
    if client is None:
        yield _NoopObservation()
        return
    with client.start_as_current_observation(as_type=as_type, name=name, **kwargs) as obs:
        yield obs


def flush() -> None:
    client = get_client()
    if client is not None:
        client.flush()
