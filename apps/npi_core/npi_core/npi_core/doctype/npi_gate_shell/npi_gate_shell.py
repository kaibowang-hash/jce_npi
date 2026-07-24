from __future__ import annotations

import hashlib
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
        "gate_template_global_id",
        "gate_template_version",
        "gate_template_snapshot_hash",
    )
    _FROZEN_FIELDS = (
        "requirements_frozen",
        "gate_due_date",
        "requirement_snapshot",
        "requirement_snapshot_hash",
        "requirements_frozen_at",
        "requirements_frozen_by",
    )

    def before_insert(self) -> None:
        require_project_command_write()

    def before_save(self) -> None:
        require_project_command_write()
        self._require_authorized_update()

    def _require_authorized_update(self) -> None:
        if not self.is_new() and not getattr(
            frappe.flags,
            "npi_gate_evidence_command_write",
            False,
        ):
            frappe.throw(
                _(
                    "Gate evidence records can only be changed through an authorized NPI Gate command."
                ),
                frappe.PermissionError,
            )

    def on_trash(self) -> None:
        deny_controlled_history_delete()

    def before_validate(self) -> None:
        self._require_authorized_update()
        if self.project_global_id and self.gate_key:
            self.shell_key = f"{self.project_global_id}:{self.gate_key}"
        if self.is_new():
            self.state = "not_started"
            self.optimistic_version = 1
            self.requirements_frozen = 0

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
            frappe.throw(
                _("Sequence must be greater than zero."), frappe.ValidationError
            )
        if self.optimistic_version < 1:
            frappe.throw(
                _("Optimistic Version must be greater than zero."),
                frappe.ValidationError,
            )
        snapshot = _json_object(self.template_gate_snapshot)
        if not isinstance(snapshot, dict):
            frappe.throw(
                _("Template Gate Snapshot must be a JSON object."),
                frappe.ValidationError,
            )
        expected_gate_snapshot: dict[str, object] = {
            "key": self.gate_key,
            "sequence": self.sequence,
            "title": self.title,
        }
        template_ref_values = (
            self.gate_template_global_id,
            self.gate_template_version,
            self.gate_template_snapshot_hash,
        )
        if any(value not in (None, "", 0) for value in template_ref_values):
            if not all(value not in (None, "", 0) for value in template_ref_values):
                frappe.throw(
                    _("The Gate Template reference is incomplete."),
                    frappe.ValidationError,
                )
            self.gate_template_global_id = ensure_uuid(
                self.gate_template_global_id,
                _("Gate Template Global ID"),
            )
            if int(self.gate_template_version) < 1:
                frappe.throw(
                    _("Gate Template Version must be greater than zero."),
                    frappe.ValidationError,
                )
            _validate_hash(
                self.gate_template_snapshot_hash,
                _("Gate Template Snapshot Hash"),
            )
            expected_gate_snapshot["gateTemplateRef"] = {
                "globalId": self.gate_template_global_id,
                "version": int(self.gate_template_version),
                "snapshotHash": self.gate_template_snapshot_hash,
            }
        if snapshot != expected_gate_snapshot:
            frappe.throw(
                _("Template Gate Snapshot does not match this Gate shell."),
                frappe.ValidationError,
            )
        self.template_gate_snapshot = _canonical_json(snapshot)
        self._validate_frozen_requirements()
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
            if int(self.optimistic_version) != int(previous.optimistic_version) + 1:
                frappe.throw(
                    _("Optimistic Version must advance by one."),
                    frappe.ValidationError,
                )
            if int(previous.requirements_frozen or 0) == 1:
                assert_immutable_fields(self, previous, self._FROZEN_FIELDS)
            elif int(self.requirements_frozen or 0) != 1:
                frappe.throw(
                    _("The Gate command must freeze its requirements."),
                    frappe.ValidationError,
                )

    def _validate_frozen_requirements(self) -> None:
        frozen = int(self.requirements_frozen or 0)
        values = (
            self.gate_due_date,
            self.requirement_snapshot,
            self.requirement_snapshot_hash,
            self.requirements_frozen_at,
            self.requirements_frozen_by,
        )
        if frozen == 0:
            if any(value not in (None, "") for value in values):
                frappe.throw(
                    _("Unfrozen Gate requirements cannot contain snapshot data."),
                    frappe.ValidationError,
                )
            return
        if frozen != 1 or not self.gate_template_global_id:
            frappe.throw(
                _("Only a configured Gate can freeze requirements."),
                frappe.ValidationError,
            )
        if any(value in (None, "") for value in values):
            frappe.throw(
                _("Frozen Gate requirement data is incomplete."),
                frappe.ValidationError,
            )
        payload = _json_object(self.requirement_snapshot)
        if (
            not isinstance(payload, dict)
            or set(payload)
            != {
                "schemaVersion",
                "gateTemplateRef",
                "gateDueDate",
                "requirements",
            }
            or payload.get("schemaVersion") != 1
            or not isinstance(payload.get("requirements"), list)
            or not payload["requirements"]
        ):
            frappe.throw(
                _("Requirement Snapshot must be a valid frozen snapshot."),
                frappe.ValidationError,
            )
        expected_ref = {
            "globalId": self.gate_template_global_id,
            "version": int(self.gate_template_version),
            "snapshotHash": self.gate_template_snapshot_hash,
        }
        if payload.get("gateTemplateRef") != expected_ref or str(
            payload.get("gateDueDate")
        ) != str(self.gate_due_date):
            frappe.throw(
                _("Requirement Snapshot does not match this Gate."),
                frappe.ValidationError,
            )
        for requirement in payload["requirements"]:
            if (
                not isinstance(requirement, dict)
                or set(requirement)
                != {
                    "globalId",
                    "key",
                    "title",
                    "classification",
                    "priority",
                    "allowedEvidenceKinds",
                    "ownerMemberId",
                    "reviewerMemberIds",
                    "dueDate",
                }
                or requirement.get("classification") not in {"required", "optional"}
                or requirement.get("priority") not in {"P0", "P1", "P2"}
                or not isinstance(requirement.get("allowedEvidenceKinds"), list)
                or not requirement["allowedEvidenceKinds"]
                or not isinstance(requirement.get("reviewerMemberIds"), list)
                or not requirement["reviewerMemberIds"]
            ):
                frappe.throw(
                    _("Requirement Snapshot contains an invalid requirement."),
                    frappe.ValidationError,
                )
            ensure_uuid(requirement["globalId"], _("Global ID"))
            ensure_uuid(
                requirement["ownerMemberId"],
                _("Owner Member Global ID"),
            )
            reviewers = [
                ensure_uuid(value, _("Reviewer Member Global ID"))
                for value in requirement["reviewerMemberIds"]
            ]
            if len(reviewers) != len(set(reviewers)):
                frappe.throw(
                    _("Reviewer member identities must be unique."),
                    frappe.ValidationError,
                )
        _validate_hash(
            self.requirement_snapshot_hash,
            _("Requirement Snapshot Hash"),
        )
        if _sha256_json(payload) != self.requirement_snapshot_hash:
            frappe.throw(
                _("Requirement Snapshot Hash does not match its content."),
                frappe.ValidationError,
            )
        self.requirement_snapshot = _canonical_json(payload)


def _json_object(value: object) -> dict[str, object] | None:
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (TypeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _sha256_json(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _validate_hash(value: object, label: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        frappe.throw(
            _("{field} must be a lowercase SHA-256 hash.").format(field=label),
            frappe.ValidationError,
        )
