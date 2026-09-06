from __future__ import annotations

import hashlib

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    assert_immutable_fields,
    canonical_uuid,
    deny_document_history_delete,
    key_text,
    positive_integer,
    require_exact_parent,
    required_text,
    tenant_text,
)


_IDENTITY_FIELDS = (
    "global_id",
    "tenant_id",
    "project_global_id",
    "policy_key",
    "policy_key_hash",
)


class NPIDocumentReleasePolicy(Document):
    """Project-scoped administrative root for immutable release-policy versions."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_validate(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.tenant_id = tenant_text(self.tenant_id)
        self.project_global_id = canonical_uuid(
            self.project_global_id,
            _("Project Global ID"),
        )
        self.policy_key = key_text(self.policy_key, _("Release Policy Key"))
        self.policy_key_hash = hashlib.sha256(
            (
                f"{self.tenant_id}:{self.project_global_id}:"
                f"{self.policy_key.casefold()}"
            ).encode("utf-8")
        ).hexdigest()
        self.title = required_text(self.title, _("Release Policy Title"), 140)
        if self.is_new():
            self.optimistic_version = 1

    def validate(self) -> None:
        require_exact_parent(
            "NPI Engineering Project",
            self.project_global_id,
            {
                "global_id": self.project_global_id,
                "tenant_id": self.tenant_id,
            },
            _("The release policy does not match its Project and tenant."),
        )
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _IDENTITY_FIELDS)
            self.optimistic_version = (
                positive_integer(
                    previous.get("optimistic_version"),
                    _("Optimistic Version"),
                )
                + 1
            )
        else:
            self.optimistic_version = positive_integer(
                self.optimistic_version,
                _("Optimistic Version"),
            )
        if type(self.enabled) not in {int, bool} or int(self.enabled) not in {0, 1}:
            frappe.throw(_("Enabled must be a checkbox value."), frappe.ValidationError)

    def on_trash(self) -> None:
        deny_document_history_delete(
            self,
            target_global_id=self.global_id,
            target_version=self.optimistic_version,
        )
