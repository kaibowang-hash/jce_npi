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
    require_exact_parent,
    tenant_text,
)
from npi_core.tooling.engineering_controls_domain import defect_revision_from_snapshot
from npi_core.trial.frappe_validation import trial_domain_value
from npi_core.trial.quality_diagnostics import quality_type_error_stage
from npi_core.trial.quality_domain import (
    TrialDefectPredecessorKind,
    TrialDefectRevision,
    cavity_result_from_snapshot,
    trial_defect_from_snapshot,
    validate_cavity_result_successor,
    validate_trial_defect_successor,
    validate_trial_defect_verification,
    verification_from_snapshot,
)


def normalize_cavity_result_identity(document: Any) -> None:
    _normalize_identity(
        document,
        (
            ("global_id", _("Global ID")),
            ("cavity_result_global_id", _("Trial Cavity Result Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("trial_round_global_id", _("Trial Round Global ID")),
            ("input_lock_revision_global_id", _("Trial Input Lock Revision Global ID")),
            ("sample_batch_revision_global_id", _("Trial Sample Batch Revision Global ID")),
            ("tooling_revision_global_id", _("Tooling Revision Global ID")),
            ("tooling_set_global_id", _("Tooling Set Global ID")),
            ("cavity_global_id", _("Cavity Global ID")),
            ("request_id", _("Request ID")),
        ),
        (("predecessor_global_id", _("Predecessor Trial Cavity Result Revision Global ID")),),
    )


def validate_cavity_result_document(document: Any) -> None:
    supplied = json_object(
        document.cavity_result_snapshot,
        _("Trial Cavity Result Revision Snapshot"),
    )
    value = trial_domain_value(lambda: cavity_result_from_snapshot(supplied))
    expected = (
        str(value.global_id),
        str(value.cavity_result_global_id),
        value.tenant_id,
        str(value.project_global_id),
        str(value.trial_round_global_id),
        str(value.input_lock_revision_global_id),
        value.input_lock_revision_snapshot_hash,
        str(value.sample_batch_revision_global_id),
        value.sample_batch_revision_snapshot_hash,
        str(value.tooling_revision_global_id),
        value.tooling_revision_snapshot_hash,
        str(value.tooling_set_global_id),
        value.tooling_set_snapshot_hash,
        str(value.cavity_global_id),
        value.result_version,
        str(value.predecessor_global_id) if value.predecessor_global_id else None,
        value.predecessor_snapshot_hash,
        value.reason,
        value.created_by_user_id,
        str(value.request_id),
        value.trace_id,
    )
    actual = (
        document.global_id,
        document.cavity_result_global_id,
        document.tenant_id,
        document.project_global_id,
        document.trial_round_global_id,
        document.input_lock_revision_global_id,
        document.input_lock_revision_snapshot_hash,
        document.sample_batch_revision_global_id,
        document.sample_batch_revision_snapshot_hash,
        document.tooling_revision_global_id,
        document.tooling_revision_snapshot_hash,
        document.tooling_set_global_id,
        document.tooling_set_snapshot_hash,
        document.cavity_global_id,
        document.result_version,
        document.predecessor_global_id or None,
        document.predecessor_snapshot_hash or None,
        document.reason,
        document.created_by_user_id,
        document.request_id,
        document.trace_id,
    )
    if actual != expected:
        frappe.throw(
            _("Trial cavity result fields do not match the exact snapshot."),
            frappe.ValidationError,
        )
    _require_hashes(document, value, _("Trial Cavity Result"))
    if json_array(document.measurement_snapshot, _("Trial Cavity Measurement Snapshot")) != [
        item.snapshot_payload() for item in value.measurements
    ]:
        frappe.throw(
            _("Cavity measurements do not match the exact result snapshot."),
            frappe.ValidationError,
        )
    if json_array(document.evidence_snapshot, _("Trial Quality Evidence Snapshot")) != [
        item.snapshot_payload() for item in value.evidence
    ]:
        frappe.throw(
            _("Trial quality evidence does not match the exact result snapshot."),
            frappe.ValidationError,
        )
    _require_running_round(
        tenant_id=value.tenant_id,
        project_global_id=str(value.project_global_id),
        round_global_id=str(value.trial_round_global_id),
    )
    _require_trial_context(value)
    _require_quality_evidence(value, require_measurement_report=True)
    if value.predecessor_global_id is not None:
        predecessor = require_exact_parent(
            "NPI Trial Cavity Result Revision",
            str(value.predecessor_global_id),
            {
                "global_id": str(value.predecessor_global_id),
                "cavity_result_global_id": str(value.cavity_result_global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "result_version": value.result_version - 1,
                "snapshot_hash": value.predecessor_snapshot_hash,
            },
            _("The exact predecessor Trial cavity result is unavailable."),
            extra_fields=("cavity_result_snapshot",),
        )
        current = trial_domain_value(
            lambda: cavity_result_from_snapshot(
                json_object(
                    predecessor["cavity_result_snapshot"],
                    _("Trial Cavity Result Revision Snapshot"),
                )
            )
        )
        trial_domain_value(lambda: validate_cavity_result_successor(current, value))
    document.trial_round = str(value.trial_round_global_id)
    document.input_lock_revision = str(value.input_lock_revision_global_id)
    document.sample_batch_revision = str(value.sample_batch_revision_global_id)
    document.tooling_revision = str(value.tooling_revision_global_id)
    document.tooling_set = str(value.tooling_set_global_id)
    document.version_key_hash = value.version_key_hash
    document.measurement_snapshot = canonical_json(
        [item.snapshot_payload() for item in value.measurements]
    )
    document.evidence_snapshot = canonical_json(
        [item.snapshot_payload() for item in value.evidence]
    )
    document.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
    document.cavity_result_snapshot = canonical_json(value.snapshot_payload())
    document.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))


def normalize_trial_defect_identity(document: Any) -> None:
    _normalize_identity(
        document,
        (
            ("global_id", _("Global ID")),
            ("defect_global_id", _("NPI Defect Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("tooling_master_global_id", _("Tooling Master Global ID")),
            ("trial_round_global_id", _("Trial Round Global ID")),
            ("input_lock_revision_global_id", _("Trial Input Lock Revision Global ID")),
            ("tooling_revision_global_id", _("Tooling Revision Global ID")),
            ("tooling_set_global_id", _("Tooling Set Global ID")),
            ("cavity_global_id", _("Cavity Global ID")),
            ("request_id", _("Request ID")),
        ),
        (
            ("sample_batch_revision_global_id", _("Trial Sample Batch Revision Global ID")),
            ("predecessor_global_id", _("Predecessor NPI Defect Revision Global ID")),
        ),
    )


def validate_trial_defect_document(document: Any) -> None:
    supplied = json_object(
        document.trial_defect_snapshot,
        _("Trial Defect Revision Snapshot"),
    )
    with quality_type_error_stage(
        "P703_QUALITY_DEFECT_SNAPSHOT_PARSE",
        str(document.trace_id),
    ):
        value = trial_domain_value(lambda: trial_defect_from_snapshot(supplied))
    expected = (
        str(value.global_id), str(value.defect_global_id), value.tenant_id,
        str(value.project_global_id), str(value.tooling_master_global_id),
        str(value.trial_round_global_id), value.trial_round_optimistic_version,
        value.trial_round_snapshot_hash, str(value.input_lock_revision_global_id),
        value.input_lock_revision_snapshot_hash, str(value.tooling_revision_global_id),
        value.tooling_revision_snapshot_hash, str(value.tooling_set_global_id),
        value.tooling_set_snapshot_hash, str(value.cavity_global_id),
        str(value.sample_batch_revision_global_id) if value.sample_batch_revision_global_id else None,
        value.sample_batch_revision_snapshot_hash, value.defect_version,
        value.predecessor_kind.value if value.predecessor_kind else None,
        str(value.predecessor_global_id) if value.predecessor_global_id else None,
        value.predecessor_snapshot_hash, value.business_code, value.title,
        value.description, value.category_key, value.location, value.severity.value,
        int(value.blocking), value.state.value, value.root_cause_state.value,
        value.root_cause, str(value.responsible_member.global_id) if value.responsible_member else None,
        value.occurrence_count, value.reason, value.created_by_user_id,
        str(value.request_id), value.trace_id,
    )
    actual = (
        document.global_id, document.defect_global_id, document.tenant_id,
        document.project_global_id, document.tooling_master_global_id,
        document.trial_round_global_id, document.trial_round_optimistic_version,
        document.trial_round_snapshot_hash, document.input_lock_revision_global_id,
        document.input_lock_revision_snapshot_hash, document.tooling_revision_global_id,
        document.tooling_revision_snapshot_hash, document.tooling_set_global_id,
        document.tooling_set_snapshot_hash, document.cavity_global_id,
        document.sample_batch_revision_global_id or None,
        document.sample_batch_revision_snapshot_hash or None, document.defect_version,
        document.predecessor_kind or None, document.predecessor_global_id or None,
        document.predecessor_snapshot_hash or None, document.business_code, document.title,
        document.description, document.category_key, document.location, document.severity,
        int(document.blocking or 0), document.state, document.root_cause_state,
        document.root_cause or None, document.responsible_member_global_id or None,
        document.occurrence_count, document.reason, document.created_by_user_id,
        document.request_id, document.trace_id,
    )
    if actual != expected:
        frappe.throw(
            _("Trial defect fields do not match the exact snapshot."),
            frappe.ValidationError,
        )
    _require_hashes(document, value, _("Trial Defect"))
    if json_array(document.action_snapshot, _("Trial Defect Action Snapshot")) != [
        item.snapshot_payload() for item in value.actions
    ]:
        frappe.throw(
            _("Trial defect actions do not match the exact snapshot."),
            frappe.ValidationError,
        )
    if json_array(document.evidence_snapshot, _("Trial Quality Evidence Snapshot")) != [
        item.snapshot_payload() for item in value.evidence
    ]:
        frappe.throw(
            _("Trial quality evidence does not match the exact defect snapshot."),
            frappe.ValidationError,
        )
    if json_object(document.external_effect_snapshot, _("Trial Defect External Effect Snapshot")) != supplied["externalEffects"]:
        frappe.throw(
            _("Trial defect external effects do not match the exact snapshot."),
            frappe.ValidationError,
        )
    with quality_type_error_stage(
        "P703_QUALITY_DEFECT_RUNNING_ROUND",
        value.trace_id,
    ):
        _require_running_round(
            tenant_id=value.tenant_id,
            project_global_id=str(value.project_global_id),
            round_global_id=str(value.trial_round_global_id),
            optimistic_version=value.trial_round_optimistic_version,
            snapshot_hash=value.trial_round_snapshot_hash,
        )
    with quality_type_error_stage("P703_QUALITY_DEFECT_CONTEXT", value.trace_id):
        _require_trial_context(value)
    with quality_type_error_stage(
        "P703_QUALITY_DEFECT_RESPONSIBILITY",
        value.trace_id,
    ):
        _require_member(value.responsible_member, value)
        for item in value.actions:
            _require_member(item.responsible_member, value)
            _require_round_reference(
                value.tenant_id,
                str(value.project_global_id),
                str(item.target_round_global_id),
                item.target_round_optimistic_version,
                item.target_round_snapshot_hash,
            )
            if item.verification_revision_global_id is not None:
                require_exact_parent(
                    "NPI Trial Defect Verification Revision",
                    str(item.verification_revision_global_id),
                    {
                        "global_id": str(item.verification_revision_global_id),
                        "tenant_id": value.tenant_id,
                        "project_global_id": str(value.project_global_id),
                        "defect_global_id": str(value.defect_global_id),
                        "action_global_id": str(item.global_id),
                        "result": "pass",
                        "snapshot_hash": item.verification_revision_snapshot_hash,
                    },
                    _("The exact successful defect verification is unavailable."),
                )
    predecessor_value: Any = None
    if value.predecessor_global_id is not None:
        with quality_type_error_stage(
            "P703_QUALITY_DEFECT_PREDECESSOR",
            value.trace_id,
        ):
            predecessor_doctype = (
                "NPI Tooling Defect Revision"
                if value.predecessor_kind
                is TrialDefectPredecessorKind.TOOLING_DEFECT_REVISION
                else "NPI Trial Defect Revision"
            )
            snapshot_field = (
                "defect_snapshot"
                if value.predecessor_kind
                is TrialDefectPredecessorKind.TOOLING_DEFECT_REVISION
                else "trial_defect_snapshot"
            )
            predecessor = require_exact_parent(
                predecessor_doctype,
                str(value.predecessor_global_id),
                {
                    "global_id": str(value.predecessor_global_id),
                    "defect_global_id": str(value.defect_global_id),
                    "tenant_id": value.tenant_id,
                    "project_global_id": str(value.project_global_id),
                    "tooling_master_global_id": str(value.tooling_master_global_id),
                    "defect_version": value.defect_version - 1,
                    "snapshot_hash": value.predecessor_snapshot_hash,
                },
                _("The exact predecessor NPI defect revision is unavailable."),
                extra_fields=(snapshot_field,),
            )
            parser = (
                defect_revision_from_snapshot
                if value.predecessor_kind
                is TrialDefectPredecessorKind.TOOLING_DEFECT_REVISION
                else trial_defect_from_snapshot
            )
            predecessor_value = trial_domain_value(
                lambda: parser(
                    json_object(
                        predecessor[snapshot_field],
                        _("NPI Defect Revision Snapshot"),
                    )
                )
            )
            trial_domain_value(
                lambda: validate_trial_defect_successor(predecessor_value, value)
            )
    retained_evidence = (
        {
            item.global_id: item.snapshot_hash
            for item in predecessor_value.evidence
        }
        if isinstance(predecessor_value, TrialDefectRevision)
        else {}
    )
    with quality_type_error_stage("P703_QUALITY_DEFECT_EVIDENCE", value.trace_id):
        _require_quality_evidence(
            value,
            require_measurement_report=False,
            retained_evidence=retained_evidence,
        )
    with quality_type_error_stage("P703_QUALITY_DEFECT_NORMALIZE", value.trace_id):
        document.tooling_master = str(value.tooling_master_global_id)
        document.trial_round = str(value.trial_round_global_id)
        document.input_lock_revision = str(value.input_lock_revision_global_id)
        document.tooling_revision = str(value.tooling_revision_global_id)
        document.tooling_set = str(value.tooling_set_global_id)
        document.sample_batch_revision = (
            str(value.sample_batch_revision_global_id)
            if value.sample_batch_revision_global_id
            else None
        )
        document.responsible_member = (
            str(value.responsible_member.global_id)
            if value.responsible_member
            else None
        )
        document.version_key_hash = value.version_key_hash
        document.action_snapshot = canonical_json(
            [item.snapshot_payload() for item in value.actions]
        )
        document.evidence_snapshot = canonical_json(
            [item.snapshot_payload() for item in value.evidence]
        )
        document.external_effect_snapshot = canonical_json(supplied["externalEffects"])
        document.created_at = frappe_utc_datetime_text(
            value.created_at,
            _("Created At"),
        )
        document.trial_defect_snapshot = canonical_json(value.snapshot_payload())
        document.snapshot_hash = lowercase_sha256(
            value.snapshot_hash,
            _("Snapshot Hash"),
        )


def normalize_verification_identity(document: Any) -> None:
    _normalize_identity(
        document,
        (
            ("global_id", _("Global ID")),
            ("verification_global_id", _("Trial Defect Verification Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("defect_global_id", _("NPI Defect Global ID")),
            ("defect_revision_global_id", _("Trial Defect Revision Global ID")),
            ("action_global_id", _("Trial Defect Action Global ID")),
            ("target_round_global_id", _("Target Trial Round Global ID")),
            ("verification_round_global_id", _("Verification Trial Round Global ID")),
            ("cavity_result_revision_global_id", _("Trial Cavity Result Revision Global ID")),
            ("verifier_member_global_id", _("Verifier Project Member Global ID")),
            ("request_id", _("Request ID")),
        ),
    )


def validate_verification_document(document: Any) -> None:
    supplied = json_object(
        document.verification_snapshot,
        _("Trial Defect Verification Revision Snapshot"),
    )
    value = trial_domain_value(lambda: verification_from_snapshot(supplied))
    expected = (
        str(value.global_id), str(value.verification_global_id), value.attempt_sequence,
        value.tenant_id, str(value.project_global_id), str(value.defect_global_id),
        str(value.defect_revision_global_id), value.defect_revision_snapshot_hash,
        str(value.action_global_id), str(value.target_round_global_id),
        value.target_round_optimistic_version, value.target_round_snapshot_hash,
        str(value.verification_round_global_id), value.verification_round_optimistic_version,
        value.verification_round_snapshot_hash, str(value.cavity_result_revision_global_id),
        value.cavity_result_revision_snapshot_hash, str(value.verifier_member.global_id),
        value.result.value, value.finding, value.created_by_user_id,
        str(value.request_id), value.trace_id,
    )
    actual = (
        document.global_id, document.verification_global_id, document.attempt_sequence,
        document.tenant_id, document.project_global_id, document.defect_global_id,
        document.defect_revision_global_id, document.defect_revision_snapshot_hash,
        document.action_global_id, document.target_round_global_id,
        document.target_round_optimistic_version, document.target_round_snapshot_hash,
        document.verification_round_global_id, document.verification_round_optimistic_version,
        document.verification_round_snapshot_hash, document.cavity_result_revision_global_id,
        document.cavity_result_revision_snapshot_hash, document.verifier_member_global_id,
        document.result, document.finding, document.created_by_user_id,
        document.request_id, document.trace_id,
    )
    if actual != expected:
        frappe.throw(
            _("Trial defect verification fields do not match the exact snapshot."),
            frappe.ValidationError,
        )
    _require_hashes(document, value, _("Trial Defect Verification"))
    if json_array(document.evidence_snapshot, _("Trial Quality Evidence Snapshot")) != [
        item.snapshot_payload() for item in value.evidence
    ]:
        frappe.throw(
            _("Trial verification evidence does not match the exact snapshot."),
            frappe.ValidationError,
        )
    defect_parent = require_exact_parent(
        "NPI Trial Defect Revision",
        str(value.defect_revision_global_id),
        {
            "global_id": str(value.defect_revision_global_id),
            "defect_global_id": str(value.defect_global_id),
            "tenant_id": value.tenant_id,
            "project_global_id": str(value.project_global_id),
            "snapshot_hash": value.defect_revision_snapshot_hash,
        },
        _("The exact Trial defect revision is unavailable for verification."),
        extra_fields=("trial_defect_snapshot",),
    )
    result_parent = require_exact_parent(
        "NPI Trial Cavity Result Revision",
        str(value.cavity_result_revision_global_id),
        {
            "global_id": str(value.cavity_result_revision_global_id),
            "tenant_id": value.tenant_id,
            "project_global_id": str(value.project_global_id),
            "trial_round_global_id": str(value.verification_round_global_id),
            "snapshot_hash": value.cavity_result_revision_snapshot_hash,
        },
        _("The exact Trial cavity result is unavailable for verification."),
        extra_fields=("cavity_result_snapshot",),
    )
    defect = trial_domain_value(
        lambda: trial_defect_from_snapshot(
            json_object(defect_parent["trial_defect_snapshot"], _("Trial Defect Revision Snapshot"))
        )
    )
    cavity_result = trial_domain_value(
        lambda: cavity_result_from_snapshot(
            json_object(
                result_parent["cavity_result_snapshot"],
                _("Trial Cavity Result Revision Snapshot"),
            )
        )
    )
    trial_domain_value(lambda: validate_trial_defect_verification(defect, cavity_result, value))
    _require_round_reference(
        value.tenant_id,
        str(value.project_global_id),
        str(value.target_round_global_id),
        value.target_round_optimistic_version,
        value.target_round_snapshot_hash,
    )
    _require_running_round(
        tenant_id=value.tenant_id,
        project_global_id=str(value.project_global_id),
        round_global_id=str(value.verification_round_global_id),
        optimistic_version=value.verification_round_optimistic_version,
        snapshot_hash=value.verification_round_snapshot_hash,
    )
    _require_member(value.verifier_member, value)
    _require_quality_evidence(value, require_measurement_report=False)
    document.defect_revision = str(value.defect_revision_global_id)
    document.target_round = str(value.target_round_global_id)
    document.verification_round = str(value.verification_round_global_id)
    document.cavity_result_revision = str(value.cavity_result_revision_global_id)
    document.verifier_member = str(value.verifier_member.global_id)
    document.version_key_hash = value.version_key_hash
    document.observed_at = frappe_utc_datetime_text(value.observed_at, _("Observed At"))
    document.evidence_snapshot = canonical_json([item.snapshot_payload() for item in value.evidence])
    document.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
    document.verification_snapshot = canonical_json(value.snapshot_payload())
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


def _require_hashes(document: Any, value: Any, label: str) -> None:
    if document.version_key_hash not in (None, "", value.version_key_hash):
        frappe.throw(
            _("{object} Version Key Hash does not match.").format(object=label),
            frappe.ValidationError,
        )
    if document.snapshot_hash not in (None, "", value.snapshot_hash):
        frappe.throw(
            _("{object} Snapshot Hash does not match.").format(object=label),
            frappe.ValidationError,
        )


def _require_running_round(
    *,
    tenant_id: str,
    project_global_id: str,
    round_global_id: str,
    optimistic_version: int | None = None,
    snapshot_hash: str | None = None,
) -> None:
    filters: dict[str, object] = {
        "global_id": round_global_id,
        "tenant_id": tenant_id,
        "project_global_id": project_global_id,
        "current_state": "running",
    }
    if optimistic_version is not None:
        filters["optimistic_version"] = optimistic_version
    if snapshot_hash is not None:
        filters["snapshot_hash"] = snapshot_hash
    require_exact_parent(
        "NPI Trial Round",
        round_global_id,
        filters,
        _("The exact running Trial Round is unavailable for quality recording."),
    )


def _require_round_reference(
    tenant_id: str,
    project_global_id: str,
    round_global_id: str,
    optimistic_version: int,
    snapshot_hash: str,
) -> None:
    require_exact_parent(
        "NPI Trial Round",
        round_global_id,
        {
            "global_id": round_global_id,
            "tenant_id": tenant_id,
            "project_global_id": project_global_id,
            "optimistic_version": optimistic_version,
            "snapshot_hash": snapshot_hash,
        },
        _("The exact target Trial Round is unavailable."),
    )


def _require_trial_context(value: Any) -> None:
    lock = require_exact_parent(
        "NPI Trial Input Lock Revision",
        str(value.input_lock_revision_global_id),
        {
            "global_id": str(value.input_lock_revision_global_id),
            "tenant_id": value.tenant_id,
            "project_global_id": str(value.project_global_id),
            "trial_round_global_id": str(value.trial_round_global_id),
            "snapshot_hash": value.input_lock_revision_snapshot_hash,
        },
        _("The exact Trial input lock is unavailable for quality recording."),
        extra_fields=("reference_snapshot",),
    )
    references = json_array(lock["reference_snapshot"], _("Locked Trial Reference Snapshot"))
    expected_references = {
        ("tooling_revision", str(value.tooling_revision_global_id), value.tooling_revision_snapshot_hash),
        ("tooling_set", str(value.tooling_set_global_id), value.tooling_set_snapshot_hash),
        ("cavity", str(value.cavity_global_id), None),
    }
    actual_references = {
        (
            item.get("kind"),
            item.get("globalId"),
            item.get("snapshotHash") if item.get("kind") != "cavity" else None,
        )
        for item in references
        if isinstance(item, dict)
    }
    if not expected_references.issubset(actual_references):
        frappe.throw(
            _("The exact Tooling Revision, Set, or cavity is not locked for this Round."),
            frappe.ValidationError,
        )
    require_exact_parent(
        "NPI Tooling Revision",
        str(value.tooling_revision_global_id),
        {
            "global_id": str(value.tooling_revision_global_id),
            "tenant_id": value.tenant_id,
            "project_global_id": str(value.project_global_id),
            "snapshot_hash": value.tooling_revision_snapshot_hash,
        },
        _("The exact Tooling Revision is unavailable for Trial quality."),
    )
    require_exact_parent(
        "NPI Tooling Set",
        str(value.tooling_set_global_id),
        {
            "global_id": str(value.tooling_set_global_id),
            "tenant_id": value.tenant_id,
            "snapshot_hash": value.tooling_set_snapshot_hash,
        },
        _("The exact Tooling Set is unavailable for Trial quality."),
    )
    sample_global_id = getattr(value, "sample_batch_revision_global_id", None)
    sample_hash = getattr(value, "sample_batch_revision_snapshot_hash", None)
    if sample_global_id is not None:
        sample = require_exact_parent(
            "NPI Trial Sample Batch Revision",
            str(sample_global_id),
            {
                "global_id": str(sample_global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "trial_round_global_id": str(value.trial_round_global_id),
                "snapshot_hash": sample_hash,
            },
            _("The exact Sample Batch revision is unavailable for Trial quality."),
            extra_fields=("cavity_snapshot",),
        )
        if str(value.cavity_global_id) not in json_array(
            sample["cavity_snapshot"],
            _("Trial Sample Batch Cavity Snapshot"),
        ):
            frappe.throw(
                _("The exact cavity is unavailable in this Sample Batch."),
                frappe.ValidationError,
            )


def _require_member(member: Any, value: Any) -> None:
    if member is None:
        return
    require_exact_parent(
        "NPI Project Member",
        str(member.global_id),
        {
            "global_id": str(member.global_id),
            "tenant_id": value.tenant_id,
            "project_global_id": str(value.project_global_id),
            "user_id": member.user_id,
            "optimistic_version": member.optimistic_version,
            "effective_to": None,
        },
        _("The exact Project member is unavailable for Trial quality."),
    )


def _require_quality_evidence(
    value: Any,
    *,
    require_measurement_report: bool,
    retained_evidence: dict[object, str] | None = None,
) -> None:
    retained_evidence = retained_evidence or {}
    sample_global_id = getattr(value, "sample_batch_revision_global_id", None)
    sample_hash = getattr(value, "sample_batch_revision_snapshot_hash", None)
    round_global_id = getattr(value, "trial_round_global_id", None)
    if round_global_id is None:
        round_global_id = value.verification_round_global_id
    for item in value.evidence:
        filters: dict[str, object] = {
            "global_id": str(item.global_id),
            "tenant_id": value.tenant_id,
            "project_global_id": str(value.project_global_id),
            "snapshot_hash": item.snapshot_hash,
        }
        if retained_evidence.get(item.global_id) != item.snapshot_hash:
            filters["trial_round_global_id"] = str(round_global_id)
            if sample_global_id is not None:
                filters["sample_batch_revision_global_id"] = str(sample_global_id)
                filters["sample_batch_revision_snapshot_hash"] = sample_hash
        if require_measurement_report:
            filters["role"] = "measurement_report"
        require_exact_parent(
            "NPI Trial Evidence Reference",
            str(item.global_id),
            filters,
            _("The exact Trial quality evidence is unavailable."),
        )
