from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime
from threading import Barrier
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from verify_frappe_runtime import (
    HttpResult,
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
    TEMPLATE_GLOBAL_ID,
    TEMPLATE_VERSION_KEY,
    actor_key_hash,
    bootstrap_csrf,
    create_resource,
    delete_resource,
    ensure_synthetic_template,
    get_resource,
    list_resources,
    post_project,
    project_payload,
    update_resource,
)


FIXTURE_REVISION = 2
FIXTURE_RUN_ID_ENV = "NPI_PROJECT_WORK_RUNTIME_RUN_ID"


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
FIXTURE_RUN_ID = validated_fixture_run_id(
    CALLER_SUPPLIED_FIXTURE_RUN_ID
)
FIXTURE_NAMESPACE = f"r{FIXTURE_REVISION}-{FIXTURE_RUN_ID}"
FIXTURE_PREFIX = f"p4-02-runtime-{FIXTURE_NAMESPACE}"
OWNER_USER = f"npi-work-{FIXTURE_NAMESPACE}-owner@example.invalid"
MEMBER_USER = f"npi-work-{FIXTURE_NAMESPACE}-member@example.invalid"
POLICY_GLOBAL_ID = str(
    uuid5(
        NAMESPACE_URL,
        (
            "https://npi-one.example.invalid/runtime/p4-02/"
            f"{FIXTURE_NAMESPACE}/policy"
        ),
    )
)
GUARD_POLICY_GLOBAL_ID = str(
    uuid5(
        NAMESPACE_URL,
        (
            "https://npi-one.example.invalid/runtime/p4-02/"
            f"{FIXTURE_NAMESPACE}/guard-policy"
        ),
    )
)
POLICY_VERSION = 1
POLICY_VERSION_KEY = f"{POLICY_GLOBAL_ID}:{POLICY_VERSION}"
GUARD_POLICY_VERSION_KEY = f"{GUARD_POLICY_GLOBAL_ID}:{POLICY_VERSION}"
POLICY_KEY = f"p4_project_work_{FIXTURE_NAMESPACE.replace('-', '_')}"
GUARD_POLICY_KEY = f"{POLICY_KEY}_guard"
require(
    len(POLICY_KEY) <= 64 and len(GUARD_POLICY_KEY) <= 64,
    "Synthetic Project work policy keys exceed the DocType field contract",
)
POLICY_TITLE = f"Synthetic P4-02 {FIXTURE_NAMESPACE} runtime work policy"
GUARD_POLICY_TITLE = f"{POLICY_TITLE} guard"
ROLE_KEY = "project_engineer"
WBS_STATE_KEY = "queued_custom"
WORK_STATE_DEFINITIONS = {
    "action": ("action_queued_custom", "Open"),
    "decision_request": ("decision_waiting_custom", "Requested"),
    "issue": ("issue_triage_custom", "Open"),
    "risk": ("risk_logged_custom", "Identified"),
}


def fixture_key(name: str) -> str:
    return f"{FIXTURE_PREFIX}-{name}"


MAIN_PROJECT_CREATE_KEY = fixture_key("main-project-create")
CYCLE_PROJECT_CREATE_KEY = fixture_key("cycle-project-create")
GUARD_PROJECT_CREATE_KEY = fixture_key("guard-project-create")
CONCURRENCY_PROJECT_CREATE_KEY = fixture_key("concurrency-project-create")
MAIN_TEAM_KEY = fixture_key("main-team")
CYCLE_TEAM_KEY = fixture_key("cycle-team")
GUARD_TEAM_KEY = fixture_key("guard-team")
CONCURRENCY_TEAM_KEY = fixture_key("concurrency-team")
MAIN_PLAN_KEY = fixture_key("main-plan")
MAIN_BASELINE_KEY = fixture_key("main-baseline")
MAIN_SHIFTED_PLAN_KEY = fixture_key("main-shifted-plan")
GUARD_PLAN_KEY = fixture_key("guard-plan")
GUARD_BASELINE_KEY = fixture_key("guard-baseline")
GUARD_WORK_ITEM_KEY = fixture_key("guard-work-item")
CONCURRENCY_PLAN_KEYS = (
    fixture_key("concurrency-plan-a"),
    fixture_key("concurrency-plan-b"),
)
MAIN_WORK_ITEM_KEYS = {
    "risk": fixture_key("main-risk"),
    "issue": fixture_key("main-issue"),
    "action": fixture_key("main-action"),
    "decision_request": fixture_key("main-decision"),
}
PARENT_CYCLE_KEY = fixture_key("parent-cycle-rejected")
DEPENDENCY_CYCLE_KEY = fixture_key("dependency-cycle-rejected")
VERSION_CONFLICT_KEY = fixture_key("version-conflict")
CSRF_REJECTED_KEY = fixture_key("csrf-rejected")
TENANT_INJECTION_KEY = fixture_key("tenant-injection")
OWNER_REJECTED_KEY = fixture_key("owner-command-rejected")
IDOR_UNAUTHORIZED_KEY = fixture_key("idor-unauthorized")
IDOR_ABSENT_KEY = fixture_key("idor-absent")


def fixture_id(scope: str, name: str) -> str:
    return str(
        uuid5(
            NAMESPACE_URL,
            (
                "https://npi-one.example.invalid/runtime/p4-02/"
                f"{FIXTURE_NAMESPACE}/{scope}/{name}"
            ),
        )
    )


def canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def json_value(value: object) -> object:
    return json.loads(value) if isinstance(value, str) else value


def utc_iso(value: object) -> str:
    raw = str(value).replace(" ", "T")
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat().replace(
        "+00:00",
        "Z",
    )


def ensure_runtime_user(
    administrator,
    base_url: str,
    user: str,
    password: str,
    csrf_token: str,
) -> None:
    existing = request(administrator, base_url, user_resource_path(user))
    if existing.status == 404:
        created = create_resource(
            administrator,
            base_url,
            "User",
            {
                "email": user,
                "enabled": 1,
                "first_name": "NPI P4-02 Runtime",
                "language": "en",
                "last_name": "Fixture",
                "new_password": password,
                "send_welcome_email": 0,
                "user_type": "Website User",
            },
            csrf_token,
        )
        require(
            created.status in {200, 201},
            f"Synthetic Project work user creation returned HTTP {created.status}",
        )
    else:
        require(
            existing.status == 200,
            f"Synthetic Project work user lookup returned HTTP {existing.status}",
        )
        data = existing.body.get("data", {})
        require(
            data.get("name") == user
            and data.get("email") == user
            and data.get("enabled") == 1
            and data.get("first_name") == "NPI P4-02 Runtime"
            and data.get("language") == "en"
            and data.get("last_name") == "Fixture"
            and data.get("user_type") == "Website User",
            f"Refusing to reuse an unknown local fixture user: {user}",
        )
        updated = update_resource(
            administrator,
            base_url,
            "User",
            user,
            {"enabled": 1, "new_password": password},
            csrf_token,
        )
        require(
            updated.status == 200,
            f"Synthetic Project work user reset returned HTTP {updated.status}",
        )

    retained = request(administrator, base_url, user_resource_path(user))
    require(retained.status == 200, f"Synthetic Project work user is unavailable: {user}")
    data = retained.body.get("data", {})
    roles = {
        row.get("role")
        for row in data.get("roles", [])
        if isinstance(row, dict)
    }
    require(
        data.get("enabled") == 1
        and data.get("language") == "en"
        and data.get("user_type") == "Website User"
        and "System Manager" not in roles,
        f"Synthetic Project work user gained elevated access: {user}",
    )


def policy_payload(*, guard: bool = False) -> dict[str, object]:
    return {
        "policy_global_id": (
            GUARD_POLICY_GLOBAL_ID if guard else POLICY_GLOBAL_ID
        ),
        "policy_key": GUARD_POLICY_KEY if guard else POLICY_KEY,
        "policy_version": POLICY_VERSION,
        "title": GUARD_POLICY_TITLE if guard else POLICY_TITLE,
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
                "initialStateKey": state_key,
                "states": [
                    {
                        "key": state_key,
                        "labelSource": label_source,
                        "terminal": False,
                    }
                ],
            }
            for kind, (state_key, label_source) in WORK_STATE_DEFINITIONS.items()
        ],
    }


def expected_policy_reference(*, guard: bool = False) -> dict[str, object]:
    policy = policy_payload(guard=guard)
    snapshot_payload = {
        "policyGlobalId": policy["policy_global_id"],
        "policyKey": policy["policy_key"],
        "policyVersion": POLICY_VERSION,
        "roleKeys": policy["role_keys"],
        "wbsLifecycle": policy["wbs_states"],
        "workItemLifecycles": policy["work_item_lifecycles"],
    }
    return {
        "globalId": policy["policy_global_id"],
        "version": POLICY_VERSION,
        "snapshotHash": canonical_hash(snapshot_payload),
    }


def ensure_work_policy(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    guard: bool = False,
) -> dict[str, object]:
    expected = policy_payload(guard=guard)
    version_key = (
        GUARD_POLICY_VERSION_KEY if guard else POLICY_VERSION_KEY
    )
    result = get_resource(
        administrator,
        base_url,
        "NPI Project Work Policy Version",
        version_key,
    )
    if result.status == 404:
        result = create_resource(
            administrator,
            base_url,
            "NPI Project Work Policy Version",
            expected,
            csrf_token,
        )
    require(
        result.status in {200, 201},
        f"Synthetic Project work policy returned HTTP {result.status}",
    )
    data = result.body.get("data", {})
    for field in (
        "policy_global_id",
        "policy_key",
        "policy_version",
        "title",
        "publication_state",
    ):
        require(
            data.get(field) == expected[field],
            f"Synthetic Project work policy {field} drifted",
        )
    require(data.get("name") == version_key, "Work policy version key drifted")
    require(
        json_value(data.get("role_keys")) == expected["role_keys"],
        "Work policy roles drifted",
    )
    require(
        json_value(data.get("wbs_states")) == expected["wbs_states"],
        "Work policy WBS lifecycle drifted",
    )
    require(
        json_value(data.get("work_item_lifecycles"))
        == expected["work_item_lifecycles"],
        "Work policy kind lifecycles drifted",
    )
    snapshot_hash = data.get("snapshot_hash")
    require(
        snapshot_hash
        == expected_policy_reference(guard=guard)["snapshotHash"],
        "Work policy snapshot hash drifted",
    )
    return {
        "globalId": expected["policy_global_id"],
        "version": POLICY_VERSION,
        "snapshotHash": snapshot_hash,
    }


def ensure_project(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    owner: str,
    business_code: str,
    title: str,
    idempotency_key: str,
) -> str:
    payload = project_payload(owner)
    payload["businessCode"] = business_code
    payload["title"] = title
    result = post_project(
        administrator,
        base_url,
        payload,
        csrf_token=csrf_token,
        idempotency_key=idempotency_key,
    )
    require(result.status == 201, f"Synthetic Project returned HTTP {result.status}")
    require(
        result.headers.get("Idempotency-Replayed") == "false",
        "Synthetic Project creation was not a fresh command",
    )
    project_id = result.body.get("project", {}).get("globalId")
    require(isinstance(project_id, str), "Synthetic Project identity is unavailable")
    replay = post_project(
        administrator,
        base_url,
        payload,
        csrf_token=csrf_token,
        idempotency_key=idempotency_key,
    )
    require(
        replay.status == 201
        and replay.headers.get("Idempotency-Replayed") == "true"
        and replay.body == result.body,
        "Synthetic Project did not replay its complete sealed response",
    )
    rows = list_resources(
        administrator,
        base_url,
        "NPI Engineering Project",
        filters=[["global_id", "=", project_id]],
        fields=[
            "business_code",
            "global_id",
            "owner_user_id",
            "tenant_id",
        ],
    )
    require(
        rows
        == [
            {
                "business_code": business_code,
                "global_id": project_id,
                "owner_user_id": owner,
                "tenant_id": TENANT_ID,
            }
        ],
        "Synthetic Project persistence drifted",
    )
    return project_id


def business_code(scope: str) -> str:
    return f"P4-02-{FIXTURE_NAMESPACE.upper()}-{scope.upper()}"


def project_title(scope: str) -> str:
    return f"Synthetic P4-02 {FIXTURE_NAMESPACE} runtime {scope} Project"


def expected_project_payload_hash(scope: str, owner: str) -> str:
    payload = project_payload(owner)
    payload["businessCode"] = business_code(scope)
    payload["title"] = project_title(scope)
    references = [
        {
            "type": row["type"],
            "sourceSystem": row["sourceSystem"],
            "sourceObjectId": row["sourceObjectId"],
            "globalId": row.get("globalId"),
        }
        for row in payload["references"]  # type: ignore[union-attr]
    ]
    normalized = {
        **payload,
        "ownerUserId": str(payload["ownerUserId"]).casefold(),
        "references": sorted(
            references,
            key=lambda row: (
                str(row["type"]),
                str(row["sourceSystem"]),
                str(row["sourceObjectId"]),
                str(row["globalId"] or ""),
            ),
        ),
    }
    return canonical_hash(normalized)


def _assert_existing_policy_compatible(
    result: HttpResult,
    *,
    guard: bool,
) -> None:
    expected = policy_payload(guard=guard)
    version_key = (
        GUARD_POLICY_VERSION_KEY if guard else POLICY_VERSION_KEY
    )
    require(result.status == 200, "Fixture work policy lookup drifted")
    data = result.body.get("data", {})
    require(
        data.get("name") == version_key
        and all(
            data.get(field) == expected[field]
            for field in (
                "policy_global_id",
                "policy_key",
                "policy_version",
                "title",
                "publication_state",
            )
        )
        and json_value(data.get("role_keys")) == expected["role_keys"]
        and json_value(data.get("wbs_states")) == expected["wbs_states"]
        and json_value(data.get("work_item_lifecycles"))
        == expected["work_item_lifecycles"],
        "Existing fixture work policy drifted; refusing to write",
    )
    require(
        data.get("snapshot_hash")
        == expected_policy_reference(guard=guard)["snapshotHash"],
        "Existing fixture work policy snapshot drifted; refusing to write",
    )


def _assert_existing_user_compatible(result: HttpResult, user: str) -> None:
    require(result.status == 200, "Fixture user lookup drifted")
    data = result.body.get("data", {})
    roles = {
        row.get("role")
        for row in data.get("roles", [])
        if isinstance(row, dict)
    }
    require(
        data.get("name") == user
        and data.get("email") == user
        and data.get("enabled") == 1
        and data.get("first_name") == "NPI P4-02 Runtime"
        and data.get("language") == "en"
        and data.get("last_name") == "Fixture"
        and data.get("user_type") == "Website User"
        and "System Manager" not in roles,
        f"Existing fixture user drifted; refusing to write: {user}",
    )


def _scope_expected_commands(scope: str) -> tuple[tuple[str, str], ...]:
    if scope == "main":
        return (
            (MAIN_TEAM_KEY, "project.team.configure"),
            (MAIN_PLAN_KEY, "project.work_plan.apply"),
            (MAIN_BASELINE_KEY, "project.plan_baseline.capture"),
            (MAIN_SHIFTED_PLAN_KEY, "project.work_plan.apply"),
            *(
                (
                    MAIN_WORK_ITEM_KEYS[kind],
                    "project.domain_work_item.create",
                )
                for kind in ("risk", "issue", "action", "decision_request")
            ),
        )
    if scope == "cycle":
        return ((CYCLE_TEAM_KEY, "project.team.configure"),)
    if scope == "guard":
        return (
            (GUARD_TEAM_KEY, "project.team.configure"),
            (GUARD_PLAN_KEY, "project.work_plan.apply"),
            (GUARD_BASELINE_KEY, "project.plan_baseline.capture"),
            (GUARD_WORK_ITEM_KEY, "project.domain_work_item.create"),
        )
    if scope == "concurrency":
        return (
            (CONCURRENCY_TEAM_KEY, "project.team.configure"),
            (CONCURRENCY_PLAN_KEYS[0], "project.work_plan.apply"),
            (CONCURRENCY_PLAN_KEYS[1], "project.work_plan.apply"),
        )
    raise RuntimeError(f"Unknown fixture scope: {scope}")


def _expected_existing_command_payload(
    scope: str,
    raw_key: str,
    project_id: str,
    *,
    stage_id: str | None,
    responses: dict[str, dict[str, object]],
) -> dict[str, object]:
    policy_ref = expected_policy_reference(guard=scope == "guard")
    if raw_key in {
        MAIN_TEAM_KEY,
        CYCLE_TEAM_KEY,
        GUARD_TEAM_KEY,
        CONCURRENCY_TEAM_KEY,
    }:
        return team_payload(
            scope,
            project_id,
            policy_ref,
            OWNER_USER,
            MEMBER_USER,
        )
    if raw_key == MAIN_PLAN_KEY:
        return main_plan_payload(policy_ref, shifted=False)
    if raw_key == MAIN_SHIFTED_PLAN_KEY:
        return main_plan_payload(policy_ref, shifted=True)
    if raw_key == GUARD_PLAN_KEY:
        return guard_plan_payload(policy_ref)
    if raw_key in CONCURRENCY_PLAN_KEYS:
        return concurrency_plan_payload(
            policy_ref,
            variant="a" if raw_key == CONCURRENCY_PLAN_KEYS[0] else "b",
        )
    if raw_key == MAIN_BASELINE_KEY:
        return {
            "expectedProjectVersion": 3,
            "workPolicyRef": policy_ref,
            "label": "Synthetic P4-02 plan baseline",
        }
    if raw_key == GUARD_BASELINE_KEY:
        return {
            "expectedProjectVersion": 3,
            "workPolicyRef": policy_ref,
            "label": "Synthetic P4-02 guard plan baseline",
        }
    if raw_key == GUARD_WORK_ITEM_KEY:
        return domain_item_payload(
            kind="risk",
            expected_version=4,
            policy_ref=policy_ref,
            owner=OWNER_USER,
            stage_id=None,
            wbs_item_id=plan_ids("guard")["wbs-child"],
            related_ids=[],
        )
    for offset, kind in enumerate(
        ("risk", "issue", "action", "decision_request"),
        start=5,
    ):
        if raw_key != MAIN_WORK_ITEM_KEYS[kind]:
            continue
        risk_response = responses.get(MAIN_WORK_ITEM_KEYS["risk"], {})
        risk_id = risk_response.get("globalId")
        if kind == "action":
            require(
                isinstance(risk_id, str),
                "Existing action fixture lost its related risk identity",
            )
        return domain_item_payload(
            kind=kind,
            expected_version=offset,
            policy_ref=policy_ref,
            owner=(
                OWNER_USER
                if kind in {"risk", "action"}
                else MEMBER_USER
            ),
            stage_id=stage_id if kind == "risk" else None,
            wbs_item_id=plan_ids("main")["wbs-child"],
            related_ids=[str(risk_id)] if kind == "action" else [],
        )
    raise RuntimeError(f"Unknown existing fixture command: {raw_key}")


def verify_fresh_fixture_namespace(
    administrator,
    base_url: str,
    *,
    owner: str,
    member: str,
) -> dict[str, str]:
    """Fail closed unless this process-owned namespace has no prior state."""
    states: dict[str, str] = {}
    for user in (owner, member):
        result = request(administrator, base_url, user_resource_path(user))
        require(
            result.status == 404,
            f"Fresh fixture namespace already contains user state: {user}",
        )
        states[f"user:{user}"] = "absent"

    for guard, version_key in (
        (False, POLICY_VERSION_KEY),
        (True, GUARD_POLICY_VERSION_KEY),
    ):
        expected = policy_payload(guard=guard)
        result = get_resource(
            administrator,
            base_url,
            "NPI Project Work Policy Version",
            version_key,
        )
        global_id_rows = list_resources(
            administrator,
            base_url,
            "NPI Project Work Policy Version",
            filters=[
                [
                    "policy_global_id",
                    "=",
                    expected["policy_global_id"],
                ]
            ],
            fields=["name"],
        )
        policy_key_rows = list_resources(
            administrator,
            base_url,
            "NPI Project Work Policy Version",
            filters=[["policy_key", "=", expected["policy_key"]]],
            fields=["name"],
        )
        require(
            result.status == 404
            and global_id_rows == []
            and policy_key_rows == [],
            "Fresh fixture namespace already contains work policy state",
        )
        states[f"policy:{version_key}"] = "absent"

    create_keys = {
        "main": MAIN_PROJECT_CREATE_KEY,
        "cycle": CYCLE_PROJECT_CREATE_KEY,
        "guard": GUARD_PROJECT_CREATE_KEY,
        "concurrency": CONCURRENCY_PROJECT_CREATE_KEY,
    }
    for scope, create_key in create_keys.items():
        projects = list_resources(
            administrator,
            base_url,
            "NPI Engineering Project",
            filters=[["business_code", "=", business_code(scope)]],
            fields=["global_id"],
        )
        project_idempotency = list_resources(
            administrator,
            base_url,
            "NPI Project Idempotency",
            filters=[
                [
                    "actor_key_hash",
                    "=",
                    actor_key_hash("Administrator", create_key),
                ]
            ],
            fields=["name"],
        )
        work_idempotency = [
            row
            for raw_key, _operation in _scope_expected_commands(scope)
            for row in list_resources(
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
        ]
        require(
            projects == []
            and project_idempotency == []
            and work_idempotency == [],
            f"Fresh fixture namespace already contains Project state: {scope}",
        )
        states[f"project:{scope}"] = "absent"

    return states


def classify_fixture_state(
    administrator,
    base_url: str,
    *,
    owner: str,
    member: str,
) -> dict[str, str]:
    """Classify all revision-owned fixtures before the first domain write."""
    states: dict[str, str] = {}
    policy_available: dict[bool, bool] = {}
    for user in (owner, member):
        result = request(administrator, base_url, user_resource_path(user))
        if result.status == 404:
            states[f"user:{user}"] = "absent"
        else:
            _assert_existing_user_compatible(result, user)
            states[f"user:{user}"] = "compatible"

    for guard, key in (
        (False, POLICY_VERSION_KEY),
        (True, GUARD_POLICY_VERSION_KEY),
    ):
        result = get_resource(
            administrator,
            base_url,
            "NPI Project Work Policy Version",
            key,
        )
        if result.status == 404:
            states[f"policy:{key}"] = "absent"
            policy_available[guard] = False
        else:
            _assert_existing_policy_compatible(result, guard=guard)
            states[f"policy:{key}"] = "compatible"
            policy_available[guard] = True

    create_keys = {
        "main": MAIN_PROJECT_CREATE_KEY,
        "cycle": CYCLE_PROJECT_CREATE_KEY,
        "guard": GUARD_PROJECT_CREATE_KEY,
        "concurrency": CONCURRENCY_PROJECT_CREATE_KEY,
    }
    max_versions = {"main": 9, "cycle": 2, "guard": 5, "concurrency": 3}
    for scope, create_key in create_keys.items():
        rows = list_resources(
            administrator,
            base_url,
            "NPI Engineering Project",
            filters=[["business_code", "=", business_code(scope)]],
            fields=[
                "global_id",
                "business_code",
                "title",
                "owner_user_id",
                "tenant_id",
                "optimistic_version",
                "work_policy_global_id",
                "work_policy_snapshot_hash",
                "work_policy_version",
                "work_plan_revision",
                "active_plan_baseline_global_id",
            ],
        )
        project_records = list_resources(
            administrator,
            base_url,
            "NPI Project Idempotency",
            filters=[
                [
                    "actor_key_hash",
                    "=",
                    actor_key_hash("Administrator", create_key),
                ]
            ],
            fields=[
                "actor",
                "actor_key_hash",
                "payload_hash",
                "project_global_id",
                "tenant_id",
            ],
        )
        if not rows:
            require(
                project_records == [],
                f"Fixture {scope} has orphan Project idempotency; refusing to write",
            )
            for raw_key, _operation in _scope_expected_commands(scope):
                orphan_rows = list_resources(
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
                require(
                    orphan_rows == [],
                    f"Fixture {scope} has orphan work history; refusing to write",
                )
            states[f"project:{scope}"] = "absent"
            continue
        require(
            len(rows) == 1 and len(project_records) == 1,
            f"Fixture {scope} Project identity drifted; refusing to write",
        )
        project = rows[0]
        project_id = str(project["global_id"])
        require(
            project["business_code"] == business_code(scope)
            and project["title"] == project_title(scope)
            and project["owner_user_id"] == owner
            and project["tenant_id"] == TENANT_ID
            and project_records[0]["actor"] == "Administrator"
            and project_records[0]["tenant_id"] == TENANT_ID
            and project_records[0]["project_global_id"] == project_id
            and project_records[0]["payload_hash"]
            == expected_project_payload_hash(scope, owner),
            f"Fixture {scope} Project drifted; refusing to write",
        )
        work_rows = list_resources(
            administrator,
            base_url,
            "NPI Project Work Idempotency",
            filters=[["project_global_id", "=", project_id]],
            fields=[
                "actor",
                "actor_key_hash",
                "operation",
                "payload_hash",
                "project_global_id",
                "response_json",
                "response_sealed",
                "tenant_id",
            ],
        )
        expected_commands = _scope_expected_commands(scope)
        command_by_hash = {
            actor_key_hash("Administrator", key): (key, operation)
            for key, operation in expected_commands
        }
        require(
            all(
                row["actor_key_hash"] in command_by_hash
                and row["actor"] == "Administrator"
                and row["tenant_id"] == TENANT_ID
                and row["project_global_id"] == project_id
                and row["operation"]
                == command_by_hash[str(row["actor_key_hash"])][1]
                and row["response_sealed"] == 1
                and re.fullmatch(r"[a-f0-9]{64}", str(row["payload_hash"]))
                and isinstance(json_value(row["response_json"]), dict)
                for row in work_rows
            ),
            f"Fixture {scope} work history drifted; refusing to write",
        )
        present = {str(row["actor_key_hash"]) for row in work_rows}
        require(
            len(present) == len(work_rows),
            f"Fixture {scope} work identities are not unique; refusing to write",
        )
        require(
            not work_rows or policy_available[scope == "guard"],
            f"Fixture {scope} lost its immutable work policy; refusing to write",
        )
        if scope != "concurrency":
            ordered_hashes = [
                actor_key_hash("Administrator", key)
                for key, _operation in expected_commands
            ]
            require(
                ordered_hashes[: len(present)] == [
                    value for value in ordered_hashes if value in present
                ]
                and len(present) <= len(ordered_hashes),
                f"Fixture {scope} command history is not a prefix; refusing to write",
            )
        else:
            plan_count = sum(
                actor_key_hash("Administrator", key) in present
                for key in CONCURRENCY_PLAN_KEYS
            )
            require(
                plan_count <= 1
                and (
                    not present
                    or actor_key_hash(
                        "Administrator", CONCURRENCY_TEAM_KEY
                    )
                    in present
                ),
                "Concurrency fixture history drifted; refusing to write",
            )

        responses: dict[str, dict[str, object]] = {}
        rows_by_key: dict[str, dict[str, object]] = {}
        for row in work_rows:
            raw_key, _operation = command_by_hash[str(row["actor_key_hash"])]
            response = json_value(row["response_json"])
            require(
                isinstance(response, dict),
                f"Fixture {scope} sealed response drifted; refusing to write",
            )
            responses[raw_key] = response
            rows_by_key[raw_key] = row
        stage_id: str | None = None
        if scope == "main" and any(
            key in responses for key in MAIN_WORK_ITEM_KEYS.values()
        ):
            gates = list_resources(
                administrator,
                base_url,
                "NPI Gate Shell",
                filters=[["project_global_id", "=", project_id]],
                fields=["gate_key", "global_id"],
            )
            g0_ids = [
                str(row["global_id"])
                for row in gates
                if row.get("gate_key") == "G0"
            ]
            require(
                len(g0_ids) == 1,
                "Existing main fixture lost its G0 identity; refusing to write",
            )
            stage_id = g0_ids[0]
        for raw_key, operation in expected_commands:
            if raw_key not in responses:
                continue
            response = responses[raw_key]
            payload = _expected_existing_command_payload(
                scope,
                raw_key,
                project_id,
                stage_id=stage_id,
                responses=responses,
            )
            row = rows_by_key[raw_key]
            require(
                row["payload_hash"]
                == canonical_hash(
                    normalized_command_payload(
                        project_id,
                        operation,
                        payload,
                    )
                ),
                f"Fixture {scope} payload drifted; refusing to write",
            )
            require(
                response.get("projectId") == project_id,
                f"Fixture {scope} response Project drifted; refusing to write",
            )
            if operation in {
                "project.team.configure",
                "project.work_plan.apply",
            }:
                global_id = project_id
                object_version = int(payload["expectedProjectVersion"]) + 1
                result = "updated"
                require(
                    response.get("projectVersion") == object_version,
                    f"Fixture {scope} response version drifted; refusing to write",
                )
            else:
                global_id = response.get("globalId")
                object_version = 1
                result = "created"
                require(
                    isinstance(global_id, str)
                    and response.get("version") == object_version,
                    f"Fixture {scope} created response drifted; refusing to write",
                )
            audits = audit_rows(
                administrator,
                base_url,
                global_id=str(global_id),
                operation=operation,
            )
            expected_audit_count = (
                sum(
                    candidate_operation == operation
                    and candidate_key in responses
                    for candidate_key, candidate_operation in expected_commands
                )
                if global_id == project_id
                else 1
            )
            matches = [
                audit
                for audit in audits
                if audit["actor"] == "Administrator"
                and int(audit["object_version"]) == object_version
                and audit["result"] == result
                and audit["trace_id"] == command_trace_id(raw_key)
                and isinstance(json_value(audit["input_summary"]), dict)
                and json_value(audit["input_summary"]).get("requestId")
                == command_request_id(raw_key)
            ]
            require(
                len(audits) == expected_audit_count
                and len(matches) == 1,
                f"Fixture {scope} audit drifted; refusing to write",
            )

        team_present = any(
            key in responses
            for key in (
                MAIN_TEAM_KEY,
                CYCLE_TEAM_KEY,
                GUARD_TEAM_KEY,
                CONCURRENCY_TEAM_KEY,
            )
        )
        plan_present = any(
            key in responses
            for key in (
                MAIN_PLAN_KEY,
                GUARD_PLAN_KEY,
                *CONCURRENCY_PLAN_KEYS,
            )
        )
        baseline_present = any(
            key in responses
            for key in (MAIN_BASELINE_KEY, GUARD_BASELINE_KEY)
        )
        work_item_count = sum(
            key in responses
            for key in (
                *MAIN_WORK_ITEM_KEYS.values(),
                GUARD_WORK_ITEM_KEY,
            )
        )
        expected_policy_ref = expected_policy_reference(
            guard=scope == "guard"
        )
        plan_count = sum(
            key in responses
            for key in (
                MAIN_PLAN_KEY,
                MAIN_SHIFTED_PLAN_KEY,
                GUARD_PLAN_KEY,
                *CONCURRENCY_PLAN_KEYS,
            )
        )
        baseline_key = (
            GUARD_BASELINE_KEY
            if scope == "guard"
            else MAIN_BASELINE_KEY
        )
        expected_baseline_id = (
            responses.get(baseline_key, {}).get("globalId")
            if baseline_present
            else None
        )
        require(
            (
                not work_rows
                and not project.get("work_policy_global_id")
                and not project.get("work_policy_snapshot_hash")
                and int(project.get("work_policy_version") or 0) == 0
            )
            or (
                bool(work_rows)
                and project.get("work_policy_global_id")
                == expected_policy_ref["globalId"]
                and project.get("work_policy_snapshot_hash")
                == expected_policy_ref["snapshotHash"]
                and project.get("work_policy_version")
                == expected_policy_ref["version"]
            ),
            f"Fixture {scope} Project policy state drifted; refusing to write",
        )
        require(
            int(project.get("work_plan_revision") or 0) == plan_count
            and (project.get("active_plan_baseline_global_id") or None)
            == expected_baseline_id,
            f"Fixture {scope} plan state drifted; refusing to write",
        )
        expected_counts = {
            "NPI Project Member": (
                2
                if team_present and scope in {"main", "guard"}
                else int(team_present)
            ),
            "NPI Project Role Assignment": int(team_present),
            "NPI Project Substitution": int(
                team_present and scope in {"main", "guard"}
            ),
            "NPI Project RACI Assignment": int(team_present),
            "NPI WBS Item": 2 if plan_present else 0,
            "NPI WBS Dependency": int(plan_present),
            "NPI WBS Plan Baseline": int(baseline_present),
            "NPI Domain Work Item": work_item_count,
        }
        for doctype, expected_count in expected_counts.items():
            scoped_rows = list_resources(
                administrator,
                base_url,
                doctype,
                filters=[["project_global_id", "=", project_id]],
                fields=["project_global_id", "tenant_id"],
            )
            require(
                len(scoped_rows) == expected_count
                and all(
                    row["project_global_id"] == project_id
                    and row["tenant_id"] == TENANT_ID
                    for row in scoped_rows
                ),
                f"Fixture {scope} persistence drifted; refusing to write",
            )
        expected_version = 1 + len(work_rows)
        require(
            int(project["optimistic_version"]) == expected_version
            and expected_version <= max_versions[scope],
            f"Fixture {scope} version/history drifted; refusing to write",
        )
        states[f"project:{scope}"] = (
            "compatible-complete"
            if expected_version == max_versions[scope]
            else "compatible-partial"
        )
    return states


def verify_cross_process_replay(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    owner: str,
    member: str,
) -> dict[str, object]:
    """Prove a retained response can be replayed by a separate process."""
    fixture_states = classify_fixture_state(
        administrator,
        base_url,
        owner=owner,
        member=member,
    )
    expected_states = {
        f"user:{owner}": "compatible",
        f"user:{member}": "compatible",
        f"policy:{POLICY_VERSION_KEY}": "compatible",
        f"policy:{GUARD_POLICY_VERSION_KEY}": "compatible",
        "project:main": "compatible-complete",
        "project:cycle": "compatible-complete",
        "project:guard": "compatible-complete",
        "project:concurrency": "compatible-complete",
    }
    require(
        fixture_states == expected_states,
        "Replay-only fixture namespace is incomplete",
    )
    require_shared_template_history(
        administrator,
        base_url,
        fixture_states,
    )

    projects = list_resources(
        administrator,
        base_url,
        "NPI Engineering Project",
        filters=[["business_code", "=", business_code("main")]],
        fields=["global_id"],
    )
    require(
        len(projects) == 1
        and isinstance(projects[0].get("global_id"), str),
        "Replay-only main Project identity is unavailable",
    )
    project_id = str(projects[0]["global_id"])
    payload = team_payload(
        "main",
        project_id,
        expected_policy_reference(),
        owner,
        member,
    )
    expected_payload_hash = canonical_hash(
        normalized_command_payload(
            project_id,
            "project.team.configure",
            payload,
        )
    )
    idempotency_rows = list_resources(
        administrator,
        base_url,
        "NPI Project Work Idempotency",
        filters=[
            [
                "actor_key_hash",
                "=",
                actor_key_hash("Administrator", MAIN_TEAM_KEY),
            ]
        ],
        fields=[
            "name",
            "actor",
            "actor_key_hash",
            "operation",
            "payload_hash",
            "project_global_id",
            "response_json",
            "response_sealed",
            "tenant_id",
        ],
    )
    require(
        len(idempotency_rows) == 1,
        "Replay-only sealed idempotency record is unavailable",
    )
    retained_row = idempotency_rows[0]
    sealed_response = json_value(retained_row.get("response_json"))
    require(
        retained_row.get("actor") == "Administrator"
        and retained_row.get("actor_key_hash")
        == actor_key_hash("Administrator", MAIN_TEAM_KEY)
        and retained_row.get("operation") == "project.team.configure"
        and retained_row.get("payload_hash") == expected_payload_hash
        and retained_row.get("project_global_id") == project_id
        and retained_row.get("response_sealed") == 1
        and retained_row.get("tenant_id") == TENANT_ID
        and isinstance(sealed_response, dict),
        "Replay-only sealed idempotency evidence drifted",
    )

    before_context = get_work_context(
        administrator,
        base_url,
        project_id,
    )
    require(
        before_context.status == 200,
        "Replay-only Project work context is unavailable",
    )
    replay = work_command(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}:configure-team",
        payload,
        idempotency_key=MAIN_TEAM_KEY,
        csrf_token=csrf_token,
    )
    require_sealed_command_replay(
        replay,
        200,
        "Cross-process Project team command",
        sealed_response,
    )
    after_context = get_work_context(
        administrator,
        base_url,
        project_id,
    )
    retained_after = list_resources(
        administrator,
        base_url,
        "NPI Project Work Idempotency",
        filters=[
            [
                "actor_key_hash",
                "=",
                actor_key_hash("Administrator", MAIN_TEAM_KEY),
            ]
        ],
        fields=[
            "name",
            "actor",
            "actor_key_hash",
            "operation",
            "payload_hash",
            "project_global_id",
            "response_json",
            "response_sealed",
            "tenant_id",
        ],
    )
    require(
        after_context.status == 200
        and after_context.body == before_context.body
        and retained_after == idempotency_rows,
        "Replay-only command changed retained Project work state",
    )
    return {
        "fixtureStates": fixture_states,
        "mainProjectId": project_id,
        "replayedCommand": "project.team.configure",
        "replayedKey": MAIN_TEAM_KEY,
        "sealedResponseHash": canonical_hash(sealed_response),
    }


def require_shared_template_history(
    administrator,
    base_url: str,
    fixture_states: dict[str, str],
) -> None:
    if not any(
        key.startswith("project:") and value != "absent"
        for key, value in fixture_states.items()
    ):
        return
    template = get_resource(
        administrator,
        base_url,
        "NPI Project Template",
        TEMPLATE_GLOBAL_ID,
    )
    version = get_resource(
        administrator,
        base_url,
        "NPI Project Template Version",
        TEMPLATE_VERSION_KEY,
    )
    require(
        template.status == 200 and version.status == 200,
        "Existing P4-02 fixtures lost immutable Project template history",
    )


def command_request_id(idempotency_key: str) -> str:
    return str(
        uuid5(
            NAMESPACE_URL,
            f"https://npi-one.example.invalid/{idempotency_key}/request",
        )
    )


def command_trace_id(idempotency_key: str) -> str:
    return (
        "trace-"
        + uuid5(
            NAMESPACE_URL,
            f"https://npi-one.example.invalid/{idempotency_key}/trace",
        ).hex
    )


def work_command(
    opener,
    base_url: str,
    path: str,
    payload: dict[str, object],
    *,
    idempotency_key: str,
    csrf_token: str | None,
) -> HttpResult:
    request_id = command_request_id(idempotency_key)
    trace_id = command_trace_id(idempotency_key)
    headers = {
        "Idempotency-Key": idempotency_key,
        "X-Request-ID": request_id,
        "X-Trace-ID": trace_id,
    }
    if csrf_token is not None:
        headers["X-Frappe-CSRF-Token"] = csrf_token
    result = request(
        opener,
        base_url,
        path,
        method="POST",
        payload=payload,
        request_headers=headers,
    )
    require(
        result.headers.get("X-Request-ID") == request_id,
        "Project work request ID was not echoed",
    )
    require(
        result.headers.get("X-Trace-ID") == trace_id,
        "Project work trace ID was not echoed",
    )
    return HttpResult(
        result.status,
        result.headers,
        result.body,
        request_id=request_id,
        trace_id=trace_id,
    )


def _normalized_work_policy_ref(
    reference: dict[str, object],
) -> dict[str, object]:
    return {
        "global_id": reference["globalId"],
        "version": reference["version"],
        "snapshot_hash": reference["snapshotHash"],
    }


def normalized_command_payload(
    project_id: str,
    operation: str,
    payload: dict[str, object],
) -> dict[str, object]:
    common = {
        "projectId": project_id,
        "expectedProjectVersion": payload["expectedProjectVersion"],
        "workPolicyRef": _normalized_work_policy_ref(
            payload["workPolicyRef"]  # type: ignore[arg-type]
        ),
    }
    if operation == "project.team.configure":
        return {
            **common,
            "members": [
                {
                    "global_id": row["globalId"],
                    "user_id": str(row["userId"]).casefold(),
                    "effective_from": row["effectiveFrom"],
                    "effective_to": row.get("effectiveTo"),
                }
                for row in payload["members"]  # type: ignore[union-attr]
            ],
            "roleAssignments": [
                {
                    "global_id": row["globalId"],
                    "member_id": row["memberId"],
                    "role_key": row["roleKey"],
                    "effective_from": row["effectiveFrom"],
                    "effective_to": row.get("effectiveTo"),
                }
                for row in payload["roleAssignments"]  # type: ignore[union-attr]
            ],
            "substitutions": [
                {
                    "global_id": row["globalId"],
                    "role_assignment_id": row["roleAssignmentId"],
                    "substitute_member_id": row["substituteMemberId"],
                    "effective_from": row["effectiveFrom"],
                    "effective_to": row["effectiveTo"],
                }
                for row in payload["substitutions"]  # type: ignore[union-attr]
            ],
            "raciAssignments": [
                {
                    "global_id": row["globalId"],
                    "context_type": row["contextType"],
                    "context_id": row["contextId"],
                    "responsibility_key": row["responsibilityKey"],
                    "role_assignment_id": row["roleAssignmentId"],
                    "raci": row["raci"],
                }
                for row in payload["raciAssignments"]  # type: ignore[union-attr]
            ],
        }
    if operation == "project.work_plan.apply":
        return {
            **common,
            "items": [
                {
                    "global_id": row["globalId"],
                    "code": row["code"],
                    "title": row["title"],
                    "parent_id": row.get("parentId"),
                    "owner_role_assignment_id": row.get(
                        "ownerRoleAssignmentId"
                    ),
                    "planned_start": row["plannedStart"],
                    "planned_finish": row["plannedFinish"],
                    "actual_start": row.get("actualStart"),
                    "actual_finish": row.get("actualFinish"),
                    "milestone": row["milestone"],
                    "status_key": row["statusKey"],
                    "progress_percent": row["progressPercent"],
                    "critical": row["critical"],
                }
                for row in payload["items"]  # type: ignore[union-attr]
            ],
            "dependencies": [
                {
                    "global_id": row["globalId"],
                    "predecessor_item_id": row["predecessorItemId"],
                    "successor_item_id": row["successorItemId"],
                }
                for row in payload["dependencies"]  # type: ignore[union-attr]
            ],
        }
    if operation == "project.plan_baseline.capture":
        return {**common, "label": payload["label"]}
    if operation == "project.domain_work_item.create":
        context = payload["context"]
        require(isinstance(context, dict), "Domain context fixture drifted")
        return {
            **common,
            "kind": payload["kind"],
            "title": payload["title"],
            "detail": payload.get("detail"),
            "context": {
                "stage_id": context.get("stageId"),
                "wbs_item_id": context.get("wbsItemId"),
            },
            "ownerUserId": str(payload["ownerUserId"]).casefold(),
            "dueAt": str(payload["dueAt"]).replace("+00:00", "Z"),
            "severity": payload["severity"],
            "blocking": payload["blocking"],
            "relatedWorkItemIds": payload["relatedWorkItemIds"],
        }
    raise RuntimeError(f"Unknown Project work operation: {operation}")


def require_fresh_command_success(
    result: HttpResult,
    expected_status: int,
    label: str,
) -> dict[str, object]:
    body = require_command_success(result, expected_status, label)
    require(
        result.headers.get("Idempotency-Replayed") == "false",
        f"{label} was not a fresh command",
    )
    return body


def require_sealed_command_replay(
    result: HttpResult,
    expected_status: int,
    label: str,
    expected_body: dict[str, object],
) -> None:
    require_command_success(result, expected_status, f"{label} replay")
    require(
        result.headers.get("Idempotency-Replayed") == "true"
        and result.body == expected_body,
        f"{label} replay response drifted",
    )


def execute_success_with_replay(
    opener,
    base_url: str,
    path: str,
    payload: dict[str, object],
    *,
    operation: str,
    idempotency_key: str,
    csrf_token: str,
    expected_status: int,
    label: str,
    project_id: str,
    evidence: dict[str, HttpResult],
    payload_hashes: dict[str, str],
) -> dict[str, object]:
    first = work_command(
        opener,
        base_url,
        path,
        payload,
        idempotency_key=idempotency_key,
        csrf_token=csrf_token,
    )
    body = require_fresh_command_success(first, expected_status, label)
    replay = work_command(
        opener,
        base_url,
        path,
        payload,
        idempotency_key=idempotency_key,
        csrf_token=csrf_token,
    )
    require_sealed_command_replay(
        replay,
        expected_status,
        label,
        body,
    )
    evidence[idempotency_key] = first
    payload_hashes[idempotency_key] = canonical_hash(
        normalized_command_payload(project_id, operation, payload)
    )
    return body


def get_work_context(opener, base_url: str, project_id: str) -> HttpResult:
    request_id = str(uuid4())
    trace_id = f"trace-{uuid4().hex}"
    result = request(
        opener,
        base_url,
        f"/api/npi/v1/projects/{project_id}/work-context",
        request_headers={
            "X-Request-ID": request_id,
            "X-Trace-ID": trace_id,
        },
    )
    require(
        result.headers.get("X-Request-ID") == request_id,
        "Project work-context request ID was not echoed",
    )
    require(
        result.headers.get("X-Trace-ID") == trace_id,
        "Project work-context trace ID was not echoed",
    )
    return HttpResult(
        result.status,
        result.headers,
        result.body,
        request_id=request_id,
        trace_id=trace_id,
    )


def list_work_items(
    opener,
    base_url: str,
    project_id: str,
    **query: object,
) -> HttpResult:
    request_id = str(uuid4())
    trace_id = f"trace-{uuid4().hex}"
    suffix = urllib.parse.urlencode(
        {
            key: str(value).lower() if isinstance(value, bool) else str(value)
            for key, value in query.items()
        }
    )
    path = f"/api/npi/v1/projects/{project_id}/domain-work-items"
    if suffix:
        path = f"{path}?{suffix}"
    result = request(
        opener,
        base_url,
        path,
        request_headers={
            "X-Request-ID": request_id,
            "X-Trace-ID": trace_id,
        },
    )
    require(
        result.headers.get("X-Request-ID") == request_id,
        "Domain WorkItem request ID was not echoed",
    )
    require(
        result.headers.get("X-Trace-ID") == trace_id,
        "Domain WorkItem trace ID was not echoed",
    )
    return HttpResult(
        result.status,
        result.headers,
        result.body,
        request_id=request_id,
        trace_id=trace_id,
    )


def require_command_success(
    result: HttpResult,
    expected_status: int,
    label: str,
) -> dict[str, object]:
    require(
        result.status == expected_status,
        f"{label} returned HTTP {result.status}",
    )
    require(
        result.headers.get("Idempotency-Replayed") in {"true", "false"},
        f"{label} replay header drifted",
    )
    require(
        result.headers.get("Cache-Control") == "private, no-store",
        f"{label} cache control drifted",
    )
    return result.body


def require_field_error(result: HttpResult, path: str) -> None:
    field_errors = result.body.get("fieldErrors", [])
    require(
        any(
            isinstance(error, dict) and error.get("path") == path
            for error in field_errors
        ),
        f"Expected validation path was not returned: {path}",
    )


def team_ids(scope: str) -> dict[str, str]:
    return {
        name: fixture_id(scope, name)
        for name in (
            "member-owner",
            "member-substitute",
            "role-owner",
            "substitution",
            "raci-project",
        )
    }


def team_payload(
    scope: str,
    project_id: str,
    policy_ref: dict[str, object],
    owner: str,
    member: str,
    *,
    expected_version: int = 1,
) -> dict[str, object]:
    ids = team_ids(scope)
    members = [
        {
            "globalId": ids["member-owner"],
            "userId": owner,
            "effectiveFrom": "2026-01-01",
            "effectiveTo": "2099-12-31",
        }
    ]
    substitutions: list[dict[str, object]] = []
    if scope in {"main", "guard"}:
        members.append(
            {
                "globalId": ids["member-substitute"],
                "userId": member,
                "effectiveFrom": "2026-01-01",
                "effectiveTo": "2099-12-31",
            }
        )
        substitutions.append(
            {
                "globalId": ids["substitution"],
                "roleAssignmentId": ids["role-owner"],
                "substituteMemberId": ids["member-substitute"],
                "effectiveFrom": "2026-07-01",
                "effectiveTo": "2026-07-31",
            }
        )
    return {
        "expectedProjectVersion": expected_version,
        "workPolicyRef": policy_ref,
        "members": members,
        "roleAssignments": [
            {
                "globalId": ids["role-owner"],
                "memberId": ids["member-owner"],
                "roleKey": ROLE_KEY,
                "effectiveFrom": "2026-01-01",
                "effectiveTo": "2099-12-31",
            }
        ],
        "substitutions": substitutions,
        "raciAssignments": [
            {
                "globalId": ids["raci-project"],
                "contextType": "project",
                "contextId": project_id,
                "responsibilityKey": "project.delivery",
                "roleAssignmentId": ids["role-owner"],
                "raci": "responsible",
            }
        ],
    }


def plan_ids(scope: str) -> dict[str, str]:
    return {
        name: fixture_id(scope, name)
        for name in (
            "wbs-root",
            "wbs-child",
            "dependency-root-child",
            "dependency-child-root",
        )
    }


def wbs_item(
    *,
    global_id: str,
    code: str,
    title: str,
    planned_start: str,
    planned_finish: str,
    parent_id: str | None,
    owner_role_id: str,
    critical: bool,
) -> dict[str, object]:
    return {
        "globalId": global_id,
        "code": code,
        "title": title,
        "parentId": parent_id,
        "ownerRoleAssignmentId": owner_role_id,
        "plannedStart": planned_start,
        "plannedFinish": planned_finish,
        "actualStart": None,
        "actualFinish": None,
        "milestone": False,
        "statusKey": WBS_STATE_KEY,
        "progressPercent": 0,
        "critical": critical,
    }


def main_plan_payload(
    policy_ref: dict[str, object],
    *,
    shifted: bool,
) -> dict[str, object]:
    ids = plan_ids("main")
    role_id = team_ids("main")["role-owner"]
    dates = (
        ("2026-08-03", "2026-08-13", "2026-08-06", "2026-08-09")
        if shifted
        else ("2026-08-01", "2026-08-10", "2026-08-05", "2026-08-07")
    )
    return {
        "expectedProjectVersion": 4 if shifted else 2,
        "workPolicyRef": policy_ref,
        "items": [
            wbs_item(
                global_id=ids["wbs-root"],
                code="P4.02.ROOT",
                title="Synthetic work root",
                planned_start=dates[0],
                planned_finish=dates[1],
                parent_id=None,
                owner_role_id=role_id,
                critical=True,
            ),
            wbs_item(
                global_id=ids["wbs-child"],
                code="P4.02.CHILD",
                title="Synthetic work child",
                planned_start=dates[2],
                planned_finish=dates[3],
                parent_id=ids["wbs-root"],
                owner_role_id=role_id,
                critical=False,
            ),
        ],
        "dependencies": [
            {
                "globalId": ids["dependency-root-child"],
                "predecessorItemId": ids["wbs-root"],
                "successorItemId": ids["wbs-child"],
            }
        ],
    }


def guard_plan_payload(
    policy_ref: dict[str, object],
) -> dict[str, object]:
    ids = plan_ids("guard")
    role_id = team_ids("guard")["role-owner"]
    return {
        "expectedProjectVersion": 2,
        "workPolicyRef": policy_ref,
        "items": [
            wbs_item(
                global_id=ids["wbs-root"],
                code="P4.02.GUARD.ROOT",
                title="Synthetic guard work root",
                planned_start="2026-10-01",
                planned_finish="2026-10-10",
                parent_id=None,
                owner_role_id=role_id,
                critical=True,
            ),
            wbs_item(
                global_id=ids["wbs-child"],
                code="P4.02.GUARD.CHILD",
                title="Synthetic guard work child",
                planned_start="2026-10-03",
                planned_finish="2026-10-07",
                parent_id=ids["wbs-root"],
                owner_role_id=role_id,
                critical=False,
            ),
        ],
        "dependencies": [
            {
                "globalId": ids["dependency-root-child"],
                "predecessorItemId": ids["wbs-root"],
                "successorItemId": ids["wbs-child"],
            }
        ],
    }


def concurrency_plan_payload(
    policy_ref: dict[str, object],
    *,
    variant: str,
) -> dict[str, object]:
    require(variant in {"a", "b"}, "Concurrency fixture variant drifted")
    ids = plan_ids("concurrency")
    role_id = team_ids("concurrency")["role-owner"]
    first_is_root = variant == "a"
    predecessor = ids["wbs-root"] if first_is_root else ids["wbs-child"]
    successor = ids["wbs-child"] if first_is_root else ids["wbs-root"]
    dependency_id = (
        ids["dependency-root-child"]
        if first_is_root
        else ids["dependency-child-root"]
    )
    return {
        "expectedProjectVersion": 2,
        "workPolicyRef": policy_ref,
        "items": [
            wbs_item(
                global_id=ids["wbs-root"],
                code="P4.02.CONCURRENCY.A",
                title="Synthetic concurrent node A",
                planned_start="2026-11-01",
                planned_finish="2026-11-03",
                parent_id=None if first_is_root else ids["wbs-child"],
                owner_role_id=role_id,
                critical=first_is_root,
            ),
            wbs_item(
                global_id=ids["wbs-child"],
                code="P4.02.CONCURRENCY.B",
                title="Synthetic concurrent node B",
                planned_start="2026-11-04",
                planned_finish="2026-11-06",
                parent_id=ids["wbs-root"] if first_is_root else None,
                owner_role_id=role_id,
                critical=not first_is_root,
            ),
        ],
        "dependencies": [
            {
                "globalId": dependency_id,
                "predecessorItemId": predecessor,
                "successorItemId": successor,
            }
        ],
    }


def cyclic_plan_payload(
    policy_ref: dict[str, object],
    *,
    dependency_cycle: bool,
) -> dict[str, object]:
    ids = plan_ids("cycle")
    role_id = team_ids("cycle")["role-owner"]
    items = [
        wbs_item(
            global_id=ids["wbs-root"],
            code="P4.02.CYCLE.A",
            title="Synthetic cycle node A",
            planned_start="2026-09-01",
            planned_finish="2026-09-03",
            parent_id=None if dependency_cycle else ids["wbs-child"],
            owner_role_id=role_id,
            critical=False,
        ),
        wbs_item(
            global_id=ids["wbs-child"],
            code="P4.02.CYCLE.B",
            title="Synthetic cycle node B",
            planned_start="2026-09-04",
            planned_finish="2026-09-06",
            parent_id=None if dependency_cycle else ids["wbs-root"],
            owner_role_id=role_id,
            critical=False,
        ),
    ]
    dependencies: list[dict[str, object]] = []
    if dependency_cycle:
        dependencies = [
            {
                "globalId": ids["dependency-root-child"],
                "predecessorItemId": ids["wbs-root"],
                "successorItemId": ids["wbs-child"],
            },
            {
                "globalId": ids["dependency-child-root"],
                "predecessorItemId": ids["wbs-child"],
                "successorItemId": ids["wbs-root"],
            },
        ]
    return {
        "expectedProjectVersion": 2,
        "workPolicyRef": policy_ref,
        "items": items,
        "dependencies": dependencies,
    }


def domain_item_payload(
    *,
    kind: str,
    expected_version: int,
    policy_ref: dict[str, object],
    owner: str,
    stage_id: str | None,
    wbs_item_id: str,
    related_ids: list[str],
) -> dict[str, object]:
    due_dates = {
        "risk": "2000-01-01T00:00:00Z",
        "issue": "2099-01-01T00:00:00Z",
        "action": "2099-02-01T00:00:00Z",
        "decision_request": "2099-03-01T00:00:00Z",
    }
    severities = {
        "risk": "high",
        "issue": "critical",
        "action": "medium",
        "decision_request": "low",
    }
    context: dict[str, object] = {"wbsItemId": wbs_item_id}
    if stage_id is not None:
        context["stageId"] = stage_id
    return {
        "expectedProjectVersion": expected_version,
        "workPolicyRef": policy_ref,
        "kind": kind,
        "title": f"Synthetic {kind.replace('_', ' ')}",
        "detail": f"Deterministic P4-02 runtime {kind} fixture",
        "context": context,
        "ownerUserId": owner,
        "dueAt": due_dates[kind],
        "severity": severities[kind],
        "blocking": kind in {"risk", "issue"},
        "relatedWorkItemIds": related_ids,
    }


def require_context_shape(
    body: dict[str, object],
    *,
    project_id: str,
    version: int,
    administrator: bool,
) -> None:
    require(body.get("projectId") == project_id, "Work context Project drifted")
    require(body.get("projectVersion") == version, "Work context version drifted")
    require(body.get("initialized") is True, "Work context was not initialized")
    permissions = body.get("permissions")
    require(isinstance(permissions, dict), "Work context permissions are unavailable")
    require(permissions.get("canView") is True, "Work context view permission drifted")
    require(
        permissions.get("canContribute") is administrator
        and permissions.get("canAdminister") is administrator,
        "Work context write permissions drifted",
    )


def verify_no_work_idempotency(
    administrator,
    base_url: str,
    actor: str,
    raw_key: str,
) -> None:
    rows = list_resources(
        administrator,
        base_url,
        "NPI Project Work Idempotency",
        filters=[["actor_key_hash", "=", actor_key_hash(actor, raw_key)]],
        fields=["actor_key_hash"],
    )
    require(rows == [], "Rejected Project work command retained idempotency")


def verify_cycle_rejections(
    administrator,
    base_url: str,
    csrf_token: str,
    project_id: str,
    policy_ref: dict[str, object],
) -> None:
    path = f"/api/npi/v1/projects/{project_id}:apply-work-plan"
    cases = (
        (
            PARENT_CYCLE_KEY,
            cyclic_plan_payload(policy_ref, dependency_cycle=False),
            "items.parentId",
        ),
        (
            DEPENDENCY_CYCLE_KEY,
            cyclic_plan_payload(policy_ref, dependency_cycle=True),
            "dependencies",
        ),
    )
    for key, payload, expected_path in cases:
        result = work_command(
            administrator,
            base_url,
            path,
            payload,
            idempotency_key=key,
            csrf_token=csrf_token,
        )
        validate_problem(result, 422, "VALIDATION_FAILED")
        require_field_error(result, expected_path)
        verify_no_work_idempotency(
            administrator,
            base_url,
            "Administrator",
            key,
        )

    context = get_work_context(administrator, base_url, project_id)
    require(context.status == 200, "Cycle Project context is unavailable")
    require_context_shape(
        context.body,
        project_id=project_id,
        version=2,
        administrator=True,
    )
    require(
        context.body.get("wbsItems") == []
        and context.body.get("dependencies") == [],
        "Rejected cycle changed persisted WBS state",
    )
    for doctype in ("NPI WBS Item", "NPI WBS Dependency"):
        rows = list_resources(
            administrator,
            base_url,
            doctype,
            filters=[["project_global_id", "=", project_id]],
            fields=["name"],
        )
        require(rows == [], f"Rejected cycle persisted {doctype}")


def verify_final_work_context(
    body: dict[str, object],
    *,
    project_id: str,
    policy_ref: dict[str, object],
    owner: str,
    member: str,
    baseline_id: str,
) -> None:
    require_context_shape(
        body,
        project_id=project_id,
        version=9,
        administrator=True,
    )
    require(body.get("workPolicyRef") == policy_ref, "Work policy reference drifted")
    ids = team_ids("main")
    members = body.get("members")
    require(isinstance(members, list) and len(members) == 2, "Project members drifted")
    members_by_id = {item["globalId"]: item for item in members}
    require(
        members_by_id[ids["member-owner"]]["userId"] == owner
        and members_by_id[ids["member-substitute"]]["userId"] == member,
        "Project member identities drifted",
    )
    roles = body.get("roleAssignments")
    require(isinstance(roles, list) and len(roles) == 1, "Project roles drifted")
    require(
        roles[0]["globalId"] == ids["role-owner"]
        and roles[0]["roleKey"] == ROLE_KEY,
        "Project role assignment drifted",
    )
    substitutions = body.get("substitutions")
    require(
        isinstance(substitutions, list)
        and len(substitutions) == 1
        and substitutions[0]["globalId"] == ids["substitution"],
        "Project substitution drifted",
    )
    raci = body.get("raciAssignments")
    require(
        isinstance(raci, list)
        and len(raci) == 1
        and raci[0]["globalId"] == ids["raci-project"]
        and raci[0]["raci"] == "responsible",
        "Project RACI drifted",
    )

    work_ids = plan_ids("main")
    wbs_items = body.get("wbsItems")
    require(isinstance(wbs_items, list) and len(wbs_items) == 2, "WBS items drifted")
    wbs_by_id = {item["globalId"]: item for item in wbs_items}
    root = wbs_by_id[work_ids["wbs-root"]]
    child = wbs_by_id[work_ids["wbs-child"]]
    require(
        root["plannedStart"] == "2026-08-03"
        and root["plannedFinish"] == "2026-08-13"
        and root["statusKey"] == WBS_STATE_KEY
        and root["statusLabelSource"] == "Not started"
        and root["version"] == 2,
        "Shifted root WBS item drifted",
    )
    require(
        child["parentId"] == work_ids["wbs-root"]
        and child["plannedStart"] == "2026-08-06"
        and child["plannedFinish"] == "2026-08-09"
        and child["statusLabelSource"] == "Not started"
        and child["version"] == 2,
        "Shifted child WBS item drifted",
    )
    dependencies = body.get("dependencies")
    require(
        isinstance(dependencies, list)
        and len(dependencies) == 1
        and dependencies[0]["globalId"] == work_ids["dependency-root-child"]
        and dependencies[0]["version"] == 2,
        "WBS dependency drifted",
    )

    baselines = body.get("baselines")
    require(
        isinstance(baselines, list)
        and len(baselines) == 1
        and baselines[0]["globalId"] == baseline_id
        and baselines[0]["projectVersion"] == 3
        and baselines[0]["capturedBy"] == "Administrator",
        "Plan baseline projection drifted",
    )
    comparison = body.get("baselineComparison")
    require(isinstance(comparison, dict), "Baseline comparison is unavailable")
    require(
        comparison.get("baselineId") == baseline_id
        and comparison.get("baselineProjectVersion") == 3
        and comparison.get("currentProjectVersion") == 9,
        "Baseline comparison identity drifted",
    )
    comparison_items = comparison.get("items")
    require(
        isinstance(comparison_items, list) and len(comparison_items) == 2,
        "Baseline comparison items drifted",
    )
    variances = {
        item["wbsItemId"]: (
            item["startVarianceDays"],
            item["finishVarianceDays"],
        )
        for item in comparison_items
    }
    require(
        variances
        == {
            work_ids["wbs-root"]: (2, 3),
            work_ids["wbs-child"]: (1, 2),
        },
        "Baseline variance calculation drifted",
    )


def verify_domain_queries(
    administrator,
    base_url: str,
    project_id: str,
    *,
    item_ids: dict[str, str],
    owner: str,
    member: str,
    stage_id: str,
) -> None:
    first = list_work_items(
        administrator,
        base_url,
        project_id,
        limit=2,
    )
    require(first.status == 200, f"Domain WorkItem page returned HTTP {first.status}")
    require(
        first.body.get("projectId") == project_id
        and first.body.get("projectVersion") == 9,
        "Domain WorkItem page identity drifted",
    )
    first_ids = [item["globalId"] for item in first.body.get("items", [])]
    require(
        first_ids == [item_ids["risk"], item_ids["issue"]],
        "Domain WorkItem first page order drifted",
    )
    cursor = first.body.get("nextCursor")
    require(isinstance(cursor, str) and cursor, "Domain WorkItem cursor is unavailable")
    second = list_work_items(
        administrator,
        base_url,
        project_id,
        limit=2,
        cursor=cursor,
    )
    require(second.status == 200, "Domain WorkItem second page failed")
    require(
        [item["globalId"] for item in second.body.get("items", [])]
        == [item_ids["action"], item_ids["decision_request"]]
        and second.body.get("nextCursor") is None,
        "Domain WorkItem second page drifted",
    )
    replacement = "A" if cursor[-1] != "A" else "B"
    tampered = list_work_items(
        administrator,
        base_url,
        project_id,
        limit=2,
        cursor=f"{cursor[:-1]}{replacement}",
    )
    validate_problem(tampered, 422, "VALIDATION_FAILED")
    require(
        tampered.body.get("fieldErrors")
        == [{"path": "cursor", "message": "Enter a valid cursor."}],
        "A tampered Domain WorkItem cursor was not rejected safely",
    )

    cases = (
        ({"kind": "risk"}, [item_ids["risk"]]),
        ({"stageId": stage_id}, [item_ids["risk"]]),
        (
            {"ownerUserId": owner},
            [item_ids["risk"], item_ids["action"]],
        ),
        (
            {"ownerUserId": member},
            [item_ids["issue"], item_ids["decision_request"]],
        ),
        ({"overdue": True}, [item_ids["risk"]]),
        (
            {"overdue": False},
            [
                item_ids["issue"],
                item_ids["action"],
                item_ids["decision_request"],
            ],
        ),
    )
    for query, expected_ids in cases:
        result = list_work_items(
            administrator,
            base_url,
            project_id,
            limit=100,
            **query,
        )
        require(
            result.status == 200
            and [item["globalId"] for item in result.body.get("items", [])]
            == expected_ids,
            f"Domain WorkItem filter drifted: {query}",
        )


def require_baseline_response(
    body: dict[str, object],
    *,
    project_id: str,
    policy_ref: dict[str, object],
    label: str,
) -> tuple[str, str]:
    expected_keys = {
        "globalId",
        "projectId",
        "projectVersion",
        "workPolicyRef",
        "label",
        "snapshotHash",
        "capturedAt",
        "capturedBy",
        "version",
    }
    baseline_id = body.get("globalId")
    snapshot_hash = body.get("snapshotHash")
    require(
        set(body) == expected_keys
        and isinstance(baseline_id, str)
        and isinstance(snapshot_hash, str)
        and re.fullmatch(r"[a-f0-9]{64}", snapshot_hash) is not None
        and body.get("projectId") == project_id
        and body.get("projectVersion") == 3
        and body.get("workPolicyRef") == policy_ref
        and body.get("label") == label
        and isinstance(body.get("capturedAt"), str)
        and utc_iso(body["capturedAt"]) == body["capturedAt"]
        and body.get("capturedBy") == "Administrator"
        and body.get("version") == 1,
        "Project Plan Baseline response drifted",
    )
    return baseline_id, snapshot_hash


def verify_baseline_hash(
    administrator,
    base_url: str,
    baseline_id: str,
    response_hash: str,
    *,
    project_id: str,
    policy_ref: dict[str, object],
    expected_label: str,
    response_captured_at: str,
    scope: str = "main",
) -> None:
    result = get_resource(
        administrator,
        base_url,
        "NPI WBS Plan Baseline",
        baseline_id,
    )
    require(result.status == 200, "Persisted Plan Baseline is unavailable")
    data = result.body.get("data", {})
    snapshot = json_value(data.get("snapshot"))
    ids = plan_ids(scope)
    if scope == "main":
        expected_items = (
            (ids["wbs-root"], "2026-08-01", "2026-08-10", True),
            (ids["wbs-child"], "2026-08-05", "2026-08-07", False),
        )
    else:
        expected_items = (
            (ids["wbs-root"], "2026-10-01", "2026-10-10", True),
            (ids["wbs-child"], "2026-10-03", "2026-10-07", False),
        )
    expected_snapshot = {
        "items": [
            {
                "wbsItemId": item_id,
                "plannedStart": planned_start,
                "plannedFinish": planned_finish,
                "critical": critical,
            }
            for item_id, planned_start, planned_finish, critical in sorted(
                expected_items,
                key=lambda item: item[0],
            )
        ]
    }
    require(
        snapshot == expected_snapshot
        and canonical_hash(snapshot) == data.get("snapshot_hash")
        and data.get("snapshot_hash") == response_hash,
        "Domain and DocType Plan Baseline hashes differ",
    )
    require(
        data.get("global_id") == baseline_id
        and data.get("project_global_id") == project_id
        and data.get("plan_revision") == 1
        and data.get("project_version") == 3
        and data.get("label") == expected_label
        and data.get("work_policy_global_id") == policy_ref["globalId"]
        and data.get("work_policy_version") == policy_ref["version"]
        and data.get("work_policy_snapshot_hash")
        == policy_ref["snapshotHash"]
        and data.get("captured_by") == "Administrator"
        and data.get("optimistic_version") == 1,
        "Persisted Plan Baseline context or version drifted",
    )
    require(
        utc_iso(data.get("captured_at")) == response_captured_at,
        "Persisted Plan Baseline capture time drifted",
    )


def require_idor_equivalent(
    unauthorized: HttpResult,
    absent: HttpResult,
) -> None:
    require_problem_equivalent(
        unauthorized,
        absent,
        status=404,
        code="PROJECT_UNAVAILABLE",
        problem_type="urn:npi:problem:project_unavailable",
        title="The requested project is unavailable.",
        label="IDOR-safe",
    )


def require_permission_equivalent(
    unauthorized: HttpResult,
    absent: HttpResult,
) -> None:
    require_problem_equivalent(
        unauthorized,
        absent,
        status=403,
        code="PERMISSION_DENIED",
        problem_type="urn:npi:problem:permission_denied",
        title="You do not have permission to perform this action.",
        label="Pre-authorization",
    )


def require_problem_equivalent(
    unauthorized: HttpResult,
    absent: HttpResult,
    *,
    status: int,
    code: str,
    problem_type: str,
    title: str,
    label: str,
) -> None:
    validate_problem(unauthorized, status, code)
    validate_problem(absent, status, code)
    expected_keys = {
        "type",
        "title",
        "status",
        "code",
        "traceId",
        "retryable",
    }
    require(
        set(unauthorized.body) == expected_keys
        and set(absent.body) == expected_keys,
        f"{label} problem body shape drifted",
    )
    unauthorized_body = {**unauthorized.body, "traceId": "<trace>"}
    absent_body = {**absent.body, "traceId": "<trace>"}
    expected_body = {
        "type": problem_type,
        "title": title,
        "status": status,
        "code": code,
        "traceId": "<trace>",
        "retryable": False,
    }
    require(
        unauthorized_body == absent_body == expected_body,
        f"{label} unauthorized and absent problem bodies differ",
    )
    for result in (unauthorized, absent):
        require(
            isinstance(result.request_id, str)
            and result.headers.get("X-Request-ID") == result.request_id
            and isinstance(result.trace_id, str)
            and result.body["traceId"] == result.trace_id
            and result.headers.get("X-Trace-ID") == result.trace_id,
            f"{label} problem lost request or trace identity",
        )


def verify_security_boundaries(
    administrator,
    owner_session,
    member_session,
    base_url: str,
    *,
    administrator_csrf: str,
    owner_csrf: str,
    main_project_id: str,
    guard_project_id: str,
    main_policy_ref: dict[str, object],
    guard_policy_ref: dict[str, object],
    owner: str,
    member: str,
) -> None:
    team = team_payload(
        "guard",
        guard_project_id,
        guard_policy_ref,
        owner,
        member,
        expected_version=5,
    )
    command_path = (
        f"/api/npi/v1/projects/{guard_project_id}:configure-team"
    )

    no_csrf = work_command(
        administrator,
        base_url,
        command_path,
        team,
        idempotency_key=CSRF_REJECTED_KEY,
        csrf_token=None,
    )
    validate_problem(no_csrf, 403, "CSRF_TOKEN_INVALID")
    verify_no_work_idempotency(
        administrator,
        base_url,
        "Administrator",
        CSRF_REJECTED_KEY,
    )

    tenant_injection = deepcopy(team)
    tenant_injection["tenantId"] = "other-runtime-tenant"
    tenant_problem = work_command(
        administrator,
        base_url,
        command_path,
        tenant_injection,
        idempotency_key=TENANT_INJECTION_KEY,
        csrf_token=administrator_csrf,
    )
    validate_problem(tenant_problem, 422, "VALIDATION_FAILED")
    require_field_error(tenant_problem, "tenantId")
    verify_no_work_idempotency(
        administrator,
        base_url,
        "Administrator",
        TENANT_INJECTION_KEY,
    )

    owner_problem = work_command(
        owner_session,
        base_url,
        command_path,
        team,
        idempotency_key=OWNER_REJECTED_KEY,
        csrf_token=owner_csrf,
    )
    validate_problem(owner_problem, 403, "PERMISSION_DENIED")
    verify_no_work_idempotency(
        administrator,
        base_url,
        owner,
        OWNER_REJECTED_KEY,
    )

    version_payload = deepcopy(team)
    version_payload["expectedProjectVersion"] = 999
    version_problem = work_command(
        administrator,
        base_url,
        command_path,
        version_payload,
        idempotency_key=VERSION_CONFLICT_KEY,
        csrf_token=administrator_csrf,
    )
    validate_problem(version_problem, 409, "VERSION_CONFLICT")
    verify_no_work_idempotency(
        administrator,
        base_url,
        "Administrator",
        VERSION_CONFLICT_KEY,
    )

    changed_team = team_payload(
        "guard",
        guard_project_id,
        guard_policy_ref,
        owner,
        member,
    )
    changed_team["members"][0]["effectiveTo"] = "2098-12-31"  # type: ignore[index]
    idempotency_problem = work_command(
        administrator,
        base_url,
        command_path,
        changed_team,
        idempotency_key=GUARD_TEAM_KEY,
        csrf_token=administrator_csrf,
    )
    validate_problem(
        idempotency_problem,
        409,
        "IDEMPOTENCY_KEY_CONFLICT",
    )

    owner_context = get_work_context(owner_session, base_url, main_project_id)
    require(owner_context.status == 200, "Project owner cannot read work context")
    require_context_shape(
        owner_context.body,
        project_id=main_project_id,
        version=9,
        administrator=False,
    )
    owner_items = list_work_items(
        owner_session,
        base_url,
        main_project_id,
        limit=100,
    )
    require(
        owner_items.status == 200
        and len(owner_items.body.get("items", [])) == 4,
        "Project owner cannot read Domain WorkItems",
    )

    absent_id = fixture_id("security", "absent-project")
    unauthorized_context = get_work_context(
        member_session,
        base_url,
        main_project_id,
    )
    absent_context = get_work_context(member_session, base_url, absent_id)
    unauthorized_items = list_work_items(
        member_session,
        base_url,
        main_project_id,
        limit=100,
    )
    absent_items = list_work_items(
        member_session,
        base_url,
        absent_id,
        limit=100,
    )
    main_team = team_payload(
        "main",
        main_project_id,
        main_policy_ref,
        owner,
        member,
        expected_version=9,
    )
    unauthorized_write = work_command(
        member_session,
        base_url,
        f"/api/npi/v1/projects/{main_project_id}:configure-team",
        main_team,
        idempotency_key=IDOR_UNAUTHORIZED_KEY,
        csrf_token=bootstrap_csrf(member_session, base_url, member),
    )
    absent_write = work_command(
        member_session,
        base_url,
        f"/api/npi/v1/projects/{absent_id}:configure-team",
        main_team,
        idempotency_key=IDOR_ABSENT_KEY,
        csrf_token=bootstrap_csrf(member_session, base_url, member),
    )
    for unauthorized, absent in (
        (unauthorized_context, absent_context),
        (unauthorized_items, absent_items),
    ):
        require_idor_equivalent(unauthorized, absent)
    require_permission_equivalent(unauthorized_write, absent_write)
    for actor, key in (
        (member, IDOR_UNAUTHORIZED_KEY),
        (member, IDOR_ABSENT_KEY),
    ):
        verify_no_work_idempotency(administrator, base_url, actor, key)

    guest = get_work_context(
        urllib.request.build_opener(),
        base_url,
        main_project_id,
    )
    validate_problem(guest, 401, "AUTHENTICATION_REQUIRED")
    invalid = get_work_context(administrator, base_url, "not-a-uuid")
    validate_problem(invalid, 422, "VALIDATION_FAILED")


def verify_true_concurrency(
    administrator,
    base_url: str,
    *,
    administrator_password: str,
    project_id: str,
    policy_ref: dict[str, object],
    evidence: dict[str, HttpResult],
    payload_hashes: dict[str, str],
) -> str:
    sessions = [
        login(base_url, "Administrator", administrator_password)
        for _index in range(2)
    ]
    csrf_tokens = [
        bootstrap_csrf(session, base_url, "Administrator")
        for session in sessions
    ]
    barrier = Barrier(2)
    variants = ("a", "b")

    def submit(index: int) -> HttpResult:
        barrier.wait(timeout=15)
        return work_command(
            sessions[index],
            base_url,
            f"/api/npi/v1/projects/{project_id}:apply-work-plan",
            concurrency_plan_payload(policy_ref, variant=variants[index]),
            idempotency_key=CONCURRENCY_PLAN_KEYS[index],
            csrf_token=csrf_tokens[index],
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(submit, index) for index in range(2)]
        results = [future.result(timeout=30) for future in futures]

    require(
        sorted(result.status for result in results) == [200, 409],
        "Concurrent same-version work-plan commands did not yield one success and one conflict",
    )
    winner_index = next(
        index for index, result in enumerate(results) if result.status == 200
    )
    loser_index = 1 - winner_index
    winner = results[winner_index]
    loser = results[loser_index]
    winner_key = CONCURRENCY_PLAN_KEYS[winner_index]
    loser_key = CONCURRENCY_PLAN_KEYS[loser_index]
    winner_variant = variants[winner_index]
    winner_payload = concurrency_plan_payload(
        policy_ref,
        variant=winner_variant,
    )
    winner_body = require_fresh_command_success(
        winner,
        200,
        "Concurrent Project work plan winner",
    )
    require_context_shape(
        winner_body,
        project_id=project_id,
        version=3,
        administrator=True,
    )
    validate_problem(
        loser,
        409,
        "VERSION_CONFLICT",
        expected_trace_id=loser.trace_id,
    )
    verify_no_work_idempotency(
        administrator,
        base_url,
        "Administrator",
        loser_key,
    )

    replay = work_command(
        sessions[winner_index],
        base_url,
        f"/api/npi/v1/projects/{project_id}:apply-work-plan",
        winner_payload,
        idempotency_key=winner_key,
        csrf_token=csrf_tokens[winner_index],
    )
    require_sealed_command_replay(
        replay,
        200,
        "Concurrent Project work plan winner",
        winner_body,
    )
    evidence[winner_key] = winner
    payload_hashes[winner_key] = canonical_hash(
        normalized_command_payload(
            project_id,
            "project.work_plan.apply",
            winner_payload,
        )
    )

    expected_items = {
        str(item["globalId"]): {
            "parentId": item.get("parentId"),
            "critical": item["critical"],
        }
        for item in winner_payload["items"]  # type: ignore[index]
    }
    response_items = {
        str(item["globalId"]): {
            "parentId": item.get("parentId"),
            "critical": item["critical"],
            "version": item["version"],
        }
        for item in winner_body.get("wbsItems", [])
    }
    require(
        response_items
        == {
            item_id: {**values, "version": 1}
            for item_id, values in expected_items.items()
        },
        "Concurrent winner WBS response was merged or lost",
    )
    expected_dependency = winner_payload["dependencies"][0]  # type: ignore[index]
    require(
        winner_body.get("dependencies")
        == [
            {
                "globalId": expected_dependency["globalId"],
                "projectId": project_id,
                "predecessorItemId": expected_dependency[
                    "predecessorItemId"
                ],
                "successorItemId": expected_dependency["successorItemId"],
                "version": 1,
            }
        ],
        "Concurrent winner dependency response was merged or lost",
    )

    project_rows = list_resources(
        administrator,
        base_url,
        "NPI Engineering Project",
        filters=[["global_id", "=", project_id]],
        fields=["optimistic_version", "work_plan_revision"],
    )
    require(
        project_rows
        == [{"optimistic_version": 3, "work_plan_revision": 1}],
        "Concurrent Project version or plan revision was lost",
    )
    persisted_items = list_resources(
        administrator,
        base_url,
        "NPI WBS Item",
        filters=[["project_global_id", "=", project_id]],
        fields=[
            "critical_task",
            "global_id",
            "optimistic_version",
            "parent_global_id",
            "plan_revision",
        ],
    )
    require(
        {
            str(row["global_id"]): {
                "parentId": row["parent_global_id"] or None,
                "critical": bool(row["critical_task"]),
                "planRevision": row["plan_revision"],
                "version": row["optimistic_version"],
            }
            for row in persisted_items
        }
        == {
            item_id: {
                **values,
                "planRevision": 1,
                "version": 1,
            }
            for item_id, values in expected_items.items()
        },
        "Concurrent Project persisted a combined parent cycle or lost WBS state",
    )
    persisted_dependencies = list_resources(
        administrator,
        base_url,
        "NPI WBS Dependency",
        filters=[["project_global_id", "=", project_id]],
        fields=[
            "active",
            "global_id",
            "optimistic_version",
            "plan_revision",
            "predecessor_global_id",
            "successor_global_id",
        ],
    )
    require(
        persisted_dependencies
        == [
            {
                "active": 1,
                "global_id": expected_dependency["globalId"],
                "optimistic_version": 1,
                "plan_revision": 1,
                "predecessor_global_id": expected_dependency[
                    "predecessorItemId"
                ],
                "successor_global_id": expected_dependency[
                    "successorItemId"
                ],
            }
        ],
        "Concurrent Project persisted a combined dependency cycle or lost dependency state",
    )
    return winner_key


def verify_idempotency_records(
    administrator,
    base_url: str,
    *,
    command_specs: dict[str, tuple[str, str]],
    evidence: dict[str, HttpResult],
    payload_hashes: dict[str, str],
) -> dict[str, dict[str, object]]:
    require(
        set(command_specs) == set(evidence) == set(payload_hashes),
        "Successful command evidence is incomplete",
    )
    rows_by_key: dict[str, dict[str, object]] = {}
    for project_id in sorted({value[0] for value in command_specs.values()}):
        project_keys = {
            key
            for key, (expected_project_id, _operation) in command_specs.items()
            if expected_project_id == project_id
        }
        rows = list_resources(
            administrator,
            base_url,
            "NPI Project Work Idempotency",
            filters=[["project_global_id", "=", project_id]],
            fields=[
                "name",
                "actor",
                "actor_key_hash",
                "operation",
                "payload_hash",
                "project_global_id",
                "response_json",
                "response_sealed",
                "tenant_id",
            ],
        )
        require(
            len(rows) == len(project_keys),
            f"Project {project_id} idempotency record count drifted",
        )
        by_hash = {str(row["actor_key_hash"]): row for row in rows}
        require(
            len(by_hash) == len(rows),
            f"Project {project_id} idempotency identities are not unique",
        )
        for key in project_keys:
            row = by_hash.get(actor_key_hash("Administrator", key))
            require(
                row is not None,
                f"Successful command idempotency record is missing: {key}",
            )
            expected_project_id, operation = command_specs[key]
            require(
                row["actor"] == "Administrator"
                and row["tenant_id"] == TENANT_ID
                and row["project_global_id"] == expected_project_id
                and row["operation"] == operation
                and row["payload_hash"] == payload_hashes[key]
                and row["response_sealed"] == 1
                and json_value(row["response_json"]) == evidence[key].body,
                f"Successful command idempotency evidence drifted: {key}",
            )
            require(
                evidence[key].headers.get("Idempotency-Replayed") == "false",
                f"Successful command was not first-run evidence: {key}",
            )
            rows_by_key[key] = row
    return rows_by_key


def audit_rows(
    administrator,
    base_url: str,
    *,
    global_id: str,
    operation: str,
) -> list[dict[str, object]]:
    return list_resources(
        administrator,
        base_url,
        "NPI Audit Event",
        filters=[
            ["global_id", "=", global_id],
            ["operation", "=", operation],
        ],
        fields=[
            "name",
            "actor",
            "global_id",
            "input_summary",
            "object_version",
            "operation",
            "result",
            "trace_id",
        ],
    )


def verify_audit_events(
    administrator,
    base_url: str,
    *,
    expected_events: list[tuple[str, str, int, str, str]],
    evidence: dict[str, HttpResult],
) -> str:
    grouped: dict[
        tuple[str, str],
        list[tuple[int, str, str]],
    ] = {}
    for global_id, operation, object_version, result, command_key in expected_events:
        require(command_key in evidence, f"Audit command evidence is missing: {command_key}")
        grouped.setdefault((global_id, operation), []).append(
            (object_version, result, command_key)
        )
    retained_audit_name = ""
    for (global_id, operation), expected in grouped.items():
        rows = audit_rows(
            administrator,
            base_url,
            global_id=global_id,
            operation=operation,
        )
        require(
            len(rows) == len(expected),
            f"Audit evidence drifted for {operation}",
        )
        unmatched = list(rows)
        for object_version, result, command_key in expected:
            command = evidence[command_key]
            matches = [
                row
                for row in unmatched
                if row["actor"] == "Administrator"
                and int(row["object_version"]) == object_version
                and row["result"] == result
                and row["trace_id"] == command.trace_id
                and isinstance(json_value(row["input_summary"]), dict)
                and json_value(row["input_summary"]).get("requestId")
                == command.request_id
            ]
            require(
                len(matches) == 1,
                (
                    "Audit version, result, trace, or request association "
                    f"drifted for {command_key}"
                ),
            )
            retained_audit_name = retained_audit_name or str(matches[0]["name"])
            unmatched.remove(matches[0])
        require(not unmatched, f"Unexpected audit evidence exists for {operation}")
    return retained_audit_name


def verify_generic_crud_and_history_guards(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    guard_project_id: str,
    owner: str,
    guard_baseline_id: str,
    guard_item_id: str,
    guard_idempotency_name: str,
    guard_audit_name: str,
) -> int:
    generic_member_id = fixture_id("guard", "generic-member-must-not-exist")
    create = create_resource(
        administrator,
        base_url,
        "NPI Project Member",
        {
            "global_id": generic_member_id,
            "tenant_id": TENANT_ID,
            "project_global_id": guard_project_id,
            "user_id": owner,
            "effective_from": "2026-01-01",
            "effective_to": "2099-12-31",
            "optimistic_version": 1,
        },
        csrf_token,
    )
    require(
        create.status in {403, 417},
        f"Generic Project member create returned HTTP {create.status}",
    )
    require(
        get_resource(
            administrator,
            base_url,
            "NPI Project Member",
            generic_member_id,
        ).status
        == 404,
        "Rejected generic create persisted a Project member",
    )

    retained_member_id = team_ids("guard")["member-owner"]
    before = get_resource(
        administrator,
        base_url,
        "NPI Project Member",
        retained_member_id,
    )
    require(before.status == 200, "Project member update target is unavailable")
    update = update_resource(
        administrator,
        base_url,
        "NPI Project Member",
        retained_member_id,
        {"effective_to": "2098-12-31"},
        csrf_token,
    )
    require(
        update.status in {403, 417},
        f"Generic Project member update returned HTTP {update.status}",
    )
    after = get_resource(
        administrator,
        base_url,
        "NPI Project Member",
        retained_member_id,
    )
    require(
        after.status == 200
        and after.body.get("data", {}).get("effective_to")
        == before.body.get("data", {}).get("effective_to"),
        "Rejected generic update changed a Project member",
    )

    policy_update = update_resource(
        administrator,
        base_url,
        "NPI Project Work Policy Version",
        GUARD_POLICY_VERSION_KEY,
        {"title": "MUST NOT CHANGE"},
        csrf_token,
    )
    require(
        policy_update.status in {403, 417},
        f"Published Work Policy update returned HTTP {policy_update.status}",
    )
    policy_delete = delete_resource(
        administrator,
        base_url,
        "NPI Project Work Policy Version",
        GUARD_POLICY_VERSION_KEY,
        csrf_token,
    )
    require(
        policy_delete.status in {403, 417},
        f"Published Work Policy deletion returned HTTP {policy_delete.status}",
    )
    retained_policy = get_resource(
        administrator,
        base_url,
        "NPI Project Work Policy Version",
        GUARD_POLICY_VERSION_KEY,
    )
    require(
        retained_policy.status == 200
        and retained_policy.body.get("data", {}).get("title")
        == GUARD_POLICY_TITLE,
        "Published Work Policy was changed or deleted",
    )

    team = team_ids("guard")
    plan = plan_ids("guard")
    targets = [
        ("NPI Project Member", team["member-owner"]),
        ("NPI Project Role Assignment", team["role-owner"]),
        ("NPI Project Substitution", team["substitution"]),
        ("NPI Project RACI Assignment", team["raci-project"]),
        ("NPI WBS Item", plan["wbs-root"]),
        ("NPI WBS Dependency", plan["dependency-root-child"]),
        ("NPI WBS Plan Baseline", guard_baseline_id),
        ("NPI Domain Work Item", guard_item_id),
        (
            "NPI Project Work Idempotency",
            guard_idempotency_name,
        ),
        ("NPI Audit Event", guard_audit_name),
    ]
    for doctype, name in targets:
        rejected = delete_resource(
            administrator,
            base_url,
            doctype,
            name,
            csrf_token,
        )
        require(
            rejected.status in {403, 417},
            f"{doctype} history deletion returned HTTP {rejected.status}",
        )
        require(
            get_resource(administrator, base_url, doctype, name).status == 200,
            f"{doctype} history was physically deleted",
        )
    return len(targets) + 1


def verify_scoped_persistence(
    administrator,
    base_url: str,
    *,
    main_project_id: str,
    cycle_project_id: str,
    guard_project_id: str,
    concurrency_project_id: str,
) -> None:
    doctypes = (
        "NPI Project Member",
        "NPI Project Role Assignment",
        "NPI Project Substitution",
        "NPI Project RACI Assignment",
        "NPI WBS Item",
        "NPI WBS Dependency",
        "NPI WBS Plan Baseline",
        "NPI Domain Work Item",
        "NPI Project Work Idempotency",
    )
    expected = {
        main_project_id: (2, 1, 1, 1, 2, 1, 1, 4, 8),
        cycle_project_id: (1, 1, 0, 1, 0, 0, 0, 0, 1),
        guard_project_id: (2, 1, 1, 1, 2, 1, 1, 1, 4),
        concurrency_project_id: (1, 1, 0, 1, 2, 1, 0, 0, 2),
    }
    for project_id, counts in expected.items():
        for doctype, count in zip(doctypes, counts, strict=True):
            rows = list_resources(
                administrator,
                base_url,
                doctype,
                filters=[["project_global_id", "=", project_id]],
                fields=["project_global_id", "tenant_id"],
            )
            require(
                len(rows) == count
                and all(
                    row["project_global_id"] == project_id
                    and row["tenant_id"] == TENANT_ID
                    for row in rows
                ),
                f"{doctype} Project or tenant scope drifted for {project_id}",
            )


def verify_domain_work_item_persistence(
    administrator,
    base_url: str,
    *,
    project_id: str,
    item_ids: dict[str, str],
    policy_ref: dict[str, object],
    owner: str,
    member: str,
    stage_id: str,
) -> None:
    domain_rows = list_resources(
        administrator,
        base_url,
        "NPI Domain Work Item",
        filters=[["project_global_id", "=", project_id]],
        fields=[
            "blocking",
            "detail",
            "due_at",
            "evidence_references",
            "global_id",
            "kind",
            "optimistic_version",
            "owner_user_id",
            "project_global_id",
            "relations",
            "severity",
            "source_system",
            "stage_global_id",
            "state_key",
            "state_label_source",
            "state_terminal",
            "tenant_id",
            "title",
            "wbs_item_global_id",
            "work_policy_global_id",
            "work_policy_snapshot_hash",
            "work_policy_version",
        ],
    )
    require(len(domain_rows) == 4, "Persisted Domain WorkItem count drifted")
    by_kind = {str(row["kind"]): row for row in domain_rows}
    require(set(by_kind) == set(WORK_STATE_DEFINITIONS), "Domain kinds drifted")
    for kind, (state_key, label_source) in WORK_STATE_DEFINITIONS.items():
        row = by_kind[kind]
        payload = domain_item_payload(
            kind=kind,
            expected_version=0,
            policy_ref=policy_ref,
            owner=owner if kind in {"risk", "action"} else member,
            stage_id=stage_id if kind == "risk" else None,
            wbs_item_id=plan_ids("main")["wbs-child"],
            related_ids=[item_ids["risk"]] if kind == "action" else [],
        )
        expected_context = payload["context"]
        require(isinstance(expected_context, dict), "WorkItem context fixture drifted")
        require(
            row["global_id"] == item_ids[kind]
            and row["tenant_id"] == TENANT_ID
            and row["project_global_id"] == project_id
            and (row["stage_global_id"] or None)
            == expected_context.get("stageId")
            and row["wbs_item_global_id"] == expected_context["wbsItemId"]
            and row["title"] == payload["title"]
            and row["detail"] == payload["detail"]
            and row["owner_user_id"] == payload["ownerUserId"]
            and utc_iso(row["due_at"]) == payload["dueAt"]
            and row["severity"] == payload["severity"]
            and bool(row["blocking"]) is payload["blocking"]
            and row["state_key"] == state_key
            and row["state_label_source"] == label_source
            and row["state_terminal"] == 0
            and row["work_policy_global_id"] == policy_ref["globalId"]
            and row["work_policy_version"] == policy_ref["version"]
            and row["work_policy_snapshot_hash"] == policy_ref["snapshotHash"]
            and json_value(row["relations"]) == payload["relatedWorkItemIds"]
            and json_value(row["evidence_references"]) == []
            and row["source_system"] == "NPI_ONE"
            and row["optimistic_version"] == 1,
            f"Persisted Domain WorkItem {kind} drifted",
        )
    require(
        {
            row["kind"]: (
                row["state_key"],
                row["state_label_source"],
                json_value(row["evidence_references"]),
            )
            for row in domain_rows
        }
        == {
            kind: (state_key, label_source, [])
            for kind, (state_key, label_source) in WORK_STATE_DEFINITIONS.items()
        },
        "Persisted kind-specific state or evidence boundary drifted",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument(
        "--replay-only",
        action="store_true",
        help=(
            "verify a completed fixture namespace from a separate process "
            "without setting up fixtures"
        ),
    )
    arguments = parser.parse_args()
    require(
        not arguments.replay_only
        or CALLER_SUPPLIED_FIXTURE_RUN_ID is not None,
        f"--replay-only requires {FIXTURE_RUN_ID_ENV}",
    )
    administrator_user = "Administrator"
    administrator_password = secret_from_environment(
        "NPI_RUNTIME_ADMINISTRATOR_PASSWORD"
    )
    owner_user = OWNER_USER
    member_user = MEMBER_USER
    base_url = validate_local_fixture_inputs(
        arguments.base_url,
        administrator_user,
        owner_user,
    )
    validate_local_fixture_inputs(
        base_url,
        administrator_user,
        member_user,
    )
    require(
        owner_user != member_user,
        "Project work owner and member fixtures must differ",
    )

    administrator = login(
        base_url,
        administrator_user,
        administrator_password,
    )
    administrator_csrf = bootstrap_csrf(
        administrator,
        base_url,
        administrator_user,
    )
    if arguments.replay_only:
        replay_evidence = verify_cross_process_replay(
            administrator,
            base_url,
            administrator_csrf,
            owner=owner_user,
            member=member_user,
        )
        print(
            json.dumps(
                {
                    "fixtureRevision": FIXTURE_REVISION,
                    "fixtureRunId": FIXTURE_RUN_ID,
                    "mode": "replay-only",
                    **replay_evidence,
                    "tenantId": TENANT_ID,
                },
                sort_keys=True,
            )
        )
        print(
            "local Frappe Project work cross-process replay "
            "verification passed"
        )
        return

    fixture_password = secret_from_environment(
        "NPI_RUNTIME_FIXTURE_PASSWORD"
    )
    fixture_states = verify_fresh_fixture_namespace(
        administrator,
        base_url,
        owner=owner_user,
        member=member_user,
    )
    ensure_synthetic_template(administrator, base_url, administrator_csrf)
    for user in (owner_user, member_user):
        ensure_runtime_user(
            administrator,
            base_url,
            user,
            fixture_password,
            administrator_csrf,
        )
    owner_session = login(
        base_url,
        owner_user,
        fixture_password,
    )
    member_session = login(
        base_url,
        member_user,
        fixture_password,
    )
    owner_csrf = bootstrap_csrf(
        owner_session,
        base_url,
        owner_user,
    )
    bootstrap_csrf(
        member_session,
        base_url,
        member_user,
    )

    policy_ref = ensure_work_policy(
        administrator,
        base_url,
        administrator_csrf,
    )
    guard_policy_ref = ensure_work_policy(
        administrator,
        base_url,
        administrator_csrf,
        guard=True,
    )
    main_project_id = ensure_project(
        administrator,
        base_url,
        administrator_csrf,
        owner=owner_user,
        business_code=business_code("main"),
        title=project_title("main"),
        idempotency_key=MAIN_PROJECT_CREATE_KEY,
    )
    cycle_project_id = ensure_project(
        administrator,
        base_url,
        administrator_csrf,
        owner=owner_user,
        business_code=business_code("cycle"),
        title=project_title("cycle"),
        idempotency_key=CYCLE_PROJECT_CREATE_KEY,
    )
    guard_project_id = ensure_project(
        administrator,
        base_url,
        administrator_csrf,
        owner=owner_user,
        business_code=business_code("guard"),
        title=project_title("guard"),
        idempotency_key=GUARD_PROJECT_CREATE_KEY,
    )
    concurrency_project_id = ensure_project(
        administrator,
        base_url,
        administrator_csrf,
        owner=owner_user,
        business_code=business_code("concurrency"),
        title=project_title("concurrency"),
        idempotency_key=CONCURRENCY_PROJECT_CREATE_KEY,
    )
    evidence: dict[str, HttpResult] = {}
    payload_hashes: dict[str, str] = {}

    cycle_team_payload = team_payload(
        "cycle",
        cycle_project_id,
        policy_ref,
        owner_user,
        member_user,
    )
    cycle_body = execute_success_with_replay(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{cycle_project_id}:configure-team",
        cycle_team_payload,
        operation="project.team.configure",
        idempotency_key=CYCLE_TEAM_KEY,
        csrf_token=administrator_csrf,
        expected_status=200,
        label="Cycle Project team",
        project_id=cycle_project_id,
        evidence=evidence,
        payload_hashes=payload_hashes,
    )
    require_context_shape(
        cycle_body,
        project_id=cycle_project_id,
        version=2,
        administrator=True,
    )
    verify_cycle_rejections(
        administrator,
        base_url,
        administrator_csrf,
        cycle_project_id,
        policy_ref,
    )

    main_team_payload = team_payload(
        "main",
        main_project_id,
        policy_ref,
        owner_user,
        member_user,
    )
    main_team_body = execute_success_with_replay(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{main_project_id}:configure-team",
        main_team_payload,
        operation="project.team.configure",
        idempotency_key=MAIN_TEAM_KEY,
        csrf_token=administrator_csrf,
        expected_status=200,
        label="Main Project team",
        project_id=main_project_id,
        evidence=evidence,
        payload_hashes=payload_hashes,
    )
    require_context_shape(
        main_team_body,
        project_id=main_project_id,
        version=2,
        administrator=True,
    )
    initial_plan_payload = main_plan_payload(policy_ref, shifted=False)
    initial_plan_body = execute_success_with_replay(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{main_project_id}:apply-work-plan",
        initial_plan_payload,
        operation="project.work_plan.apply",
        idempotency_key=MAIN_PLAN_KEY,
        csrf_token=administrator_csrf,
        expected_status=200,
        label="Initial Project work plan",
        project_id=main_project_id,
        evidence=evidence,
        payload_hashes=payload_hashes,
    )
    require_context_shape(
        initial_plan_body,
        project_id=main_project_id,
        version=3,
        administrator=True,
    )
    require(
        len(initial_plan_body.get("wbsItems", [])) == 2
        and all(
            item.get("statusLabelSource") == "Not started"
            for item in initial_plan_body.get("wbsItems", [])
        ),
        "Initial WBS labels drifted",
    )

    baseline_payload = {
        "expectedProjectVersion": 3,
        "workPolicyRef": policy_ref,
        "label": "Synthetic P4-02 plan baseline",
    }
    baseline_body = execute_success_with_replay(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{main_project_id}:capture-plan-baseline",
        baseline_payload,
        operation="project.plan_baseline.capture",
        idempotency_key=MAIN_BASELINE_KEY,
        csrf_token=administrator_csrf,
        expected_status=201,
        label="Project Plan Baseline",
        project_id=main_project_id,
        evidence=evidence,
        payload_hashes=payload_hashes,
    )
    baseline_id, baseline_hash = require_baseline_response(
        baseline_body,
        project_id=main_project_id,
        policy_ref=policy_ref,
        label=str(baseline_payload["label"]),
    )
    verify_baseline_hash(
        administrator,
        base_url,
        baseline_id,
        baseline_hash,
        project_id=main_project_id,
        policy_ref=policy_ref,
        expected_label=str(baseline_payload["label"]),
        response_captured_at=str(baseline_body["capturedAt"]),
    )

    shifted_plan_payload = main_plan_payload(policy_ref, shifted=True)
    shifted_body = execute_success_with_replay(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{main_project_id}:apply-work-plan",
        shifted_plan_payload,
        operation="project.work_plan.apply",
        idempotency_key=MAIN_SHIFTED_PLAN_KEY,
        csrf_token=administrator_csrf,
        expected_status=200,
        label="Shifted Project work plan",
        project_id=main_project_id,
        evidence=evidence,
        payload_hashes=payload_hashes,
    )
    require_context_shape(
        shifted_body,
        project_id=main_project_id,
        version=5,
        administrator=True,
    )

    gates = list_resources(
        administrator,
        base_url,
        "NPI Gate Shell",
        filters=[["project_global_id", "=", main_project_id]],
        fields=["gate_key", "global_id"],
    )
    stage_id = next(
        (
            str(row["global_id"])
            for row in gates
            if row.get("gate_key") == "G0"
        ),
        "",
    )
    require(bool(stage_id), "Synthetic Project stage is unavailable")

    item_ids: dict[str, str] = {}
    for offset, kind in enumerate(
        ("risk", "issue", "action", "decision_request"),
        start=5,
    ):
        item_owner = (
            owner_user
            if kind in {"risk", "action"}
            else member_user
        )
        related_ids = [item_ids["risk"]] if kind == "action" else []
        item_payload = domain_item_payload(
            kind=kind,
            expected_version=offset,
            policy_ref=policy_ref,
            owner=item_owner,
            stage_id=stage_id if kind == "risk" else None,
            wbs_item_id=plan_ids("main")["wbs-child"],
            related_ids=related_ids,
        )
        item_body = execute_success_with_replay(
            administrator,
            base_url,
            f"/api/npi/v1/projects/{main_project_id}/domain-work-items",
            item_payload,
            operation="project.domain_work_item.create",
            idempotency_key=MAIN_WORK_ITEM_KEYS[kind],
            csrf_token=administrator_csrf,
            expected_status=201,
            label=f"Domain WorkItem {kind}",
            project_id=main_project_id,
            evidence=evidence,
            payload_hashes=payload_hashes,
        )
        state_key, label_source = WORK_STATE_DEFINITIONS[kind]
        item_id = item_body.get("globalId")
        require(
            isinstance(item_id, str)
            and item_body.get("projectId") == main_project_id
            and item_body.get("kind") == kind
            and item_body.get("stateKey") == state_key
            and item_body.get("stateLabelSource") == label_source
            and item_body.get("ownerUserId") == item_owner
            and item_body.get("workPolicyRef") == policy_ref
            and item_body.get("overdue") is (kind == "risk")
            and "evidenceReferences" not in item_body,
            f"Domain WorkItem {kind} projection drifted",
        )
        require(
            item_body.get("relatedWorkItemIds") == related_ids,
            f"Domain WorkItem {kind} relations drifted",
        )
        item_ids[kind] = item_id

    guard_team_payload = team_payload(
        "guard",
        guard_project_id,
        guard_policy_ref,
        owner_user,
        member_user,
    )
    guard_team_body = execute_success_with_replay(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{guard_project_id}:configure-team",
        guard_team_payload,
        operation="project.team.configure",
        idempotency_key=GUARD_TEAM_KEY,
        csrf_token=administrator_csrf,
        expected_status=200,
        label="Guard Project team",
        project_id=guard_project_id,
        evidence=evidence,
        payload_hashes=payload_hashes,
    )
    require_context_shape(
        guard_team_body,
        project_id=guard_project_id,
        version=2,
        administrator=True,
    )
    guard_plan = guard_plan_payload(guard_policy_ref)
    guard_plan_body = execute_success_with_replay(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{guard_project_id}:apply-work-plan",
        guard_plan,
        operation="project.work_plan.apply",
        idempotency_key=GUARD_PLAN_KEY,
        csrf_token=administrator_csrf,
        expected_status=200,
        label="Guard Project work plan",
        project_id=guard_project_id,
        evidence=evidence,
        payload_hashes=payload_hashes,
    )
    require_context_shape(
        guard_plan_body,
        project_id=guard_project_id,
        version=3,
        administrator=True,
    )
    guard_baseline_payload = {
        "expectedProjectVersion": 3,
        "workPolicyRef": guard_policy_ref,
        "label": "Synthetic P4-02 guard plan baseline",
    }
    guard_baseline_body = execute_success_with_replay(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{guard_project_id}:capture-plan-baseline",
        guard_baseline_payload,
        operation="project.plan_baseline.capture",
        idempotency_key=GUARD_BASELINE_KEY,
        csrf_token=administrator_csrf,
        expected_status=201,
        label="Guard Project Plan Baseline",
        project_id=guard_project_id,
        evidence=evidence,
        payload_hashes=payload_hashes,
    )
    guard_baseline_id, guard_baseline_hash = require_baseline_response(
        guard_baseline_body,
        project_id=guard_project_id,
        policy_ref=guard_policy_ref,
        label=str(guard_baseline_payload["label"]),
    )
    verify_baseline_hash(
        administrator,
        base_url,
        guard_baseline_id,
        guard_baseline_hash,
        project_id=guard_project_id,
        policy_ref=guard_policy_ref,
        expected_label=str(guard_baseline_payload["label"]),
        response_captured_at=str(guard_baseline_body["capturedAt"]),
        scope="guard",
    )
    guard_item_payload = domain_item_payload(
        kind="risk",
        expected_version=4,
        policy_ref=guard_policy_ref,
        owner=owner_user,
        stage_id=None,
        wbs_item_id=plan_ids("guard")["wbs-child"],
        related_ids=[],
    )
    guard_item_body = execute_success_with_replay(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{guard_project_id}/domain-work-items",
        guard_item_payload,
        operation="project.domain_work_item.create",
        idempotency_key=GUARD_WORK_ITEM_KEY,
        csrf_token=administrator_csrf,
        expected_status=201,
        label="Guard Project Domain WorkItem",
        project_id=guard_project_id,
        evidence=evidence,
        payload_hashes=payload_hashes,
    )
    guard_item_id = guard_item_body.get("globalId")
    require(
        isinstance(guard_item_id, str)
        and guard_item_body.get("projectId") == guard_project_id
        and guard_item_body.get("kind") == "risk"
        and guard_item_body.get("workPolicyRef") == guard_policy_ref,
        "Guard Project Domain WorkItem response drifted",
    )

    concurrency_team_payload = team_payload(
        "concurrency",
        concurrency_project_id,
        policy_ref,
        owner_user,
        member_user,
    )
    concurrency_team_body = execute_success_with_replay(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{concurrency_project_id}:configure-team",
        concurrency_team_payload,
        operation="project.team.configure",
        idempotency_key=CONCURRENCY_TEAM_KEY,
        csrf_token=administrator_csrf,
        expected_status=200,
        label="Concurrency Project team",
        project_id=concurrency_project_id,
        evidence=evidence,
        payload_hashes=payload_hashes,
    )
    require_context_shape(
        concurrency_team_body,
        project_id=concurrency_project_id,
        version=2,
        administrator=True,
    )
    concurrency_winner_key = verify_true_concurrency(
        administrator,
        base_url,
        administrator_password=administrator_password,
        project_id=concurrency_project_id,
        policy_ref=policy_ref,
        evidence=evidence,
        payload_hashes=payload_hashes,
    )

    final_context = get_work_context(
        administrator,
        base_url,
        main_project_id,
    )
    require(final_context.status == 200, "Final Project work context failed")
    verify_final_work_context(
        final_context.body,
        project_id=main_project_id,
        policy_ref=policy_ref,
        owner=owner_user,
        member=member_user,
        baseline_id=baseline_id,
    )
    verify_domain_queries(
        administrator,
        base_url,
        main_project_id,
        item_ids=item_ids,
        owner=owner_user,
        member=member_user,
        stage_id=stage_id,
    )
    verify_domain_work_item_persistence(
        administrator,
        base_url,
        project_id=main_project_id,
        item_ids=item_ids,
        policy_ref=policy_ref,
        owner=owner_user,
        member=member_user,
        stage_id=stage_id,
    )
    verify_security_boundaries(
        administrator,
        owner_session,
        member_session,
        base_url,
        administrator_csrf=administrator_csrf,
        owner_csrf=owner_csrf,
        main_project_id=main_project_id,
        guard_project_id=guard_project_id,
        main_policy_ref=policy_ref,
        guard_policy_ref=guard_policy_ref,
        owner=owner_user,
        member=member_user,
    )
    command_specs = {
        MAIN_TEAM_KEY: (main_project_id, "project.team.configure"),
        MAIN_PLAN_KEY: (main_project_id, "project.work_plan.apply"),
        MAIN_BASELINE_KEY: (
            main_project_id,
            "project.plan_baseline.capture",
        ),
        MAIN_SHIFTED_PLAN_KEY: (
            main_project_id,
            "project.work_plan.apply",
        ),
        **{
            key: (main_project_id, "project.domain_work_item.create")
            for key in MAIN_WORK_ITEM_KEYS.values()
        },
        CYCLE_TEAM_KEY: (cycle_project_id, "project.team.configure"),
        GUARD_TEAM_KEY: (guard_project_id, "project.team.configure"),
        GUARD_PLAN_KEY: (guard_project_id, "project.work_plan.apply"),
        GUARD_BASELINE_KEY: (
            guard_project_id,
            "project.plan_baseline.capture",
        ),
        GUARD_WORK_ITEM_KEY: (
            guard_project_id,
            "project.domain_work_item.create",
        ),
        CONCURRENCY_TEAM_KEY: (
            concurrency_project_id,
            "project.team.configure",
        ),
        concurrency_winner_key: (
            concurrency_project_id,
            "project.work_plan.apply",
        ),
    }
    idempotency_rows = verify_idempotency_records(
        administrator,
        base_url,
        command_specs=command_specs,
        evidence=evidence,
        payload_hashes=payload_hashes,
    )
    verify_scoped_persistence(
        administrator,
        base_url,
        main_project_id=main_project_id,
        cycle_project_id=cycle_project_id,
        guard_project_id=guard_project_id,
        concurrency_project_id=concurrency_project_id,
    )
    expected_audit_events = [
        (
            guard_project_id,
            "project.team.configure",
            2,
            "updated",
            GUARD_TEAM_KEY,
        ),
        (
            guard_project_id,
            "project.work_plan.apply",
            3,
            "updated",
            GUARD_PLAN_KEY,
        ),
        (
            guard_baseline_id,
            "project.plan_baseline.capture",
            1,
            "created",
            GUARD_BASELINE_KEY,
        ),
        (
            guard_item_id,
            "project.domain_work_item.create",
            1,
            "created",
            GUARD_WORK_ITEM_KEY,
        ),
        (
            main_project_id,
            "project.team.configure",
            2,
            "updated",
            MAIN_TEAM_KEY,
        ),
        (
            main_project_id,
            "project.work_plan.apply",
            3,
            "updated",
            MAIN_PLAN_KEY,
        ),
        (
            baseline_id,
            "project.plan_baseline.capture",
            1,
            "created",
            MAIN_BASELINE_KEY,
        ),
        (
            main_project_id,
            "project.work_plan.apply",
            5,
            "updated",
            MAIN_SHIFTED_PLAN_KEY,
        ),
        *[
            (
                item_ids[kind],
                "project.domain_work_item.create",
                1,
                "created",
                MAIN_WORK_ITEM_KEYS[kind],
            )
            for kind in ("risk", "issue", "action", "decision_request")
        ],
        (
            cycle_project_id,
            "project.team.configure",
            2,
            "updated",
            CYCLE_TEAM_KEY,
        ),
        (
            concurrency_project_id,
            "project.team.configure",
            2,
            "updated",
            CONCURRENCY_TEAM_KEY,
        ),
        (
            concurrency_project_id,
            "project.work_plan.apply",
            3,
            "updated",
            concurrency_winner_key,
        ),
    ]
    guard_audit_name = verify_audit_events(
        administrator,
        base_url,
        expected_events=expected_audit_events,
        evidence=evidence,
    )
    delete_denials = verify_generic_crud_and_history_guards(
        administrator,
        base_url,
        administrator_csrf,
        guard_project_id=guard_project_id,
        owner=owner_user,
        guard_baseline_id=guard_baseline_id,
        guard_item_id=guard_item_id,
        guard_idempotency_name=str(
            idempotency_rows[GUARD_TEAM_KEY]["name"]
        ),
        guard_audit_name=guard_audit_name,
    )
    main_after_guard = get_work_context(
        administrator,
        base_url,
        main_project_id,
    )
    require(
        main_after_guard.status == 200
        and main_after_guard.body == final_context.body,
        "Sacrificial guard checks changed the main replay fixture",
    )

    print(
        json.dumps(
            {
                "auditEvents": len(expected_audit_events),
                "baselineHashVerified": True,
                "baselineVarianceItems": 2,
                "concurrency": {
                    "conflicts": 1,
                    "projectVersion": 3,
                    "winnerKey": concurrency_winner_key,
                },
                "cycleRejections": 2,
                "domainKinds": sorted(item_ids),
                "fixtureRevision": FIXTURE_REVISION,
                "fixtureRunId": FIXTURE_RUN_ID,
                "fixtureStatesBeforeWrite": fixture_states,
                "genericCreateUpdateDenied": True,
                "historyDeleteDenied": delete_denials,
                "idor": 404,
                "idempotencyRecords": len(command_specs),
                "mainProjectId": main_project_id,
                "mainProjectVersion": 9,
                "ownerReadOnly": True,
                "policyVersionKey": POLICY_VERSION_KEY,
                "retainedLocalFixtureUsers": [
                    owner_user,
                    member_user,
                ],
                "tenantId": TENANT_ID,
            },
            sort_keys=True,
        )
    )
    print("local Frappe Project work runtime verification passed")


if __name__ == "__main__":
    main()
