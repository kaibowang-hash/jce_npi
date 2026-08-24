from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path
from typing import Any
from uuid import UUID

import verify_document_runtime as document_runtime
import verify_item_publish_runtime as item_runtime
import verify_tooling_engineering_controls_runtime as predecessor
from verify_frappe_runtime import (
    delete_disposable_user,
    login,
    require,
    secret_from_environment,
    validate_local_fixture_inputs,
    validate_problem,
)
from verify_project_runtime import (
    bootstrap_csrf,
    delete_resource,
    get_resource,
    update_resource,
)


ROOT = Path(__file__).resolve().parents[1]
BENCH_PATH = ROOT / "tmp" / "frappe-bench"
SITE_NAME = document_runtime.SITE_NAME
RUNTIME_MARKER = document_runtime.RUNTIME_MARKER
FIXTURE_RUN_ID = document_runtime.FIXTURE_RUN_ID
TENANT_ID = document_runtime.TENANT_ID
ACTOR_USER = predecessor.ACTOR_USER
UNRELATED_USER = (
    f"npi-tooling-acceptance-{FIXTURE_RUN_ID[:12]}-unrelated@example.invalid"
)

ACCEPTANCE_ONE_KEY = f"p6-06-runtime-r1-{FIXTURE_RUN_ID}-acceptance-one"
ACCEPTANCE_TWO_KEY = f"p6-06-runtime-r1-{FIXTURE_RUN_ID}-acceptance-two"
ACCEPTANCE_STALE_KEY = f"p6-06-runtime-r1-{FIXTURE_RUN_ID}-acceptance-stale"
ACCEPTANCE_AUTHORIZATION_KEY = (
    f"p6-06-runtime-r1-{FIXTURE_RUN_ID}-customer-authorization"
)
ASSET_REQUEST_KEY = f"p6-06-runtime-r1-{FIXTURE_RUN_ID}-asset-request"
ASSET_REFERENCE_KEY = f"p6-06-runtime-r1-{FIXTURE_RUN_ID}-asset-reference"
ABSENT_PROJECT_ID = "00000000-0000-4000-8000-000000000001"
ABSENT_REQUEST_ID = "00000000-0000-4000-8000-000000000002"

ACKNOWLEDGEMENT = (
    "I confirm this only validates a local Mock draft. It does not approve "
    "Tooling, contact ERPNext or create an Asset."
)
ACCEPTANCE_CATEGORIES = (
    "technical",
    "quality",
    "cycle_capacity",
    "spares_maintenance",
    "documents",
    "warranty_responsibility",
    "cost",
    "safety_interface",
    "asset_location",
)
ACCEPTANCE_DOCTYPE = "NPI Tooling Acceptance Evidence Revision"
ASSET_REQUEST_DOCTYPE = "NPI Tool Asset Request"
ASSET_RECEIPT_DOCTYPE = "NPI Tool Asset Command Idempotency"
ACCEPTANCE_RECEIPT_DOCTYPE = "NPI Tooling Command Idempotency"
P606_ASSET_CREATE_DIAGNOSTICS_ENABLED = True
_P606_ASSET_CREATE_DIAGNOSTIC_HEADER = "X-NPI-Diagnostic-Scope"
_P606_ASSET_CREATE_DIAGNOSTIC_SCOPE = "p805-p606-asset-create-v1"
_P606_ASSET_CREATE_DIAGNOSTIC_CODES = frozenset(
    {
        "P805_P606_ASSET_COMMAND_CONTEXT",
        "P805_P606_ASSET_INPUT_PARSE",
        "P805_P606_ASSET_REPOSITORY_INIT",
        "P805_P606_ASSET_PROJECT_LOCK",
        "P805_P606_ASSET_MASTER_RESOLVE",
        "P805_P606_ASSET_SET_RESOLVE",
        "P805_P606_ASSET_BINDING_RESOLVE",
        "P805_P606_ASSET_REVISION_RESOLVE",
        "P805_P606_ASSET_ACCEPTANCE_RESOLVE",
        "P805_P606_ASSET_INPUT_BUILD",
        "P805_P606_ASSET_PAYLOAD_BUILD",
        "P805_P606_ASSET_RECEIPT_REPLAY",
        "P805_P606_ASSET_DOMAIN_BUILD",
        "P805_P606_ASSET_RESPONSE_BUILD",
        "P805_P606_ASSET_TRANSACTION_SCOPE",
        "P805_P606_ASSET_RECEIPT_INSERT",
        "P805_P606_ASSET_REQUEST_INSERT",
        "P805_P606_ASSET_AUDIT_APPEND",
        "P805_P606_ASSET_RECEIPT_SEAL",
        "P805_P606_ASSET_OUTCOME_VALIDATE",
    }
)
_UUID_PATH_SEGMENT = (
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
_ASSET_CREATE_PATH_PATTERN = re.compile(
    rf"^/api/npi/v1/projects/{_UUID_PATH_SEGMENT}/tooling/"
    rf"{_UUID_PATH_SEGMENT}/sets/{_UUID_PATH_SEGMENT}/asset-requests$"
)


def acceptance_path(project_id: str, master_id: str) -> str:
    return (
        f"/api/npi/v1/projects/{project_id}/tooling/{master_id}/"
        "acceptance-assets"
    )


def acceptance_command_path(project_id: str, master_id: str) -> str:
    return (
        f"/api/npi/v1/projects/{project_id}/tooling/{master_id}/"
        "acceptance-revisions"
    )


def asset_request_collection_path(project_id: str, master_id: str) -> str:
    return (
        f"/api/npi/v1/projects/{project_id}/tooling/{master_id}/asset-requests"
    )


def asset_request_command_path(
    project_id: str,
    master_id: str,
    tooling_set_id: str,
) -> str:
    return (
        f"/api/npi/v1/projects/{project_id}/tooling/{master_id}/sets/"
        f"{tooling_set_id}/asset-requests"
    )


def asset_request_detail_path(
    project_id: str,
    master_id: str,
    asset_request_id: str,
) -> str:
    return (
        f"/api/npi/v1/projects/{project_id}/tooling/{master_id}/asset-requests/"
        f"{asset_request_id}"
    )


def tooling_request(*args, query_key: str = "query", **kwargs):
    return predecessor.tooling_request(
        *args,
        query_key=f"p606-{query_key}",
        **kwargs,
    )


def command(
    opener,
    base_url: str,
    csrf_token: str,
    path: str,
    payload: dict[str, object],
    key: str,
    *,
    asset_create_diagnostic: bool = False,
):
    diagnostic_active = (
        P606_ASSET_CREATE_DIAGNOSTICS_ENABLED
        and asset_create_diagnostic
        and key == ASSET_REQUEST_KEY
        and _ASSET_CREATE_PATH_PATTERN.fullmatch(path) is not None
    )
    cursors = (
        item_runtime._replay_diagnostic_log_cursors()
        if diagnostic_active
        else None
    )
    if diagnostic_active:
        headers = document_runtime.command_headers(csrf_token, key)
        headers[_P606_ASSET_CREATE_DIAGNOSTIC_HEADER] = (
            _P606_ASSET_CREATE_DIAGNOSTIC_SCOPE
        )
        result = document_runtime.request(
            opener,
            base_url,
            path,
            method="POST",
            payload=payload,
            request_headers=headers,
        )
        require(
            result.headers.get("X-Request-ID") == headers["X-Request-ID"],
            "P6-06 predecessor request identity was not echoed",
        )
        require(
            result.headers.get("Cache-Control") == "private, no-store",
            "P6-06 predecessor cache control drifted",
        )
    else:
        result = tooling_request(
            opener,
            base_url,
            path,
            method="POST",
            payload=payload,
            csrf_token=csrf_token,
            idempotency_key=key,
        )
    if result.status != 201 and diagnostic_active:
        diagnostic = item_runtime._sanitized_server_log_diagnostic(
            result.trace_id,
            cursors,
            code_prefix="P805_P606_ASSET_",
            allowed_codes=_P606_ASSET_CREATE_DIAGNOSTIC_CODES,
        )
        if diagnostic is not None:
            code, exception_type, trace_id = diagnostic
            raise RuntimeError(
                "P6-06 Tool Asset predecessor command failed "
                f"[diagnostic_code={code}; exception_type={exception_type}; "
                f"trace_id={trace_id}]"
            )
        raise RuntimeError("P6-06 Tool Asset predecessor command failed")
    require(
        result.status == 201,
        (
            f"P6-06 command {key} returned HTTP {result.status} with problem code "
            f"{result.body.get('code', 'UNAVAILABLE')}"
        ),
    )
    require(
        result.headers.get("Idempotency-Replayed") in {"true", "false"},
        "P6-06 replay header is invalid",
    )
    return result


def require_uuid(value: object, label: str) -> str:
    require(
        isinstance(value, str) and str(UUID(value)) == value,
        f"{label} identity drifted",
    )
    return value


def require_hash(value: object, label: str) -> str:
    require(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value),
        f"{label} hash drifted",
    )
    return value


def rows(administrator, base_url: str, doctype: str, filters, fields=None):
    return predecessor.rows(administrator, base_url, doctype, filters, fields)


def exact_single(values, label: str):
    return predecessor.exact_single(values, label)


def project_context(administrator, base_url: str) -> dict[str, object]:
    context = dict(predecessor.project_context(administrator, base_url))
    project_id = str(context["projectId"])
    master_id = str(context["masterId"])
    tooling_set_id = str(context["toolingSetId"])
    engineering_revision_id = str(context["revisionId"])
    engineering_revision_snapshot_hash = str(context["revisionSnapshotHash"])
    master = exact_single(
        rows(
            administrator,
            base_url,
            "NPI Tooling Master",
            [["global_id", "=", master_id]],
            ["global_id", "snapshot_hash"],
        ),
        "P6-06 Tooling Master",
    )
    tooling_set = exact_single(
        rows(
            administrator,
            base_url,
            "NPI Tooling Set",
            [
                ["project_global_id", "=", project_id],
                ["global_id", "=", tooling_set_id],
            ],
            [
                "global_id",
                "requirement_kind",
                "physical_serial",
                "snapshot_hash",
            ],
        ),
        "P6-06 physical Tooling Set",
    )
    binding = exact_single(
        rows(
            administrator,
            base_url,
            "NPI Tooling Set Revision Binding",
            [
                ["project_global_id", "=", project_id],
                ["tooling_set_global_id", "=", tooling_set_id],
            ],
            [
                "global_id",
                "tooling_revision_global_id",
                "tooling_revision_snapshot_hash",
                "snapshot_hash",
            ],
        ),
        "P6-06 Set-to-Revision binding",
    )
    revision_id = require_uuid(
        binding.get("tooling_revision_global_id"),
        "P6-06 bound Tooling Revision",
    )
    revision_snapshot_hash = require_hash(
        binding.get("tooling_revision_snapshot_hash"),
        "P6-06 bound Tooling Revision",
    )
    revision = exact_single(
        rows(
            administrator,
            base_url,
            "NPI Tooling Revision",
            [
                ["project_global_id", "=", project_id],
                ["global_id", "=", revision_id],
            ],
            ["global_id", "revision_number", "revision_label", "snapshot_hash"],
        ),
        "P6-06 Tooling Revision",
    )
    require(
        tooling_set.get("requirement_kind") == "customer_owned_intake"
        and tooling_set.get("physical_serial") == "P6-02-PHYSICAL-001",
        "P6-06 customer-owned physical Set truth drifted",
    )
    require(
        binding.get("tooling_revision_global_id") == revision_id
        and binding.get("tooling_revision_snapshot_hash")
        == revision_snapshot_hash
        and revision.get("snapshot_hash") == revision_snapshot_hash,
        "P6-06 exact Set binding truth drifted",
    )
    context.update(
        {
            "engineeringRevisionId": engineering_revision_id,
            "engineeringRevisionSnapshotHash": engineering_revision_snapshot_hash,
            "masterSnapshotHash": require_hash(
                master.get("snapshot_hash"),
                "P6-06 Tooling Master",
            ),
            "requirementKind": str(tooling_set["requirement_kind"]),
            "physicalSerial": str(tooling_set["physical_serial"]),
            "bindingId": require_uuid(
                binding.get("global_id"),
                "P6-06 Set binding",
            ),
            "bindingSnapshotHash": require_hash(
                binding.get("snapshot_hash"),
                "P6-06 Set binding",
            ),
            "revisionId": revision_id,
            "revisionNumber": int(revision["revision_number"]),
            "revisionLabel": str(revision["revision_label"]),
            "revisionSnapshotHash": revision_snapshot_hash,
        }
    )
    return context


def predecessor_context(context: dict[str, object]) -> dict[str, object]:
    value = dict(context)
    value["revisionId"] = context["engineeringRevisionId"]
    value["revisionSnapshotHash"] = context["engineeringRevisionSnapshotHash"]
    return value


def file_evidence(context: dict[str, object], role: str) -> dict[str, object]:
    source = context["fileEvidence"]
    require(isinstance(source, dict), "P6-06 retained File evidence is unavailable")
    return {
        "role": role,
        "fileRevisionGlobalId": source["fileRevisionGlobalId"],
        "fileOptimisticVersion": source["fileOptimisticVersion"],
        "frappeContentHash": source["frappeContentHash"],
        "sha256": source["sha256"],
    }


def acceptance_payload(
    context: dict[str, object],
    *,
    version: int,
    predecessor_value: dict[str, object] | None = None,
    include_customer_authorization: bool = True,
) -> dict[str, object]:
    checklist = []
    for index, category in enumerate(ACCEPTANCE_CATEGORIES, start=1):
        recorded = category == "technical" or (
            version == 2 and category == "quality"
        )
        checklist.append(
            {
                "category": category,
                "requirementKey": f"P6-06-{index:02d}",
                "requirementStatement": (
                    f"Synthetic controlled acceptance evidence for {category}."
                ),
                "disposition": (
                    "evidence_recorded" if recorded else "evidence_missing"
                ),
                "responsibleMember": context["member"],
                "evidence": (
                    [file_evidence(context, "checklist")] if recorded else []
                ),
                "note": (
                    f"Controlled runtime revision {version}."
                    if recorded
                    else "Evidence remains visibly missing."
                ),
            }
        )
    payload: dict[str, object] = {
        "toolingSetGlobalId": context["toolingSetId"],
        "toolingSetSnapshotHash": context["toolingSetSnapshotHash"],
        "setRevisionBindingGlobalId": context["bindingId"],
        "setRevisionBindingSnapshotHash": context["bindingSnapshotHash"],
        "toolingRevisionGlobalId": context["revisionId"],
        "toolingRevisionNumber": context["revisionNumber"],
        "toolingRevisionSnapshotHash": context["revisionSnapshotHash"],
        "checklist": checklist,
        "assetActions": [
            {
                "actionKind": "move",
                "reason": "Retain a proposed move as NPI evidence only.",
                "approvalReference": "SYNTHETIC-MOVE-APPROVAL",
                "proposedEffectiveDate": "2027-03-01",
                "evidence": [file_evidence(context, "action")],
            }
        ],
        "spareRecommendations": [
            {
                "recommendationKey": "P6-06-CRITICAL-SPARE",
                "kind": "critical_spare",
                "description": "Synthetic controlled critical-spare recommendation.",
                "recommendedMinimumQuantity": "2",
                "unit": "pcs",
                "supplierSourceSystem": None,
                "supplierSourceObjectId": None,
            }
        ],
        "repairs": [
            {
                "authorizationReference": "SYNTHETIC-CUSTOMER-AUTHORIZATION",
                "quoteReference": "SYNTHETIC-QUOTE-001",
                "quoteCurrency": "CNY",
                "quoteAmount": "1250.00",
                "responsibleMember": context["member"],
                "downtimeImpactHours": "4",
                "detail": "Retain customer-owned repair evidence without ERP execution.",
                "customerAuthorizationEvidence": (
                    [file_evidence(context, "customer_authorization")]
                    if include_customer_authorization
                    else []
                ),
                "verificationEvidence": [
                    file_evidence(context, "repair_verification")
                ],
            }
        ],
        "reason": f"Create controlled acceptance evidence revision {version}.",
    }
    if predecessor_value is not None:
        payload["acceptanceGlobalId"] = predecessor_value["acceptanceGlobalId"]
        payload["expectedVersion"] = version - 1
    return payload


def asset_request_payload(
    context: dict[str, object],
    acceptance: dict[str, object],
) -> dict[str, object]:
    return {
        "targetMode": "mock",
        "acceptanceRevisionGlobalId": acceptance["globalId"],
        "acceptanceVersion": acceptance["acceptanceVersion"],
        "acceptanceSnapshotHash": acceptance["snapshotHash"],
        "expectedToolingMasterSnapshotHash": context["masterSnapshotHash"],
        "expectedToolingSetSnapshotHash": context["toolingSetSnapshotHash"],
        "expectedBindingSnapshotHash": context["bindingSnapshotHash"],
        "expectedToolingRevisionNumber": context["revisionNumber"],
        "expectedToolingRevisionSnapshotHash": context["revisionSnapshotHash"],
        "acknowledgement": ACKNOWLEDGEMENT,
    }


def assert_acceptance_revision(
    value: object,
    *,
    context: dict[str, object],
    version: int,
    predecessor_value: dict[str, object] | None,
) -> dict[str, object]:
    require(isinstance(value, dict), "P6-06 acceptance revision response drifted")
    require_uuid(value.get("globalId"), "P6-06 acceptance revision")
    require_uuid(value.get("acceptanceGlobalId"), "P6-06 acceptance chain")
    require_hash(value.get("snapshotHash"), "P6-06 acceptance revision")
    require(
        value.get("projectGlobalId") == context["projectId"]
        and value.get("toolingMasterGlobalId") == context["masterId"]
        and value.get("toolingMasterSnapshotHash") == context["masterSnapshotHash"]
        and value.get("toolingSetGlobalId") == context["toolingSetId"]
        and value.get("toolingSetSnapshotHash") == context["toolingSetSnapshotHash"]
        and value.get("toolingRequirementKind") == "customer_owned_intake"
        and value.get("setRevisionBindingGlobalId") == context["bindingId"]
        and value.get("setRevisionBindingSnapshotHash")
        == context["bindingSnapshotHash"]
        and value.get("toolingRevisionGlobalId") == context["revisionId"]
        and value.get("toolingRevisionNumber") == context["revisionNumber"]
        and value.get("toolingRevisionSnapshotHash")
        == context["revisionSnapshotHash"],
        "P6-06 acceptance exact Tooling context drifted",
    )
    require(
        value.get("acceptanceVersion") == version,
        "P6-06 acceptance version drifted",
    )
    if predecessor_value is None:
        require(
            value.get("predecessorGlobalId") is None
            and value.get("predecessorSnapshotHash") is None,
            "P6-06 first acceptance revision has a predecessor",
        )
    else:
        require(
            value.get("acceptanceGlobalId")
            == predecessor_value.get("acceptanceGlobalId")
            and value.get("predecessorGlobalId") == predecessor_value.get("globalId")
            and value.get("predecessorSnapshotHash")
            == predecessor_value.get("snapshotHash"),
            "P6-06 immutable acceptance succession drifted",
        )
    checklist = value.get("checklist")
    coverage = value.get("categoryCoverage")
    repairs = value.get("repairs")
    require(
        isinstance(checklist, list)
        and len(checklist) == 9
        and {item.get("category") for item in checklist} == set(ACCEPTANCE_CATEGORIES)
        and isinstance(coverage, list)
        and len(coverage) == 9
        and {item.get("category") for item in coverage}
        == set(ACCEPTANCE_CATEGORIES),
        "P6-06 nine-category evidence coverage drifted",
    )
    require(
        value.get("businessApproval")
        == {
            "state": "unavailable",
            "reasonCode": "tooling_acceptance_policy_unavailable",
        },
        "P6-06 evidence was presented as business acceptance",
    )
    require(
        isinstance(repairs, list)
        and len(repairs) == 1
        and len(repairs[0].get("customerAuthorizationEvidence", [])) == 1
        and repairs[0]["customerAuthorizationEvidence"][0].get("role")
        == "customer_authorization"
        and repairs[0].get("erpRepairResult")
        == {
            "state": "unavailable",
            "reasonCode": "erp_repair_projection_unavailable",
        },
        "P6-06 customer-owned repair authorization truth drifted",
    )
    require(
        all(
            item.get("erpExecution", {}).get("state") == "unavailable"
            for item in value.get("assetActions", [])
        )
        and all(
            item.get("formalItemAndInventory", {}).get("state") == "unavailable"
            for item in value.get("spareRecommendations", [])
        ),
        "P6-06 NPI evidence claimed ERP execution",
    )
    return value


def assert_asset_request(
    value: object,
    *,
    context: dict[str, object],
    acceptance: dict[str, object],
) -> dict[str, object]:
    require(isinstance(value, dict), "P6-06 Tool Asset request response drifted")
    require_uuid(value.get("globalId"), "P6-06 Tool Asset request")
    require_hash(value.get("requestInputHash"), "P6-06 Tool Asset request input")
    require_hash(value.get("payloadHash"), "P6-06 Tool Asset request payload")
    require_hash(value.get("snapshotHash"), "P6-06 Tool Asset request")
    request_input = value.get("requestInput")
    require(
        value.get("apiVersion") == "npi.tooling-asset.v1"
        and value.get("operation") == "create_or_update_tool_asset"
        and value.get("targetMode") == "mock"
        and value.get("requestState") == "draft"
        and value.get("inputValidationState") == "validated_mock"
        and value.get("businessApprovalState") == "unavailable"
        and value.get("dispatchState") == "prohibited"
        and value.get("targetResultState") == "not_requested"
        and value.get("targetResult")
        == {"state": "not_requested", "reasonCode": "phase_6_dispatch_prohibited"},
        "P6-06 Mock-only request truth drifted",
    )
    require(
        isinstance(request_input, dict)
        and request_input.get("projectGlobalId") == context["projectId"]
        and request_input.get("toolingMasterGlobalId") == context["masterId"]
        and request_input.get("toolingMasterSnapshotHash")
        == context["masterSnapshotHash"]
        and request_input.get("toolingSetGlobalId") == context["toolingSetId"]
        and request_input.get("toolingSetSnapshotHash")
        == context["toolingSetSnapshotHash"]
        and request_input.get("setRevisionBindingGlobalId") == context["bindingId"]
        and request_input.get("setRevisionBindingSnapshotHash")
        == context["bindingSnapshotHash"]
        and request_input.get("toolingRevisionGlobalId") == context["revisionId"]
        and request_input.get("toolingRevisionNumber") == context["revisionNumber"]
        and request_input.get("toolingRevisionSnapshotHash")
        == context["revisionSnapshotHash"]
        and request_input.get("acceptanceRevisionGlobalId")
        == acceptance["globalId"]
        and request_input.get("acceptanceVersion") == acceptance["acceptanceVersion"]
        and request_input.get("acceptanceSnapshotHash") == acceptance["snapshotHash"],
        "P6-06 server-resolved Tool Asset request input drifted",
    )
    require(
        value.get("formalAssetMapping")
        == {
            "sourceSystem": "ERPNEXT",
            "editableIn": "ERPNEXT",
            "state": "unavailable",
            "reasonCode": "erp_asset_mapping_unavailable",
            "mappingCardinality": "zero_or_one_per_physical_set",
        },
        "P6-06 local draft fabricated formal Asset mapping truth",
    )
    forbidden = {
        "assetId",
        "formalAssetId",
        "erpAssetId",
        "targetObjectId",
        "location",
        "shotCount",
        "maintenanceState",
        "dispatchReceipt",
        "outboxMessageId",
    }
    require(
        forbidden.isdisjoint(value) and forbidden.isdisjoint(request_input),
        "P6-06 local request exposed forbidden target truth",
    )
    return value


def assert_acceptance_context(
    result,
    *,
    context: dict[str, object],
    acceptance_count: int,
    request_count: int,
) -> dict[str, object]:
    require(result.status == 200, "P6-06 acceptance/Asset context query failed")
    value = result.body
    require(
        isinstance(value, dict)
        and value.get("projectGlobalId") == context["projectId"]
        and value.get("toolingMasterGlobalId") == context["masterId"]
        and value.get("permissions")
        == {
            "view": True,
            "recordEvidence": True,
            "prepareMockAssetRequest": True,
            "approveAcceptance": False,
            "dispatchAssetRequest": False,
            "editErpProjection": False,
        }
        and value.get("businessApproval")
        == {
            "state": "unavailable",
            "reasonCode": "tooling_acceptance_policy_unavailable",
        }
        and value.get("assetProjection")
        == {
            "sourceSystem": "ERPNEXT",
            "editableIn": "ERPNEXT",
            "state": "unavailable",
            "reasonCode": "erp_asset_projection_unavailable",
            "mappingCardinality": "zero_or_one_per_physical_set",
        },
        "P6-06 permissions, approval, or ERP projection truth drifted",
    )
    require(
        isinstance(value.get("acceptanceRevisions"), list)
        and len(value["acceptanceRevisions"]) == acceptance_count
        and isinstance(value.get("assetRequests"), list)
        and len(value["assetRequests"]) == request_count,
        "P6-06 retained acceptance/Asset cardinality drifted",
    )
    return value


def persisted_counts(
    administrator,
    base_url: str,
    project_id: str,
) -> dict[str, int]:
    return {
        "acceptance": len(
            rows(
                administrator,
                base_url,
                ACCEPTANCE_DOCTYPE,
                [["project_global_id", "=", project_id]],
                ["global_id"],
            )
        ),
        "acceptanceReceipts": len(
            rows(
                administrator,
                base_url,
                ACCEPTANCE_RECEIPT_DOCTYPE,
                [
                    ["project_global_id", "=", project_id],
                    ["operation", "=", "tooling_acceptance_evidence.create"],
                ],
                ["global_id"],
            )
        ),
        "assetRequests": len(
            rows(
                administrator,
                base_url,
                ASSET_REQUEST_DOCTYPE,
                [["project_global_id", "=", project_id]],
                ["global_id"],
            )
        ),
        "assetReceipts": len(
            rows(
                administrator,
                base_url,
                ASSET_RECEIPT_DOCTYPE,
                [
                    ["project_global_id", "=", project_id],
                    ["operation", "=", "create_or_update_tool_asset"],
                ],
                ["global_id"],
            )
        ),
        "acceptanceAudits": len(
            rows(
                administrator,
                base_url,
                "NPI Audit Event",
                [["operation", "=", "tooling_acceptance_evidence.create"]],
                ["global_id"],
            )
        ),
        "assetAudits": len(
            rows(
                administrator,
                base_url,
                "NPI Audit Event",
                [["operation", "=", "tooling_asset_request.create"]],
                ["global_id"],
            )
        ),
        "outbox": len(
            rows(
                administrator,
                base_url,
                "NPI Outbox Message",
                [],
                ["event_id"],
            )
        ),
        "inbox": len(
            rows(
                administrator,
                base_url,
                "NPI Inbox Message",
                [],
                ["event_id"],
            )
        ),
    }


def verify_persistence(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    context: dict[str, object],
    acceptances: tuple[dict[str, object], dict[str, object]],
    asset_request: dict[str, object],
    integration_before: tuple[int, int],
) -> None:
    counts = persisted_counts(
        administrator,
        base_url,
        str(context["projectId"]),
    )
    require(
        counts["acceptance"] == 2
        and counts["acceptanceReceipts"] == 2
        and counts["assetRequests"] == 1
        and counts["assetReceipts"] == 1
        and counts["acceptanceAudits"] == 2
        and counts["assetAudits"] == 1,
        "P6-06 persisted immutable cardinality drifted",
    )
    require(
        (counts["outbox"], counts["inbox"]) == integration_before,
        "P6-06 local Mock preparation created integration traffic",
    )
    acceptance_receipts = rows(
        administrator,
        base_url,
        ACCEPTANCE_RECEIPT_DOCTYPE,
        [["operation", "=", "tooling_acceptance_evidence.create"]],
        ["actor_user_id", "payload_hash", "response_hash", "sealed"],
    )
    asset_receipts = rows(
        administrator,
        base_url,
        ASSET_RECEIPT_DOCTYPE,
        [["operation", "=", "create_or_update_tool_asset"]],
        [
            "actor_user_id",
            "payload_hash",
            "response_hash",
            "request_global_id",
            "sealed",
        ],
    )
    require(
        len(acceptance_receipts) == 2
        and all(item.get("actor_user_id") == ACTOR_USER for item in acceptance_receipts)
        and all(item.get("sealed") == 1 for item in acceptance_receipts)
        and all(len(str(item.get("payload_hash"))) == 64 for item in acceptance_receipts)
        and all(len(str(item.get("response_hash"))) == 64 for item in acceptance_receipts)
        and len(asset_receipts) == 1
        and asset_receipts[0].get("actor_user_id") == ACTOR_USER
        and asset_receipts[0].get("request_global_id") == asset_request["globalId"]
        and asset_receipts[0].get("sealed") == 1
        and len(str(asset_receipts[0].get("payload_hash"))) == 64
        and len(str(asset_receipts[0].get("response_hash"))) == 64,
        "P6-06 actor-bound sealed receipt truth drifted",
    )
    for operation, expected in (
        ("tooling_acceptance_evidence.create", 2),
        ("tooling_asset_request.create", 1),
    ):
        audits = rows(
            administrator,
            base_url,
            "NPI Audit Event",
            [["operation", "=", operation]],
            ["result", "trace_id"],
        )
        require(
            len(audits) == expected
            and all(item.get("result") == "created" for item in audits)
            and all(item.get("trace_id") for item in audits),
            f"P6-06 audit truth drifted for {operation}",
        )
    immutable = (
        (ACCEPTANCE_DOCTYPE, acceptances[0]["globalId"]),
        (ACCEPTANCE_DOCTYPE, acceptances[1]["globalId"]),
        (ASSET_REQUEST_DOCTYPE, asset_request["globalId"]),
    )
    for doctype, name in immutable:
        before = get_resource(administrator, base_url, doctype, str(name))
        snapshot_hash = before.body.get("data", {}).get("snapshot_hash")
        rejected_update = update_resource(
            administrator,
            base_url,
            doctype,
            str(name),
            {"snapshot_hash": "0" * 64},
            csrf_token,
        )
        rejected_delete = delete_resource(
            administrator,
            base_url,
            doctype,
            str(name),
            csrf_token,
        )
        after = get_resource(administrator, base_url, doctype, str(name))
        require(
            before.status == 200
            and isinstance(snapshot_hash, str)
            and len(snapshot_hash) == 64
            and rejected_update.status in {403, 417}
            and rejected_delete.status in {403, 417}
            and after.status == 200
            and after.body.get("data", {}).get("snapshot_hash") == snapshot_hash,
            f"P6-06 immutable {doctype} accepted generic mutation",
        )


def verify_idor(
    administrator,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
    *,
    context: dict[str, object],
    asset_request: dict[str, object],
) -> None:
    document_runtime.create_internal_fixture_user(
        administrator,
        base_url,
        UNRELATED_USER,
        fixture_password,
        csrf_token,
    )
    try:
        unrelated = login(base_url, UNRELATED_USER, fixture_password)
        unrelated_csrf = bootstrap_csrf(unrelated, base_url, UNRELATED_USER)
        denied = tooling_request(
            unrelated,
            base_url,
            acceptance_path(str(context["projectId"]), str(context["masterId"])),
            query_key="idor-denied",
        )
        absent = tooling_request(
            unrelated,
            base_url,
            acceptance_path(ABSENT_PROJECT_ID, str(context["masterId"])),
            query_key="idor-absent",
        )
        validate_problem(denied, 404, "TOOLING_UNAVAILABLE")
        validate_problem(absent, 404, "TOOLING_UNAVAILABLE")
        fields = ("type", "title", "status", "code", "retryable")
        require(
            {key: denied.body.get(key) for key in fields}
            == {key: absent.body.get(key) for key in fields},
            "P6-06 unauthorized and absent Projects are distinguishable",
        )
        denied_detail = tooling_request(
            unrelated,
            base_url,
            asset_request_detail_path(
                str(context["projectId"]),
                str(context["masterId"]),
                str(asset_request["globalId"]),
            ),
            query_key="idor-detail-denied",
        )
        absent_detail = tooling_request(
            unrelated,
            base_url,
            asset_request_detail_path(
                ABSENT_PROJECT_ID,
                str(context["masterId"]),
                ABSENT_REQUEST_ID,
            ),
            query_key="idor-detail-absent",
        )
        validate_problem(denied_detail, 404, "TOOLING_UNAVAILABLE")
        validate_problem(absent_detail, 404, "TOOLING_UNAVAILABLE")
        require(
            {key: denied_detail.body.get(key) for key in fields}
            == {key: absent_detail.body.get(key) for key in fields},
            "P6-06 unauthorized and absent request details are distinguishable",
        )
        command_key = f"p6-06-runtime-r1-{FIXTURE_RUN_ID}-idor-command"
        denied_command = tooling_request(
            unrelated,
            base_url,
            acceptance_command_path(
                str(context["projectId"]),
                str(context["masterId"]),
            ),
            method="POST",
            payload={"doctype": "Secret"},
            csrf_token=unrelated_csrf,
            idempotency_key=command_key,
            query_key="idor-command-denied",
        )
        absent_command = tooling_request(
            unrelated,
            base_url,
            acceptance_command_path(ABSENT_PROJECT_ID, str(context["masterId"])),
            method="POST",
            payload={"doctype": "Secret"},
            csrf_token=unrelated_csrf,
            idempotency_key=command_key,
            query_key="idor-command-absent",
        )
        validate_problem(denied_command, 403, "PERMISSION_DENIED")
        validate_problem(absent_command, 403, "PERMISSION_DENIED")
        require(
            {key: denied_command.body.get(key) for key in fields}
            == {key: absent_command.body.get(key) for key in fields},
            "P6-06 unauthorized and absent command scopes are distinguishable",
        )
    finally:
        delete_disposable_user(
            administrator,
            base_url,
            UNRELATED_USER,
            csrf_token,
        )


def verify_conflict_rollback(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    context: dict[str, object],
    acceptance_one: dict[str, object],
    acceptance_two: dict[str, object],
) -> None:
    before = persisted_counts(
        administrator,
        base_url,
        str(context["projectId"]),
    )
    different = acceptance_payload(context, version=1)
    different["reason"] = "A different payload for the sealed idempotency key."
    stale = acceptance_payload(
        context,
        version=2,
        predecessor_value=acceptance_one,
    )
    no_customer_authorization = acceptance_payload(
        context,
        version=1,
        include_customer_authorization=False,
    )
    request_conflict = asset_request_payload(context, acceptance_one)
    invalid_reference = asset_request_payload(context, acceptance_two)
    invalid_reference["expectedToolingSetSnapshotHash"] = "0" * 64
    failures = (
        (
            acceptance_command_path(
                str(context["projectId"]),
                str(context["masterId"]),
            ),
            different,
            ACCEPTANCE_ONE_KEY,
            409,
            "TOOLING_IDEMPOTENCY_CONFLICT",
        ),
        (
            acceptance_command_path(
                str(context["projectId"]),
                str(context["masterId"]),
            ),
            stale,
            ACCEPTANCE_STALE_KEY,
            409,
            "TOOLING_VERSION_CONFLICT",
        ),
        (
            acceptance_command_path(
                str(context["projectId"]),
                str(context["masterId"]),
            ),
            no_customer_authorization,
            ACCEPTANCE_AUTHORIZATION_KEY,
            422,
            "VALIDATION_FAILED",
        ),
        (
            asset_request_command_path(
                str(context["projectId"]),
                str(context["masterId"]),
                str(context["toolingSetId"]),
            ),
            request_conflict,
            ASSET_REQUEST_KEY,
            409,
            "TOOLING_IDEMPOTENCY_CONFLICT",
        ),
        (
            asset_request_command_path(
                str(context["projectId"]),
                str(context["masterId"]),
                str(context["toolingSetId"]),
            ),
            invalid_reference,
            ASSET_REFERENCE_KEY,
            404,
            "TOOLING_REFERENCE_UNAVAILABLE",
        ),
    )
    for path, payload, key, status, code in failures:
        result = tooling_request(
            administrator,
            base_url,
            path,
            method="POST",
            payload=payload,
            csrf_token=csrf_token,
            idempotency_key=key,
        )
        validate_problem(result, status, code)
    require(
        persisted_counts(
            administrator,
            base_url,
            str(context["projectId"]),
        )
        == before,
        "P6-06 failed commands changed business, receipt, audit, or integration truth",
    )


def run_fresh(
    administrator,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
) -> dict[str, object]:
    context = project_context(administrator, base_url)
    schema = run_bench_fixture(
        "verify_tooling_acceptance_runtime_schema",
        {"fixture_run_id": FIXTURE_RUN_ID},
    )
    project_id = str(context["projectId"])
    master_id = str(context["masterId"])
    context_path = acceptance_path(project_id, master_id)
    acceptance_create_path = acceptance_command_path(project_id, master_id)
    asset_create_path = asset_request_command_path(
        project_id,
        master_id,
        str(context["toolingSetId"]),
    )
    empty = assert_acceptance_context(
        tooling_request(
            administrator,
            base_url,
            context_path,
            query_key="empty-context",
        ),
        context=context,
        acceptance_count=0,
        request_count=0,
    )
    require(
        empty["acceptanceRevisions"] == [] and empty["assetRequests"] == [],
        "P6-06 fresh acceptance/Asset context was not empty",
    )
    guest = tooling_request(
        urllib.request.build_opener(),
        base_url,
        context_path,
        query_key="guest",
    )
    validate_problem(guest, 401, "AUTHENTICATION_REQUIRED")
    initial_counts = persisted_counts(administrator, base_url, project_id)
    integration_before = (initial_counts["outbox"], initial_counts["inbox"])

    first_result = command(
        administrator,
        base_url,
        csrf_token,
        acceptance_create_path,
        acceptance_payload(context, version=1),
        ACCEPTANCE_ONE_KEY,
    )
    first = assert_acceptance_revision(
        first_result.body.get("acceptanceEvidence"),
        context=context,
        version=1,
        predecessor_value=None,
    )
    second_result = command(
        administrator,
        base_url,
        csrf_token,
        acceptance_create_path,
        acceptance_payload(context, version=2, predecessor_value=first),
        ACCEPTANCE_TWO_KEY,
    )
    second = assert_acceptance_revision(
        second_result.body.get("acceptanceEvidence"),
        context=context,
        version=2,
        predecessor_value=first,
    )
    request_result = command(
        administrator,
        base_url,
        csrf_token,
        asset_create_path,
        asset_request_payload(context, second),
        ASSET_REQUEST_KEY,
        asset_create_diagnostic=True,
    )
    asset_request = assert_asset_request(
        request_result.body,
        context=context,
        acceptance=second,
    )

    retained = assert_acceptance_context(
        tooling_request(
            administrator,
            base_url,
            context_path,
            query_key="retained-context",
        ),
        context=context,
        acceptance_count=2,
        request_count=1,
    )
    retained_acceptances = retained["acceptanceRevisions"]
    assert_acceptance_revision(
        retained_acceptances[0],
        context=context,
        version=1,
        predecessor_value=None,
    )
    assert_acceptance_revision(
        retained_acceptances[1],
        context=context,
        version=2,
        predecessor_value=retained_acceptances[0],
    )
    assert_asset_request(
        retained["assetRequests"][0],
        context=context,
        acceptance=retained_acceptances[1],
    )
    collection = tooling_request(
        administrator,
        base_url,
        asset_request_collection_path(project_id, master_id),
        query_key="request-collection",
    )
    require(
        collection.status == 200
        and collection.body.get("projectGlobalId") == project_id
        and collection.body.get("toolingMasterGlobalId") == master_id
        and collection.body.get("items") == [asset_request],
        "P6-06 Tool Asset request collection drifted",
    )
    detail = tooling_request(
        administrator,
        base_url,
        asset_request_detail_path(project_id, master_id, str(asset_request["globalId"])),
        query_key="request-detail",
    )
    require(
        detail.status == 200 and detail.body == asset_request,
        "P6-06 Tool Asset request detail drifted",
    )
    missing_detail = tooling_request(
        administrator,
        base_url,
        asset_request_detail_path(project_id, master_id, ABSENT_REQUEST_ID),
        query_key="request-detail-missing",
    )
    validate_problem(missing_detail, 404, "TOOLING_UNAVAILABLE")

    verify_idor(
        administrator,
        base_url,
        csrf_token,
        fixture_password,
        context=context,
        asset_request=asset_request,
    )
    verify_persistence(
        administrator,
        base_url,
        csrf_token,
        context=context,
        acceptances=(first, second),
        asset_request=asset_request,
        integration_before=integration_before,
    )
    verify_conflict_rollback(
        administrator,
        base_url,
        csrf_token,
        context=context,
        acceptance_one=first,
        acceptance_two=second,
    )
    return {
        "acceptanceRevisionCount": 2,
        "assetRequestCount": 1,
        "businessApproval": "unavailable",
        "dispatchState": "prohibited",
        "doctypeCount": schema["doctypeCount"],
        "fixtureRunId": FIXTURE_RUN_ID,
        "integrationTrafficCreated": False,
        "targetResultState": "not_requested",
    }


def replay_context(administrator, base_url: str):
    context = project_context(administrator, base_url)
    retained = assert_acceptance_context(
        tooling_request(
            administrator,
            base_url,
            acceptance_path(str(context["projectId"]), str(context["masterId"])),
            query_key="replay-context",
        ),
        context=context,
        acceptance_count=2,
        request_count=1,
    )
    first, second = retained["acceptanceRevisions"]
    asset_request = retained["assetRequests"][0]
    assert_acceptance_revision(
        first,
        context=context,
        version=1,
        predecessor_value=None,
    )
    assert_acceptance_revision(
        second,
        context=context,
        version=2,
        predecessor_value=first,
    )
    assert_asset_request(
        asset_request,
        context=context,
        acceptance=second,
    )
    return context, first, second, asset_request


def run_replay(administrator, base_url: str, csrf_token: str) -> None:
    context, first, second, asset_request = replay_context(administrator, base_url)
    before = persisted_counts(
        administrator,
        base_url,
        str(context["projectId"]),
    )
    commands = (
        (
            acceptance_command_path(
                str(context["projectId"]),
                str(context["masterId"]),
            ),
            acceptance_payload(context, version=1),
            ACCEPTANCE_ONE_KEY,
            {"acceptanceEvidence": first},
        ),
        (
            acceptance_command_path(
                str(context["projectId"]),
                str(context["masterId"]),
            ),
            acceptance_payload(context, version=2, predecessor_value=first),
            ACCEPTANCE_TWO_KEY,
            {"acceptanceEvidence": second},
        ),
        (
            asset_request_command_path(
                str(context["projectId"]),
                str(context["masterId"]),
                str(context["toolingSetId"]),
            ),
            asset_request_payload(context, second),
            ASSET_REQUEST_KEY,
            asset_request,
        ),
    )
    for path, payload, key, exact_body in commands:
        replay = command(
            administrator,
            base_url,
            csrf_token,
            path,
            payload,
            key,
        )
        require(
            replay.headers.get("Idempotency-Replayed") == "true",
            f"P6-06 cross-process replay was not declared for {key}",
        )
        require(replay.body == exact_body, f"P6-06 replay response drifted for {key}")
    require(
        persisted_counts(
            administrator,
            base_url,
            str(context["projectId"]),
        )
        == before,
        "P6-06 cross-process replay changed immutable or integration cardinality",
    )


def route_disable_probe(administrator, base_url: str, expected_mode: str) -> None:
    context = project_context(administrator, base_url)
    project_id = str(context["projectId"])
    master_id = str(context["masterId"])
    acceptance = tooling_request(
        administrator,
        base_url,
        acceptance_path(project_id, master_id),
        query_key=f"route-{expected_mode}",
    )
    engineering = tooling_request(
        administrator,
        base_url,
        predecessor.engineering_path(project_id, master_id),
        query_key=f"engineering-{expected_mode}",
    )
    retained_engineering = predecessor.assert_engineering_context(
        engineering,
        context=predecessor_context(context),
        expected_count=2,
    )
    predecessor.assert_successors(retained_engineering)
    if expected_mode == "disabled":
        validate_problem(
            acceptance,
            503,
            "TOOLING_ACCEPTANCE_ASSETS_ROUTES_DISABLED",
        )
        return
    assert_acceptance_context(
        acceptance,
        context=context,
        acceptance_count=2,
        request_count=1,
    )


def verify_tooling_acceptance_runtime_schema(
    fixture_run_id: str,
) -> dict[str, object]:
    import frappe

    document_runtime._validated_runtime_site()
    require(fixture_run_id == FIXTURE_RUN_ID, "P6-06 schema fixture namespace drifted")
    required_fields = {
        ACCEPTANCE_DOCTYPE: {
            "global_id",
            "acceptance_global_id",
            "project_global_id",
            "tooling_master_global_id",
            "tooling_set_global_id",
            "tooling_revision_global_id",
            "acceptance_version",
            "predecessor_global_id",
            "acceptance_snapshot",
            "snapshot_hash",
        },
        ASSET_REQUEST_DOCTYPE: {
            "global_id",
            "project_global_id",
            "tooling_master_global_id",
            "tooling_set_global_id",
            "acceptance_revision_global_id",
            "operation",
            "request_state",
            "dispatch_state",
            "target_result_state",
            "request_snapshot",
            "snapshot_hash",
        },
        ASSET_RECEIPT_DOCTYPE: {
            "global_id",
            "receipt_key",
            "project_global_id",
            "actor_user_id",
            "operation",
            "payload_hash",
            "request_global_id",
            "response_hash",
            "sealed",
        },
    }
    for doctype, fields in required_fields.items():
        meta = frappe.get_meta(doctype)
        actual = {field.fieldname for field in meta.fields}
        require(fields.issubset(actual), f"P6-06 {doctype} metadata drifted")
        require(
            int(meta.allow_rename or 0) == 0 and int(meta.is_submittable or 0) == 0,
            f"P6-06 {doctype} mutability metadata drifted",
        )
    return {
        "doctypeCount": len(required_fields),
        "fixtureRunId": fixture_run_id,
        "metadataSynchronized": True,
        "runtimeMarker": RUNTIME_MARKER,
    }


def run_bench_fixture(method: str, kwargs: dict[str, object]) -> dict[str, Any]:
    require(
        method == "verify_tooling_acceptance_runtime_schema",
        "P6-06 Bench fixture is unavailable",
    )
    require(
        BENCH_PATH.is_dir()
        and not BENCH_PATH.is_symlink()
        and BENCH_PATH.resolve() == BENCH_PATH,
        "P6-06 verifier requires the fixed physical Bench",
    )
    environment = os.environ.copy()
    for name in (
        "NPI_RUNTIME_ADMINISTRATOR_PASSWORD",
        "NPI_RUNTIME_FIXTURE_PASSWORD",
        "NPI_ADMINISTRATOR_PASSWORD",
        "NPI_DATABASE_ROOT_PASSWORD",
    ):
        environment.pop(name, None)
    current_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        str(ROOT)
        if not current_pythonpath
        else f"{ROOT}{os.pathsep}{current_pythonpath}"
    )
    completed = subprocess.run(
        [
            str(BENCH_PATH / "env" / "bin" / "python"),
            str(ROOT / "scripts" / "verify_tooling_acceptance_runtime.py"),
            "--bench-fixture",
            method,
            "--fixture-kwargs",
            json.dumps(kwargs, separators=(",", ":"), sort_keys=True),
        ],
        cwd=BENCH_PATH / "sites",
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    require(completed.returncode == 0, f"P6-06 Bench fixture failed: {method}")
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    require(bool(lines), f"P6-06 Bench fixture was silent: {method}")
    result = json.loads(lines[-1])
    require(isinstance(result, dict), "P6-06 Bench fixture result is invalid")
    return result


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    require(
        method == "verify_tooling_acceptance_runtime_schema",
        "P6-06 Bench fixture is unavailable",
    )
    import frappe

    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    try:
        frappe.set_user(ACTOR_USER)
        result = verify_tooling_acceptance_runtime_schema(**kwargs)
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the real cumulative P6-06 Tooling acceptance runtime.",
    )
    parser.add_argument("--base-url")
    parser.add_argument(
        "--bench-fixture",
        choices=("verify_tooling_acceptance_runtime_schema",),
    )
    parser.add_argument("--fixture-kwargs")
    parser.add_argument("--route-disable-probe", choices=("disabled", "recovered"))
    parser.add_argument("--replay-only", action="store_true")
    arguments = parser.parse_args()
    if arguments.bench_fixture is not None:
        require(
            arguments.base_url is None
            and isinstance(arguments.fixture_kwargs, str)
            and arguments.route_disable_probe is None
            and not arguments.replay_only,
            "P6-06 Bench fixture arguments are invalid",
        )
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "P6-06 fixture kwargs are invalid")
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return
    require(
        isinstance(arguments.base_url, str)
        and arguments.fixture_kwargs is None
        and document_runtime.CALLER_SUPPLIED_FIXTURE_RUN_ID is not None,
        "P6-06 runtime base URL and fixture namespace are required",
    )
    fixture_password = secret_from_environment("NPI_RUNTIME_FIXTURE_PASSWORD")
    base_url = validate_local_fixture_inputs(
        arguments.base_url,
        "Administrator",
        UNRELATED_USER,
    )
    require(
        FIXTURE_RUN_ID != "0" * 32
        and ACTOR_USER.endswith("@example.invalid")
        and UNRELATED_USER.endswith("@example.invalid"),
        "P6-06 fixture identity drifted",
    )
    require(
        int(arguments.route_disable_probe is not None)
        + int(arguments.replay_only)
        <= 1,
        "P6-06 runtime modes are mutually exclusive",
    )
    actor = login(base_url, ACTOR_USER, fixture_password)
    csrf_token = bootstrap_csrf(actor, base_url, ACTOR_USER)
    if arguments.route_disable_probe is not None:
        route_disable_probe(actor, base_url, arguments.route_disable_probe)
        print(json.dumps({"routeMode": arguments.route_disable_probe}, sort_keys=True))
        return
    if arguments.replay_only:
        run_replay(actor, base_url, csrf_token)
        print(
            json.dumps(
                {"crossProcessReplay": True, "fixtureRunId": FIXTURE_RUN_ID},
                sort_keys=True,
            )
        )
        print("local Frappe Tooling acceptance runtime replay verification passed")
        return
    evidence = run_fresh(actor, base_url, csrf_token, fixture_password)
    print(json.dumps(evidence, sort_keys=True))
    print("local Frappe Tooling acceptance runtime verification passed")


if __name__ == "__main__":
    main()
