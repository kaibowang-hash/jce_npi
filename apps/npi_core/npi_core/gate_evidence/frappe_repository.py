from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

import frappe
from frappe import _

from npi_core.controlled_evidence_validation import (
    GATE_EVIDENCE_COMMAND_FLAG,
    canonical_snapshot_hash,
    evidence_reference_key,
)
from npi_core.foundation.audit import create_audit_event
from npi_core.foundation.errors import (
    PermissionDenied,
    RequestValidationFailed,
    VersionConflict,
)
from npi_core.foundation.security import Principal, ProjectAccess, authorize_project
from npi_core.gate_evidence.domain import (
    EvidenceAlreadyAttached,
    EvidenceSourceUnavailable,
    EvidenceVersionConflict,
    GateRequirementsAlreadyFrozen,
    GateRequirementsNotFrozen,
    GateTemplateUnavailable,
    build_frozen_requirement_snapshot,
)
from npi_core.gate_template.frappe_repository import (
    load_exact_gate_template_snapshot,
)
from npi_core.npi_core.doctype.npi_file_revision.npi_file_revision import (
    file_revision_source_snapshot,
    has_complete_file_revision_identity,
    has_live_private_file_identity,
)
from npi_core.npi_core.doctype.npi_gate_evidence_reference.npi_gate_evidence_reference import (
    wbs_item_source_snapshot,
)
from npi_core.project.domain import IdempotencyConflict, ProjectType
from npi_core.project_controls.terminal_guard import require_mutable_project

_SUPPORTED_EVIDENCE_KINDS = frozenset({"wbs_item", "file_revision"})


@dataclass(frozen=True, slots=True)
class GateCommandOutcome:
    response: dict[str, Any]
    replayed: bool = False


class FrappeGateEvidenceRepository:
    """Frappe adapter for the bounded P4-03 Gate evidence aggregate."""

    def __init__(
        self,
        *,
        principal: Principal,
        request_id: str,
        trace_id: str,
    ) -> None:
        self.principal = principal
        self.actor = principal.user_id
        self.request_id = request_id
        self.trace_id = trace_id

    def evidence_workspace(
        self,
        project_id: UUID,
        gate_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id, ProjectAccess.VIEW)
        if project is None:
            return None
        gate = self._gate_for_project(project, gate_id)
        if gate is None:
            return None
        return self._workspace_for(project, gate)

    def freeze_requirements(
        self,
        project_id: UUID,
        gate_id: UUID,
        *,
        idempotency_key: str,
        expected_gate_version: int,
        gate_due_date: date,
        assignments: Sequence[Mapping[str, object]],
    ) -> GateCommandOutcome | None:
        project = self._locked_authorized_project(
            project_id,
            ProjectAccess.ADMINISTER,
        )
        if project is None:
            return None
        gate = self._locked_gate_for_project(project, gate_id)
        if gate is None:
            return None
        payload_hash = _payload_hash(
            {
                "projectId": project_id,
                "gateId": gate_id,
                "expectedGateVersion": expected_gate_version,
                "gateDueDate": gate_due_date,
                "requirements": assignments,
            }
        )
        replay = self._idempotency_replay(idempotency_key, payload_hash)
        if replay is not None:
            return GateCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        self._require_gate_version(gate, expected_gate_version)
        if int(gate.requirements_frozen or 0) == 1:
            raise GateRequirementsAlreadyFrozen()

        template = self._load_gate_template(project, gate)
        self._require_supported_template(template)
        snapshot, snapshot_hash = build_frozen_requirement_snapshot(
            gate_global_id=gate_id,
            gate_template_snapshot=template,
            gate_due_date=gate_due_date,
            assignments=assignments,
        )
        self._validate_assignment_members(
            project,
            snapshot["requirements"],
        )
        frozen_at = datetime.now(UTC)

        with _controlled_gate_write_scope():
            idempotency = self._insert_idempotency(
                idempotency_key,
                payload_hash,
                project,
                "gate.requirements.freeze",
            )
            if type(idempotency) is dict:
                return GateCommandOutcome(idempotency, replayed=True)
            gate.requirements_frozen = 1
            gate.gate_due_date = gate_due_date.isoformat()
            gate.requirement_snapshot = snapshot
            gate.requirement_snapshot_hash = snapshot_hash
            gate.requirements_frozen_at = _database_datetime(frozen_at)
            gate.requirements_frozen_by = self.actor
            gate.optimistic_version = int(gate.optimistic_version) + 1
            gate.save()
            self._append_audit(
                operation="gate.requirements.freeze",
                global_id=gate_id,
                object_version=int(gate.optimistic_version),
                result="updated",
                summary={
                    "gateDueDate": gate_due_date.isoformat(),
                    "projectId": str(project_id),
                    "requestId": self.request_id,
                    "requirementCount": len(snapshot["requirements"]),
                    "snapshotHash": snapshot_hash,
                },
            )
            response = self._workspace_for(project, gate)
            self._seal_idempotency(idempotency, response)
        return GateCommandOutcome(response)

    def attach_evidence(
        self,
        project_id: UUID,
        gate_id: UUID,
        requirement_key: str,
        *,
        idempotency_key: str,
        expected_gate_version: int,
        evidence_kind: str,
        source_global_id: UUID,
        source_version: int,
        source_hash: str,
    ) -> GateCommandOutcome | None:
        project = self._locked_authorized_project(
            project_id,
            ProjectAccess.ADMINISTER,
        )
        if project is None:
            return None
        gate = self._locked_gate_for_project(project, gate_id)
        if gate is None:
            return None
        payload_hash = _payload_hash(
            {
                "projectId": project_id,
                "gateId": gate_id,
                "requirementKey": requirement_key,
                "expectedGateVersion": expected_gate_version,
                "evidenceKind": evidence_kind,
                "sourceGlobalId": source_global_id,
                "sourceVersion": source_version,
                "sourceHash": source_hash,
            }
        )
        replay = self._idempotency_replay(idempotency_key, payload_hash)
        if replay is not None:
            return GateCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        self._require_gate_version(gate, expected_gate_version)
        snapshot = self._requirement_snapshot(gate)
        requirement = _requirement_by_key(snapshot, requirement_key)
        allowed = requirement.get("allowedEvidenceKinds")
        if not isinstance(allowed, list) or evidence_kind not in allowed:
            raise _field_problem(
                "evidenceKind",
                _("Select an evidence kind allowed by this requirement."),
            )
        if evidence_kind not in _SUPPORTED_EVIDENCE_KINDS:
            raise EvidenceSourceUnavailable()
        source_snapshot = self._resolve_exact_source(
            project,
            evidence_kind=evidence_kind,
            source_global_id=source_global_id,
            source_version=source_version,
            source_hash=source_hash,
        )
        requirement_global_id = UUID(str(requirement["globalId"]))
        reference_key = evidence_reference_key(
            tenant_id=str(project.tenant_id),
            project_global_id=str(project_id),
            gate_global_id=str(gate_id),
            requirement_global_id=str(requirement_global_id),
            requirement_key=str(requirement["key"]),
            evidence_kind=evidence_kind,
            source_object_type=evidence_kind,
            source_global_id=str(source_global_id),
            source_version=source_version,
            source_hash=source_hash,
        )
        if frappe.db.get_value(
            "NPI Gate Evidence Reference",
            {"reference_key": reference_key},
            "name",
        ):
            raise EvidenceAlreadyAttached()
        if (
            frappe.db.count(
                "NPI Gate Evidence Reference",
                filters={
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project_id),
                    "gate_global_id": str(gate_id),
                    "requirement_global_id": str(requirement_global_id),
                },
            )
            >= 100
        ):
            raise _field_problem(
                "requirementKey",
                _(
                    "This requirement already contains the maximum number of evidence references."
                ),
            )

        evidence_global_id = uuid4()
        with _controlled_gate_write_scope():
            idempotency = self._insert_idempotency(
                idempotency_key,
                payload_hash,
                project,
                "gate.evidence.attach",
            )
            if type(idempotency) is dict:
                return GateCommandOutcome(idempotency, replayed=True)
            frappe.get_doc(
                {
                    "doctype": "NPI Gate Evidence Reference",
                    "global_id": str(evidence_global_id),
                    "reference_key": reference_key,
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project_id),
                    "gate_global_id": str(gate_id),
                    "requirement_global_id": str(requirement_global_id),
                    "requirement_key": str(requirement["key"]),
                    "evidence_kind": evidence_kind,
                    "source_object_type": evidence_kind,
                    "source_global_id": str(source_global_id),
                    "source_version": source_version,
                    "source_hash": source_hash,
                    "source_snapshot": source_snapshot,
                    "created_by": self.actor,
                    "created_at": _database_datetime(datetime.now(UTC)),
                    "optimistic_version": 1,
                }
            ).insert()
            gate.optimistic_version = int(gate.optimistic_version) + 1
            gate.save()
            self._refresh_gate_review_locked(project, gate)
            self._append_audit(
                operation="gate.evidence.attach",
                global_id=evidence_global_id,
                object_version=1,
                result="created",
                summary={
                    "evidenceKind": evidence_kind,
                    "gateId": str(gate_id),
                    "projectId": str(project_id),
                    "requestId": self.request_id,
                    "requirementKey": str(requirement["key"]),
                    "sourceGlobalId": str(source_global_id),
                    "sourceHash": source_hash,
                    "sourceVersion": source_version,
                },
            )
            response = self._workspace_for(project, gate)
            self._seal_idempotency(idempotency, response)
        return GateCommandOutcome(response)

    def _refresh_gate_review_locked(self, project, gate) -> bool:
        """Evaluate review input only after the new reference is persisted."""
        from npi_core.gate_review.frappe_repository import (
            refresh_gate_review_dependency_locked,
        )

        return refresh_gate_review_dependency_locked(
            project,
            gate,
            request_id=self.request_id,
            trace_id=self.trace_id,
            reason="GATE_EVIDENCE_ATTACHED",
            initiated_by_user_id=self.actor,
        )

    def _workspace_for(self, project, gate) -> dict[str, Any]:
        snapshot = self._requirement_snapshot(gate)
        requirements = snapshot["requirements"]
        if not isinstance(requirements, list):
            raise ValueError("Persisted Gate requirement snapshot is invalid.")
        evidence_documents = _project_documents(
            "NPI Gate Evidence Reference",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "gate_global_id": str(gate.global_id),
            },
            order_by="created_at asc, global_id asc",
            maximum=50000,
        )
        requirement_keys = {
            str(requirement["key"]): requirement
            for requirement in requirements
            if isinstance(requirement, dict)
        }
        if len(requirement_keys) != len(requirements):
            raise ValueError("Persisted Gate requirement keys are invalid.")
        evidence_by_key: dict[str, list[dict[str, Any]]] = {
            key: [] for key in requirement_keys
        }
        unsafe_scan_count = 0
        for document in evidence_documents:
            key = str(document.requirement_key)
            requirement = requirement_keys.get(key)
            if requirement is None or (
                str(document.requirement_global_id) != str(requirement["globalId"])
            ):
                raise ValueError(
                    "Persisted Gate evidence requirement identity is invalid."
                )
            response = self._evidence_response(project, document)
            file_metadata = response.get("file")
            if isinstance(file_metadata, dict) and (
                file_metadata.get("scanState") != "clean"
            ):
                unsafe_scan_count += 1
            evidence_by_key[key].append(response)

        member_ids = {
            str(member_id)
            for requirement in requirements
            for member_id in (
                requirement["ownerMemberId"],
                *requirement["reviewerMemberIds"],
            )
        }
        members = {
            member_id: self._member_response(project, UUID(member_id))
            for member_id in member_ids
        }
        requirement_responses: list[dict[str, Any]] = []
        missing_required_count = 0
        required_count = 0
        for requirement in requirements:
            key = str(requirement["key"])
            evidence = evidence_by_key[key]
            if requirement["classification"] == "required":
                required_count += 1
                if not evidence:
                    missing_required_count += 1
            requirement_responses.append(
                {
                    "globalId": str(UUID(str(requirement["globalId"]))),
                    "key": key,
                    "title": str(requirement["title"]),
                    "classification": str(requirement["classification"]),
                    "priority": str(requirement["priority"]),
                    "owner": members[str(requirement["ownerMemberId"])],
                    "reviewers": [
                        members[str(member_id)]
                        for member_id in requirement["reviewerMemberIds"]
                    ],
                    "dueDate": str(requirement["dueDate"]),
                    "allowedEvidenceKinds": [
                        str(kind) for kind in requirement["allowedEvidenceKinds"]
                    ],
                    "evidenceState": _evidence_state(evidence),
                    "evidence": evidence,
                }
            )
        system_manager = self._is_internal_system_manager()
        project_mutable = str(project.get("lifecycle_state") or "") not in {
            "cancelled",
            "completed",
        }
        return {
            "project": {
                "globalId": str(UUID(str(project.global_id))),
                "businessCode": str(project.business_code),
                "title": str(project.title),
            },
            "gate": {
                "globalId": str(UUID(str(gate.global_id))),
                "key": str(gate.gate_key),
                "title": str(gate.title),
                "state": str(gate.state),
                "version": int(gate.optimistic_version),
                "dueDate": _date_iso(gate.gate_due_date),
                "templateRef": {
                    "globalId": str(UUID(str(gate.gate_template_global_id))),
                    "version": int(gate.gate_template_version),
                    "snapshotHash": str(gate.gate_template_snapshot_hash),
                },
                "requirementSnapshotHash": str(gate.requirement_snapshot_hash),
                "frozenAt": _datetime_iso(gate.requirements_frozen_at),
                "frozenBy": str(gate.requirements_frozen_by),
            },
            "requirements": requirement_responses,
            "summary": {
                "requiredCount": required_count,
                "missingRequiredCount": missing_required_count,
                "unsafeScanCount": unsafe_scan_count,
                "evidenceCount": len(evidence_documents),
            },
            "permissions": {
                "canView": True,
                "canAttachEvidence": system_manager and project_mutable,
                "canAdminister": system_manager and project_mutable,
            },
        }

    def _evidence_response(
        self,
        project,
        document,
    ) -> dict[str, Any]:
        try:
            source_snapshot = _json_object(document.source_snapshot)
        except ValueError as error:
            raise ValueError(
                "Persisted Gate evidence source snapshot is invalid."
            ) from error
        response: dict[str, Any] = {
            "globalId": str(UUID(str(document.global_id))),
            "kind": str(document.evidence_kind),
            "sourceObjectType": str(document.source_object_type),
            "sourceGlobalId": str(UUID(str(document.source_global_id))),
            "revision": int(document.source_version),
            "objectHash": str(document.source_hash),
            "createdAt": _datetime_iso(document.created_at),
            "createdBy": str(document.created_by),
        }
        if str(document.evidence_kind) == "file_revision":
            source = _optional_doc(
                "NPI File Revision",
                str(UUID(str(document.source_global_id))),
            )
            if (
                source is None
                or not has_complete_file_revision_identity(source)
                or not has_live_private_file_identity(source)
                or str(source.tenant_id) != str(project.tenant_id)
                or str(source.project_global_id) != str(project.global_id)
                or int(source.revision) != int(document.source_version)
                or str(source.sha256) != str(document.source_hash)
            ):
                raise ValueError(
                    "Persisted Gate File Revision evidence integrity failed."
                )
            safe_file_snapshot = file_revision_source_snapshot(source)
            immutable_file_fields = (
                "documentGlobalId",
                "fileContentHash",
                "fileId",
                "fileName",
                "globalId",
                "isPrivate",
                "mimeType",
                "revision",
                "sha256",
                "sizeBytes",
            )
            if any(
                source_snapshot.get(field) != safe_file_snapshot.get(field)
                for field in immutable_file_fields
            ):
                raise ValueError(
                    "Persisted Gate File Revision snapshot integrity failed."
                )
            response["file"] = {
                "fileName": str(safe_file_snapshot["fileName"]),
                "mimeType": str(safe_file_snapshot["mimeType"]),
                "sizeBytes": int(safe_file_snapshot["sizeBytes"]),
                "scanState": str(safe_file_snapshot["scanState"]),
            }
        elif (
            canonical_snapshot_hash(source_snapshot) != str(document.source_hash)
            or source_snapshot.get("globalId") != str(document.source_global_id)
            or source_snapshot.get("projectGlobalId") != str(project.global_id)
            or source_snapshot.get("tenantId") != str(project.tenant_id)
            or source_snapshot.get("optimisticVersion") != int(document.source_version)
        ):
            raise ValueError("Persisted Gate WBS evidence snapshot integrity failed.")
        return response

    def _resolve_exact_source(
        self,
        project,
        *,
        evidence_kind: str,
        source_global_id: UUID,
        source_version: int,
        source_hash: str,
    ) -> dict[str, object]:
        doctype = "NPI WBS Item" if evidence_kind == "wbs_item" else "NPI File Revision"
        source = _optional_doc(doctype, str(source_global_id))
        if source is None:
            raise EvidenceSourceUnavailable()
        if str(source.tenant_id) != str(project.tenant_id) or str(
            source.project_global_id
        ) != str(project.global_id):
            raise EvidenceSourceUnavailable()
        if evidence_kind == "wbs_item":
            snapshot = wbs_item_source_snapshot(source)
            expected_version = int(source.optimistic_version)
            expected_hash = canonical_snapshot_hash(snapshot)
        else:
            if not has_complete_file_revision_identity(
                source
            ) or not has_live_private_file_identity(source):
                raise EvidenceSourceUnavailable()
            snapshot = file_revision_source_snapshot(source)
            expected_version = int(source.revision)
            expected_hash = str(source.sha256)
        if expected_version != source_version or expected_hash != source_hash:
            raise EvidenceVersionConflict()
        return snapshot

    def _requirement_snapshot(self, gate) -> dict[str, Any]:
        if int(gate.requirements_frozen or 0) != 1:
            raise GateRequirementsNotFrozen()
        snapshot = _json_object(gate.requirement_snapshot)
        expected_template_ref = {
            "globalId": str(UUID(str(gate.gate_template_global_id))),
            "version": int(gate.gate_template_version),
            "snapshotHash": str(gate.gate_template_snapshot_hash),
        }
        if (
            set(snapshot)
            != {
                "schemaVersion",
                "gateTemplateRef",
                "gateDueDate",
                "requirements",
            }
            or snapshot.get("schemaVersion") != 1
            or snapshot.get("gateTemplateRef") != expected_template_ref
            or snapshot.get("gateDueDate") != _date_iso(gate.gate_due_date)
            or canonical_snapshot_hash(snapshot) != str(gate.requirement_snapshot_hash)
        ):
            raise ValueError("Persisted Gate requirement snapshot integrity failed.")
        return snapshot

    def _load_gate_template(self, project, gate):
        values = (
            gate.gate_template_global_id,
            gate.gate_template_version,
            gate.gate_template_snapshot_hash,
        )
        if not all(value not in (None, "", 0) for value in values):
            raise GateTemplateUnavailable()
        try:
            template_global_id = UUID(str(gate.gate_template_global_id))
            template_version = int(gate.gate_template_version)
        except (TypeError, ValueError):
            raise GateTemplateUnavailable()
        snapshot = load_exact_gate_template_snapshot(
            template_global_id,
            template_version,
            str(gate.gate_template_snapshot_hash),
        )
        if snapshot is None:
            raise GateTemplateUnavailable()
        project_type = ProjectType(str(project.project_type))
        if project_type not in snapshot.applicable_project_types:
            raise GateTemplateUnavailable()
        return snapshot

    @staticmethod
    def _require_supported_template(template) -> None:
        unsupported = {
            kind.value
            for requirement in template.requirements
            for kind in requirement.allowed_evidence_kinds
        } - _SUPPORTED_EVIDENCE_KINDS
        if unsupported:
            raise GateTemplateUnavailable()

    def _validate_assignment_members(
        self,
        project,
        requirements: object,
    ) -> None:
        if not isinstance(requirements, list):
            raise ValueError("Frozen Gate requirements are invalid.")
        member_ids = {
            str(value)
            for requirement in requirements
            for value in (
                requirement["ownerMemberId"],
                *requirement["reviewerMemberIds"],
            )
        }
        for member_id in member_ids:
            member = _optional_doc("NPI Project Member", member_id)
            if (
                member is None
                or str(member.tenant_id) != str(project.tenant_id)
                or str(member.project_global_id) != str(project.global_id)
            ):
                raise _field_problem(
                    "requirements",
                    _("Select Project members from this Project."),
                )
            user = frappe.db.get_value(
                "User",
                str(member.user_id),
                ["enabled", "user_type"],
                as_dict=True,
            )
            if (
                not user
                or int(_record_value(user, "enabled") or 0) != 1
                or str(_record_value(user, "user_type")) != "System User"
            ):
                raise _field_problem(
                    "requirements",
                    _("Select enabled internal Project members."),
                )

    def _member_response(self, project, member_id: UUID) -> dict[str, Any]:
        member = _optional_doc("NPI Project Member", str(member_id))
        if (
            member is None
            or str(member.tenant_id) != str(project.tenant_id)
            or str(member.project_global_id) != str(project.global_id)
        ):
            raise ValueError("Persisted Gate requirement member is invalid.")
        user_id = str(member.user_id)
        full_name = frappe.db.get_value("User", user_id, "full_name")
        return {
            "memberId": str(member_id),
            "userId": user_id,
            "displayName": (
                str(full_name).strip()
                if isinstance(full_name, str) and full_name.strip()
                else user_id
            ),
        }

    @staticmethod
    def _require_gate_version(gate, expected_version: int) -> None:
        if (
            type(expected_version) is not int
            or expected_version < 1
            or int(gate.optimistic_version) != expected_version
        ):
            raise VersionConflict()

    def _authorized_project(
        self,
        project_id: UUID,
        required: ProjectAccess,
    ):
        project = _optional_doc("NPI Engineering Project", str(project_id))
        if project is None:
            return None
        return self._authorize_project_document(project, project_id, required)

    def _locked_authorized_project(
        self,
        project_id: UUID,
        required: ProjectAccess,
    ):
        try:
            project = frappe.get_doc(
                "NPI Engineering Project",
                str(project_id),
                for_update=True,
            )
        except frappe.DoesNotExistError:
            return None
        return self._authorize_project_document(
            project,
            project_id,
            required,
        )

    def _authorize_project_document(
        self,
        project,
        project_id: UUID,
        required: ProjectAccess,
    ):
        access = None
        if self._is_internal_system_manager():
            access = ProjectAccess.ADMINISTER
        elif (
            not self.principal.is_external
            and str(project.owner_user_id).casefold() == self.actor.casefold()
        ):
            access = ProjectAccess.VIEW
        principal = self.principal
        if access is not None:
            principal = replace(
                principal,
                project_access={str(project_id): access},
            )
        try:
            authorize_project(
                principal,
                str(project_id),
                required,
                project_tenant_id=str(project.tenant_id),
            )
        except PermissionDenied:
            return None
        return project

    def _gate_for_project(self, project, gate_id: UUID):
        gate = _optional_doc("NPI Gate Shell", str(gate_id))
        return self._validated_gate(project, gate, gate_id)

    def _locked_gate_for_project(self, project, gate_id: UUID):
        try:
            gate = frappe.get_doc(
                "NPI Gate Shell",
                str(gate_id),
                for_update=True,
            )
        except frappe.DoesNotExistError:
            return None
        return self._validated_gate(project, gate, gate_id)

    @staticmethod
    def _validated_gate(project, gate, gate_id: UUID):
        if gate is None or (
            str(gate.global_id) != str(gate_id)
            or str(gate.project_global_id) != str(project.global_id)
            or str(gate.engineering_project) != str(project.global_id)
        ):
            return None
        return gate

    def _is_internal_system_manager(self) -> bool:
        return (
            not self.principal.is_external and "System Manager" in self.principal.roles
        )

    def _idempotency_replay(
        self,
        actor_key_hash: str,
        payload_hash: str,
    ) -> dict[str, Any] | None:
        record = frappe.db.get_value(
            "NPI Project Work Idempotency",
            {"actor_key_hash": actor_key_hash},
            ["payload_hash", "response_json", "response_sealed"],
            as_dict=True,
            for_update=True,
        )
        if not record:
            return None
        if str(record.payload_hash) != payload_hash:
            raise IdempotencyConflict()
        if int(record.response_sealed or 0) != 1:
            raise RuntimeError("Persisted Gate command idempotency is unsealed.")
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
                    "doctype": "NPI Project Work Idempotency",
                    "record_id": str(uuid4()),
                    "actor": self.actor,
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "operation": operation,
                    "actor_key_hash": actor_key_hash,
                    "payload_hash": payload_hash,
                    "response_json": {},
                    "response_sealed": 0,
                }
            ).insert()
        except (frappe.UniqueValidationError, frappe.DuplicateEntryError):
            frappe.db.rollback()
            replay = self._idempotency_replay(actor_key_hash, payload_hash)
            if replay is None:
                raise
            return replay

    @staticmethod
    def _seal_idempotency(document, response: Mapping[str, object]) -> None:
        document.response_json = dict(response)
        document.response_sealed = 1
        document.save()

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


def _requirement_by_key(
    snapshot: Mapping[str, Any],
    requirement_key: str,
) -> dict[str, Any]:
    requirements = snapshot.get("requirements")
    if not isinstance(requirements, list):
        raise ValueError("Persisted Gate requirements are invalid.")
    matches = [
        requirement
        for requirement in requirements
        if isinstance(requirement, dict)
        and str(requirement.get("key")).casefold() == requirement_key.casefold()
    ]
    if len(matches) != 1:
        raise _field_problem(
            "requirementKey",
            _("Select a requirement from this Gate."),
        )
    return matches[0]


def _evidence_state(evidence: Sequence[Mapping[str, Any]]) -> str:
    if not evidence:
        return "missing"
    scan_states = [
        str(file_metadata["scanState"])
        for item in evidence
        for file_metadata in (item.get("file"),)
        if isinstance(file_metadata, dict)
    ]
    if "infected" in scan_states:
        return "scan_infected"
    if "failed" in scan_states:
        return "scan_failed"
    if "pending" in scan_states:
        return "scan_pending"
    if scan_states:
        return "scan_clean"
    return "attached"


def _payload_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            _jsonable(value),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _jsonable(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _jsonable(nested)
            for key, nested in sorted(
                value.items(),
                key=lambda item: str(item[0]),
            )
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        values = [_jsonable(nested) for nested in value]
        if all(isinstance(nested, dict) and "key" in nested for nested in values):
            return sorted(values, key=lambda nested: str(nested["key"]).casefold())
        if values and all(
            isinstance(nested, str) and _is_uuid_text(nested) for nested in values
        ):
            return sorted(values)
        return values
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def _project_documents(
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
        raise ValueError("Persisted Gate evidence collection exceeds its safe bound.")
    return tuple(frappe.get_doc(doctype, name) for name in names)


def _optional_doc(doctype: str, name: str):
    try:
        return frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        return None


def _json_object(value: object) -> dict[str, Any]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, dict):
        raise ValueError("Persisted Gate JSON value must be an object.")
    return parsed


def _date_iso(value: object) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return date.fromisoformat(str(value)).isoformat()


def _datetime_iso(value: object) -> str:
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    elif isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _database_datetime(value: datetime) -> str:
    parsed = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return (
        parsed.astimezone(UTC)
        .replace(tzinfo=None)
        .isoformat(
            sep=" ",
            timespec="microseconds",
        )
    )


def _record_value(record: object, fieldname: str) -> object:
    if isinstance(record, dict):
        return record.get(fieldname)
    return getattr(record, fieldname, None)


def _is_uuid_text(value: str) -> bool:
    try:
        return str(UUID(value)) == value.casefold()
    except (ValueError, AttributeError):
        return False


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


@contextmanager
def _controlled_gate_write_scope() -> Iterator[None]:
    flags = frappe.flags
    missing = object()
    names = (
        GATE_EVIDENCE_COMMAND_FLAG,
        "npi_project_command_write",
        "npi_project_work_command_write",
        "npi_audit_append",
    )
    previous = {name: getattr(flags, name, missing) for name in names}
    for name in names:
        setattr(flags, name, True)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is missing:
                try:
                    delattr(flags, name)
                except AttributeError:
                    pass
            else:
                setattr(flags, name, value)
