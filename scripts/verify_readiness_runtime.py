from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import verify_document_runtime as document_runtime
import verify_tooling_engineering_controls_runtime as tooling_controls_runtime
import verify_trial_runtime as trial_runtime
from verify_frappe_runtime import (
    HttpResult,
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
SITE_NAME = "npi.localhost"
RUNTIME_MARKER = document_runtime.RUNTIME_MARKER
FIXTURE_RUN_ID = document_runtime.FIXTURE_RUN_ID
TENANT_ID = document_runtime.TENANT_ID
ACTOR_USER = f"npi-readiness-{FIXTURE_RUN_ID[:20]}-manager@example.invalid"
UNRELATED_USER = f"npi-readiness-{FIXTURE_RUN_ID[:20]}-unrelated@example.invalid"
INDUSTRY_KEY = "injection_molding"

INTERNAL_SOURCE_KINDS = (
    "project",
    "domain_work_item",
    "released_document",
    "release_baseline",
    "file_revision",
    "tooling_capacity_scenario",
    "trial_input_lock",
    "trial_actual",
    "trial_sample",
    "trial_cavity_result",
    "trial_defect",
    "trial_defect_verification",
    "trial_comparison",
    "trial_review_reference",
    "trial_conclusion",
    "controlled_quality_result",
)
EXTERNAL_SOURCE_KINDS = (
    "erp_material_specification",
    "erp_quality_result",
    "erp_run_at_rate",
    "erp_hr_qualification",
    "erp_supplier_execution",
)
EXTERNAL_REASON_CODES = {
    kind: f"{kind}_provider_unavailable" for kind in EXTERNAL_SOURCE_KINDS
}

READINESS_DOCTYPES = (
    "NPI Readiness Template",
    "NPI Readiness Template Version",
    "NPI Readiness Instance Revision",
    "NPI Readiness Command Idempotency",
)
READINESS_OPERATIONS = (
    "readiness_template.create",
    "readiness_template.edit",
    "readiness_template.publish",
    "readiness_instance.initialize",
    "readiness_instance.revise",
)
READINESS_PROTECTED_FIELDS = {
    "NPI Readiness Template": "template_code",
    "NPI Readiness Template Version": "snapshot_hash",
    "NPI Readiness Instance Revision": "snapshot_hash",
    "NPI Readiness Command Idempotency": "payload_hash",
}

TEMPLATE_CREATE_KEY = f"p7-05-runtime-{FIXTURE_RUN_ID}-template-create"
TEMPLATE_EDIT_KEY = f"p7-05-runtime-{FIXTURE_RUN_ID}-template-edit"
TEMPLATE_PUBLISH_KEY = f"p7-05-runtime-{FIXTURE_RUN_ID}-template-publish"
TEMPLATE_IMMUTABLE_KEY = f"p7-05-runtime-{FIXTURE_RUN_ID}-template-immutable"
INITIALIZE_KEY = f"p7-05-runtime-{FIXTURE_RUN_ID}-initialize"
INTERNAL_REVISE_KEY = f"p7-05-runtime-{FIXTURE_RUN_ID}-internal"
QUALITY_REVISE_KEY = f"p7-05-runtime-{FIXTURE_RUN_ID}-quality"
EXTERNAL_REVISE_KEY = f"p7-05-runtime-{FIXTURE_RUN_ID}-external"
STALE_REVISE_KEY = f"p7-05-runtime-{FIXTURE_RUN_ID}-stale"
ROLLBACK_REVISE_KEY = f"p7-05-runtime-{FIXTURE_RUN_ID}-rollback"
IDOR_REVISE_KEY = f"p7-05-runtime-{FIXTURE_RUN_ID}-idor"
CAPACITY_SOURCE_PREP_KEY = f"p7-05-runtime-{FIXTURE_RUN_ID}-capacity-source"
TRIAL_REFERENCE_REOPEN_KEY = f"p7-05-runtime-{FIXTURE_RUN_ID}-reference-reopen"
TRIAL_REFERENCE_COMPARISON_KEY = (
    f"p7-05-runtime-{FIXTURE_RUN_ID}-reference-comparison"
)
TRIAL_REFERENCE_CREATE_KEY = f"p7-05-runtime-{FIXTURE_RUN_ID}-reference-create"
SOURCE_PREPARATION_IDEMPOTENCY_KEYS = (
    CAPACITY_SOURCE_PREP_KEY,
    TRIAL_REFERENCE_REOPEN_KEY,
    TRIAL_REFERENCE_COMPARISON_KEY,
    TRIAL_REFERENCE_CREATE_KEY,
)
TEMPLATE_CODE = f"P705-{FIXTURE_RUN_ID[:16].upper()}"
CAPACITY_SOURCE_SENTINEL = "P705-CAPACITY-SOURCE-SENTINEL"
TRIAL_REFERENCE_SENTINEL = "P705-TRIAL-REFERENCE-SENTINEL"

ABSENT_INSTANCE_ID = "00000000-0000-4000-8000-000000000705"
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def template_path(
    template_id: str | None = None,
    template_version: int | None = None,
    *,
    publish: bool = False,
) -> str:
    path = "/api/npi/v1/npi-readiness/templates"
    if template_id is None:
        require(template_version is None and not publish, "P7-05 template path is invalid")
        return path
    require(
        isinstance(template_version, int) and template_version > 0,
        "P7-05 template version path is invalid",
    )
    path = f"{path}/{template_id}/versions/{template_version}"
    return f"{path}:publish" if publish else path


def readiness_path(project_id: str, instance_id: str | None = None) -> str:
    path = f"/api/npi/v1/projects/{project_id}/npi-readiness"
    return path if instance_id is None else f"{path}/{instance_id}/revisions"


def readiness_request(
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
        else document_runtime.query_headers(f"p705-{query_key}-{uuid4().hex}")
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
        "P7-05 request identity was not echoed",
    )
    require(
        result.headers.get("Cache-Control") == "private, no-store",
        "P7-05 private no-store response drifted",
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
    method: str = "POST",
    expected_status: int,
    replayed: bool = False,
) -> HttpResult:
    result = readiness_request(
        opener,
        base_url,
        path,
        method=method,
        payload=payload,
        csrf_token=csrf_token,
        idempotency_key=key,
    )
    require(
        result.status == expected_status
        and result.headers.get("Idempotency-Replayed")
        == ("true" if replayed else "false"),
        f"P7-05 command returned HTTP {result.status}",
    )
    require_safe_payload(result.body, "P7-05 command response")
    return result


def require_safe_payload(value: object, label: str) -> None:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    folded = serialized.casefold()
    require(
        "/private/files/" not in folded
        and '"fileurl"' not in folded
        and '"password"' not in folded
        and '"secret"' not in folded
        and "/users/" not in folded,
        f"{label} exposed a sensitive value or private path",
    )


def _json_object(value: object, label: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{label} is not an object")
    return dict(value)


def _uuid(value: object, label: str) -> str:
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        require(False, f"{label} is not a UUID")
        raise AssertionError
    require(str(parsed) == str(value).casefold(), f"{label} is not canonical")
    return str(parsed)


def _hash(value: object, label: str) -> str:
    require(
        isinstance(value, str) and _SHA256.fullmatch(value) is not None,
        f"{label} is not a SHA-256 hash",
    )
    return value


def _source_request(source: Mapping[str, object], requirement_key: str) -> dict[str, object]:
    kind = str(source.get("kind"))
    require(kind in INTERNAL_SOURCE_KINDS, "P7-05 internal source kind drifted")
    return {
        "requirementKey": requirement_key,
        "kind": kind,
        "globalId": _uuid(source.get("globalId"), f"{kind} global ID"),
        "sourceVersion": int(source.get("sourceVersion") or 0),
        "snapshotHash": _hash(source.get("snapshotHash"), f"{kind} snapshot"),
    }


def _external_source_requests() -> list[dict[str, object]]:
    # External provider requests intentionally contain no identity, state, or result.
    return [
        {"requirementKey": "external_offline", "kind": kind}
        for kind in EXTERNAL_SOURCE_KINDS
    ]


def template_payload(context: Mapping[str, object], *, edited: bool = False) -> dict[str, object]:
    project_type = str(context["projectType"])
    customer_keys = list(context.get("customerReferenceKeys", []))
    gate_key = str(context["gateKey"])
    applicability = {
        "projectTypes": [project_type],
        "customerReferenceKeys": customer_keys,
        "industryKeys": [INDUSTRY_KEY],
    }
    item_applicability = {
        "projectTypes": [project_type],
        "customerReferenceKeys": customer_keys,
        "industryKeys": [INDUSTRY_KEY],
    }
    return {
        "templateCode": TEMPLATE_CODE,
        "title": (
            "Synthetic controlled readiness template, revised"
            if edited
            else "Synthetic controlled readiness template"
        ),
        "applicability": applicability,
        "categories": [{"key": "runtime", "title": "Controlled runtime"}],
        "items": [
            {
                "key": "internal_exact",
                "title": "Exact retained internal evidence",
                "categoryKey": "runtime",
                "weight": 97,
                "required": True,
                "blockingLevel": "P2",
                "gateKey": gate_key,
                "completionRule": "exact_evidence",
                "applicability": item_applicability,
                "evidenceRequirements": [
                    {
                        "key": "internal_exact",
                        "acceptedSourceKinds": list(INTERNAL_SOURCE_KINDS),
                        "minimumCount": 16,
                        "unavailableBlocks": False,
                    }
                ],
            },
            {
                "key": "p0_hold",
                "title": "Authoritative P0 confirmation P705-GATE-DRIFT-SENTINEL",
                "categoryKey": "runtime",
                "weight": 1,
                "required": True,
                "blockingLevel": "P0",
                "gateKey": gate_key,
                "completionRule": "confirmation",
                "applicability": item_applicability,
                "evidenceRequirements": [],
            },
            {
                "key": "quality_hold",
                "title": "Mandatory exact quality result",
                "categoryKey": "runtime",
                "weight": 1,
                "required": True,
                "blockingLevel": "P1",
                "gateKey": gate_key,
                "completionRule": "exact_source_result",
                "applicability": item_applicability,
                "evidenceRequirements": [
                    {
                        "key": "quality_failed",
                        "acceptedSourceKinds": [
                            "trial_cavity_result",
                            "trial_defect",
                            "trial_defect_verification",
                        ],
                        "minimumCount": 1,
                        "unavailableBlocks": False,
                    }
                ],
            },
            {
                "key": "external_hold",
                "title": "Formal external provider P705-ERP-MATERIAL-SENTINEL",
                "categoryKey": "runtime",
                "weight": 1,
                "required": True,
                "blockingLevel": "P1",
                "gateKey": gate_key,
                "completionRule": "exact_evidence",
                "applicability": item_applicability,
                "evidenceRequirements": [
                    {
                        "key": "external_offline",
                        "acceptedSourceKinds": list(EXTERNAL_SOURCE_KINDS),
                        "minimumCount": 1,
                        "unavailableBlocks": True,
                    }
                ],
            },
        ],
    }


def capacity_source_payload(
    context: Mapping[str, object],
    profile: Mapping[str, object],
) -> dict[str, object]:
    """Build one bounded passing source without rewriting retained P6 history."""

    applications = context.get("applicability")
    require(
        isinstance(applications, list)
        and len(applications) == 2
        and all(isinstance(value, dict) for value in applications),
        "P7-05 Capacity source requires the two retained applicability rows",
    )
    payload = tooling_controls_runtime.capacity_payload(
        dict(context),
        dict(profile),
        version=1,
    )
    require(
        "scenarioGlobalId" not in payload and "expectedVersion" not in payload,
        "P7-05 Capacity source must remain an independent first revision",
    )
    return {
        **payload,
        "title": CAPACITY_SOURCE_SENTINEL,
        "effectiveFrom": "2026-08-23",
        "targetMonthlyAssemblyUnits": "25000.0",
        "reason": CAPACITY_SOURCE_SENTINEL,
    }


def current_controlled_reference(
    workspace: Mapping[str, object],
) -> dict[str, object] | None:
    """Return one controlled reference only when its frozen target is still current."""

    trial_round = workspace.get("trialRound")
    comparisons = workspace.get("comparisonSnapshots")
    references = workspace.get("reviewReferenceRevisions")
    if not (
        isinstance(trial_round, dict)
        and isinstance(comparisons, list)
        and isinstance(references, list)
    ):
        return None
    round_id = trial_round.get("globalId")
    round_version = trial_round.get("optimisticVersion")
    round_hash = trial_round.get("snapshotHash")
    matches: list[dict[str, object]] = []
    for reference in references:
        if not (
            isinstance(reference, dict)
            and reference.get("referenceKind") == "controlled_quality_report"
            and reference.get("trialRoundGlobalId") == round_id
        ):
            continue
        exact = reference.get("comparisonSnapshot")
        if not isinstance(exact, dict):
            continue
        candidates = [
            value
            for value in comparisons
            if isinstance(value, dict)
            and value.get("globalId") == exact.get("globalId")
            and value.get("snapshotHash") == exact.get("snapshotHash")
        ]
        if len(candidates) != 1:
            continue
        comparison = candidates[0]
        sources = comparison.get("sources")
        if not isinstance(sources, list) or not sources:
            continue
        target = sources[-1]
        if (
            comparison.get("targetRoundGlobalId") == round_id
            and isinstance(target, dict)
            and target.get("trialRoundGlobalId") == round_id
            and target.get("trialRoundOptimisticVersion") == round_version
            and target.get("trialRoundSnapshotHash") == round_hash
        ):
            matches.append(dict(reference))
    return matches[0] if len(matches) == 1 else None


def _prepare_capacity_source(
    administrator,
    base_url: str,
    administrator_csrf: str,
) -> dict[str, object]:
    context = tooling_controls_runtime.project_context(administrator, base_url)
    path = tooling_controls_runtime.engineering_path(
        str(context["projectId"]),
        str(context["masterId"]),
    )
    retained = tooling_controls_runtime.assert_engineering_context(
        tooling_controls_runtime.tooling_request(
            administrator,
            base_url,
            path,
            query_key="readiness-source-before",
        ),
        context=context,
        expected_count=2,
    )
    profiles = retained["process"]["customerStandardRevisions"]
    require(
        isinstance(profiles, list) and len(profiles) == 2,
        "P7-05 retained Customer Standard profiles are unavailable",
    )
    profile = max(profiles, key=lambda value: int(value.get("profileVersion") or 0))
    require(
        isinstance(profile, dict) and profile.get("profileVersion") == 2,
        "P7-05 exact Customer Standard successor is unavailable",
    )
    result = tooling_controls_runtime.command(
        administrator,
        base_url,
        administrator_csrf,
        tooling_controls_runtime.engineering_command_path(
            str(context["projectId"]),
            str(context["masterId"]),
            "/capacity-scenario-revisions",
        ),
        capacity_source_payload(context, profile),
        CAPACITY_SOURCE_PREP_KEY,
    )
    scenario = result.body.get("scenario")
    require(isinstance(scenario, dict), "P7-05 prepared Capacity Scenario drifted")
    scenario_result = scenario.get("result")
    try:
        target = Decimal(str(scenario.get("targetMonthlyAssemblyUnits")))
        gap = Decimal(str(scenario_result.get("gap")))
    except (AttributeError, InvalidOperation):
        require(False, "P7-05 prepared Capacity Scenario result is invalid")
        raise AssertionError
    require(
        scenario.get("scenarioVersion") == 1
        and scenario.get("predecessorGlobalId") is None
        and scenario.get("predecessorSnapshotHash") is None
        and target == Decimal("25000")
        and gap == Decimal("0")
        and isinstance(scenario.get("lines"), list)
        and len(scenario["lines"]) == 2,
        "P7-05 prepared Capacity Scenario is not an independent satisfied source",
    )
    _uuid(scenario.get("globalId"), "prepared Capacity Scenario revision")
    _hash(scenario.get("snapshotHash"), "prepared Capacity Scenario revision")
    after = tooling_controls_runtime.tooling_request(
        administrator,
        base_url,
        path,
        query_key="readiness-source-after",
    )
    scenarios = after.body.get("capacityScenarioRevisions")
    require(
        after.status == 200
        and after.body.get("projectGlobalId") == context["projectId"]
        and after.body.get("toolingMasterGlobalId") == context["masterId"]
        and isinstance(scenarios, list)
        and len(scenarios) == 3
        and len(after.body.get("defectRevisions", [])) == 2
        and len(
            after.body.get("process", {}).get("customerStandardRevisions", [])
        )
        == 2
        and sum(
            1
            for value in scenarios
            if isinstance(value, dict)
            and value.get("globalId") == scenario.get("globalId")
            and value.get("snapshotHash") == scenario.get("snapshotHash")
        )
        == 1,
        "P7-05 Capacity source preparation changed retained P6 chains",
    )
    return {
        "globalId": scenario["globalId"],
        "scenarioVersion": 1,
        "snapshotHash": scenario["snapshotHash"],
    }


def _exact_reference_context(reference: Mapping[str, object]) -> dict[str, object]:
    exact_fields = {
        "partRevision": "partRevision",
        "toolingRevision": "toolingRevision",
        "toolingSet": "toolingSet",
        "fileRevision": "fileRevision",
    }
    exact: dict[str, dict[str, object]] = {}
    for source, label in exact_fields.items():
        value = reference.get(source)
        require(isinstance(value, dict), f"P7-05 exact {label} is unavailable")
        exact[source] = value
        _uuid(value.get("globalId"), f"P7-05 exact {label}")
        _hash(value.get("snapshotHash"), f"P7-05 exact {label}")
    return {
        "partRevisionGlobalId": exact["partRevision"]["globalId"],
        "partRevisionSnapshotHash": exact["partRevision"]["snapshotHash"],
        "toolingMasterGlobalId": _uuid(
            reference.get("toolingMasterGlobalId"),
            "P7-05 exact Tooling Master",
        ),
        "toolingRevisionGlobalId": exact["toolingRevision"]["globalId"],
        "toolingRevisionSnapshotHash": exact["toolingRevision"]["snapshotHash"],
        "toolingSetGlobalId": exact["toolingSet"]["globalId"],
        "toolingSetSnapshotHash": exact["toolingSet"]["snapshotHash"],
        "fileRevisionGlobalId": exact["fileRevision"]["globalId"],
        "fileRevisionSnapshotHash": exact["fileRevision"]["snapshotHash"],
    }


def _prepare_current_trial_reference(
    administrator,
    base_url: str,
    fixture_password: str,
) -> dict[str, object]:
    project_id, _plan_id, detail = trial_runtime.retained_detail(
        administrator, base_url
    )
    primary = trial_runtime.exact_single(
        [value for value in detail["rounds"] if value.get("displayLabel") == "T0"],
        "P7-05 primary Trial Round",
    )
    target = trial_runtime.exact_single(
        [value for value in detail["rounds"] if value.get("displayLabel") == "T1"],
        "P7-05 target Trial Round",
    )
    round_id = str(target["globalId"])
    reviewer = login(base_url, trial_runtime.REVIEW_USER, fixture_password)
    reviewer_csrf = bootstrap_csrf(
        reviewer,
        base_url,
        trial_runtime.REVIEW_USER,
    )
    rejected = trial_runtime.assert_review_workspace(
        trial_runtime.trial_request(
            reviewer,
            base_url,
            trial_runtime.review_path(project_id, round_id),
            query_key="readiness-source-rejected",
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
    policy = trial_runtime.exact_single(
        rejected["policyVersions"],
        "P7-05 Trial review policy",
    )
    rejected_conclusion = rejected["conclusionRevisions"][-1]
    controlled = max(
        (
            value
            for value in rejected["reviewReferenceRevisions"]
            if value.get("referenceKind") == "controlled_quality_report"
        ),
        key=lambda value: int(value.get("referenceVersion") or 0),
        default=None,
    )
    require(
        isinstance(controlled, dict) and controlled.get("referenceVersion") == 2,
        "P7-05 retained controlled quality reference is unavailable",
    )
    reference_context = _exact_reference_context(controlled)
    reopened_result = trial_runtime.command(
        reviewer,
        base_url,
        reviewer_csrf,
        trial_runtime.execution_path(project_id, round_id, ":reopen"),
        {
            **trial_runtime.review_policy_context(policy, rejected["trialRound"]),
            "conclusionGlobalId": rejected_conclusion["conclusionGlobalId"],
            "expectedConclusionRevisionGlobalId": rejected_conclusion["globalId"],
            "expectedConclusionRevisionSnapshotHash": rejected_conclusion[
                "snapshotHash"
            ],
            "expectedConclusionVersion": rejected_conclusion["conclusionVersion"],
            "reason": TRIAL_REFERENCE_SENTINEL,
        },
        TRIAL_REFERENCE_REOPEN_KEY,
    )
    reopened = trial_runtime.assert_review_workspace(
        reopened_result,
        project_id,
        round_id,
        state="analysis",
        round_version=10,
        policies=1,
        comparisons=1,
        references=3,
        conclusions=6,
    )
    comparison_ids = {
        value.get("globalId") for value in reopened["comparisonSnapshots"]
    }
    compared_result = trial_runtime.command(
        reviewer,
        base_url,
        reviewer_csrf,
        trial_runtime.review_path(project_id, round_id, "/comparisons"),
        {
            **trial_runtime.review_policy_context(policy, reopened["trialRound"]),
            "rounds": [
                {
                    "trialRoundGlobalId": primary["globalId"],
                    "expectedOptimisticVersion": primary["optimisticVersion"],
                    "expectedSnapshotHash": primary["snapshotHash"],
                },
                {
                    "trialRoundGlobalId": reopened["trialRound"]["globalId"],
                    "expectedOptimisticVersion": reopened["trialRound"][
                        "optimisticVersion"
                    ],
                    "expectedSnapshotHash": reopened["trialRound"]["snapshotHash"],
                },
            ],
            "reason": TRIAL_REFERENCE_SENTINEL,
        },
        TRIAL_REFERENCE_COMPARISON_KEY,
    )
    compared = trial_runtime.assert_review_workspace(
        compared_result,
        project_id,
        round_id,
        state="analysis",
        round_version=10,
        policies=1,
        comparisons=2,
        references=3,
        conclusions=6,
    )
    new_comparisons = [
        value
        for value in compared["comparisonSnapshots"]
        if value.get("globalId") not in comparison_ids
    ]
    comparison = trial_runtime.exact_single(
        new_comparisons,
        "P7-05 current Trial comparison",
    )
    reference_payload = trial_runtime.review_reference_payload(
        reference_context,
        policy,
        compared["trialRound"],
        comparison,
        kind="controlled_quality_report",
    )
    reference_payload["reason"] = TRIAL_REFERENCE_SENTINEL
    created_result = trial_runtime.command(
        reviewer,
        base_url,
        reviewer_csrf,
        trial_runtime.review_path(project_id, round_id, "/review-references"),
        reference_payload,
        TRIAL_REFERENCE_CREATE_KEY,
    )
    created = trial_runtime.assert_review_workspace(
        created_result,
        project_id,
        round_id,
        state="analysis",
        round_version=10,
        policies=1,
        comparisons=2,
        references=4,
        conclusions=6,
    )
    reference = current_controlled_reference(created)
    require(
        isinstance(reference, dict)
        and reference.get("comparisonSnapshot")
        == {
            "globalId": comparison["globalId"],
            "snapshotHash": comparison["snapshotHash"],
        }
        and reference.get("referenceVersion") == 1,
        "P7-05 prepared Trial review reference is not current",
    )
    return {
        "globalId": reference["globalId"],
        "referenceVersion": reference["referenceVersion"],
        "snapshotHash": reference["snapshotHash"],
    }


def prepare_readiness_source_fixtures(
    administrator,
    base_url: str,
    administrator_csrf: str,
    fixture_password: str,
) -> dict[str, object]:
    """Create only the missing current sources before the P7-05 mutation baseline."""

    capacity = _prepare_capacity_source(
        administrator,
        base_url,
        administrator_csrf,
    )
    reference = _prepare_current_trial_reference(
        administrator,
        base_url,
        fixture_password,
    )
    return {
        "capacitySourcePrepared": True,
        "currentTrialReferencePrepared": True,
        "sourcePreparationCommandCount": len(SOURCE_PREPARATION_IDEMPOTENCY_KEYS),
        "capacitySource": capacity,
        "trialReference": reference,
    }


def edit_template_payload(context: Mapping[str, object], optimistic_version: int) -> dict[str, object]:
    payload = template_payload(context, edited=True)
    payload.pop("templateCode")
    return {"expectedOptimisticVersion": optimistic_version, **payload}


def initialize_payload(
    published: Mapping[str, object], context: Mapping[str, object]
) -> dict[str, object]:
    return {
        "templateRevisionGlobalId": _uuid(
            published.get("globalId"), "published template revision"
        ),
        "templateVersion": int(published.get("templateVersion") or 0),
        "templateSnapshotHash": _hash(
            published.get("snapshotHash"), "published template"
        ),
        "industryKey": INDUSTRY_KEY,
        "assignments": [
            {
                "itemKey": key,
                "ownerMemberGlobalId": context["memberGlobalId"],
                "dueDate": due,
            }
            for key, due in (
                ("internal_exact", "2027-08-01"),
                ("p0_hold", "2027-08-02"),
                ("quality_hold", "2027-08-03"),
                ("external_hold", "2027-08-04"),
            )
        ],
    }


def revision_payload(
    current: Mapping[str, object],
    *,
    item_key: str,
    owner_member_id: str,
    due_date: str,
    state: str,
    confirmation_value: str | None,
    sources: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "expectedInstanceVersion": int(current["instanceVersion"]),
        "expectedRevisionGlobalId": current["globalId"],
        "expectedRevisionSnapshotHash": current["snapshotHash"],
        "itemKey": item_key,
        "ownerMemberGlobalId": owner_member_id,
        "dueDate": due_date,
        "state": state,
        "confirmationValue": confirmation_value,
        "sources": sources,
    }


def current_revision(workspace: Mapping[str, object]) -> dict[str, Any]:
    current = workspace.get("currentRevision")
    require(isinstance(current, dict), "P7-05 current revision is unavailable")
    _uuid(current.get("globalId"), "current readiness revision")
    _uuid(current.get("instanceGlobalId"), "current readiness instance")
    _hash(current.get("snapshotHash"), "current readiness revision")
    return dict(current)


def readiness_counts(administrator, base_url: str, project_id: str) -> dict[str, int]:
    result: dict[str, int] = {}
    specs = {
        "NPI Readiness Template": [["template_code", "=", TEMPLATE_CODE]],
        "NPI Readiness Template Version": [["template_code", "=", TEMPLATE_CODE]],
        "NPI Readiness Instance Revision": [["project_global_id", "=", project_id]],
        "NPI Readiness Command Idempotency": [
            ["actor_user_id", "in", [ACTOR_USER, UNRELATED_USER]]
        ],
    }
    for doctype, filters in specs.items():
        result[doctype] = len(
            list_resources(
                administrator,
                base_url,
                doctype,
                filters=filters,
                fields=["name"],
            )
        )
    for operation in READINESS_OPERATIONS:
        result[f"audit:{operation}"] = len(
            list_resources(
                administrator,
                base_url,
                "NPI Audit Event",
                filters=[
                    ["actor", "in", [ACTOR_USER, UNRELATED_USER]],
                    ["operation", "=", operation],
                ],
                fields=["event_id"],
            )
        )
    return result


def ensure_readiness_runtime_users(fixture_run_id: str) -> dict[str, object]:
    import frappe

    document_runtime._validated_runtime_site()
    require(fixture_run_id == FIXTURE_RUN_ID, "P7-05 user fixture namespace drifted")
    expected_roles = {"Desk User", "NPI API User", "System Manager"}
    for user_id, first_name in (
        (ACTOR_USER, "NPI Readiness Manager"),
        (UNRELATED_USER, "NPI Readiness Unrelated"),
    ):
        if not frappe.db.exists("User", user_id):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": user_id,
                    "enabled": 1,
                    "first_name": first_name,
                    "language": "en",
                    "last_name": "Runtime Fixture",
                    "roles": [{"role": role} for role in sorted(expected_roles)],
                    "send_welcome_email": 0,
                    "user_type": "System User",
                }
            ).insert()
        user = frappe.get_doc("User", user_id)
        roles = {str(value.role) for value in user.roles}
        require(
            int(user.enabled) == 1
            and str(user.user_type) == "System User"
            and expected_roles <= roles,
            "P7-05 runtime user authority drifted",
        )
    frappe.db.commit()
    return {
        "actorUser": ACTOR_USER,
        "fixtureRunId": fixture_run_id,
        "unrelatedUser": UNRELATED_USER,
        "usersReady": True,
    }


def _project_scope_field(doctype: str) -> str:
    if doctype == "NPI Engineering Project":
        return "global_id"
    if doctype in {
        "NPI Engineering Part",
        "NPI Engineering Part Revision",
        "NPI Tooling Master",
    }:
        return "originating_project_global_id"
    return "project_global_id"


def _project_scoped_count(frappe, doctype: str, project_id: str) -> int:
    return int(frappe.db.count(doctype, {_project_scope_field(doctype): project_id}))


def _canonical_row_digest(frappe, doctype: str, filters: Mapping[str, object]) -> str:
    rows = frappe.get_all(
        doctype,
        filters=dict(filters),
        fields=["*"],
        order_by="name asc",
        limit_page_length=1_001,
    )
    require(len(rows) <= 1_000, f"P7-05 {doctype} digest collection is unsafe")
    encoded = json.dumps(
        rows,
        default=str,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def readiness_persistence_context(
    fixture_run_id: str, *, project_id: str
) -> dict[str, object]:
    import frappe

    from npi_core.readiness.frappe_repository import _customer_reference_keys

    document_runtime._validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "P7-05 persistence fixture namespace drifted",
    )
    project = frappe.get_doc("NPI Engineering Project", project_id)
    member = frappe.get_doc("NPI Project Member", document_runtime.BASELINE_MEMBER_ID)
    gate_names = frappe.get_all(
        "NPI Gate Shell",
        filters={"project_global_id": project_id, "gate_key": document_runtime.GATE_KEY},
        pluck="name",
        limit_page_length=2,
    )
    require(
        str(project.global_id) == project_id
        and str(project.tenant_id) == TENANT_ID
        and str(member.global_id) == document_runtime.BASELINE_MEMBER_ID
        and str(member.project_global_id) == project_id
        and str(member.tenant_id) == TENANT_ID
        and len(gate_names) == 1,
        "P7-05 exact Project/member/Gate context drifted",
    )
    gate = frappe.get_doc("NPI Gate Shell", str(gate_names[0]))
    second_projects = frappe.get_all(
        "NPI Engineering Project",
        filters={"tenant_id": TENANT_ID, "global_id": ["!=", project_id]},
        fields=["global_id"],
        order_by="global_id asc",
        limit_page_length=2,
    )
    require(bool(second_projects), "P7-05 independent Project IDOR fixture is unavailable")

    project_doctypes = (
        "NPI Engineering Project",
        "NPI Project Member",
        "NPI Gate Shell",
    )
    work_doctypes = ("NPI Domain Work Item",)
    tooling_doctypes = (
        "NPI Engineering Part",
        "NPI Engineering Part Revision",
        "NPI Tooling Requirement",
        "NPI Tooling Master",
        "NPI Tooling Applicability",
        "NPI Tooling Set",
        "NPI Tooling Intake",
        "NPI Tooling Revision",
        "NPI Part Controlled Specification",
        "NPI Tooling Process Chain Revision",
        "NPI Tooling Set Revision Binding",
        "NPI Tooling Manufacturing Plan Revision",
        "NPI Tooling Manufacturing Milestone Observation",
        "NPI Tooling Defect Revision",
        "NPI Tooling Process Profile Revision",
        "NPI Tooling Capacity Scenario Revision",
        "NPI Tooling Command Idempotency",
    )
    document_doctypes = (
        "NPI Document Revision",
        "NPI Document Revision Lifecycle",
        "NPI Document Baseline",
        "NPI File Revision",
    )
    groups = {
        "project": project_doctypes,
        "work": work_doctypes,
        "document": document_doctypes,
        "tooling": tooling_doctypes,
        "trial": trial_runtime.TRIAL_DOCTYPES,
    }
    downstream: dict[str, int] = {}
    downstream_digests: dict[str, str] = {}
    for group, doctypes in groups.items():
        for doctype in doctypes:
            field = _project_scope_field(doctype)
            downstream[f"{group}:{doctype}"] = _project_scoped_count(
                frappe, doctype, project_id
            )
            downstream_digests[f"{group}:{doctype}"] = _canonical_row_digest(
                frappe, doctype, {field: project_id}
            )
    downstream["NPI Outbox Message"] = int(frappe.db.count("NPI Outbox Message"))
    downstream["NPI Inbox Message"] = int(frappe.db.count("NPI Inbox Message"))
    downstream_digests["NPI Outbox Message"] = _canonical_row_digest(
        frappe, "NPI Outbox Message", {}
    )
    downstream_digests["NPI Inbox Message"] = _canonical_row_digest(
        frappe, "NPI Inbox Message", {}
    )
    preparation_audit_filters = {
        "toolingCapacity": {
            "actor": "Administrator",
            "operation": "tooling_capacity_scenario.create",
        },
        "trialComparison": {
            "actor": trial_runtime.REVIEW_USER,
            "operation": "trial_comparison.create",
        },
        "trialReference": {
            "actor": trial_runtime.REVIEW_USER,
            "operation": "trial_review_reference.create",
        },
        "trialReopen": {
            "actor": trial_runtime.REVIEW_USER,
            "operation": "trial_conclusion.reopen",
        },
    }
    preparation_audit_counts = {
        key: int(frappe.db.count("NPI Audit Event", filters))
        for key, filters in preparation_audit_filters.items()
    }
    preparation_audit_digests = {
        key: _canonical_row_digest(frappe, "NPI Audit Event", filters)
        for key, filters in preparation_audit_filters.items()
    }
    return {
        "customerReferenceKeys": list(_customer_reference_keys(project)),
        "downstreamCounts": downstream,
        "downstreamDigests": downstream_digests,
        "fixtureRunId": fixture_run_id,
        "gateGlobalId": str(gate.global_id),
        "gateKey": str(gate.gate_key),
        "gateOptimisticVersion": int(gate.optimistic_version),
        "memberGlobalId": str(member.global_id),
        "memberOptimisticVersion": int(member.optimistic_version),
        "projectGlobalId": project_id,
        "projectOptimisticVersion": int(project.optimistic_version),
        "projectType": str(project.project_type),
        "secondProjectGlobalId": str(second_projects[0].global_id),
        "sourcePreparationAuditCounts": preparation_audit_counts,
        "sourcePreparationAuditDigests": preparation_audit_digests,
    }


def _source_rows(frappe, doctype: str, project_id: str) -> list[Any]:
    names = frappe.get_all(
        doctype,
        filters={"tenant_id": TENANT_ID, "project_global_id": project_id},
        pluck="name",
        order_by="creation asc, name asc",
        limit_page_length=1_001,
    )
    require(len(names) <= 1_000, f"P7-05 {doctype} source collection is unsafe")
    return [frappe.get_doc(doctype, str(name)) for name in names]


def readiness_source_context(
    fixture_run_id: str, *, project_id: str
) -> dict[str, object]:
    import frappe

    from npi_core.foundation.security import Principal
    from npi_core.readiness.domain import ReadinessSourceKind, instance_from_snapshot
    from npi_core.readiness.frappe_repository import (
        FrappeReadinessRepository,
        _domain_work_item_source_snapshot,
        _domain_work_item_value,
        _payload_hash,
    )
    from npi_core.readiness.source_resolver import ExactSourceQuery, SourceResolutionContext

    document_runtime._validated_runtime_site()
    require(fixture_run_id == FIXTURE_RUN_ID, "P7-05 source fixture namespace drifted")
    project = frappe.get_doc("NPI Engineering Project", project_id)
    require(
        str(project.global_id) == project_id and str(project.tenant_id) == TENANT_ID,
        "P7-05 source Project context drifted",
    )
    principal = Principal(
        ACTOR_USER,
        roles=frozenset({"NPI API User", "System Manager"}),
        tenant_id=TENANT_ID,
    )
    repository = FrappeReadinessRepository(
        principal=principal,
        request_id=str(uuid4()),
        trace_id=f"trace-{uuid4().hex}",
    )
    resolution = SourceResolutionContext(TENANT_ID, UUID(project_id))

    candidates: dict[str, list[tuple[str, int, str]]] = {
        kind: [] for kind in INTERNAL_SOURCE_KINDS
    }
    revisions = _source_rows(frappe, "NPI Readiness Instance Revision", project_id)
    require(bool(revisions), "P7-05 frozen Project source is unavailable")
    frozen = instance_from_snapshot(revisions[-1].instance_snapshot).project
    candidates["project"].append(
        (str(frozen.global_id), frozen.optimistic_version, frozen.snapshot_hash)
    )

    for document in _source_rows(frappe, "NPI Domain Work Item", project_id):
        value = _domain_work_item_value(document)
        if value is not None:
            candidates["domain_work_item"].append(
                (
                    str(value.global_id),
                    int(value.version),
                    _payload_hash(_domain_work_item_source_snapshot(value)),
                )
            )
    for lifecycle in _source_rows(
        frappe, "NPI Document Revision Lifecycle", project_id
    ):
        if str(lifecycle.current_state) == "released" and lifecycle.release_snapshot_hash:
            candidates["released_document"].append(
                (
                    str(lifecycle.revision_global_id),
                    int(lifecycle.lifecycle_version),
                    str(lifecycle.release_snapshot_hash),
                )
            )
    for baseline in _source_rows(frappe, "NPI Document Baseline", project_id):
        candidates["release_baseline"].append(
            (
                str(baseline.global_id),
                int(baseline.baseline_version),
                str(baseline.snapshot_hash),
            )
        )
    for file_revision in _source_rows(frappe, "NPI File Revision", project_id):
        candidates["file_revision"].append(
            (
                str(file_revision.global_id),
                int(file_revision.revision),
                str(file_revision.sha256),
            )
        )

    specs = {
        "tooling_capacity_scenario": (
            "NPI Tooling Capacity Scenario Revision",
            "scenario_version",
        ),
        "trial_input_lock": ("NPI Trial Input Lock Revision", "lock_version"),
        "trial_actual": ("NPI Trial Actual Revision", "actual_version"),
        "trial_sample": ("NPI Trial Sample Batch Revision", "sample_version"),
        "trial_cavity_result": (
            "NPI Trial Cavity Result Revision",
            "result_version",
        ),
        "trial_defect": ("NPI Trial Defect Revision", "defect_version"),
        "trial_defect_verification": (
            "NPI Trial Defect Verification Revision",
            "attempt_sequence",
        ),
        "trial_comparison": ("NPI Trial Round Comparison Snapshot", None),
        "trial_review_reference": (
            "NPI Trial Review Reference Revision",
            "reference_version",
        ),
        "trial_conclusion": ("NPI Trial Conclusion Revision", "conclusion_version"),
        "controlled_quality_result": (
            "NPI Trial Review Reference Revision",
            "reference_version",
        ),
    }
    for kind, (doctype, version_field) in specs.items():
        for document in _source_rows(frappe, doctype, project_id):
            candidates[kind].append(
                (
                    str(document.global_id),
                    int(document.get(version_field)) if version_field else 1,
                    str(document.snapshot_hash),
                )
            )

    resolved: dict[str, dict[str, object]] = {}
    failed_quality: dict[str, object] | None = None
    quality_kinds = {
        "trial_cavity_result",
        "trial_defect",
        "trial_defect_verification",
    }
    for kind in INTERNAL_SOURCE_KINDS:
        for global_id, version, snapshot_hash in candidates[kind]:
            query = ExactSourceQuery(
                ReadinessSourceKind(kind),
                UUID(global_id),
                version,
                snapshot_hash,
            )
            observation = repository.get_exact_source(resolution, query)
            if observation is None:
                continue
            repository.authorize_exact_source(resolution, observation)
            source = {
                "globalId": global_id,
                "kind": kind,
                "snapshotHash": snapshot_hash,
                "sourceVersion": version,
                "state": observation.disposition.value,
            }
            if observation.disposition.value == "satisfied" and kind not in resolved:
                resolved[kind] = source
            if (
                kind in quality_kinds
                and observation.disposition.value == "failed"
                and failed_quality is None
            ):
                failed_quality = source
    require(
        set(resolved) == set(INTERNAL_SOURCE_KINDS),
        "P7-05 exact retained internal source catalog is incomplete",
    )
    require(failed_quality is not None, "P7-05 exact failed quality source is unavailable")
    return {
        "failedQualitySource": failed_quality,
        "fixtureRunId": fixture_run_id,
        "internalSources": [resolved[kind] for kind in INTERNAL_SOURCE_KINDS],
    }


def _gate_authority_snapshot(
    frappe, gate_id: str, project_id: str
) -> dict[str, object]:
    gate_audit_operations = (
        "gate.evidence.attach",
        "gate.requirements.freeze",
        "gate.review.decide",
        "gate.review.exception.decide",
        "gate.review.exception.request",
        "gate.review.history.delete_attempt",
        "gate.review.invalidate",
        "gate.review.refresh",
        "gate.review.reopen",
        "gate.review.start",
        "gate.review.submit",
    )
    specs: dict[str, dict[str, object]] = {
        "NPI Gate Shell": {"global_id": gate_id},
        "NPI Gate Review Cycle": {"gate_global_id": gate_id},
        # The authoritative decision row is NPI Gate Decision Snapshot.
        "NPI Gate Decision Snapshot": {"gate_global_id": gate_id},
        "NPI Baseline Gate Dependency": {"gate_global_id": gate_id},
        "NPI Gate Evidence Reference": {"gate_global_id": gate_id},
        "NPI Gate Review Event": {"gate_global_id": gate_id},
        "NPI Gate Review Exception": {"gate_global_id": gate_id},
        "NPI Gate Review Record": {"gate_global_id": gate_id},
        "NPI Gate Review Idempotency": {
            "project_global_id": project_id,
            "gate_global_id": gate_id,
        },
        "NPI Audit Event": {"operation": ["in", list(gate_audit_operations)]},
    }
    snapshot = {
        doctype: {
            "count": int(frappe.db.count(doctype, filters)),
            "digest": _canonical_row_digest(frappe, doctype, filters),
        }
        for doctype, filters in specs.items()
    }
    snapshot["NPI Gate Decision"] = snapshot["NPI Gate Decision Snapshot"]
    return snapshot


def verify_external_resolver_offline(fixture_run_id: str) -> dict[str, object]:
    from npi_core.readiness.request_validation import parse_source_requests
    from npi_core.readiness.source_resolver import (
        SourceResolutionContext,
        resolve_sources,
    )

    document_runtime._validated_runtime_site()
    require(fixture_run_id == FIXTURE_RUN_ID, "P7-05 resolver fixture namespace drifted")

    class NoRepositoryBoundary:
        calls = 0

        def get_exact_source(self, *_args, **_kwargs):
            self.calls += 1
            raise AssertionError("External readiness resolution crossed a repository boundary")

        def authorize_exact_source(self, *_args, **_kwargs):
            self.calls += 1
            raise AssertionError("External readiness resolution crossed an authority boundary")

    boundary = NoRepositoryBoundary()
    sources = resolve_sources(
        parse_source_requests(_external_source_requests()),
        context=SourceResolutionContext(TENANT_ID, UUID(int=705)),
        repository=boundary,
    )
    require(
        len(sources) == len(EXTERNAL_SOURCE_KINDS)
        and boundary.calls == 0
        and all(value.state.value == "unavailable" for value in sources),
        "P7-05 external resolver crossed its identity-free offline boundary",
    )
    return {
        "externalSourceCount": len(sources),
        "fixtureRunId": fixture_run_id,
        "repositoryCalls": boundary.calls,
    }


def readiness_gate_input_context(
    fixture_run_id: str, *, project_id: str, gate_id: str
) -> dict[str, object]:
    import frappe

    from npi_core.foundation.security import Principal
    from npi_core.gate_review.frappe_repository import FrappeGateReviewRepository

    document_runtime._validated_runtime_site()
    require(fixture_run_id == FIXTURE_RUN_ID, "P7-05 Gate fixture namespace drifted")
    project = frappe.get_doc("NPI Engineering Project", project_id)
    gate = frappe.get_doc("NPI Gate Shell", gate_id)
    require(
        str(project.tenant_id) == TENANT_ID
        and str(gate.project_global_id) == project_id
        and str(gate.global_id) == gate_id,
        "P7-05 exact Gate input context drifted",
    )
    repository = FrappeGateReviewRepository(
        principal=Principal(
            ACTOR_USER,
            roles=frozenset({"NPI API User", "System Manager"}),
            tenant_id=TENANT_ID,
        ),
        request_id=str(uuid4()),
        trace_id=f"trace-{uuid4().hex}",
    )
    current = repository._build_current_input(project, gate)
    payload = current.canonical_dict()
    return {
        "blockers": payload["blockers"],
        "dependencies": payload["dependencies"],
        "fixtureRunId": fixture_run_id,
        "gateAuthoritySnapshot": _gate_authority_snapshot(
            frappe, gate_id, project_id
        ),
        "gateInputHash": current.snapshot_hash,
        "gateOptimisticVersion": int(gate.optimistic_version),
        "gateState": str(gate.state),
    }


def verify_readiness_runtime_schema(fixture_run_id: str) -> dict[str, object]:
    import frappe

    document_runtime._validated_runtime_site()
    require(fixture_run_id == FIXTURE_RUN_ID, "P7-05 schema fixture namespace drifted")
    required_fields = {
        "NPI Readiness Template": {
            "global_id",
            "template_code",
            "enabled",
            "optimistic_version",
        },
        "NPI Readiness Template Version": {
            "global_id",
            "template_global_id",
            "template_version",
            "optimistic_version",
            "publication_state",
            "template_snapshot",
            "snapshot_hash",
        },
        "NPI Readiness Instance Revision": {
            "global_id",
            "instance_global_id",
            "project_global_id",
            "instance_version",
            "predecessor_global_id",
            "instance_snapshot",
            "evaluation_snapshot",
            "snapshot_hash",
        },
        "NPI Readiness Command Idempotency": {
            "global_id",
            "receipt_key",
            "actor_user_id",
            "operation",
            "payload_hash",
            "response_payload",
            "response_hash",
            "sealed",
        },
    }
    for doctype in READINESS_DOCTYPES:
        require(frappe.db.table_exists(doctype), f"P7-05 table is unavailable: {doctype}")
        fields = {field.fieldname for field in frappe.get_meta(doctype, cached=False).fields}
        require(
            required_fields[doctype] <= fields,
            f"P7-05 metadata is incomplete for {doctype}",
        )
    return {
        "doctypeCount": len(READINESS_DOCTYPES),
        "fixtureRunId": fixture_run_id,
        "metadataSynchronized": True,
        "runtimeMarker": RUNTIME_MARKER,
    }


BENCH_FIXTURES = {
    "ensure_readiness_runtime_users": ensure_readiness_runtime_users,
    "readiness_gate_input_context": readiness_gate_input_context,
    "readiness_persistence_context": readiness_persistence_context,
    "readiness_source_context": readiness_source_context,
    "verify_external_resolver_offline": verify_external_resolver_offline,
    "verify_readiness_runtime_schema": verify_readiness_runtime_schema,
}


def run_bench_fixture(method: str, kwargs: dict[str, object]) -> dict[str, Any]:
    require(method in BENCH_FIXTURES, "P7-05 Bench fixture is unavailable")
    require(
        BENCH_PATH.is_dir()
        and not BENCH_PATH.is_symlink()
        and BENCH_PATH.resolve() == BENCH_PATH,
        "P7-05 verifier requires the fixed physical Bench",
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
            str(ROOT / "scripts" / "verify_readiness_runtime.py"),
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
    require(completed.returncode == 0, f"P7-05 Bench fixture failed: {method}")
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    require(bool(lines), f"P7-05 Bench fixture was silent: {method}")
    result = json.loads(lines[-1])
    require(isinstance(result, dict), "P7-05 Bench fixture result is invalid")
    return result


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    require(method in BENCH_FIXTURES, "P7-05 Bench fixture is unavailable")
    import frappe

    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    try:
        frappe.set_user("Administrator")
        result = BENCH_FIXTURES[method](**kwargs)
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.destroy()


def prepare_runtime_users(
    administrator,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
) -> None:
    fixture = run_bench_fixture(
        "ensure_readiness_runtime_users", {"fixture_run_id": FIXTURE_RUN_ID}
    )
    require(
        fixture.get("usersReady") is True
        and fixture.get("actorUser") == ACTOR_USER
        and fixture.get("unrelatedUser") == UNRELATED_USER,
        "P7-05 closed user fixture drifted",
    )
    for user_id in (ACTOR_USER, UNRELATED_USER):
        changed = update_resource(
            administrator,
            base_url,
            "User",
            user_id,
            {"new_password": fixture_password},
            csrf_token,
        )
        require(changed.status == 200, "P7-05 runtime user password was not set")
        retained = get_resource(administrator, base_url, "User", user_id)
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
            "P7-05 runtime user authority drifted after HTTP provisioning",
        )


def template_catalog(opener, base_url: str, project_id: str) -> dict[str, Any]:
    result = readiness_request(
        opener,
        base_url,
        f"{template_path()}?projectId={project_id}",
        query_key="template-catalog",
    )
    require(result.status == 200, f"P7-05 template catalog returned HTTP {result.status}")
    require_safe_payload(result.body, "P7-05 template catalog")
    require(
        result.body.get("projectGlobalId") == project_id
        and isinstance(result.body.get("templates"), list),
        "P7-05 template catalog Project context drifted",
    )
    return _json_object(result.body, "P7-05 template catalog")


def readiness_workspace(opener, base_url: str, project_id: str) -> dict[str, Any]:
    result = readiness_request(
        opener,
        base_url,
        readiness_path(project_id),
        query_key="workspace",
    )
    require(result.status == 200, f"P7-05 workspace returned HTTP {result.status}")
    require_safe_payload(result.body, "P7-05 readiness workspace")
    require(
        result.body.get("projectGlobalId") == project_id,
        "P7-05 workspace crossed its Project boundary",
    )
    return _json_object(result.body, "P7-05 readiness workspace")


def _item(revision: Mapping[str, object], item_key: str) -> dict[str, Any]:
    items = revision.get("items")
    require(isinstance(items, list), "P7-05 readiness item collection is invalid")
    selected = [
        value
        for value in items
        if isinstance(value, dict)
        and isinstance(value.get("definition"), dict)
        and value["definition"].get("key") == item_key
    ]
    require(len(selected) == 1, f"P7-05 readiness item is unavailable: {item_key}")
    return dict(selected[0])


def verify_template_response(
    value: Mapping[str, object],
    *,
    publication_state: str,
    optimistic_version: int,
) -> None:
    if publication_state == "draft":
        require(
            value.get("publicationState") == "draft",
            "P7-05 template was not retained as a draft",
        )
    else:
        require(
            publication_state == "published"
            and value.get("publicationState") == "published",
            "P7-05 template was not retained as published",
        )
    require(
        value.get("templateCode") == TEMPLATE_CODE
        and value.get("templateVersion") == 1
        and value.get("optimisticVersion") == optimistic_version
        and value.get("publicationState") == publication_state
        and isinstance(value.get("templateGlobalId"), str),
        "P7-05 readiness template lifecycle truth drifted",
    )
    _uuid(value.get("globalId"), "template revision")
    _uuid(value.get("templateGlobalId"), "template root")
    _hash(value.get("snapshotHash"), "template revision")


def verify_internal_sources(current: Mapping[str, object]) -> None:
    selected = _item(current, "internal_exact")
    sources = selected.get("sources")
    require(isinstance(sources, list), "P7-05 internal sources are invalid")
    require(
        selected.get("state") == "complete"
        and len(sources) == 16
        and {value.get("kind") for value in sources if isinstance(value, dict)}
        == set(INTERNAL_SOURCE_KINDS),
        "P7-05 exact internal source coverage drifted",
    )
    for source in sources:
        require(isinstance(source, dict), "P7-05 internal source is invalid")
        require(
            source.get("requirementKey") == "internal_exact"
            and source.get("state") == "satisfied"
            and source.get("reasonCode") is None,
            "P7-05 retained internal source did not resolve as satisfied",
        )
        _uuid(source.get("globalId"), "internal source")
        require(
            type(source.get("sourceVersion")) is int
            and int(source["sourceVersion"]) > 0,
            "P7-05 internal source version drifted",
        )
        _hash(source.get("snapshotHash"), "internal source")


def verify_initialized_instance(
    revision: Mapping[str, object],
    published: Mapping[str, object],
    context: Mapping[str, object],
) -> None:
    project = revision.get("project")
    template_revision = revision.get("templateRevision")
    categories = revision.get("categories")
    require(
        isinstance(project, dict)
        and project.get("globalId") == context.get("projectGlobalId")
        and project.get("optimisticVersion") == context.get("projectOptimisticVersion")
        and project.get("projectType") == context.get("projectType")
        and project.get("customerReferenceKeys")
        == context.get("customerReferenceKeys")
        and project.get("industryKey") == INDUSTRY_KEY,
        "P7-05 frozen readiness Project identity drifted",
    )
    _hash(project.get("snapshotHash"), "frozen readiness Project")
    require(
        isinstance(template_revision, dict)
        and template_revision
        == {
            "globalId": published.get("globalId"),
            "version": published.get("templateVersion"),
            "snapshotHash": published.get("snapshotHash"),
        },
        "P7-05 frozen readiness template exact tuple drifted",
    )
    require(
        categories == [{"key": "runtime", "title": "Controlled runtime"}],
        "P7-05 frozen readiness category drifted",
    )
    expected_due_dates = {
        "internal_exact": "2027-08-01",
        "p0_hold": "2027-08-02",
        "quality_hold": "2027-08-03",
        "external_hold": "2027-08-04",
    }
    expected_levels = {
        "internal_exact": "P2",
        "p0_hold": "P0",
        "quality_hold": "P1",
        "external_hold": "P1",
    }
    expected_owner = {
        "globalId": context.get("memberGlobalId"),
        "userId": document_runtime.BASELINE_USER,
        "optimisticVersion": context.get("memberOptimisticVersion"),
    }
    for item_key, due_date in expected_due_dates.items():
        item = _item(revision, item_key)
        definition = item.get("definition")
        gate = item.get("gate")
        require(
            isinstance(definition, dict)
            and definition.get("key") == item_key
            and definition.get("categoryKey") == "runtime"
            and definition.get("blockingLevel") == expected_levels[item_key]
            and definition.get("gateKey") == context.get("gateKey")
            and item.get("applicable") is True
            and item.get("owner") == expected_owner
            and item.get("dueDate") == due_date
            and item.get("state") == "not_started"
            and item.get("confirmationValue") is None
            and item.get("sources") == []
            and isinstance(gate, dict)
            and gate.get("globalId") == context.get("gateGlobalId")
            and gate.get("gateKey") == context.get("gateKey")
            and gate.get("optimisticVersion")
            == context.get("gateOptimisticVersion"),
            "P7-05 frozen readiness item assignment or Gate identity drifted",
        )
        _uuid(item.get("globalId"), f"{item_key} readiness item")
        _hash(gate.get("snapshotHash"), f"{item_key} frozen Gate")


def verify_external_sources_offline(workspace: Mapping[str, object]) -> None:
    current = current_revision(workspace)
    selected = _item(current, "external_hold")
    sources = selected.get("sources")
    require(isinstance(sources, list), "P7-05 external source set is invalid")
    require(
        len(sources) == 5
        and {source.get("kind") for source in sources if isinstance(source, dict)}
        == set(EXTERNAL_SOURCE_KINDS),
        "P7-05 external source coverage drifted",
    )
    for source in sources:
        require(isinstance(source, dict), "P7-05 external source is invalid")
        kind = str(source.get("kind"))
        require(
            source.get("requirementKey") == "external_offline"
            and source.get("state") == "unavailable"
            and source.get("globalId") is None
            and source.get("sourceVersion") is None
            and source.get("snapshotHash") is None
            and source.get("reasonCode") == EXTERNAL_REASON_CODES[kind],
            "P7-05 formal ERP projection acquired caller identity",
        )
    projections = workspace.get("unavailableProjections")
    require(isinstance(projections, list), "P7-05 unavailable projection set is invalid")
    require(
        len(projections) == 5
        and {value.get("kind") for value in projections if isinstance(value, dict)}
        == set(EXTERNAL_SOURCE_KINDS),
        "P7-05 formal ERP unavailable projections drifted",
    )
    for projection in projections:
        require(isinstance(projection, dict), "P7-05 unavailable projection is invalid")
        kind = str(projection.get("kind"))
        require(
            set(projection) == {"kind", "state", "reasonCode"}
            and projection.get("state") == "unavailable"
            and projection.get("globalId") is None
            and projection.get("sourceVersion") is None
            and projection.get("snapshotHash") is None
            and projection.get("reasonCode") == EXTERNAL_REASON_CODES[kind],
            "P7-05 formal ERP projection acquired caller identity",
        )


def verify_high_score_blockers(workspace: Mapping[str, object]) -> None:
    current = current_revision(workspace)
    evaluation = current.get("evaluation")
    require(isinstance(evaluation, dict), "P7-05 readiness evaluation is unavailable")
    total = evaluation.get("totalScore")
    category_scores = evaluation.get("categoryScores")
    blockers = evaluation.get("blockers")
    expected_item_keys = {
        "incomplete_p0": "p0_hold",
        "failed_mandatory_quality": "quality_hold",
        "required_source_unavailable": "external_hold",
    }
    require(
        evaluation.get("formulaVersion") == "readiness-score.v1"
        and isinstance(total, dict)
        and category_scores
        == [
            {
                "categoryKey": "runtime",
                "earnedWeight": 97,
                "applicableWeight": 100,
                "basisPoints": 9700,
                "state": "scored",
            }
        ]
        and total.get("earnedWeight") == 97
        and total.get("applicableWeight") == 100
        and total.get("basisPoints") == 9700
        and total.get("state") == "scored"
        and isinstance(blockers, list)
        and len(blockers) == 3
        and {value.get("code") for value in blockers if isinstance(value, dict)}
        == {
            "incomplete_p0",
            "failed_mandatory_quality",
            "required_source_unavailable",
        }
        and evaluation.get("ready") is False,
        "P7-05 high readiness score hid authoritative blockers",
    )
    blocker_by_code = {
        str(value["code"]): value for value in blockers if isinstance(value, dict)
    }
    require(
        len(blocker_by_code) == len(blockers),
        "P7-05 readiness evaluation duplicated an authoritative blocker",
    )
    for code, item_key in expected_item_keys.items():
        blocker = blocker_by_code[code]
        item = _item(current, item_key)
        require(
            blocker.get("itemKey") == item_key
            and blocker.get("itemGlobalId") == item.get("globalId")
            and blocker.get("gate") == item.get("gate"),
            "P7-05 readiness blocker lost its exact item and Gate identity",
        )


def _assert_replay(
    opener,
    base_url: str,
    csrf_token: str,
    path: str,
    payload: dict[str, object],
    key: str,
    expected_body: Mapping[str, object],
    expected_status: int,
    counts_before: Mapping[str, int],
    administrator,
    project_id: str,
    *,
    method: str = "POST",
) -> dict[str, Any]:
    replay = command(
        opener,
        base_url,
        csrf_token,
        path,
        payload,
        key,
        method=method,
        expected_status=expected_status,
        replayed=True,
    )
    require(
        replay.body == expected_body
        and readiness_counts(administrator, base_url, project_id) == counts_before,
        "P7-05 same-process readiness replay changed sealed response truth",
    )
    return _json_object(replay.body, "P7-05 replay response")


def verify_gate_input_drift(
    initial: Mapping[str, object],
    final: Mapping[str, object],
    initial_revision: Mapping[str, object],
    final_revision: Mapping[str, object],
) -> None:
    initial_dependencies = initial.get("dependencies")
    final_dependencies = final.get("dependencies")
    require(
        isinstance(initial_dependencies, list)
        and isinstance(final_dependencies, list),
        "P7-05 Gate dependency collection is invalid",
    )
    initial_dependency = [
        value
        for value in initial_dependencies
        if isinstance(value, dict)
        and value.get("kind") == "gate_input_snapshot"
        and value.get("globalId") == initial_revision.get("globalId")
    ]
    final_dependency = [
        value
        for value in final_dependencies
        if isinstance(value, dict)
        and value.get("kind") == "gate_input_snapshot"
        and value.get("globalId") == final_revision.get("globalId")
    ]
    initial_remaining = [
        value for value in initial_dependencies if value not in initial_dependency
    ]
    final_remaining = [
        value for value in final_dependencies if value not in final_dependency
    ]
    initial_p0 = _item(initial_revision, "p0_hold")
    final_p0 = _item(final_revision, "p0_hold")
    initial_readiness_blockers = [
        value
        for value in initial.get("blockers", [])
        if isinstance(value, dict) and value.get("state") == "readiness_incomplete_p0"
    ]
    final_readiness_blockers = [
        value
        for value in final.get("blockers", [])
        if isinstance(value, dict) and value.get("state") == "readiness_incomplete_p0"
    ]
    expected_readiness_blocker = {
        "globalId": initial_p0.get("globalId"),
        "version": 1,
        "state": "readiness_incomplete_p0",
        "blocking": True,
        "terminal": False,
    }
    require(
        len(initial_dependency) == 1
        and len(final_dependency) == 1
        and len(initial_dependencies) == len(final_dependencies)
        and initial_remaining == final_remaining
        and initial_dependency[0].get("kind") == "gate_input_snapshot"
        and final_dependency[0].get("kind") == "gate_input_snapshot"
        and initial_dependency[0].get("globalId")
        == initial_revision.get("globalId")
        and final_dependency[0].get("globalId") == final_revision.get("globalId")
        and initial_dependency[0].get("version") == 1
        and initial_dependency[0].get("snapshotHash")
        == initial_revision.get("snapshotHash")
        and final_dependency[0].get("version") == 4
        and final_dependency[0].get("snapshotHash") == final_revision.get("snapshotHash")
        and initial.get("gateInputHash") != final.get("gateInputHash")
        and initial.get("gateAuthoritySnapshot") == final.get("gateAuthoritySnapshot")
        and initial.get("gateOptimisticVersion") == final.get("gateOptimisticVersion")
        and initial.get("gateState") == final.get("gateState"),
        "P7-05 Gate input drift mutated Gate authority",
    )
    require(
        initial_p0.get("globalId") == final_p0.get("globalId")
        and initial_p0.get("itemVersion") == 1
        and final_p0.get("itemVersion") == 1
        and initial_readiness_blockers == [expected_readiness_blocker]
        and final_readiness_blockers == [expected_readiness_blocker],
        "P7-05 Gate input did not retain the one exact incomplete P0 blocker",
    )


def verify_generic_mutation_denial(
    actor,
    base_url: str,
    csrf_token: str,
    project_id: str,
) -> None:
    specs = (
        ("NPI Readiness Template", [["template_code", "=", TEMPLATE_CODE]]),
        ("NPI Readiness Template Version", [["template_code", "=", TEMPLATE_CODE]]),
        (
            "NPI Readiness Instance Revision",
            [["project_global_id", "=", project_id]],
        ),
        (
            "NPI Readiness Command Idempotency",
            [["actor_user_id", "=", ACTOR_USER]],
        ),
    )
    for doctype, filters in specs:
        rows = list_resources(
            actor,
            base_url,
            doctype,
            filters=filters,
            fields=["name", READINESS_PROTECTED_FIELDS[doctype]],
        )
        require(bool(rows), f"P7-05 protected row is unavailable: {doctype}")
        name = str(rows[0]["name"])
        protected = READINESS_PROTECTED_FIELDS[doctype]
        retained = get_resource(actor, base_url, doctype, name)
        require(retained.status == 200, f"P7-05 protected row read failed: {doctype}")
        before = _json_object(retained.body.get("data"), f"P7-05 {doctype} row")
        old_value = str(before[protected])
        forged = (
            f"{old_value}-forged"
            if protected == "template_code"
            else ("0" if old_value[0] != "0" else "1") + old_value[1:]
        )
        rejected_update = update_resource(
            actor,
            base_url,
            doctype,
            name,
            {protected: forged},
            csrf_token,
        )
        require(
            rejected_update.status in {403, 417},
            f"P7-05 generic update guard failed for {doctype}",
        )
        rejected_delete = delete_resource(
            actor,
            base_url,
            doctype,
            name,
            csrf_token,
        )
        require(
            rejected_delete.status in {403, 417},
            f"P7-05 generic delete guard failed for {doctype}",
        )
        after = get_resource(actor, base_url, doctype, name)
        require(
            after.status == 200 and after.body.get("data") == before,
            f"P7-05 rejected generic mutation changed {doctype}",
        )


def verify_project_first_idor(
    actor,
    base_url: str,
    csrf_token: str,
    *,
    second_project_id: str,
    target_instance_id: str,
    payload: dict[str, object],
    administrator,
    target_project_id: str,
) -> None:
    before = readiness_counts(administrator, base_url, target_project_id)
    cross_project = command(
        actor,
        base_url,
        csrf_token,
        readiness_path(second_project_id, target_instance_id),
        payload,
        IDOR_REVISE_KEY,
        expected_status=404,
    )
    validate_problem(cross_project, 404, "READINESS_UNAVAILABLE")
    absent = command(
        actor,
        base_url,
        csrf_token,
        readiness_path(second_project_id, ABSENT_INSTANCE_ID),
        payload,
        f"{IDOR_REVISE_KEY}-absent",
        expected_status=404,
    )
    validate_problem(absent, 404, "READINESS_UNAVAILABLE")
    stable_fields = ("status", "code", "title", "detail", "retryable")
    require(
        {key: cross_project.body.get(key) for key in stable_fields}
        == {key: absent.body.get(key) for key in stable_fields}
        and readiness_counts(administrator, base_url, target_project_id) == before,
        "P7-05 Project-first IDOR boundary disclosed a secondary identifier",
    )


def verify_downstream_unchanged(
    before: Mapping[str, object], after: Mapping[str, object]
) -> dict[str, bool]:
    before_counts = before.get("downstreamCounts")
    after_counts = after.get("downstreamCounts")
    before_digests = before.get("downstreamDigests")
    after_digests = after.get("downstreamDigests")
    require(
        before_counts == after_counts and before_digests == after_digests,
        "P7-05 controlled readiness mutated retained downstream truth",
    )
    require(
        isinstance(before_counts, dict)
        and before_counts.get("NPI Outbox Message")
        == after_counts.get("NPI Outbox Message")
        and before_counts.get("NPI Inbox Message")
        == after_counts.get("NPI Inbox Message"),
        "P7-05 controlled readiness created ERP integration traffic",
    )
    require(
        before.get("sourcePreparationAuditCounts")
        == after.get("sourcePreparationAuditCounts")
        and before.get("sourcePreparationAuditDigests")
        == after.get("sourcePreparationAuditDigests"),
        "P7-05 controlled readiness changed source-preparation audit history",
    )
    return {
        "readinessIntegrationTrafficCreated": False,
        "readinessGateMutationCreated": False,
        "readinessTrialMutationCreated": False,
        "readinessWorkItemMutationCreated": False,
        "readinessToolingMutationCreated": False,
    }


def verify_source_preparation_scope(
    before: Mapping[str, object], after: Mapping[str, object]
) -> dict[str, object]:
    """Prove the explicit fixture extension and reject every adjacent mutation."""

    stable_context_fields = {
        "customerReferenceKeys",
        "fixtureRunId",
        "gateGlobalId",
        "gateKey",
        "gateOptimisticVersion",
        "memberGlobalId",
        "memberOptimisticVersion",
        "projectGlobalId",
        "projectOptimisticVersion",
        "projectType",
        "secondProjectGlobalId",
    }
    require(
        stable_context_fields <= set(before)
        and stable_context_fields <= set(after)
        and {key: before.get(key) for key in stable_context_fields}
        == {key: after.get(key) for key in stable_context_fields},
        "P7-05 source fixture preparation changed Project/member/Gate context",
    )
    before_counts = before.get("downstreamCounts")
    after_counts = after.get("downstreamCounts")
    before_digests = before.get("downstreamDigests")
    after_digests = after.get("downstreamDigests")
    before_audit_counts = before.get("sourcePreparationAuditCounts")
    after_audit_counts = after.get("sourcePreparationAuditCounts")
    before_audit_digests = before.get("sourcePreparationAuditDigests")
    after_audit_digests = after.get("sourcePreparationAuditDigests")
    require(
        isinstance(before_counts, dict)
        and isinstance(after_counts, dict)
        and isinstance(before_digests, dict)
        and isinstance(after_digests, dict)
        and isinstance(before_audit_counts, dict)
        and isinstance(after_audit_counts, dict)
        and isinstance(before_audit_digests, dict)
        and isinstance(after_audit_digests, dict)
        and set(before_counts) == set(after_counts) == set(before_digests)
        == set(after_digests),
        "P7-05 source fixture persistence inventory drifted",
    )
    allowed_count_deltas = {
        "tooling:NPI Tooling Capacity Scenario Revision": 1,
        "tooling:NPI Tooling Command Idempotency": 1,
        "trial:NPI Trial Round": 0,
        "trial:NPI Trial Round Lifecycle Event": 1,
        "trial:NPI Trial Command Idempotency": 3,
        "trial:NPI Trial Round Comparison Snapshot": 1,
        "trial:NPI Trial Review Reference Revision": 1,
        "trial:NPI Trial Conclusion Revision": 1,
    }
    require(
        set(allowed_count_deltas) | {"NPI Outbox Message", "NPI Inbox Message"}
        <= set(before_counts),
        "P7-05 source fixture persistence inventory is incomplete",
    )
    for key in before_counts:
        expected_delta = allowed_count_deltas.get(key, 0)
        require(
            int(after_counts[key]) - int(before_counts[key]) == expected_delta,
            f"P7-05 source fixture changed an unauthorized collection: {key}",
        )
        if key in allowed_count_deltas:
            require(
                after_digests[key] != before_digests[key],
                f"P7-05 source fixture did not append its declared history: {key}",
            )
        else:
            require(
                after_digests[key] == before_digests[key],
                f"P7-05 source fixture rewrote adjacent truth: {key}",
            )
    require(
        set(before_audit_counts)
        == set(after_audit_counts)
        == set(before_audit_digests)
        == set(after_audit_digests)
        == {
            "toolingCapacity",
            "trialComparison",
            "trialReference",
            "trialReopen",
        }
        and all(
            int(after_audit_counts[key]) - int(before_audit_counts[key]) == 1
            and after_audit_digests[key] != before_audit_digests[key]
            for key in before_audit_counts
        ),
        "P7-05 source fixture preparation audit history drifted",
    )
    require(
        before_counts["NPI Outbox Message"] == after_counts["NPI Outbox Message"]
        and before_counts["NPI Inbox Message"]
        == after_counts["NPI Inbox Message"]
        and before_digests["NPI Outbox Message"]
        == after_digests["NPI Outbox Message"]
        and before_digests["NPI Inbox Message"]
        == after_digests["NPI Inbox Message"],
        "P7-05 source fixture preparation created ERP integration traffic",
    )
    return {
        "fixtureCapacityCommandCount": 1,
        "fixtureCapacityScenarioCreated": True,
        "fixtureAuditEventCount": 4,
        "fixtureIntegrationTrafficCreated": False,
        "fixtureSourcePreparationCommandCount": 4,
        "fixtureTrialCommandCount": 3,
        "fixtureTrialHistoryExtended": True,
        "fixtureTrialRoundReopenedToAnalysis": True,
    }


def run_fresh(
    administrator,
    actor,
    unrelated,
    base_url: str,
    administrator_csrf: str,
    actor_csrf: str,
    unrelated_csrf: str,
    fixture_password: str,
) -> dict[str, object]:
    project_id, _project_version = document_runtime.fixture_project(
        administrator, base_url
    )
    schema = run_bench_fixture(
        "verify_readiness_runtime_schema", {"fixture_run_id": FIXTURE_RUN_ID}
    )
    fixture_before_context = run_bench_fixture(
        "readiness_persistence_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    fixture_before_gate = run_bench_fixture(
        "readiness_gate_input_context",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "gate_id": fixture_before_context["gateGlobalId"],
        },
    )
    source_preparation = prepare_readiness_source_fixtures(
        administrator,
        base_url,
        administrator_csrf,
        fixture_password,
    )
    require(
        source_preparation.get("capacitySourcePrepared") is True
        and source_preparation.get("currentTrialReferencePrepared") is True
        and source_preparation.get("sourcePreparationCommandCount") == 4,
        "P7-05 exact source preparation was incomplete",
    )
    context = run_bench_fixture(
        "readiness_persistence_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    fixture_scope = verify_source_preparation_scope(
        fixture_before_context,
        context,
    )
    fixture_after_gate = run_bench_fixture(
        "readiness_gate_input_context",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "gate_id": context["gateGlobalId"],
        },
    )
    require(
        fixture_before_gate == fixture_after_gate,
        "P7-05 source fixture preparation mutated Gate input or authority",
    )
    offline_seam = run_bench_fixture(
        "verify_external_resolver_offline", {"fixture_run_id": FIXTURE_RUN_ID}
    )
    require(
        schema.get("metadataSynchronized") is True
        and offline_seam.get("externalSourceCount") == 5
        and offline_seam.get("repositoryCalls") == 0,
        "P7-05 runtime schema or offline resolver seam drifted",
    )
    before_context = dict(context)
    initial_counts = readiness_counts(administrator, base_url, project_id)
    require(
        all(value == 0 for value in initial_counts.values()),
        "P7-05 readiness namespace was not independently empty",
    )

    create_body = template_payload(context)
    created_result = command(
        actor,
        base_url,
        actor_csrf,
        template_path(),
        create_body,
        TEMPLATE_CREATE_KEY,
        expected_status=201,
    )
    created = _json_object(created_result.body, "P7-05 created template")
    verify_template_response(created, publication_state="draft", optimistic_version=1)
    after_create = readiness_counts(administrator, base_url, project_id)
    _assert_replay(
        actor,
        base_url,
        actor_csrf,
        template_path(),
        create_body,
        TEMPLATE_CREATE_KEY,
        created,
        201,
        after_create,
        administrator,
        project_id,
    )
    actor_bound = command(
        unrelated,
        base_url,
        unrelated_csrf,
        template_path(),
        create_body,
        TEMPLATE_CREATE_KEY,
        expected_status=409,
    )
    validate_problem(actor_bound, 409, "READINESS_VERSION_CONFLICT")
    require(
        readiness_counts(administrator, base_url, project_id) == after_create,
        "P7-05 idempotency receipt crossed the authenticated actor boundary",
    )

    template_id = str(created["templateGlobalId"])
    template_version = int(created["templateVersion"])
    edit_body = edit_template_payload(context, 1)
    edited_result = command(
        actor,
        base_url,
        actor_csrf,
        template_path(template_id, template_version),
        edit_body,
        TEMPLATE_EDIT_KEY,
        method="PUT",
        expected_status=200,
    )
    edited = _json_object(edited_result.body, "P7-05 edited template")
    verify_template_response(edited, publication_state="draft", optimistic_version=2)
    after_edit = readiness_counts(administrator, base_url, project_id)
    _assert_replay(
        actor,
        base_url,
        actor_csrf,
        template_path(template_id, template_version),
        edit_body,
        TEMPLATE_EDIT_KEY,
        edited,
        200,
        after_edit,
        administrator,
        project_id,
        method="PUT",
    )

    publish_body = {"expectedOptimisticVersion": 2}
    published_result = command(
        actor,
        base_url,
        actor_csrf,
        template_path(template_id, template_version, publish=True),
        publish_body,
        TEMPLATE_PUBLISH_KEY,
        expected_status=200,
    )
    published = _json_object(published_result.body, "P7-05 published template")
    verify_template_response(
        published, publication_state="published", optimistic_version=3
    )
    after_publish = readiness_counts(administrator, base_url, project_id)
    _assert_replay(
        actor,
        base_url,
        actor_csrf,
        template_path(template_id, template_version, publish=True),
        publish_body,
        TEMPLATE_PUBLISH_KEY,
        published,
        200,
        after_publish,
        administrator,
        project_id,
    )
    immutable = command(
        actor,
        base_url,
        actor_csrf,
        template_path(template_id, template_version),
        edit_template_payload(context, 3),
        TEMPLATE_IMMUTABLE_KEY,
        method="PUT",
        expected_status=409,
    )
    validate_problem(immutable, 409, "READINESS_TEMPLATE_IMMUTABLE")
    require(
        readiness_counts(administrator, base_url, project_id) == after_publish,
        "P7-05 published template accepted mutation",
    )
    catalog = template_catalog(actor, base_url, project_id)
    retained_templates = [
        value
        for value in catalog["templates"]
        if isinstance(value, dict) and value.get("templateCode") == TEMPLATE_CODE
    ]
    require(
        retained_templates == [published],
        "P7-05 published template catalog truth drifted",
    )

    empty_workspace = readiness_workspace(actor, base_url, project_id)
    require(
        empty_workspace.get("currentRevision") is None
        and empty_workspace.get("revisions") == [],
        "P7-05 Project readiness was not independently initialized",
    )
    initialize_body = initialize_payload(published, context)
    initialized_result = command(
        actor,
        base_url,
        actor_csrf,
        readiness_path(project_id),
        initialize_body,
        INITIALIZE_KEY,
        expected_status=201,
    )
    initialized = _json_object(initialized_result.body, "P7-05 initialized workspace")
    initial_revision = current_revision(initialized)
    require(
        initial_revision.get("instanceVersion") == 1
        and len(initialized.get("revisions", [])) == 1,
        "P7-05 readiness initialization revision drifted",
    )
    verify_initialized_instance(initial_revision, published, context)
    after_initialize = readiness_counts(administrator, base_url, project_id)
    _assert_replay(
        actor,
        base_url,
        actor_csrf,
        readiness_path(project_id),
        initialize_body,
        INITIALIZE_KEY,
        initialized,
        201,
        after_initialize,
        administrator,
        project_id,
    )
    initial_gate = run_bench_fixture(
        "readiness_gate_input_context",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "gate_id": context["gateGlobalId"],
        },
    )
    source_context = run_bench_fixture(
        "readiness_source_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    source_values = source_context.get("internalSources")
    require(
        isinstance(source_values, list)
        and len(source_values) == 16
        and {value.get("kind") for value in source_values if isinstance(value, dict)}
        == set(INTERNAL_SOURCE_KINDS),
        "P7-05 retained internal source fixture drifted",
    )
    internal_sources = [
        _source_request(value, "internal_exact")
        for value in source_values
        if isinstance(value, dict)
    ]
    internal_body = revision_payload(
        initial_revision,
        item_key="internal_exact",
        owner_member_id=str(context["memberGlobalId"]),
        due_date="2027-08-01",
        state="complete",
        confirmation_value=None,
        sources=internal_sources,
    )
    internal_result = command(
        actor,
        base_url,
        actor_csrf,
        readiness_path(project_id, str(initial_revision["instanceGlobalId"])),
        internal_body,
        INTERNAL_REVISE_KEY,
        expected_status=201,
    )
    internal_workspace = _json_object(internal_result.body, "P7-05 internal revision")
    internal_revision = current_revision(internal_workspace)
    verify_internal_sources(internal_revision)
    after_internal = readiness_counts(administrator, base_url, project_id)
    _assert_replay(
        actor,
        base_url,
        actor_csrf,
        readiness_path(project_id, str(initial_revision["instanceGlobalId"])),
        internal_body,
        INTERNAL_REVISE_KEY,
        internal_workspace,
        201,
        after_internal,
        administrator,
        project_id,
    )
    stale = command(
        actor,
        base_url,
        actor_csrf,
        readiness_path(project_id, str(initial_revision["instanceGlobalId"])),
        internal_body,
        STALE_REVISE_KEY,
        expected_status=409,
    )
    validate_problem(stale, 409, "READINESS_VERSION_CONFLICT")
    conflict_body = dict(internal_body)
    conflict_body["dueDate"] = "2027-08-11"
    idempotency_conflict = command(
        actor,
        base_url,
        actor_csrf,
        readiness_path(project_id, str(initial_revision["instanceGlobalId"])),
        conflict_body,
        INTERNAL_REVISE_KEY,
        expected_status=409,
    )
    validate_problem(
        idempotency_conflict, 409, "READINESS_IDEMPOTENCY_CONFLICT"
    )
    require(
        readiness_counts(administrator, base_url, project_id) == after_internal,
        "P7-05 stale or idempotency conflict wrote readiness truth",
    )

    failed_source = source_context.get("failedQualitySource")
    require(isinstance(failed_source, dict), "P7-05 failed quality source is unavailable")
    quality_body = revision_payload(
        internal_revision,
        item_key="quality_hold",
        owner_member_id=str(context["memberGlobalId"]),
        due_date="2027-08-03",
        state="failed",
        confirmation_value="Synthetic readiness confirmation sentinel",
        sources=[_source_request(failed_source, "quality_failed")],
    )
    quality_result = command(
        actor,
        base_url,
        actor_csrf,
        readiness_path(project_id, str(initial_revision["instanceGlobalId"])),
        quality_body,
        QUALITY_REVISE_KEY,
        expected_status=201,
    )
    quality_workspace = _json_object(quality_result.body, "P7-05 quality revision")
    quality_revision = current_revision(quality_workspace)
    quality_item = _item(quality_revision, "quality_hold")
    require(
        quality_item.get("state") == "failed"
        and len(quality_item.get("sources", [])) == 1
        and quality_item["sources"][0].get("state") == "failed",
        "P7-05 failed mandatory quality truth drifted",
    )
    after_quality = readiness_counts(administrator, base_url, project_id)
    _assert_replay(
        actor,
        base_url,
        actor_csrf,
        readiness_path(project_id, str(initial_revision["instanceGlobalId"])),
        quality_body,
        QUALITY_REVISE_KEY,
        quality_workspace,
        201,
        after_quality,
        administrator,
        project_id,
    )

    external_requests = _external_source_requests()
    require(
        all(set(value) == {"requirementKey", "kind"} for value in external_requests),
        "P7-05 external source selection acquired caller identity",
    )
    external_body = revision_payload(
        quality_revision,
        item_key="external_hold",
        owner_member_id=str(context["memberGlobalId"]),
        due_date="2027-08-04",
        state="in_progress",
        confirmation_value=None,
        sources=external_requests,
    )
    external_result = command(
        actor,
        base_url,
        actor_csrf,
        readiness_path(project_id, str(initial_revision["instanceGlobalId"])),
        external_body,
        EXTERNAL_REVISE_KEY,
        expected_status=201,
    )
    final_workspace = _json_object(external_result.body, "P7-05 external revision")
    final_revision = current_revision(final_workspace)
    require(final_revision.get("instanceVersion") == 4, "P7-05 final revision drifted")
    verify_internal_sources(final_revision)
    verify_external_sources_offline(final_workspace)
    verify_high_score_blockers(final_workspace)
    after_external = readiness_counts(administrator, base_url, project_id)
    _assert_replay(
        actor,
        base_url,
        actor_csrf,
        readiness_path(project_id, str(initial_revision["instanceGlobalId"])),
        external_body,
        EXTERNAL_REVISE_KEY,
        final_workspace,
        201,
        after_external,
        administrator,
        project_id,
    )

    invalid_sources = [dict(value) for value in internal_sources]
    invalid_sources[0]["snapshotHash"] = "0" * 64
    rollback_body = revision_payload(
        final_revision,
        item_key="internal_exact",
        owner_member_id=str(context["memberGlobalId"]),
        due_date="2027-08-01",
        state="complete",
        confirmation_value=None,
        sources=invalid_sources,
    )
    rollback = command(
        actor,
        base_url,
        actor_csrf,
        readiness_path(project_id, str(initial_revision["instanceGlobalId"])),
        rollback_body,
        ROLLBACK_REVISE_KEY,
        expected_status=422,
    )
    validate_problem(rollback, 422, "VALIDATION_FAILED")
    require(
        readiness_workspace(actor, base_url, project_id) == final_workspace
        and readiness_counts(administrator, base_url, project_id) == after_external,
        "P7-05 readiness conflict did not roll back",
    )
    idor_body = revision_payload(
        final_revision,
        item_key="external_hold",
        owner_member_id=str(context["memberGlobalId"]),
        due_date="2027-08-04",
        state="in_progress",
        confirmation_value=None,
        sources=_external_source_requests(),
    )
    verify_project_first_idor(
        actor,
        base_url,
        actor_csrf,
        second_project_id=str(context["secondProjectGlobalId"]),
        target_instance_id=str(initial_revision["instanceGlobalId"]),
        payload=idor_body,
        administrator=administrator,
        target_project_id=project_id,
    )
    verify_generic_mutation_denial(actor, base_url, actor_csrf, project_id)

    final_gate = run_bench_fixture(
        "readiness_gate_input_context",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "gate_id": context["gateGlobalId"],
        },
    )
    verify_gate_input_drift(initial_gate, final_gate, initial_revision, final_revision)
    after_context = run_bench_fixture(
        "readiness_persistence_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    zero_effects = verify_downstream_unchanged(before_context, after_context)
    final_counts = readiness_counts(administrator, base_url, project_id)
    expected_counts = {
        "NPI Readiness Template": 1,
        "NPI Readiness Template Version": 1,
        "NPI Readiness Instance Revision": 4,
        "NPI Readiness Command Idempotency": 7,
        "audit:readiness_template.create": 1,
        "audit:readiness_template.edit": 1,
        "audit:readiness_template.publish": 1,
        "audit:readiness_instance.initialize": 1,
        "audit:readiness_instance.revise": 3,
    }
    require(final_counts == expected_counts, "P7-05 readiness authority cardinality drifted")
    return {
        "blockerCount": 3,
        "externalOfflineSourceCount": 5,
        "idempotentReplay": True,
        "internalExactSourceCount": 16,
        "metadataSynchronized": True,
        "readinessRevisionCount": 4,
        "scoreBasisPoints": 9700,
        **fixture_scope,
        **zero_effects,
    }


def run_replay(
    administrator,
    actor,
    base_url: str,
    actor_csrf: str,
) -> dict[str, object]:
    project_id, _project_version = document_runtime.fixture_project(
        administrator, base_url
    )
    context = run_bench_fixture(
        "readiness_persistence_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    before_context = dict(context)
    before_counts = readiness_counts(administrator, base_url, project_id)
    before_gate = run_bench_fixture(
        "readiness_gate_input_context",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "gate_id": context["gateGlobalId"],
        },
    )
    workspace = readiness_workspace(actor, base_url, project_id)
    history = workspace.get("revisions")
    require(
        isinstance(history, list)
        and len(history) == 4
        and all(isinstance(value, dict) for value in history),
        "P7-05 retained readiness revision chain drifted",
    )
    final_revision = current_revision(workspace)
    verify_internal_sources(final_revision)
    verify_external_sources_offline(workspace)
    verify_high_score_blockers(workspace)
    catalog = template_catalog(actor, base_url, project_id)
    templates = [
        value
        for value in catalog["templates"]
        if isinstance(value, dict) and value.get("templateCode") == TEMPLATE_CODE
    ]
    require(len(templates) == 1, "P7-05 retained published template is unavailable")
    published = dict(templates[0])
    template_id = str(published["templateGlobalId"])
    template_version = int(published["templateVersion"])

    created = command(
        actor,
        base_url,
        actor_csrf,
        template_path(),
        template_payload(context),
        TEMPLATE_CREATE_KEY,
        expected_status=201,
        replayed=True,
    )
    verify_template_response(created.body, publication_state="draft", optimistic_version=1)
    edited = command(
        actor,
        base_url,
        actor_csrf,
        template_path(template_id, template_version),
        edit_template_payload(context, 1),
        TEMPLATE_EDIT_KEY,
        method="PUT",
        expected_status=200,
        replayed=True,
    )
    verify_template_response(edited.body, publication_state="draft", optimistic_version=2)
    published_replay = command(
        actor,
        base_url,
        actor_csrf,
        template_path(template_id, template_version, publish=True),
        {"expectedOptimisticVersion": 2},
        TEMPLATE_PUBLISH_KEY,
        expected_status=200,
        replayed=True,
    )
    require(published_replay.body == published, "P7-05 published replay truth drifted")

    initialized = command(
        actor,
        base_url,
        actor_csrf,
        readiness_path(project_id),
        initialize_payload(published, context),
        INITIALIZE_KEY,
        expected_status=201,
        replayed=True,
    )
    require(
        initialized.body.get("currentRevision") == history[0]
        and initialized.body.get("revisions") == history[:1],
        "P7-05 initialization replay lost sealed historic truth",
    )
    source_context = run_bench_fixture(
        "readiness_source_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    source_values = source_context.get("internalSources")
    failed_source = source_context.get("failedQualitySource")
    require(
        isinstance(source_values, list)
        and len(source_values) == 16
        and isinstance(failed_source, dict),
        "P7-05 replay source fixture drifted",
    )
    internal_body = revision_payload(
        history[0],
        item_key="internal_exact",
        owner_member_id=str(context["memberGlobalId"]),
        due_date="2027-08-01",
        state="complete",
        confirmation_value=None,
        sources=[
            _source_request(value, "internal_exact")
            for value in source_values
            if isinstance(value, dict)
        ],
    )
    internal = command(
        actor,
        base_url,
        actor_csrf,
        readiness_path(project_id, str(history[0]["instanceGlobalId"])),
        internal_body,
        INTERNAL_REVISE_KEY,
        expected_status=201,
        replayed=True,
    )
    require(
        internal.body.get("currentRevision") == history[1]
        and internal.body.get("revisions") == history[:2],
        "P7-05 internal-source replay lost sealed historic truth",
    )
    quality_body = revision_payload(
        history[1],
        item_key="quality_hold",
        owner_member_id=str(context["memberGlobalId"]),
        due_date="2027-08-03",
        state="failed",
        confirmation_value="Synthetic readiness confirmation sentinel",
        sources=[_source_request(failed_source, "quality_failed")],
    )
    quality = command(
        actor,
        base_url,
        actor_csrf,
        readiness_path(project_id, str(history[0]["instanceGlobalId"])),
        quality_body,
        QUALITY_REVISE_KEY,
        expected_status=201,
        replayed=True,
    )
    require(
        quality.body.get("currentRevision") == history[2]
        and quality.body.get("revisions") == history[:3],
        "P7-05 quality replay lost sealed historic truth",
    )
    external_body = revision_payload(
        history[2],
        item_key="external_hold",
        owner_member_id=str(context["memberGlobalId"]),
        due_date="2027-08-04",
        state="in_progress",
        confirmation_value=None,
        sources=_external_source_requests(),
    )
    external = command(
        actor,
        base_url,
        actor_csrf,
        readiness_path(project_id, str(history[0]["instanceGlobalId"])),
        external_body,
        EXTERNAL_REVISE_KEY,
        expected_status=201,
        replayed=True,
    )
    after_context = run_bench_fixture(
        "readiness_persistence_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    after_gate = run_bench_fixture(
        "readiness_gate_input_context",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "gate_id": context["gateGlobalId"],
        },
    )
    require(
        external.body == workspace
        and readiness_counts(administrator, base_url, project_id) == before_counts
        and before_context == after_context
        and before_gate == after_gate,
        "P7-05 cross-process readiness replay changed sealed truth or cardinality",
    )
    return {
        "crossProcessReplay": True,
        "externalOfflineSourceCount": 5,
        "internalExactSourceCount": 16,
        "readinessRevisionCount": 4,
        "scoreBasisPoints": 9700,
    }


def _retained_route_ids(administrator, base_url: str, project_id: str) -> tuple[str, int, str]:
    templates = list_resources(
        administrator,
        base_url,
        "NPI Readiness Template Version",
        filters=[["template_code", "=", TEMPLATE_CODE]],
        fields=["template_global_id", "template_version"],
    )
    revisions = list_resources(
        administrator,
        base_url,
        "NPI Readiness Instance Revision",
        filters=[["project_global_id", "=", project_id]],
        fields=["instance_global_id"],
    )
    require(
        len(templates) == 1 and len(revisions) == 4,
        "P7-05 retained route-probe identity context drifted",
    )
    instance_ids = {str(value["instance_global_id"]) for value in revisions}
    require(len(instance_ids) == 1, "P7-05 route-probe instance identity drifted")
    return (
        str(templates[0]["template_global_id"]),
        int(templates[0]["template_version"]),
        next(iter(instance_ids)),
    )


def route_disable_probe(
    administrator,
    actor,
    base_url: str,
    actor_csrf: str,
    *,
    expected_mode: str,
) -> dict[str, object]:
    require(expected_mode in {"disabled", "recovered"}, "P7-05 route mode drifted")
    project_id, _project_version = document_runtime.fixture_project(
        administrator, base_url
    )
    template_id, template_version, instance_id = _retained_route_ids(
        administrator, base_url, project_id
    )
    before_counts = readiness_counts(administrator, base_url, project_id)
    before_context = run_bench_fixture(
        "readiness_persistence_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    before_gate = run_bench_fixture(
        "readiness_gate_input_context",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "gate_id": before_context["gateGlobalId"],
        },
    )
    cases: tuple[tuple[str, str, dict[str, object] | None, str | None], ...] = (
        ("GET", f"{template_path()}?projectId={project_id}", None, None),
        ("POST", template_path(), {}, "template-create"),
        (
            "PUT",
            template_path(template_id, template_version),
            {},
            "template-edit",
        ),
        (
            "POST",
            template_path(template_id, template_version, publish=True),
            {},
            "template-publish",
        ),
        ("GET", readiness_path(project_id), None, None),
        ("POST", readiness_path(project_id), {}, "initialize"),
        (
            "POST",
            readiness_path(project_id, instance_id),
            {},
            "revise",
        ),
    )
    for index, (method, path, payload, suffix) in enumerate(cases):
        result = readiness_request(
            actor,
            base_url,
            path,
            method=method,
            payload=payload,
            csrf_token=actor_csrf,
            idempotency_key=(
                f"p7-05-route-{FIXTURE_RUN_ID}-{expected_mode}-{suffix}"
                if suffix is not None
                else None
            ),
            query_key=f"route-{expected_mode}-{index}",
        )
        require_safe_payload(result.body, "P7-05 route probe")
        if expected_mode == "disabled":
            validate_problem(result, 503, "READINESS_ROUTES_DISABLED")
        elif method == "GET":
            require(result.status == 200, "P7-05 recovered GET route did not reopen")
        else:
            validate_problem(result, 422, "VALIDATION_FAILED")
            require(
                result.headers.get("Idempotency-Replayed") == "false",
                "P7-05 recovered command route reported a false replay",
            )
    after_context = run_bench_fixture(
        "readiness_persistence_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    after_gate = run_bench_fixture(
        "readiness_gate_input_context",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "gate_id": before_context["gateGlobalId"],
        },
    )
    require(
        readiness_counts(administrator, base_url, project_id) == before_counts
        and before_context == after_context
        and before_gate == after_gate,
        "P7-05 route probe mutated retained readiness or Gate truth",
    )
    return {"routeCount": 7, "routeMode": expected_mode, "stateChanged": False}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the controlled P7-05 NPI readiness runtime.",
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
            "P7-05 Bench fixture arguments are invalid",
        )
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "P7-05 fixture kwargs are invalid")
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return

    require(
        isinstance(arguments.base_url, str)
        and arguments.fixture_kwargs is None
        and document_runtime.CALLER_SUPPLIED_FIXTURE_RUN_ID is not None
        and os.environ.get("NPI_DOCUMENT_RUNTIME_RUN_ID") == FIXTURE_RUN_ID,
        "P7-05 runtime base URL and fixture namespace are required",
    )
    require(
        int(arguments.route_disable_probe is not None) + int(arguments.replay_only)
        <= 1,
        "P7-05 runtime modes are mutually exclusive",
    )
    base_url = validate_local_fixture_inputs(
        arguments.base_url, "Administrator", ACTOR_USER
    )
    validate_local_fixture_inputs(base_url, "Administrator", UNRELATED_USER)
    require(
        ACTOR_USER.endswith("@example.invalid")
        and UNRELATED_USER.endswith("@example.invalid")
        and ACTOR_USER != UNRELATED_USER
        and FIXTURE_RUN_ID != "0" * 32,
        "P7-05 runtime fixture identity drifted",
    )
    administrator_password = secret_from_environment(
        "NPI_RUNTIME_ADMINISTRATOR_PASSWORD"
    )
    fixture_password = secret_from_environment("NPI_RUNTIME_FIXTURE_PASSWORD")
    administrator = login(base_url, "Administrator", administrator_password)
    administrator_csrf = bootstrap_csrf(administrator, base_url, "Administrator")
    prepare_runtime_users(
        administrator,
        base_url,
        administrator_csrf,
        fixture_password,
    )
    actor = login(base_url, ACTOR_USER, fixture_password)
    actor_csrf = bootstrap_csrf(actor, base_url, ACTOR_USER)
    if arguments.route_disable_probe is not None:
        result = route_disable_probe(
            administrator,
            actor,
            base_url,
            actor_csrf,
            expected_mode=arguments.route_disable_probe,
        )
    elif arguments.replay_only:
        result = run_replay(administrator, actor, base_url, actor_csrf)
    else:
        unrelated = login(base_url, UNRELATED_USER, fixture_password)
        unrelated_csrf = bootstrap_csrf(unrelated, base_url, UNRELATED_USER)
        result = run_fresh(
            administrator,
            actor,
            unrelated,
            base_url,
            administrator_csrf,
            actor_csrf,
            unrelated_csrf,
            fixture_password,
        )
    require_safe_payload(result, "P7-05 sanitized verifier evidence")
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
