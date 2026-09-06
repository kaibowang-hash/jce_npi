from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for app in (
    ROOT / "apps/npi_integration",
    ROOT / "apps/npi_erpnext_connector",
):
    if str(app) not in sys.path:
        sys.path.insert(0, str(app))

from npi_erpnext_connector.item_contract import canonical_json
from npi_erpnext_connector.tool_asset_config import (
    ToolAssetConfigurationError,
    load_tool_asset_profile,
    operation_is_disabled,
)
from npi_erpnext_connector.tool_asset_contract import (
    ToolAssetContractError,
    decode_tool_asset_command,
)
from npi_integration.tool_asset_request.adapters import (
    ToolAssetAdapterCommand,
)
from npi_integration.tool_asset_request.execution_domain import (
    ToolAssetApprovalState,
    ToolAssetBusinessApprovalReference,
    ToolAssetExecutionOperation,
    ToolAssetExecutionRequest,
    ToolAssetExecutionRequestState,
    ToolAssetExecutionTargetMode,
    ToolAssetMappingExpectation,
)

from tests.test_phase8_tool_asset_domain import (
    NOW,
    profile,
    source,
    uid,
)


def command(
    operation: ToolAssetExecutionOperation = ToolAssetExecutionOperation.CREATE,
) -> ToolAssetAdapterCommand:
    source_value = source()
    expectation = (
        ToolAssetMappingExpectation(
            operation,
            source_value.source_stream_key_hash,
            0,
        )
        if operation is ToolAssetExecutionOperation.CREATE
        else ToolAssetMappingExpectation(
            operation,
            source_value.source_stream_key_hash,
            1,
            "ASSET-TEST-1",
            "2026-09-05 10:00:00.000001",
            "8" * 64,
        )
    )
    approval = ToolAssetBusinessApprovalReference(
        ToolAssetApprovalState.VERIFIED,
        "tool-asset-approval-v1",
        1,
        "8" * 64,
        "tool-asset-approval-evidence",
        "9" * 64,
    )
    request = ToolAssetExecutionRequest(
        uid(20),
        source_value,
        approval,
        expectation,
        profile(ToolAssetExecutionTargetMode.SANDBOX),
        ToolAssetExecutionRequestState.QUEUED,
        "engineer@example.invalid",
        uid(21),
        "trace-tool-asset-001",
        "a" * 64,
        NOW,
    )
    return ToolAssetAdapterCommand(
        request.global_id,
        uid(22),
        1,
        operation,
        "b" * 64,
        source_value.source_hash,
        expectation,
        request.canonical_mapping(),
    )


def body(value: ToolAssetAdapterCommand | None = None) -> bytes:
    return canonical_json((value or command()).snapshot).encode("utf-8")


class ERPNextConnectorToolAssetContractTest(unittest.TestCase):
    def test_exact_launchflow_command_decodes_to_five_owned_asset_values(self) -> None:
        decoded = decode_tool_asset_command(body())
        self.assertEqual(decoded.operation, "create_tool_asset")
        self.assertEqual(decoded.actor_user_id, "engineer@example.invalid")
        self.assertEqual(decoded.tooling_master_title, "Synthetic Tooling Master")
        self.assertEqual(decoded.physical_set_serial, "SET-SYNTHETIC-001")
        self.assertEqual(decoded.tooling_requirement_kind, "new_tool")
        self.assertEqual(decoded.expected_mapping_version, 0)
        self.assertEqual(
            set(decoded.owned_values()),
            {
                "tooling_master_title",
                "physical_set_serial",
                "tooling_requirement_kind",
                "source_tooling_revision",
                "acceptance_evidence_reference",
            },
        )

    def test_business_actor_must_be_a_canonical_email(self) -> None:
        raw = deepcopy(command().snapshot)
        raw["request"]["actorUserId"] = "Engineer@example.invalid"
        with self.assertRaisesRegex(ToolAssetContractError, "actorUserId"):
            decode_tool_asset_command(canonical_json(raw).encode("utf-8"))

    def test_attempt_identity_does_not_change_semantic_request_hash(self) -> None:
        first = command()
        retried = ToolAssetAdapterCommand(
            first.request_global_id,
            uid(23),
            2,
            first.operation,
            first.target_idempotency_key_hash,
            first.source_hash,
            first.mapping_expectation,
            first.request_snapshot,
        )
        self.assertEqual(
            decode_tool_asset_command(body(first)).semantic_request_hash,
            decode_tool_asset_command(body(retried)).semantic_request_hash,
        )

    def test_tampering_duplicate_keys_and_non_sandbox_fail_closed(self) -> None:
        duplicate = body().replace(
            b'"contractVersion":1',
            b'"contractVersion":1,"contractVersion":1',
            1,
        )
        with self.assertRaises(ToolAssetContractError):
            decode_tool_asset_command(duplicate)
        with self.assertRaises(ToolAssetContractError):
            decode_tool_asset_command(b"x" * 1_048_577)
        for mutation in ("source", "approval", "mapping", "profile"):
            raw = deepcopy(command().snapshot)
            if mutation == "source":
                raw["request"]["source"]["toolingMasterTitle"] = "Drifted"
            elif mutation == "approval":
                raw["request"]["approval"]["state"] = "unavailable"
            elif mutation == "mapping":
                raw["request"]["mappingExpectation"]["mappingVersion"] = 1
            else:
                raw["request"]["profile"]["targetMode"] = "synthetic"
            with (
                self.subTest(mutation=mutation),
                self.assertRaises(ToolAssetContractError),
            ):
                decode_tool_asset_command(canonical_json(raw).encode("utf-8"))

    def test_receiver_profile_is_exact_and_each_operation_is_default_off(self) -> None:
        self.assertTrue(operation_is_disabled({}, "create_tool_asset"))
        self.assertTrue(operation_is_disabled({}, "update_tool_asset"))
        configuration = {
            "npi_erp_connector_tool_asset_create_disabled": False,
            "npi_erp_connector_tool_asset_update_disabled": True,
            "npi_erp_connector_tool_asset_profile": {
                "company": "JCE Test",
                "location": "JCE Test Location",
                "itemCode": "NPI-TOOL-ASSET",
                "purchaseDateSource": "acceptedAt",
                "purchaseAmount": "1.00",
            },
        }
        profile_value = load_tool_asset_profile(configuration)
        self.assertEqual(profile_value.company, "JCE Test")
        self.assertFalse(operation_is_disabled(configuration, "create_tool_asset"))
        self.assertTrue(operation_is_disabled(configuration, "update_tool_asset"))
        configuration["npi_erp_connector_tool_asset_profile"]["purchaseDateSource"] = (
            "today"
        )
        with self.assertRaises(ToolAssetConfigurationError):
            load_tool_asset_profile(configuration)
        configuration["npi_erp_connector_tool_asset_profile"]["purchaseDateSource"] = (
            "acceptedAt"
        )
        configuration["npi_erp_connector_tool_asset_profile"]["purchaseAmount"] = "0"
        with self.assertRaises(ToolAssetConfigurationError):
            load_tool_asset_profile(configuration)


if __name__ == "__main__":
    unittest.main()
