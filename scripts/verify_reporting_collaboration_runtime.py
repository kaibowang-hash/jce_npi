from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter_ns
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import verify_document_runtime as document_runtime
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
RUNTIME_MARKER = document_runtime.RUNTIME_MARKER
ACTOR_USER = os.environ.get(
    "NPI_P9_02D_RUNTIME_ACTOR", "p9-reporting-manager@example.invalid"
)
LIMITED_USER = os.environ.get(
    "NPI_P9_02D_RUNTIME_LIMITED_ACTOR", "p9-reporting-limited@example.invalid"
)
PROJECT_ID = os.environ.get(
    "NPI_P9_02D_RUNTIME_PROJECT_ID", "00000000-0000-4000-8000-000000000902"
)
MEETING_TITLE = f"P9 reporting review {FIXTURE_RUN_ID[:12]}"
MEETING_KEY = f"p9-reporting-meeting-{FIXTURE_RUN_ID}"
MEETING_STALE_KEY = f"p9-reporting-meeting-stale-{FIXTURE_RUN_ID}"
NOTIFICATION_KEY = f"p9-notification-read-{FIXTURE_RUN_ID}"
NOTIFICATION_STALE_KEY = f"p9-notification-read-stale-{FIXTURE_RUN_ID}"
PREFERENCE_KEY = f"p9-notification-preference-{FIXTURE_RUN_ID}"
PREFERENCE_STALE_KEY = f"p9-notification-preference-stale-{FIXTURE_RUN_ID}"
NOTIFICATION_SOURCE_ID = str(
    uuid5(NAMESPACE_URL, f"npi-p9-02-runtime-notification:{FIXTURE_RUN_ID}")
)
STANDARD_MEETING_TEMPLATE = {
    "globalId": "00000000-0000-4000-8000-000000000902",
    "key": "standard_npi_review",
    "version": 1,
    "titleSource": "Standard NPI review meeting",
    "sectionKeys": ["agenda", "discussion", "decisions"],
}


def canonical_hash(value: object) -> str:
    import hashlib

    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode()
    ).hexdigest()


STANDARD_MEETING_TEMPLATE_HASH = canonical_hash(STANDARD_MEETING_TEMPLATE)
PERFORMANCE_WARMUP_COUNT = 2
PERFORMANCE_SAMPLE_COUNT = 20
COMMON_READ_P95_MILLISECONDS = 3_000
METADATA_SEARCH_P95_MILLISECONDS = 5_000


def nearest_rank_p95(samples: list[float]) -> float:
    require(
        len(samples) == PERFORMANCE_SAMPLE_COUNT
        and all(value >= 0 for value in samples),
        "P9-03 performance sample shape drifted",
    )
    ordered = sorted(samples)
    return ordered[(95 * len(ordered) + 99) // 100 - 1]


def measure_read_performance(
    opener,
    base_url: str,
    operations: dict[str, tuple[str, int]],
    *,
    clock=perf_counter_ns,
) -> dict[str, object]:
    summary: dict[str, object] = {}
    for operation, (path, threshold_milliseconds) in operations.items():
        samples: list[float] = []
        shape_hash = ""
        for index in range(PERFORMANCE_WARMUP_COUNT + PERFORMANCE_SAMPLE_COUNT):
            started = clock()
            result = _read(
                opener,
                base_url,
                path,
                key=f"performance-{operation}-{index}",
            )
            elapsed_milliseconds = (clock() - started) / 1_000_000
            shape_hash = canonical_hash(sorted(result.body))
            if index >= PERFORMANCE_WARMUP_COUNT:
                samples.append(elapsed_milliseconds)
        p95 = nearest_rank_p95(samples)
        require(
            p95 <= threshold_milliseconds,
            f"P9-03 {operation} P95 exceeded its engineering threshold",
        )
        summary[operation] = {
            "maxMs": round(max(samples), 3),
            "p95Ms": round(p95, 3),
            "responseShapeHash": shape_hash,
            "thresholdMs": threshold_milliseconds,
        }
    return {
        "clock": "perf_counter_ns",
        "environment": "disposable-local-frappe-site",
        "operations": summary,
        "percentileMethod": "nearest-rank",
        "sampleCount": PERFORMANCE_SAMPLE_COUNT,
        "warmupCount": PERFORMANCE_WARMUP_COUNT,
    }


def _uuid(value: object) -> bool:
    try:
        return str(UUID(str(value))) == str(value)
    except (TypeError, ValueError, AttributeError):
        return False


def _query(path: str, values: dict[str, object]) -> str:
    return f"{path}?{urllib.parse.urlencode(values)}"


def _read(opener, base_url: str, path: str, *, key: str):
    result = document_runtime.npi_request(
        opener, base_url, path, query_key=f"p902-{key}"
    )
    require(result.status == 200, f"P9-02 {key} query did not return HTTP 200")
    return result


def _command(
    opener,
    base_url: str,
    path: str,
    payload: dict[str, object],
    *,
    csrf: str,
    key: str,
    status: int,
):
    result = document_runtime.npi_request(
        opener,
        base_url,
        path,
        method="PUT" if path == "/api/npi/v1/me/preferences/notifications" else "POST",
        payload=payload,
        csrf_token=csrf,
        idempotency_key=key,
    )
    problem_code = result.body.get("code") if isinstance(result.body, dict) else None
    require(
        result.status == status,
        f"P9-02 command HTTP boundary drifted: status={result.status}; "
        f"code={problem_code or '-'}",
    )
    return result


def _meeting_payload(project_version: int) -> dict[str, object]:
    return {
        "expectedProjectVersion": project_version,
        "templateRef": {
            "globalId": STANDARD_MEETING_TEMPLATE["globalId"],
            "version": STANDARD_MEETING_TEMPLATE["version"],
            "snapshotHash": STANDARD_MEETING_TEMPLATE_HASH,
        },
        "title": MEETING_TITLE,
        "occurredAt": "2026-09-03T08:00:00Z",
        "attendeeUserIds": [ACTOR_USER],
        "sections": {
            "agenda": "Review the controlled reporting facts.",
            "discussion": "Confirm the permission-filtered Project view.",
            "decisions": "Retain the approved reporting boundary.",
        },
        "items": [],
    }


def _validate_inputs(base_url: object) -> tuple[str, str]:
    require(
        os.environ.get("NPI_P9_02D_RUNTIME_ENABLED") == "1"
        and os.environ.get("NPI_P9_02D_RUNTIME_ACTOR") == ACTOR_USER
        and os.environ.get("NPI_P9_02D_RUNTIME_LIMITED_ACTOR") == LIMITED_USER
        and os.environ.get("NPI_P9_02D_RUNTIME_PROJECT_ID") == PROJECT_ID,
        "P9-02 runtime environment drifted",
    )
    require(
        ACTOR_USER.endswith("@example.invalid")
        and LIMITED_USER.endswith("@example.invalid")
        and ACTOR_USER != LIMITED_USER
        and _uuid(PROJECT_ID)
        and not (ROOT / "tmp").is_symlink()
        and BENCH_PATH.is_dir()
        and not BENCH_PATH.is_symlink()
        and BENCH_PATH.resolve(strict=True) == ROOT / "tmp" / "frappe-bench",
        "P9-02 runtime fixture identity drifted",
    )
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
        "P9-02 runtime database environment drifted",
    )
    normalized = validate_local_fixture_inputs(
        str(base_url), "Administrator", ACTOR_USER
    )
    validate_local_fixture_inputs(str(base_url), "Administrator", LIMITED_USER)
    return normalized, secret_from_environment("NPI_RUNTIME_FIXTURE_PASSWORD")


def run_disabled(base_url: str, password: str) -> dict[str, bool]:
    actor = login(base_url, ACTOR_USER, password)
    portfolio = document_runtime.npi_request(
        actor, base_url, "/api/npi/v1/portfolio/projects", query_key="disabled"
    )
    meeting = document_runtime.npi_request(
        actor,
        base_url,
        f"/api/npi/v1/projects/{PROJECT_ID}/meetings",
        query_key="p902-disabled-meetings",
    )
    validate_problem(portfolio, 503, "REPORTING_ROUTES_DISABLED")
    validate_problem(meeting, 503, "REPORTING_ROUTES_DISABLED")
    return {"defaultDisabled": True}


def run_fresh(base_url: str, password: str) -> dict[str, bool]:
    actor = login(base_url, ACTOR_USER, password)
    csrf = bootstrap_csrf(actor, base_url, ACTOR_USER)
    limited = login(base_url, LIMITED_USER, password)
    limited_csrf = bootstrap_csrf(limited, base_url, LIMITED_USER)

    portfolio = _read(
        actor,
        base_url,
        _query("/api/npi/v1/portfolio/projects", {"limit": 100}),
        key="portfolio",
    ).body
    projects = [
        item
        for item in portfolio.get("items", [])
        if isinstance(item, dict) and item.get("globalId") == PROJECT_ID
    ]
    require(
        portfolio.get("permissions") == {"serverFiltered": True}
        and len(projects) == 1,
        "P9-02 permission-filtered portfolio drifted",
    )
    project = projects[0]
    project_version = project.get("version")
    business_code = project.get("businessCode")
    require(
        type(project_version) is int
        and project_version >= 1
        and isinstance(business_code, str)
        and business_code,
        "P9-02 retained Project reporting identity drifted",
    )

    empty = _read(
        actor,
        base_url,
        _query(
            "/api/npi/v1/portfolio/projects",
            {"customerReferenceKey": f"absent-{FIXTURE_RUN_ID}", "limit": 25},
        ),
        key="portfolio-empty",
    ).body
    require(empty.get("items") == [], "P9-02 empty portfolio truth drifted")

    search = _read(
        actor,
        base_url,
        _query(
            "/api/npi/v1/search",
            {"query": business_code, "kinds": "project", "limit": 25},
        ),
        key="search",
    ).body
    require(
        any(
            isinstance(item, dict)
            and item.get("globalId") == PROJECT_ID
            and item.get("kind") == "project"
            for item in search.get("items", [])
        ),
        "P9-02 global search did not return the authorized Project",
    )

    kpis = _read(
        actor,
        base_url,
        _query(
            "/api/npi/v1/reports/kpis",
            {"fromMonth": "2026-01", "toMonth": "2026-12"},
        ),
        key="kpis",
    ).body
    series = kpis.get("series")
    require(
        isinstance(series, list)
        and len(series) == 4
        and all(
            isinstance(item, dict)
            and item.get("availability") == "unavailable"
            and item.get("points") == []
            and isinstance(item.get("reasonCode"), str)
            for item in series
        ),
        "P9-02 unavailable KPI truth drifted",
    )

    catalog = _read(
        actor,
        base_url,
        "/api/npi/v1/administration/capabilities",
        key="configuration",
    ).body
    require(
        catalog.get("mode") == "read_only_catalog"
        and catalog.get("genericWriterAvailable") is False
        and isinstance(catalog.get("items"), list),
        "P9-02 read-only configuration catalog drifted",
    )
    performance = measure_read_performance(
        actor,
        base_url,
        {
            "configuration": (
                "/api/npi/v1/administration/capabilities",
                COMMON_READ_P95_MILLISECONDS,
            ),
            "kpiAvailability": (
                _query(
                    "/api/npi/v1/reports/kpis",
                    {"fromMonth": "2026-01", "toMonth": "2026-12"},
                ),
                COMMON_READ_P95_MILLISECONDS,
            ),
            "metadataSearch": (
                _query(
                    "/api/npi/v1/search",
                    {"query": business_code, "kinds": "project", "limit": 25},
                ),
                METADATA_SEARCH_P95_MILLISECONDS,
            ),
            "portfolio": (
                _query("/api/npi/v1/portfolio/projects", {"limit": 100}),
                COMMON_READ_P95_MILLISECONDS,
            ),
        },
    )
    print(
        "P9-03 non-production performance evidence "
        + json.dumps(performance, separators=(",", ":"), sort_keys=True)
    )
    denied_catalog = document_runtime.npi_request(
        limited,
        base_url,
        "/api/npi/v1/administration/capabilities",
        query_key="p902-limited-configuration",
    )
    validate_problem(denied_catalog, 403, "PERMISSION_DENIED")

    meeting_path = f"/api/npi/v1/projects/{PROJECT_ID}/meetings"
    initial_meetings = _read(
        actor, base_url, meeting_path, key="meetings-initial"
    ).body
    require(
        initial_meetings.get("projectVersion") == project_version,
        "P9-02 meeting Project version drifted",
    )
    payload = _meeting_payload(project_version)
    denied_meeting = document_runtime.npi_request(
        limited,
        base_url,
        meeting_path,
        method="POST",
        payload=payload,
        csrf_token=limited_csrf,
        idempotency_key=f"p9-limited-meeting-{FIXTURE_RUN_ID}",
    )
    validate_problem(denied_meeting, 403, "PERMISSION_DENIED")
    created = _command(
        actor,
        base_url,
        meeting_path,
        payload,
        csrf=csrf,
        key=MEETING_KEY,
        status=201,
    )
    meeting_id = created.body.get("globalId")
    require(
        _uuid(meeting_id)
        and created.body.get("projectId") == PROJECT_ID
        and created.body.get("title") == MEETING_TITLE
        and created.body.get("linkedItems") == []
        and created.body.get("version") == 1,
        "P9-02 immutable meeting response drifted",
    )
    replay = _command(
        actor,
        base_url,
        meeting_path,
        payload,
        csrf=csrf,
        key=MEETING_KEY,
        status=201,
    )
    require(replay.body == created.body, "P9-02 meeting retry was not idempotent")
    conflicting_payload = dict(payload)
    conflicting_payload["title"] = MEETING_TITLE + " changed"
    meeting_conflict = _command(
        actor,
        base_url,
        meeting_path,
        conflicting_payload,
        csrf=csrf,
        key=MEETING_KEY,
        status=409,
    )
    require(
        meeting_conflict.body.get("code") == "IDEMPOTENCY_KEY_CONFLICT",
        "P9-02 meeting idempotency conflict drifted",
    )
    stale_payload = dict(payload)
    stale_payload["expectedProjectVersion"] = project_version + 1
    stale_meeting = _command(
        actor,
        base_url,
        meeting_path,
        stale_payload,
        csrf=csrf,
        key=MEETING_STALE_KEY,
        status=409,
    )
    require(
        stale_meeting.body.get("code") == "VERSION_CONFLICT",
        "P9-02 meeting version conflict drifted",
    )

    scheduler = run_bench_fixture(
        "seed_notification", {"actor": ACTOR_USER, "project_id": PROJECT_ID}
    )
    notification_id = scheduler.get("notificationId")
    require(
        _uuid(notification_id)
        and scheduler.get("created") == 1
        and scheduler.get("duplicateCreated") == 0
        and scheduler.get("emailFailed") == 1,
        "P9-02 scheduler failure or duplicate suppression drifted",
    )
    feed = _read(
        actor,
        base_url,
        _query("/api/npi/v1/notifications", {"unreadOnly": "true", "limit": 100}),
        key="notifications",
    ).body
    notifications = [
        item
        for item in feed.get("items", [])
        if isinstance(item, dict) and item.get("globalId") == notification_id
    ]
    require(
        len(notifications) == 1
        and notifications[0].get("emailDeliveryState") == "failed"
        and notifications[0].get("failureCode") == "email_queue_failed"
        and notifications[0].get("readAt") is None,
        "P9-02 notification failure truth drifted",
    )
    notification = notifications[0]
    notification_version = notification.get("version")
    require(
        type(notification_version) is int and notification_version >= 1,
        "P9-02 notification version drifted",
    )
    notification_path = f"/api/npi/v1/notifications/{notification_id}:mark-read"
    marked = _command(
        actor,
        base_url,
        notification_path,
        {"expectedVersion": notification_version},
        csrf=csrf,
        key=NOTIFICATION_KEY,
        status=200,
    )
    require(
        marked.body.get("readAt") is not None
        and marked.body.get("version") == notification_version + 1,
        "P9-02 notification read outcome drifted",
    )
    marked_replay = _command(
        actor,
        base_url,
        notification_path,
        {"expectedVersion": notification_version},
        csrf=csrf,
        key=NOTIFICATION_KEY,
        status=200,
    )
    require(
        marked_replay.body == marked.body,
        "P9-02 notification read retry was not idempotent",
    )
    stale_notification = _command(
        actor,
        base_url,
        notification_path,
        {"expectedVersion": notification_version},
        csrf=csrf,
        key=NOTIFICATION_STALE_KEY,
        status=409,
    )
    require(
        stale_notification.body.get("code") == "VERSION_CONFLICT",
        "P9-02 stale notification update drifted",
    )

    preference_path = "/api/npi/v1/me/preferences/notifications"
    preference = _read(
        actor, base_url, preference_path, key="preference-initial"
    ).body
    require(
        preference.get("version") == 0
        and preference.get("criticalAuditEmail") is True
        and preference.get("criticalAuditMutable") is False,
        "P9-02 default notification preference drifted",
    )
    preference_payload = {"expectedVersion": 0, "emailKinds": ["due_reminder"]}
    saved_preference = _command(
        actor,
        base_url,
        preference_path,
        preference_payload,
        csrf=csrf,
        key=PREFERENCE_KEY,
        status=200,
    )
    require(
        saved_preference.body.get("version") == 1
        and saved_preference.body.get("emailKinds") == ["due_reminder"]
        and saved_preference.body.get("criticalAuditEmail") is True,
        "P9-02 notification preference update drifted",
    )
    preference_replay = _command(
        actor,
        base_url,
        preference_path,
        preference_payload,
        csrf=csrf,
        key=PREFERENCE_KEY,
        status=200,
    )
    require(
        preference_replay.body == saved_preference.body,
        "P9-02 notification preference retry was not idempotent",
    )
    stale_preference = _command(
        actor,
        base_url,
        preference_path,
        {"expectedVersion": 0, "emailKinds": ["overdue_escalation"]},
        csrf=csrf,
        key=PREFERENCE_STALE_KEY,
        status=409,
    )
    require(
        stale_preference.body.get("code") == "VERSION_CONFLICT",
        "P9-02 stale notification preference update drifted",
    )
    return {
        "configurationReadOnly": True,
        "duplicateSuppressed": True,
        "emptyPortfolio": True,
        "meetingIdempotent": True,
        "noPermission": True,
        "notificationFailureTruth": True,
        "notificationPreference": True,
        "reportingReadModel": True,
        "staleConflict": True,
        "unavailableKpis": True,
    }


def run_replay(base_url: str, password: str) -> dict[str, bool]:
    actor = login(base_url, ACTOR_USER, password)
    csrf = bootstrap_csrf(actor, base_url, ACTOR_USER)
    portfolio = _read(
        actor,
        base_url,
        _query("/api/npi/v1/portfolio/projects", {"limit": 100}),
        key="replay-portfolio",
    ).body
    project = next(
        (
            item
            for item in portfolio.get("items", [])
            if isinstance(item, dict) and item.get("globalId") == PROJECT_ID
        ),
        None,
    )
    require(isinstance(project, dict), "P9-02 replay Project truth is unavailable")
    meeting = _command(
        actor,
        base_url,
        f"/api/npi/v1/projects/{PROJECT_ID}/meetings",
        _meeting_payload(int(project["version"])),
        csrf=csrf,
        key=MEETING_KEY,
        status=201,
    )
    meetings = _read(
        actor,
        base_url,
        f"/api/npi/v1/projects/{PROJECT_ID}/meetings",
        key="replay-meetings",
    ).body
    require(
        sum(
            isinstance(item, dict) and item.get("globalId") == meeting.body.get("globalId")
            for item in meetings.get("items", [])
        )
        == 1,
        "P9-02 cross-process meeting replay created a duplicate",
    )
    feed = _read(
        actor,
        base_url,
        _query("/api/npi/v1/notifications", {"limit": 100}),
        key="replay-notifications",
    ).body
    require(
        any(
            isinstance(item, dict)
            and item.get("source", {}).get("globalId") == NOTIFICATION_SOURCE_ID
            and item.get("readAt") is not None
            and item.get("emailDeliveryState") == "failed"
            for item in feed.get("items", [])
        ),
        "P9-02 retained notification truth drifted",
    )
    preference = _read(
        actor,
        base_url,
        "/api/npi/v1/me/preferences/notifications",
        key="replay-preference",
    ).body
    require(
        preference.get("version") == 1
        and preference.get("emailKinds") == ["due_reminder"],
        "P9-02 retained notification preference drifted",
    )
    return {"crossProcessReplay": True}


def run_recovered(base_url: str, password: str) -> dict[str, bool]:
    actor = login(base_url, ACTOR_USER, password)
    meetings = _read(
        actor,
        base_url,
        f"/api/npi/v1/projects/{PROJECT_ID}/meetings",
        key="recovered-meetings",
    ).body
    require(
        sum(
            isinstance(item, dict) and item.get("title") == MEETING_TITLE
            for item in meetings.get("items", [])
        )
        == 1,
        "P9-02 route recovery lost retained meeting truth",
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
        require(completed.returncode == 0, "P9-02 Bench fixture failed")
        output.seek(0)
        lines = [line for line in output if line.strip()]
    require(len(lines) == 1, "P9-02 Bench fixture output drifted")
    result = json.loads(lines[0])
    require(isinstance(result, dict), "P9-02 Bench fixture result drifted")
    return result


def _require_bench_fixture(actor: object, project_id: object) -> tuple[str, str]:
    require(
        os.environ.get("NPI_P9_02D_RUNTIME_ENABLED") == "1"
        and actor == ACTOR_USER
        and project_id == PROJECT_ID
        and _uuid(project_id),
        "P9-02 Bench fixture environment drifted",
    )
    return str(actor), str(project_id)


def _seed_notification(*, actor: object, project_id: object) -> dict[str, object]:
    actor_id, project = _require_bench_fixture(actor, project_id)
    import frappe

    from npi_core.collaboration.frappe_repository import refresh_due_notifications

    now = datetime(2026, 9, 3, 9, 0, tzinfo=UTC)
    assignment = {
        "tenant_id": TENANT_ID,
        "actor_user_id": actor_id,
        "project_global_id": project,
        "source_type": "domain_work_item",
        "source_global_id": NOTIFICATION_SOURCE_ID,
        "source_version": 1,
        "category": "task",
        "due_at": datetime(2026, 9, 3, 8, 0, tzinfo=UTC),
        "priority_value": "critical",
        "blocking": 1,
    }
    original_get_all = frappe.get_all
    original_sendmail = frappe.sendmail

    def fixture_get_all(doctype: str, *args, **kwargs):
        if doctype == "NPI My Work Assignment":
            return [assignment]
        return original_get_all(doctype, *args, **kwargs)

    def failed_sendmail(**_kwargs):
        raise RuntimeError("Synthetic local email queue failure")

    frappe.get_all = fixture_get_all
    frappe.sendmail = failed_sendmail
    try:
        first = refresh_due_notifications(now)
        second = refresh_due_notifications(now)
    finally:
        frappe.get_all = original_get_all
        frappe.sendmail = original_sendmail
    rows = frappe.get_all(
        "NPI Internal Notification",
        filters={
            "tenant_id": TENANT_ID,
            "recipient_user_id": actor_id,
            "source_global_id": NOTIFICATION_SOURCE_ID,
        },
        fields=["global_id", "email_delivery_state", "failure_code"],
        limit_page_length=2,
    )
    require(
        len(rows) == 1
        and rows[0].email_delivery_state == "failed"
        and rows[0].failure_code == "email_queue_failed",
        "P9-02 notification scheduler fixture drifted",
    )
    return {
        "created": first["created"],
        "duplicateCreated": second["created"],
        "emailFailed": first["emailFailed"],
        "notificationId": str(rows[0].global_id),
    }


def _cleanup(*, actor: object, project_id: object) -> dict[str, bool]:
    actor_id, project = _require_bench_fixture(actor, project_id)
    import frappe

    meeting_ids = frappe.get_all(
        "NPI Meeting Minute",
        filters={"project_global_id": project, "title": MEETING_TITLE},
        pluck="global_id",
        limit_page_length=2,
    )
    notification_ids = frappe.get_all(
        "NPI Internal Notification",
        filters={
            "recipient_user_id": actor_id,
            "source_global_id": NOTIFICATION_SOURCE_ID,
        },
        pluck="global_id",
        limit_page_length=2,
    )
    preference_ids = frappe.get_all(
        "NPI Notification Preference",
        filters={"tenant_id": TENANT_ID, "user_id": actor_id},
        pluck="global_id",
        limit_page_length=2,
    )
    controlled_ids = [
        *(str(value) for value in meeting_ids),
        *(str(value) for value in notification_ids),
        *(str(value) for value in preference_ids),
    ]
    if meeting_ids:
        frappe.db.delete(
            "NPI Meeting Work Link",
            {"meeting_global_id": ["in", meeting_ids]},
        )
    if controlled_ids:
        frappe.db.delete("NPI Audit Event", {"global_id": ["in", controlled_ids]})
    frappe.db.delete(
        "NPI Collaboration Idempotency",
        {
            "tenant_id": TENANT_ID,
            "actor": actor_id,
            "operation": [
                "in",
                [
                    "meeting_minute.create",
                    "notification.mark_read",
                    "notification_preference.set",
                ],
            ],
        },
    )
    frappe.db.delete(
        "NPI Meeting Minute",
        {"project_global_id": project, "title": MEETING_TITLE},
    )
    frappe.db.delete(
        "NPI Internal Notification",
        {
            "recipient_user_id": actor_id,
            "source_global_id": NOTIFICATION_SOURCE_ID,
        },
    )
    frappe.db.delete(
        "NPI Notification Preference",
        {"tenant_id": TENANT_ID, "user_id": actor_id},
    )
    remaining = sum(
        frappe.db.count(doctype, filters)
        for doctype, filters in (
            (
                "NPI Meeting Minute",
                {"project_global_id": project, "title": MEETING_TITLE},
            ),
            (
                "NPI Internal Notification",
                {
                    "recipient_user_id": actor_id,
                    "source_global_id": NOTIFICATION_SOURCE_ID,
                },
            ),
            (
                "NPI Notification Preference",
                {"tenant_id": TENANT_ID, "user_id": actor_id},
            ),
            (
                "NPI Collaboration Idempotency",
                {
                    "tenant_id": TENANT_ID,
                    "actor": actor_id,
                    "operation": [
                        "in",
                        [
                            "meeting_minute.create",
                            "notification.mark_read",
                            "notification_preference.set",
                        ],
                    ],
                },
            ),
        )
    )
    require(remaining == 0, "P9-02 cleanup left exact collaboration fixtures")
    return {"cleanupComplete": True}


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    import frappe

    fixtures = {"cleanup": _cleanup, "seed_notification": _seed_notification}
    require(method in fixtures, "P9-02 Bench fixture is unavailable")
    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    try:
        document_runtime._validated_runtime_site()
        require(
            frappe.conf.get("npi_runtime_disposable_marker") == RUNTIME_MARKER,
            "P9-02 disposable Site marker drifted",
        )
        frappe.set_user("Administrator")
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
    parser.add_argument("--disabled-probe", action="store_true")
    parser.add_argument("--replay-only", action="store_true")
    parser.add_argument("--recovered-probe", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--bench-fixture")
    parser.add_argument("--fixture-kwargs")
    arguments = parser.parse_args()
    if arguments.bench_fixture:
        require(
            arguments.base_url is None
            and arguments.fixture_kwargs is not None
            and not any(
                (
                    arguments.disabled_probe,
                    arguments.replay_only,
                    arguments.recovered_probe,
                    arguments.cleanup,
                )
            ),
            "P9-02 Bench fixture invocation drifted",
        )
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "P9-02 Bench fixture arguments drifted")
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return 0
    require(
        isinstance(arguments.base_url, str)
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
        "P9-02 runtime invocation drifted",
    )
    base_url, password = _validate_inputs(arguments.base_url)
    if arguments.disabled_probe:
        result = run_disabled(base_url, password)
    elif arguments.replay_only:
        result = run_replay(base_url, password)
    elif arguments.recovered_probe:
        result = run_recovered(base_url, password)
    elif arguments.cleanup:
        result = run_bench_fixture(
            "cleanup", {"actor": ACTOR_USER, "project_id": PROJECT_ID}
        )
    else:
        result = run_fresh(base_url, password)
    require(
        result and all(value is True for value in result.values()),
        "P9-02 runtime result drifted",
    )
    print("local Frappe reporting and collaboration runtime verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
