from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID, uuid5

import verify_document_runtime as document_runtime
import verify_item_publish_runtime as item_runtime
import verify_publish_request_runtime as publish_runtime
from verify_frappe_runtime import (
    login,
    require,
    secret_from_environment,
    validate_local_fixture_inputs,
)
from verify_project_runtime import bootstrap_csrf


ROOT = Path(__file__).resolve().parents[1]
BENCH_PATH = ROOT / "tmp" / "frappe-bench"
SITE_NAME = document_runtime.SITE_NAME
FIXTURE_RUN_ID = document_runtime.FIXTURE_RUN_ID
ACTOR_USER = publish_runtime.ACTOR_USER
RUNTIME_MARKER = "npi-one-mbom-publish-disposable-v1"
ACKNOWLEDGEMENT = (
    "I confirm this request uses the exact released EBOM topology, current Item "
    "readiness, MBOM expectations, and execution profile."
)


def mbom_publish_path(project_id: str, request_id: str | None = None) -> str:
    base = f"/api/npi/v1/projects/{project_id}/mbom-publish-requests"
    return base if request_id is None else f"{base}/{request_id}"


def mbom_publish_request(
    opener,
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    csrf_token: str | None = None,
    idempotency_key: str | None = None,
    query_key: str = "query",
):
    headers = (
        document_runtime.command_headers(csrf_token, idempotency_key)
        if idempotency_key is not None
        else document_runtime.query_headers(f"p804-{query_key}")
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
        "P8-04 MBOM request identity was not echoed",
    )
    require(
        result.headers.get("Cache-Control") == "private, no-store",
        "P8-04 MBOM response cache control drifted",
    )
    return result


def assert_profile(value: object, *, available: bool) -> None:
    require(isinstance(value, dict), "P8-04 MBOM collection is invalid")
    permissions = value.get("permissions")
    if not available:
        require(
            value.get("executionProfile") is None
            and permissions == {"canView": True, "canExecute": False},
            "P8-04 default-disabled profile drifted",
        )
        return
    profile = value.get("executionProfile")
    require(
        isinstance(profile, dict)
        and profile.get("profileId") == "mbom-synthetic-disposable-v1"
        and profile.get("profileVersion") == 1
        and profile.get("targetMode") == "synthetic"
        and profile.get("environmentCode") == "disposable-test"
        and permissions == {"canView": True, "canExecute": True},
        "P8-04 disposable Synthetic profile drifted",
    )


def _assert_no_formal_target(value: object) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key in {"formalBomId", "targetVersion"}:
                require(nested is None, "P8-04 Synthetic proof claimed formal MBOM truth")
            _assert_no_formal_target(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_no_formal_target(nested)


def run_disabled_probe(base_url: str, fixture_password: str) -> dict[str, object]:
    administrator = login(
        base_url,
        "Administrator",
        secret_from_environment("NPI_RUNTIME_ADMINISTRATOR_PASSWORD"),
    )
    actor = login(base_url, ACTOR_USER, fixture_password)
    context = item_runtime.released_item_context(administrator, actor, base_url)
    project_id = str(context["projectGlobalId"])
    listed = mbom_publish_request(
        actor, base_url, mbom_publish_path(project_id), query_key="disabled"
    )
    require(
        listed.status == 200 and listed.body.get("items") == [],
        "P8-04 disabled collection is not empty",
    )
    assert_profile(listed.body, available=False)
    return {"defaultDisabled": True, "projectGlobalId": project_id}


def run_fresh(base_url: str, fixture_password: str) -> dict[str, object]:
    administrator = login(
        base_url,
        "Administrator",
        secret_from_environment("NPI_RUNTIME_ADMINISTRATOR_PASSWORD"),
    )
    actor = login(base_url, ACTOR_USER, fixture_password)
    csrf = bootstrap_csrf(actor, base_url, ACTOR_USER)
    context = item_runtime.released_item_context(administrator, actor, base_url)
    project_id = str(context["projectGlobalId"])
    publish_request_id = str(context["publishRequestGlobalId"])
    worker = os.environ.get("NPI_P8_04_RUNTIME_WORKER")
    require(
        os.environ.get("NPI_P8_04_RUNTIME_PROJECT_ID") == project_id
        and os.environ.get("NPI_P8_04_RUNTIME_REQUESTER") == ACTOR_USER
        and isinstance(worker, str)
        and worker not in {"", ACTOR_USER},
        "P8-04 runtime actors are not exactly bound",
    )
    path = mbom_publish_path(project_id)
    empty = mbom_publish_request(actor, base_url, path, query_key="enabled-empty")
    require(empty.status == 200 and empty.body.get("items") == [], "P8-04 namespace is not fresh")
    assert_profile(empty.body, available=True)
    inputs = run_bench_fixture(
        "capture_inputs",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "phase5_request_id": publish_request_id,
        },
    )
    created = mbom_publish_request(
        actor,
        base_url,
        path,
        method="POST",
        payload={
            "phase5PublishRequestGlobalId": publish_request_id,
            "expectedSourceHash": inputs["sourceHash"],
            "expectedTopologyHash": inputs["topologyHash"],
            "expectedItemMappingSetHash": inputs["itemMappingSetHash"],
            "expectedMbomMappingSetHash": inputs["mbomMappingSetHash"],
            "acknowledgement": ACKNOWLEDGEMENT,
        },
        csrf_token=csrf,
        idempotency_key=f"p8-04-synthetic-{FIXTURE_RUN_ID}",
    )
    request = created.body.get("request")
    request_id = created.body.get("requestGlobalId")
    outbox_id = created.body.get("outboxEventId")
    require(
        created.status == 201
        and isinstance(request, dict)
        and request.get("state") == "queued"
        and isinstance(request_id, str)
        and str(UUID(request_id)) == request_id
        and isinstance(outbox_id, str)
        and str(UUID(outbox_id)) == outbox_id,
        "P8-04 Synthetic command did not create one queued batch",
    )
    exercised = run_bench_fixture(
        "exercise_worker",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "request_id": request_id,
            "outbox_id": outbox_id,
        },
    )
    require(
        exercised.get("syntheticVerified") is True
        and exercised.get("adapterCalls") == 1
        and exercised.get("mappingHeadCount") == 0
        and exercised.get("terminalReplayNotClaimed") is True
        and exercised.get("recoverableCount") == 0,
        "P8-04 worker durability proof drifted",
    )
    detail = mbom_publish_request(
        actor,
        base_url,
        mbom_publish_path(project_id, request_id),
        query_key="terminal-detail",
    )
    require(
        detail.status == 200
        and detail.body.get("request", {}).get("state") == "synthetic_verified",
        "P8-04 terminal Synthetic truth is unavailable",
    )
    _assert_no_formal_target(detail.body)
    return {
        "adapterCalls": 1,
        "mappingHeadCount": 0,
        "projectGlobalId": project_id,
        "syntheticVerified": True,
    }


def capture_inputs(
    fixture_run_id: str, project_id: str, phase5_request_id: str
) -> dict[str, object]:
    import frappe

    from npi_core.foundation.security import Principal, ProjectAccess
    from npi_integration.mbom_publish.frappe_repository import FrappeMbomPublishRepository
    from npi_integration.mbom_publish.runtime_fixture import resolve_profile

    require(
        fixture_run_id == FIXTURE_RUN_ID
        and project_id == str(UUID(project_id))
        and phase5_request_id == str(UUID(phase5_request_id)),
        "P8-04 input capture identity drifted",
    )
    project = frappe.get_doc("NPI Engineering Project", project_id)
    principal = Principal(
        user_id=ACTOR_USER,
        roles=frozenset({"NPI API User"}),
        project_access={project_id: ProjectAccess.CONTRIBUTE},
        tenant_id=str(project.tenant_id),
    )
    repository = FrappeMbomPublishRepository(
        principal=principal,
        request_id=str(uuid5(UUID(int=0), f"p804-request:{fixture_run_id}")),
        trace_id=f"trace-p804-{fixture_run_id}",
        profile_resolver=lambda tenant, project_uuid: resolve_profile(
            tenant, str(project_uuid)
        ),
    )
    profile = resolve_profile(str(project.tenant_id), project_id)
    require(profile is not None, "P8-04 disposable profile is unavailable")
    built = repository._build_request(
        project,
        UUID(phase5_request_id),
        profile,
        idempotency_key_hash="0" * 64,
        lock=False,
    )
    return {
        "sourceHash": built.source.source_hash,
        "topologyHash": built.source.topology_hash,
        "itemMappingSetHash": built.item_mapping_set_hash,
        "mbomMappingSetHash": built.mbom_mapping_set_hash,
    }


def exercise_worker(
    fixture_run_id: str, project_id: str, request_id: str, outbox_id: str
) -> dict[str, object]:
    import frappe

    from npi_integration.mbom_publish.runtime_fixture import synthetic_adapter_call_count
    from npi_integration.mbom_publish.worker import process_outbox_message
    from npi_integration.mbom_publish.worker_repository import FrappeMbomPublishWorkerRepository

    require(
        fixture_run_id == FIXTURE_RUN_ID
        and project_id == str(UUID(project_id))
        and request_id == str(UUID(request_id))
        and outbox_id == str(UUID(outbox_id)),
        "P8-04 worker fixture identity drifted",
    )
    result = process_outbox_message(outbox_id)
    request = frappe.get_doc("NPI MBOM Publish Request", request_id)
    node_results = frappe.get_all(
        "NPI MBOM Publish Node Result",
        filters={"request_global_id": request_id},
        fields=["state", "formal_bom_id", "target_version", "authority"],
    )
    require(
        result.get("state") == "synthetic_verified"
        and str(request.state) == "synthetic_verified"
        and node_results
        and all(
            row.get("state") == "synthetic_verified"
            and row.get("authority") == "synthetic"
            and not row.get("formal_bom_id")
            and not row.get("target_version")
            for row in node_results
        ),
        "P8-04 Synthetic node truth drifted",
    )
    replay = process_outbox_message(outbox_id)
    recoverable = FrappeMbomPublishWorkerRepository().recoverable_outbox_event_ids(
        now=datetime.now(UTC)
    )
    return {
        "adapterCalls": synthetic_adapter_call_count(),
        "mappingHeadCount": frappe.db.count(
            "NPI MBOM Mapping Head", {"project_global_id": project_id}
        ),
        "recoverableCount": sum(1 for value in recoverable if str(value) == outbox_id),
        "syntheticVerified": True,
        "terminalReplayNotClaimed": replay.get("state") == "not_claimed",
    }


def run_bench_fixture(method: str, kwargs: dict[str, object]) -> dict[str, Any]:
    environment = os.environ.copy()
    current_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = str(ROOT) if not current_pythonpath else f"{ROOT}{os.pathsep}{current_pythonpath}"
    for variable in (
        "NPI_RUNTIME_ADMINISTRATOR_PASSWORD",
        "NPI_RUNTIME_FIXTURE_PASSWORD",
        "NPI_ADMINISTRATOR_PASSWORD",
        "NPI_DATABASE_ROOT_PASSWORD",
    ):
        environment.pop(variable, None)
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as fixture_output:
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
            stdout=fixture_output,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        require(completed.returncode == 0, "P8-04 Bench fixture failed")
        fixture_output.seek(0)
        lines = [line for line in fixture_output if line.strip()]
    result = json.loads(lines[-1]) if lines else None
    require(isinstance(result, dict), "P8-04 Bench fixture result is invalid")
    return result


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    import frappe

    fixtures = {"capture_inputs": capture_inputs, "exercise_worker": exercise_worker}
    require(method in fixtures, "P8-04 Bench fixture is unavailable")
    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    try:
        document_runtime._validated_runtime_site()
        frappe.set_user(ACTOR_USER if method == "exercise_worker" else "Administrator")
        result = fixtures[method](**kwargs)
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
        require(
            arguments.base_url is None
            and arguments.fixture_kwargs is not None
            and not arguments.disabled_probe,
            "P8-04 fixture invocation drifted",
        )
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "P8-04 fixture arguments are invalid")
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return
    require(
        arguments.base_url is not None and FIXTURE_RUN_ID != "0" * 32,
        "P8-04 runtime invocation is incomplete",
    )
    base_url = validate_local_fixture_inputs(arguments.base_url, "Administrator", ACTOR_USER)
    fixture_password = secret_from_environment("NPI_RUNTIME_FIXTURE_PASSWORD")
    result = (
        run_disabled_probe(base_url, fixture_password)
        if arguments.disabled_probe
        else run_fresh(base_url, fixture_password)
    )
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
