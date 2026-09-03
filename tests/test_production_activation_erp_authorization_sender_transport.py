from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sys
import unittest
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
ERP_APP = ROOT / "apps/npi_erpnext_connector"
if str(ERP_APP) not in sys.path:
    sys.path.insert(0, str(ERP_APP))

from npi_erpnext_connector.config import SenderProfile, load_profile, sender_is_disabled  # noqa: E402
from npi_erpnext_connector.domain import (  # noqa: E402
    AuthorizationSenderError,
    SenderPolicy,
    SourceUser,
    build_event,
    project_source_user,
)
from npi_erpnext_connector.transport import (  # noqa: E402
    PermanentDeliveryError,
    RetryableDeliveryError,
    deliver,
)


class _Response:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self.payload = payload
        self.closed = False

    def json(self) -> object:
        return self.payload

    def iter_content(self, *, chunk_size: int):
        body = json.dumps(self.payload, separators=(",", ":")).encode()
        yield from (body[index : index + chunk_size] for index in range(0, len(body), chunk_size))

    def close(self) -> None:
        self.closed = True


class _Session:
    def __init__(self, response: _Response | Exception) -> None:
        self.response = response
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def put(self, *args: object, **kwargs: object) -> _Response:
        self.calls.append((args, kwargs))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _event():
    policy = SenderPolicy.from_mapping(
        {
            "roleMap": {"Manufacturing User": "NPI Engineer"},
            "projectMap": {},
            "projectAccessByRole": {},
            "ttlSeconds": 3600,
        }
    )
    snapshot = project_source_user(
        SourceUser(
            "user@example.com",
            "user@example.com",
            True,
            "System User",
            ("Manufacturing User",),
            (),
        ),
        policy,
    )
    return build_event(
        snapshot,
        source_version=1,
        issued_at=datetime(2026, 9, 4, tzinfo=UTC),
        ttl_seconds=3600,
    )


def _profile() -> SenderProfile:
    return SenderProfile(
        "https://launchflow.example.com",
        SenderPolicy.from_mapping(
            {
                "roleMap": {"Manufacturing User": "NPI Engineer"},
                "projectMap": {},
                "projectAccessByRole": {},
                "ttlSeconds": 3600,
            }
        ),
    )


def _result(event: object) -> dict[str, object]:
    return {
        "projectionId": "73dd7689-f12a-4f30-ad20-ae047d25a7aa",
        "sourceVersion": event.event["sourceVersion"],
        "state": "enabled",
        "projectionHash": "a" * 64,
        "exactReplay": False,
        "localUserState": "enabled",
        "localUserDisposition": "created",
        "requestId": str(event.request_id),
        "traceId": event.trace_id,
    }


class ProductionActivationERPAuthorizationSenderTransportTest(unittest.TestCase):
    def test_profile_is_default_disabled_and_requires_closed_https_origin(self) -> None:
        self.assertTrue(sender_is_disabled({}))
        self.assertTrue(sender_is_disabled({"npi_erp_authorization_sender_disabled": 0}))
        with self.assertRaisesRegex(AuthorizationSenderError, "disabled"):
            load_profile({})
        config = {
            "npi_erp_authorization_sender_disabled": False,
            "npi_erp_authorization_target_base_url": "https://launchflow.example.com",
            "npi_erp_authorization_role_map": {
                "Manufacturing User": "NPI Engineer"
            },
            "npi_erp_authorization_project_map": {},
            "npi_erp_authorization_project_access_by_role": {},
            "npi_erp_authorization_ttl_seconds": 3600,
        }
        self.assertEqual(
            load_profile(config).endpoint,
            "https://launchflow.example.com/api/npi/v1/integration/erpnext/user-authorization",
        )
        for invalid in (
            "http://launchflow.example.com",
            "https://user@launchflow.example.com",
            "https://launchflow.example.com/path",
            "https://launchflow.example.com?query=1",
            "https://launchflow.example.com:8443",
        ):
            with self.subTest(invalid=invalid):
                changed = dict(config)
                changed["npi_erp_authorization_target_base_url"] = invalid
                with self.assertRaisesRegex(AuthorizationSenderError, "HTTPS origin"):
                    load_profile(changed)

    def test_delivery_uses_fixed_route_headers_timeout_and_no_redirect(self) -> None:
        event = _event()
        response = _Response(200, _result(event))
        session = _Session(response)
        receipt = deliver(
            _profile(),
            event,
            session=session,
            environment={"NPI_ERP_AUTHORIZATION_TOKEN": "token key:secret"},
        )
        self.assertEqual(receipt.projection_hash, "a" * 64)
        self.assertEqual(receipt.local_user_disposition, "created")
        self.assertTrue(response.closed)
        self.assertEqual(len(session.calls), 1)
        args, kwargs = session.calls[0]
        self.assertEqual(
            args,
            (
                "https://launchflow.example.com/api/npi/v1/integration/erpnext/user-authorization",
            ),
        )
        self.assertEqual(kwargs["json"], event.event)
        self.assertEqual(kwargs["timeout"], (3.05, 10.0))
        self.assertFalse(kwargs["allow_redirects"])
        self.assertTrue(kwargs["stream"])
        self.assertEqual(kwargs["headers"]["Authorization"], "token key:secret")
        self.assertEqual(kwargs["headers"]["X-Request-ID"], str(event.request_id))

    def test_retryable_and_permanent_failures_store_only_safe_codes(self) -> None:
        event = _event()
        for status, expected in (
            (429, RetryableDeliveryError),
            (503, RetryableDeliveryError),
            (401, PermanentDeliveryError),
            (409, PermanentDeliveryError),
        ):
            with self.subTest(status=status):
                response = _Response(status, {"secret": "must-not-leak"})
                with self.assertRaises(expected) as raised:
                    deliver(
                        _profile(),
                        event,
                        session=_Session(response),
                        environment={
                            "NPI_ERP_AUTHORIZATION_TOKEN": "token key:secret"
                        },
                    )
                self.assertEqual(raised.exception.code, f"HTTP_{status}")
                self.assertNotIn("secret", str(raised.exception))
                self.assertTrue(response.closed)

    def test_response_must_bind_request_source_version_trace_and_state(self) -> None:
        event = _event()
        for key, value in (
            ("requestId", str(UUID(int=1))),
            ("sourceVersion", 2),
            ("sourceVersion", True),
            ("traceId", "different-trace"),
            ("state", "disabled"),
            ("localUserState", "unknown"),
        ):
            with self.subTest(key=key):
                payload = _result(event)
                payload[key] = value
                with self.assertRaisesRegex(
                    RetryableDeliveryError,
                    "INVALID_RESPONSE_BINDING",
                ):
                    deliver(
                        _profile(),
                        event,
                        session=_Session(_Response(200, payload)),
                        environment={
                            "NPI_ERP_AUTHORIZATION_TOKEN": "token key:secret"
                        },
                    )

    def test_response_body_is_bounded_before_json_parsing(self) -> None:
        response = _Response(200, {"oversized": "x" * 70_000})
        with self.assertRaisesRegex(RetryableDeliveryError, "RESPONSE_TOO_LARGE"):
            deliver(
                _profile(),
                _event(),
                session=_Session(response),
                environment={"NPI_ERP_AUTHORIZATION_TOKEN": "token key:secret"},
            )
        self.assertTrue(response.closed)

    def test_service_token_is_runtime_only_and_fails_closed(self) -> None:
        for value in (None, "", "Bearer value", "token no-colon", "token key:value\n"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    PermanentDeliveryError,
                    "SERVICE_TOKEN_UNAVAILABLE",
                ):
                    deliver(
                        _profile(),
                        _event(),
                        session=_Session(_Response(200, {})),
                        environment=(
                            {}
                            if value is None
                            else {"NPI_ERP_AUTHORIZATION_TOKEN": value}
                        ),
                    )


if __name__ == "__main__":
    unittest.main()
