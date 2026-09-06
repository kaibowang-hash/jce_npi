from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_integration.trial_summary_publish.domain import (
    TrialSummaryDeliveryError,
    canonical_hash,
    parse_uuid,
    valid_hash,
)
from npi_integration.trial_summary_publish.frappe_validation import (
    deny_delivery_delete,
    require_delivery_write,
)

_TERMINAL = frozenset(
    {
        "succeeded",
        "failed_retryable",
        "failed_final",
        "uncertain",
        "reconciled_present",
        "reconciled_absent",
    }
)


class NPITrialSummaryDeliveryAttempt(Document):
    def autoname(self) -> None:
        self.global_id = _uuid(self.global_id, _("Attempt Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_delivery_write()

    def before_save(self) -> None:
        require_delivery_write()

    def before_validate(self) -> None:
        self.global_id = _uuid(self.global_id, _("Attempt Global ID"))
        self.delivery_global_id = _uuid(
            self.delivery_global_id,
            _("Trial Summary Delivery"),
        )

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            for fieldname in (
                "global_id",
                "delivery_global_id",
                "attempt_number",
                "attempt_key_hash",
                "attempt_kind",
                "trace_id",
                "started_at",
            ):
                if getattr(previous, fieldname, None) != getattr(self, fieldname, None):
                    frappe.throw(
                        _("Trial Summary attempt identity is immutable."),
                        frappe.ValidationError,
                    )
            if previous.state != "started" or self.state not in (_TERMINAL | {"started"}):
                frappe.throw(
                    _("The Trial Summary attempt transition is invalid."),
                    frappe.ValidationError,
                )
        elif self.state != "started":
            frappe.throw(
                _("A Trial Summary attempt must start before it is completed."),
                frappe.ValidationError,
            )
        if self.attempt_kind not in {"publish", "reconcile"}:
            frappe.throw(
                _("Trial Summary Attempt Kind is invalid."),
                frappe.ValidationError,
            )
        if type(self.attempt_number) is not int or self.attempt_number < 1:
            frappe.throw(_("Attempt Number is invalid."), frappe.ValidationError)
        if not valid_hash(self.attempt_key_hash):
            frappe.throw(_("Attempt Key Hash is invalid."), frappe.ValidationError)
        expected = canonical_hash(
            {
                "deliveryGlobalId": self.delivery_global_id,
                "attemptKind": self.attempt_kind,
                "attemptNumber": self.attempt_number,
            }
        )
        if self.attempt_key_hash != expected:
            frappe.throw(
                _("The Trial Summary attempt key is invalid."),
                frappe.ValidationError,
            )
        if self.response_hash and not valid_hash(self.response_hash):
            frappe.throw(_("Response Hash is invalid."), frappe.ValidationError)

    def on_trash(self) -> None:
        deny_delivery_delete()


def _uuid(value: object, label: str) -> str:
    try:
        return parse_uuid(value, str(label))
    except TrialSummaryDeliveryError as error:
        raise frappe.ValidationError(_("{field} is invalid.").format(field=label)) from error
