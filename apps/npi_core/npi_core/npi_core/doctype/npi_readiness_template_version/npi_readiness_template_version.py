from __future__ import annotations

from frappe.model.document import Document

from npi_core.readiness.frappe_validation import (
    deny_readiness_history_delete,
    deny_readiness_history_update,
    require_readiness_command_write,
)
from npi_core.readiness.metadata_validation import (
    canonical_readiness_identity,
    normalize_template_version_identity,
    validate_template_version_document,
)


class NPIReadinessTemplateVersion(Document):
    """Exact draft or immutable published NPI readiness template version."""

    def autoname(self) -> None:
        canonical_readiness_identity(self)

    def before_insert(self) -> None:
        require_readiness_command_write()

    def before_save(self) -> None:
        require_readiness_command_write()
        previous = self.get_doc_before_save()
        if previous is not None and str(previous.publication_state) == "published":
            deny_readiness_history_update()

    def before_validate(self) -> None:
        normalize_template_version_identity(self)

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None and str(previous.publication_state) == "published":
            deny_readiness_history_update()
        validate_template_version_document(self)

    def on_trash(self) -> None:
        deny_readiness_history_delete(self)
