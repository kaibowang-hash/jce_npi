from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from npi_core.documents.frappe_validation import (
    canonical_json,
    canonical_uuid,
    frappe_utc_datetime_text,
    json_array,
    json_object,
    lowercase_sha256,
    optional_uuid,
    tenant_text,
)
from npi_core.trial.frappe_validation import trial_domain_value
from npi_core.trial.review_domain import (
    comparison_from_snapshot,
    conclusion_from_snapshot,
    policy_from_snapshot,
    review_reference_from_snapshot,
)


def normalize_policy_identity(document: Any) -> None:
    _normalize_identity(
        document,
        (
            ("global_id", _("Global ID")),
            ("policy_global_id", _("Trial Conclusion Policy Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("trial_plan_global_id", _("Trial Plan Global ID")),
            (
                "trial_plan_revision_global_id",
                _("Trial Plan Revision Global ID"),
            ),
            ("request_id", _("Request ID")),
        ),
        (("predecessor_global_id", _("Predecessor Trial Conclusion Policy Global ID")),),
    )


def validate_policy_document(document: Any) -> None:
    supplied = json_object(
        document.policy_snapshot,
        _("Trial Conclusion Policy Version Snapshot"),
    )
    value = trial_domain_value(lambda: policy_from_snapshot(supplied))
    _expect_fields(
        (
            document.global_id,
            document.policy_global_id,
            document.tenant_id,
            document.project_global_id,
            document.trial_plan_global_id,
            document.trial_plan_revision_global_id,
            document.trial_plan_revision_snapshot_hash,
            document.policy_version,
            document.predecessor_global_id or None,
            document.predecessor_snapshot_hash or None,
            int(document.require_cavity_results or 0),
            int(document.block_on_open_blocking_defects or 0),
            int(document.block_on_unverified_required_actions or 0),
            document.published_by_user_id,
            document.request_id,
            document.trace_id,
        ),
        (
            str(value.global_id),
            str(value.policy_global_id),
            value.tenant_id,
            str(value.project_global_id),
            str(value.trial_plan_global_id),
            str(value.trial_plan_revision_global_id),
            value.trial_plan_revision_snapshot_hash,
            value.policy_version,
            str(value.predecessor_global_id) if value.predecessor_global_id else None,
            value.predecessor_snapshot_hash,
            int(value.require_cavity_results),
            int(value.block_on_open_blocking_defects),
            int(value.block_on_unverified_required_actions),
            value.published_by_user_id,
            str(value.request_id),
            value.trace_id,
        ),
        _("Trial conclusion policy fields do not match the exact snapshot."),
    )
    _require_version_hashes(document, value, _("Trial Conclusion Policy"))
    _expect_json_array(
        document.required_parameter_snapshot,
        list(value.required_parameter_keys),
        _("Required Trial Parameter Snapshot"),
    )
    _expect_json_array(
        document.required_dimension_snapshot,
        list(value.required_dimension_keys),
        _("Required Trial Dimension Snapshot"),
    )
    _expect_json_array(
        document.required_reference_kind_snapshot,
        [item.value for item in value.required_reference_kinds],
        _("Required Trial Review Reference Kind Snapshot"),
    )
    _expect_json_array(
        document.allowed_conclusion_code_snapshot,
        [item.value for item in value.allowed_conclusion_codes],
        _("Allowed Trial Conclusion Code Snapshot"),
    )
    _expect_json_array(
        document.out_of_spec_blocking_code_snapshot,
        [item.value for item in value.out_of_spec_blocking_codes],
        _("Out-of-Specification Blocking Code Snapshot"),
    )
    _expect_json_array(
        document.authority_binding_snapshot,
        [item.snapshot_payload() for item in value.authority_bindings],
        _("Trial Conclusion Authority Binding Snapshot"),
    )
    document.trial_plan_revision = str(value.trial_plan_revision_global_id)
    document.version_key_hash = value.version_key_hash
    document.published_at = frappe_utc_datetime_text(value.published_at, _("Published At"))
    document.policy_snapshot = canonical_json(value.snapshot_payload())
    document.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))


def normalize_comparison_identity(document: Any) -> None:
    _normalize_identity(
        document,
        (
            ("global_id", _("Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("trial_plan_global_id", _("Trial Plan Global ID")),
            ("target_round_global_id", _("Target Trial Round Global ID")),
            ("policy_revision_global_id", _("Trial Conclusion Policy Revision Global ID")),
            ("request_id", _("Request ID")),
        ),
    )


def validate_comparison_document(document: Any) -> None:
    supplied = json_object(
        document.comparison_snapshot,
        _("Trial Round Comparison Snapshot"),
    )
    value = trial_domain_value(lambda: comparison_from_snapshot(supplied))
    _expect_fields(
        (
            document.global_id,
            document.tenant_id,
            document.project_global_id,
            document.trial_plan_global_id,
            document.target_round_global_id,
            document.policy_revision_global_id,
            document.policy_revision_snapshot_hash,
            document.formal_erp_quality,
            document.created_by_user_id,
            document.request_id,
            document.trace_id,
        ),
        (
            str(value.global_id),
            value.tenant_id,
            str(value.project_global_id),
            str(value.trial_plan_global_id),
            str(value.target_round_global_id),
            str(value.policy_revision.global_id),
            value.policy_revision.snapshot_hash,
            "unavailable",
            value.created_by_user_id,
            str(value.request_id),
            value.trace_id,
        ),
        _("Trial Round comparison fields do not match the exact snapshot."),
    )
    _require_snapshot_hash(document, value, _("Trial Round Comparison"))
    _expect_json_array(
        document.source_snapshot,
        [item.snapshot_payload() for item in value.sources],
        _("Trial Round Comparison Source Snapshot"),
    )
    _expect_json_array(
        document.input_comparison_snapshot,
        [item.snapshot_payload() for item in value.input_rows],
        _("Trial Input Comparison Snapshot"),
    )
    _expect_json_array(
        document.metric_comparison_snapshot,
        [item.snapshot_payload() for item in value.metric_rows],
        _("Trial Metric Comparison Snapshot"),
    )
    _expect_json_array(
        document.defect_trend_snapshot,
        supplied["defectTrends"],
        _("Trial Defect Trend Snapshot"),
    )
    document.target_round = str(value.target_round_global_id)
    document.policy_revision = str(value.policy_revision.global_id)
    document.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
    document.comparison_snapshot = canonical_json(value.snapshot_payload())
    document.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))


def normalize_reference_identity(document: Any) -> None:
    _normalize_identity(
        document,
        (
            ("global_id", _("Global ID")),
            ("reference_global_id", _("Trial Review Reference Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("trial_round_global_id", _("Trial Round Global ID")),
            ("comparison_snapshot_global_id", _("Trial Round Comparison Global ID")),
            ("part_revision_global_id", _("Part Revision Global ID")),
            ("tooling_master_global_id", _("Tooling Master Global ID")),
            ("tooling_revision_global_id", _("Tooling Revision Global ID")),
            ("tooling_set_global_id", _("Tooling Set Global ID")),
            ("file_revision_global_id", _("File Revision Global ID")),
            ("request_id", _("Request ID")),
        ),
        (("predecessor_global_id", _("Predecessor Trial Review Reference Global ID")),),
    )


def validate_reference_document(document: Any) -> None:
    supplied = json_object(
        document.reference_snapshot,
        _("Trial Review Reference Revision Snapshot"),
    )
    value = trial_domain_value(lambda: review_reference_from_snapshot(supplied))
    _expect_fields(
        (
            document.global_id,
            document.reference_global_id,
            document.tenant_id,
            document.project_global_id,
            document.trial_round_global_id,
            document.comparison_snapshot_global_id,
            document.comparison_snapshot_hash,
            document.reference_kind,
            document.reference_version,
            document.predecessor_global_id or None,
            document.predecessor_snapshot_hash or None,
            document.part_revision_global_id,
            document.part_revision_snapshot_hash,
            document.tooling_master_global_id,
            document.tooling_revision_global_id,
            document.tooling_revision_snapshot_hash,
            document.tooling_set_global_id,
            document.tooling_set_snapshot_hash,
            document.file_revision_global_id,
            document.file_revision_snapshot_hash,
            document.approval_authority,
            document.reason,
            document.created_by_user_id,
            document.request_id,
            document.trace_id,
        ),
        (
            str(value.global_id),
            str(value.reference_global_id),
            value.tenant_id,
            str(value.project_global_id),
            str(value.trial_round_global_id),
            str(value.comparison_snapshot.global_id),
            value.comparison_snapshot.snapshot_hash,
            value.reference_kind.value,
            value.reference_version,
            str(value.predecessor_global_id) if value.predecessor_global_id else None,
            value.predecessor_snapshot_hash,
            str(value.part_revision.global_id),
            value.part_revision.snapshot_hash,
            str(value.tooling_master_global_id),
            str(value.tooling_revision.global_id),
            value.tooling_revision.snapshot_hash,
            str(value.tooling_set.global_id),
            value.tooling_set.snapshot_hash,
            str(value.file_revision.global_id),
            value.file_revision.snapshot_hash,
            "unavailable",
            value.reason,
            value.created_by_user_id,
            str(value.request_id),
            value.trace_id,
        ),
        _("Trial review reference fields do not match the exact snapshot."),
    )
    _require_version_hashes(document, value, _("Trial Review Reference"))
    document.trial_round = str(value.trial_round_global_id)
    document.comparison_snapshot_revision = str(value.comparison_snapshot.global_id)
    document.tooling_master = str(value.tooling_master_global_id)
    document.tooling_revision = str(value.tooling_revision.global_id)
    document.tooling_set = str(value.tooling_set.global_id)
    document.file_revision = str(value.file_revision.global_id)
    document.version_key_hash = value.version_key_hash
    document.effective_from = value.effective_from
    document.effective_to = value.effective_to
    document.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
    document.reference_snapshot = canonical_json(value.snapshot_payload())
    document.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))


def normalize_conclusion_identity(document: Any) -> None:
    _normalize_identity(
        document,
        (
            ("global_id", _("Global ID")),
            ("conclusion_global_id", _("Trial Conclusion Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("trial_round_global_id", _("Trial Round Global ID")),
            ("policy_revision_global_id", _("Trial Conclusion Policy Revision Global ID")),
            ("comparison_snapshot_global_id", _("Trial Round Comparison Global ID")),
            ("request_id", _("Request ID")),
        ),
        (("predecessor_global_id", _("Predecessor Trial Conclusion Global ID")),),
    )


def validate_conclusion_document(document: Any) -> None:
    supplied = json_object(
        document.conclusion_snapshot,
        _("Trial Conclusion Revision Snapshot"),
    )
    value = trial_domain_value(lambda: conclusion_from_snapshot(supplied))
    _expect_fields(
        (
            document.global_id,
            document.conclusion_global_id,
            document.tenant_id,
            document.project_global_id,
            document.trial_round_global_id,
            document.trial_round_optimistic_version,
            document.trial_round_snapshot_hash,
            document.conclusion_version,
            document.predecessor_global_id or None,
            document.predecessor_snapshot_hash or None,
            document.state,
            document.conclusion_code,
            document.policy_revision_global_id,
            document.policy_revision_snapshot_hash,
            document.comparison_snapshot_global_id,
            document.comparison_snapshot_hash,
            document.proposed_gate_effect,
            document.proposed_npi_effect,
            document.reason,
            document.created_by_user_id,
            document.request_id,
            document.trace_id,
        ),
        (
            str(value.global_id),
            str(value.conclusion_global_id),
            value.tenant_id,
            str(value.project_global_id),
            str(value.trial_round_global_id),
            value.trial_round_optimistic_version,
            value.trial_round_snapshot_hash,
            value.conclusion_version,
            str(value.predecessor_global_id) if value.predecessor_global_id else None,
            value.predecessor_snapshot_hash,
            value.state.value,
            value.conclusion_code.value,
            str(value.policy_revision.global_id),
            value.policy_revision.snapshot_hash,
            str(value.comparison_snapshot.global_id),
            value.comparison_snapshot.snapshot_hash,
            value.proposed_gate_effect,
            value.proposed_npi_effect,
            value.reason,
            value.created_by_user_id,
            str(value.request_id),
            value.trace_id,
        ),
        _("Trial conclusion fields do not match the exact snapshot."),
    )
    _require_version_hashes(document, value, _("Trial Conclusion"))
    _expect_json_array(
        document.review_reference_snapshot,
        [item.snapshot_payload() for item in value.review_references],
        _("Trial Review Reference Snapshot"),
    )
    _expect_json_array(
        document.blocker_snapshot,
        [item.snapshot_payload() for item in value.blockers],
        _("Trial Conclusion Blocker Snapshot"),
    )
    _expect_json_object(
        document.summary_input_snapshot,
        value.summary_input,
        _("Trial One-Page Summary Input Snapshot"),
    )
    _expect_json_array(
        document.proposed_next_work_snapshot,
        list(value.proposed_next_work),
        _("Proposed Next Trial Work Snapshot"),
    )
    _expect_json_object(
        document.external_effect_snapshot,
        supplied["externalEffects"],
        _("Trial Conclusion External Effect Snapshot"),
    )
    document.trial_round = str(value.trial_round_global_id)
    document.policy_revision = str(value.policy_revision.global_id)
    document.comparison_snapshot_revision = str(value.comparison_snapshot.global_id)
    document.version_key_hash = value.version_key_hash
    document.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
    document.conclusion_snapshot = canonical_json(value.snapshot_payload())
    document.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))


def _normalize_identity(
    document: Any,
    fields: tuple[tuple[str, str], ...],
    optional_fields: tuple[tuple[str, str], ...] = (),
) -> None:
    for fieldname, label in fields:
        setattr(document, fieldname, canonical_uuid(getattr(document, fieldname), label))
    for fieldname, label in optional_fields:
        setattr(document, fieldname, optional_uuid(getattr(document, fieldname), label))
    document.tenant_id = tenant_text(document.tenant_id)


def _expect_fields(actual: tuple[object, ...], expected: tuple[object, ...], message: str) -> None:
    if actual != expected:
        frappe.throw(message, frappe.ValidationError)


def _expect_json_array(supplied: object, expected: list[object], label: str) -> None:
    if json_array(supplied, label) != expected:
        frappe.throw(
            _("{object} does not match the exact snapshot.").format(object=label),
            frappe.ValidationError,
        )


def _expect_json_object(supplied: object, expected: dict[str, object], label: str) -> None:
    if json_object(supplied, label) != expected:
        frappe.throw(
            _("{object} does not match the exact snapshot.").format(object=label),
            frappe.ValidationError,
        )


def _require_version_hashes(document: Any, value: Any, label: str) -> None:
    if document.version_key_hash not in (None, "", value.version_key_hash):
        frappe.throw(
            _("{object} Version Key Hash does not match.").format(object=label),
            frappe.ValidationError,
        )
    _require_snapshot_hash(document, value, label)


def _require_snapshot_hash(document: Any, value: Any, label: str) -> None:
    if document.snapshot_hash not in (None, "", value.snapshot_hash):
        frappe.throw(
            _("{object} Snapshot Hash does not match.").format(object=label),
            frappe.ValidationError,
        )
