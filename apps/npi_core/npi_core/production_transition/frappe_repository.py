from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Callable
from uuid import UUID, uuid4

import frappe
from frappe import _

from npi_core.foundation.audit import create_audit_event
from npi_core.foundation.errors import NpiProblem, PermissionDenied, RequestValidationFailed
from npi_core.foundation.security import Principal
from npi_core.production_transition.domain import (
    ExactVersionReference,
    FrozenAcknowledgementSlot,
    HandoverAcknowledgement,
    HandoverPackageRevision,
    HandoverSourceKind,
    ObservationPeriodRevision,
    PolicyPublicationState,
    ProductionTransitionPolicyVersion,
    ProductionTransitionVersionConflict,
    ProjectMemberSnapshot,
    ProjectRoleSnapshot,
    ProjectTransitionSnapshot,
    UnresolvedActionSnapshot,
    WorkItemKind,
    acknowledgement_from_snapshot,
    create_handover_acknowledgement,
    create_handover_package_revision,
    create_handover_package_successor,
    create_observation_period_revision,
    create_observation_period_successor,
    derive_fully_acknowledged,
    handover_package_from_snapshot,
    observation_from_snapshot,
    policy_from_snapshot,
    sha256_json,
    unavailable_observation_providers,
    validate_handover_successor,
    validate_observation_successor,
)
from npi_core.production_transition.frappe_validation import (
    production_transition_command_write,
    production_transition_policy_version_write,
)
from npi_core.production_transition.request_validation import (
    AcknowledgementIntent,
    CreateObservationRequest,
    CreatePolicyRequest,
    EditPolicyRequest,
    HandoverContentRequest,
    NextPolicyVersionRequest,
    ObservationRevisionRequest,
    PublishPolicyRequest,
    ReviseHandoverRequest,
)
from npi_core.production_transition.response_validation import (
    validate_policy_catalog_response,
    validate_receipt_response,
    validate_workspace_response,
)
from npi_core.production_transition.source_resolver import (
    ResolvedTransitionSource,
    SourceResolutionContext,
    resolve_manifest_sources,
    resolve_observation_sources,
)
from npi_core.project.domain import ProjectType
from npi_core.project_controls.terminal_guard import require_mutable_project


_MAX_POLICY_VERSIONS = 1_000
_MAX_HANDOVER_REVISIONS = 1_000
_MAX_OBSERVATION_REVISIONS = 1_000
_MAX_ACKNOWLEDGEMENTS = 100
_MAX_PROJECT_MEMBERS = 256
_MAX_UNRESOLVED_ACTIONS = 10_000
_MAX_RELEASE_SOURCE_FILES = 64


class ProductionTransitionIdempotencyConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "PRODUCTION_TRANSITION_IDEMPOTENCY_CONFLICT",
            _("The idempotency key was already used for a different request."),
        )


@dataclass(frozen=True, slots=True)
class ProductionTransitionCommandOutcome:
    response: dict[str, Any]
    replayed: bool
    target_global_id: UUID


class FrappeProductionTransitionRepository:
    """Project-first persistence for the bounded P7-06 technical foundation."""

    def __init__(
        self,
        *,
        principal: Principal,
        request_id: str,
        trace_id: str,
        clock: Callable[[], datetime] | None = None,
        uuid_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self.principal = principal
        self.actor = principal.user_id
        self.request_id = str(UUID(request_id))
        self.trace_id = trace_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._uuid_factory = uuid_factory

    def policy_catalog(self, project_id: UUID) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        project_value = _project_snapshot(project)
        policies = [
            _policy_response(value)
            for value in self._all_policy_versions(
                tenant_id=str(project.tenant_id),
                for_update=False,
            )
            if value.publication_state is PolicyPublicationState.PUBLISHED
            and value.applicability.applies_to(project_value)
        ]
        response = {
            "projectGlobalId": str(project_id),
            "policies": policies,
        }
        return validate_policy_catalog_response(
            response,
            project_global_id=project_id,
            tenant_id=str(project.tenant_id),
        )

    def create_policy(
        self,
        *,
        idempotency_key_hash: str,
        request: CreatePolicyRequest,
    ) -> ProductionTransitionCommandOutcome:
        tenant_id = self._require_policy_administrator()
        payload_hash = _payload_hash(
            {
                "policyCode": request.policy_code,
                "title": request.title,
                "definition": _policy_definition_payload(request),
            }
        )
        operation = "production_transition_policy.create"
        replay = self._idempotency_replay(
            tenant_id=tenant_id,
            project_id=None,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
        )
        if replay is not None:
            return replay
        policy_code_key_hash = _policy_code_key_hash(
            tenant_id,
            request.policy_code,
        )
        if frappe.db.exists(
            "NPI Production Transition Policy",
            {
                "tenant_id": tenant_id,
                "policy_code_key_hash": policy_code_key_hash,
            },
        ):
            raise ProductionTransitionVersionConflict()

        now = self._now()
        policy_id = self._uuid_factory()
        value = ProductionTransitionPolicyVersion.create_draft(
            policy_global_id=policy_id,
            tenant_id=tenant_id,
            policy_code=request.policy_code,
            title=request.title,
            applicability=request.definition.applicability,
            receiving_groups=request.definition.receiving_groups,
            acknowledgement_slots=request.definition.acknowledgement_slots,
            handover_requirements=request.definition.handover_requirements,
            observation_source_rules=request.definition.observation_source_rules,
            observation_window_days=request.definition.observation_window_days,
            changed_by_user_id=self.actor,
            changed_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        response = _policy_response(value)
        with production_transition_policy_version_write():
            receipt = self._insert_receipt(
                tenant_id=tenant_id,
                project_id=None,
                operation=operation,
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                created_at=now,
            )
            if isinstance(receipt, ProductionTransitionCommandOutcome):
                return receipt
            frappe.get_doc(
                {
                    "doctype": "NPI Production Transition Policy",
                    "global_id": str(policy_id),
                    "tenant_id": tenant_id,
                    "policy_code": value.policy_code,
                    "policy_code_key_hash": policy_code_key_hash,
                    "title": value.title,
                    "optimistic_version": value.optimistic_version,
                }
            ).insert()
            self._insert_policy_version(value)
            self._append_audit(
                operation=operation,
                global_id=value.global_id,
                object_version=value.optimistic_version,
                summary={
                    "occurredAt": _utc_datetime_text(now),
                    "policyGlobalId": str(policy_id),
                    "policyVersion": value.policy_version,
                    "requestId": self.request_id,
                    "snapshotHash": value.snapshot_hash,
                    "tenantId": tenant_id,
                },
            )
            self._seal_receipt(
                receipt,
                operation=operation,
                target_object_type="production_transition_policy",
                target_global_id=policy_id,
                project_id=None,
                response=response,
                updated_at=now,
            )
        return ProductionTransitionCommandOutcome(response, False, policy_id)

    def edit_policy(
        self,
        policy_id: UUID,
        policy_version: int,
        *,
        idempotency_key_hash: str,
        request: EditPolicyRequest,
    ) -> ProductionTransitionCommandOutcome | None:
        return self._change_policy(
            policy_id,
            policy_version,
            operation="production_transition_policy.edit",
            idempotency_key_hash=idempotency_key_hash,
            payload={
                "expectedOptimisticVersion": request.expected_optimistic_version,
                "title": request.title,
                "definition": _policy_definition_payload(request),
            },
            transform=lambda current, now: current.edit_draft(
                expected_version=request.expected_optimistic_version,
                changed_by_user_id=self.actor,
                changed_at=now,
                request_id=UUID(self.request_id),
                trace_id=self.trace_id,
                title=request.title,
                applicability=request.definition.applicability,
                receiving_groups=request.definition.receiving_groups,
                acknowledgement_slots=request.definition.acknowledgement_slots,
                handover_requirements=request.definition.handover_requirements,
                observation_source_rules=request.definition.observation_source_rules,
                observation_window_days=request.definition.observation_window_days,
            ),
        )

    def publish_policy(
        self,
        policy_id: UUID,
        policy_version: int,
        *,
        idempotency_key_hash: str,
        request: PublishPolicyRequest,
    ) -> ProductionTransitionCommandOutcome | None:
        return self._change_policy(
            policy_id,
            policy_version,
            operation="production_transition_policy.publish",
            idempotency_key_hash=idempotency_key_hash,
            payload={
                "expectedOptimisticVersion": request.expected_optimistic_version,
                "expectedSnapshotHash": request.expected_snapshot_hash,
            },
            before_transform=lambda current: _require_exact_snapshot(
                current.snapshot_hash,
                request.expected_snapshot_hash,
            ),
            transform=lambda current, now: current.publish(
                expected_version=request.expected_optimistic_version,
                changed_by_user_id=self.actor,
                changed_at=now,
                request_id=UUID(self.request_id),
                trace_id=self.trace_id,
            ),
        )

    def create_policy_version(
        self,
        policy_id: UUID,
        *,
        idempotency_key_hash: str,
        request: NextPolicyVersionRequest,
    ) -> ProductionTransitionCommandOutcome | None:
        tenant_id = self._require_policy_administrator()
        operation = "production_transition_policy.next_version"
        payload_hash = _payload_hash(
            {
                "policyGlobalId": policy_id,
                "expectedPublishedVersion": request.expected_published_version,
                "expectedPublishedSnapshotHash": (
                    request.expected_published_snapshot_hash
                ),
            }
        )
        replay = self._idempotency_replay(
            tenant_id=tenant_id,
            project_id=None,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
        )
        if replay is not None:
            return replay
        root = _single_document(
            "NPI Production Transition Policy",
            {
                "global_id": str(policy_id),
                "tenant_id": tenant_id,
            },
            for_update=True,
        )
        if root is None or str(_value(root, "global_id")) != str(policy_id):
            return None
        chain = self._policy_chain(
            policy_id,
            tenant_id=tenant_id,
            for_update=True,
        )
        if not chain:
            return None
        current = chain[-1]
        if (
            current.policy_version != request.expected_published_version
            or current.snapshot_hash != request.expected_published_snapshot_hash
        ):
            raise ProductionTransitionVersionConflict()
        now = self._now()
        successor = current.next_draft(
            changed_by_user_id=self.actor,
            changed_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        response = _policy_response(successor)
        with production_transition_policy_version_write():
            receipt = self._insert_receipt(
                tenant_id=tenant_id,
                project_id=None,
                operation=operation,
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                created_at=now,
            )
            if isinstance(receipt, ProductionTransitionCommandOutcome):
                return receipt
            self._insert_policy_version(successor)
            root.title = successor.title
            root.optimistic_version = successor.optimistic_version
            root.save()
            self._append_audit(
                operation=operation,
                global_id=successor.global_id,
                object_version=successor.optimistic_version,
                summary={
                    "occurredAt": _utc_datetime_text(now),
                    "policyGlobalId": str(policy_id),
                    "policyVersion": successor.policy_version,
                    "predecessorGlobalId": str(current.global_id),
                    "predecessorSnapshotHash": current.snapshot_hash,
                    "requestId": self.request_id,
                    "snapshotHash": successor.snapshot_hash,
                    "tenantId": tenant_id,
                },
            )
            self._seal_receipt(
                receipt,
                operation=operation,
                target_object_type="production_transition_policy_version",
                target_global_id=successor.global_id,
                project_id=None,
                response=response,
                updated_at=now,
            )
        return ProductionTransitionCommandOutcome(response, False, successor.global_id)

    def production_transition_workspace(
        self,
        project_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        return self._workspace_for(project)

    def create_handover(
        self,
        project_id: UUID,
        *,
        idempotency_key_hash: str,
        request: HandoverContentRequest,
    ) -> ProductionTransitionCommandOutcome | None:
        project = self._locked_authorized_project(project_id, administer=True)
        if project is None:
            return None
        payload_hash = _payload_hash(
            {
                "projectGlobalId": project_id,
                "content": _handover_content_payload(request),
            }
        )
        operation = "production_handover.create"
        replay = self._idempotency_replay(
            tenant_id=str(project.tenant_id),
            project_id=project_id,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
        )
        if replay is not None:
            return replay
        require_mutable_project(project)
        self._require_project_version(project, request.expected_project_version)
        if self._handover_chain(project, for_update=True):
            raise ProductionTransitionVersionConflict()

        now = self._now()
        policy = self._published_policy(
            request.policy,
            tenant_id=str(project.tenant_id),
            for_update=True,
        )
        project_value = _project_snapshot(project)
        slots, enabled_users = self._slot_bindings(
            project,
            policy,
            request.slot_assignments,
            effective_date=now.date(),
        )
        manifest = resolve_manifest_sources(
            request.manifest_sources,
            policy=policy,
            context=SourceResolutionContext(str(project.tenant_id), project_id),
            repository=self,
            for_update=True,
        )
        unresolved = self._unresolved_actions(project, for_update=True)
        readiness_ref = _readiness_reference(manifest)
        value = create_handover_package_revision(
            handover_global_id=self._uuid_factory(),
            tenant_id=str(project.tenant_id),
            project=project_value,
            policy=policy,
            readiness_ref=readiness_ref,
            slots=slots,
            manifest=manifest,
            server_unresolved_actions=unresolved,
            enabled_user_ids=enabled_users,
            reason=request.reason,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        response = _handover_command_response(project_id, value)
        with production_transition_command_write():
            receipt = self._insert_receipt(
                tenant_id=str(project.tenant_id),
                project_id=project_id,
                operation=operation,
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                created_at=now,
            )
            if isinstance(receipt, ProductionTransitionCommandOutcome):
                return receipt
            self._insert_handover_revision(value)
            self._append_audit(
                operation=operation,
                global_id=value.global_id,
                object_version=value.handover_version,
                summary=self._handover_audit_summary(value),
            )
            self._seal_receipt(
                receipt,
                operation=operation,
                target_object_type="handover_package_revision",
                target_global_id=value.global_id,
                project_id=project_id,
                response=response,
                updated_at=now,
            )
        return ProductionTransitionCommandOutcome(response, False, value.global_id)

    def revise_handover(
        self,
        project_id: UUID,
        handover_id: UUID,
        *,
        idempotency_key_hash: str,
        request: ReviseHandoverRequest,
    ) -> ProductionTransitionCommandOutcome | None:
        project = self._locked_authorized_project(project_id, administer=True)
        if project is None:
            return None
        payload_hash = _payload_hash(
            {
                "projectGlobalId": project_id,
                "handoverGlobalId": handover_id,
                "expectedRevisionGlobalId": request.expected_revision_global_id,
                "expectedSnapshotHash": request.expected_snapshot_hash,
                "content": _handover_content_payload(request.content),
            }
        )
        operation = "production_handover.revise"
        replay = self._idempotency_replay(
            tenant_id=str(project.tenant_id),
            project_id=project_id,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
        )
        if replay is not None:
            return replay
        require_mutable_project(project)
        self._require_project_version(
            project,
            request.content.expected_project_version,
        )
        chain = self._handover_chain(project, for_update=True)
        if not chain:
            return None
        current = chain[-1]
        if current.handover_global_id != handover_id:
            return None
        if (
            current.global_id != request.expected_revision_global_id
            or current.snapshot_hash != request.expected_snapshot_hash
        ):
            raise ProductionTransitionVersionConflict()

        now = self._now()
        policy = self._published_policy(
            request.content.policy,
            tenant_id=str(project.tenant_id),
            for_update=True,
        )
        slots, enabled_users = self._slot_bindings(
            project,
            policy,
            request.content.slot_assignments,
            effective_date=now.date(),
        )
        manifest = resolve_manifest_sources(
            request.content.manifest_sources,
            policy=policy,
            context=SourceResolutionContext(str(project.tenant_id), project_id),
            repository=self,
            for_update=True,
        )
        unresolved = self._unresolved_actions(project, for_update=True)
        successor = create_handover_package_successor(
            current,
            project=_project_snapshot(project),
            policy=policy,
            readiness_ref=_readiness_reference(manifest),
            slots=slots,
            manifest=manifest,
            server_unresolved_actions=unresolved,
            enabled_user_ids=enabled_users,
            reason=request.content.reason,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        response = _handover_command_response(project_id, successor)
        with production_transition_command_write():
            receipt = self._insert_receipt(
                tenant_id=str(project.tenant_id),
                project_id=project_id,
                operation=operation,
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                created_at=now,
            )
            if isinstance(receipt, ProductionTransitionCommandOutcome):
                return receipt
            self._insert_handover_revision(successor)
            self._append_audit(
                operation=operation,
                global_id=successor.global_id,
                object_version=successor.handover_version,
                summary=self._handover_audit_summary(successor),
            )
            self._seal_receipt(
                receipt,
                operation=operation,
                target_object_type="handover_package_revision",
                target_global_id=successor.global_id,
                project_id=project_id,
                response=response,
                updated_at=now,
            )
        return ProductionTransitionCommandOutcome(response, False, successor.global_id)

    def acknowledge_handover(
        self,
        project_id: UUID,
        handover_id: UUID,
        handover_version: int,
        *,
        idempotency_key_hash: str,
        request: AcknowledgementIntent,
    ) -> ProductionTransitionCommandOutcome | None:
        project = self._locked_authorized_project(project_id, administer=False)
        if project is None:
            return None
        payload_hash = _payload_hash(
            {
                "projectGlobalId": project_id,
                "handoverGlobalId": handover_id,
                "handoverVersion": handover_version,
                "expectedRevisionGlobalId": request.expected_revision_global_id,
                "expectedSnapshotHash": request.expected_snapshot_hash,
                "slotKey": request.slot_key,
                "intent": request.intent,
            }
        )
        operation = "production_handover.acknowledge"
        replay = self._idempotency_replay(
            tenant_id=str(project.tenant_id),
            project_id=project_id,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
        )
        if replay is not None:
            return replay
        require_mutable_project(project)
        chain = self._handover_chain(project, for_update=True)
        if not chain:
            return None
        package = chain[-1]
        if package.handover_global_id != handover_id:
            return None
        if (
            package.handover_version != handover_version
            or package.global_id != request.expected_revision_global_id
            or package.snapshot_hash != request.expected_snapshot_hash
        ):
            raise ProductionTransitionVersionConflict()
        slot = _exact_one(
            (value for value in package.slots if value.slot_key == request.slot_key),
            "Persisted handover acknowledgement slot is ambiguous.",
        )
        if slot is None or slot.member.user_id.casefold() != self.actor.casefold():
            raise PermissionDenied()
        member = self._member_snapshot(
            project,
            slot.member.global_id,
            for_update=True,
        )
        role = self._role_snapshot(
            project,
            slot.role.global_id,
            for_update=True,
        )
        now = self._now()
        acknowledgement = create_handover_acknowledgement(
            package,
            slot_key=request.slot_key,
            acknowledgement_intent=request.intent == "acknowledge",
            actor_user_id=self.actor,
            actor_user_enabled=_enabled_system_user(
                self.actor,
                for_update=True,
            ),
            current_member=member,
            current_role=role,
            acknowledged_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        if _optional_doc(
            "NPI Handover Acknowledgement",
            str(acknowledgement.global_id),
        ) is not None:
            raise ProductionTransitionVersionConflict()
        response = _acknowledgement_command_response(
            project_id,
            package,
            acknowledgement,
        )
        with production_transition_command_write():
            receipt = self._insert_receipt(
                tenant_id=str(project.tenant_id),
                project_id=project_id,
                operation=operation,
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                created_at=now,
            )
            if isinstance(receipt, ProductionTransitionCommandOutcome):
                return receipt
            self._insert_acknowledgement(project, acknowledgement)
            self._append_audit(
                operation=operation,
                global_id=acknowledgement.global_id,
                object_version=acknowledgement.package_version,
                summary=_acknowledgement_audit_summary(
                    package,
                    acknowledgement,
                ),
            )
            self._seal_receipt(
                receipt,
                operation=operation,
                target_object_type="handover_acknowledgement",
                target_global_id=acknowledgement.global_id,
                project_id=project_id,
                response=response,
                updated_at=now,
            )
        return ProductionTransitionCommandOutcome(
            response,
            False,
            acknowledgement.global_id,
        )

    def create_observation(
        self,
        project_id: UUID,
        *,
        idempotency_key_hash: str,
        request: CreateObservationRequest,
    ) -> ProductionTransitionCommandOutcome | None:
        project = self._locked_authorized_project(project_id, administer=True)
        if project is None:
            return None
        payload_hash = _payload_hash(
            {
                "projectGlobalId": project_id,
                "request": _observation_create_payload(request),
            }
        )
        operation = "observation_period.create"
        replay = self._idempotency_replay(
            tenant_id=str(project.tenant_id),
            project_id=project_id,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
        )
        if replay is not None:
            return replay
        require_mutable_project(project)
        self._require_project_version(project, request.expected_project_version)
        if self._observation_chain(project, for_update=True):
            raise ProductionTransitionVersionConflict()
        policy = self._published_policy(
            request.policy,
            tenant_id=str(project.tenant_id),
            for_update=True,
        )
        handover_ref = self._requested_handover_reference(
            project,
            request.handover,
            require_current=False,
        )
        context, retrospective = resolve_observation_sources(
            request.context_sources,
            request.retrospective_sources,
            context=SourceResolutionContext(str(project.tenant_id), project_id),
            repository=self,
            for_update=True,
        )
        now = self._now()
        value = create_observation_period_revision(
            observation_global_id=self._uuid_factory(),
            tenant_id=str(project.tenant_id),
            project=_project_snapshot(project),
            policy=policy,
            handover_package_ref=handover_ref,
            context_references=context,
            retrospective_references=retrospective,
            retrospective_note=request.retrospective_note,
            reason=request.reason,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        return self._persist_observation(
            project,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
            value=value,
            now=now,
        )

    def revise_observation(
        self,
        project_id: UUID,
        observation_id: UUID,
        *,
        idempotency_key_hash: str,
        request: ObservationRevisionRequest,
    ) -> ProductionTransitionCommandOutcome | None:
        project = self._locked_authorized_project(project_id, administer=True)
        if project is None:
            return None
        payload_hash = _payload_hash(
            {
                "projectGlobalId": project_id,
                "observationGlobalId": observation_id,
                "request": _observation_revision_payload(request),
            }
        )
        operation = "observation_period.revise"
        replay = self._idempotency_replay(
            tenant_id=str(project.tenant_id),
            project_id=project_id,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
        )
        if replay is not None:
            return replay
        require_mutable_project(project)
        chain = self._observation_chain(project, for_update=True)
        if not chain:
            return None
        current = chain[-1]
        if current.observation_global_id != observation_id:
            return None
        if (
            request.expected_revision_global_id is None
            or request.expected_snapshot_hash is None
            or current.global_id != request.expected_revision_global_id
            or current.snapshot_hash != request.expected_snapshot_hash
        ):
            raise ProductionTransitionVersionConflict()
        policy = self._policy_by_exact_ref(
            current.policy_ref,
            tenant_id=str(project.tenant_id),
            for_update=True,
        )
        handover_ref = self._exact_handover_reference(
            project,
            current.handover_package_ref,
        )
        context, retrospective = resolve_observation_sources(
            request.context_sources,
            request.retrospective_sources,
            context=SourceResolutionContext(str(project.tenant_id), project_id),
            repository=self,
            for_update=True,
        )
        now = self._now()
        successor = create_observation_period_successor(
            current,
            project=_project_snapshot(project),
            policy=policy,
            handover_package_ref=handover_ref,
            context_references=context,
            retrospective_references=retrospective,
            retrospective_note=request.retrospective_note,
            reason=request.reason,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        return self._persist_observation(
            project,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
            value=successor,
            now=now,
        )

    def load_readiness_instance_revision(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None:
        project = self._source_project(context)
        if project is None:
            return None
        document = _source_document(
            "NPI Readiness Instance Revision",
            context,
            global_id,
            for_update=for_update,
        )
        if document is None:
            return None
        from npi_core.readiness.frappe_repository import _project_revision_chain

        chain = _project_revision_chain(project)
        if not chain or chain[-1].global_id != global_id:
            return None
        value = chain[-1]
        return ResolvedTransitionSource(
            HandoverSourceKind.READINESS_INSTANCE_REVISION,
            value.global_id,
            value.instance_version,
            value.snapshot_hash,
        )

    def load_domain_work_item(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None:
        document = _source_document(
            "NPI Domain Work Item",
            context,
            global_id,
            for_update=for_update,
        )
        if document is None:
            return None
        from npi_core.readiness.frappe_repository import (
            _domain_work_item_source_snapshot,
            _domain_work_item_value,
        )

        value = _domain_work_item_value(document)
        if value is None or value.global_id != global_id:
            return None
        return ResolvedTransitionSource(
            HandoverSourceKind.DOMAIN_WORK_ITEM,
            value.global_id,
            value.version,
            _payload_hash(_domain_work_item_source_snapshot(value)),
        )

    def load_released_document(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None:
        revision = _source_document(
            "NPI Document Revision",
            context,
            global_id,
            for_update=for_update,
        )
        lifecycle = _single_document(
            "NPI Document Revision Lifecycle",
            {
                "tenant_id": context.tenant_id,
                "project_global_id": str(context.project_global_id),
                "revision_global_id": str(global_id),
            },
            for_update=for_update,
        )
        if revision is None or lifecycle is None:
            return None
        if not _lock_released_file_dependencies(
            context,
            revision,
            for_update=for_update,
        ):
            return None
        try:
            source_version = int(_value(lifecycle, "lifecycle_version"))
            snapshot_hash = str(_value(lifecycle, "release_snapshot_hash"))
            from npi_core.readiness.domain import ReadinessSourceKind
            from npi_core.readiness.frappe_repository import (
                _released_document_source_is_current,
            )
            from npi_core.readiness.source_resolver import (
                ExactSourceQuery as ReadinessExactSourceQuery,
            )
            from npi_core.readiness.source_resolver import (
                SourceResolutionContext as ReadinessSourceResolutionContext,
            )

            exact = ReadinessExactSourceQuery(
                ReadinessSourceKind.RELEASED_DOCUMENT,
                global_id,
                source_version,
                snapshot_hash,
            )
            current = _released_document_source_is_current(
                ReadinessSourceResolutionContext(
                    context.tenant_id,
                    context.project_global_id,
                ),
                exact,
                revision,
            )
        except (
            AttributeError,
            RequestValidationFailed,
            TypeError,
            ValueError,
            frappe.DoesNotExistError,
            frappe.PermissionError,
            frappe.ValidationError,
        ):
            return None
        if not current:
            return None
        return ResolvedTransitionSource(
            HandoverSourceKind.RELEASED_DOCUMENT,
            global_id,
            source_version,
            snapshot_hash,
        )

    def load_release_baseline(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None:
        project = self._source_project(context)
        if project is None:
            return None
        from npi_core.documents.baseline_repository import load_document_baseline

        value = load_document_baseline(project, global_id, lock=for_update)
        if value is None or value.global_id != global_id:
            return None
        return ResolvedTransitionSource(
            HandoverSourceKind.RELEASE_BASELINE,
            value.global_id,
            value.version,
            value.snapshot_hash,
        )

    def load_file_revision(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None:
        document = _source_document(
            "NPI File Revision",
            context,
            global_id,
            for_update=for_update,
        )
        if document is None:
            return None
        from npi_core.npi_core.doctype.npi_file_revision.npi_file_revision import (
            file_revision_source_snapshot,
        )

        if (
            str(_value(document, "scan_state")) != "clean"
            or not _locked_live_private_file_identity(
                document,
                for_update=for_update,
            )
        ):
            return None
        try:
            projection = file_revision_source_snapshot(document)
            version = int(_value(document, "optimistic_version"))
        except (AttributeError, TypeError, ValueError):
            return None
        return ResolvedTransitionSource(
            HandoverSourceKind.FILE_REVISION,
            global_id,
            version,
            sha256_json(projection),
        )

    def load_tooling_capacity_scenario(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None:
        project = self._source_project(context)
        document = _source_document(
            "NPI Tooling Capacity Scenario Revision",
            context,
            global_id,
            for_update=for_update,
        )
        if project is None or document is None:
            return None
        try:
            master_id = UUID(str(_value(document, "tooling_master_global_id")))
            scenario_id = UUID(str(_value(document, "scenario_global_id")))
            from npi_core.tooling.frappe_repository import FrappeToolingRepository

            repository = FrappeToolingRepository(
                principal=self.principal,
                request_id=self.request_id,
                trace_id=self.trace_id,
            )
            chain = repository._engineering_capacity_scenarios(
                project,
                master_id,
                scenario_id=scenario_id,
            )
        except (AttributeError, TypeError, ValueError):
            return None
        if not chain or chain[-1].global_id != global_id:
            return None
        value = chain[-1]
        return ResolvedTransitionSource(
            HandoverSourceKind.TOOLING_CAPACITY_SCENARIO,
            value.global_id,
            value.scenario_version,
            value.snapshot_hash,
        )

    def load_trial_defect_revision(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None:
        project = self._source_project(context)
        document = _source_document(
            "NPI Trial Defect Revision",
            context,
            global_id,
            for_update=for_update,
        )
        if project is None or document is None:
            return None
        try:
            defect_id = UUID(str(_value(document, "defect_global_id")))
            from npi_core.trial.quality_repository import FrappeTrialQualityRepository

            repository = FrappeTrialQualityRepository(
                principal=self.principal,
                request_id=self.request_id,
                trace_id=self.trace_id,
            )
            chain = repository._trial_defect_chain(
                project,
                defect_id=defect_id,
                for_update=for_update,
            )
        except (AttributeError, TypeError, ValueError):
            return None
        if not chain or chain[-1].global_id != global_id:
            return None
        value = chain[-1]
        return ResolvedTransitionSource(
            HandoverSourceKind.TRIAL_DEFECT_REVISION,
            value.global_id,
            value.defect_version,
            value.snapshot_hash,
        )

    def load_trial_review_reference(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None:
        project = self._source_project(context)
        document = _source_document(
            "NPI Trial Review Reference Revision",
            context,
            global_id,
            for_update=for_update,
        )
        if project is None or document is None:
            return None
        try:
            round_id = UUID(str(_value(document, "trial_round_global_id")))
            reference_id = UUID(str(_value(document, "reference_global_id")))
            from npi_core.readiness.frappe_repository import (
                _trial_review_reference_sources_are_current,
            )
            from npi_core.readiness.source_resolver import (
                SourceResolutionContext as ReadinessSourceResolutionContext,
            )
            from npi_core.trial.review_repository import FrappeTrialReviewRepository

            repository = FrappeTrialReviewRepository(
                principal=self.principal,
                request_id=self.request_id,
                trace_id=self.trace_id,
            )
            chain = repository._reference_chain(project, round_id, reference_id)
            value = chain[-1] if chain else None
            file_revision = (
                _source_document(
                    "NPI File Revision",
                    context,
                    value.file_revision.global_id,
                    for_update=for_update,
                )
                if value is not None
                else None
            )
            from npi_core.npi_core.doctype.npi_file_revision.npi_file_revision import (
                file_revision_source_snapshot,
            )

            file_snapshot = (
                file_revision_source_snapshot(file_revision)
                if file_revision is not None
                else None
            )
            current = bool(
                value is not None
                and value.global_id == global_id
                and file_revision is not None
                and file_snapshot is not None
                and _payload_hash(file_snapshot)
                == value.file_revision.snapshot_hash
                and str(file_snapshot.get("scanState")) == "clean"
                and _locked_live_private_file_identity(
                    file_revision,
                    for_update=for_update,
                )
                and _trial_review_reference_sources_are_current(
                    ReadinessSourceResolutionContext(
                        context.tenant_id,
                        context.project_global_id,
                    ),
                    value,
                )
            )
        except (
            AttributeError,
            RequestValidationFailed,
            TypeError,
            ValueError,
            frappe.DoesNotExistError,
            frappe.PermissionError,
            frappe.ValidationError,
        ):
            return None
        if not current or value is None:
            return None
        return ResolvedTransitionSource(
            HandoverSourceKind.TRIAL_REVIEW_REFERENCE,
            value.global_id,
            value.reference_version,
            value.snapshot_hash,
        )

    def load_trial_conclusion(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None:
        project = self._source_project(context)
        document = _source_document(
            "NPI Trial Conclusion Revision",
            context,
            global_id,
            for_update=for_update,
        )
        if project is None or document is None:
            return None
        try:
            round_id = UUID(str(_value(document, "trial_round_global_id")))
            conclusion_id = UUID(str(_value(document, "conclusion_global_id")))
            from npi_core.trial.review_repository import FrappeTrialReviewRepository

            repository = FrappeTrialReviewRepository(
                principal=self.principal,
                request_id=self.request_id,
                trace_id=self.trace_id,
            )
            chain = repository._conclusion_chain(project, round_id, conclusion_id)
        except (AttributeError, TypeError, ValueError):
            return None
        if not chain or chain[-1].global_id != global_id:
            return None
        value = chain[-1]
        return ResolvedTransitionSource(
            HandoverSourceKind.TRIAL_CONCLUSION,
            value.global_id,
            value.conclusion_version,
            value.snapshot_hash,
        )

    def _change_policy(
        self,
        policy_id: UUID,
        policy_version: int,
        *,
        operation: str,
        idempotency_key_hash: str,
        payload: Mapping[str, Any],
        transform: Callable[
            [ProductionTransitionPolicyVersion, datetime],
            ProductionTransitionPolicyVersion,
        ],
        before_transform: Callable[[ProductionTransitionPolicyVersion], None]
        | None = None,
    ) -> ProductionTransitionCommandOutcome | None:
        tenant_id = self._require_policy_administrator()
        payload_hash = _payload_hash(
            {
                "policyGlobalId": policy_id,
                "policyVersion": policy_version,
                **dict(payload),
            }
        )
        replay = self._idempotency_replay(
            tenant_id=tenant_id,
            project_id=None,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
        )
        if replay is not None:
            return replay
        root = _single_document(
            "NPI Production Transition Policy",
            {
                "global_id": str(policy_id),
                "tenant_id": tenant_id,
            },
            for_update=True,
        )
        if root is None or str(_value(root, "global_id")) != str(policy_id):
            return None
        chain = self._policy_chain(
            policy_id,
            tenant_id=tenant_id,
            for_update=True,
        )
        if not chain:
            return None
        current = chain[-1]
        if current.policy_version != policy_version:
            raise ProductionTransitionVersionConflict()
        if before_transform is not None:
            before_transform(current)
        now = self._now()
        successor = transform(current, now)
        response = _policy_response(successor)
        document = _optional_doc(
            "NPI Production Transition Policy Version",
            str(current.global_id),
        )
        if document is None:
            return None
        with production_transition_policy_version_write():
            receipt = self._insert_receipt(
                tenant_id=tenant_id,
                project_id=None,
                operation=operation,
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                created_at=now,
            )
            if isinstance(receipt, ProductionTransitionCommandOutcome):
                return receipt
            _apply_policy_version(document, successor)
            document.save()
            root.title = successor.title
            root.optimistic_version = successor.optimistic_version
            root.save()
            self._append_audit(
                operation=operation,
                global_id=successor.global_id,
                object_version=successor.optimistic_version,
                summary={
                    "occurredAt": _utc_datetime_text(now),
                    "policyGlobalId": str(policy_id),
                    "policyVersion": successor.policy_version,
                    "predecessorGlobalId": (
                        str(successor.prior_version_ref.global_id)
                        if successor.prior_version_ref
                        else None
                    ),
                    "predecessorSnapshotHash": (
                        successor.prior_version_ref.snapshot_hash
                        if successor.prior_version_ref
                        else None
                    ),
                    "publicationState": successor.publication_state.value,
                    "requestId": self.request_id,
                    "snapshotHash": successor.snapshot_hash,
                    "tenantId": tenant_id,
                },
            )
            self._seal_receipt(
                receipt,
                operation=operation,
                target_object_type="production_transition_policy_version",
                target_global_id=successor.global_id,
                project_id=None,
                response=response,
                updated_at=now,
            )
        return ProductionTransitionCommandOutcome(response, False, successor.global_id)

    def _persist_observation(
        self,
        project,
        *,
        operation: str,
        idempotency_key_hash: str,
        payload_hash: str,
        value: ObservationPeriodRevision,
        now: datetime,
    ) -> ProductionTransitionCommandOutcome:
        project_id = UUID(str(project.global_id))
        response = _observation_command_response(project_id, value)
        with production_transition_command_write():
            receipt = self._insert_receipt(
                tenant_id=str(project.tenant_id),
                project_id=project_id,
                operation=operation,
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                created_at=now,
            )
            if isinstance(receipt, ProductionTransitionCommandOutcome):
                return receipt
            self._insert_observation_revision(value)
            self._append_audit(
                operation=operation,
                global_id=value.global_id,
                object_version=value.observation_version,
                summary=_observation_audit_summary(value),
            )
            self._seal_receipt(
                receipt,
                operation=operation,
                target_object_type="observation_period_revision",
                target_global_id=value.global_id,
                project_id=project_id,
                response=response,
                updated_at=now,
            )
        return ProductionTransitionCommandOutcome(response, False, value.global_id)

    def _workspace_for(self, project) -> dict[str, Any]:
        project_id = UUID(str(project.global_id))
        handovers = self._handover_chain(project, for_update=False)
        handover_views = [
            self._handover_view(project, value) for value in handovers
        ]
        observations = self._observation_chain(project, for_update=False)
        observation_responses = [_observation_response(value) for value in observations]
        current_handover = handover_views[-1] if handover_views else None
        current_observation = observation_responses[-1] if observation_responses else None
        administrator = self._can_administer_project(project, project_id)
        mutable = str(project.lifecycle_state) not in {"cancelled", "completed"}
        acknowledgement_slots = self._acknowledgeable_slots(
            project,
            handovers[-1] if handovers else None,
        )
        response = {
            "projectGlobalId": str(project_id),
            "currentHandover": current_handover,
            "handoverHistory": handover_views,
            "currentObservation": current_observation,
            "observationHistory": observation_responses,
            "unavailableProviders": [
                value.snapshot_payload()
                for value in unavailable_observation_providers()
            ],
            "permissions": {
                "canManagePolicies": administrator,
                "canCreateHandover": administrator and mutable and not handovers,
                "canReviseHandover": administrator and mutable and bool(handovers),
                "canAcknowledgeSlots": list(acknowledgement_slots),
                "canCreateObservation": administrator and mutable and not observations,
                "canReviseObservation": administrator and mutable and bool(observations),
            },
        }
        return validate_workspace_response(
            response,
            project_global_id=project_id,
            tenant_id=str(project.tenant_id),
        )

    def _handover_view(
        self,
        project,
        value: HandoverPackageRevision,
    ) -> dict[str, Any]:
        acknowledgements = self._acknowledgements_for(
            project,
            value,
            for_update=False,
        )
        return {
            "revision": _handover_response(value),
            "acknowledgements": [
                _acknowledgement_response(item) for item in acknowledgements
            ],
            "fullyAcknowledged": derive_fully_acknowledged(
                value,
                acknowledgements,
            ),
        }

    def _acknowledgeable_slots(
        self,
        project,
        package: HandoverPackageRevision | None,
    ) -> tuple[str, ...]:
        if package is None or self.principal.is_external:
            return ()
        if str(project.lifecycle_state) in {"cancelled", "completed"}:
            return ()
        acknowledgements = self._acknowledgements_for(
            project,
            package,
            for_update=False,
        )
        completed = {value.slot_key for value in acknowledgements}
        today = self._now().date()
        result = []
        for slot in package.slots:
            if slot.slot_key in completed or (
                slot.member.user_id.casefold() != self.actor.casefold()
            ):
                continue
            try:
                member = self._member_snapshot(
                    project,
                    slot.member.global_id,
                    for_update=False,
                )
                role = self._role_snapshot(
                    project,
                    slot.role.global_id,
                    for_update=False,
                )
            except RequestValidationFailed:
                continue
            if (
                member == slot.member
                and role == slot.role
                and member.is_effective(today)
                and role.is_effective(today)
                and _enabled_system_user(self.actor)
            ):
                result.append(slot.slot_key)
        return tuple(sorted(result))

    def _policy_chain(
        self,
        policy_id: UUID,
        *,
        tenant_id: str,
        for_update: bool,
    ) -> tuple[ProductionTransitionPolicyVersion, ...]:
        names = frappe.get_all(
            "NPI Production Transition Policy Version",
            filters={
                "policy_global_id": str(policy_id),
                "tenant_id": tenant_id,
            },
            pluck="name",
            order_by="policy_version asc, global_id asc",
            limit_page_length=_MAX_POLICY_VERSIONS + 1,
        )
        if len(names) > _MAX_POLICY_VERSIONS:
            raise RuntimeError(
                "Persisted Production Transition Policy collection exceeds its safe bound."
            )
        values = tuple(
            _policy_from_document(
                frappe.get_doc(
                    "NPI Production Transition Policy Version",
                    str(name),
                    for_update=for_update,
                )
            )
            for name in names
        )
        _validate_policy_chain(policy_id, tenant_id, values)
        _validate_policy_root(
            policy_id,
            tenant_id,
            values,
            for_update=for_update,
        )
        return values

    def _all_policy_versions(
        self,
        *,
        tenant_id: str,
        for_update: bool,
    ) -> tuple[ProductionTransitionPolicyVersion, ...]:
        names = frappe.get_all(
            "NPI Production Transition Policy Version",
            filters={"tenant_id": tenant_id},
            pluck="name",
            order_by="policy_global_id asc, policy_version asc, global_id asc",
            limit_page_length=_MAX_POLICY_VERSIONS + 1,
        )
        if len(names) > _MAX_POLICY_VERSIONS:
            raise RuntimeError(
                "Persisted Production Transition Policy catalog exceeds its safe bound."
            )
        values = tuple(
            _policy_from_document(
                frappe.get_doc(
                    "NPI Production Transition Policy Version",
                    str(name),
                    for_update=for_update,
                )
            )
            for name in names
        )
        grouped: dict[UUID, list[ProductionTransitionPolicyVersion]] = {}
        for value in values:
            grouped.setdefault(value.policy_global_id, []).append(value)
        for policy_id, chain in grouped.items():
            _validate_policy_chain(policy_id, tenant_id, tuple(chain))
            _validate_policy_root(
                policy_id,
                tenant_id,
                tuple(chain),
                for_update=for_update,
            )
        return values

    def _published_policy(
        self,
        reference,
        *,
        tenant_id: str,
        for_update: bool,
    ) -> ProductionTransitionPolicyVersion:
        chain = self._policy_chain(
            reference.policy_global_id,
            tenant_id=tenant_id,
            for_update=for_update,
        )
        matches = [
            value
            for value in chain
            if value.policy_version == reference.policy_version
        ]
        if len(matches) != 1:
            raise _field_problem(
                "policyRef",
                _("Select an exact published policy version."),
            )
        value = matches[0]
        if (
            value.publication_state is not PolicyPublicationState.PUBLISHED
            or value.snapshot_hash != reference.policy_snapshot_hash
        ):
            raise _field_problem(
                "policyRef",
                _("Select an exact published policy version."),
            )
        return value

    def _policy_by_exact_ref(
        self,
        reference: ExactVersionReference,
        *,
        tenant_id: str,
        for_update: bool,
    ) -> ProductionTransitionPolicyVersion:
        document = _single_document(
            "NPI Production Transition Policy Version",
            {
                "global_id": str(reference.global_id),
                "tenant_id": tenant_id,
            },
            for_update=for_update,
        )
        if document is None:
            raise ProductionTransitionVersionConflict()
        value = _policy_from_document(document)
        if (
            value.global_id != reference.global_id
            or value.tenant_id != tenant_id
            or value.policy_version != reference.version
            or value.snapshot_hash != reference.snapshot_hash
            or value.publication_state is not PolicyPublicationState.PUBLISHED
        ):
            raise ProductionTransitionVersionConflict()
        self._policy_chain(
            value.policy_global_id,
            tenant_id=tenant_id,
            for_update=for_update,
        )
        return value

    def _handover_chain(
        self,
        project,
        *,
        for_update: bool,
    ) -> tuple[HandoverPackageRevision, ...]:
        names = frappe.get_all(
            "NPI Handover Package Revision",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
            },
            pluck="name",
            order_by="handover_version asc, global_id asc",
            limit_page_length=_MAX_HANDOVER_REVISIONS + 1,
        )
        if len(names) > _MAX_HANDOVER_REVISIONS:
            raise RuntimeError("Persisted handover collection exceeds its safe bound.")
        values = tuple(
            _handover_from_document(
                frappe.get_doc(
                    "NPI Handover Package Revision",
                    str(name),
                    for_update=for_update,
                )
            )
            for name in names
        )
        if not values:
            return ()
        if (
            len({value.handover_global_id for value in values}) != 1
            or any(
                value.tenant_id != str(project.tenant_id)
                or value.project.global_id != UUID(str(project.global_id))
                for value in values
            )
        ):
            raise RuntimeError("Persisted handover stream scope is invalid.")
        by_version = _unique_version_map(
            values,
            lambda item: item.handover_version,
            "Persisted handover lineage is ambiguous.",
        )
        ordered = tuple(by_version[index] for index in range(1, len(values) + 1))
        for current, successor in zip(ordered, ordered[1:]):
            validate_handover_successor(current, successor)
        return ordered

    def _observation_chain(
        self,
        project,
        *,
        for_update: bool,
    ) -> tuple[ObservationPeriodRevision, ...]:
        names = frappe.get_all(
            "NPI Observation Period Revision",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
            },
            pluck="name",
            order_by="observation_version asc, global_id asc",
            limit_page_length=_MAX_OBSERVATION_REVISIONS + 1,
        )
        if len(names) > _MAX_OBSERVATION_REVISIONS:
            raise RuntimeError("Persisted observation collection exceeds its safe bound.")
        values = tuple(
            _observation_from_document(
                frappe.get_doc(
                    "NPI Observation Period Revision",
                    str(name),
                    for_update=for_update,
                )
            )
            for name in names
        )
        if not values:
            return ()
        if (
            len({value.observation_global_id for value in values}) != 1
            or any(
                value.tenant_id != str(project.tenant_id)
                or value.project.global_id != UUID(str(project.global_id))
                for value in values
            )
        ):
            raise RuntimeError("Persisted observation stream scope is invalid.")
        by_version = _unique_version_map(
            values,
            lambda item: item.observation_version,
            "Persisted observation lineage is ambiguous.",
        )
        ordered = tuple(by_version[index] for index in range(1, len(values) + 1))
        for current, successor in zip(ordered, ordered[1:]):
            validate_observation_successor(current, successor)
        return ordered

    def _acknowledgements_for(
        self,
        project,
        package: HandoverPackageRevision,
        *,
        for_update: bool,
    ) -> tuple[HandoverAcknowledgement, ...]:
        names = frappe.get_all(
            "NPI Handover Acknowledgement",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "package_revision_global_id": str(package.global_id),
            },
            pluck="name",
            order_by="slot_key asc, global_id asc",
            limit_page_length=_MAX_ACKNOWLEDGEMENTS + 1,
        )
        if len(names) > _MAX_ACKNOWLEDGEMENTS:
            raise RuntimeError(
                "Persisted acknowledgement collection exceeds its safe bound."
            )
        values = tuple(
            _acknowledgement_from_document(
                frappe.get_doc(
                    "NPI Handover Acknowledgement",
                    str(name),
                    for_update=for_update,
                )
            )
            for name in names
        )
        if len({value.global_id for value in values}) != len(values) or len(
            {value.slot_key for value in values}
        ) != len(values):
            raise RuntimeError("Persisted acknowledgement facts are ambiguous.")
        for value in values:
            if (
                value.handover_global_id != package.handover_global_id
                or value.package_revision_global_id != package.global_id
                or value.package_version != package.handover_version
                or value.package_snapshot_hash != package.snapshot_hash
            ):
                raise RuntimeError("Persisted acknowledgement scope is invalid.")
        derive_fully_acknowledged(package, values)
        return values

    def _slot_bindings(
        self,
        project,
        policy: ProductionTransitionPolicyVersion,
        selections: Sequence[object],
        *,
        effective_date: date,
    ) -> tuple[tuple[FrozenAcknowledgementSlot, ...], frozenset[str]]:
        by_key = {str(value.slot_key): value for value in selections}
        if len(by_key) != len(selections) or set(by_key) != {
            value.key for value in policy.acknowledgement_slots
        }:
            raise _field_problem(
                "slotAssignments",
                _(
                    "Freeze exactly one Project member and role for every required acknowledgement slot."
                ),
            )
        loaded: dict[str, tuple[ProjectMemberSnapshot, ProjectRoleSnapshot]] = {}
        for key in sorted(by_key):
            selection = by_key[key]
            member = self._member_snapshot(
                project,
                selection.member_global_id,
                for_update=True,
            )
            role = self._role_snapshot(
                project,
                selection.role_assignment_global_id,
                for_update=True,
            )
            if (
                member.optimistic_version != selection.member_expected_version
                or role.optimistic_version != selection.role_expected_version
                or role.member_global_id != member.global_id
                or not member.is_effective(effective_date)
                or not role.is_effective(effective_date)
                or not _enabled_system_user(member.user_id, for_update=True)
            ):
                raise _field_problem(
                    "slotAssignments",
                    _(
                        "The acknowledgement member and role must be enabled and currently effective for this Project."
                    ),
                )
            loaded[key] = (member, role)
        definitions = {value.key: value for value in policy.acknowledgement_slots}
        slots = tuple(
            FrozenAcknowledgementSlot(
                slot_key=key,
                group_key=definitions[key].group_key,
                direction=definitions[key].direction,
                member=loaded[key][0],
                role=loaded[key][1],
            )
            for key in (value.key for value in policy.acknowledgement_slots)
        )
        return slots, frozenset(value.member.user_id for value in slots)

    def _member_snapshot(
        self,
        project,
        member_id: UUID,
        *,
        for_update: bool,
    ) -> ProjectMemberSnapshot:
        document = _optional_doc(
            "NPI Project Member",
            str(member_id),
            for_update=for_update,
        )
        if (
            document is None
            or str(_value(document, "global_id")) != str(member_id)
            or str(_value(document, "tenant_id")) != str(project.tenant_id)
            or str(_value(document, "project_global_id")) != str(project.global_id)
        ):
            raise _field_problem(
                "memberGlobalId",
                _("Select exact Project member and role assignments."),
            )
        try:
            return ProjectMemberSnapshot(
                global_id=member_id,
                tenant_id=str(document.tenant_id),
                project_global_id=UUID(str(document.project_global_id)),
                user_id=str(document.user_id),
                effective_from=_date_value(document.effective_from),
                effective_to=(
                    _date_value(document.effective_to)
                    if document.effective_to
                    else None
                ),
                optimistic_version=int(document.optimistic_version),
            )
        except (AttributeError, TypeError, ValueError):
            raise _field_problem(
                "memberGlobalId",
                _("Select exact Project member and role assignments."),
            ) from None

    def _role_snapshot(
        self,
        project,
        role_id: UUID,
        *,
        for_update: bool,
    ) -> ProjectRoleSnapshot:
        document = _optional_doc(
            "NPI Project Role Assignment",
            str(role_id),
            for_update=for_update,
        )
        if (
            document is None
            or str(_value(document, "global_id")) != str(role_id)
            or str(_value(document, "tenant_id")) != str(project.tenant_id)
            or str(_value(document, "project_global_id")) != str(project.global_id)
        ):
            raise _field_problem(
                "roleAssignmentGlobalId",
                _("Select exact Project member and role assignments."),
            )
        try:
            return ProjectRoleSnapshot(
                global_id=role_id,
                tenant_id=str(document.tenant_id),
                project_global_id=UUID(str(document.project_global_id)),
                member_global_id=UUID(str(document.member_global_id)),
                role_key=str(document.role_key),
                effective_from=_date_value(document.effective_from),
                effective_to=(
                    _date_value(document.effective_to)
                    if document.effective_to
                    else None
                ),
                optimistic_version=int(document.optimistic_version),
            )
        except (AttributeError, TypeError, ValueError):
            raise _field_problem(
                "roleAssignmentGlobalId",
                _("Select exact Project member and role assignments."),
            ) from None

    def _unresolved_actions(
        self,
        project,
        *,
        for_update: bool,
    ) -> tuple[UnresolvedActionSnapshot, ...]:
        names = frappe.get_all(
            "NPI Domain Work Item",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "state_terminal": 0,
            },
            pluck="name",
            order_by="global_id asc",
            limit_page_length=_MAX_UNRESOLVED_ACTIONS + 1,
        )
        if len(names) > _MAX_UNRESOLVED_ACTIONS:
            raise _field_problem(
                "projectId",
                _("Enter a supported object count."),
            )
        from npi_core.readiness.frappe_repository import (
            _domain_work_item_source_snapshot,
            _domain_work_item_value,
        )

        actions = []
        identities: set[UUID] = set()
        for name in names:
            document = frappe.get_doc(
                "NPI Domain Work Item",
                str(name),
                for_update=for_update,
            )
            value = _domain_work_item_value(document)
            if (
                value is None
                or value.global_id in identities
                or value.tenant_id != str(project.tenant_id)
                or value.project_global_id != UUID(str(project.global_id))
                or value.state_terminal
                or value.kind.value not in {item.value for item in WorkItemKind}
                or not value.owner_user_id
                or value.due_at is None
            ):
                raise RuntimeError("Persisted unresolved Work Item integrity failed.")
            identities.add(value.global_id)
            actions.append(
                UnresolvedActionSnapshot(
                    global_id=value.global_id,
                    source_version=value.version,
                    snapshot_hash=_payload_hash(
                        _domain_work_item_source_snapshot(value)
                    ),
                    kind=WorkItemKind(value.kind.value),
                    state=value.state_key,
                    owner_user_id=value.owner_user_id,
                    due_date=value.due_at.date(),
                )
            )
        ordered = tuple(sorted(actions, key=lambda item: str(item.global_id)))
        if tuple(str(value.global_id) for value in ordered) != tuple(
            sorted(str(value) for value in identities)
        ):
            raise RuntimeError("Persisted unresolved Work Item ordering drifted.")
        return ordered

    def _requested_handover_reference(
        self,
        project,
        reference,
        *,
        require_current: bool,
    ) -> ExactVersionReference | None:
        if reference is None:
            return None
        chain = self._handover_chain(project, for_update=True)
        matches = [
            value
            for value in chain
            if value.handover_global_id == reference.handover_global_id
            and value.handover_version == reference.handover_version
        ]
        if len(matches) != 1 or (require_current and matches[0] != chain[-1]):
            raise ProductionTransitionVersionConflict()
        value = matches[0]
        if (
            value.global_id != reference.handover_revision_global_id
            or value.snapshot_hash != reference.handover_snapshot_hash
        ):
            raise ProductionTransitionVersionConflict()
        return ExactVersionReference(
            value.global_id,
            value.handover_version,
            value.snapshot_hash,
        )

    def _exact_handover_reference(
        self,
        project,
        reference: ExactVersionReference | None,
    ) -> ExactVersionReference | None:
        if reference is None:
            return None
        chain = self._handover_chain(project, for_update=True)
        matches = [value for value in chain if value.global_id == reference.global_id]
        if len(matches) != 1:
            raise ProductionTransitionVersionConflict()
        value = matches[0]
        if (
            value.handover_version != reference.version
            or value.snapshot_hash != reference.snapshot_hash
        ):
            raise ProductionTransitionVersionConflict()
        return reference

    def _authorized_project(self, project_id: UUID):
        project = _optional_doc("NPI Engineering Project", str(project_id))
        return (
            project
            if project is not None and self._can_view_project(project, project_id)
            else None
        )

    def _locked_authorized_project(
        self,
        project_id: UUID,
        *,
        administer: bool,
    ):
        project = _locked_optional_doc("NPI Engineering Project", str(project_id))
        if project is None:
            return None
        allowed = (
            self._can_administer_project(project, project_id)
            if administer
            else self._can_view_project(project, project_id)
        )
        return project if allowed else None

    def _can_view_project(self, project, project_id: UUID) -> bool:
        if (
            self.principal.is_external
            or not self.principal.tenant_id
            or self.principal.tenant_id != str(project.tenant_id)
            or str(project.global_id) != str(project_id)
        ):
            return False
        if self._is_internal_system_manager() or str(
            project.owner_user_id
        ).casefold() == self.actor.casefold():
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
            not self.principal.is_external
            and "System Manager" in self.principal.roles
            and _enabled_system_user(self.actor)
        )

    def _require_policy_administrator(self) -> str:
        if not self._is_internal_system_manager() or not self.principal.tenant_id:
            raise PermissionDenied()
        return self.principal.tenant_id

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
            limit_page_length=_MAX_PROJECT_MEMBERS + 1,
        )
        if len(names) > _MAX_PROJECT_MEMBERS:
            raise RuntimeError("Persisted Project member collection exceeds its safe bound.")
        today = self._now().date()
        matches = [
            document
            for name in names
            if (
                (document := frappe.get_doc("NPI Project Member", str(name)))
                and _member_effective(document, today)
                and _enabled_system_user(self.actor)
            )
        ]
        return matches[0] if len(matches) == 1 else None

    def _source_project(self, context: SourceResolutionContext):
        project = self._authorized_project(context.project_global_id)
        if (
            project is None
            or str(project.tenant_id) != context.tenant_id
            or str(project.global_id) != str(context.project_global_id)
        ):
            return None
        return project

    @staticmethod
    def _require_project_version(project, expected_version: int) -> None:
        if int(project.optimistic_version) != expected_version:
            raise ProductionTransitionVersionConflict()

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise RuntimeError("Production transition clock must be timezone-aware.")
        return value.astimezone(UTC)

    @staticmethod
    def _handover_audit_summary(value: HandoverPackageRevision) -> dict[str, Any]:
        return {
            "occurredAt": _utc_datetime_text(value.created_at),
            "handoverGlobalId": str(value.handover_global_id),
            "handoverVersion": value.handover_version,
            "manifestSourceCount": len(value.manifest),
            "manifestSourceSummary": [
                item.snapshot_payload() for item in value.manifest
            ],
            "policyRef": value.policy_ref.snapshot_payload(),
            "predecessorGlobalId": (
                str(value.predecessor_global_id)
                if value.predecessor_global_id
                else None
            ),
            "predecessorSnapshotHash": value.predecessor_snapshot_hash,
            "projectId": str(value.project.global_id),
            "requestId": str(value.request_id),
            "snapshotHash": value.snapshot_hash,
            "tenantId": value.tenant_id,
            "unresolvedActionCount": len(value.unresolved_actions),
        }

    def _idempotency_replay(
        self,
        *,
        tenant_id: str,
        project_id: UUID | None,
        operation: str,
        idempotency_key_hash: str,
        payload_hash: str,
    ) -> ProductionTransitionCommandOutcome | None:
        receipt_key = _receipt_key(
            tenant_id=tenant_id,
            project_id=project_id,
            actor=self.actor,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
        )
        record = frappe.db.get_value(
            "NPI Production Transition Command Idempotency",
            {"receipt_key": receipt_key},
            [
                "tenant_id",
                "project_global_id",
                "actor_user_id",
                "operation",
                "idempotency_key_hash",
                "payload_hash",
                "target_object_type",
                "target_global_id",
                "response_payload",
                "response_hash",
                "sealed",
            ],
            as_dict=True,
            for_update=True,
        )
        if not record:
            return None
        if str(_value(record, "payload_hash")) != payload_hash:
            raise ProductionTransitionIdempotencyConflict()
        expected_project = str(project_id) if project_id else None
        target_type = _TARGET_TYPES.get(operation)
        if (
            str(_value(record, "tenant_id")) != tenant_id
            or (_value(record, "project_global_id") or None) != expected_project
            or str(_value(record, "actor_user_id")).casefold()
            != self.actor.casefold()
            or str(_value(record, "operation")) != operation
            or str(_value(record, "idempotency_key_hash"))
            != idempotency_key_hash
            or str(_value(record, "target_object_type")) != target_type
            or int(_value(record, "sealed") or 0) != 1
        ):
            raise RuntimeError(
                "Persisted production transition idempotency receipt integrity failed."
            )
        try:
            target_id = UUID(str(_value(record, "target_global_id")))
        except (TypeError, ValueError):
            raise RuntimeError(
                "Persisted production transition idempotency target is invalid."
            ) from None
        response = _json_object(_value(record, "response_payload"))
        if _payload_hash(response) != str(_value(record, "response_hash")):
            raise RuntimeError(
                "Persisted production transition idempotency response integrity failed."
            )
        response = validate_receipt_response(
            operation,
            response,
            target_global_id=target_id,
            project_global_id=project_id,
            tenant_id=tenant_id,
        )
        return ProductionTransitionCommandOutcome(response, True, target_id)

    def _insert_receipt(
        self,
        *,
        tenant_id: str,
        project_id: UUID | None,
        operation: str,
        idempotency_key_hash: str,
        payload_hash: str,
        created_at: datetime,
    ):
        receipt_key = _receipt_key(
            tenant_id=tenant_id,
            project_id=project_id,
            actor=self.actor,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
        )
        try:
            return frappe.get_doc(
                {
                    "doctype": "NPI Production Transition Command Idempotency",
                    "global_id": str(self._uuid_factory()),
                    "receipt_key": receipt_key,
                    "tenant_id": tenant_id,
                    "project_global_id": str(project_id) if project_id else None,
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
                tenant_id=tenant_id,
                project_id=project_id,
                operation=operation,
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
            )
            if replay is None:
                raise
            return replay

    @staticmethod
    def _seal_receipt(
        receipt,
        *,
        operation: str,
        target_object_type: str,
        target_global_id: UUID,
        project_id: UUID | None,
        response: Mapping[str, Any],
        updated_at: datetime,
    ) -> None:
        if _TARGET_TYPES.get(operation) != target_object_type:
            raise RuntimeError("Production transition receipt target type drifted.")
        validated = validate_receipt_response(
            operation,
            response,
            target_global_id=target_global_id,
            project_global_id=project_id,
            tenant_id=str(_value(receipt, "tenant_id")),
        )
        receipt.target_object_type = target_object_type
        receipt.target_global_id = str(target_global_id)
        receipt.response_payload = validated
        receipt.response_hash = _payload_hash(validated)
        receipt.sealed = 1
        receipt.updated_at = _database_datetime(updated_at)
        receipt.save()

    @staticmethod
    def _insert_policy_version(value: ProductionTransitionPolicyVersion) -> None:
        document = frappe.get_doc(
            {"doctype": "NPI Production Transition Policy Version"}
        )
        _apply_policy_version(document, value)
        document.insert()

    @staticmethod
    def _insert_handover_revision(value: HandoverPackageRevision) -> None:
        frappe.get_doc(
            {
                "doctype": "NPI Handover Package Revision",
                "global_id": str(value.global_id),
                "handover_global_id": str(value.handover_global_id),
                "version_key_hash": value.version_key_hash,
                "tenant_id": value.tenant_id,
                "project": str(value.project.global_id),
                "project_global_id": str(value.project.global_id),
                "project_optimistic_version": value.project.optimistic_version,
                "project_snapshot_hash": value.project.snapshot_hash,
                "policy_version": str(value.policy_ref.global_id),
                "policy_version_global_id": str(value.policy_ref.global_id),
                "policy_business_version": value.policy_ref.version,
                "policy_snapshot_hash": value.policy_ref.snapshot_hash,
                "handover_version": value.handover_version,
                "predecessor_global_id": (
                    str(value.predecessor_global_id)
                    if value.predecessor_global_id
                    else None
                ),
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "readiness_revision_global_id": (
                    str(value.readiness_ref.global_id)
                    if value.readiness_ref
                    else None
                ),
                "readiness_revision_version": (
                    value.readiness_ref.version if value.readiness_ref else None
                ),
                "readiness_revision_snapshot_hash": (
                    value.readiness_ref.snapshot_hash
                    if value.readiness_ref
                    else None
                ),
                "project_snapshot": value.project.snapshot_payload(),
                "slot_snapshot": [item.snapshot_payload() for item in value.slots],
                "manifest_snapshot": [
                    item.snapshot_payload() for item in value.manifest
                ],
                "unresolved_selector_snapshot": {
                    "mode": "all_non_terminal",
                    "kinds": ["action", "decision_request", "issue", "risk"],
                },
                "unresolved_action_snapshot": [
                    item.snapshot_payload() for item in value.unresolved_actions
                ],
                "reason": value.reason,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "package_snapshot": value.snapshot_payload(),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    @staticmethod
    def _insert_acknowledgement(
        project,
        value: HandoverAcknowledgement,
    ) -> None:
        project_id = UUID(str(project.global_id))
        frappe.get_doc(
            {
                "doctype": "NPI Handover Acknowledgement",
                "global_id": str(value.global_id),
                "tenant_id": str(project.tenant_id),
                "project": str(project_id),
                "project_global_id": str(project_id),
                "handover_global_id": str(value.handover_global_id),
                "package_revision": str(value.package_revision_global_id),
                "package_revision_global_id": str(value.package_revision_global_id),
                "package_version": value.package_version,
                "package_snapshot_hash": value.package_snapshot_hash,
                "slot_key": value.slot_key,
                "acknowledgement_intent": "acknowledge_exact_package_slot",
                "actor_user_id": value.actor_user_id,
                "member_global_id": str(value.member_global_id),
                "member_optimistic_version": value.member_optimistic_version,
                "member_snapshot_hash": value.member_snapshot_hash,
                "role_global_id": str(value.role_global_id),
                "role_optimistic_version": value.role_optimistic_version,
                "role_snapshot_hash": value.role_snapshot_hash,
                "acknowledged_at": _database_datetime(value.acknowledged_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "acknowledgement_snapshot": value.snapshot_payload(),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    @staticmethod
    def _insert_observation_revision(value: ObservationPeriodRevision) -> None:
        frappe.get_doc(
            {
                "doctype": "NPI Observation Period Revision",
                "global_id": str(value.global_id),
                "observation_global_id": str(value.observation_global_id),
                "version_key_hash": value.version_key_hash,
                "tenant_id": value.tenant_id,
                "project": str(value.project.global_id),
                "project_global_id": str(value.project.global_id),
                "project_optimistic_version": value.project.optimistic_version,
                "project_snapshot_hash": value.project.snapshot_hash,
                "policy_version": str(value.policy_ref.global_id),
                "policy_version_global_id": str(value.policy_ref.global_id),
                "policy_business_version": value.policy_ref.version,
                "policy_snapshot_hash": value.policy_ref.snapshot_hash,
                "observation_version": value.observation_version,
                "predecessor_global_id": (
                    str(value.predecessor_global_id)
                    if value.predecessor_global_id
                    else None
                ),
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "handover_package_revision": (
                    str(value.handover_package_ref.global_id)
                    if value.handover_package_ref
                    else None
                ),
                "handover_package_revision_global_id": (
                    str(value.handover_package_ref.global_id)
                    if value.handover_package_ref
                    else None
                ),
                "handover_package_version": (
                    value.handover_package_ref.version
                    if value.handover_package_ref
                    else None
                ),
                "handover_package_snapshot_hash": (
                    value.handover_package_ref.snapshot_hash
                    if value.handover_package_ref
                    else None
                ),
                "project_snapshot": value.project.snapshot_payload(),
                "provider_source_snapshot": [
                    item.snapshot_payload() for item in value.providers
                ],
                "context_reference_snapshot": [
                    item.snapshot_payload() for item in value.context_references
                ],
                "retrospective_evidence_snapshot": [
                    item.snapshot_payload()
                    for item in value.retrospective_references
                ],
                "observation_state": value.observation_state.value,
                "technical_disposition": value.technical_disposition.value,
                "retrospective_note": value.retrospective_note,
                "reason": value.reason,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "observation_snapshot": value.snapshot_payload(),
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


_TARGET_TYPES = {
    "production_transition_policy.create": "production_transition_policy",
    "production_transition_policy.edit": "production_transition_policy_version",
    "production_transition_policy.publish": "production_transition_policy_version",
    "production_transition_policy.next_version": "production_transition_policy_version",
    "production_handover.create": "handover_package_revision",
    "production_handover.revise": "handover_package_revision",
    "production_handover.acknowledge": "handover_acknowledgement",
    "observation_period.create": "observation_period_revision",
    "observation_period.revise": "observation_period_revision",
}


def _policy_response(value: ProductionTransitionPolicyVersion) -> dict[str, Any]:
    return {**value.snapshot_payload(), "snapshotHash": value.snapshot_hash}


def _handover_response(value: HandoverPackageRevision) -> dict[str, Any]:
    return {**value.snapshot_payload(), "snapshotHash": value.snapshot_hash}


def _acknowledgement_response(value: HandoverAcknowledgement) -> dict[str, Any]:
    return {**value.snapshot_payload(), "snapshotHash": value.snapshot_hash}


def _observation_response(value: ObservationPeriodRevision) -> dict[str, Any]:
    return {**value.snapshot_payload(), "snapshotHash": value.snapshot_hash}


def _handover_command_response(
    project_id: UUID,
    value: HandoverPackageRevision,
) -> dict[str, Any]:
    return {
        "projectGlobalId": str(project_id),
        "handoverPackage": _handover_response(value),
    }


def _acknowledgement_command_response(
    project_id: UUID,
    package: HandoverPackageRevision,
    value: HandoverAcknowledgement,
) -> dict[str, Any]:
    return {
        "projectGlobalId": str(project_id),
        "handoverPackage": _handover_response(package),
        "acknowledgement": _acknowledgement_response(value),
    }


def _observation_command_response(
    project_id: UUID,
    value: ObservationPeriodRevision,
) -> dict[str, Any]:
    return {
        "projectGlobalId": str(project_id),
        "observationPeriod": _observation_response(value),
    }


def _acknowledgement_audit_summary(
    package: HandoverPackageRevision,
    value: HandoverAcknowledgement,
) -> dict[str, Any]:
    return {
        "acknowledgementSnapshotHash": value.snapshot_hash,
        "acknowledgedAt": _utc_datetime_text(value.acknowledged_at),
        "handoverGlobalId": str(value.handover_global_id),
        "memberRef": {
            "globalId": str(value.member_global_id),
            "optimisticVersion": value.member_optimistic_version,
            "snapshotHash": value.member_snapshot_hash,
        },
        "packageRevisionGlobalId": str(value.package_revision_global_id),
        "packageSnapshotHash": value.package_snapshot_hash,
        "packageVersion": value.package_version,
        "policyRef": package.policy_ref.snapshot_payload(),
        "requestId": str(value.request_id),
        "roleRef": {
            "globalId": str(value.role_global_id),
            "optimisticVersion": value.role_optimistic_version,
            "snapshotHash": value.role_snapshot_hash,
        },
        "slotKey": value.slot_key,
        "tenantId": package.tenant_id,
    }


def _observation_audit_summary(
    value: ObservationPeriodRevision,
) -> dict[str, Any]:
    return {
        "contextSourceSummary": [
            item.snapshot_payload() for item in value.context_references
        ],
        "handoverPackageRef": (
            value.handover_package_ref.snapshot_payload()
            if value.handover_package_ref
            else None
        ),
        "observationGlobalId": str(value.observation_global_id),
        "observationState": value.observation_state.value,
        "observationVersion": value.observation_version,
        "occurredAt": _utc_datetime_text(value.created_at),
        "policyRef": value.policy_ref.snapshot_payload(),
        "predecessorGlobalId": (
            str(value.predecessor_global_id)
            if value.predecessor_global_id
            else None
        ),
        "predecessorSnapshotHash": value.predecessor_snapshot_hash,
        "projectId": str(value.project.global_id),
        "providerSummary": [
            item.snapshot_payload() for item in value.providers
        ],
        "requestId": str(value.request_id),
        "retrospectiveSourceSummary": [
            item.snapshot_payload() for item in value.retrospective_references
        ],
        "snapshotHash": value.snapshot_hash,
        "technicalDisposition": value.technical_disposition.value,
        "tenantId": value.tenant_id,
    }


def _policy_from_document(document) -> ProductionTransitionPolicyVersion:
    value = policy_from_snapshot(_json_object(_value(document, "policy_snapshot")))
    prior = value.prior_version_ref
    if any(
        (
            str(value.global_id) != str(_value(document, "global_id")),
            str(value.policy_global_id)
            != str(_value(document, "policy_global_id")),
            value.tenant_id != str(_value(document, "tenant_id")),
            value.policy_code != str(_value(document, "policy_code")),
            value.policy_version != int(_value(document, "policy_version")),
            value.optimistic_version
            != int(_value(document, "optimistic_version")),
            value.publication_state.value
            != str(_value(document, "publication_state")),
            (str(prior.global_id) if prior else None)
            != (_value(document, "predecessor_global_id") or None),
            (prior.snapshot_hash if prior else None)
            != (_value(document, "predecessor_snapshot_hash") or None),
            value.version_key_hash != str(_value(document, "version_key_hash")),
            value.snapshot_hash != str(_value(document, "snapshot_hash")),
        )
    ):
        raise RuntimeError("Persisted Production Transition Policy integrity failed.")
    return value


def _apply_policy_version(document, value: ProductionTransitionPolicyVersion) -> None:
    prior = value.prior_version_ref
    document.global_id = str(value.global_id)
    document.policy = str(value.policy_global_id)
    document.policy_global_id = str(value.policy_global_id)
    document.tenant_id = value.tenant_id
    document.version_key_hash = value.version_key_hash
    document.policy_code = value.policy_code
    document.policy_version = value.policy_version
    document.optimistic_version = value.optimistic_version
    document.title = value.title
    document.publication_state = value.publication_state.value
    document.predecessor_global_id = str(prior.global_id) if prior else None
    document.predecessor_snapshot_hash = prior.snapshot_hash if prior else None
    document.applicability_snapshot = value.applicability.snapshot_payload()
    document.receiving_group_snapshot = [
        item.snapshot_payload() for item in value.receiving_groups
    ]
    document.acknowledgement_slot_snapshot = [
        item.snapshot_payload() for item in value.acknowledgement_slots
    ]
    document.handover_object_requirement_snapshot = [
        item.snapshot_payload() for item in value.handover_requirements
    ]
    document.unresolved_action_rule_snapshot = {
        "mode": "all_non_terminal",
        "kinds": ["action", "decision_request", "issue", "risk"],
    }
    document.observation_source_requirement_snapshot = [
        item.snapshot_payload() for item in value.observation_source_rules
    ]
    document.conclusion_rule_snapshot = [
        {
            "providerKind": item.provider_kind.value,
            "allowedDispositions": [
                disposition.value for disposition in item.allowed_dispositions
            ],
        }
        for item in value.observation_source_rules
    ]
    document.observation_window_days = value.observation_window_days
    document.changed_by_user_id = value.changed_by_user_id
    document.changed_at = _database_datetime(value.changed_at)
    document.request_id = str(value.request_id)
    document.trace_id = value.trace_id
    document.policy_snapshot = value.snapshot_payload()
    document.snapshot_hash = value.snapshot_hash


def _handover_from_document(document) -> HandoverPackageRevision:
    value = handover_package_from_snapshot(
        _json_object(_value(document, "package_snapshot"))
    )
    readiness = value.readiness_ref
    if any(
        (
            str(value.global_id) != str(_value(document, "global_id")),
            str(value.handover_global_id)
            != str(_value(document, "handover_global_id")),
            value.version_key_hash != str(_value(document, "version_key_hash")),
            value.tenant_id != str(_value(document, "tenant_id")),
            str(value.project.global_id)
            != str(_value(document, "project_global_id")),
            value.project.optimistic_version
            != int(_value(document, "project_optimistic_version")),
            value.project.snapshot_hash
            != str(_value(document, "project_snapshot_hash")),
            str(value.policy_ref.global_id)
            != str(_value(document, "policy_version_global_id")),
            value.policy_ref.version
            != int(_value(document, "policy_business_version")),
            value.policy_ref.snapshot_hash
            != str(_value(document, "policy_snapshot_hash")),
            value.handover_version != int(_value(document, "handover_version")),
            (str(value.predecessor_global_id) if value.predecessor_global_id else None)
            != (_value(document, "predecessor_global_id") or None),
            value.predecessor_snapshot_hash
            != (_value(document, "predecessor_snapshot_hash") or None),
            (str(readiness.global_id) if readiness else None)
            != (_value(document, "readiness_revision_global_id") or None),
            (readiness.version if readiness else None)
            != (_value(document, "readiness_revision_version") or None),
            (readiness.snapshot_hash if readiness else None)
            != (_value(document, "readiness_revision_snapshot_hash") or None),
            value.snapshot_hash != str(_value(document, "snapshot_hash")),
        )
    ):
        raise RuntimeError("Persisted handover package integrity failed.")
    return value


def _acknowledgement_from_document(document) -> HandoverAcknowledgement:
    value = acknowledgement_from_snapshot(
        _json_object(_value(document, "acknowledgement_snapshot"))
    )
    if any(
        (
            str(value.global_id) != str(_value(document, "global_id")),
            str(value.handover_global_id)
            != str(_value(document, "handover_global_id")),
            str(value.package_revision_global_id)
            != str(_value(document, "package_revision_global_id")),
            value.package_version != int(_value(document, "package_version")),
            value.package_snapshot_hash
            != str(_value(document, "package_snapshot_hash")),
            value.slot_key != str(_value(document, "slot_key")),
            value.actor_user_id.casefold()
            != str(_value(document, "actor_user_id")).casefold(),
            value.snapshot_hash != str(_value(document, "snapshot_hash")),
        )
    ):
        raise RuntimeError("Persisted handover acknowledgement integrity failed.")
    return value


def _observation_from_document(document) -> ObservationPeriodRevision:
    value = observation_from_snapshot(
        _json_object(_value(document, "observation_snapshot"))
    )
    handover = value.handover_package_ref
    if any(
        (
            str(value.global_id) != str(_value(document, "global_id")),
            str(value.observation_global_id)
            != str(_value(document, "observation_global_id")),
            value.version_key_hash != str(_value(document, "version_key_hash")),
            value.tenant_id != str(_value(document, "tenant_id")),
            str(value.project.global_id)
            != str(_value(document, "project_global_id")),
            value.project.optimistic_version
            != int(_value(document, "project_optimistic_version")),
            value.project.snapshot_hash
            != str(_value(document, "project_snapshot_hash")),
            str(value.policy_ref.global_id)
            != str(_value(document, "policy_version_global_id")),
            value.policy_ref.version
            != int(_value(document, "policy_business_version")),
            value.policy_ref.snapshot_hash
            != str(_value(document, "policy_snapshot_hash")),
            value.observation_version
            != int(_value(document, "observation_version")),
            (str(value.predecessor_global_id) if value.predecessor_global_id else None)
            != (_value(document, "predecessor_global_id") or None),
            value.predecessor_snapshot_hash
            != (_value(document, "predecessor_snapshot_hash") or None),
            (str(handover.global_id) if handover else None)
            != (_value(document, "handover_package_revision_global_id") or None),
            (handover.version if handover else None)
            != (_value(document, "handover_package_version") or None),
            (handover.snapshot_hash if handover else None)
            != (_value(document, "handover_package_snapshot_hash") or None),
            value.snapshot_hash != str(_value(document, "snapshot_hash")),
        )
    ):
        raise RuntimeError("Persisted observation-period integrity failed.")
    return value


def _validate_policy_chain(
    policy_id: UUID,
    tenant_id: str,
    values: tuple[ProductionTransitionPolicyVersion, ...],
) -> None:
    if not values:
        return
    if any(value.policy_global_id != policy_id for value in values):
        raise RuntimeError("Persisted Production Transition Policy scope is invalid.")
    if any(value.tenant_id != tenant_id for value in values):
        raise RuntimeError("Persisted Production Transition Policy scope is invalid.")
    if [value.policy_version for value in values] != list(
        range(1, len(values) + 1)
    ):
        raise RuntimeError("Persisted Production Transition Policy lineage is ambiguous.")
    if len({value.policy_code for value in values}) != 1:
        raise RuntimeError("Persisted Production Transition Policy identity drifted.")
    drafts = [
        index
        for index, value in enumerate(values)
        if value.publication_state is PolicyPublicationState.DRAFT
    ]
    if drafts and drafts != [len(values) - 1]:
        raise RuntimeError("Persisted Production Transition Policy draft tip is invalid.")
    for current, successor in zip(values, values[1:]):
        prior = successor.prior_version_ref
        if (
            current.publication_state is not PolicyPublicationState.PUBLISHED
            or prior is None
            or prior.global_id != current.global_id
            or prior.version != current.policy_version
            or prior.snapshot_hash != current.snapshot_hash
        ):
            raise RuntimeError("Persisted Production Transition Policy lineage is invalid.")


def _validate_policy_root(
    policy_id: UUID,
    tenant_id: str,
    values: tuple[ProductionTransitionPolicyVersion, ...],
    *,
    for_update: bool,
) -> None:
    root = _single_document(
        "NPI Production Transition Policy",
        {
            "global_id": str(policy_id),
            "tenant_id": tenant_id,
        },
        for_update=for_update,
    )
    if not values:
        if root is not None:
            raise RuntimeError(
                "Persisted Production Transition Policy has no version lineage."
            )
        return
    if root is None:
        raise RuntimeError("Persisted Production Transition Policy root is unavailable.")
    current = values[-1]
    try:
        optimistic_version = int(_value(root, "optimistic_version"))
    except (TypeError, ValueError):
        raise RuntimeError(
            "Persisted Production Transition Policy root integrity failed."
        ) from None
    if any(
        (
            str(_value(root, "global_id")) != str(policy_id),
            str(_value(root, "tenant_id")) != tenant_id,
            str(_value(root, "policy_code")) != current.policy_code,
            str(_value(root, "policy_code_key_hash"))
            != _policy_code_key_hash(tenant_id, current.policy_code),
            str(_value(root, "title")) != current.title,
            optimistic_version != current.optimistic_version,
        )
    ):
        raise RuntimeError(
            "Persisted Production Transition Policy root integrity failed."
        )


def _project_snapshot(project) -> ProjectTransitionSnapshot:
    try:
        project_id = UUID(str(project.global_id))
        template_id = UUID(str(project.template_global_id))
        template_version = int(project.template_version)
        template_hash = str(project.template_snapshot_hash)
        work_policy_id = UUID(str(project.work_policy_global_id))
        work_policy_version = int(project.work_policy_version)
        work_policy_hash = str(project.work_policy_snapshot_hash)
        from npi_core.project.frappe_repository import FrappeProjectRepository
        from npi_core.project_work.frappe_repository import FrappeProjectWorkRepository

        template = FrappeProjectRepository(
            principal=Principal("system"),
            request_id=str(uuid4()),
            trace_id="production-transition-project-snapshot",
        ).get_template_version(template_id, template_version)
        work_policy = FrappeProjectWorkRepository(
            principal=Principal("system"),
            request_id=str(uuid4()),
            trace_id="production-transition-project-snapshot",
        )._load_policy(
            {
                "globalId": str(work_policy_id),
                "version": work_policy_version,
                "snapshotHash": work_policy_hash,
            }
        )
        if (
            template is None
            or template.snapshot_hash != template_hash
            or template.publication_state.value != "published"
            or work_policy["ref"]
            != {
                "globalId": str(work_policy_id),
                "version": work_policy_version,
                "snapshotHash": work_policy_hash,
            }
        ):
            raise ValueError
        return ProjectTransitionSnapshot(
            global_id=project_id,
            tenant_id=str(project.tenant_id),
            optimistic_version=int(project.optimistic_version),
            business_code=str(project.business_code),
            title=str(project.title),
            project_type=ProjectType(str(project.project_type)),
            owner_user_id=str(project.owner_user_id),
            target_sop_date=_date_value(project.target_sop) if project.target_sop else None,
            lifecycle_state=str(project.lifecycle_state),
            template_ref=ExactVersionReference(
                template_id,
                template_version,
                template_hash,
            ),
            work_policy_ref=ExactVersionReference(
                work_policy_id,
                work_policy_version,
                work_policy_hash,
            ),
            customer_reference_keys=_customer_reference_keys(project),
        )
    except (AttributeError, KeyError, RequestValidationFailed, TypeError, ValueError):
        raise RuntimeError("Persisted Project transition snapshot integrity failed.") from None


def _customer_reference_keys(project) -> tuple[str, ...]:
    references = _value(project, "references") or ()
    keys = {
        f"{str(_value(value, 'source_system')).upper()}:"
        f"{str(_value(value, 'source_object_id')).strip()}"
        for value in references
        if str(_value(value, "reference_type")) == "customer"
        and str(_value(value, "source_system")).strip()
        and str(_value(value, "source_object_id")).strip()
    }
    return tuple(sorted(keys))


def _readiness_reference(
    manifest: Sequence[object],
) -> ExactVersionReference | None:
    matches = [
        value
        for value in manifest
        if value.kind is HandoverSourceKind.READINESS_INSTANCE_REVISION
    ]
    if len(matches) > 1:
        raise _field_problem(
            "manifestSources",
            _("Values must be unique."),
        )
    if not matches:
        return None
    value = matches[0]
    return ExactVersionReference(
        value.global_id,
        value.source_version,
        value.snapshot_hash,
    )


def _policy_definition_payload(request: object) -> dict[str, Any]:
    definition = request.definition
    return {
        "applicability": definition.applicability.snapshot_payload(),
        "receivingGroups": [
            value.snapshot_payload() for value in definition.receiving_groups
        ],
        "acknowledgementSlots": [
            value.snapshot_payload() for value in definition.acknowledgement_slots
        ],
        "handoverRequirements": [
            value.snapshot_payload() for value in definition.handover_requirements
        ],
        "observationSourceRules": [
            value.snapshot_payload() for value in definition.observation_source_rules
        ],
        "observationWindowDays": definition.observation_window_days,
    }


def _policy_reference_payload(reference: object) -> dict[str, Any]:
    return {
        "policyGlobalId": reference.policy_global_id,
        "policyVersion": reference.policy_version,
        "policySnapshotHash": reference.policy_snapshot_hash,
    }


def _source_selection_payload(value: object) -> dict[str, Any]:
    result = {
        "kind": value.kind,
        "globalId": value.global_id,
        "expectedVersion": value.expected_version,
    }
    requirement_key = getattr(value, "requirement_key", None)
    if requirement_key is not None:
        return {"requirementKey": requirement_key, **result}
    return result


def _handover_content_payload(request: HandoverContentRequest) -> dict[str, Any]:
    return {
        "expectedProjectVersion": request.expected_project_version,
        "policy": _policy_reference_payload(request.policy),
        "slotAssignments": [
            {
                "slotKey": value.slot_key,
                "memberGlobalId": value.member_global_id,
                "memberExpectedVersion": value.member_expected_version,
                "roleAssignmentGlobalId": value.role_assignment_global_id,
                "roleExpectedVersion": value.role_expected_version,
            }
            for value in request.slot_assignments
        ],
        "manifestSources": [
            _source_selection_payload(value) for value in request.manifest_sources
        ],
        "reason": request.reason,
    }


def _handover_reference_payload(reference: object | None) -> object:
    if reference is None:
        return None
    return {
        "handoverGlobalId": reference.handover_global_id,
        "handoverVersion": reference.handover_version,
        "handoverRevisionGlobalId": reference.handover_revision_global_id,
        "handoverSnapshotHash": reference.handover_snapshot_hash,
    }


def _observation_create_payload(request: CreateObservationRequest) -> dict[str, Any]:
    return {
        "expectedProjectVersion": request.expected_project_version,
        "policy": _policy_reference_payload(request.policy),
        "handover": _handover_reference_payload(request.handover),
        "contextSources": [
            _source_selection_payload(value) for value in request.context_sources
        ],
        "retrospectiveSources": [
            _source_selection_payload(value)
            for value in request.retrospective_sources
        ],
        "retrospectiveNote": request.retrospective_note,
        "reason": request.reason,
    }


def _observation_revision_payload(
    request: ObservationRevisionRequest,
) -> dict[str, Any]:
    return {
        "expectedRevisionGlobalId": request.expected_revision_global_id,
        "expectedSnapshotHash": request.expected_snapshot_hash,
        "contextSources": [
            _source_selection_payload(value) for value in request.context_sources
        ],
        "retrospectiveSources": [
            _source_selection_payload(value)
            for value in request.retrospective_sources
        ],
        "retrospectiveNote": request.retrospective_note,
        "reason": request.reason,
    }


def _receipt_key(
    *,
    tenant_id: str,
    project_id: UUID | None,
    actor: str,
    operation: str,
    idempotency_key_hash: str,
) -> str:
    return _payload_hash(
        {
            "tenantId": tenant_id,
            "projectGlobalId": str(project_id) if project_id else None,
            "actorUserId": actor.casefold(),
            "operation": operation,
            "idempotencyKeyHash": idempotency_key_hash,
        }
    )


def _policy_code_key_hash(tenant_id: str, policy_code: str) -> str:
    return hashlib.sha256(
        f"{tenant_id}:{policy_code.casefold()}".encode("utf-8")
    ).hexdigest()


def _payload_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            _json_value(value),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return [_json_value(item) for item in value]
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return getattr(value, "value", value)


def _json_object(value: object) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, Mapping):
        raise RuntimeError("Persisted production transition JSON object is invalid.")
    return dict(value)


def _optional_doc(
    doctype: str,
    name: str,
    *,
    for_update: bool = False,
):
    try:
        return frappe.get_doc(doctype, name, for_update=for_update)
    except frappe.DoesNotExistError:
        return None


def _locked_optional_doc(doctype: str, name: str):
    return _optional_doc(doctype, name, for_update=True)


def _single_document(
    doctype: str,
    filters: Mapping[str, Any],
    *,
    for_update: bool,
):
    names = frappe.get_all(
        doctype,
        filters=dict(filters),
        pluck="name",
        order_by="name asc",
        limit_page_length=2,
    )
    if len(names) != 1:
        return None
    return frappe.get_doc(doctype, str(names[0]), for_update=for_update)


def _lock_released_file_dependencies(
    context: SourceResolutionContext,
    revision,
    *,
    for_update: bool,
) -> bool:
    document_id = str(_value(revision, "document_global_id"))
    if not document_id:
        return False
    names = frappe.get_all(
        "NPI Document Revision File",
        filters={
            "tenant_id": context.tenant_id,
            "project_global_id": str(context.project_global_id),
            "document_global_id": document_id,
            "document_revision_global_id": str(_value(revision, "global_id")),
        },
        pluck="name",
        order_by="global_id asc",
        limit_page_length=_MAX_RELEASE_SOURCE_FILES + 1,
    )
    if not names or len(names) > _MAX_RELEASE_SOURCE_FILES:
        return False
    for name in names:
        association = frappe.get_doc(
            "NPI Document Revision File",
            str(name),
            for_update=for_update,
        )
        try:
            file_revision_id = UUID(
                str(_value(association, "file_revision_global_id"))
            )
        except (TypeError, ValueError):
            return False
        file_revision = _source_document(
            "NPI File Revision",
            context,
            file_revision_id,
            for_update=for_update,
        )
        if (
            file_revision is None
            or str(_value(association, "document_global_id")) != document_id
            or str(_value(association, "document_revision_global_id"))
            != str(_value(revision, "global_id"))
            or not _locked_live_private_file_identity(
                file_revision,
                for_update=for_update,
            )
        ):
            return False
    return True


def _locked_live_private_file_identity(
    file_revision,
    *,
    for_update: bool,
) -> bool:
    from npi_core.npi_core.doctype.npi_file_revision.npi_file_revision import (
        has_complete_file_revision_identity,
    )

    if not has_complete_file_revision_identity(file_revision):
        return False
    file_id = str(_value(file_revision, "frappe_file_id"))
    try:
        live_file = frappe.get_doc("File", file_id, for_update=for_update)
        live_size = _value(live_file, "file_size")
        return bool(
            str(_value(live_file, "name")) == file_id
            and int(_value(live_file, "is_private") or 0) == 1
            and int(_value(live_file, "is_remote_file") or 0) == 0
            and str(_value(live_file, "file_url"))
            == str(_value(file_revision, "file"))
            and str(_value(live_file, "file_url")).startswith("/private/files/")
            and str(_value(live_file, "file_name"))
            == str(_value(file_revision, "file_name"))
            and live_size is not None
            and int(live_size) == int(_value(file_revision, "size_bytes"))
            and str(_value(live_file, "content_hash") or "").lower()
            == str(_value(file_revision, "frappe_content_hash"))
        )
    except (
        AttributeError,
        TypeError,
        ValueError,
        frappe.DoesNotExistError,
        frappe.PermissionError,
    ):
        return False


def _source_document(
    doctype: str,
    context: SourceResolutionContext,
    global_id: UUID,
    *,
    for_update: bool,
):
    document = _optional_doc(doctype, str(global_id), for_update=for_update)
    if (
        document is None
        or str(_value(document, "global_id")) != str(global_id)
        or str(_value(document, "tenant_id")) != context.tenant_id
        or str(_value(document, "project_global_id"))
        != str(context.project_global_id)
    ):
        return None
    return document


def _value(record: object, fieldname: str) -> object:
    if isinstance(record, Mapping):
        return record.get(fieldname)
    getter = getattr(record, "get", None)
    if callable(getter):
        return getter(fieldname)
    return getattr(record, fieldname, None)


def _enabled_system_user(user_id: str, *, for_update: bool = False) -> bool:
    value = frappe.db.get_value(
        "User",
        user_id,
        ["enabled", "user_type"],
        as_dict=True,
        for_update=for_update,
    )
    return bool(
        value
        and int(_value(value, "enabled") or 0) == 1
        and str(_value(value, "user_type")) == "System User"
    )


def _member_effective(member, today: date) -> bool:
    starts = _date_value(member.effective_from)
    ends = _date_value(member.effective_to) if member.effective_to else None
    return starts <= today and (ends is None or today <= ends)


def _date_value(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _utc_datetime_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _database_datetime(value: datetime) -> str:
    return value.astimezone(UTC).replace(tzinfo=None).isoformat(
        sep=" ",
        timespec="microseconds",
    )


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


def _require_exact_snapshot(actual: str, expected: str) -> None:
    if actual != expected:
        raise ProductionTransitionVersionConflict()


def _exact_one(values, error: str):
    matches = list(values)
    if len(matches) > 1:
        raise RuntimeError(error)
    return matches[0] if matches else None


def _unique_version_map(values, version, error: str):
    result = {}
    for value in values:
        key = version(value)
        if key in result:
            raise RuntimeError(error)
        result[key] = value
    if set(result) != set(range(1, len(values) + 1)):
        raise RuntimeError(error)
    return result
