from __future__ import annotations

import ast
import copy
import importlib.util
import inspect
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_production_transition_runtime.py"
SHELL = ROOT / "scripts" / "verify-frappe-runtime.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
FIXTURE_RUN_ID = "0123456789abcdef0123456789abcdef"
HASH_A = "a" * 64


def load_verifier():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    module_names = (
        "verify_document_runtime",
        "verify_readiness_runtime",
        "verify_trial_runtime",
        "verify_tooling_runtime",
        "verify_tooling_engineering_controls_runtime",
        "verify_production_transition_runtime_contract",
    )
    saved = {name: sys.modules.pop(name, None) for name in module_names}
    spec = importlib.util.spec_from_file_location(
        "verify_production_transition_runtime_contract",
        VERIFIER,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Production transition verifier cannot be imported")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        with patch.dict(
            os.environ,
            {"NPI_DOCUMENT_RUNTIME_RUN_ID": FIXTURE_RUN_ID},
            clear=False,
        ):
            spec.loader.exec_module(module)
    finally:
        for name in module_names:
            sys.modules.pop(name, None)
        for name, value in saved.items():
            if value is not None:
                sys.modules[name] = value
    return module


class Phase7ProductionTransitionRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_verifier()
        cls.source = VERIFIER.read_text(encoding="utf-8")
        cls.shell = SHELL.read_text(encoding="utf-8")
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_fixture_namespace_and_all_eleven_paths_are_fixed(self) -> None:
        self.assertEqual(self.module.FIXTURE_RUN_ID, FIXTURE_RUN_ID)
        self.assertEqual(self.module.SITE_NAME, "npi.localhost")
        self.assertEqual(self.module.TENANT_ID, "runtime-tenant")
        self.assertEqual(
            self.module.ACKNOWLEDGEMENT_USER,
            self.module.document_runtime.BASELINE_USER,
        )
        self.assertNotEqual(self.module.ACTOR_USER, self.module.ACKNOWLEDGEMENT_USER)
        self.assertEqual(
            self.module.policy_path(),
            "/api/npi/v1/production-transition/policies",
        )
        self.assertEqual(
            self.module.policy_path("policy-id", 2),
            "/api/npi/v1/production-transition/policies/policy-id/versions/2",
        )
        self.assertEqual(
            self.module.policy_path("policy-id", 2, publish=True),
            "/api/npi/v1/production-transition/policies/policy-id/versions/2:publish",
        )
        self.assertEqual(
            self.module.policy_path("policy-id", next_version=True),
            "/api/npi/v1/production-transition/policies/policy-id/versions",
        )
        self.assertEqual(
            self.module.workspace_path("project-id"),
            "/api/npi/v1/projects/project-id/production-transition",
        )
        self.assertEqual(
            self.module.handover_path("project-id", "handover-id", 3),
            "/api/npi/v1/projects/project-id/production-handover/handover-id/revisions/3/acknowledgements",
        )
        self.assertEqual(
            self.module.observation_path("project-id", "observation-id"),
            "/api/npi/v1/projects/project-id/observation-periods/observation-id/revisions",
        )
        route_source = inspect.getsource(self.module.route_disable_probe)
        self.assertIn('return {"routeCount": 11', route_source)

    def test_policy_and_provider_orders_are_intentionally_distinct(self) -> None:
        self.assertEqual(
            self.module.POLICY_PROVIDER_ORDER,
            (
                "actual_sop",
                "customer_complaint",
                "first_batch_yield",
                "production_cycle_time",
                "tooling_stability",
            ),
        )
        self.assertEqual(
            self.module.PROVIDER_RESPONSE_ORDER,
            (
                "actual_sop",
                "first_batch_yield",
                "customer_complaint",
                "production_cycle_time",
                "tooling_stability",
            ),
        )
        self.assertNotEqual(
            self.module.POLICY_PROVIDER_ORDER,
            self.module.PROVIDER_RESPONSE_ORDER,
        )

    def test_policy_payload_freezes_nine_sources_and_two_technical_slots(self) -> None:
        context = {
            "projectGlobalId": "00000000-0000-4000-8000-000000000001",
            "projectType": "new_tool",
        }
        payload = self.module.create_policy_payload(context)
        definition = payload["definition"]
        self.assertEqual(payload["title"], self.module.POLICY_SENTINEL)
        self.assertEqual(
            [value["providerKind"] for value in definition["observationSourceRules"]],
            list(self.module.POLICY_PROVIDER_ORDER),
        )
        self.assertEqual(len(definition["handoverRequirements"]), 9)
        self.assertEqual(
            [value["acceptedSourceKinds"][0] for value in definition["handoverRequirements"]],
            list(self.module.SOURCE_KINDS),
        )
        self.assertEqual(
            [value["key"] for value in definition["acknowledgementSlots"]],
            ["sender", "receiver"],
        )
        self.assertTrue(
            all(
                value["allowedProjectRoleKeys"]
                == [self.module.document_runtime.BASELINE_ROLE_KEY]
                for value in definition["acknowledgementSlots"]
            )
        )

    def test_handover_request_never_accepts_server_hash_or_manifest_role(self) -> None:
        context = self._context()
        sources = self._sources()
        content = self.module.handover_content(
            context,
            self._policy(),
            sources,
            version=1,
        )
        self.assertEqual(len(content["slotAssignments"]), 2)
        self.assertEqual(
            {value["memberGlobalId"] for value in content["slotAssignments"]},
            {context["memberGlobalId"]},
        )
        self.assertEqual(
            {value["roleAssignmentGlobalId"] for value in content["slotAssignments"]},
            {context["roleAssignmentGlobalId"]},
        )
        self.assertEqual(len(content["manifestSources"]), 9)
        self.assertTrue(
            all(
                set(value)
                == {"requirementKey", "kind", "globalId", "expectedVersion"}
                and "snapshotHash" not in value
                and "role" not in value
                for value in content["manifestSources"]
            )
        )

    def test_observation_request_reuses_one_exact_tuple_without_manifest_fields(self) -> None:
        current = {
            "globalId": "00000000-0000-4000-8000-000000000101",
            "snapshotHash": HASH_A,
        }
        source = self._sources()[0]
        payload = self.module.observation_revision_payload(current, source)
        self.assertEqual(payload["contextSources"], payload["retrospectiveSources"])
        self.assertEqual(
            set(payload["contextSources"][0]),
            {"kind", "globalId", "expectedVersion"},
        )
        self.assertNotIn("snapshotHash", payload["contextSources"][0])
        self.assertNotIn("requirementKey", payload["contextSources"][0])
        payload["contextSources"][0]["expectedVersion"] = 99
        self.assertEqual(payload["retrospectiveSources"][0]["expectedVersion"], 1)

    def test_package_verifier_requires_server_injected_roles_hashes_and_all_work(self) -> None:
        context = self._context()
        sources = self._sources()
        package = self._package(context, sources)
        self.module.verify_package(
            package,
            context,
            sources,
            version=1,
            predecessor=None,
        )
        drifted = copy.deepcopy(package)
        drifted["manifest"][0]["snapshotHash"] = "b" * 64
        with self.assertRaisesRegex(RuntimeError, "manifest role/hash"):
            self.module.verify_package(
                drifted,
                context,
                sources,
                version=1,
                predecessor=None,
            )
        drifted = copy.deepcopy(package)
        drifted["unresolvedActions"] = []
        with self.assertRaisesRegex(RuntimeError, "frozen collection"):
            self.module.verify_package(
                drifted,
                context,
                sources,
                version=1,
                predecessor=None,
            )

    def test_observation_verifier_requires_identity_free_canonical_providers(self) -> None:
        handover = {
            "globalId": "00000000-0000-4000-8000-000000000201",
            "handoverVersion": 1,
            "snapshotHash": HASH_A,
        }
        value = {
            "globalId": "00000000-0000-4000-8000-000000000202",
            "observationGlobalId": "00000000-0000-4000-8000-000000000203",
            "observationVersion": 1,
            "snapshotHash": HASH_A,
            "predecessorGlobalId": None,
            "predecessorSnapshotHash": None,
            "handoverPackageRef": {
                "globalId": handover["globalId"],
                "version": 1,
                "snapshotHash": HASH_A,
            },
            "observedStartDate": None,
            "observedEndDate": None,
            "observationState": "not_evaluable",
            "technicalDisposition": "not_evaluable",
            "authorityBoundary": "technical_observation_only",
            "providers": self._providers(),
        }
        self.module.verify_observation(
            value,
            version=1,
            handover=handover,
            predecessor=None,
        )
        drifted = copy.deepcopy(value)
        drifted["providers"][0]["sourceIdentity"] = "external-record"
        with self.assertRaisesRegex(RuntimeError, "exposed identity"):
            self.module.verify_observation(
                drifted,
                version=1,
                handover=handover,
                predecessor=None,
            )

    def test_source_context_re_resolves_all_nine_and_rejects_p705_file_tuple(self) -> None:
        source = inspect.getsource(self.module.production_transition_source_context)
        for marker in (
            "readiness_runtime.readiness_source_context",
            "SOURCE_LOADER_SEAMS",
            "resolved.source_version",
            "resolved.snapshot_hash",
            '"trial_defect" if kind_text == "trial_defect_revision"',
            'kind_text == "file_revision"',
            'tuple_differences == [True]',
            '"p705FileTupleRejected": True',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        self.assertEqual(len(self.module.SOURCE_KINDS), 9)
        self.assertIn("trial_defect_revision", self.module.SOURCE_KINDS)
        self.assertNotIn("trial_defect", self.module.SOURCE_KINDS)

    def test_all_nonterminal_preflight_compares_exact_db_identity_and_truth(self) -> None:
        source = inspect.getsource(self.module.production_transition_fixture_context)
        for marker in (
            '"state_terminal": 0',
            "limit_page_length=10_001",
            'allowed_kinds = {"action", "decision_request", "issue", "risk"}',
            "raw_ids == tuple(str(value.global_id) for value in unresolved)",
            "len(set(raw_ids)) == len(raw_ids)",
            "row.owner_user_id",
            "row.due_at",
            "getdate(row.due_at)",
            "row.optimistic_version",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

    def test_acknowledgement_actor_is_exact_member_and_manager_proxy_is_denied(self) -> None:
        fixture_source = inspect.getsource(
            self.module.production_transition_fixture_context
        )
        fresh_source = inspect.getsource(self.module.run_fresh)
        self.assertIn("ACKNOWLEDGEMENT_USER.casefold()", fixture_source)
        self.assertIn('"System Manager" not in user_roles', fixture_source)
        self.assertIn('code="PERMISSION_DENIED"', fresh_source)
        self.assertIn('status=403', fresh_source)
        self.assertIn("acknowledgement_actor,", fresh_source)
        self.assertIn("technicalSlotAcknowledgements", fresh_source)

    def test_project_first_probes_use_real_and_absent_secondary_ids_with_full_digest(self) -> None:
        source = inspect.getsource(self.module.verify_project_first_idor)
        for marker in (
            "target_package[\"handoverGlobalId\"]",
            "target_observation[\"observationGlobalId\"]",
            "handover-revise",
            "handover-ack",
            "observation-revise",
            "ABSENT_ID",
            "PRODUCTION_TRANSITION_UNAVAILABLE",
            "before_context == after_context",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

    def test_zero_effect_snapshot_covers_project_gate_readiness_integration_and_global_p706(self) -> None:
        source = inspect.getsource(
            self.module.production_transition_persistence_context
        )
        for marker in (
            "NPI Project Role Assignment",
            "NPI Project Substitution",
            "NPI Project RACI Assignment",
            "NPI Gate Evidence Reference",
            "NPI Gate Review Cycle",
            "NPI Gate Review Record",
            "NPI Gate Review Exception",
            "NPI Gate Decision Snapshot",
            "NPI Gate Review Event",
            "NPI Gate Review Idempotency",
            "NPI Baseline Gate Dependency",
            "NPI Project Control Binding",
            "NPI Readiness Instance Revision",
            '"module": "NPI Integration"',
            '"audit:non-p706"',
            '"transitionGlobalSnapshot"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

    def test_exact_cardinality_and_cross_process_replay_are_sealed(self) -> None:
        fresh = inspect.getsource(self.module.run_fresh)
        replay = inspect.getsource(self.module.run_replay)
        for marker in (
            '"NPI Production Transition Policy": 1',
            '"NPI Handover Package Revision": 2',
            '"NPI Handover Acknowledgement": 4',
            '"NPI Observation Period Revision": 2',
            '"NPI Production Transition Command Idempotency": 11',
            '"audit:production_handover.acknowledge": 4',
            '"audit:production_transition_policy.next_version": 0',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, fresh)
        self.assertEqual(replay.count("replayed=True"), 9)
        self.assertEqual(replay.count('for slot in ("sender", "receiver")'), 2)
        self.assertIn("before_persistence == after_persistence", replay)
        self.assertIn("transition_workspace(actor, base_url, project_id) == workspace", replay)

    def test_conflict_stale_and_wrong_source_paths_use_digest_rollback_guard(self) -> None:
        fresh = inspect.getsource(self.module.run_fresh)
        guard = inspect.getsource(self.module._expect_problem_without_write)
        for marker in (
            "PRODUCTION_TRANSITION_IDEMPOTENCY_CONFLICT",
            "PRODUCTION_TRANSITION_POLICY_IMMUTABLE",
            "STALE_HANDOVER_KEY",
            "STALE_ACK_KEY",
            "STALE_OBSERVATION_KEY",
            "ROLLBACK_OBSERVATION_KEY",
            'wrong_source["expectedVersion"]',
            'code="VALIDATION_FAILED"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, fresh)
        self.assertIn("production_transition_persistence_context", guard)
        self.assertIn("before_context == after_context", guard)
        self.assertIn("transition_counts", guard)

    def test_controlled_site_persisted_redaction_is_recursive_and_keeps_sealed_scope(self) -> None:
        fixture = inspect.getsource(
            self.module.verify_production_transition_persisted_redaction
        )
        recursive = inspect.getsource(self.module._assert_persisted_value_redacted)
        for marker in (
            "NPI Production Transition Policy",
            "NPI Production Transition Policy Version",
            "NPI Handover Package Revision",
            "NPI Handover Acknowledgement",
            "NPI Observation Period Revision",
            "NPI Production Transition Command Idempotency",
            "response_payload",
            "int(document.sealed) == 1",
            "NPI Audit Event",
            "audit.input_summary",
            '"sensitivePersisted": False',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, fixture)
        for marker in ("/private/files/", "fileurl", "password", "secret", "token"):
            self.assertIn(marker, recursive)
        self.module._assert_persisted_value_redacted(
            {
                "title": self.module.POLICY_SENTINEL,
                "nested": [{"value": self.module.HANDOVER_SENTINEL}],
            },
            "allowed business sentinels",
        )
        for value in (
            {"fileUrl": "/safe-looking"},
            {"nested": [{"value": "/private/files/controlled.pdf"}]},
            {"password": "redacted"},
            {"value": "secret"},
            {"apiToken": "redacted"},
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, "sensitive"):
                    self.module._assert_persisted_value_redacted(value, "bad")
        self.assertIn(
            "verify_production_transition_persisted_redaction",
            self.module.BENCH_FIXTURES,
        )
        self.assertIn(
            "verify_production_transition_persisted_redaction",
            inspect.getsource(self.module.run_fresh),
        )

    def test_generic_create_update_delete_are_denied_for_all_six_doctypes(self) -> None:
        rows_source = inspect.getsource(self.module._generic_rows)
        guard_source = inspect.getsource(self.module.verify_generic_mutation_denial)
        for doctype in self.module.TRANSITION_DOCTYPES:
            self.assertIn(doctype, rows_source)
        self.assertIn("create_resource(", guard_source)
        self.assertIn("update_resource(", guard_source)
        self.assertIn("delete_resource(", guard_source)
        self.assertEqual(guard_source.count("status in {403, 417}"), 3)
        self.assertIn("before_context == after_context", guard_source)

    def test_verifier_uses_only_fixed_disposable_bench_and_no_network_provider(self) -> None:
        for marker in (
            'BENCH_PATH = ROOT / "tmp" / "frappe-bench"',
            "BENCH_PATH.resolve() == BENCH_PATH",
            "document_runtime._validated_runtime_site()",
            "validate_local_fixture_inputs",
            "NPI_DOCUMENT_RUNTIME_RUN_ID",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)
        folded = self.source.casefold()
        self.assertNotIn("core." + "whjichen.cn", folded)
        self.assertNotIn("requests.post", folded)
        self.assertNotIn("erpnext_url", folded)

    def test_cli_shell_and_workflow_wire_fresh_disable_recover_replay_and_cleanup(self) -> None:
        tree = ast.parse(self.source)
        self.assertIsInstance(tree, ast.Module)
        for marker in (
            'parser.add_argument("--base-url")',
            'parser.add_argument("--bench-fixture"',
            'parser.add_argument("--fixture-kwargs")',
            'parser.add_argument("--route-disable-probe"',
            'parser.add_argument("--replay-only"',
        ):
            self.assertIn(marker, self.source)
        for marker in (
            "run_production_transition_runtime_verifier fresh",
            "run_production_transition_route_probe disabled",
            "run_production_transition_route_probe recovered",
            "run_production_transition_runtime_verifier replay-only",
            "set_production_transition_route_switch None absent",
            "P706-POLICY-SENTINEL",
            "P706-HANDOVER-SENTINEL",
            "P706-OBSERVATION-SENTINEL",
            '"/private/files/"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.shell)
        for marker in (
            "tests.test_phase7_production_transition_runtime_verifier",
            "P7-06 Production transition",
            "scope=p5-01-through-p7-06",
            "predecessor_scope=p5-01-through-p7-05",
            "timeout-minutes: 45",
            "bash scripts/verify-frappe-runtime.sh --trial-only",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.workflow)

    @staticmethod
    def _context() -> dict[str, object]:
        return {
            "projectGlobalId": "00000000-0000-4000-8000-000000000001",
            "projectOptimisticVersion": 7,
            "projectType": "new_tool",
            "memberGlobalId": "00000000-0000-4000-8000-000000000002",
            "memberOptimisticVersion": 2,
            "roleAssignmentGlobalId": "00000000-0000-4000-8000-000000000003",
            "roleOptimisticVersion": 3,
            "unresolvedActions": [
                {
                    "globalId": "00000000-0000-4000-8000-000000000004",
                    "sourceVersion": 1,
                    "snapshotHash": HASH_A,
                    "kind": "action",
                    "state": "open",
                    "ownerUserId": "owner@example.invalid",
                    "dueDate": "2026-08-31",
                }
            ],
        }

    @staticmethod
    def _policy() -> dict[str, object]:
        return {
            "policyGlobalId": "00000000-0000-4000-8000-000000000010",
            "policyVersion": 1,
            "snapshotHash": HASH_A,
        }

    @classmethod
    def _sources(cls) -> list[dict[str, object]]:
        return [
            {
                "kind": kind,
                "globalId": f"00000000-0000-4000-8000-{index:012d}",
                "expectedVersion": 1,
                "snapshotHash": HASH_A,
            }
            for index, kind in enumerate(cls.module.SOURCE_KINDS, start=20)
        ]

    @classmethod
    def _package(
        cls,
        context: dict[str, object],
        sources: list[dict[str, object]],
    ) -> dict[str, object]:
        slots = []
        for slot, group, direction in (
            ("sender", "npi_sender", "sender"),
            ("receiver", "production_receiver", "receiver"),
        ):
            slots.append(
                {
                    "slotKey": slot,
                    "groupKey": group,
                    "direction": direction,
                    "member": {
                        "globalId": context["memberGlobalId"],
                        "userId": cls.module.ACKNOWLEDGEMENT_USER,
                        "optimisticVersion": context["memberOptimisticVersion"],
                    },
                    "role": {
                        "globalId": context["roleAssignmentGlobalId"],
                        "roleKey": cls.module.document_runtime.BASELINE_ROLE_KEY,
                        "optimisticVersion": context["roleOptimisticVersion"],
                    },
                }
            )
        return {
            "globalId": "00000000-0000-4000-8000-000000000050",
            "handoverGlobalId": "00000000-0000-4000-8000-000000000051",
            "handoverVersion": 1,
            "snapshotHash": HASH_A,
            "predecessorGlobalId": None,
            "predecessorSnapshotHash": None,
            "slots": slots,
            "manifest": [
                {
                    "requirementKey": f"requirement_{source['kind']}",
                    "kind": source["kind"],
                    "globalId": source["globalId"],
                    "sourceVersion": source["expectedVersion"],
                    "snapshotHash": source["snapshotHash"],
                    "role": f"controlled_{source['kind']}",
                }
                for source in sources
            ],
            "unresolvedActions": copy.deepcopy(context["unresolvedActions"]),
        }

    @classmethod
    def _providers(cls) -> list[dict[str, object]]:
        return [
            {
                "kind": kind,
                "state": "unavailable",
                "reasonCode": cls.module.PROVIDER_REASON_CODES[kind],
                "sourceIdentity": None,
                "observedAt": None,
                "value": None,
                "unit": None,
            }
            for kind in cls.module.PROVIDER_RESPONSE_ORDER
        ]


if __name__ == "__main__":
    unittest.main()
