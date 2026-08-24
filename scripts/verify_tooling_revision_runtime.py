from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.request
from pathlib import Path
from typing import Any
from uuid import UUID

import verify_document_runtime as document_runtime
import verify_tooling_runtime as predecessor
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
ACTOR_USER = "Administrator"
UNRELATED_USER = (
    f"npi-tooling-revision-{FIXTURE_RUN_ID[:16]}-unrelated@example.invalid"
)

PART_KEY = f"p6-03-runtime-r1-{FIXTURE_RUN_ID}-part"
APPLICABILITY_KEY = f"p6-03-runtime-r1-{FIXTURE_RUN_ID}-applicability"
REVISION_ONE_KEY = f"p6-03-runtime-r1-{FIXTURE_RUN_ID}-revision-one"
REVISION_TWO_KEY = f"p6-03-runtime-r1-{FIXTURE_RUN_ID}-revision-two"
REVISION_STALE_KEY = f"p6-03-runtime-r1-{FIXTURE_RUN_ID}-revision-stale"
SPECIFICATION_KEY = f"p6-03-runtime-r1-{FIXTURE_RUN_ID}-part-specification"
SPECIFICATION_CONFLICT_KEY = (
    f"p6-03-runtime-r1-{FIXTURE_RUN_ID}-part-specification-conflict"
)
CHAIN_ONE_KEY = f"p6-03-runtime-r1-{FIXTURE_RUN_ID}-chain-one"
CHAIN_TWO_KEY = f"p6-03-runtime-r1-{FIXTURE_RUN_ID}-chain-two"
CHAIN_STALE_KEY = f"p6-03-runtime-r1-{FIXTURE_RUN_ID}-chain-stale"
BINDING_KEY = f"p6-03-runtime-r1-{FIXTURE_RUN_ID}-set-binding"
BINDING_CONFLICT_KEY = f"p6-03-runtime-r1-{FIXTURE_RUN_ID}-set-binding-conflict"
PART_TITLE = "Synthetic P6-03 controlled Part"
RETAINED_MASTER_TITLE = "Synthetic shared front housing tool"
ABSENT_PROJECT_ID = "00000000-0000-4000-8000-000000000001"
ABSENT_OBJECT_ID = "00000000-0000-4000-8000-000000000002"

REVISION_DOCTYPES = (
    "NPI Tooling Revision",
    "NPI Part Controlled Specification",
    "NPI Tooling Process Chain Revision",
    "NPI Tooling Set Revision Binding",
)
REVISION_PERMISSIONS = {
    "view": True,
    "createRevision": True,
    "createPartSpecification": True,
    "createProcessChain": True,
    "bindSetSource": True,
    "transitionLifecycle": False,
}
_UNEXPECTED_DIAGNOSTIC_CODES = frozenset({"UNEXPECTED_BFF_EXCEPTION"})
TOOLING_REVISION_CREATE_DIAGNOSTICS_ENABLED = False
_REVISION_CREATE_DIAGNOSTIC_CODES = frozenset(
    {
        "P603_REVISION_COMMAND_CONTEXT",
        "P603_REVISION_INPUT_PARSE",
        "P603_REVISION_PROJECT_LOCK",
        "P603_REVISION_IDEMPOTENCY_CONTEXT",
        "P603_REVISION_MASTER_LOAD",
        "P603_REVISION_TIP_LOAD",
        "P603_REVISION_DOMAIN_BUILD",
        "P603_REVISION_RECEIPT_INSERT",
        "P603_REVISION_INSERT",
        "P603_REVISION_AUDIT_APPEND",
        "P603_REVISION_RESPONSE_BUILD",
        "P603_REVISION_RECEIPT_SEAL",
        "P603_REVISION_API_RESPONSE",
    }
)


def revision_path(project_id: str, master_id: str, suffix: str = "") -> str:
    return predecessor.tooling_path(project_id, f"/{master_id}/revisions{suffix}")


def part_specification_path(project_id: str, part_id: str, revision_id: str) -> str:
    return (
        f"/api/npi/v1/projects/{project_id}/parts/{part_id}/revisions/"
        f"{revision_id}/controlled-specification"
    )


def process_chain_path(project_id: str, suffix: str = "") -> str:
    return f"/api/npi/v1/projects/{project_id}/tooling-process-chains{suffix}"


def binding_path(project_id: str, master_id: str, set_id: str) -> str:
    return predecessor.tooling_set_path(
        project_id,
        master_id,
        f"/{set_id}/revision-binding",
    )


def tooling_request(*args, query_key: str = "query", **kwargs):
    return predecessor.tooling_request(
        *args,
        query_key=f"p603-{query_key}",
        **kwargs,
    )


def exact_retained_master(values: object, project_id: str) -> dict[str, object]:
    require(
        isinstance(values, list),
        "P6-03 retained Tooling Master collection drifted",
    )
    return predecessor.exact_single(
        [
            value
            for value in values
            if isinstance(value, dict)
            and value.get("title") == RETAINED_MASTER_TITLE
            and value.get("originatingProjectGlobalId") == project_id
        ],
        "P6-03 retained Tooling Master",
    )


def command(
    opener,
    base_url: str,
    csrf_token: str,
    path: str,
    payload: dict[str, object],
    key: str,
):
    result = tooling_request(
        opener,
        base_url,
        path,
        method="POST",
        payload=payload,
        csrf_token=csrf_token,
        idempotency_key=key,
        tooling_revision_create_diagnostic=(
            TOOLING_REVISION_CREATE_DIAGNOSTICS_ENABLED
        ),
    )
    problem_code = result.body.get("code") if isinstance(result.body, dict) else None
    if result.status != 201:
        diagnostic = predecessor._sanitized_server_diagnostic(
            result.trace_id,
            _REVISION_CREATE_DIAGNOSTIC_CODES,
        )
        if diagnostic is None:
            diagnostic = predecessor._sanitized_server_diagnostic(
                result.trace_id,
                _UNEXPECTED_DIAGNOSTIC_CODES,
            )
        if diagnostic is not None:
            exception_type, diagnostic_code, trace_id = diagnostic
            raise RuntimeError(
                f"P6-03 command {key} returned HTTP {result.status}"
                f" with problem code {problem_code or 'UNAVAILABLE'}"
                f" [diagnostic_code={diagnostic_code}; "
                f"exception_type={exception_type}; trace_id={trace_id}]"
            )
    require(
        result.status == 201,
        (
            f"P6-03 command {key} returned HTTP {result.status}"
            f" with problem code {problem_code or 'UNAVAILABLE'}"
        ),
    )
    require(
        result.headers.get("Idempotency-Replayed") in {"true", "false"},
        "P6-03 replay header is invalid",
    )
    return result


def measurement(value: str, unit: str, source: str) -> dict[str, str]:
    return {"value": value, "unit": unit, "source": source}


def tooling_specification(revision_number: int) -> dict[str, object]:
    return {
        "toolingType": "Injection mold",
        "moldBaseMaterial": "P20",
        "coreMaterial": "H13",
        "hardness": measurement("52", "HRC", "Controlled drawing"),
        "surfaceTreatment": "Nitrided",
        "cavityCount": 1,
        "hotRunner": "Valve gate",
        "length": measurement("1100", "mm", "Controlled drawing"),
        "width": measurement("820", "mm", "Controlled drawing"),
        "height": measurement("760", "mm", "Controlled drawing"),
        "weight": measurement("1200", "kg", "Controlled drawing"),
        "clampTonnage": measurement("450", "t", "Engineering calculation"),
        "tieBarSpacingX": measurement("900", "mm", "Machine envelope"),
        "tieBarSpacingY": measurement("750", "mm", "Machine envelope"),
        "injectionCapacity": measurement("1200", "g", "Engineering calculation"),
        "machineType": "Injection molding machine",
        "targetCycle": measurement(
            "40" if revision_number == 2 else "42",
            "s",
            "Controlled target",
        ),
        "targetLife": measurement("1000000", "shots", "Customer contract"),
        "warranty": "Twelve months after acceptance",
        "customerStandard": "Synthetic customer standard CS-01",
        "interfaceRequirement": "Synthetic standard machine interface",
        "spareParts": [],
        "deliveryDocuments": [],
    }


def external_identity(identity_type: str, value: str, source_id: str) -> dict[str, object]:
    return {
        "identityType": identity_type,
        "value": value,
        "rawValue": f"Raw {value}",
        "sourceSystem": "NPI_ONE",
        "sourceObjectId": source_id,
        "effectiveFrom": "2026-08-01",
    }


def revision_payload(
    applicability_id: str,
    revision_number: int,
    model_reference: dict[str, str],
) -> dict[str, object]:
    payload: dict[str, object] = {
        "revisionLabel": f"R{revision_number}",
        "specification": tooling_specification(revision_number),
        "cavities": [
            {
                "cavityIdentifier": "C01",
                "toolingApplicabilityGlobalId": applicability_id,
                "structuralState": "enabled",
            }
        ],
        "inserts": [
            {
                "insertCode": "INS-CORE-01",
                "insertVersion": revision_number,
                "toolingApplicabilityGlobalId": applicability_id,
                "model": dict(model_reference),
                "changeoverDuration": measurement("30", "min", "Validated plan"),
                "validationState": "validated",
                "validationReason": "Synthetic model reference validated for runtime proof.",
            }
        ],
        "externalIdentities": [
            external_identity(
                "customer",
                f"CUSTOMER-TOOL-R{revision_number}",
                f"P603-TOOL-R{revision_number}",
            )
        ],
        "designDocumentRevisions": [],
        "reason": f"Controlled synthetic Tooling Revision R{revision_number}.",
    }
    if revision_number > 1:
        payload["expectedVersion"] = revision_number - 1
    return payload


def part_specification_payload() -> dict[str, object]:
    values = (
        ("material_family", "PA66", "PA 66", "P603-MATERIAL"),
        ("grade", "PA66-GF30", "PA66 GF30", "P603-GRADE"),
        ("color", "Industrial black", "Black", "P603-COLOR"),
        ("fda_compliance", "Not required", "N/A", "P603-COMPLIANCE"),
    )
    return {
        "items": [
            {
                "kind": kind,
                "normalizedValue": normalized,
                "rawValue": raw,
                "sourceSystem": "NPI_ONE",
                "sourceObjectId": source_id,
                "effectiveFrom": "2026-08-01",
            }
            for kind, normalized, raw, source_id in values
        ],
        "externalIdentities": [
            external_identity("customer", "PART-SPEC-001", "P603-PART-SPEC")
        ],
    }


def process_chain_payload(
    dedicated_revision_id: str,
    retained_revision_ids: tuple[str, str],
    tooling_revision_id: str,
    *,
    chain_id: str | None = None,
    expected_version: int | None = None,
) -> dict[str, object]:
    retained_one, retained_two = retained_revision_ids
    payload: dict[str, object] = {
        "steps": [
            {
                "stepOrder": 1,
                "processKind": "primary_molding",
                "toolingRevisionGlobalId": tooling_revision_id,
                "inputPartRevisionGlobalIds": [dedicated_revision_id],
                "outputPartRevisionGlobalId": retained_one,
                "machineType": "Synthetic primary molding machine",
                "clampTonnage": measurement("450", "t", "Controlled machine plan"),
            },
            {
                "stepOrder": 2,
                "processKind": "overmold",
                "toolingRevisionGlobalId": tooling_revision_id,
                "inputPartRevisionGlobalIds": [retained_one],
                "outputPartRevisionGlobalId": retained_two,
                "parentStepOrder": 1,
                "machineType": "Synthetic overmold machine",
                "clampTonnage": measurement("300", "t", "Controlled machine plan"),
            },
        ],
        "reason": (
            "Controlled synthetic process-chain successor."
            if chain_id
            else "Controlled synthetic process-chain baseline."
        ),
    }
    if chain_id is not None:
        payload["processChainGlobalId"] = chain_id
    if expected_version is not None:
        payload["expectedVersion"] = expected_version
    return payload


def binding_payload(tooling_revision_id: str) -> dict[str, object]:
    return {
        "toolingRevisionGlobalId": tooling_revision_id,
        "reason": "Bind the physical Set to its exact controlled source Revision.",
    }


def require_uuid(value: object, label: str) -> str:
    require(isinstance(value, str) and str(UUID(value)) == value, f"{label} identity drifted")
    return value


def exact_applicability(values: object, revision_id: str) -> dict[str, Any]:
    require(isinstance(values, list), "P6-03 applicability projection is invalid")
    return predecessor.exact_single(
        [
            item
            for item in values
            if isinstance(item, dict)
            and item.get("part", {}).get("globalId") == revision_id
        ],
        "P6-03 current applicability",
    )


def unavailable(value: object, reason_code: str, label: str) -> None:
    require(
        isinstance(value, dict)
        and value.get("state") == "unavailable"
        and value.get("reasonCode") == reason_code,
        f"{label} unavailable truth drifted",
    )


def assert_revision_item(
    value: object,
    *,
    master_id: str,
    revision_number: int,
) -> dict[str, Any]:
    require(isinstance(value, dict), "P6-03 Tooling Revision is invalid")
    require(
        set(value)
        == {
            "globalId",
            "toolingMasterGlobalId",
            "revisionNumber",
            "revisionLabel",
            "predecessorGlobalId",
            "specification",
            "cavities",
            "inserts",
            "externalIdentities",
            "designDocumentRevisions",
            "reason",
            "snapshotHash",
        }
        and value.get("toolingMasterGlobalId") == master_id
        and value.get("revisionNumber") == revision_number
        and value.get("revisionLabel") == f"R{revision_number}",
        "P6-03 Tooling Revision response drifted",
    )
    require_uuid(value.get("globalId"), "P6-03 Tooling Revision")
    require(
        len(value.get("cavities", [])) == 1
        and len(value.get("inserts", [])) == 1
        and len(value.get("externalIdentities", [])) == 1
        and value.get("designDocumentRevisions") == []
        and isinstance(value.get("snapshotHash"), str)
        and len(value["snapshotHash"]) == 64,
        "P6-03 Tooling Revision controlled content drifted",
    )
    return value


def assert_revision_collection(
    result,
    *,
    project_id: str,
    master_id: str,
    expected_count: int,
) -> dict[str, Any]:
    require(result.status in {200, 201}, "P6-03 revision collection failed")
    require(
        set(result.body)
        == {
            "projectGlobalId",
            "toolingMasterGlobalId",
            "permissions",
            "lifecycle",
            "supplier",
            "erpLocationAndAsset",
            "combinedTrial",
            "items",
        }
        and result.body.get("projectGlobalId") == project_id
        and result.body.get("toolingMasterGlobalId") == master_id
        and result.body.get("permissions") == REVISION_PERMISSIONS,
        "P6-03 revision collection contract drifted",
    )
    unavailable(result.body.get("lifecycle"), "lifecycle_policy_unavailable", "lifecycle")
    unavailable(result.body.get("supplier"), "formal_supplier_unavailable", "supplier")
    unavailable(
        result.body.get("erpLocationAndAsset"),
        "erp_projection_unavailable",
        "ERP projection",
    )
    unavailable(
        result.body.get("combinedTrial"),
        "combined_trial_not_delivered",
        "combined Trial",
    )
    items = result.body.get("items")
    require(
        isinstance(items, list) and len(items) == expected_count,
        "P6-03 revision collection cardinality drifted",
    )
    for index, item in enumerate(items, start=1):
        assert_revision_item(item, master_id=master_id, revision_number=index)
        require(
            item.get("predecessorGlobalId")
            == (None if index == 1 else items[index - 2].get("globalId")),
            "P6-03 Tooling Revision predecessor drifted",
        )
    return result.body


def assert_part_specification(result, project_id: str, part_id: str, revision_id: str):
    require(result.status in {200, 201}, "P6-03 Part specification failed")
    require(
        set(result.body)
        == {
            "projectGlobalId",
            "partGlobalId",
            "partRevision",
            "permissions",
            "automaticImpact",
            "controlledSpecification",
        }
        and result.body.get("projectGlobalId") == project_id
        and result.body.get("partGlobalId") == part_id
        and result.body.get("permissions") == REVISION_PERMISSIONS,
        "P6-03 Part specification context drifted",
    )
    unavailable(
        result.body.get("automaticImpact"),
        "automatic_impact_not_delivered",
        "automatic impact",
    )
    specification = result.body.get("controlledSpecification")
    require(
        isinstance(specification, dict)
        and specification.get("partRevisionGlobalId") == revision_id
        and len(specification.get("items", [])) == 4
        and len(specification.get("externalIdentities", [])) == 1
        and isinstance(specification.get("snapshotHash"), str)
        and len(specification["snapshotHash"]) == 64,
        "P6-03 controlled Part specification drifted",
    )
    return result.body


def assert_chain(value: object, *, version: int) -> dict[str, Any]:
    require(
        isinstance(value, dict)
        and set(value)
        == {
            "globalId",
            "processChainGlobalId",
            "chainVersion",
            "predecessorGlobalId",
            "steps",
            "reason",
            "snapshotHash",
        }
        and value.get("chainVersion") == version
        and len(value.get("steps", [])) == 2,
        "P6-03 Process Chain response drifted",
    )
    require_uuid(value.get("globalId"), "P6-03 Process Chain Revision")
    require_uuid(value.get("processChainGlobalId"), "P6-03 Process Chain")
    require(
        [step.get("stepOrder") for step in value["steps"]] == [1, 2]
        and value["steps"][0].get("processKind") == "primary_molding"
        and value["steps"][1].get("processKind") == "overmold"
        and value["steps"][1].get("parentStepGlobalId")
        == value["steps"][0].get("globalId")
        and isinstance(value.get("snapshotHash"), str)
        and len(value["snapshotHash"]) == 64,
        "P6-03 ordered Process Chain truth drifted",
    )
    return value


def assert_set_binding(
    result,
    *,
    project_id: str,
    master_id: str,
    set_id: str,
    revision_id: str,
) -> dict[str, Any]:
    require(result.status in {200, 201}, "P6-03 Set binding projection failed")
    summary = result.body.get("toolingSet") if "toolingSet" in result.body else None
    if summary is None:
        items = result.body.get("items")
        require(isinstance(items, list), "P6-03 Tooling Set collection is invalid")
        summary = predecessor.exact_single(
            [item for item in items if item.get("globalId") == set_id],
            "bound physical Set",
        )
    require(
        isinstance(summary, dict)
        and summary.get("projectGlobalId") == project_id
        and summary.get("toolingMasterGlobalId") == master_id
        and summary.get("globalId") == set_id,
        "P6-03 bound physical Set identity drifted",
    )
    binding = summary.get("sourceRevision")
    require(
        isinstance(binding, dict)
        and binding.get("toolingMasterGlobalId") == master_id
        and binding.get("toolingSetGlobalId") == set_id
        and binding.get("toolingRevisionGlobalId") == revision_id
        and isinstance(binding.get("snapshotHash"), str)
        and len(binding["snapshotHash"]) == 64,
        "P6-03 exact Set source binding drifted",
    )
    return result.body


def project_context(
    administrator,
    base_url: str,
) -> tuple[str, str, str, tuple[str, str], str, dict[str, str]]:
    project_id, _version = document_runtime.fixture_project(administrator, base_url)
    cockpit = tooling_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}/cockpit",
        query_key="project-reference",
    )
    references = cockpit.body.get("references")
    require(
        cockpit.status == 200 and isinstance(references, list),
        "P6-03 retained Project references are unavailable",
    )
    model_reference = predecessor.exact_single(
        [
            value
            for value in references
            if isinstance(value, dict) and value.get("type") == "customer"
        ],
        "P6-03 Project customer reference",
    )
    require(
        set(model_reference) in (
            {"type", "sourceSystem", "sourceObjectId"},
            {"type", "sourceSystem", "sourceObjectId", "globalId"},
        )
        and model_reference.get("sourceSystem") in {"NPI_ONE", "ERPNEXT"}
        and isinstance(model_reference.get("sourceObjectId"), str)
        and bool(model_reference["sourceObjectId"]),
        "P6-03 Project customer reference drifted",
    )
    insert_model_reference = {
        "sourceSystem": str(model_reference["sourceSystem"]),
        "sourceObjectId": str(model_reference["sourceObjectId"]),
    }
    workspace = tooling_request(
        administrator,
        base_url,
        predecessor.tooling_path(project_id),
        query_key="context",
    )
    require(
        workspace.status == 200
        and set(workspace.body)
        == {
            "project",
            "permissions",
            "masters",
            "requirements",
            "parts",
            "applicability",
            "downstream",
        },
        "P6-03 predecessor workspace is unavailable",
    )
    master_id = require_uuid(
        exact_retained_master(workspace.body.get("masters"), project_id).get("globalId"),
        "P6-03 Tooling Master",
    )
    retained_parts = [item for item in workspace.body.get("parts", []) if item.get("title") != PART_TITLE]
    retained_part = predecessor.exact_single(retained_parts, "retained P6-01 Part")
    retained_revision_rows = predecessor.rows(
        administrator,
        base_url,
        "NPI Engineering Part Revision",
        [["part_global_id", "=", retained_part["globalId"]]],
        ["global_id", "revision_number"],
    )
    retained_revision_ids = tuple(
        str(item["global_id"])
        for item in sorted(retained_revision_rows, key=lambda item: int(item["revision_number"]))
    )
    require(len(retained_revision_ids) == 2, "P6-03 retained Part revision chain drifted")
    sets = tooling_request(
        administrator,
        base_url,
        predecessor.tooling_set_path(project_id, master_id),
        query_key="context-sets",
    )
    require(sets.status == 200, "P6-03 predecessor Tooling Sets are unavailable")
    tooling_set = predecessor.exact_single(
        [item for item in sets.body.get("items", []) if item.get("physicalSerial") == "P6-02-PHYSICAL-001"],
        "P6-03 physical Set",
    )
    return (
        project_id,
        master_id,
        str(retained_part["globalId"]),
        (retained_revision_ids[0], retained_revision_ids[1]),
        require_uuid(tooling_set.get("globalId"), "P6-03 physical Set"),
        insert_model_reference,
    )


def dedicated_part_context(administrator, base_url: str, project_id: str) -> tuple[str, str, str]:
    parts = predecessor.rows(
        administrator,
        base_url,
        "NPI Engineering Part",
        [
            ["originating_project_global_id", "=", project_id],
            ["title", "=", PART_TITLE],
        ],
        ["global_id", "current_revision_global_id"],
    )
    part = predecessor.exact_single(parts, "P6-03 dedicated Part")
    part_id = require_uuid(part.get("global_id"), "P6-03 dedicated Part")
    revision_id = require_uuid(
        part.get("current_revision_global_id"),
        "P6-03 dedicated Part Revision",
    )
    applicability = predecessor.rows(
        administrator,
        base_url,
        "NPI Tooling Applicability",
        [["part_revision_global_id", "=", revision_id]],
        ["global_id", "applicability_version", "effective_from", "effective_to"],
    )
    relationship = predecessor.exact_single(applicability, "P6-03 applicability")
    applicability_id = require_uuid(
        relationship.get("global_id"),
        "P6-03 applicability",
    )
    require(
        relationship.get("applicability_version") == 1
        and str(relationship.get("effective_from")) == "2026-08-01"
        and relationship.get("effective_to") in {None, ""},
        "P6-03 current effective applicability drifted",
    )
    return part_id, revision_id, applicability_id


def verify_idor(
    administrator,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
    *,
    project_id: str,
    master_id: str,
    revision_id: str,
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
        denied = tooling_request(
            unrelated,
            base_url,
            revision_path(project_id, master_id, f"/{revision_id}"),
            query_key="idor-denied",
        )
        absent = tooling_request(
            unrelated,
            base_url,
            revision_path(ABSENT_PROJECT_ID, master_id, f"/{revision_id}"),
            query_key="idor-absent-project",
        )
        validate_problem(denied, 404, "TOOLING_UNAVAILABLE")
        validate_problem(absent, 404, "TOOLING_UNAVAILABLE")
        fields = ("type", "title", "status", "code", "retryable")
        require(
            {key: denied.body.get(key) for key in fields}
            == {key: absent.body.get(key) for key in fields},
            "P6-03 unauthorized and absent Projects are distinguishable",
        )
    finally:
        delete_disposable_user(
            administrator,
            base_url,
            UNRELATED_USER,
            csrf_token,
        )

    projects = predecessor.rows(
        administrator,
        base_url,
        "NPI Engineering Project",
        [["business_code", "=", predecessor.SECOND_PROJECT_CODE]],
        ["global_id"],
    )
    second_project_id = str(predecessor.exact_single(projects, "P6-03 second Project")["global_id"])
    cross_project = tooling_request(
        administrator,
        base_url,
        revision_path(second_project_id, master_id, f"/{revision_id}"),
        query_key="idor-cross-project",
    )
    missing = tooling_request(
        administrator,
        base_url,
        revision_path(project_id, master_id, f"/{ABSENT_OBJECT_ID}"),
        query_key="idor-absent-revision",
    )
    validate_problem(cross_project, 404, "TOOLING_UNAVAILABLE")
    validate_problem(missing, 404, "TOOLING_UNAVAILABLE")
    fields = ("type", "title", "status", "code", "retryable")
    require(
        {key: cross_project.body.get(key) for key in fields}
        == {key: missing.body.get(key) for key in fields},
        "P6-03 cross-Project and absent Revisions are distinguishable",
    )


def persisted_counts(administrator, base_url: str, project_id: str) -> dict[str, int]:
    return {
        doctype: len(
            predecessor.rows(
                administrator,
                base_url,
                doctype,
                [["project_global_id", "=", project_id]],
            )
        )
        for doctype in REVISION_DOCTYPES
    }


def verify_persistence(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    project_id: str,
    revision_ids: tuple[str, str],
    specification_id: str,
    chain_revision_ids: tuple[str, str],
    binding_id: str,
) -> None:
    require(
        persisted_counts(administrator, base_url, project_id)
        == {
            "NPI Tooling Revision": 2,
            "NPI Part Controlled Specification": 1,
            "NPI Tooling Process Chain Revision": 2,
            "NPI Tooling Set Revision Binding": 1,
        },
        "P6-03 persisted immutable cardinality drifted",
    )
    expected_operations = {
        "tooling_revision.create": 2,
        "part_controlled_specification.create": 1,
        "tooling_process_chain_revision.create": 2,
        "tooling_set_revision_binding.create": 1,
    }
    for operation, expected in expected_operations.items():
        receipts = predecessor.rows(
            administrator,
            base_url,
            "NPI Tooling Command Idempotency",
            [["operation", "=", operation]],
            ["actor_user_id", "payload_hash", "response_hash", "sealed"],
        )
        audits = predecessor.rows(
            administrator,
            base_url,
            "NPI Audit Event",
            [["operation", "=", operation]],
            ["result", "trace_id"],
        )
        require(
            len(receipts) == expected
            and all(item.get("actor_user_id") == ACTOR_USER for item in receipts)
            and all(item.get("sealed") == 1 for item in receipts)
            and all(len(str(item.get("payload_hash"))) == 64 for item in receipts)
            and all(len(str(item.get("response_hash"))) == 64 for item in receipts)
            and len(audits) == expected
            and all(item.get("result") == "created" and item.get("trace_id") for item in audits),
            f"P6-03 receipt or audit truth drifted for {operation}",
        )
    immutable = (
        ("NPI Tooling Revision", revision_ids[0]),
        ("NPI Tooling Revision", revision_ids[1]),
        ("NPI Part Controlled Specification", specification_id),
        ("NPI Tooling Process Chain Revision", chain_revision_ids[0]),
        ("NPI Tooling Process Chain Revision", chain_revision_ids[1]),
        ("NPI Tooling Set Revision Binding", binding_id),
    )
    for doctype, name in immutable:
        before = get_resource(administrator, base_url, doctype, name)
        snapshot_hash = before.body.get("data", {}).get("snapshot_hash")
        require(
            before.status == 200
            and isinstance(snapshot_hash, str)
            and len(snapshot_hash) == 64,
            f"P6-03 immutable {doctype} is unavailable",
        )
        rejected_update = update_resource(
            administrator,
            base_url,
            doctype,
            name,
            {"snapshot_hash": "0" * 64},
            csrf_token,
        )
        rejected_delete = delete_resource(
            administrator,
            base_url,
            doctype,
            name,
            csrf_token,
        )
        after = get_resource(administrator, base_url, doctype, name)
        require(
            rejected_update.status in {403, 417}
            and rejected_delete.status in {403, 417}
            and after.status == 200
            and after.body.get("data", {}).get("snapshot_hash") == snapshot_hash,
            f"P6-03 immutable {doctype} accepted generic mutation",
        )


def verify_conflict_rollback(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    project_id: str,
    master_id: str,
    part_id: str,
    part_revision_id: str,
    applicability_id: str,
    retained_revision_ids: tuple[str, str],
    revision_one_id: str,
    revision_two_id: str,
    chain_id: str,
    set_id: str,
    model_reference: dict[str, str],
) -> None:
    before = persisted_counts(administrator, base_url, project_id)
    different_revision = revision_payload(applicability_id, 1, model_reference)
    different_revision["revisionLabel"] = "DIFFERENT"
    conflicts = (
        (
            revision_path(project_id, master_id),
            different_revision,
            REVISION_ONE_KEY,
            "TOOLING_IDEMPOTENCY_CONFLICT",
        ),
        (
            revision_path(project_id, master_id),
            {
                **revision_payload(applicability_id, 2, model_reference),
                "revisionLabel": "R3",
            },
            REVISION_STALE_KEY,
            "TOOLING_VERSION_CONFLICT",
        ),
        (
            part_specification_path(project_id, part_id, part_revision_id),
            part_specification_payload(),
            SPECIFICATION_CONFLICT_KEY,
            "TOOLING_VERSION_CONFLICT",
        ),
        (
            process_chain_path(project_id),
            process_chain_payload(
                part_revision_id,
                retained_revision_ids,
                revision_two_id,
                chain_id=chain_id,
                expected_version=1,
            ),
            CHAIN_STALE_KEY,
            "TOOLING_VERSION_CONFLICT",
        ),
        (
            binding_path(project_id, master_id, set_id),
            binding_payload(revision_one_id),
            BINDING_CONFLICT_KEY,
            "TOOLING_VERSION_CONFLICT",
        ),
    )
    for path, payload, key, code in conflicts:
        result = tooling_request(
            administrator,
            base_url,
            path,
            method="POST",
            payload=payload,
            csrf_token=csrf_token,
            idempotency_key=key,
        )
        validate_problem(result, 409, code)
    require(
        persisted_counts(administrator, base_url, project_id) == before,
        "P6-03 failed commands changed immutable cardinality",
    )


def run_fresh(administrator, base_url: str, csrf_token: str, fixture_password: str) -> dict[str, object]:
    (
        project_id,
        master_id,
        _retained_part_id,
        retained_revision_ids,
        set_id,
        model_reference,
    ) = project_context(administrator, base_url)
    schema = run_bench_fixture(
        "verify_tooling_revision_runtime_schema",
        {"fixture_run_id": FIXTURE_RUN_ID},
    )
    empty_revisions = assert_revision_collection(
        tooling_request(
            administrator,
            base_url,
            revision_path(project_id, master_id),
            query_key="empty-revisions",
        ),
        project_id=project_id,
        master_id=master_id,
        expected_count=0,
    )
    require(empty_revisions["items"] == [], "P6-03 fresh revision collection was not empty")
    guest = tooling_request(
        urllib.request.build_opener(),
        base_url,
        revision_path(project_id, master_id),
        query_key="guest",
    )
    validate_problem(guest, 401, "AUTHENTICATION_REQUIRED")

    part_result = predecessor.command(
        administrator,
        base_url,
        csrf_token,
        f"/api/npi/v1/projects/{project_id}/parts",
        predecessor.part_payload(PART_TITLE, "A"),
        PART_KEY,
    )
    parts = [item for item in part_result.body.get("parts", []) if item.get("title") == PART_TITLE]
    part = predecessor.exact_single(parts, "P6-03 dedicated Part")
    part_id = require_uuid(part.get("globalId"), "P6-03 dedicated Part")
    part_revision_id = require_uuid(
        part.get("currentRevision", {}).get("globalId"),
        "P6-03 dedicated Part Revision",
    )
    applicability_result = predecessor.command(
        administrator,
        base_url,
        csrf_token,
        f"/api/npi/v1/projects/{project_id}/tooling-applicabilities",
        predecessor.applicability_payload(
            master_id,
            part_revision_id,
            effective_from="2026-08-01",
            effective_to=None,
        ),
        APPLICABILITY_KEY,
    )
    applicability = exact_applicability(
        applicability_result.body.get("applicability", []),
        part_revision_id,
    )
    applicability_id = require_uuid(
        applicability.get("globalId"),
        "P6-03 current applicability",
    )

    revision_one = command(
        administrator,
        base_url,
        csrf_token,
        revision_path(project_id, master_id),
        revision_payload(applicability_id, 1, model_reference),
        REVISION_ONE_KEY,
    )
    revision_one_value = assert_revision_item(
        revision_one.body.get("revision"),
        master_id=master_id,
        revision_number=1,
    )
    revision_one_id = str(revision_one_value["globalId"])
    revision_two = command(
        administrator,
        base_url,
        csrf_token,
        revision_path(project_id, master_id),
        revision_payload(applicability_id, 2, model_reference),
        REVISION_TWO_KEY,
    )
    revision_two_value = assert_revision_item(
        revision_two.body.get("revision"),
        master_id=master_id,
        revision_number=2,
    )
    revision_two_id = str(revision_two_value["globalId"])
    require(
        revision_two_value.get("predecessorGlobalId") == revision_one_id,
        "P6-03 immutable successor did not retain its predecessor",
    )

    specification = command(
        administrator,
        base_url,
        csrf_token,
        part_specification_path(project_id, part_id, part_revision_id),
        part_specification_payload(),
        SPECIFICATION_KEY,
    )
    specification_context = assert_part_specification(
        specification,
        project_id,
        part_id,
        part_revision_id,
    )
    specification_id = require_uuid(
        specification_context["controlledSpecification"].get("globalId"),
        "P6-03 Part Controlled Specification",
    )

    chain_one = command(
        administrator,
        base_url,
        csrf_token,
        process_chain_path(project_id),
        process_chain_payload(
            part_revision_id,
            retained_revision_ids,
            revision_one_id,
        ),
        CHAIN_ONE_KEY,
    )
    chain_one_value = assert_chain(chain_one.body, version=1)
    chain_id = str(chain_one_value["processChainGlobalId"])
    chain_one_id = str(chain_one_value["globalId"])
    chain_two = command(
        administrator,
        base_url,
        csrf_token,
        process_chain_path(project_id),
        process_chain_payload(
            part_revision_id,
            retained_revision_ids,
            revision_two_id,
            chain_id=chain_id,
            expected_version=1,
        ),
        CHAIN_TWO_KEY,
    )
    chain_two_value = assert_chain(chain_two.body, version=2)
    chain_two_id = str(chain_two_value["globalId"])
    require(
        chain_two_value.get("predecessorGlobalId") == chain_one_id,
        "P6-03 Process Chain successor did not retain its predecessor",
    )

    binding = command(
        administrator,
        base_url,
        csrf_token,
        binding_path(project_id, master_id, set_id),
        binding_payload(revision_two_id),
        BINDING_KEY,
    )
    assert_set_binding(
        binding,
        project_id=project_id,
        master_id=master_id,
        set_id=set_id,
        revision_id=revision_two_id,
    )
    binding_id = require_uuid(
        binding.body["toolingSet"]["sourceRevision"].get("globalId"),
        "P6-03 Set Revision Binding",
    )

    collection = assert_revision_collection(
        tooling_request(
            administrator,
            base_url,
            revision_path(project_id, master_id),
            query_key="retained-revisions",
        ),
        project_id=project_id,
        master_id=master_id,
        expected_count=2,
    )
    for value in collection["items"]:
        detail = tooling_request(
            administrator,
            base_url,
            revision_path(project_id, master_id, f"/{value['globalId']}"),
            query_key=f"revision-{value['revisionNumber']}",
        )
        require(
            detail.status == 200
            and set(detail.body)
            == {
                "projectGlobalId",
                "permissions",
                "lifecycle",
                "supplier",
                "erpLocationAndAsset",
                "combinedTrial",
                "revision",
            }
            and detail.body.get("revision") == value,
            "P6-03 Tooling Revision detail drifted",
        )
    chains = tooling_request(
        administrator,
        base_url,
        process_chain_path(project_id),
        query_key="retained-chains",
    )
    require(
        chains.status == 200
        and set(chains.body) == {"projectGlobalId", "permissions", "combinedTrial", "items"}
        and chains.body.get("permissions") == REVISION_PERMISSIONS
        and len(chains.body.get("items", [])) == 2,
        "P6-03 Process Chain collection drifted",
    )
    unavailable(
        chains.body.get("combinedTrial"),
        "combined_trial_not_delivered",
        "combined Trial",
    )
    for version, value in enumerate(chains.body["items"], start=1):
        assert_chain(value, version=version)
        detail = tooling_request(
            administrator,
            base_url,
            process_chain_path(project_id, f"/{value['globalId']}"),
            query_key=f"chain-{version}",
        )
        require(detail.status == 200 and detail.body == value, "P6-03 Process Chain detail drifted")
    set_collection = tooling_request(
        administrator,
        base_url,
        predecessor.tooling_set_path(project_id, master_id),
        query_key="bound-sets",
    )
    assert_set_binding(
        set_collection,
        project_id=project_id,
        master_id=master_id,
        set_id=set_id,
        revision_id=revision_two_id,
    )

    verify_idor(
        administrator,
        base_url,
        csrf_token,
        fixture_password,
        project_id=project_id,
        master_id=master_id,
        revision_id=revision_one_id,
    )
    verify_persistence(
        administrator,
        base_url,
        csrf_token,
        project_id=project_id,
        revision_ids=(revision_one_id, revision_two_id),
        specification_id=specification_id,
        chain_revision_ids=(chain_one_id, chain_two_id),
        binding_id=binding_id,
    )
    verify_conflict_rollback(
        administrator,
        base_url,
        csrf_token,
        project_id=project_id,
        master_id=master_id,
        part_id=part_id,
        part_revision_id=part_revision_id,
        applicability_id=applicability_id,
        retained_revision_ids=retained_revision_ids,
        revision_one_id=revision_one_id,
        revision_two_id=revision_two_id,
        chain_id=chain_id,
        set_id=set_id,
        model_reference=model_reference,
    )
    return {
        "bindingGlobalId": binding_id,
        "doctypeCount": schema["doctypeCount"],
        "fixtureRunId": FIXTURE_RUN_ID,
        "partControlledSpecificationGlobalId": specification_id,
        "processChainGlobalId": chain_id,
        "processChainRevisionCount": 2,
        "toolingRevisionCount": 2,
    }


def replay_inputs(administrator, base_url: str):
    (
        project_id,
        master_id,
        _retained_part_id,
        retained_revision_ids,
        set_id,
        model_reference,
    ) = project_context(administrator, base_url)
    part_id, part_revision_id, applicability_id = dedicated_part_context(
        administrator,
        base_url,
        project_id,
    )
    revisions = assert_revision_collection(
        tooling_request(
            administrator,
            base_url,
            revision_path(project_id, master_id),
            query_key="replay-revisions",
        ),
        project_id=project_id,
        master_id=master_id,
        expected_count=2,
    )["items"]
    chains_result = tooling_request(
        administrator,
        base_url,
        process_chain_path(project_id),
        query_key="replay-chains",
    )
    require(chains_result.status == 200 and len(chains_result.body.get("items", [])) == 2, "P6-03 replay chains drifted")
    chains = chains_result.body["items"]
    revision_details = []
    for index, revision in enumerate(revisions, start=1):
        detail = tooling_request(
            administrator,
            base_url,
            revision_path(project_id, master_id, f"/{revision['globalId']}"),
            query_key=f"replay-revision-detail-{index}",
        )
        require(detail.status == 200, "P6-03 replay revision detail is unavailable")
        revision_details.append(detail.body)
    specification = tooling_request(
        administrator,
        base_url,
        part_specification_path(project_id, part_id, part_revision_id),
        query_key="replay-part-specification",
    )
    binding = tooling_request(
        administrator,
        base_url,
        predecessor.tooling_set_path(project_id, master_id, f"/{set_id}"),
        query_key="replay-set-binding",
    )
    require(
        specification.status == 200 and binding.status == 200,
        "P6-03 replay context is unavailable",
    )
    return (
        project_id,
        master_id,
        part_id,
        part_revision_id,
        applicability_id,
        model_reference,
        retained_revision_ids,
        set_id,
        revisions,
        chains,
        revision_details,
        specification.body,
        binding.body,
    )


def run_replay(administrator, base_url: str, csrf_token: str) -> None:
    (
        project_id,
        master_id,
        part_id,
        part_revision_id,
        applicability_id,
        model_reference,
        retained_revision_ids,
        set_id,
        revisions,
        chains,
        revision_details,
        specification_body,
        binding_body,
    ) = replay_inputs(administrator, base_url)
    commands = (
        (
            revision_path(project_id, master_id),
            revision_payload(applicability_id, 1, model_reference),
            REVISION_ONE_KEY,
            revision_details[0],
        ),
        (
            revision_path(project_id, master_id),
            revision_payload(applicability_id, 2, model_reference),
            REVISION_TWO_KEY,
            revision_details[1],
        ),
        (
            part_specification_path(project_id, part_id, part_revision_id),
            part_specification_payload(),
            SPECIFICATION_KEY,
            specification_body,
        ),
        (
            process_chain_path(project_id),
            process_chain_payload(
                part_revision_id,
                retained_revision_ids,
                str(revisions[0]["globalId"]),
            ),
            CHAIN_ONE_KEY,
            chains[0],
        ),
        (
            process_chain_path(project_id),
            process_chain_payload(
                part_revision_id,
                retained_revision_ids,
                str(revisions[1]["globalId"]),
                chain_id=str(chains[0]["processChainGlobalId"]),
                expected_version=1,
            ),
            CHAIN_TWO_KEY,
            chains[1],
        ),
        (
            binding_path(project_id, master_id, set_id),
            binding_payload(str(revisions[1]["globalId"])),
            BINDING_KEY,
            binding_body,
        ),
    )
    before = persisted_counts(administrator, base_url, project_id)
    for path, payload, key, exact_body in commands:
        replay = command(administrator, base_url, csrf_token, path, payload, key)
        require(
            replay.headers.get("Idempotency-Replayed") == "true",
            f"P6-03 cross-process replay was not declared for {key}",
        )
        require(replay.body == exact_body, f"P6-03 replay response drifted for {key}")
    require(
        persisted_counts(administrator, base_url, project_id) == before,
        "P6-03 cross-process replay changed immutable cardinality",
    )


def route_disable_probe(administrator, base_url: str, expected_mode: str) -> None:
    (
        project_id,
        master_id,
        _part_id,
        _retained_revisions,
        set_id,
        _model_reference,
    ) = project_context(administrator, base_url)
    revisions = tooling_request(
        administrator,
        base_url,
        revision_path(project_id, master_id),
        query_key=f"route-{expected_mode}",
    )
    cockpit = tooling_request(
        administrator,
        base_url,
        predecessor.tooling_path(project_id),
        query_key=f"cockpit-{expected_mode}",
    )
    sets = tooling_request(
        administrator,
        base_url,
        predecessor.tooling_set_path(project_id, master_id),
        query_key=f"sets-{expected_mode}",
    )
    require(cockpit.status == 200 and sets.status == 200, "P6-03 switch changed P6-01/P6-02 routes")
    source_set = predecessor.exact_single(
        [item for item in sets.body.get("items", []) if item.get("globalId") == set_id],
        "P6-03 route-probe physical Set",
    )
    if expected_mode == "disabled":
        validate_problem(revisions, 503, "TOOLING_REVISION_ROUTES_DISABLED")
        unavailable(
            cockpit.body.get("downstream", {}).get("revision"),
            "tooling_revision_not_delivered",
            "P6-03 cockpit capability",
        )
        unavailable(
            source_set.get("sourceRevision"),
            "tooling_revision_not_delivered",
            "P6-03 Set source projection",
        )
        return
    collection = assert_revision_collection(
        revisions,
        project_id=project_id,
        master_id=master_id,
        expected_count=2,
    )
    require(
        cockpit.body.get("downstream", {}).get("revision")
        == {
            "state": "available",
            "reasonCode": "tooling_revision_available",
            "revisionCount": 2,
        },
        "P6-03 recovered cockpit capability drifted",
    )
    assert_set_binding(
        sets,
        project_id=project_id,
        master_id=master_id,
        set_id=set_id,
        revision_id=str(collection["items"][1]["globalId"]),
    )


def verify_tooling_revision_runtime_schema(fixture_run_id: str) -> dict[str, object]:
    import frappe

    document_runtime._validated_runtime_site()
    require(fixture_run_id == FIXTURE_RUN_ID, "P6-03 schema fixture namespace drifted")
    required_fields = {
        "NPI Tooling Revision": {
            "global_id",
            "revision_key_hash",
            "tooling_master_global_id",
            "revision_number",
            "predecessor_global_id",
            "revision_snapshot",
            "snapshot_hash",
        },
        "NPI Part Controlled Specification": {
            "global_id",
            "specification_key_hash",
            "part_global_id",
            "part_revision_global_id",
            "specification_snapshot",
            "snapshot_hash",
        },
        "NPI Tooling Process Chain Revision": {
            "global_id",
            "process_chain_global_id",
            "version_key_hash",
            "chain_version",
            "predecessor_global_id",
            "chain_snapshot",
            "snapshot_hash",
        },
        "NPI Tooling Set Revision Binding": {
            "global_id",
            "binding_key_hash",
            "tooling_set_global_id",
            "tooling_revision_global_id",
            "binding_snapshot",
            "snapshot_hash",
        },
    }
    for doctype in REVISION_DOCTYPES:
        require(frappe.db.table_exists(doctype), f"P6-03 table is unavailable: {doctype}")
        fields = {field.fieldname for field in frappe.get_meta(doctype, cached=False).fields}
        require(required_fields[doctype] <= fields, f"P6-03 metadata is incomplete for {doctype}")
    return {
        "doctypeCount": len(REVISION_DOCTYPES),
        "fixtureRunId": fixture_run_id,
        "metadataSynchronized": True,
        "runtimeMarker": RUNTIME_MARKER,
    }


def run_bench_fixture(method: str, kwargs: dict[str, object]) -> dict[str, Any]:
    require(method == "verify_tooling_revision_runtime_schema", "P6-03 Bench fixture is unavailable")
    require(
        BENCH_PATH.is_dir()
        and not BENCH_PATH.is_symlink()
        and BENCH_PATH.resolve() == BENCH_PATH,
        "P6-03 verifier requires the fixed physical Bench",
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
    environment["PYTHONPATH"] = str(ROOT) if not current_pythonpath else f"{ROOT}{os.pathsep}{current_pythonpath}"
    completed = subprocess.run(
        [
            str(BENCH_PATH / "env" / "bin" / "python"),
            str(ROOT / "scripts" / "verify_tooling_revision_runtime.py"),
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
    require(completed.returncode == 0, f"P6-03 Bench fixture failed: {method}")
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    require(bool(lines), f"P6-03 Bench fixture was silent: {method}")
    result = json.loads(lines[-1])
    require(isinstance(result, dict), "P6-03 Bench fixture result is invalid")
    return result


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    require(method == "verify_tooling_revision_runtime_schema", "P6-03 Bench fixture is unavailable")
    import frappe

    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    try:
        frappe.set_user(ACTOR_USER)
        result = verify_tooling_revision_runtime_schema(**kwargs)
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the real cumulative P6-03 Tooling Revision runtime.")
    parser.add_argument("--base-url")
    parser.add_argument("--bench-fixture", choices=("verify_tooling_revision_runtime_schema",))
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
            "P6-03 Bench fixture arguments are invalid",
        )
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "P6-03 fixture kwargs are invalid")
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return
    require(
        isinstance(arguments.base_url, str)
        and arguments.fixture_kwargs is None
        and document_runtime.CALLER_SUPPLIED_FIXTURE_RUN_ID is not None,
        "P6-03 runtime base URL and fixture namespace are required",
    )
    administrator_password = secret_from_environment("NPI_RUNTIME_ADMINISTRATOR_PASSWORD")
    fixture_password = secret_from_environment("NPI_RUNTIME_FIXTURE_PASSWORD")
    base_url = validate_local_fixture_inputs(arguments.base_url, ACTOR_USER, UNRELATED_USER)
    require(
        FIXTURE_RUN_ID != "0" * 32 and UNRELATED_USER.endswith("@example.invalid"),
        "P6-03 fixture identity drifted",
    )
    administrator = login(base_url, ACTOR_USER, administrator_password)
    csrf_token = bootstrap_csrf(administrator, base_url, ACTOR_USER)
    require(
        int(arguments.route_disable_probe is not None) + int(arguments.replay_only) <= 1,
        "P6-03 runtime modes are mutually exclusive",
    )
    if arguments.route_disable_probe is not None:
        route_disable_probe(administrator, base_url, arguments.route_disable_probe)
        print(json.dumps({"routeMode": arguments.route_disable_probe}, sort_keys=True))
        return
    if arguments.replay_only:
        run_replay(administrator, base_url, csrf_token)
        print(json.dumps({"crossProcessReplay": True, "fixtureRunId": FIXTURE_RUN_ID}, sort_keys=True))
        print("local Frappe Tooling Revision runtime replay verification passed")
        return
    evidence = run_fresh(administrator, base_url, csrf_token, fixture_password)
    print(json.dumps(evidence, sort_keys=True))
    print("local Frappe Tooling Revision runtime verification passed")


if __name__ == "__main__":
    main()
