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
from npi_core.tooling.frappe_validation import (
    deny_tooling_history_delete,
    deny_tooling_history_update,
    require_tooling_command_write,
    tooling_domain_value,
)
from npi_core.tooling.revision_domain import process_chain_revision_from_snapshot


class NPIToolingProcessChainRevision(Document):
    """Immutable ordered parent, second-shot and overmold structure."""

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
            ("process_chain_global_id", _("Process Chain Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("request_id", _("Request ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.predecessor_global_id = optional_uuid(
            self.predecessor_global_id,
            _("Predecessor Process Chain Global ID"),
        )
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_tooling_history_update()
        supplied = json_object(self.chain_snapshot, _("Process Chain Revision Snapshot"))
        value = tooling_domain_value(lambda: process_chain_revision_from_snapshot(supplied))
        expected = (
            str(value.global_id), str(value.process_chain_global_id), value.tenant_id,
            str(value.project_global_id), value.chain_version,
            str(value.predecessor_global_id) if value.predecessor_global_id else None,
            value.predecessor_snapshot_hash, str(value.request_id), value.trace_id,
        )
        actual = (
            self.global_id, self.process_chain_global_id, self.tenant_id,
            self.project_global_id, self.chain_version, self.predecessor_global_id,
            self.predecessor_snapshot_hash or None, self.request_id, self.trace_id,
        )
        if actual != expected:
            frappe.throw(_("Process Chain Revision fields do not match the exact snapshot."), frappe.ValidationError)
        if self.version_key_hash not in (None, "", value.version_key_hash):
            frappe.throw(_("Process Chain Version Key Hash does not match."), frappe.ValidationError)
        if self.snapshot_hash not in (None, "", value.snapshot_hash):
            frappe.throw(_("Process Chain Revision Snapshot Hash does not match."), frappe.ValidationError)
        if json_array(self.step_snapshot, _("Process Step Snapshot")) != [
            item.snapshot_payload() for item in value.steps
        ]:
            frappe.throw(_("Process Step Snapshot does not match."), frappe.ValidationError)
        if value.predecessor_global_id is not None:
            require_exact_parent(
                "NPI Tooling Process Chain Revision",
                str(value.predecessor_global_id),
                {
                    "global_id": str(value.predecessor_global_id),
                    "process_chain_global_id": str(value.process_chain_global_id),
                    "tenant_id": value.tenant_id,
                    "project_global_id": str(value.project_global_id),
                    "snapshot_hash": value.predecessor_snapshot_hash,
                },
                _("The predecessor Process Chain Revision is unavailable."),
            )
        revision_refs = {
            (step.tooling_revision_global_id, step.tooling_revision_snapshot_hash)
            for step in value.steps
        }
        for revision_global_id, revision_snapshot_hash in revision_refs:
            require_exact_parent(
                "NPI Tooling Revision",
                str(revision_global_id),
                {
                    "global_id": str(revision_global_id),
                    "tenant_id": value.tenant_id,
                    "project_global_id": str(value.project_global_id),
                    "snapshot_hash": revision_snapshot_hash,
                },
                _("A Tooling Revision is unavailable for this process chain."),
            )
        part_revision_ids = {
            part_revision_id
            for step in value.steps
            for part_revision_id in (
                *step.input_part_revision_global_ids,
                step.output_part_revision_global_id,
            )
        }
        for part_revision_id in part_revision_ids:
            require_exact_parent(
                "NPI Engineering Part Revision",
                str(part_revision_id),
                {
                    "global_id": str(part_revision_id),
                    "tenant_id": value.tenant_id,
                    "originating_project_global_id": str(value.project_global_id),
                },
                _("A Part Revision is unavailable for this process chain."),
            )
        self.version_key_hash = value.version_key_hash
        self.reason = value.reason
        self.created_by_user_id = value.created_by_user_id
        self.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
        self.step_snapshot = canonical_json([item.snapshot_payload() for item in value.steps])
        self.chain_snapshot = canonical_json(value.snapshot_payload())
        self.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))

    def on_trash(self) -> None:
        deny_tooling_history_delete(self)
