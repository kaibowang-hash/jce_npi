from __future__ import annotations

import json
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.engineering_change.domain import TargetMode  # noqa: E402
from npi_integration.engineering_change.ingress import (  # noqa: E402
    IngressProblem,
    authenticate_inbound_request,
)
from npi_integration.engineering_change.signature import (  # noqa: E402
    SignatureHeaders,
    WEBHOOK_PATH,
    sign_request,
)

from tests.test_phase9_change_integration_domain import (  # noqa: E402
    NOW,
    inbound_event,
    profile,
)


class Phase9ChangeIntegrationIngressTest(unittest.TestCase):
    def signed(self) -> tuple[bytes, dict[str, str]]:
        raw = json.dumps(
            inbound_event().envelope(), separators=(",", ":"), sort_keys=True
        ).encode()
        headers = SignatureHeaders(
            request_id="00000000-0000-4000-8000-000000009201",
            key_id="key-2026-08",
            timestamp=str(int(NOW.timestamp())),
            signature="v1=" + "0" * 64,
        )
        signature = sign_request(
            secret=b"p901-exact-test-secret-material-0001",
            method="POST",
            path=WEBHOOK_PATH,
            headers=headers,
            raw_body=raw,
        )
        return raw, {
            "request_id": headers.request_id,
            "key_id": headers.key_id,
            "timestamp": headers.timestamp,
            "signature": signature,
        }

    def authenticate(self, **overrides: object):
        raw, headers = self.signed()
        values = {
            "method": "POST",
            "path": WEBHOOK_PATH,
            "content_type": "application/json",
            "content_encoding": None,
            "raw_body": raw,
            **headers,
            "is_secure": True,
            "site_tenant_id": "tenant-p901",
            "now": NOW,
            "profile_resolver": lambda _tenant, _project: profile(),
            "secret_resolver": lambda _key: b"p901-exact-test-secret-material-0001",
        }
        values.update(overrides)
        return authenticate_inbound_request(**values)

    def test_exact_signed_secure_request_authenticates_without_persisting_secret(self) -> None:
        result = self.authenticate()
        self.assertEqual(result.event, inbound_event())
        self.assertEqual(result.profile.target_mode, TargetMode.SYNTHETIC)
        self.assertEqual(result.received_at, NOW)
        self.assertNotIn(
            "p901-exact-test-secret-material-0001", repr(result).casefold()
        )

    def test_transport_profile_and_signature_fail_closed(self) -> None:
        cases = (
            ({"method": "GET"}, 401),
            ({"path": WEBHOOK_PATH + "/extra"}, 401),
            ({"content_type": "text/plain"}, 415),
            ({"is_secure": False}, 503),
            ({"site_tenant_id": "wrong-tenant"}, 503),
            ({"profile_resolver": lambda _tenant, _project: profile(TargetMode.DISABLED)}, 503),
            ({"signature": "v1=" + "f" * 64}, 401),
            ({"now": datetime(2026, 8, 31, 5, 5, 6, tzinfo=UTC)}, 401),
        )
        for mutation, status in cases:
            with self.subTest(mutation=mutation), self.assertRaises(IngressProblem) as raised:
                self.authenticate(**mutation)
            self.assertEqual(raised.exception.status, status)

    def test_unknown_resolver_shape_and_oversized_body_stop_without_expansion(self) -> None:
        for mutation, status in (
            ({"profile_resolver": None}, 503),
            ({"secret_resolver": None}, 503),
            ({"raw_body": b"x" * 262_145}, 413),
        ):
            with self.subTest(mutation=mutation), self.assertRaises(IngressProblem) as raised:
                self.authenticate(**mutation)
            self.assertEqual(raised.exception.status, status)


if __name__ == "__main__":
    unittest.main()
