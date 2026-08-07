from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    canonical_json,
    canonical_uuid,
    json_object,
    lowercase_sha256,
    require_exact_parent,
    tenant_text,
)
from npi_core.tooling.frappe_validation import (
    deny_tooling_history_delete,
    deny_tooling_history_update,
    require_tooling_command_write,
    tooling_domain_value,
)
from npi_core.tooling.revision_domain import set_revision_binding_from_snapshot


class NPIToolingSetRevisionBinding(Document):
    """Immutable initial exact source Revision for one physical Set."""

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
            ("tooling_set_global_id", _("Tooling Set Global ID")),
            ("tooling_revision_global_id", _("Tooling Revision Global ID")),
            ("request_id", _("Request ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_tooling_history_update()
        supplied = json_object(self.binding_snapshot, _("Set Revision Binding Snapshot"))
        value = tooling_domain_value(lambda: set_revision_binding_from_snapshot(supplied))
        expected = (
            str(value.global_id), value.tenant_id, str(value.project_global_id),
            str(value.tooling_master_global_id), str(value.tooling_set_global_id),
            value.tooling_set_snapshot_hash, str(value.tooling_revision_global_id),
            value.tooling_revision_snapshot_hash, str(value.request_id), value.trace_id,
        )
        actual = (
            self.global_id, self.tenant_id, self.project_global_id,
            self.tooling_master_global_id, self.tooling_set_global_id,
            self.tooling_set_snapshot_hash, self.tooling_revision_global_id,
            self.tooling_revision_snapshot_hash, self.request_id, self.trace_id,
        )
        if actual != expected:
            frappe.throw(_("Set Revision Binding fields do not match the exact snapshot."), frappe.ValidationError)
        if self.binding_key_hash not in (None, "", value.binding_key_hash):
            frappe.throw(_("Set Revision Binding Key Hash does not match."), frappe.ValidationError)
        if self.snapshot_hash not in (None, "", value.snapshot_hash):
            frappe.throw(_("Set Revision Binding Snapshot Hash does not match."), frappe.ValidationError)
        require_exact_parent(
            "NPI Tooling Set",
            str(value.tooling_set_global_id),
            {
                "global_id": str(value.tooling_set_global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "tooling_master_global_id": str(value.tooling_master_global_id),
                "snapshot_hash": value.tooling_set_snapshot_hash,
            },
            _("The Tooling Set is unavailable for this source binding."),
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
            _("The Tooling Revision is unavailable for this source binding."),
        )
        self.tooling_set = str(value.tooling_set_global_id)
        self.tooling_revision = str(value.tooling_revision_global_id)
        self.binding_key_hash = value.binding_key_hash
        self.reason = value.reason
        self.created_by_user_id = value.created_by_user_id
        self.created_at = value.snapshot_payload()["createdAt"]
        self.binding_snapshot = canonical_json(value.snapshot_payload())
        self.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))

    def on_trash(self) -> None:
        deny_tooling_history_delete(self)
