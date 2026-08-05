from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

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
    create_resource,
    get_resource,
    list_resources,
    update_resource,
)


SITE_NAME = document_runtime.SITE_NAME
RUNTIME_MARKER = document_runtime.RUNTIME_MARKER
DATABASE_NAME = document_runtime.DATABASE_NAME
DATABASE_USER = document_runtime.DATABASE_USER
DATABASE_PORT = document_runtime.DATABASE_PORT
ROOT = Path(__file__).resolve().parents[1]
BENCH_PATH = ROOT / "tmp" / "frappe-bench"
FIXTURE_RUN_ID = document_runtime.FIXTURE_RUN_ID
FIXTURE_PREFIX = f"p5-04-runtime-r1-{FIXTURE_RUN_ID}"
TENANT_ID = document_runtime.TENANT_ID
BUSINESS_CODE = document_runtime.BUSINESS_CODE
ACTOR_USER = document_runtime.BASELINE_USER
UNRELATED_USER = (
    f"npi-ebom-{FIXTURE_RUN_ID[:20]}-unrelated@example.invalid"
)


def fixture_id(scope: str) -> str:
    return str(
        uuid5(
            NAMESPACE_URL,
            (
                "https://npi-one.example.invalid/runtime/p5-04/"
                f"r1-{FIXTURE_RUN_ID}/{scope}"
            ),
        )
    )


POLICY_ID = fixture_id("ebom-policy")
POLICY_VERSION = 1
POLICY_VERSION_KEY = f"{POLICY_ID}:{POLICY_VERSION}"
POLICY_KEY = f"p5_04_runtime_{FIXTURE_RUN_ID}"
ENGINEERING_BOM_FIELD = "engineering" + "BomKey"
ENGINEERING_BOM_KEY = f"synthetic_ebom_{FIXTURE_RUN_ID[:16]}"
CREATE_KEY = f"{FIXTURE_PREFIX}-create"
CREATE_CONFLICT_KEY = CREATE_KEY
INVALID_REVISION_KEY = f"{FIXTURE_PREFIX}-invalid-revision"
REVISE_KEY = f"{FIXTURE_PREFIX}-revise"
SUBMIT_KEY = f"{FIXTURE_PREFIX}-submit-review"
REVIEW_KEY = f"{FIXTURE_PREFIX}-review"
RELEASE_KEY = f"{FIXTURE_PREFIX}-release"
STALE_TRANSITION_KEY = f"{FIXTURE_PREFIX}-stale-transition"
PREDECESSOR_ROUTE_QUERY = "p504-predecessor-" + "route-isolation"

EBOM_DOCTYPES = (
    "NPI EBOM Policy",
    "NPI EBOM Policy Version",
    "NPI Engineering BOM",
    "NPI Engineering BOM Revision",
    "NPI Engineering BOM Line",
    "NPI EBOM Revision Lifecycle",
    "NPI EBOM Lifecycle Event",
    "NPI EBOM Command Idempotency",
)

_TRACE_PATTERN = re.compile(r"^trace-[a-f0-9]{32}$")
_TYPE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,127}$")
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_RUNTIME_STAGE_CODES = frozenset(
    {
        "P504_RUNTIME_EMPTY_WORKSPACE",
        "P504_RUNTIME_GUEST_AUTHORIZATION",
        "P504_RUNTIME_UNRELATED_AUTHORIZATION",
        "P504_RUNTIME_CREATE",
        "P504_RUNTIME_CREATE_REPLAY",
        "P504_RUNTIME_IDEMPOTENCY_CONFLICT",
        "P504_RUNTIME_INVALID_REVISION_ROLLBACK",
        "P504_RUNTIME_SUCCESSOR_REVISION",
        "P504_RUNTIME_COMPARISON",
        "P504_RUNTIME_SUBMIT_REVIEW",
        "P504_RUNTIME_REVIEW",
        "P504_RUNTIME_RELEASE",
        "P504_RUNTIME_STALE_TRANSITION",
        "P504_RUNTIME_FINAL_WORKSPACE",
        "P504_RUNTIME_ROUTE_DISABLED",
        "P504_RUNTIME_ROUTE_RECOVERED",
        "P504_RUNTIME_PREDECESSOR_ROUTE_ISOLATION",
        "P504_RUNTIME_REPLAY_CREATE",
        "P504_RUNTIME_REPLAY_RELEASE",
    }
)


class RuntimeStageFailure(RuntimeError):
    """Expose only one allowlisted stage, validated type, and exact trace."""

    def __init__(
        self,
        code: str,
        trace_id: str,
        *,
        exception_type: str,
    ) -> None:
        super().__init__("Controlled EBOM runtime stage failed")
        if code not in _RUNTIME_STAGE_CODES:
            raise ValueError("EBOM runtime diagnostic code is not allowlisted")
        if _TRACE_PATTERN.fullmatch(trace_id) is None:
            raise ValueError("EBOM runtime diagnostic trace identity is invalid")
        if _TYPE_PATTERN.fullmatch(exception_type) is None:
            raise ValueError("EBOM runtime diagnostic exception type is invalid")
        self.code = code
        self.trace_id = trace_id
        self.exception_type = exception_type


def runtime_stage_diagnostic(error: RuntimeStageFailure) -> str:
    return (
        f"[diagnostic_code={error.code}; "
        f"exc_type={error.exception_type}; "
        f"trace_id={error.trace_id}]"
    )


def require_stage_status(
    result: HttpResult,
    expected: set[int],
    code: str,
) -> None:
    if result.status in expected:
        return
    exception_type = result.body.get("exc_type")
    if (
        not isinstance(exception_type, str)
        or _TYPE_PATTERN.fullmatch(exception_type) is None
    ):
        exception_type = "HttpStatusError"
    trace_id = result.trace_id
    if not isinstance(trace_id, str) or _TRACE_PATTERN.fullmatch(trace_id) is None:
        raise ValueError("Controlled EBOM response trace identity is invalid")
    raise RuntimeStageFailure(
        code,
        trace_id,
        exception_type=exception_type,
    )


def fixture_project(administrator, base_url: str) -> str:
    rows = list_resources(
        administrator,
        base_url,
        "NPI Engineering Project",
        filters=[
            ["tenant_id", "=", TENANT_ID],
            ["business_code", "=", BUSINESS_CODE],
        ],
        fields=["global_id", "business_code"],
    )
    require(
        len(rows) == 1
        and rows[0].get("business_code") == BUSINESS_CODE
        and isinstance(rows[0].get("global_id"), str),
        "Controlled EBOM runtime Project identity drifted",
    )
    return str(rows[0]["global_id"])


def ebom_path(project_id: str, ebom_id: str | None = None) -> str:
    base = f"/api/npi/v1/projects/{project_id}/eboms"
    return base if ebom_id is None else f"{base}/{ebom_id}"


def ebom_request(
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
    return document_runtime.npi_request(
        opener,
        base_url,
        path,
        method=method,
        payload=payload,
        csrf_token=csrf_token,
        idempotency_key=idempotency_key,
        query_key=f"p504-{query_key}",
    )


def initial_lines() -> list[dict[str, object]]:
    return [
        {
            "lineKey": "10",
            "engineeringItemId": "synthetic:assembly-a",
            "description": "Synthetic assembly A",
            "quantity": "1.000",
            "engineeringUom": "EA",
            "effectivityStart": "2026-08-05",
            "attributes": {"material": "ABS"},
        }
    ]


def successor_lines() -> list[dict[str, object]]:
    return [
        {
            "lineKey": "10",
            "engineeringItemId": "synthetic:assembly-a",
            "description": "Synthetic assembly A revised",
            "quantity": "2.000",
            "engineeringUom": "EA",
            "effectivityStart": "2026-08-05",
            "attributes": {"material": "PC"},
        },
        {
            "lineKey": "20",
            "parentLineKey": "10",
            "engineeringItemId": "synthetic:component-b",
            "description": "Synthetic component B",
            "quantity": "1.000",
            "engineeringUom": "EA",
            "attributes": {"material": "PC"},
        },
    ]


def create_payload(policy_hash: str) -> dict[str, object]:
    return {
        "policyGlobalId": POLICY_ID,
        "policyVersion": POLICY_VERSION,
        "policySnapshotHash": policy_hash,
        ENGINEERING_BOM_FIELD: ENGINEERING_BOM_KEY,
        "title": "Synthetic controlled EBOM",
        "reason": "Create the controlled runtime structure.",
        "effectivityNote": "Synthetic engineering scope only.",
        "lines": initial_lines(),
    }


def revision_payload(
    policy_hash: str,
    *,
    predecessor_id: str,
    predecessor_hash: str,
    lines: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "expectedEbomVersion": 2,
        "predecessorRevisionId": predecessor_id,
        "expectedPredecessorSnapshotHash": predecessor_hash,
        "policyGlobalId": POLICY_ID,
        "policyVersion": POLICY_VERSION,
        "policySnapshotHash": policy_hash,
        "reason": "Create an exact immutable successor.",
        "effectivityNote": "Synthetic comparison fixture.",
        "lines": successor_lines() if lines is None else lines,
    }


def transition_payload(
    policy_hash: str,
    revision_hash: str,
    lifecycle_version: int,
) -> dict[str, object]:
    return {
        "expectedEbomVersion": 3,
        "expectedRevisionSnapshotHash": revision_hash,
        "expectedLifecycleVersion": lifecycle_version,
        "policyGlobalId": POLICY_ID,
        "policyVersion": POLICY_VERSION,
        "policySnapshotHash": policy_hash,
    }


def ensure_policy(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    project_id: str,
) -> str:
    roots = list_resources(
        administrator,
        base_url,
        "NPI EBOM Policy",
        filters=[["global_id", "=", POLICY_ID]],
        fields=["global_id"],
    )
    require(not roots, "Controlled EBOM policy namespace is not fresh")
    created_root = create_resource(
        administrator,
        base_url,
        "NPI EBOM Policy",
        {
            "global_id": POLICY_ID,
            "tenant_id": TENANT_ID,
            "project_global_id": project_id,
            "policy_key": POLICY_KEY,
            "title": "Synthetic controlled EBOM policy",
            "enabled": 1,
        },
        csrf_token,
    )
    require(
        created_root.status in {200, 201}
        and created_root.body.get("data", {}).get("name") == POLICY_ID,
        "Controlled EBOM policy root creation failed",
    )
    draft = create_resource(
        administrator,
        base_url,
        "NPI EBOM Policy Version",
        {
            "ebom_policy": POLICY_ID,
            "policy_version": POLICY_VERSION,
            "title": "Synthetic controlled EBOM policy",
            "publication_state": "draft",
            "synthetic_namespace": "synthetic_runtime",
            "line_identity_mode": "caller_supplied_stable_key",
            "quantity_scale": 3,
            "maximum_nodes": 20,
            "engineering_uoms": ["EA"],
            "attribute_keys": ["material"],
            "creator_user_ids": [ACTOR_USER],
            "review_submitter_user_ids": [ACTOR_USER],
            "reviewer_user_ids": [ACTOR_USER],
            "release_authority_user_ids": [ACTOR_USER],
            "require_acyclic_graph": 1,
            "require_closed_alternates": 1,
            "require_effectivity_order": 1,
        },
        csrf_token,
    )
    require(
        draft.status in {200, 201}
        and draft.body.get("data", {}).get("name") == POLICY_VERSION_KEY,
        "Controlled EBOM policy draft creation failed",
    )
    published = update_resource(
        administrator,
        base_url,
        "NPI EBOM Policy Version",
        POLICY_VERSION_KEY,
        {"publication_state": "published"},
        csrf_token,
    )
    data = published.body.get("data", {})
    policy_hash = data.get("snapshot_hash")
    require(
        published.status == 200
        and data.get("publication_state") == "published"
        and isinstance(policy_hash, str)
        and _HASH_PATTERN.fullmatch(policy_hash) is not None,
        "Controlled EBOM policy publication failed",
    )
    return policy_hash


def exact_revision(result: HttpResult) -> tuple[dict[str, Any], dict[str, Any]]:
    ebom = result.body.get("ebom")
    revision = result.body.get("revision")
    require(
        isinstance(ebom, dict)
        and isinstance(revision, dict)
        and isinstance(ebom.get("globalId"), str)
        and isinstance(revision.get("globalId"), str)
        and _HASH_PATTERN.fullmatch(str(revision.get("snapshotHash"))) is not None,
        "Controlled EBOM command response shape drifted",
    )
    return ebom, revision


def command(
    actor,
    base_url: str,
    csrf_token: str,
    path: str,
    payload: dict[str, object],
    key: str,
    code: str,
) -> HttpResult:
    result = ebom_request(
        actor,
        base_url,
        path,
        method="POST",
        payload=payload,
        csrf_token=csrf_token,
        idempotency_key=key,
    )
    require_stage_status(result, {201}, code)
    return result


def assert_replayed(result: HttpResult, expected: str) -> None:
    require(
        result.headers.get("Idempotency-Replayed") == expected,
        "Controlled EBOM idempotency replay header drifted",
    )


def count_rows(
    administrator,
    base_url: str,
    doctype: str,
    project_id: str,
) -> list[dict[str, object]]:
    return list_resources(
        administrator,
        base_url,
        doctype,
        filters=[["project_global_id", "=", project_id]],
        fields=["name"],
    )


def run_fresh(
    administrator,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
) -> dict[str, object]:
    project_id = fixture_project(administrator, base_url)
    schema = run_bench_fixture(
        "verify_ebom_runtime_schema",
        {"fixture_run_id": FIXTURE_RUN_ID},
    )
    policy_hash = ensure_policy(
        administrator,
        base_url,
        csrf_token,
        project_id=project_id,
    )
    actor = login(base_url, ACTOR_USER, fixture_password)
    actor_csrf = bootstrap_csrf(actor, base_url, ACTOR_USER)
    document_runtime.create_internal_fixture_user(
        administrator,
        base_url,
        UNRELATED_USER,
        fixture_password,
        csrf_token,
    )
    try:
        empty = ebom_request(
            actor,
            base_url,
            ebom_path(project_id),
            query_key="empty",
        )
        require_stage_status(empty, {200}, "P504_RUNTIME_EMPTY_WORKSPACE")
        require(
            empty.body.get("items") == []
            and empty.body.get("permissions") == {"view": True, "create": True}
            and len(empty.body.get("policies", [])) == 1
            and empty.body["policies"][0].get("snapshotHash") == policy_hash,
            "Controlled EBOM empty workspace or policy truth drifted",
        )

        guest = ebom_request(
            urllib.request.build_opener(),
            base_url,
            ebom_path(project_id),
            query_key="guest",
        )
        if guest.status != 401:
            require_stage_status(guest, {401}, "P504_RUNTIME_GUEST_AUTHORIZATION")
        validate_problem(guest, 401, "AUTHENTICATION_REQUIRED")
        unrelated = login(base_url, UNRELATED_USER, fixture_password)
        denied = ebom_request(
            unrelated,
            base_url,
            ebom_path(project_id),
            query_key="unrelated",
        )
        if denied.status != 404:
            require_stage_status(
                denied,
                {404},
                "P504_RUNTIME_UNRELATED_AUTHORIZATION",
            )
        validate_problem(denied, 404, "EBOM_UNAVAILABLE")

        created = command(
            actor,
            base_url,
            actor_csrf,
            ebom_path(project_id),
            create_payload(policy_hash),
            CREATE_KEY,
            "P504_RUNTIME_CREATE",
        )
        assert_replayed(created, "false")
        ebom, revision_one = exact_revision(created)
        ebom_id = str(ebom["globalId"])
        revision_one_id = str(revision_one["globalId"])
        revision_one_hash = str(revision_one["snapshotHash"])
        require(
            ebom.get("optimisticVersion") == 2
            and ebom.get("latestRevision", {}).get("revisionNumber") == 1
            and revision_one.get("revisionNumber") == 1
            and revision_one.get("lifecycle")
            == {"state": "draft", "version": 1, "lastEventId": None}
            and len(revision_one.get("lines", [])) == 1,
            "Controlled EBOM first immutable revision drifted",
        )

        replay = command(
            actor,
            base_url,
            actor_csrf,
            ebom_path(project_id),
            create_payload(policy_hash),
            CREATE_KEY,
            "P504_RUNTIME_CREATE_REPLAY",
        )
        assert_replayed(replay, "true")
        require(replay.body == created.body, "Controlled EBOM create replay drifted")

        conflict_payload = create_payload(policy_hash)
        conflict_payload["title"] = "Different synthetic intent"
        conflict = ebom_request(
            actor,
            base_url,
            ebom_path(project_id),
            method="POST",
            payload=conflict_payload,
            csrf_token=actor_csrf,
            idempotency_key=CREATE_CONFLICT_KEY,
        )
        if conflict.status != 409:
            require_stage_status(
                conflict,
                {409},
                "P504_RUNTIME_IDEMPOTENCY_CONFLICT",
            )
        validate_problem(conflict, 409, "EBOM_IDEMPOTENCY_CONFLICT")

        invalid_payload = revision_payload(
            policy_hash,
            predecessor_id=revision_one_id,
            predecessor_hash=revision_one_hash,
            lines=[
                {
                    "lineKey": "10",
                    "parentLineKey": "10",
                    "engineeringItemId": "synthetic:invalid-cycle",
                    "description": "Invalid synthetic self cycle",
                    "quantity": "1.000",
                    "engineeringUom": "EA",
                    "attributes": {"material": "ABS"},
                }
            ],
        )
        invalid = ebom_request(
            actor,
            base_url,
            f"{ebom_path(project_id, ebom_id)}/revisions",
            method="POST",
            payload=invalid_payload,
            csrf_token=actor_csrf,
            idempotency_key=INVALID_REVISION_KEY,
        )
        if invalid.status != 422:
            require_stage_status(
                invalid,
                {422},
                "P504_RUNTIME_INVALID_REVISION_ROLLBACK",
            )
        validate_problem(invalid, 422, "VALIDATION_FAILED")
        after_invalid = ebom_request(
            actor,
            base_url,
            ebom_path(project_id, ebom_id),
            query_key="after-invalid",
        )
        require_stage_status(
            after_invalid,
            {200},
            "P504_RUNTIME_INVALID_REVISION_ROLLBACK",
        )
        require(
            after_invalid.body.get("ebom", {}).get("optimisticVersion") == 2
            and len(after_invalid.body.get("revisions", [])) == 1,
            "Invalid EBOM successor was not rolled back",
        )

        revised = command(
            actor,
            base_url,
            actor_csrf,
            f"{ebom_path(project_id, ebom_id)}/revisions",
            revision_payload(
                policy_hash,
                predecessor_id=revision_one_id,
                predecessor_hash=revision_one_hash,
            ),
            REVISE_KEY,
            "P504_RUNTIME_SUCCESSOR_REVISION",
        )
        revised_ebom, revision_two = exact_revision(revised)
        revision_two_id = str(revision_two["globalId"])
        revision_two_hash = str(revision_two["snapshotHash"])
        require(
            revised_ebom.get("optimisticVersion") == 3
            and revised_ebom.get("latestRevision", {}).get("revisionNumber") == 2
            and revision_two.get("revisionNumber") == 2
            and revision_two.get("predecessorRevisionId") == revision_one_id
            and revision_two.get("predecessorSnapshotHash") == revision_one_hash
            and len(revision_two.get("lines", [])) == 2,
            "Controlled EBOM successor identity drifted",
        )

        compared = ebom_request(
            actor,
            base_url,
            (
                f"{ebom_path(project_id, ebom_id)}/compare"
                f"?fromRevisionId={revision_one_id}"
                f"&toRevisionId={revision_two_id}"
            ),
            query_key="compare",
        )
        require_stage_status(compared, {200}, "P504_RUNTIME_COMPARISON")
        require(
            compared.body.get("identical") is False
            and compared.body.get("summary")
            == {
                "added": 1,
                "removed": 0,
                "quantity": 1,
                "substitution": 0,
                "attribute": 1,
            }
            and [
                (change.get("lineKey"), change.get("changeType"))
                for change in compared.body.get("changes", [])
            ]
            == [("10", "quantity"), ("10", "attribute"), ("20", "added")],
            "Controlled EBOM deterministic comparison drifted",
        )

        transition_base = transition_payload(policy_hash, revision_two_hash, 1)
        submitted = command(
            actor,
            base_url,
            actor_csrf,
            f"{ebom_path(project_id, ebom_id)}/revisions/{revision_two_id}:submit-review",
            {**transition_base, "reason": "Ready for controlled review."},
            SUBMIT_KEY,
            "P504_RUNTIME_SUBMIT_REVIEW",
        )
        require(
            submitted.body.get("revision", {}).get("lifecycle", {}).get("state")
            == "in_review",
            "Controlled EBOM review submission drifted",
        )
        reviewed = command(
            actor,
            base_url,
            actor_csrf,
            f"{ebom_path(project_id, ebom_id)}/revisions/{revision_two_id}:review",
            {
                **transition_payload(policy_hash, revision_two_hash, 2),
                "decision": "approve",
                "reason": "Controlled review approved.",
            },
            REVIEW_KEY,
            "P504_RUNTIME_REVIEW",
        )
        require(
            reviewed.body.get("revision", {}).get("lifecycle", {}).get("state")
            == "approved",
            "Controlled EBOM review decision drifted",
        )
        release_payload = {
            **transition_payload(policy_hash, revision_two_hash, 3),
            "confirmed": True,
            "confirmationIntent": "release_exact_ebom_revision",
        }
        released = command(
            actor,
            base_url,
            actor_csrf,
            f"{ebom_path(project_id, ebom_id)}/revisions/{revision_two_id}:release",
            release_payload,
            RELEASE_KEY,
            "P504_RUNTIME_RELEASE",
        )
        assert_replayed(released, "false")
        released_revision = released.body.get("revision", {})
        require(
            released_revision.get("lifecycle", {}).get("state") == "released"
            and released_revision.get("lifecycle", {}).get("version") == 4
            and [event.get("eventType") for event in released_revision.get("events", [])]
            == ["review_submitted", "review_approved", "released"],
            "Controlled EBOM exact release history drifted",
        )

        stale = ebom_request(
            actor,
            base_url,
            f"{ebom_path(project_id, ebom_id)}/revisions/{revision_two_id}:review",
            method="POST",
            payload={
                **transition_payload(policy_hash, revision_two_hash, 2),
                "decision": "approve",
                "reason": "Stale controlled request.",
            },
            csrf_token=actor_csrf,
            idempotency_key=STALE_TRANSITION_KEY,
        )
        if stale.status != 409:
            require_stage_status(stale, {409}, "P504_RUNTIME_STALE_TRANSITION")
        validate_problem(stale, 409, "EBOM_STATE_CONFLICT")

        final_detail = ebom_request(
            actor,
            base_url,
            ebom_path(project_id, ebom_id),
            query_key="final",
        )
        require_stage_status(final_detail, {200}, "P504_RUNTIME_FINAL_WORKSPACE")
        revisions = final_detail.body.get("revisions", [])
        require(
            len(revisions) == 2
            and revisions[0].get("globalId") == revision_two_id
            and revisions[0].get("lifecycle", {}).get("state") == "released"
            and revisions[1].get("globalId") == revision_one_id
            and revisions[1].get("lifecycle", {}).get("state") == "draft",
            "Controlled EBOM final immutable workspace drifted",
        )

        expected_counts = {
            "NPI EBOM Policy": 1,
            "NPI EBOM Policy Version": 1,
            "NPI Engineering BOM": 1,
            "NPI Engineering BOM Revision": 2,
            "NPI Engineering BOM Line": 3,
            "NPI EBOM Revision Lifecycle": 2,
            "NPI EBOM Lifecycle Event": 3,
            "NPI EBOM Command Idempotency": 5,
        }
        for doctype, expected in expected_counts.items():
            require(
                len(count_rows(administrator, base_url, doctype, project_id))
                == expected,
                f"Controlled EBOM persisted {doctype} cardinality drifted",
            )
        expected_audits = {
            "ebom.create": CREATE_KEY,
            "ebom.revise": REVISE_KEY,
            "ebom.submit_review": SUBMIT_KEY,
            "ebom.review": REVIEW_KEY,
            "ebom.release": RELEASE_KEY,
        }
        for operation, key in expected_audits.items():
            rows = list_resources(
                administrator,
                base_url,
                "NPI Audit Event",
                filters=[
                    ["operation", "=", operation],
                    ["trace_id", "=", document_runtime.fixture_trace_id(key)],
                ],
                fields=["operation", "result", "trace_id"],
            )
            require(
                len(rows) == 1 and rows[0].get("trace_id"),
                f"Controlled EBOM audit cardinality drifted for {operation}",
            )
    finally:
        delete_disposable_user(
            administrator,
            base_url,
            UNRELATED_USER,
            csrf_token,
        )
    return {
        "auditOperations": 5,
        "comparisonChanges": 3,
        "crossProcessReplayReady": True,
        "ebomId": ebom_id,
        "fixtureRunId": FIXTURE_RUN_ID,
        "immutableRevisions": 2,
        "metadataSynchronized": schema.get("metadataSynchronized"),
        "projectId": project_id,
        "releasedRevisionId": revision_two_id,
        "rollbackVerified": True,
    }


def route_disable_probe(
    administrator,
    base_url: str,
    fixture_password: str,
    *,
    expected_mode: str,
) -> None:
    project_id = fixture_project(administrator, base_url)
    actor = login(base_url, ACTOR_USER, fixture_password)
    result = ebom_request(
        actor,
        base_url,
        ebom_path(project_id),
        query_key=f"route-{expected_mode}",
    )
    if expected_mode == "disabled":
        if result.status != 503:
            require_stage_status(result, {503}, "P504_RUNTIME_ROUTE_DISABLED")
        validate_problem(result, 503, "EBOM_ROUTES_DISABLED")
        documents = document_runtime.npi_request(
            actor,
            base_url,
            f"/api/npi/v1/projects/{project_id}/documents",
            query_key=PREDECESSOR_ROUTE_QUERY,
        )
        require_stage_status(
            documents,
            {200},
            "P504_RUNTIME_PREDECESSOR_ROUTE_ISOLATION",
        )
        require(
            len(documents.body.get("items", [])) == 1,
            "P5-04 route switch changed the retained Document route",
        )
        return
    require_stage_status(result, {200}, "P504_RUNTIME_ROUTE_RECOVERED")
    require(
        len(result.body.get("items", [])) == 1,
        "Recovered controlled EBOM route truth drifted",
    )


def run_replay(
    administrator,
    base_url: str,
    fixture_password: str,
) -> None:
    project_id = fixture_project(administrator, base_url)
    version = get_resource(
        administrator,
        base_url,
        "NPI EBOM Policy Version",
        POLICY_VERSION_KEY,
    )
    policy_hash = version.body.get("data", {}).get("snapshot_hash")
    require(
        version.status == 200
        and isinstance(policy_hash, str)
        and _HASH_PATTERN.fullmatch(policy_hash) is not None,
        "Controlled EBOM replay policy is unavailable",
    )
    actor = login(base_url, ACTOR_USER, fixture_password)
    actor_csrf = bootstrap_csrf(actor, base_url, ACTOR_USER)
    workspace = ebom_request(
        actor,
        base_url,
        ebom_path(project_id),
        query_key="replay-workspace",
    )
    require_stage_status(workspace, {200}, "P504_RUNTIME_REPLAY_CREATE")
    require(
        len(workspace.body.get("items", [])) == 1,
        "Controlled EBOM replay workspace drifted",
    )
    ebom_id = str(workspace.body["items"][0]["globalId"])
    detail = ebom_request(
        actor,
        base_url,
        ebom_path(project_id, ebom_id),
        query_key="replay-detail",
    )
    require_stage_status(detail, {200}, "P504_RUNTIME_REPLAY_RELEASE")
    revisions = detail.body.get("revisions", [])
    require(
        len(revisions) == 2
        and revisions[0].get("lifecycle", {}).get("state") == "released",
        "Controlled EBOM replay exact revision history drifted",
    )
    revision_two = revisions[0]
    create_replay = command(
        actor,
        base_url,
        actor_csrf,
        ebom_path(project_id),
        create_payload(policy_hash),
        CREATE_KEY,
        "P504_RUNTIME_REPLAY_CREATE",
    )
    assert_replayed(create_replay, "true")
    require(
        create_replay.body.get("ebom", {}).get("globalId") == ebom_id,
        "Controlled EBOM cross-process create replay identity drifted",
    )
    release_replay = command(
        actor,
        base_url,
        actor_csrf,
        (
            f"{ebom_path(project_id, ebom_id)}/revisions/"
            f"{revision_two['globalId']}:release"
        ),
        {
            **transition_payload(
                policy_hash,
                str(revision_two["snapshotHash"]),
                3,
            ),
            "confirmed": True,
            "confirmationIntent": "release_exact_ebom_revision",
        },
        RELEASE_KEY,
        "P504_RUNTIME_REPLAY_RELEASE",
    )
    assert_replayed(release_replay, "true")
    require(
        release_replay.body.get("revision", {}).get("globalId")
        == revision_two.get("globalId"),
        "Controlled EBOM cross-process release replay identity drifted",
    )


def verify_ebom_runtime_schema(fixture_run_id: str) -> dict[str, object]:
    import frappe

    document_runtime._validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "Controlled EBOM schema fixture namespace drifted",
    )
    required_fields = {
        "NPI EBOM Policy": {
            "global_id",
            "project_global_id",
            "policy_key_hash",
            "optimistic_version",
        },
        "NPI EBOM Policy Version": {
            "policy_global_id",
            "publication_state",
            "policy_snapshot",
            "snapshot_hash",
        },
        "NPI Engineering BOM": {
            "global_id",
            "project_global_id",
            "latest_revision_global_id",
            "optimistic_version",
        },
        "NPI Engineering BOM Revision": {
            "ebom_global_id",
            "revision_number",
            "revision_snapshot",
            "snapshot_hash",
        },
        "NPI Engineering BOM Line": {
            "revision_global_id",
            "line_identity_key",
            "line_snapshot",
            "line_hash",
        },
        "NPI EBOM Revision Lifecycle": {
            "revision_global_id",
            "current_state",
            "lifecycle_version",
        },
        "NPI EBOM Lifecycle Event": {
            "revision_global_id",
            "from_version",
            "to_version",
            "event_hash",
        },
        "NPI EBOM Command Idempotency": {
            "receipt_key",
            "actor_user_id",
            "payload_hash",
            "response_hash",
            "sealed",
        },
    }
    for doctype, expected in required_fields.items():
        meta = frappe.get_meta(doctype, cached=False)
        actual = {field.fieldname for field in meta.fields}
        require(
            expected <= actual,
            f"Controlled EBOM metadata is incomplete for {doctype}",
        )
    return {
        "doctypes": len(required_fields),
        "fixtureRunId": fixture_run_id,
        "metadataSynchronized": True,
    }


def run_bench_fixture(method: str, kwargs: dict[str, object]) -> dict[str, Any]:
    require(
        BENCH_PATH.is_dir()
        and not BENCH_PATH.is_symlink()
        and BENCH_PATH.resolve() == BENCH_PATH,
        "Controlled EBOM verifier requires the fixed physical Bench",
    )
    environment = os.environ.copy()
    for variable in (
        "NPI_RUNTIME_ADMINISTRATOR_PASSWORD",
        "NPI_RUNTIME_FIXTURE_PASSWORD",
        "NPI_ADMINISTRATOR_PASSWORD",
        "NPI_DATABASE_ROOT_PASSWORD",
    ):
        environment.pop(variable, None)
    current_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        str(ROOT)
        if not current_pythonpath
        else f"{ROOT}{os.pathsep}{current_pythonpath}"
    )
    completed = subprocess.run(
        [
            str(BENCH_PATH / "env" / "bin" / "python"),
            str(ROOT / "scripts" / "verify_ebom_runtime.py"),
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
        "Controlled EBOM Bench fixture failed",
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    require(bool(lines), "Controlled EBOM Bench fixture was silent")
    result = json.loads(lines[-1])
    require(isinstance(result, dict), "Controlled EBOM Bench fixture result is invalid")
    return result


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    require(
        method == "verify_ebom_runtime_schema",
        "Controlled EBOM Bench fixture is unavailable",
    )
    import frappe

    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    try:
        frappe.set_user("Administrator")
        result = verify_ebom_runtime_schema(**kwargs)
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    finally:
        frappe.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the real P5-04 controlled EBOM runtime.",
    )
    parser.add_argument("--base-url")
    parser.add_argument(
        "--bench-fixture",
        choices=("verify_ebom_runtime_schema",),
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
            "Controlled EBOM Bench fixture arguments are invalid",
        )
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "Controlled EBOM fixture kwargs are invalid")
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return

    require(
        isinstance(arguments.base_url, str)
        and arguments.fixture_kwargs is None
        and document_runtime.CALLER_SUPPLIED_FIXTURE_RUN_ID is not None,
        "The P5-04 runtime base URL and fixture namespace are required",
    )
    administrator_password = secret_from_environment(
        "NPI_RUNTIME_ADMINISTRATOR_PASSWORD"
    )
    fixture_password = secret_from_environment("NPI_RUNTIME_FIXTURE_PASSWORD")
    base_url = validate_local_fixture_inputs(
        arguments.base_url,
        "Administrator",
        ACTOR_USER,
    )
    validate_local_fixture_inputs(base_url, "Administrator", UNRELATED_USER)
    require(
        FIXTURE_RUN_ID != "0" * 32
        and ENGINEERING_BOM_KEY.startswith("synthetic_ebom_")
        and ACTOR_USER.endswith("@example.invalid")
        and UNRELATED_USER.endswith("@example.invalid"),
        "Controlled EBOM fixture identity drifted",
    )
    administrator = login(base_url, "Administrator", administrator_password)
    csrf_token = bootstrap_csrf(administrator, base_url, "Administrator")
    require(
        int(arguments.route_disable_probe is not None)
        + int(arguments.replay_only)
        <= 1,
        "Controlled EBOM runtime modes are mutually exclusive",
    )
    if arguments.route_disable_probe is not None:
        route_disable_probe(
            administrator,
            base_url,
            fixture_password,
            expected_mode=arguments.route_disable_probe,
        )
        print(json.dumps({"routeMode": arguments.route_disable_probe}, sort_keys=True))
        return
    if arguments.replay_only:
        run_replay(administrator, base_url, fixture_password)
        print(
            json.dumps(
                {"crossProcessReplay": True, "fixtureRunId": FIXTURE_RUN_ID},
                sort_keys=True,
            )
        )
        print("local Frappe EBOM runtime replay verification passed")
        return
    evidence = run_fresh(
        administrator,
        base_url,
        csrf_token,
        fixture_password,
    )
    print(json.dumps(evidence, sort_keys=True))
    print("local Frappe EBOM runtime verification passed")


if __name__ == "__main__":
    try:
        main()
    except RuntimeStageFailure as error:
        print(runtime_stage_diagnostic(error), file=sys.stderr)
        raise SystemExit(1) from None
