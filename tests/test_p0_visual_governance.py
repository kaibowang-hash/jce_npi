from __future__ import annotations

import json
import shutil
import struct
import tempfile
import unittest
from pathlib import Path

from scripts.verify_p0_visual_governance import (
    EXPECTED_LOCALES,
    EXPECTED_SCREENS,
    EXPECTED_VIEWPORT,
    REGISTRY,
    SPEC,
    VisualGovernanceError,
    expected_case_names,
    load_registry,
    verify_visual_governance,
)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class P0VisualGovernanceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.registry = self.root / "p0-visual-registry.json"
        self.spec = self.root / "r1-06-p0-visual-governance.spec.ts"
        self.snapshots = self.root / "snapshots"
        shutil.copyfile(REGISTRY, self.registry)
        shutil.copyfile(SPEC, self.spec)
        self.snapshots.mkdir()
        registry = load_registry(self.registry)
        for case_name in expected_case_names(registry):
            self.write_png(self.snapshots / f"{case_name}-linux.png")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def write_png(path: Path, width: int = 1440, height: int = 900) -> None:
        path.write_bytes(
            PNG_SIGNATURE
            + struct.pack(">I", 13)
            + b"IHDR"
            + struct.pack(">II", width, height)
        )

    def write_registry(self, document: object) -> None:
        self.registry.write_text(
            json.dumps(document, ensure_ascii=False),
            encoding="utf-8",
        )

    def test_exact_registry_spec_and_linux_snapshot_set_pass(self) -> None:
        expected = verify_visual_governance(
            self.registry,
            self.spec,
            self.snapshots,
        )
        self.assertEqual(len(expected), 18)

    def test_registry_rejects_duplicate_keys(self) -> None:
        source = self.registry.read_text(encoding="utf-8")
        self.registry.write_text(
            source.replace(
                '"schemaVersion": 1,',
                '"schemaVersion": 1, "schemaVersion": 1,',
                1,
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(VisualGovernanceError, "duplicate JSON key"):
            load_registry(self.registry)

    def test_registry_rejects_viewport_locale_and_screen_drift(self) -> None:
        safe = {
            "schemaVersion": 1,
            "viewport": EXPECTED_VIEWPORT,
            "scenario": "normal",
            "locales": EXPECTED_LOCALES,
            "screens": EXPECTED_SCREENS,
        }
        variants = (
            {**safe, "viewport": {**EXPECTED_VIEWPORT, "width": 1439}},
            {**safe, "locales": ["en", "zh"]},
            {**safe, "screens": EXPECTED_SCREENS[:-1]},
            {**safe, "extra": True},
        )
        for document in variants:
            with self.subTest(document=document):
                self.write_registry(document)
                with self.assertRaises(VisualGovernanceError):
                    load_registry(self.registry)

    def test_snapshot_set_rejects_missing_and_extra_linux_files(self) -> None:
        target = next(self.snapshots.glob("*-linux.png"))
        target.unlink()
        with self.assertRaisesRegex(VisualGovernanceError, "missing="):
            verify_visual_governance(self.registry, self.spec, self.snapshots)
        self.write_png(target)
        self.write_png(self.snapshots / "unregistered-linux.png")
        with self.assertRaisesRegex(VisualGovernanceError, "extra="):
            verify_visual_governance(self.registry, self.spec, self.snapshots)

    def test_snapshot_rejects_wrong_dimensions_and_invalid_png(self) -> None:
        target = next(self.snapshots.glob("*-linux.png"))
        self.write_png(target, width=1366)
        with self.assertRaisesRegex(VisualGovernanceError, "1440x900"):
            verify_visual_governance(self.registry, self.spec, self.snapshots)
        target.write_bytes(b"not-a-png" * 4)
        with self.assertRaisesRegex(VisualGovernanceError, "canonical PNG"):
            verify_visual_governance(self.registry, self.spec, self.snapshots)

    def test_snapshot_rejects_symlink(self) -> None:
        target = next(self.snapshots.glob("*-linux.png"))
        target.unlink()
        target.symlink_to(self.registry)
        with self.assertRaisesRegex(VisualGovernanceError, "symlink"):
            verify_visual_governance(self.registry, self.spec, self.snapshots)

    def test_spec_rejects_removed_governed_assertion(self) -> None:
        source = self.spec.read_text(encoding="utf-8")
        self.spec.write_text(
            source.replace("await expectNoDocumentOverflow(page);", ""),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(VisualGovernanceError, "governed fragment"):
            verify_visual_governance(self.registry, self.spec, self.snapshots)


if __name__ == "__main__":
    unittest.main()
