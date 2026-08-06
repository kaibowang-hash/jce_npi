from __future__ import annotations

import importlib
import json
import sys
import types
import unittest
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "npi_core"))
sys.path.insert(0, str(ROOT / "apps" / "npi_integration"))

TENANT_ID = "tenant-a"
PROJECT_ID = UUID("10000000-0000-4000-8000-000000000001")
POLICY_ID = UUID("10000000-0000-4000-8000-000000000002")
VERSION_ID = UUID("10000000-0000-4000-8000-000000000003")
ACTOR_USER = "publish.actor@example.invalid"
POLICY_KEY = "synthetic_publish_policy"


class StubDocument:
    def __init__(self, values: dict[str, Any] | None = None) -> None:
        for fieldname, value in (values or {}).items():
            setattr(self, fieldname, value)
        self._previous = None

    def get(self, fieldname: str) -> Any:
        return getattr(self, fieldname, None)

    def get_doc_before_save(self) -> Any:
        return self._previous


class Phase5PublishPolicyControllerTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "frappe.model",
        "frappe.model.document",
        "npi_core.documents.frappe_validation",
        "npi_integration.publish_request.domain",
        "npi_integration.publish_request.frappe_validation",
        (
            "npi_integration.npi_integration.doctype."
            "npi_ebom_publish_policy_version.npi_ebom_publish_policy_version"
        ),
    )

    def setUp(self) -> None:
        self.saved_modules = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)

        self.ValidationError = type("ValidationError", (Exception,), {})
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.ValidationError = self.ValidationError
        frappe.PermissionError = type("PermissionError", (Exception,), {})
        frappe.flags = types.SimpleNamespace()
        frappe.session = types.SimpleNamespace(user="Administrator")

        def throw(message: str, error_type: type[Exception]) -> None:
            raise error_type(message)

        frappe.throw = throw

        def get_value(
            doctype: str,
            name: object,
            fields: list[str],
            *,
            as_dict: bool = False,
        ) -> dict[str, object] | None:
            self.assertTrue(as_dict)
            if doctype == "NPI EBOM Publish Policy" and name == str(POLICY_ID):
                return {
                    "global_id": str(POLICY_ID),
                    "tenant_id": TENANT_ID,
                    "project_global_id": str(PROJECT_ID),
                    "policy_key": POLICY_KEY,
                    "enabled": 1,
                }
            if doctype == "User" and name == ACTOR_USER:
                return {
                    "name": ACTOR_USER,
                    "enabled": 1,
                    "user_type": "System User",
                }
            return None

        frappe.db = types.SimpleNamespace(get_value=get_value)
        model = types.ModuleType("frappe.model")
        document = types.ModuleType("frappe.model.document")
        document.Document = StubDocument
        model.document = document
        frappe.model = model
        sys.modules["frappe"] = frappe
        sys.modules["frappe.model"] = model
        sys.modules["frappe.model.document"] = document

        self.domain = importlib.import_module(
            "npi_integration.publish_request.domain"
        )
        controller = importlib.import_module(
            "npi_integration.npi_integration.doctype."
            "npi_ebom_publish_policy_version.npi_ebom_publish_policy_version"
        )
        self.Controller = controller.NPIEBOMPublishPolicyVersion

    def tearDown(self) -> None:
        for name in self.MODULES:
            previous = self.saved_modules.get(name)
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous

    def test_requester_ids_are_canonical_before_frappe_persistence(self) -> None:
        snapshot = {
            "schemaVersion": 1,
            "globalId": str(VERSION_ID),
            "policyGlobalId": str(POLICY_ID),
            "tenantId": TENANT_ID,
            "projectGlobalId": str(PROJECT_ID),
            "policyKey": POLICY_KEY,
            "policyVersion": 1,
            "title": "Synthetic publish policy",
            "publicationState": "published",
            "targetMode": "mock",
            "apiVersion": "npi.erp-publish.v1",
            "operation": "publish_released_ebom_item_mbom",
            "requesterUserIds": [ACTOR_USER],
        }
        document = self.Controller(
            {
                "global_id": str(VERSION_ID),
                "publish_policy": str(POLICY_ID),
                "tenant_id": TENANT_ID,
                "project_global_id": str(PROJECT_ID),
                "policy_global_id": str(POLICY_ID),
                "policy_key": POLICY_KEY,
                "policy_version": 1,
                "version_key": f"{POLICY_ID}:1",
                "title": "Synthetic publish policy",
                "publication_state": "published",
                "target_mode": "mock",
                "api_version": "npi.erp-publish.v1",
                "operation": "publish_released_ebom_item_mbom",
                "requester_user_ids": [ACTOR_USER],
                "policy_snapshot": snapshot,
                "snapshot_hash": self.domain.sha256_json(snapshot),
                "published_at": datetime(2026, 8, 6, 12, 0, tzinfo=UTC),
                "optimistic_version": 1,
            }
        )

        document.before_validate()
        document.validate()

        self.assertIsInstance(document.requester_user_ids, str)
        self.assertEqual(json.loads(document.requester_user_ids), [ACTOR_USER])
        self.assertEqual(
            document.requester_user_ids,
            json.dumps([ACTOR_USER], separators=(",", ":"), sort_keys=True),
        )


if __name__ == "__main__":
    unittest.main()
