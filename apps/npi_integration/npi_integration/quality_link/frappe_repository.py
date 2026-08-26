from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping
from uuid import UUID, uuid4, uuid5

import frappe

from npi_core.documents.frappe_repository import FrappeDocumentRepository
from npi_core.foundation.audit import create_audit_event
from npi_core.foundation.security import Principal
from npi_core.project_controls.terminal_guard import require_mutable_project
from npi_core.readiness.frappe_repository import (
    FrappeReadinessRepository,
    _project_revision_chain,
)
from npi_core.trial.quality_repository import FrappeTrialQualityRepository
from npi_core.trial.review_repository import FrappeTrialReviewRepository
from npi_integration.quality_link.domain import (
    QUALITY_LINK_OPERATION,
    QUALITY_LINK_SCHEMA_VERSION,
    FormalQualityObservationReference,
    FormalQualityRecordKind,
    QualityLinkCommandIdentity,
    QualityLinkContractError,
    QualityLinkReconciliationReason,
    QualityLinkReconciliationState,
    QualityLinkRevision,
    QualityLinkState,
    QualitySourceKind,
    QualitySourceReference,
    canonical_payload_hash,
    quality_link_reconciliation,
)
from npi_integration.quality_link.frappe_validation import (
    quality_link_command_write,
)
from npi_integration.quality_link.problems import (
    FormalQualityLinkAuthorityUnavailable,
    FormalQualityLinkHeadConflict,
    FormalQualityLinkIdempotencyConflict,
    FormalQualityLinkSourceConflict,
    FormalQualityProjectionConflict,
)


_MAX_LINKS = 1_000
_HEAD_NAMESPACE = UUID("6f1ed39f-d156-5932-a345-3cfb913bd95e")
_PROJECTION_HEAD_SNAPSHOT_FIELDS = {
    "schemaVersion",
    "globalId",
    "tenantId",
    "projectGlobalId",
    "scopeKind",
    "scopeGlobalId",
    "projectionKind",
    "sourceObjectType",
    "sourceObjectId",
    "streamKeyHash",
    "currentObservationGlobalId",
    "lastRefreshObservationGlobalId",
    "currentSourceVersion",
    "currentSourceModifiedAt",
    "currentPayloadHash",
    "availability",
    "freshness",
    "freshnessPolicyRef",
    "optimisticVersion",
    "updatedAt",
}


@dataclass(frozen=True, slots=True)
class FormalQualityLinkCommandOutcome:
    response: dict[str, Any]
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class _ResolvedSource:
    reference: QualitySourceReference
    scope_kind: str
    scope_global_id: UUID


class FrappeFormalQualityLinkRepository(FrappeDocumentRepository):
    """Project-first NPI link history; ERP observations remain read-only."""

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
        *,
        administer: bool = False,
    ) -> bool:
        project = self._authorized_project(project_id)
        if project is None:
            return False
        return not administer or self._can_administer_project(project, project_id)

    def list_quality_links(self, project_id: UUID) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        names = frappe.get_all(
            "NPI Formal Quality Link Head",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
            },
            pluck="name",
            order_by="source_kind asc, source_global_id asc, global_id asc",
            limit_page_length=_MAX_LINKS + 1,
        )
        if len(names) > _MAX_LINKS:
            raise RuntimeError("Persisted formal quality link collection exceeds its safe bound.")
        items = [
            self._link_item(project, frappe.get_doc("NPI Formal Quality Link Head", str(name)))
            for name in names
        ]
        return {
            "projectGlobalId": str(project.global_id),
            "permissions": {"view": True, "link": False},
            "items": items,
        }

    def quality_link_detail(
        self,
        project_id: UUID,
        link_head_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        head = _optional_doc("NPI Formal Quality Link Head", link_head_id)
        if head is None or not self._head_matches_project(project, head, link_head_id):
            return None
        return {
            "projectGlobalId": str(project.global_id),
            "permissions": {"view": True, "link": False},
            "link": self._link_item(project, head),
        }

    def link_observed_formal_quality_reference(
        self,
        project_id: UUID,
        *,
        source_kind: QualitySourceKind,
        source_global_id: UUID,
        expected_source_version: int,
        expected_source_snapshot_hash: str,
        observation_global_id: UUID,
        expected_projection_head_global_id: UUID,
        expected_projection_head_version: int,
        expected_projection_head_hash: str,
        expected_link_head_version: int,
        idempotency_key_hash: str,
    ) -> FormalQualityLinkCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        require_mutable_project(project)

        command_payload = {
            "operation": QUALITY_LINK_OPERATION,
            "sourceKind": source_kind.value,
            "sourceGlobalId": str(source_global_id),
            "expectedSourceVersion": expected_source_version,
            "expectedSourceSnapshotHash": expected_source_snapshot_hash,
            "formalObservationGlobalId": str(observation_global_id),
            "expectedProjectionHeadGlobalId": str(expected_projection_head_global_id),
            "expectedProjectionHeadVersion": expected_projection_head_version,
            "expectedProjectionHeadHash": expected_projection_head_hash,
            "expectedLinkHeadVersion": expected_link_head_version,
        }
        payload_hash = canonical_payload_hash(command_payload)
        identity = QualityLinkCommandIdentity(
            str(project.tenant_id),
            UUID(str(project.global_id)),
            self.actor.casefold(),
            QUALITY_LINK_OPERATION,
            idempotency_key_hash,
            payload_hash,
            expected_source_snapshot_hash,
            expected_projection_head_hash,
        )
        replay = self._receipt_replay(project, identity)
        if replay is not None:
            return FormalQualityLinkCommandOutcome(replay, replayed=True)

        source = self._resolve_source(
            project,
            source_kind=source_kind,
            source_global_id=source_global_id,
            expected_version=expected_source_version,
            expected_snapshot_hash=expected_source_snapshot_hash,
        )
        observation = self._resolve_observation(
            project,
            source=source,
            observation_global_id=observation_global_id,
            expected_head_global_id=expected_projection_head_global_id,
            expected_head_version=expected_projection_head_version,
            expected_head_hash=expected_projection_head_hash,
        )
        stream_key_hash = canonical_payload_hash(
            {
                "tenantId": str(project.tenant_id),
                "projectGlobalId": str(project.global_id),
                "sourceKind": source_kind.value,
                "sourceGlobalId": str(source_global_id),
            }
        )
        head = self._locked_link_head(stream_key_hash)
        if head is None:
            if expected_link_head_version != 0:
                raise FormalQualityLinkHeadConflict()
            revision_number = 1
            predecessor_id = None
            link_head_id = uuid5(_HEAD_NAMESPACE, stream_key_hash)
        else:
            self._require_link_head_identity(
                project,
                head,
                source.reference,
                stream_key_hash,
            )
            if int(head.optimistic_version) != expected_link_head_version:
                raise FormalQualityLinkHeadConflict()
            revision_number = int(head.revision_number) + 1
            predecessor_id = UUID(str(head.current_revision))
            link_head_id = UUID(str(head.global_id))

        now = datetime.now(UTC)
        revision = QualityLinkRevision(
            uuid4(),
            stream_key_hash,
            revision_number,
            predecessor_id,
            source.reference,
            observation,
            QualityLinkState.LINKED,
            self.actor,
            self.trace_id,
            now,
        )
        revision_response = {**revision.payload(), "linkHash": revision.payload_hash}
        head_response = _head_response(
            global_id=link_head_id,
            project=project,
            source=source.reference,
            stream_key_hash=stream_key_hash,
            revision=revision,
            optimistic_version=(1 if head is None else int(head.optimistic_version) + 1),
            updated_at=now,
        )
        response = {
            "projectGlobalId": str(project.global_id),
            "operation": QUALITY_LINK_OPERATION,
            "linkRevision": revision_response,
            "linkHead": head_response,
            "formalQualityInterpretation": {
                "state": "unavailable",
                "reasonCode": "raw_formal_quality_codes_not_interpreted",
            },
        }

        with quality_link_command_write(
            scope=f"{QUALITY_LINK_OPERATION}:{project.global_id}",
        ):
            receipt = self._insert_receipt(project, identity, now)
            self._insert_revision(revision)
            if head is None:
                self._insert_head(head_response)
            else:
                self._advance_head(head, head_response)
            self._append_audit(
                revision,
                source_snapshot_hash=source.reference.source_snapshot_hash,
                projection_head_hash=observation.head_hash,
            )
            self._seal_receipt(receipt, revision, response, now)
        return FormalQualityLinkCommandOutcome(response)

    def _resolve_source(
        self,
        project: object,
        *,
        source_kind: QualitySourceKind,
        source_global_id: UUID,
        expected_version: int,
        expected_snapshot_hash: str,
    ) -> _ResolvedSource:
        if source_kind is QualitySourceKind.TRIAL_DEFECT:
            repository = FrappeTrialQualityRepository(
                principal=self.principal,
                request_id=self.request_id,
                trace_id=self.trace_id,
            )
            chain = repository._trial_defect_chain(
                project,
                defect_id=source_global_id,
                for_update=True,
            )
            if not chain:
                raise FormalQualityLinkSourceConflict()
            current = chain[-1]
            workspace = repository.quality_workspace(
                UUID(str(project.global_id)),
                current.trial_round_global_id,
            )
            permitted = bool(
                workspace
                and isinstance(workspace.get("permissions"), dict)
                and workspace["permissions"].get("manageDefects") is True
            )
            version = current.defect_version
            state = current.state.value
            snapshot_hash = current.snapshot_hash
            scope_kind = "trial_round"
            scope_global_id = current.trial_round_global_id
        elif source_kind is QualitySourceKind.TRIAL_REVIEW:
            repository = FrappeTrialReviewRepository(
                principal=self.principal,
                request_id=self.request_id,
                trace_id=self.trace_id,
            )
            names = frappe.get_all(
                "NPI Trial Review Reference Revision",
                filters={
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "reference_global_id": str(source_global_id),
                },
                fields=["trial_round_global_id"],
                order_by="reference_version asc, global_id asc",
                limit_page_length=2,
            )
            round_ids = {_row_value(row, "trial_round_global_id") for row in names}
            if len(round_ids) != 1:
                raise FormalQualityLinkSourceConflict()
            round_id = UUID(str(next(iter(round_ids))))
            chain = repository._reference_chain(project, round_id, source_global_id)
            if not chain:
                raise FormalQualityLinkSourceConflict()
            current = chain[-1]
            workspace = repository.review_workspace(UUID(str(project.global_id)), round_id)
            permitted = bool(
                workspace
                and isinstance(workspace.get("permissions"), dict)
                and workspace["permissions"].get("manageReviewReferences") is True
            )
            version = current.reference_version
            state = "current"
            snapshot_hash = current.snapshot_hash
            scope_kind = "trial_round"
            scope_global_id = current.trial_round_global_id
        elif source_kind is QualitySourceKind.READINESS_ASSESSMENT:
            repository = FrappeReadinessRepository(
                principal=self.principal,
                request_id=self.request_id,
                trace_id=self.trace_id,
            )
            chain = _project_revision_chain(project)
            if not chain or chain[-1].instance_global_id != source_global_id:
                raise FormalQualityLinkSourceConflict()
            current = chain[-1]
            workspace = repository.readiness_workspace(UUID(str(project.global_id)))
            permitted = bool(
                workspace
                and isinstance(workspace.get("permissions"), dict)
                and workspace["permissions"].get("canRevise") is True
            )
            version = current.instance_version
            state = "ready" if current.evaluation.ready else "not_ready"
            snapshot_hash = current.snapshot_hash
            scope_kind = "readiness"
            scope_global_id = current.instance_global_id
        else:
            raise FormalQualityLinkAuthorityUnavailable()

        if not permitted:
            raise FormalQualityLinkAuthorityUnavailable()
        if version != expected_version or snapshot_hash != expected_snapshot_hash:
            raise FormalQualityLinkSourceConflict()
        reference = QualitySourceReference(
            str(project.tenant_id),
            UUID(str(project.global_id)),
            source_kind,
            source_global_id,
            version,
            state,
            snapshot_hash,
        )
        return _ResolvedSource(reference, scope_kind, scope_global_id)

    def _resolve_observation(
        self,
        project: object,
        *,
        source: _ResolvedSource,
        observation_global_id: UUID,
        expected_head_global_id: UUID,
        expected_head_version: int,
        expected_head_hash: str,
    ) -> FormalQualityObservationReference:
        head = _optional_doc(
            "NPI ERP Projection Head",
            expected_head_global_id,
            for_update=True,
        )
        observation = _optional_doc(
            "NPI ERP Projection Observation",
            observation_global_id,
        )
        if head is None or observation is None:
            raise FormalQualityProjectionConflict()
        expected_scope = (source.scope_kind, str(source.scope_global_id))
        head_scope = (str(head.scope_kind), str(head.scope_global_id))
        observation_scope = (
            str(observation.scope_kind),
            str(observation.scope_global_id),
        )
        if (
            str(head.global_id) != str(expected_head_global_id)
            or str(head.tenant_id) != str(project.tenant_id)
            or str(head.project_global_id) != str(project.global_id)
            or head_scope != expected_scope
            or str(head.projection_kind) != "formal_quality_status"
            or str(head.current_observation) != str(observation_global_id)
            or int(head.optimistic_version) != expected_head_version
            or str(head.head_hash) != expected_head_hash
            or str(head.availability) != "available"
            or str(head.freshness) != "fresh"
            or not head.freshness_policy_ref
            or canonical_payload_hash(_json_object(head.head_snapshot))
            != str(head.head_hash)
            or str(observation.global_id) != str(observation_global_id)
            or str(observation.tenant_id) != str(project.tenant_id)
            or str(observation.project_global_id) != str(project.global_id)
            or observation_scope != expected_scope
            or str(observation.projection_kind) != "formal_quality_status"
            or str(observation.source_system) != "ERPNEXT"
            or str(observation.target_system) != "NPI_ONE"
            or str(observation.adapter_mode) != "sandbox"
            or str(observation.availability) != "available"
            or str(observation.freshness) != "fresh"
            or str(observation.disposition) != "applied_current"
            or str(observation.source_object_type) != str(head.source_object_type)
            or str(observation.source_object_id) != str(head.source_object_id)
            or str(observation.source_version) != str(head.current_source_version)
            or str(observation.payload_hash) != str(head.current_payload_hash)
            or canonical_payload_hash(_json_object(observation.observation_snapshot))
            != str(observation.observation_hash)
        ):
            raise FormalQualityProjectionConflict()
        payload = _json_object(observation.payload)
        values = payload.get("values")
        if not isinstance(values, dict) or set(values) != {
            "recordKind",
            "statusCode",
            "resultCode",
            "observedAt",
        }:
            raise FormalQualityProjectionConflict()
        try:
            return FormalQualityObservationReference(
                str(project.tenant_id),
                UUID(str(project.global_id)),
                source.scope_kind,
                source.scope_global_id,
                observation_global_id,
                expected_head_global_id,
                expected_head_version,
                str(observation.source_object_type),
                str(observation.source_object_id),
                str(observation.source_version),
                FormalQualityRecordKind(str(values["recordKind"])),
                str(values["statusCode"]),
                values["resultCode"],
                str(observation.payload_hash),
                str(observation.observation_hash),
                str(head.head_hash),
                str(head.freshness_policy_ref),
            )
        except (TypeError, ValueError) as error:
            raise FormalQualityProjectionConflict() from error

    def _receipt_replay(
        self,
        project: object,
        identity: QualityLinkCommandIdentity,
    ) -> dict[str, Any] | None:
        name = frappe.db.get_value(
            "NPI Formal Quality Link Command Idempotency",
            {"receipt_key_hash": identity.receipt_key_hash},
            "name",
        )
        if not name:
            return None
        receipt = frappe.get_doc(
            "NPI Formal Quality Link Command Idempotency",
            str(name),
            for_update=True,
        )
        expected = identity.payload()
        if any(
            str(getattr(receipt, field)) != str(expected[key])
            for field, key in (
                ("tenant_id", "tenantId"),
                ("project_global_id", "projectGlobalId"),
                ("actor_user_id", "actorUserId"),
                ("operation", "operation"),
                ("idempotency_key_hash", "idempotencyKeyHash"),
                ("payload_hash", "payloadHash"),
                ("source_snapshot_hash", "sourceSnapshotHash"),
                ("projection_head_hash", "projectionHeadHash"),
            )
        ):
            raise FormalQualityLinkIdempotencyConflict()
        response = _json_object(receipt.response_payload)
        if (
            int(receipt.sealed or 0) != 1
            or not receipt.link_revision_global_id
            or canonical_payload_hash(response) != str(receipt.response_hash)
        ):
            raise RuntimeError("Persisted formal quality link receipt is invalid.")
        return response

    def _locked_link_head(self, stream_key_hash: str) -> object | None:
        name = frappe.db.get_value(
            "NPI Formal Quality Link Head",
            {"stream_key_hash": stream_key_hash},
            "name",
        )
        if not name:
            return None
        return frappe.get_doc("NPI Formal Quality Link Head", str(name), for_update=True)

    @staticmethod
    def _require_link_head_identity(
        project: object,
        head: object,
        source: QualitySourceReference,
        stream_key_hash: str,
    ) -> None:
        snapshot = _json_object(head.head_snapshot)
        if (
            str(head.tenant_id) != str(project.tenant_id)
            or str(head.project_global_id) != str(project.global_id)
            or str(head.source_kind) != source.source_kind.value
            or str(head.source_global_id) != str(source.source_global_id)
            or str(head.stream_key_hash) != stream_key_hash
            or canonical_payload_hash(snapshot) != str(head.head_hash)
        ):
            raise FormalQualityLinkHeadConflict()

    def _link_item(self, project: object, head: object) -> dict[str, Any]:
        if not self._head_matches_project(project, head, UUID(str(head.global_id))):
            raise RuntimeError("Persisted formal quality link escaped its Project.")
        head_payload = _json_object(head.head_snapshot)
        if canonical_payload_hash(head_payload) != str(head.head_hash):
            raise RuntimeError("Persisted formal quality link head integrity failed.")
        revision = frappe.get_doc(
            "NPI Formal Quality Link Revision",
            str(head.current_revision),
        )
        revision_payload = _json_object(revision.link_snapshot)
        if (
            str(revision.project_global_id) != str(project.global_id)
            or str(revision.global_id) != str(head.current_revision)
            or canonical_payload_hash(revision_payload) != str(revision.link_hash)
        ):
            raise RuntimeError("Persisted formal quality link revision integrity failed.")
        return {
            "linkHead": {**head_payload, "headHash": str(head.head_hash)},
            "linkRevision": {
                **revision_payload,
                "linkHash": str(revision.link_hash),
            },
            "reconciliation": self._link_reconciliation(
                project,
                revision_payload,
            ),
            "formalQualityInterpretation": {
                "state": "unavailable",
                "reasonCode": "raw_formal_quality_codes_not_interpreted",
            },
        }

    def _link_reconciliation(
        self,
        project: object,
        revision_payload: Mapping[str, Any],
    ) -> dict[str, str]:
        try:
            source, observation = _linked_references(revision_payload)
            source_state = self._source_currentness(project, source, observation)
            projection_state = self._projection_currentness(
                project,
                observation,
            )
            return quality_link_reconciliation(
                source_state,
                projection_state,
            ).payload()
        except (
            AttributeError,
            KeyError,
            QualityLinkContractError,
            RuntimeError,
            TypeError,
            ValueError,
        ):
            return {
                "state": QualityLinkReconciliationState.UNAVAILABLE.value,
                "reasonCode": QualityLinkReconciliationReason.CURRENT_TRUTH_UNAVAILABLE.value,
            }

    def _source_currentness(
        self,
        project: object,
        source: QualitySourceReference,
        observation: FormalQualityObservationReference,
    ) -> QualityLinkReconciliationState:
        if source.source_kind is QualitySourceKind.TRIAL_DEFECT:
            repository = FrappeTrialQualityRepository(
                principal=self.principal,
                request_id=self.request_id,
                trace_id=self.trace_id,
            )
            chain = repository._trial_defect_chain(
                project,
                defect_id=source.source_global_id,
                for_update=False,
            )
            if not chain:
                return QualityLinkReconciliationState.UNAVAILABLE
            current = chain[-1]
            if (
                current.tenant_id != source.tenant_id
                or current.project_global_id != source.project_global_id
                or current.defect_global_id != source.source_global_id
                or observation.scope_kind != "trial_round"
                or current.trial_round_global_id != observation.scope_global_id
            ):
                return QualityLinkReconciliationState.UNAVAILABLE
            version = current.defect_version
            snapshot_hash = current.snapshot_hash
        elif source.source_kind is QualitySourceKind.TRIAL_REVIEW:
            if observation.scope_kind != "trial_round":
                return QualityLinkReconciliationState.UNAVAILABLE
            repository = FrappeTrialReviewRepository(
                principal=self.principal,
                request_id=self.request_id,
                trace_id=self.trace_id,
            )
            chain = repository._reference_chain(
                project,
                observation.scope_global_id,
                source.source_global_id,
            )
            if not chain:
                return QualityLinkReconciliationState.UNAVAILABLE
            current = chain[-1]
            if (
                current.tenant_id != source.tenant_id
                or current.project_global_id != source.project_global_id
                or current.reference_global_id != source.source_global_id
                or current.trial_round_global_id != observation.scope_global_id
            ):
                return QualityLinkReconciliationState.UNAVAILABLE
            version = current.reference_version
            snapshot_hash = current.snapshot_hash
        elif source.source_kind is QualitySourceKind.READINESS_ASSESSMENT:
            if (
                observation.scope_kind != "readiness"
                or observation.scope_global_id != source.source_global_id
            ):
                return QualityLinkReconciliationState.UNAVAILABLE
            chain = _project_revision_chain(project)
            if not chain:
                return QualityLinkReconciliationState.UNAVAILABLE
            current = chain[-1]
            if (
                current.tenant_id != source.tenant_id
                or current.project.global_id != source.project_global_id
                or current.instance_global_id != source.source_global_id
            ):
                return QualityLinkReconciliationState.UNAVAILABLE
            version = current.instance_version
            snapshot_hash = current.snapshot_hash
        else:
            return QualityLinkReconciliationState.UNAVAILABLE
        return _currentness(
            linked_version=source.source_version,
            linked_hash=source.source_snapshot_hash,
            current_version=version,
            current_hash=snapshot_hash,
        )

    def _projection_currentness(
        self,
        project: object,
        linked: FormalQualityObservationReference,
    ) -> QualityLinkReconciliationState:
        names = frappe.get_all(
            "NPI ERP Projection Head",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "scope_kind": linked.scope_kind,
                "scope_global_id": str(linked.scope_global_id),
                "projection_kind": "formal_quality_status",
                "source_object_type": linked.source_object_type,
                "source_object_id": linked.source_object_id,
            },
            pluck="name",
            order_by="global_id asc",
            limit_page_length=2,
        )
        if not isinstance(names, (list, tuple)) or len(names) != 1:
            return QualityLinkReconciliationState.UNAVAILABLE
        head = _optional_doc("NPI ERP Projection Head", UUID(str(names[0])))
        if head is None:
            return QualityLinkReconciliationState.UNAVAILABLE
        head_snapshot = _json_object(head.head_snapshot)
        expected_stream = {
            "tenantId": str(project.tenant_id),
            "projectGlobalId": str(project.global_id),
            "scopeKind": linked.scope_kind,
            "scopeGlobalId": str(linked.scope_global_id),
            "projectionKind": "formal_quality_status",
            "sourceObjectType": linked.source_object_type,
            "sourceObjectId": linked.source_object_id,
        }
        if (
            set(head_snapshot) != _PROJECTION_HEAD_SNAPSHOT_FIELDS
            or str(head.global_id) != str(names[0])
            or str(head.global_id) != str(linked.head_global_id)
            or str(head.tenant_id) != expected_stream["tenantId"]
            or str(head.project_global_id) != expected_stream["projectGlobalId"]
            or str(head.scope_kind) != expected_stream["scopeKind"]
            or str(head.scope_global_id) != expected_stream["scopeGlobalId"]
            or str(head.projection_kind) != expected_stream["projectionKind"]
            or str(head.source_object_type) != expected_stream["sourceObjectType"]
            or str(head.source_object_id) != expected_stream["sourceObjectId"]
            or str(head.stream_key_hash) != canonical_payload_hash(expected_stream)
            or canonical_payload_hash(head_snapshot) != str(head.head_hash)
            or head_snapshot["schemaVersion"] != 1
            or str(head_snapshot["globalId"]) != str(head.global_id)
            or any(
                str(head_snapshot[key]) != value
                for key, value in expected_stream.items()
            )
            or str(head_snapshot["streamKeyHash"]) != str(head.stream_key_hash)
            or str(head_snapshot["currentObservationGlobalId"])
            != str(head.current_observation)
            or str(head_snapshot["currentSourceVersion"])
            != str(head.current_source_version)
            or str(head_snapshot["currentPayloadHash"])
            != str(head.current_payload_hash)
            or str(head_snapshot["availability"]) != str(head.availability)
            or str(head_snapshot["freshness"]) != str(head.freshness)
            or str(head_snapshot["freshnessPolicyRef"])
            != str(head.freshness_policy_ref)
            or int(head_snapshot["optimisticVersion"])
            != int(head.optimistic_version)
            or str(head.availability) != "available"
            or str(head.freshness) != "fresh"
            or not head.current_observation
            or not head.current_source_version
            or not head.current_payload_hash
            or not head.freshness_policy_ref
        ):
            return QualityLinkReconciliationState.UNAVAILABLE
        observation = _optional_doc(
            "NPI ERP Projection Observation",
            UUID(str(head.current_observation)),
        )
        if observation is None:
            return QualityLinkReconciliationState.UNAVAILABLE
        observation_snapshot = _json_object(observation.observation_snapshot)
        if (
            str(observation.global_id) != str(head.current_observation)
            or str(observation.tenant_id) != expected_stream["tenantId"]
            or str(observation.project_global_id) != expected_stream["projectGlobalId"]
            or str(observation.scope_kind) != expected_stream["scopeKind"]
            or str(observation.scope_global_id) != expected_stream["scopeGlobalId"]
            or str(observation.projection_kind) != expected_stream["projectionKind"]
            or str(observation.source_object_type) != expected_stream["sourceObjectType"]
            or str(observation.source_object_id) != expected_stream["sourceObjectId"]
            or str(observation.source_system) != "ERPNEXT"
            or str(observation.target_system) != "NPI_ONE"
            or str(observation.adapter_mode) != "sandbox"
            or str(observation.availability) != "available"
            or str(observation.freshness) != "fresh"
            or str(observation.disposition) != "applied_current"
            or str(observation.source_version) != str(head.current_source_version)
            or str(observation.payload_hash) != str(head.current_payload_hash)
            or canonical_payload_hash(observation_snapshot)
            != str(observation.observation_hash)
        ):
            return QualityLinkReconciliationState.UNAVAILABLE
        payload = _json_object(observation.payload)
        values = payload.get("values")
        if not isinstance(values, dict) or set(values) != {
            "recordKind",
            "statusCode",
            "resultCode",
            "observedAt",
        }:
            return QualityLinkReconciliationState.UNAVAILABLE
        current = FormalQualityObservationReference(
            str(project.tenant_id),
            UUID(str(project.global_id)),
            linked.scope_kind,
            linked.scope_global_id,
            UUID(str(observation.global_id)),
            UUID(str(head.global_id)),
            int(head.optimistic_version),
            str(observation.source_object_type),
            str(observation.source_object_id),
            str(observation.source_version),
            FormalQualityRecordKind(str(values["recordKind"])),
            str(values["statusCode"]),
            values["resultCode"],
            str(observation.payload_hash),
            str(observation.observation_hash),
            str(head.head_hash),
            str(head.freshness_policy_ref),
        )
        exact = (
            current.head_optimistic_version == linked.head_optimistic_version
            and current.observation_global_id == linked.observation_global_id
            and current.source_version == linked.source_version
            and current.payload_hash == linked.payload_hash
            and current.observation_hash == linked.observation_hash
            and current.head_hash == linked.head_hash
        )
        if exact:
            return QualityLinkReconciliationState.CURRENT
        if current.head_optimistic_version > linked.head_optimistic_version:
            return QualityLinkReconciliationState.DRIFTED
        return QualityLinkReconciliationState.UNAVAILABLE

    @staticmethod
    def _head_matches_project(
        project: object,
        head: object,
        head_id: UUID,
    ) -> bool:
        return bool(
            str(head.global_id) == str(head_id)
            and str(head.tenant_id) == str(project.tenant_id)
            and str(head.project_global_id) == str(project.global_id)
        )

    @staticmethod
    def _insert_receipt(
        project: object,
        identity: QualityLinkCommandIdentity,
        now: datetime,
    ) -> object:
        return frappe.get_doc(
            {
                "doctype": "NPI Formal Quality Link Command Idempotency",
                "global_id": str(uuid4()),
                "schema_version": QUALITY_LINK_SCHEMA_VERSION,
                "receipt_key_hash": identity.receipt_key_hash,
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "actor_user_id": identity.actor_user_id,
                "operation": identity.operation,
                "idempotency_key_hash": identity.idempotency_key_hash,
                "payload_hash": identity.payload_hash,
                "source_snapshot_hash": identity.source_snapshot_hash,
                "projection_head_hash": identity.projection_head_hash,
                "link_revision_global_id": None,
                "response_payload": None,
                "response_hash": None,
                "sealed": 0,
                "created_at": _database_datetime(now),
                "updated_at": _database_datetime(now),
            }
        ).insert()

    @staticmethod
    def _insert_revision(revision: QualityLinkRevision) -> object:
        payload = revision.payload()
        source = payload["source"]
        observation = payload["formalObservation"]
        return frappe.get_doc(
            {
                "doctype": "NPI Formal Quality Link Revision",
                "global_id": str(revision.global_id),
                "schema_version": QUALITY_LINK_SCHEMA_VERSION,
                "tenant_id": source["tenantId"],
                "project_global_id": source["projectGlobalId"],
                "source_kind": source["sourceKind"],
                "source_global_id": source["sourceGlobalId"],
                "source_version": source["sourceVersion"],
                "source_state": source["sourceState"],
                "source_snapshot_hash": source["sourceSnapshotHash"],
                "stream_key_hash": revision.stream_key_hash,
                "revision_number": revision.revision_number,
                "predecessor_global_id": payload["predecessorGlobalId"],
                "observation_global_id": observation["observationGlobalId"],
                "head_global_id": observation["headGlobalId"],
                "head_optimistic_version": observation["headOptimisticVersion"],
                "scope_kind": observation["scopeKind"],
                "scope_global_id": observation["scopeGlobalId"],
                "source_object_type": observation["sourceObjectType"],
                "source_object_id": observation["sourceObjectId"],
                "source_object_version": observation["sourceVersion"],
                "record_kind": observation["recordKind"],
                "raw_status_code": observation["statusCode"],
                "raw_result_code": observation["resultCode"],
                "projection_payload_hash": observation["payloadHash"],
                "observation_hash": observation["observationHash"],
                "projection_head_hash": observation["headHash"],
                "freshness_policy_ref": observation["freshnessPolicyRef"],
                "link_state": payload["linkState"],
                "source_snapshot": source,
                "formal_observation_snapshot": observation,
                "link_snapshot": payload,
                "link_hash": revision.payload_hash,
                "actor_user_id": revision.actor_user_id,
                "trace_id": revision.trace_id,
                "created_at": _database_datetime(revision.created_at),
            }
        ).insert()

    @staticmethod
    def _insert_head(payload: Mapping[str, Any]) -> object:
        return frappe.get_doc(
            {
                "doctype": "NPI Formal Quality Link Head",
                "global_id": payload["globalId"],
                "tenant_id": payload["tenantId"],
                "project_global_id": payload["projectGlobalId"],
                "source_kind": payload["sourceKind"],
                "source_global_id": payload["sourceGlobalId"],
                "stream_key_hash": payload["streamKeyHash"],
                "current_revision": payload["currentRevisionGlobalId"],
                "revision_number": payload["revisionNumber"],
                "current_observation_global_id": payload["currentObservationGlobalId"],
                "current_projection_head_global_id": payload["currentProjectionHeadGlobalId"],
                "current_projection_head_version": payload["currentProjectionHeadVersion"],
                "optimistic_version": payload["optimisticVersion"],
                "head_snapshot": {key: value for key, value in payload.items() if key != "headHash"},
                "head_hash": payload["headHash"],
                "updated_at": payload["updatedAt"],
            }
        ).insert()

    @staticmethod
    def _advance_head(head: object, payload: Mapping[str, Any]) -> None:
        head.current_revision = payload["currentRevisionGlobalId"]
        head.revision_number = payload["revisionNumber"]
        head.current_observation_global_id = payload["currentObservationGlobalId"]
        head.current_projection_head_global_id = payload["currentProjectionHeadGlobalId"]
        head.current_projection_head_version = payload["currentProjectionHeadVersion"]
        head.optimistic_version = payload["optimisticVersion"]
        head.head_snapshot = {key: value for key, value in payload.items() if key != "headHash"}
        head.head_hash = payload["headHash"]
        head.updated_at = payload["updatedAt"]
        head.save()

    def _append_audit(
        self,
        revision: QualityLinkRevision,
        *,
        source_snapshot_hash: str,
        projection_head_hash: str,
    ) -> None:
        event = create_audit_event(
            actor=self.actor,
            trace_id=self.trace_id,
            operation="formal_quality_link.link_observed_reference",
            global_id=revision.global_id,
            object_version=revision.revision_number,
            result="linked",
            input_summary={
                "sourceKind": revision.source.source_kind.value,
                "sourceSnapshotHash": source_snapshot_hash,
                "projectionHeadHash": projection_head_hash,
            },
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
    def _seal_receipt(
        receipt: object,
        revision: QualityLinkRevision,
        response: Mapping[str, Any],
        now: datetime,
    ) -> None:
        receipt.link_revision_global_id = str(revision.global_id)
        receipt.response_payload = dict(response)
        receipt.response_hash = canonical_payload_hash(response)
        receipt.sealed = 1
        receipt.updated_at = _database_datetime(now)
        receipt.save()


def _linked_references(
    revision_payload: Mapping[str, Any],
) -> tuple[QualitySourceReference, FormalQualityObservationReference]:
    source = _closed_object(
        revision_payload.get("source"),
        {
            "tenantId",
            "projectGlobalId",
            "sourceKind",
            "sourceGlobalId",
            "sourceVersion",
            "sourceState",
            "sourceSnapshotHash",
        },
    )
    observation = _closed_object(
        revision_payload.get("formalObservation"),
        {
            "tenantId",
            "projectGlobalId",
            "scopeKind",
            "scopeGlobalId",
            "projectionKind",
            "sourceSystem",
            "availability",
            "freshness",
            "disposition",
            "observationGlobalId",
            "headGlobalId",
            "headOptimisticVersion",
            "sourceObjectType",
            "sourceObjectId",
            "sourceVersion",
            "recordKind",
            "statusCode",
            "resultCode",
            "payloadHash",
            "observationHash",
            "headHash",
            "freshnessPolicyRef",
        },
    )
    source_reference = QualitySourceReference(
        source["tenantId"],
        UUID(str(source["projectGlobalId"])),
        QualitySourceKind(str(source["sourceKind"])),
        UUID(str(source["sourceGlobalId"])),
        source["sourceVersion"],
        source["sourceState"],
        source["sourceSnapshotHash"],
    )
    observation_reference = FormalQualityObservationReference(
        observation["tenantId"],
        UUID(str(observation["projectGlobalId"])),
        observation["scopeKind"],
        UUID(str(observation["scopeGlobalId"])),
        UUID(str(observation["observationGlobalId"])),
        UUID(str(observation["headGlobalId"])),
        observation["headOptimisticVersion"],
        observation["sourceObjectType"],
        observation["sourceObjectId"],
        observation["sourceVersion"],
        FormalQualityRecordKind(str(observation["recordKind"])),
        observation["statusCode"],
        observation["resultCode"],
        observation["payloadHash"],
        observation["observationHash"],
        observation["headHash"],
        observation["freshnessPolicyRef"],
    )
    if (
        observation.get("projectionKind") != observation_reference.projection_kind
        or observation.get("sourceSystem") != observation_reference.source_system
        or observation.get("availability") != observation_reference.availability
        or observation.get("freshness") != observation_reference.freshness
        or observation.get("disposition") != observation_reference.disposition
        or source_reference.tenant_id != observation_reference.tenant_id
        or source_reference.project_global_id
        != observation_reference.project_global_id
    ):
        raise QualityLinkContractError(
            "Persisted formal quality link references are invalid."
        )
    return source_reference, observation_reference


def _currentness(
    *,
    linked_version: object,
    linked_hash: object,
    current_version: object,
    current_hash: object,
) -> QualityLinkReconciliationState:
    if (
        type(linked_version) is not int
        or type(current_version) is not int
        or linked_version < 1
        or current_version < 1
        or not isinstance(linked_hash, str)
        or not isinstance(current_hash, str)
    ):
        return QualityLinkReconciliationState.UNAVAILABLE
    if current_version == linked_version and current_hash == linked_hash:
        return QualityLinkReconciliationState.CURRENT
    if current_version > linked_version:
        return QualityLinkReconciliationState.DRIFTED
    return QualityLinkReconciliationState.UNAVAILABLE


def _head_response(
    *,
    global_id: UUID,
    project: object,
    source: QualitySourceReference,
    stream_key_hash: str,
    revision: QualityLinkRevision,
    optimistic_version: int,
    updated_at: datetime,
) -> dict[str, Any]:
    payload = {
        "schemaVersion": QUALITY_LINK_SCHEMA_VERSION,
        "globalId": str(global_id),
        "tenantId": str(project.tenant_id),
        "projectGlobalId": str(project.global_id),
        "sourceKind": source.source_kind.value,
        "sourceGlobalId": str(source.source_global_id),
        "streamKeyHash": stream_key_hash,
        "currentRevisionGlobalId": str(revision.global_id),
        "revisionNumber": revision.revision_number,
        "currentObservationGlobalId": str(revision.observation.observation_global_id),
        "currentProjectionHeadGlobalId": str(revision.observation.head_global_id),
        "currentProjectionHeadVersion": revision.observation.head_optimistic_version,
        "optimisticVersion": optimistic_version,
        "updatedAt": _utc(updated_at),
    }
    return {**payload, "headHash": canonical_payload_hash(payload)}


def _optional_doc(
    doctype: str,
    global_id: UUID,
    *,
    for_update: bool = False,
) -> object | None:
    try:
        return frappe.get_doc(doctype, str(global_id), for_update=for_update)
    except frappe.DoesNotExistError:
        return None


def _json_object(value: object) -> dict[str, Any]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, dict):
        raise RuntimeError("Persisted formal quality link JSON is invalid.")
    return parsed


def _closed_object(value: object, fields: set[str]) -> dict[str, Any]:
    result = _json_object(value)
    if set(result) != fields:
        raise QualityLinkContractError(
            "Persisted formal quality link reference shape is invalid."
        )
    return result


def _row_value(row: object, fieldname: str) -> object:
    return row.get(fieldname) if hasattr(row, "get") else getattr(row, fieldname)


def _database_datetime(value: datetime) -> str:
    exact = value.astimezone(UTC)
    return exact.strftime("%Y-%m-%d %H:%M:%S.%f")


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


__all__ = ["FormalQualityLinkCommandOutcome", "FrappeFormalQualityLinkRepository"]
