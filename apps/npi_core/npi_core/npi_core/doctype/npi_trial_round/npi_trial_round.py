from __future__ import annotations

from frappe.model.document import Document

from npi_core.trial.frappe_validation import (
    deny_trial_history_delete,
    require_trial_command_write,
)
from npi_core.trial.metadata_validation import (
    canonical_trial_identity,
    normalize_round_identity,
    validate_round_document,
)


class NPITrialRound(Document):
    """Guarded current Trial Round identity and state projection."""

    def autoname(self) -> None:
        canonical_trial_identity(self)

    def before_insert(self) -> None:
        require_trial_command_write()

    def before_save(self) -> None:
        require_trial_command_write()

    def before_validate(self) -> None:
        normalize_round_identity(self)

    def validate(self) -> None:
        validate_round_document(self)

    def on_trash(self) -> None:
        deny_trial_history_delete(self)
