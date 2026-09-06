from __future__ import annotations

from frappe.model.document import Document

from npi_integration.project_publish.domain import parse_uuid
from npi_integration.project_publish.frappe_validation import deny_project_publish_delete, require_project_publish_write


class NPIERPProjectPublishResult(Document):
    def autoname(self) -> None:
        self.global_id = parse_uuid(self.global_id, "resultGlobalId")
        self.name = self.global_id

    def before_insert(self) -> None:
        require_project_publish_write()

    def before_save(self) -> None:
        require_project_publish_write()

    def on_trash(self) -> None:
        deny_project_publish_delete()

    def validate(self) -> None:
        self.global_id = parse_uuid(self.global_id, "resultGlobalId")
        self.request_global_id = parse_uuid(self.request_global_id, "requestGlobalId")
        self.attempt_global_id = parse_uuid(self.attempt_global_id, "attemptGlobalId")
        if self.get_doc_before_save() is not None:
            deny_project_publish_delete()
