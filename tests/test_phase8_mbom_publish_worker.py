from __future__ import annotations

import importlib
import sys
import types
import unittest
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/npi_core"), str(ROOT / "apps/npi_integration")]

from npi_integration.mbom_publish.adapters import (  # noqa: E402
    MbomAdapterRegistration,
    MbomAdapterRegistry,
)
from npi_integration.mbom_publish.domain import (  # noqa: E402
    MBOM_PUBLISH_OPERATION,
    MbomTargetMode,
)
from tests.test_phase8_mbom_publish_adapters import (  # noqa: E402
    command,
    profile,
    response,
)


NOW = datetime(2026, 8, 21, 17, 0, tzinfo=UTC)
OUTBOX_ID = UUID(int=91)


class StubDatabase:
    def __init__(self, owner):
        self.owner = owner

    def commit(self):
        self.owner.events.append("commit")
        if self.owner.fail_commit_number == self.owner.events.count("commit"):
            raise RuntimeError("private database commit failure")

    def rollback(self):
        self.owner.events.append("rollback")

    def get_value(self, doctype, actor, fields, **kwargs):
        if doctype != "User":
            return None
        enabled = actor == "worker@example.invalid"
        value = {"enabled": int(enabled), "user_type": "System User"}
        return value if kwargs.get("as_dict") else tuple(value.values())


@dataclass
class StubOutcome:
    state: str
    outbox_event_id: UUID = OUTBOX_ID
    request_global_id: UUID = UUID(int=10)
    disposition: str = "synthetic_verified"
    result_global_id: UUID | None = UUID(int=92)
    mapping_advanced_count: int = 0


class StubFinalFailure(RuntimeError):
    def __init__(self, code):
        self.code = code


class StubRepository:
    def __init__(self, owner=None):
        self.owner = owner
        synthetic = profile(MbomTargetMode.SYNTHETIC)
        self.claim_value = types.SimpleNamespace(
            outbox_event_id=OUTBOX_ID,
            request_global_id=UUID(int=10),
            tenant_id=synthetic.tenant_id,
            project_global_id=UUID(synthetic.project_global_id),
            trace_id="trace-p804-worker-0001",
            claim_token=UUID(int=93),
            lease_expires_at=NOW + timedelta(minutes=5),
            command=command(),
            profile_reference=synthetic.reference,
            service_actor_user_id=synthetic.service_actor_user_id,
            expired_recovery=False,
            recovered_after_adapter_boundary=False,
        )
        self.profile_failure = None
        self.boundary_value = True
        self.recoverable = ()
        self.fail_seal = False
        self.results = []

    def execution_route(self, event_id):
        return types.SimpleNamespace(
            outbox_event_id=event_id,
            service_actor_user_id=self.claim_value.service_actor_user_id,
        )

    def claim(self, event_id, *, now, expected_route=None):
        self.owner.events.append("claim")
        return self.claim_value

    def require_execution_profile(self, claim, value):
        self.owner.events.append("profile")
        if self.profile_failure:
            raise self.profile_failure
        return value

    def mark_adapter_boundary(self, claim, *, profile, now):
        self.owner.events.append("boundary")
        return self.boundary_value

    def seal_result(self, claim, *, profile, result, now):
        self.owner.events.append("seal")
        self.results.append(result)
        if self.fail_seal:
            raise RuntimeError("private seal failure")
        return StubOutcome(result.state.value)

    def recover_or_seal_result(self, claim, *, profile, result, now):
        self.owner.events.append("recover")
        return StubOutcome(result.state.value)

    def recoverable_outbox_event_ids(self, *, now):
        self.owner.events.append("recoverable")
        return self.recoverable


class Phase8MbomPublishWorkerTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_core.api",
        "npi_integration.mbom_publish.worker_repository",
        "npi_integration.mbom_publish.frappe_validation",
        "npi_integration.mbom_publish.worker",
    )

    def setUp(self):
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.events = []
        self.fail_commit_number = None
        self.diagnostics = []
        self.enqueued = []
        frappe = types.ModuleType("frappe")
        frappe.db = StubDatabase(self)
        frappe.session = types.SimpleNamespace(user="publisher@example.invalid")
        frappe.set_user = lambda user: setattr(frappe.session, "user", user)
        frappe.get_roles = lambda actor: ["NPI API User"] if actor == "worker@example.invalid" else []
        frappe.enqueue = lambda path, **kwargs: self.enqueued.append({"path": path, **kwargs})
        frappe.get_hooks = lambda _name: []
        frappe.get_attr = lambda _path: None
        sys.modules["frappe"] = frappe
        api = types.ModuleType("npi_core.api")
        api.record_safe_diagnostic = lambda **values: self.diagnostics.append(values)
        sys.modules["npi_core.api"] = api
        validation = types.ModuleType("npi_integration.mbom_publish.frappe_validation")
        validation.MbomServiceActorUnavailable = type(
            "MbomServiceActorUnavailable", (RuntimeError,), {}
        )

        class Scope:
            def __init__(scope, actor):
                scope.actor = actor

            def __enter__(scope):
                if scope.actor != "worker@example.invalid":
                    raise validation.MbomServiceActorUnavailable()
                scope.previous = frappe.session.user
                frappe.set_user(scope.actor)

            def __exit__(scope, *_args):
                frappe.set_user(scope.previous)

        validation.mbom_service_actor_scope = Scope
        sys.modules[validation.__name__] = validation
        repository_module = types.ModuleType("npi_integration.mbom_publish.worker_repository")
        repository_module.FrappeMbomPublishWorkerRepository = StubRepository
        repository_module.MbomPublishWorkerFinalFailure = StubFinalFailure
        repository_module.MbomPublishWorkerOutcome = StubOutcome
        sys.modules[repository_module.__name__] = repository_module
        self.module = importlib.import_module("npi_integration.mbom_publish.worker")
        self.repository = StubRepository(self)
        self.synthetic = profile(MbomTargetMode.SYNTHETIC)
        self.adapter_calls = 0
        self.adapter_users = []

        def adapter(value):
            self.events.append("adapter")
            self.adapter_calls += 1
            self.adapter_users.append(frappe.session.user)
            return response(value)

        self.registry = MbomAdapterRegistry(
            (
                MbomAdapterRegistration(
                    self.synthetic.adapter_resolver,
                    MbomTargetMode.SYNTHETIC,
                    MBOM_PUBLISH_OPERATION,
                    adapter,
                ),
            )
        )

    def tearDown(self):
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def execute(self, profile_value=None):
        return self.module._execute_worker(
            outbox_event_id=OUTBOX_ID,
            repository=self.repository,
            profile_resolver=lambda _tenant, _project: profile_value or self.synthetic,
            registry_resolver=lambda: self.registry,
            clock=lambda: NOW,
        )

    def test_claim_boundary_and_commits_precede_single_adapter_dispatch(self):
        outcome = self.execute()
        self.assertEqual(outcome.state, "synthetic_verified")
        self.assertEqual(
            self.events,
            ["claim", "commit", "profile", "boundary", "commit", "adapter", "seal", "commit"],
        )
        self.assertEqual(self.adapter_calls, 1)
        self.assertEqual(self.adapter_users, ["worker@example.invalid"])
        self.assertEqual(sys.modules["frappe"].session.user, "publisher@example.invalid")

    def test_expired_post_boundary_becomes_uncertain_without_redispatch(self):
        self.repository.claim_value.recovered_after_adapter_boundary = True
        outcome = self.execute()
        self.assertEqual(outcome.state, "uncertain_after_timeout")
        self.assertEqual(self.adapter_calls, 0)
        self.assertEqual(self.events, ["claim", "commit", "seal", "commit"])

    def test_boundary_commit_failure_rolls_back_and_never_dispatches(self):
        self.fail_commit_number = 2
        with self.assertRaises(RuntimeError):
            self.execute()
        self.assertEqual(
            self.events,
            ["claim", "commit", "profile", "boundary", "commit", "rollback"],
        )
        self.assertEqual(self.adapter_calls, 0)
        self.assertEqual(
            self.diagnostics[-1]["code"], "MBOM_PUBLISH_BOUNDARY_COMMIT_FAILED"
        )
        self.assertNotIn("private database commit failure", repr(self.diagnostics))

    def test_profile_or_adapter_failure_is_final_before_boundary(self):
        self.repository.profile_failure = StubFinalFailure(
            "MBOM_PUBLISH_EXECUTION_PROFILE_UNAVAILABLE"
        )
        outcome = self.execute()
        self.assertEqual(outcome.state, "failed_final")
        self.assertEqual(self.adapter_calls, 0)
        self.assertNotIn("boundary", self.events)

    def test_invalid_actor_never_claims_or_dispatches(self):
        self.repository.claim_value.service_actor_user_id = "disabled@example.invalid"
        self.assertIsNone(self.execute())
        self.assertNotIn("claim", self.events)
        self.assertEqual(self.adapter_calls, 0)
        self.assertEqual(self.diagnostics[-1]["code"], "MBOM_PUBLISH_SERVICE_ACTOR_UNAVAILABLE")

    def test_adapter_exception_is_uncertain_and_message_is_not_diagnostic(self):
        private = "private target payload"

        def fail(_command):
            raise RuntimeError(private)

        self.registry = MbomAdapterRegistry(
            (
                MbomAdapterRegistration(
                    self.synthetic.adapter_resolver,
                    MbomTargetMode.SYNTHETIC,
                    MBOM_PUBLISH_OPERATION,
                    fail,
                ),
            )
        )
        outcome = self.execute()
        self.assertEqual(outcome.state, "uncertain_after_timeout")
        self.assertNotIn(private, repr(self.diagnostics))

    def test_local_seal_recovery_does_not_redispatch(self):
        self.repository.fail_seal = True
        outcome = self.execute()
        self.assertEqual(outcome.state, "synthetic_verified")
        self.assertEqual(self.adapter_calls, 1)
        self.assertEqual(self.events.count("recover"), 1)

    def test_bounded_recovery_only_enqueues_repository_allowlist(self):
        self.repository.recoverable = (UUID(int=101), UUID(int=102))
        self.module.FrappeMbomPublishWorkerRepository = lambda: self.repository
        self.assertEqual(self.module.recover_mbom_publish_outbox_messages(), 2)
        self.assertEqual(len(self.enqueued), 2)
        self.assertTrue(all(item["enqueue_after_commit"] for item in self.enqueued))


if __name__ == "__main__":
    unittest.main()
