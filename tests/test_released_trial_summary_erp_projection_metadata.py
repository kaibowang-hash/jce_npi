from __future__ import annotations

import ast
import csv
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ERP_APP = ROOT / "apps/npi_erpnext_connector/npi_erpnext_connector"
ERP_DOCTYPES = ERP_APP / "npi_erpnext_connector/doctype"
NPI_APP = ROOT / "apps/npi_integration/npi_integration"
NPI_DOCTYPES = NPI_APP / "npi_integration/doctype"


class ReleasedTrialSummaryERPProjectionMetadataTest(unittest.TestCase):
    def test_erp_projection_is_read_only_but_queryable_by_viewer(self) -> None:
        for directory in ("npi_erp_trial_summary", "npi_erp_trial_summary_fact"):
            metadata = json.loads(
                (ERP_DOCTYPES / directory / f"{directory}.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(metadata["read_only"], 1)
            permissions = {row["role"]: row for row in metadata["permissions"]}
            self.assertEqual(set(permissions), {"System Manager", "NPI ERP Trial Summary Viewer"})
            for row in permissions.values():
                self.assertEqual(row["read"], 1)
                self.assertEqual(row["write"], 0)
                self.assertEqual(row["create"], 0)
                self.assertEqual(row["delete"], 0)
            self.assertTrue(all(field.get("read_only") == 1 for field in metadata["fields"]))

    def test_npi_delivery_and_attempt_are_controlled_history(self) -> None:
        for directory in (
            "npi_trial_summary_delivery",
            "npi_trial_summary_delivery_attempt",
        ):
            metadata = json.loads(
                (NPI_DOCTYPES / directory / f"{directory}.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(metadata["read_only"], 1)
            self.assertTrue(all(field.get("read_only") == 1 for field in metadata["fields"]))
            self.assertFalse(any(row.get("write") for row in metadata["permissions"]))
            self.assertFalse(any(row.get("create") for row in metadata["permissions"]))
            self.assertFalse(any(row.get("delete") for row in metadata["permissions"]))

    def test_transport_has_no_generic_writer_or_database_escape(self) -> None:
        sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                ERP_APP / "trial_summary_api.py",
                ERP_APP / "trial_summary_frappe.py",
                ERP_APP / "frappe_validation.py",
                NPI_APP / "trial_summary_publish/connector_runtime.py",
                NPI_APP / "trial_summary_publish/worker.py",
            )
        )
        for forbidden in (
            "frappe.db." + "sql",
            "frappe.client." + "insert",
            "frappe.client." + "save",
            ".submit(",
            ".cancel(",
            "doctype = command",
            "verify=False",
            "http://",
        ):
            self.assertNotIn(forbidden, sources)

    def test_hook_is_transactional_and_bff_routes_are_fixed(self) -> None:
        hooks = (NPI_APP / "hooks.py").read_text(encoding="utf-8")
        self.assertIn('"NPI Released Trial Summary Revision"', hooks)
        self.assertIn("queue_released_trial_summary", hooks)
        service = (NPI_APP / "trial_summary_publish/service.py").read_text(encoding="utf-8")
        self.assertLess(service.index("insert_support_document"), service.index("frappe.enqueue"))
        self.assertIn("enqueue_after_commit=True", service)
        bff = (ROOT / "apps/npi_core/npi_core/bff.py").read_text(encoding="utf-8")
        self.assertIn("/trial-summary-deliveries", bff)
        self.assertIn("trial_summary_publish.api.retry_delivery", bff)
        self.assertIn("trial_summary_publish.api.request_reconciliation", bff)
        contract = (ROOT / "contracts/npi-api.openapi.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn("name: trialRoundGlobalId", contract)
        self.assertNotIn("name: trial_round_global_id", contract)

    def test_migrations_cover_schema_and_existing_summary_backfill(self) -> None:
        self.assertIn(
            "npi_integration.patches.v0_2.backfill_released_trial_summary_deliveries",
            (NPI_APP / "patches.txt").read_text(encoding="utf-8"),
        )
        backfill = (
            NPI_APP
            / "patches/v0_2/backfill_released_trial_summary_deliveries.py"
        ).read_text(encoding="utf-8")
        self.assertIn("enqueue=False", backfill)
        self.assertIn("page_length=PAGE_SIZE", backfill)
        self.assertIn(
            "npi_erpnext_connector.patches.v0_5.sync_trial_summary_schema",
            (ERP_APP / "patches.txt").read_text(encoding="utf-8"),
        )

    def test_receiver_and_queries_have_distinct_least_privilege_roles(self) -> None:
        source = (ERP_APP / "trial_summary_api.py").read_text(encoding="utf-8")
        self.assertIn('SERVICE_ROLE = "NPI ERP Trial Summary Integration Service"', source)
        self.assertIn('VIEWER_ROLE = "NPI ERP Trial Summary Viewer"', source)
        self.assertIn('user.get("user_type") != "Website User"', source)
        self.assertIn("frappe.has_permission(SUMMARY_DOCTYPE", source)
        self.assertNotIn("allow_guest=True", source)

    def test_delivery_state_machine_has_no_success_redispatch(self) -> None:
        source = (
            NPI_DOCTYPES
            / "npi_trial_summary_delivery/npi_trial_summary_delivery.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"succeeded": frozenset(),', source)
        self.assertIn('"uncertain": frozenset({"processing"}),', source)
        self.assertNotIn('"uncertain": frozenset({"pending"', source)

    def test_erp_connector_remains_python_310_compatible(self) -> None:
        sources = "\n".join(path.read_text(encoding="utf-8") for path in ERP_APP.rglob("*.py"))
        self.assertNotIn("from datetime import UTC", sources)
        self.assertNotIn("from enum import StrEnum", sources)
        for path in (
            ERP_APP / "trial_summary_api.py",
            ERP_APP / "trial_summary_contract.py",
            ERP_APP / "trial_summary_frappe.py",
        ):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_visible_sources_have_symmetric_chinese_translations(self) -> None:
        for app_root, python_files, metadata_files in (
            (
                ERP_APP,
                [
                    ERP_APP / "trial_summary_api.py",
                    ERP_APP / "trial_summary_frappe.py",
                    ERP_APP / "frappe_validation.py",
                    *ERP_DOCTYPES.glob("npi_erp_trial_summary*/*.py"),
                ],
                list(ERP_DOCTYPES.glob("npi_erp_trial_summary*/*.json")),
            ),
            (
                NPI_APP,
                [
                    *NPI_APP.glob("trial_summary_publish/*.py"),
                    *NPI_DOCTYPES.glob("npi_trial_summary_delivery*/*.py"),
                ],
                list(NPI_DOCTYPES.glob("npi_trial_summary_delivery*/*.json")),
            ),
        ):
            sources: set[str] = set()
            for path in python_files:
                tree = ast.parse(path.read_text(encoding="utf-8"))
                sources.update(
                    str(node.args[0].value)
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "_"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                )
            for path in metadata_files:
                metadata = json.loads(path.read_text(encoding="utf-8"))
                sources.add(metadata["name"])
                for field in metadata["fields"]:
                    if field.get("label"):
                        sources.add(field["label"])
                    if field.get("fieldtype") == "Select":
                        sources.update(field.get("options", "").splitlines())
            translated: dict[str, set[str]] = {}
            for locale in ("zh", "zh-TW"):
                with (app_root / f"translations/{locale}.csv").open(
                    encoding="utf-8",
                    newline="",
                ) as handle:
                    rows = list(csv.reader(handle))
                keys = [row[0] for row in rows if row]
                self.assertEqual(len(keys), len(set(keys)))
                translated[locale] = set(keys)
                self.assertFalse(sources - translated[locale])
            self.assertEqual(sources - translated["zh"], sources - translated["zh-TW"])


if __name__ == "__main__":
    unittest.main()
