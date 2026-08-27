from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator
from uuid import UUID, uuid5

import verify_document_runtime as document_runtime
import verify_item_publish_runtime as item_runtime
import verify_readiness_runtime as readiness_runtime
from verify_frappe_runtime import login, require, secret_from_environment, validate_local_fixture_inputs
from verify_project_runtime import bootstrap_csrf

ROOT = Path(__file__).resolve().parents[1]
BENCH_PATH = ROOT / "tmp" / "frappe-bench"
SITE_NAME = document_runtime.SITE_NAME
FIXTURE_RUN_ID = document_runtime.FIXTURE_RUN_ID
ACTOR_USER = readiness_runtime.ACTOR_USER
IDEMPOTENCY_KEY = f"p8-06-quality-link-{FIXTURE_RUN_ID}"
ACKNOWLEDGEMENT = (
    "I confirm this links only the exact observed formal quality reference. "
    "It does not write ERPNext or interpret a formal pass."
)
_NAMESPACE = UUID("2f927cab-16a1-4ac9-a9da-39fc8800b806")
QUALITY_LINK_RUNTIME_STAGE_DIAGNOSTICS_ENABLED = False
QUALITY_LINK_PREPARE_PROJECTION_DIAGNOSTICS_ENABLED = False
QUALITY_LINK_PREPARE_BOOTSTRAP_DIAGNOSTICS_ENABLED = False
QUALITY_LINK_POST_PERMISSION_DIAGNOSTICS_ENABLED = False
QUALITY_LINK_CREATE_RESPONSE_DIAGNOSTICS_ENABLED = False
QUALITY_LINK_POST_RECEIPT_DIAGNOSTICS_ENABLED = False
QUALITY_LINK_PARENT_DOWNSTREAM_DIAGNOSTICS_ENABLED = False
QUALITY_LINK_POST_PROJECTION_PERMISSION_DIAGNOSTICS_ENABLED = False
QUALITY_LINK_FULL_BOUNDARY_DIAGNOSTICS_ENABLED = False
QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED = False
QUALITY_LINK_POST_WRITE_FULL_BOUNDARY_DIAGNOSTICS_ENABLED = False
QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED = False
QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = True
QUALITY_LINK_RUNTIME_DIAGNOSTIC_CODES = (
    "P806_QUALITY_BOOTSTRAP_SECRET",
    "P806_QUALITY_ADMIN_LOGIN",
    "P806_QUALITY_PROJECT_CONTEXT",
    "P806_QUALITY_ACTOR_LOGIN",
    "P806_QUALITY_CSRF",
    "P806_QUALITY_READINESS_HTTP",
    "P806_QUALITY_READINESS_SHAPE",
    "P806_QUALITY_PREPARE_PROJECTION",
    "P806_QUALITY_CURRENT_TRUTH",
    "P806_QUALITY_CREATE_HTTP",
    "P806_QUALITY_CREATE_SHAPE",
    "P806_QUALITY_REPLAY_HTTP",
    "P806_QUALITY_REPLAY_SHAPE",
    "P806_QUALITY_STALE_HTTP",
    "P806_QUALITY_LIST_HTTP",
    "P806_QUALITY_LIST_SHAPE",
    "P806_QUALITY_CLEANUP",
)
QUALITY_LINK_PREPARE_PROJECTION_PARENT_CODES = (
    "P806_QUALITY_PREPARE_PARENT_SUBPROCESS",
    "P806_QUALITY_PREPARE_PARENT_CHILD_STATUS",
    "P806_QUALITY_PREPARE_PARENT_RESULT_PARSE",
    "P806_QUALITY_PREPARE_PARENT_RESULT_SHAPE",
)
QUALITY_LINK_PREPARE_BOOTSTRAP_CODES = (
    "P806_QUALITY_PREPARE_BOOTSTRAP_IMPORT_FRAPPE",
    "P806_QUALITY_PREPARE_BOOTSTRAP_IMPORT_REPOSITORY",
    "P806_QUALITY_PREPARE_BOOTSTRAP_ARGUMENTS",
    "P806_QUALITY_PREPARE_BOOTSTRAP_INIT",
    "P806_QUALITY_PREPARE_BOOTSTRAP_CONTEXT_ACTIVE",
)
QUALITY_LINK_PREPARE_PROJECTION_SERVER_CODES = frozenset(
    {
        "P806_QUALITY_PREPARE_CHILD_INIT",
        "P806_QUALITY_PREPARE_CHILD_CONNECT",
        "P806_QUALITY_PREPARE_SITE_VALIDATE",
        "P806_QUALITY_PREPARE_SET_ACTOR",
        "P806_QUALITY_PREPARE_PRINCIPAL",
        "P806_QUALITY_PREPARE_REPOSITORY",
        "P806_QUALITY_PREPARE_TARGET",
        "P806_QUALITY_PREPARE_RESULT",
        "P806_QUALITY_PREPARE_APPLY",
        "P806_QUALITY_PREPARE_COLLECTION_AUTHORIZE",
        "P806_QUALITY_PREPARE_COLLECTION_READ",
        "P806_QUALITY_PREPARE_COLLECTION_CARDINALITY",
        "P806_QUALITY_PREPARE_COMMIT",
        "P806_QUALITY_PREPARE_RESPONSE",
        "P806_QUALITY_PREPARE_DESTROY",
        "P806_QUALITY_PROJECTION_AUTHORIZE",
        "P806_QUALITY_PROJECTION_TARGET",
        "P806_QUALITY_PROJECTION_SCOPE",
        "P806_QUALITY_PROJECTION_RESULT",
        "P806_QUALITY_PROJECTION_NORMALIZE",
        "P806_QUALITY_PROJECTION_PAYLOAD",
        "P806_QUALITY_PROJECTION_STREAM",
        "P806_QUALITY_PROJECTION_HEAD_LOCK",
        "P806_QUALITY_PROJECTION_HEAD_IDENTITY",
        "P806_QUALITY_PROJECTION_EVENT_ROWS",
        "P806_QUALITY_PROJECTION_EVENT_BOUND",
        "P806_QUALITY_PROJECTION_REPLAY",
        "P806_QUALITY_PROJECTION_CURRENT",
        "P806_QUALITY_PROJECTION_CLASSIFY",
        "P806_QUALITY_PROJECTION_FRESHNESS",
        "P806_QUALITY_PROJECTION_OBSERVATION_VALUES",
        "P806_QUALITY_PROJECTION_HEAD_VALUES",
        "P806_QUALITY_PROJECTION_TRANSACTION",
        "P806_QUALITY_PROJECTION_OBSERVATION_INSERT",
        "P806_QUALITY_PROJECTION_HEAD_INSERT",
        "P806_QUALITY_PROJECTION_HEAD_UPDATE",
        "P806_QUALITY_PROJECTION_HEAD_SAVE",
        "P806_QUALITY_PROJECTION_AUDIT",
        "P806_QUALITY_PROJECTION_OUTCOME",
    }
)
QUALITY_LINK_CREATE_RESPONSE_PARENT_CODES = (
    "P806_QUALITY_CREATE_STATUS_INVALID",
    "P806_QUALITY_CREATE_STATUS_INFORMATIONAL",
    "P806_QUALITY_CREATE_STATUS_SUCCESS_NON_201",
    "P806_QUALITY_CREATE_STATUS_REDIRECTION",
    "P806_QUALITY_CREATE_STATUS_CLIENT_ERROR",
    "P806_QUALITY_CREATE_STATUS_SERVER_ERROR",
    "P806_QUALITY_CREATE_BODY_SHAPE",
)
QUALITY_LINK_CREATE_RESPONSE_SERVER_CODES = frozenset(
    {
        "P806_QUALITY_CREATE_API_CSRF",
        "P806_QUALITY_CREATE_API_CONTEXT",
        "P806_QUALITY_CREATE_API_REQUEST_FIELDS",
        "P806_QUALITY_CREATE_API_ACKNOWLEDGEMENT",
        "P806_QUALITY_CREATE_API_SOURCE_KIND",
        "P806_QUALITY_CREATE_API_INPUT_PARSE",
        "P806_QUALITY_CREATE_API_REPOSITORY_COMMAND",
        "P806_QUALITY_CREATE_API_OUTCOME",
        "P806_QUALITY_CREATE_API_COMMIT",
        "P806_QUALITY_CREATE_API_RESPONSE",
        "P806_QUALITY_CREATE_REPOSITORY_PROJECT",
        "P806_QUALITY_CREATE_REPOSITORY_COMMAND_IDENTITY",
        "P806_QUALITY_CREATE_REPOSITORY_REPLAY",
        "P806_QUALITY_CREATE_REPOSITORY_SOURCE",
        "P806_QUALITY_CREATE_REPOSITORY_OBSERVATION",
        "P806_QUALITY_CREATE_REPOSITORY_STREAM",
        "P806_QUALITY_CREATE_REPOSITORY_HEAD",
        "P806_QUALITY_CREATE_REPOSITORY_REVISION",
        "P806_QUALITY_CREATE_REPOSITORY_RESPONSE",
        "P806_QUALITY_CREATE_REPOSITORY_TRANSACTION",
        "P806_QUALITY_CREATE_REPOSITORY_RECEIPT_INSERT",
        "P806_QUALITY_CREATE_REPOSITORY_REVISION_INSERT",
        "P806_QUALITY_CREATE_REPOSITORY_HEAD_INSERT",
        "P806_QUALITY_CREATE_REPOSITORY_HEAD_SAVE",
        "P806_QUALITY_CREATE_REPOSITORY_AUDIT",
        "P806_QUALITY_CREATE_REPOSITORY_RECEIPT_SEAL",
        "P806_QUALITY_CREATE_REPOSITORY_OUTCOME",
    }
)
QUALITY_LINK_CREATE_RESPONSE_DIAGNOSTIC_HEADER = (
    "X-NPI-P806-Quality-Create-Diagnostic"
)
QUALITY_LINK_CREATE_RESPONSE_DIAGNOSTIC_SCOPE = (
    "p8-06-quality-link-create-response-v1"
)
_PREPARE_PROJECTION_DIAGNOSTIC_SCOPE = (
    "p8-06-quality-link-prepare-projection-v1"
)
_PREPARE_PROJECTION_DIAGNOSTIC_ENV = (
    "NPI_P806_QUALITY_PREPARE_PROJECTION_DIAGNOSTIC_SCOPE"
)
_DIAGNOSTIC_PATH_ENV = "NPI_QUALITY_LINK_RUNTIME_DIAGNOSTIC_PATH"
_DIAGNOSTIC_RECORD_KEYS = frozenset({"code", "exceptionType", "traceId"})
_DIAGNOSTIC_RECORD_LIMIT = 4096
_TRACE_PATTERN = re.compile(r"^trace-[a-f0-9]{32}$")
_TYPE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,127}$")
_DIAGNOSTIC_STATE: ContextVar[dict[str, object] | None] = ContextVar(
    "p806_quality_link_runtime_diagnostic_state",
    default=None,
)


def quality_link_runtime_diagnostic_trace() -> str:
    return f"trace-{uuid5(_NAMESPACE, f'diagnostic:{FIXTURE_RUN_ID}').hex}"


def _full_boundary_diagnostics_enabled() -> bool:
    return QUALITY_LINK_FULL_BOUNDARY_DIAGNOSTICS_ENABLED and not any(
        (
            QUALITY_LINK_RUNTIME_STAGE_DIAGNOSTICS_ENABLED,
            QUALITY_LINK_PREPARE_PROJECTION_DIAGNOSTICS_ENABLED,
            QUALITY_LINK_PREPARE_BOOTSTRAP_DIAGNOSTICS_ENABLED,
            QUALITY_LINK_POST_PERMISSION_DIAGNOSTICS_ENABLED,
            QUALITY_LINK_CREATE_RESPONSE_DIAGNOSTICS_ENABLED,
            QUALITY_LINK_POST_RECEIPT_DIAGNOSTICS_ENABLED,
            QUALITY_LINK_PARENT_DOWNSTREAM_DIAGNOSTICS_ENABLED,
            QUALITY_LINK_POST_PROJECTION_PERMISSION_DIAGNOSTICS_ENABLED,
            QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED,
            QUALITY_LINK_POST_WRITE_FULL_BOUNDARY_DIAGNOSTICS_ENABLED,
            QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED,
            QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED,
        )
    )


@contextmanager
def quality_link_runtime_diagnostic_scope(trace_id: str) -> Iterator[None]:
    state = None
    if (
        (
            QUALITY_LINK_RUNTIME_STAGE_DIAGNOSTICS_ENABLED
            or QUALITY_LINK_PREPARE_PROJECTION_DIAGNOSTICS_ENABLED
            or QUALITY_LINK_PREPARE_BOOTSTRAP_DIAGNOSTICS_ENABLED
            or QUALITY_LINK_POST_PERMISSION_DIAGNOSTICS_ENABLED
            or QUALITY_LINK_CREATE_RESPONSE_DIAGNOSTICS_ENABLED
            or QUALITY_LINK_POST_RECEIPT_DIAGNOSTICS_ENABLED
            or QUALITY_LINK_PARENT_DOWNSTREAM_DIAGNOSTICS_ENABLED
            or QUALITY_LINK_POST_PROJECTION_PERMISSION_DIAGNOSTICS_ENABLED
            or QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED
            or QUALITY_LINK_POST_WRITE_FULL_BOUNDARY_DIAGNOSTICS_ENABLED
            or QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED
            or QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED
            or _full_boundary_diagnostics_enabled()
        )
        and _TRACE_PATTERN.fullmatch(trace_id) is not None
    ):
        state = {"trace_id": trace_id, "recorded": False}
    token = _DIAGNOSTIC_STATE.set(state)
    try:
        yield
    finally:
        _DIAGNOSTIC_STATE.reset(token)


@contextmanager
def quality_link_runtime_diagnostic_step(code: str) -> Iterator[None]:
    try:
        yield
    except Exception as error:
        _record_quality_link_runtime_diagnostic(code, error)
        raise


def _record_quality_link_runtime_diagnostic(code: str, error: Exception) -> None:
    try:
        state = _DIAGNOSTIC_STATE.get()
        exception_type = type(error).__name__
        if (
            state is None
            or state["recorded"] is True
            or (
                code not in QUALITY_LINK_RUNTIME_DIAGNOSTIC_CODES
                and code not in QUALITY_LINK_PREPARE_PROJECTION_PARENT_CODES
                and code not in QUALITY_LINK_PREPARE_BOOTSTRAP_CODES
                and code not in QUALITY_LINK_CREATE_RESPONSE_PARENT_CODES
            )
            or (
                code in QUALITY_LINK_RUNTIME_DIAGNOSTIC_CODES
                and not (
                    QUALITY_LINK_RUNTIME_STAGE_DIAGNOSTICS_ENABLED
                    or QUALITY_LINK_POST_PERMISSION_DIAGNOSTICS_ENABLED
                    or QUALITY_LINK_PARENT_DOWNSTREAM_DIAGNOSTICS_ENABLED
                    or QUALITY_LINK_POST_WRITE_FULL_BOUNDARY_DIAGNOSTICS_ENABLED
                    or QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED
                    or _full_boundary_diagnostics_enabled()
                )
            )
            or (
                code in QUALITY_LINK_PREPARE_PROJECTION_PARENT_CODES
                and not (
                    QUALITY_LINK_PREPARE_PROJECTION_DIAGNOSTICS_ENABLED
                    or QUALITY_LINK_PREPARE_BOOTSTRAP_DIAGNOSTICS_ENABLED
                    or QUALITY_LINK_POST_PERMISSION_DIAGNOSTICS_ENABLED
                    or QUALITY_LINK_POST_PROJECTION_PERMISSION_DIAGNOSTICS_ENABLED
                    or QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED
                    or QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED
                    or _full_boundary_diagnostics_enabled()
                )
            )
            or (
                code in QUALITY_LINK_PREPARE_BOOTSTRAP_CODES
                and not (
                    QUALITY_LINK_PREPARE_BOOTSTRAP_DIAGNOSTICS_ENABLED
                    or QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED
                    or QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED
                    or _full_boundary_diagnostics_enabled()
                )
            )
            or (
                code in QUALITY_LINK_CREATE_RESPONSE_PARENT_CODES
                and not (
                    QUALITY_LINK_CREATE_RESPONSE_DIAGNOSTICS_ENABLED
                    or QUALITY_LINK_POST_RECEIPT_DIAGNOSTICS_ENABLED
                    or QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED
                )
            )
            or _TYPE_PATTERN.fullmatch(exception_type) is None
        ):
            return
        state["recorded"] = True
        _write_quality_link_runtime_diagnostic(
            {
                "code": code,
                "exceptionType": exception_type,
                "traceId": str(state["trace_id"]),
            }
        )
    except Exception:
        # Diagnostics must never replace the original verifier failure.
        pass


def _write_quality_link_runtime_diagnostic(record: dict[str, str]) -> None:
    path_value = os.environ.get(_DIAGNOSTIC_PATH_ENV)
    if not isinstance(path_value, str) or not path_value:
        return
    path = Path(path_value)
    if not path.is_absolute() or path.name != "p8-06-quality-link-runtime-diagnostic.json":
        return
    payload = json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(payload)


def read_quality_link_runtime_diagnostic(
    path: Path,
    *,
    expected_trace: str,
) -> tuple[str, str, str] | None:
    if _TRACE_PATTERN.fullmatch(expected_trace) is None:
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
        or code not in _active_quality_link_runtime_diagnostic_codes()
        or not isinstance(exception_type, str)
        or _TYPE_PATTERN.fullmatch(exception_type) is None
        or trace_id != expected_trace
    ):
        return None
    return exception_type, code, expected_trace


def _active_quality_link_runtime_diagnostic_codes() -> frozenset[str]:
    if QUALITY_LINK_PREPARE_BOOTSTRAP_DIAGNOSTICS_ENABLED:
        return (
            frozenset(QUALITY_LINK_PREPARE_PROJECTION_PARENT_CODES)
            .union(QUALITY_LINK_PREPARE_BOOTSTRAP_CODES)
            .union(QUALITY_LINK_PREPARE_PROJECTION_SERVER_CODES)
        )
    if QUALITY_LINK_POST_PERMISSION_DIAGNOSTICS_ENABLED:
        return (
            frozenset(QUALITY_LINK_RUNTIME_DIAGNOSTIC_CODES)
            .union(QUALITY_LINK_PREPARE_PROJECTION_PARENT_CODES)
            .union(QUALITY_LINK_PREPARE_PROJECTION_SERVER_CODES)
        )
    if QUALITY_LINK_POST_PROJECTION_PERMISSION_DIAGNOSTICS_ENABLED:
        return frozenset(QUALITY_LINK_PREPARE_PROJECTION_PARENT_CODES).union(
            QUALITY_LINK_PREPARE_PROJECTION_SERVER_CODES
        )
    if QUALITY_LINK_PREPARE_PROJECTION_DIAGNOSTICS_ENABLED:
        return frozenset(QUALITY_LINK_PREPARE_PROJECTION_PARENT_CODES).union(
            QUALITY_LINK_PREPARE_PROJECTION_SERVER_CODES
        )
    if QUALITY_LINK_RUNTIME_STAGE_DIAGNOSTICS_ENABLED:
        return frozenset(QUALITY_LINK_RUNTIME_DIAGNOSTIC_CODES)
    if QUALITY_LINK_PARENT_DOWNSTREAM_DIAGNOSTICS_ENABLED:
        return frozenset(QUALITY_LINK_RUNTIME_DIAGNOSTIC_CODES).union(
            QUALITY_LINK_CREATE_RESPONSE_SERVER_CODES
        )
    if QUALITY_LINK_POST_WRITE_FULL_BOUNDARY_DIAGNOSTICS_ENABLED:
        return frozenset(QUALITY_LINK_RUNTIME_DIAGNOSTIC_CODES).union(
            QUALITY_LINK_CREATE_RESPONSE_SERVER_CODES
        )
    if QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED:
        return (
            frozenset(QUALITY_LINK_PREPARE_PROJECTION_PARENT_CODES)
            .union(QUALITY_LINK_PREPARE_BOOTSTRAP_CODES)
            .union(QUALITY_LINK_PREPARE_PROJECTION_SERVER_CODES)
        )
    if QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED:
        return (
            frozenset(QUALITY_LINK_RUNTIME_DIAGNOSTIC_CODES)
            .union(QUALITY_LINK_PREPARE_PROJECTION_PARENT_CODES)
            .union(QUALITY_LINK_PREPARE_BOOTSTRAP_CODES)
            .union(QUALITY_LINK_PREPARE_PROJECTION_SERVER_CODES)
            .union(QUALITY_LINK_CREATE_RESPONSE_SERVER_CODES)
        )
    if (
        QUALITY_LINK_CREATE_RESPONSE_DIAGNOSTICS_ENABLED
        or QUALITY_LINK_POST_RECEIPT_DIAGNOSTICS_ENABLED
        or QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED
    ):
        return frozenset(QUALITY_LINK_CREATE_RESPONSE_PARENT_CODES).union(
            QUALITY_LINK_CREATE_RESPONSE_SERVER_CODES
        )
    if _full_boundary_diagnostics_enabled():
        return (
            frozenset(QUALITY_LINK_RUNTIME_DIAGNOSTIC_CODES)
            .union(QUALITY_LINK_PREPARE_PROJECTION_PARENT_CODES)
            .union(QUALITY_LINK_PREPARE_BOOTSTRAP_CODES)
            .union(QUALITY_LINK_PREPARE_PROJECTION_SERVER_CODES)
        )
    return frozenset()


@contextmanager
def _prepare_parent_diagnostic_step(
    method: str,
    code: str,
) -> Iterator[None]:
    if method == "prepare_projection":
        with quality_link_runtime_diagnostic_step(code):
            yield
        return
    yield


@contextmanager
def _prepare_bootstrap_diagnostic_step(
    method: str,
    code: str,
) -> Iterator[None]:
    if method == "prepare_projection":
        with quality_link_runtime_diagnostic_step(code):
            yield
        return
    yield


def _prepare_projection_diagnostics_enabled() -> bool:
    return (
        QUALITY_LINK_PREPARE_PROJECTION_DIAGNOSTICS_ENABLED
        or QUALITY_LINK_PREPARE_BOOTSTRAP_DIAGNOSTICS_ENABLED
        or QUALITY_LINK_POST_PERMISSION_DIAGNOSTICS_ENABLED
        or QUALITY_LINK_CREATE_RESPONSE_DIAGNOSTICS_ENABLED
        or QUALITY_LINK_POST_PROJECTION_PERMISSION_DIAGNOSTICS_ENABLED
        or QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED
        or QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED
        or _full_boundary_diagnostics_enabled()
    )


def _create_response_parent_code(status: object) -> str | None:
    if type(status) is not int or status < 100 or status > 599:
        return "P806_QUALITY_CREATE_STATUS_INVALID"
    if status == 201:
        return None
    if status < 200:
        return "P806_QUALITY_CREATE_STATUS_INFORMATIONAL"
    if status < 300:
        return "P806_QUALITY_CREATE_STATUS_SUCCESS_NON_201"
    if status < 400:
        return "P806_QUALITY_CREATE_STATUS_REDIRECTION"
    if status < 500:
        return "P806_QUALITY_CREATE_STATUS_CLIENT_ERROR"
    return "P806_QUALITY_CREATE_STATUS_SERVER_ERROR"


def _create_response_request(
    actor: object,
    base_url: str,
    path: str,
    *,
    actor_csrf: str,
    payload: dict[str, object],
) -> object:
    if not (
        QUALITY_LINK_CREATE_RESPONSE_DIAGNOSTICS_ENABLED
        or QUALITY_LINK_POST_RECEIPT_DIAGNOSTICS_ENABLED
        or QUALITY_LINK_PARENT_DOWNSTREAM_DIAGNOSTICS_ENABLED
        or QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED
        or QUALITY_LINK_POST_WRITE_FULL_BOUNDARY_DIAGNOSTICS_ENABLED
        or QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED
    ):
        return document_runtime.npi_request(
            actor,
            base_url,
            path,
            method="POST",
            payload=payload,
            csrf_token=actor_csrf,
            idempotency_key=IDEMPOTENCY_KEY,
            query_key="p806-link",
        )
    trace_id = quality_link_runtime_diagnostic_trace()
    headers = document_runtime.command_headers(actor_csrf, IDEMPOTENCY_KEY)
    headers["X-Trace-ID"] = trace_id
    headers[QUALITY_LINK_CREATE_RESPONSE_DIAGNOSTIC_HEADER] = (
        QUALITY_LINK_CREATE_RESPONSE_DIAGNOSTIC_SCOPE
    )
    cursors = item_runtime._replay_diagnostic_log_cursors()
    result = document_runtime.request(
        actor,
        base_url,
        path,
        method="POST",
        payload=payload,
        request_headers=headers,
    )
    require(
        result.headers.get("X-Request-ID") == headers["X-Request-ID"],
        "NPI request identity was not echoed for formal quality link create",
    )
    require(
        result.headers.get("Cache-Control") == "private, no-store",
        "NPI cache control drifted for formal quality link create",
    )
    parent_code = _create_response_parent_code(getattr(result, "status", None))
    if parent_code is not None:
        diagnostic = item_runtime._sanitized_server_log_diagnostic(
            trace_id,
            cursors,
            code_prefix="P806_QUALITY_CREATE_",
            allowed_codes=QUALITY_LINK_CREATE_RESPONSE_SERVER_CODES,
        )
        if diagnostic is not None:
            exception_type, code, validated_trace = diagnostic
            try:
                _write_quality_link_runtime_diagnostic(
                    {
                        "code": code,
                        "exceptionType": exception_type,
                        "traceId": validated_trace,
                    }
                )
            except OSError:
                pass
        with quality_link_runtime_diagnostic_step(parent_code):
            require(False, "P8-06 create response HTTP class drifted")
    with quality_link_runtime_diagnostic_step(
        "P806_QUALITY_CREATE_BODY_SHAPE"
    ):
        require(
            isinstance(getattr(result, "body", None), dict),
            "P8-06 create response shape drifted",
        )
    return document_runtime.HttpResult(
        result.status,
        result.headers,
        result.body,
        request_id=headers["X-Request-ID"],
        trace_id=trace_id,
    )


def _body(result: object, *, status: int) -> dict[str, Any]:
    require(getattr(result, "status", None) == status, "P8-06 runtime HTTP boundary drifted")
    value = getattr(result, "body", None)
    require(isinstance(value, dict), "P8-06 runtime response is not an object")
    return value


def run_bench_fixture(method: str, kwargs: dict[str, object]) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT) + (
        os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else ""
    )
    for variable in (
        "NPI_RUNTIME_ADMINISTRATOR_PASSWORD",
        "NPI_RUNTIME_FIXTURE_PASSWORD",
        "NPI_ADMINISTRATOR_PASSWORD",
        "NPI_DATABASE_ROOT_PASSWORD",
    ):
        environment.pop(variable, None)
    diagnostic_trace_id = kwargs.get("diagnostic_trace_id")
    diagnostic_cursors = (
        item_runtime._replay_diagnostic_log_cursors()
        if method == "prepare_projection"
        and _prepare_projection_diagnostics_enabled()
        and isinstance(diagnostic_trace_id, str)
        and _TRACE_PATTERN.fullmatch(diagnostic_trace_id) is not None
        else None
    )
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as output:
        with _prepare_parent_diagnostic_step(
            method,
            "P806_QUALITY_PREPARE_PARENT_SUBPROCESS"
        ):
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
        if completed.returncode != 0 and diagnostic_cursors is not None:
            diagnostic = item_runtime._sanitized_server_log_diagnostic(
                diagnostic_trace_id,
                diagnostic_cursors,
                code_prefix="P806_QUALITY_",
                allowed_codes=QUALITY_LINK_PREPARE_PROJECTION_SERVER_CODES,
            )
            if diagnostic is not None:
                exception_type, code, validated_trace = diagnostic
                try:
                    _write_quality_link_runtime_diagnostic(
                        {
                            "code": code,
                            "exceptionType": exception_type,
                            "traceId": validated_trace,
                        }
                    )
                except OSError:
                    pass
        with _prepare_parent_diagnostic_step(
            method,
            "P806_QUALITY_PREPARE_PARENT_CHILD_STATUS"
        ):
            require(completed.returncode == 0, "P8-06 Bench fixture failed")
        output.seek(0)
        lines = [line for line in output if line.strip()]
    with _prepare_parent_diagnostic_step(
        method,
        "P806_QUALITY_PREPARE_PARENT_RESULT_PARSE"
    ):
        result = json.loads(lines[-1]) if lines else None
    with _prepare_parent_diagnostic_step(
        method,
        "P806_QUALITY_PREPARE_PARENT_RESULT_SHAPE"
    ):
        require(isinstance(result, dict), "P8-06 Bench fixture result is invalid")
    return result


def prepare_projection(*, project_id: str, readiness_id: str) -> dict[str, object]:
    import frappe
    from npi_core.foundation.security import Principal
    from npi_integration.projections.domain import (
        AdapterMode,
        ProjectionAvailability,
        ProjectionContext,
        ProjectionKind,
        ProjectionReaderResult,
        ProjectionRefreshTarget,
        ProjectionScopeKind,
    )
    from npi_integration.projections.frappe_repository import (
        FrappeProjectionRepository,
        quality_link_prepare_projection_step,
    )

    with quality_link_prepare_projection_step("P806_QUALITY_PREPARE_PRINCIPAL"):
        principal = Principal(
            user_id=ACTOR_USER,
            roles=frozenset(frappe.get_roles(ACTOR_USER)),
            tenant_id=document_runtime.TENANT_ID,
            is_external=False,
        )
    with quality_link_prepare_projection_step("P806_QUALITY_PREPARE_REPOSITORY"):
        repository = FrappeProjectionRepository(
            principal=principal,
            request_id=str(uuid5(_NAMESPACE, f"request:{FIXTURE_RUN_ID}")),
            trace_id=f"trace-p806-runtime-{FIXTURE_RUN_ID[:12]}",
            freshness_policies={
                ProjectionKind.FORMAL_QUALITY_STATUS: (
                    "p8-06-runtime-quality-v1",
                    86400,
                )
            },
        )
    with quality_link_prepare_projection_step("P806_QUALITY_PREPARE_TARGET"):
        target = ProjectionRefreshTarget(
            context=ProjectionContext(
                tenant_id=document_runtime.TENANT_ID,
                project_global_id=UUID(project_id),
                scope_kind=ProjectionScopeKind.READINESS,
                scope_global_id=UUID(readiness_id),
            ),
            kind=ProjectionKind.FORMAL_QUALITY_STATUS,
            source_object_id="QUALITY-P806-RUNTIME",
        )
    with quality_link_prepare_projection_step("P806_QUALITY_PREPARE_RESULT"):
        result = ProjectionReaderResult(
            kind=ProjectionKind.FORMAL_QUALITY_STATUS,
            adapter_mode=AdapterMode.SANDBOX,
            source_environment="disposable-test",
            source_object_id="QUALITY-P806-RUNTIME",
            source_version="p8-06-runtime-v1",
            source_modified_at=datetime(2026, 8, 26, 8, 0, tzinfo=UTC),
            availability=ProjectionAvailability.AVAILABLE,
            values={
                "recordKind": "quality_inspection",
                "statusCode": "submitted",
                "resultCode": "accepted",
                "observedAt": "2026-08-26T08:00:00Z",
            },
        )
    with quality_link_prepare_projection_step("P806_QUALITY_PREPARE_APPLY"):
        outcome = repository.apply_observation(
            project_global_id=UUID(project_id),
            target=target,
            result=result,
            event_id=uuid5(_NAMESPACE, f"event:{FIXTURE_RUN_ID}"),
            received_at=datetime(2026, 8, 26, 8, 1, tzinfo=UTC),
            correlation_id=uuid5(_NAMESPACE, f"correlation:{FIXTURE_RUN_ID}"),
        )
    with quality_link_prepare_projection_step(
        "P806_QUALITY_PREPARE_COLLECTION_AUTHORIZE"
    ):
        access = repository.authorize_project(UUID(project_id))
    with quality_link_prepare_projection_step("P806_QUALITY_PREPARE_COLLECTION_READ"):
        collection = repository.project_collection(
            access,
            kind="formal_quality_status",
        )
    with quality_link_prepare_projection_step(
        "P806_QUALITY_PREPARE_COLLECTION_CARDINALITY"
    ):
        matches = [
            item
            for item in collection["items"]
            if item["scopeKind"] == "readiness"
            and item["scopeGlobalId"] == readiness_id
        ]
        require(len(matches) == 1, "P8-06 projection fixture cardinality drifted")
    return {"item": matches[0], "replayed": outcome.replayed}


def cleanup(*, project_id: str, readiness_id: str) -> dict[str, object]:
    import frappe

    revisions = frappe.get_all(
        "NPI Formal Quality Link Revision",
        filters={"project_global_id": project_id, "source_kind": "readiness_assessment", "source_global_id": readiness_id},
        pluck="global_id",
        limit_page_length=20,
    )
    for revision_id in revisions:
        frappe.db.delete("NPI Audit Event", {"global_id": str(revision_id), "operation": "formal_quality_link.link_observed_reference"})
    frappe.db.delete("NPI Formal Quality Link Command Idempotency", {"project_global_id": project_id, "operation": "link_observed_formal_quality_reference"})
    frappe.db.delete("NPI Formal Quality Link Head", {"project_global_id": project_id, "source_kind": "readiness_assessment", "source_global_id": readiness_id})
    frappe.db.delete("NPI Formal Quality Link Revision", {"project_global_id": project_id, "source_kind": "readiness_assessment", "source_global_id": readiness_id})
    frappe.db.delete("NPI ERP Projection Head", {"project_global_id": project_id, "projection_kind": "formal_quality_status", "scope_kind": "readiness", "scope_global_id": readiness_id})
    frappe.db.delete("NPI ERP Projection Observation", {"project_global_id": project_id, "projection_kind": "formal_quality_status", "scope_kind": "readiness", "scope_global_id": readiness_id})
    return {"cleaned": True}


def _exercise_link(
    *,
    actor: object,
    actor_csrf: str,
    base_url: str,
    current: dict[str, object],
    item: object,
    project_id: str,
    readiness_id: str,
) -> dict[str, object]:
    with quality_link_runtime_diagnostic_step("P806_QUALITY_CURRENT_TRUTH"):
        truth = item.get("currentTruth") if isinstance(item, dict) else None
        require(isinstance(truth, dict), "P8-06 formal quality current truth is unavailable")
        path = f"/api/npi/v1/projects/{project_id}/formal-quality-links:link-observed-reference"
        payload = {
            "sourceKind": "readiness_assessment",
            "sourceGlobalId": readiness_id,
            "expectedSourceVersion": current["instanceVersion"],
            "expectedSourceSnapshotHash": current["snapshotHash"],
            "formalObservationGlobalId": truth["observationGlobalId"],
            "expectedProjectionHeadGlobalId": truth["headGlobalId"],
            "expectedProjectionHeadVersion": truth["headOptimisticVersion"],
            "expectedProjectionHeadHash": truth["headHash"],
            "expectedLinkHeadVersion": 0,
            "acknowledgement": ACKNOWLEDGEMENT,
        }
    with quality_link_runtime_diagnostic_step("P806_QUALITY_CREATE_HTTP"):
        first = _create_response_request(
            actor,
            base_url,
            path,
            actor_csrf=actor_csrf,
            payload=payload,
        )
    with quality_link_runtime_diagnostic_step("P806_QUALITY_CREATE_SHAPE"):
        first_body = _body(first, status=201)
    with quality_link_runtime_diagnostic_step("P806_QUALITY_REPLAY_HTTP"):
        replay = document_runtime.npi_request(actor, base_url, path, method="POST", payload=payload, csrf_token=actor_csrf, idempotency_key=IDEMPOTENCY_KEY, query_key="p806-replay")
    with quality_link_runtime_diagnostic_step("P806_QUALITY_REPLAY_SHAPE"):
        replay_body = _body(replay, status=201)
        require(first_body == replay_body and replay.headers.get("Idempotency-Replayed") == "true", "P8-06 actor-bound replay drifted")
    with quality_link_runtime_diagnostic_step("P806_QUALITY_STALE_HTTP"):
        stale = document_runtime.npi_request(actor, base_url, path, method="POST", payload={**payload, "expectedSourceVersion": int(current["instanceVersion"]) + 1}, csrf_token=actor_csrf, idempotency_key=f"{IDEMPOTENCY_KEY}-stale", query_key="p806-stale")
        require(stale.status == 409, "P8-06 stale source did not fail closed")
    with quality_link_runtime_diagnostic_step("P806_QUALITY_LIST_HTTP"):
        listed = document_runtime.npi_request(actor, base_url, f"/api/npi/v1/projects/{project_id}/formal-quality-links", query_key="p806-list")
    with quality_link_runtime_diagnostic_step("P806_QUALITY_LIST_SHAPE"):
        listing = _body(listed, status=200)
        require(listing.get("permissions") == {"view": True, "link": True} and len(listing.get("items", [])) == 1, "P8-06 linked collection truth drifted")
    return {"linked": True, "replayed": True, "staleRejected": True, "targetTraffic": 0, "cleaned": True}


def run_fresh(
    base_url: str,
    fixture_password: str,
    administrator_password: str,
) -> dict[str, object]:
    with quality_link_runtime_diagnostic_step("P806_QUALITY_ADMIN_LOGIN"):
        administrator = login(base_url, "Administrator", administrator_password)
    with quality_link_runtime_diagnostic_step("P806_QUALITY_PROJECT_CONTEXT"):
        project_id, _ = document_runtime.fixture_project(administrator, base_url)
    with quality_link_runtime_diagnostic_step("P806_QUALITY_ACTOR_LOGIN"):
        actor = login(base_url, ACTOR_USER, fixture_password)
    with quality_link_runtime_diagnostic_step("P806_QUALITY_CSRF"):
        actor_csrf = bootstrap_csrf(actor, base_url, ACTOR_USER)
    with quality_link_runtime_diagnostic_step("P806_QUALITY_READINESS_HTTP"):
        readiness = document_runtime.npi_request(actor, base_url, f"/api/npi/v1/projects/{project_id}/npi-readiness", query_key="p806-readiness")
    with quality_link_runtime_diagnostic_step("P806_QUALITY_READINESS_SHAPE"):
        workspace = _body(readiness, status=200)
        current = workspace.get("currentRevision")
        require(isinstance(current, dict), "P8-06 retained readiness revision is unavailable")
        readiness_id = current.get("instanceGlobalId")
        require(isinstance(readiness_id, str), "P8-06 readiness identity is unavailable")
    prepare_kwargs = {"project_id": project_id, "readiness_id": readiness_id}
    if _prepare_projection_diagnostics_enabled():
        prepare_kwargs["diagnostic_trace_id"] = quality_link_runtime_diagnostic_trace()
    with quality_link_runtime_diagnostic_step("P806_QUALITY_PREPARE_PROJECTION"):
        prepared = run_bench_fixture(
            "prepare_projection",
            prepare_kwargs,
        )
    try:
        return _exercise_link(
            actor=actor,
            actor_csrf=actor_csrf,
            base_url=base_url,
            current=current,
            item=prepared["item"],
            project_id=project_id,
            readiness_id=readiness_id,
        )
    finally:
        with quality_link_runtime_diagnostic_step("P806_QUALITY_CLEANUP"):
            run_bench_fixture(
                "cleanup",
                {"project_id": project_id, "readiness_id": readiness_id},
            )


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    with _prepare_bootstrap_diagnostic_step(
        method,
        "P806_QUALITY_PREPARE_BOOTSTRAP_IMPORT_FRAPPE",
    ):
        import frappe
    with _prepare_bootstrap_diagnostic_step(
        method,
        "P806_QUALITY_PREPARE_BOOTSTRAP_IMPORT_REPOSITORY",
    ):
        frappe_repository = importlib.import_module(
            "npi_integration.projections.frappe_repository"
        )

    with _prepare_bootstrap_diagnostic_step(
        method,
        "P806_QUALITY_PREPARE_BOOTSTRAP_ARGUMENTS",
    ):
        require(
            method in {"prepare_projection", "cleanup"},
            "P8-06 Bench fixture is unavailable",
        )
        exact_kwargs = dict(kwargs)
        diagnostic_trace_id = exact_kwargs.pop("diagnostic_trace_id", None)
        prepare_diagnostic_enabled = (
            os.environ.get(_PREPARE_PROJECTION_DIAGNOSTIC_ENV)
            == _PREPARE_PROJECTION_DIAGNOSTIC_SCOPE
        )
        if method == "prepare_projection":
            require(
                set(exact_kwargs) == {"project_id", "readiness_id"}
                and (
                    (
                        prepare_diagnostic_enabled
                        and isinstance(diagnostic_trace_id, str)
                        and _TRACE_PATTERN.fullmatch(diagnostic_trace_id) is not None
                    )
                    or (
                        not prepare_diagnostic_enabled
                        and diagnostic_trace_id is None
                    )
                ),
                "P8-06 prepare fixture arguments are invalid",
            )
        else:
            require(
                set(exact_kwargs) == {"project_id", "readiness_id"}
                and diagnostic_trace_id is None,
                "P8-06 cleanup fixture arguments are invalid",
            )
    with _prepare_bootstrap_diagnostic_step(
        method,
        "P806_QUALITY_PREPARE_BOOTSTRAP_INIT",
    ):
        frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    with frappe_repository.quality_link_prepare_projection_diagnostics(
        diagnostic_trace_id if method == "prepare_projection" else None
    ):
        if method == "prepare_projection" and prepare_diagnostic_enabled:
            with _prepare_bootstrap_diagnostic_step(
                method,
                "P806_QUALITY_PREPARE_BOOTSTRAP_CONTEXT_ACTIVE",
            ):
                state = getattr(
                    frappe.flags,
                    frappe_repository._QUALITY_LINK_PREPARE_PROJECTION_DIAGNOSTIC_FLAG,
                    None,
                )
                require(
                    isinstance(state, dict)
                    and set(state) == {"trace_id", "recorded"}
                    and state.get("trace_id") == diagnostic_trace_id
                    and state.get("recorded") is False,
                    "P8-06 prepare diagnostic context is inactive",
                )
        with frappe_repository.quality_link_prepare_projection_step(
            "P806_QUALITY_PREPARE_CHILD_INIT"
        ):
            require(
                getattr(frappe.local, "initialised", False) is True,
                "P8-06 prepare fixture Site was not initialized",
            )
        with frappe_repository.quality_link_prepare_projection_step(
            "P806_QUALITY_PREPARE_CHILD_CONNECT"
        ):
            frappe.connect()
        try:
            with frappe_repository.quality_link_prepare_projection_step(
                "P806_QUALITY_PREPARE_SITE_VALIDATE"
            ):
                document_runtime._validated_runtime_site()
            with frappe_repository.quality_link_prepare_projection_step(
                "P806_QUALITY_PREPARE_SET_ACTOR"
            ):
                frappe.set_user(
                    ACTOR_USER if method == "prepare_projection" else "Administrator"
                )
            result = (
                prepare_projection(**exact_kwargs)
                if method == "prepare_projection"
                else cleanup(**exact_kwargs)
            )
            with frappe_repository.quality_link_prepare_projection_step(
                "P806_QUALITY_PREPARE_COMMIT"
            ):
                frappe.db.commit()
            with frappe_repository.quality_link_prepare_projection_step(
                "P806_QUALITY_PREPARE_RESPONSE"
            ):
                print(json.dumps(result, separators=(",", ":"), sort_keys=True))
        except Exception:
            frappe.db.rollback()
            raise
        finally:
            with frappe_repository.quality_link_prepare_projection_step(
                "P806_QUALITY_PREPARE_DESTROY"
            ):
                frappe.destroy()


def run_scoped_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    trace_id = kwargs.get("diagnostic_trace_id")
    scope_is_exact = (
        method == "prepare_projection"
        and (
            QUALITY_LINK_PREPARE_BOOTSTRAP_DIAGNOSTICS_ENABLED
            or QUALITY_LINK_POST_PERMISSION_DIAGNOSTICS_ENABLED
            or QUALITY_LINK_POST_PROJECTION_PERMISSION_DIAGNOSTICS_ENABLED
            or QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED
            or QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED
            or _full_boundary_diagnostics_enabled()
        )
        and os.environ.get(_PREPARE_PROJECTION_DIAGNOSTIC_ENV)
        == _PREPARE_PROJECTION_DIAGNOSTIC_SCOPE
        and isinstance(trace_id, str)
        and _TRACE_PATTERN.fullmatch(trace_id) is not None
    )
    with quality_link_runtime_diagnostic_scope(
        trace_id if scope_is_exact else ""
    ):
        run_local_bench_fixture(method, kwargs)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url")
    parser.add_argument("--bench-fixture")
    parser.add_argument("--fixture-kwargs")
    parser.add_argument("--diagnostic-trace", action="store_true")
    parser.add_argument("--read-diagnostic")
    parser.add_argument("--expected-trace")
    arguments = parser.parse_args()
    if arguments.diagnostic_trace:
        require(
            arguments.base_url is None
            and arguments.bench_fixture is None
            and arguments.fixture_kwargs is None
            and arguments.read_diagnostic is None
            and arguments.expected_trace is None,
            "P8-06 diagnostic trace invocation drifted",
        )
        print(quality_link_runtime_diagnostic_trace())
        return 0
    if arguments.read_diagnostic:
        if (
            arguments.base_url is not None
            or arguments.bench_fixture is not None
            or arguments.fixture_kwargs is not None
            or arguments.expected_trace is None
        ):
            return 2
        diagnostic = read_quality_link_runtime_diagnostic(
            Path(arguments.read_diagnostic),
            expected_trace=arguments.expected_trace,
        )
        if diagnostic is None:
            return 2
        exception_type, code, trace_id = diagnostic
        print(
            f"diagnostic_code={code}; exception_type={exception_type}; "
            f"trace_id={trace_id}"
        )
        return 0
    if arguments.bench_fixture:
        require(arguments.base_url is None and arguments.fixture_kwargs is not None, "P8-06 fixture invocation drifted")
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "P8-06 fixture arguments are invalid")
        run_scoped_local_bench_fixture(arguments.bench_fixture, kwargs)
        return 0
    trace_id = quality_link_runtime_diagnostic_trace()
    with quality_link_runtime_diagnostic_scope(trace_id):
        try:
            with quality_link_runtime_diagnostic_step("P806_QUALITY_BOOTSTRAP_SECRET"):
                require(arguments.base_url is not None and FIXTURE_RUN_ID != "0" * 32, "P8-06 runtime invocation is incomplete")
                base_url = validate_local_fixture_inputs(arguments.base_url, "Administrator", ACTOR_USER)
                fixture_password = secret_from_environment("NPI_RUNTIME_FIXTURE_PASSWORD")
                administrator_password = secret_from_environment("NPI_RUNTIME_ADMINISTRATOR_PASSWORD")
            result = run_fresh(base_url, fixture_password, administrator_password)
        except Exception:
            if (
                QUALITY_LINK_RUNTIME_STAGE_DIAGNOSTICS_ENABLED
                or QUALITY_LINK_PREPARE_PROJECTION_DIAGNOSTICS_ENABLED
                or QUALITY_LINK_PREPARE_BOOTSTRAP_DIAGNOSTICS_ENABLED
                or QUALITY_LINK_POST_PERMISSION_DIAGNOSTICS_ENABLED
                or QUALITY_LINK_CREATE_RESPONSE_DIAGNOSTICS_ENABLED
                or QUALITY_LINK_POST_RECEIPT_DIAGNOSTICS_ENABLED
                or QUALITY_LINK_PARENT_DOWNSTREAM_DIAGNOSTICS_ENABLED
                or QUALITY_LINK_POST_PROJECTION_PERMISSION_DIAGNOSTICS_ENABLED
                or QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED
                or QUALITY_LINK_POST_WRITE_FULL_BOUNDARY_DIAGNOSTICS_ENABLED
                or QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED
                or QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED
                or _full_boundary_diagnostics_enabled()
            ):
                return 1
            raise
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
