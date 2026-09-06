from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts/verify_erp_authorization_sender_runtime.py"


class ProductionActivationERPAuthorizationSenderRuntimeVerifierTest(unittest.TestCase):
    def test_verifier_is_disposable_rollback_only_and_network_free(self) -> None:
        source = VERIFIER.read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertIn('SITE_NAME == "pa07.localhost"', source)
        self.assertIn("frappe.db.rollback()", source)
        self.assertIn('"runtimeTransportContact": False', source)
        self.assertIn("worker.deliver = success", source)
        self.assertIn("timeout_after_commit", source)
        for forbidden in (
            "requests.",
            "httpx.",
            "subprocess",
            "paramiko",
            "JCE-Core",
            "ssh ",
            "frappe.db." + "commit",
        ):
            self.assertNotIn(forbidden, source)
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "rollback"
        ]
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
