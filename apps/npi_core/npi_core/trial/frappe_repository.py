from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

import frappe
from frappe import _

from npi_core.foundation.audit import create_audit_event
from npi_core.foundation.errors import RequestValidationFailed
from npi_core.foundation.security import Principal
from npi_core.project_controls.terminal_guard import require_mutable_project
from npi_core.project_work.frappe_repository import FrappeProjectWorkRepository
from npi_core.trial.domain import (
    TrialIdempotencyConflict,
    TrialLabelConflict,
    TrialMeasurementPlanIntent,
    TrialPlanRevision,
    TrialPlanWorkLink,
    TrialProjectMemberReference,
    TrialPurpose,
    TrialReferenceUnavailable,
    TrialResourceKind,
    TrialResourceProposal,
    TrialResourceSource,
    TrialRound,
    TrialUnavailable,
    TrialVersionConflict,
    create_planned_trial_round,
    sha256_json,
    trial_plan_from_snapshot,
    trial_round_from_snapshot,
    trial_work_link_from_snapshot,
    validate_trial_plan_successor,
)
from npi_core.trial.frappe_validation import trial_command_write


_MAX_PLANS = 500
_MAX_PLAN_REVISIONS = 1_000
_MAX_TOTAL_REVISIONS = 50_000
_MAX_ROUNDS = 1_000
_MAX_ACTION_LINKS = 5_000
_MAX_MEMBERS = 256


@dataclass(frozen=True, slots=True)
class TrialCommandOutcome:
    response: dict[str, Any]
    replayed: bool = False


class FrappeTrialRepository:
    """Authorized Project-first persistence for the bounded P7-01 slice."""

    def __init__(
        self,
        *,
        principal: Principal,
        request_id: str,
        trace_id: str,
    ) -> None:
        self.principal = principal
        self.actor = principal.user_id
        self.request_id = str(UUID(request_id))
        self.trace_id = trace_id

    def planning_workspace(self, project_id: UUID) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        revisions = self._project_plan_revisions(project)
        grouped: dict[UUID, list[TrialPlanRevision]] = {}
        for revision in revisions:
            grouped.setdefault(revision.plan_global_id, []).append(revision)
        if len(grouped) > _MAX_PLANS:
            raise RuntimeError("Persisted Trial Plan collection exceeds its safe bound.")
        plans = []
        for plan_id in sorted(grouped, key=str):
            latest = max(grouped[plan_id], key=lambda value: value.plan_version)
            plans.append(
                {
                    "planGlobalId": str(plan_id),
                    "latestRevision": _plan_response(latest),
                    "roundCount": self._bounded_count(
                        "NPI Trial Round",
                        {
                            "tenant_id": str(project.tenant_id),
                            "project_global_id": str(project_id),
                            "trial_plan_global_id": str(plan_id),
                        },
                        _MAX_ROUNDS,
                    ),
                    "actionCount": self._bounded_count(
                        "NPI Trial Plan Work Link",
                        {
                            "tenant_id": str(project.tenant_id),
                            "project_global_id": str(project_id),
                            "trial_plan_global_id": str(plan_id),
                        },
                        _MAX_ACTION_LINKS,
                    ),
                }
            )
        return {
            "projectGlobalId": str(project_id),
            "plans": plans,
            "capabilities": _unavailable_capabilities(),
            "permissions": self._permissions(),
        }

    def plan_detail(
        self,
        project_id: UUID,
        plan_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        return self._plan_detail_for(project, plan_id)

    def create_plan(
        self,
        project_id: UUID,
        *,
        idempotency_key_hash: str,
        tooling_master_global_id: UUID,
        purpose: TrialPurpose,
        objective: str,
        planned_start_at: datetime,
        planned_end_at: datetime,
        resources: Sequence[Mapping[str, Any]],
        responsible_member_global_ids: Sequence[UUID],
        sample_quantity: int,
        measurement_plan: Mapping[str, Any],
        reason: str,
    ) -> TrialCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "projectId": project_id,
            "toolingMasterGlobalId": tooling_master_global_id,
            "purpose": purpose,
            "objective": objective,
            "plannedStartAt": planned_start_at,
            "plannedEndAt": planned_end_at,
            "resources": resources,
            "responsibleMemberGlobalIds": responsible_member_global_ids,
            "sampleQuantity": sample_quantity,
            "measurementPlan": measurement_plan,
            "reason": reason,
        }
        payload_hash = _payload_hash(payload)
        replay = self._idempotency_replay(
            project,
            "trial_plan.create",
            idempotency_key_hash,
            payload_hash,
        )
        if replay is not None:
            return TrialCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        self._require_tooling(project, tooling_master_global_id)
        now = datetime.now(UTC)
        plan = self._build_plan_revision(
            project,
            global_id=uuid4(),
            plan_global_id=uuid4(),
            tooling_master_global_id=tooling_master_global_id,
            plan_version=1,
            purpose=purpose,
            objective=objective,
            planned_start_at=planned_start_at,
            planned_end_at=planned_end_at,
            resources=resources,
            responsible_member_global_ids=responsible_member_global_ids,
            sample_quantity=sample_quantity,
            measurement_plan=measurement_plan,
            reason=reason,
            created_at=now,
        )
        with trial_command_write():
            receipt = self._insert_receipt(
                project,
                operation="trial_plan.create",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                created_at=now,
            )
            if _is_replay_response(receipt):
                return TrialCommandOutcome(receipt, replayed=True)
            self._insert_plan_revision(plan)
            self._append_audit(
                operation="trial_plan.create",
                global_id=plan.global_id,
                object_version=plan.plan_version,
                summary={
                    "planGlobalId": str(plan.plan_global_id),
                    "projectId": str(project_id),
                    "reason": plan.reason,
                    "requestId": self.request_id,
                },
            )
            response = self._plan_detail_for(project, plan.plan_global_id)
            if response is None:
                raise RuntimeError("Created Trial Plan could not be reconstructed.")
            self._seal_receipt(
                receipt,
                target_object_type="trial_plan_revision",
                target_global_id=plan.global_id,
                response=response,
                updated_at=now,
            )
        return TrialCommandOutcome(response)

    def create_plan_revision(
        self,
        project_id: UUID,
        plan_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_revision_global_id: UUID,
        expected_revision_snapshot_hash: str,
        expected_plan_version: int,
        purpose: TrialPurpose,
        objective: str,
        planned_start_at: datetime,
        planned_end_at: datetime,
        resources: Sequence[Mapping[str, Any]],
        responsible_member_global_ids: Sequence[UUID],
        sample_quantity: int,
        measurement_plan: Mapping[str, Any],
        reason: str,
    ) -> TrialCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "projectId": project_id,
            "planId": plan_id,
            "expectedRevisionGlobalId": expected_revision_global_id,
            "expectedRevisionSnapshotHash": expected_revision_snapshot_hash,
            "expectedPlanVersion": expected_plan_version,
            "purpose": purpose,
            "objective": objective,
            "plannedStartAt": planned_start_at,
            "plannedEndAt": planned_end_at,
            "resources": resources,
            "responsibleMemberGlobalIds": responsible_member_global_ids,
            "sampleQuantity": sample_quantity,
            "measurementPlan": measurement_plan,
            "reason": reason,
        }
        payload_hash = _payload_hash(payload)
        replay = self._idempotency_replay(
            project,
            "trial_plan.revise",
            idempotency_key_hash,
            payload_hash,
        )
        if replay is not None:
            return TrialCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        predecessor = self._current_plan_revision(project, plan_id, for_update=True)
        if predecessor is None:
            return None
        if (
            predecessor.global_id != expected_revision_global_id
            or predecessor.snapshot_hash != expected_revision_snapshot_hash
            or predecessor.plan_version != expected_plan_version
        ):
            raise TrialVersionConflict()
        now = datetime.now(UTC)
        successor = self._build_plan_revision(
            project,
            global_id=uuid4(),
            plan_global_id=plan_id,
            tooling_master_global_id=predecessor.tooling_master_global_id,
            plan_version=predecessor.plan_version + 1,
            predecessor=predecessor,
            purpose=purpose,
            objective=objective,
            planned_start_at=planned_start_at,
            planned_end_at=planned_end_at,
            resources=resources,
            responsible_member_global_ids=responsible_member_global_ids,
            sample_quantity=sample_quantity,
            measurement_plan=measurement_plan,
            reason=reason,
            created_at=now,
        )
        validate_trial_plan_successor(predecessor, successor)
        with trial_command_write():
            receipt = self._insert_receipt(
                project,
                operation="trial_plan.revise",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                created_at=now,
            )
            if _is_replay_response(receipt):
                return TrialCommandOutcome(receipt, replayed=True)
            self._insert_plan_revision(successor)
            self._append_audit(
                operation="trial_plan.revise",
                global_id=successor.global_id,
                object_version=successor.plan_version,
                summary={
                    "planGlobalId": str(plan_id),
                    "predecessorGlobalId": str(predecessor.global_id),
                    "projectId": str(project_id),
                    "reason": successor.reason,
                    "requestId": self.request_id,
                },
            )
            response = self._plan_detail_for(project, plan_id)
            if response is None:
                raise RuntimeError("Revised Trial Plan could not be reconstructed.")
            self._seal_receipt(
                receipt,
                target_object_type="trial_plan_revision",
                target_global_id=successor.global_id,
                response=response,
                updated_at=now,
            )
        return TrialCommandOutcome(response)

    def create_round(
        self,
        project_id: UUID,
        plan_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_plan_revision_global_id: UUID,
        expected_plan_revision_snapshot_hash: str,
        display_label: str | None,
        reason: str,
    ) -> TrialCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "projectId": project_id,
            "planId": plan_id,
            "expectedPlanRevisionGlobalId": expected_plan_revision_global_id,
            "expectedPlanRevisionSnapshotHash": expected_plan_revision_snapshot_hash,
            "displayLabel": display_label,
            "reason": reason,
        }
        payload_hash = _payload_hash(payload)
        replay = self._idempotency_replay(
            project,
            "trial_round.create",
            idempotency_key_hash,
            payload_hash,
        )
        if replay is not None:
            return TrialCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        plan = self._exact_plan_revision(
            project,
            plan_id,
            expected_plan_revision_global_id,
            expected_plan_revision_snapshot_hash,
        )
        if plan is None:
            return None
        latest_round = frappe.get_all(
            "NPI Trial Round",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project_id),
                "trial_plan_global_id": str(plan_id),
            },
            fields=["round_sequence"],
            order_by="round_sequence desc, global_id desc",
            limit_page_length=1,
        )
        sequence = int(latest_round[0].round_sequence) + 1 if latest_round else 0
        normalized_label = (
            display_label.strip().upper()
            if display_label is not None
            else f"T{sequence}"
        )
        if frappe.db.exists(
            "NPI Trial Round",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project_id),
                "trial_plan_global_id": str(plan_id),
                "display_label": normalized_label,
            },
        ):
            raise TrialLabelConflict()
        now = datetime.now(UTC)
        trial_round, event = create_planned_trial_round(
            global_id=uuid4(),
            event_global_id=uuid4(),
            plan=plan,
            round_sequence=sequence,
            display_label=normalized_label,
            reason=reason,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        with trial_command_write():
            receipt = self._insert_receipt(
                project,
                operation="trial_round.create",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                created_at=now,
            )
            if _is_replay_response(receipt):
                return TrialCommandOutcome(receipt, replayed=True)
            self._insert_round_event(event)
            self._insert_round(trial_round)
            self._append_audit(
                operation="trial_round.create",
                global_id=trial_round.global_id,
                object_version=trial_round.optimistic_version,
                summary={
                    "displayLabel": trial_round.display_label,
                    "planGlobalId": str(plan_id),
                    "planRevisionGlobalId": str(plan.global_id),
                    "projectId": str(project_id),
                    "reason": event.reason,
                    "requestId": self.request_id,
                },
            )
            response = self._plan_detail_for(project, plan_id)
            if response is None:
                raise RuntimeError("Created Trial Round could not be reconstructed.")
            self._seal_receipt(
                receipt,
                target_object_type="trial_round",
                target_global_id=trial_round.global_id,
                response=response,
                updated_at=now,
            )
        return TrialCommandOutcome(response)

    def generate_actions(
        self,
        project_id: UUID,
        plan_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_plan_revision_global_id: UUID,
        expected_plan_revision_snapshot_hash: str,
        trial_round_global_id: UUID | None,
        actions: Sequence[Mapping[str, Any]],
        reason: str,
    ) -> TrialCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "projectId": project_id,
            "planId": plan_id,
            "expectedPlanRevisionGlobalId": expected_plan_revision_global_id,
            "expectedPlanRevisionSnapshotHash": expected_plan_revision_snapshot_hash,
            "trialRoundGlobalId": trial_round_global_id,
            "actions": actions,
            "reason": reason,
        }
        payload_hash = _payload_hash(payload)
        replay = self._idempotency_replay(
            project,
            "trial_plan.generate_actions",
            idempotency_key_hash,
            payload_hash,
        )
        if replay is not None:
            return TrialCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        plan = self._exact_plan_revision(
            project,
            plan_id,
            expected_plan_revision_global_id,
            expected_plan_revision_snapshot_hash,
        )
        if plan is None:
            return None
        if trial_round_global_id is not None:
            trial_round = self._round_document(
                project,
                plan_id,
                trial_round_global_id,
            )
            if trial_round is None:
                return None
            closed_round = trial_round_from_snapshot(
                _json_object(trial_round.round_snapshot)
            )
            if closed_round.trial_plan_revision_global_id != plan.global_id:
                raise TrialReferenceUnavailable()
        prepared_actions = self._prepare_actions(project, actions)
        now = datetime.now(UTC)
        with trial_command_write():
            receipt = self._insert_receipt(
                project,
                operation="trial_plan.generate_actions",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                created_at=now,
            )
            if _is_replay_response(receipt):
                return TrialCommandOutcome(receipt, replayed=True)
            work_repository = FrappeProjectWorkRepository(
                principal=self.principal,
                request_id=self.request_id,
                trace_id=self.trace_id,
            )
            created = work_repository.create_domain_work_items_in_parent_command(
                project,
                items=prepared_actions,
            )
            if created is None:
                raise RuntimeError(
                    "Project Work authorization changed inside the Trial transaction."
                )
            links: list[TrialPlanWorkLink] = []
            for value in created:
                document = value["document"]
                link = TrialPlanWorkLink(
                    global_id=uuid4(),
                    tenant_id=str(project.tenant_id),
                    project_global_id=project_id,
                    trial_plan_global_id=plan_id,
                    trial_plan_revision_global_id=plan.global_id,
                    trial_plan_revision_snapshot_hash=plan.snapshot_hash,
                    trial_round_global_id=trial_round_global_id,
                    domain_work_item_global_id=UUID(str(document.global_id)),
                    created_by_user_id=self.actor,
                    created_at=now,
                    request_id=UUID(self.request_id),
                    trace_id=self.trace_id,
                )
                self._insert_work_link(link)
                links.append(link)
            self._append_audit(
                operation="trial_plan.generate_actions",
                global_id=plan.global_id,
                object_version=plan.plan_version,
                summary={
                    "actionCount": len(links),
                    "planGlobalId": str(plan_id),
                    "projectId": str(project_id),
                    "reason": reason,
                    "requestId": self.request_id,
                    "trialRoundGlobalId": (
                        str(trial_round_global_id)
                        if trial_round_global_id is not None
                        else None
                    ),
                },
            )
            response = self._plan_detail_for(project, plan_id)
            if response is None:
                raise RuntimeError("Generated Trial actions could not be reconstructed.")
            self._seal_receipt(
                receipt,
                target_object_type="trial_plan_work_link_set",
                target_global_id=plan.global_id,
                response=response,
                updated_at=now,
            )
        return TrialCommandOutcome(response)

    def _build_plan_revision(
        self,
        project,
        *,
        global_id: UUID,
        plan_global_id: UUID,
        tooling_master_global_id: UUID,
        plan_version: int,
        purpose: TrialPurpose,
        objective: str,
        planned_start_at: datetime,
        planned_end_at: datetime,
        resources: Sequence[Mapping[str, Any]],
        responsible_member_global_ids: Sequence[UUID],
        sample_quantity: int,
        measurement_plan: Mapping[str, Any],
        reason: str,
        created_at: datetime,
        predecessor: TrialPlanRevision | None = None,
    ) -> TrialPlanRevision:
        member_refs = tuple(
            self._responsible_member(project, member_id)
            for member_id in responsible_member_global_ids
        )
        resource_values = tuple(
            TrialResourceProposal(
                global_id=uuid4(),
                kind=_enum_value(value.get("kind"), TrialResourceKind, "resources.kind"),
                source_system=_enum_value(
                    value.get("sourceSystem", value.get("source_system")),
                    TrialResourceSource,
                    "resources.sourceSystem",
                ),
                source_object_id=value.get(
                    "sourceObjectId",
                    value.get("source_object_id"),
                ),
                label=value.get("label"),
                quantity=value.get("quantity"),
                unit=value.get("unit"),
            )
            for value in resources
        )
        measurement = TrialMeasurementPlanIntent(
            description=measurement_plan.get("description"),
            document_revision_global_id=measurement_plan.get(
                "documentRevisionGlobalId",
                measurement_plan.get("document_revision_global_id"),
            ),
            document_revision_snapshot_hash=measurement_plan.get(
                "documentRevisionSnapshotHash",
                measurement_plan.get("document_revision_snapshot_hash"),
            ),
            document_optimistic_version=measurement_plan.get(
                "documentOptimisticVersion",
                measurement_plan.get("document_optimistic_version"),
            ),
        )
        self._require_measurement_document(project, measurement)
        return TrialPlanRevision(
            global_id=global_id,
            plan_global_id=plan_global_id,
            tenant_id=str(project.tenant_id),
            project_global_id=UUID(str(project.global_id)),
            tooling_master_global_id=tooling_master_global_id,
            plan_version=plan_version,
            predecessor_global_id=predecessor.global_id if predecessor else None,
            predecessor_snapshot_hash=(
                predecessor.snapshot_hash if predecessor else None
            ),
            purpose=purpose,
            objective=objective,
            planned_start_at=planned_start_at,
            planned_end_at=planned_end_at,
            resources=resource_values,
            responsible_members=member_refs,
            sample_quantity=sample_quantity,
            measurement_plan=measurement,
            reason=reason,
            created_by_user_id=self.actor,
            created_at=created_at,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )

    def _prepare_actions(
        self,
        project,
        actions: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        if not actions or len(actions) > 50:
            raise _field_problem("actions", _("Add between 1 and 50 valid actions."))
        prepared = []
        action_keys: set[str] = set()
        for index, value in enumerate(actions):
            action_key = value.get("actionKey", value.get("action_key"))
            if not isinstance(action_key, str) or not action_key.strip():
                raise _field_problem(
                    f"actions[{index}].actionKey",
                    _("Enter a value."),
                )
            normalized_key = action_key.strip()
            if normalized_key in action_keys:
                raise _field_problem(
                    f"actions[{index}].actionKey",
                    _("Action keys must be unique."),
                )
            action_keys.add(normalized_key)
            member_id = value.get(
                "responsibleMemberGlobalId",
                value.get("responsible_member_global_id"),
            )
            member = self._responsible_member(project, UUID(str(member_id)))
            prepared.append(
                {
                    "actionKey": normalized_key,
                    "title": value.get("title"),
                    "description": value.get("description"),
                    "ownerUserId": member.user_id,
                    "dueAt": value.get("dueAt", value.get("due_at")),
                    "severity": value.get("severity"),
                    "blocking": value.get("blocking"),
                }
            )
        return prepared

    def _responsible_member(
        self,
        project,
        member_id: UUID,
    ) -> TrialProjectMemberReference:
        document = _optional_doc("NPI Project Member", str(member_id))
        today = datetime.now(UTC).date()
        if (
            document is None
            or str(document.global_id) != str(member_id)
            or str(document.tenant_id) != str(project.tenant_id)
            or str(document.project_global_id) != str(project.global_id)
            or not _member_effective(document, today)
        ):
            raise TrialReferenceUnavailable()
        user = frappe.db.get_value(
            "User",
            str(document.user_id),
            ["enabled", "user_type"],
            as_dict=True,
        )
        if (
            not user
            or int(_value(user, "enabled") or 0) != 1
            or str(_value(user, "user_type")) != "System User"
        ):
            raise TrialReferenceUnavailable()
        return TrialProjectMemberReference(
            global_id=member_id,
            user_id=str(document.user_id),
            optimistic_version=int(document.optimistic_version),
        )

    def _require_tooling(self, project, tooling_master_id: UUID) -> None:
        tooling = _optional_doc("NPI Tooling Master", str(tooling_master_id))
        if (
            tooling is None
            or str(tooling.global_id) != str(tooling_master_id)
            or str(tooling.tenant_id) != str(project.tenant_id)
            or not frappe.db.exists(
                "NPI Tooling Applicability",
                {
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "tooling_master_global_id": str(tooling_master_id),
                },
            )
        ):
            raise TrialReferenceUnavailable()

    @staticmethod
    def _require_measurement_document(
        project,
        measurement: TrialMeasurementPlanIntent,
    ) -> None:
        if measurement.document_revision_global_id is None:
            return
        document = _optional_doc(
            "NPI Document Revision",
            str(measurement.document_revision_global_id),
        )
        if (
            document is None
            or str(document.global_id)
            != str(measurement.document_revision_global_id)
            or str(document.tenant_id) != str(project.tenant_id)
            or str(document.project_global_id) != str(project.global_id)
            or str(document.snapshot_hash)
            != measurement.document_revision_snapshot_hash
            or int(document.optimistic_version)
            != measurement.document_optimistic_version
        ):
            raise TrialReferenceUnavailable()

    def _project_plan_revisions(self, project) -> list[TrialPlanRevision]:
        names = frappe.get_all(
            "NPI Trial Plan Revision",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
            },
            pluck="name",
            order_by="plan_global_id asc, plan_version asc, global_id asc",
            limit_page_length=_MAX_TOTAL_REVISIONS + 1,
        )
        if len(names) > _MAX_TOTAL_REVISIONS:
            raise RuntimeError("Persisted Trial revision collection exceeds its safe bound.")
        return [self._closed_plan_document(name, project) for name in names]

    def _current_plan_revision(
        self,
        project,
        plan_id: UUID,
        *,
        for_update: bool,
    ) -> TrialPlanRevision | None:
        names = frappe.get_all(
            "NPI Trial Plan Revision",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "plan_global_id": str(plan_id),
            },
            pluck="name",
            order_by="plan_version desc, global_id desc",
            limit_page_length=2,
        )
        if not names:
            return None
        document = frappe.get_doc(
            "NPI Trial Plan Revision",
            str(names[0]),
            for_update=for_update,
        )
        return self._closed_plan(document, project)

    def _exact_plan_revision(
        self,
        project,
        plan_id: UUID,
        revision_id: UUID,
        snapshot_hash: str,
    ) -> TrialPlanRevision | None:
        document = _optional_doc("NPI Trial Plan Revision", str(revision_id))
        if document is None:
            return None
        value = self._closed_plan(document, project)
        if value.plan_global_id != plan_id:
            return None
        if value.snapshot_hash != snapshot_hash:
            raise TrialVersionConflict()
        return value

    def _closed_plan_document(self, name: object, project) -> TrialPlanRevision:
        return self._closed_plan(
            frappe.get_doc("NPI Trial Plan Revision", str(name)),
            project,
        )

    @staticmethod
    def _closed_plan(document, project) -> TrialPlanRevision:
        value = trial_plan_from_snapshot(_json_object(document.plan_snapshot))
        if (
            str(value.global_id) != str(document.global_id)
            or str(value.tenant_id) != str(project.tenant_id)
            or str(value.project_global_id) != str(project.global_id)
            or value.snapshot_hash != str(document.snapshot_hash)
        ):
            raise RuntimeError("Persisted Trial Plan integrity failed.")
        return value

    def _plan_detail_for(self, project, plan_id: UUID) -> dict[str, Any] | None:
        names = frappe.get_all(
            "NPI Trial Plan Revision",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "plan_global_id": str(plan_id),
            },
            pluck="name",
            order_by="plan_version asc, global_id asc",
            limit_page_length=_MAX_PLAN_REVISIONS + 1,
        )
        if not names:
            return None
        if len(names) > _MAX_PLAN_REVISIONS:
            raise RuntimeError("Persisted Trial Plan history exceeds its safe bound.")
        revisions = [self._closed_plan_document(name, project) for name in names]
        round_names = frappe.get_all(
            "NPI Trial Round",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "trial_plan_global_id": str(plan_id),
            },
            pluck="name",
            order_by="round_sequence asc, global_id asc",
            limit_page_length=_MAX_ROUNDS + 1,
        )
        if len(round_names) > _MAX_ROUNDS:
            raise RuntimeError("Persisted Trial Round collection exceeds its safe bound.")
        rounds = [
            self._closed_round_document(name, project, plan_id)
            for name in round_names
        ]
        link_names = frappe.get_all(
            "NPI Trial Plan Work Link",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "trial_plan_global_id": str(plan_id),
            },
            pluck="name",
            order_by="created_at asc, global_id asc",
            limit_page_length=_MAX_ACTION_LINKS + 1,
        )
        if len(link_names) > _MAX_ACTION_LINKS:
            raise RuntimeError("Persisted Trial action link collection exceeds its safe bound.")
        links = [
            self._closed_link_document(name, project, plan_id)
            for name in link_names
        ]
        latest = max(revisions, key=lambda value: value.plan_version)
        return {
            "projectGlobalId": str(project.global_id),
            "planGlobalId": str(plan_id),
            "latestRevision": _plan_response(latest),
            "revisions": [_plan_response(value) for value in revisions],
            "rounds": [_round_response(value) for value in rounds],
            "actionLinks": [_link_response(value) for value in links],
            "capabilities": _unavailable_capabilities(),
            "permissions": self._permissions(),
        }

    def _closed_round_document(
        self,
        name: object,
        project,
        plan_id: UUID,
    ) -> TrialRound:
        document = frappe.get_doc("NPI Trial Round", str(name))
        value = trial_round_from_snapshot(_json_object(document.round_snapshot))
        if (
            str(value.global_id) != str(document.global_id)
            or str(value.tenant_id) != str(project.tenant_id)
            or str(value.project_global_id) != str(project.global_id)
            or value.trial_plan_global_id != plan_id
            or value.snapshot_hash != str(document.snapshot_hash)
        ):
            raise RuntimeError("Persisted Trial Round integrity failed.")
        return value

    def _closed_link_document(
        self,
        name: object,
        project,
        plan_id: UUID,
    ) -> TrialPlanWorkLink:
        document = frappe.get_doc("NPI Trial Plan Work Link", str(name))
        value = trial_work_link_from_snapshot(_json_object(document.link_snapshot))
        if (
            str(value.global_id) != str(document.global_id)
            or str(value.tenant_id) != str(project.tenant_id)
            or str(value.project_global_id) != str(project.global_id)
            or value.trial_plan_global_id != plan_id
            or value.snapshot_hash != str(document.snapshot_hash)
        ):
            raise RuntimeError("Persisted Trial work-link integrity failed.")
        return value

    def _round_document(self, project, plan_id: UUID, round_id: UUID):
        document = _optional_doc("NPI Trial Round", str(round_id))
        if document is None:
            return None
        value = trial_round_from_snapshot(_json_object(document.round_snapshot))
        if (
            value.global_id != round_id
            or value.trial_plan_global_id != plan_id
            or str(value.tenant_id) != str(project.tenant_id)
            or str(value.project_global_id) != str(project.global_id)
            or value.snapshot_hash != str(document.snapshot_hash)
        ):
            return None
        return document

    def _authorized_project(self, project_id: UUID):
        project = _optional_doc("NPI Engineering Project", str(project_id))
        return (
            project
            if project is not None and self._can_view_project(project, project_id)
            else None
        )

    def _locked_authorized_project(self, project_id: UUID):
        try:
            project = frappe.get_doc(
                "NPI Engineering Project",
                str(project_id),
                for_update=True,
            )
        except frappe.DoesNotExistError:
            return None
        if not self._can_administer_project(project, project_id):
            return None
        return project

    def _can_view_project(self, project, project_id: UUID) -> bool:
        if (
            self.principal.is_external
            or not self.principal.tenant_id
            or self.principal.tenant_id != str(project.tenant_id)
            or str(project.global_id) != str(project_id)
        ):
            return False
        if (
            self._is_internal_system_manager()
            or str(project.owner_user_id).casefold() == self.actor.casefold()
        ):
            return True
        return self._current_actor_member(project) is not None

    def _can_administer_project(self, project, project_id: UUID) -> bool:
        return bool(
            not self.principal.is_external
            and self.principal.tenant_id == str(project.tenant_id)
            and str(project.global_id) == str(project_id)
            and self._is_internal_system_manager()
        )

    def _is_internal_system_manager(self) -> bool:
        return bool(
            not self.principal.is_external and "System Manager" in self.principal.roles
        )

    def _current_actor_member(self, project):
        names = frappe.get_all(
            "NPI Project Member",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "user_id": self.actor,
            },
            pluck="name",
            order_by="global_id asc",
            limit_page_length=_MAX_MEMBERS + 1,
        )
        if len(names) > _MAX_MEMBERS:
            raise RuntimeError("Persisted Project member collection exceeds its safe bound.")
        today = datetime.now(UTC).date()
        matches = []
        for name in names:
            member = frappe.get_doc("NPI Project Member", str(name))
            if not _member_effective(member, today):
                continue
            user = frappe.db.get_value(
                "User",
                self.actor,
                ["enabled", "user_type"],
                as_dict=True,
            )
            if (
                user
                and int(_value(user, "enabled") or 0) == 1
                and str(_value(user, "user_type")) == "System User"
            ):
                matches.append(member)
        return matches[0] if len(matches) == 1 else None

    def _permissions(self) -> dict[str, bool]:
        allowed = self._is_internal_system_manager()
        return {
            "canCreatePlan": allowed,
            "canRevisePlan": allowed,
            "canCreateRound": allowed,
            "canGenerateActions": allowed,
        }

    def _idempotency_replay(
        self,
        project,
        operation: str,
        idempotency_key_hash: str,
        payload_hash: str,
    ) -> dict[str, Any] | None:
        receipt_key = _receipt_key(
            tenant_id=str(project.tenant_id),
            project_id=UUID(str(project.global_id)),
            actor=self.actor,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
        )
        record = frappe.db.get_value(
            "NPI Trial Command Idempotency",
            {"receipt_key": receipt_key},
            ["payload_hash", "response_payload", "sealed"],
            as_dict=True,
            for_update=True,
        )
        if not record:
            return None
        if str(_value(record, "payload_hash")) != payload_hash:
            raise TrialIdempotencyConflict()
        if int(_value(record, "sealed") or 0) != 1:
            raise RuntimeError("Persisted Trial idempotency receipt is unsealed.")
        return _json_object(_value(record, "response_payload"))

    def _insert_receipt(
        self,
        project,
        *,
        operation: str,
        idempotency_key_hash: str,
        payload_hash: str,
        created_at: datetime,
    ):
        receipt_key = _receipt_key(
            tenant_id=str(project.tenant_id),
            project_id=UUID(str(project.global_id)),
            actor=self.actor,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
        )
        try:
            return frappe.get_doc(
                {
                    "doctype": "NPI Trial Command Idempotency",
                    "global_id": str(uuid4()),
                    "receipt_key": receipt_key,
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "actor_user_id": self.actor,
                    "operation": operation,
                    "idempotency_key_hash": idempotency_key_hash,
                    "payload_hash": payload_hash,
                    "target_object_type": None,
                    "target_global_id": None,
                    "response_payload": {},
                    "response_hash": None,
                    "sealed": 0,
                    "created_at": _database_datetime(created_at),
                    "updated_at": _database_datetime(created_at),
                }
            ).insert()
        except (frappe.UniqueValidationError, frappe.DuplicateEntryError):
            frappe.db.rollback()
            replay = self._idempotency_replay(
                project,
                operation,
                idempotency_key_hash,
                payload_hash,
            )
            if replay is None:
                raise
            return replay

    @staticmethod
    def _seal_receipt(
        receipt,
        *,
        target_object_type: str,
        target_global_id: UUID,
        response: Mapping[str, Any],
        updated_at: datetime,
    ) -> None:
        receipt.target_object_type = target_object_type
        receipt.target_global_id = str(target_global_id)
        receipt.response_payload = dict(response)
        receipt.response_hash = sha256_json(response)
        receipt.sealed = 1
        receipt.updated_at = _database_datetime(updated_at)
        receipt.save()

    @staticmethod
    def _insert_plan_revision(value: TrialPlanRevision) -> None:
        frappe.get_doc(
            {
                "doctype": "NPI Trial Plan Revision",
                "global_id": str(value.global_id),
                "plan_global_id": str(value.plan_global_id),
                "version_key_hash": value.version_key_hash,
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "tooling_master_global_id": str(value.tooling_master_global_id),
                "tooling_master": str(value.tooling_master_global_id),
                "plan_version": value.plan_version,
                "predecessor_global_id": (
                    str(value.predecessor_global_id)
                    if value.predecessor_global_id is not None
                    else None
                ),
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "purpose": value.purpose.value,
                "objective": value.objective,
                "planned_start_at": _database_datetime(value.planned_start_at),
                "planned_end_at": _database_datetime(value.planned_end_at),
                "resource_proposal_snapshot": [
                    item.snapshot_payload() for item in value.resources
                ],
                "responsible_member_snapshot": [
                    item.snapshot_payload() for item in value.responsible_members
                ],
                "sample_quantity": value.sample_quantity,
                "measurement_plan_snapshot": value.measurement_plan.snapshot_payload(),
                "reason": value.reason,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "plan_snapshot": value.snapshot_payload(),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    @staticmethod
    def _insert_round_event(value) -> None:
        frappe.get_doc(
            {
                "doctype": "NPI Trial Round Lifecycle Event",
                "global_id": str(value.global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "trial_round_global_id": str(value.trial_round_global_id),
                "event_version": value.event_version,
                "event_type": value.event_type.value,
                "from_state": value.from_state.value if value.from_state else None,
                "to_state": value.to_state.value,
                "reason": value.reason,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "event_snapshot": value.snapshot_payload(),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    @staticmethod
    def _insert_round(value: TrialRound) -> None:
        frappe.get_doc(
            {
                "doctype": "NPI Trial Round",
                "global_id": str(value.global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "trial_plan_global_id": str(value.trial_plan_global_id),
                "trial_plan_revision": str(value.trial_plan_revision_global_id),
                "trial_plan_revision_global_id": str(
                    value.trial_plan_revision_global_id
                ),
                "trial_plan_revision_snapshot_hash": (
                    value.trial_plan_revision_snapshot_hash
                ),
                "tooling_master": str(value.tooling_master_global_id),
                "tooling_master_global_id": str(value.tooling_master_global_id),
                "round_sequence": value.round_sequence,
                "display_label": value.display_label,
                "purpose": value.purpose.value,
                "planned_start_at": _database_datetime(value.planned_start_at),
                "planned_end_at": _database_datetime(value.planned_end_at),
                "current_state": value.current_state.value,
                "current_event_global_id": str(value.current_event_global_id),
                "optimistic_version": value.optimistic_version,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "round_snapshot": value.snapshot_payload(),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    @staticmethod
    def _insert_work_link(value: TrialPlanWorkLink) -> None:
        frappe.get_doc(
            {
                "doctype": "NPI Trial Plan Work Link",
                "global_id": str(value.global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "trial_plan_global_id": str(value.trial_plan_global_id),
                "trial_plan_revision": str(value.trial_plan_revision_global_id),
                "trial_plan_revision_global_id": str(
                    value.trial_plan_revision_global_id
                ),
                "trial_plan_revision_snapshot_hash": (
                    value.trial_plan_revision_snapshot_hash
                ),
                "trial_round": (
                    str(value.trial_round_global_id)
                    if value.trial_round_global_id is not None
                    else None
                ),
                "trial_round_global_id": (
                    str(value.trial_round_global_id)
                    if value.trial_round_global_id is not None
                    else None
                ),
                "domain_work_item": str(value.domain_work_item_global_id),
                "domain_work_item_global_id": str(value.domain_work_item_global_id),
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "link_snapshot": value.snapshot_payload(),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    def _append_audit(
        self,
        *,
        operation: str,
        global_id: UUID,
        object_version: int,
        summary: Mapping[str, Any],
    ) -> None:
        event = create_audit_event(
            actor=self.actor,
            trace_id=self.trace_id,
            operation=operation,
            global_id=global_id,
            object_version=object_version,
            result="created",
            input_summary=summary,
        )
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
        ).insert()

    @staticmethod
    def _bounded_count(
        doctype: str,
        filters: Mapping[str, Any],
        maximum: int,
    ) -> int:
        count = int(frappe.db.count(doctype, filters=dict(filters)))
        if count > maximum:
            raise RuntimeError(f"Persisted {doctype} collection exceeds its safe bound.")
        return count


def _plan_response(value: TrialPlanRevision) -> dict[str, Any]:
    return {
        "globalId": str(value.global_id),
        "planGlobalId": str(value.plan_global_id),
        "projectGlobalId": str(value.project_global_id),
        "toolingMasterGlobalId": str(value.tooling_master_global_id),
        "planVersion": value.plan_version,
        "predecessorGlobalId": (
            str(value.predecessor_global_id)
            if value.predecessor_global_id is not None
            else None
        ),
        "predecessorSnapshotHash": value.predecessor_snapshot_hash,
        "purpose": value.purpose.value,
        "objective": value.objective,
        "plannedStartAt": _datetime_iso(value.planned_start_at),
        "plannedEndAt": _datetime_iso(value.planned_end_at),
        "resources": [item.snapshot_payload() for item in value.resources],
        "responsibleMembers": [
            item.snapshot_payload() for item in value.responsible_members
        ],
        "sampleQuantity": value.sample_quantity,
        "measurementPlan": value.measurement_plan.snapshot_payload(),
        "reason": value.reason,
        "createdByUserId": value.created_by_user_id,
        "createdAt": _datetime_iso(value.created_at),
        "snapshotHash": value.snapshot_hash,
    }


def _round_response(value: TrialRound) -> dict[str, Any]:
    return {
        "globalId": str(value.global_id),
        "projectGlobalId": str(value.project_global_id),
        "trialPlanGlobalId": str(value.trial_plan_global_id),
        "trialPlanRevisionGlobalId": str(value.trial_plan_revision_global_id),
        "trialPlanRevisionSnapshotHash": value.trial_plan_revision_snapshot_hash,
        "toolingMasterGlobalId": str(value.tooling_master_global_id),
        "roundSequence": value.round_sequence,
        "displayLabel": value.display_label,
        "purpose": value.purpose.value,
        "plannedStartAt": _datetime_iso(value.planned_start_at),
        "plannedEndAt": _datetime_iso(value.planned_end_at),
        "currentState": value.current_state.value,
        "optimisticVersion": value.optimistic_version,
        "createdByUserId": value.created_by_user_id,
        "createdAt": _datetime_iso(value.created_at),
        "snapshotHash": value.snapshot_hash,
    }


def _link_response(value: TrialPlanWorkLink) -> dict[str, Any]:
    return {
        "globalId": str(value.global_id),
        "projectGlobalId": str(value.project_global_id),
        "trialPlanGlobalId": str(value.trial_plan_global_id),
        "trialPlanRevisionGlobalId": str(value.trial_plan_revision_global_id),
        "trialPlanRevisionSnapshotHash": value.trial_plan_revision_snapshot_hash,
        "trialRoundGlobalId": (
            str(value.trial_round_global_id)
            if value.trial_round_global_id is not None
            else None
        ),
        "domainWorkItemGlobalId": str(value.domain_work_item_global_id),
        "createdByUserId": value.created_by_user_id,
        "createdAt": _datetime_iso(value.created_at),
        "snapshotHash": value.snapshot_hash,
    }


def _unavailable_capabilities() -> list[dict[str, str]]:
    return [
        {
            "key": "resource_availability",
            "availability": "unavailable",
            "reasonCode": "approved_resource_reader_not_configured",
        },
        {
            "key": "resource_reservation",
            "availability": "unavailable",
            "reasonCode": "approved_booking_policy_not_configured",
        },
    ]


def _receipt_key(
    *,
    tenant_id: str,
    project_id: UUID,
    actor: str,
    operation: str,
    idempotency_key_hash: str,
) -> str:
    return sha256_json(
        {
            "tenantId": tenant_id,
            "projectGlobalId": str(project_id),
            "actorUserId": actor.casefold(),
            "operation": operation,
            "idempotencyKeyHash": idempotency_key_hash,
        }
    )


def _payload_hash(value: object) -> str:
    return sha256_json(_json_value(value))


def _json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_value(item) for item in value]
    if isinstance(value, datetime):
        return _datetime_iso(value)
    if isinstance(value, UUID):
        return str(value)
    enum_value = getattr(value, "value", value)
    return enum_value


def _json_object(value: object) -> dict[str, Any]:
    if isinstance(value, str):
        import json

        value = json.loads(value)
    if not isinstance(value, Mapping):
        raise RuntimeError("Persisted Trial response is invalid.")
    return dict(value)


def _is_replay_response(value: object) -> bool:
    return isinstance(value, dict) and not callable(getattr(value, "save", None))


def _enum_value(value: object, enum_type, path: str):
    try:
        return enum_type(str(getattr(value, "value", value)))
    except (TypeError, ValueError) as error:
        raise _field_problem(path, _("Select a supported value.")) from error


def _optional_doc(doctype: str, name: str):
    try:
        return frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        return None


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


def _value(record: object, fieldname: str) -> object:
    if isinstance(record, Mapping):
        return record.get(fieldname)
    return getattr(record, fieldname, None)


def _member_effective(member, today: date) -> bool:
    starts = _date(member.effective_from)
    ends = _date(member.effective_to) if member.effective_to else None
    return starts <= today and (ends is None or today <= ends)


def _date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _datetime_iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _database_datetime(value: datetime) -> str:
    return value.astimezone(UTC).replace(tzinfo=None).isoformat(
        sep=" ",
        timespec="microseconds",
    )
