from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_APP = ROOT / "apps/npi_integration"
if str(INTEGRATION_APP) not in sys.path:
    sys.path.insert(0, str(INTEGRATION_APP))

from npi_integration.project_publish.config import (  # noqa: E402
    ENABLED_KEY,
    PROFILES_KEY,
    SECRETS_ENV,
    configured_environments,
    load_profile,
)
from npi_integration.project_publish.connector_runtime import (  # noqa: E402
    PUBLISH_PATH,
    Credential,
    load_credential,
    publish,
)
from npi_integration.project_publish.domain import (  # noqa: E402
    ProjectSource,
    PublishCommand,
    canonical_hash,
    canonical_json,
)


NOW = 1_788_537_600
PROJECT_ID = "00000000-0000-4000-8000-000000007001"
REQUEST_ID = "00000000-0000-4000-8000-000000007002"
ATTEMPT_ID = "00000000-0000-4000-8000-000000007003"
SIGNATURE_VERSION = "npi-hmac-sha256-v1"


def profile_mapping() -> dict[str, object]:
    return {
        "profileId": "erpnext-test-project-v1",
        "profileVersion": 1,
        "tenantId": "TENANT-SANDBOX",
        "environmentCode": "test",
        "serviceActorUserId": "worker@example.invalid",
        "baseUrl": "https://erpnext.test.example.invalid",
        "allowedHostnames": ["erpnext.test.example.invalid"],
        "secretReference": "secrets/erpnext-test-item-v1",
        "connectTimeoutSeconds": 3,
        "readTimeoutSeconds": 10,
    }


def configuration() -> dict[str, object]:
    return {ENABLED_KEY: True, PROFILES_KEY: [profile_mapping()]}


def command() -> PublishCommand:
    source = ProjectSource(
        tenant_id="TENANT-SANDBOX",
        project_global_id=PROJECT_ID,
        business_code="MM-TEST-001",
        title="Sandbox project",
        project_type="new_tool",
        target_sop="2026-12-31",
        actor_user_id="publisher@example.invalid",
        source_version=1,
    )
    return PublishCommand(REQUEST_ID, ATTEMPT_ID, 1, source)


def signed_body(value: PublishCommand, credential: Credential) -> bytes:
    core = {
        "contractVersion": 1,
        "operation": "create_erp_project",
        "requestGlobalId": value.request_global_id,
        "attemptGlobalId": value.attempt_global_id,
        "attemptNumber": value.attempt_number,
        "targetIdempotencyKeyHash": value.source.target_idempotency_key_hash,
        "sourceHash": value.source.source_hash,
        "httpStatus": 200,
        "formalProjectId": "PROJ-0042",
        "targetVersion": "2026-09-06 10:00:00.000001",
        "exactReplay": False,
        "errorCode": None,
    }
    signed = {
        **core,
        "responseHash": canonical_hash(core),
        "signatureVersion": SIGNATURE_VERSION,
        "signedAt": NOW,
    }
    signature = hmac.new(
        credential.signing_secret.encode(),
        canonical_json(signed).encode(),
        hashlib.sha256,
    ).hexdigest()
    return canonical_json({"message": {**signed, "responseSignature": signature}}).encode()


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.status_code = 200
        self.headers = {
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
        }
        self.body = body
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
        self.closed = False
        self.call: dict[str, object] | None = None

    def post(self, endpoint: str, **kwargs: object) -> FakeResponse:
        self.call = {"endpoint": endpoint, **kwargs}
        return self.response

    def close(self) -> None:
        self.closed = True


class ProjectPublishConnectorRuntimeTest(unittest.TestCase):
    def test_profile_and_shared_credential_are_closed_and_non_production(self) -> None:
        self.assertIsNone(load_profile({}, "TENANT-SANDBOX"))
        profile = load_profile(configuration(), "TENANT-SANDBOX")
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(configured_environments(configuration()), ("test",))
        unsafe = configuration()
        unsafe[PROFILES_KEY] = [
            {
                **profile_mapping(),
                "environmentCode": "production",
                "baseUrl": "https://erpnext.example.invalid",
                "allowedHostnames": ["erpnext.example.invalid"],
            }
        ]
        with self.assertRaisesRegex(ValueError, "non-production"):
            load_profile(unsafe, "TENANT-SANDBOX")
        prior = os.environ.get(SECRETS_ENV)
        try:
            os.environ[SECRETS_ENV] = json.dumps(
                {
                    "secrets/erpnext-test-item-v1": {
                        "apiKey": "abcdefgh12345678",
                        "apiSecret": "sandbox-secret-value",
                    }
                }
            )
            credential = load_credential(profile)
            self.assertEqual(credential.api_key, "abcdefgh12345678")
        finally:
            if prior is None:
                os.environ.pop(SECRETS_ENV, None)
            else:
                os.environ[SECRETS_ENV] = prior

    def test_adapter_posts_exact_actor_bound_command_and_accepts_signed_result(self) -> None:
        value = command()
        profile = load_profile(configuration(), "TENANT-SANDBOX")
        assert profile is not None
        credential = Credential("abcdefgh12345678", "sandbox-secret-value")
        response = FakeResponse(signed_body(value, credential))
        session = FakeSession(response)
        observed = publish(
            value,
            profile,
            credential,
            session_factory=lambda: session,
            clock=lambda: NOW,
        )
        self.assertTrue(observed.authenticated)
        self.assertTrue(observed.contract_valid)
        self.assertEqual(observed.formal_project_id, "PROJ-0042")
        assert session.call is not None
        self.assertEqual(
            session.call["endpoint"],
            f"https://erpnext.test.example.invalid{PUBLISH_PATH}",
        )
        posted = json.loads(session.call["data"])
        self.assertEqual(posted["actorUserId"], "publisher@example.invalid")
        self.assertEqual(posted["source"]["projectGlobalId"], PROJECT_ID)
        self.assertFalse(session.call["allow_redirects"])
        self.assertFalse(session.trust_env)
        self.assertTrue(session.closed)
        self.assertTrue(response.closed)

    def test_tampered_result_never_becomes_authoritative(self) -> None:
        value = command()
        profile = load_profile(configuration(), "TENANT-SANDBOX")
        assert profile is not None
        credential = Credential("abcdefgh12345678", "sandbox-secret-value")
        body = signed_body(value, credential).replace(b"PROJ-0042", b"PROJ-0099")
        observed = publish(
            value,
            profile,
            credential,
            session_factory=lambda: FakeSession(FakeResponse(body)),
            clock=lambda: NOW,
        )
        self.assertFalse(observed.authenticated)
        self.assertFalse(observed.contract_valid)
        self.assertIsNone(observed.formal_project_id)


if __name__ == "__main__":
    unittest.main()
