from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.change_control.domain import FORMAL_CHANGE_DOCTYPE
from npi_core.change_control.frappe_validation import (
    assert_immutable_fields,
    canonical_uuid,
    deny_change_history_delete,
    lowercase_sha256,
    positive_integer,
    required_text,
    require_change_command_write,
    require_change_observation_write,
    utc_datetime_text,
)


_STATES = frozenset({"draft", "active", "ready_to_close", "closed", "cancelled"})
_FORMAL_FIELDS = (
    "formal_change_doctype",
    "formal_change_document_id",
    "formal_change_raw_status",
    "formal_change_source_version",
    "formal_change_source_modified_at",
    "formal_change_source_hash",
    "formal_change_observed_at",
)


class NPIEngineeringChange(Document):
    """Current Project-scoped pointer; history remains in immutable revisions."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_change_command_write()

    def before_save(self) -> None:
        require_change_command_write()

    def validate(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.project_global_id = canonical_uuid(self.project_global_id, _("Project Global ID"))
        self.current_revision_global_id = canonical_uuid(self.current_revision_global_id, _("Current Revision Global ID"))
        if self.current_revision != self.current_revision_global_id:
            frappe.throw(
                _("The current revision Link must match its exact global ID."),
                frappe.ValidationError,
            )
        self.tenant_id = required_text(self.tenant_id, _("Tenant ID"))
        self.title = required_text(self.title, _("Engineering Change Title"), 280)
        if self.internal_state not in _STATES:
            frappe.throw(_("Select a supported engineering change state."), frappe.ValidationError)
        self.optimistic_version = positive_integer(self.optimistic_version, _("Optimistic Version"))
        self.current_revision_number = positive_integer(self.current_revision_number, _("Current Revision Number"))
        self.current_revision_snapshot_hash = lowercase_sha256(self.current_revision_snapshot_hash, _("Current Revision Snapshot Hash"))
        self._validate_formal_observation()
        previous = self.get_doc_before_save()
        if previous is None:
            if self.optimistic_version != 1 or self.current_revision_number != 1:
                frappe.throw(_("A new engineering change must start at version one."), frappe.ValidationError)
            if any(getattr(self, name, None) not in (None, "") for name in _FORMAL_FIELDS):
                require_change_observation_write()
            return
        assert_immutable_fields(self, previous, ("global_id", "tenant_id", "project_global_id"))
        if self.optimistic_version != int(previous.optimistic_version) + 1 or self.current_revision_number != int(previous.current_revision_number) + 1:
            frappe.throw(_("The engineering change version must advance by exactly one."), frappe.ValidationError)
        if any(getattr(self, name, None) != getattr(previous, name, None) for name in _FORMAL_FIELDS):
            require_change_observation_write()

    def on_trash(self) -> None:
        deny_change_history_delete(self)

    def _validate_formal_observation(self) -> None:
        values = tuple(getattr(self, name, None) for name in _FORMAL_FIELDS)
        if all(value in (None, "") for value in values):
            return
        if any(value in (None, "") for value in values):
            frappe.throw(_("The formal change observation must be complete."), frappe.ValidationError)
        if self.formal_change_doctype != FORMAL_CHANGE_DOCTYPE:
            frappe.throw(_("Select the supported formal change type."), frappe.ValidationError)
        self.formal_change_document_id = required_text(self.formal_change_document_id, _("Formal Change ID"))
        self.formal_change_raw_status = required_text(self.formal_change_raw_status, _("Formal Change Raw Status"))
        self.formal_change_source_version = required_text(self.formal_change_source_version, _("Formal Change Source Version"))
        utc_datetime_text(self.formal_change_source_modified_at, _("Formal Change Source Modified At"))
        self.formal_change_source_hash = lowercase_sha256(self.formal_change_source_hash, _("Formal Change Source Hash"))
        utc_datetime_text(self.formal_change_observed_at, _("Formal Change Observed At"))
