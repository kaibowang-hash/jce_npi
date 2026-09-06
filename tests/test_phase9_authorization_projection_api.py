from __future__ import annotations

import importlib
import sys
import types
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/npi_core"), str(ROOT / "apps/npi_integration")]

from npi_integration.authorization_projection.domain import canonical_hash


REQUEST_ID = str(UUID(int=940))


def payload() -> dict[str, object]:
    now = datetime(2026, 9, 3, 8, 0, tzinfo=UTC)
    event_payload: dict[str, object] = {
        "sourceSubjectId": "entra-subject-p904",
        "targetUserId": "member@example.invalid",
        "sourceVersion": 4,
        "enabled": True,
        "roles": ["NPI Engineer"],
        "projectAccess": [],
        "organizationScopes": [],
        "issuedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expiresAt": (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return {
        "schemaVersion": 1,
        "operation": "replace_user_authorization",
        "sourceSystem": "ERPNEXT",
        "targetSystem": "NPI_ONE",
        "objectType": "UserAuthorizationProjection",
        "eventId": str(UUID(int=941)),
        **event_payload,
        "traceId": "trace-p904-api",
        "payloadHash": canonical_hash(event_payload),
    }


class AuthorizationProjectionApiTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_integration.authorization_projection_api",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.rollbacks = 0
        self.headers = {
            "X-Request-ID": REQUEST_ID,
            "X-Trace-ID": "trace-p904-api",
        }
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.flags = types.SimpleNamespace(npi_bff_request=False)
        frappe.local = types.SimpleNamespace(
            response=types.SimpleNamespace(http_status_code=200),
            form_dict={},
        )
        frappe.conf = {
            "npi_p9_04_authorization_projection_routes_disabled": False,
            "npi_tenant_id": "tenant-p904",
        }
        frappe.session = types.SimpleNamespace(user="service@example.invalid")
        frappe.get_request_header = lambda name: self.headers.get(name)
        frappe.get_hooks = lambda _name: []
        frappe.get_attr = lambda _path: None
        frappe.get_roles = lambda _actor: ["NPI API User"]
        frappe.DuplicateEntryError = type("DuplicateEntryError", (Exception,), {})
        frappe.UniqueValidationError = type("UniqueValidationError", (Exception,), {})
        frappe.db = types.SimpleNamespace(rollback=self._rollback)
        frappe.logger = lambda _name: types.SimpleNamespace(error=lambda *_args: None)
        frappe.log_error = lambda **_values: None

        def whitelist(*, allow_guest=False, methods=None):
            def decorate(function):
                function.allow_guest = allow_guest
                function.allowed_methods = tuple(methods or ())
                return function

            return decorate

        frappe.whitelist = whitelist
        sys.modules["frappe"] = frappe
        self.frappe = frappe
        self.module = importlib.import_module(
            "npi_integration.authorization_projection_api"
        )
        self.module.authenticated_user = lambda: frappe.session.user
        self.module.configured_tenant_id = lambda: "tenant-p904"
        self.module.response_request_id = lambda: REQUEST_ID
        self.module.require_service_actor = lambda actor: self.assertEqual(
            actor, frappe.session.user
        )

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def _rollback(self) -> None:
        self.rollbacks += 1

    def test_route_is_default_disabled_before_authentication(self) -> None:
        self.frappe.conf.clear()
        self.module.authenticated_user = lambda: self.fail(
            "Disabled route must stop before actor resolution."
        )
        result = self.module.replace_user_authorization(**payload())
        self.assertEqual(result["code"], "AUTHORIZATION_PROJECTION_ROUTES_DISABLED")
        self.assertEqual(self.frappe.local.response.http_status_code, 503)
        self.assertEqual(self.rollbacks, 1)

    def test_exact_event_retries_one_unique_race_and_returns_truth(self) -> None:
        calls: list[object] = []

        class Repository:
            def __init__(inner, **values):
                calls.append(values)

            def apply(inner, event):
                calls.append(event)
                if sum(hasattr(value, "event_id") for value in calls) == 1:
                    raise self.frappe.DuplicateEntryError()
                return types.SimpleNamespace(
                    projection_id=UUID(int=942),
                    source_version=event.source_version,
                    state="enabled",
                    projection_hash=event.projection_hash,
                    exact_replay=True,
                    local_user_state="enabled",
                    local_user_disposition="exact_replay",
                )

        self.module.FrappeAuthorizationProjectionRepository = Repository
        result = self.module.replace_user_authorization(**payload())

        self.assertEqual(self.rollbacks, 1)
        self.assertEqual(result["projectionId"], str(UUID(int=942)))
        self.assertEqual(result["sourceVersion"], 4)
        self.assertTrue(result["exactReplay"])
        self.assertEqual(result["localUserState"], "enabled")
        self.assertEqual(result["localUserDisposition"], "exact_replay")
        self.assertEqual(result["requestId"], REQUEST_ID)
        self.assertEqual(self.frappe.local.response.http_status_code, 200)
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Cache-Control"],
            "private, no-store",
        )

    def test_unknown_fields_and_invalid_hash_are_validation_failures(self) -> None:
        for changes in (
            {"unexpected": "value"},
            {"payloadHash": "0" * 64},
        ):
            with self.subTest(changes=changes):
                result = self.module.replace_user_authorization(
                    **{**payload(), **changes}
                )
                self.assertEqual(result["code"], "VALIDATION_FAILED")
                self.assertEqual(self.frappe.local.response.http_status_code, 422)


if __name__ == "__main__":
    unittest.main()
