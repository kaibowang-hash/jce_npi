from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    assert_immutable_fields,
    canonical_json,
    frappe_utc_datetime_text,
    json_object,
    lowercase_sha256,
    positive_integer,
    required_text,
    tenant_text,
    utc_datetime_text,
)
from npi_integration.inbound_project.domain import (
    ProjectSourceContractError,
    ProjectSourceObjectType,
    SourceStreamIdentity,
    canonical_json_hash,
)
from npi_integration.inbound_project.frappe_validation import (
    deny_inbound_project_delete,
    require_source_binding_write,
)


_IMMUTABLE_SOURCE_FIELDS = (
    "source_key_hash",
    "schema_version",
    "tenant_id",
    "profile_id",
    "profile_version",
    "source_system",
    "target_system",
    "source_object_type",
    "source_object_id",
)
_BOUND_FIELDS = (
    "bound_project_global_id",
    "bound_inbox_message",
    "bound_version",
    "bound_payload_hash",
    "bound_policy_snapshot",
    "bound_policy_hash",
)


class NPIProjectSourceBinding(Document):
    def autoname(self) -> None:
        self.source_key_hash = lowercase_sha256(
            self.source_key_hash, _("Source Key Hash")
        )
        self.name = self.source_key_hash

    def before_insert(self) -> None:
        require_source_binding_write()

    def before_save(self) -> None:
        require_source_binding_write()

    def before_validate(self) -> None:
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _IMMUTABLE_SOURCE_FIELDS)
            if previous.bound_project_global_id:
                assert_immutable_fields(self, previous, _BOUND_FIELDS)
        if positive_integer(self.schema_version, _("Schema Version")) != 1:
            frappe.throw(
                _("Select the supported Project source-binding schema version."),
                frappe.ValidationError,
            )
        if self.source_system != "ERPNEXT" or self.target_system != "NPI_ONE":
            frappe.throw(
                _("Project source-binding system ownership is invalid."),
                frappe.ValidationError,
            )
        try:
            identity = SourceStreamIdentity(
                tenant_id=self.tenant_id,
                profile_id=self.profile_id,
                object_type=ProjectSourceObjectType(self.source_object_type),
                source_object_id=self.source_object_id,
            )
        except (ProjectSourceContractError, ValueError) as error:
            frappe.throw(
                _("The Project source-binding identity is invalid."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.") from error
        self.profile_id = identity.profile_id
        positive_integer(self.profile_version, _("Source Profile Version"))
        if lowercase_sha256(self.source_key_hash, _("Source Key Hash")) != identity.key_hash:
            frappe.throw(
                _("The Project source key hash does not match its identity."),
                frappe.ValidationError,
            )
        positive_integer(self.highest_received_version, _("Highest Received Version"))
        lowercase_sha256(self.highest_payload_hash, _("Highest Payload Hash"))
        required_text(self.highest_inbox_message, _("Highest Inbox Message"), 140)
        if self.stream_state not in {"unbound", "bound", "conflicted"}:
            frappe.throw(
                _("Select a supported Project source stream state."),
                frappe.ValidationError,
            )
        bound_values = [getattr(self, fieldname) for fieldname in _BOUND_FIELDS]
        if any(bound_values) != all(bound_values):
            frappe.throw(
                _("Project source binding fields must be present together."),
                frappe.ValidationError,
            )
        if self.stream_state == "bound" and not all(bound_values):
            frappe.throw(
                _("A bound Project source stream requires the exact Project result."),
                frappe.ValidationError,
            )
        if self.stream_state == "unbound" and any(bound_values):
            frappe.throw(
                _("An unbound Project source stream cannot contain a Project result."),
                frappe.ValidationError,
            )
        if all(bound_values):
            positive_integer(self.bound_version, _("Bound Source Version"))
            lowercase_sha256(self.bound_payload_hash, _("Bound Payload Hash"))
            policy = json_object(self.bound_policy_snapshot, _("Bound Policy Snapshot"))
            self.bound_policy_snapshot = canonical_json(policy)
            if lowercase_sha256(
                self.bound_policy_hash, _("Bound Policy Hash")
            ) != canonical_json_hash(policy):
                frappe.throw(
                    _("The bound policy hash does not match its snapshot."),
                    frappe.ValidationError,
                )
        optimistic_version = positive_integer(
            self.optimistic_version, _("Optimistic Version")
        )
        previous_version = int(previous.optimistic_version) if previous is not None else 0
        if optimistic_version != previous_version + 1:
            frappe.throw(
                _("The Project source binding version must advance by one."),
                frappe.ValidationError,
            )
        if self.last_processing_code:
            self.last_processing_code = required_text(
                self.last_processing_code, _("Last Processing Code"), 128
            )
        if self.last_processed_at:
            last_processed_at = utc_datetime_text(
                self.last_processed_at, _("Last Processed At")
            )
            self.last_processed_at = frappe_utc_datetime_text(
                last_processed_at, _("Last Processed At")
            )
        updated_at = utc_datetime_text(self.updated_at, _("Updated At"))
        self.updated_at = frappe_utc_datetime_text(updated_at, _("Updated At"))

    def on_trash(self) -> None:
        deny_inbound_project_delete()
