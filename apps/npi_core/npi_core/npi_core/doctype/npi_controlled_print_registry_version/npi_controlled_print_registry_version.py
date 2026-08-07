import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.controlled_print.frappe_validation import (
    deny_controlled_print_history_delete,
    require_controlled_print_registry_write,
    validate_registry_version,
)
from npi_core.documents.frappe_validation import assert_immutable_fields


_FIELDS = (
    "global_id", "print_registry", "tenant_id", "registry_global_id",
    "mapping_key", "mapping_version", "version_key", "title",
    "publication_state", "source_object_type", "project_type_key", "gate_key",
    "source_state", "language", "delivery_mode", "copy_state",
    "print_format_name", "template_content", "template_sha256",
    "watermark_source", "printer_user_ids", "effective_from", "effective_to",
    "mapping_snapshot", "snapshot_hash", "published_at",
)


class NPIControlledPrintRegistryVersion(Document):
    def autoname(self) -> None:
        validate_registry_version(self)
        self.name = self.global_id

    def before_insert(self) -> None:
        require_controlled_print_registry_write()

    def before_save(self) -> None:
        require_controlled_print_registry_write()

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None and previous.publication_state == "published":
            assert_immutable_fields(self, previous, _FIELDS)
            frappe.throw(
                _("Published controlled print mappings are immutable."),
                frappe.PermissionError,
            )
        validate_registry_version(self)

    def on_trash(self) -> None:
        deny_controlled_print_history_delete(self)
