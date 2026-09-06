from __future__ import annotations

import hashlib

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    assert_immutable_fields,
    canonical_uuid,
    key_text,
    lowercase_sha256,
    optional_uuid,
    positive_integer,
    require_exact_parent,
    required_text,
    tenant_text,
)
from npi_core.ebom.frappe_validation import (
    deny_ebom_history_delete,
    require_ebom_command_write,
)


_IDENTITY_FIELDS = (
    "global_id",
    "tenant_id",
    "project_global_id",
    "engineering_bom_key",
    "engineering_bom_key_hash",
    "policy_global_id",
    "policy_version",
    "policy_snapshot_hash",
)


class NPIEngineeringBOM(Document):
    """Stable NPI-owned EBOM identity with an exact latest-revision pointer."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_ebom_command_write()

    def before_save(self) -> None:
        require_ebom_command_write()

    def before_validate(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.tenant_id = tenant_text(self.tenant_id)
        self.project_global_id = canonical_uuid(
            self.project_global_id,
            _("Project Global ID"),
        )
        self.engineering_bom_key = key_text(
            self.engineering_bom_key,
            _("Engineering BOM Key"),
        )
        self.engineering_bom_key_hash = hashlib.sha256(
            (
                f"{self.tenant_id}:{self.project_global_id}:"
                f"{self.engineering_bom_key.casefold()}"
            ).encode("utf-8")
        ).hexdigest()
        self.policy_global_id = canonical_uuid(
            self.policy_global_id,
            _("EBOM Policy Global ID"),
        )
        self.latest_revision_global_id = optional_uuid(
            self.latest_revision_global_id,
            _("Latest EBOM Revision"),
        )

    def validate(self) -> None:
        require_exact_parent(
            "NPI Engineering Project",
            self.project_global_id,
            {"global_id": self.project_global_id, "tenant_id": self.tenant_id},
            _("The EBOM does not match its Project and tenant."),
        )
        require_exact_parent(
            "NPI EBOM Policy Version",
            {
                "policy_global_id": self.policy_global_id,
                "policy_version": self.policy_version,
            },
            {
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "publication_state": "published",
                "snapshot_hash": self.policy_snapshot_hash,
            },
            _("The exact published EBOM policy is unavailable."),
        )
        self.title = required_text(self.title, _("Engineering BOM Title"), 140)
        self.policy_version = positive_integer(
            self.policy_version,
            _("EBOM Policy Version"),
        )
        self.policy_snapshot_hash = lowercase_sha256(
            self.policy_snapshot_hash,
            _("EBOM Policy Snapshot Hash"),
        )
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _IDENTITY_FIELDS)
            self.optimistic_version = positive_integer(
                previous.get("optimistic_version"),
                _("Optimistic Version"),
            ) + 1
        else:
            self.optimistic_version = positive_integer(
                self.optimistic_version,
                _("Optimistic Version"),
            )
        latest_values = (
            self.latest_revision_global_id,
            self.latest_revision_number,
            self.latest_revision_snapshot_hash,
        )
        if all(value in (None, "", 0) for value in latest_values):
            self.latest_revision_global_id = None
            self.latest_revision_number = None
            self.latest_revision_snapshot_hash = None
            return
        if any(value in (None, "", 0) for value in latest_values):
            frappe.throw(
                _("Latest EBOM revision identity, number and hash must be supplied together."),
                frappe.ValidationError,
            )
        self.latest_revision_number = positive_integer(
            self.latest_revision_number,
            _("Latest EBOM Revision Number"),
        )
        self.latest_revision_snapshot_hash = lowercase_sha256(
            self.latest_revision_snapshot_hash,
            _("Latest EBOM Revision Snapshot Hash"),
        )
        require_exact_parent(
            "NPI Engineering BOM Revision",
            self.latest_revision_global_id,
            {
                "global_id": self.latest_revision_global_id,
                "ebom_global_id": self.global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "revision_number": self.latest_revision_number,
                "snapshot_hash": self.latest_revision_snapshot_hash,
            },
            _("The latest EBOM revision pointer is unavailable."),
        )
        if previous is not None:
            previous_number = int(previous.get("latest_revision_number") or 0)
            if self.latest_revision_number != previous_number + 1:
                frappe.throw(
                    _("The latest EBOM revision must advance exactly once."),
                    frappe.ValidationError,
                )

    def on_trash(self) -> None:
        deny_ebom_history_delete(
            self,
            target_version=self.get("optimistic_version") or 1,
        )
