from __future__ import annotations

import ast
import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_integration/npi_integration/npi_integration/doctype"
CORE_DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
ITEM_ROOT = ROOT / "apps/npi_integration/npi_integration/item_publish"
TRANSLATIONS = ROOT / "apps/npi_core/npi_core/translations"


class Phase8ItemPublishMetadataTest(unittest.TestCase):
    FOLDERS = (
        "npi_item_publish_request",
        "npi_item_publish_command_idempotency",
        "npi_item_publish_attempt",
        "npi_item_publish_result",
        "npi_item_mapping_head",
        "npi_item_mapping_observation",
    )

    def load(self, folder: str) -> dict[str, object]:
        return json.loads(
            (DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8")
        )

    def test_six_additive_support_doctypes_are_read_only_without_business_crud(self) -> None:
        for folder in self.FOLDERS:
            with self.subTest(folder=folder):
                metadata = self.load(folder)
                fields = {field["fieldname"]: field for field in metadata["fields"]}
                identity = (
                    "scope_key_hash"
                    if folder == "npi_item_publish_command_idempotency"
                    else "global_id"
                )
                self.assertEqual(metadata["autoname"], f"field:{identity}")
                self.assertEqual(metadata["allow_rename"], 0)
                self.assertEqual(metadata["track_changes"], 0)
                self.assertEqual(metadata["read_only"], 1)
                self.assertTrue(fields)
                self.assertTrue(all(field.get("read_only") == 1 for field in fields.values()))
                self.assertNotIn("fixtures", metadata)
                self.assertNotIn("records", metadata)
                for permission in metadata["permissions"]:
                    self.assertFalse(permission.get("write", 0))
                    self.assertFalse(permission.get("create", 0))
                    self.assertFalse(permission.get("delete", 0))
                    self.assertFalse(permission.get("export", 0))
                    self.assertFalse(permission.get("print", 0))
                    self.assertFalse(permission.get("email", 0))

    def test_version_one_outbox_is_additive_guarded_and_legacy_rows_cannot_be_promoted(self) -> None:
        metadata = self.load("npi_outbox_message")
        fields = {field["fieldname"]: field for field in metadata["fields"]}
        self.assertEqual(metadata["autoname"], "field:event_id")
        self.assertEqual(metadata["allow_rename"], 0)
        self.assertEqual(metadata["read_only"], 1)
        self.assertIn("uncertain", fields["state"]["options"].splitlines())
        for fieldname in (
            "schema_version",
            "operation",
            "tenant_id",
            "project_global_id",
            "request_global_id",
            "profile_snapshot_hash",
            "source_stream_key_hash",
            "source_hash",
            "expected_mapping_version",
            "event_snapshot_hash",
            "claim_token",
            "lease_expires_at",
            "adapter_boundary_crossed",
            "last_attempt_global_id",
            "result_global_id",
        ):
            self.assertIn(fieldname, fields)
            self.assertNotEqual(fields[fieldname].get("reqd"), 1)
        controller = (
            DOCTYPE_ROOT / "npi_outbox_message/npi_outbox_message.py"
        ).read_text(encoding="utf-8")
        for marker in (
            "require_item_outbox_write()",
            "deny_legacy_outbox_promotion()",
            "deny_item_history_update()",
            "assert_immutable_fields(",
            "validate_one_way_transition(",
            "deny_item_history_delete()",
            'previous.state in _ITEM_TERMINAL_STATES',
            'self.state == "pending" and self.adapter_boundary_crossed',
            'not terminal and self.result_global_id',
            'ITEM_REQUEST_EVENT_TYPE',
            'ITEM_PUBLISH_OPERATION',
        ):
            self.assertIn(marker, controller)

    def test_controllers_use_narrow_internal_write_guards_and_immutable_history(self) -> None:
        guards = (ITEM_ROOT / "frappe_validation.py").read_text(encoding="utf-8")
        for marker in (
            'ITEM_OUTBOX_WRITE_FLAG = "npi_item_outbox_write"',
            'ITEM_REQUEST_WRITE_FLAG = "npi_item_publish_request_write"',
            'ITEM_IDEMPOTENCY_WRITE_FLAG = "npi_item_publish_idempotency_write"',
            'ITEM_ATTEMPT_WRITE_FLAG = "npi_item_publish_attempt_write"',
            'ITEM_RESULT_WRITE_FLAG = "npi_item_publish_result_write"',
            'ITEM_MAPPING_WRITE_FLAG = "npi_item_mapping_write"',
            "item_request_transaction_write()",
            "item_claim_write()",
            "item_result_transaction_write()",
        ):
            self.assertIn(marker, guards)
        expected_guards = {
            "npi_item_publish_request": "require_item_request_write()",
            "npi_item_publish_command_idempotency": "require_item_idempotency_write()",
            "npi_item_publish_attempt": "require_item_attempt_write()",
            "npi_item_publish_result": "require_item_result_write()",
            "npi_item_mapping_head": "require_item_mapping_write()",
            "npi_item_mapping_observation": "require_item_mapping_write()",
        }
        for folder, guard in expected_guards.items():
            source = (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(
                encoding="utf-8"
            )
            self.assertGreaterEqual(source.count(guard), 2)
            self.assertIn("deny_item_history_delete()", source)
            ast.parse(source)
        self.assertIn(
            "deny_item_history_update()",
            (DOCTYPE_ROOT / "npi_item_publish_result/npi_item_publish_result.py").read_text(
                encoding="utf-8"
            ),
        )
        self.assertIn(
            "deny_item_history_update()",
            (DOCTYPE_ROOT / "npi_item_publish_attempt/npi_item_publish_attempt.py").read_text(
                encoding="utf-8"
            ),
        )
        self.assertIn(
            "assert_immutable_fields(",
            (DOCTYPE_ROOT / "npi_item_mapping_head/npi_item_mapping_head.py").read_text(
                encoding="utf-8"
            ),
        )

    def test_mapping_metadata_never_grants_authority_to_mock_or_synthetic_proof(self) -> None:
        observation = (
            DOCTYPE_ROOT
            / "npi_item_mapping_observation/npi_item_mapping_observation.py"
        ).read_text(encoding="utf-8")
        head = (
            DOCTYPE_ROOT / "npi_item_mapping_head/npi_item_mapping_head.py"
        ).read_text(encoding="utf-8")
        self.assertIn("Synthetic Item proof cannot contain or advance a formal mapping.", observation)
        self.assertIn("ItemResultAuthority.AUTHORITATIVE_SANDBOX", observation)
        self.assertIn('"authority": "authoritative_sandbox"', head)
        self.assertIn('"disposition": "advanced"', head)
        self.assertIn("require_exact_parent(", head)

    def test_metadata_links_target_real_repository_doctypes(self) -> None:
        names = {
            str(json.loads(path.read_text(encoding="utf-8"))["name"])
            for root in (DOCTYPE_ROOT, CORE_DOCTYPE_ROOT)
            for path in root.glob("*/*.json")
        }
        for folder in (*self.FOLDERS, "npi_outbox_message"):
            for field in self.load(folder)["fields"]:
                if field.get("fieldtype") == "Link":
                    self.assertIn(field.get("options"), names)

    def test_visible_sources_have_symmetric_direct_chinese_translations(self) -> None:
        sources: set[str] = set()
        source_paths = [
            ITEM_ROOT / "frappe_validation.py",
            ITEM_ROOT / "frappe_repository.py",
            ITEM_ROOT / "problems.py",
            ROOT / "apps/npi_integration/npi_integration/item_publish_api.py",
        ]
        for folder in (*self.FOLDERS, "npi_outbox_message"):
            metadata = self.load(folder)
            sources.add(str(metadata["name"]))
            sources.update(str(field["label"]) for field in metadata["fields"])
            for field in metadata["fields"]:
                if field.get("fieldtype") == "Select":
                    sources.update(
                        value
                        for value in str(field.get("options", "")).splitlines()
                        if value
                    )
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
        for language in ("zh", "zh-TW"):
            with (TRANSLATIONS / f"{language}.csv").open(
                encoding="utf-8", newline=""
            ) as handle:
                catalogs[language] = {
                    row[0]: row[1]
                    for row in csv.reader(handle)
                    if len(row) >= 2 and row[0]
                }
            self.assertFalse(
                sorted(source for source in sources if not catalogs[language].get(source)),
                f"missing {language} Item publish translations",
            )
        self.assertEqual(set(catalogs["zh"]), set(catalogs["zh-TW"]))

    def test_checkpoint_three_activates_only_closed_worker_and_synthetic_runtime(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in ITEM_ROOT.glob("*.py")
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
        repository = (ITEM_ROOT / "frappe_repository.py").read_text(
            encoding="utf-8"
        )
        api = (
            ROOT / "apps/npi_integration/npi_integration/item_publish_api.py"
        ).read_text(encoding="utf-8")
        for marker in (
            "class FrappeItemPublishRepository",
            "self._locked_command_project(project_id)",
            "self._exact_released_phase5_request(",
            "group_item_source(",
            "self._current_mapping_for_source(project, source, lock=True)",
            "with item_request_transaction_write()",
            "self._insert_item_request(",
            "self._insert_outbox(",
            "self._insert_idempotency_receipt(",
        ):
            self.assertIn(marker, repository)
        for marker in (
            "frappe.db.commit()",
            "_enqueue_after_commit(outcome.outbox_event_id)",
            'enqueue_after_commit=False',
            '"npi_integration.item_publish.worker.process_outbox_message"',
            '_PROFILE_RESOLVER_HOOK = "npi_item_publish_profile_resolver"',
        ):
            self.assertIn(marker, api)
        worker = (ITEM_ROOT / "worker.py").read_text(encoding="utf-8")
        worker_repository = (ITEM_ROOT / "worker_repository.py").read_text(
            encoding="utf-8"
        )
        adapters = (ITEM_ROOT / "adapters.py").read_text(encoding="utf-8")
        runtime_fixture = (ITEM_ROOT / "runtime_fixture.py").read_text(
            encoding="utf-8"
        )
        for marker in (
            "recover_item_publish_outbox_messages",
            "mark_adapter_boundary",
            "uncertain_item_adapter_result",
            "ITEM_PUBLISH_RESULT_COMMIT_FAILED",
        ):
            self.assertIn(marker, worker)
        for marker in (
            "class FrappeItemPublishWorkerRepository",
            "recoverable_outbox_event_ids",
            "item_claim_write()",
            "item_result_transaction_write()",
            "classify_mapping_observation(",
        ):
            self.assertIn(marker, worker_repository)
        self.assertIn("class ItemAdapterRegistry", adapters)
        self.assertIn("npi-one-item-publish-disposable-v1", runtime_fixture)
        self.assertNotIn("https://", runtime_fixture)
        hooks = (
            ROOT / "apps/npi_integration/npi_integration/hooks.py"
        ).read_text(encoding="utf-8")
        self.assertIn("recover_item_publish_outbox_messages", hooks)
        self.assertIn("npi_item_publish_profile_resolver", hooks)
        self.assertIn("npi_item_publish_adapter_registry", hooks)


if __name__ == "__main__":
    unittest.main()
