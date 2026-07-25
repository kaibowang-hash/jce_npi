from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from verify_frappe_runtime import (
    HttpResult,
    delete_disposable_user,
    login,
    request,
    require,
    secret_from_environment,
    user_resource_path,
    validate_local_fixture_inputs,
    validate_problem,
)
from verify_project_runtime import (
    TENANT_ID,
    actor_key_hash,
    bootstrap_csrf,
    create_resource,
    get_resource,
    list_resources,
    update_resource,
)


FIXTURE_REVISION = 1
FIXTURE_RUN_ID_ENV = "NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID"
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
# Reuse the exact P4-03/P4-04 fixture builders in this caller-owned namespace.
# The two prerequisite modules validate the same controlled Site and derive
# every identity from these environment values.
os.environ.setdefault("NPI_GATE_EVIDENCE_RUNTIME_RUN_ID", FIXTURE_RUN_ID)
os.environ.setdefault("NPI_GATE_REVIEW_RUNTIME_RUN_ID", FIXTURE_RUN_ID)

import verify_gate_evidence_runtime as evidence_runtime  # noqa: E402
import verify_gate_review_runtime as review_runtime  # noqa: E402


def fixture_id(scope: str) -> str:
    return str(
        uuid5(
            NAMESPACE_URL,
            (
                "https://npi-one.example.invalid/runtime/p4-05/"
                f"{FIXTURE_NAMESPACE}/{scope}"
            ),
        )
    )


FIXTURE_PREFIX = f"p4-05-runtime-{FIXTURE_NAMESPACE}"
BUSINESS_PREFIX = f"P4-05-{FIXTURE_RUN_ID[:16].upper()}"
MAIN_BUSINESS_CODE = f"{BUSINESS_PREFIX}-MAIN"
TERMINAL_BUSINESS_CODE = f"{BUSINESS_PREFIX}-TERMINAL"
TENANT_GUARD_BUSINESS_CODE = f"{BUSINESS_PREFIX}-TENANT"

CONTROL_POLICY_ID = fixture_id("project-control-policy")
CONTROL_POLICY_VERSION = 1
CONTROL_POLICY_VERSION_KEY = f"{CONTROL_POLICY_ID}:{CONTROL_POLICY_VERSION}"
CONTROL_POLICY_CODE = f"p405-{FIXTURE_RUN_ID[:16]}"
CONTROLLER_SLOT = "project_controller"
SPONSOR_SLOT = "project_sponsor"

TERMINAL_OWNER_MEMBER_ID = fixture_id("terminal-member-owner")
TERMINAL_REVIEWER_MEMBER_ID = fixture_id("terminal-member-reviewer")
TERMINAL_OWNER_ROLE_ID = fixture_id("terminal-role-owner")
TERMINAL_RACI_ID = fixture_id("terminal-raci-project")
TERMINAL_WBS_ID = fixture_id("terminal-wbs")
TERMINAL_MY_WORK_DOMAIN_SOURCE_ID = fixture_id("terminal-my-work-domain-source")

WORK_ITEM_KEYS = {
    "risk": f"{FIXTURE_PREFIX}-work-risk",
    "action": f"{FIXTURE_PREFIX}-work-action",
    "decision_request": f"{FIXTURE_PREFIX}-work-decision",
}
MAIN_BIND_KEY = f"{FIXTURE_PREFIX}-main-bind"
TERMINAL_BIND_KEY = f"{FIXTURE_PREFIX}-terminal-bind"
HEALTH_REJECTED_KEY = f"{FIXTURE_PREFIX}-health-red-rejected"
HEALTH_KEY = f"{FIXTURE_PREFIX}-health-red"
PAUSE_KEY = f"{FIXTURE_PREFIX}-pause"
RESUME_KEY = f"{FIXTURE_PREFIX}-resume"
COMPLETE_REJECTED_KEY = f"{FIXTURE_PREFIX}-complete-rejected"
TERMINAL_CANCEL_KEY = f"{FIXTURE_PREFIX}-terminal-cancel"
SHARED_COMMENT_KEY = f"{FIXTURE_PREFIX}-actor-bound-comment"
CROSS_COMMENT_KEY = f"{FIXTURE_PREFIX}-cross-comment-rejected"
CSRF_REJECTED_KEY = f"{FIXTURE_PREFIX}-csrf-rejected"
IDOR_COMMENT_KEY = f"{FIXTURE_PREFIX}-idor-comment"
FOLLOW_KEY = f"{FIXTURE_PREFIX}-follow"
UNFOLLOW_KEY = f"{FIXTURE_PREFIX}-unfollow"
LEARNING_KEY = f"{FIXTURE_PREFIX}-learning"
ROLLBACK_COMMENT_KEY = f"{FIXTURE_PREFIX}-rollback-comment"
TERMINAL_COMMENT_KEY = f"{FIXTURE_PREFIX}-terminal-comment"
TERMINAL_PLAN_KEY = f"{FIXTURE_PREFIX}-terminal-plan-rejected"
TERMINAL_TEAM_KEY = f"{FIXTURE_PREFIX}-terminal-team"
TERMINAL_FREEZE_KEY = f"{FIXTURE_PREFIX}-terminal-freeze-rejected"
TERMINAL_REVIEW_KEY = f"{FIXTURE_PREFIX}-terminal-review-rejected"
TERMINAL_PROJECT_CREATE_KEY = f"{FIXTURE_PREFIX}-terminal-project"
TENANT_GUARD_PROJECT_CREATE_KEY = f"{FIXTURE_PREFIX}-tenant-project"

TODAY_DUE_AT = f"{datetime.now(UTC).date().isoformat()}T23:59:59.999999Z"

CONTROL_HISTORY_DOCTYPES = (
    "NPI Project Control Binding",
    "NPI Project Health Assessment",
    "NPI Project Activity Event",
    "NPI Project Follower",
    "NPI Project Learning",
    "NPI Project Control Idempotency",
)


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


def json_value(value: object) -> object:
    return json.loads(value) if isinstance(value, str) else value


def fixture_request_id(key: str) -> str:
    return str(
        uuid5(
            NAMESPACE_URL,
            f"{FIXTURE_PREFIX}/request/{key}",
        )
    )


def fixture_trace_id(key: str) -> str:
    return (
        "trace-"
        + uuid5(
            NAMESPACE_URL,
            f"{FIXTURE_PREFIX}/trace/{key}",
        ).hex
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
    if idempotency_key is None:
        request_id = str(uuid4())
        headers = {
            "X-Request-ID": request_id,
            "X-Trace-ID": f"trace-{uuid4().hex}",
        }
    else:
        request_id = fixture_request_id(idempotency_key)
        headers = {
            "Idempotency-Key": idempotency_key,
            "X-Request-ID": request_id,
            "X-Trace-ID": fixture_trace_id(idempotency_key),
        }
        if csrf_token is not None:
            headers["X-Frappe-CSRF-Token"] = csrf_token
    result = request(
        opener,
        base_url,
        path,
        method=method,
        payload=payload,
        request_headers=headers,
    )
    require(
        result.headers.get("X-Request-ID") == request_id,
        f"NPI request identity was not echoed for {path}",
    )
    return result


def command(
    opener,
    base_url: str,
    path: str,
    payload: dict[str, object],
    *,
    csrf_token: str | None,
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


def require_fresh_command(
    result: HttpResult,
    expected_status: int,
    label: str,
) -> dict[str, Any]:
    require(
        result.status == expected_status
        and result.headers.get("Idempotency-Replayed") == "false"
        and result.headers.get("Cache-Control") == "private, no-store",
        (
            f"{label} returned HTTP {result.status}, replayed, "
            "or lost private no-store"
        ),
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


def execute_with_replay(
    opener,
    base_url: str,
    path: str,
    payload: dict[str, object],
    *,
    csrf_token: str,
    idempotency_key: str,
    expected_status: int,
    label: str,
) -> dict[str, Any]:
    first = command(
        opener,
        base_url,
        path,
        payload,
        csrf_token=csrf_token,
        idempotency_key=idempotency_key,
    )
    body = require_fresh_command(first, expected_status, label)
    replay = command(
        opener,
        base_url,
        path,
        payload,
        csrf_token=csrf_token,
        idempotency_key=idempotency_key,
    )
    require_replay(replay, expected_status, body, label)
    return body


def same_project_unavailable(first: HttpResult, second: HttpResult) -> None:
    validate_problem(first, 404, "PROJECT_UNAVAILABLE")
    validate_problem(second, 404, "PROJECT_UNAVAILABLE")
    for field in ("type", "title", "status", "code", "retryable"):
        require(
            first.body.get(field) == second.body.get(field),
            f"IDOR-safe Project unavailable field drifted: {field}",
        )


def enable_transport_role_and_utc(
    administrator,
    base_url: str,
    csrf_token: str,
    user_id: str,
) -> None:
    review_runtime.enable_transport_role(
        administrator,
        base_url,
        csrf_token,
        user_id,
    )
    updated = update_resource(
        administrator,
        base_url,
        "User",
        user_id,
        {"time_zone": "UTC"},
        csrf_token,
    )
    require(
        updated.status == 200
        and updated.body.get("data", {}).get("time_zone") == "UTC",
        f"Fixture UTC time zone assignment drifted: {user_id}",
    )


def control_policy_version_payload() -> dict[str, object]:
    return {
        "project_control_policy": CONTROL_POLICY_ID,
        "policy_version": CONTROL_POLICY_VERSION,
        "title": f"Synthetic P4-05 runtime {FIXTURE_NAMESPACE} control policy",
        "publication_state": "published",
        "authority_slots": [CONTROLLER_SLOT, SPONSOR_SLOT],
        "health_assessment_slot": CONTROLLER_SLOT,
        "health_rules": [
            {
                "dimension": "progress",
                "mode": "higher_is_better",
                "greenThreshold": 80,
                "yellowThreshold": 60,
            },
            {
                "dimension": "cost",
                "mode": "lower_is_better",
                "greenThreshold": 100,
                "yellowThreshold": 120,
            },
            {
                "dimension": "quality",
                "mode": "manual",
                "greenThreshold": None,
                "yellowThreshold": None,
            },
            {
                "dimension": "risk",
                "mode": "unavailable",
                "greenThreshold": None,
                "yellowThreshold": None,
            },
        ],
        "require_all_dimensions": 1,
        "lifecycle_transitions": [
            {
                "sourceState": "draft",
                "action": "pause",
                "targetState": "on_hold",
                "authoritySlot": CONTROLLER_SLOT,
                "prerequisites": [],
            },
            {
                "sourceState": "draft",
                "action": "cancel",
                "targetState": "cancelled",
                "authoritySlot": SPONSOR_SLOT,
                "prerequisites": ["open_blockers"],
            },
            {
                "sourceState": "on_hold",
                "action": "resume",
                "targetState": "active",
                "authoritySlot": CONTROLLER_SLOT,
                "prerequisites": [],
            },
            {
                "sourceState": "active",
                "action": "complete",
                "targetState": "completed",
                "authoritySlot": CONTROLLER_SLOT,
                "prerequisites": [
                    "open_blockers",
                    "controlled_files",
                    "handover",
                    "cost",
                ],
            },
        ],
    }


def ensure_control_policy(
    administrator,
    base_url: str,
    csrf_token: str,
) -> dict[str, object]:
    root = create_resource(
        administrator,
        base_url,
        "NPI Project Control Policy",
        {
            "global_id": CONTROL_POLICY_ID,
            "policy_code": CONTROL_POLICY_CODE,
            "title": (f"Synthetic P4-05 runtime {FIXTURE_NAMESPACE} control policy"),
            "enabled": 1,
        },
        csrf_token,
    )
    require(
        root.status in {200, 201},
        f"Project Control Policy root returned HTTP {root.status}",
    )
    version = create_resource(
        administrator,
        base_url,
        "NPI Project Control Policy Version",
        control_policy_version_payload(),
        csrf_token,
    )
    data = version.body.get("data", {})
    snapshot = json_value(data.get("snapshot"))
    snapshot_hash = data.get("snapshot_hash")
    require(
        version.status in {200, 201}
        and data.get("name") == CONTROL_POLICY_VERSION_KEY
        and data.get("publication_state") == "published"
        and isinstance(snapshot, dict)
        and isinstance(snapshot_hash, str)
        and re.fullmatch(r"[a-f0-9]{64}", snapshot_hash) is not None
        and canonical_hash(snapshot) == snapshot_hash,
        "Published Project Control Policy identity or hash drifted",
    )
    return {
        "globalId": CONTROL_POLICY_ID,
        "version": CONTROL_POLICY_VERSION,
        "snapshotHash": snapshot_hash,
    }


def configure_terminal_team(
    administrator,
    base_url: str,
    project_id: str,
    work_policy_ref: dict[str, object],
    csrf_token: str,
) -> None:
    payload = {
        "expectedProjectVersion": 1,
        "workPolicyRef": work_policy_ref,
        "members": [
            {
                "globalId": TERMINAL_OWNER_MEMBER_ID,
                "userId": evidence_runtime.OWNER_USER,
                "effectiveFrom": "2026-07-01",
            },
            {
                "globalId": TERMINAL_REVIEWER_MEMBER_ID,
                "userId": evidence_runtime.REVIEWER_USER,
                "effectiveFrom": "2026-07-01",
            },
        ],
        "roleAssignments": [
            {
                "globalId": TERMINAL_OWNER_ROLE_ID,
                "memberId": TERMINAL_OWNER_MEMBER_ID,
                "roleKey": evidence_runtime.ROLE_KEY,
                "effectiveFrom": "2026-07-01",
            }
        ],
        "substitutions": [],
        "raciAssignments": [
            {
                "globalId": TERMINAL_RACI_ID,
                "contextType": "project",
                "contextId": project_id,
                "responsibilityKey": "project.controls.runtime",
                "roleAssignmentId": TERMINAL_OWNER_ROLE_ID,
                "raci": "responsible",
            }
        ],
    }
    result = evidence_runtime.post_work_command(
        administrator,
        base_url,
        project_id,
        "configure-team",
        payload,
        csrf_token=csrf_token,
        idempotency_key=TERMINAL_TEAM_KEY,
    )
    require(
        result.status == 200
        and result.headers.get("Idempotency-Replayed") == "false"
        and result.body.get("projectVersion") == 2,
        f"Terminal Project team returned HTTP {result.status}",
    )


def domain_item_payload(
    *,
    kind: str,
    expected_version: int,
    work_policy_ref: dict[str, object],
    gate_id: str,
) -> dict[str, object]:
    due_dates = {
        "risk": "2000-01-01T00:00:00Z",
        "action": TODAY_DUE_AT,
        "decision_request": "2099-03-01T00:00:00Z",
    }
    severities = {
        "risk": "high",
        "action": "medium",
        "decision_request": "low",
    }
    context: dict[str, object] = {
        "wbsItemId": evidence_runtime.MAIN_WBS_ID,
    }
    if kind == "risk":
        context["stageId"] = gate_id
    return {
        "expectedProjectVersion": expected_version,
        "workPolicyRef": work_policy_ref,
        "kind": kind,
        "title": f"Synthetic P4-05 runtime {kind.replace('_', ' ')}",
        "detail": f"Deterministic P4-05 runtime {kind} fixture",
        "context": context,
        "ownerUserId": evidence_runtime.OWNER_USER,
        "dueAt": due_dates[kind],
        "severity": severities[kind],
        "blocking": kind == "risk",
        "relatedWorkItemIds": [],
    }


def create_domain_items(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    project_id: str,
    gate_id: str,
    work_policy_ref: dict[str, object],
) -> dict[str, str]:
    result: dict[str, str] = {}
    for expected_version, kind in enumerate(
        ("risk", "action", "decision_request"),
        start=3,
    ):
        payload = domain_item_payload(
            kind=kind,
            expected_version=expected_version,
            work_policy_ref=work_policy_ref,
            gate_id=gate_id,
        )
        body = execute_with_replay(
            administrator,
            base_url,
            f"/api/npi/v1/projects/{project_id}/domain-work-items",
            payload,
            csrf_token=csrf_token,
            idempotency_key=WORK_ITEM_KEYS[kind],
            expected_status=201,
            label=f"Domain Work Item {kind}",
        )
        global_id = body.get("globalId")
        require(
            isinstance(global_id, str)
            and body.get("projectId") == project_id
            and body.get("kind") == kind
            and body.get("ownerUserId") == evidence_runtime.OWNER_USER
            and body.get("version") == 1,
            f"Domain Work Item {kind} projection drifted",
        )
        result[kind] = global_id
    return result


def control_bindings(member_global_id: str) -> list[dict[str, str]]:
    return [
        {"slot": slot, "memberGlobalId": member_global_id}
        for slot in (CONTROLLER_SLOT, SPONSOR_SLOT)
    ]


def bind_control_policy(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    project_id: str,
    expected_version: int,
    policy_ref: dict[str, object],
    member_global_id: str,
    idempotency_key: str,
) -> dict[str, Any]:
    return execute_with_replay(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}:bind-control-policy",
        {
            "expectedProjectVersion": expected_version,
            "policyRef": policy_ref,
            "bindings": control_bindings(member_global_id),
        },
        csrf_token=csrf_token,
        idempotency_key=idempotency_key,
        expected_status=200,
        label="Project Control Policy binding",
    )


def get_controls(opener, base_url: str, project_id: str) -> HttpResult:
    return npi_request(
        opener,
        base_url,
        f"/api/npi/v1/projects/{project_id}/controls",
    )


def require_unassessed_controls(
    result: HttpResult,
    *,
    project_id: str,
    expected_version: int,
) -> dict[str, Any]:
    require(
        result.status == 200
        and result.headers.get("Cache-Control") == "private, no-store",
        f"Unassessed Project controls returned HTTP {result.status}",
    )
    body = result.body
    health = body.get("health", {})
    dimensions = health.get("dimensions", [])
    require(
        body.get("project", {}).get("globalId") == project_id
        and body.get("project", {}).get("version") == expected_version
        and body.get("policy") is None
        and body.get("binding") is None
        and health.get("overallStatus") == "unassessed"
        and health.get("assessment") is None
        and len(dimensions) == 4
        and {value.get("dimension") for value in dimensions}
        == {"progress", "cost", "quality", "risk"}
        and all(value.get("status") == "unassessed" for value in dimensions)
        and all(
            value.get("available") is False
            and value.get("reasonCode") == "policy_missing"
            for value in body.get("lifecycleActions", [])
        ),
        "Fresh migrated Project did not remain honestly unassessed",
    )
    return body


def require_bound_controls(
    body: dict[str, Any],
    *,
    project_id: str,
    expected_version: int,
    policy_ref: dict[str, object],
    member_global_id: str,
) -> None:
    policy = body.get("policy", {})
    binding = body.get("binding", {})
    authorities = binding.get("authorities", [])
    health = body.get("health", {})
    dimensions = {
        value.get("dimension"): value for value in health.get("dimensions", [])
    }
    require(
        body.get("project", {}).get("globalId") == project_id
        and body.get("project", {}).get("version") == expected_version
        and policy.get("globalId") == policy_ref["globalId"]
        and policy.get("version") == policy_ref["version"]
        and policy.get("snapshotHash") == policy_ref["snapshotHash"]
        and binding.get("version") == 1
        and {value.get("slot") for value in authorities}
        == {CONTROLLER_SLOT, SPONSOR_SLOT}
        and all(
            value.get("memberGlobalId") == member_global_id
            and value.get("userId") == evidence_runtime.OWNER_USER
            and isinstance(value.get("displayName"), str)
            and value.get("displayName")
            for value in authorities
        )
        and health.get("overallStatus") == "unassessed"
        and dimensions["risk"].get("status") == "unavailable"
        and all(
            dimensions[key].get("status") == "unassessed"
            for key in ("progress", "cost", "quality")
        ),
        "Bound Project controls lost exact policy, authority, or health state",
    )


def require_binding_options(
    result: HttpResult,
    *,
    policy_ref: dict[str, object],
) -> None:
    require(
        result.status == 200
        and result.body.get("permissions", {}).get("canBindPolicy") is True,
        "Project Control Policy binding permission was unavailable",
    )
    options = result.body.get("bindingOptions")
    require(
        isinstance(options, dict) and set(options) == {"policies", "eligibleMembers"},
        "Project Control Policy binding options shape drifted",
    )
    policies = options["policies"]
    require(
        isinstance(policies, list)
        and any(
            isinstance(option, dict)
            and option.get("policyRef") == policy_ref
            and option.get("code") == CONTROL_POLICY_CODE
            and set(option.get("authoritySlots", [])) == {CONTROLLER_SLOT, SPONSOR_SLOT}
            and isinstance(option.get("title"), str)
            and option["title"]
            for option in policies
        ),
        "Published Project Control Policy was not a selectable exact option",
    )
    members = options["eligibleMembers"]
    require(
        isinstance(members, list)
        and {
            (option.get("memberGlobalId"), option.get("userId"))
            for option in members
            if isinstance(option, dict)
            and set(option) == {"memberGlobalId", "userId", "displayName"}
            and isinstance(option.get("displayName"), str)
            and option["displayName"]
        }
        == {
            (
                evidence_runtime.OWNER_MEMBER_ID,
                evidence_runtime.OWNER_USER,
            ),
        },
        "Project Control Policy eligible-member options drifted",
    )


def my_work(
    opener,
    base_url: str,
    *,
    view: str,
    project_id: str | None = None,
    priority_scheme: str | None = None,
    priority_value: str | None = None,
    search: str | None = None,
    cursor: str | None = None,
    limit: int = 100,
) -> HttpResult:
    query: list[tuple[str, object]] = [
        ("view", view),
        ("limit", limit),
    ]
    if project_id is not None:
        query.append(("projectId", project_id))
    if priority_scheme is not None:
        query.append(("priorityScheme", priority_scheme))
    if priority_value is not None:
        query.append(("priorityValue", priority_value))
    if search is not None:
        query.append(("search", search))
    if cursor is not None:
        query.append(("cursor", cursor))
    return npi_request(
        opener,
        base_url,
        "/api/npi/v1/me/work?" + urllib.parse.urlencode(query),
    )


def require_my_work_page(
    result: HttpResult,
    *,
    expected_count: int,
    expected_time_zone: str,
) -> dict[str, Any]:
    require(
        result.status == 200
        and result.headers.get("Cache-Control") == "private, no-store",
        f"My Work returned HTTP {result.status}",
    )
    body = result.body
    counts = body.get("counts", {})
    project_options = body.get("projectOptions")
    require(
        set(body)
        == {
            "asOf",
            "timeZone",
            "projectOptions",
            "items",
            "nextCursor",
            "counts",
        }
        and isinstance(body.get("asOf"), str)
        and body.get("timeZone") == expected_time_zone
        and isinstance(project_options, list)
        and len(project_options) <= 2000
        and isinstance(body.get("items"), list)
        and counts.get("all") == {"availability": "available", "value": expected_count}
        and counts.get("integration")
        == {
            "availability": "unavailable",
            "reason": "source_not_available",
        }
        and "value" not in counts.get("integration", {}),
        (
            "My Work time zone, counts, or integration availability drifted: "
            f"{json.dumps(body, sort_keys=True)}"
        ),
    )
    project_by_id: dict[str, dict[str, object]] = {}
    for project in project_options:
        require(
            isinstance(project, dict)
            and set(project) == {"globalId", "businessCode", "title"}
            and isinstance(project.get("globalId"), str)
            and isinstance(project.get("businessCode"), str)
            and isinstance(project.get("title"), str)
            and project["globalId"] not in project_by_id,
            "My Work Project filter options are not exact and unique",
        )
        project_by_id[project["globalId"]] = project
    for item in body["items"]:
        require(
            project_by_id.get(item.get("project", {}).get("globalId"))
            == item.get("project"),
            "My Work row Project is absent from the complete filter options",
        )
        require(
            set(item.get("sourceStatus", {}))
            == {"sourceSystem", "editableIn", "syncState"}
            and item["sourceStatus"]
            == {
                "sourceSystem": "NPI_ONE",
                "editableIn": "NPI_ONE",
                "syncState": "local",
            },
            "My Work source ownership status drifted",
        )
        target = item.get("target", {})
        if target.get("kind") == "my_work_item":
            require(
                set(target) == {"kind", "workItemId"}
                and target.get("workItemId") == item.get("source", {}).get("globalId"),
                "Domain My Work target is not exact and typed",
            )
        elif target.get("kind") == "gate_review":
            require(
                set(target) == {"kind", "projectId", "gateId"}
                and target.get("projectId") == item.get("project", {}).get("globalId")
                and target.get("gateId") == item.get("source", {}).get("globalId"),
                "Gate My Work target is not exact and typed",
            )
        else:
            raise RuntimeError("My Work exposed an unsupported target.")
        serialized = json.dumps(item, sort_keys=True).casefold()
        require(
            '"path"' not in serialized
            and '"url"' not in serialized
            and "/private/files/" not in serialized,
            "My Work exposed an arbitrary path or URL",
        )
    return body


def verify_my_work_projection(
    owner,
    administrator,
    unrelated,
    base_url: str,
    *,
    project_id: str,
    gate_id: str,
    item_ids: dict[str, str],
    administrator_time_zone: str,
) -> dict[str, Any]:
    initial = require_my_work_page(
        my_work(owner, base_url, view="all"),
        expected_count=5,
        expected_time_zone="UTC",
    )
    items = initial["items"]
    domain_by_source = {
        value["source"]["globalId"]: value
        for value in items
        if value["source"]["type"] == "domain_work_item"
    }
    gate_items = [
        value
        for value in items
        if value["source"]["type"] == "gate_review_assignment"
    ]
    require(
        set(domain_by_source) == set(item_ids.values())
        and domain_by_source[item_ids["risk"]]["category"] == "risk"
        and domain_by_source[item_ids["risk"]]["blocking"] is True
        and domain_by_source[item_ids["action"]]["category"] == "task"
        and domain_by_source[item_ids["decision_request"]]["category"] == "decision"
        and len(gate_items) == 2
        and {value["source"]["globalId"] for value in gate_items} == {gate_id}
        and {value["category"] for value in gate_items} == {"approval"}
        and {value["why"] for value in gate_items}
        == {"gate_review_step", "gate_final_decision"}
        and all(
            value["target"]
            == {
                "kind": "gate_review",
                "projectId": project_id,
                "gateId": gate_id,
            }
            for value in gate_items
        ),
        "My Work source mapping or typed targets drifted",
    )
    counts = initial["counts"]
    require(
        counts["today"] == {"availability": "available", "value": 1}
        and counts["overdue"] == {"availability": "available", "value": 1}
        and counts["approvals"]
        == {
            "availability": "available",
            "value": 2,
        }
        and counts["blockers"]
        == {
            "availability": "available",
            "value": 1,
        }
        and counts["waiting"]
        == {
            "availability": "available",
            "value": 0,
        },
        "My Work view counts drifted",
    )

    expected_views = {
        "today": {item_ids["action"]},
        "overdue": {item_ids["risk"]},
        "approvals": {gate_id},
        "blockers": {item_ids["risk"]},
        "waiting": set(),
        "integration": set(),
    }
    for view, expected_sources in expected_views.items():
        page = require_my_work_page(
            my_work(owner, base_url, view=view),
            expected_count=5,
            expected_time_zone="UTC",
        )
        require(
            {value["source"]["globalId"] for value in page["items"]}
            == expected_sources,
            f"My Work {view} filter drifted",
        )
        if view == "approvals":
            require(
                len(page["items"]) == 2
                and {value["why"] for value in page["items"]}
                == {"gate_review_step", "gate_final_decision"},
                "My Work Gate authority view drifted",
            )

    project_page = require_my_work_page(
        my_work(
            owner,
            base_url,
            view="all",
            project_id=project_id,
        ),
        expected_count=5,
        expected_time_zone="UTC",
    )
    require(
        len(project_page["items"]) == 5,
        "My Work Project filter drifted",
    )
    priority_page = require_my_work_page(
        my_work(
            owner,
            base_url,
            view="all",
            priority_scheme="domain_severity",
            priority_value="high",
        ),
        expected_count=1,
        expected_time_zone="UTC",
    )
    require(
        [value["source"]["globalId"] for value in priority_page["items"]]
        == [item_ids["risk"]],
        "My Work exact priority vocabulary filter drifted",
    )

    paged_ids: list[str] = []
    cursor: str | None = None
    page_as_of: str | None = None
    first_cursor: str | None = None
    for _page in range(10):
        page = require_my_work_page(
            my_work(
                owner,
                base_url,
                view="all",
                cursor=cursor,
                limit=1,
            ),
            expected_count=5,
            expected_time_zone="UTC",
        )
        if page_as_of is None:
            page_as_of = page["asOf"]
        require(
            page["asOf"] == page_as_of,
            "My Work cursor did not retain a fixed as-of instant",
        )
        paged_ids.extend(value["id"] for value in page["items"])
        cursor = page["nextCursor"]
        if first_cursor is None:
            first_cursor = cursor
        if cursor is None:
            break
    require(
        len(paged_ids) == 5
        and len(set(paged_ids)) == 5
        and set(paged_ids) == {value["id"] for value in items}
        and first_cursor is not None,
        "My Work stable keyset pagination lost or duplicated work",
    )
    mismatched = my_work(
        owner,
        base_url,
        view="approvals",
        cursor=first_cursor,
        limit=1,
    )
    validate_problem(mismatched, 422, "VALIDATION_FAILED")
    forged = my_work(
        owner,
        base_url,
        view="all",
        cursor=f"{first_cursor}x",
        limit=1,
    )
    validate_problem(forged, 422, "VALIDATION_FAILED")
    cross_actor = my_work(
        unrelated,
        base_url,
        view="all",
        cursor=first_cursor,
        limit=1,
    )
    validate_problem(cross_actor, 422, "VALIDATION_FAILED")

    for actor, label, expected_time_zone in (
        (administrator, "System Manager", administrator_time_zone),
        (unrelated, "unassigned internal user", "UTC"),
    ):
        empty = require_my_work_page(
            my_work(actor, base_url, view="all"),
            expected_count=0,
            expected_time_zone=expected_time_zone,
        )
        require(
            empty["items"] == [],
            f"{label} received work without an exact source assignment",
        )
    guest = my_work(
        urllib.request.build_opener(),
        base_url,
        view="all",
    )
    validate_problem(guest, 401, "AUTHENTICATION_REQUIRED")
    return {
        "actorBoundCursor": True,
        "asOf": initial["asOf"],
        "cursorPages": len(paged_ids),
        "initialItems": len(items),
        "typedTargets": sorted({value["target"]["kind"] for value in items}),
    }


def comment_payload(
    *,
    work_item_id: str,
) -> dict[str, object]:
    return {
        "body": ("Synthetic P4-05 contextual comment with exact retained references."),
        "mentions": [{"memberGlobalId": evidence_runtime.REVIEWER_MEMBER_ID}],
        "attachments": [
            {
                "globalId": evidence_runtime.FILE_REVISION_ID,
                "version": 2,
            }
        ],
        "objectLinks": [
            {
                "type": "domain_work_item",
                "globalId": work_item_id,
                "version": 1,
            }
        ],
    }


def require_comment_options(
    value: object,
    *,
    project_id: str,
    gate_id: str,
    item_ids: dict[str, str],
    learning_id: str,
    attachment_sha256: str,
) -> None:
    require(
        isinstance(value, dict)
        and set(value) == {"truncated", "mentions", "attachments", "objectLinks"}
        and value["truncated"] is False,
        "Project comment options shape drifted",
    )
    mentions = value["mentions"]
    require(
        isinstance(mentions, list)
        and {
            (
                option.get("memberGlobalId"),
                option.get("userId"),
            )
            for option in mentions
            if isinstance(option, dict)
            and set(option)
            == {
                "memberGlobalId",
                "userId",
                "displayName",
            }
            and isinstance(option.get("displayName"), str)
            and option["displayName"]
        }
        == {
            (
                evidence_runtime.OWNER_MEMBER_ID,
                evidence_runtime.OWNER_USER,
            ),
            (
                evidence_runtime.REVIEWER_MEMBER_ID,
                evidence_runtime.REVIEWER_USER,
            ),
        }
        and len(mentions) == 2,
        "Project comment mention options were not exact current members",
    )
    attachments = value["attachments"]
    require(
        isinstance(attachments, list)
        and len(attachments) == 1
        and isinstance(attachments[0], dict)
        and set(attachments[0])
        == {
            "globalId",
            "version",
            "fileName",
            "mimeType",
            "sizeBytes",
            "sha256",
            "scanState",
        }
        and attachments[0]["globalId"] == evidence_runtime.FILE_REVISION_ID
        and attachments[0]["version"] == 2
        and attachments[0]["sha256"] == attachment_sha256
        and attachments[0]["scanState"] == "clean",
        "Project comment attachment options were not exact clean metadata",
    )
    expected_targets = {
        ("project", project_id): {
            "kind": "project",
            "projectId": project_id,
        },
        ("gate", gate_id): {
            "kind": "gate",
            "projectId": project_id,
            "gateId": gate_id,
        },
        ("file_revision", evidence_runtime.FILE_REVISION_ID): {
            "kind": "project",
            "projectId": project_id,
        },
        ("learning", learning_id): {
            "kind": "project_learning",
            "projectId": project_id,
            "learningId": learning_id,
        },
        **{
            ("domain_work_item", work_item_id): {
                "kind": "project_work_item",
                "projectId": project_id,
                "workItemId": work_item_id,
            }
            for work_item_id in item_ids.values()
        },
    }
    object_links = value["objectLinks"]
    require(
        isinstance(object_links, list) and len(object_links) == len(expected_targets),
        "Project comment object-link option cardinality drifted",
    )
    actual_targets: dict[tuple[object, object], object] = {}
    for option in object_links:
        require(
            isinstance(option, dict)
            and set(option)
            == {"type", "globalId", "version", "code", "title", "target"}
            and isinstance(option["version"], int)
            and option["version"] >= 1
            and isinstance(option["code"], str)
            and option["code"]
            and isinstance(option["title"], str)
            and option["title"],
            "Project comment object-link option shape drifted",
        )
        actual_targets[(option["type"], option["globalId"])] = option["target"]
    require(
        actual_targets == expected_targets,
        "Project comment object-link options lost exact typed targets",
    )


def require_control_receipt(
    administrator,
    base_url: str,
    *,
    actor: str,
    raw_key: str,
    operation: str,
    expected_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = list_resources(
        administrator,
        base_url,
        "NPI Project Control Idempotency",
        filters=[
            [
                "actor_key_hash",
                "=",
                actor_key_hash(actor, raw_key),
            ]
        ],
        fields=[
            "actor",
            "tenant_id",
            "operation",
            "payload_hash",
            "response_json",
            "response_sealed",
        ],
    )
    require(
        len(rows) == 1
        and str(rows[0]["actor"]).casefold() == actor.casefold()
        and rows[0]["tenant_id"] == TENANT_ID
        and rows[0]["operation"] == operation
        and re.fullmatch(
            r"[a-f0-9]{64}",
            str(rows[0]["payload_hash"]),
        )
        is not None
        and rows[0]["response_sealed"] == 1,
        f"Project control sealed receipt drifted: {actor}/{operation}",
    )
    response = json_value(rows[0]["response_json"])
    require(
        isinstance(response, dict)
        and (expected_body is None or response == expected_body),
        f"Project control receipt response drifted: {actor}/{operation}",
    )
    return response


def require_no_control_receipt(
    administrator,
    base_url: str,
    *,
    actor: str,
    raw_key: str,
) -> None:
    rows = list_resources(
        administrator,
        base_url,
        "NPI Project Control Idempotency",
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
        f"Rejected Project control command retained a receipt: {raw_key}",
    )


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


def _table_fields(doctype: str) -> set[str]:
    import frappe

    return {str(field.fieldname) for field in frappe.get_meta(doctype).fields}


def _effective_user_time_zone(actor: str) -> str:
    import frappe

    candidates = (
        frappe.db.get_value("User", actor, "time_zone"),
        frappe.db.get_single_value("System Settings", "time_zone"),
    )
    for candidate in candidates:
        if not isinstance(candidate, str) or not candidate.strip():
            continue
        value = candidate.strip()
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError):
            continue
        return value
    raise RuntimeError(f"Effective time zone is unavailable for {actor}.")


def _runtime_control_project_ids() -> set[str]:
    import frappe

    projects = frappe.get_all(
        "NPI Engineering Project",
        filters={"control_binding_global_id": ["!=", ""]},
        fields=["global_id", "business_code"],
        limit_page_length=10001,
    )
    require(
        len(projects) <= 10000
        and all(str(row.business_code).startswith("P4-05-") for row in projects),
        "Disposable Site contains a non-runtime Project control binding",
    )
    return {str(row.global_id) for row in projects}


def verify_runtime_schema(fixture_run_id: str) -> dict[str, object]:
    import frappe

    _validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "Schema fixture namespace is invalid",
    )
    required_fields = {
        "NPI Project Control Policy": {
            "global_id",
            "policy_code",
            "enabled",
        },
        "NPI Project Control Policy Version": {
            "global_id",
            "policy_global_id",
            "publication_state",
            "snapshot",
            "snapshot_hash",
        },
        "NPI Project Control Binding": {
            "global_id",
            "project_global_id",
            "policy_snapshot",
            "binding_snapshot",
            "snapshot_hash",
        },
        "NPI Project Health Assessment": {
            "global_id",
            "project_global_id",
            "assessment_snapshot",
            "snapshot_hash",
        },
        "NPI Project Activity Event": {
            "global_id",
            "event_type",
            "payload",
            "payload_hash",
        },
        "NPI Project Follower": {
            "global_id",
            "follower_key",
            "active",
            "optimistic_version",
        },
        "NPI Project Learning": {
            "global_id",
            "kind",
            "record_snapshot",
            "snapshot_hash",
        },
        "NPI Project Control Idempotency": {
            "record_id",
            "actor",
            "actor_key_hash",
            "payload_hash",
            "response_json",
            "response_sealed",
        },
        "NPI My Work Assignment": {
            "global_id",
            "assignment_key",
            "source_type",
            "source_snapshot",
            "snapshot_hash",
            "active",
        },
    }
    for doctype, fields in required_fields.items():
        require(
            frappe.db.table_exists(doctype) and fields <= _table_fields(doctype),
            f"Migrated Project controls fields are missing: {doctype}",
        )
    project_fields = {
        "control_binding_global_id",
        "control_policy_global_id",
        "control_policy_version",
        "control_policy_snapshot_hash",
        "control_binding_version",
        "current_health_assessment_global_id",
        "current_health_status",
        "current_health_snapshot",
        "current_health_at",
    }
    require(
        project_fields <= _table_fields("NPI Engineering Project"),
        "Migrated Project control compatibility fields are missing",
    )
    for doctype, fieldname in (
        ("NPI Project Control Idempotency", "actor_key_hash"),
        ("NPI My Work Assignment", "assignment_key"),
    ):
        indexes = frappe.db.sql(
            f"SHOW INDEX FROM `tab{doctype}`",
            as_dict=True,
        )
        require(
            any(
                str(row.get("Column_name")) == fieldname
                and int(row.get("Non_unique")) == 0
                for row in indexes
            ),
            f"Migrated unique index is missing: {doctype}.{fieldname}",
        )

    patch = "npi_core.patches.v1_2.rebuild_my_work_projection"
    require(
        frappe.db.exists(
            "Patch Log",
            {"patch": patch, "skipped": 0},
        ),
        "The additive My Work projection rebuild patch was not recorded",
    )
    roots = frappe.get_all(
        "NPI Project Control Policy",
        fields=["global_id", "policy_code", "title"],
        limit_page_length=10001,
    )
    require(
        len(roots) <= 10000
        and all(
            str(row.policy_code).startswith("p405-")
            and str(row.title).startswith("Synthetic P4-05 runtime ")
            for row in roots
        ),
        (
            "Migration installed a non-runtime Project Control Policy "
            "or business default"
        ),
    )
    runtime_projects = _runtime_control_project_ids()
    for doctype in CONTROL_HISTORY_DOCTYPES:
        rows = frappe.get_all(
            doctype,
            fields=["project_global_id"],
            limit_page_length=10001,
        )
        require(
            len(rows) <= 10000
            and all(str(row.project_global_id) in runtime_projects for row in rows),
            f"Migration installed non-runtime business history: {doctype}",
        )

    require(
        not frappe.db.exists(
            "NPI Project Control Policy",
            CONTROL_POLICY_ID,
        )
        and not frappe.db.exists(
            "NPI Project Control Policy Version",
            CONTROL_POLICY_VERSION_KEY,
        )
        and all(
            not frappe.db.exists(
                "NPI Engineering Project",
                {"business_code": business_code},
            )
            for business_code in (
                MAIN_BUSINESS_CODE,
                TERMINAL_BUSINESS_CODE,
                TENANT_GUARD_BUSINESS_CODE,
            )
        ),
        "Fresh P4-05 fixture namespace already contains business data",
    )
    return {
        "administratorTimeZone": _effective_user_time_zone("Administrator"),
        "doctypes": len(required_fields),
        "migrationBusinessDefaults": 0,
        "patchRecorded": True,
        "preexistingRuntimePolicies": len(roots),
        "projectCompatibilityFields": len(project_fields),
        "uniqueIndexes": 2,
    }


def mark_wrong_tenant_project(
    fixture_run_id: str,
    project_id: str,
) -> dict[str, str]:
    import frappe

    _validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "Tenant fixture namespace is invalid",
    )
    project = frappe.get_doc("NPI Engineering Project", project_id)
    require(
        str(project.tenant_id) == TENANT_ID
        and str(project.business_code) == TENANT_GUARD_BUSINESS_CODE,
        "Tenant guard Project scope drifted",
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
        frappe.db.get_value(
            "NPI Engineering Project",
            project_id,
            "tenant_id",
        )
        == "other-runtime-tenant",
        "Tenant guard Project mutation did not persist",
    )
    return {"projectId": project_id, "tenantId": "other-runtime-tenant"}


def reassign_domain_work_item(
    fixture_run_id: str,
    project_id: str,
    work_item_id: str,
) -> dict[str, object]:
    import frappe

    from npi_core.project_work.frappe_repository import (
        _controlled_work_write_scope,
    )

    _validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "Work assignment fixture namespace is invalid",
    )
    source = frappe.get_doc("NPI Domain Work Item", work_item_id)
    require(
        str(source.project_global_id) == project_id
        and str(source.owner_user_id) == evidence_runtime.OWNER_USER,
        "Domain Work Item reassignment scope drifted",
    )
    with _controlled_work_write_scope():
        source.owner_user_id = evidence_runtime.REVIEWER_USER
        source.save()
    frappe.db.commit()
    rows = frappe.get_all(
        "NPI My Work Assignment",
        filters={
            "source_type": "domain_work_item",
            "source_global_id": work_item_id,
        },
        fields=[
            "actor_user_id",
            "active",
            "source_version",
            "source_snapshot",
            "snapshot_hash",
        ],
        order_by="actor_user_id asc",
        limit_page_length=10,
    )
    require(
        len(rows) == 2
        and {
            (
                str(row.actor_user_id),
                int(row.active),
                int(row.source_version),
            )
            for row in rows
        }
        == {
            (evidence_runtime.OWNER_USER, 0, 1),
            (evidence_runtime.REVIEWER_USER, 1, 2),
        },
        "Domain Work Item source refresh did not deactivate the old owner",
    )
    for row in rows:
        snapshot = json_value(row.source_snapshot)
        require(
            isinstance(snapshot, dict)
            and canonical_hash(snapshot) == str(row.snapshot_hash),
            "Reassigned My Work projection hash drifted",
        )
    return {
        "activeActor": evidence_runtime.REVIEWER_USER,
        "inactiveActor": evidence_runtime.OWNER_USER,
        "sourceVersion": 2,
    }


def verify_projection_deactivation(
    fixture_run_id: str,
    gate_id: str,
    work_item_id: str,
) -> dict[str, object]:
    import frappe

    _validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "Projection deactivation fixture namespace is invalid",
    )
    gate_rows = frappe.get_all(
        "NPI My Work Assignment",
        filters={"source_global_id": gate_id},
        fields=["source_type", "assignment_code", "actor_user_id", "active"],
        limit_page_length=10,
    )
    work_rows = frappe.get_all(
        "NPI My Work Assignment",
        filters={"source_global_id": work_item_id},
        fields=["actor_user_id", "active"],
        limit_page_length=10,
    )
    require(
        len(gate_rows) == 2
        and {
            (
                str(row.source_type),
                str(row.assignment_code),
                str(row.actor_user_id),
                int(row.active),
            )
            for row in gate_rows
        }
        == {
            (
                "gate_review_assignment",
                "gate_review_step",
                evidence_runtime.OWNER_USER,
                0,
            ),
            (
                "gate_review_assignment",
                "gate_final_decision",
                evidence_runtime.OWNER_USER,
                1,
            ),
        },
        "Completed Gate review step did not preserve only the live final decision authority",
    )
    require(
        len(work_rows) == 2 and sum(int(row.active) for row in work_rows) == 1,
        "Reassigned Domain Work Item projection did not deactivate exactly once",
    )
    return {
        "gateDecisionAuthorityActive": True,
        "gateStepAssignmentActive": False,
        "workAssignmentActiveRows": 1,
    }


def seed_terminal_my_work_projections(
    fixture_run_id: str,
    project_id: str,
    gate_id: str,
) -> dict[str, object]:
    import frappe

    from npi_core.my_work.domain import (
        DomainWorkItemKind,
        MyWorkCategory,
        MyWorkPriority,
        MyWorkPriorityScheme,
        MyWorkSourceType,
        MyWorkStatus,
    )
    from npi_core.my_work.frappe_repository import (
        FrappeMyWorkAssignmentStore,
        ProjectionSpec,
    )

    _validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "Terminal My Work fixture namespace is invalid",
    )
    project = frappe.get_doc("NPI Engineering Project", project_id)
    gate = frappe.get_doc("NPI Gate Shell", gate_id)
    require(
        str(project.tenant_id) == TENANT_ID
        and str(project.lifecycle_state) in {"draft", "proposed", "active", "on_hold"}
        and str(gate.project_global_id) == project_id,
        "Terminal My Work seed scope drifted",
    )
    identities = {
        "domain_work_item": (
            fixture_id("terminal-my-work-domain-assignment"),
            TERMINAL_MY_WORK_DOMAIN_SOURCE_ID,
        ),
        "gate_review_assignment": (
            fixture_id("terminal-my-work-gate-assignment"),
            gate_id,
        ),
        "gate_review_invalidation": (
            fixture_id("terminal-my-work-gate-invalidation"),
            gate_id,
        ),
    }
    shared = {
        "tenant_id": TENANT_ID,
        "actor_user_id": evidence_runtime.OWNER_USER,
        "project_global_id": UUID(project_id),
        "source_version": 1,
        "due_at": None,
        "title": "Synthetic terminal My Work projection",
        "project_business_code": str(project.business_code),
        "project_title": str(project.title),
        "context_code": str(gate.gate_key),
        "context_title": str(gate.title),
    }
    specs = (
        ProjectionSpec(
            global_id=UUID(identities["domain_work_item"][0]),
            assignment_key=(f"{FIXTURE_PREFIX}:terminal-my-work:domain-work-item"),
            source_type=MyWorkSourceType.DOMAIN_WORK_ITEM,
            source_global_id=UUID(identities["domain_work_item"][1]),
            assignment_code="domain_work_item_owner",
            category=MyWorkCategory.TASK,
            priority=MyWorkPriority(
                MyWorkPriorityScheme.DOMAIN_SEVERITY,
                "medium",
            ),
            blocking=False,
            status=MyWorkStatus.READY,
            domain_kind=DomainWorkItemKind.ACTION,
            source_detail=(("domainKind", "action"),),
            **shared,
        ),
        ProjectionSpec(
            global_id=UUID(identities["gate_review_assignment"][0]),
            assignment_key=(f"{FIXTURE_PREFIX}:terminal-my-work:gate-assignment"),
            source_type=MyWorkSourceType.GATE_REVIEW_ASSIGNMENT,
            source_global_id=UUID(identities["gate_review_assignment"][1]),
            assignment_code="gate_review_step",
            category=MyWorkCategory.APPROVAL,
            priority=None,
            blocking=False,
            status=MyWorkStatus.READY,
            domain_kind=None,
            source_detail=(("stepKey", "runtime-terminal"),),
            **shared,
        ),
        ProjectionSpec(
            global_id=UUID(identities["gate_review_invalidation"][0]),
            assignment_key=(f"{FIXTURE_PREFIX}:terminal-my-work:gate-invalidation"),
            source_type=MyWorkSourceType.GATE_REVIEW_INVALIDATION,
            source_global_id=UUID(identities["gate_review_invalidation"][1]),
            assignment_code="gate_dependency_change",
            category=MyWorkCategory.BLOCKER,
            priority=None,
            blocking=True,
            status=MyWorkStatus.BLOCKED,
            domain_kind=None,
            source_detail=(("stepKey", "runtime-terminal"),),
            **shared,
        ),
    )
    store = FrappeMyWorkAssignmentStore()
    indexed_at = datetime.now(UTC)
    for spec in specs:
        try:
            store.upsert(spec, indexed_at=indexed_at)
        except Exception as error:
            raise RuntimeError(
                "Terminal My Work seed rejected "
                f"{spec.source_type.value} with priority "
                f"{spec.priority!r}"
            ) from error
    frappe.db.commit()
    rows = frappe.get_all(
        "NPI My Work Assignment",
        filters={
            "project_global_id": project_id,
            "global_id": ["in", [str(spec.global_id) for spec in specs]],
        },
        fields=["global_id", "source_type", "active"],
        order_by="source_type asc",
        limit_page_length=4,
    )
    require(
        len(rows) == 3
        and {str(row.source_type) for row in rows}
        == {
            "domain_work_item",
            "gate_review_assignment",
            "gate_review_invalidation",
        }
        and all(int(row.active) == 1 for row in rows),
        "Terminal My Work seed rows were not active",
    )
    return {
        "active": 3,
        "globalIds": sorted(str(row.global_id) for row in rows),
        "sourceTypes": sorted(str(row.source_type) for row in rows),
    }


def verify_terminal_my_work_deactivation(
    fixture_run_id: str,
    project_id: str,
    assignment_global_ids: list[str],
) -> dict[str, object]:
    import frappe

    _validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID
        and len(assignment_global_ids) == 3
        and len(set(assignment_global_ids)) == 3,
        "Terminal My Work verification scope is invalid",
    )
    project = frappe.get_doc("NPI Engineering Project", project_id)
    rows = frappe.get_all(
        "NPI My Work Assignment",
        filters={
            "project_global_id": project_id,
            "global_id": ["in", assignment_global_ids],
        },
        fields=[
            "global_id",
            "source_type",
            "active",
            "source_snapshot",
            "snapshot_hash",
        ],
        order_by="source_type asc",
        limit_page_length=4,
    )
    require(
        str(project.lifecycle_state) in {"completed", "cancelled"}
        and len(rows) == 3
        and {str(row.source_type) for row in rows}
        == {
            "domain_work_item",
            "gate_review_assignment",
            "gate_review_invalidation",
        }
        and all(int(row.active) == 0 for row in rows),
        "Terminal Project hook left an active My Work source type",
    )
    for row in rows:
        snapshot = json_value(row.source_snapshot)
        require(
            isinstance(snapshot, dict)
            and snapshot.get("active") is False
            and canonical_hash(snapshot) == str(row.snapshot_hash),
            "Terminal My Work deactivation snapshot drifted",
        )
    return {
        "active": 0,
        "deactivated": len(rows),
        "sourceTypes": sorted(str(row.source_type) for row in rows),
    }


def _projection_state() -> list[dict[str, object]]:
    import frappe

    rows = frappe.get_all(
        "NPI My Work Assignment",
        filters={"tenant_id": TENANT_ID},
        fields=[
            "global_id",
            "assignment_key",
            "tenant_id",
            "actor_user_id",
            "project_global_id",
            "source_type",
            "source_global_id",
            "source_version",
            "assignment_code",
            "category",
            "due_at",
            "priority_scheme",
            "priority_value",
            "blocking",
            "active",
            "source_snapshot",
            "snapshot_hash",
        ],
        order_by="assignment_key asc",
        limit_page_length=10001,
    )
    require(
        len(rows) <= 10000,
        "My Work projection state exceeds the runtime verification bound",
    )
    state: list[dict[str, object]] = []
    for row in rows:
        snapshot = json_value(row.source_snapshot)
        require(
            isinstance(snapshot, dict)
            and canonical_hash(snapshot) == str(row.snapshot_hash),
            "My Work projection snapshot/hash state is invalid",
        )
        state.append(
            {
                "globalId": str(row.global_id),
                "assignmentKey": str(row.assignment_key),
                "tenantId": str(row.tenant_id),
                "actorUserId": str(row.actor_user_id),
                "projectGlobalId": str(row.project_global_id),
                "sourceType": str(row.source_type),
                "sourceGlobalId": str(row.source_global_id),
                "sourceVersion": int(row.source_version),
                "assignmentCode": str(row.assignment_code),
                "category": str(row.category),
                "dueAt": (
                    str(row.due_at) if row.due_at is not None else None
                ),
                "priorityScheme": (
                    str(row.priority_scheme)
                    if row.priority_scheme is not None
                    else None
                ),
                "priorityValue": (
                    str(row.priority_value)
                    if row.priority_value is not None
                    else None
                ),
                "blocking": int(row.blocking),
                "active": int(row.active),
                "sourceSnapshot": snapshot,
                "snapshotHash": str(row.snapshot_hash),
            }
        )
    return state


def verify_projection_rebuild(
    fixture_run_id: str,
) -> dict[str, object]:
    from unittest.mock import patch

    import frappe
    from npi_core.my_work import frappe_repository as projection_repository

    _validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "Projection rebuild fixture namespace is invalid",
    )
    before = _projection_state()
    original_refresh = (
        projection_repository.refresh_domain_work_item_assignment
    )
    refresh_count = 0

    def fail_after_first_refresh(*args, **kwargs):
        nonlocal refresh_count
        result = original_refresh(*args, **kwargs)
        refresh_count += 1
        if refresh_count == 1:
            raise RuntimeError(
                "synthetic failure after partial My Work projection rebuild"
            )
        return result

    try:
        with patch.object(
            projection_repository,
            "refresh_domain_work_item_assignment",
            side_effect=fail_after_first_refresh,
        ):
            projection_repository.rebuild_my_work_projection()
    except RuntimeError as error:
        require(
            str(error)
            == "synthetic failure after partial My Work projection rebuild",
            "Projection rebuild rollback raised an unexpected error",
        )
        frappe.db.rollback()
    else:
        frappe.db.rollback()
        raise AssertionError(
            "Projection rebuild rollback failure was not injected"
        )
    rolled_back = _projection_state()
    require(
        refresh_count == 1 and rolled_back == before,
        "Partial My Work projection rebuild was not rolled back atomically",
    )

    first_result = projection_repository.rebuild_my_work_projection()
    frappe.db.commit()
    first = _projection_state()
    second_result = projection_repository.rebuild_my_work_projection()
    frappe.db.commit()
    second = _projection_state()
    require(
        before == first == second and first_result == second_result,
        (
            "My Work projection rebuild was not idempotent: "
            f"before={before!r}; first={first!r}; second={second!r}; "
            f"firstResult={first_result!r}; secondResult={second_result!r}"
        ),
    )
    return {
        "active": sum(int(value["active"]) for value in second),
        "assignmentCount": second_result.assignment_count,
        "assignmentDigest": second_result.assignment_digest,
        "idempotent": True,
        "rollbackAtomic": True,
        "rows": len(second),
        "sourceCount": second_result.source_count,
    }


def verify_transaction_rollback(
    fixture_run_id: str,
    project_id: str,
) -> dict[str, object]:
    from unittest.mock import patch

    import frappe
    from npi_core.foundation.security import Principal
    from npi_core.project_controls.frappe_repository import (
        FrappeProjectControlsRepository,
    )

    _validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "Project control rollback fixture namespace is invalid",
    )
    project_before = frappe.get_doc("NPI Engineering Project", project_id)
    request_id = str(uuid4())
    trace_id = f"trace-{uuid4().hex}"
    hashed_key = actor_key_hash("Administrator", ROLLBACK_COMMENT_KEY)
    repository = FrappeProjectControlsRepository(
        principal=Principal(
            user_id="Administrator",
            roles=frozenset({"System Manager", "NPI API User"}),
            project_access={},
            is_external=False,
            tenant_id=TENANT_ID,
        ),
        request_id=request_id,
        trace_id=trace_id,
    )
    injected = RuntimeError(
        "synthetic rollback after Project audit insert"
    )
    staged_receipt: object | None = None
    staged_activity: list[str] = []
    staged_audit: list[str] = []
    try:
        with patch.object(
            FrappeProjectControlsRepository,
            "_seal_idempotency",
            side_effect=injected,
        ):
            repository.add_comment(
                UUID(project_id),
                idempotency_key=hashed_key,
                body="Synthetic transaction rollback probe.",
                mentions=(),
                attachments=(),
                object_links=(),
            )
    except RuntimeError as error:
        require(
            str(error) == str(injected),
            "Project control rollback raised an unexpected error",
        )
        staged_receipt = frappe.db.get_value(
            "NPI Project Control Idempotency",
            {"actor_key_hash": hashed_key},
            "name",
        )
        staged_activity = frappe.get_all(
            "NPI Project Activity Event",
            filters={"request_id": request_id},
            pluck="name",
            limit_page_length=2,
        )
        staged_audit = frappe.get_all(
            "NPI Audit Event",
            filters={"trace_id": trace_id},
            pluck="name",
            limit_page_length=2,
        )
        require(
            staged_receipt is not None
            and len(staged_activity) == 1
            and len(staged_audit) == 1,
            "Project control rollback probe did not stage every write",
        )
        frappe.db.rollback()
    else:
        frappe.db.rollback()
        raise AssertionError("Project control rollback failure was not injected")

    project_after = frappe.get_doc("NPI Engineering Project", project_id)
    receipt = frappe.db.get_value(
        "NPI Project Control Idempotency",
        {"actor_key_hash": hashed_key},
        "name",
    )
    activity = frappe.get_all(
        "NPI Project Activity Event",
        filters={"request_id": request_id},
        pluck="name",
        limit_page_length=2,
    )
    audit = frappe.get_all(
        "NPI Audit Event",
        filters={"trace_id": trace_id},
        pluck="name",
        limit_page_length=2,
    )
    require(
        receipt is None
        and activity == []
        and audit == []
        and int(project_after.optimistic_version)
        == int(project_before.optimistic_version),
        "Failed Project control transaction left partial state",
    )
    return {
        "activityAbsent": True,
        "auditAbsent": True,
        "idempotencyAbsent": True,
        "projectVersion": int(project_after.optimistic_version),
        "stagedActivity": len(staged_activity),
        "stagedAudit": len(staged_audit),
        "stagedIdempotency": staged_receipt is not None,
    }


def verify_route_disable_switch(
    fixture_run_id: str,
) -> dict[str, object]:
    import frappe
    from npi_core import bff

    _validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "Project collaboration route-disable fixture namespace is invalid",
    )
    key = "npi_p4_05_routes_disabled"
    had_original = key in frappe.conf
    original = frappe.conf.get(key)
    try:
        frappe.conf[key] = True
        require(
            bff._p4_05_routes_disabled(
                "npi_core.my_work_api.get_my_work"
            )
            and bff._p4_05_routes_disabled(
                "npi_core.project_controls_api.get_project_controls"
            )
            and not bff._p4_05_routes_disabled(
                "npi_core.project_work_api.get_project_work_context"
            ),
            "Project collaboration route-disable scope drifted",
        )
        frappe.conf[key] = "true"
        require(
            not bff._p4_05_routes_disabled(
                "npi_core.my_work_api.get_my_work"
            ),
            "Ambiguous route-disable configuration was accepted",
        )
    finally:
        if had_original:
            frappe.conf[key] = original
        else:
            frappe.conf.pop(key, None)
    return {
        "exactBooleanRequired": True,
        "priorRoutesRemainEnabled": True,
        "p405RoutesDisable": True,
    }


def verify_route_disable_http_probe(
    base_url: str,
    *,
    expected_mode: str,
) -> dict[str, object]:
    """Exercise every P4-05 BFF route through the restarted local server."""

    require(
        expected_mode in {"disabled", "recovered"},
        "Project collaboration route probe mode is invalid",
    )
    administrator_user = "Administrator"
    administrator = login(
        base_url,
        administrator_user,
        secret_from_environment("NPI_RUNTIME_ADMINISTRATOR_PASSWORD"),
    )
    csrf_token = bootstrap_csrf(
        administrator,
        base_url,
        administrator_user,
    )
    missing_project_id = fixture_id("route-disable-missing-project")
    missing_gate_id = fixture_id("route-disable-missing-gate")
    policy_id = fixture_id("route-disable-policy")
    route_requests: tuple[
        tuple[
            str,
            str,
            str,
            dict[str, object] | None,
            int,
            str | None,
        ],
        ...,
    ] = (
        (
            "my-work",
            "GET",
            "/api/npi/v1/me/work?view=all&limit=1",
            None,
            200,
            None,
        ),
        (
            "global-learning",
            "GET",
            "/api/npi/v1/learning?limit=1",
            None,
            200,
            None,
        ),
        (
            "project-controls",
            "GET",
            f"/api/npi/v1/projects/{missing_project_id}/controls",
            None,
            404,
            "PROJECT_UNAVAILABLE",
        ),
        (
            "project-activity",
            "GET",
            f"/api/npi/v1/projects/{missing_project_id}/activity?limit=1",
            None,
            404,
            "PROJECT_UNAVAILABLE",
        ),
        (
            "project-comment",
            "POST",
            f"/api/npi/v1/projects/{missing_project_id}/comments",
            {
                "body": "Controlled route-disable recovery probe.",
                "mentions": [],
                "attachments": [],
                "objectLinks": [],
            },
            404,
            "PROJECT_UNAVAILABLE",
        ),
        (
            "project-learning-query",
            "GET",
            f"/api/npi/v1/projects/{missing_project_id}/learning?limit=1",
            None,
            404,
            "PROJECT_UNAVAILABLE",
        ),
        (
            "project-learning-create",
            "POST",
            f"/api/npi/v1/projects/{missing_project_id}/learning",
            {
                "kind": "retrospective",
                "title": "Controlled route-disable recovery probe",
                "content": "No production data is used.",
                "recommendation": None,
                "tags": [],
            },
            404,
            "PROJECT_UNAVAILABLE",
        ),
        (
            "bind-policy",
            "POST",
            (
                f"/api/npi/v1/projects/{missing_project_id}"
                ":bind-control-policy"
            ),
            {
                "expectedProjectVersion": 1,
                "policyRef": {
                    "globalId": policy_id,
                    "version": 1,
                    "snapshotHash": "a" * 64,
                },
                "bindings": [],
            },
            404,
            "PROJECT_UNAVAILABLE",
        ),
        (
            "assess-health",
            "POST",
            f"/api/npi/v1/projects/{missing_project_id}:assess-health",
            {
                "expectedProjectVersion": 1,
                "measurements": [],
                "reason": None,
                "recoveryPlan": None,
            },
            404,
            "PROJECT_UNAVAILABLE",
        ),
        (
            "transition",
            "POST",
            f"/api/npi/v1/projects/{missing_project_id}:transition",
            {
                "expectedProjectVersion": 1,
                "action": "pause",
                "reason": "Controlled route-disable recovery probe.",
            },
            404,
            "PROJECT_UNAVAILABLE",
        ),
        (
            "follow",
            "POST",
            f"/api/npi/v1/projects/{missing_project_id}:follow",
            {"expectedVersion": 0},
            404,
            "PROJECT_UNAVAILABLE",
        ),
        (
            "unfollow",
            "POST",
            f"/api/npi/v1/projects/{missing_project_id}:unfollow",
            {"expectedVersion": 0},
            404,
            "PROJECT_UNAVAILABLE",
        ),
    )
    route_statuses: dict[str, int] = {}
    for index, (
        label,
        method,
        path,
        payload,
        recovered_status,
        recovered_code,
    ) in enumerate(route_requests):
        result = npi_request(
            administrator,
            base_url,
            path,
            method=method,
            payload=payload,
            csrf_token=csrf_token if method == "POST" else None,
            idempotency_key=(
                f"{FIXTURE_PREFIX}-route-probe-{expected_mode}-{index}"
                if method == "POST"
                else None
            ),
        )
        route_statuses[label] = result.status
        if expected_mode == "disabled":
            validate_problem(
                result,
                503,
                "PROJECT_COLLABORATION_ROUTES_DISABLED",
            )
            require(
                result.body.get("retryable") is True
                and result.headers.get("Cache-Control")
                == "private, no-store",
                f"Disabled Project collaboration route {label} drifted",
            )
        else:
            require(
                result.status == recovered_status
                and result.body.get("code") == recovered_code,
                (
                    f"Recovered Project collaboration route {label} "
                    "did not restore its exact contract"
                ),
            )
            require(
                result.headers.get("Cache-Control") == "private, no-store",
                f"Recovered Project collaboration route {label} lost privacy",
            )

    def direct_body(result: HttpResult, label: str) -> dict[str, object]:
        if set(result.body) == {"message"}:
            message = result.body.get("message")
            require(
                isinstance(message, dict),
                f"Direct Project collaboration route {label} envelope drifted",
            )
            return message
        return result.body

    direct_statuses: dict[str, int] = {}
    for label, path in (
        (
            "direct-my-work",
            (
                "/api/method/npi_core.my_work_api.get_my_work"
                "?view=all&limit=1"
            ),
        ),
        (
            "direct-global-learning",
            (
                "/api/method/"
                "npi_core.project_controls_api.search_project_learning"
                "?limit=1"
            ),
        ),
    ):
        result = npi_request(administrator, base_url, path)
        direct_statuses[label] = result.status
        response_body = direct_body(result, label)
        if expected_mode == "disabled":
            require(
                result.status == 503
                and response_body.get("code")
                == "PROJECT_COLLABORATION_ROUTES_DISABLED"
                and response_body.get("retryable") is True
                and response_body.get("traceId")
                == result.headers.get("X-Trace-ID"),
                f"Disabled direct Project collaboration route {label} drifted",
            )
        else:
            require(
                result.status == 200
                and response_body.get("code")
                != "PROJECT_COLLABORATION_ROUTES_DISABLED",
                f"Recovered direct Project collaboration route {label} drifted",
            )
        require(
            result.headers.get("Cache-Control") == "private, no-store",
            f"Direct Project collaboration route {label} lost privacy",
        )

    prior_route_statuses: dict[str, int] = {}
    for label, path, recovered_code in (
        (
            "project-work-context",
            f"/api/npi/v1/projects/{missing_project_id}/work-context",
            "PROJECT_UNAVAILABLE",
        ),
        (
            "gate-evidence",
            (
                f"/api/npi/v1/projects/{missing_project_id}/gates/"
                f"{missing_gate_id}/evidence"
            ),
            "GATE_UNAVAILABLE",
        ),
    ):
        result = npi_request(administrator, base_url, path)
        prior_route_statuses[label] = result.status
        require(
            result.status == 404
            and result.body.get("code") == recovered_code
            and result.headers.get("Cache-Control") == "private, no-store",
            f"Prior route {label} was affected by the P4-05 switch",
        )

    return {
        "mode": expected_mode,
        "p405RouteCount": len(route_statuses) + len(direct_statuses),
        "priorRouteCount": len(prior_route_statuses),
        "directRouteStatuses": direct_statuses,
        "routeStatuses": route_statuses,
        "priorRouteStatuses": prior_route_statuses,
    }


def verify_persisted_controls(
    fixture_run_id: str,
    main_project_id: str,
    terminal_project_id: str,
    risk_id: str,
) -> dict[str, object]:
    import frappe

    _validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "Persisted controls fixture namespace is invalid",
    )
    main = frappe.get_doc("NPI Engineering Project", main_project_id)
    terminal = frappe.get_doc(
        "NPI Engineering Project",
        terminal_project_id,
    )
    require(
        str(main.lifecycle_state) == "active"
        and int(main.optimistic_version) == 10
        and str(main.current_health_status) == "unavailable"
        and str(terminal.lifecycle_state) == "cancelled"
        and int(terminal.optimistic_version) == 4,
        "Persisted Project lifecycle or health state drifted",
    )

    hashed_fields = {
        "NPI Project Control Binding": (
            "binding_snapshot",
            "snapshot_hash",
        ),
        "NPI Project Health Assessment": (
            "assessment_snapshot",
            "snapshot_hash",
        ),
        "NPI Project Activity Event": ("payload", "payload_hash"),
        "NPI Project Learning": ("record_snapshot", "snapshot_hash"),
        "NPI My Work Assignment": ("source_snapshot", "snapshot_hash"),
    }
    verified_hashes = 0
    for doctype, (payload_field, hash_field) in hashed_fields.items():
        filters: dict[str, object]
        if doctype == "NPI My Work Assignment":
            filters = {"tenant_id": TENANT_ID}
        else:
            filters = {
                "project_global_id": [
                    "in",
                    [main_project_id, terminal_project_id],
                ]
            }
        rows = frappe.get_all(
            doctype,
            filters=filters,
            fields=[payload_field, hash_field],
            limit_page_length=10001,
        )
        require(
            len(rows) <= 10000,
            f"Persisted {doctype} verification bound exceeded",
        )
        for row in rows:
            payload = json_value(row.get(payload_field))
            require(
                isinstance(payload, dict)
                and canonical_hash(payload) == str(row.get(hash_field)),
                f"Persisted {doctype} hash drifted",
            )
            verified_hashes += 1

    activities = frappe.get_all(
        "NPI Project Activity Event",
        filters={
            "project_global_id": [
                "in",
                [main_project_id, terminal_project_id],
            ]
        },
        fields=["event_type", "payload"],
        limit_page_length=100,
    )
    event_types = {str(row.event_type) for row in activities}
    require(
        {
            "comment_added",
            "followed",
            "unfollowed",
            "health_assessed",
            "lifecycle_transition",
            "learning_created",
        }
        <= event_types,
        "Persisted Project activity coverage drifted",
    )
    serialized = json.dumps(
        [json_value(row.payload) for row in activities],
        sort_keys=True,
    ).casefold()
    require(
        "/private/files/" not in serialized
        and '"url"' not in serialized
        and "file_url" not in serialized,
        "Persisted Project activity exposed a private URL",
    )
    risk = frappe.get_doc("NPI Domain Work Item", risk_id)
    require(
        str(risk.owner_user_id) == evidence_runtime.OWNER_USER
        and int(risk.optimistic_version) == 1,
        "Cross-process comment source identity drifted",
    )
    return {
        "activityEventTypes": sorted(event_types),
        "hashesVerified": verified_hashes,
        "mainProjectVersion": int(main.optimistic_version),
        "terminalProjectVersion": int(terminal.optimistic_version),
    }


def run_bench_fixture(
    method: str,
    kwargs: dict[str, object],
) -> dict[str, Any]:
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
            str(ROOT / "scripts" / "verify_project_controls_runtime.py"),
            "--bench-fixture",
            method,
            "--fixture-kwargs",
            json.dumps(
                kwargs,
                separators=(",", ":"),
                sort_keys=True,
            ),
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
    require(
        bool(output),
        f"Controlled Bench fixture {method} returned no result",
    )
    result = json.loads(output[-1])
    require(
        isinstance(result, dict),
        f"Controlled Bench fixture {method} result is invalid",
    )
    return result


def run_local_bench_fixture(
    method: str,
    kwargs: dict[str, object],
) -> None:
    fixtures = {
        "mark_wrong_tenant_project": mark_wrong_tenant_project,
        "reassign_domain_work_item": reassign_domain_work_item,
        "seed_terminal_my_work_projections": (seed_terminal_my_work_projections),
        "verify_persisted_controls": verify_persisted_controls,
        "verify_projection_deactivation": (verify_projection_deactivation),
        "verify_projection_rebuild": verify_projection_rebuild,
        "verify_route_disable_switch": verify_route_disable_switch,
        "verify_runtime_schema": verify_runtime_schema,
        "verify_terminal_my_work_deactivation": (verify_terminal_my_work_deactivation),
        "verify_transaction_rollback": verify_transaction_rollback,
    }
    require(
        method in fixtures,
        "Controlled Bench fixture method is unavailable",
    )
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
        print(
            json.dumps(
                result,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.destroy()


def verify_fresh_fixture_namespace(
    administrator,
    base_url: str,
) -> dict[str, object]:
    base = review_runtime.verify_fresh_fixture_namespace(
        administrator,
        base_url,
    )
    for doctype, name in (
        ("NPI Project Control Policy", CONTROL_POLICY_ID),
        (
            "NPI Project Control Policy Version",
            CONTROL_POLICY_VERSION_KEY,
        ),
    ):
        require(
            get_resource(
                administrator,
                base_url,
                doctype,
                name,
            ).status
            == 404,
            f"Fresh P4-05 namespace already contains {doctype}: {name}",
        )
    for business_code in (
        MAIN_BUSINESS_CODE,
        TERMINAL_BUSINESS_CODE,
        TENANT_GUARD_BUSINESS_CODE,
    ):
        require(
            list_resources(
                administrator,
                base_url,
                "NPI Engineering Project",
                filters=[["business_code", "=", business_code]],
                fields=["name"],
            )
            == [],
            f"Fresh P4-05 namespace already contains {business_code}",
        )
    idempotency = (
        ("Administrator", MAIN_BIND_KEY),
        ("Administrator", TERMINAL_BIND_KEY),
        (evidence_runtime.OWNER_USER, HEALTH_REJECTED_KEY),
        (evidence_runtime.OWNER_USER, HEALTH_KEY),
        (evidence_runtime.OWNER_USER, PAUSE_KEY),
        (evidence_runtime.OWNER_USER, RESUME_KEY),
        (evidence_runtime.OWNER_USER, COMPLETE_REJECTED_KEY),
        (evidence_runtime.OWNER_USER, TERMINAL_CANCEL_KEY),
        (evidence_runtime.OWNER_USER, SHARED_COMMENT_KEY),
        ("Administrator", SHARED_COMMENT_KEY),
        (evidence_runtime.UNRELATED_USER, IDOR_COMMENT_KEY),
        (evidence_runtime.OWNER_USER, CROSS_COMMENT_KEY),
        (evidence_runtime.OWNER_USER, CSRF_REJECTED_KEY),
        (evidence_runtime.OWNER_USER, FOLLOW_KEY),
        (evidence_runtime.OWNER_USER, UNFOLLOW_KEY),
        (evidence_runtime.OWNER_USER, LEARNING_KEY),
        (evidence_runtime.OWNER_USER, TERMINAL_COMMENT_KEY),
    )
    for actor, raw_key in idempotency:
        require(
            list_resources(
                administrator,
                base_url,
                "NPI Project Control Idempotency",
                filters=[
                    [
                        "actor_key_hash",
                        "=",
                        actor_key_hash(actor, raw_key),
                    ]
                ],
                fields=["name"],
            )
            == [],
            f"Fresh P4-05 namespace contains idempotency: {raw_key}",
        )
    for doctype, actor, raw_key in (
        (
            "NPI Project Idempotency",
            "Administrator",
            TERMINAL_PROJECT_CREATE_KEY,
        ),
        (
            "NPI Project Idempotency",
            "Administrator",
            TENANT_GUARD_PROJECT_CREATE_KEY,
        ),
        (
            "NPI Project Work Idempotency",
            "Administrator",
            TERMINAL_TEAM_KEY,
        ),
        *(
            (
                "NPI Project Work Idempotency",
                "Administrator",
                raw_key,
            )
            for raw_key in WORK_ITEM_KEYS.values()
        ),
        (
            "NPI Project Work Idempotency",
            "Administrator",
            TERMINAL_PLAN_KEY,
        ),
        (
            "NPI Project Work Idempotency",
            "Administrator",
            TERMINAL_FREEZE_KEY,
        ),
        (
            "NPI Gate Review Idempotency",
            "Administrator",
            TERMINAL_REVIEW_KEY,
        ),
    ):
        require(
            list_resources(
                administrator,
                base_url,
                doctype,
                filters=[
                    [
                        "actor_key_hash",
                        "=",
                        actor_key_hash(actor, raw_key),
                    ]
                ],
                fields=["name"],
            )
            == [],
            f"Fresh P4-05 namespace contains idempotency: {raw_key}",
        )
    return {
        "base": base,
        "controlIdempotency": len(idempotency),
        "controlPolicyRecords": 2,
        "projects": 3,
    }


def terminal_plan_payload(
    work_policy_ref: dict[str, object],
) -> dict[str, object]:
    return {
        "expectedProjectVersion": 4,
        "workPolicyRef": work_policy_ref,
        "items": [
            {
                "globalId": TERMINAL_WBS_ID,
                "code": "P4.05.TERMINAL",
                "title": "This terminal mutation must be rejected",
                "ownerRoleAssignmentId": TERMINAL_OWNER_ROLE_ID,
                "plannedStart": "2026-08-01",
                "plannedFinish": "2026-08-02",
                "actualStart": None,
                "actualFinish": None,
                "milestone": False,
                "statusKey": evidence_runtime.WBS_STATE_KEY,
                "progressPercent": 0,
                "critical": False,
            }
        ],
        "dependencies": [],
    }


def terminal_freeze_payload() -> dict[str, object]:
    return {
        "expectedGateVersion": 1,
        "gateDueDate": "2026-08-31",
        "requirements": [
            {
                "key": evidence_runtime.REQUIREMENT_WBS,
                "ownerMemberId": TERMINAL_OWNER_MEMBER_ID,
                "reviewerMemberIds": [TERMINAL_REVIEWER_MEMBER_ID],
                "dueDate": "2026-08-15",
            },
            {
                "key": evidence_runtime.REQUIREMENT_FILE,
                "ownerMemberId": TERMINAL_REVIEWER_MEMBER_ID,
                "reviewerMemberIds": [TERMINAL_OWNER_MEMBER_ID],
                "dueDate": "2026-08-20",
            },
        ],
    }


def verify_terminal_guards(
    administrator,
    owner,
    base_url: str,
    *,
    administrator_csrf: str,
    owner_csrf: str,
    project_id: str,
    gate_id: str,
    work_policy_ref: dict[str, object],
    review_policy_hash: str,
) -> None:
    work = evidence_runtime.post_work_command(
        administrator,
        base_url,
        project_id,
        "apply-work-plan",
        terminal_plan_payload(work_policy_ref),
        csrf_token=administrator_csrf,
        idempotency_key=TERMINAL_PLAN_KEY,
    )
    validate_problem(work, 409, "PROJECT_HISTORY_LOCKED")

    freeze = evidence_runtime.freeze_requirements(
        administrator,
        base_url,
        project_id,
        gate_id,
        terminal_freeze_payload(),
        csrf_token=administrator_csrf,
        idempotency_key=TERMINAL_FREEZE_KEY,
    )
    validate_problem(freeze, 409, "PROJECT_HISTORY_LOCKED")

    start = review_runtime.start_review(
        administrator,
        base_url,
        project_id,
        gate_id,
        {
            "expectedGateVersion": 1,
            "policyGlobalId": review_runtime.POLICY_ID,
            "policyVersion": review_runtime.POLICY_VERSION,
            "policySnapshotHash": review_policy_hash,
            "bindings": [
                {
                    "slot": slot,
                    "memberGlobalId": TERMINAL_OWNER_MEMBER_ID,
                }
                for slot in (
                    review_runtime.REVIEW_SLOT,
                    review_runtime.DECISION_SLOT,
                    review_runtime.REOPEN_SLOT,
                    review_runtime.EXCEPTION_SLOT,
                )
            ],
        },
        csrf_token=administrator_csrf,
        idempotency_key=TERMINAL_REVIEW_KEY,
    )
    validate_problem(start, 409, "PROJECT_HISTORY_LOCKED")
    for doctype, raw_key in (
        ("NPI Project Work Idempotency", TERMINAL_PLAN_KEY),
        ("NPI Project Work Idempotency", TERMINAL_FREEZE_KEY),
        ("NPI Gate Review Idempotency", TERMINAL_REVIEW_KEY),
    ):
        require(
            list_resources(
                administrator,
                base_url,
                doctype,
                filters=[
                    [
                        "actor_key_hash",
                        "=",
                        actor_key_hash("Administrator", raw_key),
                    ]
                ],
                fields=["name"],
            )
            == [],
            f"Terminal legacy mutation retained a receipt: {raw_key}",
        )

    comment = execute_with_replay(
        owner,
        base_url,
        f"/api/npi/v1/projects/{project_id}/comments",
        {
            "body": ("Append-only context remains available after cancellation."),
            "mentions": [],
            "attachments": [],
            "objectLinks": [],
        },
        csrf_token=owner_csrf,
        idempotency_key=TERMINAL_COMMENT_KEY,
        expected_status=201,
        label="Terminal Project append-only comment",
    )
    require(
        comment.get("eventType") == "comment_added",
        "Terminal Project append-only collaboration was not retained",
    )


def find_single_project(
    administrator,
    base_url: str,
    business_code: str,
) -> str:
    rows = list_resources(
        administrator,
        base_url,
        "NPI Engineering Project",
        filters=[["business_code", "=", business_code]],
        fields=["global_id"],
    )
    require(
        len(rows) == 1 and isinstance(rows[0].get("global_id"), str),
        f"Expected one retained Project: {business_code}",
    )
    return str(rows[0]["global_id"])


def find_single_work_item(
    administrator,
    base_url: str,
    project_id: str,
    kind: str,
) -> dict[str, object]:
    rows = list_resources(
        administrator,
        base_url,
        "NPI Domain Work Item",
        filters=[
            ["project_global_id", "=", project_id],
            ["kind", "=", kind],
        ],
        fields=["global_id", "optimistic_version"],
    )
    require(
        len(rows) == 1,
        f"Expected one retained {kind} Domain Work Item",
    )
    return rows[0]


def verify_cross_process_replay(
    administrator,
    base_url: str,
    fixture_password: str,
) -> dict[str, object]:
    project_id = find_single_project(
        administrator,
        base_url,
        MAIN_BUSINESS_CODE,
    )
    risk = find_single_work_item(
        administrator,
        base_url,
        project_id,
        "risk",
    )
    require(
        risk.get("optimistic_version") == 1,
        "Retained comment source version drifted",
    )
    owner = login(
        base_url,
        evidence_runtime.OWNER_USER,
        fixture_password,
    )
    owner_csrf = bootstrap_csrf(
        owner,
        base_url,
        evidence_runtime.OWNER_USER,
    )
    expected = require_control_receipt(
        administrator,
        base_url,
        actor=evidence_runtime.OWNER_USER,
        raw_key=SHARED_COMMENT_KEY,
        operation="project.comment.add",
    )
    replay = command(
        owner,
        base_url,
        f"/api/npi/v1/projects/{project_id}/comments",
        comment_payload(work_item_id=str(risk["global_id"])),
        csrf_token=owner_csrf,
        idempotency_key=SHARED_COMMENT_KEY,
    )
    require_replay(
        replay,
        201,
        expected,
        "Cross-process Project comment",
    )
    return {
        "actor": evidence_runtime.OWNER_USER,
        "operation": "project.comment.add",
        "projectId": project_id,
        "sealedReplay": True,
    }


def require_activity_cursor_chain(
    session,
    base_url: str,
    *,
    project_id: str,
    expected_items: list[dict[str, Any]],
) -> dict[str, int]:
    cursor: str | None = None
    seen_cursors: set[str] = set()
    seen_ids: set[str] = set()
    collected: list[dict[str, Any]] = []
    previous_key: tuple[datetime, str] | None = None
    page_count = 0
    while True:
        query: dict[str, object] = {"limit": 2}
        if cursor is not None:
            query["cursor"] = cursor
        page = npi_request(
            session,
            base_url,
            (
                f"/api/npi/v1/projects/{project_id}/activity?"
                + urllib.parse.urlencode(query)
            ),
        )
        require(
            page.status == 200
            and page.body.get("projectId") == project_id
            and "nextCursor" in page.body,
            "Project activity continuation page drifted",
        )
        items = page.body.get("items")
        require(
            isinstance(items, list) and len(items) <= 2,
            "Project activity continuation exceeded its requested bound",
        )
        for item in items:
            require(
                isinstance(item, dict)
                and isinstance(item.get("occurredAt"), str)
                and isinstance(item.get("globalId"), str),
                "Project activity continuation item is invalid",
            )
            global_id = str(UUID(item["globalId"]))
            require(
                global_id == item["globalId"] and global_id not in seen_ids,
                "Project activity continuation repeated an event",
            )
            key = (
                datetime.fromisoformat(
                    item["occurredAt"].replace("Z", "+00:00")
                ).astimezone(UTC),
                global_id,
            )
            require(
                previous_key is None or previous_key > key,
                "Project activity continuation order drifted",
            )
            previous_key = key
            seen_ids.add(global_id)
            collected.append(item)
        page_count += 1
        require(
            page_count <= 100,
            "Project activity continuation did not terminate",
        )
        next_cursor = page.body.get("nextCursor")
        if next_cursor is None:
            break
        require(
            isinstance(next_cursor, str)
            and re.fullmatch(r"[A-Za-z0-9._~:-]{1,500}", next_cursor) is not None
            and next_cursor not in seen_cursors
            and bool(items),
            "Project activity continuation cursor is invalid or cyclic",
        )
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    require(
        collected == expected_items,
        "Project activity continuation skipped or changed an event",
    )
    return {"items": len(collected), "pages": page_count}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Verify the live P4-05 Project controls, collaboration, "
            "and My Work runtime."
        )
    )
    parser.add_argument("--base-url")
    parser.add_argument(
        "--replay-only",
        action="store_true",
        help=("verify one retained actor-bound response from a second process"),
    )
    parser.add_argument(
        "--route-disable-probe",
        choices=("disabled", "recovered"),
        help=(
            "verify the persisted route switch through the restarted "
            "local HTTP server"
        ),
    )
    parser.add_argument(
        "--bench-fixture",
        choices=(
            "mark_wrong_tenant_project",
            "reassign_domain_work_item",
            "seed_terminal_my_work_projections",
            "verify_persisted_controls",
            "verify_projection_deactivation",
            "verify_projection_rebuild",
            "verify_route_disable_switch",
            "verify_runtime_schema",
            "verify_terminal_my_work_deactivation",
            "verify_transaction_rollback",
        ),
    )
    parser.add_argument("--fixture-kwargs")
    arguments = parser.parse_args()
    if arguments.bench_fixture is not None:
        require(
            arguments.base_url is None
            and not arguments.replay_only
            and arguments.route_disable_probe is None
            and isinstance(arguments.fixture_kwargs, str),
            "Controlled Bench fixture arguments are invalid",
        )
        kwargs = json.loads(arguments.fixture_kwargs)
        require(
            isinstance(kwargs, dict),
            "Controlled Bench fixture kwargs must be an object",
        )
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return
    require(
        isinstance(arguments.base_url, str) and arguments.fixture_kwargs is None,
        "The P4-05 runtime base URL is required",
    )
    require(
        CALLER_SUPPLIED_FIXTURE_RUN_ID is not None,
        f"{FIXTURE_RUN_ID_ENV} is required for a controlled runtime run",
    )
    if arguments.route_disable_probe is not None:
        require(
            not arguments.replay_only,
            "Route-disable probe mode cannot replay a command",
        )
        evidence = verify_route_disable_http_probe(
            arguments.base_url,
            expected_mode=arguments.route_disable_probe,
        )
        print(json.dumps(evidence, sort_keys=True))
        print(
            "local Frappe Project collaboration route-disable "
            f"{arguments.route_disable_probe} probe passed"
        )
        return

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
    if arguments.replay_only:
        replay = verify_cross_process_replay(
            administrator,
            arguments.base_url,
            fixture_password,
        )
        print(
            json.dumps(
                {
                    "fixtureRevision": FIXTURE_REVISION,
                    "fixtureRunId": FIXTURE_RUN_ID,
                    "mode": "replay-only",
                    "tenantId": TENANT_ID,
                    **replay,
                },
                sort_keys=True,
            )
        )
        print(
            "local Frappe Project controls cross-process replay " "verification passed"
        )
        return

    schema = run_bench_fixture(
        "verify_runtime_schema",
        {"fixture_run_id": FIXTURE_RUN_ID},
    )
    fixture_absence = verify_fresh_fixture_namespace(
        administrator,
        arguments.base_url,
    )
    created_users: list[str] = []
    controlled_history_retained = False
    try:
        for user_id, label in (
            (evidence_runtime.OWNER_USER, "Control owner"),
            (evidence_runtime.REVIEWER_USER, "Control reviewer"),
            (evidence_runtime.UNRELATED_USER, "Unrelated internal"),
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
            enable_transport_role_and_utc(
                administrator,
                arguments.base_url,
                administrator_csrf,
                user_id,
            )

        owner = login(
            arguments.base_url,
            evidence_runtime.OWNER_USER,
            fixture_password,
        )
        reviewer = login(
            arguments.base_url,
            evidence_runtime.REVIEWER_USER,
            fixture_password,
        )
        unrelated = login(
            arguments.base_url,
            evidence_runtime.UNRELATED_USER,
            fixture_password,
        )
        owner_csrf = bootstrap_csrf(
            owner,
            arguments.base_url,
            evidence_runtime.OWNER_USER,
        )
        bootstrap_csrf(
            reviewer,
            arguments.base_url,
            evidence_runtime.REVIEWER_USER,
        )
        unrelated_csrf = bootstrap_csrf(
            unrelated,
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
        main_project_id, main_gate_id = evidence_runtime.create_project(
            administrator,
            arguments.base_url,
            administrator_csrf,
            owner_user_id=evidence_runtime.OWNER_USER,
            business_code=MAIN_BUSINESS_CODE,
            title=(f"Synthetic {FIXTURE_NAMESPACE} Project controls Project"),
            idempotency_key=evidence_runtime.PROJECT_CREATE_KEY,
        )
        controlled_history_retained = True
        terminal_project_id, terminal_gate_id = evidence_runtime.create_project(
            administrator,
            arguments.base_url,
            administrator_csrf,
            owner_user_id=evidence_runtime.OWNER_USER,
            business_code=TERMINAL_BUSINESS_CODE,
            title=(f"Synthetic {FIXTURE_NAMESPACE} terminal Project"),
            idempotency_key=TERMINAL_PROJECT_CREATE_KEY,
        )
        tenant_guard_project_id, _tenant_guard_gate_id = (
            evidence_runtime.create_project(
                administrator,
                arguments.base_url,
                administrator_csrf,
                owner_user_id=evidence_runtime.OWNER_USER,
                business_code=TENANT_GUARD_BUSINESS_CODE,
                title=(f"Synthetic {FIXTURE_NAMESPACE} tenant guard Project"),
                idempotency_key=TENANT_GUARD_PROJECT_CREATE_KEY,
            )
        )
        run_bench_fixture(
            "mark_wrong_tenant_project",
            {
                "fixture_run_id": FIXTURE_RUN_ID,
                "project_id": tenant_guard_project_id,
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
            main_project_id,
            work_policy_ref,
            administrator_csrf,
        )
        evidence_runtime.apply_plan(
            administrator,
            arguments.base_url,
            main_project_id,
            work_policy_ref,
            administrator_csrf,
            expected_version=2,
            item_id=evidence_runtime.MAIN_WBS_ID,
            code="1.50",
            title="Synthetic exact P4-05 control work",
            owner_role_id=evidence_runtime.OWNER_ROLE_ID,
            idempotency_key=evidence_runtime.MAIN_PLAN_KEY,
        )
        configure_terminal_team(
            administrator,
            arguments.base_url,
            terminal_project_id,
            work_policy_ref,
            administrator_csrf,
        )
        item_ids = create_domain_items(
            administrator,
            arguments.base_url,
            administrator_csrf,
            project_id=main_project_id,
            gate_id=main_gate_id,
            work_policy_ref=work_policy_ref,
        )
        evidence_runtime.run_bench_fixture(
            "seed_private_file_revisions",
            {
                "main_project_id": main_project_id,
                "cross_project_id": terminal_project_id,
                "fixture_run_id": FIXTURE_RUN_ID,
            },
        )
        pending_main_file = evidence_runtime.validate_file_revision(
            administrator,
            arguments.base_url,
            evidence_runtime.FILE_REVISION_ID,
            main_project_id,
        )
        evidence_runtime.run_bench_fixture(
            "observe_private_file_scan",
            {
                "fixture_run_id": FIXTURE_RUN_ID,
                "scan_state": "clean",
            },
        )
        main_file_result = get_resource(
            administrator,
            arguments.base_url,
            "NPI File Revision",
            evidence_runtime.FILE_REVISION_ID,
        )
        main_file = main_file_result.body.get("data", {})
        require(
            main_file_result.status == 200
            and main_file.get("project_global_id") == main_project_id
            and main_file.get("optimistic_version") == 2
            and main_file.get("scan_state") == "clean"
            and main_file.get("sha256") == pending_main_file.get("sha256"),
            "Clean private attachment fixture drifted",
        )

        require_unassessed_controls(
            get_controls(owner, arguments.base_url, main_project_id),
            project_id=main_project_id,
            expected_version=6,
        )
        require_unassessed_controls(
            get_controls(
                administrator,
                arguments.base_url,
                terminal_project_id,
            ),
            project_id=terminal_project_id,
            expected_version=2,
        )

        random_unavailable = get_controls(
            administrator,
            arguments.base_url,
            str(uuid4()),
        )
        unrelated_unavailable = get_controls(
            unrelated,
            arguments.base_url,
            main_project_id,
        )
        tenant_unavailable = get_controls(
            administrator,
            arguments.base_url,
            tenant_guard_project_id,
        )
        same_project_unavailable(
            unrelated_unavailable,
            random_unavailable,
        )
        same_project_unavailable(
            tenant_unavailable,
            random_unavailable,
        )
        guest = get_controls(
            urllib.request.build_opener(),
            arguments.base_url,
            main_project_id,
        )
        validate_problem(guest, 401, "AUTHENTICATION_REQUIRED")

        policy_ref = ensure_control_policy(
            administrator,
            arguments.base_url,
            administrator_csrf,
        )
        require_binding_options(
            get_controls(
                administrator,
                arguments.base_url,
                main_project_id,
            ),
            policy_ref=policy_ref,
        )
        owner_binding_view = get_controls(
            owner,
            arguments.base_url,
            main_project_id,
        )
        require(
            owner_binding_view.status == 200
            and owner_binding_view.body.get("bindingOptions") is None
            and owner_binding_view.body.get("permissions", {}).get("canBindPolicy")
            is False,
            "Non-administrator received Project Control Policy binding choices",
        )
        main_bound = bind_control_policy(
            administrator,
            arguments.base_url,
            administrator_csrf,
            project_id=main_project_id,
            expected_version=6,
            policy_ref=policy_ref,
            member_global_id=evidence_runtime.OWNER_MEMBER_ID,
            idempotency_key=MAIN_BIND_KEY,
        )
        require_bound_controls(
            main_bound,
            project_id=main_project_id,
            expected_version=7,
            policy_ref=policy_ref,
            member_global_id=evidence_runtime.OWNER_MEMBER_ID,
        )
        transaction_rollback = run_bench_fixture(
            "verify_transaction_rollback",
            {
                "fixture_run_id": FIXTURE_RUN_ID,
                "project_id": main_project_id,
            },
        )
        require(
            transaction_rollback["activityAbsent"] is True
            and transaction_rollback["auditAbsent"] is True
            and transaction_rollback["idempotencyAbsent"] is True,
            "Project control transaction rollback evidence drifted",
        )
        route_disable = run_bench_fixture(
            "verify_route_disable_switch",
            {"fixture_run_id": FIXTURE_RUN_ID},
        )
        require(
            route_disable["p405RoutesDisable"] is True
            and route_disable["priorRoutesRemainEnabled"] is True
            and route_disable["exactBooleanRequired"] is True,
            "Project collaboration route-disable evidence drifted",
        )
        terminal_bound = bind_control_policy(
            administrator,
            arguments.base_url,
            administrator_csrf,
            project_id=terminal_project_id,
            expected_version=2,
            policy_ref=policy_ref,
            member_global_id=TERMINAL_OWNER_MEMBER_ID,
            idempotency_key=TERMINAL_BIND_KEY,
        )
        require_bound_controls(
            terminal_bound,
            project_id=terminal_project_id,
            expected_version=3,
            policy_ref=policy_ref,
            member_global_id=TERMINAL_OWNER_MEMBER_ID,
        )
        terminal_projection_seed = run_bench_fixture(
            "seed_terminal_my_work_projections",
            {
                "fixture_run_id": FIXTURE_RUN_ID,
                "project_id": terminal_project_id,
                "gate_id": terminal_gate_id,
            },
        )
        require(
            terminal_projection_seed["active"] == 3,
            "Terminal My Work projection seed drifted",
        )

        direct_project_update = update_resource(
            owner,
            arguments.base_url,
            "NPI Engineering Project",
            main_project_id,
            {
                "lifecycle_state": "on_hold",
                "optimistic_version": 8,
            },
            owner_csrf,
        )
        require(
            direct_project_update.status == 403,
            "Project owner bypassed the controlled Project command route",
        )
        retained_project = get_resource(
            administrator,
            arguments.base_url,
            "NPI Engineering Project",
            main_project_id,
        )
        require(
            retained_project.status == 200
            and retained_project.body.get("data", {}).get("lifecycle_state") == "draft"
            and retained_project.body.get("data", {}).get("optimistic_version") == 7,
            "Rejected direct Project mutation changed controlled state",
        )

        red_measurements = [
            {
                "dimension": "progress",
                "numericValue": 50,
                "manualStatus": None,
            },
            {
                "dimension": "cost",
                "numericValue": 90,
                "manualStatus": None,
            },
            {
                "dimension": "quality",
                "numericValue": None,
                "manualStatus": "red",
            },
        ]
        rejected_health = command(
            owner,
            arguments.base_url,
            (f"/api/npi/v1/projects/{main_project_id}:" "assess-health"),
            {
                "expectedProjectVersion": 7,
                "measurements": red_measurements,
                "reason": None,
                "recoveryPlan": None,
            },
            csrf_token=owner_csrf,
            idempotency_key=HEALTH_REJECTED_KEY,
        )
        validate_problem(
            rejected_health,
            422,
            "VALIDATION_FAILED",
        )
        require(
            {value.get("path") for value in rejected_health.body.get("fieldErrors", [])}
            == {"reason", "recoveryPlan"},
            "Red Project health did not require reason and recovery plan",
        )
        require_no_control_receipt(
            administrator,
            arguments.base_url,
            actor=evidence_runtime.OWNER_USER,
            raw_key=HEALTH_REJECTED_KEY,
        )
        health = execute_with_replay(
            owner,
            arguments.base_url,
            (f"/api/npi/v1/projects/{main_project_id}:" "assess-health"),
            {
                "expectedProjectVersion": 7,
                "measurements": red_measurements,
                "reason": ("Progress and quality are below the synthetic threshold."),
                "recoveryPlan": (
                    "Complete the controlled corrective work and reassess."
                ),
            },
            csrf_token=owner_csrf,
            idempotency_key=HEALTH_KEY,
            expected_status=200,
            label="Red Project health assessment",
        )
        health_dimensions = {
            value["dimension"]: value for value in health["health"]["dimensions"]
        }
        require(
            health["project"]["version"] == 8
            and health["health"]["overallStatus"] == "unavailable"
            and health_dimensions["progress"]["status"] == "red"
            and health_dimensions["cost"]["status"] == "green"
            and health_dimensions["quality"]["status"] == "red"
            and health_dimensions["risk"]["status"] == "unavailable"
            and health["health"]["assessment"]["reason"]
            == ("Progress and quality are below the synthetic threshold.")
            and health["health"]["assessment"]["recoveryPlan"]
            == ("Complete the controlled corrective work and reassess."),
            "Project health did not retain red and unavailable truth",
        )

        pause_payload = {
            "expectedProjectVersion": 8,
            "action": "pause",
            "reason": "Pause the synthetic Project for controlled review.",
        }
        paused = execute_with_replay(
            owner,
            arguments.base_url,
            f"/api/npi/v1/projects/{main_project_id}:transition",
            pause_payload,
            csrf_token=owner_csrf,
            idempotency_key=PAUSE_KEY,
            expected_status=200,
            label="Project pause",
        )
        require(
            paused["project"]["state"] == "on_hold"
            and paused["project"]["version"] == 9,
            "Project pause state drifted",
        )
        resumed = execute_with_replay(
            owner,
            arguments.base_url,
            f"/api/npi/v1/projects/{main_project_id}:transition",
            {
                "expectedProjectVersion": 9,
                "action": "resume",
                "reason": ("Resume after the controlled synthetic review."),
            },
            csrf_token=owner_csrf,
            idempotency_key=RESUME_KEY,
            expected_status=200,
            label="Project resume",
        )
        require(
            resumed["project"]["state"] == "active"
            and resumed["project"]["version"] == 10,
            "Project resume state drifted",
        )
        completion = command(
            owner,
            arguments.base_url,
            f"/api/npi/v1/projects/{main_project_id}:transition",
            {
                "expectedProjectVersion": 10,
                "action": "complete",
                "reason": "This completion must remain fail closed.",
            },
            csrf_token=owner_csrf,
            idempotency_key=COMPLETE_REJECTED_KEY,
        )
        validate_problem(
            completion,
            409,
            "PROJECT_TRANSITION_PREREQUISITE_UNAVAILABLE",
        )
        require(
            {value.get("path") for value in completion.body.get("fieldErrors", [])}
            == {"prerequisites.cost", "prerequisites.handover"},
            "Completion did not expose unavailable server-owned readiness",
        )
        require_no_control_receipt(
            administrator,
            arguments.base_url,
            actor=evidence_runtime.OWNER_USER,
            raw_key=COMPLETE_REJECTED_KEY,
        )

        cancelled = execute_with_replay(
            owner,
            arguments.base_url,
            f"/api/npi/v1/projects/{terminal_project_id}:transition",
            {
                "expectedProjectVersion": 3,
                "action": "cancel",
                "reason": ("Cancel this dedicated terminal-history fixture."),
            },
            csrf_token=owner_csrf,
            idempotency_key=TERMINAL_CANCEL_KEY,
            expected_status=200,
            label="Project cancel",
        )
        require(
            cancelled["project"]["state"] == "cancelled"
            and cancelled["project"]["version"] == 4
            and all(
                value["available"] is False
                and value["reasonCode"] == "project_terminal"
                for value in cancelled["lifecycleActions"]
            ),
            "Cancelled Project did not become protected history",
        )
        terminal_projection_deactivation = run_bench_fixture(
            "verify_terminal_my_work_deactivation",
            {
                "fixture_run_id": FIXTURE_RUN_ID,
                "project_id": terminal_project_id,
                "assignment_global_ids": terminal_projection_seed["globalIds"],
            },
        )
        terminal_my_work = require_my_work_page(
            my_work(
                owner,
                arguments.base_url,
                view="all",
                project_id=terminal_project_id,
            ),
            expected_count=0,
            expected_time_zone="UTC",
        )
        require(
            terminal_projection_deactivation["deactivated"] == 3
            and terminal_my_work["items"] == [],
            "Terminal Project remained visible in My Work",
        )

        main_wbs_version, main_wbs_hash = evidence_runtime.exact_wbs(
            administrator,
            arguments.base_url,
            evidence_runtime.MAIN_WBS_ID,
        )
        freeze = evidence_runtime.freeze_requirements(
            administrator,
            arguments.base_url,
            main_project_id,
            main_gate_id,
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
            main_project_id,
            main_gate_id,
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
            f"Gate WBS evidence returned HTTP {wbs_attach.status}",
        )
        review_policy_hash = review_runtime.ensure_review_policy(
            administrator,
            arguments.base_url,
            administrator_csrf,
            gate_template_hash,
        )
        started = review_runtime.start_review(
            administrator,
            arguments.base_url,
            main_project_id,
            main_gate_id,
            {
                "expectedGateVersion": 3,
                "policyGlobalId": review_runtime.POLICY_ID,
                "policyVersion": review_runtime.POLICY_VERSION,
                "policySnapshotHash": review_policy_hash,
                "bindings": review_runtime.review_bindings(),
            },
            csrf_token=administrator_csrf,
            idempotency_key=review_runtime.START_KEY,
        )
        started_body = review_runtime.require_fresh_command(
            started,
            201,
            "Gate review start",
        )
        cycle = started_body.get("activeCycle", {})
        require(
            started_body.get("gate", {}).get("reviewState") == "in_review"
            and cycle.get("version") == 1
            and len(cycle.get("selectedSteps", [])) == 1,
            "Started Gate review assignment drifted",
        )
        cycle_id = str(cycle["globalId"])
        cycle_input_hash = str(cycle["inputHash"])

        verify_terminal_guards(
            administrator,
            owner,
            arguments.base_url,
            administrator_csrf=administrator_csrf,
            owner_csrf=owner_csrf,
            project_id=terminal_project_id,
            gate_id=terminal_gate_id,
            work_policy_ref=work_policy_ref,
            review_policy_hash=review_policy_hash,
        )

        csrf_rejected = command(
            owner,
            arguments.base_url,
            f"/api/npi/v1/projects/{main_project_id}:follow",
            {"expectedVersion": 0},
            csrf_token=None,
            idempotency_key=CSRF_REJECTED_KEY,
        )
        validate_problem(
            csrf_rejected,
            403,
            "CSRF_TOKEN_INVALID",
        )
        require_no_control_receipt(
            administrator,
            arguments.base_url,
            actor=evidence_runtime.OWNER_USER,
            raw_key=CSRF_REJECTED_KEY,
        )
        idor_comment = command(
            unrelated,
            arguments.base_url,
            f"/api/npi/v1/projects/{main_project_id}/comments",
            {
                "body": "This IDOR write must not disclose the Project.",
                "mentions": [],
                "attachments": [],
                "objectLinks": [],
            },
            csrf_token=unrelated_csrf,
            idempotency_key=IDOR_COMMENT_KEY,
        )
        same_project_unavailable(idor_comment, random_unavailable)
        require_no_control_receipt(
            administrator,
            arguments.base_url,
            actor=evidence_runtime.UNRELATED_USER,
            raw_key=IDOR_COMMENT_KEY,
        )
        cross_comment = command(
            owner,
            arguments.base_url,
            f"/api/npi/v1/projects/{main_project_id}/comments",
            {
                "body": ("This cross-Project attachment must be rejected."),
                "mentions": [],
                "attachments": [
                    {
                        "globalId": (evidence_runtime.CROSS_FILE_REVISION_ID),
                        "version": 1,
                    }
                ],
                "objectLinks": [],
            },
            csrf_token=owner_csrf,
            idempotency_key=CROSS_COMMENT_KEY,
        )
        validate_problem(
            cross_comment,
            422,
            "VALIDATION_FAILED",
        )
        require_no_control_receipt(
            administrator,
            arguments.base_url,
            actor=evidence_runtime.OWNER_USER,
            raw_key=CROSS_COMMENT_KEY,
        )

        my_work_evidence = verify_my_work_projection(
            owner,
            administrator,
            unrelated,
            arguments.base_url,
            project_id=main_project_id,
            gate_id=main_gate_id,
            item_ids=item_ids,
            administrator_time_zone=str(schema["administratorTimeZone"]),
        )

        shared_payload = comment_payload(
            work_item_id=item_ids["risk"],
        )
        owner_comment = execute_with_replay(
            owner,
            arguments.base_url,
            f"/api/npi/v1/projects/{main_project_id}/comments",
            shared_payload,
            csrf_token=owner_csrf,
            idempotency_key=SHARED_COMMENT_KEY,
            expected_status=201,
            label="Owner contextual comment",
        )
        administrator_comment = execute_with_replay(
            administrator,
            arguments.base_url,
            f"/api/npi/v1/projects/{main_project_id}/comments",
            shared_payload,
            csrf_token=administrator_csrf,
            idempotency_key=SHARED_COMMENT_KEY,
            expected_status=201,
            label="Administrator contextual comment",
        )
        require(
            owner_comment["globalId"] != administrator_comment["globalId"]
            and owner_comment["actorUserId"] == evidence_runtime.OWNER_USER
            and administrator_comment["actorUserId"] == "Administrator"
            and owner_comment["detail"]["attachments"][0]["globalId"]
            == evidence_runtime.FILE_REVISION_ID
            and owner_comment["detail"]["objectLinks"][0]["target"]
            == {
                "kind": "project_work_item",
                "projectId": main_project_id,
                "workItemId": item_ids["risk"],
            },
            "Actor-bound contextual comment projections drifted",
        )
        serialized_comment = json.dumps(
            owner_comment,
            sort_keys=True,
        ).casefold()
        require(
            "/private/files/" not in serialized_comment
            and '"url"' not in serialized_comment
            and "file_url" not in serialized_comment,
            "Contextual comment exposed a private File URL",
        )
        require_control_receipt(
            administrator,
            arguments.base_url,
            actor=evidence_runtime.OWNER_USER,
            raw_key=SHARED_COMMENT_KEY,
            operation="project.comment.add",
            expected_body=owner_comment,
        )
        require_control_receipt(
            administrator,
            arguments.base_url,
            actor="Administrator",
            raw_key=SHARED_COMMENT_KEY,
            operation="project.comment.add",
            expected_body=administrator_comment,
        )

        followed = execute_with_replay(
            owner,
            arguments.base_url,
            f"/api/npi/v1/projects/{main_project_id}:follow",
            {"expectedVersion": 0},
            csrf_token=owner_csrf,
            idempotency_key=FOLLOW_KEY,
            expected_status=200,
            label="Project follow",
        )
        unfollowed = execute_with_replay(
            owner,
            arguments.base_url,
            f"/api/npi/v1/projects/{main_project_id}:unfollow",
            {"expectedVersion": 1},
            csrf_token=owner_csrf,
            idempotency_key=UNFOLLOW_KEY,
            expected_status=200,
            label="Project unfollow",
        )
        require(
            followed["following"] is True
            and followed["version"] == 1
            and unfollowed["following"] is False
            and unfollowed["version"] == 2,
            "Project follow lifecycle drifted",
        )

        learning = execute_with_replay(
            owner,
            arguments.base_url,
            f"/api/npi/v1/projects/{main_project_id}/learning",
            {
                "kind": "template_improvement",
                "title": "Retain an explicit recovery-plan prompt",
                "content": (
                    "The synthetic retrospective found that red health "
                    "requires explicit recovery context."
                ),
                "recommendation": (
                    "Propose this prompt for a future template version."
                ),
                "tags": ["health", "recovery"],
            },
            csrf_token=owner_csrf,
            idempotency_key=LEARNING_KEY,
            expected_status=201,
            label="Project learning",
        )
        require(
            learning["projectGlobalId"] == main_project_id
            and learning["kind"] == "template_improvement"
            and learning["tags"] == ["health", "recovery"]
            and learning["target"]
            == {
                "kind": "project_learning",
                "projectId": main_project_id,
                "learningId": learning["globalId"],
            },
            "Project learning did not retain a typed proposed target",
        )
        project_learning = npi_request(
            owner,
            arguments.base_url,
            (
                f"/api/npi/v1/projects/{main_project_id}/learning?"
                + urllib.parse.urlencode(
                    {
                        "kind": "template_improvement",
                        "search": "recovery-plan",
                        "limit": 10,
                    }
                )
            ),
        )
        require(
            project_learning.status == 200
            and project_learning.body
            == {
                "projectId": main_project_id,
                "items": [learning],
                "permissions": {"canCreate": True},
            },
            "Project learning query drifted",
        )
        exact_project_learning = npi_request(
            owner,
            arguments.base_url,
            (
                f"/api/npi/v1/projects/{main_project_id}/learning?"
                + urllib.parse.urlencode(
                    {
                        "learningId": learning["globalId"],
                        "limit": 1,
                    }
                )
            ),
        )
        require(
            exact_project_learning.status == 200
            and exact_project_learning.body
            == {
                "projectId": main_project_id,
                "items": [learning],
                "permissions": {"canCreate": True},
            },
            "Exact Project learning target was not reachable",
        )
        global_learning = npi_request(
            owner,
            arguments.base_url,
            "/api/npi/v1/learning?"
            + urllib.parse.urlencode(
                {
                    "kind": "template_improvement",
                    "tag": "recovery",
                    "search": "future template",
                    "projectId": main_project_id,
                    "templateGlobalId": (evidence_runtime.PROJECT_TEMPLATE_ID),
                    "templateVersion": 1,
                    "limit": 10,
                }
            ),
        )
        require(
            global_learning.status == 200
            and global_learning.body == {"items": [learning]},
            "Global accessible Project learning query drifted",
        )
        unrelated_learning = npi_request(
            unrelated,
            arguments.base_url,
            "/api/npi/v1/learning?kind=template_improvement&limit=10",
        )
        require(
            unrelated_learning.status == 200
            and unrelated_learning.body == {"items": []},
            "Project learning search disclosed an inaccessible Project",
        )

        activity = npi_request(
            owner,
            arguments.base_url,
            f"/api/npi/v1/projects/{main_project_id}/activity?limit=100",
        )
        require(
            activity.status == 200
            and activity.body.get("projectId") == main_project_id
            and activity.body.get("following") is False
            and activity.body.get("followerVersion") == 2
            and activity.body.get("permissions")
            == {"canComment": True, "canFollow": True},
            "Project activity or follower projection drifted",
        )
        activity_types = {
            value.get("eventType") for value in activity.body.get("items", [])
        }
        require(
            {
                "comment_added",
                "followed",
                "unfollowed",
                "health_assessed",
                "lifecycle_transition",
                "learning_created",
            }
            <= activity_types,
            "Project activity timeline is incomplete",
        )
        require_comment_options(
            activity.body.get("commentOptions"),
            project_id=main_project_id,
            gate_id=main_gate_id,
            item_ids=item_ids,
            learning_id=learning["globalId"],
            attachment_sha256=main_file["sha256"],
        )
        serialized_activity = json.dumps(
            activity.body,
            sort_keys=True,
        ).casefold()
        require(
            "/private/files/" not in serialized_activity
            and '"url"' not in serialized_activity
            and "file_url" not in serialized_activity,
            "Project activity timeline exposed a private URL",
        )
        activity_pagination = require_activity_cursor_chain(
            owner,
            arguments.base_url,
            project_id=main_project_id,
            expected_items=activity.body.get("items", []),
        )

        reviewed = review_runtime.submit_review(
            owner,
            arguments.base_url,
            main_project_id,
            main_gate_id,
            cycle_id,
            {
                "expectedCycleVersion": 1,
                "expectedInputHash": cycle_input_hash,
                "stepKey": review_runtime.REVIEW_STEP_KEY,
                "outcome": "approved",
                "opinion": ("Approved for the exact My Work deactivation fixture."),
            },
            csrf_token=owner_csrf,
            idempotency_key=review_runtime.REVIEW_KEY,
        )
        review_runtime.require_fresh_command(
            reviewed,
            201,
            "Gate review opinion",
        )
        after_review = require_my_work_page(
            my_work(owner, arguments.base_url, view="all"),
            expected_count=4,
            expected_time_zone="UTC",
        )
        require(
            {
                value["why"]
                for value in after_review["items"]
                if value["source"]["globalId"] == main_gate_id
            }
            == {"gate_final_decision"}
            and after_review["counts"]["approvals"]["value"] == 1,
            "Completed Gate review step did not retain the exact final decision authority",
        )

        reassignment = run_bench_fixture(
            "reassign_domain_work_item",
            {
                "fixture_run_id": FIXTURE_RUN_ID,
                "project_id": main_project_id,
                "work_item_id": item_ids["action"],
            },
        )
        require(
            reassignment["activeActor"] == evidence_runtime.REVIEWER_USER,
            "Domain Work Item reassignment evidence drifted",
        )
        owner_after_reassignment = require_my_work_page(
            my_work(owner, arguments.base_url, view="all"),
            expected_count=3,
            expected_time_zone="UTC",
        )
        require(
            {value["source"]["globalId"] for value in owner_after_reassignment["items"]}
            == {
                item_ids["risk"],
                item_ids["decision_request"],
                main_gate_id,
            },
            "Old Domain Work Item owner retained reassigned work",
        )
        reviewer_after_reassignment = require_my_work_page(
            my_work(reviewer, arguments.base_url, view="all"),
            expected_count=0,
            expected_time_zone="UTC",
        )
        require(
            reviewer_after_reassignment["items"] == [],
            (
                "Source assignment widened the Project Work target "
                "authorization boundary"
            ),
        )
        projection_deactivation = run_bench_fixture(
            "verify_projection_deactivation",
            {
                "fixture_run_id": FIXTURE_RUN_ID,
                "gate_id": main_gate_id,
                "work_item_id": item_ids["action"],
            },
        )
        projection_rebuild = run_bench_fixture(
            "verify_projection_rebuild",
            {"fixture_run_id": FIXTURE_RUN_ID},
        )
        persisted = run_bench_fixture(
            "verify_persisted_controls",
            {
                "fixture_run_id": FIXTURE_RUN_ID,
                "main_project_id": main_project_id,
                "terminal_project_id": terminal_project_id,
                "risk_id": item_ids["risk"],
            },
        )

        print(
            json.dumps(
                {
                    "actorBoundReceipts": 2,
                    "activityEventTypes": sorted(activity_types),
                    "activityPagination": activity_pagination,
                    "compatibilityUnassessed": True,
                    "completionFailClosed": True,
                    "fixtureRevision": FIXTURE_REVISION,
                    "fixtureRunId": FIXTURE_RUN_ID,
                    "fixtureStatesBeforeWrite": fixture_absence,
                    "health": {
                        "overall": "unavailable",
                        "redDimensions": ["progress", "quality"],
                    },
                    "mainProjectId": main_project_id,
                    "migrationSchema": schema,
                    "myWork": my_work_evidence,
                    "persisted": persisted,
                    "productionErpnextConnected": False,
                    "projectionDeactivation": projection_deactivation,
                    "projectionRebuild": projection_rebuild,
                    "routeDisableRecovery": route_disable,
                    "retainedLocalFixtureUsers": created_users,
                    "tenantId": TENANT_ID,
                    "terminalLegacyGuards": 3,
                    "terminalMyWork": terminal_projection_deactivation,
                    "terminalProjectId": terminal_project_id,
                    "transactionRollback": transaction_rollback,
                    "typedCollaboration": True,
                },
                sort_keys=True,
            )
        )
        print(
            "local Frappe Project controls and My Work runtime " "verification passed"
        )
    except Exception:
        if not controlled_history_retained:
            for user_id in reversed(created_users):
                try:
                    delete_disposable_user(
                        administrator,
                        arguments.base_url,
                        user_id,
                        administrator_csrf,
                    )
                except Exception:
                    pass
        raise


if __name__ == "__main__":
    main()
