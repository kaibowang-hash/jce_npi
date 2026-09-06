from __future__ import annotations

import base64
import hashlib
import sys
import unittest

sys.path.insert(0, "apps/npi_core")

from npi_core.controlled_print.qr import (
    verification_qr_data_uri,
    verification_qr_digest,
    verification_qr_matrix,
    verification_qr_svg,
)


PAYLOAD = (
    "urn:npi:controlled-print:00000000-0000-4000-8000-000000000605:"
    + "a" * 64
)


class Phase5ControlledPrintQrTest(unittest.TestCase):
    def test_fixed_version_six_vector_is_stable(self) -> None:
        matrix = verification_qr_matrix(PAYLOAD)
        bits = "".join("1" if value else "0" for row in matrix for value in row)

        self.assertEqual(len(matrix), 41)
        self.assertTrue(all(len(row) == 41 for row in matrix))
        self.assertEqual(
            hashlib.sha256(bits.encode("ascii")).hexdigest(),
            "90a3d8c0b43bf4d368dc0562abb3011eb9cfcec4b0bb63d0b647969ec9980250",
        )

    def test_svg_is_self_contained_deterministic_and_does_not_echo_payload(
        self,
    ) -> None:
        svg = verification_qr_svg(PAYLOAD)

        self.assertEqual(svg, verification_qr_svg(PAYLOAD))
        self.assertIn('viewBox="0 0 49 49"', svg)
        self.assertIn('shape-rendering="crispEdges"', svg)
        self.assertNotIn(PAYLOAD, svg)
        self.assertEqual(
            verification_qr_digest(PAYLOAD),
            hashlib.sha256(svg.encode("utf-8")).hexdigest(),
        )

    def test_data_uri_contains_only_the_exact_svg(self) -> None:
        uri = verification_qr_data_uri(PAYLOAD)
        prefix = "data:image/svg+xml;base64,"

        self.assertTrue(uri.startswith(prefix))
        decoded = base64.b64decode(uri.removeprefix(prefix)).decode("utf-8")
        self.assertEqual(decoded, verification_qr_svg(PAYLOAD))

    def test_invalid_payload_and_quiet_zone_fail_closed(self) -> None:
        for payload in (
            "https://example.invalid/verify",
            PAYLOAD.replace(":aaaaaaaa", ":AAAAAAAA", 1),
            PAYLOAD + "a",
        ):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                verification_qr_matrix(payload)
        for quiet_zone in (3, 17, True):
            with self.subTest(quiet_zone=quiet_zone), self.assertRaises(ValueError):
                verification_qr_svg(PAYLOAD, quiet_zone=quiet_zone)

    def test_finder_alignment_timing_and_dark_modules_are_present(self) -> None:
        matrix = verification_qr_matrix(PAYLOAD)

        for center_x, center_y in ((3, 3), (37, 3), (3, 37)):
            self.assertTrue(matrix[center_y][center_x])
            self.assertFalse(matrix[center_y - 2][center_x])
            self.assertTrue(matrix[center_y - 3][center_x])
        self.assertTrue(matrix[34][34])
        self.assertFalse(matrix[33][34])
        self.assertTrue(matrix[32][34])
        self.assertTrue(matrix[33][8])


if __name__ == "__main__":
    unittest.main()
