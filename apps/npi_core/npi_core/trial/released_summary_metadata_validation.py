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
from npi_core.trial.released_summary_domain import (
    released_trial_summary_from_snapshot,
)


def normalize_released_summary_identity(document: Any) -> None:
    for fieldname, label in (
        ("global_id", _("Global ID")),
        ("summary_global_id", _("Released Trial Summary Global ID")),
        ("project_global_id", _("Project Global ID")),
        ("trial_plan_global_id", _("Trial Plan Global ID")),
        ("trial_round_global_id", _("Trial Round Global ID")),
        ("trial_plan_revision_global_id", _("Trial Plan Revision Global ID")),
        ("conclusion_revision_global_id", _("Trial Conclusion Revision Global ID")),
        ("request_id", _("Request ID")),
    ):
        setattr(document, fieldname, canonical_uuid(getattr(document, fieldname), label))
    document.predecessor_global_id = optional_uuid(
        document.predecessor_global_id,
        _("Predecessor Released Trial Summary Revision Global ID"),
    )
    document.tenant_id = tenant_text(document.tenant_id)


def validate_released_summary_document(document: Any) -> None:
    supplied = json_object(
        document.summary_snapshot,
        _("Released Trial Summary Revision Snapshot"),
    )
    value = trial_domain_value(lambda: released_trial_summary_from_snapshot(supplied))
    actual = (
        document.global_id,
        document.summary_global_id,
        document.tenant_id,
        document.project_global_id,
        document.trial_plan_global_id,
        document.trial_round_global_id,
        document.summary_version,
        document.predecessor_global_id or None,
        document.predecessor_snapshot_hash or None,
        document.trial_round_optimistic_version,
        document.trial_round_snapshot_hash,
        document.trial_plan_revision_global_id,
        document.trial_plan_revision_snapshot_hash,
        document.conclusion_revision_global_id,
        document.conclusion_version,
        document.conclusion_snapshot_hash,
        document.conclusion_state,
        document.conclusion_code,
        document.reason,
        document.created_by_user_id,
        document.request_id,
        document.trace_id,
    )
    expected = (
        str(value.global_id),
        str(value.summary_global_id),
        value.tenant_id,
        str(value.project_global_id),
        str(value.trial_plan_global_id),
        str(value.trial_round_global_id),
        value.summary_version,
        str(value.predecessor_global_id) if value.predecessor_global_id else None,
        value.predecessor_snapshot_hash,
        value.trial_round_optimistic_version,
        value.trial_round_snapshot_hash,
        str(value.trial_plan_revision_global_id),
        value.trial_plan_revision_snapshot_hash,
        str(value.conclusion_revision_global_id),
        value.conclusion_version,
        value.conclusion_snapshot_hash,
        value.conclusion_state.value,
        value.conclusion_code.value,
        value.reason,
        value.created_by_user_id,
        str(value.request_id),
        value.trace_id,
    )
    if actual != expected:
        frappe.throw(
            _("Released Trial Summary fields do not match the exact snapshot."),
            frappe.ValidationError,
        )
    for fieldname, expected_hash, label in (
        ("version_key_hash", value.version_key_hash, _("Released Trial Summary Version Key Hash")),
        ("source_manifest_hash", value.source_manifest_hash, _("Released Trial Summary Source Manifest Hash")),
        (
            "presentation_projection_hash",
            value.presentation_projection_hash,
            _("Released Trial Summary Presentation Projection Hash"),
        ),
        (
            "redaction_manifest_hash",
            value.redaction_manifest_hash,
            _("Released Trial Summary Redaction Manifest Hash"),
        ),
        ("snapshot_hash", value.snapshot_hash, _("Snapshot Hash")),
    ):
        supplied_hash = getattr(document, fieldname)
        if supplied_hash not in (None, "", expected_hash):
            frappe.throw(
                _("{object} does not match the exact snapshot.").format(object=label),
                frappe.ValidationError,
            )
        setattr(document, fieldname, lowercase_sha256(expected_hash, label))
    if json_array(document.source_manifest, _("Released Trial Summary Source Manifest")) != [
        item.snapshot_payload() for item in value.source_manifest
    ]:
        frappe.throw(
            _("Released Trial Summary sources do not match the exact snapshot."),
            frappe.ValidationError,
        )
    if json_object(
        document.presentation_projection,
        _("Released Trial Summary Presentation Projection"),
    ) != supplied["presentationProjection"]:
        frappe.throw(
            _("Released Trial Summary presentation does not match the exact snapshot."),
            frappe.ValidationError,
        )
    if json_object(
        document.redaction_manifest,
        _("Released Trial Summary Redaction Manifest"),
    ) != supplied["redactionManifest"]:
        frappe.throw(
            _("Released Trial Summary redaction does not match the exact snapshot."),
            frappe.ValidationError,
        )
    document.trial_round = str(value.trial_round_global_id)
    document.conclusion_revision = str(value.conclusion_revision_global_id)
    document.source_manifest = canonical_json(
        [item.snapshot_payload() for item in value.source_manifest]
    )
    document.presentation_projection = canonical_json(supplied["presentationProjection"])
    document.redaction_manifest = canonical_json(supplied["redactionManifest"])
    document.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
    document.summary_snapshot = canonical_json(value.snapshot_payload())
