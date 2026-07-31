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
from uuid import NAMESPACE_URL, uuid4, uuid5

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
_SENSITIVE_DIAGNOSTIC_PATTERN = re.compile(
    r"\b(?:authorization|cookie|csrf|password|passwd|pwd|secret|token)\b",
    re.IGNORECASE,
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
OWNER_USER = (
    f"npi-document-{FIXTURE_RUN_ID[:20]}-owner@example.invalid"
)
UNRELATED_USER = (
    f"npi-document-{FIXTURE_RUN_ID[:20]}-unrelated@example.invalid"
)
BUSINESS_CODE = f"P5-01-{FIXTURE_RUN_ID[:16].upper()}"
PROJECT_TEMPLATE_CODE = f"P501-{FIXTURE_RUN_ID[:16].upper()}"
POLICY_KEY = f"p5_01_runtime_{FIXTURE_RUN_ID}"
RELEASE_POLICY_KEY = f"p5_02_runtime_{FIXTURE_RUN_ID}"
PROJECT_CREATE_KEY = f"{FIXTURE_PREFIX}-project-create"
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


@dataclass(frozen=True)
class BinaryHttpResult:
    status: int
    headers: Any
    content: bytes
    problem: dict[str, Any] | None


class RuntimeSubstageFailure(RuntimeError):
    """Closed verifier failure that exposes no response or exception text."""

    def __init__(self, code: str, trace_id: str) -> None:
        super().__init__("Controlled Document runtime substage failed")
        self.code = code
        self.trace_id = trace_id


def require_runtime_substage(
    condition: bool,
    *,
    code: str,
    trace_id: str,
) -> None:
    if code not in _RUNTIME_RELATIONSHIP_DIAGNOSTIC_CODES:
        raise ValueError("Runtime diagnostic code is not allowlisted")
    if _DIAGNOSTIC_TRACE_PATTERN.fullmatch(trace_id) is None:
        raise ValueError("Runtime diagnostic trace identity is invalid")
    if not condition:
        raise RuntimeSubstageFailure(code, trace_id)


def runtime_substage_diagnostic(error: RuntimeSubstageFailure) -> str:
    return (
        f"[diagnostic_code={error.code}; "
        f"exc_type={type(error).__name__}; "
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
) -> HttpResult:
    headers = (
        command_headers(csrf_token, idempotency_key)
        if idempotency_key is not None
        else query_headers(f"{query_key}-{uuid4().hex}")
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


def ensure_project_template(
    administrator,
    base_url: str,
    csrf_token: str,
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
                    "gate_key": "G0",
                    "title": "Synthetic document intake",
                    "sequence": 1,
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


def verify_fresh_namespace(administrator, base_url: str) -> None:
    for user in (OWNER_USER, UNRELATED_USER):
        result = request(administrator, base_url, user_resource_path(user))
        require(
            result.status == 404,
            f"Fresh runtime fixture already contains User {user}",
        )
    for doctype, name in (
        ("NPI Project Template", PROJECT_TEMPLATE_ID),
        ("NPI Document Policy", DOCUMENT_POLICY_ID),
        ("NPI Document Release Policy", DOCUMENT_RELEASE_POLICY_ID),
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
    require(
        str(revision.project_global_id) == project_id
        and str(revision.document_global_id) == document_id
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


def run_replay(
    administrator,
    base_url: str,
    csrf_token: str,
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
    revision_id = str(detail.body["revisions"][0]["globalId"])
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
    files = detail.body.get("revisions", [])[0].get("files", [])
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
        and files[0].get("scanState") == "clean",
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
        "reviewCycles": 2,
        "reviewRejectResubmit": True,
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
    owner_cleanup_required = True
    try:
        evidence = _run_fresh_with_owner(
            administrator,
            base_url,
            csrf_token,
            fixture_password,
        )
    finally:
        if owner_cleanup_required:
            delete_disposable_user(
                administrator,
                base_url,
                OWNER_USER,
                csrf_token,
            )
    return {
        **evidence,
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
    ensure_project_template(
        administrator,
        base_url,
        csrf_token,
    )
    project_id, project_version = create_project(
        administrator,
        base_url,
        csrf_token,
    )
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
    parser.add_argument("--replay-only", action="store_true")
    arguments = parser.parse_args()
    if arguments.bench_fixture is not None:
        require(
            arguments.base_url is None
            and isinstance(arguments.fixture_kwargs, str)
            and not arguments.replay_only
            and arguments.route_disable_probe is None
            and arguments.release_route_disable_probe is None,
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
    require(
        BUSINESS_CODE.startswith("P5-01-")
        and OWNER_USER.endswith("@example.invalid")
        and UNRELATED_USER.endswith("@example.invalid")
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
    if arguments.replay_only:
        run_replay(administrator, base_url, csrf_token)
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
