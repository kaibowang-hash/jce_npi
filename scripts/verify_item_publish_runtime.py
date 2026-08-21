from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID, uuid5

import verify_document_runtime as document_runtime
import verify_ebom_runtime as ebom_runtime
import verify_publish_request_runtime as publish_runtime
from verify_frappe_runtime import (
    login,
    require,
    secret_from_environment,
    validate_local_fixture_inputs,
    validate_problem,
)
from verify_project_runtime import bootstrap_csrf


ROOT = Path(__file__).resolve().parents[1]
BENCH_PATH = ROOT / "tmp" / "frappe-bench"
SITE_NAME = document_runtime.SITE_NAME
FIXTURE_RUN_ID = document_runtime.FIXTURE_RUN_ID
TENANT_ID = document_runtime.TENANT_ID
ACTOR_USER = publish_runtime.ACTOR_USER
ACKNOWLEDGEMENT = (
    "I confirm this request uses the exact released Item source and current "
    "execution profile."
)
RUNTIME_MARKER = "npi-one-item-publish-disposable-v1"
ITEM_CREATE_DIAGNOSTICS_ENABLED = True
_CREATE_DIAGNOSTIC_HEADER = "X-NPI-Diagnostic-Scope"
_CREATE_DIAGNOSTIC_SCOPE = "p803-item-create-v1"
_PROBLEM_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{0,79}$")
_CREATE_SERVER_DIAGNOSTIC_CODES = frozenset(
    {
        "P803_CREATE_COMMAND_CONTEXT",
        "P803_CREATE_INPUT_PARSE",
        "P803_CREATE_PROJECT_LOCK",
        "P803_CREATE_IDEMPOTENCY_CONTEXT",
        "P803_CREATE_PROJECT_MUTABILITY",
        "P803_CREATE_SOURCE_RESOLVE",
        "P803_CREATE_MAPPING_READ",
        "P803_CREATE_PROFILE_RESOLVE",
        "P803_CREATE_DOMAIN_BUILD",
        "P803_CREATE_RESPONSE_BUILD",
        "P803_CREATE_TRANSACTION_SCOPE",
        "P803_CREATE_STREAM_GUARD",
        "P803_CREATE_LOCK_REVALIDATE",
        "P803_CREATE_REQUEST_INSERT",
        "P803_CREATE_OUTBOX_INSERT",
        "P803_CREATE_GUARD_ACTIVATE",
        "P803_CREATE_AUDIT_APPEND",
        "P803_CREATE_IDEMPOTENCY_INSERT",
        "P803_CREATE_REPOSITORY_COMMAND",
        "P803_CREATE_COMMIT",
        "P803_CREATE_ENQUEUE",
        "P803_CREATE_API_RESPONSE",
    }
)

LEGACY_OUTBOX_PAYLOAD_KEYS = frozenset(
    {
        "schema_version",
        "api_version",
        "operation",
        "request_global_id",
        "request_payload_hash",
        "project_global_id",
        "source_stream_key_hash",
        "source_hash",
        "intent",
        "expected_mapping_version",
        "expected_target_version",
        "target_mode",
        "profile_id",
        "profile_version",
        "profile_snapshot_hash",
        "idempotency_key_hash",
    }
)
CURRENT_OUTBOX_PAYLOAD_KEYS = LEGACY_OUTBOX_PAYLOAD_KEYS | frozenset(
    {
        "target_idempotency_key_hash",
        "semantic_source_effect_hash",
        "semantic_effect_hash",
    }
)


def item_publish_path(project_id: str, request_id: str | None = None) -> str:
    base = f"/api/npi/v1/projects/{project_id}/item-publish-requests"
    return base if request_id is None else f"{base}/{request_id}"


def item_publish_request(
    opener,
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    csrf_token: str | None = None,
    idempotency_key: str | None = None,
    query_key: str = "query",
    create_diagnostic: bool = False,
):
    headers = (
        document_runtime.command_headers(csrf_token, idempotency_key)
        if idempotency_key is not None
        else document_runtime.query_headers(f"p803-{query_key}")
    )
    if create_diagnostic:
        require(
            method == "POST" and idempotency_key is not None,
            "The P8-03 Item create diagnostic requires one command request",
        )
        headers[_CREATE_DIAGNOSTIC_HEADER] = _CREATE_DIAGNOSTIC_SCOPE
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
        "P8-03 Item request identity was not echoed",
    )
    require(
        result.headers.get("Cache-Control") == "private, no-store",
        "P8-03 Item response cache control drifted",
    )
    return result


def sanitized_problem_code(result) -> str | None:
    """Return only a contract-shaped problem code from a failed response."""

    code = result.body.get("code") if isinstance(result.body, dict) else None
    if isinstance(code, str) and _PROBLEM_CODE_PATTERN.fullmatch(code):
        return code
    return None


def released_item_context(administrator, actor, base_url: str) -> dict[str, object]:
    context = publish_runtime.released_context(administrator, actor, base_url)
    path = publish_runtime.publish_path(
        str(context["projectId"]),
        str(context["ebomId"]),
        str(context["revisionId"]),
    )
    request_label = "p803-retained-publish"
    retained = publish_runtime.publish_request(
        actor,
        base_url,
        path,
        query_key=request_label,
    )
    require(retained.status == 200, "P8-03 released publish input is unavailable")
    items = retained.body.get("items")
    require(
        isinstance(items, list) and len(items) == 1,
        "P8-03 released publish request cardinality drifted",
    )
    request = items[0]
    nodes = request.get("nodes") if isinstance(request, dict) else None
    require(
        isinstance(nodes, list)
        and len(nodes) == 2
        and all(isinstance(node, dict) for node in nodes),
        "P8-03 released Item node cardinality drifted",
    )
    publish_request_id = request.get("globalId")
    node_ids = tuple(node.get("globalId") for node in nodes)
    require(
        isinstance(publish_request_id, str)
        and str(UUID(publish_request_id)) == publish_request_id
        and len(set(node_ids)) == 2
        and all(
            isinstance(node_id, str) and str(UUID(node_id)) == node_id
            for node_id in node_ids
        ),
        "P8-03 released Item identities drifted",
    )
    return {
        "projectGlobalId": str(context["projectId"]),
        "publishRequestGlobalId": publish_request_id,
        "selectedPublishNodeGlobalIds": list(node_ids),
    }


def create_payload(context: Mapping[str, object], node_id: str) -> dict[str, object]:
    return {
        "publishRequestGlobalId": context["publishRequestGlobalId"],
        "selectedPublishNodeGlobalId": node_id,
        "expectedMappingVersion": 0,
        "acknowledgement": ACKNOWLEDGEMENT,
    }


def assert_profile(value: object, *, available: bool) -> None:
    require(isinstance(value, dict), "P8-03 Item collection is invalid")
    permissions = value.get("permissions")
    if not available:
        require(
            value.get("executionProfile") is None
            and permissions == {"canView": True, "canExecute": False},
            "P8-03 default-disabled profile drifted",
        )
        return
    profile = value.get("executionProfile")
    require(
        isinstance(profile, dict)
        and profile.get("profileId") == "item-synthetic-disposable-v1"
        and profile.get("profileVersion") == 1
        and profile.get("targetMode") == "synthetic"
        and profile.get("environmentCode") == "disposable-test"
        and permissions == {"canView": True, "canExecute": True},
        "P8-03 disposable Synthetic profile drifted",
    )


def _assert_no_formal_target(value: object) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key in {"formalItemCode", "targetVersion"}:
                require(nested is None, "P8-03 Synthetic proof claimed formal target truth")
            _assert_no_formal_target(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_no_formal_target(nested)


def _assert_no_private_execution_metadata(value: object) -> None:
    """Keep frozen worker/effect routing out of the public HTTP projection."""

    forbidden = {
        "serviceActorUserId",
        "semanticSourceEffectHash",
        "semanticEffectHash",
    }
    if isinstance(value, Mapping):
        for key, nested in value.items():
            require(
                key not in forbidden,
                "P8-03 public Item projection leaked private execution metadata",
            )
            _assert_no_private_execution_metadata(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_no_private_execution_metadata(nested)


def run_disabled_probe(base_url: str, fixture_password: str) -> dict[str, object]:
    administrator = login(
        base_url,
        "Administrator",
        secret_from_environment("NPI_RUNTIME_ADMINISTRATOR_PASSWORD"),
    )
    actor = login(base_url, ACTOR_USER, fixture_password)
    actor_csrf = bootstrap_csrf(actor, base_url, ACTOR_USER)
    context = released_item_context(administrator, actor, base_url)
    project_id = str(context["projectGlobalId"])
    path = item_publish_path(project_id)
    listed = item_publish_request(actor, base_url, path, query_key="disabled-list")
    require(
        listed.status == 200 and listed.body.get("items") == [],
        "P8-03 default-disabled collection drifted",
    )
    assert_profile(listed.body, available=False)
    nodes = context["selectedPublishNodeGlobalIds"]
    assert isinstance(nodes, list)
    rejected = item_publish_request(
        actor,
        base_url,
        path,
        method="POST",
        payload=create_payload(context, str(nodes[0])),
        csrf_token=actor_csrf,
        idempotency_key=f"p8-03-disabled-{FIXTURE_RUN_ID}",
    )
    validate_problem(rejected, 503, "ITEM_EXECUTION_PROFILE_UNAVAILABLE")
    for doctype in ("NPI Item Publish Request", "NPI Outbox Message"):
        require(
            ebom_runtime.count_rows(
                administrator,
                base_url,
                doctype,
                project_id,
            )
            == [],
            "P8-03 disabled command persisted executable work",
        )
    return {"defaultDisabled": True, "projectGlobalId": project_id}


def _assert_created(value: object, *, project_id: str) -> tuple[str, str]:
    require(isinstance(value, dict), "P8-03 Item command response is invalid")
    request = value.get("request")
    require(
        value.get("currentMapping") is None
        and isinstance(request, dict)
        and request.get("state") == "queued"
        and request.get("dispatchAllowed") is True
        and request.get("source", {}).get("projectGlobalId") == project_id
        and request.get("profile", {}).get("targetMode") == "synthetic",
        "P8-03 queued Item command truth drifted",
    )
    request_id = request.get("globalId")
    outbox_id = request.get("outboxEventId")
    require(
        isinstance(request_id, str)
        and str(UUID(request_id)) == request_id
        and isinstance(outbox_id, str)
        and str(UUID(outbox_id)) == outbox_id,
        "P8-03 queued Item identities drifted",
    )
    _assert_no_formal_target(value)
    _assert_no_private_execution_metadata(value)
    return request_id, outbox_id


def run_fresh(base_url: str, fixture_password: str) -> dict[str, object]:
    administrator = login(
        base_url,
        "Administrator",
        secret_from_environment("NPI_RUNTIME_ADMINISTRATOR_PASSWORD"),
    )
    actor = login(base_url, ACTOR_USER, fixture_password)
    actor_csrf = bootstrap_csrf(actor, base_url, ACTOR_USER)
    context = released_item_context(administrator, actor, base_url)
    project_id = str(context["projectGlobalId"])
    require(
        os.environ.get("NPI_P8_03_RUNTIME_PROJECT_ID") == project_id
        and os.environ.get("NPI_P8_03_RUNTIME_REQUESTER") == ACTOR_USER
        and isinstance(os.environ.get("NPI_P8_03_RUNTIME_WORKER"), str)
        and os.environ.get("NPI_P8_03_RUNTIME_WORKER") not in {None, ACTOR_USER},
        "P8-03 runtime profile environment is not bound to distinct retained actors",
    )
    path = item_publish_path(project_id)
    empty = item_publish_request(actor, base_url, path, query_key="enabled-empty")
    require(
        empty.status == 200 and empty.body.get("items") == [],
        "P8-03 enabled collection is not fresh",
    )
    assert_profile(empty.body, available=True)
    nodes = context["selectedPublishNodeGlobalIds"]
    assert isinstance(nodes, list)
    identities: list[tuple[str, str]] = []
    for label, node_id in zip(("synthetic", "uncertain"), nodes, strict=True):
        created = item_publish_request(
            actor,
            base_url,
            path,
            method="POST",
            payload=create_payload(context, str(node_id)),
            csrf_token=actor_csrf,
            idempotency_key=f"p8-03-{label}-{FIXTURE_RUN_ID}",
            create_diagnostic=(
                ITEM_CREATE_DIAGNOSTICS_ENABLED and label == "synthetic"
            ),
        )
        if created.status != 201 and ITEM_CREATE_DIAGNOSTICS_ENABLED:
            diagnostic = ebom_runtime._sanitized_server_diagnostic(
                created.trace_id,
                _CREATE_SERVER_DIAGNOSTIC_CODES,
            )
            if diagnostic is not None:
                exception_type, code, trace_id = diagnostic
                raise RuntimeError(
                    "P8-03 Item command create failed"
                    f" [diagnostic_code={code}; "
                    f"exception_type={exception_type}; trace_id={trace_id}]"
                )
            problem_code = sanitized_problem_code(created)
            if problem_code is not None:
                raise RuntimeError(
                    "P8-03 Item command create returned a governed problem"
                    f" [http_status={created.status}; problem_code={problem_code}; "
                    f"trace_id={created.trace_id}]"
                )
        require(
            created.status == 201
            and created.headers.get("Idempotency-Replayed") == "false",
            "P8-03 Item command did not create one queued request",
        )
        identities.append(_assert_created(created.body, project_id=project_id))

        if label == "synthetic":
            # A second semantic request on the same source stream is rejected
            # while the first request is queued.  This is the runtime proof
            # that the guard serializes the effect rather than the caller's
            # selected occurrence or HTTP idempotency key.
            active_conflict = item_publish_request(
                actor,
                base_url,
                path,
                method="POST",
                payload=create_payload(context, str(node_id)),
                csrf_token=actor_csrf,
                idempotency_key=f"p8-03-same-stream-active-{FIXTURE_RUN_ID}",
            )
            validate_problem(
                active_conflict,
                409,
                "ITEM_PUBLISH_STREAM_ACTIVE",
            )

    exercised = run_bench_fixture(
        "exercise_worker",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "synthetic_request_id": identities[0][0],
            "synthetic_outbox_id": identities[0][1],
            "uncertain_request_id": identities[1][0],
            "uncertain_outbox_id": identities[1][1],
        },
    )
    require(
        exercised.get("syntheticVerified") is True
        and exercised.get("uncertainAfterBoundary") is True
        and exercised.get("liveClaimRejected") is True
        and exercised.get("expiredPreBoundaryRecovered") is True
        and exercised.get("adapterCalls") == 1
        and exercised.get("adapterSessionWorkerOnly") is True
        and exercised.get("callerRestoredAfterSynthetic") is True
        and exercised.get("callerRestoredAfterUncertain") is True
        and exercised.get("attemptCount") == 4
        and exercised.get("resultCount") == 2
        and exercised.get("mappingCount") == 0,
        "P8-03 worker durability proof drifted",
    )
    retained_conflict = item_publish_request(
        actor,
        base_url,
        path,
        method="POST",
        payload=create_payload(context, str(nodes[0])),
        csrf_token=actor_csrf,
        idempotency_key=f"p8-03-same-stream-retained-{FIXTURE_RUN_ID}",
    )
    validate_problem(
        retained_conflict,
        409,
        "ITEM_PUBLISH_EFFECT_RETAINED",
    )
    listed = item_publish_request(actor, base_url, path, query_key="terminal-list")
    require(listed.status == 200, "P8-03 terminal Item collection is unavailable")
    assert_profile(listed.body, available=True)
    items = listed.body.get("items")
    require(
        isinstance(items, list)
        and len(items) == 2
        and {item.get("state") for item in items if isinstance(item, dict)}
        == {"synthetic_verified", "uncertain_after_timeout"},
        "P8-03 terminal Item states drifted",
    )
    _assert_no_formal_target(listed.body)
    _assert_no_private_execution_metadata(listed.body)
    return {
        "crossProcessReplayReady": True,
        "actorScopeTrace": {
            "adapterSessionWorkerOnly": exercised["adapterSessionWorkerOnly"],
            "callerRestoredAfterSynthetic": exercised[
                "callerRestoredAfterSynthetic"
            ],
            "callerRestoredAfterUncertain": exercised[
                "callerRestoredAfterUncertain"
            ],
            "ownerAndAuditBindingsVerified": True,
        },
        "digest": exercised["digest"],
        "mappingCount": 0,
        "projectGlobalId": project_id,
        "resultCount": 2,
        "sameStreamActiveConflict": True,
        "sameStreamRetainedEffectConflict": True,
    }


def run_replay(base_url: str, fixture_password: str) -> dict[str, object]:
    administrator = login(
        base_url,
        "Administrator",
        secret_from_environment("NPI_RUNTIME_ADMINISTRATOR_PASSWORD"),
    )
    actor = login(base_url, ACTOR_USER, fixture_password)
    context = released_item_context(administrator, actor, base_url)
    project_id = str(context["projectGlobalId"])
    listed = item_publish_request(
        actor,
        base_url,
        item_publish_path(project_id),
        query_key="cross-process-list",
    )
    items = listed.body.get("items")
    require(
        listed.status == 200 and isinstance(items, list) and len(items) == 2,
        "P8-03 retained terminal requests are unavailable",
    )
    bindings = [
        {
            "request_id": str(item.get("globalId")),
            "outbox_id": str(item.get("outboxEventId")),
        }
        for item in items
        if isinstance(item, dict)
    ]
    require(len(bindings) == 2, "P8-03 retained Outbox bindings drifted")
    replayed = run_bench_fixture(
        "replay_terminal",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "bindings": bindings,
        },
    )
    require(
        replayed.get("crossProcessReplay") is True
        and replayed.get("notClaimedCount") == 2
        and replayed.get("recoverableCount") == 0
        and replayed.get("mappingCount") == 0,
        "P8-03 cross-process terminal replay drifted",
    )
    _assert_no_formal_target(listed.body)
    return replayed


def run_legacy(
    base_url: str,
    fixture_password: str,
    legacy_request_id: str,
    legacy_node_id: str,
) -> dict[str, object]:
    """Exercise the post-migration read-only legacy boundary over HTTP."""

    administrator = login(
        base_url,
        "Administrator",
        secret_from_environment("NPI_RUNTIME_ADMINISTRATOR_PASSWORD"),
    )
    actor = login(base_url, ACTOR_USER, fixture_password)
    actor_csrf = bootstrap_csrf(actor, base_url, ACTOR_USER)
    context = released_item_context(administrator, actor, base_url)
    project_id = str(context["projectGlobalId"])
    _require_enabled_runtime_marker(project_id)
    path = item_publish_path(project_id)
    listed = item_publish_request(actor, base_url, path, query_key="legacy-list")
    items = listed.body.get("items")
    require(
        listed.status == 200
        and isinstance(items, list)
        and len(items) == 3,
        "P8-03 migrated legacy Item was not readable in the collection",
    )
    legacy_items = [
        item
        for item in items
        if isinstance(item, dict) and item.get("globalId") == legacy_request_id
    ]
    require(
        len(legacy_items) == 1,
        "P8-03 migrated legacy Item was not projected",
    )
    legacy_public = legacy_items[0]
    require(
        legacy_public.get("dispatchAllowed") is False
        and legacy_public.get("legacyReadOnly") is True
        and legacy_public.get("current") is False
        and legacy_public.get("outboxEventId") is None
        and legacy_public.get("resultGlobalId") is None,
        "P8-03 legacy Item was exposed as executable work",
    )
    detail = item_publish_request(
        actor,
        base_url,
        item_publish_path(project_id, legacy_request_id),
        query_key="legacy-detail",
    )
    require(detail.status == 200, "P8-03 migrated legacy Item detail is unavailable")
    require(
        detail.body.get("requestGlobalId") == legacy_request_id
        and detail.body.get("request", {}).get("legacyReadOnly") is True
        and detail.body.get("request", {}).get("current") is False
        and detail.body.get("currentMapping") is None
        and detail.body.get("attempts") == []
        and detail.body.get("result") is None
        and detail.body.get("permissions") == {"canView": True, "canExecute": False},
        "P8-03 legacy Item detail was not read-only",
    )
    _assert_no_formal_target(legacy_public)
    _assert_no_formal_target(detail.body)
    _assert_no_private_execution_metadata(legacy_public)
    _assert_no_private_execution_metadata(detail.body)
    expected_request_ids = [
        str(item.get("globalId")) for item in items if isinstance(item, dict)
    ]
    legacy_outbox_id = os.environ.get("NPI_P8_03_RUNTIME_LEGACY_OUTBOX_ID", "")
    legacy_stream_hash = os.environ.get("NPI_P8_03_RUNTIME_LEGACY_STREAM_HASH", "")
    require(
        str(UUID(legacy_outbox_id)) == legacy_outbox_id
        and len(legacy_stream_hash) == 64
        and all(character in "0123456789abcdef" for character in legacy_stream_hash),
        "P8-03 legacy runtime binding is incomplete",
    )
    rejected = item_publish_request(
        actor,
        base_url,
        path,
        method="POST",
        payload=create_payload(context, legacy_node_id),
        csrf_token=actor_csrf,
        idempotency_key=f"p8-03-legacy-reconcile-{FIXTURE_RUN_ID}",
    )
    validate_problem(
        rejected,
        409,
        "ITEM_PUBLISH_STREAM_RECONCILIATION_REQUIRED",
    )
    inspected = run_bench_fixture(
        "inspect_legacy",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "legacy_request_id": legacy_request_id,
            "legacy_outbox_id": legacy_outbox_id,
            "source_stream_key_hash": legacy_stream_hash,
            "expected_request_ids": expected_request_ids,
        },
    )
    cleaned = run_bench_fixture(
        "cleanup_legacy",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "legacy_request_id": legacy_request_id,
            "legacy_outbox_id": legacy_outbox_id,
            "source_stream_key_hash": legacy_stream_hash,
        },
    )
    require(
        inspected.get("guardBlocked") is True
        and inspected.get("legacyBindingsNull") is True
        and inspected.get("legacyState") == "queued"
        and inspected.get("legacyOptimisticVersion") == 1
        and inspected.get("legacyTimestampsEqual") is True
        and inspected.get("workerRoute") is None
        and inspected.get("adapterCalls") == 0
        and cleaned.get("legacyRowsRemoved") is True,
        "P8-03 legacy migration boundary proof drifted",
    )
    return {
        "commandReconciliationRequired": True,
        "detailReadOnly": True,
        "guardBlocked": inspected["guardBlocked"],
        "legacyState": inspected["legacyState"],
        "legacyOptimisticVersion": inspected["legacyOptimisticVersion"],
        "legacyTimestampsEqual": inspected["legacyTimestampsEqual"],
        "legacyBindingsNull": inspected["legacyBindingsNull"],
        "legacyRowsRemoved": cleaned["legacyRowsRemoved"],
        "listAndDetailReadable": True,
        "workerZeroClaimAdapter": inspected["workerRoute"] is None,
    }


def capture_project(fixture_run_id: str) -> dict[str, object]:
    import frappe

    document_runtime._validated_runtime_site()
    require(fixture_run_id == FIXTURE_RUN_ID, "P8-03 fixture namespace drifted")
    project_id = frappe.db.get_value(
        "NPI Engineering Project",
        {"tenant_id": TENANT_ID, "business_code": document_runtime.BUSINESS_CODE},
        "global_id",
    )
    require(
        isinstance(project_id, str) and str(UUID(project_id)) == project_id,
        "P8-03 retained Project identity is unavailable",
    )
    return {"projectGlobalId": project_id}


def _rows(doctype: str, filters: object, fields: list[str]) -> list[dict[str, Any]]:
    import frappe

    return list(
        frappe.get_all(
            doctype,
            filters=filters,
            fields=fields,
            order_by="name asc",
            limit_page_length=100,
        )
    )


def _structural_context(project_id: str) -> dict[str, object]:
    from npi_integration.item_publish.domain import canonical_hash

    requests = _rows(
        "NPI Item Publish Request",
        {"project_global_id": project_id},
        [
            "global_id",
            "state",
            "outbox_event_id",
            "result_global_id",
            "optimistic_version",
            "actor_user_id",
            "service_actor_user_id",
            "target_idempotency_key_hash",
            "semantic_source_effect_hash",
            "semantic_effect_hash",
            "owner",
            "modified_by",
        ],
    )
    request_ids = [str(row["global_id"]) for row in requests]
    scoped = [["request_global_id", "in", request_ids]]
    outboxes = _rows(
        "NPI Outbox Message",
        {
            "project_global_id": project_id,
            "operation": "publish_released_item",
        },
        [
            "event_id",
            "request_global_id",
            "payload_hash",
            "payload",
            "state",
            "attempt_count",
            "adapter_boundary_crossed",
            "last_attempt_global_id",
            "result_global_id",
            "disposition",
            "owner",
            "modified_by",
            "service_actor_user_id",
            "target_idempotency_key_hash",
            "semantic_source_effect_hash",
            "semantic_effect_hash",
        ],
    )
    for outbox in outboxes:
        payload = outbox.get("payload")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = None
        require(
            isinstance(payload, dict)
            and set(payload) == CURRENT_OUTBOX_PAYLOAD_KEYS
            and isinstance(outbox.get("payload_hash"), str)
            and canonical_hash(payload) == outbox.get("payload_hash"),
            "P8-03 persisted Item Outbox payload is not the exact 19-key envelope",
        )
    attempts = (
        _rows(
            "NPI Item Publish Attempt",
            scoped,
            [
                "global_id",
                "request_global_id",
                "attempt_number",
                "target_idempotency_key_hash",
                "state",
                "adapter_boundary_crossed",
                "transport_disposition",
                "fault_kind",
                "reconciliation_required",
                "safe_error_code",
                "attempt_hash",
                "owner",
                "modified_by",
            ],
        )
        if request_ids
        else []
    )
    results = (
        _rows(
            "NPI Item Publish Result",
            scoped,
            [
                "global_id",
                "request_global_id",
                "attempt_global_id",
                "attempt_number",
                "idempotency_key_hash",
                "state",
                "authority",
                "formal_item_code",
                "target_version",
                "fault_kind",
                "result_hash",
                "owner",
                "modified_by",
            ],
        )
        if request_ids
        else []
    )
    mapping_heads = _rows(
        "NPI Item Mapping Head",
        {"project_global_id": project_id},
        ["global_id"],
    )
    mapping_observations = _rows(
        "NPI Item Mapping Observation",
        {"project_global_id": project_id},
        ["global_id"],
    )
    guards = _rows(
        "NPI Item Publish Stream Guard",
        {"project_global_id": project_id},
        [
            "name",
            "source_stream_key_hash",
            "active_request_global_id",
            "active_target_idempotency_key_hash",
            "active_state",
            "last_request_global_id",
            "last_target_idempotency_key_hash",
            "last_state",
            "blocked_reason_code",
            "optimistic_version",
            "owner",
            "modified_by",
        ],
    )
    audit_events = (
        _rows(
            "NPI Audit Event",
            [["global_id", "in", request_ids]],
            ["global_id", "actor", "operation", "result", "trace_id"],
        )
        if request_ids
        else []
    )
    value = {
        "requests": requests,
        "outboxes": outboxes,
        "attempts": attempts,
        "results": results,
        "mappingHeadCount": len(mapping_heads),
        "mappingObservationCount": len(mapping_observations),
        "guards": guards,
        "auditEvents": audit_events,
    }
    return {**value, "digest": canonical_hash(value)}


def _validate_fixture(
    *,
    fixture_run_id: str,
    project_id: str,
    request_ids: tuple[str, ...],
) -> None:
    import frappe

    document_runtime._validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID
        and os.environ.get("NPI_P8_03_RUNTIME_ENABLED") == "1"
        and os.environ.get("NPI_P8_03_RUNTIME_MARKER") == RUNTIME_MARKER
        and os.environ.get("NPI_P8_03_RUNTIME_PROJECT_ID") == project_id
        and os.environ.get("NPI_P8_03_RUNTIME_REQUESTER") == ACTOR_USER
        and isinstance(os.environ.get("NPI_P8_03_RUNTIME_WORKER"), str)
        and os.environ.get("NPI_P8_03_RUNTIME_WORKER") not in {None, ACTOR_USER},
        "P8-03 disposable execution binding drifted",
    )
    worker_user = os.environ.get("NPI_P8_03_RUNTIME_WORKER")
    require(
        isinstance(worker_user, str) and worker_user and worker_user != ACTOR_USER,
        "P8-03 worker fixture actor is not distinct from requester",
    )
    worker_row = frappe.get_doc("User", worker_user)
    worker_roles = frozenset(frappe.get_roles(worker_user))
    require(
        int(worker_row.enabled or 0) == 1
        and str(worker_row.user_type) == "System User"
        and "NPI API User" in worker_roles,
        "P8-03 frozen worker actor is not an enabled internal NPI API User",
    )
    project = frappe.get_doc("NPI Engineering Project", project_id)
    require(
        str(project.global_id) == project_id and str(project.tenant_id) == TENANT_ID,
        "P8-03 retained Project scope drifted",
    )
    for request_id in request_ids:
        row = frappe.get_doc("NPI Item Publish Request", request_id)
        require(
            str(row.project_global_id) == project_id
            and str(row.tenant_id) == TENANT_ID
            and str(row.actor_user_id) == ACTOR_USER,
            "P8-03 retained request scope drifted",
        )
        require(
            str(row.service_actor_user_id)
            == os.environ.get("NPI_P8_03_RUNTIME_WORKER"),
            "P8-03 frozen service actor binding drifted",
        )


def _require_disposable_legacy_fixture(
    fixture_run_id: str,
    project_id: str,
) -> None:
    """Validate every identity boundary before a legacy fixture SQL statement."""

    import frappe

    # This helper must remain the first guard before any legacy fixture SQL.
    # The document runtime helper validates the persistent Site configuration
    # and the live database identity (database/user/port), not merely env vars.
    document_runtime._validated_runtime_site()
    require(
        frappe.local.site == SITE_NAME == "npi.localhost"
        and frappe.conf.get("db_name")
        == document_runtime.DATABASE_NAME
        == "npi_one_runtime"
        and frappe.conf.get("npi_tenant_id") == TENANT_ID
        and frappe.conf.get("npi_runtime_disposable_marker")
        == document_runtime.RUNTIME_MARKER
        == "npi-one-local-runtime-disposable-v1"
        and document_runtime.DATABASE_USER == "npi_one_runtime"
        and document_runtime.DATABASE_PORT == 3306,
        "P8-03 legacy fixture Site/database identity drifted",
    )
    require(
        os.environ.get("NPI_P8_03_RUNTIME_ENABLED") == "1"
        and os.environ.get("NPI_P8_03_RUNTIME_MARKER") == RUNTIME_MARKER
        and os.environ.get("NPI_P8_03_RUNTIME_PROJECT_ID") == project_id
        and os.environ.get("NPI_P8_03_RUNTIME_REQUESTER") == ACTOR_USER
        and isinstance(os.environ.get("NPI_P8_03_RUNTIME_WORKER"), str)
        and os.environ.get("NPI_P8_03_RUNTIME_WORKER") not in {None, ACTOR_USER},
        "P8-03 legacy fixture environment binding drifted",
    )
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "P8-03 legacy fixture namespace drifted",
    )
    require(
        str(getattr(frappe.session, "user", "")) == "Administrator",
        "P8-03 legacy fixture must run as Administrator",
    )
    project = frappe.get_doc("NPI Engineering Project", project_id)
    require(
        str(project.global_id) == project_id
        and str(project.tenant_id) == TENANT_ID,
        "P8-03 legacy fixture Project identity drifted",
    )


def _require_enabled_runtime_marker(project_id: str) -> None:
    require(
        os.environ.get("NPI_P8_03_RUNTIME_ENABLED") == "1"
        and os.environ.get("NPI_P8_03_RUNTIME_MARKER") == RUNTIME_MARKER
        and os.environ.get("NPI_P8_03_RUNTIME_PROJECT_ID") == project_id,
        "P8-03 legacy fixture is not bound to the disposable runtime marker",
    )


def _legacy_event_snapshot(
    *,
    event_id: str,
    global_id: str,
    tenant_id: str,
    project_id: str,
    event_type: str,
    operation: str,
    profile_id: str,
    profile_version: int,
    profile_snapshot_hash: str,
    source_stream_key_hash: str,
    source_hash: str,
    expected_mapping_version: int,
    expected_target_version: int | None,
    actor_user_id: str,
    request_id: str,
    trace_id: str,
    idempotency_key_hash: str,
    payload_hash: str,
) -> dict[str, object]:
    """Return the frozen 8dd event snapshot, excluding post-8dd bindings."""

    return {
        "schemaVersion": 1,
        "eventId": event_id,
        "eventType": event_type,
        "globalId": global_id,
        "objectVersion": 1,
        "tenantId": tenant_id,
        "projectGlobalId": project_id,
        "requestGlobalId": global_id,
        "operation": operation,
        "profileId": profile_id,
        "profileVersion": profile_version,
        "profileSnapshotHash": profile_snapshot_hash,
        "sourceStreamKeyHash": source_stream_key_hash,
        "sourceHash": source_hash,
        "expectedMappingVersion": expected_mapping_version,
        "expectedTargetVersion": expected_target_version,
        "actorUserId": actor_user_id,
        "requestId": request_id,
        "traceId": trace_id,
        "idempotencyKeyHash": idempotency_key_hash,
        "payloadHash": payload_hash,
    }


def seed_legacy(
    fixture_run_id: str,
    project_id: str,
) -> dict[str, object]:
    """Insert one exact 8dd-shaped row through a marker-gated test seam.

    This intentionally uses the database only as a disposable migration
    fixture: the row omits all post-8dd execution bindings and is never
    promoted through a product controller.  The production repositories stay
    responsible for the read-only legacy projection and reconciliation block.
    """

    import frappe
    from npi_integration.item_publish.domain import canonical_hash

    _require_disposable_legacy_fixture(fixture_run_id, project_id)
    rows = _rows(
        "NPI Item Publish Request",
        {"project_global_id": project_id},
        ["global_id"],
    )
    require(rows, "P8-03 legacy fixture source request is unavailable")
    source_request_id = str(rows[0]["global_id"])
    source_request = frappe.get_doc("NPI Item Publish Request", source_request_id)
    require(
        source_request.outbox_event_id,
        "P8-03 legacy fixture source Outbox is unavailable",
    )
    source_outbox = frappe.get_doc(
        "NPI Outbox Message", str(source_request.outbox_event_id)
    )
    legacy_id = str(uuid5(UUID(source_request_id), "npi-one-p8-03-legacy-8dd"))
    legacy_request_id = str(uuid5(UUID(source_request_id), "legacy-request"))
    legacy_outbox_id = str(uuid5(UUID(source_request_id), "legacy-outbox"))
    source_stream = str(source_request.source_stream_key_hash)
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    source_payload = source_outbox.payload
    if isinstance(source_payload, str):
        source_payload = json.loads(source_payload)
    require(
        isinstance(source_payload, dict),
        "P8-03 source Outbox payload is not a JSON object",
    )
    legacy_payload = dict(source_payload)
    for key in (
        "target_idempotency_key_hash",
        "semantic_source_effect_hash",
        "semantic_effect_hash",
    ):
        legacy_payload.pop(key, None)
    legacy_payload["request_global_id"] = legacy_id
    require(
        set(legacy_payload) == LEGACY_OUTBOX_PAYLOAD_KEYS,
        "P8-03 source Outbox payload is not the exact 8dd shape",
    )
    legacy_payload_hash = canonical_hash(legacy_payload)
    legacy_trace_id = f"trace-p8-03-legacy-outbox-{FIXTURE_RUN_ID[:12]}"
    legacy_event_snapshot = _legacy_event_snapshot(
        event_id=legacy_outbox_id,
        global_id=legacy_id,
        tenant_id=str(source_request.tenant_id),
        project_id=str(source_request.project_global_id),
        event_type=str(source_outbox.event_type),
        operation=str(source_outbox.operation),
        profile_id=str(source_outbox.profile_id),
        profile_version=int(source_outbox.profile_version),
        profile_snapshot_hash=str(source_outbox.profile_snapshot_hash),
        source_stream_key_hash=source_stream,
        source_hash=str(source_outbox.source_hash),
        expected_mapping_version=int(source_outbox.expected_mapping_version),
        expected_target_version=(
            int(source_outbox.expected_target_version)
            if source_outbox.expected_target_version is not None
            else None
        ),
        actor_user_id=str(source_outbox.actor_user_id),
        request_id=legacy_request_id,
        trace_id=legacy_trace_id,
        idempotency_key_hash=str(source_outbox.idempotency_key_hash),
        payload_hash=legacy_payload_hash,
    )
    legacy_event_snapshot_hash = canonical_hash(legacy_event_snapshot)
    duplicate_attempt_count = int(
        frappe.db.sql(
            """
            SELECT COUNT(*)
            FROM (
                SELECT attempt_global_id
                FROM `tabNPI Item Publish Result`
                WHERE attempt_global_id IS NOT NULL
                GROUP BY attempt_global_id
                HAVING COUNT(*) > 1
            ) AS duplicate_attempts
            """
        )[0][0]
        or 0
    )
    require(
        duplicate_attempt_count == 0,
        "P8-03 pre-migration Result attempt identity is duplicated",
    )
    # A rerun of the disposable fixture replaces only its exact legacy row and
    # guard.  No production or unrelated project rows are addressable here.
    frappe.db.sql(
        "DELETE FROM `tabNPI Item Publish Request` "
        "WHERE name = %s AND project_global_id = %s",
        (legacy_id, project_id),
    )
    frappe.db.sql(
        "DELETE FROM `tabNPI Outbox Message` "
        "WHERE name = %s AND project_global_id = %s",
        (legacy_outbox_id, project_id),
    )
    frappe.db.sql(
        "DELETE FROM `tabNPI Item Publish Stream Guard` "
        "WHERE source_stream_key_hash = %s AND project_global_id = %s",
        (source_stream, project_id),
    )
    legacy_request_columns = (
        "name",
        "creation",
        "modified",
        "modified_by",
        "owner",
        "global_id",
        "schema_version",
        "api_version",
        "operation",
        "tenant_id",
        "project_global_id",
        "source_stream_key_hash",
        "engineering_item_id",
        "selected_publish_node_global_id",
        "source_snapshot",
        "source_hash",
        "released_evidence_snapshot",
        "released_evidence_hash",
        "profile_id",
        "profile_version",
        "profile_snapshot_hash",
        "target_mode",
        "environment_code",
        "intent",
        "expected_mapping_version",
        "expected_formal_item_code",
        "expected_target_version",
        "expected_mapping_observation_hash",
        "state",
        "dispatch_allowed",
        "outbox_event_id",
        "result_global_id",
        "actor_user_id",
        "request_id",
        "trace_id",
        "idempotency_key_hash",
        "payload_hash",
        "optimistic_version",
        "created_at",
        "updated_at",
    )
    legacy_request_values = (
        legacy_id,
        now,
        now,
        ACTOR_USER,
        ACTOR_USER,
        legacy_id,
        source_request.schema_version,
        source_request.api_version,
        source_request.operation,
        source_request.tenant_id,
        source_request.project_global_id,
        source_request.source_stream_key_hash,
        source_request.engineering_item_id,
        source_request.selected_publish_node_global_id,
        source_request.source_snapshot,
        source_request.source_hash,
        source_request.released_evidence_snapshot,
        source_request.released_evidence_hash,
        source_request.profile_id,
        source_request.profile_version,
        source_request.profile_snapshot_hash,
        source_request.target_mode,
        source_request.environment_code,
        source_request.intent,
        source_request.expected_mapping_version,
        source_request.expected_formal_item_code,
        source_request.expected_target_version,
        source_request.expected_mapping_observation_hash,
        "queued",
        1,
        legacy_outbox_id,
        None,
        source_request.actor_user_id,
        legacy_request_id,
        f"trace-p8-03-legacy-{FIXTURE_RUN_ID[:12]}",
        source_request.idempotency_key_hash,
        source_request.payload_hash,
        1,
        now,
        now,
    )
    legacy_request_placeholders = tuple("%s" for _ in legacy_request_columns)
    require(
        len(legacy_request_columns)
        == len(legacy_request_placeholders)
        == len(legacy_request_values),
        "P8-03 legacy Request SQL shape drifted",
    )
    frappe.db.sql(
        "INSERT INTO `tabNPI Item Publish Request` ("
        + ", ".join(legacy_request_columns)
        + ") VALUES ("
        + ", ".join(legacy_request_placeholders)
        + ")",
        legacy_request_values,
    )
    legacy_outbox_columns = (
        "name",
        "creation",
        "modified",
        "modified_by",
        "owner",
        "event_id",
        "event_type",
        "global_id",
        "object_version",
        "trace_id",
        "payload_hash",
        "payload",
        "state",
        "attempt_count",
        "last_error_code",
        "schema_version",
        "operation",
        "tenant_id",
        "project_global_id",
        "request_global_id",
        "profile_id",
        "profile_version",
        "profile_snapshot_hash",
        "source_stream_key_hash",
        "source_hash",
        "expected_mapping_version",
        "expected_target_version",
        "actor_user_id",
        "request_id",
        "idempotency_key_hash",
        "event_snapshot_hash",
        "claim_token",
        "claimed_at",
        "lease_expires_at",
        "adapter_boundary_crossed",
        "last_attempt_global_id",
        "result_global_id",
        "disposition",
        "last_error_at",
    )
    legacy_outbox_values = (
        legacy_outbox_id,
        now,
        now,
        ACTOR_USER,
        ACTOR_USER,
        legacy_outbox_id,
        source_outbox.event_type,
        legacy_id,
        1,
        legacy_trace_id,
        legacy_payload_hash,
        json.dumps(legacy_payload, separators=(",", ":"), sort_keys=True),
        "pending",
        0,
        None,
        source_outbox.schema_version,
        source_outbox.operation,
        source_outbox.tenant_id,
        source_outbox.project_global_id,
        legacy_id,
        source_outbox.profile_id,
        source_outbox.profile_version,
        source_outbox.profile_snapshot_hash,
        source_outbox.source_stream_key_hash,
        source_outbox.source_hash,
        source_outbox.expected_mapping_version,
        source_outbox.expected_target_version,
        source_outbox.actor_user_id,
        legacy_request_id,
        source_outbox.idempotency_key_hash,
        legacy_event_snapshot_hash,
        None,
        None,
        None,
        0,
        None,
        None,
        "ready",
        None,
    )
    legacy_outbox_placeholders = tuple("%s" for _ in legacy_outbox_columns)
    require(
        len(legacy_outbox_columns)
        == len(legacy_outbox_placeholders)
        == len(legacy_outbox_values),
        "P8-03 legacy Outbox SQL shape drifted",
    )
    frappe.db.sql(
        "INSERT INTO `tabNPI Outbox Message` ("
        + ", ".join(legacy_outbox_columns)
        + ") VALUES ("
        + ", ".join(legacy_outbox_placeholders)
        + ")",
        legacy_outbox_values,
    )
    return {
        "legacyOutboxId": legacy_outbox_id,
        "legacyRequestId": legacy_id,
        "legacyRequestCorrelationId": legacy_request_id,
        "projectGlobalId": project_id,
        "selectedPublishNodeGlobalId": str(
            source_request.selected_publish_node_global_id
        ),
        "sourceStreamKeyHash": source_stream,
        "newBindingsNull": True,
        "preMigrationDuplicateAttemptCount": duplicate_attempt_count,
        "preMigrationShape": "8dd",
    }


def inspect_legacy(
    fixture_run_id: str,
    project_id: str,
    legacy_request_id: str,
    legacy_outbox_id: str,
    source_stream_key_hash: str,
    expected_request_ids: list[str],
) -> dict[str, object]:
    """Verify migration left legacy bindings null and command blocked the stream."""

    import frappe
    from npi_integration.item_publish.domain import canonical_hash

    _require_disposable_legacy_fixture(fixture_run_id, project_id)
    legacy = frappe.get_doc("NPI Item Publish Request", legacy_request_id)
    request_ids = [
        str(row["global_id"])
        for row in _rows(
            "NPI Item Publish Request",
            {"project_global_id": project_id},
            ["global_id"],
        )
    ]
    require(
        set(request_ids) == set(expected_request_ids)
        and str(legacy.global_id) == legacy_request_id
        and str(legacy.outbox_event_id) == legacy_outbox_id
        and str(legacy.state) == "queued"
        and int(legacy.optimistic_version) == 1
        and str(legacy.created_at) == str(legacy.updated_at)
        and not legacy.target_idempotency_key_hash
        and not legacy.service_actor_user_id
        and not legacy.semantic_source_effect_hash
        and not legacy.semantic_effect_hash,
        "P8-03 migration backfilled the legacy Item execution bindings",
    )
    guard = frappe.db.get_value(
        "NPI Item Publish Stream Guard",
        {
            "source_stream_key_hash": source_stream_key_hash,
            "project_global_id": project_id,
        },
        [
            "blocked_reason_code",
            "active_request_global_id",
            "active_target_idempotency_key_hash",
            "active_state",
        ],
        as_dict=True,
    )
    require(
        guard
        and guard.blocked_reason_code == "ITEM_PUBLISH_STREAM_RECONCILIATION_REQUIRED"
        and not guard.active_request_global_id
        and not guard.active_target_idempotency_key_hash
        and not guard.active_state,
        "P8-03 legacy stream guard was not durably blocked",
    )
    outbox = frappe.get_doc("NPI Outbox Message", legacy_outbox_id)
    outbox_payload = outbox.payload
    if isinstance(outbox_payload, str):
        outbox_payload = json.loads(outbox_payload)
    require(
        isinstance(outbox_payload, dict)
        and set(outbox_payload) == LEGACY_OUTBOX_PAYLOAD_KEYS
        and outbox_payload.get("request_global_id") == legacy_request_id
        and outbox_payload.get("request_payload_hash") == str(legacy.payload_hash)
        and canonical_hash(outbox_payload) == str(outbox.payload_hash),
        "P8-03 legacy Outbox payload is not an exact 8dd envelope",
    )
    expected_event_snapshot = _legacy_event_snapshot(
        event_id=str(outbox.event_id),
        global_id=str(outbox.global_id),
        tenant_id=str(outbox.tenant_id),
        project_id=str(outbox.project_global_id),
        event_type=str(outbox.event_type),
        operation=str(outbox.operation),
        profile_id=str(outbox.profile_id),
        profile_version=int(outbox.profile_version),
        profile_snapshot_hash=str(outbox.profile_snapshot_hash),
        source_stream_key_hash=str(outbox.source_stream_key_hash),
        source_hash=str(outbox.source_hash),
        expected_mapping_version=int(outbox.expected_mapping_version),
        expected_target_version=(
            int(outbox.expected_target_version)
            if outbox.expected_target_version is not None
            else None
        ),
        actor_user_id=str(outbox.actor_user_id),
        request_id=str(outbox.request_id),
        trace_id=str(outbox.trace_id),
        idempotency_key_hash=str(outbox.idempotency_key_hash),
        payload_hash=str(outbox.payload_hash),
    )
    require(
        str(outbox.request_global_id) == legacy_request_id
        and str(outbox.global_id) == legacy_request_id
        and str(outbox.event_id) == legacy_outbox_id
        and str(outbox.state) == "pending"
        and int(outbox.attempt_count or 0) == 0
        and str(outbox.disposition) == "ready"
        and str(outbox.event_snapshot_hash)
        == canonical_hash(expected_event_snapshot)
        and not outbox.service_actor_user_id
        and not outbox.target_idempotency_key_hash
        and not outbox.semantic_source_effect_hash
        and not outbox.semantic_effect_hash,
        "P8-03 migration promoted the legacy Item Outbox envelope",
    )
    duplicate_attempt_count = int(
        frappe.db.sql(
            """
            SELECT COUNT(*)
            FROM (
                SELECT attempt_global_id
                FROM `tabNPI Item Publish Result`
                WHERE attempt_global_id IS NOT NULL
                GROUP BY attempt_global_id
                HAVING COUNT(*) > 1
            ) AS duplicate_attempts
            """
        )[0][0]
        or 0
    )
    unique_indexes = frappe.db.sql(
        "SHOW INDEX FROM `tabNPI Item Publish Result`",
        as_dict=True,
    )
    attempt_index_is_unique = any(
        str(index.get("Column_name")) == "attempt_global_id"
        and int(index.get("Non_unique") or 1) == 0
        for index in unique_indexes
    )
    require(
        duplicate_attempt_count == 0 and attempt_index_is_unique,
        "P8-03 migrated Result attempt uniqueness is not enforced",
    )
    # The worker's read-only route probe and closed processing call are the
    # real zero-claim/zero-adapter assertions for the legacy request.
    from npi_integration.item_publish.worker_repository import (
        FrappeItemPublishWorkerRepository,
    )
    from npi_integration.item_publish.worker import process_outbox_message
    from npi_integration.item_publish.runtime_fixture import (
        synthetic_adapter_call_count,
    )

    missing_route = FrappeItemPublishWorkerRepository().execution_route(
        UUID(legacy_outbox_id)
    )
    require(missing_route is None, "P8-03 legacy row acquired an executable route")
    outcome = process_outbox_message(legacy_outbox_id)
    require(
        outcome.get("state") == "not_claimed",
        "P8-03 legacy Item Outbox acquired a worker claim",
    )
    adapter_calls = synthetic_adapter_call_count()
    require(adapter_calls == 0, "P8-03 legacy Item reached the adapter boundary")
    return {
        "adapterCalls": adapter_calls,
        "guardBlocked": True,
        "legacyState": str(legacy.state),
        "legacyOptimisticVersion": int(legacy.optimistic_version),
        "legacyTimestampsEqual": str(legacy.created_at) == str(legacy.updated_at),
        "legacyBindingsNull": True,
        "legacyProjectionReadOnly": True,
        "postMigrationDuplicateAttemptCount": duplicate_attempt_count,
        "resultAttemptIndexUnique": attempt_index_is_unique,
        "workerRoute": None,
    }


def cleanup_legacy(
    fixture_run_id: str,
    project_id: str,
    legacy_request_id: str,
    legacy_outbox_id: str,
    source_stream_key_hash: str,
) -> dict[str, object]:
    import frappe

    _require_disposable_legacy_fixture(fixture_run_id, project_id)
    frappe.db.sql(
        "DELETE FROM `tabNPI Outbox Message` "
        "WHERE name = %s AND request_global_id = %s "
        "AND project_global_id = %s",
        (legacy_outbox_id, legacy_request_id, project_id),
    )
    frappe.db.sql(
        "DELETE FROM `tabNPI Item Publish Request` "
        "WHERE name = %s AND project_global_id = %s",
        (legacy_request_id, project_id),
    )
    frappe.db.sql(
        "DELETE FROM `tabNPI Item Publish Stream Guard` "
        "WHERE source_stream_key_hash = %s AND project_global_id = %s "
        "AND blocked_reason_code = %s",
        (
            source_stream_key_hash,
            project_id,
            "ITEM_PUBLISH_STREAM_RECONCILIATION_REQUIRED",
        ),
    )
    return {"legacyRowsRemoved": True, "guardCleanupBounded": True}


def exercise_worker(
    fixture_run_id: str,
    project_id: str,
    synthetic_request_id: str,
    synthetic_outbox_id: str,
    uncertain_request_id: str,
    uncertain_outbox_id: str,
) -> dict[str, object]:
    import frappe

    from npi_integration.item_publish.runtime_fixture import (
        resolve_profile,
        synthetic_adapter_call_count,
        synthetic_adapter_session_users,
    )
    from npi_integration.item_publish.worker import process_outbox_message
    from npi_integration.item_publish.worker_repository import (
        FrappeItemPublishWorkerRepository,
    )
    from npi_integration.item_publish.frappe_validation import (
        item_service_actor_scope,
    )

    _validate_fixture(
        fixture_run_id=fixture_run_id,
        project_id=project_id,
        request_ids=(synthetic_request_id, uncertain_request_id),
    )
    requester_user = str(getattr(frappe.session, "user", ""))
    worker_user = os.environ.get("NPI_P8_03_RUNTIME_WORKER")
    require(
        requester_user == ACTOR_USER,
        "P8-03 runtime worker fixture did not start as the authenticated requester",
    )
    require(
        isinstance(worker_user, str) and worker_user and worker_user != requester_user,
        "P8-03 runtime worker fixture actor is not distinct from requester",
    )

    def as_worker(function, *args, **kwargs):
        with item_service_actor_scope(worker_user):
            result = function(*args, **kwargs)
            require(
                str(getattr(frappe.session, "user", "")) == worker_user,
                "P8-03 frozen worker scope changed before its write completed",
            )
            return result

    repository = FrappeItemPublishWorkerRepository()
    anchor = datetime.now(UTC)

    first = as_worker(
        repository.claim,
        UUID(synthetic_outbox_id),
        now=anchor - timedelta(minutes=12),
    )
    require(
        first is not None and first.command.attempt_number == 1,
        "P8-03 initial pending claim drifted",
    )
    frappe.db.commit()
    live = as_worker(
        repository.claim,
        UUID(synthetic_outbox_id),
        now=anchor - timedelta(minutes=7, seconds=1),
    )
    require(live is None, "P8-03 live claim was not excluded")
    frappe.db.rollback()
    recovered = as_worker(
        repository.claim,
        UUID(synthetic_outbox_id),
        now=anchor - timedelta(minutes=6),
    )
    require(
        recovered is not None
        and recovered.expired_recovery
        and not recovered.recovered_after_adapter_boundary
        and recovered.command.attempt_number == 2,
        "P8-03 expired pre-boundary claim was not recovered",
    )
    frappe.db.commit()
    calls_before_synthetic = synthetic_adapter_call_count()
    require(
        str(getattr(frappe.session, "user", "")) == requester_user,
        "P8-03 worker claim did not restore the requester session",
    )
    synthetic = process_outbox_message(synthetic_outbox_id)
    caller_restored_after_synthetic = (
        str(getattr(frappe.session, "user", "")) == requester_user
    )
    require(
        synthetic.get("state") == "synthetic_verified"
        and synthetic.get("mappingAdvanced") is False
        and synthetic_adapter_call_count() == calls_before_synthetic + 1,
        "P8-03 Synthetic worker result drifted",
    )
    require(
        caller_restored_after_synthetic,
        "P8-03 worker did not restore the requester after Synthetic execution",
    )

    uncertain_claim = as_worker(
        repository.claim,
        UUID(uncertain_outbox_id),
        now=anchor - timedelta(minutes=6),
    )
    require(
        uncertain_claim is not None and uncertain_claim.command.attempt_number == 1,
        "P8-03 uncertain-path initial claim drifted",
    )
    frappe.db.commit()
    uncertain_profile = as_worker(
        repository.require_execution_profile,
        uncertain_claim,
        resolve_profile(TENANT_ID, project_id),
    )
    require(
        as_worker(
            repository.mark_adapter_boundary,
            uncertain_claim,
            profile=uncertain_profile,
            now=anchor - timedelta(minutes=5, seconds=59),
        ),
        "P8-03 durable adapter boundary was not sealed",
    )
    frappe.db.commit()
    calls_before_recovery = synthetic_adapter_call_count()
    require(
        str(getattr(frappe.session, "user", "")) == requester_user,
        "P8-03 worker claim did not restore the requester before recovery",
    )
    uncertain = process_outbox_message(uncertain_outbox_id)
    caller_restored_after_uncertain = (
        str(getattr(frappe.session, "user", "")) == requester_user
    )
    require(
        uncertain.get("state") == "uncertain_after_timeout"
        and uncertain.get("mappingAdvanced") is False
        and synthetic_adapter_call_count() == calls_before_recovery,
        "P8-03 crossed-boundary recovery blindly redispatched",
    )
    require(
        caller_restored_after_uncertain,
        "P8-03 worker did not restore the requester after recovery",
    )

    structural = _structural_context(project_id)
    attempts = structural["attempts"]
    results = structural["results"]
    assert isinstance(attempts, list) and isinstance(results, list)
    synthetic_attempts = [
        row for row in attempts if row["request_global_id"] == synthetic_request_id
    ]
    uncertain_attempts = [
        row for row in attempts if row["request_global_id"] == uncertain_request_id
    ]
    synthetic_attempts.sort(key=lambda row: int(row["attempt_number"]))
    uncertain_attempts.sort(key=lambda row: int(row["attempt_number"]))
    require(
        len(synthetic_attempts) == 3
        and [row["attempt_number"] for row in synthetic_attempts] == [1, 2, 3]
        and len({row["target_idempotency_key_hash"] for row in synthetic_attempts})
        == 1
        and [row["state"] for row in synthetic_attempts]
        == ["observed_failure", "observed_failure", "synthetic_verified"]
        and len(uncertain_attempts) == 1
        and uncertain_attempts[0]["attempt_number"] == 1
        and uncertain_attempts[0]["state"] == "uncertain"
        and bool(uncertain_attempts[0]["adapter_boundary_crossed"])
        and bool(uncertain_attempts[0]["reconciliation_required"]),
        "P8-03 immutable attempt history drifted",
    )
    require(
        len(results) == 2
        and {row["state"] for row in results}
        == {"synthetic_verified", "uncertain_after_timeout"}
        and {row["authority"] for row in results} == {"synthetic", "none"}
        and all(row["formal_item_code"] is None for row in results)
        and all(row["target_version"] is None for row in results)
        and structural["mappingHeadCount"] == 0
        and structural["mappingObservationCount"] == 0,
        "P8-03 non-authoritative result boundary drifted",
    )
    require(
        repository.recoverable_outbox_event_ids(now=datetime.now(UTC)) == (),
        "P8-03 bounded recovery included terminal work",
    )
    audit_events = structural["auditEvents"]
    require(isinstance(audit_events, list), "P8-03 audit trace shape is invalid")
    worker_audit_operations = {
        "item_publish.claim",
        "item_publish.claim_recovered",
        "item_publish.adapter_boundary",
        "item_publish.complete",
        "item_publish.complete_historical_evidence",
    }
    worker_audits = [
        row
        for row in audit_events
        if row.get("operation") in worker_audit_operations
    ]
    require(
        worker_audits and all(row.get("actor") == worker_user for row in worker_audits),
        "P8-03 claim/boundary/complete audit actor drifted from the frozen worker",
    )
    requests = structural["requests"]
    outboxes = structural["outboxes"]
    guards = structural["guards"]
    require(
        isinstance(requests, list)
        and isinstance(outboxes, list)
        and isinstance(guards, list),
        "P8-03 persistence trace shape is invalid",
    )
    scoped_outboxes = [
        row
        for row in outboxes
        if row.get("request_global_id") in {synthetic_request_id, uncertain_request_id}
    ]
    scoped_guards = [
        row
        for row in guards
        if row.get("active_request_global_id")
        or row.get("last_request_global_id")
    ]
    require(
        all(row.get("owner") == requester_user for row in requests)
        and all(row.get("modified_by") == worker_user for row in requests)
        and all(row.get("owner") == requester_user for row in scoped_outboxes)
        and all(row.get("modified_by") == worker_user for row in scoped_outboxes)
        and all(row.get("owner") == worker_user for row in attempts)
        and all(row.get("modified_by") == worker_user for row in attempts)
        and all(row.get("owner") == worker_user for row in results)
        and all(row.get("modified_by") == worker_user for row in results)
        and all(row.get("owner") == requester_user for row in scoped_guards)
        and all(row.get("modified_by") == worker_user for row in scoped_guards),
        "P8-03 persisted owner or modified_by actor drifted",
    )
    adapter_sessions = synthetic_adapter_session_users()
    require(
        adapter_sessions and all(user == worker_user for user in adapter_sessions),
        "P8-03 adapter session actor drifted from the frozen worker",
    )
    return {
        "callerRestoredAfterSynthetic": caller_restored_after_synthetic,
        "callerRestoredAfterUncertain": caller_restored_after_uncertain,
        "adapterCalls": synthetic_adapter_call_count(),
        "adapterSessionWorkerOnly": True,
        "attemptCount": len(attempts),
        "digest": structural["digest"],
        "expiredPreBoundaryRecovered": True,
        "liveClaimRejected": True,
        "mappingCount": 0,
        "resultCount": len(results),
        "syntheticVerified": True,
        "uncertainAfterBoundary": True,
    }


def replay_terminal(
    fixture_run_id: str,
    project_id: str,
    bindings: list[dict[str, str]],
) -> dict[str, object]:
    import frappe

    from npi_integration.item_publish.worker import process_outbox_message
    from npi_integration.item_publish.worker_repository import (
        FrappeItemPublishWorkerRepository,
    )

    require(
        isinstance(bindings, list)
        and len(bindings) == 2
        and all(
            isinstance(value, dict)
            and set(value) == {"request_id", "outbox_id"}
            for value in bindings
        ),
        "P8-03 replay bindings are invalid",
    )
    request_ids = tuple(str(value["request_id"]) for value in bindings)
    _validate_fixture(
        fixture_run_id=fixture_run_id,
        project_id=project_id,
        request_ids=request_ids,
    )
    requester_user = str(getattr(frappe.session, "user", ""))
    require(
        requester_user == ACTOR_USER,
        "P8-03 replay fixture did not start as the authenticated requester",
    )
    before = _structural_context(project_id)
    outcomes = [
        process_outbox_message(str(value["outbox_id"])) for value in bindings
    ]
    require(
        str(getattr(frappe.session, "user", "")) == requester_user,
        "P8-03 worker did not restore the requester after terminal replay",
    )
    after = _structural_context(project_id)
    recoverable = FrappeItemPublishWorkerRepository().recoverable_outbox_event_ids(
        now=datetime.now(UTC)
    )
    require(
        all(outcome.get("state") == "not_claimed" for outcome in outcomes)
        and before == after
        and recoverable == (),
        "P8-03 cross-process replay changed terminal truth",
    )
    return {
        "callerRestored": True,
        "crossProcessReplay": True,
        "digest": after["digest"],
        "mappingCount": after["mappingHeadCount"],
        "notClaimedCount": len(outcomes),
        "recoverableCount": len(recoverable),
    }


def run_bench_fixture(method: str, kwargs: dict[str, object]) -> dict[str, Any]:
    environment = os.environ.copy()
    current_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        str(ROOT)
        if not current_pythonpath
        else f"{ROOT}{os.pathsep}{current_pythonpath}"
    )
    for variable in (
        "NPI_RUNTIME_ADMINISTRATOR_PASSWORD",
        "NPI_RUNTIME_FIXTURE_PASSWORD",
        "NPI_ADMINISTRATOR_PASSWORD",
        "NPI_DATABASE_ROOT_PASSWORD",
    ):
        environment.pop(variable, None)
    completed = subprocess.run(
        [
            str(BENCH_PATH / "env" / "bin" / "python"),
            str(Path(__file__).resolve()),
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
        f"P8-03 Bench fixture {method} failed with a withheld diagnostic",
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    result = json.loads(lines[-1]) if lines else None
    require(isinstance(result, dict), "P8-03 Bench fixture result is invalid")
    return result


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    import frappe

    fixtures = {
        "capture_project": capture_project,
        "exercise_worker": exercise_worker,
        "replay_terminal": replay_terminal,
        "seed_legacy": seed_legacy,
        "inspect_legacy": inspect_legacy,
        "cleanup_legacy": cleanup_legacy,
    }
    require(method in fixtures, "P8-03 Bench fixture is unavailable")
    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    try:
        document_runtime._validated_runtime_site()
        # Read-only project capture runs as Administrator.  Worker fixtures
        # deliberately enter as the authenticated requester; the worker
        # boundary itself must switch to the frozen service actor and restore
        # this session before returning.
        frappe.set_user(
            ACTOR_USER if method in {"exercise_worker", "replay_terminal"} else "Administrator"
        )
        result = fixtures[method](**kwargs)
        frappe.db.commit()
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.destroy()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url")
    parser.add_argument("--disabled-probe", action="store_true")
    parser.add_argument("--replay-only", action="store_true")
    parser.add_argument("--legacy-only", action="store_true")
    parser.add_argument("--legacy-request-id")
    parser.add_argument("--legacy-node-id")
    parser.add_argument("--bench-fixture")
    parser.add_argument("--fixture-kwargs")
    arguments = parser.parse_args()
    if arguments.bench_fixture is not None:
        require(
            arguments.base_url is None
            and arguments.fixture_kwargs is not None
            and not arguments.disabled_probe
            and not arguments.replay_only
            and not arguments.legacy_only,
            "P8-03 fixture invocation drifted",
        )
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "P8-03 fixture arguments are invalid")
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return
    require(
        arguments.base_url is not None
        and FIXTURE_RUN_ID != "0" * 32
        and ACTOR_USER.endswith("@example.invalid")
        and int(arguments.disabled_probe)
        + int(arguments.replay_only)
        + int(arguments.legacy_only)
        <= 1,
        "P8-03 runtime invocation is incomplete",
    )
    base_url = validate_local_fixture_inputs(
        arguments.base_url,
        "Administrator",
        ACTOR_USER,
    )
    fixture_password = secret_from_environment("NPI_RUNTIME_FIXTURE_PASSWORD")
    if arguments.disabled_probe:
        result = run_disabled_probe(base_url, fixture_password)
    elif arguments.replay_only:
        result = run_replay(base_url, fixture_password)
    elif arguments.legacy_only:
        require(
            isinstance(arguments.legacy_request_id, str)
            and isinstance(arguments.legacy_node_id, str)
            and str(UUID(arguments.legacy_request_id)) == arguments.legacy_request_id
            and str(UUID(arguments.legacy_node_id)) == arguments.legacy_node_id,
            "P8-03 legacy runtime invocation is incomplete",
        )
        result = run_legacy(
            base_url,
            fixture_password,
            arguments.legacy_request_id,
            arguments.legacy_node_id,
        )
    else:
        result = run_fresh(base_url, fixture_password)
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
