from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    assert_immutable_fields,
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
from npi_integration.tool_asset_request.execution_domain import (
    TOOL_ASSET_EXECUTION_API_VERSION,
    TOOL_ASSET_EXECUTION_OPERATIONS,
    TOOL_ASSET_EXECUTION_SCHEMA_VERSION,
    ToolAssetExecutionContractError,
    canonical_hash,
    tool_asset_execution_request_from_mapping,
)
from npi_integration.tool_asset_request.execution_frappe_validation import (
    deny_tool_asset_execution_history_delete,
    deny_tool_asset_execution_history_update,
    require_tool_asset_execution_capability,
    require_tool_asset_execution_request_write,
)


class NPIToolAssetRequest(Document):
    """Mock-validated draft only; no target dispatch or mapping."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        if self._is_execution_v2():
            require_tool_asset_execution_request_write()
            require_tool_asset_execution_capability("NPI Tool Asset Request", "insert")
        else:
            require_tool_asset_request_write()

    def before_save(self) -> None:
        if self._is_execution_v2():
            require_tool_asset_execution_request_write()
            action = "insert" if getattr(getattr(self, "flags", None), "in_insert", False) else "save"
            require_tool_asset_execution_capability("NPI Tool Asset Request", action)
            return
        require_tool_asset_request_write()
        if self.get_doc_before_save() is not None:
            deny_tool_asset_history_update()

    def before_validate(self) -> None:
        if self._is_execution_v2():
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
            return
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
        if self._is_execution_v2():
            self._validate_execution_v2()
            return
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
        if self._is_execution_v2():
            deny_tool_asset_execution_history_delete()
        else:
            deny_tool_asset_history_delete(self)

    def _is_execution_v2(self) -> bool:
        return int(getattr(self, "schema_version", 0) or 0) == TOOL_ASSET_EXECUTION_SCHEMA_VERSION or getattr(self, "operation", None) in TOOL_ASSET_EXECUTION_OPERATIONS

    def _validate_execution_v2(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _EXECUTION_IMMUTABLE_FIELDS)
            _require_execution_transition(str(previous.execution_state), str(self.execution_state))
        if int(self.schema_version or 0) != TOOL_ASSET_EXECUTION_SCHEMA_VERSION or self.api_version != TOOL_ASSET_EXECUTION_API_VERSION or self.operation not in TOOL_ASSET_EXECUTION_OPERATIONS:
            frappe.throw(_("The Tool Asset execution request version or operation is invalid."), frappe.ValidationError)
        source = json_object(self.source_snapshot, _("Exact Tool Asset Source Snapshot"))
        approval = json_object(self.approval_snapshot, _("Tool Asset Business Approval Snapshot"))
        expectation = json_object(self.mapping_expectation_snapshot, _("Tool Asset Mapping Expectation Snapshot"))
        request = json_object(self.request_snapshot, _("Tool Asset Request Snapshot"))
        try:
            rebuilt = tool_asset_execution_request_from_mapping(request)
        except ToolAssetExecutionContractError:
            frappe.throw(_("Tool Asset execution request fields do not match the exact snapshot."), frappe.ValidationError)
        if rebuilt.canonical_mapping() != request:
            frappe.throw(_("Tool Asset execution request fields do not match the exact snapshot."), frappe.ValidationError)
        for supplied, expected, label in (
            (self.source_hash, canonical_hash(source), _("Tool Asset Source Hash")),
            (self.approval_hash, canonical_hash(approval), _("Tool Asset Business Approval Hash")),
            (self.mapping_expectation_hash, canonical_hash(expectation), _("Tool Asset Mapping Expectation Hash")),
            (self.payload_hash, request.get("payloadHash"), _("Tool Asset Request Payload Hash")),
        ):
            if lowercase_sha256(supplied, label) != expected:
                frappe.throw(_("{field} does not match.").format(field=label), frappe.ValidationError)
        exact = {
            "schemaVersion": TOOL_ASSET_EXECUTION_SCHEMA_VERSION,
            "apiVersion": TOOL_ASSET_EXECUTION_API_VERSION,
            "globalId": self.global_id,
            "operation": self.operation,
            "tenantId": self.tenant_id,
            "projectGlobalId": self.project_global_id,
            "state": request.get("state"),
            "actorUserId": self.actor_user_id,
            "requestId": self.request_id,
            "traceId": self.trace_id,
            "idempotencyKeyHash": self.idempotency_key_hash,
            "payloadHash": self.payload_hash,
            "optimisticVersion": int(self.optimistic_version or 0),
        }
        if any(request.get(name) != value for name, value in exact.items()) or request.get("source") != source or request.get("approval") != approval or request.get("mappingExpectation") != expectation:
            frappe.throw(_("Tool Asset execution request fields do not match the exact snapshot."), frappe.ValidationError)
        if source.get("sourceStreamKeyHash") != self.source_stream_key_hash or source.get("sourceHash") != self.source_hash or source.get("toolingSetGlobalId") != self.tooling_set_global_id:
            frappe.throw(_("Tool Asset execution source fields do not match the exact physical Set."), frappe.ValidationError)
        if expectation.get("operation") != self.operation or expectation.get("sourceStreamKeyHash") != self.source_stream_key_hash:
            frappe.throw(_("Tool Asset mapping expectation does not match the exact operation."), frappe.ValidationError)
        profile = request.get("profile")
        if not isinstance(profile, dict) or (
            profile.get("profileId"), profile.get("profileVersion"), profile.get("targetMode"), profile.get("environmentCode"), profile.get("projectionPolicyId"), profile.get("projectionPolicyVersion"), profile.get("projectionPolicyHash"), profile.get("snapshotHash")
        ) != (
            self.profile_id, int(self.profile_version or 0), self.execution_target_mode, self.environment_code, self.projection_policy_id, int(self.projection_policy_version or 0), self.projection_policy_hash, self.profile_snapshot_hash
        ):
            frappe.throw(_("Tool Asset execution profile fields do not match the exact snapshot."), frappe.ValidationError)
        if self.execution_target_mode == "mock" and (bool(self.dispatch_allowed) or self.outbox_event_id or self.result_global_id or self.execution_state != "validated_mock"):
            frappe.throw(_("Mock Tool Asset execution must remain undispatched and non-authoritative."), frappe.ValidationError)
        self.source_snapshot = canonical_json(source)
        self.approval_snapshot = canonical_json(approval)
        self.mapping_expectation_snapshot = canonical_json(expectation)
        self.request_snapshot = canonical_json(request)


_EXECUTION_IMMUTABLE_FIELDS = (
    "global_id", "tenant_id", "project_global_id", "tooling_master_global_id",
    "tooling_set_global_id", "tooling_revision_global_id",
    "acceptance_revision_global_id", "schema_version", "api_version", "operation",
    "source_stream_key_hash", "source_snapshot", "source_hash", "approval_snapshot",
    "approval_hash", "mapping_expectation_snapshot", "mapping_expectation_hash",
    "profile_id", "profile_version", "execution_target_mode", "environment_code",
    "profile_snapshot_hash", "projection_policy_id", "projection_policy_version",
    "projection_policy_hash", "dispatch_allowed", "outbox_event_id",
    "target_idempotency_key_hash", "semantic_effect_hash", "payload_hash",
    "request_snapshot", "actor_user_id", "request_id", "trace_id",
    "idempotency_key_hash", "created_at",
)

_EXECUTION_TRANSITIONS = {
    "queued": frozenset({"queued", "processing", "failed_final"}),
    "processing": frozenset({
        "processing", "synthetic_verified", "partially_succeeded", "succeeded",
        "failed_retryable", "failed_final", "uncertain_after_timeout", "mapping_conflict",
    }),
}


def _require_execution_transition(previous: str, current: str) -> None:
    if current not in _EXECUTION_TRANSITIONS.get(previous, frozenset({previous})):
        frappe.throw(_("The Tool Asset execution request state transition is invalid."), frappe.ValidationError)


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
