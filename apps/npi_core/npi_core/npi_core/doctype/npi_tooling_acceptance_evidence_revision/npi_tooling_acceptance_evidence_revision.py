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
from npi_core.tooling.acceptance_domain import (
    acceptance_revision_from_snapshot,
    validate_acceptance_successor,
)
from npi_core.tooling.frappe_validation import (
    deny_tooling_history_delete,
    deny_tooling_history_update,
    require_tooling_command_write,
    tooling_domain_value,
)


class NPIToolingAcceptanceEvidenceRevision(Document):
    """Immutable evidence presence; never a Tooling acceptance decision."""

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
            ("acceptance_global_id", _("Acceptance Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("tooling_master_global_id", _("Tooling Master Global ID")),
            ("tooling_set_global_id", _("Tooling Set Global ID")),
            ("set_revision_binding_global_id", _("Set Revision Binding Global ID")),
            ("tooling_revision_global_id", _("Tooling Revision Global ID")),
            ("request_id", _("Request ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.predecessor_global_id = optional_uuid(
            self.predecessor_global_id,
            _("Predecessor Acceptance Evidence Revision"),
        )
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_tooling_history_update()
        supplied = json_object(
            self.acceptance_snapshot,
            _("Tooling Acceptance Evidence Revision Snapshot"),
        )
        value = tooling_domain_value(lambda: acceptance_revision_from_snapshot(supplied))
        actual = (
            self.global_id,
            self.acceptance_global_id,
            self.tenant_id,
            self.project_global_id,
            self.tooling_master_global_id,
            self.tooling_master_snapshot_hash,
            self.tooling_set_global_id,
            self.tooling_set_snapshot_hash,
            self.tooling_requirement_kind,
            self.set_revision_binding_global_id,
            self.set_revision_binding_snapshot_hash,
            self.tooling_revision_global_id,
            self.tooling_revision_number,
            self.tooling_revision_snapshot_hash,
            self.acceptance_version,
            self.predecessor_global_id,
            self.predecessor_snapshot_hash or None,
            self.request_id,
            self.trace_id,
        )
        expected = (
            str(value.global_id),
            str(value.acceptance_global_id),
            value.tenant_id,
            str(value.project_global_id),
            str(value.tooling_master_global_id),
            value.tooling_master_snapshot_hash,
            str(value.tooling_set_global_id),
            value.tooling_set_snapshot_hash,
            value.tooling_requirement_kind.value,
            str(value.set_revision_binding_global_id),
            value.set_revision_binding_snapshot_hash,
            str(value.tooling_revision_global_id),
            value.tooling_revision_number,
            value.tooling_revision_snapshot_hash,
            value.acceptance_version,
            str(value.predecessor_global_id) if value.predecessor_global_id else None,
            value.predecessor_snapshot_hash,
            str(value.request_id),
            value.trace_id,
        )
        if actual != expected:
            frappe.throw(
                _("Tooling Acceptance Evidence Revision fields do not match the exact snapshot."),
                frappe.ValidationError,
            )
        if self.version_key_hash not in (None, "", value.version_key_hash):
            frappe.throw(_("Acceptance Version Key Hash does not match."), frappe.ValidationError)
        if self.snapshot_hash not in (None, "", value.snapshot_hash):
            frappe.throw(_("Tooling Acceptance Evidence Snapshot Hash does not match."), frappe.ValidationError)
        for supplied_snapshot, expected_snapshot, label in (
            (
                json_array(self.checklist_snapshot, _("Acceptance Checklist Snapshot")),
                [item.snapshot_payload() for item in value.checklist],
                _("Acceptance Checklist Snapshot"),
            ),
            (
                json_array(self.asset_action_snapshot, _("Asset Action Evidence Snapshot")),
                [item.snapshot_payload() for item in value.asset_actions],
                _("Asset Action Evidence Snapshot"),
            ),
            (
                json_array(self.spare_recommendation_snapshot, _("Spare Recommendation Snapshot")),
                [item.snapshot_payload() for item in value.spare_recommendations],
                _("Spare Recommendation Snapshot"),
            ),
            (
                json_array(self.repair_snapshot, _("Repair Evidence Snapshot")),
                [item.snapshot_payload() for item in value.repairs],
                _("Repair Evidence Snapshot"),
            ),
        ):
            if supplied_snapshot != expected_snapshot:
                frappe.throw(
                    _("{field} does not match the exact acceptance evidence.").format(field=label),
                    frappe.ValidationError,
                )
        _require_exact_context(value)
        if value.predecessor_global_id is not None:
            predecessor = require_exact_parent(
                "NPI Tooling Acceptance Evidence Revision",
                str(value.predecessor_global_id),
                {
                    "global_id": str(value.predecessor_global_id),
                    "acceptance_global_id": str(value.acceptance_global_id),
                    "tenant_id": value.tenant_id,
                    "project_global_id": str(value.project_global_id),
                    "tooling_master_global_id": str(value.tooling_master_global_id),
                    "tooling_set_global_id": str(value.tooling_set_global_id),
                    "snapshot_hash": value.predecessor_snapshot_hash,
                },
                _("The predecessor Tooling Acceptance Evidence Revision is unavailable."),
                extra_fields=("acceptance_snapshot",),
            )
            current = tooling_domain_value(
                lambda: acceptance_revision_from_snapshot(
                    json_object(
                        predecessor["acceptance_snapshot"],
                        _("Tooling Acceptance Evidence Revision Snapshot"),
                    )
                )
            )
            tooling_domain_value(lambda: validate_acceptance_successor(current, value))
        _require_members_and_files(value)
        self.tooling_master = str(value.tooling_master_global_id)
        self.tooling_set = str(value.tooling_set_global_id)
        self.set_revision_binding = str(value.set_revision_binding_global_id)
        self.tooling_revision = str(value.tooling_revision_global_id)
        self.version_key_hash = value.version_key_hash
        self.reason = value.reason
        self.created_by_user_id = value.created_by_user_id
        self.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
        self.checklist_snapshot = canonical_json([item.snapshot_payload() for item in value.checklist])
        self.asset_action_snapshot = canonical_json([item.snapshot_payload() for item in value.asset_actions])
        self.spare_recommendation_snapshot = canonical_json(
            [item.snapshot_payload() for item in value.spare_recommendations]
        )
        self.repair_snapshot = canonical_json([item.snapshot_payload() for item in value.repairs])
        self.acceptance_snapshot = canonical_json(value.snapshot_payload())
        self.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))

    def on_trash(self) -> None:
        deny_tooling_history_delete(self)


def _require_exact_context(value) -> None:
    require_exact_parent(
        "NPI Tooling Master",
        str(value.tooling_master_global_id),
        {
            "global_id": str(value.tooling_master_global_id),
            "tenant_id": value.tenant_id,
            "snapshot_hash": value.tooling_master_snapshot_hash,
        },
        _("The exact Tooling Master is unavailable for this acceptance evidence."),
    )
    require_exact_parent(
        "NPI Tooling Set",
        str(value.tooling_set_global_id),
        {
            "global_id": str(value.tooling_set_global_id),
            "tenant_id": value.tenant_id,
            "project_global_id": str(value.project_global_id),
            "tooling_master_global_id": str(value.tooling_master_global_id),
            "requirement_kind": value.tooling_requirement_kind.value,
            "snapshot_hash": value.tooling_set_snapshot_hash,
        },
        _("The exact physical Tooling Set is unavailable for this acceptance evidence."),
    )
    require_exact_parent(
        "NPI Tooling Set Revision Binding",
        str(value.set_revision_binding_global_id),
        {
            "global_id": str(value.set_revision_binding_global_id),
            "tenant_id": value.tenant_id,
            "project_global_id": str(value.project_global_id),
            "tooling_master_global_id": str(value.tooling_master_global_id),
            "tooling_set_global_id": str(value.tooling_set_global_id),
            "tooling_revision_global_id": str(value.tooling_revision_global_id),
            "snapshot_hash": value.set_revision_binding_snapshot_hash,
        },
        _("The exact Tooling Set Revision Binding is unavailable."),
    )
    require_exact_parent(
        "NPI Tooling Revision",
        str(value.tooling_revision_global_id),
        {
            "global_id": str(value.tooling_revision_global_id),
            "tenant_id": value.tenant_id,
            "project_global_id": str(value.project_global_id),
            "tooling_master_global_id": str(value.tooling_master_global_id),
            "revision_number": value.tooling_revision_number,
            "snapshot_hash": value.tooling_revision_snapshot_hash,
        },
        _("The exact Tooling Revision is unavailable for this acceptance evidence."),
    )


def _require_members_and_files(value) -> None:
    members = [
        item.responsible_member for item in value.checklist if item.responsible_member
    ]
    members.extend(repair.responsible_member for repair in value.repairs)
    for member in members:
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
            _("A responsible Project member is unavailable for this acceptance evidence."),
        )
    evidence = [file for item in value.checklist for file in item.evidence]
    evidence.extend(file for item in value.asset_actions for file in item.evidence)
    evidence.extend(
        file
        for repair in value.repairs
        for file in (*repair.customer_authorization_evidence, *repair.verification_evidence)
    )
    for file in evidence:
        require_exact_parent(
            "NPI File Revision",
            str(file.file_revision_global_id),
            {
                "global_id": str(file.file_revision_global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "optimistic_version": file.file_optimistic_version,
                "frappe_content_hash": file.frappe_content_hash,
                "file_name": file.file_name,
                "mime_type": file.mime_type,
                "size_bytes": file.size_bytes,
                "sha256": file.sha256,
                "scan_state": "clean",
                "is_private": 1,
            },
            _("A clean private File Revision is unavailable for this acceptance evidence."),
        )
