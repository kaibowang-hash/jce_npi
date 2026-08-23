from __future__ import annotations

import ast
import csv
import importlib.util
import json
import re
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_integration/npi_integration/npi_integration/doctype"
CORE_DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
MBOM_ROOT = ROOT / "apps/npi_integration/npi_integration/mbom_publish"
TRANSLATIONS = ROOT / "apps/npi_core/npi_core/translations"


class Phase8MbomPublishMetadataTest(unittest.TestCase):
    FOLDERS = (
        "npi_mbom_publish_request",
        "npi_mbom_publish_node",
        "npi_mbom_publish_command_idempotency",
        "npi_mbom_publish_stream_guard",
        "npi_mbom_publish_attempt",
        "npi_mbom_publish_result",
        "npi_mbom_publish_node_result",
        "npi_mbom_mapping_observation",
        "npi_mbom_mapping_head",
    )

    def load(self, folder: str) -> dict[str, object]:
        return json.loads(
            (DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8")
        )

    def test_nine_additive_support_doctypes_are_read_only_without_business_crud(self) -> None:
        for folder in self.FOLDERS:
            with self.subTest(folder=folder):
                metadata = self.load(folder)
                fields = {field["fieldname"]: field for field in metadata["fields"]}
                identity = {
                    "npi_mbom_publish_command_idempotency": "scope_key_hash",
                    "npi_mbom_publish_stream_guard": "source_stream_key_hash",
                }.get(folder, "global_id")
                self.assertEqual(metadata["autoname"], f"field:{identity}")
                self.assertEqual(metadata["allow_rename"], 0)
                self.assertEqual(metadata["track_changes"], 0)
                self.assertEqual(metadata["read_only"], 1)
                self.assertTrue(fields)
                self.assertTrue(
                    all(field.get("read_only") == 1 for field in fields.values())
                )
                self.assertNotIn("fixtures", metadata)
                self.assertNotIn("records", metadata)
                for permission in metadata["permissions"]:
                    for operation in (
                        "write",
                        "create",
                        "delete",
                        "export",
                        "print",
                        "email",
                    ):
                        self.assertFalse(permission.get(operation, 0))

    def test_metadata_links_target_repository_doctypes(self) -> None:
        names = {
            str(json.loads(path.read_text(encoding="utf-8"))["name"])
            for root in (DOCTYPE_ROOT, CORE_DOCTYPE_ROOT)
            for path in root.glob("*/*.json")
        }
        for folder in (*self.FOLDERS, "npi_outbox_message"):
            for field in self.load(folder)["fields"]:
                if field.get("fieldtype") == "Link":
                    self.assertIn(field.get("options"), names)

    def test_controllers_use_capability_scoped_internal_guards(self) -> None:
        guards = (MBOM_ROOT / "frappe_validation.py").read_text(encoding="utf-8")
        for marker in (
            'MBOM_OUTBOX_WRITE_FLAG = "npi_mbom_outbox_write"',
            'MBOM_REQUEST_WRITE_FLAG = "npi_mbom_publish_request_write"',
            'MBOM_NODE_WRITE_FLAG = "npi_mbom_publish_node_write"',
            'MBOM_IDEMPOTENCY_WRITE_FLAG = "npi_mbom_publish_idempotency_write"',
            'MBOM_STREAM_GUARD_WRITE_FLAG = "npi_mbom_publish_stream_guard_write"',
            'MBOM_ATTEMPT_WRITE_FLAG = "npi_mbom_publish_attempt_write"',
            'MBOM_RESULT_WRITE_FLAG = "npi_mbom_publish_result_write"',
            'MBOM_MAPPING_WRITE_FLAG = "npi_mbom_mapping_write"',
            "mbom_request_transaction_write(",
            "mbom_claim_write(",
            "mbom_result_transaction_write(",
            "require_mbom_capability(",
            "_CURRENT_CAPABILITY.reset(token)",
        ):
            self.assertIn(marker, guards)

        base = (MBOM_ROOT / "doctype_base.py").read_text(encoding="utf-8")
        for marker in (
            'self._require_write("insert")',
            '"insert"',
            '"save"',
            '"in_insert"',
            "self._require_write(action)",
            "deny_mbom_history_update()",
            "deny_mbom_history_delete()",
            "require_mbom_capability(self.doctype, action)",
            "assert_immutable_fields(",
        ):
            self.assertIn(marker, base)
        ast.parse(base)

        for folder in self.FOLDERS:
            source = (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(
                encoding="utf-8"
            )
            self.assertIn("MbomSupportDocument", source)
            self.assertIn("write_guard = staticmethod(require_mbom_", source)
            ast.parse(source)

    def test_schema_two_outbox_is_additive_and_cannot_convert_item_history(self) -> None:
        metadata = self.load("npi_outbox_message")
        fields = {field["fieldname"]: field for field in metadata["fields"]}
        for fieldname in (
            "mbom_request_global_id",
            "mbom_topology_hash",
            "item_mapping_set_hash",
            "mbom_mapping_set_hash",
            "mbom_node_manifest_hash",
            "mbom_last_attempt_global_id",
            "mbom_result_global_id",
        ):
            self.assertIn(fieldname, fields)
            self.assertNotEqual(fields[fieldname].get("reqd"), 1)
            self.assertEqual(fields[fieldname].get("read_only"), 1)
        states = set(str(fields["state"]["options"]).splitlines())
        self.assertTrue(
            {"partially_succeeded", "mapping_conflict", "uncertain"}.issubset(states)
        )

        controller = (
            DOCTYPE_ROOT / "npi_outbox_message/npi_outbox_message.py"
        ).read_text(encoding="utf-8")
        for marker in (
            "MBOM_PUBLISH_SCHEMA_VERSION",
            "MBOM_REQUEST_EVENT_TYPE",
            "MBOM_PUBLISH_OPERATION",
            "require_mbom_outbox_write()",
            "deny_outbox_operation_conversion()",
            "_validate_mbom_v2(",
            "if not self._is_item_v1():",
            "deny_legacy_outbox_promotion()",
            "deny_item_history_update()",
            "ITEM_REQUEST_EVENT_TYPE",
            "ITEM_PUBLISH_OPERATION",
        ):
            self.assertIn(marker, controller)
        ast.parse(controller)

    def test_request_persists_complete_profile_reference_for_fail_closed_rebuild(self) -> None:
        metadata = self.load("npi_mbom_publish_request")
        fields = {field["fieldname"]: field for field in metadata["fields"]}
        required = (
            "target_mode",
            "environment_code",
            "projection_policy_id",
            "projection_policy_version",
        )
        for fieldname in required:
            self.assertTrue(fields[fieldname]["reqd"])
            self.assertTrue(fields[fieldname]["read_only"])
        source = (
            DOCTYPE_ROOT
            / "npi_mbom_publish_request"
            / "npi_mbom_publish_request.py"
        ).read_text(encoding="utf-8")
        for fieldname in required:
            self.assertIn(f'"{fieldname}"', source)

    def test_outbox_event_hash_validation_stays_inside_its_schema_branch(self) -> None:
        path = DOCTYPE_ROOT / "npi_outbox_message/npi_outbox_message.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        methods = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        }

        def strings(method: str) -> list[str]:
            return [
                node.value
                for node in ast.walk(methods[method])
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
            ]

        self.assertEqual(
            strings("_validate_mbom_v2").count("MBOM Outbox Event Snapshot Hash"),
            1,
        )
        self.assertNotIn("Item Outbox Event Snapshot Hash", strings("_validate_mbom_v2"))
        self.assertEqual(strings("validate").count("Item Outbox Event Snapshot Hash"), 1)
        self.assertNotIn("MBOM Outbox Event Snapshot Hash", strings("validate"))

    def test_mbom_terminal_outbox_requires_and_accepts_complete_claim_history(self) -> None:
        validation_error = type("PinnedValidationError", (Exception,), {})
        permission_error = type("PinnedPermissionError", (Exception,), {})
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.ValidationError = validation_error
        frappe.PermissionError = permission_error

        def throw(message, error_type):
            raise error_type(message)

        frappe.throw = throw
        frappe_model = types.ModuleType("frappe.model")
        frappe_document = types.ModuleType("frappe.model.document")
        frappe_document.Document = object
        core_validation = types.ModuleType("npi_core.documents.frappe_validation")
        core_validation.actor_text = lambda value, _label: value
        core_validation.assert_immutable_fields = lambda *_args: None
        core_validation.canonical_json = lambda value: json.dumps(
            value, separators=(",", ":"), sort_keys=True
        )
        core_validation.canonical_uuid = lambda value, _label: value
        core_validation.frappe_utc_datetime_text = lambda value, _label: value
        core_validation.json_object = lambda value, _label: value
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
        item_validation.deny_item_history_delete = lambda: None
        item_validation.deny_item_history_update = lambda: None
        item_validation.deny_legacy_outbox_promotion = lambda: None
        item_validation.require_item_outbox_write = lambda: None

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
        mbom_validation.deny_mbom_history_delete = lambda: None
        mbom_validation.deny_mbom_history_update = lambda: None
        mbom_validation.deny_outbox_operation_conversion = lambda: None
        mbom_validation.require_mbom_outbox_write = lambda: None
        modules = {
            "frappe": frappe,
            "frappe.model": frappe_model,
            "frappe.model.document": frappe_document,
            "npi_core.documents.frappe_validation": core_validation,
            "npi_integration.item_publish.domain": item_domain,
            "npi_integration.item_publish.frappe_validation": item_validation,
            "npi_integration.mbom_publish.domain": mbom_domain,
            "npi_integration.mbom_publish.frappe_validation": mbom_validation,
        }
        path = DOCTYPE_ROOT / "npi_outbox_message/npi_outbox_message.py"
        spec = importlib.util.spec_from_file_location(
            "p804_terminal_outbox_contract", path
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        controller = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(controller)

        previous = types.SimpleNamespace(
            schema_version=2,
            event_type="mbom.publish.requested",
            state="processing",
            attempt_count=1,
            adapter_boundary_crossed=1,
        )
        terminal_states = (
            "partially_succeeded",
            "succeeded",
            "failed_retryable",
            "failed_final",
            "uncertain",
            "mapping_conflict",
        )

        def terminal(state):
            value = controller.NPIOutboxMessage()
            for fieldname, field_value in {
                "schema_version": 2,
                "event_type": "mbom.publish.requested",
                "operation": "mbom.publish",
                "object_version": 1,
                "event_id": "event",
                "global_id": "global",
                "tenant_id": "tenant",
                "project_global_id": "project",
                "mbom_request_global_id": "request",
                "request_id": "request-command",
                "trace_id": "trace-p804-terminal",
                "profile_id": "profile",
                "profile_version": 1,
                "actor_user_id": "publisher@example.invalid",
                "service_actor_user_id": "worker@example.invalid",
                "profile_snapshot_hash": "h" * 64,
                "source_stream_key_hash": "h" * 64,
                "source_hash": "h" * 64,
                "mbom_topology_hash": "h" * 64,
                "item_mapping_set_hash": "h" * 64,
                "mbom_mapping_set_hash": "h" * 64,
                "mbom_node_manifest_hash": "h" * 64,
                "idempotency_key_hash": "h" * 64,
                "target_idempotency_key_hash": "h" * 64,
                "semantic_effect_hash": "h" * 64,
                "payload_hash": "h" * 64,
                "event_snapshot_hash": "h" * 64,
                "payload": {},
                "attempt_count": 1,
                "claim_token": "claim",
                "claimed_at": "2026-08-21 17:00:00",
                "lease_expires_at": "2026-08-21 17:05:00",
                "adapter_boundary_crossed": 1,
                "state": state,
                "mbom_result_global_id": "result",
            }.items():
                setattr(value, fieldname, field_value)
            return value

        for state in terminal_states:
            with self.subTest(state=state):
                terminal(state)._validate_mbom_v2(previous)
        for missing in ("claim_token", "claimed_at", "lease_expires_at"):
            with self.subTest(partial_claim_missing=missing), self.assertRaises(
                validation_error
            ):
                value = terminal("succeeded")
                setattr(value, missing, None)
                value._validate_mbom_v2(previous)

    def test_checkpoint_three_adds_only_closed_worker_and_network_free_fixture(self) -> None:
        files = {path.name for path in MBOM_ROOT.glob("*.py")}
        self.assertEqual(
            files,
            {
                "__init__.py",
                "config.py",
                "diagnostics.py",
                "domain.py",
                "doctype_base.py",
                "frappe_repository.py",
                "frappe_validation.py",
                "problems.py",
                "adapters.py",
                "worker.py",
                "worker_repository.py",
                "runtime_fixture.py",
            },
        )
        combined = "\n".join(
            path.read_text(encoding="utf-8") for path in MBOM_ROOT.glob("*.py")
        ).casefold()
        for forbidden in (
            "requests" + ".",
            "httpx" + ".",
            "urllib." + "request",
            "socket" + ".",
            "frappe.db" + ".sql",
            "adapter.call",
        ):
            self.assertNotIn(forbidden, combined)
        diagnostics = (MBOM_ROOT / "diagnostics.py").read_text(encoding="utf-8")
        worker_repository = (MBOM_ROOT / "worker_repository.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("MBOM_PROCESS_VALIDATION_DIAGNOSTIC_CODES", diagnostics)
        self.assertIn("mbom_process_validation_step", worker_repository)
        self.assertNotIn("requests" + ".", diagnostics.casefold())
        self.assertNotIn("httpx" + ".", diagnostics.casefold())
        api = ROOT / "apps/npi_integration/npi_integration/mbom_publish_api.py"
        self.assertTrue(api.is_file())
        api_source = api.read_text(encoding="utf-8")
        self.assertIn("enqueue_after_commit=False", api_source)
        self.assertNotIn("requests" + ".", api_source)
        hooks = (ROOT / "apps/npi_integration/npi_integration/hooks.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("recover_mbom_publish_outbox_messages", hooks)
        self.assertIn("npi_mbom_publish_adapter_registry", hooks)
        self.assertIn("npi_mbom_publish_profile_resolver", hooks)
        openapi = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")
        self.assertIn("/projects/{projectId}/mbom-publish-requests:", openapi)
        self.assertIn(
            "/projects/{projectId}/mbom-publish-requests/{mbomPublishRequestId}:",
            openapi,
        )
        router = (ROOT / "apps/npi_core/npi_core/bff.py").read_text(encoding="utf-8")
        for marker in (
            "_PROJECT_MBOM_PUBLISH_REQUESTS_ROUTE",
            "_PROJECT_MBOM_PUBLISH_REQUEST_ROUTE",
            "npi_integration.mbom_publish_api.get_mbom_publish_requests",
            "npi_integration.mbom_publish_api.create_mbom_publish_request",
            "npi_integration.mbom_publish_api.get_mbom_publish_request",
        ):
            self.assertIn(marker, router)

    def test_visible_sources_have_symmetric_direct_chinese_translations(self) -> None:
        sources: set[str] = set()
        source_paths = [
            MBOM_ROOT / "frappe_validation.py",
            MBOM_ROOT / "problems.py",
            ROOT / "apps/npi_integration/npi_integration/mbom_publish_api.py",
        ]
        for folder in (*self.FOLDERS, "npi_outbox_message"):
            metadata = self.load(folder)
            if folder != "npi_outbox_message":
                sources.add(str(metadata["name"]))
            for field in metadata["fields"]:
                if folder != "npi_outbox_message" or str(field["fieldname"]).startswith(
                    "mbom_"
                ) or field["fieldname"] in {
                    "topology_hash",
                    "item_mapping_set_hash",
                    "node_manifest_hash",
                }:
                    sources.add(str(field["label"]))
                    if field.get("fieldtype") == "Select":
                        sources.update(
                            value
                            for value in str(field.get("options", "")).splitlines()
                            if value
                        )
            if folder != "npi_outbox_message":
                source_paths.append(DOCTYPE_ROOT / folder / f"{folder}.py")
        for path in source_paths:
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

        catalogs: dict[str, dict[str, str]] = {}
        placeholder = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")
        for language in ("zh", "zh-TW"):
            rows: list[list[str]]
            with (TRANSLATIONS / f"{language}.csv").open(
                encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.reader(handle))
            self.assertNotEqual(rows[0][:2], ["source", "translation"])
            keys = [row[0] for row in rows if len(row) >= 2 and row[0]]
            self.assertEqual(len(keys), len(set(keys)), f"duplicate {language} source")
            catalogs[language] = {
                row[0]: row[1] for row in rows if len(row) >= 2 and row[0]
            }
            missing = sorted(source for source in sources if not catalogs[language].get(source))
            self.assertFalse(missing, f"missing {language} MBOM translations: {missing}")
            for source in sources:
                self.assertEqual(
                    set(placeholder.findall(source)),
                    set(placeholder.findall(catalogs[language][source])),
                    f"placeholder mismatch for {language}: {source}",
                )
        self.assertEqual(set(catalogs["zh"]), set(catalogs["zh-TW"]))


if __name__ == "__main__":
    unittest.main()
