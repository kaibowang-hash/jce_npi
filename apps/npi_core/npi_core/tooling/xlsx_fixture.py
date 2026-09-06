"""Deterministic, visibly synthetic XLSX fixtures for P6-07 verification."""

from __future__ import annotations

import hashlib
import html
import json
import zipfile
from pathlib import Path

SYNTHETIC_HEADERS = (
    "Item",
    "Mold No.",
    "Part Name English",
    "Chinese name",
    "Picture",
    "appearance part Y/N",
    "Model",
    "SN P/N",
    "KW P/N",
    "TH Part Number",
    "KW Tooling No.",
    "Cavity",
    "Usage Per Unit",
    "Part Material",
    "Material trademark",
    "FDA",
    "secondary process",
    "Material Grade",
    "Color Master CN",
    "Color description",
    "Lijun code",
    "Color Master Thailand",
    "calculated weight",
    "actual weight",
    "runner weight",
    "allocated runner + net per cavity",
    "injection cycle seconds",
    "Supplier",
    "tonnage",
    "initial tooling set quantity",
    "single-set daily output",
    "single-set daily assembly units",
    "copied tooling sets",
    "total tooling sets",
    "total daily output",
    "total daily assembly units",
    "monthly capacity",
    "common tooling Y/N",
    "A",
    "B",
    "C",
    "remarks",
    "unnamed trailing note",
)

FIXTURE_VERSION = "p6-07.synthetic-tooling-list.v1"
_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_TRANSPARENT_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360000000020001e221bc330000000049454e44ae426082"
)


def _column_letters(index: int) -> str:
    value = index
    result = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


def _inline_cell(reference: str, value: str) -> str:
    escaped = html.escape(value, quote=False)
    preserve = ' xml:space="preserve"' if value != value.strip() or "\n" in value else ""
    return (
        f'<c r="{reference}" t="inlineStr"><is><t{preserve}>'
        f"{escaped}</t></is></c>"
    )


def _formula_error_cell(reference: str) -> str:
    return f'<c r="{reference}" t="e"><f>1/0+#REF!</f><v>#REF!</v></c>'


def _row_xml(row_number: int, values: list[str], formula_error_column: int | None = None) -> str:
    cells: list[str] = []
    for index, value in enumerate(values, start=1):
        reference = f"{_column_letters(index)}{row_number}"
        if formula_error_column == index:
            cells.append(_formula_error_cell(reference))
        elif value != "":
            cells.append(_inline_cell(reference, value))
    return f'<row r="{row_number}">{"".join(cells)}</row>'


def _synthetic_rows(title_row_count: int) -> tuple[list[str], int, int, int]:
    rows = [
        _row_xml(index + 1, [f"Synthetic NPI Tooling Fixture Title {index + 1}"])
        for index in range(title_row_count)
    ]
    header_row = title_row_count + 1
    rows.append(_row_xml(header_row, list(SYNTHETIC_HEADERS)))

    first_data_row = header_row + 1
    first = [""] * len(SYNTHETIC_HEADERS)
    first[0] = "1"
    first[1] = "SYN-MOLD-001"
    first[2] = "Synthetic Housing"
    first[3] = "合成外壳"
    first[5] = "Y"
    first[6] = "MODEL-A / MODEL-B"
    first[7] = "SN-001\nSN-002"
    first[8] = "KW-001"
    first[9] = "TH-001"
    first[10] = "SYN-TOOL-001\nNew Tooling"
    first[11] = "2"
    first[12] = "1"
    first[13] = "PP"
    first[14] = "SYNTHETIC-BRAND"
    first[15] = "N"
    first[16] = "No"
    first[17] = "SYN-GRADE"
    first[18] = "SYN-COLOR-CN"
    first[19] = "Synthetic neutral"
    first[20] = "SYN-LJ-01"
    first[21] = "SYN-COLOR-TH"
    first[22] = "12 g"
    first[23] = "13 gram"
    first[24] = "4 g"
    first[25] = "15 g"
    first[26] = "42 s"
    first[27] = "SYNTHETIC SUPPLIER"
    first[28] = "180 T / dual-shot machine"
    first[29] = "1"
    first[30] = "1000"
    first[31] = "1000"
    first[32] = "0"
    first[33] = "1"
    first[35] = "1000"
    first[36] = "26000"
    first[37] = "N"
    first[38] = "A-RAW"
    first[39] = "B-RAW"
    first[40] = "C-RAW"
    first[41] = "Dual-shot / overmold; insert candidate; confirm relation"
    first[42] = "Synthetic unmapped value"
    rows.append(_row_xml(first_data_row, first, formula_error_column=35))

    second_data_row = first_data_row + 1
    second = [""] * len(SYNTHETIC_HEADERS)
    second[0] = "2"
    second[2] = ""
    second[6] = "MODEL-C"
    second[10] = "New Tooling"
    second[11] = "two"
    second[13] = "ABS"
    second[22] = "0.012 kg"
    second[23] = "12 g"
    second[28] = "vertical machine"
    second[37] = "N"
    second[38] = "undefined-A"
    second[41] = "Blank required name; ambiguous image and insert relation"
    rows.append(_row_xml(second_data_row, second))

    shared_marker_row = second_data_row + 1
    rows.append(_row_xml(shared_marker_row, ["Shared Tooling Section"]))
    shared_data = [""] * len(SYNTHETIC_HEADERS)
    shared_data[0] = "3"
    shared_data[1] = "SYN-MOLD-SHARED"
    shared_data[2] = "Synthetic Shared Cover"
    shared_data[6] = "MODEL-D / MODEL-E"
    shared_data[10] = "SYN-TOOL-SHARED"
    shared_data[11] = "4"
    shared_data[13] = "ABS+PC"
    shared_data[37] = "Y"
    rows.append(_row_xml(shared_marker_row + 1, shared_data))

    summary_row = shared_marker_row + 2
    rows.append(_row_xml(summary_row, ["Color Master Summary", "Synthetic summary only"]))
    return rows, header_row, first_data_row, second_data_row


def build_sanitized_tooling_workbook(path: Path, *, title_row_count: int) -> dict[str, object]:
    if title_row_count not in {1, 3}:
        raise ValueError("synthetic fixture title_row_count must be 1 or 3")
    rows, header_row, first_data_row, second_data_row = _synthetic_rows(title_row_count)
    last_row = len(rows)
    worksheet = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<dimension ref="A1:AQ{last_row}"/><sheetData>{"".join(rows)}</sheetData>'
        '<drawing r:id="drawing1"/></worksheet>'
    )
    drawing = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing">'
        '<xdr:oneCellAnchor><xdr:from>'
        f'<xdr:col>4</xdr:col><xdr:row>{first_data_row - 1}</xdr:row>'
        '</xdr:from></xdr:oneCellAnchor>'
        '<xdr:oneCellAnchor><xdr:from>'
        f'<xdr:col>4</xdr:col><xdr:row>{second_data_row - 1}</xdr:row>'
        '</xdr:from></xdr:oneCellAnchor>'
        '</xdr:wsDr>'
    )
    parts = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="png" ContentType="image/png"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/drawings/drawing1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>'
            '</Types>'
        ).encode(),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="officeDocument" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>'
        ).encode(),
        "xl/workbook.xml": (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Synthetic Tooling List" sheetId="1" r:id="sheet1"/></sheets>'
            '</workbook>'
        ).encode(),
        "xl/_rels/workbook.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="sheet1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '</Relationships>'
        ).encode(),
        "xl/worksheets/sheet1.xml": worksheet.encode(),
        "xl/worksheets/_rels/sheet1.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="drawing1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" Target="../drawings/drawing1.xml"/>'
            '</Relationships>'
        ).encode(),
        "xl/drawings/drawing1.xml": drawing.encode(),
        "xl/drawings/_rels/drawing1.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="image1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png"/>'
            '<Relationship Id="image2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image2.png"/>'
            '</Relationships>'
        ).encode(),
        "xl/media/image1.png": _TRANSPARENT_PNG,
        "xl/media/image2.png": _TRANSPARENT_PNG,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(parts):
            info = zipfile.ZipInfo(name, _ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o600 << 16
            archive.writestr(info, parts[name], compress_type=zipfile.ZIP_STORED)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "fixtureVersion": FIXTURE_VERSION,
        "fileName": path.name,
        "sha256": digest,
        "synthetic": True,
        "titleRowCount": title_row_count,
        "headerRow": header_row,
        "sourceColumnCount": len(SYNTHETIC_HEADERS),
        "containsCustomerData": False,
    }


def build_fixture_set(directory: Path) -> dict[str, object]:
    fixtures = [
        build_sanitized_tooling_workbook(
            directory / "p6-07-synthetic-title-row-deleted.xlsx",
            title_row_count=1,
        ),
        build_sanitized_tooling_workbook(
            directory / "p6-07-synthetic-title-rows-inserted.xlsx",
            title_row_count=3,
        ),
    ]
    manifest = {
        "fixtureVersion": FIXTURE_VERSION,
        "provenance": "Deterministically generated synthetic verification data; no customer workbook values.",
        "containsCustomerData": False,
        "fixtures": fixtures,
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
