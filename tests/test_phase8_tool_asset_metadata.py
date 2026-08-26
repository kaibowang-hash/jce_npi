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
        for marker in ("ToolAssetSupportWriteCapability", "_CURRENT_CAPABILITY", "require_tool_asset_execution_capability", "_CURRENT_CAPABILITY.reset(token)", "tool_asset_request_transaction_write", "insert_tool_asset_support_document", "insert_tool_asset_audit_document"):
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

    def test_synthetic_outbox_terminal_is_an_exact_processing_transition(self) -> None:
        metadata = self.load("npi_outbox_message")
        fields = {field["fieldname"]: field for field in metadata["fields"]}
        self.assertEqual(
            fields["state"]["options"].splitlines(),
            [
                "pending",
                "processing",
                "synthetic_verified",
                "partially_succeeded",
                "succeeded",
                "failed_retryable",
                "failed_final",
                "uncertain",
                "mapping_conflict",
            ],
        )

        validation_error = type("PinnedValidationError", (Exception,), {})
        permission_error = type("PinnedPermissionError", (Exception,), {})
        frappe = types.ModuleType("frappe")
        frappe._ = lambda value: value
        frappe.ValidationError = validation_error
        frappe.PermissionError = permission_error

        def throw(message, error=None):
            raise (error or validation_error)(message)

        frappe.throw = throw
        frappe_model = types.ModuleType("frappe.model")
        frappe_document = types.ModuleType("frappe.model.document")
        frappe_document.Document = type("Document", (), {})

        core_validation = types.ModuleType("npi_core.documents.frappe_validation")
        core_validation.actor_text = lambda value, _label: value
        core_validation.assert_immutable_fields = lambda *_args: None
        core_validation.canonical_json = lambda value: json.dumps(
            value, sort_keys=True, separators=(",", ":")
        )
        core_validation.canonical_uuid = lambda value, _label: value
        core_validation.frappe_utc_datetime_text = lambda value, _label: value
        core_validation.json_object = lambda value, _label: (
            json.loads(value) if isinstance(value, str) else dict(value)
        )
        core_validation.lowercase_sha256 = lambda value, _label: value
        core_validation.nonnegative_integer = lambda value, _label: int(value)
        core_validation.positive_integer = lambda value, _label: int(value)
        core_validation.required_text = lambda value, _label, _maximum: value
        core_validation.tenant_text = lambda value: value
        core_validation.utc_datetime_text = lambda value, _label: value

        item_domain = types.ModuleType("npi_integration.item_publish.domain")
        item_domain.ITEM_PUBLISH_OPERATION = "item.publish"
        item_domain.ITEM_PUBLISH_SCHEMA_VERSION = 1
        item_domain.ITEM_REQUEST_EVENT_TYPE = "item.publish.requested"
        item_domain.canonical_hash = lambda _value: "h" * 64
        item_validation = types.ModuleType(
            "npi_integration.item_publish.frappe_validation"
        )
        for name in (
            "deny_item_history_delete",
            "deny_item_history_update",
            "deny_legacy_outbox_promotion",
            "require_item_outbox_write",
        ):
            setattr(item_validation, name, lambda: None)

        def transition(before, after, *, allowed, label):
            if after != before and after not in allowed.get(before, frozenset()):
                frappe.throw(label, validation_error)

        item_validation.validate_one_way_transition = transition
        mbom_domain = types.ModuleType("npi_integration.mbom_publish.domain")
        mbom_domain.MBOM_PUBLISH_OPERATION = "mbom.publish"
        mbom_domain.MBOM_PUBLISH_SCHEMA_VERSION = 2
        mbom_domain.MBOM_REQUEST_EVENT_TYPE = "mbom.publish.requested"
        mbom_validation = types.ModuleType(
            "npi_integration.mbom_publish.frappe_validation"
        )
        for name in (
            "deny_mbom_history_delete",
            "deny_mbom_history_update",
            "deny_outbox_operation_conversion",
            "require_mbom_outbox_write",
        ):
            setattr(mbom_validation, name, lambda: None)
        tool_domain = types.ModuleType(
            "npi_integration.tool_asset_request.execution_domain"
        )
        tool_domain.TOOL_ASSET_EXECUTION_API_VERSION = "npi.erp-tool-asset.v1"
        tool_domain.TOOL_ASSET_EXECUTION_OPERATIONS = frozenset(
            {"create_tool_asset", "update_tool_asset"}
        )
        tool_domain.TOOL_ASSET_OUTBOX_SCHEMA_VERSION = 3
        tool_domain.TOOL_ASSET_REQUEST_EVENT_TYPE = "npi.tool_asset_request.ready"
        tool_validation = types.ModuleType(
            "npi_integration.tool_asset_request.execution_frappe_validation"
        )
        for name in (
            "deny_tool_asset_execution_history_delete",
            "deny_tool_asset_execution_history_update",
            "deny_tool_asset_outbox_conversion",
            "require_tool_asset_execution_outbox_write",
        ):
            setattr(tool_validation, name, lambda: None)
        modules = {
            "frappe": frappe,
            "frappe.model": frappe_model,
            "frappe.model.document": frappe_document,
            "npi_core.documents.frappe_validation": core_validation,
            "npi_integration.item_publish.domain": item_domain,
            "npi_integration.item_publish.frappe_validation": item_validation,
            "npi_integration.mbom_publish.domain": mbom_domain,
            "npi_integration.mbom_publish.frappe_validation": mbom_validation,
            "npi_integration.tool_asset_request.execution_domain": tool_domain,
            "npi_integration.tool_asset_request.execution_frappe_validation": tool_validation,
        }
        path = DOCTYPE_ROOT / "npi_outbox_message/npi_outbox_message.py"
        spec = importlib.util.spec_from_file_location(
            "p805_synthetic_terminal_outbox_contract", path
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        controller = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(controller)

        previous = types.SimpleNamespace(
            schema_version=3,
            event_type="npi.tool_asset_request.ready",
            state="processing",
            attempt_count=1,
            adapter_boundary_crossed=1,
        )

        def terminal(state="synthetic_verified", *, result="result"):
            value = controller.NPIOutboxMessage()
            values = {
                "schema_version": 3,
                "event_type": "npi.tool_asset_request.ready",
                "operation": "create_tool_asset",
                "object_version": 1,
                "event_id": "event",
                "global_id": "global",
                "tenant_id": "tenant",
                "project_global_id": "project",
                "tool_asset_request_global_id": "request",
                "tooling_set_global_id": "set",
                "request_id": "command",
                "trace_id": "trace-p805-terminal",
                "profile_id": "profile",
                "profile_version": 1,
                "actor_user_id": "requester@example.invalid",
                "service_actor_user_id": "worker@example.invalid",
                "profile_snapshot_hash": "h" * 64,
                "source_stream_key_hash": "h" * 64,
                "source_hash": "h" * 64,
                "tool_asset_mapping_expectation_hash": "h" * 64,
                "idempotency_key_hash": "h" * 64,
                "target_idempotency_key_hash": "h" * 64,
                "semantic_effect_hash": "h" * 64,
                "payload_hash": "h" * 64,
                "event_snapshot_hash": "h" * 64,
                "payload": {},
                "attempt_count": 1,
                "claim_token": "claim",
                "claimed_at": "2026-08-26 01:00:00",
                "lease_expires_at": "2026-08-26 01:05:00",
                "adapter_boundary_crossed": 1,
                "state": state,
                "tool_asset_result_global_id": result,
            }
            for fieldname, field_value in values.items():
                setattr(value, fieldname, field_value)
            return value

        terminal()._validate_tool_asset_v3(previous)
        with self.assertRaises(validation_error):
            terminal("validated_mock")._validate_tool_asset_v3(previous)
        with self.assertRaises(validation_error):
            terminal(result=None)._validate_tool_asset_v3(previous)
        pending = types.SimpleNamespace(**vars(previous))
        pending.state = "pending"
        with self.assertRaises(validation_error):
            terminal()._validate_tool_asset_v3(pending)

    def test_all_visible_sources_have_direct_zh_and_zh_tw_translations(self) -> None:
        sources: set[str] = set()
        paths = [
            TOOL_ASSET_ROOT / "execution_frappe_validation.py",
            TOOL_ASSET_ROOT / "doctype_base.py",
            TOOL_ASSET_ROOT / "problems.py",
            ROOT / "apps/npi_integration/npi_integration/tool_asset_request_api.py",
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
