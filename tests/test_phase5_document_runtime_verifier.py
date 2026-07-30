from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_document_runtime.py"
RUNTIME_SHELL = ROOT / "scripts" / "verify-frappe-runtime.sh"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
TOOLCHAIN = ROOT / ".devcontainer" / "toolchain.env"
FIXTURE_RUN_ID = "0123456789abcdef0123456789abcdef"


def load_verifier():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(
        "verify_document_runtime_contract",
        VERIFIER,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Document runtime verifier cannot be imported")
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
        sys.modules.pop(spec.name, None)
    return module


class Phase5DocumentRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_verifier()
        cls.source = VERIFIER.read_text(encoding="utf-8")
        cls.shell = RUNTIME_SHELL.read_text(encoding="utf-8")
        cls.workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    def test_fixture_namespace_and_headers_are_bounded(self) -> None:
        module = self.module
        self.assertEqual(
            module.validated_fixture_run_id(FIXTURE_RUN_ID),
            FIXTURE_RUN_ID,
        )
        for invalid in (None, "", "A" * 32, "a" * 31, "../runtime"):
            with self.subTest(invalid=invalid), self.assertRaises(RuntimeError):
                module.validated_fixture_run_id(invalid)
        self.assertRegex(
            module.PROJECT_TEMPLATE_ID,
            r"^[a-f0-9-]{36}$",
        )
        self.assertNotEqual(
            module.PROJECT_TEMPLATE_ID,
            module.DOCUMENT_POLICY_ID,
        )
        headers = module.command_headers(
            "csrf-" + ("a" * 48),
            module.DOCUMENT_CREATE_KEY,
        )
        self.assertEqual(headers["Idempotency-Key"], module.DOCUMENT_CREATE_KEY)
        self.assertRegex(
            headers["X-Request-ID"],
            r"^[a-f0-9-]{36}$",
        )
        self.assertTrue(headers["X-Trace-ID"].startswith("trace-"))

    def test_runtime_schema_inventory_is_exact_and_additive(self) -> None:
        self.assertEqual(
            set(self.module.DOCUMENT_DOCTYPES),
            {
                "NPI Document Policy",
                "NPI Document Policy Version",
                "NPI Controlled Document",
                "NPI Document Revision",
                "NPI Document Revision File",
                "NPI Document Relationship",
                "NPI Document Lock Event",
                "NPI Document Command Idempotency",
                "NPI Document Share Grant",
            },
        )
        self.assertIn("frappe.db.table_exists(doctype)", self.source)
        self.assertIn("frappe.get_meta(doctype, cached=False)", self.source)
        self.assertNotIn("drop table", self.source.casefold())
        self.assertNotIn("truncate table", self.source.casefold())

    def test_runtime_covers_real_file_and_authorization_boundaries(self) -> None:
        required_fragments = (
            "multipart_revision_request(",
            "observe_document_file_scan",
            "FILE_SCAN_RESULT_FLAG",
            '"scanState"] == "pending"',
            '"scanState") == "clean"',
            "binary_content_request(",
            '"X-Content-Type-Options") == "nosniff"',
            '"Referrer-Policy") == "no-referrer"',
            '"Idempotency-Replayed") == "true"',
            "DOCUMENT_VERSION_CONFLICT",
            "DOCUMENT_UNAVAILABLE",
            "AUTHENTICATION_REQUIRED",
            "externalRetrieval",
            "rawPrivateUrlExposed",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.source)
        permission_bypass_token = "ignore_" + "permissions=True"
        self.assertNotIn(permission_bypass_token, self.source)
        self.assertNotIn("allow_guest=True", self.source)
        self.assertNotIn("http://core.whjichen.cn", self.source)

    def test_runtime_shell_migrates_twice_and_restores_route_switch(self) -> None:
        required_fragments = (
            '"--document-only"',
            "for _migration_attempt in 1 2",
            'npi_p5_01_routes_disabled "${value}"',
            "run_document_runtime_verifier fresh",
            "run_document_route_probe disabled",
            "run_document_route_probe recovered",
            "run_document_runtime_verifier replay-only",
            "restore_document_route_switch",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.shell)
        self.assertIn(
            'document_route_disable_original_state}" != "absent"',
            self.shell,
        )

    def test_runtime_uses_only_the_fixed_disposable_site(self) -> None:
        required_fragments = (
            'SITE_NAME = "npi.localhost"',
            'DATABASE_NAME = "npi_one_runtime"',
            'RUNTIME_MARKER = "npi-one-local-runtime-disposable-v1"',
            "frappe.local.site == SITE_NAME",
            "frappe.conf.get(\"npi_runtime_disposable_marker\") == RUNTIME_MARKER",
            "BENCH_PATH.resolve() == BENCH_PATH",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.source)

    def test_manual_ci_lane_uses_the_pinned_disposable_runtime(self) -> None:
        toolchain = dict(
            line.split("=", 1)
            for line in TOOLCHAIN.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
        )
        runtime_job = self.workflow.split("\n  document_runtime:\n", 1)[1]
        required_fragments = (
            "if: github.event_name == 'workflow_dispatch'",
            "timeout-minutes: 45",
            f'"frappe-bench=={toolchain["BENCH_EXPECTED_VERSION"]}"',
            f'"uv=={toolchain["UV_EXPECTED_VERSION"]}"',
            f'test "$(bench --version)" = "{toolchain["BENCH_EXPECTED_VERSION"]}"',
            f'test "$(uv --version)" = "uv {toolchain["UV_EXPECTED_VERSION"]}"',
            f'test "$(yarn --version)" = "{toolchain["YARN_EXPECTED_VERSION"]}"',
            "bash scripts/init-frappe-bench.sh",
            "bash scripts/init-npi-site.sh",
            "bash scripts/verify-frappe-runtime.sh --document-only",
            "site=npi.localhost",
            "database=npi_one_runtime",
            "runtime_marker=npi-one-local-runtime-disposable-v1",
            f'frappe_commit={toolchain["FRAPPE_COMMIT"]}',
            "p5-document-runtime-${{ github.run_id }}",
            "docker compose down --volumes",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, runtime_job)
        self.assertNotIn("secrets.", runtime_job)
        self.assertNotIn("continue-on-error", runtime_job)
        self.assertNotIn("core.whjichen.cn", runtime_job)
        self.assertNotIn("npm install --global", runtime_job)
        self.assertNotIn("--dangerously-allow-all-scripts", runtime_job)


if __name__ == "__main__":
    unittest.main()
