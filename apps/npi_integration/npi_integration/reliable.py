from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Mapping
from uuid import UUID, uuid4


def canonical_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


class MessageState(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_FINAL = "failed_final"
    QUARANTINED = "quarantined"


@dataclass(frozen=True, slots=True)
class IntegrationEvent:
    event_id: UUID
    event_type: str
    event_version: int
    occurred_at: datetime
    source_system: str
    target_system: str
    global_id: UUID
    object_type: str
    object_version: int
    trace_id: str
    payload_hash: str
    payload: Mapping[str, Any]

    @classmethod
    def create(cls, *, event_type: str, global_id: UUID, object_type: str,
               object_version: int, trace_id: str, payload: Mapping[str, Any]) -> "IntegrationEvent":
        if not event_type.startswith("npi.") or object_version < 0 or len(trace_id) < 8:
            raise ValueError("Event type, object version or trace ID is invalid.")
        return cls(uuid4(), event_type, 1, datetime.now(UTC), "NPI_ONE", "ERPNEXT",
                   global_id, object_type, object_version, trace_id,
                   canonical_hash(payload), dict(payload))


@dataclass(frozen=True, slots=True)
class OutboxMessage:
    event: IntegrationEvent
    state: MessageState = MessageState.PENDING
    attempt_count: int = 0
    last_error_code: str | None = None

    def start(self) -> "OutboxMessage":
        if self.state not in {MessageState.PENDING, MessageState.FAILED_RETRYABLE}:
            raise ValueError("Only pending or retryable messages can start.")
        return replace(self, state=MessageState.PROCESSING, attempt_count=self.attempt_count + 1)

    def complete(self) -> "OutboxMessage":
        if self.state is not MessageState.PROCESSING:
            raise ValueError("Only processing messages can complete.")
        return replace(self, state=MessageState.SUCCEEDED, last_error_code=None)

    def fail(self, error_code: str, *, retryable: bool) -> "OutboxMessage":
        if self.state is not MessageState.PROCESSING or not error_code:
            raise ValueError("A processing message and error code are required.")
        state = MessageState.FAILED_RETRYABLE if retryable else MessageState.FAILED_FINAL
        return replace(self, state=state, last_error_code=error_code)


@dataclass(frozen=True, slots=True)
class InboxReceipt:
    event_id: UUID
    payload_hash: str
    state: MessageState = MessageState.PENDING


class InboxRegistry:
    """Models the unique event_id + immutable payload rule enforced by persistence."""

    def __init__(self) -> None:
        self._receipts: dict[UUID, InboxReceipt] = {}

    def land(self, event_id: UUID, payload: Mapping[str, Any]) -> tuple[InboxReceipt, bool]:
        payload_hash = canonical_hash(payload)
        existing = self._receipts.get(event_id)
        if existing:
            if existing.payload_hash != payload_hash:
                return replace(existing, state=MessageState.QUARANTINED), False
            return existing, False
        receipt = InboxReceipt(event_id, payload_hash)
        self._receipts[event_id] = receipt
        return receipt, True
