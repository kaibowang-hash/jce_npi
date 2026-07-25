from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.domain import (
    DocumentRelationship,
    DocumentRelationshipKind,
    sha256_json,
)
from npi_core.documents.frappe_validation import (
    actor_text,
    assert_immutable_fields,
    canonical_json,
    canonical_uuid,
    deny_document_history_delete,
    deny_document_history_update,
    document_domain_value,
    json_object,
    optional_uuid,
    positive_integer,
    required_text,
    require_exact_parent,
    require_document_command_write,
    tenant_text,
    utc_datetime_text,
)


_ALL_FIELDS = (
    "global_id",
    "relationship_key",
    "tenant_id",
    "project_global_id",
    "controlled_document",
    "document_global_id",
    "relationship_kind",
    "project_reference_type",
    "target_source_system",
    "target_reference_global_id",
    "target_identity",
    "target_version",
    "target_snapshot",
    "snapshot_hash",
    "optimistic_version",
    "created_by_user_id",
    "created_at",
    "request_id",
    "trace_id",
)


class NPIDocumentRelationship(Document):
    """Typed, same-project relationship used for navigation and reverse lookup."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_document_command_write()

    def before_save(self) -> None:
        require_document_command_write()
        if self.get_doc_before_save() is not None:
            deny_document_history_update()

    def before_validate(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.tenant_id = tenant_text(self.tenant_id)
        self.project_global_id = canonical_uuid(
            self.project_global_id,
            _("Project Global ID"),
        )
        self.controlled_document = canonical_uuid(
            self.controlled_document,
            _("Controlled Document"),
        )
        self.document_global_id = canonical_uuid(
            self.document_global_id,
            _("Document Global ID"),
        )
        self.target_reference_global_id = optional_uuid(
            self.target_reference_global_id,
            _("Target Reference Global ID"),
        )

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _ALL_FIELDS)
            deny_document_history_update()
        if self.controlled_document != self.document_global_id:
            frappe.throw(
                _("Controlled Document must match the exact Document Global ID."),
                frappe.ValidationError,
            )
        require_exact_parent(
            "NPI Controlled Document",
            self.controlled_document,
            {
                "global_id": self.document_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
            },
            _("The document relationship does not match its controlled document."),
        )
        try:
            kind = DocumentRelationshipKind(str(self.relationship_kind))
        except ValueError:
            frappe.throw(
                _("Select a supported document relationship kind."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.")
        if kind is DocumentRelationshipKind.PROJECT_REFERENCE:
            if self.project_reference_type not in {
                "customer",
                "product",
                "part",
                "tooling",
                "order",
            }:
                frappe.throw(
                    _("Select a supported typed Project reference."),
                    frappe.ValidationError,
                )
            if self.target_source_system not in {"NPI_ONE", "ERPNEXT"}:
                frappe.throw(
                    _("Select a supported reference source system."),
                    frappe.ValidationError,
                )
        elif any(
            value not in (None, "")
            for value in (
                self.project_reference_type,
                self.target_source_system,
                self.target_reference_global_id,
            )
        ):
            frappe.throw(
                _("Only a Project reference can contain a target subtype."),
                frappe.ValidationError,
            )
        identity = required_text(
            self.target_identity,
            _("Target Identity"),
            512,
        )
        if kind is not DocumentRelationshipKind.PROJECT_REFERENCE:
            identity = canonical_uuid(identity, _("Target Identity"))
        target_version = positive_integer(
            self.target_version,
            _("Target Version"),
        )
        expected_key = sha256_json(
            {
                "tenantId": self.tenant_id,
                "projectGlobalId": self.project_global_id,
                "documentGlobalId": self.document_global_id,
                "kind": kind.value,
                "projectReferenceType": self.project_reference_type or None,
                "targetSourceSystem": self.target_source_system or None,
                "targetReferenceGlobalId": self.target_reference_global_id,
                "targetIdentity": identity,
                "targetVersion": target_version,
            }
        )
        if self.relationship_key not in (None, "", expected_key):
            frappe.throw(
                _("Relationship Key does not match the exact relationship."),
                frappe.ValidationError,
            )
        relationship = document_domain_value(
            lambda: DocumentRelationship(
                global_id=self.global_id,
                document_global_id=self.document_global_id,
                tenant_id=self.tenant_id,
                project_global_id=self.project_global_id,
                kind=kind,
                target_identity=identity,
                target_version=target_version,
                relationship_key=expected_key,
                project_reference_type=self.project_reference_type or None,
                target_source_system=self.target_source_system or None,
                target_reference_global_id=self.target_reference_global_id,
            )
        )
        _resolve_target(relationship)
        target_snapshot = {
            "schemaVersion": 1,
            "tenantId": relationship.tenant_id,
            "projectGlobalId": str(relationship.project_global_id),
            "kind": relationship.kind.value,
            "projectReferenceType": relationship.project_reference_type,
            "targetSourceSystem": relationship.target_source_system,
            "targetReferenceGlobalId": (
                str(relationship.target_reference_global_id)
                if relationship.target_reference_global_id
                else None
            ),
            "targetIdentity": relationship.target_identity,
            "targetVersion": relationship.target_version,
        }
        expected_snapshot_hash = sha256_json(target_snapshot)
        if (
            json_object(self.target_snapshot, _("Target Snapshot")) != target_snapshot
            or str(self.snapshot_hash) != expected_snapshot_hash
        ):
            frappe.throw(
                _("Target Snapshot does not match the exact related object."),
                frappe.ValidationError,
            )
        if self.optimistic_version != 1:
            frappe.throw(
                _("A new document relationship must remain at version one."),
                frappe.ValidationError,
            )
        self.relationship_key = relationship.relationship_key
        self.relationship_kind = relationship.kind.value
        self.project_reference_type = relationship.project_reference_type
        self.target_source_system = relationship.target_source_system
        self.target_reference_global_id = (
            str(relationship.target_reference_global_id)
            if relationship.target_reference_global_id
            else None
        )
        self.target_identity = relationship.target_identity
        self.target_version = relationship.target_version
        self.target_snapshot = canonical_json(target_snapshot)
        self.snapshot_hash = expected_snapshot_hash
        self.created_by_user_id = actor_text(
            self.created_by_user_id,
            _("Created By"),
        )
        self.created_at = utc_datetime_text(self.created_at, _("Created At"))
        self.request_id = required_text(
            self.request_id,
            _("Request ID"),
            128,
        )
        self.trace_id = required_text(
            self.trace_id,
            _("Trace ID"),
            128,
        )

    def on_trash(self) -> None:
        deny_document_history_delete(
            self,
            target_global_id=self.global_id,
            target_version=self.optimistic_version,
        )


def _resolve_target(relationship: DocumentRelationship) -> None:
    if relationship.kind is DocumentRelationshipKind.PROJECT:
        require_exact_parent(
            "NPI Engineering Project",
            str(relationship.project_global_id),
            {
                "global_id": relationship.target_identity,
                "tenant_id": relationship.tenant_id,
                "optimistic_version": relationship.target_version,
            },
            _("The related Project is unavailable."),
        )
        if relationship.target_identity != str(relationship.project_global_id):
            frappe.throw(
                _("The related Project must be the current Project."),
                frappe.ValidationError,
            )
        return
    if relationship.kind is DocumentRelationshipKind.PROJECT_REFERENCE:
        require_exact_parent(
            "NPI Engineering Project",
            str(relationship.project_global_id),
            {
                "global_id": str(relationship.project_global_id),
                "tenant_id": relationship.tenant_id,
                "optimistic_version": relationship.target_version,
            },
            _("The related Project reference is unavailable."),
        )
        require_exact_parent(
            "NPI Project Reference",
            {
                "parent": str(relationship.project_global_id),
                "parenttype": "NPI Engineering Project",
                "reference_type": relationship.project_reference_type,
                "source_system": relationship.target_source_system,
                "source_object_id": relationship.target_identity,
            },
            {
                "reference_type": relationship.project_reference_type,
                "source_system": relationship.target_source_system,
                "source_object_id": relationship.target_identity,
                "reference_global_id": (
                    str(relationship.target_reference_global_id)
                    if relationship.target_reference_global_id
                    else None
                ),
            },
            _("The related Project reference is unavailable."),
        )
        return
    resolver = {
        DocumentRelationshipKind.GATE: (
            "NPI Gate Shell",
            {"project_global_id": str(relationship.project_global_id)},
        ),
        DocumentRelationshipKind.WBS_ITEM: (
            "NPI WBS Item",
            {
                "tenant_id": relationship.tenant_id,
                "project_global_id": str(relationship.project_global_id),
            },
        ),
        DocumentRelationshipKind.DOMAIN_WORK_ITEM: (
            "NPI Domain Work Item",
            {
                "tenant_id": relationship.tenant_id,
                "project_global_id": str(relationship.project_global_id),
            },
        ),
    }.get(relationship.kind)
    if resolver is None:
        frappe.throw(
            _("The related object type is unavailable."),
            frappe.ValidationError,
        )
    doctype, scope = resolver
    require_exact_parent(
        doctype,
        relationship.target_identity,
        {
            "global_id": relationship.target_identity,
            **scope,
            "optimistic_version": relationship.target_version,
        },
        _("The related object is unavailable."),
    )
