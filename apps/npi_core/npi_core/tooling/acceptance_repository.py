from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import frappe

from npi_core.tooling.acceptance_domain import (
    ToolingAcceptanceChecklistItem,
    ToolingAcceptanceEvidenceRevision,
    ToolingAcceptanceFileEvidence,
    ToolingAssetActionEvidence,
    ToolingRepairEvidence,
    ToolingSpareRecommendation,
    acceptance_revision_from_snapshot,
    validate_acceptance_successor,
)
from npi_core.tooling.domain import ToolingReferenceUnavailable, ToolingVersionConflict
from npi_core.tooling.frappe_validation import tooling_command_write


_MAX_ACCEPTANCE_REVISIONS = 500


@dataclass(frozen=True, slots=True)
class ToolingAcceptanceCommandOutcome:
    response: dict[str, Any]
    replayed: bool = False


class ToolingAcceptanceRepositoryMixin:
    """Project-first persistence for immutable acceptance-evidence revisions."""

    def tooling_acceptance_context(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None or self._master_for_project(project, tooling_master_id) is None:
            return None
        create = self._is_internal_system_manager()
        return {
            "projectGlobalId": str(project.global_id),
            "toolingMasterGlobalId": str(tooling_master_id),
            "permissions": {
                "view": True,
                "recordEvidence": create,
                "prepareMockAssetRequest": create,
                "approveAcceptance": False,
                "dispatchAssetRequest": False,
                "editErpProjection": False,
            },
            "businessApproval": {
                "state": "unavailable",
                "reasonCode": "tooling_acceptance_policy_unavailable",
            },
            "acceptanceRevisions": [
                value.public_dict()
                for value in self._acceptance_revisions(project, tooling_master_id)
            ],
            "assetRequests": [],
            "assetProjection": {
                "sourceSystem": "ERPNEXT",
                "editableIn": "ERPNEXT",
                "state": "unavailable",
                "reasonCode": "erp_asset_projection_unavailable",
                "mappingCardinality": "zero_or_one_per_physical_set",
            },
        }

    def create_tooling_acceptance_evidence_revision(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        *,
        idempotency_key_hash: str,
        acceptance_id: UUID | None,
        expected_version: int | None,
        tooling_set_id: UUID,
        tooling_set_snapshot_hash: str,
        binding_id: UUID,
        binding_snapshot_hash: str,
        tooling_revision_id: UUID,
        tooling_revision_number: int,
        tooling_revision_snapshot_hash: str,
        checklist: Sequence[Mapping[str, object]],
        asset_actions: Sequence[Mapping[str, object]],
        spare_recommendations: Sequence[Mapping[str, object]],
        repairs: Sequence[Mapping[str, object]],
        reason: str,
    ) -> ToolingAcceptanceCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "toolingMasterGlobalId": str(tooling_master_id),
            "acceptanceGlobalId": str(acceptance_id) if acceptance_id else None,
            "expectedVersion": expected_version,
            "toolingSetGlobalId": str(tooling_set_id),
            "toolingSetSnapshotHash": tooling_set_snapshot_hash,
            "setRevisionBindingGlobalId": str(binding_id),
            "setRevisionBindingSnapshotHash": binding_snapshot_hash,
            "toolingRevisionGlobalId": str(tooling_revision_id),
            "toolingRevisionNumber": tooling_revision_number,
            "toolingRevisionSnapshotHash": tooling_revision_snapshot_hash,
            "checklist": _command_payload(checklist),
            "assetActions": _command_payload(asset_actions),
            "spareRecommendations": _command_payload(spare_recommendations),
            "repairs": _command_payload(repairs),
            "reason": reason,
        }
        command_context = self._command_context(
            project,
            operation="tooling_acceptance_evidence.create",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(command_context, dict):
            return ToolingAcceptanceCommandOutcome(command_context, replayed=True)
        receipt_key, payload_hash = command_context

        master = self._master_for_project(project, tooling_master_id)
        tooling_set = self._tooling_set_for_project(
            project,
            tooling_master_id,
            tooling_set_id,
        )
        if master is None:
            raise ToolingReferenceUnavailable()
        if tooling_set is None or tooling_set.snapshot_hash != tooling_set_snapshot_hash:
            raise ToolingReferenceUnavailable()
        binding = self._binding_for_set(project, tooling_set)
        if (
            binding is None
            or binding.global_id != binding_id
            or binding.snapshot_hash != binding_snapshot_hash
            or binding.tooling_revision_global_id != tooling_revision_id
        ):
            raise ToolingReferenceUnavailable()
        tooling_revision = self._tooling_revision_for_project(
            project,
            tooling_revision_id,
            tooling_master_id=tooling_master_id,
        )
        if (
            tooling_revision is None
            or tooling_revision.revision_number != tooling_revision_number
            or tooling_revision.snapshot_hash != tooling_revision_snapshot_hash
        ):
            raise ToolingReferenceUnavailable()
        stable_id, predecessor = self._acceptance_predecessor(
            project,
            tooling_master_id,
            acceptance_id,
            expected_version,
        )
        exact_checklist = tuple(
            self._acceptance_checklist_item(project, item) for item in checklist
        )
        exact_actions = tuple(
            self._acceptance_asset_action(project, item) for item in asset_actions
        )
        exact_spares = tuple(
            ToolingSpareRecommendation(
                global_id=self._new_uuid(),
                recommendation_key=str(item["recommendation_key"]),
                kind=item["kind"],
                description=str(item["description"]),
                recommended_minimum_quantity=str(item["recommended_minimum_quantity"]),
                unit=str(item["unit"]),
                supplier_source_system=item["supplier_source_system"],
                supplier_source_object_id=item["supplier_source_object_id"],
            )
            for item in spare_recommendations
        )
        exact_repairs = tuple(
            self._acceptance_repair(project, item) for item in repairs
        )
        now = self._now()
        value = ToolingAcceptanceEvidenceRevision(
            global_id=self._new_uuid(),
            acceptance_global_id=stable_id,
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            tooling_master_global_id=tooling_master_id,
            tooling_master_snapshot_hash=str(master.snapshot_hash),
            tooling_set_global_id=tooling_set.global_id,
            tooling_set_snapshot_hash=tooling_set.snapshot_hash,
            tooling_requirement_kind=tooling_set.requirement_kind,
            set_revision_binding_global_id=binding.global_id,
            set_revision_binding_snapshot_hash=binding.snapshot_hash,
            tooling_revision_global_id=tooling_revision.global_id,
            tooling_revision_number=tooling_revision.revision_number,
            tooling_revision_snapshot_hash=tooling_revision.snapshot_hash,
            acceptance_version=(
                1 if predecessor is None else predecessor.acceptance_version + 1
            ),
            predecessor_global_id=predecessor.global_id if predecessor else None,
            predecessor_snapshot_hash=predecessor.snapshot_hash if predecessor else None,
            checklist=exact_checklist,
            asset_actions=exact_actions,
            spare_recommendations=exact_spares,
            repairs=exact_repairs,
            reason=reason,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        if predecessor is not None:
            validate_acceptance_successor(predecessor, value)
        response = {"acceptanceEvidence": value.public_dict()}
        with tooling_command_write():
            receipt = self._insert_receipt(
                project,
                receipt_key=receipt_key,
                operation="tooling_acceptance_evidence.create",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._insert_acceptance_revision(value)
            self._append_audit(
                operation="tooling_acceptance_evidence.create",
                global_id=value.global_id,
                object_version=value.acceptance_version,
                summary={
                    "acceptanceGlobalId": str(value.acceptance_global_id),
                    "toolingSetGlobalId": str(value.tooling_set_global_id),
                    "snapshotHash": value.snapshot_hash,
                    "businessApprovalState": "unavailable",
                },
            )
            self._seal_receipt(
                receipt,
                target_type="tooling_acceptance_evidence_revision",
                target_id=value.global_id,
                response=response,
                now=now,
            )
        return ToolingAcceptanceCommandOutcome(response)

    def _acceptance_revisions(
        self,
        project: object,
        tooling_master_id: UUID,
        *,
        acceptance_id: UUID | None = None,
    ) -> tuple[ToolingAcceptanceEvidenceRevision, ...]:
        filters = {
            "tenant_id": str(project.tenant_id),
            "project_global_id": str(project.global_id),
            "tooling_master_global_id": str(tooling_master_id),
        }
        if acceptance_id is not None:
            filters["acceptance_global_id"] = str(acceptance_id)
        rows = self._bounded_documents(
            "NPI Tooling Acceptance Evidence Revision",
            filters=filters,
            maximum=_MAX_ACCEPTANCE_REVISIONS,
        )
        values = tuple(
            acceptance_revision_from_snapshot(_json_object(row.acceptance_snapshot))
            for row in rows
        )
        grouped: dict[UUID, list[ToolingAcceptanceEvidenceRevision]] = {}
        for value in values:
            grouped.setdefault(value.acceptance_global_id, []).append(value)
        for chain in grouped.values():
            chain.sort(key=lambda item: item.acceptance_version)
            for index, value in enumerate(chain):
                if value.acceptance_version != index + 1:
                    raise RuntimeError("The acceptance-evidence chain is not contiguous.")
                if index:
                    validate_acceptance_successor(chain[index - 1], value)
        return tuple(
            sorted(
                values,
                key=lambda item: (str(item.acceptance_global_id), item.acceptance_version),
            )
        )

    def _acceptance_revision_for_project(
        self,
        project: object,
        tooling_master_id: UUID,
        revision_id: UUID,
    ) -> ToolingAcceptanceEvidenceRevision | None:
        try:
            row = frappe.get_doc(
                "NPI Tooling Acceptance Evidence Revision",
                str(revision_id),
            )
        except frappe.DoesNotExistError:
            return None
        if any(
            (
                str(row.global_id) != str(revision_id),
                str(row.tenant_id) != str(project.tenant_id),
                str(row.project_global_id) != str(project.global_id),
                str(row.tooling_master_global_id) != str(tooling_master_id),
            )
        ):
            return None
        return acceptance_revision_from_snapshot(_json_object(row.acceptance_snapshot))

    def _acceptance_predecessor(
        self,
        project: object,
        tooling_master_id: UUID,
        acceptance_id: UUID | None,
        expected_version: int | None,
    ) -> tuple[UUID, ToolingAcceptanceEvidenceRevision | None]:
        if acceptance_id is None:
            if expected_version is not None:
                raise ToolingVersionConflict()
            return self._new_uuid(), None
        chain = self._acceptance_revisions(
            project,
            tooling_master_id,
            acceptance_id=acceptance_id,
        )
        if not chain or expected_version != chain[-1].acceptance_version:
            raise ToolingVersionConflict()
        return acceptance_id, chain[-1]

    def _acceptance_file_evidence(
        self,
        project: object,
        supplied: Mapping[str, object],
    ) -> ToolingAcceptanceFileEvidence:
        row = self._file_revision_for_project(project, supplied["file_revision_id"])
        if row is None or any(
            (
                int(row.optimistic_version) != supplied["file_optimistic_version"],
                str(row.frappe_content_hash) != supplied["frappe_content_hash"],
                str(row.sha256) != supplied["sha256"],
            )
        ):
            raise ToolingReferenceUnavailable()
        return ToolingAcceptanceFileEvidence(
            global_id=self._new_uuid(),
            role=supplied["role"],
            file_revision_global_id=UUID(str(row.global_id)),
            file_optimistic_version=int(row.optimistic_version),
            frappe_content_hash=str(row.frappe_content_hash),
            file_name=str(row.file_name),
            mime_type=str(row.mime_type),
            size_bytes=int(row.size_bytes),
            sha256=str(row.sha256),
        )

    def _acceptance_checklist_item(
        self,
        project: object,
        supplied: Mapping[str, object],
    ) -> ToolingAcceptanceChecklistItem:
        return ToolingAcceptanceChecklistItem(
            global_id=self._new_uuid(),
            category=supplied["category"],
            requirement_key=str(supplied["requirement_key"]),
            requirement_statement=str(supplied["requirement_statement"]),
            disposition=supplied["disposition"],
            responsible_member=self._exact_engineering_member(
                project,
                supplied["responsible_member"],
            ),
            evidence=tuple(
                self._acceptance_file_evidence(project, item)
                for item in supplied["evidence"]
            ),
            note=supplied["note"],
        )

    def _acceptance_asset_action(
        self,
        project: object,
        supplied: Mapping[str, object],
    ) -> ToolingAssetActionEvidence:
        return ToolingAssetActionEvidence(
            global_id=self._new_uuid(),
            action_kind=supplied["action_kind"],
            reason=str(supplied["reason"]),
            approval_reference=str(supplied["approval_reference"]),
            proposed_effective_date=supplied["proposed_effective_date"],
            evidence=tuple(
                self._acceptance_file_evidence(project, item)
                for item in supplied["evidence"]
            ),
        )

    def _acceptance_repair(
        self,
        project: object,
        supplied: Mapping[str, object],
    ) -> ToolingRepairEvidence:
        member = self._exact_engineering_member(project, supplied["responsible_member"])
        if member is None:
            raise ToolingReferenceUnavailable()
        return ToolingRepairEvidence(
            global_id=self._new_uuid(),
            authorization_reference=str(supplied["authorization_reference"]),
            quote_reference=supplied["quote_reference"],
            quote_currency=supplied["quote_currency"],
            quote_amount=supplied["quote_amount"],
            responsible_member=member,
            downtime_impact_hours=str(supplied["downtime_impact_hours"]),
            detail=str(supplied["detail"]),
            customer_authorization_evidence=tuple(
                self._acceptance_file_evidence(project, item)
                for item in supplied["customer_authorization_evidence"]
            ),
            verification_evidence=tuple(
                self._acceptance_file_evidence(project, item)
                for item in supplied["verification_evidence"]
            ),
        )

    @staticmethod
    def _insert_acceptance_revision(
        value: ToolingAcceptanceEvidenceRevision,
    ) -> object:
        snapshot = value.snapshot_payload()
        return frappe.get_doc(
            {
                "doctype": "NPI Tooling Acceptance Evidence Revision",
                "global_id": str(value.global_id),
                "acceptance_global_id": str(value.acceptance_global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "tooling_master": str(value.tooling_master_global_id),
                "tooling_master_global_id": str(value.tooling_master_global_id),
                "tooling_master_snapshot_hash": value.tooling_master_snapshot_hash,
                "tooling_set": str(value.tooling_set_global_id),
                "tooling_set_global_id": str(value.tooling_set_global_id),
                "tooling_set_snapshot_hash": value.tooling_set_snapshot_hash,
                "tooling_requirement_kind": value.tooling_requirement_kind.value,
                "set_revision_binding": str(value.set_revision_binding_global_id),
                "set_revision_binding_global_id": str(value.set_revision_binding_global_id),
                "set_revision_binding_snapshot_hash": value.set_revision_binding_snapshot_hash,
                "tooling_revision": str(value.tooling_revision_global_id),
                "tooling_revision_global_id": str(value.tooling_revision_global_id),
                "tooling_revision_number": value.tooling_revision_number,
                "tooling_revision_snapshot_hash": value.tooling_revision_snapshot_hash,
                "acceptance_version": value.acceptance_version,
                "predecessor_global_id": (
                    str(value.predecessor_global_id) if value.predecessor_global_id else None
                ),
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "checklist_snapshot": _canonical_json(snapshot["checklist"]),
                "asset_action_snapshot": _canonical_json(snapshot["assetActions"]),
                "spare_recommendation_snapshot": _canonical_json(snapshot["spareRecommendations"]),
                "repair_snapshot": _canonical_json(snapshot["repairs"]),
                "version_key_hash": value.version_key_hash,
                "acceptance_snapshot": _canonical_json(snapshot),
                "snapshot_hash": value.snapshot_hash,
                "reason": value.reason,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
            }
        ).insert()


def _command_payload(value: object) -> object:
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "snapshot_payload"):
        return value.snapshot_payload()
    if isinstance(value, Mapping):
        return {str(key): _command_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_command_payload(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_object(value: object) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise RuntimeError("The acceptance-evidence snapshot is invalid.")
    return value


def _database_datetime(value: datetime) -> str:
    return value.astimezone(UTC).replace(tzinfo=None).isoformat(
        sep=" ",
        timespec="microseconds",
    )
