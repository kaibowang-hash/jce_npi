from __future__ import annotations

import time
from dataclasses import dataclass
from uuid import uuid4

import erpnext
import frappe

from npi_erpnext_connector import __version__ as connector_version
from npi_erpnext_connector.item_config import load_item_profile
from npi_erpnext_connector.item_contract import canonical_hash, canonical_json
from npi_erpnext_connector.item_frappe import execute_item_command
from npi_erpnext_connector.item_runtime_verifier import (
    _business_user,
    _item_group,
    _prepare_erp_item_naming,
    _stock_uom,
)
from npi_erpnext_connector.item_runtime_verifier import (
    _command as item_command,
)
from npi_erpnext_connector.mbom_api import SERVICE_ROLE, publish_mbom
from npi_erpnext_connector.mbom_config import load_mbom_profile
from npi_erpnext_connector.mbom_contract import (
    MBOM_METHOD_PATH,
    decode_mbom_command,
)
from npi_erpnext_connector.mbom_frappe import execute_mbom_command
from npi_erpnext_connector.receiver_security import (
    request_signature,
    verify_response,
)

ATTESTATION = "erpnext-test-mbom-rollback-v1"
_SAVEPOINT = "npi_erp_mbom_runtime_verifier"
_MISSING = object()


@dataclass(frozen=True, slots=True)
class _Context:
    tenant_id: str
    project_id: str
    ebom_id: str
    phase5_request_id: str
    publish_policy_id: str
    actor_user_id: str
    line_ids: dict[str, str]
    item_truth: dict[str, tuple[object, object]]


def run(attestation: str) -> dict[str, object]:
    if attestation != ATTESTATION:
        raise RuntimeError("ERPNext test MBOM runtime attestation is invalid.")
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
        suffix = uuid4().hex[:12].upper()
        business_actor = _business_user(f"MBOM{suffix}")
        company = _company(suffix)
        item_group = _item_group()
        stock_uom = _stock_uom()
        erp_naming_series, naming_default_changed = _prepare_erp_item_naming()
        project_id = str(uuid4())
        item_profile = load_item_profile(
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
        item_truth: dict[str, tuple[object, object]] = {}
        for key in ("ROOT", "SUB", "LEAF-A", "LEAF-B"):
            engineering_id = f"MBOM-{key}-{suffix}"
            command = item_command(
                project_id=project_id,
                node_id=str(uuid4()),
                line_id=str(uuid4()),
                engineering_id=engineering_id,
                actor_user_id=business_actor,
                description=f"MBOM rollback verification {key}",
                stock_uom=stock_uom,
                intent="create_item",
                expected_mapping_version=0,
                expected_target_version=None,
            )
            result = execute_item_command(
                command,
                item_profile,
                service_user="Administrator",
                trace_id=f"mbom-item-{suffix}-{key}",
            )
            item_truth[key] = (command, result)
        context = _Context(
            tenant_id="RUNTIME-VERIFY",
            project_id=project_id,
            ebom_id=str(uuid4()),
            phase5_request_id=str(uuid4()),
            publish_policy_id=str(uuid4()),
            actor_user_id=business_actor,
            line_ids={key: str(uuid4()) for key in item_truth},
            item_truth=item_truth,
        )
        mbom_profile = {"company": company}
        if frappe.get_meta("BOM").has_field("custom_temporary_bom"):
            mbom_profile["customTemporaryBomValue"] = "No"
        profile = load_mbom_profile(
            {
                "npi_erp_connector_mbom_disabled": False,
                "npi_erp_connector_mbom_profile": mbom_profile,
            }
        )
        created_command = _command(context, revision=1, quantity_a="2")
        created = execute_mbom_command(
            created_command,
            profile,
            service_user="Administrator",
            trace_id=f"mbom-runtime-{suffix}",
        )
        if created.exact_replay or any(
            node.http_status != 200 for node in created.nodes
        ):
            errors = ",".join(
                f"{node.stable_line_key}:{node.http_status}:{node.error_code or 'NONE'}"
                for node in created.nodes
            )
            raise RuntimeError(f"ERPNext MBOM create verification failed ({errors}).")
        if any(
            frappe.db.get_value("BOM", node.formal_bom_id, "owner") != business_actor
            for node in created.nodes
        ):
            raise RuntimeError("ERPNext MBOM creator verification failed.")
        replayed = execute_mbom_command(
            created_command,
            profile,
            service_user="Administrator",
            trace_id=f"mbom-runtime-{suffix}",
        )
        if not replayed.exact_replay or replayed.nodes != created.nodes:
            raise RuntimeError("ERPNext MBOM exact replay verification failed.")

        mappings = _mapping_expectations(context.project_id)
        updated_command = _command(
            context,
            revision=2,
            quantity_a="3",
            mappings=mappings,
        )
        updated = execute_mbom_command(
            updated_command,
            profile,
            service_user="Administrator",
            trace_id=f"mbom-runtime-{suffix}-update",
        )
        if any(
            node.http_status != 200 or node.mapping_version != 2
            for node in updated.nodes
        ):
            raise RuntimeError("ERPNext MBOM draft update verification failed.")

        mappings = _mapping_expectations(context.project_id)
        partial_command = _command(
            context,
            revision=3,
            quantity_a="4",
            mappings=mappings,
            stale_key="ROOT",
        )
        partial = execute_mbom_command(
            partial_command,
            profile,
            service_user="Administrator",
            trace_id=f"mbom-runtime-{suffix}-partial",
        )
        if (
            partial.nodes[0].http_status != 409
            or partial.nodes[0].error_code != "MBOM_PUBLISH_STALE_MAPPING"
            or partial.nodes[1].http_status != 200
            or partial.nodes[1].mapping_version != 3
        ):
            raise RuntimeError("ERPNext MBOM partial-result verification failed.")
        partial_replay = execute_mbom_command(
            partial_command,
            profile,
            service_user="Administrator",
            trace_id=f"mbom-runtime-{suffix}-partial-replay",
        )
        if not partial_replay.exact_replay or partial_replay.nodes != partial.nodes:
            raise RuntimeError("ERPNext MBOM partial replay verification failed.")

        mappings = _mapping_expectations(context.project_id)
        root_bom = str(mappings["ROOT"]["formalBomId"])
        frappe.get_doc("BOM", root_bom).db_set("docstatus", 1, update_modified=False)
        submitted_command = _command(
            context,
            revision=4,
            quantity_a="5",
            mappings=mappings,
        )
        submitted = execute_mbom_command(
            submitted_command,
            profile,
            service_user="Administrator",
            trace_id=f"mbom-runtime-{suffix}-submitted",
        )
        if (
            submitted.nodes[0].target_submission_state != "submitted_immutable"
            or submitted.nodes[0].mapping_version != 2
            or submitted.nodes[1].http_status != 200
            or submitted.nodes[1].mapping_version != 4
        ):
            raise RuntimeError("ERPNext submitted BOM protection verification failed.")

        api = _verify_api(created_command, company, suffix)
        during = _counts()
        expected = {
            **baseline,
            "items": baseline["items"] + 4,
            "itemMappings": baseline["itemMappings"] + 4,
            "itemReceipts": baseline["itemReceipts"] + 4,
            "boms": baseline["boms"] + 2,
            "mbomMappings": baseline["mbomMappings"] + 2,
            "mbomReceipts": baseline["mbomReceipts"] + 4,
            "users": baseline["users"] + 2,
        }
        if during != expected:
            raise RuntimeError("ERPNext MBOM runtime write set is invalid.")
    finally:
        frappe.db.rollback(save_point=_SAVEPOINT)
        if naming_default_changed:
            frappe.clear_cache()
        frappe.set_user(previous_user)
    if _counts() != baseline:
        raise RuntimeError("ERPNext MBOM runtime rollback verification failed.")
    return {
        "status": "PASS",
        "connectorVersion": connector_version,
        "frappeMajor": frappe_major,
        "erpnextMajor": erpnext_major,
        "createDraft": True,
        "businessCreatorAttribution": True,
        "exactReplay": True,
        "updateDraft": True,
        "partialResult": True,
        "partialReplay": True,
        "submittedProtection": True,
        **api,
        "rollback": True,
    }


def _command(
    context: _Context,
    *,
    revision: int,
    quantity_a: str,
    mappings: dict[str, dict[str, object]] | None = None,
    stale_key: str | None = None,
):
    line_definitions = {
        "LEAF-A": ("SUB", "LEAF-A", quantity_a, "component_only"),
        "LEAF-B": ("ROOT", "LEAF-B", "1", "component_only"),
        "ROOT": (None, "ROOT", "1", "assembly"),
        "SUB": ("ROOT", "SUB", "1", "assembly"),
    }
    stock_uom = _stock_uom()
    lines = []
    for key in sorted(line_definitions):
        parent, item_key, quantity, role = line_definitions[key]
        item_command_value, _result = context.item_truth[item_key]
        line_core = {
            "lineGlobalId": context.line_ids[key],
            "stableLineKey": key,
            "parentLineKey": parent,
            "engineeringItemId": item_command_value.engineering_item_id,
            "quantity": quantity,
            "engineeringUom": stock_uom,
            "alternates": [],
            "effectivity": {},
            "attributes": {},
            "sourceRole": role,
        }
        lines.append(
            {
                **line_core,
                "lineHash": canonical_hash({"revision": revision, "line": line_core}),
            }
        )
    topology = {
        "revisionGlobalId": str(uuid4()),
        "revisionNumber": revision,
        "revisionSnapshotHash": canonical_hash({"revision": revision, "lines": lines}),
        "lines": lines,
    }
    release_id = str(uuid4())
    source_payload = {
        "schemaVersion": 2,
        "tenantId": context.tenant_id,
        "projectGlobalId": context.project_id,
        "ebomGlobalId": context.ebom_id,
        "phase5PublishRequestGlobalId": context.phase5_request_id,
        "phase5PublishRequestPayloadHash": canonical_hash(
            {"phase5": context.phase5_request_id}
        ),
        "publishPolicyGlobalId": context.publish_policy_id,
        "publishPolicyVersion": 1,
        "publishPolicySnapshotHash": canonical_hash(
            {"policy": context.publish_policy_id}
        ),
        "lifecycleVersion": revision,
        "releaseEventGlobalId": release_id,
        "releaseEventHash": canonical_hash({"release": release_id}),
        "approvalEvidenceIds": [release_id],
        "releasedAt": f"2026-09-05T10:{revision:02d}:00Z",
        "topology": topology,
    }
    source_hash = canonical_hash(source_payload)
    topology_hash = canonical_hash(topology)
    source_stream_key_hash = canonical_hash(
        {
            "schemaVersion": 2,
            "tenantId": context.tenant_id,
            "projectGlobalId": context.project_id,
            "ebomGlobalId": context.ebom_id,
        }
    )
    source = {
        **source_payload,
        "sourceStreamKeyHash": source_stream_key_hash,
        "topologyHash": topology_hash,
        "sourceHash": source_hash,
    }
    readiness = []
    for key in sorted(context.item_truth):
        item_command_value, result = context.item_truth[key]
        readiness.append(
            {
                "engineeringItemId": item_command_value.engineering_item_id,
                "disposition": "advanced",
                "itemStreamKeyHash": item_command_value.source_stream_key_hash,
                "mappingVersion": result.mapping_version,
                "formalItemCode": result.formal_item_code,
                "targetVersion": result.target_version,
                "observationHash": canonical_hash(
                    {"item": result.formal_item_code, "version": result.target_version}
                ),
                "authority": "authoritative_sandbox",
                "responseAuthenticated": True,
                "syntheticItemReference": None,
            }
        )
    readiness.sort(key=lambda value: value["engineeringItemId"])
    item_set_hash = canonical_hash(
        {"sourceHash": source_hash, "targetMode": "sandbox", "items": readiness}
    )
    expectations = []
    for key in ("ROOT", "SUB"):
        assembly_key = canonical_hash(
            {
                "schemaVersion": 2,
                "tenantId": context.tenant_id,
                "projectGlobalId": context.project_id,
                "ebomGlobalId": context.ebom_id,
                "stableLineKey": key,
            }
        )
        current = mappings.get(key) if mappings else None
        version = int(current["mappingVersion"]) if current else 0
        if key == stale_key:
            version -= 1
        expectations.append(
            {
                "assemblySourceKey": assembly_key,
                "stableLineKey": key,
                "mappingVersion": version,
                "submissionState": "editable_draft" if current else "unmapped_create",
                "intent": "update_draft" if current else "create_draft",
                "formalBomId": current["formalBomId"] if current else None,
                "targetVersion": current["targetVersion"] if current else None,
                "observationHash": (
                    canonical_hash({"mapping": current}) if current else None
                ),
            }
        )
    mbom_set_hash = canonical_hash(
        {
            "sourceHash": source_hash,
            "topologyHash": topology_hash,
            "assemblies": expectations,
        }
    )
    profile = {
        "profileId": "mbom-runtime-sandbox-v1",
        "profileVersion": 1,
        "targetMode": "sandbox",
        "environmentCode": "test",
        "projectionPolicyId": "mbom-material-only-v1",
        "projectionPolicyVersion": 1,
        "projectionPolicyHash": "7" * 64,
        "snapshotHash": "8" * 64,
    }
    semantic_effect = canonical_hash(
        {
            "schemaVersion": 2,
            "operation": "publish_released_mbom",
            "sourceStreamKeyHash": source_stream_key_hash,
            "sourceHash": source_hash,
            "topologyHash": topology_hash,
            "itemMappingSetHash": item_set_hash,
            "mbomMappingSetHash": mbom_set_hash,
            "profile": profile,
        }
    )
    target_key = canonical_hash(
        {"operation": "publish_released_mbom", "semanticEffectHash": semantic_effect}
    )
    request_id = str(uuid4())
    request = {
        "schemaVersion": 2,
        "apiVersion": "npi.erp-mbom-publish.v1",
        "operation": "publish_released_mbom",
        "globalId": request_id,
        "source": source,
        "itemReadiness": readiness,
        "itemMappingSetHash": item_set_hash,
        "mbomExpectations": expectations,
        "mbomMappingSetHash": mbom_set_hash,
        "profile": profile,
        "actorUserId": context.actor_user_id,
        "serviceActorUserId": "runtime.worker@example.invalid",
        "requestId": str(uuid4()),
        "traceId": f"mbom-runtime-revision-{revision}",
        "idempotencyKeyHash": canonical_hash(
            {"request": request_id, "revision": revision}
        ),
        "targetIdempotencyKeyHash": target_key,
        "semanticEffectHash": semantic_effect,
        "state": "queued",
        "dispatchAllowed": True,
        "createdAt": f"2026-09-05T10:{revision:02d}:30Z",
    }
    readiness_by_item = {value["engineeringItemId"]: value for value in readiness}
    lines_by_key = {value["stableLineKey"]: value for value in lines}
    expectations_by_key = {value["stableLineKey"]: value for value in expectations}
    nodes = [
        {
            "line": lines_by_key[key],
            "itemReadiness": readiness_by_item[lines_by_key[key]["engineeringItemId"]],
            "mbomExpectation": expectations_by_key[key],
        }
        for key in ("ROOT", "SUB")
    ]
    manifest = [
        {
            "globalId": str(uuid4()),
            "stableLineKey": value["line"]["stableLineKey"],
            "nodeSnapshotHash": canonical_hash(value),
        }
        for value in nodes
    ]
    raw = {
        "contractVersion": 1,
        "operation": "publish_released_mbom",
        "requestGlobalId": request_id,
        "attemptGlobalId": str(uuid4()),
        "attemptNumber": 1,
        "targetIdempotencyKeyHash": target_key,
        "sourceHash": source_hash,
        "topologyHash": topology_hash,
        "itemMappingSetHash": item_set_hash,
        "mbomMappingSetHash": mbom_set_hash,
        "nodeManifestHash": canonical_hash(
            {"requestGlobalId": request_id, "nodes": manifest}
        ),
        "request": request,
        "nodes": nodes,
    }
    return decode_mbom_command(canonical_json(raw).encode("utf-8"))


def _mapping_expectations(project_global_id: str) -> dict[str, dict[str, object]]:
    values = frappe.get_all(
        "NPI ERP MBOM Mapping",
        fields=[
            "stable_line_key",
            "mapping_version",
            "formal_bom_id",
            "target_version",
        ],
        filters={"project_global_id": project_global_id},
        order_by="stable_line_key asc",
        limit_page_length=10,
    )
    result = {
        str(value.stable_line_key): {
            "mappingVersion": int(value.mapping_version),
            "formalBomId": str(value.formal_bom_id),
            "targetVersion": str(value.target_version),
        }
        for value in values
        if str(value.stable_line_key) in {"ROOT", "SUB"}
    }
    if set(result) != {"ROOT", "SUB"}:
        raise RuntimeError("ERPNext MBOM runtime mappings are unavailable.")
    return result


def _verify_api(command: object, company: str, suffix: str) -> dict[str, bool]:
    if not frappe.db.exists("Role", SERVICE_ROLE):
        raise RuntimeError("ERPNext MBOM integration service role is unavailable.")
    actor = f"npi.mbom.runtime.{suffix.casefold()}@example.invalid"
    api_key = uuid4().hex[:16]
    api_secret = uuid4().hex
    signing_secret = f"{api_key}:{api_secret}"
    user = frappe.get_doc(
        {
            "doctype": "User",
            "email": actor,
            "first_name": "NPI MBOM Runtime",
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
    body = canonical_json(command.raw).encode("utf-8")
    timestamp = str(int(time.time()))
    headers = {
        "X-NPI-Timestamp": timestamp,
        "X-NPI-Signature": request_signature(
            signing_secret, MBOM_METHOD_PATH, timestamp, body
        ),
        "X-NPI-Trace-ID": f"mbom-api-{suffix}",
    }
    request = _Request(body, headers)
    previous_request = getattr(frappe.local, "request", _MISSING)
    keys = ("npi_erp_connector_mbom_disabled", "npi_erp_connector_mbom_profile")
    previous_config = {key: frappe.conf.get(key, _MISSING) for key in keys}
    try:
        frappe.local.request = request
        frappe.set_user(actor)
        profile = {"company": company}
        if frappe.get_meta("BOM").has_field("custom_temporary_bom"):
            profile["customTemporaryBomValue"] = "No"
        frappe.conf["npi_erp_connector_mbom_profile"] = profile
        frappe.conf["npi_erp_connector_mbom_disabled"] = True
        disabled = verify_response(publish_mbom(), signing_secret)
        if disabled["nodes"][0]["errorCode"] != "MBOM_PUBLISH_RECEIVER_DISABLED":
            raise RuntimeError("ERPNext MBOM default-disabled API verification failed.")
        request.headers["X-NPI-Signature"] = "0" * 64
        try:
            publish_mbom()
        except frappe.PermissionError:
            pass
        else:
            raise RuntimeError("ERPNext MBOM API accepted an invalid signature.")
        request.headers["X-NPI-Signature"] = headers["X-NPI-Signature"]
        frappe.conf["npi_erp_connector_mbom_disabled"] = False
        replay = verify_response(publish_mbom(), signing_secret)
        if (
            replay.get("requestGlobalId") != command.request_global_id
            or not all(node.get("exactReplay") is True for node in replay["nodes"])
            or not all(node.get("formalBomId") for node in replay["nodes"])
        ):
            raise RuntimeError("ERPNext MBOM signed API replay verification failed.")
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
        "apiSignedReplay": True,
        "apiSignedResponse": True,
    }


class _Request:
    content_type = "application/json; charset=utf-8"
    path = MBOM_METHOD_PATH

    def __init__(self, body: bytes, headers: dict[str, str]) -> None:
        self._body = body
        self.headers = dict(headers)

    def get_data(self, *, cache: bool, as_text: bool) -> bytes:
        if cache is not True or as_text is not False:
            raise RuntimeError("ERPNext MBOM API request reader changed.")
        return self._body


def _company(suffix: str) -> str:
    values = frappe.get_all(
        "Company",
        fields=["name", "default_currency"],
        order_by="name asc",
        limit_page_length=100,
    )
    for value in values:
        if value.default_currency:
            return str(value.name)
    currencies = frappe.get_all(
        "Currency",
        filters={"enabled": 1},
        pluck="name",
        order_by="name asc",
        limit_page_length=1,
    )
    countries = frappe.get_all(
        "Country",
        pluck="name",
        order_by="name asc",
        limit_page_length=1,
    )
    if not currencies or not countries:
        raise RuntimeError("ERPNext test Company prerequisites are unavailable.")
    if not frappe.db.exists("Warehouse Type", "Transit"):
        frappe.get_doc(
            {
                "doctype": "Warehouse Type",
                "name": "Transit",
                "description": "Disposable MBOM runtime prerequisite",
            }
        ).insert()
    company_name = f"NPI Connector Runtime {suffix}"
    company = frappe.get_doc(
        {
            "doctype": "Company",
            "company_name": company_name,
            "abbr": f"N{suffix[:4]}",
            "default_currency": str(currencies[0]),
            "country": str(countries[0]),
        }
    ).insert()
    return str(company.name)


def _counts() -> dict[str, int]:
    return {
        "items": frappe.db.count("Item"),
        "itemMappings": frappe.db.count("NPI ERP Item Mapping"),
        "itemReceipts": frappe.db.count("NPI ERP Item Operation Receipt"),
        "boms": frappe.db.count("BOM"),
        "mbomMappings": frappe.db.count("NPI ERP MBOM Mapping"),
        "mbomReceipts": frappe.db.count("NPI ERP MBOM Operation Receipt"),
        "users": frappe.db.count("User"),
    }


def _major(value: str) -> int:
    try:
        return int(str(value).split(".", 1)[0])
    except (TypeError, ValueError) as error:
        raise RuntimeError("ERPNext test runtime version is invalid.") from error
