from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

import frappe

from npi_core.tooling.domain import (
    ToolingReferenceUnavailable,
    ToolingVersionConflict,
)
from npi_core.tooling.engineering_controls_domain import (
    CapacityInputProvenance,
    CapacityProvenanceKind,
    ProcessComparisonRuleSnapshot,
    ToolingCapacityLineInput,
    ToolingCapacityScenarioRevision,
    ToolingDefectAction,
    ToolingDefectContextKind,
    ToolingDefectDetectionContext,
    ToolingDefectFileEvidence,
    ToolingDefectRevision,
    ToolingDefectRootCauseState,
    ToolingDefectSeverity,
    ToolingDefectState,
    ToolingHealthUnavailable,
    ToolingProcessContextEvidence,
    ToolingProcessContextKind,
    ToolingProcessLayer,
    ToolingProcessMetric,
    ToolingProcessProfileRevision,
    capacity_scenario_from_snapshot,
    compare_process_metric,
    defect_revision_from_snapshot,
    process_profile_from_snapshot,
    validate_capacity_scenario_successor,
    validate_process_profile_successor,
    validate_tooling_defect_successor,
)
from npi_core.tooling.frappe_validation import tooling_command_write


_MAX_DEFECT_REVISIONS = 1_000
_MAX_PROCESS_PROFILE_REVISIONS = 500
_MAX_CAPACITY_SCENARIO_REVISIONS = 500


@dataclass(frozen=True, slots=True)
class EngineeringControlsCommandOutcome:
    response: dict[str, Any]
    replayed: bool = False


class ToolingEngineeringControlsRepositoryMixin:
    """Project-first persistence for immutable P6-05 engineering controls."""

    def tooling_engineering_controls(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        if self._master_for_project(project, tooling_master_id) is None:
            return None
        defects = self._engineering_defects(project, tooling_master_id)
        profiles = self._engineering_process_profiles(project, tooling_master_id)
        scenarios = self._engineering_capacity_scenarios(project, tooling_master_id)
        latest_profiles = _latest_process_profiles(profiles)
        comparisons = [
            compare_process_metric(
                ToolingProcessLayer.CUSTOMER_STANDARD,
                metric,
                None,
            ).snapshot_payload()
            for profile in latest_profiles
            for metric in profile.metrics
        ]
        create = self._is_internal_system_manager()
        return {
            "projectGlobalId": str(project.global_id),
            "toolingMasterGlobalId": str(tooling_master_id),
            "permissions": {
                "view": True,
                "reviseDefect": create,
                "createCustomerStandard": create,
                "createCapacityScenario": create,
                "createTrialActual": False,
                "approveProcessBaseline": False,
                "editHealth": False,
                "transitionGate": False,
                "transitionToolingLifecycle": False,
            },
            "defectRevisions": [_defect_response(value) for value in defects],
            "process": {
                "customerStandardRevisions": [
                    _process_profile_response(value) for value in profiles
                ],
                "trialActual": {
                    "state": "not_measured",
                    "reasonCode": "trial_context_unavailable",
                },
                "approvedBaseline": {
                    "state": "unavailable",
                    "reasonCode": "approved_trial_evidence_unavailable",
                },
                "comparisons": comparisons,
            },
            "capacityScenarioRevisions": [
                _capacity_scenario_response(value) for value in scenarios
            ],
            "health": ToolingHealthUnavailable().snapshot_payload(),
        }

    def create_tooling_defect_revision(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        *,
        idempotency_key_hash: str,
        defect_id: UUID | None,
        expected_version: int | None,
        tooling_revision_id: UUID,
        tooling_revision_snapshot_hash: str,
        cavity_id: UUID | None,
        business_code: str,
        title: str,
        description: str,
        category_key: str,
        severity: ToolingDefectSeverity,
        blocking: bool,
        state: ToolingDefectState,
        detection_context: Mapping[str, object],
        root_cause_state: ToolingDefectRootCauseState,
        root_cause: str | None,
        responsible_member: object | None,
        target_round_label: str | None,
        actions: Sequence[Mapping[str, object]],
        evidence: Sequence[Mapping[str, object]],
        reason: str,
    ) -> EngineeringControlsCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "toolingMasterGlobalId": str(tooling_master_id),
            "defectGlobalId": str(defect_id) if defect_id else None,
            "expectedVersion": expected_version,
            "toolingRevisionGlobalId": str(tooling_revision_id),
            "toolingRevisionSnapshotHash": tooling_revision_snapshot_hash,
            "cavityGlobalId": str(cavity_id) if cavity_id else None,
            "businessCode": business_code,
            "title": title,
            "description": description,
            "categoryKey": category_key,
            "severity": severity.value,
            "blocking": blocking,
            "state": state.value,
            "detectionContext": _command_payload(detection_context),
            "rootCauseState": root_cause_state.value,
            "rootCause": root_cause,
            "responsibleMember": (
                responsible_member.snapshot_payload()
                if responsible_member is not None
                else None
            ),
            "targetRoundLabel": target_round_label,
            "actions": [_command_payload(value) for value in actions],
            "evidence": [_command_payload(value) for value in evidence],
            "reason": reason,
        }
        context = self._command_context(
            project,
            operation="tooling_defect.revise",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(context, dict):
            return EngineeringControlsCommandOutcome(context, replayed=True)
        receipt_key, payload_hash = context
        if self._master_for_project(project, tooling_master_id) is None:
            raise ToolingReferenceUnavailable()
        revision = self._tooling_revision_for_project(
            project,
            tooling_revision_id,
            tooling_master_id=tooling_master_id,
        )
        if revision is None or revision.snapshot_hash != tooling_revision_snapshot_hash:
            raise ToolingReferenceUnavailable()
        cavity_identifier = self._exact_cavity_identifier(revision, cavity_id)
        stable_id, predecessor = self._defect_predecessor(
            project,
            tooling_master_id,
            defect_id,
            expected_version,
        )
        exact_member = self._exact_engineering_member(project, responsible_member)
        exact_context = self._exact_detection_context(
            project,
            tooling_master_id,
            revision,
            detection_context,
        )
        exact_actions = self._defect_actions(project, predecessor, actions)
        retained_evidence = predecessor.evidence if predecessor else ()
        exact_evidence = retained_evidence + tuple(
            self._defect_file_evidence(project, value) for value in evidence
        )
        now = self._now()
        value = ToolingDefectRevision(
            global_id=self._new_uuid(),
            defect_global_id=stable_id,
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            tooling_master_global_id=tooling_master_id,
            tooling_revision_global_id=revision.global_id,
            tooling_revision_snapshot_hash=revision.snapshot_hash,
            cavity_global_id=cavity_id,
            cavity_identifier=cavity_identifier,
            defect_version=1 if predecessor is None else predecessor.defect_version + 1,
            predecessor_global_id=predecessor.global_id if predecessor else None,
            predecessor_snapshot_hash=predecessor.snapshot_hash if predecessor else None,
            business_code=business_code,
            title=title,
            description=description,
            category_key=category_key,
            severity=severity,
            blocking=blocking,
            state=state,
            detection_context=exact_context,
            root_cause_state=root_cause_state,
            root_cause=root_cause,
            responsible_member=exact_member,
            target_round_label=target_round_label,
            actions=exact_actions,
            evidence=exact_evidence,
            reason=reason,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        if predecessor is not None:
            validate_tooling_defect_successor(predecessor, value)
        response = {"defect": _defect_response(value)}
        with tooling_command_write():
            receipt = self._insert_receipt(
                project,
                receipt_key=receipt_key,
                operation="tooling_defect.revise",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._insert_engineering_defect(value)
            self._append_audit(
                operation="tooling_defect.revise",
                global_id=value.global_id,
                object_version=value.defect_version,
                summary={
                    "defectGlobalId": str(value.defect_global_id),
                    "state": value.state.value,
                    "blocking": value.blocking,
                    "snapshotHash": value.snapshot_hash,
                },
            )
            self._seal_receipt(
                receipt,
                target_type="tooling_defect_revision",
                target_id=value.global_id,
                response=response,
                now=now,
            )
        return EngineeringControlsCommandOutcome(response)

    def create_tooling_process_profile_revision(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        *,
        idempotency_key_hash: str,
        profile_id: UUID | None,
        expected_version: int | None,
        tooling_revision_id: UUID,
        tooling_revision_snapshot_hash: str,
        context: Mapping[str, object],
        effective_from: date,
        metrics: Sequence[Mapping[str, object]],
        reason: str,
    ) -> EngineeringControlsCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "toolingMasterGlobalId": str(tooling_master_id),
            "profileGlobalId": str(profile_id) if profile_id else None,
            "expectedVersion": expected_version,
            "toolingRevisionGlobalId": str(tooling_revision_id),
            "toolingRevisionSnapshotHash": tooling_revision_snapshot_hash,
            "context": _command_payload(context),
            "effectiveFrom": effective_from.isoformat(),
            "metrics": [_command_payload(value) for value in metrics],
            "reason": reason,
        }
        command_context = self._command_context(
            project,
            operation="tooling_process_profile.create",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(command_context, dict):
            return EngineeringControlsCommandOutcome(command_context, replayed=True)
        receipt_key, payload_hash = command_context
        if self._master_for_project(project, tooling_master_id) is None:
            raise ToolingReferenceUnavailable()
        revision = self._tooling_revision_for_project(
            project,
            tooling_revision_id,
            tooling_master_id=tooling_master_id,
        )
        if revision is None or revision.snapshot_hash != tooling_revision_snapshot_hash:
            raise ToolingReferenceUnavailable()
        stable_id, predecessor = self._process_profile_predecessor(
            project,
            tooling_master_id,
            profile_id,
            expected_version,
        )
        exact_context = self._exact_process_context(project, revision, context)
        exact_metrics = self._process_metrics(predecessor, metrics)
        now = self._now()
        value = ToolingProcessProfileRevision(
            global_id=self._new_uuid(),
            profile_global_id=stable_id,
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            tooling_master_global_id=tooling_master_id,
            tooling_revision_global_id=revision.global_id,
            tooling_revision_snapshot_hash=revision.snapshot_hash,
            layer=ToolingProcessLayer.CUSTOMER_STANDARD,
            profile_version=1 if predecessor is None else predecessor.profile_version + 1,
            predecessor_global_id=predecessor.global_id if predecessor else None,
            predecessor_snapshot_hash=predecessor.snapshot_hash if predecessor else None,
            context=exact_context,
            effective_from=effective_from,
            metrics=exact_metrics,
            reason=reason,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        if predecessor is not None:
            validate_process_profile_successor(predecessor, value)
        response = {"profile": _process_profile_response(value)}
        with tooling_command_write():
            receipt = self._insert_receipt(
                project,
                receipt_key=receipt_key,
                operation="tooling_process_profile.create",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._insert_engineering_process_profile(value)
            self._append_audit(
                operation="tooling_process_profile.create",
                global_id=value.global_id,
                object_version=value.profile_version,
                summary={
                    "profileGlobalId": str(value.profile_global_id),
                    "layer": value.layer.value,
                    "snapshotHash": value.snapshot_hash,
                },
            )
            self._seal_receipt(
                receipt,
                target_type="tooling_process_profile_revision",
                target_id=value.global_id,
                response=response,
                now=now,
            )
        return EngineeringControlsCommandOutcome(response)

    def create_tooling_capacity_scenario_revision(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        *,
        idempotency_key_hash: str,
        scenario_id: UUID | None,
        expected_version: int | None,
        title: str,
        effective_from: date,
        target_monthly_assembly_units: str,
        lines: Sequence[Mapping[str, object]],
        reason: str,
    ) -> EngineeringControlsCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "toolingMasterGlobalId": str(tooling_master_id),
            "scenarioGlobalId": str(scenario_id) if scenario_id else None,
            "expectedVersion": expected_version,
            "title": title,
            "effectiveFrom": effective_from.isoformat(),
            "targetMonthlyAssemblyUnits": target_monthly_assembly_units,
            "lines": [_command_payload(value) for value in lines],
            "reason": reason,
        }
        command_context = self._command_context(
            project,
            operation="tooling_capacity_scenario.create",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(command_context, dict):
            return EngineeringControlsCommandOutcome(command_context, replayed=True)
        receipt_key, payload_hash = command_context
        if self._master_for_project(project, tooling_master_id) is None:
            raise ToolingReferenceUnavailable()
        stable_id, predecessor = self._capacity_scenario_predecessor(
            project,
            tooling_master_id,
            scenario_id,
            expected_version,
        )
        exact_lines = self._capacity_lines(
            project,
            tooling_master_id,
            predecessor,
            lines,
        )
        now = self._now()
        value = ToolingCapacityScenarioRevision(
            global_id=self._new_uuid(),
            scenario_global_id=stable_id,
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            tooling_master_global_id=tooling_master_id,
            scenario_version=1 if predecessor is None else predecessor.scenario_version + 1,
            predecessor_global_id=predecessor.global_id if predecessor else None,
            predecessor_snapshot_hash=predecessor.snapshot_hash if predecessor else None,
            title=title,
            effective_from=effective_from,
            target_monthly_assembly_units=target_monthly_assembly_units,
            lines=exact_lines,
            reason=reason,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        if predecessor is not None:
            validate_capacity_scenario_successor(predecessor, value)
        response = {"scenario": _capacity_scenario_response(value)}
        with tooling_command_write():
            receipt = self._insert_receipt(
                project,
                receipt_key=receipt_key,
                operation="tooling_capacity_scenario.create",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._insert_engineering_capacity_scenario(value)
            self._append_audit(
                operation="tooling_capacity_scenario.create",
                global_id=value.global_id,
                object_version=value.scenario_version,
                summary={
                    "scenarioGlobalId": str(value.scenario_global_id),
                    "formulaVersion": "capacity.v1",
                    "snapshotHash": value.snapshot_hash,
                },
            )
            self._seal_receipt(
                receipt,
                target_type="tooling_capacity_scenario_revision",
                target_id=value.global_id,
                response=response,
                now=now,
            )
        return EngineeringControlsCommandOutcome(response)

    def _engineering_defects(
        self,
        project: object,
        tooling_master_id: UUID,
        *,
        defect_id: UUID | None = None,
    ) -> tuple[ToolingDefectRevision, ...]:
        filters: dict[str, object] = {
            "tenant_id": str(project.tenant_id),
            "project_global_id": str(project.global_id),
            "tooling_master_global_id": str(tooling_master_id),
        }
        if defect_id is not None:
            filters["defect_global_id"] = str(defect_id)
        rows = self._bounded_documents(
            "NPI Tooling Defect Revision",
            filters=filters,
            maximum=_MAX_DEFECT_REVISIONS,
        )
        values = tuple(
            defect_revision_from_snapshot(_json_object(row.defect_snapshot))
            for row in rows
        )
        _validate_chains(
            values,
            group=lambda value: value.defect_global_id,
            version=lambda value: value.defect_version,
            validate=validate_tooling_defect_successor,
            label="Tooling defect",
        )
        return tuple(
            sorted(
                values,
                key=lambda value: (str(value.defect_global_id), value.defect_version),
            )
        )

    def _engineering_process_profiles(
        self,
        project: object,
        tooling_master_id: UUID,
        *,
        profile_id: UUID | None = None,
    ) -> tuple[ToolingProcessProfileRevision, ...]:
        filters: dict[str, object] = {
            "tenant_id": str(project.tenant_id),
            "project_global_id": str(project.global_id),
            "tooling_master_global_id": str(tooling_master_id),
            "layer": ToolingProcessLayer.CUSTOMER_STANDARD.value,
        }
        if profile_id is not None:
            filters["profile_global_id"] = str(profile_id)
        rows = self._bounded_documents(
            "NPI Tooling Process Profile Revision",
            filters=filters,
            maximum=_MAX_PROCESS_PROFILE_REVISIONS,
        )
        values = tuple(
            process_profile_from_snapshot(_json_object(row.profile_snapshot))
            for row in rows
        )
        if any(value.layer is not ToolingProcessLayer.CUSTOMER_STANDARD for value in values):
            raise RuntimeError("The process profile layer filter drifted.")
        _validate_chains(
            values,
            group=lambda value: value.profile_global_id,
            version=lambda value: value.profile_version,
            validate=validate_process_profile_successor,
            label="process profile",
        )
        return tuple(
            sorted(
                values,
                key=lambda value: (str(value.profile_global_id), value.profile_version),
            )
        )

    def _engineering_capacity_scenarios(
        self,
        project: object,
        tooling_master_id: UUID,
        *,
        scenario_id: UUID | None = None,
    ) -> tuple[ToolingCapacityScenarioRevision, ...]:
        filters: dict[str, object] = {
            "tenant_id": str(project.tenant_id),
            "project_global_id": str(project.global_id),
            "tooling_master_global_id": str(tooling_master_id),
        }
        if scenario_id is not None:
            filters["scenario_global_id"] = str(scenario_id)
        rows = self._bounded_documents(
            "NPI Tooling Capacity Scenario Revision",
            filters=filters,
            maximum=_MAX_CAPACITY_SCENARIO_REVISIONS,
        )
        values = tuple(
            capacity_scenario_from_snapshot(_json_object(row.scenario_snapshot))
            for row in rows
        )
        _validate_chains(
            values,
            group=lambda value: value.scenario_global_id,
            version=lambda value: value.scenario_version,
            validate=validate_capacity_scenario_successor,
            label="Capacity Scenario",
        )
        return tuple(
            sorted(
                values,
                key=lambda value: (str(value.scenario_global_id), value.scenario_version),
            )
        )

    def _defect_predecessor(
        self,
        project: object,
        tooling_master_id: UUID,
        defect_id: UUID | None,
        expected_version: int | None,
    ) -> tuple[UUID, ToolingDefectRevision | None]:
        if defect_id is None:
            if expected_version is not None:
                raise ToolingVersionConflict()
            return self._new_uuid(), None
        trial_successors = frappe.get_all(
            "NPI Trial Defect Revision",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "defect_global_id": str(defect_id),
            },
            pluck="name",
            order_by="defect_version desc, global_id desc",
            limit_page_length=1,
        )
        if trial_successors:
            # The Project row is already locked by the command boundary. Once the
            # shared defect has entered its Trial stream, P6 must never append a
            # parallel Tooling tip.
            raise ToolingVersionConflict()
        chain = self._engineering_defects(
            project,
            tooling_master_id,
            defect_id=defect_id,
        )
        if not chain or expected_version != chain[-1].defect_version:
            raise ToolingVersionConflict()
        return defect_id, chain[-1]

    def _process_profile_predecessor(
        self,
        project: object,
        tooling_master_id: UUID,
        profile_id: UUID | None,
        expected_version: int | None,
    ) -> tuple[UUID, ToolingProcessProfileRevision | None]:
        if profile_id is None:
            if expected_version is not None:
                raise ToolingVersionConflict()
            return self._new_uuid(), None
        chain = self._engineering_process_profiles(
            project,
            tooling_master_id,
            profile_id=profile_id,
        )
        if not chain or expected_version != chain[-1].profile_version:
            raise ToolingVersionConflict()
        return profile_id, chain[-1]

    def _capacity_scenario_predecessor(
        self,
        project: object,
        tooling_master_id: UUID,
        scenario_id: UUID | None,
        expected_version: int | None,
    ) -> tuple[UUID, ToolingCapacityScenarioRevision | None]:
        if scenario_id is None:
            if expected_version is not None:
                raise ToolingVersionConflict()
            return self._new_uuid(), None
        chain = self._engineering_capacity_scenarios(
            project,
            tooling_master_id,
            scenario_id=scenario_id,
        )
        if not chain or expected_version != chain[-1].scenario_version:
            raise ToolingVersionConflict()
        return scenario_id, chain[-1]

    @staticmethod
    def _exact_cavity_identifier(revision: object, cavity_id: UUID | None) -> str | None:
        if cavity_id is None:
            return None
        matches = [
            value
            for value in revision.cavities
            if value.global_id == cavity_id
        ]
        if len(matches) != 1:
            raise ToolingReferenceUnavailable()
        return matches[0].cavity_identifier

    def _exact_engineering_member(
        self,
        project: object,
        supplied: object | None,
    ):
        if supplied is None:
            return None
        exact = self._active_member(project, supplied.global_id)
        if exact != supplied:
            raise ToolingReferenceUnavailable()
        return exact

    def _exact_detection_context(
        self,
        project: object,
        tooling_master_id: UUID,
        revision: object,
        supplied: Mapping[str, object],
    ) -> ToolingDefectDetectionContext:
        kind = supplied["kind"]
        global_id = supplied.get("global_id")
        snapshot_hash = supplied.get("snapshot_hash")
        if kind is ToolingDefectContextKind.UNAVAILABLE_TRIAL_CONTEXT:
            return ToolingDefectDetectionContext(kind=kind, global_id=None, snapshot_hash=None)
        if global_id is None or snapshot_hash is None:
            raise ToolingReferenceUnavailable()
        if kind is ToolingDefectContextKind.TOOLING_REVISION:
            if global_id != revision.global_id or snapshot_hash != revision.snapshot_hash:
                raise ToolingReferenceUnavailable()
        elif kind is ToolingDefectContextKind.MANUFACTURING_MILESTONE_OBSERVATION:
            row = _optional_doc(
                "NPI Tooling Manufacturing Milestone Observation",
                str(global_id),
            )
            if row is None or any(
                (
                    str(row.global_id) != str(global_id),
                    str(row.tenant_id) != str(project.tenant_id),
                    str(row.project_global_id) != str(project.global_id),
                    str(row.tooling_master_global_id) != str(tooling_master_id),
                    str(row.snapshot_hash) != str(snapshot_hash),
                )
            ):
                raise ToolingReferenceUnavailable()
        elif kind is ToolingDefectContextKind.TOOLING_INTAKE:
            row = _optional_doc("NPI Tooling Intake", str(global_id))
            if row is None or any(
                (
                    str(row.global_id) != str(global_id),
                    str(row.tenant_id) != str(project.tenant_id),
                    str(row.project_global_id) != str(project.global_id),
                    str(row.tooling_master_global_id) != str(tooling_master_id),
                    str(row.snapshot_hash) != str(snapshot_hash),
                )
            ):
                raise ToolingReferenceUnavailable()
        else:
            raise ToolingReferenceUnavailable()
        return ToolingDefectDetectionContext(
            kind=kind,
            global_id=global_id,
            snapshot_hash=str(snapshot_hash),
        )

    def _defect_actions(
        self,
        project: object,
        predecessor: ToolingDefectRevision | None,
        supplied: Sequence[Mapping[str, object]],
    ) -> tuple[ToolingDefectAction, ...]:
        previous = {value.global_id: value for value in predecessor.actions} if predecessor else {}
        updates: dict[UUID, ToolingDefectAction] = {}
        additions: list[ToolingDefectAction] = []
        for item in supplied:
            supplied_id = item.get("global_id")
            if supplied_id is not None and supplied_id not in previous:
                raise ToolingReferenceUnavailable()
            current = previous.get(supplied_id) if supplied_id is not None else None
            member = self._exact_engineering_member(project, item["responsible_member"])
            retained = current.evidence if current else ()
            action = ToolingDefectAction(
                global_id=current.global_id if current else self._new_uuid(),
                action_type=item["action_type"],
                state=item["state"],
                detail=str(item["detail"]),
                responsible_member=member,
                due_date=item["due_date"],
                evidence=retained
                + tuple(
                    self._defect_file_evidence(project, value)
                    for value in item["evidence"]
                ),
            )
            if current:
                updates[current.global_id] = action
            else:
                additions.append(action)
        retained_actions = [updates.get(value.global_id, value) for value in previous.values()]
        return tuple(retained_actions + additions)

    def _defect_file_evidence(
        self,
        project: object,
        supplied: Mapping[str, object],
    ) -> ToolingDefectFileEvidence:
        row = self._file_revision_for_project(project, supplied["file_revision_id"])
        if row is None or any(
            (
                int(row.optimistic_version) != supplied["file_optimistic_version"],
                str(row.frappe_content_hash) != supplied["frappe_content_hash"],
                str(row.sha256) != supplied["sha256"],
            )
        ):
            raise ToolingReferenceUnavailable()
        return ToolingDefectFileEvidence(
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

    def _exact_process_context(
        self,
        project: object,
        revision: object,
        supplied: Mapping[str, object],
    ) -> ToolingProcessContextEvidence:
        kind = supplied["kind"]
        global_id = supplied["global_id"]
        snapshot_hash = str(supplied["snapshot_hash"])
        if kind is ToolingProcessContextKind.TOOLING_REVISION_SPECIFICATION:
            if global_id != revision.global_id or snapshot_hash != revision.snapshot_hash:
                raise ToolingReferenceUnavailable()
            return ToolingProcessContextEvidence(
                kind=kind,
                global_id=global_id,
                snapshot_hash=snapshot_hash,
            )
        if kind is ToolingProcessContextKind.RELEASED_DOCUMENT:
            evidence = self._released_document_evidence(project, global_id)
            if evidence is None or evidence.revision_snapshot_hash != snapshot_hash:
                raise ToolingReferenceUnavailable()
            return ToolingProcessContextEvidence(
                kind=kind,
                global_id=global_id,
                snapshot_hash=snapshot_hash,
                released_document=evidence,
            )
        raise ToolingReferenceUnavailable()

    def _process_metrics(
        self,
        predecessor: ToolingProcessProfileRevision | None,
        supplied: Sequence[Mapping[str, object]],
    ) -> tuple[ToolingProcessMetric, ...]:
        previous = {value.code: value for value in predecessor.metrics} if predecessor else {}
        result = []
        for item in supplied:
            code = item["code"]
            current = previous.get(code)
            rule_input = item.get("comparison_rule")
            rule = None
            if rule_input is not None:
                current_rule = current.comparison_rule if current else None
                unchanged = bool(
                    current_rule
                    and current_rule.unit == rule_input["unit"]
                    and current_rule.minimum == rule_input["minimum"]
                    and current_rule.maximum == rule_input["maximum"]
                )
                rule = (
                    current_rule
                    if unchanged
                    else ProcessComparisonRuleSnapshot(
                        global_id=(
                            current_rule.global_id if current_rule else self._new_uuid()
                        ),
                        rule_version=(
                            current_rule.rule_version + 1 if current_rule else 1
                        ),
                        unit=str(rule_input["unit"]),
                        minimum=str(rule_input["minimum"]),
                        maximum=str(rule_input["maximum"]),
                    )
                )
            result.append(
                ToolingProcessMetric(
                    global_id=current.global_id if current else self._new_uuid(),
                    code=code,
                    value_kind=item["value_kind"],
                    numeric_value=item.get("numeric_value"),
                    text_value=item.get("text_value"),
                    unit=item.get("unit"),
                    comparison_rule=rule,
                )
            )
        return tuple(result)

    def _capacity_lines(
        self,
        project: object,
        tooling_master_id: UUID,
        predecessor: ToolingCapacityScenarioRevision | None,
        supplied: Sequence[Mapping[str, object]],
    ) -> tuple[ToolingCapacityLineInput, ...]:
        previous = {
            value.applicability_global_id: value for value in predecessor.lines
        } if predecessor else {}
        applications = {
            value.global_id: value
            for value in self._applicabilities(project)
            if value.tooling_master_global_id == tooling_master_id
        }
        tooling_sets = {
            value.global_id: value
            for value in self._tooling_sets_for_master(project, tooling_master_id)
        }
        customer_standards = {
            value.global_id: value
            for value in self._engineering_process_profiles(project, tooling_master_id)
        }
        revision_cache: dict[UUID, object] = {}
        result = []
        for item in supplied:
            part = self._part_revision_for_project(
                project,
                item["part_revision_id"],
                require_current=False,
            )
            application = applications.get(item["applicability_id"])
            if (
                part is None
                or part.snapshot_hash != item["part_revision_snapshot_hash"]
                or application is None
                or application.snapshot_hash != item["applicability_snapshot_hash"]
                or application.part_revision_global_id != part.global_id
            ):
                raise ToolingReferenceUnavailable()
            selected_ids = tuple(item["selected_tooling_set_ids"])
            if any(value not in tooling_sets for value in selected_ids):
                raise ToolingReferenceUnavailable()
            provenances = tuple(
                self._exact_capacity_provenance(
                    project,
                    tooling_master_id,
                    value,
                    applications,
                    tooling_sets,
                    customer_standards,
                    revision_cache,
                )
                for value in (
                    item["cycle_provenance"],
                    item["cavity_provenance"],
                    item["usage_provenance"],
                    item["set_provenance"],
                )
            )
            current = previous.get(application.global_id)
            result.append(
                ToolingCapacityLineInput(
                    global_id=current.global_id if current else self._new_uuid(),
                    part_revision_global_id=part.global_id,
                    part_revision_snapshot_hash=part.snapshot_hash,
                    applicability_global_id=application.global_id,
                    applicability_snapshot_hash=application.snapshot_hash,
                    available_hours_per_day=str(item["available_hours_per_day"]),
                    working_days_per_month=int(item["working_days_per_month"]),
                    oee_ratio=str(item["oee_ratio"]),
                    yield_ratio=str(item["yield_ratio"]),
                    cycle_seconds=str(item["cycle_seconds"]),
                    cavity_count=int(item["cavity_count"]),
                    usage_per_assembly=str(item["usage_per_assembly"]),
                    effective_set_count=int(item["effective_set_count"]),
                    selected_tooling_set_global_ids=selected_ids,
                    cycle_provenance=provenances[0],
                    cavity_provenance=provenances[1],
                    usage_provenance=provenances[2],
                    set_provenance=provenances[3],
                )
            )
        return tuple(result)

    def _exact_capacity_provenance(
        self,
        project: object,
        tooling_master_id: UUID,
        supplied: Mapping[str, object],
        applications: Mapping[UUID, object],
        tooling_sets: Mapping[UUID, object],
        customer_standards: Mapping[UUID, ToolingProcessProfileRevision],
        revision_cache: dict[UUID, object],
    ) -> CapacityInputProvenance:
        provenance = CapacityInputProvenance(
            kind=supplied["kind"],
            global_id=supplied.get("global_id"),
            snapshot_hash=str(supplied["snapshot_hash"]),
        )
        if provenance.kind is CapacityProvenanceKind.SCENARIO_ASSUMPTION:
            return provenance
        global_id = provenance.global_id
        exact_hash = None
        if provenance.kind is CapacityProvenanceKind.CUSTOMER_STANDARD:
            value = customer_standards.get(global_id)
            exact_hash = value.snapshot_hash if value else None
        elif provenance.kind is CapacityProvenanceKind.TOOLING_APPLICABILITY:
            value = applications.get(global_id)
            exact_hash = value.snapshot_hash if value else None
        elif provenance.kind is CapacityProvenanceKind.TOOLING_SET_SELECTION:
            value = tooling_sets.get(global_id)
            exact_hash = value.snapshot_hash if value else None
        elif provenance.kind is CapacityProvenanceKind.TOOLING_REVISION:
            if global_id not in revision_cache:
                revision_cache[global_id] = self._tooling_revision_for_project(
                    project,
                    global_id,
                    tooling_master_id=tooling_master_id,
                )
            value = revision_cache[global_id]
            exact_hash = value.snapshot_hash if value else None
        if exact_hash != provenance.snapshot_hash:
            raise ToolingReferenceUnavailable()
        return provenance

    @staticmethod
    def _insert_engineering_defect(value: ToolingDefectRevision) -> object:
        snapshot = value.snapshot_payload()
        return frappe.get_doc(
            {
                "doctype": "NPI Tooling Defect Revision",
                "global_id": str(value.global_id),
                "defect_global_id": str(value.defect_global_id),
                "version_key_hash": value.version_key_hash,
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "tooling_master": str(value.tooling_master_global_id),
                "tooling_master_global_id": str(value.tooling_master_global_id),
                "tooling_revision": str(value.tooling_revision_global_id),
                "tooling_revision_global_id": str(value.tooling_revision_global_id),
                "tooling_revision_snapshot_hash": value.tooling_revision_snapshot_hash,
                "cavity_global_id": str(value.cavity_global_id) if value.cavity_global_id else None,
                "cavity_identifier": value.cavity_identifier,
                "defect_version": value.defect_version,
                "predecessor_global_id": str(value.predecessor_global_id) if value.predecessor_global_id else None,
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "business_code": value.business_code,
                "title": value.title,
                "description": value.description,
                "category_key": value.category_key,
                "severity": value.severity.value,
                "blocking": int(value.blocking),
                "state": value.state.value,
                "responsible_member": str(value.responsible_member.global_id) if value.responsible_member else None,
                "responsible_member_global_id": str(value.responsible_member.global_id) if value.responsible_member else None,
                "detection_context_snapshot": _canonical_json(snapshot["detectionContext"]),
                "root_cause_state": value.root_cause_state.value,
                "root_cause": value.root_cause,
                "target_round_label": value.target_round_label,
                "action_snapshot": _canonical_json(snapshot["actions"]),
                "evidence_snapshot": _canonical_json(snapshot["evidence"]),
                "reason": value.reason,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "defect_snapshot": _canonical_json(snapshot),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    @staticmethod
    def _insert_engineering_process_profile(
        value: ToolingProcessProfileRevision,
    ) -> object:
        snapshot = value.snapshot_payload()
        return frappe.get_doc(
            {
                "doctype": "NPI Tooling Process Profile Revision",
                "global_id": str(value.global_id),
                "profile_global_id": str(value.profile_global_id),
                "version_key_hash": value.version_key_hash,
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "tooling_master": str(value.tooling_master_global_id),
                "tooling_master_global_id": str(value.tooling_master_global_id),
                "tooling_revision": str(value.tooling_revision_global_id),
                "tooling_revision_global_id": str(value.tooling_revision_global_id),
                "tooling_revision_snapshot_hash": value.tooling_revision_snapshot_hash,
                "layer": value.layer.value,
                "profile_version": value.profile_version,
                "predecessor_global_id": str(value.predecessor_global_id) if value.predecessor_global_id else None,
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "effective_from": value.effective_from.isoformat(),
                "context_snapshot": _canonical_json(snapshot["context"]),
                "metric_snapshot": _canonical_json(snapshot["metrics"]),
                "reason": value.reason,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "profile_snapshot": _canonical_json(snapshot),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    @staticmethod
    def _insert_engineering_capacity_scenario(
        value: ToolingCapacityScenarioRevision,
    ) -> object:
        snapshot = value.snapshot_payload()
        return frappe.get_doc(
            {
                "doctype": "NPI Tooling Capacity Scenario Revision",
                "global_id": str(value.global_id),
                "scenario_global_id": str(value.scenario_global_id),
                "version_key_hash": value.version_key_hash,
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "tooling_master": str(value.tooling_master_global_id),
                "tooling_master_global_id": str(value.tooling_master_global_id),
                "scenario_version": value.scenario_version,
                "predecessor_global_id": str(value.predecessor_global_id) if value.predecessor_global_id else None,
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "title": value.title,
                "effective_from": value.effective_from.isoformat(),
                "target_monthly_assembly_units": value.target_monthly_assembly_units,
                "formula_version": "capacity.v1",
                "rounding_rule": "decimal-6-half-even",
                "input_snapshot": _canonical_json(snapshot["lines"]),
                "result_snapshot": _canonical_json(snapshot["result"]),
                "reason": value.reason,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "scenario_snapshot": _canonical_json(snapshot),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()


def _latest_process_profiles(
    values: Sequence[ToolingProcessProfileRevision],
) -> tuple[ToolingProcessProfileRevision, ...]:
    latest: dict[UUID, ToolingProcessProfileRevision] = {}
    for value in values:
        latest[value.profile_global_id] = value
    return tuple(latest[key] for key in sorted(latest, key=str))


def _validate_chains(values, *, group, version, validate, label: str) -> None:
    grouped: dict[object, list[object]] = {}
    for value in values:
        grouped.setdefault(group(value), []).append(value)
    for chain in grouped.values():
        chain.sort(key=version)
        for index, value in enumerate(chain):
            if version(value) != index + 1:
                raise RuntimeError(f"The {label} chain is not contiguous.")
            if index:
                validate(chain[index - 1], value)


def _defect_response(value: ToolingDefectRevision) -> dict[str, object]:
    return {**value.snapshot_payload(), "snapshotHash": value.snapshot_hash}


def _process_profile_response(
    value: ToolingProcessProfileRevision,
) -> dict[str, object]:
    return {**value.snapshot_payload(), "snapshotHash": value.snapshot_hash}


def _capacity_scenario_response(
    value: ToolingCapacityScenarioRevision,
) -> dict[str, object]:
    return {**value.snapshot_payload(), "snapshotHash": value.snapshot_hash}


def _command_payload(value: object) -> object:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "snapshot_payload"):
        return value.snapshot_payload()
    if isinstance(value, Mapping):
        return {str(key): _command_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_command_payload(item) for item in value]
    return value


def _optional_doc(doctype: str, name: str):
    try:
        return frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        return None


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_object(value: object) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise RuntimeError("The engineering-controls snapshot is invalid.")
    return value


def _database_datetime(value: datetime) -> str:
    return value.astimezone(UTC).replace(tzinfo=None).isoformat(sep=" ", timespec="microseconds")
