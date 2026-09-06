from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.production_transition.frappe_validation import (
    deny_production_transition_history_delete,
    deny_production_transition_history_update,
    require_production_transition_command_write,
    require_production_transition_policy_version_write,
)
from npi_core.production_transition.metadata_validation import (
    normalize_policy_version_identity,
    validate_policy_version_document,
)


class NPIProductionTransitionPolicyVersion(Document):
    """Guarded draft and immutable published transition policy version."""

    def autoname(self) -> None:
        normalize_policy_version_identity(self)

    def before_insert(self) -> None:
        require_production_transition_policy_version_write()
        if str(self.publication_state) != "draft":
            frappe.throw(
                _("A new Production Transition Policy version must start as draft."),
                frappe.ValidationError,
            )

    def before_save(self) -> None:
        require_production_transition_command_write()
        previous = self.get_doc_before_save()
        if previous is not None:
            if str(previous.publication_state) == "published":
                deny_production_transition_history_update()
            require_production_transition_policy_version_write()

    def before_validate(self) -> None:
        normalize_policy_version_identity(self)

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            if str(previous.publication_state) == "published":
                deny_production_transition_history_update()
            require_production_transition_policy_version_write()
        validate_policy_version_document(self, previous)

    def on_trash(self) -> None:
        deny_production_transition_history_delete(self)
