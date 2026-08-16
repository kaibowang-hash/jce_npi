from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import subprocess
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

import verify_document_runtime as document_runtime
import verify_project_runtime as project_runtime
from verify_frappe_runtime import (
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
TENANT_ID = document_runtime.TENANT_ID
FIXTURE_RUN_ID = document_runtime.FIXTURE_RUN_ID
ACTOR_USER = os.environ.get("NPI_P8_02_RUNTIME_ACTOR", "")
OWNER_USER = os.environ.get("NPI_P8_02_RUNTIME_OWNER", "")
TEMPLATE_ID = os.environ.get("NPI_P8_02_RUNTIME_TEMPLATE_ID", "")
TEMPLATE_VERSION_KEY = f"{TEMPLATE_ID}:1"
WEBHOOK_PATH = "/api/npi/v1/integration/erpnext/project-source-events"
NAMESPACE = UUID("be05ea93-4d1a-4ac0-a148-c3e7a8a80202")


def deterministic_uuid(label: str) -> UUID:
    return uuid5(NAMESPACE, f"{FIXTURE_RUN_ID}:{label}")


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def source_event(
    *,
    label: str,
    source_id: str,
    version: int,
    title: str,
) -> dict[str, object]:
    now = datetime.now(UTC).replace(microsecond=0)
    payload = {
        "schema_version": 1,
        "submission_state": "submitted",
        "title": title,
        "target_sop": "2026-12-31",
        "source_modified_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return {
        "event_id": str(deterministic_uuid(f"event:{label}")),
        "event_type": "erpnext.quotation.submitted",
        "event_version": 1,
        "occurred_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_system": "ERPNEXT",
        "target_system": "NPI_ONE",
        "global_id": str(deterministic_uuid(f"source-global:{label}")),
        "object_type": "Quotation",
        "source_object_id": source_id,
        "object_version": version,
        "correlation_id": str(deterministic_uuid(f"correlation:{source_id}")),
        "trace_id": f"trace-p802-{FIXTURE_RUN_ID[:12]}-{label}",
        "actor": {"type": "service", "id": "erpnext-disposable-runtime"},
        "payload_hash": canonical_hash(payload),
        "payload": payload,
        "sensitivity": "confidential",
    }


def signed_headers(
    raw_body: bytes,
    *,
    key_id: str,
    secret: str,
    request_label: str,
    timestamp: int | None = None,
) -> dict[str, str]:
    request_id = str(deterministic_uuid(f"request:{request_label}"))
    unix_seconds = int(time.time()) if timestamp is None else timestamp
    prefix = (
        f"npi-webhook-v1\nPOST\n{WEBHOOK_PATH}\n{key_id}\n"
        f"{unix_seconds}\n{request_id}\n"
    ).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), prefix + raw_body, hashlib.sha256)
    return {
        "Content-Type": "application/json",
        "X-NPI-Key-ID": key_id,
        "X-NPI-Timestamp": str(unix_seconds),
        "X-NPI-Signature": f"v1={signature.hexdigest()}",
        "X-Request-ID": request_id,
    }


def send_event(
    base_url: str,
    event: dict[str, object],
    *,
    key_id: str,
    secret: str,
    request_label: str,
    timestamp: int | None = None,
    corrupt_signature: bool = False,
):
    raw = json.dumps(
        event,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=False,
    )
    headers = signed_headers(
        raw.encode("utf-8"),
        key_id=key_id,
        secret=secret,
        request_label=request_label,
        timestamp=timestamp,
    )
    if corrupt_signature:
        headers["X-NPI-Signature"] = "v1=" + "0" * 64
    return request(
        urllib.request.build_opener(),
        base_url,
        WEBHOOK_PATH,
        method="POST",
        raw_payload=raw,
        request_headers=headers,
    )


def ensure_runtime_users(
    administrator,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
) -> None:
    actor = project_runtime.get_resource(administrator, base_url, "User", ACTOR_USER)
    if actor.status == 404:
        created_actor = project_runtime.create_resource(
            administrator,
            base_url,
            "User",
            {
                "email": ACTOR_USER,
                "enabled": 1,
                "first_name": "P8 Runtime",
                "last_name": "Inbound Actor",
                "language": "en",
                "new_password": fixture_password,
                "send_welcome_email": 0,
                "user_type": "System User",
                "roles": [{"role": "NPI API User"}],
            },
            csrf_token,
        )
        require(
            created_actor.status in {200, 201},
            "P8-02 runtime actor could not be created",
        )
        actor = project_runtime.get_resource(
            administrator, base_url, "User", ACTOR_USER
        )
    require(actor.status == 200, "P8-02 runtime actor is unavailable")
    actor_value = actor.body.get("data", {})
    actor_roles = {
        row.get("role")
        for row in actor_value.get("roles", [])
        if isinstance(row, dict)
    }
    require(
        actor_value.get("name") == ACTOR_USER
        and actor_value.get("enabled") == 1
        and actor_value.get("user_type") == "System User"
        and "NPI API User" in actor_roles
        and "System Manager" not in actor_roles,
        "P8-02 runtime actor authority drifted",
    )

    owner = project_runtime.get_resource(administrator, base_url, "User", OWNER_USER)
    if owner.status == 404:
        created_owner = project_runtime.create_resource(
            administrator,
            base_url,
            "User",
            {
                "email": OWNER_USER,
                "enabled": 1,
                "first_name": "P8 Runtime",
                "last_name": "Project Owner",
                "language": "en",
                "new_password": fixture_password,
                "send_welcome_email": 0,
                "user_type": "Website User",
            },
            csrf_token,
        )
        require(
            created_owner.status in {200, 201},
            "P8-02 runtime owner could not be created",
        )
        owner = project_runtime.get_resource(
            administrator, base_url, "User", OWNER_USER
        )
    require(
        owner.status == 200
        and owner.body.get("data", {}).get("enabled") == 1,
        "P8-02 runtime owner is unavailable",
    )


def ensure_runtime_template(administrator, base_url: str, csrf_token: str) -> None:
    template = project_runtime.get_resource(
        administrator, base_url, "NPI Project Template", TEMPLATE_ID
    )
    if template.status == 404:
        template = project_runtime.create_resource(
            administrator,
            base_url,
            "NPI Project Template",
            {
                "global_id": TEMPLATE_ID,
                "template_code": f"P802-{FIXTURE_RUN_ID[:12]}",
                "title": "Synthetic inbound Project runtime template",
                "enabled": 1,
            },
            csrf_token,
        )
    require(template.status in {200, 201}, "P8-02 runtime template is unavailable")
    version = project_runtime.get_resource(
        administrator,
        base_url,
        "NPI Project Template Version",
        TEMPLATE_VERSION_KEY,
    )
    if version.status == 404:
        version = project_runtime.create_resource(
            administrator,
            base_url,
            "NPI Project Template Version",
            {
                "project_template": TEMPLATE_ID,
                "template_version": 1,
                "title": "Synthetic inbound Project runtime template version",
                "publication_state": "published",
                "applicable_project_types": ["new_tool"],
                "reference_rules": [],
                "gates": [
                    {"gate_key": "G0", "title": "Synthetic feasibility", "sequence": 1},
                    {"gate_key": "G1", "title": "Synthetic authorization", "sequence": 2},
                ],
            },
            csrf_token,
        )
    value = version.body.get("data", {})
    require(
        version.status in {200, 201}
        and value.get("publication_state") == "published"
        and value.get("optimistic_version") == 1
        and value.get("reference_rules") == [],
        "P8-02 runtime template version drifted",
    )


def run_bench_fixture(method: str, kwargs: dict[str, object]) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT)
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
        f"P8-02 Bench fixture {method} failed: {completed.stderr[-2000:]}",
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    require(bool(lines), f"P8-02 Bench fixture {method} was silent")
    result = json.loads(lines[-1])
    require(isinstance(result, dict), "P8-02 Bench fixture result is invalid")
    return result


def _runtime_context(source_id: str, receipt_ids: tuple[str, ...]) -> dict[str, object]:
    import frappe

    inbox_rows = frappe.get_all(
        "NPI Inbox Message",
        filters={"source_object_id": source_id},
        fields=[
            "name",
            "state",
            "disposition",
            "attempt_count",
            "project_global_id",
        ],
        order_by="object_version asc, name asc",
        limit_page_length=10,
    )
    require(
        {str(row.name) for row in inbox_rows}.issuperset(receipt_ids),
        "P8-02 retained Inbox receipts are unavailable",
    )
    binding_rows = frappe.get_all(
        "NPI Project Source Binding",
        filters={"source_object_id": source_id},
        fields=[
            "source_key_hash",
            "stream_state",
            "bound_project_global_id",
            "bound_inbox_message",
            "bound_version",
            "optimistic_version",
        ],
        limit_page_length=2,
    )
    require(len(binding_rows) == 1, "P8-02 source binding cardinality drifted")
    binding = binding_rows[0]
    project_id = str(binding.bound_project_global_id or "")
    project_rows = frappe.get_all(
        "NPI Engineering Project",
        filters={"business_code": source_id, "tenant_id": TENANT_ID},
        fields=[
            "global_id",
            "lifecycle_state",
            "source_system",
            "optimistic_version",
            "owner_user_id",
        ],
        limit_page_length=2,
    )
    gates = (
        frappe.get_all(
            "NPI Gate Shell",
            filters={"project_global_id": project_id},
            fields=["global_id", "state", "optimistic_version", "sequence"],
            order_by="sequence asc",
            limit_page_length=10,
        )
        if project_id
        else []
    )
    audits = frappe.db.count(
        "NPI Audit Event",
        {"operation": ["in", ["project.create", "inbound_project.complete"]]},
    )
    canonical = json.dumps(
        {
            "binding": dict(binding),
            "gates": [dict(row) for row in gates],
            "inbox": [dict(row) for row in inbox_rows],
            "projects": [dict(row) for row in project_rows],
        },
        default=str,
        separators=(",", ":"),
        sort_keys=True,
    )
    return {
        "auditCount": audits,
        "binding": dict(binding),
        "digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "gates": [dict(row) for row in gates],
        "inbox": [dict(row) for row in inbox_rows],
        "projects": [dict(row) for row in project_rows],
    }


def process_reordered_receipts(
    source_id: str,
    older_receipt_id: str,
    newer_receipt_id: str,
) -> dict[str, object]:
    import frappe

    from npi_integration.inbound_project.runtime_fixture import resolve_profile
    from npi_integration.inbound_project.worker import process_inbox_message
    from npi_integration.inbound_project.worker_repository import (
        FrappeInboundProjectWorkerRepository,
    )

    repository = FrappeInboundProjectWorkerRepository()
    now = datetime.now(UTC)
    first = repository.claim(UUID(older_receipt_id), now=now - timedelta(minutes=10))
    require(first is not None and first.lease.attempt_count == 1, "P8-02 pending claim failed")
    frappe.db.commit()
    live = repository.claim(
        UUID(older_receipt_id), now=now - timedelta(minutes=9, seconds=59)
    )
    require(live is None, "P8-02 live claim was stolen")
    frappe.db.rollback()
    recovered = repository.claim(
        UUID(older_receipt_id), now=now - timedelta(minutes=4, seconds=59)
    )
    require(
        recovered is not None
        and recovered.expired_recovery
        and recovered.lease.attempt_count == 2,
        "P8-02 expired claim was not recovered",
    )
    frappe.db.commit()
    older = repository.process_claim(
        recovered,
        profile=resolve_profile(),
        now=now - timedelta(minutes=4, seconds=58),
    )
    frappe.db.commit()
    require(
        older.state == "superseded" and older.project_global_id is None,
        "P8-02 higher-before-older ordering created an old Project",
    )
    newer = process_inbox_message(newer_receipt_id)
    require(
        newer.get("state") == "succeeded"
        and newer.get("disposition") == "project_created",
        "P8-02 current receipt did not create the draft Project",
    )
    context = _runtime_context(source_id, (older_receipt_id, newer_receipt_id))
    projects = context["projects"]
    gates = context["gates"]
    binding = context["binding"]
    require(
        isinstance(projects, list)
        and len(projects) == 1
        and projects[0].get("lifecycle_state") == "draft"
        and projects[0].get("source_system") == "NPI_ONE"
        and projects[0].get("owner_user_id") == OWNER_USER,
        "P8-02 Project result drifted",
    )
    require(
        isinstance(gates, list)
        and len(gates) == 2
        and all(row.get("state") == "not_started" for row in gates),
        "P8-02 Gate shell result drifted",
    )
    require(
        isinstance(binding, dict)
        and binding.get("stream_state") == "bound"
        and binding.get("bound_project_global_id") == newer.get("projectGlobalId")
        and int(binding.get("bound_version") or 0) == 2,
        "P8-02 exact source binding drifted",
    )
    return {
        "digest": context["digest"],
        "expiredRecovery": True,
        "gateCount": len(gates),
        "projectGlobalId": newer["projectGlobalId"],
        "projectCount": len(projects),
    }


def replay_receipt(
    source_id: str,
    older_receipt_id: str,
    newer_receipt_id: str,
    expected_digest: str,
    expected_project_id: str,
) -> dict[str, object]:
    from npi_integration.inbound_project.worker import process_inbox_message

    before = _runtime_context(source_id, (older_receipt_id, newer_receipt_id))
    result = process_inbox_message(newer_receipt_id)
    after = _runtime_context(source_id, (older_receipt_id, newer_receipt_id))
    require(
        result.get("state") == "not_claimed"
        and before["digest"] == expected_digest
        and after["digest"] == expected_digest
        and after["binding"].get("bound_project_global_id") == expected_project_id,
        "P8-02 cross-process replay changed durable truth",
    )
    return {
        "digest": after["digest"],
        "projectGlobalId": expected_project_id,
        "replayStable": True,
    }


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    import frappe

    fixtures = {
        "process_reordered_receipts": process_reordered_receipts,
        "replay_receipt": replay_receipt,
    }
    require(method in fixtures, "P8-02 Bench fixture is unavailable")
    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    try:
        result = fixtures[method](**kwargs)
        frappe.db.commit()
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.destroy()


def run_fresh(base_url: str) -> dict[str, object]:
    administrator_password = secret_from_environment(
        "NPI_RUNTIME_ADMINISTRATOR_PASSWORD"
    )
    administrator = login(base_url, "Administrator", administrator_password)
    csrf = bootstrap_csrf(administrator, base_url, "Administrator")
    fixture_password = secret_from_environment("NPI_RUNTIME_FIXTURE_PASSWORD")
    ensure_runtime_users(administrator, base_url, csrf, fixture_password)
    ensure_runtime_template(administrator, base_url, csrf)
    old_secret = secret_from_environment("NPI_P8_02_RUNTIME_SECRET_OLD")
    new_secret = secret_from_environment("NPI_P8_02_RUNTIME_SECRET_NEW")
    main_source = f"QTN-P802-{FIXTURE_RUN_ID[:12]}"

    invalid = source_event(
        label="bad-signature",
        source_id=f"QTN-BAD-{FIXTURE_RUN_ID[:10]}",
        version=1,
        title="Synthetic invalid signature",
    )
    bad = send_event(
        base_url,
        invalid,
        key_id="p8-runtime-old",
        secret=old_secret,
        request_label="bad-signature",
        corrupt_signature=True,
    )
    require(
        bad.status == 401
        and bad.body.get("code") == "INBOUND_PROJECT_AUTHENTICATION_FAILED",
        "P8-02 bad signature did not fail closed",
    )
    stale = send_event(
        base_url,
        {**invalid, "event_id": str(deterministic_uuid("event:stale"))},
        key_id="p8-runtime-old",
        secret=old_secret,
        request_label="stale",
        timestamp=int(time.time()) - 301,
    )
    require(
        stale.status == 401
        and stale.body.get("code") == "INBOUND_PROJECT_AUTHENTICATION_FAILED",
        "P8-02 stale signature did not fail closed",
    )

    older_event = source_event(
        label="main-v1",
        source_id=main_source,
        version=1,
        title="Synthetic inbound Project v1",
    )
    older = send_event(
        base_url,
        older_event,
        key_id="p8-runtime-old",
        secret=old_secret,
        request_label="main-v1",
    )
    require(
        older.status == 202
        and older.body.get("state") == "pending"
        and older.body.get("exactDuplicate") is False,
        "P8-02 old-key receipt was not durably acknowledged",
    )

    newer_event = source_event(
        label="main-v2",
        source_id=main_source,
        version=2,
        title="Synthetic inbound Project v2",
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                send_event,
                base_url,
                newer_event,
                key_id="p8-runtime-new",
                secret=new_secret,
                request_label=f"main-v2-{index}",
            )
            for index in range(2)
        ]
        concurrent = [future.result() for future in futures]
    require(
        all(result.status == 202 for result in concurrent)
        and sorted(result.body.get("exactDuplicate") for result in concurrent)
        == [False, True]
        and len({result.body.get("receiptId") for result in concurrent}) == 1,
        "P8-02 concurrent event replay was not idempotent",
    )
    newer_receipt = str(concurrent[0].body["receiptId"])

    conflict_source = f"QTN-CONFLICT-{FIXTURE_RUN_ID[:8]}"
    conflict_first_event = source_event(
        label="conflict-a",
        source_id=conflict_source,
        version=1,
        title="Synthetic conflict A",
    )
    conflict_first = send_event(
        base_url,
        conflict_first_event,
        key_id="p8-runtime-new",
        secret=new_secret,
        request_label="conflict-a",
    )
    conflict_second = send_event(
        base_url,
        source_event(
            label="conflict-b",
            source_id=conflict_source,
            version=1,
            title="Synthetic conflict B",
        ),
        key_id="p8-runtime-new",
        secret=new_secret,
        request_label="conflict-b",
    )
    require(
        conflict_first.status == 202
        and conflict_second.status == 409
        and conflict_second.body.get("code") == "INBOUND_PROJECT_SOURCE_CONFLICT",
        "P8-02 equal-version source conflict drifted",
    )

    processed = run_bench_fixture(
        "process_reordered_receipts",
        {
            "source_id": main_source,
            "older_receipt_id": str(older.body["receiptId"]),
            "newer_receipt_id": newer_receipt,
        },
    )
    later = send_event(
        base_url,
        source_event(
            label="main-v3",
            source_id=main_source,
            version=3,
            title="Synthetic inbound Project v3",
        ),
        key_id="p8-runtime-new",
        secret=new_secret,
        request_label="main-v3",
    )
    require(
        later.status == 202
        and later.body.get("state") == "received_after_creation",
        "P8-02 later source version attempted to rewrite the Project",
    )
    return {
        "digest": processed["digest"],
        "newerReceiptId": newer_receipt,
        "olderReceiptId": str(older.body["receiptId"]),
        "projectGlobalId": processed["projectGlobalId"],
        "sourceId": main_source,
    }


def run_disabled_probe(base_url: str) -> dict[str, object]:
    secret = secret_from_environment("NPI_P8_02_RUNTIME_SECRET_OLD")
    result = send_event(
        base_url,
        source_event(
            label="disabled-probe",
            source_id=f"QTN-DISABLED-{FIXTURE_RUN_ID[:8]}",
            version=1,
            title="Synthetic disabled ingress probe",
        ),
        key_id="p8-runtime-old",
        secret=secret,
        request_label="disabled-probe",
    )
    require(
        result.status == 503
        and result.body.get("code") == "INBOUND_PROJECT_INGRESS_UNAVAILABLE",
        "P8-02 default-disabled ingress drifted",
    )
    return {"disabled": True, "digest": canonical_hash(result.body)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url")
    parser.add_argument("--replay-only", action="store_true")
    parser.add_argument("--disabled-probe", action="store_true")
    parser.add_argument("--bench-fixture")
    parser.add_argument("--fixture-kwargs")
    arguments = parser.parse_args()
    if arguments.bench_fixture:
        require(
            arguments.base_url is None and arguments.fixture_kwargs is not None,
            "P8-02 fixture invocation drifted",
        )
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "P8-02 fixture arguments are invalid")
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return
    require(
        arguments.base_url is not None
        and FIXTURE_RUN_ID != "0" * 32
        and ACTOR_USER.endswith("@example.invalid")
        and OWNER_USER.endswith("@example.invalid")
        and bool(TEMPLATE_ID),
        "P8-02 runtime invocation is incomplete",
    )
    base_url = validate_local_fixture_inputs(
        arguments.base_url,
        "Administrator",
        ACTOR_USER,
    )
    state_path = BENCH_PATH / "sites" / SITE_NAME / ".p8-02-runtime-state.json"
    if arguments.disabled_probe:
        result = run_disabled_probe(base_url)
    elif arguments.replay_only:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        result = run_bench_fixture(
            "replay_receipt",
            {
                "source_id": state["sourceId"],
                "older_receipt_id": state["olderReceiptId"],
                "newer_receipt_id": state["newerReceiptId"],
                "expected_digest": state["digest"],
                "expected_project_id": state["projectGlobalId"],
            },
        )
        state_path.unlink()
    else:
        result = run_fresh(base_url)
        state_path.write_text(
            json.dumps(result, separators=(",", ":"), sort_keys=True),
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "claimRecovery": not arguments.disabled_probe,
                "projectCount": 0 if arguments.disabled_probe else 1,
                "replayStable": bool(arguments.replay_only),
                "resultDigest": result["digest"],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
