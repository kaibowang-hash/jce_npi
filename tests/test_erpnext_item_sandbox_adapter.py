from __future__ import annotations

import hashlib
import hmac
import json
import sys
import unittest
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_APP = ROOT / "apps/npi_integration"
if str(INTEGRATION_APP) not in sys.path:
    sys.path.insert(0, str(INTEGRATION_APP))

from npi_integration.item_publish.adapters import (  # noqa: E402
    ItemAdapterCommand,
)
from npi_integration.item_publish.connector_runtime import (  # noqa: E402
    ITEM_METHOD_PATH,
    SANDBOX_ADAPTER_PATH,
    SANDBOX_ENABLED_KEY,
    SANDBOX_PROFILES_KEY,
    SandboxCredential,
    execute_sandbox_item,
    load_sandbox_credential,
    load_sandbox_profile,
)
from npi_integration.item_publish.domain import (  # noqa: E402
    ItemPublishIntent,
    canonical_hash,
)

PROJECT_ID = "00000000-0000-4000-8000-000000002001"
REQUEST_ID = UUID("00000000-0000-4000-8000-000000002002")
ATTEMPT_ID = UUID("00000000-0000-4000-8000-000000002003")
NODE_ID = "00000000-0000-4000-8000-000000002004"
LINE_ID = "00000000-0000-4000-8000-000000002005"
NOW = 1_788_537_600
SIGNATURE_VERSION = "npi-hmac-sha256-v1"


def signed_response(
    payload: dict[str, object], secret: str, *, now: int
) -> dict[str, object]:
    value = {**payload, "signatureVersion": SIGNATURE_VERSION, "signedAt": now}
    canonical = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    signature = hmac.new(
        secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {**value, "responseSignature": signature}


def profile_mapping() -> dict[str, object]:
    return {
        "profileId": "erpnext-test-item-v1",
        "profileVersion": 1,
        "tenantId": "TENANT-SANDBOX",
        "projectGlobalId": PROJECT_ID,
        "environmentCode": "test",
        "requesterUserIds": ["publisher@example.invalid"],
        "serviceActorUserId": "worker@example.invalid",
        "baseUrl": "https://erpnext.test.example.invalid",
        "allowedHostnames": ["erpnext.test.example.invalid"],
        "secretReference": "secrets/erpnext-test-item-v1",
        "connectTimeoutSeconds": 3,
        "readTimeoutSeconds": 10,
    }


def configuration() -> dict[str, object]:
    return {
        SANDBOX_ENABLED_KEY: True,
        SANDBOX_PROFILES_KEY: [profile_mapping()],
    }


def command() -> ItemAdapterCommand:
    item = {
        "description": "Sandbox engineering item",
        "engineeringUom": "Nos",
        "attributes": {"material": "PA66"},
    }
    source_payload = {
        "schemaVersion": 1,
        "tenantId": "TENANT-SANDBOX",
        "projectGlobalId": PROJECT_ID,
        "engineeringItemId": "ENG-ITEM-001",
        "selectedPublishNodeGlobalId": NODE_ID,
        "itemMaster": item,
        "occurrences": [
            {
                "publishNodeGlobalId": NODE_ID,
                "lineGlobalId": LINE_ID,
                "engineeringItemId": "ENG-ITEM-001",
                **item,
                "lineHash": "1" * 64,
                "nodeInputHash": "2" * 64,
            }
        ],
    }
    source_hash = canonical_hash(source_payload)
    return ItemAdapterCommand(
        request_global_id=REQUEST_ID,
        attempt_global_id=ATTEMPT_ID,
        attempt_number=1,
        target_idempotency_key_hash="3" * 64,
        source_hash=source_hash,
        actor_user_id="publisher@example.invalid",
        source_snapshot={
            **source_payload,
            "streamKeyHash": canonical_hash(
                {
                    "schemaVersion": 1,
                    "tenantId": "TENANT-SANDBOX",
                    "projectGlobalId": PROJECT_ID,
                    "engineeringItemId": "ENG-ITEM-001",
                }
            ),
            "sourceHash": source_hash,
        },
        intent=ItemPublishIntent.CREATE_ITEM,
        expected_mapping_version=0,
        expected_target_version=None,
    )


def response_body(
    value: ItemAdapterCommand,
    credential: SandboxCredential,
    *,
    status: int = 200,
) -> bytes:
    success = 200 <= status < 300
    core = {
        "contractVersion": 2,
        "operation": "publish_released_item",
        "requestGlobalId": str(value.request_global_id),
        "attemptGlobalId": str(value.attempt_global_id),
        "attemptNumber": value.attempt_number,
        "targetIdempotencyKeyHash": value.target_idempotency_key_hash,
        "sourceHash": value.source_hash,
        "httpStatus": status,
        "formalItemCode": "NPI-SBX-ENG-ITEM-001" if success else None,
        "targetVersion": "2026-09-05 09:00:00.000001" if success else None,
        "mappingVersion": 1 if success else None,
        "exactReplay": False,
        "errorCode": None if success else "ITEM_PUBLISH_CONFIGURATION_INVALID",
    }
    message = signed_response(
        {**core, "responseHash": canonical_hash(core)},
        credential.signing_secret,
        now=NOW,
    )
    return json.dumps(
        {"message": message},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.body = body
        self.status_code = status
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
        self.closed = False
        self.call: dict[str, object] | None = None

    def post(self, endpoint: str, **kwargs: object) -> FakeResponse:
        self.call = {"endpoint": endpoint, **kwargs}
        return self.response

    def close(self) -> None:
        self.closed = True


class ERPNextItemSandboxAdapterTest(unittest.TestCase):
    def test_profile_is_default_disabled_closed_and_non_production_only(self) -> None:
        self.assertIsNone(load_sandbox_profile({}, "TENANT-SANDBOX", PROJECT_ID))
        profile = load_sandbox_profile(
            configuration(),
            "TENANT-SANDBOX",
            PROJECT_ID,
        )
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile.adapter_resolver, SANDBOX_ADAPTER_PATH)
        self.assertEqual(profile.base_url, "https://erpnext.test.example.invalid")
        self.assertIsNone(
            load_sandbox_profile(configuration(), "TENANT-OTHER", PROJECT_ID)
        )

        production = configuration()
        production[SANDBOX_PROFILES_KEY] = [
            {
                **profile_mapping(),
                "environmentCode": "production",
                "baseUrl": "https://erpnext.example.invalid",
                "allowedHostnames": ["erpnext.example.invalid"],
            }
        ]
        with self.assertRaisesRegex(ValueError, "non-production"):
            load_sandbox_profile(production, "TENANT-SANDBOX", PROJECT_ID)

    def test_credentials_are_closed_and_selected_by_opaque_reference(self) -> None:
        serialized = json.dumps(
            {
                "secrets/erpnext-test-item-v1": {
                    "apiKey": "abcdefgh12345678",
                    "apiSecret": "sandbox-secret-value",
                }
            }
        )
        value = load_sandbox_credential(
            "secrets/erpnext-test-item-v1",
            serialized,
        )
        self.assertEqual(value.api_key, "abcdefgh12345678")
        with self.assertRaisesRegex(ValueError, "unavailable"):
            load_sandbox_credential("secrets/missing", serialized)
        with self.assertRaisesRegex(ValueError, "unavailable"):
            load_sandbox_credential(
                "secrets/erpnext-test-item-v1",
                '{"secrets/erpnext-test-item-v1":{},"secrets/erpnext-test-item-v1":{}}',
            )

    def test_adapter_posts_exact_signed_command_and_accepts_signed_result(self) -> None:
        value = command()
        profile = load_sandbox_profile(
            configuration(),
            "TENANT-SANDBOX",
            PROJECT_ID,
        )
        assert profile is not None
        credential = SandboxCredential(
            "abcdefgh12345678",
            "sandbox-secret-value",
        )
        remote_response = FakeResponse(response_body(value, credential))
        session = FakeSession(remote_response)
        result = execute_sandbox_item(
            value,
            profile,
            credential,
            session_factory=lambda: session,
            clock=lambda: NOW,
        )
        self.assertTrue(result.response_authenticated)
        self.assertTrue(result.response_contract_valid)
        self.assertEqual(result.formal_item_code, "NPI-SBX-ENG-ITEM-001")
        self.assertEqual(result.http_status, 200)
        assert session.call is not None
        self.assertEqual(
            session.call["endpoint"],
            f"https://erpnext.test.example.invalid{ITEM_METHOD_PATH}",
        )
        self.assertFalse(session.call["allow_redirects"])
        self.assertEqual(session.call["timeout"], (3, 10))
        self.assertTrue(session.call["stream"])
        posted = json.loads(session.call["data"])
        self.assertEqual(posted["contractVersion"], 2)
        self.assertEqual(posted["actorUserId"], "publisher@example.invalid")
        self.assertFalse(session.trust_env)
        self.assertTrue(session.closed)
        self.assertTrue(remote_response.closed)
        headers = session.call["headers"]
        self.assertIsInstance(headers, dict)
        assert isinstance(headers, dict)
        self.assertEqual(headers["X-NPI-Timestamp"], str(NOW))
        self.assertEqual(len(str(headers["X-NPI-Signature"])), 64)

    def test_tampered_or_oversized_response_never_becomes_authoritative(self) -> None:
        value = command()
        profile = load_sandbox_profile(
            configuration(),
            "TENANT-SANDBOX",
            PROJECT_ID,
        )
        assert profile is not None
        credential = SandboxCredential(
            "abcdefgh12345678",
            "sandbox-secret-value",
        )
        body = response_body(value, credential).replace(
            b"NPI-SBX-ENG-ITEM-001",
            b"NPI-SBX-ENG-ITEM-999",
        )
        tampered = execute_sandbox_item(
            value,
            profile,
            credential,
            session_factory=lambda: FakeSession(FakeResponse(body)),
            clock=lambda: NOW,
        )
        self.assertFalse(tampered.response_authenticated)
        self.assertFalse(tampered.response_contract_valid)
        self.assertIsNone(tampered.formal_item_code)

        oversized = FakeResponse(b"{}")
        oversized.headers["Content-Length"] = "262145"
        with self.assertRaisesRegex(ValueError, "too large"):
            execute_sandbox_item(
                value,
                profile,
                credential,
                session_factory=lambda: FakeSession(oversized),
                clock=lambda: NOW,
            )


if __name__ == "__main__":
    unittest.main()
