from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID

import verify_document_runtime as document_runtime
import verify_ebom_runtime as ebom_runtime
import verify_publish_request_runtime as publish_runtime
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
ACKNOWLEDGEMENT = (
    "I confirm this request uses the exact released Item source and current "
    "execution profile."
)
RUNTIME_MARKER = "npi-one-item-publish-disposable-v1"


def item_publish_path(project_id: str, request_id: str | None = None) -> str:
    base = f"/api/npi/v1/projects/{project_id}/item-publish-requests"
    return base if request_id is None else f"{base}/{request_id}"


def item_publish_request(
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
        else document_runtime.query_headers(f"p803-{query_key}")
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
        "P8-03 Item request identity was not echoed",
    )
    require(
        result.headers.get("Cache-Control") == "private, no-store",
        "P8-03 Item response cache control drifted",
    )
    return result


def released_item_context(administrator, actor, base_url: str) -> dict[str, object]:
    context = publish_runtime.released_context(administrator, actor, base_url)
    path = publish_runtime.publish_path(
        str(context["projectId"]),
        str(context["ebomId"]),
        str(context["revisionId"]),
    )
    request_label = "p803-retained-publish"
    retained = publish_runtime.publish_request(
        actor,
        base_url,
        path,
        query_key=request_label,
    )
    require(retained.status == 200, "P8-03 released publish input is unavailable")
    items = retained.body.get("items")
    require(
        isinstance(items, list) and len(items) == 1,
        "P8-03 released publish request cardinality drifted",
    )
    request = items[0]
    nodes = request.get("nodes") if isinstance(request, dict) else None
    require(
        isinstance(nodes, list)
        and len(nodes) == 2
        and all(isinstance(node, dict) for node in nodes),
        "P8-03 released Item node cardinality drifted",
    )
    publish_request_id = request.get("globalId")
    node_ids = tuple(node.get("globalId") for node in nodes)
    require(
        isinstance(publish_request_id, str)
        and str(UUID(publish_request_id)) == publish_request_id
        and len(set(node_ids)) == 2
        and all(
            isinstance(node_id, str) and str(UUID(node_id)) == node_id
            for node_id in node_ids
        ),
        "P8-03 released Item identities drifted",
    )
    return {
        "projectGlobalId": str(context["projectId"]),
        "publishRequestGlobalId": publish_request_id,
        "selectedPublishNodeGlobalIds": list(node_ids),
    }


def create_payload(context: Mapping[str, object], node_id: str) -> dict[str, object]:
    return {
        "publishRequestGlobalId": context["publishRequestGlobalId"],
        "selectedPublishNodeGlobalId": node_id,
        "expectedMappingVersion": 0,
        "acknowledgement": ACKNOWLEDGEMENT,
    }


def assert_profile(value: object, *, available: bool) -> None:
    require(isinstance(value, dict), "P8-03 Item collection is invalid")
    permissions = value.get("permissions")
    if not available:
        require(
            value.get("executionProfile") is None
            and permissions == {"canView": True, "canExecute": False},
            "P8-03 default-disabled profile drifted",
        )
        return
    profile = value.get("executionProfile")
    require(
        isinstance(profile, dict)
        and profile.get("profileId") == "item-synthetic-disposable-v1"
        and profile.get("profileVersion") == 1
        and profile.get("targetMode") == "synthetic"
        and profile.get("environmentCode") == "disposable-test"
        and permissions == {"canView": True, "canExecute": True},
        "P8-03 disposable Synthetic profile drifted",
    )


def _assert_no_formal_target(value: object) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key in {"formalItemCode", "targetVersion"}:
                require(nested is None, "P8-03 Synthetic proof claimed formal target truth")
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
    actor_csrf = bootstrap_csrf(actor, base_url, ACTOR_USER)
    context = released_item_context(administrator, actor, base_url)
    project_id = str(context["projectGlobalId"])
    path = item_publish_path(project_id)
    listed = item_publish_request(actor, base_url, path, query_key="disabled-list")
    require(
        listed.status == 200 and listed.body.get("items") == [],
        "P8-03 default-disabled collection drifted",
    )
    assert_profile(listed.body, available=False)
    nodes = context["selectedPublishNodeGlobalIds"]
    assert isinstance(nodes, list)
    rejected = item_publish_request(
        actor,
        base_url,
        path,
        method="POST",
        payload=create_payload(context, str(nodes[0])),
        csrf_token=actor_csrf,
        idempotency_key=f"p8-03-disabled-{FIXTURE_RUN_ID}",
    )
    validate_problem(rejected, 503, "ITEM_EXECUTION_PROFILE_UNAVAILABLE")
    for doctype in ("NPI Item Publish Request", "NPI Outbox Message"):
        require(
            ebom_runtime.count_rows(
                administrator,
                base_url,
                doctype,
                project_id,
            )
            == [],
            "P8-03 disabled command persisted executable work",
        )
    return {"defaultDisabled": True, "projectGlobalId": project_id}


def _assert_created(value: object, *, project_id: str) -> tuple[str, str]:
    require(isinstance(value, dict), "P8-03 Item command response is invalid")
    request = value.get("request")
    require(
        value.get("currentMapping") is None
        and isinstance(request, dict)
        and request.get("state") == "queued"
        and request.get("dispatchAllowed") is True
        and request.get("source", {}).get("projectGlobalId") == project_id
        and request.get("profile", {}).get("targetMode") == "synthetic",
        "P8-03 queued Item command truth drifted",
    )
    request_id = request.get("globalId")
    outbox_id = request.get("outboxEventId")
    require(
        isinstance(request_id, str)
        and str(UUID(request_id)) == request_id
        and isinstance(outbox_id, str)
        and str(UUID(outbox_id)) == outbox_id,
        "P8-03 queued Item identities drifted",
    )
    _assert_no_formal_target(value)
    return request_id, outbox_id


def run_fresh(base_url: str, fixture_password: str) -> dict[str, object]:
    administrator = login(
        base_url,
        "Administrator",
        secret_from_environment("NPI_RUNTIME_ADMINISTRATOR_PASSWORD"),
    )
    actor = login(base_url, ACTOR_USER, fixture_password)
    actor_csrf = bootstrap_csrf(actor, base_url, ACTOR_USER)
    context = released_item_context(administrator, actor, base_url)
    project_id = str(context["projectGlobalId"])
    require(
        os.environ.get("NPI_P8_03_RUNTIME_PROJECT_ID") == project_id
        and os.environ.get("NPI_P8_03_RUNTIME_REQUESTER") == ACTOR_USER
        and os.environ.get("NPI_P8_03_RUNTIME_WORKER") == ACTOR_USER,
        "P8-03 runtime profile environment is not bound to the retained Project",
    )
    path = item_publish_path(project_id)
    empty = item_publish_request(actor, base_url, path, query_key="enabled-empty")
    require(
        empty.status == 200 and empty.body.get("items") == [],
        "P8-03 enabled collection is not fresh",
    )
    assert_profile(empty.body, available=True)
    nodes = context["selectedPublishNodeGlobalIds"]
    assert isinstance(nodes, list)
    identities: list[tuple[str, str]] = []
    for label, node_id in zip(("synthetic", "uncertain"), nodes, strict=True):
        created = item_publish_request(
            actor,
            base_url,
            path,
            method="POST",
            payload=create_payload(context, str(node_id)),
            csrf_token=actor_csrf,
            idempotency_key=f"p8-03-{label}-{FIXTURE_RUN_ID}",
        )
        require(
            created.status == 201
            and created.headers.get("Idempotency-Replayed") == "false",
            "P8-03 Item command did not create one queued request",
        )
        identities.append(_assert_created(created.body, project_id=project_id))

    exercised = run_bench_fixture(
        "exercise_worker",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "synthetic_request_id": identities[0][0],
            "synthetic_outbox_id": identities[0][1],
            "uncertain_request_id": identities[1][0],
            "uncertain_outbox_id": identities[1][1],
        },
    )
    require(
        exercised.get("syntheticVerified") is True
        and exercised.get("uncertainAfterBoundary") is True
        and exercised.get("liveClaimRejected") is True
        and exercised.get("expiredPreBoundaryRecovered") is True
        and exercised.get("adapterCalls") == 1
        and exercised.get("attemptCount") == 4
        and exercised.get("resultCount") == 2
        and exercised.get("mappingCount") == 0,
        "P8-03 worker durability proof drifted",
    )
    listed = item_publish_request(actor, base_url, path, query_key="terminal-list")
    require(listed.status == 200, "P8-03 terminal Item collection is unavailable")
    assert_profile(listed.body, available=True)
    items = listed.body.get("items")
    require(
        isinstance(items, list)
        and len(items) == 2
        and {item.get("state") for item in items if isinstance(item, dict)}
        == {"synthetic_verified", "uncertain_after_timeout"},
        "P8-03 terminal Item states drifted",
    )
    _assert_no_formal_target(listed.body)
    return {
        "crossProcessReplayReady": True,
        "digest": exercised["digest"],
        "mappingCount": 0,
        "projectGlobalId": project_id,
        "resultCount": 2,
    }


def run_replay(base_url: str, fixture_password: str) -> dict[str, object]:
    administrator = login(
        base_url,
        "Administrator",
        secret_from_environment("NPI_RUNTIME_ADMINISTRATOR_PASSWORD"),
    )
    actor = login(base_url, ACTOR_USER, fixture_password)
    context = released_item_context(administrator, actor, base_url)
    project_id = str(context["projectGlobalId"])
    listed = item_publish_request(
        actor,
        base_url,
        item_publish_path(project_id),
        query_key="cross-process-list",
    )
    items = listed.body.get("items")
    require(
        listed.status == 200 and isinstance(items, list) and len(items) == 2,
        "P8-03 retained terminal requests are unavailable",
    )
    bindings = [
        {
            "request_id": str(item.get("globalId")),
            "outbox_id": str(item.get("outboxEventId")),
        }
        for item in items
        if isinstance(item, dict)
    ]
    require(len(bindings) == 2, "P8-03 retained Outbox bindings drifted")
    replayed = run_bench_fixture(
        "replay_terminal",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "bindings": bindings,
        },
    )
    require(
        replayed.get("crossProcessReplay") is True
        and replayed.get("notClaimedCount") == 2
        and replayed.get("recoverableCount") == 0
        and replayed.get("mappingCount") == 0,
        "P8-03 cross-process terminal replay drifted",
    )
    _assert_no_formal_target(listed.body)
    return replayed


def capture_project(fixture_run_id: str) -> dict[str, object]:
    import frappe

    document_runtime._validated_runtime_site()
    require(fixture_run_id == FIXTURE_RUN_ID, "P8-03 fixture namespace drifted")
    project_id = frappe.db.get_value(
        "NPI Engineering Project",
        {"tenant_id": TENANT_ID, "business_code": document_runtime.BUSINESS_CODE},
        "global_id",
    )
    require(
        isinstance(project_id, str) and str(UUID(project_id)) == project_id,
        "P8-03 retained Project identity is unavailable",
    )
    return {"projectGlobalId": project_id}


def _rows(doctype: str, filters: object, fields: list[str]) -> list[dict[str, Any]]:
    import frappe

    return list(
        frappe.get_all(
            doctype,
            filters=filters,
            fields=fields,
            order_by="name asc",
            limit_page_length=100,
        )
    )


def _structural_context(project_id: str) -> dict[str, object]:
    from npi_integration.item_publish.domain import canonical_hash

    requests = _rows(
        "NPI Item Publish Request",
        {"project_global_id": project_id},
        ["global_id", "state", "outbox_event_id", "result_global_id", "optimistic_version"],
    )
    request_ids = [str(row["global_id"]) for row in requests]
    scoped = [["request_global_id", "in", request_ids]]
    outboxes = _rows(
        "NPI Outbox Message",
        {
            "project_global_id": project_id,
            "operation": "publish_released_item",
        },
        [
            "event_id",
            "request_global_id",
            "state",
            "attempt_count",
            "adapter_boundary_crossed",
            "last_attempt_global_id",
            "result_global_id",
            "disposition",
        ],
    )
    attempts = (
        _rows(
            "NPI Item Publish Attempt",
            scoped,
            [
                "global_id",
                "request_global_id",
                "attempt_number",
                "target_idempotency_key_hash",
                "state",
                "adapter_boundary_crossed",
                "transport_disposition",
                "fault_kind",
                "reconciliation_required",
                "safe_error_code",
                "attempt_hash",
            ],
        )
        if request_ids
        else []
    )
    results = (
        _rows(
            "NPI Item Publish Result",
            scoped,
            [
                "global_id",
                "request_global_id",
                "attempt_global_id",
                "attempt_number",
                "idempotency_key_hash",
                "state",
                "authority",
                "formal_item_code",
                "target_version",
                "fault_kind",
                "result_hash",
            ],
        )
        if request_ids
        else []
    )
    mapping_heads = _rows(
        "NPI Item Mapping Head",
        {"project_global_id": project_id},
        ["global_id"],
    )
    mapping_observations = _rows(
        "NPI Item Mapping Observation",
        {"project_global_id": project_id},
        ["global_id"],
    )
    value = {
        "requests": requests,
        "outboxes": outboxes,
        "attempts": attempts,
        "results": results,
        "mappingHeadCount": len(mapping_heads),
        "mappingObservationCount": len(mapping_observations),
    }
    return {**value, "digest": canonical_hash(value)}


def _validate_fixture(
    *,
    fixture_run_id: str,
    project_id: str,
    request_ids: tuple[str, ...],
) -> None:
    import frappe

    document_runtime._validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID
        and os.environ.get("NPI_P8_03_RUNTIME_ENABLED") == "1"
        and os.environ.get("NPI_P8_03_RUNTIME_MARKER") == RUNTIME_MARKER
        and os.environ.get("NPI_P8_03_RUNTIME_PROJECT_ID") == project_id
        and os.environ.get("NPI_P8_03_RUNTIME_REQUESTER") == ACTOR_USER
        and os.environ.get("NPI_P8_03_RUNTIME_WORKER") == ACTOR_USER,
        "P8-03 disposable execution binding drifted",
    )
    project = frappe.get_doc("NPI Engineering Project", project_id)
    require(
        str(project.global_id) == project_id and str(project.tenant_id) == TENANT_ID,
        "P8-03 retained Project scope drifted",
    )
    for request_id in request_ids:
        row = frappe.get_doc("NPI Item Publish Request", request_id)
        require(
            str(row.project_global_id) == project_id
            and str(row.tenant_id) == TENANT_ID
            and str(row.actor_user_id) == ACTOR_USER,
            "P8-03 retained request scope drifted",
        )


def exercise_worker(
    fixture_run_id: str,
    project_id: str,
    synthetic_request_id: str,
    synthetic_outbox_id: str,
    uncertain_request_id: str,
    uncertain_outbox_id: str,
) -> dict[str, object]:
    import frappe

    from npi_integration.item_publish.runtime_fixture import (
        resolve_profile,
        synthetic_adapter_call_count,
    )
    from npi_integration.item_publish.worker import process_outbox_message
    from npi_integration.item_publish.worker_repository import (
        FrappeItemPublishWorkerRepository,
    )

    _validate_fixture(
        fixture_run_id=fixture_run_id,
        project_id=project_id,
        request_ids=(synthetic_request_id, uncertain_request_id),
    )
    frappe.set_user(ACTOR_USER)
    repository = FrappeItemPublishWorkerRepository()
    anchor = datetime.now(UTC)

    first = repository.claim(
        UUID(synthetic_outbox_id),
        now=anchor - timedelta(minutes=12),
    )
    require(
        first is not None and first.command.attempt_number == 1,
        "P8-03 initial pending claim drifted",
    )
    frappe.db.commit()
    live = repository.claim(
        UUID(synthetic_outbox_id),
        now=anchor - timedelta(minutes=7, seconds=1),
    )
    require(live is None, "P8-03 live claim was not excluded")
    frappe.db.rollback()
    recovered = repository.claim(
        UUID(synthetic_outbox_id),
        now=anchor - timedelta(minutes=6),
    )
    require(
        recovered is not None
        and recovered.expired_recovery
        and not recovered.recovered_after_adapter_boundary
        and recovered.command.attempt_number == 2,
        "P8-03 expired pre-boundary claim was not recovered",
    )
    frappe.db.commit()
    calls_before_synthetic = synthetic_adapter_call_count()
    synthetic = process_outbox_message(synthetic_outbox_id)
    require(
        synthetic.get("state") == "synthetic_verified"
        and synthetic.get("mappingAdvanced") is False
        and synthetic_adapter_call_count() == calls_before_synthetic + 1,
        "P8-03 Synthetic worker result drifted",
    )

    uncertain_claim = repository.claim(
        UUID(uncertain_outbox_id),
        now=anchor - timedelta(minutes=6),
    )
    require(
        uncertain_claim is not None and uncertain_claim.command.attempt_number == 1,
        "P8-03 uncertain-path initial claim drifted",
    )
    frappe.db.commit()
    uncertain_profile = repository.require_execution_profile(
        uncertain_claim,
        resolve_profile(TENANT_ID, project_id),
    )
    require(
        repository.mark_adapter_boundary(
            uncertain_claim,
            profile=uncertain_profile,
            now=anchor - timedelta(minutes=5, seconds=59),
        ),
        "P8-03 durable adapter boundary was not sealed",
    )
    frappe.db.commit()
    calls_before_recovery = synthetic_adapter_call_count()
    uncertain = process_outbox_message(uncertain_outbox_id)
    require(
        uncertain.get("state") == "uncertain_after_timeout"
        and uncertain.get("mappingAdvanced") is False
        and synthetic_adapter_call_count() == calls_before_recovery,
        "P8-03 crossed-boundary recovery blindly redispatched",
    )

    structural = _structural_context(project_id)
    attempts = structural["attempts"]
    results = structural["results"]
    assert isinstance(attempts, list) and isinstance(results, list)
    synthetic_attempts = [
        row for row in attempts if row["request_global_id"] == synthetic_request_id
    ]
    uncertain_attempts = [
        row for row in attempts if row["request_global_id"] == uncertain_request_id
    ]
    synthetic_attempts.sort(key=lambda row: int(row["attempt_number"]))
    uncertain_attempts.sort(key=lambda row: int(row["attempt_number"]))
    require(
        len(synthetic_attempts) == 3
        and [row["attempt_number"] for row in synthetic_attempts] == [1, 2, 3]
        and len({row["target_idempotency_key_hash"] for row in synthetic_attempts})
        == 1
        and [row["state"] for row in synthetic_attempts]
        == ["observed_failure", "observed_failure", "synthetic_verified"]
        and len(uncertain_attempts) == 1
        and uncertain_attempts[0]["attempt_number"] == 1
        and uncertain_attempts[0]["state"] == "uncertain"
        and bool(uncertain_attempts[0]["adapter_boundary_crossed"])
        and bool(uncertain_attempts[0]["reconciliation_required"]),
        "P8-03 immutable attempt history drifted",
    )
    require(
        len(results) == 2
        and {row["state"] for row in results}
        == {"synthetic_verified", "uncertain_after_timeout"}
        and {row["authority"] for row in results} == {"synthetic", "none"}
        and all(row["formal_item_code"] is None for row in results)
        and all(row["target_version"] is None for row in results)
        and structural["mappingHeadCount"] == 0
        and structural["mappingObservationCount"] == 0,
        "P8-03 non-authoritative result boundary drifted",
    )
    require(
        repository.recoverable_outbox_event_ids(now=datetime.now(UTC)) == (),
        "P8-03 bounded recovery included terminal work",
    )
    return {
        "adapterCalls": synthetic_adapter_call_count(),
        "attemptCount": len(attempts),
        "digest": structural["digest"],
        "expiredPreBoundaryRecovered": True,
        "liveClaimRejected": True,
        "mappingCount": 0,
        "resultCount": len(results),
        "syntheticVerified": True,
        "uncertainAfterBoundary": True,
    }


def replay_terminal(
    fixture_run_id: str,
    project_id: str,
    bindings: list[dict[str, str]],
) -> dict[str, object]:
    import frappe

    from npi_integration.item_publish.worker import process_outbox_message
    from npi_integration.item_publish.worker_repository import (
        FrappeItemPublishWorkerRepository,
    )

    require(
        isinstance(bindings, list)
        and len(bindings) == 2
        and all(
            isinstance(value, dict)
            and set(value) == {"request_id", "outbox_id"}
            for value in bindings
        ),
        "P8-03 replay bindings are invalid",
    )
    request_ids = tuple(str(value["request_id"]) for value in bindings)
    _validate_fixture(
        fixture_run_id=fixture_run_id,
        project_id=project_id,
        request_ids=request_ids,
    )
    frappe.set_user(ACTOR_USER)
    before = _structural_context(project_id)
    outcomes = [
        process_outbox_message(str(value["outbox_id"])) for value in bindings
    ]
    after = _structural_context(project_id)
    recoverable = FrappeItemPublishWorkerRepository().recoverable_outbox_event_ids(
        now=datetime.now(UTC)
    )
    require(
        all(outcome.get("state") == "not_claimed" for outcome in outcomes)
        and before == after
        and recoverable == (),
        "P8-03 cross-process replay changed terminal truth",
    )
    return {
        "crossProcessReplay": True,
        "digest": after["digest"],
        "mappingCount": after["mappingHeadCount"],
        "notClaimedCount": len(outcomes),
        "recoverableCount": len(recoverable),
    }


def run_bench_fixture(method: str, kwargs: dict[str, object]) -> dict[str, Any]:
    environment = os.environ.copy()
    current_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        str(ROOT)
        if not current_pythonpath
        else f"{ROOT}{os.pathsep}{current_pythonpath}"
    )
    for variable in (
        "NPI_RUNTIME_ADMINISTRATOR_PASSWORD",
        "NPI_RUNTIME_FIXTURE_PASSWORD",
        "NPI_ADMINISTRATOR_PASSWORD",
        "NPI_DATABASE_ROOT_PASSWORD",
    ):
        environment.pop(variable, None)
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
        f"P8-03 Bench fixture {method} failed with a withheld diagnostic",
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    result = json.loads(lines[-1]) if lines else None
    require(isinstance(result, dict), "P8-03 Bench fixture result is invalid")
    return result


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    import frappe

    fixtures = {
        "capture_project": capture_project,
        "exercise_worker": exercise_worker,
        "replay_terminal": replay_terminal,
    }
    require(method in fixtures, "P8-03 Bench fixture is unavailable")
    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    try:
        frappe.set_user("Administrator")
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
    parser.add_argument("--replay-only", action="store_true")
    parser.add_argument("--bench-fixture")
    parser.add_argument("--fixture-kwargs")
    arguments = parser.parse_args()
    if arguments.bench_fixture is not None:
        require(
            arguments.base_url is None
            and arguments.fixture_kwargs is not None
            and not arguments.disabled_probe
            and not arguments.replay_only,
            "P8-03 fixture invocation drifted",
        )
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "P8-03 fixture arguments are invalid")
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return
    require(
        arguments.base_url is not None
        and FIXTURE_RUN_ID != "0" * 32
        and ACTOR_USER.endswith("@example.invalid")
        and int(arguments.disabled_probe) + int(arguments.replay_only) <= 1,
        "P8-03 runtime invocation is incomplete",
    )
    base_url = validate_local_fixture_inputs(
        arguments.base_url,
        "Administrator",
        ACTOR_USER,
    )
    fixture_password = secret_from_environment("NPI_RUNTIME_FIXTURE_PASSWORD")
    if arguments.disabled_probe:
        result = run_disabled_probe(base_url, fixture_password)
    elif arguments.replay_only:
        result = run_replay(base_url, fixture_password)
    else:
        result = run_fresh(base_url, fixture_password)
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
