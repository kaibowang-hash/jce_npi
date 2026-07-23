from __future__ import annotations

import json
import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.project.frappe_validation import (
    assert_immutable_fields,
    deny_controlled_history_delete,
    ensure_uuid,
    require_project_command_write,
)


class NPIGateShell(Document):
    """Ordered Gate shell created atomically with an Engineering Project draft."""

    _IDENTITY_FIELDS = (
        "global_id",
        "engineering_project",
        "project_global_id",
        "gate_key",
        "shell_key",
        "title",
        "sequence",
        "template_global_id",
        "template_version",
        "template_snapshot_hash",
        "template_gate_snapshot",
    )

    def before_insert(self) -> None:
        require_project_command_write()

    def before_save(self) -> None:
        require_project_command_write()

    def on_trash(self) -> None:
        deny_controlled_history_delete()

    def before_validate(self) -> None:
        if self.project_global_id and self.gate_key:
            self.shell_key = f"{self.project_global_id}:{self.gate_key}"
        if self.is_new():
            self.state = "not_started"
            self.optimistic_version = 1

    def validate(self) -> None:
        self.global_id = ensure_uuid(self.global_id, _("Global ID"))
        self.project_global_id = ensure_uuid(
            self.project_global_id,
            _("Project Global ID"),
        )
        self.template_global_id = ensure_uuid(
            self.template_global_id,
            _("Template Global ID"),
        )
        if self.sequence < 1:
            frappe.throw(_("Sequence must be greater than zero."), frappe.ValidationError)
        if self.optimistic_version < 1:
            frappe.throw(
                _("Optimistic Version must be greater than zero."),
                frappe.ValidationError,
            )
        try:
            snapshot = (
                json.loads(self.template_gate_snapshot)
                if isinstance(self.template_gate_snapshot, str)
                else self.template_gate_snapshot
            )
        except (TypeError, json.JSONDecodeError):
            snapshot = None
        if not isinstance(snapshot, dict):
            frappe.throw(
                _("Template Gate Snapshot must be a JSON object."),
                frappe.ValidationError,
            )
        if snapshot != {
            "key": self.gate_key,
            "sequence": self.sequence,
            "title": self.title,
        }:
            frappe.throw(
                _("Template Gate Snapshot does not match this Gate shell."),
                frappe.ValidationError,
            )
        project_identity = frappe.db.get_value(
            "NPI Engineering Project",
            self.engineering_project,
            [
                "global_id",
                "template_global_id",
                "template_version",
                "template_snapshot_hash",
            ],
            as_dict=True,
        )
        if not project_identity or (
            str(project_identity.global_id) != self.project_global_id
            or str(project_identity.template_global_id) != self.template_global_id
            or int(project_identity.template_version) != self.template_version
            or str(project_identity.template_snapshot_hash)
            != self.template_snapshot_hash
        ):
            frappe.throw(
                _("The Gate shell does not match its Engineering Project."),
                frappe.ValidationError,
            )
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, self._IDENTITY_FIELDS)
