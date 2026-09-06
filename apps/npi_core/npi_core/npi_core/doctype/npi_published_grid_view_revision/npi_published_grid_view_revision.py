from __future__ import annotations

import json
from uuid import UUID

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.grid_personalization.domain import (
    GRID_ID,
    PROJECT_PERMISSION_BOUNDARY,
    TABLE_SCHEMA_VERSION,
    GridPersonalizationValidationError,
    PublishedGridViewDefinition,
    canonical_hash,
    canonical_json,
)
from npi_core.grid_personalization.frappe_validation import (
    canonical_utc_datetime_text,
    deny_grid_personalization_delete,
    frappe_utc_datetime_text,
    normalize_uuid_fields,
    require_actor,
    require_grid_personalization_write,
    require_hash,
    require_positive_integer,
    require_reason_code,
    require_tenant_id,
    require_trace_id,
    throw_domain_validation,
)
from npi_core.project.frappe_validation import ensure_uuid


class NPIPublishedGridViewRevision(Document):
    def before_insert(self) -> None:
        require_grid_personalization_write()

    def before_save(self) -> None:
        require_grid_personalization_write()
        if self.get_doc_before_save() is not None:
            frappe.throw(
                _("A published grid view revision cannot be changed."),
                frappe.PermissionError,
            )

    def on_trash(self) -> None:
        deny_grid_personalization_delete()

    def validate(self) -> None:
        normalize_uuid_fields(
            self,
            (
                "global_id",
                "published_view_global_id",
                "project_global_id",
                "prior_revision_global_id",
                "restored_from_revision_global_id",
            ),
        )
        revision_number = require_positive_integer(
            self.revision_number,
            _("Revision Number"),
        )
        expected_key = f"{self.published_view_global_id}:{revision_number}"
        if self.revision_key != expected_key:
            frappe.throw(
                _("Revision Key does not match its identities."),
                frappe.ValidationError,
            )
        self.tenant_id = require_tenant_id(self.tenant_id)
        if self.grid_id != GRID_ID or self.table_schema_version != (
            TABLE_SCHEMA_VERSION
        ):
            frappe.throw(
                _("Select the supported My Work grid schema."),
                frappe.ValidationError,
            )
        if self.permission_boundary != PROJECT_PERMISSION_BOUNDARY:
            frappe.throw(
                _("Select the supported Project permission boundary."),
                frappe.ValidationError,
            )
        self._validate_lineage(revision_number)
        if (
            not isinstance(self.view_name, str)
            or not self.view_name.strip()
            or len(self.view_name.strip()) > 140
        ):
            frappe.throw(
                _("Published View Name must be valid text."),
                frappe.ValidationError,
            )
        self.view_name = self.view_name.strip()
        description = self.description or ""
        if not isinstance(description, str) or len(description.strip()) > 1000:
            frappe.throw(
                _("Published View Description must be valid text."),
                frappe.ValidationError,
            )
        self.description = description.strip()
        try:
            definition_value = (
                json.loads(self.definition_snapshot)
                if isinstance(self.definition_snapshot, str)
                else self.definition_snapshot
            )
            definition = PublishedGridViewDefinition.parse(definition_value)
        except (
            GridPersonalizationValidationError,
            TypeError,
            json.JSONDecodeError,
        ) as error:
            throw_domain_validation(error)
            return
        if definition.filter.project_id not in (
            None,
            UUID(self.project_global_id),
        ):
            frappe.throw(
                _(
                    "A published grid view filter must stay within its Project boundary."
                ),
                frappe.ValidationError,
            )
        definition_snapshot = definition.canonical_dict()
        expected_definition_hash = canonical_hash(definition_snapshot)
        if self.definition_hash != expected_definition_hash:
            frappe.throw(
                _("Definition Hash does not match its canonical snapshot."),
                frappe.ValidationError,
            )
        self.definition_snapshot = canonical_json(definition_snapshot)
        self.definition_hash = expected_definition_hash
        self.published_by = require_actor(self.published_by, _("Published By"))
        self.authority_reason_code = require_reason_code(
            self.authority_reason_code
        )
        authority_evidence = self._json_object(
            self.authority_evidence,
            _("Authority Evidence"),
        )
        self.authority_evidence = canonical_json(authority_evidence)
        self.request_id = ensure_uuid(self.request_id, _("Request ID"))
        self.trace_id = require_trace_id(self.trace_id)
        self.published_at = frappe_utc_datetime_text(
            self.published_at,
            _("Published At"),
        )
        snapshot = self._revision_snapshot(
            definition_snapshot,
            authority_evidence,
        )
        expected_snapshot_hash = canonical_hash(snapshot)
        supplied_snapshot = self._json_object(
            self.revision_snapshot,
            _("Revision Snapshot"),
        )
        if supplied_snapshot != snapshot or self.snapshot_hash != (
            expected_snapshot_hash
        ):
            frappe.throw(
                _("Revision Snapshot Hash does not match its canonical snapshot."),
                frappe.ValidationError,
            )
        self.revision_snapshot = canonical_json(snapshot)
        self.snapshot_hash = expected_snapshot_hash

    def _validate_lineage(self, revision_number: int) -> None:
        prior_values = (
            self.prior_revision_global_id,
            self.prior_revision_number,
            self.prior_revision_snapshot_hash,
        )
        if revision_number == 1:
            if any(value not in (None, "", 0) for value in prior_values):
                frappe.throw(
                    _("The first published view revision cannot have a prior revision."),
                    frappe.ValidationError,
                )
        else:
            if (
                not self.prior_revision_global_id
                or type(self.prior_revision_number) is not int
                or int(self.prior_revision_number) != revision_number - 1
            ):
                frappe.throw(
                    _("Select the exact preceding published view revision."),
                    frappe.ValidationError,
                )
            self.prior_revision_snapshot_hash = require_hash(
                self.prior_revision_snapshot_hash,
                _("Prior Revision Snapshot Hash"),
            )
        restored_values = (
            self.restored_from_revision_global_id,
            self.restored_from_revision_number,
            self.restored_from_revision_snapshot_hash,
        )
        populated = tuple(value not in (None, "", 0) for value in restored_values)
        if any(populated) and not all(populated):
            frappe.throw(
                _("Restored revision evidence must be complete."),
                frappe.ValidationError,
            )
        if all(populated):
            if (
                type(self.restored_from_revision_number) is not int
                or int(self.restored_from_revision_number) >= revision_number
            ):
                frappe.throw(
                    _("Select an earlier published view revision to restore."),
                    frappe.ValidationError,
                )
            self.restored_from_revision_snapshot_hash = require_hash(
                self.restored_from_revision_snapshot_hash,
                _("Restored From Revision Snapshot Hash"),
            )

    def _revision_snapshot(
        self,
        definition: dict[str, object],
        authority_evidence: dict[str, object],
    ) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "globalId": self.global_id,
            "publishedViewId": self.published_view_global_id,
            "tenantId": self.tenant_id,
            "projectId": self.project_global_id,
            "gridId": self.grid_id,
            "tableSchemaVersion": self.table_schema_version,
            "revisionNumber": int(self.revision_number),
            "priorRevision": self._reference("prior"),
            "restoredFromRevision": self._reference("restored_from"),
            "name": self.view_name,
            "description": self.description,
            "permissionBoundary": self.permission_boundary,
            "definition": definition,
            "definitionHash": self.definition_hash,
            "publishedBy": self.published_by,
            "publishedAt": self._datetime_text(self.published_at),
            "authorityReasonCode": self.authority_reason_code,
            "authorityEvidence": authority_evidence,
            "requestId": self.request_id,
            "traceId": self.trace_id,
        }

    def _reference(self, prefix: str) -> dict[str, object] | None:
        global_id = self.get(f"{prefix}_revision_global_id")
        if not global_id:
            return None
        return {
            "globalId": global_id,
            "revisionNumber": int(self.get(f"{prefix}_revision_number")),
            "snapshotHash": self.get(f"{prefix}_revision_snapshot_hash"),
        }

    @staticmethod
    def _json_object(value: object, label: str) -> dict[str, object]:
        try:
            parsed = json.loads(value) if isinstance(value, str) else value
        except (TypeError, json.JSONDecodeError):
            parsed = None
        if not isinstance(parsed, dict):
            frappe.throw(
                _("{field} must be a JSON object.").format(field=label),
                frappe.ValidationError,
            )
        return parsed

    @staticmethod
    def _datetime_text(value: object) -> str:
        return canonical_utc_datetime_text(value, _("Published At"))
