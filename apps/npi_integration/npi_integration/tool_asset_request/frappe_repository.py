from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import frappe

from npi_core.tooling.domain import (
    ToolingIdempotencyConflict,
    ToolingReferenceUnavailable,
    sha256_json,
)
from npi_core.foundation.errors import NpiProblem
from npi_core.foundation.audit import create_audit_event
from npi_core.project_controls.terminal_guard import require_mutable_project
from npi_core.tooling.frappe_repository import FrappeToolingRepository
from npi_integration.tool_asset_request.config import ToolAssetExecutionProfile
from npi_integration.tool_asset_request.domain import (
    TOOL_ASSET_OPERATION,
    ToolAssetRequest,
    ToolAssetRequestInput,
    create_mock_tool_asset_request,
    tool_asset_request_from_snapshot,
)
from npi_integration.tool_asset_request.diagnostics import (
    p606_asset_create_step,
    tool_asset_context_step,
)
from npi_integration.tool_asset_request.frappe_validation import (
    tool_asset_request_write,
)
from npi_integration.tool_asset_request.execution_domain import (
    CREATE_TOOL_ASSET,
    TOOL_ASSET_EXECUTION_API_VERSION,
    TOOL_ASSET_EXECUTION_SCHEMA_VERSION,
    TOOL_ASSET_OUTBOX_SCHEMA_VERSION,
    TOOL_ASSET_REQUEST_EVENT_TYPE,
    TOOL_ASSET_OWNED_FIELDS,
    UPDATE_TOOL_ASSET,
    ToolAssetApprovalState,
    ToolAssetBusinessApprovalReference,
    ToolAssetExecutionOperation,
    ToolAssetExecutionRequest,
    ToolAssetExecutionRequestState,
    ToolAssetExecutionTargetMode,
    ToolAssetMappingExpectation,
    ToolAssetSourceSnapshot,
    canonical_hash,
    tool_asset_execution_request_from_mapping,
)
from npi_integration.tool_asset_request.execution_frappe_validation import (
    ToolAssetSupportWriteCapability,
    insert_tool_asset_audit_document,
    insert_tool_asset_support_document,
    save_tool_asset_support_document,
    tool_asset_request_transaction_write,
)
from npi_integration.tool_asset_request.problems import (
    ToolAssetExecutionApprovalUnavailable,
    ToolAssetExecutionAuthorityUnavailable,
    ToolAssetExecutionIdempotencyConflict,
    ToolAssetExecutionProfileUnavailable,
    ToolAssetExecutionStateConflict,
    ToolAssetExecutionStreamActive,
    ToolAssetExecutionUnavailable,
)


_MAX_REQUESTS = 500
_MAX_ATTEMPTS = 100
ProfileResolver = Callable[[str, UUID], ToolAssetExecutionProfile | None]


@dataclass(frozen=True, slots=True)
class ToolAssetCommandOutcome:
    response: dict[str, Any]
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class ToolAssetExecutionCommandOutcome:
    response: dict[str, Any] | None = None
    replayed: bool = False
    should_enqueue: bool = False
    outbox_event_id: UUID | None = None
    problem: NpiProblem | None = None


class FrappeToolAssetRequestRepository(FrappeToolingRepository):
    """Project-authorized local Mock drafts; no ERP adapter is reachable here."""

    def __init__(
        self,
        *,
        execution_profile_resolver: ProfileResolver | None = None,
        **values: object,
    ) -> None:
        super().__init__(**values)
        self._execution_profile_resolver = execution_profile_resolver

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
        with p606_asset_create_step("P805_P606_ASSET_PROJECT_LOCK"):
            project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        with p606_asset_create_step("P805_P606_ASSET_MASTER_RESOLVE"):
            master = self._master_for_project(project, tooling_master_id)
            if master is None or str(master.snapshot_hash) != expected_master_snapshot_hash:
                raise ToolingReferenceUnavailable()
        with p606_asset_create_step("P805_P606_ASSET_SET_RESOLVE"):
            tooling_set = self._tooling_set_for_project(
                project,
                tooling_master_id,
                tooling_set_id,
            )
            if tooling_set is None or tooling_set.snapshot_hash != expected_set_snapshot_hash:
                raise ToolingReferenceUnavailable()
        with p606_asset_create_step("P805_P606_ASSET_BINDING_RESOLVE"):
            binding = self._binding_for_set(project, tooling_set)
            if binding is None or binding.snapshot_hash != expected_binding_snapshot_hash:
                raise ToolingReferenceUnavailable()
        with p606_asset_create_step("P805_P606_ASSET_REVISION_RESOLVE"):
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
        with p606_asset_create_step("P805_P606_ASSET_ACCEPTANCE_RESOLVE"):
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
                or acceptance.tooling_revision_snapshot_hash
                != tooling_revision.snapshot_hash
            ):
                raise ToolingReferenceUnavailable()
        with p606_asset_create_step("P805_P606_ASSET_INPUT_BUILD"):
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
        with p606_asset_create_step("P805_P606_ASSET_PAYLOAD_BUILD"):
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
        with p606_asset_create_step("P805_P606_ASSET_RECEIPT_REPLAY"):
            replay = self._asset_receipt_replay(
                project,
                receipt_key=receipt_key,
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
            )
        if replay is not None:
            return ToolAssetCommandOutcome(replay, replayed=True)
        with p606_asset_create_step("P805_P606_ASSET_DOMAIN_BUILD"):
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
        with p606_asset_create_step("P805_P606_ASSET_RESPONSE_BUILD"):
            response = value.public_dict()
        with p606_asset_create_step("P805_P606_ASSET_TRANSACTION_SCOPE"):
            with tool_asset_request_write():
                with p606_asset_create_step("P805_P606_ASSET_RECEIPT_INSERT"):
                    receipt = self._insert_asset_receipt(
                        project,
                        receipt_key=receipt_key,
                        idempotency_key_hash=idempotency_key_hash,
                        payload_hash=payload_hash,
                        now=now,
                    )
                with p606_asset_create_step("P805_P606_ASSET_REQUEST_INSERT"):
                    self._insert_asset_request(value)
                with p606_asset_create_step("P805_P606_ASSET_AUDIT_APPEND"):
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
                with p606_asset_create_step("P805_P606_ASSET_RECEIPT_SEAL"):
                    self._seal_asset_receipt(receipt, value, response, now)
        return ToolAssetCommandOutcome(response)

    def list_execution_requests(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        tooling_set_id: UUID,
        *,
        acceptance_revision_id: UUID | None = None,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        master = self._master_for_project(project, tooling_master_id)
        tooling_set = self._tooling_set_for_project(
            project,
            tooling_master_id,
            tooling_set_id,
        )
        if master is None or tooling_set is None:
            return None
        with tool_asset_context_step(
            "P805_TOOL_ASSET_CONTEXT_PROFILE_RESOLVE"
        ):
            profile = self._read_execution_profile(project)
        context = None
        if acceptance_revision_id is not None and profile is not None:
            contexts: dict[str, object] = {}
            for operation in (
                ToolAssetExecutionOperation.CREATE,
                ToolAssetExecutionOperation.UPDATE,
            ):
                try:
                    value = self._build_execution_request(
                        project,
                        tooling_master_id,
                        tooling_set_id,
                        acceptance_revision_id,
                        profile,
                        operation,
                        idempotency_key_hash="0" * 64,
                        lock=False,
                    )
                except (NpiProblem, RuntimeError, ValueError):
                    continue
                contexts[operation.value] = self._command_context_payload(value)
            context = contexts or None
        rows = self._bounded_documents(
            "NPI Tool Asset Request",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "tooling_master_global_id": str(tooling_master_id),
                "tooling_set_global_id": str(tooling_set_id),
                "schema_version": TOOL_ASSET_EXECUTION_SCHEMA_VERSION,
            },
            order_by="created_at desc, global_id asc",
            maximum=_MAX_REQUESTS,
        )
        return {
            "projectGlobalId": str(project.global_id),
            "toolingMasterGlobalId": str(tooling_master_id),
            "toolingSetGlobalId": str(tooling_set_id),
            "permissions": self._execution_permissions(project, profile),
            "businessApproval": ToolAssetBusinessApprovalReference(
                ToolAssetApprovalState.UNAVAILABLE
            ).canonical_mapping(),
            "executionProfile": profile.reference.canonical_mapping() if profile else None,
            "commandContexts": context,
            "items": [self._execution_request_public(row) for row in rows],
        }

    def execution_request_detail(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        tooling_set_id: UUID,
        request_global_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        if (
            self._master_for_project(project, tooling_master_id) is None
            or self._tooling_set_for_project(
                project,
                tooling_master_id,
                tooling_set_id,
            )
            is None
        ):
            return None
        row = self._execution_request_for_scope(
            project,
            tooling_master_id,
            tooling_set_id,
            request_global_id,
            lock=False,
        )
        if row is None:
            return None
        request = tool_asset_execution_request_from_mapping(
            _json_object(row.request_snapshot)
        )
        detail = self._execution_request_public(row)
        request = replace(
            request,
            state=ToolAssetExecutionRequestState(str(row.execution_state)),
            optimistic_version=int(row.optimistic_version or 0),
        )
        attempts = self._execution_attempts_public(request, row)
        result, field_results = self._execution_result_public(request, row, attempts)
        observation, current_mapping = self._execution_mapping_public(
            project,
            request,
            result,
        )
        profile = self._read_execution_profile(project)
        detail.update(
            {
                "attempts": attempts,
                "result": result,
                "fieldResults": field_results,
                "mappingObservation": observation,
                "currentMapping": current_mapping,
                "permissions": self._execution_permissions(project, profile),
            }
        )
        return detail

    def _execution_attempts_public(
        self,
        request: ToolAssetExecutionRequest,
        request_row: object,
    ) -> list[dict[str, Any]]:
        rows = self._bounded_documents(
            "NPI Tool Asset Attempt",
            filters={"request_global_id": str(request.global_id)},
            order_by="attempt_number asc, global_id asc",
            maximum=_MAX_ATTEMPTS,
        )
        values: list[dict[str, Any]] = []
        seen: set[int] = set()
        for row in rows:
            snapshot = _json_object(row.attempt_snapshot)
            attempt_number = int(row.attempt_number or 0)
            expected_bindings = (
                str(request.global_id),
                str(request_row.outbox_event_id),
                request.operation.value,
                request.source.source_hash,
                canonical_hash(request.mapping_expectation.canonical_mapping()),
                request.profile.profile_id,
                request.profile.profile_version,
                request.profile.snapshot_hash,
            )
            actual_bindings = (
                str(row.request_global_id),
                str(row.outbox_event_id),
                str(row.operation),
                str(row.source_hash),
                str(row.mapping_expectation_hash),
                str(row.profile_id),
                int(row.profile_version or 0),
                str(row.profile_snapshot_hash),
            )
            if (
                attempt_number < 1
                or attempt_number in seen
                or actual_bindings != expected_bindings
                or snapshot.get("global_id") != str(row.global_id)
                or snapshot.get("attempt_number") != attempt_number
                or canonical_hash(snapshot) != str(row.attempt_hash)
            ):
                raise RuntimeError("Persisted Tool Asset attempt is invalid.")
            seen.add(attempt_number)
            values.append(
                {
                    "globalId": str(row.global_id),
                    "attemptNumber": attempt_number,
                    "state": str(row.state),
                    "adapterBoundaryCrossed": bool(row.adapter_boundary_crossed),
                    "transportDisposition": str(row.transport_disposition) if row.transport_disposition else None,
                    "faultKind": str(row.fault_kind) if row.fault_kind else None,
                    "reconciliationRequired": bool(row.reconciliation_required),
                    "safeErrorCode": str(row.safe_error_code) if row.safe_error_code else None,
                    "startedAt": _utc_text(_datetime_value(row.started_at)),
                    "finishedAt": _utc_text(_datetime_value(row.finished_at)) if row.finished_at else None,
                }
            )
        return values

    def _execution_result_public(
        self,
        request: ToolAssetExecutionRequest,
        request_row: object,
        attempts: list[dict[str, Any]],
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        result_id = getattr(request_row, "result_global_id", None)
        if not result_id:
            if request.state not in {
                ToolAssetExecutionRequestState.VALIDATED_MOCK,
                ToolAssetExecutionRequestState.QUEUED,
                ToolAssetExecutionRequestState.PROCESSING,
            }:
                raise RuntimeError("Persisted Tool Asset result is unavailable.")
            return None, []
        try:
            row = frappe.get_doc("NPI Tool Asset Result", str(result_id))
        except frappe.DoesNotExistError as error:
            raise RuntimeError("Persisted Tool Asset result is unavailable.") from error
        snapshot = _json_object(row.result_snapshot)
        if (
            snapshot.get("globalId") != str(result_id)
            or snapshot.get("requestGlobalId") != str(request.global_id)
            or str(row.request_global_id) != str(request.global_id)
            or str(row.state) != request.state.value
            or canonical_hash(snapshot) != str(row.result_hash)
            or not any(value["globalId"] == str(row.attempt_global_id) for value in attempts)
        ):
            raise RuntimeError("Persisted Tool Asset result is invalid.")
        fields = self._bounded_documents(
            "NPI Tool Asset Field Result",
            filters={"result_global_id": str(result_id)},
            order_by="field_code asc, global_id asc",
            maximum=len(TOOL_ASSET_OWNED_FIELDS),
        )
        public_by_code: dict[str, dict[str, Any]] = {}
        canonical_by_code: dict[str, dict[str, Any]] = {}
        for field in fields:
            value = _json_object(field.field_result_snapshot)
            field_code = str(field.field_code)
            if (
                value.get("fieldCode") != field_code
                or value.get("requestGlobalId") != str(request.global_id)
                or value.get("resultGlobalId") != str(result_id)
                or canonical_hash(value) != str(field.field_result_hash)
            ):
                raise RuntimeError("Persisted Tool Asset field result is invalid.")
            if field_code in canonical_by_code:
                raise RuntimeError("Persisted Tool Asset field result is invalid.")
            canonical_by_code[field_code] = {
                    key: value[key]
                    for key in (
                        "fieldCode",
                        "state",
                        "authority",
                        "responseAuthenticated",
                        "responseHash",
                        "faultKind",
                    )
                }
            public_by_code[field_code] = {
                    "fieldCode": field_code,
                    "state": str(field.state),
                    "authority": str(field.authority),
                    "responseAuthenticated": bool(field.response_authenticated),
                    "faultKind": str(field.fault_kind),
                    "observedAt": str(value["observedAt"]),
                }
        canonical_fields = [canonical_by_code[code] for code in TOOL_ASSET_OWNED_FIELDS if code in canonical_by_code]
        public_fields = [public_by_code[code] for code in TOOL_ASSET_OWNED_FIELDS if code in public_by_code]
        if (
            tuple(value["fieldCode"] for value in canonical_fields)
            != TOOL_ASSET_OWNED_FIELDS
            or canonical_hash(canonical_fields) != str(row.field_result_set_hash)
        ):
            raise RuntimeError("Persisted Tool Asset field result set is invalid.")
        return (
            {
                "globalId": str(result_id),
                "attemptGlobalId": str(row.attempt_global_id),
                "attemptNumber": int(row.attempt_number),
                "operation": str(row.operation),
                "state": str(row.state),
                "authority": str(row.authority),
                "responseAuthenticated": bool(row.response_authenticated),
                "faultKind": str(row.fault_kind),
                "observedAt": str(snapshot["observedAt"]),
                "formalAssetId": None,
                "targetVersion": None,
            },
            public_fields,
        )

    def _execution_mapping_public(
        self,
        project: object,
        request: ToolAssetExecutionRequest,
        result: dict[str, Any] | None,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        rows = self._bounded_documents(
            "NPI Tool Asset Mapping Observation",
            filters={"request_global_id": str(request.global_id)},
            order_by="observed_at asc, global_id asc",
            maximum=1,
        )
        if result is None:
            if rows:
                raise RuntimeError("Persisted Tool Asset mapping observation is invalid.")
            return None, None
        if len(rows) != 1:
            raise RuntimeError("Persisted Tool Asset mapping observation is unavailable.")
        row = rows[0]
        snapshot = _json_object(row.observation_snapshot)
        expected = (
            str(project.tenant_id),
            str(project.global_id),
            str(request.source.tooling_set_global_id),
            request.source.source_stream_key_hash,
            str(request.global_id),
            result["globalId"],
            result["attemptGlobalId"],
            request.operation.value,
            request.source.source_hash,
            canonical_hash(request.mapping_expectation.canonical_mapping()),
        )
        actual = tuple(
            str(value)
            for value in (
                row.tenant_id,
                row.project_global_id,
                row.tooling_set_global_id,
                row.source_stream_key_hash,
                row.request_global_id,
                row.result_global_id,
                row.attempt_global_id,
                row.operation,
                row.source_hash,
                row.mapping_expectation_hash,
            )
        )
        if actual != tuple(str(value) for value in expected) or canonical_hash(snapshot) != str(row.observation_hash):
            raise RuntimeError("Persisted Tool Asset mapping observation is invalid.")
        observation = {
            "disposition": str(row.disposition),
            "authority": str(row.authority),
            "responseAuthenticated": bool(row.response_authenticated),
            "observedAt": str(snapshot["observedAt"]),
            "previousFormalAssetId": None,
            "previousTargetVersion": None,
            "observedFormalAssetId": None,
            "observedTargetVersion": None,
        }
        authoritative = (
            result["state"] == ToolAssetExecutionRequestState.SUCCEEDED.value
            and result["authority"] == "authoritative_sandbox"
            and result["responseAuthenticated"] is True
            and str(row.disposition) == "advance"
        )
        if not authoritative:
            return observation, None
        head = self._mapping_head(project, request.source, lock=False)
        if head is None or str(head.current_observation) != str(row.global_id) or str(head.current_observation_hash) != str(row.observation_hash):
            raise RuntimeError("Persisted Tool Asset current mapping is invalid.")
        expected_head = _json_object(head.head_snapshot)
        if canonical_hash(expected_head) != str(head.head_hash):
            raise RuntimeError("Persisted Tool Asset current mapping is invalid.")
        return observation, {
            "mappingVersion": int(head.mapping_version),
            "formalAssetId": str(head.formal_asset_id),
            "targetVersion": str(head.target_version),
            "observationHash": str(row.observation_hash),
            "updatedAt": _utc_text(_datetime_value(head.updated_at)),
        }

    def create_tool_asset_execution_request(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        tooling_set_id: UUID,
        **values: Any,
    ) -> ToolAssetExecutionCommandOutcome | None:
        return self._create_execution_request(
            project_id,
            tooling_master_id,
            tooling_set_id,
            ToolAssetExecutionOperation.CREATE,
            **values,
        )

    def update_tool_asset_execution_request(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        tooling_set_id: UUID,
        **values: Any,
    ) -> ToolAssetExecutionCommandOutcome | None:
        return self._create_execution_request(
            project_id,
            tooling_master_id,
            tooling_set_id,
            ToolAssetExecutionOperation.UPDATE,
            **values,
        )

    def _create_execution_request(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        tooling_set_id: UUID,
        operation: ToolAssetExecutionOperation,
        *,
        acceptance_revision_id: UUID,
        expected_source_hash: str,
        expected_approval_hash: str,
        expected_mapping_expectation_hash: str,
        expected_profile_snapshot_hash: str,
        idempotency_key_hash: str,
        acknowledgement: str,
    ) -> ToolAssetExecutionCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        command_hash = canonical_hash(
            {
                "schemaVersion": TOOL_ASSET_EXECUTION_SCHEMA_VERSION,
                "apiVersion": TOOL_ASSET_EXECUTION_API_VERSION,
                "operation": operation.value,
                "projectGlobalId": str(project.global_id),
                "toolingMasterGlobalId": str(tooling_master_id),
                "toolingSetGlobalId": str(tooling_set_id),
                "acceptanceRevisionGlobalId": str(acceptance_revision_id),
                "expectedSourceHash": expected_source_hash,
                "expectedApprovalHash": expected_approval_hash,
                "expectedMappingExpectationHash": expected_mapping_expectation_hash,
                "expectedProfileSnapshotHash": expected_profile_snapshot_hash,
                "acknowledgement": acknowledgement,
            }
        )
        receipt_key = canonical_hash(
            {
                "schemaVersion": TOOL_ASSET_EXECUTION_SCHEMA_VERSION,
                "tenantId": str(project.tenant_id),
                "projectGlobalId": str(project.global_id),
                "actorUserId": self.actor.casefold(),
                "idempotencyKeyHash": idempotency_key_hash,
            }
        )
        receipt = self._execution_receipt(receipt_key)
        if receipt is not None:
            return self._execution_replay_or_conflict(
                project,
                receipt,
                receipt_key=receipt_key,
                operation=operation,
                idempotency_key_hash=idempotency_key_hash,
                command_hash=command_hash,
            )
        require_mutable_project(project)
        try:
            profile = self._required_execution_profile(project)
            value = self._build_execution_request(
                project,
                tooling_master_id,
                tooling_set_id,
                acceptance_revision_id,
                profile,
                operation,
                idempotency_key_hash=idempotency_key_hash,
                lock=True,
            )
        except ToolAssetExecutionProfileUnavailable as problem:
            return ToolAssetExecutionCommandOutcome(problem=problem)
        except ToolAssetExecutionApprovalUnavailable as problem:
            return ToolAssetExecutionCommandOutcome(problem=problem)
        except ToolAssetExecutionAuthorityUnavailable as problem:
            return ToolAssetExecutionCommandOutcome(problem=problem)
        except (ToolAssetExecutionStateConflict, ToolAssetExecutionUnavailable) as problem:
            return ToolAssetExecutionCommandOutcome(problem=problem)
        if (
            value.source.source_hash != expected_source_hash
            or canonical_hash(value.approval.canonical_mapping()) != expected_approval_hash
            or canonical_hash(value.mapping_expectation.canonical_mapping())
            != expected_mapping_expectation_hash
            or value.profile.snapshot_hash != expected_profile_snapshot_hash
        ):
            return ToolAssetExecutionCommandOutcome(
                problem=ToolAssetExecutionStateConflict()
            )
        dispatch_allowed = value.profile.target_mode is not ToolAssetExecutionTargetMode.MOCK
        outbox_event_id = self._new_uuid() if dispatch_allowed else None
        target_key_hash = canonical_hash(
            {
                "tenantId": value.source.tenant_id,
                "sourceStreamKeyHash": value.source.source_stream_key_hash,
                "operation": operation.value,
                "idempotencyKeyHash": idempotency_key_hash,
            }
        )
        semantic_effect_hash = canonical_hash(
            {
                "operation": operation.value,
                "sourceHash": value.source.source_hash,
                "mappingExpectationHash": canonical_hash(
                    value.mapping_expectation.canonical_mapping()
                ),
                "profileSnapshotHash": value.profile.snapshot_hash,
            }
        )
        response = {
            "requestGlobalId": str(value.global_id),
            "request": value.canonical_mapping(),
            "dispatchAllowed": dispatch_allowed,
            "outboxEventId": str(outbox_event_id) if outbox_event_id else None,
            "targetIdempotencyKeyHash": target_key_hash,
            "semanticEffectHash": semantic_effect_hash,
        }
        with tool_asset_request_transaction_write(self.actor) as capability:
            guard = None
            if dispatch_allowed:
                guard = self._locked_execution_stream_guard(
                    project,
                    value,
                    capability=capability,
                )
                if getattr(guard, "active_request_global_id", None):
                    return ToolAssetExecutionCommandOutcome(
                        problem=ToolAssetExecutionStreamActive()
                    )
            self._insert_execution_request(
                value,
                outbox_event_id=outbox_event_id,
                target_idempotency_key_hash=target_key_hash,
                semantic_effect_hash=semantic_effect_hash,
                capability=capability,
            )
            if outbox_event_id is not None:
                self._insert_execution_outbox(
                    project,
                    value,
                    event_id=outbox_event_id,
                    target_idempotency_key_hash=target_key_hash,
                    semantic_effect_hash=semantic_effect_hash,
                    capability=capability,
                )
                self._activate_execution_stream_guard(
                    guard,
                    value,
                    target_idempotency_key_hash=target_key_hash,
                    capability=capability,
                )
            self._append_execution_audit(
                operation=f"tool_asset_execution.{operation.value}.request.create",
                global_id=value.global_id,
                object_version=1,
                result=value.state.value,
                summary={
                    "sourceStreamKeyHash": value.source.source_stream_key_hash,
                    "sourceHash": value.source.source_hash,
                    "profileId": value.profile.profile_id,
                    "profileVersion": value.profile.profile_version,
                    "requestPayloadHash": value.payload_hash,
                    "outboxEventId": str(outbox_event_id) if outbox_event_id else None,
                },
                capability=capability,
            )
            self._insert_execution_receipt(
                project,
                value,
                receipt_key=receipt_key,
                command_hash=command_hash,
                response=response,
                capability=capability,
            )
        return ToolAssetExecutionCommandOutcome(
            response=response,
            should_enqueue=dispatch_allowed,
            outbox_event_id=outbox_event_id,
        )

    def _build_execution_request(
        self,
        project: object,
        tooling_master_id: UUID,
        tooling_set_id: UUID,
        acceptance_revision_id: UUID,
        profile: ToolAssetExecutionProfile,
        operation: ToolAssetExecutionOperation,
        *,
        idempotency_key_hash: str,
        lock: bool,
    ) -> ToolAssetExecutionRequest:
        create_operation = operation is ToolAssetExecutionOperation.CREATE
        with tool_asset_context_step(
            "P805_TOOL_ASSET_CONTEXT_CREATE_SOURCE",
            create_operation=create_operation,
        ):
            source = self._execution_source(
                project,
                tooling_master_id,
                tooling_set_id,
                acceptance_revision_id,
                lock=lock,
            )
        approval = ToolAssetBusinessApprovalReference(
            ToolAssetApprovalState.UNAVAILABLE
        )
        with tool_asset_context_step(
            "P805_TOOL_ASSET_CONTEXT_CREATE_PROFILE_BINDING",
            create_operation=create_operation,
        ):
            if (
                profile.tenant_id != source.tenant_id
                or profile.project_global_id != str(source.project_global_id)
            ):
                raise ToolAssetExecutionProfileUnavailable()
        with tool_asset_context_step(
            "P805_TOOL_ASSET_CONTEXT_CREATE_AUTHORITY",
            create_operation=create_operation,
        ):
            if profile.target_mode is ToolAssetExecutionTargetMode.MOCK:
                permitted = profile.permits(self.actor)
            else:
                permitted = profile.permits(self.actor, operation.value)
            if not permitted or self._current_actor_member(project) is None:
                raise ToolAssetExecutionAuthorityUnavailable()
        with tool_asset_context_step(
            "P805_TOOL_ASSET_CONTEXT_CREATE_SANDBOX_GUARD",
            create_operation=create_operation,
        ):
            if profile.target_mode is ToolAssetExecutionTargetMode.SANDBOX:
                raise ToolAssetExecutionApprovalUnavailable()
        with tool_asset_context_step(
            "P805_TOOL_ASSET_CONTEXT_CREATE_MAPPING",
            create_operation=create_operation,
        ):
            expectation = self._mapping_expectation(
                project,
                tooling_master_id,
                source,
                operation,
                lock=lock,
            )
        with tool_asset_context_step(
            "P805_TOOL_ASSET_CONTEXT_CREATE_REQUEST_BUILD",
            create_operation=create_operation,
        ):
            return ToolAssetExecutionRequest(
                global_id=self._new_uuid(),
                source=source,
                approval=approval,
                mapping_expectation=expectation,
                profile=profile.reference,
                state=(
                    ToolAssetExecutionRequestState.VALIDATED_MOCK
                    if profile.target_mode is ToolAssetExecutionTargetMode.MOCK
                    else ToolAssetExecutionRequestState.QUEUED
                ),
                actor_user_id=self.actor,
                request_id=UUID(self.request_id),
                trace_id=self.trace_id,
                idempotency_key_hash=idempotency_key_hash,
                created_at=self._now(),
            )

    def _execution_source(
        self,
        project: object,
        tooling_master_id: UUID,
        tooling_set_id: UUID,
        acceptance_revision_id: UUID,
        *,
        lock: bool,
    ) -> ToolAssetSourceSnapshot:
        master = self._master_for_project(project, tooling_master_id)
        tooling_set = self._tooling_set_for_project(project, tooling_master_id, tooling_set_id)
        if master is None or tooling_set is None:
            raise ToolAssetExecutionUnavailable()
        binding = self._binding_for_set(project, tooling_set)
        if binding is None:
            raise ToolAssetExecutionStateConflict()
        revision = self._tooling_revision_for_project(
            project,
            binding.tooling_revision_global_id,
            tooling_master_id=tooling_master_id,
        )
        acceptance = self._acceptance_revision_for_project(
            project,
            tooling_master_id,
            acceptance_revision_id,
        )
        if revision is None or acceptance is None:
            raise ToolAssetExecutionStateConflict()
        if any(
            (
                acceptance.tooling_set_global_id != tooling_set.global_id,
                acceptance.tooling_set_snapshot_hash != tooling_set.snapshot_hash,
                acceptance.set_revision_binding_global_id != binding.global_id,
                acceptance.set_revision_binding_snapshot_hash != binding.snapshot_hash,
                acceptance.tooling_revision_global_id != revision.global_id,
                acceptance.tooling_revision_number != revision.revision_number,
                acceptance.tooling_revision_snapshot_hash != revision.snapshot_hash,
                acceptance.tooling_master_snapshot_hash != str(master.snapshot_hash),
            )
        ):
            raise ToolAssetExecutionStateConflict()
        if lock:
            for doctype, identity, expected in (
                ("NPI Tooling Master", master.global_id, {"global_id": master.global_id, "tenant_id": project.tenant_id, "snapshot_hash": master.snapshot_hash}),
                ("NPI Tooling Set", tooling_set.global_id, {"global_id": tooling_set.global_id, "tenant_id": project.tenant_id, "project_global_id": project.global_id, "tooling_master_global_id": tooling_master_id, "snapshot_hash": tooling_set.snapshot_hash}),
                ("NPI Tooling Set Revision Binding", binding.global_id, {"global_id": binding.global_id, "tenant_id": project.tenant_id, "project_global_id": project.global_id, "tooling_set_global_id": tooling_set.global_id, "tooling_revision_global_id": revision.global_id, "snapshot_hash": binding.snapshot_hash}),
                ("NPI Tooling Revision", revision.global_id, {"global_id": revision.global_id, "tenant_id": project.tenant_id, "project_global_id": project.global_id, "tooling_master_global_id": tooling_master_id, "snapshot_hash": revision.snapshot_hash}),
                ("NPI Tooling Acceptance Evidence Revision", acceptance.global_id, {"global_id": acceptance.global_id, "tenant_id": project.tenant_id, "project_global_id": project.global_id, "tooling_master_global_id": tooling_master_id, "tooling_set_global_id": tooling_set.global_id, "snapshot_hash": acceptance.snapshot_hash}),
            ):
                self._lock_exact_execution_parent(doctype, identity, expected)
        return ToolAssetSourceSnapshot(
            tenant_id=str(project.tenant_id),
            project_global_id=UUID(str(project.global_id)),
            tooling_master_global_id=tooling_master_id,
            tooling_master_title=str(master.title),
            tooling_master_snapshot_hash=str(master.snapshot_hash),
            tooling_set_global_id=tooling_set.global_id,
            tooling_set_physical_serial=tooling_set.physical_serial,
            tooling_set_snapshot_hash=tooling_set.snapshot_hash,
            tooling_requirement_kind=tooling_set.requirement_kind.value,
            set_revision_binding_global_id=binding.global_id,
            set_revision_binding_snapshot_hash=binding.snapshot_hash,
            tooling_revision_global_id=revision.global_id,
            tooling_revision_number=revision.revision_number,
            tooling_revision_label=revision.revision_label,
            tooling_revision_snapshot_hash=revision.snapshot_hash,
            acceptance_revision_global_id=acceptance.global_id,
            acceptance_global_id=acceptance.acceptance_global_id,
            acceptance_version=acceptance.acceptance_version,
            acceptance_predecessor_global_id=acceptance.predecessor_global_id,
            acceptance_predecessor_snapshot_hash=acceptance.predecessor_snapshot_hash,
            acceptance_snapshot_hash=acceptance.snapshot_hash,
            accepted_at=acceptance.created_at,
        )

    @staticmethod
    def _lock_exact_execution_parent(
        doctype: str,
        identity: object,
        expected: Mapping[str, object],
    ) -> None:
        try:
            row = frappe.get_doc(doctype, str(identity), for_update=True)
        except frappe.DoesNotExistError as error:
            raise ToolAssetExecutionStateConflict() from error
        if any(str(getattr(row, key)) != str(value) for key, value in expected.items()):
            raise ToolAssetExecutionStateConflict()

    def _mapping_expectation(
        self,
        project: object,
        tooling_master_id: UUID,
        source: ToolAssetSourceSnapshot,
        operation: ToolAssetExecutionOperation,
        *,
        lock: bool,
    ) -> ToolAssetMappingExpectation:
        head = self._mapping_head(project, source, lock=lock)
        try:
            projection = self._asset_projection(project, tooling_master_id).public_dict()
        except Exception as error:
            raise ToolAssetExecutionStateConflict() from error
        if operation is ToolAssetExecutionOperation.CREATE:
            if head is not None or projection.get("state") != "unavailable":
                raise ToolAssetExecutionStateConflict()
            return ToolAssetMappingExpectation(
                operation=operation,
                source_stream_key_hash=source.source_stream_key_hash,
                mapping_version=0,
            )
        if head is None or projection.get("state") != "available":
            raise ToolAssetExecutionStateConflict()
        expected_projection = (
            str(source.tooling_set_global_id),
            int(head.mapping_version),
            str(head.formal_asset_id),
            str(head.target_version),
        )
        actual_projection = (
            str(projection.get("toolingSetGlobalId")),
            projection.get("mappingVersion"),
            str(projection.get("formalAssetId")),
            str(projection.get("targetVersion")),
        )
        if actual_projection != expected_projection:
            raise ToolAssetExecutionStateConflict()
        return ToolAssetMappingExpectation(
            operation=operation,
            source_stream_key_hash=source.source_stream_key_hash,
            mapping_version=int(head.mapping_version),
            formal_asset_id=str(head.formal_asset_id),
            target_version=str(head.target_version),
            observation_hash=str(head.current_observation_hash),
        )

    @staticmethod
    def _mapping_head(
        project: object,
        source: ToolAssetSourceSnapshot,
        *,
        lock: bool,
    ) -> object | None:
        name = frappe.db.get_value(
            "NPI Tool Asset Mapping Head",
            {"source_stream_key_hash": source.source_stream_key_hash},
            "name",
        )
        if not name:
            return None
        try:
            row = frappe.get_doc(
                "NPI Tool Asset Mapping Head",
                str(name),
                for_update=lock,
            )
        except frappe.DoesNotExistError as error:
            raise ToolAssetExecutionStateConflict() from error
        expected = {
            "schemaVersion": TOOL_ASSET_EXECUTION_SCHEMA_VERSION,
            "globalId": str(row.global_id),
            "tenantId": str(row.tenant_id),
            "projectGlobalId": str(row.project_global_id),
            "toolingSetGlobalId": str(row.tooling_set_global_id),
            "sourceStreamKeyHash": str(row.source_stream_key_hash),
            "mappingVersion": int(row.mapping_version),
            "formalAssetId": str(row.formal_asset_id),
            "targetVersion": str(row.target_version),
            "currentObservationGlobalId": str(row.current_observation),
            "currentObservationHash": str(row.current_observation_hash),
            "updatedAt": _utc_text(_datetime_value(row.updated_at)),
        }
        if (
            str(row.tenant_id) != str(project.tenant_id)
            or str(row.project_global_id) != str(project.global_id)
            or str(row.tooling_set_global_id) != str(source.tooling_set_global_id)
            or str(row.source_stream_key_hash) != source.source_stream_key_hash
            or _json_object(row.head_snapshot) != expected
            or canonical_hash(expected) != str(row.head_hash)
        ):
            raise ToolAssetExecutionStateConflict()
        return row

    def _required_execution_profile(self, project: object) -> ToolAssetExecutionProfile:
        profile = self._read_execution_profile(project)
        if profile is None:
            raise ToolAssetExecutionProfileUnavailable()
        return profile

    def _read_execution_profile(
        self,
        project: object,
    ) -> ToolAssetExecutionProfile | None:
        if not callable(self._execution_profile_resolver):
            return None
        try:
            profile = self._execution_profile_resolver(
                str(project.tenant_id),
                UUID(str(project.global_id)),
            )
        except Exception as error:
            raise ToolAssetExecutionProfileUnavailable() from error
        if profile is None:
            return None
        if (
            not isinstance(profile, ToolAssetExecutionProfile)
            or profile.tenant_id != str(project.tenant_id)
            or profile.project_global_id != str(project.global_id)
        ):
            raise ToolAssetExecutionProfileUnavailable()
        return profile

    def _execution_permissions(
        self,
        project: object,
        profile: ToolAssetExecutionProfile | None,
    ) -> dict[str, bool]:
        internal = bool(
            not self.principal.is_external
            and "NPI API User" in self.principal.roles
            and self._current_actor_member(project) is not None
        )
        return {
            "canView": True,
            "canCreate": bool(
                internal
                and profile is not None
                and (
                    profile.permits(self.actor)
                    if profile.target_mode is ToolAssetExecutionTargetMode.MOCK
                    else profile.permits(self.actor, CREATE_TOOL_ASSET)
                )
            ),
            "canUpdate": bool(
                internal
                and profile is not None
                and (
                    profile.permits(self.actor)
                    if profile.target_mode is ToolAssetExecutionTargetMode.MOCK
                    else profile.permits(self.actor, UPDATE_TOOL_ASSET)
                )
            ),
        }

    @staticmethod
    def _command_context_payload(value: ToolAssetExecutionRequest) -> dict[str, object]:
        return {
            "operation": value.operation.value,
            "source": value.source.canonical_mapping(),
            "expectedSourceHash": value.source.source_hash,
            "approval": value.approval.canonical_mapping(),
            "expectedApprovalHash": canonical_hash(value.approval.canonical_mapping()),
            "mappingExpectation": value.mapping_expectation.canonical_mapping(),
            "expectedMappingExpectationHash": canonical_hash(
                value.mapping_expectation.canonical_mapping()
            ),
            "profile": value.profile.canonical_mapping(),
            "expectedProfileSnapshotHash": value.profile.snapshot_hash,
        }

    @staticmethod
    def _execution_request_for_scope(
        project: object,
        tooling_master_id: UUID,
        tooling_set_id: UUID,
        request_global_id: UUID,
        *,
        lock: bool,
    ) -> object | None:
        try:
            row = frappe.get_doc(
                "NPI Tool Asset Request",
                str(request_global_id),
                for_update=lock,
            )
        except frappe.DoesNotExistError:
            return None
        return row if (
            str(row.global_id) == str(request_global_id)
            and int(row.schema_version or 0) == TOOL_ASSET_EXECUTION_SCHEMA_VERSION
            and str(row.tenant_id) == str(project.tenant_id)
            and str(row.project_global_id) == str(project.global_id)
            and str(row.tooling_master_global_id) == str(tooling_master_id)
            and str(row.tooling_set_global_id) == str(tooling_set_id)
        ) else None

    @staticmethod
    def _execution_request_public(row: object) -> dict[str, Any]:
        request = tool_asset_execution_request_from_mapping(
            _json_object(row.request_snapshot)
        )
        if (
            str(row.global_id) != str(request.global_id)
            or str(row.payload_hash) != request.payload_hash
            or str(row.source_hash) != request.source.source_hash
        ):
            raise RuntimeError("Persisted Tool Asset execution request is invalid.")
        current = replace(
            request,
            state=ToolAssetExecutionRequestState(str(row.execution_state)),
            optimistic_version=int(row.optimistic_version or 0),
        )
        return {
            "requestGlobalId": str(request.global_id),
            "request": current.canonical_mapping(),
            "dispatchAllowed": bool(row.dispatch_allowed),
            "outboxEventId": str(row.outbox_event_id) if row.outbox_event_id else None,
            "targetIdempotencyKeyHash": str(row.target_idempotency_key_hash),
            "semanticEffectHash": str(row.semantic_effect_hash),
            "resultGlobalId": str(row.result_global_id) if row.result_global_id else None,
        }

    @staticmethod
    def _execution_receipt(receipt_key: str) -> object | None:
        name = frappe.db.get_value(
            "NPI Tool Asset Command Idempotency",
            {"receipt_key": receipt_key},
            "name",
        )
        if not name:
            return None
        try:
            return frappe.get_doc(
                "NPI Tool Asset Command Idempotency",
                str(name),
                for_update=True,
            )
        except frappe.DoesNotExistError as error:
            raise RuntimeError("Persisted Tool Asset idempotency receipt is unavailable.") from error

    def _execution_replay_or_conflict(
        self,
        project: object,
        receipt: object,
        *,
        receipt_key: str,
        operation: ToolAssetExecutionOperation,
        idempotency_key_hash: str,
        command_hash: str,
    ) -> ToolAssetExecutionCommandOutcome:
        expected = (
            receipt_key,
            TOOL_ASSET_EXECUTION_SCHEMA_VERSION,
            str(project.tenant_id),
            str(project.global_id),
            self.actor.casefold(),
            operation.value,
            idempotency_key_hash,
            command_hash,
        )
        actual = (
            str(receipt.receipt_key),
            int(receipt.schema_version or 0),
            str(receipt.tenant_id),
            str(receipt.project_global_id),
            str(receipt.actor_user_id).casefold(),
            str(receipt.operation),
            str(receipt.idempotency_key_hash),
            str(receipt.payload_hash),
        )
        if actual != expected:
            if receipt.request_global_id:
                with tool_asset_request_transaction_write(self.actor) as capability:
                    self._append_execution_audit(
                        operation="tool_asset_execution.request.conflict",
                        global_id=UUID(str(receipt.request_global_id)),
                        object_version=1,
                        result="idempotency_conflict",
                        summary={"receiptKey": receipt_key, "errorCode": "TOOL_ASSET_EXECUTION_IDEMPOTENCY_CONFLICT"},
                        capability=capability,
                    )
            return ToolAssetExecutionCommandOutcome(
                problem=ToolAssetExecutionIdempotencyConflict()
            )
        response = _json_object(receipt.response_payload)
        if (
            int(receipt.sealed or 0) != 1
            or not receipt.request_global_id
            or response.get("requestGlobalId") != str(receipt.request_global_id)
            or not isinstance(response.get("request"), dict)
            or canonical_hash(response) != str(receipt.response_hash)
        ):
            raise RuntimeError("Persisted Tool Asset execution receipt is invalid.")
        row = self._execution_request_for_scope(
            project,
            UUID(str(response["request"]["source"]["toolingMasterGlobalId"])),
            UUID(str(response["request"]["source"]["toolingSetGlobalId"])),
            UUID(str(receipt.request_global_id)),
            lock=True,
        )
        if row is None or str(row.payload_hash) != str(response["request"].get("payloadHash")):
            raise RuntimeError("Persisted Tool Asset execution replay is invalid.")
        with tool_asset_request_transaction_write(self.actor) as capability:
            self._append_execution_audit(
                operation="tool_asset_execution.request.replay",
                global_id=UUID(str(receipt.request_global_id)),
                object_version=1,
                result="replayed",
                summary={"receiptKey": receipt_key, "requestPayloadHash": str(row.payload_hash)},
                capability=capability,
            )
        return ToolAssetExecutionCommandOutcome(response=response, replayed=True)

    def _append_execution_audit(
        self,
        *,
        operation: str,
        global_id: UUID,
        object_version: int,
        result: str,
        summary: Mapping[str, object],
        capability: ToolAssetSupportWriteCapability,
    ) -> None:
        event = create_audit_event(
            actor=self.actor,
            trace_id=self.trace_id,
            operation=operation,
            global_id=global_id,
            object_version=object_version,
            result=result,
            input_summary=summary,
        )
        insert_tool_asset_audit_document(
            frappe.get_doc(
                {
                    "doctype": "NPI Audit Event",
                    "event_id": str(event.event_id),
                    "global_id": str(event.global_id),
                    "object_version": event.object_version,
                    "actor": event.actor,
                    "trace_id": event.trace_id,
                    "operation": event.operation,
                    "result": event.result,
                    "input_summary": dict(event.input_summary),
                }
            ),
            capability=capability,
        )

    def _locked_execution_stream_guard(
        self,
        project: object,
        value: ToolAssetExecutionRequest,
        *,
        capability: ToolAssetSupportWriteCapability,
    ) -> object:
        name = frappe.db.get_value(
            "NPI Tool Asset Stream Guard",
            {"source_stream_key_hash": value.source.source_stream_key_hash},
            "name",
        )
        if name:
            try:
                row = frappe.get_doc("NPI Tool Asset Stream Guard", str(name), for_update=True)
            except frappe.DoesNotExistError as error:
                raise ToolAssetExecutionStateConflict() from error
            if any(
                (
                    str(row.source_stream_key_hash) != value.source.source_stream_key_hash,
                    str(row.tenant_id) != str(project.tenant_id),
                    str(row.project_global_id) != str(project.global_id),
                    str(row.tooling_set_global_id) != str(value.source.tooling_set_global_id),
                )
            ):
                raise ToolAssetExecutionStateConflict()
            return row
        return insert_tool_asset_support_document(
            frappe.get_doc(
                {
                    "doctype": "NPI Tool Asset Stream Guard",
                    "source_stream_key_hash": value.source.source_stream_key_hash,
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "tooling_set_global_id": str(value.source.tooling_set_global_id),
                    "optimistic_version": 1,
                    "updated_at": _database_datetime(value.created_at),
                }
            ),
            capability=capability,
        )

    @staticmethod
    def _activate_execution_stream_guard(
        guard: object,
        value: ToolAssetExecutionRequest,
        *,
        target_idempotency_key_hash: str,
        capability: ToolAssetSupportWriteCapability,
    ) -> None:
        guard.active_request_global_id = str(value.global_id)
        guard.active_target_idempotency_key_hash = target_idempotency_key_hash
        guard.active_state = value.state.value
        guard.optimistic_version = int(guard.optimistic_version or 0) + 1
        guard.updated_at = _database_datetime(value.created_at)
        save_tool_asset_support_document(guard, capability=capability)

    @staticmethod
    def _insert_execution_request(
        value: ToolAssetExecutionRequest,
        *,
        outbox_event_id: UUID | None,
        target_idempotency_key_hash: str,
        semantic_effect_hash: str,
        capability: ToolAssetSupportWriteCapability,
    ) -> None:
        source = value.source
        approval = value.approval.canonical_mapping()
        expectation = value.mapping_expectation.canonical_mapping()
        insert_tool_asset_support_document(
            frappe.get_doc(
                {
                    "doctype": "NPI Tool Asset Request",
                    "global_id": str(value.global_id),
                    "tenant_id": source.tenant_id,
                    "project_global_id": str(source.project_global_id),
                    "tooling_master": str(source.tooling_master_global_id),
                    "tooling_master_global_id": str(source.tooling_master_global_id),
                    "tooling_set": str(source.tooling_set_global_id),
                    "tooling_set_global_id": str(source.tooling_set_global_id),
                    "tooling_revision": str(source.tooling_revision_global_id),
                    "tooling_revision_global_id": str(source.tooling_revision_global_id),
                    "acceptance_revision": str(source.acceptance_revision_global_id),
                    "acceptance_revision_global_id": str(source.acceptance_revision_global_id),
                    "schema_version": TOOL_ASSET_EXECUTION_SCHEMA_VERSION,
                    "api_version": TOOL_ASSET_EXECUTION_API_VERSION,
                    "operation": value.operation.value,
                    "source_stream_key_hash": source.source_stream_key_hash,
                    "source_snapshot": source.canonical_mapping(),
                    "source_hash": source.source_hash,
                    "approval_snapshot": approval,
                    "approval_hash": canonical_hash(approval),
                    "mapping_expectation_snapshot": expectation,
                    "mapping_expectation_hash": canonical_hash(expectation),
                    "profile_id": value.profile.profile_id,
                    "profile_version": value.profile.profile_version,
                    "execution_target_mode": value.profile.target_mode.value,
                    "environment_code": value.profile.environment_code,
                    "profile_snapshot_hash": value.profile.snapshot_hash,
                    "projection_policy_id": value.profile.projection_policy_id,
                    "projection_policy_version": value.profile.projection_policy_version,
                    "projection_policy_hash": value.profile.projection_policy_hash,
                    "execution_state": value.state.value,
                    "dispatch_allowed": int(outbox_event_id is not None),
                    "outbox_event_id": str(outbox_event_id) if outbox_event_id else None,
                    "target_idempotency_key_hash": target_idempotency_key_hash,
                    "semantic_effect_hash": semantic_effect_hash,
                    "payload_hash": value.payload_hash,
                    "request_snapshot": value.canonical_mapping(),
                    "optimistic_version": value.optimistic_version,
                    "actor_user_id": value.actor_user_id,
                    "request_id": str(value.request_id),
                    "trace_id": value.trace_id,
                    "idempotency_key_hash": value.idempotency_key_hash,
                    "created_at": _database_datetime(value.created_at),
                    "updated_at": _database_datetime(value.created_at),
                }
            ),
            capability=capability,
        )

    def _insert_execution_outbox(
        self,
        project: object,
        value: ToolAssetExecutionRequest,
        *,
        event_id: UUID,
        target_idempotency_key_hash: str,
        semantic_effect_hash: str,
        capability: ToolAssetSupportWriteCapability,
    ) -> None:
        service_actor_user_id = self._service_actor_for_profile(project, value.profile)
        payload = {
            "schemaVersion": TOOL_ASSET_OUTBOX_SCHEMA_VERSION,
            "apiVersion": TOOL_ASSET_EXECUTION_API_VERSION,
            "eventType": TOOL_ASSET_REQUEST_EVENT_TYPE,
            "request": value.canonical_mapping(),
            "targetIdempotencyKeyHash": target_idempotency_key_hash,
            "semanticEffectHash": semantic_effect_hash,
        }
        payload_hash = canonical_hash(payload)
        event_hash = canonical_hash(
            {
                "schemaVersion": TOOL_ASSET_OUTBOX_SCHEMA_VERSION,
                "apiVersion": TOOL_ASSET_EXECUTION_API_VERSION,
                "eventId": str(event_id),
                "eventType": TOOL_ASSET_REQUEST_EVENT_TYPE,
                "globalId": str(value.global_id),
                "objectVersion": 1,
                "tenantId": str(project.tenant_id),
                "projectGlobalId": str(project.global_id),
                "toolAssetRequestGlobalId": str(value.global_id),
                "toolingSetGlobalId": str(value.source.tooling_set_global_id),
                "operation": value.operation.value,
                "profileId": value.profile.profile_id,
                "profileVersion": value.profile.profile_version,
                "profileSnapshotHash": value.profile.snapshot_hash,
                "sourceStreamKeyHash": value.source.source_stream_key_hash,
                "sourceHash": value.source.source_hash,
                "mappingExpectationHash": canonical_hash(value.mapping_expectation.canonical_mapping()),
                "actorUserId": value.actor_user_id,
                "serviceActorUserId": service_actor_user_id,
                "requestId": str(value.request_id),
                "traceId": value.trace_id,
                "idempotencyKeyHash": value.idempotency_key_hash,
                "targetIdempotencyKeyHash": target_idempotency_key_hash,
                "semanticEffectHash": semantic_effect_hash,
                "payloadHash": payload_hash,
            }
        )
        profile = value.profile
        insert_tool_asset_support_document(
            frappe.get_doc(
                {
                    "doctype": "NPI Outbox Message",
                    "event_id": str(event_id),
                    "event_type": TOOL_ASSET_REQUEST_EVENT_TYPE,
                    "global_id": str(value.global_id),
                    "object_version": 1,
                    "trace_id": value.trace_id,
                    "payload_hash": payload_hash,
                    "payload": payload,
                    "state": "pending",
                    "attempt_count": 0,
                    "schema_version": TOOL_ASSET_OUTBOX_SCHEMA_VERSION,
                    "operation": value.operation.value,
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "tool_asset_request_global_id": str(value.global_id),
                    "tooling_set_global_id": str(value.source.tooling_set_global_id),
                    "profile_id": profile.profile_id,
                    "profile_version": profile.profile_version,
                    "profile_snapshot_hash": profile.snapshot_hash,
                    "source_stream_key_hash": value.source.source_stream_key_hash,
                    "source_hash": value.source.source_hash,
                    "tool_asset_mapping_expectation_hash": canonical_hash(value.mapping_expectation.canonical_mapping()),
                    "actor_user_id": value.actor_user_id,
                    "service_actor_user_id": service_actor_user_id,
                    "request_id": str(value.request_id),
                    "idempotency_key_hash": value.idempotency_key_hash,
                    "target_idempotency_key_hash": target_idempotency_key_hash,
                    "semantic_effect_hash": semantic_effect_hash,
                    "event_snapshot_hash": event_hash,
                    "adapter_boundary_crossed": 0,
                    "disposition": "ready",
                }
            ),
            capability=capability,
        )

    def _service_actor_for_profile(
        self,
        project: object,
        reference: object,
    ) -> str:
        profile = self._required_execution_profile(project)
        if profile.reference != reference:
            raise ToolAssetExecutionProfileUnavailable()
        return profile.service_actor_user_id

    def _insert_execution_receipt(
        self,
        project: object,
        value: ToolAssetExecutionRequest,
        *,
        receipt_key: str,
        command_hash: str,
        response: Mapping[str, object],
        capability: ToolAssetSupportWriteCapability,
    ) -> None:
        try:
            insert_tool_asset_support_document(
                frappe.get_doc(
                    {
                        "doctype": "NPI Tool Asset Command Idempotency",
                        "global_id": str(self._new_uuid()),
                        "schema_version": TOOL_ASSET_EXECUTION_SCHEMA_VERSION,
                        "receipt_key": receipt_key,
                        "tenant_id": str(project.tenant_id),
                        "project_global_id": str(project.global_id),
                        "actor_user_id": self.actor.casefold(),
                        "operation": value.operation.value,
                        "idempotency_key_hash": value.idempotency_key_hash,
                        "payload_hash": command_hash,
                        "source_stream_key_hash": value.source.source_stream_key_hash,
                        "profile_snapshot_hash": value.profile.snapshot_hash,
                        "mapping_expectation_hash": canonical_hash(value.mapping_expectation.canonical_mapping()),
                        "request_global_id": str(value.global_id),
                        "response_payload": dict(response),
                        "response_hash": canonical_hash(response),
                        "sealed": 1,
                        "created_at": _database_datetime(value.created_at),
                        "updated_at": _database_datetime(value.created_at),
                    }
                ),
                capability=capability,
            )
        except (frappe.DuplicateEntryError, frappe.UniqueValidationError) as error:
            raise ToolAssetExecutionIdempotencyConflict() from error

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


def _datetime_value(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise RuntimeError("The Tool Asset mapping timestamp is invalid.")
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
