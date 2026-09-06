from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Mapping, Sequence
from uuid import UUID

from npi_core.foundation.errors import NpiProblem, RequestValidationFailed

try:
    from frappe import _
except ImportError:  # Keeps the domain independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


DATA_EXCHANGE_SCHEMA_VERSION = "data-exchange.v1"
REPORT_PACKAGE_SCHEMA_VERSION = "data-exchange-report-package.v1"
EXPORT_PROFILE_SCHEMA_VERSION = "data-exchange-export-profile.v1"
RETENTION_POLICY_SCHEMA_VERSION = "retention-policy.v1"
ARCHIVE_RECORD_SCHEMA_VERSION = "retention-archive-record.v1"
MAX_EXPORT_ROWS = 5_000
MAX_EXPORT_BYTES = 8_000_000
MAX_WORKSPACE_ITEMS = 50
_HASH = re.compile(r"^[a-f0-9]{64}$")
_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_MONTH = re.compile(r"^\d{4}-(?:0[1-9]|1[0-2])$")


class DataExchangeConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "DATA_EXCHANGE_CONFLICT",
            _("The Data Exchange definition or source changed after it was reviewed."),
            _("Reload the exact version and try the operation again."),
        )


class DataExchangeUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "DATA_EXCHANGE_UNAVAILABLE",
            _("The requested Data Exchange record is unavailable."),
        )


class DataExchangeRoutesDisabled(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "DATA_EXCHANGE_ROUTES_DISABLED",
            _("Data Exchange is temporarily unavailable."),
            _("The Data Exchange routes are disabled by Site configuration."),
            retryable=True,
        )


class DatasetId(StrEnum):
    PROJECT_PORTFOLIO = "project_portfolio.v1"
    KPI_TRENDS = "kpi_trends.v1"


class ExportLanguage(StrEnum):
    ENGLISH = "en"
    SIMPLIFIED_CHINESE = "zh"
    TRADITIONAL_CHINESE = "zh-TW"


class RedactionProfile(StrEnum):
    INTERNAL_REPORT = "internal_report.v1"
    MINIMUM_DISCLOSURE = "minimum_disclosure.v1"


class RetentionScope(StrEnum):
    TENANT = "tenant"
    CUSTOMER = "customer_reference"
    REGULATION = "regulation_reference"


class RetentionCategory(StrEnum):
    PROJECT = "project"
    QUALITY = "quality"
    CHANGE = "change"
    FILE = "file"
    DATA_EXCHANGE_EXPORT = "data_exchange_export"
    CONTROLLED_PRINT = "controlled_print"


class ArchiveSourceKind(StrEnum):
    PROJECT = "project"
    QUALITY_REVISION = "quality_revision"
    CHANGE_REVISION = "change_revision"
    FILE_REVISION = "file_revision"
    DATA_EXCHANGE_EXPORT = "data_exchange_export"
    CONTROLLED_PRINT = "controlled_print"


SOURCE_CATEGORY = {
    ArchiveSourceKind.PROJECT: RetentionCategory.PROJECT,
    ArchiveSourceKind.QUALITY_REVISION: RetentionCategory.QUALITY,
    ArchiveSourceKind.CHANGE_REVISION: RetentionCategory.CHANGE,
    ArchiveSourceKind.FILE_REVISION: RetentionCategory.FILE,
    ArchiveSourceKind.DATA_EXCHANGE_EXPORT: RetentionCategory.DATA_EXCHANGE_EXPORT,
    ArchiveSourceKind.CONTROLLED_PRINT: RetentionCategory.CONTROLLED_PRINT,
}


PROJECT_PORTFOLIO_COLUMNS = (
    "projectCode",
    "title",
    "projectType",
    "lifecycleState",
    "targetSop",
    "ownerUserId",
    "currentHealthStatus",
    "openWorkCount",
    "currentGate",
    "erpAvailability",
)
KPI_TREND_COLUMNS = (
    "metricKey",
    "label",
    "valueKind",
    "sourceSystem",
    "availability",
    "reasonCode",
    "month",
    "value",
)
DATASET_COLUMNS = {
    DatasetId.PROJECT_PORTFOLIO: PROJECT_PORTFOLIO_COLUMNS,
    DatasetId.KPI_TRENDS: KPI_TREND_COLUMNS,
}
MINIMUM_COLUMNS = {
    DatasetId.PROJECT_PORTFOLIO: frozenset(
        {
            "projectCode",
            "title",
            "projectType",
            "lifecycleState",
            "targetSop",
            "currentHealthStatus",
            "openWorkCount",
            "currentGate",
            "erpAvailability",
        }
    ),
    DatasetId.KPI_TRENDS: frozenset(KPI_TREND_COLUMNS),
}
CAPABILITY_CATALOG = (
    {
        "id": "tooling_xlsx_import.v1",
        "mode": "specialized_existing",
        "exportableHere": False,
        "route": "/projects/{projectId}/tooling/imports",
    },
    {
        "id": "tooling_object_export.v1",
        "mode": "specialized_existing",
        "exportableHere": False,
        "route": "/projects/{projectId}/tooling",
    },
    {
        "id": "controlled_print.v1",
        "mode": "specialized_existing",
        "exportableHere": False,
        "route": "/projects/{projectId}/documents",
    },
    {
        "id": "historical_migration_rehearsal.v1",
        "mode": "specialized_existing",
        "exportableHere": False,
        "route": "/administration/historical-migration-rehearsals",
    },
    {
        "id": DatasetId.PROJECT_PORTFOLIO.value,
        "mode": "report_export_profile",
        "exportableHere": True,
        "route": "/portfolio/projects",
    },
    {
        "id": DatasetId.KPI_TRENDS.value,
        "mode": "report_export_profile",
        "exportableHere": True,
        "route": "/reports/kpis",
    },
)


def sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class ExportProfileVersion:
    global_id: UUID
    version: int
    dataset_id: DatasetId
    columns: tuple[str, ...]
    language: ExportLanguage
    redaction_profile: RedactionProfile
    query: tuple[tuple[str, object], ...]
    max_rows: int
    max_bytes: int
    published_by_user_id: str
    published_at: datetime
    definition_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "globalId"))
        if type(self.version) is not int or self.version < 1:
            raise _problem("version", _("Enter a positive profile version."))
        try:
            dataset = DatasetId(self.dataset_id)
            language = ExportLanguage(self.language)
            redaction = RedactionProfile(self.redaction_profile)
        except ValueError:
            raise _problem("profile", _("Select a supported export profile value.")) from None
        object.__setattr__(self, "dataset_id", dataset)
        object.__setattr__(self, "language", language)
        object.__setattr__(self, "redaction_profile", redaction)
        columns = tuple(self.columns)
        allowed = DATASET_COLUMNS[dataset]
        effective = (
            tuple(column for column in columns if column in MINIMUM_COLUMNS[dataset])
            if redaction is RedactionProfile.MINIMUM_DISCLOSURE
            else columns
        )
        if not effective or effective != columns or len(columns) != len(set(columns)):
            raise _problem("columns", _("Select unique allowed columns for the dataset."))
        if any(column not in allowed for column in columns):
            raise _problem("columns", _("Select unique allowed columns for the dataset."))
        object.__setattr__(self, "columns", columns)
        query = tuple(sorted(tuple(self.query), key=lambda item: item[0]))
        _validate_query(dataset, query)
        object.__setattr__(self, "query", query)
        if type(self.max_rows) is not int or not 1 <= self.max_rows <= MAX_EXPORT_ROWS:
            raise _problem("maxRows", _("Enter an export row limit from 1 to 5000."))
        if type(self.max_bytes) is not int or not 10_000 <= self.max_bytes <= MAX_EXPORT_BYTES:
            raise _problem("maxBytes", _("Enter an export byte limit from 10000 to 8000000."))
        object.__setattr__(
            self,
            "published_by_user_id",
            _text(self.published_by_user_id, "publishedByUserId", 254),
        )
        object.__setattr__(self, "published_at", _aware(self.published_at, "publishedAt"))
        expected = sha256_json(self.definition_payload())
        if self.definition_hash and self.definition_hash != expected:
            raise _problem("definitionHash", _("The export profile hash does not match."))
        object.__setattr__(self, "definition_hash", expected)

    def definition_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": EXPORT_PROFILE_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "version": self.version,
            "datasetId": self.dataset_id.value,
            "columns": list(self.columns),
            "language": self.language.value,
            "redactionProfile": self.redaction_profile.value,
            "query": dict(self.query),
            "outputs": ["csv", "xlsx", "pdf", "readme"],
            "maxRows": self.max_rows,
            "maxBytes": self.max_bytes,
            "publishedByUserId": self.published_by_user_id,
            "publishedAt": _utc(self.published_at),
        }

    def response(self) -> dict[str, object]:
        return {**self.definition_payload(), "definitionHash": self.definition_hash}


@dataclass(frozen=True, slots=True)
class RetentionPolicyVersion:
    global_id: UUID
    version: int
    scope: RetentionScope
    scope_reference: str | None
    effective_from: date
    effective_until: date | None
    retention_years: tuple[tuple[RetentionCategory, int], ...]
    published_by_user_id: str
    published_at: datetime
    definition_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "globalId"))
        if type(self.version) is not int or self.version < 1:
            raise _problem("version", _("Enter a positive policy version."))
        try:
            scope = RetentionScope(self.scope)
        except ValueError:
            raise _problem("scope", _("Select a supported retention scope.")) from None
        object.__setattr__(self, "scope", scope)
        reference = self.scope_reference
        if scope is RetentionScope.TENANT:
            if reference not in (None, ""):
                raise _problem("scopeReference", _("A tenant policy cannot include a scope reference."))
            reference = None
        elif not isinstance(reference, str) or _REFERENCE.fullmatch(reference.strip()) is None:
            raise _problem("scopeReference", _("Enter the exact policy scope reference."))
        else:
            reference = reference.strip()
        object.__setattr__(self, "scope_reference", reference)
        if not isinstance(self.effective_from, date) or isinstance(self.effective_from, datetime):
            raise _problem("effectiveFrom", _("Enter a valid policy start date."))
        if self.effective_until is not None:
            if (
                not isinstance(self.effective_until, date)
                or isinstance(self.effective_until, datetime)
                or self.effective_until <= self.effective_from
            ):
                raise _problem("effectiveUntil", _("Enter an end date after the policy start date."))
        values = tuple(sorted(self.retention_years, key=lambda item: item[0].value))
        if {item[0] for item in values} != set(RetentionCategory) or len(values) != len(RetentionCategory):
            raise _problem("retentionYears", _("Enter retention years for every controlled category."))
        if any(type(years) is not int or not 1 <= years <= 100 for _, years in values):
            raise _problem("retentionYears", _("Enter retention years from 1 to 100."))
        object.__setattr__(self, "retention_years", values)
        object.__setattr__(
            self,
            "published_by_user_id",
            _text(self.published_by_user_id, "publishedByUserId", 254),
        )
        object.__setattr__(self, "published_at", _aware(self.published_at, "publishedAt"))
        expected = sha256_json(self.definition_payload())
        if self.definition_hash and self.definition_hash != expected:
            raise _problem("definitionHash", _("The retention policy hash does not match."))
        object.__setattr__(self, "definition_hash", expected)

    def definition_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": RETENTION_POLICY_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "version": self.version,
            "scope": self.scope.value,
            "scopeReference": self.scope_reference,
            "effectiveFrom": self.effective_from.isoformat(),
            "effectiveUntil": self.effective_until.isoformat() if self.effective_until else None,
            "retentionYears": {category.value: years for category, years in self.retention_years},
            "publishedByUserId": self.published_by_user_id,
            "publishedAt": _utc(self.published_at),
        }

    def response(self) -> dict[str, object]:
        return {**self.definition_payload(), "definitionHash": self.definition_hash}

    def years_for(self, category: RetentionCategory) -> int:
        return dict(self.retention_years)[category]

    def applies(self, *, on_date: date, scope: RetentionScope, reference: str | None) -> bool:
        return (
            self.scope is scope
            and self.scope_reference == reference
            and self.effective_from <= on_date
            and (self.effective_until is None or on_date < self.effective_until)
        )


def calculate_retain_until(source_date: date, years: int) -> date:
    try:
        return source_date.replace(year=source_date.year + years)
    except ValueError:  # February 29 uses the inclusive last day of February.
        return source_date.replace(month=2, day=28, year=source_date.year + years)


def archive_record_payload(
    *,
    global_id: UUID,
    tenant_id: str,
    source_kind: ArchiveSourceKind,
    source_id: UUID,
    source_version: int,
    source_hash: str,
    source_date: date,
    source_snapshot: Mapping[str, object],
    policy: RetentionPolicyVersion,
    retain_until: date,
    actor: str,
    created_at: datetime,
    request_id: UUID,
    trace_id: str,
) -> dict[str, object]:
    if source_version < 1 or not _HASH.fullmatch(source_hash):
        raise _problem("source", _("Enter an exact immutable archive source."))
    return {
        "schemaVersion": ARCHIVE_RECORD_SCHEMA_VERSION,
        "globalId": str(_uuid(global_id, "globalId")),
        "tenantId": _text(tenant_id, "tenantId", 128),
        "sourceKind": ArchiveSourceKind(source_kind).value,
        "category": SOURCE_CATEGORY[ArchiveSourceKind(source_kind)].value,
        "sourceId": str(_uuid(source_id, "sourceId")),
        "sourceVersion": source_version,
        "sourceHash": source_hash,
        "sourceDate": source_date.isoformat(),
        "sourceSnapshot": dict(source_snapshot),
        "policyId": str(policy.global_id),
        "policyVersion": policy.version,
        "policyHash": policy.definition_hash,
        "retainUntil": retain_until.isoformat(),
        "createdByUserId": _text(actor, "createdByUserId", 254),
        "createdAt": _utc(_aware(created_at, "createdAt")),
        "requestId": str(_uuid(request_id, "requestId")),
        "traceId": _text(trace_id, "traceId", 128),
    }


def _validate_query(dataset: DatasetId, query: Sequence[tuple[str, object]]) -> None:
    values = dict(query)
    if len(values) != len(query):
        raise _problem("query", _("The export query fields must be unique."))
    portfolio = {
        "customerReferenceKey",
        "ownerUserId",
        "projectType",
        "factoryReferenceKey",
        "sopMonth",
        "lifecycleState",
    }
    allowed = portfolio if dataset is DatasetId.PROJECT_PORTFOLIO else portfolio | {"fromMonth", "toMonth"}
    if set(values) - allowed:
        raise _problem("query", _("The export query contains unsupported fields."))
    if dataset is DatasetId.KPI_TRENDS:
        months = tuple(values.get(key) for key in ("fromMonth", "toMonth"))
        if not all(isinstance(value, str) and _MONTH.fullmatch(value) for value in months):
            raise _problem("query", _("KPI exports require an exact month range."))
        start = date.fromisoformat(str(months[0]) + "-01")
        end = date.fromisoformat(str(months[1]) + "-01")
        span = (end.year - start.year) * 12 + end.month - start.month
        if span < 0 or span > 23:
            raise _problem("query", _("KPI exports require a range of no more than 24 months."))
    if any(value is not None and (not isinstance(value, str) or len(value) > 128) for value in values.values()):
        raise _problem("query", _("The export query contains unsupported values."))


def _problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


def _uuid(value: object, path: str) -> UUID:
    if not isinstance(value, UUID):
        try:
            value = UUID(str(value))
        except (ValueError, TypeError, AttributeError):
            raise _problem(path, _("Enter a canonical global ID.")) from None
    return value


def _text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise _problem(path, _("Enter a valid value."))
    return value.strip()


def _aware(value: datetime, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _problem(path, _("Enter a timezone-aware timestamp."))
    return value.astimezone(UTC)


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
