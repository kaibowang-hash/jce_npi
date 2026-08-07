from frappe.model.document import Document

from npi_core.controlled_print.frappe_validation import (
    deny_controlled_print_history_delete,
    require_controlled_print_command_write,
    validate_access_event,
)
from npi_core.documents.frappe_validation import assert_immutable_fields


_IMMUTABLE_FIELDS = (
    "global_id",
    "tenant_id",
    "project_global_id",
    "controlled_print_snapshot",
    "snapshot_global_id",
    "controlled_print_output",
    "output_global_id",
    "event_type",
    "actor_user_id",
    "occurred_at",
    "trace_id",
    "event_snapshot",
    "event_hash",
)


class NPIControlledPrintAccessEvent(Document):
    def autoname(self) -> None:
        validate_access_event(self)
        self.name = self.global_id

    def before_insert(self) -> None:
        require_controlled_print_command_write()

    def before_save(self) -> None:
        require_controlled_print_command_write()

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _IMMUTABLE_FIELDS)
        validate_access_event(self)

    def on_trash(self) -> None:
        deny_controlled_print_history_delete(self)
