from __future__ import annotations

import ast
import copy
import csv
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
CORE_DOCTYPE = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
INTEGRATION_DOCTYPE = ROOT / "apps/npi_integration/npi_integration/npi_integration/doctype"
TRANSLATIONS = ROOT / "apps/npi_core/npi_core/translations"
ASSET_RECEIPT_CONTROLLER = (
    INTEGRATION_DOCTYPE
    / "npi_tool_asset_command_idempotency"
    / "npi_tool_asset_command_idempotency.py"
)


class Phase6ToolingAcceptanceMetadataTest(unittest.TestCase):
    OBJECTS = {
        "npi_tooling_acceptance_evidence_revision": CORE_DOCTYPE,
        "npi_tool_asset_request": INTEGRATION_DOCTYPE,
        "npi_tool_asset_command_idempotency": INTEGRATION_DOCTYPE,
    }

    @staticmethod
    def load(root: Path, folder: str) -> dict[str, object]:
        return json.loads((root / folder / f"{folder}.json").read_text(encoding="utf-8"))

    @staticmethod
    def fields(metadata: dict[str, object]) -> dict[str, dict[str, object]]:
        return {value["fieldname"]: value for value in metadata["fields"]}  # type: ignore[index]

    def test_three_additive_objects_are_guarded_and_install_no_rows(self) -> None:
        for folder, root in self.OBJECTS.items():
            with self.subTest(folder=folder):
                metadata = self.load(root, folder)
                self.assertEqual(metadata.get("allow_rename"), 0)
                self.assertEqual(metadata.get("read_only"), 1)
                self.assertNotIn("fixtures", metadata)
                self.assertNotIn("records", metadata)
                self.assertTrue(all(field.get("read_only") == 1 for field in self.fields(metadata).values()))
        request_fields = self.fields(self.load(INTEGRATION_DOCTYPE, "npi_tool_asset_request"))
        self.assertEqual(request_fields["target_mode"].get("options"), "mock")
        self.assertEqual(request_fields["request_state"].get("options"), "draft")
        self.assertEqual(request_fields["business_approval_state"].get("options"), "unavailable")
        self.assertEqual(request_fields["dispatch_state"].get("options"), "prohibited")
        self.assertEqual(request_fields["target_result_state"].get("options"), "not_requested")
        for forbidden in (
            "formal_asset_id", "asset_state", "location", "shot_count",
            "maintenance_due", "endpoint", "credential", "secret", "outbox",
        ):
            self.assertNotIn(forbidden, request_fields)

    def test_controllers_require_closed_writes_exact_dependencies_and_immutability(self) -> None:
        acceptance = (CORE_DOCTYPE / "npi_tooling_acceptance_evidence_revision" / "npi_tooling_acceptance_evidence_revision.py").read_text(encoding="utf-8")
        request = (INTEGRATION_DOCTYPE / "npi_tool_asset_request" / "npi_tool_asset_request.py").read_text(encoding="utf-8")
        receipt = (INTEGRATION_DOCTYPE / "npi_tool_asset_command_idempotency" / "npi_tool_asset_command_idempotency.py").read_text(encoding="utf-8")
        for marker in (
            "require_tooling_command_write()", "deny_tooling_history_update()",
            "deny_tooling_history_delete", '"NPI Tooling Master"', '"NPI Tooling Set"',
            '"NPI Tooling Set Revision Binding"', '"NPI Tooling Revision"',
            '"NPI File Revision"', '"scan_state": "clean"', '"is_private": 1',
            "validate_acceptance_successor",
        ):
            self.assertIn(marker, acceptance)
        for marker in (
            "require_tool_asset_request_write()", "deny_tool_asset_history_update()",
            "deny_tool_asset_history_delete", '"NPI Tooling Master"', '"NPI Tooling Set"',
            '"NPI Tooling Set Revision Binding"', '"NPI Tooling Revision"',
            '"NPI Tooling Acceptance Evidence Revision"',
        ):
            self.assertIn(marker, request)
        self.assertIn("TOOL_ASSET_OPERATION", receipt)
        self.assertIn("A sealed Tool Asset command receipt cannot be changed.", receipt)

    def test_receipts_add_only_exact_acceptance_and_asset_operation_pairs(self) -> None:
        core = self.fields(self.load(CORE_DOCTYPE, "npi_tooling_command_idempotency"))
        self.assertEqual(str(core["operation"].get("options", "")).splitlines()[-1], "tooling_acceptance_evidence.create")
        self.assertEqual(str(core["target_object_type"].get("options", "")).splitlines()[-1], "tooling_acceptance_evidence_revision")
        acceptance = self.load(
            CORE_DOCTYPE,
            "npi_tooling_acceptance_evidence_revision",
        )
        acceptance_fields = self.fields(acceptance)
        self.assertEqual(acceptance_fields["version_key_hash"].get("unique"), 1)
        source = (CORE_DOCTYPE / "npi_tooling_command_idempotency" / "npi_tooling_command_idempotency.py").read_text(encoding="utf-8")
        self.assertIn('"tooling_acceptance_evidence.create": "tooling_acceptance_evidence_revision"', source)
        asset = self.fields(self.load(INTEGRATION_DOCTYPE, "npi_tool_asset_command_idempotency"))
        self.assertEqual(asset["request_global_id"].get("options"), "NPI Tool Asset Request")

    def test_legacy_receipt_normalizes_frappe_int_storage_without_weakening_identity(self) -> None:
        class PinnedPermissionError(RuntimeError):
            pass

        class PinnedValidationError(RuntimeError):
            pass

        class StubDocument:
            def __init__(self) -> None:
                self.flags = SimpleNamespace(in_insert=False)
                self._before = None
                self._stored = None
                self.save_calls = 0

            def get_doc_before_save(self):
                return self._before

            def _storage_snapshot(self):
                snapshot = copy.copy(self)
                snapshot.schema_version = int(self.schema_version or 0)
                snapshot._before = None
                snapshot._stored = None
                return snapshot

            def insert(self):
                self.before_insert()
                self.flags.in_insert = True
                self.before_validate()
                self.validate()
                self.before_save()
                self.flags.in_insert = False
                self._stored = self._storage_snapshot()
                return self

            def save(self):
                self._before = copy.copy(self._stored)
                self.before_validate()
                self.validate()
                self.before_save()
                self._stored = self._storage_snapshot()
                self.save_calls += 1
                return self

        frappe = types.ModuleType("frappe")
        frappe.flags = SimpleNamespace(npi_tool_asset_request_write=False)
        frappe.PermissionError = PinnedPermissionError
        frappe.ValidationError = PinnedValidationError
        frappe._ = lambda value: value

        def throw(message, exception):
            raise exception(message)

        frappe.throw = throw
        frappe_model = types.ModuleType("frappe.model")
        frappe_document = types.ModuleType("frappe.model.document")
        frappe_document.Document = StubDocument

        core_validation = types.ModuleType("npi_core.documents.frappe_validation")
        core_validation.canonical_json = lambda value: json.dumps(
            value, sort_keys=True, separators=(",", ":")
        )
        core_validation.canonical_uuid = lambda value, _label: value
        core_validation.json_object = lambda value, _label: (
            value if isinstance(value, dict) else json.loads(value)
        )
        core_validation.lowercase_sha256 = lambda value, _label: value
        core_validation.optional_uuid = lambda value, _label: value
        core_validation.require_exact_parent = lambda *_args, **_kwargs: SimpleNamespace(
            payload_hash="a" * 64
        )
        core_validation.required_text = lambda value, _label, **_kwargs: value
        core_validation.tenant_text = lambda value: value
        core_validation.utc_datetime_text = lambda value, _label: str(value)

        tooling_domain = types.ModuleType("npi_core.tooling.domain")
        tooling_domain.sha256_json = lambda _value: "h" * 64
        legacy_domain = types.ModuleType("npi_integration.tool_asset_request.domain")
        legacy_domain.TOOL_ASSET_OPERATION = "create_or_update_tool_asset"
        legacy_validation = types.ModuleType(
            "npi_integration.tool_asset_request.frappe_validation"
        )

        def require_legacy_write() -> None:
            if not frappe.flags.npi_tool_asset_request_write:
                frappe.throw("closed", frappe.PermissionError)

        legacy_validation.require_tool_asset_request_write = require_legacy_write
        legacy_validation.deny_tool_asset_history_delete = lambda _document: None
        execution_domain = types.ModuleType(
            "npi_integration.tool_asset_request.execution_domain"
        )
        execution_domain.TOOL_ASSET_EXECUTION_SCHEMA_VERSION = 2
        execution_domain.TOOL_ASSET_EXECUTION_OPERATIONS = (
            "create_tool_asset",
            "update_tool_asset",
        )
        execution_validation = types.ModuleType(
            "npi_integration.tool_asset_request.execution_frappe_validation"
        )
        execution_validation.require_tool_asset_execution_idempotency_write = (
            lambda: None
        )
        execution_validation.deny_tool_asset_execution_history_delete = lambda: None
        modules = {
            "frappe": frappe,
            "frappe.model": frappe_model,
            "frappe.model.document": frappe_document,
            "npi_core.documents.frappe_validation": core_validation,
            "npi_core.tooling.domain": tooling_domain,
            "npi_integration.tool_asset_request.domain": legacy_domain,
            "npi_integration.tool_asset_request.frappe_validation": legacy_validation,
            "npi_integration.tool_asset_request.execution_domain": execution_domain,
            "npi_integration.tool_asset_request.execution_frappe_validation": execution_validation,
        }
        spec = importlib.util.spec_from_file_location(
            "npi_integration.p606_tool_asset_receipt_controller",
            ASSET_RECEIPT_CONTROLLER,
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        loaded = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(loaded)

        def receipt(*, schema_version=None, operation=None):
            document = loaded.NPIToolAssetCommandIdempotency()
            document.global_id = "10000000-0000-4000-8000-000000000001"
            document.schema_version = schema_version
            document.receipt_key = "receipt"
            document.tenant_id = "tenant"
            document.project_global_id = "20000000-0000-4000-8000-000000000002"
            document.actor_user_id = "actor@example.invalid"
            document.operation = operation or legacy_domain.TOOL_ASSET_OPERATION
            document.idempotency_key_hash = "b" * 64
            document.payload_hash = "a" * 64
            document.source_stream_key_hash = "c" * 64
            document.profile_snapshot_hash = "d" * 64
            document.mapping_expectation_hash = "e" * 64
            document.request_global_id = None
            document.response_payload = None
            document.response_hash = None
            document.sealed = 0
            document.created_at = "2026-08-24 00:00:00"
            document.updated_at = document.created_at
            return document

        outside = receipt()
        with self.assertRaises(PinnedPermissionError):
            outside.insert()

        frappe.flags.npi_tool_asset_request_write = True
        outside.insert()
        frappe.flags.npi_tool_asset_request_write = False
        with self.assertRaises(PinnedPermissionError):
            outside.save()

        frappe.flags.npi_tool_asset_request_write = True
        document = receipt().insert()
        stored = document._stored
        document.request_global_id = "30000000-0000-4000-8000-000000000003"
        document.response_payload = {
            "globalId": document.request_global_id,
            "payloadHash": document.payload_hash,
        }
        document.response_hash = "h" * 64
        document.sealed = 1
        document.save()
        self.assertIsNone(document.schema_version)
        self.assertEqual(stored.schema_version, 0)
        self.assertEqual(document.save_calls, 1)

        for before_schema, current_schema, operation in (
            (0, 2, "create_tool_asset"),
            (2, 0, legacy_domain.TOOL_ASSET_OPERATION),
        ):
            with self.subTest(
                before_schema=before_schema,
                current_schema=current_schema,
            ):
                tampered = receipt(
                    schema_version=current_schema,
                    operation=operation,
                )
                tampered._before = copy.copy(tampered)
                tampered._before.schema_version = before_schema
                with self.assertRaises(PinnedPermissionError):
                    tampered.validate()

    def test_all_new_visible_sources_have_direct_symmetric_translations(self) -> None:
        sources: set[str] = set()
        python_paths = [
            ROOT / "apps/npi_core/npi_core/tooling/acceptance_domain.py",
            ROOT / "apps/npi_integration/npi_integration/tool_asset_request/domain.py",
            ROOT / "apps/npi_integration/npi_integration/tool_asset_request/frappe_validation.py",
        ]
        for folder, root in self.OBJECTS.items():
            metadata = self.load(root, folder)
            sources.add(str(metadata["name"]))
            sources.update(str(field["label"]) for field in metadata["fields"])
            python_paths.append(root / folder / f"{folder}.py")
        for path in python_paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "_"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                ):
                    sources.add(node.args[0].value)
        catalogs: dict[str, dict[str, str]] = {}
        for language in ("zh", "zh-TW"):
            with (TRANSLATIONS / f"{language}.csv").open(encoding="utf-8", newline="") as handle:
                catalogs[language] = {
                    row[0]: row[1]
                    for row in csv.reader(handle)
                    if len(row) >= 2 and row[0]
                }
            self.assertFalse(
                sorted(source for source in sources if not catalogs[language].get(source)),
                f"missing {language} P6-06 translations",
            )
        self.assertEqual(set(catalogs["zh"]), set(catalogs["zh-TW"]))


if __name__ == "__main__":
    unittest.main()
