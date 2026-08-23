from __future__ import annotations

import ast
import csv
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_integration/npi_integration/npi_integration/doctype"
CORE_DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
TOOL_ASSET_ROOT = ROOT / "apps/npi_integration/npi_integration/tool_asset_request"
TRANSLATIONS = ROOT / "apps/npi_core/npi_core/translations"


class Phase8ToolAssetMetadataTest(unittest.TestCase):
    FOLDERS = (
        "npi_tool_asset_stream_guard",
        "npi_tool_asset_attempt",
        "npi_tool_asset_result",
        "npi_tool_asset_field_result",
        "npi_tool_asset_mapping_observation",
        "npi_tool_asset_mapping_head",
    )

    @staticmethod
    def load(folder: str) -> dict[str, object]:
        return json.loads((DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8"))

    def test_six_additive_support_doctypes_are_read_only_and_install_no_rows(self) -> None:
        for folder in self.FOLDERS:
            with self.subTest(folder=folder):
                metadata = self.load(folder)
                fields = {field["fieldname"]: field for field in metadata["fields"]}
                identity = "source_stream_key_hash" if folder == "npi_tool_asset_stream_guard" else "global_id"
                self.assertEqual(metadata["autoname"], f"field:{identity}")
                self.assertEqual(metadata["allow_rename"], 0)
                self.assertEqual(metadata["track_changes"], 0)
                self.assertEqual(metadata["read_only"], 1)
                self.assertNotIn("fixtures", metadata)
                self.assertNotIn("records", metadata)
                self.assertTrue(all(field.get("read_only") == 1 for field in fields.values()))
                for permission in metadata["permissions"]:
                    for action in ("write", "create", "delete", "export", "print", "email"):
                        self.assertFalse(permission.get(action, 0))

    def test_metadata_links_resolve_only_repository_doctypes(self) -> None:
        names = {str(json.loads(path.read_text(encoding="utf-8"))["name"]) for root in (DOCTYPE_ROOT, CORE_DOCTYPE_ROOT) for path in root.glob("*/*.json")}
        for folder in (*self.FOLDERS, "npi_tool_asset_request", "npi_tool_asset_command_idempotency", "npi_outbox_message"):
            for field in self.load(folder)["fields"]:
                if field.get("fieldtype") == "Link":
                    self.assertIn(field.get("options"), names)

    def test_support_controllers_require_exact_capability_and_preserve_insert_lifecycle(self) -> None:
        validation = (TOOL_ASSET_ROOT / "execution_frappe_validation.py").read_text(encoding="utf-8")
        for marker in ("ToolAssetSupportWriteCapability", "_CURRENT_CAPABILITY", "require_tool_asset_execution_capability", "_CURRENT_CAPABILITY.reset(token)", "checkpoint 1 has no caller or write route"):
            self.assertIn(marker, validation)
        base = (TOOL_ASSET_ROOT / "doctype_base.py").read_text(encoding="utf-8")
        for marker in ('self._require_write("insert")', '"in_insert"', 'self._require_write(action)', "assert_immutable_fields", "deny_tool_asset_execution_history_delete"):
            self.assertIn(marker, base)
        ast.parse(base)
        for folder in self.FOLDERS:
            controller = (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(encoding="utf-8")
            self.assertIn("ToolAssetSupportDocument", controller)
            self.assertIn("write_guard = staticmethod(require_tool_asset_execution_", controller)
            ast.parse(controller)

    def test_support_base_executes_insert_capability_through_frappe_before_save(self) -> None:
        core_validation = types.ModuleType("npi_core.documents.frappe_validation")
        for name in (
            "actor_text", "canonical_uuid", "lowercase_sha256",
            "nonnegative_integer", "positive_integer", "required_text",
            "tenant_text",
        ):
            setattr(core_validation, name, lambda value, *_args: value)
        core_validation.assert_immutable_fields = lambda *_args: None
        frappe_model = types.ModuleType("frappe.model")
        frappe_document = types.ModuleType("frappe.model.document")
        frappe_document.Document = object
        validation = types.ModuleType(
            "npi_integration.tool_asset_request.execution_frappe_validation"
        )
        calls: list[tuple[str, str] | str] = []
        validation.deny_tool_asset_execution_history_delete = lambda: calls.append("delete")
        validation.deny_tool_asset_execution_history_update = lambda: calls.append("update")
        validation.require_tool_asset_execution_capability = (
            lambda doctype, action: calls.append((doctype, action))
        )
        modules = {
            "frappe.model": frappe_model,
            "frappe.model.document": frappe_document,
            "npi_core.documents.frappe_validation": core_validation,
            "npi_integration.tool_asset_request.execution_frappe_validation": validation,
        }
        path = TOOL_ASSET_ROOT / "doctype_base.py"
        spec = importlib.util.spec_from_file_location(
            "npi_integration.tool_asset_request.p805_tool_asset_doctype_base",
            path,
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        loaded = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(loaded)

        document = loaded.ToolAssetSupportDocument()
        document.doctype = "NPI Tool Asset Attempt"
        document.flags = types.SimpleNamespace(in_insert=True)
        document.write_guard = lambda: calls.append("guard")
        document.get_doc_before_save = lambda: None
        document.before_insert()
        document.before_save()
        self.assertEqual(
            calls,
            ["guard", (document.doctype, "insert"), "guard", (document.doctype, "insert")],
        )

        calls.clear()
        document.flags.in_insert = False
        document.before_save()
        self.assertEqual(calls, ["guard", (document.doctype, "save")])

    def test_v1_request_is_retained_while_v2_metadata_is_isolated(self) -> None:
        request = self.load("npi_tool_asset_request")
        fields = {field["fieldname"]: field for field in request["fields"]}
        self.assertEqual(fields["target_mode"]["options"], "mock")
        self.assertEqual(fields["request_state"]["options"], "draft")
        self.assertEqual(fields["business_approval_state"]["options"], "unavailable")
        for fieldname in ("schema_version", "source_stream_key_hash", "source_snapshot", "source_hash", "approval_snapshot", "approval_hash", "mapping_expectation_snapshot", "mapping_expectation_hash", "profile_snapshot_hash", "execution_target_mode", "execution_state", "dispatch_allowed"):
            self.assertIn(fieldname, fields)
            self.assertEqual(fields[fieldname].get("read_only"), 1)
        source = (DOCTYPE_ROOT / "npi_tool_asset_request/npi_tool_asset_request.py").read_text(encoding="utf-8")
        for marker in ("tool_asset_request_from_snapshot", "tool_asset_execution_request_from_mapping", "_validate_execution_v2", "TOOL_ASSET_EXECUTION_OPERATIONS", "require_tool_asset_execution_request_write", "Mock Tool Asset execution must remain undispatched"):
            self.assertIn(marker, source)

    def test_attempt_seals_only_mutable_outcome_while_inputs_remain_immutable(self) -> None:
        source = (
            DOCTYPE_ROOT
            / "npi_tool_asset_attempt/npi_tool_asset_attempt.py"
        ).read_text(encoding="utf-8")
        self.assertIn("append_only = False", source)
        self.assertIn('"claim_token")', source)
        for fieldname in (
            "operation", "profile_id", "profile_version", "request_snapshot",
            "request_snapshot_hash", "started_at",
        ):
            self.assertIn(f'"{fieldname}"', source)

    def test_outbox_schema_three_is_additive_and_cannot_convert_existing_branches(self) -> None:
        fields = {field["fieldname"]: field for field in self.load("npi_outbox_message")["fields"]}
        for fieldname in ("tool_asset_request_global_id", "tooling_set_global_id", "tool_asset_mapping_expectation_hash", "tool_asset_last_attempt_global_id", "tool_asset_result_global_id"):
            self.assertIn(fieldname, fields)
            self.assertEqual(fields[fieldname].get("read_only"), 1)
            self.assertNotEqual(fields[fieldname].get("reqd"), 1)
        source = (DOCTYPE_ROOT / "npi_outbox_message/npi_outbox_message.py").read_text(encoding="utf-8")
        for marker in ("TOOL_ASSET_OUTBOX_SCHEMA_VERSION", "TOOL_ASSET_REQUEST_EVENT_TYPE", "_validate_tool_asset_v3", "deny_tool_asset_outbox_conversion", "_validate_mbom_v2", "_is_item_v1", "Tool Asset Outbox claim fields must be present together.", "A processing Tool Asset Outbox message requires an exact claim.", "Tool Asset Outbox terminal state and result reference must agree.", "An uncertain Tool Asset Outbox message requires a crossed adapter boundary."):
            self.assertIn(marker, source)
        ast.parse(source)

    def test_all_visible_sources_have_direct_zh_and_zh_tw_translations(self) -> None:
        sources: set[str] = set()
        paths = [
            TOOL_ASSET_ROOT / "execution_frappe_validation.py",
            TOOL_ASSET_ROOT / "doctype_base.py",
            DOCTYPE_ROOT / "npi_tool_asset_request/npi_tool_asset_request.py",
            DOCTYPE_ROOT / "npi_tool_asset_command_idempotency/npi_tool_asset_command_idempotency.py",
            DOCTYPE_ROOT / "npi_outbox_message/npi_outbox_message.py",
        ]
        for folder in (*self.FOLDERS, "npi_tool_asset_request", "npi_tool_asset_command_idempotency", "npi_outbox_message"):
            metadata = self.load(folder)
            sources.add(str(metadata["name"]))
            sources.update(str(field["label"]) for field in metadata["fields"])
            paths.append(DOCTYPE_ROOT / folder / f"{folder}.py")
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_" and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    sources.add(node.args[0].value)
        catalogs: dict[str, dict[str, str]] = {}
        for language in ("zh", "zh-TW"):
            with (TRANSLATIONS / f"{language}.csv").open(encoding="utf-8", newline="") as stream:
                catalogs[language] = {row[0]: row[1] for row in csv.reader(stream) if len(row) >= 2 and row[0]}
            self.assertFalse(sorted(source for source in sources if not catalogs[language].get(source)), f"missing {language} P8-05 translations")
        self.assertEqual(set(catalogs["zh"]), set(catalogs["zh-TW"]))


if __name__ == "__main__":
    unittest.main()
