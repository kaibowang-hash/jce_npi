from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, Mapping
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_id: UUID
    occurred_at: datetime
    actor: str
    trace_id: str
    operation: str
    global_id: UUID
    object_version: int
    result: str
    input_summary: Mapping[str, Any]


def create_audit_event(
    *, actor: str, trace_id: str, operation: str, global_id: UUID,
    object_version: int, result: str, input_summary: Mapping[str, Any],
) -> AuditEvent:
    if len(trace_id) < 8:
        raise ValueError("Trace ID must contain at least eight characters.")
    safe_summary = {key: value for key, value in input_summary.items() if key.lower() not in {"password", "token", "secret"}}
    return AuditEvent(uuid4(), datetime.now(UTC), actor, trace_id, operation, global_id,
                      object_version, result, MappingProxyType(safe_summary))
