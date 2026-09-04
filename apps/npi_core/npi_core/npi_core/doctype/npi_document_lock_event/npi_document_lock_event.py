from __future__ import annotations

from datetime import UTC, datetime

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.domain import (
    DocumentEditLock,
    DocumentLockState,
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
    frappe_utc_datetime_text,
    json_object,
    optional_uuid,
    required_text,
    require_exact_parent,
    require_document_command_write,
    tenant_text,
)


_ALL_FIELDS = (
    "global_id",
    "event_key",
    "tenant_id",
    "project_global_id",
    "controlled_document",
    "document_global_id",
    "lock_global_id",
    "lock_version",
    "event_type",
    "holder_user_id",
    "acquired_at",
    "expires_at",
    "actor_user_id",
    "occurred_at",
    "prior_event_global_id",
    "closure_reason",
    "request_id",
    "trace_id",
    "event_snapshot",
    "snapshot_hash",
)
_STATE_BY_EVENT = {
    "acquired": DocumentLockState.ACTIVE,
    "released": DocumentLockState.RELEASED,
    "recovered": DocumentLockState.RECOVERED,
    "expired": DocumentLockState.EXPIRED,
}


class NPIDocumentLockEvent(Document):
    """Frozen acquisition or terminal event for one edit lease."""

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
        self.lock_global_id = canonical_uuid(
            self.lock_global_id,
            _("Lock Global ID"),
        )
        self.prior_event_global_id = optional_uuid(
            self.prior_event_global_id,
            _("Prior Lock Event Global ID"),
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
            _("The lock event does not match its controlled document."),
        )
        state = _STATE_BY_EVENT.get(str(self.event_type))
        if state is None:
            frappe.throw(
                _("Select a supported document lock event type."),
                frappe.ValidationError,
            )
        if (self.event_type == "acquired" and self.lock_version != 1) or (
            self.event_type != "acquired" and self.lock_version != 2
        ):
            frappe.throw(
                _("Lock Version does not match the lock event type."),
                frappe.ValidationError,
            )
        actor = actor_text(self.actor_user_id, _("Actor"))
        occurred_at = _as_utc_datetime(self.occurred_at)
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
        lock = document_domain_value(
            lambda: DocumentEditLock(
                global_id=self.lock_global_id,
                document_global_id=self.document_global_id,
                version=self.lock_version,
                holder_user_id=self.holder_user_id,
                acquired_at=_as_utc_datetime(self.acquired_at),
                expires_at=_as_utc_datetime(self.expires_at),
                state=state,
                closed_at=(None if state is DocumentLockState.ACTIVE else occurred_at),
                closed_by=None if state is DocumentLockState.ACTIVE else actor,
                reason=self.closure_reason or None,
            )
        )
        if state is DocumentLockState.ACTIVE:
            if (
                actor.casefold() != lock.holder_user_id.casefold()
                or occurred_at != lock.acquired_at
                or self.prior_event_global_id is not None
            ):
                frappe.throw(
                    _("The lock acquisition event is invalid."),
                    frappe.ValidationError,
                )
        else:
            if self.prior_event_global_id is None:
                frappe.throw(
                    _("A terminal lock event requires its exact acquisition event."),
                    frappe.ValidationError,
                )
            require_exact_parent(
                "NPI Document Lock Event",
                self.prior_event_global_id,
                {
                    "global_id": self.prior_event_global_id,
                    "tenant_id": self.tenant_id,
                    "project_global_id": self.project_global_id,
                    "document_global_id": self.document_global_id,
                    "lock_global_id": self.lock_global_id,
                    "lock_version": 1,
                    "event_type": "acquired",
                    "holder_user_id": lock.holder_user_id,
                    "acquired_at": self.acquired_at,
                    "expires_at": self.expires_at,
                },
                _("The terminal lock event does not match its acquisition event."),
            )
            if state is DocumentLockState.RELEASED and (
                actor.casefold() != lock.holder_user_id.casefold()
                or occurred_at > lock.expires_at
            ):
                frappe.throw(
                    _("Only the current holder can release an unexpired edit lock."),
                    frappe.ValidationError,
                )
            if state is DocumentLockState.EXPIRED and occurred_at < lock.expires_at:
                frappe.throw(
                    _("An edit lock cannot expire before its expiry time."),
                    frappe.ValidationError,
                )
        expected_event_key = f"{lock.global_id}:{lock.version}"
        if self.event_key not in (None, "", expected_event_key):
            frappe.throw(
                _("Lock Event Key does not match the exact lock version."),
                frappe.ValidationError,
            )
        snapshot = {
            "schemaVersion": 1,
            "globalId": self.global_id,
            "tenantId": self.tenant_id,
            "projectGlobalId": self.project_global_id,
            "documentGlobalId": self.document_global_id,
            "lockGlobalId": str(lock.global_id),
            "lockVersion": lock.version,
            "eventType": self.event_type,
            "holderUserId": lock.holder_user_id,
            "acquiredAt": lock.acquired_at.isoformat().replace("+00:00", "Z"),
            "expiresAt": lock.expires_at.isoformat().replace("+00:00", "Z"),
            "actorUserId": actor,
            "occurredAt": occurred_at.isoformat().replace("+00:00", "Z"),
            "priorEventGlobalId": self.prior_event_global_id,
            "closureReason": lock.reason,
            "requestId": self.request_id,
            "traceId": self.trace_id,
        }
        expected_hash = sha256_json(snapshot)
        if (
            json_object(self.event_snapshot, _("Lock Event Snapshot")) != snapshot
            or str(self.snapshot_hash) != expected_hash
        ):
            frappe.throw(
                _("Lock Event Snapshot does not match the exact lock event."),
                frappe.ValidationError,
            )
        self.event_key = expected_event_key
        self.holder_user_id = lock.holder_user_id
        self.acquired_at = frappe_utc_datetime_text(
            lock.acquired_at,
            _("Acquired At"),
        )
        self.expires_at = frappe_utc_datetime_text(
            lock.expires_at,
            _("Expires At"),
        )
        self.actor_user_id = actor
        self.occurred_at = frappe_utc_datetime_text(
            occurred_at,
            _("Occurred At"),
        )
        self.closure_reason = lock.reason
        self.event_snapshot = canonical_json(snapshot)
        self.snapshot_hash = expected_hash

    def on_trash(self) -> None:
        deny_document_history_delete(
            self,
            target_global_id=self.global_id,
            target_version=self.lock_version,
        )


def _as_utc_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError) as error:
            frappe.throw(
                _("Enter a valid date and time."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
