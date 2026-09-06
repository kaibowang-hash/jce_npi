from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.project_controls.frappe_validation import (
    deny_project_control_history_delete,
    normalize_uuid_fields,
    require_actor,
    require_positive_integer,
    require_project_control_write,
    require_request_id,
    require_trace_id,
)


class NPIProjectFollower(Document):
    _IDENTITY_FIELDS = (
        "global_id",
        "follower_key",
        "tenant_id",
        "project_global_id",
        "user_id",
    )

    def before_insert(self) -> None:
        require_project_control_write()

    def before_save(self) -> None:
        require_project_control_write()

    def on_trash(self) -> None:
        deny_project_control_history_delete()

    def validate(self) -> None:
        normalize_uuid_fields(self, ("global_id", "project_global_id"))
        if not self.tenant_id:
            frappe.throw(_("Tenant ID is required."), frappe.ValidationError)
        self.user_id = require_actor(self.user_id, _("Follower"))
        if (
            not isinstance(self.follower_key, str)
            or self.follower_key
            != f"{self.project_global_id}:{self.user_id}"
        ):
            frappe.throw(
                _("Project Follower Key does not match its identities."),
                frappe.ValidationError,
            )
        if type(self.active) not in {bool, int} or int(self.active) not in {0, 1}:
            frappe.throw(
                _("Active must be a valid true or false value."),
                frappe.ValidationError,
            )
        self.active = int(self.active)
        self.last_changed_by = require_actor(
            self.last_changed_by,
            _("Last Changed By"),
        )
        self.request_id = require_request_id(self.request_id)
        self.trace_id = require_trace_id(self.trace_id)
        previous = self.get_doc_before_save()
        if previous is None:
            self.optimistic_version = 1
            return
        for fieldname in self._IDENTITY_FIELDS:
            if self.get(fieldname) != previous.get(fieldname):
                frappe.throw(
                    _("A protected field cannot be changed."),
                    frappe.ValidationError,
                )
        require_positive_integer(
            self.optimistic_version,
            _("Optimistic Version"),
        )
        if int(self.optimistic_version) != int(previous.optimistic_version) + 1:
            frappe.throw(
                _("Follower Version must advance one version at a time."),
                frappe.ValidationError,
            )
        if int(self.active) == int(previous.active):
            frappe.throw(
                _("Follower state must change before a new version is saved."),
                frappe.ValidationError,
            )
