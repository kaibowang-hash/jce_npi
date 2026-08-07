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
    delete_resource,
    get_resource,
    list_resources,
    post_project,
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
    f"npi-tooling-{FIXTURE_RUN_ID[:20]}-unrelated@example.invalid"
)
SECOND_PROJECT_CODE = f"P6-01-{FIXTURE_RUN_ID[:16].upper()}"

PART_ONE_KEY = f"p6-01-runtime-r1-{FIXTURE_RUN_ID}-part-one"
REQUIREMENT_KEY = f"p6-01-runtime-r1-{FIXTURE_RUN_ID}-requirement"
MASTER_KEY = f"p6-01-runtime-r1-{FIXTURE_RUN_ID}-master"
APPLICABILITY_ONE_KEY = f"p6-01-runtime-r1-{FIXTURE_RUN_ID}-applicability-one"
APPLICABILITY_CONFLICT_KEY = (
    f"p6-01-runtime-r1-{FIXTURE_RUN_ID}-applicability-conflict"
)
APPLICABILITY_TWO_KEY = f"p6-01-runtime-r1-{FIXTURE_RUN_ID}-applicability-two"
PART_REVISION_KEY = f"p6-01-runtime-r1-{FIXTURE_RUN_ID}-part-revision"
STALE_PART_REVISION_KEY = (
    f"p6-01-runtime-r1-{FIXTURE_RUN_ID}-stale-part-revision"
)
SECOND_PROJECT_KEY = f"p6-01-runtime-r1-{FIXTURE_RUN_ID}-second-project"
PART_TWO_KEY = f"p6-01-runtime-r1-{FIXTURE_RUN_ID}-part-two"
SHARED_APPLICABILITY_KEY = (
    f"p6-01-runtime-r1-{FIXTURE_RUN_ID}-shared-applicability"
)
PREDECESSOR_ROUTE_QUERY = "p601-predecessor-route-isolation"
PART_CREATE_DIAGNOSTICS_ENABLED = False
APPLICABILITY_CREATE_DIAGNOSTICS_ENABLED = True
_PART_CREATE_DIAGNOSTIC_HEADER = "X-NPI-Diagnostic-Scope"
_PART_CREATE_DIAGNOSTIC_SCOPE = "p601-part-create-v1"
_APPLICABILITY_CREATE_DIAGNOSTIC_SCOPE = "p601-applicability-create-v1"
_SERVER_DIAGNOSTIC_LOG_TAIL_LIMIT = 64 * 1024
_PART_CREATE_DIAGNOSTIC_CODES = frozenset(
    {
        "P601_PART_CREATE_COMMAND_CONTEXT",
        "P601_PART_CREATE_INPUT_PARSE",
        "P601_PART_CREATE_PROJECT_LOCK",
        "P601_PART_CREATE_IDEMPOTENCY_CONTEXT",
        "P601_PART_CREATE_DOMAIN_BUILD",
        "P601_PART_CREATE_RECEIPT_INSERT",
        "P601_PART_CREATE_ROOT_INSERT",
        "P601_PART_CREATE_REVISION_INSERT",
        "P601_PART_CREATE_ROOT_POINTER_SAVE",
        "P601_PART_CREATE_AUDIT_APPEND",
        "P601_PART_CREATE_RESPONSE_BUILD",
        "P601_PART_CREATE_RECEIPT_SEAL",
        "P601_PART_CREATE_API_RESPONSE",
    }
)
_APPLICABILITY_CREATE_DIAGNOSTIC_CODES = frozenset(
    {
        "P601_APPLICABILITY_CREATE_COMMAND_CONTEXT",
        "P601_APPLICABILITY_CREATE_INPUT_PARSE",
        "P601_APPLICABILITY_CREATE_PROJECT_LOCK",
        "P601_APPLICABILITY_CREATE_IDEMPOTENCY_CONTEXT",
        "P601_APPLICABILITY_CREATE_REFERENCE_LOAD",
        "P601_APPLICABILITY_CREATE_REFERENCE_VALIDATE",
        "P601_APPLICABILITY_CREATE_RETAINED_LOAD",
        "P601_APPLICABILITY_CREATE_PREDECESSOR_RESOLVE",
        "P601_APPLICABILITY_CREATE_DOMAIN_BUILD",
        "P601_APPLICABILITY_CREATE_DOMAIN_VALIDATE",
        "P601_APPLICABILITY_CREATE_RECEIPT_INSERT",
        "P601_APPLICABILITY_CREATE_RELATIONSHIP_INSERT",
        "P601_APPLICABILITY_CREATE_AUDIT_APPEND",
        "P601_APPLICABILITY_CREATE_RESPONSE_BUILD",
        "P601_APPLICABILITY_CREATE_RECEIPT_SEAL",
        "P601_APPLICABILITY_CREATE_API_RESPONSE",
    }
)
_TRACE_PATTERN = re.compile(r"^trace-[a-f0-9]{32}$")
_TYPE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,127}$")

TOOLING_DOCTYPES = (
    "NPI Engineering Part",
    "NPI Engineering Part Revision",
    "NPI Tooling Requirement",
    "NPI Tooling Master",
    "NPI Tooling Applicability",
    "NPI Tooling Command Idempotency",
)


def tooling_path(project_id: str, suffix: str = "") -> str:
    return f"/api/npi/v1/projects/{project_id}/tooling{suffix}"


def tooling_request(
    opener,
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    csrf_token: str | None = None,
    idempotency_key: str | None = None,
    query_key: str = "query",
    part_create_diagnostic: bool = False,
    applicability_create_diagnostic: bool = False,
) -> HttpResult:
    headers = (
        document_runtime.command_headers(csrf_token, idempotency_key)
        if idempotency_key is not None
        else document_runtime.query_headers(f"p601-{query_key}")
    )
    if part_create_diagnostic or applicability_create_diagnostic:
        require(
            method == "POST" and idempotency_key is not None,
            "The P6-01 diagnostic requires one command request",
        )
        require(
            part_create_diagnostic is not applicability_create_diagnostic,
            "Exactly one P6-01 diagnostic scope must be active",
        )
        headers[_PART_CREATE_DIAGNOSTIC_HEADER] = (
            _PART_CREATE_DIAGNOSTIC_SCOPE
            if part_create_diagnostic
            else _APPLICABILITY_CREATE_DIAGNOSTIC_SCOPE
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
        "P6-01 request identity was not echoed",
    )
    require(
        result.headers.get("Cache-Control") == "private, no-store",
        "P6-01 private no-store response drifted",
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
    *,
    part_create_diagnostic: bool = False,
    applicability_create_diagnostic: bool = False,
) -> HttpResult:
    result = tooling_request(
        opener,
        base_url,
        path,
        method="POST",
        payload=payload,
        csrf_token=csrf_token,
        idempotency_key=key,
        part_create_diagnostic=part_create_diagnostic,
        applicability_create_diagnostic=applicability_create_diagnostic,
    )
    if result.status != 201 and (
        part_create_diagnostic or applicability_create_diagnostic
    ):
        diagnostic = _sanitized_server_diagnostic(
            result.trace_id,
            (
                _PART_CREATE_DIAGNOSTIC_CODES
                if part_create_diagnostic
                else _APPLICABILITY_CREATE_DIAGNOSTIC_CODES
            ),
        )
        if diagnostic is not None:
            exception_type, code, trace_id = diagnostic
            raise RuntimeError(
                f"[diagnostic_code={code}; exception_type={exception_type}; "
                f"trace_id={trace_id}]"
            )
    require(result.status == 201, f"P6-01 command {key} did not return HTTP 201")
    require(
        result.headers.get("Idempotency-Replayed") in {"true", "false"},
        "P6-01 replay header is invalid",
    )
    return result


def _sanitized_part_create_server_diagnostic(
    trace_id: str | None,
) -> tuple[str, str, str] | None:
    """Read only one allowlisted P6-01 server record for the exact trace."""

    return _sanitized_server_diagnostic(trace_id, _PART_CREATE_DIAGNOSTIC_CODES)


def _sanitized_server_diagnostic(
    trace_id: str | None,
    allowed_codes: frozenset[str],
) -> tuple[str, str, str] | None:
    """Read one allowlisted P6-01 server record for the exact trace."""

    if not isinstance(trace_id, str) or _TRACE_PATTERN.fullmatch(trace_id) is None:
        return None
    try:
        bench_root = BENCH_PATH.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    candidates = (
        BENCH_PATH / "logs" / "npi_core.log",
        BENCH_PATH / "sites" / SITE_NAME / "logs" / "npi_core.log",
    )
    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            if candidate.is_symlink() or not candidate.is_file():
                continue
            resolved = candidate.resolve(strict=True)
            if not resolved.is_relative_to(bench_root):
                continue
            with resolved.open("rb") as log_file:
                log_file.seek(0, os.SEEK_END)
                size = log_file.tell()
                log_file.seek(max(0, size - _SERVER_DIAGNOSTIC_LOG_TAIL_LIMIT))
                tail = log_file.read(_SERVER_DIAGNOSTIC_LOG_TAIL_LIMIT)
        except (OSError, RuntimeError):
            continue
        for line in reversed(tail.decode("utf-8", errors="ignore").splitlines()):
            if trace_id not in line:
                continue
            for start, character in enumerate(line):
                if character != "{":
                    continue
                try:
                    record, _end = decoder.raw_decode(line[start:])
                except (TypeError, ValueError):
                    continue
                if not isinstance(record, dict) or set(record) != {
                    "code",
                    "exceptionType",
                    "traceId",
                }:
                    continue
                code = record.get("code")
                exception_type = record.get("exceptionType")
                if (
                    record.get("traceId") == trace_id
                    and isinstance(code, str)
                    and code in allowed_codes
                    and isinstance(exception_type, str)
                    and _TYPE_PATTERN.fullmatch(exception_type) is not None
                ):
                    return exception_type, code, trace_id
    return None


def assert_workspace(
    result: HttpResult,
    project_id: str,
    *,
    create: bool = True,
) -> dict[str, Any]:
    require(result.status == 200 or result.status == 201, "P6-01 workspace failed")
    require(
        set(result.body)
        == {
            "project",
            "permissions",
            "masters",
            "requirements",
            "parts",
            "applicability",
            "downstream",
        },
        "P6-01 workspace keys drifted",
    )
    require(
        result.body.get("project", {}).get("globalId") == project_id,
        "P6-01 workspace Project identity drifted",
    )
    require(
        result.body.get("permissions")
        == {
            "view": True,
            "createPart": create,
            "createRequirement": create,
            "createMaster": create,
            "createApplicability": create,
            "transitionLifecycle": False,
        },
        "P6-01 capability truth drifted",
    )
    expected_downstream = {
        "lifecycle": "lifecycle_policy_unavailable",
        "revision": "tooling_revision_not_delivered",
        "physicalSet": "physical_set_not_delivered",
        "trial": "trial_not_delivered",
        "erp": "erp_projection_unavailable",
    }
    require(
        {
            name: value.get("reasonCode")
            for name, value in result.body.get("downstream", {}).items()
            if isinstance(value, dict) and value.get("state") == "unavailable"
        }
        == expected_downstream,
        "P6-01 downstream unavailable truth drifted",
    )
    return result.body


def part_payload(title: str, revision_label: str) -> dict[str, object]:
    return {
        "title": title,
        "revisionLabel": revision_label,
        "reason": "Create an exact synthetic engineering Part revision.",
    }


def applicability_payload(
    master_id: str,
    revision_id: str,
    *,
    effective_from: str,
    effective_to: str | None,
    relationship_id: str | None = None,
    expected_version: int | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "toolingMasterGlobalId": master_id,
        "partRevisionGlobalId": revision_id,
        "effectiveFrom": effective_from,
        "reason": "Record exact synthetic Tooling applicability.",
    }
    if effective_to is not None:
        value["effectiveTo"] = effective_to
    if relationship_id is not None:
        value["relationshipGlobalId"] = relationship_id
        value["expectedVersion"] = expected_version
    return value


def exact_single(values: object, label: str) -> dict[str, Any]:
    require(
        isinstance(values, list)
        and len(values) == 1
        and isinstance(values[0], dict),
        f"P6-01 {label} cardinality drifted",
    )
    return values[0]


def create_second_project(
    administrator,
    base_url: str,
    csrf_token: str,
) -> str:
    payload = {
        "tenantId": TENANT_ID,
        "businessCode": SECOND_PROJECT_CODE,
        "title": "Synthetic shared Tooling consumer Project",
        "projectType": "new_tool",
        "ownerUserId": document_runtime.BASELINE_USER,
        "targetSop": "2027-03-31",
        "templateGlobalId": document_runtime.PROJECT_TEMPLATE_ID,
        "templateVersion": document_runtime.PROJECT_TEMPLATE_VERSION,
        "expectedVersion": 1,
        "references": [
            {
                "type": "customer",
                "sourceSystem": "ERPNEXT",
                "sourceObjectId": f"SYNTHETIC-SHARED-{FIXTURE_RUN_ID[:16]}",
            }
        ],
    }
    created = post_project(
        administrator,
        base_url,
        payload,
        csrf_token=csrf_token,
        idempotency_key=SECOND_PROJECT_KEY,
        request_id=document_runtime.fixture_request_id(SECOND_PROJECT_KEY),
    )
    require(
        created.status == 201
        and created.headers.get("Idempotency-Replayed") == "false",
        "P6-01 second Project fixture was not created exactly once",
    )
    project_id = created.body.get("project", {}).get("globalId")
    require(
        isinstance(project_id, str) and str(UUID(project_id)) == project_id,
        "P6-01 second Project identity drifted",
    )
    return project_id


def rows(
    administrator,
    base_url: str,
    doctype: str,
    filters: list[list[object]],
    fields: list[str] | None = None,
) -> list[dict[str, object]]:
    return list_resources(
        administrator,
        base_url,
        doctype,
        filters=filters,
        fields=fields or ["name"],
    )


def verify_persistence(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    first_project_id: str,
    second_project_id: str,
    master_id: str,
    first_revision_id: str,
) -> None:
    expected_counts = (
        (
            "NPI Engineering Part",
            "originating_project_global_id",
            first_project_id,
            1,
        ),
        (
            "NPI Engineering Part Revision",
            "originating_project_global_id",
            first_project_id,
            2,
        ),
        ("NPI Tooling Requirement", "project_global_id", first_project_id, 1),
        ("NPI Tooling Applicability", "project_global_id", first_project_id, 2),
        (
            "NPI Engineering Part",
            "originating_project_global_id",
            second_project_id,
            1,
        ),
        (
            "NPI Engineering Part Revision",
            "originating_project_global_id",
            second_project_id,
            1,
        ),
        ("NPI Tooling Applicability", "project_global_id", second_project_id, 1),
    )
    for doctype, fieldname, project_id, expected in expected_counts:
        require(
            len(rows(administrator, base_url, doctype, [[fieldname, "=", project_id]]))
            == expected,
            f"P6-01 persisted {doctype} cardinality drifted",
        )
    masters = rows(
        administrator,
        base_url,
        "NPI Tooling Master",
        [["tenant_id", "=", TENANT_ID]],
        ["global_id", "originating_project_global_id", "snapshot_hash"],
    )
    require(
        len(masters) == 1
        and masters[0].get("global_id") == master_id
        and masters[0].get("originating_project_global_id") == first_project_id,
        "P6-01 shared logical Master was cloned or re-owned",
    )
    receipts = rows(
        administrator,
        base_url,
        "NPI Tooling Command Idempotency",
        [["tenant_id", "=", TENANT_ID]],
        [
            "actor_user_id",
            "idempotency_key_hash",
            "payload_hash",
            "response_hash",
            "sealed",
        ],
    )
    require(
        len(receipts) == 8
        and all(value.get("actor_user_id") == ACTOR_USER for value in receipts)
        and all(value.get("sealed") == 1 for value in receipts)
        and all(
            all(
                isinstance(value.get(fieldname), str)
                and len(str(value[fieldname])) == 64
                for fieldname in (
                    "idempotency_key_hash",
                    "payload_hash",
                    "response_hash",
                )
            )
            for value in receipts
        ),
        "P6-01 actor-bound sealed receipt truth drifted",
    )
    expected_audits = {
        "part.create": 2,
        "part.revise": 1,
        "tooling_requirement.create": 1,
        "tooling_master.create": 1,
        "tooling_applicability.create": 3,
    }
    audit_rows: list[dict[str, object]] = []
    for operation, expected in expected_audits.items():
        matching = rows(
            administrator,
            base_url,
            "NPI Audit Event",
            [["operation", "=", operation]],
            ["name", "operation", "result", "trace_id"],
        )
        require(
            len(matching) == expected
            and all(value.get("result") == "created" for value in matching)
            and all(value.get("trace_id") for value in matching),
            f"P6-01 append-only audit truth drifted for {operation}",
        )
        audit_rows.extend(matching)
    retained_revision = get_resource(
        administrator,
        base_url,
        "NPI Engineering Part Revision",
        first_revision_id,
    )
    snapshot_hash = retained_revision.body.get("data", {}).get("snapshot_hash")
    require(
        retained_revision.status == 200
        and isinstance(snapshot_hash, str)
        and len(snapshot_hash) == 64,
        "P6-01 first immutable Part Revision is unavailable",
    )
    update = update_resource(
        administrator,
        base_url,
        "NPI Engineering Part Revision",
        first_revision_id,
        {"title": "Mutation must be rejected"},
        csrf_token,
    )
    delete = delete_resource(
        administrator,
        base_url,
        "NPI Engineering Part Revision",
        first_revision_id,
        csrf_token,
    )
    require(
        update.status in {403, 417} and delete.status in {403, 417},
        "P6-01 immutable Part Revision accepted generic mutation",
    )
    after = get_resource(
        administrator,
        base_url,
        "NPI Engineering Part Revision",
        first_revision_id,
    )
    require(
        after.status == 200
        and after.body.get("data", {}).get("snapshot_hash") == snapshot_hash,
        "P6-01 rejected mutation changed immutable Part Revision truth",
    )
    audit_name = str(audit_rows[0]["name"])
    audit_update = update_resource(
        administrator,
        base_url,
        "NPI Audit Event",
        audit_name,
        {"result": "tampered"},
        csrf_token,
    )
    audit_delete = delete_resource(
        administrator,
        base_url,
        "NPI Audit Event",
        audit_name,
        csrf_token,
    )
    require(
        audit_update.status in {403, 417} and audit_delete.status in {403, 417},
        "P6-01 append-only audit accepted generic mutation",
    )


def run_fresh(
    administrator,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
) -> dict[str, object]:
    first_project_id, _version = document_runtime.fixture_project(
        administrator,
        base_url,
    )
    schema = run_bench_fixture(
        "verify_tooling_runtime_schema",
        {"fixture_run_id": FIXTURE_RUN_ID},
    )
    empty = tooling_request(
        administrator,
        base_url,
        tooling_path(first_project_id),
        query_key="empty",
    )
    empty_workspace = assert_workspace(empty, first_project_id)
    require(
        all(
            empty_workspace[name] == []
            for name in ("masters", "requirements", "parts", "applicability")
        ),
        "P6-01 fresh workspace was not empty",
    )
    guest = tooling_request(
        urllib.request.build_opener(),
        base_url,
        tooling_path(first_project_id),
        query_key="guest",
    )
    validate_problem(guest, 401, "AUTHENTICATION_REQUIRED")
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
            tooling_path(first_project_id),
            query_key="unrelated",
        )
        absent = tooling_request(
            unrelated,
            base_url,
            tooling_path("00000000-0000-4000-8000-000000000001"),
            query_key="absent",
        )
        validate_problem(denied, 404, "TOOLING_UNAVAILABLE")
        validate_problem(absent, 404, "TOOLING_UNAVAILABLE")
        require(
            {
                key: denied.body.get(key)
                for key in ("type", "title", "status", "code", "retryable")
            }
            == {
                key: absent.body.get(key)
                for key in ("type", "title", "status", "code", "retryable")
            },
            "P6-01 unauthorized and absent Projects are distinguishable",
        )
    finally:
        delete_disposable_user(
            administrator,
            base_url,
            UNRELATED_USER,
            csrf_token,
        )

    first_part_payload = part_payload("Synthetic front housing", "A")
    created_part = command(
        administrator,
        base_url,
        csrf_token,
        f"/api/npi/v1/projects/{first_project_id}/parts",
        first_part_payload,
        PART_ONE_KEY,
        part_create_diagnostic=PART_CREATE_DIAGNOSTICS_ENABLED,
    )
    require(
        created_part.headers.get("Idempotency-Replayed") == "false",
        "P6-01 first Part replay truth drifted",
    )
    created_part_workspace = assert_workspace(created_part, first_project_id)
    part_one = exact_single(created_part_workspace["parts"], "first Part")
    revision_one = part_one.get("currentRevision", {})
    part_one_id = str(part_one.get("globalId"))
    revision_one_id = str(revision_one.get("globalId"))
    revision_one_hash = revision_one.get("snapshotHash")
    require(
        str(UUID(part_one_id)) == part_one_id
        and str(UUID(revision_one_id)) == revision_one_id
        and revision_one.get("revisionNumber") == 1
        and isinstance(revision_one_hash, str)
        and len(revision_one_hash) == 64,
        "P6-01 distinct Part and initial Revision truth drifted",
    )
    replay = command(
        administrator,
        base_url,
        csrf_token,
        f"/api/npi/v1/projects/{first_project_id}/parts",
        first_part_payload,
        PART_ONE_KEY,
    )
    require(
        replay.headers.get("Idempotency-Replayed") == "true"
        and replay.body == created_part.body,
        "P6-01 exact Part replay changed response truth",
    )
    conflict_payload = dict(first_part_payload)
    conflict_payload["title"] = "Different synthetic intent"
    conflict = tooling_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{first_project_id}/parts",
        method="POST",
        payload=conflict_payload,
        csrf_token=csrf_token,
        idempotency_key=PART_ONE_KEY,
    )
    validate_problem(conflict, 409, "TOOLING_IDEMPOTENCY_CONFLICT")

    requirement = command(
        administrator,
        base_url,
        csrf_token,
        f"/api/npi/v1/projects/{first_project_id}/tooling-requirements",
        {
            "kind": "new_tool",
            "title": "Synthetic front housing Tooling need",
            "reason": "Record a distinct Project need without lifecycle truth.",
            "targetPartRevisionGlobalId": revision_one_id,
            "targetDate": "2027-01-15",
        },
        REQUIREMENT_KEY,
    )
    assert_workspace(requirement, first_project_id)
    master = command(
        administrator,
        base_url,
        csrf_token,
        f"/api/npi/v1/projects/{first_project_id}/tooling-masters",
        {"title": "Synthetic shared front housing tool"},
        MASTER_KEY,
    )
    master_workspace = assert_workspace(master, first_project_id)
    master_value = exact_single(master_workspace["masters"], "logical Master")
    master_id = str(master_value.get("globalId"))
    require(
        str(UUID(master_id)) == master_id
        and master_value.get("originatingProjectGlobalId") == first_project_id,
        "P6-01 logical Master identity drifted",
    )

    first_applicability = command(
        administrator,
        base_url,
        csrf_token,
        f"/api/npi/v1/projects/{first_project_id}/tooling-applicabilities",
        applicability_payload(
            master_id,
            revision_one_id,
            effective_from="2026-08-01",
            effective_to="2026-09-01",
        ),
        APPLICABILITY_ONE_KEY,
        applicability_create_diagnostic=APPLICABILITY_CREATE_DIAGNOSTICS_ENABLED,
    )
    first_applicability_workspace = assert_workspace(
        first_applicability,
        first_project_id,
    )
    applicability_one = exact_single(
        first_applicability_workspace["applicability"],
        "first Applicability",
    )
    relationship_id = str(applicability_one.get("relationshipGlobalId"))
    require(
        applicability_one.get("version") == 1
        and applicability_one.get("effectiveFrom") == "2026-08-01"
        and applicability_one.get("effectiveTo") == "2026-09-01"
        and str(UUID(relationship_id)) == relationship_id,
        "P6-01 first effective Applicability truth drifted",
    )
    overlapping = tooling_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{first_project_id}/tooling-applicabilities",
        method="POST",
        payload=applicability_payload(
            master_id,
            revision_one_id,
            relationship_id=relationship_id,
            expected_version=1,
            effective_from="2026-08-15",
            effective_to="2026-10-01",
        ),
        csrf_token=csrf_token,
        idempotency_key=APPLICABILITY_CONFLICT_KEY,
    )
    validate_problem(overlapping, 409, "TOOLING_APPLICABILITY_CONFLICT")
    after_overlap = tooling_request(
        administrator,
        base_url,
        tooling_path(first_project_id),
        query_key="after-overlap",
    )
    require(
        len(assert_workspace(after_overlap, first_project_id)["applicability"]) == 1,
        "P6-01 rejected Applicability left a persisted row",
    )
    successor = command(
        administrator,
        base_url,
        csrf_token,
        f"/api/npi/v1/projects/{first_project_id}/tooling-applicabilities",
        applicability_payload(
            master_id,
            revision_one_id,
            relationship_id=relationship_id,
            expected_version=1,
            effective_from="2026-09-01",
            effective_to=None,
        ),
        APPLICABILITY_TWO_KEY,
    )
    successor_workspace = assert_workspace(successor, first_project_id)
    versions = sorted(
        successor_workspace["applicability"],
        key=lambda value: value["version"],
    )
    require(
        [value.get("version") for value in versions] == [1, 2]
        and versions[1].get("predecessorGlobalId") == versions[0].get("globalId")
        and versions[1].get("effectiveFrom") == versions[0].get("effectiveTo"),
        "P6-01 Applicability successor chain drifted",
    )

    revised = command(
        administrator,
        base_url,
        csrf_token,
        f"/api/npi/v1/projects/{first_project_id}/parts/{part_one_id}/revisions",
        {
            "expectedVersion": 1,
            "revisionLabel": "B",
            "title": "Synthetic front housing revised",
            "reason": "Create one exact immutable successor Part Revision.",
        },
        PART_REVISION_KEY,
    )
    revised_workspace = assert_workspace(revised, first_project_id)
    revised_part = exact_single(revised_workspace["parts"], "revised Part")
    revision_two = revised_part.get("currentRevision", {})
    require(
        revised_part.get("version") == 2
        and revision_two.get("revisionNumber") == 2
        and revision_two.get("globalId") != revision_one_id,
        "P6-01 Part successor projection drifted",
    )
    stale = tooling_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{first_project_id}/parts/{part_one_id}/revisions",
        method="POST",
        payload={
            "expectedVersion": 1,
            "revisionLabel": "C",
            "title": "Stale synthetic revision",
            "reason": "This stale command must roll back.",
        },
        csrf_token=csrf_token,
        idempotency_key=STALE_PART_REVISION_KEY,
    )
    validate_problem(stale, 409, "TOOLING_VERSION_CONFLICT")
    after_stale = tooling_request(
        administrator,
        base_url,
        tooling_path(first_project_id),
        query_key="after-stale",
    )
    require(
        exact_single(
            assert_workspace(after_stale, first_project_id)["parts"],
            "Part after stale command",
        )
        .get("currentRevision", {})
        .get("globalId")
        == revision_two.get("globalId"),
        "P6-01 stale Part command changed current Revision",
    )

    second_project_id = create_second_project(administrator, base_url, csrf_token)
    second_empty = tooling_request(
        administrator,
        base_url,
        tooling_path(second_project_id),
        query_key="second-empty",
    )
    require(
        assert_workspace(second_empty, second_project_id)["masters"] == [],
        "P6-01 unrelated Project disclosed a Master before Applicability",
    )
    second_part = command(
        administrator,
        base_url,
        csrf_token,
        f"/api/npi/v1/projects/{second_project_id}/parts",
        part_payload("Synthetic shared consumer Part", "A"),
        PART_TWO_KEY,
    )
    second_part_value = exact_single(
        assert_workspace(second_part, second_project_id)["parts"],
        "second Project Part",
    )
    second_revision_id = str(
        second_part_value.get("currentRevision", {}).get("globalId")
    )
    shared = command(
        administrator,
        base_url,
        csrf_token,
        f"/api/npi/v1/projects/{second_project_id}/tooling-applicabilities",
        applicability_payload(
            master_id,
            second_revision_id,
            effective_from="2026-10-01",
            effective_to=None,
        ),
        SHARED_APPLICABILITY_KEY,
    )
    shared_workspace = assert_workspace(shared, second_project_id)
    shared_master = exact_single(shared_workspace["masters"], "shared Master")
    require(
        shared_master.get("globalId") == master_id
        and shared_master.get("originatingProjectGlobalId") == first_project_id
        and exact_single(shared_workspace["applicability"], "shared Applicability")
        .get("toolingMasterGlobalId")
        == master_id,
        "P6-01 second Project cloned or re-owned the shared Master",
    )
    detail = tooling_request(
        administrator,
        base_url,
        tooling_path(second_project_id, f"/{master_id}"),
        query_key="shared-detail",
    )
    require(
        exact_single(
            assert_workspace(detail, second_project_id)["masters"],
            "shared Master detail",
        )
        .get("globalId")
        == master_id,
        "P6-01 shared Master detail is unavailable in its authorized Project",
    )
    verify_persistence(
        administrator,
        base_url,
        csrf_token,
        first_project_id=first_project_id,
        second_project_id=second_project_id,
        master_id=master_id,
        first_revision_id=revision_one_id,
    )
    return {
        "appendOnlyAudits": 8,
        "crossProcessReplayReady": True,
        "fixtureRunId": FIXTURE_RUN_ID,
        "immutablePartRevisions": 3,
        "metadataSynchronized": schema.get("metadataSynchronized"),
        "projectApplicabilities": 3,
        "projects": 2,
        "rollbackVerified": True,
        "sharedMasterCount": 1,
    }


def route_disable_probe(
    administrator,
    base_url: str,
    *,
    expected_mode: str,
) -> None:
    project_id, _version = document_runtime.fixture_project(administrator, base_url)
    tooling = tooling_request(
        administrator,
        base_url,
        tooling_path(project_id),
        query_key=f"route-{expected_mode}",
    )
    if expected_mode == "disabled":
        validate_problem(tooling, 503, "TOOLING_ROUTES_DISABLED")
        documents = document_runtime.npi_request(
            administrator,
            base_url,
            f"/api/npi/v1/projects/{project_id}/documents",
            query_key=PREDECESSOR_ROUTE_QUERY,
        )
        require(
            documents.status == 200 and len(documents.body.get("items", [])) == 1,
            "P6-01 route switch changed the retained P5 Document route",
        )
        return
    workspace = assert_workspace(tooling, project_id)
    require(
        len(workspace["masters"]) == 1
        and len(workspace["parts"]) == 1
        and len(workspace["applicability"]) == 2,
        "P6-01 recovered route truth drifted",
    )


def run_replay(administrator, base_url: str, csrf_token: str) -> None:
    first_project_id, _version = document_runtime.fixture_project(
        administrator,
        base_url,
    )
    second_projects = rows(
        administrator,
        base_url,
        "NPI Engineering Project",
        [["business_code", "=", SECOND_PROJECT_CODE]],
        ["global_id"],
    )
    second_project_id = str(
        exact_single(second_projects, "second Project")["global_id"]
    )
    first_workspace = assert_workspace(
        tooling_request(
            administrator,
            base_url,
            tooling_path(first_project_id),
            query_key="replay-first",
        ),
        first_project_id,
    )
    master_id = str(
        exact_single(first_workspace["masters"], "replay Master")["globalId"]
    )
    part_replay = command(
        administrator,
        base_url,
        csrf_token,
        f"/api/npi/v1/projects/{first_project_id}/parts",
        part_payload("Synthetic front housing", "A"),
        PART_ONE_KEY,
    )
    require(
        part_replay.headers.get("Idempotency-Replayed") == "true",
        "P6-01 cross-process Part replay was not declared",
    )
    second_workspace = assert_workspace(
        tooling_request(
            administrator,
            base_url,
            tooling_path(second_project_id),
            query_key="replay-second",
        ),
        second_project_id,
    )
    second_revision_id = str(
        exact_single(second_workspace["parts"], "replay second Part")
        .get("currentRevision", {})
        .get("globalId")
    )
    shared_replay = command(
        administrator,
        base_url,
        csrf_token,
        f"/api/npi/v1/projects/{second_project_id}/tooling-applicabilities",
        applicability_payload(
            master_id,
            second_revision_id,
            effective_from="2026-10-01",
            effective_to=None,
        ),
        SHARED_APPLICABILITY_KEY,
    )
    require(
        shared_replay.headers.get("Idempotency-Replayed") == "true"
        and exact_single(
            shared_replay.body.get("masters"),
            "replayed shared Master",
        )
        .get("globalId")
        == master_id,
        "P6-01 cross-process shared-Master replay drifted",
    )


def verify_tooling_runtime_schema(fixture_run_id: str) -> dict[str, object]:
    import frappe

    document_runtime._validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "P6-01 schema fixture namespace drifted",
    )
    required_fields = {
        "NPI Engineering Part": {
            "global_id",
            "originating_project_global_id",
            "current_revision_global_id",
            "optimistic_version",
        },
        "NPI Engineering Part Revision": {
            "part_global_id",
            "revision_number",
            "predecessor_global_id",
            "revision_snapshot",
            "snapshot_hash",
        },
        "NPI Tooling Requirement": {
            "project_global_id",
            "requirement_kind",
            "target_part_revision_global_id",
            "requirement_snapshot",
        },
        "NPI Tooling Master": {
            "global_id",
            "originating_project_global_id",
            "master_snapshot",
            "snapshot_hash",
        },
        "NPI Tooling Applicability": {
            "relationship_global_id",
            "relationship_key_hash",
            "applicability_version",
            "effective_from",
            "effective_to",
            "applicability_snapshot",
        },
        "NPI Tooling Command Idempotency": {
            "receipt_key",
            "actor_user_id",
            "idempotency_key_hash",
            "payload_hash",
            "response_hash",
            "sealed",
        },
    }
    for doctype in TOOLING_DOCTYPES:
        require(
            frappe.db.table_exists(doctype),
            f"P6-01 table is unavailable: {doctype}",
        )
        fields = {
            field.fieldname
            for field in frappe.get_meta(doctype, cached=False).fields
        }
        require(
            required_fields[doctype] <= fields,
            f"P6-01 metadata is incomplete for {doctype}",
        )
    return {
        "doctypeCount": len(TOOLING_DOCTYPES),
        "fixtureRunId": fixture_run_id,
        "metadataSynchronized": True,
        "runtimeMarker": RUNTIME_MARKER,
    }


def run_bench_fixture(method: str, kwargs: dict[str, object]) -> dict[str, Any]:
    require(
        method == "verify_tooling_runtime_schema",
        "P6-01 Bench fixture is unavailable",
    )
    require(
        BENCH_PATH.is_dir()
        and not BENCH_PATH.is_symlink()
        and BENCH_PATH.resolve() == BENCH_PATH,
        "P6-01 verifier requires the fixed physical Bench",
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
            str(ROOT / "scripts" / "verify_tooling_runtime.py"),
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
    require(completed.returncode == 0, "P6-01 schema fixture failed")
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    require(bool(lines), "P6-01 schema fixture was silent")
    result = json.loads(lines[-1])
    require(isinstance(result, dict), "P6-01 schema fixture result is invalid")
    return result


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    require(
        method == "verify_tooling_runtime_schema",
        "P6-01 Bench fixture is unavailable",
    )
    import frappe

    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    try:
        frappe.set_user(ACTOR_USER)
        result = verify_tooling_runtime_schema(**kwargs)
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the real P6-01 controlled Tooling runtime.",
    )
    parser.add_argument("--base-url")
    parser.add_argument(
        "--bench-fixture",
        choices=("verify_tooling_runtime_schema",),
    )
    parser.add_argument("--fixture-kwargs")
    parser.add_argument(
        "--route-disable-probe",
        choices=("disabled", "recovered"),
    )
    parser.add_argument("--replay-only", action="store_true")
    arguments = parser.parse_args()
    if arguments.bench_fixture is not None:
        require(
            arguments.base_url is None
            and isinstance(arguments.fixture_kwargs, str)
            and arguments.route_disable_probe is None
            and not arguments.replay_only,
            "P6-01 Bench fixture arguments are invalid",
        )
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "P6-01 fixture kwargs are invalid")
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return
    require(
        isinstance(arguments.base_url, str)
        and arguments.fixture_kwargs is None
        and document_runtime.CALLER_SUPPLIED_FIXTURE_RUN_ID is not None,
        "P6-01 runtime base URL and fixture namespace are required",
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
        and UNRELATED_USER.endswith("@example.invalid")
        and SECOND_PROJECT_CODE.startswith("P6-01-"),
        "P6-01 fixture identity drifted",
    )
    administrator = login(base_url, ACTOR_USER, administrator_password)
    csrf_token = bootstrap_csrf(administrator, base_url, ACTOR_USER)
    require(
        int(arguments.route_disable_probe is not None)
        + int(arguments.replay_only)
        <= 1,
        "P6-01 runtime modes are mutually exclusive",
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
        run_replay(administrator, base_url, csrf_token)
        print(
            json.dumps(
                {"crossProcessReplay": True, "fixtureRunId": FIXTURE_RUN_ID},
                sort_keys=True,
            )
        )
        print("local Frappe Tooling runtime replay verification passed")
        return
    evidence = run_fresh(
        administrator,
        base_url,
        csrf_token,
        fixture_password,
    )
    print(json.dumps(evidence, sort_keys=True))
    print("local Frappe Tooling runtime verification passed")


if __name__ == "__main__":
    main()
