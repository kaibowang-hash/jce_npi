from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

import frappe

from npi_erpnext_connector.frappe_validation import (
    insert_mbom_support_document,
    insert_mbom_target_document,
    mbom_execution_write,
    save_mbom_support_document,
    save_mbom_target_document,
)
from npi_erpnext_connector.item_contract import canonical_hash, canonical_json
from npi_erpnext_connector.mbom_config import MbomReceiverProfile
from npi_erpnext_connector.mbom_contract import (
    CREATE_INTENT,
    EDITABLE_DRAFT,
    MBOM_OPERATION,
    SUBMITTED_IMMUTABLE,
    MbomCommand,
    MbomNodeCommand,
)
from npi_erpnext_connector.receiver_security import (
    business_actor_context,
    business_actor_is_enabled,
)

MAPPING_DOCTYPE = "NPI ERP MBOM Mapping"
RECEIPT_DOCTYPE = "NPI ERP MBOM Operation Receipt"
ITEM_MAPPING_DOCTYPE = "NPI ERP Item Mapping"
UTC = timezone.utc
CUSTOM_TEMPORARY_BOM_FIELD = "custom_temporary_bom"


class MbomExecutionError(ValueError):
    def __init__(self, code: str, http_status: int = 422) -> None:
        super().__init__(code)
        self.code = code
        self.http_status = http_status


class MbomNodeExecutionError(MbomExecutionError):
    pass


@dataclass(frozen=True, slots=True)
class MbomNodeExecutionResult:
    stable_line_key: str
    assembly_source_key: str
    http_status: int
    formal_bom_id: str | None
    target_version: str | None
    target_submission_state: str | None
    mapping_version: int | None
    error_code: str | None

    def mapping(self) -> dict[str, object]:
        return {
            "stableLineKey": self.stable_line_key,
            "assemblySourceKey": self.assembly_source_key,
            "httpStatus": self.http_status,
            "formalBomId": self.formal_bom_id,
            "targetVersion": self.target_version,
            "targetSubmissionState": self.target_submission_state,
            "mappingVersion": self.mapping_version,
            "errorCode": self.error_code,
        }


@dataclass(frozen=True, slots=True)
class MbomExecutionResult:
    nodes: tuple[MbomNodeExecutionResult, ...]
    exact_replay: bool


def execute_mbom_command(
    command: MbomCommand,
    profile: MbomReceiverProfile,
    *,
    service_user: str,
    trace_id: str,
) -> MbomExecutionResult:
    if not business_actor_is_enabled(command.actor_user_id, service_user=service_user):
        raise MbomExecutionError("MBOM_PUBLISH_BUSINESS_ACTOR_UNAVAILABLE", 403)
    savepoint = f"npi_erp_mbom_{command.target_idempotency_key_hash[:16]}"
    frappe.db.savepoint(savepoint)
    try:
        return _execute_mbom_command(
            command,
            profile,
            service_user=service_user,
            trace_id=trace_id,
        )
    except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
        frappe.db.rollback(save_point=savepoint)
        return _recover_unique_race(command)
    except Exception:
        frappe.db.rollback(save_point=savepoint)
        raise


def _execute_mbom_command(
    command: MbomCommand,
    profile: MbomReceiverProfile,
    *,
    service_user: str,
    trace_id: str,
) -> MbomExecutionResult:
    receipt_name = frappe.db.get_value(
        RECEIPT_DOCTYPE,
        command.target_idempotency_key_hash,
        "name",
    )
    if receipt_name:
        receipt = frappe.get_doc(RECEIPT_DOCTYPE, receipt_name, for_update=True)
        return _result_from_receipt(command, receipt)
    duplicate_request = frappe.db.get_value(
        RECEIPT_DOCTYPE,
        {"request_global_id": command.request_global_id},
        "target_idempotency_key_hash",
    )
    if duplicate_request:
        raise MbomExecutionError("MBOM_PUBLISH_REQUEST_ID_CONFLICT", 409)
    if not frappe.db.exists("Company", profile.company):
        raise MbomExecutionError("MBOM_PUBLISH_COMPANY_UNAVAILABLE")
    currency = frappe.db.get_value("Company", profile.company, "default_currency")
    if not isinstance(currency, str) or not currency:
        raise MbomExecutionError("MBOM_PUBLISH_COMPANY_CURRENCY_UNAVAILABLE")
    custom_bom_values = _custom_bom_values(profile)
    _validate_item_readiness(command)

    results: list[MbomNodeExecutionResult] = []
    with mbom_execution_write(command.request_global_id) as capability:
        for node in command.nodes:
            node_savepoint = f"npi_erp_mbom_node_{node.assembly_source_key[:16]}"
            frappe.db.savepoint(node_savepoint)
            try:
                result = _execute_node(
                    command,
                    node,
                    profile,
                    currency,
                    custom_bom_values,
                    capability=capability,
                )
            except MbomNodeExecutionError as error:
                frappe.db.rollback(save_point=node_savepoint)
                result = _failed_node(node, error.code, error.http_status)
            except frappe.ValidationError:
                frappe.db.rollback(save_point=node_savepoint)
                result = _failed_node(
                    node,
                    "MBOM_PUBLISH_BUSINESS_VALIDATION",
                    422,
                )
            results.append(result)
        result_payload = [result.mapping() for result in results]
        receipt = frappe.get_doc(
            {
                "doctype": RECEIPT_DOCTYPE,
                "target_idempotency_key_hash": command.target_idempotency_key_hash,
                "request_global_id": command.request_global_id,
                "operation": MBOM_OPERATION,
                "semantic_request_hash": command.semantic_request_hash,
                "source_hash": command.source_hash,
                "topology_hash": command.topology_hash,
                "service_user": service_user,
                "trace_id": trace_id,
                "result_json": canonical_json(result_payload),
                "result_hash": canonical_hash(result_payload),
                "completed_at": datetime.now(UTC).replace(tzinfo=None),
            }
        )
        insert_mbom_support_document(receipt, capability=capability)
    return MbomExecutionResult(tuple(results), False)


def _validate_item_readiness(command: MbomCommand) -> None:
    for readiness in command.item_readiness:
        mapping = frappe.db.get_value(
            ITEM_MAPPING_DOCTYPE,
            readiness.stream_key_hash,
            ["mapping_version", "formal_item_code", "target_version"],
            as_dict=True,
        )
        if (
            not mapping
            or int(mapping.get("mapping_version") or 0) != readiness.mapping_version
            or str(mapping.get("formal_item_code") or "") != readiness.formal_item_code
            or str(mapping.get("target_version") or "") != readiness.target_version
        ):
            raise MbomExecutionError("MBOM_PUBLISH_ITEM_MAPPING_STALE", 409)
        current_version = frappe.db.get_value(
            "Item", readiness.formal_item_code, "modified"
        )
        if current_version is None or str(current_version) != readiness.target_version:
            raise MbomExecutionError("MBOM_PUBLISH_ITEM_TARGET_VERSION_CONFLICT", 409)


def _execute_node(
    command: MbomCommand,
    node: MbomNodeCommand,
    profile: MbomReceiverProfile,
    currency: str,
    custom_bom_values: dict[str, str],
    *,
    capability: object,
) -> MbomNodeExecutionResult:
    mapping_name = frappe.db.get_value(
        MAPPING_DOCTYPE,
        node.assembly_source_key,
        "name",
    )
    mapping = (
        frappe.get_doc(MAPPING_DOCTYPE, mapping_name, for_update=True)
        if mapping_name
        else None
    )
    if node.intent == CREATE_INTENT:
        if mapping is not None:
            raise MbomNodeExecutionError("MBOM_PUBLISH_STALE_MAPPING", 409)
        bom = frappe.get_doc(
            {
                "doctype": "BOM",
                "owner": command.actor_user_id,
                "item": node.formal_item_code,
                "company": profile.company,
                "currency": currency,
                "quantity": 1,
                "is_active": 1,
                "is_default": 0,
                "items": _component_rows(node),
                **custom_bom_values,
            }
        )
        with business_actor_context(command.actor_user_id):
            insert_mbom_target_document(bom, capability=capability)
        formal_bom_id = _formal_bom_id(bom)
        target_version = _target_version(formal_bom_id)
        mapping_version = 1
        mapping = frappe.get_doc(
            {
                "doctype": MAPPING_DOCTYPE,
                "assembly_source_key": node.assembly_source_key,
                "tenant_id": command.tenant_id,
                "project_global_id": command.project_global_id,
                "ebom_global_id": command.ebom_global_id,
                "stable_line_key": node.stable_line_key,
                "formal_bom_id": formal_bom_id,
                "mapping_version": mapping_version,
                "target_version": target_version,
                "submission_state": EDITABLE_DRAFT,
                "source_hash": command.source_hash,
                "topology_hash": command.topology_hash,
                "last_request_global_id": command.request_global_id,
                "last_target_idempotency_key_hash": command.target_idempotency_key_hash,
                "updated_at": datetime.now(UTC).replace(tzinfo=None),
            }
        )
        insert_mbom_support_document(mapping, capability=capability)
    else:
        if mapping is None:
            raise MbomNodeExecutionError("MBOM_PUBLISH_MAPPING_UNAVAILABLE", 409)
        if (
            int(mapping.mapping_version) != node.expected_mapping_version
            or str(mapping.formal_bom_id) != node.expected_formal_bom_id
            or str(mapping.target_version) != node.expected_target_version
            or str(mapping.tenant_id) != command.tenant_id
            or str(mapping.project_global_id) != command.project_global_id
            or str(mapping.ebom_global_id) != command.ebom_global_id
            or str(mapping.stable_line_key) != node.stable_line_key
            or str(mapping.submission_state) != EDITABLE_DRAFT
        ):
            raise MbomNodeExecutionError("MBOM_PUBLISH_STALE_MAPPING", 409)
        formal_bom_id = str(mapping.formal_bom_id)
        bom = frappe.get_doc("BOM", formal_bom_id, for_update=True)
        current_version = _target_version(formal_bom_id)
        if int(bom.docstatus) != 0:
            return MbomNodeExecutionResult(
                node.stable_line_key,
                node.assembly_source_key,
                200,
                formal_bom_id,
                current_version,
                SUBMITTED_IMMUTABLE,
                int(mapping.mapping_version),
                None,
            )
        if current_version != node.expected_target_version:
            raise MbomNodeExecutionError("MBOM_PUBLISH_TARGET_VERSION_CONFLICT", 409)
        bom.set("items", [])
        for row in _component_rows(node):
            bom.append("items", row)
        save_mbom_target_document(bom, capability=capability)
        target_version = _target_version(formal_bom_id)
        mapping_version = int(mapping.mapping_version) + 1
        mapping.mapping_version = mapping_version
        mapping.target_version = target_version
        mapping.submission_state = EDITABLE_DRAFT
        mapping.source_hash = command.source_hash
        mapping.topology_hash = command.topology_hash
        mapping.last_request_global_id = command.request_global_id
        mapping.last_target_idempotency_key_hash = command.target_idempotency_key_hash
        mapping.updated_at = datetime.now(UTC).replace(tzinfo=None)
        save_mbom_support_document(mapping, capability=capability)
    return MbomNodeExecutionResult(
        node.stable_line_key,
        node.assembly_source_key,
        200,
        formal_bom_id,
        target_version,
        EDITABLE_DRAFT,
        mapping_version,
        None,
    )


def _component_rows(node: MbomNodeCommand) -> list[dict[str, object]]:
    return [
        {
            "item_code": component.formal_item_code,
            "qty": float(component.quantity),
        }
        for component in node.components
    ]


def _custom_bom_values(profile: MbomReceiverProfile) -> dict[str, str]:
    field = frappe.get_meta("BOM").get_field(CUSTOM_TEMPORARY_BOM_FIELD)
    configured = profile.custom_temporary_bom_value
    if field is None:
        if configured is not None:
            raise MbomExecutionError(
                "MBOM_PUBLISH_CUSTOM_FIELD_UNAVAILABLE",
                422,
            )
        return {}
    options = tuple(
        line.strip()
        for line in str(getattr(field, "options", "") or "").splitlines()
        if line.strip()
    )
    if str(getattr(field, "fieldtype", "")) != "Select" or options != (
        "Yes",
        "No",
    ):
        raise MbomExecutionError(
            "MBOM_PUBLISH_CUSTOM_FIELD_INCOMPATIBLE",
            422,
        )
    if configured is None:
        if int(getattr(field, "reqd", 0) or 0) == 1:
            raise MbomExecutionError(
                "MBOM_PUBLISH_CUSTOM_FIELD_CONFIGURATION_REQUIRED",
                422,
            )
        return {}
    return {CUSTOM_TEMPORARY_BOM_FIELD: configured}


def _failed_node(
    node: MbomNodeCommand,
    code: str,
    status: int,
) -> MbomNodeExecutionResult:
    return MbomNodeExecutionResult(
        node.stable_line_key,
        node.assembly_source_key,
        status,
        None,
        None,
        None,
        None,
        code,
    )


def _formal_bom_id(bom: object) -> str:
    value = str(getattr(bom, "name", "") or "")
    if not value or len(value) > 140:
        raise MbomNodeExecutionError("MBOM_PUBLISH_TARGET_IDENTITY_UNAVAILABLE", 500)
    return value


def _target_version(formal_bom_id: str) -> str:
    value = frappe.db.get_value("BOM", formal_bom_id, "modified")
    if value is None:
        raise MbomNodeExecutionError("MBOM_PUBLISH_TARGET_VERSION_UNAVAILABLE", 500)
    result = str(value)
    if not result or len(result) > 140:
        raise MbomNodeExecutionError("MBOM_PUBLISH_TARGET_VERSION_UNAVAILABLE", 500)
    return result


def _result_from_receipt(command: MbomCommand, receipt: object) -> MbomExecutionResult:
    if (
        str(getattr(receipt, "request_global_id", "")) != command.request_global_id
        or str(getattr(receipt, "semantic_request_hash", ""))
        != command.semantic_request_hash
        or str(getattr(receipt, "source_hash", "")) != command.source_hash
        or str(getattr(receipt, "topology_hash", "")) != command.topology_hash
    ):
        raise MbomExecutionError("MBOM_PUBLISH_PAYLOAD_CONFLICT", 409)
    try:
        values = json.loads(str(getattr(receipt, "result_json", "")))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise MbomExecutionError("MBOM_PUBLISH_RECEIPT_INVALID", 500) from error
    if (
        not isinstance(values, list)
        or canonical_json(values) != str(getattr(receipt, "result_json", ""))
        or canonical_hash(values) != str(getattr(receipt, "result_hash", ""))
    ):
        raise MbomExecutionError("MBOM_PUBLISH_RECEIPT_INVALID", 500)
    nodes = tuple(_node_from_mapping(value) for value in values)
    if tuple(node.stable_line_key for node in nodes) != tuple(
        node.stable_line_key for node in command.nodes
    ):
        raise MbomExecutionError("MBOM_PUBLISH_RECEIPT_INVALID", 500)
    return MbomExecutionResult(nodes, True)


def _node_from_mapping(value: object) -> MbomNodeExecutionResult:
    keys = {
        "stableLineKey",
        "assemblySourceKey",
        "httpStatus",
        "formalBomId",
        "targetVersion",
        "targetSubmissionState",
        "mappingVersion",
        "errorCode",
    }
    if not isinstance(value, dict) or set(value) != keys:
        raise MbomExecutionError("MBOM_PUBLISH_RECEIPT_INVALID", 500)
    return MbomNodeExecutionResult(
        str(value["stableLineKey"]),
        str(value["assemblySourceKey"]),
        int(value["httpStatus"]),
        value["formalBomId"] if isinstance(value["formalBomId"], str) else None,
        value["targetVersion"] if isinstance(value["targetVersion"], str) else None,
        (
            value["targetSubmissionState"]
            if isinstance(value["targetSubmissionState"], str)
            else None
        ),
        int(value["mappingVersion"]) if type(value["mappingVersion"]) is int else None,
        value["errorCode"] if isinstance(value["errorCode"], str) else None,
    )


def _recover_unique_race(command: MbomCommand) -> MbomExecutionResult:
    try:
        receipt = frappe.get_doc(
            RECEIPT_DOCTYPE,
            command.target_idempotency_key_hash,
            for_update=True,
        )
    except frappe.DoesNotExistError:
        receipt = None
    if receipt is not None:
        return _result_from_receipt(command, receipt)
    raise MbomExecutionError("MBOM_PUBLISH_TARGET_IDENTITY_CONFLICT", 409)
