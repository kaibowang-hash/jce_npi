from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/verify_v1_2_reconciliation.py"


def _load_verifier():
    spec = importlib.util.spec_from_file_location(
        "verify_v1_2_reconciliation", MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load reconciliation verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class V12ReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.verifier = _load_verifier()

    def test_generated_artifacts_are_current(self) -> None:
        self.verifier.verify_generated_artifacts()

    def test_trace_sets_are_complete_and_consistent(self) -> None:
        self.verifier.verify_trace_sets()

    def test_brand_package_is_exact_and_self_contained(self) -> None:
        self.verifier.verify_brand_package()


if __name__ == "__main__":
    unittest.main()
