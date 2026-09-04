from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid5

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.baseline_domain import (
    DocumentBaselinePolicyState,
    DocumentBaselinePolicyVersion,
)
from npi_core.documents.frappe_validation import (
    assert_immutable_fields,
    canonical_json,
    deny_document_history_delete,
    document_domain_value,
    frappe_utc_datetime_text,
    json_array,
    json_object,
    positive_integer,
    tenant_text,
)
from npi_core.documents.release_frappe import validate_internal_policy_users


_IDENTITY_FIELDS = (
    "global_id",
    "document_baseline_policy",
    "tenant_id",
    "project_global_id",
    "policy_global_id",
    "policy_key",
    "policy_version",
    "version_key",
)


class NPIDocumentBaselinePolicyVersion(Document):
    """Administrative draft that becomes an immutable baseline policy."""

    def autoname(self) -> None:
        self._set_policy_identity()
        self.name = self.version_key

    def before_validate(self) -> None:
        self._set_policy_identity()

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if (
            previous is not None
            and str(previous.get("publication_state"))
            == DocumentBaselinePolicyState.PUBLISHED.value
        ):
            frappe.throw(
                _("A published document baseline policy version cannot be changed."),
                frappe.ValidationError,
            )
        self._validate_version_sequence(previous)
        if previous is not None:
            assert_immutable_fields(self, previous, _IDENTITY_FIELDS)
        try:
            state = DocumentBaselinePolicyState(
                str(self.publication_state or "draft")
            )
        except ValueError:
            frappe.throw(
                _("Select a supported baseline policy publication state."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.")
        if previous is None and state is not DocumentBaselinePolicyState.DRAFT:
            frappe.throw(
                _("A new document baseline policy version must start as a draft."),
                frappe.ValidationError,
            )
        if state is DocumentBaselinePolicyState.PUBLISHED and not getattr(
            self,
            "_document_baseline_policy_enabled",
            False,
        ):
            frappe.throw(
                _("Enable the document baseline policy before publishing this version."),
                frappe.ValidationError,
            )
        authorities = tuple(
            str(value)
            for value in json_array(
                self.baseline_authority_user_ids,
                _("Baseline Authority User IDs"),
            )
        )
        policy = document_domain_value(
            lambda: DocumentBaselinePolicyVersion(
                global_id=UUID(self.global_id),
                policy_global_id=UUID(self.policy_global_id),
                tenant_id=self.tenant_id,
                project_global_id=UUID(self.project_global_id),
                policy_key=self.policy_key,
                policy_version=self.policy_version,
                title=self.title,
                state=state,
                baseline_authority_user_ids=authorities,
            )
        )
        if state is DocumentBaselinePolicyState.PUBLISHED:
            validate_internal_policy_users(policy.baseline_authority_user_ids)
        self._apply_policy(
            policy,
            1
            if previous is None
            else positive_integer(
                previous.get("optimistic_version"),
                _("Optimistic Version"),
            )
            + 1,
            previous,
        )

    def on_trash(self) -> None:
        deny_document_history_delete(
            self,
            target_global_id=self.global_id,
            target_version=self.policy_version,
        )

    def _set_policy_identity(self) -> None:
        root = frappe.db.get_value(
            "NPI Document Baseline Policy",
            str(self.document_baseline_policy or ""),
            [
                "global_id",
                "tenant_id",
                "project_global_id",
                "policy_key",
                "enabled",
            ],
            as_dict=True,
        )
        if not root:
            frappe.throw(
                _("Select an existing document baseline policy."),
                frappe.ValidationError,
            )
        root_global_id = str(root.get("global_id"))
        try:
            policy_identity = UUID(root_global_id)
        except (TypeError, ValueError):
            frappe.throw(
                _("Select an existing document baseline policy."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.")
        self.document_baseline_policy = root_global_id
        self.tenant_id = tenant_text(root.get("tenant_id"))
        self.project_global_id = str(root.get("project_global_id"))
        self.policy_global_id = root_global_id
        self.policy_key = str(root.get("policy_key") or "")
        self._document_baseline_policy_enabled = int(root.get("enabled") or 0) == 1
        self.policy_version = positive_integer(
            self.policy_version,
            _("Baseline Policy Version"),
        )
        expected_global_id = uuid5(
            policy_identity,
            f"version:{self.policy_version}",
        )
        if self.global_id not in (None, "", str(expected_global_id)):
            frappe.throw(
                _("Enter a valid document baseline policy version."),
                frappe.ValidationError,
            )
        self.global_id = str(expected_global_id)
        self.version_key = f"{root_global_id}:{self.policy_version}"

    def _validate_version_sequence(self, previous: object | None) -> None:
        if previous is not None:
            return
        if self.policy_version == 1:
            existing = frappe.db.get_value(
                "NPI Document Baseline Policy Version",
                {"policy_global_id": self.policy_global_id},
                "name",
            )
            valid = existing is None
        else:
            prior = frappe.db.get_value(
                "NPI Document Baseline Policy Version",
                {
                    "policy_global_id": self.policy_global_id,
                    "policy_version": self.policy_version - 1,
                },
                "publication_state",
            )
            valid = prior == DocumentBaselinePolicyState.PUBLISHED.value
        if not valid:
            frappe.throw(
                _(
                    "Publish each document baseline policy version before creating the next."
                ),
                frappe.ValidationError,
            )

    def _apply_policy(
        self,
        policy: DocumentBaselinePolicyVersion,
        optimistic_version: int,
        previous: object | None,
    ) -> None:
        snapshot = policy.snapshot_payload()
        canonical_snapshot = canonical_json(snapshot)
        prior_snapshot = (
            previous.get("policy_snapshot") if previous is not None else None
        )
        if self.policy_snapshot not in (
            None,
            "",
            prior_snapshot,
            canonical_snapshot,
        ):
            supplied = json_object(
                self.policy_snapshot,
                _("Canonical Baseline Policy Snapshot"),
            )
            if supplied != snapshot:
                frappe.throw(
                    _("Canonical Baseline Policy Snapshot does not match its rules."),
                    frappe.ValidationError,
                )
        prior_hash = previous.get("snapshot_hash") if previous is not None else None
        if self.snapshot_hash not in (
            None,
            "",
            prior_hash,
            policy.snapshot_hash,
        ):
            frappe.throw(
                _("Baseline Policy Snapshot Hash does not match its rules."),
                frappe.ValidationError,
            )
        self.global_id = str(policy.global_id)
        self.policy_global_id = str(policy.policy_global_id)
        self.tenant_id = policy.tenant_id
        self.project_global_id = str(policy.project_global_id)
        self.policy_key = policy.policy_key
        self.policy_version = policy.policy_version
        self.version_key = f"{policy.policy_global_id}:{policy.policy_version}"
        self.title = policy.title
        self.publication_state = policy.state.value
        self.baseline_authority_user_ids = canonical_json(
            list(policy.baseline_authority_user_ids)
        )
        self.policy_snapshot = canonical_snapshot
        self.snapshot_hash = policy.snapshot_hash
        self.optimistic_version = optimistic_version
        if policy.state is DocumentBaselinePolicyState.PUBLISHED:
            self.published_at = frappe_utc_datetime_text(
                (
                    previous.get("published_at")
                    if previous is not None and previous.get("published_at")
                    else datetime.now(UTC)
                ),
                _("Published At"),
            )
        elif self.published_at not in (None, ""):
            frappe.throw(
                _("A draft baseline policy cannot have a publication time."),
                frappe.ValidationError,
            )
