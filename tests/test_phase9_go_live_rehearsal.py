from __future__ import annotations

import importlib.util
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_go_live_rehearsal.py"
RUN_ID = "0123456789abcdef0123456789abcdef"


def load_verifier():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location("verify_go_live_rehearsal_contract", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("P9-07 recovery verifier cannot be imported")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    with patch.dict(os.environ, {"NPI_DOCUMENT_RUNTIME_RUN_ID": RUN_ID}, clear=False):
        spec.loader.exec_module(module)
    return module


class GoLiveRehearsalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.verifier = load_verifier()

    def manifest(self) -> dict[str, object]:
        return {
            "appNames": ["frappe", "npi_core", "npi_integration"],
            "appTreeSha256": {"npi_core": "a" * 64, "npi_integration": "b" * 64},
            "configKeyCount": 9,
            "configKeySha256": "c" * 64,
            "database": "npi_one_runtime",
            "environment": "disposable-local-frappe-site",
            "frappeSha": "d" * 40,
            "gitSha": "e" * 40,
            "productionContact": False,
            "runtimeMarker": "npi-one-local-runtime-disposable-v1",
            "schemaTreeSha256": "f" * 64,
            "schemaVersion": "go-live-rehearsal-manifest.v1",
            "site": "npi.localhost",
        }

    def test_canonical_hash_is_order_independent(self) -> None:
        self.assertEqual(
            self.verifier.canonical_sha256({"b": 2, "a": 1}),
            self.verifier.canonical_sha256({"a": 1, "b": 2}),
        )

    def test_release_manifest_is_closed_and_production_false(self) -> None:
        manifest = self.manifest()
        self.verifier.validate_release_manifest(manifest)
        for mutation in (
            {**manifest, "productionContact": True},
            {**manifest, "site": "jce.1"},
            {**manifest, "extra": "forbidden"},
            {**manifest, "appTreeSha256": {"npi_core": "a" * 64}},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(RuntimeError):
                self.verifier.validate_release_manifest(mutation)

    def test_rehearsal_directory_is_fixed_private_and_non_symlinked(self) -> None:
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            accepted = root / "npi-p9-07-rehearsal.A1b2C3"
            accepted.mkdir(mode=0o700)
            accepted.chmod(0o700)
            with patch.dict(os.environ, {"NPI_P9_07_REHEARSAL_ROOT": str(root)}):
                self.assertEqual(
                    self.verifier.validated_rehearsal_directory(str(accepted)),
                    accepted.resolve(),
                )
                accepted.chmod(0o755)
                with self.assertRaisesRegex(RuntimeError, "permissions"):
                    self.verifier.validated_rehearsal_directory(str(accepted))
                accepted.chmod(0o700)
                escaped = root / "arbitrary"
                escaped.mkdir()
                with self.assertRaisesRegex(RuntimeError, "escaped"):
                    self.verifier.validated_rehearsal_directory(str(escaped))

    def test_backup_inventory_hashes_exact_four_private_members(self) -> None:
        with tempfile.TemporaryDirectory() as root_name:
            directory = Path(root_name)
            for index, name in enumerate(self.verifier.BACKUP_MEMBERS.values(), start=1):
                path = directory / name
                path.write_bytes(f"synthetic-{index}".encode())
                path.chmod(0o600)
            result = self.verifier.backup_inventory(directory)
            self.assertEqual(set(result["members"]), set(self.verifier.BACKUP_MEMBERS))
            self.assertFalse(result["productionContact"])
            self.assertRegex(result["evidenceChecksum"], r"^[a-f0-9]{64}$")
            (directory / "database.sql.gz").write_bytes(b"")
            with self.assertRaisesRegex(RuntimeError, "empty"):
                self.verifier.backup_inventory(directory)

    def test_file_tree_inventory_is_bounded_and_content_addressed(self) -> None:
        with tempfile.TemporaryDirectory() as root_name:
            bench = Path(root_name) / "frappe-bench"
            site = bench / "sites" / "npi.localhost"
            for visibility in ("public", "private"):
                directory = site / visibility / "files"
                directory.mkdir(parents=True)
                (directory / f"{visibility}.txt").write_text(visibility, encoding="utf-8")
            with (
                patch.object(self.verifier, "BENCH_PATH", bench),
                patch.object(self.verifier, "load_controlled_database"),
            ):
                first = self.verifier.tree_inventory()
                second = self.verifier.tree_inventory()
                self.assertEqual(first, second)
                self.assertEqual(first["fileCount"], 2)
                self.assertEqual(first["totalBytes"], 13)
                self.assertRegex(first["treeSha256"], r"^[a-f0-9]{64}$")

    def test_result_accepts_only_bounded_integer_timings(self) -> None:
        manifest = self.manifest()
        backup = {
            "members": {},
            "productionContact": False,
            "schemaVersion": "go-live-recovery-result.v1",
        }
        backup["evidenceChecksum"] = self.verifier.canonical_sha256(backup)
        tree = {
            "fileCount": 2,
            "totalBytes": 13,
            "treeSha256": "a" * 64,
            "evidenceChecksum": "b" * 64,
        }
        with tempfile.TemporaryDirectory() as root_name:
            directory = Path(root_name)
            (directory / "release-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (directory / "backup-inventory.json").write_text(json.dumps(backup), encoding="utf-8")
            (directory / "pre-backup-files.json").write_text(json.dumps(tree), encoding="utf-8")
            environment = {
                "NPI_P9_07_BACKUP_SECONDS": "12",
                "NPI_P9_07_RESTORE_SECONDS": "13",
                "NPI_P9_07_FORWARD_FIX_SECONDS": "14",
            }
            with (
                patch.object(self.verifier, "backup_inventory", return_value=backup),
                patch.object(self.verifier, "tree_inventory", return_value=tree),
                patch.dict(os.environ, environment, clear=False),
            ):
                result = self.verifier.build_result(directory)
                self.assertEqual(result["backupSeconds"], 12)
                self.assertTrue(result["restoreVerified"])
                self.assertTrue(result["forwardFixVerified"])
                self.assertFalse(result["productionContact"])
            environment["NPI_P9_07_BACKUP_SECONDS"] = "2701"
            with (
                patch.object(self.verifier, "backup_inventory", return_value=backup),
                patch.object(self.verifier, "tree_inventory", return_value=tree),
                patch.dict(os.environ, environment, clear=False),
                self.assertRaisesRegex(RuntimeError, "bound"),
            ):
                self.verifier.build_result(directory)


if __name__ == "__main__":
    unittest.main()
