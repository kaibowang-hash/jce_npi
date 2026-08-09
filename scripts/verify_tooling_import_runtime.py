from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import verify_document_runtime as document_runtime
import verify_tooling_acceptance_runtime as predecessor
import verify_tooling_runtime as tooling_runtime
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
UNRELATED_USER = f"npi-tooling-import-{FIXTURE_RUN_ID[:12]}-unrelated@example.invalid"
ABSENT_PROJECT_ID = "00000000-0000-4000-8000-000000000031"
ABSENT_BATCH_ID = "00000000-0000-4000-8000-000000000032"
IMPORT_TARGET_DIAGNOSTIC_CODES = frozenset(
    {
        "P607_IMPORT_TARGET_ROOT_INSERT",
        "P607_IMPORT_TARGET_REVISION_INSERT",
        "P607_IMPORT_TARGET_ROOT_ADVANCE",
        "P607_IMPORT_TARGET_ROW_RESULT_INSERT",
        "P607_IMPORT_TARGET_BINDING_INSERT",
    }
)
CORRECTION_DIAGNOSTIC_CODES = frozenset(
    {
        "P607_CORRECTION_RECEIPT_INSERT",
        "P607_CORRECTION_FILE_SAVE",
        "P607_CORRECTION_ARTIFACT_INSERT",
        "P607_CORRECTION_RESPONSE_BUILD",
        "P607_CORRECTION_AUDIT_APPEND",
        "P607_CORRECTION_RECEIPT_SEAL",
    }
)
CORRECTION_VALIDATION_DIAGNOSTIC_CODES = frozenset(
    {
        "P607_CORRECTION_ARTIFACT_SNAPSHOT_VALIDATE",
        "P607_CORRECTION_ARTIFACT_PROJECTION_VALIDATE",
        "P607_CORRECTION_ARTIFACT_JOB_VALIDATE",
        "P607_CORRECTION_ARTIFACT_FILE_VALIDATE",
    }
)
CORRECTION_DOWNLOAD_DIAGNOSTIC_CODES = frozenset(
    {
        "P607_CORRECTION_DOWNLOAD_CONTENT_VALIDATE",
        "P607_CORRECTION_DOWNLOAD_PRIVACY_VALIDATE",
        "P607_CORRECTION_DOWNLOAD_FILE_ID_VALIDATE",
        "P607_CORRECTION_DOWNLOAD_FILE_NAME_VALIDATE",
        "P607_CORRECTION_DOWNLOAD_FILE_SIZE_VALIDATE",
        "P607_CORRECTION_DOWNLOAD_SIZE_VALIDATE",
        "P607_CORRECTION_DOWNLOAD_DIGEST_VALIDATE",
    }
)
RECONCILIATION_DIAGNOSTIC_CODES = frozenset(
    {
        "P607_RECONCILIATION_SNAPSHOT_BUILD",
        "P607_RECONCILIATION_RESPONSE_BUILD",
        "P607_RECONCILIATION_RECEIPT_INSERT",
        "P607_RECONCILIATION_REVISION_INSERT",
        "P607_RECONCILIATION_AUDIT_APPEND",
        "P607_RECONCILIATION_RECEIPT_SEAL",
    }
)
RECONCILIATION_VALIDATION_DIAGNOSTIC_CODES = frozenset(
    {
        "P607_RECONCILIATION_SNAPSHOT_VALIDATE",
        "P607_RECONCILIATION_PROJECTION_VALIDATE",
        "P607_RECONCILIATION_ITEMS_VALIDATE",
        "P607_RECONCILIATION_JOB_VALIDATE",
    }
)
RECONCILIATION_DOMAIN_PATHS = frozenset(
    {
        "rowResultGlobalId",
        "targetObjectType",
        "targetGlobalId",
        "expectedSnapshotHash",
        "observedSnapshotHash",
        "downstreamReferenceCount",
        "state",
        "global_id",
        "job_global_id",
        "request_id",
        "jobSnapshotHash",
        "kind",
        "items",
        "createdByUserId",
        "createdAt",
        "traceId",
    }
)

FIXTURES = (
    {
        "fileName": "p6-07-synthetic-title-row-deleted.xlsx",
        "sha256": "b807aca4ef6776a0ad6e8eada1c8291b3a13dbe32724828d33661d67bc8e684f",
        "titleRowCount": 1,
        "headerRow": 2,
        "rollbackMode": "allowed",
    },
    {
        "fileName": "p6-07-synthetic-title-rows-inserted.xlsx",
        "sha256": "f1c67a991bb59cffbee208fcc786ee44de342d3a2cf56da31d3422c9026459b4",
        "titleRowCount": 3,
        "headerRow": 4,
        "rollbackMode": "denied",
    },
)

IMPORT_DOCTYPES = (
    "NPI Tooling Import Batch",
    "NPI Tooling Import Inspection Revision",
    "NPI Tooling Import Mapping Revision",
    "NPI Tooling Import Preview Revision",
    "NPI Tooling Import Mapping Activation",
    "NPI Tooling Import Job",
    "NPI Tooling Import Row Result",
    "NPI Tooling Import Target Binding",
    "NPI Tooling Import Correction Artifact",
    "NPI Tooling Import Reconciliation Revision",
    "NPI Tooling Import Command Idempotency",
)


def deterministic_uuid(label: str) -> str:
    seeded = uuid5(NAMESPACE_URL, f"npi-one:p6-07:{FIXTURE_RUN_ID}:{label}")
    return str(UUID(int=seeded.int, version=4))


def imports_path(project_id: str) -> str:
    return f"/api/npi/v1/projects/{project_id}/tooling-imports"


def batch_path(project_id: str, batch_id: str) -> str:
    return f"{imports_path(project_id)}/{batch_id}"


def inspection_path(project_id: str, batch_id: str) -> str:
    return f"{batch_path(project_id, batch_id)}/inspections"


def mapping_path(project_id: str, batch_id: str) -> str:
    return f"{batch_path(project_id, batch_id)}/mapping-proposals"


def preview_path(project_id: str, batch_id: str) -> str:
    return f"{batch_path(project_id, batch_id)}/previews"


def confirmation_path(project_id: str, batch_id: str, preview_id: str) -> str:
    return f"{preview_path(project_id, batch_id)}/{preview_id}/confirmations"


def execute_path(project_id: str, batch_id: str, preview_id: str) -> str:
    return f"{preview_path(project_id, batch_id)}/{preview_id}:execute"


def jobs_path(project_id: str, batch_id: str) -> str:
    return f"{batch_path(project_id, batch_id)}/jobs"


def job_path(project_id: str, batch_id: str, job_id: str) -> str:
    return f"{jobs_path(project_id, batch_id)}/{job_id}"


def retry_path(project_id: str, batch_id: str, job_id: str) -> str:
    return f"{job_path(project_id, batch_id, job_id)}:retry"


def corrections_path(project_id: str, batch_id: str, job_id: str) -> str:
    return f"{job_path(project_id, batch_id, job_id)}/correction-artifacts"


def correction_content_path(
    project_id: str,
    batch_id: str,
    job_id: str,
    artifact_id: str,
) -> str:
    return f"{corrections_path(project_id, batch_id, job_id)}/{artifact_id}:content"


def reconcile_path(project_id: str, batch_id: str, job_id: str) -> str:
    return f"{job_path(project_id, batch_id, job_id)}:reconcile"


def rollback_evaluation_path(project_id: str, batch_id: str, job_id: str) -> str:
    return f"{job_path(project_id, batch_id, job_id)}:evaluate-rollback"


def rollback_path(project_id: str, batch_id: str, job_id: str) -> str:
    return f"{job_path(project_id, batch_id, job_id)}:rollback"


def tooling_request(*args, query_key: str = "query", **kwargs):
    return predecessor.tooling_request(
        *args,
        query_key=f"p607-{query_key}",
        **kwargs,
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
    )
    if result.status != 201 and key.endswith("-correction"):
        diagnostic = tooling_runtime._sanitized_server_diagnostic(
            result.trace_id,
            CORRECTION_VALIDATION_DIAGNOSTIC_CODES,
        )
        if diagnostic is None:
            diagnostic = tooling_runtime._sanitized_server_diagnostic(
                result.trace_id,
                CORRECTION_DIAGNOSTIC_CODES,
            )
        if diagnostic is not None:
            exception_type, code, trace_id = diagnostic
            raise RuntimeError(
                f"[diagnostic_code={code}; exception_type={exception_type}; "
                f"trace_id={trace_id}]"
            )
    if result.status != 201 and key.endswith("-reconcile"):
        field_path = reconciliation_domain_path(result.body)
        if field_path is not None:
            raise RuntimeError(
                f"[diagnostic_field={field_path}; trace_id={result.trace_id}]"
            )
        diagnostic = tooling_runtime._sanitized_server_diagnostic(
            result.trace_id,
            RECONCILIATION_VALIDATION_DIAGNOSTIC_CODES,
        )
        if diagnostic is None:
            diagnostic = tooling_runtime._sanitized_server_diagnostic(
                result.trace_id,
                RECONCILIATION_DIAGNOSTIC_CODES,
            )
        if diagnostic is not None:
            exception_type, code, trace_id = diagnostic
            raise RuntimeError(
                f"[diagnostic_code={code}; exception_type={exception_type}; "
                f"trace_id={trace_id}]"
            )
    require(
        result.status == 201,
        (
            f"P6-07 command {key} returned HTTP {result.status} with problem code "
            f"{result.body.get('code', 'UNAVAILABLE')}"
        ),
    )
    require(
        result.headers.get("Idempotency-Replayed") in {"true", "false"},
        "P6-07 replay header is invalid",
    )
    return result


def reconciliation_domain_path(problem: object) -> str | None:
    if not isinstance(problem, dict):
        return None
    field_errors = problem.get("fieldErrors")
    if not isinstance(field_errors, list) or len(field_errors) != 1:
        return None
    field_error = field_errors[0]
    if not isinstance(field_error, dict):
        return None
    path = field_error.get("path")
    return path if isinstance(path, str) and path in RECONCILIATION_DOMAIN_PATHS else None


def rows(administrator, base_url: str, doctype: str, filters, fields=None):
    return predecessor.rows(administrator, base_url, doctype, filters, fields)


def exact_single(values, label: str):
    return predecessor.exact_single(values, label)


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


def project_context(administrator, base_url: str) -> dict[str, object]:
    context = dict(predecessor.project_context(administrator, base_url))
    project_id = str(context["projectId"])
    cockpit = tooling_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}/cockpit",
        query_key="project-customer",
    )
    references = cockpit.body.get("references")
    require(
        cockpit.status == 200 and isinstance(references, list),
        "P6-07 Project customer references are unavailable",
    )
    customer = exact_single(
        [
            item
            for item in references
            if isinstance(item, dict) and item.get("type") == "customer"
        ],
        "P6-07 synthetic customer scope",
    )
    customer_scope_id = customer.get("sourceObjectId")
    require(
        isinstance(customer_scope_id, str) and bool(customer_scope_id),
        "P6-07 synthetic customer scope drifted",
    )
    context["customerScopeId"] = customer_scope_id
    return context


def scenario_key(index: int, operation: str) -> str:
    return f"p6-07-runtime-r{index}-{FIXTURE_RUN_ID}-{operation}"


def batch_payload(file_evidence: dict[str, object], customer_scope_id: str) -> dict[str, object]:
    return {
        "customerScopeId": customer_scope_id,
        "fileRevisionGlobalId": file_evidence["fileRevisionGlobalId"],
        "fileOptimisticVersion": file_evidence["fileOptimisticVersion"],
        "frappeContentHash": file_evidence["frappeContentHash"],
        "sha256": file_evidence["sha256"],
    }


def assert_source(value: object, *, fixture: dict[str, object], project_id: str) -> dict[str, object]:
    require(isinstance(value, dict), "P6-07 source payload is invalid")
    require(
        value.get("projectGlobalId") == project_id
        and value.get("fileName") == fixture["fileName"]
        and value.get("sha256") == fixture["sha256"]
        and value.get("mimeType")
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "P6-07 exact synthetic source truth drifted",
    )
    require_uuid(value.get("batchGlobalId"), "P6-07 batch")
    require_hash(value.get("snapshotHash"), "P6-07 source")
    return value


def assert_inspection(value: object, *, fixture: dict[str, object]) -> dict[str, object]:
    require(isinstance(value, dict), "P6-07 inspection payload is invalid")
    columns = value.get("columns")
    regions = value.get("regions")
    formula_errors = value.get("formulaErrors")
    anchors = value.get("imageAnchors")
    require(
        value.get("worksheetName") == "Synthetic Tooling List"
        and value.get("headerRow") == fixture["headerRow"]
        and isinstance(columns, list)
        and len(columns) == 43
        and isinstance(regions, list)
        and len(regions) >= 2
        and isinstance(formula_errors, list)
        and len(formula_errors) == 1
        and isinstance(anchors, list)
        and len(anchors) == 2,
        "P6-07 position-independent inspection truth drifted",
    )
    require_uuid(value.get("globalId"), "P6-07 inspection")
    require_hash(value.get("snapshotHash"), "P6-07 inspection")
    return value


def assert_mapping(
    value: object,
    *,
    expected_state: str,
    expected_version: int,
) -> dict[str, object]:
    require(isinstance(value, dict), "P6-07 mapping payload is invalid")
    require(
        value.get("state") == expected_state
        and value.get("mappingVersion") == expected_version
        and isinstance(value.get("entries"), list)
        and len(value["entries"]) == 43,
        "P6-07 exact 43-column mapping truth drifted",
    )
    require_uuid(value.get("globalId"), "P6-07 mapping revision")
    require_hash(value.get("snapshotHash"), "P6-07 mapping revision")
    return value


def assert_preview(
    value: object,
    *,
    expected_version: int,
    expected_eligible: bool,
) -> dict[str, object]:
    require(isinstance(value, dict), "P6-07 preview payload is invalid")
    preview_rows = value.get("rows")
    require(
        value.get("previewVersion") == expected_version
        and value.get("mappingState") == "approved_fixture"
        and value.get("executionEligible") is expected_eligible
        and isinstance(preview_rows, list)
        and len(preview_rows) == 3,
        "P6-07 preview truth drifted",
    )
    require_uuid(value.get("globalId"), "P6-07 preview revision")
    require_uuid(value.get("previewGlobalId"), "P6-07 preview chain")
    require_hash(value.get("snapshotHash"), "P6-07 preview revision")
    return value


def preview_confirmations(
    preview: dict[str, object],
    inspection: dict[str, object],
    context: dict[str, object],
) -> list[dict[str, object]]:
    anchors = {
        int(item["candidateSourceRow"]): item
        for item in inspection["imageAnchors"]
        if isinstance(item, dict) and item.get("requiresConfirmation") is True
    }
    confirmations: list[dict[str, object]] = []
    for row in preview["rows"]:
        if not isinstance(row, dict) or row.get("requiresConfirmation") is not True:
            continue
        worksheet = str(row["worksheetName"])
        source_row = int(row["sourceRow"])
        reasons = set(row.get("reasonCodes", []))
        if "image_confirmation_required" in reasons:
            anchor = anchors.get(source_row)
            require(anchor is not None, "P6-07 image confirmation anchor drifted")
            confirmations.append(
                {
                    "kind": "image_anchor",
                    "worksheetName": worksheet,
                    "sourceRow": source_row,
                    "anchorKey": anchor["anchorKey"],
                    "selectedTargetObject": "tooling_master",
                    "selectedTargetGlobalId": context["masterId"],
                    "selectedTargetSnapshotHash": context["masterSnapshotHash"],
                    "reason": "Synthetic fixture image bound to the exact controlled Tooling Master.",
                }
            )
        if "relationship_confirmation_required" in reasons:
            confirmations.append(
                {
                    "kind": "relationship",
                    "worksheetName": worksheet,
                    "sourceRow": source_row,
                    "anchorKey": None,
                    "selectedTargetObject": "tooling_master",
                    "selectedTargetGlobalId": context["masterId"],
                    "selectedTargetSnapshotHash": context["masterSnapshotHash"],
                    "reason": "Synthetic relationship bound to the exact controlled Tooling Master.",
                }
            )
    require(bool(confirmations), "P6-07 confirmation fixture is unexpectedly empty")
    return confirmations


def assert_job(
    value: object,
    *,
    expected_state: str,
    expected_attempt: int,
) -> dict[str, object]:
    require(isinstance(value, dict), "P6-07 job payload is invalid")
    results = value.get("rowResults")
    require(
        value.get("state") == expected_state
        and value.get("attempt") == expected_attempt
        and isinstance(value.get("optimisticVersion"), int)
        and isinstance(results, list),
        f"P6-07 import job did not reach {expected_state}",
    )
    require_uuid(value.get("globalId"), "P6-07 import job")
    require_hash(value.get("snapshotHash"), "P6-07 import job")
    return value


def latest_results(job: dict[str, object]) -> list[dict[str, object]]:
    latest: dict[tuple[str, int], dict[str, object]] = {}
    for item in job["rowResults"]:
        require(isinstance(item, dict), "P6-07 row result payload is invalid")
        identity = (str(item.get("worksheetName")), int(item.get("sourceRow", 0)))
        retained = latest.get(identity)
        if retained is None or int(item.get("attempt", 0)) > int(
            retained.get("attempt", 0)
        ):
            latest[identity] = item
    return list(latest.values())


def partial_row_diagnostic(results: list[dict[str, object]]) -> str:
    """Return only closed states/codes and one allowlisted server diagnostic."""

    structure = []
    diagnostic = None
    for item in results:
        fields = item.get("fieldResults")
        codes = (
            sorted(
                str(field.get("resultCode"))
                for field in fields
                if isinstance(field, dict)
                and isinstance(field.get("resultCode"), str)
            )
            if isinstance(fields, list)
            else []
        )
        structure.append({"state": item.get("state"), "resultCodes": codes})
        trace_id = item.get("traceId")
        candidate = tooling_runtime._sanitized_server_diagnostic(
            str(trace_id) if isinstance(trace_id, str) else None,
            IMPORT_TARGET_DIAGNOSTIC_CODES,
        )
        if diagnostic is None and candidate is not None:
            diagnostic = candidate
    suffix = json.dumps(structure, separators=(",", ":"), sort_keys=True)
    if diagnostic is None:
        return suffix
    exception_type, code, trace_id = diagnostic
    return (
        f"{suffix} [diagnostic_code={code}; exc_type={exception_type}; "
        f"trace_id={trace_id}]"
    )


def correction_entries(
    job: dict[str, object],
    corrected_part_value: str,
    corrected_formula_value: str,
) -> list[dict[str, object]]:
    failed = [
        item
        for item in latest_results(job)
        if item.get("state") == "failed_retryable"
    ]
    require(len(failed) == 2, "P6-07 retryable row cardinality drifted")
    expected = {
        ("Part Name English", "required_value_missing"): corrected_part_value,
        ("total daily output", "formula_error"): corrected_formula_value,
    }
    corrections: list[dict[str, object]] = []
    observed: set[tuple[str, str]] = set()
    for item in failed:
        fields = item.get("fieldResults")
        require(isinstance(fields, list), "P6-07 retryable field truth drifted")
        for field in fields:
            if not isinstance(field, dict):
                continue
            identity = (str(field.get("sourceHeader")), str(field.get("resultCode")))
            if identity not in expected:
                continue
            require(identity not in observed, "P6-07 retryable field identity drifted")
            observed.add(identity)
            corrections.append(
                {
                    "worksheetName": item["worksheetName"],
                    "sourceRow": item["sourceRow"],
                    "sourceHeader": identity[0],
                    "correctedValue": expected[identity],
                }
            )
    require(observed == set(expected), "P6-07 retryable field truth drifted")
    return corrections


def binary_correction_request(
    opener,
    base_url: str,
    path: str,
    *,
    csrf_token: str,
    idempotency_key: str,
    expected_snapshot_hash: str,
):
    body = json.dumps(
        {"expectedSnapshotHash": expected_snapshot_hash},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    headers = document_runtime.command_headers(csrf_token, idempotency_key)
    headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with opener.open(request, timeout=30) as response:
            result = document_runtime.BinaryHttpResult(
                response.status,
                response.headers,
                response.read(),
                None,
            )
    except urllib.error.HTTPError as error:
        raw = error.read()
        result = document_runtime.BinaryHttpResult(
            error.code,
            error.headers,
            raw,
            json.loads(raw.decode("utf-8")),
        )
    require(
        result.headers.get("X-Request-ID") == headers["X-Request-ID"]
        and result.headers.get("Cache-Control") == "private, no-store",
        "P6-07 correction download response identity drifted",
    )
    return result


def correction_download_checks(
    downloaded: object,
    *,
    corrected_value: str,
    corrected_formula_value: str,
    artifact_content_hash: str,
) -> dict[str, bool]:
    content = getattr(downloaded, "content", b"")
    headers = getattr(downloaded, "headers", {})
    return {
        "statusOk": getattr(downloaded, "status", None) == 200,
        "csvPreambleOk": isinstance(content, bytes)
        and content.startswith(
            b"\xef\xbb\xbfworksheet_name,source_row,source_header,corrected_value\n"
        ),
        "digestOk": isinstance(content, bytes)
        and hashlib.sha256(content).hexdigest() == artifact_content_hash,
        "partCorrectionPresent": isinstance(content, bytes)
        and corrected_value.encode("utf-8") in content,
        "formulaCorrectionPresent": isinstance(content, bytes)
        and corrected_formula_value.encode("utf-8") in content,
        "freshReceipt": getattr(headers, "get", lambda *_: None)(
            "Idempotency-Replayed"
        )
        == "false",
    }


def correction_download_diagnostic(
    downloaded: object,
    checks: dict[str, bool],
) -> dict[str, object]:
    status = getattr(downloaded, "status", None)
    problem = getattr(downloaded, "problem", None)
    candidate_code = problem.get("code") if isinstance(problem, dict) else None
    problem_code = (
        candidate_code
        if isinstance(candidate_code, str)
        and len(candidate_code) <= 64
        and candidate_code.replace("_", "").isalnum()
        and candidate_code.upper() == candidate_code
        else "UNAVAILABLE"
    )
    result = {
        **checks,
        "httpStatus": status if isinstance(status, int) and 100 <= status <= 599 else 0,
        "problemCode": problem_code,
    }
    trace_id = problem.get("traceId") if isinstance(problem, dict) else None
    server_diagnostic = tooling_runtime._sanitized_server_diagnostic(
        trace_id,
        CORRECTION_DOWNLOAD_DIAGNOSTIC_CODES,
    )
    if server_diagnostic is not None:
        exception_type, diagnostic_code, exact_trace_id = server_diagnostic
        result.update(
            {
                "diagnosticCode": diagnostic_code,
                "exceptionType": exception_type,
                "traceId": exact_trace_id,
            }
        )
    return result


def current_job(opener, base_url: str, project_id: str, batch_id: str, job_id: str):
    result = tooling_request(
        opener,
        base_url,
        job_path(project_id, batch_id, job_id),
        query_key=f"job-{job_id[:8]}",
    )
    require(result.status == 200, "P6-07 import job detail is unavailable")
    return result.body.get("job", result.body)


def run_scenario(
    actor,
    base_url: str,
    csrf_token: str,
    *,
    context: dict[str, object],
    fixture: dict[str, object],
    index: int,
) -> dict[str, object]:
    project_id = str(context["projectId"])
    file_evidence = run_bench_fixture(
        "seed_tooling_import_fixture",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "file_name": fixture["fileName"],
        },
    )
    require(
        file_evidence.get("sha256") == fixture["sha256"]
        and file_evidence.get("synthetic") is True
        and file_evidence.get("containsCustomerData") is False,
        "P6-07 generated fixture provenance drifted",
    )
    create_payload = batch_payload(
        file_evidence,
        str(context["customerScopeId"]),
    )
    batch_result = command(
        actor,
        base_url,
        csrf_token,
        imports_path(project_id),
        create_payload,
        scenario_key(index, "source"),
    )
    source = assert_source(
        batch_result.body.get("batch"),
        fixture=fixture,
        project_id=project_id,
    )
    batch_id = str(source["batchGlobalId"])
    require(
        batch_result.body.get("mappingAuthority")
        == {"state": "unavailable", "reasonCode": "production_mapping_unavailable"},
        "P6-07 production mapping was not unavailable at source registration",
    )

    inspection_result = command(
        actor,
        base_url,
        csrf_token,
        inspection_path(project_id, batch_id),
        {},
        scenario_key(index, "inspection"),
    )
    inspection = assert_inspection(
        inspection_result.body.get("inspection"),
        fixture=fixture,
    )
    mapping_payload = {
        "inspectionGlobalId": inspection["globalId"],
        "inspectionSnapshotHash": inspection["snapshotHash"],
        "templateKey": "synthetic.controlled.v1",
        "reason": "Controlled synthetic fixture proposal; not production mapping authority.",
    }
    mapping_result = command(
        actor,
        base_url,
        csrf_token,
        mapping_path(project_id, batch_id),
        mapping_payload,
        scenario_key(index, "mapping"),
    )
    proposal = assert_mapping(
        mapping_result.body.get("mappingProposal"),
        expected_state="proposal",
        expected_version=1,
    )
    require(
        mapping_result.body.get("mappingAuthority", {}).get("state") == "unavailable",
        "P6-07 proposal invented production mapping authority",
    )

    activation_result = run_bench_fixture(
        "seed_tooling_import_mapping_activation",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "batch_id": batch_id,
            "proposal_id": proposal["globalId"],
        },
    )
    approved = assert_mapping(
        activation_result.get("mappingProposal"),
        expected_state="approved_fixture",
        expected_version=2,
    )
    activation = activation_result.get("mappingActivation")
    require(
        isinstance(activation, dict)
        and activation.get("fixtureVersion")
        == "p6-07.synthetic-execution-mapping.v1"
        and activation.get("sourceSha256") == fixture["sha256"],
        "P6-07 synthetic mapping activation truth drifted",
    )

    preview_payload = {
        "inspectionGlobalId": inspection["globalId"],
        "inspectionSnapshotHash": inspection["snapshotHash"],
        "mappingGlobalId": approved["globalId"],
        "mappingSnapshotHash": approved["snapshotHash"],
    }
    preview_result = command(
        actor,
        base_url,
        csrf_token,
        preview_path(project_id, batch_id),
        preview_payload,
        scenario_key(index, "preview"),
    )
    initial_preview = assert_preview(
        preview_result.body.get("preview"),
        expected_version=1,
        expected_eligible=False,
    )
    confirmations = preview_confirmations(initial_preview, inspection, context)
    confirmation_payload = {
        "expectedVersion": initial_preview["previewVersion"],
        "expectedSnapshotHash": initial_preview["snapshotHash"],
        "confirmations": confirmations,
    }
    confirmation_result = command(
        actor,
        base_url,
        csrf_token,
        confirmation_path(
            project_id,
            batch_id,
            str(initial_preview["previewGlobalId"]),
        ),
        confirmation_payload,
        scenario_key(index, "confirmation"),
    )
    confirmed_preview = assert_preview(
        confirmation_result.body.get("preview"),
        expected_version=2,
        expected_eligible=True,
    )

    execute_payload = {
        "expectedVersion": confirmed_preview["previewVersion"],
        "expectedSnapshotHash": confirmed_preview["snapshotHash"],
    }
    execute_result = command(
        actor,
        base_url,
        csrf_token,
        execute_path(
            project_id,
            batch_id,
            str(confirmed_preview["previewGlobalId"]),
        ),
        execute_payload,
        scenario_key(index, "execute"),
    )
    queued = assert_job(
        execute_result.body.get("job"),
        expected_state="queued",
        expected_attempt=1,
    )
    job_id = str(queued["globalId"])
    run_bench_fixture(
        "run_tooling_import_worker",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "job_id": job_id,
            "expected_snapshot_hash": queued["snapshotHash"],
        },
    )
    partial = assert_job(
        current_job(actor, base_url, project_id, batch_id, job_id),
        expected_state="partially_succeeded",
        expected_attempt=1,
    )
    partial_latest = latest_results(partial)
    require(
        len(partial_latest) == 3
        and sum(item.get("state") == "created" for item in partial_latest) == 1
        and sum(item.get("state") == "failed_retryable" for item in partial_latest)
        == 2,
        f"P6-07 partial row truth drifted: {partial_row_diagnostic(partial_latest)}",
    )

    corrected_value = f"Synthetic corrected part {index}"
    corrected_formula_value = str(2000 + index)
    corrections = correction_entries(
        partial,
        corrected_value,
        corrected_formula_value,
    )
    artifact_result = command(
        actor,
        base_url,
        csrf_token,
        corrections_path(project_id, batch_id, job_id),
        {
            "expectedVersion": partial["optimisticVersion"],
            "expectedSnapshotHash": partial["snapshotHash"],
            "corrections": corrections,
        },
        scenario_key(index, "correction"),
    )
    artifact = artifact_result.body.get("correctionArtifact")
    require(
        isinstance(artifact, dict)
        and artifact.get("entryCount") == 2
        and artifact.get("mimeType") == "text/csv"
        and artifact.get("jobSnapshotHash") == partial["snapshotHash"],
        "P6-07 correction artifact truth drifted",
    )
    artifact_id = require_uuid(
        artifact.get("globalId"),
        "P6-07 correction artifact",
    )
    artifact_hash = require_hash(
        artifact.get("snapshotHash"),
        "P6-07 correction artifact",
    )
    artifact_content_hash = require_hash(
        artifact.get("sha256"),
        "P6-07 correction artifact content",
    )
    downloaded = binary_correction_request(
        actor,
        base_url,
        correction_content_path(project_id, batch_id, job_id, artifact_id),
        csrf_token=csrf_token,
        idempotency_key=scenario_key(index, "correction-download"),
        expected_snapshot_hash=artifact_hash,
    )
    download_checks = correction_download_checks(
        downloaded,
        corrected_value=corrected_value,
        corrected_formula_value=corrected_formula_value,
        artifact_content_hash=artifact_content_hash,
    )
    require(
        all(download_checks.values()),
        "P6-07 authorized correction download drifted: "
        + json.dumps(
            correction_download_diagnostic(downloaded, download_checks),
            separators=(",", ":"),
            sort_keys=True,
        ),
    )

    retry_result = command(
        actor,
        base_url,
        csrf_token,
        retry_path(project_id, batch_id, job_id),
        {
            "expectedVersion": partial["optimisticVersion"],
            "expectedSnapshotHash": partial["snapshotHash"],
            "correctionArtifactGlobalId": artifact_id,
            "correctionArtifactSnapshotHash": artifact_hash,
        },
        scenario_key(index, "retry"),
    )
    retry_queued = assert_job(
        retry_result.body.get("job"),
        expected_state="queued",
        expected_attempt=2,
    )
    require(
        len(retry_queued["rowResults"]) == len(partial["rowResults"]),
        "P6-07 retry discarded immutable first-attempt truth",
    )
    run_bench_fixture(
        "run_tooling_import_worker",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "job_id": job_id,
            "expected_snapshot_hash": retry_queued["snapshotHash"],
        },
    )
    succeeded = assert_job(
        current_job(actor, base_url, project_id, batch_id, job_id),
        expected_state="succeeded",
        expected_attempt=2,
    )
    succeeded_latest = latest_results(succeeded)
    require(
        len(succeeded_latest) == 3
        and all(item.get("state") == "created" for item in succeeded_latest)
        and len(succeeded["rowResults"]) == 5,
        "P6-07 failed-row-only retry or successful-row non-duplication drifted",
    )

    job_version = {
        "expectedVersion": succeeded["optimisticVersion"],
        "expectedSnapshotHash": succeeded["snapshotHash"],
    }
    reconciliation_result = command(
        actor,
        base_url,
        csrf_token,
        reconcile_path(project_id, batch_id, job_id),
        job_version,
        scenario_key(index, "reconcile"),
    )
    reconciliation = reconciliation_result.body.get("reconciliation")
    require(
        isinstance(reconciliation, dict)
        and len(reconciliation.get("items", [])) == 3
        and all(
            item.get("state") == "matched"
            for item in reconciliation.get("items", [])
        ),
        "P6-07 exact target reconciliation drifted",
    )
    if fixture["rollbackMode"] == "denied":
        run_bench_fixture(
            "seed_tooling_import_downstream_reference",
            {
                "fixture_run_id": FIXTURE_RUN_ID,
                "project_id": project_id,
                "job_id": job_id,
            },
        )

    eligibility_result = command(
        actor,
        base_url,
        csrf_token,
        rollback_evaluation_path(project_id, batch_id, job_id),
        job_version,
        scenario_key(index, "rollback-evaluate"),
    )
    eligibility = eligibility_result.body.get("rollbackEligibility")
    require(
        isinstance(eligibility, dict)
        and len(eligibility.get("items", [])) == 3,
        "P6-07 rollback eligibility truth drifted",
    )
    states = {item.get("state") for item in eligibility["items"]}
    expected_states = (
        {"matched"}
        if fixture["rollbackMode"] == "allowed"
        else {"matched", "downstream_used"}
    )
    require(
        states == expected_states,
        f"P6-07 {fixture['rollbackMode']} eligibility state drifted",
    )
    rollback_result = command(
        actor,
        base_url,
        csrf_token,
        rollback_path(project_id, batch_id, job_id),
        {
            **job_version,
            "eligibilityGlobalId": eligibility["globalId"],
            "eligibilitySnapshotHash": eligibility["snapshotHash"],
        },
        scenario_key(index, "rollback"),
    )
    expected_job_state = (
        "rolled_back" if fixture["rollbackMode"] == "allowed" else "rollback_denied"
    )
    final_job = assert_job(
        rollback_result.body.get("job"),
        expected_state=expected_job_state,
        expected_attempt=2,
    )
    rollback = rollback_result.body.get("rollback")
    expected_item_state = (
        "rolled_back" if fixture["rollbackMode"] == "allowed" else None
    )
    require(
        isinstance(rollback, dict)
        and (
            all(item.get("state") == expected_item_state for item in rollback["items"])
            if expected_item_state is not None
            else any(
                item.get("state") == "downstream_used" for item in rollback["items"]
            )
        ),
        "P6-07 rollback result truth drifted",
    )
    return {
        "index": index,
        "fixture": fixture,
        "fileEvidence": file_evidence,
        "createPayload": create_payload,
        "batchId": batch_id,
        "inspection": inspection,
        "mappingPayload": mapping_payload,
        "proposal": proposal,
        "approved": approved,
        "previewPayload": preview_payload,
        "initialPreview": initial_preview,
        "confirmationPayload": confirmation_payload,
        "confirmedPreview": confirmed_preview,
        "executePayload": execute_payload,
        "jobId": job_id,
        "finalJob": final_job,
    }


def persisted_counts(administrator, base_url: str, project_id: str) -> dict[str, int]:
    result = {
        doctype: len(
            rows(
                administrator,
                base_url,
                doctype,
                [["project_global_id", "=", project_id]],
                ["global_id"],
            )
        )
        for doctype in IMPORT_DOCTYPES
        if doctype != "NPI Tooling Import Command Idempotency"
    }
    result["NPI Tooling Import Command Idempotency"] = len(
        rows(
            administrator,
            base_url,
            "NPI Tooling Import Command Idempotency",
            [["project_global_id", "=", project_id]],
            ["global_id"],
        )
    )
    result["outbox"] = len(
        rows(administrator, base_url, "NPI Outbox Message", [], ["event_id"])
    )
    result["inbox"] = len(
        rows(administrator, base_url, "NPI Inbox Message", [], ["event_id"])
    )
    return result


def verify_persistence(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    project_id: str,
    scenarios: list[dict[str, object]],
    integration_before: tuple[int, int],
) -> None:
    counts = persisted_counts(administrator, base_url, project_id)
    require(
        counts["NPI Tooling Import Batch"] == 2
        and counts["NPI Tooling Import Inspection Revision"] == 2
        and counts["NPI Tooling Import Mapping Revision"] == 4
        and counts["NPI Tooling Import Mapping Activation"] == 2
        and counts["NPI Tooling Import Preview Revision"] == 4
        and counts["NPI Tooling Import Job"] == 2
        and counts["NPI Tooling Import Row Result"] == 8
        and counts["NPI Tooling Import Target Binding"] == 6
        and counts["NPI Tooling Import Correction Artifact"] == 2
        and counts["NPI Tooling Import Reconciliation Revision"] == 6,
        "P6-07 controlled import cardinality drifted",
    )
    require(
        (counts["outbox"], counts["inbox"]) == integration_before,
        "P6-07 controlled import created ERP integration traffic",
    )
    mappings = rows(
        administrator,
        base_url,
        "NPI Tooling Import Mapping Revision",
        [["project_global_id", "=", project_id]],
        ["global_id", "state", "mapping_version"],
    )
    require(
        {item.get("state") for item in mappings} == {"proposal", "approved_fixture"}
        and sum(item.get("state") == "approved_fixture" for item in mappings) == 2,
        "P6-07 production mapping state was persisted",
    )
    for scenario in scenarios:
        batch_id = str(scenario["batchId"])
        detail = tooling_request(
            administrator,
            base_url,
            batch_path(project_id, batch_id),
            query_key=f"retained-{scenario['index']}",
        )
        require(
            detail.status == 200
            and detail.body.get("mappingAuthority", {}).get("state")
            == "approved_fixture"
            and detail.body.get("permissions", {}).get("activateProductionMapping")
            is False,
            "P6-07 retained mapping authority drifted",
        )
        immutable = (
            ("NPI Tooling Import Batch", batch_id),
            (
                "NPI Tooling Import Job",
                str(scenario["jobId"]),
            ),
        )
        for doctype, name in immutable:
            before = get_resource(administrator, base_url, doctype, name)
            snapshot_hash = before.body.get("data", {}).get("snapshot_hash")
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
                before.status == 200
                and isinstance(snapshot_hash, str)
                and len(snapshot_hash) == 64
                and rejected_update.status in {403, 417}
                and rejected_delete.status in {403, 417}
                and after.body.get("data", {}).get("snapshot_hash") == snapshot_hash,
                f"P6-07 immutable {doctype} accepted generic mutation",
            )


def verify_idor(
    administrator,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
    *,
    context: dict[str, object],
    scenario: dict[str, object],
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
        project_id = str(context["projectId"])
        batch_id = str(scenario["batchId"])
        denied = tooling_request(
            unrelated,
            base_url,
            batch_path(project_id, batch_id),
            query_key="idor-denied",
        )
        absent = tooling_request(
            unrelated,
            base_url,
            batch_path(ABSENT_PROJECT_ID, ABSENT_BATCH_ID),
            query_key="idor-absent",
        )
        validate_problem(denied, 404, "TOOLING_UNAVAILABLE")
        validate_problem(absent, 404, "TOOLING_UNAVAILABLE")
        fields = ("type", "title", "status", "code", "retryable")
        require(
            {key: denied.body.get(key) for key in fields}
            == {key: absent.body.get(key) for key in fields},
            "P6-07 unauthorized and absent import scopes are distinguishable",
        )
        denied_command = tooling_request(
            unrelated,
            base_url,
            inspection_path(project_id, batch_id),
            method="POST",
            payload={"doctype": "Secret"},
            csrf_token=unrelated_csrf,
            idempotency_key=scenario_key(9, "idor"),
            query_key="idor-command-denied",
        )
        absent_command = tooling_request(
            unrelated,
            base_url,
            inspection_path(ABSENT_PROJECT_ID, ABSENT_BATCH_ID),
            method="POST",
            payload={"doctype": "Secret"},
            csrf_token=unrelated_csrf,
            idempotency_key=scenario_key(9, "idor"),
            query_key="idor-command-absent",
        )
        validate_problem(denied_command, 403, "PERMISSION_DENIED")
        validate_problem(absent_command, 403, "PERMISSION_DENIED")
        require(
            {key: denied_command.body.get(key) for key in fields}
            == {key: absent_command.body.get(key) for key in fields},
            "P6-07 unauthorized and absent command scopes are distinguishable",
        )
    finally:
        delete_disposable_user(
            administrator,
            base_url,
            UNRELATED_USER,
            csrf_token,
        )


def verify_conflict_rollback(
    actor,
    base_url: str,
    csrf_token: str,
    *,
    context: dict[str, object],
    scenario: dict[str, object],
) -> None:
    project_id = str(context["projectId"])
    before = persisted_counts(actor, base_url, project_id)
    different = dict(scenario["createPayload"])
    different["customerScopeId"] = "synthetic-conflicting-scope"
    conflict = tooling_request(
        actor,
        base_url,
        imports_path(project_id),
        method="POST",
        payload=different,
        csrf_token=csrf_token,
        idempotency_key=scenario_key(int(scenario["index"]), "source"),
    )
    validate_problem(conflict, 409, "TOOLING_IDEMPOTENCY_CONFLICT")
    missing = dict(scenario["createPayload"])
    missing["sha256"] = "0" * 64
    unavailable = tooling_request(
        actor,
        base_url,
        imports_path(project_id),
        method="POST",
        payload=missing,
        csrf_token=csrf_token,
        idempotency_key=scenario_key(9, "invalid-source"),
    )
    validate_problem(unavailable, 404, "TOOLING_REFERENCE_UNAVAILABLE")
    require(
        persisted_counts(actor, base_url, project_id) == before,
        "P6-07 failed commands changed business, receipt, audit, or integration truth",
    )


def replay_scenario(
    actor,
    base_url: str,
    csrf_token: str,
    *,
    context: dict[str, object],
    scenario: dict[str, object],
) -> None:
    index = int(scenario["index"])
    project_id = str(context["projectId"])
    batch_id = str(scenario["batchId"])
    calls = (
        (
            imports_path(project_id),
            scenario["createPayload"],
            "source",
            "batch",
            batch_id,
        ),
        (
            inspection_path(project_id, batch_id),
            {},
            "inspection",
            "inspection",
            scenario["inspection"]["globalId"],
        ),
        (
            mapping_path(project_id, batch_id),
            scenario["mappingPayload"],
            "mapping",
            "mappingProposal",
            scenario["proposal"]["globalId"],
        ),
        (
            preview_path(project_id, batch_id),
            scenario["previewPayload"],
            "preview",
            "preview",
            scenario["initialPreview"]["globalId"],
        ),
        (
            confirmation_path(
                project_id,
                batch_id,
                str(scenario["initialPreview"]["previewGlobalId"]),
            ),
            scenario["confirmationPayload"],
            "confirmation",
            "preview",
            scenario["confirmedPreview"]["globalId"],
        ),
        (
            execute_path(
                project_id,
                batch_id,
                str(scenario["confirmedPreview"]["previewGlobalId"]),
            ),
            scenario["executePayload"],
            "execute",
            "job",
            scenario["jobId"],
        ),
    )
    for path, payload, operation, response_key, identity in calls:
        result = command(
            actor,
            base_url,
            csrf_token,
            str(path),
            dict(payload),
            scenario_key(index, str(operation)),
        )
        value = result.body.get(response_key)
        actual = (
            value.get("batchGlobalId")
            if response_key == "batch" and isinstance(value, dict)
            else value.get("globalId") if isinstance(value, dict) else None
        )
        require(
            result.headers.get("Idempotency-Replayed") == "true"
            and actual == identity,
            f"P6-07 cross-process {operation} replay drifted",
        )
    seeded = run_bench_fixture(
        "seed_tooling_import_mapping_activation",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "batch_id": batch_id,
            "proposal_id": scenario["proposal"]["globalId"],
        },
    )
    require(seeded.get("replayed") is True, "P6-07 mapping seed replay drifted")


def run_fresh(
    actor,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
) -> dict[str, object]:
    context = project_context(actor, base_url)
    project_id = str(context["projectId"])
    schema = run_bench_fixture(
        "verify_tooling_import_runtime_schema",
        {"fixture_run_id": FIXTURE_RUN_ID},
    )
    empty = tooling_request(
        actor,
        base_url,
        imports_path(project_id),
        query_key="fresh-empty",
    )
    require(
        empty.status == 200 and empty.body.get("batches") == [],
        "P6-07 fresh import collection was not empty",
    )
    guest = tooling_request(
        urllib.request.build_opener(),
        base_url,
        imports_path(project_id),
        query_key="guest",
    )
    validate_problem(guest, 401, "AUTHENTICATION_REQUIRED")
    initial_counts = persisted_counts(actor, base_url, project_id)
    integration_before = (initial_counts["outbox"], initial_counts["inbox"])
    scenarios = [
        run_scenario(
            actor,
            base_url,
            csrf_token,
            context=context,
            fixture=dict(fixture),
            index=index,
        )
        for index, fixture in enumerate(FIXTURES, start=1)
    ]
    verify_idor(
        actor,
        base_url,
        csrf_token,
        fixture_password,
        context=context,
        scenario=scenarios[0],
    )
    verify_conflict_rollback(
        actor,
        base_url,
        csrf_token,
        context=context,
        scenario=scenarios[0],
    )
    verify_persistence(
        actor,
        base_url,
        csrf_token,
        project_id=project_id,
        scenarios=scenarios,
        integration_before=integration_before,
    )
    return {
        "doctypeCount": schema["doctypeCount"],
        "fixtureRunId": FIXTURE_RUN_ID,
        "generatedFixtureCount": 2,
        "sourceColumnCount": 43,
        "partialJobCount": 2,
        "retrySucceededCount": 2,
        "rollbackAllowedCount": 1,
        "rollbackDeniedCount": 1,
        "productionMappingActive": False,
        "integrationTrafficCreated": False,
    }


def run_replay(actor, base_url: str, csrf_token: str) -> dict[str, object]:
    context = project_context(actor, base_url)
    project_id = str(context["projectId"])
    collection = tooling_request(
        actor,
        base_url,
        imports_path(project_id),
        query_key="replay-collection",
    )
    batches = collection.body.get("batches")
    require(
        collection.status == 200 and isinstance(batches, list) and len(batches) == 2,
        "P6-07 replay collection truth drifted",
    )
    scenarios = []
    for index, fixture in enumerate(FIXTURES, start=1):
        batch = exact_single(
            [item for item in batches if item.get("fileName") == fixture["fileName"]],
            f"P6-07 replay batch {index}",
        )
        batch_id = str(batch["batchGlobalId"])
        detail = tooling_request(
            actor,
            base_url,
            batch_path(project_id, batch_id),
            query_key=f"replay-detail-{index}",
        )
        require(detail.status == 200, "P6-07 replay batch detail is unavailable")
        inspections = detail.body.get("inspections")
        mappings = detail.body.get("mappingProposals")
        previews = detail.body.get("previews")
        jobs = detail.body.get("jobs")
        require(
            all(isinstance(value, list) for value in (inspections, mappings, previews, jobs)),
            "P6-07 replay retained collections are invalid",
        )
        inspection = exact_single(inspections, f"P6-07 replay inspection {index}")
        proposal = exact_single(
            [item for item in mappings if item.get("state") == "proposal"],
            f"P6-07 replay proposal {index}",
        )
        approved = exact_single(
            [item for item in mappings if item.get("state") == "approved_fixture"],
            f"P6-07 replay fixture mapping {index}",
        )
        initial_preview = exact_single(
            [item for item in previews if item.get("previewVersion") == 1],
            f"P6-07 replay preview {index}",
        )
        confirmed_preview = exact_single(
            [item for item in previews if item.get("previewVersion") == 2],
            f"P6-07 replay confirmed preview {index}",
        )
        job = exact_single(jobs, f"P6-07 replay job {index}")
        scenarios.append(
            {
                "index": index,
                "createPayload": {
                    "customerScopeId": batch["customerScopeId"],
                    "fileRevisionGlobalId": batch["fileRevisionGlobalId"],
                    "fileOptimisticVersion": batch["fileOptimisticVersion"],
                    "frappeContentHash": batch["frappeContentHash"],
                    "sha256": batch["sha256"],
                },
                "batchId": batch_id,
                "inspection": inspection,
                "mappingPayload": {
                    "inspectionGlobalId": inspection["globalId"],
                    "inspectionSnapshotHash": inspection["snapshotHash"],
                    "templateKey": proposal["templateKey"],
                    "reason": proposal["reason"],
                },
                "proposal": proposal,
                "approved": approved,
                "previewPayload": {
                    "inspectionGlobalId": inspection["globalId"],
                    "inspectionSnapshotHash": inspection["snapshotHash"],
                    "mappingGlobalId": approved["globalId"],
                    "mappingSnapshotHash": approved["snapshotHash"],
                },
                "initialPreview": initial_preview,
                "confirmationPayload": {
                    "expectedVersion": initial_preview["previewVersion"],
                    "expectedSnapshotHash": initial_preview["snapshotHash"],
                    "confirmations": confirmed_preview["confirmations"],
                },
                "confirmedPreview": confirmed_preview,
                "executePayload": {
                    "expectedVersion": confirmed_preview["previewVersion"],
                    "expectedSnapshotHash": confirmed_preview["snapshotHash"],
                },
                "jobId": job["globalId"],
            }
        )
    before = persisted_counts(actor, base_url, project_id)
    for scenario in scenarios:
        replay_scenario(
            actor,
            base_url,
            csrf_token,
            context=context,
            scenario=scenario,
        )
    require(
        persisted_counts(actor, base_url, project_id) == before,
        "P6-07 cross-process replay changed immutable or integration cardinality",
    )
    return {"crossProcessReplay": True, "scenarioCount": 2}


def route_disable_probe(actor, base_url: str, expected_mode: str) -> None:
    context = project_context(actor, base_url)
    project_id = str(context["projectId"])
    imports = tooling_request(
        actor,
        base_url,
        imports_path(project_id),
        query_key=f"route-{expected_mode}",
    )
    acceptance = predecessor.tooling_request(
        actor,
        base_url,
        predecessor.acceptance_path(project_id, str(context["masterId"])),
        query_key=f"p607-predecessor-{expected_mode}",
    )
    require(
        acceptance.status == 200,
        "P6-07 route switch changed predecessor acceptance availability",
    )
    if expected_mode == "disabled":
        validate_problem(imports, 503, "TOOLING_IMPORT_ROUTES_DISABLED")
        return
    require(
        imports.status == 200 and len(imports.body.get("batches", [])) == 2,
        "P6-07 route recovery lost retained import history",
    )


def verify_tooling_import_runtime_schema(fixture_run_id: str) -> dict[str, object]:
    import frappe

    document_runtime._validated_runtime_site()
    require(fixture_run_id == FIXTURE_RUN_ID, "P6-07 schema fixture namespace drifted")
    required_fields = {
        "NPI Tooling Import Batch": {
            "global_id",
            "project_global_id",
            "file_revision_global_id",
            "source_snapshot",
            "snapshot_hash",
        },
        "NPI Tooling Import Inspection Revision": {
            "global_id",
            "batch_global_id",
            "inspection_snapshot",
            "snapshot_hash",
        },
        "NPI Tooling Import Mapping Revision": {
            "global_id",
            "mapping_global_id",
            "mapping_version",
            "state",
            "mapping_snapshot",
            "snapshot_hash",
        },
        "NPI Tooling Import Preview Revision": {
            "global_id",
            "preview_global_id",
            "preview_version",
            "preview_snapshot",
            "snapshot_hash",
        },
        "NPI Tooling Import Mapping Activation": {
            "global_id",
            "mapping_revision_global_id",
            "activation_snapshot",
            "snapshot_hash",
        },
        "NPI Tooling Import Job": {
            "global_id",
            "batch_global_id",
            "state",
            "attempt",
            "job_snapshot",
            "snapshot_hash",
        },
        "NPI Tooling Import Row Result": {
            "global_id",
            "job_global_id",
            "source_row",
            "attempt",
            "row_result_snapshot",
            "snapshot_hash",
        },
        "NPI Tooling Import Target Binding": {
            "global_id",
            "job_global_id",
            "target_global_id",
            "binding_snapshot",
            "snapshot_hash",
        },
        "NPI Tooling Import Correction Artifact": {
            "global_id",
            "job_global_id",
            "frappe_file_id",
            "artifact_snapshot",
            "snapshot_hash",
        },
        "NPI Tooling Import Reconciliation Revision": {
            "global_id",
            "job_global_id",
            "kind",
            "reconciliation_snapshot",
            "snapshot_hash",
        },
        "NPI Tooling Import Command Idempotency": {
            "global_id",
            "operation",
            "payload_hash",
            "response_hash",
            "sealed",
        },
    }
    for doctype, fields in required_fields.items():
        require(frappe.db.table_exists(doctype), f"P6-07 table is unavailable: {doctype}")
        meta = frappe.get_meta(doctype, cached=False)
        actual = {field.fieldname for field in meta.fields}
        require(fields <= actual, f"P6-07 {doctype} metadata drifted")
        require(
            int(meta.allow_rename or 0) == 0 and int(meta.is_submittable or 0) == 0,
            f"P6-07 {doctype} mutability metadata drifted",
        )
    return {
        "doctypeCount": len(required_fields),
        "fixtureRunId": fixture_run_id,
        "metadataSynchronized": True,
        "runtimeMarker": RUNTIME_MARKER,
    }


def seed_tooling_import_fixture(
    fixture_run_id: str,
    project_id: str,
    file_name: str,
) -> dict[str, object]:
    import frappe
    from frappe.utils import now_datetime

    from npi_core.controlled_evidence_validation import (
        FILE_REVISION_COMMAND_FLAG,
        FILE_SCAN_RESULT_FLAG,
    )
    from npi_core.npi_core.doctype.npi_file_revision.npi_file_revision import (
        has_live_private_file_identity,
    )
    from npi_core.tooling.xlsx_fixture import build_sanitized_tooling_workbook

    document_runtime._validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "P6-07 source fixture namespace drifted",
    )
    fixture = exact_single(
        [item for item in FIXTURES if item["fileName"] == file_name],
        "P6-07 source fixture definition",
    )
    project = frappe.get_doc("NPI Engineering Project", project_id)
    require(
        str(project.global_id) == project_id
        and str(project.business_code) == document_runtime.BUSINESS_CODE
        and str(project.tenant_id) == TENANT_ID,
        "P6-07 source fixture Project identity drifted",
    )
    revision_id = deterministic_uuid(f"file-revision:{file_name}")
    document_id = deterministic_uuid(f"file-document:{file_name}")
    require(
        not frappe.db.exists("NPI File Revision", revision_id),
        "P6-07 fresh synthetic File Revision already exists",
    )
    temporary_directory = (
        Path(frappe.get_site_path("private", "files"))
        / f".p6-07-runtime-{fixture_run_id}"
    )
    require(
        not temporary_directory.exists(),
        "P6-07 synthetic source staging directory already exists",
    )
    temporary_directory.mkdir(mode=0o700)
    temporary = temporary_directory / file_name
    try:
        manifest = build_sanitized_tooling_workbook(
            temporary,
            title_row_count=int(fixture["titleRowCount"]),
        )
        content = temporary.read_bytes()
    finally:
        if temporary.exists():
            temporary.unlink()
        temporary_directory.rmdir()
    require(
        manifest == {
            "fixtureVersion": "p6-07.synthetic-tooling-list.v1",
            "fileName": file_name,
            "sha256": fixture["sha256"],
            "synthetic": True,
            "titleRowCount": fixture["titleRowCount"],
            "headerRow": fixture["headerRow"],
            "sourceColumnCount": 43,
            "containsCustomerData": False,
        },
        "P6-07 generated fixture manifest drifted",
    )
    file_document = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": file_name,
            "is_private": 1,
            "content": content,
        }
    ).insert(ignore_permissions=True)
    require(
        str(file_document.file_name) == file_name,
        "P6-07 synthetic private File name drifted",
    )
    previous_command = getattr(frappe.flags, FILE_REVISION_COMMAND_FLAG, None)
    setattr(frappe.flags, FILE_REVISION_COMMAND_FLAG, True)
    try:
        revision = frappe.get_doc(
            {
                "doctype": "NPI File Revision",
                "global_id": revision_id,
                "tenant_id": TENANT_ID,
                "project_global_id": project_id,
                "document_global_id": document_id,
                "revision": 1,
                "frappe_file_id": file_document.name,
                "file": file_document.file_url,
                "sha256": manifest["sha256"],
                "scan_state": "pending",
            }
        ).insert()
    finally:
        if previous_command is None:
            delattr(frappe.flags, FILE_REVISION_COMMAND_FLAG)
        else:
            setattr(frappe.flags, FILE_REVISION_COMMAND_FLAG, previous_command)
    previous_scan = getattr(frappe.flags, FILE_SCAN_RESULT_FLAG, None)
    setattr(frappe.flags, FILE_SCAN_RESULT_FLAG, True)
    try:
        revision.scan_state = "clean"
        revision.scan_observed_at = now_datetime()
        revision.save()
    finally:
        if previous_scan is None:
            delattr(frappe.flags, FILE_SCAN_RESULT_FLAG)
        else:
            setattr(frappe.flags, FILE_SCAN_RESULT_FLAG, previous_scan)
    frappe.db.commit()
    identity_checks = {
        "global-id": str(revision.global_id) == revision_id,
        "file-name": str(revision.file_name) == file_name,
        "mime-type": str(revision.mime_type)
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "sha256": str(revision.sha256) == fixture["sha256"],
        "scan-state": str(revision.scan_state) == "clean",
        "optimistic-version": int(revision.optimistic_version) == 2,
        "live-private-file": has_live_private_file_identity(revision),
    }
    failed_identity_checks = sorted(
        name for name, accepted in identity_checks.items() if not accepted
    )
    require(
        not failed_identity_checks,
        "P6-07 synthetic live private File identity drifted: "
        + ",".join(failed_identity_checks),
    )
    return {
        "fileRevisionGlobalId": revision_id,
        "fileOptimisticVersion": int(revision.optimistic_version),
        "frappeContentHash": str(revision.frappe_content_hash),
        "sha256": str(revision.sha256),
        "fileName": file_name,
        "synthetic": True,
        "containsCustomerData": False,
    }


def seed_tooling_import_mapping_activation(
    fixture_run_id: str,
    project_id: str,
    batch_id: str,
    proposal_id: str,
) -> dict[str, object]:
    import frappe

    from npi_core.foundation.security import Principal
    from npi_core.tooling.import_execution_repository import (
        FrappeToolingImportExecutionRepository,
    )

    document_runtime._validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "P6-07 mapping fixture namespace drifted",
    )
    frappe.set_user(ACTOR_USER)
    principal = Principal(
        user_id=ACTOR_USER,
        tenant_id=TENANT_ID,
        roles=frozenset(frappe.get_roles(ACTOR_USER)),
        is_external=False,
    )
    repository = FrappeToolingImportExecutionRepository(
        principal=principal,
        request_id=deterministic_uuid(f"mapping-seed-request:{batch_id}"),
        trace_id=f"trace-p607-seed-{batch_id.replace('-', '')[:16]}",
    )
    result = repository.seed_synthetic_fixture_mapping_activation(
        UUID(project_id),
        UUID(batch_id),
        UUID(proposal_id),
    )
    require(result is not None, "P6-07 synthetic mapping seed is unavailable")
    frappe.db.commit()
    return result


def run_tooling_import_worker(
    fixture_run_id: str,
    job_id: str,
    expected_snapshot_hash: str,
) -> dict[str, object]:
    import frappe

    from npi_core.tooling.import_execution_repository import run_tooling_import_job

    document_runtime._validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "P6-07 worker fixture namespace drifted",
    )
    run_tooling_import_job(job_id, expected_snapshot_hash)
    job = frappe.get_doc("NPI Tooling Import Job", job_id)
    return {
        "globalId": str(job.global_id),
        "state": str(job.state),
        "attempt": int(job.attempt),
        "optimisticVersion": int(job.optimistic_version),
        "snapshotHash": str(job.snapshot_hash),
    }


def seed_tooling_import_downstream_reference(
    fixture_run_id: str,
    project_id: str,
    job_id: str,
) -> dict[str, object]:
    import frappe

    from npi_core.tooling.domain import ToolingRequirement, ToolingRequirementKind
    from npi_core.tooling.frappe_repository import FrappeToolingRepository
    from npi_core.tooling.frappe_validation import tooling_command_write

    document_runtime._validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "P6-07 downstream fixture namespace drifted",
    )
    bindings = frappe.get_all(
        "NPI Tooling Import Target Binding",
        filters={"project_global_id": project_id, "job_global_id": job_id},
        fields=["target_global_id"],
        order_by="created_at asc",
        limit_page_length=10,
    )
    require(len(bindings) == 3, "P6-07 downstream fixture target set drifted")
    target_id = str(bindings[0].target_global_id)
    now = datetime.now(UTC)
    value = ToolingRequirement(
        global_id=UUID(deterministic_uuid(f"downstream-requirement:{job_id}")),
        tenant_id=TENANT_ID,
        project_global_id=UUID(project_id),
        kind=ToolingRequirementKind.CAPACITY_NEED,
        title="Synthetic downstream rollback guard",
        reason="Controlled disposable-Site dependency for rollback denial proof.",
        target_part_revision_global_id=UUID(target_id),
        target_date=None,
        created_by_user_id=ACTOR_USER,
        created_at=now,
        request_id=UUID(deterministic_uuid(f"downstream-request:{job_id}")),
        trace_id=f"trace-p607-downstream-{job_id.replace('-', '')[:16]}",
    )
    with tooling_command_write():
        FrappeToolingRepository._insert_requirement(value)
    frappe.db.commit()
    return {
        "requirementGlobalId": str(value.global_id),
        "targetPartRevisionGlobalId": target_id,
        "downstreamReferenceCount": 1,
    }


BENCH_FIXTURES = {
    "verify_tooling_import_runtime_schema": verify_tooling_import_runtime_schema,
    "seed_tooling_import_fixture": seed_tooling_import_fixture,
    "seed_tooling_import_mapping_activation": seed_tooling_import_mapping_activation,
    "run_tooling_import_worker": run_tooling_import_worker,
    "seed_tooling_import_downstream_reference": seed_tooling_import_downstream_reference,
}


def run_bench_fixture(method: str, kwargs: dict[str, object]) -> dict[str, Any]:
    require(method in BENCH_FIXTURES, "P6-07 Bench fixture is unavailable")
    require(
        BENCH_PATH.is_dir()
        and not BENCH_PATH.is_symlink()
        and BENCH_PATH.resolve() == BENCH_PATH,
        "P6-07 verifier requires the fixed physical Bench",
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
            str(ROOT / "scripts" / "verify_tooling_import_runtime.py"),
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
    require(
        completed.returncode == 0,
        (
            f"P6-07 Bench fixture failed: {method}: "
            f"{completed.stderr[-2000:]}"
        ),
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    require(bool(lines), f"P6-07 Bench fixture was silent: {method}")
    result = json.loads(lines[-1])
    require(isinstance(result, dict), "P6-07 Bench fixture result is invalid")
    return result


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    require(method in BENCH_FIXTURES, "P6-07 Bench fixture is unavailable")
    import frappe

    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    try:
        frappe.set_user(ACTOR_USER)
        result = BENCH_FIXTURES[method](**kwargs)
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the cumulative controlled P6-07 Tooling import runtime.",
    )
    parser.add_argument("--base-url")
    parser.add_argument("--bench-fixture", choices=tuple(BENCH_FIXTURES))
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
            "P6-07 Bench fixture arguments are invalid",
        )
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "P6-07 fixture kwargs are invalid")
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return
    require(
        isinstance(arguments.base_url, str)
        and arguments.fixture_kwargs is None
        and document_runtime.CALLER_SUPPLIED_FIXTURE_RUN_ID is not None,
        "P6-07 runtime base URL and fixture namespace are required",
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
        "P6-07 fixture identity drifted",
    )
    require(
        int(arguments.route_disable_probe is not None)
        + int(arguments.replay_only)
        <= 1,
        "P6-07 runtime modes are mutually exclusive",
    )
    actor = login(base_url, ACTOR_USER, fixture_password)
    csrf_token = bootstrap_csrf(actor, base_url, ACTOR_USER)
    if arguments.route_disable_probe is not None:
        route_disable_probe(actor, base_url, arguments.route_disable_probe)
        print(json.dumps({"routeMode": arguments.route_disable_probe}, sort_keys=True))
        return
    if arguments.replay_only:
        evidence = run_replay(actor, base_url, csrf_token)
        print(json.dumps(evidence, sort_keys=True))
        print("local Frappe Tooling import runtime replay verification passed")
        return
    evidence = run_fresh(actor, base_url, csrf_token, fixture_password)
    print(json.dumps(evidence, sort_keys=True))
    print("local Frappe Tooling import runtime verification passed")


if __name__ == "__main__":
    main()
