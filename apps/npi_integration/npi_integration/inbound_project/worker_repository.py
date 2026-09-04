from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

import frappe

from npi_core.foundation.audit import create_audit_event
from npi_core.foundation.errors import NpiProblem
from npi_core.foundation.security import Principal
from npi_core.project.domain import (
    BusinessCodeConflict,
    CreateProjectCommand,
    ProjectInstantiationService,
    ProjectLifecycleState,
    ProjectSourceSystem,
    ProjectType,
    TemplateNotPublished,
    TemplateUnavailable,
    actor_idempotency_key_hash,
)
from npi_core.project.frappe_repository import FrappeProjectRepository

from .config import InboundProjectProfile, ProjectIntakePolicy
from .domain import (
    ClaimLease,
    ProjectSourceContractError,
    canonical_json_hash,
    issue_claim,
    parse_project_source_event,
)
from .frappe_validation import inbound_project_repository_write


CLAIM_LEASE_SECONDS = 300
RECOVERY_BATCH_LIMIT = 100


@dataclass(frozen=True, slots=True)
class ClaimedInboxMessage:
    receipt_id: UUID
    event_id: UUID
    source_key_hash: str
    trace_id: str
    lease: ClaimLease
    expired_recovery: bool


@dataclass(frozen=True, slots=True)
class InboundProjectWorkerOutcome:
    receipt_id: UUID
    state: str
    disposition: str
    project_global_id: UUID | None = None
    replayed: bool = False


class InboundProjectFinalFailure(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class FrappeInboundProjectWorkerRepository:
    """Claim and complete one P8-02 receipt with closed transactional effects."""

    def claim(
        self,
        receipt_id: UUID,
        *,
        now: datetime,
        lease_seconds: int = CLAIM_LEASE_SECONDS,
    ) -> ClaimedInboxMessage | None:
        inbox = _optional_locked_doc("NPI Inbox Message", str(receipt_id))
        if inbox is None or not _authenticated_v1(inbox):
            return None
        state = str(_value(inbox, "state"))
        expired_recovery = False
        if state == "processing":
            expires_at = _stored_utc(_value(inbox, "lease_expires_at"))
            if _aware_utc(now) < expires_at:
                return None
            expired_recovery = True
        elif state != "pending":
            return None
        lease = issue_claim(
            now=_aware_utc(now),
            lease_seconds=lease_seconds,
            previous_attempt_count=int(_value(inbox, "attempt_count") or 0),
        )
        with inbound_project_repository_write():
            inbox.state = "processing"
            inbox.disposition = "pending"
            inbox.claim_token = str(lease.token)
            inbox.claimed_at = _utc_text(lease.claimed_at)
            inbox.lease_expires_at = _utc_text(lease.expires_at)
            inbox.attempt_count = lease.attempt_count
            inbox.last_error_code = None
            inbox.last_error_at = None
            inbox.project_global_id = None
            inbox.project_result_hash = None
            inbox.save()
            _append_audit(
                actor="npi-inbound-worker",
                trace_id=str(_value(inbox, "trace_id")),
                operation=(
                    "inbound_project.claim_recovered"
                    if expired_recovery
                    else "inbound_project.claim"
                ),
                global_id=UUID(str(_value(inbox, "event_id"))),
                object_version=int(_value(inbox, "object_version")),
                result="processing",
                summary={
                    "attemptCount": lease.attempt_count,
                    "expiredRecovery": expired_recovery,
                    "receiptId": str(receipt_id),
                    "sourceKeyHash": str(_value(inbox, "source_key_hash")),
                },
            )
        return ClaimedInboxMessage(
            receipt_id=receipt_id,
            event_id=UUID(str(_value(inbox, "event_id"))),
            source_key_hash=str(_value(inbox, "source_key_hash")),
            trace_id=str(_value(inbox, "trace_id")),
            lease=lease,
            expired_recovery=expired_recovery,
        )

    def process_claim(
        self,
        claim: ClaimedInboxMessage,
        *,
        profile: InboundProjectProfile | None,
        now: datetime,
    ) -> InboundProjectWorkerOutcome:
        inbox = _required_locked_claim(claim)
        event = _validated_event(inbox)
        policy = _validated_policy(inbox, event.object_type.value)
        _require_profile(profile, inbox, policy)
        assert profile is not None

        binding = _optional_locked_doc(
            "NPI Project Source Binding", claim.source_key_hash
        )
        if binding is None:
            raise RuntimeError("Persisted Project source binding is unavailable.")
        _require_binding_identity(binding, inbox)
        source_outcome = _source_terminal_outcome(binding, inbox)
        if source_outcome is not None:
            state, disposition = source_outcome
            return _seal_non_project_outcome(
                binding=binding,
                inbox=inbox,
                claim=claim,
                actor=profile.service_actor_user_id,
                now=now,
                state=state,
                disposition=disposition,
            )

        bound_project = _value(binding, "bound_project_global_id")
        if bound_project:
            return _seal_project_outcome(
                binding=binding,
                inbox=inbox,
                claim=claim,
                actor=profile.service_actor_user_id,
                now=now,
                project_global_id=UUID(str(bound_project)),
                replayed=True,
            )

        principal = _service_principal(profile, str(_value(inbox, "tenant_id")))
        _require_enabled_owner(policy.owner_user_id)
        project_repository = FrappeProjectRepository(
            principal=principal,
            request_id=str(_value(inbox, "request_id")),
            trace_id=str(_value(inbox, "trace_id")),
        )
        template = project_repository.get_template_version(
            policy.template_global_id,
            policy.template_version,
        )
        if template is None:
            raise InboundProjectFinalFailure("INBOUND_PROJECT_TEMPLATE_UNAVAILABLE")
        try:
            project_type = ProjectType(policy.project_type)
            command = CreateProjectCommand(
                idempotency_key=actor_idempotency_key_hash(
                    profile.service_actor_user_id,
                    f"inbound-project-source:{claim.source_key_hash}",
                ),
                tenant_id=str(_value(inbox, "tenant_id")),
                business_code=str(_value(inbox, "source_object_id")),
                title=event.payload.title,
                project_type=project_type,
                owner_user_id=policy.owner_user_id,
                target_sop=date.fromisoformat(event.payload.target_sop),
                template_global_id=policy.template_global_id,
                template_version=policy.template_version,
                expected_version=template.version,
                references=(),
            )
            result = ProjectInstantiationService(project_repository).instantiate(command)
        except (TemplateUnavailable, TemplateNotPublished) as error:
            raise InboundProjectFinalFailure(
                "INBOUND_PROJECT_TEMPLATE_UNAVAILABLE"
            ) from error
        except BusinessCodeConflict as error:
            raise InboundProjectFinalFailure(
                "INBOUND_PROJECT_BUSINESS_CODE_CONFLICT"
            ) from error
        except NpiProblem as error:
            raise InboundProjectFinalFailure(
                "INBOUND_PROJECT_COMMAND_REJECTED"
            ) from error
        project = result.project
        if (
            project.state is not ProjectLifecycleState.DRAFT
            or project.source_system is not ProjectSourceSystem.NPI_ONE
            or project.tenant_id != str(_value(inbox, "tenant_id"))
            or project.business_code != str(_value(inbox, "source_object_id"))
        ):
            raise RuntimeError("Created Project result violates the inbound contract.")
        return _seal_project_outcome(
            binding=binding,
            inbox=inbox,
            claim=claim,
            actor=profile.service_actor_user_id,
            now=now,
            project_global_id=project.global_id,
            replayed=result.replayed,
        )

    def mark_failure(
        self,
        claim: ClaimedInboxMessage,
        *,
        code: str,
        retryable: bool,
        now: datetime,
    ) -> bool:
        inbox = _optional_locked_doc("NPI Inbox Message", str(claim.receipt_id))
        if inbox is None or not _claim_matches(inbox, claim):
            return False
        state = "failed_retryable" if retryable else "failed_final"
        with inbound_project_repository_write():
            inbox.state = state
            inbox.disposition = state
            inbox.last_error_code = code
            inbox.last_error_at = _utc_text(now)
            inbox.project_global_id = None
            inbox.project_result_hash = None
            inbox.save()
            _append_audit(
                actor="npi-inbound-worker",
                trace_id=claim.trace_id,
                operation="inbound_project.fail",
                global_id=claim.event_id,
                object_version=int(_value(inbox, "object_version")),
                result=state,
                summary={
                    "errorCode": code,
                    "receiptId": str(claim.receipt_id),
                    "retryable": retryable,
                    "sourceKeyHash": claim.source_key_hash,
                },
            )
        return True

    def recoverable_receipt_ids(
        self,
        *,
        now: datetime,
        limit: int = RECOVERY_BATCH_LIMIT,
    ) -> tuple[UUID, ...]:
        if type(limit) is not int or not 1 <= limit <= RECOVERY_BATCH_LIMIT:
            raise ValueError("Recovery batch limit is invalid.")
        fields = ["name"]
        common = {"schema_version": 1, "authenticated": 1}
        rows = frappe.get_all(
            "NPI Inbox Message",
            filters={**common, "state": "pending"},
            fields=fields,
            order_by="received_at asc, name asc",
            limit_page_length=limit,
        )
        remaining = limit - len(rows)
        if remaining:
            rows.extend(
                frappe.get_all(
                    "NPI Inbox Message",
                    filters=[
                        ["schema_version", "=", 1],
                        ["authenticated", "=", 1],
                        ["state", "=", "processing"],
                        ["lease_expires_at", "<=", _utc_text(now)],
                    ],
                    fields=fields,
                    order_by="lease_expires_at asc, name asc",
                    limit_page_length=remaining,
                )
            )
        return tuple(UUID(str(_value(row, "name"))) for row in rows)


def _validated_event(inbox: Any):
    try:
        event = parse_project_source_event(str(_value(inbox, "raw_body")).encode("utf-8"))
    except (ProjectSourceContractError, UnicodeEncodeError) as error:
        raise InboundProjectFinalFailure("INBOUND_PROJECT_RECEIPT_INVALID") from error
    expected = {
        "event_id": str(event.event_id),
        "canonical_event_hash": event.canonical_event_hash,
        "payload_hash": event.payload_hash,
        "source_object_type": event.object_type.value,
        "source_object_id": event.source_object_id,
        "object_version": event.object_version,
        "trace_id": event.trace_id,
    }
    if any(str(_value(inbox, key)) != str(value) for key, value in expected.items()):
        raise InboundProjectFinalFailure("INBOUND_PROJECT_RECEIPT_INVALID")
    return event


def _validated_policy(inbox: Any, source_object_type: str) -> ProjectIntakePolicy:
    try:
        snapshot = _json_object(_value(inbox, "policy_snapshot"))
        policy = ProjectIntakePolicy.from_snapshot(snapshot)
    except (ProjectSourceContractError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise InboundProjectFinalFailure("INBOUND_PROJECT_POLICY_UNAVAILABLE") from error
    if (
        policy.source_object_type.value != source_object_type
        or policy.snapshot_hash != str(_value(inbox, "policy_hash"))
    ):
        raise InboundProjectFinalFailure("INBOUND_PROJECT_POLICY_UNAVAILABLE")
    return policy


def _require_profile(
    profile: InboundProjectProfile | None,
    inbox: Any,
    policy: ProjectIntakePolicy,
) -> None:
    if (
        not isinstance(profile, InboundProjectProfile)
        or not profile.enabled
        or profile.profile_id != str(_value(inbox, "profile_id"))
        or profile.version != int(_value(inbox, "profile_version"))
        or profile.tenant_id != str(_value(inbox, "tenant_id"))
    ):
        raise InboundProjectFinalFailure("INBOUND_PROJECT_PROFILE_UNAVAILABLE")
    configured = profile.policy_by_object_type.get(policy.source_object_type)
    if configured is None or configured.snapshot_hash != policy.snapshot_hash:
        raise InboundProjectFinalFailure("INBOUND_PROJECT_POLICY_UNAVAILABLE")


def _service_principal(profile: InboundProjectProfile, tenant_id: str) -> Principal:
    actor = profile.service_actor_user_id
    user = frappe.db.get_value(
        "User", actor, ["enabled", "user_type"], as_dict=True
    )
    roles = frozenset(frappe.get_roles(actor)) if user else frozenset()
    if (
        not user
        or int(_value(user, "enabled") or 0) != 1
        or str(_value(user, "user_type")) != "System User"
        or "NPI API User" not in roles
    ):
        raise InboundProjectFinalFailure("INBOUND_PROJECT_SERVICE_ACTOR_UNAVAILABLE")
    return Principal(
        user_id=actor,
        roles=roles,
        tenant_id=tenant_id,
        is_external=False,
    )


def _require_enabled_owner(owner_user_id: str) -> None:
    if frappe.db.get_value("User", owner_user_id, "enabled") != 1:
        raise InboundProjectFinalFailure("INBOUND_PROJECT_OWNER_UNAVAILABLE")


def _source_terminal_outcome(binding: Any, inbox: Any) -> tuple[str, str] | None:
    if str(_value(binding, "stream_state")) == "conflicted":
        return "quarantined", "conflicted"
    inbox_version = int(_value(inbox, "object_version"))
    highest_version = int(_value(binding, "highest_received_version"))
    if inbox_version < highest_version:
        return "superseded", "superseded"
    if inbox_version > highest_version:
        raise RuntimeError("Inbox version is ahead of its locked source head.")
    if str(_value(inbox, "payload_hash")) != str(
        _value(binding, "highest_payload_hash")
    ):
        return "quarantined", "conflicted"
    return None


def _seal_non_project_outcome(
    *,
    binding: Any,
    inbox: Any,
    claim: ClaimedInboxMessage,
    actor: str,
    now: datetime,
    state: str,
    disposition: str,
) -> InboundProjectWorkerOutcome:
    with inbound_project_repository_write():
        inbox.state = state
        inbox.disposition = disposition
        inbox.last_error_code = None
        inbox.last_error_at = None
        inbox.project_global_id = None
        inbox.project_result_hash = None
        inbox.save()
        _touch_binding(binding, disposition, now)
        _append_audit(
            actor=actor,
            trace_id=claim.trace_id,
            operation="inbound_project.complete",
            global_id=claim.event_id,
            object_version=int(_value(inbox, "object_version")),
            result=disposition,
            summary={
                "receiptId": str(claim.receipt_id),
                "sourceKeyHash": claim.source_key_hash,
            },
        )
    return InboundProjectWorkerOutcome(
        receipt_id=claim.receipt_id,
        state=state,
        disposition=disposition,
    )


def _seal_project_outcome(
    *,
    binding: Any,
    inbox: Any,
    claim: ClaimedInboxMessage,
    actor: str,
    now: datetime,
    project_global_id: UUID,
    replayed: bool,
) -> InboundProjectWorkerOutcome:
    disposition = "project_replayed" if replayed else "project_created"
    result_hash = canonical_json_hash(
        {
            "project_global_id": str(project_global_id),
            "receipt_id": str(claim.receipt_id),
            "source_key_hash": claim.source_key_hash,
        }
    )
    with inbound_project_repository_write():
        if not _value(binding, "bound_project_global_id"):
            binding.stream_state = "bound"
            binding.bound_project_global_id = str(project_global_id)
            binding.bound_inbox_message = str(claim.receipt_id)
            binding.bound_version = int(_value(inbox, "object_version"))
            binding.bound_payload_hash = str(_value(inbox, "payload_hash"))
            binding.bound_policy_snapshot = _json_object(
                _value(inbox, "policy_snapshot")
            )
            binding.bound_policy_hash = str(_value(inbox, "policy_hash"))
        elif str(_value(binding, "bound_project_global_id")) != str(project_global_id):
            raise RuntimeError("Project source binding result is inconsistent.")
        _touch_binding(binding, disposition, now)
        inbox.state = "succeeded"
        inbox.disposition = disposition
        inbox.last_error_code = None
        inbox.last_error_at = None
        inbox.project_global_id = str(project_global_id)
        inbox.project_result_hash = result_hash
        inbox.save()
        _append_audit(
            actor=actor,
            trace_id=claim.trace_id,
            operation="inbound_project.complete",
            global_id=claim.event_id,
            object_version=int(_value(inbox, "object_version")),
            result=disposition,
            summary={
                "projectGlobalId": str(project_global_id),
                "receiptId": str(claim.receipt_id),
                "sourceKeyHash": claim.source_key_hash,
            },
        )
    return InboundProjectWorkerOutcome(
        receipt_id=claim.receipt_id,
        state="succeeded",
        disposition=disposition,
        project_global_id=project_global_id,
        replayed=replayed,
    )


def _touch_binding(binding: Any, code: str, now: datetime) -> None:
    binding.optimistic_version = int(_value(binding, "optimistic_version")) + 1
    binding.last_processing_code = code
    binding.last_processed_at = _utc_text(now)
    binding.updated_at = _utc_text(now)
    binding.save()


def _required_locked_claim(claim: ClaimedInboxMessage):
    inbox = _optional_locked_doc("NPI Inbox Message", str(claim.receipt_id))
    if inbox is None or not _claim_matches(inbox, claim):
        raise RuntimeError("Inbound Project claim is no longer current.")
    return inbox


def _claim_matches(inbox: Any, claim: ClaimedInboxMessage) -> bool:
    return (
        _authenticated_v1(inbox)
        and str(_value(inbox, "state")) == "processing"
        and str(_value(inbox, "claim_token")) == str(claim.lease.token)
        and int(_value(inbox, "attempt_count") or 0) == claim.lease.attempt_count
    )


def _authenticated_v1(inbox: Any) -> bool:
    return (
        int(_value(inbox, "schema_version") or 0) == 1
        and int(_value(inbox, "authenticated") or 0) == 1
    )


def _require_binding_identity(binding: Any, inbox: Any) -> None:
    expected = {
        "source_key_hash": _value(inbox, "source_key_hash"),
        "tenant_id": _value(inbox, "tenant_id"),
        "profile_id": _value(inbox, "profile_id"),
        "source_system": "ERPNEXT",
        "target_system": "NPI_ONE",
        "source_object_type": _value(inbox, "source_object_type"),
        "source_object_id": _value(inbox, "source_object_id"),
    }
    if any(str(_value(binding, key)) != str(value) for key, value in expected.items()):
        raise RuntimeError("Persisted Project source identity is invalid.")


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


def _optional_locked_doc(doctype: str, name: str):
    try:
        return frappe.get_doc(doctype, name, for_update=True)
    except frappe.DoesNotExistError:
        return None


def _json_object(value: object) -> dict[str, object]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, dict):
        raise TypeError("JSON object is required.")
    return dict(parsed)


def _stored_utc(value: object) -> datetime:
    if isinstance(value, datetime):
        return _aware_utc(value)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError("Stored claim lease is invalid.")
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    return _aware_utc(parsed)


def _aware_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError("Timestamp must be a datetime.")
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return _aware_utc(value).strftime("%Y-%m-%dT%H:%M:%SZ")


def _value(row: object, fieldname: str) -> object:
    return row.get(fieldname) if hasattr(row, "get") else getattr(row, fieldname)
