from __future__ import annotations

from datetime import UTC, date, datetime
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
from npi_core.trial.domain import (
    trial_event_from_snapshot,
    trial_plan_from_snapshot,
    trial_round_from_snapshot,
    trial_work_link_from_snapshot,
)
from npi_core.trial.execution_domain import (
    actual_revision_from_snapshot,
    evidence_reference_from_snapshot,
    input_lock_from_snapshot,
    sample_batch_from_snapshot,
)
from npi_core.trial.frappe_validation import trial_domain_value


def canonical_trial_identity(document: Any) -> None:
    document.global_id = canonical_uuid(document.global_id, _("Global ID"))
    document.name = document.global_id


def normalize_plan_identity(document: Any) -> None:
    for fieldname, label in (
        ("global_id", _("Global ID")),
        ("plan_global_id", _("Trial Plan Global ID")),
        ("project_global_id", _("Project Global ID")),
        ("tooling_master_global_id", _("Tooling Master Global ID")),
        ("request_id", _("Request ID")),
    ):
        setattr(document, fieldname, canonical_uuid(getattr(document, fieldname), label))
    document.predecessor_global_id = optional_uuid(
        document.predecessor_global_id,
        _("Predecessor Trial Plan Revision Global ID"),
    )
    document.tenant_id = tenant_text(document.tenant_id)


def validate_plan_document(document: Any) -> None:
    supplied = json_object(document.plan_snapshot, _("Trial Plan Revision Snapshot"))
    value = trial_domain_value(lambda: trial_plan_from_snapshot(supplied))
    expected = (
        str(value.global_id),
        str(value.plan_global_id),
        value.tenant_id,
        str(value.project_global_id),
        str(value.tooling_master_global_id),
        value.plan_version,
        str(value.predecessor_global_id) if value.predecessor_global_id else None,
        value.predecessor_snapshot_hash,
        value.purpose.value,
        value.objective,
        value.sample_quantity,
        value.reason,
        value.created_by_user_id,
        str(value.request_id),
        value.trace_id,
    )
    actual = (
        document.global_id,
        document.plan_global_id,
        document.tenant_id,
        document.project_global_id,
        document.tooling_master_global_id,
        document.plan_version,
        document.predecessor_global_id,
        document.predecessor_snapshot_hash or None,
        document.purpose,
        document.objective,
        document.sample_quantity,
        document.reason,
        document.created_by_user_id,
        document.request_id,
        document.trace_id,
    )
    if actual != expected:
        frappe.throw(
            _("Trial Plan Revision fields do not match the exact snapshot."),
            frappe.ValidationError,
        )
    if document.version_key_hash not in (None, "", value.version_key_hash):
        frappe.throw(_("Trial Plan Version Key Hash does not match."), frappe.ValidationError)
    if document.snapshot_hash not in (None, "", value.snapshot_hash):
        frappe.throw(_("Trial Plan Snapshot Hash does not match."), frappe.ValidationError)
    if json_array(document.resource_proposal_snapshot, _("Resource Proposal Snapshot")) != [
        item.snapshot_payload() for item in value.resources
    ]:
        frappe.throw(_("Resource proposals do not match the exact Trial Plan."), frappe.ValidationError)
    if json_array(document.responsible_member_snapshot, _("Responsible Member Snapshot")) != [
        item.snapshot_payload() for item in value.responsible_members
    ]:
        frappe.throw(_("Responsible members do not match the exact Trial Plan."), frappe.ValidationError)
    if json_object(document.measurement_plan_snapshot, _("Measurement Plan Snapshot")) != value.measurement_plan.snapshot_payload():
        frappe.throw(_("Measurement plan does not match the exact Trial Plan."), frappe.ValidationError)
    require_exact_parent(
        "NPI Engineering Project",
        str(value.project_global_id),
        {"global_id": str(value.project_global_id), "tenant_id": value.tenant_id},
        _("The Project is unavailable for this Trial Plan."),
    )
    require_exact_parent(
        "NPI Tooling Master",
        str(value.tooling_master_global_id),
        {"global_id": str(value.tooling_master_global_id), "tenant_id": value.tenant_id},
        _("The Tooling Master is unavailable for this Trial Plan."),
    )
    if not frappe.db.exists(
        "NPI Tooling Applicability",
        {
            "tenant_id": value.tenant_id,
            "project_global_id": str(value.project_global_id),
            "tooling_master_global_id": str(value.tooling_master_global_id),
        },
    ):
        frappe.throw(_("The Tooling Master is unavailable for this Project."), frappe.ValidationError)
    for member in value.responsible_members:
        require_current_project_member(
            member,
            tenant_id=value.tenant_id,
            project_global_id=str(value.project_global_id),
        )
    measurement = value.measurement_plan
    if measurement.document_revision_global_id is not None:
        require_exact_parent(
            "NPI Document Revision",
            str(measurement.document_revision_global_id),
            {
                "global_id": str(measurement.document_revision_global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "snapshot_hash": measurement.document_revision_snapshot_hash,
                "optimistic_version": measurement.document_optimistic_version,
            },
            _("The measurement plan document is unavailable."),
        )
    if value.predecessor_global_id is not None:
        require_exact_parent(
            "NPI Trial Plan Revision",
            str(value.predecessor_global_id),
            {
                "global_id": str(value.predecessor_global_id),
                "plan_global_id": str(value.plan_global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "tooling_master_global_id": str(value.tooling_master_global_id),
                "plan_version": value.plan_version - 1,
                "snapshot_hash": value.predecessor_snapshot_hash,
            },
            _("The predecessor Trial Plan Revision is unavailable."),
        )
    document.tooling_master = str(value.tooling_master_global_id)
    document.version_key_hash = value.version_key_hash
    document.planned_start_at = frappe_utc_datetime_text(value.planned_start_at, _("Planned Start At"))
    document.planned_end_at = frappe_utc_datetime_text(value.planned_end_at, _("Planned End At"))
    document.resource_proposal_snapshot = canonical_json([item.snapshot_payload() for item in value.resources])
    document.responsible_member_snapshot = canonical_json([item.snapshot_payload() for item in value.responsible_members])
    document.measurement_plan_snapshot = canonical_json(value.measurement_plan.snapshot_payload())
    document.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
    document.plan_snapshot = canonical_json(value.snapshot_payload())
    document.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))


def require_current_project_member(
    member: Any,
    *,
    tenant_id: str,
    project_global_id: str,
) -> None:
    message = _("A responsible Project member is unavailable for this Trial Plan.")
    try:
        document = frappe.get_doc("NPI Project Member", str(member.global_id))
    except frappe.DoesNotExistError:
        frappe.throw(message, frappe.ValidationError)
    today = datetime.now(UTC).date()
    if (
        str(document.global_id) != str(member.global_id)
        or str(document.tenant_id) != tenant_id
        or str(document.project_global_id) != project_global_id
        or str(document.user_id) != member.user_id
        or int(document.optimistic_version) != member.optimistic_version
        or not _member_effective(document, today)
    ):
        frappe.throw(message, frappe.ValidationError)
    user = frappe.db.get_value(
        "User",
        member.user_id,
        ["enabled", "user_type"],
        as_dict=True,
    )
    if (
        not user
        or int(_record_value(user, "enabled") or 0) != 1
        or str(_record_value(user, "user_type")) != "System User"
    ):
        frappe.throw(message, frappe.ValidationError)


def _member_effective(member: Any, today: date) -> bool:
    starts = _date_value(member.effective_from)
    ends = _date_value(member.effective_to) if member.effective_to else None
    return starts <= today and (ends is None or today <= ends)


def _date_value(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _record_value(record: Any, fieldname: str) -> Any:
    if isinstance(record, dict):
        return record.get(fieldname)
    return getattr(record, fieldname, None)


def normalize_round_identity(document: Any) -> None:
    for fieldname, label in (
        ("global_id", _("Global ID")),
        ("project_global_id", _("Project Global ID")),
        ("trial_plan_global_id", _("Trial Plan Global ID")),
        ("trial_plan_revision_global_id", _("Trial Plan Revision Global ID")),
        ("tooling_master_global_id", _("Tooling Master Global ID")),
        ("current_event_global_id", _("Current Trial Event Global ID")),
        ("request_id", _("Request ID")),
    ):
        setattr(document, fieldname, canonical_uuid(getattr(document, fieldname), label))
    document.tenant_id = tenant_text(document.tenant_id)


def validate_round_document(document: Any) -> None:
    supplied = json_object(document.round_snapshot, _("Trial Round Snapshot"))
    value = trial_domain_value(lambda: trial_round_from_snapshot(supplied))
    expected = (
        str(value.global_id), value.tenant_id, str(value.project_global_id),
        str(value.trial_plan_global_id), str(value.trial_plan_revision_global_id),
        value.trial_plan_revision_snapshot_hash, str(value.tooling_master_global_id),
        value.round_sequence, value.display_label, value.purpose.value,
        value.current_state.value, str(value.current_event_global_id),
        value.optimistic_version, value.created_by_user_id, str(value.request_id),
        value.trace_id,
    )
    actual = (
        document.global_id, document.tenant_id, document.project_global_id,
        document.trial_plan_global_id, document.trial_plan_revision_global_id,
        document.trial_plan_revision_snapshot_hash, document.tooling_master_global_id,
        document.round_sequence, document.display_label, document.purpose,
        document.current_state, document.current_event_global_id,
        document.optimistic_version, document.created_by_user_id,
        document.request_id, document.trace_id,
    )
    if actual != expected:
        frappe.throw(_("Trial Round fields do not match the exact snapshot."), frappe.ValidationError)
    if document.snapshot_hash not in (None, "", value.snapshot_hash):
        frappe.throw(_("Trial Round Snapshot Hash does not match."), frappe.ValidationError)
    require_exact_parent(
        "NPI Trial Plan Revision",
        str(value.trial_plan_revision_global_id),
        {
            "global_id": str(value.trial_plan_revision_global_id),
            "plan_global_id": str(value.trial_plan_global_id),
            "tenant_id": value.tenant_id,
            "project_global_id": str(value.project_global_id),
            "tooling_master_global_id": str(value.tooling_master_global_id),
            "snapshot_hash": value.trial_plan_revision_snapshot_hash,
        },
        _("The exact Trial Plan Revision is unavailable for this Round."),
    )
    require_exact_parent(
        "NPI Trial Round Lifecycle Event",
        str(value.current_event_global_id),
        {
            "global_id": str(value.current_event_global_id),
            "tenant_id": value.tenant_id,
            "project_global_id": str(value.project_global_id),
            "trial_round_global_id": str(value.global_id),
            "event_version": value.optimistic_version,
            "to_state": value.current_state.value,
        },
        _("The exact current Trial lifecycle event is unavailable."),
    )
    document.trial_plan_revision = str(value.trial_plan_revision_global_id)
    document.tooling_master = str(value.tooling_master_global_id)
    document.planned_start_at = frappe_utc_datetime_text(value.planned_start_at, _("Planned Start At"))
    document.planned_end_at = frappe_utc_datetime_text(value.planned_end_at, _("Planned End At"))
    document.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
    document.round_snapshot = canonical_json(value.snapshot_payload())
    document.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))


def normalize_event_identity(document: Any) -> None:
    for fieldname, label in (
        ("global_id", _("Global ID")),
        ("project_global_id", _("Project Global ID")),
        ("trial_round_global_id", _("Trial Round Global ID")),
        ("request_id", _("Request ID")),
    ):
        setattr(document, fieldname, canonical_uuid(getattr(document, fieldname), label))
    document.tenant_id = tenant_text(document.tenant_id)


def validate_event_document(document: Any) -> None:
    supplied = json_object(document.event_snapshot, _("Trial Lifecycle Event Snapshot"))
    value = trial_domain_value(lambda: trial_event_from_snapshot(supplied))
    expected = (
        str(value.global_id), value.tenant_id, str(value.project_global_id),
        str(value.trial_round_global_id), value.event_version,
        value.event_type.value, value.from_state.value if value.from_state else None,
        value.to_state.value, value.reason, value.created_by_user_id,
        str(value.request_id), value.trace_id,
    )
    actual = (
        document.global_id, document.tenant_id, document.project_global_id,
        document.trial_round_global_id, document.event_version,
        document.event_type, document.from_state or None, document.to_state,
        document.reason, document.created_by_user_id, document.request_id,
        document.trace_id,
    )
    if actual != expected:
        frappe.throw(_("Trial lifecycle event fields do not match the exact snapshot."), frappe.ValidationError)
    if document.snapshot_hash not in (None, "", value.snapshot_hash):
        frappe.throw(_("Trial Lifecycle Event Snapshot Hash does not match."), frappe.ValidationError)
    document.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
    document.event_snapshot = canonical_json(value.snapshot_payload())
    document.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))


def normalize_work_link_identity(document: Any) -> None:
    for fieldname, label in (
        ("global_id", _("Global ID")),
        ("project_global_id", _("Project Global ID")),
        ("trial_plan_global_id", _("Trial Plan Global ID")),
        ("trial_plan_revision_global_id", _("Trial Plan Revision Global ID")),
        ("domain_work_item_global_id", _("Domain Work Item Global ID")),
        ("request_id", _("Request ID")),
    ):
        setattr(document, fieldname, canonical_uuid(getattr(document, fieldname), label))
    document.trial_round_global_id = optional_uuid(
        document.trial_round_global_id,
        _("Trial Round Global ID"),
    )
    document.tenant_id = tenant_text(document.tenant_id)


def validate_work_link_document(document: Any) -> None:
    supplied = json_object(document.link_snapshot, _("Trial Plan Work Link Snapshot"))
    value = trial_domain_value(lambda: trial_work_link_from_snapshot(supplied))
    expected = (
        str(value.global_id), value.tenant_id, str(value.project_global_id),
        str(value.trial_plan_global_id), str(value.trial_plan_revision_global_id),
        value.trial_plan_revision_snapshot_hash,
        str(value.trial_round_global_id) if value.trial_round_global_id else None,
        str(value.domain_work_item_global_id), value.created_by_user_id,
        str(value.request_id), value.trace_id,
    )
    actual = (
        document.global_id, document.tenant_id, document.project_global_id,
        document.trial_plan_global_id, document.trial_plan_revision_global_id,
        document.trial_plan_revision_snapshot_hash,
        document.trial_round_global_id or None,
        document.domain_work_item_global_id, document.created_by_user_id,
        document.request_id, document.trace_id,
    )
    if actual != expected:
        frappe.throw(_("Trial Plan work-link fields do not match the exact snapshot."), frappe.ValidationError)
    if document.snapshot_hash not in (None, "", value.snapshot_hash):
        frappe.throw(_("Trial Plan Work Link Snapshot Hash does not match."), frappe.ValidationError)
    require_exact_parent(
        "NPI Trial Plan Revision",
        str(value.trial_plan_revision_global_id),
        {
            "global_id": str(value.trial_plan_revision_global_id),
            "plan_global_id": str(value.trial_plan_global_id),
            "tenant_id": value.tenant_id,
            "project_global_id": str(value.project_global_id),
            "snapshot_hash": value.trial_plan_revision_snapshot_hash,
        },
        _("The exact Trial Plan Revision is unavailable for this work link."),
    )
    if value.trial_round_global_id is not None:
        require_exact_parent(
            "NPI Trial Round",
            str(value.trial_round_global_id),
            {
                "global_id": str(value.trial_round_global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "trial_plan_global_id": str(value.trial_plan_global_id),
            },
            _("The Trial Round is unavailable for this work link."),
        )
    require_exact_parent(
        "NPI Domain Work Item",
        str(value.domain_work_item_global_id),
        {
            "global_id": str(value.domain_work_item_global_id),
            "tenant_id": value.tenant_id,
            "project_global_id": str(value.project_global_id),
        },
        _("The Domain Work Item is unavailable for this Trial Plan."),
    )
    document.trial_plan_revision = str(value.trial_plan_revision_global_id)
    document.trial_round = str(value.trial_round_global_id) if value.trial_round_global_id else None
    document.domain_work_item = str(value.domain_work_item_global_id)
    document.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
    document.link_snapshot = canonical_json(value.snapshot_payload())
    document.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))


def _normalize_execution_identity(
    document: Any,
    fields: tuple[tuple[str, str], ...],
    optional_fields: tuple[tuple[str, str], ...] = (),
) -> None:
    for fieldname, label in fields:
        setattr(document, fieldname, canonical_uuid(getattr(document, fieldname), label))
    for fieldname, label in optional_fields:
        setattr(document, fieldname, optional_uuid(getattr(document, fieldname), label))
    document.tenant_id = tenant_text(document.tenant_id)


def normalize_input_lock_identity(document: Any) -> None:
    _normalize_execution_identity(
        document,
        (
            ("global_id", _("Global ID")),
            ("input_lock_global_id", _("Trial Input Lock Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("trial_round_global_id", _("Trial Round Global ID")),
            ("trial_plan_revision_global_id", _("Trial Plan Revision Global ID")),
            ("request_id", _("Request ID")),
        ),
        (("predecessor_global_id", _("Predecessor Trial Input Lock Revision Global ID")),),
    )


def validate_input_lock_document(document: Any) -> None:
    supplied = json_object(document.lock_snapshot, _("Trial Input Lock Revision Snapshot"))
    value = trial_domain_value(lambda: input_lock_from_snapshot(supplied))
    expected = (
        str(value.global_id),
        str(value.input_lock_global_id),
        value.tenant_id,
        str(value.project_global_id),
        str(value.trial_round_global_id),
        str(value.trial_plan_revision_global_id),
        value.trial_plan_revision_snapshot_hash,
        value.lock_version,
        str(value.predecessor_global_id) if value.predecessor_global_id else None,
        value.predecessor_snapshot_hash,
        value.reason,
        value.created_by_user_id,
        str(value.request_id),
        value.trace_id,
    )
    actual = (
        document.global_id,
        document.input_lock_global_id,
        document.tenant_id,
        document.project_global_id,
        document.trial_round_global_id,
        document.trial_plan_revision_global_id,
        document.trial_plan_revision_snapshot_hash,
        document.lock_version,
        document.predecessor_global_id or None,
        document.predecessor_snapshot_hash or None,
        document.reason,
        document.created_by_user_id,
        document.request_id,
        document.trace_id,
    )
    if actual != expected:
        frappe.throw(
            _("Trial input lock fields do not match the exact snapshot."),
            frappe.ValidationError,
        )
    if document.version_key_hash not in (None, "", value.version_key_hash):
        frappe.throw(_("Trial Input Lock Version Key Hash does not match."), frappe.ValidationError)
    if document.snapshot_hash not in (None, "", value.snapshot_hash):
        frappe.throw(_("Trial Input Lock Snapshot Hash does not match."), frappe.ValidationError)
    if json_array(document.reference_snapshot, _("Locked Trial Reference Snapshot")) != [
        item.snapshot_payload() for item in value.references
    ]:
        frappe.throw(_("Locked Trial references do not match the exact input lock."), frappe.ValidationError)
    if json_object(document.material_snapshot, _("Trial Material Observation Snapshot")) != value.material.snapshot_payload():
        frappe.throw(_("Trial material does not match the exact input lock."), frappe.ValidationError)
    if json_array(document.parameter_definition_snapshot, _("Trial Parameter Definition Snapshot")) != [
        item.snapshot_payload() for item in value.parameter_definitions
    ]:
        frappe.throw(_("Trial parameters do not match the exact input lock."), frappe.ValidationError)
    require_exact_parent(
        "NPI Trial Round",
        str(value.trial_round_global_id),
        {
            "global_id": str(value.trial_round_global_id),
            "tenant_id": value.tenant_id,
            "project_global_id": str(value.project_global_id),
            "trial_plan_revision_global_id": str(value.trial_plan_revision_global_id),
            "trial_plan_revision_snapshot_hash": value.trial_plan_revision_snapshot_hash,
        },
        _("The exact planned Trial Round is unavailable for this input lock."),
    )
    require_exact_parent(
        "NPI Trial Plan Revision",
        str(value.trial_plan_revision_global_id),
        {
            "global_id": str(value.trial_plan_revision_global_id),
            "tenant_id": value.tenant_id,
            "project_global_id": str(value.project_global_id),
            "snapshot_hash": value.trial_plan_revision_snapshot_hash,
        },
        _("The exact Trial Plan Revision is unavailable for this input lock."),
    )
    if value.predecessor_global_id is not None:
        require_exact_parent(
            "NPI Trial Input Lock Revision",
            str(value.predecessor_global_id),
            {
                "global_id": str(value.predecessor_global_id),
                "input_lock_global_id": str(value.input_lock_global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "trial_round_global_id": str(value.trial_round_global_id),
                "lock_version": value.lock_version - 1,
                "snapshot_hash": value.predecessor_snapshot_hash,
            },
            _("The exact predecessor Trial input lock is unavailable."),
        )
    document.trial_round = str(value.trial_round_global_id)
    document.trial_plan_revision = str(value.trial_plan_revision_global_id)
    document.version_key_hash = value.version_key_hash
    document.reference_snapshot = canonical_json([item.snapshot_payload() for item in value.references])
    document.material_snapshot = canonical_json(value.material.snapshot_payload())
    document.parameter_definition_snapshot = canonical_json(
        [item.snapshot_payload() for item in value.parameter_definitions]
    )
    document.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
    document.lock_snapshot = canonical_json(value.snapshot_payload())
    document.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))


def normalize_actual_identity(document: Any) -> None:
    _normalize_execution_identity(
        document,
        (
            ("global_id", _("Global ID")),
            ("actual_global_id", _("Trial Actual Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("trial_round_global_id", _("Trial Round Global ID")),
            ("input_lock_revision_global_id", _("Trial Input Lock Revision Global ID")),
            ("request_id", _("Request ID")),
        ),
        (("predecessor_global_id", _("Predecessor Trial Actual Revision Global ID")),),
    )


def validate_actual_document(document: Any) -> None:
    supplied = json_object(document.actual_snapshot, _("Trial Actual Revision Snapshot"))
    value = trial_domain_value(lambda: actual_revision_from_snapshot(supplied))
    expected = (
        str(value.global_id),
        str(value.actual_global_id),
        value.tenant_id,
        str(value.project_global_id),
        str(value.trial_round_global_id),
        str(value.input_lock_revision_global_id),
        value.input_lock_revision_snapshot_hash,
        value.actual_version,
        str(value.predecessor_global_id) if value.predecessor_global_id else None,
        value.predecessor_snapshot_hash,
        value.acquisition_mode.value,
        value.operator_user_id,
        value.confirmed_by_user_id,
        value.reason,
        str(value.request_id),
        value.trace_id,
    )
    actual = (
        document.global_id,
        document.actual_global_id,
        document.tenant_id,
        document.project_global_id,
        document.trial_round_global_id,
        document.input_lock_revision_global_id,
        document.input_lock_revision_snapshot_hash,
        document.actual_version,
        document.predecessor_global_id or None,
        document.predecessor_snapshot_hash or None,
        document.acquisition_mode,
        document.operator_user_id,
        document.confirmed_by_user_id,
        document.reason,
        document.request_id,
        document.trace_id,
    )
    if actual != expected:
        frappe.throw(_("Trial Actual fields do not match the exact snapshot."), frappe.ValidationError)
    if document.version_key_hash not in (None, "", value.version_key_hash):
        frappe.throw(_("Trial Actual Version Key Hash does not match."), frappe.ValidationError)
    if document.snapshot_hash not in (None, "", value.snapshot_hash):
        frappe.throw(_("Trial Actual Snapshot Hash does not match."), frappe.ValidationError)
    snapshots = (
        (document.resource_snapshot, _("Actual Trial Resource Snapshot"), [item.snapshot_payload() for item in value.resources]),
        (document.environment_snapshot, _("Trial Environment Observation Snapshot"), [item.snapshot_payload() for item in value.environment]),
        (document.parameter_snapshot, _("Trial Parameter Observation Snapshot"), [item.snapshot_payload() for item in value.parameters]),
    )
    for supplied_snapshot, label, expected_snapshot in snapshots:
        if json_array(supplied_snapshot, label) != expected_snapshot:
            frappe.throw(_("Trial Actual detail does not match the exact snapshot."), frappe.ValidationError)
    if json_object(document.material_snapshot, _("Trial Material Observation Snapshot")) != value.material.snapshot_payload():
        frappe.throw(_("Trial Actual material does not match the exact snapshot."), frappe.ValidationError)
    require_exact_parent(
        "NPI Trial Round",
        str(value.trial_round_global_id),
        {
            "global_id": str(value.trial_round_global_id),
            "tenant_id": value.tenant_id,
            "project_global_id": str(value.project_global_id),
        },
        _("The exact Trial Round is unavailable for this Trial Actual."),
    )
    require_exact_parent(
        "NPI Trial Input Lock Revision",
        str(value.input_lock_revision_global_id),
        {
            "global_id": str(value.input_lock_revision_global_id),
            "tenant_id": value.tenant_id,
            "project_global_id": str(value.project_global_id),
            "trial_round_global_id": str(value.trial_round_global_id),
            "snapshot_hash": value.input_lock_revision_snapshot_hash,
        },
        _("The exact Trial input lock is unavailable for this Trial Actual."),
    )
    if value.predecessor_global_id is not None:
        require_exact_parent(
            "NPI Trial Actual Revision",
            str(value.predecessor_global_id),
            {
                "global_id": str(value.predecessor_global_id),
                "actual_global_id": str(value.actual_global_id),
                "actual_version": value.actual_version - 1,
                "snapshot_hash": value.predecessor_snapshot_hash,
            },
            _("The exact predecessor Trial Actual is unavailable."),
        )
    document.trial_round = str(value.trial_round_global_id)
    document.input_lock_revision = str(value.input_lock_revision_global_id)
    document.version_key_hash = value.version_key_hash
    document.resource_snapshot = canonical_json([item.snapshot_payload() for item in value.resources])
    document.material_snapshot = canonical_json(value.material.snapshot_payload())
    document.environment_snapshot = canonical_json([item.snapshot_payload() for item in value.environment])
    document.parameter_snapshot = canonical_json([item.snapshot_payload() for item in value.parameters])
    document.execution_started_at = frappe_utc_datetime_text(value.execution_started_at, _("Trial Execution Started At"))
    document.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
    document.actual_snapshot = canonical_json(value.snapshot_payload())
    document.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))


def normalize_sample_identity(document: Any) -> None:
    _normalize_execution_identity(
        document,
        (
            ("global_id", _("Global ID")),
            ("sample_batch_global_id", _("Trial Sample Batch Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("trial_round_global_id", _("Trial Round Global ID")),
            ("input_lock_revision_global_id", _("Trial Input Lock Revision Global ID")),
            ("request_id", _("Request ID")),
        ),
        (("predecessor_global_id", _("Predecessor Trial Sample Batch Revision Global ID")),),
    )


def validate_sample_document(document: Any) -> None:
    supplied = json_object(document.sample_snapshot, _("Trial Sample Batch Revision Snapshot"))
    value = trial_domain_value(lambda: sample_batch_from_snapshot(supplied))
    expected = (
        str(value.global_id), str(value.sample_batch_global_id), value.tenant_id,
        str(value.project_global_id), str(value.trial_round_global_id),
        str(value.input_lock_revision_global_id), value.input_lock_revision_snapshot_hash,
        value.sample_version,
        str(value.predecessor_global_id) if value.predecessor_global_id else None,
        value.predecessor_snapshot_hash, value.label, value.material_snapshot_hash,
        value.quantity, value.unit, value.packaging, value.destination,
        value.feedback_text, value.feedback_source, value.reason,
        value.created_by_user_id, str(value.request_id), value.trace_id,
    )
    actual = (
        document.global_id, document.sample_batch_global_id, document.tenant_id,
        document.project_global_id, document.trial_round_global_id,
        document.input_lock_revision_global_id, document.input_lock_revision_snapshot_hash,
        document.sample_version, document.predecessor_global_id or None,
        document.predecessor_snapshot_hash or None, document.label,
        document.material_snapshot_hash, document.quantity, document.unit,
        document.packaging, document.destination, document.feedback_text or None,
        document.feedback_source or None, document.reason, document.created_by_user_id,
        document.request_id, document.trace_id,
    )
    if actual != expected:
        frappe.throw(_("Sample Batch fields do not match the exact snapshot."), frappe.ValidationError)
    if document.version_key_hash not in (None, "", value.version_key_hash):
        frappe.throw(_("Trial Sample Batch Version Key Hash does not match."), frappe.ValidationError)
    if document.snapshot_hash not in (None, "", value.snapshot_hash):
        frappe.throw(_("Trial Sample Batch Snapshot Hash does not match."), frappe.ValidationError)
    if json_array(document.cavity_snapshot, _("Trial Sample Batch Cavity Snapshot")) != [
        str(item) for item in value.cavity_global_ids
    ]:
        frappe.throw(_("Sample Batch cavities do not match the exact snapshot."), frappe.ValidationError)
    require_exact_parent(
        "NPI Trial Round",
        str(value.trial_round_global_id),
        {"global_id": str(value.trial_round_global_id), "tenant_id": value.tenant_id, "project_global_id": str(value.project_global_id)},
        _("The exact Trial Round is unavailable for this Sample Batch."),
    )
    require_exact_parent(
        "NPI Trial Input Lock Revision",
        str(value.input_lock_revision_global_id),
        {
            "global_id": str(value.input_lock_revision_global_id),
            "trial_round_global_id": str(value.trial_round_global_id),
            "snapshot_hash": value.input_lock_revision_snapshot_hash,
        },
        _("The exact Trial input lock is unavailable for this Sample Batch."),
    )
    if value.predecessor_global_id is not None:
        require_exact_parent(
            "NPI Trial Sample Batch Revision",
            str(value.predecessor_global_id),
            {
                "global_id": str(value.predecessor_global_id),
                "sample_batch_global_id": str(value.sample_batch_global_id),
                "sample_version": value.sample_version - 1,
                "snapshot_hash": value.predecessor_snapshot_hash,
            },
            _("The exact predecessor Sample Batch is unavailable."),
        )
    document.trial_round = str(value.trial_round_global_id)
    document.input_lock_revision = str(value.input_lock_revision_global_id)
    document.version_key_hash = value.version_key_hash
    document.cavity_snapshot = canonical_json([str(item) for item in value.cavity_global_ids])
    document.feedback_observed_at = (
        frappe_utc_datetime_text(value.feedback_observed_at, _("Trial Sample Feedback Observed At"))
        if value.feedback_observed_at else None
    )
    document.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
    document.sample_snapshot = canonical_json(value.snapshot_payload())
    document.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))


def normalize_evidence_identity(document: Any) -> None:
    _normalize_execution_identity(
        document,
        (
            ("global_id", _("Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("trial_round_global_id", _("Trial Round Global ID")),
            ("file_revision_global_id", _("File Revision Global ID")),
            ("request_id", _("Request ID")),
        ),
        (("sample_batch_revision_global_id", _("Trial Sample Batch Revision Global ID")),),
    )


def validate_evidence_document(document: Any) -> None:
    supplied = json_object(document.evidence_snapshot, _("Trial Evidence Reference Snapshot"))
    value = trial_domain_value(lambda: evidence_reference_from_snapshot(supplied))
    expected = (
        str(value.global_id), value.tenant_id, str(value.project_global_id),
        str(value.trial_round_global_id), value.role.value,
        str(value.sample_batch_revision_global_id) if value.sample_batch_revision_global_id else None,
        value.sample_batch_revision_snapshot_hash, str(value.file_revision_global_id),
        value.file_sha256, value.file_size_bytes, value.file_mime_type,
        value.created_by_user_id, str(value.request_id), value.trace_id,
    )
    actual = (
        document.global_id, document.tenant_id, document.project_global_id,
        document.trial_round_global_id, document.role,
        document.sample_batch_revision_global_id or None,
        document.sample_batch_revision_snapshot_hash or None,
        document.file_revision_global_id, document.file_sha256,
        document.file_size_bytes, document.file_mime_type,
        document.created_by_user_id, document.request_id, document.trace_id,
    )
    if actual != expected:
        frappe.throw(_("Trial evidence fields do not match the exact snapshot."), frappe.ValidationError)
    if document.snapshot_hash not in (None, "", value.snapshot_hash):
        frappe.throw(_("Trial Evidence Reference Snapshot Hash does not match."), frappe.ValidationError)
    require_exact_parent(
        "NPI Trial Round",
        str(value.trial_round_global_id),
        {"global_id": str(value.trial_round_global_id), "tenant_id": value.tenant_id, "project_global_id": str(value.project_global_id)},
        _("The exact Trial Round is unavailable for this evidence."),
    )
    if value.sample_batch_revision_global_id is not None:
        require_exact_parent(
            "NPI Trial Sample Batch Revision",
            str(value.sample_batch_revision_global_id),
            {
                "global_id": str(value.sample_batch_revision_global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "trial_round_global_id": str(value.trial_round_global_id),
                "snapshot_hash": value.sample_batch_revision_snapshot_hash,
            },
            _("The exact Sample Batch revision is unavailable for this evidence."),
        )
    require_exact_parent(
        "NPI File Revision",
        str(value.file_revision_global_id),
        {
            "global_id": str(value.file_revision_global_id),
            "tenant_id": value.tenant_id,
            "project_global_id": str(value.project_global_id),
            "sha256": value.file_sha256,
            "size_bytes": value.file_size_bytes,
            "mime_type": value.file_mime_type,
            "is_private": 1,
            "scan_state": "clean",
        },
        _("Select an exact clean private file revision."),
    )
    document.trial_round = str(value.trial_round_global_id)
    document.sample_batch_revision = (
        str(value.sample_batch_revision_global_id)
        if value.sample_batch_revision_global_id else None
    )
    document.file_revision = str(value.file_revision_global_id)
    document.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
    document.evidence_snapshot = canonical_json(value.snapshot_payload())
    document.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))
