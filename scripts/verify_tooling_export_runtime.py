from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import verify_document_runtime as document_runtime
import verify_tooling_import_runtime as predecessor
from verify_frappe_runtime import (
    HttpResult,
    login,
    require,
    secret_from_environment,
    set_language,
    validate_local_fixture_inputs,
    validate_problem,
)
from verify_project_runtime import (
    bootstrap_csrf,
    delete_resource,
    get_resource,
    update_resource,
)


ROOT = Path(__file__).resolve().parents[1]
BENCH_PATH = ROOT / "tmp" / "frappe-bench"
SITE_NAME = document_runtime.SITE_NAME
RUNTIME_MARKER = document_runtime.RUNTIME_MARKER
FIXTURE_RUN_ID = document_runtime.FIXTURE_RUN_ID
TENANT_ID = document_runtime.TENANT_ID
ACTOR_USER = predecessor.ACTOR_USER
UNRELATED_USER = f"npi-tooling-export-{FIXTURE_RUN_ID[:12]}-unrelated@example.invalid"
ABSENT_PROJECT_ID = "00000000-0000-4000-8000-000000000041"
ABSENT_PACKAGE_ID = "00000000-0000-4000-8000-000000000042"
FORMULA_MASTER_TITLE = "=P6-08 controlled formula sentinel"
FORMULA_MASTER_KEY = f"p6-08-runtime-{FIXTURE_RUN_ID}-formula-master"
EXPIRED_CREATE_KEY = f"p6-08-runtime-{FIXTURE_RUN_ID}-expired-create"
EXPIRED_DOWNLOAD_KEY = f"p6-08-runtime-{FIXTURE_RUN_ID}-expired-download"
STALE_SELECTION_KEY = f"p6-08-runtime-{FIXTURE_RUN_ID}-stale-selection"
STALE_FILTER_KEY = f"p6-08-runtime-{FIXTURE_RUN_ID}-stale-filter"
CONFLICT_CREATE_KEY = f"p6-08-runtime-{FIXTURE_RUN_ID}-create-conflict"
PACKAGE_CASES = (
    ("en", "selection"),
    ("zh", "selection"),
    ("zh-TW", "filtered"),
)
VIEW_IDS = (
    "all",
    "missing_applicability",
    "single_part",
    "shared_parts",
    "missing_physical_set",
    "single_physical_set",
    "multiple_physical_sets",
    "missing_design_revision",
    "has_design_revision",
    "customer_owned_set",
)
PACKAGE_MEMBERS = ("manifest.json", "tooling-objects.csv", "README.txt")
OMITTED_FIELD_CLASSES = (
    "raw_file_url_and_content",
    "raw_workbook_values",
    "external_customer_or_supplier_identifiers",
    "repair_custody_or_return_text",
    "cost",
    "evidence",
    "erp_or_lifecycle_truth",
)
LOCALIZED_EXPECTATIONS = {
    "en": ("Project code", "Tooling title", "Tooling object package"),
    "zh": ("项目编码", "模具标题", "模具对象包"),
    "zh-TW": ("專案編碼", "模具標題", "模具物件包"),
}
EXPORT_DOCTYPES = (
    "NPI Tooling List Preference",
    "NPI Tooling Export Package",
    "NPI Tooling Export Command Idempotency",
)


def deterministic_uuid(label: str) -> str:
    seeded = uuid5(NAMESPACE_URL, f"npi-one:p6-08:{FIXTURE_RUN_ID}:{label}")
    return str(UUID(int=seeded.int, version=4))


def list_path(project_id: str, **values: object) -> str:
    base = f"/api/npi/v1/projects/{project_id}/tooling-list"
    query = {key: value for key, value in values.items() if value is not None}
    return base if not query else f"{base}?{urllib.parse.urlencode(query)}"


def preference_path(project_id: str, view_id: str) -> str:
    return f"{list_path(project_id)}/preferences/{view_id}"


def exports_path(project_id: str) -> str:
    return f"/api/npi/v1/projects/{project_id}/tooling-exports"


def package_content_path(project_id: str, package_id: str) -> str:
    return f"{exports_path(project_id)}/{package_id}:content"


def create_key(language: str) -> str:
    return f"p6-08-runtime-{FIXTURE_RUN_ID}-{language}-create"


def download_key(language: str) -> str:
    return f"p6-08-runtime-{FIXTURE_RUN_ID}-{language}-download"


def json_request(
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
        document_runtime.command_headers(csrf_token, idempotency_key)
        if idempotency_key is not None
        else document_runtime.query_headers(f"p608-{query_key}")
    )
    if csrf_token is not None:
        headers["X-Frappe-CSRF-Token"] = csrf_token
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
        "P6-08 request identity was not echoed",
    )
    require(
        result.headers.get("Cache-Control") == "private, no-store",
        "P6-08 private no-store response drifted",
    )
    return HttpResult(
        result.status,
        result.headers,
        result.body,
        request_id=headers["X-Request-ID"],
        trace_id=headers["X-Trace-ID"],
    )


def binary_request(
    opener,
    base_url: str,
    path: str,
    *,
    csrf_token: str,
    idempotency_key: str,
    expected_snapshot_hash: str,
) -> document_runtime.BinaryHttpResult:
    headers = document_runtime.command_headers(csrf_token, idempotency_key)
    headers["Content-Type"] = "application/json"
    body = json.dumps(
        {"expectedSnapshotHash": expected_snapshot_hash},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with opener.open(request, timeout=30) as response:
            result = document_runtime.BinaryHttpResult(
                response.status,
                response.headers,
                response.read(),
                None,
            )
    except urllib.error.HTTPError as error:
        content = error.read()
        result = document_runtime.BinaryHttpResult(
            error.code,
            error.headers,
            content,
            json.loads(content.decode("utf-8")),
        )
    require(
        result.headers.get("X-Request-ID") == headers["X-Request-ID"],
        "P6-08 binary request identity was not echoed",
    )
    require(
        result.headers.get("Cache-Control") == "private, no-store",
        "P6-08 binary private no-store response drifted",
    )
    return result


def rows(opener, base_url: str, doctype: str, filters, fields=None):
    return predecessor.rows(opener, base_url, doctype, filters, fields)


def exact_single(values, label: str):
    return predecessor.exact_single(values, label)


def require_uuid(value: object, label: str) -> str:
    require(
        isinstance(value, str) and str(UUID(value)) == value,
        f"{label} identity drifted",
    )
    return value


def require_hash(value: object, label: str) -> str:
    require(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value),
        f"{label} hash drifted",
    )
    return value


def query_list(
    opener,
    base_url: str,
    project_id: str,
    *,
    view_id: str = "all",
    search: str = "",
    sort_key: str = "title",
    sort_direction: str = "asc",
    group_key: str = "none",
    page_size: int = 100,
    cursor: str | None = None,
    query_key: str = "list",
) -> HttpResult:
    return json_request(
        opener,
        base_url,
        list_path(
            project_id,
            viewId=view_id,
            search=search,
            sortKey=sort_key,
            sortDirection=sort_direction,
            groupKey=group_key,
            pageSize=page_size,
            cursor=cursor,
        ),
        query_key=query_key,
    )


def assert_list(result: HttpResult, project_id: str) -> dict[str, Any]:
    problem_code = result.body.get("code")
    require(
        result.status == 200,
        (
            f"P6-08 Tooling List returned HTTP {result.status} "
            f"with code {problem_code if isinstance(problem_code, str) else 'unavailable'}"
        ),
    )
    value = result.body
    items = value.get("items")
    permissions = value.get("permissions")
    require(
        value.get("projectGlobalId") == project_id
        and isinstance(value.get("filter"), dict)
        and isinstance(value.get("querySnapshotHash"), str)
        and isinstance(value.get("totalCount"), int)
        and isinstance(items, list)
        and isinstance(permissions, dict)
        and permissions.get("view") is True
        and permissions.get("canExport") is True,
        "P6-08 Tooling List projection drifted",
    )
    identities: set[str] = set()
    for item in items:
        require(isinstance(item, dict), "P6-08 Tooling List row drifted")
        identity = require_uuid(item.get("toolingMasterGlobalId"), "P6-08 Master")
        require(identity not in identities, "P6-08 Tooling List row duplicated")
        identities.add(identity)
        require_hash(item.get("toolingMasterSnapshotHash"), "P6-08 Master")
        require(
            item.get("projectGlobalId") == project_id
            and item.get("source") in {"manual", "controlled_xlsx_import"},
            "P6-08 Project-relative row truth drifted",
        )
    return value


def matches_view(row: dict[str, Any], view_id: str) -> bool:
    return {
        "all": True,
        "missing_applicability": row.get("applicabilityCount") == 0,
        "single_part": row.get("distinctPartRevisionCount") == 1,
        "shared_parts": int(row.get("distinctPartRevisionCount", 0)) > 1,
        "missing_physical_set": row.get("physicalSetCount") == 0,
        "single_physical_set": row.get("physicalSetCount") == 1,
        "multiple_physical_sets": int(row.get("physicalSetCount", 0)) > 1,
        "missing_design_revision": row.get("designRevisionCount") == 0,
        "has_design_revision": int(row.get("designRevisionCount", 0)) > 0,
        "customer_owned_set": row.get("customerOwnedSet") is True,
    }[view_id]


def seed_formula_master(
    actor,
    base_url: str,
    csrf_token: str,
    project_id: str,
) -> dict[str, Any]:
    result = json_request(
        actor,
        base_url,
        f"/api/npi/v1/projects/{project_id}/tooling-masters",
        method="POST",
        payload={"title": FORMULA_MASTER_TITLE},
        csrf_token=csrf_token,
        idempotency_key=FORMULA_MASTER_KEY,
    )
    require(
        result.status == 201
        and result.headers.get("Idempotency-Replayed") == "false",
        "P6-08 formula-neutralization Master was not created",
    )
    masters = result.body.get("masters")
    require(isinstance(masters, list), "P6-08 Master workspace drifted")
    master = exact_single(
        [item for item in masters if item.get("title") == FORMULA_MASTER_TITLE],
        "P6-08 formula-neutralization Master",
    )
    require_uuid(master.get("globalId"), "P6-08 formula-neutralization Master")
    return master


def verify_views_and_paging(
    actor,
    base_url: str,
    project_id: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    all_result = assert_list(
        query_list(actor, base_url, project_id, query_key="all"),
        project_id,
    )
    all_rows = all_result["items"]
    require(
        all_result["totalCount"] == len(all_rows)
        and 1 <= len(all_rows) <= 100,
        "P6-08 bounded complete Tooling List drifted",
    )
    view_counts: dict[str, int] = {}
    for view_id in VIEW_IDS:
        value = assert_list(
            query_list(
                actor,
                base_url,
                project_id,
                view_id=view_id,
                query_key=f"view-{view_id}",
            ),
            project_id,
        )
        expected = {
            item["toolingMasterGlobalId"]
            for item in all_rows
            if matches_view(item, view_id)
        }
        actual = {item["toolingMasterGlobalId"] for item in value["items"]}
        require(
            actual == expected and value["totalCount"] == len(expected),
            f"P6-08 {view_id} membership drifted",
        )
        view_counts[view_id] = len(actual)
    observed_sources = {item.get("source") for item in all_rows}
    require(
        view_counts["missing_applicability"] >= 1
        and view_counts["missing_physical_set"] >= 1
        and view_counts["missing_design_revision"] >= 1
        and view_counts["customer_owned_set"] >= 1
        and "manual" in observed_sources
        and observed_sources <= {"manual", "controlled_xlsx_import"},
        "P6-08 controlled view fixture coverage drifted",
    )
    first = assert_list(
        query_list(
            actor,
            base_url,
            project_id,
            page_size=1,
            query_key="page-one",
        ),
        project_id,
    )
    require(
        len(first["items"]) == 1 and isinstance(first.get("nextCursor"), str),
        "P6-08 first stable page drifted",
    )
    second = assert_list(
        query_list(
            actor,
            base_url,
            project_id,
            page_size=1,
            cursor=str(first["nextCursor"]),
            query_key="page-two",
        ),
        project_id,
    )
    require(
        second["querySnapshotHash"] == first["querySnapshotHash"]
        and second["totalCount"] == first["totalCount"]
        and second["items"][0]["toolingMasterGlobalId"]
        != first["items"][0]["toolingMasterGlobalId"],
        "P6-08 stable cursor paging drifted",
    )
    stale_cursor = query_list(
        actor,
        base_url,
        project_id,
        search=FORMULA_MASTER_TITLE,
        page_size=1,
        cursor=str(first["nextCursor"]),
        query_key="stale-cursor",
    )
    validate_problem(stale_cursor, 422, "VALIDATION_FAILED")
    return all_rows, view_counts


def preference_payload(view_id: str) -> dict[str, object]:
    return {
        "gridId": "tooling-list",
        "tableSchemaVersion": "tooling-list-grid-v1",
        "viewId": view_id,
        "filter": {
            "viewId": view_id,
            "search": "",
            "sortKey": "title",
            "sortDirection": "asc",
            "groupKey": "none",
        },
        "columnOrder": [
            "selection",
            "tooling",
            "applicability",
            "part_revisions",
            "physical_sets",
            "design_revisions",
            "origin",
            "source",
            "action",
        ],
        "hiddenColumns": ["origin"],
        "columnWidths": [{"columnId": "tooling", "width": 272}],
    }


def preference_save_diagnostic(
    result: HttpResult,
    expected_preference: dict[str, object],
) -> str:
    problem_code = result.body.get("code")
    return (
        "P6-08 saved preference truth drifted: "
        f"HTTP {result.status}; "
        f"code={problem_code if isinstance(problem_code, str) else 'unavailable'}; "
        f"storedTrue={result.body.get('stored') is True}; "
        f"versionOne={result.body.get('optimisticVersion') == 1}; "
        f"snapshotHashValid={isinstance(result.body.get('snapshotHash'), str) and len(result.body['snapshotHash']) == 64}; "
        f"preferenceMatches={result.body.get('preference') == expected_preference}"
        f"{document_runtime.sanitized_http_failure(result)}"
    )


def verify_preference(
    actor,
    base_url: str,
    csrf_token: str,
    project_id: str,
) -> dict[str, Any]:
    path = preference_path(project_id, "shared_parts")
    empty = json_request(actor, base_url, path, query_key="preference-empty")
    require(
        empty.status == 200
        and empty.body.get("stored") is False
        and empty.body.get("optimisticVersion") == 0,
        "P6-08 fresh preference truth drifted",
    )
    payload = {
        "expectedVersion": 0,
        "expectedSnapshotHash": None,
        "preference": preference_payload("shared_parts"),
    }
    saved = json_request(
        actor,
        base_url,
        path,
        method="PUT",
        payload=payload,
        csrf_token=csrf_token,
        query_key="preference-save",
    )
    require(
        saved.status == 200
        and saved.body.get("stored") is True
        and saved.body.get("optimisticVersion") == 1
        and saved.body.get("preference") == payload["preference"],
        preference_save_diagnostic(saved, payload["preference"]),
    )
    require_hash(saved.body.get("snapshotHash"), "P6-08 preference")
    retained = json_request(actor, base_url, path, query_key="preference-retained")
    require(retained.body == saved.body, "P6-08 retained preference drifted")
    conflict = json_request(
        actor,
        base_url,
        path,
        method="PUT",
        payload=payload,
        csrf_token=csrf_token,
        query_key="preference-conflict",
    )
    validate_problem(conflict, 409, "TOOLING_VERSION_CONFLICT")
    return saved.body


def formula_row(rows_value: list[dict[str, Any]]) -> dict[str, Any]:
    return exact_single(
        [item for item in rows_value if item.get("title") == FORMULA_MASTER_TITLE],
        "P6-08 formula-neutralization list row",
    )


def export_payload(
    actor,
    base_url: str,
    project_id: str,
    mode: str,
) -> dict[str, object]:
    if mode == "selection":
        row = formula_row(
            assert_list(
                query_list(actor, base_url, project_id, query_key="selection-source"),
                project_id,
            )["items"]
        )
        return {
            "mode": "selection",
            "selection": [
                {
                    "toolingMasterGlobalId": row["toolingMasterGlobalId"],
                    "snapshotHash": row["toolingMasterSnapshotHash"],
                }
            ],
        }
    filtered = assert_list(
        query_list(
            actor,
            base_url,
            project_id,
            search=FORMULA_MASTER_TITLE,
            query_key="filtered-source",
        ),
        project_id,
    )
    require(
        filtered["totalCount"] == 1
        and filtered["items"][0]["title"] == FORMULA_MASTER_TITLE,
        "P6-08 complete filtered source drifted",
    )
    return {
        "mode": "filtered",
        "filter": filtered["filter"],
        "querySnapshotHash": filtered["querySnapshotHash"],
    }


def create_package(
    actor,
    base_url: str,
    csrf_token: str,
    project_id: str,
    payload: dict[str, object],
    key: str,
    *,
    replayed: str,
) -> tuple[HttpResult, dict[str, Any]]:
    result = json_request(
        actor,
        base_url,
        exports_path(project_id),
        method="POST",
        payload=payload,
        csrf_token=csrf_token,
        idempotency_key=key,
    )
    package = result.body.get("package")
    require(
        result.status == 201
        and result.headers.get("Idempotency-Replayed") == replayed
        and isinstance(package, dict),
        "P6-08 package creation/replay truth drifted",
    )
    require(
        "/private/files/" not in repr(result.body)
        and "fileUrl" not in repr(result.body)
        and "frappeFileId" not in repr(result.body),
        "P6-08 package response exposed a private File identity",
    )
    return result, package


def validate_package_content(
    package: dict[str, Any],
    downloaded: document_runtime.BinaryHttpResult,
    *,
    project_id: str,
    language: str,
    mode: str,
    replayed: str,
) -> dict[str, object]:
    package_id = require_uuid(package.get("globalId"), "P6-08 package")
    package_hash = require_hash(package.get("sha256"), "P6-08 package content")
    snapshot_hash = require_hash(package.get("snapshotHash"), "P6-08 package")
    manifest_hash = require_hash(package.get("manifestSha256"), "P6-08 manifest")
    generated_at = datetime.fromisoformat(str(package["generatedAt"]).replace("Z", "+00:00"))
    expires_at = datetime.fromisoformat(str(package["expiresAt"]).replace("Z", "+00:00"))
    require(
        package.get("projectGlobalId") == project_id
        and package.get("createdByUserId") == ACTOR_USER
        and package.get("language") == language
        and package.get("mode") == mode
        and package.get("objectCount") == 1
        and package.get("confidentialityClass") == "internal_project"
        and package.get("mimeType") == "application/zip"
        and expires_at - generated_at == timedelta(hours=1)
        and downloaded.status == 200
        and downloaded.problem is None
        and downloaded.headers.get("Idempotency-Replayed") == replayed
        and downloaded.headers.get("Content-Type") == "application/zip"
        and downloaded.headers.get("X-Content-Type-Options") == "nosniff"
        and downloaded.headers.get("Content-Security-Policy")
        == "sandbox; default-src 'none'"
        and "attachment" in str(downloaded.headers.get("Content-Disposition")),
        "P6-08 package/download public truth drifted",
    )
    require(
        len(downloaded.content) == package.get("sizeBytes")
        and hashlib.sha256(downloaded.content).hexdigest() == package_hash,
        "P6-08 package byte identity drifted",
    )
    with zipfile.ZipFile(io.BytesIO(downloaded.content), "r") as archive:
        require(
            tuple(archive.namelist()) == PACKAGE_MEMBERS,
            "P6-08 fixed package member set drifted",
        )
        members = {name: archive.read(name) for name in PACKAGE_MEMBERS}
    require(
        hashlib.sha256(members["manifest.json"]).hexdigest() == manifest_hash,
        "P6-08 manifest hash drifted",
    )
    manifest = json.loads(members["manifest.json"].decode("utf-8"))
    require(
        manifest.get("schemaVersion") == "tooling-object-package-v1"
        and manifest.get("packageGlobalId") == package_id
        and manifest.get("projectGlobalId") == project_id
        and manifest.get("createdByUserId") == ACTOR_USER
        and manifest.get("language") == language
        and manifest.get("mode") == mode
        and manifest.get("rowCount") == 1
        and tuple(manifest.get("omittedFieldClasses", [])) == OMITTED_FIELD_CLASSES
        and manifest.get("objectRefs") == package.get("objectRefs")
        and manifest.get("querySnapshotHash") == package.get("querySnapshotHash"),
        "P6-08 immutable manifest truth drifted",
    )
    declared_members = manifest.get("members")
    require(
        isinstance(declared_members, list)
        and {item.get("name") for item in declared_members}
        == {"tooling-objects.csv", "README.txt"},
        "P6-08 manifest member declaration drifted",
    )
    for item in declared_members:
        content = members[str(item["name"])]
        require(
            item.get("sizeBytes") == len(content)
            and item.get("sha256") == hashlib.sha256(content).hexdigest(),
            "P6-08 member hash drifted",
        )
    csv_rows = list(
        csv.reader(
            io.StringIO(
                members["tooling-objects.csv"].decode("utf-8-sig"),
                newline="",
            )
        )
    )
    expected_project, expected_title, expected_readme = LOCALIZED_EXPECTATIONS[language]
    require(
        len(csv_rows) == 2
        and csv_rows[0][0] == expected_project
        and csv_rows[0][2] == expected_title
        and csv_rows[1][2] == "'" + FORMULA_MASTER_TITLE,
        "P6-08 localized CSV or formula neutralization drifted",
    )
    readme = members["README.txt"].decode("utf-8")
    require(
        readme.splitlines()[0] == expected_readme
        and "/private/files/" not in repr(members)
        and "frappeFileId" not in repr(members),
        "P6-08 localized README or redaction boundary drifted",
    )
    return {
        "language": language,
        "mode": mode,
        "packageGlobalId": package_id,
        "packageSha256": package_hash,
        "snapshotHash": snapshot_hash,
    }


def set_actor_language(
    actor,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
    language: str,
):
    changed = set_language(actor, base_url, language, csrf_token)
    require(
        changed.status == 200 and changed.body.get("language") == language,
        "P6-08 actor language change drifted",
    )
    refreshed = login(base_url, ACTOR_USER, fixture_password)
    refreshed_csrf = bootstrap_csrf(refreshed, base_url, ACTOR_USER)
    return refreshed, refreshed_csrf


def verify_stale_and_conflict(
    actor,
    base_url: str,
    csrf_token: str,
    project_id: str,
) -> None:
    selection = export_payload(actor, base_url, project_id, "selection")
    stale_selection = json.loads(json.dumps(selection))
    stale_selection["selection"][0]["snapshotHash"] = "0" * 64
    stale = json_request(
        actor,
        base_url,
        exports_path(project_id),
        method="POST",
        payload=stale_selection,
        csrf_token=csrf_token,
        idempotency_key=STALE_SELECTION_KEY,
    )
    validate_problem(stale, 422, "VALIDATION_FAILED")
    filtered = export_payload(actor, base_url, project_id, "filtered")
    stale_filtered = dict(filtered)
    stale_filtered["querySnapshotHash"] = "0" * 64
    stale = json_request(
        actor,
        base_url,
        exports_path(project_id),
        method="POST",
        payload=stale_filtered,
        csrf_token=csrf_token,
        idempotency_key=STALE_FILTER_KEY,
    )
    validate_problem(stale, 422, "VALIDATION_FAILED")
    conflict = json_request(
        actor,
        base_url,
        exports_path(project_id),
        method="POST",
        payload=filtered,
        csrf_token=csrf_token,
        idempotency_key=create_key("en"),
    )
    validate_problem(conflict, 409, "TOOLING_IDEMPOTENCY_CONFLICT")


def verify_idor(
    actor,
    administrator,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
    project_id: str,
    package: dict[str, Any],
) -> None:
    guest = query_list(
        urllib.request.build_opener(),
        base_url,
        project_id,
        query_key="guest",
    )
    validate_problem(guest, 401, "AUTHENTICATION_REQUIRED")
    document_runtime.create_internal_fixture_user(
        actor,
        base_url,
        UNRELATED_USER,
        fixture_password,
        csrf_token,
    )
    try:
        unrelated = login(base_url, UNRELATED_USER, fixture_password)
        unrelated_csrf = bootstrap_csrf(unrelated, base_url, UNRELATED_USER)
        denied = query_list(
            unrelated,
            base_url,
            project_id,
            query_key="unrelated-project",
        )
        absent = query_list(
            unrelated,
            base_url,
            ABSENT_PROJECT_ID,
            query_key="unrelated-absent",
        )
        validate_problem(denied, 404, "TOOLING_UNAVAILABLE")
        validate_problem(absent, 404, "TOOLING_UNAVAILABLE")
        require(
            {
                key: denied.body.get(key)
                for key in ("type", "title", "status", "code", "retryable")
            }
            == {
                key: absent.body.get(key)
                for key in ("type", "title", "status", "code", "retryable")
            },
            "P6-08 unauthorized and absent list scopes are distinguishable",
        )
        denied_export = json_request(
            unrelated,
            base_url,
            exports_path(project_id),
            method="POST",
            payload={"mode": "selection", "selection": package["objectRefs"]},
            csrf_token=unrelated_csrf,
            idempotency_key=f"p6-08-runtime-{FIXTURE_RUN_ID}-unrelated-create",
        )
        validate_problem(denied_export, 403, "PERMISSION_DENIED")
    finally:
        document_runtime.delete_disposable_user(
            actor,
            base_url,
            UNRELATED_USER,
            csrf_token,
        )
    creator_denied = binary_request(
        administrator,
        base_url,
        package_content_path(project_id, str(package["globalId"])),
        csrf_token=bootstrap_csrf(administrator, base_url, "Administrator"),
        idempotency_key=f"p6-08-runtime-{FIXTURE_RUN_ID}-noncreator-download",
        expected_snapshot_hash=str(package["snapshotHash"]),
    )
    require(
        creator_denied.status == 404
        and creator_denied.problem is not None
        and creator_denied.problem.get("code") == "TOOLING_UNAVAILABLE",
        "P6-08 non-creator download was not denied",
    )
    projects = rows(
        actor,
        base_url,
        "NPI Engineering Project",
        [["global_id", "!=", project_id]],
        ["global_id"],
    )
    require(bool(projects), "P6-08 cross-Project fixture is unavailable")
    cross_project_id = str(projects[0]["global_id"])
    cross_project = binary_request(
        actor,
        base_url,
        package_content_path(cross_project_id, str(package["globalId"])),
        csrf_token=csrf_token,
        idempotency_key=f"p6-08-runtime-{FIXTURE_RUN_ID}-cross-project-download",
        expected_snapshot_hash=str(package["snapshotHash"]),
    )
    require(
        cross_project.status == 404
        and cross_project.problem is not None
        and cross_project.problem.get("code") == "TOOLING_UNAVAILABLE",
        "P6-08 cross-Project package was not denied",
    )
    wrong_hash = binary_request(
        actor,
        base_url,
        package_content_path(project_id, str(package["globalId"])),
        csrf_token=csrf_token,
        idempotency_key=f"p6-08-runtime-{FIXTURE_RUN_ID}-wrong-hash-download",
        expected_snapshot_hash="0" * 64,
    )
    require(
        wrong_hash.status == 404
        and wrong_hash.problem is not None
        and wrong_hash.problem.get("code") == "TOOLING_UNAVAILABLE",
        "P6-08 wrong-hash package download was not denied",
    )


def persisted_counts(opener, base_url: str, project_id: str) -> dict[str, int]:
    result = {
        doctype: len(
            rows(
                opener,
                base_url,
                doctype,
                [["project_global_id", "=", project_id]],
                ["global_id"],
            )
        )
        for doctype in EXPORT_DOCTYPES
    }
    result["createAudit"] = len(
        rows(
            opener,
            base_url,
            "NPI Audit Event",
            [["operation", "=", "tooling_export_package.create"]],
            ["global_id"],
        )
    )
    result["downloadAudit"] = len(
        rows(
            opener,
            base_url,
            "NPI Audit Event",
            [["operation", "=", "tooling_export_package.download"]],
            ["global_id"],
        )
    )
    result["preferenceAudit"] = len(
        rows(
            opener,
            base_url,
            "NPI Audit Event",
            [["operation", "=", "tooling_list_preference.save"]],
            ["global_id"],
        )
    )
    result["outbox"] = len(
        rows(opener, base_url, "NPI Outbox Message", [], ["event_id"])
    )
    result["inbox"] = len(
        rows(opener, base_url, "NPI Inbox Message", [], ["event_id"])
    )
    return result


def verify_generic_mutation_denial(
    actor,
    base_url: str,
    csrf_token: str,
    project_id: str,
) -> None:
    for doctype in EXPORT_DOCTYPES:
        retained_rows = rows(
            actor,
            base_url,
            doctype,
            [["project_global_id", "=", project_id]],
            ["global_id", "snapshot_hash"],
        )
        require(bool(retained_rows), f"P6-08 retained {doctype} is unavailable")
        retained = retained_rows[0]
        name = str(retained["global_id"])
        before = get_resource(actor, base_url, doctype, name)
        rejected_update = update_resource(
            actor,
            base_url,
            doctype,
            name,
            {"snapshot_hash": "0" * 64},
            csrf_token,
        )
        rejected_delete = delete_resource(
            actor,
            base_url,
            doctype,
            name,
            csrf_token,
        )
        after = get_resource(actor, base_url, doctype, name)
        require(
            before.status == 200
            and rejected_update.status == 403
            and rejected_delete.status == 403
            and after.status == 200
            and after.body.get("data", {}).get("snapshot_hash")
            == before.body.get("data", {}).get("snapshot_hash"),
            f"P6-08 {doctype} accepted generic mutation",
        )


def run_fresh(
    actor,
    administrator,
    base_url: str,
    csrf_token: str,
    fixture_password: str,
) -> dict[str, object]:
    project_id = predecessor.retained_project_id(actor, base_url)
    schema = run_bench_fixture(
        "verify_tooling_export_runtime_schema",
        {"fixture_run_id": FIXTURE_RUN_ID},
    )
    initial = persisted_counts(actor, base_url, project_id)
    require(
        initial["NPI Tooling List Preference"] == 0
        and initial["NPI Tooling Export Package"] == 0
        and initial["NPI Tooling Export Command Idempotency"] == 0,
        "P6-08 fresh export persistence was not empty",
    )
    integration_before = (initial["outbox"], initial["inbox"])
    seed_formula_master(actor, base_url, csrf_token, project_id)
    all_rows, view_counts = verify_views_and_paging(actor, base_url, project_id)
    formula = formula_row(all_rows)
    preference = verify_preference(actor, base_url, csrf_token, project_id)
    packages: list[dict[str, object]] = []
    current_actor = actor
    current_csrf = csrf_token
    first_package: dict[str, Any] | None = None
    for language, mode in PACKAGE_CASES:
        current_actor, current_csrf = set_actor_language(
            current_actor,
            base_url,
            current_csrf,
            fixture_password,
            language,
        )
        payload = export_payload(current_actor, base_url, project_id, mode)
        created, package = create_package(
            current_actor,
            base_url,
            current_csrf,
            project_id,
            payload,
            create_key(language),
            replayed="false",
        )
        replay, replay_package = create_package(
            current_actor,
            base_url,
            current_csrf,
            project_id,
            payload,
            create_key(language),
            replayed="true",
        )
        require(
            replay.body == created.body and replay_package == package,
            "P6-08 same-process create replay changed response truth",
        )
        downloaded = binary_request(
            current_actor,
            base_url,
            package_content_path(project_id, str(package["globalId"])),
            csrf_token=current_csrf,
            idempotency_key=download_key(language),
            expected_snapshot_hash=str(package["snapshotHash"]),
        )
        summary = validate_package_content(
            package,
            downloaded,
            project_id=project_id,
            language=language,
            mode=mode,
            replayed="false",
        )
        replay_download = binary_request(
            current_actor,
            base_url,
            package_content_path(project_id, str(package["globalId"])),
            csrf_token=current_csrf,
            idempotency_key=download_key(language),
            expected_snapshot_hash=str(package["snapshotHash"]),
        )
        require(
            replay_download.content == downloaded.content,
            "P6-08 same-process download replay changed package bytes",
        )
        validate_package_content(
            package,
            replay_download,
            project_id=project_id,
            language=language,
            mode=mode,
            replayed="true",
        )
        packages.append(summary)
        if first_package is None:
            first_package = package
    current_actor, current_csrf = set_actor_language(
        current_actor,
        base_url,
        current_csrf,
        fixture_password,
        "en",
    )
    require(first_package is not None, "P6-08 package fixture is unavailable")
    verify_stale_and_conflict(current_actor, base_url, current_csrf, project_id)
    verify_idor(
        current_actor,
        administrator,
        base_url,
        current_csrf,
        fixture_password,
        project_id,
        first_package,
    )
    expired = run_bench_fixture(
        "seed_expired_tooling_export_package",
        {
            "fixture_run_id": FIXTURE_RUN_ID,
            "project_id": project_id,
            "master_id": formula["toolingMasterGlobalId"],
            "master_snapshot_hash": formula["toolingMasterSnapshotHash"],
        },
    )
    expired_package = expired.get("package")
    require(isinstance(expired_package, dict), "P6-08 expired fixture drifted")
    expired_download = binary_request(
        current_actor,
        base_url,
        package_content_path(project_id, str(expired_package["globalId"])),
        csrf_token=current_csrf,
        idempotency_key=EXPIRED_DOWNLOAD_KEY,
        expected_snapshot_hash=str(expired_package["snapshotHash"]),
    )
    require(
        expired_download.status == 410
        and expired_download.problem is not None
        and expired_download.problem.get("code") == "TOOLING_EXPORT_EXPIRED",
        "P6-08 one-hour expiry boundary was not enforced",
    )
    verify_generic_mutation_denial(
        current_actor,
        base_url,
        current_csrf,
        project_id,
    )
    final = persisted_counts(current_actor, base_url, project_id)
    require(
        final["NPI Tooling List Preference"] == 1
        and final["NPI Tooling Export Package"] == 4
        and final["NPI Tooling Export Command Idempotency"] == 7
        and final["createAudit"] == 4
        and final["downloadAudit"] == 3
        and final["preferenceAudit"] == 1,
        "P6-08 controlled persistence cardinality drifted",
    )
    require(
        (final["outbox"], final["inbox"]) == integration_before,
        "P6-08 controlled export created ERP integration traffic",
    )
    return {
        "doctypeCount": schema["doctypeCount"],
        "fixtureRunId": FIXTURE_RUN_ID,
        "viewCount": len(view_counts),
        "nonEmptyViewCount": sum(value > 0 for value in view_counts.values()),
        "packageCount": len(packages) + 1,
        "localizedPackageCount": len(packages),
        "formulaNeutralized": True,
        "oneHourExpiryDenied": True,
        "integrationTrafficCreated": False,
        "preferenceSnapshotHash": preference["snapshotHash"],
    }


def run_replay(actor, base_url: str, csrf_token: str) -> dict[str, object]:
    project_id = predecessor.retained_project_id(actor, base_url)
    before = persisted_counts(actor, base_url, project_id)
    replayed: list[str] = []
    for language, mode in PACKAGE_CASES:
        payload = export_payload(actor, base_url, project_id, mode)
        _result, package = create_package(
            actor,
            base_url,
            csrf_token,
            project_id,
            payload,
            create_key(language),
            replayed="true",
        )
        require(
            package.get("language") == language and package.get("mode") == mode,
            "P6-08 cross-process create replay changed immutable package truth",
        )
        downloaded = binary_request(
            actor,
            base_url,
            package_content_path(project_id, str(package["globalId"])),
            csrf_token=csrf_token,
            idempotency_key=download_key(language),
            expected_snapshot_hash=str(package["snapshotHash"]),
        )
        require(
            downloaded.status == 200
            and downloaded.headers.get("Idempotency-Replayed") == "true"
            and hashlib.sha256(downloaded.content).hexdigest() == package.get("sha256"),
            "P6-08 cross-process download replay drifted",
        )
        replayed.append(language)
    require(
        persisted_counts(actor, base_url, project_id) == before,
        "P6-08 cross-process replay changed package, receipt, audit or integration truth",
    )
    return {"crossProcessReplay": True, "languages": replayed}


def route_disable_probe(actor, base_url: str, expected_mode: str) -> None:
    project_id = predecessor.retained_project_id(actor, base_url)
    listing = query_list(
        actor,
        base_url,
        project_id,
        query_key=f"route-{expected_mode}",
    )
    imports = predecessor.tooling_request(
        actor,
        base_url,
        predecessor.imports_path(project_id),
        query_key=f"p608-predecessor-{expected_mode}",
    )
    require(
        imports.status == 200 and len(imports.body.get("batches", [])) == 2,
        "P6-08 route switch changed predecessor import availability",
    )
    if expected_mode == "disabled":
        validate_problem(listing, 503, "TOOLING_EXPORT_ROUTES_DISABLED")
        return
    value = assert_list(listing, project_id)
    require(
        any(item.get("title") == FORMULA_MASTER_TITLE for item in value["items"]),
        "P6-08 route recovery lost retained Tooling List truth",
    )


def verify_tooling_export_runtime_schema(fixture_run_id: str) -> dict[str, object]:
    import frappe

    document_runtime._validated_runtime_site()
    require(fixture_run_id == FIXTURE_RUN_ID, "P6-08 schema fixture namespace drifted")
    required_fields = {
        "NPI Tooling List Preference": {
            "global_id",
            "project_global_id",
            "actor_user_id",
            "view_id",
            "optimistic_version",
            "preference_snapshot",
            "snapshot_hash",
        },
        "NPI Tooling Export Package": {
            "global_id",
            "project_global_id",
            "created_by_user_id",
            "mode",
            "language",
            "object_refs",
            "expires_at",
            "frappe_file_id",
            "sha256",
            "package_snapshot",
            "snapshot_hash",
        },
        "NPI Tooling Export Command Idempotency": {
            "global_id",
            "project_global_id",
            "actor_user_id",
            "operation",
            "payload_hash",
            "response_hash",
            "sealed",
        },
    }
    for doctype, fields in required_fields.items():
        require(frappe.db.table_exists(doctype), f"P6-08 table is unavailable: {doctype}")
        meta = frappe.get_meta(doctype, cached=False)
        actual = {field.fieldname for field in meta.fields}
        require(fields <= actual, f"P6-08 {doctype} metadata drifted")
        require(
            int(meta.allow_rename or 0) == 0 and int(meta.is_submittable or 0) == 0,
            f"P6-08 {doctype} mutability metadata drifted",
        )
    return {
        "doctypeCount": len(required_fields),
        "fixtureRunId": fixture_run_id,
        "metadataSynchronized": True,
        "runtimeMarker": RUNTIME_MARKER,
    }


def seed_expired_tooling_export_package(
    fixture_run_id: str,
    project_id: str,
    master_id: str,
    master_snapshot_hash: str,
) -> dict[str, object]:
    import frappe

    from npi_core.foundation.security import Principal
    from npi_core.tooling.export_domain import (
        ToolingExportMode,
        ToolingExportReference,
    )
    from npi_core.tooling.export_repository import FrappeToolingExportRepository

    document_runtime._validated_runtime_site()
    require(fixture_run_id == FIXTURE_RUN_ID, "P6-08 expiry fixture namespace drifted")
    frappe.set_user(ACTOR_USER)
    principal = Principal(
        user_id=ACTOR_USER,
        tenant_id=TENANT_ID,
        roles=frozenset(frappe.get_roles(ACTOR_USER)),
        is_external=False,
    )
    require("System Manager" in principal.roles, "P6-08 expiry actor authority drifted")
    generated_at = datetime.now(UTC) - timedelta(hours=1)
    repository = FrappeToolingExportRepository(
        principal=principal,
        request_id=deterministic_uuid("expired-request"),
        trace_id=f"trace-p608-expired-{FIXTURE_RUN_ID[:12]}",
        clock=lambda: generated_at,
    )
    outcome = repository.create_tooling_export_package(
        UUID(project_id),
        idempotency_key_hash=hashlib.sha256(EXPIRED_CREATE_KEY.encode()).hexdigest(),
        mode=ToolingExportMode.SELECTION,
        selection=(
            ToolingExportReference(
                tooling_master_global_id=UUID(master_id),
                snapshot_hash=master_snapshot_hash,
            ),
        ),
        filter_spec=None,
        query_snapshot_hash=None,
    )
    require(outcome is not None, "P6-08 expired package fixture is unavailable")
    package = outcome.response.get("package")
    require(isinstance(package, dict), "P6-08 expired package projection drifted")
    expires_at = datetime.fromisoformat(str(package["expiresAt"]).replace("Z", "+00:00"))
    require(
        expires_at <= datetime.now(UTC)
        and expires_at
        - datetime.fromisoformat(str(package["generatedAt"]).replace("Z", "+00:00"))
        == timedelta(hours=1),
        "P6-08 exact expiry fixture boundary drifted",
    )
    frappe.db.commit()
    return {"package": package, "replayed": outcome.replayed}


BENCH_FIXTURES = {
    "verify_tooling_export_runtime_schema": verify_tooling_export_runtime_schema,
    "seed_expired_tooling_export_package": seed_expired_tooling_export_package,
}


def run_bench_fixture(method: str, kwargs: dict[str, object]) -> dict[str, Any]:
    require(method in BENCH_FIXTURES, "P6-08 Bench fixture is unavailable")
    require(
        BENCH_PATH.is_dir()
        and not BENCH_PATH.is_symlink()
        and BENCH_PATH.resolve() == BENCH_PATH,
        "P6-08 verifier requires the fixed physical Bench",
    )
    environment = os.environ.copy()
    for name in (
        "NPI_RUNTIME_ADMINISTRATOR_PASSWORD",
        "NPI_RUNTIME_FIXTURE_PASSWORD",
        "NPI_ADMINISTRATOR_PASSWORD",
        "NPI_DATABASE_ROOT_PASSWORD",
    ):
        environment.pop(name, None)
    current_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        str(ROOT)
        if not current_pythonpath
        else f"{ROOT}{os.pathsep}{current_pythonpath}"
    )
    completed = subprocess.run(
        [
            str(BENCH_PATH / "env" / "bin" / "python"),
            str(ROOT / "scripts" / "verify_tooling_export_runtime.py"),
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
        f"P6-08 Bench fixture failed: {method}: {completed.stderr[-2000:]}",
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    require(bool(lines), f"P6-08 Bench fixture was silent: {method}")
    result = json.loads(lines[-1])
    require(isinstance(result, dict), "P6-08 Bench fixture result is invalid")
    return result


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    require(method in BENCH_FIXTURES, "P6-08 Bench fixture is unavailable")
    import frappe

    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    try:
        frappe.set_user(ACTOR_USER)
        result = BENCH_FIXTURES[method](**kwargs)
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the cumulative controlled P6-08 Tooling export runtime.",
    )
    parser.add_argument("--base-url")
    parser.add_argument("--bench-fixture", choices=tuple(BENCH_FIXTURES))
    parser.add_argument("--fixture-kwargs")
    parser.add_argument("--route-disable-probe", choices=("disabled", "recovered"))
    parser.add_argument("--replay-only", action="store_true")
    arguments = parser.parse_args()
    if arguments.bench_fixture is not None:
        require(
            arguments.base_url is None
            and isinstance(arguments.fixture_kwargs, str)
            and arguments.route_disable_probe is None
            and not arguments.replay_only,
            "P6-08 Bench fixture arguments are invalid",
        )
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "P6-08 fixture kwargs are invalid")
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return
    require(
        isinstance(arguments.base_url, str)
        and arguments.fixture_kwargs is None
        and document_runtime.CALLER_SUPPLIED_FIXTURE_RUN_ID is not None,
        "P6-08 runtime base URL and fixture namespace are required",
    )
    fixture_password = secret_from_environment("NPI_RUNTIME_FIXTURE_PASSWORD")
    administrator_password = secret_from_environment(
        "NPI_RUNTIME_ADMINISTRATOR_PASSWORD"
    )
    base_url = validate_local_fixture_inputs(
        arguments.base_url,
        "Administrator",
        UNRELATED_USER,
    )
    require(
        FIXTURE_RUN_ID != "0" * 32
        and ACTOR_USER.endswith("@example.invalid")
        and UNRELATED_USER.endswith("@example.invalid"),
        "P6-08 fixture identity drifted",
    )
    require(
        int(arguments.route_disable_probe is not None)
        + int(arguments.replay_only)
        <= 1,
        "P6-08 runtime modes are mutually exclusive",
    )
    actor = login(base_url, ACTOR_USER, fixture_password)
    csrf_token = bootstrap_csrf(actor, base_url, ACTOR_USER)
    if arguments.route_disable_probe is not None:
        route_disable_probe(actor, base_url, arguments.route_disable_probe)
        print(json.dumps({"routeMode": arguments.route_disable_probe}, sort_keys=True))
        return
    if arguments.replay_only:
        evidence = run_replay(actor, base_url, csrf_token)
        print(json.dumps(evidence, sort_keys=True))
        print("local Frappe Tooling export runtime replay verification passed")
        return
    administrator = login(base_url, "Administrator", administrator_password)
    evidence = run_fresh(
        actor,
        administrator,
        base_url,
        csrf_token,
        fixture_password,
    )
    print(json.dumps(evidence, sort_keys=True))
    print("local Frappe Tooling export runtime verification passed")


if __name__ == "__main__":
    main()
