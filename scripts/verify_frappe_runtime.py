from __future__ import annotations

import argparse
import csv
import http.cookiejar
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BENCH_PATH = ROOT / "tmp" / "frappe-bench"
RUNTIME_BASE_URL = "http://127.0.0.1:8003"
ADMINISTRATOR_USER = "Administrator"
DISPOSABLE_USER = "npi-runtime-user@example.invalid"
INSPECTOR_DISPOSABLE_USER = "npi-runtime-inspector@example.invalid"
EXPECTED_KEYS = {
    "userId",
    "language",
    "allowedLanguages",
    "csrfToken",
    "catalog",
    "preferences",
}
LANGUAGES = ("en", "zh", "zh-TW")
GRID_PREFERENCE_PATH = "/api/npi/v1/me/preferences/my-work-grid"
GRID_PREFERENCE_KEYS = {
    "gridId",
    "tableSchemaVersion",
    "version",
    "viewLayouts",
    "favoriteViewIds",
    "recentViewIds",
    "defaultProjectId",
    "recoveryReason",
    "capabilities",
}
GRID_VIEW_IDS = (
    "all",
    "today",
    "overdue",
    "approvals",
    "blockers",
    "waiting",
    "integration",
)
INSPECTOR_PREFERENCE_PATH = (
    "/api/npi/v1/me/preferences/my-work-inspector"
)
INSPECTOR_PREFERENCE_KEY = "npi_one_my_work_inspector_layout_v1"
_TRACE_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
INSPECTOR_PREFERENCE_KEYS = {
    "paneId",
    "schemaVersion",
    "widthPx",
    "collapsed",
    "recoveryReason",
}


@dataclass(frozen=True)
class HttpResult:
    status: int
    headers: Any
    body: dict[str, Any]
    request_id: str | None = None
    trace_id: str | None = None


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def response_trace_id(
    status: int,
    headers: Any,
    body: object,
) -> str:
    """Resolve one validated response trace without trusting arbitrary body data."""

    header_trace = _validated_response_trace(headers.get("X-Trace-ID"))
    body_trace = None
    content_type = headers.get("Content-Type")
    governed_problem = (
        400 <= status <= 599
        and isinstance(content_type, str)
        and content_type.split(";", 1)[0].strip().casefold()
        == "application/problem+json"
        and isinstance(body, dict)
    )
    if governed_problem and "traceId" in body:
        body_trace = _validated_response_trace(body.get("traceId"))
    if (
        header_trace is not None
        and body_trace is not None
        and header_trace != body_trace
    ):
        raise RuntimeError("HTTP response trace identities do not match")
    trace_id = header_trace or body_trace
    if trace_id is None:
        raise RuntimeError("HTTP response trace identity is missing")
    return trace_id


def _validated_response_trace(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or _TRACE_ID_PATTERN.fullmatch(value) is None:
        raise RuntimeError("HTTP response trace identity is invalid")
    return value


def _http_result(status: int, headers: Any, body: object) -> HttpResult:
    if not isinstance(body, dict):
        raise RuntimeError("HTTP response body is not a JSON object")
    return HttpResult(
        status,
        headers,
        body,
        trace_id=response_trace_id(status, headers, body),
    )


def request(
    opener: urllib.request.OpenerDirector,
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: Any = None,
    raw_payload: str | None = None,
    request_headers: dict[str, str] | None = None,
) -> HttpResult:
    require(
        payload is None or raw_payload is None,
        "HTTP helper accepts either a JSON payload or a raw payload, not both",
    )
    data = None
    headers = dict(request_headers or {})
    if payload is not None:
        data = json.dumps(payload).encode()
        headers.setdefault("Content-Type", "application/json")
    elif raw_payload is not None:
        data = raw_payload.encode()
        headers.setdefault("Content-Type", "application/json")
    http_request = urllib.request.Request(
        f"{base_url}{path}", data=data, headers=headers, method=method
    )
    try:
        with opener.open(http_request, timeout=15) as response:
            raw = response.read().decode()
            return _http_result(response.status, response.headers, json.loads(raw))
    except urllib.error.HTTPError as error:
        raw = error.read().decode()
        return _http_result(error.code, error.headers, json.loads(raw))


def login(base_url: str, user: str, password: str) -> urllib.request.OpenerDirector:
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    body = urllib.parse.urlencode({"usr": user, "pwd": password}).encode()
    login_request = urllib.request.Request(
        f"{base_url}/api/method/login", data=body, method="POST"
    )
    with opener.open(login_request, timeout=15) as response:
        result = json.loads(response.read().decode())
    require(
        result.get("message") in {"Logged In", "No App"},
        f"Local Frappe login failed for {user}",
    )
    return opener


def catalog_rows(language: str) -> dict[str, str]:
    catalog_path = (
        ROOT / "apps" / "npi_core" / "npi_core" / "translations" / f"{language}.csv"
    )
    with catalog_path.open(encoding="utf-8", newline="") as catalog_file:
        return {row[0]: row[1] for row in csv.reader(catalog_file)}


def validate_bootstrap(
    result: HttpResult,
    expected_user: str,
    language: str,
    expected_count: int,
    navigation_collapsed: bool = False,
) -> None:
    require(
        result.status == 200,
        (
            f"Bootstrap returned HTTP {result.status}: "
            f"{json.dumps(result.body, sort_keys=True)}"
        ),
    )
    require(set(result.body) == EXPECTED_KEYS, "Bootstrap response keys drifted")
    require(result.body.get("userId") == expected_user, "Unexpected bootstrap user")
    require(
        result.body.get("language") == language, "Bootstrap language did not persist"
    )
    require(
        tuple(result.body.get("allowedLanguages", ())) == LANGUAGES,
        "Language allowlist drifted",
    )
    csrf_token = result.body.get("csrfToken")
    require(
        isinstance(csrf_token, str) and 32 <= len(csrf_token) <= 128,
        "Session CSRF token is missing or invalid",
    )
    catalog = result.body.get("catalog", {})
    require(catalog.get("language") == language, "Catalog language drifted")
    require(
        len(catalog.get("messages", {})) == expected_count,
        "Catalog coverage drifted",
    )
    require(
        bool(re.fullmatch(r"[a-f0-9]{64}", catalog.get("version", ""))),
        "Catalog version is invalid",
    )
    preferences = result.body.get("preferences")
    require(
        isinstance(preferences, dict)
        and set(preferences) == {"navigationCollapsed"},
        "Session preference contract drifted",
    )
    collapsed = preferences.get("navigationCollapsed")
    require(type(collapsed) is bool, "Navigation preference is not an exact boolean")
    require(
        collapsed is navigation_collapsed,
        "Navigation preference did not persist",
    )
    require(
        "message" not in result.body and "headers" not in result.body,
        "Frappe metadata leaked into BFF body",
    )
    require(bool(result.headers.get("X-Trace-ID")), "BFF trace header is missing")
    require(
        result.headers.get("Cache-Control") == "private, no-store",
        "Session response cache control drifted",
    )


def validate_problem(
    result: HttpResult,
    expected_status: int,
    expected_code: str,
    *,
    expected_trace_id: str | None = None,
) -> None:
    require(result.status == expected_status, f"Problem returned HTTP {result.status}")
    require(result.body.get("status") == expected_status, "Problem status drifted")
    require(result.body.get("code") == expected_code, "Problem code drifted")
    require(
        result.headers.get_content_type() == "application/problem+json",
        "Problem media type drifted",
    )
    trace_id = result.body.get("traceId")
    require(
        isinstance(trace_id, str) and trace_id == result.headers.get("X-Trace-ID"),
        "Problem trace header/body mismatch",
    )
    if expected_trace_id is not None:
        require(trace_id == expected_trace_id, "Incoming trace identifier was not preserved")
    require(
        not {"exc", "exception", "exc_type", "message"}.intersection(result.body),
        "Frappe error envelope leaked into NPI problem body",
    )


def validate_grid_preferences(result: HttpResult) -> None:
    require(
        result.status == 200,
        (
            f"Grid preferences returned HTTP {result.status}: "
            f"{json.dumps(result.body, sort_keys=True)}"
        ),
    )
    require(
        set(result.body) == GRID_PREFERENCE_KEYS,
        "Grid preference response keys drifted",
    )
    require(result.body.get("gridId") == "my-work", "Grid identity drifted")
    require(
        result.body.get("tableSchemaVersion") == "my-work-grid-v1",
        "Grid table schema drifted",
    )
    require(
        type(result.body.get("version")) is int and result.body["version"] >= 0,
        "Grid preference version is invalid",
    )
    require(
        result.body.get("recoveryReason")
        in {None, "stored_preference_invalid"},
        "Grid preference recovery reason drifted",
    )
    view_layouts = result.body.get("viewLayouts")
    require(
        isinstance(view_layouts, list)
        and tuple(value.get("viewId") for value in view_layouts) == GRID_VIEW_IDS,
        "Grid preference closed views drifted",
    )
    require(
        all(
            isinstance(value, dict)
            and set(value)
            == {"viewId", "layout", "filter", "hasSavedFilter"}
            and type(value.get("hasSavedFilter")) is bool
            for value in view_layouts
        ),
        "Grid preference saved-filter state drifted",
    )
    capabilities = result.body.get("capabilities")
    require(
        isinstance(capabilities, dict)
        and capabilities.get("canPublishSharedView") is False
        and capabilities.get("canRollbackSharedView") is False
        and capabilities.get("canExport") is False
        and capabilities.get("canRunBulkActions") is False
        and capabilities.get("publishUnavailableReason")
        == "publisher_authority_policy_required",
        "Grid preference capabilities did not fail closed",
    )
    require(
        result.headers.get("Cache-Control") == "private, no-store",
        "Grid preference cache control drifted",
    )
    require(
        bool(result.headers.get("X-Request-ID")),
        "Grid preference request header is missing",
    )
    require(
        bool(result.headers.get("X-Trace-ID")),
        "Grid preference trace header is missing",
    )


def put_grid_preferences(
    opener: urllib.request.OpenerDirector,
    base_url: str,
    payload: dict[str, Any],
    csrf_token: str | None,
    *,
    trace_id: str | None = None,
) -> HttpResult:
    headers: dict[str, str] = {}
    if csrf_token is not None:
        headers["X-Frappe-CSRF-Token"] = csrf_token
    if trace_id is not None:
        headers["X-Trace-ID"] = trace_id
    return request(
        opener,
        base_url,
        GRID_PREFERENCE_PATH,
        method="PUT",
        payload=payload,
        request_headers=headers,
    )


def grid_preference_payload(
    preferences: dict[str, Any],
    *,
    expected_version: int,
    favorite_view_ids: list[str] | None = None,
    recent_view_ids: list[str] | None = None,
) -> dict[str, Any]:
    selected = preferences["viewLayouts"][0]
    return {
        "expectedVersion": expected_version,
        "tableSchemaVersion": "my-work-grid-v1",
        "viewId": "all",
        "layout": selected["layout"],
        "filter": selected["filter"],
        "saveFilter": False,
        "favoriteViewIds": (
            preferences["favoriteViewIds"]
            if favorite_view_ids is None
            else favorite_view_ids
        ),
        "recentViewIds": (
            preferences["recentViewIds"]
            if recent_view_ids is None
            else recent_view_ids
        ),
        "defaultProjectId": preferences["defaultProjectId"],
    }


def verify_grid_preferences_runtime(
    administrator_opener: urllib.request.OpenerDirector,
    base_url: str,
    administrator_password: str,
    csrf_token: str,
) -> dict[str, Any]:
    initial = request(administrator_opener, base_url, GRID_PREFERENCE_PATH)
    validate_grid_preferences(initial)
    initial_version = int(initial.body["version"])

    csrf_missing = put_grid_preferences(
        administrator_opener,
        base_url,
        grid_preference_payload(
            initial.body,
            expected_version=initial_version,
        ),
        None,
        trace_id="trace-grid-csrf-missing",
    )
    validate_problem(
        csrf_missing,
        403,
        "CSRF_TOKEN_INVALID",
        expected_trace_id="trace-grid-csrf-missing",
    )

    stale = put_grid_preferences(
        administrator_opener,
        base_url,
        grid_preference_payload(
            initial.body,
            expected_version=initial_version + 1,
        ),
        csrf_token,
    )
    validate_problem(stale, 409, "VERSION_CONFLICT")

    fresh_session = login(
        base_url,
        ADMINISTRATOR_USER,
        administrator_password,
    )
    fresh = request(fresh_session, base_url, GRID_PREFERENCE_PATH)
    validate_grid_preferences(fresh)
    require(
        fresh.body == initial.body,
        "Read-only grid verification changed the preference across sessions",
    )

    invalid_schema_payload = grid_preference_payload(
        fresh.body,
        expected_version=initial_version,
    )
    invalid_schema_payload["tableSchemaVersion"] = "unsupported-grid-schema"
    fresh_bootstrap = request(
        fresh_session,
        base_url,
        "/api/npi/v1/session/bootstrap",
    )
    invalid_schema = put_grid_preferences(
        fresh_session,
        base_url,
        invalid_schema_payload,
        str(fresh_bootstrap.body["csrfToken"]),
    )
    validate_problem(invalid_schema, 422, "VALIDATION_FAILED")

    unchanged = request(
        fresh_session,
        base_url,
        GRID_PREFERENCE_PATH,
    )
    validate_grid_preferences(unchanged)
    require(
        unchanged.body == initial.body,
        "Rejected grid preference probes changed stored state",
    )
    return {
        "gridPreferenceCsrfMissing": 403,
        "gridPreferenceReadIsolation": True,
        "gridPreferenceSchemaMismatch": 422,
        "gridPreferenceVersionConflict": 409,
    }


def validate_inspector_preference(
    result: HttpResult,
    *,
    expected_width_px: int,
    expected_collapsed: bool,
    expected_recovery_reason: str | None,
) -> None:
    require(
        result.status == 200,
        (
            f"Inspector preference returned HTTP {result.status}: "
            f"{json.dumps(result.body, sort_keys=True)}"
        ),
    )
    require(
        set(result.body) == INSPECTOR_PREFERENCE_KEYS,
        "Inspector preference response keys drifted",
    )
    require(
        result.body.get("paneId") == "my-work-inspector",
        "Inspector pane identity drifted",
    )
    require(
        result.body.get("schemaVersion") == "my-work-inspector-v1",
        "Inspector preference schema drifted",
    )
    require(
        type(result.body.get("widthPx")) is int
        and 260 <= result.body["widthPx"] <= 480
        and result.body["widthPx"] == expected_width_px,
        "Inspector preference width drifted",
    )
    require(
        type(result.body.get("collapsed")) is bool
        and result.body["collapsed"] is expected_collapsed,
        "Inspector preference collapsed state drifted",
    )
    require(
        result.body.get("recoveryReason") == expected_recovery_reason,
        "Inspector preference recovery reason drifted",
    )
    require(
        result.headers.get("Cache-Control") == "private, no-store",
        "Inspector preference cache control drifted",
    )
    require(
        bool(result.headers.get("X-Request-ID")),
        "Inspector preference request header is missing",
    )
    require(
        bool(result.headers.get("X-Trace-ID")),
        "Inspector preference trace header is missing",
    )


def put_inspector_preference(
    opener: urllib.request.OpenerDirector,
    base_url: str,
    payload: dict[str, Any],
    csrf_token: str | None,
    *,
    trace_id: str | None = None,
) -> HttpResult:
    headers: dict[str, str] = {}
    if csrf_token is not None:
        headers["X-Frappe-CSRF-Token"] = csrf_token
    if trace_id is not None:
        headers["X-Trace-ID"] = trace_id
    return request(
        opener,
        base_url,
        INSPECTOR_PREFERENCE_PATH,
        method="PUT",
        payload=payload,
        request_headers=headers,
    )


def inspector_preference_payload(
    *,
    width_px: int,
    collapsed: bool,
) -> dict[str, Any]:
    return {
        "schemaVersion": "my-work-inspector-v1",
        "widthPx": width_px,
        "collapsed": collapsed,
    }


def verify_inspector_preference_runtime(
    opener: urllib.request.OpenerDirector,
    base_url: str,
    password: str,
    csrf_token: str,
) -> dict[str, Any]:
    corrupt = request(opener, base_url, INSPECTOR_PREFERENCE_PATH)
    validate_inspector_preference(
        corrupt,
        expected_width_px=340,
        expected_collapsed=False,
        expected_recovery_reason="stored_preference_invalid",
    )
    corrupt_again = request(opener, base_url, INSPECTOR_PREFERENCE_PATH)
    validate_inspector_preference(
        corrupt_again,
        expected_width_px=340,
        expected_collapsed=False,
        expected_recovery_reason="stored_preference_invalid",
    )
    require(
        corrupt_again.body == corrupt.body,
        "Inspector corrupt-storage GET repaired or changed the stored value",
    )

    csrf_missing = put_inspector_preference(
        opener,
        base_url,
        inspector_preference_payload(width_px=420, collapsed=True),
        None,
        trace_id="trace-inspector-csrf-missing",
    )
    validate_problem(
        csrf_missing,
        403,
        "CSRF_TOKEN_INVALID",
        expected_trace_id="trace-inspector-csrf-missing",
    )

    saved = put_inspector_preference(
        opener,
        base_url,
        inspector_preference_payload(width_px=420, collapsed=True),
        csrf_token,
    )
    validate_inspector_preference(
        saved,
        expected_width_px=420,
        expected_collapsed=True,
        expected_recovery_reason=None,
    )

    fresh_session = login(
        base_url,
        INSPECTOR_DISPOSABLE_USER,
        password,
    )
    persisted = request(
        fresh_session,
        base_url,
        INSPECTOR_PREFERENCE_PATH,
    )
    validate_inspector_preference(
        persisted,
        expected_width_px=420,
        expected_collapsed=True,
        expected_recovery_reason=None,
    )
    require(
        persisted.body == saved.body,
        "Inspector preference did not persist across authenticated sessions",
    )
    return {
        "inspectorPreferenceCorruptNoRepair": True,
        "inspectorPreferenceCsrfMissing": 403,
        "inspectorPreferencePersistence": True,
    }


def verify_grid_generic_create_denied(
    administrator_opener: urllib.request.OpenerDirector,
    base_url: str,
    csrf_token: str,
) -> bool:
    cases = (
        (
            "NPI My Work Grid Preference",
            "73000000-0000-4000-8000-000000000001",
        ),
        (
            "NPI Published Grid View",
            "73000000-0000-4000-8000-000000000002",
        ),
        (
            "NPI Published Grid View Revision",
            "73000000-0000-4000-8000-000000000003",
        ),
    )
    for doctype, global_id in cases:
        collection_path = (
            "/api/resource/" + urllib.parse.quote(doctype, safe="")
        )
        created = request(
            administrator_opener,
            base_url,
            collection_path,
            method="POST",
            payload={"global_id": global_id},
            request_headers={"X-Frappe-CSRF-Token": csrf_token},
        )
        require(
            created.status == 403,
            f"Generic create was not denied for {doctype}",
        )
        resource_path = collection_path + "/" + urllib.parse.quote(
            global_id,
            safe="",
        )
        require(
            request(
                administrator_opener,
                base_url,
                resource_path,
            ).status
            == 404,
            f"Denied generic create left a {doctype} record",
        )

    return True


def put_language(
    opener: urllib.request.OpenerDirector,
    base_url: str,
    payload: Any,
    csrf_token: str | None,
    *,
    trace_id: str | None = None,
) -> HttpResult:
    headers = {}
    if csrf_token is not None:
        headers["X-Frappe-CSRF-Token"] = csrf_token
    if trace_id is not None:
        headers["X-Trace-ID"] = trace_id
    return request(
        opener,
        base_url,
        "/api/npi/v1/session/language",
        method="PUT",
        payload=payload,
        request_headers=headers,
    )


def set_language(
    opener: urllib.request.OpenerDirector,
    base_url: str,
    language: str,
    csrf_token: str,
) -> HttpResult:
    return put_language(opener, base_url, {"language": language}, csrf_token)


def put_navigation_preference(
    opener: urllib.request.OpenerDirector,
    base_url: str,
    payload: Any,
    csrf_token: str | None,
    *,
    trace_id: str | None = None,
) -> HttpResult:
    headers = {}
    if csrf_token is not None:
        headers["X-Frappe-CSRF-Token"] = csrf_token
    if trace_id is not None:
        headers["X-Trace-ID"] = trace_id
    return request(
        opener,
        base_url,
        "/api/npi/v1/session/preferences/navigation",
        method="PUT",
        payload=payload,
        request_headers=headers,
    )


def set_navigation_preference(
    opener: urllib.request.OpenerDirector,
    base_url: str,
    collapsed: bool,
    csrf_token: str,
) -> HttpResult:
    return put_navigation_preference(
        opener,
        base_url,
        {"collapsed": collapsed},
        csrf_token,
    )


def user_resource_path(user: str) -> str:
    return f"/api/resource/User/{urllib.parse.quote(user, safe='')}/"


def validate_local_fixture_inputs(
    base_url: str,
    administrator_user: str,
    fixture_user: str,
) -> str:
    normalized_base_url = base_url.rstrip("/")
    require(
        normalized_base_url == RUNTIME_BASE_URL,
        "Runtime verification requires the fixed local Frappe endpoint",
    )
    parsed = urllib.parse.urlparse(normalized_base_url)
    require(
        parsed.scheme == "http"
        and parsed.hostname == "127.0.0.1"
        and parsed.port == 8003
        and parsed.username is None
        and parsed.password is None
        and parsed.path in {"", "/"}
        and not parsed.params
        and not parsed.query
        and not parsed.fragment,
        "Runtime verification is restricted to a local HTTP Frappe Site",
    )
    require(
        administrator_user == "Administrator",
        "Runtime verification must use the local Administrator fixture",
    )
    require(
        fixture_user.lower().endswith("@example.invalid"),
        "Disposable user must use the reserved @example.invalid domain",
    )
    require(
        fixture_user == fixture_user.lower(),
        "Disposable user email must be lowercase for exact cleanup",
    )
    require(
        fixture_user not in {"Administrator", "Guest"},
        "Disposable user must not be a standard Frappe user",
    )
    validate_runtime_environment()
    return normalized_base_url


def validate_runtime_environment() -> None:
    expected_bench = ROOT / "tmp" / "frappe-bench"
    require(
        not (ROOT / "tmp").is_symlink()
        and BENCH_PATH == expected_bench
        and BENCH_PATH.is_dir()
        and not BENCH_PATH.is_symlink()
        and BENCH_PATH.resolve(strict=True) == expected_bench,
        "Runtime verifier requires the fixed physical repository Bench",
    )
    site_guard = ROOT / "scripts" / "verify_local_frappe_site.py"
    require(
        site_guard.is_file() and not site_guard.is_symlink(),
        "Runtime database identity guard is unavailable",
    )
    database_override_names = (
        "FRAPPE_DB_HOST",
        "FRAPPE_DB_PORT",
        "FRAPPE_DB_SOCKET",
        "FRAPPE_DB_TYPE",
    )
    require(
        not any(os.environ.get(name) for name in database_override_names),
        "Frappe database environment overrides are forbidden for runtime fixtures",
    )
    guard_environment = os.environ.copy()
    for name in (
        *database_override_names,
        "NPI_ADMINISTRATOR_PASSWORD",
        "NPI_DATABASE_ROOT_PASSWORD",
        "NPI_LOCAL_DATABASE_ROOT_PASSWORD",
        "NPI_RUNTIME_ADMINISTRATOR_PASSWORD",
        "NPI_RUNTIME_FIXTURE_PASSWORD",
    ):
        guard_environment.pop(name, None)
    try:
        guarded = subprocess.run(
            [
                str(BENCH_PATH / "env" / "bin" / "python"),
                str(site_guard),
                "--mode",
                "live",
            ],
            cwd=ROOT,
            env=guard_environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        raise RuntimeError(
            "Runtime database identity guard could not be executed"
        ) from None
    require(
        guarded.returncode == 0,
        "Runtime database endpoint or live identity validation failed",
    )


def secret_from_environment(name: str) -> str:
    value = os.environ.pop(name, None)
    require(
        isinstance(value, str)
        and len(value) >= 12
        and "\x00" not in value
        and "\n" not in value
        and "\r" not in value,
        f"Required controlled runtime secret is unavailable: {name}",
    )
    return value


def create_disposable_user(
    administrator_opener: urllib.request.OpenerDirector,
    base_url: str,
    user: str,
    password: str,
    csrf_token: str,
) -> HttpResult:
    return request(
        administrator_opener,
        base_url,
        "/api/resource/User",
        method="POST",
        request_headers={"X-Frappe-CSRF-Token": csrf_token},
        payload={
            "email": user,
            "enabled": 1,
            "first_name": "NPI Runtime",
            "language": "en",
            "last_name": "Fixture",
            "new_password": password,
            "send_welcome_email": 0,
            "user_type": "Website User",
        },
    )


def create_disposable_inspector_user(
    administrator_opener: urllib.request.OpenerDirector,
    base_url: str,
    user: str,
    password: str,
    csrf_token: str,
) -> HttpResult:
    corrupt_preference = (
        '{"collapsed":false,"schemaVersion":"my-work-inspector-v1",'
        '"unexpected":true,"widthPx":360}'
    )
    return request(
        administrator_opener,
        base_url,
        "/api/resource/User",
        method="POST",
        request_headers={"X-Frappe-CSRF-Token": csrf_token},
        payload={
            "email": user,
            "enabled": 1,
            "first_name": "NPI Inspector",
            "language": "en",
            "last_name": "Runtime Fixture",
            "new_password": password,
            "send_welcome_email": 0,
            "user_type": "System User",
            "roles": [{"role": "Desk User"}],
            "defaults": [
                {
                    "defkey": INSPECTOR_PREFERENCE_KEY,
                    "defvalue": corrupt_preference,
                }
            ],
        },
    )


def validate_disposable_user(result: HttpResult, expected_user: str) -> None:
    require(
        result.status in {200, 201},
        f"Disposable user creation returned HTTP {result.status}",
    )
    user = result.body.get("data", {})
    require(
        user.get("name") == expected_user and user.get("email") == expected_user,
        "Disposable user identity drifted",
    )
    require(
        user.get("user_type") == "Website User",
        "Disposable user unexpectedly has Desk access",
    )
    roles = {
        role.get("role") for role in user.get("roles", []) if isinstance(role, dict)
    }
    require(
        "System Manager" not in roles,
        "Disposable user unexpectedly has System Manager privileges",
    )


def validate_disposable_inspector_user(
    result: HttpResult,
    expected_user: str,
) -> None:
    require(
        result.status in {200, 201},
        f"Disposable inspector user creation returned HTTP {result.status}",
    )
    user = result.body.get("data", {})
    require(
        user.get("name") == expected_user
        and user.get("email") == expected_user,
        "Disposable inspector user identity drifted",
    )
    require(
        user.get("user_type") == "System User",
        "Disposable inspector user is not internal",
    )
    roles = {
        role.get("role")
        for role in user.get("roles", [])
        if isinstance(role, dict)
    }
    require(
        "Desk User" in roles and "System Manager" not in roles,
        "Disposable inspector user authority drifted",
    )


def delete_disposable_user(
    administrator_opener: urllib.request.OpenerDirector,
    base_url: str,
    expected_user: str,
    csrf_token: str,
) -> None:
    user_path = user_resource_path(expected_user)
    existing = request(administrator_opener, base_url, user_path)
    require(
        existing.status == 200
        and existing.body.get("data", {}).get("name") == expected_user,
        "Exact disposable user could not be resolved for cleanup",
    )
    deleted = request(
        administrator_opener,
        base_url,
        user_path,
        method="DELETE",
        request_headers={"X-Frappe-CSRF-Token": csrf_token},
    )
    require(
        deleted.status == 202,
        f"Disposable user deletion returned HTTP {deleted.status}",
    )
    require(
        request(administrator_opener, base_url, user_path).status == 404,
        "Disposable user still exists after cleanup",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    arguments = parser.parse_args()
    administrator_password = secret_from_environment(
        "NPI_RUNTIME_ADMINISTRATOR_PASSWORD"
    )
    fixture_password = secret_from_environment("NPI_RUNTIME_FIXTURE_PASSWORD")

    base_url = validate_local_fixture_inputs(
        arguments.base_url,
        ADMINISTRATOR_USER,
        DISPOSABLE_USER,
    )
    require(
        validate_local_fixture_inputs(
            arguments.base_url,
            ADMINISTRATOR_USER,
            INSPECTOR_DISPOSABLE_USER,
        )
        == base_url,
        "Inspector runtime fixture base URL drifted",
    )

    catalogs = {language: catalog_rows(language) for language in ("zh", "zh-TW")}
    expected_count = len(catalogs["zh"])
    require(expected_count == len(catalogs["zh-TW"]), "Direct locale coverage differs")

    guest = request(
        urllib.request.build_opener(), base_url, "/api/npi/v1/session/bootstrap"
    )
    validate_problem(guest, 401, "AUTHENTICATION_REQUIRED")
    guest_preference = put_navigation_preference(
        urllib.request.build_opener(),
        base_url,
        {"collapsed": True},
        "guest-csrf-token",
    )
    validate_problem(guest_preference, 401, "AUTHENTICATION_REQUIRED")
    guest_grid_preferences = request(
        urllib.request.build_opener(),
        base_url,
        GRID_PREFERENCE_PATH,
    )
    validate_problem(
        guest_grid_preferences,
        401,
        "AUTHENTICATION_REQUIRED",
    )
    guest_grid_preferences_extra = request(
        urllib.request.build_opener(),
        base_url,
        f"{GRID_PREFERENCE_PATH}?owner=Administrator",
    )
    validate_problem(
        guest_grid_preferences_extra,
        401,
        "AUTHENTICATION_REQUIRED",
    )
    guest_grid_preference_write = put_grid_preferences(
        urllib.request.build_opener(),
        base_url,
        {},
        "guest-csrf-token",
    )
    validate_problem(
        guest_grid_preference_write,
        401,
        "AUTHENTICATION_REQUIRED",
    )
    guest_inspector_preference = request(
        urllib.request.build_opener(),
        base_url,
        INSPECTOR_PREFERENCE_PATH,
    )
    validate_problem(
        guest_inspector_preference,
        401,
        "AUTHENTICATION_REQUIRED",
    )
    guest_inspector_preference_write = put_inspector_preference(
        urllib.request.build_opener(),
        base_url,
        {},
        "guest-csrf-token",
    )
    validate_problem(
        guest_inspector_preference_write,
        401,
        "AUTHENTICATION_REQUIRED",
    )

    unknown = request(urllib.request.build_opener(), base_url, "/api/npi/v1/unknown")
    validate_problem(unknown, 404, "API_ROUTE_NOT_FOUND")

    administrator_opener = login(
        base_url,
        ADMINISTRATOR_USER,
        administrator_password,
    )
    administrator_initial = request(
        administrator_opener, base_url, "/api/npi/v1/session/bootstrap"
    )
    administrator_language = str(administrator_initial.body.get("language"))
    administrator_navigation_collapsed = administrator_initial.body.get(
        "preferences", {}
    ).get("navigationCollapsed")
    require(
        type(administrator_navigation_collapsed) is bool,
        "Administrator navigation preference is not an exact boolean",
    )
    validate_bootstrap(
        administrator_initial,
        ADMINISTRATOR_USER,
        administrator_language,
        expected_count,
        administrator_navigation_collapsed,
    )
    administrator_csrf_token = str(administrator_initial.body["csrfToken"])
    administrator_inspector_initial = request(
        administrator_opener,
        base_url,
        INSPECTOR_PREFERENCE_PATH,
    )
    validate_inspector_preference(
        administrator_inspector_initial,
        expected_width_px=int(
            administrator_inspector_initial.body.get("widthPx", -1)
        ),
        expected_collapsed=administrator_inspector_initial.body.get(
            "collapsed"
        ),
        expected_recovery_reason=administrator_inspector_initial.body.get(
            "recoveryReason"
        ),
    )
    grid_preference_evidence = verify_grid_preferences_runtime(
        administrator_opener,
        base_url,
        administrator_password,
        administrator_csrf_token,
    )
    grid_generic_create_denied = verify_grid_generic_create_denied(
        administrator_opener,
        base_url,
        administrator_csrf_token,
    )

    fixture_path = user_resource_path(DISPOSABLE_USER)
    fixture_before = request(administrator_opener, base_url, fixture_path)
    require(
        fixture_before.status == 404,
        "Disposable fixture user already exists; refusing to delete a pre-existing user",
    )
    inspector_fixture_path = user_resource_path(INSPECTOR_DISPOSABLE_USER)
    inspector_fixture_before = request(
        administrator_opener,
        base_url,
        inspector_fixture_path,
    )
    require(
        inspector_fixture_before.status == 404,
        (
            "Disposable inspector user already exists; refusing to delete "
            "a pre-existing user"
        ),
    )

    fixture_created = False
    fixture_deleted = False
    inspector_fixture_created = False
    inspector_fixture_deleted = False
    inspector_preference_evidence: dict[str, Any] = {}

    try:
        inspector_created = create_disposable_inspector_user(
            administrator_opener,
            base_url,
            INSPECTOR_DISPOSABLE_USER,
            fixture_password,
            administrator_csrf_token,
        )
        inspector_fixture_created = inspector_created.status in {200, 201}
        validate_disposable_inspector_user(
            inspector_created,
            INSPECTOR_DISPOSABLE_USER,
        )
        inspector_opener = login(
            base_url,
            INSPECTOR_DISPOSABLE_USER,
            fixture_password,
        )
        inspector_bootstrap = request(
            inspector_opener,
            base_url,
            "/api/npi/v1/session/bootstrap",
        )
        validate_bootstrap(
            inspector_bootstrap,
            INSPECTOR_DISPOSABLE_USER,
            "en",
            expected_count,
        )
        inspector_preference_evidence = (
            verify_inspector_preference_runtime(
                inspector_opener,
                base_url,
                fixture_password,
                str(inspector_bootstrap.body["csrfToken"]),
            )
        )

        created = create_disposable_user(
            administrator_opener,
            base_url,
            DISPOSABLE_USER,
            fixture_password,
            administrator_csrf_token,
        )
        fixture_created = created.status in {200, 201}
        validate_disposable_user(created, DISPOSABLE_USER)

        fixture_opener = login(
            base_url, DISPOSABLE_USER, fixture_password
        )
        fixture_initial = request(
            fixture_opener, base_url, "/api/npi/v1/session/bootstrap"
        )
        validate_bootstrap(
            fixture_initial, DISPOSABLE_USER, "en", expected_count
        )
        fixture_csrf_token = str(fixture_initial.body["csrfToken"])
        external_inspector_preference = request(
            fixture_opener,
            base_url,
            INSPECTOR_PREFERENCE_PATH,
        )
        validate_problem(
            external_inspector_preference,
            403,
            "PERMISSION_DENIED",
        )

        csrf_missing = put_language(
            fixture_opener,
            base_url,
            {"language": "zh"},
            None,
            trace_id="trace-csrf-missing",
        )
        validate_problem(
            csrf_missing,
            403,
            "CSRF_TOKEN_INVALID",
            expected_trace_id="trace-csrf-missing",
        )
        require(csrf_missing.body.get("retryable") is True, "CSRF problem is not retryable")

        csrf_wrong = put_language(
            fixture_opener,
            base_url,
            {"language": "zh"},
            "wrong-csrf-token",
            trace_id="trace-csrf-wrong",
        )
        validate_problem(
            csrf_wrong,
            403,
            "CSRF_TOKEN_INVALID",
            expected_trace_id="trace-csrf-wrong",
        )

        navigation_csrf_missing = put_navigation_preference(
            fixture_opener,
            base_url,
            {"collapsed": True},
            None,
            trace_id="trace-navigation-csrf-missing",
        )
        validate_problem(
            navigation_csrf_missing,
            403,
            "CSRF_TOKEN_INVALID",
            expected_trace_id="trace-navigation-csrf-missing",
        )
        navigation_csrf_wrong = put_navigation_preference(
            fixture_opener,
            base_url,
            {"collapsed": True},
            "wrong-csrf-token",
            trace_id="trace-navigation-csrf-wrong",
        )
        validate_problem(
            navigation_csrf_wrong,
            403,
            "CSRF_TOKEN_INVALID",
            expected_trace_id="trace-navigation-csrf-wrong",
        )

        malformed = request(
            fixture_opener,
            base_url,
            "/api/npi/v1/session/language",
            method="PUT",
            raw_payload="{",
            request_headers={
                "X-Frappe-CSRF-Token": fixture_csrf_token,
                "X-Trace-ID": "trace-malformed-json",
            },
        )
        validate_problem(
            malformed,
            400,
            "MALFORMED_REQUEST",
            expected_trace_id="trace-malformed-json",
        )
        navigation_malformed = request(
            fixture_opener,
            base_url,
            "/api/npi/v1/session/preferences/navigation",
            method="PUT",
            raw_payload="{",
            request_headers={
                "X-Frappe-CSRF-Token": fixture_csrf_token,
                "X-Trace-ID": "trace-navigation-malformed-json",
            },
        )
        validate_problem(
            navigation_malformed,
            400,
            "MALFORMED_REQUEST",
            expected_trace_id="trace-navigation-malformed-json",
        )

        missing_language = put_language(
            fixture_opener, base_url, {}, fixture_csrf_token
        )
        validate_problem(missing_language, 422, "VALIDATION_FAILED")
        require(
            missing_language.body.get("fieldErrors", [{}])[0].get("path")
            == "language",
            "Missing language field error drifted",
        )

        extra_field = put_language(
            fixture_opener,
            base_url,
            {"language": "zh", "unapproved": "value"},
            fixture_csrf_token,
        )
        validate_problem(extra_field, 422, "VALIDATION_FAILED")
        require(
            extra_field.body.get("fieldErrors", [{}])[0].get("path")
            == "unapproved",
            "Additional-property field error drifted",
        )

        wrong_type = put_language(
            fixture_opener,
            base_url,
            {"language": {"code": "zh"}},
            fixture_csrf_token,
        )
        validate_problem(wrong_type, 422, "LANGUAGE_NOT_SUPPORTED")

        missing_navigation_preference = put_navigation_preference(
            fixture_opener,
            base_url,
            {},
            fixture_csrf_token,
        )
        validate_problem(
            missing_navigation_preference,
            422,
            "VALIDATION_FAILED",
        )
        require(
            missing_navigation_preference.body.get(
                "fieldErrors", [{}]
            )[0].get("path")
            == "collapsed",
            "Missing navigation preference field error drifted",
        )

        extra_navigation_field = put_navigation_preference(
            fixture_opener,
            base_url,
            {"collapsed": True, "user": ADMINISTRATOR_USER},
            fixture_csrf_token,
        )
        validate_problem(
            extra_navigation_field,
            422,
            "VALIDATION_FAILED",
        )
        require(
            extra_navigation_field.body.get("fieldErrors", [{}])[0].get(
                "path"
            )
            == "user",
            "Navigation preference additional-property error drifted",
        )

        for invalid_collapsed in (1, 0, "true", None):
            invalid_navigation_preference = put_navigation_preference(
                fixture_opener,
                base_url,
                {"collapsed": invalid_collapsed},
                fixture_csrf_token,
            )
            validate_problem(
                invalid_navigation_preference,
                422,
                "VALIDATION_FAILED",
            )
            require(
                invalid_navigation_preference.body.get(
                    "fieldErrors", [{}]
                )[0].get("path")
                == "collapsed",
                "Navigation preference type validation drifted",
            )

        bootstrap_extra = request(
            fixture_opener,
            base_url,
            "/api/npi/v1/session/bootstrap?unapproved=value",
        )
        validate_problem(bootstrap_extra, 422, "VALIDATION_FAILED")
        require(
            bootstrap_extra.body.get("fieldErrors", [{}])[0].get("path")
            == "unapproved",
            "Bootstrap additional-property field error drifted",
        )

        unchanged = request(
            fixture_opener, base_url, "/api/npi/v1/session/bootstrap"
        )
        validate_bootstrap(unchanged, DISPOSABLE_USER, "en", expected_count)
        fixture_csrf_token = str(unchanged.body["csrfToken"])

        navigation_collapsed = set_navigation_preference(
            fixture_opener,
            base_url,
            True,
            fixture_csrf_token,
        )
        validate_bootstrap(
            navigation_collapsed,
            DISPOSABLE_USER,
            "en",
            expected_count,
            True,
        )
        collapsed_session = login(
            base_url,
            DISPOSABLE_USER,
            fixture_password,
        )
        collapsed_bootstrap = request(
            collapsed_session,
            base_url,
            "/api/npi/v1/session/bootstrap",
        )
        validate_bootstrap(
            collapsed_bootstrap,
            DISPOSABLE_USER,
            "en",
            expected_count,
            True,
        )
        navigation_expanded = set_navigation_preference(
            collapsed_session,
            base_url,
            False,
            str(collapsed_bootstrap.body["csrfToken"]),
        )
        validate_bootstrap(
            navigation_expanded,
            DISPOSABLE_USER,
            "en",
            expected_count,
            False,
        )
        expanded_session = login(
            base_url,
            DISPOSABLE_USER,
            fixture_password,
        )
        validate_bootstrap(
            request(
                expanded_session,
                base_url,
                "/api/npi/v1/session/bootstrap",
            ),
            DISPOSABLE_USER,
            "en",
            expected_count,
            False,
        )
        fixture_after_navigation = request(
            fixture_opener,
            base_url,
            "/api/npi/v1/session/bootstrap",
        )
        validate_bootstrap(
            fixture_after_navigation,
            DISPOSABLE_USER,
            "en",
            expected_count,
            False,
        )
        fixture_csrf_token = str(
            fixture_after_navigation.body["csrfToken"]
        )

        simplified = set_language(
            fixture_opener, base_url, "zh", fixture_csrf_token
        )
        validate_bootstrap(simplified, DISPOSABLE_USER, "zh", expected_count)
        require(
            simplified.body["catalog"]["messages"]["My Work"]
            == catalogs["zh"]["My Work"],
            "Simplified Chinese catalog value drifted",
        )

        later_opener = login(
            base_url, DISPOSABLE_USER, fixture_password
        )
        later_bootstrap = request(
            later_opener, base_url, "/api/npi/v1/session/bootstrap"
        )
        validate_bootstrap(
            later_bootstrap,
            DISPOSABLE_USER,
            "zh",
            expected_count,
        )
        later_csrf_token = str(later_bootstrap.body["csrfToken"])

        invalid = set_language(
            later_opener, base_url, "zh-CN", later_csrf_token
        )
        validate_problem(invalid, 422, "LANGUAGE_NOT_SUPPORTED")
        require(
            invalid.body.get("fieldErrors", [{}])[0].get("path") == "language",
            "Invalid locale field error drifted",
        )
        validate_bootstrap(
            request(later_opener, base_url, "/api/npi/v1/session/bootstrap"),
            DISPOSABLE_USER,
            "zh",
            expected_count,
        )

        traditional = set_language(
            later_opener, base_url, "zh-TW", later_csrf_token
        )
        validate_bootstrap(traditional, DISPOSABLE_USER, "zh-TW", expected_count)
        require(
            traditional.body["catalog"]["messages"]["My Work"]
            == catalogs["zh-TW"]["My Work"],
            "Traditional Chinese catalog value drifted",
        )
        fresh_fixture_opener = login(
            base_url, DISPOSABLE_USER, fixture_password
        )
        validate_bootstrap(
            request(
                fresh_fixture_opener,
                base_url,
                "/api/npi/v1/session/bootstrap",
            ),
            DISPOSABLE_USER,
            "zh-TW",
            expected_count,
        )

        fresh_administrator_opener = login(
            base_url,
            ADMINISTRATOR_USER,
            administrator_password,
        )
        validate_bootstrap(
            request(
                fresh_administrator_opener,
                base_url,
                "/api/npi/v1/session/bootstrap",
            ),
            ADMINISTRATOR_USER,
            administrator_language,
            expected_count,
            administrator_navigation_collapsed,
        )
        administrator_inspector_after = request(
            fresh_administrator_opener,
            base_url,
            INSPECTOR_PREFERENCE_PATH,
        )
        require(
            administrator_inspector_after.body
            == administrator_inspector_initial.body,
            "Inspector preference crossed the authenticated actor boundary",
        )
    finally:
        if fixture_created or inspector_fixture_created:
            cleanup_opener = login(
                base_url,
                ADMINISTRATOR_USER,
                administrator_password,
            )
            cleanup_bootstrap = request(
                cleanup_opener, base_url, "/api/npi/v1/session/bootstrap"
            )
            validate_bootstrap(
                cleanup_bootstrap,
                ADMINISTRATOR_USER,
                administrator_language,
                expected_count,
                administrator_navigation_collapsed,
            )
            cleanup_csrf = str(cleanup_bootstrap.body["csrfToken"])
            if fixture_created:
                delete_disposable_user(
                    cleanup_opener,
                    base_url,
                    DISPOSABLE_USER,
                    cleanup_csrf,
                )
                fixture_deleted = True
            if inspector_fixture_created:
                delete_disposable_user(
                    cleanup_opener,
                    base_url,
                    INSPECTOR_DISPOSABLE_USER,
                    cleanup_csrf,
                )
                inspector_fixture_deleted = True

    print(
        json.dumps(
            {
                "administratorLanguage": administrator_language,
                "administratorLanguageUnchanged": True,
                "administratorNavigationPreferenceUnchanged": True,
                "catalogEntriesPerLocale": expected_count,
                "disposableUserDeleted": fixture_deleted,
                "disposableUserId": DISPOSABLE_USER,
                "disposableUserType": "Website User",
                "guest": 401,
                "guestPreference": 401,
                "guestGridPreference": 401,
                "guestGridPreferenceWrite": 401,
                "guestInspectorPreference": 401,
                "guestInspectorPreferenceWrite": 401,
                "gridGenericCreateDenied": grid_generic_create_denied,
                "inspectorDisposableUserDeleted": inspector_fixture_deleted,
                "inspectorDisposableUserId": INSPECTOR_DISPOSABLE_USER,
                "inspectorExternalDenied": 403,
                "inspectorPreferenceActorIsolation": True,
                "csrfMissing": 403,
                "csrfWrong": 403,
                "extraField": 422,
                "invalidLanguage": 422,
                "languages": list(LANGUAGES),
                "malformedJson": 400,
                "missingLanguage": 422,
                "navigationCsrfMissing": 403,
                "navigationCsrfWrong": 403,
                "navigationExtraField": 422,
                "navigationMalformedJson": 400,
                "navigationMissingField": 422,
                "navigationPersistence": True,
                "navigationUserIsolation": True,
                "navigationWrongTypes": 422,
                "unknownRoute": 404,
                "wrongTypeLanguage": 422,
                **grid_preference_evidence,
                **inspector_preference_evidence,
            },
            sort_keys=True,
        )
    )
    print("local Frappe BFF runtime verification passed")


if __name__ == "__main__":
    main()
