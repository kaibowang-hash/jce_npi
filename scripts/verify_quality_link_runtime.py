from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

import verify_document_runtime as document_runtime
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
        require(completed.returncode == 0, "P8-06 Bench fixture failed")
        output.seek(0)
        lines = [line for line in output if line.strip()]
    result = json.loads(lines[-1]) if lines else None
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
    from npi_integration.projections.frappe_repository import FrappeProjectionRepository

    principal = Principal(
        user_id=ACTOR_USER,
        roles=frozenset(frappe.get_roles(ACTOR_USER)),
        tenant_id=document_runtime.TENANT_ID,
        is_external=False,
    )
    repository = FrappeProjectionRepository(
        principal=principal,
        request_id=str(uuid5(_NAMESPACE, f"request:{FIXTURE_RUN_ID}")),
        trace_id=f"trace-p806-runtime-{FIXTURE_RUN_ID[:12]}",
        freshness_policies={ProjectionKind.FORMAL_QUALITY_STATUS: ("p8-06-runtime-quality-v1", 86400)},
    )
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
    outcome = repository.apply_observation(
        project_global_id=UUID(project_id),
        target=target,
        result=ProjectionReaderResult(
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
        ),
        event_id=uuid5(_NAMESPACE, f"event:{FIXTURE_RUN_ID}"),
        received_at=datetime(2026, 8, 26, 8, 1, tzinfo=UTC),
        correlation_id=uuid5(_NAMESPACE, f"correlation:{FIXTURE_RUN_ID}"),
    )
    collection = repository.project_collection(
        repository.authorize_project(UUID(project_id)),
        kind="formal_quality_status",
    )
    matches = [
        item
        for item in collection["items"]
        if item["scopeKind"] == "readiness" and item["scopeGlobalId"] == readiness_id
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
    first = document_runtime.npi_request(actor, base_url, path, method="POST", payload=payload, csrf_token=actor_csrf, idempotency_key=IDEMPOTENCY_KEY, query_key="p806-link")
    first_body = _body(first, status=201)
    replay = document_runtime.npi_request(actor, base_url, path, method="POST", payload=payload, csrf_token=actor_csrf, idempotency_key=IDEMPOTENCY_KEY, query_key="p806-replay")
    replay_body = _body(replay, status=201)
    require(first_body == replay_body and replay.headers.get("Idempotency-Replayed") == "true", "P8-06 actor-bound replay drifted")
    stale = document_runtime.npi_request(actor, base_url, path, method="POST", payload={**payload, "expectedSourceVersion": int(current["instanceVersion"]) + 1}, csrf_token=actor_csrf, idempotency_key=f"{IDEMPOTENCY_KEY}-stale", query_key="p806-stale")
    require(stale.status == 409, "P8-06 stale source did not fail closed")
    listing = _body(document_runtime.npi_request(actor, base_url, f"/api/npi/v1/projects/{project_id}/formal-quality-links", query_key="p806-list"), status=200)
    require(listing.get("permissions") == {"view": True, "link": True} and len(listing.get("items", [])) == 1, "P8-06 linked collection truth drifted")
    return {"linked": True, "replayed": True, "staleRejected": True, "targetTraffic": 0, "cleaned": True}


def run_fresh(base_url: str, fixture_password: str) -> dict[str, object]:
    administrator_password = secret_from_environment("NPI_RUNTIME_ADMINISTRATOR_PASSWORD")
    administrator = login(base_url, "Administrator", administrator_password)
    project_id, _ = document_runtime.fixture_project(administrator, base_url)
    actor = login(base_url, ACTOR_USER, fixture_password)
    actor_csrf = bootstrap_csrf(actor, base_url, ACTOR_USER)
    workspace = _body(
        document_runtime.npi_request(actor, base_url, f"/api/npi/v1/projects/{project_id}/npi-readiness", query_key="p806-readiness"),
        status=200,
    )
    current = workspace.get("currentRevision")
    require(isinstance(current, dict), "P8-06 retained readiness revision is unavailable")
    readiness_id = current.get("instanceGlobalId")
    require(isinstance(readiness_id, str), "P8-06 readiness identity is unavailable")
    prepared = run_bench_fixture(
        "prepare_projection",
        {"project_id": project_id, "readiness_id": readiness_id},
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
        run_bench_fixture(
            "cleanup",
            {"project_id": project_id, "readiness_id": readiness_id},
        )


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    import frappe

    require(method in {"prepare_projection", "cleanup"}, "P8-06 Bench fixture is unavailable")
    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    try:
        document_runtime._validated_runtime_site()
        frappe.set_user(ACTOR_USER if method == "prepare_projection" else "Administrator")
        result = prepare_projection(**kwargs) if method == "prepare_projection" else cleanup(**kwargs)
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
    parser.add_argument("--bench-fixture")
    parser.add_argument("--fixture-kwargs")
    arguments = parser.parse_args()
    if arguments.bench_fixture:
        require(arguments.base_url is None and arguments.fixture_kwargs is not None, "P8-06 fixture invocation drifted")
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "P8-06 fixture arguments are invalid")
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return
    require(arguments.base_url is not None and FIXTURE_RUN_ID != "0" * 32, "P8-06 runtime invocation is incomplete")
    base_url = validate_local_fixture_inputs(arguments.base_url, "Administrator", ACTOR_USER)
    result = run_fresh(base_url, secret_from_environment("NPI_RUNTIME_FIXTURE_PASSWORD"))
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
