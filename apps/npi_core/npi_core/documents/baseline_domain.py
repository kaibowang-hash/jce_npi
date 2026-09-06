from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from npi_core.documents.release_domain import DocumentReviewEvidence
from npi_core.foundation.errors import NpiProblem, RequestValidationFailed

try:
    from frappe import _
except ImportError:  # Keeps the domain independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


DOCUMENT_BASELINE_POLICY_SCHEMA_VERSION = 1
DOCUMENT_BASELINE_SCHEMA_VERSION = 1
BASELINE_GATE_DEPENDENCY_SCHEMA_VERSION = 1
BASELINE_IMPACT_SCHEMA_VERSION = 1
MAX_BASELINE_MEMBERS = 100

_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_TENANT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def sha256_json(value: object) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class DocumentBaselinePolicyState(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class BaselineImpactEventType(StrEnum):
    INVALIDATED = "invalidated"


class DocumentBaselinePolicyUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "DOCUMENT_BASELINE_POLICY_UNAVAILABLE",
            _("The document baseline policy is unavailable."),
        )


class DocumentBaselineAuthorityUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            403,
            "DOCUMENT_BASELINE_AUTHORITY_UNAVAILABLE",
            _("You are not authorized to create this document baseline."),
        )


class DocumentBaselineInputUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            422,
            "DOCUMENT_BASELINE_INPUT_UNAVAILABLE",
            _("The exact released document baseline input is unavailable."),
        )


class DocumentBaselineUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "DOCUMENT_BASELINE_UNAVAILABLE",
            _("The document baseline is unavailable."),
        )


class DocumentBaselineIdempotencyConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "DOCUMENT_BASELINE_IDEMPOTENCY_CONFLICT",
            _("The idempotency key was already used for a different baseline."),
        )


@dataclass(frozen=True, slots=True)
class DocumentBaselinePolicyReference:
    global_id: UUID
    version: int
    snapshot_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "policy.globalId"))
        object.__setattr__(self, "version", _positive(self.version, "policy.version"))
        object.__setattr__(
            self,
            "snapshot_hash",
            _hash(self.snapshot_hash, "policy.snapshotHash"),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "version": self.version,
            "snapshotHash": self.snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class DocumentBaselineMemberPrecondition:
    revision_id: UUID
    expected_revision_snapshot_hash: str
    expected_lifecycle_version: int
    expected_release_snapshot_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "revision_id",
            _uuid(self.revision_id, "baselineInput.revisionId"),
        )
        object.__setattr__(
            self,
            "expected_revision_snapshot_hash",
            _hash(
                self.expected_revision_snapshot_hash,
                "baselineInput.expectedRevisionSnapshotHash",
            ),
        )
        object.__setattr__(
            self,
            "expected_lifecycle_version",
            _positive(
                self.expected_lifecycle_version,
                "baselineInput.expectedLifecycleVersion",
            ),
        )
        object.__setattr__(
            self,
            "expected_release_snapshot_hash",
            _hash(
                self.expected_release_snapshot_hash,
                "baselineInput.expectedReleaseSnapshotHash",
            ),
        )


@dataclass(frozen=True, slots=True)
class DocumentBaselinePolicyVersion:
    global_id: UUID
    policy_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    policy_key: str
    policy_version: int
    title: str
    state: DocumentBaselinePolicyState
    baseline_authority_user_ids: tuple[str, ...]
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "global_id",
            _uuid(self.global_id, "baselinePolicy.globalId"),
        )
        object.__setattr__(
            self,
            "policy_global_id",
            _uuid(self.policy_global_id, "baselinePolicy.policyGlobalId"),
        )
        object.__setattr__(
            self,
            "tenant_id",
            _text(
                self.tenant_id,
                "baselinePolicy.tenantId",
                maximum=128,
                pattern=_TENANT_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "project_global_id",
            _uuid(self.project_global_id, "baselinePolicy.projectGlobalId"),
        )
        object.__setattr__(
            self,
            "policy_key",
            _text(
                self.policy_key,
                "baselinePolicy.key",
                maximum=64,
                pattern=_KEY_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "policy_version",
            _positive(self.policy_version, "baselinePolicy.version"),
        )
        object.__setattr__(
            self,
            "title",
            _text(self.title, "baselinePolicy.title", maximum=140),
        )
        if not isinstance(self.state, DocumentBaselinePolicyState):
            raise _field_problem(
                "baselinePolicy.state",
                _("Select a supported value."),
            )
        authorities = _users(
            self.baseline_authority_user_ids,
            "baselinePolicy.baselineAuthorityUserIds",
        )
        object.__setattr__(self, "baseline_authority_user_ids", authorities)
        expected = sha256_json(self.snapshot_payload())
        if self.snapshot_hash and self.snapshot_hash != expected:
            raise _field_problem(
                "baselinePolicy.snapshotHash",
                _("The baseline policy snapshot hash does not match its content."),
            )
        object.__setattr__(self, "snapshot_hash", expected)

    @property
    def reference(self) -> DocumentBaselinePolicyReference:
        return DocumentBaselinePolicyReference(
            self.policy_global_id,
            self.policy_version,
            self.snapshot_hash,
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": DOCUMENT_BASELINE_POLICY_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "policyGlobalId": str(self.policy_global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "key": self.policy_key,
            "version": self.policy_version,
            "title": self.title,
            "state": self.state.value,
            "baselineAuthorityUserIds": sorted(
                self.baseline_authority_user_ids,
                key=str.casefold,
            ),
        }

    def permits_baseline(self, actor: str) -> bool:
        candidate = actor.casefold()
        return any(
            value.casefold() == candidate
            for value in self.baseline_authority_user_ids
        )


@dataclass(frozen=True, slots=True)
class DocumentBaselineMember:
    global_id: UUID
    sequence: int
    document_global_id: UUID
    revision_global_id: UUID
    major: int
    minor: int
    revision_snapshot_hash: str
    lifecycle_version: int
    release_event_global_id: UUID
    release_snapshot_hash: str
    release_evidence: DocumentReviewEvidence

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "document_global_id",
            "revision_global_id",
            "release_event_global_id",
        ):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), f"baselineMember.{fieldname}"),
            )
        object.__setattr__(
            self,
            "sequence",
            _positive(self.sequence, "baselineMember.sequence"),
        )
        object.__setattr__(
            self,
            "major",
            _nonnegative(self.major, "baselineMember.major"),
        )
        object.__setattr__(
            self,
            "minor",
            _nonnegative(self.minor, "baselineMember.minor"),
        )
        object.__setattr__(
            self,
            "revision_snapshot_hash",
            _hash(
                self.revision_snapshot_hash,
                "baselineMember.revisionSnapshotHash",
            ),
        )
        object.__setattr__(
            self,
            "lifecycle_version",
            _positive(self.lifecycle_version, "baselineMember.lifecycleVersion"),
        )
        object.__setattr__(
            self,
            "release_snapshot_hash",
            _hash(
                self.release_snapshot_hash,
                "baselineMember.releaseSnapshotHash",
            ),
        )
        if not isinstance(self.release_evidence, DocumentReviewEvidence):
            raise _field_problem(
                "baselineMember.releaseEvidence",
                _("Enter exact released file evidence."),
            )
        if self.release_evidence.revision_global_id != self.revision_global_id:
            raise _field_problem(
                "baselineMember.releaseEvidence",
                _("Released file evidence does not match the document revision."),
            )
        if (
            self.release_evidence.revision_snapshot_hash
            != self.revision_snapshot_hash
        ):
            raise _field_problem(
                "baselineMember.revisionSnapshotHash",
                _("The revision snapshot hash does not match released evidence."),
            )

    @property
    def member_hash(self) -> str:
        return sha256_json(self.canonical_dict())

    def canonical_dict(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "sequence": self.sequence,
            "documentGlobalId": str(self.document_global_id),
            "revisionGlobalId": str(self.revision_global_id),
            "major": self.major,
            "minor": self.minor,
            "revisionSnapshotHash": self.revision_snapshot_hash,
            "lifecycleVersion": self.lifecycle_version,
            "releaseEventGlobalId": str(self.release_event_global_id),
            "releaseSnapshotHash": self.release_snapshot_hash,
            "releaseEvidence": self.release_evidence.canonical_dict(),
        }


@dataclass(frozen=True, slots=True)
class DocumentBaseline:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    label: str
    policy_ref: DocumentBaselinePolicyReference
    members: tuple[DocumentBaselineMember, ...]
    created_by_user_id: str
    created_at: datetime
    request_id: str
    trace_id: str
    version: int = 1
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "baseline.globalId"))
        object.__setattr__(
            self,
            "tenant_id",
            _text(
                self.tenant_id,
                "baseline.tenantId",
                maximum=128,
                pattern=_TENANT_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "project_global_id",
            _uuid(self.project_global_id, "baseline.projectGlobalId"),
        )
        object.__setattr__(
            self,
            "label",
            _text(self.label, "baseline.label", maximum=140),
        )
        if not isinstance(self.policy_ref, DocumentBaselinePolicyReference):
            raise _field_problem(
                "baseline.policyRef",
                _("Select an exact baseline policy version."),
            )
        if (
            isinstance(self.members, (str, bytes))
            or not isinstance(self.members, Sequence)
            or not self.members
            or len(self.members) > MAX_BASELINE_MEMBERS
            or not all(isinstance(value, DocumentBaselineMember) for value in self.members)
        ):
            raise _field_problem(
                "baseline.members",
                _("Enter a bounded list of exact released revisions."),
            )
        ordered = tuple(sorted(self.members, key=lambda value: value.sequence))
        if [value.sequence for value in ordered] != list(range(1, len(ordered) + 1)):
            raise _field_problem(
                "baseline.members",
                _("Baseline member sequence must be contiguous."),
            )
        member_ids = [value.global_id for value in ordered]
        revision_ids = [value.revision_global_id for value in ordered]
        if len(member_ids) != len(set(member_ids)) or len(revision_ids) != len(
            set(revision_ids)
        ):
            raise _field_problem(
                "baseline.members",
                _("Baseline members and revisions must be unique."),
            )
        object.__setattr__(self, "members", ordered)
        object.__setattr__(
            self,
            "created_by_user_id",
            _text(
                self.created_by_user_id,
                "baseline.createdByUserId",
                maximum=254,
                pattern=_ACTOR_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "created_at",
            _utc_datetime(self.created_at, "baseline.createdAt"),
        )
        object.__setattr__(
            self,
            "request_id",
            _text(self.request_id, "baseline.requestId", maximum=128),
        )
        object.__setattr__(
            self,
            "trace_id",
            _text(self.trace_id, "baseline.traceId", maximum=128),
        )
        if self.version != 1:
            raise _field_problem(
                "baseline.version",
                _("An immutable baseline must use version 1."),
            )
        expected = sha256_json(self.snapshot_payload())
        if self.snapshot_hash and self.snapshot_hash != expected:
            raise _field_problem(
                "baseline.snapshotHash",
                _("The baseline snapshot hash does not match its members."),
            )
        object.__setattr__(self, "snapshot_hash", expected)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": DOCUMENT_BASELINE_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "label": self.label,
            "version": self.version,
            "policyRef": self.policy_ref.canonical_dict(),
            "members": [value.canonical_dict() for value in self.members],
            "createdByUserId": self.created_by_user_id,
            "createdAt": _timestamp(self.created_at),
            "requestId": self.request_id,
            "traceId": self.trace_id,
        }


def create_document_baseline(
    *,
    global_id: UUID,
    tenant_id: str,
    project_global_id: UUID,
    label: str,
    policy: DocumentBaselinePolicyVersion,
    members: Sequence[DocumentBaselineMember],
    actor: str,
    now: datetime,
    request_id: str,
    trace_id: str,
) -> DocumentBaseline:
    if (
        policy.state is not DocumentBaselinePolicyState.PUBLISHED
        or policy.tenant_id != tenant_id
        or policy.project_global_id != project_global_id
    ):
        raise DocumentBaselinePolicyUnavailable()
    if not policy.permits_baseline(actor):
        raise DocumentBaselineAuthorityUnavailable()
    return DocumentBaseline(
        global_id=global_id,
        tenant_id=tenant_id,
        project_global_id=project_global_id,
        label=label,
        policy_ref=policy.reference,
        members=tuple(members),
        created_by_user_id=actor,
        created_at=now,
        request_id=request_id,
        trace_id=trace_id,
    )


@dataclass(frozen=True, slots=True)
class BaselineGateDependency:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    baseline_global_id: UUID
    baseline_snapshot_hash: str
    input_document_global_id: UUID
    input_revision_global_id: UUID
    input_revision_snapshot_hash: str
    gate_global_id: UUID
    requirement_global_id: UUID
    requirement_key: str
    evidence_reference_global_id: UUID
    registered_by_user_id: str
    registered_at: datetime
    request_id: str
    trace_id: str
    dependency_key: str = ""
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "project_global_id",
            "baseline_global_id",
            "input_document_global_id",
            "input_revision_global_id",
            "gate_global_id",
            "requirement_global_id",
            "evidence_reference_global_id",
        ):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), f"baselineDependency.{fieldname}"),
            )
        object.__setattr__(
            self,
            "tenant_id",
            _text(
                self.tenant_id,
                "baselineDependency.tenantId",
                maximum=128,
                pattern=_TENANT_PATTERN,
            ),
        )
        for fieldname in ("baseline_snapshot_hash", "input_revision_snapshot_hash"):
            object.__setattr__(
                self,
                fieldname,
                _hash(getattr(self, fieldname), f"baselineDependency.{fieldname}"),
            )
        object.__setattr__(
            self,
            "requirement_key",
            _text(
                self.requirement_key,
                "baselineDependency.requirementKey",
                maximum=64,
                pattern=_KEY_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "registered_by_user_id",
            _text(
                self.registered_by_user_id,
                "baselineDependency.registeredByUserId",
                maximum=254,
                pattern=_ACTOR_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "registered_at",
            _utc_datetime(self.registered_at, "baselineDependency.registeredAt"),
        )
        object.__setattr__(
            self,
            "request_id",
            _text(self.request_id, "baselineDependency.requestId", maximum=128),
        )
        object.__setattr__(
            self,
            "trace_id",
            _text(self.trace_id, "baselineDependency.traceId", maximum=128),
        )
        expected_key = sha256_json(
            {
                "tenantId": self.tenant_id,
                "projectGlobalId": str(self.project_global_id),
                "baselineGlobalId": str(self.baseline_global_id),
                "inputRevisionGlobalId": str(self.input_revision_global_id),
                "gateGlobalId": str(self.gate_global_id),
                "requirementGlobalId": str(self.requirement_global_id),
                "evidenceReferenceGlobalId": str(self.evidence_reference_global_id),
            }
        )
        if self.dependency_key and self.dependency_key != expected_key:
            raise _field_problem(
                "baselineDependency.dependencyKey",
                _("The baseline dependency key does not match its exact scope."),
            )
        object.__setattr__(self, "dependency_key", expected_key)
        expected_hash = sha256_json(self.snapshot_payload())
        if self.snapshot_hash and self.snapshot_hash != expected_hash:
            raise _field_problem(
                "baselineDependency.snapshotHash",
                _("The baseline dependency snapshot hash does not match."),
            )
        object.__setattr__(self, "snapshot_hash", expected_hash)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": BASELINE_GATE_DEPENDENCY_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "baselineGlobalId": str(self.baseline_global_id),
            "baselineSnapshotHash": self.baseline_snapshot_hash,
            "inputDocumentGlobalId": str(self.input_document_global_id),
            "inputRevisionGlobalId": str(self.input_revision_global_id),
            "inputRevisionSnapshotHash": self.input_revision_snapshot_hash,
            "gateGlobalId": str(self.gate_global_id),
            "requirementGlobalId": str(self.requirement_global_id),
            "requirementKey": self.requirement_key,
            "evidenceReferenceGlobalId": str(self.evidence_reference_global_id),
            "registeredByUserId": self.registered_by_user_id,
            "registeredAt": _timestamp(self.registered_at),
            "requestId": self.request_id,
            "traceId": self.trace_id,
        }


@dataclass(frozen=True, slots=True)
class BaselineImpactEvent:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    dependency_global_id: UUID
    baseline_global_id: UUID
    baseline_snapshot_hash: str
    old_revision_global_id: UUID
    old_revision_snapshot_hash: str
    new_revision_global_id: UUID
    new_revision_snapshot_hash: str
    gate_global_id: UUID
    requirement_global_id: UUID
    evidence_reference_global_id: UUID
    initiated_by_user_id: str
    occurred_at: datetime
    request_id: str
    trace_id: str
    event_type: BaselineImpactEventType = BaselineImpactEventType.INVALIDATED
    impact_key: str = ""
    event_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "project_global_id",
            "dependency_global_id",
            "baseline_global_id",
            "old_revision_global_id",
            "new_revision_global_id",
            "gate_global_id",
            "requirement_global_id",
            "evidence_reference_global_id",
        ):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), f"baselineImpact.{fieldname}"),
            )
        object.__setattr__(
            self,
            "tenant_id",
            _text(
                self.tenant_id,
                "baselineImpact.tenantId",
                maximum=128,
                pattern=_TENANT_PATTERN,
            ),
        )
        if not isinstance(self.event_type, BaselineImpactEventType):
            raise _field_problem(
                "baselineImpact.eventType",
                _("Select a supported baseline impact event."),
            )
        if self.old_revision_global_id == self.new_revision_global_id:
            raise _field_problem(
                "baselineImpact.newRevisionGlobalId",
                _("The successor revision must differ from the prior input."),
            )
        for fieldname in (
            "baseline_snapshot_hash",
            "old_revision_snapshot_hash",
            "new_revision_snapshot_hash",
        ):
            object.__setattr__(
                self,
                fieldname,
                _hash(getattr(self, fieldname), f"baselineImpact.{fieldname}"),
            )
        object.__setattr__(
            self,
            "initiated_by_user_id",
            _text(
                self.initiated_by_user_id,
                "baselineImpact.initiatedByUserId",
                maximum=254,
                pattern=_ACTOR_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "occurred_at",
            _utc_datetime(self.occurred_at, "baselineImpact.occurredAt"),
        )
        object.__setattr__(
            self,
            "request_id",
            _text(self.request_id, "baselineImpact.requestId", maximum=128),
        )
        object.__setattr__(
            self,
            "trace_id",
            _text(self.trace_id, "baselineImpact.traceId", maximum=128),
        )
        expected_key = sha256_json(
            {
                "dependencyGlobalId": str(self.dependency_global_id),
                "newRevisionGlobalId": str(self.new_revision_global_id),
            }
        )
        if self.impact_key and self.impact_key != expected_key:
            raise _field_problem(
                "baselineImpact.impactKey",
                _("The baseline impact key does not match its exact lineage."),
            )
        object.__setattr__(self, "impact_key", expected_key)
        expected_hash = sha256_json(self.event_payload())
        if self.event_hash and self.event_hash != expected_hash:
            raise _field_problem(
                "baselineImpact.eventHash",
                _("The baseline impact event hash does not match its lineage."),
            )
        object.__setattr__(self, "event_hash", expected_hash)

    def event_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": BASELINE_IMPACT_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "eventType": self.event_type.value,
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "dependencyGlobalId": str(self.dependency_global_id),
            "baselineGlobalId": str(self.baseline_global_id),
            "baselineSnapshotHash": self.baseline_snapshot_hash,
            "oldRevisionGlobalId": str(self.old_revision_global_id),
            "oldRevisionSnapshotHash": self.old_revision_snapshot_hash,
            "newRevisionGlobalId": str(self.new_revision_global_id),
            "newRevisionSnapshotHash": self.new_revision_snapshot_hash,
            "gateGlobalId": str(self.gate_global_id),
            "requirementGlobalId": str(self.requirement_global_id),
            "evidenceReferenceGlobalId": str(self.evidence_reference_global_id),
            "initiatedByUserId": self.initiated_by_user_id,
            "occurredAt": _timestamp(self.occurred_at),
            "requestId": self.request_id,
            "traceId": self.trace_id,
        }


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


def _uuid(value: object, path: str) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise _field_problem(path, _("Enter a valid global ID."))
    return value


def _text(
    value: object,
    path: str,
    *,
    maximum: int,
    pattern: re.Pattern[str] | None = None,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _field_problem(path, _("Enter a value."))
    normalized = value.strip()
    if len(normalized) > maximum or (
        pattern is not None and pattern.fullmatch(normalized) is None
    ):
        raise _field_problem(path, _("Enter a valid value."))
    return normalized


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise _field_problem(path, _("Enter a valid lowercase SHA-256 hash."))
    return value


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _field_problem(path, _("Enter an integer greater than zero."))
    return value


def _nonnegative(value: object, path: str) -> int:
    if type(value) is not int or value < 0:
        raise _field_problem(path, _("Enter a non-negative integer."))
    return value


def _utc_datetime(value: object, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _field_problem(path, _("Enter a timezone-aware date and time."))
    return value.astimezone(UTC)


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _users(values: object, path: str) -> tuple[str, ...]:
    if (
        isinstance(values, (str, bytes))
        or not isinstance(values, Sequence)
        or not values
        or len(values) > 100
    ):
        raise _field_problem(path, _("Enter a bounded list of user IDs."))
    normalized = tuple(
        _text(value, f"{path}[{index}]", maximum=254, pattern=_ACTOR_PATTERN)
        for index, value in enumerate(values)
    )
    if len({value.casefold() for value in normalized}) != len(normalized):
        raise _field_problem(path, _("User IDs must be unique."))
    return normalized
