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
UNRELATED_USER = f"npi-trial-{FIXTURE_RUN_ID[:20]}-unrelated@example.invalid"
ABSENT_PROJECT_ID = "00000000-0000-4000-8000-000000000701"
ABSENT_PLAN_ID = "00000000-0000-4000-8000-000000000702"

CREATE_KEY = f"p7-01-runtime-{FIXTURE_RUN_ID}-create"
REVISE_KEY = f"p7-01-runtime-{FIXTURE_RUN_ID}-revise"
STALE_REVISE_KEY = f"p7-01-runtime-{FIXTURE_RUN_ID}-stale-revise"
ROUND_KEY = f"p7-01-runtime-{FIXTURE_RUN_ID}-round"
ROUND_CONFLICT_KEY = f"p7-01-runtime-{FIXTURE_RUN_ID}-round-conflict"
ACTION_KEY = f"p7-01-runtime-{FIXTURE_RUN_ID}-actions"

TRIAL_DOCTYPES = (
    "NPI Trial Plan Revision",
    "NPI Trial Round",
    "NPI Trial Round Lifecycle Event",
    "NPI Trial Plan Work Link",
    "NPI Trial Command Idempotency",
)
TRIAL_PROTECTED_FIELDS = {
    "NPI Trial Plan Revision": "snapshot_hash",
    "NPI Trial Round": "snapshot_hash",
    "NPI Trial Round Lifecycle Event": "snapshot_hash",
    "NPI Trial Plan Work Link": "snapshot_hash",
    "NPI Trial Command Idempotency": "payload_hash",
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


def trial_path(project_id: str, suffix: str = "") -> str:
    return f"/api/npi/v1/projects/{project_id}/trials{suffix}"


def plan_path(project_id: str, plan_id: str, suffix: str = "") -> str:
    return f"/api/npi/v1/projects/{project_id}/trial-plans/{plan_id}{suffix}"


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
    require(result.status == 201, f"P7-01 command returned HTTP {result.status}")
    require(
        result.headers.get("Idempotency-Replayed") in {"true", "false"},
        "P7-01 replay response header drifted",
    )
    return result


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


def round_payload(successor: dict[str, Any]) -> dict[str, object]:
    return {
        "expectedPlanRevisionGlobalId": successor["globalId"],
        "expectedPlanRevisionSnapshotHash": successor["snapshotHash"],
        "displayLabel": "T0",
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
    verify_idor(
        administrator,
        base_url,
        csrf_token,
        fixture_password,
        project_id,
        plan_id,
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
        and final_counts["NPI Trial Round"] == 1
        and final_counts["NPI Trial Round Lifecycle Event"] == 1
        and final_counts["NPI Trial Plan Work Link"] == 1
        and final_counts["NPI Trial Command Idempotency"] == 4
        and all(
            final_counts[f"audit:{operation}"] == 1
            for operation in (
                "trial_plan.create",
                "trial_plan.revise",
                "trial_round.create",
                "trial_plan.generate_actions",
            )
        ),
        "P7-01 controlled persistence cardinality drifted",
    )
    require(
        (final_counts["outbox"], final_counts["inbox"]) == integration_before,
        "P7-01 controlled Trial planning created ERP integration traffic",
    )
    return {
        "actionLinkCount": 1,
        "crossProcessReplayReady": True,
        "doctypeCount": schema["doctypeCount"],
        "fixtureRunId": FIXTURE_RUN_ID,
        "integrationTrafficCreated": False,
        "metadataSynchronized": schema["metadataSynchronized"],
        "planRevisionCount": 2,
        "plannedRoundCount": 1,
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
        rounds=1,
        links=1,
    )
    return project_id, plan_id, detail


def run_replay(administrator, base_url: str, csrf_token: str) -> None:
    project_id, plan_id, detail = retained_detail(administrator, base_url)
    master_id = str(detail["latestRevision"]["toolingMasterGlobalId"])
    initial, successor = detail["revisions"]
    round_id = str(exact_single(detail["rounds"], "replay Round")["globalId"])
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
    after = persisted_counts(administrator, base_url, project_id)
    require(
        after == before,
        "P7-01 cross-process replay changed immutable cardinality or integration truth",
    )


def route_disable_probe(administrator, base_url: str, *, expected_mode: str) -> None:
    project_id, _version = document_runtime.fixture_project(administrator, base_url)
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
    if expected_mode == "disabled":
        validate_problem(trials, 503, "TRIAL_ROUTES_DISABLED")
        return
    require(expected_mode == "recovered", "P7-01 route probe mode drifted")
    assert_workspace(trials, project_id, expected_plans=1)


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
    }
    for doctype in TRIAL_DOCTYPES:
        require(frappe.db.table_exists(doctype), f"P7-01 table is unavailable: {doctype}")
        fields = {
            field.fieldname for field in frappe.get_meta(doctype, cached=False).fields
        }
        require(
            required_fields[doctype] <= fields,
            f"P7-01 metadata is incomplete for {doctype}",
        )
    return {
        "doctypeCount": len(TRIAL_DOCTYPES),
        "fixtureRunId": fixture_run_id,
        "metadataSynchronized": True,
        "runtimeMarker": RUNTIME_MARKER,
    }


BENCH_FIXTURES = {
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
        description="Verify the cumulative controlled P7-01 Trial planning runtime.",
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
        "P7-01 runtime base URL and fixture namespace are required",
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
        and RESPONSIBLE_MEMBER_ID == document_runtime.BASELINE_MEMBER_ID,
        "P7-01 fixture identity drifted",
    )
    administrator = login(base_url, ACTOR_USER, administrator_password)
    csrf_token = bootstrap_csrf(administrator, base_url, ACTOR_USER)
    require(
        int(arguments.route_disable_probe is not None)
        + int(arguments.replay_only)
        <= 1,
        "P7-01 runtime modes are mutually exclusive",
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
        print("local Frappe Trial runtime replay verification passed")
        return
    evidence = run_fresh(
        administrator,
        base_url,
        csrf_token,
        fixture_password,
    )
    print(json.dumps(evidence, sort_keys=True))
    print("local Frappe Trial runtime verification passed")


if __name__ == "__main__":
    main()
