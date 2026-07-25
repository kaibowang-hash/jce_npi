from __future__ import annotations

import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_VERIFIER = ROOT / "scripts" / "verify_project_controls_runtime.py"
RUNTIME_SHELL = ROOT / "scripts" / "verify-frappe-runtime.sh"


class Phase4ProjectControlsRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = RUNTIME_VERIFIER.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.functions = {
            node.name: ast.get_source_segment(cls.source, node) or ""
            for node in cls.tree.body
            if isinstance(node, ast.FunctionDef)
        }
        cls.shell = RUNTIME_SHELL.read_text(encoding="utf-8")

    def test_fixture_namespace_is_caller_owned_and_shared_exactly(self) -> None:
        validator = self.functions["validated_fixture_run_id"]
        self.assertIn("return uuid4().hex", validator)
        self.assertIn('r"[a-f0-9]{32}"', validator)
        self.assertIn("NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID", self.source)
        self.assertIn(
            'os.environ.setdefault("NPI_GATE_EVIDENCE_RUNTIME_RUN_ID", FIXTURE_RUN_ID)',
            self.source,
        )
        self.assertIn(
            'os.environ.setdefault("NPI_GATE_REVIEW_RUNTIME_RUN_ID", FIXTURE_RUN_ID)',
            self.source,
        )

        environment = os.environ.copy()
        environment["NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID"] = (
            "0123456789abcdef0123456789abcdef"
        )
        accepted = subprocess.run(
            [sys.executable, str(RUNTIME_VERIFIER), "--help"],
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        environment["NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID"] = "NOT-A-RUN-ID"
        rejected = subprocess.run(
            [sys.executable, str(RUNTIME_VERIFIER), "--help"],
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn(
            "must be exactly 32 lowercase hexadecimal characters",
            rejected.stderr,
        )

    def test_schema_probe_is_additive_and_rejects_migration_defaults(
        self,
    ) -> None:
        schema = self.functions["verify_runtime_schema"]
        for doctype in (
            "NPI Project Control Policy",
            "NPI Project Control Policy Version",
            "NPI Project Control Binding",
            "NPI Project Health Assessment",
            "NPI Project Activity Event",
            "NPI Project Follower",
            "NPI Project Learning",
            "NPI Project Control Idempotency",
            "NPI My Work Assignment",
        ):
            self.assertIn(f'"{doctype}"', schema)
        for field in (
            "control_binding_global_id",
            "current_health_assessment_global_id",
            "current_health_status",
        ):
            self.assertIn(f'"{field}"', schema)
        self.assertIn("frappe.db.table_exists(doctype)", schema)
        self.assertIn('"actor_key_hash"', schema)
        self.assertIn('"assignment_key"', schema)
        self.assertIn('"Non_unique"', schema)
        self.assertIn(
            '"npi_core.patches.v1_2.rebuild_my_work_projection"',
            schema,
        )
        self.assertIn(
            "Migration installed a non-runtime Project Control Policy",
            schema,
        )
        self.assertIn(
            "Migration installed non-runtime business history",
            schema,
        )

    def test_controls_cover_honest_health_and_lifecycle_fail_closed(
        self,
    ) -> None:
        main = self.functions["main"]
        self.assertIn("require_unassessed_controls(", main)
        self.assertIn("require_bound_controls(", main)
        self.assertIn('"measurements": red_measurements', main)
        self.assertIn('{"reason", "recoveryPlan"}', main)
        self.assertIn('"overallStatus"] == "unavailable"', main)
        for dimension, status in (
            ("progress", "red"),
            ("cost", "green"),
            ("quality", "red"),
            ("risk", "unavailable"),
        ):
            self.assertIn(
                f'health_dimensions["{dimension}"]["status"] == "{status}"',
                main,
            )
        for action in ("pause", "resume", "complete", "cancel"):
            self.assertIn(f'"action": "{action}"', main)
        self.assertIn(
            '"PROJECT_TRANSITION_PREREQUISITE_UNAVAILABLE"',
            main,
        )
        self.assertIn(
            '{"prerequisites.cost", "prerequisites.handover"}',
            main,
        )

    def test_security_and_actor_bound_sealed_replay_are_live(self) -> None:
        main = self.functions["main"]
        self.assertIn("same_project_unavailable(", main)
        self.assertIn("unrelated_unavailable", main)
        self.assertIn("tenant_unavailable", main)
        self.assertIn('"AUTHENTICATION_REQUIRED"', main)
        self.assertIn('"CSRF_TOKEN_INVALID"', main)
        self.assertIn("cross_comment", main)
        self.assertIn("SHARED_COMMENT_KEY", main)
        self.assertIn("owner_comment", main)
        self.assertIn("administrator_comment", main)
        self.assertIn("require_control_receipt(", main)
        receipt = self.functions["require_control_receipt"]
        self.assertIn("actor_key_hash(actor, raw_key)", receipt)
        self.assertIn('"response_sealed"', receipt)
        self.assertIn("response == expected_body", receipt)
        replay = self.functions["verify_cross_process_replay"]
        self.assertIn("SHARED_COMMENT_KEY", replay)
        self.assertIn("require_replay(", replay)

    def test_injected_transaction_rollback_and_route_disable_are_live(self) -> None:
        rollback = self.functions["verify_transaction_rollback"]
        self.assertIn('"_seal_idempotency"', rollback)
        self.assertIn("frappe.db.rollback()", rollback)
        self.assertIn('"NPI Project Control Idempotency"', rollback)
        self.assertIn('"NPI Project Activity Event"', rollback)
        self.assertIn('"NPI Audit Event"', rollback)
        self.assertIn("staged_receipt is not None", rollback)
        self.assertIn("len(staged_activity) == 1", rollback)
        self.assertIn("len(staged_audit) == 1", rollback)
        self.assertIn("receipt is None", rollback)
        self.assertIn("activity == []", rollback)
        self.assertIn("audit == []", rollback)

        route_disable = self.functions["verify_route_disable_switch"]
        self.assertIn("npi_p4_05_routes_disabled", route_disable)
        self.assertIn("npi_core.my_work_api.get_my_work", route_disable)
        self.assertIn(
            "npi_core.project_work_api.get_project_work_context",
            route_disable,
        )
        self.assertIn('frappe.conf[key] = "true"', route_disable)
        http_probe = self.functions["verify_route_disable_http_probe"]
        for route in (
            "/api/npi/v1/me/work",
            "/api/npi/v1/learning",
            "/controls",
            "/activity",
            "/comments",
            "/learning",
            ":bind-control-policy",
            ":assess-health",
            ":transition",
            ":follow",
            ":unfollow",
            "/api/method/npi_core.my_work_api.get_my_work",
            "npi_core.project_controls_api.search_project_learning",
            "/work-context",
            "/evidence",
        ):
            self.assertIn(route, http_probe)
        self.assertIn(
            '"PROJECT_COLLABORATION_ROUTES_DISABLED"',
            http_probe,
        )
        self.assertIn('"private, no-store"', http_probe)
        main = self.functions["main"]
        self.assertIn('"verify_transaction_rollback"', main)
        self.assertIn('"verify_route_disable_switch"', main)
        self.assertIn('"transactionRollback"', main)
        self.assertIn('"routeDisableRecovery"', main)

    def test_collaboration_is_typed_private_and_append_only(self) -> None:
        main = self.functions["main"]
        for call in (
            "/comments",
            ":follow",
            ":unfollow",
            "/learning",
            "/activity",
        ):
            self.assertIn(call, main)
        self.assertIn('"template_improvement"', main)
        self.assertIn('"project_learning"', main)
        self.assertIn('"project_work_item"', main)
        self.assertIn("require_comment_options(", main)
        self.assertIn('"/private/files/" not in serialized_comment', main)
        self.assertIn("'\"url\"' not in serialized_comment", main)
        options = self.functions["require_comment_options"]
        self.assertIn(
            '{"truncated", "mentions", "attachments", "objectLinks"}',
            options,
        )
        self.assertIn('value["truncated"] is False', options)
        self.assertIn('"scanState"] == "clean"', options)
        self.assertIn("actual_targets == expected_targets", options)
        self.assertIn("verify_terminal_guards(", main)
        self.assertIn("require_activity_cursor_chain(", main)
        terminal = self.functions["verify_terminal_guards"]
        self.assertEqual(terminal.count('"PROJECT_HISTORY_LOCKED"'), 3)
        self.assertIn("Terminal Project append-only comment", terminal)
        cursor_chain = self.functions["require_activity_cursor_chain"]
        self.assertIn('query: dict[str, object] = {"limit": 2}', cursor_chain)
        self.assertIn('query["cursor"] = cursor', cursor_chain)
        self.assertIn("previous_key > key", cursor_chain)
        self.assertIn("global_id not in seen_ids", cursor_chain)
        self.assertIn("next_cursor not in seen_cursors", cursor_chain)
        self.assertIn("collected == expected_items", cursor_chain)

    def test_my_work_covers_counts_filters_cursor_and_typed_targets(
        self,
    ) -> None:
        verifier = self.functions["verify_my_work_projection"]
        for view in (
            "today",
            "overdue",
            "approvals",
            "blockers",
            "waiting",
            "integration",
        ):
            self.assertIn(f'"{view}"', verifier)
        self.assertIn('"domain_severity"', verifier)
        self.assertIn('"high"', verifier)
        self.assertIn("cursor=cursor", verifier)
        self.assertIn('page["asOf"] == page_as_of', verifier)
        self.assertIn('"VALIDATION_FAILED"', verifier)
        self.assertIn("cross_actor = my_work(", verifier)
        self.assertIn('"actorBoundCursor": True', verifier)
        self.assertIn('"gate_review_assignment"', verifier)
        self.assertIn('"gate_review_step"', verifier)
        self.assertIn('"gate_final_decision"', verifier)
        self.assertIn("len(gate_items) == 2", verifier)
        page = self.functions["require_my_work_page"]
        self.assertIn("expected_time_zone", page)
        self.assertIn('body.get("timeZone") == expected_time_zone', page)
        self.assertIn('"projectOptions"', page)
        self.assertIn("project_by_id", page)
        self.assertIn(
            '"My Work row Project is absent from the complete filter options"',
            page,
        )
        self.assertIn('"source_not_available"', page)
        self.assertIn('"value" not in counts.get("integration", {})', page)
        self.assertIn('target.get("kind") == "my_work_item"', page)
        self.assertIn('target.get("kind") == "gate_review"', page)
        self.assertIn('"path"', page)
        self.assertIn('"url"', page)
        self.assertIn(
            '(administrator, "System Manager", administrator_time_zone)',
            verifier,
        )
        effective_time_zone = self.functions["_effective_user_time_zone"]
        self.assertIn('"System Settings"', effective_time_zone)
        self.assertIn("ZoneInfo(value)", effective_time_zone)

    def test_projection_refresh_deactivation_and_rebuild_are_persisted(
        self,
    ) -> None:
        reassign = self.functions["reassign_domain_work_item"]
        self.assertIn("_controlled_work_write_scope", reassign)
        self.assertIn("source.save()", reassign)
        self.assertIn("(evidence_runtime.OWNER_USER, 0, 1)", reassign)
        self.assertIn("(evidence_runtime.REVIEWER_USER, 1, 2)", reassign)
        deactivation = self.functions["verify_projection_deactivation"]
        self.assertIn('"gate_review_assignment"', deactivation)
        self.assertIn('"gate_review_step"', deactivation)
        self.assertIn('"gate_final_decision"', deactivation)
        self.assertIn('"gateStepAssignmentActive": False', deactivation)
        self.assertIn('"gateDecisionAuthorityActive": True', deactivation)
        rebuild = self.functions["verify_projection_rebuild"]
        self.assertEqual(rebuild.count("rebuild_my_work_projection()"), 3)
        self.assertIn(
            '"refresh_domain_work_item_assignment"',
            rebuild,
        )
        self.assertIn("frappe.db.rollback()", rebuild)
        self.assertIn("rolled_back == before", rebuild)
        self.assertIn("before == first == second", rebuild)
        self.assertIn("first_result == second_result", rebuild)
        state = self.functions["_projection_state"]
        for fieldname in (
            '"actor_user_id"',
            '"project_global_id"',
            '"source_version"',
            '"assignment_code"',
            '"category"',
            '"due_at"',
            '"priority_scheme"',
            '"priority_value"',
            '"blocking"',
            '"source_snapshot"',
            '"snapshot_hash"',
        ):
            self.assertIn(fieldname, state)
        main = self.functions["main"]
        self.assertIn('"verify_projection_deactivation"', main)
        self.assertIn('"verify_projection_rebuild"', main)

    def test_terminal_project_deactivates_all_my_work_source_types(self) -> None:
        seed = self.functions["seed_terminal_my_work_projections"]
        verify = self.functions["verify_terminal_my_work_deactivation"]
        main = self.functions["main"]
        for source_type in (
            "domain_work_item",
            "gate_review_assignment",
            "gate_review_invalidation",
        ):
            self.assertIn(f'"{source_type}"', seed)
            self.assertIn(f'"{source_type}"', verify)
        self.assertIn("store.upsert", seed)
        self.assertIn("all(int(row.active) == 1", seed)
        self.assertIn("all(int(row.active) == 0", verify)
        self.assertIn('snapshot.get("active") is False', verify)
        self.assertIn('"seed_terminal_my_work_projections"', main)
        self.assertIn('"verify_terminal_my_work_deactivation"', main)
        self.assertIn("project_id=terminal_project_id", main)
        self.assertIn('terminal_my_work["items"] == []', main)

    def test_shell_runs_fresh_then_second_process_replay(self) -> None:
        self.assertIn("--project-controls-only", self.shell)
        self.assertIn(
            'export NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID="${project_controls_runtime_run_id}"',
            self.shell,
        )
        self.assertIn(
            "run_project_controls_runtime_verifier fresh",
            self.shell,
        )
        self.assertIn(
            "run_project_controls_runtime_verifier replay-only",
            self.shell,
        )
        self.assertIn(
            "set_p405_route_switch true true",
            self.shell,
        )
        self.assertIn(
            "set_p405_route_switch false false",
            self.shell,
        )
        self.assertIn(
            "set_p405_route_switch None absent",
            self.shell,
        )
        self.assertIn('if key not in config:', self.shell)
        self.assertIn('verify_p405_route_switch_state "${expected}"', self.shell)
        self.assertIn("route_disable_config_changed=true", self.shell)
        self.assertNotIn("restore_p405_route_switch || true", self.shell)
        self.assertIn("Local Frappe runtime did not release port", self.shell)
        self.assertLess(
            self.shell.index("route_disable_config_changed=true"),
            self.shell.index("set_p405_route_switch true true"),
        )
        self.assertIn(
            "run_project_controls_route_probe disabled",
            self.shell,
        )
        self.assertIn(
            "run_project_controls_route_probe recovered",
            self.shell,
        )
        self.assertLess(
            self.shell.index("run_project_controls_runtime_verifier fresh"),
            self.shell.index("run_project_controls_route_probe disabled"),
        )
        self.assertLess(
            self.shell.index("run_project_controls_route_probe disabled"),
            self.shell.index("set_p405_route_switch false false"),
        )
        self.assertLess(
            self.shell.index("set_p405_route_switch false false"),
            self.shell.index("run_project_controls_route_probe recovered"),
        )
        self.assertLess(
            self.shell.index("run_project_controls_route_probe recovered"),
            self.shell.index("run_project_controls_runtime_verifier replay-only"),
        )
        self.assertIn(
            'if [[ "${verification_mode}" == "all" ||',
            self.shell,
        )


if __name__ == "__main__":
    unittest.main()
