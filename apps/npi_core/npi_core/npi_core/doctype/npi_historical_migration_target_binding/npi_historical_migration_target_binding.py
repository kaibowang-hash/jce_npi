from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.historical_migration.frappe_validation import (
    deny_historical_migration_delete,
    require_historical_migration_write,
)


_HASH = re.compile(r"^[a-f0-9]{64}$")


class NPIHistoricalMigrationTargetBinding(Document):
    def before_insert(self) -> None:
        require_historical_migration_write()

    def before_save(self) -> None:
        require_historical_migration_write()

    def on_trash(self) -> None:
        deny_historical_migration_delete()

    def autoname(self) -> None:
        self.name = str(self.binding_key_hash)

    def validate(self) -> None:
        if any(
            _HASH.fullmatch(str(value or "")) is None
            for value in (
                self.binding_key_hash,
                self.source_hash,
                self.target_snapshot_hash,
            )
        ):
            frappe.throw(_("The historical migration binding hash is invalid."))
        if self.state not in {"active", "rolled_back", "forward_correction_required"}:
            frappe.throw(_("Select a supported historical migration binding state."))
        previous = self.get_doc_before_save()
        if previous is not None:
            immutable = (
                "binding_key_hash",
                "tenant_id",
                "family",
                "source_system",
                "source_key",
                "source_hash",
                "target_doctype",
                "target_global_id",
                "target_version",
                "target_snapshot_hash",
                "created_by_job_global_id",
            )
            if any(self.get(field) != previous.get(field) for field in immutable):
                frappe.throw(_("Historical migration target bindings are immutable."))
            transitions = {
                "active": {"active", "rolled_back", "forward_correction_required"},
                "rolled_back": {"rolled_back"},
                "forward_correction_required": {"forward_correction_required"},
            }
            if self.state not in transitions.get(str(previous.state), set()):
                frappe.throw(_("The historical migration binding state cannot move backward."))
