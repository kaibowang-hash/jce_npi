from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Phase8InboundProjectRuntimeVerifierTest(unittest.TestCase):
    def test_runtime_fixture_is_marker_and_environment_gated_without_raw_secrets(self) -> None:
        source = (
            ROOT
            / "apps/npi_integration/npi_integration/inbound_project/runtime_fixture.py"
        ).read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn("npi-one-local-runtime-disposable-v1", source)
        self.assertIn("NPI_P8_02_RUNTIME_ENABLED", source)
        self.assertIn("NPI_P8_02_RUNTIME_SECRET_OLD", source)
        self.assertIn("NPI_P8_02_RUNTIME_SECRET_NEW", source)
        self.assertIn("return None", source)
        self.assertNotIn("https://", source)
        self.assertNotIn("api_secret", source.casefold())
        self.assertNotIn("password", source.casefold())

    def test_runtime_verifier_covers_signed_route_claim_project_and_replay(self) -> None:
        source = (
            ROOT / "scripts/verify_inbound_project_runtime.py"
        ).read_text(encoding="utf-8")
        ast.parse(source)
        for marker in (
            "INBOUND_PROJECT_AUTHENTICATION_FAILED",
            "INBOUND_PROJECT_INGRESS_UNAVAILABLE",
            "INBOUND_PROJECT_SOURCE_CONFLICT",
            "ThreadPoolExecutor",
            "capture_retained_context",
            "process_reordered_receipts",
            "live claim was stolen",
            "expired claim was not recovered",
            "project_created",
            "received_after_creation",
            "cross-process replay changed durable truth",
            '"reference_rules": []',
            '{"role": "Desk User"}',
            "created_actor.status in {200, 201}",
            "created_owner.status in {200, 201}",
            'str(later.body["receiptId"])',
        ):
            self.assertIn(marker, source)
        self.assertEqual(source.count('base_url, "User", ACTOR_USER'), 2)
        self.assertEqual(source.count('base_url, "User", OWNER_USER'), 2)
        for forbidden in (
            "requests.",
            "httpx.",
            "erpnext.com",
            "core.whjichen.cn",
        ):
            self.assertNotIn(forbidden, source.casefold())

    def test_cumulative_shell_and_ci_lane_extend_exactly_through_p8_02(self) -> None:
        shell = (ROOT / "scripts/verify-frappe-runtime.sh").read_text(
            encoding="utf-8"
        )
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("run_inbound_project_runtime_verifier disabled", shell)
        self.assertIn("run_inbound_project_runtime_verifier fresh", shell)
        self.assertIn("run_inbound_project_runtime_verifier replay-only", shell)
        self.assertIn("verify_inbound_project_runtime_log_redaction", shell)
        self.assertIn("scope=p5-01-through-p8-02", workflow)
        self.assertIn("predecessor_scope=p5-01-through-p8-01", workflow)
        self.assertIn("p8-integration-runtime-${{ github.run_id }}", workflow)
        self.assertIn(
            "bash scripts/verify-frappe-runtime.sh --projection-only", workflow
        )


if __name__ == "__main__":
    unittest.main()
