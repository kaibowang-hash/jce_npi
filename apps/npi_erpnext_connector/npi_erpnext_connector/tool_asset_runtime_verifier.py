from __future__ import annotations

import time
from uuid import uuid4

import erpnext
import frappe

from npi_erpnext_connector import __version__ as connector_version
from npi_erpnext_connector.item_contract import canonical_hash, canonical_json
from npi_erpnext_connector.item_runtime_verifier import (
    _business_user,
    _item_group,
    _stock_uom,
)
from npi_erpnext_connector.mbom_runtime_verifier import _company
from npi_erpnext_connector.receiver_security import (
    request_signature,
    verify_response,
)
from npi_erpnext_connector.tool_asset_api import (
    SERVICE_ROLE,
    upsert_npi_tool_asset_v1,
)
from npi_erpnext_connector.tool_asset_config import load_tool_asset_profile
from npi_erpnext_connector.tool_asset_contract import (
    CREATE_OPERATION,
    OWNED_FIELDS,
    TOOL_ASSET_METHOD_PATH,
    UPDATE_OPERATION,
    decode_tool_asset_command,
)
from npi_erpnext_connector.tool_asset_frappe import (
    ToolAssetExecutionError,
    execute_tool_asset_command,
)

ATTESTATION = "erpnext-test-tool-asset-rollback-v1"
_SAVEPOINT = "npi_erp_tool_asset_runtime_verifier"
_MISSING = object()


def run(attestation: str) -> dict[str, object]:
    if attestation != ATTESTATION:
        raise RuntimeError("ERPNext test Tool Asset runtime attestation is invalid.")
    frappe_major = _major(frappe.__version__)
    erpnext_major = _major(erpnext.__version__)
    if frappe_major not in {15, 16} or erpnext_major not in {15, 16}:
        raise RuntimeError("ERPNext test runtime version is unsupported.")
    baseline = _counts()
    previous_user = str(getattr(frappe.session, "user", "") or "Guest")
    frappe.db.savepoint(_SAVEPOINT)
    try:
        frappe.set_user("Administrator")
        suffix = uuid4().hex[:12].upper()
        business_actor = _business_user(f"TOOL{suffix}")
        company = _company(suffix)
        profile_values = _target_profile(company, suffix)
        prepared = _counts()
        profile = load_tool_asset_profile(
            {
                "npi_erp_connector_tool_asset_profile": profile_values,
            }
        )
        context = {
            "tenantId": "RUNTIME-VERIFY",
            "projectGlobalId": str(uuid4()),
            "toolingMasterGlobalId": str(uuid4()),
            "toolingSetGlobalId": str(uuid4()),
            "setRevisionBindingGlobalId": str(uuid4()),
            "toolingRevisionGlobalId": str(uuid4()),
            "acceptanceRevisionGlobalId": str(uuid4()),
            "acceptanceGlobalId": str(uuid4()),
            "suffix": suffix,
            "actorUserId": business_actor,
        }
        created_command = _command(context, CREATE_OPERATION, revision=1)
        created = execute_tool_asset_command(
            created_command,
            profile,
            service_user="Administrator",
            trace_id=f"tool-asset-runtime-{suffix}",
        )
        if (
            created.http_status != 200
            or created.exact_replay
            or not created.formal_asset_id
            or created.mapping_version != 1
        ):
            raise RuntimeError("ERPNext Tool Asset create verification failed.")
        if (
            frappe.db.get_value("Asset", created.formal_asset_id, "owner")
            != business_actor
        ):
            raise RuntimeError("ERPNext Tool Asset creator verification failed.")
        replayed = execute_tool_asset_command(
            created_command,
            profile,
            service_user="Administrator",
            trace_id=f"tool-asset-runtime-{suffix}",
        )
        if not replayed.exact_replay or replayed.mapping() != created.mapping():
            raise RuntimeError("ERPNext Tool Asset exact replay verification failed.")

        mapping = _mapping(context["toolingSetGlobalId"])
        updated_command = _command(
            context,
            UPDATE_OPERATION,
            revision=2,
            mapping=mapping,
        )
        updated = execute_tool_asset_command(
            updated_command,
            profile,
            service_user="Administrator",
            trace_id=f"tool-asset-runtime-{suffix}-update",
        )
        if (
            updated.http_status != 200
            or updated.mapping_version != 2
            or updated.formal_asset_id != created.formal_asset_id
        ):
            raise RuntimeError("ERPNext Tool Asset update verification failed.")

        mapping = _mapping(context["toolingSetGlobalId"])
        stale = {**mapping, "mappingVersion": int(mapping["mappingVersion"]) - 1}
        _expect_error(
            _command(context, UPDATE_OPERATION, revision=3, mapping=stale),
            profile,
            "TOOL_ASSET_STALE_MAPPING",
        )

        asset = frappe.get_doc("Asset", str(mapping["formalAssetId"]))
        asset.db_set("docstatus", 1, update_modified=False)
        _expect_error(
            _command(context, UPDATE_OPERATION, revision=4, mapping=mapping),
            profile,
            "TOOL_ASSET_TARGET_PROTECTED",
        )

        api = _verify_api(profile_values, suffix, business_actor)
        during = _counts()
        expected = {
            **prepared,
            "assets": prepared["assets"] + 2,
            "assetActivities": prepared["assetActivities"] + 2,
            "mappings": prepared["mappings"] + 2,
            "receipts": prepared["receipts"] + 3,
            "users": prepared["users"] + 1,
        }
        if during != expected:
            raise RuntimeError(
                "ERPNext Tool Asset runtime write set is invalid: "
                f"expected={expected}, observed={during}."
            )
    finally:
        frappe.db.rollback(save_point=_SAVEPOINT)
        frappe.set_user(previous_user)
    if _counts() != baseline:
        raise RuntimeError("ERPNext Tool Asset runtime rollback verification failed.")
    return {
        "status": "PASS",
        "connectorVersion": connector_version,
        "frappeMajor": frappe_major,
        "erpnextMajor": erpnext_major,
        "createDraft": True,
        "businessCreatorAttribution": True,
        "exactReplay": True,
        "updateDraft": True,
        "staleMappingRejected": True,
        "submittedProtection": True,
        **api,
        "rollback": True,
    }


def _command(
    context: dict[str, str],
    operation: str,
    *,
    revision: int,
    mapping: dict[str, object] | None = None,
):
    source_payload = {
        "schemaVersion": 2,
        "tenantId": context["tenantId"],
        "projectGlobalId": context["projectGlobalId"],
        "toolingMasterGlobalId": context["toolingMasterGlobalId"],
        "toolingMasterTitle": f"NPI Tool Asset Runtime {revision}",
        "toolingMasterSnapshotHash": canonical_hash(
            {"master": context["toolingMasterGlobalId"], "revision": revision}
        ),
        "toolingSetGlobalId": context["toolingSetGlobalId"],
        "toolingSetPhysicalSerial": f"SET-{context['suffix']}",
        "toolingSetSnapshotHash": canonical_hash(
            {"set": context["toolingSetGlobalId"], "revision": revision}
        ),
        "toolingRequirementKind": "new_tool",
        "setRevisionBindingGlobalId": context["setRevisionBindingGlobalId"],
        "setRevisionBindingSnapshotHash": canonical_hash(
            {"binding": context["setRevisionBindingGlobalId"], "revision": revision}
        ),
        "toolingRevisionGlobalId": context["toolingRevisionGlobalId"],
        "toolingRevisionNumber": revision,
        "toolingRevisionLabel": f"R{revision}",
        "toolingRevisionSnapshotHash": canonical_hash(
            {"tooling": context["toolingRevisionGlobalId"], "revision": revision}
        ),
        "acceptanceRevisionGlobalId": context["acceptanceRevisionGlobalId"],
        "acceptanceGlobalId": context["acceptanceGlobalId"],
        "acceptanceVersion": 1,
        "acceptancePredecessorGlobalId": None,
        "acceptancePredecessorSnapshotHash": None,
        "acceptanceSnapshotHash": canonical_hash(
            {"acceptance": context["acceptanceGlobalId"], "revision": revision}
        ),
        "acceptedAt": "2026-09-05T10:00:00Z",
        "ownedFieldsManifest": list(OWNED_FIELDS),
    }
    stream_hash = canonical_hash(
        {
            "schemaVersion": 2,
            "tenantId": context["tenantId"],
            "projectGlobalId": context["projectGlobalId"],
            "toolingSetGlobalId": context["toolingSetGlobalId"],
        }
    )
    source_hash = canonical_hash(source_payload)
    source = {
        **source_payload,
        "sourceStreamKeyHash": stream_hash,
        "sourceHash": source_hash,
    }
    if operation == CREATE_OPERATION:
        expectation = {
            "operation": operation,
            "sourceStreamKeyHash": stream_hash,
            "mappingVersion": 0,
            "formalAssetId": None,
            "targetVersion": None,
            "observationHash": None,
        }
    else:
        if mapping is None:
            raise RuntimeError("ERPNext Tool Asset runtime mapping is unavailable.")
        expectation = {
            "operation": operation,
            "sourceStreamKeyHash": stream_hash,
            "mappingVersion": mapping["mappingVersion"],
            "formalAssetId": mapping["formalAssetId"],
            "targetVersion": mapping["targetVersion"],
            "observationHash": canonical_hash({"mapping": mapping}),
        }
    approval = {
        "state": "verified",
        "policyId": "tool-asset-runtime-policy-v1",
        "policyVersion": 1,
        "policyHash": "7" * 64,
        "evidenceReference": "tool-asset-runtime-approval",
        "evidenceHash": "8" * 64,
    }
    profile = {
        "profileId": "tool-asset-runtime-sandbox-v1",
        "profileVersion": 1,
        "targetMode": "sandbox",
        "environmentCode": "test",
        "projectionPolicyId": "tool-asset-asset-draft-v1",
        "projectionPolicyVersion": 1,
        "projectionPolicyHash": "9" * 64,
        "snapshotHash": "a" * 64,
    }
    request_id = str(uuid4())
    request = {
        "schemaVersion": 2,
        "apiVersion": "npi.erp-tool-asset.v1",
        "globalId": request_id,
        "operation": operation,
        "tenantId": context["tenantId"],
        "projectGlobalId": context["projectGlobalId"],
        "source": source,
        "approval": approval,
        "mappingExpectation": expectation,
        "profile": profile,
        "state": "queued",
        "actorUserId": context["actorUserId"],
        "requestId": str(uuid4()),
        "traceId": f"tool-asset-runtime-{revision}",
        "idempotencyKeyHash": canonical_hash(
            {"request": request_id, "operation": operation}
        ),
        "payloadHash": "",
        "optimisticVersion": 1,
        "createdAt": f"2026-09-05T10:{revision:02d}:00Z",
    }
    request["payloadHash"] = canonical_hash(
        {
            "schemaVersion": 2,
            "apiVersion": "npi.erp-tool-asset.v1",
            "operation": operation,
            "source": source,
            "approval": approval,
            "mappingExpectation": expectation,
            "profile": profile,
        }
    )
    target_key = canonical_hash(
        {
            "operation": operation,
            "sourceHash": source_hash,
            "mappingExpectation": expectation,
            "profile": profile,
        }
    )
    raw = {
        "contractVersion": 1,
        "operation": operation,
        "requestGlobalId": request_id,
        "attemptGlobalId": str(uuid4()),
        "attemptNumber": 1,
        "targetIdempotencyKeyHash": target_key,
        "sourceHash": source_hash,
        "mappingExpectation": expectation,
        "request": request,
        "ownedFieldsManifest": list(OWNED_FIELDS),
    }
    return decode_tool_asset_command(canonical_json(raw).encode("utf-8"))


def _mapping(tooling_set_global_id: str) -> dict[str, object]:
    value = frappe.db.get_value(
        "NPI ERP Tool Asset Mapping",
        {"tooling_set_global_id": tooling_set_global_id},
        ["mapping_version", "formal_asset_id", "target_version"],
        as_dict=True,
    )
    if not value:
        raise RuntimeError("ERPNext Tool Asset runtime mapping is unavailable.")
    return {
        "mappingVersion": int(value.mapping_version),
        "formalAssetId": str(value.formal_asset_id),
        "targetVersion": str(value.target_version),
    }


def _expect_error(command: object, profile: object, code: str) -> None:
    try:
        execute_tool_asset_command(
            command,
            profile,
            service_user="Administrator",
            trace_id=f"tool-asset-error-{uuid4().hex[:12]}",
        )
    except ToolAssetExecutionError as error:
        if error.code != code:
            raise
    else:
        raise RuntimeError(f"ERPNext Tool Asset {code} was not rejected.")


def _target_profile(company: str, suffix: str) -> dict[str, str]:
    fixed_accounts = frappe.get_all(
        "Account",
        filters={
            "company": company,
            "account_type": "Fixed Asset",
            "is_group": 0,
            "disabled": 0,
        },
        pluck="name",
        order_by="name asc",
        limit_page_length=1,
    )
    if not fixed_accounts:
        raise RuntimeError("ERPNext test fixed-asset account is unavailable.")
    category = frappe.get_doc(
        {
            "doctype": "Asset Category",
            "asset_category_name": f"NPI Runtime {suffix}",
            "non_depreciable_category": 1,
            "accounts": [
                {
                    "company_name": company,
                    "fixed_asset_account": str(fixed_accounts[0]),
                }
            ],
        }
    ).insert()
    location = frappe.get_doc(
        {
            "doctype": "Location",
            "location_name": f"NPI Runtime {suffix}",
        }
    ).insert()
    item_code = f"NPI-ASSET-VERIFY-{suffix}"
    item = frappe.get_doc(
        {
            "doctype": "Item",
            "item_code": item_code,
            "item_name": item_code,
            "item_group": _item_group(),
            "stock_uom": _stock_uom(),
            "is_stock_item": 0,
            "is_fixed_asset": 1,
            "asset_category": category.name,
        }
    ).insert()
    return {
        "company": company,
        "location": str(location.name),
        "itemCode": str(item.name),
        "purchaseDateSource": "acceptedAt",
        "purchaseAmount": "1",
    }


def _verify_api(
    profile: dict[str, str],
    suffix: str,
    business_actor: str,
) -> dict[str, bool]:
    if not frappe.db.exists("Role", SERVICE_ROLE):
        raise RuntimeError("ERPNext Tool Asset service role is unavailable.")
    actor = f"npi.tool.asset.runtime.{suffix.casefold()}@example.invalid"
    api_key = uuid4().hex[:16]
    api_secret = uuid4().hex
    signing_secret = f"{api_key}:{api_secret}"
    user = frappe.get_doc(
        {
            "doctype": "User",
            "email": actor,
            "first_name": "NPI Tool Asset Runtime",
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
    context = {
        "tenantId": "RUNTIME-VERIFY-API",
        "projectGlobalId": str(uuid4()),
        "toolingMasterGlobalId": str(uuid4()),
        "toolingSetGlobalId": str(uuid4()),
        "setRevisionBindingGlobalId": str(uuid4()),
        "toolingRevisionGlobalId": str(uuid4()),
        "acceptanceRevisionGlobalId": str(uuid4()),
        "acceptanceGlobalId": str(uuid4()),
        "suffix": f"API{suffix[:8]}",
        "actorUserId": business_actor,
    }
    command = _command(context, CREATE_OPERATION, revision=1)
    body = canonical_json(command.raw).encode("utf-8")
    timestamp = str(int(time.time()))
    headers = {
        "X-NPI-Timestamp": timestamp,
        "X-NPI-Signature": request_signature(
            signing_secret,
            TOOL_ASSET_METHOD_PATH,
            timestamp,
            body,
        ),
        "X-NPI-Trace-ID": f"tool-asset-api-{suffix}",
    }
    request = _Request(body, headers)
    previous_request = getattr(frappe.local, "request", _MISSING)
    keys = (
        "npi_erp_connector_tool_asset_create_disabled",
        "npi_erp_connector_tool_asset_update_disabled",
        "npi_erp_connector_tool_asset_profile",
    )
    previous_config = {key: frappe.conf.get(key, _MISSING) for key in keys}
    try:
        frappe.local.request = request
        frappe.set_user(actor)
        frappe.conf["npi_erp_connector_tool_asset_profile"] = profile
        frappe.conf["npi_erp_connector_tool_asset_create_disabled"] = True
        frappe.conf["npi_erp_connector_tool_asset_update_disabled"] = True
        disabled = verify_response(upsert_npi_tool_asset_v1(), signing_secret)
        if disabled.get("errorCode") != "TOOL_ASSET_RECEIVER_DISABLED":
            raise RuntimeError("ERPNext Tool Asset default-disabled API failed.")
        request.headers["X-NPI-Signature"] = "0" * 64
        try:
            upsert_npi_tool_asset_v1()
        except frappe.PermissionError:
            pass
        else:
            raise RuntimeError("ERPNext Tool Asset API accepted an invalid signature.")
        request.headers["X-NPI-Signature"] = headers["X-NPI-Signature"]
        frappe.conf["npi_erp_connector_tool_asset_create_disabled"] = False
        created = verify_response(upsert_npi_tool_asset_v1(), signing_secret)
        replayed = verify_response(upsert_npi_tool_asset_v1(), signing_secret)
        if (
            created.get("httpStatus") != 200
            or created.get("exactReplay") is not False
            or not created.get("formalAssetId")
            or replayed.get("exactReplay") is not True
            or replayed.get("formalAssetId") != created.get("formalAssetId")
            or not all(
                field.get("httpStatus") == 200 for field in replayed.get("fields", [])
            )
        ):
            raise RuntimeError("ERPNext Tool Asset signed API verification failed.")
        if (
            frappe.db.get_value("Asset", created["formalAssetId"], "owner")
            != business_actor
        ):
            raise RuntimeError("ERPNext Tool Asset API creator verification failed.")
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
    path = TOOL_ASSET_METHOD_PATH

    def __init__(self, body: bytes, headers: dict[str, str]) -> None:
        self._body = body
        self.headers = dict(headers)

    def get_data(self, *, cache: bool, as_text: bool) -> bytes:
        if cache is not True or as_text is not False:
            raise RuntimeError("ERPNext Tool Asset API request reader changed.")
        return self._body


def _counts() -> dict[str, int]:
    return {
        "companies": frappe.db.count("Company"),
        "assetCategories": frappe.db.count("Asset Category"),
        "locations": frappe.db.count("Location"),
        "items": frappe.db.count("Item"),
        "assets": frappe.db.count("Asset"),
        "assetActivities": frappe.db.count("Asset Activity"),
        "mappings": frappe.db.count("NPI ERP Tool Asset Mapping"),
        "receipts": frappe.db.count("NPI ERP Tool Asset Operation Receipt"),
        "users": frappe.db.count("User"),
    }


def _major(value: str) -> int:
    try:
        return int(str(value).split(".", 1)[0])
    except (TypeError, ValueError) as error:
        raise RuntimeError("ERPNext test runtime version is invalid.") from error
