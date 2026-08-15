from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

import frappe

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.tooling.domain import (
    ToolingReferenceUnavailable,
    ToolingVersionConflict,
)
from npi_core.tooling.frappe_validation import tooling_command_write
from npi_core.tooling.manufacturing_domain import (
    DesignReleaseEvidenceCapability,
    ManufacturingAuthorizationUnavailable,
    PlanningMoney,
    ProjectMemberResponsibility,
    ReleasedDocumentEvidence,
    ToolingManufacturingMilestone,
    ToolingManufacturingMilestoneObservation,
    ToolingManufacturingPlanRevision,
    ToolingMilestoneFileEvidence,
    ToolingPlanEvidence,
    ToolingProcurementCostAvailable,
    ToolingProcurementCostUnavailable,
    ToolingSourcingStrategy,
    design_release_capability,
    manufacturing_plan_from_snapshot,
    milestone_observation_from_snapshot,
    procurement_cost_projection_from_snapshot,
    validate_manufacturing_plan_successor,
    validate_milestone_observation_successor,
)


_MAX_PLANS = 200
_MAX_OBSERVATIONS = 1_000
_MAX_MEMBERS = 500
_MAX_LIFECYCLES = 2


@dataclass(frozen=True, slots=True)
class ManufacturingCommandOutcome:
    response: dict[str, Any]
    replayed: bool = False


class ToolingManufacturingRepositoryMixin:
    """Project-first persistence for immutable P6-04 manufacturing records."""

    def tooling_manufacturing_plans(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        if self._master_for_project(project, tooling_master_id) is None:
            return None
        plans = self._manufacturing_plans(project, tooling_master_id)
        observations = self._manufacturing_observations(project, tooling_master_id)
        return self._manufacturing_context(
            project,
            tooling_master_id,
            items=[
                self._manufacturing_plan_item(project, plan, observations)
                for plan in plans
            ],
        )

    def tooling_manufacturing_plan_detail(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        plan_revision_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        if self._master_for_project(project, tooling_master_id) is None:
            return None
        plan = self._manufacturing_plan_for_project(
            project,
            plan_revision_id,
            tooling_master_id=tooling_master_id,
        )
        if plan is None:
            return None
        observations = self._manufacturing_observations(
            project,
            tooling_master_id,
            plan_revision_id=plan_revision_id,
        )
        return self._manufacturing_context(
            project,
            tooling_master_id,
            item=self._manufacturing_plan_item(project, plan, observations),
        )

    def create_tooling_manufacturing_plan(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        *,
        idempotency_key_hash: str,
        plan_id: UUID | None,
        expected_version: int | None,
        tooling_revision_id: UUID,
        tooling_revision_snapshot_hash: str,
        sourcing_strategy: ToolingSourcingStrategy,
        responsible_member: ProjectMemberResponsibility,
        engineering_estimate: PlanningMoney | None,
        budget: PlanningMoney | None,
        evidence: Sequence[ToolingPlanEvidence],
        design_release_evidence: Sequence[ReleasedDocumentEvidence],
        milestones: Sequence[ToolingManufacturingMilestone],
        reason: str,
    ) -> ManufacturingCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "toolingMasterGlobalId": str(tooling_master_id),
            "planGlobalId": str(plan_id) if plan_id else None,
            "expectedVersion": expected_version,
            "toolingRevisionGlobalId": str(tooling_revision_id),
            "toolingRevisionSnapshotHash": tooling_revision_snapshot_hash,
            "sourcingStrategy": sourcing_strategy.value,
            "responsibleMember": responsible_member.snapshot_payload(),
            "engineeringEstimate": (
                engineering_estimate.snapshot_payload()
                if engineering_estimate is not None
                else None
            ),
            "budget": budget.snapshot_payload() if budget is not None else None,
            "evidence": [value.snapshot_payload() for value in evidence],
            "designReleaseEvidence": [
                value.snapshot_payload() for value in design_release_evidence
            ],
            "milestones": [value.snapshot_payload() for value in milestones],
            "reason": reason,
        }
        context = self._command_context(
            project,
            operation="tooling_manufacturing_plan.create",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(context, dict):
            return ManufacturingCommandOutcome(context, replayed=True)
        receipt_key, payload_hash = context
        if self._master_for_project(project, tooling_master_id) is None:
            raise ToolingReferenceUnavailable()
        revision = self._tooling_revision_for_project(
            project,
            tooling_revision_id,
            tooling_master_id=tooling_master_id,
        )
        if (
            revision is None
            or revision.snapshot_hash != tooling_revision_snapshot_hash
        ):
            raise ToolingReferenceUnavailable()
        stable_plan_id = plan_id or self._new_uuid()
        chain = self._manufacturing_plans(
            project,
            tooling_master_id,
            plan_id=stable_plan_id,
        )
        if (not chain and expected_version is not None) or (
            chain and expected_version != chain[-1].plan_version
        ):
            raise ToolingVersionConflict()
        exact_responsible = self._active_member(
            project,
            responsible_member.global_id,
        )
        if exact_responsible != responsible_member:
            raise ToolingReferenceUnavailable()
        for milestone in milestones:
            if milestone.responsible_member is None:
                continue
            if (
                self._active_member(project, milestone.responsible_member.global_id)
                != milestone.responsible_member
            ):
                raise ToolingReferenceUnavailable()
        released_by_revision = {
            value.revision_global_id: value for value in design_release_evidence
        }
        released_by_revision.update(
            {value.document.revision_global_id: value.document for value in evidence}
        )
        for supplied in released_by_revision.values():
            if self._released_document_evidence(project, supplied.revision_global_id) != supplied:
                raise ToolingReferenceUnavailable()
        expected_design = {
            (value.global_id, value.snapshot_hash)
            for value in revision.design_document_revisions
        }
        observed_design = {
            (value.revision_global_id, value.revision_snapshot_hash)
            for value in design_release_evidence
        }
        if expected_design != observed_design:
            raise ToolingReferenceUnavailable()
        now = self._now()
        predecessor = chain[-1] if chain else None
        plan = ToolingManufacturingPlanRevision(
            global_id=self._new_uuid(),
            plan_global_id=stable_plan_id,
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            tooling_master_global_id=tooling_master_id,
            tooling_revision_global_id=revision.global_id,
            tooling_revision_snapshot_hash=revision.snapshot_hash,
            plan_version=1 if predecessor is None else predecessor.plan_version + 1,
            predecessor_global_id=(predecessor.global_id if predecessor else None),
            predecessor_snapshot_hash=(predecessor.snapshot_hash if predecessor else None),
            sourcing_strategy=sourcing_strategy,
            responsible_member=exact_responsible,
            engineering_estimate=engineering_estimate,
            budget=budget,
            evidence=tuple(evidence),
            design_release_evidence=tuple(design_release_evidence),
            milestones=tuple(milestones),
            reason=reason,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        if predecessor is not None:
            validate_manufacturing_plan_successor(predecessor, plan)
        response = {
            "plan": _plan_response(plan),
            "designReleaseEvidence": self._design_release_capability(
                project,
                plan,
            ).snapshot_payload(),
        }
        with tooling_command_write():
            receipt = self._insert_receipt(
                project,
                receipt_key=receipt_key,
                operation="tooling_manufacturing_plan.create",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._insert_manufacturing_plan(plan)
            self._append_audit(
                operation="tooling_manufacturing_plan.create",
                global_id=plan.global_id,
                object_version=plan.plan_version,
                summary={
                    "projectGlobalId": str(project_id),
                    "toolingMasterGlobalId": str(tooling_master_id),
                    "planGlobalId": str(plan.plan_global_id),
                    "predecessorGlobalId": (
                        str(predecessor.global_id) if predecessor else None
                    ),
                    "snapshotHash": plan.snapshot_hash,
                    "requestId": self.request_id,
                },
            )
            self._seal_receipt(
                receipt,
                target_type="tooling_manufacturing_plan_revision",
                target_id=plan.global_id,
                response=response,
                now=now,
            )
        return ManufacturingCommandOutcome(response)

    def create_tooling_manufacturing_milestone_observation(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        plan_revision_id: UUID,
        milestone_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_version: int | None,
        plan_revision_snapshot_hash: str,
        milestone_snapshot_hash: str,
        progress_percentage: int,
        actual_start: date | None,
        actual_finish: date | None,
        risk: str | None,
        note: str | None,
        evidence: Sequence[Mapping[str, object]],
    ) -> ManufacturingCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "toolingMasterGlobalId": str(tooling_master_id),
            "planRevisionGlobalId": str(plan_revision_id),
            "milestoneGlobalId": str(milestone_id),
            "expectedVersion": expected_version,
            "planRevisionSnapshotHash": plan_revision_snapshot_hash,
            "milestoneSnapshotHash": milestone_snapshot_hash,
            "progressPercentage": progress_percentage,
            "actualStart": actual_start.isoformat() if actual_start else None,
            "actualFinish": actual_finish.isoformat() if actual_finish else None,
            "risk": risk,
            "note": note,
            "evidence": [_input_payload(value) for value in evidence],
        }
        context = self._command_context(
            project,
            operation="tooling_manufacturing_milestone.observe",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(context, dict):
            return ManufacturingCommandOutcome(context, replayed=True)
        receipt_key, payload_hash = context
        if self._master_for_project(project, tooling_master_id) is None:
            raise ToolingReferenceUnavailable()
        plan = self._manufacturing_plan_for_project(
            project,
            plan_revision_id,
            tooling_master_id=tooling_master_id,
        )
        if plan is None or plan.snapshot_hash != plan_revision_snapshot_hash:
            raise ToolingReferenceUnavailable()
        milestone = next(
            (value for value in plan.milestones if value.global_id == milestone_id),
            None,
        )
        if milestone is None or milestone.snapshot_hash != milestone_snapshot_hash:
            raise ToolingReferenceUnavailable()
        chain = self._manufacturing_observations(
            project,
            tooling_master_id,
            plan_revision_id=plan_revision_id,
            milestone_id=milestone_id,
        )
        if (not chain and expected_version is not None) or (
            chain and expected_version != chain[-1].observation_version
        ):
            raise ToolingVersionConflict()
        reporter = self._current_actor_manufacturing_member(project)
        if reporter is None:
            raise ToolingReferenceUnavailable()
        exact_evidence = tuple(
            self._milestone_file_evidence(project, value) for value in evidence
        )
        now = self._now()
        predecessor = chain[-1] if chain else None
        observation = ToolingManufacturingMilestoneObservation(
            global_id=self._new_uuid(),
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            tooling_master_global_id=tooling_master_id,
            plan_revision_global_id=plan.global_id,
            plan_revision_snapshot_hash=plan.snapshot_hash,
            milestone_global_id=milestone.global_id,
            milestone_snapshot_hash=milestone.snapshot_hash,
            observation_version=(
                1 if predecessor is None else predecessor.observation_version + 1
            ),
            predecessor_global_id=(predecessor.global_id if predecessor else None),
            predecessor_snapshot_hash=(predecessor.snapshot_hash if predecessor else None),
            progress_percentage=progress_percentage,
            actual_start=actual_start,
            actual_finish=actual_finish,
            risk=risk,
            note=note,
            evidence=exact_evidence,
            reported_by_member=reporter,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        if predecessor is not None:
            validate_milestone_observation_successor(predecessor, observation)
        response = {"observation": _observation_response(observation)}
        with tooling_command_write():
            receipt = self._insert_receipt(
                project,
                receipt_key=receipt_key,
                operation="tooling_manufacturing_milestone.observe",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._insert_milestone_observation(observation)
            self._append_audit(
                operation="tooling_manufacturing_milestone.observe",
                global_id=observation.global_id,
                object_version=observation.observation_version,
                summary={
                    "projectGlobalId": str(project_id),
                    "toolingMasterGlobalId": str(tooling_master_id),
                    "planRevisionGlobalId": str(plan.global_id),
                    "milestoneGlobalId": str(milestone.global_id),
                    "predecessorGlobalId": (
                        str(predecessor.global_id) if predecessor else None
                    ),
                    "snapshotHash": observation.snapshot_hash,
                    "requestId": self.request_id,
                },
            )
            self._seal_receipt(
                receipt,
                target_type="tooling_manufacturing_milestone_observation",
                target_id=observation.global_id,
                response=response,
                now=now,
            )
        return ManufacturingCommandOutcome(response)

    def _manufacturing_context(
        self,
        project: object,
        tooling_master_id: UUID,
        **values: object,
    ) -> dict[str, Any]:
        create = self._is_internal_system_manager()
        return {
            "projectGlobalId": str(project.global_id),
            "toolingMasterGlobalId": str(tooling_master_id),
            "permissions": {
                "view": True,
                "createPlan": create,
                "observeMilestone": create,
                "transitionLifecycle": False,
                "editErpProjection": False,
            },
            "manufacturingAuthorization": (
                ManufacturingAuthorizationUnavailable().snapshot_payload()
            ),
            "erpProjection": self._procurement_cost_projection(
                project,
                tooling_master_id,
            ).snapshot_payload(),
            **values,
        }

    def _manufacturing_plan_item(
        self,
        project: object,
        plan: ToolingManufacturingPlanRevision,
        observations: Sequence[ToolingManufacturingMilestoneObservation],
    ) -> dict[str, object]:
        return {
            "plan": _plan_response(plan),
            "observations": [
                _observation_response(value)
                for value in observations
                if value.plan_revision_global_id == plan.global_id
            ],
            "designReleaseEvidence": self._design_release_capability(
                project,
                plan,
            ).snapshot_payload(),
        }

    def _manufacturing_plans(
        self,
        project: object,
        tooling_master_id: UUID,
        *,
        plan_id: UUID | None = None,
    ) -> tuple[ToolingManufacturingPlanRevision, ...]:
        filters: dict[str, object] = {
            "tenant_id": str(project.tenant_id),
            "project_global_id": str(project.global_id),
            "tooling_master_global_id": str(tooling_master_id),
        }
        if plan_id is not None:
            filters["plan_global_id"] = str(plan_id)
        rows = self._bounded_documents(
            "NPI Tooling Manufacturing Plan Revision",
            filters=filters,
            maximum=_MAX_PLANS,
        )
        values = tuple(
            manufacturing_plan_from_snapshot(_json_object(row.plan_snapshot))
            for row in rows
        )
        grouped: dict[UUID, list[ToolingManufacturingPlanRevision]] = {}
        for value in values:
            grouped.setdefault(value.plan_global_id, []).append(value)
        for chain in grouped.values():
            chain.sort(key=lambda value: value.plan_version)
            for index, value in enumerate(chain):
                if value.plan_version != index + 1:
                    raise RuntimeError("The manufacturing plan chain is not contiguous.")
                if index:
                    validate_manufacturing_plan_successor(chain[index - 1], value)
        return tuple(
            sorted(
                values,
                key=lambda value: (str(value.plan_global_id), value.plan_version),
            )
        )

    def _manufacturing_plan_for_project(
        self,
        project: object,
        plan_revision_id: UUID,
        *,
        tooling_master_id: UUID,
    ) -> ToolingManufacturingPlanRevision | None:
        row = _optional_doc(
            "NPI Tooling Manufacturing Plan Revision",
            str(plan_revision_id),
        )
        if row is None or any(
            (
                str(row.global_id) != str(plan_revision_id),
                str(row.tenant_id) != str(project.tenant_id),
                str(row.project_global_id) != str(project.global_id),
                str(row.tooling_master_global_id) != str(tooling_master_id),
            )
        ):
            return None
        return manufacturing_plan_from_snapshot(_json_object(row.plan_snapshot))

    def _manufacturing_observations(
        self,
        project: object,
        tooling_master_id: UUID,
        *,
        plan_revision_id: UUID | None = None,
        milestone_id: UUID | None = None,
    ) -> tuple[ToolingManufacturingMilestoneObservation, ...]:
        filters: dict[str, object] = {
            "tenant_id": str(project.tenant_id),
            "project_global_id": str(project.global_id),
            "tooling_master_global_id": str(tooling_master_id),
        }
        if plan_revision_id is not None:
            filters["plan_revision_global_id"] = str(plan_revision_id)
        if milestone_id is not None:
            filters["milestone_global_id"] = str(milestone_id)
        rows = self._bounded_documents(
            "NPI Tooling Manufacturing Milestone Observation",
            filters=filters,
            maximum=_MAX_OBSERVATIONS,
        )
        values = tuple(
            milestone_observation_from_snapshot(_json_object(row.observation_snapshot))
            for row in rows
        )
        grouped: dict[
            tuple[UUID, UUID],
            list[ToolingManufacturingMilestoneObservation],
        ] = {}
        for value in values:
            grouped.setdefault(
                (value.plan_revision_global_id, value.milestone_global_id),
                [],
            ).append(value)
        for chain in grouped.values():
            chain.sort(key=lambda value: value.observation_version)
            for index, value in enumerate(chain):
                if value.observation_version != index + 1:
                    raise RuntimeError(
                        "The milestone observation chain is not contiguous."
                    )
                if index:
                    validate_milestone_observation_successor(chain[index - 1], value)
        return tuple(
            sorted(
                values,
                key=lambda value: (
                    str(value.plan_revision_global_id),
                    str(value.milestone_global_id),
                    value.observation_version,
                ),
            )
        )

    def _design_release_capability(
        self,
        project: object,
        plan: ToolingManufacturingPlanRevision,
    ) -> DesignReleaseEvidenceCapability:
        revision = self._tooling_revision_for_project(
            project,
            plan.tooling_revision_global_id,
            tooling_master_id=plan.tooling_master_global_id,
        )
        if revision is None or revision.snapshot_hash != plan.tooling_revision_snapshot_hash:
            expected = tuple(
                (value.revision_global_id, value.revision_snapshot_hash)
                for value in plan.design_release_evidence
            )
            return design_release_capability(expected, ())
        expected = tuple(
            (value.global_id, value.snapshot_hash)
            for value in revision.design_document_revisions
        )
        released = tuple(
            value
            for value in (
                self._released_document_evidence(project, revision_id)
                for revision_id, _snapshot_hash in expected
            )
            if value is not None
        )
        return design_release_capability(expected, released)

    def _released_document_evidence(
        self,
        project: object,
        revision_id: UUID,
    ) -> ReleasedDocumentEvidence | None:
        revision = _optional_doc("NPI Document Revision", str(revision_id))
        if revision is None or any(
            (
                str(revision.global_id) != str(revision_id),
                str(revision.tenant_id) != str(project.tenant_id),
                str(revision.project_global_id) != str(project.global_id),
            )
        ):
            return None
        lifecycles = self._bounded_documents(
            "NPI Document Revision Lifecycle",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "revision_global_id": str(revision_id),
            },
            maximum=_MAX_LIFECYCLES,
        )
        if len(lifecycles) != 1:
            return None
        lifecycle = lifecycles[0]
        release_event_id = getattr(lifecycle, "release_event_global_id", None)
        if (
            str(getattr(lifecycle, "current_state", "")) != "released"
            or not release_event_id
            or str(getattr(lifecycle, "last_event_global_id", ""))
            != str(release_event_id)
            or not getattr(lifecycle, "release_snapshot_hash", None)
        ):
            return None
        event = _optional_doc("NPI Document Lifecycle Event", str(release_event_id))
        if event is None or any(
            (
                str(event.global_id) != str(release_event_id),
                str(event.tenant_id) != str(project.tenant_id),
                str(event.project_global_id) != str(project.global_id),
                str(event.revision_global_id) != str(revision_id),
                str(event.event_type) != "released",
                str(event.to_state) != "released",
                int(event.to_version) != int(lifecycle.lifecycle_version),
            )
        ):
            return None
        try:
            return ReleasedDocumentEvidence(
                revision_global_id=revision_id,
                revision_snapshot_hash=str(revision.snapshot_hash),
                lifecycle_global_id=UUID(str(lifecycle.global_id)),
                lifecycle_version=int(lifecycle.lifecycle_version),
                release_event_global_id=UUID(str(release_event_id)),
                release_event_hash=str(event.event_hash),
                release_snapshot_hash=str(lifecycle.release_snapshot_hash),
            )
        except (RequestValidationFailed, TypeError, ValueError):
            return None

    def _active_member(
        self,
        project: object,
        member_id: UUID,
    ) -> ProjectMemberResponsibility | None:
        member = _optional_doc("NPI Project Member", str(member_id))
        if member is None or any(
            (
                str(member.global_id) != str(member_id),
                str(member.tenant_id) != str(project.tenant_id),
                str(member.project_global_id) != str(project.global_id),
                getattr(member, "effective_to", None) not in (None, ""),
                _date_value(member.effective_from) > self._now().date(),
            )
        ):
            return None
        return ProjectMemberResponsibility(
            global_id=UUID(str(member.global_id)),
            user_id=str(member.user_id),
            optimistic_version=int(member.optimistic_version),
        )

    def _current_actor_manufacturing_member(
        self,
        project: object,
    ) -> ProjectMemberResponsibility | None:
        names = frappe.get_all(
            "NPI Project Member",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "user_id": self.actor,
                "effective_to": ["is", "not set"],
            },
            pluck="name",
            order_by="global_id asc",
            limit_page_length=_MAX_MEMBERS + 1,
        )
        if len(names) > _MAX_MEMBERS:
            raise RuntimeError("The Project member collection exceeds its safe bound.")
        matches = tuple(
            value
            for value in (
                self._active_member(project, UUID(str(name))) for name in names
            )
            if value is not None and value.user_id == self.actor
        )
        return matches[0] if len(matches) == 1 else None

    def _milestone_file_evidence(
        self,
        project: object,
        supplied: Mapping[str, object],
    ) -> ToolingMilestoneFileEvidence:
        row = self._file_revision_for_project(
            project,
            supplied["file_revision_id"],
        )
        if row is None or any(
            (
                int(row.optimistic_version) != supplied["file_optimistic_version"],
                str(row.frappe_content_hash) != supplied["frappe_content_hash"],
                str(row.sha256) != supplied["sha256"],
            )
        ):
            raise ToolingReferenceUnavailable()
        return ToolingMilestoneFileEvidence(
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

    def _procurement_cost_projection(
        self,
        project: object,
        tooling_master_id: UUID,
    ) -> ToolingProcurementCostUnavailable | ToolingProcurementCostAvailable:
        reader = self._procurement_cost_reader or self._resolved_projection_consumer_reader()
        if reader is None:
            return ToolingProcurementCostUnavailable()
        snapshot = reader.read_tooling_procurement_cost(
            project_global_id=UUID(str(project.global_id)),
            tooling_master_global_id=tooling_master_id,
        )
        if snapshot is None:
            return ToolingProcurementCostUnavailable()
        projection = procurement_cost_projection_from_snapshot(snapshot)
        if (
            isinstance(projection, ToolingProcurementCostAvailable)
            and projection.tooling_master_global_id != tooling_master_id
        ):
            raise ToolingReferenceUnavailable()
        return projection

    @staticmethod
    def _insert_manufacturing_plan(
        value: ToolingManufacturingPlanRevision,
    ) -> object:
        return frappe.get_doc(
            {
                "doctype": "NPI Tooling Manufacturing Plan Revision",
                "global_id": str(value.global_id),
                "plan_global_id": str(value.plan_global_id),
                "version_key_hash": value.version_key_hash,
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "tooling_master": str(value.tooling_master_global_id),
                "tooling_master_global_id": str(value.tooling_master_global_id),
                "tooling_revision": str(value.tooling_revision_global_id),
                "tooling_revision_global_id": str(value.tooling_revision_global_id),
                "tooling_revision_snapshot_hash": value.tooling_revision_snapshot_hash,
                "plan_version": value.plan_version,
                "predecessor_global_id": (
                    str(value.predecessor_global_id)
                    if value.predecessor_global_id
                    else None
                ),
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "sourcing_strategy": value.sourcing_strategy.value,
                "responsible_member": str(value.responsible_member.global_id),
                "responsible_member_global_id": str(value.responsible_member.global_id),
                "responsibility_snapshot": _canonical_json(
                    value.responsible_member.snapshot_payload()
                ),
                "cost_snapshot": _canonical_json(
                    {
                        "engineeringEstimate": (
                            value.engineering_estimate.snapshot_payload()
                            if value.engineering_estimate
                            else None
                        ),
                        "budget": value.budget.snapshot_payload() if value.budget else None,
                    }
                ),
                "document_evidence_snapshot": _canonical_json(
                    [item.snapshot_payload() for item in value.evidence]
                ),
                "design_release_snapshot": _canonical_json(
                    [item.snapshot_payload() for item in value.design_release_evidence]
                ),
                "milestone_snapshot": _canonical_json(
                    [item.snapshot_payload() for item in value.milestones]
                ),
                "reason": value.reason,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "plan_snapshot": _canonical_json(value.snapshot_payload()),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    @staticmethod
    def _insert_milestone_observation(
        value: ToolingManufacturingMilestoneObservation,
    ) -> object:
        return frappe.get_doc(
            {
                "doctype": "NPI Tooling Manufacturing Milestone Observation",
                "global_id": str(value.global_id),
                "observation_key_hash": value.observation_key_hash,
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "tooling_master_global_id": str(value.tooling_master_global_id),
                "manufacturing_plan_revision": str(value.plan_revision_global_id),
                "plan_revision_global_id": str(value.plan_revision_global_id),
                "plan_revision_snapshot_hash": value.plan_revision_snapshot_hash,
                "milestone_global_id": str(value.milestone_global_id),
                "milestone_snapshot_hash": value.milestone_snapshot_hash,
                "observation_version": value.observation_version,
                "predecessor_global_id": (
                    str(value.predecessor_global_id)
                    if value.predecessor_global_id
                    else None
                ),
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "progress_percentage": value.progress_percentage,
                "actual_start": value.actual_start.isoformat() if value.actual_start else None,
                "actual_finish": value.actual_finish.isoformat() if value.actual_finish else None,
                "risk": value.risk,
                "note": value.note,
                "evidence_snapshot": _canonical_json(
                    [item.snapshot_payload() for item in value.evidence]
                ),
                "reported_by_member": str(value.reported_by_member.global_id),
                "reported_by_member_global_id": str(value.reported_by_member.global_id),
                "reporter_snapshot": _canonical_json(
                    value.reported_by_member.snapshot_payload()
                ),
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "observation_snapshot": _canonical_json(value.snapshot_payload()),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()


def _optional_doc(doctype: str, name: str):
    try:
        return frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        return None


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_object(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    parsed = json.loads(str(value))
    if not isinstance(parsed, dict):
        raise RuntimeError("The persisted manufacturing snapshot is invalid.")
    return parsed


def _database_datetime(value: datetime) -> str:
    return value.astimezone(UTC).replace(tzinfo=None).isoformat(
        sep=" ",
        timespec="microseconds",
    )


def _date_value(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def _input_payload(value: Mapping[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, item in value.items():
        if isinstance(item, UUID):
            result[key] = str(item)
        elif hasattr(item, "value"):
            result[key] = item.value
        else:
            result[key] = item
    return result


def _plan_response(value: ToolingManufacturingPlanRevision) -> dict[str, object]:
    snapshot = value.snapshot_payload()
    return {
        key: snapshot[key]
        for key in (
            "globalId",
            "planGlobalId",
            "toolingMasterGlobalId",
            "toolingRevisionGlobalId",
            "toolingRevisionSnapshotHash",
            "planVersion",
            "predecessorGlobalId",
            "predecessorSnapshotHash",
            "sourcingStrategy",
            "responsibleMember",
            "engineeringEstimate",
            "budget",
            "evidence",
            "designReleaseEvidence",
            "milestones",
            "reason",
        )
    } | {"snapshotHash": value.snapshot_hash}


def _observation_response(
    value: ToolingManufacturingMilestoneObservation,
) -> dict[str, object]:
    snapshot = value.snapshot_payload()
    return {
        key: snapshot[key]
        for key in (
            "globalId",
            "planRevisionGlobalId",
            "planRevisionSnapshotHash",
            "milestoneGlobalId",
            "milestoneSnapshotHash",
            "observationVersion",
            "predecessorGlobalId",
            "predecessorSnapshotHash",
            "progressPercentage",
            "actualStart",
            "actualFinish",
            "risk",
            "note",
            "evidence",
            "reportedByMember",
        )
    } | {"snapshotHash": value.snapshot_hash}
