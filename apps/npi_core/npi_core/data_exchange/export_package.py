from __future__ import annotations

import csv
import hashlib
import html
import io
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable, Iterable, Mapping

from npi_core.data_exchange.domain import (
    MAX_EXPORT_BYTES,
    REPORT_PACKAGE_SCHEMA_VERSION,
    ExportProfileVersion,
    canonical_json,
    sha256_json,
)

try:
    from frappe import _
except ImportError:

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


PACKAGE_MEMBERS = (
    "manifest.json",
    "report.csv",
    "report.xlsx",
    "report.pdf",
    "README.txt",
)
OMITTED_FIELD_CLASSES = (
    "raw_identifiers_not_allowlisted_by_profile",
    "private_file_urls_and_paths",
    "credentials_and_security_tokens",
    "free_text_not_allowlisted_by_profile",
)
COLUMN_LABELS = {
    "projectCode": "Project code",
    "title": "Title",
    "projectType": "Project type",
    "lifecycleState": "Lifecycle state",
    "targetSop": "Target SOP",
    "ownerUserId": "Owner user ID",
    "currentHealthStatus": "Current health status",
    "openWorkCount": "Open work count",
    "currentGate": "Current gate",
    "erpAvailability": "ERP availability",
    "metricKey": "Metric key",
    "label": "Metric",
    "valueKind": "Value kind",
    "sourceSystem": "Source system",
    "availability": "Availability",
    "reasonCode": "Reason code",
    "month": "Month",
    "value": "Value",
}


def frappe_localization_source_inventory() -> tuple[str, ...]:
    return (
        _("Project code"),
        _("Title"),
        _("Project type"),
        _("Lifecycle state"),
        _("Target SOP"),
        _("Owner user ID"),
        _("Current health status"),
        _("Open work count"),
        _("Current gate"),
        _("ERP availability"),
        _("Metric key"),
        _("Metric"),
        _("Value kind"),
        _("Source system"),
        _("Availability"),
        _("Reason code"),
        _("Month"),
        _("Value"),
        _("Data Exchange report package"),
        _("Generated from a permission-filtered report snapshot."),
        _("Rows: {row_count}"),
        _("Dataset: {dataset_id}"),
        _("Profile: {profile_id} version {profile_version}"),
        _("The package contains CSV, XLSX and controlled PDF renderings."),
        _("All spreadsheet text is protected from formula execution."),
        _("Unavailable"),
    )


@dataclass(frozen=True, slots=True)
class RenderedReportPackage:
    content: bytes
    file_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    manifest_sha256: str
    data_sha256: str
    member_sha256: tuple[tuple[str, str], ...]


def render_report_package(
    *,
    profile: ExportProfileVersion,
    rows: Iterable[Mapping[str, object]],
    generated_at: datetime,
    actor_user_id: str,
    translate: Callable[[str], str],
    render_pdf: Callable[[str], bytes],
) -> RenderedReportPackage:
    generated_at = _aware_utc(generated_at)
    normalized = tuple(_project_row(row, profile.columns) for row in rows)
    if len(normalized) > profile.max_rows:
        raise ValueError("The report exceeds the published row limit.")
    data_payload = {"columns": list(profile.columns), "rows": [dict(row) for row in normalized]}
    data_hash = sha256_json(data_payload)
    csv_content = _render_csv(profile, normalized, translate)
    xlsx_content = _render_xlsx(profile, normalized, generated_at, translate)
    html_content = _render_html(profile, normalized, generated_at, translate)
    pdf_content = render_pdf(html_content)
    if not isinstance(pdf_content, bytes) or not pdf_content.startswith(b"%PDF-"):
        raise ValueError("The controlled PDF renderer returned invalid content.")
    readme_content = _render_readme(profile, len(normalized), translate)
    content_members = (
        ("report.csv", csv_content, "text/csv; charset=utf-8"),
        ("report.xlsx", xlsx_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("report.pdf", pdf_content, "application/pdf"),
        ("README.txt", readme_content, "text/plain; charset=utf-8"),
    )
    manifest = {
        "schemaVersion": REPORT_PACKAGE_SCHEMA_VERSION,
        "datasetId": profile.dataset_id.value,
        "profileId": str(profile.global_id),
        "profileVersion": profile.version,
        "profileHash": profile.definition_hash,
        "language": profile.language.value,
        "redactionProfile": profile.redaction_profile.value,
        "columns": list(profile.columns),
        "omittedFieldClasses": list(OMITTED_FIELD_CLASSES),
        "rowCount": len(normalized),
        "dataSha256": data_hash,
        "createdByUserId": actor_user_id,
        "generatedAt": _utc(generated_at),
        "members": [
            {"name": name, "mediaType": media, "sizeBytes": len(content), "sha256": _hash(content)}
            for name, content, media in content_members
        ],
    }
    manifest_content = (canonical_json(manifest) + "\n").encode("utf-8")
    members = (("manifest.json", manifest_content),) + tuple(
        (name, content) for name, content, _media in content_members
    )
    archive = _zip(members, generated_at)
    if len(archive) > profile.max_bytes or len(archive) > MAX_EXPORT_BYTES:
        raise ValueError("The report package exceeds the published byte limit.")
    timestamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
    return RenderedReportPackage(
        content=archive,
        file_name=f"data-exchange-{profile.dataset_id.value}-{timestamp}.zip",
        mime_type="application/zip",
        size_bytes=len(archive),
        sha256=_hash(archive),
        manifest_sha256=_hash(manifest_content),
        data_sha256=data_hash,
        member_sha256=tuple((name, _hash(content)) for name, content in members),
    )


def _project_row(row: Mapping[str, object], columns: tuple[str, ...]) -> tuple[tuple[str, object], ...]:
    if not isinstance(row, Mapping):
        raise TypeError("Report rows must be mappings.")
    return tuple((column, _neutralize(row.get(column))) for column in columns)


def _render_csv(profile, rows, translate) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow([translate(COLUMN_LABELS[column]) for column in profile.columns])
    for row in rows:
        writer.writerow([_cell(dict(row)[column], translate) for column in profile.columns])
    return b"\xef\xbb\xbf" + output.getvalue().encode("utf-8")


def _render_xlsx(profile, rows, generated_at, translate) -> bytes:
    labels = [translate(COLUMN_LABELS[column]) for column in profile.columns]
    sheet_rows = [labels] + [[_cell(dict(row)[column], translate) for column in profile.columns] for row in rows]
    worksheet = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
    for row_index, values in enumerate(sheet_rows, start=1):
        cells = []
        for column_index, value in enumerate(values, start=1):
            reference = f"{_column_name(column_index)}{row_index}"
            cells.append(f'<c r="{reference}" t="inlineStr"><is><t>{html.escape(str(value))}</t></is></c>')
        worksheet.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    worksheet.append("</sheetData></worksheet>")
    members = (
        ("[Content_Types].xml", b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'),
        ("_rels/.rels", b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'),
        ("xl/workbook.xml", b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Report" sheetId="1" r:id="rId1"/></sheets></workbook>'),
        ("xl/_rels/workbook.xml.rels", b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'),
        ("xl/worksheets/sheet1.xml", "".join(worksheet).encode("utf-8")),
    )
    return _zip(members, generated_at)


def _render_html(profile, rows, generated_at, translate) -> str:
    headers = "".join(f"<th>{html.escape(translate(COLUMN_LABELS[column]))}</th>" for column in profile.columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(_cell(dict(row)[column], translate)))}</td>" for column in profile.columns) + "</tr>"
        for row in rows
    )
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\"><style>"
        "@page{size:A4 landscape;margin:12mm}body{font:9pt sans-serif;color:#1f2933}"
        "table{border-collapse:collapse;width:100%}th,td{border:1px solid #77828c;padding:3px;text-align:left}"
        "th{background:#e8edef}h1{font-size:14pt}</style></head><body>"
        f"<h1>{html.escape(translate('Data Exchange report package'))}</h1>"
        f"<p>{html.escape(profile.dataset_id.value)} · {html.escape(_utc(generated_at))}</p>"
        f"<table><thead><tr>{headers}</tr></thead><tbody>{body}</tbody></table></body></html>"
    )


def _render_readme(profile, row_count, translate) -> bytes:
    lines = (
        translate("Data Exchange report package"),
        translate("Generated from a permission-filtered report snapshot."),
        translate("Rows: {row_count}").format(row_count=row_count),
        translate("Dataset: {dataset_id}").format(dataset_id=profile.dataset_id.value),
        translate("Profile: {profile_id} version {profile_version}").format(profile_id=profile.global_id, profile_version=profile.version),
        translate("The package contains CSV, XLSX and controlled PDF renderings."),
        translate("All spreadsheet text is protected from formula execution."),
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


def _cell(value: object, translate) -> object:
    if value is None:
        return translate("Unavailable")
    if isinstance(value, (dict, list, tuple)):
        return canonical_json(value)
    return value


def _neutralize(value: object) -> object:
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _zip(members, generated_at) -> bytes:
    output = io.BytesIO()
    stamp = _zip_time(generated_at)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, content in members:
            info = zipfile.ZipInfo(name, stamp)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100600 << 16
            archive.writestr(info, content)
    return output.getvalue()


def _zip_time(value: datetime) -> tuple[int, int, int, int, int, int]:
    value = _aware_utc(value)
    year = min(max(value.year, 1980), 2107)
    return year, value.month, value.day, value.hour, value.minute, value.second - value.second % 2


def _aware_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("The package timestamp must be timezone-aware.")
    return value.astimezone(UTC)


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
