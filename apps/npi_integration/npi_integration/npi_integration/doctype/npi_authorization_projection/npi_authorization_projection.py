from __future__ import annotations

import json
from datetime import UTC

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    assert_immutable_fields,
    canonical_uuid,
    frappe_utc_datetime_text,
    lowercase_sha256,
    positive_integer,
    required_text,
    tenant_text,
    utc_datetime_text,
)
from npi_integration.authorization_projection.frappe_validation import (
    deny_authorization_projection_delete,
    require_authorization_projection_write,
)


class NPIAuthorizationProjection(Document):
    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_authorization_projection_write()

    def before_save(self) -> None:
        require_authorization_projection_write()

    def before_validate(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(
                self,
                previous,
                (
                    "global_id",
                    "projection_key_hash",
                    "tenant_id",
                    "source_subject_hash",
                    "target_user_id",
                ),
            )
        self.projection_key_hash = lowercase_sha256(
            self.projection_key_hash,
            _("Projection Key Hash"),
        )
        self.source_subject_hash = lowercase_sha256(
            self.source_subject_hash,
            _("Source Subject Hash"),
        )
        self.source_event_hash = lowercase_sha256(
            self.source_event_hash,
            _("Source Event Hash"),
        )
        self.projection_hash = lowercase_sha256(
            self.projection_hash,
            _("Projection Hash"),
        )
        self.target_user_id = required_text(
            self.target_user_id,
            _("Target User"),
            255,
        )
        self.source_event_id = canonical_uuid(
            self.source_event_id,
            _("Source Event ID"),
        )
        self.source_version = positive_integer(
            self.source_version,
            _("Source Version"),
        )
        if self.state not in {"enabled", "disabled"}:
            frappe.throw(
                _("Select a supported authorization projection state."),
                frappe.ValidationError,
            )
        roles = _json_list(self.roles)
        project_access = _json_list(self.project_access)
        organization_scopes = _json_list(self.organization_scopes)
        if self.state == "disabled" and (
            roles or project_access or organization_scopes
        ):
            frappe.throw(
                _("A disabled authorization projection cannot retain access."),
                frappe.ValidationError,
            )
        issued_at = utc_datetime_text(self.issued_at, _("Issued At"))
        expires_at = utc_datetime_text(self.expires_at, _("Expires At"))
        if expires_at <= issued_at:
            frappe.throw(
                _("Authorization projection expiry is invalid."),
                frappe.ValidationError,
            )
        self.roles = json.dumps(roles, ensure_ascii=False, separators=(",", ":"))
        self.project_access = json.dumps(
            project_access,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        self.organization_scopes = json.dumps(
            organization_scopes,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        self.issued_at = frappe_utc_datetime_text(issued_at, _("Issued At"))
        self.expires_at = frappe_utc_datetime_text(expires_at, _("Expires At"))
        self.applied_at = frappe_utc_datetime_text(
            utc_datetime_text(self.applied_at, _("Applied At")),
            _("Applied At"),
        )
        self.source_trace_id = required_text(
            self.source_trace_id,
            _("Source Trace ID"),
            128,
        )
        self.request_id = canonical_uuid(self.request_id, _("Request ID"))

    def on_trash(self) -> None:
        deny_authorization_projection_delete()


def _json_list(value: object) -> list[object]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            frappe.throw(
                _("The authorization projection is invalid."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.") from error
    if not isinstance(value, list):
        frappe.throw(
            _("The authorization projection is invalid."),
            frappe.ValidationError,
        )
    return value
