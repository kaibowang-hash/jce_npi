from __future__ import annotations

import csv
import io
import json
import sys
import unittest
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_core"))

from npi_core.data_exchange.domain import DatasetId, ExportLanguage, ExportProfileVersion, RedactionProfile
from npi_core.data_exchange.export_package import PACKAGE_MEMBERS, render_report_package


NOW = datetime(2026, 9, 3, 9, 0, tzinfo=UTC)


def profile(**overrides):
    values = {
        "global_id": UUID("00000000-0000-4000-8000-000000000071"),
        "version": 1,
        "dataset_id": DatasetId.PROJECT_PORTFOLIO,
        "columns": ("projectCode", "title", "ownerUserId"),
        "language": ExportLanguage.ENGLISH,
        "redaction_profile": RedactionProfile.INTERNAL_REPORT,
        "query": (),
        "max_rows": 20,
        "max_bytes": 1_000_000,
        "published_by_user_id": "manager@example.invalid",
        "published_at": NOW,
    }
    values.update(overrides)
    return ExportProfileVersion(**values)


class Phase9DataExchangePackageTest(unittest.TestCase):
    def render(self, rows, **profile_values):
        return render_report_package(
            profile=profile(**profile_values),
            rows=rows,
            generated_at=NOW,
            actor_user_id="manager@example.invalid",
            translate=lambda source: source,
            render_pdf=lambda document: b"%PDF-1.7\n" + document.encode("utf-8"),
        )

    def test_package_is_deterministic_closed_hashed_and_formula_safe(self) -> None:
        rows = ({"projectCode": "=2+2", "title": "+unsafe", "ownerUserId": "owner@example.invalid", "secret": "never"},)
        first = self.render(rows)
        second = self.render(rows)
        self.assertEqual(first.content, second.content)
        self.assertEqual(first.sha256, second.sha256)
        with zipfile.ZipFile(io.BytesIO(first.content)) as archive:
            self.assertEqual(tuple(archive.namelist()), PACKAGE_MEMBERS)
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["columns"], ["projectCode", "title", "ownerUserId"])
            self.assertNotIn("secret", str(manifest))
            csv_rows = list(csv.reader(io.StringIO(archive.read("report.csv").decode("utf-8-sig"))))
            self.assertEqual(csv_rows[1][0], "'=2+2")
            self.assertEqual(csv_rows[1][1], "'+unsafe")
            self.assertNotIn(b"secret", archive.read("report.xlsx"))
            self.assertTrue(archive.read("report.pdf").startswith(b"%PDF-"))

    def test_empty_report_is_valid_and_limits_fail_closed(self) -> None:
        rendered = self.render(())
        with zipfile.ZipFile(io.BytesIO(rendered.content)) as archive:
            self.assertEqual(json.loads(archive.read("manifest.json"))["rowCount"], 0)
        with self.assertRaises(ValueError):
            self.render(({"projectCode": "P1"}, {"projectCode": "P2"}), max_rows=1)
        with self.assertRaises(ValueError):
            render_report_package(
                profile=profile(), rows=(), generated_at=NOW,
                actor_user_id="manager@example.invalid", translate=lambda source: source,
                render_pdf=lambda _document: b"not-pdf",
            )

    def test_structural_redaction_excludes_owner_from_every_member(self) -> None:
        rendered = self.render(
            ({"projectCode": "P1", "title": "Project", "ownerUserId": "private@example.invalid"},),
            columns=("projectCode", "title"),
            redaction_profile=RedactionProfile.MINIMUM_DISCLOSURE,
        )
        with zipfile.ZipFile(io.BytesIO(rendered.content)) as archive:
            for name in PACKAGE_MEMBERS:
                self.assertNotIn(b"private@example.invalid", archive.read(name))


if __name__ == "__main__":
    unittest.main()
