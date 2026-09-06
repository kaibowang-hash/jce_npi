from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for app in (
    ROOT / "apps/npi_integration",
    ROOT / "apps/npi_erpnext_connector",
):
    if str(app) not in sys.path:
        sys.path.insert(0, str(app))

from npi_erpnext_connector.receiver_security import (
    signed_response,
    verify_request,
)
from npi_integration.tool_asset_request.adapters import (
    classify_tool_asset_adapter_response,
)
from npi_integration.tool_asset_request.connector_runtime import (
    SANDBOX_ADAPTER_PATH,
    SANDBOX_ENABLED_KEY,
    SANDBOX_PROFILES_KEY,
    TOOL_ASSET_METHOD_PATH,
    SandboxCredential,
    execute_sandbox_tool_asset,
    load_sandbox_credential,
    load_sandbox_profile,
)
from npi_integration.tool_asset_request.execution_domain import (
    TOOL_ASSET_OWNED_FIELDS,
    ToolAssetExecutionContractError,
    ToolAssetExecutionRequestState,
    canonical_hash,
)

from tests.test_erpnext_connector_tool_asset_contract import command
from tests.test_phase8_tool_asset_adapters import (
    NOW as OBSERVED_AT,
)

NOW = 1_788_537_600
SECRET = SandboxCredential("ApiKey1234567890", "secret-value-1234567890abcdef")


def profile_mapping() -> dict[str, object]:
    return {
        "profileId": "erpnext-test-tool-asset-v1",
        "profileVersion": 1,
        "tenantId": "tenant-synthetic",
        "projectGlobalId": "00000000-0000-0000-0000-000000000001",
        "environmentCode": "test",
        "requesterUserIds": ["engineer@example.invalid"],
        "serviceActorUserId": "worker@example.invalid",
        "projectionPolicyId": "tool-asset-projection-v1",
        "projectionPolicyVersion": 1,
        "projectionPolicyHash": "6" * 64,
        "allowedOperations": ["create_tool_asset"],
        "baseUrl": "https://erpnext.test.example.invalid",
        "allowedHostnames": ["erpnext.test.example.invalid"],
        "secretReference": "secrets/erpnext-test-tool-asset-v1",
        "connectTimeoutSeconds": 3,
        "readTimeoutSeconds": 20,
    }


def configuration() -> dict[str, object]:
    return {
        SANDBOX_ENABLED_KEY: True,
        SANDBOX_PROFILES_KEY: [profile_mapping()],
    }


def response_body() -> bytes:
    value = command()
    fields = []
    for code in TOOL_ASSET_OWNED_FIELDS:
        core = {
            "fieldCode": code,
            "httpStatus": 200,
            "errorCode": None,
            "exactReplay": False,
        }
        fields.append({**core, "responseHash": canonical_hash(core)})
    core = {
        "contractVersion": 1,
        "operation": value.operation.value,
        "requestGlobalId": str(value.request_global_id),
        "attemptGlobalId": str(value.attempt_global_id),
        "attemptNumber": value.attempt_number,
        "targetIdempotencyKeyHash": value.target_idempotency_key_hash,
        "sourceHash": value.source_hash,
        "httpStatus": 200,
        "formalAssetId": "ACC-ASS-2026-00001",
        "targetVersion": "2026-09-05 10:00:00.000001",
        "mappingVersion": 1,
        "errorCode": None,
        "exactReplay": False,
        "fields": fields,
    }
    message = signed_response(
        {**core, "responseHash": canonical_hash(core)},
        SECRET.signing_secret,
        now=NOW,
    )
    return json.dumps(
        {"message": message},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


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
        self.closed = False
        self.call: dict[str, object] | None = None

    def post(self, endpoint: str, **kwargs: object) -> FakeResponse:
        self.call = {"endpoint": endpoint, **kwargs}
        return self.response

    def close(self) -> None:
        self.closed = True


class ERPNextToolAssetSandboxAdapterTest(unittest.TestCase):
    def test_profile_is_default_off_nonproduction_and_operation_specific(self) -> None:
        project = "00000000-0000-0000-0000-000000000001"
        self.assertIsNone(load_sandbox_profile({}, "tenant-synthetic", project))
        profile = load_sandbox_profile(configuration(), "tenant-synthetic", project)
        self.assertEqual(profile.adapter_resolver, SANDBOX_ADAPTER_PATH)
        self.assertEqual(profile.allowed_operations, ("create_tool_asset",))
        invalid = profile_mapping()
        invalid["baseUrl"] = "https://erpnext.example.com"
        invalid["allowedHostnames"] = ["erpnext.example.com"]
        with self.assertRaises(ToolAssetExecutionContractError):
            load_sandbox_profile(
                {
                    SANDBOX_ENABLED_KEY: True,
                    SANDBOX_PROFILES_KEY: [invalid],
                },
                "tenant-synthetic",
                project,
            )

    def test_credentials_are_opaque_exact_and_closed(self) -> None:
        serialized = json.dumps(
            {
                "secrets/erpnext-test-tool-asset-v1": {
                    "apiKey": SECRET.api_key,
                    "apiSecret": SECRET.api_secret,
                }
            }
        )
        self.assertEqual(
            load_sandbox_credential(
                "secrets/erpnext-test-tool-asset-v1",
                serialized,
            ),
            SECRET,
        )
        with self.assertRaises(ToolAssetExecutionContractError):
            load_sandbox_credential(
                "secrets/erpnext-test-tool-asset-v1",
                serialized.replace("apiSecret", "password"),
            )

    def test_signed_transport_produces_authoritative_asset_result(self) -> None:
        profile = load_sandbox_profile(
            configuration(),
            "tenant-synthetic",
            "00000000-0000-0000-0000-000000000001",
        )
        assert profile is not None
        remote = FakeResponse(response_body())
        session = FakeSession(remote)
        value = command()
        response = execute_sandbox_tool_asset(
            value,
            profile,
            SECRET,
            session_factory=lambda: session,
            clock=lambda: NOW,
        )
        assert session.call is not None
        self.assertFalse(session.trust_env)
        self.assertFalse(session.call["allow_redirects"])
        self.assertEqual(
            session.call["endpoint"],
            "https://erpnext.test.example.invalid" + TOOL_ASSET_METHOD_PATH,
        )
        headers = session.call["headers"]
        verify_request(
            secret=SECRET.signing_secret,
            path=TOOL_ASSET_METHOD_PATH,
            timestamp=headers["X-NPI-Timestamp"],
            signature=headers["X-NPI-Signature"],
            body=session.call["data"],
            now=NOW,
        )
        classified = classify_tool_asset_adapter_response(
            profile=profile,
            command=value,
            response=response,
            observed_at=OBSERVED_AT,
        )
        self.assertEqual(classified.state, ToolAssetExecutionRequestState.SUCCEEDED)
        self.assertEqual(classified.formal_asset_id, "ACC-ASS-2026-00001")
        self.assertTrue(remote.closed)
        self.assertTrue(session.closed)

    def test_tampered_or_oversized_response_never_becomes_authoritative(self) -> None:
        profile = load_sandbox_profile(
            configuration(),
            "tenant-synthetic",
            "00000000-0000-0000-0000-000000000001",
        )
        assert profile is not None
        tampered = json.loads(response_body())
        tampered["message"]["formalAssetId"] = "ACC-ASS-TAMPERED"
        response = execute_sandbox_tool_asset(
            command(),
            profile,
            SECRET,
            session_factory=lambda: FakeSession(
                FakeResponse(json.dumps(tampered).encode("utf-8"))
            ),
            clock=lambda: NOW,
        )
        classified = classify_tool_asset_adapter_response(
            profile=profile,
            command=command(),
            response=response,
            observed_at=OBSERVED_AT,
        )
        self.assertNotEqual(classified.state, ToolAssetExecutionRequestState.SUCCEEDED)
        self.assertIsNone(classified.formal_asset_id)

        oversized = FakeResponse(b"{}")
        oversized.headers["Content-Length"] = str(1_048_577)
        with self.assertRaises(ToolAssetExecutionContractError):
            execute_sandbox_tool_asset(
                command(),
                profile,
                SECRET,
                session_factory=lambda: FakeSession(oversized),
                clock=lambda: NOW,
            )


if __name__ == "__main__":
    unittest.main()
