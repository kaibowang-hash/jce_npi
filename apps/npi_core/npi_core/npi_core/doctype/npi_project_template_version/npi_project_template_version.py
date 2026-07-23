from __future__ import annotations

import json
from uuid import UUID, uuid5

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.project.domain import (
    GateDefinition,
    ProjectReferenceType,
    ProjectTemplateVersion,
    ProjectType,
    TemplatePublicationState,
    TemplateReferenceRule,
)
from npi_core.project.frappe_validation import (
    assert_immutable_fields,
    deny_controlled_history_delete,
    ensure_uuid,
    throw_domain_validation,
)


class NPIProjectTemplateVersion(Document):
    """Versioned administrative definition; published content is immutable."""

    _CONTENT_FIELDS = (
        "global_id",
        "project_template",
        "template_global_id",
        "template_code",
        "template_version",
        "version_key",
        "title",
        "publication_state",
        "applicable_project_types",
        "reference_rules",
        "gates",
        "snapshot_hash",
        "published_at",
    )

    def autoname(self) -> None:
        self._set_template_identity()
        self.name = self.version_key

    def before_validate(self) -> None:
        self._set_template_identity()

    def on_trash(self) -> None:
        if self.publication_state == "published":
            deny_controlled_history_delete()

    def _set_template_identity(self) -> None:
        template_identity = frappe.db.get_value(
            "NPI Project Template",
            self.project_template,
            ["global_id", "template_code"],
            as_dict=True,
        )
        if not template_identity:
            frappe.throw(
                _("Select an existing project template."),
                frappe.ValidationError,
            )
        self.template_global_id = ensure_uuid(
            template_identity.global_id,
            _("Template Global ID"),
        )
        self.template_code = template_identity.template_code
        if self.template_version and not self.global_id:
            self.global_id = str(
                uuid5(
                    UUID(self.template_global_id),
                    f"project-template-version:{self.template_version}",
                )
            )
        if self.template_version:
            self.version_key = f"{self.template_global_id}:{self.template_version}"

    def validate(self) -> None:
        self.global_id = ensure_uuid(self.global_id, _("Global ID"))
        if type(self.template_version) is not int or self.template_version < 1:
            frappe.throw(
                _("Template Version must be greater than zero."),
                frappe.ValidationError,
            )
        project_types = self._project_types()
        if not project_types:
            frappe.throw(
                _("Select at least one applicable project type."),
                frappe.ValidationError,
            )

        previous = self.get_doc_before_save()
        if previous is not None and previous.publication_state == "published":
            frappe.throw(
                _("A published project template version cannot be changed."),
                frappe.ValidationError,
            )
        if previous is not None:
            assert_immutable_fields(
                self,
                previous,
                (
                    "global_id",
                    "project_template",
                    "template_global_id",
                    "template_code",
                    "template_version",
                    "version_key",
                ),
            )
            self.optimistic_version = int(previous.optimistic_version) + 1
        else:
            self.optimistic_version = 1

        domain_template = self._domain_template(project_types)
        self.title = domain_template.title
        self.template_code = domain_template.template_code
        self.snapshot_hash = domain_template.snapshot_hash
        if self.publication_state == "published":
            self.published_at = now_datetime()
        else:
            self.published_at = None

    def _project_types(self) -> tuple[ProjectType, ...]:
        try:
            raw_types = (
                json.loads(self.applicable_project_types)
                if isinstance(self.applicable_project_types, str)
                else self.applicable_project_types
            )
        except (TypeError, json.JSONDecodeError):
            frappe.throw(
                _("Applicable Project Types must be a JSON array."),
                frappe.ValidationError,
            )
        if not isinstance(raw_types, list):
            frappe.throw(
                _("Applicable Project Types must be a JSON array."),
                frappe.ValidationError,
            )
        allowed = {item.value for item in ProjectType}
        if any(type(item) is not str or item not in allowed for item in raw_types):
            frappe.throw(
                _("Applicable Project Types contains an unsupported value."),
                frappe.ValidationError,
            )
        if len(set(raw_types)) != len(raw_types):
            frappe.throw(
                _("Applicable Project Types must be unique."),
                frappe.ValidationError,
            )
        normalized = tuple(
            sorted(
                (ProjectType(item) for item in raw_types),
                key=lambda item: item.value,
            )
        )
        self.applicable_project_types = json.dumps(
            [item.value for item in normalized],
            separators=(",", ":"),
        )
        return normalized

    def _domain_template(
        self,
        project_types: tuple[ProjectType, ...],
    ) -> ProjectTemplateVersion:
        try:
            reference_rules = tuple(
                TemplateReferenceRule(
                    reference_type=ProjectReferenceType(row.reference_type),
                    required=bool(row.required),
                    allow_multiple=bool(row.allow_multiple),
                )
                for row in (self.reference_rules or ())
            )
            gates = []
            for row in self.gates or ():
                gate = GateDefinition(
                    key=row.gate_key,
                    title=row.title,
                    sequence=row.sequence,
                )
                row.gate_key = gate.key
                row.title = gate.title
                row.sequence = gate.sequence
                gates.append(gate)
            return ProjectTemplateVersion(
                global_id=UUID(self.global_id),
                template_global_id=UUID(self.template_global_id),
                template_code=self.template_code,
                template_version=self.template_version,
                version=self.optimistic_version,
                title=self.title,
                publication_state=TemplatePublicationState(self.publication_state),
                applicable_project_types=project_types,
                reference_rules=reference_rules,
                gates=tuple(gates),
            )
        except RequestValidationFailed as error:
            throw_domain_validation(error)
        except (TypeError, ValueError):
            frappe.throw(_("Enter a valid value."), frappe.ValidationError)
        raise AssertionError("Frappe validation must raise an exception.")
