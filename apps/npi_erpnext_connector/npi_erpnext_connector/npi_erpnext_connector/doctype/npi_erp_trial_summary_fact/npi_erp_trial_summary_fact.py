from __future__ import annotations

import json
import re
from collections.abc import Sequence
from uuid import UUID

import frappe
from frappe import _
from frappe.model.document import Document

from npi_erpnext_connector.frappe_validation import (
    deny_trial_summary_execution_delete,
    require_trial_summary_execution_write,
)
from npi_erpnext_connector.trial_summary_contract import (
    FACT_GROUPS,
    VALUE_STATES,
    canonical_hash,
    canonical_json,
    fact_type,
)

_HASH = re.compile(r"^[a-f0-9]{64}$")


class NPIERPTrialSummaryFact(Document):
    def autoname(self) -> None:
        self.fact_global_id = _hash(
            self.fact_global_id,
            _("Trial Summary Fact Global ID"),
        )
        self.name = self.fact_global_id

    def before_insert(self) -> None:
        require_trial_summary_execution_write()

    def before_save(self) -> None:
        require_trial_summary_execution_write()
        if self.get_doc_before_save() is not None:
            frappe.throw(
                _("ERPNext Trial Summary facts are immutable."),
                frappe.PermissionError,
            )

    def validate(self) -> None:
        self.fact_global_id = _hash(
            self.fact_global_id,
            _("Trial Summary Fact Global ID"),
        )
        self.source_references_hash = _hash(
            self.source_references_hash,
            _("Trial Summary Fact Source References Hash"),
        )
        for fieldname, label in (
            ("summary_revision_global_id", _("Trial Summary Revision Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("trial_round_global_id", _("Trial Round Global ID")),
            ("request_global_id", _("Delivery Request Global ID")),
        ):
            setattr(self, fieldname, _uuid(getattr(self, fieldname), label))
        if self.trial_summary != self.summary_revision_global_id:
            frappe.throw(
                _("The Trial Summary fact parent is invalid."),
                frappe.ValidationError,
            )
        value = _json_value(self.value_json)
        references = _json_references(self.source_references)
        if (
            self.fact_group not in FACT_GROUPS
            or fact_type(str(self.fact_key), str(self.fact_group)) != self.fact_type
            or self.value_state not in VALUE_STATES
            or canonical_json(value) != str(self.value_json)
            or _value_text(value) != self.value_text
            or (self.unit is not None and not 1 <= len(str(self.unit)) <= 64)
        ):
            frappe.throw(
                _("The stored Trial Summary fact is invalid."),
                frappe.ValidationError,
            )
        if (
            canonical_json(references) != str(self.source_references)
            or canonical_hash(references) != self.source_references_hash
        ):
            frappe.throw(
                _("The stored Trial Summary fact source references are invalid."),
                frappe.ValidationError,
            )

    def on_trash(self) -> None:
        deny_trial_summary_execution_delete()


def _uuid(value: object, label: str) -> str:
    try:
        parsed = UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise frappe.ValidationError(_("{field} is invalid.").format(field=label)) from error
    if parsed.int == 0 or str(parsed) != str(value).casefold():
        frappe.throw(_("{field} is invalid.").format(field=label), frappe.ValidationError)
    return str(parsed)


def _hash(value: object, label: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        frappe.throw(_("{field} is invalid.").format(field=label), frappe.ValidationError)
    return value


def _json_value(value: object) -> str | int | float | bool | None:
    if not isinstance(value, str) or len(value.encode("utf-8")) > 16_384:
        frappe.throw(_("The stored Trial Summary fact is invalid."), frappe.ValidationError)
    try:
        parsed = json.loads(
            value,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()),
        )
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise frappe.ValidationError(
            _("The stored Trial Summary fact is invalid.")
        ) from error
    if parsed is not None and type(parsed) not in {str, int, float, bool}:
        frappe.throw(_("The stored Trial Summary fact is invalid."), frappe.ValidationError)
    if isinstance(parsed, str) and len(parsed) > 4_000:
        frappe.throw(_("The stored Trial Summary fact is invalid."), frappe.ValidationError)
    return parsed


def _json_references(value: object) -> list[object]:
    if not isinstance(value, str) or len(value.encode("utf-8")) > 1_048_576:
        frappe.throw(
            _("The stored Trial Summary fact source references are invalid."),
            frappe.ValidationError,
        )
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise frappe.ValidationError(
            _("The stored Trial Summary fact source references are invalid.")
        ) from error
    if (
        isinstance(parsed, (str, bytes))
        or not isinstance(parsed, Sequence)
        or not 1 <= len(parsed) <= 100
    ):
        frappe.throw(
            _("The stored Trial Summary fact source references are invalid."),
            frappe.ValidationError,
        )
    return list(parsed)


def _value_text(value: str | int | float | bool | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
