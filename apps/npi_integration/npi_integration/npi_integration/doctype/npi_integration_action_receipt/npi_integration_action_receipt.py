from __future__ import annotations

from datetime import datetime

import frappe
from frappe import _

from npi_core.documents.frappe_validation import (
    canonical_json,
    frappe_utc_datetime_text,
    json_object,
    utc_datetime_text,
)
from npi_integration.integration_operations.doctype_base import (
    IntegrationOperationsSupportDocument,
)
from npi_integration.integration_operations.domain import (
    INTEGRATION_OPERATIONS_SCHEMA_VERSION,
    IntegrationActionKind,
    IntegrationActionOutcome,
    IntegrationActionReceipt,
    IntegrationOperationKind,
    IntegrationOperationReference,
    IntegrationOperationsContractError,
    IntegrationViewState,
)


_FIELDS = (
    "global_id",
    "schema_version",
    "tenant_id",
    "project_global_id",
    "operation_kind",
    "operation_global_id",
    "source_global_id",
    "operation_version",
    "raw_state",
    "shared_state",
    "source_snapshot_hash",
    "target_idempotency_key_hash",
    "action_kind",
    "action_idempotency_key_hash",
    "expected_raw_state",
    "expected_version",
    "request_hash",
    "outcome_state",
    "outcome_reference_global_id",
    "response_snapshot",
    "response_hash",
    "receipt_snapshot",
    "receipt_hash",
    "actor_user_id",
    "trace_id",
    "created_at",
)


class NPIIntegrationActionReceipt(IntegrationOperationsSupportDocument):
    immutable_fields = _FIELDS
    uuid_fields = (
        "global_id",
        "project_global_id",
        "operation_global_id",
        "source_global_id",
    )
    optional_uuid_fields = ("outcome_reference_global_id",)
    hash_fields = (
        "source_snapshot_hash",
        "target_idempotency_key_hash",
        "action_idempotency_key_hash",
        "request_hash",
        "response_hash",
        "receipt_hash",
    )
    positive_fields = ("schema_version", "operation_version", "expected_version")
    text_fields = ("raw_state", "expected_raw_state", "trace_id")
    actor_fields = ("actor_user_id",)

    def validate(self) -> None:
        super().validate()
        if self.schema_version != INTEGRATION_OPERATIONS_SCHEMA_VERSION:
            frappe.throw(
                _("The integration action receipt schema version is unsupported."),
                frappe.ValidationError,
            )
        response = json_object(
            self.response_snapshot,
            _("Integration Action Response Snapshot"),
        )
        snapshot = json_object(
            self.receipt_snapshot,
            _("Integration Action Receipt Snapshot"),
        )
        try:
            operation = IntegrationOperationReference(
                tenant_id=self.tenant_id,
                project_global_id=self.project_global_id,
                operation_kind=IntegrationOperationKind(self.operation_kind),
                operation_global_id=self.operation_global_id,
                source_global_id=self.source_global_id,
                operation_version=self.operation_version,
                raw_state=self.raw_state,
                shared_state=IntegrationViewState(self.shared_state),
                source_snapshot_hash=self.source_snapshot_hash,
                target_idempotency_key_hash=self.target_idempotency_key_hash,
            )
            receipt = IntegrationActionReceipt(
                global_id=self.global_id,
                operation=operation,
                action_kind=IntegrationActionKind(self.action_kind),
                action_idempotency_key_hash=self.action_idempotency_key_hash,
                expected_raw_state=self.expected_raw_state,
                expected_version=self.expected_version,
                request_hash=self.request_hash,
                outcome_state=IntegrationActionOutcome(self.outcome_state),
                outcome_reference_global_id=self.outcome_reference_global_id or None,
                response_snapshot=response,
                response_hash=self.response_hash,
                actor_user_id=self.actor_user_id,
                trace_id=self.trace_id,
                created_at=_domain_datetime(
                    self.created_at,
                    _("Integration Action Recorded At"),
                ),
            )
        except (IntegrationOperationsContractError, ValueError) as error:
            frappe.throw(
                _("The integration action receipt is invalid."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.") from error
        if snapshot != receipt.payload() or self.receipt_hash != receipt.receipt_hash:
            frappe.throw(
                _("The integration action receipt hash does not match its fields."),
                frappe.ValidationError,
            )
        self.response_snapshot = canonical_json(response)
        self.receipt_snapshot = canonical_json(snapshot)
        self.created_at = frappe_utc_datetime_text(
            self.created_at,
            _("Integration Action Recorded At"),
        )


def _domain_datetime(value: object, label: str) -> datetime:
    text = utc_datetime_text(value, label)
    return datetime.fromisoformat(text.replace("Z", "+00:00"))
