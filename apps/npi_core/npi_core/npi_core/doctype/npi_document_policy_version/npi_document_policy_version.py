from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid5

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.domain import (
    DocumentPolicyState,
    DocumentPolicyVersion,
    DocumentTypeRule,
)
from npi_core.documents.frappe_validation import (
    assert_immutable_fields,
    canonical_json,
    document_domain_value,
    json_array,
    positive_integer,
    tenant_text,
    utc_datetime_text,
)


_IDENTITY_FIELDS = (
    "global_id",
    "document_policy",
    "tenant_id",
    "policy_global_id",
    "policy_key",
    "policy_version",
    "version_key",
)


class NPIDocumentPolicyVersion(Document):
    """Administrative draft that becomes immutable after explicit publication."""

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
            == DocumentPolicyState.PUBLISHED.value
        ):
            frappe.throw(
                _("A published document policy version cannot be changed."),
                frappe.ValidationError,
            )
        self._validate_version_sequence(previous)
        if previous is not None:
            assert_immutable_fields(self, previous, _IDENTITY_FIELDS)

        rules = json_array(self.document_types, _("Document Types"))
        if not all(
            isinstance(value, dict) and set(value) == {"key", "prefix", "titleSource"}
            for value in rules
        ):
            frappe.throw(
                _("Document Types must contain only valid rules."),
                frappe.ValidationError,
            )
        try:
            state = DocumentPolicyState(str(self.publication_state or "draft"))
        except ValueError:
            frappe.throw(
                _("Select a supported document policy publication state."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.")
        if previous is None and state is not DocumentPolicyState.DRAFT:
            frappe.throw(
                _("A new document policy version must start as a draft."),
                frappe.ValidationError,
            )
        if state is DocumentPolicyState.PUBLISHED and not getattr(
            self,
            "_document_policy_enabled",
            False,
        ):
            frappe.throw(
                _("Enable the document policy before publishing this version."),
                frappe.ValidationError,
            )
        expected_optimistic_version = (
            1 if previous is None else int(previous.get("optimistic_version") or 0) + 1
        )
        policy = document_domain_value(
            lambda: DocumentPolicyVersion(
                global_id=self.global_id,
                policy_global_id=self.policy_global_id,
                policy_key=self.policy_key,
                policy_version=self.policy_version,
                title=self.title,
                state=state,
                document_types=tuple(
                    DocumentTypeRule(
                        key=value.get("key"),
                        prefix=value.get("prefix"),
                        title_source=value.get("titleSource"),
                    )
                    for value in rules
                ),
                confidentiality_keys=tuple(
                    json_array(
                        self.confidentiality_keys,
                        _("Confidentiality Keys"),
                    )
                ),
                allowed_mime_types=tuple(
                    json_array(
                        self.allowed_mime_types,
                        _("Allowed File Formats"),
                    )
                ),
                preview_mime_types=tuple(
                    json_array(
                        self.preview_mime_types,
                        _("Preview File Formats"),
                    )
                ),
                maximum_file_bytes=self.maximum_file_bytes,
                lock_lease_minutes=self.lock_lease_minutes,
            )
        )
        self._apply_policy(policy, expected_optimistic_version, previous)

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
            "NPI Document Policy",
            str(self.document_policy or ""),
            ["global_id", "tenant_id", "policy_key", "enabled"],
            as_dict=True,
        )
        if not root:
            frappe.throw(
                _("Select an existing document policy."),
                frappe.ValidationError,
            )
        root_global_id = str(root.get("global_id"))
        try:
            policy_identity = UUID(root_global_id)
        except (TypeError, ValueError):
            frappe.throw(
                _("Select an existing document policy."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.")
        self.document_policy = root_global_id
        self.tenant_id = tenant_text(root.get("tenant_id"))
        self.policy_global_id = root_global_id
        self.policy_key = str(root.get("policy_key") or "")
        self._document_policy_enabled = int(root.get("enabled") or 0) == 1
        self.policy_version = positive_integer(
            self.policy_version,
            _("Policy Version"),
        )
        expected_global_id = uuid5(
            policy_identity,
            f"version:{self.policy_version}",
        )
        if self.global_id not in (None, "", str(expected_global_id)):
            frappe.throw(
                _("Enter a valid document policy version."),
                frappe.ValidationError,
            )
        self.global_id = str(expected_global_id)
        self.version_key = f"{root_global_id}:{self.policy_version}"

    def _validate_version_sequence(self, previous: object | None) -> None:
        if previous is not None:
            return
        if self.policy_version == 1:
            existing = frappe.db.get_value(
                "NPI Document Policy Version",
                {"policy_global_id": self.policy_global_id},
                ["name"],
                as_dict=True,
            )
            valid = existing is None
        else:
            prior = frappe.db.get_value(
                "NPI Document Policy Version",
                {
                    "policy_global_id": self.policy_global_id,
                    "policy_version": self.policy_version - 1,
                },
                ["publication_state"],
                as_dict=True,
            )
            valid = bool(
                prior
                and str(prior.get("publication_state"))
                == DocumentPolicyState.PUBLISHED.value
            )
        if not valid:
            frappe.throw(
                _("Publish each document policy version before creating the next."),
                frappe.ValidationError,
            )

    def _apply_policy(
        self,
        policy: DocumentPolicyVersion,
        optimistic_version: int,
        previous: object | None,
    ) -> None:
        snapshot = policy.snapshot_payload()
        self.global_id = str(policy.global_id)
        self.policy_global_id = str(policy.policy_global_id)
        self.policy_key = policy.policy_key
        self.policy_version = policy.policy_version
        self.version_key = f"{policy.policy_global_id}:{policy.policy_version}"
        self.title = policy.title
        self.publication_state = policy.state.value
        self.document_types = canonical_json(
            [value.canonical_dict() for value in policy.document_types]
        )
        self.confidentiality_keys = canonical_json(list(policy.confidentiality_keys))
        self.allowed_mime_types = canonical_json(list(policy.allowed_mime_types))
        self.preview_mime_types = canonical_json(list(policy.preview_mime_types))
        self.maximum_file_bytes = policy.maximum_file_bytes
        self.lock_lease_minutes = policy.lock_lease_minutes
        self.policy_snapshot = canonical_json(snapshot)
        self.snapshot_hash = policy.snapshot_hash
        self.optimistic_version = optimistic_version
        if policy.state is DocumentPolicyState.PUBLISHED:
            self.published_at = utc_datetime_text(
                datetime.now(UTC),
                _("Published At"),
            )
        elif previous is not None and previous.get("published_at"):
            frappe.throw(
                _("A published document policy version cannot return to draft."),
                frappe.ValidationError,
            )
        else:
            self.published_at = None
