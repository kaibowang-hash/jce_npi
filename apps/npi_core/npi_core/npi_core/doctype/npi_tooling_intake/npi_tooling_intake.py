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
    json_array,
    json_object,
    lowercase_sha256,
    optional_uuid,
    positive_integer,
    require_exact_parent,
    tenant_text,
    utc_datetime_text,
)
from npi_core.tooling.domain import (
    ToolingAccessoryLine,
    ToolingDifferenceSourceKind,
    ToolingInspectionCategory,
    ToolingInspectionObservation,
    ToolingIntake,
    ToolingIntakeDifference,
)
from npi_core.tooling.frappe_validation import (
    deny_tooling_history_delete,
    deny_tooling_history_update,
    require_tooling_command_write,
    tooling_domain_value,
)


class NPIToolingIntake(Document):
    """Immutable versioned transport, inspection and difference snapshot."""

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
            ("project_global_id", _("Project Global ID")),
            ("tooling_master_global_id", _("Tooling Master Global ID")),
            ("tooling_set_global_id", _("Tooling Set Global ID")),
            ("request_id", _("Request ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.predecessor_global_id = optional_uuid(
            self.predecessor_global_id,
            _("Predecessor Tooling Intake Global ID"),
        )
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_tooling_history_update()
        require_exact_parent(
            "NPI Tooling Set",
            self.tooling_set_global_id,
            {
                "global_id": self.tooling_set_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "tooling_master_global_id": self.tooling_master_global_id,
            },
            _("The Tooling Set is unavailable for this intake."),
        )
        if self.predecessor_global_id:
            require_exact_parent(
                "NPI Tooling Intake",
                self.predecessor_global_id,
                {
                    "global_id": self.predecessor_global_id,
                    "tenant_id": self.tenant_id,
                    "project_global_id": self.project_global_id,
                    "tooling_master_global_id": self.tooling_master_global_id,
                    "tooling_set_global_id": self.tooling_set_global_id,
                },
                _("The predecessor Tooling Intake is unavailable."),
            )
        arrived_at = utc_datetime_text(self.arrived_at, _("Arrived At"))
        created_at = utc_datetime_text(self.created_at, _("Created At"))
        accessories_payload = json_array(
            self.accessory_snapshot,
            _("Accessory Snapshot"),
        )
        inspections_payload = json_array(
            self.inspection_snapshot,
            _("Inspection Snapshot"),
        )
        differences_payload = json_array(
            self.difference_snapshot,
            _("Difference Snapshot"),
        )
        supplied = json_object(self.intake_snapshot, _("Tooling Intake Snapshot"))
        value = tooling_domain_value(
            lambda: ToolingIntake(
                global_id=UUID(self.global_id),
                tenant_id=self.tenant_id,
                project_global_id=UUID(self.project_global_id),
                tooling_master_global_id=UUID(self.tooling_master_global_id),
                tooling_set_global_id=UUID(self.tooling_set_global_id),
                intake_version=positive_integer(
                    self.intake_version,
                    _("Tooling Intake Version"),
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
                transport_provider=self.transport_provider,
                transport_reference=self.transport_reference,
                arrived_at=datetime.fromisoformat(arrived_at.replace("Z", "+00:00")),
                custody_handover=self.custody_handover,
                accessories=tuple(
                    _accessory(value) for value in accessories_payload
                ),
                inspections=tuple(
                    _inspection(value) for value in inspections_payload
                ),
                differences=tuple(
                    _difference(value) for value in differences_payload
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
        if supplied != value.snapshot_payload():
            frappe.throw(
                _("Tooling Intake Snapshot does not match its exact intake version."),
                frappe.ValidationError,
            )
        expected_key = hashlib.sha256(
            f"{self.tenant_id}:{value.tooling_set_global_id}:{value.intake_version}".encode()
        ).hexdigest()
        if self.intake_key not in (None, "", expected_key):
            frappe.throw(
                _("Tooling Intake Key does not match the exact version."),
                frappe.ValidationError,
            )
        self.intake_key = expected_key
        self.tooling_set = str(value.tooling_set_global_id)
        self.intake_version = value.intake_version
        self.transport_provider = value.transport_provider
        self.transport_reference = value.transport_reference
        self.arrived_at = frappe_utc_datetime_text(value.arrived_at, _("Arrived At"))
        self.custody_handover = value.custody_handover
        self.accessory_snapshot = canonical_json(
            [item.snapshot_payload() for item in value.accessories]
        )
        self.inspection_snapshot = canonical_json(
            [item.snapshot_payload() for item in value.inspections]
        )
        self.difference_snapshot = canonical_json(
            [item.snapshot_payload() for item in value.differences]
        )
        self.created_by_user_id = value.created_by_user_id
        self.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
        self.trace_id = value.trace_id
        self.intake_snapshot = canonical_json(value.snapshot_payload())
        self.snapshot_hash = value.snapshot_hash

    def on_trash(self) -> None:
        deny_tooling_history_delete(self)


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        frappe.throw(_("{field} is invalid.").format(field=label), frappe.ValidationError)
    return value


def _accessory(value: object) -> ToolingAccessoryLine:
    payload = _object(value, _("Accessory Snapshot"))
    return ToolingAccessoryLine(
        global_id=payload.get("globalId"),
        description=payload.get("description"),
        declared_quantity=payload.get("declaredQuantity"),
        received_quantity=payload.get("receivedQuantity"),
        unit=payload.get("unit"),
    )


def _inspection(value: object) -> ToolingInspectionObservation:
    payload = _object(value, _("Inspection Snapshot"))
    try:
        category = ToolingInspectionCategory(str(payload.get("category")))
    except ValueError:
        frappe.throw(_("Select a supported value."), frappe.ValidationError)
        raise AssertionError("Frappe validation must raise.")
    return ToolingInspectionObservation(
        global_id=payload.get("globalId"),
        category=category,
        observation=payload.get("observation"),
        difference_observed=payload.get("differenceObserved"),
    )


def _difference(value: object) -> ToolingIntakeDifference:
    payload = _object(value, _("Difference Snapshot"))
    try:
        source_kind = ToolingDifferenceSourceKind(str(payload.get("sourceKind")))
    except ValueError:
        frappe.throw(_("Select a supported value."), frappe.ValidationError)
        raise AssertionError("Frappe validation must raise.")
    return ToolingIntakeDifference(
        global_id=payload.get("globalId"),
        source_kind=source_kind,
        source_global_id=payload.get("sourceGlobalId"),
        description=payload.get("description"),
        customer_confirmation_required=payload.get("customerConfirmationRequired"),
    )
