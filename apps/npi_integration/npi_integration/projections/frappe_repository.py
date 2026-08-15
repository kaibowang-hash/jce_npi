from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid5

import frappe

from npi_core.documents.frappe_repository import FrappeDocumentRepository
from npi_core.foundation.security import Principal
from npi_core.tooling.acceptance_domain import (
    ErpAssetMovementObservation,
    ErpAssetRepairObservation,
    ErpAssetSpareInventoryObservation,
    ToolingAssetActionKind,
    ToolingAssetProjectionAvailable,
)
from npi_core.tooling.manufacturing_domain import (
    ErpActualCostRow,
    FormalSupplierReference,
    ToolingProcurementCostAvailable,
    aggregate_actual_costs,
)
from npi_integration.projections.domain import (
    PROJECTION_ADAPTER_CONTRACT_VERSION,
    PROJECTION_DEFINITIONS,
    PROJECTION_SCHEMA_VERSION,
    ApplicationDisposition,
    CurrentProjectionIdentity,
    ProjectionApplyOutcome,
    ProjectionAvailability,
    ProjectionContext,
    ProjectionFreshness,
    ProjectionKind,
    ProjectionReaderResult,
    ProjectionRefreshTarget,
    ProjectionScopeKind,
    ProjectionSensitivity,
    canonical_payload_hash,
    classify_observation,
    projection_freshness,
)
from npi_integration.projections.frappe_validation import (
    projection_repository_write,
)


MAX_PROJECT_PROJECTION_HEADS = 200
MAX_EVENT_OBSERVATIONS = 50
_HEAD_NAMESPACE = UUID("e17085df-3b96-5d87-a5da-c2eaf4bc6c61")
_OBSERVATION_NAMESPACE = UUID("5e43f3df-50d0-57bc-8b85-2bb7cd3c12e3")


@dataclass(frozen=True, slots=True)
class ProjectProjectionAccess:
    project: Any
    redacted: bool


class FrappeProjectionRepository(FrappeDocumentRepository):
    """Project-first immutable ERP observation repository and bounded query."""

    def __init__(
        self,
        *,
        principal: Principal,
        request_id: str,
        trace_id: str,
        freshness_policies: Mapping[ProjectionKind, tuple[str, int]] | None = None,
    ) -> None:
        super().__init__(
            principal=principal,
            request_id=request_id,
            trace_id=trace_id,
        )
        self._freshness_policies = _freshness_policy_map(freshness_policies)

    def authorize_project(self, project_global_id: UUID) -> ProjectProjectionAccess | None:
        project_id = _uuid(project_global_id)
        project = _optional_doc("NPI Engineering Project", str(project_id))
        if (
            project is None
            or str(project.global_id) != str(project_id)
            or self.principal.tenant_id != str(project.tenant_id)
        ):
            return None
        if self.principal.is_external:
            return ProjectProjectionAccess(project=project, redacted=True)
        if not self._can_view_project(project, project_id):
            return None
        return ProjectProjectionAccess(project=project, redacted=False)

    def project_collection(
        self,
        access: ProjectProjectionAccess,
        *,
        kind: object | None,
    ) -> dict[str, object]:
        if not isinstance(access, ProjectProjectionAccess):
            raise TypeError("Authorized Project projection context is required.")
        project = access.project
        project_id = UUID(str(project.global_id))
        if access.redacted:
            return {
                "projectGlobalId": str(project_id),
                "accessState": "redacted",
                "reasonCode": "projection_access_redacted",
                "permissions": {"view": False, "edit": False, "refresh": False},
                "items": [],
            }
        selected_kind = _optional_kind(kind)
        filters: dict[str, object] = {
            "tenant_id": str(project.tenant_id),
            "project_global_id": str(project_id),
        }
        if selected_kind is not None:
            filters["projection_kind"] = selected_kind.value
        names = frappe.get_all(
            "NPI ERP Projection Head",
            filters=filters,
            pluck="name",
            order_by=(
                "projection_kind asc, scope_kind asc, scope_global_id asc, "
                "source_object_id asc, global_id asc"
            ),
            limit_page_length=MAX_PROJECT_PROJECTION_HEADS + 1,
        )
        if len(names) > MAX_PROJECT_PROJECTION_HEADS:
            raise ValueError("Persisted ERP projection collection exceeds its safe bound.")
        items = []
        for name in names:
            head = frappe.get_doc("NPI ERP Projection Head", str(name))
            self._require_head_scope(project, head)
            items.append(self._head_response(head))
        return {
            "projectGlobalId": str(project_id),
            "accessState": "available",
            "reasonCode": None,
            "permissions": {"view": True, "edit": False, "refresh": False},
            "items": items,
        }

    def enumerate_refresh_targets(
        self,
        project_global_id: UUID,
    ) -> Sequence[ProjectionRefreshTarget]:
        access = self.authorize_project(project_global_id)
        if access is None or access.redacted:
            return ()
        project = access.project
        targets: list[ProjectionRefreshTarget] = []
        for reference in project.references:
            if (
                str(reference.reference_type) == "customer"
                and str(reference.source_system) == "ERPNEXT"
            ):
                targets.append(
                    ProjectionRefreshTarget(
                        context=ProjectionContext(
                            tenant_id=str(project.tenant_id),
                            project_global_id=UUID(str(project.global_id)),
                            scope_kind=ProjectionScopeKind.PROJECT,
                            scope_global_id=UUID(str(project.global_id)),
                        ),
                        kind=ProjectionKind.CUSTOMER_MASTER,
                        source_object_id=str(reference.source_object_id),
                    )
                )
        names = frappe.get_all(
            "NPI ERP Projection Head",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
            },
            pluck="name",
            order_by="projection_kind asc, scope_kind asc, scope_global_id asc, global_id asc",
            limit_page_length=MAX_PROJECT_PROJECTION_HEADS + 1,
        )
        if len(names) > MAX_PROJECT_PROJECTION_HEADS:
            raise ValueError("Persisted ERP projection refresh scope exceeds its safe bound.")
        for name in names:
            head = frappe.get_doc("NPI ERP Projection Head", str(name))
            self._require_head_scope(project, head)
            targets.append(
                ProjectionRefreshTarget(
                    context=ProjectionContext(
                        tenant_id=str(project.tenant_id),
                        project_global_id=UUID(str(project.global_id)),
                        scope_kind=ProjectionScopeKind(str(head.scope_kind)),
                        scope_global_id=UUID(str(head.scope_global_id)),
                    ),
                    kind=ProjectionKind(str(head.projection_kind)),
                    source_object_id=str(head.source_object_id),
                )
            )
        unique = {
            (
                target.context.scope_kind,
                target.context.scope_global_id,
                target.kind,
                target.source_object_id,
            ): target
            for target in targets
        }
        return tuple(
            unique[key]
            for key in sorted(unique, key=lambda value: tuple(map(str, value)))
        )

    def apply_observation(
        self,
        *,
        project_global_id: UUID,
        target: ProjectionRefreshTarget,
        result: ProjectionReaderResult,
        event_id: UUID,
        received_at: datetime,
        correlation_id: UUID,
    ) -> ProjectionApplyOutcome:
        access = self.authorize_project(project_global_id)
        if access is None or access.redacted:
            raise PermissionError("The Project projection scope is unavailable.")
        project = access.project
        _require_target_matches_project(project, target)
        self._require_scope_belongs_to_project(project, target.context)
        if (
            not isinstance(result, ProjectionReaderResult)
            or result.kind is not target.kind
            or result.source_object_id != target.source_object_id
        ):
            raise ValueError("Projection reader result does not match its exact target.")
        received = _datetime(received_at)
        exact_event_id = _uuid(event_id)
        exact_correlation_id = _uuid(correlation_id)
        payload = result.event_payload(context=target.context, received_at=received)
        payload_hash = canonical_payload_hash(payload)
        stream_identity = _stream_identity(target)
        stream_key_hash = canonical_payload_hash(stream_identity)
        head_id = uuid5(_HEAD_NAMESPACE, stream_key_hash)
        event_key_hash = canonical_payload_hash(
            {"eventId": str(exact_event_id), "payloadHash": payload_hash}
        )
        observation_id = uuid5(_OBSERVATION_NAMESPACE, event_key_hash)
        head = _optional_locked_doc("NPI ERP Projection Head", str(head_id))
        if head is not None:
            self._require_head_identity(head, stream_identity, stream_key_hash)

        existing_event_rows = frappe.get_all(
            "NPI ERP Projection Observation",
            filters={"event_id": str(exact_event_id)},
            fields=["name", "payload_hash", "disposition"],
            order_by="created_at asc, global_id asc",
            limit_page_length=MAX_EVENT_OBSERVATIONS + 1,
        )
        if len(existing_event_rows) > MAX_EVENT_OBSERVATIONS:
            raise ValueError("Persisted ERP projection event history exceeds its safe bound.")
        for row in existing_event_rows:
            if str(_row_value(row, "payload_hash")) == payload_hash:
                if head is None:
                    raise RuntimeError("A persisted projection replay has no guarded head.")
                return ProjectionApplyOutcome(
                    observation_global_id=UUID(str(_row_value(row, "name"))),
                    disposition=ApplicationDisposition(
                        str(_row_value(row, "disposition"))
                    ),
                    head_optimistic_version=int(head.optimistic_version),
                    replayed=True,
                )

        current = self._current_identity(head)
        disposition = (
            ApplicationDisposition.CONFLICTED
            if existing_event_rows
            else classify_observation(
                current,
                event_id=exact_event_id,
                result=result,
                payload_hash=payload_hash,
            )
        )
        freshness, policy_ref = self._candidate_freshness(
            target.kind,
            result,
            received,
            disposition,
            head,
        )
        observation_values = _observation_values(
            global_id=observation_id,
            event_id=exact_event_id,
            event_key_hash=event_key_hash,
            target=target,
            result=result,
            payload=payload,
            payload_hash=payload_hash,
            received_at=received,
            trace_id=self.trace_id,
            correlation_id=exact_correlation_id,
            freshness=freshness,
            disposition=disposition,
        )
        next_head_values = _head_values(
            global_id=head_id,
            stream_identity=stream_identity,
            stream_key_hash=stream_key_hash,
            previous=head,
            observation_values=observation_values,
            result=result,
            freshness=freshness,
            policy_ref=policy_ref,
            disposition=disposition,
            updated_at=received,
        )
        with projection_repository_write():
            frappe.get_doc(observation_values).insert()
            if head is None:
                head = frappe.get_doc(next_head_values).insert()
            else:
                for fieldname, value in next_head_values.items():
                    if fieldname not in {"doctype", "global_id"}:
                        setattr(head, fieldname, value)
                head.save()
            self._append_audit(
                operation="erp_projection.observe",
                global_id=observation_id,
                object_version=int(next_head_values["optimistic_version"]),
                result=disposition.value,
                summary={
                    "eventId": str(exact_event_id),
                    "projectGlobalId": str(project.global_id),
                    "projectionKind": target.kind.value,
                    "scopeGlobalId": str(target.context.scope_global_id),
                    "scopeKind": target.context.scope_kind.value,
                    "sourceObjectType": target.source_object_type,
                },
            )
        return ProjectionApplyOutcome(
            observation_global_id=observation_id,
            disposition=disposition,
            head_optimistic_version=int(next_head_values["optimistic_version"]),
        )

    def _candidate_freshness(
        self,
        kind: ProjectionKind,
        result: ProjectionReaderResult,
        received_at: datetime,
        disposition: ApplicationDisposition,
        head: object | None,
    ) -> tuple[ProjectionFreshness, str | None]:
        if disposition is ApplicationDisposition.APPLIED_CURRENT:
            policy = self._freshness_policies.get(kind)
            if policy is None:
                return ProjectionFreshness.UNKNOWN, None
            assert result.source_modified_at is not None
            return (
                projection_freshness(
                    observed_at=result.source_modified_at,
                    now=received_at,
                    maximum_age_seconds=policy[1],
                ),
                policy[0],
            )
        if disposition in {
            ApplicationDisposition.DUPLICATE_EXACT,
            ApplicationDisposition.SUPERSEDED,
        } and head is not None:
            return (
                ProjectionFreshness(str(head.freshness)),
                str(head.freshness_policy_ref) if head.freshness_policy_ref else None,
            )
        return ProjectionFreshness.UNKNOWN, None

    def _current_identity(self, head: object | None) -> CurrentProjectionIdentity | None:
        if head is None or not head.current_observation:
            return None
        observation = frappe.get_doc(
            "NPI ERP Projection Observation", str(head.current_observation)
        )
        if str(observation.disposition) != ApplicationDisposition.APPLIED_CURRENT.value:
            raise RuntimeError("Persisted current ERP projection is not applied truth.")
        return CurrentProjectionIdentity(
            event_id=UUID(str(observation.event_id)),
            source_object_id=str(observation.source_object_id),
            source_version=str(observation.source_version),
            source_modified_at=_datetime(observation.source_modified_at),
            payload_hash=str(observation.payload_hash),
        )

    def _head_response(self, head: object) -> dict[str, object]:
        latest = frappe.get_doc(
            "NPI ERP Projection Observation", str(head.last_refresh_observation)
        )
        _require_observation_matches_head(latest, head)
        current = None
        if head.current_observation:
            current_document = frappe.get_doc(
                "NPI ERP Projection Observation", str(head.current_observation)
            )
            _require_observation_matches_head(current_document, head)
            current_payload = _json_object(current_document.payload)
            current = {
                "observationGlobalId": str(current_document.global_id),
                "sourceVersion": str(current_document.source_version),
                "sourceModifiedAt": _utc_text(
                    _datetime(current_document.source_modified_at)
                ),
                "receivedAt": _utc_text(_datetime(current_document.received_at)),
                "payloadHash": str(current_document.payload_hash),
                "values": current_payload["values"],
            }
        payload = _json_object(latest.payload)
        return {
            "observationGlobalId": str(latest.global_id),
            "projectionKind": str(latest.projection_kind),
            "scopeKind": str(latest.scope_kind),
            "scopeGlobalId": str(latest.scope_global_id),
            "availability": str(head.availability),
            "freshness": str(head.freshness),
            "disposition": str(latest.disposition),
            "sourceSystem": "ERPNEXT",
            "sourceObjectType": str(latest.source_object_type),
            "sourceObjectId": str(latest.source_object_id),
            "sourceVersion": str(latest.source_version) if latest.source_version else None,
            "sourceModifiedAt": (
                _utc_text(_datetime(latest.source_modified_at))
                if latest.source_modified_at
                else None
            ),
            "receivedAt": _utc_text(_datetime(latest.received_at)),
            "payloadHash": str(latest.payload_hash),
            "unavailableReasonCode": (
                str(latest.unavailable_reason_code)
                if latest.unavailable_reason_code
                else None
            ),
            "values": payload["values"],
            "currentTruth": current,
            "editable": False,
        }

    def _require_head_scope(self, project: object, head: object) -> None:
        if (
            str(head.tenant_id) != str(project.tenant_id)
            or str(head.project_global_id) != str(project.global_id)
        ):
            raise ValueError("Persisted ERP projection head escaped its Project.")
        context = ProjectionContext(
            tenant_id=str(head.tenant_id),
            project_global_id=UUID(str(head.project_global_id)),
            scope_kind=ProjectionScopeKind(str(head.scope_kind)),
            scope_global_id=UUID(str(head.scope_global_id)),
        )
        if context.scope_kind not in PROJECTION_DEFINITIONS[
            ProjectionKind(str(head.projection_kind))
        ].scopes:
            raise ValueError("Persisted ERP projection scope kind is invalid.")
        self._require_scope_belongs_to_project(project, context)

    def _require_scope_belongs_to_project(
        self,
        project: object,
        context: ProjectionContext,
    ) -> None:
        if context.scope_kind is ProjectionScopeKind.PROJECT:
            if context.scope_global_id != UUID(str(project.global_id)):
                raise ValueError("ERP projection Project scope is invalid.")
            return
        specifications = {
            ProjectionScopeKind.TOOLING_MASTER: (
                "NPI Tooling Master",
                "originating_project_global_id",
            ),
            ProjectionScopeKind.TOOLING_SET: (
                "NPI Tooling Set",
                "project_global_id",
            ),
            ProjectionScopeKind.ENGINEERING_ITEM: (
                "NPI Engineering Part",
                "originating_project_global_id",
            ),
            ProjectionScopeKind.TRIAL_ROUND: (
                "NPI Trial Round",
                "project_global_id",
            ),
        }
        if context.scope_kind is ProjectionScopeKind.READINESS:
            rows = frappe.get_all(
                "NPI Readiness Instance Revision",
                filters={"instance_global_id": str(context.scope_global_id)},
                fields=["tenant_id", "project_global_id"],
                order_by="instance_version desc, global_id desc",
                limit_page_length=501,
            )
            if not rows or len(rows) > 500 or any(
                str(_row_value(row, "tenant_id")) != str(project.tenant_id)
                or str(_row_value(row, "project_global_id")) != str(project.global_id)
                for row in rows
            ):
                raise ValueError("ERP projection Readiness scope is unavailable.")
            return
        doctype, project_field = specifications[context.scope_kind]
        document = _optional_doc(doctype, str(context.scope_global_id))
        if (
            document is None
            or str(document.tenant_id) != str(project.tenant_id)
            or str(getattr(document, project_field)) != str(project.global_id)
        ):
            raise ValueError("ERP projection secondary scope is unavailable.")

    @staticmethod
    def _require_head_identity(
        head: object,
        stream_identity: Mapping[str, object],
        stream_key_hash: str,
    ) -> None:
        expected = {
            "tenantId": str(head.tenant_id),
            "projectGlobalId": str(head.project_global_id),
            "scopeKind": str(head.scope_kind),
            "scopeGlobalId": str(head.scope_global_id),
            "projectionKind": str(head.projection_kind),
            "sourceObjectType": str(head.source_object_type),
            "sourceObjectId": str(head.source_object_id),
        }
        if expected != dict(stream_identity) or str(head.stream_key_hash) != stream_key_hash:
            raise ValueError("Persisted ERP projection stream identity is invalid.")


class FrappeProjectionConsumerReader:
    """Local typed reader for existing Tooling cost and Asset surfaces."""

    def read_tooling_procurement_cost(
        self,
        *,
        project_global_id: UUID,
        tooling_master_global_id: UUID,
    ) -> dict[str, object] | None:
        observation = _one_confirmed_observation(
            project_global_id=project_global_id,
            projection_kind=ProjectionKind.TOOLING_PROCUREMENT_COST,
            scope_kind=ProjectionScopeKind.TOOLING_MASTER,
            scope_global_id=tooling_master_global_id,
        )
        if observation is None:
            return None
        values = _closed_mapping(
            _json_object(observation.payload)["values"],
            {"toolingMasterGlobalId", "supplier", "rows"},
        )
        if str(values.get("toolingMasterGlobalId")) != str(tooling_master_global_id):
            raise ValueError("Persisted Tooling cost projection escaped its scope.")
        supplier_value = _closed_mapping(
            values.get("supplier"),
            {"sourceObjectId", "targetVersion", "supplierCode", "supplierName"},
        )
        supplier = FormalSupplierReference(
            source_object_id=supplier_value["sourceObjectId"],
            target_version=supplier_value["targetVersion"],
            supplier_code=supplier_value["supplierCode"],
            supplier_name=supplier_value["supplierName"],
        )
        rows = tuple(
            _cost_row(value)
            for value in _closed_sequence(values.get("rows"), maximum=1000)
        )
        projection = ToolingProcurementCostAvailable(
            tooling_master_global_id=tooling_master_global_id,
            observed_at=_datetime(observation.source_modified_at),
            target_version=str(observation.source_version),
            supplier=supplier,
            rows=rows,
            summaries=aggregate_actual_costs(rows),
        )
        return projection.snapshot_payload()

    def read_tool_asset_status(
        self,
        *,
        project_global_id: UUID,
        tooling_master_global_id: UUID,
    ) -> dict[str, object] | None:
        project = _projection_project(project_global_id)
        heads = frappe.get_all(
            "NPI ERP Projection Head",
            filters={
                "project_global_id": str(_uuid(project_global_id)),
                "tenant_id": str(project.tenant_id),
                "projection_kind": ProjectionKind.TOOL_ASSET_STATUS.value,
                "scope_kind": ProjectionScopeKind.TOOLING_SET.value,
                "availability": ProjectionAvailability.AVAILABLE.value,
                "freshness": ProjectionFreshness.FRESH.value,
            },
            pluck="name",
            order_by="scope_global_id asc, global_id asc",
            limit_page_length=MAX_PROJECT_PROJECTION_HEADS + 1,
        )
        if len(heads) > MAX_PROJECT_PROJECTION_HEADS:
            raise ValueError("Persisted Tool Asset projection scope exceeds its safe bound.")
        matches = []
        for name in heads:
            head = frappe.get_doc("NPI ERP Projection Head", str(name))
            _require_confirmed_head(project, head)
            tooling_set = _optional_doc(
                "NPI Tooling Set", str(head.scope_global_id)
            )
            if (
                tooling_set is not None
                and str(tooling_set.project_global_id) == str(project_global_id)
                and str(tooling_set.tooling_master_global_id)
                == str(tooling_master_global_id)
                and str(tooling_set.tenant_id) == str(head.tenant_id)
            ):
                observation = frappe.get_doc(
                    "NPI ERP Projection Observation",
                    str(head.current_observation),
                )
                _require_observation_matches_head(observation, head)
                if str(observation.disposition) != ApplicationDisposition.APPLIED_CURRENT.value:
                    raise ValueError("Confirmed Tool Asset projection is not applied truth.")
                matches.append(observation)
        if not matches:
            return None
        if len(matches) != 1:
            raise ValueError("Confirmed Tool Asset projection is ambiguous.")
        observation = matches[0]
        values = _closed_mapping(
            _json_object(observation.payload)["values"],
            {
                "toolingSetGlobalId",
                "mappingVersion",
                "formalAssetId",
                "targetVersion",
                "assetState",
                "currentLocation",
                "shotCount",
                "expectedLifeShots",
                "maintenanceDue",
                "movements",
                "repairs",
                "spares",
            },
        )
        if str(values.get("toolingSetGlobalId")) != str(observation.scope_global_id):
            raise ValueError("Persisted Tool Asset projection escaped its scope.")
        projection = ToolingAssetProjectionAvailable(
            tooling_set_global_id=values["toolingSetGlobalId"],
            mapping_version=values["mappingVersion"],
            formal_asset_id=values["formalAssetId"],
            target_version=values["targetVersion"],
            asset_state=values["assetState"],
            current_location=values["currentLocation"],
            shot_count=values["shotCount"],
            expected_life_shots=values["expectedLifeShots"],
            maintenance_due=(
                date.fromisoformat(str(values["maintenanceDue"]))
                if values["maintenanceDue"] is not None
                else None
            ),
            movements=tuple(
                _asset_movement(value)
                for value in _closed_sequence(values["movements"], maximum=200)
            ),
            repairs=tuple(
                _asset_repair(value)
                for value in _closed_sequence(values["repairs"], maximum=200)
            ),
            spares=tuple(
                _asset_spare(value)
                for value in _closed_sequence(values["spares"], maximum=500)
            ),
            observation_global_id=observation.global_id,
            observation_hash=observation.observation_hash,
            observed_at=_datetime(observation.source_modified_at),
        )
        return projection.public_dict()


def projection_reader_factory() -> FrappeProjectionConsumerReader:
    return FrappeProjectionConsumerReader()


def _observation_values(
    *,
    global_id: UUID,
    event_id: UUID,
    event_key_hash: str,
    target: ProjectionRefreshTarget,
    result: ProjectionReaderResult,
    payload: Mapping[str, object],
    payload_hash: str,
    received_at: datetime,
    trace_id: str,
    correlation_id: UUID,
    freshness: ProjectionFreshness,
    disposition: ApplicationDisposition,
) -> dict[str, object]:
    definition = PROJECTION_DEFINITIONS[target.kind]
    snapshot = {
        "schemaVersion": PROJECTION_SCHEMA_VERSION,
        "globalId": str(global_id),
        "eventId": str(event_id),
        "eventKeyHash": event_key_hash,
        "eventType": definition.event_type,
        "eventVersion": 1,
        "sourceSystem": "ERPNEXT",
        "targetSystem": "NPI_ONE",
        "sourceObjectType": definition.source_object_type,
        "payload": dict(payload),
        "payloadHash": payload_hash,
        "traceId": trace_id,
        "correlationId": str(correlation_id),
        "sensitivity": ProjectionSensitivity.CONFIDENTIAL.value,
        "freshness": freshness.value,
        "disposition": disposition.value,
        "createdAt": _utc_text(received_at),
    }
    return {
        "doctype": "NPI ERP Projection Observation",
        "global_id": str(global_id),
        "schema_version": PROJECTION_SCHEMA_VERSION,
        "event_id": str(event_id),
        "event_key_hash": event_key_hash,
        "event_type": definition.event_type,
        "event_version": 1,
        "source_system": "ERPNEXT",
        "target_system": "NPI_ONE",
        "adapter_mode": result.adapter_mode.value,
        "adapter_contract_version": PROJECTION_ADAPTER_CONTRACT_VERSION,
        "source_environment": result.source_environment,
        "source_object_type": definition.source_object_type,
        "source_object_id": result.source_object_id,
        "source_version": result.source_version,
        "source_modified_at": (
            _database_datetime(result.source_modified_at)
            if result.source_modified_at is not None
            else None
        ),
        "payload": dict(payload),
        "payload_hash": payload_hash,
        "received_at": _database_datetime(received_at),
        "trace_id": trace_id,
        "correlation_id": str(correlation_id),
        "sensitivity": ProjectionSensitivity.CONFIDENTIAL.value,
        "tenant_id": target.context.tenant_id,
        "project_global_id": str(target.context.project_global_id),
        "scope_kind": target.context.scope_kind.value,
        "scope_global_id": str(target.context.scope_global_id),
        "projection_kind": target.kind.value,
        "availability": result.availability.value,
        "freshness": freshness.value,
        "disposition": disposition.value,
        "unavailable_reason_code": result.unavailable_reason_code,
        "observation_snapshot": snapshot,
        "observation_hash": canonical_payload_hash(snapshot),
        "created_at": _database_datetime(received_at),
    }


def _head_values(
    *,
    global_id: UUID,
    stream_identity: Mapping[str, object],
    stream_key_hash: str,
    previous: object | None,
    observation_values: Mapping[str, object],
    result: ProjectionReaderResult,
    freshness: ProjectionFreshness,
    policy_ref: str | None,
    disposition: ApplicationDisposition,
    updated_at: datetime,
) -> dict[str, object]:
    current_observation = getattr(previous, "current_observation", None)
    current_source_version = getattr(previous, "current_source_version", None)
    current_source_modified_at = getattr(previous, "current_source_modified_at", None)
    current_payload_hash = getattr(previous, "current_payload_hash", None)
    availability = (
        ProjectionAvailability(str(previous.availability))
        if previous is not None
        else ProjectionAvailability.UNAVAILABLE
    )
    if disposition is ApplicationDisposition.APPLIED_CURRENT:
        current_observation = observation_values["global_id"]
        current_source_version = result.source_version
        current_source_modified_at = observation_values["source_modified_at"]
        current_payload_hash = observation_values["payload_hash"]
        availability = ProjectionAvailability.AVAILABLE
    elif disposition is ApplicationDisposition.UNAVAILABLE_CURRENT:
        availability = ProjectionAvailability.UNAVAILABLE
    elif disposition is ApplicationDisposition.SYNTHETIC_RETAINED:
        availability = ProjectionAvailability.SYNTHETIC
    elif disposition is ApplicationDisposition.CONFLICTED:
        availability = ProjectionAvailability.UNAVAILABLE
    version = int(previous.optimistic_version) + 1 if previous is not None else 1
    snapshot = {
        "schemaVersion": 1,
        "globalId": str(global_id),
        **dict(stream_identity),
        "streamKeyHash": stream_key_hash,
        "currentObservationGlobalId": str(current_observation) if current_observation else None,
        "lastRefreshObservationGlobalId": str(observation_values["global_id"]),
        "currentSourceVersion": str(current_source_version) if current_source_version else None,
        "currentSourceModifiedAt": (
            _utc_text(_datetime(current_source_modified_at))
            if current_source_modified_at
            else None
        ),
        "currentPayloadHash": str(current_payload_hash) if current_payload_hash else None,
        "availability": availability.value,
        "freshness": freshness.value,
        "freshnessPolicyRef": policy_ref,
        "optimisticVersion": version,
        "updatedAt": _utc_text(updated_at),
    }
    return {
        "doctype": "NPI ERP Projection Head",
        "global_id": str(global_id),
        "stream_key_hash": stream_key_hash,
        "tenant_id": stream_identity["tenantId"],
        "project_global_id": stream_identity["projectGlobalId"],
        "scope_kind": stream_identity["scopeKind"],
        "scope_global_id": stream_identity["scopeGlobalId"],
        "projection_kind": stream_identity["projectionKind"],
        "source_object_type": stream_identity["sourceObjectType"],
        "source_object_id": stream_identity["sourceObjectId"],
        "current_observation": str(current_observation) if current_observation else None,
        "last_refresh_observation": str(observation_values["global_id"]),
        "current_source_version": (
            str(current_source_version) if current_source_version else None
        ),
        "current_source_modified_at": current_source_modified_at,
        "current_payload_hash": str(current_payload_hash) if current_payload_hash else None,
        "availability": availability.value,
        "freshness": freshness.value,
        "freshness_policy_ref": policy_ref,
        "optimistic_version": version,
        "head_snapshot": snapshot,
        "head_hash": canonical_payload_hash(snapshot),
        "updated_at": _database_datetime(updated_at),
    }


def _stream_identity(target: ProjectionRefreshTarget) -> dict[str, object]:
    return {
        "tenantId": target.context.tenant_id,
        "projectGlobalId": str(target.context.project_global_id),
        "scopeKind": target.context.scope_kind.value,
        "scopeGlobalId": str(target.context.scope_global_id),
        "projectionKind": target.kind.value,
        "sourceObjectType": target.source_object_type,
        "sourceObjectId": target.source_object_id,
    }


def _require_target_matches_project(project: object, target: ProjectionRefreshTarget) -> None:
    if (
        not isinstance(target, ProjectionRefreshTarget)
        or target.context.project_global_id != UUID(str(project.global_id))
        or target.context.tenant_id != str(project.tenant_id)
    ):
        raise ValueError("Projection target escaped its authorized Project.")


def _require_observation_matches_head(observation: object, head: object) -> None:
    for fieldname in (
        "tenant_id",
        "project_global_id",
        "scope_kind",
        "scope_global_id",
        "projection_kind",
        "source_object_type",
        "source_object_id",
    ):
        if str(getattr(observation, fieldname)) != str(getattr(head, fieldname)):
            raise ValueError("Persisted ERP observation escaped its guarded head.")


def _one_confirmed_observation(
    *,
    project_global_id: UUID,
    projection_kind: ProjectionKind,
    scope_kind: ProjectionScopeKind,
    scope_global_id: UUID,
) -> object | None:
    project = _projection_project(project_global_id)
    rows = frappe.get_all(
        "NPI ERP Projection Head",
        filters={
            "project_global_id": str(_uuid(project_global_id)),
            "tenant_id": str(project.tenant_id),
            "projection_kind": projection_kind.value,
            "scope_kind": scope_kind.value,
            "scope_global_id": str(_uuid(scope_global_id)),
            "availability": ProjectionAvailability.AVAILABLE.value,
            "freshness": ProjectionFreshness.FRESH.value,
        },
        pluck="name",
        order_by="global_id asc",
        limit_page_length=2,
    )
    if not rows:
        return None
    if len(rows) != 1:
        raise ValueError("Confirmed ERP projection identity is ambiguous.")
    head = frappe.get_doc("NPI ERP Projection Head", str(rows[0]))
    _require_confirmed_head(project, head)
    observation = frappe.get_doc(
        "NPI ERP Projection Observation", str(head.current_observation)
    )
    _require_observation_matches_head(observation, head)
    if str(observation.disposition) != ApplicationDisposition.APPLIED_CURRENT.value:
        raise ValueError("Confirmed ERP projection is not applied truth.")
    return observation


def _projection_project(project_global_id: UUID) -> object:
    project_id = _uuid(project_global_id)
    project = _optional_doc("NPI Engineering Project", str(project_id))
    if project is None or str(project.global_id) != str(project_id):
        raise ValueError("Confirmed ERP projection Project is unavailable.")
    return project


def _require_confirmed_head(project: object, head: object) -> None:
    if (
        str(head.project_global_id) != str(project.global_id)
        or str(head.tenant_id) != str(project.tenant_id)
        or str(head.availability) != ProjectionAvailability.AVAILABLE.value
        or str(head.freshness) != ProjectionFreshness.FRESH.value
        or not head.current_observation
    ):
        raise ValueError("Confirmed ERP projection head is invalid.")


def _cost_row(value: object) -> ErpActualCostRow:
    row = _closed_mapping(
        value,
        {
            "toolingMasterGlobalId",
            "sourceRowId",
            "sourceRowVersion",
            "supplierSourceObjectId",
            "purchaseOrderSourceId",
            "purchaseReceiptSourceId",
            "purchaseInvoiceSourceId",
            "actualCostSourceId",
            "costTypeCode",
            "postingDate",
            "currency",
            "amount",
        },
    )
    return ErpActualCostRow(
        tooling_master_global_id=row["toolingMasterGlobalId"],
        source_row_id=row["sourceRowId"],
        source_row_version=row["sourceRowVersion"],
        supplier_source_object_id=row["supplierSourceObjectId"],
        purchase_order_source_id=row["purchaseOrderSourceId"],
        purchase_receipt_source_id=row["purchaseReceiptSourceId"],
        purchase_invoice_source_id=row["purchaseInvoiceSourceId"],
        actual_cost_source_id=row["actualCostSourceId"],
        cost_type_code=row["costTypeCode"],
        posting_date=date.fromisoformat(str(row["postingDate"])),
        currency=row["currency"],
        amount=row["amount"],
    )


def _asset_movement(value: object) -> ErpAssetMovementObservation:
    row = _closed_mapping(
        value,
        {"globalId", "actionKind", "fromLocation", "toLocation", "occurredAt", "sourceObjectId"},
    )
    return ErpAssetMovementObservation(
        global_id=row["globalId"],
        action_kind=ToolingAssetActionKind(str(row["actionKind"])),
        from_location=row["fromLocation"],
        to_location=row["toLocation"],
        occurred_at=_datetime(row["occurredAt"]),
        source_object_id=row["sourceObjectId"],
    )


def _asset_repair(value: object) -> ErpAssetRepairObservation:
    row = _closed_mapping(
        value,
        {"globalId", "summary", "downtimeHours", "completedAt", "sourceObjectId"},
    )
    return ErpAssetRepairObservation(
        global_id=row["globalId"],
        summary=row["summary"],
        downtime_hours=row["downtimeHours"],
        completed_at=_datetime(row["completedAt"]),
        source_object_id=row["sourceObjectId"],
    )


def _asset_spare(value: object) -> ErpAssetSpareInventoryObservation:
    row = _closed_mapping(
        value,
        {"formalItemId", "description", "stockOnHand", "minimumStock", "unit", "supplierId"},
    )
    return ErpAssetSpareInventoryObservation(
        formal_item_id=row["formalItemId"],
        description=row["description"],
        stock_on_hand=row["stockOnHand"],
        minimum_stock=row["minimumStock"],
        unit=row["unit"],
        supplier_id=row["supplierId"],
    )


def _closed_mapping(value: object, fields: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ValueError("Persisted ERP projection object is not closed.")
    return value


def _closed_sequence(value: object, *, maximum: int) -> Sequence[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ValueError("Persisted ERP projection collection is invalid.")
    if len(value) > maximum:
        raise ValueError("Persisted ERP projection collection exceeds its safe bound.")
    return value


def _freshness_policy_map(
    value: Mapping[ProjectionKind, tuple[str, int]] | None,
) -> dict[ProjectionKind, tuple[str, int]]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("Projection freshness policy map is invalid.")
    result = dict(value)
    if any(
        not isinstance(kind, ProjectionKind)
        or not isinstance(policy, tuple)
        or len(policy) != 2
        or not isinstance(policy[0], str)
        or not policy[0]
        or len(policy[0]) > 128
        or type(policy[1]) is not int
        or policy[1] < 1
        for kind, policy in result.items()
    ):
        raise ValueError("Projection freshness policy map is invalid.")
    return result


def _optional_kind(value: object | None) -> ProjectionKind | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError("Projection kind filter is invalid.")
    return ProjectionKind(value)


def _optional_doc(doctype: str, name: str):
    try:
        return frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        return None


def _optional_locked_doc(doctype: str, name: str):
    try:
        return frappe.get_doc(doctype, name, for_update=True)
    except frappe.DoesNotExistError:
        return None


def _json_object(value: object) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("Persisted ERP projection JSON is invalid.")
    return value


def _row_value(row: object, fieldname: str) -> object:
    return row.get(fieldname) if hasattr(row, "get") else getattr(row, fieldname)


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _database_datetime(value: datetime) -> str:
    return _datetime(value).replace(tzinfo=None).isoformat(sep=" ", timespec="microseconds")


def _utc_text(value: datetime) -> str:
    return _datetime(value).isoformat().replace("+00:00", "Z")
