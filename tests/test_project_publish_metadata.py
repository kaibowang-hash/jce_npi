from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NPI = ROOT / "apps/npi_integration/npi_integration"
ERP = ROOT / "apps/npi_erpnext_connector/npi_erpnext_connector"


class ProjectPublishMetadataTest(unittest.TestCase):
    def test_support_records_are_read_only_non_exportable_and_immutable(self) -> None:
        directories = (
            NPI / "npi_integration/doctype/npi_erp_project_publish_request",
            NPI / "npi_integration/doctype/npi_erp_project_publish_attempt",
            NPI / "npi_integration/doctype/npi_erp_project_publish_result",
            ERP / "npi_erpnext_connector/doctype/npi_erp_project_publish_mapping",
            ERP / "npi_erpnext_connector/doctype/npi_erp_project_publish_receipt",
        )
        for directory in directories:
            metadata = json.loads(
                (directory / f"{directory.name}.json").read_text(encoding="utf-8")
            )
            self.assertEqual(metadata["read_only"], 1)
            self.assertTrue(
                all(field.get("read_only") == 1 for field in metadata["fields"])
            )
            permission = metadata["permissions"][0]
            self.assertEqual(permission["role"], "System Manager")
            for operation in ("write", "create", "delete", "export", "print", "email", "share"):
                self.assertEqual(permission[operation], 0)

    def test_project_hook_is_transactional_and_recovery_is_scheduled(self) -> None:
        hooks = ast.parse((NPI / "hooks.py").read_text(encoding="utf-8"))
        doc_events = ast.literal_eval(
            next(
                node.value
                for node in hooks.body
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "doc_events" for target in node.targets)
            )
        )
        self.assertEqual(
            doc_events["NPI Engineering Project"]["after_insert"],
            "npi_integration.project_publish.service.queue_engineering_project",
        )
        source = (NPI / "project_publish/service.py").read_text(encoding="utf-8")
        self.assertIn("enqueue_after_commit=after_commit", source)
        self.assertIn("npi_project_source_binding_write", source)
        self.assertIn("recover_project_publish_requests", (NPI / "hooks.py").read_text())
        self.assertIn(
            'SECRETS_ENV = "NPI_ITEM_PUBLISH_SANDBOX_SECRETS"',
            (NPI / "project_publish/config.py").read_text(encoding="utf-8"),
        )
        worker = (NPI / "project_publish/worker.py").read_text(encoding="utf-8")
        self.assertLess(
            worker.index("source = restore_source"),
            worker.index("insert_support_document(attempt"),
        )
        self.assertIn("PROJECT_PUBLISH_ATTEMPT_LIMIT_REACHED", worker)
        self.assertIn('request_state in {"failed_retryable", "uncertain"}', worker)

    def test_receiver_is_operation_specific_v15_v16_and_loop_suppressed(self) -> None:
        api = (ERP / "project_publish_api.py").read_text(encoding="utf-8")
        repository = (ERP / "project_repository.py").read_text(encoding="utf-8")
        self.assertIn("supportedFrappeMajors", api)
        self.assertIn("[15, 16]", api)
        self.assertIn("NPI ERP Project Publish Mapping", repository)
        for forbidden in ("frappe.db." + "sql", "verify=False", "http://", "frappe.client." + "insert"):
            self.assertNotIn(forbidden, api + repository)


if __name__ == "__main__":
    unittest.main()
