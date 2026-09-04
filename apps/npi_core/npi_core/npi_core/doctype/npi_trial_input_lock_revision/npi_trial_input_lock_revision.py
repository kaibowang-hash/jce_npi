from __future__ import annotations

from frappe.model.document import Document

from npi_core.trial.frappe_validation import (
    deny_trial_history_delete,
    deny_trial_history_update,
    require_trial_command_write,
)
from npi_core.trial.metadata_validation import (
    canonical_trial_identity,
    normalize_input_lock_identity,
    validate_input_lock_document,
)


class NPITrialInputLockRevision(Document):
    """Immutable exact Trial Round input-lock revision."""

    def autoname(self) -> None:
        canonical_trial_identity(self)

    def before_insert(self) -> None:
        require_trial_command_write()

    def before_save(self) -> None:
        require_trial_command_write()
        if self.get_doc_before_save() is not None:
            deny_trial_history_update()

    def before_validate(self) -> None:
        normalize_input_lock_identity(self)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_trial_history_update()
        validate_input_lock_document(self)

    def on_trash(self) -> None:
        deny_trial_history_delete(self)
