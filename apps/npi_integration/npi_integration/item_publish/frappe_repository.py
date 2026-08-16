from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import frappe

from npi_core.documents.frappe_repository import _database_datetime, _json_object
from npi_core.foundation.errors import NpiProblem
from npi_core.foundation.security import Principal
from npi_core.project_controls.terminal_guard import require_mutable_project
from npi_integration.item_publish.config import ItemExecutionProfile
from npi_integration.item_publish.domain import (
    ITEM_PUBLISH_API_VERSION,
    ITEM_PUBLISH_OPERATION,
    ITEM_PUBLISH_SCHEMA_VERSION,
    ITEM_REQUEST_EVENT_TYPE,
    CurrentItemMapping,
    ItemExecutionProfileReference,
    ItemMappingExpectation,
    ItemOccurrence,
    ItemPublishContractError,
    ItemPublishRequest,
    ItemPublishRequestState,
    ItemSourceSnapshot,
    ItemTargetMode,
    ReleasedItemSourceEvidence,
    canonical_hash,
    create_item_publish_request,
    group_item_source,
)
from npi_integration.item_publish.problems import (
    ItemExecutionProfileUnavailable,
    ItemPublishAuthorityUnavailable,
    ItemPublishIdempotencyConflict,
    ItemPublishSourceConflict,
    ItemPublishStateConflict,
    ItemPublishUnavailable,
)
from npi_integration.item_publish.frappe_validation import (
    item_request_transaction_write,
)
from npi_integration.publish_request.domain import (
    PublishRequest,
    PublishRequestState,
    PublishTargetMode,
)
from npi_integration.publish_request.frappe_repository import (
    FrappePublishRequestRepository,
)


_MAX_ITEM_REQUESTS = 200

ProfileResolver = Callable[[str, UUID], ItemExecutionProfile | None]


@dataclass(frozen=True, slots=True)
class ItemPublishCommandOutcome:
    response: dict[str, Any] | None = None
    replayed: bool = False
    should_enqueue: bool = False
    outbox_event_id: UUID | None = None
    problem: NpiProblem | None = None


class FrappeItemPublishRepository(FrappePublishRequestRepository):
    """Project-first Item command landing; no adapter is reachable here."""

    def __init__(
        self,
        *,
        principal: Principal,
        request_id: str,
        trace_id: str,
        profile_resolver: ProfileResolver | None,
    ) -> None:
        super().__init__(
            principal=principal,
            request_id=request_id,
            trace_id=trace_id,
        )
        self._profile_resolver = profile_resolver

    def list_item_publish_requests(
        self,
        project_id: UUID,
        *,
        publish_request_id: UUID | None = None,
        selected_publish_node_id: UUID | None = None,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        profile = self._read_profile(project)
        rows = self._bounded_documents(
            "NPI Item Publish Request",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
            },
            order_by="created_at desc, global_id asc",
            maximum=_MAX_ITEM_REQUESTS,
        )
        items: list[dict[str, Any]] = []
        for row in rows:
            value = self._item_request_value(project, row)
            if (
                publish_request_id is not None
                and value.released_evidence.publish_request_global_id
                != publish_request_id
            ):
                continue
            if (
                selected_publish_node_id is not None
                and value.source.selected_publish_node_global_id
                != selected_publish_node_id
            ):
                continue
            items.append(self._request_public_dict(row, value))
        return {
            "projectGlobalId": str(project.global_id),
            "sourceFilters": {
                "publishRequestGlobalId": (
                    str(publish_request_id) if publish_request_id else None
                ),
                "selectedPublishNodeGlobalId": (
                    str(selected_publish_node_id)
                    if selected_publish_node_id
                    else None
                ),
            },
            "permissions": self._permissions(project, profile),
            "executionProfile": (
                profile.reference.canonical_mapping() if profile else None
            ),
            "items": items,
        }

    def item_publish_request_detail(
        self,
        project_id: UUID,
        request_global_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        row = self._item_request_for_scope(project, request_global_id, lock=False)
        if row is None:
            return None
        value = self._item_request_value(project, row)
        current = self._current_mapping_for_source(
            project,
            value.source,
            lock=False,
        )
        return self._detail_response(
            row,
            value,
            current=current,
            can_execute=self._permissions(
                project,
                self._read_profile(project),
            )["canExecute"],
        )

    def create_item_publish_request(
        self,
        project_id: UUID,
        *,
        publish_request_id: UUID,
        selected_publish_node_id: UUID,
        expected_mapping_version: int,
        idempotency_key_hash: str,
        acknowledgement: str,
    ) -> ItemPublishCommandOutcome | None:
        project = self._locked_command_project(project_id)
        if project is None:
            return None
        command_hash = canonical_hash(
            {
                "apiVersion": ITEM_PUBLISH_API_VERSION,
                "operation": ITEM_PUBLISH_OPERATION,
                "projectGlobalId": str(project.global_id),
                "publishRequestGlobalId": str(publish_request_id),
                "selectedPublishNodeGlobalId": str(selected_publish_node_id),
                "expectedMappingVersion": expected_mapping_version,
                "acknowledgement": acknowledgement,
            }
        )
        scope_key = self._idempotency_scope_key(
            project,
            idempotency_key_hash=idempotency_key_hash,
        )
        receipt = self._idempotency_receipt(scope_key)
        if receipt is not None:
            return self._replay_or_conflict(
                project,
                receipt,
                scope_key=scope_key,
                idempotency_key_hash=idempotency_key_hash,
                command_hash=command_hash,
            )
        require_mutable_project(project)

        phase5_row = self._phase5_request_for_project(
            project,
            publish_request_id,
            lock=True,
        )
        if phase5_row is None:
            return self._problem_outcome(
                project,
                global_id=publish_request_id,
                result="source_unavailable",
                problem=ItemPublishUnavailable(),
                summary={
                    "publishRequestGlobalId": str(publish_request_id),
                    "selectedPublishNodeGlobalId": str(
                        selected_publish_node_id
                    ),
                    "errorCode": "ITEM_PUBLISH_REQUEST_UNAVAILABLE",
                },
            )
        try:
            phase5_request = self._exact_released_phase5_request(
                project,
                phase5_row,
            )
            source = self._item_source(
                project,
                phase5_request,
                selected_publish_node_id,
            )
        except ItemPublishContractError:
            return self._problem_outcome(
                project,
                global_id=publish_request_id,
                result="source_engineering_item_conflict",
                problem=ItemPublishSourceConflict(),
                summary={
                    "publishRequestGlobalId": str(publish_request_id),
                    "selectedPublishNodeGlobalId": str(selected_publish_node_id),
                    "errorCode": "SOURCE_ENGINEERING_ITEM_CONFLICT",
                },
            )
        except NpiProblem as problem:
            return self._problem_outcome(
                project,
                global_id=publish_request_id,
                result="source_unavailable",
                problem=problem,
                summary={
                    "publishRequestGlobalId": str(publish_request_id),
                    "selectedPublishNodeGlobalId": str(selected_publish_node_id),
                    "errorCode": problem.code,
                },
            )
        except RuntimeError:
            return self._problem_outcome(
                project,
                global_id=publish_request_id,
                result="source_integrity_conflict",
                problem=ItemPublishStateConflict(),
                summary={
                    "publishRequestGlobalId": str(publish_request_id),
                    "selectedPublishNodeGlobalId": str(
                        selected_publish_node_id
                    ),
                    "errorCode": "ITEM_PUBLISH_STATE_CONFLICT",
                },
            )

        current = self._current_mapping_for_source(project, source, lock=True)
        current_version = 0 if current is None else current.mapping_version
        if current_version != expected_mapping_version:
            return self._problem_outcome(
                project,
                global_id=publish_request_id,
                result="mapping_expectation_conflict",
                problem=ItemPublishStateConflict(),
                summary={
                    "sourceStreamKeyHash": source.stream_key_hash,
                    "expectedMappingVersion": expected_mapping_version,
                    "currentMappingVersion": current_version,
                    "errorCode": "ITEM_PUBLISH_STATE_CONFLICT",
                },
            )
        expectation = self._mapping_expectation(current)
        try:
            profile = self._required_profile(project)
        except NpiProblem as problem:
            return self._problem_outcome(
                project,
                global_id=publish_request_id,
                result="profile_unavailable",
                problem=problem,
                summary={
                    "sourceStreamKeyHash": source.stream_key_hash,
                    "errorCode": problem.code,
                },
            )
        if not profile.permits(self.actor):
            return self._problem_outcome(
                project,
                global_id=publish_request_id,
                result="authority_unavailable",
                problem=ItemPublishAuthorityUnavailable(),
                summary={
                    "sourceStreamKeyHash": source.stream_key_hash,
                    "profileId": profile.profile_id,
                    "profileVersion": profile.profile_version,
                    "errorCode": "ITEM_PUBLISH_AUTHORITY_UNAVAILABLE",
                },
            )

        evidence = self._item_released_evidence(phase5_request)
        now = datetime.now(UTC)
        value = create_item_publish_request(
            source=source,
            released_evidence=evidence,
            profile=profile.reference,
            mapping_expectation=expectation,
            actor_user_id=self.actor,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
            idempotency_key_hash=idempotency_key_hash,
            global_id=uuid4(),
            created_at=now,
        )
        outbox_event_id = uuid4() if value.dispatch_allowed else None
        response = self._detail_response_from_value(
            value,
            outbox_event_id=outbox_event_id,
            current=current,
            can_execute=True,
            updated_at=now,
        )
        with item_request_transaction_write():
            self._insert_item_request(
                project,
                value,
                outbox_event_id=outbox_event_id,
                now=now,
            )
            if outbox_event_id is not None:
                self._insert_outbox(
                    project,
                    value,
                    event_id=outbox_event_id,
                )
            self._append_audit(
                operation="item_publish.request.create",
                global_id=value.global_id,
                object_version=1,
                result=value.state.value,
                summary={
                    "publishRequestGlobalId": str(publish_request_id),
                    "selectedPublishNodeGlobalId": str(selected_publish_node_id),
                    "sourceStreamKeyHash": source.stream_key_hash,
                    "sourceHash": source.source_hash,
                    "profileId": profile.profile_id,
                    "profileVersion": profile.profile_version,
                    "profileSnapshotHash": profile.snapshot_hash,
                    "targetMode": profile.target_mode.value,
                    "expectedMappingVersion": expectation.mapping_version,
                    "requestPayloadHash": value.payload_hash,
                    "outboxEventId": (
                        str(outbox_event_id) if outbox_event_id else None
                    ),
                },
            )
            self._insert_idempotency_receipt(
                project,
                value,
                scope_key=scope_key,
                command_hash=command_hash,
                response=response,
                now=now,
            )
        return ItemPublishCommandOutcome(
            response=response,
            should_enqueue=outbox_event_id is not None,
            outbox_event_id=outbox_event_id,
        )

    def _replay_or_conflict(
        self,
        project: object,
        receipt: object,
        *,
        scope_key: str,
        idempotency_key_hash: str,
        command_hash: str,
    ) -> ItemPublishCommandOutcome:
        exact_scope = (
            str(receipt.scope_key_hash) == scope_key
            and str(receipt.tenant_id) == str(project.tenant_id)
            and str(receipt.project_global_id) == str(project.global_id)
            and str(receipt.operation) == ITEM_PUBLISH_OPERATION
            and str(receipt.actor_user_id).casefold() == self.actor.casefold()
            and str(receipt.idempotency_key_hash) == idempotency_key_hash
        )
        if not exact_scope or str(receipt.request_payload_hash) != command_hash:
            return self._problem_outcome(
                project,
                global_id=UUID(str(receipt.request_global_id)),
                result="idempotency_conflict",
                problem=ItemPublishIdempotencyConflict(),
                summary={
                    "scopeKeyHash": scope_key,
                    "errorCode": "ITEM_PUBLISH_IDEMPOTENCY_CONFLICT",
                },
            )
        response = _json_object(receipt.response_snapshot)
        if (
            response.get("requestGlobalId") != str(receipt.request_global_id)
            or canonical_hash(response) != str(receipt.response_hash)
        ):
            raise RuntimeError("Persisted Item publish command response is invalid.")
        request_row = self._item_request_for_scope(
            project,
            UUID(str(receipt.request_global_id)),
            lock=True,
        )
        if request_row is None:
            raise RuntimeError("Persisted Item publish idempotency request is unavailable.")
        outbox_id = (
            UUID(str(request_row.outbox_event_id))
            if request_row.outbox_event_id
            else None
        )
        with item_request_transaction_write():
            self._append_audit(
                operation="item_publish.request.replay",
                global_id=UUID(str(receipt.request_global_id)),
                object_version=int(request_row.optimistic_version),
                result="replayed",
                summary={
                    "requestPayloadHash": str(request_row.payload_hash),
                    "sourceStreamKeyHash": str(request_row.source_stream_key_hash),
                    "outboxEventId": str(outbox_id) if outbox_id else None,
                },
            )
        return ItemPublishCommandOutcome(
            response=response,
            replayed=True,
            should_enqueue=False,
            outbox_event_id=outbox_id,
        )

    def _problem_outcome(
        self,
        project: object,
        *,
        global_id: UUID,
        result: str,
        problem: NpiProblem,
        summary: Mapping[str, object],
    ) -> ItemPublishCommandOutcome:
        with item_request_transaction_write():
            self._append_audit(
                operation="item_publish.request.conflict",
                global_id=global_id,
                object_version=1,
                result=result,
                summary=dict(summary),
            )
        return ItemPublishCommandOutcome(problem=problem)

    def _exact_released_phase5_request(
        self,
        project: object,
        row: object,
    ) -> PublishRequest:
        value = self._request_value(project, row)
        if (
            value.target_mode is not PublishTargetMode.MOCK
            or value.state is not PublishRequestState.VALIDATED
            or value.dispatch_allowed
        ):
            raise ItemPublishStateConflict()
        policy = self._load_exact_publish_policy(
            project,
            policy_global_id=value.policy.global_id,
            policy_version=value.policy.version,
            snapshot_hash=value.policy.snapshot_hash,
            lock=True,
        )
        if (
            UUID(str(policy["global_id"])) != value.policy.global_id
            or int(policy["version"]) != value.policy.version
            or str(policy["snapshot_hash"]) != value.policy.snapshot_hash
        ):
            raise ItemPublishStateConflict()
        evidence = value.evidence
        context = self._released_context(
            project,
            ebom_id=evidence.ebom_global_id,
            revision_id=evidence.revision_global_id,
            lock=True,
        )
        if context is None:
            raise ItemPublishStateConflict()
        root, _revision_row, revision, _lifecycle_row, lifecycle, release = context
        approval_ids = self._approval_evidence_ids(
            project,
            root,
            revision,
            release.global_id,
        )
        if (
            int(root.optimistic_version) != evidence.ebom_version
            or revision.revision_number != evidence.revision_number
            or revision.snapshot_hash != evidence.revision_snapshot_hash
            or lifecycle.lifecycle_version != evidence.lifecycle_version
            or release.global_id != evidence.release_event_global_id
            or release.event_hash != evidence.release_event_hash
            or tuple(approval_ids) != tuple(evidence.approval_evidence_ids)
            or revision.policy_ref.global_id != evidence.ebom_policy_global_id
            or revision.policy_ref.version != evidence.ebom_policy_version
            or revision.policy_ref.snapshot_hash
            != evidence.ebom_policy_snapshot_hash
            or release.occurred_at.astimezone(UTC)
            != evidence.released_at.astimezone(UTC)
        ):
            raise ItemPublishStateConflict()
        return value

    @staticmethod
    def _item_source(
        project: object,
        request: PublishRequest,
        selected_publish_node_id: UUID,
    ) -> ItemSourceSnapshot:
        selected_nodes = tuple(
            node
            for node in request.nodes
            if node.global_id == selected_publish_node_id
        )
        if len(selected_nodes) != 1:
            raise ItemPublishUnavailable()
        occurrences = tuple(
            ItemOccurrence(
                publish_node_global_id=node.global_id,
                line_global_id=node.line.global_id,
                engineering_item_id=node.line.engineering_item_id,
                description=node.line.description,
                engineering_uom=node.line.engineering_uom,
                attributes=tuple(node.line.attributes),
                line_hash=node.line.line_hash,
                node_input_hash=node.input_hash,
            )
            for node in request.nodes
        )
        return group_item_source(
            tenant_id=str(project.tenant_id),
            project_global_id=UUID(str(project.global_id)),
            selected_publish_node_global_id=selected_publish_node_id,
            occurrences=occurrences,
        )

    @staticmethod
    def _item_released_evidence(
        request: PublishRequest,
    ) -> ReleasedItemSourceEvidence:
        source = request.evidence
        return ReleasedItemSourceEvidence(
            publish_request_global_id=request.global_id,
            publish_request_payload_hash=request.payload_hash,
            publish_policy_global_id=request.policy.global_id,
            publish_policy_version=request.policy.version,
            publish_policy_snapshot_hash=request.policy.snapshot_hash,
            ebom_global_id=source.ebom_global_id,
            ebom_version=source.ebom_version,
            revision_global_id=source.revision_global_id,
            revision_number=source.revision_number,
            revision_snapshot_hash=source.revision_snapshot_hash,
            lifecycle_version=source.lifecycle_version,
            release_event_global_id=source.release_event_global_id,
            release_event_hash=source.release_event_hash,
            approval_evidence_ids=source.approval_evidence_ids,
            released_at=source.released_at,
        )

    def _required_profile(self, project: object) -> ItemExecutionProfile:
        profile = self._optional_profile(project)
        if profile is None:
            raise ItemExecutionProfileUnavailable()
        return profile

    def _read_profile(self, project: object) -> ItemExecutionProfile | None:
        try:
            return self._optional_profile(project)
        except ItemExecutionProfileUnavailable:
            return None

    def _optional_profile(self, project: object) -> ItemExecutionProfile | None:
        if not callable(self._profile_resolver):
            return None
        try:
            profile = self._profile_resolver(
                str(project.tenant_id),
                UUID(str(project.global_id)),
            )
        except Exception as error:
            raise ItemExecutionProfileUnavailable() from error
        if profile is None:
            return None
        if (
            not isinstance(profile, ItemExecutionProfile)
            or profile.tenant_id != str(project.tenant_id)
            or profile.project_global_id != str(project.global_id)
        ):
            raise ItemExecutionProfileUnavailable()
        return profile

    def _permissions(
        self,
        project: object,
        profile: ItemExecutionProfile | None,
    ) -> dict[str, bool]:
        can_execute = bool(
            profile is not None
            and not self.principal.is_external
            and "NPI API User" in self.principal.roles
            and self._current_actor_member(project) is not None
            and profile.permits(self.actor)
        )
        return {"canView": True, "canExecute": can_execute}

    def _current_mapping_for_source(
        self,
        project: object,
        source: ItemSourceSnapshot,
        *,
        lock: bool,
    ) -> CurrentItemMapping | None:
        name = frappe.db.get_value(
            "NPI Item Mapping Head",
            {"source_stream_key_hash": source.stream_key_hash},
            "name",
        )
        if not name:
            return None
        try:
            row = (
                frappe.get_doc("NPI Item Mapping Head", str(name), for_update=True)
                if lock
                else frappe.get_doc("NPI Item Mapping Head", str(name))
            )
        except frappe.DoesNotExistError as error:
            raise ItemPublishStateConflict() from error
        snapshot = _json_object(row.head_snapshot)
        expected = {
            "schemaVersion": 1,
            "globalId": str(row.global_id),
            "tenantId": str(row.tenant_id),
            "projectGlobalId": str(row.project_global_id),
            "sourceStreamKeyHash": str(row.source_stream_key_hash),
            "engineeringItemId": str(row.engineering_item_id),
            "mappingVersion": int(row.mapping_version),
            "formalItemCode": str(row.formal_item_code),
            "targetVersion": str(row.target_version),
            "currentObservationGlobalId": str(row.current_observation),
            "currentObservationHash": str(row.current_observation_hash),
            "updatedAt": _utc_text(_datetime_value(row.updated_at)),
        }
        if (
            str(row.tenant_id) != str(project.tenant_id)
            or str(row.project_global_id) != str(project.global_id)
            or str(row.source_stream_key_hash) != source.stream_key_hash
            or str(row.engineering_item_id) != source.engineering_item_id
            or snapshot != expected
            or canonical_hash(expected) != str(row.head_hash)
        ):
            raise ItemPublishStateConflict()
        return CurrentItemMapping(
            mapping_version=int(row.mapping_version),
            formal_item_code=str(row.formal_item_code),
            target_version=str(row.target_version),
            observation_hash=str(row.current_observation_hash),
        )

    @staticmethod
    def _mapping_expectation(
        current: CurrentItemMapping | None,
    ) -> ItemMappingExpectation:
        if current is None:
            return ItemMappingExpectation(0)
        return ItemMappingExpectation(
            current.mapping_version,
            current.formal_item_code,
            current.target_version,
            current.observation_hash,
        )

    @staticmethod
    def _phase5_request_for_project(
        project: object,
        request_id: UUID,
        *,
        lock: bool,
    ) -> object | None:
        try:
            row = (
                frappe.get_doc(
                    "NPI EBOM Publish Request",
                    str(request_id),
                    for_update=True,
                )
                if lock
                else frappe.get_doc("NPI EBOM Publish Request", str(request_id))
            )
        except frappe.DoesNotExistError:
            return None
        return row if (
            str(row.global_id) == str(request_id)
            and str(row.tenant_id) == str(project.tenant_id)
            and str(row.project_global_id) == str(project.global_id)
        ) else None

    @staticmethod
    def _item_request_for_scope(
        project: object,
        request_id: UUID,
        *,
        lock: bool,
    ) -> object | None:
        try:
            row = (
                frappe.get_doc(
                    "NPI Item Publish Request",
                    str(request_id),
                    for_update=True,
                )
                if lock
                else frappe.get_doc("NPI Item Publish Request", str(request_id))
            )
        except frappe.DoesNotExistError:
            return None
        return row if (
            str(row.global_id) == str(request_id)
            and str(row.tenant_id) == str(project.tenant_id)
            and str(row.project_global_id) == str(project.global_id)
        ) else None

    @staticmethod
    def _idempotency_receipt(scope_key: str) -> object | None:
        try:
            return frappe.get_doc(
                "NPI Item Publish Command Idempotency",
                scope_key,
                for_update=True,
            )
        except frappe.DoesNotExistError:
            return None

    def _idempotency_scope_key(
        self,
        project: object,
        *,
        idempotency_key_hash: str,
    ) -> str:
        return canonical_hash(
            {
                "tenantId": str(project.tenant_id),
                "projectGlobalId": str(project.global_id),
                "operation": ITEM_PUBLISH_OPERATION,
                "actorUserId": self.actor.casefold(),
                "idempotencyKeyHash": idempotency_key_hash,
            }
        )

    @staticmethod
    def _insert_item_request(
        project: object,
        value: ItemPublishRequest,
        *,
        outbox_event_id: UUID | None,
        now: datetime,
    ) -> None:
        expectation = value.mapping_expectation
        frappe.get_doc(
            {
                "doctype": "NPI Item Publish Request",
                "global_id": str(value.global_id),
                "schema_version": ITEM_PUBLISH_SCHEMA_VERSION,
                "api_version": ITEM_PUBLISH_API_VERSION,
                "operation": ITEM_PUBLISH_OPERATION,
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "source_stream_key_hash": value.source.stream_key_hash,
                "engineering_item_id": value.source.engineering_item_id,
                "selected_publish_node_global_id": str(
                    value.source.selected_publish_node_global_id
                ),
                "source_snapshot": value.source.canonical_mapping(),
                "source_hash": value.source.source_hash,
                "released_evidence_snapshot": (
                    value.released_evidence.canonical_mapping()
                ),
                "released_evidence_hash": canonical_hash(
                    value.released_evidence.canonical_mapping()
                ),
                "profile_id": value.profile.profile_id,
                "profile_version": value.profile.profile_version,
                "profile_snapshot_hash": value.profile.snapshot_hash,
                "target_mode": value.profile.target_mode.value,
                "environment_code": value.profile.environment_code,
                "intent": value.intent.value,
                "expected_mapping_version": expectation.mapping_version,
                "expected_formal_item_code": expectation.formal_item_code,
                "expected_target_version": expectation.target_version,
                "expected_mapping_observation_hash": expectation.observation_hash,
                "state": value.state.value,
                "dispatch_allowed": int(value.dispatch_allowed),
                "outbox_event_id": (
                    str(outbox_event_id) if outbox_event_id else None
                ),
                "result_global_id": None,
                "actor_user_id": value.actor_user_id,
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "idempotency_key_hash": value.idempotency_key_hash,
                "payload_hash": value.payload_hash,
                "optimistic_version": 1,
                "created_at": _database_datetime(value.created_at),
                "updated_at": _database_datetime(now),
            }
        ).insert()

    @staticmethod
    def _insert_outbox(
        project: object,
        value: ItemPublishRequest,
        *,
        event_id: UUID,
    ) -> None:
        payload = value.event_payload()
        payload_hash = canonical_hash(payload)
        event_snapshot_hash = canonical_hash(
            {
                "schemaVersion": 1,
                "eventId": str(event_id),
                "eventType": ITEM_REQUEST_EVENT_TYPE,
                "globalId": str(value.global_id),
                "objectVersion": 1,
                "tenantId": str(project.tenant_id),
                "projectGlobalId": str(project.global_id),
                "requestGlobalId": str(value.global_id),
                "operation": ITEM_PUBLISH_OPERATION,
                "profileId": value.profile.profile_id,
                "profileVersion": value.profile.profile_version,
                "profileSnapshotHash": value.profile.snapshot_hash,
                "sourceStreamKeyHash": value.source.stream_key_hash,
                "sourceHash": value.source.source_hash,
                "expectedMappingVersion": (
                    value.mapping_expectation.mapping_version
                ),
                "expectedTargetVersion": (
                    value.mapping_expectation.target_version
                ),
                "actorUserId": value.actor_user_id,
                "requestId": str(value.request_id),
                "traceId": value.trace_id,
                "idempotencyKeyHash": value.idempotency_key_hash,
                "payloadHash": payload_hash,
            }
        )
        frappe.get_doc(
            {
                "doctype": "NPI Outbox Message",
                "event_id": str(event_id),
                "event_type": ITEM_REQUEST_EVENT_TYPE,
                "global_id": str(value.global_id),
                "object_version": 1,
                "trace_id": value.trace_id,
                "payload_hash": payload_hash,
                "payload": payload,
                "state": "pending",
                "attempt_count": 0,
                "schema_version": ITEM_PUBLISH_SCHEMA_VERSION,
                "operation": ITEM_PUBLISH_OPERATION,
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "request_global_id": str(value.global_id),
                "profile_id": value.profile.profile_id,
                "profile_version": value.profile.profile_version,
                "profile_snapshot_hash": value.profile.snapshot_hash,
                "source_stream_key_hash": value.source.stream_key_hash,
                "source_hash": value.source.source_hash,
                "expected_mapping_version": (
                    value.mapping_expectation.mapping_version
                ),
                "expected_target_version": (
                    value.mapping_expectation.target_version
                ),
                "actor_user_id": value.actor_user_id,
                "request_id": str(value.request_id),
                "idempotency_key_hash": value.idempotency_key_hash,
                "event_snapshot_hash": event_snapshot_hash,
                "adapter_boundary_crossed": 0,
                "disposition": "ready",
            }
        ).insert()

    def _insert_idempotency_receipt(
        self,
        project: object,
        value: ItemPublishRequest,
        *,
        scope_key: str,
        command_hash: str,
        response: Mapping[str, object],
        now: datetime,
    ) -> None:
        frappe.get_doc(
            {
                "doctype": "NPI Item Publish Command Idempotency",
                "scope_key_hash": scope_key,
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "operation": ITEM_PUBLISH_OPERATION,
                "actor_user_id": self.actor.casefold(),
                "idempotency_key_hash": value.idempotency_key_hash,
                "request_payload_hash": command_hash,
                "request_global_id": str(value.global_id),
                "response_snapshot": dict(response),
                "response_hash": canonical_hash(response),
                "created_at": _database_datetime(now),
            }
        ).insert()

    def _item_request_value(
        self,
        project: object,
        row: object,
    ) -> ItemPublishRequest:
        source = _source_value(_json_object(row.source_snapshot))
        evidence = _evidence_value(_json_object(row.released_evidence_snapshot))
        profile = ItemExecutionProfileReference(
            profile_id=str(row.profile_id),
            profile_version=int(row.profile_version),
            target_mode=ItemTargetMode(str(row.target_mode)),
            environment_code=str(row.environment_code),
            snapshot_hash=str(row.profile_snapshot_hash),
        )
        expectation = ItemMappingExpectation(
            int(row.expected_mapping_version),
            row.expected_formal_item_code or None,
            row.expected_target_version or None,
            row.expected_mapping_observation_hash or None,
        )
        value = ItemPublishRequest(
            global_id=UUID(str(row.global_id)),
            source=source,
            released_evidence=evidence,
            profile=profile,
            mapping_expectation=expectation,
            actor_user_id=str(row.actor_user_id),
            request_id=UUID(str(row.request_id)),
            trace_id=str(row.trace_id),
            idempotency_key_hash=str(row.idempotency_key_hash),
            state=ItemPublishRequestState(str(row.state)),
            created_at=_datetime_value(row.created_at),
            payload_hash=str(row.payload_hash),
        )
        if (
            str(row.tenant_id) != str(project.tenant_id)
            or str(row.project_global_id) != str(project.global_id)
            or int(row.schema_version) != ITEM_PUBLISH_SCHEMA_VERSION
            or str(row.api_version) != ITEM_PUBLISH_API_VERSION
            or str(row.operation) != ITEM_PUBLISH_OPERATION
            or str(row.source_stream_key_hash) != source.stream_key_hash
            or str(row.engineering_item_id) != source.engineering_item_id
            or str(row.selected_publish_node_global_id)
            != str(source.selected_publish_node_global_id)
            or str(row.source_hash) != source.source_hash
            or str(row.released_evidence_hash)
            != canonical_hash(evidence.canonical_mapping())
            or bool(row.dispatch_allowed) != value.dispatch_allowed
            or int(row.optimistic_version) < 1
        ):
            raise RuntimeError("Persisted Item publish request scope is invalid.")
        return value

    @staticmethod
    def _request_public_dict(
        row: object,
        value: ItemPublishRequest,
    ) -> dict[str, Any]:
        expectation = value.mapping_expectation
        return {
            "schemaVersion": ITEM_PUBLISH_SCHEMA_VERSION,
            "globalId": str(value.global_id),
            "apiVersion": ITEM_PUBLISH_API_VERSION,
            "operation": ITEM_PUBLISH_OPERATION,
            "source": value.source.canonical_mapping(),
            "releasedEvidence": value.released_evidence.canonical_mapping(),
            "profile": value.profile.canonical_mapping(),
            "mappingExpectation": expectation.canonical_mapping(),
            "intent": value.intent.value,
            "actorUserId": value.actor_user_id,
            "requestId": str(value.request_id),
            "traceId": value.trace_id,
            "idempotencyKeyHash": value.idempotency_key_hash,
            "payloadHash": value.payload_hash,
            "state": str(row.state),
            "dispatchAllowed": bool(row.dispatch_allowed),
            "outboxEventId": (
                str(row.outbox_event_id) if row.outbox_event_id else None
            ),
            "resultGlobalId": (
                str(row.result_global_id) if row.result_global_id else None
            ),
            "optimisticVersion": int(row.optimistic_version),
            "createdAt": _utc_text(_datetime_value(row.created_at)),
            "updatedAt": _utc_text(_datetime_value(row.updated_at)),
        }

    def _detail_response(
        self,
        row: object,
        value: ItemPublishRequest,
        *,
        current: CurrentItemMapping | None,
        can_execute: bool,
    ) -> dict[str, Any]:
        return {
            "requestGlobalId": str(value.global_id),
            "request": self._request_public_dict(row, value),
            "currentMapping": _mapping_public_dict(current),
            "permissions": {"canView": True, "canExecute": can_execute},
        }

    @staticmethod
    def _detail_response_from_value(
        value: ItemPublishRequest,
        *,
        outbox_event_id: UUID | None,
        current: CurrentItemMapping | None,
        can_execute: bool,
        updated_at: datetime,
    ) -> dict[str, Any]:
        request = {
            "schemaVersion": ITEM_PUBLISH_SCHEMA_VERSION,
            "globalId": str(value.global_id),
            "apiVersion": ITEM_PUBLISH_API_VERSION,
            "operation": ITEM_PUBLISH_OPERATION,
            "source": value.source.canonical_mapping(),
            "releasedEvidence": value.released_evidence.canonical_mapping(),
            "profile": value.profile.canonical_mapping(),
            "mappingExpectation": value.mapping_expectation.canonical_mapping(),
            "intent": value.intent.value,
            "actorUserId": value.actor_user_id,
            "requestId": str(value.request_id),
            "traceId": value.trace_id,
            "idempotencyKeyHash": value.idempotency_key_hash,
            "payloadHash": value.payload_hash,
            "state": value.state.value,
            "dispatchAllowed": value.dispatch_allowed,
            "outboxEventId": (
                str(outbox_event_id) if outbox_event_id else None
            ),
            "resultGlobalId": None,
            "optimisticVersion": 1,
            "createdAt": _utc_text(value.created_at),
            "updatedAt": _utc_text(updated_at),
        }
        return {
            "requestGlobalId": str(value.global_id),
            "request": request,
            "currentMapping": _mapping_public_dict(current),
            "permissions": {"canView": True, "canExecute": can_execute},
        }


def _source_value(value: Mapping[str, object]) -> ItemSourceSnapshot:
    item_master = value.get("itemMaster")
    occurrences = value.get("occurrences")
    if (
        not isinstance(item_master, Mapping)
        or not isinstance(occurrences, list)
        or not all(isinstance(item, Mapping) for item in occurrences)
    ):
        raise RuntimeError("Persisted Item source snapshot is invalid.")
    return ItemSourceSnapshot(
        tenant_id=str(value["tenantId"]),
        project_global_id=UUID(str(value["projectGlobalId"])),
        engineering_item_id=str(value["engineeringItemId"]),
        selected_publish_node_global_id=UUID(
            str(value["selectedPublishNodeGlobalId"])
        ),
        description=str(item_master["description"]),
        engineering_uom=str(item_master["engineeringUom"]),
        attributes=tuple(sorted(dict(item_master["attributes"]).items())),
        occurrences=tuple(
            ItemOccurrence(
                publish_node_global_id=UUID(str(item["publishNodeGlobalId"])),
                line_global_id=UUID(str(item["lineGlobalId"])),
                engineering_item_id=str(item["engineeringItemId"]),
                description=str(item["description"]),
                engineering_uom=str(item["engineeringUom"]),
                attributes=tuple(sorted(dict(item["attributes"]).items())),
                line_hash=str(item["lineHash"]),
                node_input_hash=str(item["nodeInputHash"]),
            )
            for item in occurrences
        ),
        stream_key_hash=str(value["streamKeyHash"]),
        source_hash=str(value["sourceHash"]),
    )


def _evidence_value(value: Mapping[str, object]) -> ReleasedItemSourceEvidence:
    return ReleasedItemSourceEvidence(
        publish_request_global_id=UUID(str(value["publishRequestGlobalId"])),
        publish_request_payload_hash=str(value["publishRequestPayloadHash"]),
        publish_policy_global_id=UUID(str(value["publishPolicyGlobalId"])),
        publish_policy_version=int(value["publishPolicyVersion"]),
        publish_policy_snapshot_hash=str(value["publishPolicySnapshotHash"]),
        ebom_global_id=UUID(str(value["ebomGlobalId"])),
        ebom_version=int(value["ebomVersion"]),
        revision_global_id=UUID(str(value["revisionGlobalId"])),
        revision_number=int(value["revisionNumber"]),
        revision_snapshot_hash=str(value["revisionSnapshotHash"]),
        lifecycle_version=int(value["lifecycleVersion"]),
        release_event_global_id=UUID(str(value["releaseEventGlobalId"])),
        release_event_hash=str(value["releaseEventHash"]),
        approval_evidence_ids=tuple(
            UUID(str(item)) for item in value["approvalEvidenceIds"]
        ),
        released_at=_datetime_value(value["releasedAt"]),
    )


def _mapping_public_dict(
    value: CurrentItemMapping | None,
) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "mappingVersion": value.mapping_version,
        "formalItemCode": value.formal_item_code,
        "targetVersion": value.target_version,
        "observationHash": value.observation_hash,
    }


def _datetime_value(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise RuntimeError("Persisted Item publish timestamp is invalid.") from error
    else:
        raise RuntimeError("Persisted Item publish timestamp is invalid.")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


__all__ = [
    "FrappeItemPublishRepository",
    "ItemExecutionProfileUnavailable",
    "ItemPublishAuthorityUnavailable",
    "ItemPublishCommandOutcome",
    "ItemPublishIdempotencyConflict",
    "ItemPublishSourceConflict",
    "ItemPublishStateConflict",
    "ItemPublishUnavailable",
]
