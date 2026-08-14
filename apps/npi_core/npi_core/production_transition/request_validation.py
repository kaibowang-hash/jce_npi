from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from npi_core.foundation.errors import RequestValidationFailed

try:
    from frappe import _
except ImportError:  # Keeps the closed request boundary independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


HANDOVER_SOURCE_KINDS = frozenset(
    {
        "readiness_instance_revision",
        "domain_work_item",
        "released_document",
        "release_baseline",
        "file_revision",
        "tooling_capacity_scenario",
        "trial_defect_revision",
        "trial_review_reference",
        "trial_conclusion",
    }
)
MANDATORY_EXTERNAL_PROVIDER_ORDER = (
    "actual_sop",
    "first_batch_yield",
    "customer_complaint",
    "production_cycle_time",
    "tooling_stability",
)
MANDATORY_EXTERNAL_PROVIDER_KINDS = frozenset(MANDATORY_EXTERNAL_PROVIDER_ORDER)
MAX_EXACT_SOURCES = 1_000

_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_EXACT_SOURCE_FIELDS = frozenset({"kind", "globalId", "expectedVersion"})
_MANIFEST_SOURCE_FIELDS = _EXACT_SOURCE_FIELDS | frozenset({"requirementKey"})


@dataclass(frozen=True, slots=True)
class ExactSourceSelection:
    """One observation identity; its usage, projection and hash remain server-owned."""

    kind: str
    global_id: UUID
    expected_version: int


@dataclass(frozen=True, slots=True)
class ManifestSourceSelection:
    """One requirement-bound handover identity without caller role or source truth."""

    requirement_key: str
    kind: str
    global_id: UUID
    expected_version: int


@dataclass(frozen=True, slots=True)
class AcknowledgementIntent:
    """The only actor-independent acknowledgement values accepted from a caller."""

    expected_revision_global_id: UUID
    expected_snapshot_hash: str
    slot_key: str
    intent: str


@dataclass(frozen=True, slots=True)
class ObservationRevisionRequest:
    """Exact predecessor plus NPI review context; external actuals are not accepted."""

    expected_revision_global_id: UUID | None
    expected_snapshot_hash: str | None
    context_sources: tuple[ExactSourceSelection, ...]
    retrospective_sources: tuple[ExactSourceSelection, ...]
    retrospective_note: str | None
    reason: str


def closed_payload(
    value: object,
    path: str,
    allowed: frozenset[str],
    required: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Return a mapping only when supplied and required fields are closed."""

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


def parse_exact_source_selection(
    value: object,
    path: str = "source",
) -> ExactSourceSelection:
    """Accept only one closed registry tuple without a caller projection or hash."""

    record = closed_payload(value, path, _EXACT_SOURCE_FIELDS)
    kind = _closed_value(
        record["kind"],
        _child_path(path, "kind"),
        HANDOVER_SOURCE_KINDS,
    )
    return ExactSourceSelection(
        kind=kind,
        global_id=_uuid(record["globalId"], _child_path(path, "globalId")),
        expected_version=_positive(
            record["expectedVersion"],
            _child_path(path, "expectedVersion"),
        ),
    )


def parse_manifest_source_selection(
    value: object,
    path: str = "source",
) -> ManifestSourceSelection:
    """Accept a policy requirement plus exact source tuple, but no role or hash."""

    record = closed_payload(value, path, _MANIFEST_SOURCE_FIELDS)
    kind = _closed_value(
        record["kind"],
        _child_path(path, "kind"),
        HANDOVER_SOURCE_KINDS,
    )
    return ManifestSourceSelection(
        requirement_key=_key(
            record["requirementKey"],
            _child_path(path, "requirementKey"),
        ),
        kind=kind,
        global_id=_uuid(record["globalId"], _child_path(path, "globalId")),
        expected_version=_positive(
            record["expectedVersion"],
            _child_path(path, "expectedVersion"),
        ),
    )


def parse_manifest_source_selections(
    value: object,
    path: str = "manifestSources",
) -> tuple[ManifestSourceSelection, ...]:
    """Parse bounded handover selections without double-counting one exact source."""

    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or len(value) < 1
        or len(value) > MAX_EXACT_SOURCES
    ):
        raise _field(path, _("Enter a valid bounded list."))
    parsed = tuple(
        parse_manifest_source_selection(item, f"{path}[{index}]")
        for index, item in enumerate(value)
    )
    identities = tuple((item.kind, item.global_id) for item in parsed)
    if len(set(identities)) != len(identities):
        raise _field(path, _("Values must be unique."))
    return parsed


def parse_exact_source_selections(
    value: object,
    path: str = "sources",
) -> tuple[ExactSourceSelection, ...]:
    """Parse a bounded, duplicate-free ordered exact-source selection."""

    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or len(value) > MAX_EXACT_SOURCES
    ):
        raise _field(path, _("Enter a valid bounded list."))
    parsed = tuple(
        parse_exact_source_selection(item, f"{path}[{index}]")
        for index, item in enumerate(value)
    )
    identities = tuple((item.kind, item.global_id) for item in parsed)
    if len(set(identities)) != len(identities):
        raise _field(path, _("Values must be unique."))
    return parsed


def parse_acknowledgement_intent(
    value: object,
    path: str = "acknowledgement",
) -> AcknowledgementIntent:
    """Reject caller actor, time, signature, approval and derived completion truth."""

    fields = frozenset(
        {
            "expectedRevisionGlobalId",
            "expectedSnapshotHash",
            "slotKey",
            "intent",
        }
    )
    record = closed_payload(value, path, fields)
    intent = _closed_value(
        record["intent"],
        _child_path(path, "intent"),
        frozenset({"acknowledge"}),
    )
    return AcknowledgementIntent(
        expected_revision_global_id=_uuid(
            record["expectedRevisionGlobalId"],
            _child_path(path, "expectedRevisionGlobalId"),
        ),
        expected_snapshot_hash=_hash(
            record["expectedSnapshotHash"],
            _child_path(path, "expectedSnapshotHash"),
        ),
        slot_key=_key(record["slotKey"], _child_path(path, "slotKey")),
        intent=intent,
    )


def parse_observation_revision_request(
    value: object,
    *,
    successor: bool,
    path: str = "observation",
) -> ObservationRevisionRequest:
    """Parse an observation create/successor without accepting external truth."""

    predecessor_fields = frozenset(
        {"expectedRevisionGlobalId", "expectedSnapshotHash"}
    )
    fields = predecessor_fields | frozenset(
        {"contextSources", "retrospectiveSources", "retrospectiveNote", "reason"}
    )
    required = frozenset(
        {"contextSources", "retrospectiveSources", "retrospectiveNote", "reason"}
    ) | (
        predecessor_fields if successor else frozenset()
    )
    record = closed_payload(value, path, fields, required)
    retrospective_note = record["retrospectiveNote"]
    if retrospective_note is not None and (
        not isinstance(retrospective_note, str)
        or len(retrospective_note.strip()) > 4_000
    ):
        raise _field(
            _child_path(path, "retrospectiveNote"),
            _("Enter a valid value."),
        )
    reason = record["reason"]
    if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 1_000:
        raise _field(_child_path(path, "reason"), _("Enter a valid value."))
    if not successor and predecessor_fields & set(record):
        raise _field(path, _("This field is not allowed."))
    context_sources = parse_exact_source_selections(
        record["contextSources"],
        _child_path(path, "contextSources"),
    )
    retrospective_sources = parse_exact_source_selections(
        record["retrospectiveSources"],
        _child_path(path, "retrospectiveSources"),
    )
    context_versions = {
        (source.kind, source.global_id): source.expected_version
        for source in context_sources
    }
    if any(
        context_versions.get((source.kind, source.global_id), source.expected_version)
        != source.expected_version
        for source in retrospective_sources
    ):
        raise _field(
            _child_path(path, "retrospectiveSources"),
            _("Enter a valid value."),
        )
    return ObservationRevisionRequest(
        expected_revision_global_id=(
            _uuid(
                record["expectedRevisionGlobalId"],
                _child_path(path, "expectedRevisionGlobalId"),
            )
            if successor
            else None
        ),
        expected_snapshot_hash=(
            _hash(
                record["expectedSnapshotHash"],
                _child_path(path, "expectedSnapshotHash"),
            )
            if successor
            else None
        ),
        context_sources=context_sources,
        retrospective_sources=retrospective_sources,
        retrospective_note=(
            retrospective_note.strip()
            if isinstance(retrospective_note, str)
            else None
        ),
        reason=reason.strip(),
    )


def assert_mandatory_provider_kinds(value: object, path: str = "providers") -> None:
    """Require the server-fixed provider set when validating internal assemblies."""

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise _field(path, _("Enter a valid bounded list."))
    actual = tuple(value)
    if actual != MANDATORY_EXTERNAL_PROVIDER_ORDER:
        raise _field(path, _("Select all required values exactly once."))


def _closed_value(value: object, path: str, allowed: frozenset[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise _field(path, _("Select a supported value."))
    return value


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
