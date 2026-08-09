from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

import frappe

from npi_core.documents.frappe_repository import FrappeDocumentRepository
from npi_core.npi_core.doctype.npi_file_revision.npi_file_revision import (
    has_live_private_file_identity,
)
from npi_core.foundation.audit import create_audit_event
from npi_core.foundation.errors import RequestValidationFailed
from npi_core.tooling.domain import (
    EngineeringPart,
    EngineeringPartRevision,
    ToolingAccessoryLine,
    ToolingApplicability,
    ToolingApplicabilityConflict,
    ToolingDifferenceSourceKind,
    ToolingEvidenceConflict,
    ToolingIdempotencyConflict,
    ToolingInspectionCategory,
    ToolingInspectionObservation,
    ToolingIntake,
    ToolingIntakeDifference,
    ToolingIntakeEvidenceReference,
    ToolingIntakeEvidenceRole,
    ToolingIntakeVersionConflict,
    ToolingMaster,
    ToolingReferenceUnavailable,
    ToolingRequirement,
    ToolingRequirementKind,
    ToolingSet,
    ToolingVersionConflict,
    ensure_no_effectivity_overlap,
    sha256_json,
    validate_applicability_successor,
    validate_intake_successor,
)
from npi_core.tooling.frappe_validation import tooling_command_write
from npi_core.tooling.acceptance_repository import ToolingAcceptanceRepositoryMixin
from npi_core.tooling.engineering_controls_repository import (
    ToolingEngineeringControlsRepositoryMixin,
)
from npi_core.tooling.manufacturing_repository import ToolingManufacturingRepositoryMixin
from npi_core.tooling.revision_repository import ToolingRevisionRepositoryMixin
from npi_core.tooling.diagnostics import (
    applicability_create_server_step,
    part_create_server_step,
)


_MAX_MASTERS = 200
_MAX_REQUIREMENTS = 200
_MAX_PARTS = 500
_MAX_APPLICABILITY = 1_000
_MAX_SETS = 200
_MAX_INTAKES = 100
_MAX_EVIDENCE = 500


@dataclass(frozen=True, slots=True)
class ToolingCommandOutcome:
    response: dict[str, Any]
    replayed: bool = False


class FrappeToolingRepository(
    ToolingAcceptanceRepositoryMixin,
    ToolingEngineeringControlsRepositoryMixin,
    ToolingManufacturingRepositoryMixin,
    ToolingRevisionRepositoryMixin,
    FrappeDocumentRepository,
):
    """Project-first persistence adapter for the bounded P6-01 slice."""

    def __init__(
        self,
        *,
        clock=None,
        uuid_factory=uuid4,
        procurement_cost_reader=None,
        **values: object,
    ) -> None:
        super().__init__(**values)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._uuid_factory = uuid_factory
        self._procurement_cost_reader = procurement_cost_reader

    def authorize_scope(
        self,
        project_id: UUID,
        tooling_master_id: UUID | None = None,
        *,
        administer: bool = False,
    ) -> bool:
        project = self._authorized_project(project_id)
        if project is None:
            return False
        if administer and not self._can_administer_project(project, project_id):
            return False
        return bool(
            tooling_master_id is None
            or self._master_for_project(project, tooling_master_id) is not None
        )

    def cockpit(self, project_id: UUID) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        return self._cockpit_for(project)

    def master_detail(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        master = self._master_for_project(project, tooling_master_id)
        if master is None:
            return None
        applications = tuple(
            value
            for value in self._applicabilities(project)
            if str(value.tooling_master_global_id) == str(tooling_master_id)
        )
        revision_ids = {str(value.part_revision_global_id) for value in applications}
        part_ids = {str(value.part_global_id) for value in applications}
        parts = tuple(
            value
            for value in self._parts(project)
            if str(value.global_id) in part_ids
        )
        requirements = tuple(
            value
            for value in self._requirements(project)
            if value.target_part_revision_global_id is not None
            and str(value.target_part_revision_global_id) in revision_ids
        )
        return self._cockpit_response(
            project,
            masters=(self._master_value(master),),
            requirements=requirements,
            parts=parts,
            applications=applications,
        )

    def tooling_sets(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        if self._master_for_project(project, tooling_master_id) is None:
            return None
        return self._tooling_set_collection(project, tooling_master_id)

    def tooling_set_detail(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        tooling_set_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        if self._master_for_project(project, tooling_master_id) is None:
            return None
        tooling_set = self._tooling_set_for_project(
            project,
            tooling_master_id,
            tooling_set_id,
        )
        if tooling_set is None:
            return None
        return self._tooling_set_detail(project, tooling_set)

    def create_part(
        self,
        project_id: UUID,
        *,
        idempotency_key_hash: str,
        title: str,
        revision_label: str,
        reason: str,
    ) -> ToolingCommandOutcome | None:
        with part_create_server_step("P601_PART_CREATE_PROJECT_LOCK"):
            project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "title": title,
            "revisionLabel": revision_label,
            "reason": reason,
        }
        with part_create_server_step("P601_PART_CREATE_IDEMPOTENCY_CONTEXT"):
            context = self._command_context(
                project,
                operation="part.create",
                idempotency_key_hash=idempotency_key_hash,
                payload=payload,
            )
        if isinstance(context, dict):
            return ToolingCommandOutcome(context, replayed=True)
        receipt_key, payload_hash = context
        now = self._now()
        part_id = self._new_uuid()
        with part_create_server_step("P601_PART_CREATE_DOMAIN_BUILD"):
            revision = EngineeringPartRevision(
                global_id=self._new_uuid(),
                part_global_id=part_id,
                tenant_id=str(project.tenant_id),
                originating_project_global_id=project_id,
                revision_number=1,
                revision_label=revision_label,
                title=title,
                reason=reason,
                predecessor_global_id=None,
                predecessor_snapshot_hash=None,
                created_by_user_id=self.actor,
                created_at=now,
                request_id=UUID(self.request_id),
                trace_id=self.trace_id,
            )
        with tooling_command_write():
            with part_create_server_step("P601_PART_CREATE_RECEIPT_INSERT"):
                receipt = self._insert_receipt(
                    project,
                    receipt_key=receipt_key,
                    operation="part.create",
                    idempotency_key_hash=idempotency_key_hash,
                    payload_hash=payload_hash,
                    now=now,
                )
            with part_create_server_step("P601_PART_CREATE_ROOT_INSERT"):
                root = frappe.get_doc(
                    {
                        "doctype": "NPI Engineering Part",
                        "global_id": str(part_id),
                        "tenant_id": str(project.tenant_id),
                        "originating_project_global_id": str(project_id),
                        "title": title,
                        "current_revision_global_id": None,
                        "current_revision_number": None,
                        "current_revision_snapshot_hash": None,
                        "optimistic_version": 1,
                    }
                ).insert()
            with part_create_server_step("P601_PART_CREATE_REVISION_INSERT"):
                self._insert_part_revision(revision)
            with part_create_server_step("P601_PART_CREATE_ROOT_POINTER_SAVE"):
                root.current_revision_global_id = str(revision.global_id)
                root.current_revision_number = revision.revision_number
                root.current_revision_snapshot_hash = revision.snapshot_hash
                root.title = revision.title
                root.save()
            with part_create_server_step("P601_PART_CREATE_AUDIT_APPEND"):
                self._append_audit(
                    operation="part.create",
                    global_id=part_id,
                    object_version=int(root.optimistic_version),
                    summary={
                        "projectId": str(project_id),
                        "revisionId": str(revision.global_id),
                        "requestId": self.request_id,
                    },
                )
            with part_create_server_step("P601_PART_CREATE_RESPONSE_BUILD"):
                response = self._cockpit_for(project)
            with part_create_server_step("P601_PART_CREATE_RECEIPT_SEAL"):
                self._seal_receipt(
                    receipt,
                    target_type="part",
                    target_id=part_id,
                    response=response,
                    now=now,
                )
        return ToolingCommandOutcome(response)

    def create_part_revision(
        self,
        project_id: UUID,
        part_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_version: int,
        revision_label: str,
        title: str,
        reason: str,
    ) -> ToolingCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        root = self._locked_part_for_project(project, part_id)
        if root is None:
            return None
        payload = {
            "partGlobalId": str(part_id),
            "expectedVersion": expected_version,
            "revisionLabel": revision_label,
            "title": title,
            "reason": reason,
        }
        context = self._command_context(
            project,
            operation="part.revise",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(context, dict):
            return ToolingCommandOutcome(context, replayed=True)
        receipt_key, payload_hash = context
        if int(root.optimistic_version) != expected_version:
            raise ToolingVersionConflict()
        current = self._part_revision_for_project(
            project,
            UUID(str(root.current_revision_global_id)),
            require_current=True,
        )
        if current is None:
            raise RuntimeError("The current Part Revision pointer is unavailable.")
        part = self._part_value(root, current)
        now = self._now()
        revision = EngineeringPartRevision(
            global_id=self._new_uuid(),
            part_global_id=part_id,
            tenant_id=str(project.tenant_id),
            originating_project_global_id=project_id,
            revision_number=part.current_revision_number + 1,
            revision_label=revision_label,
            title=title,
            reason=reason,
            predecessor_global_id=part.current_revision_global_id,
            predecessor_snapshot_hash=part.current_revision_snapshot_hash,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        advanced = part.advance(revision)
        with tooling_command_write():
            receipt = self._insert_receipt(
                project,
                receipt_key=receipt_key,
                operation="part.revise",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._insert_part_revision(revision)
            root.current_revision_global_id = str(advanced.current_revision_global_id)
            root.current_revision_number = advanced.current_revision_number
            root.current_revision_snapshot_hash = advanced.current_revision_snapshot_hash
            root.title = advanced.title
            root.save()
            if int(root.optimistic_version) != advanced.optimistic_version:
                raise RuntimeError("The Part projection version drifted.")
            self._append_audit(
                operation="part.revise",
                global_id=revision.global_id,
                object_version=revision.revision_number,
                summary={
                    "partId": str(part_id),
                    "projectId": str(project_id),
                    "requestId": self.request_id,
                },
            )
            response = self._cockpit_for(project)
            self._seal_receipt(
                receipt,
                target_type="part_revision",
                target_id=revision.global_id,
                response=response,
                now=now,
            )
        return ToolingCommandOutcome(response)

    def create_requirement(
        self,
        project_id: UUID,
        *,
        idempotency_key_hash: str,
        kind: ToolingRequirementKind,
        title: str,
        reason: str,
        target_part_revision_id: UUID | None,
        target_date: date | None,
    ) -> ToolingCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "kind": kind.value,
            "title": title,
            "reason": reason,
            "targetPartRevisionGlobalId": (
                str(target_part_revision_id)
                if target_part_revision_id is not None
                else None
            ),
            "targetDate": target_date.isoformat() if target_date else None,
        }
        context = self._command_context(
            project,
            operation="tooling_requirement.create",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(context, dict):
            return ToolingCommandOutcome(context, replayed=True)
        receipt_key, payload_hash = context
        if target_part_revision_id is not None and self._part_revision_for_project(
            project,
            target_part_revision_id,
            require_current=True,
        ) is None:
            raise ToolingReferenceUnavailable()
        now = self._now()
        requirement = ToolingRequirement(
            global_id=self._new_uuid(),
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            kind=kind,
            title=title,
            reason=reason,
            target_part_revision_global_id=target_part_revision_id,
            target_date=target_date,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        with tooling_command_write():
            receipt = self._insert_receipt(
                project,
                receipt_key=receipt_key,
                operation="tooling_requirement.create",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._insert_requirement(requirement)
            self._append_audit(
                operation="tooling_requirement.create",
                global_id=requirement.global_id,
                object_version=1,
                summary={"projectId": str(project_id), "requestId": self.request_id},
            )
            response = self._cockpit_for(project)
            self._seal_receipt(
                receipt,
                target_type="tooling_requirement",
                target_id=requirement.global_id,
                response=response,
                now=now,
            )
        return ToolingCommandOutcome(response)

    def create_master(
        self,
        project_id: UUID,
        *,
        idempotency_key_hash: str,
        title: str,
    ) -> ToolingCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {"title": title}
        context = self._command_context(
            project,
            operation="tooling_master.create",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(context, dict):
            return ToolingCommandOutcome(context, replayed=True)
        receipt_key, payload_hash = context
        now = self._now()
        master = ToolingMaster(
            global_id=self._new_uuid(),
            tenant_id=str(project.tenant_id),
            originating_project_global_id=project_id,
            title=title,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        with tooling_command_write():
            receipt = self._insert_receipt(
                project,
                receipt_key=receipt_key,
                operation="tooling_master.create",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._insert_master(master)
            self._append_audit(
                operation="tooling_master.create",
                global_id=master.global_id,
                object_version=1,
                summary={"projectId": str(project_id), "requestId": self.request_id},
            )
            response = self._cockpit_for(project)
            self._seal_receipt(
                receipt,
                target_type="tooling_master",
                target_id=master.global_id,
                response=response,
                now=now,
            )
        return ToolingCommandOutcome(response)

    def create_applicability(
        self,
        project_id: UUID,
        *,
        idempotency_key_hash: str,
        tooling_master_id: UUID,
        part_revision_id: UUID,
        product: Mapping[str, str] | None,
        model: Mapping[str, str] | None,
        relationship_id: UUID | None,
        expected_version: int | None,
        effective_from: date,
        effective_to: date | None,
        reason: str,
    ) -> ToolingCommandOutcome | None:
        with applicability_create_server_step(
            "P601_APPLICABILITY_CREATE_PROJECT_LOCK"
        ):
            project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "toolingMasterGlobalId": str(tooling_master_id),
            "partRevisionGlobalId": str(part_revision_id),
            "product": dict(product) if product is not None else None,
            "model": dict(model) if model is not None else None,
            "relationshipGlobalId": (
                str(relationship_id) if relationship_id is not None else None
            ),
            "expectedVersion": expected_version,
            "effectiveFrom": effective_from.isoformat(),
            "effectiveTo": effective_to.isoformat() if effective_to else None,
            "reason": reason,
        }
        with applicability_create_server_step(
            "P601_APPLICABILITY_CREATE_IDEMPOTENCY_CONTEXT"
        ):
            context = self._command_context(
                project,
                operation="tooling_applicability.create",
                idempotency_key_hash=idempotency_key_hash,
                payload=payload,
            )
        if isinstance(context, dict):
            return ToolingCommandOutcome(context, replayed=True)
        receipt_key, payload_hash = context
        with applicability_create_server_step(
            "P601_APPLICABILITY_CREATE_REFERENCE_LOAD"
        ):
            master_row = self._same_tenant_master(project, tooling_master_id)
            revision = self._part_revision_for_project(
                project,
                part_revision_id,
                require_current=True,
            )
        if master_row is None or revision is None:
            raise ToolingReferenceUnavailable()
        part_id = revision.part_global_id
        with applicability_create_server_step(
            "P601_APPLICABILITY_CREATE_REFERENCE_VALIDATE"
        ):
            self._require_project_reference(project, product)
            self._require_project_reference(project, model)
        with applicability_create_server_step(
            "P601_APPLICABILITY_CREATE_RETAINED_LOAD"
        ):
            retained = self._applicabilities(project)
        with applicability_create_server_step(
            "P601_APPLICABILITY_CREATE_PREDECESSOR_RESOLVE"
        ):
            previous = None
            if relationship_id is not None:
                versions = tuple(
                    value
                    for value in retained
                    if value.relationship_global_id == relationship_id
                )
                if not versions:
                    raise ToolingReferenceUnavailable()
                previous = max(
                    versions,
                    key=lambda value: value.applicability_version,
                )
                if previous.applicability_version != expected_version:
                    raise ToolingVersionConflict()
            elif expected_version is not None:
                raise ToolingVersionConflict()
        with applicability_create_server_step(
            "P601_APPLICABILITY_CREATE_DOMAIN_BUILD"
        ):
            now = self._now()
            applicability = ToolingApplicability(
                global_id=self._new_uuid(),
                relationship_global_id=relationship_id or self._new_uuid(),
                tenant_id=str(project.tenant_id),
                project_global_id=project_id,
                tooling_master_global_id=tooling_master_id,
                part_global_id=part_id,
                part_revision_global_id=part_revision_id,
                product_source_system=(product or {}).get("sourceSystem"),
                product_source_object_id=(product or {}).get("sourceObjectId"),
                model_source_system=(model or {}).get("sourceSystem"),
                model_source_object_id=(model or {}).get("sourceObjectId"),
                applicability_version=(
                    previous.applicability_version + 1
                    if previous is not None
                    else 1
                ),
                predecessor_global_id=(
                    previous.global_id if previous is not None else None
                ),
                predecessor_snapshot_hash=(
                    previous.snapshot_hash if previous is not None else None
                ),
                effective_from=effective_from,
                effective_to=effective_to,
                reason=reason,
                created_by_user_id=self.actor,
                created_at=now,
                request_id=UUID(self.request_id),
                trace_id=self.trace_id,
            )
        with applicability_create_server_step(
            "P601_APPLICABILITY_CREATE_DOMAIN_VALIDATE"
        ):
            try:
                if previous is not None:
                    validate_applicability_successor(previous, applicability)
                elif any(
                    value.relationship_key_hash == applicability.relationship_key_hash
                    for value in retained
                ):
                    raise ToolingApplicabilityConflict()
                ensure_no_effectivity_overlap(applicability, retained)
            except RequestValidationFailed as error:
                raise ToolingApplicabilityConflict() from error
        with tooling_command_write():
            with applicability_create_server_step(
                "P601_APPLICABILITY_CREATE_RECEIPT_INSERT"
            ):
                receipt = self._insert_receipt(
                    project,
                    receipt_key=receipt_key,
                    operation="tooling_applicability.create",
                    idempotency_key_hash=idempotency_key_hash,
                    payload_hash=payload_hash,
                    now=now,
                )
            with applicability_create_server_step(
                "P601_APPLICABILITY_CREATE_RELATIONSHIP_INSERT"
            ):
                try:
                    self._insert_applicability(applicability)
                except (
                    frappe.DuplicateEntryError,
                    frappe.UniqueValidationError,
                ) as error:
                    raise ToolingApplicabilityConflict() from error
            with applicability_create_server_step(
                "P601_APPLICABILITY_CREATE_AUDIT_APPEND"
            ):
                self._append_audit(
                    operation="tooling_applicability.create",
                    global_id=applicability.global_id,
                    object_version=applicability.applicability_version,
                    summary={
                        "projectId": str(project_id),
                        "relationshipId": str(applicability.relationship_global_id),
                        "requestId": self.request_id,
                    },
                )
            with applicability_create_server_step(
                "P601_APPLICABILITY_CREATE_RESPONSE_BUILD"
            ):
                response = self._cockpit_for(project)
            with applicability_create_server_step(
                "P601_APPLICABILITY_CREATE_RECEIPT_SEAL"
            ):
                self._seal_receipt(
                    receipt,
                    target_type="tooling_applicability",
                    target_id=applicability.global_id,
                    response=response,
                    now=now,
                )
        return ToolingCommandOutcome(response)

    def create_tooling_set(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        *,
        idempotency_key_hash: str,
        tooling_requirement_id: UUID,
        physical_serial: str,
        customer: Mapping[str, str] | None,
        custody_responsibility: str,
        repair_authorization_reference: str,
        return_conditions: str,
    ) -> ToolingCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "toolingMasterGlobalId": str(tooling_master_id),
            "toolingRequirementGlobalId": str(tooling_requirement_id),
            "physicalSerial": physical_serial,
            "customer": dict(customer) if customer is not None else None,
            "custodyResponsibility": custody_responsibility,
            "repairAuthorizationReference": repair_authorization_reference,
            "returnConditions": return_conditions,
        }
        context = self._command_context(
            project,
            operation="tooling_set.create",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(context, dict):
            return ToolingCommandOutcome(context, replayed=True)
        receipt_key, payload_hash = context
        if self._master_for_project(project, tooling_master_id) is None:
            return None
        requirement = self._requirement_for_set(project, tooling_requirement_id)
        if requirement is None:
            return None
        self._require_customer_reference(project, customer)
        now = self._now()
        tooling_set = ToolingSet(
            global_id=self._new_uuid(),
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            tooling_master_global_id=tooling_master_id,
            tooling_requirement_global_id=tooling_requirement_id,
            requirement_kind=requirement.kind,
            physical_serial=physical_serial,
            customer_source_system=(
                customer["sourceSystem"] if customer is not None else None
            ),
            customer_source_object_id=(
                customer["sourceObjectId"] if customer is not None else None
            ),
            custody_responsibility=custody_responsibility,
            repair_authorization_reference=repair_authorization_reference,
            return_conditions=return_conditions,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        with tooling_command_write():
            receipt = self._insert_receipt(
                project,
                receipt_key=receipt_key,
                operation="tooling_set.create",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._insert_tooling_set(tooling_set)
            self._append_audit(
                operation="tooling_set.create",
                global_id=tooling_set.global_id,
                object_version=1,
                summary={
                    "projectId": str(project_id),
                    "toolingMasterId": str(tooling_master_id),
                    "toolingRequirementId": str(tooling_requirement_id),
                    "requestId": self.request_id,
                },
            )
            response = self._tooling_set_collection(project, tooling_master_id)
            self._seal_receipt(
                receipt,
                target_type="tooling_set",
                target_id=tooling_set.global_id,
                response=response,
                now=now,
            )
        return ToolingCommandOutcome(response)

    def create_tooling_intake(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        tooling_set_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_version: int | None,
        transport_provider: str,
        transport_reference: str,
        arrived_at: datetime,
        custody_handover: str,
        accessories: tuple[ToolingAccessoryLine, ...],
        inspections: tuple[ToolingInspectionObservation, ...],
        differences: tuple[ToolingIntakeDifference, ...],
    ) -> ToolingCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "toolingMasterGlobalId": str(tooling_master_id),
            "toolingSetGlobalId": str(tooling_set_id),
            "expectedVersion": expected_version,
            "transportProvider": transport_provider,
            "transportReference": transport_reference,
            "arrivedAt": arrived_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "custodyHandover": custody_handover,
            "accessories": [value.snapshot_payload() for value in accessories],
            "inspections": [value.snapshot_payload() for value in inspections],
            "differences": [value.snapshot_payload() for value in differences],
        }
        context = self._command_context(
            project,
            operation="tooling_intake.create",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(context, dict):
            return ToolingCommandOutcome(context, replayed=True)
        receipt_key, payload_hash = context
        if self._master_for_project(project, tooling_master_id) is None:
            return None
        tooling_set = self._tooling_set_for_project(
            project,
            tooling_master_id,
            tooling_set_id,
        )
        if tooling_set is None:
            return None
        retained = self._intakes_for_set(project, tooling_set)
        previous = retained[-1] if retained else None
        if previous is None:
            if expected_version is not None:
                raise ToolingIntakeVersionConflict()
            intake_version = 1
        else:
            if expected_version != previous.intake_version:
                raise ToolingIntakeVersionConflict()
            intake_version = previous.intake_version + 1
        now = self._now()
        intake = ToolingIntake(
            global_id=self._new_uuid(),
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            tooling_master_global_id=tooling_master_id,
            tooling_set_global_id=tooling_set_id,
            intake_version=intake_version,
            predecessor_global_id=(previous.global_id if previous else None),
            predecessor_snapshot_hash=(previous.snapshot_hash if previous else None),
            transport_provider=transport_provider,
            transport_reference=transport_reference,
            arrived_at=arrived_at,
            custody_handover=custody_handover,
            accessories=accessories,
            inspections=inspections,
            differences=differences,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        if previous is not None:
            validate_intake_successor(previous, intake)
        with tooling_command_write():
            receipt = self._insert_receipt(
                project,
                receipt_key=receipt_key,
                operation="tooling_intake.create",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            try:
                self._insert_tooling_intake(intake)
            except (frappe.DuplicateEntryError, frappe.UniqueValidationError) as error:
                raise ToolingIntakeVersionConflict() from error
            self._append_audit(
                operation="tooling_intake.create",
                global_id=intake.global_id,
                object_version=intake.intake_version,
                summary={
                    "projectId": str(project_id),
                    "toolingMasterId": str(tooling_master_id),
                    "toolingSetId": str(tooling_set_id),
                    "requestId": self.request_id,
                },
            )
            response = self._tooling_set_detail(project, tooling_set)
            self._seal_receipt(
                receipt,
                target_type="tooling_intake",
                target_id=intake.global_id,
                response=response,
                now=now,
            )
        return ToolingCommandOutcome(response)

    def create_tooling_intake_evidence_reference(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        tooling_set_id: UUID,
        intake_id: UUID,
        *,
        idempotency_key_hash: str,
        evidence_role: ToolingIntakeEvidenceRole,
        difference_ids: tuple[UUID, ...],
        file_revision_id: UUID,
    ) -> ToolingCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "toolingMasterGlobalId": str(tooling_master_id),
            "toolingSetGlobalId": str(tooling_set_id),
            "toolingIntakeGlobalId": str(intake_id),
            "evidenceRole": evidence_role.value,
            "differenceGlobalIds": [str(value) for value in difference_ids],
            "fileRevisionGlobalId": str(file_revision_id),
        }
        context = self._command_context(
            project,
            operation="tooling_intake_evidence.create",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(context, dict):
            return ToolingCommandOutcome(context, replayed=True)
        receipt_key, payload_hash = context
        if self._master_for_project(project, tooling_master_id) is None:
            return None
        tooling_set = self._tooling_set_for_project(
            project,
            tooling_master_id,
            tooling_set_id,
        )
        if tooling_set is None:
            return None
        intake = self._intake_for_set(project, tooling_set, intake_id)
        if intake is None:
            return None
        available_difference_ids = {value.global_id for value in intake.differences}
        if any(value not in available_difference_ids for value in difference_ids):
            return None
        file_revision = self._file_revision_for_project(project, file_revision_id)
        if file_revision is None:
            return None
        now = self._now()
        evidence = ToolingIntakeEvidenceReference(
            global_id=self._new_uuid(),
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            tooling_master_global_id=tooling_master_id,
            tooling_set_global_id=tooling_set_id,
            tooling_intake_global_id=intake_id,
            intake_snapshot_hash=intake.snapshot_hash,
            evidence_role=evidence_role,
            difference_global_ids=difference_ids,
            file_revision_global_id=file_revision_id,
            file_optimistic_version=int(file_revision.optimistic_version),
            frappe_content_hash=str(file_revision.frappe_content_hash).lower(),
            file_name=str(file_revision.file_name),
            mime_type=str(file_revision.mime_type),
            size_bytes=int(file_revision.size_bytes),
            sha256=str(file_revision.sha256).lower(),
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        with tooling_command_write():
            receipt = self._insert_receipt(
                project,
                receipt_key=receipt_key,
                operation="tooling_intake_evidence.create",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            try:
                self._insert_tooling_intake_evidence(evidence)
            except (frappe.DuplicateEntryError, frappe.UniqueValidationError) as error:
                raise ToolingEvidenceConflict() from error
            self._append_audit(
                operation="tooling_intake_evidence.create",
                global_id=evidence.global_id,
                object_version=intake.intake_version,
                summary={
                    "projectId": str(project_id),
                    "toolingMasterId": str(tooling_master_id),
                    "toolingSetId": str(tooling_set_id),
                    "toolingIntakeId": str(intake_id),
                    "requestId": self.request_id,
                },
            )
            response = self._tooling_set_detail(project, tooling_set)
            self._seal_receipt(
                receipt,
                target_type="tooling_intake_evidence",
                target_id=evidence.global_id,
                response=response,
                now=now,
            )
        return ToolingCommandOutcome(response)

    def _cockpit_for(self, project: object) -> dict[str, Any]:
        return self._cockpit_response(
            project,
            masters=self._masters(project),
            requirements=self._requirements(project),
            parts=self._parts(project),
            applications=self._applicabilities(project),
        )

    def _cockpit_response(
        self,
        project: object,
        *,
        masters: Sequence[ToolingMaster],
        requirements: Sequence[ToolingRequirement],
        parts: Sequence[EngineeringPart],
        applications: Sequence[ToolingApplicability],
    ) -> dict[str, Any]:
        revision_by_id: dict[str, EngineeringPartRevision] = {}
        for part in parts:
            revision = self._part_revision_for_project(
                project,
                part.current_revision_global_id,
                require_current=True,
            )
            if revision is None:
                raise RuntimeError("The current Part Revision pointer is unavailable.")
            revision_by_id[str(revision.global_id)] = revision
        for value in applications:
            key = str(value.part_revision_global_id)
            if key not in revision_by_id:
                revision = self._part_revision_for_project(
                    project,
                    value.part_revision_global_id,
                    require_current=False,
                )
                if revision is None:
                    raise RuntimeError("The exact Part Revision is unavailable.")
                revision_by_id[key] = revision
        return {
            "project": {
                "globalId": str(project.global_id),
                "businessCode": str(project.business_code),
                "title": str(project.title),
            },
            "permissions": self._tooling_permissions(),
            "masters": [
                self._master_response(value)
                for value in sorted(masters, key=lambda item: str(item.global_id))
            ],
            "requirements": [
                self._requirement_response(value)
                for value in sorted(requirements, key=lambda item: str(item.global_id))
            ],
            "parts": [
                self._part_response(
                    value,
                    revision_by_id[str(value.current_revision_global_id)],
                )
                for value in sorted(parts, key=lambda item: str(item.global_id))
            ],
            "applicability": [
                self._applicability_response(
                    value,
                    revision_by_id[str(value.part_revision_global_id)],
                )
                for value in sorted(
                    applications,
                    key=lambda item: (
                        str(item.relationship_global_id),
                        item.applicability_version,
                    ),
                )
            ],
            "downstream": {
                "lifecycle": self._unavailable("lifecycle_policy_unavailable"),
                "revision": self._tooling_revision_capability(project),
                "physicalSet": self._unavailable("physical_set_not_delivered"),
                "trial": self._unavailable("trial_not_delivered"),
                "erp": self._unavailable("erp_projection_unavailable"),
            },
        }

    def _masters(self, project: object) -> tuple[ToolingMaster, ...]:
        applications = self._applicabilities(project)
        identifiers = {
            str(value.tooling_master_global_id) for value in applications
        }
        originating = self._bounded_documents(
            "NPI Tooling Master",
            filters={
                "tenant_id": str(project.tenant_id),
                "originating_project_global_id": str(project.global_id),
            },
            maximum=_MAX_MASTERS,
        )
        identifiers.update(str(value.global_id) for value in originating)
        if len(identifiers) > _MAX_MASTERS:
            raise RuntimeError("The Tooling Master collection exceeds its safe bound.")
        result = []
        for identifier in sorted(identifiers):
            row = self._same_tenant_master(project, UUID(identifier))
            if row is None:
                raise RuntimeError("The Tooling Master is unavailable.")
            result.append(self._master_value(row))
        return tuple(result)

    def _requirements(self, project: object) -> tuple[ToolingRequirement, ...]:
        rows = self._bounded_documents(
            "NPI Tooling Requirement",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
            },
            maximum=_MAX_REQUIREMENTS,
        )
        return tuple(self._requirement_value(value) for value in rows)

    def _parts(self, project: object) -> tuple[EngineeringPart, ...]:
        rows = self._bounded_documents(
            "NPI Engineering Part",
            filters={
                "tenant_id": str(project.tenant_id),
                "originating_project_global_id": str(project.global_id),
            },
            maximum=_MAX_PARTS,
        )
        result = []
        for row in rows:
            if not row.current_revision_global_id:
                raise RuntimeError("The current Part Revision pointer is unavailable.")
            revision = self._part_revision_for_project(
                project,
                UUID(str(row.current_revision_global_id)),
                require_current=True,
            )
            if revision is None:
                raise RuntimeError("The current Part Revision pointer is unavailable.")
            result.append(self._part_value(row, revision))
        return tuple(result)

    def _applicabilities(self, project: object) -> tuple[ToolingApplicability, ...]:
        rows = self._bounded_documents(
            "NPI Tooling Applicability",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
            },
            maximum=_MAX_APPLICABILITY,
        )
        return tuple(self._applicability_value(value) for value in rows)

    def _tooling_set_collection(
        self,
        project: object,
        tooling_master_id: UUID,
    ) -> dict[str, Any]:
        return {
            "toolingMasterGlobalId": str(tooling_master_id),
            "permissions": self._tooling_set_permissions(),
            "items": [
                self._tooling_set_response(value)
                for value in self._tooling_sets_for_master(project, tooling_master_id)
            ],
        }

    def _tooling_set_detail(
        self,
        project: object,
        tooling_set: ToolingSet,
    ) -> dict[str, Any]:
        intakes = self._intakes_for_set(project, tooling_set)
        evidence = self._evidence_for_set(project, tooling_set)
        return {
            "toolingSet": self._tooling_set_response(tooling_set),
            "permissions": self._tooling_set_permissions(),
            "intakes": [self._intake_response(value) for value in intakes],
            "evidence": [self._evidence_response(value) for value in evidence],
        }

    def _tooling_sets_for_master(
        self,
        project: object,
        tooling_master_id: UUID,
    ) -> tuple[ToolingSet, ...]:
        rows = self._bounded_documents(
            "NPI Tooling Set",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "tooling_master_global_id": str(tooling_master_id),
            },
            maximum=_MAX_SETS,
        )
        return tuple(
            sorted(
                (self._tooling_set_value(value) for value in rows),
                key=lambda item: str(item.global_id),
            )
        )

    def _tooling_set_for_project(
        self,
        project: object,
        tooling_master_id: UUID,
        tooling_set_id: UUID,
    ) -> ToolingSet | None:
        row = _optional_doc("NPI Tooling Set", str(tooling_set_id))
        if row is None or any(
            (
                str(row.global_id) != str(tooling_set_id),
                str(row.tenant_id) != str(project.tenant_id),
                str(row.project_global_id) != str(project.global_id),
                str(row.tooling_master_global_id) != str(tooling_master_id),
            )
        ):
            return None
        return self._tooling_set_value(row)

    def _intakes_for_set(
        self,
        project: object,
        tooling_set: ToolingSet,
    ) -> tuple[ToolingIntake, ...]:
        rows = self._bounded_documents(
            "NPI Tooling Intake",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "tooling_master_global_id": str(tooling_set.tooling_master_global_id),
                "tooling_set_global_id": str(tooling_set.global_id),
            },
            maximum=_MAX_INTAKES,
        )
        result = tuple(
            sorted(
                (self._intake_value(value) for value in rows),
                key=lambda item: item.intake_version,
            )
        )
        for index, value in enumerate(result):
            if value.intake_version != index + 1:
                raise RuntimeError("The Tooling Intake version chain is not contiguous.")
            if index:
                validate_intake_successor(result[index - 1], value)
        return result

    def _intake_for_set(
        self,
        project: object,
        tooling_set: ToolingSet,
        intake_id: UUID,
    ) -> ToolingIntake | None:
        row = _optional_doc("NPI Tooling Intake", str(intake_id))
        if row is None or any(
            (
                str(row.global_id) != str(intake_id),
                str(row.tenant_id) != str(project.tenant_id),
                str(row.project_global_id) != str(project.global_id),
                str(row.tooling_master_global_id)
                != str(tooling_set.tooling_master_global_id),
                str(row.tooling_set_global_id) != str(tooling_set.global_id),
            )
        ):
            return None
        return self._intake_value(row)

    def _evidence_for_set(
        self,
        project: object,
        tooling_set: ToolingSet,
    ) -> tuple[ToolingIntakeEvidenceReference, ...]:
        rows = self._bounded_documents(
            "NPI Tooling Intake Evidence Reference",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "tooling_master_global_id": str(tooling_set.tooling_master_global_id),
                "tooling_set_global_id": str(tooling_set.global_id),
            },
            maximum=_MAX_EVIDENCE,
        )
        return tuple(
            sorted(
                (self._evidence_value(value) for value in rows),
                key=lambda item: str(item.global_id),
            )
        )

    def _requirement_for_set(
        self,
        project: object,
        requirement_id: UUID,
    ) -> ToolingRequirement | None:
        row = _optional_doc("NPI Tooling Requirement", str(requirement_id))
        if row is None or any(
            (
                str(row.global_id) != str(requirement_id),
                str(row.tenant_id) != str(project.tenant_id),
                str(row.project_global_id) != str(project.global_id),
                str(row.requirement_kind)
                not in {
                    ToolingRequirementKind.CUSTOMER_OWNED_INTAKE.value,
                    ToolingRequirementKind.COPY_OR_ADDITIONAL_SET.value,
                },
            )
        ):
            return None
        return self._requirement_value(row)

    @staticmethod
    def _require_customer_reference(
        project: object,
        value: Mapping[str, str] | None,
    ) -> None:
        if value is None:
            return
        expected = (value["sourceSystem"], value["sourceObjectId"])
        matches = [
            row
            for row in project.references
            if str(row.reference_type) == "customer"
            and (str(row.source_system), str(row.source_object_id)) == expected
        ]
        if len(matches) != 1:
            raise ToolingReferenceUnavailable()

    @staticmethod
    def _file_revision_for_project(project: object, revision_id: UUID):
        row = _optional_doc("NPI File Revision", str(revision_id))
        if row is None or any(
            (
                str(row.global_id) != str(revision_id),
                str(row.tenant_id) != str(project.tenant_id),
                str(row.project_global_id) != str(project.global_id),
                str(row.scan_state) != "clean",
                not has_live_private_file_identity(row),
            )
        ):
            return None
        return row

    def _master_for_project(self, project: object, master_id: UUID):
        master = self._same_tenant_master(project, master_id)
        if master is None:
            return None
        if str(master.originating_project_global_id) == str(project.global_id):
            return master
        rows = self._bounded_documents(
            "NPI Tooling Applicability",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "tooling_master_global_id": str(master_id),
            },
            maximum=_MAX_APPLICABILITY,
        )
        return master if rows else None

    @staticmethod
    def _same_tenant_master(project: object, master_id: UUID):
        master = _optional_doc("NPI Tooling Master", str(master_id))
        return (
            master
            if master is not None
            and str(master.global_id) == str(master_id)
            and str(master.tenant_id) == str(project.tenant_id)
            else None
        )

    @staticmethod
    def _locked_part_for_project(project: object, part_id: UUID):
        try:
            part = frappe.get_doc("NPI Engineering Part", str(part_id), for_update=True)
        except frappe.DoesNotExistError:
            return None
        return (
            part
            if str(part.global_id) == str(part_id)
            and str(part.tenant_id) == str(project.tenant_id)
            and str(part.originating_project_global_id) == str(project.global_id)
            else None
        )

    def _part_revision_for_project(
        self,
        project: object,
        revision_id: UUID,
        *,
        require_current: bool,
    ) -> EngineeringPartRevision | None:
        row = _optional_doc("NPI Engineering Part Revision", str(revision_id))
        if row is None or any(
            (
                str(row.global_id) != str(revision_id),
                str(row.tenant_id) != str(project.tenant_id),
                str(row.originating_project_global_id) != str(project.global_id),
            )
        ):
            return None
        part = _optional_doc("NPI Engineering Part", str(row.part_global_id))
        if part is None or any(
            (
                str(part.global_id) != str(row.part_global_id),
                str(part.tenant_id) != str(project.tenant_id),
                str(part.originating_project_global_id) != str(project.global_id),
                require_current
                and str(part.current_revision_global_id) != str(revision_id),
            )
        ):
            return None
        revision = self._revision_value(row)
        if require_current and any(
            (
                int(part.current_revision_number) != revision.revision_number,
                str(part.current_revision_snapshot_hash) != revision.snapshot_hash,
            )
        ):
            return None
        return revision

    @staticmethod
    def _require_project_reference(
        project: object,
        value: Mapping[str, str] | None,
    ) -> None:
        if value is None:
            return
        expected = (value["sourceSystem"], value["sourceObjectId"])
        matches = [
            row
            for row in project.references
            if (str(row.source_system), str(row.source_object_id)) == expected
        ]
        if len(matches) != 1:
            raise ToolingReferenceUnavailable()

    def _command_context(
        self,
        project: object,
        *,
        operation: str,
        idempotency_key_hash: str,
        payload: Mapping[str, object],
    ) -> tuple[str, str] | dict[str, Any]:
        payload_hash = sha256_json(
            {
                "actorUserId": self.actor.casefold(),
                "operation": operation,
                "projectGlobalId": str(project.global_id),
                "tenantId": str(project.tenant_id),
                "payload": dict(payload),
            }
        )
        receipt_key = sha256_json(
            {
                "tenantId": str(project.tenant_id),
                "projectGlobalId": str(project.global_id),
                "actorUserId": self.actor.casefold(),
                "operation": operation,
                "idempotencyKeyHash": idempotency_key_hash,
            }
        )
        replay = self._receipt_replay(
            project,
            receipt_key=receipt_key,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
        )
        return replay if replay is not None else (receipt_key, payload_hash)

    def _receipt_replay(
        self,
        project: object,
        *,
        receipt_key: str,
        operation: str,
        idempotency_key_hash: str,
        payload_hash: str,
    ) -> dict[str, Any] | None:
        row = frappe.db.get_value(
            "NPI Tooling Command Idempotency",
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
        if not row:
            return None
        expected = {
            "tenant_id": str(project.tenant_id),
            "project_global_id": str(project.global_id),
            "actor_user_id": self.actor,
            "operation": operation,
            "idempotency_key_hash": idempotency_key_hash,
            "payload_hash": payload_hash,
        }
        if any(str(_value(row, key)) != value for key, value in expected.items()):
            raise ToolingIdempotencyConflict()
        if int(_value(row, "sealed") or 0) != 1:
            raise RuntimeError("The Tooling idempotency receipt is unsealed.")
        response = _json_object(_value(row, "response_payload"))
        if (
            not _value(row, "target_object_type")
            or not _value(row, "target_global_id")
            or str(_value(row, "response_hash")) != sha256_json(response)
        ):
            raise RuntimeError("The Tooling idempotency receipt integrity drifted.")
        return response

    def _insert_receipt(
        self,
        project: object,
        *,
        receipt_key: str,
        operation: str,
        idempotency_key_hash: str,
        payload_hash: str,
        now: datetime,
    ) -> object:
        try:
            return frappe.get_doc(
                {
                    "doctype": "NPI Tooling Command Idempotency",
                    "global_id": str(self._new_uuid()),
                    "receipt_key": receipt_key,
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "actor_user_id": self.actor,
                    "operation": operation,
                    "idempotency_key_hash": idempotency_key_hash,
                    "payload_hash": payload_hash,
                    "target_object_type": None,
                    "target_global_id": None,
                    "response_payload": _canonical_json({}),
                    "response_hash": None,
                    "sealed": 0,
                    "created_at": _database_datetime(now),
                    "updated_at": _database_datetime(now),
                }
            ).insert()
        except (frappe.DuplicateEntryError, frappe.UniqueValidationError) as error:
            raise ToolingIdempotencyConflict() from error

    @staticmethod
    def _seal_receipt(
        receipt: object,
        *,
        target_type: str,
        target_id: UUID,
        response: Mapping[str, object],
        now: datetime,
    ) -> None:
        receipt.target_object_type = target_type
        receipt.target_global_id = str(target_id)
        receipt.response_payload = _canonical_json(response)
        receipt.response_hash = sha256_json(response)
        receipt.sealed = 1
        receipt.updated_at = _database_datetime(now)
        receipt.save()

    @staticmethod
    def _insert_part_revision(value: EngineeringPartRevision) -> object:
        return frappe.get_doc(
            {
                "doctype": "NPI Engineering Part Revision",
                "global_id": str(value.global_id),
                "engineering_part": str(value.part_global_id),
                "part_global_id": str(value.part_global_id),
                "tenant_id": value.tenant_id,
                "originating_project_global_id": str(
                    value.originating_project_global_id
                ),
                "revision_number": value.revision_number,
                "revision_key": None,
                "revision_label": value.revision_label,
                "predecessor_global_id": (
                    str(value.predecessor_global_id)
                    if value.predecessor_global_id is not None
                    else None
                ),
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "title": value.title,
                "reason": value.reason,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "revision_snapshot": _canonical_json(value.snapshot_payload()),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    @staticmethod
    def _insert_requirement(value: ToolingRequirement) -> object:
        return frappe.get_doc(
            {
                "doctype": "NPI Tooling Requirement",
                "global_id": str(value.global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "requirement_kind": value.kind.value,
                "title": value.title,
                "reason": value.reason,
                "target_part_revision_global_id": (
                    str(value.target_part_revision_global_id)
                    if value.target_part_revision_global_id is not None
                    else None
                ),
                "target_date": (
                    value.target_date.isoformat() if value.target_date else None
                ),
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "requirement_snapshot": _canonical_json(value.snapshot_payload()),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    @staticmethod
    def _insert_master(value: ToolingMaster) -> object:
        return frappe.get_doc(
            {
                "doctype": "NPI Tooling Master",
                "global_id": str(value.global_id),
                "tenant_id": value.tenant_id,
                "originating_project_global_id": str(
                    value.originating_project_global_id
                ),
                "title": value.title,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "master_snapshot": _canonical_json(value.snapshot_payload()),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    @staticmethod
    def _insert_applicability(value: ToolingApplicability) -> object:
        return frappe.get_doc(
            {
                "doctype": "NPI Tooling Applicability",
                "global_id": str(value.global_id),
                "relationship_global_id": str(value.relationship_global_id),
                "relationship_key_hash": value.relationship_key_hash,
                "version_key": _applicability_version_key(
                    value.tenant_id,
                    value.relationship_global_id,
                    value.applicability_version,
                ),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "tooling_master_global_id": str(value.tooling_master_global_id),
                "part_global_id": str(value.part_global_id),
                "part_revision_global_id": str(value.part_revision_global_id),
                "product_source_system": value.product_source_system,
                "product_source_object_id": value.product_source_object_id,
                "model_source_system": value.model_source_system,
                "model_source_object_id": value.model_source_object_id,
                "applicability_version": value.applicability_version,
                "predecessor_global_id": (
                    str(value.predecessor_global_id)
                    if value.predecessor_global_id is not None
                    else None
                ),
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "effective_from": value.effective_from.isoformat(),
                "effective_to": (
                    value.effective_to.isoformat() if value.effective_to else None
                ),
                "reason": value.reason,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "applicability_snapshot": _canonical_json(value.snapshot_payload()),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    @staticmethod
    def _insert_tooling_set(value: ToolingSet) -> object:
        return frappe.get_doc(
            {
                "doctype": "NPI Tooling Set",
                "global_id": str(value.global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "tooling_master": str(value.tooling_master_global_id),
                "tooling_master_global_id": str(value.tooling_master_global_id),
                "tooling_requirement": str(value.tooling_requirement_global_id),
                "tooling_requirement_global_id": str(
                    value.tooling_requirement_global_id
                ),
                "requirement_kind": value.requirement_kind.value,
                "physical_serial": value.physical_serial,
                "customer_source_system": value.customer_source_system,
                "customer_source_object_id": value.customer_source_object_id,
                "custody_responsibility": value.custody_responsibility,
                "repair_authorization_reference": (
                    value.repair_authorization_reference
                ),
                "return_conditions": value.return_conditions,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "set_snapshot": _canonical_json(value.snapshot_payload()),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    @staticmethod
    def _insert_tooling_intake(value: ToolingIntake) -> object:
        return frappe.get_doc(
            {
                "doctype": "NPI Tooling Intake",
                "global_id": str(value.global_id),
                "intake_key": None,
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "tooling_master_global_id": str(value.tooling_master_global_id),
                "tooling_set": str(value.tooling_set_global_id),
                "tooling_set_global_id": str(value.tooling_set_global_id),
                "intake_version": value.intake_version,
                "predecessor_global_id": (
                    str(value.predecessor_global_id)
                    if value.predecessor_global_id is not None
                    else None
                ),
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "transport_provider": value.transport_provider,
                "transport_reference": value.transport_reference,
                "arrived_at": _database_datetime(value.arrived_at),
                "custody_handover": value.custody_handover,
                "accessory_snapshot": _canonical_json(
                    [item.snapshot_payload() for item in value.accessories]
                ),
                "inspection_snapshot": _canonical_json(
                    [item.snapshot_payload() for item in value.inspections]
                ),
                "difference_snapshot": _canonical_json(
                    [item.snapshot_payload() for item in value.differences]
                ),
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "intake_snapshot": _canonical_json(value.snapshot_payload()),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    @staticmethod
    def _insert_tooling_intake_evidence(
        value: ToolingIntakeEvidenceReference,
    ) -> object:
        return frappe.get_doc(
            {
                "doctype": "NPI Tooling Intake Evidence Reference",
                "global_id": str(value.global_id),
                "evidence_key_hash": value.evidence_key_hash,
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "tooling_master_global_id": str(value.tooling_master_global_id),
                "tooling_set_global_id": str(value.tooling_set_global_id),
                "tooling_intake": str(value.tooling_intake_global_id),
                "tooling_intake_global_id": str(value.tooling_intake_global_id),
                "intake_snapshot_hash": value.intake_snapshot_hash,
                "evidence_role": value.evidence_role.value,
                "difference_global_ids": _canonical_json(
                    [str(item) for item in value.difference_global_ids]
                ),
                "file_revision": str(value.file_revision_global_id),
                "file_revision_global_id": str(value.file_revision_global_id),
                "file_optimistic_version": value.file_optimistic_version,
                "frappe_content_hash": value.frappe_content_hash,
                "file_name": value.file_name,
                "mime_type": value.mime_type,
                "size_bytes": value.size_bytes,
                "sha256": value.sha256,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "evidence_snapshot": _canonical_json(value.snapshot_payload()),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    def _append_audit(
        self,
        *,
        operation: str,
        global_id: UUID,
        object_version: int,
        summary: Mapping[str, object],
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

    @staticmethod
    def _part_value(row: object, revision: EngineeringPartRevision) -> EngineeringPart:
        return EngineeringPart(
            global_id=UUID(str(row.global_id)),
            tenant_id=str(row.tenant_id),
            originating_project_global_id=UUID(
                str(row.originating_project_global_id)
            ),
            title=str(row.title),
            current_revision_global_id=UUID(str(row.current_revision_global_id)),
            current_revision_number=int(row.current_revision_number),
            current_revision_snapshot_hash=str(
                row.current_revision_snapshot_hash
            ),
            optimistic_version=int(row.optimistic_version),
        )

    @staticmethod
    def _revision_value(row: object) -> EngineeringPartRevision:
        value = EngineeringPartRevision(
            global_id=UUID(str(row.global_id)),
            part_global_id=UUID(str(row.part_global_id)),
            tenant_id=str(row.tenant_id),
            originating_project_global_id=UUID(
                str(row.originating_project_global_id)
            ),
            revision_number=int(row.revision_number),
            revision_label=str(row.revision_label),
            title=str(row.title),
            reason=str(row.reason),
            predecessor_global_id=(
                UUID(str(row.predecessor_global_id))
                if row.predecessor_global_id
                else None
            ),
            predecessor_snapshot_hash=(
                str(row.predecessor_snapshot_hash)
                if row.predecessor_snapshot_hash
                else None
            ),
            created_by_user_id=str(row.created_by_user_id),
            created_at=_datetime(row.created_at),
            request_id=UUID(str(row.request_id)),
            trace_id=str(row.trace_id),
            snapshot_hash=str(row.snapshot_hash),
        )
        if _json_object(row.revision_snapshot) != value.snapshot_payload():
            raise RuntimeError("The Part Revision snapshot integrity drifted.")
        return value

    @staticmethod
    def _requirement_value(row: object) -> ToolingRequirement:
        value = ToolingRequirement(
            global_id=UUID(str(row.global_id)),
            tenant_id=str(row.tenant_id),
            project_global_id=UUID(str(row.project_global_id)),
            kind=ToolingRequirementKind(str(row.requirement_kind)),
            title=str(row.title),
            reason=str(row.reason),
            target_part_revision_global_id=(
                UUID(str(row.target_part_revision_global_id))
                if row.target_part_revision_global_id
                else None
            ),
            target_date=_optional_date(row.target_date),
            created_by_user_id=str(row.created_by_user_id),
            created_at=_datetime(row.created_at),
            request_id=UUID(str(row.request_id)),
            trace_id=str(row.trace_id),
            snapshot_hash=str(row.snapshot_hash),
        )
        if _json_object(row.requirement_snapshot) != value.snapshot_payload():
            raise RuntimeError("The Tooling Requirement snapshot integrity drifted.")
        return value

    @staticmethod
    def _master_value(row: object) -> ToolingMaster:
        value = ToolingMaster(
            global_id=UUID(str(row.global_id)),
            tenant_id=str(row.tenant_id),
            originating_project_global_id=UUID(
                str(row.originating_project_global_id)
            ),
            title=str(row.title),
            created_by_user_id=str(row.created_by_user_id),
            created_at=_datetime(row.created_at),
            request_id=UUID(str(row.request_id)),
            trace_id=str(row.trace_id),
            snapshot_hash=str(row.snapshot_hash),
        )
        if _json_object(row.master_snapshot) != value.snapshot_payload():
            raise RuntimeError("The Tooling Master snapshot integrity drifted.")
        return value

    @staticmethod
    def _applicability_value(row: object) -> ToolingApplicability:
        value = ToolingApplicability(
            global_id=UUID(str(row.global_id)),
            relationship_global_id=UUID(str(row.relationship_global_id)),
            tenant_id=str(row.tenant_id),
            project_global_id=UUID(str(row.project_global_id)),
            tooling_master_global_id=UUID(str(row.tooling_master_global_id)),
            part_global_id=UUID(str(row.part_global_id)),
            part_revision_global_id=UUID(str(row.part_revision_global_id)),
            product_source_system=(
                str(row.product_source_system) if row.product_source_system else None
            ),
            product_source_object_id=(
                str(row.product_source_object_id)
                if row.product_source_object_id
                else None
            ),
            model_source_system=(
                str(row.model_source_system) if row.model_source_system else None
            ),
            model_source_object_id=(
                str(row.model_source_object_id)
                if row.model_source_object_id
                else None
            ),
            applicability_version=int(row.applicability_version),
            predecessor_global_id=(
                UUID(str(row.predecessor_global_id))
                if row.predecessor_global_id
                else None
            ),
            predecessor_snapshot_hash=(
                str(row.predecessor_snapshot_hash)
                if row.predecessor_snapshot_hash
                else None
            ),
            effective_from=_date(row.effective_from),
            effective_to=_optional_date(row.effective_to),
            reason=str(row.reason),
            created_by_user_id=str(row.created_by_user_id),
            created_at=_datetime(row.created_at),
            request_id=UUID(str(row.request_id)),
            trace_id=str(row.trace_id),
            relationship_key_hash=str(row.relationship_key_hash),
            snapshot_hash=str(row.snapshot_hash),
        )
        if _json_object(row.applicability_snapshot) != value.snapshot_payload():
            raise RuntimeError("The Tooling Applicability snapshot integrity drifted.")
        return value

    @staticmethod
    def _tooling_set_value(row: object) -> ToolingSet:
        value = ToolingSet(
            global_id=UUID(str(row.global_id)),
            tenant_id=str(row.tenant_id),
            project_global_id=UUID(str(row.project_global_id)),
            tooling_master_global_id=UUID(str(row.tooling_master_global_id)),
            tooling_requirement_global_id=UUID(
                str(row.tooling_requirement_global_id)
            ),
            requirement_kind=ToolingRequirementKind(str(row.requirement_kind)),
            physical_serial=str(row.physical_serial),
            customer_source_system=(
                str(row.customer_source_system)
                if row.customer_source_system
                else None
            ),
            customer_source_object_id=(
                str(row.customer_source_object_id)
                if row.customer_source_object_id
                else None
            ),
            custody_responsibility=str(row.custody_responsibility),
            repair_authorization_reference=str(
                row.repair_authorization_reference
            ),
            return_conditions=str(row.return_conditions),
            created_by_user_id=str(row.created_by_user_id),
            created_at=_datetime(row.created_at),
            request_id=UUID(str(row.request_id)),
            trace_id=str(row.trace_id),
            snapshot_hash=str(row.snapshot_hash),
        )
        if _json_object(row.set_snapshot) != value.snapshot_payload():
            raise RuntimeError("The Tooling Set snapshot integrity drifted.")
        return value

    @staticmethod
    def _intake_value(row: object) -> ToolingIntake:
        accessories = tuple(
            ToolingAccessoryLine(
                global_id=UUID(str(item["globalId"])),
                description=str(item["description"]),
                declared_quantity=int(item["declaredQuantity"]),
                received_quantity=int(item["receivedQuantity"]),
                unit=str(item["unit"]),
            )
            for item in _json_array(row.accessory_snapshot)
        )
        inspections = tuple(
            ToolingInspectionObservation(
                global_id=UUID(str(item["globalId"])),
                category=ToolingInspectionCategory(str(item["category"])),
                observation=str(item["observation"]),
                difference_observed=item["differenceObserved"],
            )
            for item in _json_array(row.inspection_snapshot)
        )
        differences = tuple(
            ToolingIntakeDifference(
                global_id=UUID(str(item["globalId"])),
                source_kind=ToolingDifferenceSourceKind(str(item["sourceKind"])),
                source_global_id=UUID(str(item["sourceGlobalId"])),
                description=str(item["description"]),
                customer_confirmation_required=item[
                    "customerConfirmationRequired"
                ],
            )
            for item in _json_array(row.difference_snapshot)
        )
        value = ToolingIntake(
            global_id=UUID(str(row.global_id)),
            tenant_id=str(row.tenant_id),
            project_global_id=UUID(str(row.project_global_id)),
            tooling_master_global_id=UUID(str(row.tooling_master_global_id)),
            tooling_set_global_id=UUID(str(row.tooling_set_global_id)),
            intake_version=int(row.intake_version),
            predecessor_global_id=(
                UUID(str(row.predecessor_global_id))
                if row.predecessor_global_id
                else None
            ),
            predecessor_snapshot_hash=(
                str(row.predecessor_snapshot_hash)
                if row.predecessor_snapshot_hash
                else None
            ),
            transport_provider=str(row.transport_provider),
            transport_reference=str(row.transport_reference),
            arrived_at=_datetime(row.arrived_at),
            custody_handover=str(row.custody_handover),
            accessories=accessories,
            inspections=inspections,
            differences=differences,
            created_by_user_id=str(row.created_by_user_id),
            created_at=_datetime(row.created_at),
            request_id=UUID(str(row.request_id)),
            trace_id=str(row.trace_id),
            snapshot_hash=str(row.snapshot_hash),
        )
        if _json_object(row.intake_snapshot) != value.snapshot_payload():
            raise RuntimeError("The Tooling Intake snapshot integrity drifted.")
        return value

    @staticmethod
    def _evidence_value(row: object) -> ToolingIntakeEvidenceReference:
        value = ToolingIntakeEvidenceReference(
            global_id=UUID(str(row.global_id)),
            tenant_id=str(row.tenant_id),
            project_global_id=UUID(str(row.project_global_id)),
            tooling_master_global_id=UUID(str(row.tooling_master_global_id)),
            tooling_set_global_id=UUID(str(row.tooling_set_global_id)),
            tooling_intake_global_id=UUID(str(row.tooling_intake_global_id)),
            intake_snapshot_hash=str(row.intake_snapshot_hash),
            evidence_role=ToolingIntakeEvidenceRole(str(row.evidence_role)),
            difference_global_ids=tuple(
                UUID(str(item))
                for item in _json_array(row.difference_global_ids)
            ),
            file_revision_global_id=UUID(str(row.file_revision_global_id)),
            file_optimistic_version=int(row.file_optimistic_version),
            frappe_content_hash=str(row.frappe_content_hash),
            file_name=str(row.file_name),
            mime_type=str(row.mime_type),
            size_bytes=int(row.size_bytes),
            sha256=str(row.sha256),
            created_by_user_id=str(row.created_by_user_id),
            created_at=_datetime(row.created_at),
            request_id=UUID(str(row.request_id)),
            trace_id=str(row.trace_id),
            evidence_key_hash=str(row.evidence_key_hash),
            snapshot_hash=str(row.snapshot_hash),
        )
        if _json_object(row.evidence_snapshot) != value.snapshot_payload():
            raise RuntimeError("The Tooling Intake evidence integrity drifted.")
        return value

    def _bounded_documents(
        self,
        doctype: str,
        *,
        filters: Mapping[str, object],
        maximum: int,
    ) -> tuple[object, ...]:
        names = frappe.get_all(
            doctype,
            filters=dict(filters),
            pluck="name",
            order_by="global_id asc",
            limit_page_length=maximum + 1,
        )
        if len(names) > maximum:
            raise RuntimeError(f"The {doctype} collection exceeds its safe bound.")
        return tuple(frappe.get_doc(doctype, str(name)) for name in names)

    def _tooling_permissions(self) -> dict[str, bool]:
        create = self._is_internal_system_manager()
        return {
            "view": True,
            "createPart": create,
            "createRequirement": create,
            "createMaster": create,
            "createApplicability": create,
            "transitionLifecycle": False,
        }

    def _tooling_set_permissions(self) -> dict[str, bool]:
        create = self._is_internal_system_manager()
        return {
            "view": True,
            "createSet": create,
            "createIntake": create,
            "attachEvidence": create,
            "transitionLifecycle": False,
        }

    @staticmethod
    def _part_response(
        value: EngineeringPart,
        revision: EngineeringPartRevision,
    ) -> dict[str, object]:
        return {
            "globalId": str(value.global_id),
            "title": value.title,
            "version": value.optimistic_version,
            "currentRevision": FrappeToolingRepository._revision_response(revision),
            "source": _npi_source(),
        }

    @staticmethod
    def _revision_response(value: EngineeringPartRevision) -> dict[str, object]:
        return {
            "globalId": str(value.global_id),
            "partGlobalId": str(value.part_global_id),
            "revisionNumber": value.revision_number,
            "revisionLabel": value.revision_label,
            "snapshotHash": value.snapshot_hash,
        }

    @staticmethod
    def _requirement_response(value: ToolingRequirement) -> dict[str, object]:
        return {
            "globalId": str(value.global_id),
            "projectGlobalId": str(value.project_global_id),
            "kind": value.kind.value,
            "title": value.title,
            "reason": value.reason,
            "targetPartRevisionGlobalId": (
                str(value.target_part_revision_global_id)
                if value.target_part_revision_global_id is not None
                else None
            ),
            "targetDate": value.target_date.isoformat() if value.target_date else None,
            "snapshotHash": value.snapshot_hash,
        }

    @staticmethod
    def _master_response(value: ToolingMaster) -> dict[str, object]:
        return {
            "globalId": str(value.global_id),
            "title": value.title,
            "originatingProjectGlobalId": str(value.originating_project_global_id),
            "snapshotHash": value.snapshot_hash,
            "source": _npi_source(),
        }

    @staticmethod
    def _applicability_response(
        value: ToolingApplicability,
        revision: EngineeringPartRevision,
    ) -> dict[str, object]:
        return {
            "globalId": str(value.global_id),
            "relationshipGlobalId": str(value.relationship_global_id),
            "relationshipKeyHash": value.relationship_key_hash,
            "projectGlobalId": str(value.project_global_id),
            "toolingMasterGlobalId": str(value.tooling_master_global_id),
            "part": FrappeToolingRepository._revision_response(revision),
            "product": _external_reference(
                value.product_source_system,
                value.product_source_object_id,
            ),
            "model": _external_reference(
                value.model_source_system,
                value.model_source_object_id,
            ),
            "version": value.applicability_version,
            "predecessorGlobalId": (
                str(value.predecessor_global_id)
                if value.predecessor_global_id is not None
                else None
            ),
            "effectiveFrom": value.effective_from.isoformat(),
            "effectiveTo": (
                value.effective_to.isoformat() if value.effective_to else None
            ),
            "snapshotHash": value.snapshot_hash,
        }

    def _tooling_set_response(self, value: ToolingSet) -> dict[str, object]:
        return {
            "globalId": str(value.global_id),
            "projectGlobalId": str(value.project_global_id),
            "toolingMasterGlobalId": str(value.tooling_master_global_id),
            "toolingRequirementGlobalId": str(
                value.tooling_requirement_global_id
            ),
            "requirementKind": value.requirement_kind.value,
            "physicalSerial": value.physical_serial,
            "customer": _external_reference(
                value.customer_source_system,
                value.customer_source_object_id,
            ),
            "custodyResponsibility": value.custody_responsibility,
            "repairAuthorizationReference": (
                value.repair_authorization_reference
            ),
            "returnConditions": value.return_conditions,
            "sourceRevision": self._tooling_set_source_revision_response(value),
            "supplier": FrappeToolingRepository._unavailable(
                "formal_supplier_unavailable"
            ),
            "lifecycle": FrappeToolingRepository._unavailable(
                "lifecycle_policy_unavailable"
            ),
            "erpLocationAndAsset": FrappeToolingRepository._unavailable(
                "erp_projection_unavailable"
            ),
            "snapshotHash": value.snapshot_hash,
        }

    @staticmethod
    def _intake_response(value: ToolingIntake) -> dict[str, object]:
        return {
            "globalId": str(value.global_id),
            "toolingSetGlobalId": str(value.tooling_set_global_id),
            "version": value.intake_version,
            "predecessorGlobalId": (
                str(value.predecessor_global_id)
                if value.predecessor_global_id is not None
                else None
            ),
            "transportProvider": value.transport_provider,
            "transportReference": value.transport_reference,
            "arrivedAt": _utc_datetime_text(value.arrived_at),
            "custodyHandover": value.custody_handover,
            "accessories": [
                item.snapshot_payload() for item in value.accessories
            ],
            "inspections": [
                item.snapshot_payload() for item in value.inspections
            ],
            "differences": [
                item.snapshot_payload() for item in value.differences
            ],
            "snapshotHash": value.snapshot_hash,
        }

    @staticmethod
    def _evidence_response(
        value: ToolingIntakeEvidenceReference,
    ) -> dict[str, object]:
        return {
            "globalId": str(value.global_id),
            "toolingIntakeGlobalId": str(value.tooling_intake_global_id),
            "intakeSnapshotHash": value.intake_snapshot_hash,
            "evidenceRole": value.evidence_role.value,
            "differenceGlobalIds": [
                str(item) for item in value.difference_global_ids
            ],
            "fileRevisionGlobalId": str(value.file_revision_global_id),
            "fileOptimisticVersion": value.file_optimistic_version,
            "fileContentHash": value.frappe_content_hash,
            "fileName": value.file_name,
            "mimeType": value.mime_type,
            "sizeBytes": value.size_bytes,
            "sha256": value.sha256,
            "snapshotHash": value.snapshot_hash,
        }

    @staticmethod
    def _unavailable(reason_code: str) -> dict[str, str]:
        return {"state": "unavailable", "reasonCode": reason_code}

    def _now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise RuntimeError("The Tooling clock must be timezone-aware.")
        return value.astimezone(UTC)

    def _new_uuid(self) -> UUID:
        value = self._uuid_factory()
        parsed = value if isinstance(value, UUID) else UUID(str(value))
        if parsed.version != 4:
            raise RuntimeError("The Tooling identifier must be a UUIDv4 value.")
        return parsed


def _optional_doc(doctype: str, name: str):
    try:
        return frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        return None


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _json_object(value: object) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError) as error:
            raise RuntimeError("Persisted Tooling JSON is invalid.") from error
    if not isinstance(value, dict):
        raise RuntimeError("Persisted Tooling JSON is not an object.")
    return dict(value)


def _json_array(value: object) -> list[Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError) as error:
            raise RuntimeError("Persisted Tooling JSON is invalid.") from error
    if not isinstance(value, list):
        raise RuntimeError("Persisted Tooling JSON is not an array.")
    return list(value)


def _value(record: object, fieldname: str) -> object:
    return record.get(fieldname) if isinstance(record, dict) else getattr(record, fieldname, None)


def _datetime(value: object) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _utc_datetime_text(value: datetime) -> str:
    return _datetime(value).isoformat(timespec="microseconds").replace(
        "+00:00",
        "Z",
    )


def _applicability_version_key(
    tenant_id: str,
    relationship_global_id: UUID,
    applicability_version: int,
) -> str:
    return hashlib.sha256(
        f"{tenant_id}:{relationship_global_id}:{applicability_version}".encode()
    ).hexdigest()


def _database_datetime(value: datetime) -> str:
    return _datetime(value).replace(tzinfo=None).isoformat(sep=" ", timespec="microseconds")


def _date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def _optional_date(value: object) -> date | None:
    return None if value in (None, "") else _date(value)


def _npi_source() -> dict[str, str]:
    return {
        "sourceSystem": "NPI_ONE",
        "editableIn": "NPI_ONE",
        "syncState": "local",
    }


def _external_reference(
    source_system: str | None,
    source_object_id: str | None,
) -> dict[str, str] | None:
    if source_system is None or source_object_id is None:
        return None
    return {"sourceSystem": source_system, "sourceObjectId": source_object_id}
