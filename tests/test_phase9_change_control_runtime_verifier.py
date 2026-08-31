from __future__ import annotations

import ast
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_engineering_change_runtime.py"
SHELL = ROOT / "scripts" / "verify-frappe-runtime.sh"
RUN_ID = "0123456789abcdef0123456789abcdef"
PROJECT_ID = "00000000-0000-5000-8000-000000009101"
REQUESTER = "p9-requester@example.invalid"
WORKER = "p9-worker@example.invalid"


def load_verifier():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(
        "verify_engineering_change_runtime_contract", SCRIPT
    )
    if spec is None or spec.loader is None:
        raise AssertionError("P9-01 runtime verifier cannot be imported")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    with patch.dict(
        os.environ,
        {
            "NPI_DOCUMENT_RUNTIME_RUN_ID": RUN_ID,
            "NPI_P9_01C_RUNTIME_PROJECT_ID": PROJECT_ID,
            "NPI_P9_01C_RUNTIME_REQUESTER": REQUESTER,
            "NPI_P9_01C_RUNTIME_WORKER": WORKER,
            "NPI_P9_01C_RUNTIME_SECRET": "a" * 64,
        },
        clear=False,
    ):
        spec.loader.exec_module(module)
    return module


class Phase9ChangeControlRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.verifier = load_verifier()
        cls.source = SCRIPT.read_text(encoding="utf-8")
        cls.shell = SHELL.read_text(encoding="utf-8")

    def test_fixture_content_is_exact_closed_and_version_ready(self) -> None:
        draft = self.verifier.revision_content(complete=False)
        complete = self.verifier.revision_content(complete=True)
        self.assertEqual(
            [item["category"] for item in draft["impactAssessments"]],
            list(self.verifier.IMPACT_CATEGORIES),
        )
        self.assertEqual(len(draft["impactAssessments"]), 12)
        self.assertIsNone(draft["closureEvidence"])
        self.assertEqual(complete["effectivityRules"][0]["kind"], "date")
        self.assertEqual(
            complete["revalidationRequirements"][0]["state"], "satisfied"
        )
        self.assertTrue(
            all(
                complete["closureEvidence"][name]
                for name in (
                    "newVersionsReleased",
                    "erpUpdateObserved",
                    "oldVersionsWithdrawn",
                    "effectivityValidated",
                    "dispositionsExecuted",
                )
            )
        )

    def test_inbound_envelope_has_exact_identity_and_canonical_hash(self) -> None:
        with patch.dict(
            os.environ,
            {"NPI_P9_01C_RUNTIME_PROJECT_ID": PROJECT_ID},
            clear=False,
        ):
            event = self.verifier._inbound_event(
                "00000000-0000-4000-8000-000000009102"
            )
        self.assertEqual(event["event_type"], "npi.erp-engineering-change.v1")
        self.assertEqual(event["source_system"], "ERPNEXT")
        self.assertEqual(event["target_system"], "NPI_ONE")
        self.assertEqual(event["object_type"], "Engineering Change Request")
        self.assertEqual(event["idempotency_key"], event["event_id"])
        self.assertEqual(
            event["payload_hash"], self.verifier.canonical_hash(event["payload"])
        )

    def test_identity_is_deterministic_and_request_headers_are_bounded(self) -> None:
        self.assertEqual(
            self.verifier.deterministic_uuid("same"),
            self.verifier.deterministic_uuid("same"),
        )
        headers = self.verifier._request_headers(
            "command", csrf_token="csrf", idempotency_key="idempotency-key"
        )
        self.assertTrue(self.verifier._uuid(headers["X-Request-ID"]))
        self.assertRegex(headers["X-Trace-ID"], r"^[A-Za-z0-9._:-]{8,128}$")
        self.assertEqual(headers["X-Frappe-CSRF-Token"], "csrf")
        self.assertEqual(headers["Idempotency-Key"], "idempotency-key")

    def test_runtime_covers_closed_lifecycle_replay_and_operation_truth(self) -> None:
        for literal in (
            '"engineering_change.create"',
            '"engineering_change.revise"',
            '"ready_to_close"',
            '"engineering_change.close"',
            '"receive_engineering_change_event"',
            '"publish_change_implementation_summary"',
            '"synthetic_verified"',
            '"crossProcessReplay"',
            '"routeRecovered"',
            '"cleanupComplete"',
        ):
            self.assertIn(literal, self.source)

    def test_bench_child_output_is_unread_on_failure(self) -> None:
        tree = ast.parse(self.source)
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "run_bench_fixture"
        )
        text = ast.unparse(function)
        self.assertIn("stderr=subprocess.DEVNULL", text)
        self.assertLess(
            text.index("require(completed.returncode == 0"),
            text.index("output.seek(0)"),
        )

    def test_cleanup_is_project_and_exact_fixture_bounded(self) -> None:
        tree = ast.parse(self.source)
        cleanup = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_cleanup"
        )
        text = ast.unparse(cleanup)
        self.assertIn("project_global_id", text)
        self.assertIn("CHANGE_TITLE", text)
        self.assertNotIn("frappe" + ".db.sql", text)
        for doctype in (
            "NPI Engineering Change",
            "NPI Engineering Change Revision",
            "NPI Engineering Change Event",
            "NPI Engineering Change Inbox",
            "NPI Engineering Change Summary Request",
            "NPI Engineering Change Summary Outbox",
            "NPI Engineering Change Summary Attempt",
            "NPI Engineering Change Summary Result",
            "NPI Engineering Change Idempotency",
            "NPI Audit Event",
        ):
            self.assertIn(doctype, text)
        self.assertIn("engineering_change.%", text)
        self.assertIn("remaining == 0", text)

    def test_shell_owns_default_disable_restart_recovery_and_restoration(self) -> None:
        sequence = self.shell[self.shell.index("# P9-01 reuses") :]
        ordered = (
            "run_engineering_change_runtime_verifier disabled",
            "set_engineering_change_route_switch false false",
            "set_runtime_disposable_marker npi-one-engineering-change-disposable-v1",
            "run_engineering_change_runtime_verifier fresh",
            "run_engineering_change_runtime_verifier replay-only",
            "set_engineering_change_route_switch true true",
            "run_engineering_change_runtime_verifier recovered",
            "run_engineering_change_runtime_verifier cleanup",
            "restore_runtime_disposable_marker",
            "restore_engineering_change_route_switch",
        )
        positions = [sequence.index(value) for value in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertIn(
            "engineering_change_route_disable_original_state", self.shell
        )
        self.assertIn(
            "Failed to restore the P9-01 route-disable switch to absent.",
            self.shell,
        )

    def test_shell_never_activates_a_production_target(self) -> None:
        self.assertNotIn("JCE-Core", self.shell)
        self.assertNotIn("ssh ", self.shell)
        self.assertNotIn("bench --site jce.1", self.shell)
        self.assertIn(
            "npi-one-engineering-change-disposable-v1", self.shell
        )


if __name__ == "__main__":
    unittest.main()
