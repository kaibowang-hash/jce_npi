from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID

import frappe
from frappe import _

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.tooling.domain import (
    ToolingReferenceUnavailable,
    ToolingSet,
    ToolingVersionConflict,
    sha256_json,
)
from npi_core.tooling.frappe_validation import tooling_command_write
from npi_core.tooling.revision_domain import (
    CavityMapping,
    DocumentRevisionReference,
    ExternalIdentity,
    InsertApplicability,
    InsertValidationState,
    PartControlledSpecification,
    PartSpecificationItem,
    ToolingProcessChainRevision,
    ToolingProcessStep,
    ToolingRevision,
    ToolingSetRevisionBinding,
    part_controlled_specification_from_snapshot,
    process_chain_revision_from_snapshot,
    set_revision_binding_from_snapshot,
    tooling_revision_from_snapshot,
    validate_process_chain_successor,
    validate_tooling_revision_successor,
)


_MAX_REVISIONS = 200
_MAX_PART_SPECIFICATIONS = 2
_MAX_PROCESS_CHAIN_REVISIONS = 500
_MAX_BINDINGS = 2


@dataclass(frozen=True, slots=True)
class RevisionCommandOutcome:
    response: dict[str, Any]
    replayed: bool = False


class ToolingRevisionRepositoryMixin:
    """Project-first repository behavior for the bounded P6-03 slice."""

    def tooling_revisions(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        if self._master_for_project(project, tooling_master_id) is None:
            return None
        return self._tooling_revision_collection(project, tooling_master_id)

    def tooling_revision_detail(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        tooling_revision_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        if self._master_for_project(project, tooling_master_id) is None:
            return None
        revision = self._tooling_revision_for_project(
            project,
            tooling_revision_id,
            tooling_master_id=tooling_master_id,
        )
        if revision is None:
            return None
        return self._tooling_revision_detail_response(project, revision)

    def part_controlled_specification(
        self,
        project_id: UUID,
        part_id: UUID,
        part_revision_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        revision = self._part_revision_for_project(
            project,
            part_revision_id,
            require_current=True,
        )
        if revision is None or revision.part_global_id != part_id:
            return None
        return self._part_specification_context(project, revision)

    def tooling_process_chains(self, project_id: UUID) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        return self._process_chain_collection(project)

    def tooling_process_chain_detail(
        self,
        project_id: UUID,
        process_chain_revision_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        value = self._process_chain_revision_for_project(
            project,
            process_chain_revision_id,
        )
        return self._process_chain_response(value) if value is not None else None

    def create_tooling_revision(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_version: int | None,
        revision_label: str,
        specification: object,
        cavities: Sequence[Mapping[str, object]],
        inserts: Sequence[Mapping[str, object]],
        external_identities: Sequence[Mapping[str, object]],
        design_document_revisions: Sequence[DocumentRevisionReference],
        reason: str,
    ) -> RevisionCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "toolingMasterGlobalId": str(tooling_master_id),
            "expectedVersion": expected_version,
            "revisionLabel": revision_label,
            "specification": specification.snapshot_payload(),
            "cavities": [_input_payload(value) for value in cavities],
            "inserts": [_input_payload(value) for value in inserts],
            "externalIdentities": [
                _input_payload(value) for value in external_identities
            ],
            "designDocumentRevisions": [
                value.snapshot_payload() for value in design_document_revisions
            ],
            "reason": reason,
        }
        context = self._command_context(
            project,
            operation="tooling_revision.create",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(context, dict):
            return RevisionCommandOutcome(context, replayed=True)
        receipt_key, payload_hash = context
        if self._master_for_project(project, tooling_master_id) is None:
            raise ToolingReferenceUnavailable()
        current = self._tooling_revisions_for_master(project, tooling_master_id)
        if (not current and expected_version is not None) or (
            current and expected_version != current[-1].revision_number
        ):
            raise ToolingVersionConflict()
        now = self._now()
        predecessor = current[-1] if current else None
        revision = ToolingRevision(
            global_id=self._new_uuid(),
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            tooling_master_global_id=tooling_master_id,
            revision_number=1 if predecessor is None else predecessor.revision_number + 1,
            revision_label=revision_label,
            predecessor_global_id=(predecessor.global_id if predecessor else None),
            predecessor_snapshot_hash=(predecessor.snapshot_hash if predecessor else None),
            specification=specification,
            cavities=tuple(
                self._cavity_value(project, tooling_master_id, value)
                for value in cavities
            ),
            inserts=tuple(
                self._insert_value(project, tooling_master_id, value, now)
                for value in inserts
            ),
            external_identities=tuple(
                self._external_identity_value(value)
                for value in external_identities
            ),
            design_document_revisions=tuple(
                self._document_revision_reference(project, value)
                for value in design_document_revisions
            ),
            reason=reason,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        if predecessor is not None:
            validate_tooling_revision_successor(predecessor, revision)
        with tooling_command_write():
            receipt = self._insert_receipt(
                project,
                receipt_key=receipt_key,
                operation="tooling_revision.create",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._insert_tooling_revision(revision)
            self._append_audit(
                operation="tooling_revision.create",
                global_id=revision.global_id,
                object_version=revision.revision_number,
                summary={
                    "projectGlobalId": str(project_id),
                    "toolingMasterGlobalId": str(tooling_master_id),
                    "predecessorGlobalId": (
                        str(predecessor.global_id) if predecessor else None
                    ),
                    "snapshotHash": revision.snapshot_hash,
                    "requestId": self.request_id,
                },
            )
            response = self._tooling_revision_detail_response(project, revision)
            self._seal_receipt(
                receipt,
                target_type="tooling_revision",
                target_id=revision.global_id,
                response=response,
                now=now,
            )
        return RevisionCommandOutcome(response)

    def create_part_controlled_specification(
        self,
        project_id: UUID,
        part_id: UUID,
        part_revision_id: UUID,
        *,
        idempotency_key_hash: str,
        items: Sequence[Mapping[str, object]],
        external_identities: Sequence[Mapping[str, object]],
    ) -> RevisionCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "partGlobalId": str(part_id),
            "partRevisionGlobalId": str(part_revision_id),
            "items": [_input_payload(value) for value in items],
            "externalIdentities": [
                _input_payload(value) for value in external_identities
            ],
        }
        context = self._command_context(
            project,
            operation="part_controlled_specification.create",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(context, dict):
            return RevisionCommandOutcome(context, replayed=True)
        receipt_key, payload_hash = context
        revision = self._part_revision_for_project(
            project,
            part_revision_id,
            require_current=True,
        )
        if revision is None or revision.part_global_id != part_id:
            raise ToolingReferenceUnavailable()
        if self._part_specification_for_revision(project, part_revision_id) is not None:
            raise ToolingVersionConflict()
        now = self._now()
        specification = PartControlledSpecification(
            global_id=self._new_uuid(),
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            part_global_id=part_id,
            part_revision_global_id=part_revision_id,
            part_revision_snapshot_hash=revision.snapshot_hash,
            items=tuple(self._part_specification_item(value) for value in items),
            external_identities=tuple(
                self._external_identity_value(value)
                for value in external_identities
            ),
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        with tooling_command_write():
            receipt = self._insert_receipt(
                project,
                receipt_key=receipt_key,
                operation="part_controlled_specification.create",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._insert_part_controlled_specification(specification)
            self._append_audit(
                operation="part_controlled_specification.create",
                global_id=specification.global_id,
                object_version=revision.revision_number,
                summary={
                    "projectGlobalId": str(project_id),
                    "partGlobalId": str(part_id),
                    "partRevisionGlobalId": str(part_revision_id),
                    "snapshotHash": specification.snapshot_hash,
                    "requestId": self.request_id,
                },
            )
            response = self._part_specification_context(project, revision)
            self._seal_receipt(
                receipt,
                target_type="part_controlled_specification",
                target_id=specification.global_id,
                response=response,
                now=now,
            )
        return RevisionCommandOutcome(response)

    def create_tooling_process_chain_revision(
        self,
        project_id: UUID,
        *,
        idempotency_key_hash: str,
        process_chain_id: UUID | None,
        expected_version: int | None,
        steps: Sequence[Mapping[str, object]],
        reason: str,
    ) -> RevisionCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "processChainGlobalId": str(process_chain_id) if process_chain_id else None,
            "expectedVersion": expected_version,
            "steps": [_input_payload(value) for value in steps],
            "reason": reason,
        }
        context = self._command_context(
            project,
            operation="tooling_process_chain_revision.create",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(context, dict):
            return RevisionCommandOutcome(context, replayed=True)
        receipt_key, payload_hash = context
        chain_id = process_chain_id or self._new_uuid()
        current = self._process_chain_revisions(project, chain_id)
        if (not current and (process_chain_id is not None or expected_version is not None)) or (
            current and expected_version != current[-1].chain_version
        ):
            raise ToolingVersionConflict()
        now = self._now()
        predecessor = current[-1] if current else None
        step_ids = {int(value["step_order"]): self._new_uuid() for value in steps}
        chain_steps = tuple(
            self._process_step_value(project, value, step_ids)
            for value in steps
        )
        chain = ToolingProcessChainRevision(
            global_id=self._new_uuid(),
            process_chain_global_id=chain_id,
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            chain_version=1 if predecessor is None else predecessor.chain_version + 1,
            predecessor_global_id=(predecessor.global_id if predecessor else None),
            predecessor_snapshot_hash=(predecessor.snapshot_hash if predecessor else None),
            steps=chain_steps,
            reason=reason,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        if predecessor is not None:
            validate_process_chain_successor(predecessor, chain)
        with tooling_command_write():
            receipt = self._insert_receipt(
                project,
                receipt_key=receipt_key,
                operation="tooling_process_chain_revision.create",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._insert_process_chain_revision(chain)
            self._append_audit(
                operation="tooling_process_chain_revision.create",
                global_id=chain.global_id,
                object_version=chain.chain_version,
                summary={
                    "projectGlobalId": str(project_id),
                    "processChainGlobalId": str(chain_id),
                    "predecessorGlobalId": (
                        str(predecessor.global_id) if predecessor else None
                    ),
                    "snapshotHash": chain.snapshot_hash,
                    "requestId": self.request_id,
                },
            )
            response = self._process_chain_response(chain)
            self._seal_receipt(
                receipt,
                target_type="tooling_process_chain_revision",
                target_id=chain.global_id,
                response=response,
                now=now,
            )
        return RevisionCommandOutcome(response)

    def create_tooling_set_revision_binding(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        tooling_set_id: UUID,
        *,
        idempotency_key_hash: str,
        tooling_revision_id: UUID,
        reason: str,
    ) -> RevisionCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "toolingMasterGlobalId": str(tooling_master_id),
            "toolingSetGlobalId": str(tooling_set_id),
            "toolingRevisionGlobalId": str(tooling_revision_id),
            "reason": reason,
        }
        context = self._command_context(
            project,
            operation="tooling_set_revision_binding.create",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(context, dict):
            return RevisionCommandOutcome(context, replayed=True)
        receipt_key, payload_hash = context
        if self._master_for_project(project, tooling_master_id) is None:
            raise ToolingReferenceUnavailable()
        tooling_set = self._tooling_set_for_project(
            project,
            tooling_master_id,
            tooling_set_id,
        )
        revision = self._tooling_revision_for_project(
            project,
            tooling_revision_id,
            tooling_master_id=tooling_master_id,
        )
        if tooling_set is None or revision is None:
            raise ToolingReferenceUnavailable()
        if self._binding_for_set(project, tooling_set) is not None:
            raise ToolingVersionConflict()
        now = self._now()
        binding = ToolingSetRevisionBinding(
            global_id=self._new_uuid(),
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            tooling_master_global_id=tooling_master_id,
            tooling_set_global_id=tooling_set_id,
            tooling_set_snapshot_hash=tooling_set.snapshot_hash,
            tooling_revision_global_id=tooling_revision_id,
            tooling_revision_snapshot_hash=revision.snapshot_hash,
            reason=reason,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        with tooling_command_write():
            receipt = self._insert_receipt(
                project,
                receipt_key=receipt_key,
                operation="tooling_set_revision_binding.create",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._insert_set_revision_binding(binding)
            self._append_audit(
                operation="tooling_set_revision_binding.create",
                global_id=binding.global_id,
                object_version=1,
                summary={
                    "projectGlobalId": str(project_id),
                    "toolingMasterGlobalId": str(tooling_master_id),
                    "toolingSetGlobalId": str(tooling_set_id),
                    "toolingRevisionGlobalId": str(tooling_revision_id),
                    "snapshotHash": binding.snapshot_hash,
                    "requestId": self.request_id,
                },
            )
            response = self._tooling_set_detail(project, tooling_set)
            self._seal_receipt(
                receipt,
                target_type="tooling_set_revision_binding",
                target_id=binding.global_id,
                response=response,
                now=now,
            )
        return RevisionCommandOutcome(response)

    def _tooling_revision_collection(
        self,
        project: object,
        tooling_master_id: UUID,
    ) -> dict[str, Any]:
        revisions = self._tooling_revisions_for_master(project, tooling_master_id)
        return {
            "projectGlobalId": str(project.global_id),
            "toolingMasterGlobalId": str(tooling_master_id),
            "permissions": self._revision_permissions(),
            "lifecycle": self._unavailable("lifecycle_policy_unavailable"),
            "supplier": self._unavailable("formal_supplier_unavailable"),
            "erpLocationAndAsset": self._unavailable("erp_projection_unavailable"),
            "combinedTrial": self._unavailable("combined_trial_not_delivered"),
            "items": [self._tooling_revision_response(value) for value in revisions],
        }

    def _tooling_revision_detail_response(
        self,
        project: object,
        revision: ToolingRevision,
    ) -> dict[str, Any]:
        return {
            "projectGlobalId": str(project.global_id),
            "permissions": self._revision_permissions(),
            "lifecycle": self._unavailable("lifecycle_policy_unavailable"),
            "supplier": self._unavailable("formal_supplier_unavailable"),
            "erpLocationAndAsset": self._unavailable("erp_projection_unavailable"),
            "combinedTrial": self._unavailable("combined_trial_not_delivered"),
            "revision": self._tooling_revision_response(revision),
        }

    def _part_specification_context(self, project: object, revision: object) -> dict[str, Any]:
        value = self._part_specification_for_revision(project, revision.global_id)
        return {
            "projectGlobalId": str(project.global_id),
            "partGlobalId": str(revision.part_global_id),
            "partRevision": self._revision_response(revision),
            "permissions": self._revision_permissions(),
            "automaticImpact": self._unavailable("automatic_impact_not_delivered"),
            "controlledSpecification": (
                self._part_specification_response(value)
                if value is not None
                else self._unavailable("controlled_part_specification_not_recorded")
            ),
        }

    def _process_chain_collection(self, project: object) -> dict[str, Any]:
        return {
            "projectGlobalId": str(project.global_id),
            "permissions": self._revision_permissions(),
            "combinedTrial": self._unavailable("combined_trial_not_delivered"),
            "items": [
                self._process_chain_response(value)
                for value in self._process_chain_revisions(project)
            ],
        }

    def _tooling_revisions_for_master(
        self,
        project: object,
        tooling_master_id: UUID,
    ) -> tuple[ToolingRevision, ...]:
        rows = self._bounded_documents(
            "NPI Tooling Revision",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "tooling_master_global_id": str(tooling_master_id),
            },
            maximum=_MAX_REVISIONS,
        )
        result = tuple(
            sorted(
                (tooling_revision_from_snapshot(_json_object(row.revision_snapshot)) for row in rows),
                key=lambda item: item.revision_number,
            )
        )
        for index, value in enumerate(result):
            if value.revision_number != index + 1:
                raise RuntimeError("The Tooling Revision chain is not contiguous.")
            if index:
                validate_tooling_revision_successor(result[index - 1], value)
        return result

    def _tooling_revision_for_project(
        self,
        project: object,
        revision_id: UUID,
        *,
        tooling_master_id: UUID | None = None,
    ) -> ToolingRevision | None:
        row = _optional_doc("NPI Tooling Revision", str(revision_id))
        if row is None or any(
            (
                str(row.global_id) != str(revision_id),
                str(row.tenant_id) != str(project.tenant_id),
                str(row.project_global_id) != str(project.global_id),
                tooling_master_id is not None
                and str(row.tooling_master_global_id) != str(tooling_master_id),
            )
        ):
            return None
        return tooling_revision_from_snapshot(_json_object(row.revision_snapshot))

    def _part_specification_for_revision(
        self,
        project: object,
        part_revision_id: UUID,
    ) -> PartControlledSpecification | None:
        rows = self._bounded_documents(
            "NPI Part Controlled Specification",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "part_revision_global_id": str(part_revision_id),
            },
            maximum=_MAX_PART_SPECIFICATIONS,
        )
        if len(rows) > 1:
            raise RuntimeError("A Part Revision has multiple controlled specifications.")
        return (
            part_controlled_specification_from_snapshot(
                _json_object(rows[0].specification_snapshot)
            )
            if rows
            else None
        )

    def _process_chain_revisions(
        self,
        project: object,
        process_chain_id: UUID | None = None,
    ) -> tuple[ToolingProcessChainRevision, ...]:
        filters = {
            "tenant_id": str(project.tenant_id),
            "project_global_id": str(project.global_id),
        }
        if process_chain_id is not None:
            filters["process_chain_global_id"] = str(process_chain_id)
        rows = self._bounded_documents(
            "NPI Tooling Process Chain Revision",
            filters=filters,
            maximum=_MAX_PROCESS_CHAIN_REVISIONS,
        )
        values = tuple(
            process_chain_revision_from_snapshot(_json_object(row.chain_snapshot))
            for row in rows
        )
        if process_chain_id is not None:
            ordered = tuple(sorted(values, key=lambda item: item.chain_version))
            for index, value in enumerate(ordered):
                if value.chain_version != index + 1:
                    raise RuntimeError("The Process Chain version is not contiguous.")
                if index:
                    validate_process_chain_successor(ordered[index - 1], value)
            return ordered
        return tuple(
            sorted(
                values,
                key=lambda item: (str(item.process_chain_global_id), item.chain_version),
            )
        )

    def _process_chain_revision_for_project(
        self,
        project: object,
        revision_id: UUID,
    ) -> ToolingProcessChainRevision | None:
        row = _optional_doc("NPI Tooling Process Chain Revision", str(revision_id))
        if row is None or any(
            (
                str(row.global_id) != str(revision_id),
                str(row.tenant_id) != str(project.tenant_id),
                str(row.project_global_id) != str(project.global_id),
            )
        ):
            return None
        return process_chain_revision_from_snapshot(_json_object(row.chain_snapshot))

    def _binding_for_set(
        self,
        project: object,
        tooling_set: ToolingSet,
    ) -> ToolingSetRevisionBinding | None:
        rows = self._bounded_documents(
            "NPI Tooling Set Revision Binding",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "tooling_master_global_id": str(tooling_set.tooling_master_global_id),
                "tooling_set_global_id": str(tooling_set.global_id),
            },
            maximum=_MAX_BINDINGS,
        )
        if len(rows) > 1:
            raise RuntimeError("A Tooling Set has multiple source bindings.")
        return (
            set_revision_binding_from_snapshot(_json_object(rows[0].binding_snapshot))
            if rows
            else None
        )

    def _cavity_value(
        self,
        project: object,
        tooling_master_id: UUID,
        value: Mapping[str, object],
    ) -> CavityMapping:
        applicability = self._current_effective_applicability(
            project,
            tooling_master_id,
            value["tooling_applicability_id"],
        )
        return CavityMapping(
            global_id=self._new_uuid(),
            cavity_identifier=value["cavity_identifier"],
            tooling_applicability_global_id=applicability.global_id,
            part_revision_global_id=applicability.part_revision_global_id,
            structural_state=value["structural_state"],
        )

    def _insert_value(
        self,
        project: object,
        tooling_master_id: UUID,
        value: Mapping[str, object],
        now: datetime,
    ) -> InsertApplicability:
        applicability = self._current_effective_applicability(
            project,
            tooling_master_id,
            value["tooling_applicability_id"],
        )
        model = value["model"]
        self._require_project_reference(project, model)
        validated = value["validation_state"] is InsertValidationState.VALIDATED
        return InsertApplicability(
            global_id=self._new_uuid(),
            insert_code=value["insert_code"],
            insert_version=value["insert_version"],
            tooling_applicability_global_id=applicability.global_id,
            part_revision_global_id=applicability.part_revision_global_id,
            model_source_system=(model["sourceSystem"] if model else None),
            model_source_object_id=(model["sourceObjectId"] if model else None),
            changeover_duration=value["changeover_duration"],
            validation_state=value["validation_state"],
            validated_by_user_id=self.actor if validated else None,
            validated_at=now if validated else None,
            validation_reason=value["validation_reason"] if validated else None,
        )

    def _current_effective_applicability(
        self,
        project: object,
        tooling_master_id: UUID,
        applicability_id: object,
    ):
        retained = self._applicabilities(project)
        matches = [
            value
            for value in retained
            if value.global_id == applicability_id
            and value.tooling_master_global_id == tooling_master_id
        ]
        if len(matches) != 1:
            raise ToolingReferenceUnavailable()
        value = matches[0]
        relationship = [
            item
            for item in retained
            if item.relationship_global_id == value.relationship_global_id
        ]
        if not relationship or max(item.applicability_version for item in relationship) != value.applicability_version:
            raise ToolingReferenceUnavailable()
        today = self._now().date()
        if value.effective_from > today or (
            value.effective_to is not None and today >= value.effective_to
        ):
            raise ToolingReferenceUnavailable()
        return value

    def _document_revision_reference(
        self,
        project: object,
        value: DocumentRevisionReference,
    ) -> DocumentRevisionReference:
        row = _optional_doc("NPI Document Revision", str(value.global_id))
        if row is None or any(
            (
                str(row.global_id) != str(value.global_id),
                str(row.tenant_id) != str(project.tenant_id),
                str(row.project_global_id) != str(project.global_id),
                str(row.snapshot_hash) != value.snapshot_hash,
            )
        ):
            raise ToolingReferenceUnavailable()
        return value

    def _process_step_value(
        self,
        project: object,
        value: Mapping[str, object],
        step_ids: Mapping[int, UUID],
    ) -> ToolingProcessStep:
        revision = self._tooling_revision_for_project(
            project,
            value["tooling_revision_id"],
        )
        if revision is None:
            raise ToolingReferenceUnavailable()
        part_revision_ids = (*value["input_part_revision_ids"], value["output_part_revision_id"])
        if any(
            self._part_revision_for_project(project, item, require_current=False) is None
            for item in part_revision_ids
        ):
            raise ToolingReferenceUnavailable()
        parent_order = value["parent_step_order"]
        if parent_order is not None and (
            parent_order not in step_ids or parent_order >= value["step_order"]
        ):
            raise RequestValidationFailed(
                [
                    {
                        "path": "parentStepOrder",
                        "message": _("The process parent must be an earlier step."),
                    }
                ]
            )
        return ToolingProcessStep(
            global_id=step_ids[value["step_order"]],
            step_order=value["step_order"],
            process_kind=value["process_kind"],
            tooling_revision_global_id=revision.global_id,
            tooling_revision_snapshot_hash=revision.snapshot_hash,
            input_part_revision_global_ids=value["input_part_revision_ids"],
            output_part_revision_global_id=value["output_part_revision_id"],
            parent_step_global_id=(step_ids[parent_order] if parent_order else None),
            machine_type=value["machine_type"],
            clamp_tonnage=value["clamp_tonnage"],
        )

    def _external_identity_value(self, value: Mapping[str, object]) -> ExternalIdentity:
        return ExternalIdentity(global_id=self._new_uuid(), **dict(value))

    def _part_specification_item(self, value: Mapping[str, object]) -> PartSpecificationItem:
        return PartSpecificationItem(global_id=self._new_uuid(), **dict(value))

    @staticmethod
    def _insert_tooling_revision(value: ToolingRevision) -> object:
        return frappe.get_doc(
            {
                "doctype": "NPI Tooling Revision",
                "global_id": str(value.global_id),
                "revision_key_hash": value.revision_key_hash,
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "tooling_master": str(value.tooling_master_global_id),
                "tooling_master_global_id": str(value.tooling_master_global_id),
                "revision_number": value.revision_number,
                "revision_label": value.revision_label,
                "predecessor_global_id": str(value.predecessor_global_id) if value.predecessor_global_id else None,
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "specification_snapshot": _canonical_json(value.specification.snapshot_payload()),
                "cavity_snapshot": _canonical_json([item.snapshot_payload() for item in value.cavities]),
                "insert_snapshot": _canonical_json([item.snapshot_payload() for item in value.inserts]),
                "external_identity_snapshot": _canonical_json([item.snapshot_payload() for item in value.external_identities]),
                "design_document_revision_snapshot": _canonical_json([item.snapshot_payload() for item in value.design_document_revisions]),
                "reason": value.reason,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "revision_snapshot": _canonical_json(value.snapshot_payload()),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    @staticmethod
    def _insert_part_controlled_specification(value: PartControlledSpecification) -> object:
        return frappe.get_doc(
            {
                "doctype": "NPI Part Controlled Specification",
                "global_id": str(value.global_id),
                "specification_key_hash": value.specification_key_hash,
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "engineering_part": str(value.part_global_id),
                "part_global_id": str(value.part_global_id),
                "engineering_part_revision": str(value.part_revision_global_id),
                "part_revision_global_id": str(value.part_revision_global_id),
                "part_revision_snapshot_hash": value.part_revision_snapshot_hash,
                "item_snapshot": _canonical_json([item.snapshot_payload() for item in value.items]),
                "external_identity_snapshot": _canonical_json([item.snapshot_payload() for item in value.external_identities]),
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "specification_snapshot": _canonical_json(value.snapshot_payload()),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    @staticmethod
    def _insert_process_chain_revision(value: ToolingProcessChainRevision) -> object:
        return frappe.get_doc(
            {
                "doctype": "NPI Tooling Process Chain Revision",
                "global_id": str(value.global_id),
                "process_chain_global_id": str(value.process_chain_global_id),
                "version_key_hash": value.version_key_hash,
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "chain_version": value.chain_version,
                "predecessor_global_id": str(value.predecessor_global_id) if value.predecessor_global_id else None,
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "step_snapshot": _canonical_json([item.snapshot_payload() for item in value.steps]),
                "reason": value.reason,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "chain_snapshot": _canonical_json(value.snapshot_payload()),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    @staticmethod
    def _insert_set_revision_binding(value: ToolingSetRevisionBinding) -> object:
        return frappe.get_doc(
            {
                "doctype": "NPI Tooling Set Revision Binding",
                "global_id": str(value.global_id),
                "binding_key_hash": value.binding_key_hash,
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "tooling_master_global_id": str(value.tooling_master_global_id),
                "tooling_set": str(value.tooling_set_global_id),
                "tooling_set_global_id": str(value.tooling_set_global_id),
                "tooling_set_snapshot_hash": value.tooling_set_snapshot_hash,
                "tooling_revision": str(value.tooling_revision_global_id),
                "tooling_revision_global_id": str(value.tooling_revision_global_id),
                "tooling_revision_snapshot_hash": value.tooling_revision_snapshot_hash,
                "reason": value.reason,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "binding_snapshot": _canonical_json(value.snapshot_payload()),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    def _revision_permissions(self) -> dict[str, bool]:
        create = self._is_internal_system_manager()
        return {
            "view": True,
            "createRevision": create,
            "createPartSpecification": create,
            "createProcessChain": create,
            "bindSetSource": create,
            "transitionLifecycle": False,
        }

    @staticmethod
    def _tooling_revision_response(value: ToolingRevision) -> dict[str, object]:
        return {
            "globalId": str(value.global_id),
            "toolingMasterGlobalId": str(value.tooling_master_global_id),
            "revisionNumber": value.revision_number,
            "revisionLabel": value.revision_label,
            "predecessorGlobalId": str(value.predecessor_global_id) if value.predecessor_global_id else None,
            "specification": value.specification.snapshot_payload(),
            "cavities": [item.snapshot_payload() for item in value.cavities],
            "inserts": [item.snapshot_payload() for item in value.inserts],
            "externalIdentities": [item.snapshot_payload() for item in value.external_identities],
            "designDocumentRevisions": [item.snapshot_payload() for item in value.design_document_revisions],
            "reason": value.reason,
            "snapshotHash": value.snapshot_hash,
        }

    @staticmethod
    def _part_specification_response(value: PartControlledSpecification) -> dict[str, object]:
        return {
            "globalId": str(value.global_id),
            "partGlobalId": str(value.part_global_id),
            "partRevisionGlobalId": str(value.part_revision_global_id),
            "partRevisionSnapshotHash": value.part_revision_snapshot_hash,
            "items": [item.snapshot_payload() for item in value.items],
            "externalIdentities": [item.snapshot_payload() for item in value.external_identities],
            "snapshotHash": value.snapshot_hash,
        }

    @staticmethod
    def _process_chain_response(value: ToolingProcessChainRevision) -> dict[str, object]:
        return {
            "globalId": str(value.global_id),
            "processChainGlobalId": str(value.process_chain_global_id),
            "chainVersion": value.chain_version,
            "predecessorGlobalId": str(value.predecessor_global_id) if value.predecessor_global_id else None,
            "steps": [item.snapshot_payload() for item in value.steps],
            "reason": value.reason,
            "snapshotHash": value.snapshot_hash,
        }

    @staticmethod
    def _binding_response(value: ToolingSetRevisionBinding) -> dict[str, object]:
        return {
            "globalId": str(value.global_id),
            "toolingMasterGlobalId": str(value.tooling_master_global_id),
            "toolingSetGlobalId": str(value.tooling_set_global_id),
            "toolingSetSnapshotHash": value.tooling_set_snapshot_hash,
            "toolingRevisionGlobalId": str(value.tooling_revision_global_id),
            "toolingRevisionSnapshotHash": value.tooling_revision_snapshot_hash,
            "reason": value.reason,
            "snapshotHash": value.snapshot_hash,
        }

    def _tooling_set_source_revision_response(self, value: ToolingSet) -> dict[str, object]:
        from npi_core.request_security import tooling_revision_routes_are_disabled

        if tooling_revision_routes_are_disabled():
            return self._unavailable("tooling_revision_not_delivered")
        project = self._authorized_project(value.project_global_id)
        if project is None:
            return self._unavailable("tooling_revision_not_delivered")
        binding = self._binding_for_set(project, value)
        return (
            self._binding_response(binding)
            if binding is not None
            else self._unavailable("tooling_revision_not_delivered")
        )

    def _tooling_revision_capability(self, project: object) -> dict[str, object]:
        from npi_core.request_security import tooling_revision_routes_are_disabled

        if tooling_revision_routes_are_disabled():
            return self._unavailable("tooling_revision_not_delivered")
        rows = self._bounded_documents(
            "NPI Tooling Revision",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
            },
            maximum=_MAX_REVISIONS,
        )
        return {
            "state": "available",
            "reasonCode": "tooling_revision_available",
            "revisionCount": len(rows),
        }


def _optional_doc(doctype: str, name: str):
    try:
        return frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        return None


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _json_object(value: object) -> dict[str, Any]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, dict) or any(not isinstance(key, str) for key in parsed):
        raise RuntimeError("The immutable Tooling snapshot is invalid.")
    return parsed


def _database_datetime(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _input_payload(value: Mapping[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, item in value.items():
        if hasattr(item, "snapshot_payload"):
            result[key] = item.snapshot_payload()
        elif hasattr(item, "value") and isinstance(getattr(item, "value"), str):
            result[key] = item.value
        elif isinstance(item, UUID):
            result[key] = str(item)
        elif isinstance(item, date):
            result[key] = item.isoformat()
        elif isinstance(item, tuple):
            result[key] = [str(entry) if isinstance(entry, UUID) else entry for entry in item]
        elif isinstance(item, Mapping):
            result[key] = dict(item)
        else:
            result[key] = item
    return result
