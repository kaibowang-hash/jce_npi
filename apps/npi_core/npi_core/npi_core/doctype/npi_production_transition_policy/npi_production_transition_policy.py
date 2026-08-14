from __future__ import annotations

from frappe.model.document import Document

from npi_core.production_transition.frappe_validation import (
    deny_production_transition_history_delete,
    require_production_transition_command_write,
)
from npi_core.production_transition.metadata_validation import normalize_policy_root


class NPIProductionTransitionPolicy(Document):
    """Guarded stable root for versioned production-transition policies."""

    def autoname(self) -> None:
        normalize_policy_root(self)

    def before_insert(self) -> None:
        require_production_transition_command_write()

    def before_save(self) -> None:
        require_production_transition_command_write()

    def before_validate(self) -> None:
        normalize_policy_root(self)

    def validate(self) -> None:
        normalize_policy_root(self)

    def on_trash(self) -> None:
        deny_production_transition_history_delete(self)
