from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import verify_document_runtime as document_runtime
import verify_tooling_runtime as tooling_runtime
from verify_frappe_runtime import (
    HttpResult,
    delete_disposable_user,
    login,
    require,
    secret_from_environment,
    validate_local_fixture_inputs,
    validate_problem,
)
from verify_project_runtime import (
    bootstrap_csrf,
    create_resource,
    delete_resource,
    get_resource,
    list_resources,
    update_resource,
)


ROOT = Path(__file__).resolve().parents[1]
BENCH_PATH = ROOT / "tmp" / "frappe-bench"
SITE_NAME = document_runtime.SITE_NAME
RUNTIME_MARKER = document_runtime.RUNTIME_MARKER
FIXTURE_RUN_ID = document_runtime.FIXTURE_RUN_ID
TENANT_ID = document_runtime.TENANT_ID
ACTOR_USER = "Administrator"
RESPONSIBLE_MEMBER_ID = document_runtime.BASELINE_MEMBER_ID
VERIFIER_MEMBER_ID = document_runtime.fixture_id("p7-03-verifier-member")
REVIEW_MEMBER_ID = document_runtime.fixture_id("p7-04-review-member")
REVIEW_POLICY_ID = document_runtime.fixture_id("p7-04-review-policy")
REVIEW_POLICY_REVISION_ID = document_runtime.fixture_id("p7-04-review-policy-r1")
VERIFIER_USER = f"npi-trial-{FIXTURE_RUN_ID[:20]}-verifier@example.invalid"
REVIEW_USER = f"npi-trial-{FIXTURE_RUN_ID[:20]}-reviewer@example.invalid"
UNRELATED_USER = f"npi-trial-{FIXTURE_RUN_ID[:20]}-unrelated@example.invalid"
ABSENT_PROJECT_ID = "00000000-0000-4000-8000-000000000701"
ABSENT_PLAN_ID = "00000000-0000-4000-8000-000000000702"

CREATE_KEY = f"p7-01-runtime-{FIXTURE_RUN_ID}-create"
REVISE_KEY = f"p7-01-runtime-{FIXTURE_RUN_ID}-revise"
STALE_REVISE_KEY = f"p7-01-runtime-{FIXTURE_RUN_ID}-stale-revise"
ROUND_KEY = f"p7-01-runtime-{FIXTURE_RUN_ID}-round"
TARGET_ROUND_KEY = f"p7-03-runtime-{FIXTURE_RUN_ID}-target-round"
ROUND_CONFLICT_KEY = f"p7-01-runtime-{FIXTURE_RUN_ID}-round-conflict"
ACTION_KEY = f"p7-01-runtime-{FIXTURE_RUN_ID}-actions"

PREPARE_KEY = f"p7-02-runtime-{FIXTURE_RUN_ID}-prepare"
STALE_PREPARE_KEY = f"p7-02-runtime-{FIXTURE_RUN_ID}-stale-prepare"
START_KEY = f"p7-02-runtime-{FIXTURE_RUN_ID}-start"
ACTUAL_KEY = f"p7-02-runtime-{FIXTURE_RUN_ID}-actual"
STALE_ACTUAL_KEY = f"p7-02-runtime-{FIXTURE_RUN_ID}-stale-actual"
SAMPLE_KEY = f"p7-02-runtime-{FIXTURE_RUN_ID}-sample"
SAMPLE_REVISE_KEY = f"p7-02-runtime-{FIXTURE_RUN_ID}-sample-revise"
UPLOAD_KEY = f"p7-02-runtime-{FIXTURE_RUN_ID}-upload"
BIND_KEY = f"p7-02-runtime-{FIXTURE_RUN_ID}-bind"
TARGET_PREPARE_KEY = f"p7-03-runtime-{FIXTURE_RUN_ID}-target-prepare"
TARGET_START_KEY = f"p7-03-runtime-{FIXTURE_RUN_ID}-target-start"
TARGET_SAMPLE_KEY = f"p7-03-runtime-{FIXTURE_RUN_ID}-target-sample"
TARGET_UPLOAD_KEY = f"p7-03-runtime-{FIXTURE_RUN_ID}-target-upload"
TARGET_BIND_KEY = f"p7-03-runtime-{FIXTURE_RUN_ID}-target-bind"
CAVITY_CREATE_KEY = f"p7-03-runtime-{FIXTURE_RUN_ID}-cavity-create"
CAVITY_REVISE_KEY = f"p7-03-runtime-{FIXTURE_RUN_ID}-cavity-revise"
CAVITY_STALE_KEY = f"p7-03-runtime-{FIXTURE_RUN_ID}-cavity-stale"
NEW_DEFECT_CREATE_KEY = f"p7-03-runtime-{FIXTURE_RUN_ID}-defect-new"
NEW_DEFECT_KEYS = tuple(
    f"p7-03-runtime-{FIXTURE_RUN_ID}-defect-new-v{version}"
    for version in range(2, 7)
)
CONTINUE_TOOLING_DEFECT_KEY = f"p7-03-runtime-{FIXTURE_RUN_ID}-defect-tooling"
CROSS_ROUND_DEFECT_KEY = f"p7-03-runtime-{FIXTURE_RUN_ID}-defect-cross-round"
VERIFY_FAIL_KEY = f"p7-03-runtime-{FIXTURE_RUN_ID}-verify-fail"
VERIFY_PASS_KEY = f"p7-03-runtime-{FIXTURE_RUN_ID}-verify-pass"
BEGIN_ANALYSIS_KEY = f"p7-04-runtime-{FIXTURE_RUN_ID}-begin-analysis"
COMPARISON_KEY = f"p7-04-runtime-{FIXTURE_RUN_ID}-comparison"
STALE_COMPARISON_KEY = f"p7-04-runtime-{FIXTURE_RUN_ID}-stale-comparison"
INTERNAL_REFERENCE_KEY = f"p7-04-runtime-{FIXTURE_RUN_ID}-internal-reference"
CONTROLLED_REFERENCE_KEY = f"p7-04-runtime-{FIXTURE_RUN_ID}-controlled-reference"
CONTROLLED_REFERENCE_REVISE_KEY = (
    f"p7-04-runtime-{FIXTURE_RUN_ID}-controlled-reference-revise"
)
STALE_REFERENCE_REVISE_KEY = f"p7-04-runtime-{FIXTURE_RUN_ID}-stale-reference"
BLOCKED_CONCLUSION_KEY = f"p7-04-runtime-{FIXTURE_RUN_ID}-blocked-conclusion"
SUBMIT_CONCLUSION_KEY = f"p7-04-runtime-{FIXTURE_RUN_ID}-submit-conclusion"
APPROVE_CONCLUSION_KEY = f"p7-04-runtime-{FIXTURE_RUN_ID}-approve-conclusion"
REOPEN_CONCLUSION_KEY = f"p7-04-runtime-{FIXTURE_RUN_ID}-reopen-conclusion"
RESUBMIT_CONCLUSION_KEY = f"p7-04-runtime-{FIXTURE_RUN_ID}-resubmit-conclusion"
REJECT_CONCLUSION_KEY = f"p7-04-runtime-{FIXTURE_RUN_ID}-reject-conclusion"
EVIDENCE_FILE_NAME = "p7-02-controlled-parameters.csv"
EVIDENCE_CONTENT = (
    b"definitionKey,value,unit\n"
    b"melt_temperature,287,degC\n"
)

TRIAL_DOCTYPES = (
    "NPI Trial Plan Revision",
    "NPI Trial Round",
    "NPI Trial Round Lifecycle Event",
    "NPI Trial Plan Work Link",
    "NPI Trial Command Idempotency",
    "NPI Trial Input Lock Revision",
    "NPI Trial Actual Revision",
    "NPI Trial Sample Batch Revision",
    "NPI Trial Evidence Reference",
    "NPI Trial Cavity Result Revision",
    "NPI Trial Defect Revision",
    "NPI Trial Defect Verification Revision",
    "NPI Trial Conclusion Policy Version",
    "NPI Trial Round Comparison Snapshot",
    "NPI Trial Review Reference Revision",
    "NPI Trial Conclusion Revision",
)
TRIAL_PROTECTED_FIELDS = {
    "NPI Trial Plan Revision": "snapshot_hash",
    "NPI Trial Round": "snapshot_hash",
    "NPI Trial Round Lifecycle Event": "snapshot_hash",
    "NPI Trial Plan Work Link": "snapshot_hash",
    "NPI Trial Command Idempotency": "payload_hash",
    "NPI Trial Input Lock Revision": "snapshot_hash",
    "NPI Trial Actual Revision": "snapshot_hash",
    "NPI Trial Sample Batch Revision": "snapshot_hash",
    "NPI Trial Evidence Reference": "snapshot_hash",
    "NPI Trial Cavity Result Revision": "snapshot_hash",
    "NPI Trial Defect Revision": "snapshot_hash",
    "NPI Trial Defect Verification Revision": "snapshot_hash",
    "NPI Trial Conclusion Policy Version": "snapshot_hash",
    "NPI Trial Round Comparison Snapshot": "snapshot_hash",
    "NPI Trial Review Reference Revision": "snapshot_hash",
    "NPI Trial Conclusion Revision": "snapshot_hash",
}
EXPECTED_CAPABILITIES = [
    {
        "key": "resource_availability",
        "availability": "unavailable",
        "reasonCode": "approved_resource_reader_not_configured",
    },
    {
        "key": "resource_reservation",
        "availability": "unavailable",
        "reasonCode": "approved_booking_policy_not_configured",
    },
]
EXPECTED_PERMISSIONS = {
    "canCreatePlan": True,
    "canRevisePlan": True,
    "canCreateRound": True,
    "canGenerateActions": True,
}
EXPECTED_EXECUTION_CAPABILITIES = {
    "machineImport": "unavailable",
    "erpQuality": "unavailable",
    "conclusion": "unavailable",
    "gateEffect": "unavailable",
    "approvedBaseline": "unavailable",
}
EXPECTED_QUALITY_PERMISSIONS = {
    "view": True,
    "recordCavityResult": True,
    "manageDefects": True,
    "verifyDefects": True,
}
EXPECTED_QUALITY_EXTERNAL_EFFECTS = {
    "ncr": "unavailable",
    "qualityInspection": "unavailable",
    "gate": "unavailable",
    "toolingLifecycle": "unavailable",
}
EXPECTED_REVIEW_EXTERNAL_EFFECTS = {
    "formalErpQuality": "unavailable",
    "customerSignature": "unavailable",
    "gate": "unavailable",
    "npiReadiness": "unavailable",
    "toolingLifecycle": "unavailable",
    "nextWork": "proposal_only",
}
_PROBLEM_CODE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
_FIELD_PATH = re.compile(
    r"^[A-Za-z][A-Za-z0-9]*(?:(?:\.[A-Za-z][A-Za-z0-9]*)|(?:\[[0-9]{1,3}\]))*$"
)
_TRACE_ID = re.compile(r"^trace-[a-f0-9]{32}$")
_SAFE_UNEXPECTED_DIAGNOSTIC = re.compile(
    rb'\{"code":"(?P<code>[A-Z][A-Z0-9_]{1,127})","exceptionType":"'
    rb'(?P<exception>[A-Za-z][A-Za-z0-9_]{0,127})","traceId":"'
    rb'(?P<trace>trace-[a-f0-9]{32})"\}'
)
_SAFE_QUALITY_STAGE_PREFIX = b"P703_QUALITY_"
_DIAGNOSTIC_TAIL_BYTES = 256 * 1024


def trial_path(project_id: str, suffix: str = "") -> str:
    return f"/api/npi/v1/projects/{project_id}/trials{suffix}"


def plan_path(project_id: str, plan_id: str, suffix: str = "") -> str:
    return f"/api/npi/v1/projects/{project_id}/trial-plans/{plan_id}{suffix}"


def execution_path(project_id: str, round_id: str, suffix: str = "/execution") -> str:
    return f"/api/npi/v1/projects/{project_id}/trial-rounds/{round_id}{suffix}"


def quality_path(project_id: str, round_id: str, suffix: str = "/quality") -> str:
    return f"/api/npi/v1/projects/{project_id}/trial-rounds/{round_id}{suffix}"


def review_path(project_id: str, round_id: str, suffix: str = "/review") -> str:
    return f"/api/npi/v1/projects/{project_id}/trial-rounds/{round_id}{suffix}"


def sample_path(
    project_id: str,
    round_id: str,
    sample_batch_id: str,
) -> str:
    return execution_path(
        project_id,
        round_id,
        f"/sample-batches/{sample_batch_id}/revisions",
    )


def trial_request(
    opener,
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    csrf_token: str | None = None,
    idempotency_key: str | None = None,
    query_key: str = "query",
) -> HttpResult:
    headers = (
        document_runtime.command_headers(csrf_token, idempotency_key)
        if idempotency_key is not None
        else document_runtime.query_headers(f"p701-{query_key}")
    )
    result = document_runtime.request(
        opener,
        base_url,
        path,
        method=method,
        payload=payload,
        request_headers=headers,
    )
    require(
        result.headers.get("X-Request-ID") == headers["X-Request-ID"],
        "P7-01 request identity was not echoed",
    )
    require(
        result.headers.get("Cache-Control") == "private, no-store",
        "P7-01 private no-store response drifted",
    )
    return HttpResult(
        result.status,
        result.headers,
        result.body,
        request_id=headers["X-Request-ID"],
        trace_id=headers["X-Trace-ID"],
    )


def command(
    opener,
    base_url: str,
    csrf_token: str,
    path: str,
    payload: dict[str, object],
    key: str,
) -> HttpResult:
    result = trial_request(
        opener,
        base_url,
        path,
        method="POST",
        payload=payload,
        csrf_token=csrf_token,
        idempotency_key=key,
    )
    require(
        result.status == 201,
        (
            f"P7-01 command returned HTTP {result.status}"
            f"{sanitized_trial_failure(result)}"
        ),
    )
    require(
        result.headers.get("Idempotency-Replayed") in {"true", "false"},
        "P7-01 replay response header drifted",
    )
    return result


def multipart_trial_upload(
    opener,
    base_url: str,
    path: str,
    *,
    csrf_token: str,
    idempotency_key: str,
    round_version: int,
) -> HttpResult:
    boundary = f"npi-one-trial-{FIXTURE_RUN_ID}-{uuid4().hex}"
    body = b"".join(
        (
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="expectedRoundOptimisticVersion"\r\n\r\n',
            str(round_version).encode(),
            b"\r\n",
            f"--{boundary}\r\n".encode(),
            (
                'Content-Disposition: form-data; name="file"; '
                f'filename="{EVIDENCE_FILE_NAME}"\r\n'
            ).encode(),
            b"Content-Type: text/csv\r\n\r\n",
            EVIDENCE_CONTENT,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        )
    )
    headers = document_runtime.command_headers(csrf_token, idempotency_key)
    headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with opener.open(request, timeout=30) as response:
            result = HttpResult(
                response.status,
                response.headers,
                json.loads(response.read().decode("utf-8")),
            )
    except urllib.error.HTTPError as error:
        result = HttpResult(
            error.code,
            error.headers,
            json.loads(error.read().decode("utf-8")),
        )
    require(
        result.headers.get("X-Request-ID") == headers["X-Request-ID"]
        and result.headers.get("Cache-Control") == "private, no-store",
        "P7-02 multipart request boundary drifted",
    )
    return HttpResult(
        result.status,
        result.headers,
        result.body,
        request_id=headers["X-Request-ID"],
        trace_id=headers["X-Trace-ID"],
    )


def binary_evidence_request(
    opener,
    base_url: str,
    path: str,
    *,
    csrf_token: str,
) -> tuple[int, Any, bytes, dict[str, Any] | None]:
    headers = document_runtime.command_headers(
        csrf_token,
        f"p7-02-runtime-{FIXTURE_RUN_ID}-content",
    )
    headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=b"{}",
        headers=headers,
        method="POST",
    )
    problem = None
    try:
        with opener.open(request, timeout=30) as response:
            status = response.status
            response_headers = response.headers
            content = response.read()
    except urllib.error.HTTPError as error:
        status = error.code
        response_headers = error.headers
        content = error.read()
        problem = json.loads(content.decode("utf-8"))
    require(
        response_headers.get("X-Request-ID") == headers["X-Request-ID"],
        "P7-02 binary request identity was not echoed",
    )
    return status, response_headers, content, problem


def sanitized_trial_failure(result: HttpResult) -> str:
    """Expose only bounded problem codes and field paths from synthetic requests."""

    details: list[str] = []
    code = result.body.get("code")
    if isinstance(code, str) and _PROBLEM_CODE.fullmatch(code) is not None:
        details.append(f"problem_code={code}")
    field_errors = result.body.get("fieldErrors")
    paths: list[str] = []
    if isinstance(field_errors, list):
        for item in field_errors[:5]:
            path = item.get("path") if isinstance(item, dict) else None
            if (
                isinstance(path, str)
                and _FIELD_PATH.fullmatch(path) is not None
                and path not in paths
            ):
                paths.append(path)
    if paths:
        details.append(f"field_paths={','.join(paths)}")
    diagnostic = _safe_unexpected_diagnostic(result)
    if diagnostic is not None:
        diagnostic_code, exception_type = diagnostic
        if diagnostic_code.startswith("P703_QUALITY_"):
            details.append(f"server_stage={diagnostic_code}")
        details.append(f"exception_type={exception_type}")
    return f" [{'; '.join(details)}]" if details else ""


def _safe_unexpected_diagnostic(result: HttpResult) -> tuple[str, str] | None:
    """Read only an allowlisted stage and type from this request's safe BFF log."""

    if (
        result.status != 500
        or not isinstance(result.trace_id, str)
        or _TRACE_ID.fullmatch(result.trace_id) is None
    ):
        return None
    log_path = BENCH_PATH / "logs" / "npi_core.log"
    try:
        with log_path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - _DIAGNOSTIC_TAIL_BYTES))
            content = handle.read(_DIAGNOSTIC_TAIL_BYTES)
    except OSError:
        return None
    encoded_trace = result.trace_id.encode("ascii")
    matches = tuple(_SAFE_UNEXPECTED_DIAGNOSTIC.finditer(content))
    for match in matches:
        if (
            match.group("trace") == encoded_trace
            and match.group("code").startswith(_SAFE_QUALITY_STAGE_PREFIX)
        ):
            return (
                match.group("code").decode("ascii"),
                match.group("exception").decode("ascii"),
            )
    for match in reversed(matches):
        if (
            match.group("trace") == encoded_trace
            and match.group("code") == b"UNEXPECTED_BFF_EXCEPTION"
        ):
            return (
                "UNEXPECTED_BFF_EXCEPTION",
                match.group("exception").decode("ascii"),
            )
    return None


def exact_single(values: object, label: str) -> dict[str, Any]:
    require(
        isinstance(values, list)
        and len(values) == 1
        and isinstance(values[0], dict),
        f"P7-01 {label} cardinality drifted",
    )
    return values[0]


def require_uuid(value: object, label: str) -> str:
    require(isinstance(value, str), f"P7-01 {label} identity is unavailable")
    require(str(UUID(value)) == value, f"P7-01 {label} identity drifted")
    return value


def require_hash(value: object, label: str) -> str:
    require(
        isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None,
        f"P7-01 {label} hash drifted",
    )
    return value


def assert_capabilities(body: dict[str, Any]) -> None:
    require(
        body.get("capabilities") == EXPECTED_CAPABILITIES,
        "P7-01 resource availability/reservation truth drifted",
    )
    require(
        body.get("permissions") == EXPECTED_PERMISSIONS,
        "P7-01 command permission projection drifted",
    )


def assert_workspace(
    result: HttpResult,
    project_id: str,
    *,
    expected_plans: int,
) -> dict[str, Any]:
    require(result.status in {200, 201}, "P7-01 planning workspace failed")
    require(
        set(result.body) == {"projectGlobalId", "plans", "capabilities", "permissions"},
        "P7-01 planning workspace contract drifted",
    )
    require(
        result.body.get("projectGlobalId") == project_id,
        "P7-01 planning workspace Project identity drifted",
    )
    plans = result.body.get("plans")
    require(
        isinstance(plans, list) and len(plans) == expected_plans,
        "P7-01 planning workspace Plan cardinality drifted",
    )
    assert_capabilities(result.body)
    return result.body


def assert_detail(
    result: HttpResult,
    project_id: str,
    *,
    plan_id: str | None = None,
    revisions: int,
    rounds: int,
    links: int,
) -> dict[str, Any]:
    require(result.status in {200, 201}, "P7-01 Trial Plan detail failed")
    require(
        set(result.body)
        == {
            "projectGlobalId",
            "planGlobalId",
            "latestRevision",
            "revisions",
            "rounds",
            "actionLinks",
            "capabilities",
            "permissions",
        },
        "P7-01 Trial Plan detail contract drifted",
    )
    require(
        result.body.get("projectGlobalId") == project_id,
        "P7-01 Trial Plan Project identity drifted",
    )
    observed_plan_id = require_uuid(result.body.get("planGlobalId"), "Plan")
    if plan_id is not None:
        require(observed_plan_id == plan_id, "P7-01 stable Plan identity drifted")
    require(
        len(result.body.get("revisions", [])) == revisions
        and len(result.body.get("rounds", [])) == rounds
        and len(result.body.get("actionLinks", [])) == links,
        "P7-01 immutable projection cardinality drifted",
    )
    assert_capabilities(result.body)
    for revision in result.body["revisions"]:
        require(
            revision.get("planGlobalId") == observed_plan_id
            and revision.get("projectGlobalId") == project_id,
            "P7-01 revision containment drifted",
        )
        require_hash(revision.get("snapshotHash"), "Plan revision")
        resources = revision.get("resources")
        require(
            isinstance(resources, list)
            and len(resources) >= 2
            and all(item.get("bookingState") == "unavailable" for item in resources),
            "P7-01 resource proposal claimed booking success",
        )
        require(
            revision.get("measurementPlan", {}).get("lockState")
            == "planning_intent_only",
            "P7-01 measurement intent claimed an input lock",
        )
    return result.body


def assert_execution_workspace(
    result: HttpResult,
    project_id: str,
    round_id: str,
    *,
    state: str,
    round_version: int,
    locks: int,
    actuals: int,
    samples: int,
    evidence: int,
    pending: int,
) -> dict[str, Any]:
    require(result.status in {200, 201}, "P7-02 execution workspace failed")
    require(
        set(result.body)
        == {
            "projectGlobalId",
            "round",
            "inputLocks",
            "actualRevisions",
            "sampleBatchRevisions",
            "evidence",
            "pendingFiles",
            "missingFacts",
            "capabilities",
            "permissions",
        },
        "P7-02 execution workspace contract drifted",
    )
    require(
        result.body.get("projectGlobalId") == project_id
        and result.body.get("round", {}).get("globalId") == round_id
        and result.body.get("round", {}).get("currentState") == state
        and result.body.get("round", {}).get("optimisticVersion") == round_version,
        "P7-02 exact Round execution identity drifted",
    )
    require(
        len(result.body.get("inputLocks", [])) == locks
        and len(result.body.get("actualRevisions", [])) == actuals
        and len(result.body.get("sampleBatchRevisions", [])) == samples
        and len(result.body.get("evidence", [])) == evidence
        and len(result.body.get("pendingFiles", [])) == pending,
        "P7-02 immutable execution cardinality drifted",
    )
    require(
        result.body.get("capabilities") == EXPECTED_EXECUTION_CAPABILITIES,
        "P7-02 unavailable authority projection drifted",
    )
    for collection in (
        "inputLocks",
        "actualRevisions",
        "sampleBatchRevisions",
        "evidence",
    ):
        for value in result.body[collection]:
            require_hash(value.get("snapshotHash"), f"P7-02 {collection}")
    serialized = json.dumps(result.body, sort_keys=True)
    require(
        "fileUrl" not in serialized and "/private/files/" not in serialized,
        "P7-02 private file location escaped the closed BFF",
    )
    return result.body


def assert_quality_workspace(
    result: HttpResult,
    project_id: str,
    round_id: str,
    *,
    cavity_results: int,
    trial_defects: int,
    tooling_defects: int,
    verifications: int,
) -> dict[str, Any]:
    require(result.status in {200, 201}, "P7-03 quality workspace failed")
    require(
        set(result.body)
        == {
            "projectGlobalId",
            "trialRound",
            "cavityResultRevisions",
            "defectRevisions",
            "verificationRevisions",
            "cavityFilters",
            "pareto",
            "permissions",
            "externalEffects",
        },
        "P7-03 quality workspace contract drifted",
    )
    require(
        result.body.get("projectGlobalId") == project_id
        and result.body.get("trialRound", {}).get("globalId") == round_id
        and result.body.get("trialRound", {}).get("currentState") == "running"
        and result.body.get("trialRound", {}).get("optimisticVersion") == 3,
        "P7-03 exact quality Round identity drifted",
    )
    defect_rows = result.body.get("defectRevisions")
    require(
        isinstance(defect_rows, list)
        and len(result.body.get("cavityResultRevisions", [])) == cavity_results
        and sum(value.get("source") == "trial" for value in defect_rows) == trial_defects
        and sum(value.get("source") == "tooling" for value in defect_rows) == tooling_defects
        and len(result.body.get("verificationRevisions", [])) == verifications,
        "P7-03 immutable quality cardinality drifted",
    )
    require(
        result.body.get("permissions") == EXPECTED_QUALITY_PERMISSIONS
        and result.body.get("externalEffects") == EXPECTED_QUALITY_EXTERNAL_EFFECTS,
        "P7-03 quality authority projection drifted",
    )
    for value in result.body["cavityResultRevisions"]:
        require_hash(value.get("snapshotHash"), "P7-03 cavity result")
    for wrapper in defect_rows:
        require(
            set(wrapper) == {"source", "revision"}
            and wrapper.get("source") in {"tooling", "trial"}
            and isinstance(wrapper.get("revision"), dict),
            "P7-03 defect source wrapper drifted",
        )
        require_hash(wrapper["revision"].get("snapshotHash"), "P7-03 defect")
    for value in result.body["verificationRevisions"]:
        require_hash(value.get("snapshotHash"), "P7-03 verification")
    serialized = json.dumps(result.body, sort_keys=True)
    require(
        "fileUrl" not in serialized
        and "/private/files/" not in serialized
        and all(value in serialized for value in EXPECTED_QUALITY_EXTERNAL_EFFECTS.values()),
        "P7-03 quality workspace leaked a private path or external success",
    )
    return result.body


def assert_review_workspace(
    result: HttpResult,
    project_id: str,
    round_id: str,
    *,
    state: str,
    round_version: int,
    policies: int,
    comparisons: int,
    references: int,
    conclusions: int,
) -> dict[str, Any]:
    require(result.status in {200, 201}, "P7-04 review workspace failed")
    require(
        set(result.body)
        == {
            "projectGlobalId",
            "trialRound",
            "policyVersions",
            "comparisonSnapshots",
            "reviewReferenceRevisions",
            "conclusionRevisions",
            "permissions",
            "externalEffects",
        },
        "P7-04 review workspace contract drifted",
    )
    trial_round = result.body.get("trialRound", {})
    require(
        result.body.get("projectGlobalId") == project_id
        and trial_round.get("globalId") == round_id
        and trial_round.get("currentState") == state
        and trial_round.get("optimisticVersion") == round_version,
        "P7-04 exact review Round identity drifted",
    )
    require(
        len(result.body.get("policyVersions", [])) == policies
        and len(result.body.get("comparisonSnapshots", [])) == comparisons
        and len(result.body.get("reviewReferenceRevisions", [])) == references
        and len(result.body.get("conclusionRevisions", [])) == conclusions,
        "P7-04 immutable review cardinality drifted",
    )
    for collection in (
        "policyVersions",
        "comparisonSnapshots",
        "reviewReferenceRevisions",
        "conclusionRevisions",
    ):
        for value in result.body[collection]:
            require_hash(value.get("snapshotHash"), f"P7-04 {collection}")
    require(
        result.body.get("externalEffects") == EXPECTED_REVIEW_EXTERNAL_EFFECTS,
        "P7-04 review projection claimed unavailable external authority",
    )
    serialized = json.dumps(result.body, sort_keys=True)
    require(
        "customerSignature" in serialized
        and "proposal_only" in serialized
        and "fileUrl" not in serialized
        and "/private/files/" not in serialized,
        "P7-04 review workspace leaked a private path or external success",
    )
    return result.body


def measurement_payload(*, corrected: bool, observed_at: str) -> list[dict[str, object]]:
    return [
        {
            "characteristicKey": "cavity_width",
            "label": "Controlled synthetic cavity width",
            "unit": "mm",
            "nominalValue": "10.00",
            "lowerLimit": "9.90",
            "upperLimit": "10.10",
            "required": True,
            "state": "measured",
            "value": "10.04" if corrected else "10.12",
            "source": "manual",
            "observedAt": observed_at,
        }
    ]


def quality_round_context(
    round_value: dict[str, Any],
    input_lock: dict[str, Any],
) -> dict[str, object]:
    return {
        "expectedRoundOptimisticVersion": round_value["optimisticVersion"],
        "expectedRoundSnapshotHash": round_value["snapshotHash"],
        "expectedInputLockRevisionGlobalId": input_lock["globalId"],
        "expectedInputLockRevisionSnapshotHash": input_lock["snapshotHash"],
    }


def cavity_result_payload(
    context: dict[str, Any],
    *,
    corrected: bool,
) -> dict[str, object]:
    value = {
        **quality_round_context(context["round"], context["inputLock"]),
        "measurements": measurement_payload(
            corrected=corrected,
            observed_at=(
                "2027-02-10T10:00:00Z"
                if corrected
                else "2027-02-10T09:30:00Z"
            ),
        ),
        "reason": (
            "Append the corrected controlled cavity result."
            if corrected
            else "Record the initial controlled cavity result."
        ),
    }
    if not corrected:
        value.update(
            {
                "sampleBatchRevisionGlobalId": context["sample"]["globalId"],
                "expectedSampleBatchRevisionSnapshotHash": context["sample"]["snapshotHash"],
                "cavityGlobalId": context["cavityId"],
                "evidence": [
                    {
                        "globalId": context["evidence"]["globalId"],
                        "snapshotHash": context["evidence"]["snapshotHash"],
                    }
                ],
            }
        )
    return value


def defect_action_payload(
    context: dict[str, Any],
    *,
    action: dict[str, Any] | None,
    state: str,
    verification: dict[str, Any] | None = None,
) -> dict[str, object]:
    return {
        "globalId": None if action is None else action["globalId"],
        "actionType": "corrective",
        "state": state,
        "detail": "Correct the controlled cavity fit and verify the exact target Round.",
        "responsibleMember": {
            "globalId": RESPONSIBLE_MEMBER_ID,
            "optimisticVersion": 1,
        },
        "dueDate": "2027-02-12",
        "targetRoundGlobalId": context["round"]["globalId"],
        "targetRoundOptimisticVersion": context["round"]["optimisticVersion"],
        "targetRoundSnapshotHash": context["round"]["snapshotHash"],
        "verificationRevisionGlobalId": (
            None if verification is None else verification["globalId"]
        ),
        "verificationRevisionSnapshotHash": (
            None if verification is None else verification["snapshotHash"]
        ),
    }


def defect_payload(
    observation: dict[str, Any],
    target: dict[str, Any],
    *,
    predecessor: dict[str, Any] | None,
    predecessor_kind: str | None,
    business_code: str,
    state: str,
    action_state: str,
    action: dict[str, Any] | None,
    verification: dict[str, Any] | None = None,
    create_new: bool = False,
) -> dict[str, object]:
    root_cause_recorded = state != "open"
    return {
        **quality_round_context(observation["round"], observation["inputLock"]),
        **(
            {"defectGlobalId": None}
            if create_new
            else {"defectGlobalId": predecessor["defectGlobalId"]}
            if predecessor_kind == "tooling_defect_revision"
            else {}
        ),
        "expectedPredecessorKind": predecessor_kind,
        "expectedPredecessorGlobalId": (
            None if predecessor is None else predecessor["globalId"]
        ),
        "expectedPredecessorSnapshotHash": (
            None if predecessor is None else predecessor["snapshotHash"]
        ),
        "expectedDefectVersion": (
            None if predecessor is None else predecessor["defectVersion"]
        ),
        "sampleBatchRevisionGlobalId": observation["sample"]["globalId"],
        "expectedSampleBatchRevisionSnapshotHash": observation["sample"]["snapshotHash"],
        "cavityGlobalId": observation["cavityId"],
        "businessCode": business_code,
        "title": "Controlled synthetic cavity flash",
        "description": "Controlled exact-cavity defect observation for runtime proof.",
        "categoryKey": "appearance.flash",
        "location": "parting-line",
        "severity": "high",
        "blocking": True,
        "state": state,
        "rootCauseState": "recorded" if root_cause_recorded else "pending",
        "rootCause": (
            "Controlled synthetic cavity fit variation."
            if root_cause_recorded
            else None
        ),
        "responsibleMember": (
            None
            if state == "open"
            else {"globalId": RESPONSIBLE_MEMBER_ID, "optimisticVersion": 1}
        ),
        "occurrenceCount": 2,
        "actions": [
            defect_action_payload(
                target,
                action=action,
                state=action_state,
                verification=verification,
            )
        ],
        "evidence": [
            {
                "globalId": observation["evidence"]["globalId"],
                "snapshotHash": observation["evidence"]["snapshotHash"],
            }
        ],
        "reason": f"Record controlled defect state {state}.",
    }


def verification_payload(
    context: dict[str, Any],
    defect: dict[str, Any],
    action: dict[str, Any],
    cavity_result: dict[str, Any],
    *,
    result: str,
    predecessor: dict[str, Any] | None,
) -> dict[str, object]:
    return {
        "expectedDefectRevisionGlobalId": defect["globalId"],
        "expectedDefectRevisionSnapshotHash": defect["snapshotHash"],
        "actionGlobalId": action["globalId"],
        "verificationGlobalId": (
            None if predecessor is None else predecessor["verificationGlobalId"]
        ),
        "expectedAttemptSequence": (
            None if predecessor is None else predecessor["attemptSequence"]
        ),
        "targetRoundGlobalId": context["round"]["globalId"],
        "expectedTargetRoundOptimisticVersion": context["round"]["optimisticVersion"],
        "expectedTargetRoundSnapshotHash": context["round"]["snapshotHash"],
        "cavityResultRevisionGlobalId": cavity_result["globalId"],
        "expectedCavityResultRevisionSnapshotHash": cavity_result["snapshotHash"],
        "verifierMember": {
            "globalId": VERIFIER_MEMBER_ID,
            "optimisticVersion": 1,
        },
        "result": result,
        "finding": (
            "Independent controlled verification passed."
            if result == "pass"
            else "Independent controlled verification found a remaining deviation."
        ),
        "observedAt": (
            "2027-02-10T11:30:00Z" if result == "pass" else "2027-02-10T11:00:00Z"
        ),
        "evidence": [
            {
                "globalId": context["evidence"]["globalId"],
                "snapshotHash": context["evidence"]["snapshotHash"],
            }
        ],
    }


def create_payload(master_id: str) -> dict[str, object]:
    return {
        "toolingMasterGlobalId": master_id,
        "purpose": "first_trial",
        "objective": "Synthetic controlled Trial planning objective",
        "plannedStartAt": "2027-02-10T08:00:00Z",
        "plannedEndAt": "2027-02-10T12:00:00Z",
        "resources": [
            {
                "kind": "machine",
                "sourceSystem": "NPI_ONE",
                "sourceObjectId": f"SYN-MACHINE-{FIXTURE_RUN_ID[:12]}",
                "label": "Synthetic machine proposal",
            },
            {
                "kind": "material",
                "sourceSystem": "ERPNEXT",
                "sourceObjectId": f"SYN-MATERIAL-{FIXTURE_RUN_ID[:12]}",
                "label": "Synthetic material proposal",
                "quantity": 25,
                "unit": "kg",
            },
        ],
        "responsibleMemberGlobalIds": [RESPONSIBLE_MEMBER_ID],
        "sampleQuantity": 80,
        "measurementPlan": {
            "description": "Synthetic dimensional inspection intent"
        },
        "reason": "Create one immutable synthetic Trial Plan revision.",
    }


def revise_payload(initial: dict[str, Any]) -> dict[str, object]:
    payload = create_payload(str(initial["toolingMasterGlobalId"]))
    payload.pop("toolingMasterGlobalId")
    payload.update(
        {
            "expectedRevisionGlobalId": initial["globalId"],
            "expectedRevisionSnapshotHash": initial["snapshotHash"],
            "expectedPlanVersion": initial["planVersion"],
            "objective": "Synthetic successor Trial planning objective",
            "plannedEndAt": "2027-02-10T13:00:00Z",
            "sampleQuantity": 96,
            "reason": "Append one exact immutable Trial Plan successor.",
        }
    )
    return payload


def round_payload(
    successor: dict[str, Any],
    *,
    display_label: str = "T0",
) -> dict[str, object]:
    return {
        "expectedPlanRevisionGlobalId": successor["globalId"],
        "expectedPlanRevisionSnapshotHash": successor["snapshotHash"],
        "displayLabel": display_label,
        "reason": "Create one distinct planned synthetic Trial Round.",
    }


def action_payload(successor: dict[str, Any], round_id: str) -> dict[str, object]:
    return {
        "expectedPlanRevisionGlobalId": successor["globalId"],
        "expectedPlanRevisionSnapshotHash": successor["snapshotHash"],
        "trialRoundGlobalId": round_id,
        "actions": [
            {
                "actionKey": "trial-dimension-check",
                "title": "Verify synthetic dimensional evidence",
                "description": "Record the exact controlled synthetic result.",
                "responsibleMemberGlobalId": RESPONSIBLE_MEMBER_ID,
                "dueAt": "2027-02-11T08:00:00Z",
                "severity": "high",
                "blocking": True,
            }
        ],
        "reason": "Generate one governed synthetic Project action.",
    }


def execution_material_payload() -> dict[str, object]:
    return {
        "sourceSystem": "NPI_ONE",
        "sourceObjectId": f"P702-MATERIAL-{FIXTURE_RUN_ID[:12]}",
        "lotBatchCode": f"P702-LOT-{FIXTURE_RUN_ID[:12]}",
        "label": "Controlled PA66 material observation",
        "color": "natural",
        "additive": None,
        "observedAt": "2027-02-10T07:45:00Z",
    }


def prepare_execution_payload(references: list[dict[str, object]]) -> dict[str, object]:
    return {
        "expectedRoundOptimisticVersion": 1,
        "references": references,
        "material": execution_material_payload(),
        "parameterDefinitions": [
            {
                "key": "melt_temperature",
                "category": "temperature",
                "valueKind": "decimal",
                "required": True,
                "unit": "degC",
                "targetValue": "285",
                "lowerLimit": "280",
                "upperLimit": "290",
            }
        ],
        "reason": "Freeze exact controlled Trial execution inputs.",
    }


def actual_context_payload(*, successor: bool) -> dict[str, object]:
    return {
        "resources": [
            {
                "kind": "machine",
                "sourceSystem": "NPI_ONE",
                "sourceObjectId": f"P702-MACHINE-{FIXTURE_RUN_ID[:12]}",
                "label": "Controlled 160T machine observation",
            }
        ],
        "material": execution_material_payload(),
        "environment": [
            {
                "key": "ambient_temperature",
                "value": "23",
                "unit": "degC",
                "observedAt": "2027-02-10T08:05:00Z",
            }
        ],
        "parameters": [
            {
                "definitionKey": "melt_temperature",
                "state": "measured",
                "value": "287" if successor else "285",
                "unit": "degC",
                "source": "manual",
                "observedAt": (
                    "2027-02-10T08:20:00Z"
                    if successor
                    else "2027-02-10T08:10:00Z"
                ),
            }
        ],
        "operatorUserId": "operator@example.invalid",
        "executionStartedAt": "2027-02-10T08:00:00Z",
        "reason": (
            "Append one exact manual Actual successor."
            if successor
            else "Record the exact manual Trial start context."
        ),
    }


def sample_payload(
    cavity_ids: list[str],
    *,
    successor: bool,
    label_prefix: str = "P702",
) -> dict[str, object]:
    return {
        "label": f"{label_prefix}-SAMPLE-{FIXTURE_RUN_ID[:12]}",
        "cavityGlobalIds": cavity_ids,
        "quantity": 80,
        "unit": "piece",
        "packaging": (
            "Two sealed labelled trays"
            if successor
            else "Two sealed trays"
        ),
        "destination": "Controlled dimensional laboratory",
        "feedbackText": None,
        "feedbackSource": None,
        "feedbackObservedAt": None,
    }


def replay_references(input_lock: dict[str, Any]) -> list[dict[str, object]]:
    return [
        {
            "globalId": value["globalId"],
            "kind": value["kind"],
            "expectedOptimisticVersion": value["optimisticVersion"],
        }
        for value in input_lock["references"]
    ]


def fixture_master_id(administrator, base_url: str, project_id: str) -> str:
    workspace = tooling_runtime.tooling_request(
        administrator,
        base_url,
        tooling_runtime.tooling_path(project_id),
        query_key="p701-master",
    )
    require(workspace.status == 200, "P7-01 predecessor Tooling workspace failed")
    candidates = [
        value
        for value in workspace.body.get("masters", [])
        if value.get("title") == "Synthetic shared front housing tool"
        and value.get("originatingProjectGlobalId") == project_id
    ]
    return require_uuid(exact_single(candidates, "Tooling Master")["globalId"], "Master")


def second_project_id(administrator, base_url: str) -> str:
    rows = list_resources(
        administrator,
        base_url,
        "NPI Engineering Project",
        filters=[["business_code", "=", tooling_runtime.SECOND_PROJECT_CODE]],
        fields=["global_id"],
    )
    return require_uuid(exact_single(rows, "second Project")["global_id"], "second Project")


def persisted_counts(administrator, base_url: str, project_id: str) -> dict[str, int]:
    counts = {
        doctype: len(
            tooling_runtime.rows(
                administrator,
                base_url,
                doctype,
                [["project_global_id", "=", project_id]],
                ["global_id"],
            )
        )
        for doctype in TRIAL_DOCTYPES
    }
    for operation in (
        "trial_plan.create",
        "trial_plan.revise",
        "trial_round.create",
        "trial_plan.generate_actions",
        "trial_round.prepare",
        "trial_round.start",
        "trial_actual.append",
        "trial_sample.create",
        "trial_sample.revise",
        "trial_file.upload",
        "trial_evidence.bind",
        "trial_evidence.content.read",
        "trial_cavity_result.create",
        "trial_cavity_result.revise",
        "trial_defect.create",
        "trial_defect.revise",
        "trial_defect.verify",
        "trial_round.begin_analysis",
        "trial_comparison.create",
        "trial_review_reference.create",
        "trial_review_reference.revise",
        "trial_conclusion.submit",
        "trial_conclusion.decide",
        "trial_conclusion.reopen",
    ):
        counts[f"audit:{operation}"] = len(
            tooling_runtime.rows(
                administrator,
                base_url,
                "NPI Audit Event",
                [["operation", "=", operation]],
                ["event_id"],
            )
        )
    counts["outbox"] = len(
        tooling_runtime.rows(
            administrator, base_url, "NPI Outbox Message", [], ["event_id"]
        )
    )
    counts["inbox"] = len(
        tooling_runtime.rows(
            administrator, base_url, "NPI Inbox Message", [], ["event_id"]
        )
    )
    return counts


def verify_generic_mutation_denial(
    administrator,
    base_url: str,
    csrf_token: str,
    project_id: str,
) -> None:
    for doctype in TRIAL_DOCTYPES:
        protected = TRIAL_PROTECTED_FIELDS[doctype]
        rows = tooling_runtime.rows(
            administrator,
            base_url,
            doctype,
            [["project_global_id", "=", project_id]],
            ["global_id", protected],
        )
        require(bool(rows), f"P7-01 retained {doctype} is unavailable")
        retained = rows[0]
        name = require_uuid(retained.get("global_id"), doctype)
        before = get_resource(administrator, base_url, doctype, name)
        before_hash = before.body.get("data", {}).get(protected)
        rejected_update = update_resource(
            administrator,
            base_url,
            doctype,
            name,
            {protected: "0" * 64},
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
            and isinstance(before_hash, str)
            and len(before_hash) == 64
            and rejected_update.status in {403, 417}
            and rejected_delete.status in {403, 417}
            and after.status == 200
            and after.body.get("data", {}).get(protected) == before_hash,
            f"P7-01 immutable {doctype} accepted generic mutation",
        )


def verify_idor(
    administrator,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
    project_id: str,
    plan_id: str,
    round_id: str,
    review_round_id: str,
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
        denied = trial_request(
            unrelated,
            base_url,
            plan_path(project_id, plan_id),
            query_key="unrelated-plan",
        )
        absent = trial_request(
            unrelated,
            base_url,
            plan_path(ABSENT_PROJECT_ID, ABSENT_PLAN_ID),
            query_key="absent-plan",
        )
        validate_problem(denied, 404, "TRIAL_UNAVAILABLE")
        validate_problem(absent, 404, "TRIAL_UNAVAILABLE")
        require(
            {
                key: denied.body.get(key)
                for key in ("type", "title", "status", "code", "retryable")
            }
            == {
                key: absent.body.get(key)
                for key in ("type", "title", "status", "code", "retryable")
            },
            "P7-01 unauthorized and absent Trial identities are distinguishable",
        )
        denied_execution = trial_request(
            unrelated,
            base_url,
            execution_path(project_id, round_id),
            query_key="unrelated-execution",
        )
        absent_execution = trial_request(
            unrelated,
            base_url,
            execution_path(ABSENT_PROJECT_ID, round_id),
            query_key="absent-execution",
        )
        validate_problem(
            denied_execution,
            404,
            "TRIAL_EXECUTION_UNAVAILABLE",
        )
        validate_problem(
            absent_execution,
            404,
            "TRIAL_EXECUTION_UNAVAILABLE",
        )
        require(
            {
                key: denied_execution.body.get(key)
                for key in ("type", "title", "status", "code", "retryable")
            }
            == {
                key: absent_execution.body.get(key)
                for key in ("type", "title", "status", "code", "retryable")
            },
            "P7-02 unauthorized and absent execution identities are distinguishable",
        )
        denied_quality = trial_request(
            unrelated,
            base_url,
            quality_path(project_id, round_id),
            query_key="unrelated-quality",
        )
        absent_quality = trial_request(
            unrelated,
            base_url,
            quality_path(ABSENT_PROJECT_ID, round_id),
            query_key="absent-quality",
        )
        validate_problem(denied_quality, 404, "TRIAL_QUALITY_UNAVAILABLE")
        validate_problem(absent_quality, 404, "TRIAL_QUALITY_UNAVAILABLE")
        require(
            {
                key: denied_quality.body.get(key)
                for key in ("type", "title", "status", "code", "retryable")
            }
            == {
                key: absent_quality.body.get(key)
                for key in ("type", "title", "status", "code", "retryable")
            },
            "P7-03 unauthorized and absent quality identities are distinguishable",
        )
        denied_review = trial_request(
            unrelated,
            base_url,
            review_path(project_id, review_round_id),
            query_key="unrelated-review",
        )
        absent_review = trial_request(
            unrelated,
            base_url,
            review_path(ABSENT_PROJECT_ID, review_round_id),
            query_key="absent-review",
        )
        validate_problem(denied_review, 404, "TRIAL_REVIEW_UNAVAILABLE")
        validate_problem(absent_review, 404, "TRIAL_REVIEW_UNAVAILABLE")
        require(
            {
                key: denied_review.body.get(key)
                for key in ("type", "title", "status", "code", "retryable")
            }
            == {
                key: absent_review.body.get(key)
                for key in ("type", "title", "status", "code", "retryable")
            },
            "P7-04 unauthorized and absent review identities are distinguishable",
        )
    finally:
        delete_disposable_user(
            administrator,
            base_url,
            UNRELATED_USER,
            csrf_token,
        )
    cross_project = trial_request(
        administrator,
        base_url,
        plan_path(second_project_id(administrator, base_url), plan_id),
        query_key="cross-project-plan",
    )
    absent_authorized = trial_request(
        administrator,
        base_url,
        plan_path(project_id, ABSENT_PLAN_ID),
        query_key="absent-authorized-plan",
    )
    validate_problem(cross_project, 404, "TRIAL_UNAVAILABLE")
    validate_problem(absent_authorized, 404, "TRIAL_UNAVAILABLE")
    cross_project_execution = trial_request(
        administrator,
        base_url,
        execution_path(second_project_id(administrator, base_url), round_id),
        query_key="cross-project-execution",
    )
    absent_authorized_execution = trial_request(
        administrator,
        base_url,
        execution_path(project_id, ABSENT_PLAN_ID),
        query_key="absent-authorized-execution",
    )
    validate_problem(
        cross_project_execution,
        404,
        "TRIAL_EXECUTION_UNAVAILABLE",
    )
    validate_problem(
        absent_authorized_execution,
        404,
        "TRIAL_EXECUTION_UNAVAILABLE",
    )
    cross_project_quality = trial_request(
        administrator,
        base_url,
        quality_path(second_project_id(administrator, base_url), round_id),
        query_key="cross-project-quality",
    )
    absent_authorized_quality = trial_request(
        administrator,
        base_url,
        quality_path(project_id, ABSENT_PLAN_ID),
        query_key="absent-authorized-quality",
    )
    validate_problem(cross_project_quality, 404, "TRIAL_QUALITY_UNAVAILABLE")
    validate_problem(absent_authorized_quality, 404, "TRIAL_QUALITY_UNAVAILABLE")
    cross_project_review = trial_request(
        administrator,
        base_url,
        review_path(second_project_id(administrator, base_url), review_round_id),
        query_key="cross-project-review",
    )
    absent_authorized_review = trial_request(
        administrator,
        base_url,
        review_path(project_id, ABSENT_PLAN_ID),
        query_key="absent-authorized-review",
    )
    validate_problem(cross_project_review, 404, "TRIAL_REVIEW_UNAVAILABLE")
    validate_problem(absent_authorized_review, 404, "TRIAL_REVIEW_UNAVAILABLE")


def run_execution_fresh(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    project_id: str,
    round_id: str,
) -> dict[str, object]:
    initial = trial_request(
        administrator,
        base_url,
        execution_path(project_id, round_id),
        query_key="execution-empty",
    )
    initial_body = assert_execution_workspace(
        initial,
        project_id,
        round_id,
        state="planned",
        round_version=1,
        locks=0,
        actuals=0,
        samples=0,
        evidence=0,
        pending=0,
    )
    require(
        initial_body.get("missingFacts")
        == ["actual_context", "evidence", "input_lock", "sample_batch"]
        and initial_body.get("permissions")
        == {
            "canPrepare": True,
            "canStart": False,
            "canRecordActual": False,
            "canManageSamples": False,
            "canManageEvidence": False,
        },
        "P7-02 planned execution readiness drifted",
    )

    reference_context = run_bench_fixture(
        "trial_execution_reference_context",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "tooling_master_id": initial_body["round"]["toolingMasterGlobalId"],
        },
    )
    references = reference_context.get("references")
    cavity_ids = reference_context.get("cavityIds")
    require(
        isinstance(references, list)
        and len(references) >= 8
        and isinstance(cavity_ids, list)
        and bool(cavity_ids),
        "P7-02 exact predecessor reference context is unavailable",
    )
    prepared_payload = prepare_execution_payload(references)
    prepared = command(
        administrator,
        base_url,
        csrf_token,
        execution_path(project_id, round_id, ":prepare"),
        prepared_payload,
        PREPARE_KEY,
    )
    prepared_body = assert_execution_workspace(
        prepared,
        project_id,
        round_id,
        state="prepared",
        round_version=2,
        locks=1,
        actuals=0,
        samples=0,
        evidence=0,
        pending=0,
    )
    input_lock = exact_single(prepared_body["inputLocks"], "P7-02 input lock")
    input_lock_id = require_uuid(input_lock.get("globalId"), "P7-02 input lock")
    require(
        input_lock.get("lockVersion") == 1
        and len(input_lock.get("references", [])) == len(references)
        and all(
            require_hash(value.get("snapshotHash"), "P7-02 locked reference")
            for value in input_lock["references"]
        ),
        "P7-02 exact-version input lock drifted",
    )
    prepared_replay = command(
        administrator,
        base_url,
        csrf_token,
        execution_path(project_id, round_id, ":prepare"),
        prepared_payload,
        PREPARE_KEY,
    )
    require(
        prepared_replay.headers.get("Idempotency-Replayed") == "true"
        and prepared_replay.body == prepared.body,
        "P7-02 same-process prepare replay changed sealed response truth",
    )
    stale_prepare = trial_request(
        administrator,
        base_url,
        execution_path(project_id, round_id, ":prepare"),
        method="POST",
        payload={**prepared_payload, "reason": "Rejected stale prepare attempt."},
        csrf_token=csrf_token,
        idempotency_key=STALE_PREPARE_KEY,
    )
    validate_problem(stale_prepare, 409, "TRIAL_EXECUTION_CONFLICT")

    start_payload = {
        "expectedRoundOptimisticVersion": 2,
        "expectedInputLockRevisionGlobalId": input_lock_id,
        "expectedInputLockVersion": 1,
        **actual_context_payload(successor=False),
    }
    started = command(
        administrator,
        base_url,
        csrf_token,
        execution_path(project_id, round_id, ":start"),
        start_payload,
        START_KEY,
    )
    started_body = assert_execution_workspace(
        started,
        project_id,
        round_id,
        state="running",
        round_version=3,
        locks=1,
        actuals=1,
        samples=0,
        evidence=0,
        pending=0,
    )
    first_actual = exact_single(
        started_body["actualRevisions"],
        "P7-02 initial Actual",
    )
    first_actual_id = require_uuid(
        first_actual.get("globalId"),
        "P7-02 initial Actual",
    )
    require(
        first_actual.get("actualVersion") == 1
        and first_actual.get("acquisitionMode") == "manual",
        "P7-02 initial manual Actual truth drifted",
    )

    actual_payload = {
        "expectedRoundOptimisticVersion": 3,
        "expectedActualRevisionGlobalId": first_actual_id,
        "expectedActualVersion": 1,
        **actual_context_payload(successor=True),
    }
    revised_actual = command(
        administrator,
        base_url,
        csrf_token,
        execution_path(project_id, round_id, "/actual-revisions"),
        actual_payload,
        ACTUAL_KEY,
    )
    actual_body = assert_execution_workspace(
        revised_actual,
        project_id,
        round_id,
        state="running",
        round_version=3,
        locks=1,
        actuals=2,
        samples=0,
        evidence=0,
        pending=0,
    )
    actual_successor = actual_body["actualRevisions"][-1]
    require(
        actual_successor.get("actualVersion") == 2
        and actual_successor.get("predecessorGlobalId") == first_actual_id
        and actual_successor.get("predecessorSnapshotHash")
        == first_actual.get("snapshotHash")
        and actual_successor.get("actualGlobalId")
        == first_actual.get("actualGlobalId"),
        "P7-02 immutable Actual successor lineage drifted",
    )
    stale_actual = trial_request(
        administrator,
        base_url,
        execution_path(project_id, round_id, "/actual-revisions"),
        method="POST",
        payload={**actual_payload, "reason": "Rejected stale Actual successor."},
        csrf_token=csrf_token,
        idempotency_key=STALE_ACTUAL_KEY,
    )
    validate_problem(stale_actual, 409, "TRIAL_EXECUTION_CONFLICT")

    first_sample_payload = {
        "expectedRoundOptimisticVersion": 3,
        "expectedInputLockRevisionGlobalId": input_lock_id,
        "sample": sample_payload(cavity_ids, successor=False),
        "reason": "Create one exact controlled Sample Batch.",
    }
    created_sample = command(
        administrator,
        base_url,
        csrf_token,
        execution_path(project_id, round_id, "/sample-batches"),
        first_sample_payload,
        SAMPLE_KEY,
    )
    sample_body = assert_execution_workspace(
        created_sample,
        project_id,
        round_id,
        state="running",
        round_version=3,
        locks=1,
        actuals=2,
        samples=1,
        evidence=0,
        pending=0,
    )
    first_sample = exact_single(
        sample_body["sampleBatchRevisions"],
        "P7-02 initial Sample Batch",
    )
    sample_batch_id = require_uuid(
        first_sample.get("sampleBatchGlobalId"),
        "P7-02 Sample Batch",
    )
    sample_revision_id = require_uuid(
        first_sample.get("globalId"),
        "P7-02 initial Sample revision",
    )
    revised_sample_payload = {
        "expectedRoundOptimisticVersion": 3,
        "expectedRevisionGlobalId": sample_revision_id,
        "expectedSampleVersion": 1,
        "sample": sample_payload(cavity_ids, successor=True),
        "reason": "Append the exact controlled Sample packaging correction.",
    }
    revised_sample = command(
        administrator,
        base_url,
        csrf_token,
        sample_path(project_id, round_id, sample_batch_id),
        revised_sample_payload,
        SAMPLE_REVISE_KEY,
    )
    revised_sample_body = assert_execution_workspace(
        revised_sample,
        project_id,
        round_id,
        state="running",
        round_version=3,
        locks=1,
        actuals=2,
        samples=2,
        evidence=0,
        pending=0,
    )
    sample_successor = revised_sample_body["sampleBatchRevisions"][-1]
    sample_successor_id = require_uuid(
        sample_successor.get("globalId"),
        "P7-02 Sample successor",
    )
    require(
        sample_successor.get("sampleVersion") == 2
        and sample_successor.get("sampleBatchGlobalId") == sample_batch_id
        and sample_successor.get("predecessorGlobalId") == sample_revision_id
        and sample_successor.get("predecessorSnapshotHash")
        == first_sample.get("snapshotHash"),
        "P7-02 immutable Sample successor lineage drifted",
    )

    uploaded = multipart_trial_upload(
        administrator,
        base_url,
        execution_path(project_id, round_id, "/files"),
        csrf_token=csrf_token,
        idempotency_key=UPLOAD_KEY,
        round_version=3,
    )
    require(
        uploaded.status == 201
        and uploaded.headers.get("Idempotency-Replayed") == "false",
        f"P7-02 evidence upload returned HTTP {uploaded.status}",
    )
    uploaded_body = assert_execution_workspace(
        uploaded,
        project_id,
        round_id,
        state="running",
        round_version=3,
        locks=1,
        actuals=2,
        samples=2,
        evidence=0,
        pending=1,
    )
    pending_file = exact_single(uploaded_body["pendingFiles"], "pending evidence")
    file_revision_id = require_uuid(
        pending_file.get("globalId"),
        "P7-02 pending File Revision",
    )
    storage_file_name = pending_file.get("fileName")
    require(
        pending_file.get("scanState") == "pending"
        and pending_file.get("privacy") == "private"
        and pending_file.get("optimisticVersion") == 1
        and pending_file.get("sha256")
        == hashlib.sha256(EVIDENCE_CONTENT).hexdigest(),
        "P7-02 pending private upload truth drifted",
    )
    require(
        isinstance(storage_file_name, str)
        and 1 <= len(storage_file_name) <= 255
        and storage_file_name.endswith(".csv")
        and "/" not in storage_file_name
        and "\\" not in storage_file_name,
        "P7-02 Frappe storage filename boundary drifted",
    )
    upload_replay = multipart_trial_upload(
        administrator,
        base_url,
        execution_path(project_id, round_id, "/files"),
        csrf_token=csrf_token,
        idempotency_key=UPLOAD_KEY,
        round_version=3,
    )
    require(
        upload_replay.status == 201
        and upload_replay.headers.get("Idempotency-Replayed") == "true"
        and upload_replay.body == uploaded.body,
        "P7-02 same-process upload replay changed sealed response truth",
    )

    bind_payload = {
        "expectedRoundOptimisticVersion": 3,
        "role": "measurement_report",
        "fileRevisionGlobalId": file_revision_id,
        "expectedFileOptimisticVersion": 2,
        "sampleBatchRevisionGlobalId": sample_successor_id,
        "expectedSampleVersion": 2,
    }
    pending_bind = trial_request(
        administrator,
        base_url,
        execution_path(project_id, round_id, "/evidence"),
        method="POST",
        payload=bind_payload,
        csrf_token=csrf_token,
        idempotency_key=BIND_KEY,
    )
    validate_problem(
        pending_bind,
        404,
        "TRIAL_EXECUTION_REFERENCE_UNAVAILABLE",
    )
    scan = run_bench_fixture(
        "observe_trial_file_scan",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "round_id": round_id,
            "file_revision_id": file_revision_id,
        },
    )
    require(
        scan.get("scanState") == "clean"
        and scan.get("optimisticVersion") == 2
        and scan.get("sha256") == pending_file.get("sha256"),
        "P7-02 controlled scanner observation drifted",
    )
    clean_result = trial_request(
        administrator,
        base_url,
        execution_path(project_id, round_id),
        query_key="execution-clean-pending",
    )
    clean_body = assert_execution_workspace(
        clean_result,
        project_id,
        round_id,
        state="running",
        round_version=3,
        locks=1,
        actuals=2,
        samples=2,
        evidence=0,
        pending=1,
    )
    require(
        clean_body["pendingFiles"][0].get("scanState") == "clean"
        and clean_body["pendingFiles"][0].get("optimisticVersion") == 2,
        "P7-02 clean pending evidence projection drifted",
    )
    bound = command(
        administrator,
        base_url,
        csrf_token,
        execution_path(project_id, round_id, "/evidence"),
        bind_payload,
        BIND_KEY,
    )
    bound_body = assert_execution_workspace(
        bound,
        project_id,
        round_id,
        state="running",
        round_version=3,
        locks=1,
        actuals=2,
        samples=2,
        evidence=1,
        pending=0,
    )
    evidence = exact_single(bound_body["evidence"], "P7-02 evidence reference")
    evidence_id = require_uuid(evidence.get("globalId"), "P7-02 evidence")
    require(
        evidence.get("fileRevisionGlobalId") == file_revision_id
        and evidence.get("fileSha256") == pending_file.get("sha256")
        and evidence.get("sampleBatchRevisionGlobalId") == sample_successor_id
        and evidence.get("sampleBatchRevisionSnapshotHash")
        == sample_successor.get("snapshotHash")
        and bound_body.get("missingFacts") == [],
        "P7-02 exact clean evidence binding drifted",
    )
    bound_replay = command(
        administrator,
        base_url,
        csrf_token,
        execution_path(project_id, round_id, "/evidence"),
        bind_payload,
        BIND_KEY,
    )
    require(
        bound_replay.headers.get("Idempotency-Replayed") == "true"
        and bound_replay.body == bound.body,
        "P7-02 same-process evidence replay changed sealed response truth",
    )

    status, headers, content, problem = binary_evidence_request(
        administrator,
        base_url,
        execution_path(project_id, round_id, f"/evidence/{evidence_id}:content"),
        csrf_token=csrf_token,
    )
    require(
        status == 200
        and problem is None
        and content == EVIDENCE_CONTENT
        and headers.get("Content-Type", "").startswith("text/csv")
        and headers.get("Cache-Control") == "private, no-store"
        and headers.get("X-Content-Type-Options") == "nosniff"
        and headers.get("Content-Security-Policy") == "sandbox; default-src 'none'"
        and headers.get("Referrer-Policy") == "no-referrer"
        and f'filename="{storage_file_name}"'
        in headers.get("Content-Disposition", ""),
        "P7-02 audited private evidence content boundary drifted",
    )
    return {
        "actualSuccessorId": require_uuid(
            actual_successor.get("globalId"),
            "P7-02 Actual successor",
        ),
        "evidenceId": evidence_id,
        "fileRevisionId": file_revision_id,
        "inputLockId": input_lock_id,
        "inputLock": input_lock,
        "round": bound_body["round"],
        "sample": sample_successor,
        "evidence": evidence,
        "cavityIds": cavity_ids,
        "sampleBatchId": sample_batch_id,
        "sampleSuccessorId": sample_successor_id,
    }


def run_target_execution_fresh(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    project_id: str,
    plan_id: str,
    plan_successor: dict[str, Any],
    source_input_lock: dict[str, Any],
) -> dict[str, Any]:
    created_round = command(
        administrator,
        base_url,
        csrf_token,
        plan_path(project_id, plan_id, "/rounds"),
        round_payload(plan_successor, display_label="T1"),
        TARGET_ROUND_KEY,
    )
    detail = assert_detail(
        created_round,
        project_id,
        plan_id=plan_id,
        revisions=2,
        rounds=2,
        links=1,
    )
    target_round = exact_single(
        [value for value in detail["rounds"] if value.get("displayLabel") == "T1"],
        "P7-03 target Round",
    )
    round_id = require_uuid(target_round.get("globalId"), "P7-03 target Round")
    require(
        target_round.get("roundSequence") == 1
        and target_round.get("currentState") == "planned"
        and target_round.get("optimisticVersion") == 1,
        "P7-03 distinct target Round truth drifted",
    )
    references = replay_references(source_input_lock)
    prepared = command(
        administrator,
        base_url,
        csrf_token,
        execution_path(project_id, round_id, ":prepare"),
        prepare_execution_payload(references),
        TARGET_PREPARE_KEY,
    )
    prepared_body = assert_execution_workspace(
        prepared,
        project_id,
        round_id,
        state="prepared",
        round_version=2,
        locks=1,
        actuals=0,
        samples=0,
        evidence=0,
        pending=0,
    )
    input_lock = exact_single(prepared_body["inputLocks"], "P7-03 target input lock")
    started = command(
        administrator,
        base_url,
        csrf_token,
        execution_path(project_id, round_id, ":start"),
        {
            "expectedRoundOptimisticVersion": 2,
            "expectedInputLockRevisionGlobalId": input_lock["globalId"],
            "expectedInputLockVersion": 1,
            **actual_context_payload(successor=False),
        },
        TARGET_START_KEY,
    )
    started_body = assert_execution_workspace(
        started,
        project_id,
        round_id,
        state="running",
        round_version=3,
        locks=1,
        actuals=1,
        samples=0,
        evidence=0,
        pending=0,
    )
    cavity_ids = [
        value["globalId"]
        for value in input_lock["references"]
        if value.get("kind") == "cavity"
    ]
    created_sample = command(
        administrator,
        base_url,
        csrf_token,
        execution_path(project_id, round_id, "/sample-batches"),
        {
            "expectedRoundOptimisticVersion": 3,
            "expectedInputLockRevisionGlobalId": input_lock["globalId"],
            "sample": sample_payload(
                cavity_ids,
                successor=False,
                label_prefix="P703",
            ),
            "reason": "Create one exact target-Round Sample Batch.",
        },
        TARGET_SAMPLE_KEY,
    )
    sample_body = assert_execution_workspace(
        created_sample,
        project_id,
        round_id,
        state="running",
        round_version=3,
        locks=1,
        actuals=1,
        samples=1,
        evidence=0,
        pending=0,
    )
    sample = exact_single(sample_body["sampleBatchRevisions"], "P7-03 target Sample")
    uploaded = multipart_trial_upload(
        administrator,
        base_url,
        execution_path(project_id, round_id, "/files"),
        csrf_token=csrf_token,
        idempotency_key=TARGET_UPLOAD_KEY,
        round_version=3,
    )
    require(
        uploaded.status == 201
        and uploaded.headers.get("Idempotency-Replayed") == "false",
        "P7-03 target evidence upload failed",
    )
    uploaded_body = assert_execution_workspace(
        uploaded,
        project_id,
        round_id,
        state="running",
        round_version=3,
        locks=1,
        actuals=1,
        samples=1,
        evidence=0,
        pending=1,
    )
    pending_file = exact_single(uploaded_body["pendingFiles"], "P7-03 target File")
    run_bench_fixture(
        "observe_trial_file_scan",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "round_id": round_id,
            "file_revision_id": pending_file["globalId"],
        },
    )
    bound = command(
        administrator,
        base_url,
        csrf_token,
        execution_path(project_id, round_id, "/evidence"),
        {
            "expectedRoundOptimisticVersion": 3,
            "role": "measurement_report",
            "fileRevisionGlobalId": pending_file["globalId"],
            "expectedFileOptimisticVersion": 2,
            "sampleBatchRevisionGlobalId": sample["globalId"],
            "expectedSampleVersion": 1,
        },
        TARGET_BIND_KEY,
    )
    bound_body = assert_execution_workspace(
        bound,
        project_id,
        round_id,
        state="running",
        round_version=3,
        locks=1,
        actuals=1,
        samples=1,
        evidence=1,
        pending=0,
    )
    return {
        "round": bound_body["round"],
        "inputLock": input_lock,
        "sample": sample,
        "evidence": exact_single(bound_body["evidence"], "P7-03 target evidence"),
        "cavityId": cavity_ids[0],
    }


def run_quality_fresh(
    administrator,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
    *,
    project_id: str,
    primary: dict[str, Any],
    target: dict[str, Any],
) -> dict[str, object]:
    document_runtime.create_internal_fixture_user(
        administrator,
        base_url,
        VERIFIER_USER,
        fixture_password,
        csrf_token,
    )
    run_bench_fixture(
        "ensure_trial_quality_verifier_member",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    round_id = primary["round"]["globalId"]
    initial = assert_quality_workspace(
        trial_request(
            administrator,
            base_url,
            quality_path(project_id, round_id),
            query_key="quality-empty",
        ),
        project_id,
        round_id,
        cavity_results=0,
        trial_defects=0,
        tooling_defects=2,
        verifications=0,
    )
    tooling_tip = max(
        (
            value["revision"]
            for value in initial["defectRevisions"]
            if value.get("source") == "tooling"
        ),
        key=lambda value: value["defectVersion"],
    )

    created_result = command(
        administrator,
        base_url,
        csrf_token,
        quality_path(project_id, round_id, "/cavity-results"),
        cavity_result_payload(primary, corrected=False),
        CAVITY_CREATE_KEY,
    )
    created_result_body = assert_quality_workspace(
        created_result,
        project_id,
        round_id,
        cavity_results=1,
        trial_defects=0,
        tooling_defects=2,
        verifications=0,
    )
    first_result = exact_single(
        created_result_body["cavityResultRevisions"],
        "P7-03 initial cavity result",
    )
    result_replay = command(
        administrator,
        base_url,
        csrf_token,
        quality_path(project_id, round_id, "/cavity-results"),
        cavity_result_payload(primary, corrected=False),
        CAVITY_CREATE_KEY,
    )
    require(
        result_replay.headers.get("Idempotency-Replayed") == "true"
        and result_replay.body == created_result.body,
        "P7-03 same-process cavity-result replay drifted",
    )
    revised_result_payload = {
        **cavity_result_payload(primary, corrected=True),
        "expectedRevisionGlobalId": first_result["globalId"],
        "expectedRevisionSnapshotHash": first_result["snapshotHash"],
        "expectedResultVersion": 1,
    }
    revised_result = command(
        administrator,
        base_url,
        csrf_token,
        quality_path(
            project_id,
            round_id,
            f"/cavity-results/{first_result['cavityResultGlobalId']}/revisions",
        ),
        revised_result_payload,
        CAVITY_REVISE_KEY,
    )
    revised_result_body = assert_quality_workspace(
        revised_result,
        project_id,
        round_id,
        cavity_results=2,
        trial_defects=0,
        tooling_defects=2,
        verifications=0,
    )
    result_successor = revised_result_body["cavityResultRevisions"][-1]
    require(
        result_successor.get("resultVersion") == 2
        and result_successor.get("predecessorGlobalId") == first_result["globalId"]
        and result_successor.get("predecessorSnapshotHash") == first_result["snapshotHash"]
        and result_successor.get("cavityResultGlobalId")
        == first_result["cavityResultGlobalId"],
        "P7-03 cavity-result successor lineage drifted",
    )

    continued_tooling = command(
        administrator,
        base_url,
        csrf_token,
        quality_path(project_id, round_id, "/defects"),
        defect_payload(
            primary,
            target,
            predecessor=tooling_tip,
            predecessor_kind="tooling_defect_revision",
            business_code=tooling_tip["businessCode"],
            state="in_progress",
            action_state="completed",
            action=None,
        ),
        CONTINUE_TOOLING_DEFECT_KEY,
    )
    continued_body = assert_quality_workspace(
        continued_tooling,
        project_id,
        round_id,
        cavity_results=2,
        trial_defects=1,
        tooling_defects=2,
        verifications=0,
    )
    tooling_trial_tip = exact_single(
        [
            value["revision"]
            for value in continued_body["defectRevisions"]
            if value.get("source") == "trial"
        ],
        "P7-03 continued Tooling defect",
    )
    tooling_action = exact_single(tooling_trial_tip["actions"], "P7-03 Tooling action")
    require(
        tooling_trial_tip.get("defectGlobalId") == tooling_tip["defectGlobalId"]
        and tooling_trial_tip.get("defectVersion") == tooling_tip["defectVersion"] + 1
        and tooling_trial_tip.get("predecessorKind") == "tooling_defect_revision"
        and tooling_action.get("targetRoundGlobalId") == target["round"]["globalId"],
        "P7-03 P6-to-P7 defect single-tip continuation drifted",
    )
    cross_round = command(
        administrator,
        base_url,
        csrf_token,
        quality_path(
            project_id,
            target["round"]["globalId"],
            f"/defects/{tooling_trial_tip['defectGlobalId']}/revisions",
        ),
        defect_payload(
            target,
            target,
            predecessor=tooling_trial_tip,
            predecessor_kind="trial_defect_revision",
            business_code=tooling_tip["businessCode"],
            state="ready_for_verification",
            action_state="completed",
            action=tooling_action,
        ),
        CROSS_ROUND_DEFECT_KEY,
    )
    cross_round_body = assert_quality_workspace(
        cross_round,
        project_id,
        target["round"]["globalId"],
        cavity_results=0,
        trial_defects=2,
        tooling_defects=2,
        verifications=0,
    )
    cross_round_tip = max(
        (
            value["revision"]
            for value in cross_round_body["defectRevisions"]
            if value.get("source") == "trial"
        ),
        key=lambda value: value["defectVersion"],
    )
    require(
        cross_round_tip.get("trialRoundGlobalId") == target["round"]["globalId"]
        and cross_round_tip.get("predecessorGlobalId") == tooling_trial_tip["globalId"]
        and cross_round_tip.get("inputLockRevisionGlobalId") == target["inputLock"]["globalId"],
        "P7-03 cross-Round defect observation drifted",
    )

    new_created = command(
        administrator,
        base_url,
        csrf_token,
        quality_path(project_id, round_id, "/defects"),
        defect_payload(
            primary,
            primary,
            predecessor=None,
            predecessor_kind=None,
            business_code="P7-03-DEF-NEW",
            state="open",
            action_state="planned",
            action=None,
            create_new=True,
        ),
        NEW_DEFECT_CREATE_KEY,
    )
    new_created_body = assert_quality_workspace(
        new_created,
        project_id,
        round_id,
        cavity_results=2,
        trial_defects=3,
        tooling_defects=2,
        verifications=0,
    )
    new_tip = exact_single(
        [
            value["revision"]
            for value in new_created_body["defectRevisions"]
            if value.get("source") == "trial"
            and value.get("revision", {}).get("businessCode") == "P7-03-DEF-NEW"
        ],
        "P7-03 new defect",
    )
    new_action = exact_single(new_tip["actions"], "P7-03 new defect action")
    new_replay = command(
        administrator,
        base_url,
        csrf_token,
        quality_path(project_id, round_id, "/defects"),
        defect_payload(
            primary,
            primary,
            predecessor=None,
            predecessor_kind=None,
            business_code="P7-03-DEF-NEW",
            state="open",
            action_state="planned",
            action=None,
            create_new=True,
        ),
        NEW_DEFECT_CREATE_KEY,
    )
    require(
        new_replay.headers.get("Idempotency-Replayed") == "true"
        and new_replay.body == new_created.body,
        "P7-03 same-process defect replay drifted",
    )

    for index, (state, action_state) in enumerate(
        (
            ("assigned", "planned"),
            ("in_progress", "completed"),
            ("ready_for_verification", "completed"),
        )
    ):
        revised = command(
            administrator,
            base_url,
            csrf_token,
            quality_path(
                project_id,
                round_id,
                f"/defects/{new_tip['defectGlobalId']}/revisions",
            ),
            defect_payload(
                primary,
                primary,
                predecessor=new_tip,
                predecessor_kind="trial_defect_revision",
                business_code="P7-03-DEF-NEW",
                state=state,
                action_state=action_state,
                action=new_action,
            ),
            NEW_DEFECT_KEYS[index],
        )
        revised_body = revised.body
        new_tip = max(
            (
                value["revision"]
                for value in revised_body["defectRevisions"]
                if value.get("source") == "trial"
                and value.get("revision", {}).get("businessCode") == "P7-03-DEF-NEW"
            ),
            key=lambda value: value["defectVersion"],
        )
        new_action = exact_single(new_tip["actions"], "P7-03 successor action")
        require(new_tip.get("state") == state, "P7-03 defect state transition drifted")

    failed = command(
        administrator,
        base_url,
        csrf_token,
        quality_path(
            project_id,
            round_id,
            f"/defects/{new_tip['defectGlobalId']}/verifications",
        ),
        verification_payload(
            primary,
            new_tip,
            new_action,
            result_successor,
            result="fail",
            predecessor=None,
        ),
        VERIFY_FAIL_KEY,
    )
    failed_body = assert_quality_workspace(
        failed,
        project_id,
        round_id,
        cavity_results=2,
        trial_defects=6,
        tooling_defects=2,
        verifications=1,
    )
    failed_verification = exact_single(
        failed_body["verificationRevisions"],
        "P7-03 failed verification",
    )
    require(
        failed_verification.get("result") == "fail"
        and failed_verification.get("attemptSequence") == 1,
        "P7-03 failed independent verification drifted",
    )
    passed = command(
        administrator,
        base_url,
        csrf_token,
        quality_path(
            project_id,
            round_id,
            f"/defects/{new_tip['defectGlobalId']}/verifications",
        ),
        verification_payload(
            primary,
            new_tip,
            new_action,
            result_successor,
            result="pass",
            predecessor=failed_verification,
        ),
        VERIFY_PASS_KEY,
    )
    passed_body = assert_quality_workspace(
        passed,
        project_id,
        round_id,
        cavity_results=2,
        trial_defects=6,
        tooling_defects=2,
        verifications=2,
    )
    passed_verification = passed_body["verificationRevisions"][-1]
    require(
        passed_verification.get("result") == "pass"
        and passed_verification.get("attemptSequence") == 2
        and passed_verification.get("verificationGlobalId")
        == failed_verification.get("verificationGlobalId"),
        "P7-03 passed independent verification succession drifted",
    )

    for offset, state in enumerate(("closed", "reopened"), start=3):
        revised = command(
            administrator,
            base_url,
            csrf_token,
            quality_path(
                project_id,
                round_id,
                f"/defects/{new_tip['defectGlobalId']}/revisions",
            ),
            defect_payload(
                primary,
                primary,
                predecessor=new_tip,
                predecessor_kind="trial_defect_revision",
                business_code="P7-03-DEF-NEW",
                state=state,
                action_state="verified",
                action=new_action,
                verification=passed_verification,
            ),
            NEW_DEFECT_KEYS[offset],
        )
        new_tip = max(
            (
                value["revision"]
                for value in revised.body["defectRevisions"]
                if value.get("source") == "trial"
                and value.get("revision", {}).get("businessCode") == "P7-03-DEF-NEW"
            ),
            key=lambda value: value["defectVersion"],
        )
        new_action = exact_single(new_tip["actions"], "P7-03 closed action")
        require(new_tip.get("state") == state, "P7-03 close/reopen transition drifted")

    before_failed = persisted_counts(administrator, base_url, project_id)
    stale_result = trial_request(
        administrator,
        base_url,
        quality_path(
            project_id,
            round_id,
            f"/cavity-results/{first_result['cavityResultGlobalId']}/revisions",
        ),
        method="POST",
        payload={**revised_result_payload, "reason": "Reject stale cavity result."},
        csrf_token=csrf_token,
        idempotency_key=CAVITY_STALE_KEY,
    )
    validate_problem(stale_result, 409, "TRIAL_QUALITY_CONFLICT")
    idempotency_conflict_payload = defect_payload(
        primary,
        primary,
        predecessor=None,
        predecessor_kind=None,
        business_code="P7-03-DEF-NEW",
        state="open",
        action_state="planned",
        action=None,
        create_new=True,
    )
    idempotency_conflict_payload["title"] = "Different controlled payload"
    idempotency_conflict = trial_request(
        administrator,
        base_url,
        quality_path(project_id, round_id, "/defects"),
        method="POST",
        payload=idempotency_conflict_payload,
        csrf_token=csrf_token,
        idempotency_key=NEW_DEFECT_CREATE_KEY,
    )
    validate_problem(idempotency_conflict, 409, "TRIAL_IDEMPOTENCY_CONFLICT")
    require(
        persisted_counts(administrator, base_url, project_id) == before_failed,
        "P7-03 failed commands changed immutable cardinality",
    )
    final = assert_quality_workspace(
        trial_request(
            administrator,
            base_url,
            quality_path(project_id, round_id),
            query_key="quality-final",
        ),
        project_id,
        round_id,
        cavity_results=2,
        trial_defects=8,
        tooling_defects=2,
        verifications=2,
    )
    require(
        new_tip.get("state") == "reopened"
        and new_action.get("state") == "verified"
        and new_action.get("verificationRevisionGlobalId")
        == passed_verification.get("globalId")
        and final.get("pareto") == [
            {
                "categoryKey": "appearance.flash",
                "severity": "high",
                "cavityGlobalId": primary["cavityId"],
                "count": 6,
            }
        ],
        "P7-03 close/reopen, verified action or Pareto truth drifted",
    )
    return {
        "cavityResultId": first_result["cavityResultGlobalId"],
        "continuedToolingDefectId": tooling_tip["defectGlobalId"],
        "crossRoundRevisionId": cross_round_tip["globalId"],
        "newDefectId": new_tip["defectGlobalId"],
        "verificationId": passed_verification["verificationGlobalId"],
    }


def run_quality_replay(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    project_id: str,
    primary: dict[str, Any],
    target: dict[str, Any],
) -> None:
    round_id = primary["round"]["globalId"]
    quality = assert_quality_workspace(
        trial_request(
            administrator,
            base_url,
            quality_path(project_id, round_id),
            query_key="quality-replay-context",
        ),
        project_id,
        round_id,
        cavity_results=2,
        trial_defects=8,
        tooling_defects=2,
        verifications=2,
    )
    cavity_one, cavity_two = quality["cavityResultRevisions"]
    wrappers = quality["defectRevisions"]
    tooling_tip = max(
        (
            value["revision"]
            for value in wrappers
            if value.get("source") == "tooling"
        ),
        key=lambda value: value["defectVersion"],
    )
    trial_revisions = [
        value["revision"] for value in wrappers if value.get("source") == "trial"
    ]
    tooling_trial = sorted(
        [
            value
            for value in trial_revisions
            if value["defectGlobalId"] == tooling_tip["defectGlobalId"]
        ],
        key=lambda value: value["defectVersion"],
    )
    new_trial = sorted(
        [value for value in trial_revisions if value["businessCode"] == "P7-03-DEF-NEW"],
        key=lambda value: value["defectVersion"],
    )
    require(
        len(tooling_trial) == 2 and len(new_trial) == 6,
        "P7-03 retained defect replay context drifted",
    )
    failed_verification, passed_verification = quality["verificationRevisions"]

    replay_cases: list[tuple[str, dict[str, object], str]] = [
        (
            quality_path(project_id, round_id, "/cavity-results"),
            cavity_result_payload(primary, corrected=False),
            CAVITY_CREATE_KEY,
        ),
        (
            quality_path(
                project_id,
                round_id,
                f"/cavity-results/{cavity_one['cavityResultGlobalId']}/revisions",
            ),
            {
                **cavity_result_payload(primary, corrected=True),
                "expectedRevisionGlobalId": cavity_one["globalId"],
                "expectedRevisionSnapshotHash": cavity_one["snapshotHash"],
                "expectedResultVersion": 1,
            },
            CAVITY_REVISE_KEY,
        ),
        (
            quality_path(project_id, round_id, "/defects"),
            defect_payload(
                primary,
                target,
                predecessor=tooling_tip,
                predecessor_kind="tooling_defect_revision",
                business_code=tooling_tip["businessCode"],
                state="in_progress",
                action_state="completed",
                action=None,
            ),
            CONTINUE_TOOLING_DEFECT_KEY,
        ),
        (
            quality_path(
                project_id,
                target["round"]["globalId"],
                f"/defects/{tooling_tip['defectGlobalId']}/revisions",
            ),
            defect_payload(
                target,
                target,
                predecessor=tooling_trial[0],
                predecessor_kind="trial_defect_revision",
                business_code=tooling_tip["businessCode"],
                state="ready_for_verification",
                action_state="completed",
                action=exact_single(
                    tooling_trial[0]["actions"],
                    "P7-03 replay Tooling action",
                ),
            ),
            CROSS_ROUND_DEFECT_KEY,
        ),
        (
            quality_path(project_id, round_id, "/defects"),
            defect_payload(
                primary,
                primary,
                predecessor=None,
                predecessor_kind=None,
                business_code="P7-03-DEF-NEW",
                state="open",
                action_state="planned",
                action=None,
                create_new=True,
            ),
            NEW_DEFECT_CREATE_KEY,
        ),
    ]
    states = (
        ("assigned", "planned", None),
        ("in_progress", "completed", None),
        ("ready_for_verification", "completed", None),
        ("closed", "verified", passed_verification),
        ("reopened", "verified", passed_verification),
    )
    for index, (state, action_state, verification) in enumerate(states):
        predecessor = new_trial[index]
        replay_cases.append(
            (
                quality_path(
                    project_id,
                    round_id,
                    f"/defects/{predecessor['defectGlobalId']}/revisions",
                ),
                defect_payload(
                    primary,
                    primary,
                    predecessor=predecessor,
                    predecessor_kind="trial_defect_revision",
                    business_code="P7-03-DEF-NEW",
                    state=state,
                    action_state=action_state,
                    action=exact_single(
                        predecessor["actions"],
                        "P7-03 replay defect action",
                    ),
                    verification=verification,
                ),
                NEW_DEFECT_KEYS[index],
            )
        )
    ready_defect = new_trial[3]
    ready_action = exact_single(ready_defect["actions"], "P7-03 replay ready action")
    replay_cases.extend(
        (
            (
                quality_path(
                    project_id,
                    round_id,
                    f"/defects/{ready_defect['defectGlobalId']}/verifications",
                ),
                verification_payload(
                    primary,
                    ready_defect,
                    ready_action,
                    cavity_two,
                    result="fail",
                    predecessor=None,
                ),
                VERIFY_FAIL_KEY,
            ),
            (
                quality_path(
                    project_id,
                    round_id,
                    f"/defects/{ready_defect['defectGlobalId']}/verifications",
                ),
                verification_payload(
                    primary,
                    ready_defect,
                    ready_action,
                    cavity_two,
                    result="pass",
                    predecessor=failed_verification,
                ),
                VERIFY_PASS_KEY,
            ),
        )
    )
    before = persisted_counts(administrator, base_url, project_id)
    for path, payload, key in replay_cases:
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
            f"P7-03 cross-process command was not replayed: {key}",
        )
    require(
        persisted_counts(administrator, base_url, project_id) == before,
        "P7-03 cross-process replay changed immutable cardinality or integration truth",
    )


def review_policy_context(
    policy: dict[str, Any],
    trial_round: dict[str, Any],
) -> dict[str, object]:
    return {
        "policyRevisionGlobalId": policy["globalId"],
        "expectedPolicyRevisionSnapshotHash": policy["snapshotHash"],
        "expectedRoundOptimisticVersion": trial_round["optimisticVersion"],
        "expectedRoundSnapshotHash": trial_round["snapshotHash"],
    }


def review_reference_payload(
    context: dict[str, Any],
    policy: dict[str, Any],
    trial_round: dict[str, Any],
    comparison: dict[str, Any],
    *,
    kind: str,
    predecessor: dict[str, Any] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        **review_policy_context(policy, trial_round),
        "comparisonSnapshotGlobalId": comparison["globalId"],
        "expectedComparisonSnapshotHash": comparison["snapshotHash"],
        "referenceKind": kind,
        "partRevisionGlobalId": context["partRevisionGlobalId"],
        "expectedPartRevisionSnapshotHash": context["partRevisionSnapshotHash"],
        "toolingMasterGlobalId": context["toolingMasterGlobalId"],
        "toolingRevisionGlobalId": context["toolingRevisionGlobalId"],
        "expectedToolingRevisionSnapshotHash": context[
            "toolingRevisionSnapshotHash"
        ],
        "toolingSetGlobalId": context["toolingSetGlobalId"],
        "expectedToolingSetSnapshotHash": context["toolingSetSnapshotHash"],
        "fileRevisionGlobalId": context["fileRevisionGlobalId"],
        "expectedFileRevisionSnapshotHash": context["fileRevisionSnapshotHash"],
        "effectiveFrom": "2027-02-10",
        "effectiveTo": None,
        "reason": (
            "Append the exact controlled quality report reference successor."
            if predecessor
            else f"Create the exact {kind} review reference."
        ),
    }
    if predecessor:
        payload.update(
            {
                "referenceGlobalId": predecessor["referenceGlobalId"],
                "expectedReferenceRevisionGlobalId": predecessor["globalId"],
                "expectedReferenceRevisionSnapshotHash": predecessor["snapshotHash"],
                "expectedReferenceVersion": predecessor["referenceVersion"],
                "effectiveTo": "2027-12-31",
            }
        )
    return payload


def conclusion_payload(
    policy: dict[str, Any],
    trial_round: dict[str, Any],
    comparison: dict[str, Any],
    references: list[dict[str, Any]],
    *,
    predecessor: dict[str, Any] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        **review_policy_context(policy, trial_round),
        "comparisonSnapshotGlobalId": comparison["globalId"],
        "expectedComparisonSnapshotHash": comparison["snapshotHash"],
        "reviewReferences": [
            {"globalId": value["globalId"], "snapshotHash": value["snapshotHash"]}
            for value in references
        ],
        "conclusionCode": "conditional_pass",
        "proposedNextWork": ["Verify the controlled process-tuning proposal."],
        "proposedGateEffect": "Proposal only; no Gate mutation is authorized.",
        "proposedNpiEffect": "Proposal only; no NPI readiness mutation is authorized.",
        "reason": (
            "Resubmit the immutable controlled Trial conclusion successor."
            if predecessor
            else "Submit the immutable controlled Trial conclusion."
        ),
    }
    if predecessor:
        payload.update(
            {
                "conclusionGlobalId": predecessor["conclusionGlobalId"],
                "expectedConclusionRevisionGlobalId": predecessor["globalId"],
                "expectedConclusionRevisionSnapshotHash": predecessor["snapshotHash"],
                "expectedConclusionVersion": predecessor["conclusionVersion"],
            }
        )
    return payload


def prepare_trial_review_actor(
    administrator,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
):
    created = create_resource(
        administrator,
        base_url,
        "User",
        {
            "email": REVIEW_USER,
            "enabled": 1,
            "first_name": "NPI Trial Review",
            "language": "en",
            "last_name": "Runtime Manager",
            "new_password": fixture_password,
            "roles": [
                {"role": "Desk User"},
                {"role": "NPI API User"},
                {"role": "System Manager"},
            ],
            "send_welcome_email": 0,
            "user_type": "System User",
        },
        csrf_token,
    )
    require(
        created.status in {200, 201},
        "P7-04 review actor fixture could not be created",
    )
    retained = get_resource(administrator, base_url, "User", REVIEW_USER)
    data = retained.body.get("data", {})
    roles = {
        str(value.get("role"))
        for value in data.get("roles", [])
        if isinstance(value, dict)
    }
    require(
        retained.status == 200
        and data.get("enabled") == 1
        and data.get("user_type") == "System User"
        and {"NPI API User", "System Manager"} <= roles,
        "P7-04 review actor authority drifted",
    )
    reviewer = login(base_url, REVIEW_USER, fixture_password)
    return reviewer, bootstrap_csrf(reviewer, base_url, REVIEW_USER)


def run_review_fresh(
    administrator,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
    *,
    project_id: str,
    plan_id: str,
    plan_revision: dict[str, Any],
    primary: dict[str, Any],
    target: dict[str, Any],
) -> dict[str, object]:
    round_id = target["round"]["globalId"]
    reviewer, reviewer_csrf = prepare_trial_review_actor(
        administrator,
        base_url,
        csrf_token,
        fixture_password,
    )
    fixture = run_bench_fixture(
        "ensure_trial_review_policy",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "plan_id": plan_id,
            "plan_revision_id": plan_revision["globalId"],
            "plan_revision_snapshot_hash": plan_revision["snapshotHash"],
            "round_id": round_id,
            "input_lock_id": target["inputLock"]["globalId"],
            "file_revision_id": target["evidence"]["fileRevisionGlobalId"],
        },
    )
    initial = assert_review_workspace(
        trial_request(
            reviewer,
            base_url,
            review_path(project_id, round_id),
            query_key="review-initial",
        ),
        project_id,
        round_id,
        state="running",
        round_version=3,
        policies=1,
        comparisons=0,
        references=0,
        conclusions=0,
    )
    policy = exact_single(initial["policyVersions"], "P7-04 review policy")
    require(
        policy.get("globalId") == REVIEW_POLICY_REVISION_ID
        and policy.get("requiredReferenceKinds") == ["controlled_quality_report"]
        and policy.get("authorityBindings", [{}])[0].get("member", {}).get("globalId")
        == REVIEW_MEMBER_ID
        and initial.get("permissions", {}).get("beginAnalysis") is True,
        "P7-04 exact policy or authority binding drifted",
    )
    begun = command(
        reviewer,
        base_url,
        reviewer_csrf,
        execution_path(project_id, round_id, ":begin-analysis"),
        {
            **review_policy_context(policy, initial["trialRound"]),
            "reason": "Begin the exact controlled Trial review analysis.",
        },
        BEGIN_ANALYSIS_KEY,
    )
    analysis = assert_review_workspace(
        begun,
        project_id,
        round_id,
        state="analysis",
        round_version=4,
        policies=1,
        comparisons=0,
        references=0,
        conclusions=0,
    )
    require(
        all(
            analysis["permissions"].get(key) is True
            for key in (
                "createComparison",
                "manageReviewReferences",
                "submitConclusion",
            )
        ),
        "P7-04 analysis permissions drifted",
    )
    comparison_payload = {
        **review_policy_context(policy, analysis["trialRound"]),
        "rounds": [
            {
                "trialRoundGlobalId": primary["round"]["globalId"],
                "expectedOptimisticVersion": primary["round"]["optimisticVersion"],
                "expectedSnapshotHash": primary["round"]["snapshotHash"],
            },
            {
                "trialRoundGlobalId": analysis["trialRound"]["globalId"],
                "expectedOptimisticVersion": analysis["trialRound"]["optimisticVersion"],
                "expectedSnapshotHash": analysis["trialRound"]["snapshotHash"],
            },
        ],
        "reason": "Seal the exact chronological T0 to T1 comparison.",
    }
    compared = command(
        reviewer,
        base_url,
        reviewer_csrf,
        review_path(project_id, round_id, "/comparisons"),
        comparison_payload,
        COMPARISON_KEY,
    )
    compared_body = assert_review_workspace(
        compared,
        project_id,
        round_id,
        state="analysis",
        round_version=4,
        policies=1,
        comparisons=1,
        references=0,
        conclusions=0,
    )
    comparison = exact_single(
        compared_body["comparisonSnapshots"],
        "P7-04 comparison",
    )
    require(
        [value.get("trialRoundGlobalId") for value in comparison.get("sources", [])]
        == [primary["round"]["globalId"], round_id]
        and comparison.get("formalErpQuality") == "unavailable",
        "P7-04 chronological comparison or unavailable source truth drifted",
    )
    stale_payload = dict(comparison_payload)
    stale_payload["expectedRoundOptimisticVersion"] = 3
    stale = trial_request(
        reviewer,
        base_url,
        review_path(project_id, round_id, "/comparisons"),
        method="POST",
        payload=stale_payload,
        csrf_token=reviewer_csrf,
        idempotency_key=STALE_COMPARISON_KEY,
    )
    validate_problem(stale, 409, "TRIAL_REVIEW_CONFLICT")
    conflicting_payload = dict(comparison_payload)
    conflicting_payload["reason"] = "Conflicting comparison payload must be rejected."
    idempotency_conflict = trial_request(
        reviewer,
        base_url,
        review_path(project_id, round_id, "/comparisons"),
        method="POST",
        payload=conflicting_payload,
        csrf_token=reviewer_csrf,
        idempotency_key=COMPARISON_KEY,
    )
    validate_problem(idempotency_conflict, 409, "TRIAL_IDEMPOTENCY_CONFLICT")

    reference_context = fixture["referenceContext"]
    internal_created = command(
        reviewer,
        base_url,
        reviewer_csrf,
        review_path(project_id, round_id, "/review-references"),
        review_reference_payload(
            reference_context,
            policy,
            compared_body["trialRound"],
            comparison,
            kind="internal_sample_review",
        ),
        INTERNAL_REFERENCE_KEY,
    )
    internal_body = assert_review_workspace(
        internal_created,
        project_id,
        round_id,
        state="analysis",
        round_version=4,
        policies=1,
        comparisons=1,
        references=1,
        conclusions=0,
    )
    internal_reference = exact_single(
        internal_body["reviewReferenceRevisions"],
        "P7-04 internal review reference",
    )
    before_blocked = persisted_counts(administrator, base_url, project_id)
    blocked = trial_request(
        reviewer,
        base_url,
        review_path(project_id, round_id, "/conclusions"),
        method="POST",
        payload=conclusion_payload(
            policy,
            internal_body["trialRound"],
            comparison,
            [internal_reference],
        ),
        csrf_token=reviewer_csrf,
        idempotency_key=BLOCKED_CONCLUSION_KEY,
    )
    validate_problem(blocked, 422, "VALIDATION_FAILED")
    require(
        any(
            value.get("path") == "blockers"
            for value in blocked.body.get("fieldErrors", [])
        )
        and persisted_counts(administrator, base_url, project_id) == before_blocked,
        "P7-04 policy blocker did not fail closed with rollback",
    )
    controlled_created = command(
        reviewer,
        base_url,
        reviewer_csrf,
        review_path(project_id, round_id, "/review-references"),
        review_reference_payload(
            reference_context,
            policy,
            internal_body["trialRound"],
            comparison,
            kind="controlled_quality_report",
        ),
        CONTROLLED_REFERENCE_KEY,
    )
    controlled_v1 = exact_single(
        [
            value
            for value in controlled_created.body["reviewReferenceRevisions"]
            if value.get("referenceKind") == "controlled_quality_report"
        ],
        "P7-04 controlled reference v1",
    )
    controlled_revised = command(
        reviewer,
        base_url,
        reviewer_csrf,
        review_path(project_id, round_id, "/review-references"),
        review_reference_payload(
            reference_context,
            policy,
            controlled_created.body["trialRound"],
            comparison,
            kind="controlled_quality_report",
            predecessor=controlled_v1,
        ),
        CONTROLLED_REFERENCE_REVISE_KEY,
    )
    controlled_v2 = max(
        (
            value
            for value in controlled_revised.body["reviewReferenceRevisions"]
            if value.get("referenceGlobalId") == controlled_v1["referenceGlobalId"]
        ),
        key=lambda value: value["referenceVersion"],
    )
    require(
        controlled_v2.get("referenceVersion") == 2
        and controlled_v2.get("predecessorGlobalId") == controlled_v1["globalId"]
        and controlled_v2.get("predecessorSnapshotHash")
        == controlled_v1["snapshotHash"],
        "P7-04 immutable reference successor lineage drifted",
    )
    before_stale = persisted_counts(administrator, base_url, project_id)
    stale_reference = trial_request(
        reviewer,
        base_url,
        review_path(project_id, round_id, "/review-references"),
        method="POST",
        payload=review_reference_payload(
            reference_context,
            policy,
            controlled_revised.body["trialRound"],
            comparison,
            kind="controlled_quality_report",
            predecessor=controlled_v1,
        ),
        csrf_token=reviewer_csrf,
        idempotency_key=STALE_REFERENCE_REVISE_KEY,
    )
    validate_problem(stale_reference, 409, "TRIAL_REVIEW_CONFLICT")
    require(
        persisted_counts(administrator, base_url, project_id) == before_stale,
        "P7-04 stale reference fork changed immutable cardinality",
    )

    submitted = command(
        reviewer,
        base_url,
        reviewer_csrf,
        review_path(project_id, round_id, "/conclusions"),
        conclusion_payload(
            policy,
            controlled_revised.body["trialRound"],
            comparison,
            [internal_reference, controlled_v2],
        ),
        SUBMIT_CONCLUSION_KEY,
    )
    submitted_body = assert_review_workspace(
        submitted,
        project_id,
        round_id,
        state="submitted",
        round_version=5,
        policies=1,
        comparisons=1,
        references=3,
        conclusions=1,
    )
    conclusion_v1 = exact_single(
        submitted_body["conclusionRevisions"],
        "P7-04 conclusion v1",
    )
    require(
        conclusion_v1.get("blockers") == []
        and conclusion_v1.get("externalEffects") == EXPECTED_REVIEW_EXTERNAL_EFFECTS
        and submitted_body["permissions"].get("decideConclusion") is True,
        "P7-04 conclusion inputs or decision authority drifted",
    )
    approved = command(
        reviewer,
        base_url,
        reviewer_csrf,
        review_path(
            project_id,
            round_id,
            f"/conclusions/{conclusion_v1['conclusionGlobalId']}:decide",
        ),
        {
            **review_policy_context(policy, submitted_body["trialRound"]),
            "expectedConclusionRevisionGlobalId": conclusion_v1["globalId"],
            "expectedConclusionRevisionSnapshotHash": conclusion_v1["snapshotHash"],
            "expectedConclusionVersion": 1,
            "decision": "approved",
            "reason": "Approve the controlled Trial conclusion without external effect.",
        },
        APPROVE_CONCLUSION_KEY,
    )
    approved_tip = approved.body["conclusionRevisions"][-1]
    reopened = command(
        reviewer,
        base_url,
        reviewer_csrf,
        execution_path(project_id, round_id, ":reopen"),
        {
            **review_policy_context(policy, approved.body["trialRound"]),
            "conclusionGlobalId": approved_tip["conclusionGlobalId"],
            "expectedConclusionRevisionGlobalId": approved_tip["globalId"],
            "expectedConclusionRevisionSnapshotHash": approved_tip["snapshotHash"],
            "expectedConclusionVersion": 2,
            "reason": "Reopen the exact approved conclusion for controlled correction.",
        },
        REOPEN_CONCLUSION_KEY,
    )
    reopened_tip = reopened.body["conclusionRevisions"][-1]
    resubmitted = command(
        reviewer,
        base_url,
        reviewer_csrf,
        review_path(project_id, round_id, "/conclusions"),
        conclusion_payload(
            policy,
            reopened.body["trialRound"],
            comparison,
            [internal_reference, controlled_v2],
            predecessor=reopened_tip,
        ),
        RESUBMIT_CONCLUSION_KEY,
    )
    resubmitted_tip = resubmitted.body["conclusionRevisions"][-1]
    reject_payload = {
        **review_policy_context(policy, resubmitted.body["trialRound"]),
        "expectedConclusionRevisionGlobalId": resubmitted_tip["globalId"],
        "expectedConclusionRevisionSnapshotHash": resubmitted_tip["snapshotHash"],
        "expectedConclusionVersion": 4,
        "decision": "rejected",
        "reason": "Reject the corrected proposal without mutating external authorities.",
    }
    rejected = command(
        reviewer,
        base_url,
        reviewer_csrf,
        review_path(
            project_id,
            round_id,
            f"/conclusions/{resubmitted_tip['conclusionGlobalId']}:decide",
        ),
        reject_payload,
        REJECT_CONCLUSION_KEY,
    )
    final = assert_review_workspace(
        rejected,
        project_id,
        round_id,
        state="rejected",
        round_version=9,
        policies=1,
        comparisons=1,
        references=3,
        conclusions=5,
    )
    require(
        [value.get("state") for value in final["conclusionRevisions"]]
        == ["submitted", "approved", "reopened", "submitted", "rejected"]
        and [value.get("conclusionVersion") for value in final["conclusionRevisions"]]
        == [1, 2, 3, 4, 5],
        "P7-04 submit, approve, reopen, resubmit and reject history drifted",
    )
    same_process_replay = command(
        reviewer,
        base_url,
        reviewer_csrf,
        review_path(
            project_id,
            round_id,
            f"/conclusions/{resubmitted_tip['conclusionGlobalId']}:decide",
        ),
        reject_payload,
        REJECT_CONCLUSION_KEY,
    )
    require(
        same_process_replay.headers.get("Idempotency-Replayed") == "true"
        and same_process_replay.body == rejected.body,
        "P7-04 same-process conclusion replay changed sealed response truth",
    )
    return {
        "roundId": round_id,
        "policy": policy,
        "comparison": comparison,
        "finalConclusion": final["conclusionRevisions"][-1],
        "replayConclusion": resubmitted_tip,
        "rejectPayload": reject_payload,
    }


def run_fresh(
    administrator,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
) -> dict[str, object]:
    project_id, _version = document_runtime.fixture_project(administrator, base_url)
    master_id = fixture_master_id(administrator, base_url, project_id)
    schema = run_bench_fixture(
        "verify_trial_runtime_schema",
        {"fixture_run_id": FIXTURE_RUN_ID},
    )
    initial_counts = persisted_counts(administrator, base_url, project_id)
    require(
        all(initial_counts[doctype] == 0 for doctype in TRIAL_DOCTYPES),
        "P7-01 fresh Trial persistence was not empty",
    )
    integration_before = (initial_counts["outbox"], initial_counts["inbox"])
    empty = trial_request(
        administrator,
        base_url,
        trial_path(project_id),
        query_key="empty",
    )
    assert_workspace(empty, project_id, expected_plans=0)
    guest = trial_request(
        urllib.request.build_opener(),
        base_url,
        trial_path(project_id),
        query_key="guest",
    )
    validate_problem(guest, 401, "AUTHENTICATION_REQUIRED")

    first_payload = create_payload(master_id)
    created = command(
        administrator,
        base_url,
        csrf_token,
        trial_path(project_id),
        first_payload,
        CREATE_KEY,
    )
    require(
        created.headers.get("Idempotency-Replayed") == "false",
        "P7-01 first Plan was unexpectedly replayed",
    )
    created_detail = assert_detail(
        created,
        project_id,
        revisions=1,
        rounds=0,
        links=0,
    )
    plan_id = require_uuid(created_detail["planGlobalId"], "Plan")
    initial = exact_single(created_detail["revisions"], "initial Plan revision")
    initial_id = require_uuid(initial.get("globalId"), "initial revision")
    require(initial_id != plan_id, "P7-01 Plan and revision identities collapsed")
    replay = command(
        administrator,
        base_url,
        csrf_token,
        trial_path(project_id),
        first_payload,
        CREATE_KEY,
    )
    require(
        replay.headers.get("Idempotency-Replayed") == "true"
        and replay.body == created.body,
        "P7-01 same-process Plan replay changed sealed response truth",
    )
    conflicting_payload = dict(first_payload)
    conflicting_payload["objective"] = "Different synthetic intent"
    create_conflict = trial_request(
        administrator,
        base_url,
        trial_path(project_id),
        method="POST",
        payload=conflicting_payload,
        csrf_token=csrf_token,
        idempotency_key=CREATE_KEY,
    )
    validate_problem(create_conflict, 409, "TRIAL_IDEMPOTENCY_CONFLICT")

    successor_payload = revise_payload(initial)
    revised = command(
        administrator,
        base_url,
        csrf_token,
        plan_path(project_id, plan_id, "/revisions"),
        successor_payload,
        REVISE_KEY,
    )
    revised_detail = assert_detail(
        revised,
        project_id,
        plan_id=plan_id,
        revisions=2,
        rounds=0,
        links=0,
    )
    successor = revised_detail["latestRevision"]
    successor_id = require_uuid(successor.get("globalId"), "successor revision")
    require(
        successor.get("planVersion") == 2
        and successor.get("predecessorGlobalId") == initial_id
        and successor.get("predecessorSnapshotHash") == initial.get("snapshotHash")
        and successor_id not in {plan_id, initial_id},
        "P7-01 immutable successor lineage drifted",
    )
    stale_payload = dict(successor_payload)
    stale_payload["objective"] = "Rejected stale synthetic successor"
    stale = trial_request(
        administrator,
        base_url,
        plan_path(project_id, plan_id, "/revisions"),
        method="POST",
        payload=stale_payload,
        csrf_token=csrf_token,
        idempotency_key=STALE_REVISE_KEY,
    )
    validate_problem(stale, 409, "TRIAL_VERSION_CONFLICT")
    after_stale = trial_request(
        administrator,
        base_url,
        plan_path(project_id, plan_id),
        query_key="after-stale",
    )
    assert_detail(
        after_stale,
        project_id,
        plan_id=plan_id,
        revisions=2,
        rounds=0,
        links=0,
    )

    planned_round = command(
        administrator,
        base_url,
        csrf_token,
        plan_path(project_id, plan_id, "/rounds"),
        round_payload(successor),
        ROUND_KEY,
    )
    round_detail = assert_detail(
        planned_round,
        project_id,
        plan_id=plan_id,
        revisions=2,
        rounds=1,
        links=0,
    )
    round_value = exact_single(round_detail["rounds"], "planned Round")
    round_id = require_uuid(round_value.get("globalId"), "Round")
    require(
        round_id not in {plan_id, initial_id, successor_id}
        and round_value.get("trialPlanRevisionGlobalId") == successor_id
        and round_value.get("trialPlanRevisionSnapshotHash")
        == successor.get("snapshotHash")
        and round_value.get("roundSequence") == 0
        and round_value.get("displayLabel") == "T0"
        and round_value.get("currentState") == "planned"
        and round_value.get("optimisticVersion") == 1,
        "P7-01 distinct planned Round truth drifted",
    )
    duplicate_label = trial_request(
        administrator,
        base_url,
        plan_path(project_id, plan_id, "/rounds"),
        method="POST",
        payload=round_payload(successor),
        csrf_token=csrf_token,
        idempotency_key=ROUND_CONFLICT_KEY,
    )
    validate_problem(duplicate_label, 409, "TRIAL_LABEL_CONFLICT")

    generated = command(
        administrator,
        base_url,
        csrf_token,
        plan_path(project_id, plan_id, "/actions:generate"),
        action_payload(successor, round_id),
        ACTION_KEY,
    )
    final_detail = assert_detail(
        generated,
        project_id,
        plan_id=plan_id,
        revisions=2,
        rounds=1,
        links=1,
    )
    link = exact_single(final_detail["actionLinks"], "Trial Work link")
    require(
        link.get("trialPlanRevisionGlobalId") == successor_id
        and link.get("trialPlanRevisionSnapshotHash") == successor.get("snapshotHash")
        and link.get("trialRoundGlobalId") == round_id
        and require_uuid(link.get("domainWorkItemGlobalId"), "Domain Work Item")
        != round_id,
        "P7-01 governed Domain Work link drifted",
    )
    action_replay = command(
        administrator,
        base_url,
        csrf_token,
        plan_path(project_id, plan_id, "/actions:generate"),
        action_payload(successor, round_id),
        ACTION_KEY,
    )
    require(
        action_replay.headers.get("Idempotency-Replayed") == "true"
        and action_replay.body == generated.body,
        "P7-01 same-process action replay changed sealed response truth",
    )

    workspace = trial_request(
        administrator,
        base_url,
        trial_path(project_id),
        query_key="retained",
    )
    retained = assert_workspace(workspace, project_id, expected_plans=1)
    summary = exact_single(retained["plans"], "Plan summary")
    require(
        summary.get("planGlobalId") == plan_id
        and summary.get("roundCount") == 1
        and summary.get("actionCount") == 1
        and summary.get("latestRevision", {}).get("globalId") == successor_id,
        "P7-01 retained workspace summary drifted",
    )
    execution = run_execution_fresh(
        administrator,
        base_url,
        csrf_token,
        project_id=project_id,
        round_id=round_id,
    )
    primary_quality_context = {
        "round": execution["round"],
        "inputLock": execution["inputLock"],
        "sample": execution["sample"],
        "evidence": execution["evidence"],
        "cavityId": execution["cavityIds"][0],
    }
    target_execution = run_target_execution_fresh(
        administrator,
        base_url,
        csrf_token,
        project_id=project_id,
        plan_id=plan_id,
        plan_successor=successor,
        source_input_lock=execution["inputLock"],
    )
    quality = run_quality_fresh(
        administrator,
        base_url,
        csrf_token,
        fixture_password,
        project_id=project_id,
        primary=primary_quality_context,
        target=target_execution,
    )
    review = run_review_fresh(
        administrator,
        base_url,
        csrf_token,
        fixture_password,
        project_id=project_id,
        plan_id=plan_id,
        plan_revision=successor,
        primary=primary_quality_context,
        target=target_execution,
    )
    verify_idor(
        administrator,
        base_url,
        csrf_token,
        fixture_password,
        project_id,
        plan_id,
        round_id,
        review["roundId"],
    )
    verify_generic_mutation_denial(
        administrator,
        base_url,
        csrf_token,
        project_id,
    )
    final_counts = persisted_counts(administrator, base_url, project_id)
    require(
        final_counts["NPI Trial Plan Revision"] == 2
        and final_counts["NPI Trial Round"] == 2
        and final_counts["NPI Trial Round Lifecycle Event"] == 12
        and final_counts["NPI Trial Plan Work Link"] == 1
        and final_counts["NPI Trial Command Idempotency"] == 39
        and final_counts["NPI Trial Input Lock Revision"] == 2
        and final_counts["NPI Trial Actual Revision"] == 3
        and final_counts["NPI Trial Sample Batch Revision"] == 3
        and final_counts["NPI Trial Evidence Reference"] == 2
        and final_counts["NPI Trial Cavity Result Revision"] == 2
        and final_counts["NPI Trial Defect Revision"] == 8
        and final_counts["NPI Trial Defect Verification Revision"] == 2
        and final_counts["NPI Trial Conclusion Policy Version"] == 1
        and final_counts["NPI Trial Round Comparison Snapshot"] == 1
        and final_counts["NPI Trial Review Reference Revision"] == 3
        and final_counts["NPI Trial Conclusion Revision"] == 5
        and all(
            final_counts[f"audit:{operation}"] == expected
            for operation, expected in {
                "trial_plan.create": 1,
                "trial_plan.revise": 1,
                "trial_round.create": 2,
                "trial_plan.generate_actions": 1,
                "trial_round.prepare": 2,
                "trial_round.start": 2,
                "trial_actual.append": 1,
                "trial_sample.create": 2,
                "trial_sample.revise": 1,
                "trial_file.upload": 2,
                "trial_evidence.bind": 2,
                "trial_evidence.content.read": 1,
                "trial_cavity_result.create": 1,
                "trial_cavity_result.revise": 1,
                "trial_defect.create": 2,
                "trial_defect.revise": 6,
                "trial_defect.verify": 2,
                "trial_round.begin_analysis": 1,
                "trial_comparison.create": 1,
                "trial_review_reference.create": 2,
                "trial_review_reference.revise": 1,
                "trial_conclusion.submit": 2,
                "trial_conclusion.decide": 2,
                "trial_conclusion.reopen": 1,
            }.items()
        ),
        "P7-04 cumulative controlled persistence cardinality drifted",
    )
    require(
        (final_counts["outbox"], final_counts["inbox"]) == integration_before,
        # Preserved predecessor evidence: "P7-03 controlled Trial quality created ERP integration traffic"
        "P7-04 controlled Trial review created ERP integration traffic",
    )
    return {
        "actionLinkCount": 1,
        "crossProcessReplayReady": True,
        "doctypeCount": schema["doctypeCount"],
        "evidenceReferenceCount": 2,
        "fixtureRunId": FIXTURE_RUN_ID,
        "inputLockRevisionCount": 2,
        "integrationTrafficCreated": False,
        "metadataSynchronized": schema["metadataSynchronized"],
        "planRevisionCount": 2,
        "plannedRoundCount": 2,
        "roundState": "rejected",
        "sampleBatchRevisionCount": 3,
        "trialActualRevisionCount": 3,
        "cavityResultRevisionCount": 2,
        "trialDefectRevisionCount": 8,
        "verificationRevisionCount": 2,
        "comparisonSnapshotCount": 1,
        "reviewReferenceRevisionCount": 3,
        "conclusionRevisionCount": 5,
        "reviewRoundId": review["roundId"],
        "crossRoundDefectRevisionId": quality["crossRoundRevisionId"],
        "verifiedEvidenceId": execution["evidenceId"],
        "automaticMachineAcquisition": "unavailable",
        "erpQualityAuthority": "unavailable",
        "gateAndApprovalAuthority": "unavailable",
        "customerSignatureAuthority": "unavailable",
        "npiReadinessAuthority": "unavailable",
        "nextWorkEffect": "proposal_only",
        "resourceReservation": "unavailable",
        "rollbackVerified": True,
    }


def retained_detail(administrator, base_url: str) -> tuple[str, str, dict[str, Any]]:
    project_id, _version = document_runtime.fixture_project(administrator, base_url)
    plans = tooling_runtime.rows(
        administrator,
        base_url,
        "NPI Trial Plan Revision",
        [["project_global_id", "=", project_id]],
        ["plan_global_id", "plan_version"],
    )
    plan_ids = sorted({str(value["plan_global_id"]) for value in plans})
    require(len(plan_ids) == 1, "P7-01 retained Plan identity is unavailable")
    plan_id = require_uuid(plan_ids[0], "retained Plan")
    detail_result = trial_request(
        administrator,
        base_url,
        plan_path(project_id, plan_id),
        query_key="replay-detail",
    )
    detail = assert_detail(
        detail_result,
        project_id,
        plan_id=plan_id,
        revisions=2,
        rounds=2,
        links=1,
    )
    return project_id, plan_id, detail


def run_review_replay(
    reviewer,
    base_url: str,
    reviewer_csrf: str,
    *,
    project_id: str,
    round_id: str,
) -> None:
    review = assert_review_workspace(
        trial_request(
            reviewer,
            base_url,
            review_path(project_id, round_id),
            query_key="review-replay-context",
        ),
        project_id,
        round_id,
        state="rejected",
        round_version=9,
        policies=1,
        comparisons=1,
        references=3,
        conclusions=5,
    )
    policy = exact_single(review["policyVersions"], "P7-04 replay policy")
    submitted = review["conclusionRevisions"][-2]
    rejected = review["conclusionRevisions"][-1]
    payload = {
        "policyRevisionGlobalId": policy["globalId"],
        "expectedPolicyRevisionSnapshotHash": policy["snapshotHash"],
        "expectedRoundOptimisticVersion": submitted["trialRoundOptimisticVersion"],
        "expectedRoundSnapshotHash": submitted["trialRoundSnapshotHash"],
        "expectedConclusionRevisionGlobalId": submitted["globalId"],
        "expectedConclusionRevisionSnapshotHash": submitted["snapshotHash"],
        "expectedConclusionVersion": submitted["conclusionVersion"],
        "decision": "rejected",
        "reason": rejected["reason"],
    }
    before = persisted_counts(reviewer, base_url, project_id)
    replay = command(
        reviewer,
        base_url,
        reviewer_csrf,
        review_path(
            project_id,
            round_id,
            f"/conclusions/{submitted['conclusionGlobalId']}:decide",
        ),
        payload,
        REJECT_CONCLUSION_KEY,
    )
    require(
        replay.headers.get("Idempotency-Replayed") == "true"
        and replay.body == review
        and persisted_counts(reviewer, base_url, project_id) == before,
        "P7-04 cross-process review replay changed sealed truth or cardinality",
    )


def run_replay(
    administrator,
    base_url: str,
    csrf_token: str,
    reviewer,
    reviewer_csrf: str,
) -> None:
    project_id, plan_id, detail = retained_detail(administrator, base_url)
    master_id = str(detail["latestRevision"]["toolingMasterGlobalId"])
    initial, successor = detail["revisions"]
    primary_round = exact_single(
        [value for value in detail["rounds"] if value.get("displayLabel") == "T0"],
        "replay primary Round",
    )
    target_round = exact_single(
        [value for value in detail["rounds"] if value.get("displayLabel") == "T1"],
        "replay target Round",
    )
    round_id = str(primary_round["globalId"])
    target_round_id = str(target_round["globalId"])
    cases = (
        (trial_path(project_id), create_payload(master_id), CREATE_KEY, 1, 0, 0),
        (
            plan_path(project_id, plan_id, "/revisions"),
            revise_payload(initial),
            REVISE_KEY,
            2,
            0,
            0,
        ),
        (
            plan_path(project_id, plan_id, "/rounds"),
            round_payload(successor),
            ROUND_KEY,
            2,
            1,
            0,
        ),
        (
            plan_path(project_id, plan_id, "/rounds"),
            round_payload(successor, display_label="T1"),
            TARGET_ROUND_KEY,
            2,
            2,
            1,
        ),
        (
            plan_path(project_id, plan_id, "/actions:generate"),
            action_payload(successor, round_id),
            ACTION_KEY,
            2,
            1,
            1,
        ),
    )
    before = persisted_counts(administrator, base_url, project_id)
    for path, payload, key, revisions, rounds, links in cases:
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
            "P7-01 cross-process command was not replayed",
        )
        assert_detail(
            replay,
            project_id,
            plan_id=plan_id,
            revisions=revisions,
            rounds=rounds,
            links=links,
        )
    execution_result = trial_request(
        administrator,
        base_url,
        execution_path(project_id, round_id),
        query_key="replay-execution",
    )
    execution = assert_execution_workspace(
        execution_result,
        project_id,
        round_id,
        state="running",
        round_version=3,
        locks=1,
        actuals=2,
        samples=2,
        evidence=1,
        pending=0,
    )
    input_lock = exact_single(execution["inputLocks"], "replay input lock")
    first_actual, _actual_successor = execution["actualRevisions"]
    first_sample, sample_successor = execution["sampleBatchRevisions"]
    evidence = exact_single(execution["evidence"], "replay evidence")
    cavity_ids = [
        value["globalId"]
        for value in input_lock["references"]
        if value.get("kind") == "cavity"
    ]
    execution_cases = (
        (
            execution_path(project_id, round_id, ":prepare"),
            prepare_execution_payload(replay_references(input_lock)),
            PREPARE_KEY,
        ),
        (
            execution_path(project_id, round_id, ":start"),
            {
                "expectedRoundOptimisticVersion": 2,
                "expectedInputLockRevisionGlobalId": input_lock["globalId"],
                "expectedInputLockVersion": 1,
                **actual_context_payload(successor=False),
            },
            START_KEY,
        ),
        (
            execution_path(project_id, round_id, "/actual-revisions"),
            {
                "expectedRoundOptimisticVersion": 3,
                "expectedActualRevisionGlobalId": first_actual["globalId"],
                "expectedActualVersion": 1,
                **actual_context_payload(successor=True),
            },
            ACTUAL_KEY,
        ),
        (
            execution_path(project_id, round_id, "/sample-batches"),
            {
                "expectedRoundOptimisticVersion": 3,
                "expectedInputLockRevisionGlobalId": input_lock["globalId"],
                "sample": sample_payload(cavity_ids, successor=False),
                "reason": "Create one exact controlled Sample Batch.",
            },
            SAMPLE_KEY,
        ),
        (
            sample_path(project_id, round_id, first_sample["sampleBatchGlobalId"]),
            {
                "expectedRoundOptimisticVersion": 3,
                "expectedRevisionGlobalId": first_sample["globalId"],
                "expectedSampleVersion": 1,
                "sample": sample_payload(cavity_ids, successor=True),
                "reason": "Append the exact controlled Sample packaging correction.",
            },
            SAMPLE_REVISE_KEY,
        ),
        (
            execution_path(project_id, round_id, "/evidence"),
            {
                "expectedRoundOptimisticVersion": 3,
                "role": "measurement_report",
                "fileRevisionGlobalId": evidence["fileRevisionGlobalId"],
                "expectedFileOptimisticVersion": 2,
                "sampleBatchRevisionGlobalId": sample_successor["globalId"],
                "expectedSampleVersion": 2,
            },
            BIND_KEY,
        ),
    )
    for path, payload, key in execution_cases:
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
            "P7-02 cross-process execution command was not replayed",
        )
    upload_replay = multipart_trial_upload(
        administrator,
        base_url,
        execution_path(project_id, round_id, "/files"),
        csrf_token=csrf_token,
        idempotency_key=UPLOAD_KEY,
        round_version=3,
    )
    require(
        upload_replay.status == 201
        and upload_replay.headers.get("Idempotency-Replayed") == "true",
        "P7-02 cross-process upload command was not replayed",
    )
    target_execution_result = trial_request(
        administrator,
        base_url,
        execution_path(project_id, target_round_id),
        query_key="replay-target-execution",
    )
    target_execution = assert_execution_workspace(
        target_execution_result,
        project_id,
        target_round_id,
        state="rejected",
        round_version=9,
        locks=1,
        actuals=1,
        samples=1,
        evidence=1,
        pending=0,
    )
    target_input_lock = exact_single(
        target_execution["inputLocks"],
        "P7-03 replay target input lock",
    )
    target_actual = exact_single(
        target_execution["actualRevisions"],
        "P7-03 replay target Actual",
    )
    target_sample = exact_single(
        target_execution["sampleBatchRevisions"],
        "P7-03 replay target Sample",
    )
    target_evidence = exact_single(
        target_execution["evidence"],
        "P7-03 replay target evidence",
    )
    target_cavity_ids = [
        value["globalId"]
        for value in target_input_lock["references"]
        if value.get("kind") == "cavity"
    ]
    target_cases = (
        (
            execution_path(project_id, target_round_id, ":prepare"),
            prepare_execution_payload(replay_references(target_input_lock)),
            TARGET_PREPARE_KEY,
        ),
        (
            execution_path(project_id, target_round_id, ":start"),
            {
                "expectedRoundOptimisticVersion": 2,
                "expectedInputLockRevisionGlobalId": target_input_lock["globalId"],
                "expectedInputLockVersion": 1,
                **actual_context_payload(successor=False),
            },
            TARGET_START_KEY,
        ),
        (
            execution_path(project_id, target_round_id, "/sample-batches"),
            {
                "expectedRoundOptimisticVersion": 3,
                "expectedInputLockRevisionGlobalId": target_input_lock["globalId"],
                "sample": sample_payload(
                    target_cavity_ids,
                    successor=False,
                    label_prefix="P703",
                ),
                "reason": "Create one exact target-Round Sample Batch.",
            },
            TARGET_SAMPLE_KEY,
        ),
        (
            execution_path(project_id, target_round_id, "/evidence"),
            {
                "expectedRoundOptimisticVersion": 3,
                "role": "measurement_report",
                "fileRevisionGlobalId": target_evidence["fileRevisionGlobalId"],
                "expectedFileOptimisticVersion": 2,
                "sampleBatchRevisionGlobalId": target_sample["globalId"],
                "expectedSampleVersion": 1,
            },
            TARGET_BIND_KEY,
        ),
    )
    for path, payload, key in target_cases:
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
            "P7-03 target-Round command was not replayed",
        )
    target_upload_replay = multipart_trial_upload(
        administrator,
        base_url,
        execution_path(project_id, target_round_id, "/files"),
        csrf_token=csrf_token,
        idempotency_key=TARGET_UPLOAD_KEY,
        round_version=3,
    )
    require(
        target_upload_replay.status == 201
        and target_upload_replay.headers.get("Idempotency-Replayed") == "true",
        "P7-03 target-Round upload command was not replayed",
    )
    primary_context = {
        "round": execution["round"],
        "inputLock": input_lock,
        "sample": sample_successor,
        "evidence": evidence,
        "cavityId": cavity_ids[0],
    }
    historical_target = run_bench_fixture(
        "historical_trial_round_context",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "round_id": target_round_id,
            "event_version": 3,
        },
    )
    target_context = {
        "round": historical_target,
        "inputLock": target_input_lock,
        "sample": target_sample,
        "evidence": target_evidence,
        "cavityId": target_cavity_ids[0],
    }
    require(
        target_actual.get("actualVersion") == 1,
        "P7-03 target-Round retained Actual drifted",
    )
    run_quality_replay(
        administrator,
        base_url,
        csrf_token,
        project_id=project_id,
        primary=primary_context,
        target=target_context,
    )
    run_review_replay(
        reviewer,
        base_url,
        reviewer_csrf,
        project_id=project_id,
        round_id=target_round_id,
    )
    after = persisted_counts(administrator, base_url, project_id)
    require(
        after == before,
        # Preserved predecessor evidence: "P7-03 cumulative cross-process replay changed immutable cardinality or integration truth"
        "P7-04 cumulative cross-process replay changed immutable cardinality or integration truth",
    )


def route_disable_probe(administrator, base_url: str, *, expected_mode: str) -> None:
    project_id, _version = document_runtime.fixture_project(administrator, base_url)
    rounds = tooling_runtime.rows(
        administrator,
        base_url,
        "NPI Trial Round",
        [["project_global_id", "=", project_id]],
        ["global_id", "display_label"],
    )
    selected_round = exact_single(
        [value for value in rounds if value.get("display_label") == "T0"],
        "route probe Round",
    )
    round_id = require_uuid(selected_round["global_id"], "Round")
    review_round = exact_single(
        [value for value in rounds if value.get("display_label") == "T1"],
        "review route probe Round",
    )
    review_round_id = require_uuid(review_round["global_id"], "review Round")
    trials = trial_request(
        administrator,
        base_url,
        trial_path(project_id),
        query_key=f"route-{expected_mode}",
    )
    predecessor = tooling_runtime.tooling_request(
        administrator,
        base_url,
        tooling_runtime.tooling_path(project_id),
        query_key=f"p701-predecessor-{expected_mode}",
    )
    require(
        predecessor.status == 200 and bool(predecessor.body.get("masters")),
        "P7-01 route switch changed predecessor Tooling availability",
    )
    execution = trial_request(
        administrator,
        base_url,
        execution_path(project_id, round_id),
        query_key=f"execution-route-{expected_mode}",
    )
    quality = trial_request(
        administrator,
        base_url,
        quality_path(project_id, round_id),
        query_key=f"quality-route-{expected_mode}",
    )
    review = trial_request(
        administrator,
        base_url,
        review_path(project_id, review_round_id),
        query_key=f"review-route-{expected_mode}",
    )
    if expected_mode == "planning-disabled":
        validate_problem(trials, 503, "TRIAL_ROUTES_DISABLED")
        assert_execution_workspace(
            execution,
            project_id,
            round_id,
            state="running",
            round_version=3,
            locks=1,
            actuals=2,
            samples=2,
            evidence=1,
            pending=0,
        )
        assert_quality_workspace(
            quality,
            project_id,
            round_id,
            cavity_results=2,
            trial_defects=8,
            tooling_defects=2,
            verifications=2,
        )
        assert_review_workspace(
            review,
            project_id,
            review_round_id,
            state="rejected",
            round_version=9,
            policies=1,
            comparisons=1,
            references=3,
            conclusions=5,
        )
        return
    if expected_mode == "execution-disabled":
        assert_workspace(trials, project_id, expected_plans=1)
        validate_problem(execution, 503, "TRIAL_EXECUTION_ROUTES_DISABLED")
        assert_quality_workspace(
            quality,
            project_id,
            round_id,
            cavity_results=2,
            trial_defects=8,
            tooling_defects=2,
            verifications=2,
        )
        assert_review_workspace(
            review,
            project_id,
            review_round_id,
            state="rejected",
            round_version=9,
            policies=1,
            comparisons=1,
            references=3,
            conclusions=5,
        )
        return
    if expected_mode == "quality-disabled":
        assert_workspace(trials, project_id, expected_plans=1)
        assert_execution_workspace(
            execution,
            project_id,
            round_id,
            state="running",
            round_version=3,
            locks=1,
            actuals=2,
            samples=2,
            evidence=1,
            pending=0,
        )
        validate_problem(quality, 503, "TRIAL_QUALITY_ROUTES_DISABLED")
        assert_review_workspace(
            review,
            project_id,
            review_round_id,
            state="rejected",
            round_version=9,
            policies=1,
            comparisons=1,
            references=3,
            conclusions=5,
        )
        return
    if expected_mode == "review-disabled":
        assert_workspace(trials, project_id, expected_plans=1)
        assert_execution_workspace(
            execution,
            project_id,
            round_id,
            state="running",
            round_version=3,
            locks=1,
            actuals=2,
            samples=2,
            evidence=1,
            pending=0,
        )
        assert_quality_workspace(
            quality,
            project_id,
            round_id,
            cavity_results=2,
            trial_defects=8,
            tooling_defects=2,
            verifications=2,
        )
        validate_problem(review, 503, "TRIAL_REVIEW_ROUTES_DISABLED")
        return
    require(
        expected_mode
        in {
            "planning-recovered",
            "execution-recovered",
            "quality-recovered",
            "review-recovered",
        },
        "P7 cumulative route probe mode drifted",
    )
    assert_workspace(trials, project_id, expected_plans=1)
    assert_execution_workspace(
        execution,
        project_id,
        round_id,
        state="running",
        round_version=3,
        locks=1,
        actuals=2,
        samples=2,
        evidence=1,
        pending=0,
    )
    assert_quality_workspace(
        quality,
        project_id,
        round_id,
        cavity_results=2,
        trial_defects=8,
        tooling_defects=2,
        verifications=2,
    )
    assert_review_workspace(
        review,
        project_id,
        review_round_id,
        state="rejected",
        round_version=9,
        policies=1,
        comparisons=1,
        references=3,
        conclusions=5,
    )


def verify_trial_runtime_schema(fixture_run_id: str) -> dict[str, object]:
    import frappe

    document_runtime._validated_runtime_site()
    require(fixture_run_id == FIXTURE_RUN_ID, "P7-01 schema fixture namespace drifted")
    required_fields = {
        "NPI Trial Plan Revision": {
            "global_id",
            "plan_global_id",
            "plan_version",
            "predecessor_global_id",
            "plan_snapshot",
            "snapshot_hash",
        },
        "NPI Trial Round": {
            "global_id",
            "trial_plan_global_id",
            "trial_plan_revision_global_id",
            "round_sequence",
            "current_state",
            "round_snapshot",
            "snapshot_hash",
        },
        "NPI Trial Round Lifecycle Event": {
            "global_id",
            "trial_round_global_id",
            "event_version",
            "event_type",
            "event_snapshot",
            "snapshot_hash",
        },
        "NPI Trial Plan Work Link": {
            "global_id",
            "trial_plan_global_id",
            "domain_work_item_global_id",
            "link_snapshot",
            "snapshot_hash",
        },
        "NPI Trial Command Idempotency": {
            "global_id",
            "receipt_key",
            "operation",
            "idempotency_key_hash",
            "payload_hash",
            "response_hash",
            "sealed",
        },
        "NPI Trial Input Lock Revision": {
            "global_id",
            "input_lock_global_id",
            "lock_version",
            "reference_snapshot",
            "lock_snapshot",
            "snapshot_hash",
        },
        "NPI Trial Actual Revision": {
            "global_id",
            "actual_global_id",
            "actual_version",
            "predecessor_global_id",
            "actual_snapshot",
            "snapshot_hash",
        },
        "NPI Trial Sample Batch Revision": {
            "global_id",
            "sample_batch_global_id",
            "sample_version",
            "predecessor_global_id",
            "sample_snapshot",
            "snapshot_hash",
        },
        "NPI Trial Evidence Reference": {
            "global_id",
            "trial_round_global_id",
            "file_revision_global_id",
            "evidence_snapshot",
            "snapshot_hash",
        },
        "NPI Trial Cavity Result Revision": {
            "global_id",
            "cavity_result_global_id",
            "result_version",
            "predecessor_global_id",
            "cavity_result_snapshot",
            "snapshot_hash",
        },
        "NPI Trial Defect Revision": {
            "global_id",
            "defect_global_id",
            "defect_version",
            "predecessor_global_id",
            "trial_defect_snapshot",
            "snapshot_hash",
        },
        "NPI Trial Defect Verification Revision": {
            "global_id",
            "verification_global_id",
            "attempt_sequence",
            "defect_global_id",
            "verification_snapshot",
            "snapshot_hash",
        },
        "NPI Trial Conclusion Policy Version": {
            "global_id",
            "policy_global_id",
            "policy_version",
            "trial_plan_revision_global_id",
            "policy_snapshot",
            "snapshot_hash",
        },
        "NPI Trial Round Comparison Snapshot": {
            "global_id",
            "target_round_global_id",
            "policy_revision_global_id",
            "comparison_snapshot",
            "snapshot_hash",
        },
        "NPI Trial Review Reference Revision": {
            "global_id",
            "reference_global_id",
            "reference_version",
            "predecessor_global_id",
            "reference_snapshot",
            "snapshot_hash",
        },
        "NPI Trial Conclusion Revision": {
            "global_id",
            "conclusion_global_id",
            "conclusion_version",
            "predecessor_global_id",
            "conclusion_snapshot",
            "snapshot_hash",
        },
    }
    for doctype in TRIAL_DOCTYPES:
        require(
            frappe.db.table_exists(doctype),
            f"P7-02 table is unavailable: {doctype}",
        )
        fields = {
            field.fieldname
            for field in frappe.get_meta(doctype, cached=False).fields
        }
        require(
            required_fields[doctype] <= fields,
            f"P7-02 metadata is incomplete for {doctype}",
        )
    return {
        "doctypeCount": len(TRIAL_DOCTYPES),
        "fixtureRunId": fixture_run_id,
        "metadataSynchronized": True,
        "runtimeMarker": RUNTIME_MARKER,
    }


def ensure_trial_quality_verifier_member(
    fixture_run_id: str,
    *,
    project_id: str,
) -> dict[str, object]:
    import frappe

    document_runtime._validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "P7-03 verifier-member fixture namespace drifted",
    )
    project = frappe.get_doc("NPI Engineering Project", project_id)
    require(
        str(project.global_id) == project_id
        and str(project.tenant_id) == TENANT_ID,
        "P7-03 verifier-member Project identity drifted",
    )
    existing = frappe.db.exists("NPI Project Member", VERIFIER_MEMBER_ID)
    if not existing:
        previous = getattr(frappe.flags, "npi_project_work_command_write", None)
        setattr(frappe.flags, "npi_project_work_command_write", True)
        try:
            frappe.get_doc(
                {
                    "doctype": "NPI Project Member",
                    "global_id": VERIFIER_MEMBER_ID,
                    "tenant_id": TENANT_ID,
                    "project_global_id": project_id,
                    "user_id": VERIFIER_USER,
                    "effective_from": "2026-01-01",
                    "effective_to": None,
                    "optimistic_version": 1,
                }
            ).insert()
        finally:
            if previous is None:
                delattr(frappe.flags, "npi_project_work_command_write")
            else:
                setattr(frappe.flags, "npi_project_work_command_write", previous)
        frappe.db.commit()
    member = frappe.get_doc("NPI Project Member", VERIFIER_MEMBER_ID)
    require(
        str(member.project_global_id) == project_id
        and str(member.tenant_id) == TENANT_ID
        and str(member.user_id) == VERIFIER_USER
        and int(member.optimistic_version) == 1
        and VERIFIER_MEMBER_ID != RESPONSIBLE_MEMBER_ID,
        "P7-03 independent verifier member drifted",
    )
    return {
        "fixtureRunId": fixture_run_id,
        "globalId": VERIFIER_MEMBER_ID,
        "optimisticVersion": 1,
    }


def ensure_trial_review_policy(
    fixture_run_id: str,
    *,
    project_id: str,
    plan_id: str,
    plan_revision_id: str,
    plan_revision_snapshot_hash: str,
    round_id: str,
    input_lock_id: str,
    file_revision_id: str,
) -> dict[str, object]:
    import frappe

    from npi_core.documents.frappe_validation import canonical_json
    from npi_core.tooling.manufacturing_domain import ProjectMemberResponsibility
    from npi_core.trial.execution_repository import _file_revision_source_snapshot
    from npi_core.trial.frappe_validation import trial_command_write
    from npi_core.trial.review_domain import (
        TrialConclusionCapability,
        TrialConclusionCode,
        TrialConclusionPolicyVersion,
        TrialPolicyAuthorityBinding,
        TrialReviewReferenceKind,
    )
    from npi_core.trial.review_repository import _payload_hash

    document_runtime._validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "P7-04 review-policy fixture namespace drifted",
    )
    project = frappe.get_doc("NPI Engineering Project", project_id)
    trial_round = frappe.get_doc("NPI Trial Round", round_id)
    input_lock = frappe.get_doc("NPI Trial Input Lock Revision", input_lock_id)
    file_revision = frappe.get_doc("NPI File Revision", file_revision_id)
    require(
        str(project.global_id) == project_id
        and str(project.tenant_id) == TENANT_ID
        and str(trial_round.project_global_id) == project_id
        and str(trial_round.trial_plan_global_id) == plan_id
        and str(trial_round.trial_plan_revision_global_id) == plan_revision_id
        and str(trial_round.trial_plan_revision_snapshot_hash)
        == plan_revision_snapshot_hash
        and str(input_lock.project_global_id) == project_id
        and str(input_lock.trial_round_global_id) == round_id
        and str(file_revision.project_global_id) == project_id
        and str(file_revision.document_global_id) == round_id
        and str(file_revision.scan_state) == "clean",
        "P7-04 exact review-policy source context drifted",
    )
    if not frappe.db.exists("NPI Project Member", REVIEW_MEMBER_ID):
        previous = getattr(frappe.flags, "npi_project_work_command_write", None)
        setattr(frappe.flags, "npi_project_work_command_write", True)
        try:
            frappe.get_doc(
                {
                    "doctype": "NPI Project Member",
                    "global_id": REVIEW_MEMBER_ID,
                    "tenant_id": TENANT_ID,
                    "project_global_id": project_id,
                    "user_id": REVIEW_USER,
                    "effective_from": "2026-01-01",
                    "effective_to": None,
                    "optimistic_version": 1,
                }
            ).insert()
        finally:
            if previous is None:
                delattr(frappe.flags, "npi_project_work_command_write")
            else:
                setattr(frappe.flags, "npi_project_work_command_write", previous)
    member = frappe.get_doc("NPI Project Member", REVIEW_MEMBER_ID)
    require(
        str(member.project_global_id) == project_id
        and str(member.user_id) == REVIEW_USER
        and int(member.optimistic_version) == 1,
        "P7-04 review authority member drifted",
    )
    if not frappe.db.exists(
        "NPI Trial Conclusion Policy Version",
        REVIEW_POLICY_REVISION_ID,
    ):
        policy = TrialConclusionPolicyVersion(
            global_id=UUID(REVIEW_POLICY_REVISION_ID),
            policy_global_id=UUID(REVIEW_POLICY_ID),
            tenant_id=TENANT_ID,
            project_global_id=UUID(project_id),
            trial_plan_global_id=UUID(plan_id),
            trial_plan_revision_global_id=UUID(plan_revision_id),
            trial_plan_revision_snapshot_hash=plan_revision_snapshot_hash,
            policy_version=1,
            predecessor_global_id=None,
            predecessor_snapshot_hash=None,
            required_parameter_keys=(),
            required_dimension_keys=(),
            required_reference_kinds=(
                TrialReviewReferenceKind.CONTROLLED_QUALITY_REPORT,
            ),
            require_cavity_results=False,
            block_on_open_blocking_defects=False,
            block_on_unverified_required_actions=False,
            allowed_conclusion_codes=(
                TrialConclusionCode.CONDITIONAL_PASS,
                TrialConclusionCode.PROCESS_TUNING,
            ),
            out_of_spec_blocking_codes=(),
            authority_bindings=(
                TrialPolicyAuthorityBinding(
                    member=ProjectMemberResponsibility(
                        global_id=UUID(REVIEW_MEMBER_ID),
                        user_id=REVIEW_USER,
                        optimistic_version=1,
                    ),
                    capabilities=tuple(TrialConclusionCapability),
                ),
            ),
            published_by_user_id=REVIEW_USER,
            published_at=datetime.now(UTC),
            request_id=uuid4(),
            trace_id="trace-p704-runtime-policy",
        )
        payload = policy.snapshot_payload()
        with trial_command_write():
            frappe.get_doc(
                {
                    "doctype": "NPI Trial Conclusion Policy Version",
                    "global_id": str(policy.global_id),
                    "policy_global_id": str(policy.policy_global_id),
                    "version_key_hash": policy.version_key_hash,
                    "tenant_id": policy.tenant_id,
                    "project_global_id": str(policy.project_global_id),
                    "trial_plan_global_id": str(policy.trial_plan_global_id),
                    "trial_plan_revision": str(policy.trial_plan_revision_global_id),
                    "trial_plan_revision_global_id": str(
                        policy.trial_plan_revision_global_id
                    ),
                    "trial_plan_revision_snapshot_hash": (
                        policy.trial_plan_revision_snapshot_hash
                    ),
                    "policy_version": policy.policy_version,
                    "predecessor_global_id": None,
                    "predecessor_snapshot_hash": None,
                    "required_parameter_snapshot": canonical_json([]),
                    "required_dimension_snapshot": canonical_json([]),
                    "required_reference_kind_snapshot": canonical_json(
                        payload["requiredReferenceKinds"]
                    ),
                    "require_cavity_results": 0,
                    "block_on_open_blocking_defects": 0,
                    "block_on_unverified_required_actions": 0,
                    "allowed_conclusion_code_snapshot": canonical_json(
                        payload["allowedConclusionCodes"]
                    ),
                    "out_of_spec_blocking_code_snapshot": canonical_json([]),
                    "authority_binding_snapshot": canonical_json(
                        payload["authorityBindings"]
                    ),
                    "published_by_user_id": policy.published_by_user_id,
                    "published_at": policy.published_at,
                    "request_id": str(policy.request_id),
                    "trace_id": policy.trace_id,
                    "policy_snapshot": canonical_json(payload),
                    "snapshot_hash": policy.snapshot_hash,
                }
            ).insert()
    frappe.db.commit()
    policy_document = frappe.get_doc(
        "NPI Trial Conclusion Policy Version",
        REVIEW_POLICY_REVISION_ID,
    )
    reference_values = (
        json.loads(input_lock.reference_snapshot)
        if isinstance(input_lock.reference_snapshot, str)
        else input_lock.reference_snapshot
    )
    require(
        isinstance(reference_values, list),
        "P7-04 locked review reference source is invalid",
    )
    by_kind = {
        str(value.get("kind")): value
        for value in reference_values
        if isinstance(value, dict)
    }
    require(
        {"part_revision", "tooling_revision", "tooling_set"} <= set(by_kind),
        "P7-04 exact locked review references are unavailable",
    )
    file_source_hash = _payload_hash(_file_revision_source_snapshot(file_revision))
    return {
        "fixtureRunId": fixture_run_id,
        "policyGlobalId": str(policy_document.global_id),
        "policySnapshotHash": str(policy_document.snapshot_hash),
        "referenceContext": {
            "partRevisionGlobalId": by_kind["part_revision"]["globalId"],
            "partRevisionSnapshotHash": by_kind["part_revision"]["snapshotHash"],
            "toolingMasterGlobalId": str(trial_round.tooling_master_global_id),
            "toolingRevisionGlobalId": by_kind["tooling_revision"]["globalId"],
            "toolingRevisionSnapshotHash": by_kind["tooling_revision"][
                "snapshotHash"
            ],
            "toolingSetGlobalId": by_kind["tooling_set"]["globalId"],
            "toolingSetSnapshotHash": by_kind["tooling_set"]["snapshotHash"],
            "fileRevisionGlobalId": file_revision_id,
            "fileRevisionSnapshotHash": file_source_hash,
        },
    }


def historical_trial_round_context(
    fixture_run_id: str,
    *,
    project_id: str,
    round_id: str,
    event_version: int,
) -> dict[str, object]:
    import frappe

    from npi_core.trial.domain import trial_round_from_snapshot

    document_runtime._validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID and event_version == 3,
        "P7-04 historical Round fixture boundary drifted",
    )
    document = frappe.get_doc("NPI Trial Round", round_id)
    events = frappe.get_all(
        "NPI Trial Round Lifecycle Event",
        filters={
            "tenant_id": TENANT_ID,
            "project_global_id": project_id,
            "trial_round_global_id": round_id,
            "event_version": event_version,
        },
        fields=["global_id", "to_state"],
        limit_page_length=2,
    )
    event = exact_single(events, "P7-04 historical Round lifecycle event")
    supplied = (
        json.loads(document.round_snapshot)
        if isinstance(document.round_snapshot, str)
        else dict(document.round_snapshot)
    )
    supplied.update(
        {
            "currentState": str(event.to_state),
            "currentEventGlobalId": str(event.global_id),
            "optimisticVersion": event_version,
        }
    )
    historical = trial_round_from_snapshot(supplied)
    require(
        str(historical.project_global_id) == project_id
        and str(historical.global_id) == round_id
        and historical.current_state.value == "running"
        and historical.optimistic_version == 3,
        "P7-04 historical target Round reconstruction drifted",
    )
    return historical.snapshot_payload() | {"snapshotHash": historical.snapshot_hash}


def trial_execution_reference_context(
    fixture_run_id: str,
    *,
    project_id: str,
    tooling_master_id: str,
) -> dict[str, object]:
    import frappe

    document_runtime._validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "P7-02 reference fixture namespace drifted",
    )
    project = frappe.get_doc("NPI Engineering Project", project_id)
    require(
        str(project.global_id) == project_id
        and str(project.tenant_id) == TENANT_ID,
        "P7-02 reference fixture Project identity drifted",
    )

    binding = None
    tooling_set = None
    tooling_revision = None
    cavities: list[dict[str, Any]] = []
    bindings = frappe.get_all(
        "NPI Tooling Set Revision Binding",
        filters={
            "tenant_id": TENANT_ID,
            "project_global_id": project_id,
            "tooling_master_global_id": tooling_master_id,
        },
        fields=[
            "global_id",
            "tooling_set_global_id",
            "tooling_set_snapshot_hash",
            "tooling_revision_global_id",
            "tooling_revision_snapshot_hash",
            "snapshot_hash",
        ],
        order_by="creation asc, global_id asc",
        limit_page_length=100,
    )
    for candidate in bindings:
        try:
            candidate_set = frappe.get_doc(
                "NPI Tooling Set",
                str(candidate.tooling_set_global_id),
            )
            candidate_revision = frappe.get_doc(
                "NPI Tooling Revision",
                str(candidate.tooling_revision_global_id),
            )
        except frappe.DoesNotExistError:
            continue
        parsed_cavities = (
            json.loads(candidate_revision.cavity_snapshot)
            if isinstance(candidate_revision.cavity_snapshot, str)
            else candidate_revision.cavity_snapshot
        )
        if (
            str(candidate_set.project_global_id) == project_id
            and str(candidate_set.tooling_master_global_id) == tooling_master_id
            and str(candidate_revision.project_global_id) == project_id
            and str(candidate_revision.tooling_master_global_id) == tooling_master_id
            and str(candidate.tooling_set_snapshot_hash)
            == str(candidate_set.snapshot_hash)
            and str(candidate.tooling_revision_snapshot_hash)
            == str(candidate_revision.snapshot_hash)
            and isinstance(parsed_cavities, list)
            and bool(parsed_cavities)
            and all(isinstance(value, dict) for value in parsed_cavities)
        ):
            binding = candidate
            tooling_set = candidate_set
            tooling_revision = candidate_revision
            cavities = parsed_cavities
            break
    require(
        binding is not None
        and tooling_set is not None
        and tooling_revision is not None,
        "P7-02 exact Tooling Set binding is unavailable",
    )

    baselines = frappe.get_all(
        "NPI Document Baseline",
        filters={"tenant_id": TENANT_ID, "project_global_id": project_id},
        fields=["global_id", "baseline_version", "snapshot_hash"],
        order_by="baseline_version desc, global_id asc",
        limit_page_length=1,
    )
    parts = frappe.get_all(
        "NPI Engineering Part Revision",
        filters={
            "tenant_id": TENANT_ID,
            "originating_project_global_id": project_id,
        },
        fields=["global_id", "revision_number", "snapshot_hash"],
        order_by="revision_number desc, global_id asc",
        limit_page_length=1,
    )
    chains = frappe.get_all(
        "NPI Tooling Process Chain Revision",
        filters={"tenant_id": TENANT_ID, "project_global_id": project_id},
        fields=["global_id", "chain_version", "snapshot_hash"],
        order_by="chain_version desc, global_id asc",
        limit_page_length=1,
    )
    lifecycles = frappe.get_all(
        "NPI Document Revision Lifecycle",
        filters={
            "tenant_id": TENANT_ID,
            "project_global_id": project_id,
            "current_state": "released",
        },
        fields=["revision_global_id", "lifecycle_version"],
        order_by="lifecycle_version desc, global_id asc",
        limit_page_length=1,
    )
    require(
        len(baselines) == len(parts) == len(chains) == len(lifecycles) == 1,
        "P7-02 cumulative locked-reference predecessor is unavailable",
    )
    baseline = baselines[0]
    part = parts[0]
    chain = chains[0]
    inspection = frappe.get_doc(
        "NPI Document Revision",
        str(lifecycles[0].revision_global_id),
    )
    cavity_ids = [
        require_uuid(value.get("globalId"), "P7-02 cavity")
        for value in cavities
    ]
    references = [
        {
            "globalId": require_uuid(baseline.global_id, "P7-02 baseline"),
            "kind": "design_baseline",
            "expectedOptimisticVersion": int(baseline.baseline_version),
        },
        {
            "globalId": require_uuid(part.global_id, "P7-02 part revision"),
            "kind": "part_revision",
            "expectedOptimisticVersion": int(part.revision_number),
        },
        {
            "globalId": require_uuid(tooling_revision.global_id, "P7-02 tooling revision"),
            "kind": "tooling_revision",
            "expectedOptimisticVersion": int(tooling_revision.revision_number),
        },
        {
            "globalId": require_uuid(tooling_set.global_id, "P7-02 tooling set"),
            "kind": "tooling_set",
            "expectedOptimisticVersion": 1,
        },
        {
            "globalId": require_uuid(binding.global_id, "P7-02 tooling binding"),
            "kind": "tooling_set_binding",
            "expectedOptimisticVersion": 1,
        },
        *(
            {
                "globalId": cavity_id,
                "kind": "cavity",
                "expectedOptimisticVersion": int(tooling_revision.revision_number),
            }
            for cavity_id in cavity_ids
        ),
        {
            "globalId": require_uuid(chain.global_id, "P7-02 process chain"),
            "kind": "process_chain",
            "expectedOptimisticVersion": int(chain.chain_version),
        },
        {
            "globalId": require_uuid(inspection.global_id, "P7-02 inspection document"),
            "kind": "inspection_document",
            "expectedOptimisticVersion": int(inspection.optimistic_version),
        },
    ]
    return {
        "cavityIds": cavity_ids,
        "fixtureRunId": fixture_run_id,
        "references": references,
    }


def observe_trial_file_scan(
    fixture_run_id: str,
    *,
    project_id: str,
    round_id: str,
    file_revision_id: str,
) -> dict[str, object]:
    import frappe
    from frappe.utils import now_datetime

    from npi_core.controlled_evidence_validation import FILE_SCAN_RESULT_FLAG

    document_runtime._validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "P7-02 scanner fixture namespace drifted",
    )
    revision = frappe.get_doc("NPI File Revision", file_revision_id)
    file_document = frappe.get_doc("File", str(revision.frappe_file_id))
    before_hash = str(revision.sha256)
    require(
        str(revision.tenant_id) == TENANT_ID
        and str(revision.project_global_id) == project_id
        and str(revision.document_global_id) == round_id
        and str(revision.scan_state) == "pending"
        and int(revision.optimistic_version) == 1
        and int(file_document.is_private) == 1
        and isinstance(before_hash, str)
        and len(before_hash) == 64,
        "P7-02 scanner fixture File Revision boundary drifted",
    )
    previous = getattr(frappe.flags, FILE_SCAN_RESULT_FLAG, None)
    setattr(frappe.flags, FILE_SCAN_RESULT_FLAG, True)
    try:
        revision.scan_state = "clean"
        revision.scan_observed_at = now_datetime()
        revision.save()
    finally:
        if previous is None:
            delattr(frappe.flags, FILE_SCAN_RESULT_FLAG)
        else:
            setattr(frappe.flags, FILE_SCAN_RESULT_FLAG, previous)
    frappe.db.commit()
    require(
        str(revision.sha256) == before_hash
        and str(revision.scan_state) == "clean"
        and int(revision.optimistic_version) == 2,
        "P7-02 scanner observation changed immutable File truth",
    )
    return {
        "fileRevisionId": file_revision_id,
        "optimisticVersion": int(revision.optimistic_version),
        "scanState": str(revision.scan_state),
        "sha256": before_hash,
    }


BENCH_FIXTURES = {
    "ensure_trial_quality_verifier_member": ensure_trial_quality_verifier_member,
    "ensure_trial_review_policy": ensure_trial_review_policy,
    "historical_trial_round_context": historical_trial_round_context,
    "observe_trial_file_scan": observe_trial_file_scan,
    "trial_execution_reference_context": trial_execution_reference_context,
    "verify_trial_runtime_schema": verify_trial_runtime_schema,
}


def run_bench_fixture(method: str, kwargs: dict[str, object]) -> dict[str, Any]:
    require(method in BENCH_FIXTURES, "P7-01 Bench fixture is unavailable")
    require(
        BENCH_PATH.is_dir()
        and not BENCH_PATH.is_symlink()
        and BENCH_PATH.resolve() == BENCH_PATH,
        "P7-01 verifier requires the fixed physical Bench",
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
            str(ROOT / "scripts" / "verify_trial_runtime.py"),
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
        f"P7-01 Bench fixture failed: {method}: {completed.stderr[-2000:]}",
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    require(bool(lines), f"P7-01 Bench fixture was silent: {method}")
    result = json.loads(lines[-1])
    require(isinstance(result, dict), "P7-01 Bench fixture result is invalid")
    return result


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    require(method in BENCH_FIXTURES, "P7-01 Bench fixture is unavailable")
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
        description="Verify the cumulative controlled P7-04 Trial review runtime.",
    )
    parser.add_argument("--base-url")
    parser.add_argument("--bench-fixture", choices=tuple(BENCH_FIXTURES))
    parser.add_argument("--fixture-kwargs")
    parser.add_argument(
        "--route-disable-probe",
        choices=(
            "planning-disabled",
            "planning-recovered",
            "execution-disabled",
            "execution-recovered",
            "quality-disabled",
            "quality-recovered",
            "review-disabled",
            "review-recovered",
        ),
    )
    parser.add_argument("--replay-only", action="store_true")
    arguments = parser.parse_args()
    if arguments.bench_fixture is not None:
        require(
            arguments.base_url is None
            and isinstance(arguments.fixture_kwargs, str)
            and arguments.route_disable_probe is None
            and not arguments.replay_only,
            "P7-01 Bench fixture arguments are invalid",
        )
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "P7-01 fixture kwargs are invalid")
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return
    require(
        isinstance(arguments.base_url, str)
        and arguments.fixture_kwargs is None
        and document_runtime.CALLER_SUPPLIED_FIXTURE_RUN_ID is not None,
        "P7-02 runtime base URL and fixture namespace are required",
    )
    administrator_password = secret_from_environment(
        "NPI_RUNTIME_ADMINISTRATOR_PASSWORD"
    )
    fixture_password = secret_from_environment("NPI_RUNTIME_FIXTURE_PASSWORD")
    base_url = validate_local_fixture_inputs(
        arguments.base_url,
        ACTOR_USER,
        UNRELATED_USER,
    )
    require(
        FIXTURE_RUN_ID != "0" * 32
        and VERIFIER_USER.endswith("@example.invalid")
        and REVIEW_USER.endswith("@example.invalid")
        and UNRELATED_USER.endswith("@example.invalid")
        and len(
            {
                ACTOR_USER,
                VERIFIER_USER,
                REVIEW_USER,
                UNRELATED_USER,
                document_runtime.BASELINE_USER,
            }
        )
        == 5
        and RESPONSIBLE_MEMBER_ID == document_runtime.BASELINE_MEMBER_ID,
        "P7-02 fixture identity drifted",
    )
    administrator = login(base_url, ACTOR_USER, administrator_password)
    csrf_token = bootstrap_csrf(administrator, base_url, ACTOR_USER)
    require(
        int(arguments.route_disable_probe is not None)
        + int(arguments.replay_only)
        <= 1,
        "P7-02 runtime modes are mutually exclusive",
    )
    if arguments.route_disable_probe is not None:
        route_disable_probe(
            administrator,
            base_url,
            expected_mode=arguments.route_disable_probe,
        )
        print(json.dumps({"routeMode": arguments.route_disable_probe}, sort_keys=True))
        return
    if arguments.replay_only:
        reviewer = login(base_url, REVIEW_USER, fixture_password)
        reviewer_csrf = bootstrap_csrf(reviewer, base_url, REVIEW_USER)
        run_replay(
            administrator,
            base_url,
            csrf_token,
            reviewer,
            reviewer_csrf,
        )
        print(
            json.dumps(
                {"crossProcessReplay": True, "fixtureRunId": FIXTURE_RUN_ID},
                sort_keys=True,
            )
        )
        print("local Frappe Trial review runtime replay verification passed")
        return
    evidence = run_fresh(
        administrator,
        base_url,
        csrf_token,
        fixture_password,
    )
    print(json.dumps(evidence, sort_keys=True))
    print("local Frappe Trial review runtime verification passed")


if __name__ == "__main__":
    main()
