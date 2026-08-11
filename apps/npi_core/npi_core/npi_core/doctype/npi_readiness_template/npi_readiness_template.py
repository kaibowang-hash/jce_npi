from __future__ import annotations

from frappe.model.document import Document

from npi_core.readiness.frappe_validation import (
    deny_readiness_history_delete,
    require_readiness_command_write,
)
from npi_core.readiness.metadata_validation import normalize_template_root


class NPIReadinessTemplate(Document):
    """Guarded stable root for versioned NPI readiness templates."""

    def autoname(self) -> None:
        normalize_template_root(self)

    def before_insert(self) -> None:
        require_readiness_command_write()

    def before_save(self) -> None:
        require_readiness_command_write()

    def before_validate(self) -> None:
        normalize_template_root(self)

    def validate(self) -> None:
        normalize_template_root(self)

    def on_trash(self) -> None:
        deny_readiness_history_delete(self)
