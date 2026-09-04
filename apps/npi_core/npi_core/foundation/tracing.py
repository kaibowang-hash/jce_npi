from __future__ import annotations

import re
from contextvars import ContextVar
from uuid import uuid4

_TRACE_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
current_trace_id: ContextVar[str | None] = ContextVar("npi_trace_id", default=None)


def resolve_trace_id(candidate: str | None) -> str:
    trace_id = candidate if candidate and _TRACE_PATTERN.fullmatch(candidate) else uuid4().hex
    current_trace_id.set(trace_id)
    return trace_id
