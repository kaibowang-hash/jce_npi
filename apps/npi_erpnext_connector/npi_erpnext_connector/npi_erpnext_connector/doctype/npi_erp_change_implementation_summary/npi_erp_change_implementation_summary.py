from __future__ import annotations

import re
from uuid import UUID

import frappe
from frappe import _
from frappe.model.document import Document

from npi_erpnext_connector.frappe_validation import (
    deny_engineering_change_execution_delete,
    require_engineering_change_execution_write,
)

_HASH = re.compile(r"^[a-f0-9]{64}$")
_ACTOR = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class NPIERPChangeImplementationSummary(Document):
    def autoname(self) -> None:
        self.revision_global_id = _uuid(
            self.revision_global_id,
            _("Engineering Change Revision Global ID"),
        )
        self.name = self.revision_global_id

    def before_insert(self) -> None:
        require_engineering_change_execution_write()

    def before_save(self) -> None:
        require_engineering_change_execution_write()
        if self.get_doc_before_save() is not None:
            frappe.throw(
                _("ERPNext Engineering Change summary projections are immutable."),
                frappe.PermissionError,
            )

    def validate(self) -> None:
        for fieldname, label in (
            ("revision_global_id", _("Engineering Change Revision Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("change_global_id", _("Engineering Change Global ID")),
            ("request_global_id", _("Delivery Request Global ID")),
        ):
            setattr(self, fieldname, _uuid(getattr(self, fieldname), label))
        for fieldname, label in (
            ("revision_snapshot_hash", _("Revision Snapshot Hash")),
            ("formal_change_source_hash", _("Formal Change Source Hash")),
            ("affected_versions_hash", _("Affected Versions Hash")),
            ("effectivity_hash", _("Effectivity Hash")),
            ("disposition_hash", _("Disposition Hash")),
            ("revalidation_hash", _("Revalidation Hash")),
            ("closure_evidence_hash", _("Closure Evidence Hash")),
            ("target_idempotency_key_hash", _("Target Idempotency Key Hash")),
            ("source_hash", _("Source Hash")),
            ("semantic_request_hash", _("Semantic Request Hash")),
            ("profile_snapshot_hash", _("Profile Snapshot Hash")),
        ):
            setattr(self, fieldname, _hash(getattr(self, fieldname), label))
        if type(self.revision_number) is not int or self.revision_number < 1:
            frappe.throw(
                _("Engineering Change Revision Number is invalid."),
                frappe.ValidationError,
            )
        if type(self.profile_version) is not int or self.profile_version < 1:
            frappe.throw(
                _("Engineering Change Profile Version is invalid."),
                frappe.ValidationError,
            )
        actor = str(self.source_actor_user_id or "")
        if (
            actor != actor.casefold()
            or len(actor) > 254
            or _ACTOR.fullmatch(actor) is None
            or actor in {"guest", "administrator"}
        ):
            frappe.throw(
                _("Engineering Change Source Actor User ID is invalid."),
                frappe.ValidationError,
            )
        if str(self.owner or "").casefold() != actor:
            frappe.throw(
                _("Engineering Change source actor attribution is invalid."),
                frappe.ValidationError,
            )

    def on_trash(self) -> None:
        deny_engineering_change_execution_delete()


def _uuid(value: object, label: str) -> str:
    try:
        result = str(UUID(str(value)))
    except (TypeError, ValueError) as error:
        frappe.throw(_("{0} is invalid.").format(label), frappe.ValidationError)
        raise AssertionError from error
    if result != value:
        frappe.throw(_("{0} is invalid.").format(label), frappe.ValidationError)
    return result


def _hash(value: object, label: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        frappe.throw(_("{0} is invalid.").format(label), frappe.ValidationError)
    return value
