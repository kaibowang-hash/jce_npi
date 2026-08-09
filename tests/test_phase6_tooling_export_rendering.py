from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
import unittest
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.tooling.export_domain import (
    TOOLING_OBJECT_PACKAGE_MIME_TYPE,
    ToolingExportLanguage,
    ToolingExportMode,
    ToolingListRow,
    ToolingSource,
)
from npi_core.tooling.export_rendering import (
    CSV_SOURCE_STRINGS,
    OMITTED_FIELD_CLASSES,
    PACKAGE_MEMBER_NAMES,
    package_render_snapshot,
    render_tooling_object_package,
)


PROJECT_ID = UUID("99000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 8, 10, 4, 5, 6, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[1]


def _row(title: str = "Tooling A") -> ToolingListRow:
    return ToolingListRow(
        tooling_master_global_id=UUID("99000000-0000-4000-8000-000000000002"),
        tooling_master_snapshot_hash="a" * 64,
        title=title,
        project_global_id=PROJECT_ID,
        project_code="NPI-990",
        originating_project_global_id=UUID("99000000-0000-4000-8000-000000000003"),
        applicability_count=2,
        distinct_part_revision_count=2,
        physical_set_count=1,
        design_revision_count=0,
        latest_revision_number=None,
        customer_owned_set=False,
        source=ToolingSource.CONTROLLED_XLSX_IMPORT,
    )


def _translate(source: str) -> str:
    return {
        "Project code": "项目编码",
        "Tooling Master ID": "模具主数据标识",
        "Tooling title": "模具标题",
        "Tooling snapshot hash": "模具快照哈希",
        "Originating Project ID": "来源项目标识",
        "Applicability count": "适用关系数",
        "Distinct Part Revision count": "不同零件修订数",
        "Physical set count": "实体模具套数",
        "Latest revision": "最新修订",
        "Source": "来源",
        "Generated at": "生成时间",
        "Tooling object package": "模具对象包",
        "Confidentiality: Internal project use": "机密级别：项目内部使用",
        "Generated from an immutable Tooling List snapshot.": "由不可变模具清单快照生成。",
        "Rows: {row_count}": "行数：{row_count}",
        "Unavailable": "不可用",
        "Manual": "手工创建",
        "Controlled XLSX import": "受控 XLSX 导入",
    }[source]


class Phase6ToolingExportRenderingTests(unittest.TestCase):
    def _render(self, title: str = "Tooling A"):
        return render_tooling_object_package(
            rows=(_row(title),),
            project_global_id=PROJECT_ID,
            project_code="NPI-990",
            mode=ToolingExportMode.SELECTION,
            language=ToolingExportLanguage.SIMPLIFIED_CHINESE,
            query_snapshot_hash=None,
            generated_at=NOW,
            translate=_translate,
        )

    def test_package_is_deterministic_private_zip_with_exact_three_members(self) -> None:
        first = self._render()
        second = self._render()
        self.assertEqual(first.content, second.content)
        self.assertEqual(first.mime_type, TOOLING_OBJECT_PACKAGE_MIME_TYPE)
        self.assertEqual(first.size_bytes, len(first.content))
        self.assertEqual(first.sha256, hashlib.sha256(first.content).hexdigest())
        with zipfile.ZipFile(io.BytesIO(first.content)) as archive:
            self.assertEqual(tuple(archive.namelist()), PACKAGE_MEMBER_NAMES)
            self.assertFalse(any(not item.filename for item in archive.infolist()))
            manifest_bytes = archive.read("manifest.json")
            manifest = json.loads(manifest_bytes)
            self.assertEqual(first.manifest_sha256, hashlib.sha256(manifest_bytes).hexdigest())
            self.assertEqual(manifest["schemaVersion"], "tooling-object-package-v1")
            self.assertEqual(manifest["confidentialityClass"], "internal_project")
            self.assertIsNone(manifest["querySnapshotHash"])
            self.assertEqual(manifest["rowCount"], 1)
            self.assertEqual(tuple(manifest["omittedFieldClasses"]), OMITTED_FIELD_CLASSES)
            self.assertNotIn("fileUrl", json.dumps(manifest))
            self.assertNotIn("actualCost", json.dumps(manifest))

    def test_csv_is_localized_allowlisted_and_formula_safe(self) -> None:
        rendered = self._render("  =HYPERLINK(\"https://invalid.example\")")
        with zipfile.ZipFile(io.BytesIO(rendered.content)) as archive:
            csv_bytes = archive.read("tooling-objects.csv")
            self.assertTrue(csv_bytes.startswith(b"\xef\xbb\xbf"))
            rows = list(csv.reader(io.StringIO(csv_bytes[3:].decode("utf-8"))))
            self.assertEqual(rows[0], [_translate(item) for item in CSV_SOURCE_STRINGS])
            self.assertTrue(rows[1][2].startswith("'="))
            self.assertEqual(rows[1][8], "不可用")
            self.assertEqual(rows[1][9], "受控 XLSX 导入")
            self.assertEqual(len(rows[0]), 11)

    def test_readme_is_localized_and_render_snapshot_contains_only_hash_metadata(self) -> None:
        rendered = self._render()
        with zipfile.ZipFile(io.BytesIO(rendered.content)) as archive:
            readme = archive.read("README.txt").decode("utf-8")
        self.assertIn("模具对象包", readme)
        self.assertIn("行数：1", readme)
        snapshot = package_render_snapshot(rendered)
        self.assertEqual(snapshot["mimeType"], "application/zip")
        self.assertEqual(set(snapshot["memberSha256"]), set(PACKAGE_MEMBER_NAMES))
        self.assertNotIn("content", snapshot)

    def test_filtered_package_requires_exact_query_snapshot_hash(self) -> None:
        with self.assertRaises(ValueError):
            render_tooling_object_package(
                rows=(_row(),),
                project_global_id=PROJECT_ID,
                project_code="NPI-990",
                mode=ToolingExportMode.FILTERED,
                language=ToolingExportLanguage.ENGLISH,
                query_snapshot_hash=None,
                generated_at=NOW,
                translate=lambda source: source,
            )

    def test_all_three_languages_render_from_the_frappe_catalog_chain(self) -> None:
        archives: set[str] = set()
        for language in ToolingExportLanguage:
            if language is ToolingExportLanguage.ENGLISH:
                translate = lambda source: source
            else:
                catalog_path = (
                    ROOT
                    / "apps/npi_core/npi_core/translations"
                    / f"{language.value}.csv"
                )
                with catalog_path.open(encoding="utf-8", newline="") as handle:
                    catalog = {row[0]: row[1] for row in csv.reader(handle) if len(row) >= 2}
                translate = lambda source, catalog=catalog: catalog[source]
            rendered = render_tooling_object_package(
                rows=(_row(),),
                project_global_id=PROJECT_ID,
                project_code="NPI-990",
                mode=ToolingExportMode.SELECTION,
                language=language,
                query_snapshot_hash=None,
                generated_at=NOW,
                translate=translate,
            )
            with zipfile.ZipFile(io.BytesIO(rendered.content)) as archive:
                manifest = json.loads(archive.read("manifest.json"))
                rows = list(
                    csv.reader(
                        io.StringIO(
                            archive.read("tooling-objects.csv")[3:].decode("utf-8")
                        )
                    )
                )
            self.assertEqual(manifest["language"], language.value)
            self.assertEqual(rows[0][0], translate("Project code"))
            archives.add(rendered.sha256)
        self.assertEqual(len(archives), 3)


if __name__ == "__main__":
    unittest.main()
