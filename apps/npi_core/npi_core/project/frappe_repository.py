from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any, Iterator
from uuid import UUID, uuid4, uuid5

import frappe

from npi_core.foundation.audit import create_audit_event
from npi_core.foundation.errors import PermissionDenied
from npi_core.foundation.security import Principal, ProjectAccess, authorize_project
from npi_core.project.domain import (
    BusinessCodeConflict,
    EngineeringProject,
    GateDefinition,
    GateShell,
    GateShellState,
    IdempotencyConflict,
    IdempotencyRecord,
    ProjectInstantiation,
    ProjectLifecycleState,
    ProjectReferenceType,
    ProjectSourceSystem,
    ProjectTemplateVersion,
    ProjectType,
    ReferenceSourceSystem,
    TemplatePublicationState,
    TemplateReferenceRule,
    TemplateSnapshot,
    TypedReference,
    business_code_reservation_hash,
)


class FrappeProjectRepository:
    """Frappe persistence adapter for the atomic P4-01 Project command/query."""

    def __init__(self, *, principal: Principal, request_id: str, trace_id: str) -> None:
        self.principal = principal
        self.actor = principal.user_id
        self.request_id = request_id
        self.trace_id = trace_id

    def get_template_version(
        self,
        template_global_id: UUID,
        template_version: int,
    ) -> ProjectTemplateVersion | None:
        version_key = f"{template_global_id}:{template_version}"
        document = _optional_doc("NPI Project Template Version", version_key)
        if document is None:
            return None
        template_root = _optional_doc(
            "NPI Project Template",
            str(document.project_template),
        )
        if template_root is None or int(template_root.enabled or 0) != 1:
            return None
        if (
            str(template_root.global_id) != str(document.template_global_id)
            or str(template_root.template_code) != str(document.template_code)
        ):
            raise ValueError("Persisted Project Template root integrity failed.")
        project_types = _json_array(document.applicable_project_types)
        template = ProjectTemplateVersion(
            global_id=UUID(str(document.global_id)),
            template_global_id=UUID(str(document.template_global_id)),
            template_code=str(document.template_code),
            template_version=int(document.template_version),
            version=int(document.optimistic_version),
            title=str(document.title),
            publication_state=TemplatePublicationState(
                str(document.publication_state)
            ),
            applicable_project_types=tuple(
                ProjectType(str(value)) for value in project_types
            ),
            reference_rules=tuple(
                TemplateReferenceRule(
                    reference_type=ProjectReferenceType(str(row.reference_type)),
                    required=bool(row.required),
                    allow_multiple=bool(row.allow_multiple),
                )
                for row in document.reference_rules
            ),
            gates=tuple(
                GateDefinition(
                    key=str(row.gate_key),
                    title=str(row.title),
                    sequence=int(row.sequence),
                )
                for row in document.gates
            ),
        )
        if (
            template.template_global_id != template_global_id
            or template.template_version != template_version
            or str(document.snapshot_hash) != template.snapshot_hash
        ):
            raise ValueError("Persisted Project Template version integrity failed.")
        return template

    def get_idempotency_record(self, key: str) -> IdempotencyRecord | None:
        record = frappe.db.get_value(
            "NPI Project Idempotency",
            {"actor_key_hash": key},
            ["actor_key_hash", "payload_hash", "project_global_id"],
            as_dict=True,
        )
        if not record:
            return None
        if str(record.actor_key_hash) != key:
            raise ValueError("Persisted Project idempotency identity failed.")
        result = self._load_instantiation(UUID(str(record.project_global_id)))
        return IdempotencyRecord(
            key=key,
            payload_hash=str(record.payload_hash),
            result=result,
        )

    def business_code_exists(self, tenant_id: str, business_code: str) -> bool:
        reservation_key = business_code_reservation_hash(tenant_id, business_code)
        return _optional_doc("NPI Project Business Code", reservation_key) is not None

    def save_atomic(
        self,
        result: ProjectInstantiation,
        idempotency_record: IdempotencyRecord,
    ) -> ProjectInstantiation:
        project = result.project
        with _controlled_write_scope():
            try:
                frappe.get_doc(
                    {
                        "doctype": "NPI Project Idempotency",
                        "record_id": str(uuid4()),
                        "actor": self.actor,
                        "tenant_id": project.tenant_id,
                        "actor_key_hash": idempotency_record.key,
                        "payload_hash": idempotency_record.payload_hash,
                        "project_global_id": str(project.global_id),
                    }
                ).insert()
            except frappe.UniqueValidationError:
                # A concurrent loser can retain a REPEATABLE READ snapshot from
                # before the winner committed. The idempotency insert is the
                # command's first write, so resetting this top-level command
                # transaction cannot discard a successful domain mutation.
                frappe.db.rollback()
                existing = self.get_idempotency_record(idempotency_record.key)
                if existing is None:
                    raise
                if existing.payload_hash != idempotency_record.payload_hash:
                    raise IdempotencyConflict()
                return replace(existing.result, replayed=True)

            reservation_key = business_code_reservation_hash(
                project.tenant_id,
                project.business_code,
            )
            try:
                frappe.get_doc(
                    {
                        "doctype": "NPI Project Business Code",
                        "reservation_key_hash": reservation_key,
                        "tenant_id": project.tenant_id,
                        "business_code": project.business_code,
                        "project_global_id": str(project.global_id),
                    }
                ).insert()
            except (
                frappe.DuplicateEntryError,
                frappe.UniqueValidationError,
            ) as error:
                raise BusinessCodeConflict() from error

            snapshot_payload = _snapshot_payload(project.template_snapshot)
            frappe.get_doc(
                {
                    "doctype": "NPI Engineering Project",
                    "global_id": str(project.global_id),
                    "tenant_id": project.tenant_id,
                    "business_code": project.business_code,
                    "title": project.title,
                    "project_type": project.project_type.value,
                    "owner_user_id": project.owner_user_id,
                    "target_sop": project.target_sop.isoformat(),
                    "lifecycle_state": project.state.value,
                    "optimistic_version": project.version,
                    "source_system": project.source_system.value,
                    "template_global_id": str(
                        project.template_snapshot.template_global_id
                    ),
                    "template_code": project.template_snapshot.template_code,
                    "template_version": project.template_snapshot.template_version,
                    "template_snapshot_hash": (
                        project.template_snapshot.snapshot_hash
                    ),
                    "template_snapshot": json.dumps(
                        snapshot_payload,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    "references": [
                        {
                            "reference_type": reference.reference_type.value,
                            "source_system": reference.source_system.value,
                            "source_object_id": reference.source_object_id,
                            "reference_global_id": (
                                str(reference.global_id)
                                if reference.global_id is not None
                                else None
                            ),
                        }
                        for reference in project.references
                    ],
                    "creation_payload_hash": project.creation_payload_hash,
                }
            ).insert()

            for gate in result.gates:
                frappe.get_doc(
                    {
                        "doctype": "NPI Gate Shell",
                        "global_id": str(gate.global_id),
                        "engineering_project": str(project.global_id),
                        "project_global_id": str(project.global_id),
                        "gate_key": gate.key,
                        "title": gate.title,
                        "sequence": gate.sequence,
                        "state": gate.state.value,
                        "optimistic_version": gate.version,
                        "template_global_id": str(gate.template_global_id),
                        "template_version": gate.template_version,
                        "template_snapshot_hash": gate.template_snapshot_hash,
                        "template_gate_snapshot": json.dumps(
                            {
                                "key": gate.key,
                                "sequence": gate.sequence,
                                "title": gate.title,
                            },
                            ensure_ascii=False,
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                    }
                ).insert()

            event = create_audit_event(
                actor=self.actor,
                trace_id=self.trace_id,
                operation="project.create",
                global_id=project.global_id,
                object_version=project.version,
                result="created",
                input_summary={
                    "businessCode": project.business_code,
                    "gateCount": len(result.gates),
                    "payloadHash": project.creation_payload_hash,
                    "referenceCount": len(project.references),
                    "requestId": self.request_id,
                    "templateGlobalId": str(
                        project.template_snapshot.template_global_id
                    ),
                    "templateVersion": project.template_snapshot.template_version,
                    "tenantId": project.tenant_id,
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
        return result

    def project_cockpit(
        self,
        project_global_id: UUID,
    ) -> dict[str, Any] | None:
        document = _optional_doc("NPI Engineering Project", str(project_global_id))
        if document is None:
            return None
        system_manager = (
            not self.principal.is_external
            and "System Manager" in self.principal.roles
        )
        access = None
        if system_manager:
            access = ProjectAccess.ADMINISTER
        elif str(document.owner_user_id).casefold() == self.actor.casefold():
            access = ProjectAccess.VIEW
        scoped_principal = replace(
            self.principal,
            project_access=(
                {str(project_global_id): access}
                if access is not None
                else {}
            ),
        )
        try:
            authorize_project(
                scoped_principal,
                str(project_global_id),
                ProjectAccess.VIEW,
                project_tenant_id=str(document.tenant_id),
            )
        except PermissionDenied:
            return None
        snapshot = _snapshot_from_project_document(document)
        gates = self._load_gate_documents(project_global_id, snapshot)
        references = []
        for row in document.references:
            reference: dict[str, Any] = {
                "type": str(row.reference_type),
                "sourceSystem": str(row.source_system),
                "sourceObjectId": str(row.source_object_id),
            }
            if row.reference_global_id:
                reference["globalId"] = str(UUID(str(row.reference_global_id)))
            references.append(reference)
        return {
            "project": {
                "globalId": str(UUID(str(document.global_id))),
                "businessCode": str(document.business_code),
                "title": str(document.title),
                "projectType": str(document.project_type),
                "state": str(document.lifecycle_state),
                "version": int(document.optimistic_version),
                "tenantId": str(document.tenant_id),
                "ownerUserId": str(document.owner_user_id),
                "targetSop": _date_iso(document.target_sop),
                "createdAt": _datetime_iso(document.creation),
                "lastChangedAt": _datetime_iso(document.modified),
                "lastChangedBy": str(document.modified_by),
                "source": {
                    "sourceSystem": "NPI_ONE",
                    "editableIn": "NPI_ONE",
                    "syncState": "local",
                },
            },
            "templateRef": {
                "globalId": str(snapshot.template_global_id),
                "code": snapshot.template_code,
                "version": snapshot.template_version,
                "snapshotHash": snapshot.snapshot_hash,
            },
            "references": references,
            "gates": [
                {
                    "globalId": str(UUID(str(gate.global_id))),
                    "key": str(gate.gate_key),
                    "title": str(gate.title),
                    "sequence": int(gate.sequence),
                    "state": str(gate.state),
                    "version": int(gate.optimistic_version),
                }
                for gate in gates
            ],
            "permissions": {
                "canView": True,
                "canContribute": system_manager,
                "canAdminister": system_manager,
            },
        }

    def _load_instantiation(self, project_global_id: UUID) -> ProjectInstantiation:
        document = frappe.get_doc(
            "NPI Engineering Project",
            str(project_global_id),
        )
        snapshot = _snapshot_from_project_document(document)
        references = tuple(
            TypedReference(
                reference_type=ProjectReferenceType(str(row.reference_type)),
                source_system=ReferenceSourceSystem(str(row.source_system)),
                source_object_id=str(row.source_object_id),
                global_id=(
                    UUID(str(row.reference_global_id))
                    if row.reference_global_id
                    else None
                ),
            )
            for row in document.references
        )
        project = EngineeringProject(
            global_id=UUID(str(document.global_id)),
            tenant_id=str(document.tenant_id),
            business_code=str(document.business_code),
            title=str(document.title),
            project_type=ProjectType(str(document.project_type)),
            owner_user_id=str(document.owner_user_id),
            target_sop=date.fromisoformat(_date_iso(document.target_sop)),
            state=ProjectLifecycleState(str(document.lifecycle_state)),
            version=int(document.optimistic_version),
            source_system=ProjectSourceSystem(str(document.source_system)),
            template_snapshot=snapshot,
            references=references,
            creation_payload_hash=str(document.creation_payload_hash),
        )
        gates = tuple(
            GateShell(
                global_id=UUID(str(row.global_id)),
                project_global_id=UUID(str(row.project_global_id)),
                key=str(row.gate_key),
                title=str(row.title),
                sequence=int(row.sequence),
                state=GateShellState(str(row.state)),
                version=int(row.optimistic_version),
                template_global_id=UUID(str(row.template_global_id)),
                template_version=int(row.template_version),
                template_snapshot_hash=str(row.template_snapshot_hash),
            )
            for row in self._load_gate_documents(
                project_global_id,
                snapshot,
            )
        )
        return ProjectInstantiation(project=project, gates=gates)

    @staticmethod
    def _load_gate_documents(
        project_global_id: UUID,
        snapshot: TemplateSnapshot,
    ) -> tuple[Any, ...]:
        documents = []
        for definition in snapshot.gates:
            gate_global_id = uuid5(
                project_global_id,
                f"gate-shell:{definition.sequence}:{definition.key}",
            )
            document = frappe.get_doc(
                "NPI Gate Shell",
                str(gate_global_id),
            )
            if (
                str(document.project_global_id) != str(project_global_id)
                or str(document.gate_key) != definition.key
                or int(document.sequence) != definition.sequence
            ):
                raise ValueError("Persisted Gate shell integrity failed.")
            documents.append(document)
        return tuple(documents)


def _optional_doc(doctype: str, name: str):
    try:
        return frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        return None


def _json_array(value: object) -> list[object]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, list):
        raise ValueError("Persisted JSON value must be an array.")
    return parsed


def _json_object(value: object) -> dict[str, Any]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, dict):
        raise ValueError("Persisted JSON value must be an object.")
    return parsed


def _snapshot_payload(snapshot: TemplateSnapshot) -> dict[str, Any]:
    return {
        "templateGlobalId": str(snapshot.template_global_id),
        "templateCode": snapshot.template_code,
        "templateVersion": snapshot.template_version,
        "applicableProjectTypes": [
            project_type.value for project_type in snapshot.applicable_project_types
        ],
        "referenceRules": [
            {
                "type": rule.reference_type.value,
                "required": rule.required,
                "allowMultiple": rule.allow_multiple,
            }
            for rule in snapshot.reference_rules
        ],
        "gates": [
            {"key": gate.key, "title": gate.title, "sequence": gate.sequence}
            for gate in snapshot.gates
        ],
    }


def _snapshot_from_project_document(document) -> TemplateSnapshot:
    payload = _json_object(document.template_snapshot)
    snapshot = TemplateSnapshot(
        template_global_id=UUID(str(payload["templateGlobalId"])),
        template_code=str(payload["templateCode"]),
        template_version=int(payload["templateVersion"]),
        snapshot_hash=str(document.template_snapshot_hash),
        applicable_project_types=tuple(
            ProjectType(str(value)) for value in payload["applicableProjectTypes"]
        ),
        reference_rules=tuple(
            TemplateReferenceRule(
                reference_type=ProjectReferenceType(str(rule["type"])),
                required=bool(rule["required"]),
                allow_multiple=bool(rule["allowMultiple"]),
            )
            for rule in payload["referenceRules"]
        ),
        gates=tuple(
            GateDefinition(
                key=str(gate["key"]),
                title=str(gate["title"]),
                sequence=int(gate["sequence"]),
            )
            for gate in payload["gates"]
        ),
    )
    canonical_payload = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    persisted_hash = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
    if (
        _snapshot_payload(snapshot) != payload
        or persisted_hash != snapshot.snapshot_hash
    ):
        raise ValueError("Persisted Project template snapshot integrity failed.")
    return snapshot


def _date_iso(value: object) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    parsed = date.fromisoformat(str(value))
    return parsed.isoformat()


def _datetime_iso(value: object) -> str:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


@contextmanager
def _controlled_write_scope() -> Iterator[None]:
    flags = frappe.flags
    missing = object()
    previous_command = getattr(flags, "npi_project_command_write", missing)
    previous_audit = getattr(flags, "npi_audit_append", missing)
    flags.npi_project_command_write = True
    flags.npi_audit_append = True
    try:
        yield
    finally:
        _restore_flag(flags, "npi_project_command_write", previous_command, missing)
        _restore_flag(flags, "npi_audit_append", previous_audit, missing)


def _restore_flag(flags, name: str, previous: object, missing: object) -> None:
    if previous is missing:
        try:
            delattr(flags, name)
        except AttributeError:
            pass
    else:
        setattr(flags, name, previous)
