from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

import frappe
from frappe import _

from npi_core.foundation.audit import create_audit_event
from npi_core.foundation.errors import (
    CursorSigningUnavailable,
    NpiProblem,
    PermissionDenied,
    RequestValidationFailed,
    VersionConflict,
)
from npi_core.foundation.security import Principal
from npi_core.project.frappe_validation import canonical_json, sha256_json
from npi_core.npi_core.doctype.npi_file_revision.npi_file_revision import (
    file_revision_source_snapshot,
    has_live_private_file_identity,
)
from npi_core.project_controls.domain import (
    FrozenProjectControlAuthority,
    HealthAggregationMode,
    HealthAggregationRule,
    HealthDimension,
    HealthDimensionRule,
    HealthMeasurement,
    HealthRuleMode,
    HealthStatus,
    PrerequisiteStatus,
    PriorPolicyVersionReference,
    ProjectControlAction,
    ProjectControlBinding,
    ProjectControlPolicySnapshot,
    ProjectLifecycleState,
    ProjectPrerequisiteKey,
    ProjectTransitionRule,
    evaluate_project_health,
    evaluate_project_transition,
)
from npi_core.project_controls.terminal_guard import require_mutable_project


_MAX_BINDING_POLICY_OPTIONS = 500
_MAX_BINDING_MEMBER_OPTIONS = 500
_MAX_COMMENT_OPTION_CANDIDATES = 500
_COMMAND_TRANSPORT_ROLE = "NPI API User"
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_PROJECT_ACTIVITY_CURSOR_VERSION = 1
_PROJECT_ACTIVITY_CURSOR_KEY_CONTEXT = (
    b"npi-one:project-controls:activity-cursor:v1"
)
_LEARNING_FIELDS = (
    "global_id",
    "kind",
    "title",
    "content",
    "recommendation",
    "tags",
    "template_global_id",
    "template_version",
    "template_snapshot_hash",
    "created_by",
    "created_at",
    "optimistic_version",
    "project_global_id",
    "tenant_id",
    "request_id",
    "trace_id",
    "record_snapshot",
    "snapshot_hash",
)


@dataclass(frozen=True, slots=True)
class ProjectControlCommandOutcome:
    response: dict[str, Any]
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class _ProjectActivityCursor:
    occurred_at: datetime
    global_id: str
    as_of: datetime
    query_fingerprint: str


class ProjectControlPolicyUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "PROJECT_CONTROL_POLICY_UNAVAILABLE",
            _("A current published Project Control Policy binding is required."),
        )


class FrappeProjectControlsRepository:
    """Frappe adapter for bounded Project control and internal activity flows."""

    def __init__(
        self,
        *,
        principal: Principal,
        request_id: str,
        trace_id: str,
    ) -> None:
        self.principal = principal
        self.actor = (
            principal.user_id.casefold()
            if "@" in principal.user_id
            else principal.user_id
        )
        self.request_id = request_id
        self.trace_id = trace_id

    def controls(self, project_id: UUID) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        return self._controls_response(project)

    def bind_policy(
        self,
        project_id: UUID,
        *,
        idempotency_key: str,
        expected_project_version: int,
        policy_ref: object,
        bindings: Sequence[object],
    ) -> ProjectControlCommandOutcome | None:
        project = self._locked_authorized_project(project_id, administer=True)
        if project is None:
            return None
        binding_values = _input_sequence(
            bindings,
            "bindings",
            maximum=64,
            message=_("Enter valid Project control authority bindings."),
        )
        payload = {
            "projectId": str(project_id),
            "expectedProjectVersion": expected_project_version,
            "policyRef": policy_ref,
            "bindings": binding_values,
        }
        payload_hash = _payload_hash(payload)
        replay = self._idempotency_replay(idempotency_key, payload_hash)
        if replay is not None:
            return ProjectControlCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        _require_project_version(project, expected_project_version)
        policy, policy_payload = self._load_policy(policy_ref)
        authorities, persisted_bindings = self._resolve_authorities(
            project,
            policy,
            binding_values,
        )
        binding_version = int(project.control_binding_version or 0) + 1
        binding_global_id = uuid4()
        binding = ProjectControlBinding.freeze(
            global_id=binding_global_id,
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            policy=policy,
            authorities=authorities,
        )
        project_version = int(project.optimistic_version) + 1
        bound_at = datetime.now(UTC)
        binding_snapshot = {
            "schemaVersion": 1,
            "globalId": str(binding_global_id),
            "tenantId": str(project.tenant_id),
            "projectGlobalId": str(project_id),
            "bindingVersion": binding_version,
            "policyRef": {
                "globalId": str(policy.policy_global_id),
                "version": policy.policy_version,
                "snapshotHash": policy.snapshot_hash,
            },
            "policySnapshotHash": policy.snapshot_hash,
            "authorityBindings": persisted_bindings,
            "boundBy": self.actor,
            "boundAt": _datetime_iso(bound_at),
            "projectVersion": project_version,
            "requestId": self.request_id,
            "traceId": self.trace_id,
        }
        with _controlled_project_control_write_scope():
            idempotency = self._insert_idempotency(
                idempotency_key,
                payload_hash,
                project,
                "project.control_policy.bind",
            )
            if isinstance(idempotency, dict):
                return ProjectControlCommandOutcome(idempotency, replayed=True)
            frappe.get_doc(
                {
                    "doctype": "NPI Project Control Binding",
                    "global_id": str(binding_global_id),
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project_id),
                    "binding_version": binding_version,
                    "policy_global_id": str(policy.policy_global_id),
                    "policy_version": policy.policy_version,
                    "policy_snapshot_hash": policy.snapshot_hash,
                    "policy_snapshot": canonical_json(policy_payload),
                    "authority_bindings": canonical_json(persisted_bindings),
                    "bound_by": self.actor,
                    "bound_at": _database_datetime(bound_at),
                    "project_version": project_version,
                    "request_id": self.request_id,
                    "trace_id": self.trace_id,
                    "binding_snapshot": canonical_json(binding_snapshot),
                    "snapshot_hash": sha256_json(binding_snapshot),
                }
            ).insert()
            project.control_binding_global_id = str(binding.global_id)
            project.control_policy_global_id = str(policy.policy_global_id)
            project.control_policy_version = policy.policy_version
            project.control_policy_snapshot_hash = policy.snapshot_hash
            project.control_binding_version = binding_version
            project.current_health_assessment_global_id = None
            project.current_health_status = "unassessed"
            project.current_health_snapshot = None
            project.current_health_at = None
            project.optimistic_version = project_version
            project.save()
            self._append_audit(
                operation="project.control_policy.bind",
                global_id=project_id,
                object_version=project_version,
                result="updated",
                summary={
                    "bindingGlobalId": str(binding_global_id),
                    "bindingVersion": binding_version,
                    "policyGlobalId": str(policy.policy_global_id),
                    "policyVersion": policy.policy_version,
                    "requestId": self.request_id,
                },
            )
            response = self._controls_response(project)
            self._seal_idempotency(idempotency, response)
        return ProjectControlCommandOutcome(response)

    def assess_health(
        self,
        project_id: UUID,
        *,
        idempotency_key: str,
        expected_project_version: int,
        measurements: Sequence[object],
        reason: object,
        recovery_plan: object,
    ) -> ProjectControlCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        measurement_values = _input_sequence(
            measurements,
            "measurements",
            maximum=4,
            message=_("Enter each health measurement at most once."),
        )
        payload = {
            "projectId": str(project_id),
            "expectedProjectVersion": expected_project_version,
            "measurements": measurement_values,
            "reason": reason,
            "recoveryPlan": recovery_plan,
        }
        payload_hash = _payload_hash(payload)
        replay = self._idempotency_replay(idempotency_key, payload_hash)
        if replay is not None:
            return ProjectControlCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        _require_project_version(project, expected_project_version)
        policy, _policy_payload = self._current_policy(project)
        binding, persisted_bindings = self._current_binding(project, policy)
        actor = self._actor_authority(
            project,
            binding,
            persisted_bindings,
            slot=policy.health_assessment_slot,
        )
        parsed_measurements = _health_measurements(measurement_values)
        evaluation = evaluate_project_health(
            policy=policy,
            binding=binding,
            actor_member_global_id=UUID(actor["memberGlobalId"]),
            actor_user_id=self.actor,
            measurements=parsed_measurements,
            reason=_optional_text(reason, "reason", 2000),
            recovery_plan=_optional_text(
                recovery_plan,
                "recoveryPlan",
                4000,
            ),
        )
        assessed_at = datetime.now(UTC)
        assessment_global_id = uuid4()
        project_version = int(project.optimistic_version) + 1
        assessment_snapshot = {
            "schemaVersion": 1,
            "globalId": str(assessment_global_id),
            "tenantId": str(project.tenant_id),
            "projectGlobalId": str(project_id),
            "bindingGlobalId": str(binding.global_id),
            "policyRef": {
                "globalId": str(policy.policy_global_id),
                "version": policy.policy_version,
                "snapshotHash": policy.snapshot_hash,
            },
            "actor": actor,
            "assessedAt": _datetime_iso(assessed_at),
            "projectVersion": project_version,
            "measurements": [value.canonical_dict() for value in parsed_measurements],
            "evaluation": evaluation.canonical_dict(),
            "requestId": self.request_id,
            "traceId": self.trace_id,
        }
        with _controlled_project_control_write_scope():
            idempotency = self._insert_idempotency(
                idempotency_key,
                payload_hash,
                project,
                "project.health.assess",
            )
            if isinstance(idempotency, dict):
                return ProjectControlCommandOutcome(idempotency, replayed=True)
            frappe.get_doc(
                {
                    "doctype": "NPI Project Health Assessment",
                    "global_id": str(assessment_global_id),
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project_id),
                    "binding_global_id": str(binding.global_id),
                    "policy_global_id": str(policy.policy_global_id),
                    "policy_version": policy.policy_version,
                    "policy_snapshot_hash": policy.snapshot_hash,
                    "actor_authority_slot": actor["slot"],
                    "actor_member_global_id": actor["memberGlobalId"],
                    "actor_user_id": actor["userId"],
                    "actor_display_name": actor["displayName"],
                    "assessed_at": _database_datetime(assessed_at),
                    "project_version": project_version,
                    "request_id": self.request_id,
                    "trace_id": self.trace_id,
                    "assessment_snapshot": canonical_json(assessment_snapshot),
                    "snapshot_hash": sha256_json(assessment_snapshot),
                }
            ).insert()
            project.current_health_assessment_global_id = str(assessment_global_id)
            project.current_health_status = evaluation.overall_status.value
            project.current_health_snapshot = canonical_json(assessment_snapshot)
            project.current_health_at = _database_datetime(assessed_at)
            project.optimistic_version = project_version
            project.save()
            self._append_activity(
                project,
                event_type="health_assessed",
                detail={
                    "assessment": evaluation.canonical_dict(),
                    "policyRef": {
                        "globalId": str(policy.policy_global_id),
                        "version": policy.policy_version,
                        "snapshotHash": policy.snapshot_hash,
                    },
                    "bindingGlobalId": str(binding.global_id),
                    "projectVersion": project_version,
                },
                occurred_at=assessed_at,
            )
            self._append_audit(
                operation="project.health.assess",
                global_id=assessment_global_id,
                object_version=1,
                result="created",
                summary={
                    "overallStatus": evaluation.overall_status.value,
                    "projectId": str(project_id),
                    "projectVersion": project_version,
                    "requestId": self.request_id,
                    "resultHash": evaluation.result_hash,
                },
            )
            response = self._controls_response(project)
            self._seal_idempotency(idempotency, response)
        return ProjectControlCommandOutcome(response)

    def transition(
        self,
        project_id: UUID,
        *,
        idempotency_key: str,
        expected_project_version: int,
        action: object,
        reason: object,
    ) -> ProjectControlCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "projectId": str(project_id),
            "expectedProjectVersion": expected_project_version,
            "action": action,
            "reason": reason,
        }
        payload_hash = _payload_hash(payload)
        replay = self._idempotency_replay(idempotency_key, payload_hash)
        if replay is not None:
            return ProjectControlCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        _require_project_version(project, expected_project_version)
        selected_action = _enum_value(
            ProjectControlAction,
            action,
            "action",
        )
        policy, _policy_payload = self._current_policy(project)
        binding, persisted_bindings = self._current_binding(project, policy)
        actor = self._actor_authority_for_transition(
            project,
            policy,
            binding,
            persisted_bindings,
            selected_action,
        )
        current_state = ProjectLifecycleState(str(project.lifecycle_state))
        rule = policy.transition(current_state, selected_action)
        prerequisite_states = self._resolve_prerequisites(
            project,
            rule.prerequisites,
        )
        decision = evaluate_project_transition(
            policy=policy,
            binding=binding,
            current_state=current_state,
            action=selected_action,
            actor_member_global_id=UUID(actor["memberGlobalId"]),
            actor_user_id=self.actor,
            prerequisite_states=prerequisite_states,
            reason=_required_text(reason, "reason", 2000),
            current_project_version=int(project.optimistic_version),
            expected_project_version=expected_project_version,
        )
        changed_at = datetime.now(UTC)
        prerequisites = [
            {"key": key.value, "status": prerequisite_states[key].value}
            for key in sorted(prerequisite_states, key=lambda value: value.value)
        ]
        with _controlled_project_control_write_scope():
            idempotency = self._insert_idempotency(
                idempotency_key,
                payload_hash,
                project,
                f"project.lifecycle.{selected_action.value}",
            )
            if isinstance(idempotency, dict):
                return ProjectControlCommandOutcome(idempotency, replayed=True)
            project.lifecycle_state = decision.target_state.value
            project.optimistic_version = decision.project_version_after
            project.save()
            self._append_activity(
                project,
                event_type="lifecycle_transition",
                detail={
                    "action": decision.action.value,
                    "fromState": decision.source_state.value,
                    "toState": decision.target_state.value,
                    "reason": decision.reason,
                    "approvedBy": actor,
                    "policyRef": {
                        "globalId": str(policy.policy_global_id),
                        "version": policy.policy_version,
                        "snapshotHash": policy.snapshot_hash,
                    },
                    "bindingGlobalId": str(binding.global_id),
                    "prerequisites": prerequisites,
                    "projectVersion": decision.project_version_after,
                },
                occurred_at=changed_at,
            )
            self._append_audit(
                operation=f"project.lifecycle.{selected_action.value}",
                global_id=project_id,
                object_version=decision.project_version_after,
                result="updated",
                summary={
                    "decisionHash": decision.decision_hash,
                    "fromState": decision.source_state.value,
                    "requestId": self.request_id,
                    "toState": decision.target_state.value,
                },
            )
            response = self._controls_response(project)
            self._seal_idempotency(idempotency, response)
        return ProjectControlCommandOutcome(response)

    def activity(
        self,
        project_id: UUID,
        *,
        cursor: str | None,
        limit: int,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        page_size = _bounded_limit(limit)
        signing_key = _project_activity_cursor_signing_key()
        query_fingerprint = _project_activity_query_fingerprint(
            tenant_id=str(project.tenant_id),
            actor_user_id=self.actor,
            project_id=project_id,
        )
        cursor_value = (
            _decode_project_activity_cursor(
                cursor,
                expected_query_fingerprint=query_fingerprint,
                signing_key=signing_key,
            )
            if cursor is not None
            else None
        )
        as_of = (
            cursor_value.as_of
            if cursor_value is not None
            else datetime.now(UTC)
        )
        documents = _query_project_activity_page(
            tenant_id=str(project.tenant_id),
            project_id=project_id,
            as_of=as_of,
            cursor=(
                (cursor_value.occurred_at, cursor_value.global_id)
                if cursor_value is not None
                else None
            ),
            limit=page_size + 1,
        )
        has_more = len(documents) > page_size
        page = documents[:page_size]
        next_cursor = (
            _encode_project_activity_cursor(
                _activity_sort_key(page[-1]),
                as_of=as_of,
                query_fingerprint=query_fingerprint,
                signing_key=signing_key,
            )
            if has_more and page
            else None
        )
        follower = self._follower_document(project, lock=False)
        return {
            "projectId": str(project_id),
            "items": [
                _activity_response(document, project_id) for document in page
            ],
            "nextCursor": next_cursor,
            "permissions": {
                "canComment": self._has_command_transport(),
                "canFollow": self._has_command_transport(),
            },
            "commentOptions": self._comment_options(project),
            "following": bool(follower is not None and int(follower.active or 0) == 1),
            "followerVersion": (
                int(follower.optimistic_version) if follower is not None else 0
            ),
        }

    def add_comment(
        self,
        project_id: UUID,
        *,
        idempotency_key: str,
        body: object,
        mentions: Sequence[object],
        attachments: Sequence[object],
        object_links: Sequence[object],
    ) -> ProjectControlCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        mention_values = _input_sequence(
            mentions,
            "mentions",
            maximum=50,
            message=_("Enter valid Project member mentions."),
        )
        attachment_values = _input_sequence(
            attachments,
            "attachments",
            maximum=20,
            message=_("Enter valid controlled file revision references."),
        )
        object_link_values = _input_sequence(
            object_links,
            "objectLinks",
            maximum=20,
            message=_("Enter valid Project object links."),
        )
        payload = {
            "projectId": str(project_id),
            "body": body,
            "mentions": mention_values,
            "attachments": attachment_values,
            "objectLinks": object_link_values,
        }
        payload_hash = _payload_hash(payload)
        replay = self._idempotency_replay(idempotency_key, payload_hash)
        if replay is not None:
            return ProjectControlCommandOutcome(replay, replayed=True)
        detail = {
            "body": _required_text(body, "body", 4000),
            "mentions": self._resolve_mentions(project, mention_values),
            "attachments": self._resolve_attachments(
                project,
                attachment_values,
            ),
            "objectLinks": self._resolve_object_links(
                project,
                object_link_values,
            ),
        }
        with _controlled_project_control_write_scope():
            idempotency = self._insert_idempotency(
                idempotency_key,
                payload_hash,
                project,
                "project.comment.add",
            )
            if isinstance(idempotency, dict):
                return ProjectControlCommandOutcome(idempotency, replayed=True)
            event = self._append_activity(
                project,
                event_type="comment_added",
                detail=detail,
            )
            self._append_audit(
                operation="project.comment.add",
                global_id=UUID(event["globalId"]),
                object_version=1,
                result="created",
                summary={
                    "attachmentCount": len(detail["attachments"]),
                    "mentionCount": len(detail["mentions"]),
                    "objectLinkCount": len(detail["objectLinks"]),
                    "projectId": str(project_id),
                    "requestId": self.request_id,
                },
            )
            response = _activity_payload_response(event, project_id)
            self._seal_idempotency(idempotency, response)
        return ProjectControlCommandOutcome(response)

    def set_following(
        self,
        project_id: UUID,
        *,
        idempotency_key: str,
        expected_version: int,
        active: bool,
    ) -> ProjectControlCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        if type(expected_version) is not int or expected_version < 0:
            raise _field_problem(
                "expectedVersion",
                _("Enter a non-negative expected version."),
            )
        if type(active) is not bool:
            raise _field_problem(
                "active",
                _("Select a valid follow state."),
            )
        payload = {
            "projectId": str(project_id),
            "expectedVersion": expected_version,
            "active": active,
        }
        payload_hash = _payload_hash(payload)
        replay = self._idempotency_replay(idempotency_key, payload_hash)
        if replay is not None:
            return ProjectControlCommandOutcome(replay, replayed=True)
        follower = self._follower_document(project, lock=True)
        current_version = (
            int(follower.optimistic_version) if follower is not None else 0
        )
        if current_version != expected_version:
            raise VersionConflict()
        if (follower is None and active is False) or (
            follower is not None and bool(follower.active) is active
        ):
            raise _field_problem(
                "active",
                _("The Project follow state is already selected."),
            )
        changed_at = datetime.now(UTC)
        next_version = current_version + 1
        with _controlled_project_control_write_scope():
            idempotency = self._insert_idempotency(
                idempotency_key,
                payload_hash,
                project,
                "project.follow" if active else "project.unfollow",
            )
            if isinstance(idempotency, dict):
                return ProjectControlCommandOutcome(idempotency, replayed=True)
            if follower is None:
                follower = frappe.get_doc(
                    {
                        "doctype": "NPI Project Follower",
                        "global_id": str(uuid4()),
                        "follower_key": f"{project_id}:{self.actor}",
                        "tenant_id": str(project.tenant_id),
                        "project_global_id": str(project_id),
                        "user_id": self.actor,
                        "active": int(active),
                        "optimistic_version": 1,
                        "last_changed_by": self.actor,
                        "last_changed_at": _database_datetime(changed_at),
                        "request_id": self.request_id,
                        "trace_id": self.trace_id,
                    }
                ).insert()
            else:
                follower.active = int(active)
                follower.optimistic_version = next_version
                follower.last_changed_by = self.actor
                follower.last_changed_at = _database_datetime(changed_at)
                follower.request_id = self.request_id
                follower.trace_id = self.trace_id
                follower.save()
            self._append_activity(
                project,
                event_type="followed" if active else "unfollowed",
                detail={"active": active},
                occurred_at=changed_at,
            )
            self._append_audit(
                operation="project.follow" if active else "project.unfollow",
                global_id=UUID(str(follower.global_id)),
                object_version=next_version,
                result="updated",
                summary={
                    "active": active,
                    "projectId": str(project_id),
                    "requestId": self.request_id,
                },
            )
            response = {
                "projectId": str(project_id),
                "following": active,
                "version": next_version,
                "changedAt": _datetime_iso(changed_at),
            }
            self._seal_idempotency(idempotency, response)
        return ProjectControlCommandOutcome(response)

    def project_learning(
        self,
        project_id: UUID,
        *,
        kind: object | None,
        search: object | None,
        learning_id: object | None,
        limit: int,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        if learning_id is not None:
            if kind is not None or search is not None:
                raise _field_problem(
                    "learningId",
                    _(
                        "Select an exact learning record without additional filters."
                    ),
                )
            exact_learning_id = _uuid_value(learning_id, "learningId")
            documents = frappe.get_all(
                "NPI Project Learning",
                filters=[
                    ["tenant_id", "=", str(project.tenant_id)],
                    ["project_global_id", "=", str(project_id)],
                    ["global_id", "=", str(exact_learning_id)],
                ],
                fields=_LEARNING_FIELDS,
                order_by="created_at desc, global_id desc",
                limit_page_length=2,
            )
            if not documents:
                return None
            if len(documents) != 1:
                raise ValueError(
                    "Persisted Project learning identity is ambiguous."
                )
            return {
                "projectId": str(project_id),
                "items": [_learning_response(documents[0])],
                "permissions": {
                    "canCreate": self._has_command_transport(),
                },
            }
        filters: list[list[object]] = [
            ["tenant_id", "=", str(project.tenant_id)],
            ["project_global_id", "=", str(project_id)],
        ]
        if kind is not None:
            filters.append(["kind", "=", _learning_kind(kind, "kind")])
        search_value = _optional_search(search)
        documents = frappe.get_all(
            "NPI Project Learning",
            filters=filters,
            or_filters=(
                [
                    ["title", "like", f"%{search_value}%"],
                    ["content", "like", f"%{search_value}%"],
                    ["recommendation", "like", f"%{search_value}%"],
                ]
                if search_value is not None
                else None
            ),
            fields=_LEARNING_FIELDS,
            order_by="created_at desc, global_id desc",
            limit_page_length=_bounded_limit(limit),
        )
        return {
            "projectId": str(project_id),
            "items": [_learning_response(value) for value in documents],
            "permissions": {
                "canCreate": self._has_command_transport(),
            },
        }

    def create_learning(
        self,
        project_id: UUID,
        *,
        idempotency_key: str,
        kind: object,
        title: object,
        content: object,
        recommendation: object,
        tags: Sequence[object],
    ) -> ProjectControlCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        tag_values = _input_sequence(
            tags,
            "tags",
            maximum=20,
            message=_("Enter valid Project learning tags."),
        )
        payload = {
            "projectId": str(project_id),
            "kind": kind,
            "title": title,
            "content": content,
            "recommendation": recommendation,
            "tags": tag_values,
        }
        payload_hash = _payload_hash(payload)
        replay = self._idempotency_replay(idempotency_key, payload_hash)
        if replay is not None:
            return ProjectControlCommandOutcome(replay, replayed=True)
        learning_kind = _learning_kind(kind, "kind")
        learning_title = _required_text(title, "title", 280)
        learning_content = _required_text(content, "content", 4000)
        learning_recommendation = (
            _optional_text(recommendation, "recommendation", 4000) or ""
        )
        learning_tags = _learning_tags(tag_values)
        learning_global_id = uuid4()
        created_at = datetime.now(UTC)
        snapshot = {
            "schemaVersion": 1,
            "globalId": str(learning_global_id),
            "tenantId": str(project.tenant_id),
            "projectGlobalId": str(project_id),
            "kind": learning_kind,
            "title": learning_title,
            "content": learning_content,
            "recommendation": learning_recommendation,
            "tags": learning_tags,
            "templateGlobalId": str(UUID(str(project.template_global_id))),
            "templateVersion": int(project.template_version),
            "templateSnapshotHash": str(project.template_snapshot_hash),
            "createdBy": self.actor,
            "createdAt": _datetime_iso(created_at),
            "requestId": self.request_id,
            "traceId": self.trace_id,
        }
        with _controlled_project_control_write_scope():
            idempotency = self._insert_idempotency(
                idempotency_key,
                payload_hash,
                project,
                "project.learning.create",
            )
            if isinstance(idempotency, dict):
                return ProjectControlCommandOutcome(idempotency, replayed=True)
            document = frappe.get_doc(
                {
                    "doctype": "NPI Project Learning",
                    "global_id": str(learning_global_id),
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project_id),
                    "kind": learning_kind,
                    "title": learning_title,
                    "content": learning_content,
                    "recommendation": learning_recommendation,
                    "tags": canonical_json(learning_tags),
                    "template_global_id": str(project.template_global_id),
                    "template_version": int(project.template_version),
                    "template_snapshot_hash": str(project.template_snapshot_hash),
                    "created_by": self.actor,
                    "created_at": _database_datetime(created_at),
                    "optimistic_version": 1,
                    "request_id": self.request_id,
                    "trace_id": self.trace_id,
                    "record_snapshot": canonical_json(snapshot),
                    "snapshot_hash": sha256_json(snapshot),
                }
            ).insert()
            self._append_activity(
                project,
                event_type="learning_created",
                detail={
                    "learningGlobalId": str(learning_global_id),
                    "kind": learning_kind,
                    "title": learning_title,
                },
                occurred_at=created_at,
            )
            self._append_audit(
                operation="project.learning.create",
                global_id=learning_global_id,
                object_version=1,
                result="created",
                summary={
                    "kind": learning_kind,
                    "projectId": str(project_id),
                    "requestId": self.request_id,
                    "tagCount": len(learning_tags),
                },
            )
            response = _learning_response(document)
            self._seal_idempotency(idempotency, response)
        return ProjectControlCommandOutcome(response)

    def search_learning(
        self,
        *,
        kind: object | None,
        tag: object | None,
        search: object | None,
        project_id: UUID | None,
        template_global_id: object | None,
        template_version: object | None,
        limit: int,
    ) -> dict[str, Any] | None:
        if self.principal.is_external:
            raise PermissionDenied()
        if project_id is not None:
            project = self._authorized_project(project_id)
            if project is None:
                return None
            accessible = {str(project_id)}
        else:
            accessible = self._accessible_project_ids()
        kind_value = _learning_kind(kind, "kind") if kind is not None else None
        tag_value = _optional_tag(tag)
        search_value = _optional_search(search)
        page_size = _bounded_limit(limit)
        template_id = (
            None
            if template_global_id is None
            else _uuid_value(template_global_id, "templateGlobalId")
        )
        template_version_value = (
            None
            if template_version is None
            else _query_positive_integer(template_version, "templateVersion")
        )
        if (template_id is None) is not (template_version_value is None):
            raise _field_problem(
                "templateGlobalId",
                _("Select an exact Project Template version."),
            )
        if not accessible:
            return {"items": []}
        filters: list[list[object]] = [
            ["tenant_id", "=", str(self.principal.tenant_id)],
            ["project_global_id", "in", sorted(accessible)],
        ]
        if kind_value is not None:
            filters.append(["kind", "=", kind_value])
        if template_id is not None:
            filters.append(["template_global_id", "=", str(template_id)])
        if template_version_value is not None:
            filters.append(["template_version", "=", template_version_value])
        documents = frappe.get_all(
            "NPI Project Learning",
            filters=filters,
            or_filters=(
                [
                    ["title", "like", f"%{search_value}%"],
                    ["content", "like", f"%{search_value}%"],
                    ["recommendation", "like", f"%{search_value}%"],
                ]
                if search_value is not None
                else None
            ),
            fields=_LEARNING_FIELDS,
            order_by="created_at desc, global_id desc",
            limit_page_length=10001 if tag_value is not None else page_size,
        )
        if len(documents) > 10000:
            raise NpiProblem(
                422,
                "PROJECT_SCOPE_TOO_LARGE",
                _("Narrow the Project learning search."),
            )
        items = [
            _learning_response(value)
            for value in documents
            if tag_value is None or tag_value in _json_string_array(value.tags)
        ][:page_size]
        return {"items": items}

    def _resolve_mentions(
        self,
        project,
        values: Sequence[object],
    ) -> list[dict[str, str]]:
        if (
            not isinstance(values, Sequence)
            or isinstance(values, (str, bytes))
            or len(values) > 50
        ):
            raise _field_problem(
                "mentions",
                _("Enter valid Project member mentions."),
            )
        result: list[dict[str, str]] = []
        seen: set[str] = set()
        for index, value in enumerate(values):
            if not isinstance(value, Mapping) or set(value) != {"memberGlobalId"}:
                raise _field_problem(
                    f"mentions[{index}]",
                    _("Select a valid Project member."),
                )
            member_id = _uuid_value(
                value["memberGlobalId"],
                f"mentions[{index}].memberGlobalId",
            )
            if str(member_id) in seen:
                raise _field_problem(
                    f"mentions[{index}].memberGlobalId",
                    _("Mention each Project member once."),
                )
            member = self._active_internal_member(project, member_id)
            user = _enabled_internal_user(str(member.user_id))
            result.append(
                {
                    "memberGlobalId": str(member_id),
                    "userId": str(member.user_id).casefold(),
                    "displayName": str(user["full_name"]).strip(),
                }
            )
            seen.add(str(member_id))
        return result

    def _resolve_attachments(
        self,
        project,
        values: Sequence[object],
    ) -> list[dict[str, object]]:
        if (
            not isinstance(values, Sequence)
            or isinstance(values, (str, bytes))
            or len(values) > 20
        ):
            raise _field_problem(
                "attachments",
                _("Enter valid controlled file revision references."),
            )
        result: list[dict[str, object]] = []
        seen: set[str] = set()
        for index, value in enumerate(values):
            if not isinstance(value, Mapping) or set(value) != {
                "globalId",
                "version",
            }:
                raise _field_problem(
                    f"attachments[{index}]",
                    _("Select an exact controlled File Revision."),
                )
            global_id = _uuid_value(
                value["globalId"],
                f"attachments[{index}].globalId",
            )
            version = _positive_integer(
                value["version"],
                f"attachments[{index}].version",
            )
            if str(global_id) in seen:
                raise _field_problem(
                    f"attachments[{index}].globalId",
                    _("Attach each File Revision once."),
                )
            document = _optional_doc("NPI File Revision", str(global_id))
            if (
                document is None
                or str(document.tenant_id) != str(project.tenant_id)
                or str(document.project_global_id) != str(project.global_id)
                or int(document.optimistic_version) != version
            ):
                raise _field_problem(
                    f"attachments[{index}]",
                    _("Select an available File Revision from this Project."),
                )
            if not has_live_private_file_identity(document):
                raise _field_problem(
                    f"attachments[{index}]",
                    _("Select a clean private File Revision."),
                )
            snapshot = file_revision_source_snapshot(document)
            if snapshot["scanState"] != "clean" or snapshot["isPrivate"] is not True:
                raise _field_problem(
                    f"attachments[{index}]",
                    _("Select a clean private File Revision."),
                )
            result.append(
                {
                    "globalId": str(global_id),
                    "version": version,
                    "fileName": snapshot["fileName"],
                    "mimeType": snapshot["mimeType"],
                    "sizeBytes": snapshot["sizeBytes"],
                    "sha256": snapshot["sha256"],
                    "scanState": snapshot["scanState"],
                }
            )
            seen.add(str(global_id))
        return result

    def _resolve_object_links(
        self,
        project,
        values: Sequence[object],
    ) -> list[dict[str, object]]:
        if (
            not isinstance(values, Sequence)
            or isinstance(values, (str, bytes))
            or len(values) > 20
        ):
            raise _field_problem(
                "objectLinks",
                _("Enter valid Project object links."),
            )
        result: list[dict[str, object]] = []
        seen: set[tuple[str, str]] = set()
        for index, value in enumerate(values):
            if not isinstance(value, Mapping) or set(value) != {
                "type",
                "globalId",
                "version",
            }:
                raise _field_problem(
                    f"objectLinks[{index}]",
                    _("Select an exact Project object."),
                )
            object_type = value["type"]
            if object_type not in {
                "project",
                "gate",
                "domain_work_item",
                "file_revision",
                "learning",
            }:
                raise _field_problem(
                    f"objectLinks[{index}].type",
                    _("Select a supported Project object type."),
                )
            global_id = _uuid_value(
                value["globalId"],
                f"objectLinks[{index}].globalId",
            )
            version = _positive_integer(
                value["version"],
                f"objectLinks[{index}].version",
            )
            identity = (str(object_type), str(global_id))
            if identity in seen:
                raise _field_problem(
                    f"objectLinks[{index}]",
                    _("Link each Project object once."),
                )
            result.append(
                self._resolve_object_link(
                    project,
                    str(object_type),
                    global_id,
                    version,
                    path=f"objectLinks[{index}]",
                )
            )
            seen.add(identity)
        return result

    def _resolve_object_link(
        self,
        project,
        object_type: str,
        global_id: UUID,
        version: int,
        *,
        path: str,
    ) -> dict[str, object]:
        if object_type == "project":
            document = project
            matches = str(global_id) == str(project.global_id) and version == int(
                project.optimistic_version
            )
            code = str(project.business_code)
            title = str(project.title)
        else:
            doctype = {
                "gate": "NPI Gate Shell",
                "domain_work_item": "NPI Domain Work Item",
                "file_revision": "NPI File Revision",
                "learning": "NPI Project Learning",
            }[object_type]
            document = _optional_doc(doctype, str(global_id))
            matches = bool(
                document is not None
                and str(document.project_global_id) == str(project.global_id)
                and int(document.optimistic_version) == version
                and (
                    object_type == "gate"
                    or str(document.tenant_id) == str(project.tenant_id)
                )
            )
            code = (
                str(document.gate_key)
                if document is not None and object_type == "gate"
                else (
                    str(document.kind)
                    if document is not None
                    and object_type in {"domain_work_item", "learning"}
                    else (
                        f"R{int(document.revision)}"
                        if document is not None and object_type == "file_revision"
                        else ""
                    )
                )
            )
            title = (
                str(document.title)
                if document is not None and object_type != "file_revision"
                else (str(document.file_name) if document is not None else "")
            )
            if document is not None and object_type == "file_revision":
                if not has_live_private_file_identity(document):
                    matches = False
                else:
                    snapshot = file_revision_source_snapshot(document)
                    matches = bool(
                        matches
                        and snapshot["isPrivate"] is True
                        and snapshot["scanState"] == "clean"
                    )
        if not matches:
            raise _field_problem(
                path,
                _("Select an available exact object from this Project."),
            )
        return {
            "type": object_type,
            "globalId": str(global_id),
            "version": version,
            "code": code,
            "title": title,
        }

    def _follower_document(self, project, *, lock: bool):
        name = frappe.db.get_value(
            "NPI Project Follower",
            {
                "follower_key": f"{project.global_id}:{self.actor}",
                "tenant_id": str(project.tenant_id),
            },
            "name",
        )
        if not name:
            return None
        try:
            document = frappe.get_doc(
                "NPI Project Follower",
                str(name),
                for_update=lock,
            )
        except frappe.DoesNotExistError:
            return None
        if (
            str(document.project_global_id) != str(project.global_id)
            or str(document.user_id).casefold() != self.actor.casefold()
        ):
            raise ValueError("Persisted Project follower identity failed.")
        return document

    def _accessible_project_ids(self) -> set[str]:
        if self.principal.is_external or not self.principal.tenant_id:
            return set()
        filters: dict[str, object] = {
            "tenant_id": str(self.principal.tenant_id),
        }
        if not self._is_internal_system_manager():
            filters["owner_user_id"] = self.actor
        projects = frappe.get_all(
            "NPI Engineering Project",
            filters=filters,
            pluck="global_id",
            limit_page_length=10001,
        )
        if len(projects) > 10000:
            raise NpiProblem(
                422,
                "PROJECT_SCOPE_TOO_LARGE",
                _("Narrow the Project learning search."),
            )
        return {str(UUID(str(value))) for value in projects}

    def _controls_response(self, project) -> dict[str, Any]:
        project_id = UUID(str(project.global_id))
        mutable = str(project.lifecycle_state) not in {"cancelled", "completed"}
        can_bind_policy = bool(mutable and self._is_internal_system_manager())
        policy: ProjectControlPolicySnapshot | None = None
        binding: ProjectControlBinding | None = None
        persisted_bindings: list[dict[str, str]] = []
        policy_title: str | None = None
        if project.control_binding_global_id:
            policy, _payload = self._current_policy(project)
            binding, persisted_bindings = self._current_binding(project, policy)
            policy_document = _optional_doc(
                "NPI Project Control Policy Version",
                f"{policy.policy_global_id}:{policy.policy_version}",
            )
            policy_title = (
                str(policy_document.title) if policy_document is not None else None
            )

        dimensions = [
            {
                "dimension": dimension.value,
                "ruleMode": (
                    next(
                        rule.mode.value
                        for rule in policy.health_rules
                        if rule.dimension is dimension
                    )
                    if policy is not None
                    else "unavailable"
                ),
                "status": (
                    "unavailable"
                    if policy is not None
                    and next(
                        rule.mode
                        for rule in policy.health_rules
                        if rule.dimension is dimension
                    )
                    is HealthRuleMode.UNAVAILABLE
                    else "unassessed"
                ),
                "numericValue": None,
            }
            for dimension in HealthDimension
        ]
        assessment: dict[str, Any] | None = None
        if project.current_health_snapshot:
            persisted_assessment = _json_object(project.current_health_snapshot)
            evaluation = persisted_assessment.get("evaluation")
            if not isinstance(evaluation, dict):
                raise ValueError("Persisted Project health evaluation is invalid.")
            results = evaluation.get("dimensionResults")
            if not isinstance(results, list):
                raise ValueError("Persisted Project health dimensions are invalid.")
            dimensions = [dict(value) for value in results if isinstance(value, dict)]
            if len(dimensions) != 4:
                raise ValueError("Persisted Project health dimensions are incomplete.")
            assessment = {
                "globalId": str(UUID(str(project.current_health_assessment_global_id))),
                "assessedAt": _datetime_iso(project.current_health_at),
                "actor": persisted_assessment["actor"],
                "reason": evaluation.get("reason"),
                "recoveryPlan": evaluation.get("recoveryPlan"),
            }

        actions = [
            self._transition_option(
                project,
                policy,
                binding,
                persisted_bindings,
                action,
                mutable=mutable,
            )
            for action in ProjectControlAction
        ]
        can_assess = bool(
            mutable
            and self._has_command_transport()
            and policy is not None
            and binding is not None
            and self._actor_matches_slot(
                project,
                persisted_bindings,
                policy.health_assessment_slot,
            )
        )
        return {
            "project": {
                "globalId": str(project_id),
                "businessCode": str(project.business_code),
                "title": str(project.title),
                "state": str(project.lifecycle_state),
                "version": int(project.optimistic_version),
                "tenantId": str(project.tenant_id),
            },
            "policy": (
                {
                    "globalId": str(policy.policy_global_id),
                    "code": policy.policy_code,
                    "version": policy.policy_version,
                    "snapshotHash": policy.snapshot_hash,
                    "title": policy_title or policy.policy_code,
                    "healthAssessmentSlot": policy.health_assessment_slot,
                }
                if policy is not None
                else None
            ),
            "binding": (
                {
                    "globalId": str(binding.global_id),
                    "version": int(project.control_binding_version),
                    "authorities": persisted_bindings,
                }
                if binding is not None
                else None
            ),
            "health": {
                "overallStatus": str(project.current_health_status),
                "dimensions": dimensions,
                "assessment": assessment,
            },
            "lifecycleActions": actions,
            "bindingOptions": (
                self._binding_options(project) if can_bind_policy else None
            ),
            "permissions": {
                "canBindPolicy": can_bind_policy,
                "canAssessHealth": can_assess,
                "canTransition": any(bool(value["available"]) for value in actions),
            },
        }

    def _binding_options(self, project) -> dict[str, list[dict[str, object]]]:
        """Return only candidates the exact bind command can revalidate."""

        roots = frappe.get_all(
            "NPI Project Control Policy",
            filters={"enabled": 1},
            pluck="global_id",
            order_by="policy_code asc, global_id asc",
            limit_page_length=_MAX_BINDING_POLICY_OPTIONS + 1,
        )
        if len(roots) > _MAX_BINDING_POLICY_OPTIONS:
            raise NpiProblem(
                422,
                "PROJECT_CONTROL_SCOPE_TOO_LARGE",
                _("Narrow the enabled Project Control Policy scope."),
            )
        version_rows = (
            frappe.get_all(
                "NPI Project Control Policy Version",
                filters={
                    "project_control_policy": ["in", list(roots)],
                    "publication_state": "published",
                },
                fields=[
                    "policy_global_id",
                    "policy_code",
                    "policy_version",
                    "snapshot_hash",
                    "title",
                ],
                order_by=(
                    "policy_code asc, policy_version desc, " "policy_global_id asc"
                ),
                limit_page_length=_MAX_BINDING_POLICY_OPTIONS + 1,
            )
            if roots
            else []
        )
        if len(version_rows) > _MAX_BINDING_POLICY_OPTIONS:
            raise NpiProblem(
                422,
                "PROJECT_CONTROL_SCOPE_TOO_LARGE",
                _("Narrow the published Project Control Policy scope."),
            )
        policies: list[dict[str, object]] = []
        seen_policies: set[tuple[str, int]] = set()
        for row in version_rows:
            reference = {
                "globalId": str(_row_value(row, "policy_global_id")),
                "version": int(_row_value(row, "policy_version")),
                "snapshotHash": str(_row_value(row, "snapshot_hash")),
            }
            policy, _payload = self._load_policy(reference)
            identity = (
                str(policy.policy_global_id),
                policy.policy_version,
            )
            if identity in seen_policies:
                raise ValueError(
                    "Published Project Control Policy identity is ambiguous."
                )
            if (
                str(_row_value(row, "policy_code")) != policy.policy_code
                or not isinstance(_row_value(row, "title"), str)
                or not str(_row_value(row, "title")).strip()
            ):
                raise ValueError("Published Project Control Policy option is invalid.")
            policies.append(
                {
                    "policyRef": reference,
                    "code": policy.policy_code,
                    "title": str(_row_value(row, "title")).strip(),
                    "authoritySlots": list(policy.authority_slots),
                }
            )
            seen_policies.add(identity)

        return {
            "policies": policies,
            "eligibleMembers": [
                member
                for member in self._eligible_member_options(project)
                if _member_can_use_project_controls(
                    project,
                    str(member["userId"]),
                )
            ],
        }

    def _eligible_member_options(
        self,
        project,
    ) -> list[dict[str, object]]:
        eligible_members, truncated = self._eligible_member_option_page(project)
        if truncated:
            raise NpiProblem(
                422,
                "PROJECT_CONTROL_SCOPE_TOO_LARGE",
                _("Narrow the current Project member scope."),
            )
        return eligible_members

    def _eligible_member_option_page(
        self,
        project,
    ) -> tuple[list[dict[str, object]], bool]:
        member_rows = frappe.get_all(
            "NPI Project Member",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
            },
            fields=[
                "global_id",
                "user_id",
                "effective_from",
                "effective_to",
            ],
            order_by="user_id asc, global_id asc",
            limit_page_length=_MAX_BINDING_MEMBER_OPTIONS + 1,
        )
        truncated = len(member_rows) > _MAX_BINDING_MEMBER_OPTIONS
        eligible_members: list[dict[str, object]] = []
        seen_members: set[str] = set()
        today = date.today()
        for row in member_rows[:_MAX_BINDING_MEMBER_OPTIONS]:
            member_id = str(UUID(str(_row_value(row, "global_id"))))
            effective_from = _date_value(_row_value(row, "effective_from"))
            effective_to_value = _row_value(
                row,
                "effective_to",
                default=None,
            )
            effective_to = (
                _date_value(effective_to_value) if effective_to_value else None
            )
            if effective_from > today or (
                effective_to is not None and effective_to < today
            ):
                continue
            try:
                user = _enabled_internal_user(str(_row_value(row, "user_id")))
            except RequestValidationFailed:
                continue
            if member_id in seen_members:
                raise ValueError("Current Project member identity is ambiguous.")
            eligible_members.append(
                {
                    "memberGlobalId": member_id,
                    "userId": str(_row_value(row, "user_id")).casefold(),
                    "displayName": str(user["full_name"]).strip(),
                }
            )
            seen_members.add(member_id)
        return eligible_members, truncated

    def _comment_options(
        self,
        project,
    ) -> dict[str, object]:
        truncated = False
        mentions, mentions_truncated = self._eligible_member_option_page(project)
        truncated = truncated or mentions_truncated
        attachments: list[dict[str, object]] = []
        file_names = frappe.get_all(
            "NPI File Revision",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "is_private": 1,
                "scan_state": "clean",
            },
            pluck="name",
            order_by="global_id asc",
            limit_page_length=_MAX_COMMENT_OPTION_CANDIDATES + 1,
        )
        if len(file_names) > _MAX_COMMENT_OPTION_CANDIDATES:
            truncated = True
        for name in file_names[:_MAX_COMMENT_OPTION_CANDIDATES]:
            document = _optional_doc("NPI File Revision", str(name))
            if (
                document is None
                or str(document.tenant_id) != str(project.tenant_id)
                or str(document.project_global_id) != str(project.global_id)
            ):
                raise ValueError("Project File Revision option identity drifted.")
            if not has_live_private_file_identity(document):
                continue
            snapshot = file_revision_source_snapshot(document)
            if snapshot["isPrivate"] is not True or snapshot["scanState"] != "clean":
                raise ValueError("Project File Revision option is not selectable.")
            attachments.append(
                {
                    "globalId": str(UUID(str(snapshot["globalId"]))),
                    "version": int(snapshot["fileOptimisticVersion"]),
                    "fileName": str(snapshot["fileName"]),
                    "mimeType": str(snapshot["mimeType"]),
                    "sizeBytes": int(snapshot["sizeBytes"]),
                    "sha256": str(snapshot["sha256"]),
                    "scanState": "clean",
                }
            )

        object_specs: list[tuple[str, str, int]] = [
            (
                "project",
                str(project.global_id),
                int(project.optimistic_version),
            )
        ]
        for object_type, doctype in (
            ("gate", "NPI Gate Shell"),
            ("domain_work_item", "NPI Domain Work Item"),
            ("learning", "NPI Project Learning"),
        ):
            remaining = _MAX_COMMENT_OPTION_CANDIDATES - len(object_specs)
            filters = {
                "project_global_id": str(project.global_id),
            }
            if object_type != "gate":
                filters["tenant_id"] = str(project.tenant_id)
            rows = frappe.get_all(
                doctype,
                filters=filters,
                fields=["global_id", "optimistic_version"],
                order_by="global_id asc",
                limit_page_length=remaining + 1,
            )
            if len(rows) > remaining:
                truncated = True
            object_specs.extend(
                (
                    object_type,
                    str(_row_value(row, "global_id")),
                    int(_row_value(row, "optimistic_version")),
                )
                for row in rows[:remaining]
            )
        for attachment in attachments:
            if len(object_specs) >= _MAX_COMMENT_OPTION_CANDIDATES:
                truncated = True
                break
            object_specs.append(
                (
                    "file_revision",
                    str(attachment["globalId"]),
                    int(attachment["version"]),
                )
            )
        object_links = []
        for object_type, global_id, version in object_specs:
            resolved = self._resolve_object_link(
                project,
                object_type,
                UUID(global_id),
                version,
                path="commentOptions.objectLinks",
            )
            resolved["target"] = _object_link_target(
                resolved,
                UUID(str(project.global_id)),
            )
            object_links.append(resolved)
        return {
            "truncated": truncated,
            "mentions": mentions,
            "attachments": attachments,
            "objectLinks": object_links,
        }

    def _transition_option(
        self,
        project,
        policy: ProjectControlPolicySnapshot | None,
        binding: ProjectControlBinding | None,
        persisted_bindings: Sequence[Mapping[str, str]],
        action: ProjectControlAction,
        *,
        mutable: bool,
    ) -> dict[str, Any]:
        base: dict[str, Any] = {
            "action": action.value,
            "available": False,
            "targetState": {
                ProjectControlAction.PAUSE: "on_hold",
                ProjectControlAction.CANCEL: "cancelled",
                ProjectControlAction.RESUME: "active",
                ProjectControlAction.COMPLETE: "completed",
            }[action],
            "authoritySlot": None,
            "reasonCode": "policy_missing",
            "prerequisites": [],
        }
        if not mutable:
            base["reasonCode"] = "project_terminal"
            return base
        if policy is None or binding is None:
            return base
        try:
            rule = policy.transition(
                ProjectLifecycleState(str(project.lifecycle_state)),
                action,
            )
        except NpiProblem:
            base["reasonCode"] = "transition_not_defined"
            return base
        base["authoritySlot"] = rule.authority_slot
        if not self._has_command_transport():
            base["reasonCode"] = "command_access_required"
            return base
        if not self._actor_matches_slot(
            project,
            persisted_bindings,
            rule.authority_slot,
        ):
            base["reasonCode"] = "authority_required"
            return base
        states = self._resolve_prerequisites(project, rule.prerequisites)
        prerequisites = [
            {"key": key.value, "status": states[key].value}
            for key in sorted(states, key=lambda value: value.value)
        ]
        base["prerequisites"] = prerequisites
        if any(value is PrerequisiteStatus.UNAVAILABLE for value in states.values()):
            base["reasonCode"] = "prerequisite_unavailable"
            return base
        if any(value is PrerequisiteStatus.BLOCKED for value in states.values()):
            base["reasonCode"] = "prerequisite_blocked"
            return base
        base["available"] = True
        base["reasonCode"] = "available"
        return base

    def _authorized_project(self, project_id: UUID):
        project = _optional_doc("NPI Engineering Project", str(project_id))
        if project is None or not self._can_view_project(project):
            return None
        return project

    def _locked_authorized_project(
        self,
        project_id: UUID,
        *,
        administer: bool = False,
    ):
        try:
            project = frappe.get_doc(
                "NPI Engineering Project",
                str(project_id),
                for_update=True,
            )
        except frappe.DoesNotExistError:
            return None
        if not self._can_view_project(project):
            return None
        if administer and not self._is_internal_system_manager():
            raise PermissionDenied()
        return project

    def _can_view_project(self, project) -> bool:
        if self.principal.is_external:
            return False
        if self.principal.tenant_id != str(project.tenant_id):
            return False
        return bool(
            self._is_internal_system_manager()
            or str(project.owner_user_id).casefold() == self.actor.casefold()
        )

    def _is_internal_system_manager(self) -> bool:
        return bool(
            not self.principal.is_external and "System Manager" in self.principal.roles
        )

    def _has_command_transport(self) -> bool:
        return bool(
            not self.principal.is_external
            and _COMMAND_TRANSPORT_ROLE in self.principal.roles
        )

    def _load_policy(
        self,
        reference: object,
        *,
        require_enabled_root: bool = True,
    ) -> tuple[ProjectControlPolicySnapshot, dict[str, Any]]:
        if not isinstance(reference, Mapping) or set(reference) != {
            "globalId",
            "version",
            "snapshotHash",
        }:
            raise _field_problem(
                "policyRef",
                _("Select an exact published Project Control Policy version."),
            )
        global_id = _uuid_value(reference["globalId"], "policyRef.globalId")
        version = _positive_integer(reference["version"], "policyRef.version")
        snapshot_hash = _hash_value(
            reference["snapshotHash"],
            "policyRef.snapshotHash",
        )
        document = _optional_doc(
            "NPI Project Control Policy Version",
            f"{global_id}:{version}",
        )
        if (
            document is None
            or str(document.publication_state) != "published"
            or str(document.policy_global_id) != str(global_id)
            or int(document.policy_version) != version
            or str(document.snapshot_hash) != snapshot_hash
        ):
            raise ProjectControlPolicyUnavailable()
        root = _optional_doc(
            "NPI Project Control Policy",
            str(document.project_control_policy),
        )
        if (
            root is None
            or str(root.global_id) != str(global_id)
            or str(root.policy_code) != str(document.policy_code)
            or (require_enabled_root and int(root.enabled or 0) != 1)
        ):
            raise ProjectControlPolicyUnavailable()
        payload = _json_object(document.snapshot)
        if sha256_json(payload) != snapshot_hash:
            raise ValueError("Persisted Project Control Policy hash failed.")
        return _policy_from_snapshot(payload, snapshot_hash), payload

    def _current_policy(
        self,
        project,
    ) -> tuple[ProjectControlPolicySnapshot, dict[str, Any]]:
        if not all(
            (
                project.control_binding_global_id,
                project.control_policy_global_id,
                project.control_policy_version,
                project.control_policy_snapshot_hash,
            )
        ):
            raise ProjectControlPolicyUnavailable()
        return self._load_policy(
            {
                "globalId": str(project.control_policy_global_id),
                "version": int(project.control_policy_version),
                "snapshotHash": str(project.control_policy_snapshot_hash),
            },
            require_enabled_root=False,
        )

    def _resolve_authorities(
        self,
        project,
        policy: ProjectControlPolicySnapshot,
        values: Sequence[object],
    ) -> tuple[
        tuple[FrozenProjectControlAuthority, ...],
        list[dict[str, str]],
    ]:
        if (
            not isinstance(values, Sequence)
            or isinstance(values, (str, bytes))
            or len(values) != len(policy.authority_slots)
            or len(values) > 64
        ):
            raise _field_problem(
                "bindings",
                _("Bind every Project control authority slot exactly once."),
            )
        by_slot: dict[str, UUID] = {}
        for index, value in enumerate(values):
            if not isinstance(value, Mapping) or set(value) != {
                "slot",
                "memberGlobalId",
            }:
                raise _field_problem(
                    f"bindings[{index}]",
                    _("Enter a valid Project control authority binding."),
                )
            slot = _controlled_key(value["slot"], f"bindings[{index}].slot")
            if slot in by_slot:
                raise _field_problem(
                    f"bindings[{index}].slot",
                    _("Bind each authority slot once."),
                )
            by_slot[slot] = _uuid_value(
                value["memberGlobalId"],
                f"bindings[{index}].memberGlobalId",
            )
        if set(by_slot) != set(policy.authority_slots):
            raise _field_problem(
                "bindings",
                _("Bind every Project control authority slot exactly once."),
            )
        authorities: list[FrozenProjectControlAuthority] = []
        persisted: list[dict[str, str]] = []
        for slot in sorted(by_slot, key=str.casefold):
            member = self._active_internal_member(
                project,
                by_slot[slot],
            )
            if not _member_can_use_project_controls(
                project,
                str(member.user_id),
            ):
                raise _field_problem(
                    f"bindings.{slot}",
                    _("The assigned Project control authority is required."),
                )
            authorities.append(
                FrozenProjectControlAuthority(
                    slot=slot,
                    member_global_id=UUID(str(member.global_id)),
                    user_id=str(member.user_id),
                )
            )
            user = _enabled_internal_user(str(member.user_id))
            persisted.append(
                {
                    "slot": slot,
                    "memberGlobalId": str(UUID(str(member.global_id))),
                    "userId": str(member.user_id).casefold(),
                    "displayName": str(user["full_name"]).strip(),
                }
            )
        return tuple(authorities), persisted

    def _current_binding(
        self,
        project,
        policy: ProjectControlPolicySnapshot,
    ) -> tuple[ProjectControlBinding, list[dict[str, str]]]:
        document = _optional_doc(
            "NPI Project Control Binding",
            str(project.control_binding_global_id),
        )
        if (
            document is None
            or str(document.tenant_id) != str(project.tenant_id)
            or str(document.project_global_id) != str(project.global_id)
            or int(document.binding_version) != int(project.control_binding_version)
            or str(document.policy_global_id) != str(policy.policy_global_id)
            or int(document.policy_version) != policy.policy_version
            or str(document.policy_snapshot_hash) != policy.snapshot_hash
        ):
            raise ProjectControlPolicyUnavailable()
        binding_snapshot = _validated_binding_snapshot(document)
        persisted = _json_array(document.authority_bindings)
        if binding_snapshot["authorityBindings"] != persisted:
            raise ValueError("Persisted Project authority bindings drifted.")
        normalized: list[dict[str, str]] = []
        authorities: list[FrozenProjectControlAuthority] = []
        for value in persisted:
            if not isinstance(value, dict) or set(value) != {
                "slot",
                "memberGlobalId",
                "userId",
                "displayName",
            }:
                raise ValueError("Persisted Project authority binding failed.")
            normalized_value = {
                "slot": str(value["slot"]),
                "memberGlobalId": str(UUID(str(value["memberGlobalId"]))),
                "userId": str(value["userId"]).casefold(),
                "displayName": str(value["displayName"]),
            }
            normalized.append(normalized_value)
            authorities.append(
                FrozenProjectControlAuthority(
                    slot=normalized_value["slot"],
                    member_global_id=UUID(normalized_value["memberGlobalId"]),
                    user_id=normalized_value["userId"],
                )
            )
        binding = ProjectControlBinding(
            global_id=UUID(str(document.global_id)),
            tenant_id=str(document.tenant_id),
            project_global_id=UUID(str(document.project_global_id)),
            policy_global_id=UUID(str(document.policy_global_id)),
            policy_version=int(document.policy_version),
            policy_snapshot_hash=str(document.policy_snapshot_hash),
            authorities=tuple(authorities),
            version=int(document.binding_version),
        )
        binding.require_policy(policy)
        return binding, normalized

    def _actor_authority(
        self,
        project,
        binding: ProjectControlBinding,
        persisted_bindings: Sequence[Mapping[str, str]],
        *,
        slot: str,
    ) -> dict[str, str]:
        matches = [
            value
            for value in persisted_bindings
            if value["slot"] == slot
            and value["userId"].casefold() == self.actor.casefold()
        ]
        if len(matches) != 1:
            raise PermissionDenied()
        selected = dict(matches[0])
        self._active_internal_member(
            project,
            UUID(selected["memberGlobalId"]),
            expected_user_id=self.actor,
        )
        binding.require_actor(
            slot,
            actor_member_global_id=UUID(selected["memberGlobalId"]),
            actor_user_id=self.actor,
        )
        return selected

    def _actor_authority_for_transition(
        self,
        project,
        policy: ProjectControlPolicySnapshot,
        binding: ProjectControlBinding,
        persisted_bindings: Sequence[Mapping[str, str]],
        action: ProjectControlAction,
    ) -> dict[str, str]:
        rule = policy.transition(
            ProjectLifecycleState(str(project.lifecycle_state)),
            action,
        )
        matches = [
            dict(value)
            for value in persisted_bindings
            if value["slot"] == rule.authority_slot
            and value["userId"].casefold() == self.actor.casefold()
        ]
        if len(matches) != 1:
            raise PermissionDenied()
        selected = matches[0]
        self._active_internal_member(
            project,
            UUID(selected["memberGlobalId"]),
            expected_user_id=self.actor,
        )
        binding.require_actor(
            rule.authority_slot,
            actor_member_global_id=UUID(selected["memberGlobalId"]),
            actor_user_id=self.actor,
        )
        return selected

    def _actor_matches_slot(
        self,
        project,
        persisted_bindings: Sequence[Mapping[str, str]],
        slot: str,
    ) -> bool:
        matches = [
            value
            for value in persisted_bindings
            if value["slot"] == slot
            and value["userId"].casefold() == self.actor.casefold()
        ]
        if len(matches) != 1:
            return False
        try:
            self._active_internal_member(
                project,
                UUID(matches[0]["memberGlobalId"]),
                expected_user_id=self.actor,
            )
        except (NpiProblem, ValueError):
            return False
        return True

    def _active_internal_member(
        self,
        project,
        member_global_id: UUID,
        *,
        expected_user_id: str | None = None,
    ):
        member = _optional_doc("NPI Project Member", str(member_global_id))
        if (
            member is None
            or str(member.tenant_id) != str(project.tenant_id)
            or str(member.project_global_id) != str(project.global_id)
        ):
            raise _field_problem(
                "bindings",
                _("Select a current internal member of this Project."),
            )
        today = date.today()
        effective_from = _date_value(member.effective_from)
        effective_to = _date_value(member.effective_to) if member.effective_to else None
        if (
            effective_from > today
            or (effective_to is not None and effective_to < today)
            or (
                expected_user_id is not None
                and str(member.user_id).casefold() != expected_user_id.casefold()
            )
        ):
            raise _field_problem(
                "bindings",
                _("Select a current internal member of this Project."),
            )
        _enabled_internal_user(str(member.user_id))
        return member

    def _resolve_prerequisites(
        self,
        project,
        keys: Sequence[ProjectPrerequisiteKey],
    ) -> dict[ProjectPrerequisiteKey, PrerequisiteStatus]:
        result: dict[ProjectPrerequisiteKey, PrerequisiteStatus] = {}
        for key in keys:
            if key is ProjectPrerequisiteKey.OPEN_BLOCKERS:
                count = frappe.db.count(
                    "NPI Domain Work Item",
                    filters={
                        "tenant_id": str(project.tenant_id),
                        "project_global_id": str(project.global_id),
                        "blocking": 1,
                        "state_terminal": 0,
                    },
                )
                result[key] = (
                    PrerequisiteStatus.BLOCKED
                    if count
                    else PrerequisiteStatus.SATISFIED
                )
            elif key is ProjectPrerequisiteKey.CONTROLLED_FILES:
                files = frappe.get_all(
                    "NPI File Revision",
                    filters={
                        "tenant_id": str(project.tenant_id),
                        "project_global_id": str(project.global_id),
                    },
                    fields=["scan_state", "released"],
                    limit_page_length=10001,
                )
                result[key] = (
                    PrerequisiteStatus.BLOCKED
                    if len(files) > 10000
                    or any(
                        str(value.scan_state) != "clean"
                        or int(value.released or 0) != 1
                        for value in files
                    )
                    else PrerequisiteStatus.SATISFIED
                )
            elif key in {
                ProjectPrerequisiteKey.HANDOVER,
                ProjectPrerequisiteKey.COST,
            }:
                result[key] = PrerequisiteStatus.UNAVAILABLE
            else:
                raise ValueError("Unsupported Project prerequisite.")
        return result

    def _idempotency_replay(
        self,
        actor_key_hash: str,
        payload_hash: str,
    ) -> dict[str, Any] | None:
        record = frappe.db.get_value(
            "NPI Project Control Idempotency",
            {"actor_key_hash": actor_key_hash},
            ["payload_hash", "response_json", "response_sealed"],
            as_dict=True,
        )
        if not record:
            return None
        if str(record.payload_hash) != payload_hash:
            from npi_core.project.domain import IdempotencyConflict

            raise IdempotencyConflict()
        if int(record.response_sealed or 0) != 1:
            raise RuntimeError("Persisted Project control idempotency is unsealed.")
        return _json_object(record.response_json)

    def _insert_idempotency(
        self,
        actor_key_hash: str,
        payload_hash: str,
        project,
        operation: str,
    ):
        try:
            return frappe.get_doc(
                {
                    "doctype": "NPI Project Control Idempotency",
                    "record_id": str(uuid4()),
                    "actor": self.actor,
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "operation": operation,
                    "actor_key_hash": actor_key_hash,
                    "payload_hash": payload_hash,
                    "response_json": canonical_json({}),
                    "response_sealed": 0,
                }
            ).insert()
        except frappe.UniqueValidationError:
            frappe.db.rollback()
            replay = self._idempotency_replay(actor_key_hash, payload_hash)
            if replay is None:
                raise
            return replay

    @staticmethod
    def _seal_idempotency(document, response: Mapping[str, object]) -> None:
        document.response_json = canonical_json(dict(response))
        document.response_sealed = 1
        document.save()

    def _append_activity(
        self,
        project,
        *,
        event_type: str,
        detail: Mapping[str, object],
        occurred_at: datetime | None = None,
    ) -> dict[str, Any]:
        event_global_id = uuid4()
        event_at = occurred_at or datetime.now(UTC)
        event_key = f"{project.global_id}:{_datetime_iso(event_at)}:{event_global_id}"
        payload = {
            "schemaVersion": 1,
            "globalId": str(event_global_id),
            "eventKey": event_key,
            "tenantId": str(project.tenant_id),
            "projectGlobalId": str(project.global_id),
            "eventType": event_type,
            "actorUserId": self.actor,
            "occurredAt": _datetime_iso(event_at),
            "requestId": self.request_id,
            "traceId": self.trace_id,
            "detail": dict(detail),
        }
        frappe.get_doc(
            {
                "doctype": "NPI Project Activity Event",
                "global_id": str(event_global_id),
                "event_key": event_key,
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "event_type": event_type,
                "actor_user_id": self.actor,
                "occurred_at": _database_datetime(event_at),
                "request_id": self.request_id,
                "trace_id": self.trace_id,
                "payload": canonical_json(payload),
                "payload_hash": sha256_json(payload),
            }
        ).insert()
        return payload

    def _append_audit(
        self,
        *,
        operation: str,
        global_id: UUID,
        object_version: int,
        result: str,
        summary: Mapping[str, object],
    ) -> None:
        event = create_audit_event(
            actor=self.actor,
            trace_id=self.trace_id,
            operation=operation,
            global_id=global_id,
            object_version=object_version,
            result=result,
            input_summary=dict(summary),
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


def _query_project_activity_page(
    *,
    tenant_id: str,
    project_id: UUID,
    as_of: datetime,
    cursor: tuple[datetime, str] | None,
    limit: int,
) -> tuple[Any, ...]:
    base_filters: tuple[tuple[object, ...], ...] = (
        ("tenant_id", "=", tenant_id),
        ("project_global_id", "=", str(project_id)),
        ("occurred_at", "<=", _database_datetime(as_of)),
    )

    def query(extra_filters: Sequence[Sequence[object]]) -> tuple[Any, ...]:
        return tuple(
            frappe.get_all(
                "NPI Project Activity Event",
                filters=[
                    list(filter_value)
                    for filter_value in (*base_filters, *extra_filters)
                ],
                fields=[
                    "global_id",
                    "occurred_at",
                    "payload",
                    "payload_hash",
                ],
                order_by="occurred_at desc, global_id desc",
                limit_page_length=limit,
            )
        )

    if cursor is None:
        return query(())

    cursor_occurred_at, cursor_global_id = cursor
    database_occurred_at = _database_datetime(cursor_occurred_at)
    same_occurred_at = query(
        (
            ("occurred_at", "=", database_occurred_at),
            ("global_id", "<", cursor_global_id),
        )
    )
    earlier = query((("occurred_at", "<", database_occurred_at),))
    return _merge_project_activity_pages(
        same_occurred_at,
        earlier,
        limit=limit,
    )


def _merge_project_activity_pages(
    *pages: Sequence[Any],
    limit: int,
) -> tuple[Any, ...]:
    documents_by_id: dict[str, Any] = {}
    for document in (document for page in pages for document in page):
        global_id = str(UUID(str(document.global_id)))
        previous = documents_by_id.get(global_id)
        if previous is not None and (
            _datetime_iso(previous.occurred_at)
            != _datetime_iso(document.occurred_at)
            or str(previous.payload_hash) != str(document.payload_hash)
        ):
            raise ValueError("Persisted Project activity identity is inconsistent.")
        documents_by_id[global_id] = document
    return tuple(
        sorted(
            documents_by_id.values(),
            key=_activity_sort_key,
            reverse=True,
        )[:limit]
    )


def _activity_sort_key(document) -> tuple[datetime, str]:
    return (
        _datetime_value(document.occurred_at),
        str(UUID(str(document.global_id))),
    )


def _project_activity_query_fingerprint(
    *,
    tenant_id: str,
    actor_user_id: str,
    project_id: UUID,
) -> str:
    query_identity = {
        "actorUserId": actor_user_id,
        "projectId": str(project_id),
        "tenantId": tenant_id,
    }
    return hashlib.sha256(
        canonical_json(query_identity).encode("utf-8")
    ).hexdigest()


def _encode_project_activity_cursor(
    value: tuple[object, str],
    *,
    as_of: object,
    query_fingerprint: str,
    signing_key: bytes | None = None,
) -> str:
    if _HASH_PATTERN.fullmatch(query_fingerprint) is None:
        raise ValueError("An activity cursor query fingerprint must be a SHA-256 hash.")
    payload = canonical_json(
        {
            "asOf": _datetime_iso(as_of),
            "globalId": str(UUID(str(value[1]))),
            "occurredAt": _datetime_iso(value[0]),
            "queryFingerprint": query_fingerprint,
            "version": _PROJECT_ACTIVITY_CURSOR_VERSION,
        }
    ).encode("utf-8")
    resolved_signing_key = (
        signing_key
        if signing_key is not None
        else _project_activity_cursor_signing_key()
    )
    signature = hmac.new(
        resolved_signing_key,
        payload,
        hashlib.sha256,
    ).digest()
    cursor = f"{_base64url_encode(payload)}.{_base64url_encode(signature)}"
    if len(cursor) > 500:
        raise ValueError("The generated activity cursor exceeds the API limit.")
    return cursor


def _decode_project_activity_cursor(
    value: str,
    *,
    expected_query_fingerprint: str,
    signing_key: bytes | None = None,
) -> _ProjectActivityCursor:
    resolved_signing_key = (
        signing_key
        if signing_key is not None
        else _project_activity_cursor_signing_key()
    )
    try:
        if (
            not isinstance(value, str)
            or not value
            or len(value) > 500
            or _HASH_PATTERN.fullmatch(expected_query_fingerprint) is None
        ):
            raise ValueError
        encoded_payload, encoded_signature = value.split(".")
        decoded_payload = _base64url_decode(encoded_payload)
        signature = _base64url_decode(encoded_signature)
        expected_signature = hmac.new(
            resolved_signing_key,
            decoded_payload,
            hashlib.sha256,
        ).digest()
        if (
            len(signature) != hashlib.sha256().digest_size
            or not hmac.compare_digest(signature, expected_signature)
        ):
            raise ValueError
        payload = json.loads(decoded_payload.decode("utf-8"))
        if (
            not isinstance(payload, dict)
            or set(payload)
            != {
                "asOf",
                "globalId",
                "occurredAt",
                "queryFingerprint",
                "version",
            }
            or type(payload["version"]) is not int
            or payload["version"] != _PROJECT_ACTIVITY_CURSOR_VERSION
            or not isinstance(payload["queryFingerprint"], str)
            or _HASH_PATTERN.fullmatch(payload["queryFingerprint"]) is None
            or payload["queryFingerprint"] != expected_query_fingerprint
        ):
            raise ValueError
        as_of = _datetime_value(payload["asOf"])
        occurred_at = _datetime_value(payload["occurredAt"])
        global_id = str(UUID(str(payload["globalId"])))
        if (
            occurred_at > as_of
            or _base64url_encode(
                canonical_json(
                    {
                        "asOf": _datetime_iso(as_of),
                        "globalId": global_id,
                        "occurredAt": _datetime_iso(occurred_at),
                        "queryFingerprint": payload["queryFingerprint"],
                        "version": payload["version"],
                    }
                ).encode("utf-8")
            )
            != encoded_payload
        ):
            raise ValueError
        return _ProjectActivityCursor(
            occurred_at=occurred_at,
            global_id=global_id,
            as_of=as_of,
            query_fingerprint=payload["queryFingerprint"],
        )
    except (
        binascii.Error,
        OverflowError,
        TypeError,
        UnicodeError,
        ValueError,
    ) as error:
        raise RequestValidationFailed(
            [{"path": "cursor", "message": _("Enter a valid cursor.")}]
        ) from error


def _project_activity_cursor_signing_key() -> bytes:
    try:
        local = getattr(frappe, "local", None)
        configuration = getattr(local, "conf", None)
        if configuration is None:
            configuration = getattr(frappe, "conf", None)
        if configuration is None:
            raise KeyError("encryption_key")
        persisted_key = configuration.get("encryption_key")
        if not isinstance(persisted_key, str):
            raise ValueError
        encoded_key = persisted_key.encode("ascii")
        decoded_key = base64.b64decode(
            encoded_key,
            altchars=b"-_",
            validate=True,
        )
        if (
            len(decoded_key) != 32
            or base64.urlsafe_b64encode(decoded_key) != encoded_key
        ):
            raise ValueError
    except (ImportError, KeyError, TypeError, UnicodeError, ValueError) as error:
        raise CursorSigningUnavailable() from error
    except Exception as error:
        raise CursorSigningUnavailable() from error
    return hmac.new(
        decoded_key,
        _PROJECT_ACTIVITY_CURSOR_KEY_CONTEXT,
        hashlib.sha256,
    ).digest()


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    if not value or "=" in value:
        raise ValueError
    padding = "=" * (-len(value) % 4)
    decoded = base64.b64decode(
        (value + padding).encode("ascii"),
        altchars=b"-_",
        validate=True,
    )
    if _base64url_encode(decoded) != value:
        raise ValueError
    return decoded


def _activity_response(document, project_id: UUID) -> dict[str, Any]:
    payload = _json_object(document.payload)
    if (
        sha256_json(payload) != str(document.payload_hash)
        or payload.get("globalId") != str(document.global_id)
        or payload.get("projectGlobalId") != str(project_id)
        or _datetime_iso(payload.get("occurredAt"))
        != _datetime_iso(document.occurred_at)
    ):
        raise ValueError("Persisted Project activity integrity failed.")
    return _activity_payload_response(payload, project_id)


def _activity_payload_response(
    payload: Mapping[str, object],
    project_id: UUID,
) -> dict[str, Any]:
    detail_value = payload.get("detail")
    if not isinstance(detail_value, Mapping):
        raise ValueError("Persisted Project activity detail is invalid.")
    detail = dict(detail_value)
    links = detail.get("objectLinks")
    if isinstance(links, list):
        detail["objectLinks"] = [
            {
                **dict(value),
                "target": _object_link_target(
                    value,
                    project_id,
                ),
            }
            for value in links
            if isinstance(value, Mapping)
        ]
        if len(detail["objectLinks"]) != len(links):
            raise ValueError("Persisted Project object links are invalid.")
    return {
        "globalId": str(UUID(str(payload["globalId"]))),
        "eventType": str(payload["eventType"]),
        "actorUserId": str(payload["actorUserId"]),
        "occurredAt": _datetime_iso(payload["occurredAt"]),
        "detail": detail,
    }


def _object_link_target(
    value: Mapping[str, object],
    project_id: UUID,
) -> dict[str, str]:
    object_type = str(value.get("type"))
    global_id = str(UUID(str(value.get("globalId"))))
    if object_type == "gate":
        return {
            "kind": "gate",
            "projectId": str(project_id),
            "gateId": global_id,
        }
    if object_type == "domain_work_item":
        return {
            "kind": "project_work_item",
            "projectId": str(project_id),
            "workItemId": global_id,
        }
    if object_type == "learning":
        return {
            "kind": "project_learning",
            "projectId": str(project_id),
            "learningId": global_id,
        }
    return {
        "kind": "project",
        "projectId": str(project_id),
    }


def _validated_binding_snapshot(document) -> dict[str, Any]:
    snapshot = _json_object(document.binding_snapshot)
    required = {
        "schemaVersion",
        "globalId",
        "tenantId",
        "projectGlobalId",
        "bindingVersion",
        "policyRef",
        "policySnapshotHash",
        "authorityBindings",
        "boundBy",
        "boundAt",
        "projectVersion",
        "requestId",
        "traceId",
    }
    policy_ref = snapshot.get("policyRef")
    if (
        set(snapshot) != required
        or snapshot.get("schemaVersion") != 1
        or sha256_json(snapshot) != str(document.snapshot_hash)
        or not isinstance(policy_ref, dict)
        or set(policy_ref) != {"globalId", "version", "snapshotHash"}
        or snapshot.get("globalId") != str(document.global_id)
        or snapshot.get("tenantId") != str(document.tenant_id)
        or snapshot.get("projectGlobalId") != str(document.project_global_id)
        or snapshot.get("bindingVersion") != int(document.binding_version)
        or policy_ref.get("globalId") != str(document.policy_global_id)
        or policy_ref.get("version") != int(document.policy_version)
        or policy_ref.get("snapshotHash") != str(document.policy_snapshot_hash)
        or snapshot.get("policySnapshotHash") != str(document.policy_snapshot_hash)
        or not isinstance(snapshot.get("authorityBindings"), list)
        or snapshot.get("boundBy") != str(document.bound_by)
        or _datetime_iso(snapshot.get("boundAt")) != _datetime_iso(document.bound_at)
        or snapshot.get("projectVersion") != int(document.project_version)
        or snapshot.get("requestId") != str(document.request_id)
        or snapshot.get("traceId") != str(document.trace_id)
    ):
        raise ValueError("Persisted Project Control Binding snapshot failed.")
    return snapshot


def _validated_learning_snapshot(document) -> dict[str, Any]:
    snapshot = _json_object(document.record_snapshot)
    required = {
        "schemaVersion",
        "globalId",
        "tenantId",
        "projectGlobalId",
        "kind",
        "title",
        "content",
        "recommendation",
        "tags",
        "templateGlobalId",
        "templateVersion",
        "templateSnapshotHash",
        "createdBy",
        "createdAt",
        "requestId",
        "traceId",
    }
    tags = _json_string_array(document.tags)
    if (
        set(snapshot) != required
        or snapshot.get("schemaVersion") != 1
        or sha256_json(snapshot) != str(document.snapshot_hash)
        or snapshot.get("globalId") != str(document.global_id)
        or snapshot.get("tenantId") != str(document.tenant_id)
        or snapshot.get("projectGlobalId") != str(document.project_global_id)
        or snapshot.get("kind") != str(document.kind)
        or snapshot.get("title") != str(document.title)
        or snapshot.get("content") != str(document.content)
        or snapshot.get("recommendation") != str(document.recommendation or "")
        or snapshot.get("tags") != tags
        or snapshot.get("templateGlobalId") != str(document.template_global_id)
        or snapshot.get("templateVersion") != int(document.template_version)
        or snapshot.get("templateSnapshotHash") != str(document.template_snapshot_hash)
        or snapshot.get("createdBy") != str(document.created_by)
        or _datetime_iso(snapshot.get("createdAt"))
        != _datetime_iso(document.created_at)
        or snapshot.get("requestId") != str(document.request_id)
        or snapshot.get("traceId") != str(document.trace_id)
        or int(document.optimistic_version) != 1
    ):
        raise ValueError("Persisted Project Learning snapshot failed.")
    return snapshot


def _learning_response(document) -> dict[str, Any]:
    snapshot = _validated_learning_snapshot(document)
    return {
        "globalId": str(UUID(str(snapshot["globalId"]))),
        "projectGlobalId": str(UUID(str(snapshot["projectGlobalId"]))),
        "kind": str(snapshot["kind"]),
        "title": str(snapshot["title"]),
        "content": str(snapshot["content"]),
        "recommendation": str(snapshot["recommendation"]),
        "tags": list(snapshot["tags"]),
        "templateRef": {
            "globalId": str(UUID(str(snapshot["templateGlobalId"]))),
            "version": int(snapshot["templateVersion"]),
            "snapshotHash": str(snapshot["templateSnapshotHash"]),
        },
        "createdBy": str(snapshot["createdBy"]),
        "createdAt": _datetime_iso(snapshot["createdAt"]),
        "version": int(document.optimistic_version),
        "target": {
            "kind": "project_learning",
            "projectId": str(UUID(str(snapshot["projectGlobalId"]))),
            "learningId": str(UUID(str(snapshot["globalId"]))),
        },
    }


def _learning_kind(value: object, path: str) -> str:
    if value not in {
        "retrospective",
        "lesson",
        "template_improvement",
    }:
        raise _field_problem(path, _("Select a supported Project learning kind."))
    return str(value)


def _learning_tags(values: Sequence[object]) -> list[str]:
    if (
        not isinstance(values, Sequence)
        or isinstance(values, (str, bytes))
        or len(values) > 20
    ):
        raise _field_problem(
            "tags",
            _("Add no more than twenty Project learning tags."),
        )
    normalized = []
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 64:
            raise _field_problem(
                f"tags[{index}]",
                _("Enter a valid Project learning tag."),
            )
        normalized.append(value.strip())
    if len(set(normalized)) != len(normalized):
        raise _field_problem(
            "tags",
            _("Project learning tags must be unique."),
        )
    return sorted(normalized, key=str.casefold)


def _json_string_array(value: object) -> list[str]:
    values = _json_array(value)
    if any(not isinstance(item, str) for item in values):
        raise ValueError("Persisted string array is invalid.")
    return [str(item) for item in values]


def _input_sequence(
    value: object,
    path: str,
    *,
    maximum: int,
    message: str,
) -> list[object]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or len(value) > maximum
    ):
        raise _field_problem(path, message)
    return list(value)


def _optional_search(value: object | None) -> str | None:
    if value is None:
        return None
    return _optional_text(value, "search", 140)


def _optional_tag(value: object | None) -> str | None:
    if value is None:
        return None
    return _optional_text(value, "tag", 64)


def _bounded_limit(value: object) -> int:
    if type(value) is not int or value < 1 or value > 100:
        raise _field_problem(
            "limit",
            _("Enter a limit from one to one hundred."),
        )
    return value


def _policy_from_snapshot(
    value: Mapping[str, object],
    snapshot_hash: str,
) -> ProjectControlPolicySnapshot:
    required = {
        "schemaVersion",
        "globalId",
        "policyGlobalId",
        "policyCode",
        "policyVersion",
        "priorVersionRef",
        "authoritySlots",
        "healthAssessmentSlot",
        "healthRules",
        "aggregation",
        "transitions",
    }
    if set(value) != required or value["schemaVersion"] != 1:
        raise ValueError("Persisted Project Control Policy snapshot is invalid.")
    prior_value = value["priorVersionRef"]
    if prior_value is None:
        prior = None
    elif isinstance(prior_value, Mapping) and set(prior_value) == {
        "globalId",
        "version",
        "snapshotHash",
    }:
        prior = PriorPolicyVersionReference(
            global_id=UUID(str(prior_value["globalId"])),
            policy_version=int(prior_value["version"]),
            snapshot_hash=str(prior_value["snapshotHash"]),
        )
    else:
        raise ValueError("Persisted prior policy reference is invalid.")
    slots = value["authoritySlots"]
    rules = value["healthRules"]
    aggregation = value["aggregation"]
    transitions = value["transitions"]
    if (
        not isinstance(slots, list)
        or not isinstance(rules, list)
        or not isinstance(aggregation, Mapping)
        or set(aggregation) != {"mode", "requireAll"}
        or not isinstance(transitions, list)
    ):
        raise ValueError("Persisted Project Control Policy structure is invalid.")
    parsed_rules = []
    for rule in rules:
        if not isinstance(rule, Mapping) or set(rule) != {
            "dimension",
            "mode",
            "greenThreshold",
            "yellowThreshold",
        }:
            raise ValueError("Persisted Project health rule is invalid.")
        parsed_rules.append(
            HealthDimensionRule(
                dimension=HealthDimension(str(rule["dimension"])),
                mode=HealthRuleMode(str(rule["mode"])),
                green_threshold=rule["greenThreshold"],
                yellow_threshold=rule["yellowThreshold"],
            )
        )
    parsed_transitions = []
    for transition in transitions:
        if (
            not isinstance(transition, Mapping)
            or set(transition)
            != {
                "sourceState",
                "action",
                "targetState",
                "authoritySlot",
                "prerequisites",
            }
            or not isinstance(transition["prerequisites"], list)
        ):
            raise ValueError("Persisted Project lifecycle transition is invalid.")
        parsed_transitions.append(
            ProjectTransitionRule(
                source_state=ProjectLifecycleState(str(transition["sourceState"])),
                action=ProjectControlAction(str(transition["action"])),
                target_state=ProjectLifecycleState(str(transition["targetState"])),
                authority_slot=str(transition["authoritySlot"]),
                prerequisites=tuple(
                    ProjectPrerequisiteKey(str(item))
                    for item in transition["prerequisites"]
                ),
            )
        )
    return ProjectControlPolicySnapshot(
        global_id=UUID(str(value["globalId"])),
        policy_global_id=UUID(str(value["policyGlobalId"])),
        policy_code=str(value["policyCode"]),
        policy_version=int(value["policyVersion"]),
        prior_version_ref=prior,
        authority_slots=tuple(str(item) for item in slots),
        health_assessment_slot=str(value["healthAssessmentSlot"]),
        health_rules=tuple(parsed_rules),
        aggregation=HealthAggregationRule(
            mode=HealthAggregationMode(str(aggregation["mode"])),
            require_all=aggregation["requireAll"],  # type: ignore[arg-type]
        ),
        transitions=tuple(parsed_transitions),
        snapshot_hash=snapshot_hash,
    )


def _health_measurements(
    values: Sequence[object],
) -> tuple[HealthMeasurement, ...]:
    if (
        not isinstance(values, Sequence)
        or isinstance(values, (str, bytes))
        or len(values) > 4
    ):
        raise _field_problem(
            "measurements",
            _("Enter valid Project health measurements."),
        )
    parsed = []
    for index, value in enumerate(values):
        if not isinstance(value, Mapping) or set(value) != {
            "dimension",
            "numericValue",
            "manualStatus",
        }:
            raise _field_problem(
                f"measurements[{index}]",
                _("Enter a valid Project health measurement."),
            )
        manual = value["manualStatus"]
        parsed.append(
            HealthMeasurement(
                dimension=_enum_value(
                    HealthDimension,
                    value["dimension"],
                    f"measurements[{index}].dimension",
                ),
                numeric_value=value["numericValue"],
                manual_status=(
                    None
                    if manual is None
                    else _enum_value(
                        HealthStatus,
                        manual,
                        f"measurements[{index}].manualStatus",
                    )
                ),
            )
        )
    return tuple(parsed)


def _enabled_internal_user(user_id: str) -> Mapping[str, object]:
    value = frappe.db.get_value(
        "User",
        user_id,
        ["enabled", "user_type", "full_name"],
        as_dict=True,
    )
    if (
        not value
        or int(value.enabled or 0) != 1
        or str(value.user_type) != "System User"
        or not isinstance(value.full_name, str)
        or not value.full_name.strip()
    ):
        raise _field_problem(
            "bindings",
            _("Select an enabled internal Project member."),
        )
    return value


def _member_can_use_project_controls(project, user_id: str) -> bool:
    roles = set(frappe.get_roles(user_id))
    return bool(
        _COMMAND_TRANSPORT_ROLE in roles
        and (
            str(user_id).casefold() == str(project.owner_user_id).casefold()
            or "System Manager" in roles
        )
    )


def _optional_doc(doctype: str, name: str):
    try:
        return frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        return None


def _row_value(
    row: object,
    fieldname: str,
    *,
    default: object = ...,
) -> object:
    if isinstance(row, Mapping):
        if fieldname in row:
            return row[fieldname]
    elif hasattr(row, fieldname):
        return getattr(row, fieldname)
    if default is not ...:
        return default
    raise ValueError(f"Persisted row is missing {fieldname}.")


def _json_object(value: object) -> dict[str, Any]:
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("Persisted JSON object is invalid.") from error
    if not isinstance(parsed, dict):
        raise ValueError("Persisted JSON object is invalid.")
    return parsed


def _json_array(value: object) -> list[object]:
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("Persisted JSON array is invalid.") from error
    if not isinstance(parsed, list):
        raise ValueError("Persisted JSON array is invalid.")
    return parsed


def _uuid_value(value: object, path: str) -> UUID:
    if not isinstance(value, str):
        raise _field_problem(path, _("Enter a valid global ID."))
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError):
        raise _field_problem(path, _("Enter a valid global ID."))
    if str(parsed) != value.casefold():
        raise _field_problem(path, _("Enter a canonical global ID."))
    return parsed


def _positive_integer(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _field_problem(path, _("Enter a positive integer."))
    return value


def _query_positive_integer(value: object, path: str) -> int:
    if type(value) is int:
        parsed = value
    elif (
        isinstance(value, str)
        and len(value) <= 10
        and value.isascii()
        and value.isdigit()
    ):
        parsed = int(value)
        if str(parsed) != value:
            raise _field_problem(path, _("Enter a positive integer."))
    else:
        raise _field_problem(path, _("Enter a positive integer."))
    return _positive_integer(parsed, path)


def _hash_value(value: object, path: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise _field_problem(path, _("Enter a valid snapshot hash."))
    return value


def _controlled_key(value: object, path: str) -> str:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[a-z][a-z0-9_.-]{0,63}", value) is None
    ):
        raise _field_problem(path, _("Select a supported controlled key."))
    return value


def _enum_value(enum_type, value: object, path: str):
    if not isinstance(value, str):
        raise _field_problem(path, _("Select a supported value."))
    try:
        return enum_type(value)
    except ValueError:
        raise _field_problem(path, _("Select a supported value."))


def _required_text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise _field_problem(path, _("Enter valid text."))
    return value.strip()


def _optional_text(
    value: object,
    path: str,
    maximum: int,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value.strip()) > maximum:
        raise _field_problem(path, _("Enter valid text."))
    return value.strip() or None


def _require_project_version(project, expected: object) -> None:
    if type(expected) is not int or expected < 1:
        raise _field_problem(
            "expectedProjectVersion",
            _("Enter a positive Project version."),
        )
    if int(project.optimistic_version) != expected:
        raise VersionConflict()


def _date_value(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as error:
        raise ValueError("Persisted date is invalid.") from error


def _datetime_value(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("Persisted datetime is invalid.") from error
    else:
        raise ValueError("Persisted datetime is invalid.")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _datetime_iso(value: object) -> str:
    return _datetime_value(value).isoformat().replace("+00:00", "Z")


def _database_datetime(value: object) -> str:
    return _datetime_value(value).strftime("%Y-%m-%d %H:%M:%S.%f")


def _json_safe(value: object) -> object:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return _datetime_iso(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item)
            for key, item in sorted(
                value.items(),
                key=lambda entry: str(entry[0]),
            )
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_json_safe(item) for item in value]
    return value


def _payload_hash(value: Mapping[str, object]) -> str:
    return sha256_json(_json_safe(value))


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


@contextmanager
def _controlled_project_control_write_scope() -> Iterator[None]:
    names = (
        "npi_project_control_command_write",
        "npi_project_command_write",
        "npi_audit_append",
    )
    missing = object()
    previous = {name: getattr(frappe.flags, name, missing) for name in names}
    for name in names:
        setattr(frappe.flags, name, True)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is missing:
                try:
                    delattr(frappe.flags, name)
                except AttributeError:
                    pass
            else:
                setattr(frappe.flags, name, value)
