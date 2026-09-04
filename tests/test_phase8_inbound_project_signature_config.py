from __future__ import annotations

import inspect
import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.inbound_project.config import (
    BusinessCodeMode,
    InboundProjectProfile,
    ProjectIntakePolicy,
    WebhookKeyDescriptor,
)
from npi_integration.inbound_project.domain import (
    ProjectSourceContractError,
    ProjectSourceEventType,
    ProjectSourceObjectType,
)
from npi_integration.inbound_project.signature import (
    REPLAY_WINDOW_SECONDS,
    WEBHOOK_METHOD,
    WEBHOOK_PATH,
    SignatureHeaders,
    WebhookAuthenticationError,
    sign_request,
    verify_request_signature,
)
import npi_integration.inbound_project.signature as signature_module


NOW = datetime(2026, 8, 16, 5, 0, tzinfo=UTC)
SECRET_OLD = b"old-synthetic-secret-material-000000000001"
SECRET_NEW = b"new-synthetic-secret-material-000000000002"
BODY = b'{"synthetic":true}'


def unsigned_headers(*, key_id: str = "erpnext-old", timestamp: int | None = None) -> SignatureHeaders:
    return SignatureHeaders(
        request_id=str(UUID(int=1)),
        key_id=key_id,
        timestamp=str(int(NOW.timestamp()) if timestamp is None else timestamp),
        signature="v1=" + "0" * 64,
    )


def signed_headers(*, secret: bytes = SECRET_OLD, base: SignatureHeaders | None = None) -> SignatureHeaders:
    candidate = base or unsigned_headers()
    signature = sign_request(
        secret=secret,
        method=WEBHOOK_METHOD,
        path=WEBHOOK_PATH,
        headers=candidate,
        raw_body=BODY,
    )
    return replace(candidate, signature=signature)


def policy(object_type: ProjectSourceObjectType) -> ProjectIntakePolicy:
    return ProjectIntakePolicy(
        source_object_type=object_type,
        template_global_id=UUID(int=10 if object_type is ProjectSourceObjectType.QUOTATION else 11),
        template_version=1,
        project_type="new_tool",
        owner_user_id="npi-owner@example.invalid",
        business_code_mode=BusinessCodeMode.SOURCE_DOCUMENT_ID,
    )


def profile(**changes: object) -> InboundProjectProfile:
    values: dict[str, object] = {
        "profile_id": "erpnext-sandbox-v1",
        "version": 1,
        "tenant_id": "tenant-synthetic",
        "environment_code": "sandbox",
        "non_production_attested": True,
        "enabled": True,
        "trusted_tls_termination": True,
        "service_actor_user_id": "npi-integration@example.invalid",
        "allowed_event_types": (
            ProjectSourceEventType.QUOTATION_SUBMITTED,
            ProjectSourceEventType.SALES_ORDER_SUBMITTED,
        ),
        "keys": (
            WebhookKeyDescriptor(
                "erpnext-old",
                "secrets/erpnext-old",
                NOW - timedelta(days=1),
                NOW + timedelta(hours=1),
            ),
            WebhookKeyDescriptor(
                "erpnext-new",
                "secrets/erpnext-new",
                NOW - timedelta(hours=1),
                NOW + timedelta(days=1),
            ),
        ),
        "policies": (
            policy(ProjectSourceObjectType.QUOTATION),
            policy(ProjectSourceObjectType.SALES_ORDER),
        ),
    }
    values.update(changes)
    return InboundProjectProfile(**values)  # type: ignore[arg-type]


class Phase8InboundProjectSignatureConfigTest(unittest.TestCase):
    def test_policy_snapshot_round_trips_only_the_frozen_closed_shape(self) -> None:
        original = policy(ProjectSourceObjectType.QUOTATION)
        restored = ProjectIntakePolicy.from_snapshot(original.snapshot())
        self.assertEqual(restored, original)
        self.assertEqual(restored.snapshot_hash, original.snapshot_hash)
        for invalid in (
            {**original.snapshot(), "unexpected": True},
            {key: value for key, value in original.snapshot().items() if key != "owner_user_id"},
            {**original.snapshot(), "schema_version": 2},
            {**original.snapshot(), "business_code_mode": "caller_supplied"},
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ProjectSourceContractError):
                    ProjectIntakePolicy.from_snapshot(invalid)

    def test_exact_raw_signature_binds_method_path_key_timestamp_request_and_body(self) -> None:
        headers = signed_headers()
        verify_request_signature(
            secret=SECRET_OLD,
            method=WEBHOOK_METHOD,
            path=WEBHOOK_PATH,
            headers=headers,
            raw_body=BODY,
            now=NOW,
        )
        with self.assertRaises(WebhookAuthenticationError):
            verify_request_signature(
                secret=SECRET_OLD,
                method=WEBHOOK_METHOD,
                path=WEBHOOK_PATH,
                headers=headers,
                raw_body=BODY + b" ",
                now=NOW,
            )
        for method, path in (("GET", WEBHOOK_PATH), (WEBHOOK_METHOD, WEBHOOK_PATH + "/")):
            with self.subTest(method=method, path=path):
                with self.assertRaises(WebhookAuthenticationError):
                    verify_request_signature(
                        secret=SECRET_OLD,
                        method=method,
                        path=path,
                        headers=headers,
                        raw_body=BODY,
                        now=NOW,
                    )
        for changed in (
            replace(headers, key_id="erpnext-new"),
            replace(headers, request_id=str(UUID(int=2))),
            replace(headers, timestamp=str(int(NOW.timestamp()) + 1)),
        ):
            with self.subTest(headers=changed):
                with self.assertRaises(WebhookAuthenticationError):
                    verify_request_signature(
                        secret=SECRET_OLD,
                        method=WEBHOOK_METHOD,
                        path=WEBHOOK_PATH,
                        headers=changed,
                        raw_body=BODY,
                        now=NOW,
                    )

    def test_replay_window_edges_are_inclusive_and_shape_failures_are_generic(self) -> None:
        self.assertEqual(REPLAY_WINDOW_SECONDS, 300)
        for offset in (-300, 300):
            base = unsigned_headers(timestamp=int(NOW.timestamp()) + offset)
            verify_request_signature(
                secret=SECRET_OLD,
                method=WEBHOOK_METHOD,
                path=WEBHOOK_PATH,
                headers=signed_headers(base=base),
                raw_body=BODY,
                now=NOW,
            )
        for offset in (-301, 301):
            base = unsigned_headers(timestamp=int(NOW.timestamp()) + offset)
            with self.assertRaisesRegex(
                WebhookAuthenticationError, "Webhook authentication failed"
            ):
                verify_request_signature(
                    secret=SECRET_OLD,
                    method=WEBHOOK_METHOD,
                    path=WEBHOOK_PATH,
                    headers=signed_headers(base=base),
                    raw_body=BODY,
                    now=NOW,
                )
        for invalid in ("V1=" + "0" * 64, "v1=" + "A" * 64, "v2=" + "0" * 64):
            with self.assertRaises(WebhookAuthenticationError):
                replace(unsigned_headers(), signature=invalid)

    def test_verifier_uses_standard_constant_time_comparison(self) -> None:
        source = inspect.getsource(signature_module.verify_request_signature)
        self.assertIn("hmac.compare_digest", source)
        self.assertNotIn("expected == headers.signature", source)

    def test_overlapping_rotation_keys_are_allowed_but_identity_is_unambiguous(self) -> None:
        configured = profile()
        self.assertEqual(configured.key_at("erpnext-old", NOW).secret_reference, "secrets/erpnext-old")
        self.assertEqual(configured.key_at("erpnext-new", NOW).secret_reference, "secrets/erpnext-new")
        secrets = {
            "secrets/erpnext-old": SECRET_OLD,
            "secrets/erpnext-new": SECRET_NEW,
        }
        self.assertEqual(
            configured.resolve_secret("erpnext-new", NOW, secrets.__getitem__),
            SECRET_NEW,
        )
        with self.assertRaises(KeyError):
            configured.key_at("missing", NOW)
        with self.assertRaises(KeyError):
            configured.key_at("erpnext-old", NOW + timedelta(days=2))
        with self.assertRaises(ProjectSourceContractError):
            profile(keys=(configured.keys[0], configured.keys[0]))

    def test_profile_and_policy_reject_raw_secret_production_and_ambiguous_scope(self) -> None:
        with self.assertRaises(ProjectSourceContractError):
            WebhookKeyDescriptor(
                "erpnext-raw",
                "this-is-raw-secret-material",
                NOW,
            )
        for environment in ("prod", "production", "live", "unknown"):
            with self.subTest(environment=environment):
                with self.assertRaises(ProjectSourceContractError):
                    profile(environment_code=environment)
        with self.assertRaises(ProjectSourceContractError):
            profile(service_actor_user_id="Guest")
        with self.assertRaises(ProjectSourceContractError):
            profile(service_actor_user_id="Administrator")
        with self.assertRaises(ProjectSourceContractError):
            profile(
                allowed_event_types=(
                    ProjectSourceEventType.QUOTATION_SUBMITTED,
                ),
                policies=(policy(ProjectSourceObjectType.QUOTATION),),
            )
        with self.assertRaises(ProjectSourceContractError):
            profile(policies=(policy(ProjectSourceObjectType.QUOTATION),))
        with self.assertRaises(ProjectSourceContractError):
            replace(policy(ProjectSourceObjectType.QUOTATION), project_type="invented")
        disabled = profile(enabled=False)
        with self.assertRaises(KeyError):
            disabled.resolve_secret("erpnext-old", NOW, lambda _: SECRET_OLD)

    def test_frozen_snapshots_never_contain_secret_material_or_secret_reference(self) -> None:
        configured = profile()
        snapshot = configured.snapshot()
        rendered = repr(snapshot)
        self.assertNotIn("secret_reference", rendered)
        self.assertNotIn(SECRET_OLD.decode("ascii"), rendered)
        self.assertEqual(len(configured.snapshot_hash), 64)
        for configured_policy in configured.policies:
            self.assertEqual(len(configured_policy.snapshot_hash), 64)


if __name__ == "__main__":
    unittest.main()
