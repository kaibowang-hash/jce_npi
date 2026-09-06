from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ERP_APP = ROOT / "apps/npi_erpnext_connector"
if str(ERP_APP) not in sys.path:
    sys.path.insert(0, str(ERP_APP))

from npi_erpnext_connector.item_config import (
    ItemConfigurationError,
    load_item_profile,
    receiver_is_disabled,
)
from npi_erpnext_connector.item_contract import (
    ItemContractError,
    canonical_hash,
    canonical_json,
    decode_item_command,
)
from npi_erpnext_connector.receiver_security import (
    ReceiverAuthenticationError,
    request_signature,
    signed_response,
    verify_request,
    verify_response,
)

PROJECT_ID = "00000000-0000-4000-8000-000000001001"
REQUEST_ID = "00000000-0000-4000-8000-000000001002"
ATTEMPT_ID = "00000000-0000-4000-8000-000000001003"
NODE_ID = "00000000-0000-4000-8000-000000001004"
LINE_ID = "00000000-0000-4000-8000-000000001005"
PATH = "/api/method/npi_erpnext_connector.item_api.publish_item"
SECRET = "api-key-value:api-secret-value"


def command_mapping() -> dict[str, object]:
    item_master = {
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
        "itemMaster": item_master,
        "occurrences": [
            {
                "publishNodeGlobalId": NODE_ID,
                "lineGlobalId": LINE_ID,
                "engineeringItemId": "ENG-ITEM-001",
                **item_master,
                "lineHash": "1" * 64,
                "nodeInputHash": "2" * 64,
            }
        ],
    }
    source_hash = canonical_hash(source_payload)
    stream_hash = canonical_hash(
        {
            "schemaVersion": 1,
            "tenantId": "TENANT-SANDBOX",
            "projectGlobalId": PROJECT_ID,
            "engineeringItemId": "ENG-ITEM-001",
        }
    )
    return {
        "contractVersion": 2,
        "operation": "publish_released_item",
        "requestGlobalId": REQUEST_ID,
        "attemptGlobalId": ATTEMPT_ID,
        "attemptNumber": 1,
        "targetIdempotencyKeyHash": "3" * 64,
        "sourceHash": source_hash,
        "actorUserId": "publisher@example.invalid",
        "source": {
            **source_payload,
            "streamKeyHash": stream_hash,
            "sourceHash": source_hash,
        },
        "intent": "create_item",
        "expectedMappingVersion": 0,
        "expectedTargetVersion": None,
    }


def command_body() -> bytes:
    return canonical_json(command_mapping()).encode()


class ERPNextConnectorItemContractTest(unittest.TestCase):
    def test_accepts_exact_launchflow_item_command(self) -> None:
        command = decode_item_command(command_body())
        self.assertEqual(command.request_global_id, REQUEST_ID)
        self.assertEqual(command.engineering_item_id, "ENG-ITEM-001")
        self.assertEqual(command.actor_user_id, "publisher@example.invalid")
        self.assertEqual(command.attributes, (("material", "PA66"),))
        self.assertEqual(command.intent, "create_item")

    def test_rejects_duplicate_extra_and_hash_drift(self) -> None:
        duplicate = command_body().replace(
            b'"contractVersion":2',
            b'"contractVersion":2,"contractVersion":2',
            1,
        )
        with self.assertRaisesRegex(ItemContractError, "duplicate"):
            decode_item_command(duplicate)
        extra = command_mapping()
        extra["doctype"] = "Item"
        with self.assertRaisesRegex(ItemContractError, "shape"):
            decode_item_command(canonical_json(extra).encode())
        drifted = command_mapping()
        drifted["sourceHash"] = "f" * 64
        with self.assertRaisesRegex(ItemContractError, "source hash"):
            decode_item_command(canonical_json(drifted).encode())

    def test_rejects_missing_or_noncanonical_business_actor(self) -> None:
        missing = command_mapping()
        missing.pop("actorUserId")
        with self.assertRaisesRegex(ItemContractError, "shape"):
            decode_item_command(canonical_json(missing).encode())
        uppercase = command_mapping()
        uppercase["actorUserId"] = "Publisher@example.invalid"
        with self.assertRaisesRegex(ItemContractError, "actorUserId"):
            decode_item_command(canonical_json(uppercase).encode())

    def test_semantic_idempotency_ignores_only_attempt_identity(self) -> None:
        first = decode_item_command(command_body())
        retried = command_mapping()
        retried["attemptGlobalId"] = "00000000-0000-4000-8000-000000001099"
        retried["attemptNumber"] = 2
        second = decode_item_command(canonical_json(retried).encode())
        self.assertEqual(first.semantic_request_hash, second.semantic_request_hash)

    def test_receiver_profile_is_explicit_and_accounts_for_every_attribute(
        self,
    ) -> None:
        self.assertTrue(receiver_is_disabled({}))
        self.assertTrue(receiver_is_disabled({"npi_erp_connector_disabled": 0}))
        configuration = {
            "npi_erp_connector_disabled": False,
            "npi_erp_connector_item_profile": {
                "itemGroup": "NPI Sandbox Items",
                "erpNamingSeries": "STO-ITEM-.YYYY.-",
                "uomMap": {"Nos": "Nos"},
                "attributeFieldMap": {"material": "custom_npi_material"},
                "ignoredAttributes": [],
            },
        }
        profile = load_item_profile(configuration)
        self.assertEqual(profile.erp_naming_series, "STO-ITEM-.YYYY.-")
        self.assertEqual(profile.target_uom("Nos"), "Nos")
        self.assertEqual(
            profile.attribute_values((("material", "PA66"),)),
            {"custom_npi_material": "PA66"},
        )
        legacy = dict(configuration)
        legacy_profile = dict(configuration["npi_erp_connector_item_profile"])
        legacy_profile["itemCodePrefix"] = "NPI-SBX-"
        legacy_profile.pop("erpNamingSeries")
        legacy["npi_erp_connector_item_profile"] = legacy_profile
        with self.assertRaisesRegex(ItemConfigurationError, "shape"):
            load_item_profile(legacy)
        with self.assertRaisesRegex(ItemConfigurationError, "approved mapping"):
            profile.attribute_values((("material", "PA66"), ("grade", "30GF")))

    def test_request_and_response_signatures_bind_time_path_and_body(self) -> None:
        body = command_body()
        timestamp = "1788537600"
        signature = request_signature(SECRET, PATH, timestamp, body)
        verify_request(
            secret=SECRET,
            path=PATH,
            timestamp=timestamp,
            signature=signature,
            body=body,
            now=1788537600,
        )
        with self.assertRaisesRegex(ReceiverAuthenticationError, "signature"):
            verify_request(
                secret=SECRET,
                path=PATH,
                timestamp=timestamp,
                signature=signature,
                body=body + b" ",
                now=1788537600,
            )
        with self.assertRaisesRegex(ReceiverAuthenticationError, "window"):
            verify_request(
                secret=SECRET,
                path=PATH,
                timestamp=timestamp,
                signature=signature,
                body=body,
                now=1788538001,
            )

        response = signed_response(
            {"requestGlobalId": REQUEST_ID, "responseHash": "4" * 64},
            SECRET,
            now=1788537601,
        )
        verified = verify_response(response, SECRET, now=1788537601)
        self.assertEqual(verified["requestGlobalId"], REQUEST_ID)
        tampered = json.loads(json.dumps(response))
        tampered["responseHash"] = "5" * 64
        with self.assertRaisesRegex(ReceiverAuthenticationError, "signature"):
            verify_response(tampered, SECRET, now=1788537601)


if __name__ == "__main__":
    unittest.main()
