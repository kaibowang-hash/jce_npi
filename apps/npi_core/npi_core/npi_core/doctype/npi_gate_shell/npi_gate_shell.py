from __future__ import annotations

import hashlib
import json

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.controlled_evidence_validation import GATE_EVIDENCE_COMMAND_FLAG
from npi_core.gate_review.frappe_validation import GATE_REVIEW_COMMAND_FLAG
from npi_core.project.frappe_validation import (
    assert_immutable_fields,
    deny_controlled_history_delete,
    ensure_uuid,
    require_project_command_write,
)


class NPIGateShell(Document):
    """Ordered Gate shell created atomically with an Engineering Project draft."""

    _REVIEW_CONTEXT_FIELDS = (
        "current_review_cycle",
        "current_review_cycle_global_id",
        "review_policy_global_id",
        "review_policy_version",
        "review_policy_snapshot_hash",
    )
    _REVIEW_DECISION_FIELDS = (
        "latest_decision_snapshot",
        "latest_decision_snapshot_global_id",
        "latest_decision_snapshot_hash",
        "latest_decision_outcome",
    )
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
        "state",
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
        if not self._is_gate_review_command():
            require_project_command_write()
        self._require_authorized_update()

    def _require_authorized_update(self) -> None:
        if (
            not self.is_new()
            and not self._is_gate_evidence_command()
            and not self._is_gate_review_command()
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
            self.review_input_version = 1
            self.requirements_frozen = 0
            self.review_state = "not_started"
            for fieldname in (
                *self._REVIEW_CONTEXT_FIELDS,
                *self._REVIEW_DECISION_FIELDS,
            ):
                self.set(fieldname, None)
        else:
            previous = self.get_doc_before_save()
            if (
                previous is not None
                and self._is_gate_evidence_command()
                and not self._is_gate_review_command()
            ):
                self.review_input_version = (
                    _persisted_review_input_version(previous) + 1
                )
            elif previous is not None and self.get("review_input_version") in (
                None,
                "",
            ):
                self.review_input_version = _persisted_review_input_version(previous)

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
        if type(self.review_input_version) is not int or self.review_input_version < 1:
            frappe.throw(
                _("{field} must be greater than zero.").format(
                    field=_("Review Input Version")
                ),
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
        self._validate_review_references()
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
            previous_input_version = _persisted_review_input_version(previous)
            if self._is_gate_review_command():
                if int(self.review_input_version) != previous_input_version:
                    frappe.throw(
                        _("A protected field cannot be changed."),
                        frappe.ValidationError,
                    )
                assert_immutable_fields(self, previous, self._FROZEN_FIELDS)
                if int(previous.requirements_frozen or 0) != 1:
                    frappe.throw(
                        _("The Gate command must freeze its requirements."),
                        frappe.ValidationError,
                    )
                self._validate_review_transition(previous)
            else:
                if self._is_gate_evidence_command():
                    if int(self.review_input_version) != previous_input_version + 1:
                        frappe.throw(
                            _("Review Input Version must advance by one."),
                            frappe.ValidationError,
                        )
                elif int(self.review_input_version) != previous_input_version:
                    frappe.throw(
                        _("A protected field cannot be changed."),
                        frappe.ValidationError,
                    )
                self._assert_review_fields_unchanged(previous)
                if int(previous.requirements_frozen or 0) == 1:
                    assert_immutable_fields(self, previous, self._FROZEN_FIELDS)
                elif int(self.requirements_frozen or 0) != 1:
                    frappe.throw(
                        _("The Gate command must freeze its requirements."),
                        frappe.ValidationError,
                    )

    def _validate_review_references(self) -> None:
        state = self.get("review_state") or "not_started"
        self.review_state = state
        if state not in {
            "not_started",
            "in_review",
            "decided",
            "requires_review",
        }:
            self._throw_incoherent_review_state()

        context_values = tuple(
            self.get(fieldname) for fieldname in self._REVIEW_CONTEXT_FIELDS
        )
        decision_values = tuple(
            self.get(fieldname) for fieldname in self._REVIEW_DECISION_FIELDS
        )
        if state == "not_started":
            if any(
                not _is_empty(value) for value in (*context_values, *decision_values)
            ):
                self._throw_incoherent_review_state()
            return

        if any(_is_empty(value) for value in context_values):
            self._throw_incoherent_review_state()
        self.current_review_cycle = ensure_uuid(
            self.current_review_cycle,
            _("Current Review Cycle"),
        )
        self.current_review_cycle_global_id = ensure_uuid(
            self.current_review_cycle_global_id,
            _("Current Review Cycle Global ID"),
        )
        if self.current_review_cycle != self.current_review_cycle_global_id:
            self._throw_incoherent_review_state()
        self.review_policy_global_id = ensure_uuid(
            self.review_policy_global_id,
            _("Review Policy Global ID"),
        )
        try:
            policy_version = (
                0
                if isinstance(self.review_policy_version, bool)
                else int(self.review_policy_version)
            )
        except (TypeError, ValueError):
            policy_version = 0
        if policy_version < 1:
            frappe.throw(
                _("{field} must be greater than zero.").format(
                    field=_("Review Policy Version")
                ),
                frappe.ValidationError,
            )
        self.review_policy_version = policy_version
        _validate_hash(
            self.review_policy_snapshot_hash,
            _("Review Policy Snapshot Hash"),
        )

        if state != "decided":
            if any(not _is_empty(value) for value in decision_values):
                self._throw_incoherent_review_state()
            return

        if any(_is_empty(value) for value in decision_values):
            self._throw_incoherent_review_state()
        self.latest_decision_snapshot = ensure_uuid(
            self.latest_decision_snapshot,
            _("Latest Decision Snapshot"),
        )
        self.latest_decision_snapshot_global_id = ensure_uuid(
            self.latest_decision_snapshot_global_id,
            _("Latest Decision Snapshot Global ID"),
        )
        if self.latest_decision_snapshot != self.latest_decision_snapshot_global_id:
            self._throw_incoherent_review_state()
        _validate_hash(
            self.latest_decision_snapshot_hash,
            _("Latest Decision Snapshot Hash"),
        )
        if self.latest_decision_outcome not in {
            "pass",
            "conditional_pass",
            "reject",
        }:
            self._throw_incoherent_review_state()

    def _validate_review_transition(self, previous: Document) -> None:
        previous_state = previous.get("review_state") or "not_started"
        current_state = self.review_state
        transition = (previous_state, current_state)
        if previous_state == current_state:
            if (
                current_state == "requires_review"
                and self.current_review_cycle_global_id
                != previous.get("current_review_cycle_global_id")
            ):
                assert_immutable_fields(
                    self,
                    previous,
                    self._REVIEW_CONTEXT_FIELDS[2:],
                )
                return
            self._assert_review_fields_unchanged(previous)
            return

        if transition not in {
            ("not_started", "in_review"),
            ("in_review", "requires_review"),
            ("in_review", "decided"),
            ("decided", "requires_review"),
            ("decided", "in_review"),
            ("requires_review", "in_review"),
        }:
            self._throw_incoherent_review_state()

        if transition in {
            ("in_review", "decided"),
            ("requires_review", "in_review"),
        }:
            assert_immutable_fields(
                self,
                previous,
                self._REVIEW_CONTEXT_FIELDS,
            )
        if current_state == "requires_review":
            assert_immutable_fields(
                self,
                previous,
                self._REVIEW_CONTEXT_FIELDS[2:],
            )
        if (
            current_state == "requires_review" or transition == ("decided", "in_review")
        ) and self.current_review_cycle_global_id == previous.get(
            "current_review_cycle_global_id"
        ):
            self._throw_incoherent_review_state()

    def _assert_review_fields_unchanged(self, previous: Document) -> None:
        previous_state = previous.get("review_state") or "not_started"
        if previous_state != self.review_state:
            frappe.throw(
                _("A protected field cannot be changed."),
                frappe.ValidationError,
            )
        for fieldname in (
            *self._REVIEW_CONTEXT_FIELDS,
            *self._REVIEW_DECISION_FIELDS,
        ):
            if _empty_as_none(previous.get(fieldname)) != _empty_as_none(
                self.get(fieldname)
            ):
                frappe.throw(
                    _("A protected field cannot be changed."),
                    frappe.ValidationError,
                )

    @staticmethod
    def _throw_incoherent_review_state() -> None:
        frappe.throw(
            _("Gate review state references are incomplete or inconsistent."),
            frappe.ValidationError,
        )

    @staticmethod
    def _is_gate_review_command() -> bool:
        return bool(getattr(frappe.flags, GATE_REVIEW_COMMAND_FLAG, False))

    @staticmethod
    def _is_gate_evidence_command() -> bool:
        return bool(getattr(frappe.flags, GATE_EVIDENCE_COMMAND_FLAG, False))

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


def _is_empty(value: object) -> bool:
    return value in (None, "", 0)


def _empty_as_none(value: object) -> object:
    return None if _is_empty(value) else value


def _persisted_review_input_version(document: Document) -> int:
    value = document.get("review_input_version")
    if value in (None, ""):
        return 1
    if type(value) is not int or value < 1:
        return 0
    return value


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
