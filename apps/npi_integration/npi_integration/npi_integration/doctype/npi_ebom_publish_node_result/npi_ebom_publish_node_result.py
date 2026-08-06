from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    canonical_json,
    canonical_uuid,
    json_object,
    lowercase_sha256,
    nonnegative_integer,
    require_exact_parent,
    tenant_text,
    utc_datetime_text,
)
from npi_integration.publish_request.domain import sha256_json
from npi_integration.publish_request.frappe_validation import (
    deny_publish_history_delete,
    deny_publish_history_update,
    require_publish_request_write,
)


class NPIEBOMPublishNodeResult(Document):
    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_publish_request_write()

    def before_save(self) -> None:
        require_publish_request_write()
        if self.get_doc_before_save() is not None:
            deny_publish_history_update()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("publish_request", _("EBOM Publish Request")),
            ("request_global_id", _("Publish Request Global ID")),
            ("publish_node", _("EBOM Publish Node")),
            ("node_global_id", _("Publish Node Global ID")),
            ("project_global_id", _("Project Global ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_publish_history_update()
        if self.publish_request != self.request_global_id or self.publish_node != self.node_global_id:
            frappe.throw(
                _("The node result must match its exact request and node identities."),
                frappe.ValidationError,
            )
        require_exact_parent(
            "NPI EBOM Publish Request",
            self.publish_request,
            {
                "global_id": self.request_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "target_mode": "mock",
                "dispatch_allowed": 0,
            },
            _("The exact EBOM publish request is unavailable."),
        )
        node = require_exact_parent(
            "NPI EBOM Publish Node",
            self.publish_node,
            {
                "global_id": self.node_global_id,
                "request_global_id": self.request_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
            },
            _("The exact EBOM publish node is unavailable."),
            extra_fields=("result_state", "input_hash"),
        )
        self.attempt_number = nonnegative_integer(
            self.attempt_number, _("Attempt Number")
        )
        if self.attempt_number != 0 or self.state not in {"validated", "blocked_mapping"}:
            frappe.throw(
                _("Phase 5 node results can record Mock validation only."),
                frappe.ValidationError,
            )
        expected_fault = None if self.state == "validated" else "stale_mapping"
        expected_directive = "none" if self.state == "validated" else "resolve_mapping"
        if (
            self.state != str(node.result_state)
            or (self.fault_kind or None) != expected_fault
            or self.future_retry_directive != expected_directive
            or self.future_retryable
            or bool(self.reconciliation_required) != (self.state == "blocked_mapping")
            or self.retry_after_required
            or self.phase5_dispatch_allowed
            or self.formal_item_code
            or self.formal_mbom_id
            or self.target_version
        ):
            frappe.throw(
                _("The Mock node result contains unsupported execution truth."),
                frappe.ValidationError,
            )
        occurred_at = utc_datetime_text(self.occurred_at, _("Occurred At"))
        snapshot = json_object(self.result_snapshot, _("Node Result Snapshot"))
        expected = {
            "schemaVersion": 1,
            "globalId": self.global_id,
            "requestGlobalId": self.request_global_id,
            "nodeGlobalId": self.node_global_id,
            "nodeInputHash": str(node.input_hash),
            "attemptNumber": 0,
            "state": self.state,
            "faultKind": expected_fault,
            "futureRetryDirective": expected_directive,
            "futureRetryable": False,
            "reconciliationRequired": self.state == "blocked_mapping",
            "retryAfterRequired": False,
            "phase5DispatchAllowed": False,
            "formalItemCode": None,
            "formalMbomId": None,
            "targetVersion": None,
            "occurredAt": occurred_at,
        }
        if snapshot != expected:
            frappe.throw(
                _("The node result snapshot does not match its fields."),
                frappe.ValidationError,
            )
        self.result_snapshot = canonical_json(expected)
        if lowercase_sha256(
            self.result_hash, _("Node Result Hash")
        ) != sha256_json(expected):
            frappe.throw(
                _("The node result hash does not match its exact content."),
                frappe.ValidationError,
            )

    def on_trash(self) -> None:
        deny_publish_history_delete(self, target_global_id=self.global_id)
