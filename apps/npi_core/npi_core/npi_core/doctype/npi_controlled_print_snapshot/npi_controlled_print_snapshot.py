from frappe.model.document import Document

from npi_core.controlled_print.frappe_validation import (
    deny_controlled_print_history_delete,
    require_controlled_print_command_write,
    validate_snapshot,
)
from npi_core.documents.frappe_validation import assert_immutable_fields


_IMMUTABLE_FIELDS = (
    "global_id",
    "tenant_id",
    "project_global_id",
    "project_type_key",
    "gate_key",
    "source_object_type",
    "source_global_id",
    "source_version",
    "source_state",
    "source_snapshot",
    "source_snapshot_hash",
    "mapping_global_id",
    "registry_global_id",
    "mapping_version",
    "mapping_snapshot_hash",
    "template_sha256",
    "language",
    "delivery_mode",
    "copy_state",
    "watermark_source",
    "actor_user_id",
    "printed_at",
    "request_id",
    "trace_id",
    "snapshot_version",
    "snapshot",
    "snapshot_hash",
    "verification_payload",
)


class NPIControlledPrintSnapshot(Document):
    def autoname(self) -> None:
        validate_snapshot(self)
        self.name = self.global_id

    def before_insert(self) -> None:
        require_controlled_print_command_write()

    def before_save(self) -> None:
        require_controlled_print_command_write()

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _IMMUTABLE_FIELDS)
        validate_snapshot(self)

    def on_trash(self) -> None:
        deny_controlled_print_history_delete(self)
