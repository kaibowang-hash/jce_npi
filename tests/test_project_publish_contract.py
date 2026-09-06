from __future__ import annotations

import json
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for app in ("npi_integration", "npi_erpnext_connector"):
    path = str(ROOT / "apps" / app)
    if path not in sys.path:
        sys.path.insert(0, path)

from npi_erpnext_connector.project_publish_contract import (  # noqa: E402
    ProjectPublishContractError,
    decode_publish_command,
    decode_reconcile_command,
)
from npi_integration.project_publish.domain import (  # noqa: E402
    ProjectSource,
    PublishCommand,
    ReconcileCommand,
    canonical_json,
)


class ProjectPublishContractTest(unittest.TestCase):
    def source(self) -> ProjectSource:
        return ProjectSource(
            tenant_id="jce",
            project_global_id="00000000-0000-4000-8000-000000000101",
            business_code="MM-35029",
            title="MM-35029 program",
            project_type="new_tool",
            target_sop="2027-01-31",
            actor_user_id="kaibo_wang@whjichen.cn",
            source_version=1,
        )

    def test_npi_publish_command_is_accepted_by_erpnext_receiver(self) -> None:
        source = self.source()
        payload = PublishCommand(
            "00000000-0000-4000-8000-000000000102",
            "00000000-0000-4000-8000-000000000103",
            1,
            source,
        ).payload()
        decoded = decode_publish_command(canonical_json(payload).encode())
        self.assertEqual(decoded.project_global_id, source.project_global_id)
        self.assertEqual(decoded.actor_user_id, "kaibo_wang@whjichen.cn")
        self.assertEqual(decoded.business_code, "MM-35029")
        self.assertEqual(decoded.source_hash, source.source_hash)
        self.assertEqual(
            decoded.target_idempotency_key_hash,
            source.target_idempotency_key_hash,
        )

    def test_npi_reconciliation_is_accepted_by_erpnext_receiver(self) -> None:
        source = self.source()
        payload = ReconcileCommand(
            "00000000-0000-4000-8000-000000000102",
            "00000000-0000-4000-8000-000000000104",
            source,
        ).payload()
        decoded = decode_reconcile_command(canonical_json(payload).encode())
        self.assertEqual(decoded.source_hash, source.source_hash)
        self.assertEqual(
            decoded.target_idempotency_key_hash,
            source.target_idempotency_key_hash,
        )

    def test_contract_rejects_payload_tampering_and_duplicate_keys(self) -> None:
        source = self.source()
        payload = PublishCommand(
            "00000000-0000-4000-8000-000000000102",
            "00000000-0000-4000-8000-000000000103",
            1,
            source,
        ).payload()
        payload["source"] = {**payload["source"], "title": "Changed after hash"}
        with self.assertRaisesRegex(ProjectPublishContractError, "hash"):
            decode_publish_command(canonical_json(payload).encode())
        with self.assertRaisesRegex(ProjectPublishContractError, "duplicate"):
            decode_publish_command(b'{"contractVersion":1,"contractVersion":1}')


class ProjectProfileInheritanceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.saved = sys.modules.get("frappe")
        frappe = types.ModuleType("frappe")
        frappe.db = types.SimpleNamespace(exists=self.exists)
        sys.modules["frappe"] = frappe
        self.bound = True

    def tearDown(self) -> None:
        sys.modules.pop("frappe", None)
        if self.saved is not None:
            sys.modules["frappe"] = self.saved

    def exists(self, doctype: str, filters: object) -> bool:
        del filters
        return self.bound and doctype == "NPI ERP Project Publish Request"

    def test_inherits_only_one_identical_bound_tenant_template(self) -> None:
        from npi_integration.project_publish.profile_inheritance import (
            inherited_project_profile,
        )

        base = {
            "profileId": "project-a",
            "profileVersion": 1,
            "tenantId": "jce",
            "projectGlobalId": "00000000-0000-4000-8000-000000000201",
            "environmentCode": "test",
        }
        second = {
            **base,
            "profileId": "project-b",
            "projectGlobalId": "00000000-0000-4000-8000-000000000202",
        }
        result = inherited_project_profile(
            [base, second],
            "jce",
            "00000000-0000-4000-8000-000000000203",
            family="item",
        )
        assert result is not None
        self.assertEqual(
            result["projectGlobalId"],
            "00000000-0000-4000-8000-000000000203",
        )
        self.assertTrue(str(result["profileId"]).startswith("item-inherited-"))

        with self.assertRaisesRegex(ValueError, "ambiguous"):
            inherited_project_profile(
                [base, {**second, "environmentCode": "qa"}],
                "jce",
                "00000000-0000-4000-8000-000000000203",
                family="item",
            )

        self.bound = False
        self.assertIsNone(
            inherited_project_profile(
                [base],
                "jce",
                "00000000-0000-4000-8000-000000000203",
                family="item",
            )
        )


if __name__ == "__main__":
    unittest.main()
