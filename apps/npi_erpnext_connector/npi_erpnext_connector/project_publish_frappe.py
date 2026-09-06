from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import frappe

from .project_publish_config import ProjectReceiverProfile
from .project_publish_contract import ProjectPublishCommand, canonical_hash, canonical_json
from .project_publish_validation import insert_support, insert_target, project_publish_execution_write
from .receiver_security import business_actor_context, business_actor_is_enabled


MAPPING_DOCTYPE = "NPI ERP Project Publish Mapping"
RECEIPT_DOCTYPE = "NPI ERP Project Publish Receipt"
UTC = timezone.utc


class ProjectPublishExecutionError(ValueError):
    def __init__(self, code: str, http_status: int = 422) -> None:
        super().__init__(code)
        self.code = code
        self.http_status = http_status


@dataclass(frozen=True, slots=True)
class ProjectPublishExecutionResult:
    formal_project_id: str
    target_version: str
    exact_replay: bool


def execute_project_command(command: ProjectPublishCommand, profile: ProjectReceiverProfile, *, service_user: str, trace_id: str) -> ProjectPublishExecutionResult:
    if not business_actor_is_enabled(command.actor_user_id, service_user=service_user):
        raise ProjectPublishExecutionError("PROJECT_PUBLISH_BUSINESS_ACTOR_UNAVAILABLE", 403)
    savepoint = f"npi_erp_project_publish_{command.target_idempotency_key_hash[:16]}"
    frappe.db.savepoint(savepoint)
    try:
        return _execute(command, profile, service_user=service_user, trace_id=trace_id)
    except ProjectPublishExecutionError:
        frappe.db.rollback(save_point=savepoint)
        raise
    except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
        frappe.db.rollback(save_point=savepoint)
        result = receipt_for(command.target_idempotency_key_hash, command.source_hash)
        if result is not None:
            return result
        raise ProjectPublishExecutionError("PROJECT_PUBLISH_TARGET_IDENTITY_CONFLICT", 409)


def receipt_for(target_idempotency_key_hash: str, source_hash: str) -> ProjectPublishExecutionResult | None:
    name = frappe.db.get_value(RECEIPT_DOCTYPE, target_idempotency_key_hash, "name")
    if not name:
        return None
    receipt = frappe.get_doc(RECEIPT_DOCTYPE, name)
    if str(receipt.source_hash) != source_hash:
        raise ProjectPublishExecutionError("PROJECT_PUBLISH_PAYLOAD_CONFLICT", 409)
    return ProjectPublishExecutionResult(str(receipt.formal_project_id), str(receipt.target_version), True)


def _execute(command: ProjectPublishCommand, profile: ProjectReceiverProfile, *, service_user: str, trace_id: str) -> ProjectPublishExecutionResult:
    existing = frappe.db.get_value(RECEIPT_DOCTYPE, command.target_idempotency_key_hash, "name")
    if existing:
        receipt = frappe.get_doc(RECEIPT_DOCTYPE, existing, for_update=True)
        if str(receipt.request_global_id) != command.request_global_id or str(receipt.semantic_request_hash) != command.semantic_request_hash or str(receipt.source_hash) != command.source_hash:
            raise ProjectPublishExecutionError("PROJECT_PUBLISH_PAYLOAD_CONFLICT", 409)
        return ProjectPublishExecutionResult(str(receipt.formal_project_id), str(receipt.target_version), True)
    duplicate_project = frappe.db.get_value(MAPPING_DOCTYPE, command.project_global_id, "name")
    if duplicate_project:
        raise ProjectPublishExecutionError("PROJECT_PUBLISH_PROJECT_MAPPING_CONFLICT", 409)
    if not frappe.db.exists("Company", profile.company):
        raise ProjectPublishExecutionError("PROJECT_PUBLISH_COMPANY_UNAVAILABLE")
    if not frappe.db.exists("User", command.actor_user_id):
        raise ProjectPublishExecutionError("PROJECT_PUBLISH_BUSINESS_ACTOR_UNAVAILABLE", 403)
    now = datetime.now(UTC).replace(tzinfo=None)
    with project_publish_execution_write(command.request_global_id) as capability:
        project = frappe.get_doc({
            "doctype": "Project",
            "owner": command.actor_user_id,
            "naming_series": profile.naming_series,
            "project_name": command.title,
            "status": "Open",
            "company": profile.company,
            "expected_end_date": command.target_sop,
        })
        with business_actor_context(command.actor_user_id):
            insert_target(project, capability=capability)
        formal_id = str(project.name or "")
        if not formal_id or len(formal_id) > 140 or not frappe.db.exists("Project", formal_id):
            raise ProjectPublishExecutionError("PROJECT_PUBLISH_TARGET_IDENTITY_UNAVAILABLE", 500)
        target_version = _target_version(formal_id)
        mapping = frappe.get_doc({
            "doctype": MAPPING_DOCTYPE,
            "project_global_id": command.project_global_id,
            "tenant_id": command.tenant_id,
            "business_code": command.business_code,
            "formal_project_id": formal_id,
            "source_version": command.source_version,
            "source_hash": command.source_hash,
            "target_version": target_version,
            "last_request_global_id": command.request_global_id,
            "target_idempotency_key_hash": command.target_idempotency_key_hash,
            "business_actor_user_id": command.actor_user_id,
            "mapped_at": now,
        })
        insert_support(mapping, capability=capability)
        result = {"formalProjectId": formal_id, "targetVersion": target_version}
        receipt = frappe.get_doc({
            "doctype": RECEIPT_DOCTYPE,
            "target_idempotency_key_hash": command.target_idempotency_key_hash,
            "request_global_id": command.request_global_id,
            "semantic_request_hash": command.semantic_request_hash,
            "source_hash": command.source_hash,
            "project_global_id": command.project_global_id,
            "formal_project_id": formal_id,
            "target_version": target_version,
            "business_actor_user_id": command.actor_user_id,
            "service_user": service_user,
            "trace_id": trace_id,
            "result_json": canonical_json(result),
            "result_hash": canonical_hash(result),
            "completed_at": now,
        })
        insert_support(receipt, capability=capability)
    return ProjectPublishExecutionResult(formal_id, target_version, False)


def _target_version(formal_id: str) -> str:
    value = frappe.db.get_value("Project", formal_id, "modified")
    result = str(value or "")
    if not result or len(result) > 140:
        raise ProjectPublishExecutionError("PROJECT_PUBLISH_TARGET_VERSION_UNAVAILABLE", 500)
    return result
