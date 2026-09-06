from __future__ import annotations

import json
from uuid import UUID, uuid5

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.gate_template.domain import (
    EvidenceKind,
    GateRequirementClassification,
    GateRequirementDefinition,
    GateRequirementPriority,
    GateTemplatePublicationState,
    GateTemplateVersion,
)
from npi_core.project.domain import ProjectType
from npi_core.project.frappe_validation import (
    assert_immutable_fields,
    deny_controlled_history_delete,
    ensure_uuid,
    throw_domain_validation,
)


class NPIGateTemplateVersion(Document):
    """Versioned administrative definition; published content is immutable."""

    _CONTENT_FIELDS = (
        "global_id",
        "gate_template",
        "gate_template_global_id",
        "gate_template_code",
        "gate_template_version",
        "version_key",
        "title",
        "publication_state",
        "applicable_project_types",
        "requirements",
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
            "NPI Gate Template",
            self.gate_template,
            ["global_id", "template_code"],
            as_dict=True,
        )
        if not template_identity:
            frappe.throw(
                _("Select an existing Gate Template."),
                frappe.ValidationError,
            )
        self.gate_template_global_id = ensure_uuid(
            template_identity.global_id,
            _("Gate Template Global ID"),
        )
        self.gate_template_code = template_identity.template_code
        if self.gate_template_version:
            expected_global_id = uuid5(
                UUID(self.gate_template_global_id),
                f"gate-template-version:{self.gate_template_version}",
            )
            if self.global_id:
                try:
                    supplied_global_id = UUID(str(self.global_id))
                except (TypeError, ValueError, AttributeError):
                    supplied_global_id = None
                if supplied_global_id != expected_global_id:
                    frappe.throw(
                        _("Enter a valid Gate Template."),
                        frappe.ValidationError,
                    )
            self.global_id = str(expected_global_id)
            self.version_key = (
                f"{self.gate_template_global_id}:{self.gate_template_version}"
            )

    def validate(self) -> None:
        self.global_id = ensure_uuid(self.global_id, _("Global ID"))
        if (
            type(self.gate_template_version) is not int
            or self.gate_template_version < 1
        ):
            frappe.throw(
                _("Gate Template Version must be greater than zero."),
                frappe.ValidationError,
            )
        project_types = self._project_types()
        previous = self.get_doc_before_save()
        if previous is not None and previous.publication_state == "published":
            frappe.throw(
                _("A published Gate Template version cannot be changed."),
                frappe.ValidationError,
            )
        self._validate_new_version_sequence(previous)
        if previous is not None:
            assert_immutable_fields(
                self,
                previous,
                (
                    "global_id",
                    "gate_template",
                    "gate_template_global_id",
                    "gate_template_code",
                    "gate_template_version",
                    "version_key",
                ),
            )
            self.optimistic_version = int(previous.optimistic_version) + 1
        else:
            self.optimistic_version = 1

        domain_template = self._domain_template(project_types)
        self.title = domain_template.title
        self.gate_template_code = domain_template.gate_template_code
        self.snapshot_hash = domain_template.snapshot_hash
        if self.publication_state == "published":
            self.published_at = now_datetime()
        else:
            self.published_at = None

    def _validate_new_version_sequence(self, previous: object) -> None:
        if previous is not None:
            return
        if self.gate_template_version == 1:
            first_existing = frappe.db.get_value(
                "NPI Gate Template Version",
                {"gate_template_global_id": self.gate_template_global_id},
                ["name"],
                as_dict=True,
            )
            valid_sequence = first_existing is None
        else:
            previous_version = frappe.db.get_value(
                "NPI Gate Template Version",
                (
                    f"{self.gate_template_global_id}:"
                    f"{self.gate_template_version - 1}"
                ),
                ["publication_state"],
                as_dict=True,
            )
            valid_sequence = (
                previous_version is not None
                and previous_version.publication_state == "published"
            )
        if not valid_sequence:
            frappe.throw(
                _("Publish each Gate Template version before creating the next."),
                frappe.ValidationError,
            )

    def _project_types(self) -> tuple[ProjectType, ...]:
        values = _json_value(
            self.applicable_project_types,
            expected_type=list,
            message=_("Applicable Project Types must be a JSON array."),
        )
        allowed = {value.value for value in ProjectType}
        if any(type(value) is not str or value not in allowed for value in values):
            frappe.throw(
                _("Applicable Project Types contains an unsupported value."),
                frappe.ValidationError,
            )
        if len(set(values)) != len(values):
            frappe.throw(
                _("Applicable Project Types must be unique."),
                frappe.ValidationError,
            )
        normalized = tuple(
            sorted(
                (ProjectType(value) for value in values),
                key=lambda value: value.value,
            )
        )
        self.applicable_project_types = json.dumps(
            [value.value for value in normalized],
            separators=(",", ":"),
        )
        return normalized

    def _domain_template(
        self,
        project_types: tuple[ProjectType, ...],
    ) -> GateTemplateVersion:
        try:
            requirements: list[GateRequirementDefinition] = []
            for row in self.requirements or ():
                evidence_values = _json_value(
                    row.allowed_evidence_kinds,
                    expected_type=list,
                    message=_("Allowed Evidence Kinds must be a JSON array."),
                )
                requirement = GateRequirementDefinition(
                    key=row.requirement_key,
                    title=row.title,
                    classification=GateRequirementClassification(row.classification),
                    priority=GateRequirementPriority(row.priority),
                    allowed_evidence_kinds=tuple(
                        EvidenceKind(value) for value in evidence_values
                    ),
                )
                row.requirement_key = requirement.key
                row.title = requirement.title
                row.classification = requirement.classification.value
                row.priority = requirement.priority.value
                row.allowed_evidence_kinds = json.dumps(
                    [value.value for value in requirement.allowed_evidence_kinds],
                    separators=(",", ":"),
                )
                requirements.append(requirement)
            return GateTemplateVersion(
                global_id=UUID(self.global_id),
                gate_template_global_id=UUID(self.gate_template_global_id),
                gate_template_code=self.gate_template_code,
                gate_template_version=self.gate_template_version,
                version=self.optimistic_version,
                title=self.title,
                publication_state=GateTemplatePublicationState(self.publication_state),
                applicable_project_types=project_types,
                requirements=tuple(requirements),
            )
        except RequestValidationFailed as error:
            throw_domain_validation(error)
        except (TypeError, ValueError):
            frappe.throw(
                _("Enter a valid Gate Template."),
                frappe.ValidationError,
            )
        raise AssertionError("Frappe validation must raise an exception.")


def _json_value(
    value: object,
    *,
    expected_type: type[list],
    message: str,
) -> list[object]:
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (TypeError, json.JSONDecodeError):
        parsed = None
    if not isinstance(parsed, expected_type):
        frappe.throw(message, frappe.ValidationError)
    return parsed
