from __future__ import annotations

from datetime import datetime
from uuid import UUID

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    actor_text,
    canonical_json,
    canonical_uuid,
    frappe_utc_datetime_text,
    json_object,
    lowercase_sha256,
    nonnegative_integer,
    optional_uuid,
    positive_integer,
    require_exact_parent,
    required_text,
    tenant_text,
    utc_datetime_text,
)
from npi_core.ebom.domain import (
    EngineeringBomPolicyReference,
    EngineeringBomRevision,
    validate_revision_against_policy,
)
from npi_core.ebom.frappe_validation import (
    deny_ebom_history_delete,
    deny_ebom_history_update,
    ebom_domain_value,
    ebom_line_value,
    ebom_policy_value,
    require_ebom_command_write,
)


_SNAPSHOT_KEYS = {
    "schemaVersion",
    "globalId",
    "ebomGlobalId",
    "tenantId",
    "projectGlobalId",
    "engineeringBomKey",
    "revisionNumber",
    "predecessorGlobalId",
    "predecessorSnapshotHash",
    "reason",
    "effectivityNote",
    "policyRef",
    "quantityScale",
    "lines",
    "createdByUserId",
    "createdAt",
    "requestId",
    "traceId",
}


class NPIEngineeringBOMRevision(Document):
    """Immutable exact NPI-owned EBOM content snapshot."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_ebom_command_write()

    def before_save(self) -> None:
        require_ebom_command_write()
        if self.get_doc_before_save() is not None:
            deny_ebom_history_update()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("engineering_bom", _("Engineering BOM")),
            ("ebom_global_id", _("Engineering BOM Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("policy_global_id", _("EBOM Policy Global ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.predecessor_global_id = optional_uuid(
            self.predecessor_global_id,
            _("Predecessor EBOM Revision"),
        )
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_ebom_history_update()
        if self.engineering_bom != self.ebom_global_id:
            frappe.throw(
                _("Engineering BOM must match its exact Global ID."),
                frappe.ValidationError,
            )
        require_exact_parent(
            "NPI Engineering BOM",
            self.engineering_bom,
            {
                "global_id": self.ebom_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "engineering_bom_key": self.engineering_bom_key,
                "policy_global_id": self.policy_global_id,
                "policy_version": self.policy_version,
                "policy_snapshot_hash": self.policy_snapshot_hash,
            },
            _("The EBOM revision does not match its Engineering BOM."),
        )
        policy_row = require_exact_parent(
            "NPI EBOM Policy Version",
            {
                "policy_global_id": self.policy_global_id,
                "policy_version": self.policy_version,
            },
            {
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "publication_state": "published",
                "snapshot_hash": self.policy_snapshot_hash,
            },
            _("The exact published EBOM policy is unavailable."),
            extra_fields=(
                "global_id",
                "policy_global_id",
                "policy_key",
                "policy_version",
                "title",
                "synthetic_namespace",
                "line_identity_mode",
                "quantity_scale",
                "maximum_nodes",
                "engineering_uoms",
                "attribute_keys",
                "creator_user_ids",
                "review_submitter_user_ids",
                "reviewer_user_ids",
                "release_authority_user_ids",
                "require_acyclic_graph",
                "require_closed_alternates",
                "require_effectivity_order",
            ),
        )
        supplied_snapshot = json_object(
            self.revision_snapshot,
            _("Canonical EBOM Revision Snapshot"),
        )
        if set(supplied_snapshot) != _SNAPSHOT_KEYS or not isinstance(
            supplied_snapshot.get("lines"),
            list,
        ):
            frappe.throw(
                _("Canonical EBOM Revision Snapshot contains unsupported fields."),
                frappe.ValidationError,
            )
        policy_ref = json_object(
            supplied_snapshot.get("policyRef"),
            _("EBOM Policy Reference"),
        )
        if set(policy_ref) != {"globalId", "version", "snapshotHash"}:
            frappe.throw(
                _("EBOM Policy Reference contains unsupported fields."),
                frappe.ValidationError,
            )
        created_at_text = utc_datetime_text(self.created_at, _("Created At"))
        policy_ref_global_id = canonical_uuid(
            policy_ref.get("globalId"),
            _("EBOM Policy Global ID"),
        )
        policy_ref_version = positive_integer(
            policy_ref.get("version"),
            _("EBOM Policy Version"),
        )
        policy_ref_snapshot_hash = lowercase_sha256(
            policy_ref.get("snapshotHash"),
            _("EBOM Policy Snapshot Hash"),
        )
        quantity_scale = nonnegative_integer(
            self.quantity_scale,
            _("Quantity Scale"),
        )
        if quantity_scale > 6:
            frappe.throw(
                _("Quantity Scale cannot be greater than six."),
                frappe.ValidationError,
            )
        revision = ebom_domain_value(
            lambda: EngineeringBomRevision(
                global_id=UUID(self.global_id),
                ebom_global_id=UUID(self.ebom_global_id),
                tenant_id=self.tenant_id,
                project_global_id=UUID(self.project_global_id),
                engineering_bom_key=self.engineering_bom_key,
                revision_number=self.revision_number,
                predecessor_global_id=(
                    UUID(self.predecessor_global_id)
                    if self.predecessor_global_id
                    else None
                ),
                predecessor_snapshot_hash=(
                    str(self.predecessor_snapshot_hash)
                    if self.predecessor_snapshot_hash
                    else None
                ),
                reason=self.reason,
                effectivity_note=self.effectivity_note,
                policy_ref=EngineeringBomPolicyReference(
                    UUID(policy_ref_global_id),
                    policy_ref_version,
                    policy_ref_snapshot_hash,
                ),
                quantity_scale=quantity_scale,
                lines=tuple(
                    ebom_line_value(value)
                    for value in supplied_snapshot["lines"]  # type: ignore[index]
                ),
                created_by_user_id=self.created_by_user_id,
                created_at=datetime.fromisoformat(
                    created_at_text.replace("Z", "+00:00")
                ),
                request_id=self.request_id,
                trace_id=self.trace_id,
                snapshot_hash=str(self.snapshot_hash or ""),
            )
        )
        policy = ebom_domain_value(lambda: ebom_policy_value(policy_row))
        ebom_domain_value(lambda: validate_revision_against_policy(revision, policy))
        if supplied_snapshot != revision.snapshot_payload():
            frappe.throw(
                _("Canonical EBOM Revision Snapshot does not match its exact lines."),
                frappe.ValidationError,
            )
        if self.line_count not in (None, "", len(revision.lines)):
            frappe.throw(
                _("EBOM Line Count does not match the revision snapshot."),
                frappe.ValidationError,
            )
        if self.revision_number > 1:
            require_exact_parent(
                "NPI Engineering BOM Revision",
                self.predecessor_global_id,
                {
                    "global_id": self.predecessor_global_id,
                    "ebom_global_id": self.ebom_global_id,
                    "tenant_id": self.tenant_id,
                    "project_global_id": self.project_global_id,
                    "revision_number": self.revision_number - 1,
                    "snapshot_hash": self.predecessor_snapshot_hash,
                },
                _("The exact predecessor EBOM revision is unavailable."),
            )
        self.revision_number = positive_integer(
            revision.revision_number,
            _("EBOM Revision Number"),
        )
        self.revision_key = f"{revision.ebom_global_id}:{revision.revision_number}"
        self.reason = required_text(revision.reason, _("Revision Reason"), 280)
        self.policy_version = revision.policy_ref.version
        self.policy_snapshot_hash = lowercase_sha256(
            revision.policy_ref.snapshot_hash,
            _("EBOM Policy Snapshot Hash"),
        )
        self.quantity_scale = revision.quantity_scale
        self.line_count = len(revision.lines)
        self.revision_snapshot = canonical_json(revision.snapshot_payload())
        self.snapshot_hash = lowercase_sha256(
            revision.snapshot_hash,
            _("EBOM Revision Snapshot Hash"),
        )
        self.created_by_user_id = actor_text(
            revision.created_by_user_id,
            _("Created By User ID"),
        )
        self.created_at = frappe_utc_datetime_text(
            revision.created_at,
            _("Created At"),
        )
        self.request_id = required_text(self.request_id, _("Request ID"), 128)
        self.trace_id = required_text(self.trace_id, _("Trace ID"), 128)

    def on_trash(self) -> None:
        deny_ebom_history_delete(
            self,
            target_version=self.get("revision_number") or 1,
        )
