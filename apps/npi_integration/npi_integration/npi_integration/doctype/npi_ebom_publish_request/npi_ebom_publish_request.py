from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    actor_text,
    canonical_json,
    canonical_uuid,
    json_object,
    lowercase_sha256,
    positive_integer,
    require_exact_parent,
    required_text,
    tenant_text,
    utc_datetime_text,
)
from npi_integration.publish_request.frappe_validation import (
    deny_publish_history_delete,
    deny_publish_history_update,
    require_publish_request_write,
)


_EVIDENCE_KEYS = {
    "projectGlobalId",
    "ebomGlobalId",
    "ebomVersion",
    "revisionGlobalId",
    "revisionNumber",
    "revisionSnapshotHash",
    "lifecycleVersion",
    "releaseEventGlobalId",
    "releaseEventHash",
    "ebomPolicyGlobalId",
    "ebomPolicyVersion",
    "ebomPolicySnapshotHash",
    "approvalEvidenceIds",
    "releasedAt",
}


class NPIEBOMPublishRequest(Document):
    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_publish_request_write()

    def before_save(self) -> None:
        require_publish_request_write()
        if self.get_doc_before_save() is not None:
            deny_publish_history_update()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("engineering_bom", _("Engineering BOM")),
            ("ebom_global_id", _("Engineering BOM Global ID")),
            ("engineering_bom_revision", _("Engineering BOM Revision")),
            ("revision_global_id", _("EBOM Revision Global ID")),
            ("publish_policy_global_id", _("Publish Policy Global ID")),
            ("request_id", _("Request ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.tenant_id = tenant_text(self.tenant_id)
        self.actor_user_id = actor_text(self.actor_user_id, _("Actor User ID"))

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_publish_history_update()
        if self.engineering_bom != self.ebom_global_id or self.engineering_bom_revision != self.revision_global_id:
            frappe.throw(
                _("The publish request must use exact EBOM identities."),
                frappe.ValidationError,
            )
        root = require_exact_parent(
            "NPI Engineering BOM",
            self.engineering_bom,
            {
                "global_id": self.ebom_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
            },
            _("The exact Engineering BOM is unavailable."),
            extra_fields=("optimistic_version",),
        )
        revision = require_exact_parent(
            "NPI Engineering BOM Revision",
            self.engineering_bom_revision,
            {
                "global_id": self.revision_global_id,
                "engineering_bom": self.ebom_global_id,
                "ebom_global_id": self.ebom_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
            },
            _("The exact released EBOM revision is unavailable."),
            extra_fields=("revision_number", "snapshot_hash", "policy_global_id", "policy_version", "policy_snapshot_hash"),
        )
        lifecycle = require_exact_parent(
            "NPI EBOM Revision Lifecycle",
            {"revision_global_id": self.revision_global_id},
            {
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "ebom_global_id": self.ebom_global_id,
                "current_state": "released",
            },
            _("The exact EBOM revision is not released."),
            extra_fields=("lifecycle_version", "last_event_global_id"),
        )
        release_event = require_exact_parent(
            "NPI EBOM Lifecycle Event",
            str(lifecycle.last_event_global_id),
            {
                "global_id": str(lifecycle.last_event_global_id),
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "ebom_global_id": self.ebom_global_id,
                "revision_global_id": self.revision_global_id,
                "event_type": "released",
                "to_state": "released",
                "to_version": lifecycle.lifecycle_version,
            },
            _("The exact EBOM release event is unavailable."),
            extra_fields=("event_hash", "occurred_at"),
        )
        self.publish_policy_version = positive_integer(
            self.publish_policy_version, _("Publish Policy Version")
        )
        require_exact_parent(
            "NPI EBOM Publish Policy Version",
            {
                "policy_global_id": self.publish_policy_global_id,
                "policy_version": self.publish_policy_version,
            },
            {
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "publication_state": "published",
                "target_mode": "mock",
                "snapshot_hash": self.publish_policy_snapshot_hash,
            },
            _("The exact published EBOM publish policy is unavailable."),
        )
        for fieldname, label in (
            ("publish_policy_snapshot_hash", _("Publish Policy Snapshot Hash")),
            ("payload_hash", _("Publish Request Payload Hash")),
            ("idempotency_key_hash", _("Idempotency Key Hash")),
        ):
            setattr(self, fieldname, lowercase_sha256(getattr(self, fieldname), label))
        if self.target_mode != "mock" or self.dispatch_allowed:
            frappe.throw(
                _("Phase 5 publish requests must remain Mock-only with dispatch disabled."),
                frappe.ValidationError,
            )
        if self.api_version != "npi.erp-publish.v1" or self.operation != "publish_released_ebom_item_mbom":
            frappe.throw(
                _("The formal Item and MBOM publish operation is invalid."),
                frappe.ValidationError,
            )
        if self.state not in {"validated", "manual_intervention"}:
            frappe.throw(
                _("Mock publish requests cannot report ERP execution progress or success."),
                frappe.ValidationError,
            )
        self.trace_id = required_text(self.trace_id, _("Trace ID"), maximum=128)
        self.node_count = positive_integer(self.node_count, _("Publish Node Count"))
        if self.node_count > 500:
            frappe.throw(
                _("A publish request cannot contain more than 500 nodes."),
                frappe.ValidationError,
            )
        evidence = json_object(
            self.evidence_snapshot, _("Exact Released EBOM Evidence")
        )
        if set(evidence) != _EVIDENCE_KEYS:
            frappe.throw(
                _("Exact Released EBOM Evidence contains unsupported fields."),
                frappe.ValidationError,
            )
        exact_pairs = {
            "projectGlobalId": self.project_global_id,
            "ebomGlobalId": self.ebom_global_id,
            "ebomVersion": int(root.optimistic_version),
            "revisionGlobalId": self.revision_global_id,
            "revisionNumber": int(revision.revision_number),
            "revisionSnapshotHash": str(revision.snapshot_hash),
            "lifecycleVersion": int(lifecycle.lifecycle_version),
            "releaseEventGlobalId": str(lifecycle.last_event_global_id),
            "releaseEventHash": str(release_event.event_hash),
            "ebomPolicyGlobalId": str(revision.policy_global_id),
            "ebomPolicyVersion": int(revision.policy_version),
            "ebomPolicySnapshotHash": str(revision.policy_snapshot_hash),
            "releasedAt": utc_datetime_text(
                release_event.occurred_at, _("Released At")
            ),
        }
        for key, expected in exact_pairs.items():
            if evidence.get(key) != expected:
                frappe.throw(
                    _("Exact Released EBOM Evidence does not match the released revision."),
                    frappe.ValidationError,
                )
        approvals = evidence.get("approvalEvidenceIds")
        if not isinstance(approvals, list) or str(lifecycle.last_event_global_id) not in approvals:
            frappe.throw(
                _("Exact Released EBOM Evidence must include the release event."),
                frappe.ValidationError,
            )
        self.evidence_snapshot = canonical_json(evidence)
        utc_datetime_text(self.created_at, _("Created At"))

    def on_trash(self) -> None:
        deny_publish_history_delete(self, target_global_id=self.global_id)
