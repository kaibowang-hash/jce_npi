from __future__ import annotations

import re
from typing import Any, Callable, TypeVar

import frappe
from frappe import _

from npi_core.documents.frappe_validation import (
    actor_text,
    canonical_json,
    canonical_uuid,
    frappe_utc_datetime_text,
    json_array,
    json_object,
    lowercase_sha256,
    optional_uuid,
    require_exact_parent,
    required_text,
    tenant_text,
)
from npi_core.foundation.errors import RequestValidationFailed
from npi_core.production_transition.domain import (
    UNRESOLVED_ACTION_SELECTOR,
    acknowledgement_from_snapshot,
    handover_package_from_snapshot,
    observation_from_snapshot,
    policy_from_snapshot,
    validate_policy_persistence_transition,
)


_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,63}$")
_T = TypeVar("_T")


def normalize_policy_root(document: Any) -> None:
    canonical_production_transition_identity(document)
    code = str(document.policy_code or "").strip()
    title = str(document.title or "").strip()
    if _CODE.fullmatch(code) is None:
        frappe.throw(
            _("Enter a valid Production Transition Policy code."),
            frappe.ValidationError,
        )
    if not title or len(title) > 200:
        frappe.throw(
            _("Enter a valid Production Transition Policy title."),
            frappe.ValidationError,
        )
    if type(document.optimistic_version) is not int or document.optimistic_version < 1:
        frappe.throw(_("Enter a positive optimistic version."), frappe.ValidationError)
    document.policy_code = code
    document.title = title


def canonical_production_transition_identity(document: Any) -> None:
    document.global_id = canonical_uuid(document.global_id, _("Global ID"))
    document.name = document.global_id


def normalize_policy_version_identity(document: Any) -> None:
    _normalize_identity(
        document,
        (
            ("global_id", _("Global ID")),
            ("policy_global_id", _("Production Transition Policy Global ID")),
            ("request_id", _("Request ID")),
        ),
        (
            (
                "predecessor_global_id",
                _("Predecessor Production Transition Policy Version Global ID"),
            ),
        ),
    )


def validate_policy_version_document(document: Any, previous: Any | None = None) -> None:
    supplied = json_object(
        document.policy_snapshot,
        _("Production Transition Policy Version Snapshot"),
    )
    value = _domain_value(lambda: policy_from_snapshot(supplied))
    previous_value = None
    if previous is not None:
        previous_supplied = json_object(
            previous.policy_snapshot,
            _("Production Transition Policy Version Snapshot"),
        )
        previous_value = _domain_value(lambda: policy_from_snapshot(previous_supplied))
        if str(previous.snapshot_hash or "") != previous_value.snapshot_hash:
            frappe.throw(
                _("Production Transition Policy fields do not match the exact snapshot."),
                frappe.ValidationError,
            )
    _domain_value(lambda: validate_policy_persistence_transition(previous_value, value))
    prior = value.prior_version_ref
    _expect_fields(
        (
            document.global_id,
            document.policy_global_id,
            document.policy_code,
            int(document.policy_version),
            int(document.optimistic_version),
            document.title,
            document.publication_state,
            document.predecessor_global_id or None,
            document.predecessor_snapshot_hash or None,
            int(document.observation_window_days),
            document.changed_by_user_id,
            document.request_id,
            document.trace_id,
        ),
        (
            str(value.global_id),
            str(value.policy_global_id),
            value.policy_code,
            value.policy_version,
            value.optimistic_version,
            value.title,
            value.publication_state.value,
            str(prior.global_id) if prior else None,
            prior.snapshot_hash if prior else None,
            value.observation_window_days,
            value.changed_by_user_id,
            str(value.request_id),
            value.trace_id,
        ),
        _("Production Transition Policy fields do not match the exact snapshot."),
    )
    require_exact_parent(
        "NPI Production Transition Policy",
        str(value.policy_global_id),
        {
            "global_id": str(value.policy_global_id),
            "policy_code": value.policy_code,
        },
        _("The Production Transition Policy is unavailable."),
    )
    if prior is not None:
        require_exact_parent(
            "NPI Production Transition Policy Version",
            str(prior.global_id),
            {
                "global_id": str(prior.global_id),
                "policy_global_id": str(value.policy_global_id),
                "policy_version": prior.version,
                "publication_state": "published",
                "snapshot_hash": prior.snapshot_hash,
            },
            _("The predecessor Production Transition Policy version is unavailable."),
        )
    _expect_json(
        document.applicability_snapshot,
        value.applicability.snapshot_payload(),
        _("Production Transition Policy Applicability Snapshot"),
    )
    _expect_array(
        document.receiving_group_snapshot,
        [item.snapshot_payload() for item in value.receiving_groups],
        _("Production Transition Receiving Group Snapshot"),
    )
    _expect_array(
        document.acknowledgement_slot_snapshot,
        [item.snapshot_payload() for item in value.acknowledgement_slots],
        _("Production Transition Acknowledgement Slot Snapshot"),
    )
    _expect_array(
        document.handover_object_requirement_snapshot,
        [item.snapshot_payload() for item in value.handover_requirements],
        _("Handover Object Requirement Snapshot"),
    )
    selector = {
        "mode": UNRESOLVED_ACTION_SELECTOR["mode"],
        "kinds": list(UNRESOLVED_ACTION_SELECTOR["kinds"]),
    }
    _expect_json(
        document.unresolved_action_rule_snapshot,
        selector,
        _("Unresolved Action Rule Snapshot"),
    )
    source_rules = [item.snapshot_payload() for item in value.observation_source_rules]
    _expect_array(
        document.observation_source_requirement_snapshot,
        source_rules,
        _("Observation Source Requirement Snapshot"),
    )
    _expect_array(
        document.conclusion_rule_snapshot,
        [
            {
                "providerKind": item.provider_kind.value,
                "allowedDispositions": [
                    disposition.value for disposition in item.allowed_dispositions
                ],
            }
            for item in value.observation_source_rules
        ],
        _("Observation Conclusion Rule Snapshot"),
    )
    _expect_version_key_hash(document, value.version_key_hash)
    if frappe_utc_datetime_text(document.changed_at, _("Changed At")) != frappe_utc_datetime_text(
        value.changed_at,
        _("Changed At"),
    ):
        frappe.throw(
            _("Production Transition Policy fields do not match the exact snapshot."),
            frappe.ValidationError,
        )
    document.policy = str(value.policy_global_id)
    document.version_key_hash = value.version_key_hash
    document.changed_by_user_id = actor_text(value.changed_by_user_id, _("Changed By User ID"))
    document.changed_at = frappe_utc_datetime_text(value.changed_at, _("Changed At"))
    document.trace_id = required_text(value.trace_id, _("Trace ID"), 128)
    document.applicability_snapshot = canonical_json(value.applicability.snapshot_payload())
    document.receiving_group_snapshot = canonical_json(
        [item.snapshot_payload() for item in value.receiving_groups]
    )
    document.acknowledgement_slot_snapshot = canonical_json(
        [item.snapshot_payload() for item in value.acknowledgement_slots]
    )
    document.handover_object_requirement_snapshot = canonical_json(
        [item.snapshot_payload() for item in value.handover_requirements]
    )
    document.unresolved_action_rule_snapshot = canonical_json(selector)
    document.observation_source_requirement_snapshot = canonical_json(source_rules)
    document.conclusion_rule_snapshot = canonical_json(
        [
            {
                "providerKind": item.provider_kind.value,
                "allowedDispositions": [
                    disposition.value for disposition in item.allowed_dispositions
                ],
            }
            for item in value.observation_source_rules
        ]
    )
    document.policy_snapshot = canonical_json(value.snapshot_payload())
    document.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))


def normalize_handover_package_identity(document: Any) -> None:
    _normalize_identity(
        document,
        (
            ("global_id", _("Global ID")),
            ("handover_global_id", _("Handover Package Global ID")),
            ("project_global_id", _("Project Global ID")),
            (
                "policy_version_global_id",
                _("Production Transition Policy Version Global ID"),
            ),
            ("request_id", _("Request ID")),
        ),
        (
            (
                "predecessor_global_id",
                _("Predecessor Handover Package Revision Global ID"),
            ),
            ("readiness_revision_global_id", _("Readiness Instance Revision Global ID")),
        ),
    )


def validate_handover_package_document(document: Any) -> None:
    supplied = json_object(
        document.package_snapshot,
        _("Handover Package Revision Snapshot"),
    )
    value = _domain_value(lambda: handover_package_from_snapshot(supplied))
    readiness = value.readiness_ref
    _expect_fields(
        (
            document.global_id,
            document.handover_global_id,
            int(document.handover_version),
            document.predecessor_global_id or None,
            document.predecessor_snapshot_hash or None,
            document.tenant_id,
            document.project_global_id,
            int(document.project_optimistic_version),
            document.project_snapshot_hash,
            document.policy_version_global_id,
            int(document.policy_business_version),
            document.policy_snapshot_hash,
            document.readiness_revision_global_id or None,
            int(document.readiness_revision_version)
            if document.readiness_revision_version not in (None, "", 0)
            else None,
            document.readiness_revision_snapshot_hash or None,
            document.reason,
            document.created_by_user_id,
            document.request_id,
            document.trace_id,
        ),
        (
            str(value.global_id),
            str(value.handover_global_id),
            value.handover_version,
            str(value.predecessor_global_id) if value.predecessor_global_id else None,
            value.predecessor_snapshot_hash,
            value.tenant_id,
            str(value.project.global_id),
            value.project.optimistic_version,
            value.project.snapshot_hash,
            str(value.policy_ref.global_id),
            value.policy_ref.version,
            value.policy_ref.snapshot_hash,
            str(readiness.global_id) if readiness else None,
            readiness.version if readiness else None,
            readiness.snapshot_hash if readiness else None,
            value.reason,
            value.created_by_user_id,
            str(value.request_id),
            value.trace_id,
        ),
        _("Handover Package fields do not match the exact snapshot."),
    )
    _require_exact_project(value)
    require_exact_parent(
        "NPI Production Transition Policy Version",
        str(value.policy_ref.global_id),
        {
            "global_id": str(value.policy_ref.global_id),
            "policy_version": value.policy_ref.version,
            "publication_state": "published",
            "snapshot_hash": value.policy_ref.snapshot_hash,
        },
        _("The published Production Transition Policy version is unavailable."),
    )
    if value.predecessor_global_id is not None:
        require_exact_parent(
            "NPI Handover Package Revision",
            str(value.predecessor_global_id),
            {
                "global_id": str(value.predecessor_global_id),
                "handover_global_id": str(value.handover_global_id),
                "handover_version": value.handover_version - 1,
                "snapshot_hash": value.predecessor_snapshot_hash,
            },
            _("The predecessor Handover Package revision is unavailable."),
        )
    if readiness is not None:
        require_exact_parent(
            "NPI Readiness Instance Revision",
            str(readiness.global_id),
            {
                "global_id": str(readiness.global_id),
                "instance_version": readiness.version,
                "snapshot_hash": readiness.snapshot_hash,
                "project_global_id": str(value.project.global_id),
                "tenant_id": value.tenant_id,
            },
            _("The exact Readiness Instance revision is unavailable."),
        )
    _expect_json(document.project_snapshot, value.project.snapshot_payload(), _("Production Transition Project Snapshot"))
    _expect_array(document.slot_snapshot, [item.snapshot_payload() for item in value.slots], _("Handover Acknowledgement Slot Snapshot"))
    _expect_array(document.manifest_snapshot, [item.snapshot_payload() for item in value.manifest], _("Handover Object Manifest Snapshot"))
    selector = {
        "mode": UNRESOLVED_ACTION_SELECTOR["mode"],
        "kinds": list(UNRESOLVED_ACTION_SELECTOR["kinds"]),
    }
    _expect_json(document.unresolved_selector_snapshot, selector, _("Unresolved Work Item Selector Snapshot"))
    _expect_array(document.unresolved_action_snapshot, [item.snapshot_payload() for item in value.unresolved_actions], _("Unresolved Work Item Snapshot"))
    document.project = str(value.project.global_id)
    document.policy_version = str(value.policy_ref.global_id)
    _expect_version_key_hash(document, value.version_key_hash)
    document.version_key_hash = value.version_key_hash
    document.project_snapshot = canonical_json(value.project.snapshot_payload())
    document.slot_snapshot = canonical_json([item.snapshot_payload() for item in value.slots])
    document.manifest_snapshot = canonical_json([item.snapshot_payload() for item in value.manifest])
    document.unresolved_selector_snapshot = canonical_json(selector)
    document.unresolved_action_snapshot = canonical_json([item.snapshot_payload() for item in value.unresolved_actions])
    document.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
    document.package_snapshot = canonical_json(value.snapshot_payload())
    document.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))


def normalize_handover_acknowledgement_identity(document: Any) -> None:
    _normalize_identity(
        document,
        (
            ("global_id", _("Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("handover_global_id", _("Handover Package Global ID")),
            ("package_revision_global_id", _("Handover Package Revision Global ID")),
            ("member_global_id", _("Project Member Global ID")),
            ("role_global_id", _("Project Role Assignment Global ID")),
            ("request_id", _("Request ID")),
        ),
    )


def validate_handover_acknowledgement_document(document: Any) -> None:
    supplied = json_object(
        document.acknowledgement_snapshot,
        _("Handover Acknowledgement Snapshot"),
    )
    value = _domain_value(lambda: acknowledgement_from_snapshot(supplied))
    _expect_fields(
        (
            document.global_id,
            document.handover_global_id,
            document.package_revision_global_id,
            int(document.package_version),
            document.package_snapshot_hash,
            document.slot_key,
            document.acknowledgement_intent,
            document.actor_user_id,
            document.member_global_id,
            int(document.member_optimistic_version),
            document.member_snapshot_hash,
            document.role_global_id,
            int(document.role_optimistic_version),
            document.role_snapshot_hash,
            document.request_id,
            document.trace_id,
        ),
        (
            str(value.global_id),
            str(value.handover_global_id),
            str(value.package_revision_global_id),
            value.package_version,
            value.package_snapshot_hash,
            value.slot_key,
            "acknowledge_exact_package_slot",
            value.actor_user_id,
            str(value.member_global_id),
            value.member_optimistic_version,
            value.member_snapshot_hash,
            str(value.role_global_id),
            value.role_optimistic_version,
            value.role_snapshot_hash,
            str(value.request_id),
            value.trace_id,
        ),
        _("Handover Acknowledgement fields do not match the exact snapshot."),
    )
    package = require_exact_parent(
        "NPI Handover Package Revision",
        str(value.package_revision_global_id),
        {
            "global_id": str(value.package_revision_global_id),
            "handover_global_id": str(value.handover_global_id),
            "handover_version": value.package_version,
            "snapshot_hash": value.package_snapshot_hash,
        },
        _("The exact Handover Package revision is unavailable."),
        extra_fields=("tenant_id", "project_global_id", "package_snapshot"),
    )
    _expect_fields(
        (document.tenant_id, document.project_global_id),
        (str(package["tenant_id"]), str(package["project_global_id"])),
        _("The Handover Acknowledgement does not match its Project."),
    )
    package_snapshot = json_object(
        package["package_snapshot"],
        _("Handover Package Revision Snapshot"),
    )
    package_value = _domain_value(
        lambda: handover_package_from_snapshot(package_snapshot)
    )
    if (
        package_value.global_id != value.package_revision_global_id
        or package_value.handover_global_id != value.handover_global_id
        or package_value.handover_version != value.package_version
        or package_value.snapshot_hash != value.package_snapshot_hash
        or package_value.tenant_id != document.tenant_id
        or str(package_value.project.global_id) != document.project_global_id
    ):
        frappe.throw(
            _("The acknowledgement does not match its frozen actor slot."),
            frappe.ValidationError,
        )
    _validate_acknowledgement_package_slot(value, package_value)
    document.project = document.project_global_id
    document.package_revision = str(value.package_revision_global_id)
    document.actor_user_id = actor_text(value.actor_user_id, _("Actor User ID"))
    document.acknowledged_at = frappe_utc_datetime_text(value.acknowledged_at, _("Acknowledged At"))
    document.acknowledgement_snapshot = canonical_json(value.snapshot_payload())
    document.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))


def _validate_acknowledgement_package_slot(value: Any, package_value: Any) -> None:
    matches = [
        slot for slot in package_value.slots if slot.slot_key == value.slot_key
    ]
    if len(matches) != 1:
        frappe.throw(
            _("Select one exact required acknowledgement slot."),
            frappe.ValidationError,
        )
    slot = matches[0]
    if (
        value.actor_user_id != slot.member.user_id
        or value.member_global_id != slot.member.global_id
        or value.member_optimistic_version != slot.member.optimistic_version
        or value.member_snapshot_hash != slot.member.snapshot_hash
        or value.role_global_id != slot.role.global_id
        or value.role_optimistic_version != slot.role.optimistic_version
        or value.role_snapshot_hash != slot.role.snapshot_hash
    ):
        frappe.throw(
            _("The acknowledgement does not match its frozen actor slot."),
            frappe.ValidationError,
        )


def normalize_observation_period_identity(document: Any) -> None:
    _normalize_identity(
        document,
        (
            ("global_id", _("Global ID")),
            ("observation_global_id", _("Observation Period Global ID")),
            ("project_global_id", _("Project Global ID")),
            (
                "policy_version_global_id",
                _("Production Transition Policy Version Global ID"),
            ),
            ("request_id", _("Request ID")),
        ),
        (
            (
                "predecessor_global_id",
                _("Predecessor Observation Period Revision Global ID"),
            ),
            (
                "handover_package_revision_global_id",
                _("Handover Package Revision Global ID"),
            ),
        ),
    )


def validate_observation_period_document(document: Any) -> None:
    supplied = json_object(
        document.observation_snapshot,
        _("Observation Period Revision Snapshot"),
    )
    value = _domain_value(lambda: observation_from_snapshot(supplied))
    handover = value.handover_package_ref
    _expect_fields(
        (
            document.global_id,
            document.observation_global_id,
            int(document.observation_version),
            document.predecessor_global_id or None,
            document.predecessor_snapshot_hash or None,
            document.tenant_id,
            document.project_global_id,
            int(document.project_optimistic_version),
            document.project_snapshot_hash,
            document.policy_version_global_id,
            int(document.policy_business_version),
            document.policy_snapshot_hash,
            document.handover_package_revision_global_id or None,
            int(document.handover_package_version)
            if document.handover_package_version not in (None, "", 0)
            else None,
            document.handover_package_snapshot_hash or None,
            document.observation_state,
            document.technical_disposition,
            document.retrospective_note or None,
            document.reason,
            document.created_by_user_id,
            document.request_id,
            document.trace_id,
        ),
        (
            str(value.global_id),
            str(value.observation_global_id),
            value.observation_version,
            str(value.predecessor_global_id) if value.predecessor_global_id else None,
            value.predecessor_snapshot_hash,
            value.tenant_id,
            str(value.project.global_id),
            value.project.optimistic_version,
            value.project.snapshot_hash,
            str(value.policy_ref.global_id),
            value.policy_ref.version,
            value.policy_ref.snapshot_hash,
            str(handover.global_id) if handover else None,
            handover.version if handover else None,
            handover.snapshot_hash if handover else None,
            value.observation_state.value,
            value.technical_disposition.value,
            value.retrospective_note,
            value.reason,
            value.created_by_user_id,
            str(value.request_id),
            value.trace_id,
        ),
        _("Observation Period fields do not match the exact snapshot."),
    )
    _require_exact_project(value)
    require_exact_parent(
        "NPI Production Transition Policy Version",
        str(value.policy_ref.global_id),
        {
            "global_id": str(value.policy_ref.global_id),
            "policy_version": value.policy_ref.version,
            "publication_state": "published",
            "snapshot_hash": value.policy_ref.snapshot_hash,
        },
        _("The published Production Transition Policy version is unavailable."),
    )
    if value.predecessor_global_id is not None:
        require_exact_parent(
            "NPI Observation Period Revision",
            str(value.predecessor_global_id),
            {
                "global_id": str(value.predecessor_global_id),
                "observation_global_id": str(value.observation_global_id),
                "observation_version": value.observation_version - 1,
                "snapshot_hash": value.predecessor_snapshot_hash,
            },
            _("The predecessor Observation Period revision is unavailable."),
        )
    if handover is not None:
        require_exact_parent(
            "NPI Handover Package Revision",
            str(handover.global_id),
            {
                "global_id": str(handover.global_id),
                "handover_version": handover.version,
                "snapshot_hash": handover.snapshot_hash,
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project.global_id),
            },
            _("The exact Handover Package revision is unavailable."),
        )
    _expect_json(document.project_snapshot, value.project.snapshot_payload(), _("Production Transition Project Snapshot"))
    _expect_array(document.provider_source_snapshot, [item.snapshot_payload() for item in value.providers], _("Observation Provider Source Snapshot"))
    _expect_array(document.context_reference_snapshot, [item.snapshot_payload() for item in value.context_references], _("Observation Context Reference Snapshot"))
    _expect_array(document.retrospective_evidence_snapshot, [item.snapshot_payload() for item in value.retrospective_references], _("Observation Retrospective Evidence Snapshot"))
    document.project = str(value.project.global_id)
    document.policy_version = str(value.policy_ref.global_id)
    document.handover_package_revision = str(handover.global_id) if handover else None
    _expect_version_key_hash(document, value.version_key_hash)
    document.version_key_hash = value.version_key_hash
    document.project_snapshot = canonical_json(value.project.snapshot_payload())
    document.provider_source_snapshot = canonical_json([item.snapshot_payload() for item in value.providers])
    document.context_reference_snapshot = canonical_json([item.snapshot_payload() for item in value.context_references])
    document.retrospective_evidence_snapshot = canonical_json([item.snapshot_payload() for item in value.retrospective_references])
    document.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
    document.observation_snapshot = canonical_json(value.snapshot_payload())
    document.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))


def _require_exact_project(value: Any) -> None:
    project = value.project
    require_exact_parent(
        "NPI Engineering Project",
        str(project.global_id),
        {
            "global_id": str(project.global_id),
            "tenant_id": project.tenant_id,
            "optimistic_version": project.optimistic_version,
            "business_code": project.business_code,
            "title": project.title,
            "project_type": project.project_type.value,
            "owner_user_id": project.owner_user_id,
            "target_sop": (
                project.target_sop_date.isoformat()
                if project.target_sop_date is not None
                else None
            ),
            "lifecycle_state": project.lifecycle_state,
            "template_global_id": str(project.template_ref.global_id),
            "template_version": project.template_ref.version,
            "template_snapshot_hash": project.template_ref.snapshot_hash,
            "work_policy_global_id": str(project.work_policy_ref.global_id),
            "work_policy_version": project.work_policy_ref.version,
            "work_policy_snapshot_hash": project.work_policy_ref.snapshot_hash,
        },
        _("The exact Project transition snapshot is unavailable."),
    )


def _normalize_identity(
    document: Any,
    required: tuple[tuple[str, str], ...],
    optional: tuple[tuple[str, str], ...] = (),
) -> None:
    for fieldname, label in required:
        setattr(document, fieldname, canonical_uuid(getattr(document, fieldname), label))
    for fieldname, label in optional:
        setattr(document, fieldname, optional_uuid(getattr(document, fieldname), label))
    if hasattr(document, "tenant_id"):
        document.tenant_id = tenant_text(document.tenant_id)
    document.name = document.global_id


def _domain_value(factory: Callable[[], _T]) -> _T:
    try:
        return factory()
    except (RequestValidationFailed, ValueError, TypeError, KeyError) as error:
        message = _("Enter a valid immutable production transition snapshot.")
        if isinstance(error, RequestValidationFailed):
            message = error.title
            if error.field_errors:
                candidate = error.field_errors[0].get("message")
                if isinstance(candidate, str) and candidate:
                    message = candidate
        frappe.throw(message, frappe.ValidationError)
    raise AssertionError("Frappe validation must raise.")


def _expect_fields(actual: tuple[object, ...], expected: tuple[object, ...], message: str) -> None:
    if actual != expected:
        frappe.throw(message, frappe.ValidationError)


def _expect_json(value: object, expected: object, label: str) -> None:
    if json_object(value, label) != expected:
        frappe.throw(
            _("Stored JSON does not match the exact production transition snapshot."),
            frappe.ValidationError,
        )


def _expect_array(value: object, expected: list[object], label: str) -> None:
    if json_array(value, label) != expected:
        frappe.throw(
            _("Stored list does not match the exact production transition snapshot."),
            frappe.ValidationError,
        )


def _expect_version_key_hash(document: Any, expected: str) -> None:
    if document.version_key_hash not in (None, "", expected):
        frappe.throw(
            _("Production transition version key hash does not match."),
            frappe.ValidationError,
        )
