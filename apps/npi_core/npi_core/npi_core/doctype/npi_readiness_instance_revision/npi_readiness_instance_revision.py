from __future__ import annotations

from frappe.model.document import Document

from npi_core.readiness.frappe_validation import (
    deny_readiness_history_delete,
    deny_readiness_history_update,
    require_readiness_command_write,
)
from npi_core.readiness.metadata_validation import (
    canonical_readiness_identity,
    normalize_instance_identity,
    validate_instance_document,
)


class NPIReadinessInstanceRevision(Document):
    """Immutable exact Project readiness revision and derived evaluation."""

    def autoname(self) -> None:
        canonical_readiness_identity(self)

    def before_insert(self) -> None:
        require_readiness_command_write()

    def before_save(self) -> None:
        require_readiness_command_write()
        if self.get_doc_before_save() is not None:
            deny_readiness_history_update()

    def before_validate(self) -> None:
        normalize_instance_identity(self)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_readiness_history_update()
        validate_instance_document(self)

    def on_trash(self) -> None:
        deny_readiness_history_delete(self)
