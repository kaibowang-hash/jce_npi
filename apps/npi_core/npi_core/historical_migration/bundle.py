from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import date
from typing import Callable, Mapping
from uuid import UUID

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.historical_migration.domain import (
    BUNDLE_SCHEMA_VERSION,
    BundleInspection,
    MigrationFamily,
    MigrationFinding,
    MigrationRow,
    sha256_json,
)

try:
    from frappe import _
except ImportError:  # Keeps the inspector independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


MAX_BUNDLE_BYTES = 20_000_000
MAX_MEMBER_BYTES = 8_000_000
MAX_TOTAL_UNCOMPRESSED_BYTES = 30_000_000
MAX_ROWS_PER_MEMBER = 2_000
MAX_FIELDS_PER_ROW = 12
MAX_CELL_CHARACTERS = 2_000
MAX_COMPRESSION_RATIO = 100
_HASH = re.compile(r"^[a-f0-9]{64}$")
_SOURCE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+$")
_BUSINESS_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,63}$")
_ALLOWED_PROJECT_TYPES = frozenset({"customer_owned_tool", "new_tool", "tool_change"})
_ALLOWED_REFERENCE_TYPES = frozenset(
    {"customer", "factory", "product", "part", "tooling", "order"}
)
_ALLOWED_REFERENCE_SYSTEMS = frozenset({"NPI_ONE", "ERPNEXT"})


@dataclass(frozen=True, slots=True)
class _MemberSpec:
    family: MigrationFamily
    headers: tuple[str, ...]
    validator: Callable[[int, Mapping[str, str]], tuple[MigrationFinding, ...]]


_MEMBERS: dict[str, _MemberSpec] = {
    "projects.csv": _MemberSpec(
        MigrationFamily.PROJECT,
        (
            "source_key",
            "business_code",
            "title",
            "project_type",
            "owner_user_id",
            "target_sop",
            "template_global_id",
            "template_version",
            "template_expected_version",
        ),
        lambda ordinal, row: _validate_project(ordinal, row),
    ),
    "tooling_mappings.csv": _MemberSpec(
        MigrationFamily.TOOLING_MAPPING,
        (
            "source_key",
            "project_source_key",
            "tooling_global_id",
            "target_version",
            "target_snapshot_hash",
        ),
        lambda ordinal, row: _validate_tooling(ordinal, row),
    ),
    "file_index.csv": _MemberSpec(
        MigrationFamily.FILE_INDEX,
        (
            "source_key",
            "project_source_key",
            "file_revision_global_id",
            "file_optimistic_version",
            "file_sha256",
        ),
        lambda ordinal, row: _validate_file(ordinal, row),
    ),
    "npi_references.csv": _MemberSpec(
        MigrationFamily.NPI_REFERENCE,
        (
            "source_key",
            "project_source_key",
            "reference_type",
            "source_system",
            "source_object_id",
        ),
        lambda ordinal, row: _validate_reference(ordinal, row),
    ),
}
_EXACT_MEMBERS = frozenset({"manifest.json", *_MEMBERS})


def inspect_bundle(content: bytes, *, expected_sha256: str) -> BundleInspection:
    if not isinstance(content, bytes) or not content or len(content) > MAX_BUNDLE_BYTES:
        raise _problem("fileRevisionGlobalId", _("Select a bounded migration bundle."))
    actual_sha256 = hashlib.sha256(content).hexdigest()
    if not isinstance(expected_sha256, str) or not _HASH.fullmatch(expected_sha256):
        raise _problem("sha256", _("Enter a lowercase SHA-256 hash."))
    if actual_sha256 != expected_sha256:
        raise _problem("sha256", _("The migration bundle hash does not match the File Revision."))
    try:
        archive = zipfile.ZipFile(io.BytesIO(content), "r")
    except (zipfile.BadZipFile, OSError):
        raise _problem("fileRevisionGlobalId", _("Select a valid migration ZIP bundle.")) from None
    with archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        if (
            set(names) != _EXACT_MEMBERS
            or len(names) != len(_EXACT_MEMBERS)
            or len({name.casefold() for name in names}) != len(names)
        ):
            raise _problem(
                "manifest.members",
                _("The migration bundle must contain only the approved members."),
            )
        total_size = 0
        for item in infos:
            if (
                item.is_dir()
                or item.filename.startswith(("/", "\\"))
                or "/" in item.filename
                or "\\" in item.filename
                or item.flag_bits & 0x1
                or item.file_size > MAX_MEMBER_BYTES
                or item.compress_size <= 0
                or item.file_size > item.compress_size * MAX_COMPRESSION_RATIO
            ):
                raise _problem("manifest.members", _("A migration bundle member is unsafe."))
            total_size += item.file_size
        if total_size > MAX_TOTAL_UNCOMPRESSED_BYTES:
            raise _problem("manifest.members", _("The migration bundle expands beyond its limit."))
        members = {name: _read_member(archive, name) for name in _EXACT_MEMBERS}

    manifest = _manifest(members["manifest.json"])
    rows: list[MigrationRow] = []
    known_project_keys: set[str] = set()
    for member_name, spec in _MEMBERS.items():
        member_rows = _csv_rows(member_name, members[member_name], spec)
        _verify_member_manifest(manifest, member_name, members[member_name], len(member_rows))
        if spec.family is MigrationFamily.PROJECT:
            known_project_keys = {row.source_key.casefold() for row in member_rows}
        rows.extend(member_rows)
    rows = [_add_project_reference_findings(row, known_project_keys) for row in rows]
    return BundleInspection(
        bundle_id=_canonical_uuid(manifest.get("bundleId"), "manifest.bundleId"),
        source_system=_source_system(manifest.get("sourceSystem")),
        source_sha256=actual_sha256,
        manifest_hash=sha256_json(manifest),
        predecessor_manifest_hash=_optional_hash(
            manifest.get("predecessorManifestHash"),
            "manifest.predecessorManifestHash",
        ),
        rows=tuple(rows),
    )


def _read_member(archive: zipfile.ZipFile, name: str) -> bytes:
    try:
        content = archive.read(name)
    except (KeyError, RuntimeError, zipfile.BadZipFile):
        raise _problem("manifest.members", _("A migration bundle member cannot be read.")) from None
    if len(content) > MAX_MEMBER_BYTES:
        raise _problem("manifest.members", _("A migration bundle member exceeds its limit."))
    return content


def _manifest(content: bytes) -> dict[str, object]:
    try:
        decoded = content.decode("utf-8")
        value = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise _problem("manifest", _("The migration manifest must be valid UTF-8 JSON.")) from None
    allowed = {
        "schemaVersion",
        "bundleId",
        "sourceSystem",
        "predecessorManifestHash",
        "members",
    }
    required = {"schemaVersion", "bundleId", "sourceSystem", "members"}
    if (
        not isinstance(value, dict)
        or set(value) - allowed
        or not required.issubset(value)
        or value.get("schemaVersion") != BUNDLE_SCHEMA_VERSION
    ):
        raise _problem("manifest", _("The migration manifest shape or version is unsupported."))
    members = value.get("members")
    if not isinstance(members, list) or len(members) != len(_MEMBERS):
        raise _problem("manifest.members", _("The migration member manifest is invalid."))
    names: set[str] = set()
    for index, item in enumerate(members):
        if not isinstance(item, dict) or set(item) != {"name", "sha256", "rowCount"}:
            raise _problem(
                f"manifest.members[{index}]",
                _("The migration member manifest is invalid."),
            )
        name = item.get("name")
        if name not in _MEMBERS or name in names:
            raise _problem(
                f"manifest.members[{index}].name",
                _("The migration member name is invalid."),
            )
        names.add(str(name))
        if not isinstance(item.get("sha256"), str) or not _HASH.fullmatch(str(item["sha256"])):
            raise _problem(
                f"manifest.members[{index}].sha256",
                _("Enter a lowercase SHA-256 hash."),
            )
        row_count = item.get("rowCount")
        if type(row_count) is not int or row_count < 1 or row_count > MAX_ROWS_PER_MEMBER:
            raise _problem(
                f"manifest.members[{index}].rowCount",
                _("Enter a bounded positive row count."),
            )
    if names != set(_MEMBERS):
        raise _problem("manifest.members", _("The migration member manifest is incomplete."))
    return value


def _verify_member_manifest(
    manifest: Mapping[str, object], name: str, content: bytes, row_count: int
) -> None:
    members = manifest["members"]
    assert isinstance(members, list)
    entry = next(item for item in members if isinstance(item, dict) and item.get("name") == name)
    if (
        entry.get("sha256") != hashlib.sha256(content).hexdigest()
        or entry.get("rowCount") != row_count
    ):
        raise _problem(
            f"manifest.members.{name}",
            _("The migration member does not match its manifest."),
        )


def _csv_rows(name: str, content: bytes, spec: _MemberSpec) -> list[MigrationRow]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise _problem(name, _("Migration CSV members must use UTF-8.")) from None
    if "\x00" in text:
        raise _problem(name, _("The migration CSV member contains an invalid character."))
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        if tuple(reader.fieldnames or ()) != spec.headers:
            raise _problem(name, _("The migration CSV header is unsupported."))
        rows: list[MigrationRow] = []
        identities: set[str] = set()
        for ordinal, raw in enumerate(reader, start=2):
            if ordinal - 1 > MAX_ROWS_PER_MEMBER:
                raise _problem(name, _("The migration CSV row limit was exceeded."))
            if None in raw or len(raw) > MAX_FIELDS_PER_ROW:
                raise _problem(name, _("A migration CSV row has an unsupported shape."))
            values = {field: value if isinstance(value, str) else "" for field, value in raw.items()}
            if any(len(value) > MAX_CELL_CHARACTERS for value in values.values()):
                raise _problem(name, _("A migration CSV value exceeds its limit."))
            if any(value.lstrip().startswith(("=", "+", "-", "@")) for value in values.values()):
                raise _problem(name, _("Migration CSV formulas are not allowed."))
            source_key = values.get("source_key", "").strip()
            findings = list(spec.validator(ordinal, values))
            if _SOURCE_KEY.fullmatch(source_key) is None:
                findings.append(_finding("invalid_source_key", "source_key", _("Enter a valid source key.")))
                source_key = f"invalid-row-{ordinal}"
            folded = source_key.casefold()
            if folded in identities:
                findings.append(_finding("duplicate_source_key", "source_key", _("Source keys must be unique.")))
            identities.add(folded)
            rows.append(
                MigrationRow(
                    family=spec.family,
                    ordinal=ordinal,
                    source_key=source_key,
                    values=tuple((field, values[field]) for field in spec.headers),
                    findings=tuple(findings),
                )
            )
    except csv.Error:
        raise _problem(name, _("The migration CSV member is malformed.")) from None
    if not rows:
        raise _problem(name, _("Each migration CSV member requires at least one row."))
    return rows


def _validate_project(_ordinal: int, row: Mapping[str, str]) -> tuple[MigrationFinding, ...]:
    findings: list[MigrationFinding] = []
    _required(findings, row, "business_code")
    _required(findings, row, "title")
    _required(findings, row, "owner_user_id")
    if row.get("business_code") and _BUSINESS_CODE.fullmatch(row["business_code"].strip()) is None:
        findings.append(_finding("invalid_business_code", "business_code", _("Enter a valid business code.")))
    if row.get("project_type") not in _ALLOWED_PROJECT_TYPES:
        findings.append(_finding("invalid_enum", "project_type", _("Select a supported Project type.")))
    if row.get("owner_user_id") and _EMAIL.fullmatch(row["owner_user_id"].strip()) is None:
        findings.append(_finding("invalid_owner", "owner_user_id", _("Enter a valid Project owner.")))
    try:
        if date.fromisoformat(row.get("target_sop", "")).isoformat() != row.get("target_sop"):
            raise ValueError
    except ValueError:
        findings.append(_finding("invalid_date", "target_sop", _("Enter a valid target SOP date.")))
    _uuid_finding(findings, row, "template_global_id")
    _positive_finding(findings, row, "template_version")
    _positive_finding(findings, row, "template_expected_version")
    return tuple(findings)


def _validate_tooling(_ordinal: int, row: Mapping[str, str]) -> tuple[MigrationFinding, ...]:
    findings: list[MigrationFinding] = []
    _required(findings, row, "project_source_key")
    _uuid_finding(findings, row, "tooling_global_id")
    _positive_finding(findings, row, "target_version")
    _hash_finding(findings, row, "target_snapshot_hash")
    return tuple(findings)


def _validate_file(_ordinal: int, row: Mapping[str, str]) -> tuple[MigrationFinding, ...]:
    findings: list[MigrationFinding] = []
    _required(findings, row, "project_source_key")
    _uuid_finding(findings, row, "file_revision_global_id")
    _positive_finding(findings, row, "file_optimistic_version")
    _hash_finding(findings, row, "file_sha256")
    return tuple(findings)


def _validate_reference(_ordinal: int, row: Mapping[str, str]) -> tuple[MigrationFinding, ...]:
    findings: list[MigrationFinding] = []
    _required(findings, row, "project_source_key")
    _required(findings, row, "source_object_id")
    if row.get("reference_type") not in _ALLOWED_REFERENCE_TYPES:
        findings.append(_finding("invalid_enum", "reference_type", _("Select a supported reference type.")))
    if row.get("source_system") not in _ALLOWED_REFERENCE_SYSTEMS:
        findings.append(_finding("invalid_enum", "source_system", _("Select a supported source system.")))
    return tuple(findings)


def _add_project_reference_findings(
    row: MigrationRow, known_project_keys: set[str]
) -> MigrationRow:
    if row.family is MigrationFamily.PROJECT:
        return row
    project_key = row.value_map.get("project_source_key", "").casefold()
    if project_key in known_project_keys:
        return row
    return MigrationRow(
        family=row.family,
        ordinal=row.ordinal,
        source_key=row.source_key,
        values=row.values,
        findings=(
            *row.findings,
            _finding(
                "missing_project_reference",
                "project_source_key",
                _("The referenced Project source key is not present in the bundle."),
            ),
        ),
    )


def _required(findings: list[MigrationFinding], row: Mapping[str, str], field: str) -> None:
    if not row.get(field, "").strip():
        findings.append(_finding("required", field, _("Enter a value.")))


def _uuid_finding(findings: list[MigrationFinding], row: Mapping[str, str], field: str) -> None:
    try:
        parsed = UUID(row.get(field, ""))
        if str(parsed) != row.get(field, "").casefold():
            raise ValueError
    except (ValueError, AttributeError):
        findings.append(_finding("invalid_uuid", field, _("Enter a canonical global ID.")))


def _positive_finding(findings: list[MigrationFinding], row: Mapping[str, str], field: str) -> None:
    try:
        value = int(row.get(field, ""))
    except ValueError:
        value = 0
    if value < 1 or str(value) != row.get(field):
        findings.append(_finding("invalid_positive_integer", field, _("Enter a positive integer.")))


def _hash_finding(findings: list[MigrationFinding], row: Mapping[str, str], field: str) -> None:
    if _HASH.fullmatch(row.get(field, "")) is None:
        findings.append(_finding("invalid_hash", field, _("Enter a lowercase SHA-256 hash.")))


def _finding(code: str, field: str, message: str) -> MigrationFinding:
    return MigrationFinding(code=code, field=field, message=message)


def _canonical_uuid(value: object, path: str) -> UUID:
    if not isinstance(value, str):
        raise _problem(path, _("Enter a canonical global ID."))
    try:
        parsed = UUID(value)
    except ValueError:
        raise _problem(path, _("Enter a canonical global ID.")) from None
    if str(parsed) != value.casefold():
        raise _problem(path, _("Enter a canonical global ID."))
    return parsed


def _source_system(value: object) -> str:
    if not isinstance(value, str) or _SOURCE_KEY.fullmatch(value) is None:
        raise _problem("manifest.sourceSystem", _("Enter a supported source system."))
    if value in {"NPI_ONE", "ERPNEXT"}:
        raise _problem(
            "manifest.sourceSystem",
            _("Select a legacy source system that is not an active system of record."),
        )
    return value


def _optional_hash(value: object, path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise _problem(path, _("Enter a lowercase SHA-256 hash."))
    return value


def _problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
