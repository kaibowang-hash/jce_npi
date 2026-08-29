from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator
from uuid import UUID, uuid5

import verify_document_runtime as document_runtime
import verify_item_publish_runtime as item_runtime
import verify_publish_request_runtime as publish_runtime
import verify_readiness_runtime as readiness_runtime
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
ACTION_ACTOR_USER = readiness_runtime.ACTOR_USER
RUNTIME_MARKER = "npi-one-integration-operations-disposable-v1"
DEFAULT_DISABLED_DIAGNOSTICS_ENABLED = False
FRESH_COMBINED_DIAGNOSTICS_ENABLED = False
COLLECTION_SHAPE_DIAGNOSTICS_ENABLED = False
COLLECTION_RESPONSE_DIAGNOSTICS_ENABLED = False
POST_MOCK_COMBINED_DIAGNOSTICS_ENABLED = False
COLLECTION_SERVER_DIAGNOSTICS_ENABLED = False
POST_UUID_COLLECTION_SERVER_DIAGNOSTICS_ENABLED = False
POST_UUID_COLLECTION_MEMBERSHIP_DIAGNOSTICS_ENABLED = False
POST_MEMBERSHIP_COMBINED_DIAGNOSTICS_ENABLED = False
POST_OPERATION_ID_COMBINED_DIAGNOSTICS_ENABLED = False
UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTICS_ENABLED = False
UNCERTAIN_REPLAY_ACTION_DIAGNOSTICS_ENABLED = False
UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTICS_ENABLED = False
POST_ACTION_ACTOR_COMBINED_DIAGNOSTICS_ENABLED = True
_DEFAULT_DISABLED_DIAGNOSTIC_CODES = frozenset(
    {
        "P807_DEFAULT_DISABLED_LOGIN",
        "P807_DEFAULT_DISABLED_HTTP",
        "P807_DEFAULT_DISABLED_REQUEST_ID",
        "P807_DEFAULT_DISABLED_CACHE_CONTROL",
        "P807_DEFAULT_DISABLED_RESPONSE_SAFE",
        "P807_DEFAULT_DISABLED_STATUS",
        "P807_DEFAULT_DISABLED_BODY_STATUS",
        "P807_DEFAULT_DISABLED_CODE",
        "P807_DEFAULT_DISABLED_MEDIA_TYPE",
        "P807_DEFAULT_DISABLED_TRACE",
        "P807_DEFAULT_DISABLED_ENVELOPE",
        "P807_DEFAULT_DISABLED_CONTRACT",
    }
)
FRESH_RUNTIME_DIAGNOSTIC_CODES = (
    "P807_FRESH_INPUTS",
    "P807_FRESH_PROJECT_ID",
    "P807_FRESH_SECRET",
    "P807_FRESH_ENVIRONMENT",
    "P807_FRESH_LOGIN",
    "P807_FRESH_CSRF",
    "P807_FRESH_SEED",
    "P807_FRESH_SEED_SHAPE",
    "P807_FRESH_COLLECTION_HTTP",
    "P807_FRESH_COLLECTION_SHAPE",
    "P807_FRESH_COLLECTION_KINDS",
    "P807_FRESH_RETRYABLE_ITEM",
    "P807_FRESH_UNCERTAIN_ITEM",
    "P807_FRESH_CLASSIFICATION",
    "P807_FRESH_DLQ_HTTP",
    "P807_FRESH_DLQ_SHAPE",
    "P807_FRESH_DLQ_CARDINALITY",
    "P807_FRESH_PAGE_ONE_HTTP",
    "P807_FRESH_PAGE_ONE_SHAPE",
    "P807_FRESH_PAGE_ONE_CURSOR",
    "P807_FRESH_PAGE_TWO_HTTP",
    "P807_FRESH_PAGE_TWO_SHAPE",
    "P807_FRESH_PAGE_DISJOINT",
    "P807_FRESH_FOREIGN_HTTP",
    "P807_FRESH_FOREIGN_CONTRACT",
    "P807_FRESH_RETRYABLE_DETAIL_HTTP",
    "P807_FRESH_RETRYABLE_DETAIL_SHAPE",
    "P807_FRESH_UNCERTAIN_DETAIL_HTTP",
    "P807_FRESH_UNCERTAIN_DETAIL_SHAPE",
    "P807_FRESH_HISTORY",
    "P807_FRESH_SNAPSHOT_BEFORE",
    "P807_FRESH_UNCERTAIN_REPLAY_HTTP",
    "P807_FRESH_UNCERTAIN_REPLAY_CONTRACT",
    "P807_FRESH_SNAPSHOT_AFTER",
    "P807_FRESH_UNCERTAIN_UNCHANGED",
    "P807_FRESH_RECONCILIATION_HTTP",
    "P807_FRESH_RECONCILIATION_SHAPE",
    "P807_FRESH_OBSERVATION",
    "P807_FRESH_OBSERVATION_SHAPE",
    "P807_FRESH_REPLAY_HTTP",
    "P807_FRESH_REPLAY_SHAPE",
    "P807_FRESH_STALE_HTTP",
    "P807_FRESH_STALE_CONTRACT",
    "P807_FRESH_COUNTS",
    "P807_FRESH_COUNTS_SHAPE",
)
FRESH_FIXTURE_DIAGNOSTIC_CODES = (
    "P807_FIXTURE_ARGUMENTS",
    "P807_FIXTURE_INIT",
    "P807_FIXTURE_CONNECT",
    "P807_FIXTURE_SEED_CALL",
    "P807_FIXTURE_SNAPSHOT_CALL",
    "P807_FIXTURE_OBSERVATION_CALL",
    "P807_FIXTURE_COUNTS_CALL",
    "P807_FIXTURE_COMMIT",
    "P807_FIXTURE_RESPONSE",
    "P807_FIXTURE_DESTROY",
    "P807_SEED_VALIDATE",
    "P807_SEED_SET_REQUESTER",
    "P807_SEED_SOURCE_QUERY",
    "P807_SEED_SOURCE_CARDINALITY",
    "P807_SEED_SOURCE_VALUE",
    "P807_SEED_SOURCE_BUILD",
    "P807_SEED_REQUEST_BUILD",
    "P807_SEED_PROJECT_LOCK",
    "P807_SEED_STREAM_GUARD",
    "P807_SEED_REQUEST_INSERT",
    "P807_SEED_OUTBOX_INSERT",
    "P807_SEED_STREAM_ACTIVE",
    "P807_SEED_REQUEST_COMMIT",
    "P807_SEED_WORKER_REPOSITORY",
    "P807_SEED_CLAIM",
    "P807_SEED_CLAIM_COMMIT",
    "P807_SEED_FAILURE_CLASSIFY",
    "P807_SEED_RESULT_SEAL",
    "P807_SEED_RESULT_COMMIT",
    "P807_SEED_SESSION_RESTORE",
    "P807_SNAPSHOT_VALIDATE",
    "P807_SNAPSHOT_OPERATION_ID",
    "P807_SNAPSHOT_REQUEST",
    "P807_SNAPSHOT_ATTEMPTS",
    "P807_SNAPSHOT_RESULTS",
    "P807_SNAPSHOT_ACTIONS",
    "P807_SNAPSHOT_DIGEST",
    "P807_OBSERVATION_VALIDATE",
    "P807_OBSERVATION_IDENTITIES",
    "P807_OBSERVATION_REFERENCE",
    "P807_OBSERVATION_ATTEMPT",
    "P807_OBSERVATION_VALUE",
    "P807_OBSERVATION_SET_WORKER",
    "P807_OBSERVATION_DOCUMENT",
    "P807_OBSERVATION_INSERT",
    "P807_OBSERVATION_COMMIT",
    "P807_OBSERVATION_RESTORE",
    "P807_COUNTS_VALIDATE",
    "P807_COUNTS_IDENTITIES",
    "P807_COUNTS_ACTIONS",
    "P807_COUNTS_OBSERVATIONS",
    "P807_COUNTS_RESULT",
)
COLLECTION_SHAPE_DIAGNOSTIC_CODES = (
    "P807_COLLECTION_STATUS",
    "P807_COLLECTION_PROJECT",
    "P807_COLLECTION_PERMISSIONS",
    "P807_COLLECTION_ITEMS",
    "P807_COLLECTION_ITEM_SHAPES",
)
COLLECTION_RESPONSE_DIAGNOSTIC_CODES = (
    "P807_COLLECTION_STATUS_INVALID",
    "P807_COLLECTION_STATUS_INFORMATIONAL",
    "P807_COLLECTION_STATUS_OTHER_SUCCESS",
    "P807_COLLECTION_STATUS_REDIRECTION",
    "P807_COLLECTION_STATUS_CLIENT_ERROR",
    "P807_COLLECTION_STATUS_SERVER_ERROR",
    "P807_COLLECTION_STATUS_OUT_OF_RANGE",
)
UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTIC_CODES = (
    "P807_UNCERTAIN_REPLAY_STATUS_INVALID",
    "P807_UNCERTAIN_REPLAY_STATUS_INFORMATIONAL",
    "P807_UNCERTAIN_REPLAY_STATUS_SUCCESS",
    "P807_UNCERTAIN_REPLAY_STATUS_REDIRECTION",
    "P807_UNCERTAIN_REPLAY_STATUS_OTHER_CLIENT_ERROR",
    "P807_UNCERTAIN_REPLAY_STATUS_SERVER_ERROR",
    "P807_UNCERTAIN_REPLAY_STATUS_OUT_OF_RANGE",
    "P807_UNCERTAIN_REPLAY_BODY_STATUS",
    "P807_UNCERTAIN_REPLAY_CODE",
    "P807_UNCERTAIN_REPLAY_MEDIA_TYPE",
    "P807_UNCERTAIN_REPLAY_TRACE",
    "P807_UNCERTAIN_REPLAY_ENVELOPE",
)
UNCERTAIN_REPLAY_ACTION_SERVER_DIAGNOSTIC_CODES = (
    "P807_ACTION_API_DOMAIN_CALL",
    "P807_ACTION_API_CSRF",
    "P807_ACTION_API_FIELDS",
    "P807_ACTION_API_CONTEXT",
    "P807_ACTION_API_REPOSITORY",
    "P807_ACTION_API_OUTCOME",
    "P807_ACTION_API_RESPONSE",
    "P807_ACTION_API_COMMIT",
    "P807_ACTION_API_HEADERS",
    "P807_ACTION_REPOSITORY_PROJECT",
    "P807_ACTION_REPOSITORY_REQUEST",
    "P807_ACTION_REPOSITORY_REPLAY_LOOKUP",
    "P807_ACTION_REPOSITORY_MUTABLE",
    "P807_ACTION_REPOSITORY_OPERATION",
    "P807_ACTION_REPOSITORY_EXPECTATION",
    "P807_ACTION_REPOSITORY_REQUEUE",
    "P807_ACTION_REPOSITORY_RESPONSE",
    "P807_ACTION_REPOSITORY_RECEIPT",
    "P807_ACTION_REPOSITORY_RECEIPT_INSERT",
    "P807_ACTION_REPOSITORY_AUDIT",
    "P807_ACTION_REPOSITORY_ENQUEUE",
    "P807_ACTION_REPOSITORY_OUTCOME",
)
UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTIC_CODES = (
    "P807_ACTION_ENTRY_OPERATION_KIND",
    "P807_ACTION_ENTRY_ACTION_KIND",
    "P807_ACTION_ENTRY_REQUEST_FIELDS",
    "P807_ACTION_ENTRY_METHOD",
    "P807_ACTION_ENTRY_QUERY",
    "P807_ACTION_ENTRY_ROUTE",
    "P807_ACTION_ENTRY_FORM",
    "P807_ACTION_ENTRY_COMMAND",
    "P807_ACTION_ENTRY_EXPECTED_RAW_STATE",
    "P807_ACTION_ENTRY_EXPECTED_VERSION",
    "P807_ACTION_ENTRY_RUNTIME_SHAPE",
)
COLLECTION_MEMBERSHIP_DIAGNOSTIC_CODES = (
    "P807_FRESH_COLLECTION_INBOUND_ABSENT",
    "P807_FRESH_COLLECTION_ITEM_KIND",
    "P807_FRESH_COLLECTION_MBOM_KIND",
    "P807_FRESH_COLLECTION_TOOL_CREATE_KIND",
)
_REQUIRED_COLLECTION_KINDS = (
    "publish_item",
    "publish_mbom",
    "create_tool_asset",
)
_EXPECTED_COLLECTION_MEMBERSHIP = (
    (COLLECTION_MEMBERSHIP_DIAGNOSTIC_CODES[0], "receive_project_submission", False),
    (COLLECTION_MEMBERSHIP_DIAGNOSTIC_CODES[1], "publish_item", True),
    (COLLECTION_MEMBERSHIP_DIAGNOSTIC_CODES[2], "publish_mbom", True),
    (COLLECTION_MEMBERSHIP_DIAGNOSTIC_CODES[3], "create_tool_asset", True),
)
COLLECTION_SERVER_DIAGNOSTIC_CODES = (
    "P807_COLLECTION_API_DOMAIN_CALL",
    "P807_COLLECTION_API_FIELDS",
    "P807_COLLECTION_API_CONTEXT",
    "P807_COLLECTION_API_ARGUMENTS",
    "P807_COLLECTION_API_REPOSITORY",
    "P807_COLLECTION_API_OUTCOME",
    "P807_COLLECTION_API_RESPONSE",
    "P807_COLLECTION_REPOSITORY_PROJECT",
    "P807_COLLECTION_REPOSITORY_CURSOR",
    "P807_COLLECTION_REPOSITORY_VALUES",
    "P807_COLLECTION_REPOSITORY_FILTER",
    "P807_COLLECTION_REPOSITORY_ITEM",
    "P807_COLLECTION_REPOSITORY_SORT",
    "P807_COLLECTION_REPOSITORY_PAGE",
    "P807_COLLECTION_REPOSITORY_CURSOR_ENCODE",
    "P807_COLLECTION_REPOSITORY_RESPONSE",
    "P807_COLLECTION_INBOUND_QUERY",
    "P807_COLLECTION_ITEM_QUERY",
    "P807_COLLECTION_MBOM_QUERY",
    "P807_COLLECTION_TOOL_CREATE_QUERY",
    "P807_COLLECTION_TOOL_UPDATE_QUERY",
    "P807_COLLECTION_INBOUND_ROW",
    "P807_COLLECTION_ITEM_ROW",
    "P807_COLLECTION_MBOM_ROW",
    "P807_COLLECTION_TOOL_CREATE_ROW",
    "P807_COLLECTION_TOOL_UPDATE_ROW",
    "P807_COLLECTION_INBOUND_VALUE",
    "P807_COLLECTION_ITEM_VALUE",
    "P807_COLLECTION_MBOM_VALUE",
    "P807_COLLECTION_TOOL_CREATE_VALUE",
    "P807_COLLECTION_TOOL_UPDATE_VALUE",
    "P807_COLLECTION_INBOUND_TIME",
    "P807_COLLECTION_ITEM_TIME",
    "P807_COLLECTION_MBOM_TIME",
    "P807_COLLECTION_TOOL_CREATE_TIME",
    "P807_COLLECTION_TOOL_UPDATE_TIME",
    "P807_COLLECTION_INBOUND_BOUNDARIES",
    "P807_COLLECTION_ITEM_BOUNDARIES",
    "P807_COLLECTION_MBOM_BOUNDARIES",
    "P807_COLLECTION_TOOL_CREATE_BOUNDARIES",
    "P807_COLLECTION_TOOL_UPDATE_BOUNDARIES",
    "P807_COLLECTION_INBOUND_SHAPE",
    "P807_COLLECTION_ITEM_SHAPE",
    "P807_COLLECTION_MBOM_SHAPE",
    "P807_COLLECTION_TOOL_CREATE_SHAPE",
    "P807_COLLECTION_TOOL_UPDATE_SHAPE",
)
_COLLECTION_SERVER_DIAGNOSTIC_HEADER = "X-NPI-P807-Collection-Diagnostic"
_COLLECTION_SERVER_DIAGNOSTIC_SCOPE = (
    "p8-07-integration-operations-collection-v1"
)
_ACTION_SERVER_DIAGNOSTIC_HEADER = "X-NPI-P807-Action-Diagnostic"
_ACTION_SERVER_DIAGNOSTIC_SCOPE = (
    "p8-07-integration-operations-uncertain-replay-v1"
)
_FRESH_FIXTURE_CALL_CODES = {
    "append_observation": "P807_FIXTURE_OBSERVATION_CALL",
    "seed_retryable": "P807_FIXTURE_SEED_CALL",
    "snapshot": "P807_FIXTURE_SNAPSHOT_CALL",
    "verify_counts": "P807_FIXTURE_COUNTS_CALL",
}
_DIAGNOSTIC_SCOPE_ENV = "NPI_P807_FRESH_DIAGNOSTIC_SCOPE"
_DIAGNOSTIC_TRACE_ENV = "NPI_P807_FRESH_DIAGNOSTIC_TRACE"
_DIAGNOSTIC_PATH_ENV = "NPI_P807_FRESH_DIAGNOSTIC_PATH"
_DIAGNOSTIC_SCOPE = "p8-07-integration-operations-fresh-v1"
_DIAGNOSTIC_FILE_NAME = "p8-07-integration-operations-runtime-diagnostic.json"
_DIAGNOSTIC_RECORD_KEYS = frozenset({"code", "exceptionType", "traceId"})
_DIAGNOSTIC_RECORD_LIMIT = 4096
_TRACE_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_DIAGNOSTIC_TRACE_PATTERN = re.compile(r"^trace-[a-f0-9]{32}$")
_TYPE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,127}$")
_DIAGNOSTIC_NAMESPACE = UUID("07b4939b-f3e5-4bd1-a892-4c23619ea807")
_DIAGNOSTIC_STATE: ContextVar[dict[str, object] | None] = ContextVar(
    "p807_integration_operations_runtime_diagnostic_state",
    default=None,
)
_FORBIDDEN_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "credential",
        "credentials",
        "password",
        "payload",
        "rawbody",
        "rawpayload",
        "requestbody",
        "responsebody",
        "secret",
        "targetrequest",
        "targetresponse",
        "token",
    }
)
_OPERATION_SLUG = {
    "receive_project_submission": "receive-project-submissions",
    "publish_item": "item-publishes",
    "publish_mbom": "mbom-publishes",
    "create_tool_asset": "tool-asset-creates",
    "update_tool_asset": "tool-asset-updates",
}


def _fixture_uuid(label: str) -> UUID:
    raw = bytearray(hashlib.sha256(f"{FIXTURE_RUN_ID}:{label}".encode()).digest()[:16])
    raw[6] = (raw[6] & 0x0F) | 0x40
    raw[8] = (raw[8] & 0x3F) | 0x80
    return UUID(bytes=bytes(raw))


def _fixture_hash(label: str) -> str:
    return hashlib.sha256(f"{FIXTURE_RUN_ID}:{label}".encode()).hexdigest()


def _fixture_trace(label: str) -> str:
    return f"trace-{_fixture_hash(label)[:32]}"


def fresh_runtime_diagnostic_trace() -> str:
    return f"trace-{uuid5(_DIAGNOSTIC_NAMESPACE, f'diagnostic:{FIXTURE_RUN_ID}').hex}"


def _active_fresh_runtime_diagnostic_codes() -> frozenset[str]:
    activations = (
        FRESH_COMBINED_DIAGNOSTICS_ENABLED,
        COLLECTION_SHAPE_DIAGNOSTICS_ENABLED,
        COLLECTION_RESPONSE_DIAGNOSTICS_ENABLED,
        POST_MOCK_COMBINED_DIAGNOSTICS_ENABLED,
        COLLECTION_SERVER_DIAGNOSTICS_ENABLED,
        POST_UUID_COLLECTION_SERVER_DIAGNOSTICS_ENABLED,
        POST_UUID_COLLECTION_MEMBERSHIP_DIAGNOSTICS_ENABLED,
        POST_MEMBERSHIP_COMBINED_DIAGNOSTICS_ENABLED,
        POST_OPERATION_ID_COMBINED_DIAGNOSTICS_ENABLED,
        UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTICS_ENABLED,
        UNCERTAIN_REPLAY_ACTION_DIAGNOSTICS_ENABLED,
        UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTICS_ENABLED,
        POST_ACTION_ACTOR_COMBINED_DIAGNOSTICS_ENABLED,
    )
    if sum(map(int, activations)) != 1:
        return frozenset()
    codes = frozenset(FRESH_RUNTIME_DIAGNOSTIC_CODES).union(
        FRESH_FIXTURE_DIAGNOSTIC_CODES
    )
    if COLLECTION_SHAPE_DIAGNOSTICS_ENABLED:
        return codes.union(COLLECTION_SHAPE_DIAGNOSTIC_CODES)
    if (
        COLLECTION_RESPONSE_DIAGNOSTICS_ENABLED
        or POST_MOCK_COMBINED_DIAGNOSTICS_ENABLED
        or _collection_server_diagnostics_enabled()
    ):
        codes = codes.union(COLLECTION_RESPONSE_DIAGNOSTIC_CODES)
    if _collection_server_diagnostics_enabled():
        codes = codes.union(COLLECTION_SERVER_DIAGNOSTIC_CODES)
    if (
        POST_UUID_COLLECTION_MEMBERSHIP_DIAGNOSTICS_ENABLED
        or POST_MEMBERSHIP_COMBINED_DIAGNOSTICS_ENABLED
        or POST_OPERATION_ID_COMBINED_DIAGNOSTICS_ENABLED
        or UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTICS_ENABLED
        or UNCERTAIN_REPLAY_ACTION_DIAGNOSTICS_ENABLED
        or UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTICS_ENABLED
        or POST_ACTION_ACTOR_COMBINED_DIAGNOSTICS_ENABLED
    ):
        codes = codes.union(COLLECTION_MEMBERSHIP_DIAGNOSTIC_CODES)
    if (
        UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTICS_ENABLED
        or UNCERTAIN_REPLAY_ACTION_DIAGNOSTICS_ENABLED
        or UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTICS_ENABLED
        or POST_ACTION_ACTOR_COMBINED_DIAGNOSTICS_ENABLED
    ):
        codes = codes.union(UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTIC_CODES)
    if (
        UNCERTAIN_REPLAY_ACTION_DIAGNOSTICS_ENABLED
        or UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTICS_ENABLED
        or POST_ACTION_ACTOR_COMBINED_DIAGNOSTICS_ENABLED
    ):
        codes = codes.union(UNCERTAIN_REPLAY_ACTION_SERVER_DIAGNOSTIC_CODES)
    if (
        UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTICS_ENABLED
        or POST_ACTION_ACTOR_COMBINED_DIAGNOSTICS_ENABLED
    ):
        return codes.union(UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTIC_CODES)
    if codes != frozenset(FRESH_RUNTIME_DIAGNOSTIC_CODES).union(
        FRESH_FIXTURE_DIAGNOSTIC_CODES
    ):
        return codes
    return codes


def _fresh_runtime_diagnostics_enabled() -> bool:
    return bool(_active_fresh_runtime_diagnostic_codes())


def _collection_server_diagnostics_enabled() -> bool:
    activations = (
        FRESH_COMBINED_DIAGNOSTICS_ENABLED,
        COLLECTION_SHAPE_DIAGNOSTICS_ENABLED,
        COLLECTION_RESPONSE_DIAGNOSTICS_ENABLED,
        POST_MOCK_COMBINED_DIAGNOSTICS_ENABLED,
        COLLECTION_SERVER_DIAGNOSTICS_ENABLED,
        POST_UUID_COLLECTION_SERVER_DIAGNOSTICS_ENABLED,
        POST_UUID_COLLECTION_MEMBERSHIP_DIAGNOSTICS_ENABLED,
        POST_MEMBERSHIP_COMBINED_DIAGNOSTICS_ENABLED,
        POST_OPERATION_ID_COMBINED_DIAGNOSTICS_ENABLED,
        UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTICS_ENABLED,
        UNCERTAIN_REPLAY_ACTION_DIAGNOSTICS_ENABLED,
        UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTICS_ENABLED,
        POST_ACTION_ACTOR_COMBINED_DIAGNOSTICS_ENABLED,
    )
    return sum(map(int, activations)) == 1 and (
        COLLECTION_SERVER_DIAGNOSTICS_ENABLED
        or POST_UUID_COLLECTION_SERVER_DIAGNOSTICS_ENABLED
        or POST_UUID_COLLECTION_MEMBERSHIP_DIAGNOSTICS_ENABLED
        or POST_MEMBERSHIP_COMBINED_DIAGNOSTICS_ENABLED
        or POST_OPERATION_ID_COMBINED_DIAGNOSTICS_ENABLED
        or UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTICS_ENABLED
        or UNCERTAIN_REPLAY_ACTION_DIAGNOSTICS_ENABLED
        or UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTICS_ENABLED
        or POST_ACTION_ACTOR_COMBINED_DIAGNOSTICS_ENABLED
    )


def _action_server_diagnostics_enabled() -> bool:
    return bool(
        (
            UNCERTAIN_REPLAY_ACTION_DIAGNOSTICS_ENABLED
            or UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTICS_ENABLED
            or POST_ACTION_ACTOR_COMBINED_DIAGNOSTICS_ENABLED
        )
        and _fresh_runtime_diagnostics_enabled()
    )


@contextmanager
def fresh_runtime_diagnostic_scope(trace_id: str) -> Iterator[None]:
    state = None
    if (
        _fresh_runtime_diagnostics_enabled()
        and _DIAGNOSTIC_TRACE_PATTERN.fullmatch(trace_id) is not None
    ):
        state = {"trace_id": trace_id, "recorded": False}
    token = _DIAGNOSTIC_STATE.set(state)
    try:
        yield
    finally:
        _DIAGNOSTIC_STATE.reset(token)


@contextmanager
def fresh_runtime_diagnostic_step(code: str) -> Iterator[None]:
    try:
        yield
    except Exception as error:
        _record_fresh_runtime_diagnostic(code, error)
        raise


def _record_fresh_runtime_diagnostic(code: str, error: Exception) -> None:
    try:
        state = _DIAGNOSTIC_STATE.get()
        exception_type = type(error).__name__
        if (
            state is None
            or state.get("recorded") is True
            or code not in _active_fresh_runtime_diagnostic_codes()
            or _TYPE_PATTERN.fullmatch(exception_type) is None
        ):
            return
        state["recorded"] = True
        _write_fresh_runtime_diagnostic(
            {
                "code": code,
                "exceptionType": exception_type,
                "traceId": str(state["trace_id"]),
            }
        )
    except Exception:
        # Diagnostics must never replace the original verifier failure.
        pass


def _write_fresh_runtime_diagnostic(record: dict[str, str]) -> None:
    path_value = os.environ.get(_DIAGNOSTIC_PATH_ENV)
    if not isinstance(path_value, str) or not path_value:
        return
    path = Path(path_value)
    if not path.is_absolute() or path.name != _DIAGNOSTIC_FILE_NAME:
        return
    payload = json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(payload)


def read_fresh_runtime_diagnostic(
    path: Path,
    *,
    expected_trace: str,
) -> tuple[str, str, str] | None:
    if _DIAGNOSTIC_TRACE_PATTERN.fullmatch(expected_trace) is None:
        return None
    try:
        payload = path.read_bytes()
        if not payload or len(payload) > _DIAGNOSTIC_RECORD_LIMIT:
            return None
        text = payload.decode("utf-8")
        lines = [line for line in text.splitlines() if line]
        if len(lines) != 1:
            return None
        record = json.loads(lines[0])
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(record, dict) or set(record) != _DIAGNOSTIC_RECORD_KEYS:
        return None
    code = record.get("code")
    exception_type = record.get("exceptionType")
    trace_id = record.get("traceId")
    if (
        not isinstance(code, str)
        or code not in _active_fresh_runtime_diagnostic_codes()
        or not isinstance(exception_type, str)
        or _TYPE_PATTERN.fullmatch(exception_type) is None
        or trace_id != expected_trace
    ):
        return None
    return exception_type, code, expected_trace


def _require_global_id(value: object) -> str:
    try:
        parsed = UUID(str(value))
    except (TypeError, ValueError) as error:
        raise RuntimeError("P8-07 runtime identity is invalid") from error
    require(
        parsed.version in {4, 5} and str(parsed) == str(value),
        "P8-07 runtime identity drifted",
    )
    return str(parsed)


def _require_project_id(value: object) -> str:
    parsed = UUID(_require_global_id(value))
    require(parsed.version == 5, "P8-07 runtime Project identity drifted")
    return str(parsed)


def _collection_path(project_id: str, *, dlq: bool = False) -> str:
    suffix = "/dlq" if dlq else ""
    return f"/api/npi/v1/projects/{project_id}/integration-operations{suffix}"


def _detail_path(project_id: str, operation_kind: str, operation_id: str) -> str:
    return (
        f"/api/npi/v1/projects/{project_id}/integration-operations/"
        f"{operation_kind}/{operation_id}"
    )


def _action_path(
    project_id: str,
    operation_kind: str,
    operation_id: str,
    action: str,
) -> str:
    require(operation_kind in _OPERATION_SLUG, "P8-07 runtime operation kind drifted")
    require(action in {"replay", "request-reconciliation"}, "P8-07 runtime action drifted")
    return (
        f"/api/npi/v1/projects/{project_id}/integration-operations/"
        f"{_OPERATION_SLUG[operation_kind]}/{operation_id}:{action}"
    )


def _request(
    opener: Any,
    base_url: str,
    path: str,
    *,
    label: str,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    csrf_token: str | None = None,
    idempotency_key: str | None = None,
) -> Any:
    headers = (
        document_runtime.command_headers(csrf_token, idempotency_key)
        if idempotency_key is not None
        else document_runtime.query_headers(f"p807-{label}")
    )
    if _collection_server_diagnostics_enabled() and label == "fresh-list":
        state = _DIAGNOSTIC_STATE.get()
        trace_id = state.get("trace_id") if isinstance(state, dict) else None
        require(
            isinstance(trace_id, str)
            and _DIAGNOSTIC_TRACE_PATTERN.fullmatch(trace_id) is not None,
            "P8-07 collection server diagnostic trace is invalid",
        )
        headers["X-Trace-ID"] = trace_id
        headers[_COLLECTION_SERVER_DIAGNOSTIC_HEADER] = (
            _COLLECTION_SERVER_DIAGNOSTIC_SCOPE
        )
    if _action_server_diagnostics_enabled() and label == "uncertain-replay":
        state = _DIAGNOSTIC_STATE.get()
        trace_id = state.get("trace_id") if isinstance(state, dict) else None
        require(
            isinstance(trace_id, str)
            and _DIAGNOSTIC_TRACE_PATTERN.fullmatch(trace_id) is not None,
            "P8-07 action server diagnostic trace is invalid",
        )
        headers["X-Trace-ID"] = trace_id
        headers[_ACTION_SERVER_DIAGNOSTIC_HEADER] = (
            _ACTION_SERVER_DIAGNOSTIC_SCOPE
        )
    try:
        result = document_runtime.request(
            opener,
            base_url,
            path,
            method=method,
            payload=payload,
            request_headers=headers,
        )
    except Exception:
        _record_default_disabled_diagnostic("P807_DEFAULT_DISABLED_HTTP", label=label)
        raise
    _diagnostic_require(
        result.headers.get("X-Request-ID") == headers["X-Request-ID"],
        "P807_DEFAULT_DISABLED_REQUEST_ID",
        "P8-07 request identity was not echoed",
        label=label,
    )
    _diagnostic_require(
        result.headers.get("Cache-Control") == "private, no-store",
        "P807_DEFAULT_DISABLED_CACHE_CONTROL",
        "P8-07 response cache control drifted",
        label=label,
    )
    try:
        _assert_safe(result.body)
    except Exception:
        _record_default_disabled_diagnostic(
            "P807_DEFAULT_DISABLED_RESPONSE_SAFE",
            label=label,
        )
        raise
    return result


def _record_default_disabled_diagnostic(code: str, *, label: str = "disabled") -> None:
    require(code in _DEFAULT_DISABLED_DIAGNOSTIC_CODES, "P8-07 diagnostic code drifted")
    if DEFAULT_DISABLED_DIAGNOSTICS_ENABLED and label == "disabled":
        print(code, file=sys.stderr)


def _diagnostic_require(
    condition: object,
    code: str,
    message: str,
    *,
    label: str = "disabled",
) -> None:
    if condition:
        return
    _record_default_disabled_diagnostic(code, label=label)
    require(False, message)


def _diagnostic_call(code: str, function: Any) -> Any:
    try:
        return function()
    except Exception:
        _record_default_disabled_diagnostic(code)
        raise


def _assert_safe(value: object) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).casefold())
            require(
                not any(
                    normalized == forbidden
                    or normalized.startswith(forbidden)
                    or normalized.endswith(forbidden)
                    for forbidden in _FORBIDDEN_KEYS
                ),
                "P8-07 response leaked restricted material",
            )
            _assert_safe(child)
    elif isinstance(value, list):
        for child in value:
            _assert_safe(child)


def _collection_status_diagnostic_code(status: object) -> str:
    if COLLECTION_SHAPE_DIAGNOSTICS_ENABLED:
        return "P807_COLLECTION_STATUS"
    if type(status) is not int:
        return "P807_COLLECTION_STATUS_INVALID"
    if 100 <= status < 200:
        return "P807_COLLECTION_STATUS_INFORMATIONAL"
    if 200 <= status < 300:
        return "P807_COLLECTION_STATUS_OTHER_SUCCESS"
    if 300 <= status < 400:
        return "P807_COLLECTION_STATUS_REDIRECTION"
    if 400 <= status < 500:
        return "P807_COLLECTION_STATUS_CLIENT_ERROR"
    if 500 <= status < 600:
        return "P807_COLLECTION_STATUS_SERVER_ERROR"
    return "P807_COLLECTION_STATUS_OUT_OF_RANGE"


def _uncertain_replay_status_diagnostic_code(status: object) -> str:
    if type(status) is not int:
        return UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTIC_CODES[0]
    if 100 <= status < 200:
        return UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTIC_CODES[1]
    if 200 <= status < 300:
        return UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTIC_CODES[2]
    if 300 <= status < 400:
        return UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTIC_CODES[3]
    if 400 <= status < 500:
        return UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTIC_CODES[4]
    if 500 <= status < 600:
        return UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTIC_CODES[5]
    return UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTIC_CODES[6]


def _validate_uncertain_replay_problem(
    result: Any,
    *,
    diagnostic_cursors: dict[str, int] | None = None,
) -> None:
    if not (
        UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTICS_ENABLED
        or UNCERTAIN_REPLAY_ACTION_DIAGNOSTICS_ENABLED
        or UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTICS_ENABLED
        or POST_ACTION_ACTOR_COMBINED_DIAGNOSTICS_ENABLED
    ):
        validate_problem(result, 409, "INTEGRATION_OPERATION_CONFLICT")
        return
    if result.status != 409:
        state = _DIAGNOSTIC_STATE.get()
        trace_id = state.get("trace_id") if isinstance(state, dict) else None
        _record_action_server_diagnostic(trace_id, diagnostic_cursors)
        with fresh_runtime_diagnostic_step(
            _uncertain_replay_status_diagnostic_code(result.status)
        ):
            require(False, "P8-07 uncertain replay status drifted")
    with fresh_runtime_diagnostic_step(
        UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTIC_CODES[7]
    ):
        require(
            result.body.get("status") == 409,
            "P8-07 uncertain replay problem status drifted",
        )
    with fresh_runtime_diagnostic_step(
        UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTIC_CODES[8]
    ):
        require(
            result.body.get("code") == "INTEGRATION_OPERATION_CONFLICT",
            "P8-07 uncertain replay problem code drifted",
        )
    with fresh_runtime_diagnostic_step(
        UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTIC_CODES[9]
    ):
        require(
            result.headers.get_content_type() == "application/problem+json",
            "P8-07 uncertain replay problem media type drifted",
        )
    with fresh_runtime_diagnostic_step(
        UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTIC_CODES[10]
    ):
        trace_id = result.body.get("traceId")
        require(
            isinstance(trace_id, str)
            and trace_id == result.headers.get("X-Trace-ID"),
            "P8-07 uncertain replay problem trace drifted",
        )
    with fresh_runtime_diagnostic_step(
        UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTIC_CODES[11]
    ):
        require(
            not {"exc", "exception", "exc_type", "message"}.intersection(
                result.body
            ),
            "P8-07 uncertain replay problem envelope drifted",
        )


def _record_collection_server_diagnostic(
    trace_id: object,
    cursors: dict[str, int] | None,
) -> bool:
    if not _collection_server_diagnostics_enabled():
        return False
    diagnostic = item_runtime._sanitized_server_log_diagnostic(
        trace_id,
        cursors,
        code_prefix="P807_COLLECTION_",
        allowed_codes=frozenset(COLLECTION_SERVER_DIAGNOSTIC_CODES),
    )
    if diagnostic is None:
        return False
    exception_type, code, validated_trace = diagnostic
    state = _DIAGNOSTIC_STATE.get()
    if (
        not isinstance(state, dict)
        or state.get("recorded") is True
        or state.get("trace_id") != validated_trace
    ):
        return False
    try:
        _write_fresh_runtime_diagnostic(
            {
                "code": code,
                "exceptionType": exception_type,
                "traceId": validated_trace,
            }
        )
    except Exception:
        return False
    state["recorded"] = True
    return True


def _record_action_server_diagnostic(
    trace_id: object,
    cursors: dict[str, int] | None,
) -> bool:
    if not _action_server_diagnostics_enabled():
        return False
    diagnostic = item_runtime._sanitized_server_log_diagnostic(
        trace_id,
        cursors,
        code_prefix="P807_ACTION_",
        allowed_codes=frozenset(
            UNCERTAIN_REPLAY_ACTION_SERVER_DIAGNOSTIC_CODES
        ).union(UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTIC_CODES),
    )
    if diagnostic is None:
        return False
    exception_type, code, validated_trace = diagnostic
    state = _DIAGNOSTIC_STATE.get()
    if (
        not isinstance(state, dict)
        or state.get("recorded") is True
        or state.get("trace_id") != validated_trace
    ):
        return False
    try:
        _write_fresh_runtime_diagnostic(
            {
                "code": code,
                "exceptionType": exception_type,
                "traceId": validated_trace,
            }
        )
    except Exception:
        return False
    state["recorded"] = True
    return True


def _items(
    result: Any,
    *,
    project_id: str,
    diagnostic_cursors: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    if result.status != 200:
        state = _DIAGNOSTIC_STATE.get()
        trace_id = state.get("trace_id") if isinstance(state, dict) else None
        _record_collection_server_diagnostic(trace_id, diagnostic_cursors)
        with fresh_runtime_diagnostic_step(
            _collection_status_diagnostic_code(result.status)
        ):
            require(False, "P8-07 operation collection is unavailable")
    body = result.body
    items = body.get("items")
    with fresh_runtime_diagnostic_step("P807_COLLECTION_PROJECT"):
        require(
            body.get("projectGlobalId") == project_id,
            "P8-07 operation collection Project drifted",
        )
    with fresh_runtime_diagnostic_step("P807_COLLECTION_PERMISSIONS"):
        require(
            isinstance(body.get("permissions"), dict),
            "P8-07 operation collection permissions drifted",
        )
    with fresh_runtime_diagnostic_step("P807_COLLECTION_ITEMS"):
        require(
            isinstance(items, list),
            "P8-07 operation collection items drifted",
        )
    with fresh_runtime_diagnostic_step("P807_COLLECTION_ITEM_SHAPES"):
        require(
            all(isinstance(item, dict) for item in items),
            "P8-07 operation collection item shape drifted",
        )
    return items


def _detail(result: Any, *, project_id: str) -> dict[str, Any]:
    require(result.status == 200, "P8-07 operation detail is unavailable")
    operation = result.body.get("operation")
    require(
        result.body.get("projectGlobalId") == project_id
        and isinstance(result.body.get("permissions"), dict)
        and isinstance(operation, dict),
        "P8-07 operation detail shape drifted",
    )
    return operation


def _action(
    opener: Any,
    base_url: str,
    *,
    project_id: str,
    operation: dict[str, Any],
    action: str,
    csrf_token: str,
    idempotency_key: str,
    label: str,
) -> Any:
    operation_kind = str(operation.get("operationKind"))
    operation_id = str(operation.get("operationGlobalId"))
    payload = {
        "expectedRawState": operation.get("rawState"),
        "expectedVersion": operation.get("operationVersion"),
    }
    return _request(
        opener,
        base_url,
        _action_path(project_id, operation_kind, operation_id, action),
        label=label,
        method="POST",
        payload=payload,
        csrf_token=csrf_token,
        idempotency_key=idempotency_key,
    )


def _exact_item(
    items: list[dict[str, Any]],
    *,
    operation_id: str | None = None,
    raw_state: str | None = None,
) -> dict[str, Any]:
    matches = [
        item
        for item in items
        if item.get("operationKind") == "publish_item"
        and (operation_id is None or item.get("operationGlobalId") == operation_id)
        and (raw_state is None or item.get("rawState") == raw_state)
    ]
    require(len(matches) == 1, "P8-07 exact Item operation cardinality drifted")
    return matches[0]


def _require_collection_kinds(items: list[dict[str, Any]]) -> None:
    kinds = {str(item.get("operationKind")) for item in items}
    if (
        POST_UUID_COLLECTION_MEMBERSHIP_DIAGNOSTICS_ENABLED
        or POST_MEMBERSHIP_COMBINED_DIAGNOSTICS_ENABLED
        or POST_OPERATION_ID_COMBINED_DIAGNOSTICS_ENABLED
        or UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTICS_ENABLED
        or UNCERTAIN_REPLAY_ACTION_DIAGNOSTICS_ENABLED
        or UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTICS_ENABLED
        or POST_ACTION_ACTOR_COMBINED_DIAGNOSTICS_ENABLED
    ):
        for code, operation_kind, expected_present in _EXPECTED_COLLECTION_MEMBERSHIP:
            with fresh_runtime_diagnostic_step(code):
                require(
                    (operation_kind in kinds) is expected_present,
                    "P8-07 retained operation inventory drifted",
                )
        return
    with fresh_runtime_diagnostic_step("P807_FRESH_COLLECTION_KINDS"):
        require(
            "receive_project_submission" not in kinds
            and set(_REQUIRED_COLLECTION_KINDS).issubset(kinds),
            "P8-07 retained operation inventory drifted",
        )


def run_disabled_probe(
    base_url: str,
    fixture_password: str,
    project_id: str,
) -> dict[str, object]:
    actor = _diagnostic_call(
        "P807_DEFAULT_DISABLED_LOGIN",
        lambda: login(base_url, ACTOR_USER, fixture_password),
    )
    result = _request(
        actor,
        base_url,
        _collection_path(project_id),
        label="disabled",
    )
    _diagnostic_require(
        result.status == 503,
        "P807_DEFAULT_DISABLED_STATUS",
        "P8-07 disabled route status drifted",
    )
    _diagnostic_require(
        result.body.get("status") == 503,
        "P807_DEFAULT_DISABLED_BODY_STATUS",
        "P8-07 disabled route body status drifted",
    )
    _diagnostic_require(
        result.body.get("code") == "INTEGRATION_OPERATIONS_ROUTES_DISABLED",
        "P807_DEFAULT_DISABLED_CODE",
        "P8-07 disabled route code drifted",
    )
    try:
        media_type = result.headers.get_content_type()
    except Exception:
        _record_default_disabled_diagnostic("P807_DEFAULT_DISABLED_MEDIA_TYPE")
        raise
    _diagnostic_require(
        media_type == "application/problem+json",
        "P807_DEFAULT_DISABLED_MEDIA_TYPE",
        "P8-07 disabled route media type drifted",
    )
    trace_id = result.body.get("traceId")
    _diagnostic_require(
        isinstance(trace_id, str) and trace_id == result.headers.get("X-Trace-ID"),
        "P807_DEFAULT_DISABLED_TRACE",
        "P8-07 disabled route trace drifted",
    )
    _diagnostic_require(
        not {"exc", "exception", "exc_type", "message"}.intersection(result.body),
        "P807_DEFAULT_DISABLED_ENVELOPE",
        "P8-07 disabled route leaked a Frappe error envelope",
    )
    try:
        validate_problem(result, 503, "INTEGRATION_OPERATIONS_ROUTES_DISABLED")
    except Exception:
        _record_default_disabled_diagnostic("P807_DEFAULT_DISABLED_CONTRACT")
        raise
    return {"routesDisabled": True}


def run_fresh(
    base_url: str,
    fixture_password: str,
    project_id: str,
) -> dict[str, object]:
    with fresh_runtime_diagnostic_step("P807_FRESH_ENVIRONMENT"):
        _require_active_environment(project_id)
    with fresh_runtime_diagnostic_step("P807_FRESH_LOGIN"):
        actor = login(base_url, ACTOR_USER, fixture_password)
        action_actor = login(base_url, ACTION_ACTOR_USER, fixture_password)
    with fresh_runtime_diagnostic_step("P807_FRESH_CSRF"):
        bootstrap_csrf(actor, base_url, ACTOR_USER)
        action_csrf = bootstrap_csrf(
            action_actor,
            base_url,
            ACTION_ACTOR_USER,
        )
    with fresh_runtime_diagnostic_step("P807_FRESH_SEED"):
        seeded = run_bench_fixture(
            "seed_retryable",
            {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
        )
    with fresh_runtime_diagnostic_step("P807_FRESH_SEED_SHAPE"):
        require(
            seeded == {
                "failedRetryable": True,
                "networkContactCount": 0,
                "seeded": True,
            },
            "P8-07 retryable fixture drifted",
        )

    collection_diagnostic_cursors = (
        item_runtime._replay_diagnostic_log_cursors()
        if _collection_server_diagnostics_enabled()
        else None
    )
    with fresh_runtime_diagnostic_step("P807_FRESH_COLLECTION_HTTP"):
        collection = _request(
            actor,
            base_url,
            _collection_path(project_id),
            label="fresh-list",
        )
    with fresh_runtime_diagnostic_step("P807_FRESH_COLLECTION_SHAPE"):
        items = _items(
            collection,
            project_id=project_id,
            diagnostic_cursors=collection_diagnostic_cursors,
        )
    _require_collection_kinds(items)
    retryable_id = str(_fixture_uuid("retryable-request"))
    with fresh_runtime_diagnostic_step("P807_FRESH_RETRYABLE_ITEM"):
        retryable = _exact_item(items, operation_id=retryable_id)
    with fresh_runtime_diagnostic_step("P807_FRESH_UNCERTAIN_ITEM"):
        uncertain = _exact_item(items, raw_state="uncertain_after_timeout")
    with fresh_runtime_diagnostic_step("P807_FRESH_CLASSIFICATION"):
        require(
            retryable.get("sharedState") == "failed_retryable"
            and retryable.get("replayEligible") is True
            and uncertain.get("sharedState") == "uncertain"
            and uncertain.get("replayEligible") is False
            and uncertain.get("reconciliationRequired") is True,
            "P8-07 retry and uncertainty classification drifted",
        )

    with fresh_runtime_diagnostic_step("P807_FRESH_DLQ_HTTP"):
        dlq_result = _request(
            actor,
            base_url,
            _collection_path(project_id, dlq=True),
            label="fresh-dlq",
        )
    with fresh_runtime_diagnostic_step("P807_FRESH_DLQ_SHAPE"):
        dlq = _items(dlq_result, project_id=project_id)
    with fresh_runtime_diagnostic_step("P807_FRESH_DLQ_CARDINALITY"):
        dlq_ids = {str(item.get("operationGlobalId")) for item in dlq}
        require(
            retryable_id in dlq_ids
            and str(uncertain.get("operationGlobalId")) in dlq_ids,
            "P8-07 logical DLQ omitted governed operations",
        )

    with fresh_runtime_diagnostic_step("P807_FRESH_PAGE_ONE_HTTP"):
        first_page = _request(
            actor,
            base_url,
            f"{_collection_path(project_id)}?limit=2",
            label="page-one",
        )
    with fresh_runtime_diagnostic_step("P807_FRESH_PAGE_ONE_SHAPE"):
        first_items = _items(first_page, project_id=project_id)
    with fresh_runtime_diagnostic_step("P807_FRESH_PAGE_ONE_CURSOR"):
        cursor = first_page.body.get("nextCursor")
        require(
            len(first_items) == 2 and isinstance(cursor, str),
            "P8-07 cursor page drifted",
        )
    with fresh_runtime_diagnostic_step("P807_FRESH_PAGE_TWO_HTTP"):
        second_page = _request(
            actor,
            base_url,
            f"{_collection_path(project_id)}?limit=2&cursor={cursor}",
            label="page-two",
        )
    with fresh_runtime_diagnostic_step("P807_FRESH_PAGE_TWO_SHAPE"):
        second_items = _items(second_page, project_id=project_id)
    with fresh_runtime_diagnostic_step("P807_FRESH_PAGE_DISJOINT"):
        require(
            {item["operationGlobalId"] for item in first_items}.isdisjoint(
                {item["operationGlobalId"] for item in second_items}
            ),
            "P8-07 cursor repeated an operation",
        )

    foreign_project = str(_fixture_uuid("foreign-project"))
    with fresh_runtime_diagnostic_step("P807_FRESH_FOREIGN_HTTP"):
        foreign = _request(
            actor,
            base_url,
            _collection_path(foreign_project),
            label="foreign-project",
        )
    with fresh_runtime_diagnostic_step("P807_FRESH_FOREIGN_CONTRACT"):
        validate_problem(foreign, 404, "INTEGRATION_OPERATION_NOT_FOUND")

    with fresh_runtime_diagnostic_step("P807_FRESH_RETRYABLE_DETAIL_HTTP"):
        retryable_detail_result = _request(
            actor,
            base_url,
            _detail_path(project_id, "publish_item", retryable_id),
            label="retryable-detail",
        )
    with fresh_runtime_diagnostic_step("P807_FRESH_RETRYABLE_DETAIL_SHAPE"):
        retryable_detail = _detail(retryable_detail_result, project_id=project_id)
    uncertain_id = str(uncertain["operationGlobalId"])
    with fresh_runtime_diagnostic_step("P807_FRESH_UNCERTAIN_DETAIL_HTTP"):
        uncertain_detail_result = _request(
            actor,
            base_url,
            _detail_path(project_id, "publish_item", uncertain_id),
            label="uncertain-detail",
        )
    with fresh_runtime_diagnostic_step("P807_FRESH_UNCERTAIN_DETAIL_SHAPE"):
        uncertain_detail = _detail(uncertain_detail_result, project_id=project_id)
    with fresh_runtime_diagnostic_step("P807_FRESH_HISTORY"):
        require(
            len(retryable_detail.get("attempts", [])) == 1
            and len(retryable_detail.get("results", [])) == 1
            and len(uncertain_detail.get("attempts", [])) >= 1
            and len(uncertain_detail.get("results", [])) == 1,
            "P8-07 immutable operation history drifted",
        )

    with fresh_runtime_diagnostic_step("P807_FRESH_SNAPSHOT_BEFORE"):
        before_uncertain = run_bench_fixture(
            "snapshot",
            {
                "fixture_run_id": FIXTURE_RUN_ID,
                "project_id": project_id,
                "uncertain_operation_id": uncertain_id,
            },
        )
    uncertain_replay_diagnostic_cursors = (
        item_runtime._replay_diagnostic_log_cursors()
        if _action_server_diagnostics_enabled()
        else None
    )
    with fresh_runtime_diagnostic_step("P807_FRESH_UNCERTAIN_REPLAY_HTTP"):
        rejected = _action(
            action_actor,
            base_url,
            project_id=project_id,
            operation=uncertain,
            action="replay",
            csrf_token=action_csrf,
            idempotency_key=f"p807-uncertain-replay-{FIXTURE_RUN_ID}",
            label="uncertain-replay",
        )
    with fresh_runtime_diagnostic_step("P807_FRESH_UNCERTAIN_REPLAY_CONTRACT"):
        _validate_uncertain_replay_problem(
            rejected,
            diagnostic_cursors=uncertain_replay_diagnostic_cursors,
        )
    with fresh_runtime_diagnostic_step("P807_FRESH_SNAPSHOT_AFTER"):
        after_uncertain = run_bench_fixture(
            "snapshot",
            {
                "fixture_run_id": FIXTURE_RUN_ID,
                "project_id": project_id,
                "uncertain_operation_id": uncertain_id,
            },
        )
    with fresh_runtime_diagnostic_step("P807_FRESH_UNCERTAIN_UNCHANGED"):
        require(
            before_uncertain == after_uncertain
            and before_uncertain.get("adapterCalls") == 0,
            "P8-07 uncertain replay changed or redispatched owning truth",
        )

    with fresh_runtime_diagnostic_step("P807_FRESH_RECONCILIATION_HTTP"):
        reconciliation = _action(
            action_actor,
            base_url,
            project_id=project_id,
            operation=uncertain,
            action="request-reconciliation",
            csrf_token=action_csrf,
            idempotency_key=f"p807-reconcile-{FIXTURE_RUN_ID}",
            label="reconciliation",
        )
    with fresh_runtime_diagnostic_step("P807_FRESH_RECONCILIATION_SHAPE"):
        require(
            reconciliation.status == 201
            and reconciliation.headers.get("Idempotency-Replayed") == "false"
            and reconciliation.body.get("outcomeState") == "reconciliation_requested"
            and reconciliation.body.get("outcomeReferenceGlobalId") is None,
            "P8-07 reconciliation intent was not appended",
        )
    with fresh_runtime_diagnostic_step("P807_FRESH_OBSERVATION"):
        observed = run_bench_fixture(
            "append_observation",
            {
                "fixture_run_id": FIXTURE_RUN_ID,
                "project_id": project_id,
                "operation_id": uncertain_id,
                "action_receipt_id": str(reconciliation.body.get("actionGlobalId")),
            },
        )
    with fresh_runtime_diagnostic_step("P807_FRESH_OBSERVATION_SHAPE"):
        require(
            observed == {
                "appendOnly": True,
                "authoritativeSuccess": False,
                "observationCount": 1,
            },
            "P8-07 reconciliation observation boundary drifted",
        )

    with fresh_runtime_diagnostic_step("P807_FRESH_REPLAY_HTTP"):
        replay = _action(
            action_actor,
            base_url,
            project_id=project_id,
            operation=retryable,
            action="replay",
            csrf_token=action_csrf,
            idempotency_key=f"p807-replay-{FIXTURE_RUN_ID}",
            label="retryable-replay",
        )
    with fresh_runtime_diagnostic_step("P807_FRESH_REPLAY_SHAPE"):
        require(
            replay.status == 201
            and replay.headers.get("Idempotency-Replayed") == "false"
            and replay.body.get("outcomeState") == "replay_requested"
            and replay.body.get("outcomeReferenceGlobalId")
            == str(_fixture_uuid("retryable-outbox")),
            "P8-07 retryable action did not requeue exact owning work",
        )

    stale = dict(uncertain)
    stale["operationVersion"] = int(uncertain["operationVersion"]) + 1
    with fresh_runtime_diagnostic_step("P807_FRESH_STALE_HTTP"):
        stale_result = _action(
            action_actor,
            base_url,
            project_id=project_id,
            operation=stale,
            action="request-reconciliation",
            csrf_token=action_csrf,
            idempotency_key=f"p807-stale-{FIXTURE_RUN_ID}",
            label="stale-reconciliation",
        )
    with fresh_runtime_diagnostic_step("P807_FRESH_STALE_CONTRACT"):
        validate_problem(stale_result, 409, "INTEGRATION_OPERATION_CONFLICT")
    with fresh_runtime_diagnostic_step("P807_FRESH_COUNTS"):
        sealed = run_bench_fixture(
            "verify_counts",
            {
                "fixture_run_id": FIXTURE_RUN_ID,
                "project_id": project_id,
                "uncertain_operation_id": uncertain_id,
            },
        )
    with fresh_runtime_diagnostic_step("P807_FRESH_COUNTS_SHAPE"):
        require(
            sealed == {"actionCount": 2, "observationCount": 1, "rollbackClean": True},
            "P8-07 action transaction or rollback cardinality drifted",
        )
    return {
        "crossProcessReplayReady": True,
        "immutableHistory": True,
        "logicalDlq": True,
        "networkContactCount": 0,
        "projectContainment": True,
        "reconciliationIntentAndObservation": True,
        "retryableReplay": True,
        "rollback": True,
        "uncertainNoRedispatch": True,
    }


def run_replay(
    base_url: str,
    fixture_password: str,
    project_id: str,
) -> dict[str, object]:
    _require_active_environment(project_id)
    actor = login(base_url, ACTOR_USER, fixture_password)
    action_actor = login(base_url, ACTION_ACTOR_USER, fixture_password)
    action_csrf = bootstrap_csrf(
        action_actor,
        base_url,
        ACTION_ACTOR_USER,
    )
    items = _items(
        _request(actor, base_url, _collection_path(project_id), label="replay-list"),
        project_id=project_id,
    )
    retryable_id = str(_fixture_uuid("retryable-request"))
    queued = _exact_item(items, operation_id=retryable_id)
    uncertain = _exact_item(items, raw_state="uncertain_after_timeout")
    require(
        queued.get("rawState") == "queued" and queued.get("replayEligible") is False,
        "P8-07 replay did not retain exact queued owning state",
    )
    replay = _action(
        action_actor,
        base_url,
        project_id=project_id,
        operation={**queued, "rawState": "failed_retryable", "operationVersion": 3},
        action="replay",
        csrf_token=action_csrf,
        idempotency_key=f"p807-replay-{FIXTURE_RUN_ID}",
        label="replay-idempotency",
    )
    reconciliation = _action(
        action_actor,
        base_url,
        project_id=project_id,
        operation=uncertain,
        action="request-reconciliation",
        csrf_token=action_csrf,
        idempotency_key=f"p807-reconcile-{FIXTURE_RUN_ID}",
        label="reconciliation-idempotency",
    )
    require(
        replay.status == 200
        and reconciliation.status == 200
        and replay.headers.get("Idempotency-Replayed") == "true"
        and reconciliation.headers.get("Idempotency-Replayed") == "true",
        "P8-07 cross-process action idempotency drifted",
    )
    counts = run_bench_fixture(
        "verify_counts",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "uncertain_operation_id": str(uncertain["operationGlobalId"]),
        },
    )
    require(
        counts == {"actionCount": 2, "observationCount": 1, "rollbackClean": True},
        "P8-07 cross-process replay appended duplicate history",
    )
    return {"crossProcessIdempotency": True, "historyCardinalityStable": True}


def run_recovered(
    base_url: str,
    fixture_password: str,
    project_id: str,
) -> dict[str, object]:
    _require_active_environment(project_id)
    actor = login(base_url, ACTOR_USER, fixture_password)
    items = _items(
        _request(actor, base_url, _collection_path(project_id), label="route-recovered"),
        project_id=project_id,
    )
    require(
        any(item.get("operationGlobalId") == str(_fixture_uuid("retryable-request")) for item in items),
        "P8-07 route recovery lost retained operation history",
    )
    return {"routeRecovered": True}


def run_post_migration_cleanup(
    base_url: str,
    fixture_password: str,
    project_id: str,
) -> dict[str, object]:
    _require_active_environment(project_id)
    actor = login(base_url, ACTOR_USER, fixture_password)
    items = _items(
        _request(actor, base_url, _collection_path(project_id), label="post-migration"),
        project_id=project_id,
    )
    uncertain = _exact_item(items, raw_state="uncertain_after_timeout")
    cleaned = run_bench_fixture(
        "verify_and_cleanup",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "uncertain_operation_id": str(uncertain["operationGlobalId"]),
        },
    )
    require(
        cleaned
        == {
            "actionHistoryImmutable": True,
            "cleanupComplete": True,
            "migrationPreservedHistory": True,
            "observationHistoryImmutable": True,
        },
        "P8-07 migration or cleanup proof drifted",
    )
    return cleaned


def _require_active_environment(project_id: str) -> str:
    worker = os.environ.get("NPI_P8_07_RUNTIME_WORKER", "")
    require(
        os.environ.get("NPI_P8_07_RUNTIME_ENABLED") == "1"
        and os.environ.get("NPI_P8_07_RUNTIME_MARKER") == RUNTIME_MARKER
        and os.environ.get("NPI_P8_07_RUNTIME_PROJECT_ID") == project_id
        and os.environ.get("NPI_P8_07_RUNTIME_REQUESTER") == ACTOR_USER
        and bool(worker)
        and worker != ACTOR_USER,
        "P8-07 runtime environment is not exact",
    )
    require(
        ACTION_ACTOR_USER == readiness_runtime.ACTOR_USER
        and ACTION_ACTOR_USER.endswith("@example.invalid")
        and ACTION_ACTOR_USER not in {ACTOR_USER, worker},
        "P8-07 retained action actor is not exact",
    )
    return worker


def _validate_fixture(fixture_run_id: str, project_id: str) -> str:
    import frappe

    document_runtime._validated_runtime_site()
    project_id = _require_project_id(project_id)
    worker = _require_active_environment(project_id)
    require(fixture_run_id == FIXTURE_RUN_ID, "P8-07 fixture namespace drifted")
    project = frappe.get_doc("NPI Engineering Project", project_id)
    require(
        str(project.global_id) == project_id and str(project.tenant_id) == TENANT_ID,
        "P8-07 fixture Project containment drifted",
    )
    return worker


def seed_retryable(fixture_run_id: str, project_id: str) -> dict[str, object]:
    import frappe
    from npi_integration.item_publish.adapters import failed_before_adapter_boundary_result
    from npi_integration.item_publish.domain import ItemSourceSnapshot, create_item_publish_request
    from npi_integration.item_publish.frappe_repository import (
        FrappeItemPublishRepository,
        _locked_stream_guard,
        _set_stream_guard_active,
    )
    from npi_integration.item_publish.frappe_validation import (
        item_request_transaction_write,
        item_service_actor_scope,
    )
    from npi_integration.item_publish.worker_repository import (
        FrappeItemPublishWorkerRepository,
        _request_value,
    )

    with fresh_runtime_diagnostic_step("P807_SEED_VALIDATE"):
        worker = _validate_fixture(fixture_run_id, project_id)
    with fresh_runtime_diagnostic_step("P807_SEED_SET_REQUESTER"):
        frappe.set_user(ACTOR_USER)
    with fresh_runtime_diagnostic_step("P807_SEED_SOURCE_QUERY"):
        source_names = frappe.get_all(
            "NPI Item Publish Request",
            filters={"project_global_id": project_id, "state": "synthetic_verified"},
            pluck="name",
            order_by="name asc",
            limit_page_length=2,
        )
    with fresh_runtime_diagnostic_step("P807_SEED_SOURCE_CARDINALITY"):
        require(len(source_names) == 1, "P8-07 source fixture cardinality drifted")
    with fresh_runtime_diagnostic_step("P807_SEED_SOURCE_VALUE"):
        source_value = _request_value(
            frappe.get_doc("NPI Item Publish Request", source_names[0])
        )
    engineering_id = f"P807-RTRY-{FIXTURE_RUN_ID[:12]}"
    with fresh_runtime_diagnostic_step("P807_SEED_SOURCE_BUILD"):
        occurrences = tuple(
            replace(occurrence, engineering_item_id=engineering_id)
            for occurrence in source_value.source.occurrences
        )
        source = ItemSourceSnapshot(
            tenant_id=source_value.source.tenant_id,
            project_global_id=source_value.source.project_global_id,
            engineering_item_id=engineering_id,
            selected_publish_node_global_id=source_value.source.selected_publish_node_global_id,
            description=source_value.source.description,
            engineering_uom=source_value.source.engineering_uom,
            attributes=source_value.source.attributes,
            occurrences=occurrences,
        )
    now = datetime.now(UTC).replace(microsecond=0)
    request_id = _fixture_uuid("retryable-request")
    outbox_id = _fixture_uuid("retryable-outbox")
    with fresh_runtime_diagnostic_step("P807_SEED_REQUEST_BUILD"):
        value = create_item_publish_request(
            source=source,
            released_evidence=source_value.released_evidence,
            profile=source_value.profile,
            mapping_expectation=source_value.mapping_expectation,
            actor_user_id=ACTOR_USER,
            request_id=_fixture_uuid("request-identity"),
            trace_id=_fixture_trace("retryable"),
            idempotency_key_hash=_fixture_hash("request-idempotency"),
            service_actor_user_id=worker,
            global_id=request_id,
            created_at=now,
        )
    with fresh_runtime_diagnostic_step("P807_SEED_PROJECT_LOCK"):
        project = frappe.get_doc("NPI Engineering Project", project_id, for_update=True)
    with item_request_transaction_write(ACTOR_USER) as capability:
        with fresh_runtime_diagnostic_step("P807_SEED_STREAM_GUARD"):
            guard = _locked_stream_guard(
                source,
                create=True,
                now=now,
                capability=capability,
            )
            require(guard is not None, "P8-07 retryable stream guard is unavailable")
        with fresh_runtime_diagnostic_step("P807_SEED_REQUEST_INSERT"):
            FrappeItemPublishRepository._insert_item_request(
                project,
                value,
                outbox_event_id=outbox_id,
                now=now,
                capability=capability,
            )
        with fresh_runtime_diagnostic_step("P807_SEED_OUTBOX_INSERT"):
            FrappeItemPublishRepository._insert_outbox(
                project,
                value,
                event_id=outbox_id,
                capability=capability,
            )
        with fresh_runtime_diagnostic_step("P807_SEED_STREAM_ACTIVE"):
            _set_stream_guard_active(guard, value, now=now, capability=capability)
    with fresh_runtime_diagnostic_step("P807_SEED_REQUEST_COMMIT"):
        frappe.db.commit()

    with fresh_runtime_diagnostic_step("P807_SEED_WORKER_REPOSITORY"):
        repository = FrappeItemPublishWorkerRepository()
    with item_service_actor_scope(worker):
        with fresh_runtime_diagnostic_step("P807_SEED_CLAIM"):
            claim = repository.claim(outbox_id, now=now)
            require(claim is not None, "P8-07 retryable fixture could not be claimed")
        with fresh_runtime_diagnostic_step("P807_SEED_CLAIM_COMMIT"):
            frappe.db.commit()
        with fresh_runtime_diagnostic_step("P807_SEED_FAILURE_CLASSIFY"):
            classified = failed_before_adapter_boundary_result(
                command=claim.command,
                observed_at=now,
                safe_error_code="P807_DISPOSABLE_TARGET_UNAVAILABLE",
                retryable=True,
            )
        with fresh_runtime_diagnostic_step("P807_SEED_RESULT_SEAL"):
            outcome = repository.seal_result(
                claim,
                profile=None,
                result=classified,
                now=now,
            )
            require(
                outcome.state == "failed_retryable" and outcome.mapping_advanced is False,
                "P8-07 retryable fixture did not stop before target authority",
            )
        with fresh_runtime_diagnostic_step("P807_SEED_RESULT_COMMIT"):
            frappe.db.commit()
    with fresh_runtime_diagnostic_step("P807_SEED_SESSION_RESTORE"):
        require(
            str(getattr(frappe.session, "user", "")) == ACTOR_USER,
            "P8-07 retryable fixture did not restore requester session",
        )
    return {"failedRetryable": True, "networkContactCount": 0, "seeded": True}


def snapshot(
    fixture_run_id: str,
    project_id: str,
    uncertain_operation_id: str,
) -> dict[str, object]:
    import frappe
    from npi_integration.item_publish.runtime_fixture import synthetic_adapter_call_count
    from npi_integration.integration_operations.domain import canonical_hash

    with fresh_runtime_diagnostic_step("P807_SNAPSHOT_VALIDATE"):
        _validate_fixture(fixture_run_id, project_id)
    with fresh_runtime_diagnostic_step("P807_SNAPSHOT_OPERATION_ID"):
        uncertain_operation_id = _require_global_id(uncertain_operation_id)
    with fresh_runtime_diagnostic_step("P807_SNAPSHOT_REQUEST"):
        row = frappe.get_doc("NPI Item Publish Request", uncertain_operation_id)
    with fresh_runtime_diagnostic_step("P807_SNAPSHOT_ATTEMPTS"):
        attempts = frappe.get_all(
            "NPI Item Publish Attempt",
            filters={"request_global_id": uncertain_operation_id},
            fields=["name", "state", "attempt_hash"],
            order_by="name asc",
            limit_page_length=20,
        )
    with fresh_runtime_diagnostic_step("P807_SNAPSHOT_RESULTS"):
        results = frappe.get_all(
            "NPI Item Publish Result",
            filters={"request_global_id": uncertain_operation_id},
            fields=["name", "state", "result_hash"],
            order_by="name asc",
            limit_page_length=20,
        )
    with fresh_runtime_diagnostic_step("P807_SNAPSHOT_ACTIONS"):
        actions = frappe.get_all(
            "NPI Integration Action Receipt",
            filters={"operation_global_id": uncertain_operation_id},
            pluck="name",
            order_by="name asc",
            limit_page_length=20,
        )
    with fresh_runtime_diagnostic_step("P807_SNAPSHOT_DIGEST"):
        return {
            "adapterCalls": synthetic_adapter_call_count(),
            "digest": canonical_hash(
                {
                    "request": {
                        "name": str(row.name),
                        "state": str(row.state),
                        "optimisticVersion": int(row.optimistic_version),
                        "resultGlobalId": row.result_global_id or None,
                    },
                    "attempts": attempts,
                    "results": results,
                    "actions": actions,
                }
            ),
        }


def _operation_reference(project_id: str, operation_id: str) -> tuple[Any, Any]:
    import frappe
    from npi_core.foundation.security import Principal, ProjectAccess
    from npi_integration.integration_operations.domain import IntegrationOperationKind
    from npi_integration.integration_operations.frappe_repository import (
        FrappeIntegrationOperationsRepository,
    )

    row = frappe.get_doc("NPI Item Publish Request", operation_id)
    principal = Principal(
        ACTOR_USER,
        roles=frozenset(frappe.get_roles(ACTOR_USER)),
        project_access={project_id: ProjectAccess.ADMINISTER},
        tenant_id=TENANT_ID,
    )
    repository = FrappeIntegrationOperationsRepository(
        principal=principal,
        request_id=str(_fixture_uuid("observation-request")),
        trace_id=_fixture_trace("observation"),
    )
    project = frappe.get_doc("NPI Engineering Project", project_id)
    value = repository._operation_value(
        project,
        repository_module_spec("publish_item"),
        row,
    )
    require(
        value is not None
        and value.operation_kind is IntegrationOperationKind.PUBLISH_ITEM,
        "P8-07 reconciliation operation reference is unavailable",
    )
    return value, row


def repository_module_spec(operation_kind: str) -> Any:
    from npi_integration.integration_operations.domain import IntegrationOperationKind
    from npi_integration.integration_operations.frappe_repository import _SPECS

    return _SPECS[IntegrationOperationKind(operation_kind)]


def append_observation(
    fixture_run_id: str,
    project_id: str,
    operation_id: str,
    action_receipt_id: str,
) -> dict[str, object]:
    import frappe
    from npi_core.documents.frappe_repository import _database_datetime
    from npi_integration.integration_operations.domain import (
        INTEGRATION_OPERATIONS_SCHEMA_VERSION,
        IntegrationReconciliationObservation,
        ReconciliationAuthority,
        ReconciliationObservationState,
        ReconciliationObserverKind,
        canonical_hash,
    )
    from npi_integration.integration_operations.frappe_validation import (
        insert_integration_operations_support_document,
        integration_operations_write_capability,
    )

    with fresh_runtime_diagnostic_step("P807_OBSERVATION_VALIDATE"):
        worker = _validate_fixture(fixture_run_id, project_id)
    with fresh_runtime_diagnostic_step("P807_OBSERVATION_IDENTITIES"):
        operation_id = _require_global_id(operation_id)
        action_id = UUID(_require_global_id(action_receipt_id))
    with fresh_runtime_diagnostic_step("P807_OBSERVATION_REFERENCE"):
        value, row = _operation_reference(project_id, operation_id)
    with fresh_runtime_diagnostic_step("P807_OBSERVATION_ATTEMPT"):
        attempt_id = frappe.db.get_value(
            "NPI Item Publish Attempt",
            {"request_global_id": operation_id},
            "global_id",
            order_by="attempt_number desc",
        )
    with fresh_runtime_diagnostic_step("P807_OBSERVATION_VALUE"):
        evidence = {
            "sourceSnapshotHash": value.source_snapshot_hash,
            "targetIdempotencyKeyHash": value.target_idempotency_key_hash,
            "resultReferenceHash": None,
        }
        observed_at = datetime.now(UTC).replace(microsecond=0)
        observation = IntegrationReconciliationObservation(
            global_id=_fixture_uuid("reconciliation-observation"),
            operation=value,
            action_receipt_global_id=action_id,
            attempt_global_id=UUID(str(attempt_id)) if attempt_id else None,
            state=ReconciliationObservationState.TARGET_UNAVAILABLE,
            observer_kind=ReconciliationObserverKind.TRUSTED_OPERATION_SERVICE,
            authority=ReconciliationAuthority.NONE,
            response_authenticated=False,
            profile_id=str(row.profile_id),
            profile_version=int(row.profile_version),
            adapter_code="network-free-synthetic-v1",
            evidence_snapshot=evidence,
            evidence_hash=canonical_hash(evidence),
            observer_id=worker,
            trace_id=_fixture_trace("observation"),
            observed_at=observed_at,
        )
    with fresh_runtime_diagnostic_step("P807_OBSERVATION_SET_WORKER"):
        frappe.set_user(worker)
    allowed = frozenset({("NPI Integration Reconciliation Observation", "insert")})
    payload = observation.payload()
    with integration_operations_write_capability(
        service_actor_user_id=worker,
        scope=f"runtime:{observation.global_id}",
        allowed=allowed,
    ) as capability:
        with fresh_runtime_diagnostic_step("P807_OBSERVATION_DOCUMENT"):
            document = frappe.get_doc(
                {
                    "doctype": "NPI Integration Reconciliation Observation",
                    "global_id": str(observation.global_id),
                    "schema_version": INTEGRATION_OPERATIONS_SCHEMA_VERSION,
                    "tenant_id": value.tenant_id,
                    "project_global_id": str(value.project_global_id),
                    "operation_kind": value.operation_kind.value,
                    "operation_global_id": str(value.operation_global_id),
                    "source_global_id": str(value.source_global_id),
                    "operation_version": value.operation_version,
                    "raw_state": value.raw_state,
                    "shared_state": value.shared_state.value,
                    "source_snapshot_hash": value.source_snapshot_hash,
                    "target_idempotency_key_hash": value.target_idempotency_key_hash,
                    "action_receipt_global_id": str(action_id),
                    "attempt_global_id": str(observation.attempt_global_id) if observation.attempt_global_id else None,
                    "reconciliation_state": observation.state.value,
                    "observer_kind": observation.observer_kind.value,
                    "authority": observation.authority.value,
                    "response_authenticated": 0,
                    "profile_id": observation.profile_id,
                    "profile_version": observation.profile_version,
                    "adapter_code": observation.adapter_code,
                    "evidence_snapshot": evidence,
                    "evidence_hash": observation.evidence_hash,
                    "observer_id": worker,
                    "trace_id": observation.trace_id,
                    "observed_at": _database_datetime(observed_at),
                    "observation_snapshot": payload,
                    "observation_hash": observation.observation_hash,
                }
            )
        with fresh_runtime_diagnostic_step("P807_OBSERVATION_INSERT"):
            insert_integration_operations_support_document(
                document,
                capability=capability,
            )
    with fresh_runtime_diagnostic_step("P807_OBSERVATION_COMMIT"):
        frappe.db.commit()
    with fresh_runtime_diagnostic_step("P807_OBSERVATION_RESTORE"):
        frappe.set_user(ACTOR_USER)
    return {"appendOnly": True, "authoritativeSuccess": False, "observationCount": 1}


def verify_counts(
    fixture_run_id: str,
    project_id: str,
    uncertain_operation_id: str,
) -> dict[str, object]:
    import frappe

    with fresh_runtime_diagnostic_step("P807_COUNTS_VALIDATE"):
        _validate_fixture(fixture_run_id, project_id)
    with fresh_runtime_diagnostic_step("P807_COUNTS_IDENTITIES"):
        operation_ids = [
            str(_fixture_uuid("retryable-request")),
            _require_global_id(uncertain_operation_id),
        ]
    with fresh_runtime_diagnostic_step("P807_COUNTS_ACTIONS"):
        action_names = frappe.get_all(
            "NPI Integration Action Receipt",
            filters={"operation_global_id": ["in", operation_ids]},
            pluck="name",
            order_by="name asc",
            limit_page_length=10,
        )
    with fresh_runtime_diagnostic_step("P807_COUNTS_OBSERVATIONS"):
        observation_names = frappe.get_all(
            "NPI Integration Reconciliation Observation",
            filters={"project_global_id": project_id},
            pluck="name",
            order_by="name asc",
            limit_page_length=10,
        )
    with fresh_runtime_diagnostic_step("P807_COUNTS_RESULT"):
        return {
            "actionCount": len(action_names),
            "observationCount": len(observation_names),
            "rollbackClean": len(action_names) == 2 and len(observation_names) == 1,
        }


def verify_and_cleanup(
    fixture_run_id: str,
    project_id: str,
    uncertain_operation_id: str,
) -> dict[str, object]:
    import frappe

    worker = _validate_fixture(fixture_run_id, project_id)
    retryable_id = str(_fixture_uuid("retryable-request"))
    uncertain_operation_id = _require_global_id(uncertain_operation_id)
    operation_ids = [retryable_id, uncertain_operation_id]
    action_names = frappe.get_all(
        "NPI Integration Action Receipt",
        filters={"operation_global_id": ["in", operation_ids]},
        pluck="name",
        order_by="name asc",
        limit_page_length=10,
    )
    observation_names = frappe.get_all(
        "NPI Integration Reconciliation Observation",
        filters={"project_global_id": project_id},
        pluck="name",
        order_by="name asc",
        limit_page_length=10,
    )
    require(
        len(action_names) == 2 and len(observation_names) == 1,
        "P8-07 migration did not preserve exact action history",
    )
    action_immutable = False
    observation_immutable = False
    frappe.set_user(worker)
    action = frappe.get_doc("NPI Integration Action Receipt", action_names[0])
    action.outcome_state = "changed"
    try:
        action.save()
    except frappe.PermissionError:
        action_immutable = True
        frappe.db.rollback()
    observation = frappe.get_doc(
        "NPI Integration Reconciliation Observation",
        observation_names[0],
    )
    observation.reconciliation_state = "changed"
    try:
        observation.save()
    except frappe.PermissionError:
        observation_immutable = True
        frappe.db.rollback()
    require(action_immutable and observation_immutable, "P8-07 history mutation was not denied")

    attempt_names = frappe.get_all(
        "NPI Item Publish Attempt",
        filters={"request_global_id": retryable_id},
        pluck="name",
        limit_page_length=10,
    )
    result_names = frappe.get_all(
        "NPI Item Publish Result",
        filters={"request_global_id": retryable_id},
        pluck="name",
        limit_page_length=10,
    )
    frappe.db.delete(
        "NPI Integration Reconciliation Observation",
        {"name": ["in", observation_names]},
    )
    frappe.db.delete(
        "NPI Integration Action Receipt",
        {"name": ["in", action_names]},
    )
    frappe.db.delete(
        "NPI Audit Event",
        {
            "global_id": ["in", operation_ids],
            "operation": ["in", ["integration_operations.replay", "integration_operations.request_reconciliation"]],
        },
    )
    if result_names:
        frappe.db.delete("NPI Item Publish Result", {"name": ["in", result_names]})
    if attempt_names:
        frappe.db.delete("NPI Item Publish Attempt", {"name": ["in", attempt_names]})
    frappe.db.delete("NPI Outbox Message", {"request_global_id": retryable_id})
    frappe.db.delete("NPI Item Publish Request", {"name": retryable_id})
    frappe.db.delete(
        "NPI Item Publish Stream Guard",
        {"engineering_item_id": f"P807-RTRY-{FIXTURE_RUN_ID[:12]}"},
    )
    frappe.db.commit()
    cleaned = all(
        frappe.db.count(doctype, filters) == 0
        for doctype, filters in (
            ("NPI Integration Action Receipt", {"operation_global_id": ["in", operation_ids]}),
            ("NPI Integration Reconciliation Observation", {"project_global_id": project_id}),
            ("NPI Item Publish Request", {"name": retryable_id}),
            ("NPI Outbox Message", {"request_global_id": retryable_id}),
            ("NPI Item Publish Attempt", {"request_global_id": retryable_id}),
            ("NPI Item Publish Result", {"request_global_id": retryable_id}),
            ("NPI Item Publish Stream Guard", {"engineering_item_id": f"P807-RTRY-{FIXTURE_RUN_ID[:12]}"}),
        )
    )
    return {
        "actionHistoryImmutable": action_immutable,
        "cleanupComplete": cleaned,
        "migrationPreservedHistory": True,
        "observationHistoryImmutable": observation_immutable,
    }


def run_bench_fixture(method: str, kwargs: dict[str, object]) -> dict[str, Any]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "scripts")
    state = _DIAGNOSTIC_STATE.get()
    trace_id = state.get("trace_id") if isinstance(state, dict) else None
    path_value = environment.get(_DIAGNOSTIC_PATH_ENV)
    for variable in (
        _DIAGNOSTIC_SCOPE_ENV,
        _DIAGNOSTIC_TRACE_ENV,
        _DIAGNOSTIC_PATH_ENV,
    ):
        environment.pop(variable, None)
    diagnostic_active = (
        _fresh_runtime_diagnostics_enabled()
        and isinstance(trace_id, str)
        and _DIAGNOSTIC_TRACE_PATTERN.fullmatch(trace_id) is not None
    )
    if diagnostic_active:
        diagnostic_path = Path(str(path_value))
        require(
            diagnostic_path.is_absolute()
            and diagnostic_path.name == _DIAGNOSTIC_FILE_NAME,
            "P8-07 runtime diagnostic path is invalid",
        )
        environment[_DIAGNOSTIC_SCOPE_ENV] = _DIAGNOSTIC_SCOPE
        environment[_DIAGNOSTIC_TRACE_ENV] = trace_id
        environment[_DIAGNOSTIC_PATH_ENV] = str(diagnostic_path)
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as output:
        completed = subprocess.run(
            [
                str(BENCH_PATH / "env/bin/python"),
                str(Path(__file__).resolve()),
                "--bench-fixture",
                method,
                "--fixture-kwargs",
                json.dumps(kwargs, separators=(",", ":"), sort_keys=True),
            ],
            cwd=BENCH_PATH / "sites",
            env=environment,
            check=False,
            stdout=output,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        require(completed.returncode == 0, "P8-07 Bench fixture failed")
        output.seek(0)
        lines = [line for line in output if line.strip()]
    require(len(lines) == 1, "P8-07 Bench fixture output shape drifted")
    result = json.loads(lines[0])
    require(isinstance(result, dict), "P8-07 Bench fixture result is invalid")
    return result


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    with fresh_runtime_diagnostic_step("P807_FIXTURE_ARGUMENTS"):
        import frappe

        fixtures = {
            "append_observation": append_observation,
            "seed_retryable": seed_retryable,
            "snapshot": snapshot,
            "verify_and_cleanup": verify_and_cleanup,
            "verify_counts": verify_counts,
        }
        require(method in fixtures, "P8-07 Bench fixture is unavailable")
    with fresh_runtime_diagnostic_step("P807_FIXTURE_INIT"):
        frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    with fresh_runtime_diagnostic_step("P807_FIXTURE_CONNECT"):
        frappe.connect()
    try:
        call_code = _FRESH_FIXTURE_CALL_CODES.get(method)
        if call_code is None:
            result = fixtures[method](**kwargs)
        else:
            with fresh_runtime_diagnostic_step(call_code):
                result = fixtures[method](**kwargs)
        with fresh_runtime_diagnostic_step("P807_FIXTURE_COMMIT"):
            frappe.db.commit()
        with fresh_runtime_diagnostic_step("P807_FIXTURE_RESPONSE"):
            print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        with fresh_runtime_diagnostic_step("P807_FIXTURE_DESTROY"):
            frappe.destroy()


def run_scoped_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    trace_id = os.environ.get(_DIAGNOSTIC_TRACE_ENV, "")
    path_value = os.environ.get(_DIAGNOSTIC_PATH_ENV, "")
    path = Path(path_value) if path_value else None
    scope_is_exact = (
        _fresh_runtime_diagnostics_enabled()
        and os.environ.get(_DIAGNOSTIC_SCOPE_ENV) == _DIAGNOSTIC_SCOPE
        and _DIAGNOSTIC_TRACE_PATTERN.fullmatch(trace_id) is not None
        and path is not None
        and path.is_absolute()
        and path.name == _DIAGNOSTIC_FILE_NAME
    )
    with fresh_runtime_diagnostic_scope(trace_id if scope_is_exact else ""):
        run_local_bench_fixture(method, kwargs)


def _run_requested_runtime(arguments: Any) -> dict[str, object]:
    with fresh_runtime_diagnostic_step("P807_FRESH_INPUTS"):
        base_url = validate_local_fixture_inputs(
            arguments.base_url,
            "Administrator",
            ACTOR_USER,
        )
    with fresh_runtime_diagnostic_step("P807_FRESH_PROJECT_ID"):
        project_id = _require_project_id(arguments.project_id)
    with fresh_runtime_diagnostic_step("P807_FRESH_SECRET"):
        fixture_password = secret_from_environment("NPI_RUNTIME_FIXTURE_PASSWORD")
    if arguments.disabled_probe:
        return run_disabled_probe(base_url, fixture_password, project_id)
    if arguments.replay_only:
        return run_replay(base_url, fixture_password, project_id)
    if arguments.recovered_probe:
        return run_recovered(base_url, fixture_password, project_id)
    if arguments.post_migration_cleanup:
        return run_post_migration_cleanup(base_url, fixture_password, project_id)
    return run_fresh(base_url, fixture_password, project_id)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url")
    parser.add_argument("--project-id")
    parser.add_argument("--disabled-probe", action="store_true")
    parser.add_argument("--replay-only", action="store_true")
    parser.add_argument("--recovered-probe", action="store_true")
    parser.add_argument("--post-migration-cleanup", action="store_true")
    parser.add_argument("--bench-fixture")
    parser.add_argument("--fixture-kwargs")
    arguments = parser.parse_args()
    if arguments.bench_fixture:
        require(
            arguments.base_url is None
            and arguments.project_id is None
            and arguments.fixture_kwargs is not None
            and not any(
                (
                    arguments.disabled_probe,
                    arguments.replay_only,
                    arguments.recovered_probe,
                    arguments.post_migration_cleanup,
                )
            ),
            "P8-07 fixture invocation drifted",
        )
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "P8-07 fixture arguments are invalid")
        run_scoped_local_bench_fixture(arguments.bench_fixture, kwargs)
        return 0
    require(
        sum(
            map(
                int,
                (
                    arguments.disabled_probe,
                    arguments.replay_only,
                    arguments.recovered_probe,
                    arguments.post_migration_cleanup,
                ),
            )
        )
        <= 1,
        "P8-07 runtime mode is ambiguous",
    )
    fresh_requested = not any(
        (
            arguments.disabled_probe,
            arguments.replay_only,
            arguments.recovered_probe,
            arguments.post_migration_cleanup,
        )
    )
    if _fresh_runtime_diagnostics_enabled() and fresh_requested:
        trace_id = fresh_runtime_diagnostic_trace()
        previous_path = os.environ.get(_DIAGNOSTIC_PATH_ENV)
        with tempfile.TemporaryDirectory() as directory:
            diagnostic_path = Path(directory) / _DIAGNOSTIC_FILE_NAME
            os.environ[_DIAGNOSTIC_PATH_ENV] = str(diagnostic_path)
            try:
                with fresh_runtime_diagnostic_scope(trace_id):
                    try:
                        result = _run_requested_runtime(arguments)
                    except Exception:
                        diagnostic = read_fresh_runtime_diagnostic(
                            diagnostic_path,
                            expected_trace=trace_id,
                        )
                        if diagnostic is not None:
                            exception_type, code, validated_trace = diagnostic
                            print(
                                "P8-07 integration operations runtime diagnostic "
                                f"[diagnostic_code={code}; "
                                f"exception_type={exception_type}; "
                                f"trace_id={validated_trace}]",
                                file=sys.stderr,
                            )
                        return 1
            finally:
                if previous_path is None:
                    os.environ.pop(_DIAGNOSTIC_PATH_ENV, None)
                else:
                    os.environ[_DIAGNOSTIC_PATH_ENV] = previous_path
    else:
        result = _run_requested_runtime(arguments)
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
