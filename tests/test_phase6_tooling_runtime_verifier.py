from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_tooling_runtime.py"
RUNTIME_SHELL = ROOT / "scripts" / "verify-frappe-runtime.sh"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
FIXTURE_RUN_ID = "0123456789abcdef0123456789abcdef"


def load_verifier():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    saved = {
        name: sys.modules.pop(name, None)
        for name in (
            "verify_document_runtime",
            "verify_tooling_runtime_contract",
        )
    }
    spec = importlib.util.spec_from_file_location(
        "verify_tooling_runtime_contract",
        VERIFIER,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Tooling runtime verifier cannot be imported")
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
        for name in tuple(saved):
            sys.modules.pop(name, None)
        for name, value in saved.items():
            if value is not None:
                sys.modules[name] = value
    return module


class Phase6ToolingRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_verifier()
        cls.source = VERIFIER.read_text(encoding="utf-8")
        cls.shell = RUNTIME_SHELL.read_text(encoding="utf-8")
        cls.workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    def test_fixture_namespace_is_synthetic_and_bounded(self) -> None:
        module = self.module
        self.assertEqual(module.FIXTURE_RUN_ID, FIXTURE_RUN_ID)
        self.assertEqual(module.TENANT_ID, "runtime-tenant")
        self.assertTrue(module.UNRELATED_USER.endswith("@example.invalid"))
        self.assertEqual(len(module.TOOLING_DOCTYPES), 9)
        self.assertEqual(module.SECOND_PROJECT_CODE, "P6-01-0123456789ABCDEF")
        self.assertNotIn("core." + "whjichen.cn", self.source)
        for forbidden in (
            "ERPNext endpoint",
            "credential",
            "source adapter",
            "external QR",
            "production mapping",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.source)

    def test_payloads_keep_distinct_part_revision_and_applicability_truth(self) -> None:
        module = self.module
        self.assertEqual(
            module.part_payload("Part", "A"),
            {
                "title": "Part",
                "revisionLabel": "A",
                "reason": "Create an exact synthetic engineering Part revision.",
            },
        )
        initial = module.applicability_payload(
            "10000000-0000-4000-8000-000000000001",
            "20000000-0000-4000-8000-000000000002",
            effective_from="2026-08-01",
            effective_to="2026-09-01",
        )
        self.assertEqual(
            set(initial),
            {
                "toolingMasterGlobalId",
                "partRevisionGlobalId",
                "effectiveFrom",
                "effectiveTo",
                "reason",
            },
        )
        successor = module.applicability_payload(
            initial["toolingMasterGlobalId"],
            initial["partRevisionGlobalId"],
            relationship_id="30000000-0000-4000-8000-000000000003",
            expected_version=1,
            effective_from="2026-09-01",
            effective_to=None,
        )
        self.assertEqual(successor["expectedVersion"], 1)
        self.assertNotIn("effectiveTo", successor)
        for payload in (initial, successor):
            serialized = str(payload).casefold()
            for forbidden in (
                "tenantid",
                "actor",
                "snapshot",
                "relationshipkeyhash",
                "lifecycle",
                "setcount",
                "asset",
            ):
                with self.subTest(payload=payload, forbidden=forbidden):
                    self.assertNotIn(forbidden, serialized)

        tooling_set = module.tooling_set_payload(
            "10000000-0000-4000-8000-000000000001",
            "PHYSICAL-001",
            customer_owned=True,
        )
        self.assertEqual(
            tooling_set["customer"],
            {
                "sourceSystem": "ERPNEXT",
                "sourceObjectId": "SYNTHETIC-0123456789abcdef",
            },
        )
        intake = module.tooling_intake_payload()
        self.assertNotIn("expectedVersion", intake)
        self.assertEqual(len(intake["inspections"]), 5)
        self.assertEqual(
            {row["category"] for row in intake["inspections"]},
            {
                "appearance",
                "water_circuit",
                "hot_runner",
                "electrical",
                "safety",
            },
        )
        self.assertEqual(len(intake["differences"]), 2)
        successor = module.tooling_intake_payload(
            expected_version=1,
            corrected=True,
        )
        self.assertEqual(successor["expectedVersion"], 1)
        self.assertNotEqual(
            successor["transportReference"],
            intake["transportReference"],
        )

    def test_request_uses_only_closed_command_or_query_headers(self) -> None:
        module = self.module
        headers = {
            "Idempotency-Key": "p6-key",
            "X-Request-ID": "10000000-0000-4000-8000-000000000001",
            "X-Trace-ID": "trace-" + ("a" * 32),
            "X-Frappe-CSRF-Token": "csrf-" + ("b" * 48),
        }
        raw = SimpleNamespace(
            status=201,
            headers={
                "X-Request-ID": headers["X-Request-ID"],
                "Cache-Control": "private, no-store",
            },
            body={"project": {}},
        )
        with patch.object(
            module.document_runtime,
            "command_headers",
            side_effect=lambda *_values: dict(headers),
        ), patch.object(
            module.document_runtime,
            "request",
            return_value=raw,
        ) as request:
            result = module.tooling_request(
                object(),
                "http://127.0.0.1:8003",
                "/api/npi/v1/projects/project/parts",
                method="POST",
                payload={"title": "Part"},
                csrf_token=headers["X-Frappe-CSRF-Token"],
                idempotency_key=headers["Idempotency-Key"],
            )

        self.assertEqual(result.status, 201)
        self.assertEqual(
            request.call_args.kwargs["request_headers"],
            headers,
        )
        self.assertNotIn("X-NPI-Diagnostic-Scope", headers)

        with patch.object(
            module.document_runtime,
            "command_headers",
            side_effect=lambda *_values: dict(headers),
        ), patch.object(
            module.document_runtime,
            "request",
            return_value=raw,
        ) as diagnostic_request:
            module.tooling_request(
                object(),
                "http://127.0.0.1:8003",
                "/api/npi/v1/projects/project/parts",
                method="POST",
                payload={"title": "Part"},
                csrf_token=headers["X-Frappe-CSRF-Token"],
                idempotency_key=headers["Idempotency-Key"],
                part_create_diagnostic=True,
            )
        self.assertEqual(
            diagnostic_request.call_args.kwargs["request_headers"].get(
                "X-NPI-Diagnostic-Scope"
            ),
            "p601-part-create-v1",
        )
        self.assertFalse(module.PART_CREATE_DIAGNOSTICS_ENABLED)

        with patch.object(
            module.document_runtime,
            "command_headers",
            side_effect=lambda *_values: dict(headers),
        ), patch.object(
            module.document_runtime,
            "request",
            return_value=raw,
        ) as applicability_diagnostic_request:
            module.tooling_request(
                object(),
                "http://127.0.0.1:8003",
                "/api/npi/v1/projects/project/tooling-applicabilities",
                method="POST",
                payload={"toolingMasterGlobalId": "master"},
                csrf_token=headers["X-Frappe-CSRF-Token"],
                idempotency_key=headers["Idempotency-Key"],
                applicability_create_diagnostic=True,
            )
        self.assertEqual(
            applicability_diagnostic_request.call_args.kwargs[
                "request_headers"
            ].get("X-NPI-Diagnostic-Scope"),
            "p601-applicability-create-v1",
        )
        self.assertFalse(module.APPLICABILITY_CREATE_DIAGNOSTICS_ENABLED)

    def test_fresh_proves_reuse_replay_conflict_rollback_idor_and_history(self) -> None:
        fresh = self.source.split("def run_fresh", 1)[1].split("\ndef ", 1)[0]
        persistence = self.source.split("def verify_persistence", 1)[1].split(
            "\ndef ", 1
        )[0]
        for fragment in (
            "TOOLING_IDEMPOTENCY_CONFLICT",
            "TOOLING_APPLICABILITY_CONFLICT",
            "TOOLING_VERSION_CONFLICT",
            "TOOLING_INTAKE_VERSION_CONFLICT",
            "TOOLING_EVIDENCE_CONFLICT",
            "TOOLING_UNAVAILABLE",
            "Idempotency-Replayed",
            "second_project_id",
            "master_id",
            "relationship_id",
            "predecessorGlobalId",
            "customer_owned_intake",
            "copy_or_additional_set",
            "arrival_photo",
            "customer_confirmation",
            "seed_tooling_arrival_photo",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, fresh)
        for fragment in (
            "len(masters) == 1",
            "len(receipts) == 16",
            '"actor_user_id"',
            '"sealed"',
            '"part.revise": 1',
            '"tooling_applicability.create": 3',
            '"tooling_set.create": 2',
            '"tooling_intake.create": 2',
            '"tooling_intake_evidence.create": 2',
            '"NPI Tooling Set", first_set_id',
            '"NPI Tooling Intake", first_intake_id',
            "update_resource(",
            "delete_resource(",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, persistence)

    def test_schema_fixture_guards_exact_additive_metadata(self) -> None:
        module = self.module
        schema = self.source.split("def verify_tooling_runtime_schema", 1)[1].split(
            "\ndef ", 1
        )[0]
        for doctype in module.TOOLING_DOCTYPES:
            with self.subTest(doctype=doctype):
                self.assertIn(doctype, schema)
        for fragment in (
            "document_runtime._validated_runtime_site()",
            "frappe.db.table_exists(doctype)",
            "frappe.get_meta(doctype, cached=False)",
            '"relationship_key_hash"',
            '"predecessor_global_id"',
            '"response_hash"',
            '"intake_key"',
            '"evidence_key_hash"',
            '"file_revision_global_id"',
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, schema)
        self.assertNotIn("ignore_mandatory", self.source)
        self.assertNotIn("ignore_validate", self.source)

    def test_shell_runs_p5_predecessor_before_tooling_and_restores_switch(self) -> None:
        self.assertLess(
            self.shell.index("run_controlled_print_runtime_verifier replay-only"),
            self.shell.index("run_tooling_runtime_verifier fresh"),
        )
        self.assertLess(
            self.shell.index("run_tooling_runtime_verifier fresh"),
            self.shell.index("run_tooling_route_probe disabled"),
        )
        self.assertLess(
            self.shell.index("run_tooling_route_probe recovered"),
            self.shell.index("run_tooling_runtime_verifier replay-only"),
        )
        for fragment in (
            "--tooling-only",
            "npi_p6_01_routes_disabled",
            "npi_p6_02_routes_disabled",
            "tooling_route_disable_original_state",
            "restore_tooling_route_switch",
            "P6-01 route-disable switch to absent",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.shell)

    def test_manual_lane_records_exact_cumulative_scope_without_secrets(self) -> None:
        runtime_job = self.workflow.split("\n  document_runtime:\n", 1)[1]
        for fragment in (
            "P6 Tooling",
            "bash scripts/verify-frappe-runtime.sh --tooling-only",
            "scope=p5-01-through-p6-02",
            "runtime_marker=npi-one-local-runtime-disposable-v1",
            "p6-tooling-runtime-${{ github.run_id }}",
            "docker compose down --volumes",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, runtime_job)
        self.assertNotIn("secrets.", runtime_job)
        self.assertNotIn("continue-on-error", runtime_job)


if __name__ == "__main__":
    unittest.main()
