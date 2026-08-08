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
import verify_tooling_revision_runtime as predecessor
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
    create_resource,
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
ADMINISTRATOR_USER = "Administrator"
ACTOR_USER = (
    f"npi-tooling-manufacturing-{FIXTURE_RUN_ID[:12]}-manager@example.invalid"
)
UNRELATED_USER = (
    f"npi-tooling-manufacturing-{FIXTURE_RUN_ID[:12]}-unrelated@example.invalid"
)

REVISION_THREE_KEY = f"p6-04-runtime-r1-{FIXTURE_RUN_ID}-design-revision"
PLAN_ONE_KEY = f"p6-04-runtime-r1-{FIXTURE_RUN_ID}-plan-one"
PLAN_TWO_KEY = f"p6-04-runtime-r1-{FIXTURE_RUN_ID}-plan-two"
PLAN_CONFLICT_KEY = PLAN_ONE_KEY
PLAN_STALE_KEY = f"p6-04-runtime-r1-{FIXTURE_RUN_ID}-plan-stale"
PLAN_REFERENCE_KEY = f"p6-04-runtime-r1-{FIXTURE_RUN_ID}-plan-reference"
OBSERVATION_ONE_KEY = f"p6-04-runtime-r1-{FIXTURE_RUN_ID}-observation-one"
OBSERVATION_TWO_KEY = f"p6-04-runtime-r1-{FIXTURE_RUN_ID}-observation-two"
OBSERVATION_STALE_KEY = f"p6-04-runtime-r1-{FIXTURE_RUN_ID}-observation-stale"
OBSERVATION_REFERENCE_KEY = (
    f"p6-04-runtime-r1-{FIXTURE_RUN_ID}-observation-reference"
)
UNRELEASED_REFERENCE_KEY = (
    f"p6-04-runtime-r1-{FIXTURE_RUN_ID}-unreleased-design-reference"
)
PROJECT_TEAM_KEY = f"p6-04-runtime-r1-{FIXTURE_RUN_ID}-project-member"
ACTOR_MEMBER_ID = document_runtime.fixture_request_id(
    f"p6-04-{FIXTURE_RUN_ID}-manufacturing-actor-member"
)
PLAN_GLOBAL_ID = document_runtime.fixture_request_id(
    f"p6-04-{FIXTURE_RUN_ID}-manufacturing-plan"
)
UNRELEASED_PLAN_GLOBAL_ID = document_runtime.fixture_request_id(
    f"p6-04-{FIXTURE_RUN_ID}-unreleased-design-plan"
)
INTERNAL_MILESTONE_ID = document_runtime.fixture_request_id(
    f"p6-04-{FIXTURE_RUN_ID}-internal-design-milestone"
)
SUPPLIER_MILESTONE_ID = document_runtime.fixture_request_id(
    f"p6-04-{FIXTURE_RUN_ID}-supplier-machining-milestone"
)
ABSENT_PROJECT_ID = "00000000-0000-4000-8000-000000000001"
ABSENT_OBJECT_ID = "00000000-0000-4000-8000-000000000002"
MANUFACTURING_DOCTYPES = (
    "NPI Tooling Manufacturing Plan Revision",
    "NPI Tooling Manufacturing Milestone Observation",
)
MANUFACTURING_PERMISSIONS = {
    "view": True,
    "createPlan": True,
    "observeMilestone": True,
    "transitionLifecycle": False,
    "editErpProjection": False,
}


def manufacturing_path(project_id: str, master_id: str, suffix: str = "") -> str:
    return (
        f"/api/npi/v1/projects/{project_id}/tooling/{master_id}/"
        f"manufacturing-plans{suffix}"
    )


def tooling_request(*args, query_key: str = "query", **kwargs):
    return predecessor.tooling_request(
        *args,
        query_key=f"p604-{query_key}",
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
    require(
        result.status == 201,
        (
            f"P6-04 command {key} returned HTTP {result.status} with problem code "
            f"{result.body.get('code', 'UNAVAILABLE')}"
        ),
    )
    require(
        result.headers.get("Idempotency-Replayed") in {"true", "false"},
        "P6-04 replay header is invalid",
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


def unavailable(value: object, reason_code: str, label: str) -> None:
    require(
        isinstance(value, dict)
        and value.get("state") == "unavailable"
        and value.get("reasonCode") == reason_code,
        f"{label} unavailable truth drifted",
    )


def project_context(
    administrator,
    base_url: str,
) -> tuple[str, str, str, dict[str, str]]:
    (
        project_id,
        master_id,
        _retained_part_id,
        _retained_revision_ids,
        _set_id,
        model_reference,
    ) = predecessor.project_context(administrator, base_url)
    _part_id, _part_revision_id, applicability_id = predecessor.dedicated_part_context(
        administrator,
        base_url,
        project_id,
    )
    return project_id, master_id, applicability_id, model_reference


def prepare_manufacturing_actor(
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
            "email": ACTOR_USER,
            "enabled": 1,
            "first_name": "NPI Tooling Manufacturing",
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
        "P6-04 manufacturing actor fixture could not be created",
    )
    retained = get_resource(administrator, base_url, "User", ACTOR_USER)
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
        "P6-04 manufacturing actor transport authority drifted",
    )
    project_id, _project_version = document_runtime.fixture_project(
        administrator,
        base_url,
    )
    projects = predecessor.predecessor.rows(
        administrator,
        base_url,
        "NPI Engineering Project",
        [["global_id", "=", project_id]],
        [
            "global_id",
            "optimistic_version",
            "work_policy_global_id",
            "work_policy_version",
            "work_policy_snapshot_hash",
        ],
    )
    project = predecessor.predecessor.exact_single(
        projects,
        "P6-04 manufacturing actor Project",
    )
    configured = document_runtime.npi_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}:configure-team",
        method="POST",
        payload={
            "expectedProjectVersion": int(project["optimistic_version"]),
            "workPolicyRef": {
                "globalId": project["work_policy_global_id"],
                "version": int(project["work_policy_version"]),
                "snapshotHash": project["work_policy_snapshot_hash"],
            },
            "members": [
                {
                    "globalId": ACTOR_MEMBER_ID,
                    "userId": ACTOR_USER,
                    "effectiveFrom": "2026-08-01",
                }
            ],
            "roleAssignments": [],
            "substitutions": [],
            "raciAssignments": [],
        },
        csrf_token=csrf_token,
        idempotency_key=PROJECT_TEAM_KEY,
    )
    require(
        configured.status == 200
        and configured.headers.get("Idempotency-Replayed") == "false"
        and configured.body.get("projectVersion")
        == int(project["optimistic_version"]) + 1,
        "P6-04 manufacturing actor membership drifted",
    )
    actor = login(base_url, ACTOR_USER, fixture_password)
    actor_csrf = bootstrap_csrf(actor, base_url, ACTOR_USER)
    return actor, actor_csrf


def active_member(administrator, base_url: str, project_id: str) -> dict[str, object]:
    matches = predecessor.predecessor.rows(
        administrator,
        base_url,
        "NPI Project Member",
        [
            ["project_global_id", "=", project_id],
            ["user_id", "=", ACTOR_USER],
            ["effective_to", "is", "not set"],
        ],
        ["global_id", "user_id", "optimistic_version", "effective_to"],
    )
    member = predecessor.predecessor.exact_single(matches, "P6-04 active Project member")
    value = {
        "globalId": require_uuid(member.get("global_id"), "P6-04 Project member"),
        "userId": str(member.get("user_id")),
        "optimisticVersion": int(member.get("optimistic_version") or 0),
    }
    require(
        value["userId"] == ACTOR_USER
        and value["optimisticVersion"] >= 1
        and member.get("effective_to") in {None, ""},
        "P6-04 active Project member truth drifted",
    )
    return value


def released_document(
    administrator,
    base_url: str,
    project_id: str,
) -> dict[str, object]:
    lifecycles = predecessor.predecessor.rows(
        administrator,
        base_url,
        "NPI Document Revision Lifecycle",
        [
            ["project_global_id", "=", project_id],
            ["current_state", "=", "released"],
        ],
        [
            "global_id",
            "revision_global_id",
            "lifecycle_version",
            "release_event_global_id",
            "release_snapshot_hash",
            "last_event_global_id",
        ],
    )
    lifecycle = predecessor.predecessor.exact_single(
        lifecycles,
        "P6-04 released Document lifecycle",
    )
    revision_id = require_uuid(
        lifecycle.get("revision_global_id"),
        "P6-04 released Document Revision",
    )
    revisions = predecessor.predecessor.rows(
        administrator,
        base_url,
        "NPI Document Revision",
        [["global_id", "=", revision_id]],
        ["global_id", "snapshot_hash"],
    )
    revision = predecessor.predecessor.exact_single(
        revisions,
        "P6-04 released Document Revision",
    )
    release_event_id = require_uuid(
        lifecycle.get("release_event_global_id"),
        "P6-04 release event",
    )
    events = predecessor.predecessor.rows(
        administrator,
        base_url,
        "NPI Document Lifecycle Event",
        [["global_id", "=", release_event_id]],
        ["global_id", "event_type", "to_state", "to_version", "event_hash"],
    )
    event = predecessor.predecessor.exact_single(events, "P6-04 release event")
    lifecycle_version = int(lifecycle.get("lifecycle_version") or 0)
    require(
        lifecycle.get("last_event_global_id") == release_event_id
        and event.get("event_type") == "released"
        and event.get("to_state") == "released"
        and int(event.get("to_version") or 0) == lifecycle_version,
        "P6-04 released Document lineage drifted",
    )
    return {
        "revisionGlobalId": revision_id,
        "revisionSnapshotHash": require_hash(
            revision.get("snapshot_hash"),
            "P6-04 Document Revision",
        ),
        "lifecycleGlobalId": require_uuid(
            lifecycle.get("global_id"),
            "P6-04 Document lifecycle",
        ),
        "lifecycleVersion": lifecycle_version,
        "releaseEventGlobalId": release_event_id,
        "releaseEventHash": require_hash(
            event.get("event_hash"),
            "P6-04 release event",
        ),
        "releaseSnapshotHash": require_hash(
            lifecycle.get("release_snapshot_hash"),
            "P6-04 release snapshot",
        ),
    }


def unreleased_document(
    administrator,
    base_url: str,
    project_id: str,
    released: dict[str, object],
) -> dict[str, object]:
    revisions = predecessor.predecessor.rows(
        administrator,
        base_url,
        "NPI Document Revision",
        [["project_global_id", "=", project_id]],
        ["global_id", "snapshot_hash"],
    )
    candidates = sorted(
        (
            value
            for value in revisions
            if value.get("global_id") != released["revisionGlobalId"]
        ),
        key=lambda value: str(value.get("global_id")),
    )
    require(bool(candidates), "P6-04 unreleased Document Revision is unavailable")
    revision = candidates[0]
    revision_id = require_uuid(
        revision.get("global_id"),
        "P6-04 unreleased Document Revision",
    )
    lifecycles = predecessor.predecessor.rows(
        administrator,
        base_url,
        "NPI Document Revision Lifecycle",
        [["revision_global_id", "=", revision_id]],
        ["global_id", "current_state", "lifecycle_version"],
    )
    require(
        all(value.get("current_state") != "released" for value in lifecycles),
        "P6-04 unreleased Document selection drifted",
    )
    lifecycle = lifecycles[0] if lifecycles else None
    return {
        "revisionGlobalId": revision_id,
        "revisionSnapshotHash": require_hash(
            revision.get("snapshot_hash"),
            "P6-04 unreleased Document Revision",
        ),
        "lifecycleGlobalId": (
            require_uuid(
                lifecycle.get("global_id"),
                "P6-04 unreleased Document lifecycle",
            )
            if lifecycle is not None
            else ABSENT_OBJECT_ID
        ),
        "lifecycleVersion": (
            int(lifecycle.get("lifecycle_version") or 1)
            if lifecycle is not None
            else 1
        ),
        "releaseEventGlobalId": ABSENT_PROJECT_ID,
        "releaseEventHash": "0" * 64,
        "releaseSnapshotHash": "0" * 64,
    }


def milestone_file_evidence(
    administrator,
    base_url: str,
    project_id: str,
) -> dict[str, object]:
    file_id = predecessor.predecessor.TOOLING_PHOTO_FILE_REVISION_ID
    matches = predecessor.predecessor.rows(
        administrator,
        base_url,
        "NPI File Revision",
        [
            ["global_id", "=", file_id],
            ["project_global_id", "=", project_id],
        ],
        [
            "global_id",
            "optimistic_version",
            "frappe_content_hash",
            "sha256",
            "scan_state",
            "is_private",
        ],
    )
    row = predecessor.predecessor.exact_single(
        matches,
        "P6-04 milestone File Revision",
    )
    require(
        row.get("scan_state") == "clean"
        and row.get("is_private") == 1
        and int(row.get("optimistic_version") or 0) == 2,
        "P6-04 milestone File Revision truth drifted",
    )
    content_hash = str(row.get("frappe_content_hash") or "")
    require(
        32 <= len(content_hash) <= 128
        and all(character in "0123456789abcdef" for character in content_hash),
        "P6-04 Frappe content hash drifted",
    )
    return {
        "role": "progress_evidence",
        "fileRevisionGlobalId": file_id,
        "fileOptimisticVersion": 2,
        "frappeContentHash": content_hash,
        "sha256": require_hash(row.get("sha256"), "P6-04 milestone file"),
    }


def design_revision_payload(
    applicability_id: str,
    model_reference: dict[str, str],
    released: dict[str, object],
) -> dict[str, object]:
    payload = predecessor.revision_payload(applicability_id, 3, model_reference)
    payload["designDocumentRevisions"] = [
        {
            "globalId": released["revisionGlobalId"],
            "snapshotHash": released["revisionSnapshotHash"],
        }
    ]
    payload["reason"] = "Bind the released design evidence for manufacturing planning."
    return payload


def plan_payload(
    tooling_revision_id: str,
    tooling_revision_snapshot_hash: str,
    member: dict[str, object],
    released: dict[str, object],
    *,
    version: int,
) -> dict[str, object]:
    require(version in {1, 2}, "P6-04 plan payload version is invalid")
    payload: dict[str, object] = {
        "planGlobalId": PLAN_GLOBAL_ID,
        "toolingRevisionGlobalId": tooling_revision_id,
        "toolingRevisionSnapshotHash": tooling_revision_snapshot_hash,
        "sourcingStrategy": "hybrid",
        "responsibleMember": dict(member),
        "engineeringEstimate": {"amount": "120000.00", "currency": "CNY"},
        "budget": {"amount": "130000.00", "currency": "CNY"},
        "evidence": [{"role": "dfm", "document": dict(released)}],
        "designReleaseEvidence": [dict(released)],
        "milestones": [
            {
                "globalId": INTERNAL_MILESTONE_ID,
                "sequence": 1,
                "category": "design",
                "plannedStart": "2026-08-10",
                "plannedFinish": "2026-08-20",
                "responsibilityKind": "internal",
                "responsibleMember": dict(member),
                "predecessorGlobalIds": [],
            },
            {
                "globalId": SUPPLIER_MILESTONE_ID,
                "sequence": 2,
                "category": "machining",
                "plannedStart": "2026-08-21",
                "plannedFinish": "2026-09-18" if version == 1 else "2026-09-16",
                "responsibilityKind": "supplier",
                "responsibleMember": None,
                "predecessorGlobalIds": [INTERNAL_MILESTONE_ID],
            },
        ],
        "reason": (
            "Establish the controlled hybrid manufacturing plan."
            if version == 1
            else "Advance the controlled plan after the reviewed schedule update."
        ),
    }
    if version == 2:
        payload["expectedVersion"] = 1
    return payload


def observation_payload(
    plan: dict[str, object],
    evidence: dict[str, object],
    *,
    version: int,
) -> dict[str, object]:
    require(version in {1, 2}, "P6-04 observation payload version is invalid")
    milestones = plan.get("milestones")
    require(isinstance(milestones, list), "P6-04 plan milestones are invalid")
    supplier = predecessor.predecessor.exact_single(
        [
            value
            for value in milestones
            if isinstance(value, dict)
            and value.get("globalId") == SUPPLIER_MILESTONE_ID
        ],
        "P6-04 supplier milestone",
    )
    payload: dict[str, object] = {
        "planRevisionSnapshotHash": plan["snapshotHash"],
        "milestoneSnapshotHash": supplier["snapshotHash"],
        "progressPercentage": 35 if version == 1 else 65,
        "actualStart": "2026-08-21",
        "risk": "Supplier machining capacity is monitored.",
        "note": (
            "Record the first controlled supplier progress observation."
            if version == 1
            else "Advance the controlled supplier progress observation."
        ),
        "evidence": [dict(evidence)],
    }
    if version == 2:
        payload["expectedVersion"] = 1
    return payload


def assert_design_capability(
    value: object,
    released: dict[str, object],
) -> None:
    require(
        value
        == {
            "state": "satisfied",
            "reasonCode": None,
            "items": [released],
        },
        "P6-04 released design capability drifted",
    )


def assert_plan(
    value: object,
    *,
    master_id: str,
    tooling_revision_id: str,
    version: int,
    member: dict[str, object],
    released: dict[str, object],
) -> dict[str, Any]:
    require(isinstance(value, dict), "P6-04 manufacturing plan is invalid")
    require(
        set(value)
        == {
            "globalId",
            "planGlobalId",
            "toolingMasterGlobalId",
            "toolingRevisionGlobalId",
            "toolingRevisionSnapshotHash",
            "planVersion",
            "predecessorGlobalId",
            "predecessorSnapshotHash",
            "sourcingStrategy",
            "responsibleMember",
            "engineeringEstimate",
            "budget",
            "evidence",
            "designReleaseEvidence",
            "milestones",
            "reason",
            "snapshotHash",
        }
        and value.get("planGlobalId") == PLAN_GLOBAL_ID
        and value.get("toolingMasterGlobalId") == master_id
        and value.get("toolingRevisionGlobalId") == tooling_revision_id
        and value.get("planVersion") == version
        and value.get("sourcingStrategy") == "hybrid"
        and value.get("responsibleMember") == member
        and value.get("designReleaseEvidence") == [released],
        "P6-04 manufacturing plan contract drifted",
    )
    require_uuid(value.get("globalId"), "P6-04 manufacturing plan revision")
    require_hash(value.get("toolingRevisionSnapshotHash"), "P6-04 Tooling Revision")
    require_hash(value.get("snapshotHash"), "P6-04 manufacturing plan")
    milestones = value.get("milestones")
    require(
        isinstance(milestones, list)
        and len(milestones) == 2
        and [item.get("sequence") for item in milestones] == [1, 2]
        and milestones[0].get("responsibilityKind") == "internal"
        and milestones[0].get("responsibleMember") == member
        and milestones[1].get("responsibilityKind") == "supplier"
        and milestones[1].get("responsibleMember") is None
        and milestones[1].get("predecessorGlobalIds")
        == [INTERNAL_MILESTONE_ID]
        and all(
            isinstance(item.get("snapshotHash"), str)
            and len(item["snapshotHash"]) == 64
            for item in milestones
        ),
        "P6-04 milestone dependency or responsibility drifted",
    )
    return value


def assert_observation(
    value: object,
    *,
    plan: dict[str, object],
    version: int,
    member: dict[str, object],
) -> dict[str, Any]:
    require(isinstance(value, dict), "P6-04 milestone observation is invalid")
    require(
        set(value)
        == {
            "globalId",
            "planRevisionGlobalId",
            "planRevisionSnapshotHash",
            "milestoneGlobalId",
            "milestoneSnapshotHash",
            "observationVersion",
            "predecessorGlobalId",
            "predecessorSnapshotHash",
            "progressPercentage",
            "actualStart",
            "actualFinish",
            "risk",
            "note",
            "evidence",
            "reportedByMember",
            "snapshotHash",
        }
        and value.get("planRevisionGlobalId") == plan.get("globalId")
        and value.get("planRevisionSnapshotHash") == plan.get("snapshotHash")
        and value.get("milestoneGlobalId") == SUPPLIER_MILESTONE_ID
        and value.get("observationVersion") == version
        and value.get("progressPercentage") == (35 if version == 1 else 65)
        and value.get("reportedByMember") == member,
        "P6-04 milestone observation contract drifted",
    )
    require_uuid(value.get("globalId"), "P6-04 milestone observation")
    require_hash(value.get("milestoneSnapshotHash"), "P6-04 milestone")
    require_hash(value.get("snapshotHash"), "P6-04 milestone observation")
    evidence = value.get("evidence")
    require(
        isinstance(evidence, list)
        and len(evidence) == 1
        and evidence[0].get("role") == "progress_evidence"
        and evidence[0].get("fileRevisionGlobalId")
        == predecessor.predecessor.TOOLING_PHOTO_FILE_REVISION_ID
        and evidence[0].get("fileOptimisticVersion") == 2
        and evidence[0].get("mimeType") == "image/png"
        and evidence[0].get("sizeBytes", 0) > 0,
        "P6-04 milestone evidence drifted",
    )
    return value


def assert_context(
    result,
    *,
    project_id: str,
    master_id: str,
    member: dict[str, object],
    released: dict[str, object],
    tooling_revision_id: str | None,
    expected_count: int,
) -> dict[str, Any]:
    require(result.status == 200, "P6-04 manufacturing context failed")
    require(
        set(result.body)
        == {
            "projectGlobalId",
            "toolingMasterGlobalId",
            "permissions",
            "manufacturingAuthorization",
            "erpProjection",
            "items",
        }
        and result.body.get("projectGlobalId") == project_id
        and result.body.get("toolingMasterGlobalId") == master_id
        and result.body.get("permissions") == MANUFACTURING_PERMISSIONS,
        "P6-04 manufacturing context contract drifted",
    )
    unavailable(
        result.body.get("manufacturingAuthorization"),
        "tooling_lifecycle_policy_unavailable",
        "manufacturing authorization",
    )
    unavailable(
        result.body.get("erpProjection"),
        "erp_projection_unavailable",
        "ERP projection",
    )
    require(
        result.body["erpProjection"].get("sourceSystem") == "ERPNEXT"
        and result.body["erpProjection"].get("editableIn") == "ERPNEXT",
        "P6-04 ERP ownership truth drifted",
    )
    items = result.body.get("items")
    require(
        isinstance(items, list) and len(items) == expected_count,
        "P6-04 manufacturing plan cardinality drifted",
    )
    if expected_count == 0:
        return result.body
    require(tooling_revision_id is not None, "P6-04 Tooling Revision context is missing")
    previous_plan = None
    for version, item in enumerate(items, start=1):
        require(
            isinstance(item, dict)
            and set(item) == {"plan", "observations", "designReleaseEvidence"},
            "P6-04 manufacturing item contract drifted",
        )
        plan = assert_plan(
            item.get("plan"),
            master_id=master_id,
            tooling_revision_id=tooling_revision_id,
            version=version,
            member=member,
            released=released,
        )
        assert_design_capability(item.get("designReleaseEvidence"), released)
        if previous_plan is None:
            require(
                plan.get("predecessorGlobalId") is None
                and plan.get("predecessorSnapshotHash") is None,
                "P6-04 first plan predecessor drifted",
            )
        else:
            require(
                plan.get("predecessorGlobalId") == previous_plan.get("globalId")
                and plan.get("predecessorSnapshotHash")
                == previous_plan.get("snapshotHash"),
                "P6-04 immutable plan successor drifted",
            )
        observations = item.get("observations")
        expected_observations = 2 if version == 1 else 0
        require(
            isinstance(observations, list)
            and len(observations) == expected_observations,
            "P6-04 milestone observation cardinality drifted",
        )
        previous_observation = None
        for observation_version, observation in enumerate(observations, start=1):
            current = assert_observation(
                observation,
                plan=plan,
                version=observation_version,
                member=member,
            )
            if previous_observation is None:
                require(
                    current.get("predecessorGlobalId") is None
                    and current.get("predecessorSnapshotHash") is None,
                    "P6-04 first observation predecessor drifted",
                )
            else:
                require(
                    current.get("predecessorGlobalId")
                    == previous_observation.get("globalId")
                    and current.get("predecessorSnapshotHash")
                    == previous_observation.get("snapshotHash"),
                    "P6-04 immutable observation successor drifted",
                )
            previous_observation = current
        previous_plan = plan
    return result.body


def persisted_counts(administrator, base_url: str, project_id: str) -> dict[str, int]:
    return {
        doctype: len(
            predecessor.predecessor.rows(
                administrator,
                base_url,
                doctype,
                [["project_global_id", "=", project_id]],
            )
        )
        for doctype in MANUFACTURING_DOCTYPES
    }


def verify_persistence(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    project_id: str,
    plan_ids: tuple[str, str],
    observation_ids: tuple[str, str],
) -> None:
    require(
        persisted_counts(administrator, base_url, project_id)
        == {
            "NPI Tooling Manufacturing Plan Revision": 2,
            "NPI Tooling Manufacturing Milestone Observation": 2,
        },
        "P6-04 persisted immutable cardinality drifted",
    )
    for operation in (
        "tooling_manufacturing_plan.create",
        "tooling_manufacturing_milestone.observe",
    ):
        receipts = predecessor.predecessor.rows(
            administrator,
            base_url,
            "NPI Tooling Command Idempotency",
            [["operation", "=", operation]],
            ["actor_user_id", "payload_hash", "response_hash", "sealed"],
        )
        audits = predecessor.predecessor.rows(
            administrator,
            base_url,
            "NPI Audit Event",
            [["operation", "=", operation]],
            ["result", "trace_id"],
        )
        require(
            len(receipts) == 2
            and all(item.get("actor_user_id") == ACTOR_USER for item in receipts)
            and all(item.get("sealed") == 1 for item in receipts)
            and all(len(str(item.get("payload_hash"))) == 64 for item in receipts)
            and all(len(str(item.get("response_hash"))) == 64 for item in receipts)
            and len(audits) == 2
            and all(item.get("result") == "created" for item in audits)
            and all(item.get("trace_id") for item in audits),
            f"P6-04 receipt or audit truth drifted for {operation}",
        )
    immutable = tuple(
        ("NPI Tooling Manufacturing Plan Revision", value) for value in plan_ids
    ) + tuple(
        ("NPI Tooling Manufacturing Milestone Observation", value)
        for value in observation_ids
    )
    for doctype, name in immutable:
        before = get_resource(administrator, base_url, doctype, name)
        snapshot_hash = before.body.get("data", {}).get("snapshot_hash")
        require(
            before.status == 200
            and isinstance(snapshot_hash, str)
            and len(snapshot_hash) == 64,
            f"P6-04 immutable {doctype} is unavailable",
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
            f"P6-04 immutable {doctype} accepted generic mutation",
        )


def verify_idor(
    administrator,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
    *,
    project_id: str,
    master_id: str,
    plan_revision_id: str,
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
            manufacturing_path(project_id, master_id),
            query_key="idor-denied",
        )
        absent = tooling_request(
            unrelated,
            base_url,
            manufacturing_path(ABSENT_PROJECT_ID, master_id),
            query_key="idor-absent-project",
        )
        validate_problem(denied, 404, "TOOLING_UNAVAILABLE")
        validate_problem(absent, 404, "TOOLING_UNAVAILABLE")
        fields = ("type", "title", "status", "code", "retryable")
        require(
            {key: denied.body.get(key) for key in fields}
            == {key: absent.body.get(key) for key in fields},
            "P6-04 unauthorized and absent Projects are distinguishable",
        )
    finally:
        delete_disposable_user(
            administrator,
            base_url,
            UNRELATED_USER,
            csrf_token,
        )
    projects = predecessor.predecessor.rows(
        administrator,
        base_url,
        "NPI Engineering Project",
        [["business_code", "=", predecessor.predecessor.SECOND_PROJECT_CODE]],
        ["global_id"],
    )
    second_project_id = str(
        predecessor.predecessor.exact_single(
            projects,
            "P6-04 second Project",
        )["global_id"]
    )
    cross_project = tooling_request(
        administrator,
        base_url,
        manufacturing_path(
            second_project_id,
            master_id,
            f"/{plan_revision_id}",
        ),
        query_key="idor-cross-project",
    )
    missing = tooling_request(
        administrator,
        base_url,
        manufacturing_path(project_id, master_id, f"/{ABSENT_OBJECT_ID}"),
        query_key="idor-absent-plan",
    )
    validate_problem(cross_project, 404, "TOOLING_UNAVAILABLE")
    validate_problem(missing, 404, "TOOLING_UNAVAILABLE")
    fields = ("type", "title", "status", "code", "retryable")
    require(
        {key: cross_project.body.get(key) for key in fields}
        == {key: missing.body.get(key) for key in fields},
        "P6-04 cross-Project and absent Plans are distinguishable",
    )


def verify_conflict_rollback(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    project_id: str,
    master_id: str,
    revision_id: str,
    revision_snapshot_hash: str,
    member: dict[str, object],
    released: dict[str, object],
    unreleased: dict[str, object],
    plan_one: dict[str, object],
    file_evidence: dict[str, object],
) -> None:
    before = persisted_counts(administrator, base_url, project_id)
    different = plan_payload(
        revision_id,
        revision_snapshot_hash,
        member,
        released,
        version=1,
    )
    different["reason"] = "A different request must not reuse the same key."
    stale_observation = observation_payload(plan_one, file_evidence, version=2)
    reference_observation = observation_payload(plan_one, file_evidence, version=1)
    reference_observation["planRevisionSnapshotHash"] = "0" * 64
    unreleased_plan = plan_payload(
        revision_id,
        revision_snapshot_hash,
        member,
        unreleased,
        version=1,
    )
    unreleased_plan["planGlobalId"] = UNRELEASED_PLAN_GLOBAL_ID
    conflicts = (
        (
            manufacturing_path(project_id, master_id),
            different,
            PLAN_CONFLICT_KEY,
            409,
            "TOOLING_IDEMPOTENCY_CONFLICT",
        ),
        (
            manufacturing_path(project_id, master_id),
            plan_payload(
                revision_id,
                revision_snapshot_hash,
                member,
                released,
                version=2,
            ),
            PLAN_STALE_KEY,
            409,
            "TOOLING_VERSION_CONFLICT",
        ),
        (
            manufacturing_path(project_id, master_id),
            plan_payload(
                revision_id,
                "0" * 64,
                member,
                released,
                version=1,
            )
            | {"planGlobalId": ABSENT_OBJECT_ID},
            PLAN_REFERENCE_KEY,
            404,
            "TOOLING_REFERENCE_UNAVAILABLE",
        ),
        (
            manufacturing_path(project_id, master_id),
            unreleased_plan,
            UNRELEASED_REFERENCE_KEY,
            404,
            "TOOLING_REFERENCE_UNAVAILABLE",
        ),
        (
            manufacturing_path(
                project_id,
                master_id,
                f"/{plan_one['globalId']}/milestones/"
                f"{SUPPLIER_MILESTONE_ID}/observations",
            ),
            stale_observation,
            OBSERVATION_STALE_KEY,
            409,
            "TOOLING_VERSION_CONFLICT",
        ),
        (
            manufacturing_path(
                project_id,
                master_id,
                f"/{plan_one['globalId']}/milestones/"
                f"{SUPPLIER_MILESTONE_ID}/observations",
            ),
            reference_observation,
            OBSERVATION_REFERENCE_KEY,
            404,
            "TOOLING_REFERENCE_UNAVAILABLE",
        ),
    )
    for path, payload, key, status, code in conflicts:
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
        persisted_counts(administrator, base_url, project_id) == before,
        "P6-04 failed commands changed immutable cardinality",
    )


def tooling_revision_collection(administrator, base_url: str, project_id: str, master_id: str):
    result = tooling_request(
        administrator,
        base_url,
        predecessor.revision_path(project_id, master_id),
        query_key="revision-context",
    )
    require(
        result.status == 200
        and isinstance(result.body.get("items"), list)
        and len(result.body["items"]) == 3,
        "P6-04 retained Tooling Revision chain drifted",
    )
    return result


def run_fresh(
    administrator,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
) -> dict[str, object]:
    project_id, master_id, applicability_id, model_reference = project_context(
        administrator,
        base_url,
    )
    schema = run_bench_fixture(
        "verify_tooling_manufacturing_runtime_schema",
        {"fixture_run_id": FIXTURE_RUN_ID},
    )
    member = active_member(administrator, base_url, project_id)
    released = released_document(administrator, base_url, project_id)
    unreleased = unreleased_document(
        administrator,
        base_url,
        project_id,
        released,
    )
    file_evidence = milestone_file_evidence(administrator, base_url, project_id)
    empty = assert_context(
        tooling_request(
            administrator,
            base_url,
            manufacturing_path(project_id, master_id),
            query_key="empty-manufacturing",
        ),
        project_id=project_id,
        master_id=master_id,
        member=member,
        released=released,
        tooling_revision_id=None,
        expected_count=0,
    )
    require(empty["items"] == [], "P6-04 fresh manufacturing context was not empty")
    guest = tooling_request(
        urllib.request.build_opener(),
        base_url,
        manufacturing_path(project_id, master_id),
        query_key="guest",
    )
    validate_problem(guest, 401, "AUTHENTICATION_REQUIRED")

    revision = predecessor.command(
        administrator,
        base_url,
        csrf_token,
        predecessor.revision_path(project_id, master_id),
        design_revision_payload(applicability_id, model_reference, released),
        REVISION_THREE_KEY,
    )
    revision_value = revision.body.get("revision")
    require(
        isinstance(revision_value, dict)
        and revision_value.get("revisionNumber") == 3
        and revision_value.get("revisionLabel") == "R3"
        and revision_value.get("designDocumentRevisions")
        == [
            {
                "globalId": released["revisionGlobalId"],
                "snapshotHash": released["revisionSnapshotHash"],
            }
        ],
        "P6-04 design-bound Tooling Revision drifted",
    )
    revision_id = require_uuid(
        revision_value.get("globalId"),
        "P6-04 Tooling Revision",
    )
    revision_snapshot_hash = require_hash(
        revision_value.get("snapshotHash"),
        "P6-04 Tooling Revision",
    )
    tooling_revision_collection(
        administrator,
        base_url,
        project_id,
        master_id,
    )

    plan_one_result = command(
        administrator,
        base_url,
        csrf_token,
        manufacturing_path(project_id, master_id),
        plan_payload(
            revision_id,
            revision_snapshot_hash,
            member,
            released,
            version=1,
        ),
        PLAN_ONE_KEY,
    )
    plan_one = assert_plan(
        plan_one_result.body.get("plan"),
        master_id=master_id,
        tooling_revision_id=revision_id,
        version=1,
        member=member,
        released=released,
    )
    assert_design_capability(
        plan_one_result.body.get("designReleaseEvidence"),
        released,
    )
    observation_path = manufacturing_path(
        project_id,
        master_id,
        f"/{plan_one['globalId']}/milestones/{SUPPLIER_MILESTONE_ID}/observations",
    )
    observation_one_result = command(
        administrator,
        base_url,
        csrf_token,
        observation_path,
        observation_payload(plan_one, file_evidence, version=1),
        OBSERVATION_ONE_KEY,
    )
    observation_one = assert_observation(
        observation_one_result.body.get("observation"),
        plan=plan_one,
        version=1,
        member=member,
    )
    observation_two_result = command(
        administrator,
        base_url,
        csrf_token,
        observation_path,
        observation_payload(plan_one, file_evidence, version=2),
        OBSERVATION_TWO_KEY,
    )
    observation_two = assert_observation(
        observation_two_result.body.get("observation"),
        plan=plan_one,
        version=2,
        member=member,
    )
    require(
        observation_two.get("predecessorGlobalId") == observation_one.get("globalId")
        and observation_two.get("predecessorSnapshotHash")
        == observation_one.get("snapshotHash"),
        "P6-04 milestone observation successor drifted",
    )
    plan_two_result = command(
        administrator,
        base_url,
        csrf_token,
        manufacturing_path(project_id, master_id),
        plan_payload(
            revision_id,
            revision_snapshot_hash,
            member,
            released,
            version=2,
        ),
        PLAN_TWO_KEY,
    )
    plan_two = assert_plan(
        plan_two_result.body.get("plan"),
        master_id=master_id,
        tooling_revision_id=revision_id,
        version=2,
        member=member,
        released=released,
    )
    require(
        plan_two.get("predecessorGlobalId") == plan_one.get("globalId")
        and plan_two.get("predecessorSnapshotHash") == plan_one.get("snapshotHash"),
        "P6-04 immutable plan successor drifted",
    )
    assert_design_capability(
        plan_two_result.body.get("designReleaseEvidence"),
        released,
    )
    collection = assert_context(
        tooling_request(
            administrator,
            base_url,
            manufacturing_path(project_id, master_id),
            query_key="retained-manufacturing",
        ),
        project_id=project_id,
        master_id=master_id,
        member=member,
        released=released,
        tooling_revision_id=revision_id,
        expected_count=2,
    )
    for item in collection["items"]:
        detail = tooling_request(
            administrator,
            base_url,
            manufacturing_path(
                project_id,
                master_id,
                f"/{item['plan']['globalId']}",
            ),
            query_key=f"plan-detail-{item['plan']['planVersion']}",
        )
        require(
            detail.status == 200
            and set(detail.body)
            == {
                "projectGlobalId",
                "toolingMasterGlobalId",
                "permissions",
                "manufacturingAuthorization",
                "erpProjection",
                "item",
            }
            and detail.body.get("item") == item,
            "P6-04 manufacturing plan detail drifted",
        )
    verify_idor(
        administrator,
        base_url,
        csrf_token,
        fixture_password,
        project_id=project_id,
        master_id=master_id,
        plan_revision_id=str(plan_one["globalId"]),
    )
    verify_persistence(
        administrator,
        base_url,
        csrf_token,
        project_id=project_id,
        plan_ids=(str(plan_one["globalId"]), str(plan_two["globalId"])),
        observation_ids=(
            str(observation_one["globalId"]),
            str(observation_two["globalId"]),
        ),
    )
    verify_conflict_rollback(
        administrator,
        base_url,
        csrf_token,
        project_id=project_id,
        master_id=master_id,
        revision_id=revision_id,
        revision_snapshot_hash=revision_snapshot_hash,
        member=member,
        released=released,
        unreleased=unreleased,
        plan_one=plan_one,
        file_evidence=file_evidence,
    )
    return {
        "doctypeCount": schema["doctypeCount"],
        "erpProjection": "unavailable",
        "fixtureRunId": FIXTURE_RUN_ID,
        "manufacturingAuthorization": "unavailable",
        "milestoneObservationCount": 2,
        "planRevisionCount": 2,
        "toolingRevisionCount": 3,
    }


def replay_context(administrator, base_url: str):
    project_id, master_id, applicability_id, model_reference = project_context(
        administrator,
        base_url,
    )
    member = active_member(administrator, base_url, project_id)
    released = released_document(administrator, base_url, project_id)
    file_evidence = milestone_file_evidence(administrator, base_url, project_id)
    revisions = tooling_revision_collection(
        administrator,
        base_url,
        project_id,
        master_id,
    ).body["items"]
    revision = predecessor.predecessor.exact_single(
        [value for value in revisions if value.get("revisionNumber") == 3],
        "P6-04 Tooling Revision",
    )
    revision_detail = tooling_request(
        administrator,
        base_url,
        predecessor.revision_path(
            project_id,
            master_id,
            f"/{revision['globalId']}",
        ),
        query_key="replay-revision-detail",
    )
    require(revision_detail.status == 200, "P6-04 Tooling Revision detail is unavailable")
    collection = assert_context(
        tooling_request(
            administrator,
            base_url,
            manufacturing_path(project_id, master_id),
            query_key="replay-manufacturing",
        ),
        project_id=project_id,
        master_id=master_id,
        member=member,
        released=released,
        tooling_revision_id=str(revision["globalId"]),
        expected_count=2,
    )
    return (
        project_id,
        master_id,
        applicability_id,
        model_reference,
        member,
        released,
        file_evidence,
        revision,
        revision_detail.body,
        collection,
    )


def run_replay(administrator, base_url: str, csrf_token: str) -> None:
    (
        project_id,
        master_id,
        applicability_id,
        model_reference,
        member,
        released,
        file_evidence,
        revision,
        revision_detail,
        collection,
    ) = replay_context(administrator, base_url)
    revision_id = str(revision["globalId"])
    revision_snapshot_hash = str(revision["snapshotHash"])
    plan_one_item, plan_two_item = collection["items"]
    plan_one = plan_one_item["plan"]
    observation_one, observation_two = plan_one_item["observations"]
    commands = (
        (
            "revision",
            predecessor.revision_path(project_id, master_id),
            design_revision_payload(applicability_id, model_reference, released),
            REVISION_THREE_KEY,
            revision_detail,
        ),
        (
            "manufacturing",
            manufacturing_path(project_id, master_id),
            plan_payload(
                revision_id,
                revision_snapshot_hash,
                member,
                released,
                version=1,
            ),
            PLAN_ONE_KEY,
            {
                "plan": plan_one_item["plan"],
                "designReleaseEvidence": plan_one_item["designReleaseEvidence"],
            },
        ),
        (
            "manufacturing",
            manufacturing_path(
                project_id,
                master_id,
                f"/{plan_one['globalId']}/milestones/"
                f"{SUPPLIER_MILESTONE_ID}/observations",
            ),
            observation_payload(plan_one, file_evidence, version=1),
            OBSERVATION_ONE_KEY,
            {"observation": observation_one},
        ),
        (
            "manufacturing",
            manufacturing_path(
                project_id,
                master_id,
                f"/{plan_one['globalId']}/milestones/"
                f"{SUPPLIER_MILESTONE_ID}/observations",
            ),
            observation_payload(plan_one, file_evidence, version=2),
            OBSERVATION_TWO_KEY,
            {"observation": observation_two},
        ),
        (
            "manufacturing",
            manufacturing_path(project_id, master_id),
            plan_payload(
                revision_id,
                revision_snapshot_hash,
                member,
                released,
                version=2,
            ),
            PLAN_TWO_KEY,
            {
                "plan": plan_two_item["plan"],
                "designReleaseEvidence": plan_two_item["designReleaseEvidence"],
            },
        ),
    )
    before = persisted_counts(administrator, base_url, project_id)
    for kind, path, payload, key, exact_body in commands:
        replay = (
            predecessor.command(
                administrator,
                base_url,
                csrf_token,
                path,
                payload,
                key,
            )
            if kind == "revision"
            else command(
                administrator,
                base_url,
                csrf_token,
                path,
                payload,
                key,
            )
        )
        require(
            replay.headers.get("Idempotency-Replayed") == "true",
            f"P6-04 cross-process replay was not declared for {key}",
        )
        require(replay.body == exact_body, f"P6-04 replay response drifted for {key}")
    require(
        persisted_counts(administrator, base_url, project_id) == before,
        "P6-04 cross-process replay changed immutable cardinality",
    )


def route_disable_probe(administrator, base_url: str, expected_mode: str) -> None:
    project_id, master_id, _applicability_id, _model_reference = project_context(
        administrator,
        base_url,
    )
    manufacturing = tooling_request(
        administrator,
        base_url,
        manufacturing_path(project_id, master_id),
        query_key=f"route-{expected_mode}",
    )
    revisions = tooling_request(
        administrator,
        base_url,
        predecessor.revision_path(project_id, master_id),
        query_key=f"revisions-{expected_mode}",
    )
    cockpit = tooling_request(
        administrator,
        base_url,
        predecessor.predecessor.tooling_path(project_id),
        query_key=f"cockpit-{expected_mode}",
    )
    require(
        revisions.status == 200
        and len(revisions.body.get("items", [])) == 3
        and cockpit.status == 200,
        "P6-04 switch changed predecessor Tooling routes",
    )
    if expected_mode == "disabled":
        validate_problem(
            manufacturing,
            503,
            "TOOLING_MANUFACTURING_ROUTES_DISABLED",
        )
        return
    member = active_member(administrator, base_url, project_id)
    released = released_document(administrator, base_url, project_id)
    assert_context(
        manufacturing,
        project_id=project_id,
        master_id=master_id,
        member=member,
        released=released,
        tooling_revision_id=str(revisions.body["items"][2]["globalId"]),
        expected_count=2,
    )


def verify_tooling_manufacturing_runtime_schema(
    fixture_run_id: str,
) -> dict[str, object]:
    import frappe

    document_runtime._validated_runtime_site()
    require(fixture_run_id == FIXTURE_RUN_ID, "P6-04 schema fixture namespace drifted")
    required_fields = {
        "NPI Tooling Manufacturing Plan Revision": {
            "global_id",
            "plan_global_id",
            "version_key_hash",
            "tooling_revision_global_id",
            "plan_version",
            "predecessor_global_id",
            "plan_snapshot",
            "snapshot_hash",
        },
        "NPI Tooling Manufacturing Milestone Observation": {
            "global_id",
            "observation_key_hash",
            "plan_revision_global_id",
            "milestone_global_id",
            "observation_version",
            "predecessor_global_id",
            "observation_snapshot",
            "snapshot_hash",
        },
    }
    for doctype in MANUFACTURING_DOCTYPES:
        require(frappe.db.table_exists(doctype), f"P6-04 table is unavailable: {doctype}")
        fields = {
            field.fieldname for field in frappe.get_meta(doctype, cached=False).fields
        }
        require(
            required_fields[doctype] <= fields,
            f"P6-04 metadata is incomplete for {doctype}",
        )
    return {
        "doctypeCount": len(MANUFACTURING_DOCTYPES),
        "fixtureRunId": fixture_run_id,
        "metadataSynchronized": True,
        "runtimeMarker": RUNTIME_MARKER,
    }


def run_bench_fixture(method: str, kwargs: dict[str, object]) -> dict[str, Any]:
    require(
        method == "verify_tooling_manufacturing_runtime_schema",
        "P6-04 Bench fixture is unavailable",
    )
    require(
        BENCH_PATH.is_dir()
        and not BENCH_PATH.is_symlink()
        and BENCH_PATH.resolve() == BENCH_PATH,
        "P6-04 verifier requires the fixed physical Bench",
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
            str(ROOT / "scripts" / "verify_tooling_manufacturing_runtime.py"),
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
    require(completed.returncode == 0, f"P6-04 Bench fixture failed: {method}")
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    require(bool(lines), f"P6-04 Bench fixture was silent: {method}")
    result = json.loads(lines[-1])
    require(isinstance(result, dict), "P6-04 Bench fixture result is invalid")
    return result


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    require(
        method == "verify_tooling_manufacturing_runtime_schema",
        "P6-04 Bench fixture is unavailable",
    )
    import frappe

    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    try:
        frappe.set_user(ACTOR_USER)
        result = verify_tooling_manufacturing_runtime_schema(**kwargs)
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the real cumulative P6-04 Tooling manufacturing runtime.",
    )
    parser.add_argument("--base-url")
    parser.add_argument(
        "--bench-fixture",
        choices=("verify_tooling_manufacturing_runtime_schema",),
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
            "P6-04 Bench fixture arguments are invalid",
        )
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "P6-04 fixture kwargs are invalid")
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return
    require(
        isinstance(arguments.base_url, str)
        and arguments.fixture_kwargs is None
        and document_runtime.CALLER_SUPPLIED_FIXTURE_RUN_ID is not None,
        "P6-04 runtime base URL and fixture namespace are required",
    )
    administrator_password = secret_from_environment(
        "NPI_RUNTIME_ADMINISTRATOR_PASSWORD"
    )
    fixture_password = secret_from_environment("NPI_RUNTIME_FIXTURE_PASSWORD")
    base_url = validate_local_fixture_inputs(
        arguments.base_url,
        ADMINISTRATOR_USER,
        UNRELATED_USER,
    )
    require(
        FIXTURE_RUN_ID != "0" * 32
        and ACTOR_USER.endswith("@example.invalid")
        and UNRELATED_USER.endswith("@example.invalid"),
        "P6-04 fixture identity drifted",
    )
    require(
        int(arguments.route_disable_probe is not None)
        + int(arguments.replay_only)
        <= 1,
        "P6-04 runtime modes are mutually exclusive",
    )
    if arguments.route_disable_probe is None and not arguments.replay_only:
        administrator = login(
            base_url,
            ADMINISTRATOR_USER,
            administrator_password,
        )
        administrator_csrf = bootstrap_csrf(
            administrator,
            base_url,
            ADMINISTRATOR_USER,
        )
        actor, csrf_token = prepare_manufacturing_actor(
            administrator,
            base_url,
            administrator_csrf,
            fixture_password,
        )
    else:
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
        print("local Frappe Tooling manufacturing runtime replay verification passed")
        return
    evidence = run_fresh(
        actor,
        base_url,
        csrf_token,
        fixture_password,
    )
    print(json.dumps(evidence, sort_keys=True))
    print("local Frappe Tooling manufacturing runtime verification passed")


if __name__ == "__main__":
    main()
