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
    delete_resource,
    get_resource,
    list_resources,
    post_project,
    update_resource,
)


FIXTURE_REVISION = 1
FIXTURE_RUN_ID_ENV = "NPI_GATE_EVIDENCE_RUNTIME_RUN_ID"
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
FIXTURE_PREFIX = f"p4-03-runtime-{FIXTURE_NAMESPACE}"


def fixture_id(scope: str) -> str:
    return str(
        uuid5(
            NAMESPACE_URL,
            (
                "https://npi-one.example.invalid/runtime/p4-03/"
                f"{FIXTURE_NAMESPACE}/{scope}"
            ),
        )
    )


GATE_TEMPLATE_ID = fixture_id("gate-template")
GATE_TEMPLATE_VERSION = 1
GATE_TEMPLATE_VERSION_KEY = f"{GATE_TEMPLATE_ID}:{GATE_TEMPLATE_VERSION}"
PROJECT_TEMPLATE_ID = fixture_id("project-template")
PROJECT_TEMPLATE_VERSION = 1
PROJECT_TEMPLATE_VERSION_KEY = f"{PROJECT_TEMPLATE_ID}:{PROJECT_TEMPLATE_VERSION}"
DISABLED_BINDING_TEMPLATE_ID = fixture_id("disabled-binding-project-template")
DISABLED_BINDING_VERSION_KEY = f"{DISABLED_BINDING_TEMPLATE_ID}:1"
WORK_POLICY_ID = fixture_id("work-policy")
WORK_POLICY_VERSION = 1
WORK_POLICY_VERSION_KEY = f"{WORK_POLICY_ID}:{WORK_POLICY_VERSION}"
OWNER_MEMBER_ID = fixture_id("member-owner")
REVIEWER_MEMBER_ID = fixture_id("member-reviewer")
OWNER_ROLE_ID = fixture_id("role-owner")
PROJECT_RACI_ID = fixture_id("raci-project")
MAIN_WBS_ID = fixture_id("main-wbs")
CROSS_WBS_ID = fixture_id("cross-wbs")
FILE_REVISION_ID = fixture_id("file-revision")
CROSS_FILE_REVISION_ID = fixture_id("cross-file-revision")
WRONG_TENANT_FILE_REVISION_ID = fixture_id("wrong-tenant-file-revision")
DOCUMENT_ID = fixture_id("document")
CROSS_DOCUMENT_ID = fixture_id("cross-document")

OWNER_USER = f"npi-gate-{FIXTURE_NAMESPACE}-owner@example.invalid"
REVIEWER_USER = f"npi-gate-{FIXTURE_NAMESPACE}-reviewer@example.invalid"
UNRELATED_USER = f"npi-gate-{FIXTURE_NAMESPACE}-unrelated@example.invalid"
BUSINESS_CODE = f"P4-03-{FIXTURE_RUN_ID[:16].upper()}-MAIN"
CROSS_BUSINESS_CODE = f"P4-03-{FIXTURE_RUN_ID[:16].upper()}-CROSS"
GATE_TEMPLATE_CODE = f"GATE-{FIXTURE_RUN_ID[:16].upper()}"
PROJECT_TEMPLATE_CODE = f"P403-{FIXTURE_RUN_ID[:16].upper()}"
DISABLED_BINDING_TEMPLATE_CODE = f"P403-D-{FIXTURE_RUN_ID[:12].upper()}"
WORK_POLICY_KEY = f"p403_{FIXTURE_RUN_ID}"
ROLE_KEY = "gate_owner"
WBS_STATE_KEY = "not_started"
REQUIREMENT_WBS = "design_ready"
REQUIREMENT_FILE = "controlled_file"

PROJECT_CREATE_KEY = f"{FIXTURE_PREFIX}-project-create"
CROSS_PROJECT_CREATE_KEY = f"{FIXTURE_PREFIX}-cross-project-create"
TEAM_KEY = f"{FIXTURE_PREFIX}-team"
MAIN_PLAN_KEY = f"{FIXTURE_PREFIX}-main-plan"
CROSS_PLAN_KEY = f"{FIXTURE_PREFIX}-cross-plan"
FREEZE_KEY = f"{FIXTURE_PREFIX}-freeze"
WBS_ATTACH_KEY = f"{FIXTURE_PREFIX}-attach-wbs"
FILE_ATTACH_KEY = f"{FIXTURE_PREFIX}-attach-file"
FREEZE_AGAIN_KEY = f"{FIXTURE_PREFIX}-freeze-again"
STALE_ATTACH_KEY = f"{FIXTURE_PREFIX}-stale-attach"
CROSS_WBS_ATTACH_KEY = f"{FIXTURE_PREFIX}-cross-wbs"
CROSS_FILE_ATTACH_KEY = f"{FIXTURE_PREFIX}-cross-file"
OWNER_ATTACH_KEY = f"{FIXTURE_PREFIX}-owner-denied"


def canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def json_value(value: object) -> object:
    return json.loads(value) if isinstance(value, str) else value


def fixture_request_id(key: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{FIXTURE_PREFIX}/request/{key}"))


def fixture_trace_id(key: str) -> str:
    return f"trace-{uuid5(NAMESPACE_URL, f'{FIXTURE_PREFIX}/trace/{key}').hex}"


def command_headers(
    csrf_token: str | None,
    idempotency_key: str,
) -> dict[str, str]:
    headers = {
        "Idempotency-Key": idempotency_key,
        "X-Request-ID": fixture_request_id(idempotency_key),
        "X-Trace-ID": fixture_trace_id(idempotency_key),
    }
    if csrf_token is not None:
        headers["X-Frappe-CSRF-Token"] = csrf_token
    return headers


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
    headers: dict[str, str]
    if idempotency_key is None:
        request_id = str(uuid4())
        headers = {
            "X-Request-ID": request_id,
            "X-Trace-ID": f"trace-{uuid4().hex}",
        }
    else:
        headers = command_headers(csrf_token, idempotency_key)
        request_id = headers["X-Request-ID"]
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


def create_internal_user(
    administrator,
    base_url: str,
    user_id: str,
    password: str,
    csrf_token: str,
    label: str,
) -> None:
    existing = request(administrator, base_url, user_resource_path(user_id))
    require(existing.status == 404, f"Fresh fixture user already exists: {user_id}")
    created = create_resource(
        administrator,
        base_url,
        "User",
        {
            "email": user_id,
            "enabled": 1,
            "first_name": f"NPI Gate {label}",
            "language": "en",
            "last_name": "Runtime",
            "new_password": password,
            "roles": [{"role": "Desk User"}],
            "send_welcome_email": 0,
            "user_type": "System User",
        },
        csrf_token,
    )
    require(
        created.status in {200, 201},
        f"Internal fixture user creation returned HTTP {created.status}",
    )
    try:
        retained = request(administrator, base_url, user_resource_path(user_id))
        data = retained.body.get("data", {})
        roles = {
            row.get("role")
            for row in data.get("roles", [])
            if isinstance(row, dict)
        }
        require(
            retained.status == 200
            and data.get("name") == user_id
            and data.get("enabled") == 1
            and data.get("user_type") == "System User"
            and "Desk User" in roles
            and "System Manager" not in roles,
            f"Internal fixture user boundary drifted: {user_id}",
        )
    except Exception:
        delete_disposable_user(
            administrator,
            base_url,
            user_id,
            csrf_token,
        )
        raise


def gate_template_payload() -> dict[str, object]:
    return {
        "gate_template": GATE_TEMPLATE_ID,
        "gate_template_version": GATE_TEMPLATE_VERSION,
        "title": f"Synthetic {FIXTURE_NAMESPACE} Gate Template",
        "publication_state": "published",
        "applicable_project_types": ["new_tool"],
        "requirements": [
            {
                "requirement_key": REQUIREMENT_WBS,
                "title": "Design work item is exact",
                "classification": "required",
                "priority": "P0",
                "allowed_evidence_kinds": ["wbs_item"],
            },
            {
                "requirement_key": REQUIREMENT_FILE,
                "title": "Controlled private file is scanned",
                "classification": "required",
                "priority": "P1",
                "allowed_evidence_kinds": ["file_revision"],
            },
        ],
    }


def ensure_gate_template(
    administrator,
    base_url: str,
    csrf_token: str,
) -> str:
    root = create_resource(
        administrator,
        base_url,
        "NPI Gate Template",
        {
            "global_id": GATE_TEMPLATE_ID,
            "template_code": GATE_TEMPLATE_CODE,
            "title": f"Synthetic {FIXTURE_NAMESPACE} Gate Template",
            "enabled": 1,
        },
        csrf_token,
    )
    require(
        root.status in {200, 201},
        f"Gate Template root returned HTTP {root.status}",
    )
    version = create_resource(
        administrator,
        base_url,
        "NPI Gate Template Version",
        gate_template_payload(),
        csrf_token,
    )
    require(
        version.status in {200, 201},
        f"Gate Template version returned HTTP {version.status}",
    )
    data = version.body.get("data", {})
    snapshot_hash = data.get("snapshot_hash")
    require(
        data.get("name") == GATE_TEMPLATE_VERSION_KEY
        and data.get("publication_state") == "published"
        and data.get("optimistic_version") == 1
        and isinstance(snapshot_hash, str)
        and re.fullmatch(r"[a-f0-9]{64}", snapshot_hash) is not None,
        "Published Gate Template identity or hash drifted",
    )
    return str(snapshot_hash)


def project_template_version_payload(
    project_template_id: str,
    snapshot_hash: str,
    *,
    title_suffix: str = "",
) -> dict[str, object]:
    return {
        "project_template": project_template_id,
        "template_version": PROJECT_TEMPLATE_VERSION,
        "title": (
            f"Synthetic {FIXTURE_NAMESPACE} Project Template{title_suffix}"
        ),
        "publication_state": "published",
        "applicable_project_types": ["new_tool"],
        "reference_rules": [],
        "gates": [
            {
                "gate_key": "G1",
                "title": "Synthetic Gate evidence review",
                "sequence": 1,
                "gate_template_global_id": GATE_TEMPLATE_ID,
                "gate_template_version": GATE_TEMPLATE_VERSION,
                "gate_template_snapshot_hash": snapshot_hash,
            }
        ],
    }


def ensure_project_template(
    administrator,
    base_url: str,
    csrf_token: str,
    gate_template_hash: str,
) -> str:
    root = create_resource(
        administrator,
        base_url,
        "NPI Project Template",
        {
            "global_id": PROJECT_TEMPLATE_ID,
            "template_code": PROJECT_TEMPLATE_CODE,
            "title": f"Synthetic {FIXTURE_NAMESPACE} Project Template",
            "enabled": 1,
        },
        csrf_token,
    )
    require(
        root.status in {200, 201},
        f"Project Template root returned HTTP {root.status}",
    )
    version = create_resource(
        administrator,
        base_url,
        "NPI Project Template Version",
        project_template_version_payload(
            PROJECT_TEMPLATE_ID,
            gate_template_hash,
        ),
        csrf_token,
    )
    require(
        version.status in {200, 201},
        f"Project Template version returned HTTP {version.status}",
    )
    data = version.body.get("data", {})
    snapshot_hash = data.get("snapshot_hash")
    require(
        data.get("name") == PROJECT_TEMPLATE_VERSION_KEY
        and data.get("publication_state") == "published"
        and isinstance(snapshot_hash, str)
        and re.fullmatch(r"[a-f0-9]{64}", snapshot_hash) is not None,
        "Published Project Template identity or hash drifted",
    )
    return str(snapshot_hash)


def project_payload(
    owner_user_id: str,
    *,
    business_code: str,
    title: str,
) -> dict[str, object]:
    return {
        "tenantId": TENANT_ID,
        "businessCode": business_code,
        "title": title,
        "projectType": "new_tool",
        "ownerUserId": owner_user_id,
        "targetSop": "2027-01-31",
        "templateGlobalId": PROJECT_TEMPLATE_ID,
        "templateVersion": PROJECT_TEMPLATE_VERSION,
        "expectedVersion": 1,
        "references": [],
    }


def create_project(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    owner_user_id: str,
    business_code: str,
    title: str,
    idempotency_key: str,
) -> tuple[str, str]:
    payload = project_payload(
        owner_user_id,
        business_code=business_code,
        title=title,
    )
    result = post_project(
        administrator,
        base_url,
        payload,
        csrf_token=csrf_token,
        idempotency_key=idempotency_key,
        request_id=fixture_request_id(idempotency_key),
    )
    require(
        result.status == 201
        and result.headers.get("Idempotency-Replayed") == "false",
        f"Project creation returned HTTP {result.status} or replayed",
    )
    project = result.body.get("project", {})
    gates = result.body.get("gates", [])
    require(
        isinstance(project, dict)
        and isinstance(gates, list)
        and len(gates) == 1
        and gates[0].get("key") == "G1",
        "Configured Project or Gate shell is incomplete",
    )
    project_id = project.get("globalId")
    gate_id = gates[0].get("globalId")
    require(
        isinstance(project_id, str) and isinstance(gate_id, str),
        "Project or Gate identity is unavailable",
    )
    replay = post_project(
        administrator,
        base_url,
        payload,
        csrf_token=csrf_token,
        idempotency_key=idempotency_key,
        request_id=fixture_request_id(idempotency_key),
    )
    require(
        replay.status == 201
        and replay.headers.get("Idempotency-Replayed") == "true"
        and replay.body == result.body,
        "Project creation did not replay its sealed response",
    )
    return project_id, gate_id


def work_policy_payload() -> dict[str, object]:
    return {
        "policy_global_id": WORK_POLICY_ID,
        "policy_key": WORK_POLICY_KEY,
        "policy_version": WORK_POLICY_VERSION,
        "title": f"Synthetic {FIXTURE_NAMESPACE} work policy",
        "publication_state": "published",
        "role_keys": [ROLE_KEY],
        "wbs_states": {
            "initialStateKey": WBS_STATE_KEY,
            "states": [
                {
                    "key": WBS_STATE_KEY,
                    "labelSource": "Not started",
                    "terminal": False,
                }
            ],
        },
        "work_item_lifecycles": [
            {
                "kind": kind,
                "initialStateKey": state,
                "states": [
                    {
                        "key": state,
                        "labelSource": label,
                        "terminal": False,
                    }
                ],
            }
            for kind, state, label in (
                ("risk", "risk_open", "Identified"),
                ("issue", "issue_open", "Open"),
                ("action", "action_open", "Open"),
                ("decision_request", "decision_open", "Requested"),
            )
        ],
    }


def ensure_work_policy(
    administrator,
    base_url: str,
    csrf_token: str,
) -> dict[str, object]:
    payload = work_policy_payload()
    result = create_resource(
        administrator,
        base_url,
        "NPI Project Work Policy Version",
        payload,
        csrf_token,
    )
    require(
        result.status in {200, 201},
        f"Work Policy version returned HTTP {result.status}",
    )
    data = result.body.get("data", {})
    snapshot_hash = data.get("snapshot_hash")
    require(
        data.get("name") == WORK_POLICY_VERSION_KEY
        and isinstance(snapshot_hash, str)
        and re.fullmatch(r"[a-f0-9]{64}", snapshot_hash) is not None,
        "Work Policy identity or hash drifted",
    )
    return {
        "globalId": WORK_POLICY_ID,
        "version": WORK_POLICY_VERSION,
        "snapshotHash": snapshot_hash,
    }


def post_work_command(
    opener,
    base_url: str,
    project_id: str,
    action: str,
    payload: dict[str, object],
    *,
    csrf_token: str,
    idempotency_key: str,
) -> HttpResult:
    return npi_request(
        opener,
        base_url,
        f"/api/npi/v1/projects/{project_id}:{action}",
        method="POST",
        payload=payload,
        csrf_token=csrf_token,
        idempotency_key=idempotency_key,
    )


def configure_team(
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
                "globalId": OWNER_MEMBER_ID,
                "userId": OWNER_USER,
                "effectiveFrom": "2026-07-01",
            },
            {
                "globalId": REVIEWER_MEMBER_ID,
                "userId": REVIEWER_USER,
                "effectiveFrom": "2026-07-01",
            },
        ],
        "roleAssignments": [
            {
                "globalId": OWNER_ROLE_ID,
                "memberId": OWNER_MEMBER_ID,
                "roleKey": ROLE_KEY,
                "effectiveFrom": "2026-07-01",
            }
        ],
        "substitutions": [],
        "raciAssignments": [
            {
                "globalId": PROJECT_RACI_ID,
                "contextType": "project",
                "contextId": project_id,
                "responsibilityKey": "gate_evidence",
                "roleAssignmentId": OWNER_ROLE_ID,
                "raci": "responsible",
            }
        ],
    }
    result = post_work_command(
        administrator,
        base_url,
        project_id,
        "configure-team",
        payload,
        csrf_token=csrf_token,
        idempotency_key=TEAM_KEY,
    )
    require(
        result.status == 200
        and result.headers.get("Idempotency-Replayed") == "false"
        and result.body.get("projectVersion") == 2,
        f"Project Team configuration returned HTTP {result.status}",
    )


def plan_payload(
    work_policy_ref: dict[str, object],
    *,
    expected_version: int,
    item_id: str,
    code: str,
    title: str,
    owner_role_id: str | None,
) -> dict[str, object]:
    item: dict[str, object] = {
        "globalId": item_id,
        "code": code,
        "title": title,
        "plannedStart": "2026-07-01",
        "plannedFinish": "2026-07-31",
        "milestone": False,
        "statusKey": WBS_STATE_KEY,
        "progressPercent": 25,
        "critical": True,
    }
    if owner_role_id is not None:
        item["ownerRoleAssignmentId"] = owner_role_id
    return {
        "expectedProjectVersion": expected_version,
        "workPolicyRef": work_policy_ref,
        "items": [item],
        "dependencies": [],
    }


def apply_plan(
    administrator,
    base_url: str,
    project_id: str,
    work_policy_ref: dict[str, object],
    csrf_token: str,
    *,
    expected_version: int,
    item_id: str,
    code: str,
    title: str,
    owner_role_id: str | None,
    idempotency_key: str,
) -> None:
    result = post_work_command(
        administrator,
        base_url,
        project_id,
        "apply-work-plan",
        plan_payload(
            work_policy_ref,
            expected_version=expected_version,
            item_id=item_id,
            code=code,
            title=title,
            owner_role_id=owner_role_id,
        ),
        csrf_token=csrf_token,
        idempotency_key=idempotency_key,
    )
    require(
        result.status == 200
        and result.headers.get("Idempotency-Replayed") == "false"
        and result.body.get("projectVersion") == expected_version + 1,
        f"Project work plan returned HTTP {result.status}",
    )


def freeze_payload() -> dict[str, object]:
    return {
        "expectedGateVersion": 1,
        "gateDueDate": "2026-08-31",
        "requirements": [
            {
                "key": REQUIREMENT_WBS,
                "ownerMemberId": OWNER_MEMBER_ID,
                "reviewerMemberIds": [REVIEWER_MEMBER_ID],
                "dueDate": "2026-08-15",
            },
            {
                "key": REQUIREMENT_FILE,
                "ownerMemberId": REVIEWER_MEMBER_ID,
                "reviewerMemberIds": [OWNER_MEMBER_ID],
                "dueDate": "2026-08-20",
            },
        ],
    }


def freeze_requirements(
    opener,
    base_url: str,
    project_id: str,
    gate_id: str,
    payload: dict[str, object],
    *,
    csrf_token: str,
    idempotency_key: str,
) -> HttpResult:
    return npi_request(
        opener,
        base_url,
        (
            f"/api/npi/v1/projects/{project_id}/gates/"
            f"{gate_id}:freeze-requirements"
        ),
        method="POST",
        payload=payload,
        csrf_token=csrf_token,
        idempotency_key=idempotency_key,
    )


def attach_evidence(
    opener,
    base_url: str,
    project_id: str,
    gate_id: str,
    requirement_key: str,
    payload: dict[str, object],
    *,
    csrf_token: str,
    idempotency_key: str,
) -> HttpResult:
    return npi_request(
        opener,
        base_url,
        (
            f"/api/npi/v1/projects/{project_id}/gates/{gate_id}/"
            f"requirements/{requirement_key}/evidence"
        ),
        method="POST",
        payload=payload,
        csrf_token=csrf_token,
        idempotency_key=idempotency_key,
    )


def get_workspace(
    opener,
    base_url: str,
    project_id: str,
    gate_id: str,
) -> HttpResult:
    return npi_request(
        opener,
        base_url,
        f"/api/npi/v1/projects/{project_id}/gates/{gate_id}/evidence",
    )


def wbs_snapshot(document: dict[str, object]) -> dict[str, object]:
    return {
        "actualEnd": document.get("actual_end") or None,
        "actualStart": document.get("actual_start") or None,
        "criticalTask": bool(document.get("critical_task")),
        "globalId": str(document["global_id"]),
        "milestone": bool(document.get("milestone")),
        "optimisticVersion": int(document["optimistic_version"]),
        "ownerRoleAssignmentGlobalId": (
            str(document["owner_role_assignment_global_id"])
            if document.get("owner_role_assignment_global_id")
            else None
        ),
        "parentGlobalId": (
            str(document["parent_global_id"])
            if document.get("parent_global_id")
            else None
        ),
        "planRevision": int(document["plan_revision"]),
        "plannedEnd": str(document["planned_end"]),
        "plannedStart": str(document["planned_start"]),
        "progressPercent": int(document["progress_percent"]),
        "projectGlobalId": str(document["project_global_id"]),
        "statusKey": str(document["status_key"]),
        "statusLabelSource": str(document["status_label_source"]),
        "tenantId": str(document["tenant_id"]),
        "title": str(document["title"]),
        "wbsCode": str(document["wbs_code"]),
        "workPolicyGlobalId": str(document["work_policy_global_id"]),
        "workPolicySnapshotHash": str(document["work_policy_snapshot_hash"]),
        "workPolicyVersion": int(document["work_policy_version"]),
    }


def exact_wbs(
    administrator,
    base_url: str,
    item_id: str,
) -> tuple[int, str]:
    result = get_resource(administrator, base_url, "NPI WBS Item", item_id)
    require(result.status == 200, f"WBS item returned HTTP {result.status}")
    data = result.body.get("data", {})
    require(
        data.get("global_id") == item_id
        and data.get("tenant_id") == TENANT_ID,
        "WBS item identity drifted",
    )
    snapshot = wbs_snapshot(data)
    return int(data["optimistic_version"]), canonical_hash(snapshot)


def validate_gate_workspace(
    result: HttpResult,
    *,
    expected_status: int = 200,
    project_id: str,
    gate_id: str,
    gate_template_hash: str,
    expected_gate_version: int,
    expected_evidence_count: int,
    expected_missing_required: int,
    expected_file_scan_state: str | None,
    administrator: bool,
) -> dict[str, object]:
    require(
        result.status == expected_status,
        (
            f"Gate workspace returned HTTP {result.status}; "
            f"expected {expected_status}"
        ),
    )
    body = result.body
    require(
        set(body)
        == {"project", "gate", "requirements", "summary", "permissions"},
        "Gate workspace top-level contract drifted",
    )
    gate = body["gate"]
    require(
        gate["globalId"] == gate_id
        and gate["version"] == expected_gate_version
        and gate["templateRef"]
        == {
            "globalId": GATE_TEMPLATE_ID,
            "version": GATE_TEMPLATE_VERSION,
            "snapshotHash": gate_template_hash,
        }
        and re.fullmatch(r"[a-f0-9]{64}", gate["requirementSnapshotHash"])
        is not None,
        "Gate exact template or requirement snapshot drifted",
    )
    require(
        body["project"]["globalId"] == project_id
        and body["summary"]
        == {
            "requiredCount": 2,
            "missingRequiredCount": expected_missing_required,
            "unsafeScanCount": (
                1 if expected_file_scan_state is not None else 0
            ),
            "evidenceCount": expected_evidence_count,
        },
        "Gate workspace Project or summary drifted",
    )
    requirements = {
        row["key"]: row for row in body["requirements"]
    }
    require(
        set(requirements) == {REQUIREMENT_WBS, REQUIREMENT_FILE}
        and requirements[REQUIREMENT_WBS]["owner"]["memberId"]
        == OWNER_MEMBER_ID
        and requirements[REQUIREMENT_FILE]["owner"]["memberId"]
        == REVIEWER_MEMBER_ID,
        "Frozen requirement assignments drifted",
    )
    file_requirement = requirements[REQUIREMENT_FILE]
    if expected_file_scan_state is None:
        require(
            file_requirement["evidenceState"] == "missing"
            and file_requirement["evidence"] == [],
            "Absent File evidence was not represented explicitly",
        )
    else:
        require(
            file_requirement["evidenceState"]
            == f"scan_{expected_file_scan_state}"
            and len(file_requirement["evidence"]) == 1
            and file_requirement["evidence"][0]["revision"] == 1
            and file_requirement["evidence"][0]["file"]["scanState"]
            == expected_file_scan_state,
            "Live File scan state drifted",
        )
    require(
        body["permissions"]
        == {
            "canView": True,
            "canAttachEvidence": administrator,
            "canAdminister": administrator,
        },
        "Gate workspace permission projection drifted",
    )
    serialized = json.dumps(body, sort_keys=True)
    require(
        "/private/files/" not in serialized
        and "fileUrl" not in serialized
        and '"url"' not in serialized.casefold(),
        "Gate workspace exposed a raw private file URL",
    )
    return body


def verify_fresh_fixture_namespace(
    administrator,
    base_url: str,
) -> dict[str, object]:
    """Prove every caller-owned identity is absent before the first write."""
    absent: dict[str, object] = {}
    for user_id in (OWNER_USER, REVIEWER_USER, UNRELATED_USER):
        result = request(administrator, base_url, user_resource_path(user_id))
        require(
            result.status == 404,
            f"Fresh P4-03 namespace already contains user state: {user_id}",
        )
    absent["users"] = 3

    for doctype, name in (
        ("NPI Gate Template", GATE_TEMPLATE_ID),
        ("NPI Gate Template Version", GATE_TEMPLATE_VERSION_KEY),
        ("NPI Project Template", PROJECT_TEMPLATE_ID),
        ("NPI Project Template Version", PROJECT_TEMPLATE_VERSION_KEY),
        ("NPI Project Template", DISABLED_BINDING_TEMPLATE_ID),
        ("NPI Project Template Version", DISABLED_BINDING_VERSION_KEY),
        ("NPI Project Work Policy Version", WORK_POLICY_VERSION_KEY),
        ("NPI File Revision", FILE_REVISION_ID),
        ("NPI File Revision", CROSS_FILE_REVISION_ID),
        ("NPI File Revision", WRONG_TENANT_FILE_REVISION_ID),
    ):
        require(
            get_resource(administrator, base_url, doctype, name).status == 404,
            f"Fresh P4-03 namespace already contains {doctype}: {name}",
        )
    absent["namedRecords"] = 10

    for business_code in (BUSINESS_CODE, CROSS_BUSINESS_CODE):
        require(
            list_resources(
                administrator,
                base_url,
                "NPI Engineering Project",
                filters=[["business_code", "=", business_code]],
                fields=["global_id"],
            )
            == [],
            f"Fresh P4-03 namespace already contains Project: {business_code}",
        )
    absent["projects"] = 2

    for raw_key in (
        PROJECT_CREATE_KEY,
        CROSS_PROJECT_CREATE_KEY,
        TEAM_KEY,
        MAIN_PLAN_KEY,
        CROSS_PLAN_KEY,
        FREEZE_KEY,
        WBS_ATTACH_KEY,
        FILE_ATTACH_KEY,
        FREEZE_AGAIN_KEY,
        STALE_ATTACH_KEY,
        CROSS_WBS_ATTACH_KEY,
        CROSS_FILE_ATTACH_KEY,
        OWNER_ATTACH_KEY,
    ):
        doctype = (
            "NPI Project Idempotency"
            if raw_key in {PROJECT_CREATE_KEY, CROSS_PROJECT_CREATE_KEY}
            else "NPI Project Work Idempotency"
        )
        rows = list_resources(
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
        require(rows == [], f"Fresh P4-03 namespace contains idempotency: {raw_key}")
    absent["idempotency"] = 13
    return absent


def verify_disabled_template_rule(
    administrator,
    base_url: str,
    csrf_token: str,
    gate_template_hash: str,
) -> None:
    disabled = update_resource(
        administrator,
        base_url,
        "NPI Gate Template",
        GATE_TEMPLATE_ID,
        {"enabled": 0},
        csrf_token,
    )
    require(
        disabled.status == 200
        and disabled.body.get("data", {}).get("enabled") == 0,
        "Gate Template root could not be disabled",
    )
    root = create_resource(
        administrator,
        base_url,
        "NPI Project Template",
        {
            "global_id": DISABLED_BINDING_TEMPLATE_ID,
            "template_code": DISABLED_BINDING_TEMPLATE_CODE,
            "title": f"Synthetic {FIXTURE_NAMESPACE} disabled binding",
            "enabled": 1,
        },
        csrf_token,
    )
    require(
        root.status in {200, 201},
        f"Disabled-binding guard root returned HTTP {root.status}",
    )
    rejected = create_resource(
        administrator,
        base_url,
        "NPI Project Template Version",
        project_template_version_payload(
            DISABLED_BINDING_TEMPLATE_ID,
            gate_template_hash,
            title_suffix=" disabled binding",
        ),
        csrf_token,
    )
    require(
        rejected.status in {403, 409, 417, 422},
        (
            "A disabled Gate Template was unexpectedly available for "
            f"new binding: HTTP {rejected.status}"
        ),
    )
    require(
        get_resource(
            administrator,
            base_url,
            "NPI Project Template Version",
            DISABLED_BINDING_VERSION_KEY,
        ).status
        == 404,
        "Rejected disabled Gate Template binding left partial history",
    )
    removed = delete_resource(
        administrator,
        base_url,
        "NPI Project Template",
        DISABLED_BINDING_TEMPLATE_ID,
        csrf_token,
    )
    require(
        removed.status in {200, 202}
        and get_resource(
            administrator,
            base_url,
            "NPI Project Template",
            DISABLED_BINDING_TEMPLATE_ID,
        ).status
        == 404,
        "Bounded disabled-binding guard root cleanup failed",
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


def _insert_file_revision(
    *,
    project_id: str,
    revision_id: str,
    document_id: str,
    file_name: str,
    content: bytes,
) -> dict[str, object]:
    import frappe
    from frappe.utils.file_manager import save_file

    from npi_core.controlled_evidence_validation import FILE_REVISION_COMMAND_FLAG

    require(
        not frappe.db.exists("NPI File Revision", revision_id),
        f"Fresh File Revision fixture already exists: {revision_id}",
    )
    file_document = save_file(
        file_name,
        content,
        "",
        "",
        is_private=1,
    )
    previous = getattr(frappe.flags, FILE_REVISION_COMMAND_FLAG, None)
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
                "sha256": "0" * 64,
                "scan_state": "pending",
            }
        ).insert()
    finally:
        if previous is None:
            delattr(frappe.flags, FILE_REVISION_COMMAND_FLAG)
        else:
            setattr(frappe.flags, FILE_REVISION_COMMAND_FLAG, previous)
    return {
        "fileId": str(revision.frappe_file_id),
        "sha256": str(revision.sha256),
    }


def seed_private_file_revisions(
    main_project_id: str,
    cross_project_id: str,
    fixture_run_id: str,
) -> dict[str, object]:
    """Create only private File projections needed by the runtime verifier."""
    import frappe

    _validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "File fixture namespace does not match the verifier process",
    )
    UUID(main_project_id)
    UUID(cross_project_id)
    content = (
        f"Synthetic P4-03 controlled evidence {FIXTURE_NAMESPACE}\n"
    ).encode("utf-8")
    main = _insert_file_revision(
        project_id=main_project_id,
        revision_id=FILE_REVISION_ID,
        document_id=DOCUMENT_ID,
        file_name=f"{FIXTURE_PREFIX}-controlled.txt",
        content=content,
    )
    cross = _insert_file_revision(
        project_id=cross_project_id,
        revision_id=CROSS_FILE_REVISION_ID,
        document_id=CROSS_DOCUMENT_ID,
        file_name=f"{FIXTURE_PREFIX}-cross-controlled.txt",
        content=content,
    )
    require(
        main["sha256"] == cross["sha256"],
        "Same-content File Revision fixture hashes differ",
    )
    frappe.db.commit()

    from npi_core.controlled_evidence_validation import FILE_REVISION_COMMAND_FLAG

    previous = getattr(frappe.flags, FILE_REVISION_COMMAND_FLAG, None)
    setattr(frappe.flags, FILE_REVISION_COMMAND_FLAG, True)
    wrong_tenant_rejected = False
    try:
        try:
            frappe.get_doc(
                {
                    "doctype": "NPI File Revision",
                    "global_id": WRONG_TENANT_FILE_REVISION_ID,
                    "tenant_id": "other-runtime-tenant",
                    "project_global_id": main_project_id,
                    "document_global_id": fixture_id("wrong-tenant-document"),
                    "revision": 1,
                    "frappe_file_id": main["fileId"],
                    "file": "/private/files/placeholder",
                    "sha256": "0" * 64,
                    "scan_state": "pending",
                }
            ).insert()
        except frappe.ValidationError:
            wrong_tenant_rejected = True
            frappe.db.rollback()
    finally:
        if previous is None:
            delattr(frappe.flags, FILE_REVISION_COMMAND_FLAG)
        else:
            setattr(frappe.flags, FILE_REVISION_COMMAND_FLAG, previous)
    require(
        wrong_tenant_rejected
        and not frappe.db.exists(
            "NPI File Revision",
            WRONG_TENANT_FILE_REVISION_ID,
        ),
        "Wrong-tenant File Revision was not rejected without partial state",
    )
    return {
        "crossFileId": cross["fileId"],
        "mainFileId": main["fileId"],
        "sameContentHash": main["sha256"],
        "wrongTenantRejected": True,
    }


def observe_private_file_scan(
    fixture_run_id: str,
    scan_state: str,
) -> dict[str, object]:
    """Apply one scanner-owned observation through the controlled flag."""
    import frappe
    from frappe.utils import now_datetime

    from npi_core.controlled_evidence_validation import FILE_SCAN_RESULT_FLAG

    _validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID and scan_state in {"clean", "infected", "failed"},
        "Scanner fixture input is invalid",
    )
    revision = frappe.get_doc("NPI File Revision", FILE_REVISION_ID)
    before_hash = str(revision.sha256)
    previous = getattr(frappe.flags, FILE_SCAN_RESULT_FLAG, None)
    setattr(frappe.flags, FILE_SCAN_RESULT_FLAG, True)
    try:
        revision.scan_state = scan_state
        revision.scan_observed_at = now_datetime()
        revision.save()
    finally:
        if previous is None:
            delattr(frappe.flags, FILE_SCAN_RESULT_FLAG)
        else:
            setattr(frappe.flags, FILE_SCAN_RESULT_FLAG, previous)
    frappe.db.commit()
    require(
        str(revision.sha256) == before_hash,
        "Scanner observation changed immutable File content identity",
    )
    return {
        "fileRevisionId": FILE_REVISION_ID,
        "optimisticVersion": int(revision.optimistic_version),
        "scanState": str(revision.scan_state),
        "sha256": before_hash,
    }


def run_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
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
            str(ROOT / "scripts" / "verify_gate_evidence_runtime.py"),
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
            f"Controlled Bench fixture {method} failed: "
            f"{completed.stderr[-2000:]}"
        ),
    )


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    """Execute one allowlisted fixture inside the fixed disposable Frappe Site."""
    fixtures = {
        "observe_private_file_scan": observe_private_file_scan,
        "seed_private_file_revisions": seed_private_file_revisions,
    }
    require(method in fixtures, "Controlled Bench fixture method is unavailable")
    require(
        BENCH_PATH.is_dir()
        and not BENCH_PATH.is_symlink()
        and BENCH_PATH.resolve() == BENCH_PATH,
        "Controlled Bench fixture requires the fixed physical repository Bench",
    )
    import frappe

    frappe.init(
        site=SITE_NAME,
        sites_path=str(BENCH_PATH / "sites"),
    )
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


def assert_failed_command_absent(
    administrator,
    base_url: str,
    raw_key: str,
) -> None:
    rows = list_resources(
        administrator,
        base_url,
        "NPI Project Work Idempotency",
        filters=[
            [
                "actor_key_hash",
                "=",
                actor_key_hash("Administrator", raw_key),
            ]
        ],
        fields=["name"],
    )
    require(rows == [], f"Rejected Gate command retained idempotency: {raw_key}")


def verify_append_only_guards(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    gate_id: str,
    evidence_ids: list[str],
) -> int:
    targets = [
        ("NPI Gate Shell", gate_id, {"title": "MUST NOT CHANGE"}),
        (
            "NPI Gate Template Version",
            GATE_TEMPLATE_VERSION_KEY,
            {"title": "MUST NOT CHANGE"},
        ),
        (
            "NPI File Revision",
            FILE_REVISION_ID,
            {"file_name": "MUST-NOT-CHANGE.txt"},
        ),
        *[
            (
                "NPI Gate Evidence Reference",
                evidence_id,
                {"source_hash": "0" * 64},
            )
            for evidence_id in evidence_ids
        ],
    ]
    denied = 0
    for doctype, name, payload in targets:
        update = update_resource(
            administrator,
            base_url,
            doctype,
            name,
            payload,
            csrf_token,
        )
        require(
            update.status in {403, 417},
            f"{doctype} controlled update returned HTTP {update.status}",
        )
        denied += 1
        deletion = delete_resource(
            administrator,
            base_url,
            doctype,
            name,
            csrf_token,
        )
        require(
            deletion.status in {403, 417},
            f"{doctype} controlled delete returned HTTP {deletion.status}",
        )
        require(
            get_resource(administrator, base_url, doctype, name).status == 200,
            f"{doctype} controlled record was physically removed",
        )
        denied += 1
    return denied


def validate_file_revision(
    administrator,
    base_url: str,
    revision_id: str,
    project_id: str,
) -> dict[str, object]:
    first = get_resource(
        administrator,
        base_url,
        "NPI File Revision",
        revision_id,
    )
    second = get_resource(
        administrator,
        base_url,
        "NPI File Revision",
        revision_id,
    )
    require(
        first.status == 200 and second.status == 200,
        f"File Revision returned HTTP {first.status}/{second.status}",
    )
    data = first.body.get("data", {})
    require(
        first.body == second.body
        and data.get("global_id") == revision_id
        and data.get("tenant_id") == TENANT_ID
        and data.get("project_global_id") == project_id
        and data.get("revision") == 1
        and data.get("optimistic_version") == 1
        and data.get("scan_state") == "pending"
        and data.get("is_private") == 1
        and isinstance(data.get("frappe_file_id"), str)
        and str(data.get("file", "")).startswith("/private/files/")
        and re.fullmatch(r"[a-f0-9]{64}", str(data.get("sha256"))) is not None,
        "File Revision controlled identity drifted",
    )
    return data


def verify_persistence(
    administrator,
    base_url: str,
    *,
    project_id: str,
    gate_id: str,
    evidence_ids: list[str],
) -> None:
    gate = get_resource(
        administrator,
        base_url,
        "NPI Gate Shell",
        gate_id,
    )
    data = gate.body.get("data", {})
    require(
        gate.status == 200
        and data.get("project_global_id") == project_id
        and data.get("gate_template_global_id") == GATE_TEMPLATE_ID
        and data.get("gate_template_version") == GATE_TEMPLATE_VERSION
        and data.get("requirements_frozen") == 1
        and data.get("optimistic_version") == 4
        and re.fullmatch(
            r"[a-f0-9]{64}",
            str(data.get("requirement_snapshot_hash")),
        )
        is not None,
        "Persisted Gate frozen identity drifted",
    )
    rows = list_resources(
        administrator,
        base_url,
        "NPI Gate Evidence Reference",
        filters=[
            ["project_global_id", "=", project_id],
            ["gate_global_id", "=", gate_id],
        ],
        fields=[
            "global_id",
            "requirement_key",
            "evidence_kind",
            "source_global_id",
            "source_version",
            "source_hash",
            "source_snapshot",
            "tenant_id",
        ],
    )
    require(
        len(rows) == 2
        and {str(row["global_id"]) for row in rows} == set(evidence_ids)
        and all(
            row["tenant_id"] == TENANT_ID
            and row["source_version"] == 1
            and re.fullmatch(r"[a-f0-9]{64}", str(row["source_hash"]))
            is not None
            for row in rows
        ),
        "Persisted exact Gate evidence references drifted",
    )
    file_rows = [
        row for row in rows if row["evidence_kind"] == "file_revision"
    ]
    require(len(file_rows) == 1, "Persisted File evidence is not unique")
    file_snapshot = json_value(file_rows[0]["source_snapshot"])
    require(
        isinstance(file_snapshot, dict)
        and file_snapshot.get("fileId")
        and file_snapshot.get("globalId") == FILE_REVISION_ID
        and file_snapshot.get("revision") == 1
        and file_snapshot.get("sha256") == file_rows[0]["source_hash"]
        and "/private/files/" not in json.dumps(file_snapshot, sort_keys=True),
        "Persisted File evidence snapshot is not exact and URL-free",
    )
    for evidence_id, operation in (
        (gate_id, "gate.requirements.freeze"),
        (evidence_ids[0], "gate.evidence.attach"),
        (evidence_ids[1], "gate.evidence.attach"),
    ):
        audits = list_resources(
            administrator,
            base_url,
            "NPI Audit Event",
            filters=[
                ["global_id", "=", evidence_id],
                ["operation", "=", operation],
            ],
            fields=[
                "actor",
                "global_id",
                "input_summary",
                "object_version",
                "operation",
                "result",
                "trace_id",
            ],
        )
        require(
            len(audits) == 1
            and audits[0]["actor"] == "Administrator"
            and audits[0]["result"] in {"created", "updated"}
            and "/private/files/"
            not in json.dumps(json_value(audits[0]["input_summary"])),
            f"Gate audit evidence drifted for {evidence_id}",
        )


def cleanup_runtime_users(
    administrator,
    base_url: str,
    csrf_token: str,
    created_users: list[str],
    *,
    retain_controlled_history: bool,
) -> None:
    retained_users = {OWNER_USER, REVIEWER_USER}
    for user_id in reversed(created_users):
        existing = request(administrator, base_url, user_resource_path(user_id))
        if existing.status == 404:
            continue
        require(
            existing.status == 200,
            f"Runtime fixture user cleanup lookup failed: {user_id}",
        )
        if retain_controlled_history and user_id in retained_users:
            disabled = update_resource(
                administrator,
                base_url,
                "User",
                user_id,
                {"enabled": 0},
                csrf_token,
            )
            require(
                disabled.status == 200,
                f"Referenced runtime fixture user could not be disabled: {user_id}",
            )
        else:
            delete_disposable_user(
                administrator,
                base_url,
                user_id,
                csrf_token,
            )

    for user_id in (OWNER_USER, REVIEWER_USER, UNRELATED_USER):
        retained = request(administrator, base_url, user_resource_path(user_id))
        if retain_controlled_history and user_id in retained_users:
            require(
                retained.status == 200
                and retained.body.get("data", {}).get("enabled") == 0,
                f"Referenced runtime fixture user remains active: {user_id}",
            )
        else:
            require(
                retained.status == 404,
                f"Unreferenced runtime fixture user cleanup failed: {user_id}",
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the real P4-03 Gate evidence runtime.",
    )
    parser.add_argument("--base-url")
    parser.add_argument(
        "--bench-fixture",
        choices=("observe_private_file_scan", "seed_private_file_revisions"),
    )
    parser.add_argument("--fixture-kwargs")
    arguments = parser.parse_args()
    if arguments.bench_fixture is not None:
        require(
            arguments.base_url is None
            and isinstance(arguments.fixture_kwargs, str),
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
        "The P4-03 runtime base URL is required",
    )

    require(
        CALLER_SUPPLIED_FIXTURE_RUN_ID is not None,
        f"{FIXTURE_RUN_ID_ENV} is required for a controlled runtime run",
    )
    administrator_user = "Administrator"
    administrator_password = secret_from_environment(
        "NPI_RUNTIME_ADMINISTRATOR_PASSWORD"
    )
    fixture_password = secret_from_environment(
        "NPI_RUNTIME_FIXTURE_PASSWORD"
    )
    for fixture_user in (OWNER_USER, REVIEWER_USER, UNRELATED_USER):
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
    created_users: list[str] = []
    controlled_history_retained = False
    try:
        for user_id, label in (
            (OWNER_USER, "Owner"),
            (REVIEWER_USER, "Reviewer"),
            (UNRELATED_USER, "Unrelated"),
        ):
            create_internal_user(
                administrator,
                arguments.base_url,
                user_id,
                fixture_password,
                administrator_csrf,
                label,
            )
            created_users.append(user_id)

        owner = login(arguments.base_url, OWNER_USER, fixture_password)
        reviewer = login(arguments.base_url, REVIEWER_USER, fixture_password)
        unrelated = login(arguments.base_url, UNRELATED_USER, fixture_password)
        owner_csrf = bootstrap_csrf(
            owner,
            arguments.base_url,
            OWNER_USER,
        )
        bootstrap_csrf(
            reviewer,
            arguments.base_url,
            REVIEWER_USER,
        )
        bootstrap_csrf(
            unrelated,
            arguments.base_url,
            UNRELATED_USER,
        )

        gate_template_hash = ensure_gate_template(
            administrator,
            arguments.base_url,
            administrator_csrf,
        )
        ensure_project_template(
            administrator,
            arguments.base_url,
            administrator_csrf,
            gate_template_hash,
        )
        project_id, gate_id = create_project(
            administrator,
            arguments.base_url,
            administrator_csrf,
            owner_user_id=OWNER_USER,
            business_code=BUSINESS_CODE,
            title=f"Synthetic {FIXTURE_NAMESPACE} Gate evidence Project",
            idempotency_key=PROJECT_CREATE_KEY,
        )
        controlled_history_retained = True
        cross_project_id, _cross_gate_id = create_project(
            administrator,
            arguments.base_url,
            administrator_csrf,
            owner_user_id=OWNER_USER,
            business_code=CROSS_BUSINESS_CODE,
            title=f"Synthetic {FIXTURE_NAMESPACE} cross-source Project",
            idempotency_key=CROSS_PROJECT_CREATE_KEY,
        )
        work_policy_ref = ensure_work_policy(
            administrator,
            arguments.base_url,
            administrator_csrf,
        )
        configure_team(
            administrator,
            arguments.base_url,
            project_id,
            work_policy_ref,
            administrator_csrf,
        )
        apply_plan(
            administrator,
            arguments.base_url,
            project_id,
            work_policy_ref,
            administrator_csrf,
            expected_version=2,
            item_id=MAIN_WBS_ID,
            code="1.10",
            title="Synthetic exact design work",
            owner_role_id=OWNER_ROLE_ID,
            idempotency_key=MAIN_PLAN_KEY,
        )
        apply_plan(
            administrator,
            arguments.base_url,
            cross_project_id,
            work_policy_ref,
            administrator_csrf,
            expected_version=1,
            item_id=CROSS_WBS_ID,
            code="9.10",
            title="Synthetic cross-Project work",
            owner_role_id=None,
            idempotency_key=CROSS_PLAN_KEY,
        )

        main_wbs_version, main_wbs_hash = exact_wbs(
            administrator,
            arguments.base_url,
            MAIN_WBS_ID,
        )
        cross_wbs_version, cross_wbs_hash = exact_wbs(
            administrator,
            arguments.base_url,
            CROSS_WBS_ID,
        )
        run_bench_fixture(
            "seed_private_file_revisions",
            {
                "main_project_id": project_id,
                "cross_project_id": cross_project_id,
                "fixture_run_id": FIXTURE_RUN_ID,
            },
        )
        main_file = validate_file_revision(
            administrator,
            arguments.base_url,
            FILE_REVISION_ID,
            project_id,
        )
        cross_file = validate_file_revision(
            administrator,
            arguments.base_url,
            CROSS_FILE_REVISION_ID,
            cross_project_id,
        )
        require(
            main_file["sha256"] == cross_file["sha256"],
            "Same-content cross-Project File Revision hashes differ",
        )
        require(
            get_resource(
                administrator,
                arguments.base_url,
                "NPI File Revision",
                WRONG_TENANT_FILE_REVISION_ID,
            ).status
            == 404,
            "Wrong-tenant File Revision left partial state",
        )

        verify_disabled_template_rule(
            administrator,
            arguments.base_url,
            administrator_csrf,
            gate_template_hash,
        )
        freeze = freeze_requirements(
            administrator,
            arguments.base_url,
            project_id,
            gate_id,
            freeze_payload(),
            csrf_token=administrator_csrf,
            idempotency_key=FREEZE_KEY,
        )
        require(
            freeze.status == 200
            and freeze.headers.get("Idempotency-Replayed") == "false",
            (
                "Historical exact Gate freeze failed after its Gate Template "
                f"root was disabled: HTTP {freeze.status}"
            ),
        )
        frozen_body = validate_gate_workspace(
            freeze,
            project_id=project_id,
            gate_id=gate_id,
            gate_template_hash=gate_template_hash,
            expected_gate_version=2,
            expected_evidence_count=0,
            expected_missing_required=2,
            expected_file_scan_state=None,
            administrator=True,
        )
        freeze_replay = freeze_requirements(
            administrator,
            arguments.base_url,
            project_id,
            gate_id,
            freeze_payload(),
            csrf_token=administrator_csrf,
            idempotency_key=FREEZE_KEY,
        )
        require(
            freeze_replay.status == 200
            and freeze_replay.headers.get("Idempotency-Replayed") == "true"
            and freeze_replay.body == frozen_body,
            "Gate freeze did not replay its complete sealed response",
        )
        freeze_again_payload = freeze_payload()
        freeze_again_payload["expectedGateVersion"] = 2
        freeze_again = freeze_requirements(
            administrator,
            arguments.base_url,
            project_id,
            gate_id,
            freeze_again_payload,
            csrf_token=administrator_csrf,
            idempotency_key=FREEZE_AGAIN_KEY,
        )
        validate_problem(
            freeze_again,
            409,
            "GATE_REQUIREMENTS_ALREADY_FROZEN",
        )
        assert_failed_command_absent(
            administrator,
            arguments.base_url,
            FREEZE_AGAIN_KEY,
        )

        wbs_payload = {
            "expectedGateVersion": 2,
            "evidenceKind": "wbs_item",
            "sourceGlobalId": MAIN_WBS_ID,
            "sourceVersion": main_wbs_version,
            "sourceHash": main_wbs_hash,
        }
        wbs_attach = attach_evidence(
            administrator,
            arguments.base_url,
            project_id,
            gate_id,
            REQUIREMENT_WBS,
            wbs_payload,
            csrf_token=administrator_csrf,
            idempotency_key=WBS_ATTACH_KEY,
        )
        require(
            wbs_attach.status == 201
            and wbs_attach.headers.get("Idempotency-Replayed") == "false",
            f"Exact WBS evidence attach returned HTTP {wbs_attach.status}",
        )
        validate_gate_workspace(
            wbs_attach,
            expected_status=201,
            project_id=project_id,
            gate_id=gate_id,
            gate_template_hash=gate_template_hash,
            expected_gate_version=3,
            expected_evidence_count=1,
            expected_missing_required=1,
            expected_file_scan_state=None,
            administrator=True,
        )

        cross_wbs = attach_evidence(
            administrator,
            arguments.base_url,
            project_id,
            gate_id,
            REQUIREMENT_WBS,
            {
                "expectedGateVersion": 3,
                "evidenceKind": "wbs_item",
                "sourceGlobalId": CROSS_WBS_ID,
                "sourceVersion": cross_wbs_version,
                "sourceHash": cross_wbs_hash,
            },
            csrf_token=administrator_csrf,
            idempotency_key=CROSS_WBS_ATTACH_KEY,
        )
        validate_problem(cross_wbs, 422, "EVIDENCE_SOURCE_UNAVAILABLE")
        assert_failed_command_absent(
            administrator,
            arguments.base_url,
            CROSS_WBS_ATTACH_KEY,
        )
        cross_file_attempt = attach_evidence(
            administrator,
            arguments.base_url,
            project_id,
            gate_id,
            REQUIREMENT_FILE,
            {
                "expectedGateVersion": 3,
                "evidenceKind": "file_revision",
                "sourceGlobalId": CROSS_FILE_REVISION_ID,
                "sourceVersion": 1,
                "sourceHash": str(cross_file["sha256"]),
            },
            csrf_token=administrator_csrf,
            idempotency_key=CROSS_FILE_ATTACH_KEY,
        )
        validate_problem(
            cross_file_attempt,
            422,
            "EVIDENCE_SOURCE_UNAVAILABLE",
        )
        assert_failed_command_absent(
            administrator,
            arguments.base_url,
            CROSS_FILE_ATTACH_KEY,
        )
        stale_file = attach_evidence(
            administrator,
            arguments.base_url,
            project_id,
            gate_id,
            REQUIREMENT_FILE,
            {
                "expectedGateVersion": 2,
                "evidenceKind": "file_revision",
                "sourceGlobalId": FILE_REVISION_ID,
                "sourceVersion": 1,
                "sourceHash": str(main_file["sha256"]),
            },
            csrf_token=administrator_csrf,
            idempotency_key=STALE_ATTACH_KEY,
        )
        validate_problem(stale_file, 409, "VERSION_CONFLICT")
        assert_failed_command_absent(
            administrator,
            arguments.base_url,
            STALE_ATTACH_KEY,
        )

        file_payload = {
            "expectedGateVersion": 3,
            "evidenceKind": "file_revision",
            "sourceGlobalId": FILE_REVISION_ID,
            "sourceVersion": 1,
            "sourceHash": str(main_file["sha256"]),
        }
        file_attach = attach_evidence(
            administrator,
            arguments.base_url,
            project_id,
            gate_id,
            REQUIREMENT_FILE,
            file_payload,
            csrf_token=administrator_csrf,
            idempotency_key=FILE_ATTACH_KEY,
        )
        require(
            file_attach.status == 201
            and file_attach.headers.get("Idempotency-Replayed") == "false",
            f"Exact File evidence attach returned HTTP {file_attach.status}",
        )
        pending_body = validate_gate_workspace(
            file_attach,
            expected_status=201,
            project_id=project_id,
            gate_id=gate_id,
            gate_template_hash=gate_template_hash,
            expected_gate_version=4,
            expected_evidence_count=2,
            expected_missing_required=0,
            expected_file_scan_state="pending",
            administrator=True,
        )
        file_replay = attach_evidence(
            administrator,
            arguments.base_url,
            project_id,
            gate_id,
            REQUIREMENT_FILE,
            file_payload,
            csrf_token=administrator_csrf,
            idempotency_key=FILE_ATTACH_KEY,
        )
        require(
            file_replay.status == 201
            and file_replay.headers.get("Idempotency-Replayed") == "true"
            and file_replay.body == pending_body,
            "File evidence command did not replay its sealed response",
        )
        conflict_payload = dict(file_payload)
        conflict_payload["sourceHash"] = "0" * 64
        file_conflict = attach_evidence(
            administrator,
            arguments.base_url,
            project_id,
            gate_id,
            REQUIREMENT_FILE,
            conflict_payload,
            csrf_token=administrator_csrf,
            idempotency_key=FILE_ATTACH_KEY,
        )
        validate_problem(file_conflict, 409, "IDEMPOTENCY_KEY_CONFLICT")

        wbs_replay = attach_evidence(
            administrator,
            arguments.base_url,
            project_id,
            gate_id,
            REQUIREMENT_WBS,
            wbs_payload,
            csrf_token=administrator_csrf,
            idempotency_key=WBS_ATTACH_KEY,
        )
        require(
            wbs_replay.status == 201
            and wbs_replay.headers.get("Idempotency-Replayed") == "true"
            and wbs_replay.body == wbs_attach.body,
            "WBS evidence command did not replay its sealed response",
        )

        run_bench_fixture(
            "observe_private_file_scan",
            {
                "fixture_run_id": FIXTURE_RUN_ID,
                "scan_state": "infected",
            },
        )
        infected = get_workspace(
            administrator,
            arguments.base_url,
            project_id,
            gate_id,
        )
        validate_gate_workspace(
            infected,
            project_id=project_id,
            gate_id=gate_id,
            gate_template_hash=gate_template_hash,
            expected_gate_version=4,
            expected_evidence_count=2,
            expected_missing_required=0,
            expected_file_scan_state="infected",
            administrator=True,
        )
        refreshed_file = get_resource(
            administrator,
            arguments.base_url,
            "NPI File Revision",
            FILE_REVISION_ID,
        ).body.get("data", {})
        require(
            refreshed_file.get("scan_state") == "infected"
            and refreshed_file.get("sha256") == main_file["sha256"]
            and refreshed_file.get("optimistic_version") == 2,
            "Real scanner observation or immutable content identity drifted",
        )

        owner_view = get_workspace(
            owner,
            arguments.base_url,
            project_id,
            gate_id,
        )
        validate_gate_workspace(
            owner_view,
            project_id=project_id,
            gate_id=gate_id,
            gate_template_hash=gate_template_hash,
            expected_gate_version=4,
            expected_evidence_count=2,
            expected_missing_required=0,
            expected_file_scan_state="infected",
            administrator=False,
        )
        owner_command = attach_evidence(
            owner,
            arguments.base_url,
            project_id,
            gate_id,
            REQUIREMENT_FILE,
            {
                **file_payload,
                "expectedGateVersion": 4,
            },
            csrf_token=owner_csrf,
            idempotency_key=OWNER_ATTACH_KEY,
        )
        validate_problem(owner_command, 403, "PERMISSION_DENIED")

        reviewer_view = get_workspace(
            reviewer,
            arguments.base_url,
            project_id,
            gate_id,
        )
        unrelated_view = get_workspace(
            unrelated,
            arguments.base_url,
            project_id,
            gate_id,
        )
        absent_view = get_workspace(
            unrelated,
            arguments.base_url,
            str(uuid4()),
            str(uuid4()),
        )
        for denied in (reviewer_view, unrelated_view, absent_view):
            validate_problem(denied, 404, "GATE_UNAVAILABLE")
        for field in ("type", "title", "status", "code", "retryable"):
            require(
                unrelated_view.body.get(field) == absent_view.body.get(field),
                "IDOR-safe unavailable Gate problems differ",
            )
        guest_view = get_workspace(
            urllib.request.build_opener(),
            arguments.base_url,
            project_id,
            gate_id,
        )
        validate_problem(guest_view, 401, "AUTHENTICATION_REQUIRED")

        evidence_rows = list_resources(
            administrator,
            arguments.base_url,
            "NPI Gate Evidence Reference",
            filters=[
                ["project_global_id", "=", project_id],
                ["gate_global_id", "=", gate_id],
            ],
            fields=[
                "global_id",
                "evidence_kind",
                "source_global_id",
            ],
        )
        evidence_ids_by_kind = {
            str(row["evidence_kind"]): str(row["global_id"])
            for row in evidence_rows
        }
        require(
            set(evidence_ids_by_kind) == {"wbs_item", "file_revision"},
            "Gate evidence persistence kinds drifted",
        )
        evidence_ids = [
            evidence_ids_by_kind["wbs_item"],
            evidence_ids_by_kind["file_revision"],
        ]
        verify_persistence(
            administrator,
            arguments.base_url,
            project_id=project_id,
            gate_id=gate_id,
            evidence_ids=evidence_ids,
        )
        append_only_denials = verify_append_only_guards(
            administrator,
            arguments.base_url,
            administrator_csrf,
            gate_id=gate_id,
            evidence_ids=evidence_ids,
        )

        print(
            json.dumps(
                {
                    "appendOnlyDenials": append_only_denials,
                    "boundedCleanup": {
                        "disabledBindingRootAbsent": True,
                        "rejectedCommandRecordsAbsent": 4,
                        "wrongTenantRevisionAbsent": True,
                    },
                    "exactEvidence": {
                        "fileRevision": 1,
                        "gateVersion": 4,
                        "wbsVersion": main_wbs_version,
                    },
                    "fixtureAbsenceBeforeWrite": fixture_absence,
                    "fixtureRevision": FIXTURE_REVISION,
                    "fixtureRunId": FIXTURE_RUN_ID,
                    "historicalFreezeAfterTemplateDisable": True,
                    "idor": 404,
                    "projectId": project_id,
                    "rawPrivateUrlExposed": False,
                    "realScanState": "infected",
                    "retainedControlledHistory": True,
                    "retainedFixtureUsersDisabled": True,
                    "sameContentCrossProjectDenied": True,
                    "tenantMismatchDenied": True,
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
            for business_code in (BUSINESS_CODE, CROSS_BUSINESS_CODE)
        )
        cleanup_runtime_users(
            cleanup,
            arguments.base_url,
            cleanup_csrf,
            created_users,
            retain_controlled_history=(
                controlled_history_retained or retained_projects
            ),
        )

    print("local Frappe Gate evidence runtime verification passed")


if __name__ == "__main__":
    main()
