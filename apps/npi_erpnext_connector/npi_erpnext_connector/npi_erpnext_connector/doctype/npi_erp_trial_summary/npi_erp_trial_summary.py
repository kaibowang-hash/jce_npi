from __future__ import annotations

import json
import re
from collections.abc import Mapping
from uuid import UUID

import frappe
from frappe import _
from frappe.model.document import Document

from npi_erpnext_connector.frappe_validation import (
    deny_trial_summary_execution_delete,
    require_trial_summary_execution_write,
)
from npi_erpnext_connector.trial_summary_contract import (
    CONCLUSION_CODES,
    CONCLUSION_STATES,
    EXTERNAL_EFFECTS,
    PRESENTATION_SCHEMA_VERSION,
    canonical_hash,
    canonical_json,
)

_HASH = re.compile(r"^[a-f0-9]{64}$")


class NPIERPTrialSummary(Document):
    def autoname(self) -> None:
        self.summary_revision_global_id = _uuid(
            self.summary_revision_global_id,
            _("Trial Summary Revision Global ID"),
        )
        self.name = self.summary_revision_global_id

    def before_insert(self) -> None:
        require_trial_summary_execution_write()

    def before_save(self) -> None:
        require_trial_summary_execution_write()
        if self.get_doc_before_save() is not None:
            frappe.throw(
                _("ERPNext Trial Summary projections are immutable."),
                frappe.PermissionError,
            )

    def validate(self) -> None:
        for fieldname, label in (
            ("summary_revision_global_id", _("Trial Summary Revision Global ID")),
            ("summary_global_id", _("Trial Summary Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("trial_plan_global_id", _("Trial Plan Global ID")),
            ("trial_round_global_id", _("Trial Round Global ID")),
            ("request_global_id", _("Delivery Request Global ID")),
        ):
            setattr(self, fieldname, _uuid(getattr(self, fieldname), label))
        if self.predecessor_global_id:
            self.predecessor_global_id = _uuid(
                self.predecessor_global_id,
                _("Predecessor Trial Summary Revision Global ID"),
            )
        for fieldname, label in (
            ("source_snapshot_hash", _("Source Snapshot Hash")),
            ("source_manifest_hash", _("Source Manifest Hash")),
            ("presentation_projection_hash", _("Presentation Projection Hash")),
            ("redaction_manifest_hash", _("Redaction Manifest Hash")),
            ("target_idempotency_key_hash", _("Target Idempotency Key Hash")),
            ("source_hash", _("Source Hash")),
            ("semantic_request_hash", _("Semantic Request Hash")),
        ):
            setattr(self, fieldname, _hash(getattr(self, fieldname), label))
        if type(self.summary_version) is not int or self.summary_version < 1:
            frappe.throw(_("Trial Summary Version is invalid."), frappe.ValidationError)
        if type(self.fact_count) is not int or not 0 <= self.fact_count <= 25_000:
            frappe.throw(_("Trial Summary Fact Count is invalid."), frappe.ValidationError)
        if (self.summary_version == 1) != (not self.predecessor_global_id):
            frappe.throw(
                _("The Trial Summary predecessor is invalid."),
                frappe.ValidationError,
            )
        if (
            self.projection_purpose != "erpnext_read_only_engineering_evidence"
            or bool(self.formal_mp_acceptance)
        ):
            frappe.throw(
                _("The Trial Summary projection purpose is invalid."),
                frappe.ValidationError,
            )
        projection = _json_object(
            self.presentation_projection,
            _("The stored Trial Summary presentation projection is invalid."),
        )
        redaction = _json_object(
            self.redaction_manifest,
            _("The stored Trial Summary redaction manifest is invalid."),
        )
        source_manifest = projection.get("sourceManifest")
        if (
            canonical_json(projection) != str(self.presentation_projection)
            or canonical_hash(projection) != self.presentation_projection_hash
            or not isinstance(source_manifest, list)
            or canonical_hash(source_manifest) != self.source_manifest_hash
            or projection.get("schemaVersion") != PRESENTATION_SCHEMA_VERSION
            or projection.get("projectGlobalId") != self.project_global_id
            or projection.get("trialPlanGlobalId") != self.trial_plan_global_id
            or projection.get("trialRoundGlobalId") != self.trial_round_global_id
            or projection.get("conclusionState") != self.conclusion_state
            or projection.get("conclusionCode") != self.conclusion_code
            or projection.get("externalEffects") != EXTERNAL_EFFECTS
            or self.conclusion_state not in CONCLUSION_STATES
            or self.conclusion_code not in CONCLUSION_CODES
        ):
            frappe.throw(
                _("The stored Trial Summary presentation projection is invalid."),
                frappe.ValidationError,
            )
        if (
            canonical_json(redaction) != str(self.redaction_manifest)
            or canonical_hash(redaction) != self.redaction_manifest_hash
            or redaction.get("externalProjection") != "unavailable"
        ):
            frappe.throw(
                _("The stored Trial Summary redaction manifest is invalid."),
                frappe.ValidationError,
            )

    def on_trash(self) -> None:
        deny_trial_summary_execution_delete()


def _uuid(value: object, label: str) -> str:
    try:
        parsed = UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise frappe.ValidationError(_("{field} is invalid.").format(field=label)) from error
    if parsed.int == 0 or str(parsed) != str(value).casefold():
        frappe.throw(_("{field} is invalid.").format(field=label), frappe.ValidationError)
    return str(parsed)


def _hash(value: object, label: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        frappe.throw(_("{field} is invalid.").format(field=label), frappe.ValidationError)
    return value


def _json_object(value: object, message: str) -> Mapping[str, object]:
    if not isinstance(value, str) or len(value.encode("utf-8")) > 1_048_576:
        frappe.throw(message, frappe.ValidationError)
    try:
        parsed = json.loads(
            value,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()),
        )
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise frappe.ValidationError(message) from error
    if not isinstance(parsed, Mapping):
        frappe.throw(message, frappe.ValidationError)
    return parsed
