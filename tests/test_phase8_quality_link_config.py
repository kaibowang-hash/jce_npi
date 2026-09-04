from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.quality_link.config import QualityLinkConfiguration, default_quality_link_configurations  # noqa: E402
from npi_integration.quality_link.domain import QualityLinkContractError  # noqa: E402


class Phase8QualityLinkConfigTest(unittest.TestCase):
    def test_checkpoint_one_installs_no_profile_and_default_is_disabled(self) -> None:
        self.assertEqual(default_quality_link_configurations(), ())
        self.assertFalse(QualityLinkConfiguration().enabled)

    def test_authority_freshness_and_enablement_cannot_be_guessed(self) -> None:
        for values in (
            {"enabled": True},
            {"authority_policy_ref": "quality-link-authority-v1"},
            {"freshness_policy_ref": "quality-link-freshness-v1"},
            {"enabled": 1},
        ):
            with self.subTest(values=values), self.assertRaises(QualityLinkContractError):
                QualityLinkConfiguration(**values)

    def test_configuration_has_no_target_or_secret_surface(self) -> None:
        source = (ROOT / "apps/npi_integration/npi_integration/quality_link/config.py").read_text(encoding="utf-8").casefold()
        for forbidden in ("base_url", "endpoint", "credential", "secret_reference", "requests", "socket", "production"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
