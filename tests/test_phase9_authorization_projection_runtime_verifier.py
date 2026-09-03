from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/verify_authorization_projection_runtime.py"
SHELL = ROOT / "scripts/verify-frappe-runtime.sh"
RUN_ID = "0123456789abcdef0123456789abcdef"


def load_verifier():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(
        "verify_authorization_projection_runtime_contract", SCRIPT
    )
    if spec is None or spec.loader is None:
        raise AssertionError("P9-04 runtime verifier cannot be imported")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    with patch.dict(
        os.environ,
        {"NPI_DOCUMENT_RUNTIME_RUN_ID": RUN_ID},
        clear=False,
    ):
        spec.loader.exec_module(module)
    return module


class AuthorizationProjectionRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.verifier = load_verifier()
        cls.source = SCRIPT.read_text(encoding="utf-8")
        cls.shell = SHELL.read_text(encoding="utf-8")

    def test_fixture_identity_is_deterministic_and_synthetic(self) -> None:
        self.assertEqual(self.verifier.FIXTURE_RUN_ID, RUN_ID)
        self.assertEqual(
            self.verifier.deterministic_uuid("same"),
            self.verifier.deterministic_uuid("same"),
        )
        self.assertIn("@example.invalid", self.source)
        self.assertNotIn("JCE-Core", self.source)
        self.assertNotIn("ssh ", self.source)

    def test_runtime_proves_projection_replay_revocation_and_cleanup(self) -> None:
        for literal in (
            '"replace_user_authorization"',
            '"exactReplay"',
            '"staleRejected"',
            '"disabledFailsClosed"',
            '"localUserCreated"',
            '"localUserDisabled"',
            '"send_welcome_email"',
            'frappe.db.rollback()',
            '"productionContact": False',
            "authenticated_principal()",
        ):
            self.assertIn(literal, self.source)
        self.assertNotIn("frappe.db" + ".sql", self.source)
        self.assertEqual(self.source.count("ensure_service_user("), 2)

    def test_bench_child_output_is_unread_on_failure(self) -> None:
        function = self.source[
            self.source.index("def run_bench_fixture") : self.source.index(
                "def run_local_bench_fixture"
            )
        ]
        self.assertIn("stderr=subprocess.DEVNULL", function)
        self.assertLess(
            function.index("completed.returncode == 0"),
            function.index("output.seek(0)"),
        )

    def test_cumulative_projection_gate_invokes_the_runtime_once(self) -> None:
        marker = "run_authorization_projection_runtime_verifier"
        self.assertEqual(self.shell.count(f"{marker}()"), 1)
        self.assertEqual(
            self.shell.count(f"if ! {marker} >/dev/null 2>/dev/null; then"),
            1,
        )


if __name__ == "__main__":
    unittest.main()
