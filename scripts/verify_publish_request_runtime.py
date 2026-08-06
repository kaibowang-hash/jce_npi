from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import verify_ebom_runtime as ebom_runtime
from verify_frappe_runtime import (
    HttpResult,
    login,
    require,
    secret_from_environment,
    validate_local_fixture_inputs,
    validate_problem,
)
from verify_project_runtime import bootstrap_csrf, list_resources


ROOT = Path(__file__).resolve().parents[1]
BENCH_PATH = ROOT / "tmp" / "frappe-bench"
SITE_NAME = ebom_runtime.SITE_NAME
FIXTURE_RUN_ID = ebom_runtime.FIXTURE_RUN_ID
TENANT_ID = ebom_runtime.TENANT_ID
ACTOR_USER = ebom_runtime.ACTOR_USER
PUBLISH_POLICY_ID = str(
    uuid5(
        NAMESPACE_URL,
        (
            "https://npi-one.example.invalid/runtime/p5-05/"
            f"r1-{FIXTURE_RUN_ID}/publish-policy"
        ),
    )
)
PUBLISH_POLICY_VERSION_ID = str(
    uuid5(
        NAMESPACE_URL,
        (
            "https://npi-one.example.invalid/runtime/p5-05/"
            f"r1-{FIXTURE_RUN_ID}/publish-policy-version-1"
        ),
    )
)
PUBLISH_POLICY_VERSION = 1
PUBLISH_POLICY_VERSION_KEY = f"{PUBLISH_POLICY_ID}:1"
PUBLISH_POLICY_KEY = f"p5_05_runtime_{FIXTURE_RUN_ID}"
CREATE_KEY = f"p5-05-runtime-r1-{FIXTURE_RUN_ID}-create"
PREDECESSOR_ROUTE_QUERY = "p505-predecessor-" + "route-isolation"
POLICY_FIXTURE_DIAGNOSTICS_ENABLED = False

PUBLISH_DOCTYPES = (
    "NPI EBOM Publish Policy",
    "NPI EBOM Publish Policy Version",
    "NPI EBOM Publish Request",
    "NPI EBOM Publish Node",
    "NPI EBOM Publish Mapping Observation",
    "NPI EBOM Publish Node Result",
    "NPI EBOM Publish Command Idempotency",
)

_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_TRACE_PATTERN = re.compile(r"^trace-[a-f0-9]{32}$")
_TYPE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,127}$")
_FIXTURE_DIAGNOSTIC_PATTERN = re.compile(
    r"^\[fixture_diagnostic_code=(P505_RUNTIME_POLICY_[A-Z_]+); "
    r"exc_type=([A-Za-z][A-Za-z0-9_.]{0,127})\]$"
)
_RUNTIME_STAGE_CODES = frozenset(
    {
        "P505_RUNTIME_SCHEMA_FIXTURE",
        "P505_RUNTIME_POLICY_FIXTURE",
        "P505_RUNTIME_POLICY_CONTEXT",
        "P505_RUNTIME_POLICY_NAMESPACE",
        "P505_RUNTIME_POLICY_ROOT_INSERT",
        "P505_RUNTIME_POLICY_VERSION_INSERT",
        "P505_RUNTIME_POLICY_COMMIT",
        "P505_RUNTIME_POLICY_RESULT",
        "P505_RUNTIME_RELEASED_INPUT",
        "P505_RUNTIME_EMPTY_LIST",
        "P505_RUNTIME_GUEST_AUTHORIZATION",
        "P505_RUNTIME_CREATE",
        "P505_RUNTIME_REPLAY",
        "P505_RUNTIME_IDEMPOTENCY_CONFLICT",
        "P505_RUNTIME_LIST_DETAIL",
        "P505_RUNTIME_PERSISTENCE",
        "P505_RUNTIME_ROUTE_DISABLED",
        "P505_RUNTIME_ROUTE_RECOVERED",
        "P505_RUNTIME_PREDECESSOR_ROUTE_ISOLATION",
        "P505_RUNTIME_CROSS_PROCESS_REPLAY",
    }
)


class RuntimeStageFailure(RuntimeError):
    """Expose only one allowlisted stage, validated type, and exact trace."""

    def __init__(self, code: str, trace_id: str, *, exception_type: str) -> None:
        super().__init__("Controlled publish-request runtime stage failed")
        if code not in _RUNTIME_STAGE_CODES:
            raise ValueError("Publish-request runtime code is not allowlisted")
        if _TRACE_PATTERN.fullmatch(trace_id) is None:
            raise ValueError("Publish-request runtime trace identity is invalid")
        if _TYPE_PATTERN.fullmatch(exception_type) is None:
            raise ValueError("Publish-request runtime exception type is invalid")
        self.code = code
        self.trace_id = trace_id
        self.exception_type = exception_type


class FixtureStageFailure(RuntimeError):
    """Carry only an allowlisted fixture substage and exception class."""

    def __init__(self, code: str, *, exception_type: str) -> None:
        super().__init__("Controlled publish fixture substage failed")
        if code not in _RUNTIME_STAGE_CODES or not code.startswith(
            "P505_RUNTIME_POLICY_"
        ):
            raise ValueError("Publish-policy fixture code is not allowlisted")
        if _TYPE_PATTERN.fullmatch(exception_type) is None:
            raise ValueError("Publish-policy fixture exception type is invalid")
        self.code = code
        self.exception_type = exception_type


def runtime_stage_diagnostic(error: RuntimeStageFailure) -> str:
    return (
        f"[diagnostic_code={error.code}; "
        f"exc_type={error.exception_type}; "
        f"trace_id={error.trace_id}]"
    )


def fixture_stage_diagnostic(error: FixtureStageFailure) -> str:
    return (
        f"[fixture_diagnostic_code={error.code}; "
        f"exc_type={error.exception_type}]"
    )


def fixture_stage_failure(code: str, error: Exception) -> FixtureStageFailure:
    return FixtureStageFailure(code, exception_type=type(error).__name__)


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
        raise ValueError("Controlled publish response trace identity is invalid")
    raise RuntimeStageFailure(code, trace_id, exception_type=exception_type)


def publish_path(
    project_id: str,
    ebom_id: str,
    revision_id: str,
    request_id: str | None = None,
) -> str:
    base = (
        f"/api/npi/v1/projects/{project_id}/eboms/{ebom_id}/revisions/"
        f"{revision_id}/publish-requests"
    )
    return base if request_id is None else f"{base}/{request_id}"


def publish_request(
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
        ebom_runtime.document_runtime.command_headers(
            csrf_token,
            idempotency_key,
        )
        if idempotency_key is not None
        else ebom_runtime.document_runtime.query_headers(
            f"p505-{query_key}"
        )
    )
    result = ebom_runtime.document_runtime.request(
        opener,
        base_url,
        path,
        method=method,
        payload=payload,
        request_headers=headers,
    )
    require(
        result.headers.get("X-Request-ID") == headers["X-Request-ID"],
        "P5-05 request identity was not echoed",
    )
    require(
        result.headers.get("Cache-Control") == "private, no-store",
        "P5-05 private no-store response drifted",
    )
    return HttpResult(
        result.status,
        result.headers,
        result.body,
        request_id=headers["X-Request-ID"],
        trace_id=headers["X-Trace-ID"],
    )


def released_context(
    administrator,
    actor,
    base_url: str,
) -> dict[str, object]:
    project_id = ebom_runtime.fixture_project(administrator, base_url)
    workspace = ebom_runtime.ebom_request(
        actor,
        base_url,
        ebom_runtime.ebom_path(project_id),
        query_key="p505-input-list",
    )
    require_stage_status(
        workspace,
        {200},
        "P505_RUNTIME_RELEASED_INPUT",
    )
    items = workspace.body.get("items", [])
    require(
        isinstance(items, list) and len(items) == 1,
        "Controlled publish input EBOM cardinality drifted",
    )
    ebom_id = str(items[0].get("globalId"))
    detail = ebom_runtime.ebom_request(
        actor,
        base_url,
        ebom_runtime.ebom_path(project_id, ebom_id),
        query_key="p505-input-detail",
    )
    require_stage_status(detail, {200}, "P505_RUNTIME_RELEASED_INPUT")
    revisions = detail.body.get("revisions", [])
    require(
        isinstance(revisions, list)
        and len(revisions) == 2
        and revisions[0].get("lifecycle", {}).get("state") == "released"
        and revisions[0].get("lifecycle", {}).get("version") == 4,
        "Controlled publish input release truth drifted",
    )
    revision = revisions[0]
    return {
        "projectId": project_id,
        "ebomId": ebom_id,
        "ebomVersion": items[0].get("optimisticVersion"),
        "revisionId": revision.get("globalId"),
        "revisionHash": revision.get("snapshotHash"),
        "lifecycleVersion": revision.get("lifecycle", {}).get("version"),
    }


def create_payload(
    context: dict[str, object],
    policy_hash: str,
    *,
    reason: str = "Validate the exact synthetic released EBOM for Mock publishing.",
) -> dict[str, object]:
    return {
        "expectedEbomVersion": context["ebomVersion"],
        "expectedRevisionSnapshotHash": context["revisionHash"],
        "expectedLifecycleVersion": context["lifecycleVersion"],
        "publishPolicyGlobalId": PUBLISH_POLICY_ID,
        "publishPolicyVersion": PUBLISH_POLICY_VERSION,
        "publishPolicySnapshotHash": policy_hash,
        "targetMode": "mock",
        "confirmed": True,
        "confirmationIntent": (
            "validate_exact_released_ebom_for_item_mbom_publish"
        ),
        "reason": reason,
    }


def assert_publish_truth(
    value: dict[str, Any],
    context: dict[str, object],
    policy_hash: str,
) -> None:
    require(
        value.get("operation") == "publish_released_ebom_item_mbom"
        and value.get("apiVersion") == "npi.erp-publish.v1"
        and value.get("targetMode") == "mock"
        and value.get("state") == "validated"
        and value.get("dispatchAllowed") is False
        and value.get("actorUserId") == ACTOR_USER
        and value.get("policy")
        == {
            "globalId": PUBLISH_POLICY_ID,
            "version": PUBLISH_POLICY_VERSION,
            "snapshotHash": policy_hash,
        }
        and value.get("capabilities")
        == {
            "view": True,
            "create": True,
            "dispatch": False,
            "retry": False,
            "reconcile": False,
        },
        "Controlled publish request aggregate truth drifted",
    )
    evidence = value.get("releasedEbom", {})
    require(
        evidence.get("projectGlobalId") == context["projectId"]
        and evidence.get("ebomGlobalId") == context["ebomId"]
        and evidence.get("ebomVersion") == context["ebomVersion"]
        and evidence.get("revisionGlobalId") == context["revisionId"]
        and evidence.get("revisionSnapshotHash") == context["revisionHash"]
        and evidence.get("lifecycleVersion") == context["lifecycleVersion"],
        "Controlled publish request released evidence drifted",
    )
    nodes = value.get("nodes", [])
    require(
        isinstance(nodes, list) and len(nodes) == 2,
        "Controlled publish request node cardinality drifted",
    )
    for node in nodes:
        mapping = node.get("mapping", {})
        results = node.get("results", [])
        require(
            mapping
            == {
                "state": "unmapped",
                "version": 0,
                "formalItemCode": None,
                "formalMbomId": None,
                "targetVersion": None,
                "observedAt": None,
            }
            and node.get("operations")
            == ["create_item", "create_or_update_mbom"]
            and node.get("resultState") == "validated"
            and isinstance(results, list)
            and len(results) == 1
            and results[0].get("attemptNumber") == 0
            and results[0].get("state") == "validated"
            and results[0].get("faultKind") is None
            and results[0].get("futureRetryDirective") == "none"
            and results[0].get("futureRetryable") is False
            and results[0].get("reconciliationRequired") is False
            and results[0].get("retryAfterRequired") is False
            and results[0].get("phase5DispatchAllowed") is False
            and results[0].get("formalItemCode") is None
            and results[0].get("formalMbomId") is None
            and results[0].get("targetVersion") is None,
            "Controlled Mock node reported unsupported target truth",
        )


def provision_publish_policy(
    fixture_run_id: str,
    project_id: str,
    actor_user_id: str,
) -> dict[str, object]:
    import frappe

    from npi_integration.publish_request.domain import sha256_json
    from npi_integration.publish_request.frappe_validation import (
        publish_policy_write,
    )

    require(
        fixture_run_id == FIXTURE_RUN_ID
        and project_id == str(UUID(project_id))
        and actor_user_id == ACTOR_USER,
        "Controlled publish-policy fixture identity drifted",
    )
    try:
        project = frappe.db.get_value(
            "NPI Engineering Project",
            project_id,
            ["global_id", "tenant_id"],
            as_dict=True,
        )
        actor = frappe.db.get_value(
            "User",
            actor_user_id,
            ["name", "enabled", "user_type"],
            as_dict=True,
        )
        require(
            project is not None
            and str(project.get("global_id")) == project_id
            and str(project.get("tenant_id")) == TENANT_ID
            and actor is not None
            and str(actor.get("name")) == actor_user_id
            and int(actor.get("enabled") or 0) == 1
            and str(actor.get("user_type")) == "System User",
            "Controlled publish-policy fixture parent or actor is unavailable",
        )
    except Exception as error:
        raise fixture_stage_failure(
            "P505_RUNTIME_POLICY_CONTEXT", error
        ) from error
    try:
        require(
            not frappe.db.exists("NPI EBOM Publish Policy", PUBLISH_POLICY_ID)
            and not frappe.db.exists(
                "NPI EBOM Publish Policy Version",
                PUBLISH_POLICY_VERSION_ID,
            ),
            "Controlled publish-policy namespace is not fresh",
        )
    except Exception as error:
        raise fixture_stage_failure(
            "P505_RUNTIME_POLICY_NAMESPACE", error
        ) from error
    title = "Synthetic controlled Mock publish policy"
    snapshot = {
        "schemaVersion": 1,
        "globalId": PUBLISH_POLICY_VERSION_ID,
        "policyGlobalId": PUBLISH_POLICY_ID,
        "tenantId": TENANT_ID,
        "projectGlobalId": project_id,
        "policyKey": PUBLISH_POLICY_KEY,
        "policyVersion": PUBLISH_POLICY_VERSION,
        "title": title,
        "publicationState": "published",
        "targetMode": "mock",
        "apiVersion": "npi.erp-publish.v1",
        "operation": "publish_released_ebom_item_mbom",
        "requesterUserIds": [actor_user_id],
    }
    snapshot_hash = sha256_json(snapshot)
    policy_key_hash = hashlib.sha256(
        f"{TENANT_ID}:{project_id}:{PUBLISH_POLICY_KEY}".encode()
    ).hexdigest()
    with publish_policy_write():
        try:
            root = frappe.get_doc(
                {
                    "doctype": "NPI EBOM Publish Policy",
                    "global_id": PUBLISH_POLICY_ID,
                    "tenant_id": TENANT_ID,
                    "project_global_id": project_id,
                    "policy_key": PUBLISH_POLICY_KEY,
                    "policy_key_hash": policy_key_hash,
                    "title": title,
                    "enabled": 1,
                    "optimistic_version": 1,
                }
            ).insert()
        except Exception as error:
            raise fixture_stage_failure(
                "P505_RUNTIME_POLICY_ROOT_INSERT", error
            ) from error
        try:
            version = frappe.get_doc(
                {
                    "doctype": "NPI EBOM Publish Policy Version",
                    "global_id": PUBLISH_POLICY_VERSION_ID,
                    "publish_policy": PUBLISH_POLICY_ID,
                    "tenant_id": TENANT_ID,
                    "project_global_id": project_id,
                    "policy_global_id": PUBLISH_POLICY_ID,
                    "policy_key": PUBLISH_POLICY_KEY,
                    "policy_version": PUBLISH_POLICY_VERSION,
                    "version_key": PUBLISH_POLICY_VERSION_KEY,
                    "title": title,
                    "publication_state": "published",
                    "target_mode": "mock",
                    "api_version": "npi.erp-publish.v1",
                    "operation": "publish_released_ebom_item_mbom",
                    "requester_user_ids": [actor_user_id],
                    "policy_snapshot": snapshot,
                    "snapshot_hash": snapshot_hash,
                    "published_at": datetime.now(UTC),
                    "optimistic_version": 1,
                }
            ).insert()
        except Exception as error:
            raise fixture_stage_failure(
                "P505_RUNTIME_POLICY_VERSION_INSERT", error
            ) from error
    try:
        require(
            root.name == PUBLISH_POLICY_ID
            and version.name == PUBLISH_POLICY_VERSION_ID
            and str(version.snapshot_hash) == snapshot_hash,
            "Controlled publish-policy persistence drifted",
        )
    except Exception as error:
        raise fixture_stage_failure(
            "P505_RUNTIME_POLICY_RESULT", error
        ) from error
    try:
        frappe.db.commit()
    except Exception as error:
        raise fixture_stage_failure(
            "P505_RUNTIME_POLICY_COMMIT", error
        ) from error
    return {
        "fixtureRunId": fixture_run_id,
        "policyGlobalId": root.name,
        "policyVersionGlobalId": version.name,
        "publicationState": version.publication_state,
        "snapshotHash": snapshot_hash,
    }


def verify_publish_runtime_schema(fixture_run_id: str) -> dict[str, object]:
    import frappe

    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "Controlled publish schema fixture namespace drifted",
    )
    for doctype in PUBLISH_DOCTYPES:
        meta = frappe.get_meta(doctype, cached=False)
        require(
            meta.name == doctype
            and meta.module == "NPI Integration"
            and meta.istable == 0,
            f"Controlled publish metadata is unavailable for {doctype}",
        )
    return {
        "fixtureRunId": fixture_run_id,
        "metadataSynchronized": True,
        "publishDoctypes": len(PUBLISH_DOCTYPES),
    }


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    fixtures = {
        "provision_publish_policy": provision_publish_policy,
        "verify_publish_runtime_schema": verify_publish_runtime_schema,
    }
    require(method in fixtures, "Controlled publish Bench fixture is unavailable")
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


def run_bench_fixture(method: str, kwargs: dict[str, object]) -> dict[str, Any]:
    stage_codes = {
        "provision_publish_policy": "P505_RUNTIME_POLICY_FIXTURE",
        "verify_publish_runtime_schema": "P505_RUNTIME_SCHEMA_FIXTURE",
    }
    require(method in stage_codes, "Controlled publish Bench fixture is unavailable")
    stage_code = stage_codes[method]
    trace_id = ebom_runtime.document_runtime.fixture_trace_id(stage_code)
    require(
        BENCH_PATH.is_dir()
        and not BENCH_PATH.is_symlink()
        and BENCH_PATH.resolve() == BENCH_PATH,
        "Controlled publish verifier requires the fixed physical Bench",
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
            str(ROOT / "scripts" / "verify_publish_request_runtime.py"),
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
    if completed.returncode != 0:
        for line in completed.stderr.splitlines():
            match = _FIXTURE_DIAGNOSTIC_PATTERN.fullmatch(line.strip())
            if match is not None and match.group(1) in _RUNTIME_STAGE_CODES:
                raise RuntimeStageFailure(
                    match.group(1),
                    trace_id,
                    exception_type=match.group(2),
                )
        raise RuntimeStageFailure(
            stage_code,
            trace_id,
            exception_type="BenchFixtureError",
        )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    try:
        result = json.loads(lines[-1]) if lines else None
    except json.JSONDecodeError:
        result = None
    if not isinstance(result, dict):
        raise RuntimeStageFailure(
            stage_code,
            trace_id,
            exception_type="ResponseShapeError",
        )
    return result


def ensure_policy(project_id: str) -> str:
    result = run_bench_fixture(
        "provision_publish_policy",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "actor_user_id": ACTOR_USER,
        },
    )
    snapshot_hash = result.get("snapshotHash")
    require(
        result.get("fixtureRunId") == FIXTURE_RUN_ID
        and result.get("policyGlobalId") == PUBLISH_POLICY_ID
        and result.get("policyVersionGlobalId") == PUBLISH_POLICY_VERSION_ID
        and result.get("publicationState") == "published"
        and isinstance(snapshot_hash, str)
        and _HASH_PATTERN.fullmatch(snapshot_hash) is not None,
        "Controlled publish-policy fixture response drifted",
    )
    return snapshot_hash


def run_fresh(
    administrator,
    base_url: str,
    fixture_password: str,
) -> dict[str, object]:
    schema = run_bench_fixture(
        "verify_publish_runtime_schema",
        {"fixture_run_id": FIXTURE_RUN_ID},
    )
    actor = login(base_url, ACTOR_USER, fixture_password)
    actor_csrf = bootstrap_csrf(actor, base_url, ACTOR_USER)
    context = released_context(administrator, actor, base_url)
    policy_hash = ensure_policy(str(context["projectId"]))
    path = publish_path(
        str(context["projectId"]),
        str(context["ebomId"]),
        str(context["revisionId"]),
    )
    guest = publish_request(
        urllib.request.build_opener(),
        base_url,
        path,
        query_key="guest",
    )
    if guest.status != 401:
        require_stage_status(guest, {401}, "P505_RUNTIME_GUEST_AUTHORIZATION")
    validate_problem(guest, 401, "AUTHENTICATION_REQUIRED")

    empty = publish_request(actor, base_url, path, query_key="empty")
    require_stage_status(empty, {200}, "P505_RUNTIME_EMPTY_LIST")
    require(
        empty.body.get("items") == []
        and empty.body.get("permissions") == {"view": True, "create": True}
        and empty.body.get("revision", {}).get("globalId")
        == context["revisionId"]
        and len(empty.body.get("policies", [])) == 1
        and empty.body["policies"][0].get("snapshotHash") == policy_hash,
        "Controlled publish empty list or policy truth drifted",
    )
    payload = create_payload(context, policy_hash)
    created = publish_request(
        actor,
        base_url,
        path,
        method="POST",
        payload=payload,
        csrf_token=actor_csrf,
        idempotency_key=CREATE_KEY,
    )
    require_stage_status(created, {201}, "P505_RUNTIME_CREATE")
    require(
        created.headers.get("Idempotency-Replayed") == "false",
        "Controlled publish create replay header drifted",
    )
    assert_publish_truth(created.body, context, policy_hash)
    request_id = str(created.body.get("globalId"))
    require(request_id == str(UUID(request_id)), "Publish request identity drifted")

    replay = publish_request(
        actor,
        base_url,
        path,
        method="POST",
        payload=payload,
        csrf_token=actor_csrf,
        idempotency_key=CREATE_KEY,
    )
    require_stage_status(replay, {201}, "P505_RUNTIME_REPLAY")
    require(
        replay.headers.get("Idempotency-Replayed") == "true"
        and replay.body == created.body,
        "Controlled publish exact replay drifted",
    )
    conflict = publish_request(
        actor,
        base_url,
        path,
        method="POST",
        payload=create_payload(
            context,
            policy_hash,
            reason="Changed synthetic reason must fail the sealed replay.",
        ),
        csrf_token=actor_csrf,
        idempotency_key=CREATE_KEY,
    )
    if conflict.status != 409:
        require_stage_status(
            conflict,
            {409},
            "P505_RUNTIME_IDEMPOTENCY_CONFLICT",
        )
    validate_problem(conflict, 409, "EBOM_PUBLISH_IDEMPOTENCY_CONFLICT")

    listed = publish_request(actor, base_url, path, query_key="final-list")
    detail = publish_request(
        actor,
        base_url,
        publish_path(
            str(context["projectId"]),
            str(context["ebomId"]),
            str(context["revisionId"]),
            request_id,
        ),
        query_key="detail",
    )
    require_stage_status(listed, {200}, "P505_RUNTIME_LIST_DETAIL")
    require_stage_status(detail, {200}, "P505_RUNTIME_LIST_DETAIL")
    require(
        listed.body.get("items") == [created.body]
        and detail.body == created.body,
        "Controlled publish list/detail immutable truth drifted",
    )

    expected_counts = {
        "NPI EBOM Publish Policy": 1,
        "NPI EBOM Publish Policy Version": 1,
        "NPI EBOM Publish Request": 1,
        "NPI EBOM Publish Node": 2,
        "NPI EBOM Publish Mapping Observation": 2,
        "NPI EBOM Publish Node Result": 2,
        "NPI EBOM Publish Command Idempotency": 1,
    }
    for doctype, expected in expected_counts.items():
        require(
            len(
                ebom_runtime.count_rows(
                    administrator,
                    base_url,
                    doctype,
                    str(context["projectId"]),
                )
            )
            == expected,
            f"Controlled publish persisted {doctype} cardinality drifted",
        )
    audits = list_resources(
        administrator,
        base_url,
        "NPI Audit Event",
        filters=[
            ["operation", "=", "ebom.publish_request.create"],
            [
                "trace_id",
                "=",
                ebom_runtime.document_runtime.fixture_trace_id(CREATE_KEY),
            ],
        ],
        fields=["operation", "result", "trace_id"],
    )
    outbox = list_resources(
        administrator,
        base_url,
        "NPI Outbox Message",
        filters=[["global_id", "=", request_id]],
        fields=["name"],
    )
    require(
        len(audits) == 1
        and audits[0].get("result") == "validated"
        and outbox == [],
        "Controlled publish audit or no-Outbox truth drifted",
    )
    return {
        "fixtureRunId": FIXTURE_RUN_ID,
        "metadataSynchronized": schema.get("metadataSynchronized"),
        "publishRequestId": request_id,
        "mockNodes": 2,
        "dispatchAllowed": False,
        "formalTargetIdentifiers": 0,
        "outboxMessages": 0,
        "crossProcessReplayReady": True,
    }


def route_disable_probe(
    administrator,
    base_url: str,
    fixture_password: str,
    *,
    expected_mode: str,
) -> None:
    actor = login(base_url, ACTOR_USER, fixture_password)
    context = released_context(administrator, actor, base_url)
    path = publish_path(
        str(context["projectId"]),
        str(context["ebomId"]),
        str(context["revisionId"]),
    )
    result = publish_request(
        actor,
        base_url,
        path,
        query_key=f"route-{expected_mode}",
    )
    if expected_mode == "disabled":
        if result.status != 503:
            require_stage_status(result, {503}, "P505_RUNTIME_ROUTE_DISABLED")
        validate_problem(result, 503, "EBOM_PUBLISH_REQUEST_ROUTES_DISABLED")
        predecessor = ebom_runtime.ebom_request(
            actor,
            base_url,
            ebom_runtime.ebom_path(
                str(context["projectId"]),
                str(context["ebomId"]),
            ),
            query_key=PREDECESSOR_ROUTE_QUERY,
        )
        require_stage_status(
            predecessor,
            {200},
            "P505_RUNTIME_PREDECESSOR_ROUTE_ISOLATION",
        )
        require(
            predecessor.body.get("revisions", [])[0].get("lifecycle", {}).get(
                "state"
            )
            == "released",
            "P5-05 route switch changed retained EBOM truth",
        )
        return
    require_stage_status(result, {200}, "P505_RUNTIME_ROUTE_RECOVERED")
    require(
        len(result.body.get("items", [])) == 1,
        "Recovered controlled publish route truth drifted",
    )


def run_replay(administrator, base_url: str, fixture_password: str) -> None:
    actor = login(base_url, ACTOR_USER, fixture_password)
    actor_csrf = bootstrap_csrf(actor, base_url, ACTOR_USER)
    context = released_context(administrator, actor, base_url)
    path = publish_path(
        str(context["projectId"]),
        str(context["ebomId"]),
        str(context["revisionId"]),
    )
    listed = publish_request(actor, base_url, path, query_key="replay-list")
    require_stage_status(listed, {200}, "P505_RUNTIME_CROSS_PROCESS_REPLAY")
    policies = listed.body.get("policies", [])
    items = listed.body.get("items", [])
    require(
        len(policies) == 1 and len(items) == 1,
        "Controlled publish replay prerequisites drifted",
    )
    policy_hash = str(policies[0].get("snapshotHash"))
    replay = publish_request(
        actor,
        base_url,
        path,
        method="POST",
        payload=create_payload(context, policy_hash),
        csrf_token=actor_csrf,
        idempotency_key=CREATE_KEY,
    )
    require_stage_status(replay, {201}, "P505_RUNTIME_CROSS_PROCESS_REPLAY")
    require(
        replay.headers.get("Idempotency-Replayed") == "true"
        and replay.body == items[0],
        "Controlled publish cross-process replay drifted",
    )
    assert_publish_truth(replay.body, context, policy_hash)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the real P5-05 controlled publish-request runtime.",
    )
    parser.add_argument("--base-url")
    parser.add_argument(
        "--bench-fixture",
        choices=(
            "provision_publish_policy",
            "verify_publish_runtime_schema",
        ),
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
            "Controlled publish Bench fixture arguments are invalid",
        )
        kwargs = json.loads(arguments.fixture_kwargs)
        require(
            isinstance(kwargs, dict),
            "Controlled publish fixture kwargs are invalid",
        )
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return

    require(
        isinstance(arguments.base_url, str)
        and arguments.fixture_kwargs is None
        and ebom_runtime.document_runtime.CALLER_SUPPLIED_FIXTURE_RUN_ID
        is not None,
        "The P5-05 runtime base URL and fixture namespace are required",
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
    require(
        FIXTURE_RUN_ID != "0" * 32
        and ACTOR_USER.endswith("@example.invalid")
        and PUBLISH_POLICY_KEY.startswith("p5_05_runtime_"),
        "Controlled publish fixture identity drifted",
    )
    administrator = login(base_url, "Administrator", administrator_password)
    require(
        int(arguments.route_disable_probe is not None)
        + int(arguments.replay_only)
        <= 1,
        "Controlled publish runtime modes are mutually exclusive",
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
        print("local Frappe publish-request runtime replay verification passed")
        return
    evidence = run_fresh(administrator, base_url, fixture_password)
    print(json.dumps(evidence, sort_keys=True))
    print("local Frappe publish-request runtime verification passed")


if __name__ == "__main__":
    try:
        main()
    except FixtureStageFailure as error:
        if POLICY_FIXTURE_DIAGNOSTICS_ENABLED:
            print(fixture_stage_diagnostic(error), file=sys.stderr)
        raise SystemExit(1) from None
    except RuntimeStageFailure as error:
        print(runtime_stage_diagnostic(error), file=sys.stderr)
        raise SystemExit(1) from None
