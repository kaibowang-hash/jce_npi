from __future__ import annotations

import importlib
import sys
import types
import unittest
from typing import Any


sys.path.insert(0, "apps/npi_core")


ACTOR = "engineer@example.invalid"
OTHER_ACTOR = "planner@example.invalid"
EXTERNAL_ACTOR = "external@example.invalid"
REQUEST_ID = "c52c33c1-5e30-4217-91bb-3565a48283df"
TRACE_ID = "trace-r105-inspector-preference"


class AttrDict(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class StubResponse(dict):
    def __getattr__(self, name: str) -> Any:
        return self.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class StubDatabase:
    def __init__(self) -> None:
        self.rollback_count = 0
        self.user_types = {
            ACTOR: "System User",
            OTHER_ACTOR: "System User",
            EXTERNAL_ACTOR: "Website User",
        }

    def get_value(
        self,
        doctype: str,
        name_or_filters: object,
        fieldname: object,
        **_kwargs: object,
    ) -> object | None:
        if doctype == "User" and fieldname == "user_type":
            return self.user_types.get(str(name_or_filters))
        return None

    def rollback(self) -> None:
        self.rollback_count += 1


class MemoryInspectorPreferenceStore:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], object] = {}
        self.cache: dict[str, dict[str, object]] = {}
        self.read_calls: list[tuple[str, str]] = []
        self.write_calls: list[tuple[str, str, str]] = []
        self.invalidate_calls: list[str] = []
        self.fail_read = False
        self.fail_write = False
        self.fail_invalidate = False
        self.silent_write = False

    def read(self, *, actor_user_id: str, key: str) -> object | None:
        self.read_calls.append((actor_user_id, key))
        if self.fail_read:
            raise RuntimeError("Synthetic inspector preference read failure.")
        if actor_user_id not in self.cache:
            self.cache[actor_user_id] = {
                stored_key: value
                for (stored_actor, stored_key), value in self.values.items()
                if stored_actor == actor_user_id
            }
        return self.cache[actor_user_id].get(key)

    def write(
        self,
        *,
        actor_user_id: str,
        key: str,
        value: str,
    ) -> None:
        self.write_calls.append((actor_user_id, key, value))
        if self.fail_write:
            raise RuntimeError("Synthetic inspector preference write failure.")
        if not self.silent_write:
            self.values[(actor_user_id, key)] = value

    def invalidate(self, *, actor_user_id: str) -> None:
        self.invalidate_calls.append(actor_user_id)
        if self.fail_invalidate:
            raise RuntimeError("Synthetic inspector preference cache failure.")
        self.cache.pop(actor_user_id, None)

    def seed(self, actor_user_id: str, key: str, value: object) -> None:
        self.values[(actor_user_id, key)] = value
        self.cache.pop(actor_user_id, None)


class InspectorPreferenceApiTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "frappe.defaults",
        "frappe.sessions",
        "npi_core.inspector_preferences.domain",
        "npi_core.inspector_preferences.frappe_repository",
        "npi_core.inspector_preferences_api",
        "npi_core.bff",
    )

    def setUp(self) -> None:
        self.saved_modules = {
            name: sys.modules.get(name) for name in self.MODULES
        }
        for name in self.MODULES:
            sys.modules.pop(name, None)

        self.headers = {
            "X-Frappe-CSRF-Token": "csrf-" + ("a" * 48),
            "X-Request-ID": REQUEST_ID,
            "X-Trace-ID": TRACE_ID,
        }
        self.clear_cache_calls: list[str] = []
        self.default_clears: list[tuple[str, str | None]] = []
        self.default_reads: list[str] = []
        self.default_writes: list[
            tuple[str, str, str | None, str | None]
        ] = []
        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.conf = AttrDict(
            npi_tenant_id="TENANT-A",
            npi_p4_05_routes_disabled=False,
        )
        self.frappe.flags = types.SimpleNamespace(npi_bff_request=False)
        self.frappe.session = types.SimpleNamespace(user=ACTOR)
        self.frappe.local = types.SimpleNamespace(
            form_dict=AttrDict(),
            request=types.SimpleNamespace(path="/", method="GET"),
            response=StubResponse(),
        )
        self.frappe.db = StubDatabase()
        self.frappe.get_roles = lambda _actor: ["NPI API User"]
        self.frappe.get_request_header = lambda name: self.headers.get(name)
        self.frappe.clear_cache = (
            lambda user: self.clear_cache_calls.append(user)
        )
        self.frappe.log_error = lambda **_values: None
        self.frappe.logger = lambda _name: types.SimpleNamespace(
            error=lambda *_args, **_kwargs: None
        )

        def whitelist(*, methods: list[str], allow_guest: bool = False):
            def decorate(function):
                function.allowed_methods = tuple(methods)
                function.allow_guest = allow_guest
                return function

            return decorate

        self.frappe.whitelist = whitelist

        defaults = types.ModuleType("frappe.defaults")

        def get_defaults_for(parent: str) -> dict[str, object]:
            self.default_reads.append(parent)
            return {}

        def clear_user_default(
            key: str,
            user: str | None = None,
        ) -> None:
            self.default_clears.append((key, user))

        def add_user_default(
            key: str,
            value: str,
            user: str | None = None,
            parenttype: str | None = None,
        ) -> None:
            self.default_writes.append((key, value, user, parenttype))

        def set_user_default(
            key: str,
            value: str,
            user: str | None = None,
            parenttype: str | None = None,
        ) -> None:
            self.default_writes.append((key, value, user, parenttype))

        defaults.add_user_default = add_user_default
        defaults.clear_user_default = clear_user_default
        defaults.get_defaults_for = get_defaults_for
        defaults.set_user_default = set_user_default
        self.frappe.defaults = defaults

        sessions = types.ModuleType("frappe.sessions")
        sessions.get_csrf_token = lambda: "csrf-" + ("a" * 48)
        self.frappe.sessions = sessions

        sys.modules["frappe"] = self.frappe
        sys.modules["frappe.defaults"] = defaults
        sys.modules["frappe.sessions"] = sessions

        self.repository_module = importlib.import_module(
            "npi_core.inspector_preferences.frappe_repository"
        )
        self.domain = importlib.import_module(
            "npi_core.inspector_preferences.domain"
        )
        self.api = importlib.import_module(
            "npi_core.inspector_preferences_api"
        )
        self.router = importlib.import_module("npi_core.bff")
        self.store = MemoryInspectorPreferenceStore()
        self.factory_actors: list[str] = []

        def repository_factory(*, actor_user_id: str):
            self.factory_actors.append(actor_user_id)
            return self.repository_module.FrappeInspectorPreferenceRepository(
                actor_user_id=actor_user_id,
                store=self.store,
            )

        self.api._repository_factory = repository_factory

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
        for name, module in self.saved_modules.items():
            if module is not None:
                sys.modules[name] = module

    def reset_request(self, *, user: str = ACTOR) -> None:
        self.frappe.session.user = user
        self.frappe.local.form_dict = AttrDict()
        self.frappe.local.request = types.SimpleNamespace(
            path="/",
            method="GET",
        )
        self.frappe.local.response = StubResponse()
        self.frappe.flags.npi_bff_request = False
        self.frappe.flags.npi_response_body = None
        self.frappe.flags.npi_response_headers = None

    def call(self, function, payload: dict[str, object]):
        command = "npi_core.inspector_preferences_api." + function.__name__
        self.frappe.local.form_dict = AttrDict({"cmd": command, **payload})
        return function(**payload)

    def put_payload(
        self,
        *,
        width_px: object = 340,
        collapsed: object = False,
        schema_version: object = "my-work-inspector-v1",
    ) -> dict[str, object]:
        return {
            "schemaVersion": schema_version,
            "widthPx": width_px,
            "collapsed": collapsed,
        }

    def assert_problem(
        self,
        result: object,
        *,
        status: int,
        code: str,
    ) -> dict[str, object]:
        self.assertIsInstance(result, dict)
        assert isinstance(result, dict)
        self.assertEqual(result["status"], status)
        self.assertEqual(result["code"], code)
        self.assertEqual(
            self.frappe.local.response.http_status_code,
            status,
        )
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Cache-Control"],
            "private, no-store",
        )
        self.assertEqual(
            result["traceId"],
            self.frappe.flags.npi_response_headers["X-Trace-ID"],
        )
        return result

    def test_default_and_valid_put_are_exact_and_cache_confirmed(self) -> None:
        result = self.call(
            self.api.get_my_work_inspector_preference,
            {},
        )
        self.assertEqual(
            result,
            {
                "paneId": "my-work-inspector",
                "schemaVersion": "my-work-inspector-v1",
                "widthPx": 340,
                "collapsed": False,
                "recoveryReason": None,
            },
        )
        self.assertEqual(self.store.write_calls, [])
        self.assertEqual(self.factory_actors, [ACTOR])
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Cache-Control"],
            "private, no-store",
        )
        self.assertEqual(
            self.frappe.flags.npi_response_headers["X-Request-ID"],
            REQUEST_ID,
        )

        # Prime a stale actor cache; save must invalidate it before confirming.
        self.store.cache[ACTOR] = {}
        self.reset_request()
        result = self.call(
            self.api.set_my_work_inspector_preference,
            self.put_payload(width_px=480, collapsed=True),
        )
        self.assertEqual(
            result,
            {
                "paneId": "my-work-inspector",
                "schemaVersion": "my-work-inspector-v1",
                "widthPx": 480,
                "collapsed": True,
                "recoveryReason": None,
            },
        )
        self.assertEqual(
            self.store.write_calls,
            [
                (
                    ACTOR,
                    self.domain.USER_DEFAULT_KEY,
                    (
                        '{"collapsed":true,'
                        '"schemaVersion":"my-work-inspector-v1",'
                        '"widthPx":480}'
                    ),
                )
            ],
        )
        self.assertEqual(self.store.invalidate_calls, [ACTOR])
        self.assertEqual(
            self.api.get_my_work_inspector_preference.allowed_methods,
            ("GET",),
        )
        self.assertEqual(
            self.api.set_my_work_inspector_preference.allowed_methods,
            ("PUT",),
        )
        self.assertTrue(self.api.get_my_work_inspector_preference.allow_guest)
        self.assertTrue(self.api.set_my_work_inspector_preference.allow_guest)

    def test_corrupt_storage_falls_back_without_get_repair(self) -> None:
        corrupt_values = (
            "{",
            "[]",
            (
                '{"schemaVersion":"future","widthPx":340,'
                '"collapsed":false}'
            ),
            (
                '{"schemaVersion":"my-work-inspector-v1","widthPx":"340",'
                '"collapsed":false}'
            ),
            (
                '{"schemaVersion":"my-work-inspector-v1","widthPx":259,'
                '"collapsed":false}'
            ),
            (
                '{"schemaVersion":"my-work-inspector-v1","widthPx":481,'
                '"collapsed":false}'
            ),
            (
                '{"schemaVersion":"my-work-inspector-v1","widthPx":340,'
                '"collapsed":0}'
            ),
            (
                '{"schemaVersion":"my-work-inspector-v1","widthPx":340,'
                '"collapsed":false,"actor":"other"}'
            ),
            '{"schemaVersion":"my-work-inspector-v1","widthPx":340}',
            (
                '{"schemaVersion":"my-work-inspector-v1","widthPx":340,'
                '"widthPx":341,"collapsed":false}'
            ),
        )
        for corrupt_value in corrupt_values:
            with self.subTest(corrupt_value=corrupt_value):
                self.store.seed(
                    ACTOR,
                    self.domain.USER_DEFAULT_KEY,
                    corrupt_value,
                )
                before_writes = list(self.store.write_calls)
                self.reset_request()
                first = self.call(
                    self.api.get_my_work_inspector_preference,
                    {},
                )
                self.reset_request()
                second = self.call(
                    self.api.get_my_work_inspector_preference,
                    {},
                )

                self.assertEqual(first, second)
                self.assertEqual(first["widthPx"], 340)
                self.assertIs(first["collapsed"], False)
                self.assertEqual(
                    first["recoveryReason"],
                    "stored_preference_invalid",
                )
                self.assertEqual(self.store.write_calls, before_writes)
                self.assertEqual(
                    self.store.values[
                        (ACTOR, self.domain.USER_DEFAULT_KEY)
                    ],
                    corrupt_value,
                )

    def test_put_rejects_missing_extra_schema_width_and_boolean_values(
        self,
    ) -> None:
        cases = []
        missing = self.put_payload()
        missing.pop("widthPx")
        cases.append((missing, "widthPx"))
        cases.append(
            (
                {**self.put_payload(), "actor": OTHER_ACTOR},
                "actor",
            )
        )
        cases.append(
            (
                self.put_payload(schema_version="future-schema"),
                "schemaVersion",
            )
        )
        for invalid_width in (259, 481, True, False, 340.0, "340", None):
            cases.append(
                (
                    self.put_payload(width_px=invalid_width),
                    "widthPx",
                )
            )
        for invalid_collapsed in (0, 1, "false", None, [], {}):
            cases.append(
                (
                    self.put_payload(collapsed=invalid_collapsed),
                    "collapsed",
                )
            )

        for payload, expected_path in cases:
            with self.subTest(payload=payload):
                self.reset_request()
                problem = self.call(
                    self.api.set_my_work_inspector_preference,
                    payload,
                )
                validated = self.assert_problem(
                    problem,
                    status=422,
                    code="VALIDATION_FAILED",
                )
                self.assertEqual(
                    validated["fieldErrors"][0]["path"],
                    expected_path,
                )
        self.assertEqual(self.store.write_calls, [])

    def test_guest_external_csrf_and_route_switch_fail_closed(self) -> None:
        self.reset_request(user="Guest")
        guest = self.call(
            self.api.get_my_work_inspector_preference,
            {"actor": ACTOR},
        )
        self.assert_problem(
            guest,
            status=401,
            code="AUTHENTICATION_REQUIRED",
        )

        self.reset_request(user=EXTERNAL_ACTOR)
        external = self.call(
            self.api.get_my_work_inspector_preference,
            {},
        )
        self.assert_problem(
            external,
            status=403,
            code="PERMISSION_DENIED",
        )

        self.reset_request()
        self.headers.pop("X-Frappe-CSRF-Token")
        csrf = self.call(
            self.api.set_my_work_inspector_preference,
            self.put_payload(),
        )
        self.assert_problem(
            csrf,
            status=403,
            code="CSRF_TOKEN_INVALID",
        )
        self.headers["X-Frappe-CSRF-Token"] = "csrf-" + ("a" * 48)

        self.reset_request()
        reads_before_disable = len(self.store.read_calls)
        self.frappe.conf["npi_p4_05_routes_disabled"] = True
        disabled = self.call(
            self.api.get_my_work_inspector_preference,
            {},
        )
        self.assert_problem(
            disabled,
            status=503,
            code="PROJECT_COLLABORATION_ROUTES_DISABLED",
        )
        self.assertEqual(len(self.store.read_calls), reads_before_disable)
        self.frappe.conf["npi_p4_05_routes_disabled"] = False
        self.assertEqual(self.store.write_calls, [])

    def test_actor_bound_storage_never_crosses_users(self) -> None:
        first = self.call(
            self.api.set_my_work_inspector_preference,
            self.put_payload(width_px=300, collapsed=True),
        )
        self.assertEqual(first["widthPx"], 300)

        self.reset_request(user=OTHER_ACTOR)
        other_default = self.call(
            self.api.get_my_work_inspector_preference,
            {},
        )
        self.assertEqual(other_default["widthPx"], 340)
        self.assertIs(other_default["collapsed"], False)

        self.reset_request(user=OTHER_ACTOR)
        other_saved = self.call(
            self.api.set_my_work_inspector_preference,
            self.put_payload(width_px=420, collapsed=False),
        )
        self.assertEqual(other_saved["widthPx"], 420)

        self.reset_request(user=ACTOR)
        first_again = self.call(
            self.api.get_my_work_inspector_preference,
            {},
        )
        self.assertEqual(first_again["widthPx"], 300)
        self.assertIs(first_again["collapsed"], True)
        self.assertEqual(
            {
                (actor, key)
                for actor, key in self.store.values
            },
            {
                (ACTOR, self.domain.USER_DEFAULT_KEY),
                (OTHER_ACTOR, self.domain.USER_DEFAULT_KEY),
            },
        )

    def test_storage_failures_and_confirmation_mismatch_are_not_success(
        self,
    ) -> None:
        self.store.fail_read = True
        read_failure = self.call(
            self.api.get_my_work_inspector_preference,
            {},
        )
        self.assert_problem(
            read_failure,
            status=500,
            code="INTERNAL_SERVER_ERROR",
        )
        self.assertEqual(self.frappe.db.rollback_count, 1)

        self.store.fail_read = False
        self.store.fail_write = True
        self.reset_request()
        write_failure = self.call(
            self.api.set_my_work_inspector_preference,
            self.put_payload(width_px=360),
        )
        self.assert_problem(
            write_failure,
            status=500,
            code="INTERNAL_SERVER_ERROR",
        )
        self.assertEqual(self.frappe.db.rollback_count, 2)
        self.assertEqual(self.store.invalidate_calls, [ACTOR])

        self.store.fail_write = False
        self.store.silent_write = True
        self.reset_request()
        mismatch = self.call(
            self.api.set_my_work_inspector_preference,
            self.put_payload(width_px=380),
        )
        self.assert_problem(
            mismatch,
            status=500,
            code="INTERNAL_SERVER_ERROR",
        )
        self.assertEqual(self.frappe.db.rollback_count, 3)
        self.assertEqual(self.store.invalidate_calls, [ACTOR, ACTOR, ACTOR])
        self.assertNotIn(
            (ACTOR, self.domain.USER_DEFAULT_KEY),
            self.store.values,
        )

    def test_frappe_store_uses_only_fixed_explicit_user_default_scope(
        self,
    ) -> None:
        raw = (
            '{"collapsed":false,"schemaVersion":"my-work-inspector-v1",'
            '"widthPx":340}'
        )
        self.repository_module.get_defaults_for = (
            lambda parent: (
                self.default_reads.append(parent)
                or {self.domain.USER_DEFAULT_KEY: raw}
            )
        )
        self.repository_module.clear_user_default = (
            lambda key, user=None: self.default_clears.append((key, user))
        )
        self.repository_module.add_user_default = (
            lambda key, value, user=None, parenttype=None: (
                self.default_writes.append(
                    (key, value, user, parenttype)
                )
            )
        )
        store = (
            self.repository_module.FrappeUserDefaultInspectorPreferenceStore()
        )

        self.assertEqual(
            store.read(
                actor_user_id=ACTOR,
                key=self.domain.USER_DEFAULT_KEY,
            ),
            raw,
        )
        store.write(
            actor_user_id=ACTOR,
            key=self.domain.USER_DEFAULT_KEY,
            value=raw,
        )
        store.invalidate(actor_user_id=ACTOR)

        self.assertEqual(self.default_reads, [ACTOR])
        self.assertEqual(
            self.default_clears,
            [(self.domain.USER_DEFAULT_KEY, ACTOR)],
        )
        self.assertEqual(
            self.default_writes,
            [(self.domain.USER_DEFAULT_KEY, raw, ACTOR, "User")],
        )
        self.assertEqual(self.clear_cache_calls, [ACTOR])

    def test_bff_maps_only_fixed_methods_and_honors_route_disable(
        self,
    ) -> None:
        path = "/api/npi/v1/me/preferences/my-work-inspector"
        self.assertEqual(
            self.router.project_collaboration_routes_disabled.allowed_methods,
            ("GET", "POST", "PUT"),
        )
        expected_commands = {
            "GET": (
                "npi_core.inspector_preferences_api."
                "get_my_work_inspector_preference"
            ),
            "PUT": (
                "npi_core.inspector_preferences_api."
                "set_my_work_inspector_preference"
            ),
        }
        for method, expected_command in expected_commands.items():
            with self.subTest(method=method):
                self.reset_request()
                self.frappe.local.request = types.SimpleNamespace(
                    path=path,
                    method=method,
                )
                self.router.route_request()
                self.assertEqual(
                    self.frappe.local.form_dict.cmd,
                    expected_command,
                )
                self.assertEqual(self.frappe.flags.npi_route_params, {})
                self.assertTrue(
                    self.router._requires_project_request_id(method, path)
                )

        self.reset_request()
        self.frappe.local.request = types.SimpleNamespace(
            path=path,
            method="POST",
        )
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.bff.route_not_found",
        )
        self.assertFalse(
            self.router._requires_project_request_id("POST", path)
        )

        self.frappe.conf["npi_p4_05_routes_disabled"] = True
        for method in ("GET", "PUT"):
            with self.subTest(disabled_method=method):
                self.reset_request()
                self.frappe.local.request = types.SimpleNamespace(
                    path=path,
                    method=method,
                )
                self.router.route_request()
                self.assertEqual(
                    self.frappe.local.form_dict.cmd,
                    "npi_core.bff.project_collaboration_routes_disabled",
                )
                self.assertEqual(self.frappe.flags.npi_route_params, {})


if __name__ == "__main__":
    unittest.main()
