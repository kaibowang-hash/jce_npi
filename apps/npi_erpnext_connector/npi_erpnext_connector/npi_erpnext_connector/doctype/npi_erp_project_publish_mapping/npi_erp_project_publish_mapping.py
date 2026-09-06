from __future__ import annotations

from frappe.model.document import Document

from npi_erpnext_connector.project_publish_validation import deny_project_publish_execution_delete, require_project_publish_execution_write


class NPIERPProjectPublishMapping(Document):
    def autoname(self) -> None:
        self.name = self.project_global_id

    def before_insert(self) -> None:
        require_project_publish_execution_write()

    def before_save(self) -> None:
        require_project_publish_execution_write()
        if self.get_doc_before_save() is not None:
            deny_project_publish_execution_delete()

    def on_trash(self) -> None:
        deny_project_publish_execution_delete()
