from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

import frappe

from npi_erpnext_connector.frappe_validation import (
    insert_tool_asset_support_document,
    insert_tool_asset_target_document,
    save_tool_asset_support_document,
    save_tool_asset_target_document,
    tool_asset_execution_write,
)
from npi_erpnext_connector.item_contract import canonical_hash, canonical_json
from npi_erpnext_connector.receiver_security import (
    business_actor_context,
    business_actor_is_enabled,
)
from npi_erpnext_connector.tool_asset_config import ToolAssetReceiverProfile
from npi_erpnext_connector.tool_asset_contract import (
    CREATE_OPERATION,
    OWNED_FIELDS,
    ToolAssetCommand,
)

MAPPING_DOCTYPE = "NPI ERP Tool Asset Mapping"
RECEIPT_DOCTYPE = "NPI ERP Tool Asset Operation Receipt"
SOURCE_STREAM_FIELD = "custom_npi_source_stream_key"
CUSTOM_FIELDS = {
    "tooling_master_title": "custom_npi_tooling_master_title",
    "physical_set_serial": "custom_npi_physical_set_serial",
    "tooling_requirement_kind": "custom_npi_tooling_requirement_kind",
    "source_tooling_revision": "custom_npi_source_tooling_revision",
    "acceptance_evidence_reference": ("custom_npi_acceptance_evidence_reference"),
}
UTC = timezone.utc


class ToolAssetExecutionError(ValueError):
    def __init__(self, code: str, http_status: int = 422) -> None:
        super().__init__(code)
        self.code = code
        self.http_status = http_status


@dataclass(frozen=True, slots=True)
class ToolAssetExecutionResult:
    http_status: int
    formal_asset_id: str | None
    target_version: str | None
    mapping_version: int | None
    error_code: str | None
    exact_replay: bool

    def mapping(self) -> dict[str, object]:
        return {
            "httpStatus": self.http_status,
            "formalAssetId": self.formal_asset_id,
            "targetVersion": self.target_version,
            "mappingVersion": self.mapping_version,
            "errorCode": self.error_code,
        }


def execute_tool_asset_command(
    command: ToolAssetCommand,
    profile: ToolAssetReceiverProfile,
    *,
    service_user: str,
    trace_id: str,
) -> ToolAssetExecutionResult:
    if not business_actor_is_enabled(command.actor_user_id, service_user=service_user):
        raise ToolAssetExecutionError("TOOL_ASSET_BUSINESS_ACTOR_UNAVAILABLE", 403)
    savepoint = f"npi_erp_tool_asset_{command.target_idempotency_key_hash[:16]}"
    frappe.db.savepoint(savepoint)
    try:
        return _execute_tool_asset_command(
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


def _execute_tool_asset_command(
    command: ToolAssetCommand,
    profile: ToolAssetReceiverProfile,
    *,
    service_user: str,
    trace_id: str,
) -> ToolAssetExecutionResult:
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
        raise ToolAssetExecutionError("TOOL_ASSET_REQUEST_ID_CONFLICT", 409)
    _validate_target_schema()
    _validate_profile(profile)
    with tool_asset_execution_write(command.request_global_id) as capability:
        mapping_name = frappe.db.get_value(
            MAPPING_DOCTYPE,
            command.source_stream_key_hash,
            "name",
        )
        mapping = (
            frappe.get_doc(MAPPING_DOCTYPE, mapping_name, for_update=True)
            if mapping_name
            else None
        )
        if command.operation == CREATE_OPERATION:
            result = _create_asset(command, profile, mapping, capability)
        else:
            result = _update_asset(command, mapping, capability)
        payload = result.mapping()
        receipt = frappe.get_doc(
            {
                "doctype": RECEIPT_DOCTYPE,
                "target_idempotency_key_hash": (command.target_idempotency_key_hash),
                "request_global_id": command.request_global_id,
                "operation": command.operation,
                "semantic_request_hash": command.semantic_request_hash,
                "source_stream_key_hash": command.source_stream_key_hash,
                "source_hash": command.source_hash,
                "formal_asset_id": result.formal_asset_id,
                "target_version": result.target_version,
                "mapping_version": result.mapping_version,
                "service_user": service_user,
                "trace_id": trace_id,
                "result_json": canonical_json(payload),
                "result_hash": canonical_hash(payload),
                "completed_at": datetime.now(UTC).replace(tzinfo=None),
            }
        )
        insert_tool_asset_support_document(receipt, capability=capability)
    return result


def _create_asset(
    command: ToolAssetCommand,
    profile: ToolAssetReceiverProfile,
    mapping: object | None,
    capability: object,
) -> ToolAssetExecutionResult:
    if mapping is not None or command.expected_mapping_version != 0:
        raise ToolAssetExecutionError("TOOL_ASSET_STALE_MAPPING", 409)
    existing = frappe.db.get_value(
        "Asset",
        {SOURCE_STREAM_FIELD: command.source_stream_key_hash},
        "name",
    )
    if existing:
        raise ToolAssetExecutionError("TOOL_ASSET_TARGET_IDENTITY_CONFLICT", 409)
    asset_meta = frappe.get_meta("Asset")
    values: dict[str, object] = {
        "doctype": "Asset",
        "owner": command.actor_user_id,
        "item_code": profile.item_code,
        "asset_name": command.tooling_master_title,
        "company": profile.company,
        "location": profile.location,
        "purchase_date": command.accepted_at.date(),
        "available_for_use_date": command.accepted_at.date(),
        "calculate_depreciation": 0,
        "maintenance_required": 0,
        "asset_quantity": 1,
        SOURCE_STREAM_FIELD: command.source_stream_key_hash,
        **_custom_values(command),
    }
    if asset_meta.has_field("asset_type"):
        values["asset_type"] = "Existing Asset"
    elif asset_meta.has_field("is_existing_asset"):
        values["is_existing_asset"] = 1
    if asset_meta.has_field("net_purchase_amount"):
        values["net_purchase_amount"] = profile.purchase_amount
    elif asset_meta.has_field("gross_purchase_amount"):
        values["gross_purchase_amount"] = profile.purchase_amount
    else:
        raise ToolAssetExecutionError("TOOL_ASSET_TARGET_SCHEMA_INCOMPATIBLE")
    asset = frappe.get_doc(values)
    with business_actor_context(command.actor_user_id):
        insert_tool_asset_target_document(asset, capability=capability)
    formal_asset_id = _formal_asset_id(asset)
    target_version = _target_version(formal_asset_id)
    mapping_version = 1
    mapping = frappe.get_doc(
        {
            "doctype": MAPPING_DOCTYPE,
            "source_stream_key_hash": command.source_stream_key_hash,
            "tenant_id": command.tenant_id,
            "project_global_id": command.project_global_id,
            "tooling_set_global_id": command.tooling_set_global_id,
            "formal_asset_id": formal_asset_id,
            "mapping_version": mapping_version,
            "target_version": target_version,
            "source_hash": command.source_hash,
            "last_request_global_id": command.request_global_id,
            "last_target_idempotency_key_hash": (command.target_idempotency_key_hash),
            "updated_at": datetime.now(UTC).replace(tzinfo=None),
        }
    )
    insert_tool_asset_support_document(mapping, capability=capability)
    return ToolAssetExecutionResult(
        200,
        formal_asset_id,
        target_version,
        mapping_version,
        None,
        False,
    )


def _update_asset(
    command: ToolAssetCommand,
    mapping: object | None,
    capability: object,
) -> ToolAssetExecutionResult:
    if mapping is None:
        raise ToolAssetExecutionError("TOOL_ASSET_MAPPING_UNAVAILABLE", 409)
    if (
        int(mapping.mapping_version) != command.expected_mapping_version
        or str(mapping.formal_asset_id) != command.expected_formal_asset_id
        or str(mapping.target_version) != command.expected_target_version
        or str(mapping.tenant_id) != command.tenant_id
        or str(mapping.project_global_id) != command.project_global_id
        or str(mapping.tooling_set_global_id) != command.tooling_set_global_id
    ):
        raise ToolAssetExecutionError("TOOL_ASSET_STALE_MAPPING", 409)
    formal_asset_id = str(mapping.formal_asset_id)
    asset = frappe.get_doc("Asset", formal_asset_id, for_update=True)
    if int(asset.docstatus) != 0:
        raise ToolAssetExecutionError("TOOL_ASSET_TARGET_PROTECTED", 409)
    current_version = _target_version(formal_asset_id)
    if current_version != command.expected_target_version:
        raise ToolAssetExecutionError("TOOL_ASSET_TARGET_VERSION_CONFLICT", 409)
    if str(asset.get(SOURCE_STREAM_FIELD) or "") != command.source_stream_key_hash:
        raise ToolAssetExecutionError("TOOL_ASSET_TARGET_IDENTITY_CONFLICT", 409)
    asset.asset_name = command.tooling_master_title
    for fieldname, value in _custom_values(command).items():
        asset.set(fieldname, value)
    save_tool_asset_target_document(asset, capability=capability)
    target_version = _target_version(formal_asset_id)
    mapping.mapping_version = int(mapping.mapping_version) + 1
    mapping.target_version = target_version
    mapping.source_hash = command.source_hash
    mapping.last_request_global_id = command.request_global_id
    mapping.last_target_idempotency_key_hash = command.target_idempotency_key_hash
    mapping.updated_at = datetime.now(UTC).replace(tzinfo=None)
    save_tool_asset_support_document(mapping, capability=capability)
    return ToolAssetExecutionResult(
        200,
        formal_asset_id,
        target_version,
        int(mapping.mapping_version),
        None,
        False,
    )


def _validate_target_schema() -> None:
    meta = frappe.get_meta("Asset")
    stream = meta.get_field(SOURCE_STREAM_FIELD)
    if (
        stream is None
        or str(stream.fieldtype) != "Data"
        or int(stream.read_only or 0) != 1
        or int(stream.unique or 0) != 1
    ):
        raise ToolAssetExecutionError("TOOL_ASSET_TARGET_SCHEMA_INCOMPATIBLE")
    for code in OWNED_FIELDS:
        field = meta.get_field(CUSTOM_FIELDS[code])
        if field is None or int(field.read_only or 0) != 1:
            raise ToolAssetExecutionError("TOOL_ASSET_TARGET_SCHEMA_INCOMPATIBLE")


def _validate_profile(profile: ToolAssetReceiverProfile) -> None:
    if not frappe.db.exists("Company", profile.company):
        raise ToolAssetExecutionError("TOOL_ASSET_COMPANY_UNAVAILABLE")
    if not frappe.db.exists("Location", profile.location):
        raise ToolAssetExecutionError("TOOL_ASSET_LOCATION_UNAVAILABLE")
    item = frappe.db.get_value(
        "Item",
        profile.item_code,
        ["is_fixed_asset", "is_stock_item", "disabled", "asset_category"],
        as_dict=True,
    )
    if (
        not item
        or int(item.get("is_fixed_asset") or 0) != 1
        or int(item.get("is_stock_item") or 0) != 0
        or int(item.get("disabled") or 0) != 0
        or not str(item.get("asset_category") or "")
    ):
        raise ToolAssetExecutionError("TOOL_ASSET_ITEM_PROFILE_INVALID")


def _custom_values(command: ToolAssetCommand) -> dict[str, str]:
    return {
        CUSTOM_FIELDS[code]: value for code, value in command.owned_values().items()
    }


def _formal_asset_id(asset: object) -> str:
    value = str(getattr(asset, "name", "") or "")
    if not value or len(value) > 140:
        raise ToolAssetExecutionError("TOOL_ASSET_TARGET_IDENTITY_UNAVAILABLE", 500)
    return value


def _target_version(formal_asset_id: str) -> str:
    value = frappe.db.get_value("Asset", formal_asset_id, "modified")
    result = str(value or "")
    if not result or len(result) > 140:
        raise ToolAssetExecutionError("TOOL_ASSET_TARGET_VERSION_UNAVAILABLE", 500)
    return result


def _result_from_receipt(
    command: ToolAssetCommand,
    receipt: object,
) -> ToolAssetExecutionResult:
    if (
        str(getattr(receipt, "request_global_id", "")) != command.request_global_id
        or str(getattr(receipt, "operation", "")) != command.operation
        or str(getattr(receipt, "semantic_request_hash", ""))
        != command.semantic_request_hash
        or str(getattr(receipt, "source_stream_key_hash", ""))
        != command.source_stream_key_hash
        or str(getattr(receipt, "source_hash", "")) != command.source_hash
    ):
        raise ToolAssetExecutionError("TOOL_ASSET_PAYLOAD_CONFLICT", 409)
    try:
        value = json.loads(str(getattr(receipt, "result_json", "")))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ToolAssetExecutionError("TOOL_ASSET_RECEIPT_INVALID", 500) from error
    if (
        not isinstance(value, dict)
        or canonical_json(value) != str(getattr(receipt, "result_json", ""))
        or canonical_hash(value) != str(getattr(receipt, "result_hash", ""))
    ):
        raise ToolAssetExecutionError("TOOL_ASSET_RECEIPT_INVALID", 500)
    expected_keys = {
        "httpStatus",
        "formalAssetId",
        "targetVersion",
        "mappingVersion",
        "errorCode",
    }
    if set(value) != expected_keys:
        raise ToolAssetExecutionError("TOOL_ASSET_RECEIPT_INVALID", 500)
    return ToolAssetExecutionResult(
        int(value["httpStatus"]),
        value["formalAssetId"] if isinstance(value["formalAssetId"], str) else None,
        value["targetVersion"] if isinstance(value["targetVersion"], str) else None,
        int(value["mappingVersion"]) if type(value["mappingVersion"]) is int else None,
        value["errorCode"] if isinstance(value["errorCode"], str) else None,
        True,
    )


def _recover_unique_race(command: ToolAssetCommand) -> ToolAssetExecutionResult:
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
    raise ToolAssetExecutionError("TOOL_ASSET_TARGET_IDENTITY_CONFLICT", 409)
