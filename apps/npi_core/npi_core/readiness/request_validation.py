from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.readiness.domain import (
    EXTERNAL_SOURCE_KINDS,
    MAX_SOURCES,
    ReadinessSourceKind,
)

try:
    from frappe import _
except ImportError:  # Keeps request parsing independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_COMMON_FIELDS = frozenset({"requirementKey", "kind"})
_SOURCE_EXACT_FIELDS = frozenset({"globalId", "sourceVersion", "snapshotHash"})


@dataclass(frozen=True, slots=True)
class ReadinessSourceRequest:
    """One caller-selected source kind and, for internal facts, one exact identity."""

    requirement_key: str
    kind: ReadinessSourceKind
    global_id: UUID | None
    source_version: int | None
    snapshot_hash: str | None


def closed_payload(
    value: object,
    path: str,
    allowed: frozenset[str],
    required: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Return a mapping only when every supplied and required field is explicit."""

    if not isinstance(value, Mapping):
        raise _field(path, _("Enter a valid object."))
    required_fields = allowed if required is None else required
    unexpected = sorted(
        (name for name in value if not isinstance(name, str) or name not in allowed),
        key=str,
    )
    if unexpected:
        raise RequestValidationFailed(
            [
                {
                    "path": _child_path(path, str(name)),
                    "message": _("This field is not allowed."),
                }
                for name in unexpected
            ]
        )
    missing = sorted(required_fields - set(value))
    if missing:
        raise RequestValidationFailed(
            [
                {
                    "path": _child_path(path, name),
                    "message": _("This field is required."),
                }
                for name in missing
            ]
        )
    return dict(value)


def parse_source_request(
    value: object,
    path: str = "source",
) -> ReadinessSourceRequest:
    """Parse one source without accepting caller-derived state or containment."""

    record = closed_payload(
        value,
        path,
        _SOURCE_COMMON_FIELDS | _SOURCE_EXACT_FIELDS,
        _SOURCE_COMMON_FIELDS,
    )
    kind = _source_kind(record["kind"], _child_path(path, "kind"))
    requirement_key = _key(record["requirementKey"], _child_path(path, "requirementKey"))
    if kind in EXTERNAL_SOURCE_KINDS:
        closed_payload(record, path, _SOURCE_COMMON_FIELDS)
        return ReadinessSourceRequest(requirement_key, kind, None, None, None)

    exact = closed_payload(
        record,
        path,
        _SOURCE_COMMON_FIELDS | _SOURCE_EXACT_FIELDS,
    )
    return ReadinessSourceRequest(
        requirement_key=requirement_key,
        kind=kind,
        global_id=_uuid(exact["globalId"], _child_path(path, "globalId")),
        source_version=_positive(
            exact["sourceVersion"],
            _child_path(path, "sourceVersion"),
        ),
        snapshot_hash=_hash(
            exact["snapshotHash"],
            _child_path(path, "snapshotHash"),
        ),
    )


def parse_source_requests(
    value: object,
    path: str = "sources",
) -> tuple[ReadinessSourceRequest, ...]:
    """Parse a bounded, duplicate-free list of exact or provider-unavailable sources."""

    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or len(value) > MAX_SOURCES
    ):
        raise _field(path, _("Enter a valid bounded list."))
    result = tuple(
        parse_source_request(item, f"{path}[{index}]")
        for index, item in enumerate(value)
    )
    identities = tuple(
        (
            item.requirement_key,
            item.kind,
            item.global_id,
            item.source_version,
        )
        for item in result
    )
    if len(set(identities)) != len(identities):
        raise _field(path, _("Values must be unique."))
    return result


def _source_kind(value: object, path: str) -> ReadinessSourceKind:
    if not isinstance(value, str):
        raise _field(path, _("Select a supported value."))
    try:
        return ReadinessSourceKind(value)
    except ValueError as error:
        raise _field(path, _("Select a supported value.")) from error


def _uuid(value: object, path: str) -> UUID:
    if not isinstance(value, str):
        raise _field(path, _("Enter a valid global ID."))
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as error:
        raise _field(path, _("Enter a valid global ID.")) from error
    if str(parsed) != value.casefold():
        raise _field(path, _("Enter a valid global ID."))
    return parsed


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _field(path, _("Enter a positive integer."))
    return value


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise _field(path, _("Enter a valid SHA-256 hash."))
    return value


def _key(value: object, path: str) -> str:
    if not isinstance(value, str) or _KEY.fullmatch(value) is None:
        raise _field(path, _("Enter a valid value."))
    return value


def _child_path(path: str, field_name: str) -> str:
    return f"{path}.{field_name}" if path else field_name


def _field(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
