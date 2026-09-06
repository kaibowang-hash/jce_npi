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
from npi_core.tooling.frappe_validation import (
    deny_tooling_history_delete,
    deny_tooling_history_update,
    require_tooling_command_write,
    tooling_domain_value,
)
from npi_core.tooling.revision_domain import tooling_revision_from_snapshot


class NPIToolingRevision(Document):
    """Immutable unit-bearing Tooling engineering revision."""

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
            ("project_global_id", _("Project Global ID")),
            ("tooling_master_global_id", _("Tooling Master Global ID")),
            ("request_id", _("Request ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.predecessor_global_id = optional_uuid(
            self.predecessor_global_id,
            _("Predecessor Tooling Revision Global ID"),
        )
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_tooling_history_update()
        supplied = json_object(self.revision_snapshot, _("Tooling Revision Snapshot"))
        value = tooling_domain_value(lambda: tooling_revision_from_snapshot(supplied))
        expected = (
            str(value.global_id),
            value.tenant_id,
            str(value.project_global_id),
            str(value.tooling_master_global_id),
            value.revision_number,
            value.revision_label,
            str(value.predecessor_global_id) if value.predecessor_global_id else None,
            value.predecessor_snapshot_hash,
            str(value.request_id),
            value.trace_id,
        )
        actual = (
            self.global_id,
            self.tenant_id,
            self.project_global_id,
            self.tooling_master_global_id,
            self.revision_number,
            self.revision_label,
            self.predecessor_global_id,
            self.predecessor_snapshot_hash or None,
            self.request_id,
            self.trace_id,
        )
        if actual != expected:
            frappe.throw(
                _("Tooling Revision fields do not match the exact snapshot."),
                frappe.ValidationError,
            )
        if self.revision_key_hash not in (None, "", value.revision_key_hash):
            frappe.throw(
                _("Tooling Revision Key Hash does not match the exact revision."),
                frappe.ValidationError,
            )
        if self.snapshot_hash not in (None, "", value.snapshot_hash):
            frappe.throw(
                _("Tooling Revision Snapshot Hash does not match."),
                frappe.ValidationError,
            )
        for field_value, expected_value, label in (
            (
                json_object(self.specification_snapshot, _("Tooling Specification Snapshot")),
                value.specification.snapshot_payload(),
                _("Tooling Specification Snapshot"),
            ),
            (
                json_array(self.cavity_snapshot, _("Cavity Snapshot")),
                [item.snapshot_payload() for item in value.cavities],
                _("Cavity Snapshot"),
            ),
            (
                json_array(self.insert_snapshot, _("Insert Snapshot")),
                [item.snapshot_payload() for item in value.inserts],
                _("Insert Snapshot"),
            ),
            (
                json_array(self.external_identity_snapshot, _("External Identity Snapshot")),
                [item.snapshot_payload() for item in value.external_identities],
                _("External Identity Snapshot"),
            ),
            (
                json_array(
                    self.design_document_revision_snapshot,
                    _("Design Document Revision Snapshot"),
                ),
                [item.snapshot_payload() for item in value.design_document_revisions],
                _("Design Document Revision Snapshot"),
            ),
        ):
            if field_value != expected_value:
                frappe.throw(
                    _("{field} does not match the exact Tooling Revision.").format(
                        field=label
                    ),
                    frappe.ValidationError,
                )
        require_exact_parent(
            "NPI Tooling Master",
            str(value.tooling_master_global_id),
            {
                "global_id": str(value.tooling_master_global_id),
                "tenant_id": value.tenant_id,
            },
            _("The Tooling Master is unavailable for this revision."),
        )
        if value.predecessor_global_id is not None:
            require_exact_parent(
                "NPI Tooling Revision",
                str(value.predecessor_global_id),
                {
                    "global_id": str(value.predecessor_global_id),
                    "tenant_id": value.tenant_id,
                    "project_global_id": str(value.project_global_id),
                    "tooling_master_global_id": str(value.tooling_master_global_id),
                    "snapshot_hash": value.predecessor_snapshot_hash,
                },
                _("The predecessor Tooling Revision is unavailable."),
            )
        for reference in (*value.cavities, *value.inserts):
            require_exact_parent(
                "NPI Tooling Applicability",
                str(reference.tooling_applicability_global_id),
                {
                    "global_id": str(reference.tooling_applicability_global_id),
                    "tenant_id": value.tenant_id,
                    "project_global_id": str(value.project_global_id),
                    "tooling_master_global_id": str(value.tooling_master_global_id),
                    "part_revision_global_id": str(reference.part_revision_global_id),
                },
                _("A Tooling Applicability is unavailable for this revision."),
            )
        for reference in value.design_document_revisions:
            require_exact_parent(
                "NPI Document Revision",
                str(reference.global_id),
                {
                    "global_id": str(reference.global_id),
                    "tenant_id": value.tenant_id,
                    "project_global_id": str(value.project_global_id),
                    "snapshot_hash": reference.snapshot_hash,
                },
                _("A design Document Revision is unavailable."),
            )
        self.tooling_master = str(value.tooling_master_global_id)
        self.revision_key_hash = value.revision_key_hash
        self.reason = value.reason
        self.created_by_user_id = value.created_by_user_id
        self.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
        self.specification_snapshot = canonical_json(value.specification.snapshot_payload())
        self.cavity_snapshot = canonical_json([item.snapshot_payload() for item in value.cavities])
        self.insert_snapshot = canonical_json([item.snapshot_payload() for item in value.inserts])
        self.external_identity_snapshot = canonical_json(
            [item.snapshot_payload() for item in value.external_identities]
        )
        self.design_document_revision_snapshot = canonical_json(
            [item.snapshot_payload() for item in value.design_document_revisions]
        )
        self.revision_snapshot = canonical_json(value.snapshot_payload())
        self.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))

    def on_trash(self) -> None:
        deny_tooling_history_delete(self)
