from __future__ import annotations

import hashlib

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    canonical_uuid,
    lowercase_sha256,
    positive_integer,
    require_exact_parent,
    required_text,
    tenant_text,
)
from npi_integration.publish_request.frappe_validation import (
    deny_publish_history_delete,
    require_publish_policy_write,
)


class NPIEBOMPublishPolicy(Document):
    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_publish_policy_write()

    def before_save(self) -> None:
        require_publish_policy_write()

    def before_validate(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.project_global_id = canonical_uuid(
            self.project_global_id, _("Project Global ID")
        )
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        require_exact_parent(
            "NPI Engineering Project",
            self.project_global_id,
            {"global_id": self.project_global_id, "tenant_id": self.tenant_id},
            _("The publish policy Project is unavailable."),
        )
        self.policy_key = required_text(
            self.policy_key, _("Publish Policy Key"), maximum=64
        )
        self.title = required_text(
            self.title, _("Publish Policy Title"), maximum=140
        )
        expected = hashlib.sha256(
            f"{self.tenant_id}:{self.project_global_id}:{self.policy_key}".encode()
        ).hexdigest()
        if lowercase_sha256(
            self.policy_key_hash, _("Publish Policy Key Hash")
        ) != expected:
            frappe.throw(
                _("The publish policy key hash does not match its exact scope."),
                frappe.ValidationError,
            )
        self.enabled = 1 if int(self.enabled or 0) == 1 else 0
        self.optimistic_version = positive_integer(
            self.optimistic_version, _("Optimistic Version")
        )
    def on_trash(self) -> None:
        deny_publish_history_delete(
            self,
            target_global_id=self.global_id,
            target_version=self.optimistic_version,
        )
