from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    assert_immutable_fields,
    canonical_uuid,
    frappe_utc_datetime_text,
    lowercase_sha256,
    positive_integer,
    required_text,
    tenant_text,
    utc_datetime_text,
)
from npi_integration.item_publish.domain import (
    ITEM_PUBLISH_SCHEMA_VERSION,
    ItemPublishRequestState,
    canonical_hash,
)
from npi_integration.item_publish.frappe_validation import (
    deny_item_history_delete,
    require_item_stream_guard_write,
)


_IMMUTABLE_IDENTITY_FIELDS = (
    "source_stream_key_hash",
    "tenant_id",
    "project_global_id",
    "engineering_item_id",
)
_ACTIVE_STATES = frozenset(
    {
        ItemPublishRequestState.QUEUED.value,
        ItemPublishRequestState.PROCESSING.value,
        ItemPublishRequestState.FAILED_RETRYABLE.value,
        ItemPublishRequestState.UNCERTAIN_AFTER_TIMEOUT.value,
        ItemPublishRequestState.MAPPING_CONFLICT.value,
    }
)
_LAST_STATES = frozenset(
    {
        ItemPublishRequestState.SYNTHETIC_VERIFIED.value,
        ItemPublishRequestState.SUCCEEDED.value,
        ItemPublishRequestState.FAILED_RETRYABLE.value,
        ItemPublishRequestState.FAILED_FINAL.value,
        ItemPublishRequestState.UNCERTAIN_AFTER_TIMEOUT.value,
        ItemPublishRequestState.MAPPING_CONFLICT.value,
    }
)


class NPIItemPublishStreamGuard(Document):
    """One durable serialization row for one Item source stream."""

    def autoname(self) -> None:
        self.source_stream_key_hash = lowercase_sha256(
            self.source_stream_key_hash, _("Item Source Stream Key Hash")
        )
        self.name = self.source_stream_key_hash

    def before_insert(self) -> None:
        require_item_stream_guard_write()

    def before_save(self) -> None:
        require_item_stream_guard_write()

    def before_validate(self) -> None:
        self.project_global_id = canonical_uuid(
            self.project_global_id, _("Project Global ID")
        )
        for fieldname, label in (
            ("active_request_global_id", _("Active Item Publish Request")),
            ("last_request_global_id", _("Last Item Publish Request")),
        ):
            if getattr(self, fieldname, None):
                setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _IMMUTABLE_IDENTITY_FIELDS)
            expected_version = int(previous.optimistic_version or 0) + 1
        else:
            expected_version = 1

        self.engineering_item_id = required_text(
            self.engineering_item_id, _("Engineering Item ID"), 128
        )
        self.source_stream_key_hash = lowercase_sha256(
            self.source_stream_key_hash, _("Item Source Stream Key Hash")
        )
        expected_hash = canonical_hash(
            {
                "schemaVersion": ITEM_PUBLISH_SCHEMA_VERSION,
                "tenantId": self.tenant_id,
                "projectGlobalId": self.project_global_id,
                "engineeringItemId": self.engineering_item_id,
            }
        )
        if self.source_stream_key_hash != expected_hash:
            frappe.throw(
                _("The Item source stream key hash does not match its identity."),
                frappe.ValidationError,
            )
        self.optimistic_version = positive_integer(
            self.optimistic_version, _("Optimistic Version")
        )
        if self.optimistic_version != expected_version:
            frappe.throw(
                _("The Item source stream guard version must advance by one."),
                frappe.ValidationError,
            )
        self._validate_binding(
            request_field="active_request_global_id",
            key_field="active_target_idempotency_key_hash",
            state_field="active_state",
            states=_ACTIVE_STATES,
            label=_("Active Item Publish binding"),
        )
        self._validate_binding(
            request_field="last_request_global_id",
            key_field="last_target_idempotency_key_hash",
            state_field="last_state",
            states=_LAST_STATES,
            label=_("Last Item Publish binding"),
        )
        if self.blocked_reason_code:
            self.blocked_reason_code = required_text(
                self.blocked_reason_code, _("Blocked Reason Code"), 120
            )
        updated_at = utc_datetime_text(self.updated_at, _("Updated At"))
        self.updated_at = frappe_utc_datetime_text(updated_at, _("Updated At"))

    def on_trash(self) -> None:
        deny_item_history_delete()

    def _validate_binding(
        self,
        *,
        request_field: str,
        key_field: str,
        state_field: str,
        states: frozenset[str],
        label: str,
    ) -> None:
        request_id = getattr(self, request_field, None)
        key_hash = getattr(self, key_field, None)
        state = getattr(self, state_field, None)
        populated = bool(request_id or key_hash or state)
        if not populated:
            return
        if not (request_id and key_hash and state):
            frappe.throw(
                _("{label} must contain request, target key, and state.").format(label=label),
                frappe.ValidationError,
            )
        if state not in states:
            frappe.throw(
                _("{label} contains an invalid state.").format(label=label),
                frappe.ValidationError,
            )
        setattr(
            self,
            key_field,
            lowercase_sha256(key_hash, _("Target Idempotency Key Hash")),
        )
