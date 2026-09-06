from __future__ import annotations

from frappe.model.document import Document

from npi_core.project.frappe_validation import deny_standalone_child_write


class NPITemplateReferenceRule(Document):
    """Typed reference rule frozen into a published template version."""

    def before_insert(self) -> None:
        deny_standalone_child_write()

    def before_save(self) -> None:
        deny_standalone_child_write()

    def on_trash(self) -> None:
        deny_standalone_child_write()
