from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import frappe

from npi_core.documents.domain import command_payload_hash
from npi_core.documents.frappe_repository import (
    DocumentCommandOutcome,
    _database_datetime,
    _json_object,
    _project_response,
    _record_value,
)
from npi_core.ebom.domain import (
    EngineeringBomEventType,
    EngineeringBomLifecycleState,
)
from npi_core.ebom.frappe_repository import FrappeEngineeringBomRepository
from npi_core.foundation.errors import RequestValidationFailed
from npi_core.foundation.security import Principal
from npi_core.project_controls.terminal_guard import require_mutable_project
from npi_integration.publish_request.domain import (
    FutureRetryDirective,
    MappingObservation,
    PublishLineInput,
    PublishMappingState,
    PublishNodeOperation,
    PublishNodeResult,
    PublishNodeResultState,
    PublishPolicyReference,
    PublishRequest,
    PublishRequestAuthorityUnavailable,
    PublishRequestIdempotencyConflict,
    PublishRequestNode,
    PublishRequestPolicyUnavailable,
    PublishRequestState,
    PublishRequestStateConflict,
    PublishTargetMode,
    ReleasedEbomEvidence,
    TargetFaultKind,
    create_mock_publish_request,
    sha256_json,
)
from npi_integration.publish_request.frappe_validation import publish_request_write


_OPERATION = "ebom.publish_request.create"
_MAX_POLICIES = 64
_MAX_REQUESTS = 200
_MAX_NODES = 500
_MAX_RESULTS = 100
_MAX_EVENTS = 1_000


class FrappePublishRequestRepository(FrappeEngineeringBomRepository):
    """Project-authorized, Mock-only EBOM publish-request repository."""

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

    def list_requests(
        self,
        project_id: UUID,
        ebom_id: UUID,
        revision_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        policies = self._published_publish_policy_options(project)
        if not policies:
            return None
        context = self._released_context(
            project,
            ebom_id=ebom_id,
            revision_id=revision_id,
            lock=False,
        )
        if context is None:
            return None
        root, revision_row, revision, _lifecycle_row, _lifecycle, _release = context
        rows = self._bounded_documents(
            "NPI EBOM Publish Request",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "ebom_global_id": str(ebom_id),
                "revision_global_id": str(revision_id),
            },
            order_by="created_at desc, global_id asc",
            maximum=_MAX_REQUESTS,
        )
        items = []
        for row in rows:
            policy = self._load_exact_publish_policy(
                project,
                policy_global_id=UUID(str(row.publish_policy_global_id)),
                policy_version=int(row.publish_policy_version),
                snapshot_hash=str(row.publish_policy_snapshot_hash),
                lock=False,
            )
            if self._policy_permits(policy):
                items.append(self._request_value(project, row).public_dict())
        return self._list_response(
            project,
            root,
            revision,
            policies=policies,
            items=items,
        )

    def request_detail(
        self,
        project_id: UUID,
        ebom_id: UUID,
        revision_id: UUID,
        publish_request_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None or not self._published_publish_policy_options(project):
            return None
        context = self._released_context(
            project,
            ebom_id=ebom_id,
            revision_id=revision_id,
            lock=False,
        )
        if context is None:
            return None
        row = self._request_for_scope(
            project,
            ebom_id=ebom_id,
            revision_id=revision_id,
            request_id=publish_request_id,
        )
        if row is None:
            return None
        policy = self._load_exact_publish_policy(
            project,
            policy_global_id=UUID(str(row.publish_policy_global_id)),
            policy_version=int(row.publish_policy_version),
            snapshot_hash=str(row.publish_policy_snapshot_hash),
            lock=False,
        )
        if not self._policy_permits(policy):
            return None
        return self._request_value(project, row).public_dict()

    def create_request(
        self,
        project_id: UUID,
        ebom_id: UUID,
        revision_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_ebom_version: int,
        expected_revision_snapshot_hash: str,
        expected_lifecycle_version: int,
        publish_policy_global_id: UUID,
        publish_policy_version: int,
        publish_policy_snapshot_hash: str,
        reason: str,
    ) -> DocumentCommandOutcome | None:
        project = self._locked_command_project(project_id)
        if project is None:
            return None
        policy = self._load_exact_publish_policy(
            project,
            policy_global_id=publish_policy_global_id,
            policy_version=publish_policy_version,
            snapshot_hash=publish_policy_snapshot_hash,
            lock=True,
        )
        self._require_publish_policy_actor(policy)
        context = self._released_context(
            project,
            ebom_id=ebom_id,
            revision_id=revision_id,
            lock=True,
        )
        if context is None:
            return None
        root, _revision_row, revision, _lifecycle_row, lifecycle, release = context
        command_payload = {
            "ebomGlobalId": str(ebom_id),
            "revisionGlobalId": str(revision_id),
            "expectedEbomVersion": expected_ebom_version,
            "expectedRevisionSnapshotHash": expected_revision_snapshot_hash,
            "expectedLifecycleVersion": expected_lifecycle_version,
            "publishPolicyGlobalId": str(publish_policy_global_id),
            "publishPolicyVersion": publish_policy_version,
            "publishPolicySnapshotHash": publish_policy_snapshot_hash,
            "targetMode": "mock",
            "confirmed": True,
            "confirmationIntent": (
                "validate_exact_released_ebom_for_item_mbom_publish"
            ),
            "reason": reason,
        }
        command_hash = command_payload_hash(
            operation=_OPERATION,
            actor=self.actor,
            tenant_id=str(project.tenant_id),
            project_id=project_id,
            document_id=ebom_id,
            payload=command_payload,
        )
        replay = self._receipt_replay(
            project,
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=command_hash,
        )
        if replay is not None:
            return DocumentCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        if (
            int(root.optimistic_version) != expected_ebom_version
            or revision.snapshot_hash != expected_revision_snapshot_hash
            or lifecycle.lifecycle_version != expected_lifecycle_version
        ):
            raise PublishRequestStateConflict()

        evidence = ReleasedEbomEvidence(
            project_global_id=project_id,
            ebom_global_id=ebom_id,
            ebom_version=int(root.optimistic_version),
            revision_global_id=revision_id,
            revision_number=revision.revision_number,
            revision_snapshot_hash=revision.snapshot_hash,
            lifecycle_version=lifecycle.lifecycle_version,
            release_event_global_id=release.global_id,
            release_event_hash=release.event_hash,
            ebom_policy_global_id=revision.policy_ref.global_id,
            ebom_policy_version=revision.policy_ref.version,
            ebom_policy_snapshot_hash=revision.policy_ref.snapshot_hash,
            approval_evidence_ids=self._approval_evidence_ids(
                project,
                root,
                revision,
                release.global_id,
            ),
            released_at=release.occurred_at,
        )
        now = datetime.now(UTC)
        request = create_mock_publish_request(
            policy=PublishPolicyReference(
                publish_policy_global_id,
                publish_policy_version,
                publish_policy_snapshot_hash,
            ),
            evidence=evidence,
            lines=self._publish_lines(revision),
            actor_user_id=self.actor,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
            idempotency_key_hash=idempotency_key_hash,
            created_at=now,
        )
        with publish_request_write():
            receipt = self._insert_receipt(
                project,
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=command_hash,
                now=now,
            )
            self._insert_request_bundle(project, request, now=now)
            self._append_audit(
                operation=_OPERATION,
                global_id=request.global_id,
                object_version=1,
                result=request.state.value,
                summary={
                    "ebomGlobalId": str(ebom_id),
                    "revisionGlobalId": str(revision_id),
                    "revisionSnapshotHash": revision.snapshot_hash,
                    "publishPolicySnapshotHash": publish_policy_snapshot_hash,
                    "requestPayloadHash": request.payload_hash,
                    "nodeCount": len(request.nodes),
                    "targetMode": "mock",
                    "dispatchAllowed": False,
                    "reason": reason,
                },
            )
            response = request.public_dict()
            self._seal_receipt(
                receipt,
                request_id=request.global_id,
                response=response,
                now=now,
            )
        return DocumentCommandOutcome(response)

    def _released_context(
        self,
        project,
        *,
        ebom_id: UUID,
        revision_id: UUID,
        lock: bool,
    ):
        root = self._ebom_for_project(project, ebom_id, lock=lock)
        if root is None:
            return None
        revision_row = self._revision_for_root(
            project,
            root,
            revision_id,
            lock=lock,
        )
        if revision_row is None:
            return None
        revision = self._revision_value(revision_row)
        lifecycle_row = self._lifecycle_for_revision(
            project,
            root,
            revision,
            lock=lock,
        )
        lifecycle = self._lifecycle_value(lifecycle_row)
        if (
            lifecycle.current_state is not EngineeringBomLifecycleState.RELEASED
            or lifecycle.last_event_global_id is None
        ):
            return None
        try:
            release_row = (
                frappe.get_doc(
                    "NPI EBOM Lifecycle Event",
                    str(lifecycle.last_event_global_id),
                    for_update=True,
                )
                if lock
                else frappe.get_doc(
                    "NPI EBOM Lifecycle Event",
                    str(lifecycle.last_event_global_id),
                )
            )
        except frappe.DoesNotExistError:
            return None
        release = self._event_value(release_row)
        if (
            release.event_type is not EngineeringBomEventType.RELEASED
            or release.revision_global_id != revision_id
            or release.revision_snapshot_hash != revision.snapshot_hash
            or release.to_version != lifecycle.lifecycle_version
            or str(release_row.tenant_id) != str(project.tenant_id)
            or str(release_row.project_global_id) != str(project.global_id)
            or str(release_row.ebom_global_id) != str(root.global_id)
        ):
            return None
        return (
            root,
            revision_row,
            revision,
            lifecycle_row,
            lifecycle,
            release,
        )

    def _published_publish_policy_options(self, project) -> tuple[dict[str, Any], ...]:
        if (
            self.principal.is_external
            or "NPI API User" not in self.principal.roles
            or self._current_actor_member(project) is None
        ):
            return ()
        rows = self._bounded_documents(
            "NPI EBOM Publish Policy Version",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "publication_state": "published",
                "target_mode": "mock",
            },
            order_by="policy_key asc, policy_version desc, global_id asc",
            maximum=_MAX_POLICIES,
        )
        options = []
        for row in rows:
            try:
                policy = self._load_exact_publish_policy(
                    project,
                    policy_global_id=UUID(str(row.policy_global_id)),
                    policy_version=int(row.policy_version),
                    snapshot_hash=str(row.snapshot_hash),
                    lock=False,
                )
            except PublishRequestPolicyUnavailable:
                continue
            if self._policy_permits(policy):
                options.append(self._policy_option(policy))
        return tuple(options)

    @staticmethod
    def _load_exact_publish_policy(
        project,
        *,
        policy_global_id: UUID,
        policy_version: int,
        snapshot_hash: str,
        lock: bool,
    ) -> dict[str, Any]:
        try:
            root = (
                frappe.get_doc(
                    "NPI EBOM Publish Policy",
                    str(policy_global_id),
                    for_update=True,
                )
                if lock
                else frappe.get_doc(
                    "NPI EBOM Publish Policy",
                    str(policy_global_id),
                )
            )
            name = frappe.db.get_value(
                "NPI EBOM Publish Policy Version",
                {
                    "policy_global_id": str(policy_global_id),
                    "policy_version": policy_version,
                },
                "name",
            )
            if not name:
                raise PublishRequestPolicyUnavailable()
            row = (
                frappe.get_doc(
                    "NPI EBOM Publish Policy Version",
                    str(name),
                    for_update=True,
                )
                if lock
                else frappe.get_doc(
                    "NPI EBOM Publish Policy Version",
                    str(name),
                )
            )
            snapshot = _json_object(row.policy_snapshot)
            requesters = _json_array(row.requester_user_ids)
        except (
            frappe.DoesNotExistError,
            PublishRequestPolicyUnavailable,
            RequestValidationFailed,
            TypeError,
            ValueError,
        ) as error:
            if isinstance(error, PublishRequestPolicyUnavailable):
                raise
            raise PublishRequestPolicyUnavailable() from error
        expected = {
            "schemaVersion": 1,
            "globalId": str(row.global_id),
            "policyGlobalId": str(policy_global_id),
            "tenantId": str(project.tenant_id),
            "projectGlobalId": str(project.global_id),
            "policyKey": str(row.policy_key),
            "policyVersion": policy_version,
            "title": str(row.title),
            "publicationState": "published",
            "targetMode": "mock",
            "apiVersion": "npi.erp-publish.v1",
            "operation": "publish_released_ebom_item_mbom",
            "requesterUserIds": requesters,
        }
        if (
            str(root.global_id) != str(policy_global_id)
            or str(root.tenant_id) != str(project.tenant_id)
            or str(root.project_global_id) != str(project.global_id)
            or int(root.enabled or 0) != 1
            or str(root.policy_key) != str(row.policy_key)
            or str(row.publish_policy) != str(root.global_id)
            or str(row.policy_global_id) != str(policy_global_id)
            or int(row.policy_version) != policy_version
            or str(row.publication_state) != "published"
            or str(row.target_mode) != "mock"
            or str(row.api_version) != "npi.erp-publish.v1"
            or str(row.operation) != "publish_released_ebom_item_mbom"
            or str(row.snapshot_hash) != snapshot_hash
            or snapshot != expected
            or sha256_json(expected) != snapshot_hash
            or not requesters
            or len(requesters) > 100
            or len({item.casefold() for item in requesters}) != len(requesters)
        ):
            raise PublishRequestPolicyUnavailable()
        return {
            "global_id": policy_global_id,
            "version_global_id": UUID(str(row.global_id)),
            "version": policy_version,
            "snapshot_hash": snapshot_hash,
            "key": str(row.policy_key),
            "title": str(row.title),
            "requesters": tuple(requesters),
        }

    def _policy_permits(self, policy: Mapping[str, object]) -> bool:
        actor = self.actor.casefold()
        return any(
            str(value).casefold() == actor
            for value in policy.get("requesters", ())
        )

    def _require_publish_policy_actor(self, policy: Mapping[str, object]) -> None:
        if not self._policy_permits(policy):
            raise PublishRequestAuthorityUnavailable()

    @staticmethod
    def _policy_option(policy: Mapping[str, object]) -> dict[str, Any]:
        return {
            "globalId": str(policy["global_id"]),
            "version": int(policy["version"]),
            "snapshotHash": str(policy["snapshot_hash"]),
            "key": str(policy["key"]),
            "title": str(policy["title"]),
            "targetMode": "mock",
        }

    @staticmethod
    def _publish_lines(revision) -> tuple[PublishLineInput, ...]:
        values = []
        for line in revision.lines:
            snapshot = line.canonical_dict(revision.quantity_scale)
            values.append(
                PublishLineInput(
                    global_id=line.global_id,
                    line_key=line.line_key,
                    parent_line_key=line.parent_line_key,
                    engineering_item_id=line.engineering_item_id,
                    description=line.description,
                    quantity=str(snapshot["quantity"]),
                    engineering_uom=line.engineering_uom,
                    alternate_for_line_key=line.alternate_for_line_key,
                    alternate_group_key=line.alternate_group_key,
                    effectivity_start=snapshot["effectivityStart"],
                    effectivity_end=snapshot["effectivityEnd"],
                    attributes=tuple(line.attributes),
                    line_hash=sha256_json(snapshot),
                )
            )
        return tuple(values)

    def _approval_evidence_ids(
        self,
        project,
        root,
        revision,
        release_event_id: UUID,
    ) -> tuple[UUID, ...]:
        rows = self._bounded_documents(
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
        events = tuple(self._event_value(row) for row in rows)
        release = next(
            (event for event in events if event.global_id == release_event_id),
            None,
        )
        approvals = tuple(
            event
            for event in events
            if event.event_type is EngineeringBomEventType.REVIEW_APPROVED
            and release is not None
            and event.to_version < release.to_version
        )
        if release is None or not approvals:
            raise RuntimeError("Released EBOM approval evidence is incomplete.")
        return (approvals[-1].global_id, release_event_id)

    def _insert_receipt(
        self,
        project,
        *,
        idempotency_key_hash: str,
        payload_hash: str,
        now: datetime,
    ):
        try:
            return frappe.get_doc(
                {
                    "doctype": "NPI EBOM Publish Command Idempotency",
                    "global_id": str(uuid4()),
                    "receipt_key": self._receipt_key(
                        project,
                        self.actor,
                        idempotency_key_hash,
                    ),
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "actor_user_id": self.actor,
                    "operation": _OPERATION,
                    "idempotency_key_hash": idempotency_key_hash,
                    "payload_hash": payload_hash,
                    "sealed": 0,
                    "created_at": _database_datetime(now),
                    "updated_at": _database_datetime(now),
                }
            ).insert()
        except (frappe.UniqueValidationError, frappe.DuplicateEntryError) as error:
            raise PublishRequestIdempotencyConflict() from error

    def _receipt_replay(
        self,
        project,
        *,
        idempotency_key_hash: str,
        payload_hash: str,
    ) -> dict[str, Any] | None:
        row = frappe.db.get_value(
            "NPI EBOM Publish Command Idempotency",
            {
                "receipt_key": self._receipt_key(
                    project,
                    self.actor,
                    idempotency_key_hash,
                )
            },
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
        if (
            str(_record_value(row, "tenant_id")) != str(project.tenant_id)
            or str(_record_value(row, "project_global_id"))
            != str(project.global_id)
            or str(_record_value(row, "actor_user_id")).casefold()
            != self.actor.casefold()
            or str(_record_value(row, "operation")) != _OPERATION
            or str(_record_value(row, "idempotency_key_hash"))
            != idempotency_key_hash
            or str(_record_value(row, "payload_hash")) != payload_hash
        ):
            raise PublishRequestIdempotencyConflict()
        response = _json_object(_record_value(row, "response_payload"))
        request_global_id = _record_value(row, "request_global_id")
        if (
            int(_record_value(row, "sealed") or 0) != 1
            or not request_global_id
            or not response
            or response.get("globalId") != str(request_global_id)
            or str(_record_value(row, "response_hash")) != sha256_json(response)
        ):
            raise RuntimeError("Persisted publish command response is unsealed or invalid.")
        return response

    @staticmethod
    def _receipt_key(project, actor: str, idempotency_key_hash: str) -> str:
        return sha256_json(
            {
                "tenantId": str(project.tenant_id),
                "projectGlobalId": str(project.global_id),
                "actorUserId": actor.casefold(),
                "operation": _OPERATION,
                "idempotencyKeyHash": idempotency_key_hash,
            }
        )

    @staticmethod
    def _seal_receipt(
        receipt,
        *,
        request_id: UUID,
        response: Mapping[str, object],
        now: datetime,
    ) -> None:
        receipt.request_global_id = str(request_id)
        receipt.response_payload = dict(response)
        receipt.response_hash = sha256_json(response)
        receipt.sealed = 1
        receipt.updated_at = _database_datetime(now)
        receipt.save()

    @staticmethod
    def _insert_request_bundle(project, request: PublishRequest, *, now: datetime) -> None:
        frappe.get_doc(
            {
                "doctype": "NPI EBOM Publish Request",
                "global_id": str(request.global_id),
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "engineering_bom": str(request.evidence.ebom_global_id),
                "ebom_global_id": str(request.evidence.ebom_global_id),
                "engineering_bom_revision": str(request.evidence.revision_global_id),
                "revision_global_id": str(request.evidence.revision_global_id),
                "publish_policy_global_id": str(request.policy.global_id),
                "publish_policy_version": request.policy.version,
                "publish_policy_snapshot_hash": request.policy.snapshot_hash,
                "target_mode": request.target_mode.value,
                "api_version": "npi.erp-publish.v1",
                "operation": "publish_released_ebom_item_mbom",
                "state": request.state.value,
                "dispatch_allowed": 0,
                "evidence_snapshot": request.evidence.canonical_dict(),
                "payload_hash": request.payload_hash,
                "node_count": len(request.nodes),
                "actor_user_id": request.actor_user_id,
                "request_id": str(request.request_id),
                "trace_id": request.trace_id,
                "idempotency_key_hash": request.idempotency_key_hash,
                "created_at": _database_datetime(request.created_at),
            }
        ).insert()
        for node in request.nodes:
            FrappePublishRequestRepository._insert_node_bundle(
                project,
                request,
                node,
                now=now,
            )

    @staticmethod
    def _insert_node_bundle(
        project,
        request: PublishRequest,
        node: PublishRequestNode,
        *,
        now: datetime,
    ) -> None:
        mapping_id = uuid4()
        observation = {
            "schemaVersion": 1,
            "globalId": str(mapping_id),
            "projectGlobalId": str(project.global_id),
            "lineGlobalId": str(node.line.global_id),
            "engineeringItemId": node.line.engineering_item_id,
            "state": "unmapped",
            "version": 0,
            "formalItemCode": None,
            "formalMbomId": None,
            "targetVersion": None,
            "observedAt": None,
            "sourceSystem": "NPI_ONE",
        }
        frappe.get_doc(
            {
                "doctype": "NPI EBOM Publish Mapping Observation",
                "global_id": str(mapping_id),
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "line_global_id": str(node.line.global_id),
                "engineering_item_id": node.line.engineering_item_id,
                "mapping_state": "unmapped",
                "mapping_version": 0,
                "source_system": "NPI_ONE",
                "observation_snapshot": observation,
                "observation_hash": sha256_json(observation),
                "created_at": _database_datetime(now),
            }
        ).insert()
        frappe.get_doc(
            {
                "doctype": "NPI EBOM Publish Node",
                "global_id": str(node.global_id),
                "publish_request": str(request.global_id),
                "request_global_id": str(request.global_id),
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "ebom_global_id": str(request.evidence.ebom_global_id),
                "revision_global_id": str(request.evidence.revision_global_id),
                "line_global_id": str(node.line.global_id),
                "line_key": node.line.line_key,
                "engineering_item_id": node.line.engineering_item_id,
                "line_snapshot": node.line.snapshot_payload(),
                "line_hash": node.line.line_hash,
                "mapping_observation": str(mapping_id),
                "mapping_state": node.mapping.state.value,
                "mapping_version": node.mapping.version,
                "operations": [value.value for value in node.operations],
                "result_state": node.result_state.value,
                "input_hash": node.input_hash,
                "created_at": _database_datetime(now),
            }
        ).insert()
        for result in node.results:
            result_snapshot = {
                "schemaVersion": 1,
                "requestGlobalId": str(request.global_id),
                **result.payload(expose_target_identifiers=True),
            }
            frappe.get_doc(
                {
                    "doctype": "NPI EBOM Publish Node Result",
                    "global_id": str(result.global_id),
                    "publish_request": str(request.global_id),
                    "request_global_id": str(request.global_id),
                    "publish_node": str(node.global_id),
                    "node_global_id": str(node.global_id),
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "attempt_number": result.attempt_number,
                    "state": result.state.value,
                    "fault_kind": result.fault_kind.value if result.fault_kind else None,
                    "future_retry_directive": result.future_retry_directive.value,
                    "future_retryable": int(result.future_retryable),
                    "reconciliation_required": int(result.reconciliation_required),
                    "retry_after_required": int(result.retry_after_required),
                    "phase5_dispatch_allowed": 0,
                    "occurred_at": _database_datetime(result.occurred_at),
                    "result_snapshot": result_snapshot,
                    "result_hash": result.result_hash,
                }
            ).insert()

    def _request_for_scope(
        self,
        project,
        *,
        ebom_id: UUID,
        revision_id: UUID,
        request_id: UUID,
    ):
        try:
            row = frappe.get_doc("NPI EBOM Publish Request", str(request_id))
        except frappe.DoesNotExistError:
            return None
        return row if (
            str(row.global_id) == str(request_id)
            and str(row.tenant_id) == str(project.tenant_id)
            and str(row.project_global_id) == str(project.global_id)
            and str(row.ebom_global_id) == str(ebom_id)
            and str(row.revision_global_id) == str(revision_id)
        ) else None

    def _request_value(self, project, row) -> PublishRequest:
        evidence_value = _json_object(row.evidence_snapshot)
        evidence = ReleasedEbomEvidence(
            project_global_id=UUID(str(evidence_value["projectGlobalId"])),
            ebom_global_id=UUID(str(evidence_value["ebomGlobalId"])),
            ebom_version=int(evidence_value["ebomVersion"]),
            revision_global_id=UUID(str(evidence_value["revisionGlobalId"])),
            revision_number=int(evidence_value["revisionNumber"]),
            revision_snapshot_hash=str(evidence_value["revisionSnapshotHash"]),
            lifecycle_version=int(evidence_value["lifecycleVersion"]),
            release_event_global_id=UUID(str(evidence_value["releaseEventGlobalId"])),
            release_event_hash=str(evidence_value["releaseEventHash"]),
            ebom_policy_global_id=UUID(str(evidence_value["ebomPolicyGlobalId"])),
            ebom_policy_version=int(evidence_value["ebomPolicyVersion"]),
            ebom_policy_snapshot_hash=str(evidence_value["ebomPolicySnapshotHash"]),
            approval_evidence_ids=tuple(
                UUID(str(value))
                for value in evidence_value["approvalEvidenceIds"]
            ),
            released_at=_datetime_value(evidence_value["releasedAt"]),
        )
        node_rows = self._bounded_documents(
            "NPI EBOM Publish Node",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "request_global_id": str(row.global_id),
            },
            order_by="line_key asc, global_id asc",
            maximum=_MAX_NODES,
        )
        nodes = tuple(self._node_value(project, row, item) for item in node_rows)
        request = PublishRequest(
            global_id=UUID(str(row.global_id)),
            policy=PublishPolicyReference(
                UUID(str(row.publish_policy_global_id)),
                int(row.publish_policy_version),
                str(row.publish_policy_snapshot_hash),
            ),
            evidence=evidence,
            target_mode=PublishTargetMode(str(row.target_mode)),
            actor_user_id=str(row.actor_user_id),
            request_id=UUID(str(row.request_id)),
            trace_id=str(row.trace_id),
            idempotency_key_hash=str(row.idempotency_key_hash),
            state=PublishRequestState(str(row.state)),
            nodes=nodes,
            payload_hash=str(row.payload_hash),
            created_at=_datetime_value(row.created_at),
            dispatch_allowed=bool(row.dispatch_allowed),
        )
        if (
            str(row.tenant_id) != str(project.tenant_id)
            or str(row.project_global_id) != str(project.global_id)
            or str(row.ebom_global_id) != str(evidence.ebom_global_id)
            or str(row.revision_global_id) != str(evidence.revision_global_id)
            or int(row.node_count) != len(nodes)
            or str(row.api_version) != "npi.erp-publish.v1"
            or str(row.operation) != "publish_released_ebom_item_mbom"
        ):
            raise RuntimeError("Persisted publish request scope is invalid.")
        return request

    def _node_value(self, project, request_row, row) -> PublishRequestNode:
        line = _json_object(row.line_snapshot)
        mapping_row = frappe.get_doc(
            "NPI EBOM Publish Mapping Observation",
            str(row.mapping_observation),
        )
        mapping = MappingObservation(
            state=PublishMappingState(str(mapping_row.mapping_state)),
            version=int(mapping_row.mapping_version),
            formal_item_code=mapping_row.formal_item_code or None,
            formal_mbom_id=mapping_row.formal_mbom_id or None,
            target_version=mapping_row.target_version or None,
            observed_at=(
                _datetime_value(mapping_row.observed_at)
                if mapping_row.observed_at
                else None
            ),
        )
        publish_line = PublishLineInput(
            global_id=UUID(str(line["globalId"])),
            line_key=str(line["lineKey"]),
            parent_line_key=line["parentLineKey"],
            engineering_item_id=str(line["engineeringItemId"]),
            description=str(line["description"]),
            quantity=str(line["quantity"]),
            engineering_uom=str(line["engineeringUom"]),
            alternate_for_line_key=line["alternateForLineKey"],
            alternate_group_key=line["alternateGroupKey"],
            effectivity_start=line["effectivityStart"],
            effectivity_end=line["effectivityEnd"],
            attributes=tuple(sorted(dict(line["attributes"]).items())),
            line_hash=str(row.line_hash),
        )
        result_rows = self._bounded_documents(
            "NPI EBOM Publish Node Result",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "request_global_id": str(request_row.global_id),
                "node_global_id": str(row.global_id),
            },
            order_by="attempt_number asc, global_id asc",
            maximum=_MAX_RESULTS,
        )
        results = tuple(self._result_value(item) for item in result_rows)
        node = PublishRequestNode(
            global_id=UUID(str(row.global_id)),
            request_global_id=UUID(str(request_row.global_id)),
            line=publish_line,
            mapping=mapping,
            operations=tuple(
                PublishNodeOperation(str(value))
                for value in _json_array(row.operations)
            ),
            result_state=PublishNodeResultState(str(row.result_state)),
            input_hash=str(row.input_hash),
            results=results,
        )
        if (
            str(mapping_row.tenant_id) != str(project.tenant_id)
            or str(mapping_row.project_global_id) != str(project.global_id)
            or str(mapping_row.line_global_id) != str(node.line.global_id)
            or str(row.request_global_id) != str(request_row.global_id)
            or str(row.line_global_id) != str(node.line.global_id)
            or str(row.line_key) != node.line.line_key
            or str(row.engineering_item_id) != node.line.engineering_item_id
        ):
            raise RuntimeError("Persisted publish node scope is invalid.")
        return node

    @staticmethod
    def _result_value(row) -> PublishNodeResult:
        snapshot = _json_object(row.result_snapshot)
        return PublishNodeResult(
            global_id=UUID(str(snapshot["globalId"])),
            node_global_id=UUID(str(snapshot["nodeGlobalId"])),
            node_input_hash=str(snapshot["nodeInputHash"]),
            attempt_number=int(snapshot["attemptNumber"]),
            state=PublishNodeResultState(str(snapshot["state"])),
            fault_kind=(
                TargetFaultKind(str(snapshot["faultKind"]))
                if snapshot["faultKind"] is not None
                else None
            ),
            future_retry_directive=FutureRetryDirective(
                str(snapshot["futureRetryDirective"])
            ),
            future_retryable=bool(snapshot["futureRetryable"]),
            reconciliation_required=bool(snapshot["reconciliationRequired"]),
            retry_after_required=bool(snapshot["retryAfterRequired"]),
            phase5_dispatch_allowed=bool(snapshot["phase5DispatchAllowed"]),
            formal_item_code=snapshot["formalItemCode"],
            formal_mbom_id=snapshot["formalMbomId"],
            target_version=snapshot["targetVersion"],
            occurred_at=_datetime_value(snapshot["occurredAt"]),
            result_hash=str(row.result_hash),
        )

    @staticmethod
    def _list_response(
        project,
        root,
        revision,
        *,
        policies: tuple[dict[str, Any], ...],
        items: list[dict[str, object]],
    ) -> dict[str, Any]:
        return {
            "project": _project_response(project),
            "ebom": FrappeEngineeringBomRepository._ebom_summary(root),
            "revision": FrappeEngineeringBomRepository._revision_reference(revision),
            "permissions": {"view": True, "create": bool(policies)},
            "policies": list(policies),
            "items": items,
        }


def _json_array(value: object) -> list[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise RuntimeError("Persisted publish JSON array is invalid.") from error
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise RuntimeError("Persisted publish JSON array is invalid.")
    return list(value)


def _datetime_value(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
