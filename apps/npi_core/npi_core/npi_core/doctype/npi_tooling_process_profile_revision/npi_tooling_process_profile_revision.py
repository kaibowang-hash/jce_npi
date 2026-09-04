from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    canonical_json,
    canonical_uuid,
    frappe_utc_datetime_text,
    json_array,
    json_object,
    lowercase_sha256,
    optional_uuid,
    require_exact_parent,
    tenant_text,
)
from npi_core.tooling.engineering_controls_domain import (
    ToolingProcessContextKind,
    ToolingProcessLayer,
    process_profile_from_snapshot,
    validate_process_profile_successor,
)
from npi_core.tooling.frappe_validation import (
    deny_tooling_history_delete,
    deny_tooling_history_update,
    require_tooling_command_write,
    tooling_domain_value,
)


class NPIToolingProcessProfileRevision(Document):
    """Immutable and source-separated Tooling process profile revision."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_tooling_command_write()

    def before_save(self) -> None:
        require_tooling_command_write()
        if self.get_doc_before_save() is not None:
            deny_tooling_history_update()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("profile_global_id", _("Process Profile Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("tooling_master_global_id", _("Tooling Master Global ID")),
            ("tooling_revision_global_id", _("Tooling Revision Global ID")),
            ("request_id", _("Request ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.predecessor_global_id = optional_uuid(
            self.predecessor_global_id,
            _("Predecessor Process Profile Global ID"),
        )
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_tooling_history_update()
        supplied = json_object(
            self.profile_snapshot,
            _("Tooling Process Profile Revision Snapshot"),
        )
        value = tooling_domain_value(lambda: process_profile_from_snapshot(supplied))
        expected = (
            str(value.global_id), str(value.profile_global_id), value.tenant_id,
            str(value.project_global_id), str(value.tooling_master_global_id),
            str(value.tooling_revision_global_id), value.tooling_revision_snapshot_hash,
            value.layer.value, value.profile_version,
            str(value.predecessor_global_id) if value.predecessor_global_id else None,
            value.predecessor_snapshot_hash, value.effective_from.isoformat(),
            str(value.request_id), value.trace_id,
        )
        actual = (
            self.global_id, self.profile_global_id, self.tenant_id,
            self.project_global_id, self.tooling_master_global_id,
            self.tooling_revision_global_id, self.tooling_revision_snapshot_hash,
            self.layer, self.profile_version, self.predecessor_global_id,
            self.predecessor_snapshot_hash or None, str(self.effective_from),
            self.request_id, self.trace_id,
        )
        if actual != expected:
            frappe.throw(
                _("Tooling Process Profile Revision fields do not match the exact snapshot."),
                frappe.ValidationError,
            )
        if self.version_key_hash not in (None, "", value.version_key_hash):
            frappe.throw(_("Process Profile Version Key Hash does not match."), frappe.ValidationError)
        if self.snapshot_hash not in (None, "", value.snapshot_hash):
            frappe.throw(_("Tooling Process Profile Revision Snapshot Hash does not match."), frappe.ValidationError)
        if json_object(self.context_snapshot, _("Process Source Context Snapshot")) != value.context.snapshot_payload():
            frappe.throw(_("Process Source Context Snapshot does not match."), frappe.ValidationError)
        if json_array(self.metric_snapshot, _("Process Metric Snapshot")) != [item.snapshot_payload() for item in value.metrics]:
            frappe.throw(_("Process Metric Snapshot does not match."), frappe.ValidationError)
        require_exact_parent(
            "NPI Tooling Master",
            str(value.tooling_master_global_id),
            {"global_id": str(value.tooling_master_global_id), "tenant_id": value.tenant_id},
            _("The Tooling Master is unavailable for this process profile."),
        )
        require_exact_parent(
            "NPI Tooling Revision",
            str(value.tooling_revision_global_id),
            {
                "global_id": str(value.tooling_revision_global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "tooling_master_global_id": str(value.tooling_master_global_id),
                "snapshot_hash": value.tooling_revision_snapshot_hash,
            },
            _("The Tooling Revision is unavailable for this process profile."),
        )
        if value.predecessor_global_id is not None:
            predecessor = require_exact_parent(
                "NPI Tooling Process Profile Revision",
                str(value.predecessor_global_id),
                {
                    "global_id": str(value.predecessor_global_id),
                    "profile_global_id": str(value.profile_global_id),
                    "tenant_id": value.tenant_id,
                    "project_global_id": str(value.project_global_id),
                    "tooling_master_global_id": str(value.tooling_master_global_id),
                    "snapshot_hash": value.predecessor_snapshot_hash,
                },
                _("The predecessor Process Profile Revision is unavailable."),
                extra_fields=("profile_snapshot",),
            )
            current = tooling_domain_value(
                lambda: process_profile_from_snapshot(
                    json_object(predecessor["profile_snapshot"], _("Tooling Process Profile Revision Snapshot"))
                )
            )
            tooling_domain_value(lambda: validate_process_profile_successor(current, value))
        _require_context(value)
        self.tooling_master = str(value.tooling_master_global_id)
        self.tooling_revision = str(value.tooling_revision_global_id)
        self.version_key_hash = value.version_key_hash
        self.reason = value.reason
        self.created_by_user_id = value.created_by_user_id
        self.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
        self.context_snapshot = canonical_json(value.context.snapshot_payload())
        self.metric_snapshot = canonical_json([item.snapshot_payload() for item in value.metrics])
        self.profile_snapshot = canonical_json(value.snapshot_payload())
        self.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))

    def on_trash(self) -> None:
        deny_tooling_history_delete(self)


def _require_context(value) -> None:
    context = value.context
    if context.kind is ToolingProcessContextKind.TOOLING_REVISION_SPECIFICATION:
        if (
            context.global_id != value.tooling_revision_global_id
            or context.snapshot_hash != value.tooling_revision_snapshot_hash
        ):
            frappe.throw(_("Process source context does not match the Tooling Revision."), frappe.ValidationError)
        return
    if context.kind is ToolingProcessContextKind.RELEASED_DOCUMENT:
        evidence = context.released_document
        if evidence is None:
            frappe.throw(_("Released Document context requires exact release evidence."), frappe.ValidationError)
        require_exact_parent(
            "NPI Document Revision",
            str(evidence.revision_global_id),
            {
                "global_id": str(evidence.revision_global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "snapshot_hash": evidence.revision_snapshot_hash,
            },
            _("The process source Document Revision is unavailable."),
        )
        lifecycle = require_exact_parent(
            "NPI Document Revision Lifecycle",
            str(evidence.lifecycle_global_id),
            {
                "global_id": str(evidence.lifecycle_global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "revision_global_id": str(evidence.revision_global_id),
                "lifecycle_version": evidence.lifecycle_version,
                "current_state": "released",
                "last_event_global_id": str(evidence.release_event_global_id),
                "release_snapshot_hash": evidence.release_snapshot_hash,
            },
            _("The process source Document is not currently released."),
        )
        if lifecycle is None:
            frappe.throw(_("The process source Document is not currently released."), frappe.ValidationError)
        require_exact_parent(
            "NPI Document Lifecycle Event",
            str(evidence.release_event_global_id),
            {
                "global_id": str(evidence.release_event_global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "revision_global_id": str(evidence.revision_global_id),
                "event_hash": evidence.release_event_hash,
                "to_state": "released",
                "to_version": evidence.lifecycle_version,
            },
            _("The process source Document release event is unavailable."),
        )
        return
    if value.layer is ToolingProcessLayer.CUSTOMER_STANDARD:
        frappe.throw(_("Customer Standard requires a released source."), frappe.ValidationError)
    if not frappe.db.exists("DocType", "NPI Trial Round"):
        frappe.throw(_("Trial process evidence is unavailable in this phase."), frappe.ValidationError)
    require_exact_parent(
        "NPI Trial Round",
        str(context.global_id),
        {
            "global_id": str(context.global_id),
            "tenant_id": value.tenant_id,
            "project_global_id": str(value.project_global_id),
            "snapshot_hash": context.snapshot_hash,
        },
        _("The exact Trial process evidence is unavailable."),
    )
