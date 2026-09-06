from __future__ import annotations

from frappe.model.document import Document

from npi_core.production_transition.frappe_validation import (
    deny_production_transition_history_delete,
    deny_production_transition_history_update,
    require_production_transition_command_write,
)
from npi_core.production_transition.metadata_validation import (
    normalize_handover_package_identity,
    validate_handover_package_document,
)


class NPIHandoverPackageRevision(Document):
    """Immutable exact production-handover package revision."""

    def autoname(self) -> None:
        normalize_handover_package_identity(self)

    def before_insert(self) -> None:
        require_production_transition_command_write()

    def before_save(self) -> None:
        require_production_transition_command_write()
        if self.get_doc_before_save() is not None:
            deny_production_transition_history_update()

    def before_validate(self) -> None:
        normalize_handover_package_identity(self)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_production_transition_history_update()
        validate_handover_package_document(self)

    def on_trash(self) -> None:
        deny_production_transition_history_delete(self)
