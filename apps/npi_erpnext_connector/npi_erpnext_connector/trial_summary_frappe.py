from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import frappe

from npi_erpnext_connector.frappe_validation import (
    insert_trial_summary_support_document,
    trial_summary_execution_write,
)
from npi_erpnext_connector.trial_summary_contract import (
    TrialSummaryCommand,
    canonical_hash,
    canonical_json,
)

SUMMARY_DOCTYPE = "NPI ERP Trial Summary"
FACT_DOCTYPE = "NPI ERP Trial Summary Fact"
UTC = timezone.utc


class TrialSummaryExecutionError(ValueError):
    def __init__(self, code: str, http_status: int = 422) -> None:
        super().__init__(code)
        self.code = code
        self.http_status = http_status


@dataclass(frozen=True, slots=True)
class TrialSummaryExecutionResult:
    projection_id: str
    fact_count: int
    exact_replay: bool


def execute_trial_summary_command(
    command: TrialSummaryCommand,
    *,
    service_user: str,
    trace_id: str,
) -> TrialSummaryExecutionResult:
    savepoint = f"npi_erp_trial_summary_{command.target_idempotency_key_hash[:16]}"
    frappe.db.savepoint(savepoint)
    try:
        return _execute(command, service_user=service_user, trace_id=trace_id)
    except TrialSummaryExecutionError:
        frappe.db.rollback(save_point=savepoint)
        raise
    except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
        frappe.db.rollback(save_point=savepoint)
        return _recover_unique_race(command)


def receipt_for(
    target_idempotency_key_hash: str,
    source_hash: str,
) -> TrialSummaryExecutionResult | None:
    name = frappe.db.get_value(
        SUMMARY_DOCTYPE,
        {"target_idempotency_key_hash": target_idempotency_key_hash},
        "name",
    )
    if not name:
        return None
    summary = frappe.get_doc(SUMMARY_DOCTYPE, name)
    if str(summary.source_hash) != source_hash:
        raise TrialSummaryExecutionError("TRIAL_SUMMARY_PAYLOAD_CONFLICT", 409)
    return TrialSummaryExecutionResult(
        str(summary.summary_revision_global_id),
        int(summary.fact_count),
        True,
    )


def _execute(
    command: TrialSummaryCommand,
    *,
    service_user: str,
    trace_id: str,
) -> TrialSummaryExecutionResult:
    existing = frappe.db.get_value(
        SUMMARY_DOCTYPE,
        {"target_idempotency_key_hash": command.target_idempotency_key_hash},
        "name",
    )
    if existing:
        summary = frappe.get_doc(SUMMARY_DOCTYPE, existing, for_update=True)
        if any(
            (
                str(summary.summary_revision_global_id)
                != command.summary_revision_global_id,
                str(summary.request_global_id) != command.request_global_id,
                str(summary.source_hash) != command.source_hash,
                str(summary.semantic_request_hash) != command.semantic_request_hash,
            )
        ):
            raise TrialSummaryExecutionError("TRIAL_SUMMARY_PAYLOAD_CONFLICT", 409)
        return TrialSummaryExecutionResult(
            command.summary_revision_global_id,
            int(summary.fact_count),
            True,
        )
    duplicate_revision = frappe.db.get_value(
        SUMMARY_DOCTYPE,
        {"summary_revision_global_id": command.summary_revision_global_id},
        "target_idempotency_key_hash",
    )
    if duplicate_revision:
        raise TrialSummaryExecutionError("TRIAL_SUMMARY_REVISION_CONFLICT", 409)
    duplicate_request = frappe.db.get_value(
        SUMMARY_DOCTYPE,
        {"request_global_id": command.request_global_id},
        "target_idempotency_key_hash",
    )
    if duplicate_request:
        raise TrialSummaryExecutionError("TRIAL_SUMMARY_REQUEST_ID_CONFLICT", 409)

    received_at = datetime.now(UTC).replace(tzinfo=None)
    with trial_summary_execution_write(command.request_global_id) as capability:
        summary = frappe.get_doc(
            {
                "doctype": SUMMARY_DOCTYPE,
                "summary_revision_global_id": command.summary_revision_global_id,
                "summary_global_id": command.summary_global_id,
                "tenant_id": command.tenant_id,
                "project_global_id": command.project_global_id,
                "trial_plan_global_id": command.trial_plan_global_id,
                "trial_round_global_id": command.trial_round_global_id,
                "summary_version": command.summary_version,
                "predecessor_global_id": command.predecessor_global_id,
                "projection_purpose": command.projection_purpose,
                "formal_mp_acceptance": int(command.formal_mp_acceptance),
                "conclusion_state": command.conclusion_state,
                "conclusion_code": command.conclusion_code,
                "source_snapshot_hash": command.source_snapshot_hash,
                "source_manifest_hash": command.source_manifest_hash,
                "presentation_projection_hash": command.presentation_projection_hash,
                "redaction_manifest_hash": command.redaction_manifest_hash,
                "presentation_projection": canonical_json(
                    command.presentation_projection
                ),
                "redaction_manifest": canonical_json(command.redaction_manifest),
                "fact_count": len(command.facts),
                "request_global_id": command.request_global_id,
                "target_idempotency_key_hash": command.target_idempotency_key_hash,
                "source_hash": command.source_hash,
                "semantic_request_hash": command.semantic_request_hash,
                "source_actor_user_id": command.created_by_user_id,
                "source_created_at": command.created_at.removesuffix("Z"),
                "service_user": service_user,
                "trace_id": trace_id,
                "received_at": received_at,
            }
        )
        insert_trial_summary_support_document(summary, capability=capability)
        for fact in command.facts:
            references = list(fact.source_references)
            identity = canonical_hash(
                {
                    "summaryRevisionGlobalId": command.summary_revision_global_id,
                    "factGroup": fact.group,
                    "factKey": fact.fact_key,
                }
            )
            fact_document = frappe.get_doc(
                {
                    "doctype": FACT_DOCTYPE,
                    "fact_global_id": identity,
                    "trial_summary": command.summary_revision_global_id,
                    "summary_revision_global_id": command.summary_revision_global_id,
                    "project_global_id": command.project_global_id,
                    "trial_round_global_id": command.trial_round_global_id,
                    "fact_group": fact.group,
                    "fact_type": fact.fact_type,
                    "fact_key": fact.fact_key,
                    "value_state": fact.value_state,
                    "value_text": _value_text(fact.value),
                    "value_json": canonical_json(fact.value),
                    "unit": fact.unit,
                    "source_references": canonical_json(references),
                    "source_references_hash": canonical_hash(references),
                    "request_global_id": command.request_global_id,
                }
            )
            insert_trial_summary_support_document(
                fact_document,
                capability=capability,
            )
    return TrialSummaryExecutionResult(
        command.summary_revision_global_id,
        len(command.facts),
        False,
    )


def _recover_unique_race(command: TrialSummaryCommand) -> TrialSummaryExecutionResult:
    result = receipt_for(command.target_idempotency_key_hash, command.source_hash)
    if result is not None:
        summary = frappe.get_doc(SUMMARY_DOCTYPE, result.projection_id)
        if (
            str(summary.request_global_id) == command.request_global_id
            and str(summary.semantic_request_hash) == command.semantic_request_hash
        ):
            return result
        raise TrialSummaryExecutionError("TRIAL_SUMMARY_PAYLOAD_CONFLICT", 409)
    raise TrialSummaryExecutionError("TRIAL_SUMMARY_TARGET_IDENTITY_CONFLICT", 409)


def _value_text(value: str | int | float | bool | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
