from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import frappe

from npi_core.documents.domain import command_payload_hash
from npi_core.documents.frappe_repository import (
    DocumentCommandOutcome,
    FrappeDocumentRepository,
    _database_datetime,
    _datetime_iso,
    _json_object,
    _project_response,
    _record_value,
)
from npi_core.ebom.domain import (
    EngineeringBomAuthorityUnavailable,
    EngineeringBomEventType,
    EngineeringBomIdempotencyConflict,
    EngineeringBomIdentityConflict,
    EngineeringBomLifecycleState,
    EngineeringBomLifecycleEvent,
    EngineeringBomLine,
    EngineeringBomPolicyReference,
    EngineeringBomPolicyState,
    EngineeringBomPolicyUnavailable,
    EngineeringBomPolicyVersion,
    EngineeringBomReviewDecision,
    EngineeringBomRevision,
    EngineeringBomRevisionLifecycle,
    EngineeringBomStateConflict,
    compare_engineering_bom_revisions,
    create_engineering_bom_revision,
    sha256_json,
    transition_engineering_bom,
)
from npi_core.ebom.frappe_validation import (
    ebom_command_write,
    ebom_lifecycle_write,
    ebom_line_value,
    ebom_policy_value,
)
from npi_core.ebom.diagnostics import ebom_create_server_step
from npi_core.foundation.security import Principal
from npi_core.foundation.errors import RequestValidationFailed
from npi_core.project_controls.terminal_guard import require_mutable_project


_MAX_EBOMS = 200
_MAX_POLICIES = 100
_MAX_REVISIONS = 200
_MAX_EVENTS = 1_000


class FrappeEngineeringBomRepository(FrappeDocumentRepository):
    """Project-authorized adapter for immutable EBOM revisions and lifecycle."""

    def __init__(
        self,
        *,
        principal: Principal,
        request_id: str,
        trace_id: str,
    ) -> None:
        super().__init__(
            principal=principal,
            request_id=request_id,
            trace_id=trace_id,
        )

    def authorize_scope(
        self,
        project_id: UUID,
        ebom_id: UUID | None = None,
        *,
        administer: bool = False,
    ) -> bool:
        """Authorize Project first; never resolve a protected EBOM first."""
        project = self._authorized_project(project_id)
        if project is None:
            return False
        if administer and not self._can_administer_project(project, project_id):
            return False
        return bool(
            ebom_id is None
            or self._ebom_for_project(project, ebom_id, lock=False) is not None
        )

    def list_eboms(self, project_id: UUID) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        rows = self._bounded_documents(
            "NPI Engineering BOM",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
            },
            order_by="engineering_bom_key asc, global_id asc",
            maximum=_MAX_EBOMS,
        )
        policies = self._published_policy_options(project)
        return {
            "project": _project_response(project),
            "permissions": {
                "view": True,
                "create": bool(policies),
            },
            "policies": list(policies),
            "items": [self._ebom_summary(row) for row in rows],
        }

    def ebom_detail(
        self,
        project_id: UUID,
        ebom_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        root = self._ebom_for_project(project, ebom_id, lock=False)
        if root is None:
            return None
        return self._detail_response(project, root)

    def create_ebom(
        self,
        project_id: UUID,
        *,
        idempotency_key_hash: str,
        policy_global_id: UUID,
        policy_version: int,
        policy_snapshot_hash: str,
        engineering_bom_key: str,
        title: str,
        reason: str,
        effectivity_note: str | None,
        lines: Sequence[Mapping[str, object]],
    ) -> DocumentCommandOutcome | None:
        with ebom_create_server_step("P504_CREATE_PROJECT_LOCK"):
            project = self._locked_command_project(project_id)
        if project is None:
            return None
        with ebom_create_server_step("P504_CREATE_POLICY_LOAD"):
            policy = self._load_exact_policy(
                project,
                policy_global_id=policy_global_id,
                policy_version=policy_version,
                snapshot_hash=policy_snapshot_hash,
                lock=True,
            )
        with ebom_create_server_step("P504_CREATE_POLICY_AUTHORITY"):
            self._require_policy_actor(policy, "create")
        with ebom_create_server_step("P504_CREATE_PAYLOAD_HASH"):
            payload = {
                "policyGlobalId": str(policy_global_id),
                "policyVersion": policy_version,
                "policySnapshotHash": policy_snapshot_hash,
                "engineeringBomKey": engineering_bom_key,
                "title": title,
                "reason": reason,
                "effectivityNote": effectivity_note,
                "lines": [dict(value) for value in lines],
            }
            payload_hash = self._command_payload_hash(
                operation="ebom.create",
                project=project,
                ebom_id=None,
                payload=payload,
            )
        with ebom_create_server_step("P504_CREATE_IDEMPOTENCY_REPLAY"):
            replay = self._receipt_replay(
                project,
                operation="ebom.create",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
            )
        if replay is not None:
            return DocumentCommandOutcome(replay, replayed=True)
        with ebom_create_server_step("P504_CREATE_PROJECT_MUTABILITY"):
            require_mutable_project(project)
        with ebom_create_server_step("P504_CREATE_DOMAIN_BUILD"):
            now = datetime.now(UTC)
            ebom_id = uuid4()
            revision = create_engineering_bom_revision(
                global_id=uuid4(),
                ebom_global_id=ebom_id,
                tenant_id=str(project.tenant_id),
                project_global_id=project_id,
                engineering_bom_key=engineering_bom_key,
                revision_number=1,
                predecessor=None,
                reason=reason,
                effectivity_note=effectivity_note,
                policy=policy,
                lines=self._input_lines(lines),
                actor=self.actor,
                now=now,
                request_id=self.request_id,
                trace_id=self.trace_id,
            )
        with ebom_create_server_step("P504_CREATE_TRANSACTION_SCOPE"):
            with ebom_command_write():
                with ebom_create_server_step("P504_CREATE_RECEIPT_INSERT"):
                    receipt = self._insert_receipt(
                        project,
                        operation="ebom.create",
                        idempotency_key_hash=idempotency_key_hash,
                        payload_hash=payload_hash,
                        now=now,
                    )
                with ebom_create_server_step("P504_CREATE_ROOT_INSERT"):
                    try:
                        root = frappe.get_doc(
                            {
                                "doctype": "NPI Engineering BOM",
                                "global_id": str(ebom_id),
                                "tenant_id": str(project.tenant_id),
                                "project_global_id": str(project.global_id),
                                "engineering_bom_key": engineering_bom_key,
                                "title": title,
                                "policy_global_id": str(policy.policy_global_id),
                                "policy_version": policy.policy_version,
                                "policy_snapshot_hash": policy.snapshot_hash,
                                "optimistic_version": 1,
                            }
                        ).insert()
                    except (
                        frappe.UniqueValidationError,
                        frappe.DuplicateEntryError,
                    ) as error:
                        raise EngineeringBomIdentityConflict() from error
                self._insert_revision_bundle(project, root, revision, now=now)
                with ebom_create_server_step(
                    "P504_CREATE_ROOT_PROJECTION_SAVE"
                ):
                    root.latest_revision_global_id = str(revision.global_id)
                    root.latest_revision_number = revision.revision_number
                    root.latest_revision_snapshot_hash = revision.snapshot_hash
                    root.save()
                with ebom_create_server_step("P504_CREATE_AUDIT_APPEND"):
                    self._append_audit(
                        operation="ebom.create",
                        global_id=ebom_id,
                        object_version=int(root.optimistic_version),
                        result="created",
                        summary={
                            "revisionGlobalId": str(revision.global_id),
                            "revisionSnapshotHash": revision.snapshot_hash,
                            "policySnapshotHash": policy.snapshot_hash,
                        },
                    )
                with ebom_create_server_step("P504_CREATE_RESPONSE_BUILD"):
                    response = self._command_result(project, root, revision)
                with ebom_create_server_step("P504_CREATE_RECEIPT_SEAL"):
                    self._seal_receipt(
                        receipt,
                        ebom_id=ebom_id,
                        revision_id=revision.global_id,
                        response=response,
                        now=now,
                    )
        return DocumentCommandOutcome(response)

    def create_revision(
        self,
        project_id: UUID,
        ebom_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_ebom_version: int,
        predecessor_revision_id: UUID,
        expected_predecessor_snapshot_hash: str,
        policy_global_id: UUID,
        policy_version: int,
        policy_snapshot_hash: str,
        reason: str,
        effectivity_note: str | None,
        lines: Sequence[Mapping[str, object]],
    ) -> DocumentCommandOutcome | None:
        context = self._locked_command_context(project_id, ebom_id)
        if context is None:
            return None
        project, root = context
        policy = self._load_exact_policy(
            project,
            policy_global_id=policy_global_id,
            policy_version=policy_version,
            snapshot_hash=policy_snapshot_hash,
            lock=True,
        )
        self._require_policy_actor(policy, "create")
        self._require_root_policy(root, policy)
        payload = {
            "expectedEbomVersion": expected_ebom_version,
            "predecessorRevisionId": str(predecessor_revision_id),
            "expectedPredecessorSnapshotHash": expected_predecessor_snapshot_hash,
            "policyGlobalId": str(policy_global_id),
            "policyVersion": policy_version,
            "policySnapshotHash": policy_snapshot_hash,
            "reason": reason,
            "effectivityNote": effectivity_note,
            "lines": [dict(value) for value in lines],
        }
        payload_hash = self._command_payload_hash(
            operation="ebom.revise",
            project=project,
            ebom_id=ebom_id,
            payload=payload,
        )
        replay = self._receipt_replay(
            project,
            operation="ebom.revise",
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
        )
        if replay is not None:
            return DocumentCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        self._require_root_version(root, expected_ebom_version)
        if (
            str(root.latest_revision_global_id or "") != str(predecessor_revision_id)
            or str(root.latest_revision_snapshot_hash or "")
            != expected_predecessor_snapshot_hash
        ):
            raise EngineeringBomStateConflict()
        predecessor_row = self._revision_for_root(
            project,
            root,
            predecessor_revision_id,
            lock=True,
        )
        if predecessor_row is None:
            raise EngineeringBomStateConflict()
        predecessor = self._revision_value(predecessor_row)
        now = datetime.now(UTC)
        revision = create_engineering_bom_revision(
            global_id=uuid4(),
            ebom_global_id=ebom_id,
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            engineering_bom_key=str(root.engineering_bom_key),
            revision_number=int(root.latest_revision_number) + 1,
            predecessor=predecessor,
            reason=reason,
            effectivity_note=effectivity_note,
            policy=policy,
            lines=self._input_lines(lines),
            actor=self.actor,
            now=now,
            request_id=self.request_id,
            trace_id=self.trace_id,
        )
        with ebom_command_write():
            receipt = self._insert_receipt(
                project,
                operation="ebom.revise",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._insert_revision_bundle(project, root, revision, now=now)
            root.latest_revision_global_id = str(revision.global_id)
            root.latest_revision_number = revision.revision_number
            root.latest_revision_snapshot_hash = revision.snapshot_hash
            root.save()
            self._append_audit(
                operation="ebom.revise",
                global_id=ebom_id,
                object_version=int(root.optimistic_version),
                result="created",
                summary={
                    "revisionGlobalId": str(revision.global_id),
                    "predecessorRevisionId": str(predecessor.global_id),
                    "revisionSnapshotHash": revision.snapshot_hash,
                },
            )
            response = self._command_result(project, root, revision)
            self._seal_receipt(
                receipt,
                ebom_id=ebom_id,
                revision_id=revision.global_id,
                response=response,
                now=now,
            )
        return DocumentCommandOutcome(response)

    def submit_review(self, project_id: UUID, ebom_id: UUID, revision_id: UUID, **values: Any):
        return self._transition(
            project_id,
            ebom_id,
            revision_id,
            action="submit_review",
            operation="ebom.submit_review",
            **values,
        )

    def review(self, project_id: UUID, ebom_id: UUID, revision_id: UUID, **values: Any):
        return self._transition(
            project_id,
            ebom_id,
            revision_id,
            action="review",
            operation="ebom.review",
            **values,
        )

    def release(self, project_id: UUID, ebom_id: UUID, revision_id: UUID, **values: Any):
        return self._transition(
            project_id,
            ebom_id,
            revision_id,
            action="release",
            operation="ebom.release",
            **values,
        )

    def compare(
        self,
        project_id: UUID,
        ebom_id: UUID,
        *,
        from_revision_id: UUID,
        to_revision_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        root = self._ebom_for_project(project, ebom_id, lock=False)
        if root is None:
            return None
        before_row = self._revision_for_root(
            project,
            root,
            from_revision_id,
            lock=False,
        )
        after_row = self._revision_for_root(
            project,
            root,
            to_revision_id,
            lock=False,
        )
        if before_row is None or after_row is None:
            return None
        before = self._revision_value(before_row)
        after = self._revision_value(after_row)
        differences = compare_engineering_bom_revisions(before, after)
        counts = Counter(value.change_type.value for value in differences)
        return {
            "ebom": self._ebom_summary(root),
            "fromRevision": self._revision_reference(before),
            "toRevision": self._revision_reference(after),
            "identical": not differences,
            "summary": {
                "added": counts["added"],
                "removed": counts["removed"],
                "quantity": counts["quantity"],
                "substitution": counts["substitution"],
                "attribute": counts["attribute"],
            },
            "changes": [
                {
                    "lineKey": value.line_key,
                    "changeType": value.change_type.value,
                    "changedFields": list(value.changed_fields),
                    "before": dict(value.before) if value.before is not None else None,
                    "after": dict(value.after) if value.after is not None else None,
                }
                for value in differences
            ],
        }

    def _transition(
        self,
        project_id: UUID,
        ebom_id: UUID,
        revision_id: UUID,
        *,
        action: str,
        operation: str,
        idempotency_key_hash: str,
        expected_ebom_version: int,
        expected_revision_snapshot_hash: str,
        expected_lifecycle_version: int,
        policy_global_id: UUID,
        policy_version: int,
        policy_snapshot_hash: str,
        decision: EngineeringBomReviewDecision | None = None,
        reason: str | None = None,
        confirmed: bool = False,
        confirmation_intent: str | None = None,
    ) -> DocumentCommandOutcome | None:
        context = self._locked_command_context(project_id, ebom_id)
        if context is None:
            return None
        project, root = context
        policy = self._load_exact_policy(
            project,
            policy_global_id=policy_global_id,
            policy_version=policy_version,
            snapshot_hash=policy_snapshot_hash,
            lock=True,
        )
        self._require_policy_actor(policy, action)
        self._require_root_policy(root, policy)
        payload = {
            "expectedEbomVersion": expected_ebom_version,
            "expectedRevisionSnapshotHash": expected_revision_snapshot_hash,
            "expectedLifecycleVersion": expected_lifecycle_version,
            "policyGlobalId": str(policy_global_id),
            "policyVersion": policy_version,
            "policySnapshotHash": policy_snapshot_hash,
            "decision": decision.value if decision is not None else None,
            "reason": reason,
            "confirmed": confirmed,
            "confirmationIntent": confirmation_intent,
            "revisionId": str(revision_id),
        }
        payload_hash = self._command_payload_hash(
            operation=operation,
            project=project,
            ebom_id=ebom_id,
            payload=payload,
        )
        replay = self._receipt_replay(
            project,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
        )
        if replay is not None:
            return DocumentCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        self._require_root_version(root, expected_ebom_version)
        revision_row = self._revision_for_root(
            project,
            root,
            revision_id,
            lock=True,
        )
        if revision_row is None:
            return None
        revision = self._revision_value(revision_row)
        if revision.snapshot_hash != expected_revision_snapshot_hash:
            raise EngineeringBomStateConflict()
        lifecycle_row = self._lifecycle_for_revision(
            project,
            root,
            revision,
            lock=True,
        )
        lifecycle = self._lifecycle_value(lifecycle_row)
        if lifecycle.lifecycle_version != expected_lifecycle_version:
            raise EngineeringBomStateConflict()
        now = datetime.now(UTC)
        transition = transition_engineering_bom(
            lifecycle=lifecycle,
            policy=policy,
            actor=self.actor,
            event_global_id=uuid4(),
            now=now,
            request_id=self.request_id,
            trace_id=self.trace_id,
            expected_version=expected_lifecycle_version,
            action=action,
            decision=decision,
            reason=reason,
            confirmed=confirmed,
            confirmation_intent=confirmation_intent,
        )
        with ebom_lifecycle_write():
            receipt = self._insert_receipt(
                project,
                operation=operation,
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            event = transition.event
            frappe.get_doc(
                {
                    "doctype": "NPI EBOM Lifecycle Event",
                    "global_id": str(event.global_id),
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "engineering_bom": str(root.global_id),
                    "ebom_global_id": str(root.global_id),
                    "engineering_bom_revision": str(revision.global_id),
                    "revision_global_id": str(revision.global_id),
                    "revision_snapshot_hash": revision.snapshot_hash,
                    "policy_global_id": str(policy.policy_global_id),
                    "policy_version": policy.policy_version,
                    "policy_snapshot_hash": policy.snapshot_hash,
                    "event_type": event.event_type.value,
                    "from_state": event.from_state.value,
                    "to_state": event.to_state.value,
                    "from_version": event.from_version,
                    "to_version": event.to_version,
                    "actor_user_id": event.actor_user_id,
                    "authority_action": event.authority_action,
                    "decision": event.decision.value if event.decision else None,
                    "reason": event.reason,
                    "confirmation_intent": event.confirmation_intent,
                    "occurred_at": _database_datetime(event.occurred_at),
                    "request_id": event.request_id,
                    "trace_id": event.trace_id,
                    "event_snapshot": event.event_payload(),
                    "event_hash": event.event_hash,
                }
            ).insert()
            lifecycle_row.current_state = transition.lifecycle.current_state.value
            lifecycle_row.lifecycle_version = transition.lifecycle.lifecycle_version
            lifecycle_row.last_event_global_id = str(event.global_id)
            lifecycle_row.updated_by_user_id = self.actor
            lifecycle_row.updated_at = _database_datetime(now)
            lifecycle_row.request_id = self.request_id
            lifecycle_row.trace_id = self.trace_id
            lifecycle_row.save()
            self._append_audit(
                operation=operation,
                global_id=revision.global_id,
                object_version=transition.lifecycle.lifecycle_version,
                result=transition.lifecycle.current_state.value,
                summary={
                    "ebomGlobalId": str(ebom_id),
                    "revisionSnapshotHash": revision.snapshot_hash,
                    "eventHash": event.event_hash,
                },
            )
            response = self._command_result(project, root, revision)
            self._seal_receipt(
                receipt,
                ebom_id=ebom_id,
                revision_id=revision.global_id,
                response=response,
                now=now,
            )
        return DocumentCommandOutcome(response)

    def _locked_command_project(self, project_id: UUID):
        try:
            project = frappe.get_doc(
                "NPI Engineering Project",
                str(project_id),
                for_update=True,
            )
        except frappe.DoesNotExistError:
            return None
        if not self._can_view_project(project, project_id):
            return None
        if self._current_actor_member(project) is None:
            return None
        return project

    def _locked_command_context(self, project_id: UUID, ebom_id: UUID):
        project = self._locked_command_project(project_id)
        if project is None:
            return None
        root = self._ebom_for_project(project, ebom_id, lock=True)
        return None if root is None else (project, root)

    @staticmethod
    def _ebom_for_project(project, ebom_id: UUID, *, lock: bool):
        try:
            root = frappe.get_doc(
                "NPI Engineering BOM",
                str(ebom_id),
                for_update=True,
            ) if lock else frappe.get_doc("NPI Engineering BOM", str(ebom_id))
        except frappe.DoesNotExistError:
            return None
        return root if (
            str(root.global_id) == str(ebom_id)
            and str(root.tenant_id) == str(project.tenant_id)
            and str(root.project_global_id) == str(project.global_id)
        ) else None

    @staticmethod
    def _revision_for_root(project, root, revision_id: UUID, *, lock: bool):
        try:
            row = frappe.get_doc(
                "NPI Engineering BOM Revision",
                str(revision_id),
                for_update=True,
            ) if lock else frappe.get_doc("NPI Engineering BOM Revision", str(revision_id))
        except frappe.DoesNotExistError:
            return None
        return row if (
            str(row.global_id) == str(revision_id)
            and str(row.ebom_global_id) == str(root.global_id)
            and str(row.tenant_id) == str(project.tenant_id)
            and str(row.project_global_id) == str(project.global_id)
        ) else None

    @staticmethod
    def _lifecycle_for_revision(project, root, revision: EngineeringBomRevision, *, lock: bool):
        try:
            row = frappe.get_doc(
                "NPI EBOM Revision Lifecycle",
                str(revision.global_id),
                for_update=True,
            ) if lock else frappe.get_doc(
                "NPI EBOM Revision Lifecycle",
                str(revision.global_id),
            )
        except frappe.DoesNotExistError as error:
            raise RuntimeError("Persisted EBOM lifecycle is unavailable.") from error
        if (
            str(row.global_id) != str(revision.global_id)
            or str(row.ebom_global_id) != str(root.global_id)
            or str(row.tenant_id) != str(project.tenant_id)
            or str(row.project_global_id) != str(project.global_id)
            or str(row.revision_snapshot_hash) != revision.snapshot_hash
        ):
            raise RuntimeError("Persisted EBOM lifecycle scope is invalid.")
        return row

    def _published_policy_options(self, project) -> tuple[dict[str, Any], ...]:
        if (
            self.principal.is_external
            or "NPI API User" not in self.principal.roles
            or self._current_actor_member(project) is None
        ):
            return ()
        rows = self._bounded_documents(
            "NPI EBOM Policy Version",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "publication_state": EngineeringBomPolicyState.PUBLISHED.value,
            },
            order_by="policy_key asc, policy_version desc, global_id asc",
            maximum=_MAX_POLICIES,
        )
        options = []
        for row in rows:
            try:
                policy = self._load_exact_policy(
                    project,
                    policy_global_id=UUID(str(row.policy_global_id)),
                    policy_version=int(row.policy_version),
                    snapshot_hash=str(row.snapshot_hash),
                    lock=False,
                )
            except EngineeringBomPolicyUnavailable:
                continue
            if policy.permits("create", self.actor):
                options.append(self._policy_response(policy))
        return tuple(options)

    @staticmethod
    def _load_exact_policy(
        project,
        *,
        policy_global_id: UUID,
        policy_version: int,
        snapshot_hash: str,
        lock: bool,
    ) -> EngineeringBomPolicyVersion:
        try:
            root = frappe.get_doc(
                "NPI EBOM Policy",
                str(policy_global_id),
                for_update=True,
            ) if lock else frappe.get_doc("NPI EBOM Policy", str(policy_global_id))
            version_name = frappe.db.get_value(
                "NPI EBOM Policy Version",
                {
                    "policy_global_id": str(policy_global_id),
                    "policy_version": policy_version,
                },
                "name",
            )
            if not version_name:
                raise EngineeringBomPolicyUnavailable()
            row = frappe.get_doc(
                "NPI EBOM Policy Version",
                str(version_name),
                for_update=True,
            ) if lock else frappe.get_doc("NPI EBOM Policy Version", str(version_name))
            policy = ebom_policy_value(row)
        except (
            frappe.DoesNotExistError,
            RequestValidationFailed,
            TypeError,
            ValueError,
        ) as error:
            raise EngineeringBomPolicyUnavailable() from error
        if (
            str(root.global_id) != str(policy_global_id)
            or str(root.tenant_id) != str(project.tenant_id)
            or str(root.project_global_id) != str(project.global_id)
            or int(root.enabled or 0) != 1
            or str(root.policy_key) != policy.policy_key
            or str(row.ebom_policy) != str(root.global_id)
            or policy.state is not EngineeringBomPolicyState.PUBLISHED
            or policy.policy_global_id != policy_global_id
            or policy.policy_version != policy_version
            or policy.snapshot_hash != snapshot_hash
            or policy.tenant_id != str(project.tenant_id)
            or policy.project_global_id != UUID(str(project.global_id))
        ):
            raise EngineeringBomPolicyUnavailable()
        return policy

    def _require_policy_actor(self, policy: EngineeringBomPolicyVersion, action: str) -> None:
        if not policy.permits(action, self.actor):
            raise EngineeringBomAuthorityUnavailable()

    @staticmethod
    def _require_root_policy(root, policy: EngineeringBomPolicyVersion) -> None:
        if (
            str(root.policy_global_id) != str(policy.policy_global_id)
            or int(root.policy_version) != policy.policy_version
            or str(root.policy_snapshot_hash) != policy.snapshot_hash
        ):
            raise EngineeringBomPolicyUnavailable()

    @staticmethod
    def _require_root_version(root, expected: int) -> None:
        if int(root.optimistic_version) != expected:
            raise EngineeringBomStateConflict()

    @staticmethod
    def _input_lines(values: Sequence[Mapping[str, object]]) -> tuple[EngineeringBomLine, ...]:
        return tuple(
            EngineeringBomLine(
                global_id=uuid4(),
                line_key=value["lineKey"],
                parent_line_key=value.get("parentLineKey"),
                engineering_item_id=value["engineeringItemId"],
                description=value["description"],
                quantity=Decimal(str(value["quantity"])),
                engineering_uom=value["engineeringUom"],
                alternate_for_line_key=value.get("alternateForLineKey"),
                alternate_group_key=value.get("alternateGroupKey"),
                effectivity_start=FrappeEngineeringBomRepository._input_date(
                    value.get("effectivityStart")
                ),
                effectivity_end=FrappeEngineeringBomRepository._input_date(
                    value.get("effectivityEnd")
                ),
                attributes=tuple(
                    (str(key), str(item))
                    for key, item in sorted(
                        dict(value.get("attributes") or {}).items(),
                        key=lambda pair: str(pair[0]),
                    )
                ),
            )
            for value in values
        )

    @staticmethod
    def _input_date(value: object) -> date | None:
        if value in (None, ""):
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        return date.fromisoformat(str(value))

    @staticmethod
    def _insert_revision_bundle(project, root, revision: EngineeringBomRevision, *, now: datetime) -> None:
        with ebom_create_server_step("P504_CREATE_REVISION_INSERT"):
            frappe.get_doc(
                {
                    "doctype": "NPI Engineering BOM Revision",
                    "global_id": str(revision.global_id),
                    "engineering_bom": str(root.global_id),
                    "ebom_global_id": str(root.global_id),
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "engineering_bom_key": revision.engineering_bom_key,
                    "revision_number": revision.revision_number,
                    "predecessor_global_id": (
                        str(revision.predecessor_global_id)
                        if revision.predecessor_global_id is not None
                        else None
                    ),
                    "predecessor_snapshot_hash": revision.predecessor_snapshot_hash,
                    "reason": revision.reason,
                    "effectivity_note": revision.effectivity_note,
                    "policy_global_id": str(revision.policy_ref.global_id),
                    "policy_version": revision.policy_ref.version,
                    "policy_snapshot_hash": revision.policy_ref.snapshot_hash,
                    "quantity_scale": revision.quantity_scale,
                    "line_count": len(revision.lines),
                    "revision_snapshot": revision.snapshot_payload(),
                    "snapshot_hash": revision.snapshot_hash,
                    "created_by_user_id": revision.created_by_user_id,
                    "created_at": _database_datetime(revision.created_at),
                    "request_id": revision.request_id,
                    "trace_id": revision.trace_id,
                }
            ).insert()
        with ebom_create_server_step("P504_CREATE_LINE_INSERT"):
            for line in revision.lines:
                line_snapshot = line.canonical_dict(revision.quantity_scale)
                frappe.get_doc(
                    {
                        "doctype": "NPI Engineering BOM Line",
                        "global_id": str(line.global_id),
                        "line_identity_key": (
                            f"{revision.global_id}:{line.line_key.casefold()}"
                        ),
                        "engineering_bom": str(root.global_id),
                        "ebom_global_id": str(root.global_id),
                        "engineering_bom_revision": str(revision.global_id),
                        "revision_global_id": str(revision.global_id),
                        "revision_snapshot_hash": revision.snapshot_hash,
                        "tenant_id": str(project.tenant_id),
                        "project_global_id": str(project.global_id),
                        "line_key": line.line_key,
                        "parent_line_key": line.parent_line_key,
                        "engineering_item_id": line.engineering_item_id,
                        "description": line.description,
                        "quantity": line_snapshot["quantity"],
                        "engineering_uom": line.engineering_uom,
                        "alternate_for_line_key": line.alternate_for_line_key,
                        "alternate_group_key": line.alternate_group_key,
                        "effectivity_start": line.effectivity_start,
                        "effectivity_end": line.effectivity_end,
                        "attributes": dict(line.attributes),
                        "line_snapshot": line_snapshot,
                        "line_hash": sha256_json(line_snapshot),
                        "created_at": _database_datetime(revision.created_at),
                    }
                ).insert()
        with ebom_create_server_step("P504_CREATE_LIFECYCLE_INSERT"):
            with ebom_lifecycle_write():
                frappe.get_doc(
                    {
                        "doctype": "NPI EBOM Revision Lifecycle",
                        "global_id": str(revision.global_id),
                        "tenant_id": str(project.tenant_id),
                        "project_global_id": str(project.global_id),
                        "engineering_bom": str(root.global_id),
                        "ebom_global_id": str(root.global_id),
                        "engineering_bom_revision": str(revision.global_id),
                        "revision_global_id": str(revision.global_id),
                        "revision_snapshot_hash": revision.snapshot_hash,
                        "current_state": (
                            EngineeringBomLifecycleState.DRAFT.value
                        ),
                        "lifecycle_version": 1,
                        "updated_by_user_id": revision.created_by_user_id,
                        "updated_at": _database_datetime(now),
                        "request_id": revision.request_id,
                        "trace_id": revision.trace_id,
                    }
                ).insert()

    def _command_payload_hash(self, *, operation: str, project, ebom_id: UUID | None, payload: Mapping[str, object]) -> str:
        return command_payload_hash(
            operation=operation,
            actor=self.actor,
            tenant_id=str(project.tenant_id),
            project_id=UUID(str(project.global_id)),
            document_id=ebom_id,
            payload=payload,
        )

    def _receipt_replay(
        self,
        project,
        *,
        operation: str,
        idempotency_key_hash: str,
        payload_hash: str,
    ) -> dict[str, Any] | None:
        receipt_key = self._receipt_key(project, operation, idempotency_key_hash)
        row = frappe.db.get_value(
            "NPI EBOM Command Idempotency",
            {"receipt_key": receipt_key},
            [
                "tenant_id",
                "project_global_id",
                "actor_user_id",
                "operation",
                "idempotency_key_hash",
                "payload_hash",
                "response_payload",
                "response_hash",
                "sealed",
            ],
            as_dict=True,
            for_update=True,
        )
        if not row:
            return None
        if (
            str(_record_value(row, "tenant_id")) != str(project.tenant_id)
            or str(_record_value(row, "project_global_id")) != str(project.global_id)
            or str(_record_value(row, "actor_user_id")) != self.actor
            or str(_record_value(row, "operation")) != operation
            or str(_record_value(row, "idempotency_key_hash")) != idempotency_key_hash
            or str(_record_value(row, "payload_hash")) != payload_hash
        ):
            raise EngineeringBomIdempotencyConflict()
        response = _json_object(_record_value(row, "response_payload"))
        if (
            int(_record_value(row, "sealed") or 0) != 1
            or not response
            or str(_record_value(row, "response_hash")) != sha256_json(response)
        ):
            raise RuntimeError("Persisted EBOM command response is unsealed or invalid.")
        return response

    def _insert_receipt(self, project, *, operation: str, idempotency_key_hash: str, payload_hash: str, now: datetime):
        try:
            return frappe.get_doc(
                {
                    "doctype": "NPI EBOM Command Idempotency",
                    "global_id": str(uuid4()),
                    "receipt_key": self._receipt_key(project, operation, idempotency_key_hash),
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "actor_user_id": self.actor,
                    "operation": operation,
                    "idempotency_key_hash": idempotency_key_hash,
                    "payload_hash": payload_hash,
                    "response_payload": {},
                    "sealed": 0,
                    "created_at": _database_datetime(now),
                    "updated_at": _database_datetime(now),
                }
            ).insert()
        except (frappe.UniqueValidationError, frappe.DuplicateEntryError) as error:
            raise EngineeringBomIdempotencyConflict() from error

    def _receipt_key(self, project, operation: str, idempotency_key_hash: str) -> str:
        return sha256_json(
            {
                "tenantId": str(project.tenant_id),
                "projectGlobalId": str(project.global_id),
                "actorUserId": self.actor.casefold(),
                "operation": operation,
                "idempotencyKeyHash": idempotency_key_hash,
            }
        )

    @staticmethod
    def _seal_receipt(receipt, *, ebom_id: UUID, revision_id: UUID, response: Mapping[str, object], now: datetime) -> None:
        receipt.ebom_global_id = str(ebom_id)
        receipt.revision_global_id = str(revision_id)
        receipt.response_payload = dict(response)
        receipt.response_hash = sha256_json(response)
        receipt.sealed = 1
        receipt.updated_at = _database_datetime(now)
        receipt.save()

    def _detail_response(self, project, root) -> dict[str, Any]:
        revision_rows = self._bounded_documents(
            "NPI Engineering BOM Revision",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "ebom_global_id": str(root.global_id),
            },
            order_by="revision_number desc, global_id asc",
            maximum=_MAX_REVISIONS,
        )
        revisions = [self._revision_value(row) for row in revision_rows]
        policy = self._load_exact_policy(
            project,
            policy_global_id=UUID(str(root.policy_global_id)),
            policy_version=int(root.policy_version),
            snapshot_hash=str(root.policy_snapshot_hash),
            lock=False,
        )
        return {
            "project": _project_response(project),
            "permissions": {"view": True, "create": bool(self._published_policy_options(project))},
            "policy": self._policy_response(policy),
            "ebom": self._ebom_summary(root),
            "revisions": [self._revision_response(project, root, value) for value in revisions],
        }

    def _command_result(self, project, root, revision: EngineeringBomRevision) -> dict[str, Any]:
        return {
            "ebom": self._ebom_summary(root),
            "revision": self._revision_response(project, root, revision),
        }

    def _revision_response(self, project, root, revision: EngineeringBomRevision) -> dict[str, Any]:
        lifecycle_row = self._lifecycle_for_revision(project, root, revision, lock=False)
        lifecycle = self._lifecycle_value(lifecycle_row)
        events = self._bounded_documents(
            "NPI EBOM Lifecycle Event",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "ebom_global_id": str(root.global_id),
                "revision_global_id": str(revision.global_id),
            },
            order_by="to_version asc, global_id asc",
            maximum=_MAX_EVENTS,
        )
        policy = self._load_exact_policy(
            project,
            policy_global_id=revision.policy_ref.global_id,
            policy_version=revision.policy_ref.version,
            snapshot_hash=revision.policy_ref.snapshot_hash,
            lock=False,
        )
        return {
            **self._revision_reference(revision),
            "predecessorRevisionId": (
                str(revision.predecessor_global_id) if revision.predecessor_global_id else None
            ),
            "predecessorSnapshotHash": revision.predecessor_snapshot_hash,
            "reason": revision.reason,
            "effectivityNote": revision.effectivity_note,
            "policy": revision.policy_ref.canonical_dict(),
            "quantityScale": revision.quantity_scale,
            "lines": [line.canonical_dict(revision.quantity_scale) for line in revision.lines],
            "createdByUserId": revision.created_by_user_id,
            "createdAt": _datetime_iso(revision.created_at),
            "lifecycle": {
                "state": lifecycle.current_state.value,
                "version": lifecycle.lifecycle_version,
                "lastEventId": str(lifecycle.last_event_global_id) if lifecycle.last_event_global_id else None,
            },
            "events": [self._event_response(row) for row in events],
            "capabilities": {
                "revise": (
                    str(root.latest_revision_global_id) == str(revision.global_id)
                    and policy.permits("create", self.actor)
                ),
                "submitReview": lifecycle.current_state is EngineeringBomLifecycleState.DRAFT and policy.permits("submit_review", self.actor),
                "review": lifecycle.current_state is EngineeringBomLifecycleState.IN_REVIEW and policy.permits("review", self.actor),
                "release": lifecycle.current_state is EngineeringBomLifecycleState.APPROVED and policy.permits("release", self.actor),
                "compare": True,
            },
        }

    @staticmethod
    def _policy_response(policy: EngineeringBomPolicyVersion) -> dict[str, Any]:
        return {
            "globalId": str(policy.policy_global_id),
            "version": policy.policy_version,
            "snapshotHash": policy.snapshot_hash,
            "key": policy.policy_key,
            "title": policy.title,
            "syntheticNamespace": policy.synthetic_namespace,
            "quantityScale": policy.quantity_scale,
            "maximumNodes": policy.maximum_nodes,
            "engineeringUoms": list(policy.engineering_uoms),
            "attributeKeys": list(policy.attribute_keys),
        }

    @staticmethod
    def _ebom_summary(root) -> dict[str, Any]:
        return {
            "globalId": str(root.global_id),
            "engineeringBomKey": str(root.engineering_bom_key),
            "title": str(root.title),
            "policy": {
                "globalId": str(root.policy_global_id),
                "version": int(root.policy_version),
                "snapshotHash": str(root.policy_snapshot_hash),
            },
            "optimisticVersion": int(root.optimistic_version),
            "latestRevision": (
                {
                    "globalId": str(root.latest_revision_global_id),
                    "revisionNumber": int(root.latest_revision_number),
                    "snapshotHash": str(root.latest_revision_snapshot_hash),
                }
                if root.latest_revision_global_id else None
            ),
        }

    @staticmethod
    def _revision_reference(revision: EngineeringBomRevision) -> dict[str, Any]:
        return {
            "globalId": str(revision.global_id),
            "revisionNumber": revision.revision_number,
            "snapshotHash": revision.snapshot_hash,
        }

    @staticmethod
    def _lifecycle_value(row) -> EngineeringBomRevisionLifecycle:
        try:
            state = EngineeringBomLifecycleState(str(row.current_state))
        except ValueError as error:
            raise RuntimeError("Persisted EBOM lifecycle state is invalid.") from error
        return EngineeringBomRevisionLifecycle(
            revision_global_id=UUID(str(row.revision_global_id)),
            revision_snapshot_hash=str(row.revision_snapshot_hash),
            current_state=state,
            lifecycle_version=int(row.lifecycle_version),
            last_event_global_id=(
                UUID(str(row.last_event_global_id)) if row.last_event_global_id else None
            ),
        )

    @staticmethod
    def _event_response(row) -> dict[str, Any]:
        event = FrappeEngineeringBomRepository._event_value(row)
        return {
            "globalId": str(event.global_id),
            "eventType": event.event_type.value,
            "fromState": event.from_state.value,
            "toState": event.to_state.value,
            "fromVersion": event.from_version,
            "toVersion": event.to_version,
            "actorUserId": event.actor_user_id,
            "decision": event.decision.value if event.decision else None,
            "reason": event.reason,
            "confirmationIntent": event.confirmation_intent,
            "occurredAt": _datetime_iso(event.occurred_at),
            "eventHash": event.event_hash,
        }

    @staticmethod
    def _event_value(row) -> EngineeringBomLifecycleEvent:
        snapshot = _json_object(row.event_snapshot)
        expected = {
            "schemaVersion",
            "globalId",
            "revisionGlobalId",
            "revisionSnapshotHash",
            "policyRef",
            "eventType",
            "fromState",
            "toState",
            "fromVersion",
            "toVersion",
            "actorUserId",
            "authorityAction",
            "decision",
            "reason",
            "confirmationIntent",
            "occurredAt",
            "requestId",
            "traceId",
        }
        if set(snapshot) != expected:
            raise RuntimeError("Persisted EBOM lifecycle event snapshot is invalid.")
        policy = _json_object(snapshot["policyRef"])
        try:
            value = EngineeringBomLifecycleEvent(
                global_id=UUID(str(snapshot["globalId"])),
                revision_global_id=UUID(str(snapshot["revisionGlobalId"])),
                revision_snapshot_hash=str(snapshot["revisionSnapshotHash"]),
                policy_ref=EngineeringBomPolicyReference(
                    UUID(str(policy["globalId"])),
                    int(policy["version"]),
                    str(policy["snapshotHash"]),
                ),
                event_type=EngineeringBomEventType(str(snapshot["eventType"])),
                from_state=EngineeringBomLifecycleState(str(snapshot["fromState"])),
                to_state=EngineeringBomLifecycleState(str(snapshot["toState"])),
                from_version=int(snapshot["fromVersion"]),
                to_version=int(snapshot["toVersion"]),
                actor_user_id=str(snapshot["actorUserId"]),
                authority_action=str(snapshot["authorityAction"]),
                decision=(
                    EngineeringBomReviewDecision(str(snapshot["decision"]))
                    if snapshot["decision"] is not None
                    else None
                ),
                reason=(str(snapshot["reason"]) if snapshot["reason"] is not None else None),
                confirmation_intent=(
                    str(snapshot["confirmationIntent"])
                    if snapshot["confirmationIntent"] is not None
                    else None
                ),
                occurred_at=datetime.fromisoformat(
                    str(snapshot["occurredAt"]).replace("Z", "+00:00")
                ),
                request_id=str(snapshot["requestId"]),
                trace_id=str(snapshot["traceId"]),
                event_hash=str(row.event_hash),
            )
        except (RequestValidationFailed, TypeError, ValueError) as error:
            raise RuntimeError("Persisted EBOM lifecycle event is invalid.") from error
        if (
            snapshot != value.event_payload()
            or str(row.global_id) != str(value.global_id)
            or str(row.revision_global_id) != str(value.revision_global_id)
            or str(row.revision_snapshot_hash) != value.revision_snapshot_hash
            or str(row.event_type) != value.event_type.value
            or str(row.from_state) != value.from_state.value
            or str(row.to_state) != value.to_state.value
            or int(row.from_version) != value.from_version
            or int(row.to_version) != value.to_version
        ):
            raise RuntimeError("Persisted EBOM lifecycle event fields do not match.")
        return value

    @staticmethod
    def _revision_value(row) -> EngineeringBomRevision:
        snapshot = _json_object(row.revision_snapshot)
        expected = {
            "schemaVersion", "globalId", "ebomGlobalId", "tenantId",
            "projectGlobalId", "engineeringBomKey", "revisionNumber",
            "predecessorGlobalId", "predecessorSnapshotHash", "reason",
            "effectivityNote", "policyRef", "quantityScale", "lines",
            "createdByUserId", "createdAt", "requestId", "traceId",
        }
        if set(snapshot) != expected or not isinstance(snapshot.get("lines"), list):
            raise RuntimeError("Persisted EBOM revision snapshot is invalid.")
        policy = _json_object(snapshot["policyRef"])
        try:
            value = EngineeringBomRevision(
                global_id=UUID(str(snapshot["globalId"])),
                ebom_global_id=UUID(str(snapshot["ebomGlobalId"])),
                tenant_id=str(snapshot["tenantId"]),
                project_global_id=UUID(str(snapshot["projectGlobalId"])),
                engineering_bom_key=str(snapshot["engineeringBomKey"]),
                revision_number=int(snapshot["revisionNumber"]),
                predecessor_global_id=(UUID(str(snapshot["predecessorGlobalId"])) if snapshot["predecessorGlobalId"] else None),
                predecessor_snapshot_hash=(str(snapshot["predecessorSnapshotHash"]) if snapshot["predecessorSnapshotHash"] else None),
                reason=str(snapshot["reason"]),
                effectivity_note=(str(snapshot["effectivityNote"]) if snapshot["effectivityNote"] else None),
                policy_ref=EngineeringBomPolicyReference(
                    UUID(str(policy["globalId"])),
                    int(policy["version"]),
                    str(policy["snapshotHash"]),
                ),
                quantity_scale=int(snapshot["quantityScale"]),
                lines=tuple(ebom_line_value(item) for item in snapshot["lines"]),
                created_by_user_id=str(snapshot["createdByUserId"]),
                created_at=datetime.fromisoformat(str(snapshot["createdAt"]).replace("Z", "+00:00")),
                request_id=str(snapshot["requestId"]),
                trace_id=str(snapshot["traceId"]),
                snapshot_hash=str(row.snapshot_hash),
            )
        except (RequestValidationFailed, TypeError, ValueError) as error:
            raise RuntimeError("Persisted EBOM revision is invalid.") from error
        if (
            str(row.global_id) != str(value.global_id)
            or str(row.ebom_global_id) != str(value.ebom_global_id)
            or str(row.tenant_id) != value.tenant_id
            or str(row.project_global_id) != str(value.project_global_id)
            or int(row.revision_number) != value.revision_number
            or str(row.engineering_bom_key) != value.engineering_bom_key
            or (str(row.predecessor_global_id) if row.predecessor_global_id else None)
            != (
                str(value.predecessor_global_id)
                if value.predecessor_global_id is not None
                else None
            )
            or (str(row.predecessor_snapshot_hash) if row.predecessor_snapshot_hash else None)
            != value.predecessor_snapshot_hash
            or str(row.reason) != value.reason
            or (str(row.effectivity_note) if row.effectivity_note else None)
            != value.effectivity_note
            or str(row.policy_global_id) != str(value.policy_ref.global_id)
            or int(row.policy_version) != value.policy_ref.version
            or str(row.policy_snapshot_hash) != value.policy_ref.snapshot_hash
            or int(row.quantity_scale) != value.quantity_scale
            or int(row.line_count) != len(value.lines)
            or str(row.created_by_user_id) != value.created_by_user_id
            or _datetime_iso(row.created_at) != _datetime_iso(value.created_at)
            or str(row.request_id) != value.request_id
            or str(row.trace_id) != value.trace_id
            or snapshot != value.snapshot_payload()
        ):
            raise RuntimeError("Persisted EBOM revision fields do not match its snapshot.")
        return value

    @staticmethod
    def _bounded_documents(
        doctype: str,
        filters: Mapping[str, object],
        *,
        order_by: str,
        maximum: int,
    ) -> tuple[Any, ...]:
        names = frappe.get_all(
            doctype,
            filters=dict(filters),
            pluck="name",
            order_by=order_by,
            limit_page_length=maximum + 1,
        )
        if len(names) > maximum:
            raise RuntimeError(f"Persisted {doctype} collection exceeds its safe bound.")
        return tuple(frappe.get_doc(doctype, str(name)) for name in names)
