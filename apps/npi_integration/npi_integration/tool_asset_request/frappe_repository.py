from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import frappe

from npi_core.tooling.domain import (
    ToolingIdempotencyConflict,
    ToolingReferenceUnavailable,
    sha256_json,
)
from npi_core.tooling.frappe_repository import FrappeToolingRepository
from npi_integration.tool_asset_request.domain import (
    TOOL_ASSET_OPERATION,
    ToolAssetRequest,
    ToolAssetRequestInput,
    create_mock_tool_asset_request,
    tool_asset_request_from_snapshot,
)
from npi_integration.tool_asset_request.frappe_validation import (
    tool_asset_request_write,
)


_MAX_REQUESTS = 500


@dataclass(frozen=True, slots=True)
class ToolAssetCommandOutcome:
    response: dict[str, Any]
    replayed: bool = False


class FrappeToolAssetRequestRepository(FrappeToolingRepository):
    """Project-authorized local Mock drafts; no ERP adapter is reachable here."""

    def acceptance_asset_context(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
    ) -> dict[str, Any] | None:
        context = self.tooling_acceptance_context(project_id, tooling_master_id)
        if context is None:
            return None
        project = self._authorized_project(project_id)
        if project is None:
            return None
        context["assetRequests"] = [
            value.public_dict()
            for value in self._asset_requests(project, tooling_master_id)
        ]
        return context

    def list_asset_requests(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None or self._master_for_project(project, tooling_master_id) is None:
            return None
        return {
            "projectGlobalId": str(project.global_id),
            "toolingMasterGlobalId": str(tooling_master_id),
            "items": [
                value.public_dict()
                for value in self._asset_requests(project, tooling_master_id)
            ],
        }

    def asset_request_detail(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        asset_request_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None or self._master_for_project(project, tooling_master_id) is None:
            return None
        value = self._asset_request_for_scope(
            project,
            tooling_master_id,
            asset_request_id,
        )
        return value.public_dict() if value else None

    def create_asset_request(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        tooling_set_id: UUID,
        *,
        idempotency_key_hash: str,
        acceptance_revision_id: UUID,
        acceptance_version: int,
        acceptance_snapshot_hash: str,
        expected_master_snapshot_hash: str,
        expected_set_snapshot_hash: str,
        expected_binding_snapshot_hash: str,
        expected_revision_number: int,
        expected_revision_snapshot_hash: str,
    ) -> ToolAssetCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        master = self._master_for_project(project, tooling_master_id)
        tooling_set = self._tooling_set_for_project(
            project,
            tooling_master_id,
            tooling_set_id,
        )
        if (
            master is None
            or str(master.snapshot_hash) != expected_master_snapshot_hash
            or tooling_set is None
            or tooling_set.snapshot_hash != expected_set_snapshot_hash
        ):
            raise ToolingReferenceUnavailable()
        binding = self._binding_for_set(project, tooling_set)
        if binding is None or binding.snapshot_hash != expected_binding_snapshot_hash:
            raise ToolingReferenceUnavailable()
        tooling_revision = self._tooling_revision_for_project(
            project,
            binding.tooling_revision_global_id,
            tooling_master_id=tooling_master_id,
        )
        if (
            tooling_revision is None
            or tooling_revision.revision_number != expected_revision_number
            or tooling_revision.snapshot_hash != expected_revision_snapshot_hash
        ):
            raise ToolingReferenceUnavailable()
        acceptance = self._acceptance_revision_for_project(
            project,
            tooling_master_id,
            acceptance_revision_id,
        )
        if (
            acceptance is None
            or acceptance.acceptance_version != acceptance_version
            or acceptance.snapshot_hash != acceptance_snapshot_hash
            or acceptance.tooling_set_global_id != tooling_set.global_id
            or acceptance.tooling_set_snapshot_hash != tooling_set.snapshot_hash
            or acceptance.set_revision_binding_global_id != binding.global_id
            or acceptance.set_revision_binding_snapshot_hash != binding.snapshot_hash
            or acceptance.tooling_revision_global_id != tooling_revision.global_id
            or acceptance.tooling_revision_number != tooling_revision.revision_number
            or acceptance.tooling_revision_snapshot_hash != tooling_revision.snapshot_hash
        ):
            raise ToolingReferenceUnavailable()
        request_input = ToolAssetRequestInput(
            project_global_id=project_id,
            tooling_master_global_id=tooling_master_id,
            tooling_master_title=str(master.title),
            tooling_master_snapshot_hash=str(master.snapshot_hash),
            tooling_set_global_id=tooling_set.global_id,
            tooling_set_physical_serial=tooling_set.physical_serial,
            tooling_set_snapshot_hash=tooling_set.snapshot_hash,
            tooling_requirement_kind=tooling_set.requirement_kind,
            set_revision_binding_global_id=binding.global_id,
            set_revision_binding_snapshot_hash=binding.snapshot_hash,
            tooling_revision_global_id=tooling_revision.global_id,
            tooling_revision_number=tooling_revision.revision_number,
            tooling_revision_label=tooling_revision.revision_label,
            tooling_revision_snapshot_hash=tooling_revision.snapshot_hash,
            acceptance_revision_global_id=acceptance.global_id,
            acceptance_version=acceptance.acceptance_version,
            acceptance_snapshot_hash=acceptance.snapshot_hash,
        )
        payload_hash = sha256_json(
            {
                "apiVersion": "npi.tooling-asset.v1",
                "operation": TOOL_ASSET_OPERATION,
                "targetMode": "mock",
                "requestInput": request_input.snapshot_payload(),
            }
        )
        receipt_key = sha256_json(
            {
                "tenantId": str(project.tenant_id),
                "projectGlobalId": str(project.global_id),
                "actorUserId": self.actor.casefold(),
                "operation": TOOL_ASSET_OPERATION,
                "idempotencyKeyHash": idempotency_key_hash,
            }
        )
        replay = self._asset_receipt_replay(
            project,
            receipt_key=receipt_key,
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
        )
        if replay is not None:
            return ToolAssetCommandOutcome(replay, replayed=True)
        now = self._now()
        value = create_mock_tool_asset_request(
            tenant_id=str(project.tenant_id),
            request_input=request_input,
            actor_user_id=self.actor,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
            idempotency_key_hash=idempotency_key_hash,
            created_at=now,
            global_id=self._new_uuid(),
        )
        if value.payload_hash != payload_hash:
            raise RuntimeError("The Tool Asset request payload integrity drifted.")
        response = value.public_dict()
        with tool_asset_request_write():
            receipt = self._insert_asset_receipt(
                project,
                receipt_key=receipt_key,
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._insert_asset_request(value)
            self._append_audit(
                operation="tooling_asset_request.create",
                global_id=value.global_id,
                object_version=1,
                summary={
                    "toolingSetGlobalId": str(tooling_set.global_id),
                    "acceptanceRevisionGlobalId": str(acceptance.global_id),
                    "targetMode": "mock",
                    "dispatchState": "prohibited",
                    "targetResultState": "not_requested",
                    "snapshotHash": value.snapshot_hash,
                },
            )
            self._seal_asset_receipt(receipt, value, response, now)
        return ToolAssetCommandOutcome(response)

    def _asset_requests(
        self,
        project: object,
        tooling_master_id: UUID,
    ) -> tuple[ToolAssetRequest, ...]:
        rows = self._bounded_documents(
            "NPI Tool Asset Request",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "tooling_master_global_id": str(tooling_master_id),
            },
            order_by="created_at desc, global_id asc",
            maximum=_MAX_REQUESTS,
        )
        return tuple(
            tool_asset_request_from_snapshot(_json_object(row.request_snapshot))
            for row in rows
        )

    @staticmethod
    def _asset_request_for_scope(
        project: object,
        tooling_master_id: UUID,
        asset_request_id: UUID,
    ) -> ToolAssetRequest | None:
        try:
            row = frappe.get_doc("NPI Tool Asset Request", str(asset_request_id))
        except frappe.DoesNotExistError:
            return None
        if any(
            (
                str(row.global_id) != str(asset_request_id),
                str(row.tenant_id) != str(project.tenant_id),
                str(row.project_global_id) != str(project.global_id),
                str(row.tooling_master_global_id) != str(tooling_master_id),
            )
        ):
            return None
        return tool_asset_request_from_snapshot(_json_object(row.request_snapshot))

    def _asset_receipt_replay(
        self,
        project: object,
        *,
        receipt_key: str,
        idempotency_key_hash: str,
        payload_hash: str,
    ) -> dict[str, Any] | None:
        row = frappe.db.get_value(
            "NPI Tool Asset Command Idempotency",
            {"receipt_key": receipt_key},
            [
                "tenant_id",
                "project_global_id",
                "actor_user_id",
                "operation",
                "idempotency_key_hash",
                "payload_hash",
                "request_global_id",
                "response_payload",
                "response_hash",
                "sealed",
            ],
            as_dict=True,
            for_update=True,
        )
        if not row:
            return None
        expected = {
            "tenant_id": str(project.tenant_id),
            "project_global_id": str(project.global_id),
            "actor_user_id": self.actor,
            "operation": TOOL_ASSET_OPERATION,
            "idempotency_key_hash": idempotency_key_hash,
            "payload_hash": payload_hash,
        }
        if any(str(_value(row, key)) != value for key, value in expected.items()):
            raise ToolingIdempotencyConflict()
        response = _json_object(_value(row, "response_payload"))
        if (
            int(_value(row, "sealed") or 0) != 1
            or not _value(row, "request_global_id")
            or str(_value(row, "response_hash")) != sha256_json(response)
            or response.get("globalId") != str(_value(row, "request_global_id"))
            or response.get("payloadHash") != payload_hash
        ):
            raise RuntimeError("The Tool Asset command receipt integrity drifted.")
        return response

    def _insert_asset_receipt(
        self,
        project: object,
        *,
        receipt_key: str,
        idempotency_key_hash: str,
        payload_hash: str,
        now: datetime,
    ) -> object:
        try:
            return frappe.get_doc(
                {
                    "doctype": "NPI Tool Asset Command Idempotency",
                    "global_id": str(self._new_uuid()),
                    "receipt_key": receipt_key,
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "actor_user_id": self.actor,
                    "operation": TOOL_ASSET_OPERATION,
                    "idempotency_key_hash": idempotency_key_hash,
                    "payload_hash": payload_hash,
                    "request_global_id": None,
                    "response_payload": None,
                    "response_hash": None,
                    "sealed": 0,
                    "created_at": _database_datetime(now),
                    "updated_at": _database_datetime(now),
                }
            ).insert()
        except (frappe.DuplicateEntryError, frappe.UniqueValidationError) as error:
            raise ToolingIdempotencyConflict() from error

    @staticmethod
    def _seal_asset_receipt(
        receipt: object,
        value: ToolAssetRequest,
        response: dict[str, Any],
        now: datetime,
    ) -> None:
        receipt.request_global_id = str(value.global_id)
        receipt.response_payload = _canonical_json(response)
        receipt.response_hash = sha256_json(response)
        receipt.sealed = 1
        receipt.updated_at = _database_datetime(now)
        receipt.save()

    @staticmethod
    def _insert_asset_request(value: ToolAssetRequest) -> object:
        item = value.request_input
        return frappe.get_doc(
            {
                "doctype": "NPI Tool Asset Request",
                "global_id": str(value.global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(item.project_global_id),
                "tooling_master": str(item.tooling_master_global_id),
                "tooling_master_global_id": str(item.tooling_master_global_id),
                "tooling_set": str(item.tooling_set_global_id),
                "tooling_set_global_id": str(item.tooling_set_global_id),
                "tooling_revision": str(item.tooling_revision_global_id),
                "tooling_revision_global_id": str(item.tooling_revision_global_id),
                "acceptance_revision": str(item.acceptance_revision_global_id),
                "acceptance_revision_global_id": str(item.acceptance_revision_global_id),
                "target_mode": value.target_mode.value,
                "api_version": value.api_version,
                "operation": value.operation,
                "request_state": value.request_state.value,
                "input_validation_state": value.input_validation_state.value,
                "business_approval_state": value.business_approval_state.value,
                "dispatch_state": value.dispatch_state.value,
                "target_result_state": value.target_result_state.value,
                "request_input_snapshot": _canonical_json(item.snapshot_payload()),
                "request_input_hash": item.snapshot_hash,
                "payload_hash": value.payload_hash,
                "request_snapshot": _canonical_json(value.snapshot_payload()),
                "snapshot_hash": value.snapshot_hash,
                "actor_user_id": value.actor_user_id,
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "idempotency_key_hash": value.idempotency_key_hash,
                "created_at": _database_datetime(value.created_at),
            }
        ).insert()


def _value(row: object, key: str) -> object:
    return row.get(key) if hasattr(row, "get") else getattr(row, key)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_object(value: object) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise RuntimeError("The Tool Asset request snapshot is invalid.")
    return value


def _database_datetime(value: datetime) -> str:
    return value.astimezone(UTC).replace(tzinfo=None).isoformat(
        sep=" ",
        timespec="microseconds",
    )
