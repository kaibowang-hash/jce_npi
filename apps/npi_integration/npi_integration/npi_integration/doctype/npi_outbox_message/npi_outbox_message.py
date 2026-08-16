from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    actor_text,
    assert_immutable_fields,
    canonical_json,
    canonical_uuid,
    frappe_utc_datetime_text,
    json_object,
    lowercase_sha256,
    nonnegative_integer,
    positive_integer,
    required_text,
    tenant_text,
    utc_datetime_text,
)
from npi_integration.item_publish.domain import (
    ITEM_PUBLISH_OPERATION,
    ITEM_PUBLISH_SCHEMA_VERSION,
    ITEM_REQUEST_EVENT_TYPE,
    canonical_hash,
)
from npi_integration.item_publish.frappe_validation import (
    deny_item_history_delete,
    deny_item_history_update,
    deny_legacy_outbox_promotion,
    require_item_outbox_write,
    validate_one_way_transition,
)


_ITEM_STATES = {
    "pending": frozenset({"processing", "failed_final"}),
    "processing": frozenset(
        {"pending", "succeeded", "failed_retryable", "failed_final", "uncertain"}
    ),
    "failed_retryable": frozenset(),
    "succeeded": frozenset(),
    "failed_final": frozenset(),
    "uncertain": frozenset(),
}
_ITEM_TERMINAL_STATES = frozenset(
    {"succeeded", "failed_retryable", "failed_final", "uncertain"}
)
_V1_FIELDS = (
    "schema_version",
    "operation",
    "tenant_id",
    "project_global_id",
    "request_global_id",
    "profile_id",
    "profile_version",
    "profile_snapshot_hash",
    "source_stream_key_hash",
    "source_hash",
    "expected_mapping_version",
    "actor_user_id",
    "request_id",
    "idempotency_key_hash",
    "event_snapshot_hash",
)
_IMMUTABLE_V1_FIELDS = (
    "event_id",
    "event_type",
    "global_id",
    "object_version",
    "trace_id",
    "payload_hash",
    "payload",
    *_V1_FIELDS,
    "expected_target_version",
)


class NPIOutboxMessage(Document):
    """Durable support projection; only version-1 Item rows are executable."""

    def autoname(self) -> None:
        self.event_id = canonical_uuid(self.event_id, _("Event ID"))
        self.name = self.event_id

    def before_insert(self) -> None:
        if self._is_item_v1():
            require_item_outbox_write()

    def before_save(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None and not self._was_item_v1(previous) and self._is_item_v1():
            deny_legacy_outbox_promotion()
        if self._is_item_v1() or (previous is not None and self._was_item_v1(previous)):
            require_item_outbox_write()
        if previous is not None and self._was_item_v1(previous):
            if previous.state in _ITEM_TERMINAL_STATES:
                deny_item_history_update()

    def before_validate(self) -> None:
        if not self._is_item_v1():
            return
        for fieldname, label in (
            ("event_id", _("Event ID")),
            ("global_id", _("Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("request_global_id", _("Item Publish Request")),
            ("request_id", _("Request ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.tenant_id = tenant_text(self.tenant_id)
        self.actor_user_id = actor_text(self.actor_user_id, _("Actor User ID"))
        if self.claim_token:
            self.claim_token = canonical_uuid(
                self.claim_token, _("Item Outbox Claim Token")
            )
        if self.last_attempt_global_id:
            self.last_attempt_global_id = canonical_uuid(
                self.last_attempt_global_id, _("Last Item Publish Attempt")
            )
        if self.result_global_id:
            self.result_global_id = canonical_uuid(
                self.result_global_id, _("Item Publish Result")
            )

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None and not self._was_item_v1(previous):
            if self._is_item_v1() or any(getattr(self, fieldname, None) for fieldname in _V1_FIELDS):
                deny_legacy_outbox_promotion()
            return
        if not self._is_item_v1():
            return
        if previous is not None:
            if previous.state in _ITEM_TERMINAL_STATES:
                deny_item_history_update()
            assert_immutable_fields(self, previous, _IMMUTABLE_V1_FIELDS)
            validate_one_way_transition(
                previous.state,
                self.state,
                allowed=_ITEM_STATES,
                label=_("Item Outbox Message"),
            )
            if int(self.attempt_count or 0) < int(previous.attempt_count or 0):
                frappe.throw(
                    _("Item Outbox attempt count cannot decrease."),
                    frappe.ValidationError,
                )
            if bool(previous.adapter_boundary_crossed) and not bool(
                self.adapter_boundary_crossed
            ):
                frappe.throw(
                    _("The adapter boundary cannot be cleared after it is crossed."),
                    frappe.ValidationError,
                )
        if (
            positive_integer(self.schema_version, _("Schema Version"))
            != ITEM_PUBLISH_SCHEMA_VERSION
            or self.event_type != ITEM_REQUEST_EVENT_TYPE
            or self.operation != ITEM_PUBLISH_OPERATION
            or positive_integer(self.object_version, _("Object Version")) != 1
        ):
            frappe.throw(
                _("The Item Outbox envelope version or operation is invalid."),
                frappe.ValidationError,
            )
        self.trace_id = required_text(self.trace_id, _("Trace ID"), 128)
        self.profile_id = required_text(
            self.profile_id, _("Item Execution Profile ID"), 128
        )
        self.profile_version = positive_integer(
            self.profile_version, _("Item Execution Profile Version")
        )
        self.expected_mapping_version = nonnegative_integer(
            self.expected_mapping_version, _("Expected Item Mapping Version")
        )
        for fieldname, label in (
            ("profile_snapshot_hash", _("Item Execution Profile Snapshot Hash")),
            ("source_stream_key_hash", _("Item Source Stream Key Hash")),
            ("source_hash", _("Item Source Hash")),
            ("idempotency_key_hash", _("Idempotency Key Hash")),
            ("payload_hash", _("Payload Hash")),
        ):
            setattr(self, fieldname, lowercase_sha256(getattr(self, fieldname), label))
        payload = json_object(self.payload, _("Payload"))
        if canonical_hash(payload) != self.payload_hash:
            frappe.throw(
                _("The Item Outbox payload hash does not match its exact fields."),
                frappe.ValidationError,
            )
        expected_event_hash = canonical_hash(
            {
                "schemaVersion": 1,
                "eventId": self.event_id,
                "eventType": self.event_type,
                "globalId": self.global_id,
                "objectVersion": 1,
                "tenantId": self.tenant_id,
                "projectGlobalId": self.project_global_id,
                "requestGlobalId": self.request_global_id,
                "operation": self.operation,
                "profileId": self.profile_id,
                "profileVersion": self.profile_version,
                "profileSnapshotHash": self.profile_snapshot_hash,
                "sourceStreamKeyHash": self.source_stream_key_hash,
                "sourceHash": self.source_hash,
                "expectedMappingVersion": self.expected_mapping_version,
                "expectedTargetVersion": self.expected_target_version or None,
                "actorUserId": self.actor_user_id,
                "requestId": self.request_id,
                "traceId": self.trace_id,
                "idempotencyKeyHash": self.idempotency_key_hash,
                "payloadHash": self.payload_hash,
            }
        )
        if lowercase_sha256(
            self.event_snapshot_hash, _("Item Outbox Event Snapshot Hash")
        ) != expected_event_hash:
            frappe.throw(
                _("The Item Outbox event snapshot hash does not match its fields."),
                frappe.ValidationError,
            )
        self.payload = canonical_json(payload)
        self.attempt_count = nonnegative_integer(
            self.attempt_count or 0, _("Attempt Count")
        )
        self._validate_state_shape()

    def on_trash(self) -> None:
        deny_item_history_delete()

    def _is_item_v1(self) -> bool:
        return int(self.schema_version or 0) == 1 or self.event_type == ITEM_REQUEST_EVENT_TYPE

    @staticmethod
    def _was_item_v1(document: object) -> bool:
        return int(getattr(document, "schema_version", 0) or 0) == 1 or getattr(
            document, "event_type", None
        ) == ITEM_REQUEST_EVENT_TYPE

    def _validate_state_shape(self) -> None:
        claim_values = (self.claim_token, self.claimed_at, self.lease_expires_at)
        if any(claim_values) != all(claim_values):
            frappe.throw(
                _("Item Outbox claim fields must be present together."),
                frappe.ValidationError,
            )
        if self.claimed_at:
            claimed_at = utc_datetime_text(self.claimed_at, _("Claimed At"))
            expires_at = utc_datetime_text(
                self.lease_expires_at, _("Lease Expires At")
            )
            if expires_at <= claimed_at:
                frappe.throw(
                    _("Item Outbox lease expiry must follow claim time."),
                    frappe.ValidationError,
                )
            self.claimed_at = frappe_utc_datetime_text(claimed_at, _("Claimed At"))
            self.lease_expires_at = frappe_utc_datetime_text(
                expires_at, _("Lease Expires At")
            )
        if self.state == "pending" and any(claim_values):
            frappe.throw(
                _("A pending Item Outbox message cannot retain a live claim."),
                frappe.ValidationError,
            )
        if self.state == "pending" and self.adapter_boundary_crossed:
            frappe.throw(
                _("An Item Outbox message cannot return to pending after the adapter boundary."),
                frappe.ValidationError,
            )
        if self.state == "processing" and not all(claim_values):
            frappe.throw(
                _("A processing Item Outbox message requires an exact claim."),
                frappe.ValidationError,
            )
        terminal = self.state in _ITEM_TERMINAL_STATES
        if terminal and not self.result_global_id:
            frappe.throw(
                _("A terminal Item Outbox message requires an exact result."),
                frappe.ValidationError,
            )
        if not terminal and self.result_global_id:
            frappe.throw(
                _("A non-terminal Item Outbox message cannot reference a terminal result."),
                frappe.ValidationError,
            )
        if self.state == "uncertain" and not self.adapter_boundary_crossed:
            frappe.throw(
                _("An uncertain Item Outbox message requires a crossed adapter boundary."),
                frappe.ValidationError,
            )
        if self.last_error_at:
            self.last_error_at = frappe_utc_datetime_text(
                utc_datetime_text(self.last_error_at, _("Last Error At")),
                _("Last Error At"),
            )
