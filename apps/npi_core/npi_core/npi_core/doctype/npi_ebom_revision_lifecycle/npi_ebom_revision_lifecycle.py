from __future__ import annotations

from uuid import UUID

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    actor_text,
    assert_immutable_fields,
    canonical_uuid,
    frappe_utc_datetime_text,
    lowercase_sha256,
    optional_uuid,
    positive_integer,
    require_exact_parent,
    required_text,
    tenant_text,
)
from npi_core.ebom.domain import (
    EngineeringBomLifecycleState,
    EngineeringBomRevisionLifecycle,
)
from npi_core.ebom.frappe_validation import (
    deny_ebom_history_delete,
    ebom_domain_value,
    require_ebom_lifecycle_write,
)


_IDENTITY_FIELDS = (
    "global_id",
    "tenant_id",
    "project_global_id",
    "engineering_bom",
    "ebom_global_id",
    "engineering_bom_revision",
    "revision_global_id",
    "revision_snapshot_hash",
)


class NPIEBOMRevisionLifecycle(Document):
    """Guarded current-state projection over immutable EBOM content."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_ebom_lifecycle_write()

    def before_save(self) -> None:
        require_ebom_lifecycle_write()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("engineering_bom", _("Engineering BOM")),
            ("ebom_global_id", _("Engineering BOM Global ID")),
            ("engineering_bom_revision", _("Engineering BOM Revision")),
            ("revision_global_id", _("EBOM Revision Global ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.last_event_global_id = optional_uuid(
            self.last_event_global_id,
            _("Last EBOM Lifecycle Event"),
        )
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _IDENTITY_FIELDS)
        if (
            self.global_id != self.revision_global_id
            or self.engineering_bom != self.ebom_global_id
            or self.engineering_bom_revision != self.revision_global_id
        ):
            frappe.throw(
                _("EBOM lifecycle identity must match the exact revision."),
                frappe.ValidationError,
            )
        require_exact_parent(
            "NPI Engineering BOM Revision",
            self.engineering_bom_revision,
            {
                "global_id": self.revision_global_id,
                "ebom_global_id": self.ebom_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "snapshot_hash": self.revision_snapshot_hash,
            },
            _("The EBOM lifecycle does not match its exact revision."),
        )
        try:
            state = EngineeringBomLifecycleState(str(self.current_state))
        except ValueError:
            frappe.throw(
                _("Select a supported EBOM lifecycle state."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.")
        version = positive_integer(self.lifecycle_version, _("Lifecycle Version"))
        if previous is None:
            if (
                state is not EngineeringBomLifecycleState.DRAFT
                or version != 1
                or self.last_event_global_id is not None
            ):
                frappe.throw(
                    _("A new EBOM lifecycle must start as draft version 1."),
                    frappe.ValidationError,
                )
        else:
            event = require_exact_parent(
                "NPI EBOM Lifecycle Event",
                self.last_event_global_id,
                {
                    "global_id": self.last_event_global_id,
                    "tenant_id": self.tenant_id,
                    "project_global_id": self.project_global_id,
                    "ebom_global_id": self.ebom_global_id,
                    "revision_global_id": self.revision_global_id,
                    "revision_snapshot_hash": self.revision_snapshot_hash,
                    "from_state": previous.get("current_state"),
                    "to_state": state.value,
                    "from_version": previous.get("lifecycle_version"),
                    "to_version": version,
                },
                _("The EBOM lifecycle does not match its exact event."),
            )
            if version != int(previous.get("lifecycle_version") or 0) + 1:
                frappe.throw(
                    _("The EBOM lifecycle must advance exactly once."),
                    frappe.ValidationError,
                )
            if not event:
                raise AssertionError("Exact event validation must return a row.")
        lifecycle = ebom_domain_value(
            lambda: EngineeringBomRevisionLifecycle(
                revision_global_id=UUID(self.revision_global_id),
                revision_snapshot_hash=self.revision_snapshot_hash,
                current_state=state,
                lifecycle_version=version,
                last_event_global_id=self.last_event_global_id,
            )
        )
        self.revision_snapshot_hash = lowercase_sha256(
            lifecycle.revision_snapshot_hash,
            _("EBOM Revision Snapshot Hash"),
        )
        self.current_state = lifecycle.current_state.value
        self.lifecycle_version = lifecycle.lifecycle_version
        self.last_event_global_id = (
            str(lifecycle.last_event_global_id)
            if lifecycle.last_event_global_id is not None
            else None
        )
        self.updated_by_user_id = actor_text(
            self.updated_by_user_id,
            _("Updated By User ID"),
        )
        self.updated_at = frappe_utc_datetime_text(self.updated_at, _("Updated At"))
        self.request_id = required_text(self.request_id, _("Request ID"), 128)
        self.trace_id = required_text(self.trace_id, _("Trace ID"), 128)

    def on_trash(self) -> None:
        deny_ebom_history_delete(
            self,
            target_version=self.get("lifecycle_version") or 1,
        )
