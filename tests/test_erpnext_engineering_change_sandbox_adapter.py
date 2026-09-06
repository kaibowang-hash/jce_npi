from __future__ import annotations

import hashlib
import hmac
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_APP = ROOT / "apps/npi_integration"
if str(INTEGRATION_APP) not in sys.path:
    sys.path.insert(0, str(INTEGRATION_APP))

from npi_integration.engineering_change.adapters import AdapterCommand  # noqa: E402
from npi_integration.engineering_change.connector_runtime import (  # noqa: E402
    SANDBOX_ADAPTER_PATH,
    SANDBOX_ENABLED_KEY,
    SANDBOX_PROFILES_KEY,
    SUMMARY_METHOD_PATH,
    SandboxCredential,
    execute_sandbox_summary,
    load_sandbox_credential,
    load_sandbox_profile,
    load_sandbox_signing_secret,
)
from npi_integration.engineering_change.domain import (  # noqa: E402
    ChangeImplementationSummary,
    FormalChangeObservation,
)

PROJECT_ID = "00000000-0000-4000-8000-000000009001"
CHANGE_ID = "00000000-0000-4000-8000-000000009002"
REVISION_ID = "00000000-0000-4000-8000-000000009003"
REQUEST_ID = UUID("00000000-0000-4000-8000-000000009004")
ATTEMPT_ID = UUID("00000000-0000-4000-8000-000000009005")
NOW = 1_788_537_600
API_KEY = "ApiKey1234567890"
API_SECRET = "secret-value-1234567890abcdef"
SIGNING_SECRET = "webhook-secret-value-1234567890abcdef"


def profile_mapping() -> dict[str, object]:
    return {
        "profileId": "erpnext-test-engineering-change-v1",
        "profileVersion": 1,
        "tenantId": "tenant-sandbox",
        "projectGlobalId": PROJECT_ID,
        "environmentCode": "test",
        "requesterUserIds": ["publisher@example.invalid"],
        "serviceActorUserId": "worker@example.invalid",
        "signingKeyIds": ["engineering-change-test-v1"],
        "baseUrl": "https://erpnext.test.example.invalid",
        "allowedHostnames": ["erpnext.test.example.invalid"],
        "secretReference": "secrets/erpnext-test-engineering-change-v1",
        "connectTimeoutSeconds": 3,
        "readTimeoutSeconds": 10,
    }


def configuration() -> dict[str, object]:
    return {
        SANDBOX_ENABLED_KEY: True,
        SANDBOX_PROFILES_KEY: [profile_mapping()],
    }


def serialized_secrets() -> str:
    return json.dumps(
        {
            "secrets/erpnext-test-engineering-change-v1": {
                "apiKey": API_KEY,
                "apiSecret": API_SECRET,
            }
        }
    )


def serialized_ingress_secrets() -> str:
    return json.dumps({"engineering-change-test-v1": SIGNING_SECRET})


def command() -> AdapterCommand:
    observed = datetime(2026, 9, 5, 9, 0, tzinfo=timezone.utc)
    summary = ChangeImplementationSummary(
        tenant_id="tenant-sandbox",
        project_global_id=UUID(PROJECT_ID),
        change_global_id=UUID(CHANGE_ID),
        revision_global_id=UUID(REVISION_ID),
        revision_number=2,
        revision_snapshot_hash="1" * 64,
        formal_change=FormalChangeObservation(
            document_name="ECR-2026-00001",
            raw_status="Closed",
            source_version="7",
            source_modified_at=observed,
            source_hash="2" * 64,
            observed_at=observed,
        ),
        affected_versions_hash="3" * 64,
        effectivity_hash="4" * 64,
        disposition_hash="5" * 64,
        revalidation_hash="6" * 64,
        closure_evidence_hash="7" * 64,
    )
    payload = {
        **summary.payload(),
        "actor_user_id": "publisher@example.invalid",
        "request_global_id": str(REQUEST_ID),
        "profile_id": "erpnext-test-engineering-change-v1",
        "profile_version": 1,
        "profile_snapshot_hash": "8" * 64,
        "source_hash": summary.source_hash,
    }
    return AdapterCommand(
        request_global_id=REQUEST_ID,
        attempt_global_id=ATTEMPT_ID,
        attempt_number=1,
        target_idempotency_key_hash="9" * 64,
        source_hash=summary.source_hash,
        payload=payload,
    )


def response_body(value: AdapterCommand, credential: SandboxCredential) -> bytes:
    core = {
        "contractVersion": 1,
        "operation": "record_change_implementation_summary",
        "requestGlobalId": str(value.request_global_id),
        "attemptGlobalId": str(value.attempt_global_id),
        "attemptNumber": value.attempt_number,
        "targetIdempotencyKeyHash": value.target_idempotency_key_hash,
        "sourceHash": value.source_hash,
        "httpStatus": 200,
        "summaryProjectionId": REVISION_ID,
        "exactReplay": False,
        "partial": False,
        "retryAfterSeconds": None,
        "errorCode": None,
    }
    response_hash = hashlib.sha256(_json(core).encode()).hexdigest()
    signed = {**core, "responseHash": response_hash, "signatureVersion": "npi-hmac-sha256-v1", "signedAt": NOW}
    signature = hmac.new(
        credential.response_signing_secret.encode(),
        _json(signed).encode(),
        hashlib.sha256,
    ).hexdigest()
    return _json({"message": {**signed, "responseSignature": signature}}).encode()


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.status_code = 200
        self.headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Content-Length": str(len(body)),
        }
        self.closed = False

    def iter_content(self, chunk_size: int):
        self.chunk_size = chunk_size
        yield self.body

    def close(self) -> None:
        self.closed = True


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.trust_env = True
        self.call: dict[str, object] | None = None
        self.closed = False

    def post(self, endpoint: str, **kwargs: object) -> FakeResponse:
        self.call = {"endpoint": endpoint, **kwargs}
        return self.response

    def close(self) -> None:
        self.closed = True


class ERPNextEngineeringChangeSandboxAdapterTest(unittest.TestCase):
    def test_profile_and_credentials_are_closed_nonproduction_and_default_off(self) -> None:
        self.assertIsNone(load_sandbox_profile({}, "tenant-sandbox", PROJECT_ID))
        profile = load_sandbox_profile(configuration(), "tenant-sandbox", PROJECT_ID)
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile.adapter_resolver, SANDBOX_ADAPTER_PATH)
        credential = load_sandbox_credential(
            "secrets/erpnext-test-engineering-change-v1",
            serialized_secrets(),
        )
        self.assertEqual(credential.api_key, API_KEY)
        self.assertEqual(
            load_sandbox_signing_secret(
                "engineering-change-test-v1",
                serialized_ingress_secrets(),
            ),
            SIGNING_SECRET.encode(),
        )
        invalid = profile_mapping()
        invalid["environmentCode"] = "production"
        invalid["baseUrl"] = "https://erpnext.production.example.invalid"
        invalid["allowedHostnames"] = ["erpnext.production.example.invalid"]
        with self.assertRaises(ValueError):
            load_sandbox_profile(
                {
                    SANDBOX_ENABLED_KEY: True,
                    SANDBOX_PROFILES_KEY: [invalid],
                },
                "tenant-sandbox",
                PROJECT_ID,
            )

    def test_adapter_sends_actor_bound_signed_command_and_accepts_only_signed_result(self) -> None:
        profile = load_sandbox_profile(configuration(), "tenant-sandbox", PROJECT_ID)
        assert profile is not None
        credential = load_sandbox_credential(
            "secrets/erpnext-test-engineering-change-v1",
            serialized_secrets(),
        )
        value = command()
        remote = FakeResponse(response_body(value, credential))
        session = FakeSession(remote)
        result = execute_sandbox_summary(
            value,
            profile,
            credential,
            session_factory=lambda: session,
            clock=lambda: NOW,
        )
        self.assertTrue(result.authenticated)
        self.assertTrue(result.contract_valid)
        self.assertEqual(result.http_status, 200)
        assert session.call is not None
        self.assertEqual(
            session.call["endpoint"],
            "https://erpnext.test.example.invalid" + SUMMARY_METHOD_PATH,
        )
        self.assertFalse(session.call["allow_redirects"])
        posted = json.loads(session.call["data"])
        self.assertEqual(posted["actorUserId"], "publisher@example.invalid")
        self.assertEqual(posted["source"]["actor_user_id"], posted["actorUserId"])
        self.assertFalse(session.trust_env)
        self.assertTrue(session.closed)
        self.assertTrue(remote.closed)

        tampered = response_body(value, credential).replace(
            REVISION_ID.encode(),
            b"00000000-0000-4000-8000-000000009099",
        )
        rejected = execute_sandbox_summary(
            value,
            profile,
            credential,
            session_factory=lambda: FakeSession(FakeResponse(tampered)),
            clock=lambda: NOW,
        )
        self.assertFalse(rejected.authenticated)
        self.assertFalse(rejected.contract_valid)


def _json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


if __name__ == "__main__":
    unittest.main()
