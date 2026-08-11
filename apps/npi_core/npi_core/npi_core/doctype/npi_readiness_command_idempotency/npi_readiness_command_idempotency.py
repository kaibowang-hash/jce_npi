from __future__ import annotations

from frappe.model.document import Document

from npi_core.readiness.frappe_validation import (
    deny_readiness_history_delete,
    require_readiness_command_write,
)
from npi_core.readiness.metadata_validation import canonical_readiness_identity


class NPIReadinessCommandIdempotency(Document):
    """Actor-bound readiness command replay record; repository sealing is later."""

    def autoname(self) -> None:
        canonical_readiness_identity(self)

    def before_insert(self) -> None:
        require_readiness_command_write()

    def before_save(self) -> None:
        require_readiness_command_write()

    def validate(self) -> None:
        require_readiness_command_write()

    def on_trash(self) -> None:
        deny_readiness_history_delete(self)
