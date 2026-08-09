from __future__ import annotations

import importlib.util
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
INSPECTOR_PATH = (
    REPOSITORY_ROOT
    / ".agents"
    / "skills"
    / "xlsx-tooling-import"
    / "scripts"
    / "inspect_xlsx.py"
)


def _load_inspector():
    specification = importlib.util.spec_from_file_location(
        "xlsx_tooling_inspector", INSPECTOR_PATH
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _write_minimal_xlsx(
    path: Path,
    *,
    external: bool = False,
    relationship_kind: str = "worksheet",
    error_value: str = "#REF!",
    workbook_content_type: str = "",
) -> None:
    content_type_override = (
        '<Override PartName="/xl/workbook.xml" '
        f'ContentType="{workbook_content_type}"/>'
        if workbook_content_type
        else ""
    )
    external_relationship = (
        '<Relationship Id="external" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        'relationships/externalLink" Target="https://example.invalid/data" '
        'TargetMode="External"/>'
        if external
        else ""
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/'
            f'content-types">{content_type_override}</Types>',
        )
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/'
            'spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships"><sheets><sheet name="Tooling List" sheetId="1" '
            'r:id="sheet1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/'
            '2006/relationships"><Relationship Id="sheet1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            f'relationships/{relationship_kind}" '
            'Target="worksheets/sheet1.xml"/>'
            f"{external_relationship}</Relationships>",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/'
            'spreadsheetml/2006/main"><dimension ref="A1:B2"/>'
            '<sheetData><row r="1"><c r="A1" t="inlineStr"><is>'
            '<t>Mold No.</t></is></c></row><row r="2">'
            f'<c r="B2" t="e"><f>A2+1</f><v>{error_value}</v></c>'
            "</row></sheetData></worksheet>",
        )


class XlsxToolingImportInspectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inspector = _load_inspector()

    def test_reports_structure_and_formula_error_without_cell_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workbook = Path(directory) / "tooling.xlsx"
            _write_minimal_xlsx(workbook)

            report = self.inspector.inspect(workbook, 100, 1_000_000)

        self.assertEqual(report["worksheet_count"], 1)
        self.assertEqual(report["sheets"][0]["dimension"], "A1:B2")
        self.assertEqual(report["sheets"][0]["formula_count"], 1)
        self.assertEqual(
            report["formula_errors"],
            [{"sheet": "Tooling List", "cell": "B2", "error": "#REF!"}],
        )
        self.assertNotIn("Mold No.", str(report))

    def test_rejects_external_relationships(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workbook = Path(directory) / "tooling.xlsx"
            _write_minimal_xlsx(workbook, external=True)

            with self.assertRaisesRegex(
                self.inspector.WorkbookRejected,
                "external XLSX relationships",
            ):
                self.inspector.inspect(workbook, 100, 1_000_000)

    def test_rejects_archive_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workbook = Path(directory) / "tooling.xlsx"
            _write_minimal_xlsx(workbook)
            with zipfile.ZipFile(workbook, "a") as archive:
                archive.writestr("../escape.xml", "<escape/>")

            with self.assertRaisesRegex(
                self.inspector.WorkbookRejected,
                "unsafe archive member path",
            ):
                self.inspector.inspect(workbook, 100, 1_000_000)

    def test_unknown_error_cell_value_is_not_emitted(self) -> None:
        secret = "customer-secret-value"
        with tempfile.TemporaryDirectory() as directory:
            workbook = Path(directory) / "tooling.xlsx"
            _write_minimal_xlsx(workbook, error_value=secret)

            report = self.inspector.inspect(workbook, 100, 1_000_000)

        self.assertEqual(
            report["formula_errors"],
            [
                {
                    "sheet": "Tooling List",
                    "cell": "B2",
                    "error": "FORMULA_ERROR",
                }
            ],
        )
        self.assertNotIn(secret, str(report))

    def test_rejects_xlm_macro_sheet_relationship(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workbook = Path(directory) / "tooling.xlsx"
            _write_minimal_xlsx(
                workbook,
                relationship_kind="xlMacrosheet",
            )

            with self.assertRaisesRegex(
                self.inspector.WorkbookRejected,
                "active or macro-enabled",
            ):
                self.inspector.inspect(workbook, 100, 1_000_000)

    def test_rejects_duplicate_archive_members(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workbook = Path(directory) / "tooling.xlsx"
            _write_minimal_xlsx(workbook)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(workbook, "a") as archive:
                    archive.writestr("xl/workbook.xml", "<duplicate/>")

            with self.assertRaisesRegex(
                self.inspector.WorkbookRejected,
                "duplicate or canonically colliding",
            ):
                self.inspector.inspect(workbook, 100, 1_000_000)

    def test_rejects_case_colliding_archive_members(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workbook = Path(directory) / "tooling.xlsx"
            _write_minimal_xlsx(workbook)
            with zipfile.ZipFile(workbook, "a") as archive:
                archive.writestr("XL/workbook.xml", "<collision/>")

            with self.assertRaisesRegex(
                self.inspector.WorkbookRejected,
                "duplicate or canonically colliding",
            ):
                self.inspector.inspect(workbook, 100, 1_000_000)

    def test_rejects_unbounded_drawing_anchor_as_controlled_error(self) -> None:
        with self.assertRaisesRegex(
            self.inspector.WorkbookRejected,
            "invalid drawing row index",
        ):
            self.inspector._bounded_anchor_index("9" * 5_000, 1_048_575, "row")

    def test_rejects_dtd_and_entity_declarations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workbook = Path(directory) / "tooling.xlsx"
            _write_minimal_xlsx(workbook)
            with zipfile.ZipFile(workbook, "r") as source:
                parts = {
                    info.filename: source.read(info.filename)
                    for info in source.infolist()
                }
            parts["xl/workbook.xml"] = (
                b'<?xml version="1.0"?>'
                b'<!DOCTYPE workbook [<!ENTITY secret "expanded">]>'
                b'<workbook xmlns="http://schemas.openxmlformats.org/'
                b'spreadsheetml/2006/main">&secret;</workbook>'
            )
            with zipfile.ZipFile(workbook, "w") as target:
                for name, payload in parts.items():
                    target.writestr(name, payload)

            with self.assertRaisesRegex(
                self.inspector.WorkbookRejected,
                "DTD or entity declaration",
            ):
                self.inspector.inspect(workbook, 100, 1_000_000)

    def test_rejects_input_before_hashing_when_file_limit_is_exceeded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workbook = Path(directory) / "tooling.xlsx"
            _write_minimal_xlsx(workbook)

            with self.assertRaisesRegex(
                self.inspector.WorkbookRejected,
                "input file size limit",
            ):
                self.inspector.inspect(
                    workbook,
                    100,
                    1_000_000,
                    max_input_bytes=1,
                )

    def test_rejects_utf16_dtd_and_entity_declarations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workbook = Path(directory) / "tooling.xlsx"
            _write_minimal_xlsx(workbook)
            with zipfile.ZipFile(workbook, "r") as source:
                parts = {
                    info.filename: source.read(info.filename)
                    for info in source.infolist()
                }
            parts["xl/workbook.xml"] = (
                '<?xml version="1.0" encoding="UTF-16"?>'
                '<!DOCTYPE workbook [<!ENTITY secret "expanded">]>'
                '<workbook xmlns="http://schemas.openxmlformats.org/'
                'spreadsheetml/2006/main">&secret;</workbook>'
            ).encode("utf-16")
            with zipfile.ZipFile(workbook, "w") as target:
                for name, payload in parts.items():
                    target.writestr(name, payload)

            with self.assertRaisesRegex(
                self.inspector.WorkbookRejected,
                "DTD or entity declaration",
            ):
                self.inspector.inspect(workbook, 100, 1_000_000)

    def test_rejects_macro_enabled_workbook_content_type(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workbook = Path(directory) / "tooling.xlsx"
            _write_minimal_xlsx(
                workbook,
                workbook_content_type=(
                    "application/vnd.ms-excel.sheet.macroEnabled.main+xml"
                ),
            )

            with self.assertRaisesRegex(
                self.inspector.WorkbookRejected,
                "active or macro-enabled",
            ):
                self.inspector.inspect(workbook, 100, 1_000_000)

    def test_rejects_unreferenced_binary_parts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workbook = Path(directory) / "tooling.xlsx"
            _write_minimal_xlsx(workbook)
            with zipfile.ZipFile(workbook, "a") as archive:
                archive.writestr("xl/activeX/activeX1.bin", b"active-content")

            with self.assertRaisesRegex(
                self.inspector.WorkbookRejected,
                "active or embedded binary",
            ):
                self.inspector.inspect(workbook, 100, 1_000_000)

    def test_rejects_crc_failure_in_unreferenced_member(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workbook = Path(directory) / "tooling.xlsx"
            _write_minimal_xlsx(workbook)
            marker = b"crc-check-payload"
            with zipfile.ZipFile(workbook, "a") as archive:
                archive.writestr("unused.txt", marker)
            archive_bytes = bytearray(workbook.read_bytes())
            marker_offset = archive_bytes.index(marker)
            archive_bytes[marker_offset] ^= 0x01
            workbook.write_bytes(archive_bytes)

            with self.assertRaisesRegex(
                self.inspector.WorkbookRejected,
                "integrity validation",
            ):
                self.inspector.inspect(workbook, 100, 1_000_000)


if __name__ == "__main__":
    unittest.main()
