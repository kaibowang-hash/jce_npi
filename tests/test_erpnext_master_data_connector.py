from __future__ import annotations

import copy
import json
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for app in ("npi_core", "npi_integration", "npi_erpnext_connector"):
    path = str(ROOT / f"apps/{app}")
    if path not in sys.path:
        sys.path.insert(0, path)

from npi_erpnext_connector.master_data_config import load_master_data_profile
from npi_erpnext_connector.master_data_domain import (
    MasterCatalogKind as SenderKind,
    SourceMasterSnapshot,
    build_event,
)
from npi_erpnext_connector.master_data_transport import (
    PermanentMasterDataDeliveryError,
    RetryableMasterDataDeliveryError,
    deliver_master_snapshot,
)
from npi_integration.master_data.domain import (
    MasterDataContractError,
    MasterSnapshotEvent,
)


NOW = datetime(2026, 9, 6, 1, 2, 3, tzinfo=UTC)


def records(kind: SenderKind) -> tuple[dict[str, object], ...]:
    common = {
        "sourceKey": "A-001",
        "displayName": "Alpha",
        "enabled": True,
        "sourceModifiedAt": "2026-09-06T01:00:00Z",
    }
    if kind in {SenderKind.CUSTOMER, SenderKind.SUPPLIER}:
        return ({**common, "groupKey": "Primary"},)
    if kind is SenderKind.ITEM_GROUP:
        return ({**common, "parentKey": "All Item Groups", "isGroup": False},)
    return (
        {
            **common,
            "groupKey": "Products",
            "stockUom": "Nos",
            "isStockItem": True,
        },
    )


class _Response:
    def __init__(self, status: int, payload: object) -> None:
        self.status_code = status
        self.body = json.dumps(payload, separators=(",", ":")).encode()
        self.closed = False

    def iter_content(self, chunk_size: int):
        del chunk_size
        yield self.body

    def close(self) -> None:
        self.closed = True


class _Session:
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def put(self, endpoint: str, **kwargs: object) -> _Response:
        self.calls.append({"endpoint": endpoint, **kwargs})
        return self.response


class ERPNextMasterDataConnectorTest(unittest.TestCase):
    def event(self, kind: SenderKind = SenderKind.ITEM):
        snapshot = SourceMasterSnapshot(kind, NOW, records(kind))
        return build_event(
            snapshot,
            source_version=3,
            issued_at=NOW,
            source_environment="test",
        )

    def test_all_four_erpnext_catalogs_match_the_npi_contract(self) -> None:
        for kind in SenderKind:
            with self.subTest(kind=kind.value):
                event = self.event(kind)
                parsed = MasterSnapshotEvent.from_mapping(event.event)
                self.assertEqual(parsed.kind.value, kind.value)
                self.assertEqual(parsed.source_environment, "test")
                self.assertEqual(parsed.source_version, 3)
                self.assertEqual(len(parsed.records), 1)
                self.assertEqual(parsed.payload_hash, event.payload_hash)
                self.assertEqual(parsed.mapping(), event.event)

    def test_contract_rejects_unknown_fields_wrong_hash_and_unsorted_records(self) -> None:
        event = self.event(SenderKind.ITEM)
        for mutate in (
            lambda value: value.update({"unexpected": True}),
            lambda value: value.update({"payloadHash": "0" * 64}),
            lambda value: value.update({"sourceEnvironment": "production"}),
        ):
            value = copy.deepcopy(dict(event.event))
            mutate(value)
            with self.assertRaises(MasterDataContractError):
                MasterSnapshotEvent.from_mapping(value)
        value = copy.deepcopy(dict(event.event))
        value["records"] = [
            {**value["records"][0], "sourceKey": "B"},
            {**value["records"][0], "sourceKey": "A"},
        ]
        with self.assertRaises(MasterDataContractError):
            MasterSnapshotEvent.from_mapping(value)

    def test_profile_is_explicit_https_and_nonproduction(self) -> None:
        profile = load_master_data_profile(
            {
                "npi_erp_master_data_sender_disabled": False,
                "npi_erp_master_data_target_base_url": "https://launchflow.example.invalid",
                "npi_erp_master_data_source_environment": "test",
            }
        )
        self.assertEqual(
            profile.endpoint,
            "https://launchflow.example.invalid/api/npi/v1/integration/erpnext/master-data",
        )
        for invalid in ("production", "prod", "TEST"):
            with self.assertRaises(ValueError):
                load_master_data_profile(
                    {
                        "npi_erp_master_data_sender_disabled": False,
                        "npi_erp_master_data_target_base_url": "https://launchflow.example.invalid",
                        "npi_erp_master_data_source_environment": invalid,
                    }
                )

    def test_transport_binds_exact_authenticated_receipt(self) -> None:
        event = self.event()
        profile = load_master_data_profile(
            {
                "npi_erp_master_data_sender_disabled": False,
                "npi_erp_master_data_target_base_url": "https://launchflow.example.invalid",
                "npi_erp_master_data_source_environment": "test",
            }
        )
        response = _Response(
            200,
            {
                "snapshotId": "00000000-0000-4000-8000-000000000101",
                "catalogKind": "item",
                "sourceVersion": 3,
                "recordCount": 1,
                "payloadHash": event.payload_hash,
                "exactReplay": False,
                "requestId": str(event.request_id),
                "traceId": event.trace_id,
            },
        )
        session = _Session(response)
        receipt = deliver_master_snapshot(
            profile,
            event,
            session=session,
            environment={"NPI_ERP_AUTHORIZATION_TOKEN": "token key:secret"},
        )
        self.assertEqual(receipt.payload_hash, event.payload_hash)
        self.assertTrue(response.closed)
        self.assertEqual(session.calls[0]["allow_redirects"], False)
        self.assertEqual(session.calls[0]["headers"]["Authorization"], "token key:secret")

    def test_transport_classifies_retryable_and_permanent_failures(self) -> None:
        event = self.event()
        profile = load_master_data_profile(
            {
                "npi_erp_master_data_sender_disabled": False,
                "npi_erp_master_data_target_base_url": "https://launchflow.example.invalid",
                "npi_erp_master_data_source_environment": "test",
            }
        )
        with self.assertRaises(RetryableMasterDataDeliveryError):
            deliver_master_snapshot(
                profile,
                event,
                session=_Session(_Response(503, {"code": "MASTER_UNAVAILABLE"})),
                environment={"NPI_ERP_AUTHORIZATION_TOKEN": "token key:secret"},
            )
        with self.assertRaises(PermanentMasterDataDeliveryError):
            deliver_master_snapshot(
                profile,
                event,
                session=_Session(_Response(422, {"code": "MASTER_INVALID"})),
                environment={"NPI_ERP_AUTHORIZATION_TOKEN": "token key:secret"},
            )


if __name__ == "__main__":
    unittest.main()
