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
    require_controlled_key,
    require_hash,
    require_positive_integer,
    require_project_control_write,
    require_request_id,
    require_snapshot_hash,
    require_text,
    require_trace_id,
)


class NPIProjectHealthAssessment(Document):
    def before_insert(self) -> None:
        require_project_control_write()

    def before_save(self) -> None:
        require_project_control_write()
        if self.get_doc_before_save() is not None:
            frappe.throw(
                _("A Project Health Assessment is immutable."),
                frappe.PermissionError,
            )

    def on_trash(self) -> None:
        deny_project_control_history_delete()

    def validate(self) -> None:
        normalize_uuid_fields(
            self,
            (
                "global_id",
                "project_global_id",
                "binding_global_id",
                "policy_global_id",
                "actor_member_global_id",
            ),
        )
        if not self.tenant_id:
            frappe.throw(_("Tenant ID is required."), frappe.ValidationError)
        require_positive_integer(self.policy_version, _("Policy Version"))
        self.policy_snapshot_hash = require_hash(
            self.policy_snapshot_hash,
            _("Policy Snapshot Hash"),
        )
        self.actor_user_id = require_actor(
            self.actor_user_id,
            _("Actor User ID"),
        )
        self.actor_authority_slot = require_controlled_key(
            self.actor_authority_slot,
            _("Actor Authority Slot"),
        )
        self.actor_display_name = require_text(
            self.actor_display_name,
            _("Actor Display Name"),
            maximum=140,
        )
        require_positive_integer(self.project_version, _("Project Version"))
        self.request_id = require_request_id(self.request_id)
        self.trace_id = require_trace_id(self.trace_id)
        snapshot, self.assessment_snapshot = canonicalize_json(
            self.assessment_snapshot,
            expected_type=dict,
            label=_("Project Health Assessment Snapshot"),
        )
        self.snapshot_hash = require_snapshot_hash(
            snapshot,
            self.snapshot_hash,
            _("Snapshot Hash"),
        )
        required = {
            "schemaVersion",
            "globalId",
            "tenantId",
            "projectGlobalId",
            "bindingGlobalId",
            "policyRef",
            "actor",
            "assessedAt",
            "projectVersion",
            "measurements",
            "evaluation",
            "requestId",
            "traceId",
        }
        policy_ref = snapshot.get("policyRef")
        actor = snapshot.get("actor")
        if (
            set(snapshot) != required
            or not isinstance(policy_ref, dict)
            or set(policy_ref) != {"globalId", "version", "snapshotHash"}
            or not isinstance(actor, dict)
            or set(actor)
            != {"slot", "memberGlobalId", "userId", "displayName"}
            or not isinstance(snapshot.get("measurements"), list)
            or not isinstance(snapshot.get("evaluation"), dict)
            or snapshot["schemaVersion"] != 1
            or snapshot["globalId"] != self.global_id
            or snapshot["tenantId"] != self.tenant_id
            or snapshot["projectGlobalId"] != self.project_global_id
            or snapshot["bindingGlobalId"] != self.binding_global_id
            or policy_ref["globalId"] != self.policy_global_id
            or policy_ref["version"] != self.policy_version
            or policy_ref["snapshotHash"] != self.policy_snapshot_hash
            or actor["slot"] != self.actor_authority_slot
            or actor["memberGlobalId"] != self.actor_member_global_id
            or require_actor(actor["userId"], _("Actor User ID"))
            != self.actor_user_id
            or actor["displayName"] != self.actor_display_name
            or canonical_datetime(
                snapshot["assessedAt"],
                _("Assessed At"),
            )
            != canonical_datetime(self.assessed_at, _("Assessed At"))
            or snapshot["projectVersion"] != self.project_version
            or snapshot["requestId"] != self.request_id
            or snapshot["traceId"] != self.trace_id
        ):
            frappe.throw(
                _("Project Health Assessment Snapshot does not match the record."),
                frappe.ValidationError,
            )
        _validate_measurements(snapshot["measurements"])
        _validate_evaluation(snapshot["evaluation"], policy_ref)


def _validate_measurements(value: list[object]) -> None:
    if len(value) > 4:
        _invalid_snapshot()
    dimensions: set[str] = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != {
            "dimension",
            "numericValue",
            "manualStatus",
        }:
            _invalid_snapshot()
        dimension = item["dimension"]
        if (
            dimension not in {"progress", "cost", "quality", "risk"}
            or dimension in dimensions
            or (
                item["numericValue"] is not None
                and not isinstance(item["numericValue"], str)
            )
            or (
                item["manualStatus"] is not None
                and item["manualStatus"] not in {"green", "yellow", "red"}
            )
            or (
                item["numericValue"] is not None
                and item["manualStatus"] is not None
            )
        ):
            _invalid_snapshot()
        dimensions.add(str(dimension))


def _validate_evaluation(
    value: dict[str, object],
    policy_ref: dict[str, object],
) -> None:
    if set(value) != {
        "policyRef",
        "dimensionResults",
        "overallStatus",
        "reason",
        "recoveryPlan",
    } or value["policyRef"] != policy_ref:
        _invalid_snapshot()
    results = value["dimensionResults"]
    if not isinstance(results, list) or len(results) != 4:
        _invalid_snapshot()
    dimensions: set[str] = set()
    has_red = False
    for result in results:
        if not isinstance(result, dict) or set(result) != {
            "dimension",
            "ruleMode",
            "status",
            "numericValue",
        }:
            _invalid_snapshot()
        dimension = result["dimension"]
        status = result["status"]
        if (
            dimension not in {"progress", "cost", "quality", "risk"}
            or dimension in dimensions
            or result["ruleMode"]
            not in {
                "manual",
                "higher_is_better",
                "lower_is_better",
                "unavailable",
            }
            or status
            not in {
                "green",
                "yellow",
                "red",
                "unassessed",
                "unavailable",
            }
            or (
                result["numericValue"] is not None
                and not isinstance(result["numericValue"], str)
            )
        ):
            _invalid_snapshot()
        dimensions.add(str(dimension))
        has_red = has_red or status == "red"
    overall = value["overallStatus"]
    if overall not in {
        "green",
        "yellow",
        "red",
        "unassessed",
        "unavailable",
    }:
        _invalid_snapshot()
    if has_red or overall == "red":
        if (
            not isinstance(value["reason"], str)
            or not value["reason"].strip()
            or not isinstance(value["recoveryPlan"], str)
            or not value["recoveryPlan"].strip()
        ):
            _invalid_snapshot()


def _invalid_snapshot() -> None:
    frappe.throw(
        _("Project Health Assessment Snapshot has an invalid structure."),
        frappe.ValidationError,
    )
