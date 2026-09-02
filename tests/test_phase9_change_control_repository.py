from __future__ import annotations

import importlib
import inspect
import json
import os
import sys
import tempfile
import types
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import UUID


sys.path.insert(0, "apps/npi_core")

from npi_core.change_control.domain import EngineeringChangeEvent, EngineeringChangeEventType
from tests.test_phase9_change_control_domain import NOW, revision


class AttrDict(dict):
    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: object) -> None:
        self[name] = value


class Phase9ChangeControlRepositoryTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_core.change_control.frappe_validation",
        "npi_core.change_control.frappe_repository",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.flags = types.SimpleNamespace()
        frappe.session = types.SimpleNamespace(user="service@example.invalid")
        frappe.get_roles = lambda user: (
            ["NPI API User"] if user == "service@example.invalid" else []
        )
        frappe.PermissionError = type("FrappePermissionError", (Exception,), {})
        frappe.ValidationError = type("FrappeValidationError", (Exception,), {})
        frappe.throw = lambda message, error_type: (_ for _ in ()).throw(error_type(str(message)))
        frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
        frappe.UniqueValidationError = type("UniqueValidationError", (Exception,), {})
        frappe.DuplicateEntryError = type("DuplicateEntryError", (Exception,), {})
        frappe.db = types.SimpleNamespace()
        sys.modules["frappe"] = frappe
        self.repository = importlib.import_module("npi_core.change_control.frappe_repository")

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def test_persisted_revision_round_trip_revalidates_canonical_snapshot_and_hash(self) -> None:
        value = revision()
        document = AttrDict(
            revision_snapshot=value.revision_payload(),
            snapshot_hash=value.snapshot_hash,
        )
        restored = self.repository._revision_from_document(document)
        self.assertEqual(restored, value)
        document.snapshot_hash = "f" * 64
        with self.assertRaises(RuntimeError):
            self.repository._revision_from_document(document)

    def test_persisted_event_round_trip_revalidates_exact_revision_binding(self) -> None:
        current = revision()
        value = EngineeringChangeEvent(
            global_id=UUID(int=90),
            change_global_id=current.change_global_id,
            tenant_id=current.tenant_id,
            project_global_id=current.project_global_id,
            revision_global_id=current.global_id,
            revision=current.revision,
            revision_snapshot_hash=current.snapshot_hash,
            event_type=EngineeringChangeEventType.CREATED,
            actor_user_id=current.created_by_user_id,
            occurred_at=NOW,
            request_id=current.request_id,
            trace_id=current.trace_id,
        )
        restored = self.repository._event_from_document(
            AttrDict(event_snapshot=value.event_payload(), event_hash=value.event_hash)
        )
        self.assertEqual(restored, value)

    def test_root_projection_contains_only_current_pointer_and_raw_formal_observation(self) -> None:
        current = revision()
        document = AttrDict()
        self.repository.FrappeChangeControlRepository._apply_root(document, current)
        self.assertEqual(document.current_revision_global_id, str(current.global_id))
        self.assertEqual(document.current_revision_snapshot_hash, current.snapshot_hash)
        self.assertEqual(document.formal_change_doctype, "Engineering Change Request")
        self.assertEqual(document.formal_change_raw_status, "Effective")
        self.assertNotIn("formal_change_passed", document)
        self.assertNotIn("gate_result", document)

    def test_command_transaction_write_order_is_receipt_history_root_audit_seal(self) -> None:
        create = inspect.getsource(self.repository.FrappeChangeControlRepository.create_change)
        successor = inspect.getsource(self.repository.FrappeChangeControlRepository._successor_command)
        for source in (create, successor):
            positions = [
                source.index("self._insert_receipt("),
                source.index("self._insert_revision("),
                source.index("self._insert_event("),
                min(
                    position
                    for marker in ("self._insert_root(", "self._apply_root(")
                    if (position := source.find(marker)) >= 0
                ),
                source.index("self._append_audit("),
                source.index("self._seal_receipt("),
            ]
            self.assertEqual(positions, sorted(positions))
        self.assertIn("with change_command_write(", create)
        self.assertIn("change_observation_write(", successor)
        self.assertIn("service_actor_user_id=self.actor", create)
        self.assertIn("service_actor_user_id=self.actor", successor)
        self.assertIn("save_change_support_document(root, capability=capability)", successor)

    def test_actor_bound_receipts_include_tenant_project_actor_operation_and_key(self) -> None:
        first = self.repository._actor_key_hash(
            "tenant-a", UUID(int=3), "owner@example.invalid", "engineering_change.revise", "a" * 64
        )
        self.assertNotEqual(
            first,
            self.repository._actor_key_hash(
                "tenant-a", UUID(int=3), "other@example.invalid", "engineering_change.revise", "a" * 64
            ),
        )
        self.assertNotEqual(
            first,
            self.repository._actor_key_hash(
                "tenant-a", UUID(int=3), "owner@example.invalid", "engineering_change.close", "a" * 64
            ),
        )

    def test_successor_keeps_title_immutable_and_does_not_forward_it(self) -> None:
        current = revision()
        content = {
            "title": current.title,
            "reason": current.reason,
            "impact_assessments": current.impact_assessments,
            "affected_objects": current.affected_objects,
            "implementation_tasks": current.implementation_tasks,
            "effectivity_rules": current.effectivity_rules,
            "dispositions": current.dispositions,
            "revalidation_requirements": current.revalidation_requirements,
            "cost_summary": current.cost_summary,
            "closure_evidence": current.closure_evidence,
        }
        successor = self.repository._successor_content(current, content)
        self.assertNotIn("title", successor)
        with self.assertRaises(self.repository.RequestValidationFailed):
            self.repository._successor_content(
                current,
                {**content, "title": "Renamed engineering change"},
            )

    def test_source_has_no_permission_bypass_direct_sql_commit_or_external_effect(self) -> None:
        source = inspect.getsource(self.repository)
        for forbidden in (
            "ignore_permissions", "frappe.db." + "sql", "frappe.db.commit",
            "requests.", "httpx.", "enqueue(", "publish_realtime(",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn("for_update=True", source)
        self.assertIn("VersionConflict", source)
        self.assertIn("ChangeControlIdempotencyConflict", source)

    def test_datetime_storage_is_utc_without_changing_domain_snapshot_text(self) -> None:
        value = datetime(2026, 8, 31, 9, 10, tzinfo=UTC)
        self.assertEqual(
            self.repository._database_datetime(value),
            "2026-08-31 09:10:00.000000",
        )

    def test_revise_server_diagnostic_records_only_innermost_exact_safe_tuple(self) -> None:
        trace = "trace-" + "d" * 32
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p9-01-engineering-change-runtime-diagnostic.json"
            with patch.dict(
                os.environ,
                {"NPI_P9_01_RUNTIME_DIAGNOSTIC_PATH": str(path)},
                clear=False,
            ):
                with self.repository.engineering_change_revise_server_diagnostics(
                    trace,
                    active=True,
                ):
                    with self.assertRaises(self.repository.frappe.ValidationError):
                        with self.repository.engineering_change_revise_server_step(
                            "P901_CHANGE_REVISE_API_CALL"
                        ):
                            with self.repository.engineering_change_revise_server_step(
                                "P901_CHANGE_REVISE_REPOSITORY_REVISION_INSERT"
                            ):
                                raise self.repository.frappe.ValidationError(
                                    "restricted"
                                )
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                record,
                {
                    "code": "P901_CHANGE_REVISE_REPOSITORY_REVISION_INSERT",
                    "exceptionType": "FrappeValidationError",
                    "traceId": trace,
                },
            )
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("restricted", path.read_text(encoding="utf-8"))
            self.assertFalse(
                hasattr(
                    self.repository.frappe.flags,
                    "npi_p901_change_revise_server_diagnostic",
                )
            )

    def test_revise_server_diagnostic_wrong_scope_is_dormant(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p9-01-engineering-change-runtime-diagnostic.json"
            with patch.dict(
                os.environ,
                {"NPI_P9_01_RUNTIME_DIAGNOSTIC_PATH": str(path)},
                clear=False,
            ):
                for trace, active in (("wrong", True), ("trace-" + "e" * 32, False)):
                    with self.repository.engineering_change_revise_server_diagnostics(
                        trace,
                        active=active,
                    ):
                        with self.assertRaises(RuntimeError):
                            with self.repository.engineering_change_revise_server_step(
                                "P901_CHANGE_REVISE_REPOSITORY_ROOT_SAVE"
                            ):
                                raise RuntimeError("restricted")
            self.assertFalse(path.exists())

    def test_revise_server_stage_order_matches_the_transaction_order(self) -> None:
        source = inspect.getsource(
            self.repository.FrappeChangeControlRepository._successor_command
        )
        codes = (
            "P901_CHANGE_REVISE_REPOSITORY_PROJECT_LOCK",
            "P901_CHANGE_REVISE_REPOSITORY_ROOT_LOCK",
            "P901_CHANGE_REVISE_REPOSITORY_PAYLOAD",
            "P901_CHANGE_REVISE_REPOSITORY_REPLAY",
            "P901_CHANGE_REVISE_REPOSITORY_CURRENT",
            "P901_CHANGE_REVISE_REPOSITORY_PREDECESSOR",
            "P901_CHANGE_REVISE_REPOSITORY_STATE",
            "P901_CHANGE_REVISE_REPOSITORY_TRANSFORM",
            "P901_CHANGE_REVISE_REPOSITORY_EVENT",
            "P901_CHANGE_REVISE_REPOSITORY_RESPONSE",
            "P901_CHANGE_REVISE_REPOSITORY_WRITE_SCOPE",
            "P901_CHANGE_REVISE_REPOSITORY_RECEIPT",
            "P901_CHANGE_REVISE_REPOSITORY_RECEIPT_REPLAY",
            "P901_CHANGE_REVISE_REPOSITORY_REVISION_INSERT",
            "P901_CHANGE_REVISE_REPOSITORY_EVENT_INSERT",
            "P901_CHANGE_REVISE_REPOSITORY_ROOT_APPLY",
            "P901_CHANGE_REVISE_REPOSITORY_ROOT_SAVE",
            "P901_CHANGE_REVISE_REPOSITORY_AUDIT",
            "P901_CHANGE_REVISE_REPOSITORY_RECEIPT_SEAL",
            "P901_CHANGE_REVISE_REPOSITORY_OUTCOME",
        )
        positions = [source.index(code) for code in codes]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(
            set(codes),
            {
                code
                for code in self.repository.ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_CODES
                if code.startswith("P901_CHANGE_REVISE_REPOSITORY_")
            },
        )

    def test_inbound_server_diagnostic_codes_are_exact(self) -> None:
        expected = {
            "P901_CHANGE_INBOUND_API_CALL",
            "P901_CHANGE_INBOUND_API_FIELDS",
            "P901_CHANGE_INBOUND_API_REQUEST",
            "P901_CHANGE_INBOUND_API_AUTHENTICATE",
            "P901_CHANGE_INBOUND_API_PRINCIPAL",
            "P901_CHANGE_INBOUND_API_REPOSITORY_INIT",
            "P901_CHANGE_INBOUND_API_REPOSITORY_CALL",
            "P901_CHANGE_INBOUND_API_COMMIT",
            "P901_CHANGE_INBOUND_API_ENQUEUE",
            "P901_CHANGE_INBOUND_API_OUTCOME",
            "P901_CHANGE_INBOUND_API_RESPONSE",
            "P901_CHANGE_INBOUND_REPOSITORY_INPUT",
            "P901_CHANGE_INBOUND_REPOSITORY_EVENT",
            "P901_CHANGE_INBOUND_REPOSITORY_HASHES",
            "P901_CHANGE_INBOUND_REPOSITORY_REPLAY",
            "P901_CHANGE_INBOUND_REPOSITORY_SOURCE_KEY",
            "P901_CHANGE_INBOUND_REPOSITORY_LATEST",
            "P901_CHANGE_INBOUND_REPOSITORY_VERSION",
            "P901_CHANGE_INBOUND_REPOSITORY_RESPONSE",
            "P901_CHANGE_INBOUND_REPOSITORY_WRITE_SCOPE",
            "P901_CHANGE_INBOUND_REPOSITORY_INBOX_INSERT",
            "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_NULL",
            "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_MISSING_COLUMN",
            "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_DUPLICATE",
            "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_MISSING_TABLE",
            "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_LOCK",
            "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_DATETIME",
            "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_MISSING_DEFAULT",
            "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_INVALID_VALUE",
            "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_TOO_LONG",
            "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_OTHER",
            "P901_CHANGE_INBOUND_REPOSITORY_AUDIT",
            "P901_CHANGE_INBOUND_REPOSITORY_OUTCOME",
        }
        self.assertEqual(
            expected,
            {
                code
                for code in self.repository.ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_CODES
                if code.startswith("P901_CHANGE_INBOUND_")
            },
        )

    def test_summary_server_diagnostic_codes_are_exact(self) -> None:
        expected = {
            "P901_CHANGE_SUMMARY_API_CALL",
            "P901_CHANGE_SUMMARY_API_USER",
            "P901_CHANGE_SUMMARY_API_CSRF",
            "P901_CHANGE_SUMMARY_API_PRINCIPAL",
            "P901_CHANGE_SUMMARY_API_ROUTES",
            "P901_CHANGE_SUMMARY_API_REPOSITORY_INIT",
            "P901_CHANGE_SUMMARY_API_SCOPE",
            "P901_CHANGE_SUMMARY_API_FIELDS",
            "P901_CHANGE_SUMMARY_API_REPOSITORY_CALL",
            "P901_CHANGE_SUMMARY_API_COMMIT",
            "P901_CHANGE_SUMMARY_API_ENQUEUE",
            "P901_CHANGE_SUMMARY_API_OUTCOME",
            "P901_CHANGE_SUMMARY_API_RESPONSE",
            "P901_CHANGE_SUMMARY_REPOSITORY_PROJECT_LOCK",
            "P901_CHANGE_SUMMARY_REPOSITORY_PROFILE",
            "P901_CHANGE_SUMMARY_REPOSITORY_REPLAY_LOOKUP",
            "P901_CHANGE_SUMMARY_REPOSITORY_REPLAY",
            "P901_CHANGE_SUMMARY_REPOSITORY_DETAIL",
            "P901_CHANGE_SUMMARY_REPOSITORY_DETAIL_VALIDATE",
            "P901_CHANGE_SUMMARY_REPOSITORY_CURRENT",
            "P901_CHANGE_SUMMARY_REPOSITORY_SUMMARY",
            "P901_CHANGE_SUMMARY_REPOSITORY_REQUEST_VALUE",
            "P901_CHANGE_SUMMARY_REPOSITORY_RESPONSE",
            "P901_CHANGE_SUMMARY_REPOSITORY_WRITE_SCOPE",
            "P901_CHANGE_SUMMARY_REPOSITORY_REQUEST_INSERT",
            "P901_CHANGE_SUMMARY_REPOSITORY_OUTBOX_PAYLOAD",
            "P901_CHANGE_SUMMARY_REPOSITORY_OUTBOX_INSERT",
            "P901_CHANGE_SUMMARY_REPOSITORY_AUDIT",
            "P901_CHANGE_SUMMARY_REPOSITORY_OUTCOME",
        }
        self.assertEqual(
            expected,
            {
                code
                for code in self.repository.ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_CODES
                if code.startswith("P901_CHANGE_SUMMARY_")
            },
        )


if __name__ == "__main__":
    unittest.main()
