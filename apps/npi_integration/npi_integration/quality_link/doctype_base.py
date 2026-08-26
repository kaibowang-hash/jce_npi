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
    deny_quality_link_history_delete,
    deny_quality_link_history_update,
    require_quality_link_write,
)


class QualityLinkSupportDocument(Document):
    append_only = True
    immutable_fields: tuple[str, ...] = ()
    uuid_fields: tuple[str, ...] = ()
    optional_uuid_fields: tuple[str, ...] = ()
    hash_fields: tuple[str, ...] = ()
    optional_hash_fields: tuple[str, ...] = ()
    positive_fields: tuple[str, ...] = ()
    text_fields: tuple[str, ...] = ()
    actor_fields: tuple[str, ...] = ()

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, self.meta.get_label("global_id"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_quality_link_write(self.doctype, "insert")

    def before_save(self) -> None:
        action = "insert" if getattr(getattr(self, "flags", None), "in_insert", False) else "save"
        require_quality_link_write(self.doctype, action)
        previous = self.get_doc_before_save()
        if previous is None:
            return
        if self.append_only:
            deny_quality_link_history_update()
        assert_immutable_fields(self, previous, self.immutable_fields)

    def validate(self) -> None:
        for field in self.uuid_fields:
            setattr(self, field, canonical_uuid(getattr(self, field), self.meta.get_label(field)))
        for field in self.optional_uuid_fields:
            if getattr(self, field, None):
                setattr(self, field, canonical_uuid(getattr(self, field), self.meta.get_label(field)))
        for field in self.hash_fields:
            setattr(self, field, lowercase_sha256(getattr(self, field), self.meta.get_label(field)))
        for field in self.optional_hash_fields:
            if getattr(self, field, None):
                setattr(self, field, lowercase_sha256(getattr(self, field), self.meta.get_label(field)))
        for field in self.positive_fields:
            setattr(self, field, positive_integer(getattr(self, field), self.meta.get_label(field)))
        for field in self.text_fields:
            setattr(self, field, required_text(getattr(self, field), self.meta.get_label(field), 280))
        for field in self.actor_fields:
            setattr(self, field, actor_text(getattr(self, field), self.meta.get_label(field)))
        if hasattr(self, "tenant_id"):
            self.tenant_id = tenant_text(self.tenant_id)

    def on_trash(self) -> None:
        deny_quality_link_history_delete()
