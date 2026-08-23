from __future__ import annotations

import importlib
import sys
import types
import unittest
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/npi_core"), str(ROOT / "apps/npi_integration")]

from npi_integration.tool_asset_request.adapters import ToolAssetAdapterRegistry, ToolAssetAdapterRegistration  # noqa: E402
from npi_integration.tool_asset_request.execution_domain import ToolAssetExecutionOperation, ToolAssetExecutionTargetMode  # noqa: E402
from tests.test_phase8_tool_asset_adapters import command, execution_profile, response  # noqa: E402

NOW = datetime(2026, 8, 24, 9, tzinfo=UTC)


class Repository:
    def __init__(self, owner):
        self.owner = owner
        profile = execution_profile(ToolAssetExecutionTargetMode.SYNTHETIC)
        self.claim_value = types.SimpleNamespace(tenant_id=profile.tenant_id, project_global_id=UUID(profile.project_global_id), service_actor_user_id=profile.service_actor_user_id, trace_id="trace-tool-asset-worker-0001", command=command(), request=types.SimpleNamespace(operation=ToolAssetExecutionOperation.CREATE), recovered_after_adapter_boundary=False)
        self.profile = profile
        self.claimed = True
        self.recovered = ()

    def execution_route(self, event_id):
        self.owner.events.append("route")
        return types.SimpleNamespace(service_actor_user_id=self.claim_value.service_actor_user_id)

    def claim(self, event_id, *, now, expected_route):
        self.owner.events.append("claim")
        return self.claim_value if self.claimed else None

    def require_execution_profile(self, claim, value):
        self.owner.events.append("profile")
        return value

    def mark_adapter_boundary(self, claim, *, profile, now):
        self.owner.events.append("boundary")
        return True

    def seal_result(self, claim, *, profile, result, now):
        self.owner.events.append("seal")
        return types.SimpleNamespace(outbox_event_id=UUID(int=1), request_global_id=UUID(int=2), result_global_id=UUID(int=3), state=result.state.value, disposition="non_authoritative", mapping_advanced=False)

    recover_or_seal_result = seal_result

    def recoverable_outbox_event_ids(self, *, now):
        return self.recovered


class Phase8ToolAssetWorkerTest(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.module_names = ("frappe", "npi_core.api", "npi_integration.tool_asset_request.execution_frappe_validation", "npi_integration.tool_asset_request.worker_repository", "npi_integration.tool_asset_request.worker")
        self.saved_modules = {name: sys.modules.get(name) for name in self.module_names}
        for name in self.module_names:
            sys.modules.pop(name, None)
        fake = types.ModuleType("frappe")
        sys.modules["frappe"] = fake
        fake.session = types.SimpleNamespace(user="requester@example.invalid")
        fake.db = types.SimpleNamespace(commit=lambda: self.events.append("commit"), rollback=lambda: self.events.append("rollback"), get_value=lambda *a, **k: {"enabled":1,"user_type":"System User"})
        fake.get_roles = lambda user: ["NPI API User"]
        fake.set_user = lambda user: (setattr(fake.session, "user", user), self.events.append(f"user:{user}"))
        fake.enqueue = lambda *a, **k: self.events.append("enqueue")
        fake.get_hooks = lambda name: ()
        fake.get_attr = lambda path: None
        api = types.ModuleType("npi_core.api")
        api.record_safe_diagnostic = lambda **value: self.events.append(("diagnostic", value["code"], value["exception_type"]))
        sys.modules["npi_core.api"] = api
        validation = types.ModuleType("npi_integration.tool_asset_request.execution_frappe_validation")
        validation.ToolAssetServiceActorUnavailable = type("ToolAssetServiceActorUnavailable", (RuntimeError,), {})
        class Scope:
            def __init__(scope, actor): scope.actor = actor
            def __enter__(scope): scope.previous = fake.session.user; fake.set_user(scope.actor)
            def __exit__(scope, *_args): fake.set_user(scope.previous)
        validation.tool_asset_service_actor_scope = Scope
        sys.modules[validation.__name__] = validation
        repository = types.ModuleType("npi_integration.tool_asset_request.worker_repository")
        repository.FrappeToolAssetWorkerRepository = Repository
        repository.ToolAssetWorkerFinalFailure = type("ToolAssetWorkerFinalFailure", (RuntimeError,), {"__init__": lambda self, code: (RuntimeError.__init__(self, code), setattr(self, "code", code))[-1]})
        repository.ToolAssetWorkerOutcome = object
        sys.modules[repository.__name__] = repository
        self.worker = importlib.import_module("npi_integration.tool_asset_request.worker")
        self.repo = Repository(self)
        self.adapter = lambda value: (self.events.append("adapter"), response(value))[1]
        self.registry = ToolAssetAdapterRegistry((ToolAssetAdapterRegistration(self.repo.profile.adapter_resolver, self.repo.profile.target_mode, ToolAssetExecutionOperation.CREATE, self.adapter),))

    def tearDown(self):
        for name, value in self.saved_modules.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value

    def test_claim_and_boundary_are_committed_before_dispatch(self):
        outcome = self.worker._execute_worker(outbox_event_id=UUID(int=1), repository=self.repo, profile_resolver=lambda *a: self.repo.profile, registry_resolver=lambda: self.registry, clock=lambda: NOW)
        self.assertIsNotNone(outcome)
        self.assertLess(self.events.index("claim"), self.events.index("commit"))
        self.assertLess(self.events.index("boundary"), self.events.index("adapter"))
        self.assertGreaterEqual(self.events[:self.events.index("adapter")].count("commit"), 2)
        self.assertEqual(self.events[-1], "user:requester@example.invalid")

    def test_recovered_after_boundary_never_redispatches(self):
        self.repo.claim_value.recovered_after_adapter_boundary = True
        self.worker._execute_worker(outbox_event_id=UUID(int=1), repository=self.repo, profile_resolver=lambda *a: self.repo.profile, registry_resolver=lambda: self.registry, clock=lambda: NOW)
        self.assertNotIn("adapter", self.events)
        self.assertIn("seal", self.events)

    def test_live_claim_is_not_claimed_and_never_dispatches(self):
        self.repo.claimed = False
        self.assertIsNone(self.worker._execute_worker(outbox_event_id=UUID(int=1), repository=self.repo, profile_resolver=lambda *a: self.repo.profile, registry_resolver=lambda: self.registry, clock=lambda: NOW))
        self.assertNotIn("adapter", self.events)


if __name__ == "__main__":
    unittest.main()
