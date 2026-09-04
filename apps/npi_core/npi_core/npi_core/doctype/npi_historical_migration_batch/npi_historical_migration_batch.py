from __future__ import annotations

import json
import re

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.historical_migration.domain import BUNDLE_SCHEMA_VERSION, sha256_json
from npi_core.historical_migration.frappe_validation import (
    deny_historical_migration_delete,
    require_historical_migration_write,
)


_HASH = re.compile(r"^[a-f0-9]{64}$")


class NPIHistoricalMigrationBatch(Document):
    def before_insert(self) -> None:
        require_historical_migration_write()

    def before_save(self) -> None:
        require_historical_migration_write()

    def on_trash(self) -> None:
        deny_historical_migration_delete()

    def autoname(self) -> None:
        self.name = str(self.global_id)

    def validate(self) -> None:
        if self.schema_version != BUNDLE_SCHEMA_VERSION:
            frappe.throw(_("The historical migration bundle version is unsupported."))
        if any(
            _HASH.fullmatch(str(value or "")) is None
            for value in (self.source_sha256, self.manifest_hash, self.snapshot_hash)
        ):
            frappe.throw(_("The historical migration batch hash is invalid."))
        snapshot = _json_object(self.batch_snapshot)
        if (
            snapshot.get("schemaVersion") != BUNDLE_SCHEMA_VERSION
            or snapshot.get("bundleId") != self.global_id
            or snapshot.get("manifestHash") != self.manifest_hash
            or sha256_json(snapshot) != self.snapshot_hash
        ):
            frappe.throw(_("The historical migration batch snapshot is invalid."))
        previous = self.get_doc_before_save()
        if previous is not None:
            for fieldname in self.meta.get_valid_columns():
                if fieldname not in {"modified", "modified_by"} and self.get(
                    fieldname
                ) != previous.get(fieldname):
                    frappe.throw(_("Historical migration batches are immutable."))


def _json_object(value: object) -> dict[str, object]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, dict):
        frappe.throw(_("The historical migration batch snapshot is invalid."))
    return parsed
