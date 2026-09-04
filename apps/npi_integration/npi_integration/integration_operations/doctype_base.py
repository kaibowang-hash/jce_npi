from __future__ import annotations

from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    actor_text,
    assert_immutable_fields,
    canonical_uuid,
    lowercase_sha256,
    positive_integer,
    required_text,
    tenant_text,
)

from .frappe_validation import (
    deny_integration_operations_history_delete,
    deny_integration_operations_history_update,
    require_integration_operations_write,
)


class IntegrationOperationsSupportDocument(Document):
    immutable_fields: tuple[str, ...] = ()
    uuid_fields: tuple[str, ...] = ()
    optional_uuid_fields: tuple[str, ...] = ()
    hash_fields: tuple[str, ...] = ()
    positive_fields: tuple[str, ...] = ()
    text_fields: tuple[str, ...] = ()
    actor_fields: tuple[str, ...] = ()

    def autoname(self) -> None:
        self.global_id = canonical_uuid(
            self.global_id,
            self.meta.get_label("global_id"),
        )
        self.name = self.global_id

    def before_insert(self) -> None:
        require_integration_operations_write(self.doctype, "insert")

    def before_save(self) -> None:
        action = (
            "insert"
            if getattr(getattr(self, "flags", None), "in_insert", False)
            else "save"
        )
        require_integration_operations_write(self.doctype, action)
        previous = self.get_doc_before_save()
        if previous is not None:
            deny_integration_operations_history_update()
            assert_immutable_fields(self, previous, self.immutable_fields)

    def validate(self) -> None:
        for fieldname in self.uuid_fields:
            setattr(
                self,
                fieldname,
                canonical_uuid(
                    getattr(self, fieldname),
                    self.meta.get_label(fieldname),
                ),
            )
        for fieldname in self.optional_uuid_fields:
            if getattr(self, fieldname, None):
                setattr(
                    self,
                    fieldname,
                    canonical_uuid(
                        getattr(self, fieldname),
                        self.meta.get_label(fieldname),
                    ),
                )
        for fieldname in self.hash_fields:
            setattr(
                self,
                fieldname,
                lowercase_sha256(
                    getattr(self, fieldname),
                    self.meta.get_label(fieldname),
                ),
            )
        for fieldname in self.positive_fields:
            setattr(
                self,
                fieldname,
                positive_integer(
                    getattr(self, fieldname),
                    self.meta.get_label(fieldname),
                ),
            )
        for fieldname in self.text_fields:
            setattr(
                self,
                fieldname,
                required_text(
                    getattr(self, fieldname),
                    self.meta.get_label(fieldname),
                    280,
                ),
            )
        for fieldname in self.actor_fields:
            setattr(
                self,
                fieldname,
                actor_text(
                    getattr(self, fieldname),
                    self.meta.get_label(fieldname),
                ),
            )
        self.tenant_id = tenant_text(self.tenant_id)

    def on_trash(self) -> None:
        deny_integration_operations_history_delete()
