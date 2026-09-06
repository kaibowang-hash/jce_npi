from __future__ import annotations

import re
from uuid import UUID

import frappe
from frappe import _
from frappe.model.document import Document

from npi_erpnext_connector.master_data_domain import (
    MasterCatalogKind,
    restore_event,
)
from npi_erpnext_connector.master_data_validation import (
    deny_master_data_delivery_delete,
    require_master_data_delivery_write,
)


_HASH = re.compile(r"^[a-f0-9]{64}$")
_STATUS = {"pending", "retry", "delivered", "permanent_failure"}
_IMMUTABLE = (
    "event_id",
    "stream_key",
    "catalog_kind",
    "source_version",
    "source_snapshot_hash",
    "event_hash",
    "event_json",
    "request_id",
    "trace_id",
    "record_count",
)


class NPIERPMasterDataDelivery(Document):
    def autoname(self) -> None:
        self.event_id = _uuid(self.event_id, _("Event ID"))
        self.name = self.event_id

    def before_insert(self) -> None:
        require_master_data_delivery_write()

    def before_save(self) -> None:
        require_master_data_delivery_write()

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous:
            for fieldname in _IMMUTABLE:
                if getattr(previous, fieldname, None) != getattr(self, fieldname, None):
                    frappe.throw(
                        _("Master data delivery source fields are immutable."),
                        frappe.ValidationError,
                    )
            if previous.status == "delivered" and self.status != previous.status:
                frappe.throw(
                    _("A completed master data delivery cannot be changed."),
                    frappe.ValidationError,
                )
            if previous.status == "permanent_failure" and self.status not in {
                "permanent_failure",
                "retry",
            }:
                frappe.throw(
                    _("A failed master data delivery transition is invalid."),
                    frappe.ValidationError,
                )
        self.event_id = _uuid(self.event_id, _("Event ID"))
        self.request_id = _uuid(self.request_id, _("Request ID"))
        self.stream_key = _hash(self.stream_key, _("Stream Key"))
        self.source_snapshot_hash = _hash(
            self.source_snapshot_hash, _("Source Snapshot Hash")
        )
        self.event_hash = _hash(self.event_hash, _("Event Hash"))
        try:
            kind = MasterCatalogKind(self.catalog_kind)
        except ValueError as error:
            raise frappe.ValidationError(_("Master catalog type is invalid.")) from error
        if int(self.source_version or 0) < 1:
            frappe.throw(_("Source Version is invalid."), frappe.ValidationError)
        if int(self.record_count or -1) < 0:
            frappe.throw(_("Master data record count is invalid."), frappe.ValidationError)
        if self.status not in _STATUS or int(self.attempt_count or 0) < 0:
            frappe.throw(_("Master data delivery state is invalid."), frappe.ValidationError)
        event = restore_event(
            self.event_json,
            request_id=self.request_id,
            source_snapshot_hash=self.source_snapshot_hash,
            event_hash=self.event_hash,
        )
        if (
            event.kind is not kind
            or event.source_version != int(self.source_version)
            or event.trace_id != self.trace_id
            or len(event.event["records"]) != int(self.record_count)
        ):
            frappe.throw(
                _("Master data delivery event binding is invalid."),
                frappe.ValidationError,
            )
        if self.target_snapshot_id:
            self.target_snapshot_id = _uuid(
                self.target_snapshot_id, _("Target Master Snapshot ID")
            )
        if self.response_payload_hash:
            self.response_payload_hash = _hash(
                self.response_payload_hash, _("Response Payload Hash")
            )
        if self.status == "delivered" and (
            not self.target_snapshot_id
            or self.response_payload_hash != event.payload_hash
        ):
            frappe.throw(
                _("Completed master data delivery is incomplete."),
                frappe.ValidationError,
            )

    def on_trash(self) -> None:
        deny_master_data_delivery_delete()


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
