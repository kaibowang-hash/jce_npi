from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid5

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    assert_immutable_fields,
    canonical_json,
    document_domain_value,
    frappe_utc_datetime_text,
    json_array,
    json_object,
    positive_integer,
    tenant_text,
)
from npi_core.documents.release_domain import (
    DocumentReleasePolicyState,
    DocumentReleasePolicyVersion,
    DocumentReviewerAssignment,
)
from npi_core.documents.release_frappe import validate_internal_policy_users


_IDENTITY_FIELDS = (
    "global_id",
    "document_release_policy",
    "tenant_id",
    "project_global_id",
    "policy_global_id",
    "policy_key",
    "policy_version",
    "version_key",
)


class NPIDocumentReleasePolicyVersion(Document):
    """Administrative draft that becomes an immutable exact release policy."""

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
            == DocumentReleasePolicyState.PUBLISHED.value
        ):
            frappe.throw(
                _("A published document release policy version cannot be changed."),
                frappe.ValidationError,
            )
        self._validate_version_sequence(previous)
        if previous is not None:
            assert_immutable_fields(self, previous, _IDENTITY_FIELDS)
        try:
            state = DocumentReleasePolicyState(
                str(self.publication_state or "draft")
            )
        except ValueError:
            frappe.throw(
                _("Select a supported release policy publication state."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.")
        if previous is None and state is not DocumentReleasePolicyState.DRAFT:
            frappe.throw(
                _("A new document release policy version must start as a draft."),
                frappe.ValidationError,
            )
        if state is DocumentReleasePolicyState.PUBLISHED and not getattr(
            self,
            "_document_release_policy_enabled",
            False,
        ):
            frappe.throw(
                _("Enable the document release policy before publishing this version."),
                frappe.ValidationError,
            )
        reviewers = self._reviewer_assignments()
        submitters = self._users(self.submitter_user_ids, _("Submitter User IDs"))
        releasers = self._users(
            self.release_authority_user_ids,
            _("Release Authority User IDs"),
        )
        superseders = self._users(
            self.supersede_authority_user_ids,
            _("Supersede Authority User IDs"),
        )
        obsoleters = self._users(
            self.obsolete_authority_user_ids,
            _("Obsolete Authority User IDs"),
        )
        policy = document_domain_value(
            lambda: DocumentReleasePolicyVersion(
                global_id=self.global_id,
                policy_global_id=self.policy_global_id,
                tenant_id=self.tenant_id,
                project_global_id=self.project_global_id,
                policy_key=self.policy_key,
                policy_version=self.policy_version,
                title=self.title,
                state=state,
                submitter_user_ids=submitters,
                reviewer_assignments=reviewers,
                required_approval_count=self.required_approval_count,
                release_authority_user_ids=releasers,
                supersede_authority_user_ids=superseders,
                obsolete_authority_user_ids=obsoleters,
                confirmation_method=self.confirmation_method,
                required_scan_state=self.required_scan_state,
                require_live_private_identity=self._checkbox(
                    self.require_live_private_identity,
                    _("Require Live Private Identity"),
                ),
                require_sha256_match=self._checkbox(
                    self.require_sha256_match,
                    _("Require SHA-256 Match"),
                ),
                supersede_requires_released_successor=self._checkbox(
                    self.supersede_requires_released_successor,
                    _("Supersede Requires Released Successor"),
                ),
                supersede_requires_later_revision=self._checkbox(
                    self.supersede_requires_later_revision,
                    _("Supersede Requires Later Revision"),
                ),
                supersede_requires_successor_effective_date=self._checkbox(
                    self.supersede_requires_successor_effective_date,
                    _("Supersede Requires Successor Effective Date"),
                ),
            )
        )
        if state is DocumentReleasePolicyState.PUBLISHED:
            validate_internal_policy_users(
                tuple(
                    dict.fromkeys(
                        [
                            *policy.submitter_user_ids,
                            *(
                                value.user_id
                                for value in policy.reviewer_assignments
                            ),
                            *policy.release_authority_user_ids,
                            *policy.supersede_authority_user_ids,
                            *policy.obsolete_authority_user_ids,
                        ]
                    )
                )
            )
        expected_optimistic_version = (
            1 if previous is None else int(previous.get("optimistic_version") or 0) + 1
        )
        self._apply_policy(
            policy,
            expected_optimistic_version,
            previous,
        )

    def on_trash(self) -> None:
        from npi_core.documents.frappe_validation import (
            deny_document_history_delete,
        )

        deny_document_history_delete(
            self,
            target_global_id=self.global_id,
            target_version=self.policy_version,
        )

    def _set_policy_identity(self) -> None:
        root = frappe.db.get_value(
            "NPI Document Release Policy",
            str(self.document_release_policy or ""),
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
                _("Select an existing document release policy."),
                frappe.ValidationError,
            )
        root_global_id = str(root.get("global_id"))
        try:
            policy_identity = UUID(root_global_id)
        except (TypeError, ValueError):
            frappe.throw(
                _("Select an existing document release policy."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.")
        self.document_release_policy = root_global_id
        self.tenant_id = tenant_text(root.get("tenant_id"))
        self.project_global_id = str(root.get("project_global_id"))
        self.policy_global_id = root_global_id
        self.policy_key = str(root.get("policy_key") or "")
        self._document_release_policy_enabled = int(root.get("enabled") or 0) == 1
        self.policy_version = positive_integer(
            self.policy_version,
            _("Release Policy Version"),
        )
        expected_global_id = uuid5(
            policy_identity,
            f"version:{self.policy_version}",
        )
        if self.global_id not in (None, "", str(expected_global_id)):
            frappe.throw(
                _("Enter a valid document release policy version."),
                frappe.ValidationError,
            )
        self.global_id = str(expected_global_id)
        self.version_key = f"{root_global_id}:{self.policy_version}"

    def _validate_version_sequence(self, previous: object | None) -> None:
        if previous is not None:
            return
        if self.policy_version == 1:
            existing = frappe.db.get_value(
                "NPI Document Release Policy Version",
                {"policy_global_id": self.policy_global_id},
                "name",
            )
            valid = existing is None
        else:
            prior = frappe.db.get_value(
                "NPI Document Release Policy Version",
                {
                    "policy_global_id": self.policy_global_id,
                    "policy_version": self.policy_version - 1,
                },
                "publication_state",
            )
            valid = prior == DocumentReleasePolicyState.PUBLISHED.value
        if not valid:
            frappe.throw(
                _(
                    "Publish each document release policy version before "
                    "creating the next."
                ),
                frappe.ValidationError,
            )

    def _reviewer_assignments(
        self,
    ) -> tuple[DocumentReviewerAssignment, ...]:
        values = json_array(
            self.reviewer_assignments,
            _("Reviewer Assignments"),
        )
        if not all(
            isinstance(value, dict) and set(value) == {"slotKey", "userId"}
            for value in values
        ):
            frappe.throw(
                _("Reviewer Assignments must contain only valid assignments."),
                frappe.ValidationError,
            )
        return tuple(
            DocumentReviewerAssignment(
                slot_key=value.get("slotKey"),
                user_id=value.get("userId"),
            )
            for value in values
        )

    @staticmethod
    def _users(value: object, label: str) -> tuple[str, ...]:
        return tuple(str(item) for item in json_array(value, label))

    @staticmethod
    def _checkbox(value: object, label: str) -> bool:
        if type(value) not in {int, bool} or int(value) not in {0, 1}:
            frappe.throw(
                _("{field} must be a checkbox value.").format(field=label),
                frappe.ValidationError,
            )
        return int(value) == 1

    def _apply_policy(
        self,
        policy: DocumentReleasePolicyVersion,
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
                _("Canonical Release Policy Snapshot"),
            )
            if supplied != snapshot:
                frappe.throw(
                    _("Canonical Release Policy Snapshot does not match its rules."),
                    frappe.ValidationError,
                )
        prior_snapshot_hash = (
            previous.get("snapshot_hash") if previous is not None else None
        )
        if self.snapshot_hash not in (
            None,
            "",
            prior_snapshot_hash,
            policy.snapshot_hash,
        ):
            frappe.throw(
                _("Release Policy Snapshot Hash does not match its rules."),
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
        self.submitter_user_ids = canonical_json(list(policy.submitter_user_ids))
        self.reviewer_assignments = canonical_json(
            [value.canonical_dict() for value in policy.reviewer_assignments]
        )
        self.required_approval_count = policy.required_approval_count
        self.release_authority_user_ids = canonical_json(
            list(policy.release_authority_user_ids)
        )
        self.supersede_authority_user_ids = canonical_json(
            list(policy.supersede_authority_user_ids)
        )
        self.obsolete_authority_user_ids = canonical_json(
            list(policy.obsolete_authority_user_ids)
        )
        self.confirmation_method = policy.confirmation_method
        self.required_scan_state = policy.required_scan_state
        self.require_live_private_identity = 1
        self.require_sha256_match = 1
        self.supersede_requires_released_successor = 1
        self.supersede_requires_later_revision = 1
        self.supersede_requires_successor_effective_date = 1
        self.policy_snapshot = canonical_snapshot
        self.snapshot_hash = policy.snapshot_hash
        self.optimistic_version = optimistic_version
        if policy.state is DocumentReleasePolicyState.PUBLISHED:
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
                _("A draft release policy cannot have a publication time."),
                frappe.ValidationError,
            )
