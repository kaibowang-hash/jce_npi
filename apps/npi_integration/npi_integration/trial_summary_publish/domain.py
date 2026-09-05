from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

CONTRACT_VERSION = 1
SOURCE_SCHEMA_VERSION = "npi.released_trial_summary.erp_projection.v1"
OPERATION = "publish_released_trial_summary"
RECONCILE_OPERATION = "reconcile_released_trial_summary"
EVENT_TYPE = "npi.released_trial_summary.erp_projection.requested.v1"
MAX_MESSAGE_BYTES = 1_048_576
MAX_ATTEMPTS = 100
MAX_AUTOMATIC_ATTEMPTS = 8

_HASH = re.compile(r"^[a-f0-9]{64}$")


class TrialSummaryDeliveryError(ValueError):
    """Raised when local Trial Summary delivery evidence is invalid."""


@dataclass(frozen=True, slots=True)
class DeliverySource:
    tenant_id: str
    project_global_id: str
    trial_plan_global_id: str
    trial_round_global_id: str
    summary_global_id: str
    summary_revision_global_id: str
    summary_version: int
    actor_user_id: str
    trace_id: str
    source: Mapping[str, object]
    source_hash: str
    source_snapshot_hash: str
    target_idempotency_key_hash: str


@dataclass(frozen=True, slots=True)
class PublishCommand:
    request_global_id: str
    attempt_global_id: str
    attempt_number: int
    target_idempotency_key_hash: str
    source_hash: str
    actor_user_id: str
    source: Mapping[str, object]

    @property
    def expected_projection_id(self) -> str:
        return parse_uuid(
            self.source.get("summaryRevisionGlobalId"),
            "summaryRevisionGlobalId",
        )

    @property
    def expected_fact_count(self) -> int:
        return source_fact_count(self.source)

    def payload(self) -> dict[str, object]:
        return {
            "contractVersion": CONTRACT_VERSION,
            "operation": OPERATION,
            "requestGlobalId": self.request_global_id,
            "attemptGlobalId": self.attempt_global_id,
            "attemptNumber": self.attempt_number,
            "targetIdempotencyKeyHash": self.target_idempotency_key_hash,
            "sourceHash": self.source_hash,
            "actorUserId": self.actor_user_id,
            "source": dict(self.source),
        }


@dataclass(frozen=True, slots=True)
class ReconcileCommand:
    request_global_id: str
    attempt_global_id: str
    target_idempotency_key_hash: str
    source_hash: str
    expected_projection_id: str
    expected_fact_count: int

    def payload(self) -> dict[str, object]:
        return {
            "contractVersion": CONTRACT_VERSION,
            "operation": RECONCILE_OPERATION,
            "requestGlobalId": self.request_global_id,
            "attemptGlobalId": self.attempt_global_id,
            "targetIdempotencyKeyHash": self.target_idempotency_key_hash,
            "sourceHash": self.source_hash,
        }


@dataclass(frozen=True, slots=True)
class TargetObservation:
    http_status: int
    response_hash: str
    authenticated: bool
    contract_valid: bool
    projection_id: str | None
    fact_count: int | None
    exact_replay: bool
    error_code: str | None
    found: bool | None = None


def delivery_source(document: object) -> DeliverySource:
    from npi_core.trial.released_summary_domain import (
        released_trial_summary_from_snapshot,
    )

    try:
        raw = json.loads(str(getattr(document, "summary_snapshot")))
        summary = released_trial_summary_from_snapshot(raw)
    except Exception as error:
        raise TrialSummaryDeliveryError(
            "Released Trial Summary source validation failed."
        ) from error
    if str(getattr(document, "global_id", "")) != str(summary.global_id):
        raise TrialSummaryDeliveryError("Released Trial Summary identity drifted.")
    snapshot = summary.snapshot_payload()
    created_at = summary.created_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
    source = {
        "schemaVersion": SOURCE_SCHEMA_VERSION,
        "projectionPurpose": "erpnext_read_only_engineering_evidence",
        "formalMpAcceptance": False,
        "tenantId": summary.tenant_id,
        "projectGlobalId": str(summary.project_global_id),
        "trialPlanGlobalId": str(summary.trial_plan_global_id),
        "trialRoundGlobalId": str(summary.trial_round_global_id),
        "summaryGlobalId": str(summary.summary_global_id),
        "summaryRevisionGlobalId": str(summary.global_id),
        "summaryVersion": summary.summary_version,
        "predecessorGlobalId": (
            str(summary.predecessor_global_id)
            if summary.predecessor_global_id is not None
            else None
        ),
        "sourceSnapshotHash": summary.snapshot_hash,
        "sourceManifestHash": summary.source_manifest_hash,
        "presentationProjectionHash": summary.presentation_projection_hash,
        "redactionManifestHash": summary.redaction_manifest_hash,
        "conclusionState": summary.conclusion_state.value,
        "conclusionCode": summary.conclusion_code.value,
        "createdByUserId": summary.created_by_user_id,
        "createdAt": created_at,
        "presentationProjection": snapshot["presentationProjection"],
        "redactionManifest": snapshot["redactionManifest"],
    }
    source_hash = canonical_hash(source)
    serialized = canonical_json(source).encode("utf-8")
    if len(serialized) > MAX_MESSAGE_BYTES:
        raise TrialSummaryDeliveryError("Released Trial Summary delivery is too large.")
    target_key = canonical_hash(
        {
            "operation": OPERATION,
            "summaryRevisionGlobalId": str(summary.global_id),
        }
    )
    return DeliverySource(
        summary.tenant_id,
        str(summary.project_global_id),
        str(summary.trial_plan_global_id),
        str(summary.trial_round_global_id),
        str(summary.summary_global_id),
        str(summary.global_id),
        summary.summary_version,
        summary.created_by_user_id,
        summary.trace_id,
        source,
        source_hash,
        summary.snapshot_hash,
        target_key,
    )


def validate_persisted_source(
    source_value: object,
    *,
    source_hash: str,
    summary_revision_global_id: str,
) -> Mapping[str, object]:
    if isinstance(source_value, str):
        try:
            source_value = json.loads(source_value)
        except json.JSONDecodeError as error:
            raise TrialSummaryDeliveryError("Trial Summary source JSON is invalid.") from error
    if not isinstance(source_value, Mapping):
        raise TrialSummaryDeliveryError("Trial Summary source shape is invalid.")
    if (
        source_value.get("schemaVersion") != SOURCE_SCHEMA_VERSION
        or source_value.get("summaryRevisionGlobalId") != summary_revision_global_id
        or canonical_hash(source_value) != source_hash
    ):
        raise TrialSummaryDeliveryError("Trial Summary source binding is invalid.")
    return source_value


def source_fact_count(source: Mapping[str, object]) -> int:
    projection = source.get("presentationProjection")
    facts = projection.get("facts") if isinstance(projection, Mapping) else None
    if not isinstance(facts, Mapping):
        raise TrialSummaryDeliveryError("Trial Summary source facts are invalid.")
    expected_groups = {
        "inputChanges",
        "actualParameters",
        "samples",
        "cavityResults",
        "defects",
        "comparison",
        "controlledReferences",
        "blockers",
    }
    if set(facts) != expected_groups or any(
        not isinstance(values, list) for values in facts.values()
    ):
        raise TrialSummaryDeliveryError("Trial Summary source facts are invalid.")
    count = sum(len(values) for values in facts.values())
    if count > 25_000:
        raise TrialSummaryDeliveryError("Trial Summary source facts exceed the safe bound.")
    return count


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def valid_hash(value: object) -> bool:
    return isinstance(value, str) and _HASH.fullmatch(value) is not None


def parse_uuid(value: object, label: str) -> str:
    try:
        parsed = UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise TrialSummaryDeliveryError(f"{label} is invalid.") from error
    if parsed.int == 0 or str(parsed) != str(value).casefold():
        raise TrialSummaryDeliveryError(f"{label} is invalid.")
    return str(parsed)


def utc_now() -> datetime:
    return datetime.now(UTC)
