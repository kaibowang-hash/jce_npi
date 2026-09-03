from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.data_exchange.domain import ARCHIVE_RECORD_SCHEMA_VERSION, sha256_json
from npi_core.data_exchange.frappe_validation import deny_data_exchange_delete, require_data_exchange_write


class NPIRetentionArchiveRecord(Document):
    def before_insert(self) -> None:
        require_data_exchange_write()

    def before_save(self) -> None:
        require_data_exchange_write()

    def on_trash(self) -> None:
        deny_data_exchange_delete()

    def autoname(self) -> None:
        self.name = str(self.global_id)

    def validate(self) -> None:
        payload = json.loads(self.archive_snapshot)
        if (
            not isinstance(payload, dict)
            or payload.get("schemaVersion") != ARCHIVE_RECORD_SCHEMA_VERSION
            or payload.get("globalId") != self.global_id
            or sha256_json(payload) != self.record_hash
        ):
            frappe.throw(_("The retention archive snapshot is invalid."))
        if self.get_doc_before_save() is not None:
            frappe.throw(_("Retention archive records are immutable."))
