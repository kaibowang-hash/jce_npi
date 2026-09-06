from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

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
from npi_core.tooling.engineering_controls_domain import (
    ToolingDefectContextKind,
    defect_revision_from_snapshot,
    validate_tooling_defect_successor,
)
from npi_core.tooling.frappe_validation import (
    deny_tooling_history_delete,
    deny_tooling_history_update,
    require_tooling_command_write,
    tooling_domain_value,
)


class NPIToolingDefectRevision(Document):
    """Immutable Tooling defect, action and verification revision."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_tooling_command_write()

    def before_save(self) -> None:
        require_tooling_command_write()
        if self.get_doc_before_save() is not None:
            deny_tooling_history_update()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("defect_global_id", _("Tooling Defect Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("tooling_master_global_id", _("Tooling Master Global ID")),
            ("tooling_revision_global_id", _("Tooling Revision Global ID")),
            ("request_id", _("Request ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.cavity_global_id = optional_uuid(self.cavity_global_id, _("Cavity Global ID"))
        self.predecessor_global_id = optional_uuid(
            self.predecessor_global_id,
            _("Predecessor Tooling Defect Global ID"),
        )
        self.responsible_member_global_id = optional_uuid(
            self.responsible_member_global_id,
            _("Responsible Project Member Global ID"),
        )
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_tooling_history_update()
        supplied = json_object(self.defect_snapshot, _("Tooling Defect Revision Snapshot"))
        value = tooling_domain_value(lambda: defect_revision_from_snapshot(supplied))
        expected = (
            str(value.global_id), str(value.defect_global_id), value.tenant_id,
            str(value.project_global_id), str(value.tooling_master_global_id),
            str(value.tooling_revision_global_id), value.tooling_revision_snapshot_hash,
            str(value.cavity_global_id) if value.cavity_global_id else None,
            value.cavity_identifier, value.defect_version,
            str(value.predecessor_global_id) if value.predecessor_global_id else None,
            value.predecessor_snapshot_hash, value.business_code, value.title,
            value.description, value.category_key, value.severity.value,
            int(value.blocking), value.state.value,
            str(value.responsible_member.global_id) if value.responsible_member else None,
            value.root_cause_state.value, value.root_cause, value.target_round_label,
            str(value.request_id), value.trace_id,
        )
        actual = (
            self.global_id, self.defect_global_id, self.tenant_id,
            self.project_global_id, self.tooling_master_global_id,
            self.tooling_revision_global_id, self.tooling_revision_snapshot_hash,
            self.cavity_global_id, self.cavity_identifier or None,
            self.defect_version, self.predecessor_global_id,
            self.predecessor_snapshot_hash or None, self.business_code, self.title,
            self.description, self.category_key, self.severity,
            int(self.blocking or 0), self.state, self.responsible_member_global_id,
            self.root_cause_state, self.root_cause or None,
            self.target_round_label or None, self.request_id, self.trace_id,
        )
        if actual != expected:
            frappe.throw(
                _("Tooling Defect Revision fields do not match the exact snapshot."),
                frappe.ValidationError,
            )
        if self.version_key_hash not in (None, "", value.version_key_hash):
            frappe.throw(_("Tooling Defect Version Key Hash does not match."), frappe.ValidationError)
        if self.snapshot_hash not in (None, "", value.snapshot_hash):
            frappe.throw(_("Tooling Defect Revision Snapshot Hash does not match."), frappe.ValidationError)
        for supplied_snapshot, expected_snapshot, label in (
            (
                json_object(self.detection_context_snapshot, _("Defect Detection Context Snapshot")),
                value.detection_context.snapshot_payload(),
                _("Defect Detection Context Snapshot"),
            ),
            (
                json_array(self.action_snapshot, _("Defect Action Snapshot")),
                [item.snapshot_payload() for item in value.actions],
                _("Defect Action Snapshot"),
            ),
            (
                json_array(self.evidence_snapshot, _("Defect Evidence Snapshot")),
                [item.snapshot_payload() for item in value.evidence],
                _("Defect Evidence Snapshot"),
            ),
        ):
            if supplied_snapshot != expected_snapshot:
                frappe.throw(
                    _("{field} does not match the exact Tooling defect.").format(field=label),
                    frappe.ValidationError,
                )
        require_exact_parent(
            "NPI Tooling Master",
            str(value.tooling_master_global_id),
            {"global_id": str(value.tooling_master_global_id), "tenant_id": value.tenant_id},
            _("The Tooling Master is unavailable for this defect."),
        )
        revision = require_exact_parent(
            "NPI Tooling Revision",
            str(value.tooling_revision_global_id),
            {
                "global_id": str(value.tooling_revision_global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "tooling_master_global_id": str(value.tooling_master_global_id),
                "snapshot_hash": value.tooling_revision_snapshot_hash,
            },
            _("The Tooling Revision is unavailable for this defect."),
            extra_fields=("cavity_snapshot",),
        )
        if value.cavity_global_id is not None:
            cavities = json_array(revision["cavity_snapshot"], _("Cavity Snapshot"))
            expected_cavity = (str(value.cavity_global_id), value.cavity_identifier)
            if expected_cavity not in {
                (item.get("globalId"), item.get("cavityIdentifier"))
                for item in cavities
                if isinstance(item, dict)
            }:
                frappe.throw(_("The exact cavity is unavailable for this defect."), frappe.ValidationError)
        if value.predecessor_global_id is not None:
            predecessor = require_exact_parent(
                "NPI Tooling Defect Revision",
                str(value.predecessor_global_id),
                {
                    "global_id": str(value.predecessor_global_id),
                    "defect_global_id": str(value.defect_global_id),
                    "tenant_id": value.tenant_id,
                    "project_global_id": str(value.project_global_id),
                    "tooling_master_global_id": str(value.tooling_master_global_id),
                    "snapshot_hash": value.predecessor_snapshot_hash,
                },
                _("The predecessor Tooling Defect Revision is unavailable."),
                extra_fields=("defect_snapshot",),
            )
            current = tooling_domain_value(
                lambda: defect_revision_from_snapshot(
                    json_object(predecessor["defect_snapshot"], _("Tooling Defect Revision Snapshot"))
                )
            )
            tooling_domain_value(lambda: validate_tooling_defect_successor(current, value))
        _require_member(value.responsible_member, value)
        for action in value.actions:
            _require_member(action.responsible_member, value)
            _require_evidence(action.evidence, value)
        _require_evidence(value.evidence, value)
        _require_detection_context(value)
        self.tooling_master = str(value.tooling_master_global_id)
        self.tooling_revision = str(value.tooling_revision_global_id)
        self.responsible_member = (
            str(value.responsible_member.global_id) if value.responsible_member else None
        )
        self.version_key_hash = value.version_key_hash
        self.reason = value.reason
        self.created_by_user_id = value.created_by_user_id
        self.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
        self.detection_context_snapshot = canonical_json(value.detection_context.snapshot_payload())
        self.action_snapshot = canonical_json([item.snapshot_payload() for item in value.actions])
        self.evidence_snapshot = canonical_json([item.snapshot_payload() for item in value.evidence])
        self.defect_snapshot = canonical_json(value.snapshot_payload())
        self.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))

    def on_trash(self) -> None:
        deny_tooling_history_delete(self)


def _require_member(member, value) -> None:
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
        _("A responsible Project member is unavailable for this defect."),
    )


def _require_evidence(evidence, value) -> None:
    for item in evidence:
        require_exact_parent(
            "NPI File Revision",
            str(item.file_revision_global_id),
            {
                "global_id": str(item.file_revision_global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "optimistic_version": item.file_optimistic_version,
                "frappe_content_hash": item.frappe_content_hash,
                "file_name": item.file_name,
                "mime_type": item.mime_type,
                "size_bytes": item.size_bytes,
                "sha256": item.sha256,
                "scan_state": "clean",
                "is_private": 1,
            },
            _("A clean private File Revision is unavailable for this defect."),
        )


def _require_detection_context(value) -> None:
    context = value.detection_context
    if context.kind in {
        ToolingDefectContextKind.TOOLING_REVISION,
        ToolingDefectContextKind.UNAVAILABLE_TRIAL_CONTEXT,
    }:
        if context.kind is ToolingDefectContextKind.TOOLING_REVISION and (
            context.global_id != value.tooling_revision_global_id
            or context.snapshot_hash != value.tooling_revision_snapshot_hash
        ):
            frappe.throw(_("Defect detection context does not match the Tooling Revision."), frappe.ValidationError)
        return
    doctype = {
        ToolingDefectContextKind.MANUFACTURING_MILESTONE_OBSERVATION: "NPI Tooling Manufacturing Milestone Observation",
        ToolingDefectContextKind.TOOLING_INTAKE: "NPI Tooling Intake",
    }[context.kind]
    require_exact_parent(
        doctype,
        str(context.global_id),
        {
            "global_id": str(context.global_id),
            "tenant_id": value.tenant_id,
            "project_global_id": str(value.project_global_id),
            "tooling_master_global_id": str(value.tooling_master_global_id),
            "snapshot_hash": context.snapshot_hash,
        },
        _("The exact defect detection context is unavailable."),
    )
