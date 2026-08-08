from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    canonical_json,
    canonical_uuid,
    frappe_utc_datetime_text,
    json_object,
    lowercase_sha256,
    require_exact_parent,
    tenant_text,
)
from npi_core.tooling.frappe_validation import tooling_domain_value
from npi_integration.tool_asset_request.domain import tool_asset_request_from_snapshot
from npi_integration.tool_asset_request.frappe_validation import (
    deny_tool_asset_history_delete,
    deny_tool_asset_history_update,
    require_tool_asset_request_write,
)


class NPIToolAssetRequest(Document):
    """Mock-validated draft only; no target dispatch or mapping."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_tool_asset_request_write()

    def before_save(self) -> None:
        require_tool_asset_request_write()
        if self.get_doc_before_save() is not None:
            deny_tool_asset_history_update()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("tooling_master_global_id", _("Tooling Master Global ID")),
            ("tooling_set_global_id", _("Tooling Set Global ID")),
            ("tooling_revision_global_id", _("Tooling Revision Global ID")),
            ("acceptance_revision_global_id", _("Acceptance Evidence Revision Global ID")),
            ("request_id", _("Request ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_tool_asset_history_update()
        supplied = json_object(self.request_snapshot, _("Tool Asset Request Snapshot"))
        value = tooling_domain_value(lambda: tool_asset_request_from_snapshot(supplied))
        request_input = value.request_input
        actual = (
            self.global_id,
            self.tenant_id,
            self.project_global_id,
            self.tooling_master_global_id,
            self.tooling_set_global_id,
            self.tooling_revision_global_id,
            self.acceptance_revision_global_id,
            self.target_mode,
            self.api_version,
            self.operation,
            self.request_state,
            self.input_validation_state,
            self.business_approval_state,
            self.dispatch_state,
            self.target_result_state,
            self.actor_user_id,
            self.request_id,
            self.trace_id,
            self.idempotency_key_hash,
        )
        expected = (
            str(value.global_id),
            value.tenant_id,
            str(request_input.project_global_id),
            str(request_input.tooling_master_global_id),
            str(request_input.tooling_set_global_id),
            str(request_input.tooling_revision_global_id),
            str(request_input.acceptance_revision_global_id),
            value.target_mode.value,
            value.api_version,
            value.operation,
            value.request_state.value,
            value.input_validation_state.value,
            value.business_approval_state.value,
            value.dispatch_state.value,
            value.target_result_state.value,
            value.actor_user_id,
            str(value.request_id),
            value.trace_id,
            value.idempotency_key_hash,
        )
        if actual != expected:
            frappe.throw(
                _("Tool Asset Request fields do not match the exact snapshot."),
                frappe.ValidationError,
            )
        if json_object(self.request_input_snapshot, _("Tool Asset Request Input Snapshot")) != request_input.snapshot_payload():
            frappe.throw(_("Tool Asset Request Input Snapshot does not match."), frappe.ValidationError)
        for supplied_hash, expected_hash, label in (
            (self.request_input_hash, request_input.snapshot_hash, _("Tool Asset Request Input Hash")),
            (self.payload_hash, value.payload_hash, _("Tool Asset Request Payload Hash")),
            (self.snapshot_hash, value.snapshot_hash, _("Snapshot Hash")),
        ):
            if supplied_hash not in (None, "", expected_hash):
                frappe.throw(_("{field} does not match.").format(field=label), frappe.ValidationError)
        _require_exact_input(value)
        self.tooling_master = str(request_input.tooling_master_global_id)
        self.tooling_set = str(request_input.tooling_set_global_id)
        self.tooling_revision = str(request_input.tooling_revision_global_id)
        self.acceptance_revision = str(request_input.acceptance_revision_global_id)
        self.request_input_snapshot = canonical_json(request_input.snapshot_payload())
        self.request_input_hash = lowercase_sha256(request_input.snapshot_hash, _("Tool Asset Request Input Hash"))
        self.payload_hash = lowercase_sha256(value.payload_hash, _("Tool Asset Request Payload Hash"))
        self.request_snapshot = canonical_json(value.snapshot_payload())
        self.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))
        self.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))

    def on_trash(self) -> None:
        deny_tool_asset_history_delete(self)


def _require_exact_input(value) -> None:
    item = value.request_input
    require_exact_parent(
        "NPI Tooling Master",
        str(item.tooling_master_global_id),
        {
            "global_id": str(item.tooling_master_global_id),
            "tenant_id": value.tenant_id,
            "title": item.tooling_master_title,
            "snapshot_hash": item.tooling_master_snapshot_hash,
        },
        _("The exact Tooling Master is unavailable for this Asset request."),
    )
    require_exact_parent(
        "NPI Tooling Set",
        str(item.tooling_set_global_id),
        {
            "global_id": str(item.tooling_set_global_id),
            "tenant_id": value.tenant_id,
            "project_global_id": str(item.project_global_id),
            "tooling_master_global_id": str(item.tooling_master_global_id),
            "physical_serial": item.tooling_set_physical_serial,
            "requirement_kind": item.tooling_requirement_kind.value,
            "snapshot_hash": item.tooling_set_snapshot_hash,
        },
        _("The exact physical Tooling Set is unavailable for this Asset request."),
    )
    require_exact_parent(
        "NPI Tooling Set Revision Binding",
        str(item.set_revision_binding_global_id),
        {
            "global_id": str(item.set_revision_binding_global_id),
            "tenant_id": value.tenant_id,
            "project_global_id": str(item.project_global_id),
            "tooling_master_global_id": str(item.tooling_master_global_id),
            "tooling_set_global_id": str(item.tooling_set_global_id),
            "tooling_revision_global_id": str(item.tooling_revision_global_id),
            "snapshot_hash": item.set_revision_binding_snapshot_hash,
        },
        _("The exact Tooling Set Revision Binding is unavailable for this Asset request."),
    )
    require_exact_parent(
        "NPI Tooling Revision",
        str(item.tooling_revision_global_id),
        {
            "global_id": str(item.tooling_revision_global_id),
            "tenant_id": value.tenant_id,
            "project_global_id": str(item.project_global_id),
            "tooling_master_global_id": str(item.tooling_master_global_id),
            "revision_number": item.tooling_revision_number,
            "revision_label": item.tooling_revision_label,
            "snapshot_hash": item.tooling_revision_snapshot_hash,
        },
        _("The exact Tooling Revision is unavailable for this Asset request."),
    )
    require_exact_parent(
        "NPI Tooling Acceptance Evidence Revision",
        str(item.acceptance_revision_global_id),
        {
            "global_id": str(item.acceptance_revision_global_id),
            "tenant_id": value.tenant_id,
            "project_global_id": str(item.project_global_id),
            "tooling_master_global_id": str(item.tooling_master_global_id),
            "tooling_set_global_id": str(item.tooling_set_global_id),
            "tooling_revision_global_id": str(item.tooling_revision_global_id),
            "acceptance_version": item.acceptance_version,
            "snapshot_hash": item.acceptance_snapshot_hash,
        },
        _("The exact Tooling Acceptance Evidence Revision is unavailable for this Asset request."),
    )
