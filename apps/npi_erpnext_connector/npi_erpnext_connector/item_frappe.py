from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import frappe

from npi_erpnext_connector.frappe_validation import (
    insert_item_support_document,
    insert_item_target_document,
    item_execution_write,
    save_item_support_document,
    save_item_target_document,
)
from npi_erpnext_connector.item_config import ItemReceiverProfile
from npi_erpnext_connector.item_contract import (
    CREATE_INTENT,
    ItemCommand,
    canonical_hash,
    canonical_json,
)
from npi_erpnext_connector.receiver_security import (
    business_actor_context,
    business_actor_is_enabled,
)

MAPPING_DOCTYPE = "NPI ERP Item Mapping"
RECEIPT_DOCTYPE = "NPI ERP Item Operation Receipt"
UTC = timezone.utc
_SAFE_ATTRIBUTE_FIELD_TYPES = {
    "Data",
    "Small Text",
    "Text",
    "Long Text",
    "Text Editor",
}


class ItemExecutionError(ValueError):
    def __init__(self, code: str, http_status: int = 422) -> None:
        super().__init__(code)
        self.code = code
        self.http_status = http_status


@dataclass(frozen=True, slots=True)
class ItemExecutionResult:
    formal_item_code: str
    target_version: str
    mapping_version: int
    exact_replay: bool


def execute_item_command(
    command: ItemCommand,
    profile: ItemReceiverProfile,
    *,
    service_user: str,
    trace_id: str,
) -> ItemExecutionResult:
    if not business_actor_is_enabled(command.actor_user_id, service_user=service_user):
        raise ItemExecutionError("ITEM_PUBLISH_BUSINESS_ACTOR_UNAVAILABLE", 403)
    savepoint = f"npi_erp_item_{command.target_idempotency_key_hash[:16]}"
    frappe.db.savepoint(savepoint)
    try:
        return _execute_item_command(
            command,
            profile,
            service_user=service_user,
            trace_id=trace_id,
        )
    except ItemExecutionError:
        frappe.db.rollback(save_point=savepoint)
        raise
    except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
        frappe.db.rollback(save_point=savepoint)
        return _recover_unique_race(command)


def _execute_item_command(
    command: ItemCommand,
    profile: ItemReceiverProfile,
    *,
    service_user: str,
    trace_id: str,
) -> ItemExecutionResult:
    existing_name = frappe.db.get_value(
        RECEIPT_DOCTYPE,
        command.target_idempotency_key_hash,
        "name",
    )
    if existing_name:
        receipt = frappe.get_doc(RECEIPT_DOCTYPE, existing_name, for_update=True)
        if (
            str(receipt.request_global_id) != command.request_global_id
            or str(receipt.semantic_request_hash) != command.semantic_request_hash
            or str(receipt.source_hash) != command.source_hash
        ):
            raise ItemExecutionError("ITEM_PUBLISH_PAYLOAD_CONFLICT", 409)
        return ItemExecutionResult(
            str(receipt.formal_item_code),
            str(receipt.target_version),
            int(receipt.mapping_version),
            True,
        )
    duplicate_request = frappe.db.get_value(
        RECEIPT_DOCTYPE,
        {"request_global_id": command.request_global_id},
        "target_idempotency_key_hash",
    )
    if duplicate_request:
        raise ItemExecutionError("ITEM_PUBLISH_REQUEST_ID_CONFLICT", 409)

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
    with item_execution_write(command.request_global_id) as capability:
        if command.intent == CREATE_INTENT:
            if mapping is not None:
                raise ItemExecutionError("ITEM_PUBLISH_STALE_MAPPING", 409)
            pending_item_code = _pending_item_code(command)
            item_values = _create_item_values(command, profile)
            item = frappe.get_doc(
                {
                    "doctype": "Item",
                    "owner": command.actor_user_id,
                    "item_code": pending_item_code,
                    "naming_series": profile.erp_naming_series,
                    **item_values,
                }
            )
            with business_actor_context(command.actor_user_id):
                insert_item_target_document(item, capability=capability)
            item_code = _formal_item_code(item)
            if item_code == pending_item_code:
                raise ItemExecutionError("ITEM_PUBLISH_ERP_NAMING_UNAVAILABLE")
            if str(getattr(item, "item_code", "") or "") != item_code:
                item = frappe.get_doc("Item", item_code, for_update=True)
                item.item_code = item_code
                save_item_target_document(item, capability=capability)
            if frappe.db.get_value("Item", item_code, "item_code") != item_code:
                raise ItemExecutionError("ITEM_PUBLISH_ERP_NAMING_UNAVAILABLE", 500)
            target_version = _target_version(item)
            mapping_version = 1
            mapping = frappe.get_doc(
                {
                    "doctype": MAPPING_DOCTYPE,
                    "stream_key_hash": command.source_stream_key_hash,
                    "tenant_id": command.tenant_id,
                    "project_global_id": command.project_global_id,
                    "engineering_item_id": command.engineering_item_id,
                    "formal_item_code": item_code,
                    "mapping_version": mapping_version,
                    "target_version": target_version,
                    "source_hash": command.source_hash,
                    "last_request_global_id": command.request_global_id,
                    "last_target_idempotency_key_hash": command.target_idempotency_key_hash,
                    "updated_at": datetime.now(UTC).replace(tzinfo=None),
                }
            )
            insert_item_support_document(mapping, capability=capability)
        else:
            if mapping is None:
                raise ItemExecutionError("ITEM_PUBLISH_MAPPING_UNAVAILABLE", 409)
            if (
                int(mapping.mapping_version) != command.expected_mapping_version
                or str(mapping.target_version) != command.expected_target_version
                or str(mapping.tenant_id) != command.tenant_id
                or str(mapping.project_global_id) != command.project_global_id
                or str(mapping.engineering_item_id) != command.engineering_item_id
            ):
                raise ItemExecutionError("ITEM_PUBLISH_STALE_MAPPING", 409)
            item = frappe.get_doc(
                "Item", str(mapping.formal_item_code), for_update=True
            )
            if _target_version(item) != command.expected_target_version:
                raise ItemExecutionError("ITEM_PUBLISH_TARGET_VERSION_CONFLICT", 409)
            for fieldname, value in _engineering_update_values(
                command, profile
            ).items():
                setattr(item, fieldname, value)
            save_item_target_document(item, capability=capability)
            target_version = _target_version(item)
            mapping_version = int(mapping.mapping_version) + 1
            mapping.mapping_version = mapping_version
            mapping.target_version = target_version
            mapping.source_hash = command.source_hash
            mapping.last_request_global_id = command.request_global_id
            mapping.last_target_idempotency_key_hash = (
                command.target_idempotency_key_hash
            )
            mapping.updated_at = datetime.now(UTC).replace(tzinfo=None)
            save_item_support_document(mapping, capability=capability)
            item_code = str(mapping.formal_item_code)

        result = {
            "formalItemCode": item_code,
            "targetVersion": target_version,
            "mappingVersion": mapping_version,
        }
        receipt = frappe.get_doc(
            {
                "doctype": RECEIPT_DOCTYPE,
                "target_idempotency_key_hash": command.target_idempotency_key_hash,
                "request_global_id": command.request_global_id,
                "operation": "publish_released_item",
                "semantic_request_hash": command.semantic_request_hash,
                "source_stream_key_hash": command.source_stream_key_hash,
                "source_hash": command.source_hash,
                "intent": command.intent,
                "formal_item_code": item_code,
                "target_version": target_version,
                "mapping_version": mapping_version,
                "service_user": service_user,
                "trace_id": trace_id,
                "result_json": canonical_json(result),
                "result_hash": canonical_hash(result),
                "completed_at": datetime.now(UTC).replace(tzinfo=None),
            }
        )
        insert_item_support_document(receipt, capability=capability)
    return ItemExecutionResult(item_code, target_version, mapping_version, False)


def _create_item_values(
    command: ItemCommand,
    profile: ItemReceiverProfile,
) -> dict[str, object]:
    if len(command.description) > 140:
        raise ItemExecutionError("ITEM_PUBLISH_ITEM_NAME_TOO_LONG")
    if not frappe.db.exists("Item Group", profile.item_group):
        raise ItemExecutionError("ITEM_PUBLISH_ITEM_GROUP_UNAVAILABLE")
    target_uom = profile.target_uom(command.engineering_uom)
    if not frappe.db.exists("UOM", target_uom):
        raise ItemExecutionError("ITEM_PUBLISH_UOM_UNAVAILABLE")
    values: dict[str, object] = {
        "item_name": command.description,
        "description": command.description,
        "item_group": profile.item_group,
        "stock_uom": target_uom,
    }
    values.update(_engineering_attribute_values(command, profile))
    return values


def _engineering_update_values(
    command: ItemCommand,
    profile: ItemReceiverProfile,
) -> dict[str, object]:
    return {
        "description": command.description,
        **_engineering_attribute_values(command, profile),
    }


def _engineering_attribute_values(
    command: ItemCommand,
    profile: ItemReceiverProfile,
) -> dict[str, object]:
    values: dict[str, object] = {}
    meta = frappe.get_meta("Item")
    for fieldname, value in profile.attribute_values(command.attributes).items():
        field = meta.get_field(fieldname)
        if (
            field is None
            or bool(getattr(field, "read_only", False))
            or str(getattr(field, "fieldtype", "")) not in _SAFE_ATTRIBUTE_FIELD_TYPES
        ):
            raise ItemExecutionError("ITEM_PUBLISH_ATTRIBUTE_MAPPING_INVALID")
        values[fieldname] = value
    return values


def _recover_unique_race(command: ItemCommand) -> ItemExecutionResult:
    try:
        receipt = frappe.get_doc(
            RECEIPT_DOCTYPE,
            command.target_idempotency_key_hash,
            for_update=True,
        )
    except frappe.DoesNotExistError:
        receipt = None
    if receipt is not None:
        if (
            str(receipt.request_global_id) != command.request_global_id
            or str(receipt.semantic_request_hash) != command.semantic_request_hash
            or str(receipt.source_hash) != command.source_hash
        ):
            raise ItemExecutionError("ITEM_PUBLISH_PAYLOAD_CONFLICT", 409)
        return ItemExecutionResult(
            str(receipt.formal_item_code),
            str(receipt.target_version),
            int(receipt.mapping_version),
            True,
        )
    try:
        frappe.get_doc(
            MAPPING_DOCTYPE,
            command.source_stream_key_hash,
            for_update=True,
        )
    except frappe.DoesNotExistError:
        pass
    else:
        raise ItemExecutionError("ITEM_PUBLISH_STALE_MAPPING", 409)
    raise ItemExecutionError("ITEM_PUBLISH_TARGET_IDENTITY_CONFLICT", 409)


def _target_version(item: object) -> str:
    item_code = _formal_item_code(item)
    value = frappe.db.get_value("Item", item_code, "modified")
    if value is None:
        raise ItemExecutionError("ITEM_PUBLISH_TARGET_VERSION_UNAVAILABLE", 500)
    result = str(value)
    if not result or len(result) > 140:
        raise ItemExecutionError("ITEM_PUBLISH_TARGET_VERSION_UNAVAILABLE", 500)
    return result


def _formal_item_code(item: object) -> str:
    value = str(getattr(item, "name", "") or "")
    if not value or len(value) > 140:
        raise ItemExecutionError("ITEM_PUBLISH_TARGET_IDENTITY_UNAVAILABLE", 500)
    return value


def _pending_item_code(command: ItemCommand) -> str:
    return f"NPI-PENDING-{command.target_idempotency_key_hash[:32]}"
