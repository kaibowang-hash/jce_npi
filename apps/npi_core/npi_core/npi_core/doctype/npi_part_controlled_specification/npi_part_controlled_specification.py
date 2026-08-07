from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    canonical_json,
    canonical_uuid,
    json_array,
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
from npi_core.tooling.revision_domain import (
    part_controlled_specification_from_snapshot,
)


class NPIPartControlledSpecification(Document):
    """Immutable controlled material, color and compliance facts."""

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
            ("part_global_id", _("Part Global ID")),
            ("part_revision_global_id", _("Part Revision Global ID")),
            ("request_id", _("Request ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_tooling_history_update()
        supplied = json_object(
            self.specification_snapshot,
            _("Part Controlled Specification Snapshot"),
        )
        value = tooling_domain_value(
            lambda: part_controlled_specification_from_snapshot(supplied)
        )
        expected = (
            str(value.global_id), value.tenant_id, str(value.project_global_id),
            str(value.part_global_id), str(value.part_revision_global_id),
            value.part_revision_snapshot_hash, str(value.request_id), value.trace_id,
        )
        actual = (
            self.global_id, self.tenant_id, self.project_global_id,
            self.part_global_id, self.part_revision_global_id,
            self.part_revision_snapshot_hash, self.request_id, self.trace_id,
        )
        if actual != expected:
            frappe.throw(
                _("Part Controlled Specification fields do not match the exact snapshot."),
                frappe.ValidationError,
            )
        if self.specification_key_hash not in (None, "", value.specification_key_hash):
            frappe.throw(_("Part Specification Key Hash does not match."), frappe.ValidationError)
        if self.snapshot_hash not in (None, "", value.snapshot_hash):
            frappe.throw(_("Part Controlled Specification Snapshot Hash does not match."), frappe.ValidationError)
        if json_array(self.item_snapshot, _("Part Specification Item Snapshot")) != [
            item.snapshot_payload() for item in value.items
        ]:
            frappe.throw(_("Part Specification Item Snapshot does not match."), frappe.ValidationError)
        if json_array(self.external_identity_snapshot, _("External Identity Snapshot")) != [
            item.snapshot_payload() for item in value.external_identities
        ]:
            frappe.throw(_("External Identity Snapshot does not match."), frappe.ValidationError)
        require_exact_parent(
            "NPI Engineering Part Revision",
            str(value.part_revision_global_id),
            {
                "global_id": str(value.part_revision_global_id),
                "part_global_id": str(value.part_global_id),
                "tenant_id": value.tenant_id,
                "originating_project_global_id": str(value.project_global_id),
                "snapshot_hash": value.part_revision_snapshot_hash,
            },
            _("The exact Part Revision is unavailable for this specification."),
        )
        self.engineering_part = str(value.part_global_id)
        self.engineering_part_revision = str(value.part_revision_global_id)
        self.specification_key_hash = value.specification_key_hash
        self.created_by_user_id = value.created_by_user_id
        self.created_at = value.snapshot_payload()["createdAt"]
        self.item_snapshot = canonical_json([item.snapshot_payload() for item in value.items])
        self.external_identity_snapshot = canonical_json(
            [item.snapshot_payload() for item in value.external_identities]
        )
        self.specification_snapshot = canonical_json(value.snapshot_payload())
        self.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))

    def on_trash(self) -> None:
        deny_tooling_history_delete(self)
