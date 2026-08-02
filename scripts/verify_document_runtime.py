from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from verify_frappe_runtime import (
    HttpResult,
    create_disposable_user,
    delete_disposable_user,
    login,
    request,
    require,
    secret_from_environment,
    user_resource_path,
    validate_disposable_user,
    validate_local_fixture_inputs,
    validate_problem,
)
from verify_project_runtime import (
    TENANT_ID,
    bootstrap_csrf,
    create_resource,
    get_resource,
    list_resources,
    post_project,
    update_resource,
)


FIXTURE_REVISION = 1
FIXTURE_RUN_ID_ENV = "NPI_DOCUMENT_RUNTIME_RUN_ID"
SITE_NAME = "npi.localhost"
RUNTIME_MARKER = "npi-one-local-runtime-disposable-v1"
DATABASE_NAME = "npi_one_runtime"
DATABASE_USER = "npi_one_runtime"
DATABASE_PORT = 3306
ROOT = Path(__file__).resolve().parents[1]
BENCH_PATH = ROOT / "tmp" / "frappe-bench"
DOCUMENT_DOCTYPES = (
    "NPI Document Policy",
    "NPI Document Policy Version",
    "NPI Controlled Document",
    "NPI Document Revision",
    "NPI Document Revision File",
    "NPI Document Relationship",
    "NPI Document Lock Event",
    "NPI Document Command Idempotency",
    "NPI Document Share Grant",
    "NPI Document Release Policy",
    "NPI Document Release Policy Version",
    "NPI Document Revision Lifecycle",
    "NPI Document Review Cycle",
    "NPI Document Confirmation",
    "NPI Document Lifecycle Event",
    "NPI Document Baseline Policy",
    "NPI Document Baseline Policy Version",
    "NPI Document Baseline",
    "NPI Document Baseline Member",
    "NPI Baseline Command Idempotency",
    "NPI Baseline Gate Dependency",
    "NPI Baseline Impact Event",
)


def build_synthetic_pdf() -> bytes:
    """Build one deterministic, structurally valid, JavaScript-free PDF page."""

    content = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    objects = (
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R "
            b"/MediaBox [0 0 200 200] /Contents 4 0 R >>"
        ),
        b"<< /Length 0 >>\nstream\n\nendstream",
    )
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(content))
        content.extend(f"{number} 0 obj\n".encode("ascii"))
        content.extend(body)
        content.extend(b"\nendobj\n")

    xref_offset = len(content)
    content.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    content.extend(
        (
            f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(content)


PDF_CONTENT = build_synthetic_pdf()
_DIAGNOSTIC_TEXT_LIMIT = 240
_DIAGNOSTIC_LOG_TAIL_LIMIT = 64 * 1024
_DIAGNOSTIC_TYPE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,127}$")
_DIAGNOSTIC_TRACE_PATTERN = re.compile(r"^trace-[a-f0-9]{32}$")
_UNEXPECTED_BFF_DIAGNOSTIC_CODE = "UNEXPECTED_BFF_EXCEPTION"
_CHECKOUT_STAGE_DIAGNOSTIC_CODES = frozenset(
    {
        "DOCUMENT_CHECKOUT_RECEIPT_INSERT",
        "DOCUMENT_CHECKOUT_LOCK_EVENT_INSERT",
        "DOCUMENT_CHECKOUT_PROJECTION_SAVE",
        "DOCUMENT_CHECKOUT_AUDIT_APPEND",
        "DOCUMENT_CHECKOUT_RESPONSE_BUILD",
        "DOCUMENT_CHECKOUT_RECEIPT_SEAL",
    }
)
_PROJECTION_VALIDATION_DIAGNOSTIC_CODES = frozenset(
    {
        "DOCUMENT_CHECKOUT_PROJECTION_NORMALIZE_INPUT",
        "DOCUMENT_CHECKOUT_PROJECTION_IMMUTABLE_IDENTITY",
        "DOCUMENT_CHECKOUT_PROJECTION_POLICY_IDENTITY",
        "DOCUMENT_CHECKOUT_PROJECTION_DOMAIN_RECONSTRUCTION",
        "DOCUMENT_CHECKOUT_PROJECTION_NORMALIZE_IDENTITY",
        "DOCUMENT_CHECKOUT_PROJECTION_VERSION",
        "DOCUMENT_CHECKOUT_PROJECTION_REVISION",
        "DOCUMENT_CHECKOUT_PROJECTION_LOCK",
        "DOCUMENT_CHECKOUT_PROJECTION_NORMALIZE_PROJECTION",
        "DOCUMENT_CHECKOUT_PROJECTION_COMMAND_GUARD",
        "DOCUMENT_CHECKOUT_PROJECTION_FRAPPE_STANDARD_VALIDATION",
        "DOCUMENT_CHECKOUT_PROJECTION_POST_SAVE_HOOK",
        "DOCUMENT_CHECKOUT_PROJECTION_SAVE_LIFECYCLE",
    }
)
_REVISION_STAGE_DIAGNOSTIC_CODES = frozenset(
    {
        "DOCUMENT_REVISION_RECEIPT_INSERT",
        "DOCUMENT_REVISION_PRIVATE_FILE_SAVE",
        "DOCUMENT_REVISION_FILE_REVISION_INSERT",
        "DOCUMENT_REVISION_DOMAIN_APPEND",
        "DOCUMENT_REVISION_RECORD_INSERT",
        "DOCUMENT_REVISION_FILE_ASSOCIATION_INSERT",
        "DOCUMENT_REVISION_PROJECTION_SAVE",
        "DOCUMENT_REVISION_AUDIT_APPEND",
        "DOCUMENT_REVISION_RESPONSE_BUILD",
        "DOCUMENT_REVISION_RECEIPT_SEAL",
    }
)
_RUNTIME_RELATIONSHIP_DIAGNOSTIC_CODES = frozenset(
    {
        "P5_RUNTIME_RELATIONSHIP_FILTER_HTTP",
        "P5_RUNTIME_RELATIONSHIP_FILTER_CARDINALITY",
        "P5_RUNTIME_RELATIONSHIP_FILTER_IDENTITY",
    }
)
_BASELINE_WORKSPACE_DIAGNOSTIC_CODES = frozenset(
    {
        "P503_RUNTIME_BASELINE_WORKSPACE_HTTP",
        "P503_RUNTIME_BASELINE_WORKSPACE_BODY_SHAPE",
        "P503_RUNTIME_BASELINE_WORKSPACE_PERMISSIONS_SHAPE",
        "P503_RUNTIME_BASELINE_WORKSPACE_VIEW_PERMISSION",
        "P503_RUNTIME_BASELINE_WORKSPACE_CREATE_PERMISSION",
        "P503_RUNTIME_BASELINE_WORKSPACE_ITEMS_EMPTY",
        "P503_RUNTIME_BASELINE_WORKSPACE_IMPACTS_EMPTY",
        "P503_RUNTIME_BASELINE_WORKSPACE_POLICY_CARDINALITY",
        "P503_RUNTIME_BASELINE_WORKSPACE_POLICY_SHAPE",
        "P503_RUNTIME_BASELINE_WORKSPACE_POLICY_IDENTITY",
        "P503_RUNTIME_BASELINE_WORKSPACE_POLICY_VERSION",
        "P503_RUNTIME_BASELINE_WORKSPACE_POLICY_HASH",
        "P503_RUNTIME_BASELINE_WORKSPACE_POLICY_KEY",
        "P503_RUNTIME_BASELINE_WORKSPACE_POLICY_TITLE",
    }
)
_BASELINE_WORKSPACE_SERVER_DIAGNOSTIC_CODES = frozenset(
    {
        "P503_BASELINE_WORKSPACE_DOCUMENT_ROUTE_ENABLEMENT",
        "P503_BASELINE_WORKSPACE_BASELINE_ROUTE_ENABLEMENT",
        "P503_BASELINE_WORKSPACE_AUTHENTICATION",
        "P503_BASELINE_WORKSPACE_PRINCIPAL",
        "P503_BASELINE_WORKSPACE_REPOSITORY_FACTORY",
        "P503_BASELINE_WORKSPACE_ROUTE_SCOPE",
        "P503_BASELINE_WORKSPACE_REQUEST_FIELDS",
        "P503_BASELINE_WORKSPACE_REQUEST_ID",
        "P503_BASELINE_WORKSPACE_PROJECT_LOOKUP",
        "P503_BASELINE_WORKSPACE_PROJECT_IDENTITY",
        "P503_BASELINE_WORKSPACE_PROJECT_INTERNAL_PRINCIPAL",
        "P503_BASELINE_WORKSPACE_PROJECT_TENANT",
        "P503_BASELINE_WORKSPACE_PROJECT_MEMBERSHIP_QUERY",
        "P503_BASELINE_WORKSPACE_PROJECT_MEMBERSHIP_LOAD",
        "P503_BASELINE_WORKSPACE_PROJECT_MEMBERSHIP_ABSENT",
        "P503_BASELINE_WORKSPACE_PROJECT_MEMBERSHIP_EFFECTIVITY",
        "P503_BASELINE_WORKSPACE_PROJECT_MEMBER_USER",
        "P503_BASELINE_WORKSPACE_PROJECT_MEMBERSHIP_CARDINALITY",
        "P503_BASELINE_WORKSPACE_POLICY_QUERY",
        "P503_BASELINE_WORKSPACE_POLICY_ROW",
        "P503_BASELINE_WORKSPACE_POLICY_LOAD",
        "P503_BASELINE_WORKSPACE_BASELINE_QUERY",
        "P503_BASELINE_WORKSPACE_BASELINE_LOAD",
        "P503_BASELINE_WORKSPACE_IMPACT_QUERY",
        "P503_BASELINE_WORKSPACE_IMPACT_LOAD",
        "P503_BASELINE_WORKSPACE_REPOSITORY_RESPONSE",
        "P503_BASELINE_WORKSPACE_API_RESPONSE",
    }
)
_RUNTIME_DIAGNOSTIC_CODES = (
    _RUNTIME_RELATIONSHIP_DIAGNOSTIC_CODES
    | _BASELINE_WORKSPACE_DIAGNOSTIC_CODES
    | _BASELINE_WORKSPACE_SERVER_DIAGNOSTIC_CODES
)
_SENSITIVE_DIAGNOSTIC_PATTERN = re.compile(
    r"\b(?:authorization|cookie|csrf|password|passwd|pwd|secret|token)\b",
    re.IGNORECASE,
)
_BASELINE_WORKSPACE_SERVER_DIAGNOSTIC_HEADER = "X-NPI-Diagnostic-Scope"
_BASELINE_WORKSPACE_SERVER_DIAGNOSTIC_SCOPE = (
    "p503-baseline-workspace-http-v1"
)


def validated_fixture_run_id(candidate: str | None) -> str:
    require(
        isinstance(candidate, str)
        and re.fullmatch(r"[a-f0-9]{32}", candidate) is not None,
        (
            f"{FIXTURE_RUN_ID_ENV} must be exactly 32 lowercase "
            "hexadecimal characters"
        ),
    )
    return candidate


CALLER_SUPPLIED_FIXTURE_RUN_ID = os.environ.get(FIXTURE_RUN_ID_ENV)
FIXTURE_RUN_ID = (
    validated_fixture_run_id(CALLER_SUPPLIED_FIXTURE_RUN_ID)
    if CALLER_SUPPLIED_FIXTURE_RUN_ID is not None
    else "0" * 32
)
FIXTURE_NAMESPACE = f"r{FIXTURE_REVISION}-{FIXTURE_RUN_ID}"
FIXTURE_PREFIX = f"p5-01-runtime-{FIXTURE_NAMESPACE}"


def fixture_id(scope: str) -> str:
    return str(
        uuid5(
            NAMESPACE_URL,
            (
                "https://npi-one.example.invalid/runtime/p5-01/"
                f"{FIXTURE_NAMESPACE}/{scope}"
            ),
        )
    )


PROJECT_TEMPLATE_ID = fixture_id("project-template")
PROJECT_TEMPLATE_VERSION = 1
PROJECT_TEMPLATE_VERSION_KEY = (
    f"{PROJECT_TEMPLATE_ID}:{PROJECT_TEMPLATE_VERSION}"
)
DOCUMENT_POLICY_ID = fixture_id("document-policy")
DOCUMENT_POLICY_VERSION = 1
DOCUMENT_POLICY_VERSION_KEY = (
    f"{DOCUMENT_POLICY_ID}:{DOCUMENT_POLICY_VERSION}"
)
DOCUMENT_RELEASE_POLICY_ID = fixture_id("document-release-policy")
DOCUMENT_RELEASE_POLICY_VERSION = 1
DOCUMENT_RELEASE_POLICY_VERSION_KEY = (
    f"{DOCUMENT_RELEASE_POLICY_ID}:{DOCUMENT_RELEASE_POLICY_VERSION}"
)
DOCUMENT_BASELINE_POLICY_ID = fixture_id("document-baseline-policy")
DOCUMENT_BASELINE_POLICY_VERSION = 1
DOCUMENT_BASELINE_POLICY_VERSION_KEY = (
    f"{DOCUMENT_BASELINE_POLICY_ID}:{DOCUMENT_BASELINE_POLICY_VERSION}"
)
GATE_TEMPLATE_ID = fixture_id("gate-template")
GATE_TEMPLATE_VERSION = 1
GATE_TEMPLATE_VERSION_KEY = f"{GATE_TEMPLATE_ID}:{GATE_TEMPLATE_VERSION}"
GATE_TEMPLATE_CODE = f"P503-GATE-{FIXTURE_RUN_ID[:12].upper()}"
GATE_KEY = "G0"
GATE_REQUIREMENT_KEY = "released_design_baseline"
PROJECT_WORK_POLICY_ID = fixture_id("project-work-policy")
PROJECT_WORK_POLICY_VERSION = 1
PROJECT_WORK_POLICY_VERSION_KEY = (
    f"{PROJECT_WORK_POLICY_ID}:{PROJECT_WORK_POLICY_VERSION}"
)
PROJECT_WORK_POLICY_KEY = f"p5_03_runtime_work_{FIXTURE_RUN_ID}"
BASELINE_MEMBER_ID = fixture_id("baseline-member")
BASELINE_ROLE_ASSIGNMENT_ID = fixture_id("baseline-role-assignment")
BASELINE_RACI_ID = fixture_id("baseline-gate-raci")
BASELINE_ROLE_KEY = "baseline_owner"
GATE_REVIEW_POLICY_ID = fixture_id("gate-review-policy")
GATE_REVIEW_POLICY_VERSION = 1
GATE_REVIEW_POLICY_VERSION_KEY = (
    f"{GATE_REVIEW_POLICY_ID}:{GATE_REVIEW_POLICY_VERSION}"
)
GATE_REVIEW_POLICY_CODE = f"P503-REVIEW-{FIXTURE_RUN_ID[:12].upper()}"
GATE_REVIEW_STEP_KEY = "baseline_review"
GATE_REVIEW_SLOT = "baseline_reviewer"
GATE_DECISION_SLOT = "baseline_decider"
GATE_REOPEN_SLOT = "baseline_reopener"
OWNER_USER = (
    f"npi-document-{FIXTURE_RUN_ID[:20]}-owner@example.invalid"
)
BASELINE_USER = (
    f"npi-document-{FIXTURE_RUN_ID[:20]}-baseline@example.invalid"
)
UNRELATED_USER = (
    f"npi-document-{FIXTURE_RUN_ID[:20]}-unrelated@example.invalid"
)
BUSINESS_CODE = f"P5-01-{FIXTURE_RUN_ID[:16].upper()}"
PROJECT_TEMPLATE_CODE = f"P501-{FIXTURE_RUN_ID[:16].upper()}"
POLICY_KEY = f"p5_01_runtime_{FIXTURE_RUN_ID}"
RELEASE_POLICY_KEY = f"p5_02_runtime_{FIXTURE_RUN_ID}"
BASELINE_POLICY_KEY = f"p5_03_runtime_{FIXTURE_RUN_ID}"
PROJECT_CREATE_KEY = f"{FIXTURE_PREFIX}-project-create"
PROJECT_TEAM_KEY = f"{FIXTURE_PREFIX}-project-team"
DOCUMENT_CREATE_KEY = f"{FIXTURE_PREFIX}-document-create"
DOCUMENT_CHECK_OUT_KEY = f"{FIXTURE_PREFIX}-document-check-out"
DOCUMENT_REVISION_KEY = f"{FIXTURE_PREFIX}-document-revision"
DOCUMENT_CONTENT_KEY = f"{FIXTURE_PREFIX}-document-content"
DOCUMENT_CHECK_IN_KEY = f"{FIXTURE_PREFIX}-document-check-in"
DOCUMENT_REVIEW_SUBMIT_KEY = f"{FIXTURE_PREFIX}-review-submit"
DOCUMENT_REVIEW_REJECT_KEY = f"{FIXTURE_PREFIX}-review-reject"
DOCUMENT_REVIEW_RESUBMIT_KEY = f"{FIXTURE_PREFIX}-review-resubmit"
DOCUMENT_REVIEW_APPROVE_KEY = f"{FIXTURE_PREFIX}-review-approve"
DOCUMENT_RELEASE_KEY = f"{FIXTURE_PREFIX}-release"
DOCUMENT_BASELINE_KEY = f"{FIXTURE_PREFIX}-baseline-create"
GATE_FREEZE_KEY = f"{FIXTURE_PREFIX}-gate-freeze"
GATE_BASELINE_ATTACH_KEY = f"{FIXTURE_PREFIX}-gate-baseline-attach"
GATE_REVIEW_START_KEY = f"{FIXTURE_PREFIX}-gate-review-start"
DOCUMENT_SUCCESSOR_CHECK_OUT_KEY = (
    f"{FIXTURE_PREFIX}-successor-check-out"
)
DOCUMENT_SUCCESSOR_KEY = f"{FIXTURE_PREFIX}-successor-registered"
DOCUMENT_UNREGISTERED_SUCCESSOR_KEY = (
    f"{FIXTURE_PREFIX}-successor-unregistered"
)


@dataclass(frozen=True)
class BinaryHttpResult:
    status: int
    headers: Any
    content: bytes
    problem: dict[str, Any] | None


class RuntimeSubstageFailure(RuntimeError):
    """Closed verifier failure that exposes no response or exception text."""

    def __init__(
        self,
        code: str,
        trace_id: str,
        *,
        exception_type: str = "RuntimeSubstageFailure",
    ) -> None:
        super().__init__("Controlled Document runtime substage failed")
        if _DIAGNOSTIC_TYPE_PATTERN.fullmatch(exception_type) is None:
            raise ValueError("Runtime diagnostic exception type is invalid")
        self.code = code
        self.trace_id = trace_id
        self.exception_type = exception_type


def require_runtime_substage(
    condition: bool,
    *,
    code: str,
    trace_id: str,
) -> None:
    if code not in _RUNTIME_DIAGNOSTIC_CODES:
        raise ValueError("Runtime diagnostic code is not allowlisted")
    if _DIAGNOSTIC_TRACE_PATTERN.fullmatch(trace_id) is None:
        raise ValueError("Runtime diagnostic trace identity is invalid")
    if not condition:
        raise RuntimeSubstageFailure(code, trace_id)


def runtime_substage_diagnostic(error: RuntimeSubstageFailure) -> str:
    return (
        f"[diagnostic_code={error.code}; "
        f"exc_type={error.exception_type}; "
        f"trace_id={error.trace_id}]"
    )


def fixture_request_id(key: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{FIXTURE_PREFIX}/request/{key}"))


def fixture_trace_id(key: str) -> str:
    return f"trace-{uuid5(NAMESPACE_URL, f'{FIXTURE_PREFIX}/trace/{key}').hex}"


def require_http_status(
    result: HttpResult,
    expected_statuses: set[int],
    operation: str,
) -> None:
    if result.status in expected_statuses:
        return
    require(
        False,
        (
            f"{operation} returned HTTP {result.status}"
            f"{sanitized_http_failure(result)}"
        ),
    )


def sanitized_http_failure(result: HttpResult) -> str:
    """Expose only bounded Frappe type/message diagnostics for a failed fixture."""

    log_diagnostic = _sanitized_bff_log_diagnostic(result.trace_id)
    if log_diagnostic is not None:
        diagnostic_type, diagnostic_code, diagnostic_trace_id = log_diagnostic
        return (
            f" [diagnostic_code={diagnostic_code}; "
            f"exc_type={diagnostic_type}; "
            f"trace_id={diagnostic_trace_id}]"
        )
    details: list[str] = []
    exc_type = result.body.get("exc_type")
    if (
        isinstance(exc_type, str)
        and _DIAGNOSTIC_TYPE_PATTERN.fullmatch(exc_type) is not None
    ):
        details.append(f"exc_type={exc_type}")
    message = _sanitized_server_message(result.body)
    if message:
        details.append(f"message={message}")
    return f" [{'; '.join(details)}]" if details else ""


def _sanitized_bff_log_diagnostic(
    trace_id: str | None,
) -> tuple[str, str, str] | None:
    """Read only the existing safe BFF diagnostic record for this exact trace."""

    if (
        not isinstance(trace_id, str)
        or _DIAGNOSTIC_TRACE_PATTERN.fullmatch(trace_id) is None
    ):
        return None
    try:
        bench_root = BENCH_PATH.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    candidates = (
        BENCH_PATH / "logs" / "npi_core.log",
        BENCH_PATH / "sites" / SITE_NAME / "logs" / "npi_core.log",
    )
    decoder = json.JSONDecoder()
    stage_diagnostic: tuple[str, str, str] | None = None
    generic_diagnostic: tuple[str, str, str] | None = None
    for candidate in candidates:
        try:
            if candidate.is_symlink() or not candidate.is_file():
                continue
            resolved = candidate.resolve(strict=True)
            if not resolved.is_relative_to(bench_root):
                continue
            with resolved.open("rb") as log_file:
                log_file.seek(0, os.SEEK_END)
                size = log_file.tell()
                log_file.seek(max(0, size - _DIAGNOSTIC_LOG_TAIL_LIMIT))
                tail = log_file.read(_DIAGNOSTIC_LOG_TAIL_LIMIT)
        except (OSError, RuntimeError):
            continue
        for line in reversed(tail.decode("utf-8", errors="ignore").splitlines()):
            if trace_id not in line:
                continue
            for start, character in enumerate(line):
                if character != "{":
                    continue
                try:
                    record, _ = decoder.raw_decode(line[start:])
                except (TypeError, ValueError):
                    continue
                if not isinstance(record, dict) or set(record) != {
                    "code",
                    "exceptionType",
                    "traceId",
                }:
                    continue
                diagnostic_type = record.get("exceptionType")
                if (
                    record.get("traceId") == trace_id
                    and isinstance(diagnostic_type, str)
                    and _DIAGNOSTIC_TYPE_PATTERN.fullmatch(diagnostic_type)
                    is not None
                ):
                    diagnostic_code = record.get("code")
                    if (
                        isinstance(diagnostic_code, str)
                        and diagnostic_code
                        in _BASELINE_WORKSPACE_SERVER_DIAGNOSTIC_CODES
                    ):
                        return diagnostic_type, diagnostic_code, trace_id
                    if (
                        isinstance(diagnostic_code, str)
                        and diagnostic_code
                        in _PROJECTION_VALIDATION_DIAGNOSTIC_CODES
                    ):
                        return diagnostic_type, diagnostic_code, trace_id
                    if (
                        isinstance(diagnostic_code, str)
                        and diagnostic_code
                        in (
                            _CHECKOUT_STAGE_DIAGNOSTIC_CODES
                            | _REVISION_STAGE_DIAGNOSTIC_CODES
                        )
                        and stage_diagnostic is None
                    ):
                        stage_diagnostic = (
                            diagnostic_type,
                            diagnostic_code,
                            trace_id,
                        )
                    if diagnostic_code == _UNEXPECTED_BFF_DIAGNOSTIC_CODE:
                        generic_diagnostic = (
                            diagnostic_type,
                            _UNEXPECTED_BFF_DIAGNOSTIC_CODE,
                            trace_id,
                        )
    return stage_diagnostic or generic_diagnostic


def _sanitized_server_message(body: dict[str, Any]) -> str | None:
    candidates: list[object] = [body.get("message")]
    server_messages = body.get("_server_messages")
    if isinstance(server_messages, str):
        try:
            server_messages = json.loads(server_messages)
        except (TypeError, ValueError):
            server_messages = None
    if isinstance(server_messages, list):
        candidates.extend(server_messages[:3])
    for candidate in candidates:
        if isinstance(candidate, str):
            try:
                decoded = json.loads(candidate)
            except (TypeError, ValueError):
                decoded = candidate
            candidate = decoded
        if isinstance(candidate, dict):
            candidate = candidate.get("message")
        if not isinstance(candidate, str):
            continue
        text = re.sub(r"<[^>]*>", " ", html.unescape(candidate))
        text = " ".join(text.split())
        if not text or _SENSITIVE_DIAGNOSTIC_PATTERN.search(text):
            continue
        return text[:_DIAGNOSTIC_TEXT_LIMIT]
    return None


def command_headers(
    csrf_token: str | None,
    idempotency_key: str,
) -> dict[str, str]:
    headers = {
        "Idempotency-Key": idempotency_key,
        "X-Request-ID": fixture_request_id(idempotency_key),
        "X-Trace-ID": fixture_trace_id(idempotency_key),
    }
    if csrf_token is not None:
        headers["X-Frappe-CSRF-Token"] = csrf_token
    return headers


def query_headers(key: str) -> dict[str, str]:
    return {
        "X-Request-ID": fixture_request_id(key),
        "X-Trace-ID": fixture_trace_id(key),
    }


def npi_request(
    opener,
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    csrf_token: str | None = None,
    idempotency_key: str | None = None,
    query_key: str = "query",
    server_diagnostic_scope: str | None = None,
) -> HttpResult:
    headers = (
        command_headers(csrf_token, idempotency_key)
        if idempotency_key is not None
        else query_headers(f"{query_key}-{uuid4().hex}")
    )
    if server_diagnostic_scope is not None:
        require(
            server_diagnostic_scope
            == _BASELINE_WORKSPACE_SERVER_DIAGNOSTIC_SCOPE,
            "NPI server diagnostic scope is not allowlisted",
        )
        headers[_BASELINE_WORKSPACE_SERVER_DIAGNOSTIC_HEADER] = (
            server_diagnostic_scope
        )
    result = request(
        opener,
        base_url,
        path,
        method=method,
        payload=payload,
        request_headers=headers,
    )
    require(
        result.headers.get("X-Request-ID") == headers["X-Request-ID"],
        f"NPI request identity was not echoed for {path}",
    )
    require(
        result.headers.get("Cache-Control") == "private, no-store",
        f"NPI cache control drifted for {path}",
    )
    return HttpResult(
        result.status,
        result.headers,
        result.body,
        request_id=headers["X-Request-ID"],
        trace_id=headers["X-Trace-ID"],
    )


def multipart_revision_request(
    opener,
    base_url: str,
    path: str,
    *,
    csrf_token: str,
    idempotency_key: str,
    metadata: dict[str, object],
    file_name: str,
    content: bytes,
) -> HttpResult:
    boundary = f"npi-one-{FIXTURE_RUN_ID}-{uuid4().hex}"
    metadata_bytes = json.dumps(
        metadata,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    body = b"".join(
        (
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="metadata"\r\n',
            b"Content-Type: application/json\r\n\r\n",
            metadata_bytes,
            b"\r\n",
            f"--{boundary}\r\n".encode(),
            (
                'Content-Disposition: form-data; name="file"; '
                f'filename="{file_name}"\r\n'
            ).encode(),
            b"Content-Type: application/pdf\r\n\r\n",
            content,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        )
    )
    headers = command_headers(csrf_token, idempotency_key)
    headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    http_request = urllib.request.Request(
        f"{base_url}{path}",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with opener.open(http_request, timeout=30) as response:
            result = HttpResult(
                response.status,
                response.headers,
                json.loads(response.read().decode("utf-8")),
            )
    except urllib.error.HTTPError as error:
        result = HttpResult(
            error.code,
            error.headers,
            json.loads(error.read().decode("utf-8")),
        )
    require(
        result.headers.get("X-Request-ID") == headers["X-Request-ID"],
        "Multipart revision request identity was not echoed",
    )
    return HttpResult(
        result.status,
        result.headers,
        result.body,
        request_id=headers["X-Request-ID"],
        trace_id=headers["X-Trace-ID"],
    )


def binary_content_request(
    opener,
    base_url: str,
    path: str,
    *,
    csrf_token: str,
    idempotency_key: str,
    expected_document_version: int,
    expected_file_version: int,
) -> BinaryHttpResult:
    body = json.dumps(
        {
            "expectedDocumentVersion": expected_document_version,
            "expectedFileVersion": expected_file_version,
            "disposition": "inline",
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    headers = command_headers(csrf_token, idempotency_key)
    headers["Content-Type"] = "application/json"
    http_request = urllib.request.Request(
        f"{base_url}{path}",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with opener.open(http_request, timeout=30) as response:
            result = BinaryHttpResult(
                response.status,
                response.headers,
                response.read(),
                None,
            )
    except urllib.error.HTTPError as error:
        raw = error.read()
        result = BinaryHttpResult(
            error.code,
            error.headers,
            raw,
            json.loads(raw.decode("utf-8")),
        )
    require(
        result.headers.get("X-Request-ID") == headers["X-Request-ID"],
        "Binary content request identity was not echoed",
    )
    return result


def create_internal_fixture_user(
    administrator,
    base_url: str,
    user_id: str,
    password: str,
    csrf_token: str,
) -> None:
    created = create_resource(
        administrator,
        base_url,
        "User",
        {
            "email": user_id,
            "enabled": 1,
            "first_name": "NPI Document Reviewer",
            "language": "en",
            "last_name": "Runtime Fixture",
            "new_password": password,
            "roles": [
                {"role": "Desk User"},
                {"role": "NPI API User"},
            ],
            "send_welcome_email": 0,
            "user_type": "System User",
        },
        csrf_token,
    )
    require(
        created.status in {200, 201},
        f"Internal Document fixture user creation returned HTTP {created.status}",
    )
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
        and "NPI API User" in roles
        and "System Manager" not in roles,
        "Internal Document fixture transport identity drifted",
    )


def ensure_gate_template(
    administrator,
    base_url: str,
    csrf_token: str,
) -> str:
    root = create_resource(
        administrator,
        base_url,
        "NPI Gate Template",
        {
            "global_id": GATE_TEMPLATE_ID,
            "template_code": GATE_TEMPLATE_CODE,
            "title": "Synthetic P5-03 release baseline Gate",
            "enabled": 1,
        },
        csrf_token,
    )
    require_http_status(root, {200, 201}, "Gate Template creation")
    version = create_resource(
        administrator,
        base_url,
        "NPI Gate Template Version",
        {
            "gate_template": GATE_TEMPLATE_ID,
            "gate_template_version": GATE_TEMPLATE_VERSION,
            "title": "Synthetic P5-03 release baseline Gate",
            "publication_state": "published",
            "applicable_project_types": ["new_tool"],
            "requirements": [
                {
                    "requirement_key": GATE_REQUIREMENT_KEY,
                    "title": "Exact released design baseline is attached",
                    "classification": "required",
                    "priority": "P0",
                    "allowed_evidence_kinds": ["release_baseline"],
                }
            ],
        },
        csrf_token,
    )
    require_http_status(version, {200, 201}, "Gate Template publication")
    data = version.body.get("data", {})
    snapshot_hash = data.get("snapshot_hash")
    require(
        data.get("name") == GATE_TEMPLATE_VERSION_KEY
        and data.get("publication_state") == "published"
        and isinstance(snapshot_hash, str)
        and re.fullmatch(r"[a-f0-9]{64}", snapshot_hash) is not None,
        "Published Gate Template identity or hash drifted",
    )
    return snapshot_hash


def ensure_project_template(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    gate_template_hash: str,
) -> str:
    root = create_resource(
        administrator,
        base_url,
        "NPI Project Template",
        {
            "global_id": PROJECT_TEMPLATE_ID,
            "template_code": PROJECT_TEMPLATE_CODE,
            "title": "Synthetic P5-01 runtime project template",
            "enabled": 1,
        },
        csrf_token,
    )
    require(
        root.status in {200, 201},
        f"Project template creation returned HTTP {root.status}",
    )
    version = create_resource(
        administrator,
        base_url,
        "NPI Project Template Version",
        {
            "project_template": PROJECT_TEMPLATE_ID,
            "template_version": PROJECT_TEMPLATE_VERSION,
            "title": "Synthetic P5-01 runtime project template version",
            "publication_state": "published",
            "applicable_project_types": ["new_tool"],
            "reference_rules": [
                {
                    "reference_type": "customer",
                    "required": 1,
                    "allow_multiple": 0,
                }
            ],
            "gates": [
                {
                    "gate_key": GATE_KEY,
                    "title": "Synthetic document intake",
                    "sequence": 1,
                    "gate_template_global_id": GATE_TEMPLATE_ID,
                    "gate_template_version": GATE_TEMPLATE_VERSION,
                    "gate_template_snapshot_hash": gate_template_hash,
                }
            ],
        },
        csrf_token,
    )
    require(
        version.status in {200, 201},
        f"Project template version creation returned HTTP {version.status}",
    )
    snapshot_hash = version.body.get("data", {}).get("snapshot_hash")
    require(
        isinstance(snapshot_hash, str)
        and re.fullmatch(r"[a-f0-9]{64}", snapshot_hash) is not None,
        "Project template snapshot hash is unavailable",
    )
    return snapshot_hash


def create_project(
    administrator,
    base_url: str,
    csrf_token: str,
) -> tuple[str, int]:
    payload = {
        "tenantId": TENANT_ID,
        "businessCode": BUSINESS_CODE,
        "title": "Synthetic P5-01 controlled document project",
        "projectType": "new_tool",
        "ownerUserId": OWNER_USER,
        "targetSop": "2027-01-31",
        "templateGlobalId": PROJECT_TEMPLATE_ID,
        "templateVersion": PROJECT_TEMPLATE_VERSION,
        "expectedVersion": 1,
        "references": [
            {
                "type": "customer",
                "sourceSystem": "ERPNEXT",
                "sourceObjectId": f"SYNTHETIC-{FIXTURE_RUN_ID[:16]}",
            }
        ],
    }
    created = post_project(
        administrator,
        base_url,
        payload,
        csrf_token=csrf_token,
        idempotency_key=PROJECT_CREATE_KEY,
        request_id=fixture_request_id(PROJECT_CREATE_KEY),
    )
    require(
        created.status == 201,
        f"Synthetic Project creation returned HTTP {created.status}",
    )
    project = created.body.get("project", {})
    project_id = project.get("globalId")
    version = project.get("version")
    require(
        isinstance(project_id, str)
        and isinstance(version, int)
        and version == 1,
        "Synthetic Project identity or version drifted",
    )
    return project_id, version


def configured_gate_id(project_id: str) -> str:
    return str(uuid5(UUID(project_id), f"gate-shell:1:{GATE_KEY}"))


def ensure_project_work_policy(
    administrator,
    base_url: str,
    csrf_token: str,
) -> dict[str, object]:
    created = create_resource(
        administrator,
        base_url,
        "NPI Project Work Policy Version",
        {
            "policy_global_id": PROJECT_WORK_POLICY_ID,
            "policy_key": PROJECT_WORK_POLICY_KEY,
            "policy_version": PROJECT_WORK_POLICY_VERSION,
            "title": "Synthetic P5-03 baseline membership policy",
            "publication_state": "published",
            "role_keys": [BASELINE_ROLE_KEY],
            "wbs_states": {
                "initialStateKey": "not_started",
                "states": [
                    {
                        "key": "not_started",
                        "labelSource": "Not started",
                        "terminal": False,
                    }
                ],
            },
            "work_item_lifecycles": [
                {
                    "kind": kind,
                    "initialStateKey": state,
                    "states": [
                        {
                            "key": state,
                            "labelSource": label,
                            "terminal": False,
                        }
                    ],
                }
                for kind, state, label in (
                    ("risk", "risk_open", "Identified"),
                    ("issue", "issue_open", "Open"),
                    ("action", "action_open", "Open"),
                    ("decision_request", "decision_open", "Requested"),
                )
            ],
        },
        csrf_token,
    )
    require_http_status(created, {200, 201}, "Project work policy publication")
    data = created.body.get("data", {})
    snapshot_hash = data.get("snapshot_hash")
    require(
        data.get("name") == PROJECT_WORK_POLICY_VERSION_KEY
        and isinstance(snapshot_hash, str)
        and re.fullmatch(r"[a-f0-9]{64}", snapshot_hash) is not None,
        "Published Project work policy identity or hash drifted",
    )
    return {
        "globalId": PROJECT_WORK_POLICY_ID,
        "version": PROJECT_WORK_POLICY_VERSION,
        "snapshotHash": snapshot_hash,
    }


def configure_baseline_project_member(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    project_id: str,
    work_policy_ref: dict[str, object],
) -> None:
    configured = npi_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}:configure-team",
        method="POST",
        payload={
            "expectedProjectVersion": 1,
            "workPolicyRef": work_policy_ref,
            "members": [
                {
                    "globalId": BASELINE_MEMBER_ID,
                    "userId": BASELINE_USER,
                    "effectiveFrom": "2026-07-01",
                }
            ],
            "roleAssignments": [
                {
                    "globalId": BASELINE_ROLE_ASSIGNMENT_ID,
                    "memberId": BASELINE_MEMBER_ID,
                    "roleKey": BASELINE_ROLE_KEY,
                    "effectiveFrom": "2026-07-01",
                }
            ],
            "substitutions": [],
            "raciAssignments": [
                {
                    "globalId": BASELINE_RACI_ID,
                    "contextType": "project",
                    "contextId": project_id,
                    "responsibilityKey": "gate_evidence",
                    "roleAssignmentId": BASELINE_ROLE_ASSIGNMENT_ID,
                    "raci": "responsible",
                }
            ],
        },
        csrf_token=csrf_token,
        idempotency_key=PROJECT_TEAM_KEY,
    )
    require(
        configured.status == 200
        and configured.headers.get("Idempotency-Replayed") == "false"
        and configured.body.get("projectVersion") == 2,
        "Synthetic baseline Project membership drifted",
    )


def ensure_document_policy(
    administrator,
    base_url: str,
    csrf_token: str,
) -> str:
    root = create_resource(
        administrator,
        base_url,
        "NPI Document Policy",
        {
            "global_id": DOCUMENT_POLICY_ID,
            "tenant_id": TENANT_ID,
            "policy_key": POLICY_KEY,
            "title": "Synthetic P5-01 runtime document policy",
            "enabled": 1,
        },
        csrf_token,
    )
    require_http_status(
        root,
        {200, 201},
        "Document policy creation",
    )
    draft = create_resource(
        administrator,
        base_url,
        "NPI Document Policy Version",
        {
            "document_policy": DOCUMENT_POLICY_ID,
            "policy_version": DOCUMENT_POLICY_VERSION,
            "title": "Synthetic P5-01 runtime document policy version",
            "publication_state": "draft",
            "document_types": [
                {
                    "key": "drawing",
                    "prefix": "DRW",
                    "titleSource": "Drawing",
                }
            ],
            "confidentiality_keys": ["internal"],
            "allowed_mime_types": ["application/pdf"],
            "preview_mime_types": ["application/pdf"],
            "maximum_file_bytes": 1_048_576,
            "lock_lease_minutes": 30,
        },
        csrf_token,
    )
    require_http_status(
        draft,
        {200, 201},
        "Document policy draft creation",
    )
    published = update_resource(
        administrator,
        base_url,
        "NPI Document Policy Version",
        DOCUMENT_POLICY_VERSION_KEY,
        {"publication_state": "published"},
        csrf_token,
    )
    require_http_status(
        published,
        {200},
        "Document policy publication",
    )
    data = published.body.get("data", {})
    snapshot_hash = data.get("snapshot_hash")
    require(
        data.get("publication_state") == "published"
        and isinstance(snapshot_hash, str)
        and re.fullmatch(r"[a-f0-9]{64}", snapshot_hash) is not None,
        "Published document policy truth drifted",
    )
    return snapshot_hash


def ensure_document_release_policy(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    project_id: str,
) -> str:
    root = create_resource(
        administrator,
        base_url,
        "NPI Document Release Policy",
        {
            "global_id": DOCUMENT_RELEASE_POLICY_ID,
            "tenant_id": TENANT_ID,
            "project_global_id": project_id,
            "policy_key": RELEASE_POLICY_KEY,
            "title": "Synthetic P5-02 runtime document release policy",
            "enabled": 1,
        },
        csrf_token,
    )
    require_http_status(
        root,
        {200, 201},
        "Document release policy creation",
    )
    draft = create_resource(
        administrator,
        base_url,
        "NPI Document Release Policy Version",
        {
            "document_release_policy": DOCUMENT_RELEASE_POLICY_ID,
            "policy_version": DOCUMENT_RELEASE_POLICY_VERSION,
            "title": "Synthetic P5-02 runtime release policy version",
            "publication_state": "draft",
            "submitter_user_ids": ["Administrator"],
            "reviewer_assignments": [
                {
                    "slotKey": "engineering_reviewer",
                    "userId": OWNER_USER,
                }
            ],
            "required_approval_count": 1,
            "release_authority_user_ids": ["Administrator"],
            "supersede_authority_user_ids": ["Administrator"],
            "obsolete_authority_user_ids": ["Administrator"],
            "confirmation_method": "authenticated_session_confirmation",
            "required_scan_state": "clean",
            "require_live_private_identity": 1,
            "require_sha256_match": 1,
            "supersede_requires_released_successor": 1,
            "supersede_requires_later_revision": 1,
            "supersede_requires_successor_effective_date": 1,
        },
        csrf_token,
    )
    require_http_status(
        draft,
        {200, 201},
        "Document release policy draft creation",
    )
    published = update_resource(
        administrator,
        base_url,
        "NPI Document Release Policy Version",
        DOCUMENT_RELEASE_POLICY_VERSION_KEY,
        {"publication_state": "published"},
        csrf_token,
    )
    require_http_status(
        published,
        {200},
        "Document release policy publication",
    )
    data = published.body.get("data", {})
    snapshot_hash = data.get("snapshot_hash")
    require(
        data.get("publication_state") == "published"
        and data.get("project_global_id") == project_id
        and isinstance(snapshot_hash, str)
        and re.fullmatch(r"[a-f0-9]{64}", snapshot_hash) is not None,
        "Published document release policy truth drifted",
    )
    return snapshot_hash


def ensure_document_baseline_policy(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    project_id: str,
) -> str:
    root = create_resource(
        administrator,
        base_url,
        "NPI Document Baseline Policy",
        {
            "global_id": DOCUMENT_BASELINE_POLICY_ID,
            "tenant_id": TENANT_ID,
            "project_global_id": project_id,
            "policy_key": BASELINE_POLICY_KEY,
            "title": "Synthetic P5-03 document baseline policy",
            "enabled": 1,
        },
        csrf_token,
    )
    require_http_status(root, {200, 201}, "Document baseline policy creation")
    draft = create_resource(
        administrator,
        base_url,
        "NPI Document Baseline Policy Version",
        {
            "document_baseline_policy": DOCUMENT_BASELINE_POLICY_ID,
            "policy_version": DOCUMENT_BASELINE_POLICY_VERSION,
            "title": "Synthetic P5-03 document baseline policy version",
            "publication_state": "draft",
            "baseline_authority_user_ids": [BASELINE_USER],
        },
        csrf_token,
    )
    require_http_status(
        draft,
        {200, 201},
        "Document baseline policy draft creation",
    )
    published = update_resource(
        administrator,
        base_url,
        "NPI Document Baseline Policy Version",
        DOCUMENT_BASELINE_POLICY_VERSION_KEY,
        {"publication_state": "published"},
        csrf_token,
    )
    require_http_status(
        published,
        {200},
        "Document baseline policy publication",
    )
    data = published.body.get("data", {})
    snapshot_hash = data.get("snapshot_hash")
    require(
        data.get("publication_state") == "published"
        and data.get("project_global_id") == project_id
        and isinstance(snapshot_hash, str)
        and re.fullmatch(r"[a-f0-9]{64}", snapshot_hash) is not None,
        "Published document baseline policy truth drifted",
    )
    return snapshot_hash


def ensure_gate_review_policy(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    gate_template_hash: str,
) -> str:
    root = create_resource(
        administrator,
        base_url,
        "NPI Gate Review Policy",
        {
            "global_id": GATE_REVIEW_POLICY_ID,
            "policy_code": GATE_REVIEW_POLICY_CODE,
            "title": "Synthetic P5-03 baseline review policy",
            "enabled": 1,
        },
        csrf_token,
    )
    require_http_status(root, {200, 201}, "Gate Review policy creation")
    version = create_resource(
        administrator,
        base_url,
        "NPI Gate Review Policy Version",
        {
            "gate_review_policy": GATE_REVIEW_POLICY_ID,
            "policy_version": GATE_REVIEW_POLICY_VERSION,
            "title": "Synthetic P5-03 baseline review policy version",
            "publication_state": "published",
            "gate_template_global_id": GATE_TEMPLATE_ID,
            "gate_template_version": GATE_TEMPLATE_VERSION,
            "gate_template_snapshot_hash": gate_template_hash,
            "review_steps": [
                {
                    "key": GATE_REVIEW_STEP_KEY,
                    "sequence": 1,
                    "authoritySlot": GATE_REVIEW_SLOT,
                    "activation": "always",
                    "activationPriority": None,
                }
            ],
            "decision_authority_slot": GATE_DECISION_SLOT,
            "reopen_authority_slot": GATE_REOPEN_SLOT,
            "exception_rules": [],
            "dependency_evaluators": ["gate_input_snapshot"],
        },
        csrf_token,
    )
    require_http_status(version, {200, 201}, "Gate Review policy publication")
    data = version.body.get("data", {})
    snapshot_hash = data.get("snapshot_hash")
    require(
        data.get("name") == GATE_REVIEW_POLICY_VERSION_KEY
        and data.get("publication_state") == "published"
        and isinstance(snapshot_hash, str)
        and re.fullmatch(r"[a-f0-9]{64}", snapshot_hash) is not None,
        "Published Gate Review policy identity or hash drifted",
    )
    return snapshot_hash


def verify_fresh_namespace(administrator, base_url: str) -> None:
    for user in (OWNER_USER, BASELINE_USER, UNRELATED_USER):
        result = request(administrator, base_url, user_resource_path(user))
        require(
            result.status == 404,
            f"Fresh runtime fixture already contains User {user}",
        )
    for doctype, name in (
        ("NPI Project Template", PROJECT_TEMPLATE_ID),
        ("NPI Gate Template", GATE_TEMPLATE_ID),
        ("NPI Document Policy", DOCUMENT_POLICY_ID),
        ("NPI Document Release Policy", DOCUMENT_RELEASE_POLICY_ID),
        ("NPI Document Baseline Policy", DOCUMENT_BASELINE_POLICY_ID),
        ("NPI Gate Review Policy", GATE_REVIEW_POLICY_ID),
        (
            "NPI Project Work Policy Version",
            PROJECT_WORK_POLICY_VERSION_KEY,
        ),
    ):
        result = get_resource(administrator, base_url, doctype, name)
        require(
            result.status == 404,
            f"Fresh runtime fixture already contains {doctype} {name}",
        )
    projects = list_resources(
        administrator,
        base_url,
        "NPI Engineering Project",
        filters=[["business_code", "=", BUSINESS_CODE]],
        fields=["global_id"],
    )
    require(projects == [], "Fresh runtime Project namespace is not empty")


def validate_document_workspace(
    result: HttpResult,
    *,
    project_id: str,
    expected_document_id: str | None,
) -> dict[str, Any]:
    if result.status not in {200, 201}:
        diagnostic = _sanitized_bff_log_diagnostic(result.trace_id)
        detail = ""
        if diagnostic is not None:
            diagnostic_type, diagnostic_code, diagnostic_trace_id = diagnostic
            detail = (
                f" [diagnostic_code={diagnostic_code}; "
                f"exc_type={diagnostic_type}; "
                f"trace_id={diagnostic_trace_id}]"
            )
        require(
            False,
            f"Document workspace returned HTTP {result.status}{detail}",
        )
    require(
        result.body.get("project", {}).get("globalId") == project_id,
        "Document workspace Project identity drifted",
    )
    permissions = result.body.get("permissions", {})
    require(
        permissions.get("view") is True
        and permissions.get("create") is True
        and permissions.get("release") is False,
        "Document permission truth drifted",
    )
    if expected_document_id is not None:
        document = result.body.get("document", {})
        require(
            document.get("globalId") == expected_document_id,
            "Controlled Document identity drifted",
        )
    require(
        "fileUrl" not in json.dumps(result.body)
        and "/private/files/" not in json.dumps(result.body),
        "Document workspace exposed a raw private file identity",
    )
    return result.body


def create_controlled_document(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    project_id: str,
    project_version: int,
    policy_snapshot_hash: str,
) -> dict[str, Any]:
    result = npi_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}/documents",
        method="POST",
        payload={
            "policyGlobalId": DOCUMENT_POLICY_ID,
            "policyVersion": DOCUMENT_POLICY_VERSION,
            "policySnapshotHash": policy_snapshot_hash,
            "documentTypeKey": "drawing",
            "title": "Synthetic P5-01 runtime drawing",
            "confidentialityKey": "internal",
            "objectLinks": [
                {
                    "kind": "project",
                    "targetIdentity": project_id,
                    "targetVersion": project_version,
                }
            ],
        },
        csrf_token=csrf_token,
        idempotency_key=DOCUMENT_CREATE_KEY,
    )
    body = validate_document_workspace(
        result,
        project_id=project_id,
        expected_document_id=result.body.get("document", {}).get("globalId"),
    )
    require(
        result.status == 201
        and result.headers.get("Idempotency-Replayed") == "false",
        "Controlled Document create truth drifted",
    )
    document = body.get("document", {})
    require(
        document.get("optimisticVersion") == 1
        and document.get("currentRevision") is None
        and document.get("currentLock") is None,
        "New Controlled Document contains fabricated revision or lock truth",
    )
    return body


def replay_controlled_document(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    project_id: str,
    project_version: int,
    policy_snapshot_hash: str,
) -> dict[str, Any]:
    result = npi_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}/documents",
        method="POST",
        payload={
            "policyGlobalId": DOCUMENT_POLICY_ID,
            "policyVersion": DOCUMENT_POLICY_VERSION,
            "policySnapshotHash": policy_snapshot_hash,
            "documentTypeKey": "drawing",
            "title": "Synthetic P5-01 runtime drawing",
            "confidentialityKey": "internal",
            "objectLinks": [
                {
                    "kind": "project",
                    "targetIdentity": project_id,
                    "targetVersion": project_version,
                }
            ],
        },
        csrf_token=csrf_token,
        idempotency_key=DOCUMENT_CREATE_KEY,
    )
    require(
        result.status == 201
        and result.headers.get("Idempotency-Replayed") == "true",
        "Controlled Document cross-process replay was not declared",
    )
    return result.body


def _validated_runtime_site() -> None:
    import frappe

    require(
        frappe.local.site == SITE_NAME
        and frappe.conf.get("db_name") == DATABASE_NAME
        and frappe.conf.get("npi_tenant_id") == TENANT_ID
        and frappe.conf.get("npi_runtime_disposable_marker") == RUNTIME_MARKER,
        "Controlled local runtime Site identity drifted",
    )
    database_row = frappe.db.sql(
        "SELECT DATABASE(), CURRENT_USER(), @@port",
        as_list=True,
    )
    require(
        len(database_row) == 1
        and database_row[0][0] == DATABASE_NAME
        and str(database_row[0][1]).split("@", 1)[0] == DATABASE_USER
        and int(database_row[0][2]) == DATABASE_PORT,
        "Controlled local runtime database identity drifted",
    )


def verify_document_runtime_schema(fixture_run_id: str) -> dict[str, object]:
    import frappe

    _validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "Document runtime schema fixture namespace drifted",
    )
    required_fields = {
        "NPI Controlled Document": {
            "global_id",
            "project_global_id",
            "document_number_key",
            "current_revision_global_id",
            "current_lock_global_id",
            "optimistic_version",
        },
        "NPI Document Revision": {
            "global_id",
            "document_global_id",
            "revision_key",
            "snapshot_hash",
        },
        "NPI Document Revision File": {
            "document_revision_global_id",
            "file_revision_global_id",
            "sha256",
            "scan_state",
        },
        "NPI Document Command Idempotency": {
            "actor_key_hash",
            "payload_hash",
            "response_snapshot",
            "response_sealed",
        },
        "NPI Document Release Policy": {
            "global_id",
            "project_global_id",
            "policy_key_hash",
            "optimistic_version",
        },
        "NPI Document Release Policy Version": {
            "global_id",
            "policy_global_id",
            "reviewer_assignments",
            "release_authority_user_ids",
            "policy_snapshot",
            "snapshot_hash",
        },
        "NPI Document Revision Lifecycle": {
            "revision_global_id",
            "current_state",
            "lifecycle_version",
            "last_event_global_id",
        },
        "NPI Document Review Cycle": {
            "cycle_key",
            "revision_global_id",
            "review_evidence",
            "snapshot_hash",
        },
        "NPI Document Confirmation": {
            "confirmation_key",
            "revision_global_id",
            "confirmation_evidence",
            "evidence_hash",
        },
        "NPI Document Lifecycle Event": {
            "revision_global_id",
            "from_version",
            "to_version",
            "event_snapshot",
            "event_hash",
        },
        "NPI Document Baseline Policy": {
            "global_id",
            "project_global_id",
            "policy_key_hash",
            "optimistic_version",
        },
        "NPI Document Baseline Policy Version": {
            "policy_global_id",
            "baseline_authority_user_ids",
            "policy_snapshot",
            "snapshot_hash",
        },
        "NPI Document Baseline": {
            "global_id",
            "policy_global_id",
            "member_count",
            "baseline_snapshot",
            "snapshot_hash",
        },
        "NPI Document Baseline Member": {
            "baseline_global_id",
            "revision_global_id",
            "release_snapshot_hash",
            "member_snapshot",
            "member_hash",
        },
        "NPI Baseline Command Idempotency": {
            "actor_user_id",
            "idempotency_key_hash",
            "payload_hash",
            "response_payload",
            "sealed",
        },
        "NPI Baseline Gate Dependency": {
            "baseline_global_id",
            "input_revision_global_id",
            "evidence_reference_global_id",
            "dependency_snapshot",
            "snapshot_hash",
        },
        "NPI Baseline Impact Event": {
            "baseline_global_id",
            "old_revision_global_id",
            "new_revision_global_id",
            "event_snapshot",
            "event_hash",
        },
    }
    for doctype in DOCUMENT_DOCTYPES:
        require(
            frappe.db.table_exists(doctype),
            f"Document runtime table is unavailable: {doctype}",
        )
        meta = frappe.get_meta(doctype, cached=False)
        fieldnames = {field.fieldname for field in meta.fields}
        require(
            required_fields.get(doctype, set()).issubset(fieldnames),
            f"Document runtime metadata drifted: {doctype}",
        )
    return {
        "doctypeCount": len(DOCUMENT_DOCTYPES),
        "fixtureRunId": fixture_run_id,
        "metadataSynchronized": True,
    }


def observe_document_file_scan(
    fixture_run_id: str,
    *,
    file_revision_id: str,
    document_id: str,
    project_id: str,
) -> dict[str, object]:
    import frappe
    from frappe.utils import now_datetime

    from npi_core.controlled_evidence_validation import FILE_SCAN_RESULT_FLAG

    _validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "Document scanner fixture namespace drifted",
    )
    project = frappe.get_doc("NPI Engineering Project", project_id)
    require(
        str(project.business_code) == BUSINESS_CODE,
        "Document scanner fixture Project identity drifted",
    )
    association = frappe.db.get_value(
        "NPI Document Revision File",
        {
            "project_global_id": project_id,
            "document_global_id": document_id,
            "file_revision_global_id": file_revision_id,
        },
        ["name", "sha256"],
        as_dict=True,
    )
    require(association is not None, "Document scanner association is unavailable")
    revision = frappe.get_doc("NPI File Revision", file_revision_id)
    before_hash = str(revision.sha256)
    require(
        before_hash == str(association.get("sha256")),
        "Document scanner fixture hash identity drifted",
    )
    previous = getattr(frappe.flags, FILE_SCAN_RESULT_FLAG, None)
    setattr(frappe.flags, FILE_SCAN_RESULT_FLAG, True)
    try:
        revision.scan_state = "clean"
        revision.scan_observed_at = now_datetime()
        revision.save()
    finally:
        if previous is None:
            delattr(frappe.flags, FILE_SCAN_RESULT_FLAG)
        else:
            setattr(frappe.flags, FILE_SCAN_RESULT_FLAG, previous)
    frappe.db.commit()
    require(
        str(revision.sha256) == before_hash,
        "Scanner observation changed immutable file content identity",
    )
    return {
        "fileRevisionId": file_revision_id,
        "optimisticVersion": int(revision.optimistic_version),
        "scanState": str(revision.scan_state),
        "sha256": before_hash,
    }


def verify_released_file_delete_guard(
    fixture_run_id: str,
    *,
    file_revision_id: str,
    document_id: str,
    project_id: str,
) -> dict[str, object]:
    import frappe

    _validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID,
        "Released file guard fixture namespace drifted",
    )
    project = frappe.get_doc("NPI Engineering Project", project_id)
    require(
        str(project.business_code) == BUSINESS_CODE,
        "Released file guard Project identity drifted",
    )
    revision = frappe.get_doc("NPI File Revision", file_revision_id)
    association = frappe.db.get_value(
        "NPI Document Revision File",
        {
            "project_global_id": project_id,
            "document_global_id": document_id,
            "file_revision_global_id": file_revision_id,
        },
        ["file_document_global_id", "sha256"],
        as_dict=True,
    )
    require(
        association is not None
        and str(revision.project_global_id) == project_id
        and str(revision.document_global_id)
        == str(association.get("file_document_global_id"))
        and str(revision.sha256) == str(association.get("sha256"))
        and int(revision.released or 0) == 1,
        "Released file guard identity drifted",
    )
    file_id = str(revision.frappe_file_id)
    retained = frappe.get_doc("File", file_id)
    try:
        retained.delete()
    except frappe.PermissionError:
        frappe.db.rollback()
    else:
        frappe.db.rollback()
        require(False, "Released document File deletion was not rejected")
    require(
        frappe.db.exists("File", file_id)
        and frappe.db.exists("NPI File Revision", file_revision_id),
        "Released document File guard did not retain exact evidence",
    )
    return {
        "deleteRejected": True,
        "documentId": document_id,
        "fileRevisionId": file_revision_id,
        "projectId": project_id,
    }


def set_document_file_content(
    fixture_run_id: str,
    *,
    file_revision_id: str,
    document_id: str,
    project_id: str,
    mode: str,
) -> dict[str, object]:
    import frappe

    _validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID and mode in {"tamper", "restore"},
        "Document integrity fixture arguments drifted",
    )
    project = frappe.get_doc("NPI Engineering Project", project_id)
    revision = frappe.get_doc("NPI File Revision", file_revision_id)
    association = frappe.db.get_value(
        "NPI Document Revision File",
        {
            "project_global_id": project_id,
            "document_global_id": document_id,
            "file_revision_global_id": file_revision_id,
        },
        ["file_document_global_id", "sha256"],
        as_dict=True,
    )
    require(
        str(project.business_code) == BUSINESS_CODE
        and association is not None
        and str(revision.project_global_id) == project_id
        and str(revision.document_global_id)
        == str(association.get("file_document_global_id"))
        and str(revision.sha256) == str(association.get("sha256"))
        and int(revision.released or 0) == 0,
        "Document integrity fixture identity drifted",
    )
    file_document = frappe.get_doc("File", str(revision.frappe_file_id))
    file_url = str(file_document.file_url)
    require(
        file_url.startswith("/private/files/")
        and int(file_document.is_private or 0) == 1
        and int(file_document.is_remote_file or 0) == 0,
        "Document integrity fixture private-file boundary drifted",
    )
    private_root = Path(frappe.get_site_path("private", "files")).resolve()
    file_path = Path(
        frappe.get_site_path(*file_url.lstrip("/").split("/"))
    ).resolve()
    require(
        file_path.is_relative_to(private_root)
        and file_path.is_file()
        and not file_path.is_symlink(),
        "Document integrity fixture path drifted",
    )
    tampered = PDF_CONTENT + b"\n%controlled-integrity-mismatch\n"
    expected_before = PDF_CONTENT if mode == "tamper" else tampered
    expected_after = tampered if mode == "tamper" else PDF_CONTENT
    require(
        file_path.read_bytes() == expected_before,
        "Document integrity fixture precondition drifted",
    )
    file_path.write_bytes(expected_after)
    require(
        file_path.read_bytes() == expected_after,
        "Document integrity fixture write verification failed",
    )
    return {
        "contentMode": mode,
        "documentId": document_id,
        "fileRevisionId": file_revision_id,
        "projectId": project_id,
    }


def run_bench_fixture(
    method: str,
    kwargs: dict[str, object],
) -> dict[str, Any]:
    require(
        BENCH_PATH.is_dir()
        and not BENCH_PATH.is_symlink()
        and BENCH_PATH.resolve() == BENCH_PATH,
        "Document runtime verifier requires the fixed physical repository Bench",
    )
    environment = os.environ.copy()
    current_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        str(ROOT)
        if not current_pythonpath
        else f"{ROOT}{os.pathsep}{current_pythonpath}"
    )
    completed = subprocess.run(
        [
            str(BENCH_PATH / "env" / "bin" / "python"),
            str(ROOT / "scripts" / "verify_document_runtime.py"),
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
        (
            f"Controlled Document Bench fixture {method} failed: "
            f"{completed.stderr[-2000:]}"
        ),
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    require(bool(lines), f"Controlled Document Bench fixture {method} was silent")
    result = json.loads(lines[-1])
    require(isinstance(result, dict), "Document Bench fixture result is invalid")
    return result


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    fixtures = {
        "observe_document_file_scan": observe_document_file_scan,
        "set_document_file_content": set_document_file_content,
        "verify_released_file_delete_guard": verify_released_file_delete_guard,
        "verify_document_runtime_schema": verify_document_runtime_schema,
    }
    require(method in fixtures, "Controlled Document Bench fixture is unavailable")
    require(
        BENCH_PATH.is_dir()
        and not BENCH_PATH.is_symlink()
        and BENCH_PATH.resolve() == BENCH_PATH,
        "Controlled Document Bench fixture requires the fixed physical Bench",
    )
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


def fixture_project(administrator, base_url: str) -> tuple[str, int]:
    rows = list_resources(
        administrator,
        base_url,
        "NPI Engineering Project",
        filters=[["business_code", "=", BUSINESS_CODE]],
        fields=["global_id", "optimistic_version"],
    )
    require(len(rows) == 1, "Retained Document runtime Project is unavailable")
    return str(rows[0]["global_id"]), int(rows[0]["optimistic_version"])


def fixture_policy_hash(administrator, base_url: str) -> str:
    policy = get_resource(
        administrator,
        base_url,
        "NPI Document Policy Version",
        DOCUMENT_POLICY_VERSION_KEY,
    )
    require(policy.status == 200, "Retained Document runtime policy is unavailable")
    snapshot_hash = policy.body.get("data", {}).get("snapshot_hash")
    require(
        isinstance(snapshot_hash, str)
        and re.fullmatch(r"[a-f0-9]{64}", snapshot_hash) is not None,
        "Retained Document runtime policy hash drifted",
    )
    return snapshot_hash


def fixture_release_policy_hash(administrator, base_url: str) -> str:
    policy = get_resource(
        administrator,
        base_url,
        "NPI Document Release Policy Version",
        DOCUMENT_RELEASE_POLICY_VERSION_KEY,
    )
    require(
        policy.status == 200,
        "Retained Document release policy is unavailable",
    )
    snapshot_hash = policy.body.get("data", {}).get("snapshot_hash")
    require(
        isinstance(snapshot_hash, str)
        and re.fullmatch(r"[a-f0-9]{64}", snapshot_hash) is not None,
        "Retained Document release policy hash drifted",
    )
    return snapshot_hash


def release_command(
    opener,
    base_url: str,
    csrf_token: str | None,
    *,
    project_id: str,
    document_id: str,
    revision_id: str,
    suffix: str,
    payload: dict[str, object],
    idempotency_key: str,
) -> HttpResult:
    return npi_request(
        opener,
        base_url,
        (
            f"/api/npi/v1/projects/{project_id}/documents/{document_id}/"
            f"revisions/{revision_id}:{suffix}"
        ),
        method="POST",
        payload=payload,
        csrf_token=csrf_token,
        idempotency_key=idempotency_key,
    )


def validate_release_transition(
    result: HttpResult,
    *,
    expected_state: str,
    expected_version: int,
    expected_event: str,
    expected_confirmation: str | None,
    replayed: bool = False,
) -> dict[str, Any]:
    require_http_status(result, {201}, f"Document {expected_event} command")
    body = result.body
    confirmation = body.get("confirmation")
    require(
        body.get("state") == expected_state
        and body.get("lifecycleVersion") == expected_version
        and body.get("event", {}).get("type") == expected_event
        and (
            (expected_confirmation is None and confirmation is None)
            or (
                isinstance(confirmation, dict)
                and confirmation.get("type") == expected_confirmation
            )
        )
        and result.headers.get("Idempotency-Replayed")
        == ("true" if replayed else "false"),
        f"Document {expected_event} transition truth drifted",
    )
    return body


def route_disable_probe(
    administrator,
    base_url: str,
    *,
    expected_mode: str,
) -> None:
    project_id, _project_version = fixture_project(administrator, base_url)
    result = npi_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}/documents",
        query_key=f"route-{expected_mode}",
    )
    if expected_mode == "disabled":
        validate_problem(result, 503, "DOCUMENT_ROUTES_DISABLED")
    else:
        require(
            result.status == 200,
            f"Recovered Document route returned HTTP {result.status}",
        )


def release_route_disable_probe(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    expected_mode: str,
) -> None:
    project_id, _project_version = fixture_project(administrator, base_url)
    page = npi_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}/documents",
        query_key=f"release-route-list-{expected_mode}",
    )
    require(
        page.status == 200 and len(page.body.get("items", [])) == 1,
        "P5-02 route switch changed the retained P5-01 list route",
    )
    document_id = str(page.body["items"][0]["globalId"])
    detail = npi_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}/documents/{document_id}",
        query_key=f"release-route-detail-{expected_mode}",
    )
    release_workspace = detail.body.get("releaseWorkspace", {})
    require(
        detail.status == 200
        and release_workspace.get("available") is True
        and release_workspace.get("commandsEnabled")
        is (expected_mode == "recovered")
        and release_workspace.get("reasonCode")
        == ("available" if expected_mode == "recovered" else "routes_disabled"),
        "P5-02 release route switch workspace truth drifted",
    )
    if expected_mode == "recovered":
        return
    revision_history = release_workspace.get("revisions", [])[0]
    revision_id = str(revision_history["revisionId"])
    disabled = release_command(
        administrator,
        base_url,
        csrf_token,
        project_id=project_id,
        document_id=document_id,
        revision_id=revision_id,
        suffix="obsolete",
        payload={
            "expectedDocumentVersion": int(
                detail.body["document"]["optimisticVersion"]
            ),
            "expectedLifecycleVersion": int(
                revision_history["lifecycle"]["version"]
            ),
            "reason": "Controlled route-disable probe.",
            "confirmationIntent": "obsolete_revision",
            "confirmed": True,
        },
        idempotency_key=f"{FIXTURE_PREFIX}-release-route-disabled",
    )
    validate_problem(disabled, 503, "DOCUMENT_RELEASE_ROUTES_DISABLED")


def baseline_route_disable_probe(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    expected_mode: str,
) -> None:
    project_id, _project_version = fixture_project(administrator, base_url)
    documents = npi_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}/documents",
        query_key=f"baseline-route-documents-{expected_mode}",
    )
    require(
        documents.status == 200 and len(documents.body.get("items", [])) == 1,
        "P5-03 route switch changed the retained P5-01 list route",
    )
    result = document_baseline_request(
        administrator,
        base_url,
        project_id,
        query_key=f"baseline-route-{expected_mode}",
    )
    if expected_mode == "disabled":
        validate_problem(result, 503, "DOCUMENT_BASELINE_ROUTES_DISABLED")
        disabled_command = document_baseline_request(
            administrator,
            base_url,
            project_id,
            payload={},
            csrf_token=csrf_token,
            idempotency_key=f"{FIXTURE_PREFIX}-baseline-route-disabled",
        )
        validate_problem(
            disabled_command,
            503,
            "DOCUMENT_BASELINE_ROUTES_DISABLED",
        )
        return
    require(
        result.status == 200
        and len(result.body.get("items", [])) == 1
        and len(result.body.get("impacts", [])) == 1,
        "Recovered Document baseline route truth drifted",
    )


def run_replay(
    administrator,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
) -> None:
    owner = request(
        administrator,
        base_url,
        user_resource_path(OWNER_USER),
    )
    require(
        owner.status == 404,
        "Disposable Document runtime Project owner was not cleaned",
    )
    baseline_authority = request(
        administrator,
        base_url,
        user_resource_path(BASELINE_USER),
    )
    require(
        baseline_authority.status == 200,
        "Controlled baseline authority fixture was not retained",
    )
    project_id, project_version = fixture_project(administrator, base_url)
    policy_hash = fixture_policy_hash(administrator, base_url)
    replayed = replay_controlled_document(
        administrator,
        base_url,
        csrf_token,
        project_id=project_id,
        project_version=project_version,
        policy_snapshot_hash=policy_hash,
    )
    documents = replayed.get("document", {})
    require(
        documents.get("globalId"),
        "Document replay did not retain its exact identity",
    )
    document_id = str(documents["globalId"])
    detail = npi_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}/documents/{document_id}",
        query_key="release-replay-detail",
    )
    require(
        detail.status == 200
        and len(detail.body.get("releaseWorkspace", {}).get("revisions", []))
        == 1,
        "Retained Document release history is unavailable for replay",
    )
    revision_history = detail.body["releaseWorkspace"]["revisions"][0]
    revision_id = str(revision_history["revisionId"])
    release_replay = release_command(
        administrator,
        base_url,
        csrf_token,
        project_id=project_id,
        document_id=document_id,
        revision_id=revision_id,
        suffix="release",
        payload={
            "expectedDocumentVersion": 4,
            "expectedLifecycleVersion": 4,
            "confirmationIntent": "release_revision",
            "confirmed": True,
        },
        idempotency_key=DOCUMENT_RELEASE_KEY,
    )
    validate_release_transition(
        release_replay,
        expected_state="released",
        expected_version=5,
        expected_event="released",
        expected_confirmation="release",
        replayed=True,
    )
    baseline_actor = login(base_url, BASELINE_USER, fixture_password)
    baseline_csrf = bootstrap_csrf(
        baseline_actor,
        base_url,
        BASELINE_USER,
    )
    workspace = document_baseline_request(
        baseline_actor,
        base_url,
        project_id,
        query_key="baseline-cross-process-replay",
    )
    baselines = workspace.body.get("items", [])
    impacts = workspace.body.get("impacts", [])
    require(
        workspace.status == 200
        and len(baselines) == 1
        and len(impacts) == 1,
        "Retained Document baseline or impact lineage is unavailable for replay",
    )
    baseline = baselines[0]
    member = baseline["members"][0]
    payload = baseline_command_payload(
        policy_snapshot_hash=str(baseline["policy"]["snapshotHash"]),
        revision_id=str(member["revisionGlobalId"]),
        revision_snapshot_hash=str(member["revisionSnapshotHash"]),
        release_snapshot_hash=str(member["releaseSnapshotHash"]),
        label=str(baseline["label"]),
    )
    baseline_replay = document_baseline_request(
        baseline_actor,
        base_url,
        project_id,
        payload=payload,
        csrf_token=baseline_csrf,
        idempotency_key=DOCUMENT_BASELINE_KEY,
    )
    replayed_baseline = validate_document_baseline_command(
        baseline_replay,
        project_id=project_id,
        revision_id=str(member["revisionGlobalId"]),
        revision_snapshot_hash=str(member["revisionSnapshotHash"]),
        release_snapshot_hash=str(member["releaseSnapshotHash"]),
        policy_snapshot_hash=str(baseline["policy"]["snapshotHash"]),
        replayed=True,
    )
    require(
        replayed_baseline == baseline,
        "Cross-process Document baseline replay changed its sealed response",
    )


def verify_review_release_runtime(
    administrator,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
    *,
    project_id: str,
    document_id: str,
    revision_id: str,
    file_revision_id: str,
    release_policy_hash: str,
) -> dict[str, object]:
    owner = login(base_url, OWNER_USER, fixture_password)
    owner_csrf = bootstrap_csrf(owner, base_url, OWNER_USER)
    submit_payload = {
        "expectedDocumentVersion": 4,
        "expectedLifecycleVersion": 0,
        "policyGlobalId": DOCUMENT_RELEASE_POLICY_ID,
        "policyVersion": DOCUMENT_RELEASE_POLICY_VERSION,
        "policySnapshotHash": release_policy_hash,
        "confirmationIntent": "submit_review",
        "confirmed": True,
    }
    no_csrf = release_command(
        administrator,
        base_url,
        None,
        project_id=project_id,
        document_id=document_id,
        revision_id=revision_id,
        suffix="submit-review",
        payload=submit_payload,
        idempotency_key=f"{FIXTURE_PREFIX}-review-csrf-rejected",
    )
    validate_problem(no_csrf, 403, "CSRF_TOKEN_INVALID")
    wrong_submitter = release_command(
        owner,
        base_url,
        owner_csrf,
        project_id=project_id,
        document_id=document_id,
        revision_id=revision_id,
        suffix="submit-review",
        payload=submit_payload,
        idempotency_key=f"{FIXTURE_PREFIX}-review-authority-rejected",
    )
    validate_problem(
        wrong_submitter,
        403,
        "DOCUMENT_REVIEW_ASSIGNMENT_UNAVAILABLE",
    )

    submitted_result = release_command(
        administrator,
        base_url,
        csrf_token,
        project_id=project_id,
        document_id=document_id,
        revision_id=revision_id,
        suffix="submit-review",
        payload=submit_payload,
        idempotency_key=DOCUMENT_REVIEW_SUBMIT_KEY,
    )
    submitted = validate_release_transition(
        submitted_result,
        expected_state="in_review",
        expected_version=1,
        expected_event="submitted",
        expected_confirmation=None,
    )
    first_cycle_id = str(submitted["reviewCycleId"])
    submitted_replay = release_command(
        administrator,
        base_url,
        csrf_token,
        project_id=project_id,
        document_id=document_id,
        revision_id=revision_id,
        suffix="submit-review",
        payload=submit_payload,
        idempotency_key=DOCUMENT_REVIEW_SUBMIT_KEY,
    )
    replayed_submit = validate_release_transition(
        submitted_replay,
        expected_state="in_review",
        expected_version=1,
        expected_event="submitted",
        expected_confirmation=None,
        replayed=True,
    )
    require(
        replayed_submit == submitted,
        "Review submission replay changed its sealed response",
    )
    stale_submit = release_command(
        administrator,
        base_url,
        csrf_token,
        project_id=project_id,
        document_id=document_id,
        revision_id=revision_id,
        suffix="submit-review",
        payload=submit_payload,
        idempotency_key=f"{FIXTURE_PREFIX}-review-stale-submit",
    )
    validate_problem(
        stale_submit,
        409,
        "DOCUMENT_REVIEW_STATE_CONFLICT",
    )

    rejected_result = release_command(
        owner,
        base_url,
        owner_csrf,
        project_id=project_id,
        document_id=document_id,
        revision_id=revision_id,
        suffix="review",
        payload={
            "expectedDocumentVersion": 4,
            "expectedLifecycleVersion": 1,
            "decision": "reject",
            "reason": "Synthetic controlled rejection for resubmission proof.",
            "confirmationIntent": "review_decision",
            "confirmed": True,
        },
        idempotency_key=DOCUMENT_REVIEW_REJECT_KEY,
    )
    validate_release_transition(
        rejected_result,
        expected_state="draft",
        expected_version=2,
        expected_event="review_rejected",
        expected_confirmation="review_reject",
    )

    resubmitted_result = release_command(
        administrator,
        base_url,
        csrf_token,
        project_id=project_id,
        document_id=document_id,
        revision_id=revision_id,
        suffix="resubmit-review",
        payload={
            "expectedDocumentVersion": 4,
            "expectedLifecycleVersion": 2,
            "policyGlobalId": DOCUMENT_RELEASE_POLICY_ID,
            "policyVersion": DOCUMENT_RELEASE_POLICY_VERSION,
            "policySnapshotHash": release_policy_hash,
            "priorRejectedCycleId": first_cycle_id,
            "confirmationIntent": "resubmit_review",
            "confirmed": True,
        },
        idempotency_key=DOCUMENT_REVIEW_RESUBMIT_KEY,
    )
    resubmitted = validate_release_transition(
        resubmitted_result,
        expected_state="in_review",
        expected_version=3,
        expected_event="resubmitted",
        expected_confirmation=None,
    )
    require(
        str(resubmitted["reviewCycleId"]) != first_cycle_id,
        "Review resubmission did not append a new immutable cycle",
    )

    approved_result = release_command(
        owner,
        base_url,
        owner_csrf,
        project_id=project_id,
        document_id=document_id,
        revision_id=revision_id,
        suffix="review",
        payload={
            "expectedDocumentVersion": 4,
            "expectedLifecycleVersion": 3,
            "decision": "approve",
            "confirmationIntent": "review_decision",
            "confirmed": True,
        },
        idempotency_key=DOCUMENT_REVIEW_APPROVE_KEY,
    )
    validate_release_transition(
        approved_result,
        expected_state="approved",
        expected_version=4,
        expected_event="approved",
        expected_confirmation="review_approve",
    )

    integrity_kwargs = {
        "fixture_run_id": FIXTURE_RUN_ID,
        "file_revision_id": file_revision_id,
        "document_id": document_id,
        "project_id": project_id,
    }
    tampered = run_bench_fixture(
        "set_document_file_content",
        {**integrity_kwargs, "mode": "tamper"},
    )
    require(
        tampered.get("contentMode") == "tamper",
        "Controlled integrity mismatch was not applied",
    )
    release_payload = {
        "expectedDocumentVersion": 4,
        "expectedLifecycleVersion": 4,
        "confirmationIntent": "release_revision",
        "confirmed": True,
    }
    try:
        blocked_release = release_command(
            administrator,
            base_url,
            csrf_token,
            project_id=project_id,
            document_id=document_id,
            revision_id=revision_id,
            suffix="release",
            payload=release_payload,
            idempotency_key=f"{FIXTURE_PREFIX}-release-integrity-blocked",
        )
        validate_problem(
            blocked_release,
            409,
            "DOCUMENT_RELEASE_INTEGRITY_BLOCKED",
        )
    finally:
        restored = run_bench_fixture(
            "set_document_file_content",
            {**integrity_kwargs, "mode": "restore"},
        )
        require(
            restored.get("contentMode") == "restore",
            "Controlled integrity fixture was not restored",
        )

    released_result = release_command(
        administrator,
        base_url,
        csrf_token,
        project_id=project_id,
        document_id=document_id,
        revision_id=revision_id,
        suffix="release",
        payload=release_payload,
        idempotency_key=DOCUMENT_RELEASE_KEY,
    )
    released = validate_release_transition(
        released_result,
        expected_state="released",
        expected_version=5,
        expected_event="released",
        expected_confirmation="release",
    )
    release_snapshot_hash = released.get("releaseSnapshotHash")
    require(
        isinstance(release_snapshot_hash, str)
        and re.fullmatch(r"[a-f0-9]{64}", release_snapshot_hash) is not None,
        "Released revision snapshot hash is unavailable",
    )

    detail = npi_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}/documents/{document_id}",
        query_key="released-detail",
    )
    require_http_status(detail, {200}, "Released Document detail")
    histories = detail.body.get("releaseWorkspace", {}).get("revisions", [])
    revision_details = detail.body.get("revisions", [])
    files = revision_details[0].get("files", []) if revision_details else []
    revision_snapshot_hash = (
        revision_details[0].get("snapshotHash") if revision_details else None
    )
    require(
        detail.body.get("document", {}).get("optimisticVersion") == 4
        and len(histories) == 1
        and histories[0].get("lifecycle", {}).get("state") == "released"
        and histories[0].get("lifecycle", {}).get("version") == 5
        and len(histories[0].get("cycles", [])) == 2
        and [value.get("state") for value in histories[0]["cycles"]]
        == ["rejected", "approved"]
        and len(histories[0].get("confirmations", [])) == 3
        and len(histories[0].get("events", [])) == 5
        and len(files) == 1
        and files[0].get("released") is True
        and files[0].get("scanState") == "clean"
        and isinstance(revision_snapshot_hash, str)
        and re.fullmatch(r"[a-f0-9]{64}", revision_snapshot_hash) is not None,
        "Released Document history or retained file truth drifted",
    )
    deletion = run_bench_fixture(
        "verify_released_file_delete_guard",
        integrity_kwargs,
    )
    require(
        deletion.get("deleteRejected") is True,
        "Released File delete guard did not pass",
    )
    return {
        "deleteRejected": True,
        "integrityBlocked": True,
        "releaseSnapshotHash": release_snapshot_hash,
        "revisionSnapshotHash": revision_snapshot_hash,
        "reviewCycles": 2,
        "reviewRejectResubmit": True,
    }


def baseline_command_payload(
    *,
    policy_snapshot_hash: str,
    revision_id: str,
    revision_snapshot_hash: str,
    release_snapshot_hash: str,
    label: str = "Synthetic P5-03 exact release baseline",
) -> dict[str, object]:
    return {
        "policyGlobalId": DOCUMENT_BASELINE_POLICY_ID,
        "policyVersion": DOCUMENT_BASELINE_POLICY_VERSION,
        "policySnapshotHash": policy_snapshot_hash,
        "label": label,
        "members": [
            {
                "revisionId": revision_id,
                "expectedRevisionSnapshotHash": revision_snapshot_hash,
                "expectedLifecycleVersion": 5,
                "expectedReleaseSnapshotHash": release_snapshot_hash,
            }
        ],
    }


def document_baseline_request(
    opener,
    base_url: str,
    project_id: str,
    *,
    payload: dict[str, object] | None = None,
    csrf_token: str | None = None,
    idempotency_key: str | None = None,
    query_key: str = "baseline-query",
) -> HttpResult:
    diagnostic_scope = (
        _BASELINE_WORKSPACE_SERVER_DIAGNOSTIC_SCOPE
        if payload is None and query_key == "baseline-empty"
        else None
    )
    return npi_request(
        opener,
        base_url,
        f"/api/npi/v1/projects/{project_id}/document-baselines",
        method="POST" if payload is not None else "GET",
        payload=payload,
        csrf_token=csrf_token,
        idempotency_key=idempotency_key,
        query_key=query_key,
        server_diagnostic_scope=diagnostic_scope,
    )


def validate_document_baseline_command(
    result: HttpResult,
    *,
    project_id: str,
    revision_id: str,
    revision_snapshot_hash: str,
    release_snapshot_hash: str,
    policy_snapshot_hash: str,
    replayed: bool,
) -> dict[str, Any]:
    require_http_status(result, {201}, "Document baseline command")
    baseline = result.body.get("baseline")
    members = baseline.get("members") if isinstance(baseline, dict) else None
    require(
        result.body.get("projectId") == project_id
        and result.headers.get("Idempotency-Replayed")
        == ("true" if replayed else "false")
        and isinstance(baseline, dict)
        and baseline.get("version") == 1
        and baseline.get("createdByUserId") == BASELINE_USER
        and isinstance(baseline.get("globalId"), str)
        and re.fullmatch(r"[a-f0-9-]{36}", baseline["globalId"]) is not None
        and isinstance(baseline.get("snapshotHash"), str)
        and re.fullmatch(r"[a-f0-9]{64}", baseline["snapshotHash"]) is not None
        and baseline.get("policy")
        == {
            "globalId": DOCUMENT_BASELINE_POLICY_ID,
            "version": DOCUMENT_BASELINE_POLICY_VERSION,
            "snapshotHash": policy_snapshot_hash,
        }
        and isinstance(members, list)
        and len(members) == 1
        and members[0].get("revisionGlobalId") == revision_id
        and members[0].get("revisionSnapshotHash") == revision_snapshot_hash
        and members[0].get("lifecycleVersion") == 5
        and members[0].get("releaseSnapshotHash") == release_snapshot_hash
        and len(members[0].get("files", [])) == 1
        and members[0]["files"][0].get("scanState") == "clean"
        and "/private/files/" not in json.dumps(baseline, sort_keys=True)
        and '"url"' not in json.dumps(baseline, sort_keys=True).casefold(),
        "Immutable Document baseline response truth drifted",
    )
    return baseline


def validate_initial_document_baseline_workspace(
    result: HttpResult,
    *,
    expected_policy_hash: str,
) -> None:
    """Validate the exact empty baseline workspace through closed predicates."""

    trace_id = result.trace_id
    if result.status != 200:
        diagnostic = _sanitized_bff_log_diagnostic(trace_id)
        if (
            diagnostic is not None
            and diagnostic[1] in _BASELINE_WORKSPACE_SERVER_DIAGNOSTIC_CODES
        ):
            exception_type, code, diagnostic_trace_id = diagnostic
            raise RuntimeSubstageFailure(
                code,
                diagnostic_trace_id,
                exception_type=exception_type,
            )
    require_runtime_substage(
        result.status == 200,
        code="P503_RUNTIME_BASELINE_WORKSPACE_HTTP",
        trace_id=trace_id,
    )
    body = result.body
    require_runtime_substage(
        isinstance(body, dict),
        code="P503_RUNTIME_BASELINE_WORKSPACE_BODY_SHAPE",
        trace_id=trace_id,
    )
    permissions = body.get("permissions")
    require_runtime_substage(
        isinstance(permissions, dict)
        and set(permissions) == {"view", "create"},
        code="P503_RUNTIME_BASELINE_WORKSPACE_PERMISSIONS_SHAPE",
        trace_id=trace_id,
    )
    require_runtime_substage(
        permissions.get("view") is True,
        code="P503_RUNTIME_BASELINE_WORKSPACE_VIEW_PERMISSION",
        trace_id=trace_id,
    )
    require_runtime_substage(
        body.get("items") == [],
        code="P503_RUNTIME_BASELINE_WORKSPACE_ITEMS_EMPTY",
        trace_id=trace_id,
    )
    require_runtime_substage(
        body.get("impacts") == [],
        code="P503_RUNTIME_BASELINE_WORKSPACE_IMPACTS_EMPTY",
        trace_id=trace_id,
    )
    policies = body.get("policies")
    require_runtime_substage(
        isinstance(policies, list) and len(policies) == 1,
        code="P503_RUNTIME_BASELINE_WORKSPACE_POLICY_CARDINALITY",
        trace_id=trace_id,
    )
    policy = policies[0]
    require_runtime_substage(
        isinstance(policy, dict)
        and set(policy)
        == {"globalId", "version", "snapshotHash", "key", "title"},
        code="P503_RUNTIME_BASELINE_WORKSPACE_POLICY_SHAPE",
        trace_id=trace_id,
    )
    require_runtime_substage(
        policy.get("globalId") == DOCUMENT_BASELINE_POLICY_ID,
        code="P503_RUNTIME_BASELINE_WORKSPACE_POLICY_IDENTITY",
        trace_id=trace_id,
    )
    require_runtime_substage(
        policy.get("version") == DOCUMENT_BASELINE_POLICY_VERSION,
        code="P503_RUNTIME_BASELINE_WORKSPACE_POLICY_VERSION",
        trace_id=trace_id,
    )
    require_runtime_substage(
        policy.get("snapshotHash") == expected_policy_hash,
        code="P503_RUNTIME_BASELINE_WORKSPACE_POLICY_HASH",
        trace_id=trace_id,
    )
    require_runtime_substage(
        policy.get("key") == BASELINE_POLICY_KEY,
        code="P503_RUNTIME_BASELINE_WORKSPACE_POLICY_KEY",
        trace_id=trace_id,
    )
    require_runtime_substage(
        policy.get("title")
        == "Synthetic P5-03 document baseline policy version",
        code="P503_RUNTIME_BASELINE_WORKSPACE_POLICY_TITLE",
        trace_id=trace_id,
    )
    require_runtime_substage(
        permissions.get("create") is True,
        code="P503_RUNTIME_BASELINE_WORKSPACE_CREATE_PERMISSION",
        trace_id=trace_id,
    )


def create_document_successor(
    administrator,
    base_url: str,
    csrf_token: str,
    *,
    project_id: str,
    document_id: str,
    predecessor_revision_id: str,
    expected_document_version: int,
    lock_version: int,
    minor: int,
    idempotency_key: str,
) -> dict[str, Any]:
    result = multipart_revision_request(
        administrator,
        base_url,
        (
            f"/api/npi/v1/projects/{project_id}/documents/"
            f"{document_id}/revisions"
        ),
        csrf_token=csrf_token,
        idempotency_key=idempotency_key,
        metadata={
            "expectedDocumentVersion": expected_document_version,
            "expectedLockVersion": lock_version,
            "major": 0,
            "minor": minor,
            "reason": f"Synthetic exact successor revision 0.{minor}",
            "effectiveDate": f"2026-08-{minor:02d}",
            "predecessorRevisionId": predecessor_revision_id,
        },
        file_name=f"synthetic-runtime-drawing-0-{minor}.pdf",
        content=PDF_CONTENT,
    )
    workspace = validate_document_workspace(
        result,
        project_id=project_id,
        expected_document_id=document_id,
    )
    require(
        result.status == 201
        and result.headers.get("Idempotency-Replayed") == "false",
        "Document successor command truth drifted",
    )
    revisions = workspace.get("revisions", [])
    matches = [
        value
        for value in revisions
        if value.get("major") == 0 and value.get("minor") == minor
    ]
    require(
        len(matches) == 1
        and matches[0].get("predecessorRevisionId")
        == predecessor_revision_id
        and isinstance(matches[0].get("snapshotHash"), str)
        and re.fullmatch(r"[a-f0-9]{64}", matches[0]["snapshotHash"])
        is not None,
        "Document successor identity or exact predecessor drifted",
    )
    return matches[0]


def verify_document_baseline_runtime(
    administrator,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
    *,
    project_id: str,
    document_id: str,
    revision_id: str,
    revision_snapshot_hash: str,
    release_snapshot_hash: str,
    baseline_policy_hash: str,
    gate_template_hash: str,
) -> dict[str, object]:
    baseline_actor = login(base_url, BASELINE_USER, fixture_password)
    baseline_csrf = bootstrap_csrf(baseline_actor, base_url, BASELINE_USER)
    initial = document_baseline_request(
        baseline_actor,
        base_url,
        project_id,
        query_key="baseline-empty",
    )
    validate_initial_document_baseline_workspace(
        initial,
        expected_policy_hash=baseline_policy_hash,
    )
    payload = baseline_command_payload(
        policy_snapshot_hash=baseline_policy_hash,
        revision_id=revision_id,
        revision_snapshot_hash=revision_snapshot_hash,
        release_snapshot_hash=release_snapshot_hash,
    )
    no_csrf = document_baseline_request(
        baseline_actor,
        base_url,
        project_id,
        payload=payload,
        idempotency_key=f"{FIXTURE_PREFIX}-baseline-csrf-rejected",
    )
    validate_problem(no_csrf, 403, "CSRF_TOKEN_INVALID")
    created_result = document_baseline_request(
        baseline_actor,
        base_url,
        project_id,
        payload=payload,
        csrf_token=baseline_csrf,
        idempotency_key=DOCUMENT_BASELINE_KEY,
    )
    baseline = validate_document_baseline_command(
        created_result,
        project_id=project_id,
        revision_id=revision_id,
        revision_snapshot_hash=revision_snapshot_hash,
        release_snapshot_hash=release_snapshot_hash,
        policy_snapshot_hash=baseline_policy_hash,
        replayed=False,
    )
    baseline_id = str(baseline["globalId"])
    baseline_hash = str(baseline["snapshotHash"])
    replay = document_baseline_request(
        baseline_actor,
        base_url,
        project_id,
        payload=payload,
        csrf_token=baseline_csrf,
        idempotency_key=DOCUMENT_BASELINE_KEY,
    )
    replayed_baseline = validate_document_baseline_command(
        replay,
        project_id=project_id,
        revision_id=revision_id,
        revision_snapshot_hash=revision_snapshot_hash,
        release_snapshot_hash=release_snapshot_hash,
        policy_snapshot_hash=baseline_policy_hash,
        replayed=True,
    )
    require(replayed_baseline == baseline, "Document baseline replay drifted")
    conflict_payload = dict(payload)
    conflict_payload["label"] = "Conflicting synthetic release baseline"
    conflict = document_baseline_request(
        baseline_actor,
        base_url,
        project_id,
        payload=conflict_payload,
        csrf_token=baseline_csrf,
        idempotency_key=DOCUMENT_BASELINE_KEY,
    )
    validate_problem(conflict, 409, "DOCUMENT_BASELINE_IDEMPOTENCY_CONFLICT")

    gate_id = configured_gate_id(project_id)
    freeze = npi_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}/gates/{gate_id}:freeze-requirements",
        method="POST",
        payload={
            "expectedGateVersion": 1,
            "gateDueDate": "2026-08-31",
            "requirements": [
                {
                    "key": GATE_REQUIREMENT_KEY,
                    "ownerMemberId": BASELINE_MEMBER_ID,
                    "reviewerMemberIds": [BASELINE_MEMBER_ID],
                    "dueDate": "2026-08-20",
                }
            ],
        },
        csrf_token=csrf_token,
        idempotency_key=GATE_FREEZE_KEY,
    )
    require(
        freeze.status == 200
        and freeze.headers.get("Idempotency-Replayed") == "false"
        and freeze.body.get("gate", {}).get("version") == 2,
        "Exact baseline Gate requirement freeze drifted",
    )
    attached = npi_request(
        administrator,
        base_url,
        (
            f"/api/npi/v1/projects/{project_id}/gates/{gate_id}/"
            f"requirements/{GATE_REQUIREMENT_KEY}/evidence"
        ),
        method="POST",
        payload={
            "expectedGateVersion": 2,
            "evidenceKind": "release_baseline",
            "sourceGlobalId": baseline_id,
            "sourceVersion": 1,
            "sourceHash": baseline_hash,
        },
        csrf_token=csrf_token,
        idempotency_key=GATE_BASELINE_ATTACH_KEY,
    )
    requirements = attached.body.get("requirements", [])
    evidence = (
        requirements[0].get("evidence", [])
        if len(requirements) == 1
        else []
    )
    require(
        attached.status == 201
        and attached.headers.get("Idempotency-Replayed") == "false"
        and attached.body.get("gate", {}).get("version") == 3
        and len(evidence) == 1
        and evidence[0].get("kind") == "release_baseline"
        and evidence[0].get("sourceGlobalId") == baseline_id
        and evidence[0].get("revision") == 1
        and evidence[0].get("objectHash") == baseline_hash
        and evidence[0].get("baseline") == baseline
        and '"url"' not in json.dumps(evidence[0], sort_keys=True).casefold(),
        "Exact baseline Gate evidence attachment drifted",
    )
    evidence_reference_id = str(evidence[0]["globalId"])
    dependencies = list_resources(
        administrator,
        base_url,
        "NPI Baseline Gate Dependency",
        filters=[
            ["baseline_global_id", "=", baseline_id],
            ["gate_global_id", "=", gate_id],
        ],
        fields=[
            "global_id",
            "baseline_snapshot_hash",
            "input_revision_global_id",
            "input_revision_snapshot_hash",
            "requirement_key",
            "evidence_reference_global_id",
            "snapshot_hash",
        ],
    )
    require(
        len(dependencies) == 1
        and dependencies[0].get("baseline_snapshot_hash") == baseline_hash
        and dependencies[0].get("input_revision_global_id") == revision_id
        and dependencies[0].get("input_revision_snapshot_hash")
        == revision_snapshot_hash
        and dependencies[0].get("requirement_key") == GATE_REQUIREMENT_KEY
        and dependencies[0].get("evidence_reference_global_id")
        == evidence_reference_id
        and re.fullmatch(
            r"[a-f0-9]{64}",
            str(dependencies[0].get("snapshot_hash")),
        )
        is not None,
        "Exact baseline Gate dependency registration drifted",
    )
    dependency_id = str(dependencies[0]["global_id"])

    review_policy_hash = ensure_gate_review_policy(
        administrator,
        base_url,
        csrf_token,
        gate_template_hash=gate_template_hash,
    )
    started = npi_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}/gates/{gate_id}:start-review",
        method="POST",
        payload={
            "expectedGateVersion": 3,
            "policyGlobalId": GATE_REVIEW_POLICY_ID,
            "policyVersion": GATE_REVIEW_POLICY_VERSION,
            "policySnapshotHash": review_policy_hash,
            "bindings": [
                {"slot": slot, "memberGlobalId": BASELINE_MEMBER_ID}
                for slot in (
                    GATE_REVIEW_SLOT,
                    GATE_DECISION_SLOT,
                    GATE_REOPEN_SLOT,
                )
            ],
        },
        csrf_token=csrf_token,
        idempotency_key=GATE_REVIEW_START_KEY,
    )
    initial_cycle = started.body.get("activeCycle")
    require(
        started.status == 201
        and started.headers.get("Idempotency-Replayed") == "false"
        and started.body.get("gate", {}).get("reviewState") == "in_review"
        and started.body.get("gate", {}).get("version") == 4
        and isinstance(initial_cycle, dict)
        and initial_cycle.get("number") == 1
        and initial_cycle.get("state") == "active",
        "Initial exact-baseline Gate Review cycle drifted",
    )
    initial_cycle_id = str(initial_cycle["globalId"])
    initial_input_hash = str(initial_cycle["inputHash"])

    checked_out = npi_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}/documents/{document_id}:check-out",
        method="POST",
        payload={"expectedDocumentVersion": 4},
        csrf_token=csrf_token,
        idempotency_key=DOCUMENT_SUCCESSOR_CHECK_OUT_KEY,
    )
    successor_lock = validate_document_workspace(
        checked_out,
        project_id=project_id,
        expected_document_id=document_id,
    )
    lock = successor_lock.get("document", {}).get("currentLock")
    require(
        successor_lock.get("document", {}).get("optimisticVersion") == 5
        and checked_out.headers.get("Idempotency-Replayed") == "false"
        and isinstance(lock, dict)
        and lock.get("holderUserId") == "Administrator"
        and lock.get("version") == 2,
        "Document successor lock truth drifted",
    )
    successor = create_document_successor(
        administrator,
        base_url,
        csrf_token,
        project_id=project_id,
        document_id=document_id,
        predecessor_revision_id=revision_id,
        expected_document_version=5,
        lock_version=2,
        minor=2,
        idempotency_key=DOCUMENT_SUCCESSOR_KEY,
    )
    successor_id = str(successor["globalId"])
    successor_hash = str(successor["snapshotHash"])
    impacted = document_baseline_request(
        baseline_actor,
        base_url,
        project_id,
        query_key="baseline-impacted",
    )
    impacts = impacted.body.get("impacts", [])
    require(
        impacted.status == 200
        and impacted.body.get("items") == [baseline]
        and len(impacts) == 1
        and impacts[0].get("eventType") == "invalidated"
        and impacts[0].get("dependencyGlobalId") == dependency_id
        and impacts[0].get("baselineGlobalId") == baseline_id
        and impacts[0].get("baselineSnapshotHash") == baseline_hash
        and impacts[0].get("oldRevisionGlobalId") == revision_id
        and impacts[0].get("oldRevisionSnapshotHash") == revision_snapshot_hash
        and impacts[0].get("newRevisionGlobalId") == successor_id
        and impacts[0].get("newRevisionSnapshotHash") == successor_hash
        and impacts[0].get("gateGlobalId") == gate_id
        and impacts[0].get("evidenceReferenceGlobalId")
        == evidence_reference_id
        and impacts[0].get("initiatedByUserId") == "Administrator"
        and re.fullmatch(r"[a-f0-9]{64}", str(impacts[0].get("eventHash")))
        is not None,
        "Registered baseline successor impact lineage drifted",
    )
    refreshed = npi_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}/gates/{gate_id}/review",
        query_key="baseline-impact-review",
    )
    successor_cycle = refreshed.body.get("activeCycle")
    dependency_changes = refreshed.body.get("dependencyChanges", [])
    require(
        refreshed.status == 200
        and refreshed.body.get("gate", {}).get("reviewState")
        == "requires_review"
        and refreshed.body.get("gate", {}).get("version") == 5
        and isinstance(successor_cycle, dict)
        and successor_cycle.get("number") == 2
        and successor_cycle.get("state") == "active"
        and successor_cycle.get("trigger") == "dependency_change"
        and successor_cycle.get("inputHash") != initial_input_hash
        and len(dependency_changes) == 1
        and dependency_changes[0].get("eventType") == "refreshed"
        and dependency_changes[0].get("priorCycleGlobalId")
        == initial_cycle_id
        and dependency_changes[0].get("successorCycleGlobalId")
        == successor_cycle.get("globalId")
        and dependency_changes[0].get("reason")
        == "BASELINE_SUCCESSOR_IMPACT"
        and dependency_changes[0].get("initiatedByUserId") == "Administrator",
        "Baseline successor did not refresh the existing Gate Review lineage",
    )
    successor_cycle_id = str(successor_cycle["globalId"])
    successor_input_hash = str(successor_cycle["inputHash"])

    unregistered = create_document_successor(
        administrator,
        base_url,
        csrf_token,
        project_id=project_id,
        document_id=document_id,
        predecessor_revision_id=successor_id,
        expected_document_version=6,
        lock_version=2,
        minor=3,
        idempotency_key=DOCUMENT_UNREGISTERED_SUCCESSOR_KEY,
    )
    unchanged = document_baseline_request(
        baseline_actor,
        base_url,
        project_id,
        query_key="baseline-unregistered-successor",
    )
    unchanged_review = npi_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}/gates/{gate_id}/review",
        query_key="baseline-unregistered-review",
    )
    require(
        unregistered.get("predecessorRevisionId") == successor_id
        and unchanged.status == 200
        and unchanged.body.get("items") == [baseline]
        and unchanged.body.get("impacts") == impacts
        and unchanged_review.status == 200
        and unchanged_review.body.get("gate", {}).get("version") == 5
        and unchanged_review.body.get("activeCycle", {}).get("globalId")
        == successor_cycle_id
        and unchanged_review.body.get("activeCycle", {}).get("inputHash")
        == successor_input_hash
        and unchanged_review.body.get("dependencyChanges")
        == dependency_changes,
        "Unregistered successor created inferred baseline impact lineage",
    )
    return {
        "baselineCrossProcessReplayReady": True,
        "baselineGateDependencyCount": len(dependencies),
        "baselineId": baseline_id,
        "baselineImpactCount": len(impacts),
        "baselineReplayConflict": True,
        "baselineSnapshotHash": baseline_hash,
        "gateReviewSuccessorCycle": 2,
        "registeredSuccessorImpact": True,
        "unregisteredSuccessorNoImpact": True,
    }


def run_fresh(
    administrator,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
) -> dict[str, object]:
    verify_fresh_namespace(administrator, base_url)
    create_internal_fixture_user(
        administrator,
        base_url,
        OWNER_USER,
        fixture_password,
        csrf_token,
    )
    try:
        create_internal_fixture_user(
            administrator,
            base_url,
            BASELINE_USER,
            fixture_password,
            csrf_token,
        )
        evidence = _run_fresh_with_owner(
            administrator,
            base_url,
            csrf_token,
            fixture_password,
        )
    finally:
        delete_disposable_user(
            administrator,
            base_url,
            OWNER_USER,
            csrf_token,
        )
    return {
        **evidence,
        "baselineAuthorityFixtureRetained": True,
        "ownerFixtureCleaned": True,
    }


def _run_fresh_with_owner(
    administrator,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
) -> dict[str, object]:
    schema = run_bench_fixture(
        "verify_document_runtime_schema",
        {"fixture_run_id": FIXTURE_RUN_ID},
    )
    gate_template_hash = ensure_gate_template(
        administrator,
        base_url,
        csrf_token,
    )
    ensure_project_template(
        administrator,
        base_url,
        csrf_token,
        gate_template_hash=gate_template_hash,
    )
    project_id, project_version = create_project(
        administrator,
        base_url,
        csrf_token,
    )
    work_policy_ref = ensure_project_work_policy(
        administrator,
        base_url,
        csrf_token,
    )
    configure_baseline_project_member(
        administrator,
        base_url,
        csrf_token,
        project_id=project_id,
        work_policy_ref=work_policy_ref,
    )
    project_version = 2
    policy_hash = ensure_document_policy(
        administrator,
        base_url,
        csrf_token,
    )
    release_policy_hash = ensure_document_release_policy(
        administrator,
        base_url,
        csrf_token,
        project_id=project_id,
    )
    baseline_policy_hash = ensure_document_baseline_policy(
        administrator,
        base_url,
        csrf_token,
        project_id=project_id,
    )
    empty = npi_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}/documents",
        query_key="empty",
    )
    require(
        empty.status == 200
        and empty.body.get("items") == []
        and len(empty.body.get("policies", [])) == 1,
        "Empty Document workspace or explicit policy truth drifted",
    )

    no_csrf = npi_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}/documents",
        method="POST",
        payload={
            "policyGlobalId": DOCUMENT_POLICY_ID,
            "policyVersion": DOCUMENT_POLICY_VERSION,
            "policySnapshotHash": policy_hash,
            "documentTypeKey": "drawing",
            "title": "Rejected synthetic document",
            "confidentialityKey": "internal",
            "objectLinks": [],
        },
        csrf_token=None,
        idempotency_key=f"{FIXTURE_PREFIX}-csrf-rejected",
    )
    validate_problem(no_csrf, 403, "CSRF_TOKEN_INVALID")

    workspace = create_controlled_document(
        administrator,
        base_url,
        csrf_token,
        project_id=project_id,
        project_version=project_version,
        policy_snapshot_hash=policy_hash,
    )
    document = workspace["document"]
    document_id = str(document["globalId"])

    replay = replay_controlled_document(
        administrator,
        base_url,
        csrf_token,
        project_id=project_id,
        project_version=project_version,
        policy_snapshot_hash=policy_hash,
    )
    require(
        replay.get("document", {}).get("globalId") == document_id,
        "Immediate Document replay identity drifted",
    )

    check_out = npi_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}/documents/{document_id}:check-out",
        method="POST",
        payload={"expectedDocumentVersion": 1},
        csrf_token=csrf_token,
        idempotency_key=DOCUMENT_CHECK_OUT_KEY,
    )
    locked = validate_document_workspace(
        check_out,
        project_id=project_id,
        expected_document_id=document_id,
    )
    lock = locked["document"]["currentLock"]
    require(
        locked["document"]["optimisticVersion"] == 2
        and lock["holderUserId"] == "Administrator"
        and lock["version"] == 1,
        "Document lock acquisition truth drifted",
    )

    stale = npi_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}/documents/{document_id}:check-out",
        method="POST",
        payload={"expectedDocumentVersion": 1},
        csrf_token=csrf_token,
        idempotency_key=f"{FIXTURE_PREFIX}-stale-lock",
    )
    validate_problem(stale, 409, "DOCUMENT_VERSION_CONFLICT")

    revision = multipart_revision_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}/documents/{document_id}/revisions",
        csrf_token=csrf_token,
        idempotency_key=DOCUMENT_REVISION_KEY,
        metadata={
            "expectedDocumentVersion": 2,
            "expectedLockVersion": 1,
            "major": 0,
            "minor": 1,
            "reason": "Initial synthetic runtime revision",
            "effectiveDate": "2026-07-30",
            "predecessorRevisionId": None,
        },
        file_name="synthetic-runtime-drawing.pdf",
        content=PDF_CONTENT,
    )
    revised = validate_document_workspace(
        revision,
        project_id=project_id,
        expected_document_id=document_id,
    )
    require(revision.status == 201, "Document revision did not return HTTP 201")
    revision_row = revised["revisions"][0]
    file_row = revision_row["files"][0]
    require(
        revised["document"]["optimisticVersion"] == 3
        and revision_row["major"] == 0
        and revision_row["minor"] == 1
        and file_row["scanState"] == "pending"
        and file_row["capabilities"]["preview"]["state"] == "blocked"
        and file_row["connector"]["state"] == "unavailable",
        "Immutable revision or provider capability truth drifted",
    )
    require(
        file_row["sha256"] == hashlib.sha256(PDF_CONTENT).hexdigest(),
        "Server-observed runtime file hash drifted",
    )

    revision_id = str(revision_row["globalId"])
    file_revision_id = str(file_row["globalId"])
    capability_path = (
        f"/api/npi/v1/projects/{project_id}/documents/{document_id}/revisions/"
        f"{revision_id}/files/{file_revision_id}/capabilities"
    )
    pending_capability = npi_request(
        administrator,
        base_url,
        capability_path,
        query_key="pending-capability",
    )
    require(
        pending_capability.status == 200
        and pending_capability.body["capabilities"]["preview"]["state"]
        == "blocked",
        "Pending scanner capability did not fail closed",
    )

    scan = run_bench_fixture(
        "observe_document_file_scan",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "file_revision_id": file_revision_id,
            "document_id": document_id,
            "project_id": project_id,
        },
    )
    require(
        scan.get("scanState") == "clean"
        and scan.get("optimisticVersion") == 2,
        "Controlled scanner observation truth drifted",
    )
    clean_capability = npi_request(
        administrator,
        base_url,
        capability_path,
        query_key="clean-capability",
    )
    require(
        clean_capability.status == 200
        and clean_capability.body["capabilities"]["preview"]["state"]
        == "available"
        and clean_capability.body["capabilities"]["download"]["state"]
        == "available"
        and clean_capability.body["capabilities"]["externalRetrieval"]["state"]
        == "unavailable",
        "Clean file capability truth drifted",
    )

    content_path = (
        f"/api/npi/v1/projects/{project_id}/documents/{document_id}/revisions/"
        f"{revision_id}/files/{file_revision_id}:content"
    )
    content = binary_content_request(
        administrator,
        base_url,
        content_path,
        csrf_token=csrf_token,
        idempotency_key=DOCUMENT_CONTENT_KEY,
        expected_document_version=3,
        expected_file_version=2,
    )
    require(
        content.status == 200
        and content.content == PDF_CONTENT
        and content.headers.get_content_type() == "application/pdf"
        and content.headers.get("Cache-Control") == "private, no-store"
        and content.headers.get("X-Content-Type-Options") == "nosniff"
        and content.headers.get("Referrer-Policy") == "no-referrer"
        and content.headers.get("Idempotency-Replayed") == "false",
        "Audited private content response truth drifted",
    )
    content_replay = binary_content_request(
        administrator,
        base_url,
        content_path,
        csrf_token=csrf_token,
        idempotency_key=DOCUMENT_CONTENT_KEY,
        expected_document_version=3,
        expected_file_version=2,
    )
    require(
        content_replay.status == 200
        and content_replay.content == PDF_CONTENT
        and content_replay.headers.get("Idempotency-Replayed") == "true",
        "Audited private content replay truth drifted",
    )

    checked_in = npi_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}/documents/{document_id}:check-in",
        method="POST",
        payload={
            "expectedDocumentVersion": 3,
            "expectedLockVersion": 1,
        },
        csrf_token=csrf_token,
        idempotency_key=DOCUMENT_CHECK_IN_KEY,
    )
    released = validate_document_workspace(
        checked_in,
        project_id=project_id,
        expected_document_id=document_id,
    )
    require(
        released["document"]["optimisticVersion"] == 4
        and released["document"]["currentLock"] is None
        and [row["eventType"] for row in released["lockHistory"]]
        == ["released", "acquired"],
        "Document check-in or immutable lock history truth drifted",
    )
    release_evidence = verify_review_release_runtime(
        administrator,
        base_url,
        csrf_token,
        fixture_password,
        project_id=project_id,
        document_id=document_id,
        revision_id=revision_id,
        file_revision_id=file_revision_id,
        release_policy_hash=release_policy_hash,
    )
    baseline_evidence = verify_document_baseline_runtime(
        administrator,
        base_url,
        csrf_token,
        fixture_password,
        project_id=project_id,
        document_id=document_id,
        revision_id=revision_id,
        revision_snapshot_hash=str(
            release_evidence["revisionSnapshotHash"]
        ),
        release_snapshot_hash=str(release_evidence["releaseSnapshotHash"]),
        baseline_policy_hash=baseline_policy_hash,
        gate_template_hash=gate_template_hash,
    )

    relationship_filter = npi_request(
        administrator,
        base_url,
        (
            f"/api/npi/v1/projects/{project_id}/documents"
            f"?relationshipKind=project&targetIdentity={project_id}"
            f"&targetVersion={project_version}"
        ),
        query_key="relationship-filter",
    )
    require_runtime_substage(
        relationship_filter.status == 200,
        code="P5_RUNTIME_RELATIONSHIP_FILTER_HTTP",
        trace_id=relationship_filter.trace_id,
    )
    relationship_ids = [
        row["globalId"] for row in relationship_filter.body.get("items", [])
    ]
    require_runtime_substage(
        len(relationship_ids) == 1,
        code="P5_RUNTIME_RELATIONSHIP_FILTER_CARDINALITY",
        trace_id=relationship_filter.trace_id,
    )
    require_runtime_substage(
        relationship_ids[0] == document_id,
        code="P5_RUNTIME_RELATIONSHIP_FILTER_IDENTITY",
        trace_id=relationship_filter.trace_id,
    )

    unrelated_created = create_disposable_user(
        administrator,
        base_url,
        UNRELATED_USER,
        fixture_password,
        csrf_token,
    )
    validate_disposable_user(unrelated_created, UNRELATED_USER)
    try:
        unrelated = login(base_url, UNRELATED_USER, fixture_password)
        bootstrap_csrf(unrelated, base_url, UNRELATED_USER)
        unavailable = npi_request(
            unrelated,
            base_url,
            f"/api/npi/v1/projects/{project_id}/documents/{document_id}",
            query_key="unrelated",
        )
        absent = npi_request(
            unrelated,
            base_url,
            f"/api/npi/v1/projects/{project_id}/documents/{fixture_id('absent')}",
            query_key="absent",
        )
        validate_problem(unavailable, 404, "DOCUMENT_UNAVAILABLE")
        validate_problem(absent, 404, "DOCUMENT_UNAVAILABLE")
        require(
            {
                key: unavailable.body.get(key)
                for key in ("type", "title", "status", "code", "retryable")
            }
            == {
                key: absent.body.get(key)
                for key in ("type", "title", "status", "code", "retryable")
            },
            "Unauthorized and absent Document problems are distinguishable",
        )
    finally:
        delete_disposable_user(
            administrator,
            base_url,
            UNRELATED_USER,
            csrf_token,
        )

    guest = npi_request(
        urllib.request.build_opener(),
        base_url,
        f"/api/npi/v1/projects/{project_id}/documents",
        query_key="guest",
    )
    validate_problem(guest, 401, "AUTHENTICATION_REQUIRED")

    expected_audit_traces = {
        "document.create": DOCUMENT_CREATE_KEY,
        "document.lock.acquire": DOCUMENT_CHECK_OUT_KEY,
        "document.revision.create": DOCUMENT_REVISION_KEY,
        "document.content.inline": DOCUMENT_CONTENT_KEY,
        "document.lock.release": DOCUMENT_CHECK_IN_KEY,
        "document.review.submit": DOCUMENT_REVIEW_SUBMIT_KEY,
        "document.review.reject": DOCUMENT_REVIEW_REJECT_KEY,
        "document.review.resubmit": DOCUMENT_REVIEW_RESUBMIT_KEY,
        "document.review.approve": DOCUMENT_REVIEW_APPROVE_KEY,
        "document.release": DOCUMENT_RELEASE_KEY,
        "document.baseline.create": DOCUMENT_BASELINE_KEY,
        "gate.requirements.freeze": GATE_FREEZE_KEY,
        "gate.evidence.attach": GATE_BASELINE_ATTACH_KEY,
        "gate.review.start": GATE_REVIEW_START_KEY,
        "document.baseline.impact.record": DOCUMENT_SUCCESSOR_KEY,
    }
    audits = []
    for operation, command_key in expected_audit_traces.items():
        rows = list_resources(
            administrator,
            base_url,
            "NPI Audit Event",
            filters=[
                ["operation", "=", operation],
                ["trace_id", "=", fixture_trace_id(command_key)],
            ],
            fields=["operation", "result", "trace_id"],
        )
        require(
            len(rows) == 1,
            f"Document runtime audit cardinality drifted for {operation}",
        )
        audits.extend(rows)
    require(
        {row["operation"] for row in audits}
        == set(expected_audit_traces),
        "Document runtime audit history is incomplete",
    )
    require(
        all(row.get("trace_id") for row in audits),
        "Document runtime audit lost trace identity",
    )
    return {
        "auditOperations": len(audits),
        "contentBytes": len(PDF_CONTENT),
        "documentId": document_id,
        "externalRetrieval": "unavailable",
        "fileRevisionId": file_revision_id,
        "fixtureRunId": FIXTURE_RUN_ID,
        "idempotentReplay": True,
        "metadataSynchronized": schema.get("metadataSynchronized"),
        "projectId": project_id,
        "rawPrivateUrlExposed": False,
        "scanState": "clean",
        "typedRelationshipQuery": True,
        **baseline_evidence,
        **release_evidence,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the real P5-01 controlled-document runtime.",
    )
    parser.add_argument("--base-url")
    parser.add_argument(
        "--bench-fixture",
        choices=(
            "observe_document_file_scan",
            "set_document_file_content",
            "verify_released_file_delete_guard",
            "verify_document_runtime_schema",
        ),
    )
    parser.add_argument("--fixture-kwargs")
    parser.add_argument(
        "--route-disable-probe",
        choices=("disabled", "recovered"),
    )
    parser.add_argument(
        "--release-route-disable-probe",
        choices=("disabled", "recovered"),
    )
    parser.add_argument(
        "--baseline-route-disable-probe",
        choices=("disabled", "recovered"),
    )
    parser.add_argument("--replay-only", action="store_true")
    arguments = parser.parse_args()
    if arguments.bench_fixture is not None:
        require(
            arguments.base_url is None
            and isinstance(arguments.fixture_kwargs, str)
            and not arguments.replay_only
            and arguments.route_disable_probe is None
            and arguments.release_route_disable_probe is None
            and arguments.baseline_route_disable_probe is None,
            "Controlled Document Bench fixture arguments are invalid",
        )
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "Document fixture kwargs must be an object")
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return

    require(
        isinstance(arguments.base_url, str)
        and arguments.fixture_kwargs is None
        and CALLER_SUPPLIED_FIXTURE_RUN_ID is not None,
        "The P5-01 runtime base URL and fixture namespace are required",
    )
    administrator_user = "Administrator"
    administrator_password = secret_from_environment(
        "NPI_RUNTIME_ADMINISTRATOR_PASSWORD"
    )
    fixture_password = secret_from_environment("NPI_RUNTIME_FIXTURE_PASSWORD")
    base_url = validate_local_fixture_inputs(
        arguments.base_url,
        administrator_user,
        OWNER_USER,
    )
    validate_local_fixture_inputs(
        base_url,
        administrator_user,
        UNRELATED_USER,
    )
    validate_local_fixture_inputs(
        base_url,
        administrator_user,
        BASELINE_USER,
    )
    require(
        BUSINESS_CODE.startswith("P5-01-")
        and OWNER_USER.endswith("@example.invalid")
        and BASELINE_USER.endswith("@example.invalid")
        and UNRELATED_USER.endswith("@example.invalid")
        and len({OWNER_USER, BASELINE_USER, UNRELATED_USER}) == 3
        and OWNER_USER != UNRELATED_USER,
        "Document runtime fixture identity drifted",
    )
    administrator = login(
        base_url,
        administrator_user,
        administrator_password,
    )
    csrf_token = bootstrap_csrf(
        administrator,
        base_url,
        administrator_user,
    )
    require(
        sum(
            value is not None
            for value in (
                arguments.route_disable_probe,
                arguments.release_route_disable_probe,
                arguments.baseline_route_disable_probe,
            )
        )
        + int(arguments.replay_only)
        <= 1,
        "Controlled Document runtime modes are mutually exclusive",
    )
    if arguments.route_disable_probe is not None:
        route_disable_probe(
            administrator,
            base_url,
            expected_mode=arguments.route_disable_probe,
        )
        print(
            json.dumps(
                {"routeMode": arguments.route_disable_probe},
                sort_keys=True,
            )
        )
        return
    if arguments.release_route_disable_probe is not None:
        release_route_disable_probe(
            administrator,
            base_url,
            csrf_token,
            expected_mode=arguments.release_route_disable_probe,
        )
        print(
            json.dumps(
                {"releaseRouteMode": arguments.release_route_disable_probe},
                sort_keys=True,
            )
        )
        return
    if arguments.baseline_route_disable_probe is not None:
        baseline_route_disable_probe(
            administrator,
            base_url,
            csrf_token,
            expected_mode=arguments.baseline_route_disable_probe,
        )
        print(
            json.dumps(
                {"baselineRouteMode": arguments.baseline_route_disable_probe},
                sort_keys=True,
            )
        )
        return
    if arguments.replay_only:
        run_replay(
            administrator,
            base_url,
            csrf_token,
            fixture_password,
        )
        print(
            json.dumps(
                {
                    "crossProcessReplay": True,
                    "fixtureRunId": FIXTURE_RUN_ID,
                },
                sort_keys=True,
            )
        )
        print("local Frappe Document runtime replay verification passed")
        return

    evidence = run_fresh(
        administrator,
        base_url,
        csrf_token,
        fixture_password,
    )
    print(json.dumps(evidence, sort_keys=True))
    print("local Frappe Document runtime verification passed")


if __name__ == "__main__":
    try:
        main()
    except RuntimeSubstageFailure as error:
        print(runtime_substage_diagnostic(error), file=sys.stderr)
        raise SystemExit(1) from None
