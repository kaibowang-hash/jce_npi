from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from verify_frappe_runtime import (
    HttpResult,
    login,
    require,
    secret_from_environment,
    validate_local_fixture_inputs,
    validate_problem,
)
from verify_project_runtime import (
    TENANT_ID,
    actor_key_hash,
    bootstrap_csrf,
    create_resource,
    delete_resource,
    get_resource,
    list_resources,
    update_resource,
)

FIXTURE_REVISION = 1
FIXTURE_RUN_ID_ENV = "NPI_GATE_REVIEW_RUNTIME_RUN_ID"
SITE_NAME = "npi.localhost"
RUNTIME_MARKER = "npi-one-local-runtime-disposable-v1"
DATABASE_NAME = "npi_one_runtime"
DATABASE_USER = "npi_one_runtime"
DATABASE_PORT = 3306
ROOT = Path(__file__).resolve().parents[1]
BENCH_PATH = ROOT / "tmp" / "frappe-bench"


def validated_fixture_run_id(candidate: str | None) -> str:
    if candidate is None:
        return uuid4().hex
    require(
        re.fullmatch(r"[a-f0-9]{32}", candidate) is not None,
        (
            f"{FIXTURE_RUN_ID_ENV} must be exactly 32 lowercase "
            "hexadecimal characters"
        ),
    )
    return candidate


CALLER_SUPPLIED_FIXTURE_RUN_ID = os.environ.get(FIXTURE_RUN_ID_ENV)
FIXTURE_RUN_ID = validated_fixture_run_id(CALLER_SUPPLIED_FIXTURE_RUN_ID)
FIXTURE_NAMESPACE = f"r{FIXTURE_REVISION}-{FIXTURE_RUN_ID}"
# The P4-04 verifier intentionally reuses only the P4-03 fixture builders.
# Give those helpers the same caller-owned namespace so every identity remains
# deterministic and independently disposable.
os.environ.setdefault("NPI_GATE_EVIDENCE_RUNTIME_RUN_ID", FIXTURE_RUN_ID)

import verify_gate_evidence_runtime as evidence_runtime  # noqa: E402


def fixture_id(scope: str) -> str:
    return str(
        uuid5(
            NAMESPACE_URL,
            (
                "https://npi-one.example.invalid/runtime/p4-04/"
                f"{FIXTURE_NAMESPACE}/{scope}"
            ),
        )
    )


FIXTURE_PREFIX = f"p4-04-runtime-{FIXTURE_NAMESPACE}"
POLICY_ID = fixture_id("gate-review-policy")
POLICY_VERSION = 1
POLICY_VERSION_KEY = f"{POLICY_ID}:{POLICY_VERSION}"
POLICY_CODE = f"P404-{FIXTURE_RUN_ID[:16].upper()}"
WRONG_TENANT_BUSINESS_CODE = f"P4-04-{FIXTURE_RUN_ID[:16].upper()}-TENANT"

REVIEW_STEP_KEY = "engineering"
REVIEW_SLOT = "engineering_reviewer"
DECISION_SLOT = "gate_decider"
REOPEN_SLOT = "gate_reopener"
EXCEPTION_SLOT = "exception_approver"
EXCEPTION_KIND = "p1_evidence_timing"

WRONG_PROJECT_CREATE_KEY = f"{FIXTURE_PREFIX}-wrong-tenant-project"
ACTION_CREATE_KEY = f"{FIXTURE_PREFIX}-closure-action"
ROLLBACK_START_KEY = f"{FIXTURE_PREFIX}-rollback-start"
START_KEY = f"{FIXTURE_PREFIX}-start"
REVIEW_KEY = f"{FIXTURE_PREFIX}-review"
ADMIN_REVIEW_DENIED_KEY = f"{FIXTURE_PREFIX}-admin-review-denied"
EXCEPTION_REQUEST_KEY = f"{FIXTURE_PREFIX}-exception-request"
EXCEPTION_DECISION_KEY = f"{FIXTURE_PREFIX}-exception-decision"
DECISION_KEY = f"{FIXTURE_PREFIX}-decision"
REOPEN_KEY = f"{FIXTURE_PREFIX}-reopen"
SECOND_DECISION_KEY = f"{FIXTURE_PREFIX}-second-decision"
REQUIRES_REVIEW_SUBMIT_KEY = f"{FIXTURE_PREFIX}-requires-review-submit"
REQUIRES_REVIEW_EXCEPTION_KEY = f"{FIXTURE_PREFIX}-requires-review-exception"
REQUIRES_REVIEW_DECISION_KEY = f"{FIXTURE_PREFIX}-requires-review-decision"

REVIEW_HISTORY_DOCTYPES = (
    "NPI Gate Review Cycle",
    "NPI Gate Review Record",
    "NPI Gate Review Exception",
    "NPI Gate Decision Snapshot",
    "NPI Gate Review Event",
)


def json_value(value: object) -> object:
    return json.loads(value) if isinstance(value, str) else value


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def review_bindings() -> list[dict[str, str]]:
    return [
        {
            "slot": slot,
            "memberGlobalId": evidence_runtime.OWNER_MEMBER_ID,
        }
        for slot in (
            REVIEW_SLOT,
            DECISION_SLOT,
            REOPEN_SLOT,
            EXCEPTION_SLOT,
        )
    ]


def repository_bindings() -> tuple[dict[str, str], ...]:
    return tuple(
        {
            "slot": str(value["slot"]),
            "member_global_id": str(value["memberGlobalId"]),
        }
        for value in review_bindings()
    )


def npi_request(
    opener,
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    csrf_token: str | None = None,
    idempotency_key: str | None = None,
) -> HttpResult:
    return evidence_runtime.npi_request(
        opener,
        base_url,
        path,
        method=method,
        payload=payload,
        csrf_token=csrf_token,
        idempotency_key=idempotency_key,
    )


def get_gate_review(
    opener,
    base_url: str,
    project_id: str,
    gate_id: str,
) -> HttpResult:
    return npi_request(
        opener,
        base_url,
        f"/api/npi/v1/projects/{project_id}/gates/{gate_id}/review",
    )


def reconcile_gate_review_command(
    opener,
    base_url: str,
    project_id: str,
    gate_id: str,
    operation: str,
    *,
    idempotency_key: str,
) -> HttpResult:
    return npi_request(
        opener,
        base_url,
        (
            f"/api/npi/v1/projects/{project_id}/gates/{gate_id}/"
            f"review-command-receipts/{operation}"
        ),
        idempotency_key=idempotency_key,
    )


def post_gate_command(
    opener,
    base_url: str,
    path: str,
    payload: dict[str, object],
    *,
    csrf_token: str,
    idempotency_key: str,
) -> HttpResult:
    return npi_request(
        opener,
        base_url,
        path,
        method="POST",
        payload=payload,
        csrf_token=csrf_token,
        idempotency_key=idempotency_key,
    )


def start_review(
    opener,
    base_url: str,
    project_id: str,
    gate_id: str,
    payload: dict[str, object],
    *,
    csrf_token: str,
    idempotency_key: str,
) -> HttpResult:
    return post_gate_command(
        opener,
        base_url,
        f"/api/npi/v1/projects/{project_id}/gates/{gate_id}:start-review",
        payload,
        csrf_token=csrf_token,
        idempotency_key=idempotency_key,
    )


def submit_review(
    opener,
    base_url: str,
    project_id: str,
    gate_id: str,
    cycle_id: str,
    payload: dict[str, object],
    *,
    csrf_token: str,
    idempotency_key: str,
) -> HttpResult:
    return post_gate_command(
        opener,
        base_url,
        (
            f"/api/npi/v1/projects/{project_id}/gates/{gate_id}/"
            f"review-cycles/{cycle_id}/reviews"
        ),
        payload,
        csrf_token=csrf_token,
        idempotency_key=idempotency_key,
    )


def request_exception(
    opener,
    base_url: str,
    project_id: str,
    gate_id: str,
    cycle_id: str,
    payload: dict[str, object],
    *,
    csrf_token: str,
    idempotency_key: str,
) -> HttpResult:
    return post_gate_command(
        opener,
        base_url,
        (
            f"/api/npi/v1/projects/{project_id}/gates/{gate_id}/"
            f"review-cycles/{cycle_id}/exceptions"
        ),
        payload,
        csrf_token=csrf_token,
        idempotency_key=idempotency_key,
    )


def decide_exception(
    opener,
    base_url: str,
    project_id: str,
    gate_id: str,
    cycle_id: str,
    exception_id: str,
    payload: dict[str, object],
    *,
    csrf_token: str,
    idempotency_key: str,
) -> HttpResult:
    return post_gate_command(
        opener,
        base_url,
        (
            f"/api/npi/v1/projects/{project_id}/gates/{gate_id}/"
            f"review-cycles/{cycle_id}/exceptions/{exception_id}:decide"
        ),
        payload,
        csrf_token=csrf_token,
        idempotency_key=idempotency_key,
    )


def decide_gate(
    opener,
    base_url: str,
    project_id: str,
    gate_id: str,
    payload: dict[str, object],
    *,
    csrf_token: str,
    idempotency_key: str,
) -> HttpResult:
    return post_gate_command(
        opener,
        base_url,
        f"/api/npi/v1/projects/{project_id}/gates/{gate_id}:decide",
        payload,
        csrf_token=csrf_token,
        idempotency_key=idempotency_key,
    )


def reopen_gate(
    opener,
    base_url: str,
    project_id: str,
    gate_id: str,
    payload: dict[str, object],
    *,
    csrf_token: str,
    idempotency_key: str,
) -> HttpResult:
    return post_gate_command(
        opener,
        base_url,
        f"/api/npi/v1/projects/{project_id}/gates/{gate_id}:reopen",
        payload,
        csrf_token=csrf_token,
        idempotency_key=idempotency_key,
    )


def require_workspace(
    result: HttpResult,
    *,
    expected_status: int,
    project_id: str,
    gate_id: str,
) -> dict[str, Any]:
    require(
        result.status == expected_status,
        f"Gate review workspace returned HTTP {result.status}",
    )
    body = result.body
    readiness = body.get("decisionReadiness") if isinstance(body, dict) else None
    exception_options = (
        body.get("exceptionRequestOptions") if isinstance(body, dict) else None
    )
    active_cycle = body.get("activeCycle") if isinstance(body, dict) else None
    decision_outcomes = {"pass", "conditional_pass", "reject"}
    decision_blocked_codes = {
        "REVIEW_CYCLE_CLOSED",
        "GATE_INPUT_CHANGED",
        "DECISION_AUTHORITY_REQUIRED",
        "REVIEWS_INCOMPLETE",
        "FILE_EVIDENCE_UNSAFE",
        "GATE_BLOCKED",
        "REQUIRED_P0_EVIDENCE_MISSING",
        "REQUIRED_EVIDENCE_MISSING",
        "EXCEPTION_NOT_REQUIRED",
        "APPROVED_EXCEPTION_REQUIRED",
    }
    require(
        isinstance(body, dict)
        and body.get("project", {}).get("globalId") == project_id
        and body.get("gate", {}).get("globalId") == gate_id
        and isinstance(body.get("evidence"), dict)
        and isinstance(body.get("decisions"), list)
        and all(
            isinstance(decision, dict)
            and set(decision)
            == {
                "globalId",
                "cycleGlobalId",
                "outcome",
                "inputHash",
                "snapshotHash",
                "decidedAt",
                "decidedBy",
                "current",
                "detail",
            }
            and isinstance(decision["detail"], dict)
            and set(decision["detail"])
            == {
                "lineageHash",
                "cycleNumber",
                "policyRef",
                "inputSnapshot",
                "reviewHashes",
                "exceptionHashes",
                "cycleVersion",
            }
            and isinstance(decision["detail"]["inputSnapshot"], dict)
            for decision in body["decisions"]
        )
        and isinstance(body.get("availablePolicies"), list)
        and isinstance(body.get("eligibleMembers"), list)
        and isinstance(body.get("eligibleClosureActions"), list)
        and isinstance(body.get("blockers"), list)
        and isinstance(readiness, dict)
        and set(readiness) == {"allowedOutcomes", "blockedReasons"}
        and isinstance(readiness["allowedOutcomes"], list)
        and set(readiness["allowedOutcomes"]) <= decision_outcomes
        and isinstance(readiness["blockedReasons"], list)
        and all(
            isinstance(reason, dict)
            and set(reason) == {"outcome", "code"}
            and reason["outcome"] in decision_outcomes
            and reason["code"] in decision_blocked_codes
            for reason in readiness["blockedReasons"]
        )
        and isinstance(exception_options, list)
        and all(
            isinstance(option, dict)
            and set(option)
            == {
                "requirementGlobalId",
                "requirementKey",
                "kind",
                "maximumValidityDays",
                "closureActionGlobalIds",
            }
            and isinstance(option["closureActionGlobalIds"], list)
            and bool(option["closureActionGlobalIds"])
            for option in exception_options
        )
        and (
            active_cycle is None
            or (
                isinstance(active_cycle, dict)
                and isinstance(active_cycle.get("exceptions"), list)
                and all(
                    isinstance(exception, dict)
                    and isinstance(exception.get("allowedOutcomes"), list)
                    and set(exception["allowedOutcomes"]) <= {"approved", "rejected"}
                    for exception in active_cycle["exceptions"]
                )
            )
        )
        and isinstance(body.get("permissions"), dict),
        "Gate review workspace projection is incomplete",
    )
    serialized = json.dumps(body, sort_keys=True)
    require(
        "/private/files/" not in serialized
        and '"fileUrl"' not in serialized
        and '"url"' not in serialized.casefold(),
        "Gate review workspace exposed a mutable file URL",
    )
    return body


def require_fresh_command(
    result: HttpResult,
    expected_status: int,
    label: str,
) -> dict[str, Any]:
    require(
        result.status == expected_status
        and result.headers.get("Idempotency-Replayed") == "false",
        f"{label} returned HTTP {result.status} or was unexpectedly replayed",
    )
    require(
        result.headers.get("Cache-Control") == "private, no-store",
        f"{label} cache control drifted",
    )
    return result.body


def require_replay(
    result: HttpResult,
    expected_status: int,
    expected_body: dict[str, Any],
    label: str,
) -> None:
    require(
        result.status == expected_status
        and result.headers.get("Idempotency-Replayed") == "true"
        and result.body == expected_body,
        f"{label} did not replay its complete sealed response",
    )


def enable_transport_role(
    administrator,
    base_url: str,
    csrf_token: str,
    user_id: str,
) -> None:
    updated = update_resource(
        administrator,
        base_url,
        "User",
        user_id,
        {
            "roles": [
                {"role": "Desk User"},
                {"role": "NPI API User"},
            ]
        },
        csrf_token,
    )
    roles = {
        str(value.get("role"))
        for value in updated.body.get("data", {}).get("roles", [])
        if isinstance(value, dict)
    }
    require(
        updated.status == 200
        and "NPI API User" in roles
        and "System Manager" not in roles,
        f"Fixture transport role assignment drifted: {user_id}",
    )


def ensure_review_policy(
    administrator,
    base_url: str,
    csrf_token: str,
    gate_template_hash: str,
) -> str:
    root = create_resource(
        administrator,
        base_url,
        "NPI Gate Review Policy",
        {
            "global_id": POLICY_ID,
            "policy_code": POLICY_CODE,
            "title": f"Synthetic {FIXTURE_NAMESPACE} Gate review policy",
            "enabled": 1,
        },
        csrf_token,
    )
    require(
        root.status in {200, 201},
        f"Gate Review Policy root returned HTTP {root.status}",
    )
    version = create_resource(
        administrator,
        base_url,
        "NPI Gate Review Policy Version",
        {
            "gate_review_policy": POLICY_ID,
            "policy_version": POLICY_VERSION,
            "title": f"Synthetic {FIXTURE_NAMESPACE} Gate review policy",
            "publication_state": "published",
            "gate_template_global_id": evidence_runtime.GATE_TEMPLATE_ID,
            "gate_template_version": evidence_runtime.GATE_TEMPLATE_VERSION,
            "gate_template_snapshot_hash": gate_template_hash,
            "review_steps": [
                {
                    "key": REVIEW_STEP_KEY,
                    "sequence": 1,
                    "authoritySlot": REVIEW_SLOT,
                    "activation": "always",
                    "activationPriority": None,
                }
            ],
            "decision_authority_slot": DECISION_SLOT,
            "reopen_authority_slot": REOPEN_SLOT,
            "exception_rules": [
                {
                    "kind": EXCEPTION_KIND,
                    "eligibleRequirementKeys": [evidence_runtime.REQUIREMENT_FILE],
                    "approvalAuthoritySlot": EXCEPTION_SLOT,
                    "maximumValidityDays": 60,
                    "requiredClosureActionKind": "action",
                }
            ],
            "dependency_evaluators": ["gate_input_snapshot"],
        },
        csrf_token,
    )
    data = version.body.get("data", {})
    snapshot_hash = data.get("snapshot_hash")
    require(
        version.status in {200, 201}
        and data.get("name") == POLICY_VERSION_KEY
        and data.get("publication_state") == "published"
        and data.get("optimistic_version") == 2
        and isinstance(snapshot_hash, str)
        and re.fullmatch(r"[a-f0-9]{64}", snapshot_hash) is not None,
        "Published Gate Review Policy identity or snapshot drifted",
    )
    return str(snapshot_hash)


def create_closure_action(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    project_id: str,
    gate_id: str,
    work_policy_ref: dict[str, object],
) -> str:
    result = npi_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}/domain-work-items",
        method="POST",
        payload={
            "expectedProjectVersion": 3,
            "workPolicyRef": work_policy_ref,
            "kind": "action",
            "title": "Close the controlled evidence timing exception",
            "detail": ("Synthetic action retained with the exact Gate review history."),
            "context": {
                "stageId": gate_id,
                "wbsItemId": evidence_runtime.MAIN_WBS_ID,
            },
            "ownerUserId": evidence_runtime.OWNER_USER,
            "dueAt": "2026-08-15T12:00:00Z",
            "severity": "medium",
            "blocking": False,
            "relatedWorkItemIds": [],
        },
        csrf_token=csrf_token,
        idempotency_key=ACTION_CREATE_KEY,
    )
    body = require_fresh_command(result, 201, "Closure action")
    action_id = body.get("globalId")
    require(
        isinstance(action_id, str)
        and body.get("projectId") == project_id
        and body.get("kind") == "action"
        and body.get("context", {}).get("stageId") == gate_id
        and body.get("blocking") is False
        and body.get("version") == 1,
        "Closure action projection drifted",
    )
    return action_id


def verify_fresh_fixture_namespace(
    administrator,
    base_url: str,
) -> dict[str, int]:
    base = evidence_runtime.verify_fresh_fixture_namespace(
        administrator,
        base_url,
    )
    for doctype, name in (
        ("NPI Gate Review Policy", POLICY_ID),
        ("NPI Gate Review Policy Version", POLICY_VERSION_KEY),
    ):
        require(
            get_resource(administrator, base_url, doctype, name).status == 404,
            f"Fresh P4-04 namespace already contains {doctype}: {name}",
        )
    require(
        list_resources(
            administrator,
            base_url,
            "NPI Engineering Project",
            filters=[["business_code", "=", WRONG_TENANT_BUSINESS_CODE]],
            fields=["global_id"],
        )
        == [],
        "Fresh P4-04 namespace already contains the tenant guard Project",
    )
    for actor, raw_key in (
        ("Administrator", ROLLBACK_START_KEY),
        ("Administrator", START_KEY),
        (evidence_runtime.OWNER_USER, REVIEW_KEY),
        (evidence_runtime.REVIEWER_USER, REVIEW_KEY),
        (evidence_runtime.REVIEWER_USER, EXCEPTION_REQUEST_KEY),
        (evidence_runtime.OWNER_USER, EXCEPTION_DECISION_KEY),
        (evidence_runtime.OWNER_USER, DECISION_KEY),
        (evidence_runtime.OWNER_USER, REOPEN_KEY),
        (evidence_runtime.OWNER_USER, SECOND_DECISION_KEY),
    ):
        rows = list_resources(
            administrator,
            base_url,
            "NPI Gate Review Idempotency",
            filters=[
                [
                    "actor_key_hash",
                    "=",
                    actor_key_hash(actor, raw_key),
                ]
            ],
            fields=["name"],
        )
        require(
            rows == [],
            f"Fresh P4-04 namespace contains Gate review idempotency: {raw_key}",
        )
    return {
        "baseNamedRecords": int(base["namedRecords"]),
        "reviewIdempotency": 9,
        "reviewPolicyRecords": 2,
        "tenantGuardProjects": 1,
    }


def same_unavailable_problem(first: HttpResult, second: HttpResult) -> None:
    validate_problem(first, 404, "GATE_UNAVAILABLE")
    validate_problem(second, 404, "GATE_UNAVAILABLE")
    for field in ("type", "title", "status", "code", "retryable"):
        require(
            first.body.get(field) == second.body.get(field),
            f"IDOR-safe Gate-unavailable field drifted: {field}",
        )


def verify_review_receipt(
    administrator,
    base_url: str,
    *,
    actor: str,
    raw_key: str,
    operation: str,
    project_id: str,
    gate_id: str,
) -> None:
    rows = list_resources(
        administrator,
        base_url,
        "NPI Gate Review Idempotency",
        filters=[
            ["actor_key_hash", "=", actor_key_hash(actor, raw_key)],
        ],
        fields=[
            "actor",
            "tenant_id",
            "project_global_id",
            "gate_global_id",
            "operation",
            "response_json",
            "response_sealed",
        ],
    )
    require(
        len(rows) == 1
        and rows[0]["actor"] == actor
        and rows[0]["tenant_id"] == TENANT_ID
        and rows[0]["project_global_id"] == project_id
        and rows[0]["gate_global_id"] == gate_id
        and rows[0]["operation"] == operation
        and rows[0]["response_sealed"] == 1
        and isinstance(json_value(rows[0]["response_json"]), dict),
        f"Gate review idempotency receipt drifted: {operation}",
    )


def require_command_receipt(
    result: HttpResult,
    *,
    operation: str,
    status: str,
) -> None:
    require(
        result.status == 200
        and result.headers.get("Cache-Control") == "private, no-store"
        and result.body
        == {
            "operation": operation,
            "status": status,
            "workspaceReloadRequired": True,
        },
        f"Gate review command reconciliation drifted: {operation}/{status}",
    )


def verify_immutable_history(
    administrator,
    base_url: str,
    csrf_token: str,
    targets: list[tuple[str, str, str, object]],
) -> int:
    denials = 0
    for doctype, name, fieldname, replacement in targets:
        before = get_resource(administrator, base_url, doctype, name)
        require(
            before.status == 200,
            f"Controlled Gate review history is unavailable: {doctype}/{name}",
        )
        update = update_resource(
            administrator,
            base_url,
            doctype,
            name,
            {fieldname: replacement},
            csrf_token,
        )
        require(
            update.status in {403, 417},
            f"{doctype} generic update returned HTTP {update.status}",
        )
        denials += 1
        deletion = delete_resource(
            administrator,
            base_url,
            doctype,
            name,
            csrf_token,
        )
        require(
            deletion.status in {403, 417},
            f"{doctype} generic delete returned HTTP {deletion.status}",
        )
        denials += 1
        after = get_resource(administrator, base_url, doctype, name)
        require(
            after.status == 200
            and after.body.get("data", {}).get(fieldname)
            == before.body.get("data", {}).get(fieldname),
            f"{doctype} immutable value changed after a denied write",
        )
    return denials


def _validated_runtime_site() -> None:
    import frappe

    require(
        frappe.local.site == SITE_NAME
        and frappe.conf.get("db_name") == DATABASE_NAME
        and frappe.conf.get("npi_tenant_id") == TENANT_ID
        and frappe.conf.get("npi_runtime_disposable_marker") == RUNTIME_MARKER,
        "Controlled local runtime Site identity drifted",
    )
    database_row = frappe.db.sql(
        "SELECT DATABASE(), CURRENT_USER(), @@port",
        as_list=True,
    )
    require(
        len(database_row) == 1
        and database_row[0][0] == DATABASE_NAME
        and str(database_row[0][1]).split("@", 1)[0] == DATABASE_USER
        and int(database_row[0][2]) == DATABASE_PORT,
        "Controlled local runtime database identity drifted",
    )


def verify_runtime_schema(fixture_run_id: str) -> dict[str, object]:
    import frappe

    _validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "Schema fixture namespace is invalid",
    )
    required_fields = {
        "NPI Gate Review Cycle": {
            "global_id",
            "state",
            "input_snapshot",
            "input_hash",
            "prior_cycle_global_id",
            "prior_decision_snapshot_global_id",
            "prior_decision_hash",
        },
        "NPI Gate Review Record": {
            "global_id",
            "record_snapshot",
            "record_snapshot_hash",
        },
        "NPI Gate Review Exception": {
            "global_id",
            "closure_action_version",
            "closure_action_snapshot_hash",
            "request_snapshot_hash",
            "decision_snapshot_hash",
        },
        "NPI Gate Decision Snapshot": {
            "global_id",
            "decision_snapshot",
            "snapshot_hash",
            "input_hash",
        },
        "NPI Gate Review Event": {
            "global_id",
            "event_type",
            "payload",
            "payload_hash",
        },
        "NPI Gate Review Idempotency": {
            "record_id",
            "actor",
            "actor_key_hash",
            "payload_hash",
            "response_json",
            "response_sealed",
        },
    }
    for doctype, fields in required_fields.items():
        require(
            frappe.db.table_exists(doctype),
            f"Migrated Gate review table is missing: {doctype}",
        )
        meta = frappe.get_meta(doctype)
        available = {str(field.fieldname) for field in meta.fields}
        require(
            fields <= available,
            f"Migrated Gate review fields are missing: {doctype}",
        )
    state_field = frappe.get_meta("NPI Gate Review Cycle").get_field("state")
    require(
        set(str(state_field.options).splitlines())
        == {"active", "decided", "invalidated", "superseded"},
        "Migrated Gate review cycle states drifted",
    )
    indexes = frappe.db.sql(
        "SHOW INDEX FROM `tabNPI Gate Review Idempotency`",
        as_dict=True,
    )
    require(
        any(
            str(row.get("Column_name")) == "actor_key_hash"
            and int(row.get("Non_unique")) == 0
            for row in indexes
        ),
        "Actor-bound Gate review idempotency uniqueness is missing",
    )
    return {
        "doctypes": len(required_fields),
        "idempotencyUnique": True,
        "states": sorted(str(state_field.options).splitlines()),
    }


def mark_wrong_tenant_project(
    fixture_run_id: str,
    project_id: str,
    gate_id: str,
) -> dict[str, str]:
    import frappe

    _validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "Tenant fixture namespace is invalid",
    )
    project = frappe.get_doc("NPI Engineering Project", project_id)
    gate = frappe.get_doc("NPI Gate Shell", gate_id)
    require(
        str(project.tenant_id) == TENANT_ID
        and str(project.global_id) == project_id
        and str(gate.project_global_id) == project_id
        and str(gate.global_id) == gate_id,
        "Tenant guard fixture scope drifted",
    )
    frappe.db.set_value(
        "NPI Engineering Project",
        project_id,
        "tenant_id",
        "other-runtime-tenant",
        update_modified=False,
    )
    frappe.db.commit()
    require(
        str(
            frappe.db.get_value(
                "NPI Engineering Project",
                project_id,
                "tenant_id",
            )
        )
        == "other-runtime-tenant",
        "Tenant guard fixture did not persist",
    )
    return {"gateId": gate_id, "projectId": project_id}


def verify_transaction_rollback(
    fixture_run_id: str,
    project_id: str,
    gate_id: str,
    policy_snapshot_hash: str,
    raw_idempotency_key: str,
) -> dict[str, object]:
    from unittest.mock import patch

    import frappe
    from npi_core.foundation.security import Principal
    from npi_core.gate_review.frappe_repository import FrappeGateReviewRepository

    _validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID and raw_idempotency_key == ROLLBACK_START_KEY,
        "Rollback fixture input is invalid",
    )
    gate_before = frappe.get_doc("NPI Gate Shell", gate_id)
    require(
        str(gate_before.project_global_id) == project_id
        and str(gate_before.review_state or "not_started") == "not_started"
        and not gate_before.current_review_cycle_global_id,
        "Rollback fixture Gate is not fresh",
    )
    repository = FrappeGateReviewRepository(
        principal=Principal(
            user_id="Administrator",
            roles=frozenset({"System Manager"}),
            project_access={},
            is_external=False,
            tenant_id=TENANT_ID,
        ),
        request_id=str(uuid4()),
        trace_id=f"trace-{uuid4().hex}",
    )
    injected = RuntimeError("synthetic rollback after idempotency insert")
    try:
        with patch.object(
            FrappeGateReviewRepository,
            "_insert_cycle",
            side_effect=injected,
        ):
            repository.start_review(
                UUID(project_id),
                UUID(gate_id),
                idempotency_key=actor_key_hash(
                    "Administrator",
                    raw_idempotency_key,
                ),
                expected_gate_version=int(gate_before.optimistic_version),
                policy_global_id=UUID(POLICY_ID),
                policy_version=POLICY_VERSION,
                policy_snapshot_hash=policy_snapshot_hash,
                bindings=repository_bindings(),
            )
    except RuntimeError as error:
        require(
            str(error) == str(injected),
            "Rollback fixture raised an unexpected error",
        )
        frappe.db.rollback()
    else:
        frappe.db.rollback()
        raise AssertionError("Rollback fixture did not inject its failure")

    gate_after = frappe.get_doc("NPI Gate Shell", gate_id)
    receipt = frappe.db.get_value(
        "NPI Gate Review Idempotency",
        {
            "actor_key_hash": actor_key_hash(
                "Administrator",
                raw_idempotency_key,
            )
        },
        "name",
    )
    cycles = frappe.get_all(
        "NPI Gate Review Cycle",
        filters={
            "project_global_id": project_id,
            "gate_global_id": gate_id,
        },
        pluck="name",
        limit_page_length=2,
    )
    require(
        receipt is None
        and cycles == []
        and int(gate_after.optimistic_version) == int(gate_before.optimistic_version)
        and str(gate_after.review_state or "not_started") == "not_started"
        and not gate_after.current_review_cycle_global_id,
        "Failed Gate review transaction left partial state",
    )
    return {
        "cycleCount": 0,
        "gateVersion": int(gate_after.optimistic_version),
        "receiptAbsent": True,
    }


def trigger_dependency_refresh(
    fixture_run_id: str,
    project_id: str,
    gate_id: str,
    source_global_id: str,
    expected_event_type: str,
    expected_old_state: str,
) -> dict[str, object]:
    import frappe
    from npi_core.gate_review.frappe_repository import (
        GATE_REVIEW_DEPENDENCY_SYSTEM_ACTOR,
        evaluate_gate_review_dependency,
    )

    _validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID
        and expected_event_type in {"invalidated", "refreshed"}
        and expected_old_state in {"active", "decided"},
        "Dependency fixture input is invalid",
    )
    gate = frappe.get_doc("NPI Gate Shell", gate_id)
    old_cycle_id = str(gate.current_review_cycle_global_id)
    old_cycle = frappe.get_doc("NPI Gate Review Cycle", old_cycle_id)
    require(
        str(old_cycle.state) == expected_old_state
        and str(old_cycle.project_global_id) == project_id,
        "Dependency fixture current cycle drifted",
    )
    references = frappe.get_all(
        "NPI Gate Evidence Reference",
        filters={
            "tenant_id": TENANT_ID,
            "project_global_id": project_id,
            "gate_global_id": gate_id,
            "source_object_type": "wbs_item",
            "source_global_id": source_global_id,
        },
        fields=[
            "global_id",
            "tenant_id",
            "project_global_id",
            "gate_global_id",
            "source_object_type",
            "source_global_id",
        ],
        limit_page_length=2,
    )
    require(len(references) == 1, "Exact dependency reference is unavailable")
    reference = references[0]

    previous_flag = getattr(
        frappe.flags,
        "npi_project_work_command_write",
        None,
    )
    frappe.flags.npi_project_work_command_write = True
    try:
        source = frappe.get_doc("NPI WBS Item", source_global_id)
        source.progress_percent = min(int(source.progress_percent) + 1, 99)
        source.save()
    finally:
        if previous_flag is None:
            delattr(frappe.flags, "npi_project_work_command_write")
        else:
            frappe.flags.npi_project_work_command_write = previous_flag

    refreshed = evaluate_gate_review_dependency(
        reference_id=str(reference.global_id),
        tenant_id=str(reference.tenant_id),
        project_id=str(reference.project_global_id),
        gate_id=str(reference.gate_global_id),
        source_kind=str(reference.source_object_type),
        source_global_id=str(reference.source_global_id),
        initiated_by_user_id=evidence_runtime.OWNER_USER,
    )
    require(refreshed is True, "Exact Gate dependency change did not refresh")
    frappe.db.commit()

    gate_after = frappe.get_doc("NPI Gate Shell", gate_id)
    successor_id = str(gate_after.current_review_cycle_global_id)
    prior = frappe.get_doc("NPI Gate Review Cycle", old_cycle_id)
    successor = frappe.get_doc("NPI Gate Review Cycle", successor_id)
    expected_prior_state = (
        "invalidated" if expected_old_state == "decided" else "superseded"
    )
    events = frappe.get_all(
        "NPI Gate Review Event",
        filters={
            "cycle_global_id": old_cycle_id,
            "successor_cycle_global_id": successor_id,
        },
        fields=[
            "global_id",
            "event_type",
            "actor_user_id",
            "action_global_id",
            "payload",
            "payload_hash",
        ],
        limit_page_length=2,
    )
    require(len(events) == 1, "Dependency refresh event is not unique")
    event = events[0]
    payload = json_value(event.payload)
    require(
        str(prior.state) == expected_prior_state
        and str(successor.prior_cycle_global_id) == old_cycle_id
        and str(successor.trigger) == "dependency_change"
        and str(successor.state) == "active"
        and str(event.event_type) == expected_event_type
        and str(event.actor_user_id) == GATE_REVIEW_DEPENDENCY_SYSTEM_ACTOR
        and event.action_global_id in (None, "")
        and isinstance(payload, dict)
        and payload.get("actionGlobalId") is None
        and canonical_hash(payload) == str(event.payload_hash),
        "Dependency invalidation lineage or nullable action reference drifted",
    )
    if expected_old_state == "decided":
        decision_id = str(uuid5(UUID(old_cycle_id), "decision-snapshot"))
        require(
            str(successor.prior_decision_snapshot_global_id) == decision_id
            and re.fullmatch(
                r"[a-f0-9]{64}",
                str(successor.prior_decision_hash),
            )
            is not None,
            "Decided dependency invalidation lost decision lineage",
        )
    else:
        require(
            str(successor.prior_decision_snapshot_global_id)
            == str(prior.prior_decision_snapshot_global_id)
            and str(successor.prior_decision_hash) == str(prior.prior_decision_hash),
            "Active dependency refresh did not carry prior decision lineage",
        )
    return {
        "actionId": None,
        "eventId": str(event.global_id),
        "eventType": str(event.event_type),
        "oldCycleId": old_cycle_id,
        "oldState": str(prior.state),
        "priorDecisionId": (
            str(successor.prior_decision_snapshot_global_id)
            if successor.prior_decision_snapshot_global_id
            else None
        ),
        "successorCycleId": successor_id,
    }


def verify_requires_review_command_rejections(
    fixture_run_id: str,
    project_id: str,
    gate_id: str,
    closure_action_id: str,
) -> dict[str, bool]:
    from datetime import UTC, datetime, timedelta

    import frappe
    from npi_core.foundation.errors import VersionConflict
    from npi_core.foundation.security import Principal
    from npi_core.gate_review.frappe_repository import FrappeGateReviewRepository

    _validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "Requires-review rejection fixture namespace is invalid",
    )
    gate = frappe.get_doc("NPI Gate Shell", gate_id)
    cycle = frappe.get_doc(
        "NPI Gate Review Cycle",
        str(gate.current_review_cycle_global_id),
    )
    closure_action = frappe.get_doc("NPI Domain Work Item", closure_action_id)
    snapshot = json_value(cycle.input_snapshot)
    require(
        str(gate.project_global_id) == project_id
        and str(gate.review_state) == "requires_review"
        and str(cycle.project_global_id) == project_id
        and str(cycle.gate_global_id) == gate_id
        and str(cycle.state) == "active"
        and isinstance(snapshot, dict)
        and str(closure_action.project_global_id) == project_id
        and str(closure_action.stage_global_id) == gate_id,
        "Requires-review rejection fixture scope drifted",
    )
    file_requirement = next(
        (
            value
            for value in snapshot.get("requirements", [])
            if isinstance(value, dict)
            and value.get("requirementKey") == evidence_runtime.REQUIREMENT_FILE
        ),
        None,
    )
    require(
        isinstance(file_requirement, dict)
        and isinstance(file_requirement.get("globalId"), str),
        "Requires-review rejection fixture lost its exception requirement",
    )

    def repository(actor: str) -> FrappeGateReviewRepository:
        return FrappeGateReviewRepository(
            principal=Principal(
                user_id=actor,
                roles=frozenset(),
                project_access={},
                is_external=False,
                tenant_id=TENANT_ID,
            ),
            request_id=str(uuid4()),
            trace_id=f"trace-{uuid4().hex}",
        )

    expected_gate_version = int(gate.optimistic_version)
    expected_cycle_version = int(cycle.optimistic_version)
    expected_input_hash = str(cycle.input_hash)
    attempts = (
        (
            "submit",
            lambda: repository(evidence_runtime.OWNER_USER).submit_review(
                UUID(project_id),
                UUID(gate_id),
                UUID(str(cycle.global_id)),
                idempotency_key=actor_key_hash(
                    evidence_runtime.OWNER_USER,
                    REQUIRES_REVIEW_SUBMIT_KEY,
                ),
                expected_cycle_version=expected_cycle_version,
                expected_input_hash=expected_input_hash,
                step_key=REVIEW_STEP_KEY,
                outcome="approved",
                opinion="This command must wait for explicit review revalidation.",
            ),
        ),
        (
            "exception",
            lambda: repository(evidence_runtime.REVIEWER_USER).request_exception(
                UUID(project_id),
                UUID(gate_id),
                UUID(str(cycle.global_id)),
                idempotency_key=actor_key_hash(
                    evidence_runtime.REVIEWER_USER,
                    REQUIRES_REVIEW_EXCEPTION_KEY,
                ),
                expected_cycle_version=expected_cycle_version,
                expected_input_hash=expected_input_hash,
                requirement_global_id=UUID(str(file_requirement["globalId"])),
                requirement_key=evidence_runtime.REQUIREMENT_FILE,
                kind=EXCEPTION_KIND,
                reason="This command must wait for explicit review revalidation.",
                risk="The refreshed review input has not been revalidated.",
                expires_at=datetime.now(UTC) + timedelta(days=30),
                closure_action_global_id=UUID(closure_action_id),
            ),
        ),
        (
            "decision",
            lambda: repository(evidence_runtime.OWNER_USER).decide_gate(
                UUID(project_id),
                UUID(gate_id),
                idempotency_key=actor_key_hash(
                    evidence_runtime.OWNER_USER,
                    REQUIRES_REVIEW_DECISION_KEY,
                ),
                expected_gate_version=expected_gate_version,
                expected_cycle_version=expected_cycle_version,
                expected_input_hash=expected_input_hash,
                outcome="reject",
            ),
        ),
    )
    accepted: list[str] = []
    unexpected: list[str] = []
    for label, command in attempts:
        try:
            command()
        except VersionConflict:
            pass
        except Exception as error:  # noqa: BLE001 - record every unexpected probe error
            unexpected.append(f"{label}:{type(error).__name__}")
        else:
            accepted.append(label)
        finally:
            # Each probe is intentionally disposable. A wrongly accepted command
            # must never alter the retained synthetic history used by later checks.
            frappe.db.rollback()
    require(
        not accepted and not unexpected,
        (
            "A requires-review Gate accepted a command before explicit "
            f"revalidation (accepted={accepted}, unexpected={unexpected})"
        ),
    )
    return {
        "decisionRejected": True,
        "exceptionRejected": True,
        "submitRejected": True,
    }


def verify_persisted_review_history(
    fixture_run_id: str,
    project_id: str,
    gate_id: str,
    rollback_raw_key: str,
) -> dict[str, object]:
    import frappe

    _validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID and rollback_raw_key == ROLLBACK_START_KEY,
        "Persistence fixture input is invalid",
    )
    cycle_names = frappe.get_all(
        "NPI Gate Review Cycle",
        filters={
            "tenant_id": TENANT_ID,
            "project_global_id": project_id,
            "gate_global_id": gate_id,
        },
        pluck="name",
        order_by="cycle_number asc",
        limit_page_length=5,
    )
    require(len(cycle_names) == 4, "Gate review cycle history count drifted")
    cycles = [frappe.get_doc("NPI Gate Review Cycle", name) for name in cycle_names]
    require(
        [int(value.cycle_number) for value in cycles] == [1, 2, 3, 4]
        and [str(value.state) for value in cycles]
        == ["invalidated", "invalidated", "superseded", "active"]
        and [str(value.trigger) for value in cycles]
        == [
            "manual_start",
            "manual_reopen",
            "dependency_change",
            "dependency_change",
        ],
        "Gate review cycle state history drifted",
    )
    for index, cycle in enumerate(cycles[1:], start=1):
        require(
            str(cycle.prior_cycle_global_id) == str(cycles[index - 1].global_id),
            "Gate review prior-cycle lineage drifted",
        )
    require(
        cycles[0].prior_decision_snapshot_global_id in (None, "")
        and cycles[1].prior_decision_snapshot_global_id
        == str(uuid5(UUID(str(cycles[0].global_id)), "decision-snapshot"))
        and cycles[2].prior_decision_snapshot_global_id
        == str(uuid5(UUID(str(cycles[1].global_id)), "decision-snapshot"))
        and cycles[3].prior_decision_snapshot_global_id
        == cycles[2].prior_decision_snapshot_global_id
        and cycles[3].prior_decision_hash == cycles[2].prior_decision_hash,
        "Gate review decision lineage drifted",
    )

    records = frappe.get_all(
        "NPI Gate Review Record",
        filters={"project_global_id": project_id, "gate_global_id": gate_id},
        pluck="name",
        limit_page_length=3,
    )
    exceptions = frappe.get_all(
        "NPI Gate Review Exception",
        filters={"project_global_id": project_id, "gate_global_id": gate_id},
        pluck="name",
        limit_page_length=3,
    )
    decisions = frappe.get_all(
        "NPI Gate Decision Snapshot",
        filters={"project_global_id": project_id, "gate_global_id": gate_id},
        pluck="name",
        order_by="cycle_number asc",
        limit_page_length=3,
    )
    events = frappe.get_all(
        "NPI Gate Review Event",
        filters={"project_global_id": project_id, "gate_global_id": gate_id},
        fields=["name", "event_type", "payload", "payload_hash"],
        order_by="occurred_at asc",
        limit_page_length=5,
    )
    require(
        len(records) == 1
        and len(exceptions) == 1
        and len(decisions) == 2
        and [str(value.event_type) for value in events]
        == ["exception_decided", "reopened", "invalidated", "refreshed"],
        "Gate review immutable history cardinality drifted",
    )
    sealed_documents: list[tuple[object, object]] = []
    record = frappe.get_doc("NPI Gate Review Record", records[0])
    exception = frappe.get_doc("NPI Gate Review Exception", exceptions[0])
    exception_request = json_value(exception.request_snapshot)
    require(
        isinstance(exception_request, dict)
        and exception_request.get("closureActionRef")
        == {
            "globalId": str(exception.closure_action_global_id),
            "version": int(exception.closure_action_version),
            "snapshotHash": str(exception.closure_action_snapshot_hash),
        },
        "Gate review exact closure action reference drifted",
    )
    sealed_documents.append((record.record_snapshot, record.record_snapshot_hash))
    sealed_documents.append(
        (exception.request_snapshot, exception.request_snapshot_hash)
    )
    sealed_documents.append(
        (exception.decision_snapshot, exception.decision_snapshot_hash)
    )
    for name in decisions:
        decision = frappe.get_doc("NPI Gate Decision Snapshot", name)
        sealed_documents.append((decision.decision_snapshot, decision.snapshot_hash))
    sealed_documents.extend((value.payload, value.payload_hash) for value in events)
    require(
        all(
            isinstance(json_value(payload), dict)
            and canonical_hash(json_value(payload)) == str(snapshot_hash)
            for payload, snapshot_hash in sealed_documents
        ),
        "Gate review immutable snapshot hash drifted",
    )

    receipts = frappe.get_all(
        "NPI Gate Review Idempotency",
        filters={
            "tenant_id": TENANT_ID,
            "project_global_id": project_id,
            "gate_global_id": gate_id,
        },
        fields=["actor", "operation", "response_json", "response_sealed"],
        limit_page_length=10,
    )
    require(
        len(receipts) == 7
        and all(
            int(value.response_sealed) == 1
            and isinstance(json_value(value.response_json), dict)
            for value in receipts
        )
        and {(str(value.actor), str(value.operation)) for value in receipts}
        == {
            ("Administrator", "gate.review.start"),
            (evidence_runtime.OWNER_USER, "gate.review.submit"),
            (
                evidence_runtime.REVIEWER_USER,
                "gate.review.exception.request",
            ),
            (
                evidence_runtime.OWNER_USER,
                "gate.review.exception.decide",
            ),
            (evidence_runtime.OWNER_USER, "gate.review.decide"),
            (evidence_runtime.OWNER_USER, "gate.review.reopen"),
        },
        "Gate review sealed idempotency history drifted",
    )
    require(
        frappe.db.get_value(
            "NPI Gate Review Idempotency",
            {
                "actor_key_hash": actor_key_hash(
                    "Administrator",
                    rollback_raw_key,
                )
            },
            "name",
        )
        is None
        and frappe.db.get_value(
            "NPI Gate Review Idempotency",
            {
                "actor_key_hash": actor_key_hash(
                    evidence_runtime.REVIEWER_USER,
                    REVIEW_KEY,
                )
            },
            "name",
        )
        is None,
        "Rejected or rolled-back Gate review command retained a receipt",
    )
    return {
        "cycles": len(cycles),
        "decisions": len(decisions),
        "events": [str(value.event_type) for value in events],
        "exceptions": len(exceptions),
        "receipts": len(receipts),
        "reviews": len(records),
    }


def run_bench_fixture(method: str, kwargs: dict[str, object]) -> dict[str, Any]:
    require(
        BENCH_PATH.is_dir()
        and not BENCH_PATH.is_symlink()
        and BENCH_PATH.resolve() == BENCH_PATH,
        "Runtime verifier requires the fixed physical repository Bench",
    )
    environment = os.environ.copy()
    current_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        str(ROOT)
        if not current_pythonpath
        else f"{ROOT}{os.pathsep}{current_pythonpath}"
    )
    completed = subprocess.run(
        [
            str(BENCH_PATH / "env" / "bin" / "python"),
            str(ROOT / "scripts" / "verify_gate_review_runtime.py"),
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
        (f"Controlled Bench fixture {method} failed: " f"{completed.stderr[-3000:]}"),
    )
    output = completed.stdout.strip().splitlines()
    require(bool(output), f"Controlled Bench fixture {method} returned no result")
    parsed = json.loads(output[-1])
    require(
        isinstance(parsed, dict),
        f"Controlled Bench fixture {method} result is invalid",
    )
    return parsed


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    fixtures = {
        "mark_wrong_tenant_project": mark_wrong_tenant_project,
        "trigger_dependency_refresh": trigger_dependency_refresh,
        "verify_persisted_review_history": verify_persisted_review_history,
        "verify_requires_review_command_rejections": (
            verify_requires_review_command_rejections
        ),
        "verify_runtime_schema": verify_runtime_schema,
        "verify_transaction_rollback": verify_transaction_rollback,
    }
    require(method in fixtures, "Controlled Bench fixture method is unavailable")
    require(
        BENCH_PATH.is_dir()
        and not BENCH_PATH.is_symlink()
        and BENCH_PATH.resolve() == BENCH_PATH,
        "Controlled Bench fixture requires the fixed physical repository Bench",
    )
    import frappe

    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    try:
        frappe.set_user("Administrator")
        result = fixtures[method](**kwargs)
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the real P4-04 Gate review runtime.",
    )
    parser.add_argument("--base-url")
    parser.add_argument(
        "--bench-fixture",
        choices=(
            "mark_wrong_tenant_project",
            "trigger_dependency_refresh",
            "verify_persisted_review_history",
            "verify_requires_review_command_rejections",
            "verify_runtime_schema",
            "verify_transaction_rollback",
        ),
    )
    parser.add_argument("--fixture-kwargs")
    arguments = parser.parse_args()
    if arguments.bench_fixture is not None:
        require(
            arguments.base_url is None and isinstance(arguments.fixture_kwargs, str),
            "Controlled Bench fixture arguments are invalid",
        )
        fixture_kwargs = json.loads(arguments.fixture_kwargs)
        require(
            isinstance(fixture_kwargs, dict),
            "Controlled Bench fixture kwargs must be an object",
        )
        run_local_bench_fixture(arguments.bench_fixture, fixture_kwargs)
        return
    require(
        isinstance(arguments.base_url, str) and arguments.fixture_kwargs is None,
        "The P4-04 runtime base URL is required",
    )
    require(
        CALLER_SUPPLIED_FIXTURE_RUN_ID is not None,
        f"{FIXTURE_RUN_ID_ENV} is required for a controlled runtime run",
    )

    administrator_user = "Administrator"
    administrator_password = secret_from_environment(
        "NPI_RUNTIME_ADMINISTRATOR_PASSWORD"
    )
    fixture_password = secret_from_environment("NPI_RUNTIME_FIXTURE_PASSWORD")
    for fixture_user in (
        evidence_runtime.OWNER_USER,
        evidence_runtime.REVIEWER_USER,
        evidence_runtime.UNRELATED_USER,
    ):
        validate_local_fixture_inputs(
            arguments.base_url,
            administrator_user,
            fixture_user,
        )

    administrator = login(
        arguments.base_url,
        administrator_user,
        administrator_password,
    )
    administrator_csrf = bootstrap_csrf(
        administrator,
        arguments.base_url,
        administrator_user,
    )
    fixture_absence = verify_fresh_fixture_namespace(
        administrator,
        arguments.base_url,
    )
    schema = run_bench_fixture(
        "verify_runtime_schema",
        {"fixture_run_id": FIXTURE_RUN_ID},
    )
    created_users: list[str] = []
    controlled_history_retained = False
    try:
        for user_id, label in (
            (evidence_runtime.OWNER_USER, "Authority"),
            (evidence_runtime.REVIEWER_USER, "Requester"),
            (evidence_runtime.UNRELATED_USER, "Transport only"),
        ):
            evidence_runtime.create_internal_user(
                administrator,
                arguments.base_url,
                user_id,
                fixture_password,
                administrator_csrf,
                label,
            )
            created_users.append(user_id)
            enable_transport_role(
                administrator,
                arguments.base_url,
                administrator_csrf,
                user_id,
            )

        authority = login(
            arguments.base_url,
            evidence_runtime.OWNER_USER,
            fixture_password,
        )
        requester = login(
            arguments.base_url,
            evidence_runtime.REVIEWER_USER,
            fixture_password,
        )
        transport_only = login(
            arguments.base_url,
            evidence_runtime.UNRELATED_USER,
            fixture_password,
        )
        authority_csrf = bootstrap_csrf(
            authority,
            arguments.base_url,
            evidence_runtime.OWNER_USER,
        )
        requester_csrf = bootstrap_csrf(
            requester,
            arguments.base_url,
            evidence_runtime.REVIEWER_USER,
        )
        bootstrap_csrf(
            transport_only,
            arguments.base_url,
            evidence_runtime.UNRELATED_USER,
        )

        gate_template_hash = evidence_runtime.ensure_gate_template(
            administrator,
            arguments.base_url,
            administrator_csrf,
        )
        evidence_runtime.ensure_project_template(
            administrator,
            arguments.base_url,
            administrator_csrf,
            gate_template_hash,
        )
        project_id, gate_id = evidence_runtime.create_project(
            administrator,
            arguments.base_url,
            administrator_csrf,
            owner_user_id=evidence_runtime.OWNER_USER,
            business_code=evidence_runtime.BUSINESS_CODE,
            title=f"Synthetic {FIXTURE_NAMESPACE} Gate review Project",
            idempotency_key=evidence_runtime.PROJECT_CREATE_KEY,
        )
        controlled_history_retained = True
        _cross_project_id, cross_gate_id = evidence_runtime.create_project(
            administrator,
            arguments.base_url,
            administrator_csrf,
            owner_user_id=evidence_runtime.OWNER_USER,
            business_code=evidence_runtime.CROSS_BUSINESS_CODE,
            title=f"Synthetic {FIXTURE_NAMESPACE} cross-Project Gate",
            idempotency_key=evidence_runtime.CROSS_PROJECT_CREATE_KEY,
        )
        wrong_project_id, wrong_gate_id = evidence_runtime.create_project(
            administrator,
            arguments.base_url,
            administrator_csrf,
            owner_user_id=evidence_runtime.OWNER_USER,
            business_code=WRONG_TENANT_BUSINESS_CODE,
            title=f"Synthetic {FIXTURE_NAMESPACE} tenant guard Gate",
            idempotency_key=WRONG_PROJECT_CREATE_KEY,
        )
        run_bench_fixture(
            "mark_wrong_tenant_project",
            {
                "fixture_run_id": FIXTURE_RUN_ID,
                "gate_id": wrong_gate_id,
                "project_id": wrong_project_id,
            },
        )

        work_policy_ref = evidence_runtime.ensure_work_policy(
            administrator,
            arguments.base_url,
            administrator_csrf,
        )
        evidence_runtime.configure_team(
            administrator,
            arguments.base_url,
            project_id,
            work_policy_ref,
            administrator_csrf,
        )
        evidence_runtime.apply_plan(
            administrator,
            arguments.base_url,
            project_id,
            work_policy_ref,
            administrator_csrf,
            expected_version=2,
            item_id=evidence_runtime.MAIN_WBS_ID,
            code="1.10",
            title="Synthetic exact Gate review work",
            owner_role_id=evidence_runtime.OWNER_ROLE_ID,
            idempotency_key=evidence_runtime.MAIN_PLAN_KEY,
        )
        closure_action_id = create_closure_action(
            administrator,
            arguments.base_url,
            administrator_csrf,
            project_id=project_id,
            gate_id=gate_id,
            work_policy_ref=work_policy_ref,
        )
        main_wbs_version, main_wbs_hash = evidence_runtime.exact_wbs(
            administrator,
            arguments.base_url,
            evidence_runtime.MAIN_WBS_ID,
        )

        freeze = evidence_runtime.freeze_requirements(
            administrator,
            arguments.base_url,
            project_id,
            gate_id,
            evidence_runtime.freeze_payload(),
            csrf_token=administrator_csrf,
            idempotency_key=evidence_runtime.FREEZE_KEY,
        )
        require(
            freeze.status == 200
            and freeze.headers.get("Idempotency-Replayed") == "false",
            f"Gate requirement freeze returned HTTP {freeze.status}",
        )
        wbs_attach = evidence_runtime.attach_evidence(
            administrator,
            arguments.base_url,
            project_id,
            gate_id,
            evidence_runtime.REQUIREMENT_WBS,
            {
                "expectedGateVersion": 2,
                "evidenceKind": "wbs_item",
                "sourceGlobalId": evidence_runtime.MAIN_WBS_ID,
                "sourceVersion": main_wbs_version,
                "sourceHash": main_wbs_hash,
            },
            csrf_token=administrator_csrf,
            idempotency_key=evidence_runtime.WBS_ATTACH_KEY,
        )
        require(
            wbs_attach.status == 201
            and wbs_attach.headers.get("Idempotency-Replayed") == "false",
            f"Gate review WBS evidence returned HTTP {wbs_attach.status}",
        )
        policy_snapshot_hash = ensure_review_policy(
            administrator,
            arguments.base_url,
            administrator_csrf,
            gate_template_hash,
        )

        initial = get_gate_review(
            administrator,
            arguments.base_url,
            project_id,
            gate_id,
        )
        initial_body = require_workspace(
            initial,
            expected_status=200,
            project_id=project_id,
            gate_id=gate_id,
        )
        policies = initial_body["availablePolicies"]
        require(
            initial_body["gate"]["reviewState"] == "not_started"
            and initial_body["gate"]["version"] == 3
            and initial_body["activeCycle"] is None
            and initial_body["blockers"] == []
            and len(policies) == 1
            and policies[0]["policyRef"]
            == {
                "globalId": POLICY_ID,
                "version": POLICY_VERSION,
                "snapshotHash": policy_snapshot_hash,
            }
            and {value["slot"] for value in policies[0]["authoritySlots"]}
            == {REVIEW_SLOT, DECISION_SLOT, REOPEN_SLOT, EXCEPTION_SLOT},
            "Initial Gate review policy workspace drifted",
        )

        rollback = run_bench_fixture(
            "verify_transaction_rollback",
            {
                "fixture_run_id": FIXTURE_RUN_ID,
                "gate_id": gate_id,
                "policy_snapshot_hash": policy_snapshot_hash,
                "project_id": project_id,
                "raw_idempotency_key": ROLLBACK_START_KEY,
            },
        )
        require(
            rollback
            == {
                "cycleCount": 0,
                "gateVersion": 3,
                "receiptAbsent": True,
            },
            "Gate review transaction rollback evidence drifted",
        )

        random_unavailable = get_gate_review(
            administrator,
            arguments.base_url,
            str(uuid4()),
            str(uuid4()),
        )
        cross_unavailable = get_gate_review(
            requester,
            arguments.base_url,
            project_id,
            cross_gate_id,
        )
        wrong_tenant_unavailable = get_gate_review(
            administrator,
            arguments.base_url,
            wrong_project_id,
            wrong_gate_id,
        )
        same_unavailable_problem(cross_unavailable, random_unavailable)
        same_unavailable_problem(
            wrong_tenant_unavailable,
            random_unavailable,
        )
        transport_unavailable = get_gate_review(
            transport_only,
            arguments.base_url,
            project_id,
            gate_id,
        )
        same_unavailable_problem(
            transport_unavailable,
            random_unavailable,
        )
        guest = get_gate_review(
            urllib.request.build_opener(),
            arguments.base_url,
            project_id,
            gate_id,
        )
        validate_problem(guest, 401, "AUTHENTICATION_REQUIRED")

        start_payload: dict[str, object] = {
            "expectedGateVersion": 3,
            "policyGlobalId": POLICY_ID,
            "policyVersion": POLICY_VERSION,
            "policySnapshotHash": policy_snapshot_hash,
            "bindings": review_bindings(),
        }
        started = start_review(
            administrator,
            arguments.base_url,
            project_id,
            gate_id,
            start_payload,
            csrf_token=administrator_csrf,
            idempotency_key=START_KEY,
        )
        started_body = require_fresh_command(started, 201, "Gate review start")
        cycle = started_body.get("activeCycle")
        require(
            isinstance(cycle, dict)
            and started_body.get("gate", {}).get("reviewState") == "in_review"
            and started_body.get("gate", {}).get("version") == 4
            and cycle.get("number") == 1
            and cycle.get("state") == "active"
            and cycle.get("version") == 1
            and cycle.get("policyRef")
            == {
                "globalId": POLICY_ID,
                "version": POLICY_VERSION,
                "snapshotHash": policy_snapshot_hash,
            }
            and len(cycle.get("selectedSteps", [])) == 1,
            "Started Gate review cycle drifted",
        )
        cycle_id = str(cycle["globalId"])
        input_hash = str(cycle["inputHash"])
        start_replay = start_review(
            administrator,
            arguments.base_url,
            project_id,
            gate_id,
            start_payload,
            csrf_token=administrator_csrf,
            idempotency_key=START_KEY,
        )
        require_replay(start_replay, 201, started_body, "Gate review start")
        changed_start = dict(start_payload)
        changed_start["expectedGateVersion"] = 4
        start_conflict = start_review(
            administrator,
            arguments.base_url,
            project_id,
            gate_id,
            changed_start,
            csrf_token=administrator_csrf,
            idempotency_key=START_KEY,
        )
        validate_problem(start_conflict, 409, "IDEMPOTENCY_KEY_CONFLICT")

        review_payload = {
            "expectedCycleVersion": 1,
            "expectedInputHash": input_hash,
            "stepKey": REVIEW_STEP_KEY,
            "outcome": "approved",
            "opinion": "Approved against the exact frozen Gate input.",
        }
        role_only_denied = submit_review(
            requester,
            arguments.base_url,
            project_id,
            gate_id,
            cycle_id,
            review_payload,
            csrf_token=requester_csrf,
            idempotency_key=REVIEW_KEY,
        )
        validate_problem(role_only_denied, 403, "PERMISSION_DENIED")
        manager_transport_denied = submit_review(
            administrator,
            arguments.base_url,
            project_id,
            gate_id,
            cycle_id,
            review_payload,
            csrf_token=administrator_csrf,
            idempotency_key=ADMIN_REVIEW_DENIED_KEY,
        )
        validate_problem(manager_transport_denied, 403, "PERMISSION_DENIED")

        reviewed = submit_review(
            authority,
            arguments.base_url,
            project_id,
            gate_id,
            cycle_id,
            review_payload,
            csrf_token=authority_csrf,
            idempotency_key=REVIEW_KEY,
        )
        reviewed_body = require_fresh_command(
            reviewed,
            201,
            "Gate review opinion",
        )
        reviewed_cycle = reviewed_body["activeCycle"]
        review_record = reviewed_cycle["selectedSteps"][0]["review"]
        require(
            reviewed_cycle["version"] == 2
            and review_record["actor"] == evidence_runtime.OWNER_USER
            and review_record["inputHash"] == input_hash
            and review_record["outcome"] == "approved"
            and re.fullmatch(
                r"[a-f0-9]{64}",
                str(review_record["snapshotHash"]),
            )
            is not None,
            "Authorized Gate review record drifted",
        )
        review_id = str(review_record["globalId"])
        review_replay = submit_review(
            authority,
            arguments.base_url,
            project_id,
            gate_id,
            cycle_id,
            review_payload,
            csrf_token=authority_csrf,
            idempotency_key=REVIEW_KEY,
        )
        require_replay(
            review_replay,
            201,
            reviewed_body,
            "Gate review opinion",
        )
        changed_review = dict(review_payload)
        changed_review["opinion"] = "This changed payload must not replay."
        review_conflict = submit_review(
            authority,
            arguments.base_url,
            project_id,
            gate_id,
            cycle_id,
            changed_review,
            csrf_token=authority_csrf,
            idempotency_key=REVIEW_KEY,
        )
        validate_problem(review_conflict, 409, "IDEMPOTENCY_KEY_CONFLICT")
        verify_review_receipt(
            administrator,
            arguments.base_url,
            actor=evidence_runtime.OWNER_USER,
            raw_key=REVIEW_KEY,
            operation="gate.review.submit",
            project_id=project_id,
            gate_id=gate_id,
        )
        require_command_receipt(
            reconcile_gate_review_command(
                authority,
                arguments.base_url,
                project_id,
                gate_id,
                "gate.review.submit",
                idempotency_key=REVIEW_KEY,
            ),
            operation="gate.review.submit",
            status="completed",
        )

        file_requirement = next(
            value
            for value in reviewed_body["evidence"]["requirements"]
            if value["key"] == evidence_runtime.REQUIREMENT_FILE
        )
        exception_payload = {
            "expectedCycleVersion": 2,
            "expectedInputHash": input_hash,
            "requirementGlobalId": file_requirement["globalId"],
            "requirementKey": evidence_runtime.REQUIREMENT_FILE,
            "kind": EXCEPTION_KIND,
            "reason": "The controlled file will arrive after this decision.",
            "risk": "The evidence remains incomplete until the action closes.",
            "expiresAt": "2026-08-31T12:00:00Z",
            "closureActionGlobalId": closure_action_id,
        }
        exception_requested = request_exception(
            requester,
            arguments.base_url,
            project_id,
            gate_id,
            cycle_id,
            exception_payload,
            csrf_token=requester_csrf,
            idempotency_key=EXCEPTION_REQUEST_KEY,
        )
        exception_body = require_fresh_command(
            exception_requested,
            201,
            "Gate review exception request",
        )
        exception_cycle = exception_body["activeCycle"]
        exception = exception_cycle["exceptions"][0]
        require(
            exception_cycle["version"] == 3
            and exception["state"] == "pending"
            and exception["requester"]["userId"] == evidence_runtime.REVIEWER_USER
            and exception["closureActionRef"]["globalId"] == closure_action_id
            and exception["closureActionRef"]["version"] == 1
            and re.fullmatch(
                r"[a-f0-9]{64}",
                str(exception["closureActionRef"]["snapshotHash"]),
            )
            is not None
            and exception["decision"] is None,
            "Gate review exception request drifted",
        )
        exception_id = str(exception["globalId"])

        exception_decided = decide_exception(
            authority,
            arguments.base_url,
            project_id,
            gate_id,
            cycle_id,
            exception_id,
            {
                "expectedCycleVersion": 3,
                "expectedExceptionVersion": 1,
                "expectedInputHash": input_hash,
                "outcome": "approved",
                "opinion": "Approved with the exact retained closure action.",
            },
            csrf_token=authority_csrf,
            idempotency_key=EXCEPTION_DECISION_KEY,
        )
        exception_decided_body = require_fresh_command(
            exception_decided,
            200,
            "Gate review exception decision",
        )
        decided_exception = exception_decided_body["activeCycle"]["exceptions"][0]
        require(
            exception_decided_body["activeCycle"]["version"] == 4
            and decided_exception["state"] == "approved"
            and decided_exception["version"] == 2
            and decided_exception["decision"]["approver"]["userId"]
            == evidence_runtime.OWNER_USER,
            "Gate review exception decision drifted",
        )

        gate_decided = decide_gate(
            authority,
            arguments.base_url,
            project_id,
            gate_id,
            {
                "expectedGateVersion": 4,
                "expectedCycleVersion": 4,
                "expectedInputHash": input_hash,
                "outcome": "conditional_pass",
            },
            csrf_token=authority_csrf,
            idempotency_key=DECISION_KEY,
        )
        gate_decided_body = require_fresh_command(
            gate_decided,
            200,
            "Gate decision",
        )
        first_decision = gate_decided_body["decisions"][0]
        require(
            gate_decided_body["gate"]["reviewState"] == "decided"
            and gate_decided_body["gate"]["version"] == 5
            and gate_decided_body["gate"]["downstreamDecisionCurrent"] is True
            and gate_decided_body["activeCycle"]["state"] == "decided"
            and gate_decided_body["activeCycle"]["version"] == 5
            and first_decision["cycleGlobalId"] == cycle_id
            and first_decision["outcome"] == "conditional_pass"
            and first_decision["current"] is True
            and first_decision["detail"]["cycleNumber"] == 1
            and first_decision["detail"]["inputSnapshot"]["gateGlobalId"] == gate_id
            and first_decision["detail"]["policyRef"]
            == {
                "globalId": POLICY_ID,
                "version": POLICY_VERSION,
                "snapshotHash": policy_snapshot_hash,
            }
            and re.fullmatch(
                r"[a-f0-9]{64}",
                str(first_decision["detail"]["lineageHash"]),
            )
            is not None,
            "Gate decision snapshot drifted",
        )
        first_decision_id = str(first_decision["globalId"])

        reopened = reopen_gate(
            authority,
            arguments.base_url,
            project_id,
            gate_id,
            {
                "expectedGateVersion": 5,
                "expectedCycleVersion": 5,
                "expectedInputHash": input_hash,
                "reason": "A controlled follow-up review is required.",
                "policyGlobalId": POLICY_ID,
                "policyVersion": POLICY_VERSION,
                "policySnapshotHash": policy_snapshot_hash,
                "bindings": review_bindings(),
            },
            csrf_token=authority_csrf,
            idempotency_key=REOPEN_KEY,
        )
        reopened_body = require_fresh_command(
            reopened,
            201,
            "Gate reopen",
        )
        second_cycle = reopened_body["activeCycle"]
        require(
            reopened_body["gate"]["reviewState"] == "in_review"
            and reopened_body["gate"]["version"] == 6
            and reopened_body["gate"]["downstreamDecisionCurrent"] is False
            and second_cycle["number"] == 2
            and second_cycle["trigger"] == "manual_reopen"
            and second_cycle["state"] == "active"
            and second_cycle["version"] == 1
            and all(value["review"] is None for value in second_cycle["selectedSteps"])
            and reopened_body["decisions"][0]["current"] is False,
            "Gate reopen did not preserve decision history cleanly",
        )
        second_cycle_id = str(second_cycle["globalId"])

        second_decision_result = decide_gate(
            authority,
            arguments.base_url,
            project_id,
            gate_id,
            {
                "expectedGateVersion": 6,
                "expectedCycleVersion": 1,
                "expectedInputHash": str(second_cycle["inputHash"]),
                "outcome": "reject",
            },
            csrf_token=authority_csrf,
            idempotency_key=SECOND_DECISION_KEY,
        )
        second_decision_body = require_fresh_command(
            second_decision_result,
            200,
            "Second Gate decision",
        )
        require(
            second_decision_body["gate"]["reviewState"] == "decided"
            and second_decision_body["gate"]["version"] == 7
            and second_decision_body["activeCycle"]["state"] == "decided"
            and second_decision_body["activeCycle"]["version"] == 2
            and len(second_decision_body["decisions"]) == 2,
            "Second Gate decision drifted",
        )
        second_decision = next(
            value
            for value in second_decision_body["decisions"]
            if value["cycleGlobalId"] == second_cycle_id
        )
        second_decision_id = str(second_decision["globalId"])

        decided_refresh = run_bench_fixture(
            "trigger_dependency_refresh",
            {
                "expected_event_type": "invalidated",
                "expected_old_state": "decided",
                "fixture_run_id": FIXTURE_RUN_ID,
                "gate_id": gate_id,
                "project_id": project_id,
                "source_global_id": evidence_runtime.MAIN_WBS_ID,
            },
        )
        require(
            decided_refresh["oldCycleId"] == second_cycle_id
            and decided_refresh["oldState"] == "invalidated"
            and decided_refresh["priorDecisionId"] == second_decision_id,
            "Decided dependency invalidation evidence drifted",
        )
        active_refresh = run_bench_fixture(
            "trigger_dependency_refresh",
            {
                "expected_event_type": "refreshed",
                "expected_old_state": "active",
                "fixture_run_id": FIXTURE_RUN_ID,
                "gate_id": gate_id,
                "project_id": project_id,
                "source_global_id": evidence_runtime.MAIN_WBS_ID,
            },
        )
        require(
            active_refresh["oldCycleId"] == decided_refresh["successorCycleId"]
            and active_refresh["oldState"] == "superseded"
            and active_refresh["priorDecisionId"] == second_decision_id,
            "Active dependency refresh evidence drifted",
        )
        refreshed_workspace = require_workspace(
            get_gate_review(
                authority,
                arguments.base_url,
                project_id,
                gate_id,
            ),
            expected_status=200,
            project_id=project_id,
            gate_id=gate_id,
        )
        require(
            refreshed_workspace["gate"]["reviewState"] == "requires_review"
            and refreshed_workspace["gate"]["downstreamDecisionCurrent"] is False
            and refreshed_workspace["activeCycle"]["globalId"]
            == active_refresh["successorCycleId"]
            and refreshed_workspace["activeCycle"]["number"] == 4
            and refreshed_workspace["activeCycle"]["state"] == "active"
            and refreshed_workspace["activeCycle"]["trigger"] == "dependency_change"
            and refreshed_workspace["blockers"] == initial_body["blockers"] == []
            and {
                value["eventGlobalId"]
                for value in refreshed_workspace["dependencyChanges"]
            }
            == {decided_refresh["eventId"], active_refresh["eventId"]}
            and all(
                value["impactActionGlobalId"] is None
                for value in refreshed_workspace["dependencyChanges"]
            ),
            "Dependency-refreshed Gate workspace drifted",
        )
        requires_review_rejections = run_bench_fixture(
            "verify_requires_review_command_rejections",
            {
                "closure_action_id": closure_action_id,
                "fixture_run_id": FIXTURE_RUN_ID,
                "gate_id": gate_id,
                "project_id": project_id,
            },
        )

        events = list_resources(
            administrator,
            arguments.base_url,
            "NPI Gate Review Event",
            filters=[
                ["project_global_id", "=", project_id],
                ["gate_global_id", "=", gate_id],
            ],
            fields=["global_id", "event_type"],
        )
        event_ids = {
            str(value["event_type"]): str(value["global_id"]) for value in events
        }
        require(
            set(event_ids)
            == {
                "exception_decided",
                "reopened",
                "invalidated",
                "refreshed",
            },
            "Gate review transition event history drifted",
        )
        immutable_denials = verify_immutable_history(
            administrator,
            arguments.base_url,
            administrator_csrf,
            [
                (
                    "NPI Gate Review Record",
                    review_id,
                    "opinion",
                    "MUST NOT CHANGE",
                ),
                (
                    "NPI Gate Review Exception",
                    exception_id,
                    "reason",
                    "MUST NOT CHANGE",
                ),
                (
                    "NPI Gate Decision Snapshot",
                    first_decision_id,
                    "outcome",
                    "reject",
                ),
                (
                    "NPI Gate Review Cycle",
                    second_cycle_id,
                    "state",
                    "active",
                ),
                (
                    "NPI Gate Review Event",
                    event_ids["invalidated"],
                    "event_type",
                    "refreshed",
                ),
            ],
        )
        persisted = run_bench_fixture(
            "verify_persisted_review_history",
            {
                "fixture_run_id": FIXTURE_RUN_ID,
                "gate_id": gate_id,
                "project_id": project_id,
                "rollback_raw_key": ROLLBACK_START_KEY,
            },
        )

        print(
            json.dumps(
                {
                    "activeDependencyRefresh": active_refresh,
                    "actorBoundReplayConflict": True,
                    "boundedCleanup": {
                        "controlledHistoryRetained": True,
                        "unreferencedTransportUserRemoved": True,
                    },
                    "crossProjectTenantNonDisclosure": 404,
                    "decidedDependencyInvalidation": decided_refresh,
                    "fixtureAbsenceBeforeWrite": fixture_absence,
                    "fixtureRevision": FIXTURE_REVISION,
                    "fixtureRunId": FIXTURE_RUN_ID,
                    "happyPath": [
                        "start",
                        "review",
                        "exception_request",
                        "exception_decision",
                        "decision",
                        "reopen",
                    ],
                    "immutableWriteDenials": immutable_denials,
                    "persistedHistory": persisted,
                    "requiresReviewCommandRejections": (requires_review_rejections),
                    "roleIsNotApproval": True,
                    "schema": schema,
                    "transactionRollback": rollback,
                },
                sort_keys=True,
            )
        )
    finally:
        cleanup = login(
            arguments.base_url,
            administrator_user,
            administrator_password,
        )
        cleanup_csrf = bootstrap_csrf(
            cleanup,
            arguments.base_url,
            administrator_user,
        )
        retained_projects = any(
            list_resources(
                cleanup,
                arguments.base_url,
                "NPI Engineering Project",
                filters=[["business_code", "=", business_code]],
                fields=["global_id"],
            )
            for business_code in (
                evidence_runtime.BUSINESS_CODE,
                evidence_runtime.CROSS_BUSINESS_CODE,
                WRONG_TENANT_BUSINESS_CODE,
            )
        )
        evidence_runtime.cleanup_runtime_users(
            cleanup,
            arguments.base_url,
            cleanup_csrf,
            created_users,
            retain_controlled_history=(
                controlled_history_retained or retained_projects
            ),
        )

    print("local Frappe Gate review runtime verification passed")


if __name__ == "__main__":
    main()
