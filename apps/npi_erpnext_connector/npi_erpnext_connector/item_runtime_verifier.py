from __future__ import annotations

import time
from dataclasses import replace
from uuid import uuid4

import erpnext
import frappe

from npi_erpnext_connector import __version__ as connector_version
from npi_erpnext_connector.item_api import (
    ITEM_METHOD_PATH,
    SERVICE_ROLE,
    publish_item,
)
from npi_erpnext_connector.item_config import ItemReceiverProfile, load_item_profile
from npi_erpnext_connector.item_contract import (
    ItemCommand,
    canonical_hash,
    canonical_json,
    decode_item_command,
)
from npi_erpnext_connector.item_frappe import (
    ItemExecutionError,
    _pending_item_code,
    execute_item_command,
)
from npi_erpnext_connector.receiver_security import (
    request_signature,
    verify_response,
)

ATTESTATION = "erpnext-test-item-rollback-v1"
_SAVEPOINT = "npi_erp_item_runtime_verifier"
_MISSING = object()


def run(attestation: str) -> dict[str, object]:
    """Exercise Item create, replay, update and conflict, then roll back all writes."""

    if attestation != ATTESTATION:
        raise RuntimeError("ERPNext test runtime attestation is invalid.")
    frappe_major = _major(frappe.__version__)
    erpnext_major = _major(erpnext.__version__)
    if frappe_major not in {15, 16} or erpnext_major not in {15, 16}:
        raise RuntimeError("ERPNext test runtime version is unsupported.")
    baseline = _counts()
    previous_user = str(getattr(frappe.session, "user", "") or "Guest")
    naming_default_changed = False
    frappe.db.savepoint(_SAVEPOINT)
    try:
        frappe.set_user("Administrator")
        item_group = _item_group()
        stock_uom = _stock_uom()
        erp_naming_series, naming_default_changed = _prepare_erp_item_naming()
        suffix = uuid4().hex[:16].upper()
        business_actor = _business_user(suffix)
        project_id = str(uuid4())
        node_id = str(uuid4())
        line_id = str(uuid4())
        engineering_id = f"RUNTIME-{suffix}"
        profile = load_item_profile(
            {
                "npi_erp_connector_disabled": False,
                "npi_erp_connector_item_profile": {
                    "itemGroup": item_group,
                    "erpNamingSeries": erp_naming_series,
                    "uomMap": {stock_uom: stock_uom},
                    "attributeFieldMap": {},
                    "ignoredAttributes": [],
                },
            }
        )
        create = _command(
            project_id=project_id,
            node_id=node_id,
            line_id=line_id,
            engineering_id=engineering_id,
            actor_user_id=business_actor,
            description="NPI Connector rollback verification",
            stock_uom=stock_uom,
            intent="create_item",
            expected_mapping_version=0,
            expected_target_version=None,
        )
        created = execute_item_command(
            create,
            profile,
            service_user="Administrator",
            trace_id=f"runtime-{suffix}",
        )
        if created.exact_replay or created.mapping_version != 1:
            raise RuntimeError("ERPNext Item create verification failed.")
        created_item = frappe.get_doc("Item", created.formal_item_code)
        if (
            created.formal_item_code == _pending_item_code(create)
            or str(created_item.item_code) != created.formal_item_code
            or str(created_item.owner) != business_actor
        ):
            raise RuntimeError("ERPNext Item naming or creator verification failed.")
        replayed = execute_item_command(
            create,
            profile,
            service_user="Administrator",
            trace_id=f"runtime-{suffix}",
        )
        if not replayed.exact_replay or replayed != replace(created, exact_replay=True):
            raise RuntimeError("ERPNext Item replay verification failed.")
        updated_command = _command(
            project_id=project_id,
            node_id=node_id,
            line_id=line_id,
            engineering_id=engineering_id,
            actor_user_id=business_actor,
            description="NPI Connector rollback verification updated",
            stock_uom=stock_uom,
            intent="update_item_engineering_fields",
            expected_mapping_version=created.mapping_version,
            expected_target_version=created.target_version,
        )
        updated = execute_item_command(
            updated_command,
            profile,
            service_user="Administrator",
            trace_id=f"runtime-{suffix}-update",
        )
        if updated.exact_replay or updated.mapping_version != 2:
            raise RuntimeError("ERPNext Item update verification failed.")
        stale = _command(
            project_id=project_id,
            node_id=node_id,
            line_id=line_id,
            engineering_id=engineering_id,
            actor_user_id=business_actor,
            description="NPI Connector stale mapping verification",
            stock_uom=stock_uom,
            intent="update_item_engineering_fields",
            expected_mapping_version=created.mapping_version,
            expected_target_version=created.target_version,
        )
        _expect_execution_error(
            stale,
            profile,
            "ITEM_PUBLISH_STALE_MAPPING",
            trace_id=f"runtime-{suffix}-stale",
        )
        target = frappe.get_doc("Item", updated.formal_item_code)
        target.description = "ERP-owned concurrent target change"
        target.save()
        target_conflict = _command(
            project_id=project_id,
            node_id=node_id,
            line_id=line_id,
            engineering_id=engineering_id,
            actor_user_id=business_actor,
            description="NPI Connector target conflict verification",
            stock_uom=stock_uom,
            intent="update_item_engineering_fields",
            expected_mapping_version=updated.mapping_version,
            expected_target_version=updated.target_version,
        )
        _expect_execution_error(
            target_conflict,
            profile,
            "ITEM_PUBLISH_TARGET_VERSION_CONFLICT",
            trace_id=f"runtime-{suffix}-target-conflict",
        )
        conflicting = _command(
            project_id=project_id,
            node_id=node_id,
            line_id=line_id,
            engineering_id=engineering_id,
            actor_user_id=business_actor,
            description="NPI Connector conflicting replay",
            stock_uom=stock_uom,
            intent="update_item_engineering_fields",
            expected_mapping_version=created.mapping_version,
            expected_target_version=created.target_version,
            target_idempotency_key_hash=updated_command.target_idempotency_key_hash,
        )
        try:
            execute_item_command(
                conflicting,
                profile,
                service_user="Administrator",
                trace_id=f"runtime-{suffix}-conflict",
            )
        except ItemExecutionError as error:
            if error.code != "ITEM_PUBLISH_PAYLOAD_CONFLICT":
                raise
        else:
            raise RuntimeError("ERPNext Item payload conflict was not rejected.")
        api = _verify_api(
            project_id=str(uuid4()),
            node_id=str(uuid4()),
            line_id=str(uuid4()),
            engineering_id=f"RUNTIME-API-{suffix}",
            item_group=item_group,
            stock_uom=stock_uom,
            erp_naming_series=erp_naming_series,
            suffix=suffix,
            business_actor=business_actor,
        )
        during = _counts()
        if during != {
            "items": baseline["items"] + 2,
            "mappings": baseline["mappings"] + 2,
            "receipts": baseline["receipts"] + 3,
            "users": baseline["users"] + 2,
        }:
            raise RuntimeError("ERPNext Item runtime write set is invalid.")
    finally:
        frappe.db.rollback(save_point=_SAVEPOINT)
        if naming_default_changed:
            frappe.clear_cache()
        frappe.set_user(previous_user)
    if _counts() != baseline:
        raise RuntimeError("ERPNext Item runtime rollback verification failed.")
    return {
        "status": "PASS",
        "connectorVersion": connector_version,
        "frappeMajor": frappe_major,
        "erpnextMajor": erpnext_major,
        "create": True,
        "erpManagedItemCode": True,
        "businessCreatorAttribution": True,
        "exactReplay": True,
        "update": True,
        "payloadConflict": True,
        "staleMapping": True,
        "targetVersionConflict": True,
        **api,
        "rollback": True,
    }


def _command(
    *,
    project_id: str,
    node_id: str,
    line_id: str,
    engineering_id: str,
    actor_user_id: str,
    description: str,
    stock_uom: str,
    intent: str,
    expected_mapping_version: int,
    expected_target_version: str | None,
    target_idempotency_key_hash: str | None = None,
):
    item = {
        "description": description,
        "engineeringUom": stock_uom,
        "attributes": {},
    }
    source_payload = {
        "schemaVersion": 1,
        "tenantId": "RUNTIME-VERIFY",
        "projectGlobalId": project_id,
        "engineeringItemId": engineering_id,
        "selectedPublishNodeGlobalId": node_id,
        "itemMaster": item,
        "occurrences": [
            {
                "publishNodeGlobalId": node_id,
                "lineGlobalId": line_id,
                "engineeringItemId": engineering_id,
                **item,
                "lineHash": canonical_hash(
                    {"lineGlobalId": line_id, "description": description}
                ),
                "nodeInputHash": canonical_hash(
                    {"publishNodeGlobalId": node_id, "description": description}
                ),
            }
        ],
    }
    source_hash = canonical_hash(source_payload)
    stream_hash = canonical_hash(
        {
            "schemaVersion": 1,
            "tenantId": "RUNTIME-VERIFY",
            "projectGlobalId": project_id,
            "engineeringItemId": engineering_id,
        }
    )
    request = {
        "contractVersion": 2,
        "operation": "publish_released_item",
        "requestGlobalId": str(uuid4()),
        "attemptGlobalId": str(uuid4()),
        "attemptNumber": 1,
        "targetIdempotencyKeyHash": (
            target_idempotency_key_hash or canonical_hash({"sourceHash": source_hash})
        ),
        "sourceHash": source_hash,
        "actorUserId": actor_user_id,
        "source": {
            **source_payload,
            "streamKeyHash": stream_hash,
            "sourceHash": source_hash,
        },
        "intent": intent,
        "expectedMappingVersion": expected_mapping_version,
        "expectedTargetVersion": expected_target_version,
    }
    return decode_item_command(canonical_json(request).encode("utf-8"))


def _expect_execution_error(
    command: ItemCommand,
    profile: ItemReceiverProfile,
    code: str,
    *,
    trace_id: str,
) -> None:
    try:
        execute_item_command(
            command,
            profile,
            service_user="Administrator",
            trace_id=trace_id,
        )
    except ItemExecutionError as error:
        if error.code != code:
            raise
    else:
        raise RuntimeError(f"ERPNext Item {code} was not rejected.")


def _verify_api(
    *,
    project_id: str,
    node_id: str,
    line_id: str,
    engineering_id: str,
    item_group: str,
    stock_uom: str,
    erp_naming_series: str,
    suffix: str,
    business_actor: str,
) -> dict[str, bool]:
    if not frappe.db.exists("Role", SERVICE_ROLE):
        raise RuntimeError("ERPNext integration service role is unavailable.")
    actor = f"npi.connector.runtime.{suffix.casefold()}@example.invalid"
    api_key = uuid4().hex[:16]
    api_secret = uuid4().hex
    signing_secret = f"{api_key}:{api_secret}"
    user = frappe.get_doc(
        {
            "doctype": "User",
            "email": actor,
            "first_name": "NPI Connector Runtime",
            "enabled": 1,
            "user_type": "Website User",
            "send_welcome_email": 0,
            "api_key": api_key,
            "api_secret": api_secret,
            "roles": [{"role": SERVICE_ROLE}],
        }
    ).insert()
    user.add_roles(SERVICE_ROLE)
    frappe.clear_cache(user=actor)
    identity = frappe.db.get_value(
        "User",
        actor,
        ["enabled", "user_type"],
        as_dict=True,
    )
    if (
        not identity
        or identity.get("enabled") != 1
        or identity.get("user_type") != "Website User"
        or SERVICE_ROLE not in frappe.get_roles(actor)
    ):
        raise RuntimeError(
            "ERPNext integration service user setup failed: "
            f"identity={bool(identity)}, "
            f"enabled={identity.get('enabled') if identity else None}, "
            f"userType={identity.get('user_type') if identity else None}, "
            f"role={SERVICE_ROLE in frappe.get_roles(actor)}."
        )
    command = _command(
        project_id=project_id,
        node_id=node_id,
        line_id=line_id,
        engineering_id=engineering_id,
        actor_user_id=business_actor,
        description="NPI Connector signed API verification",
        stock_uom=stock_uom,
        intent="create_item",
        expected_mapping_version=0,
        expected_target_version=None,
    )
    body = canonical_json(command.raw).encode("utf-8")
    timestamp = str(int(time.time()))
    trace_id = f"runtime-api-{suffix}"
    headers = {
        "X-NPI-Timestamp": timestamp,
        "X-NPI-Signature": request_signature(
            signing_secret,
            ITEM_METHOD_PATH,
            timestamp,
            body,
        ),
        "X-NPI-Trace-ID": trace_id,
    }
    request = _Request(body, headers)
    previous_request = getattr(frappe.local, "request", _MISSING)
    config_keys = (
        "npi_erp_connector_disabled",
        "npi_erp_connector_item_profile",
    )
    previous_config = {key: frappe.conf.get(key, _MISSING) for key in config_keys}
    try:
        frappe.local.request = request
        frappe.set_user(actor)
        frappe.conf["npi_erp_connector_item_profile"] = {
            "itemGroup": item_group,
            "erpNamingSeries": erp_naming_series,
            "uomMap": {stock_uom: stock_uom},
            "attributeFieldMap": {},
            "ignoredAttributes": [],
        }
        frappe.conf["npi_erp_connector_disabled"] = True
        disabled = verify_response(publish_item(), signing_secret)
        if (
            disabled.get("httpStatus") != 403
            or disabled.get("errorCode") != "ITEM_PUBLISH_RECEIVER_DISABLED"
        ):
            raise RuntimeError("ERPNext Item default-disabled API verification failed.")
        request.headers["X-NPI-Signature"] = "0" * 64
        try:
            publish_item()
        except frappe.PermissionError:
            pass
        else:
            raise RuntimeError("ERPNext Item API accepted an invalid signature.")
        request.headers["X-NPI-Signature"] = headers["X-NPI-Signature"]
        frappe.conf["npi_erp_connector_disabled"] = False
        created = verify_response(publish_item(), signing_secret)
        if (
            created.get("httpStatus") != 200
            or created.get("exactReplay") is not False
            or not created.get("formalItemCode")
            or not created.get("targetVersion")
        ):
            raise RuntimeError("ERPNext Item signed API create verification failed.")
        if (
            frappe.db.get_value("Item", created["formalItemCode"], "owner")
            != business_actor
        ):
            raise RuntimeError("ERPNext Item signed API creator verification failed.")
        replayed = verify_response(publish_item(), signing_secret)
        if (
            replayed.get("httpStatus") != 200
            or replayed.get("exactReplay") is not True
            or replayed.get("formalItemCode") != created.get("formalItemCode")
            or replayed.get("targetVersion") != created.get("targetVersion")
        ):
            raise RuntimeError("ERPNext Item signed API replay verification failed.")
    finally:
        for key, value in previous_config.items():
            if value is _MISSING:
                frappe.conf.pop(key, None)
            else:
                frappe.conf[key] = value
        if previous_request is _MISSING:
            try:
                delattr(frappe.local, "request")
            except AttributeError:
                pass
        else:
            frappe.local.request = previous_request
        frappe.set_user("Administrator")
    return {
        "apiDefaultDisabled": True,
        "apiRejectsInvalidSignature": True,
        "apiSignedCreate": True,
        "apiSignedReplay": True,
        "apiSignedResponse": True,
    }


class _Request:
    content_type = "application/json; charset=utf-8"
    path = ITEM_METHOD_PATH

    def __init__(self, body: bytes, headers: dict[str, str]) -> None:
        self._body = body
        self.headers = dict(headers)

    def get_data(self, *, cache: bool, as_text: bool) -> bytes:
        if cache is not True or as_text is not False:
            raise RuntimeError("ERPNext Item API request reader changed.")
        return self._body


def _first_value(doctype: str, filters: dict[str, object]) -> str | None:
    values = frappe.get_all(
        doctype,
        filters=filters,
        pluck="name",
        order_by="name asc",
        limit_page_length=1,
    )
    return str(values[0]) if values else None


def _item_group() -> str:
    leaf = _first_value("Item Group", {"is_group": 0})
    if leaf is not None:
        return leaf
    root = _first_value("Item Group", {"is_group": 1})
    if root is None:
        root = "NPI Connector Runtime Root"
        frappe.get_doc(
            {
                "doctype": "Item Group",
                "item_group_name": root,
                "is_group": 1,
            }
        ).insert()
    leaf = "NPI Connector Runtime Items"
    frappe.get_doc(
        {
            "doctype": "Item Group",
            "item_group_name": leaf,
            "parent_item_group": root,
            "is_group": 0,
        }
    ).insert()
    return leaf


def _stock_uom() -> str:
    values = frappe.get_all(
        "UOM",
        filters={"enabled": 1},
        pluck="name",
        order_by="name asc",
        limit_page_length=100,
    )
    for candidate in values:
        value = str(candidate)
        if (
            1 <= len(value) <= 16
            and value[0].isalnum()
            and all(character.isalnum() or character in "._/-" for character in value)
        ):
            return value
    value = "NPI-Unit"
    frappe.get_doc(
        {
            "doctype": "UOM",
            "uom_name": value,
            "enabled": 1,
        }
    ).insert()
    return value


def _prepare_erp_item_naming() -> tuple[str, bool]:
    field = frappe.get_meta("Item").get_field("naming_series")
    options = str(getattr(field, "options", "") or "").splitlines()
    naming_series = next(
        (
            option.strip()
            for option in options
            if option.strip()
            and len(option.strip()) <= 140
            and all(
                character.isalnum() or character in "._:/#-"
                for character in option.strip()
            )
        ),
        None,
    )
    if naming_series is None:
        raise RuntimeError("ERPNext Item naming series is unavailable.")
    rules = frappe.get_all(
        "Document Naming Rule",
        filters={"document_type": "Item", "disabled": 0},
        pluck="name",
        limit_page_length=1,
    )
    if rules or frappe.db.get_default("item_naming_by") == "Naming Series":
        return naming_series, False
    frappe.db.set_default("item_naming_by", "Naming Series")
    return naming_series, True


def _counts() -> dict[str, int]:
    return {
        "items": frappe.db.count("Item"),
        "mappings": frappe.db.count("NPI ERP Item Mapping"),
        "receipts": frappe.db.count("NPI ERP Item Operation Receipt"),
        "users": frappe.db.count("User"),
    }


def _business_user(suffix: str) -> str:
    actor = f"npi.business.runtime.{suffix.casefold()}@example.invalid"
    frappe.get_doc(
        {
            "doctype": "User",
            "email": actor,
            "first_name": "NPI Business Runtime",
            "enabled": 1,
            "user_type": "System User",
            "send_welcome_email": 0,
            "roles": [{"role": "Desk User"}],
        }
    ).insert()
    return actor


def _major(value: str) -> int:
    try:
        return int(str(value).split(".", 1)[0])
    except (TypeError, ValueError) as error:
        raise RuntimeError("ERPNext test runtime version is invalid.") from error
