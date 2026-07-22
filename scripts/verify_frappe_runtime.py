from __future__ import annotations

import argparse
import csv
import http.cookiejar
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_KEYS = {"userId", "language", "allowedLanguages", "csrfToken", "catalog"}
LANGUAGES = ("en", "zh", "zh-TW")


@dataclass(frozen=True)
class HttpResult:
    status: int
    headers: Any
    body: dict[str, Any]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


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
            return HttpResult(response.status, response.headers, json.loads(raw))
    except urllib.error.HTTPError as error:
        raw = error.read().decode()
        return HttpResult(error.code, error.headers, json.loads(raw))


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
) -> None:
    require(result.status == 200, f"Bootstrap returned HTTP {result.status}")
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


def user_resource_path(user: str) -> str:
    return f"/api/resource/User/{urllib.parse.quote(user, safe='')}/"


def validate_local_fixture_inputs(
    base_url: str,
    administrator_user: str,
    fixture_user: str,
) -> str:
    normalized_base_url = base_url.rstrip("/")
    parsed = urllib.parse.urlparse(normalized_base_url)
    require(
        parsed.scheme == "http"
        and parsed.hostname in {"127.0.0.1", "localhost", "::1"},
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
    return normalized_base_url


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
    parser.add_argument("--administrator-user", default="Administrator")
    parser.add_argument("--administrator-password", required=True)
    parser.add_argument("--fixture-user", required=True)
    parser.add_argument("--fixture-password", required=True)
    arguments = parser.parse_args()

    base_url = validate_local_fixture_inputs(
        arguments.base_url,
        arguments.administrator_user,
        arguments.fixture_user,
    )

    catalogs = {language: catalog_rows(language) for language in ("zh", "zh-TW")}
    expected_count = len(catalogs["zh"])
    require(expected_count == len(catalogs["zh-TW"]), "Direct locale coverage differs")

    guest = request(
        urllib.request.build_opener(), base_url, "/api/npi/v1/session/bootstrap"
    )
    validate_problem(guest, 401, "AUTHENTICATION_REQUIRED")

    unknown = request(urllib.request.build_opener(), base_url, "/api/npi/v1/unknown")
    validate_problem(unknown, 404, "API_ROUTE_NOT_FOUND")

    administrator_opener = login(
        base_url,
        arguments.administrator_user,
        arguments.administrator_password,
    )
    administrator_initial = request(
        administrator_opener, base_url, "/api/npi/v1/session/bootstrap"
    )
    administrator_language = str(administrator_initial.body.get("language"))
    validate_bootstrap(
        administrator_initial,
        arguments.administrator_user,
        administrator_language,
        expected_count,
    )
    administrator_csrf_token = str(administrator_initial.body["csrfToken"])

    fixture_path = user_resource_path(arguments.fixture_user)
    fixture_before = request(administrator_opener, base_url, fixture_path)
    require(
        fixture_before.status == 404,
        "Disposable fixture user already exists; refusing to delete a pre-existing user",
    )

    fixture_created = False
    fixture_deleted = False

    try:
        created = create_disposable_user(
            administrator_opener,
            base_url,
            arguments.fixture_user,
            arguments.fixture_password,
            administrator_csrf_token,
        )
        fixture_created = created.status in {200, 201}
        validate_disposable_user(created, arguments.fixture_user)

        fixture_opener = login(
            base_url, arguments.fixture_user, arguments.fixture_password
        )
        fixture_initial = request(
            fixture_opener, base_url, "/api/npi/v1/session/bootstrap"
        )
        validate_bootstrap(
            fixture_initial, arguments.fixture_user, "en", expected_count
        )
        fixture_csrf_token = str(fixture_initial.body["csrfToken"])

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
        validate_bootstrap(unchanged, arguments.fixture_user, "en", expected_count)
        fixture_csrf_token = str(unchanged.body["csrfToken"])

        simplified = set_language(
            fixture_opener, base_url, "zh", fixture_csrf_token
        )
        validate_bootstrap(simplified, arguments.fixture_user, "zh", expected_count)
        require(
            simplified.body["catalog"]["messages"]["My Work"]
            == catalogs["zh"]["My Work"],
            "Simplified Chinese catalog value drifted",
        )

        later_opener = login(
            base_url, arguments.fixture_user, arguments.fixture_password
        )
        later_bootstrap = request(
            later_opener, base_url, "/api/npi/v1/session/bootstrap"
        )
        validate_bootstrap(
            later_bootstrap,
            arguments.fixture_user,
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
            arguments.fixture_user,
            "zh",
            expected_count,
        )

        traditional = set_language(
            later_opener, base_url, "zh-TW", later_csrf_token
        )
        validate_bootstrap(traditional, arguments.fixture_user, "zh-TW", expected_count)
        require(
            traditional.body["catalog"]["messages"]["My Work"]
            == catalogs["zh-TW"]["My Work"],
            "Traditional Chinese catalog value drifted",
        )
        fresh_fixture_opener = login(
            base_url, arguments.fixture_user, arguments.fixture_password
        )
        validate_bootstrap(
            request(
                fresh_fixture_opener,
                base_url,
                "/api/npi/v1/session/bootstrap",
            ),
            arguments.fixture_user,
            "zh-TW",
            expected_count,
        )

        fresh_administrator_opener = login(
            base_url,
            arguments.administrator_user,
            arguments.administrator_password,
        )
        validate_bootstrap(
            request(
                fresh_administrator_opener,
                base_url,
                "/api/npi/v1/session/bootstrap",
            ),
            arguments.administrator_user,
            administrator_language,
            expected_count,
        )
    finally:
        if fixture_created:
            cleanup_opener = login(
                base_url,
                arguments.administrator_user,
                arguments.administrator_password,
            )
            cleanup_bootstrap = request(
                cleanup_opener, base_url, "/api/npi/v1/session/bootstrap"
            )
            validate_bootstrap(
                cleanup_bootstrap,
                arguments.administrator_user,
                administrator_language,
                expected_count,
            )
            delete_disposable_user(
                cleanup_opener,
                base_url,
                arguments.fixture_user,
                str(cleanup_bootstrap.body["csrfToken"]),
            )
            fixture_deleted = True

    print(
        json.dumps(
            {
                "administratorLanguage": administrator_language,
                "administratorLanguageUnchanged": True,
                "catalogEntriesPerLocale": expected_count,
                "disposableUserDeleted": fixture_deleted,
                "disposableUserId": arguments.fixture_user,
                "disposableUserType": "Website User",
                "guest": 401,
                "csrfMissing": 403,
                "csrfWrong": 403,
                "extraField": 422,
                "invalidLanguage": 422,
                "languages": list(LANGUAGES),
                "malformedJson": 400,
                "missingLanguage": 422,
                "unknownRoute": 404,
                "wrongTypeLanguage": 422,
            },
            sort_keys=True,
        )
    )
    print("local Frappe BFF runtime verification passed")


if __name__ == "__main__":
    main()
