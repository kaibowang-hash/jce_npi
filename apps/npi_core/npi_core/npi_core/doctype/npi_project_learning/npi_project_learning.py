from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.project_controls.frappe_validation import (
    canonical_datetime,
    canonicalize_json,
    deny_project_control_history_delete,
    normalize_uuid_fields,
    require_actor,
    require_hash,
    require_positive_integer,
    require_project_control_write,
    require_request_id,
    require_snapshot_hash,
    require_text,
    require_trace_id,
)


_KINDS = {"retrospective", "lesson", "template_improvement"}


class NPIProjectLearning(Document):
    def before_insert(self) -> None:
        require_project_control_write()

    def before_save(self) -> None:
        require_project_control_write()
        if self.get_doc_before_save() is not None:
            frappe.throw(
                _("A Project Learning record is immutable."),
                frappe.PermissionError,
            )

    def on_trash(self) -> None:
        deny_project_control_history_delete()

    def validate(self) -> None:
        normalize_uuid_fields(
            self,
            ("global_id", "project_global_id", "template_global_id"),
        )
        if not self.tenant_id:
            frappe.throw(_("Tenant ID is required."), frappe.ValidationError)
        if self.kind not in _KINDS:
            frappe.throw(
                _("Select a supported Project learning kind."),
                frappe.ValidationError,
            )
        self.title = require_text(
            self.title,
            _("Project Learning Title"),
            maximum=280,
        )
        self.content = require_text(
            self.content,
            _("Project Learning Content"),
            maximum=4000,
        )
        self.recommendation = require_text(
            self.recommendation or "",
            _("Project Learning Recommendation"),
            maximum=4000,
            allow_empty=True,
        )
        tags, self.tags = canonicalize_json(
            self.tags,
            expected_type=list,
            label=_("Project Learning Tags"),
        )
        normalized_tags = _validate_tags(tags)
        if normalized_tags != tags:
            from npi_core.project.frappe_validation import canonical_json

            self.tags = canonical_json(normalized_tags)
        require_positive_integer(
            self.template_version,
            _("Template Version"),
        )
        self.template_snapshot_hash = require_hash(
            self.template_snapshot_hash,
            _("Template Snapshot Hash"),
        )
        self.created_by = require_actor(self.created_by, _("Created By"))
        self.optimistic_version = 1
        self.request_id = require_request_id(self.request_id)
        self.trace_id = require_trace_id(self.trace_id)
        snapshot, self.record_snapshot = canonicalize_json(
            self.record_snapshot,
            expected_type=dict,
            label=_("Project Learning Snapshot"),
        )
        self.snapshot_hash = require_snapshot_hash(
            snapshot,
            self.snapshot_hash,
            _("Snapshot Hash"),
        )
        required = {
            "schemaVersion",
            "globalId",
            "tenantId",
            "projectGlobalId",
            "kind",
            "title",
            "content",
            "recommendation",
            "tags",
            "templateGlobalId",
            "templateVersion",
            "templateSnapshotHash",
            "createdBy",
            "createdAt",
            "requestId",
            "traceId",
        }
        if (
            set(snapshot) != required
            or snapshot.get("schemaVersion") != 1
            or snapshot.get("globalId") != self.global_id
            or snapshot.get("tenantId") != self.tenant_id
            or snapshot.get("projectGlobalId") != self.project_global_id
            or snapshot.get("kind") != self.kind
            or snapshot.get("title") != self.title
            or snapshot.get("content") != self.content
            or snapshot.get("recommendation") != self.recommendation
            or snapshot.get("tags") != normalized_tags
            or snapshot.get("templateGlobalId") != self.template_global_id
            or snapshot.get("templateVersion") != self.template_version
            or snapshot.get("templateSnapshotHash")
            != self.template_snapshot_hash
            or require_actor(snapshot.get("createdBy"), _("Created By"))
            != self.created_by
            or canonical_datetime(
                snapshot.get("createdAt"),
                _("Created At"),
            )
            != canonical_datetime(self.created_at, _("Created At"))
            or snapshot.get("requestId") != self.request_id
            or snapshot.get("traceId") != self.trace_id
        ):
            frappe.throw(
                _("Project Learning Snapshot does not match the record."),
                frappe.ValidationError,
            )


def _validate_tags(value: list[object]) -> list[str]:
    if len(value) > 20:
        frappe.throw(
            _("Add no more than twenty Project learning tags."),
            frappe.ValidationError,
        )
    normalized: list[str] = []
    for tag in value:
        if not isinstance(tag, str) or not tag.strip() or len(tag.strip()) > 64:
            frappe.throw(
                _("Enter valid Project learning tags."),
                frappe.ValidationError,
            )
        normalized.append(tag.strip())
    if len(set(normalized)) != len(normalized):
        frappe.throw(
            _("Project learning tags must be unique."),
            frappe.ValidationError,
        )
    return sorted(normalized, key=str.casefold)
