from __future__ import annotations

import importlib
import sys
import types
import unittest
from contextlib import contextmanager
from datetime import UTC
from pathlib import Path
from unittest.mock import patch
from uuid import UUID


sys.path[:0] = ["apps/npi_core", "apps/npi_integration"]
ROOT = Path(__file__).resolve().parents[1]


class Row(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name, value):
        self[name] = value

    def insert(self):
        self["inserted"] = True
        return self


class Phase9ChangeIntegrationRepositoryTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_core.change_control.response_validation",
        "npi_core.documents.frappe_repository",
        "npi_core.foundation.security",
        "npi_integration.engineering_change.frappe_validation",
        "npi_integration.engineering_change.frappe_repository",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.rows: list[Row] = []
        self.audits: list[object] = []
        self.existing: Row | None = None
        frappe = types.ModuleType("frappe")
        frappe.flags = types.SimpleNamespace()
        frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
        frappe.get_all = lambda *_args, **_kwargs: []

        def get_doc(*args):
            if len(args) == 1 and isinstance(args[0], dict):
                row = Row(args[0])
                self.rows.append(row)
                return row
            if self.existing is not None:
                return self.existing
            raise frappe.DoesNotExistError()

        frappe.get_doc = get_doc
        sys.modules["frappe"] = frappe
        response = types.ModuleType("npi_core.change_control.response_validation")
        response.validate_change_detail_response = lambda value, **_kwargs: value
        sys.modules[response.__name__] = response
        base = types.ModuleType("npi_core.documents.frappe_repository")

        class FrappeDocumentRepository:
            def __init__(self, *, principal, request_id, trace_id):
                self.principal = principal
                self.actor = principal.user_id
                self.request_id = request_id
                self.trace_id = trace_id

            def _append_audit(_self, **values):
                self.audits.append(values)

        base.FrappeDocumentRepository = FrappeDocumentRepository
        base._database_datetime = lambda value: (
            value.astimezone(UTC)
            .replace(tzinfo=None)
            .isoformat(sep=" ", timespec="microseconds")
        )
        sys.modules[base.__name__] = base
        security = types.ModuleType("npi_core.foundation.security")
        security.Principal = object
        sys.modules[security.__name__] = security
        validation = types.ModuleType(
            "npi_integration.engineering_change.frappe_validation"
        )

        @contextmanager
        def scope(*_args, **_kwargs):
            yield None

        validation.inbound_transaction_write = scope
        validation.service_actor_scope = scope
        validation.summary_request_write = scope
        sys.modules[validation.__name__] = validation
        self.module = importlib.import_module(
            "npi_integration.engineering_change.frappe_repository"
        )
        principal = types.SimpleNamespace(user_id="operator@example.invalid")
        self.repository = self.module.FrappeEngineeringChangeIntegrationRepository(
            principal=principal,
            request_id="00000000-0000-4000-8000-000000009401",
            trace_id="trace-p901-repository",
        )

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def test_inbound_inserts_one_operation_specific_receipt_and_audit_then_exact_replay(self) -> None:
        from npi_integration.engineering_change.ingress import (
            AuthenticatedInboundRequest,
        )
        from npi_integration.engineering_change.signature import SignatureHeaders
        from tests.test_phase9_change_integration_domain import NOW, inbound_event, profile

        event = inbound_event()
        request = AuthenticatedInboundRequest(
            profile(),
            SignatureHeaders(
                "00000000-0000-4000-8000-000000009402",
                "key-2026-08",
                str(int(NOW.timestamp())),
                "v1=" + "0" * 64,
            ),
            event,
            b"exact-raw-body",
            NOW,
        )
        outcome = self.repository.receive_inbound(request)
        self.assertTrue(outcome.should_enqueue)
        self.assertFalse(outcome.replayed)
        self.assertEqual(len(self.rows), 1)
        self.assertEqual(self.rows[0]["doctype"], "NPI Engineering Change Inbox")
        self.assertEqual(self.rows[0]["state"], "pending")
        self.assertEqual(
            self.rows[0]["signed_at"],
            NOW.replace(tzinfo=None).isoformat(sep=" ", timespec="microseconds"),
        )
        self.assertEqual(
            self.rows[0]["received_at"],
            NOW.replace(tzinfo=None).isoformat(sep=" ", timespec="microseconds"),
        )
        self.assertTrue(self.rows[0]["inserted"])
        self.assertEqual(len(self.audits), 1)
        self.existing = self.rows[0]
        replay = self.repository.receive_inbound(request)
        self.assertTrue(replay.replayed)
        self.assertFalse(replay.should_enqueue)
        self.assertEqual(len(self.rows), 1)

    def test_inbound_replay_with_changed_canonical_event_is_conflict(self) -> None:
        from npi_integration.engineering_change.ingress import AuthenticatedInboundRequest
        from npi_integration.engineering_change.problems import EngineeringChangeIntegrationConflict
        from npi_integration.engineering_change.signature import SignatureHeaders
        from tests.test_phase9_change_integration_domain import NOW, inbound_event, profile

        self.existing = Row(canonical_event_hash="f" * 64)
        request = AuthenticatedInboundRequest(
            profile(),
            SignatureHeaders(
                "00000000-0000-4000-8000-000000009403",
                "key-2026-08",
                str(int(NOW.timestamp())),
                "v1=" + "0" * 64,
            ),
            inbound_event(),
            b"exact-raw-body",
            NOW,
        )
        with self.assertRaises(EngineeringChangeIntegrationConflict):
            self.repository.receive_inbound(request)

    def test_repository_has_one_transaction_for_summary_request_and_no_generic_writer(self) -> None:
        source = (
            ROOT
            / "apps/npi_integration/npi_integration/engineering_change/frappe_repository.py"
        ).read_text(encoding="utf-8")
        for marker in (
            "with summary_request_write(self.actor):",
            '"NPI Engineering Change Summary Request"',
            '"NPI Engineering Change Summary Outbox"',
            'operation="engineering_change.summary.request"',
            "validate_change_detail_response",
        ):
            self.assertIn(marker, source)
        for forbidden in ("frappe.client", "target_doctype", "target_method"):
            self.assertNotIn(forbidden, source)

    def test_every_initial_physical_datetime_is_database_normalized(self) -> None:
        source = (
            ROOT
            / "apps/npi_integration/npi_integration/engineering_change/frappe_repository.py"
        ).read_text(encoding="utf-8")
        for expression in (
            '"signed_at": _database_datetime(request.headers.signed_at)',
            '"received_at": _database_datetime(request.received_at)',
            '"created_at": _database_datetime(now)',
            '"updated_at": _database_datetime(now)',
        ):
            self.assertEqual(source.count(expression), 1)

    def test_inbound_diagnostic_stages_follow_transaction_order(self) -> None:
        source = (
            ROOT
            / "apps/npi_integration/npi_integration/engineering_change/frappe_repository.py"
        ).read_text(encoding="utf-8")
        codes = (
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
            "P901_CHANGE_INBOUND_REPOSITORY_AUDIT",
            "P901_CHANGE_INBOUND_REPOSITORY_OUTCOME",
        )
        receive_start = source.index("    def receive_inbound")
        receive_end = source.index("    def create_summary_request", receive_start)
        receive_source = source[receive_start:receive_end]
        positions = [receive_source.index(code) for code in codes]
        self.assertEqual(positions, sorted(positions))

    def test_inbox_insert_database_diagnostic_maps_only_fixed_safe_classes(self) -> None:
        expected = {
            1048: "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_NULL",
            1054: "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_MISSING_COLUMN",
            1062: "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_DUPLICATE",
            1146: "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_MISSING_TABLE",
            1205: "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_LOCK",
            1213: "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_LOCK",
            1292: "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_DATETIME",
            1364: "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_MISSING_DEFAULT",
            1366: "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_INVALID_VALUE",
            1406: "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_TOO_LONG",
        }
        for number, code in expected.items():
            with self.subTest(number=number):
                error = RuntimeError(number, "restricted message")
                self.assertEqual(
                    self.module._inbox_insert_database_diagnostic_code(error), code
                )
        for error in (RuntimeError(), RuntimeError(True), RuntimeError(9999)):
            self.assertEqual(
                self.module._inbox_insert_database_diagnostic_code(error),
                "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_OTHER",
            )


if __name__ == "__main__":
    unittest.main()
