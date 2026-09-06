from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.data_exchange.domain import RETENTION_POLICY_SCHEMA_VERSION, sha256_json
from npi_core.data_exchange.frappe_validation import deny_data_exchange_delete, require_data_exchange_write


class NPIRetentionPolicyVersion(Document):
    def before_insert(self) -> None:
        require_data_exchange_write()

    def before_save(self) -> None:
        require_data_exchange_write()

    def on_trash(self) -> None:
        deny_data_exchange_delete()

    def autoname(self) -> None:
        self.name = str(self.global_id)

    def validate(self) -> None:
        payload = json.loads(self.policy_definition)
        if (
            not isinstance(payload, dict)
            or payload.get("schemaVersion") != RETENTION_POLICY_SCHEMA_VERSION
            or payload.get("globalId") != self.global_id
            or payload.get("version") != self.policy_version
            or sha256_json(payload) != self.definition_hash
        ):
            frappe.throw(_("The retention policy definition is invalid."))
        if self.get_doc_before_save() is not None:
            frappe.throw(_("Published retention policies are immutable."))
