from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.foundation.localization import load_runtime_catalog
from npi_core.project_work import POLICY_LABEL_SOURCES, LifecycleState
from npi_core.project_work.policy_labels import (
    PolicyLabelRegistryError,
    _parse_registry,
)


class ProjectWorkPolicyLabelRegistryTest(unittest.TestCase):
    def test_packaged_registry_is_exact_and_immutable(self) -> None:
        self.assertIsInstance(POLICY_LABEL_SOURCES, frozenset)
        self.assertEqual(
            POLICY_LABEL_SOURCES,
            frozenset(
                {
                    "Draft",
                    "Identified",
                    "Not started",
                    "Open",
                    "Requested",
                }
            ),
        )
        self.assertFalse(hasattr(POLICY_LABEL_SOURCES, "add"))

    def test_registry_parser_fails_closed_for_unsafe_shapes(self) -> None:
        invalid_payloads: tuple[object, ...] = (
            [],
            {},
            {"schemaVersion": True, "labelSources": ["Draft"]},
            {"schemaVersion": 2, "labelSources": ["Draft"]},
            {"schemaVersion": 1, "labelSources": []},
            {"schemaVersion": 1, "labelSources": [" Draft"]},
            {"schemaVersion": 1, "labelSources": ["草稿"]},
            {"schemaVersion": 1, "labelSources": ["123"]},
            {"schemaVersion": 1, "labelSources": ["Draft草稿"]},
            {"schemaVersion": 1, "labelSources": ["Draft\n"]},
            {"schemaVersion": 1, "labelSources": ["Draft", "Draft"]},
            {
                "schemaVersion": 1,
                "labelSources": ["Requested", "Draft"],
            },
            {
                "schemaVersion": 1,
                "labelSources": ["Draft"],
                "unexpected": True,
            },
        )
        with self.assertRaises(PolicyLabelRegistryError):
            _parse_registry("{")
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(PolicyLabelRegistryError):
                    _parse_registry(json.dumps(payload))

    def test_registered_draft_label_is_accepted(self) -> None:
        state = LifecycleState("draft", "Draft")
        self.assertEqual(state.label_source, "Draft")

    def test_translated_but_unregistered_label_is_rejected(self) -> None:
        translations = (
            Path("apps/npi_core/npi_core/translations/zh.csv"),
            Path("apps/npi_core/npi_core/translations/zh-TW.csv"),
        )
        for path in translations:
            with self.subTest(path=path):
                self.assertIn("Completed", load_runtime_catalog(path))

        with self.assertRaises(RequestValidationFailed) as context:
            LifecycleState("completed", "Completed", terminal=True)
        self.assertEqual(
            context.exception.field_errors,
            [
                {
                    "path": "states.labelSource",
                    "message": "Select a supported value.",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
