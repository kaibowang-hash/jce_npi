from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ERP_APP = ROOT / "apps/npi_erpnext_connector"
INTEGRATION_APP = ROOT / "apps/npi_integration"
for app in (ERP_APP, INTEGRATION_APP):
    if str(app) not in sys.path:
        sys.path.insert(0, str(app))

from npi_erpnext_connector.engineering_change_contract import (  # noqa: E402
    EngineeringChangeContractError,
    decode_summary_command,
)
from tests.test_erpnext_engineering_change_sandbox_adapter import (  # noqa: E402
    command,
)


def raw_command() -> dict[str, object]:
    value = command()
    return {
        "contractVersion": 1,
        "operation": "record_change_implementation_summary",
        "requestGlobalId": str(value.request_global_id),
        "attemptGlobalId": str(value.attempt_global_id),
        "attemptNumber": value.attempt_number,
        "targetIdempotencyKeyHash": value.target_idempotency_key_hash,
        "sourceHash": value.source_hash,
        "actorUserId": value.payload["actor_user_id"],
        "source": dict(value.payload),
    }


class ERPNextConnectorEngineeringChangeContractTest(unittest.TestCase):
    def test_exact_actor_bound_summary_round_trips(self) -> None:
        raw = json.dumps(raw_command(), separators=(",", ":"), sort_keys=True).encode()
        value = decode_summary_command(raw)
        self.assertEqual(value.actor_user_id, "publisher@example.invalid")
        self.assertEqual(
            value.formal_change["documentName"],
            "ECR-2026-00001",
        )
        self.assertEqual(value.revision_number, 2)

    def test_unknown_fields_actor_drift_hash_drift_and_duplicate_keys_fail(self) -> None:
        mutations = []
        unknown = raw_command()
        unknown["targetMethod"] = "frappe.client.insert"
        mutations.append(unknown)
        actor = raw_command()
        actor["actorUserId"] = "other@example.invalid"
        mutations.append(actor)
        source_hash = raw_command()
        source_hash["source"]["closure_evidence_hash"] = "0" * 64
        mutations.append(source_hash)
        for value in mutations:
            with self.subTest(keys=set(value)), self.assertRaises(
                EngineeringChangeContractError
            ):
                decode_summary_command(json.dumps(value).encode())
        with self.assertRaises(EngineeringChangeContractError):
            decode_summary_command(b'{"operation":"one","operation":"two"}')


if __name__ == "__main__":
    unittest.main()
