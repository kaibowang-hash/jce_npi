from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_integration.trial_summary_publish.domain import (
    EVENT_TYPE,
    MAX_ATTEMPTS,
    TrialSummaryDeliveryError,
    canonical_hash,
    parse_uuid,
    valid_hash,
    validate_persisted_source,
)
from npi_integration.trial_summary_publish.frappe_validation import (
    deny_delivery_delete,
    require_delivery_write,
)

_STATES = frozenset(
    {"pending", "processing", "succeeded", "failed_retryable", "failed_final", "uncertain"}
)
_TRANSITIONS = {
    "pending": frozenset({"processing"}),
    "processing": frozenset(
        {"succeeded", "failed_retryable", "failed_final", "uncertain", "pending"}
    ),
    "failed_retryable": frozenset({"pending", "processing"}),
    "failed_final": frozenset({"pending"}),
    "uncertain": frozenset({"processing"}),
    "succeeded": frozenset(),
}
_IMMUTABLE = (
    "global_id",
    "event_type",
    "tenant_id",
    "project_global_id",
    "trial_plan_global_id",
    "trial_round_global_id",
    "summary_global_id",
    "summary_revision_global_id",
    "summary_version",
    "source_snapshot",
    "source_hash",
    "source_snapshot_hash",
    "target_idempotency_key_hash",
    "actor_user_id",
    "trace_id",
    "created_at",
)


class NPITrialSummaryDelivery(Document):
    def autoname(self) -> None:
        self.global_id = _uuid(self.global_id, _("Delivery Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_delivery_write()

    def before_save(self) -> None:
        require_delivery_write()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Delivery Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("trial_plan_global_id", _("Trial Plan Global ID")),
            ("trial_round_global_id", _("Trial Round Global ID")),
            ("summary_global_id", _("Trial Summary Global ID")),
            ("summary_revision_global_id", _("Trial Summary Revision Global ID")),
        ):
            setattr(self, fieldname, _uuid(getattr(self, fieldname), label))
        if self.claim_token:
            self.claim_token = _uuid(
                self.claim_token,
                _("Trial Summary Delivery Claim Token"),
            )
        if self.last_attempt_global_id:
            self.last_attempt_global_id = _uuid(
                self.last_attempt_global_id,
                _("Last Trial Summary Delivery Attempt"),
            )

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            for fieldname in _IMMUTABLE:
                if getattr(previous, fieldname, None) != getattr(self, fieldname, None):
                    frappe.throw(
                        _("Trial Summary delivery source fields are immutable."),
                        frappe.ValidationError,
                    )
            if bool(previous.profile_snapshot_hash) and any(
                getattr(previous, fieldname, None) != getattr(self, fieldname, None)
                for fieldname in (
                    "profile_id",
                    "profile_version",
                    "profile_snapshot_hash",
                    "environment_code",
                    "service_actor_user_id",
                )
            ):
                frappe.throw(
                    _("The Trial Summary execution route is immutable after binding."),
                    frappe.ValidationError,
                )
            if (
                previous.state != self.state
                and self.state not in _TRANSITIONS.get(previous.state, frozenset())
            ):
                frappe.throw(
                    _("The Trial Summary delivery transition is invalid."),
                    frappe.ValidationError,
                )
        if self.event_type != EVENT_TYPE or self.state not in _STATES:
            frappe.throw(
                _("The Trial Summary delivery type or state is invalid."),
                frappe.ValidationError,
            )
        if type(self.summary_version) is not int or self.summary_version < 1:
            frappe.throw(_("Trial Summary Version is invalid."), frappe.ValidationError)
        if type(self.attempt_count) is not int or not 0 <= self.attempt_count <= MAX_ATTEMPTS:
            frappe.throw(
                _("Trial Summary Delivery Attempt Count is invalid."),
                frappe.ValidationError,
            )
        for fieldname, label in (
            ("source_hash", _("Trial Summary Delivery Source Hash")),
            ("source_snapshot_hash", _("Source Snapshot Hash")),
            ("target_idempotency_key_hash", _("Target Idempotency Key Hash")),
        ):
            if not valid_hash(getattr(self, fieldname)):
                frappe.throw(_("{field} is invalid.").format(field=label), frappe.ValidationError)
        try:
            source = validate_persisted_source(
                self.source_snapshot,
                source_hash=self.source_hash,
                summary_revision_global_id=self.summary_revision_global_id,
            )
        except TrialSummaryDeliveryError as error:
            raise frappe.ValidationError(
                _("The exact Trial Summary delivery source is invalid.")
            ) from error
        expected_key = canonical_hash(
            {
                "operation": "publish_released_trial_summary",
                "summaryRevisionGlobalId": self.summary_revision_global_id,
            }
        )
        if (
            self.source_snapshot_hash != source.get("sourceSnapshotHash")
            or self.target_idempotency_key_hash != expected_key
        ):
            frappe.throw(
                _("The Trial Summary delivery source binding is invalid."),
                frappe.ValidationError,
            )
        if self.profile_snapshot_hash and not valid_hash(self.profile_snapshot_hash):
            frappe.throw(
                _("Trial Summary Execution Profile Snapshot Hash is invalid."),
                frappe.ValidationError,
            )
        if self.response_hash and not valid_hash(self.response_hash):
            frappe.throw(
                _("ERPNext Trial Summary Response Hash is invalid."),
                frappe.ValidationError,
            )

    def on_trash(self) -> None:
        deny_delivery_delete()


def _uuid(value: object, label: str) -> str:
    try:
        return parse_uuid(value, str(label))
    except TrialSummaryDeliveryError as error:
        raise frappe.ValidationError(_("{field} is invalid.").format(field=label)) from error
