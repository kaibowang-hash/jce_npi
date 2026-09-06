from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Mapping, Protocol, Sequence
from uuid import UUID, uuid5

from npi_core.foundation.errors import NpiProblem, RequestValidationFailed

try:
    from frappe import _
except ImportError:  # Keeps the domain independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


BUNDLE_SCHEMA_VERSION = "historical-migration-rehearsal.v1"
PREVIEW_SCHEMA_VERSION = "historical-migration-preview.v1"
JOB_SCHEMA_VERSION = "historical-migration-job.v1"
CORRECTION_SCHEMA_VERSION = "historical-migration-correction.v1"
RECONCILIATION_SCHEMA_VERSION = "historical-migration-reconciliation.v1"
ROLLBACK_SCHEMA_VERSION = "historical-migration-rollback.v1"
_PREVIEW_NAMESPACE = UUID("c18b443b-77dc-4380-9a28-207d7593e337")
_HASH = re.compile(r"^[a-f0-9]{64}$")
_SOURCE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")


class HistoricalMigrationConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "HISTORICAL_MIGRATION_CONFLICT",
            _("The historical migration rehearsal changed after it was reviewed."),
            _("Reload the exact preview and try the operation again."),
        )


class HistoricalMigrationUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "HISTORICAL_MIGRATION_UNAVAILABLE",
            _("The historical migration rehearsal is unavailable."),
        )


class HistoricalMigrationRoutesDisabled(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "HISTORICAL_MIGRATION_ROUTES_DISABLED",
            _("Historical migration rehearsal is temporarily unavailable."),
            _("The non-production rehearsal routes are disabled by Site configuration."),
            retryable=True,
        )


class HistoricalMigrationProductionDenied(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            403,
            "HISTORICAL_MIGRATION_PRODUCTION_DENIED",
            _("Historical migration execution is not allowed on a production Site."),
        )


class MigrationFamily(StrEnum):
    PROJECT = "project"
    TOOLING_MAPPING = "tooling_mapping"
    FILE_INDEX = "file_index"
    NPI_REFERENCE = "npi_reference"


class MigrationAction(StrEnum):
    CREATE = "create"
    LINK = "link"
    SKIP = "skip"
    BLOCKED = "blocked"


class MigrationResultState(StrEnum):
    CREATED = "created"
    LINKED = "linked"
    SKIPPED = "skipped"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_FINAL = "failed_final"
    ROLLED_BACK = "rolled_back"
    ROLLBACK_DENIED = "rollback_denied"


class MigrationJobState(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    SUCCEEDED = "succeeded"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_FINAL = "failed_final"
    RECONCILED = "reconciled"
    ROLLED_BACK = "rolled_back"
    ROLLBACK_DENIED = "rollback_denied"


@dataclass(frozen=True, slots=True)
class MigrationFinding:
    code: str
    field: str
    message: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _code(self.code, "finding.code"))
        object.__setattr__(self, "field", _text(self.field, "finding.field", 128))
        object.__setattr__(self, "message", _text(self.message, "finding.message", 500))

    def payload(self) -> dict[str, str]:
        return {"code": self.code, "field": self.field, "message": self.message}


@dataclass(frozen=True, slots=True)
class MigrationDifference:
    field: str
    source_value: str | None
    target_value: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "field", _text(self.field, "difference.field", 128))
        for name in ("source_value", "target_value"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or len(value) > 1000):
                raise _problem("differences", _("A migration difference is invalid."))

    def payload(self) -> dict[str, str | None]:
        return {
            "field": self.field,
            "sourceValue": self.source_value,
            "targetValue": self.target_value,
        }


@dataclass(frozen=True, slots=True)
class MigrationRow:
    family: MigrationFamily
    ordinal: int
    source_key: str
    values: tuple[tuple[str, str], ...]
    findings: tuple[MigrationFinding, ...]
    source_hash: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.family, MigrationFamily):
            raise _problem("family", _("Select a supported migration family."))
        if type(self.ordinal) is not int or self.ordinal < 2:
            raise _problem("ordinal", _("Enter a valid source row number."))
        object.__setattr__(self, "source_key", _source_key(self.source_key))
        values = tuple(self.values)
        if not values or len({name for name, _ in values}) != len(values):
            raise _problem("values", _("The migration row shape is invalid."))
        if any(
            not isinstance(name, str)
            or not name
            or not isinstance(value, str)
            or len(value) > 2000
            for name, value in values
        ):
            raise _problem("values", _("The migration row shape is invalid."))
        object.__setattr__(self, "values", values)
        findings = tuple(self.findings)
        if any(not isinstance(item, MigrationFinding) for item in findings):
            raise _problem("findings", _("The migration findings are invalid."))
        object.__setattr__(self, "findings", findings)
        expected = sha256_json(self.source_payload())
        if self.source_hash and self.source_hash != expected:
            raise _problem("sourceHash", _("The migration row hash does not match."))
        object.__setattr__(self, "source_hash", expected)

    @property
    def value_map(self) -> dict[str, str]:
        return dict(self.values)

    def source_payload(self) -> dict[str, object]:
        return {
            "family": self.family.value,
            "ordinal": self.ordinal,
            "sourceKey": self.source_key,
            "values": dict(self.values),
        }


@dataclass(frozen=True, slots=True)
class BundleInspection:
    bundle_id: UUID
    source_system: str
    source_sha256: str
    manifest_hash: str
    predecessor_manifest_hash: str | None
    rows: tuple[MigrationRow, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "bundle_id", _uuid(self.bundle_id, "bundleId"))
        object.__setattr__(self, "source_system", _code(self.source_system, "sourceSystem"))
        object.__setattr__(self, "source_sha256", _hash(self.source_sha256, "sourceSha256"))
        object.__setattr__(self, "manifest_hash", _hash(self.manifest_hash, "manifestHash"))
        if self.predecessor_manifest_hash is not None:
            object.__setattr__(
                self,
                "predecessor_manifest_hash",
                _hash(self.predecessor_manifest_hash, "predecessorManifestHash"),
            )
        rows = tuple(self.rows)
        if not rows or any(not isinstance(item, MigrationRow) for item in rows):
            raise _problem("rows", _("The migration bundle has no supported rows."))
        identities = {(item.family, item.source_key.casefold()) for item in rows}
        if len(identities) != len(rows):
            raise _problem("rows", _("Migration source keys must be unique in each family."))
        object.__setattr__(self, "rows", rows)

    @property
    def findings_count(self) -> int:
        return sum(len(row.findings) for row in self.rows)


@dataclass(frozen=True, slots=True)
class TargetObservation:
    action: MigrationAction
    target_global_id: UUID | None = None
    target_version: int | None = None
    target_snapshot_hash: str | None = None
    differences: tuple[MigrationDifference, ...] = ()
    findings: tuple[MigrationFinding, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.action, MigrationAction):
            raise _problem("action", _("Select a supported migration action."))
        complete_target = (
            self.target_global_id,
            self.target_version,
            self.target_snapshot_hash,
        )
        if any(value is not None for value in complete_target):
            if not all(value is not None for value in complete_target):
                raise _problem("target", _("Enter a complete migration target."))
            object.__setattr__(
                self, "target_global_id", _uuid(self.target_global_id, "targetGlobalId")
            )
            if type(self.target_version) is not int or self.target_version < 1:
                raise _problem("targetVersion", _("Enter a positive target version."))
            object.__setattr__(
                self,
                "target_snapshot_hash",
                _hash(self.target_snapshot_hash, "targetSnapshotHash"),
            )
        if self.action in {MigrationAction.LINK, MigrationAction.SKIP} and not all(
            value is not None for value in complete_target
        ):
            raise _problem("target", _("The migration action requires an exact target."))
        if self.action is MigrationAction.CREATE and any(
            value is not None for value in complete_target
        ):
            raise _problem("target", _("A create action cannot claim an existing target."))
        if self.action is MigrationAction.BLOCKED and not self.findings:
            raise _problem("findings", _("A blocked migration row requires a finding."))


class PreviewResolver(Protocol):
    def observe(self, row: MigrationRow) -> TargetObservation: ...


@dataclass(frozen=True, slots=True)
class MigrationPreviewRow:
    family: MigrationFamily
    ordinal: int
    source_key: str
    source_hash: str
    action: MigrationAction
    target_global_id: UUID | None
    target_version: int | None
    target_snapshot_hash: str | None
    differences: tuple[MigrationDifference, ...]
    findings: tuple[MigrationFinding, ...]

    def payload(self) -> dict[str, object]:
        return {
            "family": self.family.value,
            "ordinal": self.ordinal,
            "sourceKey": self.source_key,
            "sourceHash": self.source_hash,
            "action": self.action.value,
            "targetGlobalId": (
                str(self.target_global_id) if self.target_global_id is not None else None
            ),
            "targetVersion": self.target_version,
            "targetSnapshotHash": self.target_snapshot_hash,
            "differences": [item.payload() for item in self.differences],
            "findings": [item.payload() for item in self.findings],
        }


@dataclass(frozen=True, slots=True)
class HistoricalMigrationPreview:
    global_id: UUID
    bundle_id: UUID
    manifest_hash: str
    source_sha256: str
    source_file_revision_global_id: UUID
    source_file_optimistic_version: int
    tenant_id: str
    version: int
    rows: tuple[MigrationPreviewRow, ...]
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for name in (
            "global_id",
            "bundle_id",
            "source_file_revision_global_id",
            "request_id",
        ):
            object.__setattr__(self, name, _uuid(getattr(self, name), name))
        object.__setattr__(self, "manifest_hash", _hash(self.manifest_hash, "manifestHash"))
        object.__setattr__(self, "source_sha256", _hash(self.source_sha256, "sourceSha256"))
        if type(self.source_file_optimistic_version) is not int or self.source_file_optimistic_version < 1:
            raise _problem(
                "sourceFileOptimisticVersion",
                _("Enter a positive File Revision version."),
            )
        object.__setattr__(self, "tenant_id", _text(self.tenant_id, "tenantId", 128))
        if type(self.version) is not int or self.version < 1:
            raise _problem("version", _("Enter a positive preview version."))
        rows = tuple(self.rows)
        if not rows or any(not isinstance(item, MigrationPreviewRow) for item in rows):
            raise _problem("rows", _("The migration preview is invalid."))
        object.__setattr__(self, "rows", rows)
        object.__setattr__(
            self,
            "created_by_user_id",
            _text(self.created_by_user_id, "createdByUserId", 254),
        )
        if self.created_at.tzinfo is None:
            raise _problem("createdAt", _("Enter a timezone-aware timestamp."))
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))
        object.__setattr__(self, "trace_id", _text(self.trace_id, "traceId", 128))
        expected = sha256_json(self.snapshot_payload())
        if self.snapshot_hash and self.snapshot_hash != expected:
            raise _problem("snapshotHash", _("The migration preview hash does not match."))
        object.__setattr__(self, "snapshot_hash", expected)

    @property
    def blocked(self) -> bool:
        return any(row.action is MigrationAction.BLOCKED for row in self.rows)

    def summary(self) -> dict[str, int]:
        return {
            action.value: sum(row.action is action for row in self.rows)
            for action in MigrationAction
        }

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": PREVIEW_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "bundleId": str(self.bundle_id),
            "manifestHash": self.manifest_hash,
            "sourceSha256": self.source_sha256,
            "sourceFileRevisionGlobalId": str(self.source_file_revision_global_id),
            "sourceFileOptimisticVersion": self.source_file_optimistic_version,
            "tenantId": self.tenant_id,
            "version": self.version,
            "summary": self.summary(),
            "rows": [row.payload() for row in self.rows],
            "createdByUserId": self.created_by_user_id,
            "createdAt": self.created_at.isoformat().replace("+00:00", "Z"),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }

    def response(self) -> dict[str, object]:
        return {**self.snapshot_payload(), "snapshotHash": self.snapshot_hash}


def build_preview(
    inspection: BundleInspection,
    resolver: PreviewResolver,
    *,
    source_file_revision_global_id: UUID,
    source_file_optimistic_version: int,
    tenant_id: str,
    actor: str,
    created_at: datetime,
    request_id: UUID,
    trace_id: str,
) -> HistoricalMigrationPreview:
    rows: list[MigrationPreviewRow] = []
    for source_row in inspection.rows:
        if source_row.findings:
            observation = TargetObservation(
                action=MigrationAction.BLOCKED,
                findings=source_row.findings,
            )
        else:
            observation = resolver.observe(source_row)
        rows.append(
            MigrationPreviewRow(
                family=source_row.family,
                ordinal=source_row.ordinal,
                source_key=source_row.source_key,
                source_hash=source_row.source_hash,
                action=observation.action,
                target_global_id=observation.target_global_id,
                target_version=observation.target_version,
                target_snapshot_hash=observation.target_snapshot_hash,
                differences=tuple(observation.differences),
                findings=tuple(observation.findings),
            )
        )
    preview_id = uuid5(
        _PREVIEW_NAMESPACE,
        f"{inspection.bundle_id}:{inspection.manifest_hash}:{source_file_revision_global_id}:"
        f"{source_file_optimistic_version}",
    )
    return HistoricalMigrationPreview(
        global_id=preview_id,
        bundle_id=inspection.bundle_id,
        manifest_hash=inspection.manifest_hash,
        source_sha256=inspection.source_sha256,
        source_file_revision_global_id=source_file_revision_global_id,
        source_file_optimistic_version=source_file_optimistic_version,
        tenant_id=tenant_id,
        version=1,
        rows=tuple(rows),
        created_by_user_id=actor,
        created_at=created_at,
        request_id=request_id,
        trace_id=trace_id,
    )


def sha256_json(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _uuid(value: object, path: str) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        parsed = UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        raise _problem(path, _("Enter a valid global ID.")) from None
    if str(parsed) != str(value).casefold():
        raise _problem(path, _("Enter a canonical global ID."))
    return parsed


def _text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise _problem(path, _("Enter a valid value."))
    return value.strip()


def _code(value: object, path: str) -> str:
    normalized = _text(value, path, 128)
    if _SOURCE_KEY.fullmatch(normalized) is None:
        raise _problem(path, _("Enter a supported code."))
    return normalized


def _source_key(value: object) -> str:
    normalized = _text(value, "sourceKey", 128)
    if _SOURCE_KEY.fullmatch(normalized) is None:
        raise _problem("sourceKey", _("Enter a valid source key."))
    return normalized


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise _problem(path, _("Enter a lowercase SHA-256 hash."))
    return value


def _problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
