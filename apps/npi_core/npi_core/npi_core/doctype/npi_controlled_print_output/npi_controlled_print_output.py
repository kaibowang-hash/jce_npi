from frappe.model.document import Document

from npi_core.controlled_print.frappe_validation import (
    deny_controlled_print_history_delete,
    require_controlled_print_command_write,
    validate_output,
)
from npi_core.documents.frappe_validation import assert_immutable_fields


_IMMUTABLE_FIELDS = (
    "global_id",
    "tenant_id",
    "project_global_id",
    "controlled_print_snapshot",
    "snapshot_global_id",
    "frappe_file_id",
    "file_name",
    "mime_type",
    "size_bytes",
    "frappe_content_hash",
    "sha256",
    "created_by_user_id",
    "created_at",
    "output_snapshot",
    "record_hash",
)


class NPIControlledPrintOutput(Document):
    def autoname(self) -> None:
        validate_output(self)
        self.name = self.global_id

    def before_insert(self) -> None:
        require_controlled_print_command_write()

    def before_save(self) -> None:
        require_controlled_print_command_write()

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _IMMUTABLE_FIELDS)
        validate_output(self)

    def on_trash(self) -> None:
        deny_controlled_print_history_delete(self)
