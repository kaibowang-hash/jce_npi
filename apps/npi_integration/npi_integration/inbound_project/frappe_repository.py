from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

import frappe

from npi_core.foundation.audit import create_audit_event

from .domain import (
    EventIdentityDisposition,
    SourceHead,
    SourceOrderDisposition,
    SourceStreamIdentity,
    canonical_json_hash,
    classify_event_identity,
    classify_source_order,
    raw_body_hash,
)
from .frappe_validation import inbound_project_repository_write
from .ingress import AuthenticatedProjectSourceRequest


class LandingDisposition(StrEnum):
    ACCEPTED = "accepted"
    EVENT_EXACT_REPLAY = "event_exact_replay"
    EVENT_CONFLICT = "event_conflict"
    SOURCE_EXACT_REPLAY = "source_exact_replay"
    SOURCE_SUPERSEDED = "source_superseded"
    SOURCE_CONFLICT = "source_conflict"
    RECEIVED_AFTER_CREATION = "received_after_creation"


@dataclass(frozen=True, slots=True)
class InboundProjectLandingOutcome:
    receipt_id: UUID
    event_id: UUID
    state: str
    trace_id: str
    disposition: LandingDisposition
    exact_duplicate: bool = False
    should_enqueue: bool = False
    conflict_code: str | None = None


class FrappeInboundProjectRepository:
    """Durably land authenticated receipts without running Project business work."""

    def land(
        self,
        authenticated: AuthenticatedProjectSourceRequest,
    ) -> InboundProjectLandingOutcome:
        if not isinstance(authenticated, AuthenticatedProjectSourceRequest):
            raise TypeError("Authenticated Project source request is required.")
        event = authenticated.event
        existing = _locked_inbox_by_event_id(event.event_id)
        if existing is not None:
            return self._existing_event_outcome(authenticated, existing)

        identity = SourceStreamIdentity(
            tenant_id=authenticated.profile.tenant_id,
            profile_id=authenticated.profile.profile_id,
            object_type=event.object_type,
            source_object_id=event.source_object_id,
        )
        source_binding = _optional_locked_doc(
            "NPI Project Source Binding", identity.key_hash
        )
        if source_binding is not None:
            _require_source_identity(source_binding, authenticated, identity)
            # The source lock closes the event-lookup race for established streams.
            existing = _locked_inbox_by_event_id(event.event_id)
            if existing is not None:
                return self._existing_event_outcome(authenticated, existing)

        receipt_id = uuid4()
        disposition = _classify_source(source_binding, event, receipt_id)
        state, processing_disposition = _receipt_state(disposition)
        values = _receipt_values(
            authenticated=authenticated,
            identity=identity,
            receipt_id=receipt_id,
            state=state,
            disposition=processing_disposition,
        )
        with inbound_project_repository_write():
            inbox = frappe.get_doc(values).insert()
            if source_binding is None:
                source_binding = frappe.get_doc(
                    _new_source_binding_values(
                        authenticated=authenticated,
                        identity=identity,
                        receipt_id=receipt_id,
                    )
                ).insert()
            else:
                _apply_source_disposition(
                    source_binding,
                    authenticated=authenticated,
                    receipt_id=receipt_id,
                    disposition=disposition,
                )
            self._append_audit(
                actor=authenticated.profile.service_actor_user_id,
                trace_id=event.trace_id,
                operation="inbound_project.land",
                global_id=event.event_id,
                object_version=event.object_version,
                result=disposition.value,
                summary={
                    "eventId": str(event.event_id),
                    "objectType": event.object_type.value,
                    "objectVersion": event.object_version,
                    "receiptId": str(receipt_id),
                    "sourceKeyHash": identity.key_hash,
                },
            )
        conflict_code = (
            "INBOUND_PROJECT_SOURCE_CONFLICT"
            if disposition is LandingDisposition.SOURCE_CONFLICT
            else None
        )
        return InboundProjectLandingOutcome(
            receipt_id=UUID(str(inbox.name)),
            event_id=event.event_id,
            state=state,
            trace_id=event.trace_id,
            disposition=disposition,
            should_enqueue=disposition is LandingDisposition.ACCEPTED,
            conflict_code=conflict_code,
        )

    def append_ingress_failure_audit(
        self,
        *,
        request_id: UUID,
        trace_id: str,
        code: str,
        received_at: datetime,
        body_size: int | None,
        raw_hash: str | None,
        key_id_hash: str | None,
    ) -> None:
        summary: dict[str, object] = {
            "failureCode": code,
            "receivedAt": _utc_text(received_at),
        }
        if type(body_size) is int and body_size >= 0:
            summary["bodySize"] = body_size
        if raw_hash is not None:
            summary["rawBodyHash"] = raw_hash
        if key_id_hash is not None:
            summary["signingKeyIdHash"] = key_id_hash
        with inbound_project_repository_write():
            self._append_audit(
                actor="npi-inbound-transport",
                trace_id=trace_id,
                operation="inbound_project.reject",
                global_id=request_id,
                object_version=1,
                result=code.casefold(),
                summary=summary,
            )

    def _existing_event_outcome(
        self,
        authenticated: AuthenticatedProjectSourceRequest,
        existing: Any,
    ) -> InboundProjectLandingOutcome:
        event = authenticated.event
        exact_scope = (
            int(_value(existing, "schema_version") or 0) == 1
            and int(_value(existing, "authenticated") or 0) == 1
            and str(_value(existing, "tenant_id"))
            == authenticated.profile.tenant_id
            and str(_value(existing, "profile_id"))
            == authenticated.profile.profile_id
            and str(_value(existing, "source_object_type"))
            == event.object_type.value
            and str(_value(existing, "source_object_id")) == event.source_object_id
        )
        identity_disposition = classify_event_identity(
            str(_value(existing, "canonical_event_hash") or "0" * 64),
            event.canonical_event_hash,
        )
        exact = (
            exact_scope
            and identity_disposition is EventIdentityDisposition.DUPLICATE_EXACT
        )
        disposition = (
            LandingDisposition.EVENT_EXACT_REPLAY
            if exact
            else LandingDisposition.EVENT_CONFLICT
        )
        with inbound_project_repository_write():
            self._append_audit(
                actor=authenticated.profile.service_actor_user_id,
                trace_id=event.trace_id,
                operation=(
                    "inbound_project.replay" if exact else "inbound_project.conflict"
                ),
                global_id=event.event_id,
                object_version=event.object_version,
                result=disposition.value,
                summary={
                    "eventId": str(event.event_id),
                    "receiptId": str(_value(existing, "receipt_id") or existing.name),
                },
            )
        return InboundProjectLandingOutcome(
            receipt_id=UUID(str(_value(existing, "receipt_id") or existing.name)),
            event_id=event.event_id,
            state=str(_value(existing, "state")),
            trace_id=event.trace_id,
            disposition=disposition,
            exact_duplicate=exact,
            conflict_code=(
                None if exact else "INBOUND_PROJECT_EVENT_CONFLICT"
            ),
        )

    @staticmethod
    def _append_audit(
        *,
        actor: str,
        trace_id: str,
        operation: str,
        global_id: UUID,
        object_version: int,
        result: str,
        summary: dict[str, object],
    ) -> None:
        event = create_audit_event(
            actor=actor,
            trace_id=trace_id,
            operation=operation,
            global_id=global_id,
            object_version=object_version,
            result=result,
            input_summary=summary,
        )
        frappe.get_doc(
            {
                "doctype": "NPI Audit Event",
                "event_id": str(event.event_id),
                "global_id": str(event.global_id),
                "object_version": event.object_version,
                "actor": event.actor,
                "trace_id": event.trace_id,
                "operation": event.operation,
                "result": event.result,
                "input_summary": dict(event.input_summary),
            }
        ).insert()


def _receipt_values(
    *,
    authenticated: AuthenticatedProjectSourceRequest,
    identity: SourceStreamIdentity,
    receipt_id: UUID,
    state: str,
    disposition: str,
) -> dict[str, object]:
    event = authenticated.event
    signed_at = _utc_text(authenticated.headers.signed_at)
    received_at = _utc_text(authenticated.received_at)
    receipt = {
        "schema_version": 1,
        "receipt_id": str(receipt_id),
        "tenant_id": authenticated.profile.tenant_id,
        "profile_id": authenticated.profile.profile_id,
        "profile_version": authenticated.profile.version,
        "policy_hash": authenticated.policy.snapshot_hash,
        "source_key_hash": identity.key_hash,
        "event_id": str(event.event_id),
        "canonical_event_hash": event.canonical_event_hash,
        "raw_body_hash": raw_body_hash(authenticated.raw_body),
        "signing_key_id": authenticated.headers.key_id,
        "signed_at": signed_at,
        "received_at": received_at,
        "request_id": authenticated.headers.request_id,
    }
    return {
        "doctype": "NPI Inbox Message",
        "receipt_id": str(receipt_id),
        "event_id": str(event.event_id),
        "source_system": "ERPNEXT",
        "payload_hash": event.payload_hash,
        "payload": event.payload.canonical_mapping(),
        "state": state,
        "schema_version": 1,
        "authenticated": 1,
        "tenant_id": authenticated.profile.tenant_id,
        "profile_id": authenticated.profile.profile_id,
        "profile_version": authenticated.profile.version,
        "policy_snapshot": authenticated.policy.snapshot(),
        "policy_hash": authenticated.policy.snapshot_hash,
        "event_type": event.event_type.value,
        "event_version": 1,
        "target_system": "NPI_ONE",
        "global_id": str(event.global_id),
        "source_object_type": event.object_type.value,
        "source_object_id": event.source_object_id,
        "source_key_hash": identity.key_hash,
        "object_version": event.object_version,
        "event_snapshot": event.canonical_mapping(),
        "canonical_event_hash": event.canonical_event_hash,
        "raw_body": authenticated.raw_body.decode("utf-8"),
        "raw_body_hash": receipt["raw_body_hash"],
        "signing_key_id": authenticated.headers.key_id,
        "signed_at": signed_at,
        "received_at": received_at,
        "request_id": authenticated.headers.request_id,
        "trace_id": event.trace_id,
        "correlation_id": str(event.correlation_id),
        "actor_id": event.actor_id,
        "sensitivity": "confidential",
        "disposition": disposition,
        "attempt_count": 0,
        "receipt_snapshot": receipt,
        "receipt_hash": canonical_json_hash(receipt),
    }


def _new_source_binding_values(
    *,
    authenticated: AuthenticatedProjectSourceRequest,
    identity: SourceStreamIdentity,
    receipt_id: UUID,
) -> dict[str, object]:
    event = authenticated.event
    return {
        "doctype": "NPI Project Source Binding",
        "source_key_hash": identity.key_hash,
        "schema_version": 1,
        "tenant_id": authenticated.profile.tenant_id,
        "profile_id": authenticated.profile.profile_id,
        "profile_version": authenticated.profile.version,
        "source_system": "ERPNEXT",
        "target_system": "NPI_ONE",
        "source_object_type": event.object_type.value,
        "source_object_id": event.source_object_id,
        "highest_received_version": event.object_version,
        "highest_payload_hash": event.payload_hash,
        "highest_inbox_message": str(receipt_id),
        "stream_state": "unbound",
        "optimistic_version": 1,
        "last_processing_code": "received",
        "last_processed_at": _utc_text(authenticated.received_at),
        "updated_at": _utc_text(authenticated.received_at),
    }


def _classify_source(
    source_binding: Any | None,
    event: Any,
    receipt_id: UUID,
) -> LandingDisposition:
    if source_binding is None:
        return LandingDisposition.ACCEPTED
    if str(_value(source_binding, "stream_state")) == "conflicted":
        return LandingDisposition.SOURCE_CONFLICT
    current = SourceHead(
        object_version=int(_value(source_binding, "highest_received_version")),
        payload_hash=str(_value(source_binding, "highest_payload_hash")),
        inbox_id=UUID(str(_value(source_binding, "highest_inbox_message"))),
    )
    candidate = SourceHead(
        object_version=event.object_version,
        payload_hash=event.payload_hash,
        inbox_id=receipt_id,
    )
    disposition = classify_source_order(
        current,
        candidate,
        project_already_bound=bool(_value(source_binding, "bound_project_global_id")),
    )
    return {
        SourceOrderDisposition.ADVANCE: LandingDisposition.ACCEPTED,
        SourceOrderDisposition.SUPERSEDED: LandingDisposition.SOURCE_SUPERSEDED,
        SourceOrderDisposition.DUPLICATE_EXACT: LandingDisposition.SOURCE_EXACT_REPLAY,
        SourceOrderDisposition.CONFLICTED: LandingDisposition.SOURCE_CONFLICT,
        SourceOrderDisposition.RECEIVED_AFTER_CREATION: (
            LandingDisposition.RECEIVED_AFTER_CREATION
        ),
    }[disposition]


def _receipt_state(disposition: LandingDisposition) -> tuple[str, str]:
    if disposition is LandingDisposition.ACCEPTED:
        return "pending", "pending"
    if disposition in {
        LandingDisposition.SOURCE_EXACT_REPLAY,
        LandingDisposition.SOURCE_SUPERSEDED,
    }:
        return "superseded", "superseded"
    if disposition is LandingDisposition.RECEIVED_AFTER_CREATION:
        return "received_after_creation", "received_after_creation"
    if disposition is LandingDisposition.SOURCE_CONFLICT:
        return "quarantined", "conflicted"
    raise RuntimeError("Unsupported source landing disposition.")


def _apply_source_disposition(
    source_binding: Any,
    *,
    authenticated: AuthenticatedProjectSourceRequest,
    receipt_id: UUID,
    disposition: LandingDisposition,
) -> None:
    event = authenticated.event
    if disposition in {
        LandingDisposition.SOURCE_EXACT_REPLAY,
        LandingDisposition.SOURCE_SUPERSEDED,
    }:
        return
    if disposition in {
        LandingDisposition.ACCEPTED,
        LandingDisposition.RECEIVED_AFTER_CREATION,
    }:
        source_binding.highest_received_version = event.object_version
        source_binding.highest_payload_hash = event.payload_hash
        source_binding.highest_inbox_message = str(receipt_id)
    if disposition is LandingDisposition.SOURCE_CONFLICT:
        source_binding.stream_state = "conflicted"
    source_binding.optimistic_version = int(source_binding.optimistic_version) + 1
    source_binding.last_processing_code = disposition.value
    source_binding.last_processed_at = _utc_text(authenticated.received_at)
    source_binding.updated_at = _utc_text(authenticated.received_at)
    source_binding.save()


def _require_source_identity(
    source_binding: Any,
    authenticated: AuthenticatedProjectSourceRequest,
    identity: SourceStreamIdentity,
) -> None:
    expected = {
        "source_key_hash": identity.key_hash,
        "tenant_id": authenticated.profile.tenant_id,
        "profile_id": authenticated.profile.profile_id,
        "source_system": "ERPNEXT",
        "target_system": "NPI_ONE",
        "source_object_type": authenticated.event.object_type.value,
        "source_object_id": authenticated.event.source_object_id,
    }
    if any(str(_value(source_binding, key)) != str(value) for key, value in expected.items()):
        raise RuntimeError("Persisted Project source identity is invalid.")


def _locked_inbox_by_event_id(event_id: UUID):
    rows = frappe.get_all(
        "NPI Inbox Message",
        filters={"event_id": str(event_id)},
        fields=["name"],
        order_by="creation asc, name asc",
        limit_page_length=2,
    )
    if len(rows) > 1:
        raise RuntimeError("Persisted Inbox event identity is not unique.")
    if not rows:
        return None
    return frappe.get_doc(
        "NPI Inbox Message", str(_value(rows[0], "name")), for_update=True
    )


def _optional_locked_doc(doctype: str, name: str):
    try:
        return frappe.get_doc(doctype, name, for_update=True)
    except frappe.DoesNotExistError:
        return None


def _value(row: object, fieldname: str) -> object:
    return row.get(fieldname) if hasattr(row, "get") else getattr(row, fieldname)


def _utc_text(value: object) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("Timestamp must be timezone-aware.")
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
