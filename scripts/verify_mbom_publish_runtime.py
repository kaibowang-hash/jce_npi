from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator, Mapping
from uuid import UUID, uuid5

import verify_document_runtime as document_runtime
import verify_item_publish_runtime as item_runtime
import verify_publish_request_runtime as publish_runtime
from verify_frappe_runtime import (
    login,
    require,
    secret_from_environment,
    validate_local_fixture_inputs,
)
from verify_project_runtime import bootstrap_csrf


ROOT = Path(__file__).resolve().parents[1]
BENCH_PATH = ROOT / "tmp" / "frappe-bench"
SITE_NAME = document_runtime.SITE_NAME
FIXTURE_RUN_ID = document_runtime.FIXTURE_RUN_ID
ACTOR_USER = publish_runtime.ACTOR_USER
RUNTIME_MARKER = "npi-one-mbom-publish-disposable-v1"
ACKNOWLEDGEMENT = (
    "I confirm this request uses the exact released EBOM topology, current Item "
    "readiness, MBOM expectations, and execution profile."
)
MBOM_CREATE_DIAGNOSTICS_ENABLED = False
MBOM_WORKER_DOWNSTREAM_DIAGNOSTICS_ENABLED = False
MBOM_NOT_CLAIMED_DIAGNOSTICS_ENABLED = False
MBOM_POST_DATETIME_WORKER_DIAGNOSTICS_ENABLED = False
MBOM_POST_MANIFEST_WORKER_DIAGNOSTICS_ENABLED = False
MBOM_POST_COMMAND_HASH_WORKER_DIAGNOSTICS_ENABLED = True
_CREATE_FAILURE_MESSAGE = "P8-04 Synthetic command did not create one queued batch"
_WORKER_FAILURE_MESSAGE = "P8-04 Bench fixture failed"
_CREATE_DIAGNOSTIC_TRACE_PATTERN = re.compile(r"^trace-[a-f0-9]{32}$")
_CREATE_DIAGNOSTIC_HEADER = "X-NPI-Diagnostic-Scope"
_CREATE_DIAGNOSTIC_SCOPE = "p804-mbom-create-v1"
_CREATE_SERVER_DIAGNOSTIC_CODES = frozenset(
    {
        "P804_CREATE_COMMAND_CONTEXT",
        "P804_CREATE_INPUT_PARSE",
        "P804_CREATE_PROJECT_LOCK",
        "P804_CREATE_IDEMPOTENCY_CONTEXT",
        "P804_CREATE_IDEMPOTENCY_REPLAY",
        "P804_CREATE_PROBLEM_OUTCOME",
        "P804_CREATE_PROJECT_MUTABILITY",
        "P804_CREATE_PROFILE_RESOLVE",
        "P804_CREATE_PRELOCK_BUILD",
        "P804_CREATE_SERVICE_ACTOR_VALIDATE",
        "P804_CREATE_RESPONSE_BUILD",
        "P804_CREATE_TRANSACTION_SCOPE",
        "P804_CREATE_STREAM_GUARD",
        "P804_CREATE_PROFILE_REVALIDATE",
        "P804_CREATE_LOCKED_BUILD",
        "P804_CREATE_LOCK_COMPARE",
        "P804_CREATE_REQUEST_INSERT",
        "P804_CREATE_NODE_INSERT",
        "P804_CREATE_OUTBOX_INSERT",
        "P804_CREATE_GUARD_ACTIVATE",
        "P804_CREATE_AUDIT_APPEND",
        "P804_CREATE_IDEMPOTENCY_INSERT",
        "P804_CREATE_REPOSITORY_COMMAND",
        "P804_CREATE_OUTCOME_VALIDATE",
        "P804_CREATE_COMMIT",
        "P804_CREATE_OUTCOME_PROBLEM",
        "P804_CREATE_RESPONSE_VALIDATE",
        "P804_CREATE_OUTBOX_VALIDATE",
        "P804_CREATE_API_RESPONSE",
    }
)
_WORKER_OUTCOME_DIAGNOSTIC_CODE_BY_STATE = {
    "not_claimed": "P804_WORKER_OUTCOME_NOT_CLAIMED",
    "validated_mock": "P804_WORKER_OUTCOME_VALIDATED_MOCK",
    "queued": "P804_WORKER_OUTCOME_QUEUED",
    "processing": "P804_WORKER_OUTCOME_PROCESSING",
    "partially_succeeded": "P804_WORKER_OUTCOME_PARTIALLY_SUCCEEDED",
    "succeeded": "P804_WORKER_OUTCOME_SUCCEEDED",
    "failed_retryable": "P804_WORKER_OUTCOME_FAILED_RETRYABLE",
    "failed_final": "P804_WORKER_OUTCOME_FAILED_FINAL",
    "uncertain_after_timeout": "P804_WORKER_OUTCOME_UNCERTAIN_AFTER_TIMEOUT",
    "mapping_conflict": "P804_WORKER_OUTCOME_MAPPING_CONFLICT",
}
_WORKER_OUTCOME_SHAPE_DIAGNOSTIC_CODE_BY_PREDICATE = {
    "not_mapping": "P804_WORKER_OUTCOME_NOT_MAPPING",
    "state_missing": "P804_WORKER_OUTCOME_STATE_MISSING",
    "state_type": "P804_WORKER_OUTCOME_STATE_TYPE",
    "state_unknown": "P804_WORKER_OUTCOME_STATE_UNKNOWN",
}
_WORKER_NOT_CLAIMED_PRECONDITION_CODES = frozenset(
    {
        "P804_NOT_CLAIMED_OUTBOX_READ",
        "P804_NOT_CLAIMED_OUTBOX_CONTRACT",
        "P804_NOT_CLAIMED_REQUEST_LINK",
        "P804_NOT_CLAIMED_REQUEST_READ",
        "P804_NOT_CLAIMED_REQUEST_REBUILD",
        "P804_NOT_CLAIMED_OUTBOX_BINDING",
        "P804_NOT_CLAIMED_PROFILE_ACTOR",
        "P804_NOT_CLAIMED_ACTOR_VALIDATE",
        "P804_NOT_CLAIMED_ROUTE_READ",
        "P804_NOT_CLAIMED_SERVICE_SCOPE",
        "P804_NOT_CLAIMED_OUTBOX_PENDING",
        "P804_NOT_CLAIMED_REQUEST_QUEUED",
        "P804_NOT_CLAIMED_GUARD_READ",
        "P804_NOT_CLAIMED_GUARD_ACTIVE",
    }
)
_WORKER_DOWNSTREAM_DIAGNOSTIC_CODES = frozenset(
    {
        "P804_WORKER_FIXTURE_VALIDATE",
        "P804_WORKER_REQUESTER_SESSION",
        "P804_WORKER_PROCESS_OUTBOX",
        "P804_WORKER_SESSION_RESTORE",
        "P804_WORKER_REQUEST_READ",
        "P804_WORKER_NODE_RESULTS_READ",
        "P804_WORKER_REQUEST_STATE",
        "P804_WORKER_NODE_CARDINALITY",
        "P804_WORKER_NODE_TRUTH",
        "P804_WORKER_TERMINAL_REPLAY",
        "P804_WORKER_REPLAY_SESSION_RESTORE",
        "P804_WORKER_TERMINAL_OUTCOME",
        "P804_WORKER_RECOVERABLE_QUERY",
        "P804_WORKER_RECOVERABLE_SET",
        "P804_WORKER_ADAPTER_COUNT",
        "P804_WORKER_MAPPING_COUNT",
        "P804_WORKER_FIXTURE_COMMIT",
    }
) | frozenset(_WORKER_OUTCOME_DIAGNOSTIC_CODE_BY_STATE.values()) | (
    frozenset(_WORKER_OUTCOME_SHAPE_DIAGNOSTIC_CODE_BY_PREDICATE.values())
)
_WORKER_NOT_CLAIMED_DIAGNOSTIC_CODES = (
    _WORKER_NOT_CLAIMED_PRECONDITION_CODES
    | frozenset(
        {
            _WORKER_OUTCOME_DIAGNOSTIC_CODE_BY_STATE["not_claimed"],
        }
    )
)
_WORKER_POST_DATETIME_PRECONDITION_CODES = frozenset(
    {
        "P804_NOT_CLAIMED_OUTBOX_BINDING",
        "P804_NOT_CLAIMED_PROFILE_ACTOR",
        "P804_NOT_CLAIMED_ACTOR_VALIDATE",
        "P804_NOT_CLAIMED_ROUTE_READ",
        "P804_NOT_CLAIMED_SERVICE_SCOPE",
        "P804_NOT_CLAIMED_OUTBOX_PENDING",
        "P804_NOT_CLAIMED_REQUEST_QUEUED",
        "P804_NOT_CLAIMED_GUARD_READ",
        "P804_NOT_CLAIMED_GUARD_ACTIVE",
    }
)
_WORKER_POST_DATETIME_DIAGNOSTIC_CODES = (
    _WORKER_DOWNSTREAM_DIAGNOSTIC_CODES
    | _WORKER_POST_DATETIME_PRECONDITION_CODES
)
_WORKER_POST_MANIFEST_CLOSED_CODES = frozenset(
    {
        "P804_WORKER_FIXTURE_VALIDATE",
        "P804_WORKER_REQUESTER_SESSION",
    }
)
_WORKER_POST_MANIFEST_DIAGNOSTIC_CODES = (
    _WORKER_DOWNSTREAM_DIAGNOSTIC_CODES - _WORKER_POST_MANIFEST_CLOSED_CODES
)
_WORKER_POST_COMMAND_HASH_DIAGNOSTIC_CODES = _WORKER_POST_MANIFEST_DIAGNOSTIC_CODES


def _valid_worker_downstream_trace(value: object) -> bool:
    return (
        isinstance(value, str)
        and _CREATE_DIAGNOSTIC_TRACE_PATTERN.fullmatch(value) is not None
    )


def _active_worker_diagnostic_codes() -> frozenset[str]:
    if MBOM_NOT_CLAIMED_DIAGNOSTICS_ENABLED:
        return _WORKER_NOT_CLAIMED_DIAGNOSTIC_CODES
    if MBOM_POST_DATETIME_WORKER_DIAGNOSTICS_ENABLED:
        return _WORKER_POST_DATETIME_DIAGNOSTIC_CODES
    if MBOM_POST_MANIFEST_WORKER_DIAGNOSTICS_ENABLED:
        return _WORKER_POST_MANIFEST_DIAGNOSTIC_CODES
    if MBOM_POST_COMMAND_HASH_WORKER_DIAGNOSTICS_ENABLED:
        return _WORKER_POST_COMMAND_HASH_DIAGNOSTIC_CODES
    if MBOM_WORKER_DOWNSTREAM_DIAGNOSTICS_ENABLED:
        return _WORKER_DOWNSTREAM_DIAGNOSTIC_CODES
    return frozenset()


def _worker_outcome_diagnostic_code(result: object) -> str | None:
    """Classify only the fixed worker return contract without exposing its value."""

    if not isinstance(result, Mapping):
        return _WORKER_OUTCOME_SHAPE_DIAGNOSTIC_CODE_BY_PREDICATE["not_mapping"]
    if "state" not in result:
        return _WORKER_OUTCOME_SHAPE_DIAGNOSTIC_CODE_BY_PREDICATE["state_missing"]
    state = result["state"]
    if not isinstance(state, str):
        return _WORKER_OUTCOME_SHAPE_DIAGNOSTIC_CODE_BY_PREDICATE["state_type"]
    if state == "synthetic_verified":
        return None
    return _WORKER_OUTCOME_DIAGNOSTIC_CODE_BY_STATE.get(
        state,
        _WORKER_OUTCOME_SHAPE_DIAGNOSTIC_CODE_BY_PREDICATE["state_unknown"],
    )


@contextmanager
def worker_downstream_diagnostic_step(
    code: str,
    trace_id: str,
) -> Iterator[None]:
    """Record one closed verifier stage and preserve its original failure."""

    try:
        yield
    except Exception as error:
        try:
            exception_type = type(error).__name__
            if (
                code in _active_worker_diagnostic_codes()
                and _valid_worker_downstream_trace(trace_id)
                and item_runtime._TYPE_PATTERN.fullmatch(exception_type) is not None
            ):
                from npi_core.api import record_safe_diagnostic

                record_safe_diagnostic(
                    code=code,
                    title="NPI MBOM publish worker verifier stage failed",
                    exception_type=exception_type,
                    trace_id=trace_id,
                )
        except Exception:
            # Diagnostic recording cannot replace the original verifier failure.
            pass
        raise


def _verify_not_claimed_preconditions(
    repository: object,
    *,
    outbox_id: str,
    request_id: str,
    diagnostic_trace_id: str,
) -> None:
    """Read the exact fresh claim facts without changing worker state."""

    import frappe

    from npi_integration.mbom_publish.frappe_repository import _request_value
    from npi_integration.mbom_publish.frappe_validation import (
        mbom_service_actor_scope,
        validate_mbom_service_actor,
    )
    from npi_integration.mbom_publish.worker_repository import (
        _is_mbom_outbox,
        _locked_guard,
        _project_for,
        _require_active_guard,
        _require_outbox_binding,
    )

    with worker_downstream_diagnostic_step(
        "P804_NOT_CLAIMED_OUTBOX_READ", diagnostic_trace_id
    ):
        outbox = frappe.get_doc("NPI Outbox Message", outbox_id)
    with worker_downstream_diagnostic_step(
        "P804_NOT_CLAIMED_OUTBOX_CONTRACT", diagnostic_trace_id
    ):
        require(_is_mbom_outbox(outbox), "P8-04 fresh Outbox contract drifted")
    with worker_downstream_diagnostic_step(
        "P804_NOT_CLAIMED_REQUEST_LINK", diagnostic_trace_id
    ):
        linked_request_id = str(getattr(outbox, "mbom_request_global_id", ""))
        require(
            linked_request_id == request_id
            and str(UUID(linked_request_id)) == linked_request_id,
            "P8-04 fresh Outbox request binding drifted",
        )
    with worker_downstream_diagnostic_step(
        "P804_NOT_CLAIMED_REQUEST_READ", diagnostic_trace_id
    ):
        request = frappe.get_doc("NPI MBOM Publish Request", linked_request_id)
    with worker_downstream_diagnostic_step(
        "P804_NOT_CLAIMED_REQUEST_REBUILD", diagnostic_trace_id
    ):
        value = _request_value(_project_for(request), request)
    with worker_downstream_diagnostic_step(
        "P804_NOT_CLAIMED_OUTBOX_BINDING", diagnostic_trace_id
    ):
        _require_outbox_binding(outbox, value)
    with worker_downstream_diagnostic_step(
        "P804_NOT_CLAIMED_PROFILE_ACTOR", diagnostic_trace_id
    ):
        actor = getattr(value, "service_actor_user_id", None)
        target_mode = getattr(getattr(value, "profile", None), "target_mode", None)
        require(
            getattr(target_mode, "value", None) in {"sandbox", "synthetic"}
            and isinstance(actor, str)
            and bool(actor),
            "P8-04 fresh execution actor binding drifted",
        )
    with worker_downstream_diagnostic_step(
        "P804_NOT_CLAIMED_ACTOR_VALIDATE", diagnostic_trace_id
    ):
        validate_mbom_service_actor(actor)
    with worker_downstream_diagnostic_step(
        "P804_NOT_CLAIMED_ROUTE_READ", diagnostic_trace_id
    ):
        route_reader = getattr(repository, "execution_route", None)
        require(callable(route_reader), "P8-04 execution route reader is unavailable")
        route = route_reader(UUID(outbox_id))
        require(
            route is not None
            and getattr(route, "service_actor_user_id", None) == actor,
            "P8-04 fresh execution route is unavailable",
        )
    requester_user = str(getattr(frappe.session, "user", ""))
    with worker_downstream_diagnostic_step(
        "P804_NOT_CLAIMED_SERVICE_SCOPE", diagnostic_trace_id
    ):
        with mbom_service_actor_scope(actor):
            require(
                str(getattr(frappe.session, "user", "")) == actor,
                "P8-04 service actor scope was not entered",
            )
        require(
            str(getattr(frappe.session, "user", "")) == requester_user,
            "P8-04 service actor scope was not restored",
        )
    with worker_downstream_diagnostic_step(
        "P804_NOT_CLAIMED_OUTBOX_PENDING", diagnostic_trace_id
    ):
        require(
            str(getattr(outbox, "state", "")) == "pending",
            "P8-04 fresh Outbox is not pending",
        )
    with worker_downstream_diagnostic_step(
        "P804_NOT_CLAIMED_REQUEST_QUEUED", diagnostic_trace_id
    ):
        require(
            getattr(getattr(value, "state", None), "value", None) == "queued",
            "P8-04 fresh request is not queued",
        )
    with worker_downstream_diagnostic_step(
        "P804_NOT_CLAIMED_GUARD_READ", diagnostic_trace_id
    ):
        guard = _locked_guard(route)
    with worker_downstream_diagnostic_step(
        "P804_NOT_CLAIMED_GUARD_ACTIVE", diagnostic_trace_id
    ):
        _require_active_guard(guard, value)


def mbom_publish_path(project_id: str, request_id: str | None = None) -> str:
    base = f"/api/npi/v1/projects/{project_id}/mbom-publish-requests"
    return base if request_id is None else f"{base}/{request_id}"


def mbom_publish_request(
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
        else document_runtime.query_headers(f"p804-{query_key}")
    )
    if create_diagnostic:
        require(
            method == "POST"
            and isinstance(payload, dict)
            and csrf_token is not None
            and idempotency_key == f"p8-04-synthetic-{FIXTURE_RUN_ID}"
            and re.fullmatch(
                r"/api/npi/v1/projects/[0-9a-f-]{36}/mbom-publish-requests",
                path,
            )
            is not None,
            _CREATE_FAILURE_MESSAGE,
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
        "P8-04 MBOM request identity was not echoed",
    )
    require(
        result.headers.get("Cache-Control") == "private, no-store",
        "P8-04 MBOM response cache control drifted",
    )
    return result


def assert_profile(value: object, *, available: bool) -> None:
    require(isinstance(value, dict), "P8-04 MBOM collection is invalid")
    permissions = value.get("permissions")
    if not available:
        require(
            value.get("executionProfile") is None
            and permissions == {"canView": True, "canExecute": False},
            "P8-04 default-disabled profile drifted",
        )
        return
    profile = value.get("executionProfile")
    require(
        isinstance(profile, dict)
        and profile.get("profileId") == "mbom-synthetic-disposable-v1"
        and profile.get("profileVersion") == 1
        and profile.get("targetMode") == "synthetic"
        and profile.get("environmentCode") == "disposable-test"
        and permissions == {"canView": True, "canExecute": True},
        "P8-04 disposable Synthetic profile drifted",
    )


def _assert_no_formal_target(value: object) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key in {"formalBomId", "targetVersion"}:
                require(nested is None, "P8-04 Synthetic proof claimed formal MBOM truth")
            _assert_no_formal_target(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_no_formal_target(nested)


def _canonical_uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except (AttributeError, ValueError):
        return False


def _created_synthetic_batch_failure(result: object) -> str | None:
    if getattr(result, "status", None) != 201:
        return "P804_CREATE_RESPONSE_STATUS"
    body = getattr(result, "body", None)
    request = body.get("request") if isinstance(body, Mapping) else None
    if not isinstance(request, dict):
        return "P804_CREATE_RESPONSE_SHAPE"
    if request.get("state") != "queued":
        return "P804_CREATE_REQUEST_STATE"
    if not _canonical_uuid(body.get("requestGlobalId")):
        return "P804_CREATE_REQUEST_IDENTITY"
    if not _canonical_uuid(body.get("outboxEventId")):
        return "P804_CREATE_OUTBOX_IDENTITY"
    return None


def require_created_synthetic_batch(
    result: object,
    diagnostic_cursors: dict[str, int] | None = None,
) -> None:
    diagnostic_code = _created_synthetic_batch_failure(result)
    if diagnostic_code is None:
        return
    message = _CREATE_FAILURE_MESSAGE
    trace_id = getattr(result, "trace_id", None)
    if (
        MBOM_CREATE_DIAGNOSTICS_ENABLED
        and isinstance(trace_id, str)
        and _CREATE_DIAGNOSTIC_TRACE_PATTERN.fullmatch(trace_id)
    ):
        diagnostic = item_runtime._sanitized_server_log_diagnostic(
            trace_id,
            diagnostic_cursors,
            code_prefix="P804_CREATE_",
            allowed_codes=_CREATE_SERVER_DIAGNOSTIC_CODES,
        )
        if diagnostic is not None:
            exception_type, server_code, validated_trace = diagnostic
            message = (
                f"{message} [diagnostic_code={server_code}; "
                f"exception_type={exception_type}; trace_id={validated_trace}]"
            )
    raise RuntimeError(message)


def run_disabled_probe(base_url: str, fixture_password: str) -> dict[str, object]:
    administrator = login(
        base_url,
        "Administrator",
        secret_from_environment("NPI_RUNTIME_ADMINISTRATOR_PASSWORD"),
    )
    actor = login(base_url, ACTOR_USER, fixture_password)
    context = item_runtime.released_item_context(administrator, actor, base_url)
    project_id = str(context["projectGlobalId"])
    listed = mbom_publish_request(
        actor, base_url, mbom_publish_path(project_id), query_key="disabled"
    )
    require(
        listed.status == 200 and listed.body.get("items") == [],
        "P8-04 disabled collection is not empty",
    )
    assert_profile(listed.body, available=False)
    return {"defaultDisabled": True, "projectGlobalId": project_id}


def run_fresh(base_url: str, fixture_password: str) -> dict[str, object]:
    administrator = login(
        base_url,
        "Administrator",
        secret_from_environment("NPI_RUNTIME_ADMINISTRATOR_PASSWORD"),
    )
    actor = login(base_url, ACTOR_USER, fixture_password)
    csrf = bootstrap_csrf(actor, base_url, ACTOR_USER)
    context = item_runtime.released_item_context(administrator, actor, base_url)
    project_id = str(context["projectGlobalId"])
    publish_request_id = str(context["publishRequestGlobalId"])
    worker = os.environ.get("NPI_P8_04_RUNTIME_WORKER")
    require(
        os.environ.get("NPI_P8_04_RUNTIME_PROJECT_ID") == project_id
        and os.environ.get("NPI_P8_04_RUNTIME_REQUESTER") == ACTOR_USER
        and isinstance(worker, str)
        and worker not in {"", ACTOR_USER},
        "P8-04 runtime actors are not exactly bound",
    )
    path = mbom_publish_path(project_id)
    empty = mbom_publish_request(actor, base_url, path, query_key="enabled-empty")
    require(empty.status == 200 and empty.body.get("items") == [], "P8-04 namespace is not fresh")
    assert_profile(empty.body, available=True)
    inputs = run_bench_fixture(
        "capture_inputs",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "phase5_request_id": publish_request_id,
        },
    )
    diagnostic_cursors = (
        item_runtime._replay_diagnostic_log_cursors()
        if MBOM_CREATE_DIAGNOSTICS_ENABLED
        else None
    )
    created = mbom_publish_request(
        actor,
        base_url,
        path,
        method="POST",
        payload={
            "phase5PublishRequestGlobalId": publish_request_id,
            "expectedSourceHash": inputs["sourceHash"],
            "expectedTopologyHash": inputs["topologyHash"],
            "expectedItemMappingSetHash": inputs["itemMappingSetHash"],
            "expectedMbomMappingSetHash": inputs["mbomMappingSetHash"],
            "acknowledgement": ACKNOWLEDGEMENT,
        },
        csrf_token=csrf,
        idempotency_key=f"p8-04-synthetic-{FIXTURE_RUN_ID}",
        create_diagnostic=MBOM_CREATE_DIAGNOSTICS_ENABLED,
    )
    require_created_synthetic_batch(created, diagnostic_cursors)
    request_id = created.body.get("requestGlobalId")
    outbox_id = created.body.get("outboxEventId")
    diagnostic_trace_id = getattr(created, "trace_id", None)
    require(
        _valid_worker_downstream_trace(diagnostic_trace_id),
        _WORKER_FAILURE_MESSAGE,
    )
    exercised = run_bench_fixture(
        "exercise_worker",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "request_id": request_id,
            "outbox_id": outbox_id,
            "diagnostic_trace_id": diagnostic_trace_id,
        },
    )
    require(
        exercised.get("syntheticVerified") is True
        and exercised.get("adapterCalls") == 1
        and exercised.get("mappingHeadCount") == 0
        and exercised.get("terminalReplayNotClaimed") is True
        and exercised.get("recoverableCount") == 0,
        "P8-04 worker durability proof drifted",
    )
    detail = mbom_publish_request(
        actor,
        base_url,
        mbom_publish_path(project_id, request_id),
        query_key="terminal-detail",
    )
    require(
        detail.status == 200
        and detail.body.get("request", {}).get("state") == "synthetic_verified",
        "P8-04 terminal Synthetic truth is unavailable",
    )
    _assert_no_formal_target(detail.body)
    return {
        "adapterCalls": 1,
        "mappingHeadCount": 0,
        "projectGlobalId": project_id,
        "syntheticVerified": True,
    }


def capture_inputs(
    fixture_run_id: str, project_id: str, phase5_request_id: str
) -> dict[str, object]:
    import frappe

    from npi_core.foundation.security import Principal, ProjectAccess
    from npi_integration.mbom_publish.frappe_repository import FrappeMbomPublishRepository
    from npi_integration.mbom_publish.runtime_fixture import resolve_profile

    require(
        fixture_run_id == FIXTURE_RUN_ID
        and project_id == str(UUID(project_id))
        and phase5_request_id == str(UUID(phase5_request_id)),
        "P8-04 input capture identity drifted",
    )
    project = frappe.get_doc("NPI Engineering Project", project_id)
    principal = Principal(
        user_id=ACTOR_USER,
        roles=frozenset({"NPI API User"}),
        project_access={project_id: ProjectAccess.CONTRIBUTE},
        tenant_id=str(project.tenant_id),
    )
    repository = FrappeMbomPublishRepository(
        principal=principal,
        request_id=str(uuid5(UUID(int=0), f"p804-request:{fixture_run_id}")),
        trace_id=f"trace-p804-{fixture_run_id}",
        profile_resolver=lambda tenant, project_uuid: resolve_profile(
            tenant, str(project_uuid)
        ),
    )
    profile = resolve_profile(str(project.tenant_id), project_id)
    require(profile is not None, "P8-04 disposable profile is unavailable")
    built = repository._build_request(
        project,
        UUID(phase5_request_id),
        profile,
        idempotency_key_hash="0" * 64,
        lock=False,
    )
    return {
        "sourceHash": built.source.source_hash,
        "topologyHash": built.source.topology_hash,
        "itemMappingSetHash": built.item_mapping_set_hash,
        "mbomMappingSetHash": built.mbom_mapping_set_hash,
    }


def exercise_worker(
    fixture_run_id: str,
    project_id: str,
    request_id: str,
    outbox_id: str,
    diagnostic_trace_id: str,
) -> dict[str, object]:
    import frappe

    from npi_integration.mbom_publish.runtime_fixture import synthetic_adapter_call_count
    from npi_integration.mbom_publish.worker import process_outbox_message
    from npi_integration.mbom_publish.worker_repository import FrappeMbomPublishWorkerRepository

    with worker_downstream_diagnostic_step(
        "P804_WORKER_FIXTURE_VALIDATE", diagnostic_trace_id
    ):
        require(
            _valid_worker_downstream_trace(diagnostic_trace_id)
            and fixture_run_id == FIXTURE_RUN_ID
            and project_id == str(UUID(project_id))
            and request_id == str(UUID(request_id))
            and outbox_id == str(UUID(outbox_id)),
            "P8-04 worker fixture identity drifted",
        )
    requester_user = str(getattr(frappe.session, "user", ""))
    with worker_downstream_diagnostic_step(
        "P804_WORKER_REQUESTER_SESSION", diagnostic_trace_id
    ):
        require(
            requester_user == ACTOR_USER,
            "P8-04 worker fixture did not start as the authenticated requester",
        )
    repository = FrappeMbomPublishWorkerRepository()
    _verify_not_claimed_preconditions(
        repository,
        outbox_id=outbox_id,
        request_id=request_id,
        diagnostic_trace_id=diagnostic_trace_id,
    )
    with worker_downstream_diagnostic_step(
        "P804_WORKER_PROCESS_OUTBOX", diagnostic_trace_id
    ):
        result = process_outbox_message(outbox_id)
    with worker_downstream_diagnostic_step(
        "P804_WORKER_SESSION_RESTORE", diagnostic_trace_id
    ):
        require(
            str(getattr(frappe.session, "user", "")) == requester_user,
            "P8-04 worker did not restore the requester",
        )
    with worker_downstream_diagnostic_step(
        "P804_WORKER_REQUEST_READ", diagnostic_trace_id
    ):
        request = frappe.get_doc("NPI MBOM Publish Request", request_id)
    with worker_downstream_diagnostic_step(
        "P804_WORKER_NODE_RESULTS_READ", diagnostic_trace_id
    ):
        node_results = frappe.get_all(
            "NPI MBOM Publish Node Result",
            filters={"request_global_id": request_id},
            fields=["state", "formal_bom_id", "target_version", "authority"],
        )
    outcome_diagnostic_code = _worker_outcome_diagnostic_code(result)
    if outcome_diagnostic_code is not None:
        with worker_downstream_diagnostic_step(
            outcome_diagnostic_code, diagnostic_trace_id
        ):
            raise RuntimeError("P8-04 Synthetic worker outcome drifted")
    with worker_downstream_diagnostic_step(
        "P804_WORKER_REQUEST_STATE", diagnostic_trace_id
    ):
        require(
            str(request.state) == "synthetic_verified",
            "P8-04 Synthetic request state drifted",
        )
    with worker_downstream_diagnostic_step(
        "P804_WORKER_NODE_CARDINALITY", diagnostic_trace_id
    ):
        require(bool(node_results), "P8-04 Synthetic node results are unavailable")
    with worker_downstream_diagnostic_step(
        "P804_WORKER_NODE_TRUTH", diagnostic_trace_id
    ):
        require(
            all(
            row.get("state") == "synthetic_verified"
            and row.get("authority") == "synthetic"
            and not row.get("formal_bom_id")
            and not row.get("target_version")
            for row in node_results
            ),
            "P8-04 Synthetic node truth drifted",
        )
    with worker_downstream_diagnostic_step(
        "P804_WORKER_TERMINAL_REPLAY", diagnostic_trace_id
    ):
        replay = process_outbox_message(outbox_id)
    with worker_downstream_diagnostic_step(
        "P804_WORKER_REPLAY_SESSION_RESTORE", diagnostic_trace_id
    ):
        require(
            str(getattr(frappe.session, "user", "")) == requester_user,
            "P8-04 worker did not restore the requester after terminal replay",
        )
    with worker_downstream_diagnostic_step(
        "P804_WORKER_TERMINAL_OUTCOME", diagnostic_trace_id
    ):
        require(
            replay.get("state") == "not_claimed",
            "P8-04 terminal replay outcome changed",
        )
    with worker_downstream_diagnostic_step(
        "P804_WORKER_RECOVERABLE_QUERY", diagnostic_trace_id
    ):
        recoverable = FrappeMbomPublishWorkerRepository().recoverable_outbox_event_ids(
            now=datetime.now(UTC)
        )
    with worker_downstream_diagnostic_step(
        "P804_WORKER_ADAPTER_COUNT", diagnostic_trace_id
    ):
        adapter_calls = synthetic_adapter_call_count()
        require(adapter_calls == 1, "P8-04 Synthetic adapter call count drifted")
    with worker_downstream_diagnostic_step(
        "P804_WORKER_MAPPING_COUNT", diagnostic_trace_id
    ):
        mapping_head_count = frappe.db.count(
            "NPI MBOM Mapping Head", {"project_global_id": project_id}
        )
        require(mapping_head_count == 0, "P8-04 Synthetic mapping truth drifted")
    with worker_downstream_diagnostic_step(
        "P804_WORKER_RECOVERABLE_SET", diagnostic_trace_id
    ):
        recoverable_count = sum(
            1 for value in recoverable if str(value) == outbox_id
        )
        require(recoverable_count == 0, "P8-04 terminal work became recoverable")
    return {
        "adapterCalls": adapter_calls,
        "mappingHeadCount": mapping_head_count,
        "recoverableCount": recoverable_count,
        "syntheticVerified": True,
        "terminalReplayNotClaimed": True,
    }


def _sanitized_worker_downstream_diagnostic(
    trace_id: object,
    cursors: dict[str, int] | None,
) -> tuple[str, str, str] | None:
    """Accept one logical allowlisted worker record for one exact trace."""

    return item_runtime._sanitized_server_log_diagnostic(
        trace_id,
        cursors,
        code_prefix="P804_",
        allowed_codes=_active_worker_diagnostic_codes(),
    )


def _bench_fixture_failure_message(
    method: str,
    kwargs: dict[str, object],
    cursors: dict[str, int] | None,
) -> str:
    if method != "exercise_worker" or not _active_worker_diagnostic_codes():
        return _WORKER_FAILURE_MESSAGE
    diagnostic = _sanitized_worker_downstream_diagnostic(
        kwargs.get("diagnostic_trace_id"),
        cursors,
    )
    if diagnostic is None:
        return _WORKER_FAILURE_MESSAGE
    exception_type, code, trace_id = diagnostic
    return (
        f"{_WORKER_FAILURE_MESSAGE} [diagnostic_code={code}; "
        f"exception_type={exception_type}; trace_id={trace_id}]"
    )


def run_bench_fixture(method: str, kwargs: dict[str, object]) -> dict[str, Any]:
    environment = os.environ.copy()
    current_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = str(ROOT) if not current_pythonpath else f"{ROOT}{os.pathsep}{current_pythonpath}"
    for variable in (
        "NPI_RUNTIME_ADMINISTRATOR_PASSWORD",
        "NPI_RUNTIME_FIXTURE_PASSWORD",
        "NPI_ADMINISTRATOR_PASSWORD",
        "NPI_DATABASE_ROOT_PASSWORD",
    ):
        environment.pop(variable, None)
    diagnostic_cursors = (
        item_runtime._replay_diagnostic_log_cursors()
        if method == "exercise_worker"
        and _active_worker_diagnostic_codes()
        else None
    )
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as fixture_output:
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
            stdout=fixture_output,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                _bench_fixture_failure_message(method, kwargs, diagnostic_cursors)
            )
        fixture_output.seek(0)
        lines = [line for line in fixture_output if line.strip()]
    result = json.loads(lines[-1]) if lines else None
    require(isinstance(result, dict), "P8-04 Bench fixture result is invalid")
    return result


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    import frappe

    fixtures = {"capture_inputs": capture_inputs, "exercise_worker": exercise_worker}
    require(method in fixtures, "P8-04 Bench fixture is unavailable")
    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    try:
        document_runtime._validated_runtime_site()
        frappe.set_user(ACTOR_USER if method == "exercise_worker" else "Administrator")
        result = fixtures[method](**kwargs)
        if method == "exercise_worker":
            with worker_downstream_diagnostic_step(
                "P804_WORKER_FIXTURE_COMMIT",
                str(kwargs.get("diagnostic_trace_id", "")),
            ):
                frappe.db.commit()
        else:
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
    parser.add_argument("--bench-fixture")
    parser.add_argument("--fixture-kwargs")
    arguments = parser.parse_args()
    if arguments.bench_fixture:
        require(
            arguments.base_url is None
            and arguments.fixture_kwargs is not None
            and not arguments.disabled_probe,
            "P8-04 fixture invocation drifted",
        )
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "P8-04 fixture arguments are invalid")
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return
    require(
        arguments.base_url is not None and FIXTURE_RUN_ID != "0" * 32,
        "P8-04 runtime invocation is incomplete",
    )
    base_url = validate_local_fixture_inputs(arguments.base_url, "Administrator", ACTOR_USER)
    fixture_password = secret_from_environment("NPI_RUNTIME_FIXTURE_PASSWORD")
    result = (
        run_disabled_probe(base_url, fixture_password)
        if arguments.disabled_probe
        else run_fresh(base_url, fixture_password)
    )
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
