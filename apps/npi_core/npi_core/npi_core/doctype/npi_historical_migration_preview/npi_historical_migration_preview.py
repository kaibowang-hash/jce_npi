from __future__ import annotations

import json
import re

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.historical_migration.domain import PREVIEW_SCHEMA_VERSION, sha256_json
from npi_core.historical_migration.frappe_validation import (
    deny_historical_migration_delete,
    require_historical_migration_write,
)


_HASH = re.compile(r"^[a-f0-9]{64}$")


class NPIHistoricalMigrationPreview(Document):
    def before_insert(self) -> None:
        require_historical_migration_write()

    def before_save(self) -> None:
        require_historical_migration_write()

    def on_trash(self) -> None:
        deny_historical_migration_delete()

    def autoname(self) -> None:
        self.name = str(self.global_id)

    def validate(self) -> None:
        snapshot = json.loads(self.preview_snapshot)
        if (
            not isinstance(snapshot, dict)
            or snapshot.get("schemaVersion") != PREVIEW_SCHEMA_VERSION
            or snapshot.get("globalId") != self.global_id
            or snapshot.get("snapshotHash") is not None
            or sha256_json(snapshot) != self.snapshot_hash
            or _HASH.fullmatch(str(self.snapshot_hash or "")) is None
        ):
            frappe.throw(_("The historical migration preview snapshot is invalid."))
        previous = self.get_doc_before_save()
        if previous is not None:
            frappe.throw(_("Historical migration previews are immutable."))
