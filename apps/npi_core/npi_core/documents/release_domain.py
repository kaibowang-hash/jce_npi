from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping, Sequence
from uuid import UUID

from npi_core.foundation.errors import NpiProblem, RequestValidationFailed

try:
    from frappe import _
except ImportError:  # Keeps the domain independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


DOCUMENT_RELEASE_POLICY_SCHEMA_VERSION = 1
DOCUMENT_REVIEW_CYCLE_SCHEMA_VERSION = 1
DOCUMENT_CONFIRMATION_SCHEMA_VERSION = 1
DOCUMENT_LIFECYCLE_EVENT_SCHEMA_VERSION = 1
MAX_AUTHORITY_USERS = 64
MAX_REVIEWER_ASSIGNMENTS = 64
MAX_RELEASE_FILES = 64

_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_TENANT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_MIME_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9!#$&^_.+-]{0,126}/[a-z0-9][a-z0-9!#$&^_.+-]{0,126}$"
)


class DocumentReleasePolicyState(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class DocumentLifecycleState(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    RELEASED = "released"
    SUPERSEDED = "superseded"
    OBSOLETE = "obsolete"


class DocumentReviewDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class DocumentConfirmationType(StrEnum):
    REVIEW_APPROVE = "review_approve"
    REVIEW_REJECT = "review_reject"
    RELEASE = "release"
    SUPERSEDE = "supersede"
    OBSOLETE = "obsolete"


class DocumentLifecycleEventType(StrEnum):
    SUBMITTED = "submitted"
    RESUBMITTED = "resubmitted"
    REVIEW_REJECTED = "review_rejected"
    APPROVED = "approved"
    RELEASED = "released"
    SUPERSEDED = "superseded"
    OBSOLETE = "obsolete"


class DocumentReleasePolicyUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "DOCUMENT_RELEASE_POLICY_UNAVAILABLE",
            _("The selected document release policy version is unavailable."),
        )


class DocumentReviewStateConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "DOCUMENT_REVIEW_STATE_CONFLICT",
            _("The document review state changed before this command completed."),
        )


class DocumentReviewAssignmentUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            403,
            "DOCUMENT_REVIEW_ASSIGNMENT_UNAVAILABLE",
            _("The current user is not assigned to this document review action."),
        )


class DocumentReleaseAuthorityUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            403,
            "DOCUMENT_RELEASE_AUTHORITY_UNAVAILABLE",
            _("The current user is not assigned to this document release action."),
        )


class DocumentReleaseIntegrityBlocked(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "DOCUMENT_RELEASE_INTEGRITY_BLOCKED",
            _("The exact document file has not passed integrity and security checks."),
        )


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


def _uuid(value: object, path: str) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise _field_problem(path, _("Enter a valid global ID.")) from error
    if str(parsed) != str(value).casefold():
        raise _field_problem(path, _("Enter a canonical global ID."))
    return parsed


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


def _positive_integer(value: object, path: str) -> int:
    if type(value) is not int or value < 1 or value > 2_147_483_647:
        raise _field_problem(path, _("Enter a positive whole number."))
    return value


def _nonnegative_integer(value: object, path: str) -> int:
    if type(value) is not int or value < 0 or value > 2_147_483_647:
        raise _field_problem(path, _("Enter zero or a positive whole number."))
    return value


def _hash(value: object, path: str) -> str:
    return _text(value, path, maximum=64, pattern=_HASH_PATTERN)


def _utc_datetime(value: object, path: str) -> datetime:
    if not isinstance(value, datetime):
        raise _field_problem(path, _("Enter a valid date and time."))
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def immutable_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(value))


def _users(
    values: Sequence[object],
    path: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if (
        isinstance(values, (str, bytes))
        or not isinstance(values, Sequence)
        or len(values) > MAX_AUTHORITY_USERS
        or (not values and not allow_empty)
    ):
        raise _field_problem(path, _("Enter valid authority users."))
    normalized = tuple(
        _text(value, f"{path}[{index}]", maximum=254, pattern=_ACTOR_PATTERN)
        for index, value in enumerate(values)
    )
    if len({value.casefold() for value in normalized}) != len(normalized):
        raise _field_problem(path, _("Authority users must be unique."))
    return normalized


@dataclass(frozen=True, slots=True)
class DocumentReviewerAssignment:
    slot_key: str
    user_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "slot_key",
            _text(
                self.slot_key,
                "releasePolicy.reviewerAssignments.slotKey",
                maximum=64,
                pattern=_KEY_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "user_id",
            _text(
                self.user_id,
                "releasePolicy.reviewerAssignments.userId",
                maximum=254,
                pattern=_ACTOR_PATTERN,
            ),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {"slotKey": self.slot_key, "userId": self.user_id}


@dataclass(frozen=True, slots=True)
class DocumentReleasePolicyReference:
    global_id: UUID
    version: int
    snapshot_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "global_id",
            _uuid(self.global_id, "releasePolicyRef.globalId"),
        )
        object.__setattr__(
            self,
            "version",
            _positive_integer(self.version, "releasePolicyRef.version"),
        )
        object.__setattr__(
            self,
            "snapshot_hash",
            _hash(self.snapshot_hash, "releasePolicyRef.snapshotHash"),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "version": self.version,
            "snapshotHash": self.snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class DocumentReleasePolicyVersion:
    global_id: UUID
    policy_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    policy_key: str
    policy_version: int
    title: str
    state: DocumentReleasePolicyState
    submitter_user_ids: tuple[str, ...]
    reviewer_assignments: tuple[DocumentReviewerAssignment, ...]
    required_approval_count: int
    release_authority_user_ids: tuple[str, ...]
    supersede_authority_user_ids: tuple[str, ...]
    obsolete_authority_user_ids: tuple[str, ...]
    confirmation_method: str = "authenticated_session_confirmation"
    required_scan_state: str = "clean"
    require_live_private_identity: bool = True
    require_sha256_match: bool = True
    supersede_requires_released_successor: bool = True
    supersede_requires_later_revision: bool = True
    supersede_requires_successor_effective_date: bool = True
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "global_id",
            _uuid(self.global_id, "releasePolicy.globalId"),
        )
        object.__setattr__(
            self,
            "policy_global_id",
            _uuid(self.policy_global_id, "releasePolicy.policyGlobalId"),
        )
        object.__setattr__(
            self,
            "tenant_id",
            _text(
                self.tenant_id,
                "releasePolicy.tenantId",
                maximum=128,
                pattern=_TENANT_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "project_global_id",
            _uuid(self.project_global_id, "releasePolicy.projectGlobalId"),
        )
        object.__setattr__(
            self,
            "policy_key",
            _text(
                self.policy_key,
                "releasePolicy.key",
                maximum=64,
                pattern=_KEY_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "policy_version",
            _positive_integer(self.policy_version, "releasePolicy.version"),
        )
        object.__setattr__(
            self,
            "title",
            _text(self.title, "releasePolicy.title", maximum=140),
        )
        if not isinstance(self.state, DocumentReleasePolicyState):
            raise _field_problem(
                "releasePolicy.state",
                _("Select a supported value."),
            )
        submitters = _users(
            self.submitter_user_ids,
            "releasePolicy.submitterUserIds",
        )
        release_users = _users(
            self.release_authority_user_ids,
            "releasePolicy.releaseAuthorityUserIds",
        )
        supersede_users = _users(
            self.supersede_authority_user_ids,
            "releasePolicy.supersedeAuthorityUserIds",
        )
        obsolete_users = _users(
            self.obsolete_authority_user_ids,
            "releasePolicy.obsoleteAuthorityUserIds",
        )
        if (
            not self.reviewer_assignments
            or len(self.reviewer_assignments) > MAX_REVIEWER_ASSIGNMENTS
            or not all(
                isinstance(value, DocumentReviewerAssignment)
                for value in self.reviewer_assignments
            )
        ):
            raise _field_problem(
                "releasePolicy.reviewerAssignments",
                _("Enter valid reviewer assignments."),
            )
        slot_keys = [value.slot_key for value in self.reviewer_assignments]
        reviewer_users = [
            value.user_id.casefold() for value in self.reviewer_assignments
        ]
        if len(set(slot_keys)) != len(slot_keys) or len(set(reviewer_users)) != len(
            reviewer_users
        ):
            raise _field_problem(
                "releasePolicy.reviewerAssignments",
                _("Reviewer slots and users must be unique."),
            )
        approval_count = _positive_integer(
            self.required_approval_count,
            "releasePolicy.requiredApprovalCount",
        )
        if approval_count > len(self.reviewer_assignments):
            raise _field_problem(
                "releasePolicy.requiredApprovalCount",
                _("Required approvals cannot exceed reviewer assignments."),
            )
        if set(reviewer_users).intersection(
            value.casefold() for value in release_users
        ):
            raise _field_problem(
                "releasePolicy.releaseAuthorityUserIds",
                _("Reviewers and final release authorities must be separate."),
            )
        if self.confirmation_method != "authenticated_session_confirmation":
            raise _field_problem(
                "releasePolicy.confirmationMethod",
                _("Select the supported confirmation method."),
            )
        if self.required_scan_state != "clean":
            raise _field_problem(
                "releasePolicy.requiredScanState",
                _("Document release requires a clean scan state."),
            )
        safeguards = (
            self.require_live_private_identity,
            self.require_sha256_match,
            self.supersede_requires_released_successor,
            self.supersede_requires_later_revision,
            self.supersede_requires_successor_effective_date,
        )
        if any(value is not True for value in safeguards):
            raise _field_problem(
                "releasePolicy.safeguards",
                _("Document release safeguards cannot be disabled."),
            )
        object.__setattr__(self, "submitter_user_ids", submitters)
        object.__setattr__(self, "release_authority_user_ids", release_users)
        object.__setattr__(
            self,
            "supersede_authority_user_ids",
            supersede_users,
        )
        object.__setattr__(self, "obsolete_authority_user_ids", obsolete_users)
        object.__setattr__(self, "required_approval_count", approval_count)
        expected = sha256_json(self.snapshot_payload())
        if self.snapshot_hash and self.snapshot_hash != expected:
            raise _field_problem(
                "releasePolicy.snapshotHash",
                _("The release policy snapshot hash does not match its content."),
            )
        object.__setattr__(self, "snapshot_hash", expected)

    @property
    def reference(self) -> DocumentReleasePolicyReference:
        return DocumentReleasePolicyReference(
            self.policy_global_id,
            self.policy_version,
            self.snapshot_hash,
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": DOCUMENT_RELEASE_POLICY_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "policyGlobalId": str(self.policy_global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "key": self.policy_key,
            "version": self.policy_version,
            "title": self.title,
            "state": self.state.value,
            "submitterUserIds": sorted(self.submitter_user_ids, key=str.casefold),
            "reviewerAssignments": [
                value.canonical_dict()
                for value in sorted(
                    self.reviewer_assignments,
                    key=lambda assignment: assignment.slot_key,
                )
            ],
            "requiredApprovalCount": self.required_approval_count,
            "releaseAuthorityUserIds": sorted(
                self.release_authority_user_ids,
                key=str.casefold,
            ),
            "supersedeAuthorityUserIds": sorted(
                self.supersede_authority_user_ids,
                key=str.casefold,
            ),
            "obsoleteAuthorityUserIds": sorted(
                self.obsolete_authority_user_ids,
                key=str.casefold,
            ),
            "confirmationMethod": self.confirmation_method,
            "integrityRules": {
                "requiredScanState": self.required_scan_state,
                "requireLivePrivateIdentity": self.require_live_private_identity,
                "requireSha256Match": self.require_sha256_match,
            },
            "supersedeRules": {
                "requiresReleasedSuccessor": (
                    self.supersede_requires_released_successor
                ),
                "requiresLaterRevision": self.supersede_requires_later_revision,
                "requiresSuccessorEffectiveDate": (
                    self.supersede_requires_successor_effective_date
                ),
            },
        }

    def permits_submit(self, actor: str) -> bool:
        candidate = actor.casefold()
        return any(value.casefold() == candidate for value in self.submitter_user_ids)

    def reviewer_assignment(
        self,
        actor: str,
    ) -> DocumentReviewerAssignment | None:
        candidate = actor.casefold()
        return next(
            (
                value
                for value in self.reviewer_assignments
                if value.user_id.casefold() == candidate
            ),
            None,
        )

    def permits_release(self, actor: str) -> bool:
        candidate = actor.casefold()
        return any(
            value.casefold() == candidate
            for value in self.release_authority_user_ids
        )

    def permits_supersede(self, actor: str) -> bool:
        candidate = actor.casefold()
        return any(
            value.casefold() == candidate
            for value in self.supersede_authority_user_ids
        )

    def permits_obsolete(self, actor: str) -> bool:
        candidate = actor.casefold()
        return any(
            value.casefold() == candidate
            for value in self.obsolete_authority_user_ids
        )


@dataclass(frozen=True, slots=True)
class DocumentReleaseFileEvidence:
    association_global_id: UUID
    association_snapshot_hash: str
    file_revision_global_id: UUID
    file_document_global_id: UUID
    file_optimistic_version: int
    frappe_file_id: str
    frappe_content_hash: str
    file_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    scan_state: str
    scan_observed_at: datetime
    uploaded_by_user_id: str
    uploaded_at: datetime

    def __post_init__(self) -> None:
        for fieldname in (
            "association_global_id",
            "file_revision_global_id",
            "file_document_global_id",
        ):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), f"releaseFile.{fieldname}"),
            )
        object.__setattr__(
            self,
            "association_snapshot_hash",
            _hash(
                self.association_snapshot_hash,
                "releaseFile.associationSnapshotHash",
            ),
        )
        object.__setattr__(
            self,
            "file_optimistic_version",
            _positive_integer(
                self.file_optimistic_version,
                "releaseFile.fileOptimisticVersion",
            ),
        )
        object.__setattr__(
            self,
            "frappe_file_id",
            _text(self.frappe_file_id, "releaseFile.fileIdentity", maximum=140),
        )
        content_hash = _text(
            self.frappe_content_hash,
            "releaseFile.frappeContentHash",
            maximum=32,
        )
        if re.fullmatch(r"[a-f0-9]{32}", content_hash) is None:
            raise _field_problem(
                "releaseFile.frappeContentHash",
                _("Enter a valid file content hash."),
            )
        object.__setattr__(self, "frappe_content_hash", content_hash)
        object.__setattr__(
            self,
            "file_name",
            _text(self.file_name, "releaseFile.fileName", maximum=255),
        )
        object.__setattr__(
            self,
            "mime_type",
            _text(
                self.mime_type,
                "releaseFile.mimeType",
                maximum=255,
                pattern=_MIME_PATTERN,
            ).casefold(),
        )
        object.__setattr__(
            self,
            "size_bytes",
            _nonnegative_integer(self.size_bytes, "releaseFile.sizeBytes"),
        )
        object.__setattr__(
            self,
            "sha256",
            _hash(self.sha256, "releaseFile.sha256"),
        )
        if self.scan_state != "clean":
            raise _field_problem(
                "releaseFile.scanState",
                _("Only a clean file can enter a release review."),
            )
        object.__setattr__(
            self,
            "scan_observed_at",
            _utc_datetime(
                self.scan_observed_at,
                "releaseFile.scanObservedAt",
            ),
        )
        object.__setattr__(
            self,
            "uploaded_by_user_id",
            _text(
                self.uploaded_by_user_id,
                "releaseFile.uploadedByUserId",
                maximum=254,
                pattern=_ACTOR_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "uploaded_at",
            _utc_datetime(self.uploaded_at, "releaseFile.uploadedAt"),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "associationGlobalId": str(self.association_global_id),
            "associationSnapshotHash": self.association_snapshot_hash,
            "fileRevisionGlobalId": str(self.file_revision_global_id),
            "fileDocumentGlobalId": str(self.file_document_global_id),
            "fileOptimisticVersion": self.file_optimistic_version,
            "fileIdentity": self.frappe_file_id,
            "frappeContentHash": self.frappe_content_hash,
            "fileName": self.file_name,
            "mimeType": self.mime_type,
            "sizeBytes": self.size_bytes,
            "sha256": self.sha256,
            "scanState": self.scan_state,
            "scanObservedAt": _timestamp(self.scan_observed_at),
            "uploadedByUserId": self.uploaded_by_user_id,
            "uploadedAt": _timestamp(self.uploaded_at),
        }


@dataclass(frozen=True, slots=True)
class DocumentReviewEvidence:
    revision_global_id: UUID
    revision_snapshot_hash: str
    files: tuple[DocumentReleaseFileEvidence, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "revision_global_id",
            _uuid(self.revision_global_id, "reviewEvidence.revisionGlobalId"),
        )
        object.__setattr__(
            self,
            "revision_snapshot_hash",
            _hash(
                self.revision_snapshot_hash,
                "reviewEvidence.revisionSnapshotHash",
            ),
        )
        if (
            not self.files
            or len(self.files) > MAX_RELEASE_FILES
            or not all(
                isinstance(value, DocumentReleaseFileEvidence) for value in self.files
            )
        ):
            raise _field_problem(
                "reviewEvidence.files",
                _("Enter valid release file evidence."),
            )
        file_ids = [value.file_revision_global_id for value in self.files]
        association_ids = [value.association_global_id for value in self.files]
        if len(set(file_ids)) != len(file_ids) or len(set(association_ids)) != len(
            association_ids
        ):
            raise _field_problem(
                "reviewEvidence.files",
                _("Release file evidence must be unique."),
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "revisionGlobalId": str(self.revision_global_id),
            "revisionSnapshotHash": self.revision_snapshot_hash,
            "files": [
                value.canonical_dict()
                for value in sorted(
                    self.files,
                    key=lambda item: str(item.association_global_id),
                )
            ],
        }

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class DocumentRevisionLifecycle:
    revision_global_id: UUID
    state: DocumentLifecycleState
    version: int
    active_cycle_global_id: UUID | None = None
    approved_cycle_global_id: UUID | None = None
    approved_event_global_id: UUID | None = None
    release_event_global_id: UUID | None = None
    release_snapshot_hash: str | None = None
    replacement_revision_global_id: UUID | None = None
    replacement_effective_date: date | None = None
    terminal_event_global_id: UUID | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "revision_global_id",
            _uuid(self.revision_global_id, "lifecycle.revisionGlobalId"),
        )
        if not isinstance(self.state, DocumentLifecycleState):
            raise _field_problem(
                "lifecycle.state",
                _("Select a supported document lifecycle state."),
            )
        object.__setattr__(
            self,
            "version",
            _positive_integer(self.version, "lifecycle.version"),
        )
        for fieldname in (
            "active_cycle_global_id",
            "approved_cycle_global_id",
            "approved_event_global_id",
            "release_event_global_id",
            "replacement_revision_global_id",
            "terminal_event_global_id",
        ):
            value = getattr(self, fieldname)
            if value is not None:
                object.__setattr__(
                    self,
                    fieldname,
                    _uuid(value, f"lifecycle.{fieldname}"),
                )
        if self.release_snapshot_hash is not None:
            object.__setattr__(
                self,
                "release_snapshot_hash",
                _hash(
                    self.release_snapshot_hash,
                    "lifecycle.releaseSnapshotHash",
                ),
            )
        if self.replacement_effective_date is not None and type(
            self.replacement_effective_date
        ) is not date:
            raise _field_problem(
                "lifecycle.replacementEffectiveDate",
                _("Enter a valid date."),
            )
        self._validate_shape()

    def _validate_shape(self) -> None:
        if self.state is DocumentLifecycleState.IN_REVIEW:
            valid = (
                self.active_cycle_global_id is not None
                and self.release_event_global_id is None
                and self.terminal_event_global_id is None
            )
        elif self.state is DocumentLifecycleState.APPROVED:
            valid = (
                self.active_cycle_global_id is None
                and self.approved_cycle_global_id is not None
                and self.approved_event_global_id is not None
                and self.release_event_global_id is None
                and self.terminal_event_global_id is None
            )
        elif self.state is DocumentLifecycleState.RELEASED:
            valid = (
                self.active_cycle_global_id is None
                and self.approved_cycle_global_id is not None
                and self.approved_event_global_id is not None
                and self.release_event_global_id is not None
                and self.release_snapshot_hash is not None
                and self.terminal_event_global_id is None
                and self.replacement_revision_global_id is None
            )
        elif self.state is DocumentLifecycleState.SUPERSEDED:
            valid = (
                self.release_event_global_id is not None
                and self.release_snapshot_hash is not None
                and self.replacement_revision_global_id is not None
                and self.replacement_effective_date is not None
                and self.terminal_event_global_id is not None
            )
        elif self.state is DocumentLifecycleState.OBSOLETE:
            valid = (
                self.release_event_global_id is not None
                and self.release_snapshot_hash is not None
                and self.replacement_revision_global_id is None
                and self.replacement_effective_date is None
                and self.terminal_event_global_id is not None
            )
        else:
            valid = (
                self.active_cycle_global_id is None
                and self.approved_cycle_global_id is None
                and self.approved_event_global_id is None
                and self.release_event_global_id is None
                and self.release_snapshot_hash is None
                and self.replacement_revision_global_id is None
                and self.replacement_effective_date is None
                and self.terminal_event_global_id is None
            )
        if not valid:
            raise _field_problem(
                "lifecycle",
                _("Document lifecycle references do not match its state."),
            )


@dataclass(frozen=True, slots=True)
class DocumentReviewCycle:
    global_id: UUID
    revision_global_id: UUID
    cycle_number: int
    policy_ref: DocumentReleasePolicyReference
    evidence: DocumentReviewEvidence
    reviewer_assignments: tuple[DocumentReviewerAssignment, ...]
    required_approval_count: int
    prior_rejected_cycle_global_id: UUID | None
    submitted_by_user_id: str
    submitted_at: datetime
    request_id: str
    trace_id: str
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "global_id",
            _uuid(self.global_id, "reviewCycle.globalId"),
        )
        object.__setattr__(
            self,
            "revision_global_id",
            _uuid(self.revision_global_id, "reviewCycle.revisionGlobalId"),
        )
        object.__setattr__(
            self,
            "cycle_number",
            _positive_integer(self.cycle_number, "reviewCycle.cycleNumber"),
        )
        if not isinstance(self.policy_ref, DocumentReleasePolicyReference):
            raise _field_problem(
                "reviewCycle.releasePolicyRef",
                _("Enter a valid release policy reference."),
            )
        if not isinstance(self.evidence, DocumentReviewEvidence):
            raise _field_problem(
                "reviewCycle.evidence",
                _("Enter valid review evidence."),
            )
        if self.evidence.revision_global_id != self.revision_global_id:
            raise _field_problem(
                "reviewCycle.evidence",
                _("Review evidence must match the exact revision."),
            )
        if (
            not self.reviewer_assignments
            or not all(
                isinstance(value, DocumentReviewerAssignment)
                for value in self.reviewer_assignments
            )
        ):
            raise _field_problem(
                "reviewCycle.reviewerAssignments",
                _("Enter valid reviewer assignments."),
            )
        object.__setattr__(
            self,
            "required_approval_count",
            _positive_integer(
                self.required_approval_count,
                "reviewCycle.requiredApprovalCount",
            ),
        )
        if self.required_approval_count > len(self.reviewer_assignments):
            raise _field_problem(
                "reviewCycle.requiredApprovalCount",
                _("Required approvals cannot exceed reviewer assignments."),
            )
        if self.prior_rejected_cycle_global_id is not None:
            object.__setattr__(
                self,
                "prior_rejected_cycle_global_id",
                _uuid(
                    self.prior_rejected_cycle_global_id,
                    "reviewCycle.priorRejectedCycleGlobalId",
                ),
            )
        object.__setattr__(
            self,
            "submitted_by_user_id",
            _text(
                self.submitted_by_user_id,
                "reviewCycle.submittedByUserId",
                maximum=254,
                pattern=_ACTOR_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "submitted_at",
            _utc_datetime(self.submitted_at, "reviewCycle.submittedAt"),
        )
        object.__setattr__(
            self,
            "request_id",
            _text(self.request_id, "reviewCycle.requestId", maximum=128),
        )
        object.__setattr__(
            self,
            "trace_id",
            _text(self.trace_id, "reviewCycle.traceId", maximum=128),
        )
        expected = sha256_json(self.snapshot_payload())
        if self.snapshot_hash and self.snapshot_hash != expected:
            raise _field_problem(
                "reviewCycle.snapshotHash",
                _("The review-cycle snapshot hash does not match its content."),
            )
        object.__setattr__(self, "snapshot_hash", expected)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": DOCUMENT_REVIEW_CYCLE_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "revisionGlobalId": str(self.revision_global_id),
            "cycleNumber": self.cycle_number,
            "releasePolicyRef": self.policy_ref.canonical_dict(),
            "evidence": self.evidence.canonical_dict(),
            "reviewerAssignments": [
                value.canonical_dict()
                for value in sorted(
                    self.reviewer_assignments,
                    key=lambda assignment: assignment.slot_key,
                )
            ],
            "requiredApprovalCount": self.required_approval_count,
            "priorRejectedCycleGlobalId": (
                str(self.prior_rejected_cycle_global_id)
                if self.prior_rejected_cycle_global_id
                else None
            ),
            "submittedByUserId": self.submitted_by_user_id,
            "submittedAt": _timestamp(self.submitted_at),
            "requestId": self.request_id,
            "traceId": self.trace_id,
        }


@dataclass(frozen=True, slots=True)
class DocumentConfirmation:
    global_id: UUID
    confirmation_key: str
    confirmation_type: DocumentConfirmationType
    revision_global_id: UUID
    cycle_global_id: UUID
    policy_ref: DocumentReleasePolicyReference
    evidence_snapshot_hash: str
    actor_user_id: str
    authority_slot: str
    confirmation_method: str
    confirmation_intent: str
    confirmed: bool
    reason: str | None
    confirmed_at: datetime
    request_id: str
    trace_id: str
    evidence_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "global_id",
            _uuid(self.global_id, "confirmation.globalId"),
        )
        object.__setattr__(
            self,
            "confirmation_key",
            _hash(self.confirmation_key, "confirmation.key"),
        )
        if not isinstance(self.confirmation_type, DocumentConfirmationType):
            raise _field_problem(
                "confirmation.type",
                _("Select a supported confirmation type."),
            )
        object.__setattr__(
            self,
            "revision_global_id",
            _uuid(self.revision_global_id, "confirmation.revisionGlobalId"),
        )
        object.__setattr__(
            self,
            "cycle_global_id",
            _uuid(self.cycle_global_id, "confirmation.cycleGlobalId"),
        )
        if not isinstance(self.policy_ref, DocumentReleasePolicyReference):
            raise _field_problem(
                "confirmation.releasePolicyRef",
                _("Enter a valid release policy reference."),
            )
        object.__setattr__(
            self,
            "evidence_snapshot_hash",
            _hash(
                self.evidence_snapshot_hash,
                "confirmation.evidenceSnapshotHash",
            ),
        )
        object.__setattr__(
            self,
            "actor_user_id",
            _text(
                self.actor_user_id,
                "confirmation.actorUserId",
                maximum=254,
                pattern=_ACTOR_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "authority_slot",
            _text(
                self.authority_slot,
                "confirmation.authoritySlot",
                maximum=64,
                pattern=_KEY_PATTERN,
            ),
        )
        if self.confirmation_method != "authenticated_session_confirmation":
            raise _field_problem(
                "confirmation.method",
                _("Select the supported confirmation method."),
            )
        object.__setattr__(
            self,
            "confirmation_intent",
            _text(
                self.confirmation_intent,
                "confirmation.intent",
                maximum=64,
                pattern=_KEY_PATTERN,
            ),
        )
        if self.confirmed is not True:
            raise _field_problem(
                "confirmation.confirmed",
                _("Explicit confirmation is required."),
            )
        if self.reason is not None:
            object.__setattr__(
                self,
                "reason",
                _text(self.reason, "confirmation.reason", maximum=2000),
            )
        object.__setattr__(
            self,
            "confirmed_at",
            _utc_datetime(self.confirmed_at, "confirmation.confirmedAt"),
        )
        object.__setattr__(
            self,
            "request_id",
            _text(self.request_id, "confirmation.requestId", maximum=128),
        )
        object.__setattr__(
            self,
            "trace_id",
            _text(self.trace_id, "confirmation.traceId", maximum=128),
        )
        expected = sha256_json(self.evidence_payload())
        if self.evidence_hash and self.evidence_hash != expected:
            raise _field_problem(
                "confirmation.evidenceHash",
                _("The confirmation evidence hash does not match its content."),
            )
        object.__setattr__(self, "evidence_hash", expected)

    def evidence_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": DOCUMENT_CONFIRMATION_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "confirmationKey": self.confirmation_key,
            "confirmationType": self.confirmation_type.value,
            "revisionGlobalId": str(self.revision_global_id),
            "cycleGlobalId": str(self.cycle_global_id),
            "releasePolicyRef": self.policy_ref.canonical_dict(),
            "evidenceSnapshotHash": self.evidence_snapshot_hash,
            "actorUserId": self.actor_user_id,
            "authoritySlot": self.authority_slot,
            "confirmationMethod": self.confirmation_method,
            "confirmationIntent": self.confirmation_intent,
            "confirmed": True,
            "reason": self.reason,
            "confirmedAt": _timestamp(self.confirmed_at),
            "requestId": self.request_id,
            "traceId": self.trace_id,
        }


@dataclass(frozen=True, slots=True)
class DocumentLifecycleEvent:
    global_id: UUID
    revision_global_id: UUID
    event_type: DocumentLifecycleEventType
    from_state: DocumentLifecycleState
    to_state: DocumentLifecycleState
    from_version: int
    to_version: int
    cycle_global_id: UUID
    policy_ref: DocumentReleasePolicyReference
    evidence_snapshot_hash: str
    confirmation_hashes: tuple[str, ...]
    replacement_revision_global_id: UUID | None
    replacement_effective_date: date | None
    actor_user_id: str
    occurred_at: datetime
    request_id: str
    trace_id: str
    event_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "global_id",
            _uuid(self.global_id, "lifecycleEvent.globalId"),
        )
        object.__setattr__(
            self,
            "revision_global_id",
            _uuid(self.revision_global_id, "lifecycleEvent.revisionGlobalId"),
        )
        if not isinstance(self.event_type, DocumentLifecycleEventType):
            raise _field_problem(
                "lifecycleEvent.type",
                _("Select a supported lifecycle event."),
            )
        if not isinstance(self.from_state, DocumentLifecycleState) or not isinstance(
            self.to_state, DocumentLifecycleState
        ):
            raise _field_problem(
                "lifecycleEvent.state",
                _("Select supported lifecycle states."),
            )
        object.__setattr__(
            self,
            "from_version",
            _nonnegative_integer(self.from_version, "lifecycleEvent.fromVersion"),
        )
        object.__setattr__(
            self,
            "to_version",
            _positive_integer(self.to_version, "lifecycleEvent.toVersion"),
        )
        if self.to_version != self.from_version + 1:
            raise _field_problem(
                "lifecycleEvent.toVersion",
                _("Lifecycle event versions must advance exactly once."),
            )
        object.__setattr__(
            self,
            "cycle_global_id",
            _uuid(self.cycle_global_id, "lifecycleEvent.cycleGlobalId"),
        )
        if not isinstance(self.policy_ref, DocumentReleasePolicyReference):
            raise _field_problem(
                "lifecycleEvent.releasePolicyRef",
                _("Enter a valid release policy reference."),
            )
        object.__setattr__(
            self,
            "evidence_snapshot_hash",
            _hash(
                self.evidence_snapshot_hash,
                "lifecycleEvent.evidenceSnapshotHash",
            ),
        )
        if isinstance(self.confirmation_hashes, (str, bytes)) or not isinstance(
            self.confirmation_hashes, Sequence
        ):
            raise _field_problem(
                "lifecycleEvent.confirmationHashes",
                _("Enter valid confirmation hashes."),
            )
        hashes = tuple(
            _hash(value, f"lifecycleEvent.confirmationHashes[{index}]")
            for index, value in enumerate(self.confirmation_hashes)
        )
        if len(set(hashes)) != len(hashes):
            raise _field_problem(
                "lifecycleEvent.confirmationHashes",
                _("Confirmation hashes must be unique."),
            )
        object.__setattr__(self, "confirmation_hashes", hashes)
        if self.replacement_revision_global_id is not None:
            object.__setattr__(
                self,
                "replacement_revision_global_id",
                _uuid(
                    self.replacement_revision_global_id,
                    "lifecycleEvent.replacementRevisionGlobalId",
                ),
            )
        if self.replacement_effective_date is not None and type(
            self.replacement_effective_date
        ) is not date:
            raise _field_problem(
                "lifecycleEvent.replacementEffectiveDate",
                _("Enter a valid date."),
            )
        object.__setattr__(
            self,
            "actor_user_id",
            _text(
                self.actor_user_id,
                "lifecycleEvent.actorUserId",
                maximum=254,
                pattern=_ACTOR_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "occurred_at",
            _utc_datetime(self.occurred_at, "lifecycleEvent.occurredAt"),
        )
        object.__setattr__(
            self,
            "request_id",
            _text(self.request_id, "lifecycleEvent.requestId", maximum=128),
        )
        object.__setattr__(
            self,
            "trace_id",
            _text(self.trace_id, "lifecycleEvent.traceId", maximum=128),
        )
        self._validate_transition()
        expected = sha256_json(self.event_payload())
        if self.event_hash and self.event_hash != expected:
            raise _field_problem(
                "lifecycleEvent.eventHash",
                _("The lifecycle event hash does not match its content."),
            )
        object.__setattr__(self, "event_hash", expected)

    def _validate_transition(self) -> None:
        transitions = {
            DocumentLifecycleEventType.SUBMITTED: (
                DocumentLifecycleState.DRAFT,
                DocumentLifecycleState.IN_REVIEW,
            ),
            DocumentLifecycleEventType.RESUBMITTED: (
                DocumentLifecycleState.DRAFT,
                DocumentLifecycleState.IN_REVIEW,
            ),
            DocumentLifecycleEventType.REVIEW_REJECTED: (
                DocumentLifecycleState.IN_REVIEW,
                DocumentLifecycleState.DRAFT,
            ),
            DocumentLifecycleEventType.APPROVED: (
                DocumentLifecycleState.IN_REVIEW,
                DocumentLifecycleState.APPROVED,
            ),
            DocumentLifecycleEventType.RELEASED: (
                DocumentLifecycleState.APPROVED,
                DocumentLifecycleState.RELEASED,
            ),
            DocumentLifecycleEventType.SUPERSEDED: (
                DocumentLifecycleState.RELEASED,
                DocumentLifecycleState.SUPERSEDED,
            ),
            DocumentLifecycleEventType.OBSOLETE: (
                DocumentLifecycleState.RELEASED,
                DocumentLifecycleState.OBSOLETE,
            ),
        }
        if transitions[self.event_type] != (self.from_state, self.to_state):
            raise _field_problem(
                "lifecycleEvent.state",
                _("The lifecycle event does not match the allowed transition."),
            )
        replacement_required = (
            self.event_type is DocumentLifecycleEventType.SUPERSEDED
        )
        if replacement_required != (self.replacement_revision_global_id is not None):
            raise _field_problem(
                "lifecycleEvent.replacementRevisionGlobalId",
                _("Supersede requires one exact replacement revision."),
            )
        if replacement_required != (self.replacement_effective_date is not None):
            raise _field_problem(
                "lifecycleEvent.replacementEffectiveDate",
                _("Supersede requires the replacement effective date."),
            )

    def event_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": DOCUMENT_LIFECYCLE_EVENT_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "revisionGlobalId": str(self.revision_global_id),
            "eventType": self.event_type.value,
            "fromState": self.from_state.value,
            "toState": self.to_state.value,
            "fromVersion": self.from_version,
            "toVersion": self.to_version,
            "cycleGlobalId": str(self.cycle_global_id),
            "releasePolicyRef": self.policy_ref.canonical_dict(),
            "evidenceSnapshotHash": self.evidence_snapshot_hash,
            "confirmationHashes": sorted(self.confirmation_hashes),
            "replacementRevisionGlobalId": (
                str(self.replacement_revision_global_id)
                if self.replacement_revision_global_id
                else None
            ),
            "replacementEffectiveDate": (
                self.replacement_effective_date.isoformat()
                if self.replacement_effective_date
                else None
            ),
            "actorUserId": self.actor_user_id,
            "occurredAt": _timestamp(self.occurred_at),
            "requestId": self.request_id,
            "traceId": self.trace_id,
        }


@dataclass(frozen=True, slots=True)
class ReviewSubmission:
    cycle: DocumentReviewCycle
    event: DocumentLifecycleEvent
    lifecycle: DocumentRevisionLifecycle


def submit_document_review(
    *,
    lifecycle: DocumentRevisionLifecycle | None,
    policy: DocumentReleasePolicyVersion,
    evidence: DocumentReviewEvidence,
    cycle_global_id: UUID,
    event_global_id: UUID,
    cycle_number: int,
    prior_rejected_cycle_global_id: UUID | None,
    actor: str,
    now: datetime,
    request_id: str,
    trace_id: str,
) -> ReviewSubmission:
    if policy.state is not DocumentReleasePolicyState.PUBLISHED:
        raise DocumentReleasePolicyUnavailable()
    if policy.project_global_id is None or not policy.permits_submit(actor):
        raise DocumentReviewAssignmentUnavailable()
    if lifecycle is not None and lifecycle.state is not DocumentLifecycleState.DRAFT:
        raise DocumentReviewStateConflict()
    from_version = lifecycle.version if lifecycle is not None else 0
    is_resubmission = prior_rejected_cycle_global_id is not None
    if cycle_number == 1 and is_resubmission:
        raise DocumentReviewStateConflict()
    if cycle_number > 1 and not is_resubmission:
        raise DocumentReviewStateConflict()
    cycle = DocumentReviewCycle(
        global_id=cycle_global_id,
        revision_global_id=evidence.revision_global_id,
        cycle_number=cycle_number,
        policy_ref=policy.reference,
        evidence=evidence,
        reviewer_assignments=policy.reviewer_assignments,
        required_approval_count=policy.required_approval_count,
        prior_rejected_cycle_global_id=prior_rejected_cycle_global_id,
        submitted_by_user_id=actor,
        submitted_at=now,
        request_id=request_id,
        trace_id=trace_id,
    )
    event = DocumentLifecycleEvent(
        global_id=event_global_id,
        revision_global_id=evidence.revision_global_id,
        event_type=(
            DocumentLifecycleEventType.RESUBMITTED
            if is_resubmission
            else DocumentLifecycleEventType.SUBMITTED
        ),
        from_state=DocumentLifecycleState.DRAFT,
        to_state=DocumentLifecycleState.IN_REVIEW,
        from_version=from_version,
        to_version=from_version + 1,
        cycle_global_id=cycle.global_id,
        policy_ref=policy.reference,
        evidence_snapshot_hash=evidence.snapshot_hash,
        confirmation_hashes=(),
        replacement_revision_global_id=None,
        replacement_effective_date=None,
        actor_user_id=actor,
        occurred_at=now,
        request_id=request_id,
        trace_id=trace_id,
    )
    updated = DocumentRevisionLifecycle(
        revision_global_id=evidence.revision_global_id,
        state=DocumentLifecycleState.IN_REVIEW,
        version=event.to_version,
        active_cycle_global_id=cycle.global_id,
    )
    return ReviewSubmission(cycle, event, updated)


def advance_document_lifecycle(
    lifecycle: DocumentRevisionLifecycle,
    event: DocumentLifecycleEvent,
    *,
    approved_cycle_global_id: UUID | None = None,
    approved_event_global_id: UUID | None = None,
    release_event_global_id: UUID | None = None,
    release_snapshot_hash: str | None = None,
) -> DocumentRevisionLifecycle:
    if (
        event.revision_global_id != lifecycle.revision_global_id
        or event.from_state is not lifecycle.state
        or event.from_version != lifecycle.version
    ):
        raise DocumentReviewStateConflict()
    if event.to_state is DocumentLifecycleState.DRAFT:
        return DocumentRevisionLifecycle(
            revision_global_id=lifecycle.revision_global_id,
            state=DocumentLifecycleState.DRAFT,
            version=event.to_version,
        )
    if event.to_state is DocumentLifecycleState.APPROVED:
        return DocumentRevisionLifecycle(
            revision_global_id=lifecycle.revision_global_id,
            state=DocumentLifecycleState.APPROVED,
            version=event.to_version,
            approved_cycle_global_id=approved_cycle_global_id or event.cycle_global_id,
            approved_event_global_id=approved_event_global_id or event.global_id,
        )
    if event.to_state is DocumentLifecycleState.RELEASED:
        return DocumentRevisionLifecycle(
            revision_global_id=lifecycle.revision_global_id,
            state=DocumentLifecycleState.RELEASED,
            version=event.to_version,
            approved_cycle_global_id=lifecycle.approved_cycle_global_id,
            approved_event_global_id=lifecycle.approved_event_global_id,
            release_event_global_id=release_event_global_id or event.global_id,
            release_snapshot_hash=release_snapshot_hash,
        )
    if event.to_state is DocumentLifecycleState.SUPERSEDED:
        return replace(
            lifecycle,
            state=DocumentLifecycleState.SUPERSEDED,
            version=event.to_version,
            replacement_revision_global_id=event.replacement_revision_global_id,
            replacement_effective_date=event.replacement_effective_date,
            terminal_event_global_id=event.global_id,
        )
    if event.to_state is DocumentLifecycleState.OBSOLETE:
        return replace(
            lifecycle,
            state=DocumentLifecycleState.OBSOLETE,
            version=event.to_version,
            terminal_event_global_id=event.global_id,
        )
    raise DocumentReviewStateConflict()
