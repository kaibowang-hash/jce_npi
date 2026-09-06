from __future__ import annotations

import json
import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

sys.path.insert(0, "apps/npi_core")
sys.path.insert(0, "apps/npi_integration")

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.tooling.domain import ToolingRequirementKind
from npi_integration.tool_asset_request.domain import (
    ToolAssetDispatchState,
    ToolAssetRequestInput,
    ToolAssetTargetResultState,
    create_mock_tool_asset_request,
    tool_asset_request_from_snapshot,
)


NOW = datetime(2026, 8, 8, 22, 30, tzinfo=UTC)


def uid(value: int) -> UUID:
    return UUID(int=value)


def request_input(*, tooling_set_global_id: UUID = uid(3)) -> ToolAssetRequestInput:
    return ToolAssetRequestInput(
        project_global_id=uid(1),
        tooling_master_global_id=uid(2),
        tooling_master_title="Synthetic Tooling Master",
        tooling_master_snapshot_hash="a" * 64,
        tooling_set_global_id=tooling_set_global_id,
        tooling_set_physical_serial="SET-SYNTHETIC-001",
        tooling_set_snapshot_hash="b" * 64,
        tooling_requirement_kind=ToolingRequirementKind.COPY_OR_ADDITIONAL_SET,
        set_revision_binding_global_id=uid(4),
        set_revision_binding_snapshot_hash="c" * 64,
        tooling_revision_global_id=uid(5),
        tooling_revision_number=2,
        tooling_revision_label="REV-SYNTHETIC-002",
        tooling_revision_snapshot_hash="d" * 64,
        acceptance_revision_global_id=uid(6),
        acceptance_version=1,
        acceptance_snapshot_hash="e" * 64,
    )


def request(value: ToolAssetRequestInput | None = None):
    return create_mock_tool_asset_request(
        tenant_id="tenant-synthetic",
        request_input=value or request_input(),
        actor_user_id="owner@example.test",
        request_id=uid(10),
        trace_id="trace-synthetic",
        idempotency_key_hash="f" * 64,
        created_at=NOW,
        global_id=uid(20),
    )


class ToolAssetRequestDomainTest(unittest.TestCase):
    def test_mock_request_is_draft_unapproved_undispatched_and_has_no_target_id(self) -> None:
        public = request().public_dict()
        self.assertEqual(public["operation"], "create_or_update_tool_asset")
        self.assertEqual(public["targetMode"], "mock")
        self.assertEqual(public["requestState"], "draft")
        self.assertEqual(public["inputValidationState"], "validated_mock")
        self.assertEqual(public["businessApprovalState"], "unavailable")
        self.assertEqual(public["dispatchState"], "prohibited")
        self.assertEqual(public["targetResultState"], "not_requested")
        self.assertEqual(public["formalAssetMapping"]["state"], "unavailable")
        serialized = json.dumps(public)
        self.assertNotIn("formalAssetId", serialized)
        self.assertNotIn("succeeded", serialized)
        self.assertNotIn("outbox", serialized.lower())

    def test_request_round_trip_is_hash_sealed(self) -> None:
        value = request()
        restored = tool_asset_request_from_snapshot(value.snapshot_payload())
        self.assertEqual(restored.snapshot_hash, value.snapshot_hash)
        tampered = value.snapshot_payload()
        tampered["payloadHash"] = "0" * 64
        with self.assertRaises(RequestValidationFailed):
            tool_asset_request_from_snapshot(tampered)

    def test_phase_6_axes_cannot_be_promoted(self) -> None:
        value = request()
        with self.assertRaises(RequestValidationFailed):
            replace(value, dispatch_state=ToolAssetDispatchState("prohibited"), operation="delete_tool_asset")
        with self.assertRaises(RequestValidationFailed):
            replace(value, target_result_state="succeeded")

    def test_each_physical_set_produces_a_distinct_request_input_hash(self) -> None:
        first = request_input(tooling_set_global_id=uid(3))
        second = replace(first, tooling_set_global_id=uid(30))
        self.assertNotEqual(first.snapshot_hash, second.snapshot_hash)


if __name__ == "__main__":
    unittest.main()
