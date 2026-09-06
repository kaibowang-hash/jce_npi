from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
for app in (
    ROOT / "apps/npi_integration",
    ROOT / "apps/npi_erpnext_connector",
):
    if str(app) not in sys.path:
        sys.path.insert(0, str(app))

from npi_erpnext_connector.receiver_security import (  # noqa: E402
    signed_response,
    verify_request,
)
from npi_integration.mbom_publish.adapters import (  # noqa: E402
    classify_mbom_adapter_response,
)
from npi_integration.mbom_publish.connector_runtime import (  # noqa: E402
    MBOM_METHOD_PATH,
    SANDBOX_ADAPTER_PATH,
    SANDBOX_ENABLED_KEY,
    SANDBOX_PROFILES_KEY,
    SandboxCredential,
    execute_sandbox_mbom,
    load_sandbox_credential,
    load_sandbox_profile,
)
from npi_integration.mbom_publish.domain import (  # noqa: E402
    MbomPublishContractError,
    MbomPublishRequestState,
    canonical_hash,
)
from tests.test_erpnext_connector_mbom_contract import command  # noqa: E402


NOW = 1_788_537_600
SECRET = SandboxCredential("ApiKey1234567890", "secret-value-1234567890abcdef")


def profile_mapping() -> dict[str, object]:
    return {
        "profileId": "erpnext-test-mbom-v1",
        "profileVersion": 1,
        "tenantId": "tenant-synthetic",
        "projectGlobalId": "00000000-0000-0000-0000-000000000001",
        "environmentCode": "test",
        "requesterUserIds": ["publisher@example.invalid"],
        "serviceActorUserId": "worker@example.invalid",
        "projectionPolicyId": "mbom-projection-v1",
        "projectionPolicyVersion": 1,
        "projectionPolicyHash": "7" * 64,
        "baseUrl": "https://erpnext.test.example.invalid",
        "allowedHostnames": ["erpnext.test.example.invalid"],
        "secretReference": "secrets/erpnext-test-mbom-v1",
        "connectTimeoutSeconds": 3,
        "readTimeoutSeconds": 20,
    }


def configuration() -> dict[str, object]:
    return {
        SANDBOX_ENABLED_KEY: True,
        SANDBOX_PROFILES_KEY: [profile_mapping()],
    }


def response_body(*, partial: bool = True) -> bytes:
    value = command()
    nodes = []
    for index, node in enumerate(value.nodes):
        success = not partial or index == 0
        node_core = {
            "stableLineKey": node.stable_line_key,
            "assemblySourceKey": node.assembly_source_key,
            "httpStatus": 200 if success else 429,
            "formalBomId": f"BOM-TEST-{index + 1}" if success else None,
            "targetVersion": f"2026-09-05 10:00:0{index}.000001" if success else None,
            "targetSubmissionState": "editable_draft" if success else None,
            "mappingVersion": 1 if success else None,
            "errorCode": None if success else "MBOM_PUBLISH_RATE_LIMITED",
            "exactReplay": False,
        }
        nodes.append({**node_core, "responseHash": canonical_hash(node_core)})
    core = {
        "contractVersion": 1,
        "operation": "publish_released_mbom",
        "requestGlobalId": str(value.request_global_id),
        "attemptGlobalId": str(value.attempt_global_id),
        "attemptNumber": value.attempt_number,
        "targetIdempotencyKeyHash": value.target_idempotency_key_hash,
        "sourceHash": value.source_hash,
        "topologyHash": value.topology_hash,
        "nodeManifestHash": value.node_manifest_hash,
        "nodes": nodes,
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
    ).encode()


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


class ERPNextMbomSandboxAdapterTest(unittest.TestCase):
    def test_profile_is_default_off_exact_and_nonproduction_only(self) -> None:
        project = "00000000-0000-0000-0000-000000000001"
        self.assertIsNone(load_sandbox_profile({}, "tenant-synthetic", project))
        value = load_sandbox_profile(configuration(), "tenant-synthetic", project)
        self.assertEqual(value.adapter_resolver, SANDBOX_ADAPTER_PATH)
        self.assertEqual(value.allowed_operations, ("publish_released_mbom",))
        invalid = profile_mapping()
        invalid["baseUrl"] = "https://erpnext.example.com"
        invalid["allowedHostnames"] = ["erpnext.example.com"]
        with self.assertRaises(MbomPublishContractError):
            load_sandbox_profile(
                {
                    SANDBOX_ENABLED_KEY: True,
                    SANDBOX_PROFILES_KEY: [invalid],
                },
                "tenant-synthetic",
                project,
            )

    def test_credentials_are_closed_and_loaded_only_by_opaque_reference(self) -> None:
        raw = json.dumps(
            {
                "secrets/erpnext-test-mbom-v1": {
                    "apiKey": SECRET.api_key,
                    "apiSecret": SECRET.api_secret,
                }
            }
        )
        self.assertEqual(
            load_sandbox_credential("secrets/erpnext-test-mbom-v1", raw),
            SECRET,
        )
        with self.assertRaises(MbomPublishContractError):
            load_sandbox_credential(
                "secrets/erpnext-test-mbom-v1",
                raw.replace("apiSecret", "password"),
            )

    def test_signed_batch_transport_preserves_partial_node_truth(self) -> None:
        profile = load_sandbox_profile(
            configuration(),
            "tenant-synthetic",
            "00000000-0000-0000-0000-000000000001",
        )
        response = FakeResponse(response_body())
        session = FakeSession(response)
        result = execute_sandbox_mbom(
            command(),
            profile,
            SECRET,
            session_factory=lambda: session,
            clock=lambda: NOW,
        )
        self.assertFalse(session.trust_env)
        self.assertFalse(session.call["allow_redirects"])
        self.assertEqual(
            session.call["endpoint"],
            "https://erpnext.test.example.invalid" + MBOM_METHOD_PATH,
        )
        headers = session.call["headers"]
        verify_request(
            secret=SECRET.signing_secret,
            path=MBOM_METHOD_PATH,
            timestamp=headers["X-NPI-Timestamp"],
            signature=headers["X-NPI-Signature"],
            body=session.call["data"],
            now=NOW,
        )
        classified = classify_mbom_adapter_response(
            profile=profile,
            command=command(),
            response=result,
            observed_at=datetime.fromtimestamp(NOW, tz=timezone.utc),
        )
        self.assertEqual(classified.state, MbomPublishRequestState.PARTIALLY_SUCCEEDED)
        self.assertTrue(result.nodes[0].response_authenticated)
        self.assertEqual(result.nodes[1].http_status, 429)
        self.assertTrue(response.closed)
        self.assertTrue(session.closed)

    def test_tampered_signature_and_oversize_response_fail_closed(self) -> None:
        profile = load_sandbox_profile(
            configuration(),
            "tenant-synthetic",
            "00000000-0000-0000-0000-000000000001",
        )
        tampered = json.loads(response_body())
        tampered["message"]["nodes"][0]["formalBomId"] = "BOM-TAMPERED"
        body = json.dumps(tampered, separators=(",", ":"), sort_keys=True).encode()
        result = execute_sandbox_mbom(
            command(),
            profile,
            SECRET,
            session_factory=lambda: FakeSession(FakeResponse(body)),
            clock=lambda: NOW,
        )
        self.assertTrue(all(not node.response_authenticated for node in result.nodes))
        oversized = FakeResponse(b"{}")
        oversized.headers["Content-Length"] = str(4_194_305)
        with self.assertRaises(MbomPublishContractError):
            execute_sandbox_mbom(
                command(),
                profile,
                SECRET,
                session_factory=lambda: FakeSession(oversized),
                clock=lambda: NOW,
            )


if __name__ == "__main__":
    unittest.main()
