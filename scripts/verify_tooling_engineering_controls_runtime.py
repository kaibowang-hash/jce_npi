from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import verify_document_runtime as document_runtime
import verify_tooling_manufacturing_runtime as predecessor
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
UNRELATED_USER = f"npi-tooling-controls-{FIXTURE_RUN_ID[:12]}-unrelated@example.invalid"

DEFECT_ONE_KEY = f"p6-05-runtime-r1-{FIXTURE_RUN_ID}-defect-one"
DEFECT_TWO_KEY = f"p6-05-runtime-r1-{FIXTURE_RUN_ID}-defect-two"
DEFECT_STALE_KEY = f"p6-05-runtime-r1-{FIXTURE_RUN_ID}-defect-stale"
PROFILE_ONE_KEY = f"p6-05-runtime-r1-{FIXTURE_RUN_ID}-profile-one"
PROFILE_TWO_KEY = f"p6-05-runtime-r1-{FIXTURE_RUN_ID}-profile-two"
PROFILE_REFERENCE_KEY = f"p6-05-runtime-r1-{FIXTURE_RUN_ID}-profile-reference"
CAPACITY_ONE_KEY = f"p6-05-runtime-r1-{FIXTURE_RUN_ID}-capacity-one"
CAPACITY_TWO_KEY = f"p6-05-runtime-r1-{FIXTURE_RUN_ID}-capacity-two"
CAPACITY_STALE_KEY = f"p6-05-runtime-r1-{FIXTURE_RUN_ID}-capacity-stale"

ABSENT_PROJECT_ID = "00000000-0000-4000-8000-000000000001"
ENGINEERING_CONTROL_DOCTYPES = (
    "NPI Tooling Defect Revision",
    "NPI Tooling Process Profile Revision",
    "NPI Tooling Capacity Scenario Revision",
)
ENGINEERING_CONTROL_PERMISSIONS = {
    "view": True,
    "reviseDefect": True,
    "createCustomerStandard": True,
    "createCapacityScenario": True,
    "createTrialActual": False,
    "approveProcessBaseline": False,
    "editHealth": False,
    "transitionGate": False,
    "transitionToolingLifecycle": False,
}


def engineering_path(project_id: str, master_id: str, suffix: str = "") -> str:
    return (
        f"/api/npi/v1/projects/{project_id}/tooling/{master_id}/"
        f"engineering-controls{suffix}"
    )


def engineering_command_path(project_id: str, master_id: str, suffix: str) -> str:
    return f"/api/npi/v1/projects/{project_id}/tooling/{master_id}{suffix}"


def tooling_request(*args, query_key: str = "query", **kwargs):
    return predecessor.tooling_request(
        *args,
        query_key=f"p605-{query_key}",
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
            f"P6-05 command {key} returned HTTP {result.status} with problem code "
            f"{result.body.get('code', 'UNAVAILABLE')}"
        ),
    )
    require(
        result.headers.get("Idempotency-Replayed") in {"true", "false"},
        "P6-05 replay header is invalid",
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


def rows(administrator, base_url: str, doctype: str, filters, fields=None):
    return predecessor.predecessor.predecessor.rows(
        administrator,
        base_url,
        doctype,
        filters,
        fields,
    )


def exact_single(values, label: str):
    return predecessor.predecessor.predecessor.exact_single(values, label)


def project_context(administrator, base_url: str) -> dict[str, object]:
    (
        project_id,
        master_id,
        _applicability_id,
        _model_reference,
        member,
        _released,
        file_evidence,
        revision,
        _revision_detail,
        _manufacturing,
    ) = predecessor.replay_context(administrator, base_url)
    revision_id = require_uuid(revision.get("globalId"), "P6-05 Tooling Revision")
    revision_snapshot_hash = require_hash(
        revision.get("snapshotHash"),
        "P6-05 Tooling Revision",
    )
    revision_context = predecessor.predecessor.project_context(administrator, base_url)
    tooling_set_id = require_uuid(revision_context[4], "P6-05 Tooling Set")
    tooling_set = exact_single(
        rows(
            administrator,
            base_url,
            "NPI Tooling Set",
            [["global_id", "=", tooling_set_id]],
            ["global_id", "snapshot_hash"],
        ),
        "P6-05 Tooling Set",
    )
    tooling_set_snapshot_hash = require_hash(
        tooling_set.get("snapshot_hash"),
        "P6-05 Tooling Set",
    )
    applicability_rows = rows(
        administrator,
        base_url,
        "NPI Tooling Applicability",
        [
            ["project_global_id", "=", project_id],
            ["tooling_master_global_id", "=", master_id],
            ["effective_to", "is", "not set"],
        ],
        [
            "global_id",
            "part_revision_global_id",
            "snapshot_hash",
            "effective_to",
        ],
    )
    require(bool(applicability_rows), "P6-05 active Tooling applicability is unavailable")
    applicability = []
    for item in sorted(applicability_rows, key=lambda value: str(value.get("global_id")))[:2]:
        applicability_id = require_uuid(
            item.get("global_id"),
            "P6-05 Tooling applicability",
        )
        part_revision_id = require_uuid(
            item.get("part_revision_global_id"),
            "P6-05 Part Revision",
        )
        part_revision = exact_single(
            rows(
                administrator,
                base_url,
                "NPI Engineering Part Revision",
                [["global_id", "=", part_revision_id]],
                ["global_id", "snapshot_hash"],
            ),
            "P6-05 Part Revision",
        )
        applicability.append(
            {
                "globalId": applicability_id,
                "snapshotHash": require_hash(
                    item.get("snapshot_hash"),
                    "P6-05 Tooling applicability",
                ),
                "partRevisionGlobalId": part_revision_id,
                "partRevisionSnapshotHash": require_hash(
                    part_revision.get("snapshot_hash"),
                    "P6-05 Part Revision",
                ),
            }
        )
    return {
        "projectId": project_id,
        "masterId": master_id,
        "member": member,
        "fileEvidence": file_evidence,
        "revisionId": revision_id,
        "revisionSnapshotHash": revision_snapshot_hash,
        "toolingSetId": tooling_set_id,
        "toolingSetSnapshotHash": tooling_set_snapshot_hash,
        "applicability": applicability,
    }


def defect_evidence(context: dict[str, object], role: str) -> dict[str, object]:
    source = context["fileEvidence"]
    require(isinstance(source, dict), "P6-05 retained File evidence is unavailable")
    return {
        "role": role,
        "fileRevisionGlobalId": source["fileRevisionGlobalId"],
        "fileOptimisticVersion": source["fileOptimisticVersion"],
        "frappeContentHash": source["frappeContentHash"],
        "sha256": source["sha256"],
    }


def defect_payload(
    context: dict[str, object],
    *,
    version: int,
    predecessor_value: dict[str, object] | None = None,
) -> dict[str, object]:
    member = context["member"]
    require(isinstance(member, dict), "P6-05 Project member is unavailable")
    action: dict[str, object] = {
        "actionType": "containment",
        "state": "planned" if version == 1 else "completed",
        "detail": "Quarantine all synthetic parts from the affected cavity.",
        "responsibleMember": member,
        "dueDate": "2026-08-20",
        "evidence": [] if version == 1 else [defect_evidence(context, "action")],
    }
    value: dict[str, object] = {
        "toolingRevisionGlobalId": context["revisionId"],
        "toolingRevisionSnapshotHash": context["revisionSnapshotHash"],
        "businessCode": "P6-05-DEF-001",
        "title": "Synthetic gate flash at parting line",
        "description": "Controlled immutable engineering defect observation.",
        "categoryKey": "appearance.flash",
        "severity": "high",
        "blocking": True,
        "state": "open" if version == 1 else "assigned",
        "detectionContext": {
            "kind": "tooling_revision",
            "globalId": context["revisionId"],
            "snapshotHash": context["revisionSnapshotHash"],
        },
        "rootCauseState": "pending" if version == 1 else "recorded",
        "rootCause": None if version == 1 else "Synthetic parting-line fit variation.",
        "responsibleMember": member,
        "targetRoundLabel": "T1",
        "actions": [action],
        "evidence": [defect_evidence(context, "detection" if version == 1 else "analysis")],
        "reason": (
            "Record the initial controlled defect."
            if version == 1
            else "Assign containment and record the exact root cause."
        ),
    }
    if version == 2:
        require(
            isinstance(predecessor_value, dict),
            "P6-05 defect successor requires its predecessor",
        )
        value["defectGlobalId"] = predecessor_value["defectGlobalId"]
        value["expectedVersion"] = 1
        action["globalId"] = predecessor_value["actions"][0]["globalId"]
    return value


def profile_payload(
    context: dict[str, object],
    *,
    version: int,
    predecessor_value: dict[str, object] | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "toolingRevisionGlobalId": context["revisionId"],
        "toolingRevisionSnapshotHash": context["revisionSnapshotHash"],
        "context": {
            "kind": "tooling_revision_specification",
            "globalId": context["revisionId"],
            "snapshotHash": context["revisionSnapshotHash"],
        },
        "effectiveFrom": "2026-08-20" if version == 1 else "2026-08-21",
        "metrics": [
            {
                "code": "cycle_time",
                "valueKind": "numeric",
                "numericValue": "42.0" if version == 1 else "36.0",
                "textValue": None,
                "unit": "s",
                "comparisonRule": {
                    "unit": "s",
                    "minimum": "34.0",
                    "maximum": "44.0",
                },
            },
            {
                "code": "machine_type",
                "valueKind": "text",
                "numericValue": None,
                "textValue": "Synthetic 450 t injection molding machine",
                "unit": None,
                "comparisonRule": None,
            },
        ],
        "reason": (
            "Record the initial Customer Standard profile."
            if version == 1
            else "Append the revised Customer Standard cycle target."
        ),
    }
    if version == 2:
        require(
            isinstance(predecessor_value, dict),
            "P6-05 process successor requires its predecessor",
        )
        value["profileGlobalId"] = predecessor_value["profileGlobalId"]
        value["expectedVersion"] = 1
    return value


def provenance(kind: str, global_id: object | None, snapshot_hash: object) -> dict[str, object]:
    return {
        "kind": kind,
        "globalId": global_id,
        "snapshotHash": snapshot_hash,
    }


def capacity_payload(
    context: dict[str, object],
    profile: dict[str, object],
    *,
    version: int,
    predecessor_value: dict[str, object] | None = None,
) -> dict[str, object]:
    application_rows = context["applicability"]
    require(
        isinstance(application_rows, list) and bool(application_rows),
        "P6-05 capacity applicability is unavailable",
    )
    lines = []
    for index, application in enumerate(application_rows):
        require(isinstance(application, dict), "P6-05 capacity applicability drifted")
        base_cycle = Decimal("42") + Decimal(index * 18)
        cycle = base_cycle - (Decimal("6") if version == 2 else Decimal("0"))
        lines.append(
            {
                "partRevisionGlobalId": application["partRevisionGlobalId"],
                "partRevisionSnapshotHash": application["partRevisionSnapshotHash"],
                "applicabilityGlobalId": application["globalId"],
                "applicabilitySnapshotHash": application["snapshotHash"],
                "availableHoursPerDay": "20.0",
                "workingDaysPerMonth": 26,
                "oeeRatio": "0.85",
                "yieldRatio": "0.98",
                "cycleSeconds": str(cycle),
                "cavityCount": 1,
                "usagePerAssembly": "1.0",
                "effectiveSetCount": 1,
                "selectedToolingSetGlobalIds": [context["toolingSetId"]],
                "cycleProvenance": provenance(
                    "customer_standard",
                    profile["globalId"],
                    profile["snapshotHash"],
                ),
                "cavityProvenance": provenance(
                    "tooling_revision",
                    context["revisionId"],
                    context["revisionSnapshotHash"],
                ),
                "usageProvenance": provenance(
                    "tooling_applicability",
                    application["globalId"],
                    application["snapshotHash"],
                ),
                "setProvenance": provenance(
                    "tooling_set_selection",
                    context["toolingSetId"],
                    context["toolingSetSnapshotHash"],
                ),
            }
        )
    value: dict[str, object] = {
        "title": "Synthetic nominal monthly capacity",
        "effectiveFrom": "2026-08-21" if version == 1 else "2026-08-22",
        "targetMonthlyAssemblyUnits": "100000.0",
        "lines": lines,
        "reason": (
            "Record the initial controlled Capacity Scenario."
            if version == 1
            else "Recompute capacity after the controlled cycle revision."
        ),
    }
    if version == 2:
        require(
            isinstance(predecessor_value, dict),
            "P6-05 capacity successor requires its predecessor",
        )
        value["scenarioGlobalId"] = predecessor_value["scenarioGlobalId"]
        value["expectedVersion"] = 1
    return value


def persisted_counts(administrator, base_url: str, project_id: str) -> dict[str, int]:
    return {
        doctype: len(
            rows(
                administrator,
                base_url,
                doctype,
                [["project_global_id", "=", project_id]],
            )
        )
        for doctype in ENGINEERING_CONTROL_DOCTYPES
    }


def assert_engineering_context(
    result,
    *,
    context: dict[str, object],
    expected_count: int,
) -> dict[str, object]:
    require(result.status == 200, "P6-05 engineering-controls query failed")
    value = result.body
    require(
        set(value)
        == {
            "projectGlobalId",
            "toolingMasterGlobalId",
            "permissions",
            "defectRevisions",
            "process",
            "capacityScenarioRevisions",
            "health",
        }
        and value.get("projectGlobalId") == context["projectId"]
        and value.get("toolingMasterGlobalId") == context["masterId"]
        and value.get("permissions") == ENGINEERING_CONTROL_PERMISSIONS,
        "P6-05 engineering-controls envelope drifted",
    )
    defects = value.get("defectRevisions")
    process = value.get("process")
    scenarios = value.get("capacityScenarioRevisions")
    require(
        isinstance(defects, list)
        and len(defects) == expected_count
        and isinstance(process, dict)
        and isinstance(scenarios, list)
        and len(scenarios) == expected_count,
        "P6-05 engineering-control collection cardinality drifted",
    )
    require(
        set(process)
        == {
            "customerStandardRevisions",
            "trialActual",
            "approvedBaseline",
            "comparisons",
        }
        and len(process["customerStandardRevisions"]) == expected_count
        and process["trialActual"]
        == {"state": "not_measured", "reasonCode": "trial_context_unavailable"}
        and process["approvedBaseline"]
        == {
            "state": "unavailable",
            "reasonCode": "approved_trial_evidence_unavailable",
        },
        "P6-05 Customer Standard, Trial Actual, and approved baseline separation drifted",
    )
    health = value.get("health")
    require(
        isinstance(health, dict)
        and health.get("sourceSystem") == "ERPNEXT"
        and health.get("editableIn") == "ERPNEXT"
        and health.get("state") == "unavailable"
        and health.get("healthScore", {}).get("reasonCode")
        == "tooling_health_policy_unavailable",
        "P6-05 ERP-owned health unavailable truth drifted",
    )
    return value


def assert_successors(value: dict[str, object]) -> None:
    defect_one, defect_two = value["defectRevisions"]
    require(
        defect_one.get("defectVersion") == 1
        and defect_one.get("state") == "open"
        and defect_one.get("blocking") is True
        and len(defect_one.get("evidence", [])) == 1
        and defect_two.get("defectVersion") == 2
        and defect_two.get("predecessorGlobalId") == defect_one.get("globalId")
        and defect_two.get("predecessorSnapshotHash") == defect_one.get("snapshotHash")
        and defect_two.get("state") == "assigned"
        and defect_two.get("blocking") is True
        and defect_two.get("rootCauseState") == "recorded"
        and len(defect_two.get("evidence", [])) == 2
        and defect_two.get("actions", [])[0].get("globalId")
        == defect_one.get("actions", [])[0].get("globalId")
        and defect_two.get("actions", [])[0].get("state") == "completed"
        and len(defect_two.get("actions", [])[0].get("evidence", [])) == 1,
        "P6-05 immutable defect succession, action, evidence, or blocking truth drifted",
    )
    process = value["process"]
    profile_one, profile_two = process["customerStandardRevisions"]
    require(
        profile_one.get("layer") == "customer_standard"
        and profile_one.get("profileVersion") == 1
        and profile_two.get("profileVersion") == 2
        and profile_two.get("predecessorGlobalId") == profile_one.get("globalId")
        and profile_two.get("predecessorSnapshotHash") == profile_one.get("snapshotHash")
        and profile_two.get("metrics", [])[0].get("globalId")
        == profile_one.get("metrics", [])[0].get("globalId")
        and all(
            item.get("state") == "not_measured"
            and item.get("referenceLayer") == "customer_standard"
            and item.get("actualValue") is None
            for item in process.get("comparisons", [])
        ),
        "P6-05 Customer Standard successor or absent Trial comparison drifted",
    )
    scenario_one, scenario_two = value["capacityScenarioRevisions"]
    first_result = scenario_one.get("result", {})
    second_result = scenario_two.get("result", {})
    first_lines = first_result.get("lineResults", [])
    second_lines = second_result.get("lineResults", [])
    require(
        scenario_one.get("scenarioVersion") == 1
        and scenario_two.get("scenarioVersion") == 2
        and scenario_two.get("predecessorGlobalId") == scenario_one.get("globalId")
        and scenario_two.get("predecessorSnapshotHash") == scenario_one.get("snapshotHash")
        and first_result.get("formulaVersion") == "capacity.v1"
        and second_result.get("roundingRule") == "decimal-6-half-even"
        and len(first_lines) == len(second_lines) >= 1
        and [item.get("globalId") for item in second_lines]
        == [item.get("globalId") for item in first_lines]
        and Decimal(second_result["scenarioAssemblyUnitsPerMonth"])
        > Decimal(first_result["scenarioAssemblyUnitsPerMonth"])
        and Decimal(second_result["gap"]) < Decimal(first_result["gap"])
        and second_result.get("bottleneckLineGlobalIds")
        == [
            min(
                second_lines,
                key=lambda item: Decimal(item["assemblyUnitsPerMonth"]),
            )["globalId"]
        ],
        "P6-05 Capacity Scenario recomputation, bottleneck, or gap drifted",
    )


def verify_persistence(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    project_id: str,
    values: dict[str, object],
) -> None:
    require(
        persisted_counts(administrator, base_url, project_id)
        == {doctype: 2 for doctype in ENGINEERING_CONTROL_DOCTYPES},
        "P6-05 persisted immutable cardinality drifted",
    )
    for operation in (
        "tooling_defect.revise",
        "tooling_process_profile.create",
        "tooling_capacity_scenario.create",
    ):
        receipts = rows(
            administrator,
            base_url,
            "NPI Tooling Command Idempotency",
            [["operation", "=", operation]],
            ["actor_user_id", "payload_hash", "response_hash", "sealed"],
        )
        audits = rows(
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
            f"P6-05 receipt or audit truth drifted for {operation}",
        )
    immutable = (
        ("NPI Tooling Defect Revision", values["defectRevisions"]),
        (
            "NPI Tooling Process Profile Revision",
            values["process"]["customerStandardRevisions"],
        ),
        ("NPI Tooling Capacity Scenario Revision", values["capacityScenarioRevisions"]),
    )
    for doctype, records in immutable:
        for record in records:
            name = record["globalId"]
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
                and after.status == 200
                and after.body.get("data", {}).get("snapshot_hash") == snapshot_hash,
                f"P6-05 immutable {doctype} accepted generic mutation",
            )


def verify_idor(
    administrator,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
    *,
    context: dict[str, object],
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
        unrelated_csrf = bootstrap_csrf(
            unrelated,
            base_url,
            UNRELATED_USER,
        )
        denied = tooling_request(
            unrelated,
            base_url,
            engineering_path(str(context["projectId"]), str(context["masterId"])),
            query_key="idor-denied",
        )
        absent = tooling_request(
            unrelated,
            base_url,
            engineering_path(ABSENT_PROJECT_ID, str(context["masterId"])),
            query_key="idor-absent",
        )
        validate_problem(denied, 404, "TOOLING_UNAVAILABLE")
        validate_problem(absent, 404, "TOOLING_UNAVAILABLE")
        fields = ("type", "title", "status", "code", "retryable")
        require(
            {key: denied.body.get(key) for key in fields}
            == {key: absent.body.get(key) for key in fields},
            "P6-05 unauthorized and absent Projects are distinguishable",
        )
        command_key = f"p6-05-runtime-r1-{FIXTURE_RUN_ID}-idor-command"
        denied_command = tooling_request(
            unrelated,
            base_url,
            engineering_command_path(
                str(context["projectId"]),
                str(context["masterId"]),
                "/defect-revisions",
            ),
            method="POST",
            payload={"doctype": "Secret"},
            csrf_token=unrelated_csrf,
            idempotency_key=command_key,
            query_key="idor-command-denied",
        )
        absent_command = tooling_request(
            unrelated,
            base_url,
            engineering_command_path(
                ABSENT_PROJECT_ID,
                str(context["masterId"]),
                "/defect-revisions",
            ),
            method="POST",
            payload={"doctype": "Secret"},
            csrf_token=unrelated_csrf,
            idempotency_key=command_key,
            query_key="idor-command-absent",
        )
        validate_problem(denied_command, 404, "TOOLING_UNAVAILABLE")
        validate_problem(absent_command, 404, "TOOLING_UNAVAILABLE")
        require(
            {key: denied_command.body.get(key) for key in fields}
            == {key: absent_command.body.get(key) for key in fields},
            "P6-05 unauthorized and absent command scopes are distinguishable",
        )
    finally:
        delete_disposable_user(
            administrator,
            base_url,
            UNRELATED_USER,
            csrf_token,
        )


def verify_conflict_rollback(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    context: dict[str, object],
    defect_one: dict[str, object],
    defect_two: dict[str, object],
    profile_two: dict[str, object],
    scenario_two: dict[str, object],
) -> None:
    before = persisted_counts(administrator, base_url, str(context["projectId"]))
    different = defect_payload(context, version=1)
    different["title"] = "A different payload for the same idempotency key"
    conflicts = (
        (
            engineering_command_path(
                str(context["projectId"]),
                str(context["masterId"]),
                "/defect-revisions",
            ),
            different,
            DEFECT_ONE_KEY,
            409,
            "TOOLING_IDEMPOTENCY_CONFLICT",
        ),
        (
            engineering_command_path(
                str(context["projectId"]),
                str(context["masterId"]),
                "/defect-revisions",
            ),
            defect_payload(context, version=2, predecessor_value=defect_one),
            DEFECT_STALE_KEY,
            409,
            "TOOLING_VERSION_CONFLICT",
        ),
        (
            engineering_command_path(
                str(context["projectId"]),
                str(context["masterId"]),
                "/process-profile-revisions",
            ),
            {
                **profile_payload(context, version=2, predecessor_value=profile_two),
                "expectedVersion": 2,
                "toolingRevisionSnapshotHash": "0" * 64,
            },
            PROFILE_REFERENCE_KEY,
            404,
            "TOOLING_REFERENCE_UNAVAILABLE",
        ),
        (
            engineering_command_path(
                str(context["projectId"]),
                str(context["masterId"]),
                "/capacity-scenario-revisions",
            ),
            capacity_payload(
                context,
                profile_two,
                version=2,
                predecessor_value=scenario_two,
            ),
            CAPACITY_STALE_KEY,
            409,
            "TOOLING_VERSION_CONFLICT",
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
        persisted_counts(administrator, base_url, str(context["projectId"])) == before,
        "P6-05 failed commands changed immutable cardinality",
    )
    require(defect_two.get("defectVersion") == 2, "P6-05 defect context drifted")


def run_fresh(
    administrator,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
) -> dict[str, object]:
    context = project_context(administrator, base_url)
    schema = run_bench_fixture(
        "verify_tooling_engineering_controls_runtime_schema",
        {"fixture_run_id": FIXTURE_RUN_ID},
    )
    path = engineering_path(str(context["projectId"]), str(context["masterId"]))
    defect_path = engineering_command_path(
        str(context["projectId"]),
        str(context["masterId"]),
        "/defect-revisions",
    )
    profile_path = engineering_command_path(
        str(context["projectId"]),
        str(context["masterId"]),
        "/process-profile-revisions",
    )
    capacity_path = engineering_command_path(
        str(context["projectId"]),
        str(context["masterId"]),
        "/capacity-scenario-revisions",
    )
    empty = assert_engineering_context(
        tooling_request(administrator, base_url, path, query_key="empty-controls"),
        context=context,
        expected_count=0,
    )
    require(
        empty["defectRevisions"] == []
        and empty["process"]["customerStandardRevisions"] == []
        and empty["capacityScenarioRevisions"] == [],
        "P6-05 fresh engineering-controls context was not empty",
    )
    guest = tooling_request(
        urllib.request.build_opener(),
        base_url,
        path,
        query_key="guest",
    )
    validate_problem(guest, 401, "AUTHENTICATION_REQUIRED")

    defect_one_payload = defect_payload(context, version=1)
    defect_one_result = command(
        administrator,
        base_url,
        csrf_token,
        defect_path,
        defect_one_payload,
        DEFECT_ONE_KEY,
    )
    defect_one = defect_one_result.body.get("defect")
    require(isinstance(defect_one, dict), "P6-05 first defect response drifted")
    defect_two_payload = defect_payload(
        context,
        version=2,
        predecessor_value=defect_one,
    )
    defect_two_result = command(
        administrator,
        base_url,
        csrf_token,
        defect_path,
        defect_two_payload,
        DEFECT_TWO_KEY,
    )
    defect_two = defect_two_result.body.get("defect")
    require(isinstance(defect_two, dict), "P6-05 defect successor response drifted")

    profile_one_payload = profile_payload(context, version=1)
    profile_one_result = command(
        administrator,
        base_url,
        csrf_token,
        profile_path,
        profile_one_payload,
        PROFILE_ONE_KEY,
    )
    profile_one = profile_one_result.body.get("profile")
    require(isinstance(profile_one, dict), "P6-05 first profile response drifted")
    profile_two_payload = profile_payload(
        context,
        version=2,
        predecessor_value=profile_one,
    )
    profile_two_result = command(
        administrator,
        base_url,
        csrf_token,
        profile_path,
        profile_two_payload,
        PROFILE_TWO_KEY,
    )
    profile_two = profile_two_result.body.get("profile")
    require(isinstance(profile_two, dict), "P6-05 profile successor response drifted")

    capacity_one_payload = capacity_payload(context, profile_two, version=1)
    capacity_one_result = command(
        administrator,
        base_url,
        csrf_token,
        capacity_path,
        capacity_one_payload,
        CAPACITY_ONE_KEY,
    )
    capacity_one = capacity_one_result.body.get("scenario")
    require(isinstance(capacity_one, dict), "P6-05 first capacity response drifted")
    capacity_two_payload = capacity_payload(
        context,
        profile_two,
        version=2,
        predecessor_value=capacity_one,
    )
    capacity_two_result = command(
        administrator,
        base_url,
        csrf_token,
        capacity_path,
        capacity_two_payload,
        CAPACITY_TWO_KEY,
    )
    capacity_two = capacity_two_result.body.get("scenario")
    require(isinstance(capacity_two, dict), "P6-05 capacity successor response drifted")

    retained = assert_engineering_context(
        tooling_request(administrator, base_url, path, query_key="retained-controls"),
        context=context,
        expected_count=2,
    )
    assert_successors(retained)
    verify_idor(
        administrator,
        base_url,
        csrf_token,
        fixture_password,
        context=context,
    )
    verify_persistence(
        administrator,
        base_url,
        csrf_token,
        project_id=str(context["projectId"]),
        values=retained,
    )
    verify_conflict_rollback(
        administrator,
        base_url,
        csrf_token,
        context=context,
        defect_one=defect_one,
        defect_two=defect_two,
        profile_two=profile_two,
        scenario_two=capacity_two,
    )
    return {
        "capacityScenarioRevisionCount": 2,
        "defectRevisionCount": 2,
        "doctypeCount": schema["doctypeCount"],
        "fixtureRunId": FIXTURE_RUN_ID,
        "processProfileRevisionCount": 2,
        "trialActual": "not_measured",
        "approvedBaseline": "unavailable",
    }


def replay_context(administrator, base_url: str):
    context = project_context(administrator, base_url)
    path = engineering_path(str(context["projectId"]), str(context["masterId"]))
    retained = assert_engineering_context(
        tooling_request(administrator, base_url, path, query_key="replay-controls"),
        context=context,
        expected_count=2,
    )
    assert_successors(retained)
    return context, path, retained


def run_replay(administrator, base_url: str, csrf_token: str) -> None:
    context, path, retained = replay_context(administrator, base_url)
    defect_path = engineering_command_path(
        str(context["projectId"]),
        str(context["masterId"]),
        "/defect-revisions",
    )
    profile_path = engineering_command_path(
        str(context["projectId"]),
        str(context["masterId"]),
        "/process-profile-revisions",
    )
    capacity_path = engineering_command_path(
        str(context["projectId"]),
        str(context["masterId"]),
        "/capacity-scenario-revisions",
    )
    defect_one, defect_two = retained["defectRevisions"]
    profile_one, profile_two = retained["process"]["customerStandardRevisions"]
    capacity_one, capacity_two = retained["capacityScenarioRevisions"]
    commands = (
        (
            defect_path,
            defect_payload(context, version=1),
            DEFECT_ONE_KEY,
            {"defect": defect_one},
        ),
        (
            defect_path,
            defect_payload(context, version=2, predecessor_value=defect_one),
            DEFECT_TWO_KEY,
            {"defect": defect_two},
        ),
        (
            profile_path,
            profile_payload(context, version=1),
            PROFILE_ONE_KEY,
            {"profile": profile_one},
        ),
        (
            profile_path,
            profile_payload(context, version=2, predecessor_value=profile_one),
            PROFILE_TWO_KEY,
            {"profile": profile_two},
        ),
        (
            capacity_path,
            capacity_payload(context, profile_two, version=1),
            CAPACITY_ONE_KEY,
            {"scenario": capacity_one},
        ),
        (
            capacity_path,
            capacity_payload(
                context,
                profile_two,
                version=2,
                predecessor_value=capacity_one,
            ),
            CAPACITY_TWO_KEY,
            {"scenario": capacity_two},
        ),
    )
    before = persisted_counts(administrator, base_url, str(context["projectId"]))
    for command_path, payload, key, exact_body in commands:
        replay = command(
            administrator,
            base_url,
            csrf_token,
            command_path,
            payload,
            key,
        )
        require(
            replay.headers.get("Idempotency-Replayed") == "true",
            f"P6-05 cross-process replay was not declared for {key}",
        )
        require(replay.body == exact_body, f"P6-05 replay response drifted for {key}")
    require(
        persisted_counts(administrator, base_url, str(context["projectId"])) == before,
        "P6-05 cross-process replay changed immutable cardinality",
    )


def route_disable_probe(administrator, base_url: str, expected_mode: str) -> None:
    context = project_context(administrator, base_url)
    project_id = str(context["projectId"])
    master_id = str(context["masterId"])
    controls = tooling_request(
        administrator,
        base_url,
        engineering_path(project_id, master_id),
        query_key=f"route-{expected_mode}",
    )
    manufacturing = tooling_request(
        administrator,
        base_url,
        predecessor.manufacturing_path(project_id, master_id),
        query_key=f"manufacturing-{expected_mode}",
    )
    revisions = tooling_request(
        administrator,
        base_url,
        predecessor.predecessor.revision_path(project_id, master_id),
        query_key=f"revisions-{expected_mode}",
    )
    require(
        manufacturing.status == 200
        and len(manufacturing.body.get("items", [])) == 2
        and revisions.status == 200
        and len(revisions.body.get("items", [])) == 3,
        "P6-05 switch changed predecessor Tooling routes",
    )
    if expected_mode == "disabled":
        validate_problem(
            controls,
            503,
            "TOOLING_ENGINEERING_CONTROLS_ROUTES_DISABLED",
        )
        return
    retained = assert_engineering_context(
        controls,
        context=context,
        expected_count=2,
    )
    assert_successors(retained)


def verify_tooling_engineering_controls_runtime_schema(
    fixture_run_id: str,
) -> dict[str, object]:
    import frappe

    document_runtime._validated_runtime_site()
    require(fixture_run_id == FIXTURE_RUN_ID, "P6-05 schema fixture namespace drifted")
    required_fields = {
        "NPI Tooling Defect Revision": {
            "global_id",
            "defect_global_id",
            "version_key_hash",
            "defect_version",
            "predecessor_global_id",
            "defect_snapshot",
            "snapshot_hash",
        },
        "NPI Tooling Process Profile Revision": {
            "global_id",
            "profile_global_id",
            "version_key_hash",
            "layer",
            "profile_version",
            "predecessor_global_id",
            "profile_snapshot",
            "snapshot_hash",
        },
        "NPI Tooling Capacity Scenario Revision": {
            "global_id",
            "scenario_global_id",
            "version_key_hash",
            "scenario_version",
            "predecessor_global_id",
            "input_snapshot",
            "result_snapshot",
            "scenario_snapshot",
            "snapshot_hash",
        },
    }
    for doctype, fields in required_fields.items():
        meta = frappe.get_meta(doctype)
        actual = {field.fieldname for field in meta.fields}
        require(fields.issubset(actual), f"P6-05 {doctype} metadata drifted")
        require(
            int(meta.allow_rename or 0) == 0 and int(meta.is_submittable or 0) == 0,
            f"P6-05 {doctype} mutability metadata drifted",
        )
    return {
        "doctypeCount": len(ENGINEERING_CONTROL_DOCTYPES),
        "fixtureRunId": fixture_run_id,
        "metadataSynchronized": True,
        "runtimeMarker": RUNTIME_MARKER,
    }


def run_bench_fixture(method: str, kwargs: dict[str, object]) -> dict[str, Any]:
    require(
        method == "verify_tooling_engineering_controls_runtime_schema",
        "P6-05 Bench fixture is unavailable",
    )
    require(
        BENCH_PATH.is_dir()
        and not BENCH_PATH.is_symlink()
        and BENCH_PATH.resolve() == BENCH_PATH,
        "P6-05 verifier requires the fixed physical Bench",
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
            str(ROOT / "scripts" / "verify_tooling_engineering_controls_runtime.py"),
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
    require(completed.returncode == 0, f"P6-05 Bench fixture failed: {method}")
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    require(bool(lines), f"P6-05 Bench fixture was silent: {method}")
    result = json.loads(lines[-1])
    require(isinstance(result, dict), "P6-05 Bench fixture result is invalid")
    return result


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    require(
        method == "verify_tooling_engineering_controls_runtime_schema",
        "P6-05 Bench fixture is unavailable",
    )
    import frappe

    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    try:
        frappe.set_user(ACTOR_USER)
        result = verify_tooling_engineering_controls_runtime_schema(**kwargs)
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the real cumulative P6-05 Tooling engineering-controls runtime.",
    )
    parser.add_argument("--base-url")
    parser.add_argument(
        "--bench-fixture",
        choices=("verify_tooling_engineering_controls_runtime_schema",),
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
            "P6-05 Bench fixture arguments are invalid",
        )
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "P6-05 fixture kwargs are invalid")
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return
    require(
        isinstance(arguments.base_url, str)
        and arguments.fixture_kwargs is None
        and document_runtime.CALLER_SUPPLIED_FIXTURE_RUN_ID is not None,
        "P6-05 runtime base URL and fixture namespace are required",
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
        "P6-05 fixture identity drifted",
    )
    require(
        int(arguments.route_disable_probe is not None)
        + int(arguments.replay_only)
        <= 1,
        "P6-05 runtime modes are mutually exclusive",
    )
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
        print("local Frappe Tooling engineering-controls runtime replay verification passed")
        return
    evidence = run_fresh(actor, base_url, csrf_token, fixture_password)
    print(json.dumps(evidence, sort_keys=True))
    print("local Frappe Tooling engineering-controls runtime verification passed")


if __name__ == "__main__":
    main()
