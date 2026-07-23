from __future__ import annotations

import sys
import unittest
from uuid import uuid4

sys.path[:0] = ["apps/npi_core", "apps/npi_integration"]

from npi_core.foundation.audit import create_audit_event
from npi_core.foundation.concurrency import make_etag, next_version
from npi_core.foundation.errors import AuthenticationRequired, PermissionDenied, VersionConflict
from npi_core.foundation.files import FileRevision, ScanState
from npi_core.foundation.identity import GlobalIdentity, assert_global_id_immutable
from npi_core.foundation.security import Principal, ProjectAccess, authorize_project, authorize_tenant
from npi_core.api import execute_api
from npi_integration.reliable import InboxRegistry, IntegrationEvent, MessageState, OutboxMessage


class IdentityAndConcurrencyTest(unittest.TestCase):
    def test_identity_is_uuid_and_immutable(self) -> None:
        identity = GlobalIdentity.create("EngineeringProject", "PROJECT-1")
        self.assertEqual(identity.source_system, "NPI_ONE")
        assert_global_id_immutable(identity.global_id, identity.global_id)
        with self.assertRaises(ValueError):
            assert_global_id_immutable(identity.global_id, uuid4())

    def test_expected_version_is_required(self) -> None:
        self.assertEqual(next_version(2, 2), 3)
        self.assertIn(":3", make_etag(str(uuid4()), 3))
        with self.assertRaises(VersionConflict):
            next_version(2, 1)


class PermissionTest(unittest.TestCase):
    def test_authentication_and_project_scope_are_server_rules(self) -> None:
        with self.assertRaises(AuthenticationRequired):
            authorize_project(None, "P1", ProjectAccess.VIEW)
        principal = Principal("user@example.invalid", project_access={"P1": ProjectAccess.CONTRIBUTE}, tenant_id="T1")
        authorize_project(principal, "P1", ProjectAccess.VIEW, project_tenant_id="T1")
        authorize_tenant(principal, "T1")
        with self.assertRaises(PermissionDenied):
            authorize_project(principal, "P2", ProjectAccess.VIEW)
        with self.assertRaises(PermissionDenied):
            authorize_project(principal, "P1", ProjectAccess.VIEW, project_tenant_id="T2")

    def test_external_user_cannot_approve(self) -> None:
        principal = Principal("supplier@example.invalid", project_access={"P1": ProjectAccess.APPROVE}, is_external=True)
        with self.assertRaises(PermissionDenied):
            authorize_project(principal, "P1", ProjectAccess.APPROVE)


class ApiAuditAndFileTest(unittest.TestCase):
    def test_problem_response_has_trace(self) -> None:
        status, body, headers = execute_api(lambda: (_ for _ in ()).throw(PermissionDenied()), "trace-123456")
        self.assertEqual(status, 403)
        self.assertEqual(body["code"], "PERMISSION_DENIED")
        self.assertEqual(headers["Content-Type"], "application/problem+json")
        self.assertEqual(body["traceId"], headers["X-Trace-ID"])

    def test_unexpected_api_error_uses_safe_retryable_problem(self) -> None:
        secret_error_text = "do-not-expose-database-detail"

        def fail() -> dict[str, object]:
            raise RuntimeError(secret_error_text)

        status, body, headers = execute_api(fail, "trace-unexpected-123")

        self.assertEqual(status, 500)
        self.assertEqual(body["code"], "INTERNAL_SERVER_ERROR")
        self.assertTrue(body["retryable"])
        self.assertNotIn(secret_error_text, str(body))
        self.assertEqual(headers["Content-Type"], "application/problem+json")
        self.assertEqual(body["traceId"], headers["X-Trace-ID"])

    def test_error_reporter_failure_cannot_break_problem_contract(self) -> None:
        def fail_handler() -> dict[str, object]:
            raise RuntimeError("handler detail")

        def fail_reporter(_error: Exception, _trace_id: str) -> None:
            raise RuntimeError("logger unavailable")

        status, body, headers = execute_api(
            fail_handler,
            "trace-reporter-123",
            fail_reporter,
        )

        self.assertEqual(status, 500)
        self.assertEqual(body["code"], "INTERNAL_SERVER_ERROR")
        self.assertNotIn("handler detail", str(body))
        self.assertNotIn("logger unavailable", str(body))
        self.assertEqual(body["traceId"], headers["X-Trace-ID"])

    def test_audit_redacts_common_secret_fields(self) -> None:
        event = create_audit_event(actor="user", trace_id="trace-123456", operation="update",
                                   global_id=uuid4(), object_version=1, result="succeeded",
                                   input_summary={"field": "value", "token": "sensitive"})
        self.assertEqual(dict(event.input_summary), {"field": "value"})

    def test_file_release_requires_private_clean_immutable_revision(self) -> None:
        revision = FileRevision.from_content(uuid4(), 1, "drawing.pdf", "application/pdf", b"content")
        self.assertTrue(revision.is_private)
        self.assertTrue(revision.verify(b"content"))
        with self.assertRaises(ValueError):
            revision.release()
        released = revision.mark_scanned(ScanState.CLEAN).release()
        with self.assertRaises(ValueError):
            released.mark_scanned(ScanState.FAILED)


class ReliableMessagingTest(unittest.TestCase):
    def test_outbox_never_reports_success_before_completion(self) -> None:
        event = IntegrationEvent.create(event_type="npi.project.updated", global_id=uuid4(),
                                        object_type="EngineeringProject", object_version=1,
                                        trace_id="trace-123456", payload={"project_code": "P1"})
        message = OutboxMessage(event)
        self.assertEqual(message.state, MessageState.PENDING)
        processing = message.start()
        self.assertEqual(processing.attempt_count, 1)
        self.assertEqual(processing.fail("ERP_UNAVAILABLE", retryable=True).state, MessageState.FAILED_RETRYABLE)
        self.assertEqual(processing.complete().state, MessageState.SUCCEEDED)

    def test_inbox_duplicate_is_idempotent_and_hash_conflict_quarantines(self) -> None:
        registry = InboxRegistry()
        event_id = uuid4()
        _, created = registry.land(event_id, {"status": "open"})
        duplicate, duplicate_created = registry.land(event_id, {"status": "open"})
        conflict, conflict_created = registry.land(event_id, {"status": "closed"})
        self.assertTrue(created)
        self.assertFalse(duplicate_created)
        self.assertEqual(duplicate.state, MessageState.PENDING)
        self.assertFalse(conflict_created)
        self.assertEqual(conflict.state, MessageState.QUARANTINED)


if __name__ == "__main__":
    unittest.main()
