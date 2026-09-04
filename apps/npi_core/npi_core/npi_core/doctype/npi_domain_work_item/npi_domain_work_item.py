from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.project_work.frappe_validation import (
    advance_version,
    deny_project_work_history_delete,
    normalize_uuid_fields,
    require_project_work_command_write,
    validate_hash,
    validate_key,
    validate_project_identity,
)


class NPIDomainWorkItem(Document):
    _KINDS = frozenset({"risk", "issue", "action", "decision_request"})
    _SEVERITIES = frozenset({"low", "medium", "high", "critical"})

    def before_insert(self) -> None:
        require_project_work_command_write()

    def before_save(self) -> None:
        require_project_work_command_write()

    def on_trash(self) -> None:
        deny_project_work_history_delete()

    def before_validate(self) -> None:
        self.source_system = "NPI_ONE"

    def validate(self) -> None:
        validate_project_identity(self)
        normalize_uuid_fields(
            self,
            (
                "stage_global_id",
                "wbs_item_global_id",
                "work_policy_global_id",
            ),
        )
        if self.kind not in self._KINDS:
            frappe.throw(
                _("Select a supported Work Item kind."),
                frappe.ValidationError,
            )
        if self.severity not in self._SEVERITIES:
            frappe.throw(
                _("Select a supported severity."),
                frappe.ValidationError,
            )
        if (
            not isinstance(self.title, str)
            or not self.title.strip()
            or len(self.title) > 280
        ):
            frappe.throw(
                _("Enter a Work Item title with no more than 280 characters."),
                frappe.ValidationError,
            )
        if self.detail and (
            not isinstance(self.detail, str) or len(self.detail) > 4000
        ):
            frappe.throw(
                _("Work Item Detail cannot exceed 4000 characters."),
                frappe.ValidationError,
            )
        if not self.due_at:
            frappe.throw(_("Due At is required."), frappe.ValidationError)
        if (
            not isinstance(self.owner_user_id, str)
            or len(self.owner_user_id) > 254
            or "@" not in self.owner_user_id
        ):
            frappe.throw(
                _("Select a valid Work Item owner."),
                frappe.ValidationError,
            )
        self.state_key = validate_key(self.state_key, _("State Key"))
        self.work_policy_snapshot_hash = validate_hash(
            self.work_policy_snapshot_hash,
            _("Work Policy Snapshot Hash"),
        )
        if type(self.work_policy_version) is not int or self.work_policy_version < 1:
            frappe.throw(
                _("Work Policy Version must be greater than zero."),
                frappe.ValidationError,
            )
        self.relations = _json_array(self.relations, _("Related Objects"))
        self.evidence_references = _json_array(
            self.evidence_references,
            _("Evidence References"),
        )
        advance_version(
            self,
            immutable_fields=(
                "global_id",
                "tenant_id",
                "project_global_id",
                "stage_global_id",
                "kind",
                "wbs_item_global_id",
                "state_key",
                "state_label_source",
                "state_terminal",
                "work_policy_global_id",
                "work_policy_version",
                "work_policy_snapshot_hash",
                "source_system",
            ),
        )


def _json_array(value: object, label: str) -> str:
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (TypeError, json.JSONDecodeError):
        parsed = None
    if not isinstance(parsed, list):
        frappe.throw(
            _("{field} must be a JSON array.").format(field=label),
            frappe.ValidationError,
        )
    return json.dumps(
        parsed,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
