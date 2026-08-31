from __future__ import annotations

import json
from hashlib import sha256
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import frappe

from npi_core.change_control.response_validation import validate_change_detail_response
from npi_core.documents.frappe_repository import FrappeDocumentRepository
from npi_core.foundation.security import Principal

from .config import IntegrationProfile
from .domain import (
    FORMAL_CHANGE_DOCTYPE,
    SCHEMA_VERSION,
    SUMMARY_EVENT_TYPE,
    ChangeImplementationSummary,
    EngineeringChangeInboundEvent,
    FormalChangeObservation,
    SummaryRequest,
    TargetMode,
    canonical_hash,
    utc_text,
)
from .frappe_validation import (
    inbound_transaction_write,
    service_actor_scope,
    summary_request_write,
)
from .ingress import AuthenticatedInboundRequest
from .problems import EngineeringChangeIntegrationConflict, EngineeringChangeIntegrationUnavailable


@dataclass(frozen=True, slots=True)
class CommandOutcome:
    response: dict[str, Any]
    replayed: bool = False
    should_enqueue: bool = False
    queue_id: UUID | None = None


class FrappeEngineeringChangeIntegrationRepository(FrappeDocumentRepository):
    """Project-contained P9-01C intake and summary request transaction boundary."""

    def __init__(self, *, principal: Principal, request_id: str, trace_id: str, profile_resolver: object = None) -> None:
        super().__init__(principal=principal, request_id=request_id, trace_id=trace_id)
        self.profile_resolver = profile_resolver

    def authorize_scope(self, project_id: UUID) -> bool:
        return self._authorized_project(project_id) is not None

    def receive_inbound(self, request: AuthenticatedInboundRequest) -> CommandOutcome:
        if not isinstance(request, AuthenticatedInboundRequest):
            raise EngineeringChangeIntegrationUnavailable()
        event = request.event
        profile = request.profile
        event_hash = canonical_hash(event.envelope())
        raw_hash = sha256(request.raw_body).hexdigest()
        existing = _get_optional("NPI Engineering Change Inbox", str(event.event_id))
        if existing is not None:
            if str(existing.canonical_event_hash) != event_hash:
                raise EngineeringChangeIntegrationConflict()
            return CommandOutcome(_inbox_response(existing), replayed=True)

        source_key_hash = canonical_hash({
            "tenantId": event.tenant_id,
            "projectGlobalId": str(event.project_global_id),
            "doctype": FORMAL_CHANGE_DOCTYPE,
            "documentName": event.observation.document_name,
        })
        latest_names = frappe.get_all(
            "NPI Engineering Change Inbox",
            filters={"source_key_hash": source_key_hash},
            pluck="name",
            order_by="object_version desc, received_at desc, name desc",
            limit_page_length=1,
        )
        state = "pending"
        if latest_names:
            latest = frappe.get_doc("NPI Engineering Change Inbox", str(latest_names[0]))
            latest_version = int(latest.object_version)
            if event.object_version < latest_version:
                state = "superseded"
            elif event.object_version == latest_version:
                state = "superseded" if str(latest.canonical_event_hash) == event_hash else "quarantined"
        receipt_id = uuid4()
        response = {
            "schemaVersion": 1,
            "receiptId": str(receipt_id),
            "eventId": str(event.event_id),
            "changeGlobalId": str(event.change_global_id),
            "state": state,
            "canonicalEventHash": event_hash,
        }
        with service_actor_scope(profile.service_actor_user_id), inbound_transaction_write(profile.service_actor_user_id):
            row = frappe.get_doc({
                "doctype": "NPI Engineering Change Inbox",
                "receipt_id": str(receipt_id), "schema_version": SCHEMA_VERSION,
                "tenant_id": event.tenant_id, "project_global_id": str(event.project_global_id),
                "change_global_id": str(event.change_global_id), "event_id": str(event.event_id),
                "object_version": event.object_version, "source_key_hash": source_key_hash,
                "canonical_event_hash": event_hash, "raw_body_hash": raw_hash,
                "event_snapshot": _json(event.envelope()), "profile_id": profile.profile_id,
                "profile_version": profile.profile_version, "profile_snapshot_hash": profile.reference.snapshot_hash,
                "signing_key_id": request.headers.key_id, "signed_at": request.headers.signed_at,
                "received_at": request.received_at, "request_id": request.headers.request_id,
                "trace_id": event.trace_id, "state": state, "attempt_count": 0,
            })
            row.insert()
            self._append_audit(
                operation="engineering_change.integration.receive",
                global_id=event.change_global_id,
                object_version=event.object_version,
                result=state,
                summary={"eventId": str(event.event_id), "sourceKeyHash": source_key_hash, "canonicalEventHash": event_hash},
            )
        return CommandOutcome(response, should_enqueue=state == "pending", queue_id=receipt_id)

    def create_summary_request(
        self,
        project_id: UUID,
        change_id: UUID,
        *,
        expected_revision: int,
        expected_revision_global_id: UUID,
        expected_revision_snapshot_hash: str,
        idempotency_key_hash: str,
    ) -> CommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        profile = self._profile(str(project.tenant_id), project_id)
        if profile is None or profile.target_mode is TargetMode.DISABLED or not profile.permits(self.actor):
            raise EngineeringChangeIntegrationUnavailable()
        existing_names = frappe.get_all(
            "NPI Engineering Change Summary Request",
            filters={"tenant_id": str(project.tenant_id), "project_global_id": str(project_id), "actor_user_id": self.actor, "idempotency_key_hash": idempotency_key_hash},
            pluck="name", limit_page_length=2,
        )
        if len(existing_names) > 1:
            raise RuntimeError("Summary request idempotency scope is ambiguous.")
        if existing_names:
            existing = frappe.get_doc("NPI Engineering Change Summary Request", str(existing_names[0]))
            if str(existing.change_global_id) != str(change_id) or int(existing.revision_number) != expected_revision or str(existing.revision_global_id) != str(expected_revision_global_id) or str(existing.revision_snapshot_hash) != expected_revision_snapshot_hash:
                raise EngineeringChangeIntegrationConflict()
            return CommandOutcome(_summary_response(existing), replayed=True)

        from npi_core.change_control.frappe_repository import FrappeChangeControlRepository

        detail = FrappeChangeControlRepository(principal=self.principal, request_id=self.request_id, trace_id=self.trace_id).get_change(project_id, change_id)
        if detail is None:
            return None
        detail = validate_change_detail_response(
            detail,
            project_global_id=str(project_id),
            change_global_id=str(change_id),
        )
        current = detail["currentRevision"]
        if (
            current["revision"] != expected_revision
            or current["globalId"] != str(expected_revision_global_id)
            or current["snapshotHash"] != expected_revision_snapshot_hash
            or current["state"] != "closed"
            or current["formalChange"] is None
        ):
            raise EngineeringChangeIntegrationConflict()
        formal = current["formalChange"]
        summary = ChangeImplementationSummary(
            tenant_id=str(project.tenant_id), project_global_id=project_id, change_global_id=change_id,
            revision_global_id=expected_revision_global_id, revision_number=expected_revision,
            revision_snapshot_hash=expected_revision_snapshot_hash,
            formal_change=FormalChangeObservation(
                doctype=formal["doctype"], document_name=formal["documentName"], raw_status=formal["rawStatus"],
                source_version=formal["sourceVersion"], source_modified_at=_datetime(formal["sourceModifiedAt"]),
                source_hash=formal["sourceHash"], observed_at=_datetime(formal["observedAt"]),
            ),
            affected_versions_hash=canonical_hash(current["affectedObjects"]),
            effectivity_hash=canonical_hash(current["effectivityRules"]),
            disposition_hash=canonical_hash(current["dispositions"]),
            revalidation_hash=canonical_hash(current["revalidationRequirements"]),
            closure_evidence_hash=canonical_hash(current["closureEvidence"]),
        )
        now = datetime.now(UTC)
        request_value = SummaryRequest(
            global_id=uuid4(), summary=summary, profile=profile.reference, actor_user_id=self.actor,
            service_actor_user_id=profile.service_actor_user_id, request_id=UUID(self.request_id),
            trace_id=self.trace_id, idempotency_key_hash=idempotency_key_hash, created_at=now,
        )
        event_id = uuid4()
        response = {
            "schemaVersion": 1, "requestGlobalId": str(request_value.global_id),
            "changeGlobalId": str(change_id), "revisionGlobalId": str(expected_revision_global_id),
            "revisionNumber": expected_revision, "sourceHash": summary.source_hash,
            "state": "queued", "outboxEventId": str(event_id),
        }
        with summary_request_write(self.actor):
            request_row = frappe.get_doc({
                "doctype": "NPI Engineering Change Summary Request", "global_id": str(request_value.global_id),
                "tenant_id": str(project.tenant_id), "project_global_id": str(project_id), "change_global_id": str(change_id),
                "revision_global_id": str(expected_revision_global_id), "revision_number": expected_revision,
                "revision_snapshot_hash": expected_revision_snapshot_hash, "source_snapshot": _json(summary.payload()),
                "source_hash": summary.source_hash, "profile_id": profile.profile_id, "profile_version": profile.profile_version,
                "profile_snapshot_hash": profile.reference.snapshot_hash, "actor_user_id": self.actor,
                "service_actor_user_id": profile.service_actor_user_id, "request_id": self.request_id,
                "trace_id": self.trace_id, "idempotency_key_hash": idempotency_key_hash,
                "state": "queued", "outbox_event_id": str(event_id), "created_at": now, "updated_at": now,
            })
            request_row.insert()
            payload = request_value.event_payload()
            frappe.get_doc({
                "doctype": "NPI Engineering Change Summary Outbox", "event_id": str(event_id),
                "schema_version": SCHEMA_VERSION, "event_type": SUMMARY_EVENT_TYPE,
                "request_global_id": str(request_value.global_id), "tenant_id": str(project.tenant_id),
                "project_global_id": str(project_id), "change_global_id": str(change_id),
                "revision_global_id": str(expected_revision_global_id), "source_hash": summary.source_hash,
                "payload": _json(payload), "payload_hash": canonical_hash(payload),
                "profile_snapshot_hash": profile.reference.snapshot_hash,
                "service_actor_user_id": profile.service_actor_user_id, "trace_id": self.trace_id,
                "target_idempotency_key_hash": idempotency_key_hash, "state": "pending", "attempt_count": 0,
            }).insert()
            self._append_audit(
                operation="engineering_change.summary.request",
                global_id=request_value.global_id, object_version=1, result="queued",
                summary={"changeGlobalId": str(change_id), "revisionGlobalId": str(expected_revision_global_id), "sourceHash": summary.source_hash, "outboxEventId": str(event_id)},
            )
        return CommandOutcome(response, should_enqueue=True, queue_id=event_id)

    def _profile(self, tenant_id: str, project_id: UUID) -> IntegrationProfile | None:
        if not callable(self.profile_resolver):
            return None
        value = self.profile_resolver(tenant_id, project_id)
        return value if isinstance(value, IntegrationProfile) else None


def _summary_response(row: Any) -> dict[str, Any]:
    return {"schemaVersion": 1, "requestGlobalId": str(row.global_id), "changeGlobalId": str(row.change_global_id), "revisionGlobalId": str(row.revision_global_id), "revisionNumber": int(row.revision_number), "sourceHash": str(row.source_hash), "state": str(row.state), "outboxEventId": str(row.outbox_event_id)}


def _inbox_response(row: Any) -> dict[str, Any]:
    return {"schemaVersion": 1, "receiptId": str(row.receipt_id), "eventId": str(row.event_id), "changeGlobalId": str(row.change_global_id), "state": str(row.state), "canonicalEventHash": str(row.canonical_event_hash)}


def _get_optional(doctype: str, name: str) -> Any | None:
    try:
        return frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        return None


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _datetime(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise EngineeringChangeIntegrationConflict()
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(UTC)
    except ValueError as error:
        raise EngineeringChangeIntegrationConflict() from error
