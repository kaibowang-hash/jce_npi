from __future__ import annotations

import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.mbom_publish.domain import MbomTargetMode  # noqa: E402
from npi_integration.mbom_publish import runtime_fixture  # noqa: E402
from tests.test_phase8_mbom_publish_adapters import command  # noqa: E402


class Phase8MbomPublishRuntimeFixtureTest(unittest.TestCase):
    def test_default_is_disabled_and_registry_is_empty(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(
                runtime_fixture.resolve_profile(
                    "tenant-a", "00000000-0000-0000-0000-000000000001"
                )
            )
            self.assertIsNone(runtime_fixture.resolve_adapter_registry())
            with self.assertRaises(RuntimeError):
                runtime_fixture.synthetic_adapter_call_count()

    def test_exact_marker_enables_only_network_free_synthetic_profile(self) -> None:
        environment = {
            "NPI_P8_04_RUNTIME_ENABLED": "1",
            "NPI_P8_04_RUNTIME_MARKER": "npi-one-mbom-publish-disposable-v1",
            "NPI_P8_04_RUNTIME_PROJECT_ID": "00000000-0000-0000-0000-000000000001",
            "NPI_P8_04_RUNTIME_REQUESTER": "publisher@example.invalid",
            "NPI_P8_04_RUNTIME_WORKER": "worker@example.invalid",
        }
        with patch.dict(os.environ, environment, clear=True):
            profile = runtime_fixture.resolve_profile(
                "tenant-a", environment["NPI_P8_04_RUNTIME_PROJECT_ID"]
            )
            self.assertEqual(profile.target_mode, MbomTargetMode.SYNTHETIC)
            self.assertIsNone(profile.base_url)
            self.assertIsNone(profile.secret_reference)
            self.assertEqual(profile.allowed_hostnames, ())
            self.assertIsNotNone(runtime_fixture.resolve_adapter_registry())

    def test_synthetic_adapter_binds_session_and_returns_no_target_ids(self) -> None:
        environment = {
            "NPI_P8_04_RUNTIME_ENABLED": "1",
            "NPI_P8_04_RUNTIME_MARKER": "npi-one-mbom-publish-disposable-v1",
            "NPI_P8_04_RUNTIME_WORKER": "worker@example.invalid",
        }
        saved = sys.modules.get("frappe")
        sys.modules["frappe"] = types.SimpleNamespace(
            session=types.SimpleNamespace(user="worker@example.invalid")
        )
        try:
            with patch.dict(os.environ, environment, clear=True):
                result = runtime_fixture.synthetic_adapter(command())
                self.assertTrue(result.nodes)
                self.assertTrue(all(node.formal_bom_id is None for node in result.nodes))
                self.assertTrue(all(node.http_status is None for node in result.nodes))
                self.assertEqual(
                    runtime_fixture.synthetic_adapter_session_users()[-1],
                    "worker@example.invalid",
                )
        finally:
            sys.modules.pop("frappe", None)
            if saved is not None:
                sys.modules["frappe"] = saved

    def test_fixture_source_has_no_network_client_or_endpoint(self) -> None:
        source = (
            ROOT
            / "apps/npi_integration/npi_integration/mbom_publish/runtime_fixture.py"
        ).read_text(encoding="utf-8")
        for forbidden in ("requests", "httpx", "urllib", "base_url=", "https://"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
