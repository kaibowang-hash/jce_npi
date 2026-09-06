from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from frappe import _

from npi_core.foundation.errors import RequestValidationFailed


RETAIN_RELEASED_SUMMARY_FIELDS = frozenset(
    {
        "expectedRoundOptimisticVersion",
        "expectedRoundSnapshotHash",
        "conclusionRevisionGlobalId",
        "expectedConclusionVersion",
        "expectedConclusionSnapshotHash",
        "reason",
    }
)
REVISE_RELEASED_SUMMARY_FIELDS = frozenset(
    {
        *RETAIN_RELEASED_SUMMARY_FIELDS,
        "predecessorRevisionGlobalId",
        "expectedPredecessorVersion",
        "expectedPredecessorSnapshotHash",
    }
)

_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def retain_released_summary_values(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "expected_round_optimistic_version": _positive(
            value["expectedRoundOptimisticVersion"],
            "expectedRoundOptimisticVersion",
        ),
        "expected_round_snapshot_hash": _hash(
            value["expectedRoundSnapshotHash"],
            "expectedRoundSnapshotHash",
        ),
        "conclusion_revision_id": _uuid(
            value["conclusionRevisionGlobalId"],
            "conclusionRevisionGlobalId",
        ),
        "expected_conclusion_version": _positive(
            value["expectedConclusionVersion"],
            "expectedConclusionVersion",
        ),
        "expected_conclusion_snapshot_hash": _hash(
            value["expectedConclusionSnapshotHash"],
            "expectedConclusionSnapshotHash",
        ),
        "reason": _text(value["reason"], "reason", 2_000),
    }


def revise_released_summary_values(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **retain_released_summary_values(value),
        "predecessor_revision_id": _uuid(
            value["predecessorRevisionGlobalId"],
            "predecessorRevisionGlobalId",
        ),
        "expected_predecessor_version": _positive(
            value["expectedPredecessorVersion"],
            "expectedPredecessorVersion",
        ),
        "expected_predecessor_snapshot_hash": _hash(
            value["expectedPredecessorSnapshotHash"],
            "expectedPredecessorSnapshotHash",
        ),
    }


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _problem(path, _("Enter a positive integer."))
    return value


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise _problem(path, _("Enter a valid SHA-256 hash."))
    return value


def _uuid(value: object, path: str) -> UUID:
    try:
        result = UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise _problem(path, _("Enter a valid global ID.")) from error
    if str(result) != str(value).casefold():
        raise _problem(path, _("Enter a valid global ID."))
    return result


def _text(value: object, path: str, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or value != value.strip()
        or not value
        or len(value) > maximum
        or any(ord(character) < 32 for character in value)
    ):
        raise _problem(path, _("Enter a valid value."))
    return value


def _problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
