from __future__ import annotations

import importlib
import json
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))


class InboundProjectConnectorRuntimeTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_integration.inbound_project.runtime_fixture",
        "npi_integration.inbound_project.connector_runtime",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        frappe = types.ModuleType("frappe")
        frappe.conf = {
            "npi_erp_project_ingress_enabled": True,
            "npi_erp_project_ingress_profile": self.profile(),
        }
        sys.modules["frappe"] = frappe
        self.frappe = frappe
        self.module = importlib.import_module(
            "npi_integration.inbound_project.connector_runtime"
        )

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    @staticmethod
    def profile(**changes: object) -> dict[str, object]:
        value: dict[str, object] = {
            "profileId": "erpnext-test-project-v1",
            "profileVersion": 1,
            "tenantId": "TENANT-SANDBOX",
            "environmentCode": "test",
            "serviceActorUserId": "integration-worker@example.invalid",
            "ownerUserId": "kaibo_wang@whjichen.cn",
            "templateGlobalId": "00000000-0000-4000-8000-000000009001",
            "templateVersion": 1,
            "projectType": "new_tool",
            "keyId": "erpnext-test-project-v1",
            "secretReference": "secrets/erpnext-test-project-v1",
            "validFrom": "2026-09-01T00:00:00Z",
            "validUntil": "2027-09-01T00:00:00Z",
        }
        value.update(changes)
        return value

    def test_resolves_only_explicit_nonproduction_project_profile(self) -> None:
        profile = self.module.resolve_profile()
        self.assertEqual(profile.environment_code, "test")
        self.assertEqual(
            profile.policies[0].owner_user_id,
            "kaibo_wang@whjichen.cn",
        )
        self.assertEqual(
            [event.value for event in profile.allowed_event_types],
            ["erpnext.project.created"],
        )
        self.frappe.conf["npi_erp_project_ingress_enabled"] = False
        self.assertIsNone(self.module.resolve_profile())

    def test_secret_is_resolved_only_from_bounded_runtime_environment(self) -> None:
        serialized = json.dumps(
            {
                "secrets/erpnext-test-project-v1": (
                    "project-signing-secret-material-000000000001"
                )
            }
        )
        with patch.dict(
            os.environ,
            {"NPI_ERP_PROJECT_INGRESS_SECRETS": serialized},
            clear=False,
        ):
            self.assertEqual(
                self.module.resolve_secret("secrets/erpnext-test-project-v1"),
                b"project-signing-secret-material-000000000001",
            )
            with self.assertRaises(KeyError):
                self.module.resolve_secret("secrets/unknown")

    def test_rejects_production_and_unknown_profile_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-production"):
            self.module.load_project_ingress_profile(
                self.profile(environmentCode="production")
            )
        with self.assertRaisesRegex(ValueError, "shape"):
            self.module.load_project_ingress_profile(
                {**self.profile(), "rawSecret": "must-not-be-accepted"}
            )


if __name__ == "__main__":
    unittest.main()
