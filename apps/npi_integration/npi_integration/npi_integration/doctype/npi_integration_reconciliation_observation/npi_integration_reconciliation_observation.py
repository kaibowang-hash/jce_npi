from __future__ import annotations

from datetime import datetime

import frappe
from frappe import _

from npi_core.documents.frappe_validation import (
    canonical_json,
    frappe_utc_datetime_text,
    json_object,
    require_exact_parent,
    utc_datetime_text,
)
from npi_integration.integration_operations.doctype_base import (
    IntegrationOperationsSupportDocument,
)
from npi_integration.integration_operations.domain import (
    INTEGRATION_OPERATIONS_SCHEMA_VERSION,
    IntegrationOperationKind,
    IntegrationOperationReference,
    IntegrationOperationsContractError,
    IntegrationReconciliationObservation,
    IntegrationViewState,
    ReconciliationAuthority,
    ReconciliationObservationState,
    ReconciliationObserverKind,
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
    "action_receipt_global_id",
    "attempt_global_id",
    "reconciliation_state",
    "observer_kind",
    "authority",
    "response_authenticated",
    "profile_id",
    "profile_version",
    "adapter_code",
    "evidence_snapshot",
    "evidence_hash",
    "observer_id",
    "trace_id",
    "observed_at",
    "observation_snapshot",
    "observation_hash",
)


class NPIIntegrationReconciliationObservation(IntegrationOperationsSupportDocument):
    immutable_fields = _FIELDS
    uuid_fields = (
        "global_id",
        "project_global_id",
        "operation_global_id",
        "source_global_id",
        "action_receipt_global_id",
    )
    optional_uuid_fields = ("attempt_global_id",)
    hash_fields = (
        "source_snapshot_hash",
        "target_idempotency_key_hash",
        "evidence_hash",
        "observation_hash",
    )
    positive_fields = ("schema_version", "operation_version", "profile_version")
    text_fields = ("raw_state", "profile_id", "adapter_code", "trace_id")
    actor_fields = ("observer_id",)

    def validate(self) -> None:
        super().validate()
        if self.schema_version != INTEGRATION_OPERATIONS_SCHEMA_VERSION:
            frappe.throw(
                _(
                    "The integration reconciliation observation schema version is unsupported."
                ),
                frappe.ValidationError,
            )
        evidence = json_object(
            self.evidence_snapshot,
            _("Integration Reconciliation Evidence Snapshot"),
        )
        snapshot = json_object(
            self.observation_snapshot,
            _("Integration Reconciliation Observation Snapshot"),
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
            observation = IntegrationReconciliationObservation(
                global_id=self.global_id,
                operation=operation,
                action_receipt_global_id=self.action_receipt_global_id,
                attempt_global_id=self.attempt_global_id or None,
                state=ReconciliationObservationState(self.reconciliation_state),
                observer_kind=ReconciliationObserverKind(self.observer_kind),
                authority=ReconciliationAuthority(self.authority),
                response_authenticated=bool(self.response_authenticated),
                profile_id=self.profile_id,
                profile_version=self.profile_version,
                adapter_code=self.adapter_code,
                evidence_snapshot=evidence,
                evidence_hash=self.evidence_hash,
                observer_id=self.observer_id,
                trace_id=self.trace_id,
                observed_at=_domain_datetime(
                    self.observed_at,
                    _("Integration Reconciliation Observed At"),
                ),
            )
        except (IntegrationOperationsContractError, ValueError) as error:
            frappe.throw(
                _("The integration reconciliation observation is invalid."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.") from error
        if (
            snapshot != observation.payload()
            or self.observation_hash != observation.observation_hash
        ):
            frappe.throw(
                _(
                    "The integration reconciliation observation hash does not match its fields."
                ),
                frappe.ValidationError,
            )
        require_exact_parent(
            "NPI Integration Action Receipt",
            self.action_receipt_global_id,
            {
                "global_id": self.action_receipt_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "operation_kind": self.operation_kind,
                "operation_global_id": self.operation_global_id,
                "source_global_id": self.source_global_id,
                "action_kind": "request_reconciliation",
                "outcome_state": "reconciliation_requested",
            },
            _(
                "The reconciliation observation does not match its exact action receipt."
            ),
        )
        self.evidence_snapshot = canonical_json(evidence)
        self.observation_snapshot = canonical_json(snapshot)
        self.observed_at = frappe_utc_datetime_text(
            self.observed_at,
            _("Integration Reconciliation Observed At"),
        )


def _domain_datetime(value: object, label: str) -> datetime:
    text = utc_datetime_text(value, label)
    return datetime.fromisoformat(text.replace("Z", "+00:00"))
