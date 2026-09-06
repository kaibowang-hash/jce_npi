from frappe.model.document import Document

from npi_core.controlled_print.frappe_validation import (
    deny_controlled_print_history_delete,
    require_controlled_print_registry_write,
    validate_registry_root,
)


class NPIControlledPrintRegistry(Document):
    def autoname(self) -> None:
        validate_registry_root(self)
        self.name = self.global_id

    def before_insert(self) -> None:
        require_controlled_print_registry_write()

    def before_save(self) -> None:
        require_controlled_print_registry_write()

    def validate(self) -> None:
        validate_registry_root(self)

    def on_trash(self) -> None:
        deny_controlled_print_history_delete(self)
