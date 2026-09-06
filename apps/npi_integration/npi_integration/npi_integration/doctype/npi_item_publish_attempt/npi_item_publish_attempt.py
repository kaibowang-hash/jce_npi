from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    assert_immutable_fields,
    canonical_json,
    canonical_uuid,
    frappe_utc_datetime_text,
    json_object,
    lowercase_sha256,
    nonnegative_integer,
    positive_integer,
    required_text,
    utc_datetime_text,
)
from npi_integration.item_publish.domain import ItemPublishAttemptState, canonical_hash
from npi_integration.item_publish.frappe_validation import (
    deny_item_history_delete,
    deny_item_history_update,
    require_item_attempt_write,
    validate_one_way_transition,
)


_ATTEMPT_TRANSITIONS = {
    "started": frozenset(
        {"synthetic_verified", "observed_success", "observed_failure", "uncertain"}
    ),
    "synthetic_verified": frozenset(),
    "observed_success": frozenset(),
    "observed_failure": frozenset(),
    "uncertain": frozenset(),
}
_IMMUTABLE_FIELDS = (
    "global_id",
    "request_global_id",
    "outbox_event_id",
    "attempt_number",
    "claim_token",
    "target_idempotency_key_hash",
    "source_hash",
    "profile_id",
    "profile_version",
    "request_snapshot",
    "request_snapshot_hash",
    "started_at",
)


class NPIItemPublishAttempt(Document):
    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_item_attempt_write()

    def before_save(self) -> None:
        require_item_attempt_write()
        previous = self.get_doc_before_save()
        if previous is not None and previous.state != ItemPublishAttemptState.STARTED.value:
            deny_item_history_update()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("request_global_id", _("Item Publish Request")),
            ("outbox_event_id", _("Item Outbox Event ID")),
            ("claim_token", _("Item Outbox Claim Token")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            if previous.state != ItemPublishAttemptState.STARTED.value:
                deny_item_history_update()
            assert_immutable_fields(self, previous, _IMMUTABLE_FIELDS)
            # Frappe represents an unset Int as zero.  A claim starts without
            # adapter timeout evidence; the boundary seal is the one guarded
            # transition that records the profile timeouts.  Once populated,
            # those values remain immutable like the other attempt inputs.
            for fieldname in (
                "connect_timeout_seconds",
                "read_timeout_seconds",
            ):
                previous_value = getattr(previous, fieldname)
                if previous_value not in (None, "", 0) and getattr(
                    self, fieldname
                ) != previous_value:
                    deny_item_history_update()
            validate_one_way_transition(
                previous.state,
                self.state,
                allowed=_ATTEMPT_TRANSITIONS,
                label=_("Item Publish Attempt"),
            )
            if bool(previous.adapter_boundary_crossed) and not bool(
                self.adapter_boundary_crossed
            ):
                frappe.throw(
                    _("The adapter boundary cannot be cleared after it is crossed."),
                    frappe.ValidationError,
                )
        try:
            state = ItemPublishAttemptState(self.state)
        except ValueError as error:
            frappe.throw(
                _("The Item publish attempt state is invalid."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.") from error
        if previous is None and state is not ItemPublishAttemptState.STARTED:
            frappe.throw(
                _("A new Item publish attempt must start before adapter execution."),
                frappe.ValidationError,
            )
        self.attempt_number = positive_integer(
            self.attempt_number, _("Item Publish Attempt Number")
        )
        self.profile_version = positive_integer(
            self.profile_version, _("Item Execution Profile Version")
        )
        self.profile_id = required_text(
            self.profile_id, _("Item Execution Profile ID"), 128
        )
        for fieldname, label in (
            ("target_idempotency_key_hash", _("Target Idempotency Key Hash")),
            ("source_hash", _("Item Source Hash")),
            ("request_snapshot_hash", _("Adapter Request Snapshot Hash")),
            ("attempt_hash", _("Item Publish Attempt Hash")),
        ):
            setattr(self, fieldname, lowercase_sha256(getattr(self, fieldname), label))
        request_snapshot = json_object(
            self.request_snapshot, _("Exact Adapter Request Snapshot")
        )
        if canonical_hash(request_snapshot) != self.request_snapshot_hash:
            frappe.throw(
                _("The adapter request snapshot hash does not match its fields."),
                frappe.ValidationError,
            )
        if request_snapshot.get("requestGlobalId") != self.request_global_id:
            frappe.throw(
                _("The adapter request snapshot does not match its Item request."),
                frappe.ValidationError,
            )
        for fieldname, label in (
            ("connect_timeout_seconds", _("Connect Timeout Seconds")),
            ("read_timeout_seconds", _("Read Timeout Seconds")),
        ):
            value = getattr(self, fieldname)
            # Frappe persists an unset Int field as zero.  Adapter timeouts
            # are intentionally absent until the durable boundary is crossed,
            # so the stored zero must retain the same unset semantics as None.
            if value not in (None, "", 0):
                value = positive_integer(value, label)
                if value > 120:
                    frappe.throw(
                        _("Item publish adapter timeouts cannot exceed 120 seconds."),
                        frappe.ValidationError,
                    )
                setattr(self, fieldname, value)
        terminal = state is not ItemPublishAttemptState.STARTED
        if terminal != bool(self.finished_at):
            frappe.throw(
                _("Item publish attempt completion time must match its terminal state."),
                frappe.ValidationError,
            )
        if state is ItemPublishAttemptState.UNCERTAIN and (
            not self.adapter_boundary_crossed or not self.reconciliation_required
        ):
            frappe.throw(
                _("An uncertain Item publish attempt requires reconciliation after the adapter boundary."),
                frappe.ValidationError,
            )
        if state is ItemPublishAttemptState.OBSERVED_SUCCESS and not self.adapter_boundary_crossed:
            frappe.throw(
                _("Observed Item success requires a crossed adapter boundary."),
                frappe.ValidationError,
            )
        # ``target_status_code`` is also an optional Int and therefore loads as
        # zero from MariaDB before an adapter response has been observed.
        if self.target_status_code not in (None, "", 0):
            status = nonnegative_integer(
                self.target_status_code, _("Target Status Code")
            )
            if not 100 <= status <= 599:
                frappe.throw(
                    _("The target status code is invalid."),
                    frappe.ValidationError,
                )
        if self.response_hash:
            self.response_hash = lowercase_sha256(
                self.response_hash, _("Target Response Hash")
            )
        if self.safe_error_code:
            self.safe_error_code = required_text(
                self.safe_error_code, _("Safe Error Code"), 100
            )
        if self.transport_disposition:
            self.transport_disposition = required_text(
                self.transport_disposition, _("Transport Disposition"), 100
            )
        if self.fault_kind:
            self.fault_kind = required_text(
                self.fault_kind, _("Item Publish Fault Kind"), 100
            )
        attempt_snapshot = json_object(
            self.attempt_snapshot, _("Item Publish Attempt Snapshot")
        )
        if canonical_hash(attempt_snapshot) != self.attempt_hash:
            frappe.throw(
                _("The Item publish attempt hash does not match its snapshot."),
                frappe.ValidationError,
            )
        if (
            attempt_snapshot.get("globalId") != self.global_id
            or attempt_snapshot.get("requestGlobalId") != self.request_global_id
            or attempt_snapshot.get("state") != state.value
            or attempt_snapshot.get("adapterBoundaryCrossed")
            is not bool(self.adapter_boundary_crossed)
        ):
            frappe.throw(
                _("The Item publish attempt snapshot does not match its fields."),
                frappe.ValidationError,
            )
        self.request_snapshot = canonical_json(request_snapshot)
        self.attempt_snapshot = canonical_json(attempt_snapshot)
        self.started_at = frappe_utc_datetime_text(
            utc_datetime_text(self.started_at, _("Started At")), _("Started At")
        )
        if self.finished_at:
            self.finished_at = frappe_utc_datetime_text(
                utc_datetime_text(self.finished_at, _("Finished At")),
                _("Finished At"),
            )

    def on_trash(self) -> None:
        deny_item_history_delete()
