from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    assert_immutable_fields,
    canonical_uuid,
    lowercase_sha256,
    optional_uuid,
    positive_integer,
    require_exact_parent,
    required_text,
    tenant_text,
)
from npi_core.tooling.frappe_validation import (
    deny_tooling_history_delete,
    require_tooling_command_write,
)


_IDENTITY_FIELDS = (
    "global_id",
    "tenant_id",
    "originating_project_global_id",
)


class NPIEngineeringPart(Document):
    """Stable NPI Part identity with one guarded exact-revision pointer."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_tooling_command_write()

    def before_save(self) -> None:
        require_tooling_command_write()

    def before_validate(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.tenant_id = tenant_text(self.tenant_id)
        self.originating_project_global_id = canonical_uuid(
            self.originating_project_global_id,
            _("Originating Project Global ID"),
        )
        self.current_revision_global_id = optional_uuid(
            self.current_revision_global_id,
            _("Current Part Revision Global ID"),
        )

    def validate(self) -> None:
        require_exact_parent(
            "NPI Engineering Project",
            self.originating_project_global_id,
            {
                "global_id": self.originating_project_global_id,
                "tenant_id": self.tenant_id,
            },
            _("The Part does not match its originating Project and tenant."),
        )
        self.title = required_text(self.title, _("Part Title"), 140)
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _IDENTITY_FIELDS)
            previous_version = positive_integer(
                previous.get("optimistic_version"),
                _("Optimistic Version"),
            )
            self.optimistic_version = (
                previous_version
                if previous.get("current_revision_global_id") in (None, "")
                else previous_version + 1
            )
        else:
            self.optimistic_version = positive_integer(
                self.optimistic_version,
                _("Optimistic Version"),
            )
        pointer = (
            self.current_revision_global_id,
            self.current_revision_number,
            self.current_revision_snapshot_hash,
        )
        if all(value in (None, "", 0) for value in pointer):
            self.current_revision_global_id = None
            self.current_revision_number = None
            self.current_revision_snapshot_hash = None
            return
        if any(value in (None, "", 0) for value in pointer):
            frappe.throw(
                _("Current Part Revision identity, number and hash must be supplied together."),
                frappe.ValidationError,
            )
        self.current_revision_number = positive_integer(
            self.current_revision_number,
            _("Current Part Revision Number"),
        )
        self.current_revision_snapshot_hash = lowercase_sha256(
            self.current_revision_snapshot_hash,
            _("Current Part Revision Snapshot Hash"),
        )
        require_exact_parent(
            "NPI Engineering Part Revision",
            self.current_revision_global_id,
            {
                "global_id": self.current_revision_global_id,
                "part_global_id": self.global_id,
                "tenant_id": self.tenant_id,
                "originating_project_global_id": self.originating_project_global_id,
                "revision_number": self.current_revision_number,
                "snapshot_hash": self.current_revision_snapshot_hash,
            },
            _("The current Part Revision pointer is unavailable."),
        )
        if previous is not None:
            previous_number = int(previous.get("current_revision_number") or 0)
            if self.current_revision_number != previous_number + 1:
                frappe.throw(
                    _("The current Part Revision must advance exactly once."),
                    frappe.ValidationError,
                )

    def on_trash(self) -> None:
        deny_tooling_history_delete(self)
