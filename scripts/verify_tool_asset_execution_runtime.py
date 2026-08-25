from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
import urllib.parse
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator, Mapping
from uuid import UUID

import verify_document_runtime as document_runtime
import verify_item_publish_runtime as item_runtime
import verify_tooling_acceptance_runtime as tooling_runtime
import verify_tooling_revision_runtime as tooling_revision
import verify_tooling_runtime as tooling_base
from verify_frappe_runtime import login, require, secret_from_environment, validate_local_fixture_inputs
from verify_project_runtime import bootstrap_csrf

ROOT = Path(__file__).resolve().parents[1]
BENCH_PATH = ROOT / "tmp" / "frappe-bench"
SITE_NAME = document_runtime.SITE_NAME
FIXTURE_RUN_ID = document_runtime.FIXTURE_RUN_ID
ACTOR_USER = tooling_runtime.ACTOR_USER
RUNTIME_MARKER = "npi-one-tool-asset-disposable-v1"
ACKNOWLEDGEMENT = (
    "I confirm this request may create one formal ERP Asset only from the exact "
    "physical Tooling Set, separate business approval, mapping state, and execution profile."
)
TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED = False
POST_QUERY_TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED = False
TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTICS_ENABLED = False
TOOL_ASSET_CREATE_HTTP_BOUNDARY_DIAGNOSTICS_ENABLED = False
TOOL_ASSET_CREATE_PREHANDLER_DIAGNOSTICS_ENABLED = False
POST_LINK_TOOL_ASSET_CREATE_DIAGNOSTICS_ENABLED = False
POST_SOURCE_HASH_TOOL_ASSET_CREATE_DIAGNOSTICS_ENABLED = False
TOOL_ASSET_WORKER_DOWNSTREAM_DIAGNOSTICS_ENABLED = True
TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_HEADER = "X-NPI-Diagnostic-Scope"
TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_SCOPE = (
    "p805-tool-asset-create-response-v1"
)
TOOL_ASSET_CREATE_HTTP_BOUNDARY_DIAGNOSTIC_SCOPE = (
    "p805-tool-asset-create-http-boundary-v1"
)
TOOL_ASSET_CREATE_PREHANDLER_DIAGNOSTIC_SCOPE = (
    "p805-tool-asset-create-prehandler-v1"
)
TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_CODES = frozenset(
    {
        "P805_TOOL_ASSET_CREATE_ROUTES_ENABLED",
        "P805_TOOL_ASSET_CREATE_AUTHENTICATED_USER",
        "P805_TOOL_ASSET_CREATE_CSRF",
        "P805_TOOL_ASSET_CREATE_PRINCIPAL_RESOLVE",
        "P805_TOOL_ASSET_CREATE_PRINCIPAL_INTERNAL",
        "P805_TOOL_ASSET_CREATE_REQUEST_ID",
        "P805_TOOL_ASSET_CREATE_REPOSITORY_INIT",
        "P805_TOOL_ASSET_CREATE_PROJECT_ROUTE",
        "P805_TOOL_ASSET_CREATE_PROJECT_AUTHORIZE",
        "P805_TOOL_ASSET_CREATE_REQUEST_FIELDS",
        "P805_TOOL_ASSET_CREATE_INPUT_PARSE",
        "P805_TOOL_ASSET_CREATE_OPERATION_SELECT",
        "P805_TOOL_ASSET_CREATE_REPOSITORY_COMMAND",
        "P805_TOOL_ASSET_CREATE_OUTCOME_VALIDATE",
        "P805_TOOL_ASSET_CREATE_COMMIT",
        "P805_TOOL_ASSET_CREATE_PROBLEM_RAISE",
        "P805_TOOL_ASSET_CREATE_RESPONSE_SERIALIZE",
        "P805_TOOL_ASSET_CREATE_OUTBOX_VALIDATE",
        "P805_TOOL_ASSET_CREATE_DOMAIN_CALL",
        "P805_TOOL_ASSET_CREATE_PROJECT_LOCK",
        "P805_TOOL_ASSET_CREATE_RECEIPT_LOOKUP",
        "P805_TOOL_ASSET_CREATE_RECEIPT_REPLAY",
        "P805_TOOL_ASSET_CREATE_PROJECT_MUTABLE",
        "P805_TOOL_ASSET_CREATE_PROFILE_RESOLVE",
        "P805_TOOL_ASSET_CREATE_REQUEST_BUILD",
        "P805_TOOL_ASSET_CREATE_HASH_COMPARE",
        "P805_TOOL_ASSET_CREATE_TRANSACTION_SCOPE",
        "P805_TOOL_ASSET_CREATE_STREAM_GUARD",
        "P805_TOOL_ASSET_CREATE_REQUEST_INSERT",
        "P805_TOOL_ASSET_CREATE_OUTBOX_INSERT",
        "P805_TOOL_ASSET_CREATE_GUARD_ACTIVATE",
        "P805_TOOL_ASSET_CREATE_AUDIT_APPEND",
        "P805_TOOL_ASSET_CREATE_RECEIPT_INSERT",
        "P805_TOOL_ASSET_CREATE_OUTCOME_BUILD",
        "P805_TOOL_ASSET_CREATE_SOURCE",
        "P805_TOOL_ASSET_CREATE_PROFILE_BINDING",
        "P805_TOOL_ASSET_CREATE_AUTHORITY",
        "P805_TOOL_ASSET_CREATE_SANDBOX_GUARD",
        "P805_TOOL_ASSET_CREATE_MAPPING",
        "P805_TOOL_ASSET_CREATE_DOMAIN_BUILD",
    }
)
_TOOL_ASSET_CONTEXT_DIAGNOSTIC_HEADER = "X-NPI-Diagnostic-Scope"
_TOOL_ASSET_CONTEXT_DIAGNOSTIC_SCOPE = "p805-tool-asset-command-context-v1"
_TOOL_ASSET_CONTEXT_PARENT_CODES = frozenset(
    {
        "P805_TOOL_ASSET_CONTEXT_HTTP_AUTHORIZATION_CLASS",
        "P805_TOOL_ASSET_CONTEXT_HTTP_NOT_FOUND_CLASS",
        "P805_TOOL_ASSET_CONTEXT_HTTP_CLIENT_CLASS",
        "P805_TOOL_ASSET_CONTEXT_HTTP_SERVER_CLASS",
        "P805_TOOL_ASSET_CONTEXT_HTTP_OTHER_CLASS",
        "P805_TOOL_ASSET_CONTEXT_ITEMS",
        "P805_TOOL_ASSET_CONTEXT_CREATE_SHAPE",
        "P805_TOOL_ASSET_CONTEXT_TARGET_MODE",
    }
)
_TOOL_ASSET_CONTEXT_SERVER_CODES = frozenset(
    {
        "P805_TOOL_ASSET_CONTEXT_ROUTES_ENABLED",
        "P805_TOOL_ASSET_CONTEXT_AUTHENTICATED_USER",
        "P805_TOOL_ASSET_CONTEXT_PRINCIPAL_RESOLVE",
        "P805_TOOL_ASSET_CONTEXT_PRINCIPAL_INTERNAL",
        "P805_TOOL_ASSET_CONTEXT_REQUEST_ID",
        "P805_TOOL_ASSET_CONTEXT_REPOSITORY_INIT",
        "P805_TOOL_ASSET_CONTEXT_PROJECT_ROUTE",
        "P805_TOOL_ASSET_CONTEXT_PROJECT_AUTHORIZE",
        "P805_TOOL_ASSET_CONTEXT_REQUEST_FIELDS",
        "P805_TOOL_ASSET_CONTEXT_MASTER_ROUTE",
        "P805_TOOL_ASSET_CONTEXT_SET_ROUTE",
        "P805_TOOL_ASSET_CONTEXT_QUERY_PARSE",
        "P805_TOOL_ASSET_CONTEXT_REPOSITORY_LIST",
        "P805_TOOL_ASSET_CONTEXT_PROJECT_RESOLVE",
        "P805_TOOL_ASSET_CONTEXT_MASTER_RESOLVE",
        "P805_TOOL_ASSET_CONTEXT_SET_RESOLVE",
        "P805_TOOL_ASSET_CONTEXT_PROFILE_RESOLVE",
        "P805_TOOL_ASSET_CONTEXT_CREATE_SOURCE",
        "P805_TOOL_ASSET_CONTEXT_CREATE_PROFILE_BINDING",
        "P805_TOOL_ASSET_CONTEXT_CREATE_AUTHORITY",
        "P805_TOOL_ASSET_CONTEXT_CREATE_SANDBOX_GUARD",
        "P805_TOOL_ASSET_CONTEXT_CREATE_MAPPING",
        "P805_TOOL_ASSET_CONTEXT_CREATE_REQUEST_BUILD",
        "P805_TOOL_ASSET_CONTEXT_CREATE_PROJECT",
        "P805_TOOL_ASSET_CONTEXT_REQUEST_ROWS",
        "P805_TOOL_ASSET_CONTEXT_PERMISSIONS",
        "P805_TOOL_ASSET_CONTEXT_PROFILE_RESPONSE",
        "P805_TOOL_ASSET_CONTEXT_ITEM_PROJECT",
        "P805_TOOL_ASSET_CONTEXT_RESPONSE_BUILD",
        "P805_TOOL_ASSET_CONTEXT_RESPONSE_AVAILABLE",
        "P805_TOOL_ASSET_CONTEXT_RESPONSE_SERIALIZE",
    }
)
_TOOL_ASSET_CONTEXT_FAILURE = "P8-05 disposable command context is unavailable"
_TOOL_ASSET_CREATE_RESPONSE_PARENT_CODES = frozenset(
    {
        "P805_TOOL_ASSET_CREATE_HTTP_AUTHORIZATION_CLASS",
        "P805_TOOL_ASSET_CREATE_HTTP_NOT_FOUND_CLASS",
        "P805_TOOL_ASSET_CREATE_HTTP_CLIENT_CLASS",
        "P805_TOOL_ASSET_CREATE_HTTP_SERVER_CLASS",
        "P805_TOOL_ASSET_CREATE_HTTP_OTHER_CLASS",
        "P805_TOOL_ASSET_CREATE_BODY_SHAPE",
        "P805_TOOL_ASSET_CREATE_REQUEST_SHAPE",
        "P805_TOOL_ASSET_CREATE_REQUEST_STATE",
        "P805_TOOL_ASSET_CREATE_REQUEST_ID",
        "P805_TOOL_ASSET_CREATE_OUTBOX_ID",
    }
)
_TOOL_ASSET_CREATE_RESPONSE_FAILURE = (
    "P8-05 Synthetic command did not create one queued request"
)
_TOOL_ASSET_WORKER_FAILURE = "P8-05 Bench fixture failed"
_TOOL_ASSET_WORKER_STAGE_CODES = frozenset(
    {
        "P805_TOOL_ASSET_WORKER_FIXTURE_VALIDATE",
        "P805_TOOL_ASSET_WORKER_REQUESTER_SESSION",
        "P805_TOOL_ASSET_WORKER_PROCESS_OUTBOX",
        "P805_TOOL_ASSET_WORKER_SESSION_RESTORE",
        "P805_TOOL_ASSET_WORKER_REQUEST_READ",
        "P805_TOOL_ASSET_WORKER_FIELD_RESULTS_READ",
        "P805_TOOL_ASSET_WORKER_REQUEST_STATE",
        "P805_TOOL_ASSET_WORKER_FIELD_CARDINALITY",
        "P805_TOOL_ASSET_WORKER_FIELD_TRUTH",
        "P805_TOOL_ASSET_WORKER_TERMINAL_REPLAY",
        "P805_TOOL_ASSET_WORKER_REPLAY_SESSION_RESTORE",
        "P805_TOOL_ASSET_WORKER_TERMINAL_OUTCOME",
        "P805_TOOL_ASSET_WORKER_RECOVERABLE_QUERY",
        "P805_TOOL_ASSET_WORKER_RECOVERABLE_SET",
        "P805_TOOL_ASSET_WORKER_ADAPTER_COUNT",
        "P805_TOOL_ASSET_WORKER_MAPPING_COUNT",
        "P805_TOOL_ASSET_WORKER_FIXTURE_COMMIT",
    }
)
_TOOL_ASSET_WORKER_OUTCOME_CODE_BY_STATE = {
    "not_claimed": "P805_TOOL_ASSET_WORKER_OUTCOME_NOT_CLAIMED",
    "validated_mock": "P805_TOOL_ASSET_WORKER_OUTCOME_VALIDATED_MOCK",
    "queued": "P805_TOOL_ASSET_WORKER_OUTCOME_QUEUED",
    "processing": "P805_TOOL_ASSET_WORKER_OUTCOME_PROCESSING",
    "partially_succeeded": (
        "P805_TOOL_ASSET_WORKER_OUTCOME_PARTIALLY_SUCCEEDED"
    ),
    "succeeded": "P805_TOOL_ASSET_WORKER_OUTCOME_SUCCEEDED",
    "failed_retryable": "P805_TOOL_ASSET_WORKER_OUTCOME_FAILED_RETRYABLE",
    "failed_final": "P805_TOOL_ASSET_WORKER_OUTCOME_FAILED_FINAL",
    "uncertain_after_timeout": (
        "P805_TOOL_ASSET_WORKER_OUTCOME_UNCERTAIN_AFTER_TIMEOUT"
    ),
    "mapping_conflict": "P805_TOOL_ASSET_WORKER_OUTCOME_MAPPING_CONFLICT",
}
_TOOL_ASSET_WORKER_OUTCOME_SHAPE_CODES = {
    "not_mapping": "P805_TOOL_ASSET_WORKER_OUTCOME_NOT_MAPPING",
    "state_missing": "P805_TOOL_ASSET_WORKER_OUTCOME_STATE_MISSING",
    "state_type": "P805_TOOL_ASSET_WORKER_OUTCOME_STATE_TYPE",
    "state_unknown": "P805_TOOL_ASSET_WORKER_OUTCOME_STATE_UNKNOWN",
}
_TOOL_ASSET_WORKER_DIAGNOSTIC_CODES = (
    _TOOL_ASSET_WORKER_STAGE_CODES
    | frozenset(_TOOL_ASSET_WORKER_OUTCOME_CODE_BY_STATE.values())
    | frozenset(_TOOL_ASSET_WORKER_OUTCOME_SHAPE_CODES.values())
)
_TRACE_PATTERN = re.compile(r"^trace-[a-f0-9]{32}$")
_EXECUTION_STATE_DOCTYPES = (
    "NPI Tool Asset Request",
    "NPI Tool Asset Command Idempotency",
    "NPI Tool Asset Stream Guard",
    "NPI Tool Asset Attempt",
    "NPI Tool Asset Result",
    "NPI Tool Asset Field Result",
    "NPI Tool Asset Mapping Observation",
    "NPI Tool Asset Mapping Head",
    "NPI Outbox Message",
    "NPI Audit Event",
)
_DISPOSABLE_MASTER_TITLE = f"P8-05 disposable Asset tool {FIXTURE_RUN_ID[:16]}"
_DISPOSABLE_REQUIREMENT_TITLE = (
    f"P8-05 disposable Asset intake {FIXTURE_RUN_ID[:16]}"
)
_DISPOSABLE_PHYSICAL_SERIAL = f"P8-05-ASSET-{FIXTURE_RUN_ID[:16]}"


def _post_query_command_context_diagnostics_enabled() -> bool:
    """Activate only the independent post-query diagnostic cycle."""

    return (
        POST_QUERY_TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED is True
        and TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED is False
    )


def _tool_asset_create_response_diagnostics_enabled() -> bool:
    """Activate only the independent synthetic create-response cycle."""

    return (
        TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTICS_ENABLED is True
        and TOOL_ASSET_CREATE_HTTP_BOUNDARY_DIAGNOSTICS_ENABLED is False
        and TOOL_ASSET_CREATE_PREHANDLER_DIAGNOSTICS_ENABLED is False
        and POST_LINK_TOOL_ASSET_CREATE_DIAGNOSTICS_ENABLED is False
        and POST_SOURCE_HASH_TOOL_ASSET_CREATE_DIAGNOSTICS_ENABLED is False
        and TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED is False
        and POST_QUERY_TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED is False
    )


def _tool_asset_create_http_boundary_diagnostics_enabled() -> bool:
    """Activate only the independent synthetic create HTTP-boundary cycle."""

    return (
        TOOL_ASSET_CREATE_HTTP_BOUNDARY_DIAGNOSTICS_ENABLED is True
        and TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTICS_ENABLED is False
        and TOOL_ASSET_CREATE_PREHANDLER_DIAGNOSTICS_ENABLED is False
        and POST_LINK_TOOL_ASSET_CREATE_DIAGNOSTICS_ENABLED is False
        and POST_SOURCE_HASH_TOOL_ASSET_CREATE_DIAGNOSTICS_ENABLED is False
        and TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED is False
        and POST_QUERY_TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED is False
    )


def _tool_asset_create_prehandler_diagnostics_enabled() -> bool:
    """Activate only the independent synthetic create pre-handler cycle."""

    return (
        TOOL_ASSET_CREATE_PREHANDLER_DIAGNOSTICS_ENABLED is True
        and TOOL_ASSET_CREATE_HTTP_BOUNDARY_DIAGNOSTICS_ENABLED is False
        and TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTICS_ENABLED is False
        and POST_LINK_TOOL_ASSET_CREATE_DIAGNOSTICS_ENABLED is False
        and POST_SOURCE_HASH_TOOL_ASSET_CREATE_DIAGNOSTICS_ENABLED is False
        and TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED is False
        and POST_QUERY_TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED is False
    )


def _post_link_tool_asset_create_diagnostics_enabled() -> bool:
    """Activate only the independent post-reciprocal-Link create cycle."""

    return (
        POST_LINK_TOOL_ASSET_CREATE_DIAGNOSTICS_ENABLED is True
        and TOOL_ASSET_CREATE_PREHANDLER_DIAGNOSTICS_ENABLED is False
        and TOOL_ASSET_CREATE_HTTP_BOUNDARY_DIAGNOSTICS_ENABLED is False
        and TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTICS_ENABLED is False
        and POST_SOURCE_HASH_TOOL_ASSET_CREATE_DIAGNOSTICS_ENABLED is False
        and TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED is False
        and POST_QUERY_TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED is False
    )


def _post_source_hash_tool_asset_create_diagnostics_enabled() -> bool:
    """Activate only the independent post-source-hash create cycle."""

    return (
        POST_SOURCE_HASH_TOOL_ASSET_CREATE_DIAGNOSTICS_ENABLED is True
        and POST_LINK_TOOL_ASSET_CREATE_DIAGNOSTICS_ENABLED is False
        and TOOL_ASSET_CREATE_PREHANDLER_DIAGNOSTICS_ENABLED is False
        and TOOL_ASSET_CREATE_HTTP_BOUNDARY_DIAGNOSTICS_ENABLED is False
        and TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTICS_ENABLED is False
        and TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED is False
        and POST_QUERY_TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED is False
    )


def _tool_asset_worker_downstream_diagnostics_enabled() -> bool:
    """Activate only the independent Tool Asset worker downstream cycle."""

    return (
        TOOL_ASSET_WORKER_DOWNSTREAM_DIAGNOSTICS_ENABLED is True
        and POST_SOURCE_HASH_TOOL_ASSET_CREATE_DIAGNOSTICS_ENABLED is False
        and POST_LINK_TOOL_ASSET_CREATE_DIAGNOSTICS_ENABLED is False
        and TOOL_ASSET_CREATE_PREHANDLER_DIAGNOSTICS_ENABLED is False
        and TOOL_ASSET_CREATE_HTTP_BOUNDARY_DIAGNOSTICS_ENABLED is False
        and TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTICS_ENABLED is False
        and TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED is False
        and POST_QUERY_TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED is False
    )


def _active_tool_asset_worker_diagnostic_codes() -> frozenset[str]:
    return (
        _TOOL_ASSET_WORKER_DIAGNOSTIC_CODES
        if _tool_asset_worker_downstream_diagnostics_enabled()
        else frozenset()
    )


def _valid_tool_asset_worker_trace(value: object) -> bool:
    return isinstance(value, str) and _TRACE_PATTERN.fullmatch(value) is not None


def _tool_asset_worker_outcome_diagnostic_code(result: object) -> str | None:
    """Classify the fixed worker state contract without exposing its value."""

    if not isinstance(result, Mapping):
        return _TOOL_ASSET_WORKER_OUTCOME_SHAPE_CODES["not_mapping"]
    if "state" not in result:
        return _TOOL_ASSET_WORKER_OUTCOME_SHAPE_CODES["state_missing"]
    state = result["state"]
    if not isinstance(state, str):
        return _TOOL_ASSET_WORKER_OUTCOME_SHAPE_CODES["state_type"]
    if state == "synthetic_verified":
        return None
    return _TOOL_ASSET_WORKER_OUTCOME_CODE_BY_STATE.get(
        state,
        _TOOL_ASSET_WORKER_OUTCOME_SHAPE_CODES["state_unknown"],
    )


@contextmanager
def tool_asset_worker_diagnostic_step(
    code: str,
    trace_id: str,
) -> Iterator[None]:
    """Record one closed verifier stage and re-raise the original failure."""

    try:
        yield
    except Exception as error:
        try:
            exception_type = type(error).__name__
            if (
                code in _active_tool_asset_worker_diagnostic_codes()
                and _valid_tool_asset_worker_trace(trace_id)
                and item_runtime._TYPE_PATTERN.fullmatch(exception_type) is not None
            ):
                from npi_core.api import record_safe_diagnostic

                record_safe_diagnostic(
                    code=code,
                    title="NPI Tool Asset worker verifier stage failed",
                    exception_type=exception_type,
                    trace_id=trace_id,
                )
        except Exception:
            pass
        raise


def execution_path(project_id: str, master_id: str, set_id: str, suffix: str = "") -> str:
    return f"/api/npi/v1/projects/{project_id}/tooling/{master_id}/sets/{set_id}/asset-execution-requests{suffix}"


def execution_request(
    opener,
    base_url,
    path,
    *,
    method="GET",
    payload=None,
    csrf_token=None,
    idempotency_key=None,
    query_key="query",
    diagnostic_scope=None,
):
    headers = (
        document_runtime.command_headers(csrf_token, idempotency_key)
        if idempotency_key
        else document_runtime.query_headers(f"p805-{query_key}")
    )
    if diagnostic_scope is not None:
        parsed = urllib.parse.urlsplit(path)
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if diagnostic_scope == _TOOL_ASSET_CONTEXT_DIAGNOSTIC_SCOPE:
            require(
                method == "GET"
                and payload is None
                and csrf_token is None
                and idempotency_key is None
                and query_key == "enabled"
                and re.fullmatch(
                    r"/api/npi/v1/projects/[^/]+/tooling/[^/]+/sets/[^/]+/asset-execution-requests",
                    parsed.path,
                )
                is not None
                and len(query) == 1
                and query[0][0] == "acceptanceRevisionGlobalId"
                and bool(query[0][1]),
                _TOOL_ASSET_CONTEXT_FAILURE,
            )
            headers[_TOOL_ASSET_CONTEXT_DIAGNOSTIC_HEADER] = diagnostic_scope
        else:
            require(
                diagnostic_scope
                == TOOL_ASSET_CREATE_PREHANDLER_DIAGNOSTIC_SCOPE
                and method == "POST"
                and isinstance(payload, dict)
                and set(payload)
                == {
                    "acceptanceRevisionGlobalId",
                    "expectedSourceHash",
                    "expectedApprovalHash",
                    "expectedMappingExpectationHash",
                    "expectedProfileSnapshotHash",
                    "acknowledgement",
                }
                and isinstance(csrf_token, str)
                and bool(csrf_token)
                and isinstance(idempotency_key, str)
                and bool(idempotency_key)
                and query_key == "query"
                and _exact_create_execution_path(parsed.path)
                and query == [],
                _TOOL_ASSET_CREATE_RESPONSE_FAILURE,
            )
            headers[TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_HEADER] = (
                diagnostic_scope
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
        "P8-05 request identity was not echoed",
    )
    require(
        result.headers.get("Cache-Control") == "private, no-store",
        "P8-05 response cache control drifted",
    )
    return result


def _command_context_failure_message(result, cursors) -> str | None:
    if result.status != 200:
        code = _http_status_diagnostic_code(result.status)
    else:
        body = result.body if isinstance(result.body, dict) else {}
        contexts = body.get("commandContexts")
        create = (
            contexts.get("create_tool_asset")
            if isinstance(contexts, dict)
            else None
        )
        profile = body.get("executionProfile")
        if body.get("items") != []:
            code = "P805_TOOL_ASSET_CONTEXT_ITEMS"
        elif not isinstance(create, dict):
            code = "P805_TOOL_ASSET_CONTEXT_CREATE_SHAPE"
        elif (
            not isinstance(profile, dict)
            or profile.get("targetMode") != "synthetic"
        ):
            code = "P805_TOOL_ASSET_CONTEXT_TARGET_MODE"
        else:
            return None
    if not _post_query_command_context_diagnostics_enabled():
        return _TOOL_ASSET_CONTEXT_FAILURE
    trace_id = getattr(result, "trace_id", None)
    if (
        code not in _TOOL_ASSET_CONTEXT_PARENT_CODES
        or not isinstance(trace_id, str)
        or _TRACE_PATTERN.fullmatch(trace_id) is None
    ):
        return _TOOL_ASSET_CONTEXT_FAILURE
    if code.startswith("P805_TOOL_ASSET_CONTEXT_HTTP_") or code == (
        "P805_TOOL_ASSET_CONTEXT_CREATE_SHAPE"
    ):
        diagnostic = item_runtime._sanitized_server_log_diagnostic(
            trace_id,
            cursors,
            code_prefix="P805_TOOL_ASSET_CONTEXT_",
            allowed_codes=_TOOL_ASSET_CONTEXT_SERVER_CODES,
        )
        if diagnostic is not None:
            exception_type, server_code, validated_trace = diagnostic
            return (
                "P8-05 disposable command context is unavailable "
                f"[diagnostic_code={server_code}; "
                f"exception_type={exception_type}; trace_id={validated_trace}]"
            )
    return (
        "P8-05 disposable command context is unavailable "
        f"[diagnostic_code={code}; exception_type=RuntimeError; "
        f"trace_id={trace_id}]"
    )


def _http_status_diagnostic_code(status: object) -> str:
    """Classify a non-success response without exposing its actual status."""

    if status in {401, 403}:
        return "P805_TOOL_ASSET_CONTEXT_HTTP_AUTHORIZATION_CLASS"
    if status == 404:
        return "P805_TOOL_ASSET_CONTEXT_HTTP_NOT_FOUND_CLASS"
    if isinstance(status, int) and 400 <= status < 500:
        return "P805_TOOL_ASSET_CONTEXT_HTTP_CLIENT_CLASS"
    if isinstance(status, int) and 500 <= status < 600:
        return "P805_TOOL_ASSET_CONTEXT_HTTP_SERVER_CLASS"
    return "P805_TOOL_ASSET_CONTEXT_HTTP_OTHER_CLASS"


def _tool_asset_create_response_failure_message(result, cursors) -> str | None:
    body = result.body if isinstance(result.body, dict) else None
    request = body.get("request") if isinstance(body, dict) else None
    if result.status != 201:
        code = _tool_asset_create_http_status_diagnostic_code(result.status)
    elif body is None:
        code = "P805_TOOL_ASSET_CREATE_BODY_SHAPE"
    elif not isinstance(request, dict):
        code = "P805_TOOL_ASSET_CREATE_REQUEST_SHAPE"
    elif request.get("state") != "queued":
        code = "P805_TOOL_ASSET_CREATE_REQUEST_STATE"
    elif not _canonical_uuid(body.get("requestGlobalId")):
        code = "P805_TOOL_ASSET_CREATE_REQUEST_ID"
    elif not _canonical_uuid(body.get("outboxEventId")):
        code = "P805_TOOL_ASSET_CREATE_OUTBOX_ID"
    else:
        return None
    if not _post_source_hash_tool_asset_create_diagnostics_enabled():
        return _TOOL_ASSET_CREATE_RESPONSE_FAILURE
    trace_id = getattr(result, "trace_id", None)
    if (
        code not in _TOOL_ASSET_CREATE_RESPONSE_PARENT_CODES
        or not isinstance(trace_id, str)
        or _TRACE_PATTERN.fullmatch(trace_id) is None
    ):
        return _TOOL_ASSET_CREATE_RESPONSE_FAILURE
    diagnostic = item_runtime._sanitized_server_log_diagnostic(
        trace_id,
        cursors,
        code_prefix="P805_TOOL_ASSET_CREATE_",
        allowed_codes=TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_CODES,
    )
    if diagnostic is not None:
        exception_type, server_code, validated_trace = diagnostic
        return (
            "P8-05 Synthetic command did not create one queued request "
            f"[diagnostic_code={server_code}; "
            f"exception_type={exception_type}; trace_id={validated_trace}]"
        )
    return (
        "P8-05 Synthetic command did not create one queued request "
        f"[diagnostic_code={code}; exception_type=RuntimeError; "
        f"trace_id={trace_id}]"
    )


def _tool_asset_create_http_status_diagnostic_code(status: object) -> str:
    """Classify a create failure without exposing its actual HTTP status."""

    if status in {401, 403}:
        return "P805_TOOL_ASSET_CREATE_HTTP_AUTHORIZATION_CLASS"
    if status == 404:
        return "P805_TOOL_ASSET_CREATE_HTTP_NOT_FOUND_CLASS"
    if isinstance(status, int) and 400 <= status < 500:
        return "P805_TOOL_ASSET_CREATE_HTTP_CLIENT_CLASS"
    if isinstance(status, int) and 500 <= status < 600:
        return "P805_TOOL_ASSET_CREATE_HTTP_SERVER_CLASS"
    return "P805_TOOL_ASSET_CREATE_HTTP_OTHER_CLASS"


def _canonical_uuid(value: object) -> bool:
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except (AttributeError, TypeError, ValueError):
        return False


def _exact_create_execution_path(path: object) -> bool:
    if not isinstance(path, str):
        return False
    match = re.fullmatch(
        r"/api/npi/v1/projects/([^/]+)/tooling/([^/]+)/sets/([^/]+)/asset-execution-requests:create",
        path,
    )
    return match is not None and all(_canonical_uuid(value) for value in match.groups())


def _retained_context(administrator, base_url):
    context, _first, second, _legacy = tooling_runtime.replay_context(
        administrator,
        base_url,
        expected_erp_projection_mode=(
            tooling_runtime.ExpectedErpProjectionMode.AVAILABLE
        ),
        expected_asset_projection_mode=(
            tooling_runtime.ExpectedAssetProjectionMode.AVAILABLE
        ),
    )
    return context, second


def _hash(value: object) -> str:
    import hashlib

    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _expected_synthetic_profile(project_id: str) -> dict[str, object]:
    policy_hash = _hash({"authority": "synthetic", "formalAssetIds": False})
    snapshot = {
        "profileId": "tool-asset-disposable-synthetic-v1",
        "profileVersion": 1,
        "tenantId": document_runtime.TENANT_ID,
        "projectGlobalId": project_id,
        "targetMode": "synthetic",
        "environmentCode": "testing",
        "requesterUserIds": [ACTOR_USER],
        "serviceActorUserId": os.environ.get("NPI_TOOL_ASSET_WORKER_USER"),
        "projectionPolicyId": "tool-asset-synthetic-projection-v1",
        "projectionPolicyVersion": 1,
        "projectionPolicyHash": policy_hash,
        "allowedOperations": ["create_tool_asset", "update_tool_asset"],
        "adapterResolver": (
            "npi_integration.tool_asset_request.runtime_fixture.synthetic_adapter"
        ),
        "baseUrl": None,
        "allowedHostnames": [],
        "responseAuthentication": None,
        "connectTimeoutSeconds": None,
        "readTimeoutSeconds": None,
        "nonProductionAttested": False,
        "syntheticTestOnly": True,
        "followRedirects": False,
        "disposableRuntimeMarker": True,
    }
    return {
        "profileId": snapshot["profileId"],
        "profileVersion": snapshot["profileVersion"],
        "targetMode": snapshot["targetMode"],
        "environmentCode": snapshot["environmentCode"],
        "projectionPolicyId": snapshot["projectionPolicyId"],
        "projectionPolicyVersion": snapshot["projectionPolicyVersion"],
        "projectionPolicyHash": policy_hash,
        "snapshotHash": _hash(snapshot),
    }


def _execution_state_snapshot() -> dict[str, int]:
    return run_bench_fixture(
        "execution_state_snapshot",
        {"fixture_run_id": FIXTURE_RUN_ID},
    )


def _assert_collection(
    result,
    *,
    project_id: str,
    master_id: str,
    set_id: str,
    command_contexts: object,
) -> dict[str, object]:
    require(
        result.status == 200
        and isinstance(result.body, dict)
        and result.body.get("projectGlobalId") == project_id
        and result.body.get("toolingMasterGlobalId") == master_id
        and result.body.get("toolingSetGlobalId") == set_id
        and result.body.get("items") == []
        and result.body.get("executionProfile")
        == _expected_synthetic_profile(project_id)
        and result.body.get("commandContexts") == command_contexts,
        _TOOL_ASSET_CONTEXT_FAILURE,
    )
    return result.body


def _create_disposable_execution_context(
    administrator,
    base_url: str,
    csrf_token: str,
    retained: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    project_id = str(retained["projectId"])
    retained_engineering_revision_id = tooling_revision.require_uuid(
        retained.get("engineeringRevisionId"),
        "P8-05 retained Engineering Revision",
    )
    part_context = tooling_revision.dedicated_part_context(
        administrator,
        base_url,
        project_id,
    )
    require(
        isinstance(part_context, tuple) and len(part_context) == 3,
        "P8-05 disposable Engineering Part context drifted",
    )
    _part_id, part_revision_value, _applicability_id = part_context
    part_revision_id = tooling_revision.require_uuid(
        part_revision_value,
        "P8-05 disposable Engineering Part Revision",
    )
    require(
        part_revision_id != retained_engineering_revision_id,
        "P8-05 disposable Engineering Part Revision reused Tooling Revision truth",
    )
    master_result = tooling_base.command(
        administrator,
        base_url,
        csrf_token,
        f"/api/npi/v1/projects/{project_id}/tooling-masters",
        {"title": _DISPOSABLE_MASTER_TITLE},
        f"p8-05-{FIXTURE_RUN_ID}-asset-disposable-master",
    )
    master_workspace = tooling_base.assert_workspace(
        master_result,
        project_id,
        expected_revision_mode=(
            tooling_base.ExpectedToolingRevisionCapabilityMode.AVAILABLE
        ),
    )
    master = tooling_base.exact_single(
        [
            value
            for value in master_workspace["masters"]
            if value.get("title") == _DISPOSABLE_MASTER_TITLE
        ],
        "P8-05 disposable Tooling Master",
    )
    master_id = str(master.get("globalId"))
    require(
        str(UUID(master_id)) == master_id
        and master_id != str(retained["masterId"])
        and master.get("originatingProjectGlobalId") == project_id
        and isinstance(master.get("snapshotHash"), str)
        and len(str(master["snapshotHash"])) == 64,
        "P8-05 disposable Tooling Master drifted",
    )

    requirement_result = tooling_base.command(
        administrator,
        base_url,
        csrf_token,
        f"/api/npi/v1/projects/{project_id}/tooling-requirements",
        {
            "kind": "customer_owned_intake",
            "title": _DISPOSABLE_REQUIREMENT_TITLE,
            "reason": "Create one isolated physical Set for disposable Asset proof.",
            "targetPartRevisionGlobalId": part_revision_id,
            "targetDate": "2027-03-15",
        },
        f"p8-05-{FIXTURE_RUN_ID}-asset-disposable-requirement",
    )
    requirement_workspace = tooling_base.assert_workspace(
        requirement_result,
        project_id,
        expected_revision_mode=(
            tooling_base.ExpectedToolingRevisionCapabilityMode.AVAILABLE
        ),
    )
    requirement = tooling_base.exact_single(
        [
            value
            for value in requirement_workspace["requirements"]
            if value.get("title") == _DISPOSABLE_REQUIREMENT_TITLE
            and value.get("kind") == "customer_owned_intake"
        ],
        "P8-05 disposable Tooling Requirement",
    )

    applicability_result = tooling_base.command(
        administrator,
        base_url,
        csrf_token,
        f"/api/npi/v1/projects/{project_id}/tooling-applicabilities",
        tooling_base.applicability_payload(
            master_id,
            part_revision_id,
            effective_from="2026-08-01",
            effective_to=None,
        ),
        f"p8-05-{FIXTURE_RUN_ID}-asset-disposable-applicability",
    )
    applicability = tooling_base.exact_single(
        [
            value
            for value in tooling_base.assert_workspace(
                applicability_result,
                project_id,
                expected_revision_mode=(
                    tooling_base.ExpectedToolingRevisionCapabilityMode.AVAILABLE
                ),
            )["applicability"]
            if value.get("toolingMasterGlobalId") == master_id
            and value.get("part", {}).get("globalId")
            == part_revision_id
        ],
        "P8-05 disposable Tooling Applicability",
    )
    applicability_id = tooling_revision.require_uuid(
        applicability.get("globalId"),
        "P8-05 disposable Tooling Applicability",
    )
    _project, _master, _part, _revisions, _set, model_reference = (
        tooling_revision.project_context(administrator, base_url)
    )
    revision_result = tooling_revision.command(
        administrator,
        base_url,
        csrf_token,
        tooling_revision.revision_path(project_id, master_id),
        tooling_revision.revision_payload(applicability_id, 1, model_reference),
        f"p8-05-{FIXTURE_RUN_ID}-asset-disposable-revision",
    )
    revision = tooling_revision.assert_revision_item(
        revision_result.body.get("revision"),
        master_id=master_id,
        revision_number=1,
    )
    revision_id = str(revision["globalId"])

    set_result = tooling_base.command(
        administrator,
        base_url,
        csrf_token,
        tooling_base.tooling_set_path(project_id, master_id),
        tooling_base.tooling_set_payload(
            str(requirement["globalId"]),
            _DISPOSABLE_PHYSICAL_SERIAL,
            customer_owned=True,
        ),
        f"p8-05-{FIXTURE_RUN_ID}-asset-disposable-set",
    )
    set_collection = tooling_base.assert_tooling_set_collection(
        set_result,
        project_id=project_id,
        master_id=master_id,
        expected_count=1,
    )
    tooling_set = tooling_base.exact_single(
        [
            value
            for value in set_collection["items"]
            if value.get("physicalSerial") == _DISPOSABLE_PHYSICAL_SERIAL
        ],
        "P8-05 disposable physical Tooling Set",
    )
    set_id = str(tooling_set["globalId"])
    require(
        set_id != str(retained["toolingSetId"])
        and tooling_set.get("requirementKind") == "customer_owned_intake",
        "P8-05 disposable physical Tooling Set drifted",
    )
    binding_result = tooling_revision.command(
        administrator,
        base_url,
        csrf_token,
        tooling_revision.binding_path(project_id, master_id, set_id),
        tooling_revision.binding_payload(revision_id),
        f"p8-05-{FIXTURE_RUN_ID}-asset-disposable-binding",
    )
    tooling_revision.assert_set_binding(
        binding_result,
        project_id=project_id,
        master_id=master_id,
        set_id=set_id,
        revision_id=revision_id,
    )
    binding = binding_result.body["toolingSet"]["sourceRevision"]

    disposable = dict(retained)
    disposable.update(
        {
            "masterId": master_id,
            "masterSnapshotHash": str(master["snapshotHash"]),
            "toolingSetId": set_id,
            "toolingSetSnapshotHash": str(tooling_set["snapshotHash"]),
            "requirementKind": "customer_owned_intake",
            "physicalSerial": _DISPOSABLE_PHYSICAL_SERIAL,
            "bindingId": str(binding["globalId"]),
            "bindingSnapshotHash": str(binding["snapshotHash"]),
            "revisionId": revision_id,
            "revisionNumber": 1,
            "revisionLabel": "R1",
            "revisionSnapshotHash": str(revision["snapshotHash"]),
        }
    )
    acceptance_result = tooling_runtime.command(
        administrator,
        base_url,
        csrf_token,
        tooling_runtime.acceptance_command_path(project_id, master_id),
        tooling_runtime.acceptance_payload(disposable, version=1),
        f"p8-05-{FIXTURE_RUN_ID}-asset-disposable-acceptance",
    )
    acceptance = tooling_runtime.assert_acceptance_revision(
        acceptance_result.body.get("acceptanceEvidence"),
        context=disposable,
        version=1,
        predecessor_value=None,
    )
    return disposable, acceptance


def _assert_no_formal_target(value: object) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key in {"formalAssetId", "targetVersion"}:
                require(nested is None, "P8-05 Synthetic proof claimed formal Asset truth")
            _assert_no_formal_target(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_no_formal_target(nested)


def run_disabled_probe(base_url: str, fixture_password: str) -> dict[str, object]:
    administrator = login(base_url, "Administrator", secret_from_environment("NPI_RUNTIME_ADMINISTRATOR_PASSWORD"))
    actor = login(base_url, ACTOR_USER, fixture_password)
    context, _acceptance = _retained_context(administrator, base_url)
    result = execution_request(actor, base_url, execution_path(str(context["projectId"]), str(context["masterId"]), str(context["toolingSetId"])), query_key="disabled")
    require(result.status == 200 and result.body.get("items") == [] and result.body.get("executionProfile") is None and result.body.get("commandContexts") is None, "P8-05 default-disabled collection drifted")
    return {"defaultDisabled": True, "networkContactCount": 0}


def run_fresh(base_url: str, fixture_password: str) -> dict[str, object]:
    administrator = login(base_url, "Administrator", secret_from_environment("NPI_RUNTIME_ADMINISTRATOR_PASSWORD"))
    actor = login(base_url, ACTOR_USER, fixture_password)
    administrator_csrf = bootstrap_csrf(
        administrator,
        base_url,
        "Administrator",
    )
    csrf = bootstrap_csrf(actor, base_url, ACTOR_USER)
    retained, retained_acceptance = _retained_context(administrator, base_url)
    project_id, retained_master_id, retained_set_id = (
        str(retained[name]) for name in ("projectId", "masterId", "toolingSetId")
    )
    require(os.environ.get("NPI_TOOL_ASSET_RUNTIME_PROJECT_ID") == project_id and os.environ.get("NPI_TOOL_ASSET_REQUESTER_USER") == ACTOR_USER and os.environ.get("NPI_TOOL_ASSET_WORKER_USER") not in {None, "", ACTOR_USER}, "P8-05 runtime actors are not exactly bound")
    retained_path = execution_path(project_id, retained_master_id, retained_set_id)
    retained_query = urllib.parse.urlencode(
        {"acceptanceRevisionGlobalId": retained_acceptance.get("globalId")}
    )
    before_retained_query = _execution_state_snapshot()
    retained_listed = execution_request(
        actor,
        base_url,
        f"{retained_path}?{retained_query}",
        method="GET",
        query_key="enabled-retained-mapped",
    )
    _assert_collection(
        retained_listed,
        project_id=project_id,
        master_id=retained_master_id,
        set_id=retained_set_id,
        command_contexts=None,
    )
    require(
        _execution_state_snapshot() == before_retained_query,
        "P8-05 retained mapped collection query changed execution truth",
    )

    context, acceptance = _create_disposable_execution_context(
        administrator,
        base_url,
        administrator_csrf,
        retained,
    )
    master_id = str(context["masterId"])
    set_id = str(context["toolingSetId"])
    require(
        master_id != retained_master_id and set_id != retained_set_id,
        "P8-05 disposable command context reused retained mapped truth",
    )
    path = execution_path(project_id, master_id, set_id)
    query = urllib.parse.urlencode(
        {"acceptanceRevisionGlobalId": acceptance.get("globalId")}
    )
    listed = execution_request(
        actor,
        base_url,
        f"{path}?{query}",
        method="GET",
        query_key="enabled-disposable-unmapped",
    )
    body = listed.body if isinstance(listed.body, dict) else {}
    contexts = body.get("commandContexts")
    require(
        isinstance(contexts, dict)
        and set(contexts) == {"create_tool_asset"}
        and isinstance(contexts.get("create_tool_asset"), dict),
        _TOOL_ASSET_CONTEXT_FAILURE,
    )
    _assert_collection(
        listed,
        project_id=project_id,
        master_id=master_id,
        set_id=set_id,
        command_contexts=contexts,
    )
    create = contexts["create_tool_asset"]
    source = create.get("source")
    require(isinstance(source, dict) and source.get("acceptanceRevisionGlobalId") == acceptance.get("globalId"), "P8-05 retained acceptance binding drifted")
    create_cursors = (
        item_runtime._replay_diagnostic_log_cursors()
        if _post_source_hash_tool_asset_create_diagnostics_enabled()
        else None
    )
    created = execution_request(
        actor,
        base_url,
        execution_path(project_id, master_id, set_id, ":create"),
        method="POST",
        csrf_token=csrf,
        idempotency_key=f"p8-05-synthetic-{FIXTURE_RUN_ID}",
        payload={
            "acceptanceRevisionGlobalId": source["acceptanceRevisionGlobalId"],
            "expectedSourceHash": create["expectedSourceHash"],
            "expectedApprovalHash": create["expectedApprovalHash"],
            "expectedMappingExpectationHash": create[
                "expectedMappingExpectationHash"
            ],
            "expectedProfileSnapshotHash": create[
                "expectedProfileSnapshotHash"
            ],
            "acknowledgement": ACKNOWLEDGEMENT,
        },
        diagnostic_scope=(
            TOOL_ASSET_CREATE_PREHANDLER_DIAGNOSTIC_SCOPE
            if _post_source_hash_tool_asset_create_diagnostics_enabled()
            else None
        ),
    )
    create_failure = _tool_asset_create_response_failure_message(
        created,
        create_cursors,
    )
    require(create_failure is None, create_failure or _TOOL_ASSET_CREATE_RESPONSE_FAILURE)
    request_id = str(created.body["requestGlobalId"])
    outbox_id = str(created.body["outboxEventId"])
    exercised = run_bench_fixture(
        "exercise_worker",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "request_id": request_id,
            "outbox_id": outbox_id,
            "diagnostic_trace_id": created.trace_id,
        },
    )
    require(exercised == {"adapterCalls":1, "fieldResultCount":5, "mappingHeadCount":0, "recoverableCount":0, "syntheticVerified":True, "terminalReplayNotClaimed":True}, "P8-05 worker durability proof drifted")
    detail = execution_request(actor, base_url, execution_path(project_id, master_id, set_id, f"/{request_id}"), query_key="terminal")
    require(detail.status == 200 and detail.body.get("request", {}).get("state") == "synthetic_verified", "P8-05 terminal Synthetic truth is unavailable")
    _assert_no_formal_target(detail.body)
    return {"adapterCalls":1, "fieldResultCount":5, "mappingHeadCount":0, "networkContactCount":0, "syntheticVerified":True}


def execution_state_snapshot(fixture_run_id: str) -> dict[str, int]:
    import frappe

    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "P8-05 execution snapshot fixture identity drifted",
    )
    return {
        doctype: int(frappe.db.count(doctype))
        for doctype in _EXECUTION_STATE_DOCTYPES
    }


def exercise_worker(
    fixture_run_id: str,
    project_id: str,
    request_id: str,
    outbox_id: str,
    diagnostic_trace_id: str,
) -> dict[str, object]:
    import frappe
    from npi_integration.tool_asset_request.runtime_fixture import synthetic_adapter_call_count
    from npi_integration.tool_asset_request.worker import process_outbox_message
    from npi_integration.tool_asset_request.worker_repository import FrappeToolAssetWorkerRepository

    with tool_asset_worker_diagnostic_step(
        "P805_TOOL_ASSET_WORKER_FIXTURE_VALIDATE",
        diagnostic_trace_id,
    ):
        require(
            _valid_tool_asset_worker_trace(diagnostic_trace_id)
            and fixture_run_id == FIXTURE_RUN_ID
            and all(
                str(UUID(value)) == value
                for value in (project_id, request_id, outbox_id)
            ),
            "P8-05 worker fixture identity drifted",
        )
    requester_user = str(getattr(frappe.session, "user", ""))
    with tool_asset_worker_diagnostic_step(
        "P805_TOOL_ASSET_WORKER_REQUESTER_SESSION",
        diagnostic_trace_id,
    ):
        require(
            requester_user == ACTOR_USER,
            "P8-05 worker fixture did not start as the authenticated requester",
        )
    with tool_asset_worker_diagnostic_step(
        "P805_TOOL_ASSET_WORKER_PROCESS_OUTBOX",
        diagnostic_trace_id,
    ):
        result = process_outbox_message(outbox_id)
    with tool_asset_worker_diagnostic_step(
        "P805_TOOL_ASSET_WORKER_SESSION_RESTORE",
        diagnostic_trace_id,
    ):
        require(
            str(getattr(frappe.session, "user", "")) == requester_user,
            "P8-05 worker did not restore the requester",
        )
    with tool_asset_worker_diagnostic_step(
        "P805_TOOL_ASSET_WORKER_REQUEST_READ",
        diagnostic_trace_id,
    ):
        request = frappe.get_doc("NPI Tool Asset Request", request_id)
    with tool_asset_worker_diagnostic_step(
        "P805_TOOL_ASSET_WORKER_FIELD_RESULTS_READ",
        diagnostic_trace_id,
    ):
        fields = frappe.get_all(
            "NPI Tool Asset Field Result",
            filters={"request_global_id": request_id},
            fields=["state", "authority"],
        )
    outcome_code = _tool_asset_worker_outcome_diagnostic_code(result)
    if outcome_code is not None:
        with tool_asset_worker_diagnostic_step(
            outcome_code,
            diagnostic_trace_id,
        ):
            raise RuntimeError("P8-05 Synthetic worker outcome drifted")
    with tool_asset_worker_diagnostic_step(
        "P805_TOOL_ASSET_WORKER_REQUEST_STATE",
        diagnostic_trace_id,
    ):
        require(
            str(request.execution_state) == "synthetic_verified",
            "P8-05 Synthetic request state drifted",
        )
    with tool_asset_worker_diagnostic_step(
        "P805_TOOL_ASSET_WORKER_FIELD_CARDINALITY",
        diagnostic_trace_id,
    ):
        require(
            len(fields) == 5,
            "P8-05 Synthetic field result cardinality drifted",
        )
    with tool_asset_worker_diagnostic_step(
        "P805_TOOL_ASSET_WORKER_FIELD_TRUTH",
        diagnostic_trace_id,
    ):
        require(
            all(
                row.get("state") == "synthetic_verified"
                and row.get("authority") == "synthetic"
                for row in fields
            ),
            "P8-05 Synthetic field truth drifted",
        )
    with tool_asset_worker_diagnostic_step(
        "P805_TOOL_ASSET_WORKER_TERMINAL_REPLAY",
        diagnostic_trace_id,
    ):
        replay = process_outbox_message(outbox_id)
    with tool_asset_worker_diagnostic_step(
        "P805_TOOL_ASSET_WORKER_REPLAY_SESSION_RESTORE",
        diagnostic_trace_id,
    ):
        require(
            str(getattr(frappe.session, "user", "")) == requester_user,
            "P8-05 worker did not restore the requester after terminal replay",
        )
    with tool_asset_worker_diagnostic_step(
        "P805_TOOL_ASSET_WORKER_TERMINAL_OUTCOME",
        diagnostic_trace_id,
    ):
        require(
            replay.get("state") == "not_claimed",
            "P8-05 terminal replay outcome changed",
        )
    with tool_asset_worker_diagnostic_step(
        "P805_TOOL_ASSET_WORKER_RECOVERABLE_QUERY",
        diagnostic_trace_id,
    ):
        recoverable = FrappeToolAssetWorkerRepository().recoverable_outbox_event_ids(
            now=datetime.now(UTC)
        )
    with tool_asset_worker_diagnostic_step(
        "P805_TOOL_ASSET_WORKER_ADAPTER_COUNT",
        diagnostic_trace_id,
    ):
        adapter_calls = synthetic_adapter_call_count()
        require(
            adapter_calls == 1,
            "P8-05 Synthetic adapter call count drifted",
        )
    with tool_asset_worker_diagnostic_step(
        "P805_TOOL_ASSET_WORKER_MAPPING_COUNT",
        diagnostic_trace_id,
    ):
        mapping_head_count = frappe.db.count(
            "NPI Tool Asset Mapping Head",
            {"project_global_id": project_id},
        )
        require(
            mapping_head_count == 0,
            "P8-05 Synthetic mapping truth drifted",
        )
    with tool_asset_worker_diagnostic_step(
        "P805_TOOL_ASSET_WORKER_RECOVERABLE_SET",
        diagnostic_trace_id,
    ):
        recoverable_count = sum(
            1 for value in recoverable if str(value) == outbox_id
        )
        require(
            recoverable_count == 0,
            "P8-05 terminal work became recoverable",
        )
    return {
        "adapterCalls": adapter_calls,
        "fieldResultCount": len(fields),
        "mappingHeadCount": mapping_head_count,
        "recoverableCount": recoverable_count,
        "syntheticVerified": True,
        "terminalReplayNotClaimed": True,
    }


def _sanitized_tool_asset_worker_diagnostic(
    trace_id: object,
    cursors: dict[str, int] | None,
) -> tuple[str, str, str] | None:
    """Accept one logical allowlisted worker record for one exact trace."""

    return item_runtime._sanitized_server_log_diagnostic(
        trace_id,
        cursors,
        code_prefix="P805_TOOL_ASSET_WORKER_",
        allowed_codes=_active_tool_asset_worker_diagnostic_codes(),
    )


def _tool_asset_worker_fixture_failure_message(
    method: str,
    kwargs: dict[str, object],
    cursors: dict[str, int] | None,
) -> str:
    if method != "exercise_worker" or not _active_tool_asset_worker_diagnostic_codes():
        return _TOOL_ASSET_WORKER_FAILURE
    diagnostic = _sanitized_tool_asset_worker_diagnostic(
        kwargs.get("diagnostic_trace_id"),
        cursors,
    )
    if diagnostic is None:
        return _TOOL_ASSET_WORKER_FAILURE
    exception_type, code, trace_id = diagnostic
    return (
        f"{_TOOL_ASSET_WORKER_FAILURE} [diagnostic_code={code}; "
        f"exception_type={exception_type}; trace_id={trace_id}]"
    )


def run_bench_fixture(method: str, kwargs: dict[str, object]) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT) + (os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else "")
    for variable in ("NPI_RUNTIME_ADMINISTRATOR_PASSWORD", "NPI_RUNTIME_FIXTURE_PASSWORD", "NPI_ADMINISTRATOR_PASSWORD", "NPI_DATABASE_ROOT_PASSWORD"):
        environment.pop(variable, None)
    diagnostic_cursors = (
        item_runtime._replay_diagnostic_log_cursors()
        if method == "exercise_worker"
        and _active_tool_asset_worker_diagnostic_codes()
        else None
    )
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as output:
        completed = subprocess.run([str(BENCH_PATH / "env/bin/python"), str(Path(__file__).resolve()), "--bench-fixture", method, "--fixture-kwargs", json.dumps(kwargs, separators=(",", ":"), sort_keys=True)], cwd=BENCH_PATH / "sites", env=environment, check=False, stdout=output, stderr=subprocess.DEVNULL, text=True)
        if completed.returncode != 0:
            raise RuntimeError(
                _tool_asset_worker_fixture_failure_message(
                    method,
                    kwargs,
                    diagnostic_cursors,
                )
            )
        output.seek(0)
        lines = [line for line in output if line.strip()]
    result = json.loads(lines[-1]) if lines else None
    require(isinstance(result, dict), "P8-05 Bench fixture result is invalid")
    return result


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    import frappe
    require(
        method in {"execution_state_snapshot", "exercise_worker"},
        "P8-05 Bench fixture is unavailable",
    )
    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    try:
        document_runtime._validated_runtime_site()
        if method == "execution_state_snapshot":
            frappe.set_user("Administrator")
            result = execution_state_snapshot(**kwargs)
        else:
            frappe.set_user(ACTOR_USER)
            result = exercise_worker(**kwargs)
        if method == "exercise_worker":
            with tool_asset_worker_diagnostic_step(
                "P805_TOOL_ASSET_WORKER_FIXTURE_COMMIT",
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
        require(arguments.base_url is None and arguments.fixture_kwargs is not None and not arguments.disabled_probe, "P8-05 fixture invocation drifted")
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "P8-05 fixture arguments are invalid")
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return
    require(arguments.base_url is not None and FIXTURE_RUN_ID != "0"*32, "P8-05 runtime invocation is incomplete")
    base_url = validate_local_fixture_inputs(arguments.base_url, "Administrator", ACTOR_USER)
    password = secret_from_environment("NPI_RUNTIME_FIXTURE_PASSWORD")
    result = run_disabled_probe(base_url, password) if arguments.disabled_probe else run_fresh(base_url, password)
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
