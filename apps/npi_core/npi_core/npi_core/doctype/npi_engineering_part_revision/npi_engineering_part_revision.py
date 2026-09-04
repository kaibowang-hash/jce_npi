from __future__ import annotations

import hashlib
from datetime import datetime
from uuid import UUID

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    actor_text,
    canonical_json,
    canonical_uuid,
    frappe_utc_datetime_text,
    json_object,
    lowercase_sha256,
    optional_uuid,
    positive_integer,
    require_exact_parent,
    tenant_text,
    utc_datetime_text,
)
from npi_core.tooling.domain import EngineeringPartRevision
from npi_core.tooling.frappe_validation import (
    deny_tooling_history_delete,
    deny_tooling_history_update,
    require_tooling_command_write,
    tooling_import_rollback_delete_allowed,
    tooling_domain_value,
)


class NPIEngineeringPartRevision(Document):
    """Immutable exact NPI engineering Part Revision."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_tooling_command_write()

    def before_save(self) -> None:
        require_tooling_command_write()
        if self.get_doc_before_save() is not None:
            deny_tooling_history_update()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("engineering_part", _("Engineering Part")),
            ("part_global_id", _("Part Global ID")),
            ("originating_project_global_id", _("Originating Project Global ID")),
            ("request_id", _("Request ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.predecessor_global_id = optional_uuid(
            self.predecessor_global_id,
            _("Predecessor Part Revision Global ID"),
        )
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_tooling_history_update()
        if self.engineering_part != self.part_global_id:
            frappe.throw(
                _("Engineering Part must match its exact Global ID."),
                frappe.ValidationError,
            )
        require_exact_parent(
            "NPI Engineering Part",
            self.engineering_part,
            {
                "global_id": self.part_global_id,
                "tenant_id": self.tenant_id,
                "originating_project_global_id": self.originating_project_global_id,
            },
            _("The Part Revision does not match its Engineering Part."),
        )
        supplied = json_object(self.revision_snapshot, _("Part Revision Snapshot"))
        created_at = utc_datetime_text(self.created_at, _("Created At"))
        revision = tooling_domain_value(
            lambda: EngineeringPartRevision(
                global_id=UUID(self.global_id),
                part_global_id=UUID(self.part_global_id),
                tenant_id=self.tenant_id,
                originating_project_global_id=UUID(self.originating_project_global_id),
                revision_number=positive_integer(
                    self.revision_number,
                    _("Part Revision Number"),
                ),
                revision_label=self.revision_label,
                title=self.title,
                reason=self.reason,
                predecessor_global_id=(
                    UUID(self.predecessor_global_id)
                    if self.predecessor_global_id
                    else None
                ),
                predecessor_snapshot_hash=(
                    lowercase_sha256(
                        self.predecessor_snapshot_hash,
                        _("Predecessor Snapshot Hash"),
                    )
                    if self.predecessor_snapshot_hash
                    else None
                ),
                created_by_user_id=actor_text(
                    self.created_by_user_id,
                    _("Created By User ID"),
                ),
                created_at=datetime.fromisoformat(created_at.replace("Z", "+00:00")),
                request_id=UUID(self.request_id),
                trace_id=self.trace_id,
                snapshot_hash=str(self.snapshot_hash or ""),
            )
        )
        if supplied != revision.snapshot_payload():
            frappe.throw(
                _("Part Revision Snapshot does not match its exact revision."),
                frappe.ValidationError,
            )
        expected_key = hashlib.sha256(
            f"{self.tenant_id}:{self.part_global_id}:{revision.revision_number}".encode()
        ).hexdigest()
        if self.revision_key not in (None, "", expected_key):
            frappe.throw(
                _("Part Revision Key does not match the exact revision."),
                frappe.ValidationError,
            )
        self.revision_number = revision.revision_number
        self.revision_label = revision.revision_label
        self.title = revision.title
        self.reason = revision.reason
        self.revision_key = expected_key
        self.created_by_user_id = revision.created_by_user_id
        self.created_at = frappe_utc_datetime_text(revision.created_at, _("Created At"))
        self.trace_id = revision.trace_id
        self.revision_snapshot = canonical_json(revision.snapshot_payload())
        self.snapshot_hash = revision.snapshot_hash

    def on_trash(self) -> None:
        if not tooling_import_rollback_delete_allowed(self):
            deny_tooling_history_delete(self)
