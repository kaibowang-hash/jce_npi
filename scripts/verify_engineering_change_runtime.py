from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator
from uuid import UUID, uuid5

import verify_document_runtime as document_runtime
import verify_readiness_runtime as readiness_runtime
from verify_frappe_runtime import (
    HttpResult,
    RUNTIME_BASE_URL,
    login,
    request,
    require,
    secret_from_environment,
    validate_local_fixture_inputs,
)
from verify_project_runtime import bootstrap_csrf


ROOT = Path(__file__).resolve().parents[1]
BENCH_PATH = ROOT / "tmp" / "frappe-bench"
SITE_NAME = document_runtime.SITE_NAME
FIXTURE_RUN_ID = document_runtime.FIXTURE_RUN_ID
TENANT_ID = "runtime-tenant"
REQUESTER_USER = os.environ.get(
    "NPI_P9_01C_RUNTIME_REQUESTER", "p9-requester@example.invalid"
)
WORKER_USER = os.environ.get(
    "NPI_P9_01C_RUNTIME_WORKER", "p9-worker@example.invalid"
)
EXPECTED_WORKER_USER = readiness_runtime.ACTOR_USER
RUNTIME_MARKER = "npi-one-local-runtime-disposable-v1"
WEBHOOK_PATH = "/api/npi/v1/integration/erpnext/engineering-change-events"
KEY_ID = "p9-01c-runtime"
IMPACT_CATEGORIES = (
    "product",
    "drawing",
    "ebom",
    "mbom",
    "tooling",
    "process",
    "quality",
    "inventory_wip",
    "supplier",
    "cost",
    "delivery",
    "customer",
)
CHANGE_TITLE = f"P9 runtime engineering change {FIXTURE_RUN_ID[:12]}"
TRACE_PREFIX = f"trace-p901-{FIXTURE_RUN_ID[:12]}"
CREATE_KEY = f"p9-change-create-{FIXTURE_RUN_ID}"
REVISE_KEY = f"p9-change-revise-{FIXTURE_RUN_ID}"
SUMMARY_KEY = f"p9-change-summary-{FIXTURE_RUN_ID}"
CLOSE_KEY = f"p9-change-close-{FIXTURE_RUN_ID}"
_NAMESPACE = UUID("5d97e7f7-886a-50b9-8946-5740d5dc5927")
ENGINEERING_CHANGE_RUNTIME_DIAGNOSTICS_ENABLED = False
ENGINEERING_CHANGE_RUNTIME_FULL_BOUNDARY_DIAGNOSTICS_ENABLED = False
ENGINEERING_CHANGE_RUNTIME_INPUT_BOUNDARY_DIAGNOSTICS_ENABLED = False
ENGINEERING_CHANGE_RUNTIME_LOCAL_FIXTURE_DIAGNOSTICS_ENABLED = False
ENGINEERING_CHANGE_RUNTIME_POST_MARKER_DIAGNOSTICS_ENABLED = False
ENGINEERING_CHANGE_RUNTIME_REVISE_OUTCOME_DIAGNOSTICS_ENABLED = False
ENGINEERING_CHANGE_RUNTIME_REVISE_SERVER_DIAGNOSTICS_ENABLED = False
ENGINEERING_CHANGE_RUNTIME_POST_ROOT_SAVE_DIAGNOSTICS_ENABLED = False
ENGINEERING_CHANGE_RUNTIME_POST_OPTIONAL_EMPTY_DIAGNOSTICS_ENABLED = False
ENGINEERING_CHANGE_RUNTIME_INBOUND_FULL_DIAGNOSTICS_ENABLED = False
ENGINEERING_CHANGE_RUNTIME_POST_RAW_BODY_DIAGNOSTICS_ENABLED = False
ENGINEERING_CHANGE_RUNTIME_POST_MARKER_REPAIR_DIAGNOSTICS_ENABLED = False
ENGINEERING_CHANGE_RUNTIME_POST_LOOPBACK_REPAIR_DIAGNOSTICS_ENABLED = False
ENGINEERING_CHANGE_RUNTIME_POST_SERVICE_ACTOR_REPAIR_DIAGNOSTICS_ENABLED = False
ENGINEERING_CHANGE_RUNTIME_POST_INBOX_INSERT_DIAGNOSTICS_ENABLED = False
ENGINEERING_CHANGE_RUNTIME_POST_DATETIME_REPAIR_DIAGNOSTICS_ENABLED = False
ENGINEERING_CHANGE_RUNTIME_POST_REPLAY_IDENTITY_REPAIR_DIAGNOSTICS_ENABLED = False
ENGINEERING_CHANGE_RUNTIME_POST_SUMMARY_ORDERING_REPAIR_DIAGNOSTICS_ENABLED = False
ENGINEERING_CHANGE_RUNTIME_POST_FORMAL_DATETIME_COMPARISON_REPAIR_DIAGNOSTICS_ENABLED = False
ENGINEERING_CHANGE_RUNTIME_POST_SUMMARY_OPERATION_REPAIR_DIAGNOSTICS_ENABLED = False
ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_HEADER = (
    "X-NPI-P901-Change-Revise-Diagnostic"
)
ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_SCOPE = (
    "p9-01-engineering-change-revise-server-v1"
)
ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_TRACE_HEADER = (
    "X-NPI-P901-Change-Revise-Diagnostic-Trace"
)
ENGINEERING_CHANGE_INBOUND_SERVER_DIAGNOSTIC_HEADER = (
    "X-NPI-P901-Change-Inbound-Diagnostic"
)
ENGINEERING_CHANGE_INBOUND_SERVER_DIAGNOSTIC_SCOPE = (
    "p9-01-engineering-change-inbound-server-v1"
)
ENGINEERING_CHANGE_INBOUND_SERVER_DIAGNOSTIC_TRACE_HEADER = (
    "X-NPI-P901-Change-Inbound-Diagnostic-Trace"
)
ENGINEERING_CHANGE_SUMMARY_SERVER_DIAGNOSTIC_HEADER = (
    "X-NPI-P901-Change-Summary-Diagnostic"
)
ENGINEERING_CHANGE_SUMMARY_SERVER_DIAGNOSTIC_SCOPE = (
    "p9-01-engineering-change-summary-server-v1"
)
ENGINEERING_CHANGE_SUMMARY_SERVER_DIAGNOSTIC_TRACE_HEADER = (
    "X-NPI-P901-Change-Summary-Diagnostic-Trace"
)
ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_CODES = frozenset(
    {
        "P901_CHANGE_REVISE_API_CALL",
        "P901_CHANGE_REVISE_API_ROUTES",
        "P901_CHANGE_REVISE_API_USER",
        "P901_CHANGE_REVISE_API_CSRF",
        "P901_CHANGE_REVISE_API_PRINCIPAL",
        "P901_CHANGE_REVISE_API_ROLE",
        "P901_CHANGE_REVISE_API_FIELDS",
        "P901_CHANGE_REVISE_API_REPOSITORY_INIT",
        "P901_CHANGE_REVISE_API_IDEMPOTENCY",
        "P901_CHANGE_REVISE_API_REPOSITORY_CALL",
        "P901_CHANGE_REVISE_API_OUTCOME",
        "P901_CHANGE_REVISE_API_RESPONSE",
        "P901_CHANGE_REVISE_REPOSITORY_PROJECT_LOCK",
        "P901_CHANGE_REVISE_REPOSITORY_ROOT_LOCK",
        "P901_CHANGE_REVISE_REPOSITORY_PAYLOAD",
        "P901_CHANGE_REVISE_REPOSITORY_REPLAY",
        "P901_CHANGE_REVISE_REPOSITORY_CURRENT",
        "P901_CHANGE_REVISE_REPOSITORY_PREDECESSOR",
        "P901_CHANGE_REVISE_REPOSITORY_STATE",
        "P901_CHANGE_REVISE_REPOSITORY_TRANSFORM",
        "P901_CHANGE_REVISE_REPOSITORY_EVENT",
        "P901_CHANGE_REVISE_REPOSITORY_RESPONSE",
        "P901_CHANGE_REVISE_REPOSITORY_WRITE_SCOPE",
        "P901_CHANGE_REVISE_REPOSITORY_RECEIPT",
        "P901_CHANGE_REVISE_REPOSITORY_RECEIPT_REPLAY",
        "P901_CHANGE_REVISE_REPOSITORY_REVISION_INSERT",
        "P901_CHANGE_REVISE_REPOSITORY_EVENT_INSERT",
        "P901_CHANGE_REVISE_REPOSITORY_ROOT_APPLY",
        "P901_CHANGE_REVISE_REPOSITORY_ROOT_SAVE",
        "P901_CHANGE_REVISE_REPOSITORY_AUDIT",
        "P901_CHANGE_REVISE_REPOSITORY_RECEIPT_SEAL",
        "P901_CHANGE_REVISE_REPOSITORY_OUTCOME",
    }
)
ENGINEERING_CHANGE_INBOUND_SERVER_DIAGNOSTIC_CODES = frozenset(
    {
        "P901_CHANGE_INBOUND_API_CALL",
        "P901_CHANGE_INBOUND_API_FIELDS",
        "P901_CHANGE_INBOUND_API_REQUEST",
        "P901_CHANGE_INBOUND_API_AUTHENTICATE",
        "P901_CHANGE_INBOUND_API_PRINCIPAL",
        "P901_CHANGE_INBOUND_API_REPOSITORY_INIT",
        "P901_CHANGE_INBOUND_API_REPOSITORY_CALL",
        "P901_CHANGE_INBOUND_API_COMMIT",
        "P901_CHANGE_INBOUND_API_ENQUEUE",
        "P901_CHANGE_INBOUND_API_OUTCOME",
        "P901_CHANGE_INBOUND_API_RESPONSE",
        "P901_CHANGE_INBOUND_REPOSITORY_INPUT",
        "P901_CHANGE_INBOUND_REPOSITORY_EVENT",
        "P901_CHANGE_INBOUND_REPOSITORY_HASHES",
        "P901_CHANGE_INBOUND_REPOSITORY_REPLAY",
        "P901_CHANGE_INBOUND_REPOSITORY_SOURCE_KEY",
        "P901_CHANGE_INBOUND_REPOSITORY_LATEST",
        "P901_CHANGE_INBOUND_REPOSITORY_VERSION",
        "P901_CHANGE_INBOUND_REPOSITORY_RESPONSE",
        "P901_CHANGE_INBOUND_REPOSITORY_WRITE_SCOPE",
        "P901_CHANGE_INBOUND_REPOSITORY_INBOX_INSERT",
        "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_NULL",
        "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_MISSING_COLUMN",
        "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_DUPLICATE",
        "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_MISSING_TABLE",
        "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_LOCK",
        "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_DATETIME",
        "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_MISSING_DEFAULT",
        "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_INVALID_VALUE",
        "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_TOO_LONG",
        "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_OTHER",
        "P901_CHANGE_INBOUND_REPOSITORY_AUDIT",
        "P901_CHANGE_INBOUND_REPOSITORY_OUTCOME",
    }
)
ENGINEERING_CHANGE_SUMMARY_SERVER_DIAGNOSTIC_CODES = frozenset(
    {
        "P901_CHANGE_SUMMARY_API_CALL",
        "P901_CHANGE_SUMMARY_API_USER",
        "P901_CHANGE_SUMMARY_API_CSRF",
        "P901_CHANGE_SUMMARY_API_PRINCIPAL",
        "P901_CHANGE_SUMMARY_API_ROUTES",
        "P901_CHANGE_SUMMARY_API_REPOSITORY_INIT",
        "P901_CHANGE_SUMMARY_API_SCOPE",
        "P901_CHANGE_SUMMARY_API_FIELDS",
        "P901_CHANGE_SUMMARY_API_REPOSITORY_CALL",
        "P901_CHANGE_SUMMARY_API_COMMIT",
        "P901_CHANGE_SUMMARY_API_ENQUEUE",
        "P901_CHANGE_SUMMARY_API_OUTCOME",
        "P901_CHANGE_SUMMARY_API_RESPONSE",
        "P901_CHANGE_SUMMARY_REPOSITORY_PROJECT_LOCK",
        "P901_CHANGE_SUMMARY_REPOSITORY_PROFILE",
        "P901_CHANGE_SUMMARY_REPOSITORY_REPLAY_LOOKUP",
        "P901_CHANGE_SUMMARY_REPOSITORY_REPLAY",
        "P901_CHANGE_SUMMARY_REPOSITORY_DETAIL",
        "P901_CHANGE_SUMMARY_REPOSITORY_DETAIL_VALIDATE",
        "P901_CHANGE_SUMMARY_REPOSITORY_CURRENT",
        "P901_CHANGE_SUMMARY_REPOSITORY_SUMMARY",
        "P901_CHANGE_SUMMARY_REPOSITORY_REQUEST_VALUE",
        "P901_CHANGE_SUMMARY_REPOSITORY_RESPONSE",
        "P901_CHANGE_SUMMARY_REPOSITORY_WRITE_SCOPE",
        "P901_CHANGE_SUMMARY_REPOSITORY_REQUEST_INSERT",
        "P901_CHANGE_SUMMARY_REPOSITORY_OUTBOX_PAYLOAD",
        "P901_CHANGE_SUMMARY_REPOSITORY_OUTBOX_INSERT",
        "P901_CHANGE_SUMMARY_REPOSITORY_AUDIT",
        "P901_CHANGE_SUMMARY_REPOSITORY_OUTCOME",
    }
)
ENGINEERING_CHANGE_RUNTIME_DIAGNOSTIC_CODES = frozenset(
    {
        "P901_CHANGE_INVOCATION",
        "P901_CHANGE_INPUTS",
        "P901_CHANGE_INPUT_LOCAL_FIXTURE",
        "P901_CHANGE_INPUT_BASE_URL",
        "P901_CHANGE_INPUT_URL_SHAPE",
        "P901_CHANGE_INPUT_ADMINISTRATOR",
        "P901_CHANGE_INPUT_REQUESTER_DOMAIN",
        "P901_CHANGE_INPUT_REQUESTER_CASE",
        "P901_CHANGE_INPUT_REQUESTER_STANDARD",
        "P901_CHANGE_INPUT_TMP_DIRECTORY",
        "P901_CHANGE_INPUT_BENCH_DIRECTORY",
        "P901_CHANGE_INPUT_SITE_GUARD",
        "P901_CHANGE_INPUT_DATABASE_ENV",
        "P901_CHANGE_INPUT_PROJECT",
        "P901_CHANGE_INPUT_ACTORS",
        "P901_CHANGE_INPUT_RUNTIME_SECRET",
        "P901_CHANGE_FIXTURE_SECRET",
        "P901_CHANGE_FRESH_PARENT",
        "P901_CHANGE_DISABLED_PARENT",
        "P901_CHANGE_REPLAY_PARENT",
        "P901_CHANGE_RECOVERED_PARENT",
        "P901_CHANGE_CLEANUP_PARENT",
        "P901_CHANGE_RESULT",
        "P901_CHANGE_LOGIN",
        "P901_CHANGE_CSRF",
        "P901_CHANGE_CREATE_HTTP",
        "P901_CHANGE_CREATE_SHAPE",
        "P901_CHANGE_CREATE_REPLAY_HTTP",
        "P901_CHANGE_CREATE_REPLAY_SHAPE",
        "P901_CHANGE_STALE_HTTP",
        "P901_CHANGE_STALE_SHAPE",
        "P901_CHANGE_REVISE_HTTP",
        "P901_CHANGE_REVISE_REQUEST",
        "P901_CHANGE_REVISE_STATUS_INVALID",
        "P901_CHANGE_REVISE_STATUS_INFORMATIONAL",
        "P901_CHANGE_REVISE_STATUS_SUCCESS_NON_200",
        "P901_CHANGE_REVISE_STATUS_REDIRECTION",
        "P901_CHANGE_REVISE_STATUS_CLIENT_ERROR",
        "P901_CHANGE_REVISE_STATUS_SERVER_ERROR",
        "P901_CHANGE_REVISE_REQUEST_ID",
        "P901_CHANGE_REVISE_CACHE_CONTROL",
        "P901_CHANGE_REVISE_BODY_SHAPE",
        "P901_CHANGE_REVISE_IDEMPOTENCY",
        "P901_CHANGE_REVISE_SHAPE",
        "P901_CHANGE_INBOUND_HTTP",
        "P901_CHANGE_INBOUND_REQUEST",
        "P901_CHANGE_INBOUND_STATUS_INVALID",
        "P901_CHANGE_INBOUND_STATUS_INFORMATIONAL",
        "P901_CHANGE_INBOUND_STATUS_SUCCESS_UNEXPECTED",
        "P901_CHANGE_INBOUND_STATUS_REDIRECTION",
        "P901_CHANGE_INBOUND_STATUS_CLIENT_ERROR",
        "P901_CHANGE_INBOUND_STATUS_SERVER_ERROR",
        "P901_CHANGE_INBOUND_REQUEST_ID",
        "P901_CHANGE_INBOUND_CACHE_CONTROL",
        "P901_CHANGE_INBOUND_BODY_SHAPE",
        "P901_CHANGE_INBOUND_IDEMPOTENCY",
        "P901_CHANGE_INBOUND_SHAPE",
        "P901_CHANGE_INBOUND_WORKER_PARENT",
        "P901_CHANGE_INBOUND_WORKER_SHAPE",
        "P901_CHANGE_INBOUND_REPLAY_HTTP",
        "P901_CHANGE_INBOUND_REPLAY_SHAPE",
        "P901_CHANGE_DETAIL_AFTER_INBOUND",
        "P901_CHANGE_FORMAL_OBSERVATION_SHAPE",
        "P901_CHANGE_SUMMARY_HTTP",
        "P901_CHANGE_SUMMARY_SHAPE",
        "P901_CHANGE_SUMMARY_WORKER_PARENT",
        "P901_CHANGE_SUMMARY_WORKER_SHAPE",
        "P901_CHANGE_SUMMARY_REPLAY_HTTP",
        "P901_CHANGE_SUMMARY_REPLAY_SHAPE",
        "P901_CHANGE_INBOUND_OPERATIONS",
        "P901_CHANGE_OUTBOUND_OPERATIONS",
        "P901_CHANGE_OPERATIONS_SHAPE",
        "P901_CHANGE_CLOSE_HTTP",
        "P901_CHANGE_CLOSE_SHAPE",
        "P901_CHANGE_BENCH_INIT",
        "P901_CHANGE_BENCH_CONNECT",
        "P901_CHANGE_BENCH_MARKER",
        "P901_CHANGE_INBOX_CHILD_INPUT",
        "P901_CHANGE_INBOX_CHILD_WORKER",
        "P901_CHANGE_INBOX_CHILD_RESPONSE",
        "P901_CHANGE_SUMMARY_CHILD_INPUT",
        "P901_CHANGE_SUMMARY_CHILD_WORKER",
        "P901_CHANGE_SUMMARY_CHILD_RESPONSE",
    }
) | (
    ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_CODES
    | ENGINEERING_CHANGE_INBOUND_SERVER_DIAGNOSTIC_CODES
    | ENGINEERING_CHANGE_SUMMARY_SERVER_DIAGNOSTIC_CODES
)
_DIAGNOSTIC_PATH_ENV = "NPI_P9_01_RUNTIME_DIAGNOSTIC_PATH"
_DIAGNOSTIC_TRACE_ENV = "NPI_P9_01_RUNTIME_DIAGNOSTIC_TRACE"
_DIAGNOSTIC_RECORD_KEYS = frozenset({"code", "exceptionType", "traceId"})
_DIAGNOSTIC_RECORD_LIMIT = 4096
_TRACE_PATTERN = re.compile(r"^trace-[a-f0-9]{32}$")
_TYPE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,127}$")
_DIAGNOSTIC_STATE: ContextVar[dict[str, object] | None] = ContextVar(
    "p901_engineering_change_runtime_diagnostic_state", default=None
)


def _engineering_change_runtime_diagnostics_enabled() -> bool:
    return (
        ENGINEERING_CHANGE_RUNTIME_DIAGNOSTICS_ENABLED
        or ENGINEERING_CHANGE_RUNTIME_FULL_BOUNDARY_DIAGNOSTICS_ENABLED
        or ENGINEERING_CHANGE_RUNTIME_INPUT_BOUNDARY_DIAGNOSTICS_ENABLED
        or ENGINEERING_CHANGE_RUNTIME_LOCAL_FIXTURE_DIAGNOSTICS_ENABLED
        or ENGINEERING_CHANGE_RUNTIME_POST_MARKER_DIAGNOSTICS_ENABLED
        or ENGINEERING_CHANGE_RUNTIME_REVISE_OUTCOME_DIAGNOSTICS_ENABLED
        or ENGINEERING_CHANGE_RUNTIME_REVISE_SERVER_DIAGNOSTICS_ENABLED
        or ENGINEERING_CHANGE_RUNTIME_POST_ROOT_SAVE_DIAGNOSTICS_ENABLED
        or ENGINEERING_CHANGE_RUNTIME_POST_OPTIONAL_EMPTY_DIAGNOSTICS_ENABLED
        or ENGINEERING_CHANGE_RUNTIME_INBOUND_FULL_DIAGNOSTICS_ENABLED
        or ENGINEERING_CHANGE_RUNTIME_POST_RAW_BODY_DIAGNOSTICS_ENABLED
        or ENGINEERING_CHANGE_RUNTIME_POST_MARKER_REPAIR_DIAGNOSTICS_ENABLED
        or ENGINEERING_CHANGE_RUNTIME_POST_LOOPBACK_REPAIR_DIAGNOSTICS_ENABLED
        or ENGINEERING_CHANGE_RUNTIME_POST_SERVICE_ACTOR_REPAIR_DIAGNOSTICS_ENABLED
        or ENGINEERING_CHANGE_RUNTIME_POST_INBOX_INSERT_DIAGNOSTICS_ENABLED
        or ENGINEERING_CHANGE_RUNTIME_POST_DATETIME_REPAIR_DIAGNOSTICS_ENABLED
        or ENGINEERING_CHANGE_RUNTIME_POST_REPLAY_IDENTITY_REPAIR_DIAGNOSTICS_ENABLED
        or ENGINEERING_CHANGE_RUNTIME_POST_SUMMARY_ORDERING_REPAIR_DIAGNOSTICS_ENABLED
        or ENGINEERING_CHANGE_RUNTIME_POST_FORMAL_DATETIME_COMPARISON_REPAIR_DIAGNOSTICS_ENABLED
        or ENGINEERING_CHANGE_RUNTIME_POST_SUMMARY_OPERATION_REPAIR_DIAGNOSTICS_ENABLED
    )


def engineering_change_runtime_diagnostic_trace() -> str:
    return f"trace-{uuid5(_NAMESPACE, f'diagnostic:{FIXTURE_RUN_ID}').hex}"


@contextmanager
def engineering_change_runtime_diagnostic_scope(trace_id: str) -> Iterator[None]:
    state = None
    if (
        _engineering_change_runtime_diagnostics_enabled()
        and _TRACE_PATTERN.fullmatch(trace_id) is not None
    ):
        state = {"trace_id": trace_id, "recorded": False}
    token = _DIAGNOSTIC_STATE.set(state)
    try:
        yield
    finally:
        _DIAGNOSTIC_STATE.reset(token)


@contextmanager
def engineering_change_runtime_diagnostic_step(code: str) -> Iterator[None]:
    try:
        yield
    except BaseException as error:
        _record_engineering_change_runtime_diagnostic(code, error)
        raise


def _record_engineering_change_runtime_diagnostic(
    code: str, error: BaseException
) -> None:
    try:
        state = _DIAGNOSTIC_STATE.get()
        exception_type = type(error).__name__
        if (
            state is None
            or state["recorded"] is True
            or code not in ENGINEERING_CHANGE_RUNTIME_DIAGNOSTIC_CODES
            or _TYPE_PATTERN.fullmatch(exception_type) is None
        ):
            return
        _write_engineering_change_runtime_diagnostic(
            {
                "code": code,
                "exceptionType": exception_type,
                "traceId": str(state["trace_id"]),
            }
        )
        state["recorded"] = True
    except Exception:
        # Diagnostics must never replace the original verifier failure.
        pass


def _write_engineering_change_runtime_diagnostic(record: dict[str, str]) -> None:
    path_value = os.environ.get(_DIAGNOSTIC_PATH_ENV)
    if not isinstance(path_value, str) or not path_value:
        return
    path = Path(path_value)
    if (
        not path.is_absolute()
        or path.name != "p9-01-engineering-change-runtime-diagnostic.json"
    ):
        return
    payload = json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(payload)


def read_engineering_change_runtime_diagnostic(
    path: Path, *, expected_trace: str
) -> tuple[str, str, str] | None:
    if (
        not _engineering_change_runtime_diagnostics_enabled()
        or _TRACE_PATTERN.fullmatch(expected_trace) is None
    ):
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
        or code not in ENGINEERING_CHANGE_RUNTIME_DIAGNOSTIC_CODES
        or not isinstance(exception_type, str)
        or _TYPE_PATTERN.fullmatch(exception_type) is None
        or trace_id != expected_trace
    ):
        return None
    return exception_type, code, expected_trace


def deterministic_uuid(label: str) -> str:
    return str(uuid5(_NAMESPACE, f"{FIXTURE_RUN_ID}:{label}"))


def canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def revision_content(*, complete: bool) -> dict[str, object]:
    evidence = deterministic_uuid("closure-evidence")
    return {
        "title": CHANGE_TITLE,
        "reason": (
            "Complete the disposable integration proof."
            if complete
            else "Establish the disposable change-control boundary."
        ),
        "impactAssessments": [
            {
                "category": category,
                "conclusion": "not_affected",
                "responsibleUserId": REQUESTER_USER,
                "rationale": f"Disposable assessment for {category}",
                "evidenceReferenceGlobalIds": [],
            }
            for category in IMPACT_CATEGORIES
        ],
        "affectedObjects": [],
        "implementationTasks": [],
        "effectivityRules": (
            [
                {
                    "kind": "date",
                    "effectiveDate": "2026-09-15",
                    "selectorReference": None,
                    "validationEvidenceGlobalId": deterministic_uuid(
                        "effectivity-evidence"
                    ),
                }
            ]
            if complete
            else []
        ),
        "dispositions": (
            [
                {
                    "scope": "old_inventory",
                    "decision": "use_as_is",
                    "approvedByUserId": REQUESTER_USER,
                    "approvalEvidenceGlobalId": deterministic_uuid(
                        "disposition-approval"
                    ),
                    "executionEvidenceGlobalId": deterministic_uuid(
                        "disposition-execution"
                    ),
                    "note": "Disposable evidence only.",
                }
            ]
            if complete
            else []
        ),
        "revalidationRequirements": (
            [
                {
                    "kind": "fai",
                    "state": "satisfied",
                    "responsibleUserId": REQUESTER_USER,
                    "workItemGlobalId": deterministic_uuid("revalidation-work"),
                    "gateReviewGlobalId": None,
                    "evidenceReferenceGlobalIds": [
                        deterministic_uuid("revalidation-evidence")
                    ],
                    "waiverApprovalGlobalId": None,
                }
            ]
            if complete
            else []
        ),
        "costSummary": {
            "currency": "CNY",
            "engineeringCost": "0",
            "toolingCost": "0",
            "scrapCost": "0",
            "logisticsCost": "0",
            "downtimeMinutes": 0,
            "deliveryImpactDays": 0,
        },
        "closureEvidence": (
            {
                "newVersionsReleased": True,
                "erpUpdateObserved": True,
                "oldVersionsWithdrawn": True,
                "effectivityValidated": True,
                "dispositionsExecuted": True,
                "evidenceReferenceGlobalIds": [evidence],
            }
            if complete
            else None
        ),
    }


def predecessor(revision: dict[str, object]) -> dict[str, object]:
    result = {
        "expectedRevision": revision.get("revision"),
        "expectedRevisionGlobalId": revision.get("globalId"),
        "expectedRevisionSnapshotHash": revision.get("snapshotHash"),
    }
    require(
        type(result["expectedRevision"]) is int
        and _uuid(result["expectedRevisionGlobalId"])
        and _hash(result["expectedRevisionSnapshotHash"]),
        "P9-01 current revision identity drifted",
    )
    return result


def _uuid(value: object) -> bool:
    try:
        parsed = UUID(str(value))
    except (TypeError, ValueError):
        return False
    return str(parsed) == value and parsed.int != 0


def _hash(value: object) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _request_headers(
    label: str,
    *,
    csrf_token: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, str]:
    headers = {
        "X-Request-ID": deterministic_uuid(f"request:{label}"),
        "X-Trace-ID": f"{TRACE_PREFIX}-{label}",
    }
    if csrf_token is not None:
        headers["X-Frappe-CSRF-Token"] = csrf_token
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def _validate_http(
    result: HttpResult,
    *,
    expected_status: int,
    expected_request_id: str,
    private: bool = True,
) -> dict[str, Any]:
    require(
        result.status == expected_status,
        f"P9-01 HTTP status drifted from {expected_status}",
    )
    require(
        result.headers.get("X-Request-ID") == expected_request_id,
        "P9-01 request identity was not echoed",
    )
    expected_cache = "private, no-store" if private else "no-store"
    require(
        result.headers.get("Cache-Control") == expected_cache,
        "P9-01 cache boundary drifted",
    )
    require(isinstance(result.body, dict), "P9-01 response body drifted")
    return result.body


def _change_path(project_id: str, suffix: str = "") -> str:
    encoded = urllib.parse.quote(project_id, safe="")
    return f"/api/npi/v1/projects/{encoded}/engineering-changes{suffix}"


def _get_changes(opener, base_url: str, project_id: str) -> dict[str, Any]:
    headers = _request_headers("list")
    result = request(
        opener,
        base_url,
        _change_path(project_id),
        request_headers=headers,
    )
    return _validate_http(
        result, expected_status=200, expected_request_id=headers["X-Request-ID"]
    )


def _find_change(collection: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    items = collection.get("items")
    require(isinstance(items, list), "P9-01 change collection shape drifted")
    matches = [
        item
        for item in items
        if isinstance(item, dict)
        and isinstance(item.get("change"), dict)
        and item["change"].get("title") == CHANGE_TITLE
    ]
    require(len(matches) == 1, "P9-01 change fixture cardinality drifted")
    change = matches[0].get("change")
    current = matches[0].get("currentRevision")
    require(
        isinstance(change, dict)
        and isinstance(current, dict)
        and _uuid(change.get("globalId")),
        "P9-01 change collection item drifted",
    )
    return change, current


def _get_detail(
    opener, base_url: str, project_id: str, change_id: str, label: str
) -> dict[str, Any]:
    headers = _request_headers(label)
    result = request(
        opener,
        base_url,
        _change_path(project_id, f"/{urllib.parse.quote(change_id, safe='')}"),
        request_headers=headers,
    )
    body = _validate_http(
        result, expected_status=200, expected_request_id=headers["X-Request-ID"]
    )
    require(
        body.get("projectGlobalId") == project_id
        and isinstance(body.get("change"), dict)
        and body["change"].get("globalId") == change_id
        and isinstance(body.get("currentRevision"), dict),
        "P9-01 change detail shape drifted",
    )
    return body


def _command(
    opener,
    base_url: str,
    path: str,
    payload: dict[str, object],
    *,
    csrf_token: str,
    idempotency_key: str,
    label: str,
    expected_status: int,
    replayed: bool,
) -> dict[str, Any]:
    headers = _request_headers(
        label, csrf_token=csrf_token, idempotency_key=idempotency_key
    )
    state = _DIAGNOSTIC_STATE.get()
    diagnostic_trace = (
        state.get("trace_id") if isinstance(state, dict) else None
    )
    if (
        (
            ENGINEERING_CHANGE_RUNTIME_POST_SUMMARY_ORDERING_REPAIR_DIAGNOSTICS_ENABLED
            or ENGINEERING_CHANGE_RUNTIME_POST_FORMAL_DATETIME_COMPARISON_REPAIR_DIAGNOSTICS_ENABLED
        )
        and label == "close"
        and isinstance(diagnostic_trace, str)
        and _TRACE_PATTERN.fullmatch(diagnostic_trace) is not None
    ):
        headers[ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_HEADER] = (
            ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_SCOPE
        )
        headers[ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_TRACE_HEADER] = (
            diagnostic_trace
        )
    if (
        ENGINEERING_CHANGE_RUNTIME_POST_FORMAL_DATETIME_COMPARISON_REPAIR_DIAGNOSTICS_ENABLED
        and label in {"summary", "summary-replay"}
        and isinstance(diagnostic_trace, str)
        and _TRACE_PATTERN.fullmatch(diagnostic_trace) is not None
    ):
        headers[ENGINEERING_CHANGE_SUMMARY_SERVER_DIAGNOSTIC_HEADER] = (
            ENGINEERING_CHANGE_SUMMARY_SERVER_DIAGNOSTIC_SCOPE
        )
        headers[ENGINEERING_CHANGE_SUMMARY_SERVER_DIAGNOSTIC_TRACE_HEADER] = (
            diagnostic_trace
        )
    result = request(
        opener,
        base_url,
        path,
        method="POST",
        payload=payload,
        request_headers=headers,
    )
    body = _validate_http(
        result,
        expected_status=expected_status,
        expected_request_id=headers["X-Request-ID"],
    )
    require(
        result.headers.get("Idempotency-Replayed") == str(replayed).lower(),
        "P9-01 idempotency response drifted",
    )
    return body


def _revise_command(
    opener,
    base_url: str,
    path: str,
    payload: dict[str, object],
    *,
    csrf_token: str,
    idempotency_key: str,
) -> dict[str, Any]:
    headers = _request_headers(
        "revise", csrf_token=csrf_token, idempotency_key=idempotency_key
    )
    state = _DIAGNOSTIC_STATE.get()
    diagnostic_trace = (
        state.get("trace_id") if isinstance(state, dict) else None
    )
    if (
        (
            ENGINEERING_CHANGE_RUNTIME_REVISE_SERVER_DIAGNOSTICS_ENABLED
            or ENGINEERING_CHANGE_RUNTIME_POST_ROOT_SAVE_DIAGNOSTICS_ENABLED
            or ENGINEERING_CHANGE_RUNTIME_POST_OPTIONAL_EMPTY_DIAGNOSTICS_ENABLED
            or ENGINEERING_CHANGE_RUNTIME_INBOUND_FULL_DIAGNOSTICS_ENABLED
            or ENGINEERING_CHANGE_RUNTIME_POST_RAW_BODY_DIAGNOSTICS_ENABLED
            or ENGINEERING_CHANGE_RUNTIME_POST_MARKER_REPAIR_DIAGNOSTICS_ENABLED
            or ENGINEERING_CHANGE_RUNTIME_POST_LOOPBACK_REPAIR_DIAGNOSTICS_ENABLED
            or ENGINEERING_CHANGE_RUNTIME_POST_SERVICE_ACTOR_REPAIR_DIAGNOSTICS_ENABLED
            or ENGINEERING_CHANGE_RUNTIME_POST_INBOX_INSERT_DIAGNOSTICS_ENABLED
            or ENGINEERING_CHANGE_RUNTIME_POST_DATETIME_REPAIR_DIAGNOSTICS_ENABLED
            or ENGINEERING_CHANGE_RUNTIME_POST_REPLAY_IDENTITY_REPAIR_DIAGNOSTICS_ENABLED
            or ENGINEERING_CHANGE_RUNTIME_POST_SUMMARY_ORDERING_REPAIR_DIAGNOSTICS_ENABLED
            or ENGINEERING_CHANGE_RUNTIME_POST_FORMAL_DATETIME_COMPARISON_REPAIR_DIAGNOSTICS_ENABLED
        )
        and isinstance(diagnostic_trace, str)
        and _TRACE_PATTERN.fullmatch(diagnostic_trace) is not None
    ):
        headers[ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_HEADER] = (
            ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_SCOPE
        )
        headers[ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_TRACE_HEADER] = (
            diagnostic_trace
        )
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_REVISE_REQUEST"
    ):
        result = request(
            opener,
            base_url,
            path,
            method="POST",
            payload=payload,
            request_headers=headers,
        )
    if result.status != 200:
        if type(result.status) is not int or result.status < 100 or result.status > 599:
            status_code = "P901_CHANGE_REVISE_STATUS_INVALID"
        elif result.status < 200:
            status_code = "P901_CHANGE_REVISE_STATUS_INFORMATIONAL"
        elif result.status < 300:
            status_code = "P901_CHANGE_REVISE_STATUS_SUCCESS_NON_200"
        elif result.status < 400:
            status_code = "P901_CHANGE_REVISE_STATUS_REDIRECTION"
        elif result.status < 500:
            status_code = "P901_CHANGE_REVISE_STATUS_CLIENT_ERROR"
        else:
            status_code = "P901_CHANGE_REVISE_STATUS_SERVER_ERROR"
        with engineering_change_runtime_diagnostic_step(status_code):
            raise RuntimeError("P9-01 revise response status class drifted")
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_REVISE_REQUEST_ID"
    ):
        require(
            result.headers.get("X-Request-ID") == headers["X-Request-ID"],
            "P9-01 revise request identity was not echoed",
        )
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_REVISE_CACHE_CONTROL"
    ):
        require(
            result.headers.get("Cache-Control") == "private, no-store",
            "P9-01 revise cache boundary drifted",
        )
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_REVISE_BODY_SHAPE"
    ):
        require(isinstance(result.body, dict), "P9-01 revise response body drifted")
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_REVISE_IDEMPOTENCY"
    ):
        require(
            result.headers.get("Idempotency-Replayed") == "false",
            "P9-01 revise idempotency response drifted",
        )
    return result.body


def _formal_observation() -> dict[str, object]:
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return {
        "doctype": "Engineering Change Request",
        "documentName": f"ECR-RUNTIME-{FIXTURE_RUN_ID[:12]}",
        "rawStatus": "Approved",
        "sourceVersion": "1",
        "sourceModifiedAt": now,
        "sourceHash": canonical_hash(
            {"fixture": FIXTURE_RUN_ID, "kind": "formal-change"}
        ),
        "observedAt": now,
    }


def _inbound_event(change_id: str) -> dict[str, object]:
    observation = _formal_observation()
    payload = {
        "tenantId": TENANT_ID,
        "projectGlobalId": _project_id(),
        "changeGlobalId": change_id,
        "formalChange": observation,
    }
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    event_id = deterministic_uuid("inbound-event")
    return {
        "event_id": event_id,
        "event_type": "npi.erp-engineering-change.v1",
        "event_version": 1,
        "occurred_at": now,
        "source_system": "ERPNEXT",
        "target_system": "NPI_ONE",
        "global_id": deterministic_uuid("inbound-global"),
        "object_type": "Engineering Change Request",
        "source_object_id": observation["documentName"],
        "object_version": 1,
        "idempotency_key": event_id,
        "correlation_id": deterministic_uuid("inbound-correlation"),
        "causation_id": None,
        "trace_id": f"{TRACE_PREFIX}-inbound",
        "actor": {"type": "service", "id": "erpnext-disposable-runtime"},
        "payload_hash": canonical_hash(payload),
        "payload": payload,
        "sensitivity": "confidential",
    }


def _send_inbound(
    base_url: str,
    event: dict[str, object],
    secret: str,
    *,
    replayed: bool,
) -> dict[str, Any]:
    raw = json.dumps(
        event,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    label = "inbound-replay" if replayed else "inbound"
    request_id = deterministic_uuid(f"request:{label}")
    timestamp = str(int(time.time()))
    signing_input = (
        f"npi-change-webhook-v1\nPOST\n{WEBHOOK_PATH}\n{KEY_ID}\n"
        f"{timestamp}\n{request_id}\n"
    ).encode("utf-8") + raw.encode("utf-8")
    signature = hmac.new(
        secret.encode("utf-8"), signing_input, hashlib.sha256
    ).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Forwarded-Proto": "https",
        "X-NPI-Key-ID": KEY_ID,
        "X-NPI-Timestamp": timestamp,
        "X-NPI-Signature": f"v1={signature}",
        "X-Request-ID": request_id,
        "X-Trace-ID": f"{TRACE_PREFIX}-{label}",
    }
    state = _DIAGNOSTIC_STATE.get()
    diagnostic_trace = (
        state.get("trace_id") if isinstance(state, dict) else None
    )
    if (
        (
            ENGINEERING_CHANGE_RUNTIME_INBOUND_FULL_DIAGNOSTICS_ENABLED
            or ENGINEERING_CHANGE_RUNTIME_POST_RAW_BODY_DIAGNOSTICS_ENABLED
            or ENGINEERING_CHANGE_RUNTIME_POST_MARKER_REPAIR_DIAGNOSTICS_ENABLED
            or ENGINEERING_CHANGE_RUNTIME_POST_LOOPBACK_REPAIR_DIAGNOSTICS_ENABLED
            or ENGINEERING_CHANGE_RUNTIME_POST_SERVICE_ACTOR_REPAIR_DIAGNOSTICS_ENABLED
            or ENGINEERING_CHANGE_RUNTIME_POST_INBOX_INSERT_DIAGNOSTICS_ENABLED
            or ENGINEERING_CHANGE_RUNTIME_POST_DATETIME_REPAIR_DIAGNOSTICS_ENABLED
            or ENGINEERING_CHANGE_RUNTIME_POST_REPLAY_IDENTITY_REPAIR_DIAGNOSTICS_ENABLED
            or ENGINEERING_CHANGE_RUNTIME_POST_SUMMARY_ORDERING_REPAIR_DIAGNOSTICS_ENABLED
            or ENGINEERING_CHANGE_RUNTIME_POST_FORMAL_DATETIME_COMPARISON_REPAIR_DIAGNOSTICS_ENABLED
        )
        and isinstance(diagnostic_trace, str)
        and _TRACE_PATTERN.fullmatch(diagnostic_trace) is not None
    ):
        headers[ENGINEERING_CHANGE_INBOUND_SERVER_DIAGNOSTIC_HEADER] = (
            ENGINEERING_CHANGE_INBOUND_SERVER_DIAGNOSTIC_SCOPE
        )
        headers[ENGINEERING_CHANGE_INBOUND_SERVER_DIAGNOSTIC_TRACE_HEADER] = (
            diagnostic_trace
        )
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_INBOUND_REQUEST"
    ):
        result = request(
            urllib.request.build_opener(),
            base_url,
            WEBHOOK_PATH,
            method="POST",
            raw_payload=raw,
            request_headers=headers,
        )
    expected_status = 200 if replayed else 202
    if result.status != expected_status:
        if type(result.status) is not int or result.status < 100 or result.status > 599:
            status_code = "P901_CHANGE_INBOUND_STATUS_INVALID"
        elif result.status < 200:
            status_code = "P901_CHANGE_INBOUND_STATUS_INFORMATIONAL"
        elif result.status < 300:
            status_code = "P901_CHANGE_INBOUND_STATUS_SUCCESS_UNEXPECTED"
        elif result.status < 400:
            status_code = "P901_CHANGE_INBOUND_STATUS_REDIRECTION"
        elif result.status < 500:
            status_code = "P901_CHANGE_INBOUND_STATUS_CLIENT_ERROR"
        else:
            status_code = "P901_CHANGE_INBOUND_STATUS_SERVER_ERROR"
        with engineering_change_runtime_diagnostic_step(status_code):
            raise RuntimeError("P9-01 inbound response status class drifted")
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_INBOUND_REQUEST_ID"
    ):
        require(
            result.headers.get("X-Request-ID") == request_id,
            "P9-01 inbound request identity was not echoed",
        )
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_INBOUND_CACHE_CONTROL"
    ):
        require(
            result.headers.get("Cache-Control") == "no-store",
            "P9-01 inbound cache boundary drifted",
        )
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_INBOUND_BODY_SHAPE"
    ):
        require(isinstance(result.body, dict), "P9-01 inbound response body drifted")
        body = result.body
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_INBOUND_IDEMPOTENCY"
    ):
        require(
            result.headers.get("Idempotency-Replayed") == str(replayed).lower(),
            "P9-01 inbound replay marker drifted",
        )
    return body


def _operations(
    opener, base_url: str, project_id: str, operation_kind: str
) -> dict[str, Any]:
    query = urllib.parse.urlencode({"operationKind": operation_kind, "limit": 50})
    headers = _request_headers(f"operations-{operation_kind}")
    result = request(
        opener,
        base_url,
        f"/api/npi/v1/projects/{urllib.parse.quote(project_id, safe='')}/integration-operations?{query}",
        request_headers=headers,
    )
    body = _validate_http(
        result, expected_status=200, expected_request_id=headers["X-Request-ID"]
    )
    require(
        body.get("projectGlobalId") == project_id
        and isinstance(body.get("items"), list),
        "P9-01 operation collection drifted",
    )
    return body


def _project_id() -> str:
    project_id = os.environ.get("NPI_P9_01C_RUNTIME_PROJECT_ID", "")
    require(_uuid(project_id), "P9-01 runtime Project identity is invalid")
    return project_id


def _runtime_secret() -> str:
    secret = os.environ.get("NPI_P9_01C_RUNTIME_SECRET", "")
    require(
        len(secret) >= 32 and "\n" not in secret and "\r" not in secret,
        "P9-01 runtime secret is unavailable",
    )
    return secret


def _validate_inputs(base_url: str) -> tuple[str, str, str]:
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_INPUT_LOCAL_FIXTURE"
    ):
        normalized_candidate = base_url.rstrip("/")
        with engineering_change_runtime_diagnostic_step(
            "P901_CHANGE_INPUT_BASE_URL"
        ):
            require(
                normalized_candidate == RUNTIME_BASE_URL,
                "P9-01 runtime endpoint drifted",
            )
        with engineering_change_runtime_diagnostic_step(
            "P901_CHANGE_INPUT_URL_SHAPE"
        ):
            parsed = urllib.parse.urlparse(normalized_candidate)
            require(
                parsed.scheme == "http"
                and parsed.hostname == "127.0.0.1"
                and parsed.port == 8003
                and parsed.username is None
                and parsed.password is None
                and parsed.path in {"", "/"}
                and not parsed.params
                and not parsed.query
                and not parsed.fragment,
                "P9-01 runtime URL shape drifted",
            )
        with engineering_change_runtime_diagnostic_step(
            "P901_CHANGE_INPUT_ADMINISTRATOR"
        ):
            require(
                "Administrator" == "Administrator",
                "P9-01 Administrator fixture drifted",
            )
        with engineering_change_runtime_diagnostic_step(
            "P901_CHANGE_INPUT_REQUESTER_DOMAIN"
        ):
            require(
                REQUESTER_USER.lower().endswith("@example.invalid"),
                "P9-01 requester fixture domain drifted",
            )
        with engineering_change_runtime_diagnostic_step(
            "P901_CHANGE_INPUT_REQUESTER_CASE"
        ):
            require(
                REQUESTER_USER == REQUESTER_USER.lower(),
                "P9-01 requester fixture case drifted",
            )
        with engineering_change_runtime_diagnostic_step(
            "P901_CHANGE_INPUT_REQUESTER_STANDARD"
        ):
            require(
                REQUESTER_USER not in {"Administrator", "Guest"},
                "P9-01 requester fixture identity drifted",
            )
        with engineering_change_runtime_diagnostic_step(
            "P901_CHANGE_INPUT_TMP_DIRECTORY"
        ):
            require(
                not (ROOT / "tmp").is_symlink(),
                "P9-01 runtime tmp directory drifted",
            )
        with engineering_change_runtime_diagnostic_step(
            "P901_CHANGE_INPUT_BENCH_DIRECTORY"
        ):
            expected_bench = ROOT / "tmp" / "frappe-bench"
            require(
                BENCH_PATH == expected_bench
                and BENCH_PATH.is_dir()
                and not BENCH_PATH.is_symlink()
                and BENCH_PATH.resolve(strict=True) == expected_bench,
                "P9-01 runtime Bench directory drifted",
            )
        with engineering_change_runtime_diagnostic_step(
            "P901_CHANGE_INPUT_SITE_GUARD"
        ):
            site_guard = ROOT / "scripts" / "verify_local_frappe_site.py"
            require(
                site_guard.is_file() and not site_guard.is_symlink(),
                "P9-01 runtime Site guard drifted",
            )
        with engineering_change_runtime_diagnostic_step(
            "P901_CHANGE_INPUT_DATABASE_ENV"
        ):
            require(
                not any(
                    os.environ.get(name)
                    for name in (
                        "FRAPPE_DB_HOST",
                        "FRAPPE_DB_PORT",
                        "FRAPPE_DB_SOCKET",
                        "FRAPPE_DB_TYPE",
                    )
                ),
                "P9-01 runtime database environment drifted",
            )
        normalized = validate_local_fixture_inputs(
            base_url, "Administrator", REQUESTER_USER
        )
    with engineering_change_runtime_diagnostic_step("P901_CHANGE_INPUT_PROJECT"):
        project_id = _project_id()
    with engineering_change_runtime_diagnostic_step("P901_CHANGE_INPUT_ACTORS"):
        require(
            REQUESTER_USER.endswith("@example.invalid")
            and WORKER_USER.endswith("@example.invalid")
            and REQUESTER_USER not in {"Administrator", "Guest"}
            and WORKER_USER not in {"Administrator", "Guest"}
            and REQUESTER_USER != WORKER_USER
            and WORKER_USER == EXPECTED_WORKER_USER,
            "P9-01 runtime actor boundary drifted",
        )
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_INPUT_RUNTIME_SECRET"
    ):
        secret = _runtime_secret()
    return normalized, project_id, secret


def run_disabled_probe(
    base_url: str, fixture_password: str, project_id: str
) -> dict[str, object]:
    opener = login(base_url, REQUESTER_USER, fixture_password)
    headers = _request_headers("disabled")
    result = request(
        opener,
        base_url,
        _change_path(project_id),
        request_headers=headers,
    )
    require(result.status == 503, "P9-01 disabled route status drifted")
    require(
        result.body.get("code") == "ENGINEERING_CHANGE_ROUTES_DISABLED",
        "P9-01 disabled route problem drifted",
    )
    return {"defaultDisabled": True}


def run_fresh(
    base_url: str, fixture_password: str, project_id: str, secret: str
) -> dict[str, object]:
    with engineering_change_runtime_diagnostic_step("P901_CHANGE_LOGIN"):
        opener = login(base_url, REQUESTER_USER, fixture_password)
    with engineering_change_runtime_diagnostic_step("P901_CHANGE_CSRF"):
        csrf = bootstrap_csrf(opener, base_url, REQUESTER_USER)
    create_path = _change_path(project_id)
    with engineering_change_runtime_diagnostic_step("P901_CHANGE_CREATE_HTTP"):
        created = _command(
            opener,
            base_url,
            create_path,
            {"content": revision_content(complete=False)},
            csrf_token=csrf,
            idempotency_key=CREATE_KEY,
            label="create",
            expected_status=201,
            replayed=False,
        )
    with engineering_change_runtime_diagnostic_step("P901_CHANGE_CREATE_SHAPE"):
        change = created.get("change")
        current = created.get("currentRevision")
        require(
            created.get("operation") == "engineering_change.create"
            and isinstance(change, dict)
            and isinstance(current, dict)
            and change.get("projectGlobalId") == project_id
            and change.get("state") == "draft"
            and current.get("revision") == 1,
            "P9-01 create response drifted",
        )
        change_id = str(change.get("globalId"))
        require(_uuid(change_id), "P9-01 created change identity drifted")
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_CREATE_REPLAY_HTTP"
    ):
        replay = _command(
            opener,
            base_url,
            create_path,
            {"content": revision_content(complete=False)},
            csrf_token=csrf,
            idempotency_key=CREATE_KEY,
            label="create-replay",
            expected_status=201,
            replayed=True,
        )
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_CREATE_REPLAY_SHAPE"
    ):
        require(
            replay.get("change") == change
            and replay.get("currentRevision") == current,
            "P9-01 create replay drifted",
        )
    with engineering_change_runtime_diagnostic_step("P901_CHANGE_STALE_HTTP"):
        stale = dict(predecessor(current))
        stale["expectedRevisionSnapshotHash"] = "f" * 64
        stale_headers = _request_headers(
            "stale-revise",
            csrf_token=csrf,
            idempotency_key=f"p9-stale-{FIXTURE_RUN_ID}",
        )
        stale_result = request(
            opener,
            base_url,
            _change_path(project_id, f"/{change_id}/revisions"),
            method="POST",
            payload={
                "predecessor": stale,
                "content": revision_content(complete=True),
            },
            request_headers=stale_headers,
        )
    with engineering_change_runtime_diagnostic_step("P901_CHANGE_STALE_SHAPE"):
        require(stale_result.status == 409, "P9-01 stale revision did not conflict")
    with engineering_change_runtime_diagnostic_step("P901_CHANGE_REVISE_HTTP"):
        revised = _revise_command(
            opener,
            base_url,
            _change_path(project_id, f"/{change_id}/revisions"),
            {
                "predecessor": predecessor(current),
                "content": revision_content(complete=True),
            },
            csrf_token=csrf,
            idempotency_key=REVISE_KEY,
        )
    with engineering_change_runtime_diagnostic_step("P901_CHANGE_REVISE_SHAPE"):
        current = revised.get("currentRevision")
        require(
            revised.get("operation") == "engineering_change.revise"
            and isinstance(current, dict)
            and current.get("revision") == 2
            and current.get("state") == "active"
            and current.get("readyToClose") is False,
            "P9-01 revision response drifted",
        )
    event = _inbound_event(change_id)
    with engineering_change_runtime_diagnostic_step("P901_CHANGE_INBOUND_HTTP"):
        inbound = _send_inbound(base_url, event, secret, replayed=False)
    with engineering_change_runtime_diagnostic_step("P901_CHANGE_INBOUND_SHAPE"):
        receipt_id = inbound.get("receiptId")
        require(
            _uuid(receipt_id)
            and inbound.get("eventId") == event["event_id"]
            and inbound.get("changeGlobalId") == change_id
            and inbound.get("state") == "pending",
            "P9-01 inbound receipt drifted",
        )
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_INBOUND_WORKER_PARENT"
    ):
        inbound_worker = run_bench_fixture(
            "process_inbox", {"receipt_id": receipt_id, "project_id": project_id}
        )
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_INBOUND_WORKER_SHAPE"
    ):
        require(
            inbound_worker.get("state") == "succeeded",
            "P9-01 inbound worker did not seal success",
        )
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_INBOUND_REPLAY_HTTP"
    ):
        inbound_replay = _send_inbound(base_url, event, secret, replayed=True)
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_INBOUND_REPLAY_SHAPE"
    ):
        require(
            inbound_replay.get("receiptId") == receipt_id
            and inbound_replay.get("state") == "succeeded",
            "P9-01 inbound replay drifted",
        )
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_DETAIL_AFTER_INBOUND"
    ):
        detail = _get_detail(
            opener, base_url, project_id, change_id, "after-inbound"
        )
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_FORMAL_OBSERVATION_SHAPE"
    ):
        current = detail["currentRevision"]
        formal = current.get("formalChange")
        require(
            current.get("revision") == 3
            and current.get("state") == "ready_to_close"
            and current.get("readyToClose") is True
            and isinstance(formal, dict)
            and formal.get("documentName")
            == event["payload"]["formalChange"]["documentName"],
            "P9-01 formal observation drifted",
        )
    with engineering_change_runtime_diagnostic_step("P901_CHANGE_CLOSE_HTTP"):
        closed = _command(
            opener,
            base_url,
            _change_path(project_id, f"/{change_id}:close"),
            {"predecessor": predecessor(current)},
            csrf_token=csrf,
            idempotency_key=CLOSE_KEY,
            label="close",
            expected_status=200,
            replayed=False,
        )
    with engineering_change_runtime_diagnostic_step("P901_CHANGE_CLOSE_SHAPE"):
        current = closed.get("currentRevision")
        require(
            closed.get("operation") == "engineering_change.close"
            and closed.get("change", {}).get("state") == "closed"
            and isinstance(current, dict)
            and current.get("revision") == 4,
            "P9-01 close response drifted",
        )
    with engineering_change_runtime_diagnostic_step("P901_CHANGE_SUMMARY_HTTP"):
        summary = _command(
            opener,
            base_url,
            _change_path(project_id, f"/{change_id}:request-implementation-summary"),
            predecessor(current),
            csrf_token=csrf,
            idempotency_key=SUMMARY_KEY,
            label="summary",
            expected_status=202,
            replayed=False,
        )
    with engineering_change_runtime_diagnostic_step("P901_CHANGE_SUMMARY_SHAPE"):
        event_id = summary.get("outboxEventId")
        require(
            _uuid(summary.get("requestGlobalId"))
            and _uuid(event_id)
            and summary.get("changeGlobalId") == change_id
            and summary.get("state") == "queued",
            "P9-01 implementation summary receipt drifted",
        )
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_SUMMARY_WORKER_PARENT"
    ):
        summary_worker = run_bench_fixture(
            "process_summary", {"event_id": event_id, "project_id": project_id}
        )
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_SUMMARY_WORKER_SHAPE"
    ):
        require(
            summary_worker.get("state") == "synthetic_verified"
            and summary_worker.get("adapterCalls") == 1,
            "P9-01 summary worker boundary drifted",
        )
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_SUMMARY_REPLAY_HTTP"
    ):
        summary_replay = _command(
            opener,
            base_url,
            _change_path(project_id, f"/{change_id}:request-implementation-summary"),
            predecessor(current),
            csrf_token=csrf,
            idempotency_key=SUMMARY_KEY,
            label="summary-replay",
            expected_status=200,
            replayed=True,
        )
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_SUMMARY_REPLAY_SHAPE"
    ):
        require(
            summary_replay.get("requestGlobalId")
            == summary.get("requestGlobalId")
            and summary_replay.get("state") == "synthetic_verified",
            "P9-01 summary replay drifted",
        )
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_INBOUND_OPERATIONS"
    ):
        inbound_operations = _operations(
            opener, base_url, project_id, "receive_engineering_change_event"
        )
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_OUTBOUND_OPERATIONS"
    ):
        outbound_operations = _operations(
            opener, base_url, project_id, "publish_change_implementation_summary"
        )
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_OPERATIONS_SHAPE"
    ):
        require(
            len(inbound_operations["items"]) == 1
            and inbound_operations["items"][0].get("sharedState") == "succeeded"
            and len(outbound_operations["items"]) == 1
            and outbound_operations["items"][0].get("rawState")
            == "synthetic_verified"
            and outbound_operations["items"][0].get("sharedState") == "unavailable",
            "P9-01 integration operation projection drifted",
        )
    return {
        "closed": True,
        "createReplay": True,
        "inboundReplay": True,
        "summarySynthetic": True,
    }


def run_replay(
    base_url: str, fixture_password: str, project_id: str
) -> dict[str, object]:
    opener = login(base_url, REQUESTER_USER, fixture_password)
    csrf = bootstrap_csrf(opener, base_url, REQUESTER_USER)
    replay = _command(
        opener,
        base_url,
        _change_path(project_id),
        {"content": revision_content(complete=False)},
        csrf_token=csrf,
        idempotency_key=CREATE_KEY,
        label="cross-process-create-replay",
        expected_status=201,
        replayed=True,
    )
    change = replay.get("change")
    require(
        isinstance(change, dict) and change.get("state") == "draft",
        "P9-01 retained create receipt drifted",
    )
    current_change, _current = _find_change(_get_changes(opener, base_url, project_id))
    detail = _get_detail(
        opener,
        base_url,
        project_id,
        str(current_change["globalId"]),
        "cross-process-detail",
    )
    require(
        detail["change"].get("state") == "closed"
        and detail["currentRevision"].get("revision") == 4,
        "P9-01 retained closed truth drifted",
    )
    return {"crossProcessReplay": True}


def run_recovered(
    base_url: str, fixture_password: str, project_id: str
) -> dict[str, object]:
    opener = login(base_url, REQUESTER_USER, fixture_password)
    change, _current = _find_change(_get_changes(opener, base_url, project_id))
    detail = _get_detail(
        opener, base_url, project_id, str(change["globalId"]), "recovered"
    )
    require(
        detail["change"].get("state") == "closed",
        "P9-01 route recovery lost retained truth",
    )
    for kind in (
        "receive_engineering_change_event",
        "publish_change_implementation_summary",
    ):
        require(
            len(_operations(opener, base_url, project_id, kind)["items"]) == 1,
            "P9-01 route recovery lost integration history",
        )
    return {"routeRecovered": True}


def run_bench_fixture(method: str, kwargs: dict[str, object]) -> dict[str, Any]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "scripts")
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
        require(completed.returncode == 0, "P9-01 Bench fixture failed")
        output.seek(0)
        lines = [line for line in output if line.strip()]
    require(len(lines) == 1, "P9-01 Bench fixture output drifted")
    result = json.loads(lines[0])
    require(isinstance(result, dict), "P9-01 Bench fixture result drifted")
    return result


def _require_local_fixture(project_id: object) -> str:
    require(
        os.environ.get("NPI_P9_01C_RUNTIME_ENABLED") == "1"
        and os.environ.get("NPI_P9_01C_RUNTIME_PROJECT_ID") == project_id
        and os.environ.get("NPI_P9_01C_RUNTIME_REQUESTER") == REQUESTER_USER
        and os.environ.get("NPI_P9_01C_RUNTIME_WORKER") == WORKER_USER
        and WORKER_USER == EXPECTED_WORKER_USER
        and len(os.environ.get("NPI_P9_01C_RUNTIME_SECRET", "")) >= 32,
        "P9-01 Bench fixture environment drifted",
    )
    require(_uuid(project_id), "P9-01 Bench fixture Project drifted")
    return str(project_id)


def _process_inbox(*, receipt_id: object, project_id: object) -> dict[str, object]:
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_INBOX_CHILD_INPUT"
    ):
        _require_local_fixture(project_id)
        require(_uuid(receipt_id), "P9-01 Inbox receipt drifted")
    from npi_integration.engineering_change.worker import (
        process_engineering_change_inbox,
    )

    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_INBOX_CHILD_WORKER"
    ):
        result = process_engineering_change_inbox(str(receipt_id))
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_INBOX_CHILD_RESPONSE"
    ):
        require(
            isinstance(result, dict) and result.get("receiptId") == receipt_id,
            "P9-01 Inbox worker response drifted",
        )
    return result


def _process_summary(*, event_id: object, project_id: object) -> dict[str, object]:
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_SUMMARY_CHILD_INPUT"
    ):
        _require_local_fixture(project_id)
        require(_uuid(event_id), "P9-01 summary event drifted")
    from npi_integration.engineering_change.runtime_fixture import (
        synthetic_adapter_call_count,
    )
    from npi_integration.engineering_change.worker import (
        execute_change_implementation_summary,
    )

    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_SUMMARY_CHILD_WORKER"
    ):
        result = execute_change_implementation_summary(str(event_id))
    with engineering_change_runtime_diagnostic_step(
        "P901_CHANGE_SUMMARY_CHILD_RESPONSE"
    ):
        require(
            isinstance(result, dict) and result.get("outboxEventId") == event_id,
            "P9-01 summary worker response drifted",
        )
    return {**result, "adapterCalls": synthetic_adapter_call_count()}


def _cleanup(*, project_id: object) -> dict[str, object]:
    project = _require_local_fixture(project_id)
    import frappe

    roots = frappe.get_all(
        "NPI Engineering Change",
        filters={"project_global_id": project, "title": CHANGE_TITLE},
        pluck="name",
        limit_page_length=2,
    )
    require(len(roots) == 1, "P9-01 cleanup root cardinality drifted")
    change_ids = tuple(str(value) for value in roots)
    requests = frappe.get_all(
        "NPI Engineering Change Summary Request",
        filters={"project_global_id": project, "change_global_id": ["in", change_ids]},
        pluck="name",
        limit_page_length=10,
    )
    outboxes = frappe.get_all(
        "NPI Engineering Change Summary Outbox",
        filters={"project_global_id": project, "change_global_id": ["in", change_ids]},
        pluck="name",
        limit_page_length=10,
    )
    if requests:
        frappe.db.delete(
            "NPI Engineering Change Summary Result",
            {"request_global_id": ["in", requests]},
        )
        frappe.db.delete(
            "NPI Engineering Change Summary Attempt",
            {"request_global_id": ["in", requests]},
        )
    if outboxes:
        frappe.db.delete(
            "NPI Engineering Change Summary Outbox", {"name": ["in", outboxes]}
        )
    if requests:
        frappe.db.delete(
            "NPI Engineering Change Summary Request", {"name": ["in", requests]}
        )
    frappe.db.delete(
        "NPI Engineering Change Inbox",
        {"project_global_id": project, "change_global_id": ["in", change_ids]},
    )
    frappe.db.delete(
        "NPI Engineering Change Event", {"change_global_id": ["in", change_ids]}
    )
    frappe.db.delete(
        "NPI Engineering Change Revision", {"change_global_id": ["in", change_ids]}
    )
    frappe.db.delete(
        "NPI Engineering Change Idempotency",
        {
            "project_global_id": project,
            "operation": ["like", "engineering_change.%"],
        },
    )
    audit_ids = tuple((*change_ids, *(str(value) for value in requests)))
    frappe.db.delete("NPI Audit Event", {"global_id": ["in", audit_ids]})
    frappe.db.delete("NPI Engineering Change", {"name": ["in", change_ids]})
    frappe.db.commit()
    remaining = sum(
        frappe.db.count(doctype, filters)
        for doctype, filters in (
            (
                "NPI Engineering Change",
                {"project_global_id": project, "title": CHANGE_TITLE},
            ),
            (
                "NPI Engineering Change Inbox",
                {"project_global_id": project, "change_global_id": ["in", change_ids]},
            ),
            (
                "NPI Engineering Change Summary Request",
                {"project_global_id": project, "change_global_id": ["in", change_ids]},
            ),
            (
                "NPI Engineering Change Summary Outbox",
                {"project_global_id": project, "change_global_id": ["in", change_ids]},
            ),
            (
                "NPI Engineering Change Idempotency",
                {
                    "project_global_id": project,
                    "operation": ["like", "engineering_change.%"],
                },
            ),
            ("NPI Audit Event", {"global_id": ["in", audit_ids]}),
        )
    )
    require(remaining == 0, "P9-01 cleanup did not remove exact fixtures")
    return {"cleanupComplete": True}


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    import frappe

    fixtures = {
        "cleanup": _cleanup,
        "process_inbox": _process_inbox,
        "process_summary": _process_summary,
    }
    trace_id = os.environ.get(_DIAGNOSTIC_TRACE_ENV, "")
    with engineering_change_runtime_diagnostic_scope(trace_id):
        require(method in fixtures, "P9-01 Bench fixture is unavailable")
        with engineering_change_runtime_diagnostic_step("P901_CHANGE_BENCH_INIT"):
            frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
        with engineering_change_runtime_diagnostic_step(
            "P901_CHANGE_BENCH_CONNECT"
        ):
            frappe.connect()
        try:
            with engineering_change_runtime_diagnostic_step(
                "P901_CHANGE_BENCH_MARKER"
            ):
                require(
                    frappe.conf.get("npi_runtime_disposable_marker")
                    == RUNTIME_MARKER,
                    "P9-01 disposable Site marker drifted",
                )
            result = fixtures[method](**kwargs)
            frappe.db.commit()
            print(json.dumps(result, separators=(",", ":"), sort_keys=True))
        except Exception:
            frappe.db.rollback()
            raise
        finally:
            frappe.destroy()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url")
    parser.add_argument("--project-id")
    parser.add_argument("--disabled-probe", action="store_true")
    parser.add_argument("--replay-only", action="store_true")
    parser.add_argument("--recovered-probe", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--bench-fixture")
    parser.add_argument("--fixture-kwargs")
    parser.add_argument("--diagnostic-trace", action="store_true")
    parser.add_argument("--read-diagnostic")
    parser.add_argument("--expected-trace")
    arguments = parser.parse_args()
    if arguments.diagnostic_trace:
        require(
            arguments.base_url is None
            and arguments.project_id is None
            and arguments.bench_fixture is None
            and arguments.fixture_kwargs is None
            and arguments.read_diagnostic is None
            and arguments.expected_trace is None
            and not any(
                (
                    arguments.disabled_probe,
                    arguments.replay_only,
                    arguments.recovered_probe,
                    arguments.cleanup,
                )
            ),
            "P9-01 diagnostic trace invocation drifted",
        )
        print(engineering_change_runtime_diagnostic_trace())
        return 0
    if arguments.read_diagnostic:
        if (
            arguments.base_url is not None
            or arguments.project_id is not None
            or arguments.bench_fixture is not None
            or arguments.fixture_kwargs is not None
            or arguments.expected_trace is None
            or any(
                (
                    arguments.disabled_probe,
                    arguments.replay_only,
                    arguments.recovered_probe,
                    arguments.cleanup,
                )
            )
        ):
            return 2
        diagnostic = read_engineering_change_runtime_diagnostic(
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
        require(
            arguments.base_url is None
            and arguments.project_id is None
            and arguments.fixture_kwargs is not None
            and not any(
                (
                    arguments.disabled_probe,
                    arguments.replay_only,
                    arguments.recovered_probe,
                    arguments.cleanup,
                )
            ),
            "P9-01 Bench fixture invocation drifted",
        )
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "P9-01 Bench fixture arguments drifted")
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return 0
    trace_id = engineering_change_runtime_diagnostic_trace()
    os.environ[_DIAGNOSTIC_TRACE_ENV] = trace_id
    with engineering_change_runtime_diagnostic_scope(trace_id):
        with engineering_change_runtime_diagnostic_step(
            "P901_CHANGE_INVOCATION"
        ):
            require(
                isinstance(arguments.base_url, str)
                and arguments.project_id
                == os.environ.get("NPI_P9_01C_RUNTIME_PROJECT_ID")
                and sum(
                    map(
                        int,
                        (
                            arguments.disabled_probe,
                            arguments.replay_only,
                            arguments.recovered_probe,
                            arguments.cleanup,
                        ),
                    )
                )
                <= 1,
                "P9-01 runtime invocation drifted",
            )
        with engineering_change_runtime_diagnostic_step("P901_CHANGE_INPUTS"):
            base_url, project_id, secret = _validate_inputs(arguments.base_url)
        with engineering_change_runtime_diagnostic_step(
            "P901_CHANGE_FIXTURE_SECRET"
        ):
            fixture_password = secret_from_environment(
                "NPI_RUNTIME_FIXTURE_PASSWORD"
            )
        if arguments.disabled_probe:
            with engineering_change_runtime_diagnostic_step(
                "P901_CHANGE_DISABLED_PARENT"
            ):
                result = run_disabled_probe(base_url, fixture_password, project_id)
        elif arguments.replay_only:
            with engineering_change_runtime_diagnostic_step(
                "P901_CHANGE_REPLAY_PARENT"
            ):
                result = run_replay(base_url, fixture_password, project_id)
        elif arguments.recovered_probe:
            with engineering_change_runtime_diagnostic_step(
                "P901_CHANGE_RECOVERED_PARENT"
            ):
                result = run_recovered(base_url, fixture_password, project_id)
        elif arguments.cleanup:
            with engineering_change_runtime_diagnostic_step(
                "P901_CHANGE_CLEANUP_PARENT"
            ):
                result = run_bench_fixture("cleanup", {"project_id": project_id})
        else:
            with engineering_change_runtime_diagnostic_step(
                "P901_CHANGE_FRESH_PARENT"
            ):
                result = run_fresh(
                    base_url, fixture_password, project_id, secret
                )
        with engineering_change_runtime_diagnostic_step("P901_CHANGE_RESULT"):
            require(
                result and all(value is True for value in result.values()),
                "P9-01 runtime result drifted",
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
