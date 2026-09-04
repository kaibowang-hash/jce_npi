from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Mapping
from uuid import UUID, uuid5

import frappe

from npi_core.controlled_print.rendering import frappe_convert_pdf
from npi_core.data_exchange.domain import (
    CAPABILITY_CATALOG,
    DATA_EXCHANGE_SCHEMA_VERSION,
    MAX_WORKSPACE_ITEMS,
    ArchiveSourceKind,
    DataExchangeConflict,
    DataExchangeUnavailable,
    DatasetId,
    ExportLanguage,
    ExportProfileVersion,
    RedactionProfile,
    RetentionCategory,
    RetentionPolicyVersion,
    RetentionScope,
    SOURCE_CATEGORY,
    archive_record_payload,
    calculate_retain_until,
    canonical_json,
    sha256_json,
)
from npi_core.data_exchange.export_package import render_report_package
from npi_core.data_exchange.frappe_validation import data_exchange_write
from npi_core.foundation.audit import create_audit_event
from npi_core.foundation.errors import PermissionDenied
from npi_core.foundation.security import Principal, authorize_tenant
from npi_core.reporting.domain import PortfolioFilters
from npi_core.reporting.frappe_repository import FrappeReportingRepository


_EXPORT_NAMESPACE = UUID("d309ebdc-e78e-4b60-9540-341ff64ba293")
_SOURCE_ADAPTERS = {
    ArchiveSourceKind.PROJECT: (
        "NPI Engineering Project",
        "optimistic_version",
        None,
        "creation",
        ("global_id", "tenant_id", "business_code", "project_type", "lifecycle_state", "target_sop", "optimistic_version"),
    ),
    ArchiveSourceKind.QUALITY_REVISION: (
        "NPI Trial Conclusion Revision",
        "conclusion_version",
        "snapshot_hash",
        "created_at",
        ("global_id", "tenant_id", "project_global_id", "trial_round_global_id", "conclusion_version", "state", "conclusion_code", "snapshot_hash"),
    ),
    ArchiveSourceKind.CHANGE_REVISION: (
        "NPI Engineering Change Revision",
        "revision",
        "snapshot_hash",
        "created_at",
        ("global_id", "tenant_id", "project_global_id", "change_global_id", "revision", "internal_state", "snapshot_hash"),
    ),
    ArchiveSourceKind.FILE_REVISION: (
        "NPI File Revision",
        "optimistic_version",
        "sha256",
        "creation",
        ("global_id", "tenant_id", "project_global_id", "document_global_id", "revision", "optimistic_version", "sha256", "mime_type", "size_bytes"),
    ),
    ArchiveSourceKind.DATA_EXCHANGE_EXPORT: (
        "NPI Data Exchange Export",
        "profile_version",
        "package_sha256",
        "created_at",
        ("global_id", "tenant_id", "dataset_id", "profile_global_id", "profile_version", "profile_hash", "row_count", "package_sha256"),
    ),
    ArchiveSourceKind.CONTROLLED_PRINT: (
        "NPI Controlled Print Output",
        None,
        "record_hash",
        "created_at",
        ("global_id", "tenant_id", "project_global_id", "snapshot_global_id", "sha256", "record_hash"),
    ),
}


@dataclass(frozen=True, slots=True)
class DataExchangeOutcome:
    response: dict[str, object]
    replayed: bool = False


class FrappeDataExchangeRepository:
    """Closed P9-06 adapter. Callers cannot select a DocType, method or report."""

    def __init__(self, *, principal: Principal, request_id: str, trace_id: str, clock=None) -> None:
        if principal.is_external or "System Manager" not in principal.roles or principal.tenant_id is None:
            raise PermissionDenied()
        authorize_tenant(principal, principal.tenant_id)
        self.principal = principal
        self.actor = principal.user_id.casefold()
        self.request_id = request_id
        self.trace_id = trace_id
        self._clock = clock or (lambda: datetime.now(UTC))

    def workspace(self) -> dict[str, object]:
        return {
            "schemaVersion": DATA_EXCHANGE_SCHEMA_VERSION,
            "mode": "closed_operation_specific",
            "routesEnabled": _routes_enabled(),
            "productionContact": False,
            "genericWriterAvailable": False,
            "automaticDispositionAvailable": False,
            "capabilities": [dict(item) for item in CAPABILITY_CATALOG],
            "profiles": [self._profile_response(row) for row in self._bounded("NPI Data Exchange Profile", "published_at desc, global_id desc")],
            "exports": [self._export_response(row) for row in self._bounded("NPI Data Exchange Export", "created_at desc, global_id desc")],
            "retentionPolicies": [self._policy_response(row) for row in self._bounded("NPI Retention Policy Version", "published_at desc, global_id desc")],
            "archiveRecords": [self._archive_response(row) for row in self._bounded("NPI Retention Archive Record", "created_at desc, global_id desc")],
        }

    def publish_profile(
        self,
        *,
        global_id: UUID,
        version: int,
        dataset_id: DatasetId,
        columns: tuple[str, ...],
        language: ExportLanguage,
        redaction_profile: RedactionProfile,
        query: tuple[tuple[str, object], ...],
        max_rows: int,
        max_bytes: int,
    ) -> DataExchangeOutcome:
        existing = self._optional("NPI Data Exchange Profile", str(global_id))
        published_at = _datetime(existing.published_at) if existing is not None else self._now()
        profile = ExportProfileVersion(
            global_id=global_id,
            version=version,
            dataset_id=dataset_id,
            columns=columns,
            language=language,
            redaction_profile=redaction_profile,
            query=query,
            max_rows=max_rows,
            max_bytes=max_bytes,
            published_by_user_id=self.actor,
            published_at=published_at,
        )
        if existing is not None:
            if str(existing.definition_hash) != profile.definition_hash:
                raise DataExchangeConflict()
            return DataExchangeOutcome(self._profile_response(existing), replayed=True)
        with data_exchange_write():
            frappe.get_doc(
                {
                    "doctype": "NPI Data Exchange Profile",
                    "global_id": str(profile.global_id),
                    "tenant_id": self.principal.tenant_id,
                    "profile_version": profile.version,
                    "dataset_id": profile.dataset_id.value,
                    "language": profile.language.value,
                    "redaction_profile": profile.redaction_profile.value,
                    "max_rows": profile.max_rows,
                    "max_bytes": profile.max_bytes,
                    "profile_definition": canonical_json(profile.definition_payload()),
                    "definition_hash": profile.definition_hash,
                    "published_by_user_id": profile.published_by_user_id,
                    "published_at": _database_datetime(profile.published_at),
                    "request_id": self.request_id,
                    "trace_id": self.trace_id,
                }
            ).insert()
            self._audit("data_exchange.profile.publish", profile.global_id, profile.version, "published", {"datasetId": profile.dataset_id.value, "definitionHash": profile.definition_hash})
        return DataExchangeOutcome(profile.response())

    def publish_policy(
        self,
        *,
        global_id: UUID,
        version: int,
        scope: RetentionScope,
        scope_reference: str | None,
        effective_from: date,
        effective_until: date | None,
        retention_years: tuple[tuple[RetentionCategory, int], ...],
    ) -> DataExchangeOutcome:
        existing = self._optional("NPI Retention Policy Version", str(global_id))
        published_at = _datetime(existing.published_at) if existing is not None else self._now()
        policy = RetentionPolicyVersion(
            global_id=global_id,
            version=version,
            scope=scope,
            scope_reference=scope_reference,
            effective_from=effective_from,
            effective_until=effective_until,
            retention_years=retention_years,
            published_by_user_id=self.actor,
            published_at=published_at,
        )
        if existing is not None:
            if str(existing.definition_hash) != policy.definition_hash:
                raise DataExchangeConflict()
            return DataExchangeOutcome(self._policy_response(existing), replayed=True)
        with data_exchange_write():
            frappe.get_doc(
                {
                    "doctype": "NPI Retention Policy Version",
                    "global_id": str(policy.global_id),
                    "tenant_id": self.principal.tenant_id,
                    "policy_version": policy.version,
                    "scope": policy.scope.value,
                    "scope_reference": policy.scope_reference,
                    "effective_from": policy.effective_from.isoformat(),
                    "effective_until": policy.effective_until.isoformat() if policy.effective_until else None,
                    "policy_definition": canonical_json(policy.definition_payload()),
                    "definition_hash": policy.definition_hash,
                    "published_by_user_id": policy.published_by_user_id,
                    "published_at": _database_datetime(policy.published_at),
                    "request_id": self.request_id,
                    "trace_id": self.trace_id,
                }
            ).insert()
            self._audit("data_exchange.retention_policy.publish", policy.global_id, policy.version, "published", {"scope": policy.scope.value, "definitionHash": policy.definition_hash})
        return DataExchangeOutcome(policy.response())

    def create_export(
        self,
        *,
        profile_id: UUID,
        profile_version: int,
        profile_hash: str,
        execution_key_hash: str,
    ) -> DataExchangeOutcome:
        replay = frappe.db.get_value("NPI Data Exchange Export", {"execution_key_hash": execution_key_hash}, "name")
        if replay:
            record = frappe.get_doc("NPI Data Exchange Export", replay)
            if str(record.profile_global_id) != str(profile_id) or str(record.profile_hash) != profile_hash:
                raise DataExchangeConflict()
            return DataExchangeOutcome(self._export_response(record), replayed=True)
        profile = self._load_profile(profile_id, profile_version, profile_hash)
        rows, source_hash = self._report_rows(profile)
        now = self._now()
        export_id = uuid5(_EXPORT_NAMESPACE, f"{self.actor}:{execution_key_hash}")
        rendered = render_report_package(
            profile=profile,
            rows=rows,
            generated_at=now,
            actor_user_id=self.actor,
            translate=lambda source: _translate(source, profile.language.value),
            render_pdf=frappe_convert_pdf,
        )
        from frappe.utils.file_manager import save_file

        with data_exchange_write():
            file_document = save_file(rendered.file_name, rendered.content, "NPI Data Exchange Export", str(export_id), is_private=1)
            snapshot = self._export_payload(export_id, profile, rendered, source_hash, len(rows), now, str(file_document.name))
            record_hash = sha256_json(snapshot)
            frappe.get_doc(
                {
                    "doctype": "NPI Data Exchange Export",
                    "global_id": str(export_id),
                    "tenant_id": self.principal.tenant_id,
                    "dataset_id": profile.dataset_id.value,
                    "profile_global_id": str(profile.global_id),
                    "profile_version": profile.version,
                    "profile_hash": profile.definition_hash,
                    "source_hash": source_hash,
                    "data_hash": rendered.data_sha256,
                    "row_count": len(rows),
                    "artifact_file_id": str(file_document.name),
                    "file_name": rendered.file_name,
                    "mime_type": rendered.mime_type,
                    "size_bytes": rendered.size_bytes,
                    "package_sha256": rendered.sha256,
                    "manifest_sha256": rendered.manifest_sha256,
                    "execution_key_hash": execution_key_hash,
                    "export_snapshot": canonical_json(snapshot),
                    "record_hash": record_hash,
                    "created_by_user_id": self.actor,
                    "created_at": _database_datetime(now),
                    "request_id": self.request_id,
                    "trace_id": self.trace_id,
                }
            ).insert()
            self._audit("data_exchange.export.create", export_id, profile.version, "created", {"datasetId": profile.dataset_id.value, "profileHash": profile.definition_hash, "sourceHash": source_hash, "packageSha256": rendered.sha256, "rowCount": len(rows)})
        return DataExchangeOutcome({**snapshot, "recordHash": record_hash})

    def export_content(self, export_id: UUID, expected_hash: str) -> tuple[bytes, str, str]:
        record = self._owned("NPI Data Exchange Export", export_id)
        if str(record.package_sha256) != expected_hash:
            raise DataExchangeConflict()
        file_document = frappe.get_doc("File", str(record.artifact_file_id))
        if not bool(file_document.is_private) or str(file_document.attached_to_name) != str(export_id):
            raise DataExchangeConflict()
        content = file_document.get_content()
        if isinstance(content, str):
            content = content.encode("utf-8")
        if hashlib.sha256(content).hexdigest() != expected_hash:
            raise DataExchangeConflict()
        return content, str(record.file_name), str(record.mime_type)

    def create_archive(
        self,
        *,
        global_id: UUID,
        source_kind: ArchiveSourceKind,
        source_id: UUID,
        source_version: int,
        source_hash: str,
        policy_id: UUID,
        policy_version: int,
        policy_hash: str,
        scope: RetentionScope,
        scope_reference: str | None,
        execution_key_hash: str,
    ) -> DataExchangeOutcome:
        replay = frappe.db.get_value("NPI Retention Archive Record", {"execution_key_hash": execution_key_hash}, "name")
        if replay:
            record = frappe.get_doc("NPI Retention Archive Record", replay)
            if str(record.global_id) != str(global_id):
                raise DataExchangeConflict()
            return DataExchangeOutcome(self._archive_response(record), replayed=True)
        policy = self._load_policy(policy_id, policy_version, policy_hash)
        source_date, snapshot = self._source_snapshot(source_kind, source_id, source_version, source_hash)
        if not policy.applies(on_date=source_date, scope=scope, reference=scope_reference):
            raise DataExchangeConflict()
        category = SOURCE_CATEGORY[source_kind]
        retain_until = calculate_retain_until(source_date, policy.years_for(category))
        now = self._now()
        payload = archive_record_payload(
            global_id=global_id,
            tenant_id=self.principal.tenant_id,
            source_kind=source_kind,
            source_id=source_id,
            source_version=source_version,
            source_hash=source_hash,
            source_date=source_date,
            source_snapshot=snapshot,
            policy=policy,
            retain_until=retain_until,
            actor=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        record_hash = sha256_json(payload)
        with data_exchange_write():
            frappe.get_doc(
                {
                    "doctype": "NPI Retention Archive Record",
                    "global_id": str(global_id),
                    "tenant_id": self.principal.tenant_id,
                    "source_kind": source_kind.value,
                    "category": category.value,
                    "source_global_id": str(source_id),
                    "source_version": source_version,
                    "source_hash": source_hash,
                    "source_date": source_date.isoformat(),
                    "policy_global_id": str(policy.global_id),
                    "policy_version": policy.version,
                    "policy_hash": policy.definition_hash,
                    "retain_until": retain_until.isoformat(),
                    "execution_key_hash": execution_key_hash,
                    "archive_snapshot": canonical_json(payload),
                    "record_hash": record_hash,
                    "created_by_user_id": self.actor,
                    "created_at": _database_datetime(now),
                    "request_id": self.request_id,
                    "trace_id": self.trace_id,
                }
            ).insert()
            self._audit("data_exchange.archive.create", global_id, 1, "created", {"sourceKind": source_kind.value, "sourceHash": source_hash, "policyHash": policy.definition_hash, "retainUntil": retain_until.isoformat()})
        return DataExchangeOutcome({**payload, "recordHash": record_hash})

    def _report_rows(self, profile: ExportProfileVersion) -> tuple[tuple[dict[str, object], ...], str]:
        repository = FrappeReportingRepository(principal=self.principal, clock=self._clock)
        query = dict(profile.query)
        filters = PortfolioFilters(
            customer_reference_key=query.get("customerReferenceKey"), owner_user_id=query.get("ownerUserId"),
            project_type=query.get("projectType"), factory_reference_key=query.get("factoryReferenceKey"),
            sop_month=query.get("sopMonth"), lifecycle_state=query.get("lifecycleState"),
        )
        if profile.dataset_id is DatasetId.PROJECT_PORTFOLIO:
            rows: list[dict[str, object]] = []
            cursor = None
            while True:
                response = repository.portfolio(filters=filters, cursor=cursor, limit=min(100, profile.max_rows - len(rows) or 1))
                for item in response["items"]:
                    rows.append({
                        "projectCode": item.get("businessCode"), "title": item.get("title"), "projectType": item.get("projectType"),
                        "lifecycleState": item.get("lifecycleState"), "targetSop": item.get("targetSop"), "ownerUserId": item.get("ownerUserId"),
                        "currentHealthStatus": (item.get("health") or {}).get("state"), "openWorkCount": (item.get("work") or {}).get("activeCount"),
                        "currentGate": ((item.get("currentGate") or {}).get("title") if item.get("currentGate") else None),
                        "erpAvailability": (item.get("erp") or {}).get("availability"),
                    })
                page = response["page"]
                if not page["hasMore"]:
                    break
                if len(rows) >= profile.max_rows:
                    raise ValueError("The report exceeds the published row limit.")
                cursor = page["nextCursor"]
        else:
            response = repository.kpi_trends(from_month=str(query["fromMonth"]), to_month=str(query["toMonth"]), filters=filters)
            rows = []
            for series in response["series"]:
                definition = series["definition"]
                points = series.get("points") or [{"month": None, "value": None}]
                for point in points:
                    rows.append({"metricKey": definition["key"], "label": definition["labelSource"], "valueKind": definition["valueKind"], "sourceSystem": definition["sourceSystem"], "availability": series["availability"], "reasonCode": series.get("reasonCode"), "month": point.get("month"), "value": point.get("value")})
        normalized = tuple(rows)
        return normalized, sha256_json({"datasetId": profile.dataset_id.value, "query": query, "rows": normalized})

    def _source_snapshot(self, kind, source_id, expected_version, expected_hash):
        doctype, version_field, hash_field, date_field, fields = _SOURCE_ADAPTERS[kind]
        record = self._owned(doctype, source_id)
        version = 1 if version_field is None else int(record.get(version_field) or 0)
        snapshot = {field: record.get(field) for field in fields}
        normalized = {key: _json_safe(value) for key, value in snapshot.items()}
        actual_hash = sha256_json(normalized) if hash_field is None else str(record.get(hash_field) or "")
        if version != expected_version or actual_hash != expected_hash:
            raise DataExchangeConflict()
        raw_date = record.get(date_field)
        source_date = _date(raw_date)
        return source_date, normalized

    def _load_profile(self, profile_id, version, expected_hash):
        record = self._owned("NPI Data Exchange Profile", profile_id)
        payload = _json_object(record.profile_definition)
        if int(record.profile_version) != version or str(record.definition_hash) != expected_hash:
            raise DataExchangeConflict()
        return ExportProfileVersion(
            global_id=UUID(payload["globalId"]), version=int(payload["version"]), dataset_id=DatasetId(payload["datasetId"]),
            columns=tuple(payload["columns"]), language=ExportLanguage(payload["language"]), redaction_profile=RedactionProfile(payload["redactionProfile"]),
            query=tuple(payload["query"].items()), max_rows=int(payload["maxRows"]), max_bytes=int(payload["maxBytes"]),
            published_by_user_id=payload["publishedByUserId"], published_at=_datetime(payload["publishedAt"]), definition_hash=expected_hash,
        )

    def _load_policy(self, policy_id, version, expected_hash):
        record = self._owned("NPI Retention Policy Version", policy_id)
        payload = _json_object(record.policy_definition)
        if int(record.policy_version) != version or str(record.definition_hash) != expected_hash:
            raise DataExchangeConflict()
        return RetentionPolicyVersion(
            global_id=UUID(payload["globalId"]), version=int(payload["version"]), scope=RetentionScope(payload["scope"]),
            scope_reference=payload["scopeReference"], effective_from=date.fromisoformat(payload["effectiveFrom"]),
            effective_until=date.fromisoformat(payload["effectiveUntil"]) if payload["effectiveUntil"] else None,
            retention_years=tuple((RetentionCategory(key), int(value)) for key, value in payload["retentionYears"].items()),
            published_by_user_id=payload["publishedByUserId"], published_at=_datetime(payload["publishedAt"]), definition_hash=expected_hash,
        )

    def _export_payload(self, export_id, profile, rendered, source_hash, row_count, now, file_id):
        return {"schemaVersion": "data-exchange-export.v1", "globalId": str(export_id), "tenantId": self.principal.tenant_id, "datasetId": profile.dataset_id.value, "profileGlobalId": str(profile.global_id), "profileVersion": profile.version, "profileHash": profile.definition_hash, "sourceHash": source_hash, "dataHash": rendered.data_sha256, "rowCount": row_count, "artifact": {"fileName": rendered.file_name, "mimeType": rendered.mime_type, "sizeBytes": rendered.size_bytes, "sha256": rendered.sha256, "manifestSha256": rendered.manifest_sha256}, "createdByUserId": self.actor, "createdAt": _utc(now), "requestId": self.request_id, "traceId": self.trace_id, "privateFileBound": bool(file_id)}

    def _bounded(self, doctype, order_by):
        rows = frappe.get_all(doctype, filters={"tenant_id": self.principal.tenant_id}, fields=["*"], order_by=order_by, limit_page_length=MAX_WORKSPACE_ITEMS + 1)
        if len(rows) > MAX_WORKSPACE_ITEMS:
            raise RuntimeError("The Data Exchange workspace exceeds its safe bound.")
        return rows

    def _owned(self, doctype, global_id):
        record = self._optional(doctype, str(global_id))
        if record is None or str(record.get("tenant_id") or "") != self.principal.tenant_id:
            raise DataExchangeUnavailable()
        return record

    @staticmethod
    def _optional(doctype, name):
        try:
            return frappe.get_doc(doctype, name)
        except frappe.DoesNotExistError:
            return None

    def _profile_response(self, row):
        return {**_json_object(row.get("profile_definition")), "definitionHash": str(row.get("definition_hash"))}

    def _policy_response(self, row):
        return {**_json_object(row.get("policy_definition")), "definitionHash": str(row.get("definition_hash"))}

    def _export_response(self, row):
        payload = _json_object(row.get("export_snapshot"))
        payload["rowCount"] = int(row.get("row_count"))
        return {**payload, "recordHash": str(row.get("record_hash"))}

    def _archive_response(self, row):
        return {**_json_object(row.get("archive_snapshot")), "recordHash": str(row.get("record_hash"))}

    def _audit(self, operation, global_id, object_version, result, summary):
        event = create_audit_event(actor=self.actor, trace_id=self.trace_id, operation=operation, global_id=global_id, object_version=object_version, result=result, input_summary=summary)
        frappe.get_doc({"doctype": "NPI Audit Event", "event_id": str(event.event_id), "global_id": str(event.global_id), "object_version": event.object_version, "actor": event.actor, "trace_id": event.trace_id, "operation": event.operation, "result": event.result, "input_summary": dict(event.input_summary)}).insert()

    def _now(self):
        value = self._clock()
        if value.tzinfo is None:
            raise RuntimeError("The Data Exchange clock must be timezone-aware.")
        return value.astimezone(UTC)


def _translate(source: str, language: str) -> str:
    if language == "en":
        return source
    from frappe.translate import get_all_translations
    value = get_all_translations(language).get(source)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError("A Data Exchange translation is unavailable.")
    return value


def _routes_enabled() -> bool:
    configuration = getattr(frappe, "conf", None)
    return bool(hasattr(configuration, "get") and configuration.get("npi_p9_06_routes_disabled") is False)


def _database_datetime(value):
    return value.astimezone(UTC).replace(tzinfo=None)


def _utc(value):
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _datetime(value):
    result = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return result.replace(tzinfo=UTC) if result.tzinfo is None else result.astimezone(UTC)


def _date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _json_safe(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _json_object(value):
    if isinstance(value, Mapping):
        return dict(value)
    parsed = json.loads(str(value))
    if not isinstance(parsed, dict):
        raise RuntimeError("Persisted Data Exchange snapshot is invalid.")
    return parsed
