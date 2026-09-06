from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for app in ("npi_core", "npi_integration", "npi_erpnext_connector"):
    path = str(ROOT / f"apps/{app}")
    if path not in sys.path:
        sys.path.insert(0, path)

from npi_erpnext_connector.receiver_security import signed_response
from npi_erpnext_connector.trial_summary_config import receiver_is_disabled
from npi_erpnext_connector.trial_summary_contract import (
    OPERATION,
    TrialSummaryContractError,
    canonical_hash,
    canonical_json,
    decode_reconcile_command,
    decode_trial_summary_command,
)
from npi_integration.trial_summary_publish.domain import (
    PublishCommand,
    ReconcileCommand,
    delivery_source,
)
from npi_integration.trial_summary_publish.config import (
    TrialSummaryDeliveryError,
    load_profile,
)
from npi_integration.trial_summary_publish.connector_runtime import (
    SandboxCredential,
    publish,
)

from tests.test_phase7_released_trial_summary_domain import summary


class _Document:
    def __init__(self) -> None:
        value = summary()
        self.global_id = str(value.global_id)
        self.summary_snapshot = canonical_json(
            value.snapshot_payload() | {"snapshotHash": value.snapshot_hash}
        )


def command_mapping() -> dict[str, object]:
    source = delivery_source(_Document())
    return PublishCommand(
        "00000000-0000-4000-8000-000000000101",
        "00000000-0000-4000-8000-000000000102",
        1,
        source.target_idempotency_key_hash,
        source.source_hash,
        source.actor_user_id,
        source.source,
    ).payload()


class _Response:
    def __init__(self, status: int, value: object) -> None:
        self.status_code = status
        self.body = json.dumps({"message": value}, separators=(",", ":")).encode()
        self.headers = {
            "Content-Type": "application/json",
            "Content-Length": str(len(self.body)),
        }
        self.closed = False

    def iter_content(self, chunk_size: int):
        del chunk_size
        yield self.body

    def close(self) -> None:
        self.closed = True


class _Session:
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.trust_env = True
        self.request: dict[str, object] | None = None
        self.closed = False

    def post(self, endpoint: str, **values: object) -> _Response:
        self.request = {"endpoint": endpoint, **values}
        return self.response

    def close(self) -> None:
        self.closed = True


class ReleasedTrialSummaryERPProjectionContractTest(unittest.TestCase):
    def test_npi_command_is_accepted_by_exact_erpnext_contract(self) -> None:
        command = decode_trial_summary_command(
            canonical_json(command_mapping()).encode("utf-8")
        )
        self.assertEqual(command.projection_purpose, "erpnext_read_only_engineering_evidence")
        self.assertFalse(command.formal_mp_acceptance)
        self.assertEqual(command.summary_version, 1)
        self.assertEqual(command.conclusion_state, "approved")
        self.assertEqual(command.conclusion_code, "pass")
        self.assertEqual(
            {fact.fact_type for fact in command.facts},
            {
                "input_change",
                "actual_parameter",
                "sample",
                "cavity_result",
                "trial_defect",
                "comparison",
                "controlled_reference",
            },
        )

    def test_contract_is_closed_hash_bound_and_sensitive_safe(self) -> None:
        extra = command_mapping()
        extra["doctype"] = "Quality Inspection"
        with self.assertRaisesRegex(TrialSummaryContractError, "shape"):
            decode_trial_summary_command(canonical_json(extra).encode())

        source_drift = command_mapping()
        source_drift["source"]["conclusionCode"] = "cancelled"
        with self.assertRaisesRegex(TrialSummaryContractError, "identity|hash"):
            decode_trial_summary_command(canonical_json(source_drift).encode())

        idempotency_drift = command_mapping()
        idempotency_drift["targetIdempotencyKeyHash"] = "f" * 64
        with self.assertRaisesRegex(TrialSummaryContractError, "idempotency"):
            decode_trial_summary_command(canonical_json(idempotency_drift).encode())

        sensitive = command_mapping()
        sensitive["source"]["presentationProjection"]["facts"]["inputChanges"][0][
            "value"
        ] = "https://production.example.invalid/private"
        projection = sensitive["source"]["presentationProjection"]
        sensitive["source"]["presentationProjectionHash"] = canonical_hash(projection)
        sensitive["sourceHash"] = canonical_hash(sensitive["source"])
        with self.assertRaisesRegex(TrialSummaryContractError, "forbidden"):
            decode_trial_summary_command(canonical_json(sensitive).encode())

    def test_attempt_identity_is_the_only_semantic_retry_difference(self) -> None:
        first = decode_trial_summary_command(canonical_json(command_mapping()).encode())
        retry = command_mapping()
        retry["attemptGlobalId"] = "00000000-0000-4000-8000-000000000103"
        retry["attemptNumber"] = 2
        second = decode_trial_summary_command(canonical_json(retry).encode())
        self.assertEqual(first.semantic_request_hash, second.semantic_request_hash)

    def test_reconciliation_contract_is_fixed_and_read_only(self) -> None:
        publish = command_mapping()
        mapping = ReconcileCommand(
            publish["requestGlobalId"],
            "00000000-0000-4000-8000-000000000104",
            publish["targetIdempotencyKeyHash"],
            publish["sourceHash"],
            publish["source"]["summaryRevisionGlobalId"],
            7,
        ).payload()
        command = decode_reconcile_command(canonical_json(mapping).encode())
        self.assertEqual(command.target_idempotency_key_hash, publish["targetIdempotencyKeyHash"])
        drifted = copy.deepcopy(mapping)
        drifted["operation"] = OPERATION
        with self.assertRaisesRegex(TrialSummaryContractError, "unsupported"):
            decode_reconcile_command(canonical_json(drifted).encode())

    def test_receiver_is_default_closed(self) -> None:
        self.assertTrue(receiver_is_disabled({}))
        self.assertTrue(receiver_is_disabled({"npi_erp_trial_summary_receiver_disabled": 0}))
        self.assertFalse(
            receiver_is_disabled({"npi_erp_trial_summary_receiver_disabled": False})
        )

    def test_sandbox_profile_and_signed_receipt_are_exact(self) -> None:
        raw = command_mapping()
        command = PublishCommand(
            raw["requestGlobalId"],
            raw["attemptGlobalId"],
            raw["attemptNumber"],
            raw["targetIdempotencyKeyHash"],
            raw["sourceHash"],
            raw["actorUserId"],
            raw["source"],
        )
        profile_values = {
            "profileId": "erp-trial-summary-sandbox",
            "profileVersion": 1,
            "tenantId": raw["source"]["tenantId"],
            "projectGlobalId": raw["source"]["projectGlobalId"],
            "environmentCode": "sandbox",
            "serviceActorUserId": "trial-summary-service@example.invalid",
            "baseUrl": "https://erp-sandbox.example.test",
            "allowedHostnames": ["erp-sandbox.example.test"],
            "secretReference": "secret/trial-summary-sandbox",
            "connectTimeoutSeconds": 3,
            "readTimeoutSeconds": 10,
        }
        profile = load_profile(
            {
                "npi_trial_summary_erp_sandbox_enabled": True,
                "npi_trial_summary_erp_sandbox_profiles": [profile_values],
            },
            raw["source"]["tenantId"],
            raw["source"]["projectGlobalId"],
        )
        self.assertIsNotNone(profile)
        secret = "api-key-value:api-secret-value"
        core = {
            "contractVersion": 1,
            "operation": "publish_released_trial_summary",
            "requestGlobalId": raw["requestGlobalId"],
            "attemptGlobalId": raw["attemptGlobalId"],
            "attemptNumber": 1,
            "targetIdempotencyKeyHash": raw["targetIdempotencyKeyHash"],
            "sourceHash": raw["sourceHash"],
            "httpStatus": 200,
            "projectionId": raw["source"]["summaryRevisionGlobalId"],
            "factCount": 7,
            "exactReplay": False,
            "errorCode": None,
        }
        response = _Response(
            200,
            signed_response(
                {**core, "responseHash": canonical_hash(core)},
                secret,
                now=1788566400,
            ),
        )
        session = _Session(response)
        observation = publish(
            command,
            profile,
            SandboxCredential("api-key-value", "api-secret-value"),
            session_factory=lambda: session,
            clock=lambda: 1788566400,
        )
        self.assertTrue(observation.authenticated)
        self.assertTrue(observation.contract_valid)
        self.assertEqual(observation.projection_id, raw["source"]["summaryRevisionGlobalId"])
        self.assertFalse(session.trust_env)
        self.assertFalse(session.request["allow_redirects"])
        self.assertEqual(
            session.request["endpoint"],
            "https://erp-sandbox.example.test/api/method/"
            "npi_erpnext_connector.trial_summary_api.publish_trial_summary",
        )
        self.assertTrue(response.closed)
        self.assertTrue(session.closed)

        mismatched_count = copy.deepcopy(core)
        mismatched_count["factCount"] = 8
        mismatched_response = _Response(
            200,
            signed_response(
                {
                    **mismatched_count,
                    "responseHash": canonical_hash(mismatched_count),
                },
                secret,
                now=1788566400,
            ),
        )
        mismatch = publish(
            command,
            profile,
            SandboxCredential("api-key-value", "api-secret-value"),
            session_factory=lambda: _Session(mismatched_response),
            clock=lambda: 1788566400,
        )
        self.assertFalse(mismatch.contract_valid)

        production = dict(profile_values)
        production["environmentCode"] = "production"
        production["baseUrl"] = "https://erp-production.example.com"
        production["allowedHostnames"] = ["erp-production.example.com"]
        with self.assertRaises(TrialSummaryDeliveryError):
            load_profile(
                {
                    "npi_trial_summary_erp_sandbox_enabled": True,
                    "npi_trial_summary_erp_sandbox_profiles": [production],
                },
                raw["source"]["tenantId"],
                raw["source"]["projectGlobalId"],
            )


if __name__ == "__main__":
    unittest.main()
