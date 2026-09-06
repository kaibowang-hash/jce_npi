from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    canonical_json,
    canonical_uuid,
    frappe_utc_datetime_text,
    json_array,
    json_object,
    lowercase_sha256,
    positive_integer,
    require_exact_parent,
    required_text,
    tenant_text,
)
from npi_integration.publish_request.domain import sha256_json
from npi_integration.publish_request.frappe_validation import (
    deny_publish_history_delete,
    deny_publish_history_update,
    require_publish_policy_write,
    validate_internal_requester_users,
)


_SNAPSHOT_KEYS = {
    "schemaVersion",
    "globalId",
    "policyGlobalId",
    "tenantId",
    "projectGlobalId",
    "policyKey",
    "policyVersion",
    "title",
    "publicationState",
    "targetMode",
    "apiVersion",
    "operation",
    "requesterUserIds",
}


class NPIEBOMPublishPolicyVersion(Document):
    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_publish_policy_write()

    def before_save(self) -> None:
        require_publish_policy_write()
        if self.get_doc_before_save() is not None:
            deny_publish_history_update()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("publish_policy", _("EBOM Publish Policy")),
            ("policy_global_id", _("Publish Policy Global ID")),
            ("project_global_id", _("Project Global ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_publish_history_update()
        if self.publish_policy != self.policy_global_id:
            frappe.throw(
                _("The publish policy must match its exact Global ID."),
                frappe.ValidationError,
            )
        require_exact_parent(
            "NPI EBOM Publish Policy",
            self.publish_policy,
            {
                "global_id": self.policy_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "policy_key": self.policy_key,
                "enabled": 1,
            },
            _("The exact enabled publish policy is unavailable."),
        )
        self.policy_key = required_text(
            self.policy_key, _("Publish Policy Key"), maximum=64
        )
        self.title = required_text(
            self.title, _("Publish Policy Title"), maximum=140
        )
        self.policy_version = positive_integer(
            self.policy_version, _("Publish Policy Version")
        )
        expected_key = f"{self.policy_global_id}:{self.policy_version}"
        if self.version_key != expected_key:
            frappe.throw(
                _("The publish policy version key is invalid."),
                frappe.ValidationError,
            )
        if self.publication_state not in {"draft", "published"}:
            frappe.throw(
                _("Select a supported publish policy state."),
                frappe.ValidationError,
            )
        if self.target_mode != "mock":
            frappe.throw(
                _("Only Mock target mode is available in Phase 5."),
                frappe.ValidationError,
            )
        if self.api_version != "npi.erp-publish.v1" or self.operation != "publish_released_ebom_item_mbom":
            frappe.throw(
                _("The formal Item and MBOM publish operation is invalid."),
                frappe.ValidationError,
            )
        requesters = tuple(
            str(value)
            for value in json_array(
                self.requester_user_ids, _("Requester User IDs")
            )
        )
        if not requesters or len(requesters) > 100 or len(set(requesters)) != len(requesters):
            frappe.throw(
                _("Use between 1 and 100 unique requester users."),
                frappe.ValidationError,
            )
        validate_internal_requester_users(requesters)
        supplied = json_object(
            self.policy_snapshot, _("Canonical Publish Policy Snapshot")
        )
        if set(supplied) != _SNAPSHOT_KEYS:
            frappe.throw(
                _("Canonical Publish Policy Snapshot contains unsupported fields."),
                frappe.ValidationError,
            )
        expected_snapshot = {
            "schemaVersion": 1,
            "globalId": self.global_id,
            "policyGlobalId": self.policy_global_id,
            "tenantId": self.tenant_id,
            "projectGlobalId": self.project_global_id,
            "policyKey": self.policy_key,
            "policyVersion": self.policy_version,
            "title": self.title,
            "publicationState": self.publication_state,
            "targetMode": "mock",
            "apiVersion": "npi.erp-publish.v1",
            "operation": "publish_released_ebom_item_mbom",
            "requesterUserIds": list(requesters),
        }
        if supplied != expected_snapshot:
            frappe.throw(
                _("Canonical Publish Policy Snapshot does not match its fields."),
                frappe.ValidationError,
            )
        canonical = canonical_json(expected_snapshot)
        if lowercase_sha256(self.snapshot_hash, _("Publish Policy Snapshot Hash")) != sha256_json(expected_snapshot):
            frappe.throw(
                _("The publish policy snapshot hash does not match its rules."),
                frappe.ValidationError,
            )
        self.requester_user_ids = canonical_json(list(requesters))
        self.policy_snapshot = canonical
        if self.publication_state == "published":
            self.published_at = frappe_utc_datetime_text(
                self.published_at, _("Published At")
            )
        elif self.published_at:
            frappe.throw(
                _("A draft publish policy cannot have a publication time."),
                frappe.ValidationError,
            )
        self.optimistic_version = positive_integer(
            self.optimistic_version, _("Optimistic Version")
        )

    def on_trash(self) -> None:
        deny_publish_history_delete(
            self,
            target_global_id=self.global_id,
            target_version=self.optimistic_version,
        )
