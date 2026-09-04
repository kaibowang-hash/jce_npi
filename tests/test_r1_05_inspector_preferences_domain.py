from __future__ import annotations

import sys
import unittest


sys.path.insert(0, "apps/npi_core")

from npi_core.inspector_preferences.domain import (  # noqa: E402
    DEFAULT_COLLAPSED,
    DEFAULT_WIDTH_PX,
    MAXIMUM_WIDTH_PX,
    MINIMUM_WIDTH_PX,
    PANE_ID,
    SCHEMA_VERSION,
    STORED_PREFERENCE_INVALID,
    InspectorPreference,
    InspectorPreferenceValidationError,
    decode_stored_preference,
    encode_stored_preference,
)


class InspectorPreferenceDomainTest(unittest.TestCase):
    def preference_payload(
        self,
        *,
        width_px: object = DEFAULT_WIDTH_PX,
        collapsed: object = DEFAULT_COLLAPSED,
        schema_version: object = SCHEMA_VERSION,
    ) -> dict[str, object]:
        return {
            "schemaVersion": schema_version,
            "widthPx": width_px,
            "collapsed": collapsed,
        }

    def test_default_and_response_contract_are_exact(self) -> None:
        preference = InspectorPreference.default()

        self.assertEqual(preference.width_px, 340)
        self.assertIs(preference.collapsed, False)
        self.assertEqual(
            preference.response_dict(recovery_reason=None),
            {
                "paneId": PANE_ID,
                "schemaVersion": SCHEMA_VERSION,
                "widthPx": 340,
                "collapsed": False,
                "recoveryReason": None,
            },
        )
        self.assertEqual(
            preference.response_dict(
                recovery_reason=STORED_PREFERENCE_INVALID,
            )["recoveryReason"],
            STORED_PREFERENCE_INVALID,
        )

    def test_valid_bounds_and_exact_boolean_round_trip_canonically(
        self,
    ) -> None:
        for width_px, collapsed in (
            (MINIMUM_WIDTH_PX, False),
            (DEFAULT_WIDTH_PX, True),
            (MAXIMUM_WIDTH_PX, False),
        ):
            with self.subTest(width_px=width_px, collapsed=collapsed):
                preference = InspectorPreference.parse(
                    self.preference_payload(
                        width_px=width_px,
                        collapsed=collapsed,
                    )
                )
                encoded = encode_stored_preference(preference)

                self.assertEqual(
                    encoded,
                    (
                        f'{{"collapsed":{str(collapsed).lower()},'
                        f'"schemaVersion":"{SCHEMA_VERSION}",'
                        f'"widthPx":{width_px}}}'
                    ),
                )
                self.assertEqual(
                    decode_stored_preference(encoded),
                    preference,
                )

    def test_width_rejects_out_of_bounds_and_non_exact_integers(self) -> None:
        for invalid_width in (
            MINIMUM_WIDTH_PX - 1,
            MAXIMUM_WIDTH_PX + 1,
            True,
            False,
            340.0,
            "340",
            None,
        ):
            with self.subTest(invalid_width=invalid_width):
                with self.assertRaises(
                    InspectorPreferenceValidationError
                ) as raised:
                    InspectorPreference.parse(
                        self.preference_payload(width_px=invalid_width)
                    )
                self.assertEqual(raised.exception.path, "widthPx")

    def test_collapsed_rejects_truthy_values_that_are_not_booleans(
        self,
    ) -> None:
        for invalid_collapsed in (0, 1, "true", None, [], {}):
            with self.subTest(invalid_collapsed=invalid_collapsed):
                with self.assertRaises(
                    InspectorPreferenceValidationError
                ) as raised:
                    InspectorPreference.parse(
                        self.preference_payload(
                            collapsed=invalid_collapsed,
                        )
                    )
                self.assertEqual(raised.exception.path, "collapsed")

    def test_schema_and_exact_fields_are_closed(self) -> None:
        cases = (
            (
                {
                    "schemaVersion": SCHEMA_VERSION,
                    "widthPx": 340,
                },
                "collapsed",
            ),
            (
                {
                    **self.preference_payload(),
                    "paneId": PANE_ID,
                },
                "paneId",
            ),
            (
                self.preference_payload(schema_version="future-schema"),
                "schemaVersion",
            ),
            (
                self.preference_payload(schema_version=1),
                "schemaVersion",
            ),
        )
        for payload, expected_path in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(
                    InspectorPreferenceValidationError
                ) as raised:
                    InspectorPreference.parse(payload)
                self.assertEqual(raised.exception.path, expected_path)

    def test_stored_json_rejects_malformed_duplicate_and_non_object_values(
        self,
    ) -> None:
        invalid_values = (
            None,
            {"schemaVersion": SCHEMA_VERSION},
            "{",
            "[]",
            "null",
            (
                '{"schemaVersion":"my-work-inspector-v1",'
                '"widthPx":340,"widthPx":341,"collapsed":false}'
            ),
            (
                '{"schemaVersion":"my-work-inspector-v1",'
                '"widthPx":NaN,"collapsed":false}'
            ),
            "[" * 1100 + "]" * 1100,
        )
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(InspectorPreferenceValidationError):
                    decode_stored_preference(value)


if __name__ == "__main__":
    unittest.main()
