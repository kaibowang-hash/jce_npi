from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import verify_document_runtime as document_runtime
from verify_frappe_runtime import (
    HttpResult,
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
RUNTIME_MARKER = document_runtime.RUNTIME_MARKER
ACTOR_USER = document_runtime.BASELINE_USER
SOURCE_KIND = "npi.synthetic_runtime_project"
CREATE_KEY = f"p5-06-runtime-r1-{FIXTURE_RUN_ID}-create"


def fixture_uuid4(scope: str) -> str:
    """Return a deterministic synthetic UUID with exact RFC version/variant bits."""

    digest = bytearray(
        hashlib.sha256(
            (
                "https://npi-one.example.invalid/runtime/p5-06/"
                f"r1-{FIXTURE_RUN_ID}/{scope}"
            ).encode()
        ).digest()[:16]
    )
    digest[6] = (digest[6] & 0x0F) | 0x40
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(UUID(bytes=bytes(digest)))


def runtime_source_id(project_id: str) -> str:
    """Mirror the closed disposable adapter's server-owned source identity."""

    digest = bytearray(
        hashlib.sha256(f"{RUNTIME_MARKER}\0{project_id}".encode("utf-8")).digest()[:16]
    )
    digest[6] = (digest[6] & 0x0F) | 0x40
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(UUID(bytes=bytes(digest)))


REGISTRY_ID = fixture_uuid4("registry")
MAPPING_ID = fixture_uuid4("mapping-1")
PRINT_FORMAT_NAME = f"P506 Runtime {FIXTURE_RUN_ID[:12]}"
CONTROLLED_PRINT_DOCTYPES = (
    "NPI Controlled Print Registry",
    "NPI Controlled Print Registry Version",
    "NPI Controlled Print Snapshot",
    "NPI Controlled Print Output",
    "NPI Controlled Print Access Event",
    "NPI Controlled Print Command Idempotency",
)
_HASH = re.compile(r"^[a-f0-9]{64}$")
_TRACE_PATTERN = re.compile(r"^trace-[a-f0-9]{32}$")
_TYPE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,127}$")
_CREATE_DIAGNOSTIC_HEADER = "X-NPI-Diagnostic-Scope"
_CREATE_DIAGNOSTIC_SCOPE = "p506-controlled-print-create-v1"
_DIAGNOSTIC_LOG_TAIL_LIMIT = 64 * 1024
_CREATE_SERVER_DIAGNOSTIC_CODES = frozenset(
    {
        "P506_CREATE_COMMAND_CONTEXT",
        "P506_CREATE_INPUT_PARSE",
        "P506_CREATE_PROJECT_LOCK",
        "P506_CREATE_PAYLOAD_HASH",
        "P506_CREATE_IDEMPOTENCY_REPLAY",
        "P506_CREATE_SOURCE_RESOLVE",
        "P506_CREATE_MAPPING_RESOLVE",
        "P506_CREATE_AUTHORITY",
        "P506_CREATE_SNAPSHOT_BUILD",
        "P506_CREATE_PDF_RENDER",
        "P506_CREATE_TRANSACTION_SCOPE",
        "P506_CREATE_RECEIPT_INSERT",
        "P506_CREATE_SNAPSHOT_INSERT",
        "P506_CREATE_FILE_SAVE",
        "P506_CREATE_OUTPUT_INSERT",
        "P506_CREATE_ACCESS_EVENT_INSERT",
        "P506_CREATE_AUDIT_APPEND",
        "P506_CREATE_RESPONSE_BUILD",
        "P506_CREATE_RECEIPT_SEAL",
        "P506_CREATE_API_RESPONSE",
    }
)
_CAPABILITY_KEYS = {
    "available",
    "sourceKind",
    "sourceGlobalId",
    "sourceVersion",
    "language",
    "deliveryMode",
    "copyState",
    "registry",
    "permissions",
}
_REGISTRY_KEYS = {
    "globalId",
    "registryGlobalId",
    "version",
    "snapshotHash",
    "templateSha256",
}
_SNAPSHOT_KEYS = {
    "globalId",
    "version",
    "source",
    "registry",
    "language",
    "deliveryMode",
    "copyState",
    "watermarkSource",
    "actorUserId",
    "printedAt",
    "snapshotHash",
    "verificationPayload",
    "output",
}


@dataclass(frozen=True, slots=True)
class BinaryResult:
    status: int
    headers: Any
    content: bytes
    problem: dict[str, Any] | None = None


def _site_marker() -> object:
    import frappe

    configuration = getattr(frappe, "conf", None)
    return (
        configuration.get("npi_runtime_disposable_marker")
        if hasattr(configuration, "get")
        else None
    )


def _require_disposable_site() -> None:
    require(
        _site_marker() == RUNTIME_MARKER,
        "P5-06 fixtures require the exact disposable runtime Site marker",
    )


def verify_controlled_print_schema(**_kwargs: object) -> dict[str, object]:
    import frappe

    _require_disposable_site()
    missing = [
        name
        for name in CONTROLLED_PRINT_DOCTYPES
        if not frappe.db.exists("DocType", name)
    ]
    require(not missing, f"P5-06 controlled-print schema is missing: {missing}")
    from npi_core.controlled_print.source_registry import (
        default_controlled_print_source_registry,
    )

    registry = default_controlled_print_source_registry()
    require(
        registry.source_object_types == (SOURCE_KIND,),
        "Disposable P5-06 source adapter scope drifted",
    )
    return {
        "doctypeCount": len(CONTROLLED_PRINT_DOCTYPES),
        "runtimeMarker": RUNTIME_MARKER,
        "sourceKinds": list(registry.source_object_types),
    }


def provision_controlled_print_mapping(
    *,
    project_id: str,
    actor_user_id: str,
) -> dict[str, object]:
    import frappe

    from npi_core.controlled_print.domain import (
        ControlledPrintRegistryVersion,
        PrintCopyState,
        PrintDeliveryMode,
        PrintRegistryState,
    )
    from npi_core.controlled_print.frappe_validation import (
        controlled_print_registry_write,
    )

    _require_disposable_site()
    require(actor_user_id == ACTOR_USER, "P5-06 fixture actor identity drifted")
    project = frappe.get_doc("NPI Engineering Project", project_id)
    require(str(project.global_id) == project_id, "P5-06 fixture Project drifted")
    template = (
        "<h1>{{ doc.businessCode }}</h1>"
        "<p>{{ doc.title }}</p>"
        "<p>{{ doc.projectType }} / {{ doc.lifecycleState }}</p>"
        "<p>{{ controlledPrint.snapshotHash }}</p>"
    )
    now = datetime.now(UTC)
    mapping = ControlledPrintRegistryVersion(
        global_id=UUID(MAPPING_ID),
        registry_global_id=UUID(REGISTRY_ID),
        tenant_id=str(project.tenant_id),
        mapping_key=f"p5_06_runtime_{FIXTURE_RUN_ID}",
        mapping_version=1,
        title="Synthetic P5-06 controlled output",
        state=PrintRegistryState.PUBLISHED,
        source_object_type=SOURCE_KIND,
        project_type_key=str(project.project_type),
        gate_key=None,
        source_state=str(project.lifecycle_state),
        language="en",
        delivery_mode=PrintDeliveryMode.CONTROLLED_PDF,
        copy_state=PrintCopyState.NOT_NUMBERED,
        print_format_name=PRINT_FORMAT_NAME,
        template_content=template,
        template_sha256=hashlib.sha256(template.encode()).hexdigest(),
        watermark_source="Synthetic controlled runtime snapshot",
        printer_user_ids=(actor_user_id,),
        effective_from=now - timedelta(days=1),
        published_at=now - timedelta(days=1),
    )
    require(
        not frappe.db.exists("Print Format", PRINT_FORMAT_NAME),
        "P5-06 Print Format already exists",
    )
    frappe.get_doc(
        {
            "doctype": "Print Format",
            "name": PRINT_FORMAT_NAME,
            "doc_type": "NPI Engineering Project",
            "module": "NPI Core",
            "standard": "No",
            "custom_format": 1,
            "disabled": 0,
            "print_format_type": "Jinja",
            "raw_printing": 0,
            "html": template,
        }
    ).insert(ignore_permissions=True)
    with controlled_print_registry_write():
        frappe.get_doc(
            {
                "doctype": "NPI Controlled Print Registry",
                "global_id": REGISTRY_ID,
                "tenant_id": str(project.tenant_id),
                "registry_key": f"p5_06_runtime_{FIXTURE_RUN_ID}",
                "title": "Synthetic P5-06 controlled print registry",
                "enabled": 1,
                "optimistic_version": 1,
            }
        ).insert()
        frappe.get_doc(
            {
                "doctype": "NPI Controlled Print Registry Version",
                "global_id": MAPPING_ID,
                "print_registry": REGISTRY_ID,
                "tenant_id": str(project.tenant_id),
                "registry_global_id": REGISTRY_ID,
                "mapping_key": mapping.mapping_key,
                "mapping_version": 1,
                "title": mapping.title,
                "publication_state": "published",
                "source_object_type": SOURCE_KIND,
                "project_type_key": str(project.project_type),
                "source_state": str(project.lifecycle_state),
                "language": "en",
                "delivery_mode": "controlled_pdf",
                "copy_state": "not_numbered",
                "print_format_name": PRINT_FORMAT_NAME,
                "template_content": template,
                "template_sha256": mapping.template_sha256,
                "watermark_source": mapping.watermark_source,
                "printer_user_ids": json.dumps([actor_user_id]),
                "effective_from": mapping.effective_from.isoformat(),
                "mapping_snapshot": json.dumps(mapping.snapshot_payload()),
                "snapshot_hash": mapping.snapshot_hash,
                "published_at": mapping.published_at.isoformat(),
                "optimistic_version": 1,
            }
        ).insert()
    frappe.db.commit()
    return {
        "mappingGlobalId": MAPPING_ID,
        "registryGlobalId": REGISTRY_ID,
        "snapshotHash": mapping.snapshot_hash,
        "templateSha256": mapping.template_sha256,
        "printFormatName": PRINT_FORMAT_NAME,
        "sourceVersion": int(project.optimistic_version),
    }


def mutate_controlled_print_inputs(*, project_id: str) -> dict[str, object]:
    import frappe

    _require_disposable_site()
    project = frappe.get_doc("NPI Engineering Project", project_id)
    previous_version = int(project.optimistic_version)
    previous_title = str(project.title)
    mutated_title = f"{previous_title} [mutated after controlled print]"
    frappe.db.set_value(
        "NPI Engineering Project",
        project_id,
        {"title": mutated_title, "optimistic_version": previous_version + 1},
        update_modified=True,
    )
    print_format = frappe.get_doc("Print Format", PRINT_FORMAT_NAME)
    print_format.html = "<h1>MUTATED AFTER CONTROLLED PRINT</h1>"
    print_format.save(ignore_permissions=True)
    frappe.db.commit()
    return {
        "previousSourceVersion": previous_version,
        "currentSourceVersion": previous_version + 1,
        "sourceMutated": True,
        "printFormatMutated": True,
    }


def retained_controlled_print_truth(**_kwargs: object) -> dict[str, object]:
    import frappe

    _require_disposable_site()
    receipts = frappe.get_all(
        "NPI Controlled Print Command Idempotency",
        filters={"actor_user_id": ACTOR_USER, "sealed": 1},
        fields=["snapshot_global_id", "response_payload", "response_hash"],
    )
    require(len(receipts) == 1, "P5-06 retained receipt cardinality drifted")
    receipt = receipts[0]
    response = json.loads(str(receipt.response_payload))
    require(isinstance(response, dict), "P5-06 retained response is invalid")
    snapshot_id = str(receipt.snapshot_global_id)
    output = frappe.db.get_value(
        "NPI Controlled Print Output",
        {"snapshot_global_id": snapshot_id},
        ["sha256", "size_bytes", "frappe_file_id"],
        as_dict=True,
    )
    require(output is not None, "P5-06 retained output is unavailable")
    file_document = frappe.get_doc("File", str(output.frappe_file_id))
    content = file_document.get_content()
    if isinstance(content, str):
        content = content.encode()
    require(
        isinstance(content, bytes)
        and hashlib.sha256(content).hexdigest() == str(output.sha256)
        and len(content) == int(output.size_bytes),
        "P5-06 retained file integrity drifted",
    )
    return {
        "response": response,
        "responseHash": str(receipt.response_hash),
        "outputHash": str(output.sha256),
        "outputSize": int(output.size_bytes),
        "snapshotCount": frappe.db.count("NPI Controlled Print Snapshot"),
        "outputCount": frappe.db.count("NPI Controlled Print Output"),
        "receiptCount": len(receipts),
        "accessEventCount": frappe.db.count("NPI Controlled Print Access Event"),
    }


def run_bench_fixture(method: str, kwargs: dict[str, object]) -> dict[str, Any]:
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
        f"P5-06 Bench fixture {method} failed: {completed.stderr[-2000:]}",
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    require(bool(lines), f"P5-06 Bench fixture {method} was silent")
    result = json.loads(lines[-1])
    require(isinstance(result, dict), "P5-06 Bench fixture result is invalid")
    return result


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    import frappe

    fixtures = {
        "verify_controlled_print_schema": verify_controlled_print_schema,
        "provision_controlled_print_mapping": provision_controlled_print_mapping,
        "mutate_controlled_print_inputs": mutate_controlled_print_inputs,
        "retained_controlled_print_truth": retained_controlled_print_truth,
    }
    require(method in fixtures, "P5-06 Bench fixture is unavailable")
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


def controlled_print_path(project_id: str, snapshot_id: str | None = None) -> str:
    base = f"/api/npi/v1/projects/{project_id}/controlled-prints"
    return base if snapshot_id is None else f"{base}/{snapshot_id}"


def capability_path(project_id: str, source_version: int) -> str:
    query = urllib.parse.urlencode(
        {
            "sourceKind": SOURCE_KIND,
            "sourceGlobalId": runtime_source_id(project_id),
            "sourceVersion": source_version,
            "language": "en",
        }
    )
    return f"/api/npi/v1/projects/{project_id}/controlled-print/capability?{query}"


def api_request(
    opener,
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    csrf_token: str | None = None,
    idempotency_key: str | None = None,
    create_diagnostic: bool = False,
    correlation_label: str,
) -> HttpResult:
    headers = (
        document_runtime.command_headers(csrf_token, idempotency_key)
        if idempotency_key is not None
        else document_runtime.query_headers(correlation_label)
    )
    if create_diagnostic:
        if idempotency_key is None or method != "POST":
            raise ValueError(
                "The controlled-print create diagnostic requires one command request"
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
        result.headers.get("Cache-Control") == "private, no-store",
        "P5-06 cache boundary drifted",
    )
    require(
        result.headers.get("X-Request-ID") == headers["X-Request-ID"],
        "P5-06 request identity drifted",
    )
    return HttpResult(
        result.status,
        result.headers,
        result.body,
        request_id=headers["X-Request-ID"],
        trace_id=headers["X-Trace-ID"],
    )


def download_request(
    opener,
    base_url: str,
    path: str,
    *,
    correlation_label: str,
) -> BinaryResult:
    headers = document_runtime.query_headers(correlation_label)
    request = urllib.request.Request(f"{base_url}{path}", headers=headers, method="GET")
    try:
        with opener.open(request, timeout=20) as response:
            content = response.read()
            result = BinaryResult(response.status, response.headers, content)
    except urllib.error.HTTPError as error:
        raw = error.read()
        problem = json.loads(raw.decode())
        result = BinaryResult(error.code, error.headers, raw, problem)
    require(
        result.headers.get("Cache-Control") == "private, no-store",
        "P5-06 binary cache boundary drifted",
    )
    require(
        result.headers.get("X-Request-ID") == headers["X-Request-ID"],
        "P5-06 binary request identity drifted",
    )
    return result


def create_payload(
    project_id: str,
    source_version: int,
    *,
    language: str = "en",
) -> dict[str, object]:
    return {
        "sourceKind": SOURCE_KIND,
        "sourceGlobalId": runtime_source_id(project_id),
        "sourceVersion": source_version,
        "language": language,
    }


def assert_capability(value: object, project_id: str, source_version: int) -> None:
    require(
        isinstance(value, dict) and set(value) == _CAPABILITY_KEYS,
        "P5-06 capability shape drifted",
    )
    registry = value.get("registry")
    require(
        value.get("available") is True
        and value.get("sourceKind") == SOURCE_KIND
        and value.get("sourceGlobalId") == runtime_source_id(project_id)
        and value.get("sourceVersion") == source_version
        and value.get("language") == "en"
        and value.get("deliveryMode") == "controlled_pdf"
        and value.get("copyState") == "not_numbered"
        and value.get("permissions") == {"create": True, "download": True}
        and isinstance(registry, dict)
        and set(registry) == _REGISTRY_KEYS
        and registry.get("globalId") == MAPPING_ID
        and registry.get("registryGlobalId") == REGISTRY_ID
        and _HASH.fullmatch(str(registry.get("snapshotHash"))) is not None
        and _HASH.fullmatch(str(registry.get("templateSha256"))) is not None,
        "P5-06 exact capability truth drifted",
    )
    require(
        "printFormat" not in json.dumps(value),
        "P5-06 capability exposed Print Format identity",
    )


def assert_snapshot(value: object, project_id: str, source_version: int) -> None:
    require(
        isinstance(value, dict) and set(value) == _SNAPSHOT_KEYS,
        "P5-06 snapshot shape drifted",
    )
    source = value.get("source")
    registry = value.get("registry")
    output = value.get("output")
    require(
        isinstance(source, dict)
        and source.get("sourceKind") == SOURCE_KIND
        and source.get("sourceGlobalId") == runtime_source_id(project_id)
        and source.get("sourceVersion") == source_version
        and _HASH.fullmatch(str(source.get("sourceSnapshotHash"))) is not None
        and isinstance(registry, dict)
        and set(registry) == _REGISTRY_KEYS
        and isinstance(output, dict)
        and output.get("mimeType") == "application/pdf"
        and int(output.get("sizeBytes", 0)) > 0
        and _HASH.fullmatch(str(output.get("sha256"))) is not None
        and value.get("actorUserId") == ACTOR_USER
        and value.get("language") == "en"
        and value.get("deliveryMode") == "controlled_pdf"
        and value.get("copyState") == "not_numbered"
        and _HASH.fullmatch(str(value.get("snapshotHash"))) is not None,
        "P5-06 exact retained snapshot truth drifted",
    )
    serialized = json.dumps(value)
    require(
        "fileUrl" not in serialized and "templateContent" not in serialized,
        "P5-06 snapshot exposed private implementation data",
    )


def http_failure_evidence(result: HttpResult) -> str:
    code = result.body.get("code") if isinstance(result.body, dict) else None
    errors = result.body.get("errors") if isinstance(result.body, dict) else None
    paths: list[str] = []
    if isinstance(errors, list):
        paths = sorted(
            {
                str(error.get("path"))
                for error in errors
                if isinstance(error, dict) and isinstance(error.get("path"), str)
            }
        )
    return f"HTTP {result.status}; code={code!s}; paths={','.join(paths) or '-'}"


def sanitized_create_server_diagnostic(
    trace_id: str | None,
) -> tuple[str, str, str] | None:
    """Read only one allowlisted P5-06 server record for this exact trace."""

    if not isinstance(trace_id, str) or _TRACE_PATTERN.fullmatch(trace_id) is None:
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
                    record, _end = decoder.raw_decode(line[start:])
                except (TypeError, ValueError):
                    continue
                if not isinstance(record, dict) or set(record) != {
                    "code",
                    "exceptionType",
                    "traceId",
                }:
                    continue
                code = record.get("code")
                exception_type = record.get("exceptionType")
                if (
                    record.get("traceId") == trace_id
                    and isinstance(code, str)
                    and code in _CREATE_SERVER_DIAGNOSTIC_CODES
                    and isinstance(exception_type, str)
                    and _TYPE_PATTERN.fullmatch(exception_type) is not None
                ):
                    return exception_type, code, trace_id
    return None


def run_fresh(base_url: str, administrator, fixture_password: str) -> dict[str, object]:
    schema = run_bench_fixture("verify_controlled_print_schema", {})
    project_id, source_version = document_runtime.fixture_project(administrator, base_url)
    guest = api_request(
        urllib.request.build_opener(),
        base_url,
        capability_path(project_id, source_version),
        correlation_label="p506-guest",
    )
    require(guest.status == 401, "P5-06 guest capability did not fail closed")
    validate_problem(guest, 401, "AUTHENTICATION_REQUIRED")
    mapping = run_bench_fixture(
        "provision_controlled_print_mapping",
        {"project_id": project_id, "actor_user_id": ACTOR_USER},
    )
    require(mapping.get("sourceVersion") == source_version, "P5-06 mapping source version drifted")
    actor = login(base_url, ACTOR_USER, fixture_password)
    actor_csrf = bootstrap_csrf(actor, base_url, ACTOR_USER)
    capability = api_request(
        actor,
        base_url,
        capability_path(project_id, source_version),
        correlation_label="p506-capability",
    )
    require(
        capability.status == 200,
        f"P5-06 capability failed: {http_failure_evidence(capability)}",
    )
    assert_capability(capability.body, project_id, source_version)
    missing_csrf = api_request(
        actor,
        base_url,
        controlled_print_path(project_id),
        method="POST",
        payload=create_payload(project_id, source_version),
        idempotency_key=f"{CREATE_KEY}-missing-csrf",
        correlation_label="p506-missing-csrf",
    )
    require(missing_csrf.status == 403, "P5-06 missing CSRF did not fail closed")
    validate_problem(missing_csrf, 403, "CSRF_TOKEN_INVALID")
    created = api_request(
        actor,
        base_url,
        controlled_print_path(project_id),
        method="POST",
        payload=create_payload(project_id, source_version),
        csrf_token=actor_csrf,
        idempotency_key=CREATE_KEY,
        create_diagnostic=True,
        correlation_label="p506-create",
    )
    if created.status != 201:
        diagnostic = sanitized_create_server_diagnostic(created.trace_id)
        detail = ""
        if diagnostic is not None:
            exception_type, code, trace_id = diagnostic
            detail = (
                f" [diagnostic_code={code}; exc_type={exception_type}; "
                f"trace_id={trace_id}]"
            )
        require(
            False,
            f"P5-06 create failed: {http_failure_evidence(created)}{detail}",
        )
    require(
        created.headers.get("Idempotency-Replayed") == "false",
        "P5-06 create replay header drifted",
    )
    assert_snapshot(created.body, project_id, source_version)
    replay = api_request(
        actor,
        base_url,
        controlled_print_path(project_id),
        method="POST",
        payload=create_payload(project_id, source_version),
        csrf_token=actor_csrf,
        idempotency_key=CREATE_KEY,
        correlation_label="p506-replay",
    )
    require(
        replay.status == 201 and replay.body == created.body,
        "P5-06 same-process replay drifted",
    )
    require(replay.headers.get("Idempotency-Replayed") == "true", "P5-06 replay header drifted")
    conflict = api_request(
        actor,
        base_url,
        controlled_print_path(project_id),
        method="POST",
        payload=create_payload(project_id, source_version, language="zh"),
        csrf_token=actor_csrf,
        idempotency_key=CREATE_KEY,
        correlation_label="p506-conflict",
    )
    require(conflict.status == 409, "P5-06 idempotency conflict did not fail closed")
    snapshot_id = str(created.body["globalId"])
    detail_path = controlled_print_path(project_id, snapshot_id)
    detail = api_request(
        actor,
        base_url,
        detail_path,
        correlation_label="p506-detail",
    )
    require(detail.status == 200 and detail.body == created.body, "P5-06 detail drifted")
    download = download_request(
        actor,
        base_url,
        f"{detail_path}/content",
        correlation_label="p506-download",
    )
    output = created.body["output"]
    require(
        download.status == 200
        and download.content.startswith(b"%PDF-")
        and len(download.content) == output["sizeBytes"]
        and hashlib.sha256(download.content).hexdigest() == output["sha256"]
        and download.headers.get_content_type() == "application/pdf"
        and download.headers.get("X-NPI-Snapshot-Hash") == created.body["snapshotHash"]
        and download.headers.get("X-NPI-Output-Hash") == output["sha256"],
        "P5-06 retained PDF response drifted",
    )
    mutation = run_bench_fixture("mutate_controlled_print_inputs", {"project_id": project_id})
    require(
        mutation.get("previousSourceVersion") == source_version,
        "P5-06 mutation precondition drifted",
    )
    retained = run_bench_fixture("retained_controlled_print_truth", {})
    require(
        retained.get("response") == created.body
        and retained.get("outputHash") == output["sha256"]
        and retained.get("snapshotCount") == 1
        and retained.get("outputCount") == 1
        and retained.get("receiptCount") == 1
        and int(retained.get("accessEventCount", 0)) >= 1,
        "P5-06 persisted truth drifted after source/template mutation",
    )
    post_mutation_detail = api_request(
        actor,
        base_url,
        detail_path,
        correlation_label="p506-mutated-detail",
    )
    require(
        post_mutation_detail.status == 200
        and post_mutation_detail.body == created.body,
        "P5-06 retained detail followed live mutation",
    )
    post_mutation_download = download_request(
        actor,
        base_url,
        f"{detail_path}/content",
        correlation_label="p506-mutated-download",
    )
    require(
        post_mutation_download.status == 200
        and post_mutation_download.content == download.content,
        "P5-06 retained bytes followed live mutation",
    )
    return {
        "schema": schema,
        "projectId": project_id,
        "sourceVersion": source_version,
        "currentSourceVersion": mutation["currentSourceVersion"],
        "snapshotId": snapshot_id,
        "snapshotHash": created.body["snapshotHash"],
        "outputHash": output["sha256"],
        "outputSize": output["sizeBytes"],
        "sourceMutationResistant": True,
        "templateMutationResistant": True,
    }


def route_disable_probe(
    base_url: str,
    fixture_password: str,
    expected_mode: str,
) -> dict[str, object]:
    administrator = login(
        base_url,
        "Administrator",
        secret_from_environment("NPI_RUNTIME_ADMINISTRATOR_PASSWORD"),
    )
    project_id, current_version = document_runtime.fixture_project(administrator, base_url)
    actor = login(base_url, ACTOR_USER, fixture_password)
    capability = api_request(
        actor,
        base_url,
        capability_path(project_id, current_version),
        correlation_label=f"p506-route-{expected_mode}",
    )
    expected_status = 503 if expected_mode == "disabled" else 200
    require(capability.status == expected_status, f"P5-06 {expected_mode} route probe drifted")
    if expected_mode == "disabled":
        validate_problem(capability, 503, "CONTROLLED_PRINT_ROUTES_DISABLED")
    else:
        assert_capability(capability.body, project_id, current_version)
    cockpit = api_request(
        actor,
        base_url,
        f"/api/npi/v1/projects/{project_id}/cockpit",
        correlation_label=f"p506-predecessor-{expected_mode}",
    )
    require(cockpit.status == 200, "P5-06 route switch disabled a predecessor route")
    return {"routeMode": expected_mode, "predecessorRouteRetained": True}


def run_replay_only(base_url: str, administrator, fixture_password: str) -> dict[str, object]:
    project_id, current_version = document_runtime.fixture_project(administrator, base_url)
    source_version = current_version - 1
    retained = run_bench_fixture("retained_controlled_print_truth", {})
    expected = retained["response"]
    actor = login(base_url, ACTOR_USER, fixture_password)
    actor_csrf = bootstrap_csrf(actor, base_url, ACTOR_USER)
    replay = api_request(
        actor,
        base_url,
        controlled_print_path(project_id),
        method="POST",
        payload=create_payload(project_id, source_version),
        csrf_token=actor_csrf,
        idempotency_key=CREATE_KEY,
        correlation_label="p506-cross-process-replay",
    )
    require(
        replay.status == 201
        and replay.headers.get("Idempotency-Replayed") == "true"
        and replay.body == expected,
        "P5-06 cross-process replay drifted after live source mutation",
    )
    snapshot_id = str(expected["globalId"])
    content = download_request(
        actor,
        base_url,
        f"{controlled_print_path(project_id, snapshot_id)}/content",
        correlation_label="p506-cross-process-content",
    )
    require(
        content.status == 200
        and hashlib.sha256(content.content).hexdigest() == retained["outputHash"]
        and len(content.content) == retained["outputSize"],
        "P5-06 cross-process retained bytes drifted",
    )
    return {
        "projectId": project_id,
        "snapshotId": snapshot_id,
        "crossProcessReplay": True,
        "retainedOutputHash": retained["outputHash"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url")
    parser.add_argument("--replay-only", action="store_true")
    parser.add_argument("--route-disable-probe", choices=("disabled", "recovered"))
    parser.add_argument("--bench-fixture")
    parser.add_argument("--fixture-kwargs")
    arguments = parser.parse_args()
    if arguments.bench_fixture is not None:
        require(
            arguments.base_url is None and arguments.fixture_kwargs is not None,
            "P5-06 fixture invocation drifted",
        )
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "P5-06 fixture arguments are invalid")
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return
    require(
        arguments.base_url is not None
        and os.environ.get(document_runtime.FIXTURE_RUN_ID_ENV) is not None
        and not (arguments.replay_only and arguments.route_disable_probe),
        "P5-06 runtime invocation is incomplete",
    )
    administrator_password = secret_from_environment("NPI_RUNTIME_ADMINISTRATOR_PASSWORD")
    fixture_password = secret_from_environment("NPI_RUNTIME_FIXTURE_PASSWORD")
    base_url = validate_local_fixture_inputs(arguments.base_url, "Administrator", ACTOR_USER)
    if arguments.route_disable_probe is not None:
        result = route_disable_probe(base_url, fixture_password, arguments.route_disable_probe)
    else:
        administrator = login(base_url, "Administrator", administrator_password)
        result = (
            run_replay_only(base_url, administrator, fixture_password)
            if arguments.replay_only
            else run_fresh(base_url, administrator, fixture_password)
        )
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
