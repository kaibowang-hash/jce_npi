from __future__ import annotations

import json
import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.project.domain import (
    ProjectReferenceType,
    ProjectType,
    ReferenceSourceSystem,
)
from npi_core.project.frappe_validation import (
    assert_immutable_fields,
    deny_controlled_history_delete,
    ensure_uuid,
    require_project_command_write,
    sha256_json,
)


class NPIEngineeringProject(Document):
    """Administrative projection of the NPI-owned Engineering Project aggregate."""

    _CREATION_FIELDS = (
        "global_id",
        "tenant_id",
        "business_code",
        "title",
        "project_type",
        "owner_user_id",
        "target_sop",
        "source_system",
        "template_global_id",
        "template_code",
        "template_version",
        "template_snapshot_hash",
        "template_snapshot",
        "creation_payload_hash",
    )

    def before_insert(self) -> None:
        require_project_command_write()

    def before_save(self) -> None:
        require_project_command_write()

    def on_trash(self) -> None:
        deny_controlled_history_delete()

    def before_validate(self) -> None:
        self.source_system = "NPI_ONE"
        if self.is_new():
            self.lifecycle_state = "draft"
            self.optimistic_version = 1

    def validate(self) -> None:
        self.global_id = ensure_uuid(self.global_id, _("Global ID"))
        self.template_global_id = ensure_uuid(
            self.template_global_id,
            _("Template Global ID"),
        )
        if self.project_type not in {item.value for item in ProjectType}:
            frappe.throw(_("Select a supported project type."), frappe.ValidationError)
        if not self.owner_user_id or "@" not in self.owner_user_id:
            frappe.throw(
                _("Enter a valid owner email address."),
                frappe.ValidationError,
            )
        if self.optimistic_version < 1:
            frappe.throw(
                _("Optimistic Version must be greater than zero."),
                frappe.ValidationError,
            )
        self._validate_references()
        try:
            snapshot = (
                json.loads(self.template_snapshot)
                if isinstance(self.template_snapshot, str)
                else self.template_snapshot
            )
        except (TypeError, json.JSONDecodeError):
            snapshot = None
        if not isinstance(snapshot, dict):
            frappe.throw(
                _("Template Snapshot must be a JSON object."),
                frappe.ValidationError,
            )
        required_snapshot_fields = {
            "templateGlobalId",
            "templateCode",
            "templateVersion",
            "applicableProjectTypes",
            "referenceRules",
            "gates",
        }
        if set(snapshot) != required_snapshot_fields:
            frappe.throw(
                _("Template Snapshot has an invalid structure."),
                frappe.ValidationError,
            )
        if (
            str(snapshot["templateGlobalId"]) != self.template_global_id
            or str(snapshot["templateCode"]) != self.template_code
            or int(snapshot["templateVersion"]) != self.template_version
            or self.project_type not in snapshot["applicableProjectTypes"]
            or sha256_json(snapshot) != self.template_snapshot_hash
        ):
            frappe.throw(
                _("Template Snapshot does not match the selected template version."),
                frappe.ValidationError,
            )

        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, self._CREATION_FIELDS)

    def _validate_references(self) -> None:
        identities: set[tuple[str, str, str]] = set()
        allowed_systems = {item.value for item in ReferenceSourceSystem}
        allowed_reference_types = {item.value for item in ProjectReferenceType}
        for reference in self.references:
            if reference.reference_type not in allowed_reference_types:
                frappe.throw(
                    _("Select a supported project reference type."),
                    frappe.ValidationError,
                )
            if reference.source_system not in allowed_systems:
                frappe.throw(
                    _("Select a supported reference source system."),
                    frappe.ValidationError,
                )
            if not isinstance(reference.source_object_id, str) or not reference.source_object_id.strip():
                frappe.throw(
                    _("Enter a source object ID for every project reference."),
                    frappe.ValidationError,
                )
            if reference.reference_global_id:
                reference.reference_global_id = ensure_uuid(
                    reference.reference_global_id,
                    _("Global ID"),
                )
            identity = (
                reference.reference_type,
                reference.source_system,
                reference.source_object_id.strip().casefold(),
            )
            if identity in identities:
                frappe.throw(
                    _("Project references must be unique."),
                    frappe.ValidationError,
                )
            identities.add(identity)
