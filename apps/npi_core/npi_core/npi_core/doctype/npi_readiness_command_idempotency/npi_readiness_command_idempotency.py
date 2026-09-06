from __future__ import annotations

import hashlib
from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    actor_text,
    assert_immutable_fields,
    canonical_json,
    frappe_utc_datetime_text,
    json_object,
    lowercase_sha256,
    optional_uuid,
    require_exact_parent,
    tenant_text,
    utc_datetime_text,
)
from npi_core.readiness.frappe_validation import (
    deny_readiness_history_delete,
    require_readiness_command_write,
)
from npi_core.readiness.metadata_validation import canonical_readiness_identity
from npi_core.readiness.response_validation import validate_receipt_response


_IDENTITY_FIELDS = (
    "global_id",
    "receipt_key",
    "tenant_id",
    "project_global_id",
    "actor_user_id",
    "operation",
    "idempotency_key_hash",
    "payload_hash",
    "created_at",
)
_OPERATIONS = {
    "readiness_template.create": "readiness_template",
    "readiness_template.edit": "readiness_template_version",
    "readiness_template.publish": "readiness_template_version",
    "readiness_instance.initialize": "readiness_instance_revision",
    "readiness_instance.revise": "readiness_instance_revision",
}


class NPIReadinessCommandIdempotency(Document):
    """Actor-bound readiness receipt with a one-way success seal."""

    def autoname(self) -> None:
        canonical_readiness_identity(self)

    def before_insert(self) -> None:
        require_readiness_command_write()

    def before_save(self) -> None:
        require_readiness_command_write()

    def before_validate(self) -> None:
        canonical_readiness_identity(self)
        self.tenant_id = tenant_text(self.tenant_id)
        self.project_global_id = optional_uuid(
            self.project_global_id,
            _("Project Global ID"),
        )
        self.target_global_id = optional_uuid(
            self.target_global_id,
            _("Target Global ID"),
        )

    def validate(self) -> None:
        self.actor_user_id = actor_text(self.actor_user_id, _("Actor User ID"))
        expected_target_type = _OPERATIONS.get(str(self.operation))
        if expected_target_type is None:
            frappe.throw(_("Select a supported operation."), frappe.ValidationError)
        is_instance_operation = str(self.operation).startswith("readiness_instance.")
        if is_instance_operation != (self.project_global_id is not None):
            frappe.throw(_("The command failed validation."), frappe.ValidationError)
        self.idempotency_key_hash = lowercase_sha256(
            self.idempotency_key_hash,
            _("Idempotency Key Hash"),
        )
        self.payload_hash = lowercase_sha256(self.payload_hash, _("Payload Hash"))
        expected_key = _sha256_json(
            {
                "tenantId": self.tenant_id,
                "projectGlobalId": self.project_global_id,
                "actorUserId": self.actor_user_id.casefold(),
                "operation": self.operation,
                "idempotencyKeyHash": self.idempotency_key_hash,
            }
        )
        if self.receipt_key not in (None, "", expected_key):
            frappe.throw(
                _("Receipt Key does not match the actor-bound command scope."),
                frappe.ValidationError,
            )
        self.receipt_key = expected_key
        if self.project_global_id is not None:
            require_exact_parent(
                "NPI Engineering Project",
                self.project_global_id,
                {
                    "global_id": self.project_global_id,
                    "tenant_id": self.tenant_id,
                },
                _("The Project is unavailable for this NPI Readiness Instance."),
            )
        response = json_object(self.response_payload, _("Response Payload"))
        if type(self.sealed) not in {int, bool} or int(self.sealed) not in {0, 1}:
            frappe.throw(_("Sealed must be a checkbox value."), frappe.ValidationError)
        created_at = utc_datetime_text(self.created_at, _("Created At"))
        updated_at = utc_datetime_text(self.updated_at, _("Updated At"))
        if updated_at < created_at:
            frappe.throw(
                _("Updated At cannot be earlier than Created At."),
                frappe.ValidationError,
            )
        previous = self.get_doc_before_save()
        if previous is None:
            if (
                int(self.sealed or 0) != 0
                or self.target_object_type not in (None, "")
                or self.target_global_id is not None
                or response
                or self.response_hash not in (None, "")
            ):
                frappe.throw(_("The command failed validation."), frappe.ValidationError)
        else:
            assert_immutable_fields(self, previous, _IDENTITY_FIELDS)
            if (
                int(previous.get("sealed") or 0) != 0
                or int(self.sealed or 0) != 1
                or self.target_object_type != expected_target_type
                or self.target_global_id is None
                or not response
            ):
                frappe.throw(
                    _("NPI readiness history cannot be changed."),
                    frappe.PermissionError,
                )
            response = validate_receipt_response(
                str(self.operation),
                response,
                target_global_id=self.target_global_id,
                project_global_id=self.project_global_id,
            )
            expected_response_hash = _sha256_json(response)
            if self.response_hash not in (None, "", expected_response_hash):
                frappe.throw(
                    _("Response Hash does not match the sealed response."),
                    frappe.ValidationError,
                )
            self.response_hash = expected_response_hash
        self.response_payload = canonical_json(response)
        self.created_at = frappe_utc_datetime_text(
            datetime.fromisoformat(created_at.replace("Z", "+00:00")),
            _("Created At"),
        )
        self.updated_at = frappe_utc_datetime_text(
            datetime.fromisoformat(updated_at.replace("Z", "+00:00")),
            _("Updated At"),
        )

    def on_trash(self) -> None:
        deny_readiness_history_delete(self)


def _sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
