from __future__ import annotations

from uuid import uuid4

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.project.frappe_validation import (
    assert_immutable_fields,
    ensure_uuid,
)
from npi_core.project_controls.frappe_validation import (
    require_controlled_key,
    require_text,
)


class NPIProjectControlPolicy(Document):
    def autoname(self) -> None:
        self._set_identity()
        self.name = self.global_id

    def before_validate(self) -> None:
        self._set_identity()

    def validate(self) -> None:
        self.global_id = ensure_uuid(self.global_id, _("Global ID"))
        self.policy_code = require_controlled_key(
            self.policy_code,
            _("Project Control Policy Code"),
        )
        self.title = require_text(
            self.title,
            _("Project Control Policy Title"),
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
            "NPI Project Control Policy Version",
            {"policy_global_id": self.global_id},
        ):
            frappe.throw(
                _(
                    "A Project Control Policy with version history cannot be deleted."
                ),
                frappe.PermissionError,
            )

    def _set_identity(self) -> None:
        if not self.global_id:
            self.global_id = str(uuid4())
