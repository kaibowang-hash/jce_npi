from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import subprocess
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
)
PDF_CONTENT = b"%PDF-1.7\n% NPI One synthetic runtime document\n"
_DIAGNOSTIC_TEXT_LIMIT = 240
_DIAGNOSTIC_TYPE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,127}$")
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
OWNER_USER = (
    f"npi-document-{FIXTURE_RUN_ID[:20]}-owner@example.invalid"
)
UNRELATED_USER = (
    f"npi-document-{FIXTURE_RUN_ID[:20]}-unrelated@example.invalid"
)
BUSINESS_CODE = f"P5-01-{FIXTURE_RUN_ID[:16].upper()}"
PROJECT_TEMPLATE_CODE = f"P501-{FIXTURE_RUN_ID[:16].upper()}"
POLICY_KEY = f"p5_01_runtime_{FIXTURE_RUN_ID}"
PROJECT_CREATE_KEY = f"{FIXTURE_PREFIX}-project-create"
DOCUMENT_CREATE_KEY = f"{FIXTURE_PREFIX}-document-create"
DOCUMENT_CHECK_OUT_KEY = f"{FIXTURE_PREFIX}-document-check-out"
DOCUMENT_REVISION_KEY = f"{FIXTURE_PREFIX}-document-revision"
DOCUMENT_CONTENT_KEY = f"{FIXTURE_PREFIX}-document-content"
DOCUMENT_CHECK_IN_KEY = f"{FIXTURE_PREFIX}-document-check-in"


@dataclass(frozen=True)
class BinaryHttpResult:
    status: int
    headers: Any
    content: bytes
    problem: dict[str, Any] | None


def fixture_request_id(key: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{FIXTURE_PREFIX}/request/{key}"))


def fixture_trace_id(key: str) -> str:
    return f"trace-{uuid5(NAMESPACE_URL, f'{FIXTURE_PREFIX}/trace/{key}').hex}"


def require_http_status(
    result: HttpResult,
    expected_statuses: set[int],
    operation: str,
) -> None:
    require(
        result.status in expected_statuses,
        (
            f"{operation} returned HTTP {result.status}"
            f"{sanitized_http_failure(result)}"
        ),
    )


def sanitized_http_failure(result: HttpResult) -> str:
    """Expose only bounded Frappe type/message diagnostics for a failed fixture."""

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
    return result


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
    return result


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
    require(
        result.status in {200, 201},
        f"Document workspace returned HTTP {result.status}",
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


def run_fresh(
    administrator,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
) -> dict[str, object]:
    verify_fresh_namespace(administrator, base_url)
    owner_created = create_disposable_user(
        administrator,
        base_url,
        OWNER_USER,
        fixture_password,
        csrf_token,
    )
    owner_cleanup_required = owner_created.status in {200, 201}
    try:
        validate_disposable_user(owner_created, OWNER_USER)
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
    require(
        relationship_filter.status == 200
        and [
            row["globalId"]
            for row in relationship_filter.body.get("items", [])
        ]
        == [document_id],
        "Typed reverse Document relationship query drifted",
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
            "verify_document_runtime_schema",
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
            and not arguments.replay_only
            and arguments.route_disable_probe is None,
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
    main()
