from __future__ import annotations

import ast
import copy
import importlib.util
import os
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_readiness_runtime.py"
SHELL = ROOT / "scripts" / "verify-frappe-runtime.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
FIXTURE_RUN_ID = "0123456789abcdef0123456789abcdef"


def load_verifier():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    module_names = (
        "verify_document_runtime",
        "verify_trial_runtime",
        "verify_tooling_runtime",
        "verify_readiness_runtime_contract",
    )
    saved = {name: sys.modules.pop(name, None) for name in module_names}
    spec = importlib.util.spec_from_file_location(
        "verify_readiness_runtime_contract",
        VERIFIER,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Readiness runtime verifier cannot be imported")
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


class Phase7ReadinessRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_verifier()
        cls.source = VERIFIER.read_text(encoding="utf-8")
        cls.shell = SHELL.read_text(encoding="utf-8")
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_fixture_namespace_and_paths_are_fixed_and_project_scoped(self) -> None:
        self.assertEqual(self.module.FIXTURE_RUN_ID, FIXTURE_RUN_ID)
        self.assertEqual(self.module.TENANT_ID, "runtime-tenant")
        self.assertEqual(self.module.SITE_NAME, "npi.localhost")
        self.assertTrue(self.module.ACTOR_USER.endswith("@example.invalid"))
        self.assertTrue(self.module.UNRELATED_USER.endswith("@example.invalid"))
        self.assertNotEqual(self.module.ACTOR_USER, self.module.UNRELATED_USER)
        self.assertEqual(
            self.module.template_path(),
            "/api/npi/v1/npi-readiness/templates",
        )
        self.assertEqual(
            self.module.template_path("template-id", 2),
            "/api/npi/v1/npi-readiness/templates/template-id/versions/2",
        )
        self.assertEqual(
            self.module.template_path("template-id", 2, publish=True),
            "/api/npi/v1/npi-readiness/templates/template-id/versions/2:publish",
        )
        self.assertEqual(
            self.module.readiness_path("project-id"),
            "/api/npi/v1/projects/project-id/npi-readiness",
        )
        self.assertEqual(
            self.module.readiness_path("project-id", "instance-id"),
            "/api/npi/v1/projects/project-id/npi-readiness/instance-id/revisions",
        )

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
        self.assertNotIn("core." + "whjichen.cn", self.source)
        self.assertNotIn("requests.post", self.source)
        self.assertNotIn("erpnext_url", self.source.casefold())

    def test_exact_source_catalog_has_sixteen_internal_and_five_offline_external_kinds(
        self,
    ) -> None:
        self.assertEqual(
            set(self.module.INTERNAL_SOURCE_KINDS),
            {
                "project",
                "domain_work_item",
                "released_document",
                "release_baseline",
                "file_revision",
                "tooling_capacity_scenario",
                "trial_input_lock",
                "trial_actual",
                "trial_sample",
                "trial_cavity_result",
                "trial_defect",
                "trial_defect_verification",
                "trial_comparison",
                "trial_review_reference",
                "trial_conclusion",
                "controlled_quality_result",
            },
        )
        self.assertEqual(len(self.module.INTERNAL_SOURCE_KINDS), 16)
        self.assertEqual(
            set(self.module.EXTERNAL_SOURCE_KINDS),
            {
                "erp_material_specification",
                "erp_quality_result",
                "erp_run_at_rate",
                "erp_hr_qualification",
                "erp_supplier_execution",
            },
        )
        self.assertEqual(len(self.module.EXTERNAL_SOURCE_KINDS), 5)
        self.assertEqual(
            set(self.module.EXTERNAL_REASON_CODES),
            set(self.module.EXTERNAL_SOURCE_KINDS),
        )

    def test_capacity_source_payload_is_an_independent_two_line_v1_scenario(
        self,
    ) -> None:
        context = self._capacity_source_context()
        profile = {
            "globalId": "00000000-0000-4000-8000-000000000220",
            "snapshotHash": "a" * 64,
        }
        retained_context = copy.deepcopy(context)
        retained_profile = copy.deepcopy(profile)

        payload = self.module.capacity_source_payload(context, profile)

        self.assertEqual(context, retained_context)
        self.assertEqual(profile, retained_profile)
        self.assertEqual(payload.get("targetMonthlyAssemblyUnits"), "25000.0")
        self.assertNotIn("scenarioGlobalId", payload)
        self.assertNotIn("expectedVersion", payload)
        self.assertEqual(len(payload.get("lines", [])), 2)
        self.assertEqual(
            [line.get("applicabilityGlobalId") for line in payload["lines"]],
            [
                value["globalId"]
                for value in retained_context["applicability"]
            ],
        )

        payload["lines"][0]["selectedToolingSetGlobalIds"].append(
            "00000000-0000-4000-8000-000000000299"
        )
        self.assertEqual(context, retained_context)
        self.assertEqual(profile, retained_profile)

        for applicability in (
            retained_context["applicability"][:1],
            retained_context["applicability"]
            + [copy.deepcopy(retained_context["applicability"][0])],
        ):
            with self.subTest(applicability_count=len(applicability)):
                drifted = copy.deepcopy(retained_context)
                drifted["applicability"] = applicability
                with self.assertRaisesRegex(RuntimeError, "two retained applicability"):
                    self.module.capacity_source_payload(drifted, profile)

    def test_current_controlled_reference_requires_the_exact_current_round_target(
        self,
    ) -> None:
        workspace = self._controlled_reference_workspace()
        expected = workspace["reviewReferenceRevisions"][0]
        self.assertEqual(
            self.module.current_controlled_reference(workspace),
            expected,
        )

        mutations = (
            lambda value: value["trialRound"].__setitem__(
                "optimisticVersion", 8
            ),
            lambda value: value["trialRound"].__setitem__(
                "snapshotHash", "9" * 64
            ),
            lambda value: value["comparisonSnapshots"][0]["sources"][-1].__setitem__(
                "trialRoundOptimisticVersion", 8
            ),
            lambda value: value["comparisonSnapshots"][0]["sources"][-1].__setitem__(
                "trialRoundSnapshotHash", "9" * 64
            ),
            lambda value: value["reviewReferenceRevisions"][0][
                "comparisonSnapshot"
            ].__setitem__("snapshotHash", "8" * 64),
            lambda value: value["reviewReferenceRevisions"][0].__setitem__(
                "referenceKind", "internal_sample_review"
            ),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                drifted = copy.deepcopy(workspace)
                mutate(drifted)
                self.assertIsNone(
                    self.module.current_controlled_reference(drifted)
                )

    def test_source_preparation_keys_are_exact_bounded_and_non_sensitive(self) -> None:
        expected = (
            f"p7-05-runtime-{FIXTURE_RUN_ID}-capacity-source",
            f"p7-05-runtime-{FIXTURE_RUN_ID}-reference-reopen",
            f"p7-05-runtime-{FIXTURE_RUN_ID}-reference-comparison",
            f"p7-05-runtime-{FIXTURE_RUN_ID}-reference-create",
        )
        self.assertEqual(
            self.module.SOURCE_PREPARATION_IDEMPOTENCY_KEYS,
            expected,
        )
        self.assertEqual(
            expected,
            (
                self.module.CAPACITY_SOURCE_PREP_KEY,
                self.module.TRIAL_REFERENCE_REOPEN_KEY,
                self.module.TRIAL_REFERENCE_COMPARISON_KEY,
                self.module.TRIAL_REFERENCE_CREATE_KEY,
            ),
        )
        self.assertEqual(len(set(expected)), 4)
        for value in (
            *expected,
            self.module.CAPACITY_SOURCE_SENTINEL,
            self.module.TRIAL_REFERENCE_SENTINEL,
        ):
            with self.subTest(value=value):
                self.assertLessEqual(len(value), 128)
                self.assertIsNotNone(re.fullmatch(r"[A-Za-z0-9-]+", value))
                folded = value.casefold()
                for forbidden in (
                    "password",
                    "secret",
                    "token",
                    "cookie",
                    "csrf",
                    "private",
                    "/",
                    "\\",
                ):
                    self.assertNotIn(forbidden, folded)

    def test_source_preparation_precedes_the_readiness_baseline(self) -> None:
        tree = ast.parse(self.source)
        run_fresh = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "run_fresh"
        )
        source_preparation_calls = [
            node
            for node in ast.walk(run_fresh)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "prepare_readiness_source_fixtures"
        ]
        baseline_calls = [
            node
            for node in ast.walk(run_fresh)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "run_bench_fixture"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "readiness_persistence_context"
        ]

        self.assertEqual(len(source_preparation_calls), 1)
        self.assertGreaterEqual(len(baseline_calls), 3)
        ordered_baselines = sorted(baseline_calls, key=lambda node: node.lineno)
        self.assertLess(
            ordered_baselines[0].lineno,
            source_preparation_calls[0].lineno,
        )
        self.assertLess(
            source_preparation_calls[0].lineno,
            ordered_baselines[1].lineno,
        )

    def test_source_fixture_and_readiness_effect_windows_are_reported_separately(
        self,
    ) -> None:
        for marker in (
            "verify_source_preparation_scope",
            '"fixtureCapacityCommandCount": 1',
            '"fixtureCapacityScenarioCreated": True',
            '"fixtureAuditEventCount": 4',
            '"fixtureIntegrationTrafficCreated": False',
            '"fixtureSourcePreparationCommandCount": 4',
            '"fixtureTrialCommandCount": 3',
            '"fixtureTrialHistoryExtended": True',
            '"fixtureTrialRoundReopenedToAnalysis": True',
            '"readinessIntegrationTrafficCreated": False',
            '"readinessGateMutationCreated": False',
            '"readinessTrialMutationCreated": False',
            '"readinessWorkItemMutationCreated": False',
            '"readinessToolingMutationCreated": False',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)
        for misleading in (
            '"integrationTrafficCreated": False',
            '"toolingMutationCreated": False',
        ):
            with self.subTest(misleading=misleading):
                self.assertNotIn(misleading, self.source)

    def test_source_fixture_scope_rejects_undeclared_mutation(self) -> None:
        stable = {
            "customerReferenceKeys": ["ERPNEXT:CUSTOMER-001"],
            "fixtureRunId": FIXTURE_RUN_ID,
            "gateGlobalId": "00000000-0000-4000-8000-000000000240",
            "gateKey": "G6",
            "gateOptimisticVersion": 1,
            "memberGlobalId": "00000000-0000-4000-8000-000000000241",
            "memberOptimisticVersion": 1,
            "projectGlobalId": "00000000-0000-4000-8000-000000000242",
            "projectOptimisticVersion": 1,
            "projectType": "new_mold",
            "secondProjectGlobalId": "00000000-0000-4000-8000-000000000243",
        }
        allowed_deltas = {
            "tooling:NPI Tooling Capacity Scenario Revision": 1,
            "tooling:NPI Tooling Command Idempotency": 1,
            "trial:NPI Trial Round": 0,
            "trial:NPI Trial Round Lifecycle Event": 1,
            "trial:NPI Trial Command Idempotency": 3,
            "trial:NPI Trial Round Comparison Snapshot": 1,
            "trial:NPI Trial Review Reference Revision": 1,
            "trial:NPI Trial Conclusion Revision": 1,
            "NPI Outbox Message": 0,
            "NPI Inbox Message": 0,
            "project:NPI Engineering Project": 0,
        }
        before_counts = {key: 10 for key in allowed_deltas}
        after_counts = {
            key: before_counts[key] + delta for key, delta in allowed_deltas.items()
        }
        before_digests = {key: f"before-{index}" for index, key in enumerate(allowed_deltas)}
        after_digests = {
            key: (
                f"after-{index}"
                if key
                in {
                    "tooling:NPI Tooling Capacity Scenario Revision",
                    "tooling:NPI Tooling Command Idempotency",
                    "trial:NPI Trial Round",
                    "trial:NPI Trial Round Lifecycle Event",
                    "trial:NPI Trial Command Idempotency",
                    "trial:NPI Trial Round Comparison Snapshot",
                    "trial:NPI Trial Review Reference Revision",
                    "trial:NPI Trial Conclusion Revision",
                }
                else before_digests[key]
            )
            for index, key in enumerate(allowed_deltas)
        }
        audit_keys = (
            "toolingCapacity",
            "trialComparison",
            "trialReference",
            "trialReopen",
        )
        before = {
            **stable,
            "downstreamCounts": before_counts,
            "downstreamDigests": before_digests,
            "sourcePreparationAuditCounts": {key: 2 for key in audit_keys},
            "sourcePreparationAuditDigests": {
                key: f"audit-before-{key}" for key in audit_keys
            },
        }
        after = {
            **stable,
            "downstreamCounts": after_counts,
            "downstreamDigests": after_digests,
            "sourcePreparationAuditCounts": {key: 3 for key in audit_keys},
            "sourcePreparationAuditDigests": {
                key: f"audit-after-{key}" for key in audit_keys
            },
        }

        result = self.module.verify_source_preparation_scope(before, after)
        self.assertEqual(result["fixtureSourcePreparationCommandCount"], 4)
        self.assertFalse(result["fixtureIntegrationTrafficCreated"])

        tampered = copy.deepcopy(after)
        tampered["downstreamCounts"]["NPI Outbox Message"] += 1
        with self.assertRaisesRegex(RuntimeError, "unauthorized collection"):
            self.module.verify_source_preparation_scope(before, tampered)
        tampered = copy.deepcopy(after)
        tampered["sourcePreparationAuditCounts"]["trialReopen"] += 1
        with self.assertRaisesRegex(RuntimeError, "audit history"):
            self.module.verify_source_preparation_scope(before, tampered)
        tampered = copy.deepcopy(after)
        tampered["downstreamDigests"]["project:NPI Engineering Project"] = (
            "unexpected"
        )
        with self.assertRaisesRegex(RuntimeError, "rewrote adjacent truth"):
            self.module.verify_source_preparation_scope(before, tampered)

    def test_template_lifecycle_and_independent_project_instance_are_proved(self) -> None:
        for marker in (
            "template_payload",
            "readiness_source_context",
            "readiness_persistence_context",
            '"NPI Readiness Template"',
            '"NPI Readiness Template Version"',
            '"NPI Readiness Instance Revision"',
            '"publicationState") == "draft"',
            '"publicationState") == "published"',
            "P7-05 published template accepted mutation",
            "templateGlobalId",
            "templateVersion",
            "templateSnapshotHash",
            "instanceGlobalId",
            "instanceVersion",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)

    def test_runtime_proves_exact_sources_and_identity_free_external_unavailability(self) -> None:
        for marker in (
            "verify_external_sources_offline",
            "INTERNAL_SOURCE_KINDS",
            "EXTERNAL_SOURCE_KINDS",
            "EXTERNAL_REASON_CODES",
            "formal ERP projection acquired caller identity",
            '"state") == "unavailable"',
            '"globalId") is None',
            '"sourceVersion") is None',
            '"snapshotHash") is None',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)

    def test_high_score_cannot_hide_p0_failed_or_unavailable_blockers(self) -> None:
        for marker in (
            "9700",
            "high readiness score hid authoritative blockers",
            '"incomplete_p0"',
            '"failed_mandatory_quality"',
            '"required_source_unavailable"',
            '"ready") is False',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)

    def test_high_score_blocker_validation_rejects_tampering(self) -> None:
        revision = self._behavior_revision(version=4, hash_character="d")
        gate = revision["items"][0]["gate"]
        blockers = [
            {
                "code": code,
                "itemKey": item_key,
                "itemGlobalId": self._behavior_item(revision, item_key)["globalId"],
                "gate": gate,
            }
            for code, item_key in (
                ("incomplete_p0", "p0_hold"),
                ("failed_mandatory_quality", "quality_hold"),
                ("required_source_unavailable", "external_hold"),
            )
        ]
        revision["evaluation"] = {
            "formulaVersion": "readiness-score.v1",
            "categoryScores": [
                {
                    "categoryKey": "runtime",
                    "earnedWeight": 97,
                    "applicableWeight": 100,
                    "basisPoints": 9700,
                    "state": "scored",
                }
            ],
            "totalScore": {
                "earnedWeight": 97,
                "applicableWeight": 100,
                "basisPoints": 9700,
                "state": "scored",
            },
            "blockers": blockers,
            "ready": False,
        }
        workspace = {"currentRevision": revision}

        self.module.verify_high_score_blockers(workspace)
        tampered = copy.deepcopy(workspace)
        tampered["currentRevision"]["evaluation"]["blockers"].append(
            copy.deepcopy(blockers[0])
        )
        with self.assertRaisesRegex(RuntimeError, "authoritative blockers"):
            self.module.verify_high_score_blockers(tampered)

    def test_gate_input_drift_is_read_only_and_preserves_all_gate_authority(self) -> None:
        for marker in (
            "readiness_gate_input_context",
            "Gate input drift mutated Gate authority",
            "gateInputHash",
            "dependency",
            "snapshotHash",
            '"NPI Gate Review Cycle"',
            '"NPI Gate Decision"',
            '"NPI Audit Event"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)

    def test_gate_input_drift_validation_preserves_unrelated_dependencies(self) -> None:
        initial_revision = self._behavior_revision(version=1, hash_character="a")
        final_revision = self._behavior_revision(version=4, hash_character="d")
        retained_dependency = {
            "kind": "gate_input_snapshot",
            "globalId": "00000000-0000-4000-8000-000000000099",
            "version": 8,
            "snapshotHash": "9" * 64,
        }
        initial_dependency = {
            "kind": "gate_input_snapshot",
            "globalId": initial_revision["globalId"],
            "version": 1,
            "snapshotHash": initial_revision["snapshotHash"],
        }
        final_dependency = {
            "kind": "gate_input_snapshot",
            "globalId": final_revision["globalId"],
            "version": 4,
            "snapshotHash": final_revision["snapshotHash"],
        }
        blocker = {
            "globalId": self._behavior_item(initial_revision, "p0_hold")["globalId"],
            "version": 1,
            "state": "readiness_incomplete_p0",
            "blocking": True,
            "terminal": False,
        }
        authority = {"digest": "7" * 64, "count": 2}
        initial = {
            "dependencies": [retained_dependency, initial_dependency],
            "blockers": [blocker],
            "gateInputHash": "1" * 64,
            "gateAuthoritySnapshot": authority,
            "gateOptimisticVersion": 8,
            "gateState": "open",
        }
        final = {
            "dependencies": [retained_dependency, final_dependency],
            "blockers": [blocker],
            "gateInputHash": "2" * 64,
            "gateAuthoritySnapshot": authority,
            "gateOptimisticVersion": 8,
            "gateState": "open",
        }

        self.module.verify_gate_input_drift(
            initial,
            final,
            initial_revision,
            final_revision,
        )
        tampered = copy.deepcopy(final)
        tampered["dependencies"].append(initial_dependency)
        with self.assertRaisesRegex(RuntimeError, "Gate input drift"):
            self.module.verify_gate_input_drift(
                initial,
                tampered,
                initial_revision,
                final_revision,
            )

    def test_initialized_instance_validation_rejects_frozen_assignment_drift(self) -> None:
        context = self._behavior_context()
        published = {
            "globalId": "00000000-0000-4000-8000-000000000020",
            "templateVersion": 2,
            "snapshotHash": "2" * 64,
        }
        revision = self._behavior_revision(version=1, hash_character="a")
        revision["project"] = {
            "globalId": context["projectGlobalId"],
            "optimisticVersion": context["projectOptimisticVersion"],
            "projectType": context["projectType"],
            "customerReferenceKeys": context["customerReferenceKeys"],
            "industryKey": self.module.INDUSTRY_KEY,
            "snapshotHash": "3" * 64,
        }
        revision["templateRevision"] = {
            "globalId": published["globalId"],
            "version": published["templateVersion"],
            "snapshotHash": published["snapshotHash"],
        }

        self.module.verify_initialized_instance(revision, published, context)
        tampered = copy.deepcopy(revision)
        self._behavior_item(tampered, "quality_hold")["dueDate"] = "2027-09-03"
        with self.assertRaisesRegex(RuntimeError, "assignment or Gate identity"):
            self.module.verify_initialized_instance(tampered, published, context)

    def test_replay_conflict_rollback_idor_and_guarded_metadata_are_proved(self) -> None:
        for marker in (
            "same-process readiness replay changed sealed response truth",
            "cross-process readiness replay changed sealed truth or cardinality",
            "readiness conflict did not roll back",
            '"READINESS_IDEMPOTENCY_CONFLICT"',
            '"READINESS_UNAVAILABLE"',
            "verify_readiness_runtime_schema",
            "verify_generic_mutation_denial",
            "rejected_update.status in {403, 417}",
            "rejected_delete.status in {403, 417}",
            '"NPI Readiness Command Idempotency"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)

    def test_runtime_has_zero_erp_integration_or_downstream_mutation(self) -> None:
        for marker in (
            '"NPI Outbox Message"',
            '"NPI Inbox Message"',
            "controlled readiness created ERP integration traffic",
            "source fixture preparation created ERP integration traffic",
            '"fixtureIntegrationTrafficCreated": False',
            '"readinessIntegrationTrafficCreated": False',
            '"readinessGateMutationCreated": False',
            '"readinessWorkItemMutationCreated": False',
            '"readinessToolingMutationCreated": False',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)

    def test_project_scoped_digest_uses_each_persisted_field_contract(self) -> None:
        for doctype in (
            "NPI Engineering Part",
            "NPI Engineering Part Revision",
            "NPI Tooling Master",
        ):
            with self.subTest(doctype=doctype):
                self.assertEqual(
                    self.module._project_scope_field(doctype),
                    "originating_project_global_id",
                )
        self.assertEqual(
            self.module._project_scope_field("NPI Engineering Project"),
            "global_id",
        )
        self.assertEqual(
            self.module._project_scope_field("NPI Trial Round"),
            "project_global_id",
        )

    def test_bench_fixture_dispatch_is_closed_and_cli_has_only_frozen_modes(self) -> None:
        for marker in (
            "BENCH_FIXTURES = {",
            "run_bench_fixture",
            "run_local_bench_fixture",
            'parser.add_argument("--replay-only", action="store_true")',
            'parser.add_argument("--route-disable-probe"',
            'choices=("disabled", "recovered")',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)

    def test_shell_orchestrates_absent_switch_recovery_replay_and_cleanup(self) -> None:
        for marker in (
            "readiness_route_switch_state",
            "npi_p7_05_routes_disabled",
            "readiness_route_disable_original_state",
            "readiness_route_disable_config_changed",
            "set_readiness_route_switch true true",
            "run_readiness_runtime_verifier fresh",
            "run_readiness_route_probe disabled",
            "set_readiness_route_switch false false",
            "run_readiness_route_probe recovered",
            "run_readiness_runtime_verifier replay-only",
            "verify_readiness_runtime_log_redaction",
            "restore_readiness_route_switch",
            "Failed to restore the P7-05 route-disable switch to absent.",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.shell)
        self.assertLess(
            self.shell.index("run_trial_runtime_verifier replay-only"),
            self.shell.index("run_readiness_runtime_verifier fresh"),
        )
        self.assertLess(
            self.shell.index("run_readiness_route_probe disabled"),
            self.shell.index("run_readiness_route_probe recovered"),
        )
        self.assertLess(
            self.shell.index("run_readiness_route_probe recovered"),
            self.shell.index("run_readiness_runtime_verifier replay-only"),
        )

    def test_shell_redacts_sensitive_readiness_values_and_private_file_paths(self) -> None:
        self.assertIn(') >>"${runtime_log}" 2>&1 &', self.shell)
        self.assertNotIn(') >"${runtime_log}" 2>&1 &', self.shell)
        for marker in (
            "/private/files/",
            "P7-05 raw readiness value or private path leaked into the runtime log.",
            "Synthetic controlled readiness",
            "P705-CAPACITY-SOURCE-SENTINEL",
            "P705-TRIAL-REFERENCE-SENTINEL",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.shell)
        readiness_suffix = self.shell.split(
            "  readiness_route_disable_config_changed=true", 1
        )[1]
        self.assertNotIn('tail -100 "${runtime_log}"', readiness_suffix)
        self.assertNotIn("  wait_for_runtime_server\n", readiness_suffix)
        self.assertEqual(
            readiness_suffix.count("  wait_for_readiness_runtime_server\n"),
            3,
        )
        readiness_wait = self.shell.split(
            "wait_for_readiness_runtime_server() {", 1
        )[1].split("\n}\n", 1)[0]
        self.assertNotIn("tail", readiness_wait)
        self.assertIn("report_readiness_runtime_failure", readiness_wait)
        self.assertEqual(
            readiness_suffix.count("report_readiness_runtime_failure"),
            5,
        )
        self.assertIn(
            "P7-05 runtime log output withheld because it may contain controlled readiness values or private paths.",
            self.shell,
        )

    def test_workflow_records_exact_p705_scope_and_exact_sha_controlled_preflight(self) -> None:
        preflight_job = self.workflow.split("\n  controlled_preflight:\n", 1)[1].split(
            "\n  document_runtime:\n", 1
        )[0]
        runtime_job = self.workflow.split("\n  document_runtime:\n", 1)[1]
        for marker in (
            "P7-05 NPI readiness",
            "scope=p5-01-through-p7-05",
            "predecessor_scope=p5-01-through-p7-04",
            "bash scripts/verify-frappe-runtime.sh --trial-only",
            "site=npi.localhost",
            "database=npi_one_runtime",
            "runtime_marker=npi-one-local-runtime-disposable-v1",
            "docker compose down --volumes",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, runtime_job)
        for prerequisite in (
            "- repository",
            "- frontend",
            "- secret_scan",
            "- visual",
        ):
            with self.subTest(prerequisite=prerequisite):
                self.assertIn(prerequisite, preflight_job)
        for required_result in (
            "needs.repository.result == 'success'",
            "needs.frontend.result == 'success'",
            "needs.secret_scan.result == 'success'",
            "needs.visual.result == 'success'",
            "needs.repository.result == 'skipped'",
            "needs.frontend.result == 'skipped'",
            "needs.secret_scan.result == 'skipped'",
            "needs.visual.result == 'skipped'",
        ):
            with self.subTest(required_result=required_result):
                self.assertIn(required_result, preflight_job)
        self.assertIn("needs: controlled_preflight", runtime_job)
        self.assertIn("needs.controlled_preflight.result == 'success'", runtime_job)
        for marker in (
            "tests.test_phase7_readiness_runtime_verifier",
            "inputs.gate_mode == 'level_2_controlled'",
            "python scripts/verify_prior_gate.py",
            '--run-id "${{ inputs.ordinary_run_id }}"',
            '--sha "${{ github.sha }}"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.workflow)
        self.assertNotIn("secrets.", runtime_job)
        self.assertNotIn("continue-on-error", runtime_job)
        self.assertNotIn("core." + "whjichen.cn", runtime_job)

    @staticmethod
    def _behavior_context() -> dict[str, object]:
        return {
            "projectGlobalId": "00000000-0000-4000-8000-000000000010",
            "projectOptimisticVersion": 6,
            "projectType": "new_product",
            "customerReferenceKeys": ["ERPNEXT:CUST-001"],
            "memberGlobalId": "00000000-0000-4000-8000-000000000011",
            "memberOptimisticVersion": 3,
            "gateGlobalId": "00000000-0000-4000-8000-000000000012",
            "gateKey": "g2",
            "gateOptimisticVersion": 8,
        }

    @classmethod
    def _behavior_revision(
        cls,
        *,
        version: int,
        hash_character: str,
    ) -> dict[str, object]:
        context = cls._behavior_context()
        gate = {
            "globalId": context["gateGlobalId"],
            "gateKey": context["gateKey"],
            "optimisticVersion": context["gateOptimisticVersion"],
            "snapshotHash": "4" * 64,
        }
        owner = {
            "globalId": context["memberGlobalId"],
            "userId": cls.module.document_runtime.BASELINE_USER,
            "optimisticVersion": context["memberOptimisticVersion"],
        }
        item_specs = (
            ("internal_exact", "P2", "2027-08-01", 31),
            ("p0_hold", "P0", "2027-08-02", 32),
            ("quality_hold", "P1", "2027-08-03", 33),
            ("external_hold", "P1", "2027-08-04", 34),
        )
        items = [
            {
                "globalId": f"00000000-0000-4000-8000-{suffix:012d}",
                "itemVersion": 1,
                "definition": {
                    "key": key,
                    "categoryKey": "runtime",
                    "blockingLevel": level,
                    "gateKey": context["gateKey"],
                },
                "applicable": True,
                "owner": owner,
                "dueDate": due_date,
                "state": "not_started",
                "confirmationValue": None,
                "sources": [],
                "gate": gate,
            }
            for key, level, due_date, suffix in item_specs
        ]
        return {
            "globalId": f"00000000-0000-4000-8000-{version:012d}",
            "instanceGlobalId": "00000000-0000-4000-8000-000000000030",
            "instanceVersion": version,
            "snapshotHash": hash_character * 64,
            "categories": [{"key": "runtime", "title": "Controlled runtime"}],
            "items": items,
        }

    @staticmethod
    def _behavior_item(
        revision: dict[str, object],
        item_key: str,
    ) -> dict[str, object]:
        return next(
            item
            for item in revision["items"]
            if item["definition"]["key"] == item_key
        )

    @staticmethod
    def _capacity_source_context() -> dict[str, object]:
        return {
            "revisionId": "00000000-0000-4000-8000-000000000210",
            "revisionSnapshotHash": "1" * 64,
            "toolingSetId": "00000000-0000-4000-8000-000000000211",
            "toolingSetSnapshotHash": "2" * 64,
            "applicability": [
                {
                    "globalId": "00000000-0000-4000-8000-000000000212",
                    "snapshotHash": "3" * 64,
                    "partRevisionGlobalId": (
                        "00000000-0000-4000-8000-000000000213"
                    ),
                    "partRevisionSnapshotHash": "4" * 64,
                },
                {
                    "globalId": "00000000-0000-4000-8000-000000000214",
                    "snapshotHash": "5" * 64,
                    "partRevisionGlobalId": (
                        "00000000-0000-4000-8000-000000000215"
                    ),
                    "partRevisionSnapshotHash": "6" * 64,
                },
            ],
        }

    @staticmethod
    def _controlled_reference_workspace() -> dict[str, object]:
        round_id = "00000000-0000-4000-8000-000000000230"
        comparison_id = "00000000-0000-4000-8000-000000000231"
        comparison_hash = "7" * 64
        round_hash = "6" * 64
        return {
            "trialRound": {
                "globalId": round_id,
                "optimisticVersion": 7,
                "snapshotHash": round_hash,
            },
            "comparisonSnapshots": [
                {
                    "globalId": comparison_id,
                    "snapshotHash": comparison_hash,
                    "targetRoundGlobalId": round_id,
                    "sources": [
                        {
                            "sequence": 1,
                            "trialRoundGlobalId": (
                                "00000000-0000-4000-8000-000000000229"
                            ),
                            "trialRoundOptimisticVersion": 4,
                            "trialRoundSnapshotHash": "5" * 64,
                        },
                        {
                            "sequence": 2,
                            "trialRoundGlobalId": round_id,
                            "trialRoundOptimisticVersion": 7,
                            "trialRoundSnapshotHash": round_hash,
                        },
                    ],
                }
            ],
            "reviewReferenceRevisions": [
                {
                    "globalId": "00000000-0000-4000-8000-000000000232",
                    "referenceGlobalId": (
                        "00000000-0000-4000-8000-000000000233"
                    ),
                    "referenceKind": "controlled_quality_report",
                    "referenceVersion": 1,
                    "trialRoundGlobalId": round_id,
                    "comparisonSnapshot": {
                        "globalId": comparison_id,
                        "snapshotHash": comparison_hash,
                    },
                    "snapshotHash": "8" * 64,
                }
            ],
        }


if __name__ == "__main__":
    unittest.main()
