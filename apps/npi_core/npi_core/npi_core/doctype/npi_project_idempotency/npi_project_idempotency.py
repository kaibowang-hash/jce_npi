from __future__ import annotations

import re
from uuid import uuid4

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.project.frappe_validation import (
    assert_immutable_fields,
    deny_controlled_history_delete,
    ensure_uuid,
    require_project_command_write,
)


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class NPIProjectIdempotency(Document):
    """Append-only replay record; the raw idempotency key is never persisted."""

    _IMMUTABLE_FIELDS = (
        "record_id",
        "actor",
        "tenant_id",
        "actor_key_hash",
        "payload_hash",
        "project_global_id",
    )

    def before_insert(self) -> None:
        require_project_command_write()

    def on_trash(self) -> None:
        deny_controlled_history_delete()

    def before_validate(self) -> None:
        if not self.record_id:
            self.record_id = str(uuid4())

    def validate(self) -> None:
        self.record_id = ensure_uuid(self.record_id, _("Record ID"))
        self.project_global_id = ensure_uuid(
            self.project_global_id,
            _("Project Global ID"),
        )
        for fieldname in ("actor_key_hash", "payload_hash"):
            if not _SHA256_PATTERN.fullmatch(self.get(fieldname) or ""):
                frappe.throw(
                    _("A hash field must be a lowercase SHA-256 value."),
                    frappe.ValidationError,
                )
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, self._IMMUTABLE_FIELDS)
