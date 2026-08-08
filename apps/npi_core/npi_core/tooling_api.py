from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Protocol
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import frappe_domain_call
from npi_core.foundation.errors import PermissionDenied, RequestValidationFailed
from npi_core.foundation.security import Principal
from npi_core.foundation.tracing import current_trace_id
from npi_core.project.domain import actor_idempotency_key_hash
from npi_core.request_security import (
    authenticated_principal,
    authenticated_user,
    reject_unexpected_request_fields,
    require_csrf_token,
    require_request_fields,
    require_tooling_set_routes_enabled,
    require_tooling_engineering_controls_routes_enabled,
    require_tooling_manufacturing_routes_enabled,
    require_tooling_revision_routes_enabled,
    require_tooling_routes_enabled,
    response_request_id,
)
from npi_core.tooling.domain import (
    ToolingAccessoryLine,
    ToolingDifferenceSourceKind,
    ToolingInspectionCategory,
    ToolingInspectionObservation,
    ToolingIntakeDifference,
    ToolingIntakeEvidenceRole,
    ToolingRequirementKind,
    ToolingUnavailable,
)
from npi_core.tooling.diagnostics import (
    applicability_create_server_diagnostics,
    applicability_create_server_step,
    part_create_server_diagnostics,
    part_create_server_step,
    tooling_revision_create_server_diagnostics,
    tooling_revision_create_server_step,
)
from npi_core.tooling.revision_domain import (
    CavityStructuralState,
    DocumentRevisionReference,
    ExternalIdentityType,
    InsertValidationState,
    PartSpecificationKind,
    ToolingMeasurement,
    ToolingProcessKind,
    document_revision_reference_from_dict,
    measurement_from_dict,
    tooling_specification_from_dict,
)
from npi_core.tooling.manufacturing_domain import (
    PlanningMoney,
    ProjectMemberResponsibility,
    ReleasedDocumentEvidence,
    ToolingManufacturingMilestone,
    ToolingMilestoneCategory,
    ToolingMilestoneEvidenceRole,
    ToolingMilestoneResponsibilityKind,
    ToolingPlanEvidence,
    ToolingPlanEvidenceRole,
    ToolingSourcingStrategy,
)
from npi_core.tooling.engineering_controls_domain import (
    CapacityProvenanceKind,
    ToolingDefectActionState,
    ToolingDefectActionType,
    ToolingDefectContextKind,
    ToolingDefectEvidenceRole,
    ToolingDefectRootCauseState,
    ToolingDefectSeverity,
    ToolingDefectState,
    ToolingProcessContextKind,
    ToolingProcessMetricCode,
    ToolingProcessValueKind,
)


_PART_FIELDS = frozenset({"title", "revisionLabel", "reason"})
_PART_REVISION_FIELDS = frozenset(
    {"expectedVersion", "revisionLabel", "title", "reason"}
)
_REQUIREMENT_FIELDS = frozenset(
    {"kind", "title", "reason", "targetPartRevisionGlobalId", "targetDate"}
)
_REQUIREMENT_REQUIRED = frozenset({"kind", "title", "reason"})
_MASTER_FIELDS = frozenset({"title"})
_APPLICABILITY_FIELDS = frozenset(
    {
        "toolingMasterGlobalId",
        "partRevisionGlobalId",
        "product",
        "model",
        "relationshipGlobalId",
        "expectedVersion",
        "effectiveFrom",
        "effectiveTo",
        "reason",
    }
)
_APPLICABILITY_REQUIRED = frozenset(
    {"toolingMasterGlobalId", "partRevisionGlobalId", "effectiveFrom", "reason"}
)
_REFERENCE_FIELDS = frozenset({"sourceSystem", "sourceObjectId"})
_REFERENCE_SYSTEMS = frozenset({"NPI_ONE", "ERPNEXT"})
_SET_FIELDS = frozenset(
    {
        "toolingRequirementGlobalId",
        "physicalSerial",
        "customer",
        "custodyResponsibility",
        "repairAuthorizationReference",
        "returnConditions",
    }
)
_SET_REQUIRED = _SET_FIELDS - {"customer"}
_INTAKE_FIELDS = frozenset(
    {
        "expectedVersion",
        "transportProvider",
        "transportReference",
        "arrivedAt",
        "custodyHandover",
        "accessories",
        "inspections",
        "differences",
    }
)
_INTAKE_REQUIRED = _INTAKE_FIELDS - {"expectedVersion"}
_EVIDENCE_FIELDS = frozenset(
    {"evidenceRole", "differenceGlobalIds", "fileRevisionGlobalId"}
)
_REVISION_FIELDS = frozenset(
    {
        "expectedVersion",
        "revisionLabel",
        "specification",
        "cavities",
        "inserts",
        "externalIdentities",
        "designDocumentRevisions",
        "reason",
    }
)
_REVISION_REQUIRED = _REVISION_FIELDS - {"expectedVersion"}
_PART_SPECIFICATION_FIELDS = frozenset({"items", "externalIdentities"})
_PROCESS_CHAIN_FIELDS = frozenset(
    {"processChainGlobalId", "expectedVersion", "steps", "reason"}
)
_PROCESS_CHAIN_REQUIRED = frozenset({"steps", "reason"})
_SET_BINDING_FIELDS = frozenset({"toolingRevisionGlobalId", "reason"})
_MANUFACTURING_PLAN_FIELDS = frozenset(
    {
        "planGlobalId",
        "expectedVersion",
        "toolingRevisionGlobalId",
        "toolingRevisionSnapshotHash",
        "sourcingStrategy",
        "responsibleMember",
        "engineeringEstimate",
        "budget",
        "evidence",
        "designReleaseEvidence",
        "milestones",
        "reason",
    }
)
_MANUFACTURING_PLAN_REQUIRED = _MANUFACTURING_PLAN_FIELDS - {
    "planGlobalId",
    "expectedVersion",
    "engineeringEstimate",
    "budget",
}
_MILESTONE_OBSERVATION_FIELDS = frozenset(
    {
        "expectedVersion",
        "planRevisionSnapshotHash",
        "milestoneSnapshotHash",
        "progressPercentage",
        "actualStart",
        "actualFinish",
        "risk",
        "note",
        "evidence",
    }
)
_MILESTONE_OBSERVATION_REQUIRED = _MILESTONE_OBSERVATION_FIELDS - {
    "expectedVersion",
    "actualStart",
    "actualFinish",
    "risk",
    "note",
}
_DEFECT_REVISION_FIELDS = frozenset(
    {
        "defectGlobalId",
        "expectedVersion",
        "toolingRevisionGlobalId",
        "toolingRevisionSnapshotHash",
        "cavityGlobalId",
        "businessCode",
        "title",
        "description",
        "categoryKey",
        "severity",
        "blocking",
        "state",
        "detectionContext",
        "rootCauseState",
        "rootCause",
        "responsibleMember",
        "targetRoundLabel",
        "actions",
        "evidence",
        "reason",
    }
)
_DEFECT_REVISION_REQUIRED = _DEFECT_REVISION_FIELDS - {
    "defectGlobalId",
    "expectedVersion",
    "cavityGlobalId",
    "rootCause",
    "responsibleMember",
    "targetRoundLabel",
}
_PROCESS_PROFILE_REVISION_FIELDS = frozenset(
    {
        "profileGlobalId",
        "expectedVersion",
        "toolingRevisionGlobalId",
        "toolingRevisionSnapshotHash",
        "context",
        "effectiveFrom",
        "metrics",
        "reason",
    }
)
_PROCESS_PROFILE_REVISION_REQUIRED = _PROCESS_PROFILE_REVISION_FIELDS - {
    "profileGlobalId",
    "expectedVersion",
}
_CAPACITY_SCENARIO_REVISION_FIELDS = frozenset(
    {
        "scenarioGlobalId",
        "expectedVersion",
        "title",
        "effectiveFrom",
        "targetMonthlyAssemblyUnits",
        "lines",
        "reason",
    }
)
_CAPACITY_SCENARIO_REVISION_REQUIRED = _CAPACITY_SCENARIO_REVISION_FIELDS - {
    "scenarioGlobalId",
    "expectedVersion",
}


class _Outcome(Protocol):
    response: dict[str, Any]
    replayed: bool


class _Repository(Protocol):
    def authorize_scope(
        self,
        project_id: UUID,
        tooling_master_id: UUID | None = None,
        *,
        administer: bool = False,
    ) -> bool: ...

    def cockpit(self, project_id: UUID) -> dict[str, Any] | None: ...
    def master_detail(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
    ) -> dict[str, Any] | None: ...
    def create_part(self, project_id: UUID, **values: Any) -> _Outcome | None: ...
    def create_part_revision(
        self,
        project_id: UUID,
        part_id: UUID,
        **values: Any,
    ) -> _Outcome | None: ...
    def create_requirement(
        self,
        project_id: UUID,
        **values: Any,
    ) -> _Outcome | None: ...
    def create_master(self, project_id: UUID, **values: Any) -> _Outcome | None: ...
    def create_applicability(
        self,
        project_id: UUID,
        **values: Any,
    ) -> _Outcome | None: ...
    def tooling_sets(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
    ) -> dict[str, Any] | None: ...
    def tooling_set_detail(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        tooling_set_id: UUID,
    ) -> dict[str, Any] | None: ...
    def create_tooling_set(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        **values: Any,
    ) -> _Outcome | None: ...
    def create_tooling_intake(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        tooling_set_id: UUID,
        **values: Any,
    ) -> _Outcome | None: ...
    def create_tooling_intake_evidence_reference(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        tooling_set_id: UUID,
        intake_id: UUID,
        **values: Any,
    ) -> _Outcome | None: ...
    def tooling_revisions(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
    ) -> dict[str, Any] | None: ...
    def tooling_revision_detail(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        tooling_revision_id: UUID,
    ) -> dict[str, Any] | None: ...
    def part_controlled_specification(
        self,
        project_id: UUID,
        part_id: UUID,
        part_revision_id: UUID,
    ) -> dict[str, Any] | None: ...
    def tooling_process_chains(self, project_id: UUID) -> dict[str, Any] | None: ...
    def tooling_process_chain_detail(
        self,
        project_id: UUID,
        process_chain_revision_id: UUID,
    ) -> dict[str, Any] | None: ...
    def create_tooling_revision(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        **values: Any,
    ) -> _Outcome | None: ...
    def create_part_controlled_specification(
        self,
        project_id: UUID,
        part_id: UUID,
        part_revision_id: UUID,
        **values: Any,
    ) -> _Outcome | None: ...
    def create_tooling_process_chain_revision(
        self,
        project_id: UUID,
        **values: Any,
    ) -> _Outcome | None: ...
    def create_tooling_set_revision_binding(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        tooling_set_id: UUID,
        **values: Any,
    ) -> _Outcome | None: ...
    def tooling_manufacturing_plans(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
    ) -> dict[str, Any] | None: ...
    def tooling_manufacturing_plan_detail(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        plan_revision_id: UUID,
    ) -> dict[str, Any] | None: ...
    def create_tooling_manufacturing_plan(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        **values: Any,
    ) -> _Outcome | None: ...
    def create_tooling_manufacturing_milestone_observation(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        plan_revision_id: UUID,
        milestone_id: UUID,
        **values: Any,
    ) -> _Outcome | None: ...
    def tooling_engineering_controls(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
    ) -> dict[str, Any] | None: ...
    def create_tooling_defect_revision(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        **values: Any,
    ) -> _Outcome | None: ...
    def create_tooling_process_profile_revision(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        **values: Any,
    ) -> _Outcome | None: ...
    def create_tooling_capacity_scenario_revision(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        **values: Any,
    ) -> _Outcome | None: ...


def _repository_factory(
    *,
    principal: Principal,
    request_id: str,
    trace_id: str,
) -> _Repository:
    from npi_core.tooling.frappe_repository import FrappeToolingRepository

    return FrappeToolingRepository(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_tooling_cockpit(**request_fields: Any) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id = _query_context(
            frozenset(),
            request_fields,
        )
        response = repository.cockpit(project_id)
        if response is None:
            raise ToolingUnavailable()
        headers["X-Request-ID"] = request_id
        return _response(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_tooling_master(**request_fields: Any) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id = _query_context(
            frozenset(),
            request_fields,
        )
        master_id = _opaque_route_uuid("tooling_master_id")
        if not repository.authorize_scope(project_id, master_id):
            raise ToolingUnavailable()
        response = repository.master_detail(project_id, master_id)
        if response is None:
            raise ToolingUnavailable()
        headers["X-Request-ID"] = request_id
        return _response(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_engineering_part(
    title: Any = None,
    revisionLabel: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    values = lambda: {
        "title": _text(title, "title", 140),
        "revision_label": _text(revisionLabel, "revisionLabel", 40),
        "reason": _text(reason, "reason", 500),
    }
    return _command(
        _PART_FIELDS,
        _PART_FIELDS,
        request_fields,
        values,
        lambda repository, project_id, parsed: repository.create_part(
            project_id,
            **parsed,
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_engineering_part_revision(
    expectedVersion: Any = None,
    revisionLabel: Any = None,
    title: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    values = lambda: {
        "expected_version": _positive(expectedVersion, "expectedVersion"),
        "revision_label": _text(revisionLabel, "revisionLabel", 40),
        "title": _text(title, "title", 140),
        "reason": _text(reason, "reason", 500),
    }
    return _command(
        _PART_REVISION_FIELDS,
        _PART_REVISION_FIELDS,
        request_fields,
        values,
        lambda repository, project_id, parsed: repository.create_part_revision(
            project_id,
            _opaque_route_uuid("part_id"),
            **parsed,
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_tooling_requirement(
    kind: Any = None,
    title: Any = None,
    reason: Any = None,
    targetPartRevisionGlobalId: Any = None,
    targetDate: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    values = lambda: {
        "kind": _requirement_kind(kind),
        "title": _text(title, "title", 140),
        "reason": _text(reason, "reason", 500),
        "target_part_revision_id": _optional_uuid(
            targetPartRevisionGlobalId,
            "targetPartRevisionGlobalId",
        ),
        "target_date": _optional_date(targetDate, "targetDate"),
    }
    return _command(
        _REQUIREMENT_FIELDS,
        _REQUIREMENT_REQUIRED,
        request_fields,
        values,
        lambda repository, project_id, parsed: repository.create_requirement(
            project_id,
            **parsed,
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_tooling_master(
    title: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _command(
        _MASTER_FIELDS,
        _MASTER_FIELDS,
        request_fields,
        lambda: {"title": _text(title, "title", 140)},
        lambda repository, project_id, parsed: repository.create_master(
            project_id,
            **parsed,
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_tooling_applicability(
    toolingMasterGlobalId: Any = None,
    partRevisionGlobalId: Any = None,
    product: Any = None,
    model: Any = None,
    relationshipGlobalId: Any = None,
    expectedVersion: Any = None,
    effectiveFrom: Any = None,
    effectiveTo: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    def values() -> dict[str, Any]:
        relationship_id = _optional_uuid(
            relationshipGlobalId,
            "relationshipGlobalId",
        )
        expected_version = _optional_positive(expectedVersion, "expectedVersion")
        if (relationship_id is None) != (expected_version is None):
            raise _field(
                "relationshipGlobalId",
                _("Supply the relationship identity and expected version together."),
            )
        return {
            "tooling_master_id": _uuid(
                toolingMasterGlobalId,
                "toolingMasterGlobalId",
            ),
            "part_revision_id": _uuid(
                partRevisionGlobalId,
                "partRevisionGlobalId",
            ),
            "product": _reference(product, "product"),
            "model": _reference(model, "model"),
            "relationship_id": relationship_id,
            "expected_version": expected_version,
            "effective_from": _date(effectiveFrom, "effectiveFrom"),
            "effective_to": _optional_date(effectiveTo, "effectiveTo"),
            "reason": _text(reason, "reason", 500),
        }

    return _command(
        _APPLICABILITY_FIELDS,
        _APPLICABILITY_REQUIRED,
        request_fields,
        values,
        lambda repository, project_id, parsed: repository.create_applicability(
            project_id,
            **parsed,
        ),
        applicability_create_diagnostic=True,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_tooling_sets(**request_fields: Any) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id = _tooling_set_query_context(
            request_fields
        )
        master_id = _opaque_route_uuid("tooling_master_id")
        if not repository.authorize_scope(project_id, master_id):
            raise ToolingUnavailable()
        response = repository.tooling_sets(project_id, master_id)
        if response is None:
            raise ToolingUnavailable()
        headers["X-Request-ID"] = request_id
        return _response(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_tooling_set(**request_fields: Any) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id = _tooling_set_query_context(
            request_fields
        )
        master_id = _opaque_route_uuid("tooling_master_id")
        if not repository.authorize_scope(project_id, master_id):
            raise ToolingUnavailable()
        response = repository.tooling_set_detail(
            project_id,
            master_id,
            _opaque_route_uuid("tooling_set_id"),
        )
        if response is None:
            raise ToolingUnavailable()
        headers["X-Request-ID"] = request_id
        return _response(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_tooling_set(
    toolingRequirementGlobalId: Any = None,
    physicalSerial: Any = None,
    customer: Any = None,
    custodyResponsibility: Any = None,
    repairAuthorizationReference: Any = None,
    returnConditions: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _tooling_set_command(
        _SET_FIELDS,
        _SET_REQUIRED,
        request_fields,
        lambda: {
            "tooling_requirement_id": _uuid(
                toolingRequirementGlobalId,
                "toolingRequirementGlobalId",
            ),
            "physical_serial": _text(physicalSerial, "physicalSerial", 80),
            "customer": _reference(customer, "customer"),
            "custody_responsibility": _text(
                custodyResponsibility,
                "custodyResponsibility",
                500,
            ),
            "repair_authorization_reference": _text(
                repairAuthorizationReference,
                "repairAuthorizationReference",
                500,
            ),
            "return_conditions": _text(
                returnConditions,
                "returnConditions",
                500,
            ),
        },
        lambda repository, project_id, parsed: repository.create_tooling_set(
            project_id,
            _opaque_route_uuid("tooling_master_id"),
            **parsed,
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_tooling_intake(
    expectedVersion: Any = None,
    transportProvider: Any = None,
    transportReference: Any = None,
    arrivedAt: Any = None,
    custodyHandover: Any = None,
    accessories: Any = None,
    inspections: Any = None,
    differences: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _tooling_set_command(
        _INTAKE_FIELDS,
        _INTAKE_REQUIRED,
        request_fields,
        lambda: {
            "expected_version": _optional_positive(
                expectedVersion,
                "expectedVersion",
            ),
            "transport_provider": _text(
                transportProvider,
                "transportProvider",
                140,
            ),
            "transport_reference": _text(
                transportReference,
                "transportReference",
                140,
            ),
            "arrived_at": _utc_timestamp(arrivedAt, "arrivedAt"),
            "custody_handover": _text(
                custodyHandover,
                "custodyHandover",
                500,
            ),
            "accessories": _accessories(accessories),
            "inspections": _inspections(inspections),
            "differences": _differences(differences),
        },
        lambda repository, project_id, parsed: repository.create_tooling_intake(
            project_id,
            _opaque_route_uuid("tooling_master_id"),
            _opaque_route_uuid("tooling_set_id"),
            **parsed,
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_tooling_intake_evidence_reference(
    evidenceRole: Any = None,
    differenceGlobalIds: Any = None,
    fileRevisionGlobalId: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _tooling_set_command(
        _EVIDENCE_FIELDS,
        _EVIDENCE_FIELDS,
        request_fields,
        lambda: {
            "evidence_role": _evidence_role(evidenceRole),
            "difference_ids": _uuid_list(
                differenceGlobalIds,
                "differenceGlobalIds",
                maximum=100,
            ),
            "file_revision_id": _uuid(
                fileRevisionGlobalId,
                "fileRevisionGlobalId",
            ),
        },
        lambda repository, project_id, parsed: (
            repository.create_tooling_intake_evidence_reference(
                project_id,
                _opaque_route_uuid("tooling_master_id"),
                _opaque_route_uuid("tooling_set_id"),
                _opaque_route_uuid("intake_id"),
                **parsed,
            )
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_tooling_revisions(**request_fields: Any) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id = _tooling_revision_query_context(
            request_fields
        )
        master_id = _opaque_route_uuid("tooling_master_id")
        if not repository.authorize_scope(project_id, master_id):
            raise ToolingUnavailable()
        response = repository.tooling_revisions(project_id, master_id)
        if response is None:
            raise ToolingUnavailable()
        headers["X-Request-ID"] = request_id
        return _response(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_tooling_revision(**request_fields: Any) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id = _tooling_revision_query_context(
            request_fields
        )
        master_id = _opaque_route_uuid("tooling_master_id")
        if not repository.authorize_scope(project_id, master_id):
            raise ToolingUnavailable()
        response = repository.tooling_revision_detail(
            project_id,
            master_id,
            _opaque_route_uuid("tooling_revision_id"),
        )
        if response is None:
            raise ToolingUnavailable()
        headers["X-Request-ID"] = request_id
        return _response(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_part_controlled_specification(
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id = _tooling_revision_query_context(
            request_fields
        )
        response = repository.part_controlled_specification(
            project_id,
            _opaque_route_uuid("part_id"),
            _opaque_route_uuid("part_revision_id"),
        )
        if response is None:
            raise ToolingUnavailable()
        headers["X-Request-ID"] = request_id
        return _response(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_tooling_process_chains(**request_fields: Any) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id = _tooling_revision_query_context(
            request_fields
        )
        response = repository.tooling_process_chains(project_id)
        if response is None:
            raise ToolingUnavailable()
        headers["X-Request-ID"] = request_id
        return _response(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_tooling_process_chain(**request_fields: Any) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id = _tooling_revision_query_context(
            request_fields
        )
        response = repository.tooling_process_chain_detail(
            project_id,
            _opaque_route_uuid("process_chain_revision_id"),
        )
        if response is None:
            raise ToolingUnavailable()
        headers["X-Request-ID"] = request_id
        return _response(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_tooling_revision(
    expectedVersion: Any = None,
    revisionLabel: Any = None,
    specification: Any = None,
    cavities: Any = None,
    inserts: Any = None,
    externalIdentities: Any = None,
    designDocumentRevisions: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _tooling_revision_command(
        _REVISION_FIELDS,
        _REVISION_REQUIRED,
        request_fields,
        lambda: {
            "expected_version": _optional_positive(expectedVersion, "expectedVersion"),
            "revision_label": _text(revisionLabel, "revisionLabel", 40),
            "specification": _tooling_specification(specification),
            "cavities": _revision_cavities(cavities),
            "inserts": _revision_inserts(inserts),
            "external_identities": _external_identity_inputs(
                externalIdentities,
                "externalIdentities",
            ),
            "design_document_revisions": _document_revision_references(
                designDocumentRevisions
            ),
            "reason": _text(reason, "reason", 500),
        },
        lambda repository, project_id, parsed: repository.create_tooling_revision(
            project_id,
            _opaque_route_uuid("tooling_master_id"),
            **parsed,
        ),
        tooling_revision_create_diagnostic=True,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_part_controlled_specification(
    items: Any = None,
    externalIdentities: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _tooling_revision_command(
        _PART_SPECIFICATION_FIELDS,
        _PART_SPECIFICATION_FIELDS,
        request_fields,
        lambda: {
            "items": _part_specification_items(items),
            "external_identities": _external_identity_inputs(
                externalIdentities,
                "externalIdentities",
            ),
        },
        lambda repository, project_id, parsed: (
            repository.create_part_controlled_specification(
                project_id,
                _opaque_route_uuid("part_id"),
                _opaque_route_uuid("part_revision_id"),
                **parsed,
            )
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_tooling_process_chain_revision(
    processChainGlobalId: Any = None,
    expectedVersion: Any = None,
    steps: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _tooling_revision_command(
        _PROCESS_CHAIN_FIELDS,
        _PROCESS_CHAIN_REQUIRED,
        request_fields,
        lambda: {
            "process_chain_id": _optional_uuid(
                processChainGlobalId,
                "processChainGlobalId",
            ),
            "expected_version": _optional_positive(expectedVersion, "expectedVersion"),
            "steps": _process_step_inputs(steps),
            "reason": _text(reason, "reason", 500),
        },
        lambda repository, project_id, parsed: (
            repository.create_tooling_process_chain_revision(
                project_id,
                **parsed,
            )
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_tooling_set_revision_binding(
    toolingRevisionGlobalId: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _tooling_revision_command(
        _SET_BINDING_FIELDS,
        _SET_BINDING_FIELDS,
        request_fields,
        lambda: {
            "tooling_revision_id": _uuid(
                toolingRevisionGlobalId,
                "toolingRevisionGlobalId",
            ),
            "reason": _text(reason, "reason", 500),
        },
        lambda repository, project_id, parsed: (
            repository.create_tooling_set_revision_binding(
                project_id,
                _opaque_route_uuid("tooling_master_id"),
                _opaque_route_uuid("tooling_set_id"),
                **parsed,
            )
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_tooling_manufacturing_plans(
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id = _tooling_manufacturing_query_context(
            request_fields
        )
        master_id = _opaque_route_uuid("tooling_master_id")
        if not repository.authorize_scope(project_id, master_id):
            raise ToolingUnavailable()
        response = repository.tooling_manufacturing_plans(project_id, master_id)
        if response is None:
            raise ToolingUnavailable()
        headers["X-Request-ID"] = request_id
        return _response(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_tooling_manufacturing_plan(
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id = _tooling_manufacturing_query_context(
            request_fields
        )
        master_id = _opaque_route_uuid("tooling_master_id")
        if not repository.authorize_scope(project_id, master_id):
            raise ToolingUnavailable()
        response = repository.tooling_manufacturing_plan_detail(
            project_id,
            master_id,
            _opaque_route_uuid("manufacturing_plan_revision_id"),
        )
        if response is None:
            raise ToolingUnavailable()
        headers["X-Request-ID"] = request_id
        return _response(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_tooling_manufacturing_plan(
    planGlobalId: Any = None,
    expectedVersion: Any = None,
    toolingRevisionGlobalId: Any = None,
    toolingRevisionSnapshotHash: Any = None,
    sourcingStrategy: Any = None,
    responsibleMember: Any = None,
    engineeringEstimate: Any = None,
    budget: Any = None,
    evidence: Any = None,
    designReleaseEvidence: Any = None,
    milestones: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _tooling_manufacturing_command(
        _MANUFACTURING_PLAN_FIELDS,
        _MANUFACTURING_PLAN_REQUIRED,
        request_fields,
        lambda: {
            "plan_id": _optional_uuid(planGlobalId, "planGlobalId"),
            "expected_version": _optional_positive(
                expectedVersion,
                "expectedVersion",
            ),
            "tooling_revision_id": _uuid(
                toolingRevisionGlobalId,
                "toolingRevisionGlobalId",
            ),
            "tooling_revision_snapshot_hash": _sha256(
                toolingRevisionSnapshotHash,
                "toolingRevisionSnapshotHash",
            ),
            "sourcing_strategy": _enum_value(
                sourcingStrategy,
                ToolingSourcingStrategy,
                "sourcingStrategy",
            ),
            "responsible_member": _manufacturing_member(
                responsibleMember,
                "responsibleMember",
            ),
            "engineering_estimate": _planning_money(
                engineeringEstimate,
                "engineeringEstimate",
            ),
            "budget": _planning_money(budget, "budget"),
            "evidence": _manufacturing_plan_evidence(evidence),
            "design_release_evidence": _released_document_evidence_list(
                designReleaseEvidence,
                "designReleaseEvidence",
            ),
            "milestones": _manufacturing_milestones(milestones),
            "reason": _text(reason, "reason", 500),
        },
        lambda repository, project_id, parsed: (
            repository.create_tooling_manufacturing_plan(
                project_id,
                _opaque_route_uuid("tooling_master_id"),
                **parsed,
            )
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_tooling_manufacturing_milestone_observation(
    expectedVersion: Any = None,
    planRevisionSnapshotHash: Any = None,
    milestoneSnapshotHash: Any = None,
    progressPercentage: Any = None,
    actualStart: Any = None,
    actualFinish: Any = None,
    risk: Any = None,
    note: Any = None,
    evidence: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _tooling_manufacturing_command(
        _MILESTONE_OBSERVATION_FIELDS,
        _MILESTONE_OBSERVATION_REQUIRED,
        request_fields,
        lambda: {
            "expected_version": _optional_positive(
                expectedVersion,
                "expectedVersion",
            ),
            "plan_revision_snapshot_hash": _sha256(
                planRevisionSnapshotHash,
                "planRevisionSnapshotHash",
            ),
            "milestone_snapshot_hash": _sha256(
                milestoneSnapshotHash,
                "milestoneSnapshotHash",
            ),
            "progress_percentage": _percentage(
                progressPercentage,
                "progressPercentage",
            ),
            "actual_start": _optional_date(actualStart, "actualStart"),
            "actual_finish": _optional_date(actualFinish, "actualFinish"),
            "risk": _optional_text(risk, "risk", 240),
            "note": _optional_text(note, "note", 1000),
            "evidence": _milestone_evidence_inputs(evidence),
        },
        lambda repository, project_id, parsed: (
            repository.create_tooling_manufacturing_milestone_observation(
                project_id,
                _opaque_route_uuid("tooling_master_id"),
                _opaque_route_uuid("manufacturing_plan_revision_id"),
                _opaque_route_uuid("milestone_id"),
                **parsed,
            )
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_tooling_engineering_controls(
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id = (
            _tooling_engineering_controls_query_context(request_fields)
        )
        master_id = _opaque_route_uuid("tooling_master_id")
        if not repository.authorize_scope(project_id, master_id):
            raise ToolingUnavailable()
        response = repository.tooling_engineering_controls(project_id, master_id)
        if response is None:
            raise ToolingUnavailable()
        headers["X-Request-ID"] = request_id
        return _response(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_tooling_defect_revision(
    defectGlobalId: Any = None,
    expectedVersion: Any = None,
    toolingRevisionGlobalId: Any = None,
    toolingRevisionSnapshotHash: Any = None,
    cavityGlobalId: Any = None,
    businessCode: Any = None,
    title: Any = None,
    description: Any = None,
    categoryKey: Any = None,
    severity: Any = None,
    blocking: Any = None,
    state: Any = None,
    detectionContext: Any = None,
    rootCauseState: Any = None,
    rootCause: Any = None,
    responsibleMember: Any = None,
    targetRoundLabel: Any = None,
    actions: Any = None,
    evidence: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _tooling_engineering_controls_command(
        _DEFECT_REVISION_FIELDS,
        _DEFECT_REVISION_REQUIRED,
        request_fields,
        lambda: {
            "defect_id": _optional_uuid(defectGlobalId, "defectGlobalId"),
            "expected_version": _optional_positive(expectedVersion, "expectedVersion"),
            "tooling_revision_id": _uuid(
                toolingRevisionGlobalId,
                "toolingRevisionGlobalId",
            ),
            "tooling_revision_snapshot_hash": _sha256(
                toolingRevisionSnapshotHash,
                "toolingRevisionSnapshotHash",
            ),
            "cavity_id": _optional_uuid(cavityGlobalId, "cavityGlobalId"),
            "business_code": _text(businessCode, "businessCode", 64),
            "title": _text(title, "title", 255),
            "description": _text(description, "description", 4000),
            "category_key": _text(categoryKey, "categoryKey", 128),
            "severity": _enum_value(severity, ToolingDefectSeverity, "severity"),
            "blocking": _boolean(blocking, "blocking"),
            "state": _enum_value(state, ToolingDefectState, "state"),
            "detection_context": _defect_detection_context(detectionContext),
            "root_cause_state": _enum_value(
                rootCauseState,
                ToolingDefectRootCauseState,
                "rootCauseState",
            ),
            "root_cause": _optional_text(rootCause, "rootCause", 4000),
            "responsible_member": (
                _manufacturing_member(responsibleMember, "responsibleMember")
                if responsibleMember is not None
                else None
            ),
            "target_round_label": _optional_text(
                targetRoundLabel,
                "targetRoundLabel",
                64,
            ),
            "actions": _defect_actions(actions),
            "evidence": _defect_evidence_inputs(evidence, "evidence"),
            "reason": _text(reason, "reason", 1000),
        },
        lambda repository, project_id, parsed: (
            repository.create_tooling_defect_revision(
                project_id,
                _opaque_route_uuid("tooling_master_id"),
                **parsed,
            )
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_tooling_process_profile_revision(
    profileGlobalId: Any = None,
    expectedVersion: Any = None,
    toolingRevisionGlobalId: Any = None,
    toolingRevisionSnapshotHash: Any = None,
    context: Any = None,
    effectiveFrom: Any = None,
    metrics: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _tooling_engineering_controls_command(
        _PROCESS_PROFILE_REVISION_FIELDS,
        _PROCESS_PROFILE_REVISION_REQUIRED,
        request_fields,
        lambda: {
            "profile_id": _optional_uuid(profileGlobalId, "profileGlobalId"),
            "expected_version": _optional_positive(expectedVersion, "expectedVersion"),
            "tooling_revision_id": _uuid(
                toolingRevisionGlobalId,
                "toolingRevisionGlobalId",
            ),
            "tooling_revision_snapshot_hash": _sha256(
                toolingRevisionSnapshotHash,
                "toolingRevisionSnapshotHash",
            ),
            "context": _process_context_input(context),
            "effective_from": _date(effectiveFrom, "effectiveFrom"),
            "metrics": _process_metric_inputs(metrics),
            "reason": _text(reason, "reason", 1000),
        },
        lambda repository, project_id, parsed: (
            repository.create_tooling_process_profile_revision(
                project_id,
                _opaque_route_uuid("tooling_master_id"),
                **parsed,
            )
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_tooling_capacity_scenario_revision(
    scenarioGlobalId: Any = None,
    expectedVersion: Any = None,
    title: Any = None,
    effectiveFrom: Any = None,
    targetMonthlyAssemblyUnits: Any = None,
    lines: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _tooling_engineering_controls_command(
        _CAPACITY_SCENARIO_REVISION_FIELDS,
        _CAPACITY_SCENARIO_REVISION_REQUIRED,
        request_fields,
        lambda: {
            "scenario_id": _optional_uuid(scenarioGlobalId, "scenarioGlobalId"),
            "expected_version": _optional_positive(expectedVersion, "expectedVersion"),
            "title": _text(title, "title", 255),
            "effective_from": _date(effectiveFrom, "effectiveFrom"),
            "target_monthly_assembly_units": _decimal_string(
                targetMonthlyAssemblyUnits,
                "targetMonthlyAssemblyUnits",
                nonnegative=True,
            ),
            "lines": _capacity_line_inputs(lines),
            "reason": _text(reason, "reason", 1000),
        },
        lambda repository, project_id, parsed: (
            repository.create_tooling_capacity_scenario_revision(
                project_id,
                _opaque_route_uuid("tooling_master_id"),
                **parsed,
            )
        ),
    )


def _query_context(
    allowed: frozenset[str],
    request_fields: dict[str, Any],
) -> tuple[str, _Repository, UUID]:
    require_tooling_routes_enabled()
    actor = authenticated_user()
    principal = authenticated_principal(actor)
    request_id = _request_id()
    repository = _new_repository(principal, request_id)
    project_id = _opaque_route_uuid("project_id")
    if not repository.authorize_scope(project_id):
        raise ToolingUnavailable()
    reject_unexpected_request_fields(allowed, request_fields)
    return request_id, repository, project_id


def _tooling_set_query_context(
    request_fields: dict[str, Any],
) -> tuple[str, _Repository, UUID]:
    require_tooling_set_routes_enabled()
    actor = authenticated_user()
    principal = authenticated_principal(actor)
    request_id = _request_id()
    repository = _new_repository(principal, request_id)
    project_id = _opaque_route_uuid("project_id")
    if not repository.authorize_scope(project_id):
        raise ToolingUnavailable()
    reject_unexpected_request_fields(frozenset(), request_fields)
    return request_id, repository, project_id


def _tooling_revision_query_context(
    request_fields: dict[str, Any],
) -> tuple[str, _Repository, UUID]:
    require_tooling_revision_routes_enabled()
    actor = authenticated_user()
    principal = authenticated_principal(actor)
    request_id = _request_id()
    repository = _new_repository(principal, request_id)
    project_id = _opaque_route_uuid("project_id")
    if not repository.authorize_scope(project_id):
        raise ToolingUnavailable()
    reject_unexpected_request_fields(frozenset(), request_fields)
    return request_id, repository, project_id


def _tooling_manufacturing_query_context(
    request_fields: dict[str, Any],
) -> tuple[str, _Repository, UUID]:
    require_tooling_manufacturing_routes_enabled()
    actor = authenticated_user()
    principal = authenticated_principal(actor)
    request_id = _request_id()
    repository = _new_repository(principal, request_id)
    project_id = _opaque_route_uuid("project_id")
    if not repository.authorize_scope(project_id):
        raise ToolingUnavailable()
    reject_unexpected_request_fields(frozenset(), request_fields)
    return request_id, repository, project_id


def _tooling_engineering_controls_query_context(
    request_fields: dict[str, Any],
) -> tuple[str, _Repository, UUID]:
    require_tooling_engineering_controls_routes_enabled()
    actor = authenticated_user()
    principal = authenticated_principal(actor)
    request_id = _request_id()
    repository = _new_repository(principal, request_id)
    project_id = _opaque_route_uuid("project_id")
    if not repository.authorize_scope(project_id):
        raise ToolingUnavailable()
    reject_unexpected_request_fields(frozenset(), request_fields)
    return request_id, repository, project_id


def _command_context(
    allowed: frozenset[str],
    required: frozenset[str],
    request_fields: dict[str, Any],
) -> tuple[str, str, _Repository, UUID]:
    require_tooling_routes_enabled()
    actor = authenticated_user()
    require_csrf_token()
    principal = authenticated_principal(actor)
    if principal.is_external or "System Manager" not in principal.roles:
        raise PermissionDenied()
    request_id = _request_id()
    repository = _new_repository(principal, request_id)
    project_id = _opaque_route_uuid("project_id")
    if not repository.authorize_scope(project_id, administer=True):
        raise ToolingUnavailable()
    reject_unexpected_request_fields(allowed, request_fields)
    require_request_fields(required, request_fields)
    return (
        request_id,
        actor_idempotency_key_hash(
            actor,
            frappe.get_request_header("Idempotency-Key"),
        ),
        repository,
        project_id,
    )


def _tooling_set_command_context(
    allowed: frozenset[str],
    required: frozenset[str],
    request_fields: dict[str, Any],
) -> tuple[str, str, _Repository, UUID]:
    require_tooling_set_routes_enabled()
    actor = authenticated_user()
    require_csrf_token()
    principal = authenticated_principal(actor)
    if principal.is_external or "System Manager" not in principal.roles:
        raise PermissionDenied()
    request_id = _request_id()
    repository = _new_repository(principal, request_id)
    project_id = _opaque_route_uuid("project_id")
    if not repository.authorize_scope(project_id, administer=True):
        raise ToolingUnavailable()
    reject_unexpected_request_fields(allowed, request_fields)
    require_request_fields(required, request_fields)
    return (
        request_id,
        actor_idempotency_key_hash(
            actor,
            frappe.get_request_header("Idempotency-Key"),
        ),
        repository,
        project_id,
    )


def _tooling_revision_command_context(
    allowed: frozenset[str],
    required: frozenset[str],
    request_fields: dict[str, Any],
) -> tuple[str, str, _Repository, UUID]:
    require_tooling_revision_routes_enabled()
    actor = authenticated_user()
    require_csrf_token()
    principal = authenticated_principal(actor)
    if principal.is_external or "System Manager" not in principal.roles:
        raise PermissionDenied()
    request_id = _request_id()
    repository = _new_repository(principal, request_id)
    project_id = _opaque_route_uuid("project_id")
    if not repository.authorize_scope(project_id, administer=True):
        raise ToolingUnavailable()
    reject_unexpected_request_fields(allowed, request_fields)
    require_request_fields(required, request_fields)
    return (
        request_id,
        actor_idempotency_key_hash(
            actor,
            frappe.get_request_header("Idempotency-Key"),
        ),
        repository,
        project_id,
    )


def _tooling_manufacturing_command_context(
    allowed: frozenset[str],
    required: frozenset[str],
    request_fields: dict[str, Any],
) -> tuple[str, str, _Repository, UUID]:
    require_tooling_manufacturing_routes_enabled()
    actor = authenticated_user()
    require_csrf_token()
    principal = authenticated_principal(actor)
    if principal.is_external or "System Manager" not in principal.roles:
        raise PermissionDenied()
    request_id = _request_id()
    repository = _new_repository(principal, request_id)
    project_id = _opaque_route_uuid("project_id")
    master_id = _opaque_route_uuid("tooling_master_id")
    if not repository.authorize_scope(
        project_id,
        master_id,
        administer=True,
    ):
        raise ToolingUnavailable()
    reject_unexpected_request_fields(allowed, request_fields)
    require_request_fields(required, request_fields)
    return (
        request_id,
        actor_idempotency_key_hash(
            actor,
            frappe.get_request_header("Idempotency-Key"),
        ),
        repository,
        project_id,
    )


def _tooling_engineering_controls_command_context(
    allowed: frozenset[str],
    required: frozenset[str],
    request_fields: dict[str, Any],
) -> tuple[str, str, _Repository, UUID]:
    require_tooling_engineering_controls_routes_enabled()
    actor = authenticated_user()
    require_csrf_token()
    principal = authenticated_principal(actor)
    if principal.is_external or "System Manager" not in principal.roles:
        raise PermissionDenied()
    request_id = _request_id()
    repository = _new_repository(principal, request_id)
    project_id = _opaque_route_uuid("project_id")
    master_id = _opaque_route_uuid("tooling_master_id")
    if not repository.authorize_scope(project_id, master_id, administer=True):
        raise ToolingUnavailable()
    reject_unexpected_request_fields(allowed, request_fields)
    require_request_fields(required, request_fields)
    return (
        request_id,
        actor_idempotency_key_hash(
            actor,
            frappe.get_request_header("Idempotency-Key"),
        ),
        repository,
        project_id,
    )


def _command(
    allowed: frozenset[str],
    required: frozenset[str],
    request_fields: dict[str, Any],
    values,
    operation,
    *,
    applicability_create_diagnostic: bool = False,
) -> dict[str, Any] | None:
    headers = {
        "X-Request-ID": response_request_id(),
        "Idempotency-Replayed": "false",
    }

    def handle() -> dict[str, Any]:
        with part_create_server_diagnostics(
            current_trace_id.get()
        ), applicability_create_server_diagnostics(
            current_trace_id.get(),
            route_enabled=applicability_create_diagnostic,
        ):
            with part_create_server_step(
                "P601_PART_CREATE_COMMAND_CONTEXT"
            ), applicability_create_server_step(
                "P601_APPLICABILITY_CREATE_COMMAND_CONTEXT"
            ):
                request_id, key_hash, repository, project_id = _command_context(
                    allowed,
                    required,
                    request_fields,
                )
            with part_create_server_step(
                "P601_PART_CREATE_INPUT_PARSE"
            ), applicability_create_server_step(
                "P601_APPLICABILITY_CREATE_INPUT_PARSE"
            ):
                parsed = values()
            parsed["idempotency_key_hash"] = key_hash
            with part_create_server_step(
                "P601_PART_CREATE_API_RESPONSE"
            ), applicability_create_server_step(
                "P601_APPLICABILITY_CREATE_API_RESPONSE"
            ):
                outcome = operation(repository, project_id, parsed)
                if outcome is None:
                    raise ToolingUnavailable()
                if type(outcome.replayed) is not bool:
                    raise RuntimeError("The Tooling command replay result is invalid.")
                headers["X-Request-ID"] = request_id
                headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
                return _response(outcome.response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=headers,
    )


def _tooling_set_command(
    allowed: frozenset[str],
    required: frozenset[str],
    request_fields: dict[str, Any],
    values,
    operation,
) -> dict[str, Any] | None:
    headers = {
        "X-Request-ID": response_request_id(),
        "Idempotency-Replayed": "false",
    }

    def handle() -> dict[str, Any]:
        request_id, key_hash, repository, project_id = (
            _tooling_set_command_context(
                allowed,
                required,
                request_fields,
            )
        )
        parsed = values()
        parsed["idempotency_key_hash"] = key_hash
        outcome = operation(repository, project_id, parsed)
        if outcome is None:
            raise ToolingUnavailable()
        if type(outcome.replayed) is not bool:
            raise RuntimeError("The Tooling command replay result is invalid.")
        headers["X-Request-ID"] = request_id
        headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
        return _response(outcome.response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=headers,
    )


def _tooling_revision_command(
    allowed: frozenset[str],
    required: frozenset[str],
    request_fields: dict[str, Any],
    values,
    operation,
    *,
    tooling_revision_create_diagnostic: bool = False,
) -> dict[str, Any] | None:
    headers = {
        "X-Request-ID": response_request_id(),
        "Idempotency-Replayed": "false",
    }

    def handle() -> dict[str, Any]:
        with tooling_revision_create_server_diagnostics(
            current_trace_id.get(),
            route_enabled=tooling_revision_create_diagnostic,
        ):
            with tooling_revision_create_server_step(
                "P603_REVISION_COMMAND_CONTEXT"
            ):
                request_id, key_hash, repository, project_id = (
                    _tooling_revision_command_context(
                        allowed,
                        required,
                        request_fields,
                    )
                )
            with tooling_revision_create_server_step("P603_REVISION_INPUT_PARSE"):
                parsed = values()
            parsed["idempotency_key_hash"] = key_hash
            with tooling_revision_create_server_step(
                "P603_REVISION_API_RESPONSE"
            ):
                outcome = operation(repository, project_id, parsed)
                if outcome is None:
                    raise ToolingUnavailable()
                if type(outcome.replayed) is not bool:
                    raise RuntimeError(
                        "The Tooling Revision replay result is invalid."
                    )
                headers["X-Request-ID"] = request_id
                headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
                return _response(outcome.response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=headers,
    )


def _tooling_manufacturing_command(
    allowed: frozenset[str],
    required: frozenset[str],
    request_fields: dict[str, Any],
    values,
    operation,
) -> dict[str, Any] | None:
    headers = {
        "X-Request-ID": response_request_id(),
        "Idempotency-Replayed": "false",
    }

    def handle() -> dict[str, Any]:
        request_id, key_hash, repository, project_id = (
            _tooling_manufacturing_command_context(
                allowed,
                required,
                request_fields,
            )
        )
        parsed = values()
        parsed["idempotency_key_hash"] = key_hash
        outcome = operation(repository, project_id, parsed)
        if outcome is None:
            raise ToolingUnavailable()
        if type(outcome.replayed) is not bool:
            raise RuntimeError("The Tooling command replay result is invalid.")
        headers["X-Request-ID"] = request_id
        headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
        return _response(outcome.response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=headers,
    )


def _tooling_engineering_controls_command(
    allowed: frozenset[str],
    required: frozenset[str],
    request_fields: dict[str, Any],
    values,
    operation,
) -> dict[str, Any] | None:
    headers = {
        "X-Request-ID": response_request_id(),
        "Idempotency-Replayed": "false",
    }

    def handle() -> dict[str, Any]:
        request_id, key_hash, repository, project_id = (
            _tooling_engineering_controls_command_context(
                allowed,
                required,
                request_fields,
            )
        )
        parsed = values()
        parsed["idempotency_key_hash"] = key_hash
        outcome = operation(repository, project_id, parsed)
        if outcome is None:
            raise ToolingUnavailable()
        if type(outcome.replayed) is not bool:
            raise RuntimeError("The Tooling command replay result is invalid.")
        headers["X-Request-ID"] = request_id
        headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
        return _response(outcome.response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=headers,
    )


def _new_repository(principal: Principal, request_id: str) -> _Repository:
    trace_id = current_trace_id.get()
    if trace_id is None:
        raise RuntimeError("The Tooling request has no active trace identity.")
    return _repository_factory(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


def _response(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("The Tooling response is invalid.")
    return value


def _opaque_route_uuid(name: str) -> UUID:
    params = getattr(frappe.flags, "npi_route_params", None)
    value = params.get(name) if hasattr(params, "get") else None
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ToolingUnavailable() from error
    if str(parsed) != str(value).casefold():
        raise ToolingUnavailable()
    return parsed


def _request_id() -> str:
    return str(_uuid(frappe.get_request_header("X-Request-ID"), "requestId"))


def _uuid(value: object, path: str) -> UUID:
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise _field(path, _("Enter a valid global ID.")) from error
    if str(parsed) != str(value).casefold():
        raise _field(path, _("Enter a canonical global ID."))
    return parsed


def _optional_uuid(value: object, path: str) -> UUID | None:
    return None if value in (None, "") else _uuid(value, path)


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1 or value > 2_147_483_647:
        raise _field(path, _("Enter a positive whole number."))
    return value


def _optional_positive(value: object, path: str) -> int | None:
    return None if value in (None, "") else _positive(value, path)


def _text(value: object, path: str, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
        or len(value) > maximum
    ):
        raise _field(path, _("Enter a bounded text value."))
    return value


def _requirement_kind(value: object) -> ToolingRequirementKind:
    try:
        return ToolingRequirementKind(str(value))
    except ValueError as error:
        raise _field("kind", _("Select a supported value.")) from error


def _date(value: object, path: str) -> date:
    if not isinstance(value, str):
        raise _field(path, _("Enter a valid effectivity date."))
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise _field(path, _("Enter a valid effectivity date.")) from error
    if parsed.isoformat() != value:
        raise _field(path, _("Enter a canonical effectivity date."))
    return parsed


def _optional_date(value: object, path: str) -> date | None:
    return None if value in (None, "") else _date(value, path)


def _reference(value: object, path: str) -> dict[str, str] | None:
    if value in (None, ""):
        return None
    if not isinstance(value, Mapping) or set(value) != _REFERENCE_FIELDS:
        raise _field(path, _("Select a supported value."))
    source_system = value.get("sourceSystem")
    if source_system not in _REFERENCE_SYSTEMS:
        raise _field(f"{path}.sourceSystem", _("Select a supported value."))
    return {
        "sourceSystem": str(source_system),
        "sourceObjectId": _text(
            value.get("sourceObjectId"),
            f"{path}.sourceObjectId",
            128,
        ),
    }


def _accessories(value: object) -> tuple[ToolingAccessoryLine, ...]:
    items = _objects(value, "accessories", maximum=100)
    expected = {
        "globalId",
        "description",
        "declaredQuantity",
        "receivedQuantity",
        "unit",
    }
    result = []
    for index, item in enumerate(items):
        path = f"accessories[{index}]"
        _exact_fields(item, expected, path)
        result.append(
            ToolingAccessoryLine(
                global_id=_uuid(item.get("globalId"), f"{path}.globalId"),
                description=_text(
                    item.get("description"),
                    f"{path}.description",
                    200,
                ),
                declared_quantity=_non_negative(
                    item.get("declaredQuantity"),
                    f"{path}.declaredQuantity",
                ),
                received_quantity=_non_negative(
                    item.get("receivedQuantity"),
                    f"{path}.receivedQuantity",
                ),
                unit=_text(item.get("unit"), f"{path}.unit", 24),
            )
        )
    return tuple(result)


def _inspections(value: object) -> tuple[ToolingInspectionObservation, ...]:
    items = _objects(value, "inspections", maximum=5, minimum=5)
    expected = {"globalId", "category", "observation", "differenceObserved"}
    result = []
    for index, item in enumerate(items):
        path = f"inspections[{index}]"
        _exact_fields(item, expected, path)
        try:
            category = ToolingInspectionCategory(str(item.get("category")))
        except ValueError as error:
            raise _field(f"{path}.category", _("Select a supported value.")) from error
        result.append(
            ToolingInspectionObservation(
                global_id=_uuid(item.get("globalId"), f"{path}.globalId"),
                category=category,
                observation=_text(
                    item.get("observation"),
                    f"{path}.observation",
                    500,
                ),
                difference_observed=_boolean(
                    item.get("differenceObserved"),
                    f"{path}.differenceObserved",
                ),
            )
        )
    return tuple(result)


def _differences(value: object) -> tuple[ToolingIntakeDifference, ...]:
    items = _objects(value, "differences", maximum=100)
    expected = {
        "globalId",
        "sourceKind",
        "sourceGlobalId",
        "description",
        "customerConfirmationRequired",
    }
    result = []
    for index, item in enumerate(items):
        path = f"differences[{index}]"
        _exact_fields(item, expected, path)
        try:
            source_kind = ToolingDifferenceSourceKind(str(item.get("sourceKind")))
        except ValueError as error:
            raise _field(f"{path}.sourceKind", _("Select a supported value.")) from error
        result.append(
            ToolingIntakeDifference(
                global_id=_uuid(item.get("globalId"), f"{path}.globalId"),
                source_kind=source_kind,
                source_global_id=_uuid(
                    item.get("sourceGlobalId"),
                    f"{path}.sourceGlobalId",
                ),
                description=_text(
                    item.get("description"),
                    f"{path}.description",
                    500,
                ),
                customer_confirmation_required=_boolean(
                    item.get("customerConfirmationRequired"),
                    f"{path}.customerConfirmationRequired",
                ),
            )
        )
    return tuple(result)


def _objects(
    value: object,
    path: str,
    *,
    maximum: int,
    minimum: int = 0,
) -> tuple[Mapping[str, object], ...]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or len(value) < minimum
        or len(value) > maximum
        or any(not isinstance(item, Mapping) for item in value)
    ):
        raise _field(path, _("Enter a valid bounded list."))
    return tuple(value)


def _exact_fields(
    value: Mapping[str, object],
    expected: set[str],
    path: str,
) -> None:
    if set(value) != expected:
        raise _field(path, _("Select a supported value."))


def _uuid_list(value: object, path: str, *, maximum: int) -> tuple[UUID, ...]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or len(value) > maximum
    ):
        raise _field(path, _("Enter a valid bounded list."))
    result = tuple(_uuid(item, path) for item in value)
    if len(set(result)) != len(result):
        raise _field(path, _("Enter a valid bounded list."))
    return tuple(sorted(result, key=str))


def _evidence_role(value: object) -> ToolingIntakeEvidenceRole:
    try:
        return ToolingIntakeEvidenceRole(str(value))
    except ValueError as error:
        raise _field("evidenceRole", _("Select a supported value.")) from error


def _tooling_specification(value: object):
    try:
        return tooling_specification_from_dict(value)
    except RequestValidationFailed:
        raise
    except (TypeError, ValueError) as error:
        raise _field("specification", _("Enter a valid Tooling specification.")) from error


def _revision_cavities(value: object) -> tuple[dict[str, object], ...]:
    rows = _objects(value, "cavities", minimum=1, maximum=200)
    result = []
    for index, item in enumerate(rows):
        path = f"cavities[{index}]"
        _closed_fields(
            item,
            {"cavityIdentifier", "toolingApplicabilityGlobalId", "structuralState"},
            {"cavityIdentifier", "toolingApplicabilityGlobalId", "structuralState"},
            path,
        )
        result.append(
            {
                "cavity_identifier": _text(
                    item.get("cavityIdentifier"),
                    f"{path}.cavityIdentifier",
                    64,
                ),
                "tooling_applicability_id": _uuid(
                    item.get("toolingApplicabilityGlobalId"),
                    f"{path}.toolingApplicabilityGlobalId",
                ),
                "structural_state": _enum_value(
                    item.get("structuralState"),
                    CavityStructuralState,
                    f"{path}.structuralState",
                ),
            }
        )
    return tuple(result)


def _revision_inserts(value: object) -> tuple[dict[str, object], ...]:
    rows = _objects(value, "inserts", maximum=200)
    allowed = {
        "insertCode",
        "insertVersion",
        "toolingApplicabilityGlobalId",
        "model",
        "changeoverDuration",
        "validationState",
        "validationReason",
    }
    required = allowed - {"model", "validationReason"}
    result = []
    for index, item in enumerate(rows):
        path = f"inserts[{index}]"
        _closed_fields(item, allowed, required, path)
        validation_state = _enum_value(
            item.get("validationState"),
            InsertValidationState,
            f"{path}.validationState",
        )
        validation_reason = (
            _text(item.get("validationReason"), f"{path}.validationReason", 500)
            if "validationReason" in item
            else None
        )
        if (
            validation_state is InsertValidationState.VALIDATED
            and validation_reason is None
        ) or (
            validation_state is InsertValidationState.NOT_VALIDATED
            and validation_reason is not None
        ):
            raise _field(
                f"{path}.validationReason",
                _("Validation evidence must match the selected validation state."),
            )
        result.append(
            {
                "insert_code": _text(item.get("insertCode"), f"{path}.insertCode", 80),
                "insert_version": _positive(
                    item.get("insertVersion"),
                    f"{path}.insertVersion",
                ),
                "tooling_applicability_id": _uuid(
                    item.get("toolingApplicabilityGlobalId"),
                    f"{path}.toolingApplicabilityGlobalId",
                ),
                "model": _reference(item.get("model"), f"{path}.model"),
                "changeover_duration": _measurement(
                    item.get("changeoverDuration"),
                    f"{path}.changeoverDuration",
                ),
                "validation_state": validation_state,
                "validation_reason": validation_reason,
            }
        )
    return tuple(result)


def _external_identity_inputs(
    value: object,
    path: str,
) -> tuple[dict[str, object], ...]:
    rows = _objects(value, path, maximum=100)
    allowed = {
        "identityType",
        "value",
        "rawValue",
        "sourceSystem",
        "sourceObjectId",
        "effectiveFrom",
        "effectiveTo",
    }
    required = allowed - {"effectiveTo"}
    result = []
    for index, item in enumerate(rows):
        item_path = f"{path}[{index}]"
        _closed_fields(item, allowed, required, item_path)
        result.append(
            {
                "identity_type": _enum_value(
                    item.get("identityType"),
                    ExternalIdentityType,
                    f"{item_path}.identityType",
                ),
                "value": _text(item.get("value"), f"{item_path}.value", 160),
                "raw_value": _text(
                    item.get("rawValue"),
                    f"{item_path}.rawValue",
                    500,
                ),
                "source_system": _source_system(
                    item.get("sourceSystem"),
                    f"{item_path}.sourceSystem",
                ),
                "source_object_id": _text(
                    item.get("sourceObjectId"),
                    f"{item_path}.sourceObjectId",
                    128,
                ),
                "effective_from": _date(
                    item.get("effectiveFrom"),
                    f"{item_path}.effectiveFrom",
                ),
                "effective_to": _optional_date(
                    item.get("effectiveTo"),
                    f"{item_path}.effectiveTo",
                ),
            }
        )
    return tuple(result)


def _document_revision_references(
    value: object,
) -> tuple[DocumentRevisionReference, ...]:
    rows = _objects(value, "designDocumentRevisions", maximum=50)
    result = []
    for index, item in enumerate(rows):
        path = f"designDocumentRevisions[{index}]"
        _exact_fields(item, {"globalId", "snapshotHash"}, path)
        try:
            result.append(document_revision_reference_from_dict(item))
        except RequestValidationFailed as error:
            raise _field(path, _("Enter a valid Document Revision reference.")) from error
    if len({item.global_id for item in result}) != len(result):
        raise _field("designDocumentRevisions", _("Enter a valid bounded list."))
    return tuple(result)


def _manufacturing_member(
    value: object,
    path: str,
) -> ProjectMemberResponsibility:
    if not isinstance(value, Mapping):
        raise _field(path, _("Select a supported value."))
    _exact_fields(value, {"globalId", "userId", "optimisticVersion"}, path)
    return ProjectMemberResponsibility(
        global_id=_uuid(value.get("globalId"), f"{path}.globalId"),
        user_id=_text(value.get("userId"), f"{path}.userId", 254),
        optimistic_version=_positive(
            value.get("optimisticVersion"),
            f"{path}.optimisticVersion",
        ),
    )


def _planning_money(value: object, path: str) -> PlanningMoney | None:
    if value in (None, ""):
        return None
    if not isinstance(value, Mapping):
        raise _field(path, _("Select a supported value."))
    _exact_fields(value, {"amount", "currency"}, path)
    return PlanningMoney(
        amount=_text(value.get("amount"), f"{path}.amount", 64),
        currency=_text(value.get("currency"), f"{path}.currency", 3),
    )


def _released_document_evidence(
    value: object,
    path: str,
) -> ReleasedDocumentEvidence:
    if not isinstance(value, Mapping):
        raise _field(path, _("Select a supported value."))
    _exact_fields(
        value,
        {
            "revisionGlobalId",
            "revisionSnapshotHash",
            "lifecycleGlobalId",
            "lifecycleVersion",
            "releaseEventGlobalId",
            "releaseEventHash",
            "releaseSnapshotHash",
        },
        path,
    )
    return ReleasedDocumentEvidence(
        revision_global_id=_uuid(
            value.get("revisionGlobalId"),
            f"{path}.revisionGlobalId",
        ),
        revision_snapshot_hash=_sha256(
            value.get("revisionSnapshotHash"),
            f"{path}.revisionSnapshotHash",
        ),
        lifecycle_global_id=_uuid(
            value.get("lifecycleGlobalId"),
            f"{path}.lifecycleGlobalId",
        ),
        lifecycle_version=_positive(
            value.get("lifecycleVersion"),
            f"{path}.lifecycleVersion",
        ),
        release_event_global_id=_uuid(
            value.get("releaseEventGlobalId"),
            f"{path}.releaseEventGlobalId",
        ),
        release_event_hash=_sha256(
            value.get("releaseEventHash"),
            f"{path}.releaseEventHash",
        ),
        release_snapshot_hash=_sha256(
            value.get("releaseSnapshotHash"),
            f"{path}.releaseSnapshotHash",
        ),
    )


def _released_document_evidence_list(
    value: object,
    path: str,
) -> tuple[ReleasedDocumentEvidence, ...]:
    rows = _objects(value, path, minimum=1, maximum=50)
    result = tuple(
        _released_document_evidence(item, f"{path}[{index}]")
        for index, item in enumerate(rows)
    )
    if len({item.revision_global_id for item in result}) != len(result):
        raise _field(path, _("Enter a valid bounded list."))
    return result


def _manufacturing_plan_evidence(
    value: object,
) -> tuple[ToolingPlanEvidence, ...]:
    rows = _objects(value, "evidence", maximum=4)
    result = []
    for index, item in enumerate(rows):
        path = f"evidence[{index}]"
        _exact_fields(item, {"role", "document"}, path)
        result.append(
            ToolingPlanEvidence(
                role=_enum_value(
                    item.get("role"),
                    ToolingPlanEvidenceRole,
                    f"{path}.role",
                ),
                document=_released_document_evidence(
                    item.get("document"),
                    f"{path}.document",
                ),
            )
        )
    return tuple(result)


def _manufacturing_milestones(
    value: object,
) -> tuple[ToolingManufacturingMilestone, ...]:
    rows = _objects(value, "milestones", minimum=1, maximum=100)
    result = []
    expected = {
        "globalId",
        "sequence",
        "category",
        "plannedStart",
        "plannedFinish",
        "responsibilityKind",
        "responsibleMember",
        "predecessorGlobalIds",
    }
    for index, item in enumerate(rows):
        path = f"milestones[{index}]"
        _exact_fields(item, expected, path)
        member_value = item.get("responsibleMember")
        result.append(
            ToolingManufacturingMilestone(
                global_id=_uuid(item.get("globalId"), f"{path}.globalId"),
                sequence=_positive(item.get("sequence"), f"{path}.sequence"),
                category=_enum_value(
                    item.get("category"),
                    ToolingMilestoneCategory,
                    f"{path}.category",
                ),
                planned_start=_date(
                    item.get("plannedStart"),
                    f"{path}.plannedStart",
                ),
                planned_finish=_date(
                    item.get("plannedFinish"),
                    f"{path}.plannedFinish",
                ),
                responsibility_kind=_enum_value(
                    item.get("responsibilityKind"),
                    ToolingMilestoneResponsibilityKind,
                    f"{path}.responsibilityKind",
                ),
                responsible_member=(
                    _manufacturing_member(
                        member_value,
                        f"{path}.responsibleMember",
                    )
                    if member_value is not None
                    else None
                ),
                predecessor_global_ids=_uuid_list(
                    item.get("predecessorGlobalIds"),
                    f"{path}.predecessorGlobalIds",
                    maximum=20,
                ),
            )
        )
    return tuple(result)


def _milestone_evidence_inputs(
    value: object,
) -> tuple[dict[str, object], ...]:
    rows = _objects(value, "evidence", maximum=20)
    result = []
    expected = {
        "role",
        "fileRevisionGlobalId",
        "fileOptimisticVersion",
        "frappeContentHash",
        "sha256",
    }
    for index, item in enumerate(rows):
        path = f"evidence[{index}]"
        _exact_fields(item, expected, path)
        result.append(
            {
                "role": _enum_value(
                    item.get("role"),
                    ToolingMilestoneEvidenceRole,
                    f"{path}.role",
                ),
                "file_revision_id": _uuid(
                    item.get("fileRevisionGlobalId"),
                    f"{path}.fileRevisionGlobalId",
                ),
                "file_optimistic_version": _positive(
                    item.get("fileOptimisticVersion"),
                    f"{path}.fileOptimisticVersion",
                ),
                "frappe_content_hash": _content_hash(
                    item.get("frappeContentHash"),
                    f"{path}.frappeContentHash",
                ),
                "sha256": _sha256(
                    item.get("sha256"),
                    f"{path}.sha256",
                ),
            }
        )
    return tuple(result)


def _part_specification_items(value: object) -> tuple[dict[str, object], ...]:
    rows = _objects(value, "items", minimum=1, maximum=100)
    allowed = {
        "kind",
        "normalizedValue",
        "rawValue",
        "sourceSystem",
        "sourceObjectId",
        "effectiveFrom",
        "effectiveTo",
        "unit",
    }
    required = allowed - {"effectiveTo", "unit"}
    result = []
    for index, item in enumerate(rows):
        path = f"items[{index}]"
        _closed_fields(item, allowed, required, path)
        result.append(
            {
                "kind": _enum_value(
                    item.get("kind"),
                    PartSpecificationKind,
                    f"{path}.kind",
                ),
                "normalized_value": _text(
                    item.get("normalizedValue"),
                    f"{path}.normalizedValue",
                    240,
                ),
                "raw_value": _text(item.get("rawValue"), f"{path}.rawValue", 500),
                "source_system": _source_system(
                    item.get("sourceSystem"),
                    f"{path}.sourceSystem",
                ),
                "source_object_id": _text(
                    item.get("sourceObjectId"),
                    f"{path}.sourceObjectId",
                    128,
                ),
                "effective_from": _date(
                    item.get("effectiveFrom"),
                    f"{path}.effectiveFrom",
                ),
                "effective_to": _optional_date(
                    item.get("effectiveTo"),
                    f"{path}.effectiveTo",
                ),
                "unit": (
                    _text(item.get("unit"), f"{path}.unit", 32)
                    if "unit" in item
                    else None
                ),
            }
        )
    return tuple(result)


def _process_step_inputs(value: object) -> tuple[dict[str, object], ...]:
    rows = _objects(value, "steps", minimum=2, maximum=20)
    allowed = {
        "stepOrder",
        "processKind",
        "toolingRevisionGlobalId",
        "inputPartRevisionGlobalIds",
        "outputPartRevisionGlobalId",
        "parentStepOrder",
        "machineType",
        "clampTonnage",
    }
    required = allowed - {"parentStepOrder"}
    result = []
    for index, item in enumerate(rows):
        path = f"steps[{index}]"
        _closed_fields(item, allowed, required, path)
        result.append(
            {
                "step_order": _positive(item.get("stepOrder"), f"{path}.stepOrder"),
                "process_kind": _enum_value(
                    item.get("processKind"),
                    ToolingProcessKind,
                    f"{path}.processKind",
                ),
                "tooling_revision_id": _uuid(
                    item.get("toolingRevisionGlobalId"),
                    f"{path}.toolingRevisionGlobalId",
                ),
                "input_part_revision_ids": _uuid_list(
                    item.get("inputPartRevisionGlobalIds"),
                    f"{path}.inputPartRevisionGlobalIds",
                    maximum=20,
                ),
                "output_part_revision_id": _uuid(
                    item.get("outputPartRevisionGlobalId"),
                    f"{path}.outputPartRevisionGlobalId",
                ),
                "parent_step_order": (
                    _positive(item.get("parentStepOrder"), f"{path}.parentStepOrder")
                    if "parentStepOrder" in item
                    else None
                ),
                "machine_type": _text(
                    item.get("machineType"),
                    f"{path}.machineType",
                    120,
                ),
                "clamp_tonnage": _measurement(
                    item.get("clampTonnage"),
                    f"{path}.clampTonnage",
                ),
            }
        )
    if [item["step_order"] for item in result] != list(range(1, len(result) + 1)):
        raise _field("steps", _("Process step order must be contiguous."))
    return tuple(result)


def _measurement(value: object, path: str) -> ToolingMeasurement:
    if not isinstance(value, Mapping):
        raise _field(path, _("Enter a valid unit-bearing measurement."))
    _exact_fields(value, {"value", "unit", "source"}, path)
    try:
        return measurement_from_dict(value, path)
    except RequestValidationFailed:
        raise


def _source_system(value: object, path: str) -> str:
    parsed = str(value)
    if parsed not in _REFERENCE_SYSTEMS:
        raise _field(path, _("Select a supported value."))
    return parsed


def _enum_value(value: object, enum_type, path: str):
    try:
        return enum_type(str(value))
    except ValueError as error:
        raise _field(path, _("Select a supported value.")) from error


def _closed_fields(
    value: Mapping[str, object],
    allowed: set[str],
    required: set[str],
    path: str,
) -> None:
    if not required.issubset(value) or not set(value).issubset(allowed):
        raise _field(path, _("Select a supported value."))


def _utc_timestamp(value: object, path: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise _field(path, _("Enter a valid date and time."))
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise _field(path, _("Enter a valid date and time.")) from error
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise _field(path, _("Enter a valid date and time."))
    return parsed.astimezone(UTC)


def _non_negative(value: object, path: str) -> int:
    if type(value) is not int or value < 0 or value > 2_147_483_647:
        raise _field(path, _("Enter a non-negative whole number."))
    return value


def _boolean(value: object, path: str) -> bool:
    if type(value) is not bool:
        raise _field(path, _("Select a supported value."))
    return value


def _percentage(value: object, path: str) -> int:
    if type(value) is not int or not 0 <= value <= 100:
        raise _field(path, _("Progress percentage must be between zero and one hundred."))
    return value


def _optional_text(value: object, path: str, maximum: int) -> str | None:
    return None if value in (None, "") else _text(value, path, maximum)


def _sha256(value: object, path: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise _field(path, _("Enter a valid SHA-256 value."))
    return value


def _content_hash(value: object, path: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{32,128}", value) is None:
        raise _field(path, _("Enter a valid content hash."))
    return value


def _defect_detection_context(value: object) -> dict[str, object]:
    path = "detectionContext"
    if not isinstance(value, Mapping):
        raise _field(path, _("Select a supported value."))
    _closed_fields(
        value,
        {"kind", "globalId", "snapshotHash"},
        {"kind", "globalId", "snapshotHash"},
        path,
    )
    kind = _enum_value(value.get("kind"), ToolingDefectContextKind, f"{path}.kind")
    global_id = _optional_uuid(value.get("globalId"), f"{path}.globalId")
    snapshot = value.get("snapshotHash")
    snapshot_hash = (
        None if snapshot in (None, "") else _sha256(snapshot, f"{path}.snapshotHash")
    )
    if kind is ToolingDefectContextKind.UNAVAILABLE_TRIAL_CONTEXT:
        if global_id is not None or snapshot_hash is not None:
            raise _field(path, _("Select a supported value."))
    elif global_id is None or snapshot_hash is None:
        raise _field(path, _("Select a supported value."))
    return {
        "kind": kind,
        "global_id": global_id,
        "snapshot_hash": snapshot_hash,
    }


def _defect_evidence_inputs(
    value: object,
    path: str,
    *,
    maximum: int = 100,
) -> tuple[dict[str, object], ...]:
    rows = _objects(value, path, maximum=maximum)
    result = []
    expected = {
        "role",
        "fileRevisionGlobalId",
        "fileOptimisticVersion",
        "frappeContentHash",
        "sha256",
    }
    for index, item in enumerate(rows):
        item_path = f"{path}[{index}]"
        _exact_fields(item, expected, item_path)
        result.append(
            {
                "role": _enum_value(
                    item.get("role"),
                    ToolingDefectEvidenceRole,
                    f"{item_path}.role",
                ),
                "file_revision_id": _uuid(
                    item.get("fileRevisionGlobalId"),
                    f"{item_path}.fileRevisionGlobalId",
                ),
                "file_optimistic_version": _positive(
                    item.get("fileOptimisticVersion"),
                    f"{item_path}.fileOptimisticVersion",
                ),
                "frappe_content_hash": _content_hash(
                    item.get("frappeContentHash"),
                    f"{item_path}.frappeContentHash",
                ),
                "sha256": _sha256(
                    item.get("sha256"),
                    f"{item_path}.sha256",
                ),
            }
        )
    return tuple(result)


def _defect_actions(value: object) -> tuple[dict[str, object], ...]:
    rows = _objects(value, "actions", maximum=100)
    result = []
    allowed = {
        "globalId",
        "actionType",
        "state",
        "detail",
        "responsibleMember",
        "dueDate",
        "evidence",
    }
    required = allowed - {"globalId"}
    for index, item in enumerate(rows):
        path = f"actions[{index}]"
        _closed_fields(item, allowed, required, path)
        result.append(
            {
                "global_id": _optional_uuid(item.get("globalId"), f"{path}.globalId"),
                "action_type": _enum_value(
                    item.get("actionType"),
                    ToolingDefectActionType,
                    f"{path}.actionType",
                ),
                "state": _enum_value(
                    item.get("state"),
                    ToolingDefectActionState,
                    f"{path}.state",
                ),
                "detail": _text(item.get("detail"), f"{path}.detail", 2000),
                "responsible_member": _manufacturing_member(
                    item.get("responsibleMember"),
                    f"{path}.responsibleMember",
                ),
                "due_date": _date(item.get("dueDate"), f"{path}.dueDate"),
                "evidence": _defect_evidence_inputs(
                    item.get("evidence"),
                    f"{path}.evidence",
                    maximum=20,
                ),
            }
        )
    return tuple(result)


def _process_context_input(value: object) -> dict[str, object]:
    path = "context"
    if not isinstance(value, Mapping):
        raise _field(path, _("Select a supported value."))
    _exact_fields(value, {"kind", "globalId", "snapshotHash"}, path)
    kind = _enum_value(value.get("kind"), ToolingProcessContextKind, f"{path}.kind")
    if kind not in {
        ToolingProcessContextKind.RELEASED_DOCUMENT,
        ToolingProcessContextKind.TOOLING_REVISION_SPECIFICATION,
    }:
        raise _field(f"{path}.kind", _("Select a supported value."))
    return {
        "kind": kind,
        "global_id": _uuid(value.get("globalId"), f"{path}.globalId"),
        "snapshot_hash": _sha256(
            value.get("snapshotHash"),
            f"{path}.snapshotHash",
        ),
    }


def _process_metric_inputs(value: object) -> tuple[dict[str, object], ...]:
    rows = _objects(value, "metrics", minimum=1, maximum=32)
    result = []
    fields = {
        "code",
        "valueKind",
        "numericValue",
        "textValue",
        "unit",
        "comparisonRule",
    }
    for index, item in enumerate(rows):
        path = f"metrics[{index}]"
        _exact_fields(item, fields, path)
        kind = _enum_value(
            item.get("valueKind"),
            ToolingProcessValueKind,
            f"{path}.valueKind",
        )
        numeric_value = item.get("numericValue")
        text_value = item.get("textValue")
        unit = item.get("unit")
        if kind is ToolingProcessValueKind.NUMERIC:
            numeric = _decimal_string(numeric_value, f"{path}.numericValue")
            text = None if text_value in (None, "") else _text(text_value, f"{path}.textValue", 255)
            exact_unit = _text(unit, f"{path}.unit", 32)
            if text is not None:
                raise _field(path, _("Select a supported value."))
        else:
            numeric = None
            text = _text(text_value, f"{path}.textValue", 255)
            exact_unit = None
            if numeric_value not in (None, "") or unit not in (None, ""):
                raise _field(path, _("Select a supported value."))
        rule_value = item.get("comparisonRule")
        rule = None
        if rule_value is not None:
            if not isinstance(rule_value, Mapping):
                raise _field(f"{path}.comparisonRule", _("Select a supported value."))
            rule_path = f"{path}.comparisonRule"
            _exact_fields(rule_value, {"unit", "minimum", "maximum"}, rule_path)
            rule = {
                "unit": _text(rule_value.get("unit"), f"{rule_path}.unit", 32),
                "minimum": _decimal_string(
                    rule_value.get("minimum"),
                    f"{rule_path}.minimum",
                ),
                "maximum": _decimal_string(
                    rule_value.get("maximum"),
                    f"{rule_path}.maximum",
                ),
            }
            if kind is not ToolingProcessValueKind.NUMERIC or rule["unit"] != exact_unit:
                raise _field(rule_path, _("Select a supported value."))
        result.append(
            {
                "code": _enum_value(
                    item.get("code"),
                    ToolingProcessMetricCode,
                    f"{path}.code",
                ),
                "value_kind": kind,
                "numeric_value": numeric,
                "text_value": text,
                "unit": exact_unit,
                "comparison_rule": rule,
            }
        )
    if len({item["code"] for item in result}) != len(result):
        raise _field("metrics", _("Enter a valid bounded list."))
    return tuple(result)


def _capacity_line_inputs(value: object) -> tuple[dict[str, object], ...]:
    rows = _objects(value, "lines", minimum=1, maximum=100)
    result = []
    fields = {
        "partRevisionGlobalId",
        "partRevisionSnapshotHash",
        "applicabilityGlobalId",
        "applicabilitySnapshotHash",
        "availableHoursPerDay",
        "workingDaysPerMonth",
        "oeeRatio",
        "yieldRatio",
        "cycleSeconds",
        "cavityCount",
        "usagePerAssembly",
        "effectiveSetCount",
        "selectedToolingSetGlobalIds",
        "cycleProvenance",
        "cavityProvenance",
        "usageProvenance",
        "setProvenance",
    }
    for index, item in enumerate(rows):
        path = f"lines[{index}]"
        _exact_fields(item, fields, path)
        days = _positive(item.get("workingDaysPerMonth"), f"{path}.workingDaysPerMonth")
        if days > 31:
            raise _field(f"{path}.workingDaysPerMonth", _("Select a supported value."))
        result.append(
            {
                "part_revision_id": _uuid(
                    item.get("partRevisionGlobalId"),
                    f"{path}.partRevisionGlobalId",
                ),
                "part_revision_snapshot_hash": _sha256(
                    item.get("partRevisionSnapshotHash"),
                    f"{path}.partRevisionSnapshotHash",
                ),
                "applicability_id": _uuid(
                    item.get("applicabilityGlobalId"),
                    f"{path}.applicabilityGlobalId",
                ),
                "applicability_snapshot_hash": _sha256(
                    item.get("applicabilitySnapshotHash"),
                    f"{path}.applicabilitySnapshotHash",
                ),
                "available_hours_per_day": _decimal_string(
                    item.get("availableHoursPerDay"),
                    f"{path}.availableHoursPerDay",
                    nonnegative=True,
                    maximum=Decimal("24"),
                ),
                "working_days_per_month": days,
                "oee_ratio": _decimal_string(
                    item.get("oeeRatio"),
                    f"{path}.oeeRatio",
                    nonnegative=True,
                    maximum=Decimal("1"),
                ),
                "yield_ratio": _decimal_string(
                    item.get("yieldRatio"),
                    f"{path}.yieldRatio",
                    nonnegative=True,
                    maximum=Decimal("1"),
                ),
                "cycle_seconds": _decimal_string(
                    item.get("cycleSeconds"),
                    f"{path}.cycleSeconds",
                    positive=True,
                ),
                "cavity_count": _positive(
                    item.get("cavityCount"),
                    f"{path}.cavityCount",
                ),
                "usage_per_assembly": _decimal_string(
                    item.get("usagePerAssembly"),
                    f"{path}.usagePerAssembly",
                    positive=True,
                ),
                "effective_set_count": _non_negative(
                    item.get("effectiveSetCount"),
                    f"{path}.effectiveSetCount",
                ),
                "selected_tooling_set_ids": _uuid_list(
                    item.get("selectedToolingSetGlobalIds"),
                    f"{path}.selectedToolingSetGlobalIds",
                    maximum=100,
                ),
                "cycle_provenance": _capacity_provenance_input(
                    item.get("cycleProvenance"),
                    f"{path}.cycleProvenance",
                ),
                "cavity_provenance": _capacity_provenance_input(
                    item.get("cavityProvenance"),
                    f"{path}.cavityProvenance",
                ),
                "usage_provenance": _capacity_provenance_input(
                    item.get("usageProvenance"),
                    f"{path}.usageProvenance",
                ),
                "set_provenance": _capacity_provenance_input(
                    item.get("setProvenance"),
                    f"{path}.setProvenance",
                ),
            }
        )
    if len({item["applicability_id"] for item in result}) != len(result):
        raise _field("lines", _("Enter a valid bounded list."))
    return tuple(result)


def _capacity_provenance_input(value: object, path: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise _field(path, _("Select a supported value."))
    _exact_fields(value, {"kind", "globalId", "snapshotHash"}, path)
    kind = _enum_value(value.get("kind"), CapacityProvenanceKind, f"{path}.kind")
    global_id = _optional_uuid(value.get("globalId"), f"{path}.globalId")
    if (kind is CapacityProvenanceKind.SCENARIO_ASSUMPTION) != (global_id is None):
        raise _field(f"{path}.globalId", _("Select a supported value."))
    return {
        "kind": kind,
        "global_id": global_id,
        "snapshot_hash": _sha256(value.get("snapshotHash"), f"{path}.snapshotHash"),
    }


def _decimal_string(
    value: object,
    path: str,
    *,
    nonnegative: bool = False,
    positive: bool = False,
    maximum: Decimal | None = None,
) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise _field(path, _("Enter a valid decimal amount."))
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise _field(path, _("Enter a valid decimal amount.")) from error
    if (
        not parsed.is_finite()
        or len(value) > 32
        or parsed.adjusted() > 24
        or parsed.adjusted() < -24
        or (positive and parsed <= 0)
        or (nonnegative and parsed < 0)
        or (maximum is not None and parsed > maximum)
    ):
        raise _field(path, _("Enter a valid decimal amount."))
    normalized = "0" if parsed == 0 else format(parsed.normalize(), "f")
    return normalized if "." in normalized else f"{normalized}.0"


def _field(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
