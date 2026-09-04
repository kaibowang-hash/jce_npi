from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
import unittest
import zipfile
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_core"))

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.historical_migration.bundle import inspect_bundle
from npi_core.historical_migration.domain import BUNDLE_SCHEMA_VERSION, MigrationFamily


HEADERS = {
    "projects.csv": (
        "source_key", "business_code", "title", "project_type", "owner_user_id",
        "target_sop", "template_global_id", "template_version", "template_expected_version",
    ),
    "tooling_mappings.csv": (
        "source_key", "project_source_key", "tooling_global_id", "target_version", "target_snapshot_hash",
    ),
    "file_index.csv": (
        "source_key", "project_source_key", "file_revision_global_id", "file_optimistic_version", "file_sha256",
    ),
    "npi_references.csv": (
        "source_key", "project_source_key", "reference_type", "source_system", "source_object_id",
    ),
}


def csv_bytes(name: str, row: list[str]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(HEADERS[name])
    writer.writerow(row)
    return stream.getvalue().encode()


def bundle(*, project_title: str = "Historical mold", extra: dict[str, bytes] | None = None) -> bytes:
    members = {
        "projects.csv": csv_bytes(
            "projects.csv",
            [
                "project-01", "NPI-H-001", project_title, "new_tool",
                "owner@example.invalid", "2026-10-01",
                "00000000-0000-4000-8000-000000000010", "1", "1",
            ],
        ),
        "tooling_mappings.csv": csv_bytes(
            "tooling_mappings.csv",
            ["tooling-01", "project-01", "00000000-0000-4000-8000-000000000020", "2", "a" * 64],
        ),
        "file_index.csv": csv_bytes(
            "file_index.csv",
            ["file-01", "project-01", "00000000-0000-4000-8000-000000000030", "3", "b" * 64],
        ),
        "npi_references.csv": csv_bytes(
            "npi_references.csv",
            ["reference-01", "project-01", "customer", "ERPNEXT", "customer-reference-01"],
        ),
    }
    if extra:
        members.update(extra)
    manifest = {
        "schemaVersion": BUNDLE_SCHEMA_VERSION,
        "bundleId": "00000000-0000-4000-8000-000000000001",
        "sourceSystem": "LEGACY_NPI",
        "members": [
            {"name": name, "sha256": hashlib.sha256(content).hexdigest(), "rowCount": 1}
            for name, content in sorted(members.items())
            if name in HEADERS
        ],
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        for name, content in members.items():
            archive.writestr(name, content)
    return output.getvalue()


class Phase9HistoricalMigrationBundleTest(unittest.TestCase):
    def test_exact_bundle_is_deterministic_and_covers_four_closed_families(self) -> None:
        content = bundle()
        inspected = inspect_bundle(content, expected_sha256=hashlib.sha256(content).hexdigest())
        self.assertEqual(inspected.bundle_id, UUID("00000000-0000-4000-8000-000000000001"))
        self.assertEqual(inspected.source_system, "LEGACY_NPI")
        self.assertEqual({row.family for row in inspected.rows}, set(MigrationFamily))
        self.assertEqual(len(inspected.rows), 4)
        self.assertFalse([finding for row in inspected.rows for finding in row.findings])
        self.assertTrue(all(len(row.source_hash) == 64 for row in inspected.rows))

    def test_archive_rejects_extra_members_hash_drift_and_formula_markers(self) -> None:
        unsafe = bundle(extra={"unexpected.txt": b"not allowed"})
        with self.assertRaises(RequestValidationFailed):
            inspect_bundle(unsafe, expected_sha256=hashlib.sha256(unsafe).hexdigest())
        clean = bundle()
        with self.assertRaises(RequestValidationFailed):
            inspect_bundle(clean, expected_sha256="f" * 64)
        formula = bundle(project_title="=HYPERLINK(\"https://invalid.example\")")
        with self.assertRaises(RequestValidationFailed):
            inspect_bundle(formula, expected_sha256=hashlib.sha256(formula).hexdigest())

    def test_row_validation_reports_missing_project_reference_without_mutation(self) -> None:
        content = bundle()
        source = io.BytesIO(content)
        output = io.BytesIO()
        with zipfile.ZipFile(source) as original, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as revised:
            members = {name: original.read(name) for name in original.namelist() if name != "manifest.json"}
            members["file_index.csv"] = csv_bytes(
                "file_index.csv",
                ["file-01", "missing-project", "00000000-0000-4000-8000-000000000030", "3", "b" * 64],
            )
            manifest = json.loads(original.read("manifest.json"))
            for entry in manifest["members"]:
                entry["sha256"] = hashlib.sha256(members[entry["name"]]).hexdigest()
            revised.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
            for name, value in members.items():
                revised.writestr(name, value)
        changed = output.getvalue()
        inspected = inspect_bundle(changed, expected_sha256=hashlib.sha256(changed).hexdigest())
        file_row = next(row for row in inspected.rows if row.family is MigrationFamily.FILE_INDEX)
        self.assertEqual([item.code for item in file_row.findings], ["missing_project_reference"])


if __name__ == "__main__":
    unittest.main()
