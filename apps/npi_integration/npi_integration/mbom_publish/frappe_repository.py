from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import frappe

from npi_core.documents.domain import canonical_json
from npi_core.documents.frappe_repository import (
    _database_datetime,
    _json_array,
    _json_object,
)
from npi_core.foundation.errors import NpiProblem
from npi_core.foundation.security import Principal
from npi_core.project_controls.terminal_guard import require_mutable_project
from npi_integration.item_publish.frappe_repository import FrappeItemPublishRepository
from npi_integration.mbom_publish.config import MbomExecutionProfile
from npi_integration.mbom_publish.domain import (
    MBOM_PUBLISH_API_VERSION,
    MBOM_PUBLISH_EVENT_VERSION,
    MBOM_PUBLISH_OPERATION,
    MBOM_PUBLISH_SCHEMA_VERSION,
    MBOM_REQUEST_EVENT_TYPE,
    ItemMappingReadiness,
    ItemReadinessDisposition,
    MbomExecutionProfileReference,
    MbomMappingExpectation,
    MbomPublishContractError,
    MbomPublishRequest,
    MbomPublishRequestState,
    MbomResultAuthority,
    MbomSourceLine,
    MbomSourceRole,
    MbomSourceSnapshot,
    MbomTargetMode,
    MbomTargetSubmissionState,
    canonical_hash,
    create_mbom_publish_request,
    synthetic_item_readiness,
)
from npi_integration.mbom_publish.frappe_validation import (
    MbomSupportWriteCapability,
    insert_mbom_support_document,
    mbom_request_transaction_write,
    save_mbom_support_document,
    validate_mbom_service_actor,
)
from npi_integration.mbom_publish.diagnostics import mbom_create_server_step
from npi_integration.mbom_publish.problems import (
    MbomExecutionProfileUnavailable,
    MbomPublishAuthorityUnavailable,
    MbomPublishEffectRetained,
    MbomPublishIdempotencyConflict,
    MbomPublishReconciliationRequired,
    MbomPublishStateConflict,
    MbomPublishStreamActive,
    MbomPublishUnavailable,
)


_MAX_REQUESTS = 200
_MAX_NODES = 500
_MAX_ATTEMPTS = 100
_ACTIVE_STATES = frozenset(
    {
        MbomPublishRequestState.QUEUED.value,
        MbomPublishRequestState.PROCESSING.value,
        MbomPublishRequestState.FAILED_RETRYABLE.value,
        MbomPublishRequestState.UNCERTAIN_AFTER_TIMEOUT.value,
        MbomPublishRequestState.MAPPING_CONFLICT.value,
    }
)
_RETAINED_STATES = frozenset(
    {
        MbomPublishRequestState.SYNTHETIC_VERIFIED.value,
        MbomPublishRequestState.PARTIALLY_SUCCEEDED.value,
        MbomPublishRequestState.SUCCEEDED.value,
        MbomPublishRequestState.FAILED_FINAL.value,
    }
)

ProfileResolver = Callable[[str, UUID], MbomExecutionProfile | None]


@dataclass(frozen=True, slots=True)
class MbomPublishCommandOutcome:
    response: dict[str, Any] | None = None
    replayed: bool = False
    should_enqueue: bool = False
    outbox_event_id: UUID | None = None
    problem: NpiProblem | None = None


class FrappeMbomPublishRepository(FrappeItemPublishRepository):
    """Project-first MBOM command landing; no target adapter is reachable here."""

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
            profile_resolver=None,
        )
        self._mbom_profile_resolver = profile_resolver

    def list_mbom_publish_requests(
        self,
        project_id: UUID,
        *,
        phase5_publish_request_id: UUID | None = None,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        filters = {
            "tenant_id": str(project.tenant_id),
            "project_global_id": str(project.global_id),
        }
        if phase5_publish_request_id is not None:
            filters["phase5_publish_request_global_id"] = str(
                phase5_publish_request_id
            )
        rows = self._bounded_documents(
            "NPI MBOM Publish Request",
            filters,
            order_by="created_at desc, global_id asc",
            maximum=_MAX_REQUESTS,
        )
        profile = self._read_profile(project)
        create_context = None
        if phase5_publish_request_id is not None and profile is not None:
            try:
                candidate = self._build_request(
                    project,
                    phase5_publish_request_id,
                    profile,
                    idempotency_key_hash="0" * 64,
                    lock=False,
                )
            except (NpiProblem, MbomPublishContractError, RuntimeError):
                candidate = None
            if candidate is not None:
                create_context = {
                    "phase5PublishRequestGlobalId": str(
                        candidate.source.phase5_publish_request_global_id
                    ),
                    "source": candidate.source.canonical_mapping(),
                    "itemReadiness": [
                        item.canonical_mapping() for item in candidate.item_readiness
                    ],
                    "itemMappingSetHash": candidate.item_mapping_set_hash,
                    "mbomExpectations": [
                        item.canonical_mapping()
                        for item in candidate.mbom_expectations
                    ],
                    "mbomMappingSetHash": candidate.mbom_mapping_set_hash,
                    "profile": candidate.profile.canonical_mapping(),
                }
        return {
            "projectGlobalId": str(project.global_id),
            "phase5PublishRequestGlobalId": (
                str(phase5_publish_request_id)
                if phase5_publish_request_id is not None
                else None
            ),
            "permissions": self._permissions(project, profile),
            "executionProfile": profile.reference.canonical_mapping() if profile else None,
            "createContext": create_context,
            "items": [self._request_public_dict(project, row) for row in rows],
        }

    def mbom_publish_request_detail(
        self,
        project_id: UUID,
        request_global_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        row = self._request_for_scope(project, request_global_id, lock=False)
        if row is None:
            return None
        response = self._request_public_dict(project, row)
        nodes = self._bounded_documents(
            "NPI MBOM Publish Node",
            {"request_global_id": str(request_global_id)},
            order_by="stable_line_key asc, global_id asc",
            maximum=_MAX_NODES,
        )
        if len(nodes) != len(response["request"]["source"]["topology"]["lines"]):
            raise RuntimeError("Persisted MBOM node manifest is incomplete.")
        response["nodes"] = [self._node_public_dict(project, row, node) for node in nodes]
        permissions = self._permissions(project, self._read_profile(project))
        attempts = self._attempt_public_dicts(row, response["request"])
        result = self._result_public_dict(row, response["request"])
        node_results, current_mappings = self._node_result_public_dicts(
            project,
            row,
            response["request"],
            nodes,
            result,
            can_view=permissions["canView"],
        )
        response["attempts"] = list(attempts)
        response["result"] = result
        response["nodeResults"] = list(node_results)
        response["currentMappings"] = list(current_mappings)
        response["permissions"] = permissions
        return response

    def create_mbom_publish_request(
        self,
        project_id: UUID,
        *,
        phase5_publish_request_id: UUID,
        expected_source_hash: str,
        expected_topology_hash: str,
        expected_item_mapping_set_hash: str,
        expected_mbom_mapping_set_hash: str,
        idempotency_key_hash: str,
        acknowledgement: str,
    ) -> MbomPublishCommandOutcome | None:
        with mbom_create_server_step("P804_CREATE_PROJECT_LOCK"):
            project = self._locked_command_project(project_id)
        if project is None:
            return None
        with mbom_create_server_step("P804_CREATE_IDEMPOTENCY_CONTEXT"):
            command_hash = canonical_hash(
                {
                    "apiVersion": MBOM_PUBLISH_API_VERSION,
                    "operation": MBOM_PUBLISH_OPERATION,
                    "projectGlobalId": str(project.global_id),
                    "phase5PublishRequestGlobalId": str(phase5_publish_request_id),
                    "expectedSourceHash": expected_source_hash,
                    "expectedTopologyHash": expected_topology_hash,
                    "expectedItemMappingSetHash": expected_item_mapping_set_hash,
                    "expectedMbomMappingSetHash": expected_mbom_mapping_set_hash,
                    "acknowledgement": acknowledgement,
                }
            )
            scope_key = self._idempotency_scope_key(project, idempotency_key_hash)
            receipt = self._idempotency_receipt(scope_key)
        if receipt is not None:
            with mbom_create_server_step("P804_CREATE_IDEMPOTENCY_REPLAY"):
                return self._replay_or_conflict(
                    project,
                    receipt,
                    scope_key=scope_key,
                    idempotency_key_hash=idempotency_key_hash,
                    command_hash=command_hash,
                )
        with mbom_create_server_step("P804_CREATE_PROJECT_MUTABILITY"):
            require_mutable_project(project)
        try:
            with mbom_create_server_step("P804_CREATE_PROFILE_RESOLVE"):
                profile = self._required_profile(project)
            with mbom_create_server_step("P804_CREATE_PRELOCK_BUILD"):
                value = self._build_request(
                    project,
                    phase5_publish_request_id,
                    profile,
                    idempotency_key_hash=idempotency_key_hash,
                    lock=False,
                )
        except NpiProblem as problem:
            return self._problem_outcome(project, phase5_publish_request_id, problem)
        except (MbomPublishContractError, RuntimeError):
            return self._problem_outcome(
                project,
                phase5_publish_request_id,
                MbomPublishStateConflict(),
            )
        if (
            value.source.source_hash != expected_source_hash
            or value.source.topology_hash != expected_topology_hash
            or value.item_mapping_set_hash != expected_item_mapping_set_hash
            or value.mbom_mapping_set_hash != expected_mbom_mapping_set_hash
        ):
            return self._problem_outcome(
                project,
                phase5_publish_request_id,
                MbomPublishStateConflict(),
            )
        if not profile.permits(self.actor):
            return self._problem_outcome(
                project,
                phase5_publish_request_id,
                MbomPublishAuthorityUnavailable(),
            )
        if profile.target_mode is not MbomTargetMode.MOCK:
            try:
                with mbom_create_server_step(
                    "P804_CREATE_SERVICE_ACTOR_VALIDATE"
                ):
                    validate_mbom_service_actor(profile.service_actor_user_id)
            except RuntimeError:
                return self._problem_outcome(
                    project,
                    phase5_publish_request_id,
                    MbomExecutionProfileUnavailable(),
                )
        now = value.created_at
        outbox_event_id = uuid4() if value.dispatch_allowed else None
        with mbom_create_server_step("P804_CREATE_RESPONSE_BUILD"):
            response = self._response_from_value(value, outbox_event_id, now)
        with mbom_create_server_step(
            "P804_CREATE_TRANSACTION_SCOPE"
        ), mbom_request_transaction_write(self.actor) as capability:
            guard = None
            if value.dispatch_allowed:
                with mbom_create_server_step("P804_CREATE_STREAM_GUARD"):
                    guard = _locked_stream_guard(
                        value.source,
                        create=True,
                        now=now,
                        capability=capability,
                    )
                    problem = _stream_guard_problem(guard, value)
                if problem is not None:
                    return self._problem_outcome(project, value.global_id, problem)
            with mbom_create_server_step("P804_CREATE_PROFILE_REVALIDATE"):
                locked_profile = self._required_profile(project)
            with mbom_create_server_step("P804_CREATE_LOCKED_BUILD"):
                locked = self._build_request(
                    project,
                    phase5_publish_request_id,
                    locked_profile,
                    idempotency_key_hash=idempotency_key_hash,
                    lock=True,
                    global_id=value.global_id,
                    created_at=value.created_at,
                )
            with mbom_create_server_step("P804_CREATE_LOCK_COMPARE"):
                if locked != value or locked_profile.reference != value.profile:
                    raise RuntimeError(
                        "The MBOM command inputs changed during locking."
                    )
            with mbom_create_server_step("P804_CREATE_REQUEST_INSERT"):
                self._insert_request(
                    project,
                    value,
                    outbox_event_id=outbox_event_id,
                    now=now,
                    capability=capability,
                )
            with mbom_create_server_step("P804_CREATE_NODE_INSERT"):
                node_manifest_hash = self._insert_nodes(
                    value,
                    now=now,
                    capability=capability,
                )
            if outbox_event_id is not None:
                with mbom_create_server_step("P804_CREATE_OUTBOX_INSERT"):
                    self._insert_outbox(
                        project,
                        value,
                        event_id=outbox_event_id,
                        node_manifest_hash=node_manifest_hash,
                        capability=capability,
                    )
            if guard is not None:
                with mbom_create_server_step("P804_CREATE_GUARD_ACTIVATE"):
                    _activate_stream_guard(
                        guard,
                        value,
                        now=now,
                        capability=capability,
                    )
            with mbom_create_server_step("P804_CREATE_AUDIT_APPEND"):
                self._append_audit(
                    operation="mbom_publish.request.create",
                    global_id=value.global_id,
                    object_version=1,
                    result=value.state.value,
                    summary={
                        "phase5PublishRequestGlobalId": str(
                            phase5_publish_request_id
                        ),
                        "sourceHash": value.source.source_hash,
                        "topologyHash": value.source.topology_hash,
                        "itemMappingSetHash": value.item_mapping_set_hash,
                        "mbomMappingSetHash": value.mbom_mapping_set_hash,
                        "profileId": value.profile.profile_id,
                        "profileVersion": value.profile.profile_version,
                        "requestPayloadHash": value.payload_hash,
                        "outboxEventId": (
                            str(outbox_event_id) if outbox_event_id else None
                        ),
                    },
                )
            with mbom_create_server_step("P804_CREATE_IDEMPOTENCY_INSERT"):
                self._insert_idempotency_receipt(
                    project,
                    value,
                    scope_key=scope_key,
                    command_hash=command_hash,
                    response=response,
                    now=now,
                    capability=capability,
                )
        return MbomPublishCommandOutcome(
            response=response,
            should_enqueue=outbox_event_id is not None,
            outbox_event_id=outbox_event_id,
        )

    def _build_request(
        self,
        project: object,
        phase5_request_id: UUID,
        profile: MbomExecutionProfile,
        *,
        idempotency_key_hash: str,
        lock: bool,
        global_id: UUID | None = None,
        created_at: datetime | None = None,
    ) -> MbomPublishRequest:
        row = self._phase5_request_for_project(project, phase5_request_id, lock=lock)
        if row is None:
            raise MbomPublishUnavailable()
        phase5 = self._exact_released_phase5_request(project, row)
        source = _source_from_phase5(project, phase5)
        readiness = self._item_readiness(project, phase5, source, profile, lock=lock)
        expectations = self._mbom_expectations(project, source, lock=lock)
        return create_mbom_publish_request(
            source=source,
            item_readiness=readiness,
            mbom_expectations=expectations,
            profile=profile.reference,
            actor_user_id=self.actor,
            service_actor_user_id=(
                profile.service_actor_user_id
                if profile.target_mode is not MbomTargetMode.MOCK
                else None
            ),
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
            idempotency_key_hash=idempotency_key_hash,
            global_id=global_id or uuid4(),
            created_at=created_at or datetime.now(UTC),
        )

    def _item_readiness(
        self,
        project: object,
        phase5: object,
        source: MbomSourceSnapshot,
        profile: MbomExecutionProfile,
        *,
        lock: bool,
    ) -> tuple[ItemMappingReadiness, ...]:
        if profile.target_mode is MbomTargetMode.SYNTHETIC:
            return synthetic_item_readiness(source)
        if profile.target_mode is MbomTargetMode.MOCK:
            return tuple(
                ItemMappingReadiness(
                    engineering_item_id=engineering_item_id,
                    disposition=ItemReadinessDisposition.NOT_READY,
                    item_stream_key_hash=_item_stream_key(
                        source.tenant_id,
                        source.project_global_id,
                        engineering_item_id,
                    ),
                    mapping_version=0,
                )
                for engineering_item_id in source.engineering_item_ids
            )
        values: list[ItemMappingReadiness] = []
        for engineering_item_id in source.engineering_item_ids:
            node = next(
                item
                for item in phase5.nodes
                if item.line.engineering_item_id == engineering_item_id
            )
            item_source = self._item_source(project, phase5, node.global_id)
            current = self._current_mapping_for_source(project, item_source, lock=lock)
            if current is None:
                raise MbomPublishStateConflict()
            provenance = self._current_mapping_public_dict(
                project,
                SimpleNamespace(source=item_source),
                current,
            )
            observation = provenance["observation"] if provenance else None
            if not isinstance(observation, dict):
                raise MbomPublishStateConflict()
            values.append(
                ItemMappingReadiness(
                    engineering_item_id=engineering_item_id,
                    disposition=ItemReadinessDisposition.ADVANCED,
                    item_stream_key_hash=item_source.stream_key_hash,
                    mapping_version=current.mapping_version,
                    formal_item_code=current.formal_item_code,
                    target_version=current.target_version,
                    observation_hash=current.observation_hash,
                    authority=MbomResultAuthority.AUTHORITATIVE_SANDBOX,
                    response_authenticated=True,
                )
            )
        return tuple(values)

    def _mbom_expectations(
        self,
        project: object,
        source: MbomSourceSnapshot,
        *,
        lock: bool,
    ) -> tuple[MbomMappingExpectation, ...]:
        return tuple(
            self._mbom_expectation(project, source, line_key, lock=lock)
            for line_key in source.assembly_line_keys
        )

    @staticmethod
    def _mbom_expectation(
        project: object,
        source: MbomSourceSnapshot,
        stable_line_key: str,
        *,
        lock: bool,
    ) -> MbomMappingExpectation:
        assembly_key = source.assembly_source_key(stable_line_key)
        name = frappe.db.get_value(
            "NPI MBOM Mapping Head",
            {"assembly_source_key": assembly_key},
            "name",
        )
        if not name:
            return MbomMappingExpectation(
                assembly_source_key=assembly_key,
                stable_line_key=stable_line_key,
                mapping_version=0,
                submission_state=MbomTargetSubmissionState.UNMAPPED_CREATE,
            )
        try:
            row = (
                frappe.get_doc("NPI MBOM Mapping Head", str(name), for_update=True)
                if lock
                else frappe.get_doc("NPI MBOM Mapping Head", str(name))
            )
        except frappe.DoesNotExistError as error:
            raise MbomPublishStateConflict() from error
        expected = {
            "schemaVersion": MBOM_PUBLISH_SCHEMA_VERSION,
            "globalId": str(row.global_id),
            "tenantId": str(row.tenant_id),
            "projectGlobalId": str(row.project_global_id),
            "ebomGlobalId": str(row.ebom_global_id),
            "assemblySourceKey": str(row.assembly_source_key),
            "stableLineKey": str(row.stable_line_key),
            "mappingVersion": int(row.mapping_version),
            "formalBomId": str(row.formal_bom_id),
            "targetVersion": str(row.target_version),
            "targetSubmissionState": str(row.target_submission_state),
            "currentObservationGlobalId": str(row.current_observation),
            "currentObservationHash": str(row.current_observation_hash),
            "updatedAt": _utc_text(_datetime_value(row.updated_at)),
        }
        if (
            str(row.tenant_id) != str(project.tenant_id)
            or str(row.project_global_id) != str(project.global_id)
            or str(row.ebom_global_id) != str(source.ebom_global_id)
            or str(row.assembly_source_key) != assembly_key
            or str(row.stable_line_key) != stable_line_key
            or _json_object(row.head_snapshot) != expected
            or canonical_hash(expected) != str(row.head_hash)
        ):
            raise MbomPublishStateConflict()
        return MbomMappingExpectation(
            assembly_source_key=assembly_key,
            stable_line_key=stable_line_key,
            mapping_version=int(row.mapping_version),
            submission_state=MbomTargetSubmissionState(str(row.target_submission_state)),
            formal_bom_id=str(row.formal_bom_id),
            target_version=str(row.target_version),
            observation_hash=str(row.current_observation_hash),
        )

    def _required_profile(self, project: object) -> MbomExecutionProfile:
        profile = self._optional_profile(project)
        if profile is None:
            raise MbomExecutionProfileUnavailable()
        return profile

    def _read_profile(self, project: object) -> MbomExecutionProfile | None:
        try:
            return self._optional_profile(project)
        except MbomExecutionProfileUnavailable:
            return None

    def _optional_profile(self, project: object) -> MbomExecutionProfile | None:
        if not callable(self._mbom_profile_resolver):
            return None
        try:
            profile = self._mbom_profile_resolver(
                str(project.tenant_id),
                UUID(str(project.global_id)),
            )
        except Exception as error:
            raise MbomExecutionProfileUnavailable() from error
        if profile is None:
            return None
        if (
            not isinstance(profile, MbomExecutionProfile)
            or profile.tenant_id != str(project.tenant_id)
            or profile.project_global_id != str(project.global_id)
        ):
            raise MbomExecutionProfileUnavailable()
        return profile

    def _permissions(
        self,
        project: object,
        profile: MbomExecutionProfile | None,
    ) -> dict[str, bool]:
        can_execute = bool(
            profile is not None
            and not self.principal.is_external
            and "NPI API User" in self.principal.roles
            and self._current_actor_member(project) is not None
            and profile.permits(self.actor)
        )
        return {"canView": True, "canExecute": can_execute}

    @staticmethod
    def _request_for_scope(project: object, request_id: UUID, *, lock: bool) -> object | None:
        try:
            row = (
                frappe.get_doc("NPI MBOM Publish Request", str(request_id), for_update=True)
                if lock
                else frappe.get_doc("NPI MBOM Publish Request", str(request_id))
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
                "NPI MBOM Publish Command Idempotency",
                scope_key,
                for_update=True,
            )
        except frappe.DoesNotExistError:
            return None

    def _idempotency_scope_key(self, project: object, idempotency_key_hash: str) -> str:
        return canonical_hash(
            {
                "tenantId": str(project.tenant_id),
                "projectGlobalId": str(project.global_id),
                "operation": MBOM_PUBLISH_OPERATION,
                "actorUserId": self.actor.casefold(),
                "idempotencyKeyHash": idempotency_key_hash,
            }
        )

    def _replay_or_conflict(
        self,
        project: object,
        receipt: object,
        *,
        scope_key: str,
        idempotency_key_hash: str,
        command_hash: str,
    ) -> MbomPublishCommandOutcome:
        if (
            str(receipt.scope_key_hash) != scope_key
            or str(receipt.tenant_id) != str(project.tenant_id)
            or str(receipt.project_global_id) != str(project.global_id)
            or str(receipt.operation) != MBOM_PUBLISH_OPERATION
            or str(receipt.actor_user_id).casefold() != self.actor.casefold()
            or str(receipt.idempotency_key_hash) != idempotency_key_hash
            or str(receipt.request_payload_hash) != command_hash
        ):
            with mbom_request_transaction_write(self.actor):
                self._append_audit(
                    operation="mbom_publish.request.conflict",
                    global_id=UUID(str(receipt.request_global_id)),
                    object_version=1,
                    result="idempotency_conflict",
                    summary={"scopeKeyHash": scope_key, "errorCode": "MBOM_PUBLISH_IDEMPOTENCY_CONFLICT"},
                )
            return MbomPublishCommandOutcome(problem=MbomPublishIdempotencyConflict())
        response = _json_object(receipt.response_snapshot)
        if (
            response.get("requestGlobalId") != str(receipt.request_global_id)
            or canonical_hash(response) != str(receipt.response_hash)
        ):
            raise RuntimeError("Persisted MBOM command response is invalid.")
        row = self._request_for_scope(
            project,
            UUID(str(receipt.request_global_id)),
            lock=True,
        )
        if row is None:
            raise RuntimeError("Persisted MBOM idempotency request is unavailable.")
        with mbom_request_transaction_write(self.actor):
            self._append_audit(
                operation="mbom_publish.request.replay",
                global_id=UUID(str(row.global_id)),
                object_version=int(row.optimistic_version),
                result="replayed",
                summary={"requestPayloadHash": str(row.payload_hash)},
            )
        return MbomPublishCommandOutcome(
            response=response,
            replayed=True,
            outbox_event_id=UUID(str(row.outbox_event_id)) if row.outbox_event_id else None,
        )

    def _problem_outcome(
        self,
        project: object,
        global_id: UUID,
        problem: NpiProblem,
    ) -> MbomPublishCommandOutcome:
        with mbom_create_server_step(
            "P804_CREATE_PROBLEM_OUTCOME"
        ), mbom_request_transaction_write(self.actor):
            self._append_audit(
                operation="mbom_publish.request.conflict",
                global_id=global_id,
                object_version=1,
                result=problem.code.casefold(),
                summary={"errorCode": problem.code},
            )
        return MbomPublishCommandOutcome(problem=problem)

    @staticmethod
    def _insert_request(
        project: object,
        value: MbomPublishRequest,
        *,
        outbox_event_id: UUID | None,
        now: datetime,
        capability: MbomSupportWriteCapability,
    ) -> None:
        insert_mbom_support_document(
            frappe.get_doc(
                {
                    "doctype": "NPI MBOM Publish Request",
                    "global_id": str(value.global_id),
                    "schema_version": MBOM_PUBLISH_SCHEMA_VERSION,
                    "api_version": MBOM_PUBLISH_API_VERSION,
                    "operation": MBOM_PUBLISH_OPERATION,
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "phase5_publish_request_global_id": str(value.source.phase5_publish_request_global_id),
                    "ebom_global_id": str(value.source.ebom_global_id),
                    "source_stream_key_hash": value.source.source_stream_key_hash,
                    "source_snapshot": value.source.canonical_mapping(),
                    "source_hash": value.source.source_hash,
                    "topology_hash": value.source.topology_hash,
                    "item_readiness_snapshot": canonical_json(
                        [item.canonical_mapping() for item in value.item_readiness]
                    ),
                    "item_mapping_set_hash": value.item_mapping_set_hash,
                    "mbom_expectation_snapshot": canonical_json(
                        [item.canonical_mapping() for item in value.mbom_expectations]
                    ),
                    "mbom_mapping_set_hash": value.mbom_mapping_set_hash,
                    "profile_id": value.profile.profile_id,
                    "profile_version": value.profile.profile_version,
                    "target_mode": value.profile.target_mode.value,
                    "environment_code": value.profile.environment_code,
                    "profile_snapshot_hash": value.profile.snapshot_hash,
                    "projection_policy_id": value.profile.projection_policy_id,
                    "projection_policy_version": value.profile.projection_policy_version,
                    "projection_policy_hash": value.profile.projection_policy_hash,
                    "state": value.state.value,
                    "dispatch_allowed": int(value.dispatch_allowed),
                    "outbox_event_id": str(outbox_event_id) if outbox_event_id else None,
                    "result_global_id": None,
                    "actor_user_id": value.actor_user_id,
                    "service_actor_user_id": value.service_actor_user_id,
                    "request_id": str(value.request_id),
                    "trace_id": value.trace_id,
                    "idempotency_key_hash": value.idempotency_key_hash,
                    "target_idempotency_key_hash": value.target_idempotency_key_hash,
                    "semantic_effect_hash": value.semantic_effect_hash,
                    "payload_hash": value.payload_hash,
                    "optimistic_version": 1,
                    "created_at": _database_datetime(value.created_at),
                    "updated_at": _database_datetime(now),
                }
            ),
            capability=capability,
            ignore_links=outbox_event_id is not None,
        )

    @staticmethod
    def _insert_nodes(
        value: MbomPublishRequest,
        *,
        now: datetime,
        capability: MbomSupportWriteCapability,
    ) -> str:
        readiness = {item.engineering_item_id: item for item in value.item_readiness}
        expectations = {item.stable_line_key: item for item in value.mbom_expectations}
        roles = value.source.roles
        manifest: list[dict[str, object]] = []
        for line in value.source.lines:
            role = roles[line.stable_line_key]
            expectation = expectations.get(line.stable_line_key)
            node_snapshot = {
                "line": line.canonical_mapping(role),
                "itemReadiness": readiness[line.engineering_item_id].canonical_mapping(),
                "mbomExpectation": expectation.canonical_mapping() if expectation else None,
            }
            node_hash = canonical_hash(node_snapshot)
            node_id = uuid4()
            state = (
                "component_only"
                if role is MbomSourceRole.COMPONENT_ONLY
                else (
                    "blocked_item_mapping"
                    if value.profile.target_mode is MbomTargetMode.MOCK
                    else "queued"
                )
            )
            insert_mbom_support_document(
                frappe.get_doc(
                    {
                        "doctype": "NPI MBOM Publish Node",
                        "global_id": str(node_id),
                        "request_global_id": str(value.global_id),
                        "stable_line_key": line.stable_line_key,
                        "line_global_id": str(line.line_global_id),
                        "parent_line_key": line.parent_line_key,
                        "engineering_item_id": line.engineering_item_id,
                        "source_role": role.value,
                        "line_snapshot": line.canonical_mapping(role),
                        "line_hash": line.line_hash,
                        "assembly_source_key": expectation.assembly_source_key if expectation else None,
                        "item_readiness_snapshot": readiness[line.engineering_item_id].canonical_mapping(),
                        "mbom_expectation_snapshot": expectation.canonical_mapping() if expectation else None,
                        "state": state,
                        "result_global_id": None,
                        "node_snapshot_hash": node_hash,
                        "optimistic_version": 1,
                        "created_at": _database_datetime(now),
                        "updated_at": _database_datetime(now),
                    }
                ),
                capability=capability,
            )
            manifest.append(
                {"globalId": str(node_id), "stableLineKey": line.stable_line_key, "nodeSnapshotHash": node_hash}
            )
        return canonical_hash({"requestGlobalId": str(value.global_id), "nodes": manifest})

    @staticmethod
    def _insert_outbox(
        project: object,
        value: MbomPublishRequest,
        *,
        event_id: UUID,
        node_manifest_hash: str,
        capability: MbomSupportWriteCapability,
    ) -> None:
        payload = value.event_payload()
        payload_hash = canonical_hash(payload)
        event_hash = canonical_hash(
            {
                "schemaVersion": MBOM_PUBLISH_SCHEMA_VERSION,
                "eventId": str(event_id),
                "eventType": MBOM_REQUEST_EVENT_TYPE,
                "globalId": str(value.global_id),
                "objectVersion": 1,
                "tenantId": str(project.tenant_id),
                "projectGlobalId": str(project.global_id),
                "requestGlobalId": str(value.global_id),
                "operation": MBOM_PUBLISH_OPERATION,
                "profileId": value.profile.profile_id,
                "profileVersion": value.profile.profile_version,
                "profileSnapshotHash": value.profile.snapshot_hash,
                "sourceStreamKeyHash": value.source.source_stream_key_hash,
                "sourceHash": value.source.source_hash,
                "topologyHash": value.source.topology_hash,
                "itemMappingSetHash": value.item_mapping_set_hash,
                "mbomMappingSetHash": value.mbom_mapping_set_hash,
                "nodeManifestHash": node_manifest_hash,
                "actorUserId": value.actor_user_id,
                "serviceActorUserId": value.service_actor_user_id,
                "requestId": str(value.request_id),
                "traceId": value.trace_id,
                "idempotencyKeyHash": value.idempotency_key_hash,
                "targetIdempotencyKeyHash": value.target_idempotency_key_hash,
                "semanticEffectHash": value.semantic_effect_hash,
                "payloadHash": payload_hash,
            }
        )
        insert_mbom_support_document(
            frappe.get_doc(
                {
                    "doctype": "NPI Outbox Message",
                    "event_id": str(event_id),
                    "event_type": MBOM_REQUEST_EVENT_TYPE,
                    "global_id": str(value.global_id),
                    "object_version": 1,
                    "trace_id": value.trace_id,
                    "payload_hash": payload_hash,
                    "payload": payload,
                    "state": "pending",
                    "attempt_count": 0,
                    "schema_version": MBOM_PUBLISH_SCHEMA_VERSION,
                    "operation": MBOM_PUBLISH_OPERATION,
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "profile_id": value.profile.profile_id,
                    "profile_version": value.profile.profile_version,
                    "profile_snapshot_hash": value.profile.snapshot_hash,
                    "source_stream_key_hash": value.source.source_stream_key_hash,
                    "source_hash": value.source.source_hash,
                    "actor_user_id": value.actor_user_id,
                    "service_actor_user_id": value.service_actor_user_id,
                    "request_id": str(value.request_id),
                    "idempotency_key_hash": value.idempotency_key_hash,
                    "target_idempotency_key_hash": value.target_idempotency_key_hash,
                    "semantic_source_effect_hash": value.source.source_hash,
                    "semantic_effect_hash": value.semantic_effect_hash,
                    "event_snapshot_hash": event_hash,
                    "adapter_boundary_crossed": 0,
                    "disposition": "ready",
                    "mbom_request_global_id": str(value.global_id),
                    "mbom_topology_hash": value.source.topology_hash,
                    "item_mapping_set_hash": value.item_mapping_set_hash,
                    "mbom_mapping_set_hash": value.mbom_mapping_set_hash,
                    "mbom_node_manifest_hash": node_manifest_hash,
                }
            ),
            capability=capability,
        )

    def _insert_idempotency_receipt(
        self,
        project: object,
        value: MbomPublishRequest,
        *,
        scope_key: str,
        command_hash: str,
        response: Mapping[str, object],
        now: datetime,
        capability: MbomSupportWriteCapability,
    ) -> None:
        insert_mbom_support_document(
            frappe.get_doc(
                {
                    "doctype": "NPI MBOM Publish Command Idempotency",
                    "scope_key_hash": scope_key,
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "operation": MBOM_PUBLISH_OPERATION,
                    "actor_user_id": self.actor.casefold(),
                    "idempotency_key_hash": value.idempotency_key_hash,
                    "request_payload_hash": command_hash,
                    "request_global_id": str(value.global_id),
                    "response_snapshot": dict(response),
                    "response_hash": canonical_hash(response),
                    "created_at": _database_datetime(now),
                }
            ),
            capability=capability,
        )

    def _request_public_dict(self, project: object, row: object) -> dict[str, Any]:
        value = _request_value(project, row)
        return self._response_from_value(
            value,
            UUID(str(row.outbox_event_id)) if row.outbox_event_id else None,
            _datetime_value(row.updated_at),
        )

    @staticmethod
    def _response_from_value(
        value: MbomPublishRequest,
        outbox_event_id: UUID | None,
        updated_at: datetime,
    ) -> dict[str, Any]:
        return {
            "requestGlobalId": str(value.global_id),
            "request": {**value.payload(), "payloadHash": value.payload_hash},
            "outboxEventId": str(outbox_event_id) if outbox_event_id else None,
            "updatedAt": _utc_text(updated_at),
        }

    @staticmethod
    def _node_public_dict(project: object, request: object, row: object) -> dict[str, Any]:
        if (
            str(row.request_global_id) != str(request.global_id)
            or str(request.tenant_id) != str(project.tenant_id)
            or canonical_hash(
                {
                    "line": _json_object(row.line_snapshot),
                    "itemReadiness": _json_object(row.item_readiness_snapshot),
                    "mbomExpectation": (
                        _json_object(row.mbom_expectation_snapshot)
                        if row.mbom_expectation_snapshot
                        else None
                    ),
                }
            )
            != str(row.node_snapshot_hash)
        ):
            raise RuntimeError("Persisted MBOM node is invalid.")
        return {
            "globalId": str(row.global_id),
            "requestGlobalId": str(row.request_global_id),
            "line": _json_object(row.line_snapshot),
            "itemReadiness": _json_object(row.item_readiness_snapshot),
            "mbomExpectation": (
                _json_object(row.mbom_expectation_snapshot)
                if row.mbom_expectation_snapshot
                else None
            ),
            "state": str(row.state),
            "nodeSnapshotHash": str(row.node_snapshot_hash),
        }

    def _attempt_public_dicts(
        self,
        request_row: object,
        request: Mapping[str, Any],
    ) -> tuple[dict[str, Any], ...]:
        rows = self._bounded_documents(
            "NPI MBOM Publish Attempt",
            {"request_global_id": str(request["globalId"])},
            order_by="attempt_number asc, global_id asc",
            maximum=_MAX_ATTEMPTS,
        )
        values: list[dict[str, Any]] = []
        for row in rows:
            snapshot = _json_object(row.attempt_snapshot)
            if (
                canonical_hash(snapshot) != str(row.attempt_hash)
                or snapshot.get("globalId") != str(row.global_id)
                or snapshot.get("requestGlobalId") != str(request["globalId"])
                or str(row.request_global_id) != str(request["globalId"])
                or snapshot.get("outboxEventId") != str(row.outbox_event_id)
                or str(row.outbox_event_id) != str(request_row.outbox_event_id or "")
                or snapshot.get("attemptNumber") != int(row.attempt_number)
                or str(row.source_hash) != str(request["source"]["sourceHash"])
                or str(row.topology_hash) != str(request["source"]["topologyHash"])
                or str(row.item_mapping_set_hash) != str(request["itemMappingSetHash"])
                or str(row.mbom_mapping_set_hash) != str(request["mbomMappingSetHash"])
                or str(row.profile_id) != str(request["profile"]["profileId"])
                or int(row.profile_version) != int(request["profile"]["profileVersion"])
                or snapshot.get("state") != str(row.state)
                or snapshot.get("adapterBoundaryCrossed")
                is not bool(row.adapter_boundary_crossed)
                or snapshot.get("requestSnapshotHash")
                != str(row.request_snapshot_hash)
            ):
                raise RuntimeError("Persisted MBOM publish attempt is invalid.")
            values.append(
                {
                    "globalId": snapshot["globalId"],
                    "requestGlobalId": snapshot["requestGlobalId"],
                    "outboxEventId": snapshot["outboxEventId"],
                    "attemptNumber": snapshot["attemptNumber"],
                    "state": snapshot["state"],
                    "adapterBoundaryCrossed": snapshot["adapterBoundaryCrossed"],
                    "transportDisposition": snapshot.get("transportDisposition"),
                    "responseHash": snapshot.get("responseHash"),
                    "faultKind": snapshot.get("faultKind"),
                    "reconciliationRequired": snapshot["reconciliationRequired"],
                    "safeErrorCode": snapshot.get("safeErrorCode"),
                    "startedAt": snapshot["startedAt"],
                    "finishedAt": snapshot.get("finishedAt"),
                    "attemptHash": str(row.attempt_hash),
                }
            )
        return tuple(values)

    @staticmethod
    def _result_public_dict(
        request_row: object,
        request: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        if not request_row.result_global_id:
            if str(request["state"]) in _RETAINED_STATES:
                raise RuntimeError("Persisted MBOM publish result is unavailable.")
            return None
        try:
            row = frappe.get_doc(
                "NPI MBOM Publish Result",
                str(request_row.result_global_id),
            )
        except frappe.DoesNotExistError as error:
            raise RuntimeError("Persisted MBOM publish result is unavailable.") from error
        snapshot = _json_object(row.result_snapshot)
        if (
            canonical_hash(snapshot) != str(row.result_hash)
            or snapshot.get("globalId") != str(row.global_id)
            or str(row.global_id) != str(request_row.result_global_id)
            or snapshot.get("requestGlobalId") != str(request["globalId"])
            or str(row.request_global_id) != str(request["globalId"])
            or snapshot.get("outboxEventId") != str(row.outbox_event_id)
            or str(row.outbox_event_id) != str(request_row.outbox_event_id or "")
            or snapshot.get("attemptGlobalId") != str(row.attempt_global_id)
            or snapshot.get("attemptNumber") != int(row.attempt_number)
            or snapshot.get("sourceHash") != str(request["source"]["sourceHash"])
            or snapshot.get("topologyHash") != str(request["source"]["topologyHash"])
            or snapshot.get("itemMappingSetHash") != str(request["itemMappingSetHash"])
            or snapshot.get("mbomMappingSetHash") != str(request["mbomMappingSetHash"])
            or snapshot.get("state") != str(request["state"])
            or snapshot.get("nodeResultSetHash") != str(row.node_result_set_hash)
        ):
            raise RuntimeError("Persisted MBOM publish result is invalid.")
        return {
            **snapshot,
            "resultHash": str(row.result_hash),
        }

    def _node_result_public_dicts(
        self,
        project: object,
        request_row: object,
        request: Mapping[str, Any],
        nodes: Sequence[object],
        result: Mapping[str, Any] | None,
        *,
        can_view: bool,
    ) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
        if result is None:
            if any(getattr(node, "result_global_id", None) for node in nodes):
                raise RuntimeError("Persisted MBOM node result binding is invalid.")
            return (), ()
        assembly_nodes = {
            str(node.stable_line_key): node
            for node in nodes
            if str(_json_object(node.line_snapshot).get("sourceRole")) == "assembly"
        }
        rows = self._bounded_documents(
            "NPI MBOM Publish Node Result",
            {"result_global_id": str(result["globalId"])},
            order_by="stable_line_key asc, global_id asc",
            maximum=_MAX_NODES,
        )
        if len(rows) != len(assembly_nodes):
            raise RuntimeError("Persisted MBOM node result set is incomplete.")
        values: list[dict[str, Any]] = []
        mappings: list[dict[str, Any]] = []
        set_members: list[dict[str, str]] = []
        for row in rows:
            snapshot = _json_object(row.node_result_snapshot)
            node = assembly_nodes.get(str(row.stable_line_key))
            if (
                node is None
                or canonical_hash(snapshot) != str(row.node_result_hash)
                or snapshot.get("globalId") != str(row.global_id)
                or snapshot.get("requestGlobalId") != str(request["globalId"])
                or str(row.request_global_id) != str(request["globalId"])
                or snapshot.get("resultGlobalId") != str(result["globalId"])
                or str(row.result_global_id) != str(result["globalId"])
                or snapshot.get("attemptGlobalId") != str(result["attemptGlobalId"])
                or str(row.attempt_global_id) != str(result["attemptGlobalId"])
                or snapshot.get("nodeGlobalId") != str(node.global_id)
                or str(row.node_global_id) != str(node.global_id)
                or snapshot.get("stableLineKey") != str(row.stable_line_key)
                or snapshot.get("assemblySourceKey") != str(row.assembly_source_key)
                or snapshot.get("state") != str(row.state)
                or snapshot.get("authority") != str(row.authority)
                or snapshot.get("responseAuthenticated")
                is not bool(row.response_authenticated)
                or snapshot.get("responseHash") != str(row.response_hash)
                or str(getattr(node, "result_global_id", "")) != str(row.global_id)
            ):
                raise RuntimeError("Persisted MBOM node result is invalid.")
            current = self._current_mapping_public_dict(
                project,
                request,
                row,
                snapshot,
                can_view=can_view,
            )
            public = {
                **snapshot,
                "formalBomId": current["formalBomId"] if current else None,
                "targetVersion": current["targetVersion"] if current else None,
                "targetSubmissionState": (
                    current["targetSubmissionState"] if current else None
                ),
                "nodeResultHash": str(row.node_result_hash),
            }
            values.append(public)
            if current is not None:
                mappings.append(current)
            set_members.append(
                {
                    "globalId": str(row.global_id),
                    "nodeResultHash": str(row.node_result_hash),
                }
            )
        if canonical_hash(set_members) != str(result["nodeResultSetHash"]):
            raise RuntimeError("Persisted MBOM node result set is invalid.")
        return tuple(values), tuple(mappings)

    @staticmethod
    def _current_mapping_public_dict(
        project: object,
        request: Mapping[str, Any],
        node_result: object,
        node_snapshot: Mapping[str, Any],
        *,
        can_view: bool,
    ) -> dict[str, Any] | None:
        authoritative = (
            node_snapshot.get("state") == "succeeded_authoritative"
            and node_snapshot.get("authority") == "authoritative_sandbox"
            and node_snapshot.get("responseAuthenticated") is True
        )
        if not authoritative:
            if any(
                node_snapshot.get(key) is not None
                for key in ("formalBomId", "targetVersion", "targetSubmissionState")
            ):
                raise RuntimeError("Non-authoritative MBOM result contains target identity.")
            return None
        name = frappe.db.get_value(
            "NPI MBOM Mapping Head",
            {"assembly_source_key": str(node_result.assembly_source_key)},
            "name",
        )
        if not name:
            raise RuntimeError("Current MBOM mapping evidence is unavailable.")
        try:
            head = frappe.get_doc("NPI MBOM Mapping Head", str(name))
            observation = frappe.get_doc(
                "NPI MBOM Mapping Observation",
                str(head.current_observation),
            )
        except frappe.DoesNotExistError as error:
            raise RuntimeError("Current MBOM mapping evidence is unavailable.") from error
        head_snapshot = _json_object(head.head_snapshot)
        observation_snapshot = _json_object(observation.observation_snapshot)
        if (
            canonical_hash(head_snapshot) != str(head.head_hash)
            or canonical_hash(observation_snapshot) != str(observation.observation_hash)
            or head_snapshot.get("globalId") != str(head.global_id)
            or head_snapshot.get("tenantId") != str(project.tenant_id)
            or head_snapshot.get("projectGlobalId") != str(project.global_id)
            or head_snapshot.get("ebomGlobalId") != str(request["source"]["ebomGlobalId"])
            or head_snapshot.get("assemblySourceKey")
            != str(node_result.assembly_source_key)
            or head_snapshot.get("stableLineKey") != str(node_result.stable_line_key)
            or head_snapshot.get("currentObservationGlobalId")
            != str(observation.global_id)
            or head_snapshot.get("currentObservationHash")
            != str(observation.observation_hash)
            or observation_snapshot.get("requestGlobalId")
            != str(request["globalId"])
            or observation_snapshot.get("resultGlobalId")
            != str(node_result.result_global_id)
            or observation_snapshot.get("nodeResultGlobalId")
            != str(node_result.global_id)
            or observation_snapshot.get("targetResultHash")
            != str(node_result.node_result_hash)
            or observation_snapshot.get("authority") != "authoritative_sandbox"
            or observation_snapshot.get("disposition") != "advanced"
            or observation_snapshot.get("formalBomId")
            != node_snapshot.get("formalBomId")
            or observation_snapshot.get("targetVersion")
            != node_snapshot.get("targetVersion")
            or observation_snapshot.get("targetSubmissionState")
            != node_snapshot.get("targetSubmissionState")
            or head_snapshot.get("formalBomId") != node_snapshot.get("formalBomId")
            or head_snapshot.get("targetVersion") != node_snapshot.get("targetVersion")
            or head_snapshot.get("targetSubmissionState")
            != node_snapshot.get("targetSubmissionState")
        ):
            raise RuntimeError("Current MBOM mapping evidence is invalid.")
        if not can_view:
            return None
        return {
            "stableLineKey": str(node_result.stable_line_key),
            "assemblySourceKey": str(node_result.assembly_source_key),
            "mappingVersion": int(head_snapshot["mappingVersion"]),
            "formalBomId": str(head_snapshot["formalBomId"]),
            "targetVersion": str(head_snapshot["targetVersion"]),
            "targetSubmissionState": str(head_snapshot["targetSubmissionState"]),
            "authority": "authoritative_sandbox",
            "responseAuthenticated": True,
            "observationHash": str(observation.observation_hash),
            "updatedAt": str(head_snapshot["updatedAt"]),
        }


def _source_from_phase5(project: object, request: object) -> MbomSourceSnapshot:
    lines = tuple(
        MbomSourceLine(
            line_global_id=node.line.global_id,
            stable_line_key=node.line.line_key,
            parent_line_key=node.line.parent_line_key,
            engineering_item_id=node.line.engineering_item_id,
            quantity=node.line.quantity,
            engineering_uom=node.line.engineering_uom,
            alternates=tuple(
                value
                for value in (
                    node.line.alternate_for_line_key,
                    node.line.alternate_group_key,
                )
                if value
            ),
            effectivity=tuple(
                (key, value)
                for key, value in (
                    ("start", node.line.effectivity_start),
                    ("end", node.line.effectivity_end),
                )
                if value
            ),
            attributes=tuple(node.line.attributes),
            line_hash=node.line.line_hash,
        )
        for node in request.nodes
    )
    evidence = request.evidence
    return MbomSourceSnapshot(
        tenant_id=str(project.tenant_id),
        project_global_id=UUID(str(project.global_id)),
        ebom_global_id=evidence.ebom_global_id,
        phase5_publish_request_global_id=request.global_id,
        phase5_publish_request_payload_hash=request.payload_hash,
        publish_policy_global_id=request.policy.global_id,
        publish_policy_version=request.policy.version,
        publish_policy_snapshot_hash=request.policy.snapshot_hash,
        revision_global_id=evidence.revision_global_id,
        revision_number=evidence.revision_number,
        revision_snapshot_hash=evidence.revision_snapshot_hash,
        lifecycle_version=evidence.lifecycle_version,
        release_event_global_id=evidence.release_event_global_id,
        release_event_hash=evidence.release_event_hash,
        approval_evidence_ids=evidence.approval_evidence_ids,
        released_at=evidence.released_at,
        lines=lines,
    )


def _item_stream_key(tenant_id: str, project_id: UUID, engineering_item_id: str) -> str:
    return canonical_hash(
        {
            "schemaVersion": 1,
            "tenantId": tenant_id,
            "projectGlobalId": str(project_id),
            "engineeringItemId": engineering_item_id,
        }
    )


def _locked_stream_guard(
    source: MbomSourceSnapshot,
    *,
    create: bool,
    now: datetime,
    capability: MbomSupportWriteCapability,
) -> object:
    try:
        return frappe.get_doc(
            "NPI MBOM Publish Stream Guard",
            source.source_stream_key_hash,
            for_update=True,
        )
    except frappe.DoesNotExistError:
        if not create:
            raise
    guard = frappe.get_doc(
        {
            "doctype": "NPI MBOM Publish Stream Guard",
            "source_stream_key_hash": source.source_stream_key_hash,
            "tenant_id": source.tenant_id,
            "project_global_id": str(source.project_global_id),
            "ebom_global_id": str(source.ebom_global_id),
            "active_request_global_id": None,
            "active_target_idempotency_key_hash": None,
            "active_state": None,
            "last_request_global_id": None,
            "last_target_idempotency_key_hash": None,
            "last_state": None,
            "blocked_reason_code": None,
            "optimistic_version": 1,
            "updated_at": _database_datetime(now),
        }
    )
    insert_mbom_support_document(guard, capability=capability)
    return guard


def _stream_guard_problem(guard: object, value: MbomPublishRequest) -> NpiProblem | None:
    if (
        str(guard.tenant_id) != value.source.tenant_id
        or str(guard.project_global_id) != str(value.source.project_global_id)
        or str(guard.ebom_global_id) != str(value.source.ebom_global_id)
        or str(guard.source_stream_key_hash) != value.source.source_stream_key_hash
    ):
        raise RuntimeError("Persisted MBOM stream guard scope is invalid.")
    active_state = str(guard.active_state or "")
    if active_state:
        if active_state not in _ACTIVE_STATES:
            raise RuntimeError("Persisted MBOM active stream state is invalid.")
        return (
            MbomPublishReconciliationRequired()
            if active_state == MbomPublishRequestState.UNCERTAIN_AFTER_TIMEOUT.value
            else MbomPublishStreamActive()
        )
    last_state = str(guard.last_state or "")
    if last_state and last_state not in _RETAINED_STATES:
        raise RuntimeError("Persisted MBOM retained stream state is invalid.")
    if (
        last_state
        and str(guard.last_target_idempotency_key_hash or "")
        == value.target_idempotency_key_hash
    ):
        return MbomPublishEffectRetained()
    return None


def _activate_stream_guard(
    guard: object,
    value: MbomPublishRequest,
    *,
    now: datetime,
    capability: MbomSupportWriteCapability,
) -> None:
    guard.active_request_global_id = str(value.global_id)
    guard.active_target_idempotency_key_hash = value.target_idempotency_key_hash
    guard.active_state = value.state.value
    guard.blocked_reason_code = None
    guard.optimistic_version = int(guard.optimistic_version) + 1
    guard.updated_at = _database_datetime(now)
    save_mbom_support_document(guard, capability=capability)


def _request_value(project: object, row: object) -> MbomPublishRequest:
    source = _source_value(_json_object(row.source_snapshot))
    profile = MbomExecutionProfileReference(
        profile_id=str(row.profile_id),
        profile_version=int(row.profile_version),
        target_mode=MbomTargetMode(str(row.target_mode)),
        environment_code=str(row.environment_code),
        projection_policy_id=str(row.projection_policy_id),
        projection_policy_version=int(row.projection_policy_version),
        projection_policy_hash=str(row.projection_policy_hash),
        snapshot_hash=str(row.profile_snapshot_hash),
    )
    readiness = tuple(
        _readiness_value(value) for value in _json_array(row.item_readiness_snapshot)
    )
    expectations = tuple(
        _expectation_value(value) for value in _json_array(row.mbom_expectation_snapshot)
    )
    value = MbomPublishRequest(
        global_id=UUID(str(row.global_id)),
        source=source,
        item_readiness=readiness,
        item_mapping_set_hash=str(row.item_mapping_set_hash),
        mbom_expectations=expectations,
        mbom_mapping_set_hash=str(row.mbom_mapping_set_hash),
        profile=profile,
        actor_user_id=str(row.actor_user_id),
        service_actor_user_id=row.service_actor_user_id or None,
        request_id=UUID(str(row.request_id)),
        trace_id=str(row.trace_id),
        idempotency_key_hash=str(row.idempotency_key_hash),
        target_idempotency_key_hash=str(row.target_idempotency_key_hash),
        semantic_effect_hash=str(row.semantic_effect_hash),
        state=MbomPublishRequestState(str(row.state)),
        dispatch_allowed=bool(row.dispatch_allowed),
        payload_hash=str(row.payload_hash),
        created_at=_datetime_value(row.created_at),
    )
    if (
        str(row.tenant_id) != str(project.tenant_id)
        or str(row.project_global_id) != str(project.global_id)
        or str(row.phase5_publish_request_global_id) != str(source.phase5_publish_request_global_id)
        or str(row.ebom_global_id) != str(source.ebom_global_id)
    ):
        raise RuntimeError("Persisted MBOM request scope is invalid.")
    return value


def _source_value(value: Mapping[str, object]) -> MbomSourceSnapshot:
    topology = value["topology"]
    if not isinstance(topology, dict):
        raise RuntimeError("Persisted MBOM topology is invalid.")
    return MbomSourceSnapshot(
        tenant_id=str(value["tenantId"]),
        project_global_id=UUID(str(value["projectGlobalId"])),
        ebom_global_id=UUID(str(value["ebomGlobalId"])),
        phase5_publish_request_global_id=UUID(str(value["phase5PublishRequestGlobalId"])),
        phase5_publish_request_payload_hash=str(value["phase5PublishRequestPayloadHash"]),
        publish_policy_global_id=UUID(str(value["publishPolicyGlobalId"])),
        publish_policy_version=int(value["publishPolicyVersion"]),
        publish_policy_snapshot_hash=str(value["publishPolicySnapshotHash"]),
        revision_global_id=UUID(str(topology["revisionGlobalId"])),
        revision_number=int(topology["revisionNumber"]),
        revision_snapshot_hash=str(topology["revisionSnapshotHash"]),
        lifecycle_version=int(value["lifecycleVersion"]),
        release_event_global_id=UUID(str(value["releaseEventGlobalId"])),
        release_event_hash=str(value["releaseEventHash"]),
        approval_evidence_ids=tuple(UUID(str(item)) for item in value["approvalEvidenceIds"]),
        released_at=_datetime_value(value["releasedAt"]),
        lines=tuple(_line_value(item) for item in topology["lines"]),
        source_stream_key_hash=str(value["sourceStreamKeyHash"]),
        topology_hash=str(value["topologyHash"]),
        source_hash=str(value["sourceHash"]),
    )


def _line_value(value: Mapping[str, object]) -> MbomSourceLine:
    return MbomSourceLine(
        line_global_id=UUID(str(value["lineGlobalId"])),
        stable_line_key=str(value["stableLineKey"]),
        parent_line_key=value["parentLineKey"],
        engineering_item_id=str(value["engineeringItemId"]),
        quantity=str(value["quantity"]),
        engineering_uom=str(value["engineeringUom"]),
        alternates=tuple(str(item) for item in value["alternates"]),
        effectivity=tuple(sorted(dict(value["effectivity"]).items())),
        attributes=tuple(sorted(dict(value["attributes"]).items())),
        line_hash=str(value["lineHash"]),
    )


def _readiness_value(value: Mapping[str, object]) -> ItemMappingReadiness:
    return ItemMappingReadiness(
        engineering_item_id=str(value["engineeringItemId"]),
        disposition=ItemReadinessDisposition(str(value["disposition"])),
        item_stream_key_hash=str(value["itemStreamKeyHash"]),
        mapping_version=int(value["mappingVersion"]),
        formal_item_code=value["formalItemCode"],
        target_version=value["targetVersion"],
        observation_hash=value["observationHash"],
        authority=MbomResultAuthority(str(value["authority"])),
        response_authenticated=bool(value["responseAuthenticated"]),
        synthetic_item_reference=value["syntheticItemReference"],
    )


def _expectation_value(value: Mapping[str, object]) -> MbomMappingExpectation:
    return MbomMappingExpectation(
        assembly_source_key=str(value["assemblySourceKey"]),
        stable_line_key=str(value["stableLineKey"]),
        mapping_version=int(value["mappingVersion"]),
        submission_state=MbomTargetSubmissionState(str(value["submissionState"])),
        formal_bom_id=value["formalBomId"],
        target_version=value["targetVersion"],
        observation_hash=value["observationHash"],
    )


def _datetime_value(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise RuntimeError("Persisted MBOM datetime is invalid.") from error
    else:
        raise RuntimeError("Persisted MBOM datetime is invalid.")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


__all__ = ["FrappeMbomPublishRepository", "MbomPublishCommandOutcome"]
