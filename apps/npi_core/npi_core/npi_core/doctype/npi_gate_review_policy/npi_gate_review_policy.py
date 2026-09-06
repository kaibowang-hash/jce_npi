from __future__ import annotations

from uuid import uuid4

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.gate_review.frappe_validation import (
    assert_immutable_fields,
    controlled_key,
    ensure_uuid,
    required_text,
)


class NPIGateReviewPolicy(Document):
    """Administrative root for explicitly versioned Gate review policies."""

    def autoname(self) -> None:
        self._set_identity()
        self.name = self.global_id

    def before_validate(self) -> None:
        self._set_identity()

    def validate(self) -> None:
        self.global_id = ensure_uuid(self.global_id, _("Global ID"))
        self.policy_code = controlled_key(
            required_text(
                self.policy_code,
                _("Gate Review Policy Code"),
                maximum=64,
            ),
            _("Gate Review Policy Code"),
        )
        self.title = required_text(
            self.title,
            _("Gate Review Policy Title"),
            maximum=140,
        )
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(
                self,
                previous,
                ("global_id", "policy_code"),
            )

    def on_trash(self) -> None:
        if frappe.db.exists(
            "NPI Gate Review Policy Version",
            {"policy_global_id": self.global_id},
        ):
            frappe.throw(
                _("A Gate Review Policy with version history cannot be deleted."),
                frappe.PermissionError,
            )

    def _set_identity(self) -> None:
        if not self.global_id:
            self.global_id = str(uuid4())
