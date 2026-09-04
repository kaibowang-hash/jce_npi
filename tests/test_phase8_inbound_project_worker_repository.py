from __future__ import annotations

import importlib
import sys
import types
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_core"))
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_core.project.domain import ProjectLifecycleState, ProjectSourceSystem
import tests.test_phase8_inbound_project_repository as landing_test
from npi_integration.inbound_project.config import ProjectIntakePolicy
from npi_integration.inbound_project.domain import ProjectSourceObjectType
from tests.test_phase8_inbound_project_signature_config import policy, profile


NOW = datetime(2026, 8, 16, 8, 0, tzinfo=UTC)


class StubDatabase:
    def __init__(self) -> None:
        self.enabled = {
            "npi-integration@example.invalid": 1,
            "npi-owner@example.invalid": 1,
        }
        self.user_type = {"npi-integration@example.invalid": "System User"}

    def get_value(self, doctype, name, fields, *, as_dict=False):
        if doctype != "User":
            raise AssertionError((doctype, name, fields))
        if isinstance(fields, list):
            value = {
                "enabled": self.enabled.get(str(name), 0),
                "user_type": self.user_type.get(str(name)),
            }
            return types.SimpleNamespace(**value) if as_dict else tuple(value.values())
        if fields == "enabled":
            return self.enabled.get(str(name), 0)
        raise AssertionError((doctype, name, fields))


class Phase8InboundProjectWorkerRepositoryTest(unittest.TestCase):
    WORKER_MODULE = "npi_integration.inbound_project.worker_repository"

    def setUp(self) -> None:
        self.saved_worker = sys.modules.pop(self.WORKER_MODULE, None)
        self.harness = landing_test.Phase8InboundProjectRepositoryTest(
            methodName="test_first_landing_freezes_receipt_source_head_and_audit_without_business_rows"
        )
        self.harness.setUp()
        self.harness.frappe.db = StubDatabase()
        self.harness.frappe.get_roles = lambda actor: (
            ["NPI API User"]
            if actor == "npi-integration@example.invalid"
            else []
        )
        self.module = importlib.import_module(self.WORKER_MODULE)
        self.repository = self.module.FrappeInboundProjectWorkerRepository()

    def tearDown(self) -> None:
        sys.modules.pop(self.WORKER_MODULE, None)
        self.harness.tearDown()
        if self.saved_worker is not None:
            sys.modules[self.WORKER_MODULE] = self.saved_worker

    def land(self, *, event_id: int = 1, object_version: int = 1):
        return self.harness.repository.land(
            self.harness.authenticated(
                event_id=event_id,
                object_version=object_version,
            )
        )

    def inbox(self, receipt_id: UUID):
        return self.harness.documents["NPI Inbox Message"][str(receipt_id)]

    def binding(self):
        values = tuple(self.harness.documents["NPI Project Source Binding"].values())
        self.assertEqual(len(values), 1)
        return values[0]

    def test_pending_claim_live_denial_and_expired_lease_recovery(self) -> None:
        landing = self.land()
        first = self.repository.claim(landing.receipt_id, now=NOW)
        self.assertIsNotNone(first)
        assert first is not None
        inbox = self.inbox(landing.receipt_id)
        self.assertEqual(inbox.state, "processing")
        self.assertEqual(inbox.attempt_count, 1)
        self.assertFalse(first.expired_recovery)

        self.assertIsNone(
            self.repository.claim(
                landing.receipt_id,
                now=NOW + timedelta(seconds=299),
            )
        )
        recovered = self.repository.claim(
            landing.receipt_id,
            now=NOW + timedelta(seconds=300),
        )
        self.assertIsNotNone(recovered)
        assert recovered is not None
        self.assertTrue(recovered.expired_recovery)
        self.assertEqual(recovered.lease.attempt_count, 2)
        self.assertNotEqual(recovered.lease.token, first.lease.token)
        self.assertEqual(inbox.claim_token, str(recovered.lease.token))
        operations = [
            document.operation
            for document in self.harness.documents["NPI Audit Event"].values()
        ]
        self.assertIn("inbound_project.claim", operations)
        self.assertIn("inbound_project.claim_recovered", operations)

    def test_higher_received_version_supersedes_older_claim_before_project_work(self) -> None:
        older = self.land(event_id=1, object_version=1)
        newer = self.land(event_id=2, object_version=2)
        claim = self.repository.claim(older.receipt_id, now=NOW)
        self.assertIsNotNone(claim)
        assert claim is not None

        class ForbiddenProjectRepository:
            def __init__(self, **_kwargs):
                raise AssertionError("Project work must not run for an older source version")

        self.module.FrappeProjectRepository = ForbiddenProjectRepository
        outcome = self.repository.process_claim(
            claim,
            profile=profile(),
            now=NOW + timedelta(seconds=1),
        )
        self.assertEqual(outcome.state, "superseded")
        self.assertEqual(outcome.disposition, "superseded")
        self.assertEqual(self.inbox(older.receipt_id).state, "superseded")
        self.assertEqual(self.inbox(newer.receipt_id).state, "pending")
        self.assertNotIn("NPI Engineering Project", self.harness.documents)

    def test_exact_source_mapping_binds_one_draft_result_and_replays_bound_id(self) -> None:
        landing = self.land()
        claim = self.repository.claim(landing.receipt_id, now=NOW)
        self.assertIsNotNone(claim)
        assert claim is not None
        captured: list[object] = []
        project_id = UUID(int=999)

        class StubProjectRepository:
            def __init__(self, **kwargs):
                captured.append(kwargs)

            def get_template_version(self, template_global_id, template_version):
                captured.append((template_global_id, template_version))
                return types.SimpleNamespace(version=2)

        class StubProjectService:
            def __init__(self, repository):
                captured.append(repository)

            def instantiate(self, command):
                captured.append(command)
                return types.SimpleNamespace(
                    project=types.SimpleNamespace(
                        global_id=project_id,
                        state=ProjectLifecycleState.DRAFT,
                        source_system=ProjectSourceSystem.NPI_ONE,
                        tenant_id="tenant-synthetic",
                        business_code="QTN-SYNTHETIC-0001",
                    ),
                    replayed=False,
                )

        self.module.FrappeProjectRepository = StubProjectRepository
        self.module.ProjectInstantiationService = StubProjectService
        outcome = self.repository.process_claim(
            claim,
            profile=profile(),
            now=NOW + timedelta(seconds=1),
        )
        self.assertEqual(outcome.project_global_id, project_id)
        self.assertEqual(outcome.disposition, "project_created")
        inbox = self.inbox(landing.receipt_id)
        binding = self.binding()
        self.assertEqual(inbox.state, "succeeded")
        self.assertEqual(inbox.project_global_id, str(project_id))
        self.assertEqual(binding.stream_state, "bound")
        self.assertEqual(binding.bound_project_global_id, str(project_id))
        command = next(value for value in captured if hasattr(value, "idempotency_key"))
        self.assertEqual(command.business_code, "QTN-SYNTHETIC-0001")
        self.assertEqual(command.references, ())
        self.assertEqual(command.expected_version, 2)
        self.assertEqual(len(command.idempotency_key), 64)

        # A second current claim that observes the durable binding can only
        # seal the exact existing Project ID; it never invokes Project creation.
        inbox.state = "processing"
        inbox.disposition = "pending"
        inbox.claim_token = str(UUID(int=1001))
        inbox.claimed_at = "2026-08-16T08:10:00Z"
        inbox.lease_expires_at = "2026-08-16T08:15:00Z"
        inbox.attempt_count = 2
        replay_claim = self.module.ClaimedInboxMessage(
            receipt_id=landing.receipt_id,
            event_id=claim.event_id,
            source_key_hash=claim.source_key_hash,
            trace_id=claim.trace_id,
            lease=self.module.ClaimLease(
                token=UUID(int=1001),
                claimed_at=NOW + timedelta(minutes=10),
                expires_at=NOW + timedelta(minutes=15),
                attempt_count=2,
            ),
            expired_recovery=True,
        )
        self.module.FrappeProjectRepository = lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("bound source must not create another Project")
        )
        replay = self.repository.process_claim(
            replay_claim,
            profile=profile(),
            now=NOW + timedelta(minutes=10, seconds=1),
        )
        self.assertEqual(replay.project_global_id, project_id)
        self.assertEqual(replay.disposition, "project_replayed")

    def test_actor_owner_template_and_policy_fail_closed_without_binding(self) -> None:
        landing = self.land(event_id=200, object_version=1)
        claim = self.repository.claim(landing.receipt_id, now=NOW)
        assert claim is not None

        mismatched_policy = ProjectIntakePolicy(
            source_object_type=ProjectSourceObjectType.QUOTATION,
            template_global_id=UUID(int=10),
            template_version=1,
            project_type="new_tool",
            owner_user_id="different-owner@example.invalid",
        )
        mismatched_profile = profile(
            policies=(
                mismatched_policy,
                policy(ProjectSourceObjectType.SALES_ORDER),
            )
        )
        with self.assertRaisesRegex(
            self.module.InboundProjectFinalFailure,
            "INBOUND_PROJECT_POLICY_UNAVAILABLE",
        ):
            self.repository.process_claim(
                claim,
                profile=mismatched_profile,
                now=NOW,
            )

        self.harness.frappe.db.enabled["npi-integration@example.invalid"] = 0
        with self.assertRaisesRegex(
            self.module.InboundProjectFinalFailure,
            "INBOUND_PROJECT_SERVICE_ACTOR_UNAVAILABLE",
        ):
            self.repository.process_claim(claim, profile=profile(), now=NOW)
        self.harness.frappe.db.enabled["npi-integration@example.invalid"] = 1

        self.harness.frappe.db.enabled["npi-owner@example.invalid"] = 0
        with self.assertRaisesRegex(
            self.module.InboundProjectFinalFailure,
            "INBOUND_PROJECT_OWNER_UNAVAILABLE",
        ):
            self.repository.process_claim(claim, profile=profile(), now=NOW)
        self.harness.frappe.db.enabled["npi-owner@example.invalid"] = 1

        class MissingTemplateRepository:
            def __init__(self, **_kwargs):
                pass

            def get_template_version(self, *_args):
                return None

        self.module.FrappeProjectRepository = MissingTemplateRepository
        with self.assertRaisesRegex(
            self.module.InboundProjectFinalFailure,
            "INBOUND_PROJECT_TEMPLATE_UNAVAILABLE",
        ):
            self.repository.process_claim(claim, profile=profile(), now=NOW)
        self.assertFalse(self.binding().get("bound_project_global_id"))


if __name__ == "__main__":
    unittest.main()
