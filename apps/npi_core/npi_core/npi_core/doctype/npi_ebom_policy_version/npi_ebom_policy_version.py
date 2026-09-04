from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid5

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    assert_immutable_fields,
    canonical_json,
    frappe_utc_datetime_text,
    json_object,
    positive_integer,
    tenant_text,
)
from npi_core.ebom.domain import EngineeringBomPolicyState, EngineeringBomPolicyVersion
from npi_core.ebom.frappe_validation import (
    deny_ebom_history_delete,
    ebom_domain_value,
    ebom_policy_value,
    require_ebom_policy_write,
    validate_internal_ebom_policy_users,
)


_IDENTITY_FIELDS = (
    "global_id",
    "ebom_policy",
    "tenant_id",
    "project_global_id",
    "policy_global_id",
    "policy_key",
    "policy_version",
    "version_key",
)


def _domain_snapshot_hash(
    document: object,
    previous: object | None,
    state: EngineeringBomPolicyState,
) -> str:
    current_hash = str(document.get("snapshot_hash") or "")
    if previous is None or state is not EngineeringBomPolicyState.PUBLISHED:
        return current_hash
    prior_state = str(previous.get("publication_state") or "")
    prior_hash = str(previous.get("snapshot_hash") or "")
    if (
        prior_state == EngineeringBomPolicyState.DRAFT.value
        and current_hash
        and current_hash == prior_hash
    ):
        return ""
    return current_hash


class NPIEBOMPolicyVersion(Document):
    """Administrative draft that becomes an immutable synthetic EBOM policy."""

    def autoname(self) -> None:
        self._set_policy_identity()
        self.name = self.version_key

    def before_insert(self) -> None:
        require_ebom_policy_write()

    def before_save(self) -> None:
        require_ebom_policy_write()

    def before_validate(self) -> None:
        self._set_policy_identity()

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if (
            previous is not None
            and str(previous.get("publication_state"))
            == EngineeringBomPolicyState.PUBLISHED.value
        ):
            frappe.throw(
                _("A published EBOM policy version cannot be changed."),
                frappe.ValidationError,
            )
        self._validate_version_sequence(previous)
        if previous is not None:
            assert_immutable_fields(self, previous, _IDENTITY_FIELDS)
        try:
            state = EngineeringBomPolicyState(str(self.publication_state or "draft"))
        except ValueError:
            frappe.throw(
                _("Select a supported EBOM policy publication state."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.")
        if previous is None and state is not EngineeringBomPolicyState.DRAFT:
            frappe.throw(
                _("A new EBOM policy version must start as a draft."),
                frappe.ValidationError,
            )
        if state is EngineeringBomPolicyState.PUBLISHED and not getattr(
            self,
            "_ebom_policy_enabled",
            False,
        ):
            frappe.throw(
                _("Enable the EBOM policy before publishing this version."),
                frappe.ValidationError,
            )
        policy = ebom_domain_value(
            lambda: ebom_policy_value(
                self,
                snapshot_hash_override=_domain_snapshot_hash(self, previous, state),
            )
        )
        if state is EngineeringBomPolicyState.PUBLISHED:
            validate_internal_ebom_policy_users(
                (
                    *policy.creator_user_ids,
                    *policy.review_submitter_user_ids,
                    *policy.reviewer_user_ids,
                    *policy.release_authority_user_ids,
                )
            )
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
        deny_ebom_history_delete(
            self,
            target_version=self.get("policy_version") or 1,
        )

    def _set_policy_identity(self) -> None:
        root = frappe.db.get_value(
            "NPI EBOM Policy",
            str(self.ebom_policy or ""),
            ["global_id", "tenant_id", "project_global_id", "policy_key", "enabled"],
            as_dict=True,
        )
        if not root:
            frappe.throw(_("Select an existing EBOM policy."), frappe.ValidationError)
        root_global_id = str(root.get("global_id"))
        try:
            policy_identity = UUID(root_global_id)
        except (TypeError, ValueError):
            frappe.throw(_("Select an existing EBOM policy."), frappe.ValidationError)
            raise AssertionError("Frappe validation must raise.")
        self.ebom_policy = root_global_id
        self.tenant_id = tenant_text(root.get("tenant_id"))
        self.project_global_id = str(root.get("project_global_id"))
        self.policy_global_id = root_global_id
        self.policy_key = str(root.get("policy_key") or "")
        self._ebom_policy_enabled = int(root.get("enabled") or 0) == 1
        self.policy_version = positive_integer(
            self.policy_version,
            _("EBOM Policy Version"),
        )
        expected_global_id = uuid5(policy_identity, f"version:{self.policy_version}")
        if self.global_id not in (None, "", str(expected_global_id)):
            frappe.throw(_("Enter a valid EBOM policy version."), frappe.ValidationError)
        self.global_id = str(expected_global_id)
        self.version_key = f"{root_global_id}:{self.policy_version}"

    def _validate_version_sequence(self, previous: object | None) -> None:
        if previous is not None:
            return
        if self.policy_version == 1:
            valid = (
                frappe.db.get_value(
                    "NPI EBOM Policy Version",
                    {"policy_global_id": self.policy_global_id},
                    "name",
                )
                is None
            )
        else:
            valid = (
                frappe.db.get_value(
                    "NPI EBOM Policy Version",
                    {
                        "policy_global_id": self.policy_global_id,
                        "policy_version": self.policy_version - 1,
                    },
                    "publication_state",
                )
                == EngineeringBomPolicyState.PUBLISHED.value
            )
        if not valid:
            frappe.throw(
                _("Publish each EBOM policy version before creating the next."),
                frappe.ValidationError,
            )

    def _apply_policy(
        self,
        policy: EngineeringBomPolicyVersion,
        optimistic_version: int,
        previous: object | None,
    ) -> None:
        snapshot = policy.snapshot_payload()
        canonical_snapshot = canonical_json(snapshot)
        prior_snapshot = previous.get("policy_snapshot") if previous is not None else None
        if self.policy_snapshot not in (None, "", prior_snapshot, canonical_snapshot):
            if json_object(
                self.policy_snapshot,
                _("Canonical EBOM Policy Snapshot"),
            ) != snapshot:
                frappe.throw(
                    _("Canonical EBOM Policy Snapshot does not match its rules."),
                    frappe.ValidationError,
                )
        prior_hash = previous.get("snapshot_hash") if previous is not None else None
        if self.snapshot_hash not in (None, "", prior_hash, policy.snapshot_hash):
            frappe.throw(
                _("EBOM Policy Snapshot Hash does not match its rules."),
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
        self.synthetic_namespace = policy.synthetic_namespace
        self.line_identity_mode = policy.line_identity_mode
        self.quantity_scale = policy.quantity_scale
        self.maximum_nodes = policy.maximum_nodes
        for fieldname in (
            "engineering_uoms",
            "attribute_keys",
            "creator_user_ids",
            "review_submitter_user_ids",
            "reviewer_user_ids",
            "release_authority_user_ids",
        ):
            setattr(self, fieldname, canonical_json(list(getattr(policy, fieldname))))
        self.require_acyclic_graph = 1
        self.require_closed_alternates = 1
        self.require_effectivity_order = 1
        self.policy_snapshot = canonical_snapshot
        self.snapshot_hash = policy.snapshot_hash
        self.optimistic_version = optimistic_version
        if policy.state is EngineeringBomPolicyState.PUBLISHED:
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
                _("A draft EBOM policy cannot have a publication time."),
                frappe.ValidationError,
            )
