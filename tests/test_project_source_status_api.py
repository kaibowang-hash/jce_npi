from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/npi_core"), str(ROOT / "apps/npi_integration")]


class ProjectSourceStatusApiTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_core.api",
        "npi_core.request_security",
        "npi_core.foundation.errors",
        "npi_integration.project_source_status_api",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.session = types.SimpleNamespace(user="integration@example.invalid")
        frappe.get_roles = lambda _user: ["NPI API User"]
        frappe.db = types.SimpleNamespace(get_value=self.get_value)
        frappe.whitelist = lambda **_kwargs: lambda function: function
        sys.modules["frappe"] = frappe

        api = types.ModuleType("npi_core.api")
        api.frappe_domain_call = lambda handle, **_kwargs: handle()
        sys.modules["npi_core.api"] = api

        request_security = types.ModuleType("npi_core.request_security")
        request_security.authenticated_user = lambda: frappe.session.user
        request_security.response_request_id = lambda: str(UUID(int=801))

        def reject_unexpected(expected, observed):
            if set(observed) != set(expected):
                raise ValueError("unexpected request fields")

        request_security.reject_unexpected_request_fields = reject_unexpected
        sys.modules["npi_core.request_security"] = request_security
        self.module = importlib.import_module(
            "npi_integration.project_source_status_api"
        )
        self.frappe = frappe

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    @staticmethod
    def get_value(
        doctype: str,
        name: str,
        fields: list[str],
        *,
        as_dict: bool,
    ) -> dict[str, object] | None:
        assert doctype == "NPI Inbox Message"
        assert fields and as_dict
        if name != str(UUID(int=800)):
            return None
        return {
            "receipt_id": name,
            "event_id": str(UUID(int=802)),
            "state": "succeeded",
            "disposition": "project_created",
            "project_global_id": str(UUID(int=803)),
            "last_error_code": None,
            "trace_id": "erp-project-00000000000000000000000000000000",
        }

    def test_returns_only_bound_receipt_result_to_integration_role(self) -> None:
        result = self.module.get_project_source_receipt(
            receiptId=str(UUID(int=800))
        )
        self.assertEqual(result["state"], "succeeded")
        self.assertTrue(result["terminal"])
        self.assertEqual(result["projectGlobalId"], str(UUID(int=803)))
        self.assertEqual(set(result), {
            "receiptId", "eventId", "state", "terminal", "disposition",
            "projectGlobalId", "errorCode", "traceId",
        })

    def test_rejects_non_integration_roles_and_invalid_receipt_ids(self) -> None:
        self.frappe.get_roles = lambda _user: []
        with self.assertRaises(self.module.PermissionDenied):
            self.module.get_project_source_receipt(receiptId=str(UUID(int=800)))
        self.frappe.get_roles = lambda _user: ["NPI API User"]
        with self.assertRaises(self.module.RequestValidationFailed):
            self.module.get_project_source_receipt(receiptId="not-a-uuid")


if __name__ == "__main__":
    unittest.main()
