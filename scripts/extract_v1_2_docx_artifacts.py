#!/usr/bin/env python3
"""Extract the machine-readable V1.2 requirement and Tooling mapping tables."""

from __future__ import annotations

import argparse
import csv
import io
import os
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree

WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WORD = {"w": WORD_NAMESPACE}

REQUIREMENT_HEADER = ("ID", "优先级", "领域", "需求", "验收", "阶段")
REQUIREMENT_OUTPUT_HEADER = (
    "requirement_id",
    "priority",
    "domain",
    "requirement",
    "acceptance",
    "docx_phase",
)
TOOLING_MAPPING_HEADER = (
    "源列",
    "目标对象",
    "建议字段",
    "映射/校验规则",
    "优先级",
)
TOOLING_MAPPING_OUTPUT_HEADER = (
    "source_column",
    "target_object",
    "suggested_field",
    "mapping_validation_rule",
    "priority",
)

EXPECTED_REQUIREMENT_FAMILIES = {
    "ARCH": 12,
    "COD": 22,
    "FR-CH": 10,
    "FR-CO": 7,
    "FR-DS": 14,
    "FR-NP": 15,
    "FR-PM": 12,
    "FR-RP": 10,
    "FR-SG": 9,
    "FR-TL": 18,
    "FR-TR": 10,
    "FR-TX": 18,
    "I18N": 7,
    "INT": 14,
    "NFR-AUD": 1,
    "NFR-AVL": 1,
    "NFR-BCP": 1,
    "NFR-COM": 1,
    "NFR-DAT": 1,
    "NFR-INT": 1,
    "NFR-LOC": 1,
    "NFR-MNT": 1,
    "NFR-PER": 2,
    "NFR-SCL": 1,
    "NFR-SEC": 3,
    "NFR-UX": 1,
    "UX": 36,
}


class ExtractionError(RuntimeError):
    """Raised when the authoritative DOCX no longer matches its reviewed shape."""


def _cell_text(cell: ElementTree.Element) -> str:
    return "".join(node.text or "" for node in cell.findall(".//w:t", WORD)).strip()


def _table_rows(table: ElementTree.Element) -> list[tuple[str, ...]]:
    return [
        tuple(_cell_text(cell) for cell in row.findall("./w:tc", WORD))
        for row in table.findall("./w:tr", WORD)
    ]


def _find_table(
    tables: list[list[tuple[str, ...]]], header: tuple[str, ...]
) -> list[tuple[str, ...]]:
    matches = [rows for rows in tables if rows and rows[0] == header]
    if len(matches) != 1:
        raise ExtractionError(
            f"expected one DOCX table with header {header!r}; found {len(matches)}"
        )
    return matches[0]


def _family(requirement_id: str) -> str:
    return requirement_id.rsplit("-", 1)[0]


def extract(
    docx_path: Path,
) -> tuple[list[tuple[str, ...]], list[tuple[str, ...]]]:
    with zipfile.ZipFile(docx_path) as archive:
        document = ElementTree.fromstring(archive.read("word/document.xml"))

    tables = [_table_rows(table) for table in document.findall(".//w:tbl", WORD)]
    requirements = _find_table(tables, REQUIREMENT_HEADER)[1:]
    tooling_mapping = _find_table(tables, TOOLING_MAPPING_HEADER)[1:]

    if len(requirements) != 229:
        raise ExtractionError(
            f"expected 229 V1.2 requirements; found {len(requirements)}"
        )
    requirement_ids = [row[0] for row in requirements]
    if len(set(requirement_ids)) != 229:
        raise ExtractionError("V1.2 requirement IDs are not unique")
    if any(len(row) != len(REQUIREMENT_HEADER) for row in requirements):
        raise ExtractionError("a V1.2 requirement row has an unexpected column count")

    family_counts = Counter(
        _family(requirement_id) for requirement_id in requirement_ids
    )
    if dict(sorted(family_counts.items())) != EXPECTED_REQUIREMENT_FAMILIES:
        raise ExtractionError(
            "V1.2 requirement family counts differ from the reconciled baseline"
        )

    if len(tooling_mapping) != 43:
        raise ExtractionError(
            f"expected 43 Tooling List source columns; found {len(tooling_mapping)}"
        )
    if any(len(row) != len(TOOLING_MAPPING_HEADER) for row in tooling_mapping):
        raise ExtractionError("a Tooling mapping row has an unexpected column count")
    source_columns = [row[0] for row in tooling_mapping]
    if len(set(source_columns)) != 43:
        raise ExtractionError("Tooling List source-column names are not unique")

    return requirements, tooling_mapping


def _render_csv(header: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return output.getvalue()


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent, text=True
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _check_exact(path: Path, content: str) -> None:
    if not path.exists():
        raise ExtractionError(f"generated artifact is missing: {path}")
    if path.read_text(encoding="utf-8") != content:
        raise ExtractionError(f"generated artifact is stale: {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--docx",
        type=Path,
        default=Path("docs/reference/NPI_Tooling_Product_Spec_V1.2.docx"),
    )
    parser.add_argument(
        "--requirements-output",
        type=Path,
        default=Path("implementation/V1_2_DOCX_REQUIREMENTS.csv"),
    )
    parser.add_argument(
        "--mapping-output",
        type=Path,
        default=Path("docs/reference/TOOLING_LIST_FIELD_MAPPING.csv"),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail unless the checked-in outputs exactly match the DOCX",
    )
    arguments = parser.parse_args()

    requirements, tooling_mapping = extract(arguments.docx)
    requirements_csv = _render_csv(REQUIREMENT_OUTPUT_HEADER, requirements)
    mapping_csv = _render_csv(TOOLING_MAPPING_OUTPUT_HEADER, tooling_mapping)

    if arguments.check:
        _check_exact(arguments.requirements_output, requirements_csv)
        _check_exact(arguments.mapping_output, mapping_csv)
    else:
        _write_atomic(arguments.requirements_output, requirements_csv)
        _write_atomic(arguments.mapping_output, mapping_csv)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
