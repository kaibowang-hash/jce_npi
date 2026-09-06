from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
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


MAX_DOCUMENT_TYPES = 64
MAX_CONFIDENTIALITY_KEYS = 32
MAX_OBJECT_LINKS = 64
MAX_FILE_BYTES = 67_108_864
MAX_LOCK_LEASE_MINUTES = 1_440
DOCUMENT_POLICY_SCHEMA_VERSION = 1
DOCUMENT_REVISION_SCHEMA_VERSION = 1

_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_PREFIX_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9-]{0,15}$")
_TENANT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_MIME_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9!#$&^_.+-]{0,126}/[a-z0-9][a-z0-9!#$&^_.+-]{0,126}$"
)
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_MD5_PATTERN = re.compile(r"^[a-f0-9]{32}$")
_FILE_NAME_CONTROL_PATTERN = re.compile(r"[\x00-\x1f\x7f]")


class DocumentPolicyState(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class DocumentRevisionState(StrEnum):
    DRAFT = "draft"


class FileScanState(StrEnum):
    PENDING = "pending"
    CLEAN = "clean"
    INFECTED = "infected"
    FAILED = "failed"


class DocumentRelationshipKind(StrEnum):
    PROJECT = "project"
    PROJECT_REFERENCE = "project_reference"
    GATE = "gate"
    WBS_ITEM = "wbs_item"
    DOMAIN_WORK_ITEM = "domain_work_item"


class DocumentFileRole(StrEnum):
    PRIMARY = "primary"
    SOURCE = "source"
    DERIVATIVE = "derivative"


class DocumentLockState(StrEnum):
    ACTIVE = "active"
    RELEASED = "released"
    RECOVERED = "recovered"
    EXPIRED = "expired"


class CapabilityState(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    BLOCKED = "blocked"


class PreviewMode(StrEnum):
    NATIVE_PDF = "native_pdf"
    NATIVE_IMAGE = "native_image"
    NONE = "none"


class ConnectorState(StrEnum):
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class DocumentUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "DOCUMENT_UNAVAILABLE",
            _("The requested document is unavailable."),
        )


class DocumentPolicyUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "DOCUMENT_POLICY_UNAVAILABLE",
            _("The selected document policy version is unavailable."),
        )


class DocumentNumberConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "DOCUMENT_NUMBER_CONFLICT",
            _("The generated document number is already in use."),
        )


class DocumentVersionConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "DOCUMENT_VERSION_CONFLICT",
            _("The document was changed by another user."),
        )


class DocumentLockConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "DOCUMENT_LOCK_CONFLICT",
            _("The document edit lock has changed or is held by another user."),
        )


class DocumentFileUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            422,
            "DOCUMENT_FILE_UNAVAILABLE",
            _("The exact document file is unavailable."),
        )


class DocumentIdempotencyConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "IDEMPOTENCY_KEY_CONFLICT",
            _("The idempotency key was already used for a different request."),
        )


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


def _require_text(
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


def _require_positive_integer(value: object, path: str, maximum: int) -> int:
    if type(value) is not int or value < 1 or value > maximum:
        raise _field_problem(path, _("Enter a positive whole number."))
    return value


def _require_nonnegative_integer(value: object, path: str) -> int:
    if type(value) is not int or value < 0:
        raise _field_problem(path, _("Enter zero or a positive whole number."))
    return value


def _require_uuid(value: object, path: str) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise _field_problem(path, _("Enter a valid global ID.")) from error


def _require_hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH_PATTERN.fullmatch(value) is None:
        raise _field_problem(path, _("Enter a valid SHA-256 value."))
    return value


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


@dataclass(frozen=True, slots=True)
class DocumentTypeRule:
    key: str
    prefix: str
    title_source: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "key",
            _require_text(
                self.key,
                "documentTypes.key",
                maximum=64,
                pattern=_KEY_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "prefix",
            _require_text(
                self.prefix,
                "documentTypes.prefix",
                maximum=16,
                pattern=_PREFIX_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "title_source",
            _require_text(
                self.title_source,
                "documentTypes.titleSource",
                maximum=140,
            ),
        )

    def canonical_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "prefix": self.prefix,
            "titleSource": self.title_source,
        }


@dataclass(frozen=True, slots=True)
class DocumentPolicyReference:
    global_id: UUID
    version: int
    snapshot_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "global_id",
            _require_uuid(self.global_id, "documentPolicyRef.globalId"),
        )
        object.__setattr__(
            self,
            "version",
            _require_positive_integer(
                self.version,
                "documentPolicyRef.version",
                2_147_483_647,
            ),
        )
        object.__setattr__(
            self,
            "snapshot_hash",
            _require_hash(
                self.snapshot_hash,
                "documentPolicyRef.snapshotHash",
            ),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "version": self.version,
            "snapshotHash": self.snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class DocumentPolicyVersion:
    global_id: UUID
    policy_global_id: UUID
    policy_key: str
    policy_version: int
    title: str
    state: DocumentPolicyState
    document_types: tuple[DocumentTypeRule, ...]
    confidentiality_keys: tuple[str, ...]
    allowed_mime_types: tuple[str, ...]
    preview_mime_types: tuple[str, ...]
    maximum_file_bytes: int
    lock_lease_minutes: int
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "global_id",
            _require_uuid(self.global_id, "documentPolicy.globalId"),
        )
        object.__setattr__(
            self,
            "policy_global_id",
            _require_uuid(self.policy_global_id, "documentPolicy.policyGlobalId"),
        )
        object.__setattr__(
            self,
            "policy_key",
            _require_text(
                self.policy_key,
                "documentPolicy.key",
                maximum=64,
                pattern=_KEY_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "policy_version",
            _require_positive_integer(
                self.policy_version,
                "documentPolicy.version",
                2_147_483_647,
            ),
        )
        object.__setattr__(
            self,
            "title",
            _require_text(self.title, "documentPolicy.title", maximum=140),
        )
        if not isinstance(self.state, DocumentPolicyState):
            raise _field_problem(
                "documentPolicy.state",
                _("Select a supported value."),
            )
        if (
            not self.document_types
            or len(self.document_types) > MAX_DOCUMENT_TYPES
            or not all(
                isinstance(value, DocumentTypeRule) for value in self.document_types
            )
        ):
            raise _field_problem(
                "documentPolicy.documentTypes",
                _("Enter valid document type rules."),
            )
        if len({value.key for value in self.document_types}) != len(
            self.document_types
        ) or len({value.prefix for value in self.document_types}) != len(
            self.document_types
        ):
            raise _field_problem(
                "documentPolicy.documentTypes",
                _("Document type keys and prefixes must be unique."),
            )
        confidentiality_keys = _normalized_keys(
            self.confidentiality_keys,
            "documentPolicy.confidentialityKeys",
            maximum=MAX_CONFIDENTIALITY_KEYS,
        )
        allowed_mime_types = _normalized_mime_types(
            self.allowed_mime_types,
            "documentPolicy.allowedMimeTypes",
        )
        preview_mime_types = _normalized_mime_types(
            self.preview_mime_types,
            "documentPolicy.previewMimeTypes",
            allow_empty=True,
        )
        if not set(preview_mime_types).issubset(allowed_mime_types):
            raise _field_problem(
                "documentPolicy.previewMimeTypes",
                _("Preview formats must also be allowed file formats."),
            )
        unsupported_preview = set(preview_mime_types) - {
            "application/pdf",
            "image/gif",
            "image/jpeg",
            "image/png",
            "image/webp",
        }
        if unsupported_preview:
            raise _field_problem(
                "documentPolicy.previewMimeTypes",
                _("Select browser-native PDF or image preview formats."),
            )
        object.__setattr__(self, "confidentiality_keys", confidentiality_keys)
        object.__setattr__(self, "allowed_mime_types", allowed_mime_types)
        object.__setattr__(self, "preview_mime_types", preview_mime_types)
        object.__setattr__(
            self,
            "maximum_file_bytes",
            _require_positive_integer(
                self.maximum_file_bytes,
                "documentPolicy.maximumFileBytes",
                MAX_FILE_BYTES,
            ),
        )
        object.__setattr__(
            self,
            "lock_lease_minutes",
            _require_positive_integer(
                self.lock_lease_minutes,
                "documentPolicy.lockLeaseMinutes",
                MAX_LOCK_LEASE_MINUTES,
            ),
        )
        expected_hash = sha256_json(self.snapshot_payload())
        if self.snapshot_hash and self.snapshot_hash != expected_hash:
            raise _field_problem(
                "documentPolicy.snapshotHash",
                _("The document policy snapshot hash does not match its content."),
            )
        object.__setattr__(self, "snapshot_hash", expected_hash)

    @property
    def reference(self) -> DocumentPolicyReference:
        return DocumentPolicyReference(
            self.policy_global_id,
            self.policy_version,
            self.snapshot_hash,
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": DOCUMENT_POLICY_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "policyGlobalId": str(self.policy_global_id),
            "key": self.policy_key,
            "version": self.policy_version,
            "title": self.title,
            "state": self.state.value,
            "documentTypes": [
                value.canonical_dict()
                for value in sorted(self.document_types, key=lambda rule: rule.key)
            ],
            "confidentialityKeys": sorted(self.confidentiality_keys),
            "allowedMimeTypes": sorted(self.allowed_mime_types),
            "previewMimeTypes": sorted(self.preview_mime_types),
            "maximumFileBytes": self.maximum_file_bytes,
            "lockLeaseMinutes": self.lock_lease_minutes,
        }

    def require_published(self) -> None:
        if self.state is not DocumentPolicyState.PUBLISHED:
            raise DocumentPolicyUnavailable()

    def document_type(self, key: object) -> DocumentTypeRule:
        normalized = _require_text(
            key,
            "documentTypeKey",
            maximum=64,
            pattern=_KEY_PATTERN,
        )
        matches = [value for value in self.document_types if value.key == normalized]
        if len(matches) != 1:
            raise _field_problem(
                "documentTypeKey",
                _("Select a document type from the exact policy version."),
            )
        return matches[0]

    def require_confidentiality(self, key: object) -> str:
        normalized = _require_text(
            key,
            "confidentialityKey",
            maximum=64,
            pattern=_KEY_PATTERN,
        )
        if normalized not in self.confidentiality_keys:
            raise _field_problem(
                "confidentialityKey",
                _("Select a confidentiality level from the exact policy version."),
            )
        return normalized

    def document_number(self, document_type_key: object, document_id: UUID) -> str:
        rule = self.document_type(document_type_key)
        identity = _require_uuid(document_id, "documentId")
        return f"{rule.prefix}-{identity.hex[:12].upper()}"


def _normalized_keys(
    values: Sequence[object],
    path: str,
    *,
    maximum: int,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise _field_problem(path, _("Enter a valid list."))
    normalized = tuple(
        _require_text(value, path, maximum=64, pattern=_KEY_PATTERN) for value in values
    )
    if (
        not normalized
        or len(normalized) > maximum
        or len(set(normalized)) != len(normalized)
    ):
        raise _field_problem(path, _("Enter unique supported values."))
    return normalized


def _normalized_mime_types(
    values: Sequence[object],
    path: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise _field_problem(path, _("Enter a valid list."))
    normalized = tuple(
        _require_text(value, path, maximum=255, pattern=_MIME_PATTERN).casefold()
        for value in values
    )
    if (
        (not normalized and not allow_empty)
        or len(normalized) > 64
        or len(set(normalized)) != len(normalized)
    ):
        raise _field_problem(path, _("Enter unique supported file formats."))
    return normalized


@dataclass(frozen=True, slots=True)
class ControlledDocument:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    policy_ref: DocumentPolicyReference
    document_number: str
    document_number_key: str
    document_type_key: str
    title: str
    confidentiality_key: str
    version: int
    current_revision_id: UUID | None = None
    current_revision_major: int | None = None
    current_revision_minor: int | None = None
    current_revision_hash: str | None = None
    current_lock_id: UUID | None = None
    current_lock_version: int | None = None
    current_lock_holder: str | None = None
    current_lock_expires_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "global_id",
            _require_uuid(self.global_id, "documentId"),
        )
        object.__setattr__(
            self,
            "tenant_id",
            _require_text(
                self.tenant_id,
                "tenantId",
                maximum=128,
                pattern=_TENANT_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "project_global_id",
            _require_uuid(self.project_global_id, "projectId"),
        )
        if not isinstance(self.policy_ref, DocumentPolicyReference):
            raise _field_problem(
                "documentPolicyRef", _("Enter a valid policy reference.")
            )
        object.__setattr__(
            self,
            "document_number",
            _require_text(
                self.document_number,
                "documentNumber",
                maximum=64,
            ),
        )
        object.__setattr__(
            self,
            "document_number_key",
            _require_hash(self.document_number_key, "documentNumberKey"),
        )
        object.__setattr__(
            self,
            "document_type_key",
            _require_text(
                self.document_type_key,
                "documentTypeKey",
                maximum=64,
                pattern=_KEY_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "title",
            _require_text(self.title, "title", maximum=280),
        )
        object.__setattr__(
            self,
            "confidentiality_key",
            _require_text(
                self.confidentiality_key,
                "confidentialityKey",
                maximum=64,
                pattern=_KEY_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "version",
            _require_positive_integer(self.version, "documentVersion", 2_147_483_647),
        )
        revision_values = (
            self.current_revision_id,
            self.current_revision_major,
            self.current_revision_minor,
            self.current_revision_hash,
        )
        if any(value is not None for value in revision_values):
            if not all(value is not None for value in revision_values):
                raise _field_problem(
                    "currentRevision",
                    _("The current revision identity is incomplete."),
                )
            object.__setattr__(
                self,
                "current_revision_id",
                _require_uuid(self.current_revision_id, "currentRevision.globalId"),
            )
            object.__setattr__(
                self,
                "current_revision_major",
                _require_nonnegative_integer(
                    self.current_revision_major,
                    "currentRevision.major",
                ),
            )
            object.__setattr__(
                self,
                "current_revision_minor",
                _require_nonnegative_integer(
                    self.current_revision_minor,
                    "currentRevision.minor",
                ),
            )
            object.__setattr__(
                self,
                "current_revision_hash",
                _require_hash(
                    self.current_revision_hash,
                    "currentRevision.snapshotHash",
                ),
            )
        lock_values = (
            self.current_lock_id,
            self.current_lock_version,
            self.current_lock_holder,
            self.current_lock_expires_at,
        )
        if any(value is not None for value in lock_values):
            if not all(value is not None for value in lock_values):
                raise _field_problem(
                    "currentLock",
                    _("The current edit lock identity is incomplete."),
                )
            object.__setattr__(
                self,
                "current_lock_id",
                _require_uuid(self.current_lock_id, "currentLock.globalId"),
            )
            object.__setattr__(
                self,
                "current_lock_version",
                _require_positive_integer(
                    self.current_lock_version,
                    "currentLock.version",
                    2_147_483_647,
                ),
            )
            object.__setattr__(
                self,
                "current_lock_holder",
                _require_text(
                    self.current_lock_holder,
                    "currentLock.holder",
                    maximum=254,
                    pattern=_ACTOR_PATTERN,
                ),
            )
            object.__setattr__(
                self,
                "current_lock_expires_at",
                _utc_datetime(
                    self.current_lock_expires_at,
                    "currentLock.expiresAt",
                ),
            )


def create_controlled_document(
    *,
    document_id: UUID,
    tenant_id: object,
    project_id: UUID,
    policy: DocumentPolicyVersion,
    document_type_key: object,
    title: object,
    confidentiality_key: object,
) -> ControlledDocument:
    if not isinstance(policy, DocumentPolicyVersion):
        raise DocumentPolicyUnavailable()
    policy.require_published()
    tenant = _require_text(
        tenant_id,
        "tenantId",
        maximum=128,
        pattern=_TENANT_PATTERN,
    )
    project = _require_uuid(project_id, "projectId")
    global_id = _require_uuid(document_id, "documentId")
    document_type = policy.document_type(document_type_key)
    confidentiality = policy.require_confidentiality(confidentiality_key)
    number = policy.document_number(document_type.key, global_id)
    number_key = sha256_json(
        {
            "tenantId": tenant,
            "policyGlobalId": str(policy.policy_global_id),
            "documentTypeKey": document_type.key,
            "documentNumber": number.casefold(),
        }
    )
    return ControlledDocument(
        global_id=global_id,
        tenant_id=tenant,
        project_global_id=project,
        policy_ref=policy.reference,
        document_number=number,
        document_number_key=number_key,
        document_type_key=document_type.key,
        title=_require_text(title, "title", maximum=280),
        confidentiality_key=confidentiality,
        version=1,
    )


def _utc_datetime(value: object, path: str) -> datetime:
    if not isinstance(value, datetime):
        raise _field_problem(path, _("Enter a valid date and time."))
    if value.tzinfo is None:
        raise _field_problem(path, _("Enter a date and time with a time zone."))
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class DocumentEditLock:
    global_id: UUID
    document_global_id: UUID
    version: int
    holder_user_id: str
    acquired_at: datetime
    expires_at: datetime
    state: DocumentLockState
    closed_at: datetime | None = None
    closed_by: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "global_id",
            _require_uuid(self.global_id, "lockId"),
        )
        object.__setattr__(
            self,
            "document_global_id",
            _require_uuid(self.document_global_id, "documentId"),
        )
        object.__setattr__(
            self,
            "version",
            _require_positive_integer(self.version, "lockVersion", 2_147_483_647),
        )
        object.__setattr__(
            self,
            "holder_user_id",
            _require_text(
                self.holder_user_id,
                "lockHolder",
                maximum=254,
                pattern=_ACTOR_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "acquired_at",
            _utc_datetime(self.acquired_at, "lockAcquiredAt"),
        )
        object.__setattr__(
            self,
            "expires_at",
            _utc_datetime(self.expires_at, "lockExpiresAt"),
        )
        if self.expires_at <= self.acquired_at:
            raise _field_problem(
                "lockExpiresAt",
                _("The edit lock expiry must follow its acquisition time."),
            )
        if not isinstance(self.state, DocumentLockState):
            raise _field_problem("lockState", _("Select a supported value."))
        closure_values = (self.closed_at, self.closed_by)
        if self.state is DocumentLockState.ACTIVE:
            if any(value is not None for value in closure_values) or self.reason:
                raise _field_problem(
                    "lockState",
                    _("An active edit lock cannot contain closure details."),
                )
        else:
            if not all(value is not None for value in closure_values):
                raise _field_problem(
                    "lockState",
                    _("A closed edit lock requires closure details."),
                )
            object.__setattr__(
                self,
                "closed_at",
                _utc_datetime(self.closed_at, "lockClosedAt"),
            )
            object.__setattr__(
                self,
                "closed_by",
                _require_text(
                    self.closed_by,
                    "lockClosedBy",
                    maximum=254,
                    pattern=_ACTOR_PATTERN,
                ),
            )
            if self.closed_at < self.acquired_at:
                raise _field_problem(
                    "lockClosedAt",
                    _("The edit lock cannot close before it is acquired."),
                )
            if self.state is DocumentLockState.RECOVERED:
                object.__setattr__(
                    self,
                    "reason",
                    _require_text(self.reason, "reason", maximum=1000),
                )
            elif self.reason is not None:
                raise _field_problem(
                    "reason",
                    _("Only a recovered edit lock records a recovery reason."),
                )

    def active_at(self, now: datetime) -> bool:
        observed = _utc_datetime(now, "observedAt")
        return self.state is DocumentLockState.ACTIVE and self.expires_at > observed


@dataclass(frozen=True, slots=True)
class LockAcquisition:
    document: ControlledDocument
    active_lock: DocumentEditLock
    expired_lock: DocumentEditLock | None


def acquire_document_lock(
    document: ControlledDocument,
    current_lock: DocumentEditLock | None,
    *,
    lock_id: UUID,
    actor: object,
    now: datetime,
    lease_minutes: object,
) -> LockAcquisition:
    holder = _require_text(
        actor,
        "actor",
        maximum=254,
        pattern=_ACTOR_PATTERN,
    )
    acquired_at = _utc_datetime(now, "observedAt")
    lease = _require_positive_integer(
        lease_minutes,
        "lockLeaseMinutes",
        MAX_LOCK_LEASE_MINUTES,
    )
    expired: DocumentEditLock | None = None
    if current_lock is not None:
        _assert_current_lock(document, current_lock)
        if current_lock.active_at(acquired_at):
            raise DocumentLockConflict()
        if current_lock.state is DocumentLockState.ACTIVE:
            expired = replace(
                current_lock,
                version=current_lock.version + 1,
                state=DocumentLockState.EXPIRED,
                closed_at=acquired_at,
                closed_by=holder,
            )
    active = DocumentEditLock(
        global_id=_require_uuid(lock_id, "lockId"),
        document_global_id=document.global_id,
        version=1,
        holder_user_id=holder,
        acquired_at=acquired_at,
        expires_at=acquired_at + timedelta(minutes=lease),
        state=DocumentLockState.ACTIVE,
    )
    updated = replace(
        document,
        version=document.version + 1,
        current_lock_id=active.global_id,
        current_lock_version=active.version,
        current_lock_holder=active.holder_user_id,
        current_lock_expires_at=active.expires_at,
    )
    return LockAcquisition(updated, active, expired)


def release_document_lock(
    document: ControlledDocument,
    current_lock: DocumentEditLock,
    *,
    actor: object,
    now: datetime,
) -> tuple[ControlledDocument, DocumentEditLock]:
    holder = _require_text(
        actor,
        "actor",
        maximum=254,
        pattern=_ACTOR_PATTERN,
    )
    closed_at = _utc_datetime(now, "observedAt")
    _assert_current_lock(document, current_lock)
    if (
        current_lock.state is not DocumentLockState.ACTIVE
        or current_lock.holder_user_id.casefold() != holder.casefold()
        or not current_lock.active_at(closed_at)
    ):
        raise DocumentLockConflict()
    closed = replace(
        current_lock,
        version=current_lock.version + 1,
        state=DocumentLockState.RELEASED,
        closed_at=closed_at,
        closed_by=holder,
    )
    return _clear_current_lock(document), closed


def recover_document_lock(
    document: ControlledDocument,
    current_lock: DocumentEditLock,
    *,
    actor: object,
    reason: object,
    now: datetime,
) -> tuple[ControlledDocument, DocumentEditLock]:
    recovered_by = _require_text(
        actor,
        "actor",
        maximum=254,
        pattern=_ACTOR_PATTERN,
    )
    recovery_reason = _require_text(reason, "reason", maximum=1000)
    recovered_at = _utc_datetime(now, "observedAt")
    _assert_current_lock(document, current_lock)
    if current_lock.state is not DocumentLockState.ACTIVE:
        raise DocumentLockConflict()
    closed = replace(
        current_lock,
        version=current_lock.version + 1,
        state=DocumentLockState.RECOVERED,
        closed_at=recovered_at,
        closed_by=recovered_by,
        reason=recovery_reason,
    )
    return _clear_current_lock(document), closed


def _assert_current_lock(
    document: ControlledDocument,
    lock: DocumentEditLock,
) -> None:
    if (
        document.current_lock_id != lock.global_id
        or document.current_lock_version != lock.version
        or document.current_lock_holder != lock.holder_user_id
        or document.current_lock_expires_at != lock.expires_at
        or lock.document_global_id != document.global_id
    ):
        raise DocumentLockConflict()


def _clear_current_lock(document: ControlledDocument) -> ControlledDocument:
    return replace(
        document,
        version=document.version + 1,
        current_lock_id=None,
        current_lock_version=None,
        current_lock_holder=None,
        current_lock_expires_at=None,
    )


@dataclass(frozen=True, slots=True)
class UploadObservation:
    file_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    frappe_content_hash: str


def observe_upload(
    file_name: object,
    content: object,
    policy: DocumentPolicyVersion,
) -> UploadObservation:
    if not isinstance(policy, DocumentPolicyVersion):
        raise DocumentPolicyUnavailable()
    policy.require_published()
    normalized_name = validate_file_name(file_name)
    if not isinstance(content, bytes) or not content:
        raise _field_problem("file", _("Select a non-empty file."))
    if len(content) > policy.maximum_file_bytes:
        raise _field_problem(
            "file",
            _("The file exceeds the limit in the exact document policy version."),
        )
    mime_type = observed_mime_type(normalized_name, content)
    extension_mime_type = (
        mimetypes.guess_type(normalized_name)[0] or "application/octet-stream"
    ).casefold()
    if extension_mime_type != mime_type:
        raise _field_problem(
            "file",
            _("The file name extension does not match the observed file content."),
        )
    if mime_type not in policy.allowed_mime_types:
        raise _field_problem(
            "file",
            _("Select a file format allowed by the exact document policy version."),
        )
    return UploadObservation(
        file_name=normalized_name,
        mime_type=mime_type,
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        frappe_content_hash=hashlib.md5(content, usedforsecurity=False).hexdigest(),
    )


def validate_file_name(value: object) -> str:
    normalized = unicodedata.normalize(
        "NFC",
        _require_text(value, "fileName", maximum=255),
    )
    if (
        normalized in {".", ".."}
        or "/" in normalized
        or "\\" in normalized
        or _FILE_NAME_CONTROL_PATTERN.search(normalized) is not None
    ):
        raise _field_problem("fileName", _("Enter a safe file name."))
    return normalized


def observed_mime_type(file_name: str, content: bytes) -> str:
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


@dataclass(frozen=True, slots=True)
class FileRevisionSnapshot:
    global_id: UUID
    file_document_global_id: UUID
    file_revision: int
    optimistic_version: int
    file_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    scan_state: FileScanState
    frappe_file_id: str
    frappe_content_hash: str
    is_private: bool
    released: bool
    scan_observed_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "global_id",
            _require_uuid(self.global_id, "fileRevisionId"),
        )
        object.__setattr__(
            self,
            "file_document_global_id",
            _require_uuid(
                self.file_document_global_id,
                "fileDocumentId",
            ),
        )
        object.__setattr__(
            self,
            "file_revision",
            _require_positive_integer(
                self.file_revision,
                "fileRevision",
                2_147_483_647,
            ),
        )
        object.__setattr__(
            self,
            "optimistic_version",
            _require_positive_integer(
                self.optimistic_version,
                "fileOptimisticVersion",
                2_147_483_647,
            ),
        )
        object.__setattr__(self, "file_name", validate_file_name(self.file_name))
        object.__setattr__(
            self,
            "mime_type",
            _require_text(
                self.mime_type,
                "mimeType",
                maximum=255,
                pattern=_MIME_PATTERN,
            ).casefold(),
        )
        object.__setattr__(
            self,
            "size_bytes",
            _require_nonnegative_integer(
                self.size_bytes,
                "sizeBytes",
            ),
        )
        if self.size_bytes > MAX_FILE_BYTES:
            raise _field_problem(
                "sizeBytes",
                _("The file size exceeds the supported infrastructure limit."),
            )
        object.__setattr__(
            self,
            "sha256",
            _require_hash(self.sha256, "sha256"),
        )
        if not isinstance(self.scan_state, FileScanState):
            raise _field_problem("scanState", _("Select a supported scan state."))
        object.__setattr__(
            self,
            "frappe_file_id",
            _require_text(
                self.frappe_file_id,
                "fileIdentity",
                maximum=140,
            ),
        )
        object.__setattr__(
            self,
            "frappe_content_hash",
            _require_text(
                self.frappe_content_hash,
                "frappeContentHash",
                maximum=32,
                pattern=_MD5_PATTERN,
            ),
        )
        if self.is_private is not True:
            raise _field_problem("private", _("The exact file must remain private."))
        if type(self.released) is not bool:
            raise _field_problem("released", _("Enter a valid release observation."))
        if self.scan_state is FileScanState.PENDING:
            if self.scan_observed_at is not None:
                raise _field_problem(
                    "scanObservedAt",
                    _("A pending file cannot have a completed scan observation."),
                )
        else:
            object.__setattr__(
                self,
                "scan_observed_at",
                _utc_datetime(self.scan_observed_at, "scanObservedAt"),
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "fileDocumentGlobalId": str(self.file_document_global_id),
            "fileRevision": self.file_revision,
            "optimisticVersion": self.optimistic_version,
            "fileName": self.file_name,
            "mimeType": self.mime_type,
            "sizeBytes": self.size_bytes,
            "sha256": self.sha256,
            "scanState": self.scan_state.value,
            "fileIdentity": self.frappe_file_id,
            "frappeContentHash": self.frappe_content_hash,
            "private": self.is_private,
            "released": self.released,
            "scanObservedAt": (
                self.scan_observed_at.isoformat().replace("+00:00", "Z")
                if self.scan_observed_at
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class DocumentRevisionFile:
    global_id: UUID
    document_revision_global_id: UUID
    file_revision: FileRevisionSnapshot
    display_file_name: str
    role: DocumentFileRole
    provenance: str
    connector_state: ConnectorState
    connector_reason_code: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "global_id",
            _require_uuid(self.global_id, "revisionFileId"),
        )
        object.__setattr__(
            self,
            "document_revision_global_id",
            _require_uuid(
                self.document_revision_global_id,
                "documentRevisionId",
            ),
        )
        if not isinstance(self.file_revision, FileRevisionSnapshot):
            raise _field_problem("fileRevision", _("Enter a valid file revision."))
        object.__setattr__(
            self,
            "display_file_name",
            validate_file_name(self.display_file_name),
        )
        if not isinstance(self.role, DocumentFileRole):
            raise _field_problem("fileRole", _("Select a supported file role."))
        object.__setattr__(
            self,
            "provenance",
            _require_text(
                self.provenance,
                "fileProvenance",
                maximum=64,
                pattern=_KEY_PATTERN,
            ),
        )
        if not isinstance(self.connector_state, ConnectorState):
            raise _field_problem(
                "connectorState",
                _("Select a supported connector state."),
            )
        object.__setattr__(
            self,
            "connector_reason_code",
            _require_text(
                self.connector_reason_code,
                "connectorReasonCode",
                maximum=64,
                pattern=_KEY_PATTERN,
            ),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "documentRevisionGlobalId": str(self.document_revision_global_id),
            "file": self.file_revision.canonical_dict(),
            "displayFileName": self.display_file_name,
            "role": self.role.value,
            "provenance": self.provenance,
            "connector": {
                "state": self.connector_state.value,
                "reasonCode": self.connector_reason_code,
            },
        }


@dataclass(frozen=True, slots=True)
class DocumentRevision:
    global_id: UUID
    document_global_id: UUID
    major: int
    minor: int
    revision_key: str
    reason: str
    effective_date: date | None
    predecessor_revision_id: UUID | None
    state: DocumentRevisionState
    policy_ref: DocumentPolicyReference
    snapshot_hash: str
    version: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "global_id",
            _require_uuid(self.global_id, "revisionId"),
        )
        object.__setattr__(
            self,
            "document_global_id",
            _require_uuid(self.document_global_id, "documentId"),
        )
        object.__setattr__(
            self,
            "major",
            _require_nonnegative_integer(self.major, "major"),
        )
        object.__setattr__(
            self,
            "minor",
            _require_nonnegative_integer(self.minor, "minor"),
        )
        object.__setattr__(
            self,
            "revision_key",
            _require_hash(self.revision_key, "revisionKey"),
        )
        object.__setattr__(
            self,
            "reason",
            _require_text(self.reason, "reason", maximum=2000),
        )
        if self.effective_date is not None and type(self.effective_date) is not date:
            raise _field_problem("effectiveDate", _("Enter a valid date."))
        if self.predecessor_revision_id is not None:
            object.__setattr__(
                self,
                "predecessor_revision_id",
                _require_uuid(
                    self.predecessor_revision_id,
                    "predecessorRevisionId",
                ),
            )
        if not isinstance(self.state, DocumentRevisionState):
            raise _field_problem("revisionState", _("Select a supported value."))
        if not isinstance(self.policy_ref, DocumentPolicyReference):
            raise _field_problem(
                "documentPolicyRef", _("Enter a valid policy reference.")
            )
        object.__setattr__(
            self,
            "snapshot_hash",
            _require_hash(self.snapshot_hash, "revisionSnapshotHash"),
        )
        object.__setattr__(
            self,
            "version",
            _require_positive_integer(self.version, "revisionVersion", 2_147_483_647),
        )


@dataclass(frozen=True, slots=True)
class RevisionAppend:
    document: ControlledDocument
    revision: DocumentRevision
    file: DocumentRevisionFile
    snapshot: Mapping[str, object]


def append_document_revision(
    document: ControlledDocument,
    current_lock: DocumentEditLock,
    file_revision: FileRevisionSnapshot,
    *,
    display_file_name: object,
    revision_id: UUID,
    revision_file_id: UUID,
    actor: object,
    now: datetime,
    major: object,
    minor: object,
    reason: object,
    effective_date: date | None,
    predecessor_revision_id: UUID | None,
    request_id: object,
    trace_id: object,
) -> RevisionAppend:
    holder = _require_text(
        actor,
        "actor",
        maximum=254,
        pattern=_ACTOR_PATTERN,
    )
    observed_at = _utc_datetime(now, "observedAt")
    _assert_current_lock(document, current_lock)
    if (
        not current_lock.active_at(observed_at)
        or current_lock.holder_user_id.casefold() != holder.casefold()
    ):
        raise DocumentLockConflict()
    revision_major = _require_nonnegative_integer(major, "major")
    revision_minor = _require_nonnegative_integer(minor, "minor")
    if effective_date is not None and type(effective_date) is not date:
        raise _field_problem("effectiveDate", _("Enter a valid date."))
    predecessor = (
        None
        if predecessor_revision_id is None
        else _require_uuid(predecessor_revision_id, "predecessorRevisionId")
    )
    if document.current_revision_id is None:
        if predecessor is not None:
            raise _field_problem(
                "predecessorRevisionId",
                _("The first revision cannot have a predecessor."),
            )
    else:
        if predecessor != document.current_revision_id:
            raise DocumentVersionConflict()
        assert document.current_revision_major is not None
        assert document.current_revision_minor is not None
        if (revision_major, revision_minor) <= (
            document.current_revision_major,
            document.current_revision_minor,
        ):
            raise _field_problem(
                "major",
                _("The successor revision must be later than the current revision."),
            )
    global_id = _require_uuid(revision_id, "revisionId")
    revision_key = sha256_json(
        {
            "documentGlobalId": str(document.global_id),
            "major": revision_major,
            "minor": revision_minor,
        }
    )
    revision_file = DocumentRevisionFile(
        global_id=_require_uuid(revision_file_id, "revisionFileId"),
        document_revision_global_id=global_id,
        file_revision=file_revision,
        display_file_name=display_file_name,
        role=DocumentFileRole.PRIMARY,
        provenance="manual_upload",
        connector_state=ConnectorState.UNAVAILABLE,
        connector_reason_code="provider_not_configured",
    )
    payload = {
        "schemaVersion": DOCUMENT_REVISION_SCHEMA_VERSION,
        "globalId": str(global_id),
        "documentGlobalId": str(document.global_id),
        "major": revision_major,
        "minor": revision_minor,
        "reason": _require_text(reason, "reason", maximum=2000),
        "effectiveDate": effective_date.isoformat() if effective_date else None,
        "predecessorRevisionId": str(predecessor) if predecessor else None,
        "state": DocumentRevisionState.DRAFT.value,
        "documentPolicyRef": document.policy_ref.canonical_dict(),
        "lockRef": {
            "globalId": str(current_lock.global_id),
            "version": current_lock.version,
            "holderUserId": current_lock.holder_user_id,
        },
        "file": revision_file.canonical_dict(),
        "createdByUserId": holder,
        "createdAt": observed_at.isoformat().replace("+00:00", "Z"),
        "requestId": _require_text(
            request_id,
            "requestId",
            maximum=128,
        ),
        "traceId": _require_text(
            trace_id,
            "traceId",
            maximum=128,
        ),
    }
    revision = DocumentRevision(
        global_id=global_id,
        document_global_id=document.global_id,
        major=revision_major,
        minor=revision_minor,
        revision_key=revision_key,
        reason=str(payload["reason"]),
        effective_date=effective_date,
        predecessor_revision_id=predecessor,
        state=DocumentRevisionState.DRAFT,
        policy_ref=document.policy_ref,
        snapshot_hash=sha256_json(payload),
        version=1,
    )
    updated = replace(
        document,
        version=document.version + 1,
        current_revision_id=revision.global_id,
        current_revision_major=revision.major,
        current_revision_minor=revision.minor,
        current_revision_hash=revision.snapshot_hash,
    )
    return RevisionAppend(
        updated,
        revision,
        revision_file,
        immutable_mapping(payload),
    )


@dataclass(frozen=True, slots=True)
class DocumentRelationship:
    global_id: UUID
    document_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    kind: DocumentRelationshipKind
    target_identity: str
    target_version: int
    relationship_key: str
    project_reference_type: str | None = None
    target_source_system: str | None = None
    target_reference_global_id: UUID | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "global_id",
            _require_uuid(self.global_id, "relationshipId"),
        )
        object.__setattr__(
            self,
            "document_global_id",
            _require_uuid(self.document_global_id, "documentId"),
        )
        object.__setattr__(
            self,
            "tenant_id",
            _require_text(
                self.tenant_id,
                "tenantId",
                maximum=128,
                pattern=_TENANT_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "project_global_id",
            _require_uuid(self.project_global_id, "projectId"),
        )
        if not isinstance(self.kind, DocumentRelationshipKind):
            raise _field_problem("objectLinks.kind", _("Select a supported link type."))
        if self.kind is DocumentRelationshipKind.PROJECT_REFERENCE:
            if self.project_reference_type not in {
                "customer",
                "product",
                "part",
                "tooling",
                "order",
            }:
                raise _field_problem(
                    "objectLinks.targetSubtype",
                    _("Select a supported typed Project reference."),
                )
            if self.target_source_system not in {"NPI_ONE", "ERPNEXT"}:
                raise _field_problem(
                    "objectLinks.targetSourceSystem",
                    _("Select a supported reference source system."),
                )
            if self.target_reference_global_id is not None:
                object.__setattr__(
                    self,
                    "target_reference_global_id",
                    _require_uuid(
                        self.target_reference_global_id,
                        "objectLinks.targetReferenceGlobalId",
                    ),
                )
        elif any(
            value is not None
            for value in (
                self.project_reference_type,
                self.target_source_system,
                self.target_reference_global_id,
            )
        ):
            raise _field_problem(
                "objectLinks.projectReferenceType",
                _("Only a Project reference can contain a target subtype."),
            )
        object.__setattr__(
            self,
            "target_identity",
            _require_text(
                self.target_identity,
                "objectLinks.targetIdentity",
                maximum=512,
            ),
        )
        object.__setattr__(
            self,
            "target_version",
            _require_positive_integer(
                self.target_version,
                "objectLinks.targetVersion",
                2_147_483_647,
            ),
        )
        object.__setattr__(
            self,
            "relationship_key",
            _require_hash(self.relationship_key, "relationshipKey"),
        )


def build_document_relationship(
    *,
    relationship_id: UUID,
    document: ControlledDocument,
    kind: DocumentRelationshipKind,
    target_identity: object,
    target_version: object,
    project_reference_type: object | None = None,
    target_source_system: object | None = None,
    target_reference_global_id: UUID | None = None,
) -> DocumentRelationship:
    if not isinstance(kind, DocumentRelationshipKind):
        raise _field_problem("objectLinks.kind", _("Select a supported link type."))
    identity = _require_text(
        target_identity,
        "objectLinks.targetIdentity",
        maximum=512,
    )
    version = _require_positive_integer(
        target_version,
        "objectLinks.targetVersion",
        2_147_483_647,
    )
    subtype: str | None
    if kind is DocumentRelationshipKind.PROJECT_REFERENCE:
        subtype = _require_text(
            project_reference_type,
            "objectLinks.projectReferenceType",
            maximum=64,
            pattern=_KEY_PATTERN,
        )
        if subtype not in {"customer", "product", "part", "tooling", "order"}:
            raise _field_problem(
                "objectLinks.targetSubtype",
                _("Select a supported typed Project reference."),
            )
        source_system = _require_text(
            target_source_system,
            "objectLinks.targetSourceSystem",
            maximum=16,
        )
        if source_system not in {"NPI_ONE", "ERPNEXT"}:
            raise _field_problem(
                "objectLinks.targetSourceSystem",
                _("Select a supported reference source system."),
            )
        reference_global_id = (
            None
            if target_reference_global_id is None
            else _require_uuid(
                target_reference_global_id,
                "objectLinks.targetReferenceGlobalId",
            )
        )
    else:
        if any(
            value is not None
            for value in (
                project_reference_type,
                target_source_system,
                target_reference_global_id,
            )
        ):
            raise _field_problem(
                "objectLinks.targetSubtype",
                _("Only a Project reference can contain a target subtype."),
            )
        subtype = None
        source_system = None
        reference_global_id = None
    if kind is not DocumentRelationshipKind.PROJECT_REFERENCE:
        identity = str(_require_uuid(identity, "objectLinks.targetIdentity"))
    key = sha256_json(
        {
            "tenantId": document.tenant_id,
            "projectGlobalId": str(document.project_global_id),
            "documentGlobalId": str(document.global_id),
            "kind": kind.value,
            "projectReferenceType": subtype,
            "targetSourceSystem": source_system,
            "targetReferenceGlobalId": (
                str(reference_global_id) if reference_global_id else None
            ),
            "targetIdentity": identity,
            "targetVersion": version,
        }
    )
    return DocumentRelationship(
        global_id=_require_uuid(relationship_id, "relationshipId"),
        document_global_id=document.global_id,
        tenant_id=document.tenant_id,
        project_global_id=document.project_global_id,
        kind=kind,
        target_identity=identity,
        target_version=version,
        relationship_key=key,
        project_reference_type=subtype,
        target_source_system=source_system,
        target_reference_global_id=reference_global_id,
    )


@dataclass(frozen=True, slots=True)
class Capability:
    state: CapabilityState
    reason_code: str


@dataclass(frozen=True, slots=True)
class PreviewCapability(Capability):
    mode: PreviewMode


@dataclass(frozen=True, slots=True)
class FileCapabilitySnapshot:
    integrity_state: CapabilityState
    integrity_reason_code: str
    preview: PreviewCapability
    download: Capability
    external_retrieval: Capability
    connector: Capability


def file_capabilities(
    *,
    policy: DocumentPolicyVersion,
    file_revision: FileRevisionSnapshot,
    live_identity_matches: bool,
    live_sha256_matches: bool,
    preview_authorized: bool,
    download_authorized: bool,
) -> FileCapabilitySnapshot:
    if not isinstance(policy, DocumentPolicyVersion):
        raise DocumentPolicyUnavailable()
    policy.require_published()
    if type(live_identity_matches) is not bool or type(live_sha256_matches) is not bool:
        raise TypeError("File integrity observations must be boolean.")
    if type(preview_authorized) is not bool or type(download_authorized) is not bool:
        raise TypeError("File capability authorization decisions must be boolean.")
    if not live_identity_matches or not live_sha256_matches:
        integrity = CapabilityState.BLOCKED
        integrity_reason = "file_identity_drift"
    else:
        integrity = CapabilityState.AVAILABLE
        integrity_reason = "verified"
    if not download_authorized:
        download = Capability(CapabilityState.BLOCKED, "permission_required")
    elif integrity is CapabilityState.BLOCKED:
        download = Capability(CapabilityState.BLOCKED, integrity_reason)
    elif file_revision.scan_state is not FileScanState.CLEAN:
        download = Capability(
            CapabilityState.BLOCKED,
            f"scan_{file_revision.scan_state.value}",
        )
    else:
        download = Capability(CapabilityState.AVAILABLE, "authorized")

    if not preview_authorized:
        preview = PreviewCapability(
            CapabilityState.BLOCKED,
            "permission_required",
            PreviewMode.NONE,
        )
    elif integrity is CapabilityState.BLOCKED:
        preview = PreviewCapability(
            CapabilityState.BLOCKED,
            integrity_reason,
            PreviewMode.NONE,
        )
    elif file_revision.scan_state is not FileScanState.CLEAN:
        reason = f"scan_{file_revision.scan_state.value}"
        preview = PreviewCapability(
            CapabilityState.BLOCKED,
            reason,
            PreviewMode.NONE,
        )
    else:
        if file_revision.mime_type in policy.preview_mime_types:
            mode = (
                PreviewMode.NATIVE_PDF
                if file_revision.mime_type == "application/pdf"
                else PreviewMode.NATIVE_IMAGE
            )
            preview = PreviewCapability(
                CapabilityState.AVAILABLE,
                "browser_native",
                mode,
            )
        else:
            preview = PreviewCapability(
                CapabilityState.UNAVAILABLE,
                "format_not_supported",
                PreviewMode.NONE,
            )
    return FileCapabilitySnapshot(
        integrity_state=integrity,
        integrity_reason_code=integrity_reason,
        preview=preview,
        download=download,
        external_retrieval=Capability(
            CapabilityState.UNAVAILABLE,
            "external_access_policy_unavailable",
        ),
        connector=Capability(
            CapabilityState.UNAVAILABLE,
            "provider_not_configured",
        ),
    )


def command_payload_hash(
    *,
    operation: object,
    actor: object,
    tenant_id: object,
    project_id: UUID,
    document_id: UUID | None,
    payload: Mapping[str, object],
    file_sha256: str | None = None,
) -> str:
    operation_value = _require_text(
        operation,
        "operation",
        maximum=64,
        pattern=_KEY_PATTERN,
    )
    actor_value = _require_text(
        actor,
        "actor",
        maximum=254,
        pattern=_ACTOR_PATTERN,
    )
    tenant_value = _require_text(
        tenant_id,
        "tenantId",
        maximum=128,
        pattern=_TENANT_PATTERN,
    )
    if not isinstance(payload, Mapping):
        raise _field_problem("payload", _("Enter a valid request payload."))
    identity: dict[str, object] = {
        "operation": operation_value,
        "actor": actor_value,
        "tenantId": tenant_value,
        "projectGlobalId": str(_require_uuid(project_id, "projectId")),
        "documentGlobalId": (
            str(_require_uuid(document_id, "documentId"))
            if document_id is not None
            else None
        ),
        "payload": dict(payload),
    }
    if file_sha256 is not None:
        identity["fileSha256"] = _require_hash(file_sha256, "fileSha256")
    return sha256_json(identity)


def immutable_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    """Return a shallow immutable view suitable for small domain snapshots."""
    return MappingProxyType(dict(value))
