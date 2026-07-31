from __future__ import annotations

from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.domain import ControlledDocument, DocumentPolicyReference
from npi_core.documents.domain import (
    DocumentPolicyState,
    DocumentPolicyVersion,
    DocumentTypeRule,
    create_controlled_document,
)
from npi_core.documents.frappe_validation import (
    actor_text,
    assert_immutable_fields,
    canonical_uuid,
    deny_document_history_delete,
    document_domain_value,
    frappe_utc_datetime_text,
    json_array,
    mark_projection_validation_substage,
    require_exact_parent,
    require_document_command_write,
    tenant_text,
)


_IDENTITY_FIELDS = (
    "global_id",
    "tenant_id",
    "project_global_id",
    "policy_global_id",
    "policy_version",
    "policy_snapshot_hash",
    "document_number",
    "document_number_key",
    "document_type_key",
    "title",
    "confidentiality_key",
    "created_by_user_id",
    "created_at",
)


class NPIControlledDocument(Document):
    """Stable identity with mutable current-revision and edit-lease projections."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_document_command_write()

    def before_save(self) -> None:
        mark_projection_validation_substage(
            "DOCUMENT_CHECKOUT_PROJECTION_COMMAND_GUARD"
        )
        require_document_command_write()
        mark_projection_validation_substage(
            "DOCUMENT_CHECKOUT_PROJECTION_FRAPPE_STANDARD_VALIDATION"
        )

    def before_validate(self) -> None:
        mark_projection_validation_substage(
            "DOCUMENT_CHECKOUT_PROJECTION_NORMALIZE_INPUT"
        )
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.tenant_id = tenant_text(self.tenant_id)
        self.project_global_id = canonical_uuid(
            self.project_global_id,
            _("Project Global ID"),
        )

    def validate(self) -> None:
        mark_projection_validation_substage(
            "DOCUMENT_CHECKOUT_PROJECTION_IMMUTABLE_IDENTITY"
        )
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _IDENTITY_FIELDS)
        mark_projection_validation_substage(
            "DOCUMENT_CHECKOUT_PROJECTION_POLICY_IDENTITY"
        )
        require_exact_parent(
            "NPI Engineering Project",
            self.project_global_id,
            {
                "global_id": self.project_global_id,
                "tenant_id": self.tenant_id,
            },
            _("The controlled document does not match its Project and tenant."),
        )
        policy = _load_exact_policy(
            self.policy_global_id,
            self.policy_version,
            self.policy_snapshot_hash,
        )
        expected_identity = document_domain_value(
            lambda: create_controlled_document(
                document_id=self.global_id,
                tenant_id=self.tenant_id,
                project_id=self.project_global_id,
                policy=policy,
                document_type_key=self.document_type_key,
                title=self.title,
                confidentiality_key=self.confidentiality_key,
            )
        )
        if any(
            str(current) != str(expected)
            for current, expected in (
                (self.document_number, expected_identity.document_number),
                (
                    self.document_number_key,
                    expected_identity.document_number_key,
                ),
                (self.policy_global_id, expected_identity.policy_ref.global_id),
                (self.policy_version, expected_identity.policy_ref.version),
                (
                    self.policy_snapshot_hash,
                    expected_identity.policy_ref.snapshot_hash,
                ),
            )
        ):
            from frappe import ValidationError, throw

            throw(
                _(
                    "The controlled document identity does not match its exact published policy."
                ),
                ValidationError,
            )
        mark_projection_validation_substage(
            "DOCUMENT_CHECKOUT_PROJECTION_DOMAIN_RECONSTRUCTION"
        )
        domain = document_domain_value(
            lambda: ControlledDocument(
                global_id=self.global_id,
                tenant_id=self.tenant_id,
                project_global_id=self.project_global_id,
                policy_ref=DocumentPolicyReference(
                    global_id=self.policy_global_id,
                    version=self.policy_version,
                    snapshot_hash=self.policy_snapshot_hash,
                ),
                document_number=self.document_number,
                document_number_key=self.document_number_key,
                document_type_key=self.document_type_key,
                title=self.title,
                confidentiality_key=self.confidentiality_key,
                version=self.optimistic_version,
                current_revision_id=self.current_revision_global_id or None,
                current_revision_major=(
                    self.current_revision_major
                    if self.current_revision_global_id
                    else None
                ),
                current_revision_minor=(
                    self.current_revision_minor
                    if self.current_revision_global_id
                    else None
                ),
                current_revision_hash=(
                    self.current_revision_snapshot_hash
                    if self.current_revision_global_id
                    else None
                ),
                current_lock_id=self.current_lock_global_id or None,
                current_lock_version=(
                    self.current_lock_version if self.current_lock_global_id else None
                ),
                current_lock_holder=(
                    self.current_lock_holder_user_id
                    if self.current_lock_global_id
                    else None
                ),
                current_lock_expires_at=(
                    _as_datetime(self.current_lock_expires_at)
                    if self.current_lock_global_id
                    else None
                ),
            ),
        )
        mark_projection_validation_substage(
            "DOCUMENT_CHECKOUT_PROJECTION_NORMALIZE_IDENTITY"
        )
        self.global_id = str(domain.global_id)
        self.tenant_id = domain.tenant_id
        self.project_global_id = str(domain.project_global_id)
        self.policy_global_id = str(domain.policy_ref.global_id)
        self.policy_version = domain.policy_ref.version
        self.policy_snapshot_hash = domain.policy_ref.snapshot_hash
        self.document_number = domain.document_number
        self.document_number_key = domain.document_number_key
        self.document_type_key = domain.document_type_key
        self.title = domain.title
        self.confidentiality_key = domain.confidentiality_key
        mark_projection_validation_substage(
            "DOCUMENT_CHECKOUT_PROJECTION_VERSION"
        )
        if previous is None:
            if (
                domain.version != 1
                or domain.current_revision_id is not None
                or domain.current_lock_id is not None
            ):
                from frappe import ValidationError, throw

                throw(
                    _(
                        "A new controlled document must start without a revision or edit lock at version one."
                    ),
                    ValidationError,
                )
        elif domain.version != int(previous.get("optimistic_version") or 0) + 1:
            from frappe import ValidationError, throw

            throw(
                _("Optimistic Version must advance by one."),
                ValidationError,
            )
        if previous is not None:
            mark_projection_validation_substage(
                "DOCUMENT_CHECKOUT_PROJECTION_REVISION"
            )
            _validate_revision_projection(self, previous)
            mark_projection_validation_substage(
                "DOCUMENT_CHECKOUT_PROJECTION_LOCK"
            )
            _validate_lock_projection(self, previous)
        mark_projection_validation_substage(
            "DOCUMENT_CHECKOUT_PROJECTION_NORMALIZE_PROJECTION"
        )
        self.current_revision_global_id = (
            str(domain.current_revision_id) if domain.current_revision_id else None
        )
        self.current_revision_major = domain.current_revision_major
        self.current_revision_minor = domain.current_revision_minor
        self.current_revision_snapshot_hash = domain.current_revision_hash
        self.current_lock_global_id = (
            str(domain.current_lock_id) if domain.current_lock_id else None
        )
        self.current_lock_version = domain.current_lock_version
        self.current_lock_holder_user_id = domain.current_lock_holder
        self.current_lock_expires_at = (
            frappe_utc_datetime_text(
                domain.current_lock_expires_at,
                _("Current Lock Expires At"),
            )
            if domain.current_lock_expires_at
            else None
        )
        self.optimistic_version = domain.version
        self.created_by_user_id = actor_text(
            self.created_by_user_id,
            _("Created By"),
        )
        self.created_at = frappe_utc_datetime_text(
            self.created_at,
            _("Created At"),
        )

    def on_update(self) -> None:
        mark_projection_validation_substage(
            "DOCUMENT_CHECKOUT_PROJECTION_POST_SAVE_HOOK"
        )

    def on_trash(self) -> None:
        deny_document_history_delete(
            self,
            target_global_id=self.global_id,
            target_version=self.optimistic_version,
        )


def _as_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        from datetime import UTC

        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _load_exact_policy(
    policy_global_id: object,
    policy_version: object,
    snapshot_hash: object,
) -> DocumentPolicyVersion:
    require_exact_parent(
        "NPI Document Policy",
        str(policy_global_id),
        {
            "global_id": str(policy_global_id),
            "enabled": 1,
        },
        _("Select an enabled document policy."),
    )
    row = frappe.db.get_value(
        "NPI Document Policy Version",
        {
            "policy_global_id": str(policy_global_id),
            "policy_version": policy_version,
        },
        [
            "global_id",
            "policy_global_id",
            "policy_key",
            "policy_version",
            "title",
            "publication_state",
            "document_types",
            "confidentiality_keys",
            "allowed_mime_types",
            "preview_mime_types",
            "maximum_file_bytes",
            "lock_lease_minutes",
            "snapshot_hash",
        ],
        as_dict=True,
    )
    if (
        not row
        or str(row.get("publication_state")) != DocumentPolicyState.PUBLISHED.value
        or str(row.get("snapshot_hash")) != str(snapshot_hash)
    ):
        frappe.throw(
            _("Select an exact published document policy version."),
            frappe.ValidationError,
        )
    try:
        rules = json_array(
            row.get("document_types"),
            _("Document Types"),
        )
        if not all(
            isinstance(value, dict) and set(value) == {"key", "prefix", "titleSource"}
            for value in rules
        ):
            frappe.throw(
                _("Select an exact published document policy version."),
                frappe.ValidationError,
            )
        return document_domain_value(
            lambda: DocumentPolicyVersion(
                global_id=row.get("global_id"),
                policy_global_id=row.get("policy_global_id"),
                policy_key=row.get("policy_key"),
                policy_version=row.get("policy_version"),
                title=row.get("title"),
                state=DocumentPolicyState.PUBLISHED,
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
                        row.get("confidentiality_keys"),
                        _("Confidentiality Keys"),
                    )
                ),
                allowed_mime_types=tuple(
                    json_array(
                        row.get("allowed_mime_types"),
                        _("Allowed File Formats"),
                    )
                ),
                preview_mime_types=tuple(
                    json_array(
                        row.get("preview_mime_types"),
                        _("Preview File Formats"),
                    )
                ),
                maximum_file_bytes=row.get("maximum_file_bytes"),
                lock_lease_minutes=row.get("lock_lease_minutes"),
                snapshot_hash=str(row.get("snapshot_hash")),
            )
        )
    except (AttributeError, TypeError):
        frappe.throw(
            _("Select an exact published document policy version."),
            frappe.ValidationError,
        )
        raise AssertionError("Frappe validation must raise.")


def _validate_revision_projection(document: object, previous: object) -> None:
    old = (
        previous.get("current_revision_global_id"),
        previous.get("current_revision_major"),
        previous.get("current_revision_minor"),
        previous.get("current_revision_snapshot_hash"),
    )
    new = (
        document.get("current_revision_global_id"),
        document.get("current_revision_major"),
        document.get("current_revision_minor"),
        document.get("current_revision_snapshot_hash"),
    )
    if old == new:
        return
    if old[0] not in (None, "") and new[0] in (None, ""):
        frappe.throw(
            _("The current document revision cannot be cleared."),
            frappe.ValidationError,
        )
    expected = {
        "global_id": new[0],
        "tenant_id": document.get("tenant_id"),
        "project_global_id": document.get("project_global_id"),
        "document_global_id": document.get("global_id"),
        "major": new[1],
        "minor": new[2],
        "snapshot_hash": new[3],
        "predecessor_revision_global_id": (None if old[0] in (None, "") else old[0]),
    }
    require_exact_parent(
        "NPI Document Revision",
        new[0],
        expected,
        _("The current revision projection does not match an exact successor."),
    )


def _validate_lock_projection(document: object, previous: object) -> None:
    old = (
        previous.get("current_lock_global_id"),
        previous.get("current_lock_version"),
        previous.get("current_lock_holder_user_id"),
        _optional_datetime(previous.get("current_lock_expires_at")),
    )
    new = (
        document.get("current_lock_global_id"),
        document.get("current_lock_version"),
        document.get("current_lock_holder_user_id"),
        _optional_datetime(document.get("current_lock_expires_at")),
    )
    if old == new:
        return
    if old[0] not in (None, ""):
        terminal = require_exact_parent(
            "NPI Document Lock Event",
            {
                "lock_global_id": old[0],
                "lock_version": int(old[1] or 0) + 1,
            },
            {
                "tenant_id": document.get("tenant_id"),
                "project_global_id": document.get("project_global_id"),
                "document_global_id": document.get("global_id"),
                "holder_user_id": old[2],
            },
            _("The prior edit lock does not have an exact terminal event."),
            extra_fields=("event_type",),
        )
        if str(terminal.get("event_type")) not in {
            "released",
            "recovered",
            "expired",
        }:
            frappe.throw(
                _("The prior edit lock does not have an exact terminal event."),
                frappe.ValidationError,
            )
    if new[0] in (None, ""):
        return
    if old[0] == new[0]:
        frappe.throw(
            _("An active edit lock cannot be rewritten."),
            frappe.ValidationError,
        )
    require_exact_parent(
        "NPI Document Lock Event",
        {
            "lock_global_id": new[0],
            "lock_version": new[1],
        },
        {
            "tenant_id": document.get("tenant_id"),
            "project_global_id": document.get("project_global_id"),
            "document_global_id": document.get("global_id"),
            "event_type": "acquired",
            "holder_user_id": new[2],
            "expires_at": document.get("current_lock_expires_at"),
        },
        _("The current edit lock does not match an exact acquisition event."),
    )


def _optional_datetime(value: object) -> datetime | None:
    return None if value in (None, "") else _as_datetime(value)
