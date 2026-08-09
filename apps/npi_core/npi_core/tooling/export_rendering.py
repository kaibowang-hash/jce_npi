from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable, Iterable
from uuid import UUID

from npi_core.tooling.domain import sha256_json
from npi_core.tooling.export_domain import (
    MAX_TOOLING_EXPORT_OBJECTS,
    TOOLING_OBJECT_PACKAGE_CONFIDENTIALITY,
    TOOLING_OBJECT_PACKAGE_MIME_TYPE,
    TOOLING_OBJECT_PACKAGE_SCHEMA_VERSION,
    ToolingExportLanguage,
    ToolingExportMode,
    ToolingListRow,
    ToolingSource,
)

try:
    from frappe import _
except ImportError:  # Keeps static source inventory available outside Frappe.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


PACKAGE_MEMBER_NAMES = ("manifest.json", "tooling-objects.csv", "README.txt")
OMITTED_FIELD_CLASSES = (
    "raw_file_url_and_content",
    "raw_workbook_values",
    "external_customer_or_supplier_identifiers",
    "repair_custody_or_return_text",
    "cost",
    "evidence",
    "erp_or_lifecycle_truth",
)
MAX_TOOLING_OBJECT_PACKAGE_BYTES = 1_000_000
CSV_SOURCE_STRINGS = (
    "Project code",
    "Tooling Master ID",
    "Tooling title",
    "Tooling snapshot hash",
    "Originating Project ID",
    "Applicability count",
    "Distinct Part Revision count",
    "Physical set count",
    "Latest revision",
    "Source",
    "Generated at",
)
README_SOURCE_STRINGS = (
    "Tooling object package",
    "Confidentiality: Internal project use",
    "Generated from an immutable Tooling List snapshot.",
    "Rows: {row_count}",
    "Unavailable",
    "Manual",
    "Controlled XLSX import",
)
LOCALIZATION_SOURCE_STRINGS = CSV_SOURCE_STRINGS + README_SOURCE_STRINGS
_SAFE_FILE_PART = re.compile(r"[^A-Za-z0-9._-]+")


def frappe_localization_source_inventory() -> tuple[str, ...]:
    """Expose literal sources to the Frappe extractor without translating payload keys."""

    return (
        _("Project code"),
        _("Tooling Master ID"),
        _("Tooling title"),
        _("Tooling snapshot hash"),
        _("Originating Project ID"),
        _("Applicability count"),
        _("Distinct Part Revision count"),
        _("Physical set count"),
        _("Latest revision"),
        _("Source"),
        _("Generated at"),
        _("Tooling object package"),
        _("Confidentiality: Internal project use"),
        _("Generated from an immutable Tooling List snapshot."),
        _("Rows: {row_count}"),
        _("Unavailable"),
        _("Manual"),
        _("Controlled XLSX import"),
    )


@dataclass(frozen=True, slots=True)
class RenderedToolingObjectPackage:
    content: bytes
    file_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    manifest_sha256: str
    member_sha256: tuple[tuple[str, str], ...]


def render_tooling_object_package(
    *,
    rows: Iterable[ToolingListRow],
    project_global_id: UUID,
    project_code: str,
    mode: ToolingExportMode,
    language: ToolingExportLanguage,
    query_snapshot_hash: str | None,
    generated_at: datetime,
    translate: Callable[[str], str],
) -> RenderedToolingObjectPackage:
    normalized_rows = tuple(rows)
    if not 1 <= len(normalized_rows) <= MAX_TOOLING_EXPORT_OBJECTS:
        raise ValueError("A Tooling object package requires between one and one hundred rows.")
    if not all(isinstance(row, ToolingListRow) for row in normalized_rows):
        raise TypeError("Tooling object package rows must be validated Tooling List rows.")
    project_global_id = _uuid(project_global_id)
    if any(row.project_global_id != project_global_id for row in normalized_rows):
        raise ValueError("Tooling object package rows must belong to the exact Project.")
    if not isinstance(project_code, str) or any(
        row.project_code != project_code for row in normalized_rows
    ):
        raise ValueError("Tooling object package Project code does not match.")
    row_ids = [row.tooling_master_global_id for row in normalized_rows]
    if len(row_ids) != len(set(row_ids)):
        raise ValueError("Tooling object package rows must be unique.")
    mode = ToolingExportMode(mode)
    language = ToolingExportLanguage(language)
    generated_at = _aware_utc(generated_at)
    if mode is ToolingExportMode.FILTERED:
        query_snapshot_hash = _sha256(query_snapshot_hash)
    elif query_snapshot_hash not in (None, ""):
        raise ValueError("A selection package cannot include a filtered query snapshot.")
    else:
        query_snapshot_hash = None

    csv_content = _render_csv(normalized_rows, generated_at, translate)
    readme_content = _render_readme(len(normalized_rows), translate)
    content_members = (
        ("tooling-objects.csv", csv_content, "text/csv; charset=utf-8"),
        ("README.txt", readme_content, "text/plain; charset=utf-8"),
    )
    manifest = {
        "schemaVersion": TOOLING_OBJECT_PACKAGE_SCHEMA_VERSION,
        "confidentialityClass": TOOLING_OBJECT_PACKAGE_CONFIDENTIALITY,
        "projectGlobalId": str(project_global_id),
        "projectCode": project_code,
        "mode": mode.value,
        "language": language.value,
        "querySnapshotHash": query_snapshot_hash,
        "generatedAt": _utc_text(generated_at),
        "rowCount": len(normalized_rows),
        "omittedFieldClasses": list(OMITTED_FIELD_CLASSES),
        "objectRefs": [row.reference().snapshot_payload() for row in normalized_rows],
        "members": [
            {
                "name": name,
                "mediaType": media_type,
                "sizeBytes": len(content),
                "sha256": _sha256_bytes(content),
            }
            for name, content, media_type in content_members
        ],
    }
    manifest_content = (
        json.dumps(
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    members = (
        ("manifest.json", manifest_content),
        ("tooling-objects.csv", csv_content),
        ("README.txt", readme_content),
    )
    archive = _render_zip(members, generated_at)
    if len(archive) > MAX_TOOLING_OBJECT_PACKAGE_BYTES:
        raise ValueError("The Tooling object package exceeds the fixed byte limit.")
    member_hashes = tuple((name, _sha256_bytes(content)) for name, content in members)
    timestamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
    safe_project_code = _safe_file_part(project_code)
    return RenderedToolingObjectPackage(
        content=archive,
        file_name=f"tooling-objects-{safe_project_code}-{timestamp}.zip",
        mime_type=TOOLING_OBJECT_PACKAGE_MIME_TYPE,
        size_bytes=len(archive),
        sha256=_sha256_bytes(archive),
        manifest_sha256=_sha256_bytes(manifest_content),
        member_sha256=member_hashes,
    )


def package_render_snapshot(rendered: RenderedToolingObjectPackage) -> dict[str, object]:
    return {
        "fileName": rendered.file_name,
        "mimeType": rendered.mime_type,
        "sizeBytes": rendered.size_bytes,
        "sha256": rendered.sha256,
        "manifestSha256": rendered.manifest_sha256,
        "memberSha256": dict(rendered.member_sha256),
        "renderHash": sha256_json(dict(rendered.member_sha256)),
    }


def _render_csv(
    rows: tuple[ToolingListRow, ...],
    generated_at: datetime,
    translate: Callable[[str], str],
) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow([translate(source) for source in CSV_SOURCE_STRINGS])
    for row in rows:
        writer.writerow(
            [
                _neutralize(row.project_code),
                str(row.tooling_master_global_id),
                _neutralize(row.title),
                row.tooling_master_snapshot_hash,
                str(row.originating_project_global_id),
                row.applicability_count,
                row.distinct_part_revision_count,
                row.physical_set_count,
                row.latest_revision_number
                if row.latest_revision_number is not None
                else translate("Unavailable"),
                translate(_source_label(row.source)),
                _utc_text(generated_at),
            ]
        )
    return b"\xef\xbb\xbf" + output.getvalue().encode("utf-8")


def _render_readme(row_count: int, translate: Callable[[str], str]) -> bytes:
    lines = (
        translate("Tooling object package"),
        translate("Confidentiality: Internal project use"),
        translate("Generated from an immutable Tooling List snapshot."),
        translate("Rows: {row_count}").format(row_count=row_count),
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


def _render_zip(
    members: tuple[tuple[str, bytes], ...],
    generated_at: datetime,
) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, content in members:
            info = zipfile.ZipInfo(filename=name, date_time=_zip_time(generated_at))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100600 << 16
            archive.writestr(info, content)
    return output.getvalue()


def _neutralize(value: object) -> object:
    if not isinstance(value, str):
        return value
    if value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _source_label(source: ToolingSource) -> str:
    return {
        ToolingSource.MANUAL: "Manual",
        ToolingSource.CONTROLLED_XLSX_IMPORT: "Controlled XLSX import",
    }[source]


def _safe_file_part(value: str) -> str:
    normalized = _SAFE_FILE_PART.sub("-", value.strip()).strip("-._")[:64]
    return normalized or "project"


def _uuid(value: object) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("Enter a valid Project global ID.") from error


def _sha256(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise ValueError("Enter a valid SHA-256 value.")
    return value


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _aware_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("Enter a timezone-aware generated instant.")
    return value.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _zip_time(value: datetime) -> tuple[int, int, int, int, int, int]:
    utc = value.astimezone(UTC)
    if utc.year < 1980 or utc.year > 2107:
        raise ValueError("The generated instant is outside the ZIP timestamp range.")
    return (utc.year, utc.month, utc.day, utc.hour, utc.minute, utc.second)
