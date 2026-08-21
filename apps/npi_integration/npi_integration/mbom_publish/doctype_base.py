from __future__ import annotations

from collections.abc import Callable

from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    actor_text,
    assert_immutable_fields,
    canonical_uuid,
    lowercase_sha256,
    nonnegative_integer,
    positive_integer,
    required_text,
    tenant_text,
)

from .frappe_validation import (
    deny_mbom_history_delete,
    deny_mbom_history_update,
    require_mbom_capability,
)


class MbomSupportDocument(Document):
    """Shared fail-closed controller base for MBOM support metadata."""

    identity_field = "global_id"
    identity_is_hash = False
    append_only = True
    immutable_fields: tuple[str, ...] = ()
    uuid_fields: tuple[str, ...] = ()
    optional_uuid_fields: tuple[str, ...] = ()
    hash_fields: tuple[str, ...] = ()
    optional_hash_fields: tuple[str, ...] = ()
    positive_fields: tuple[str, ...] = ()
    nonnegative_fields: tuple[str, ...] = ()
    tenant_fields: tuple[str, ...] = ()
    required_text_fields: tuple[str, ...] = ()
    optional_text_fields: tuple[str, ...] = ()
    actor_fields: tuple[str, ...] = ()
    optional_actor_fields: tuple[str, ...] = ()
    write_guard: Callable[[], None] | None = None

    def autoname(self) -> None:
        identity = (
            lowercase_sha256(
                getattr(self, self.identity_field),
                self.meta.get_label(self.identity_field),
            )
            if self.identity_is_hash
            else canonical_uuid(
                getattr(self, self.identity_field),
                self.meta.get_label(self.identity_field),
            )
        )
        setattr(self, self.identity_field, identity)
        self.name = identity

    def before_insert(self) -> None:
        self._require_write("insert")

    def before_save(self) -> None:
        action = (
            "insert"
            if getattr(getattr(self, "flags", None), "in_insert", False)
            else "save"
        )
        self._require_write(action)
        previous = self.get_doc_before_save()
        if previous is None:
            return
        if self.append_only:
            deny_mbom_history_update()
        assert_immutable_fields(self, previous, self.immutable_fields)

    def validate(self) -> None:
        for fieldname in self.uuid_fields:
            setattr(
                self,
                fieldname,
                canonical_uuid(getattr(self, fieldname), self.meta.get_label(fieldname)),
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
                lowercase_sha256(getattr(self, fieldname), self.meta.get_label(fieldname)),
            )
        for fieldname in self.optional_hash_fields:
            if getattr(self, fieldname, None):
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
                positive_integer(getattr(self, fieldname), self.meta.get_label(fieldname)),
            )
        for fieldname in self.nonnegative_fields:
            setattr(
                self,
                fieldname,
                nonnegative_integer(getattr(self, fieldname), self.meta.get_label(fieldname)),
            )
        for fieldname in self.tenant_fields:
            setattr(self, fieldname, tenant_text(getattr(self, fieldname)))
        for fieldname in self.required_text_fields:
            setattr(
                self,
                fieldname,
                required_text(getattr(self, fieldname), self.meta.get_label(fieldname), 280),
            )
        for fieldname in self.optional_text_fields:
            if getattr(self, fieldname, None):
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
                actor_text(getattr(self, fieldname), self.meta.get_label(fieldname)),
            )
        for fieldname in self.optional_actor_fields:
            if getattr(self, fieldname, None):
                setattr(
                    self,
                    fieldname,
                    actor_text(
                        getattr(self, fieldname),
                        self.meta.get_label(fieldname),
                    ),
                )

    def on_trash(self) -> None:
        deny_mbom_history_delete()

    def _require_write(self, action: str) -> None:
        if self.write_guard is None:
            deny_mbom_history_update()
        self.write_guard()
        require_mbom_capability(self.doctype, action)
