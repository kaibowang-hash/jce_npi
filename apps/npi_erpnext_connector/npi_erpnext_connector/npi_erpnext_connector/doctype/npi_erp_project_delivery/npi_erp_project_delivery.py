from __future__ import annotations

import re
from uuid import UUID

import frappe
from frappe import _
from frappe.model.document import Document

from npi_erpnext_connector.frappe_validation import (
    deny_project_delivery_delete,
    require_project_delivery_write,
)
from npi_erpnext_connector.project_domain import restore_project_source_event


_HASH = re.compile(r"^[a-f0-9]{64}$")
_STATUS = {"pending", "retry", "accepted", "succeeded", "permanent_failure"}
_IMMUTABLE = (
    "event_id",
    "stream_key",
    "source_project_id",
    "source_version",
    "source_snapshot_hash",
    "event_hash",
    "event_json",
    "request_id",
    "trace_id",
)


class NPIERPProjectDelivery(Document):
    def autoname(self) -> None:
        self.event_id = _uuid(self.event_id, _("Event ID"))
        self.name = self.event_id

    def before_insert(self) -> None:
        require_project_delivery_write()

    def before_save(self) -> None:
        require_project_delivery_write()

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous:
            for fieldname in _IMMUTABLE:
                if getattr(previous, fieldname, None) != getattr(self, fieldname, None):
                    frappe.throw(
                        _("Project delivery event fields are immutable."),
                        frappe.ValidationError,
                    )
            terminal_change_forbidden = previous.status == "succeeded" and (
                self.status != previous.status
            )
            invalid_failure_replay = previous.status == "permanent_failure" and (
                self.status not in {"permanent_failure", "retry"}
            )
            if terminal_change_forbidden or invalid_failure_replay:
                frappe.throw(
                    _("A terminal Project delivery cannot be changed."),
                    frappe.ValidationError,
                )
        self.event_id = _uuid(self.event_id, _("Event ID"))
        self.request_id = _uuid(self.request_id, _("Request ID"))
        self.stream_key = _hash(self.stream_key, _("Stream Key"))
        self.source_snapshot_hash = _hash(
            self.source_snapshot_hash, _("Source Snapshot Hash")
        )
        self.event_hash = _hash(self.event_hash, _("Event Hash"))
        if not isinstance(self.source_project_id, str) or not self.source_project_id:
            frappe.throw(_("Source Project is required."), frappe.ValidationError)
        if int(self.source_version or 0) < 1:
            frappe.throw(_("Source Version is invalid."), frappe.ValidationError)
        if self.status not in _STATUS or int(self.attempt_count or 0) < 0:
            frappe.throw(_("Project delivery state is invalid."), frappe.ValidationError)
        event = restore_project_source_event(
            self.event_json,
            request_id=self.request_id,
            source_project_id=self.source_project_id,
            source_version=int(self.source_version),
            source_snapshot_hash=self.source_snapshot_hash,
            event_hash=self.event_hash,
        )
        if event.trace_id != self.trace_id:
            frappe.throw(
                _("Project delivery event binding is invalid."),
                frappe.ValidationError,
            )
        if self.receipt_id:
            self.receipt_id = _uuid(self.receipt_id, _("Receipt ID"))
        if self.target_project_global_id:
            self.target_project_global_id = _uuid(
                self.target_project_global_id, _("Target Project Global ID")
            )
        if self.status == "accepted" and not self.receipt_id:
            frappe.throw(_("Accepted Project delivery is incomplete."), frappe.ValidationError)
        if self.status == "succeeded" and (
            not self.receipt_id or not self.target_project_global_id
        ):
            frappe.throw(_("Completed Project delivery is incomplete."), frappe.ValidationError)

    def on_trash(self) -> None:
        deny_project_delivery_delete()


def _uuid(value: object, label: str) -> str:
    try:
        parsed = UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise frappe.ValidationError(_("{0} is invalid.").format(label)) from error
    if parsed.int == 0 or str(parsed) != str(value).casefold():
        frappe.throw(_("{0} is invalid.").format(label), frappe.ValidationError)
    return str(parsed)


def _hash(value: object, label: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        frappe.throw(_("{0} is invalid.").format(label), frappe.ValidationError)
    return value
