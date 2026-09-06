from __future__ import annotations

import hashlib
from datetime import date, datetime
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
    optional_date_text,
    optional_uuid,
    positive_integer,
    require_exact_parent,
    tenant_text,
    utc_datetime_text,
)
from npi_core.tooling.domain import ToolingApplicability
from npi_core.tooling.frappe_validation import (
    deny_tooling_history_delete,
    deny_tooling_history_update,
    require_tooling_command_write,
    tooling_domain_value,
)


class NPIToolingApplicability(Document):
    """Immutable versioned/effective shared-Master relationship."""

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
            ("relationship_global_id", _("Applicability Relationship Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("tooling_master_global_id", _("Tooling Master Global ID")),
            ("part_global_id", _("Part Global ID")),
            ("part_revision_global_id", _("Part Revision Global ID")),
            ("request_id", _("Request ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.predecessor_global_id = optional_uuid(
            self.predecessor_global_id,
            _("Predecessor Applicability Global ID"),
        )
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_tooling_history_update()
        require_exact_parent(
            "NPI Engineering Project",
            self.project_global_id,
            {"global_id": self.project_global_id, "tenant_id": self.tenant_id},
            _("The Applicability does not match its Project and tenant."),
        )
        require_exact_parent(
            "NPI Tooling Master",
            self.tooling_master_global_id,
            {"global_id": self.tooling_master_global_id, "tenant_id": self.tenant_id},
            _("The Tooling Master is unavailable."),
        )
        require_exact_parent(
            "NPI Engineering Part Revision",
            self.part_revision_global_id,
            {
                "global_id": self.part_revision_global_id,
                "part_global_id": self.part_global_id,
                "tenant_id": self.tenant_id,
            },
            _("The exact Part Revision is unavailable."),
        )
        created_at = utc_datetime_text(self.created_at, _("Created At"))
        effective_from = optional_date_text(
            self.effective_from,
            _("Effective From"),
        )
        if effective_from is None:
            frappe.throw(
                _("{field} is required.").format(field=_("Effective From")),
                frappe.ValidationError,
            )
        effective_to = optional_date_text(self.effective_to, _("Effective To"))
        supplied = json_object(
            self.applicability_snapshot,
            _("Tooling Applicability Snapshot"),
        )
        applicability = tooling_domain_value(
            lambda: ToolingApplicability(
                global_id=UUID(self.global_id),
                relationship_global_id=UUID(self.relationship_global_id),
                tenant_id=self.tenant_id,
                project_global_id=UUID(self.project_global_id),
                tooling_master_global_id=UUID(self.tooling_master_global_id),
                part_global_id=UUID(self.part_global_id),
                part_revision_global_id=UUID(self.part_revision_global_id),
                product_source_system=str(self.product_source_system or "") or None,
                product_source_object_id=str(self.product_source_object_id or "") or None,
                model_source_system=str(self.model_source_system or "") or None,
                model_source_object_id=str(self.model_source_object_id or "") or None,
                applicability_version=positive_integer(
                    self.applicability_version,
                    _("Applicability Version"),
                ),
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
                effective_from=date.fromisoformat(effective_from),
                effective_to=(
                    date.fromisoformat(effective_to)
                    if effective_to
                    else None
                ),
                reason=self.reason,
                created_by_user_id=actor_text(
                    self.created_by_user_id,
                    _("Created By User ID"),
                ),
                created_at=datetime.fromisoformat(created_at.replace("Z", "+00:00")),
                request_id=UUID(self.request_id),
                trace_id=self.trace_id,
                relationship_key_hash=str(self.relationship_key_hash or ""),
                snapshot_hash=str(self.snapshot_hash or ""),
            )
        )
        if supplied != applicability.snapshot_payload():
            frappe.throw(
                _("Tooling Applicability Snapshot does not match its exact relationship."),
                frappe.ValidationError,
            )
        expected_version_key = hashlib.sha256(
            (
                f"{self.tenant_id}:{applicability.relationship_global_id}:"
                f"{applicability.applicability_version}"
            ).encode()
        ).hexdigest()
        if self.version_key not in (None, "", expected_version_key):
            frappe.throw(
                _("Applicability Version Key does not match the exact version."),
                frappe.ValidationError,
            )
        self.relationship_key_hash = applicability.relationship_key_hash
        self.version_key = expected_version_key
        self.applicability_version = applicability.applicability_version
        self.reason = applicability.reason
        self.created_by_user_id = applicability.created_by_user_id
        self.created_at = frappe_utc_datetime_text(
            applicability.created_at,
            _("Created At"),
        )
        self.trace_id = applicability.trace_id
        self.applicability_snapshot = canonical_json(
            applicability.snapshot_payload()
        )
        self.snapshot_hash = applicability.snapshot_hash

    def on_trash(self) -> None:
        deny_tooling_history_delete(self)
