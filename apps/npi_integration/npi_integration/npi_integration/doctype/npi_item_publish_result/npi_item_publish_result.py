from __future__ import annotations

from datetime import UTC, datetime

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    canonical_json,
    canonical_uuid,
    frappe_utc_datetime_text,
    json_object,
    lowercase_sha256,
    positive_integer,
    utc_datetime_text,
)
from npi_integration.item_publish.domain import (
    ItemAdapterObservation,
    ItemFaultKind,
    ItemPublishContractError,
    ItemPublishResultState,
    ItemResultAuthority,
    canonical_hash,
)
from npi_integration.item_publish.frappe_validation import (
    deny_item_history_delete,
    deny_item_history_update,
    require_item_result_write,
)


class NPIItemPublishResult(Document):
    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_item_result_write()

    def before_save(self) -> None:
        require_item_result_write()
        if self.get_doc_before_save() is not None:
            deny_item_history_update()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("request_global_id", _("Item Publish Request")),
            ("outbox_event_id", _("Item Outbox Event ID")),
            ("attempt_global_id", _("Item Publish Attempt")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_item_history_update()
        for fieldname, label in (
            ("idempotency_key_hash", _("Idempotency Key Hash")),
            ("source_hash", _("Item Source Hash")),
            ("response_hash", _("Target Response Hash")),
            ("result_hash", _("Item Publish Result Hash")),
        ):
            setattr(self, fieldname, lowercase_sha256(getattr(self, fieldname), label))
        observed_at = utc_datetime_text(self.observed_at, _("Observed At"))
        try:
            observation = ItemAdapterObservation(
                request_global_id=self.request_global_id,
                attempt_global_id=self.attempt_global_id,
                attempt_number=positive_integer(
                    self.attempt_number, _("Item Publish Attempt Number")
                ),
                idempotency_key_hash=self.idempotency_key_hash,
                source_hash=self.source_hash,
                expected_target_version=self.expected_target_version or None,
                state=ItemPublishResultState(self.state),
                authority=ItemResultAuthority(self.authority),
                response_authenticated=bool(self.response_authenticated),
                response_hash=self.response_hash,
                observed_at=datetime.fromisoformat(
                    observed_at.replace("Z", "+00:00")
                ).astimezone(UTC),
                formal_item_code=self.formal_item_code or None,
                target_version=self.target_version or None,
                fault_kind=ItemFaultKind(self.fault_kind),
            )
        except (ItemPublishContractError, ValueError, TypeError) as error:
            frappe.throw(
                _("The Item publish result authority or target truth is invalid."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.") from error
        expected_snapshot = {
            "schemaVersion": 1,
            "globalId": self.global_id,
            "requestGlobalId": self.request_global_id,
            "outboxEventId": self.outbox_event_id,
            "attemptGlobalId": self.attempt_global_id,
            "attemptNumber": observation.attempt_number,
            "idempotencyKeyHash": observation.idempotency_key_hash,
            "sourceHash": observation.source_hash,
            "expectedTargetVersion": observation.expected_target_version,
            "state": observation.state.value,
            "authority": observation.authority.value,
            "responseAuthenticated": observation.response_authenticated,
            "responseHash": observation.response_hash,
            "formalItemCode": observation.formal_item_code,
            "targetVersion": observation.target_version,
            "faultKind": observation.fault_kind.value,
            "observedAt": observed_at,
        }
        snapshot = json_object(
            self.result_snapshot, _("Item Publish Result Snapshot")
        )
        if snapshot != expected_snapshot:
            frappe.throw(
                _("The Item publish result snapshot does not match its fields."),
                frappe.ValidationError,
            )
        self.result_snapshot = canonical_json(expected_snapshot)
        if canonical_hash(expected_snapshot) != self.result_hash:
            frappe.throw(
                _("The Item publish result hash does not match its snapshot."),
                frappe.ValidationError,
            )
        self.observed_at = frappe_utc_datetime_text(observed_at, _("Observed At"))

    def on_trash(self) -> None:
        deny_item_history_delete()
