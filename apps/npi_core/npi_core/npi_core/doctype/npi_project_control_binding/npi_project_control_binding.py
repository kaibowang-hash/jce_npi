from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.project_controls.frappe_validation import (
    canonical_datetime,
    canonicalize_json,
    deny_project_control_history_delete,
    normalize_uuid_fields,
    require_actor,
    require_positive_integer,
    require_project_control_write,
    require_request_id,
    require_snapshot_hash,
    require_trace_id,
)


class NPIProjectControlBinding(Document):
    def before_insert(self) -> None:
        require_project_control_write()

    def before_save(self) -> None:
        require_project_control_write()
        if self.get_doc_before_save() is not None:
            frappe.throw(
                _("A Project Control Binding is immutable."),
                frappe.PermissionError,
            )

    def on_trash(self) -> None:
        deny_project_control_history_delete()

    def validate(self) -> None:
        normalize_uuid_fields(
            self,
            ("global_id", "project_global_id", "policy_global_id"),
        )
        if not self.tenant_id:
            frappe.throw(_("Tenant ID is required."), frappe.ValidationError)
        require_positive_integer(
            self.binding_version,
            _("Control Binding Version"),
        )
        require_positive_integer(self.policy_version, _("Policy Version"))
        require_positive_integer(self.project_version, _("Project Version"))
        policy_snapshot, self.policy_snapshot = canonicalize_json(
            self.policy_snapshot,
            expected_type=dict,
            label=_("Policy Snapshot"),
        )
        self.policy_snapshot_hash = require_snapshot_hash(
            policy_snapshot,
            self.policy_snapshot_hash,
            _("Policy Snapshot Hash"),
        )
        bindings, self.authority_bindings = canonicalize_json(
            self.authority_bindings,
            expected_type=list,
            label=_("Project Control Authority Bindings"),
        )
        _validate_bindings(bindings)
        self.bound_by = require_actor(self.bound_by, _("Bound By"))
        self.request_id = require_request_id(self.request_id)
        self.trace_id = require_trace_id(self.trace_id)
        binding_snapshot, self.binding_snapshot = canonicalize_json(
            self.binding_snapshot,
            expected_type=dict,
            label=_("Control Binding Snapshot"),
        )
        self.snapshot_hash = require_snapshot_hash(
            binding_snapshot,
            self.snapshot_hash,
            _("Snapshot Hash"),
        )
        required = {
            "schemaVersion",
            "globalId",
            "tenantId",
            "projectGlobalId",
            "bindingVersion",
            "policyRef",
            "policySnapshotHash",
            "authorityBindings",
            "boundBy",
            "boundAt",
            "projectVersion",
            "requestId",
            "traceId",
        }
        policy_ref = binding_snapshot.get("policyRef")
        if (
            set(binding_snapshot) != required
            or binding_snapshot.get("schemaVersion") != 1
            or not isinstance(policy_ref, dict)
            or set(policy_ref) != {"globalId", "version", "snapshotHash"}
            or binding_snapshot.get("globalId") != self.global_id
            or binding_snapshot.get("tenantId") != self.tenant_id
            or binding_snapshot.get("projectGlobalId") != self.project_global_id
            or binding_snapshot.get("bindingVersion") != self.binding_version
            or policy_ref["globalId"] != self.policy_global_id
            or policy_ref["version"] != self.policy_version
            or policy_ref["snapshotHash"] != self.policy_snapshot_hash
            or binding_snapshot.get("policySnapshotHash")
            != self.policy_snapshot_hash
            or binding_snapshot.get("authorityBindings") != bindings
            or binding_snapshot.get("boundBy") != self.bound_by
            or canonical_datetime(
                binding_snapshot.get("boundAt"),
                _("Bound At"),
            )
            != canonical_datetime(self.bound_at, _("Bound At"))
            or binding_snapshot.get("projectVersion") != self.project_version
            or binding_snapshot.get("requestId") != self.request_id
            or binding_snapshot.get("traceId") != self.trace_id
        ):
            frappe.throw(
                _("Control Binding Snapshot does not match the binding record."),
                frappe.ValidationError,
            )


def _validate_bindings(value: list[object]) -> None:
    if not value or len(value) > 64:
        frappe.throw(
            _("Add one valid Project Control authority binding per slot."),
            frappe.ValidationError,
        )
    slots: set[str] = set()
    for binding in value:
        if not isinstance(binding, dict) or set(binding) != {
            "slot",
            "memberGlobalId",
            "userId",
            "displayName",
        }:
            frappe.throw(
                _("Enter valid Project Control authority bindings."),
                frappe.ValidationError,
            )
        slot = str(binding["slot"])
        if (
            not slot
            or len(slot) > 64
            or slot in slots
            or not isinstance(binding["userId"], str)
            or not binding["userId"]
            or len(binding["userId"]) > 254
            or binding["userId"] != binding["userId"].casefold()
            or not isinstance(binding["displayName"], str)
            or not binding["displayName"].strip()
            or len(binding["displayName"].strip()) > 140
        ):
            frappe.throw(
                _("Enter valid Project Control authority bindings."),
                frappe.ValidationError,
            )
        try:
            from uuid import UUID

            UUID(str(binding["memberGlobalId"]))
        except (TypeError, ValueError, AttributeError):
            frappe.throw(
                _("Enter valid Project Control authority bindings."),
                frappe.ValidationError,
            )
        slots.add(slot)
