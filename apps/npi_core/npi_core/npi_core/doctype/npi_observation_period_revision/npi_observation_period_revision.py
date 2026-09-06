from __future__ import annotations

from frappe.model.document import Document

from npi_core.production_transition.frappe_validation import (
    deny_production_transition_history_delete,
    deny_production_transition_history_update,
    require_production_transition_command_write,
)
from npi_core.production_transition.metadata_validation import (
    normalize_observation_period_identity,
    validate_observation_period_document,
)


class NPIObservationPeriodRevision(Document):
    """Immutable independent production observation-period revision."""

    def autoname(self) -> None:
        normalize_observation_period_identity(self)

    def before_insert(self) -> None:
        require_production_transition_command_write()

    def before_save(self) -> None:
        require_production_transition_command_write()
        if self.get_doc_before_save() is not None:
            deny_production_transition_history_update()

    def before_validate(self) -> None:
        normalize_observation_period_identity(self)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_production_transition_history_update()
        validate_observation_period_document(self)

    def on_trash(self) -> None:
        deny_production_transition_history_delete(self)
