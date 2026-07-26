from __future__ import annotations

import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.errors import UnsupportedLanguage
from npi_core.foundation.localization import (
    CatalogConfigurationError,
    build_translation_catalog,
    parse_runtime_catalog,
    validate_language_code,
)

ROOT = Path(__file__).resolve().parents[1]


class LocalizationHelpersTest(unittest.TestCase):
    def test_only_exact_frappe_language_codes_are_allowed(self) -> None:
        self.assertEqual(validate_language_code("zh"), "zh")
        self.assertEqual(validate_language_code("zh-TW"), "zh-TW")
        with self.assertRaises(UnsupportedLanguage):
            validate_language_code("zh-CN")

    def test_runtime_catalog_is_headerless_and_context_aware(self) -> None:
        with self.assertRaises(CatalogConfigurationError):
            parse_runtime_catalog(
                [["source_string", "translated_string", "context"]]
            )

        catalog = parse_runtime_catalog(
            [["Save", "保存", ""], ["Change", "更改", "Coins"]]
        )
        self.assertEqual(list(catalog), ["Save", "Change:Coins"])

    def test_traditional_catalog_requires_direct_coverage_before_filtering(self) -> None:
        canonical = parse_runtime_catalog(
            [["Save", "保存", ""], ["Status", "状态", ""]]
        )
        incomplete_traditional = parse_runtime_catalog([["Save", "儲存", ""]])

        with self.assertRaises(CatalogConfigurationError):
            build_translation_catalog(
                "zh-TW",
                canonical,
                incomplete_traditional,
                {"Save": "儲存", "Status": "状态"},
            )

    def test_effective_catalog_is_filtered_and_versioned(self) -> None:
        canonical = parse_runtime_catalog([["Save", "保存", ""]])
        catalog = build_translation_catalog(
            "zh",
            canonical,
            canonical,
            {"Save": "保存", "Frappe only": "框架专用"},
        )

        self.assertEqual(catalog["messages"], {"Save": "保存"})
        self.assertRegex(str(catalog["version"]), r"^[a-f0-9]{64}$")

    def test_english_catalog_uses_canonical_source_literals(self) -> None:
        canonical = parse_runtime_catalog(
            [["Save", "保存", ""], ["Change", "更改", "Coins"]]
        )
        catalog = build_translation_catalog("en", canonical, None, {})
        self.assertEqual(
            catalog["messages"],
            {"Save": "Save", "Change:Coins": "Change"},
        )


class FrappeLocalizationAdapterTest(unittest.TestCase):
    class StubPermissionError(Exception):
        pass

    class StubUser:
        def __init__(self, permission_error: type[Exception] | None = None) -> None:
            self.language = "en"
            self.save_count = 0
            self.permission_error = permission_error

        def save(self) -> None:
            self.save_count += 1
            if self.permission_error:
                raise self.permission_error()

    class StubResponse(dict):
        def __getattr__(self, name: str):
            return self.get(name)

        def __setattr__(self, name: str, value) -> None:
            self[name] = value

    class StubFormDict(dict):
        def __getattr__(self, name: str):
            return self.get(name)

        def __setattr__(self, name: str, value) -> None:
            self[name] = value

    class StubDatabase:
        def __init__(self) -> None:
            self.rollback_count = 0

        def rollback(self) -> None:
            self.rollback_count += 1

    class StubLogger:
        def __init__(self) -> None:
            self.messages: list[str] = []

        def error(self, message: str) -> None:
            self.messages.append(message)

    class StubHttpResponse:
        def __init__(self, status_code: int = 200) -> None:
            self.headers: dict[str, str] = {}
            self.data = b""
            self.status_code = status_code

        def set_data(self, data: str) -> None:
            self.data = data.encode()

    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.translations_directory = Path(self.temp_directory.name)
        (self.translations_directory / "zh.csv").write_text(
            "Save,保存,\nProject Cockpit,项目驾驶舱,page-title\n",
            encoding="utf-8",
        )
        (self.translations_directory / "zh-TW.csv").write_text(
            "Save,儲存,\nProject Cockpit,專案駕駛艙,page-title\n",
            encoding="utf-8",
        )

        self.user = self.StubUser()
        self.get_doc_calls: list[tuple[str, str]] = []
        self.clear_cache_calls: list[str] = []
        self.logged_errors: list[dict[str, str]] = []
        self.user_defaults: dict[str, dict[str, object]] = {}
        self.preference_read_calls: list[str] = []
        self.preference_write_calls: list[tuple[str, object, str]] = []
        self.preference_read_error: Exception | None = None
        self.preference_write_error: Exception | None = None
        self.csrf_token = "csrf-token-" + ("a" * 48)
        self.request_headers = {
            "X-Frappe-CSRF-Token": self.csrf_token,
            "X-Trace-ID": "trace-localization",
        }
        self.database = self.StubDatabase()
        self.logger = self.StubLogger()
        self.merged_catalogs = {
            "zh": {
                "Save": "保存",
                "Project Cockpit:page-title": "项目驾驶舱",
                "Framework only": "框架专用",
            },
            "zh-TW": {
                "Save": "儲存",
                "Project Cockpit:page-title": "專案駕駛艙",
                "Framework only": "框架專用",
            },
        }
        self.current_language = "zh-TW"

        self.frappe = types.ModuleType("frappe")
        self.frappe.PermissionError = self.StubPermissionError
        self.frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
        self.frappe._ = lambda source: source
        self.frappe.db = self.database
        self.frappe.flags = types.SimpleNamespace(npi_bff_request=False)
        self.frappe.session = types.SimpleNamespace(user="engineer@example.invalid")
        self.frappe.local = types.SimpleNamespace(
            lang="en",
            user_lang="en",
            response=self.StubResponse(),
            request=types.SimpleNamespace(path="/", method="GET"),
            form_dict=self.StubFormDict(),
        )
        self.frappe.get_request_header = lambda name: self.request_headers.get(name)
        self.frappe.get_app_path = (
            lambda app, directory: str(self.translations_directory)
            if (app, directory) == ("npi_core", "translations")
            else ""
        )
        self.frappe.get_doc = self._get_doc
        self.frappe.clear_cache = lambda user: self.clear_cache_calls.append(user)
        self.frappe.log_error = lambda **values: self.logged_errors.append(values)
        self.frappe.logger = lambda _name: self.logger

        def whitelist(*, methods: list[str], allow_guest: bool = False):
            def decorate(function):
                function.allowed_methods = tuple(methods)
                function.allow_guest = allow_guest
                return function

            return decorate

        self.frappe.whitelist = whitelist

        translate = types.ModuleType("frappe.translate")
        translate.get_user_lang = lambda _user: self.current_language
        translate.get_all_translations = lambda language: self.merged_catalogs[language]
        self.frappe.translate = translate

        sessions = types.ModuleType("frappe.sessions")
        sessions.get_csrf_token = lambda: self.csrf_token
        self.frappe.sessions = sessions

        defaults = types.ModuleType("frappe.defaults")
        defaults.get_defaults_for = self._get_defaults_for
        defaults.set_user_default = self._set_user_default
        self.frappe.defaults = defaults

        self.saved_modules = {
            name: sys.modules.get(name)
            for name in (
                "frappe",
                "frappe.defaults",
                "frappe.sessions",
                "frappe.translate",
            )
        }
        sys.modules["frappe"] = self.frappe
        sys.modules["frappe.defaults"] = defaults
        sys.modules["frappe.sessions"] = sessions
        sys.modules["frappe.translate"] = translate
        sys.modules.pop("npi_core.localization_api", None)
        sys.modules.pop("npi_core.bff", None)
        self.adapter = importlib.import_module("npi_core.localization_api")

    def tearDown(self) -> None:
        sys.modules.pop("npi_core.localization_api", None)
        sys.modules.pop("npi_core.bff", None)
        for name, module in self.saved_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
        self.temp_directory.cleanup()

    def _get_doc(self, doctype: str, name: str):
        self.get_doc_calls.append((doctype, name))
        return self.user

    def _get_defaults_for(self, parent: str = "__default") -> dict[str, object]:
        self.preference_read_calls.append(parent)
        if self.preference_read_error is not None:
            raise self.preference_read_error
        return dict(self.user_defaults.get(parent, {}))

    def _set_user_default(
        self,
        key: str,
        value: object,
        user: str | None = None,
        parenttype: str | None = None,
    ) -> None:
        self.assertIsNone(parenttype)
        resolved_user = user or self.frappe.session.user
        self.preference_write_calls.append((key, value, resolved_user))
        if self.preference_write_error is not None:
            raise self.preference_write_error
        self.user_defaults.setdefault(resolved_user, {})[key] = value

    def assert_problem(
        self, result: dict[str, object], status: int, code: str
    ) -> None:
        headers = self.frappe.flags.npi_response_headers
        self.assertEqual(self.frappe.local.response.http_status_code, status)
        self.assertEqual(result["status"], status)
        self.assertEqual(result["code"], code)
        self.assertEqual(headers["Content-Type"], "application/problem+json")
        self.assertEqual(result["traceId"], headers["X-Trace-ID"])

    def test_bootstrap_is_authenticated_and_uses_filtered_merged_catalog(self) -> None:
        result = self.adapter.get_session_bootstrap()

        self.assertEqual(self.frappe.local.response.http_status_code, 200)
        self.assertEqual(
            set(result),
            {
                "userId",
                "language",
                "allowedLanguages",
                "csrfToken",
                "catalog",
                "preferences",
            },
        )
        self.assertEqual(result["language"], "zh-TW")
        self.assertEqual(result["allowedLanguages"], ["en", "zh", "zh-TW"])
        self.assertEqual(result["csrfToken"], self.csrf_token)
        self.assertEqual(
            result["preferences"],
            {"navigationCollapsed": False},
        )
        self.assertIs(
            result["preferences"]["navigationCollapsed"],
            False,
        )
        self.assertEqual(
            result["catalog"]["messages"],
            {
                "Save": "儲存",
                "Project Cockpit:page-title": "專案駕駛艙",
            },
        )
        self.assertEqual(self.adapter.get_session_bootstrap.allowed_methods, ("GET",))
        self.assertTrue(self.adapter.get_session_bootstrap.allow_guest)
        self.assertEqual(
            self.preference_read_calls,
            ["engineer@example.invalid"],
        )
        self.assertEqual(self.preference_write_calls, [])
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Cache-Control"],
            "private, no-store",
        )

    def test_guest_is_rejected_inside_adapter(self) -> None:
        self.frappe.session.user = "Guest"
        result = self.adapter.get_session_bootstrap()

        self.assertEqual(self.frappe.local.response.http_status_code, 401)
        self.assertEqual(result["code"], "AUTHENTICATION_REQUIRED")
        self.assertEqual(self.get_doc_calls, [])
        self.assertEqual(self.preference_read_calls, [])
        self.assertEqual(self.preference_write_calls, [])

    def test_bootstrap_ignores_global_and_corrupt_navigation_preferences_without_repair(
        self,
    ) -> None:
        preference_key = (
            self.adapter.APP_SHELL_NAVIGATION_COLLAPSED_DEFAULT_KEY
        )
        self.user_defaults["__default"] = {preference_key: "true"}
        self.user_defaults["engineer@example.invalid"] = {
            preference_key: "corrupt"
        }

        result = self.adapter.get_session_bootstrap()

        self.assertEqual(
            result["preferences"],
            {"navigationCollapsed": False},
        )
        self.assertEqual(
            self.user_defaults["engineer@example.invalid"][preference_key],
            "corrupt",
        )
        self.assertEqual(
            self.preference_read_calls,
            ["engineer@example.invalid"],
        )
        self.assertEqual(self.preference_write_calls, [])

    def test_navigation_preference_is_persisted_for_authenticated_user_only(
        self,
    ) -> None:
        result = self.adapter.set_current_user_navigation_preference(True)

        preference_key = (
            self.adapter.APP_SHELL_NAVIGATION_COLLAPSED_DEFAULT_KEY
        )
        self.assertEqual(
            result["preferences"],
            {"navigationCollapsed": True},
        )
        self.assertEqual(
            self.preference_write_calls,
            [
                (
                    preference_key,
                    "true",
                    "engineer@example.invalid",
                )
            ],
        )
        self.assertEqual(
            self.user_defaults["engineer@example.invalid"][preference_key],
            "true",
        )
        self.assertEqual(
            self.adapter.set_current_user_navigation_preference.allowed_methods,
            ("PUT",),
        )
        self.assertTrue(
            self.adapter.set_current_user_navigation_preference.allow_guest
        )
        self.assertEqual(result["userId"], "engineer@example.invalid")
        self.assertEqual(result["csrfToken"], self.csrf_token)
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Cache-Control"],
            "private, no-store",
        )

    def test_navigation_preference_false_is_confirmed_and_persists(
        self,
    ) -> None:
        preference_key = (
            self.adapter.APP_SHELL_NAVIGATION_COLLAPSED_DEFAULT_KEY
        )
        self.user_defaults["engineer@example.invalid"] = {
            preference_key: "true"
        }

        result = self.adapter.set_current_user_navigation_preference(False)
        later = self.adapter.get_session_bootstrap()

        self.assertEqual(
            result["preferences"],
            {"navigationCollapsed": False},
        )
        self.assertEqual(
            later["preferences"],
            {"navigationCollapsed": False},
        )
        self.assertEqual(
            self.user_defaults["engineer@example.invalid"][preference_key],
            "false",
        )

    def test_navigation_preference_rejects_missing_and_non_boolean_values(
        self,
    ) -> None:
        invalid_values = (None, 0, 1, "false", [], {})
        for collapsed in invalid_values:
            with self.subTest(collapsed=collapsed):
                result = self.adapter.set_current_user_navigation_preference(
                    collapsed
                )

                self.assert_problem(result, 422, "VALIDATION_FAILED")
                self.assertEqual(
                    result["fieldErrors"][0]["path"],
                    "collapsed",
                )
        self.assertEqual(self.preference_read_calls, [])
        self.assertEqual(self.preference_write_calls, [])

    def test_navigation_preference_rejects_extra_fields_before_write(
        self,
    ) -> None:
        result = self.adapter.set_current_user_navigation_preference(
            True, user="another@example.invalid"
        )

        self.assert_problem(result, 422, "VALIDATION_FAILED")
        self.assertEqual(
            result["fieldErrors"],
            [{"path": "user", "message": "This field is not allowed."}],
        )
        self.assertEqual(self.preference_read_calls, [])
        self.assertEqual(self.preference_write_calls, [])

    def test_navigation_preference_requires_csrf_before_read_or_write(
        self,
    ) -> None:
        self.request_headers.pop("X-Frappe-CSRF-Token")

        result = self.adapter.set_current_user_navigation_preference(True)

        self.assert_problem(result, 403, "CSRF_TOKEN_INVALID")
        self.assertTrue(result["retryable"])
        self.assertEqual(self.preference_read_calls, [])
        self.assertEqual(self.preference_write_calls, [])

    def test_navigation_preference_does_not_cross_user_boundaries(self) -> None:
        preference_key = (
            self.adapter.APP_SHELL_NAVIGATION_COLLAPSED_DEFAULT_KEY
        )
        self.user_defaults["engineer@example.invalid"] = {
            preference_key: "true"
        }
        self.user_defaults["planner@example.invalid"] = {
            preference_key: "false"
        }

        engineer_bootstrap = self.adapter.get_session_bootstrap()
        self.frappe.session.user = "planner@example.invalid"
        planner_bootstrap = self.adapter.get_session_bootstrap()
        planner_update = (
            self.adapter.set_current_user_navigation_preference(True)
        )

        self.assertTrue(
            engineer_bootstrap["preferences"]["navigationCollapsed"]
        )
        self.assertFalse(
            planner_bootstrap["preferences"]["navigationCollapsed"]
        )
        self.assertTrue(
            planner_update["preferences"]["navigationCollapsed"]
        )
        self.assertEqual(
            self.user_defaults["engineer@example.invalid"][preference_key],
            "true",
        )
        self.assertEqual(
            self.user_defaults["planner@example.invalid"][preference_key],
            "true",
        )
        self.assertEqual(
            self.preference_write_calls,
            [
                (
                    preference_key,
                    "true",
                    "planner@example.invalid",
                )
            ],
        )

    def test_navigation_preference_storage_failures_are_not_success(
        self,
    ) -> None:
        self.preference_write_error = RuntimeError(
            "preference store unavailable"
        )

        result = self.adapter.set_current_user_navigation_preference(True)

        self.assert_problem(result, 500, "INTERNAL_SERVER_ERROR")
        self.assertTrue(result["retryable"])
        self.assertEqual(self.database.rollback_count, 1)
        self.assertNotIn(
            "engineer@example.invalid",
            self.user_defaults,
        )

    def test_navigation_preference_read_failures_are_not_silent_defaults(
        self,
    ) -> None:
        self.preference_read_error = RuntimeError(
            "preference store unavailable"
        )

        result = self.adapter.get_session_bootstrap()

        self.assert_problem(result, 500, "INTERNAL_SERVER_ERROR")
        self.assertTrue(result["retryable"])
        self.assertEqual(self.database.rollback_count, 1)
        self.assertEqual(self.preference_write_calls, [])

    def test_navigation_preference_catalog_failure_happens_before_write(
        self,
    ) -> None:
        (self.translations_directory / "zh-TW.csv").write_text(
            "Save,儲存,\n",
            encoding="utf-8",
        )

        result = self.adapter.set_current_user_navigation_preference(True)

        self.assert_problem(result, 503, "LOCALIZATION_UNAVAILABLE")
        self.assertEqual(self.preference_write_calls, [])

    def test_language_change_uses_normal_user_save_and_refreshes_locale(self) -> None:
        result = self.adapter.set_current_user_language("zh")

        self.assertEqual(result["language"], "zh")
        self.assertEqual(self.get_doc_calls, [("User", "engineer@example.invalid")])
        self.assertEqual(self.user.language, "zh")
        self.assertEqual(self.user.save_count, 1)
        self.assertEqual(self.frappe.local.lang, "zh")
        self.assertEqual(self.frappe.local.user_lang, "zh")
        self.assertEqual(self.clear_cache_calls, ["engineer@example.invalid"])
        self.assertEqual(
            self.adapter.set_current_user_language.allowed_methods,
            ("PUT",),
        )
        self.assertEqual(result["csrfToken"], self.csrf_token)

    def test_invalid_language_never_loads_or_saves_user(self) -> None:
        result = self.adapter.set_current_user_language("zh-CN")

        self.assert_problem(result, 422, "LANGUAGE_NOT_SUPPORTED")
        self.assertEqual(self.get_doc_calls, [])
        self.assertEqual(self.clear_cache_calls, [])

    def test_missing_language_is_a_controlled_required_field_problem(self) -> None:
        result = self.adapter.set_current_user_language()

        self.assert_problem(result, 422, "VALIDATION_FAILED")
        self.assertEqual(
            result["fieldErrors"],
            [{"path": "language", "message": "This field is required."}],
        )
        self.assertEqual(self.get_doc_calls, [])
        self.assertEqual(self.clear_cache_calls, [])

    def test_wrong_type_language_is_a_controlled_problem(self) -> None:
        result = self.adapter.set_current_user_language({"code": "zh"})

        self.assert_problem(result, 422, "LANGUAGE_NOT_SUPPORTED")
        self.assertEqual(self.get_doc_calls, [])

    def test_extra_language_field_is_rejected_instead_of_ignored(self) -> None:
        result = self.adapter.set_current_user_language("zh", unapproved="value")

        self.assert_problem(result, 422, "VALIDATION_FAILED")
        self.assertEqual(
            result["fieldErrors"],
            [{"path": "unapproved", "message": "This field is not allowed."}],
        )
        self.assertEqual(self.get_doc_calls, [])

    def test_bootstrap_query_fields_are_rejected_inside_problem_boundary(self) -> None:
        result = self.adapter.get_session_bootstrap(unapproved="value")

        self.assert_problem(result, 422, "VALIDATION_FAILED")
        self.assertEqual(
            result["fieldErrors"],
            [{"path": "unapproved", "message": "This field is not allowed."}],
        )

    def test_missing_csrf_header_never_changes_language(self) -> None:
        self.request_headers.pop("X-Frappe-CSRF-Token")

        result = self.adapter.set_current_user_language("zh")

        self.assert_problem(result, 403, "CSRF_TOKEN_INVALID")
        self.assertTrue(result["retryable"])
        self.assertEqual(self.get_doc_calls, [])

    def test_catalog_failure_happens_before_user_mutation(self) -> None:
        (self.translations_directory / "zh.csv").write_text(
            "source_string,translated_string,context\n",
            encoding="utf-8",
        )

        result = self.adapter.set_current_user_language("zh")

        self.assert_problem(result, 503, "LOCALIZATION_UNAVAILABLE")
        self.assertEqual(self.user.language, "en")
        self.assertEqual(self.user.save_count, 0)
        self.assertEqual(self.get_doc_calls, [])
        self.assertEqual(self.clear_cache_calls, [])

    def test_permission_failure_is_not_reported_as_success(self) -> None:
        self.user = self.StubUser(self.StubPermissionError)
        result = self.adapter.set_current_user_language("zh")

        self.assertEqual(self.frappe.local.response.http_status_code, 403)
        self.assertEqual(result["code"], "PERMISSION_DENIED")
        self.assertEqual(self.clear_cache_calls, [])
        self.assertEqual(self.frappe.local.lang, "en")

    def test_cache_failure_rolls_back_without_switching_request_locale(self) -> None:
        def fail_clear_cache(user: str) -> None:
            self.clear_cache_calls.append(user)
            raise RuntimeError("cache backend unavailable")

        self.frappe.clear_cache = fail_clear_cache

        result = self.adapter.set_current_user_language("zh")

        self.assert_problem(result, 500, "INTERNAL_SERVER_ERROR")
        self.assertTrue(result["retryable"])
        self.assertEqual(self.user.save_count, 1)
        self.assertEqual(self.user.language, "en")
        self.assertEqual(self.frappe.local.lang, "en")
        self.assertEqual(self.frappe.local.user_lang, "en")
        self.assertEqual(self.clear_cache_calls, ["engineer@example.invalid"])
        self.assertEqual(self.database.rollback_count, 1)

    def test_missing_direct_traditional_row_returns_visible_service_error(self) -> None:
        (self.translations_directory / "zh-TW.csv").write_text(
            "Save,儲存,\n",
            encoding="utf-8",
        )
        result = self.adapter.get_session_bootstrap()

        self.assertEqual(self.frappe.local.response.http_status_code, 503)
        self.assertEqual(result["code"], "LOCALIZATION_UNAVAILABLE")
        self.assertEqual(len(self.logged_errors), 1)

    def test_fixed_bff_route_maps_only_the_explicit_session_query(self) -> None:
        self.frappe.local.request = types.SimpleNamespace(
            path="/api/npi/v1/session/bootstrap", method="GET"
        )
        router = importlib.import_module("npi_core.bff")

        router.route_request()

        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.localization_api.get_session_bootstrap",
        )
        self.assertTrue(self.frappe.flags.npi_bff_request)

    def test_fixed_bff_route_maps_navigation_preference_only_to_its_handler(
        self,
    ) -> None:
        self.frappe.local.request = types.SimpleNamespace(
            path="/api/npi/v1/session/preferences/navigation",
            method="PUT",
        )
        router = importlib.import_module("npi_core.bff")

        router.route_request()

        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            (
                "npi_core.localization_api."
                "set_current_user_navigation_preference"
            ),
        )
        self.assertTrue(self.frappe.flags.npi_bff_request)

    def test_unknown_bff_route_uses_the_npi_problem_handler(self) -> None:
        self.frappe.local.request = types.SimpleNamespace(
            path="/api/npi/v1/unknown", method="GET"
        )
        router = importlib.import_module("npi_core.bff")

        router.route_request()

        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.bff.route_not_found",
        )
        self.assertTrue(self.frappe.flags.npi_bff_request)

    def test_similar_api_prefix_is_not_claimed_by_the_npi_router(self) -> None:
        self.frappe.local.request = types.SimpleNamespace(
            path="/api/npi/v10/session/bootstrap", method="GET"
        )
        router = importlib.import_module("npi_core.bff")

        router.route_request()

        self.assertNotIn("cmd", self.frappe.local.form_dict)
        self.assertFalse(self.frappe.flags.npi_bff_request)

    def test_bff_response_is_not_wrapped_in_frappe_message_envelope(self) -> None:
        self.frappe.flags.npi_bff_request = True

        result = self.adapter.get_session_bootstrap()

        self.assertIsNone(result)
        self.assertEqual(self.frappe.flags.npi_response_body["language"], "zh-TW")
        self.assertNotIn("message", self.frappe.local.response)
        self.assertNotIn("headers", self.frappe.local.response)
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Content-Type"],
            "application/json",
        )

    def test_bff_metadata_is_attached_as_real_http_headers(self) -> None:
        router = importlib.import_module("npi_core.bff")
        self.frappe.flags.npi_response_headers = {
            "Content-Type": "application/problem+json",
            "X-Trace-ID": "trace-response-header",
        }
        self.frappe.flags.npi_response_body = {
            "type": "urn:npi:problem:test",
            "status": 418,
        }
        response = self.StubHttpResponse()

        router.attach_response_headers(response=response)

        self.assertEqual(response.headers, self.frappe.flags.npi_response_headers)
        self.assertEqual(
            response.data,
            b'{"type":"urn:npi:problem:test","status":418}',
        )

    def test_pre_handler_csrf_error_is_a_clean_npi_problem(self) -> None:
        router = importlib.import_module("npi_core.bff")
        self.request_headers["X-Trace-ID"] = "trace-csrf-rejected"
        self.frappe.local.request = types.SimpleNamespace(
            path="/api/npi/v1/session/language", method="PUT"
        )
        self.frappe.local.response = self.StubResponse(
            exc_type="CSRFTokenError",
            exception="sensitive Frappe envelope detail",
        )
        response = self.StubHttpResponse(status_code=400)

        router.attach_response_headers(
            response=response, request=self.frappe.local.request
        )

        body = json.loads(response.data)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(body["code"], "CSRF_TOKEN_INVALID")
        self.assertTrue(body["retryable"])
        self.assertEqual(body["traceId"], "trace-csrf-rejected")
        self.assertEqual(
            response.headers["Content-Type"], "application/problem+json"
        )
        self.assertEqual(response.headers["X-Trace-ID"], body["traceId"])
        self.assertNotIn("sensitive Frappe envelope detail", response.data.decode())

    def test_pre_handler_malformed_json_is_a_clean_npi_problem(self) -> None:
        router = importlib.import_module("npi_core.bff")
        self.frappe.local.request = types.SimpleNamespace(
            path="/api/npi/v1/session/language", method="PUT"
        )
        self.frappe.local.response = self.StubResponse(
            exc_type="JSONDecodeError",
            exception="raw parser detail",
        )
        response = self.StubHttpResponse(status_code=500)

        router.attach_response_headers(
            response=response, request=self.frappe.local.request
        )

        body = json.loads(response.data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(body["code"], "MALFORMED_REQUEST")
        self.assertEqual(
            response.headers["Content-Type"], "application/problem+json"
        )
        self.assertEqual(response.headers["X-Trace-ID"], body["traceId"])
        self.assertNotIn("raw parser detail", response.data.decode())

    def test_unexpected_handler_error_rolls_back_logs_and_returns_problem(self) -> None:
        api = importlib.import_module("npi_core.api")
        self.frappe.flags.npi_bff_request = True
        secret_error_text = "database password must not escape"

        def fail() -> dict[str, object]:
            raise RuntimeError(secret_error_text)

        result = api.frappe_domain_call(fail)

        self.assertIsNone(result)
        body = self.frappe.flags.npi_response_body
        headers = self.frappe.flags.npi_response_headers
        self.assertEqual(self.frappe.local.response.http_status_code, 500)
        self.assertEqual(body["code"], "INTERNAL_SERVER_ERROR")
        self.assertTrue(body["retryable"])
        self.assertEqual(headers["Content-Type"], "application/problem+json")
        self.assertEqual(headers["X-Trace-ID"], body["traceId"])
        self.assertNotIn(secret_error_text, str(body))
        self.assertEqual(self.database.rollback_count, 1)
        self.assertEqual(len(self.logger.messages), 1)
        self.assertIn("RuntimeError", self.logger.messages[0])
        self.assertIn(body["traceId"], self.logger.messages[0])
        self.assertNotIn(secret_error_text, self.logger.messages[0])
        self.assertEqual(len(self.logged_errors), 1)
        self.assertTrue(self.logged_errors[0]["defer_insert"])
        self.assertNotIn(secret_error_text, str(self.logged_errors[0]))


class LocalizationContractTest(unittest.TestCase):
    def test_openapi_exposes_session_localization_contract(self) -> None:
        contract = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")
        self.assertIn("  version: 1.2.0", contract)
        self.assertIn("  /session/bootstrap:", contract)
        self.assertIn("  /session/language:", contract)
        self.assertIn("  /session/preferences/navigation:", contract)
        self.assertIn("enum: [en, zh, zh-TW]", contract)
        self.assertIn("SessionBootstrap:", contract)
        self.assertIn("SessionPreferences:", contract)
        self.assertIn("SetSessionNavigationPreference:", contract)
        self.assertIn("TranslationCatalog:", contract)
        self.assertIn("name: X-Frappe-CSRF-Token", contract)
        self.assertIn(
            (
                "required: [userId, language, allowedLanguages, "
                "csrfToken, catalog, preferences]"
            ),
            contract,
        )
        self.assertIn("required: [navigationCollapsed]", contract)
        self.assertIn("required: [collapsed]", contract)
        self.assertIn("additionalProperties: false", contract)

    def test_translation_csv_is_in_package_data(self) -> None:
        package_config = (ROOT / "apps/npi_core/pyproject.toml").read_text(
            encoding="utf-8"
        )
        self.assertIn('"translations/*.csv"', package_config)

    def test_site_initialization_preserves_reviewed_source_catalogs(self) -> None:
        site_initializer = (ROOT / "scripts/init-npi-site.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('run_bench --site "${site_name}" clear-cache', site_initializer)
        self.assertNotIn("build-message-files", site_initializer)

    def test_runtime_verifier_refreshes_csrf_on_the_session_it_mutates(
        self,
    ) -> None:
        runtime_verifier = (
            ROOT / "scripts/verify_frappe_runtime.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "fixture_after_navigation = request(\n"
            "            fixture_opener,",
            runtime_verifier,
        )
        self.assertIn(
            'fixture_after_navigation.body["csrfToken"]',
            runtime_verifier,
        )
        self.assertNotIn(
            'fixture_csrf_token = str(navigation_expanded.body["csrfToken"])',
            runtime_verifier,
        )


if __name__ == "__main__":
    unittest.main()
