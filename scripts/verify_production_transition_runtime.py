from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import verify_document_runtime as document_runtime
import verify_readiness_runtime as readiness_runtime
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
    create_resource,
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
ACTOR_USER = readiness_runtime.ACTOR_USER
UNRELATED_USER = readiness_runtime.UNRELATED_USER
ACKNOWLEDGEMENT_USER = document_runtime.BASELINE_USER

POLICY_CODE = f"P706-{FIXTURE_RUN_ID[:16].upper()}"
POLICY_SENTINEL = "P706-POLICY-SENTINEL"
HANDOVER_SENTINEL = "P706-HANDOVER-SENTINEL"
OBSERVATION_SENTINEL = "P706-OBSERVATION-SENTINEL"

SOURCE_KINDS = (
    "readiness_instance_revision",
    "domain_work_item",
    "released_document",
    "release_baseline",
    "file_revision",
    "tooling_capacity_scenario",
    "trial_defect_revision",
    "trial_review_reference",
    "trial_conclusion",
)
POLICY_PROVIDER_ORDER = (
    "actual_sop",
    "customer_complaint",
    "first_batch_yield",
    "production_cycle_time",
    "tooling_stability",
)
PROVIDER_RESPONSE_ORDER = (
    "actual_sop",
    "first_batch_yield",
    "customer_complaint",
    "production_cycle_time",
    "tooling_stability",
)
PROVIDER_REASON_CODES = {
    value: f"{value}_provider_unavailable" for value in PROVIDER_RESPONSE_ORDER
}

TRANSITION_DOCTYPES = (
    "NPI Production Transition Policy",
    "NPI Production Transition Policy Version",
    "NPI Handover Package Revision",
    "NPI Handover Acknowledgement",
    "NPI Observation Period Revision",
    "NPI Production Transition Command Idempotency",
)
TRANSITION_OPERATIONS = (
    "production_transition_policy.create",
    "production_transition_policy.edit",
    "production_transition_policy.publish",
    "production_transition_policy.next_version",
    "production_handover.create",
    "production_handover.revise",
    "production_handover.acknowledge",
    "observation_period.create",
    "observation_period.revise",
)
PROTECTED_FIELDS = {
    "NPI Production Transition Policy": "policy_code",
    "NPI Production Transition Policy Version": "snapshot_hash",
    "NPI Handover Package Revision": "snapshot_hash",
    "NPI Handover Acknowledgement": "snapshot_hash",
    "NPI Observation Period Revision": "snapshot_hash",
    "NPI Production Transition Command Idempotency": "payload_hash",
}

CREATE_POLICY_KEY = f"p7-06-runtime-{FIXTURE_RUN_ID}-policy-create"
EDIT_POLICY_KEY = f"p7-06-runtime-{FIXTURE_RUN_ID}-policy-edit"
PUBLISH_POLICY_KEY = f"p7-06-runtime-{FIXTURE_RUN_ID}-policy-publish"
IMMUTABLE_POLICY_KEY = f"p7-06-runtime-{FIXTURE_RUN_ID}-policy-immutable"
HANDOVER_V1_KEY = f"p7-06-runtime-{FIXTURE_RUN_ID}-handover-v1"
HANDOVER_V2_KEY = f"p7-06-runtime-{FIXTURE_RUN_ID}-handover-v2"
ACK_V1_KEYS = {
    key: f"p7-06-runtime-{FIXTURE_RUN_ID}-ack-v1-{key}"
    for key in ("sender", "receiver")
}
ACK_V2_KEYS = {
    key: f"p7-06-runtime-{FIXTURE_RUN_ID}-ack-v2-{key}"
    for key in ("sender", "receiver")
}
OBSERVATION_V1_KEY = f"p7-06-runtime-{FIXTURE_RUN_ID}-observation-v1"
OBSERVATION_V2_KEY = f"p7-06-runtime-{FIXTURE_RUN_ID}-observation-v2"
STALE_HANDOVER_KEY = f"p7-06-runtime-{FIXTURE_RUN_ID}-stale-handover"
STALE_ACK_KEY = f"p7-06-runtime-{FIXTURE_RUN_ID}-stale-ack"
STALE_OBSERVATION_KEY = f"p7-06-runtime-{FIXTURE_RUN_ID}-stale-observation"
ROLLBACK_OBSERVATION_KEY = f"p7-06-runtime-{FIXTURE_RUN_ID}-rollback-observation"
ABSENT_ID = "00000000-0000-4000-8000-000000000706"

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_SYSTEM_FIELDS = {
    "creation",
    "docstatus",
    "doctype",
    "idx",
    "modified",
    "modified_by",
    "name",
    "owner",
    "parent",
    "parentfield",
    "parenttype",
}


def policy_path(
    policy_id: str | None = None,
    policy_version: int | None = None,
    *,
    publish: bool = False,
    next_version: bool = False,
) -> str:
    base = "/api/npi/v1/production-transition/policies"
    if policy_id is None:
        require(
            policy_version is None and not publish and not next_version,
            "P7-06 policy path is invalid",
        )
        return base
    if next_version:
        require(
            policy_version is None and not publish,
            "P7-06 next policy path is invalid",
        )
        return f"{base}/{policy_id}/versions"
    require(
        isinstance(policy_version, int) and policy_version > 0,
        "P7-06 policy version path is invalid",
    )
    path = f"{base}/{policy_id}/versions/{policy_version}"
    return f"{path}:publish" if publish else path


def workspace_path(project_id: str) -> str:
    return f"/api/npi/v1/projects/{project_id}/production-transition"


def handover_path(
    project_id: str,
    handover_id: str | None = None,
    handover_version: int | None = None,
) -> str:
    base = f"/api/npi/v1/projects/{project_id}/production-handover"
    if handover_id is None:
        require(handover_version is None, "P7-06 handover path is invalid")
        return base
    path = f"{base}/{handover_id}/revisions"
    if handover_version is None:
        return path
    require(handover_version > 0, "P7-06 acknowledgement path is invalid")
    return f"{path}/{handover_version}/acknowledgements"


def observation_path(project_id: str, observation_id: str | None = None) -> str:
    base = f"/api/npi/v1/projects/{project_id}/observation-periods"
    return base if observation_id is None else f"{base}/{observation_id}/revisions"


def transition_request(
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
        else document_runtime.query_headers(f"p706-{query_key}-{uuid4().hex}")
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
        "P7-06 request identity was not echoed",
    )
    require(
        result.headers.get("Cache-Control") == "private, no-store",
        "P7-06 private no-store response drifted",
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
    result = transition_request(
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
        f"P7-06 command returned HTTP {result.status}",
    )
    require_safe_payload(result.body, "P7-06 command response")
    return result


def require_safe_payload(value: object, label: str) -> None:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    folded = serialized.casefold()
    require(
        "/private/files/" not in folded
        and '"fileurl"' not in folded
        and '"password"' not in folded
        and '"secret"' not in folded
        and '"token"' not in folded,
        f"{label} exposed a sensitive value or private path",
    )


def _object(value: object, label: str) -> dict[str, Any]:
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


def policy_definition(context: Mapping[str, object]) -> dict[str, object]:
    dispositions = ["not_evaluable", "within_rule", "outside_rule"]
    metric_rules = {
        "customer_complaint": ("count", "less_than_or_equal", "1"),
        "first_batch_yield": ("percent", "greater_than_or_equal", "95"),
        "production_cycle_time": ("second", "less_than_or_equal", "60"),
        "tooling_stability": ("count", "less_than_or_equal", "0"),
    }
    observation_rules = []
    for kind in POLICY_PROVIDER_ORDER:
        if kind == "actual_sop":
            observation_rules.append(
                {
                    "providerKind": kind,
                    "unit": None,
                    "comparator": None,
                    "threshold": None,
                    "allowedDispositions": ["not_evaluable"],
                }
            )
        else:
            unit, comparator, threshold = metric_rules[kind]
            observation_rules.append(
                {
                    "providerKind": kind,
                    "unit": unit,
                    "comparator": comparator,
                    "threshold": threshold,
                    "allowedDispositions": dispositions,
                }
            )
    return {
        "applicability": {
            "projectTypes": [context["projectType"]],
            "projectGlobalIds": [context["projectGlobalId"]],
            "customerReferenceKeys": [],
        },
        "receivingGroups": [
            {"key": "npi_sender", "title": "NPI sender group"},
            {
                "key": "production_receiver",
                "title": "Production receiving group",
            },
        ],
        "acknowledgementSlots": [
            {
                "key": "sender",
                "groupKey": "npi_sender",
                "direction": "sender",
                "allowedProjectRoleKeys": [document_runtime.BASELINE_ROLE_KEY],
            },
            {
                "key": "receiver",
                "groupKey": "production_receiver",
                "direction": "receiver",
                "allowedProjectRoleKeys": [document_runtime.BASELINE_ROLE_KEY],
            },
        ],
        "handoverRequirements": [
            {
                "key": f"requirement_{kind}",
                "acceptedSourceKinds": [kind],
                "manifestRole": f"controlled_{kind}",
                "minimumCount": 1,
            }
            for kind in SOURCE_KINDS
        ],
        "observationSourceRules": observation_rules,
        "observationWindowDays": 30,
    }


def create_policy_payload(context: Mapping[str, object]) -> dict[str, object]:
    return {
        "policyCode": POLICY_CODE,
        "title": POLICY_SENTINEL,
        "definition": policy_definition(context),
    }


def edit_policy_payload(
    context: Mapping[str, object], optimistic_version: int
) -> dict[str, object]:
    return {
        "expectedOptimisticVersion": optimistic_version,
        "title": f"{POLICY_SENTINEL}-EDITED",
        "definition": policy_definition(context),
    }


def policy_reference(policy: Mapping[str, object]) -> dict[str, object]:
    return {
        "policyGlobalId": _uuid(policy.get("policyGlobalId"), "policy reference"),
        "policyVersion": int(policy.get("policyVersion") or 0),
        "policySnapshotHash": _hash(
            policy.get("snapshotHash"), "policy reference"
        ),
    }


def source_request(source: Mapping[str, object]) -> dict[str, object]:
    return {
        "kind": source["kind"],
        "globalId": source["globalId"],
        "expectedVersion": source["expectedVersion"],
    }


def handover_content(
    context: Mapping[str, object],
    policy: Mapping[str, object],
    sources: Sequence[Mapping[str, object]],
    *,
    version: int,
) -> dict[str, object]:
    assignments = [
        {
            "slotKey": slot,
            "memberGlobalId": context["memberGlobalId"],
            "memberExpectedVersion": context["memberOptimisticVersion"],
            "roleAssignmentGlobalId": context["roleAssignmentGlobalId"],
            "roleExpectedVersion": context["roleOptimisticVersion"],
        }
        for slot in ("sender", "receiver")
    ]
    manifest = [
        {
            "requirementKey": f"requirement_{source['kind']}",
            **source_request(source),
        }
        for source in sources
    ]
    return {
        "expectedProjectVersion": context["projectOptimisticVersion"],
        "policy": policy_reference(policy),
        "slotAssignments": assignments,
        "manifestSources": manifest,
        "reason": f"{HANDOVER_SENTINEL}-V{version}",
    }


def acknowledgement_payload(
    package: Mapping[str, object], slot_key: str
) -> dict[str, object]:
    return {
        "expectedRevisionGlobalId": package["globalId"],
        "expectedSnapshotHash": package["snapshotHash"],
        "slotKey": slot_key,
        "intent": "acknowledge",
    }


def handover_reference(package: Mapping[str, object]) -> dict[str, object]:
    return {
        "handoverGlobalId": package["handoverGlobalId"],
        "handoverVersion": package["handoverVersion"],
        "handoverRevisionGlobalId": package["globalId"],
        "handoverSnapshotHash": package["snapshotHash"],
    }


def observation_create_payload(
    context: Mapping[str, object],
    policy: Mapping[str, object],
    package: Mapping[str, object],
    sources: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    return {
        "expectedProjectVersion": context["projectOptimisticVersion"],
        "policy": policy_reference(policy),
        "handover": handover_reference(package),
        "contextSources": [source_request(value) for value in sources],
        "retrospectiveSources": [],
        "retrospectiveNote": None,
        "reason": f"{OBSERVATION_SENTINEL}-V1",
    }


def observation_revision_payload(
    current: Mapping[str, object],
    repeated_source: Mapping[str, object],
) -> dict[str, object]:
    reference = source_request(repeated_source)
    return {
        "expectedRevisionGlobalId": current["globalId"],
        "expectedSnapshotHash": current["snapshotHash"],
        "contextSources": [deepcopy(reference)],
        "retrospectiveSources": [deepcopy(reference)],
        "retrospectiveNote": OBSERVATION_SENTINEL,
        "reason": f"{OBSERVATION_SENTINEL}-V2",
    }


def _canonical_row_digest(
    frappe, doctype: str, filters: Mapping[str, object]
) -> str:
    rows = frappe.get_all(
        doctype,
        filters=dict(filters),
        fields=["*"],
        order_by="name asc",
        limit_page_length=2_001,
    )
    require(len(rows) <= 2_000, f"P7-06 {doctype} digest collection is unsafe")
    encoded = json.dumps(
        rows,
        default=str,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _snapshot_collection(
    frappe, doctype: str, filters: Mapping[str, object]
) -> dict[str, object]:
    require(frappe.db.table_exists(doctype), f"P7-06 table is unavailable: {doctype}")
    return {
        "count": int(frappe.db.count(doctype, dict(filters))),
        "digest": _canonical_row_digest(frappe, doctype, filters),
    }


def _transition_filters(project_id: str) -> dict[str, dict[str, object]]:
    actors = [ACTOR_USER, UNRELATED_USER, ACKNOWLEDGEMENT_USER]
    return {
        "NPI Production Transition Policy": {"policy_code": POLICY_CODE},
        "NPI Production Transition Policy Version": {"policy_code": POLICY_CODE},
        "NPI Handover Package Revision": {"project_global_id": project_id},
        "NPI Handover Acknowledgement": {"project_global_id": project_id},
        "NPI Observation Period Revision": {"project_global_id": project_id},
        "NPI Production Transition Command Idempotency": {
            "actor_user_id": ["in", actors]
        },
    }


def production_transition_persistence_context(
    fixture_run_id: str, *, project_id: str
) -> dict[str, object]:
    import frappe

    document_runtime._validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "P7-06 persistence fixture namespace drifted",
    )
    project = frappe.get_doc("NPI Engineering Project", project_id)
    require(
        str(project.global_id) == project_id and str(project.tenant_id) == TENANT_ID,
        "P7-06 persistence Project context drifted",
    )
    gate_names = frappe.get_all(
        "NPI Gate Shell",
        filters={
            "project_global_id": project_id,
            "gate_key": document_runtime.GATE_KEY,
        },
        pluck="name",
        limit_page_length=2,
    )
    require(len(gate_names) == 1, "P7-06 retained Gate context drifted")
    gate = frappe.get_doc("NPI Gate Shell", str(gate_names[0]))

    predecessor = readiness_runtime.readiness_persistence_context(
        fixture_run_id, project_id=project_id
    )
    downstream: dict[str, object] = {
        key: {
            "count": predecessor["downstreamCounts"][key],
            "digest": predecessor["downstreamDigests"][key],
        }
        for key in predecessor["downstreamCounts"]
    }
    scoped_specs: dict[str, dict[str, object]] = {
        "NPI Engineering Project": {"global_id": project_id},
        "NPI Project Member": {"project_global_id": project_id},
        "NPI Project Role Assignment": {"project_global_id": project_id},
        "NPI Project Substitution": {"project_global_id": project_id},
        "NPI Project RACI Assignment": {"project_global_id": project_id},
        "NPI Project Follower": {"project_global_id": project_id},
        "NPI Project Activity Event": {"project_global_id": project_id},
        "NPI Project Health Assessment": {"project_global_id": project_id},
        "NPI Project Learning": {"project_global_id": project_id},
        "NPI Project Reference": {
            "parent": str(project.name),
            "parenttype": "NPI Engineering Project",
        },
        "NPI Project Work Idempotency": {"project_global_id": project_id},
        "NPI Domain Work Item": {"project_global_id": project_id},
        "NPI Gate Shell": {"global_id": str(gate.global_id)},
        "NPI Gate Evidence Reference": {"gate_global_id": str(gate.global_id)},
        "NPI Gate Review Cycle": {"gate_global_id": str(gate.global_id)},
        "NPI Gate Review Record": {"gate_global_id": str(gate.global_id)},
        "NPI Gate Review Exception": {"gate_global_id": str(gate.global_id)},
        "NPI Gate Decision Snapshot": {"gate_global_id": str(gate.global_id)},
        "NPI Gate Review Event": {"gate_global_id": str(gate.global_id)},
        "NPI Gate Review Idempotency": {
            "project_global_id": project_id,
            "gate_global_id": str(gate.global_id),
        },
        "NPI Baseline Gate Dependency": {"gate_global_id": str(gate.global_id)},
        "NPI Project Control Binding": {"project_global_id": project_id},
        "NPI Project Control Idempotency": {"project_global_id": project_id},
        "NPI Readiness Template": {"template_code": readiness_runtime.TEMPLATE_CODE},
        "NPI Readiness Template Version": {
            "template_code": readiness_runtime.TEMPLATE_CODE
        },
        "NPI Readiness Instance Revision": {"project_global_id": project_id},
        "NPI Readiness Command Idempotency": {
            "actor_user_id": [
                "in",
                [readiness_runtime.ACTOR_USER, readiness_runtime.UNRELATED_USER],
            ]
        },
    }
    for doctype, filters in scoped_specs.items():
        downstream[f"controlled:{doctype}"] = _snapshot_collection(
            frappe, doctype, filters
        )

    integration_doctypes = frappe.get_all(
        "DocType",
        filters={"module": "NPI Integration", "istable": 0},
        pluck="name",
        order_by="name asc",
        limit_page_length=201,
    )
    require(
        1 <= len(integration_doctypes) <= 200,
        "P7-06 integration inventory is unavailable or unsafe",
    )
    for doctype in integration_doctypes:
        downstream[f"integration:{doctype}"] = _snapshot_collection(
            frappe, str(doctype), {}
        )
    downstream["audit:non-p706"] = _snapshot_collection(
        frappe,
        "NPI Audit Event",
        {"operation": ["not in", list(TRANSITION_OPERATIONS)]},
    )

    transition = {
        doctype: _snapshot_collection(frappe, doctype, filters)
        for doctype, filters in _transition_filters(project_id).items()
    }
    transition_global = {
        doctype: _snapshot_collection(frappe, doctype, {})
        for doctype in TRANSITION_DOCTYPES
    }
    for operation in TRANSITION_OPERATIONS:
        transition[f"audit:{operation}"] = _snapshot_collection(
            frappe,
            "NPI Audit Event",
            {
                "actor": [
                    "in",
                    [ACTOR_USER, UNRELATED_USER, ACKNOWLEDGEMENT_USER],
                ],
                "operation": operation,
            },
        )
        transition_global[f"audit:{operation}"] = _snapshot_collection(
            frappe,
            "NPI Audit Event",
            {"operation": operation},
        )
    return {
        "downstreamSnapshot": downstream,
        "fixtureRunId": fixture_run_id,
        "gateGlobalId": str(gate.global_id),
        "projectGlobalId": project_id,
        "transitionGlobalSnapshot": transition_global,
        "transitionSnapshot": transition,
    }


def production_transition_fixture_context(
    fixture_run_id: str, *, project_id: str
) -> dict[str, object]:
    import frappe

    from npi_core.foundation.security import Principal
    from npi_core.production_transition.frappe_repository import (
        FrappeProductionTransitionRepository,
    )
    from frappe.utils import getdate

    document_runtime._validated_runtime_site()
    require(fixture_run_id == FIXTURE_RUN_ID, "P7-06 fixture namespace drifted")
    project = frappe.get_doc("NPI Engineering Project", project_id)
    member = frappe.get_doc("NPI Project Member", document_runtime.BASELINE_MEMBER_ID)
    role = frappe.get_doc(
        "NPI Project Role Assignment",
        document_runtime.BASELINE_ROLE_ASSIGNMENT_ID,
    )
    user = frappe.get_doc("User", ACKNOWLEDGEMENT_USER)
    user_roles = {str(value.role) for value in user.roles}
    require(
        str(project.global_id) == project_id
        and str(project.tenant_id) == TENANT_ID
        and str(project.lifecycle_state) not in {"cancelled", "completed"}
        and str(member.global_id) == document_runtime.BASELINE_MEMBER_ID
        and str(member.project_global_id) == project_id
        and str(member.user_id).casefold() == ACKNOWLEDGEMENT_USER.casefold()
        and str(role.global_id) == document_runtime.BASELINE_ROLE_ASSIGNMENT_ID
        and str(role.project_global_id) == project_id
        and str(role.member_global_id) == document_runtime.BASELINE_MEMBER_ID
        and str(role.role_key) == document_runtime.BASELINE_ROLE_KEY
        and int(user.enabled) == 1
        and str(user.user_type) == "System User"
        and "NPI API User" in user_roles
        and "System Manager" not in user_roles,
        "P7-06 exact acknowledgement actor/member/role context drifted",
    )
    repository = FrappeProductionTransitionRepository(
        principal=Principal(
            ACTOR_USER,
            roles=frozenset({"NPI API User", "System Manager"}),
            tenant_id=TENANT_ID,
        ),
        request_id=str(uuid4()),
        trace_id=f"trace-{uuid4().hex}",
    )
    unresolved = repository._unresolved_actions(project, for_update=False)
    raw_rows = frappe.get_all(
        "NPI Domain Work Item",
        filters={
            "tenant_id": TENANT_ID,
            "project_global_id": project_id,
            "state_terminal": 0,
        },
        fields=[
            "name",
            "global_id",
            "kind",
            "owner_user_id",
            "due_at",
            "optimistic_version",
        ],
        order_by="global_id asc",
        limit_page_length=10_001,
    )
    allowed_kinds = {"action", "decision_request", "issue", "risk"}
    raw_ids = tuple(str(value.global_id) for value in raw_rows)
    resolved_by_id = {str(value.global_id): value for value in unresolved}
    require(
        len(raw_rows) <= 10_000
        and len(raw_rows) == len(unresolved)
        and raw_ids == tuple(sorted(raw_ids))
        and raw_ids == tuple(str(value.global_id) for value in unresolved)
        and len(set(raw_ids)) == len(raw_ids)
        and all(
            str(row.kind) in allowed_kinds
            and isinstance(row.owner_user_id, str)
            and bool(row.owner_user_id.strip())
            and row.due_at is not None
            and int(row.optimistic_version) >= 1
            and str(resolved_by_id[str(row.global_id)].kind.value) == str(row.kind)
            and resolved_by_id[str(row.global_id)].owner_user_id
            == str(row.owner_user_id).strip().casefold()
            and resolved_by_id[str(row.global_id)].due_date
            == getdate(row.due_at)
            and resolved_by_id[str(row.global_id)].source_version
            == int(row.optimistic_version)
            for row in raw_rows
        ),
        "P7-06 all-nonterminal Work Item preflight drifted",
    )
    second_projects = frappe.get_all(
        "NPI Engineering Project",
        filters={"tenant_id": TENANT_ID, "global_id": ["!=", project_id]},
        fields=["global_id", "optimistic_version"],
        order_by="global_id asc",
        limit_page_length=2,
    )
    require(bool(second_projects), "P7-06 second Project IDOR fixture is unavailable")
    return {
        "acknowledgementUser": ACKNOWLEDGEMENT_USER,
        "fixtureRunId": fixture_run_id,
        "memberGlobalId": str(member.global_id),
        "memberOptimisticVersion": int(member.optimistic_version),
        "projectGlobalId": project_id,
        "projectOptimisticVersion": int(project.optimistic_version),
        "projectType": str(project.project_type),
        "roleAssignmentGlobalId": str(role.global_id),
        "roleKey": str(role.role_key),
        "roleOptimisticVersion": int(role.optimistic_version),
        "secondProjectGlobalId": str(second_projects[0].global_id),
        "secondProjectOptimisticVersion": int(
            second_projects[0].optimistic_version
        ),
        "unresolvedActionKinds": sorted(allowed_kinds),
        "unresolvedActions": [value.snapshot_payload() for value in unresolved],
    }


def production_transition_source_context(
    fixture_run_id: str, *, project_id: str
) -> dict[str, object]:
    from npi_core.foundation.security import Principal
    from npi_core.production_transition.domain import HandoverSourceKind
    from npi_core.production_transition.frappe_repository import (
        FrappeProductionTransitionRepository,
    )
    from npi_core.production_transition.source_resolver import (
        SOURCE_LOADER_SEAMS,
        SourceResolutionContext,
    )

    document_runtime._validated_runtime_site()
    require(fixture_run_id == FIXTURE_RUN_ID, "P7-06 source namespace drifted")
    predecessor = readiness_runtime.readiness_source_context(
        fixture_run_id, project_id=project_id
    )
    predecessor_sources = {
        str(value["kind"]): value
        for value in predecessor["internalSources"]
        if isinstance(value, dict)
    }
    repository = FrappeProductionTransitionRepository(
        principal=Principal(
            ACTOR_USER,
            roles=frozenset({"NPI API User", "System Manager"}),
            tenant_id=TENANT_ID,
        ),
        request_id=str(uuid4()),
        trace_id=f"trace-{uuid4().hex}",
    )
    context = SourceResolutionContext(TENANT_ID, UUID(project_id))
    sources = []
    tuple_differences = []
    for kind_text in SOURCE_KINDS:
        predecessor_kind = (
            "trial_defect" if kind_text == "trial_defect_revision" else kind_text
        )
        candidate = predecessor_sources.get(predecessor_kind)
        require(
            isinstance(candidate, dict),
            f"P7-06 source candidate is unavailable: {kind_text}",
        )
        kind = HandoverSourceKind(kind_text)
        loader = getattr(repository, SOURCE_LOADER_SEAMS[kind])
        resolved = loader(
            context,
            UUID(str(candidate["globalId"])),
            for_update=False,
        )
        require(
            resolved is not None
            and resolved.kind is kind
            and str(resolved.global_id) == str(candidate["globalId"]),
            f"P7-06 exact current source resolution failed: {kind_text}",
        )
        source = {
            "expectedVersion": int(resolved.source_version),
            "globalId": str(resolved.global_id),
            "kind": kind.value,
            "snapshotHash": str(resolved.snapshot_hash),
        }
        _hash(source["snapshotHash"], f"P7-06 {kind_text} source")
        sources.append(source)
        if kind_text == "file_revision":
            tuple_differences.append(
                int(candidate["sourceVersion"]) != source["expectedVersion"]
                or str(candidate["snapshotHash"]) != source["snapshotHash"]
            )
    require(
        len(sources) == 9
        and [value["kind"] for value in sources] == list(SOURCE_KINDS)
        and tuple_differences == [True],
        "P7-06 nine-source catalog or P7-05 tuple difference drifted",
    )
    return {
        "exactSources": sources,
        "fixtureRunId": fixture_run_id,
        "p705FileTupleRejected": True,
        "sourceCount": len(sources),
    }


def verify_production_transition_provider_offline(
    fixture_run_id: str,
) -> dict[str, object]:
    from npi_core.production_transition.domain import (
        unavailable_observation_providers,
    )

    document_runtime._validated_runtime_site()
    require(fixture_run_id == FIXTURE_RUN_ID, "P7-06 provider namespace drifted")

    class NoProviderBoundary:
        calls = 0

        def __getattr__(self, _name: str):
            self.calls += 1
            raise AssertionError("P7-06 unavailable provider crossed a boundary")

    boundary = NoProviderBoundary()
    providers = [value.snapshot_payload() for value in unavailable_observation_providers()]
    require(
        [value["kind"] for value in providers] == list(PROVIDER_RESPONSE_ORDER)
        and all(
            value
            == {
                "kind": value["kind"],
                "state": "unavailable",
                "reasonCode": PROVIDER_REASON_CODES[value["kind"]],
                "sourceIdentity": None,
                "observedAt": None,
                "value": None,
                "unit": None,
            }
            for value in providers
        )
        and boundary.calls == 0,
        "P7-06 identity-free offline provider seam drifted",
    )
    return {
        "fixtureRunId": fixture_run_id,
        "providerCount": len(providers),
        "providerOrder": [value["kind"] for value in providers],
        "repositoryCalls": boundary.calls,
    }


def _decoded_persisted_json(value: object, label: str) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError as error:
                raise RuntimeError(f"{label} contains invalid persisted JSON") from error
    return value


def _assert_persisted_value_redacted(value: object, label: str) -> None:
    decoded = _decoded_persisted_json(value, label)

    def visit(item: object, path: str) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                folded_key = str(key).casefold()
                require(
                    "fileurl" not in folded_key
                    and "password" not in folded_key
                    and "secret" not in folded_key
                    and "token" not in folded_key,
                    f"{label} retained a sensitive key at {path}",
                )
                visit(child, f"{path}.{key}")
            return
        if isinstance(item, Sequence) and not isinstance(
            item, (str, bytes, bytearray)
        ):
            for index, child in enumerate(item):
                visit(child, f"{path}[{index}]")
            return
        if isinstance(item, str):
            folded = item.casefold()
            require(
                "/private/files/" not in folded
                and "fileurl" not in folded
                and "password" not in folded
                and "secret" not in folded
                and "token" not in folded,
                f"{label} retained a sensitive value at {path}",
            )

    visit(decoded, "$")


def verify_production_transition_persisted_redaction(
    fixture_run_id: str, *, project_id: str
) -> dict[str, object]:
    import frappe

    document_runtime._validated_runtime_site()
    require(fixture_run_id == FIXTURE_RUN_ID, "P7-06 redaction namespace drifted")
    json_fields = {
        "NPI Production Transition Policy": ("policy_code", "title"),
        "NPI Production Transition Policy Version": (
            "policy_snapshot",
            "applicability_snapshot",
            "receiving_group_snapshot",
            "acknowledgement_slot_snapshot",
            "handover_object_requirement_snapshot",
            "unresolved_action_rule_snapshot",
            "observation_source_requirement_snapshot",
            "conclusion_rule_snapshot",
        ),
        "NPI Handover Package Revision": (
            "project",
            "project_snapshot",
            "slot_snapshot",
            "manifest_snapshot",
            "unresolved_selector_snapshot",
            "unresolved_action_snapshot",
            "package_snapshot",
        ),
        "NPI Handover Acknowledgement": ("acknowledgement_snapshot",),
        "NPI Observation Period Revision": (
            "project",
            "project_snapshot",
            "provider_source_snapshot",
            "context_reference_snapshot",
            "retrospective_evidence_snapshot",
            "observation_snapshot",
        ),
        "NPI Production Transition Command Idempotency": ("response_payload",),
    }
    expected_rows = {
        "NPI Production Transition Policy": 1,
        "NPI Production Transition Policy Version": 1,
        "NPI Handover Package Revision": 2,
        "NPI Handover Acknowledgement": 4,
        "NPI Observation Period Revision": 2,
        "NPI Production Transition Command Idempotency": 11,
    }
    filters = _transition_filters(project_id)
    scanned_fields = 0
    for doctype, fields in json_fields.items():
        names = frappe.get_all(
            doctype,
            filters=filters[doctype],
            pluck="name",
            order_by="name asc",
            limit_page_length=101,
        )
        require(
            len(names) == expected_rows[doctype],
            f"P7-06 redaction scope cardinality drifted: {doctype}",
        )
        for name in names:
            document = frappe.get_doc(doctype, str(name))
            if doctype == "NPI Production Transition Command Idempotency":
                require(
                    int(document.sealed) == 1
                    and bool(str(document.response_hash)),
                    "P7-06 redaction inspected an unsealed response",
                )
            for field in fields:
                _assert_persisted_value_redacted(
                    document.get(field), f"P7-06 {doctype}.{field}"
                )
                scanned_fields += 1
    audit_names = frappe.get_all(
        "NPI Audit Event",
        filters={
            "actor": ["in", [ACTOR_USER, ACKNOWLEDGEMENT_USER]],
            "operation": ["in", list(TRANSITION_OPERATIONS)],
        },
        pluck="name",
        order_by="name asc",
        limit_page_length=101,
    )
    require(len(audit_names) == 11, "P7-06 redaction audit scope drifted")
    for name in audit_names:
        audit = frappe.get_doc("NPI Audit Event", str(name))
        _assert_persisted_value_redacted(
            audit.input_summary, "P7-06 audit input_summary"
        )
        scanned_fields += 1
    return {
        "auditSummaryCount": len(audit_names),
        "businessSentinelPersistenceAllowed": True,
        "fixtureRunId": fixture_run_id,
        "persistedJsonFieldCount": scanned_fields,
        "sealedResponseCount": expected_rows[
            "NPI Production Transition Command Idempotency"
        ],
        "sensitivePersisted": False,
    }


def verify_production_transition_runtime_schema(
    fixture_run_id: str,
) -> dict[str, object]:
    import frappe

    document_runtime._validated_runtime_site()
    require(fixture_run_id == FIXTURE_RUN_ID, "P7-06 schema namespace drifted")
    required_fields = {
        "NPI Production Transition Policy": {
            "global_id",
            "tenant_id",
            "policy_code",
            "optimistic_version",
        },
        "NPI Production Transition Policy Version": {
            "global_id",
            "policy_global_id",
            "policy_version",
            "optimistic_version",
            "publication_state",
            "policy_snapshot",
            "snapshot_hash",
        },
        "NPI Handover Package Revision": {
            "global_id",
            "handover_global_id",
            "project_global_id",
            "handover_version",
            "package_snapshot",
            "snapshot_hash",
        },
        "NPI Handover Acknowledgement": {
            "global_id",
            "project_global_id",
            "package_revision_global_id",
            "slot_key",
            "actor_user_id",
            "acknowledgement_snapshot",
            "snapshot_hash",
        },
        "NPI Observation Period Revision": {
            "global_id",
            "observation_global_id",
            "project_global_id",
            "observation_version",
            "observation_snapshot",
            "snapshot_hash",
        },
        "NPI Production Transition Command Idempotency": {
            "global_id",
            "actor_user_id",
            "operation",
            "payload_hash",
            "response_payload",
            "response_hash",
            "sealed",
        },
    }
    for doctype in TRANSITION_DOCTYPES:
        require(frappe.db.table_exists(doctype), f"P7-06 table is unavailable: {doctype}")
        fields = {
            field.fieldname for field in frappe.get_meta(doctype, cached=False).fields
        }
        require(
            required_fields[doctype] <= fields,
            f"P7-06 metadata is incomplete for {doctype}",
        )
    return {
        "doctypeCount": len(TRANSITION_DOCTYPES),
        "fixtureRunId": fixture_run_id,
        "metadataSynchronized": True,
        "runtimeMarker": RUNTIME_MARKER,
    }


BENCH_FIXTURES = {
    "production_transition_fixture_context": production_transition_fixture_context,
    "production_transition_persistence_context": (
        production_transition_persistence_context
    ),
    "production_transition_source_context": production_transition_source_context,
    "verify_production_transition_persisted_redaction": (
        verify_production_transition_persisted_redaction
    ),
    "verify_production_transition_provider_offline": (
        verify_production_transition_provider_offline
    ),
    "verify_production_transition_runtime_schema": (
        verify_production_transition_runtime_schema
    ),
}


def run_bench_fixture(method: str, kwargs: dict[str, object]) -> dict[str, Any]:
    require(method in BENCH_FIXTURES, "P7-06 Bench fixture is unavailable")
    require(
        BENCH_PATH.is_dir()
        and not BENCH_PATH.is_symlink()
        and BENCH_PATH.resolve() == BENCH_PATH,
        "P7-06 verifier requires the fixed physical Bench",
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
            str(ROOT / "scripts" / "verify_production_transition_runtime.py"),
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
    require(completed.returncode == 0, f"P7-06 Bench fixture failed: {method}")
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    require(bool(lines), f"P7-06 Bench fixture was silent: {method}")
    result = json.loads(lines[-1])
    require(isinstance(result, dict), "P7-06 Bench fixture result is invalid")
    return result


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    require(method in BENCH_FIXTURES, "P7-06 Bench fixture is unavailable")
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
    administrator_csrf: str,
    fixture_password: str,
) -> None:
    readiness_runtime.prepare_runtime_users(
        administrator,
        base_url,
        administrator_csrf,
        fixture_password,
    )
    changed = update_resource(
        administrator,
        base_url,
        "User",
        ACKNOWLEDGEMENT_USER,
        {"new_password": fixture_password},
        administrator_csrf,
    )
    require(changed.status == 200, "P7-06 acknowledgement password was not set")
    retained = get_resource(
        administrator, base_url, "User", ACKNOWLEDGEMENT_USER
    )
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
        and "NPI API User" in roles
        and "System Manager" not in roles,
        "P7-06 acknowledgement actor gained proxy authority",
    )


def policy_catalog(opener, base_url: str, project_id: str) -> dict[str, Any]:
    result = transition_request(
        opener,
        base_url,
        f"{policy_path()}?projectId={project_id}",
        query_key="policy-catalog",
    )
    require(result.status == 200, f"P7-06 catalog returned HTTP {result.status}")
    require_safe_payload(result.body, "P7-06 policy catalog")
    require(
        result.body.get("projectGlobalId") == project_id
        and isinstance(result.body.get("policies"), list),
        "P7-06 policy catalog Project context drifted",
    )
    return _object(result.body, "P7-06 policy catalog")


def transition_workspace(opener, base_url: str, project_id: str) -> dict[str, Any]:
    result = transition_request(
        opener,
        base_url,
        workspace_path(project_id),
        query_key="workspace",
    )
    require(
        result.status == 200,
        f"P7-06 transition workspace returned HTTP {result.status}",
    )
    require_safe_payload(result.body, "P7-06 workspace")
    require(
        result.body.get("projectGlobalId") == project_id,
        "P7-06 workspace Project context drifted",
    )
    return _object(result.body, "P7-06 workspace")


def transition_counts(
    administrator, base_url: str, project_id: str
) -> dict[str, int]:
    specs = {
        "NPI Production Transition Policy": [["policy_code", "=", POLICY_CODE]],
        "NPI Production Transition Policy Version": [
            ["policy_code", "=", POLICY_CODE]
        ],
        "NPI Handover Package Revision": [
            ["project_global_id", "=", project_id]
        ],
        "NPI Handover Acknowledgement": [
            ["project_global_id", "=", project_id]
        ],
        "NPI Observation Period Revision": [
            ["project_global_id", "=", project_id]
        ],
        "NPI Production Transition Command Idempotency": [
            [
                "actor_user_id",
                "in",
                [ACTOR_USER, UNRELATED_USER, ACKNOWLEDGEMENT_USER],
            ]
        ],
    }
    result = {
        doctype: len(
            list_resources(
                administrator,
                base_url,
                doctype,
                filters=filters,
                fields=["name"],
            )
        )
        for doctype, filters in specs.items()
    }
    for operation in TRANSITION_OPERATIONS:
        result[f"audit:{operation}"] = len(
            list_resources(
                administrator,
                base_url,
                "NPI Audit Event",
                filters=[
                    [
                        "actor",
                        "in",
                        [ACTOR_USER, UNRELATED_USER, ACKNOWLEDGEMENT_USER],
                    ],
                    ["operation", "=", operation],
                ],
                fields=["event_id"],
            )
        )
    return result


def verify_policy_response(
    value: Mapping[str, object],
    *,
    publication_state: str,
    optimistic_version: int,
) -> None:
    _uuid(value.get("globalId"), "P7-06 policy revision")
    _uuid(value.get("policyGlobalId"), "P7-06 policy")
    _hash(value.get("snapshotHash"), "P7-06 policy")
    require(
        value.get("policyCode") == POLICY_CODE
        and value.get("policyVersion") == 1
        and value.get("publicationState") == publication_state
        and value.get("optimisticVersion") == optimistic_version
        and value.get("authorityBoundary") == "npi_technical_configuration_only",
        "P7-06 policy response drifted",
    )


def verify_package(
    package: Mapping[str, object],
    context: Mapping[str, object],
    sources: Sequence[Mapping[str, object]],
    *,
    version: int,
    predecessor: Mapping[str, object] | None,
) -> None:
    _uuid(package.get("globalId"), "P7-06 package revision")
    _uuid(package.get("handoverGlobalId"), "P7-06 handover")
    _hash(package.get("snapshotHash"), "P7-06 package")
    slots = package.get("slots")
    manifest = package.get("manifest")
    unresolved = package.get("unresolvedActions")
    require(
        package.get("handoverVersion") == version
        and isinstance(slots, list)
        and isinstance(manifest, list)
        and isinstance(unresolved, list)
        and [value.get("slotKey") for value in slots if isinstance(value, dict)]
        == ["sender", "receiver"]
        and len(manifest) == len(sources) == 9
        and unresolved == context["unresolvedActions"],
        "P7-06 package frozen collection drifted",
    )
    for slot in slots:
        require(isinstance(slot, dict), "P7-06 frozen slot is invalid")
        member = slot.get("member")
        role = slot.get("role")
        require(
            isinstance(member, dict)
            and isinstance(role, dict)
            and member.get("globalId") == context["memberGlobalId"]
            and member.get("userId") == ACKNOWLEDGEMENT_USER
            and member.get("optimisticVersion")
            == context["memberOptimisticVersion"]
            and role.get("globalId") == context["roleAssignmentGlobalId"]
            and role.get("roleKey") == document_runtime.BASELINE_ROLE_KEY
            and role.get("optimisticVersion") == context["roleOptimisticVersion"],
            "P7-06 exact frozen actor/member/role tuple drifted",
        )
    expected_by_kind = {str(value["kind"]): value for value in sources}
    require(
        [value.get("kind") for value in manifest if isinstance(value, dict)]
        == list(SOURCE_KINDS),
        "P7-06 manifest order drifted",
    )
    for value in manifest:
        require(isinstance(value, dict), "P7-06 manifest value is invalid")
        source = expected_by_kind[str(value.get("kind"))]
        require(
            value
            == {
                "requirementKey": f"requirement_{source['kind']}",
                "kind": source["kind"],
                "globalId": source["globalId"],
                "sourceVersion": source["expectedVersion"],
                "snapshotHash": source["snapshotHash"],
                "role": f"controlled_{source['kind']}",
            },
            "P7-06 server-owned manifest role/hash injection drifted",
        )
    if predecessor is None:
        require(
            package.get("predecessorGlobalId") is None
            and package.get("predecessorSnapshotHash") is None,
            "P7-06 first package gained a predecessor",
        )
    else:
        require(
            package.get("predecessorGlobalId") == predecessor.get("globalId")
            and package.get("predecessorSnapshotHash")
            == predecessor.get("snapshotHash")
            and package.get("handoverGlobalId")
            == predecessor.get("handoverGlobalId"),
            "P7-06 package successor linkage drifted",
        )


def verify_acknowledgement(
    value: Mapping[str, object],
    package: Mapping[str, object],
    context: Mapping[str, object],
    slot_key: str,
) -> None:
    _uuid(value.get("globalId"), "P7-06 acknowledgement")
    _hash(value.get("snapshotHash"), "P7-06 acknowledgement")
    require(
        value.get("packageRevisionGlobalId") == package.get("globalId")
        and value.get("packageVersion") == package.get("handoverVersion")
        and value.get("packageSnapshotHash") == package.get("snapshotHash")
        and value.get("slotKey") == slot_key
        and value.get("acknowledgementIntent")
        == "acknowledge_exact_package_slot"
        and value.get("actorUserId") == ACKNOWLEDGEMENT_USER
        and value.get("memberGlobalId") == context["memberGlobalId"]
        and value.get("memberOptimisticVersion")
        == context["memberOptimisticVersion"]
        and value.get("roleGlobalId") == context["roleAssignmentGlobalId"]
        and value.get("roleOptimisticVersion") == context["roleOptimisticVersion"],
        "P7-06 exact acknowledgement fact drifted",
    )


def verify_observation(
    value: Mapping[str, object],
    *,
    version: int,
    handover: Mapping[str, object],
    predecessor: Mapping[str, object] | None,
) -> None:
    _uuid(value.get("globalId"), "P7-06 observation revision")
    _uuid(value.get("observationGlobalId"), "P7-06 observation")
    _hash(value.get("snapshotHash"), "P7-06 observation")
    providers = value.get("providers")
    require(
        value.get("observationVersion") == version
        and value.get("handoverPackageRef")
        == {
            "globalId": handover["globalId"],
            "version": handover["handoverVersion"],
            "snapshotHash": handover["snapshotHash"],
        }
        and value.get("observedStartDate") is None
        and value.get("observedEndDate") is None
        and value.get("observationState") == "not_evaluable"
        and value.get("technicalDisposition") == "not_evaluable"
        and value.get("authorityBoundary") == "technical_observation_only"
        and isinstance(providers, list)
        and [item.get("kind") for item in providers if isinstance(item, dict)]
        == list(PROVIDER_RESPONSE_ORDER),
        "P7-06 observation or provider order drifted",
    )
    for provider in providers:
        require(
            provider
            == {
                "kind": provider["kind"],
                "state": "unavailable",
                "reasonCode": PROVIDER_REASON_CODES[provider["kind"]],
                "sourceIdentity": None,
                "observedAt": None,
                "value": None,
                "unit": None,
            },
            "P7-06 unavailable provider exposed identity or value",
        )
    if predecessor is None:
        require(
            value.get("predecessorGlobalId") is None
            and value.get("predecessorSnapshotHash") is None,
            "P7-06 first observation gained a predecessor",
        )
    else:
        require(
            value.get("predecessorGlobalId") == predecessor.get("globalId")
            and value.get("predecessorSnapshotHash")
            == predecessor.get("snapshotHash"),
            "P7-06 observation successor linkage drifted",
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
        and transition_counts(administrator, base_url, project_id) == counts_before,
        "P7-06 same-process replay changed sealed truth",
    )
    return _object(replay.body, "P7-06 replay response")


def _command_body(
    result: HttpResult,
    field: str,
    label: str,
) -> dict[str, Any]:
    body = _object(result.body, label)
    value = body.get(field)
    require(isinstance(value, dict), f"{label} has no {field}")
    return dict(value)


def _verify_workspace_history(
    workspace: Mapping[str, object],
    *,
    expected_handover_count: int,
    expected_observation_count: int,
) -> None:
    handovers = workspace.get("handoverHistory")
    observations = workspace.get("observationHistory")
    require(
        isinstance(handovers, list)
        and isinstance(observations, list)
        and len(handovers) == expected_handover_count
        and len(observations) == expected_observation_count
        and workspace.get("currentHandover")
        == (handovers[-1] if handovers else None)
        and workspace.get("currentObservation")
        == (observations[-1] if observations else None),
        "P7-06 immutable workspace history drifted",
    )


def _expect_problem_without_write(
    opener,
    base_url: str,
    csrf_token: str,
    path: str,
    payload: dict[str, object],
    key: str,
    *,
    status: int,
    code: str,
    administrator,
    project_id: str,
    method: str = "POST",
) -> HttpResult:
    before = transition_counts(administrator, base_url, project_id)
    before_context = run_bench_fixture(
        "production_transition_persistence_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    result = command(
        opener,
        base_url,
        csrf_token,
        path,
        payload,
        key,
        method=method,
        expected_status=status,
    )
    validate_problem(result, status, code)
    after_context = run_bench_fixture(
        "production_transition_persistence_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    require(
        transition_counts(administrator, base_url, project_id) == before
        and before_context == after_context,
        f"P7-06 rejected {code} command wrote retained truth",
    )
    return result


def verify_project_first_idor(
    reader,
    manager,
    base_url: str,
    reader_csrf: str,
    manager_csrf: str,
    *,
    second_project_id: str,
    second_project_version: int,
    target_package: Mapping[str, object],
    target_observation: Mapping[str, object],
    handover_payload: Mapping[str, object],
    observation_payload: Mapping[str, object],
    administrator,
    target_project_id: str,
) -> None:
    before = transition_counts(administrator, base_url, target_project_id)
    before_context = run_bench_fixture(
        "production_transition_persistence_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": target_project_id},
    )
    cross_project = transition_request(
        reader,
        base_url,
        workspace_path(second_project_id),
        query_key="idor-real-secondary",
    )
    validate_problem(cross_project, 404, "PRODUCTION_TRANSITION_UNAVAILABLE")
    absent = transition_request(
        reader,
        base_url,
        workspace_path(ABSENT_ID),
        query_key="idor-absent-secondary",
    )
    validate_problem(absent, 404, "PRODUCTION_TRANSITION_UNAVAILABLE")
    stable_fields = ("status", "code", "title", "detail", "retryable")
    require(
        {key: cross_project.body.get(key) for key in stable_fields}
        == {key: absent.body.get(key) for key in stable_fields},
        "P7-06 Project-first IDOR boundary disclosed a secondary identifier",
    )

    def assert_secondary_pair(
        opener,
        csrf_token: str,
        real_path: str,
        absent_path: str,
        payload: Mapping[str, object],
        key_suffix: str,
    ) -> None:
        real = command(
            opener,
            base_url,
            csrf_token,
            real_path,
            dict(payload),
            f"p7-06-idor-{FIXTURE_RUN_ID}-{key_suffix}-real",
            expected_status=404,
        )
        missing = command(
            opener,
            base_url,
            csrf_token,
            absent_path,
            dict(payload),
            f"p7-06-idor-{FIXTURE_RUN_ID}-{key_suffix}-absent",
            expected_status=404,
        )
        validate_problem(real, 404, "PRODUCTION_TRANSITION_UNAVAILABLE")
        validate_problem(missing, 404, "PRODUCTION_TRANSITION_UNAVAILABLE")
        require(
            {key: real.body.get(key) for key in stable_fields}
            == {key: missing.body.get(key) for key in stable_fields},
            f"P7-06 {key_suffix} disclosed a secondary identifier",
        )

    cross_handover = deepcopy(dict(handover_payload))
    content = _object(cross_handover.get("content"), "P7-06 IDOR handover content")
    content["expectedProjectVersion"] = second_project_version
    cross_handover["content"] = content
    assert_secondary_pair(
        manager,
        manager_csrf,
        handover_path(
            second_project_id, str(target_package["handoverGlobalId"])
        ),
        handover_path(second_project_id, ABSENT_ID),
        cross_handover,
        "handover-revise",
    )
    assert_secondary_pair(
        reader,
        reader_csrf,
        handover_path(
            second_project_id,
            str(target_package["handoverGlobalId"]),
            int(target_package["handoverVersion"]),
        ),
        handover_path(
            second_project_id,
            ABSENT_ID,
            int(target_package["handoverVersion"]),
        ),
        acknowledgement_payload(target_package, "sender"),
        "handover-ack",
    )
    assert_secondary_pair(
        manager,
        manager_csrf,
        observation_path(
            second_project_id, str(target_observation["observationGlobalId"])
        ),
        observation_path(second_project_id, ABSENT_ID),
        observation_payload,
        "observation-revise",
    )
    after_context = run_bench_fixture(
        "production_transition_persistence_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": target_project_id},
    )
    require(
        transition_counts(administrator, base_url, target_project_id) == before
        and before_context == after_context,
        "P7-06 Project-first probes changed counts or canonical digests",
    )


def _generic_rows(
    opener,
    base_url: str,
    project_id: str,
) -> tuple[tuple[str, list[list[object]]], ...]:
    return (
        (
            "NPI Production Transition Policy",
            [["policy_code", "=", POLICY_CODE]],
        ),
        (
            "NPI Production Transition Policy Version",
            [["policy_code", "=", POLICY_CODE]],
        ),
        (
            "NPI Handover Package Revision",
            [["project_global_id", "=", project_id]],
        ),
        (
            "NPI Handover Acknowledgement",
            [["project_global_id", "=", project_id]],
        ),
        (
            "NPI Observation Period Revision",
            [["project_global_id", "=", project_id]],
        ),
        (
            "NPI Production Transition Command Idempotency",
            [["actor_user_id", "=", ACTOR_USER]],
        ),
    )


def verify_generic_mutation_denial(
    actor,
    base_url: str,
    csrf_token: str,
    project_id: str,
) -> None:
    before_context = run_bench_fixture(
        "production_transition_persistence_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    for doctype, filters in _generic_rows(actor, base_url, project_id):
        protected = PROTECTED_FIELDS[doctype]
        rows = list_resources(
            actor,
            base_url,
            doctype,
            filters=filters,
            fields=["name", protected],
        )
        require(bool(rows), f"P7-06 protected row is unavailable: {doctype}")
        name = str(rows[0]["name"])
        retained = get_resource(actor, base_url, doctype, name)
        before = _object(
            retained.body.get("data"), f"P7-06 protected {doctype} row"
        )
        require(retained.status == 200, f"P7-06 protected read failed: {doctype}")
        forged_payload = {
            key: deepcopy(value)
            for key, value in before.items()
            if key not in _SYSTEM_FIELDS
        }
        if "global_id" in forged_payload:
            forged_payload["global_id"] = str(uuid4())
        created = create_resource(
            actor,
            base_url,
            doctype,
            forged_payload,
            csrf_token,
        )
        require(
            created.status in {403, 417},
            f"P7-06 generic create guard failed for {doctype}",
        )
        old_value = str(before[protected])
        forged_value = (
            f"{old_value}-forged"
            if protected == "policy_code"
            else ("0" if old_value[0] != "0" else "1") + old_value[1:]
        )
        updated = update_resource(
            actor,
            base_url,
            doctype,
            name,
            {protected: forged_value},
            csrf_token,
        )
        require(
            updated.status in {403, 417},
            f"P7-06 generic update guard failed for {doctype}",
        )
        deleted = delete_resource(
            actor,
            base_url,
            doctype,
            name,
            csrf_token,
        )
        require(
            deleted.status in {403, 417},
            f"P7-06 generic delete guard failed for {doctype}",
        )
        after = get_resource(actor, base_url, doctype, name)
        require(
            after.status == 200 and after.body.get("data") == before,
            f"P7-06 rejected generic mutation changed {doctype}",
        )
    after_context = run_bench_fixture(
        "production_transition_persistence_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    require(
        before_context == after_context,
        "P7-06 generic mutation probes changed counts or canonical digests",
    )


def run_fresh(
    administrator,
    actor,
    unrelated,
    acknowledgement_actor,
    base_url: str,
    actor_csrf: str,
    unrelated_csrf: str,
    acknowledgement_csrf: str,
) -> dict[str, object]:
    project_id, _project_version = document_runtime.fixture_project(
        administrator, base_url
    )
    schema = run_bench_fixture(
        "verify_production_transition_runtime_schema",
        {"fixture_run_id": FIXTURE_RUN_ID},
    )
    context = run_bench_fixture(
        "production_transition_fixture_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    source_context = run_bench_fixture(
        "production_transition_source_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    offline = run_bench_fixture(
        "verify_production_transition_provider_offline",
        {"fixture_run_id": FIXTURE_RUN_ID},
    )
    sources = source_context.get("exactSources")
    require(
        schema.get("metadataSynchronized") is True
        and context.get("acknowledgementUser") == ACKNOWLEDGEMENT_USER
        and context.get("roleKey") == document_runtime.BASELINE_ROLE_KEY
        and isinstance(context.get("unresolvedActions"), list)
        and isinstance(sources, list)
        and len(sources) == 9
        and source_context.get("p705FileTupleRejected") is True
        and offline.get("providerOrder") == list(PROVIDER_RESPONSE_ORDER)
        and offline.get("repositoryCalls") == 0,
        "P7-06 schema, fixture, source, or offline preflight drifted",
    )
    before_persistence = run_bench_fixture(
        "production_transition_persistence_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    initial_counts = transition_counts(administrator, base_url, project_id)
    require(
        all(value == 0 for value in initial_counts.values()),
        "P7-06 namespace was not independently empty",
    )

    create_body = create_policy_payload(context)
    created_result = command(
        actor,
        base_url,
        actor_csrf,
        policy_path(),
        create_body,
        CREATE_POLICY_KEY,
        expected_status=201,
    )
    created = _object(created_result.body, "P7-06 created policy")
    verify_policy_response(created, publication_state="draft", optimistic_version=1)
    after_create = transition_counts(administrator, base_url, project_id)
    _assert_replay(
        actor,
        base_url,
        actor_csrf,
        policy_path(),
        create_body,
        CREATE_POLICY_KEY,
        created,
        201,
        after_create,
        administrator,
        project_id,
    )
    _expect_problem_without_write(
        unrelated,
        base_url,
        unrelated_csrf,
        policy_path(),
        create_body,
        CREATE_POLICY_KEY,
        status=409,
        code="PRODUCTION_TRANSITION_VERSION_CONFLICT",
        administrator=administrator,
        project_id=project_id,
    )
    changed_create = deepcopy(create_body)
    changed_create["title"] = f"{POLICY_SENTINEL}-CONFLICT"
    _expect_problem_without_write(
        actor,
        base_url,
        actor_csrf,
        policy_path(),
        changed_create,
        CREATE_POLICY_KEY,
        status=409,
        code="PRODUCTION_TRANSITION_IDEMPOTENCY_CONFLICT",
        administrator=administrator,
        project_id=project_id,
    )
    require(
        transition_counts(administrator, base_url, project_id) == after_create,
        "P7-06 actor/key conflict wrote policy truth",
    )

    policy_id = str(created["policyGlobalId"])
    policy_version = int(created["policyVersion"])
    edit_body = edit_policy_payload(context, 1)
    edited_result = command(
        actor,
        base_url,
        actor_csrf,
        policy_path(policy_id, policy_version),
        edit_body,
        EDIT_POLICY_KEY,
        method="PUT",
        expected_status=200,
    )
    edited = _object(edited_result.body, "P7-06 edited policy")
    verify_policy_response(edited, publication_state="draft", optimistic_version=2)
    after_edit = transition_counts(administrator, base_url, project_id)
    _assert_replay(
        actor,
        base_url,
        actor_csrf,
        policy_path(policy_id, policy_version),
        edit_body,
        EDIT_POLICY_KEY,
        edited,
        200,
        after_edit,
        administrator,
        project_id,
        method="PUT",
    )
    publish_body = {
        "expectedOptimisticVersion": 2,
        "expectedSnapshotHash": edited["snapshotHash"],
    }
    published_result = command(
        actor,
        base_url,
        actor_csrf,
        policy_path(policy_id, policy_version, publish=True),
        publish_body,
        PUBLISH_POLICY_KEY,
        expected_status=200,
    )
    published = _object(published_result.body, "P7-06 published policy")
    verify_policy_response(
        published, publication_state="published", optimistic_version=3
    )
    after_publish = transition_counts(administrator, base_url, project_id)
    _assert_replay(
        actor,
        base_url,
        actor_csrf,
        policy_path(policy_id, policy_version, publish=True),
        publish_body,
        PUBLISH_POLICY_KEY,
        published,
        200,
        after_publish,
        administrator,
        project_id,
    )
    _expect_problem_without_write(
        actor,
        base_url,
        actor_csrf,
        policy_path(policy_id, policy_version),
        edit_policy_payload(context, 3),
        IMMUTABLE_POLICY_KEY,
        method="PUT",
        status=409,
        code="PRODUCTION_TRANSITION_POLICY_IMMUTABLE",
        administrator=administrator,
        project_id=project_id,
    )
    require(
        transition_counts(administrator, base_url, project_id) == after_publish,
        "P7-06 published policy accepted mutation",
    )
    catalog = policy_catalog(actor, base_url, project_id)
    retained_policies = [
        value
        for value in catalog["policies"]
        if isinstance(value, dict) and value.get("policyCode") == POLICY_CODE
    ]
    require(
        retained_policies == [published],
        "P7-06 published applicable policy catalog drifted",
    )
    empty_workspace = transition_workspace(actor, base_url, project_id)
    _verify_workspace_history(
        empty_workspace,
        expected_handover_count=0,
        expected_observation_count=0,
    )

    handover_v1_body = handover_content(
        context, published, sources, version=1
    )
    handover_v1_result = command(
        actor,
        base_url,
        actor_csrf,
        handover_path(project_id),
        handover_v1_body,
        HANDOVER_V1_KEY,
        expected_status=201,
    )
    package_v1 = _command_body(
        handover_v1_result, "handoverPackage", "P7-06 handover v1"
    )
    verify_package(package_v1, context, sources, version=1, predecessor=None)
    after_handover_v1 = transition_counts(administrator, base_url, project_id)
    _assert_replay(
        actor,
        base_url,
        actor_csrf,
        handover_path(project_id),
        handover_v1_body,
        HANDOVER_V1_KEY,
        handover_v1_result.body,
        201,
        after_handover_v1,
        administrator,
        project_id,
    )
    _expect_problem_without_write(
        actor,
        base_url,
        actor_csrf,
        handover_path(
            project_id,
            str(package_v1["handoverGlobalId"]),
            int(package_v1["handoverVersion"]),
        ),
        acknowledgement_payload(package_v1, "sender"),
        f"{ACK_V1_KEYS['sender']}-proxy",
        status=403,
        code="PERMISSION_DENIED",
        administrator=administrator,
        project_id=project_id,
    )
    require(
        transition_counts(administrator, base_url, project_id)
        == after_handover_v1,
        "P7-06 manager proxy acknowledgement wrote a fact",
    )

    for slot_index, slot in enumerate(("sender", "receiver")):
        body = acknowledgement_payload(package_v1, slot)
        result = command(
            acknowledgement_actor,
            base_url,
            acknowledgement_csrf,
            handover_path(
                project_id,
                str(package_v1["handoverGlobalId"]),
                1,
            ),
            body,
            ACK_V1_KEYS[slot],
            expected_status=201,
        )
        response = _object(result.body, f"P7-06 v1 {slot} acknowledgement")
        ack = _object(response.get("acknowledgement"), "P7-06 acknowledgement")
        verify_acknowledgement(ack, package_v1, context, slot)
        require(
            response.get("handoverPackage") == package_v1,
            "P7-06 acknowledgement rewrote package truth",
        )
        after_ack = transition_counts(administrator, base_url, project_id)
        _assert_replay(
            acknowledgement_actor,
            base_url,
            acknowledgement_csrf,
            handover_path(
                project_id,
                str(package_v1["handoverGlobalId"]),
                1,
            ),
            body,
            ACK_V1_KEYS[slot],
            response,
            201,
            after_ack,
            administrator,
            project_id,
        )
        workspace = transition_workspace(actor, base_url, project_id)
        current_view = _object(
            workspace.get("currentHandover"), "P7-06 current handover"
        )
        require(
            current_view.get("revision") == package_v1
            and len(current_view.get("acknowledgements", [])) == slot_index + 1
            and current_view.get("fullyAcknowledged") is (slot_index == 1),
            "P7-06 acknowledgement derivation drifted",
        )

    handover_v2_content = handover_content(
        context, published, sources, version=2
    )
    handover_v2_body = {
        "expectedRevisionGlobalId": package_v1["globalId"],
        "expectedSnapshotHash": package_v1["snapshotHash"],
        "content": handover_v2_content,
    }
    handover_v2_result = command(
        actor,
        base_url,
        actor_csrf,
        handover_path(project_id, str(package_v1["handoverGlobalId"])),
        handover_v2_body,
        HANDOVER_V2_KEY,
        expected_status=201,
    )
    package_v2 = _command_body(
        handover_v2_result, "handoverPackage", "P7-06 handover v2"
    )
    verify_package(
        package_v2, context, sources, version=2, predecessor=package_v1
    )
    after_handover_v2 = transition_counts(administrator, base_url, project_id)
    _assert_replay(
        actor,
        base_url,
        actor_csrf,
        handover_path(project_id, str(package_v1["handoverGlobalId"])),
        handover_v2_body,
        HANDOVER_V2_KEY,
        handover_v2_result.body,
        201,
        after_handover_v2,
        administrator,
        project_id,
    )
    superseded_workspace = transition_workspace(actor, base_url, project_id)
    _verify_workspace_history(
        superseded_workspace,
        expected_handover_count=2,
        expected_observation_count=0,
    )
    v1_view, v2_view = superseded_workspace["handoverHistory"]
    require(
        v1_view.get("revision") == package_v1
        and len(v1_view.get("acknowledgements", [])) == 2
        and v1_view.get("fullyAcknowledged") is True
        and v2_view.get("revision") == package_v2
        and v2_view.get("acknowledgements") == []
        and v2_view.get("fullyAcknowledged") is False,
        "P7-06 successor inherited or rewrote acknowledgement facts",
    )
    _expect_problem_without_write(
        acknowledgement_actor,
        base_url,
        acknowledgement_csrf,
        handover_path(
            project_id,
            str(package_v1["handoverGlobalId"]),
            1,
        ),
        acknowledgement_payload(package_v1, "sender"),
        STALE_ACK_KEY,
        status=409,
        code="PRODUCTION_TRANSITION_VERSION_CONFLICT",
        administrator=administrator,
        project_id=project_id,
    )

    for slot in ("sender", "receiver"):
        body = acknowledgement_payload(package_v2, slot)
        result = command(
            acknowledgement_actor,
            base_url,
            acknowledgement_csrf,
            handover_path(
                project_id,
                str(package_v2["handoverGlobalId"]),
                2,
            ),
            body,
            ACK_V2_KEYS[slot],
            expected_status=201,
        )
        response = _object(result.body, f"P7-06 v2 {slot} acknowledgement")
        verify_acknowledgement(
            _object(response.get("acknowledgement"), "P7-06 acknowledgement"),
            package_v2,
            context,
            slot,
        )
        require(
            response.get("handoverPackage") == package_v2,
            "P7-06 v2 acknowledgement rewrote package truth",
        )
        after_ack = transition_counts(administrator, base_url, project_id)
        _assert_replay(
            acknowledgement_actor,
            base_url,
            acknowledgement_csrf,
            handover_path(
                project_id,
                str(package_v2["handoverGlobalId"]),
                2,
            ),
            body,
            ACK_V2_KEYS[slot],
            response,
            201,
            after_ack,
            administrator,
            project_id,
        )

    observation_v1_body = observation_create_payload(
        context, published, package_v1, sources
    )
    observation_v1_result = command(
        actor,
        base_url,
        actor_csrf,
        observation_path(project_id),
        observation_v1_body,
        OBSERVATION_V1_KEY,
        expected_status=201,
    )
    observation_v1 = _command_body(
        observation_v1_result,
        "observationPeriod",
        "P7-06 observation v1",
    )
    verify_observation(
        observation_v1, version=1, handover=package_v1, predecessor=None
    )
    after_observation_v1 = transition_counts(administrator, base_url, project_id)
    _assert_replay(
        actor,
        base_url,
        actor_csrf,
        observation_path(project_id),
        observation_v1_body,
        OBSERVATION_V1_KEY,
        observation_v1_result.body,
        201,
        after_observation_v1,
        administrator,
        project_id,
    )
    repeated_source = sources[0]
    observation_v2_body = observation_revision_payload(
        observation_v1, repeated_source
    )
    observation_v2_result = command(
        actor,
        base_url,
        actor_csrf,
        observation_path(
            project_id, str(observation_v1["observationGlobalId"])
        ),
        observation_v2_body,
        OBSERVATION_V2_KEY,
        expected_status=201,
    )
    observation_v2 = _command_body(
        observation_v2_result,
        "observationPeriod",
        "P7-06 observation v2",
    )
    verify_observation(
        observation_v2,
        version=2,
        handover=package_v1,
        predecessor=observation_v1,
    )
    context_refs = observation_v2.get("contextReferences")
    retrospective_refs = observation_v2.get("retrospectiveReferences")
    require(
        isinstance(context_refs, list)
        and isinstance(retrospective_refs, list)
        and len(context_refs) == len(retrospective_refs) == 1
        and {
            key: context_refs[0].get(key)
            for key in ("kind", "globalId", "sourceVersion", "snapshotHash")
        }
        == {
            key: retrospective_refs[0].get(key)
            for key in ("kind", "globalId", "sourceVersion", "snapshotHash")
        }
        and context_refs[0].get("usage") == "context"
        and retrospective_refs[0].get("usage") == "retrospective"
        and not {
            "requirementKey",
            "role",
        }
        & (set(context_refs[0]) | set(retrospective_refs[0])),
        "P7-06 observation exact-source reuse or usage injection drifted",
    )
    after_observation_v2 = transition_counts(administrator, base_url, project_id)
    _assert_replay(
        actor,
        base_url,
        actor_csrf,
        observation_path(
            project_id, str(observation_v1["observationGlobalId"])
        ),
        observation_v2_body,
        OBSERVATION_V2_KEY,
        observation_v2_result.body,
        201,
        after_observation_v2,
        administrator,
        project_id,
    )

    _expect_problem_without_write(
        actor,
        base_url,
        actor_csrf,
        handover_path(project_id, str(package_v1["handoverGlobalId"])),
        handover_v2_body,
        STALE_HANDOVER_KEY,
        status=409,
        code="PRODUCTION_TRANSITION_VERSION_CONFLICT",
        administrator=administrator,
        project_id=project_id,
    )
    _expect_problem_without_write(
        actor,
        base_url,
        actor_csrf,
        observation_path(
            project_id, str(observation_v1["observationGlobalId"])
        ),
        observation_v2_body,
        STALE_OBSERVATION_KEY,
        status=409,
        code="PRODUCTION_TRANSITION_VERSION_CONFLICT",
        administrator=administrator,
        project_id=project_id,
    )
    wrong_source = deepcopy(repeated_source)
    wrong_source["expectedVersion"] = int(wrong_source["expectedVersion"]) + 1
    rollback_body = observation_revision_payload(observation_v2, wrong_source)
    _expect_problem_without_write(
        actor,
        base_url,
        actor_csrf,
        observation_path(
            project_id, str(observation_v1["observationGlobalId"])
        ),
        rollback_body,
        ROLLBACK_OBSERVATION_KEY,
        status=422,
        code="VALIDATION_FAILED",
        administrator=administrator,
        project_id=project_id,
    )

    verify_project_first_idor(
        acknowledgement_actor,
        actor,
        base_url,
        acknowledgement_csrf,
        actor_csrf,
        second_project_id=str(context["secondProjectGlobalId"]),
        second_project_version=int(context["secondProjectOptimisticVersion"]),
        target_package=package_v2,
        target_observation=observation_v2,
        handover_payload={
            "expectedRevisionGlobalId": package_v2["globalId"],
            "expectedSnapshotHash": package_v2["snapshotHash"],
            "content": handover_content(
                context, published, sources, version=3
            ),
        },
        observation_payload=observation_revision_payload(
            observation_v2, repeated_source
        ),
        administrator=administrator,
        target_project_id=project_id,
    )
    verify_generic_mutation_denial(
        actor,
        base_url,
        actor_csrf,
        project_id,
    )
    final_workspace = transition_workspace(actor, base_url, project_id)
    _verify_workspace_history(
        final_workspace,
        expected_handover_count=2,
        expected_observation_count=2,
    )
    require(
        [
            value["revision"]["handoverVersion"]
            for value in final_workspace["handoverHistory"]
        ]
        == [1, 2]
        and all(
            len(value["acknowledgements"]) == 2
            and value["fullyAcknowledged"] is True
            for value in final_workspace["handoverHistory"]
        )
        and [
            value["observationVersion"]
            for value in final_workspace["observationHistory"]
        ]
        == [1, 2],
        "P7-06 final immutable reconstruction drifted",
    )
    final_counts = transition_counts(administrator, base_url, project_id)
    expected_counts = {
        "NPI Production Transition Policy": 1,
        "NPI Production Transition Policy Version": 1,
        "NPI Handover Package Revision": 2,
        "NPI Handover Acknowledgement": 4,
        "NPI Observation Period Revision": 2,
        "NPI Production Transition Command Idempotency": 11,
        "audit:production_transition_policy.create": 1,
        "audit:production_transition_policy.edit": 1,
        "audit:production_transition_policy.publish": 1,
        "audit:production_transition_policy.next_version": 0,
        "audit:production_handover.create": 1,
        "audit:production_handover.revise": 1,
        "audit:production_handover.acknowledge": 4,
        "audit:observation_period.create": 1,
        "audit:observation_period.revise": 1,
    }
    require(final_counts == expected_counts, "P7-06 authority cardinality drifted")
    persisted_redaction = run_bench_fixture(
        "verify_production_transition_persisted_redaction",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    require(
        persisted_redaction.get("sealedResponseCount") == 11
        and persisted_redaction.get("auditSummaryCount") == 11
        and persisted_redaction.get("sensitivePersisted") is False,
        "P7-06 controlled-Site persisted redaction evidence drifted",
    )
    after_persistence = run_bench_fixture(
        "production_transition_persistence_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    require(
        before_persistence.get("downstreamSnapshot")
        == after_persistence.get("downstreamSnapshot"),
        "P7-06 controlled runtime mutated Project/Gate/downstream/ERP truth",
    )
    return {
        "acknowledgementCount": 4,
        "auditEventCount": 11,
        "exactSourceCount": 9,
        "handoverRevisionCount": 2,
        "metadataSynchronized": True,
        "observationRevisionCount": 2,
        "p705FileTupleRejected": True,
        "policyVersionCount": 1,
        "providerCount": 5,
        "providerRepositoryCalls": 0,
        "sealedReceiptCount": 11,
        "sensitivePersisted": False,
        "technicalSlotAcknowledgements": True,
        "zeroDownstreamEffects": True,
    }


def run_replay(
    administrator,
    actor,
    acknowledgement_actor,
    base_url: str,
    actor_csrf: str,
    acknowledgement_csrf: str,
) -> dict[str, object]:
    project_id, _project_version = document_runtime.fixture_project(
        administrator, base_url
    )
    context = run_bench_fixture(
        "production_transition_fixture_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    source_context = run_bench_fixture(
        "production_transition_source_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    sources = source_context.get("exactSources")
    require(
        isinstance(sources, list) and len(sources) == 9,
        "P7-06 replay source catalog drifted",
    )
    before_persistence = run_bench_fixture(
        "production_transition_persistence_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    before_counts = transition_counts(administrator, base_url, project_id)
    catalog = policy_catalog(actor, base_url, project_id)
    policies = [
        value
        for value in catalog["policies"]
        if isinstance(value, dict) and value.get("policyCode") == POLICY_CODE
    ]
    require(len(policies) == 1, "P7-06 retained published policy is unavailable")
    published = dict(policies[0])
    policy_id = str(published["policyGlobalId"])
    policy_version = int(published["policyVersion"])
    workspace = transition_workspace(actor, base_url, project_id)
    _verify_workspace_history(
        workspace,
        expected_handover_count=2,
        expected_observation_count=2,
    )
    handover_history = workspace["handoverHistory"]
    observation_history = workspace["observationHistory"]
    package_v1 = dict(handover_history[0]["revision"])
    package_v2 = dict(handover_history[1]["revision"])
    observation_v1 = dict(observation_history[0])
    observation_v2 = dict(observation_history[1])

    created = command(
        actor,
        base_url,
        actor_csrf,
        policy_path(),
        create_policy_payload(context),
        CREATE_POLICY_KEY,
        expected_status=201,
        replayed=True,
    )
    verify_policy_response(
        _object(created.body, "P7-06 create replay"),
        publication_state="draft",
        optimistic_version=1,
    )
    edited = command(
        actor,
        base_url,
        actor_csrf,
        policy_path(policy_id, policy_version),
        edit_policy_payload(context, 1),
        EDIT_POLICY_KEY,
        method="PUT",
        expected_status=200,
        replayed=True,
    )
    edited_body = _object(edited.body, "P7-06 edit replay")
    verify_policy_response(
        edited_body, publication_state="draft", optimistic_version=2
    )
    published_replay = command(
        actor,
        base_url,
        actor_csrf,
        policy_path(policy_id, policy_version, publish=True),
        {
            "expectedOptimisticVersion": 2,
            "expectedSnapshotHash": edited_body["snapshotHash"],
        },
        PUBLISH_POLICY_KEY,
        expected_status=200,
        replayed=True,
    )
    require(
        published_replay.body == published,
        "P7-06 published policy replay lost sealed truth",
    )

    handover_v1_body = handover_content(context, published, sources, version=1)
    handover_v1 = command(
        actor,
        base_url,
        actor_csrf,
        handover_path(project_id),
        handover_v1_body,
        HANDOVER_V1_KEY,
        expected_status=201,
        replayed=True,
    )
    require(
        handover_v1.body
        == {"projectGlobalId": project_id, "handoverPackage": package_v1},
        "P7-06 handover v1 replay lost sealed truth",
    )
    acknowledgements_by_version = {
        version: {
            str(value["slotKey"]): value
            for value in handover_history[version - 1]["acknowledgements"]
        }
        for version in (1, 2)
    }
    for slot in ("sender", "receiver"):
        replay = command(
            acknowledgement_actor,
            base_url,
            acknowledgement_csrf,
            handover_path(
                project_id,
                str(package_v1["handoverGlobalId"]),
                1,
            ),
            acknowledgement_payload(package_v1, slot),
            ACK_V1_KEYS[slot],
            expected_status=201,
            replayed=True,
        )
        require(
            replay.body
            == {
                "projectGlobalId": project_id,
                "handoverPackage": package_v1,
                "acknowledgement": acknowledgements_by_version[1][slot],
            },
            "P7-06 v1 acknowledgement replay lost sealed truth",
        )
    handover_v2_body = {
        "expectedRevisionGlobalId": package_v1["globalId"],
        "expectedSnapshotHash": package_v1["snapshotHash"],
        "content": handover_content(context, published, sources, version=2),
    }
    handover_v2 = command(
        actor,
        base_url,
        actor_csrf,
        handover_path(project_id, str(package_v1["handoverGlobalId"])),
        handover_v2_body,
        HANDOVER_V2_KEY,
        expected_status=201,
        replayed=True,
    )
    require(
        handover_v2.body
        == {"projectGlobalId": project_id, "handoverPackage": package_v2},
        "P7-06 handover v2 replay lost sealed truth",
    )
    for slot in ("sender", "receiver"):
        replay = command(
            acknowledgement_actor,
            base_url,
            acknowledgement_csrf,
            handover_path(
                project_id,
                str(package_v2["handoverGlobalId"]),
                2,
            ),
            acknowledgement_payload(package_v2, slot),
            ACK_V2_KEYS[slot],
            expected_status=201,
            replayed=True,
        )
        require(
            replay.body
            == {
                "projectGlobalId": project_id,
                "handoverPackage": package_v2,
                "acknowledgement": acknowledgements_by_version[2][slot],
            },
            "P7-06 v2 acknowledgement replay lost sealed truth",
        )
    observation_v1_body = observation_create_payload(
        context, published, package_v1, sources
    )
    observation_v1_replay = command(
        actor,
        base_url,
        actor_csrf,
        observation_path(project_id),
        observation_v1_body,
        OBSERVATION_V1_KEY,
        expected_status=201,
        replayed=True,
    )
    require(
        observation_v1_replay.body
        == {"projectGlobalId": project_id, "observationPeriod": observation_v1},
        "P7-06 observation v1 replay lost sealed truth",
    )
    observation_v2_body = observation_revision_payload(
        observation_v1, sources[0]
    )
    observation_v2_replay = command(
        actor,
        base_url,
        actor_csrf,
        observation_path(
            project_id, str(observation_v1["observationGlobalId"])
        ),
        observation_v2_body,
        OBSERVATION_V2_KEY,
        expected_status=201,
        replayed=True,
    )
    require(
        observation_v2_replay.body
        == {"projectGlobalId": project_id, "observationPeriod": observation_v2},
        "P7-06 observation v2 replay lost sealed truth",
    )
    after_persistence = run_bench_fixture(
        "production_transition_persistence_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    require(
        transition_counts(administrator, base_url, project_id) == before_counts
        and before_persistence == after_persistence
        and transition_workspace(actor, base_url, project_id) == workspace,
        "P7-06 cross-process replay changed sealed truth or cardinality",
    )
    persisted_redaction = run_bench_fixture(
        "verify_production_transition_persisted_redaction",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    require(
        persisted_redaction.get("sealedResponseCount") == 11
        and persisted_redaction.get("auditSummaryCount") == 11
        and persisted_redaction.get("sensitivePersisted") is False,
        "P7-06 replay persisted redaction evidence drifted",
    )
    return {
        "acknowledgementCount": 4,
        "crossProcessReplay": True,
        "exactSourceCount": 9,
        "handoverRevisionCount": 2,
        "observationRevisionCount": 2,
        "providerCount": 5,
        "sealedReceiptCount": 11,
        "sensitivePersisted": False,
    }


def route_disable_probe(
    administrator,
    actor,
    base_url: str,
    actor_csrf: str,
    *,
    expected_mode: str,
) -> dict[str, object]:
    require(expected_mode in {"disabled", "recovered"}, "P7-06 route mode drifted")
    project_id, _project_version = document_runtime.fixture_project(
        administrator, base_url
    )
    catalog = policy_catalog(actor, base_url, project_id) if expected_mode == "recovered" else None
    if catalog is None:
        policy_rows = list_resources(
            administrator,
            base_url,
            "NPI Production Transition Policy Version",
            filters=[["policy_code", "=", POLICY_CODE]],
            fields=["policy_global_id", "policy_version"],
        )
        require(len(policy_rows) == 1, "P7-06 retained route policy is unavailable")
        policy_id = str(policy_rows[0]["policy_global_id"])
        policy_version = int(policy_rows[0]["policy_version"])
    else:
        policies = [
            value
            for value in catalog["policies"]
            if isinstance(value, dict) and value.get("policyCode") == POLICY_CODE
        ]
        require(len(policies) == 1, "P7-06 retained route policy drifted")
        policy_id = str(policies[0]["policyGlobalId"])
        policy_version = int(policies[0]["policyVersion"])
    handovers = list_resources(
        administrator,
        base_url,
        "NPI Handover Package Revision",
        filters=[["project_global_id", "=", project_id]],
        fields=["handover_global_id", "handover_version"],
    )
    observations = list_resources(
        administrator,
        base_url,
        "NPI Observation Period Revision",
        filters=[["project_global_id", "=", project_id]],
        fields=["observation_global_id"],
    )
    require(
        len(handovers) == 2 and len(observations) == 2,
        "P7-06 retained route identities drifted",
    )
    handover_ids = {str(value["handover_global_id"]) for value in handovers}
    observation_ids = {str(value["observation_global_id"]) for value in observations}
    require(
        len(handover_ids) == len(observation_ids) == 1,
        "P7-06 retained route streams drifted",
    )
    handover_id = next(iter(handover_ids))
    observation_id = next(iter(observation_ids))
    before_counts = transition_counts(administrator, base_url, project_id)
    before_context = run_bench_fixture(
        "production_transition_persistence_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    cases: tuple[tuple[str, str, dict[str, object] | None, str | None], ...] = (
        ("GET", f"{policy_path()}?projectId={project_id}", None, None),
        ("POST", policy_path(), {}, "policy-create"),
        (
            "PUT",
            policy_path(policy_id, policy_version),
            {},
            "policy-edit",
        ),
        (
            "POST",
            policy_path(policy_id, policy_version, publish=True),
            {},
            "policy-publish",
        ),
        (
            "POST",
            policy_path(policy_id, next_version=True),
            {},
            "policy-next",
        ),
        ("GET", workspace_path(project_id), None, None),
        ("POST", handover_path(project_id), {}, "handover-create"),
        (
            "POST",
            handover_path(project_id, handover_id),
            {},
            "handover-revise",
        ),
        (
            "POST",
            handover_path(project_id, handover_id, 2),
            {},
            "handover-ack",
        ),
        ("POST", observation_path(project_id), {}, "observation-create"),
        (
            "POST",
            observation_path(project_id, observation_id),
            {},
            "observation-revise",
        ),
    )
    for index, (method, path, payload, suffix) in enumerate(cases):
        result = transition_request(
            actor,
            base_url,
            path,
            method=method,
            payload=payload,
            csrf_token=actor_csrf,
            idempotency_key=(
                f"p7-06-route-{FIXTURE_RUN_ID}-{expected_mode}-{suffix}"
                if suffix is not None
                else None
            ),
            query_key=f"route-{expected_mode}-{index}",
        )
        require_safe_payload(result.body, "P7-06 route probe")
        if expected_mode == "disabled":
            validate_problem(
                result, 503, "PRODUCTION_TRANSITION_ROUTES_DISABLED"
            )
        elif method == "GET":
            require(result.status == 200, "P7-06 recovered GET route did not reopen")
        else:
            validate_problem(result, 422, "VALIDATION_FAILED")
            require(
                result.headers.get("Idempotency-Replayed") == "false",
                "P7-06 recovered route reported a false replay",
            )
    after_context = run_bench_fixture(
        "production_transition_persistence_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    require(
        transition_counts(administrator, base_url, project_id) == before_counts
        and before_context == after_context,
        "P7-06 route probe mutated retained authority or downstream truth",
    )
    return {"routeCount": 11, "routeMode": expected_mode, "stateChanged": False}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the controlled P7-06 Production Transition runtime.",
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
            "P7-06 Bench fixture arguments are invalid",
        )
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "P7-06 fixture kwargs are invalid")
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return

    require(
        isinstance(arguments.base_url, str)
        and arguments.fixture_kwargs is None
        and document_runtime.CALLER_SUPPLIED_FIXTURE_RUN_ID is not None
        and os.environ.get("NPI_DOCUMENT_RUNTIME_RUN_ID") == FIXTURE_RUN_ID,
        "P7-06 runtime base URL and fixture namespace are required",
    )
    require(
        int(arguments.route_disable_probe is not None) + int(arguments.replay_only)
        <= 1,
        "P7-06 runtime modes are mutually exclusive",
    )
    base_url = validate_local_fixture_inputs(
        arguments.base_url, "Administrator", ACTOR_USER
    )
    validate_local_fixture_inputs(base_url, "Administrator", UNRELATED_USER)
    validate_local_fixture_inputs(
        base_url, "Administrator", ACKNOWLEDGEMENT_USER
    )
    require(
        ACTOR_USER.endswith("@example.invalid")
        and UNRELATED_USER.endswith("@example.invalid")
        and ACKNOWLEDGEMENT_USER.endswith("@example.invalid")
        and len({ACTOR_USER, UNRELATED_USER, ACKNOWLEDGEMENT_USER}) == 3
        and FIXTURE_RUN_ID != "0" * 32,
        "P7-06 runtime fixture identity drifted",
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
    acknowledgement_actor = login(
        base_url, ACKNOWLEDGEMENT_USER, fixture_password
    )
    acknowledgement_csrf = bootstrap_csrf(
        acknowledgement_actor, base_url, ACKNOWLEDGEMENT_USER
    )
    if arguments.route_disable_probe is not None:
        result = route_disable_probe(
            administrator,
            actor,
            base_url,
            actor_csrf,
            expected_mode=arguments.route_disable_probe,
        )
    elif arguments.replay_only:
        result = run_replay(
            administrator,
            actor,
            acknowledgement_actor,
            base_url,
            actor_csrf,
            acknowledgement_csrf,
        )
    else:
        unrelated = login(base_url, UNRELATED_USER, fixture_password)
        unrelated_csrf = bootstrap_csrf(unrelated, base_url, UNRELATED_USER)
        result = run_fresh(
            administrator,
            actor,
            unrelated,
            acknowledgement_actor,
            base_url,
            actor_csrf,
            unrelated_csrf,
            acknowledgement_csrf,
        )
    require_safe_payload(result, "P7-06 sanitized verifier evidence")
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
