from __future__ import annotations

import json
import re

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.historical_migration.domain import (
    JOB_SCHEMA_VERSION,
    MigrationJobState,
    sha256_json,
)
from npi_core.historical_migration.frappe_validation import (
    deny_historical_migration_delete,
    require_historical_migration_write,
)


_HASH = re.compile(r"^[a-f0-9]{64}$")


class NPIHistoricalMigrationJob(Document):
    def before_insert(self) -> None:
        require_historical_migration_write()

    def before_save(self) -> None:
        require_historical_migration_write()

    def on_trash(self) -> None:
        deny_historical_migration_delete()

    def autoname(self) -> None:
        self.name = str(self.global_id)

    def validate(self) -> None:
        if self.state not in {state.value for state in MigrationJobState}:
            frappe.throw(_("Select a supported historical migration job state."))
        snapshot = json.loads(self.job_snapshot)
        if (
            not isinstance(snapshot, dict)
            or snapshot.get("schemaVersion") != JOB_SCHEMA_VERSION
            or snapshot.get("globalId") != self.global_id
            or snapshot.get("state") != self.state
            or snapshot.get("optimisticVersion") != self.optimistic_version
            or sha256_json(snapshot) != self.snapshot_hash
            or _HASH.fullmatch(str(self.snapshot_hash or "")) is None
        ):
            frappe.throw(_("The historical migration job snapshot is invalid."))
        previous = self.get_doc_before_save()
        if previous is not None:
            immutable = (
                "global_id",
                "tenant_id",
                "batch_global_id",
                "preview_global_id",
                "preview_snapshot_hash",
                "execution_key_hash",
                "actor_user_id",
                "queued_at",
                "request_id",
                "trace_id",
            )
            if any(self.get(field) != previous.get(field) for field in immutable):
                frappe.throw(_("Historical migration job identity is immutable."))
