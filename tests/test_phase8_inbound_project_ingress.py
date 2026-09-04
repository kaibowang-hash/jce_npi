from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.inbound_project.domain import MAX_RAW_BODY_BYTES
from npi_integration.inbound_project.ingress import (
    InboundProjectIngressProblem,
    authenticate_project_source_request,
)
from npi_integration.inbound_project.signature import (
    WEBHOOK_METHOD,
    WEBHOOK_PATH,
    SignatureHeaders,
    sign_request,
)
import npi_integration.inbound_project.ingress as ingress_module
from tests.test_phase8_inbound_project_domain import raw
from tests.test_phase8_inbound_project_signature_config import (
    NOW,
    SECRET_OLD,
    profile,
)


def headers_for(
    body: bytes,
    *,
    key_id: str = "erpnext-old",
    timestamp: datetime = NOW,
    request_id: str = str(UUID(int=101)),
    secret: bytes = SECRET_OLD,
) -> SignatureHeaders:
    unsigned = SignatureHeaders(
        request_id=request_id,
        key_id=key_id,
        timestamp=str(int(timestamp.timestamp())),
        signature="v1=" + "0" * 64,
    )
    return replace(
        unsigned,
        signature=sign_request(
            secret=secret,
            method=WEBHOOK_METHOD,
            path=WEBHOOK_PATH,
            headers=unsigned,
            raw_body=body,
        ),
    )


class Phase8InboundProjectIngressTest(unittest.TestCase):
    def authenticate(self, body: bytes | None = None, **changes: object):
        candidate = raw() if body is None else body
        headers = changes.pop("headers", headers_for(candidate))
        values: dict[str, object] = {
            "method": WEBHOOK_METHOD,
            "path": WEBHOOK_PATH,
            "content_type": "application/json; charset=UTF-8",
            "content_encoding": None,
            "raw_body": candidate,
            "request_id": headers.request_id,
            "key_id": headers.key_id,
            "timestamp": headers.timestamp,
            "signature": headers.signature,
            "is_secure": False,
            "site_tenant_id": "tenant-synthetic",
            "now": NOW,
            "profile_resolver": profile,
            "secret_resolver": lambda reference: {
                "secrets/erpnext-old": SECRET_OLD,
            }[reference],
        }
        values.update(changes)
        return authenticate_project_source_request(**values)  # type: ignore[arg-type]

    def assert_problem(self, code: str, status: int, function) -> None:
        with self.assertRaises(InboundProjectIngressProblem) as caught:
            function()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(caught.exception.status, status)

    def test_valid_raw_request_authenticates_before_closed_event_parse(self) -> None:
        order: list[str] = []
        original_parse = ingress_module.parse_project_source_event

        def resolve_profile():
            order.append("profile")
            return profile()

        def resolve_secret(reference: str) -> bytes:
            order.append("secret")
            self.assertEqual(reference, "secrets/erpnext-old")
            return SECRET_OLD

        def parse_event(body: bytes):
            order.append("parse")
            return original_parse(body)

        ingress_module.parse_project_source_event = parse_event
        try:
            authenticated = self.authenticate(
                profile_resolver=resolve_profile,
                secret_resolver=resolve_secret,
            )
        finally:
            ingress_module.parse_project_source_event = original_parse
        self.assertEqual(order, ["profile", "secret", "parse"])
        self.assertEqual(authenticated.event.source_object_id, "QTN-SYNTHETIC-0001")
        self.assertEqual(authenticated.profile.tenant_id, "tenant-synthetic")
        self.assertEqual(authenticated.policy.project_type, "new_tool")

    def test_bad_signature_stale_time_unknown_key_and_tls_fail_before_parser(self) -> None:
        original_parse = ingress_module.parse_project_source_event
        parsed = False

        def parse_event(body: bytes):
            nonlocal parsed
            parsed = True
            return original_parse(body)

        ingress_module.parse_project_source_event = parse_event
        try:
            body = raw()
            bad = replace(headers_for(body), signature="v1=" + "0" * 64)
            faults = (
                {"headers": bad},
                {
                    "headers": headers_for(
                        body,
                        timestamp=NOW - timedelta(seconds=301),
                    )
                },
                {
                    "headers": headers_for(body, key_id="unknown"),
                },
                {
                    "is_secure": False,
                    "profile_resolver": lambda: profile(
                        trusted_tls_termination=False
                    ),
                },
                {"path": WEBHOOK_PATH + "/"},
                {"method": "GET"},
                {"request_id": None},
                {"key_id": None},
                {"timestamp": None},
                {"signature": None},
            )
            for changes in faults:
                with self.subTest(changes=changes):
                    self.assert_problem(
                        "INBOUND_PROJECT_AUTHENTICATION_FAILED",
                        401,
                        lambda changes=changes: self.authenticate(**changes),
                    )
            self.assertFalse(parsed)
        finally:
            ingress_module.parse_project_source_event = original_parse

    def test_transport_bounds_are_closed_and_signed_malformed_json_is_422(self) -> None:
        for media_type in (
            None,
            "text/plain",
            "application/json; charset=latin-1",
            "application/json; profile=generic",
        ):
            with self.subTest(media_type=media_type):
                self.assert_problem(
                    "INBOUND_PROJECT_MEDIA_TYPE_UNSUPPORTED",
                    415,
                    lambda media_type=media_type: self.authenticate(
                        content_type=media_type
                    ),
                )
        self.assert_problem(
            "INBOUND_PROJECT_MEDIA_TYPE_UNSUPPORTED",
            415,
            lambda: self.authenticate(content_encoding="gzip"),
        )
        self.assert_problem(
            "INBOUND_PROJECT_BODY_TOO_LARGE",
            413,
            lambda: self.authenticate(b"x" * (MAX_RAW_BODY_BYTES + 1)),
        )
        malformed = b'{"event_id":'
        self.assert_problem(
            "INBOUND_PROJECT_EVENT_INVALID",
            422,
            lambda: self.authenticate(malformed, headers=headers_for(malformed)),
        )

    def test_profile_tenant_and_secret_resolution_are_disabled_by_default(self) -> None:
        for changes in (
            {"profile_resolver": None},
            {"profile_resolver": lambda: None},
            {"profile_resolver": lambda: profile(enabled=False)},
            {"site_tenant_id": "another-tenant"},
            {"secret_resolver": None},
            {"secret_resolver": lambda _reference: b"short"},
        ):
            with self.subTest(changes=changes):
                self.assert_problem(
                    "INBOUND_PROJECT_INGRESS_UNAVAILABLE",
                    503,
                    lambda changes=changes: self.authenticate(**changes),
                )


if __name__ == "__main__":
    unittest.main()
