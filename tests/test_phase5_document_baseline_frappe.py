from __future__ import annotations

import importlib
import sys
import types
import unittest
from datetime import UTC, datetime
from uuid import UUID


sys.path.insert(0, "apps/npi_core")


class DocumentBaselineFrappeAdapterTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_core.documents.release_frappe",
        "npi_core.documents.baseline_frappe",
    )

    def setUp(self) -> None:
        self.saved_modules = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)

        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.ValidationError = type("ValidationError", (Exception,), {})
        frappe.PermissionError = type("PermissionError", (Exception,), {})
        frappe.flags = types.SimpleNamespace()

        def throw(message: str, exception: type[Exception]) -> None:
            raise exception(message)

        frappe.throw = throw
        sys.modules["frappe"] = frappe
        self.module = importlib.import_module(
            "npi_core.documents.baseline_frappe"
        )

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
        for name, module in self.saved_modules.items():
            if module is not None:
                sys.modules[name] = module

    def test_dependency_rebuild_treats_frappe_datetime_as_utc(self) -> None:
        ids = [UUID(int=value) for value in range(1, 8)]
        dependency = self.module.baseline_dependency_value(
            {
                "global_id": str(ids[0]),
                "tenant_id": "site-test",
                "project_global_id": str(ids[1]),
                "baseline_global_id": str(ids[2]),
                "baseline_snapshot_hash": "a" * 64,
                "input_document_global_id": str(ids[3]),
                "input_revision_global_id": str(ids[4]),
                "input_revision_snapshot_hash": "b" * 64,
                "gate_global_id": str(ids[5]),
                "requirement_global_id": str(ids[6]),
                "requirement_key": "drawing",
                "evidence_reference_global_id": str(UUID(int=8)),
                "registered_by_user_id": "Administrator",
                "registered_at": "2026-08-05 09:10:11.123456",
                "request_id": "request-p503",
                "trace_id": "trace-00000000000000000000000000000000",
            }
        )

        self.assertEqual(
            dependency.registered_at,
            datetime(2026, 8, 5, 9, 10, 11, 123456, tzinfo=UTC),
        )
        self.assertRegex(dependency.snapshot_hash, r"^[a-f0-9]{64}$")


if __name__ == "__main__":
    unittest.main()
