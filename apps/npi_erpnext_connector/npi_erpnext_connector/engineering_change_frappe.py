from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import frappe

from npi_erpnext_connector.engineering_change_contract import (
    EngineeringChangeSummaryCommand,
)
from npi_erpnext_connector.frappe_validation import (
    engineering_change_execution_write,
    insert_engineering_change_support_document,
)
from npi_erpnext_connector.receiver_security import (
    business_actor_context,
    business_actor_is_enabled,
)

SUMMARY_DOCTYPE = "NPI ERP Change Implementation Summary"
PROJECT_MAPPING_DOCTYPE = "NPI ERP Project Mapping"
FORMAL_CHANGE_DOCTYPE = "Engineering Change Request"
UTC = timezone.utc


class EngineeringChangeExecutionError(ValueError):
    def __init__(self, code: str, http_status: int = 422) -> None:
        super().__init__(code)
        self.code = code
        self.http_status = http_status


@dataclass(frozen=True, slots=True)
class EngineeringChangeExecutionResult:
    projection_id: str
    exact_replay: bool


def execute_summary_command(
    command: EngineeringChangeSummaryCommand,
    *,
    service_user: str,
    trace_id: str,
) -> EngineeringChangeExecutionResult:
    if not business_actor_is_enabled(command.actor_user_id, service_user=service_user):
        raise EngineeringChangeExecutionError(
            "ENGINEERING_CHANGE_BUSINESS_ACTOR_UNAVAILABLE", 403
        )
    savepoint = f"npi_erp_change_{command.target_idempotency_key_hash[:16]}"
    frappe.db.savepoint(savepoint)
    try:
        return _execute(command, service_user=service_user, trace_id=trace_id)
    except EngineeringChangeExecutionError:
        frappe.db.rollback(save_point=savepoint)
        raise
    except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
        frappe.db.rollback(save_point=savepoint)
        return _recover_unique_race(command)


def _execute(
    command: EngineeringChangeSummaryCommand,
    *,
    service_user: str,
    trace_id: str,
) -> EngineeringChangeExecutionResult:
    existing = frappe.db.get_value(
        SUMMARY_DOCTYPE,
        {"target_idempotency_key_hash": command.target_idempotency_key_hash},
        "name",
    )
    if existing:
        summary = frappe.get_doc(SUMMARY_DOCTYPE, existing, for_update=True)
        if any(
            (
                str(summary.revision_global_id) != command.revision_global_id,
                str(summary.request_global_id) != command.request_global_id,
                str(summary.source_hash) != command.source_hash,
                str(summary.semantic_request_hash) != command.semantic_request_hash,
            )
        ):
            raise EngineeringChangeExecutionError(
                "ENGINEERING_CHANGE_SUMMARY_PAYLOAD_CONFLICT", 409
            )
        return EngineeringChangeExecutionResult(command.revision_global_id, True)
    if frappe.db.get_value(
        SUMMARY_DOCTYPE,
        {"revision_global_id": command.revision_global_id},
        "target_idempotency_key_hash",
    ):
        raise EngineeringChangeExecutionError(
            "ENGINEERING_CHANGE_SUMMARY_REVISION_CONFLICT", 409
        )
    if frappe.db.get_value(
        SUMMARY_DOCTYPE,
        {"request_global_id": command.request_global_id},
        "target_idempotency_key_hash",
    ):
        raise EngineeringChangeExecutionError(
            "ENGINEERING_CHANGE_SUMMARY_REQUEST_ID_CONFLICT", 409
        )
    _validate_formal_change(command)
    formal = command.formal_change
    received_at = datetime.now(UTC).replace(tzinfo=None)
    with engineering_change_execution_write(command.request_global_id) as capability:
        document = frappe.get_doc(
            {
                "doctype": SUMMARY_DOCTYPE,
                "owner": command.actor_user_id,
                "revision_global_id": command.revision_global_id,
                "tenant_id": command.tenant_id,
                "project_global_id": command.project_global_id,
                "change_global_id": command.change_global_id,
                "revision_number": command.revision_number,
                "revision_snapshot_hash": command.revision_snapshot_hash,
                "formal_change_document_name": formal["documentName"],
                "formal_change_raw_status": formal["rawStatus"],
                "formal_change_source_version": formal["sourceVersion"],
                "formal_change_source_modified_at": str(
                    formal["sourceModifiedAt"]
                ).removesuffix("Z"),
                "formal_change_source_hash": formal["sourceHash"],
                "formal_change_observed_at": str(formal["observedAt"]).removesuffix(
                    "Z"
                ),
                "affected_versions_hash": command.affected_versions_hash,
                "effectivity_hash": command.effectivity_hash,
                "disposition_hash": command.disposition_hash,
                "revalidation_hash": command.revalidation_hash,
                "closure_evidence_hash": command.closure_evidence_hash,
                "request_global_id": command.request_global_id,
                "target_idempotency_key_hash": command.target_idempotency_key_hash,
                "source_hash": command.source_hash,
                "semantic_request_hash": command.semantic_request_hash,
                "profile_id": command.profile_id,
                "profile_version": command.profile_version,
                "profile_snapshot_hash": command.profile_snapshot_hash,
                "source_actor_user_id": command.actor_user_id,
                "service_user": service_user,
                "trace_id": trace_id,
                "received_at": received_at,
            }
        )
        with business_actor_context(command.actor_user_id):
            insert_engineering_change_support_document(
                document,
                capability=capability,
            )
    return EngineeringChangeExecutionResult(command.revision_global_id, False)


def _validate_formal_change(command: EngineeringChangeSummaryCommand) -> None:
    if not frappe.db.exists("DocType", FORMAL_CHANGE_DOCTYPE):
        raise EngineeringChangeExecutionError(
            "ENGINEERING_CHANGE_FORMAL_DOCTYPE_UNAVAILABLE"
        )
    meta = frappe.get_meta(FORMAL_CHANGE_DOCTYPE)
    if meta.get_field("status") is None or meta.get_field("project") is None:
        raise EngineeringChangeExecutionError(
            "ENGINEERING_CHANGE_FORMAL_MAPPING_UNAVAILABLE"
        )
    document_name = str(command.formal_change["documentName"])
    formal = frappe.db.get_value(
        FORMAL_CHANGE_DOCTYPE,
        document_name,
        ["name", "status", "project"],
        as_dict=True,
    )
    if not formal:
        raise EngineeringChangeExecutionError(
            "ENGINEERING_CHANGE_FORMAL_DOCUMENT_UNAVAILABLE", 409
        )
    if str(formal.get("status") or "") != command.formal_change["rawStatus"]:
        raise EngineeringChangeExecutionError(
            "ENGINEERING_CHANGE_FORMAL_STATUS_CONFLICT", 409
        )
    source_project = frappe.db.get_value(
        PROJECT_MAPPING_DOCTYPE,
        {"target_project_global_id": command.project_global_id},
        "source_project_id",
    )
    if not source_project:
        raise EngineeringChangeExecutionError(
            "ENGINEERING_CHANGE_PROJECT_MAPPING_UNAVAILABLE", 409
        )
    if str(formal.get("project") or "") != str(source_project):
        raise EngineeringChangeExecutionError(
            "ENGINEERING_CHANGE_PROJECT_MAPPING_CONFLICT", 409
        )


def _recover_unique_race(
    command: EngineeringChangeSummaryCommand,
) -> EngineeringChangeExecutionResult:
    name = frappe.db.get_value(
        SUMMARY_DOCTYPE,
        {"target_idempotency_key_hash": command.target_idempotency_key_hash},
        "name",
    )
    if name:
        summary = frappe.get_doc(SUMMARY_DOCTYPE, name, for_update=True)
        if (
            str(summary.revision_global_id) == command.revision_global_id
            and str(summary.request_global_id) == command.request_global_id
            and str(summary.source_hash) == command.source_hash
            and str(summary.semantic_request_hash) == command.semantic_request_hash
        ):
            return EngineeringChangeExecutionResult(command.revision_global_id, True)
    raise EngineeringChangeExecutionError(
        "ENGINEERING_CHANGE_SUMMARY_TARGET_IDENTITY_CONFLICT", 409
    )
