from __future__ import annotations

from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    canonical_json,
    canonical_uuid,
    frappe_utc_datetime_text,
    json_object,
    lowercase_sha256,
    nonnegative_integer,
    require_exact_parent,
    tenant_text,
    utc_datetime_text,
)
from npi_core.ebom.domain import sha256_json
from npi_core.ebom.frappe_validation import (
    deny_ebom_history_delete,
    deny_ebom_history_update,
    ebom_domain_value,
    ebom_line_value,
    require_ebom_command_write,
)


class NPIEngineeringBOMLine(Document):
    """Append-only materialized line from one exact EBOM revision snapshot."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_ebom_command_write()

    def before_save(self) -> None:
        require_ebom_command_write()
        if self.get_doc_before_save() is not None:
            deny_ebom_history_update()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("engineering_bom", _("Engineering BOM")),
            ("ebom_global_id", _("Engineering BOM Global ID")),
            ("engineering_bom_revision", _("Engineering BOM Revision")),
            ("revision_global_id", _("EBOM Revision Global ID")),
            ("project_global_id", _("Project Global ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_ebom_history_update()
        if self.engineering_bom != self.ebom_global_id:
            frappe.throw(
                _("Engineering BOM must match its exact Global ID."),
                frappe.ValidationError,
            )
        if self.engineering_bom_revision != self.revision_global_id:
            frappe.throw(
                _("Engineering BOM Revision must match its exact Global ID."),
                frappe.ValidationError,
            )
        revision = require_exact_parent(
            "NPI Engineering BOM Revision",
            self.engineering_bom_revision,
            {
                "global_id": self.revision_global_id,
                "ebom_global_id": self.ebom_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "snapshot_hash": self.revision_snapshot_hash,
            },
            _("The EBOM line does not match its exact revision."),
            extra_fields=("revision_snapshot", "quantity_scale", "created_at"),
        )
        line = ebom_domain_value(lambda: ebom_line_value(self.line_snapshot))
        if str(line.global_id) != self.global_id:
            frappe.throw(
                _("Canonical EBOM Line Snapshot does not match its Global ID."),
                frappe.ValidationError,
            )
        quantity_scale = nonnegative_integer(
            revision.get("quantity_scale"),
            _("Quantity Scale"),
        )
        if quantity_scale > 6:
            frappe.throw(
                _("Quantity Scale cannot be greater than six."),
                frappe.ValidationError,
            )
        expected_snapshot = line.canonical_dict(quantity_scale)
        revision_snapshot = json_object(
            revision.get("revision_snapshot"),
            _("Canonical EBOM Revision Snapshot"),
        )
        if (
            expected_snapshot not in revision_snapshot.get("lines", [])
            or json_object(
                self.line_snapshot,
                _("Canonical EBOM Line Snapshot"),
            )
            != expected_snapshot
        ):
            frappe.throw(
                _("Canonical EBOM Line Snapshot does not match its revision."),
                frappe.ValidationError,
            )
        expected_identity_key = f"{self.revision_global_id}:{line.line_key.casefold()}"
        expected_hash = sha256_json(expected_snapshot)
        if self.line_identity_key not in (None, "", expected_identity_key):
            frappe.throw(_("EBOM Line Identity Key is invalid."), frappe.ValidationError)
        if self.line_hash not in (None, "", expected_hash):
            frappe.throw(_("EBOM Line Hash does not match its snapshot."), frappe.ValidationError)
        revision_created_at = utc_datetime_text(revision.get("created_at"), _("Created At"))
        created_at = utc_datetime_text(self.created_at, _("Created At"))
        if created_at != revision_created_at:
            frappe.throw(
                _("EBOM line creation time must match its revision."),
                frappe.ValidationError,
            )
        self.line_identity_key = expected_identity_key
        self.line_key = line.line_key
        self.parent_line_key = line.parent_line_key
        self.engineering_item_id = line.engineering_item_id
        self.description = line.description
        self.quantity = expected_snapshot["quantity"]
        self.engineering_uom = line.engineering_uom
        self.alternate_for_line_key = line.alternate_for_line_key
        self.alternate_group_key = line.alternate_group_key
        self.effectivity_start = line.effectivity_start
        self.effectivity_end = line.effectivity_end
        self.attributes = canonical_json(dict(line.attributes))
        self.line_snapshot = canonical_json(expected_snapshot)
        self.line_hash = lowercase_sha256(expected_hash, _("EBOM Line Hash"))
        self.revision_snapshot_hash = lowercase_sha256(
            self.revision_snapshot_hash,
            _("EBOM Revision Snapshot Hash"),
        )
        self.created_at = frappe_utc_datetime_text(
            datetime.fromisoformat(created_at.replace("Z", "+00:00")),
            _("Created At"),
        )

    def on_trash(self) -> None:
        deny_ebom_history_delete(self)
