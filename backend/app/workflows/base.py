"""Shared plumbing for the LangGraph read-path workflows.

- ``emit`` streams a human-readable status event from inside a graph node via
  LangGraph's custom stream writer (the "real interim status" the ui-ux steering
  requires). Outside a streaming run (e.g. tests using ``invoke``) it is a no-op.
- ``stream_graph`` runs a compiled graph and yields SSE-formatted status lines,
  forwarding every custom event a node emits.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from langgraph.graph.state import CompiledStateGraph


def emit(step: str, message: str, **extra: Any) -> None:
    """Emit a status event to the SSE stream, if running under a stream."""
    try:
        from langgraph.config import get_stream_writer

        writer = get_stream_writer()
    except Exception:
        writer = None
    if writer is not None:
        writer({"step": step, "message": message, **extra})


def sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


async def stream_graph(
    graph: CompiledStateGraph, state: dict[str, Any]
) -> AsyncIterator[str]:
    """Run a graph and forward each node's custom status events as SSE lines."""
    async for chunk in graph.astream(state, stream_mode="custom"):
        yield sse(chunk)
