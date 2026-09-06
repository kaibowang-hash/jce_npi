from __future__ import annotations

from datetime import datetime
from uuid import UUID

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    canonical_json,
    canonical_uuid,
    frappe_utc_datetime_text,
    json_object,
    lowercase_sha256,
    optional_uuid,
    positive_integer,
    require_exact_parent,
    tenant_text,
    utc_datetime_text,
)
from npi_core.ebom.domain import (
    EngineeringBomEventType,
    EngineeringBomLifecycleEvent,
    EngineeringBomLifecycleState,
    EngineeringBomPolicyReference,
    EngineeringBomReviewDecision,
)
from npi_core.ebom.frappe_validation import (
    deny_ebom_history_delete,
    deny_ebom_history_update,
    ebom_domain_value,
    require_ebom_lifecycle_write,
)


class NPIEBOMLifecycleEvent(Document):
    """Append-only exact transition evidence for one EBOM revision."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_ebom_lifecycle_write()

    def before_save(self) -> None:
        require_ebom_lifecycle_write()
        if self.get_doc_before_save() is not None:
            deny_ebom_history_update()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("engineering_bom", _("Engineering BOM")),
            ("ebom_global_id", _("Engineering BOM Global ID")),
            ("engineering_bom_revision", _("Engineering BOM Revision")),
            ("revision_global_id", _("EBOM Revision Global ID")),
            ("policy_global_id", _("EBOM Policy Global ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.tenant_id = tenant_text(self.tenant_id)
        self.decision = self.decision or None

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_ebom_history_update()
        if self.engineering_bom != self.ebom_global_id:
            frappe.throw(
                _("Engineering BOM must match its exact Global ID."),
                frappe.ValidationError,
            )
        if self.engineering_bom_revision != self.revision_global_id:
            frappe.throw(
                _("Engineering BOM Revision must match its exact Global ID."),
                frappe.ValidationError,
            )
        require_exact_parent(
            "NPI Engineering BOM Revision",
            self.engineering_bom_revision,
            {
                "global_id": self.revision_global_id,
                "ebom_global_id": self.ebom_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "snapshot_hash": self.revision_snapshot_hash,
                "policy_global_id": self.policy_global_id,
                "policy_version": self.policy_version,
                "policy_snapshot_hash": self.policy_snapshot_hash,
            },
            _("The EBOM lifecycle event does not match its exact revision."),
        )
        require_exact_parent(
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
        )
        try:
            event_type = EngineeringBomEventType(str(self.event_type))
            from_state = EngineeringBomLifecycleState(str(self.from_state))
            to_state = EngineeringBomLifecycleState(str(self.to_state))
            decision = (
                EngineeringBomReviewDecision(str(self.decision))
                if self.decision
                else None
            )
        except ValueError:
            frappe.throw(
                _("Select supported EBOM lifecycle event values."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.")
        occurred_at_text = utc_datetime_text(self.occurred_at, _("Occurred At"))
        policy_version = positive_integer(
            self.policy_version,
            _("EBOM Policy Version"),
        )
        from_version = positive_integer(
            self.from_version,
            _("Prior Lifecycle Version"),
        )
        to_version = positive_integer(
            self.to_version,
            _("Lifecycle Version"),
        )
        event = ebom_domain_value(
            lambda: EngineeringBomLifecycleEvent(
                global_id=UUID(self.global_id),
                revision_global_id=UUID(self.revision_global_id),
                revision_snapshot_hash=self.revision_snapshot_hash,
                policy_ref=EngineeringBomPolicyReference(
                    UUID(self.policy_global_id),
                    policy_version,
                    self.policy_snapshot_hash,
                ),
                event_type=event_type,
                from_state=from_state,
                to_state=to_state,
                from_version=from_version,
                to_version=to_version,
                actor_user_id=self.actor_user_id,
                authority_action=self.authority_action,
                decision=decision,
                reason=self.reason,
                confirmation_intent=self.confirmation_intent,
                occurred_at=datetime.fromisoformat(
                    occurred_at_text.replace("Z", "+00:00")
                ),
                request_id=self.request_id,
                trace_id=self.trace_id,
                event_hash=str(self.event_hash or ""),
            )
        )
        supplied = json_object(
            self.event_snapshot,
            _("Canonical EBOM Lifecycle Event"),
        )
        if supplied != event.event_payload():
            frappe.throw(
                _("Canonical EBOM Lifecycle Event does not match its transition."),
                frappe.ValidationError,
            )
        self.revision_snapshot_hash = lowercase_sha256(
            event.revision_snapshot_hash,
            _("EBOM Revision Snapshot Hash"),
        )
        self.policy_version = event.policy_ref.version
        self.policy_snapshot_hash = lowercase_sha256(
            event.policy_ref.snapshot_hash,
            _("EBOM Policy Snapshot Hash"),
        )
        self.event_type = event.event_type.value
        self.from_state = event.from_state.value
        self.to_state = event.to_state.value
        self.from_version = event.from_version
        self.to_version = event.to_version
        self.actor_user_id = event.actor_user_id
        self.authority_action = event.authority_action
        self.decision = event.decision.value if event.decision is not None else None
        self.reason = event.reason
        self.confirmation_intent = event.confirmation_intent
        self.occurred_at = frappe_utc_datetime_text(event.occurred_at, _("Occurred At"))
        self.request_id = event.request_id
        self.trace_id = event.trace_id
        self.event_snapshot = canonical_json(event.event_payload())
        self.event_hash = lowercase_sha256(event.event_hash, _("EBOM Lifecycle Event Hash"))

    def on_trash(self) -> None:
        deny_ebom_history_delete(
            self,
            target_version=self.get("to_version") or 1,
        )
