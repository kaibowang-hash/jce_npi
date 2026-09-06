from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    canonical_json,
    canonical_uuid,
    frappe_utc_datetime_text,
    json_array,
    json_object,
    lowercase_sha256,
    optional_uuid,
    require_exact_parent,
    tenant_text,
)
from npi_core.tooling.engineering_controls_domain import (
    CapacityProvenanceKind,
    capacity_scenario_from_snapshot,
    validate_capacity_scenario_successor,
)
from npi_core.tooling.frappe_validation import (
    deny_tooling_history_delete,
    deny_tooling_history_update,
    require_tooling_command_write,
    tooling_domain_value,
)


class NPIToolingCapacityScenarioRevision(Document):
    """Immutable explicit-input Tooling Capacity Scenario revision."""

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
            ("scenario_global_id", _("Capacity Scenario Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("tooling_master_global_id", _("Tooling Master Global ID")),
            ("request_id", _("Request ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.predecessor_global_id = optional_uuid(
            self.predecessor_global_id,
            _("Predecessor Capacity Scenario Global ID"),
        )
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_tooling_history_update()
        supplied = json_object(
            self.scenario_snapshot,
            _("Tooling Capacity Scenario Revision Snapshot"),
        )
        value = tooling_domain_value(lambda: capacity_scenario_from_snapshot(supplied))
        expected = (
            str(value.global_id), str(value.scenario_global_id), value.tenant_id,
            str(value.project_global_id), str(value.tooling_master_global_id),
            value.scenario_version,
            str(value.predecessor_global_id) if value.predecessor_global_id else None,
            value.predecessor_snapshot_hash, value.title,
            value.effective_from.isoformat(), value.target_monthly_assembly_units,
            "capacity.v1", "decimal-6-half-even", str(value.request_id), value.trace_id,
        )
        actual = (
            self.global_id, self.scenario_global_id, self.tenant_id,
            self.project_global_id, self.tooling_master_global_id,
            self.scenario_version, self.predecessor_global_id,
            self.predecessor_snapshot_hash or None, self.title,
            str(self.effective_from), self.target_monthly_assembly_units,
            self.formula_version, self.rounding_rule, self.request_id, self.trace_id,
        )
        if actual != expected:
            frappe.throw(
                _("Tooling Capacity Scenario Revision fields do not match the exact snapshot."),
                frappe.ValidationError,
            )
        if self.version_key_hash not in (None, "", value.version_key_hash):
            frappe.throw(_("Capacity Scenario Version Key Hash does not match."), frappe.ValidationError)
        if self.snapshot_hash not in (None, "", value.snapshot_hash):
            frappe.throw(_("Tooling Capacity Scenario Revision Snapshot Hash does not match."), frappe.ValidationError)
        if json_array(self.input_snapshot, _("Capacity Input Snapshot")) != [item.snapshot_payload() for item in value.lines]:
            frappe.throw(_("Capacity Input Snapshot does not match."), frappe.ValidationError)
        if json_object(self.result_snapshot, _("Capacity Result Snapshot")) != value.result_payload():
            frappe.throw(_("Capacity Result Snapshot does not match."), frappe.ValidationError)
        require_exact_parent(
            "NPI Tooling Master",
            str(value.tooling_master_global_id),
            {"global_id": str(value.tooling_master_global_id), "tenant_id": value.tenant_id},
            _("The Tooling Master is unavailable for this Capacity Scenario."),
        )
        if value.predecessor_global_id is not None:
            predecessor = require_exact_parent(
                "NPI Tooling Capacity Scenario Revision",
                str(value.predecessor_global_id),
                {
                    "global_id": str(value.predecessor_global_id),
                    "scenario_global_id": str(value.scenario_global_id),
                    "tenant_id": value.tenant_id,
                    "project_global_id": str(value.project_global_id),
                    "tooling_master_global_id": str(value.tooling_master_global_id),
                    "snapshot_hash": value.predecessor_snapshot_hash,
                },
                _("The predecessor Capacity Scenario Revision is unavailable."),
                extra_fields=("scenario_snapshot",),
            )
            current = tooling_domain_value(
                lambda: capacity_scenario_from_snapshot(
                    json_object(predecessor["scenario_snapshot"], _("Tooling Capacity Scenario Revision Snapshot"))
                )
            )
            tooling_domain_value(lambda: validate_capacity_scenario_successor(current, value))
        for line in value.lines:
            require_exact_parent(
                "NPI Engineering Part Revision",
                str(line.part_revision_global_id),
                {
                    "global_id": str(line.part_revision_global_id),
                    "tenant_id": value.tenant_id,
                    "snapshot_hash": line.part_revision_snapshot_hash,
                },
                _("A Part Revision is unavailable for this Capacity Scenario."),
            )
            require_exact_parent(
                "NPI Tooling Applicability",
                str(line.applicability_global_id),
                {
                    "global_id": str(line.applicability_global_id),
                    "tenant_id": value.tenant_id,
                    "project_global_id": str(value.project_global_id),
                    "tooling_master_global_id": str(value.tooling_master_global_id),
                    "part_revision_global_id": str(line.part_revision_global_id),
                    "snapshot_hash": line.applicability_snapshot_hash,
                },
                _("A Tooling Applicability is unavailable for this Capacity Scenario."),
            )
            for set_global_id in line.selected_tooling_set_global_ids:
                require_exact_parent(
                    "NPI Tooling Set",
                    str(set_global_id),
                    {
                        "global_id": str(set_global_id),
                        "tenant_id": value.tenant_id,
                        "project_global_id": str(value.project_global_id),
                        "tooling_master_global_id": str(value.tooling_master_global_id),
                    },
                    _("A selected Tooling Set is unavailable for this Capacity Scenario."),
                )
            _require_provenance(line, value)
        self.tooling_master = str(value.tooling_master_global_id)
        self.version_key_hash = value.version_key_hash
        self.reason = value.reason
        self.created_by_user_id = value.created_by_user_id
        self.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
        self.input_snapshot = canonical_json([item.snapshot_payload() for item in value.lines])
        self.result_snapshot = canonical_json(value.result_payload())
        self.scenario_snapshot = canonical_json(value.snapshot_payload())
        self.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))

    def on_trash(self) -> None:
        deny_tooling_history_delete(self)


def _require_provenance(line, value) -> None:
    for provenance in (
        line.cycle_provenance,
        line.cavity_provenance,
        line.usage_provenance,
        line.set_provenance,
    ):
        if provenance.kind is CapacityProvenanceKind.SCENARIO_ASSUMPTION:
            continue
        doctype = {
            CapacityProvenanceKind.CUSTOMER_STANDARD: "NPI Tooling Process Profile Revision",
            CapacityProvenanceKind.TOOLING_REVISION: "NPI Tooling Revision",
            CapacityProvenanceKind.TOOLING_APPLICABILITY: "NPI Tooling Applicability",
            CapacityProvenanceKind.TOOLING_SET_SELECTION: "NPI Tooling Set",
        }[provenance.kind]
        require_exact_parent(
            doctype,
            str(provenance.global_id),
            {
                "global_id": str(provenance.global_id),
                "tenant_id": value.tenant_id,
                "snapshot_hash": provenance.snapshot_hash,
            },
            _("Exact capacity input provenance is unavailable."),
        )
