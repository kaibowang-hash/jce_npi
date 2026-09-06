from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Mapping

try:
    from frappe import _
except ImportError:

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


PANE_ID = "my-work-inspector"
SCHEMA_VERSION = "my-work-inspector-v1"
USER_DEFAULT_KEY = "npi_one_my_work_inspector_layout_v1"
MINIMUM_WIDTH_PX = 260
MAXIMUM_WIDTH_PX = 480
DEFAULT_WIDTH_PX = 340
DEFAULT_COLLAPSED = False
STORED_PREFERENCE_INVALID = "stored_preference_invalid"

_PREFERENCE_FIELDS = frozenset({"schemaVersion", "widthPx", "collapsed"})
_MAX_STORED_PREFERENCE_CHARACTERS = 512


class InspectorPreferenceValidationError(ValueError):
    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}")


def _fail(path: str, message: str) -> InspectorPreferenceValidationError:
    return InspectorPreferenceValidationError(path, message)


@dataclass(frozen=True, slots=True)
class InspectorPreference:
    width_px: int
    collapsed: bool

    @classmethod
    def default(cls) -> InspectorPreference:
        return cls(width_px=DEFAULT_WIDTH_PX, collapsed=DEFAULT_COLLAPSED)

    @classmethod
    def parse(cls, value: object) -> InspectorPreference:
        if not isinstance(value, Mapping):
            raise _fail(
                "preference",
                _("Enter an object with the exact supported fields."),
            )

        field_names = set(value)
        unexpected_fields = sorted(
            field_names - _PREFERENCE_FIELDS,
            key=str,
        )
        if unexpected_fields:
            raise _fail(
                unexpected_fields[0],
                _("This field is not allowed."),
            )
        missing_fields = sorted(_PREFERENCE_FIELDS - field_names)
        if missing_fields:
            raise _fail(
                missing_fields[0],
                _("This field is required."),
            )

        if (
            type(value["schemaVersion"]) is not str
            or value["schemaVersion"] != SCHEMA_VERSION
        ):
            raise _fail(
                "schemaVersion",
                _("Select the supported My Work inspector schema."),
            )

        width_px = value["widthPx"]
        if (
            type(width_px) is not int
            or width_px < MINIMUM_WIDTH_PX
            or width_px > MAXIMUM_WIDTH_PX
        ):
            raise _fail(
                "widthPx",
                _("Enter an inspector width within the supported range."),
            )

        collapsed = value["collapsed"]
        if type(collapsed) is not bool:
            raise _fail(
                "collapsed",
                _("Select a valid true or false value."),
            )

        return cls(width_px=width_px, collapsed=collapsed)

    def storage_dict(self) -> dict[str, object]:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "widthPx": self.width_px,
            "collapsed": self.collapsed,
        }

    def response_dict(
        self,
        *,
        recovery_reason: str | None,
    ) -> dict[str, object]:
        if recovery_reason not in {None, STORED_PREFERENCE_INVALID}:
            raise ValueError("The inspector recovery reason is invalid.")
        return {
            "paneId": PANE_ID,
            "schemaVersion": SCHEMA_VERSION,
            "widthPx": self.width_px,
            "collapsed": self.collapsed,
            "recoveryReason": recovery_reason,
        }


def encode_stored_preference(preference: InspectorPreference) -> str:
    return json.dumps(
        preference.storage_dict(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )


def decode_stored_preference(value: object) -> InspectorPreference:
    if (
        type(value) is not str
        or len(value) > _MAX_STORED_PREFERENCE_CHARACTERS
    ):
        raise _fail(
            "storedPreference",
            _("The stored inspector preference is invalid."),
        )

    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        parsed: dict[str, object] = {}
        for key, item in pairs:
            if key in parsed:
                raise ValueError("Duplicate JSON object field.")
            parsed[key] = item
        return parsed

    def reject_constant(_value: str) -> object:
        raise ValueError("Non-finite JSON number.")

    try:
        parsed = json.loads(
            value,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
        return InspectorPreference.parse(parsed)
    except InspectorPreferenceValidationError:
        raise
    except (RecursionError, TypeError, ValueError) as error:
        raise _fail(
            "storedPreference",
            _("The stored inspector preference is invalid."),
        ) from error
