from frappe.model.document import Document

from npi_core.controlled_print.frappe_validation import (
    deny_controlled_print_history_delete,
    require_controlled_print_command_write,
    require_immutable_or_receipt_seal,
    validate_command_receipt,
)


_IMMUTABLE_FIELDS = (
    "global_id", "receipt_key", "tenant_id", "project_global_id",
    "actor_user_id", "operation", "idempotency_key_hash", "payload_hash",
    "created_at",
)


class NPIControlledPrintCommandIdempotency(Document):
    def autoname(self) -> None:
        validate_command_receipt(self)
        self.name = self.global_id

    def before_insert(self) -> None:
        require_controlled_print_command_write()

    def before_save(self) -> None:
        require_controlled_print_command_write()

    def validate(self) -> None:
        require_immutable_or_receipt_seal(self, _IMMUTABLE_FIELDS)
        validate_command_receipt(self)

    def on_trash(self) -> None:
        deny_controlled_print_history_delete(self)
