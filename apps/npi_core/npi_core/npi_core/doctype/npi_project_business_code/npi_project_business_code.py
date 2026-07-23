from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.project.domain import business_code_reservation_hash
from npi_core.project.frappe_validation import (
    assert_immutable_fields,
    deny_controlled_history_delete,
    ensure_uuid,
    require_project_command_write,
)


class NPIProjectBusinessCode(Document):
    """Atomic tenant-scoped reservation for a case-insensitive business code."""

    _IMMUTABLE_FIELDS = (
        "reservation_key_hash",
        "tenant_id",
        "business_code",
        "project_global_id",
    )

    def before_insert(self) -> None:
        require_project_command_write()

    def on_trash(self) -> None:
        deny_controlled_history_delete()

    def validate(self) -> None:
        self.project_global_id = ensure_uuid(
            self.project_global_id,
            _("Project Global ID"),
        )
        expected_hash = business_code_reservation_hash(
            self.tenant_id,
            self.business_code,
        )
        if self.reservation_key_hash != expected_hash:
            frappe.throw(
                _("Reservation Key Hash does not match the tenant and business code."),
                frappe.ValidationError,
            )
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, self._IMMUTABLE_FIELDS)
