from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
for app in (
    ROOT / "apps/npi_integration",
    ROOT / "apps/npi_erpnext_connector",
):
    if str(app) not in sys.path:
        sys.path.insert(0, str(app))

from npi_erpnext_connector.mbom_config import (  # noqa: E402
    MbomConfigurationError,
    load_mbom_profile,
)
from npi_erpnext_connector.mbom_contract import (  # noqa: E402
    MbomContractError,
    decode_mbom_command,
)
from npi_integration.mbom_publish.adapters import (  # noqa: E402
    MbomAdapterCommand,
    MbomAdapterNodeCommand,
)
from npi_integration.mbom_publish.domain import (  # noqa: E402
    MbomTargetMode,
    canonical_hash,
    create_mbom_publish_request,
)

from tests.test_phase8_mbom_publish_domain import (  # noqa: E402
    NOW,
    advanced_readiness,
    expectations,
    profile,
    source,
    uid,
)


def command() -> MbomAdapterCommand:
    source_value = source()
    readiness = tuple(
        advanced_readiness(source_value, index + 1, engineering_item_id)
        for index, engineering_item_id in enumerate(source_value.engineering_item_ids)
    )
    expected = expectations(source_value)
    request = create_mbom_publish_request(
        source=source_value,
        item_readiness=readiness,
        mbom_expectations=expected,
        profile=profile(MbomTargetMode.SANDBOX),
        actor_user_id="publisher@example.invalid",
        service_actor_user_id="worker@example.invalid",
        request_id=uid(90),
        trace_id="mbom-contract-test",
        idempotency_key_hash="9" * 64,
        global_id=uid(91),
        created_at=NOW,
    )
    readiness_by_item = {value.engineering_item_id: value for value in readiness}
    expectations_by_key = {value.stable_line_key: value for value in expected}
    roles = source_value.roles
    nodes = tuple(
        MbomAdapterNodeCommand.from_expectation(
            expectations_by_key[line.stable_line_key],
            node_global_id=UUID(int=100 + index),
            node_snapshot={
                "line": line.canonical_mapping(roles[line.stable_line_key]),
                "itemReadiness": readiness_by_item[
                    line.engineering_item_id
                ].canonical_mapping(),
                "mbomExpectation": expectations_by_key[
                    line.stable_line_key
                ].canonical_mapping(),
            },
        )
        for index, line in enumerate(source_value.lines)
        if line.stable_line_key in expectations_by_key
    )
    manifest = [
        {
            "globalId": str(node.node_global_id),
            "stableLineKey": node.stable_line_key,
            "nodeSnapshotHash": node.node_snapshot_hash,
        }
        for node in nodes
    ]
    return MbomAdapterCommand(
        request.global_id,
        uid(92),
        1,
        request.target_idempotency_key_hash,
        request.source.source_hash,
        request.source.topology_hash,
        request.item_mapping_set_hash,
        request.mbom_mapping_set_hash,
        canonical_hash({"requestGlobalId": str(request.global_id), "nodes": manifest}),
        request.payload(),
        nodes,
    )


def body(value: MbomAdapterCommand | None = None) -> bytes:
    return json.dumps(
        (value or command()).snapshot(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


class ERPNextConnectorMbomContractTest(unittest.TestCase):
    def test_receiver_profile_supports_only_the_exact_jce_bom_setting(self) -> None:
        configuration = {
            "npi_erp_connector_mbom_disabled": False,
            "npi_erp_connector_mbom_profile": {
                "company": "JCE",
                "customTemporaryBomValue": "No",
            },
        }
        profile_value = load_mbom_profile(configuration)
        self.assertEqual(profile_value.company, "JCE")
        self.assertEqual(profile_value.custom_temporary_bom_value, "No")
        configuration["npi_erp_connector_mbom_profile"]["customTemporaryBomValue"] = (
            "Maybe"
        )
        with self.assertRaises(MbomConfigurationError):
            load_mbom_profile(configuration)
        configuration["npi_erp_connector_mbom_profile"] = {
            "company": "JCE",
            "customFieldValues": {"anything": "anything"},
        }
        with self.assertRaises(MbomConfigurationError):
            load_mbom_profile(configuration)

    def test_exact_launchflow_command_decodes_to_two_material_boms(self) -> None:
        decoded = decode_mbom_command(body())
        self.assertEqual(decoded.request_global_id, str(uid(91)))
        self.assertEqual(decoded.actor_user_id, "publisher@example.invalid")
        self.assertEqual(
            tuple(node.stable_line_key for node in decoded.nodes),
            ("ROOT", "SUB"),
        )
        self.assertEqual(
            tuple(
                component.stable_line_key for component in decoded.nodes[0].components
            ),
            ("LEAF-B", "SUB"),
        )
        self.assertEqual(
            tuple(
                component.stable_line_key for component in decoded.nodes[1].components
            ),
            ("LEAF-A",),
        )

    def test_business_actor_must_be_a_canonical_email(self) -> None:
        raw = command().snapshot()
        raw["request"]["actorUserId"] = "Publisher@example.invalid"
        with self.assertRaisesRegex(MbomContractError, "actorUserId"):
            decode_mbom_command(
                json.dumps(raw, separators=(",", ":"), sort_keys=True).encode()
            )

    def test_attempt_identity_does_not_change_semantic_request_hash(self) -> None:
        first = command()
        second = MbomAdapterCommand(
            first.request_global_id,
            uid(93),
            2,
            first.target_idempotency_key_hash,
            first.source_hash,
            first.topology_hash,
            first.item_mapping_set_hash,
            first.mbom_mapping_set_hash,
            first.node_manifest_hash,
            first.request_snapshot,
            first.nodes,
        )
        self.assertEqual(
            decode_mbom_command(body(first)).semantic_request_hash,
            decode_mbom_command(body(second)).semantic_request_hash,
        )

    def test_hash_topology_mapping_and_node_tampering_fail_closed(self) -> None:
        cases = []
        for mutation in ("source", "readiness", "expectation", "node"):
            raw = command().snapshot()
            if mutation == "source":
                raw["request"]["source"]["tenantId"] = "other-tenant"
            elif mutation == "readiness":
                raw["request"]["itemReadiness"][0]["mappingVersion"] += 1
            elif mutation == "expectation":
                raw["request"]["mbomExpectations"][0]["assemblySourceKey"] = "0" * 64
            else:
                raw["nodes"][0]["line"]["quantity"] = "9"
            cases.append(raw)
        for raw in cases:
            with self.subTest(), self.assertRaises(MbomContractError):
                decode_mbom_command(
                    json.dumps(raw, separators=(",", ":"), sort_keys=True).encode()
                )

    def test_duplicate_keys_oversize_and_non_sandbox_are_rejected(self) -> None:
        with self.assertRaises(MbomContractError):
            decode_mbom_command(b'{"contractVersion":1,"contractVersion":1}')
        with self.assertRaises(MbomContractError):
            decode_mbom_command(b"x" * 4_194_305)
        raw = command().snapshot()
        raw["request"]["profile"]["targetMode"] = "synthetic"
        with self.assertRaises(MbomContractError):
            decode_mbom_command(
                json.dumps(raw, separators=(",", ":"), sort_keys=True).encode()
            )


if __name__ == "__main__":
    unittest.main()
