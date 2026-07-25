#!/usr/bin/env python3
"""Inspect XLSX structure and hazards without executing or extracting content."""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree  # nosec B405
from xml.parsers import expat

SPREADSHEET = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
OFFICE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
DRAWING = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"

NS = {
    "s": SPREADSHEET,
    "r": OFFICE_REL,
    "p": PACKAGE_REL,
    "xdr": DRAWING,
    "ct": CONTENT_TYPES,
}
CELL_REFERENCE = re.compile(r"^[A-Z]{1,3}[1-9][0-9]*$")
URI_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
EXCEL_ERROR_CODES = {
    "#NULL!",
    "#DIV/0!",
    "#VALUE!",
    "#REF!",
    "#NAME?",
    "#NUM!",
    "#N/A",
    "#GETTING_DATA",
    "#SPILL!",
    "#CALC!",
    "#FIELD!",
    "#BLOCKED!",
    "#UNKNOWN!",
    "#CONNECT!",
    "#BUSY!",
    "#PYTHON!",
    "#DATA!",
}
ACTIVE_RELATIONSHIP_SUFFIXES = {
    "/activeXControl",
    "/activeXControlBinary",
    "/control",
    "/customUI",
    "/dialogsheet",
    "/intlMacrosheet",
    "/macrosheet",
    "/oleObject",
    "/package",
    "/vbaProject",
    "/xlMacrosheet",
}
ACTIVE_CONTENT_TYPE_FRAGMENTS = {
    "activex",
    "controlproperties",
    "dialogsheet",
    "intlmacrosheet",
    "macroenabled",
    "macrosheet",
    "oleobject",
    "vbaproject",
}
ACTIVE_PART_PATH_FRAGMENTS = {
    "/activex/",
    "/ctrlprops/",
    "/dialogsheets/",
    "/embeddings/",
    "/macrosheets/",
    "/printersettings/",
}
MAX_INPUT_BYTES = 100_000_000
MAX_XML_PART_BYTES = 10_000_000
MAX_XML_ELEMENTS = 500_000
MAX_XML_DEPTH = 256
MAX_WORKSHEETS = 256
MAX_CELLS_PER_SHEET = 1_100_000
MAX_ROWS_PER_SHEET = 1_048_576
MAX_MERGED_CELLS_PER_SHEET = 100_000
MAX_DRAWING_ANCHORS = 100_000
MAX_SHARED_STRINGS = 2_000_000


class WorkbookRejected(RuntimeError):
    """Raised when the workbook archive is unsafe or outside inspection limits."""


def _safe_member_name(name: str) -> str:
    if "\\" in name:
        raise WorkbookRejected(f"archive member uses a backslash path: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise WorkbookRejected(f"unsafe archive member path: {name!r}")
    return path.as_posix()


def _resolve_part(base_part: str, target: str) -> str:
    if target.startswith(("/", "//")) or "\\" in target or URI_SCHEME.match(target):
        raise WorkbookRejected(f"unsafe relationship target: {target!r}")
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(base_part), target))
    _safe_member_name(resolved)
    return resolved


def _parse_xml(archive: zipfile.ZipFile, name: str) -> ElementTree.Element:
    try:
        info = archive.getinfo(name)
    except KeyError as error:
        raise WorkbookRejected(f"required XLSX part is missing: {name}") from error
    if info.file_size > MAX_XML_PART_BYTES:
        raise WorkbookRejected(f"XLSX XML part exceeds safety limit: {name}")
    try:
        payload = archive.read(name)
    except (RuntimeError, zipfile.BadZipFile) as error:
        raise WorkbookRejected(f"unable to read XLSX part safely: {name}") from error

    upper_payload = payload.upper()
    if b"<!DOCTYPE" in upper_payload or b"<!ENTITY" in upper_payload:
        raise WorkbookRejected(f"DTD or entity declaration is not accepted: {name}")

    element_count = 0
    depth = 0
    parser = expat.ParserCreate()

    def start_element(_name: str, _attributes: dict[str, str]) -> None:
        nonlocal element_count, depth
        element_count += 1
        depth += 1
        if element_count > MAX_XML_ELEMENTS:
            raise WorkbookRejected(f"XLSX XML element limit exceeded: {name}")
        if depth > MAX_XML_DEPTH:
            raise WorkbookRejected(f"XLSX XML depth limit exceeded: {name}")

    def end_element(_name: str) -> None:
        nonlocal depth
        depth -= 1

    parser.StartElementHandler = start_element
    parser.EndElementHandler = end_element

    def reject_declaration(*_arguments: object) -> None:
        raise WorkbookRejected(f"DTD or entity declaration is not accepted: {name}")

    parser.StartDoctypeDeclHandler = reject_declaration
    parser.EntityDeclHandler = reject_declaration
    parser.ExternalEntityRefHandler = reject_declaration
    try:
        parser.Parse(payload, True)
        return ElementTree.fromstring(payload)  # nosec B314
    except WorkbookRejected:
        raise
    except (expat.ExpatError, ElementTree.ParseError) as error:
        raise WorkbookRejected(f"invalid XML in XLSX part: {name}") from error


def _relationship_is_active(relationship_type: str) -> bool:
    return any(
        relationship_type.endswith(suffix) for suffix in ACTIVE_RELATIONSHIP_SUFFIXES
    )


def _validate_passive_package(archive: zipfile.ZipFile, names: set[str]) -> None:
    content_types = _parse_xml(archive, "[Content_Types].xml")
    for item in list(content_types):
        content_type = item.attrib.get("ContentType", "").lower()
        if any(fragment in content_type for fragment in ACTIVE_CONTENT_TYPE_FRAGMENTS):
            raise WorkbookRejected(
                "active or macro-enabled workbook content is not accepted"
            )

    if any(name.lower().endswith("vbaproject.bin") for name in names):
        raise WorkbookRejected(
            "active or macro-enabled workbook content is not accepted"
        )
    for name in names:
        normalized_name = f"/{name.lower()}"
        if normalized_name.endswith(".bin") or any(
            fragment in normalized_name for fragment in ACTIVE_PART_PATH_FRAGMENTS
        ):
            raise WorkbookRejected(
                "active or embedded binary workbook content is not accepted"
            )

    for relationships_part in sorted(name for name in names if name.endswith(".rels")):
        relationships_root = _parse_xml(archive, relationships_part)
        for relationship in relationships_root.findall("p:Relationship", NS):
            if relationship.attrib.get("TargetMode") == "External":
                raise WorkbookRejected("external XLSX relationships are not accepted")
            if _relationship_is_active(relationship.attrib.get("Type", "")):
                raise WorkbookRejected(
                    "active or macro-enabled workbook relationships are not " "accepted"
                )


def _relationships(
    archive: zipfile.ZipFile, owner_part: str, relationships_part: str
) -> tuple[dict[str, str], list[dict[str, str]]]:
    root = _parse_xml(archive, relationships_part)
    internal: dict[str, str] = {}
    external: list[dict[str, str]] = []
    for relationship in root.findall("p:Relationship", NS):
        relationship_id = relationship.attrib.get("Id", "")
        target = relationship.attrib.get("Target", "")
        relationship_type = relationship.attrib.get("Type", "")
        if not relationship_id or not target or not relationship_type:
            raise WorkbookRejected(
                f"incomplete relationship in XLSX part: {relationships_part}"
            )
        if relationship_id in internal or any(
            item["relationship_id"] == relationship_id for item in external
        ):
            raise WorkbookRejected(
                f"duplicate relationship ID in XLSX part: {relationships_part}"
            )
        if relationship.attrib.get("TargetMode") == "External":
            external.append(
                {
                    "owner_part": owner_part,
                    "relationship_id": relationship_id,
                    "relationship_type": relationship_type,
                }
            )
            continue
        internal[relationship_id] = _resolve_part(owner_part, target)
    return internal, external


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = _parse_xml(archive, "xl/sharedStrings.xml")
    strings = [
        "".join(node.text or "" for node in item.findall(".//s:t", NS))
        for item in root.findall("s:si", NS)
    ]
    if len(strings) > MAX_SHARED_STRINGS:
        raise WorkbookRejected("shared-string count exceeds safety limit")
    return strings


def _cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//s:is//s:t", NS))
    value = cell.findtext("s:v", default="", namespaces=NS)
    if cell_type == "s" and value:
        try:
            return shared_strings[int(value)]
        except (ValueError, IndexError) as error:
            raise WorkbookRejected("invalid shared-string reference") from error
    return value


def _inspect_sheet(
    archive: zipfile.ZipFile,
    sheet_name: str,
    sheet_part: str,
    shared_strings: list[str],
) -> tuple[dict[str, object], list[dict[str, str]]]:
    root = _parse_xml(archive, sheet_part)
    cells = root.findall(".//s:c", NS)
    rows = root.findall(".//s:row", NS)
    if len(cells) > MAX_CELLS_PER_SHEET:
        raise WorkbookRejected("worksheet cell count exceeds safety limit")
    if len(rows) > MAX_ROWS_PER_SHEET:
        raise WorkbookRejected("worksheet row count exceeds safety limit")
    errors: list[dict[str, str]] = []
    formula_count = 0
    for cell in cells:
        reference = cell.attrib.get("r", "")
        if reference and not CELL_REFERENCE.fullmatch(reference):
            raise WorkbookRejected(f"invalid cell reference: {reference!r}")
        formula = cell.findtext("s:f", default="", namespaces=NS)
        value = _cell_value(cell, shared_strings)
        if formula:
            formula_count += 1
        if "#REF!" in formula:
            error_code = "#REF!"
        elif cell.attrib.get("t") == "e" and value:
            error_code = value if value in EXCEL_ERROR_CODES else "FORMULA_ERROR"
        else:
            error_code = ""
        if error_code:
            errors.append(
                {
                    "sheet": sheet_name,
                    "cell": reference,
                    "error": error_code,
                }
            )

    drawing_ids = [
        drawing.attrib.get(f"{{{OFFICE_REL}}}id", "")
        for drawing in root.findall("s:drawing", NS)
    ]
    dimension = root.find("s:dimension", NS)
    merged_cells = root.findall(".//s:mergeCell", NS)
    if len(merged_cells) > MAX_MERGED_CELLS_PER_SHEET:
        raise WorkbookRejected("merged-cell count exceeds safety limit")
    return (
        {
            "name": sheet_name,
            "part": sheet_part,
            "dimension": (
                dimension.attrib.get("ref", "") if dimension is not None else ""
            ),
            "cell_count": len(cells),
            "formula_count": formula_count,
            "merged_cell_count": len(merged_cells),
            "formula_errors": errors,
            "drawing_relationship_ids": [item for item in drawing_ids if item],
        },
        errors,
    )


def _bounded_anchor_index(value: str, maximum: int, label: str) -> int | None:
    if not value:
        return None
    if not value.isascii() or not value.isdigit() or len(value) > 7:
        raise WorkbookRejected(f"invalid drawing {label} index")
    parsed = int(value)
    if parsed > maximum:
        raise WorkbookRejected(f"drawing {label} index exceeds XLSX limits")
    return parsed


def _drawing_anchors(
    archive: zipfile.ZipFile,
    sheet_part: str,
    drawing_relationship_ids: list[str],
) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    if not drawing_relationship_ids:
        return [], []
    rels_part = posixpath.join(
        posixpath.dirname(sheet_part),
        "_rels",
        f"{posixpath.basename(sheet_part)}.rels",
    )
    relationships, external = _relationships(archive, sheet_part, rels_part)
    anchors: list[dict[str, object]] = []
    for relationship_id in drawing_relationship_ids:
        drawing_part = relationships.get(relationship_id)
        if not drawing_part:
            raise WorkbookRejected(
                f"sheet drawing relationship is unresolved: {relationship_id}"
            )
        drawing_root = _parse_xml(archive, drawing_part)
        for anchor in list(drawing_root):
            if anchor.tag not in {
                f"{{{DRAWING}}}oneCellAnchor",
                f"{{{DRAWING}}}twoCellAnchor",
                f"{{{DRAWING}}}absoluteAnchor",
            }:
                continue
            if len(anchors) >= MAX_DRAWING_ANCHORS:
                raise WorkbookRejected("drawing anchor count exceeds safety limit")
            start = anchor.find("xdr:from", NS)
            row = start.findtext("xdr:row", default="", namespaces=NS) if start else ""
            column = (
                start.findtext("xdr:col", default="", namespaces=NS) if start else ""
            )
            anchors.append(
                {
                    "drawing_part": drawing_part,
                    "anchor_type": anchor.tag.rsplit("}", 1)[-1],
                    "zero_based_row": _bounded_anchor_index(row, 1_048_575, "row"),
                    "zero_based_column": _bounded_anchor_index(
                        column, 16_383, "column"
                    ),
                    "requires_human_target_confirmation": True,
                }
            )
    return anchors, external


def inspect(
    workbook: Path,
    max_entries: int,
    max_uncompressed_bytes: int,
    max_input_bytes: int = MAX_INPUT_BYTES,
) -> dict[str, object]:
    if workbook.suffix.lower() != ".xlsx":
        raise WorkbookRejected("only .xlsx workbooks are accepted")
    try:
        input_size = workbook.stat().st_size
    except OSError:
        raise
    if input_size > max_input_bytes:
        raise WorkbookRejected("input file size limit exceeded")
    digest_builder = hashlib.sha256()
    with workbook.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest_builder.update(chunk)
    digest = digest_builder.hexdigest()
    try:
        archive = zipfile.ZipFile(workbook)
    except zipfile.BadZipFile as error:
        raise WorkbookRejected("input is not a valid ZIP-based XLSX file") from error

    with archive:
        infos = archive.infolist()
        if len(infos) > max_entries:
            raise WorkbookRejected("archive entry limit exceeded")
        if sum(info.file_size for info in infos) > max_uncompressed_bytes:
            raise WorkbookRejected("archive uncompressed-size limit exceeded")
        canonical_names: set[str] = set()
        for info in infos:
            canonical_name = _safe_member_name(info.filename)
            if canonical_name in canonical_names:
                raise WorkbookRejected(
                    "duplicate or canonically colliding archive members are "
                    "not accepted"
                )
            canonical_names.add(canonical_name)
            if info.flag_bits & 0x1:
                raise WorkbookRejected("encrypted archive entries are not accepted")
            unix_mode = (info.external_attr >> 16) & 0o170000
            if unix_mode == stat.S_IFLNK:
                raise WorkbookRejected("archive links are not accepted")

        try:
            corrupt_member = archive.testzip()
        except (RuntimeError, zipfile.BadZipFile) as error:
            raise WorkbookRejected(
                "an XLSX archive member failed integrity validation"
            ) from error
        if corrupt_member is not None:
            raise WorkbookRejected("an XLSX archive member failed integrity validation")

        names = set(archive.namelist())
        _validate_passive_package(archive, names)

        workbook_root = _parse_xml(archive, "xl/workbook.xml")
        workbook_relationships, external_relationships = _relationships(
            archive,
            "xl/workbook.xml",
            "xl/_rels/workbook.xml.rels",
        )
        shared_strings = _shared_strings(archive)

        sheets: list[dict[str, object]] = []
        all_errors: list[dict[str, str]] = []
        all_anchors: list[dict[str, object]] = []
        workbook_sheets = workbook_root.findall(".//s:sheets/s:sheet", NS)
        if len(workbook_sheets) > MAX_WORKSHEETS:
            raise WorkbookRejected("worksheet count exceeds safety limit")
        seen_sheet_names: set[str] = set()
        for sheet in workbook_sheets:
            sheet_name = sheet.attrib.get("name", "")
            if not sheet_name or sheet_name in seen_sheet_names:
                raise WorkbookRejected("worksheet names must be non-empty and unique")
            seen_sheet_names.add(sheet_name)
            relationship_id = sheet.attrib.get(f"{{{OFFICE_REL}}}id", "")
            sheet_part = workbook_relationships.get(relationship_id)
            if not sheet_part:
                raise WorkbookRejected(
                    f"worksheet relationship is unresolved: {relationship_id}"
                )
            sheet_report, errors = _inspect_sheet(
                archive, sheet_name, sheet_part, shared_strings
            )
            anchors, drawing_external = _drawing_anchors(
                archive,
                sheet_part,
                sheet_report["drawing_relationship_ids"],
            )
            external_relationships.extend(drawing_external)
            sheets.append(sheet_report)
            all_errors.extend(errors)
            all_anchors.extend(anchors)

        if external_relationships:
            raise WorkbookRejected("external XLSX relationships are not accepted")

        return {
            "file_name": workbook.name,
            "sha256": digest,
            "archive_entry_count": len(infos),
            "uncompressed_bytes": sum(info.file_size for info in infos),
            "worksheet_count": len(sheets),
            "sheets": sheets,
            "formula_errors": all_errors,
            "floating_image_anchors": all_anchors,
            "notes": [
                "No formulas or macros were executed.",
                "Image anchors are candidates only and require human target confirmation.",
                "Cell values are not emitted except formula error codes.",
            ],
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--max-entries", type=int, default=10_000)
    parser.add_argument("--max-uncompressed-bytes", type=int, default=50_000_000)
    parser.add_argument("--max-input-bytes", type=int, default=MAX_INPUT_BYTES)
    arguments = parser.parse_args()
    if (
        arguments.max_entries <= 0
        or arguments.max_uncompressed_bytes <= 0
        or arguments.max_input_bytes <= 0
    ):
        raise SystemExit("inspection limits must be positive")
    try:
        report = inspect(
            arguments.workbook,
            arguments.max_entries,
            arguments.max_uncompressed_bytes,
            arguments.max_input_bytes,
        )
    except (OSError, WorkbookRejected) as error:
        print(json.dumps({"accepted": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"accepted": True, **report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
