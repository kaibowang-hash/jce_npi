from __future__ import annotations

import json
import re
from uuid import UUID

import frappe
from frappe import _
from frappe.model.document import Document

from npi_erpnext_connector.domain import canonical_hash, canonical_json
from npi_erpnext_connector.frappe_validation import (
    deny_delivery_delete,
    require_delivery_write,
)


_HASH = re.compile(r"^[a-f0-9]{64}$")
_STATUS = {"pending", "retry", "delivered", "permanent_failure"}
_IMMUTABLE = (
    "event_id",
    "stream_key",
    "target_user_id",
    "source_version",
    "source_snapshot_hash",
    "event_hash",
    "event_json",
    "request_id",
    "trace_id",
    "expires_at",
)


class NPIERPAuthorizationDelivery(Document):
    def autoname(self) -> None:
        self.event_id = _uuid(self.event_id, _("Event ID"))
        self.name = self.event_id

    def before_insert(self) -> None:
        require_delivery_write()

    def before_save(self) -> None:
        require_delivery_write()

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous:
            for fieldname in _IMMUTABLE:
                if getattr(previous, fieldname, None) != getattr(self, fieldname, None):
                    frappe.throw(
                        _("Authorization delivery event fields are immutable."),
                        frappe.ValidationError,
                    )
        self.event_id = _uuid(self.event_id, _("Event ID"))
        self.request_id = _uuid(self.request_id, _("Request ID"))
        self.stream_key = _hash(self.stream_key, _("Stream Key"))
        self.source_snapshot_hash = _hash(
            self.source_snapshot_hash,
            _("Source Snapshot Hash"),
        )
        self.event_hash = _hash(self.event_hash, _("Event Hash"))
        if not isinstance(self.target_user_id, str) or not self.target_user_id:
            frappe.throw(_("Target User is required."), frappe.ValidationError)
        if int(self.source_version or 0) < 1:
            frappe.throw(_("Source Version is invalid."), frappe.ValidationError)
        if self.status not in _STATUS:
            frappe.throw(_("Status is invalid."), frappe.ValidationError)
        if int(self.attempt_count or 0) < 0:
            frappe.throw(_("Attempt Count is invalid."), frappe.ValidationError)
        try:
            event = json.loads(self.event_json)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise frappe.ValidationError(_("Event JSON is invalid.")) from error
        if (
            not isinstance(event, dict)
            or canonical_json(event) != self.event_json
            or canonical_hash(event) != self.event_hash
            or event.get("eventId") != self.event_id
            or event.get("targetUserId") != self.target_user_id
            or event.get("sourceVersion") != int(self.source_version)
            or event.get("traceId") != self.trace_id
        ):
            frappe.throw(_("Authorization delivery event binding is invalid."), frappe.ValidationError)

    def on_trash(self) -> None:
        deny_delivery_delete()


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
