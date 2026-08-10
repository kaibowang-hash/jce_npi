from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import UUID, uuid4

import frappe
from frappe import _
from frappe.translate import get_user_lang

from npi_core.controlled_print.rendering import frappe_translate
from npi_core.documents.frappe_repository import _decode_cursor, _encode_cursor
from npi_core.foundation.errors import RequestValidationFailed
from npi_core.foundation.localization import validate_language_code
from npi_core.tooling.domain import (
    ToolingIdempotencyConflict,
    ToolingReferenceUnavailable,
    ToolingVersionConflict,
    sha256_json,
)
from npi_core.tooling.export_domain import (
    MAX_TOOLING_EXPORT_OBJECTS,
    TOOLING_LIST_GRID_ID,
    TOOLING_LIST_TABLE_SCHEMA_VERSION,
    TOOLING_OBJECT_PACKAGE_CONFIDENTIALITY,
    TOOLING_OBJECT_PACKAGE_VALIDITY,
    ToolingExportExpired,
    ToolingExportLanguage,
    ToolingExportMode,
    ToolingExportOperation,
    ToolingExportPackageIdentity,
    ToolingExportReference,
    ToolingExportSelection,
    ToolingListFilter,
    ToolingListGroupKey,
    ToolingListPreferenceSnapshot,
    ToolingListRow,
    ToolingListSortDirection,
    ToolingListSortKey,
    ToolingListViewId,
    ToolingSource,
    filtered_query_snapshot_hash,
    query_tooling_list_rows,
    resolve_exact_selection,
    tooling_export_receipt_key_hash,
    tooling_list_preference_key_hash,
    tooling_list_query_snapshot_hash,
)
from npi_core.tooling.export_frappe_validation import (
    PREFERENCE_VALIDATION_DIAGNOSTIC_HEADER,
    record_tooling_preference_validation_fallback,
    tooling_export_write,
    tooling_preference_validation_diagnostics,
)
from npi_core.tooling.export_rendering import (
    RenderedToolingObjectPackage,
    render_tooling_object_package,
)
from npi_core.tooling.frappe_repository import FrappeToolingRepository


_MAX_PAGE_SIZE = 100
_MAX_PROJECT_SETS = 500
_MAX_PROJECT_REVISIONS = 1_000
_MAX_IMPORT_BINDINGS = 1_000


@dataclass(frozen=True, slots=True)
class ToolingExportCommandOutcome:
    response: dict[str, Any]
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class ToolingExportBinaryOutcome:
    content: bytes
    file_name: str
    mime_type: str
    replayed: bool = False


class FrappeToolingExportRepository(FrappeToolingRepository):
    """Project-first P6-08 list, preference and private package adapter."""

    def __init__(
        self,
        *,
        clock=None,
        uuid_factory=uuid4,
        translate=frappe_translate,
        **values: object,
    ) -> None:
        super().__init__(clock=clock, uuid_factory=uuid_factory, **values)
        self._export_clock = clock or (lambda: datetime.now(UTC))
        self._export_uuid_factory = uuid_factory
        self._export_translate = translate

    def tooling_list(
        self,
        project_id: UUID,
        *,
        filter_spec: ToolingListFilter,
        page_size: int,
        cursor: str | None,
    ) -> dict[str, object] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        rows = self._tooling_list_rows(project)
        selected = query_tooling_list_rows(rows, filter_spec)
        query_hash = tooling_list_query_snapshot_hash(filter_spec, rows)
        start = 0
        if cursor is not None:
            cursor_id = _decode_cursor(cursor, expected_query_hash=query_hash)
            positions = [
                index
                for index, row in enumerate(selected)
                if str(row.tooling_master_global_id) == cursor_id
            ]
            if len(positions) != 1:
                raise RequestValidationFailed(
                    [{"path": "cursor", "message": _("Enter a valid cursor.")}]
                )
            start = positions[0] + 1
        page = selected[start : start + page_size]
        next_cursor = (
            _encode_cursor(
                str(page[-1].tooling_master_global_id),
                query_hash=query_hash,
            )
            if page and start + len(page) < len(selected)
            else None
        )
        can_export = self._is_internal_system_manager()
        return {
            "projectGlobalId": str(project.global_id),
            "filter": filter_spec.snapshot_payload(),
            "querySnapshotHash": query_hash,
            "totalCount": len(selected),
            "pageSize": page_size,
            "nextCursor": next_cursor,
            "items": [_public_row(row) for row in page],
            "permissions": {
                "view": True,
                "canExport": can_export,
                "exportUnavailableReason": (
                    None if can_export else "separate_export_authority_required"
                ),
            },
        }

    def tooling_list_preference(
        self,
        project_id: UUID,
        view_id: ToolingListViewId,
    ) -> dict[str, object] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        key_hash = tooling_list_preference_key_hash(
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            actor_user_id=self.actor,
            view_id=view_id,
        )
        row = self._preference_for_key(project, key_hash, view_id)
        if row is None:
            preference = ToolingListPreferenceSnapshot(
                view_id=view_id,
                filter_spec=ToolingListFilter(view_id=view_id),
            )
            return {
                "stored": False,
                "globalId": None,
                "optimisticVersion": 0,
                "snapshotHash": None,
                "preference": preference.snapshot_payload(),
            }
        return self._public_preference(row)

    def save_tooling_list_preference(
        self,
        project_id: UUID,
        view_id: ToolingListViewId,
        *,
        expected_version: int,
        expected_snapshot_hash: str | None,
        preference: ToolingListPreferenceSnapshot,
    ) -> dict[str, object] | None:
        project = self._locked_view_project(project_id)
        if project is None:
            return None
        key_hash = tooling_list_preference_key_hash(
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            actor_user_id=self.actor,
            view_id=view_id,
        )
        row = self._locked_preference_for_key(project, key_hash, view_id)
        if row is None:
            if expected_version != 0 or expected_snapshot_hash is not None:
                raise ToolingVersionConflict()
            global_id = self._new_export_uuid()
            version = 1
        else:
            if (
                int(row.optimistic_version) != expected_version
                or str(row.snapshot_hash) != str(expected_snapshot_hash)
            ):
                raise ToolingVersionConflict()
            self._validated_preference_snapshot(row)
            global_id = UUID(str(row.global_id))
            version = int(row.optimistic_version) + 1
        now = self._now_export()
        snapshot = {
            "globalId": str(global_id),
            "preferenceKeyHash": key_hash,
            "tenantId": str(project.tenant_id),
            "projectGlobalId": str(project.global_id),
            "actorUserId": self.actor,
            "gridId": TOOLING_LIST_GRID_ID,
            "tableSchemaVersion": TOOLING_LIST_TABLE_SCHEMA_VERSION,
            "viewId": view_id.value,
            "optimisticVersion": version,
            "preference": preference.snapshot_payload(),
            "lastChangedBy": self.actor,
            "lastChangedAt": _utc_text(now),
            "requestId": self.request_id,
            "traceId": self.trace_id,
        }
        values = {
            "preference_key_hash": key_hash,
            "tenant_id": str(project.tenant_id),
            "project_global_id": str(project.global_id),
            "actor_user_id": self.actor,
            "grid_id": TOOLING_LIST_GRID_ID,
            "table_schema_version": TOOLING_LIST_TABLE_SCHEMA_VERSION,
            "view_id": view_id.value,
            "optimistic_version": version,
            "preference_snapshot": _canonical_json(snapshot),
            "snapshot_hash": sha256_json(snapshot),
            "last_changed_by": self.actor,
            "last_changed_at": _database_datetime(now),
            "request_id": self.request_id,
            "trace_id": self.trace_id,
        }
        with tooling_export_write():
            if row is None:
                try:
                    with tooling_preference_validation_diagnostics(
                        self.trace_id,
                        enabled=frappe.get_request_header(
                            "X-NPI-P6-08-Diagnostic"
                        )
                        == PREFERENCE_VALIDATION_DIAGNOSTIC_HEADER,
                    ):
                        try:
                            row = frappe.get_doc(
                                {
                                    "doctype": "NPI Tooling List Preference",
                                    "global_id": str(global_id),
                                    **values,
                                }
                            ).insert()
                        except Exception as error:
                            record_tooling_preference_validation_fallback(error)
                            raise
                except (frappe.DuplicateEntryError, frappe.UniqueValidationError) as error:
                    raise ToolingVersionConflict() from error
            else:
                for fieldname, value in values.items():
                    setattr(row, fieldname, value)
                row.save()
            self._append_audit(
                operation="tooling_list_preference.save",
                global_id=global_id,
                object_version=version,
                summary={
                    "projectGlobalId": str(project.global_id),
                    "viewId": view_id.value,
                    "preferenceSnapshotHash": sha256_json(snapshot),
                },
            )
        return self._public_preference(row)

    def create_tooling_export_package(
        self,
        project_id: UUID,
        *,
        idempotency_key_hash: str,
        mode: ToolingExportMode,
        selection: Sequence[ToolingExportReference] | None,
        filter_spec: ToolingListFilter | None,
        query_snapshot_hash: str | None,
    ) -> ToolingExportCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None or not self._is_internal_system_manager():
            return None
        payload = {
            "mode": mode.value,
            "selection": (
                [reference.snapshot_payload() for reference in selection]
                if selection is not None
                else None
            ),
            "filter": filter_spec.snapshot_payload() if filter_spec else None,
            "querySnapshotHash": query_snapshot_hash,
        }
        context = self._export_command_context(
            project,
            operation=ToolingExportOperation.CREATE,
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(context, dict):
            return ToolingExportCommandOutcome(context, replayed=True)
        receipt_key, payload_hash = context
        rows = self._tooling_list_rows(project)
        if mode is ToolingExportMode.SELECTION:
            if selection is None or filter_spec is not None or query_snapshot_hash is not None:
                raise _mode_error()
            selected = resolve_exact_selection(rows, ToolingExportSelection(tuple(selection)))
            exact_query_hash = None
        else:
            if selection is not None or filter_spec is None or query_snapshot_hash is None:
                raise _mode_error()
            selected = query_tooling_list_rows(rows, filter_spec)
            if not 1 <= len(selected) <= MAX_TOOLING_EXPORT_OBJECTS:
                raise RequestValidationFailed(
                    [
                        {
                            "path": "filter",
                            "message": _(
                                "Narrow the Tooling List filter to between one and one hundred objects."
                            ),
                        }
                    ]
                )
            exact_query_hash = filtered_query_snapshot_hash(filter_spec, rows)
            if exact_query_hash != query_snapshot_hash:
                raise RequestValidationFailed(
                    [
                        {
                            "path": "querySnapshotHash",
                            "message": _("The filtered Tooling List is stale."),
                        }
                    ]
                )
        package_id = self._new_export_uuid()
        now = self._now_export()
        language = ToolingExportLanguage(validate_language_code(get_user_lang(self.actor)))
        identity = ToolingExportPackageIdentity(
            global_id=package_id,
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            actor_user_id=self.actor,
            mode=mode,
            language=language,
            query_snapshot_hash=exact_query_hash,
            references=tuple(row.reference() for row in selected),
            generated_at=now,
            expires_at=now + TOOLING_OBJECT_PACKAGE_VALIDITY,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        try:
            rendered = render_tooling_object_package(
                rows=selected,
                package_global_id=package_id,
                project_global_id=project_id,
                project_code=str(project.business_code),
                actor_user_id=self.actor,
                mode=mode,
                language=language,
                query_snapshot_hash=exact_query_hash,
                generated_at=now,
                expires_at=identity.expires_at,
                translate=lambda source: self._export_translate(source, language.value),
            )
        except (TypeError, ValueError) as error:
            raise RequestValidationFailed(
                [
                    {
                        "path": "export",
                        "message": _("The Tooling object package could not be rendered safely."),
                    }
                ]
            ) from error
        response: dict[str, Any]
        with tooling_export_write():
            receipt = self._insert_export_receipt(
                project,
                receipt_key=receipt_key,
                operation=ToolingExportOperation.CREATE,
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            file_document = self._save_private_package(package_id, rendered)
            self._register_orphan_cleanup(file_document)
            package = self._insert_package(
                project,
                identity=identity,
                rendered=rendered,
                file_document=file_document,
            )
            response = {"package": self._public_package(package)}
            self._append_audit(
                operation=ToolingExportOperation.CREATE.value,
                global_id=package_id,
                object_version=1,
                summary={
                    "projectGlobalId": str(project.global_id),
                    "mode": mode.value,
                    "objectCount": len(selected),
                    "querySnapshotHash": exact_query_hash,
                    "packageSha256": rendered.sha256,
                    "manifestSha256": rendered.manifest_sha256,
                },
            )
            self._seal_export_receipt(
                receipt,
                target_id=package_id,
                response=response,
                now=now,
            )
        return ToolingExportCommandOutcome(response)

    def tooling_export_package_content(
        self,
        project_id: UUID,
        package_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_snapshot_hash: str,
    ) -> ToolingExportBinaryOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None or not self._is_internal_system_manager():
            return None
        package = self._package_for_project(project, package_id)
        if (
            package is None
            or str(package.created_by_user_id).casefold() != self.actor.casefold()
            or str(package.snapshot_hash) != expected_snapshot_hash
        ):
            return None
        now = self._now_export()
        if now >= _datetime(package.expires_at):
            raise ToolingExportExpired()
        payload = {
            "packageGlobalId": str(package_id),
            "expectedSnapshotHash": expected_snapshot_hash,
        }
        context = self._export_command_context(
            project,
            operation=ToolingExportOperation.DOWNLOAD,
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        file_document = frappe.get_doc("File", str(package.frappe_file_id))
        content = self._verified_package_content(package, file_document)
        if isinstance(context, dict):
            return ToolingExportBinaryOutcome(
                content=content,
                file_name=str(package.file_name),
                mime_type=str(package.mime_type),
                replayed=True,
            )
        receipt_key, payload_hash = context
        response = {
            "packageGlobalId": str(package_id),
            "snapshotHash": expected_snapshot_hash,
            "sha256": str(package.sha256),
        }
        with tooling_export_write():
            receipt = self._insert_export_receipt(
                project,
                receipt_key=receipt_key,
                operation=ToolingExportOperation.DOWNLOAD,
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._append_audit(
                operation=ToolingExportOperation.DOWNLOAD.value,
                global_id=package_id,
                object_version=1,
                summary={
                    "projectGlobalId": str(project.global_id),
                    "packageSha256": str(package.sha256),
                    "objectCount": int(package.object_count),
                },
            )
            self._seal_export_receipt(
                receipt,
                target_id=package_id,
                response=response,
                now=now,
            )
        return ToolingExportBinaryOutcome(
            content=content,
            file_name=str(package.file_name),
            mime_type=str(package.mime_type),
        )

    def _tooling_list_rows(self, project: object) -> tuple[ToolingListRow, ...]:
        masters = self._masters(project)
        retained_applicabilities = self._applicabilities(project)
        current_applicabilities = _current_applicabilities(
            retained_applicabilities,
            self._now_export(),
        )
        sets = self._bounded_documents(
            "NPI Tooling Set",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
            },
            maximum=_MAX_PROJECT_SETS,
        )
        revisions = self._bounded_documents(
            "NPI Tooling Revision",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
            },
            maximum=_MAX_PROJECT_REVISIONS,
            order_by="revision_number asc, global_id asc",
        )
        import_bindings = self._bounded_documents(
            "NPI Tooling Import Target Binding",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "target_object_type": "tooling_master",
            },
            maximum=_MAX_IMPORT_BINDINGS,
        )
        result: list[ToolingListRow] = []
        for master in masters:
            master_id = str(master.global_id)
            applications = tuple(
                item
                for item in current_applicabilities
                if str(item.tooling_master_global_id) == master_id
            )
            master_sets = tuple(
                item for item in sets if str(item.tooling_master_global_id) == master_id
            )
            master_revisions = tuple(
                item
                for item in revisions
                if str(item.tooling_master_global_id) == master_id
            )
            bindings = tuple(
                item for item in import_bindings if str(item.target_global_id) == master_id
            )
            source = (
                ToolingSource.CONTROLLED_XLSX_IMPORT if bindings else ToolingSource.MANUAL
            )
            row_hash = sha256_json(
                {
                    "projectGlobalId": str(project.global_id),
                    "toolingMasterGlobalId": master_id,
                    "toolingMasterSnapshotHash": master.snapshot_hash,
                    "applicabilitySnapshots": sorted(item.snapshot_hash for item in applications),
                    "setSnapshots": sorted(str(item.snapshot_hash) for item in master_sets),
                    "revisionSnapshots": sorted(
                        str(item.snapshot_hash) for item in master_revisions
                    ),
                    "source": source.value,
                }
            )
            result.append(
                ToolingListRow(
                    tooling_master_global_id=master.global_id,
                    tooling_master_snapshot_hash=row_hash,
                    title=master.title,
                    project_global_id=UUID(str(project.global_id)),
                    project_code=str(project.business_code),
                    originating_project_global_id=master.originating_project_global_id,
                    applicability_count=len(applications),
                    distinct_part_revision_count=len(
                        {item.part_revision_global_id for item in applications}
                    ),
                    physical_set_count=len(master_sets),
                    design_revision_count=len(master_revisions),
                    latest_revision_number=(
                        max(int(item.revision_number) for item in master_revisions)
                        if master_revisions
                        else None
                    ),
                    customer_owned_set=any(
                        str(item.requirement_kind) == "customer_owned_intake"
                        for item in master_sets
                    ),
                    source=source,
                )
            )
        return tuple(result)

    def _locked_view_project(self, project_id: UUID):
        try:
            project = frappe.get_doc(
                "NPI Engineering Project",
                str(project_id),
                for_update=True,
            )
        except frappe.DoesNotExistError:
            return None
        return project if self._can_view_project(project, project_id) else None

    def _preference_for_key(
        self,
        project: object,
        key_hash: str,
        view_id: ToolingListViewId,
    ):
        name = frappe.db.get_value(
            "NPI Tooling List Preference",
            {"preference_key_hash": key_hash},
            "name",
        )
        if not name:
            return None
        row = frappe.get_doc("NPI Tooling List Preference", str(name))
        if not self._preference_matches(project, row, key_hash, view_id):
            raise RuntimeError("The Tooling List preference scope drifted.")
        return row

    def _locked_preference_for_key(
        self,
        project: object,
        key_hash: str,
        view_id: ToolingListViewId,
    ):
        row = frappe.db.get_value(
            "NPI Tooling List Preference",
            {"preference_key_hash": key_hash},
            ["name"],
            as_dict=True,
            for_update=True,
        )
        if not row:
            return None
        document = frappe.get_doc(
            "NPI Tooling List Preference",
            str(_record_value(row, "name")),
        )
        if not self._preference_matches(project, document, key_hash, view_id):
            raise RuntimeError("The Tooling List preference scope drifted.")
        return document

    def _preference_matches(
        self,
        project: object,
        row: object,
        key_hash: str,
        view_id: ToolingListViewId,
    ) -> bool:
        return not any(
            (
                str(row.preference_key_hash) != key_hash,
                str(row.tenant_id) != str(project.tenant_id),
                str(row.project_global_id) != str(project.global_id),
                str(row.actor_user_id).casefold() != self.actor.casefold(),
                str(row.view_id) != view_id.value,
                str(row.grid_id) != TOOLING_LIST_GRID_ID,
                str(row.table_schema_version) != TOOLING_LIST_TABLE_SCHEMA_VERSION,
            )
        )

    @staticmethod
    def _validated_preference_snapshot(row: object) -> dict[str, object]:
        snapshot = _json_object(row.preference_snapshot)
        if sha256_json(snapshot) != str(row.snapshot_hash):
            raise RuntimeError("The Tooling List preference integrity drifted.")
        expected_fields = {
            "globalId",
            "preferenceKeyHash",
            "tenantId",
            "projectGlobalId",
            "actorUserId",
            "gridId",
            "tableSchemaVersion",
            "viewId",
            "optimisticVersion",
            "preference",
            "lastChangedBy",
            "lastChangedAt",
            "requestId",
            "traceId",
        }
        if set(snapshot) != expected_fields:
            raise RuntimeError("The Tooling List preference projection drifted.")
        try:
            preference = _preference_from_stored_payload(snapshot["preference"])
        except (KeyError, TypeError, ValueError, RequestValidationFailed) as error:
            raise RuntimeError("The Tooling List preference payload is invalid.") from error
        if preference.snapshot_payload() != snapshot["preference"]:
            raise RuntimeError("The Tooling List preference payload is not canonical.")
        return snapshot

    def _public_preference(self, row: object) -> dict[str, object]:
        snapshot = self._validated_preference_snapshot(row)
        if any(
            (
                str(snapshot.get("globalId")) != str(row.global_id),
                int(snapshot.get("optimisticVersion", 0)) != int(row.optimistic_version),
            )
        ):
            raise RuntimeError("The Tooling List preference projection drifted.")
        return {
            "stored": True,
            "globalId": str(row.global_id),
            "optimisticVersion": int(row.optimistic_version),
            "snapshotHash": str(row.snapshot_hash),
            "preference": snapshot["preference"],
        }

    def _export_command_context(
        self,
        project: object,
        *,
        operation: ToolingExportOperation,
        idempotency_key_hash: str,
        payload: Mapping[str, object],
    ) -> tuple[str, str] | dict[str, Any]:
        payload_hash = sha256_json(
            {
                "tenantId": str(project.tenant_id),
                "projectGlobalId": str(project.global_id),
                "actorUserId": self.actor.casefold(),
                "operation": operation.value,
                "payload": dict(payload),
            }
        )
        receipt_key = tooling_export_receipt_key_hash(
            tenant_id=str(project.tenant_id),
            project_global_id=UUID(str(project.global_id)),
            actor_user_id=self.actor,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
        )
        replay = self._export_receipt_replay(
            project,
            receipt_key=receipt_key,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
        )
        return replay if replay is not None else (receipt_key, payload_hash)

    def _export_receipt_replay(
        self,
        project: object,
        *,
        receipt_key: str,
        operation: ToolingExportOperation,
        idempotency_key_hash: str,
        payload_hash: str,
    ) -> dict[str, Any] | None:
        row = frappe.db.get_value(
            "NPI Tooling Export Command Idempotency",
            {"receipt_key_hash": receipt_key},
            [
                "tenant_id",
                "project_global_id",
                "actor_user_id",
                "operation",
                "idempotency_key_hash",
                "payload_hash",
                "target_doctype",
                "target_global_id",
                "response_snapshot",
                "response_hash",
                "sealed",
            ],
            as_dict=True,
            for_update=True,
        )
        if not row:
            return None
        expected = {
            "tenant_id": str(project.tenant_id),
            "project_global_id": str(project.global_id),
            "actor_user_id": self.actor,
            "operation": operation.value,
            "idempotency_key_hash": idempotency_key_hash,
            "payload_hash": payload_hash,
        }
        if any(str(_record_value(row, key)) != value for key, value in expected.items()):
            raise ToolingIdempotencyConflict()
        response = _json_object(_record_value(row, "response_snapshot"))
        if any(
            (
                int(_record_value(row, "sealed") or 0) != 1,
                str(_record_value(row, "target_doctype"))
                != "NPI Tooling Export Package",
                not _record_value(row, "target_global_id"),
                str(_record_value(row, "response_hash")) != sha256_json(response),
            )
        ):
            raise RuntimeError("The Tooling export receipt integrity drifted.")
        try:
            target_id = UUID(str(_record_value(row, "target_global_id")))
        except (TypeError, ValueError) as error:
            raise RuntimeError("The Tooling export receipt target is invalid.") from error
        package = self._package_for_project(project, target_id)
        if (
            package is None
            or str(package.created_by_user_id).casefold() != self.actor.casefold()
        ):
            raise RuntimeError("The Tooling export receipt target is unavailable.")
        expected_response = (
            {"package": self._public_package(package)}
            if operation is ToolingExportOperation.CREATE
            else {
                "packageGlobalId": str(package.global_id),
                "snapshotHash": str(package.snapshot_hash),
                "sha256": str(package.sha256),
            }
        )
        if response != expected_response:
            raise RuntimeError("The Tooling export receipt response drifted.")
        return expected_response

    def _insert_export_receipt(
        self,
        project: object,
        *,
        receipt_key: str,
        operation: ToolingExportOperation,
        idempotency_key_hash: str,
        payload_hash: str,
        now: datetime,
    ):
        try:
            return frappe.get_doc(
                {
                    "doctype": "NPI Tooling Export Command Idempotency",
                    "global_id": str(self._new_export_uuid()),
                    "receipt_key_hash": receipt_key,
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "actor_user_id": self.actor,
                    "operation": operation.value,
                    "idempotency_key_hash": idempotency_key_hash,
                    "payload_hash": payload_hash,
                    "sealed": 0,
                    "created_at": _database_datetime(now),
                    "request_id": self.request_id,
                    "trace_id": self.trace_id,
                }
            ).insert()
        except (frappe.DuplicateEntryError, frappe.UniqueValidationError) as error:
            raise ToolingIdempotencyConflict() from error

    @staticmethod
    def _seal_export_receipt(
        receipt: object,
        *,
        target_id: UUID,
        response: Mapping[str, object],
        now: datetime,
    ) -> None:
        receipt.target_doctype = "NPI Tooling Export Package"
        receipt.target_global_id = str(target_id)
        receipt.response_snapshot = _canonical_json(response)
        receipt.response_hash = sha256_json(response)
        receipt.sealed = 1
        receipt.sealed_at = _database_datetime(now)
        receipt.save()

    @staticmethod
    def _save_private_package(
        package_id: UUID,
        rendered: RenderedToolingObjectPackage,
    ):
        from frappe.utils.file_manager import save_file

        document = save_file(
            rendered.file_name,
            rendered.content,
            "NPI Tooling Export Package",
            str(package_id),
            is_private=1,
        )
        content = document.get_content()
        if not isinstance(content, bytes) or any(
            (
                int(document.is_private or 0) != 1,
                str(document.file_name) != rendered.file_name,
                len(content) != rendered.size_bytes,
                hashlib.sha256(content).hexdigest() != rendered.sha256,
            )
        ):
            raise ToolingReferenceUnavailable()
        return document

    def _insert_package(
        self,
        project: object,
        *,
        identity: ToolingExportPackageIdentity,
        rendered: RenderedToolingObjectPackage,
        file_document: object,
    ):
        snapshot = {
            "globalId": str(identity.global_id),
            "tenantId": identity.tenant_id,
            "projectGlobalId": str(identity.project_global_id),
            "createdByUserId": identity.actor_user_id,
            "mode": identity.mode.value,
            "language": identity.language.value,
            "confidentialityClass": TOOLING_OBJECT_PACKAGE_CONFIDENTIALITY,
            "objectCount": len(identity.references),
            "querySnapshotHash": identity.query_snapshot_hash,
            "objectRefs": [item.snapshot_payload() for item in identity.references],
            "generatedAt": _utc_text(identity.generated_at),
            "expiresAt": _utc_text(identity.expires_at),
            "frappeFileId": str(file_document.name),
            "fileName": rendered.file_name,
            "mimeType": rendered.mime_type,
            "sizeBytes": rendered.size_bytes,
            "sha256": rendered.sha256,
            "manifestSha256": rendered.manifest_sha256,
            "requestId": str(identity.request_id),
            "traceId": identity.trace_id,
        }
        return frappe.get_doc(
            {
                "doctype": "NPI Tooling Export Package",
                "global_id": str(identity.global_id),
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "created_by_user_id": self.actor,
                "mode": identity.mode.value,
                "language": identity.language.value,
                "confidentiality_class": TOOLING_OBJECT_PACKAGE_CONFIDENTIALITY,
                "object_count": len(identity.references),
                "query_snapshot_hash": identity.query_snapshot_hash,
                "object_refs": _canonical_json(snapshot["objectRefs"]),
                "generated_at": _database_datetime(identity.generated_at),
                "expires_at": _database_datetime(identity.expires_at),
                "frappe_file_id": str(file_document.name),
                "file_name": rendered.file_name,
                "mime_type": rendered.mime_type,
                "size_bytes": rendered.size_bytes,
                "sha256": rendered.sha256,
                "manifest_sha256": rendered.manifest_sha256,
                "package_snapshot": _canonical_json(snapshot),
                "snapshot_hash": sha256_json(snapshot),
                "request_id": self.request_id,
                "trace_id": self.trace_id,
            }
        ).insert()

    def _package_for_project(self, project: object, package_id: UUID):
        try:
            row = frappe.get_doc("NPI Tooling Export Package", str(package_id))
        except frappe.DoesNotExistError:
            return None
        if any(
            (
                str(row.global_id) != str(package_id),
                str(row.tenant_id) != str(project.tenant_id),
                str(row.project_global_id) != str(project.global_id),
            )
        ):
            return None
        _validated_package_snapshot(row)
        return row

    @staticmethod
    def _public_package(row: object) -> dict[str, object]:
        _validated_package_snapshot(row)
        return {
            "globalId": str(row.global_id),
            "projectGlobalId": str(row.project_global_id),
            "createdByUserId": str(row.created_by_user_id),
            "mode": str(row.mode),
            "language": str(row.language),
            "confidentialityClass": str(row.confidentiality_class),
            "objectCount": int(row.object_count),
            "querySnapshotHash": row.query_snapshot_hash or None,
            "objectRefs": _json_array(row.object_refs),
            "generatedAt": _utc_text(_datetime(row.generated_at)),
            "expiresAt": _utc_text(_datetime(row.expires_at)),
            "fileName": str(row.file_name),
            "mimeType": str(row.mime_type),
            "sizeBytes": int(row.size_bytes),
            "sha256": str(row.sha256),
            "manifestSha256": str(row.manifest_sha256),
            "snapshotHash": str(row.snapshot_hash),
        }

    @staticmethod
    def _verified_package_content(package: object, file_document: object) -> bytes:
        content = file_document.get_content()
        if not isinstance(content, bytes) or any(
            (
                int(file_document.is_private or 0) != 1,
                str(file_document.name) != str(package.frappe_file_id),
                str(file_document.file_name) != str(package.file_name),
                int(file_document.file_size or 0) != len(content),
                len(content) != int(package.size_bytes),
                hashlib.sha256(content).hexdigest() != str(package.sha256),
            )
        ):
            raise ToolingReferenceUnavailable()
        return content

    @staticmethod
    def _register_orphan_cleanup(file_document: object) -> None:
        file_url = str(file_document.file_url)
        parsed = PurePosixPath(file_url)
        if (
            not file_url.startswith("/private/files/")
            or len(parsed.parts) != 4
            or parsed.parts[:3] != ("/", "private", "files")
            or parsed.name in {"", ".", ".."}
        ):
            raise ToolingReferenceUnavailable()
        private_directory = Path(frappe.get_site_path("private", "files")).resolve()
        file_path = (private_directory / parsed.name).resolve()
        if file_path.parent != private_directory:
            raise ToolingReferenceUnavailable()

        def cleanup_after_rollback() -> None:
            try:
                remaining = frappe.db.get_value(
                    "File",
                    {"file_url": file_url},
                    "name",
                )
                if not remaining:
                    file_path.unlink(missing_ok=True)
            except Exception as error:
                from npi_core.api import record_safe_diagnostic

                record_safe_diagnostic(
                    code="TOOLING_EXPORT_ORPHAN_FILE_CLEANUP_FAILED",
                    title="NPI Tooling export orphan file cleanup failed",
                    exception_type=type(error).__name__,
                )

        frappe.db.after_rollback.add(cleanup_after_rollback)

    def _now_export(self) -> datetime:
        value = self._export_clock()
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise RuntimeError("The Tooling export clock must be timezone-aware.")
        return value.astimezone(UTC)

    def _new_export_uuid(self) -> UUID:
        value = self._export_uuid_factory()
        return value if isinstance(value, UUID) else UUID(str(value))


def _current_applicabilities(values: Sequence[object], now: datetime) -> tuple[object, ...]:
    latest: dict[UUID, object] = {}
    for value in values:
        current = latest.get(value.relationship_global_id)
        if current is None or value.applicability_version > current.applicability_version:
            latest[value.relationship_global_id] = value
    today = now.date()
    return tuple(
        value
        for value in latest.values()
        if value.effective_from <= today
        and (value.effective_to is None or today < value.effective_to)
    )


def _public_row(row: ToolingListRow) -> dict[str, object]:
    return {
        "toolingMasterGlobalId": str(row.tooling_master_global_id),
        "toolingMasterSnapshotHash": row.tooling_master_snapshot_hash,
        "title": row.title,
        "projectGlobalId": str(row.project_global_id),
        "projectCode": row.project_code,
        "originatingProjectGlobalId": str(row.originating_project_global_id),
        "applicabilityCount": row.applicability_count,
        "distinctPartRevisionCount": row.distinct_part_revision_count,
        "physicalSetCount": row.physical_set_count,
        "designRevisionCount": row.design_revision_count,
        "latestRevisionNumber": row.latest_revision_number,
        "customerOwnedSet": row.customer_owned_set,
        "source": row.source.value,
    }


def _mode_error() -> RequestValidationFailed:
    return RequestValidationFailed(
        [
            {
                "path": "mode",
                "message": _("Choose either an exact selection or the current filtered result."),
            }
        ]
    )


def _record_value(record: object, fieldname: str) -> object:
    if isinstance(record, Mapping):
        return record.get(fieldname)
    return getattr(record, fieldname, None)


def _json_object(value: object) -> dict[str, Any]:
    parsed = frappe.parse_json(value)
    if not isinstance(parsed, dict):
        raise RuntimeError("The stored Tooling export JSON object is invalid.")
    return parsed


def _json_array(value: object) -> list[object]:
    parsed = frappe.parse_json(value)
    if not isinstance(parsed, list):
        raise RuntimeError("The stored Tooling export JSON array is invalid.")
    return parsed


def _preference_from_stored_payload(value: object) -> ToolingListPreferenceSnapshot:
    if not isinstance(value, Mapping):
        raise TypeError("The stored Tooling List preference must be an object.")
    payload = dict(value)
    expected_fields = {
        "gridId",
        "tableSchemaVersion",
        "viewId",
        "filter",
        "columnOrder",
        "hiddenColumns",
        "columnWidths",
    }
    if set(payload) != expected_fields:
        raise ValueError("The stored Tooling List preference fields are invalid.")
    filter_payload = payload["filter"]
    if not isinstance(filter_payload, Mapping) or set(filter_payload) != {
        "viewId",
        "search",
        "sortKey",
        "sortDirection",
        "groupKey",
    }:
        raise ValueError("The stored Tooling List filter fields are invalid.")
    widths = payload["columnWidths"]
    if not isinstance(widths, Sequence) or isinstance(widths, (str, bytes, bytearray)):
        raise TypeError("The stored Tooling List widths must be a list.")
    normalized_widths: list[tuple[str, int]] = []
    for width in widths:
        if not isinstance(width, Mapping) or set(width) != {"columnId", "width"}:
            raise ValueError("The stored Tooling List width fields are invalid.")
        normalized_widths.append((width["columnId"], width["width"]))
    column_order = payload["columnOrder"]
    hidden_columns = payload["hiddenColumns"]
    if (
        not isinstance(column_order, Sequence)
        or isinstance(column_order, (str, bytes, bytearray))
        or not isinstance(hidden_columns, Sequence)
        or isinstance(hidden_columns, (str, bytes, bytearray))
    ):
        raise TypeError("The stored Tooling List columns must be lists.")
    view_id = ToolingListViewId(payload["viewId"])
    return ToolingListPreferenceSnapshot(
        view_id=view_id,
        filter_spec=ToolingListFilter(
            view_id=ToolingListViewId(filter_payload["viewId"]),
            search=filter_payload["search"],
            sort_key=ToolingListSortKey(filter_payload["sortKey"]),
            sort_direction=ToolingListSortDirection(filter_payload["sortDirection"]),
            group_key=ToolingListGroupKey(filter_payload["groupKey"]),
        ),
        column_order=tuple(column_order),
        hidden_columns=tuple(hidden_columns),
        column_widths=tuple(normalized_widths),
        grid_id=payload["gridId"],
        table_schema_version=payload["tableSchemaVersion"],
    )


def _validated_package_snapshot(row: object) -> dict[str, object]:
    snapshot = _json_object(row.package_snapshot)
    expected = {
        "globalId": str(row.global_id),
        "tenantId": str(row.tenant_id),
        "projectGlobalId": str(row.project_global_id),
        "createdByUserId": str(row.created_by_user_id),
        "mode": str(row.mode),
        "language": str(row.language),
        "confidentialityClass": str(row.confidentiality_class),
        "objectCount": int(row.object_count),
        "querySnapshotHash": row.query_snapshot_hash or None,
        "objectRefs": _json_array(row.object_refs),
        "generatedAt": _utc_text(_datetime(row.generated_at)),
        "expiresAt": _utc_text(_datetime(row.expires_at)),
        "frappeFileId": str(row.frappe_file_id),
        "fileName": str(row.file_name),
        "mimeType": str(row.mime_type),
        "sizeBytes": int(row.size_bytes),
        "sha256": str(row.sha256),
        "manifestSha256": str(row.manifest_sha256),
        "requestId": str(row.request_id),
        "traceId": str(row.trace_id),
    }
    if snapshot != expected or sha256_json(snapshot) != str(row.snapshot_hash):
        raise RuntimeError("The Tooling export package integrity drifted.")
    return snapshot


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _datetime(value: object) -> datetime:
    from frappe.utils import get_datetime

    parsed = get_datetime(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _database_datetime(value: datetime) -> str:
    return value.astimezone(UTC).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S.%f")


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
