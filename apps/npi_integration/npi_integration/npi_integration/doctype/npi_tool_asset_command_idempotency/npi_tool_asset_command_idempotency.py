from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    canonical_json,
    canonical_uuid,
    json_object,
    lowercase_sha256,
    optional_uuid,
    require_exact_parent,
    required_text,
    tenant_text,
    utc_datetime_text,
)
from npi_core.tooling.domain import sha256_json
from npi_integration.tool_asset_request.domain import TOOL_ASSET_OPERATION
from npi_integration.tool_asset_request.frappe_validation import (
    deny_tool_asset_history_delete,
    require_tool_asset_request_write,
)
from npi_integration.tool_asset_request.execution_domain import (
    TOOL_ASSET_EXECUTION_OPERATIONS,
    TOOL_ASSET_EXECUTION_SCHEMA_VERSION,
)
from npi_integration.tool_asset_request.execution_frappe_validation import (
    deny_tool_asset_execution_history_delete,
    require_tool_asset_execution_idempotency_write,
)


class NPIToolAssetCommandIdempotency(Document):
    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        if self._is_execution_v2():
            require_tool_asset_execution_idempotency_write()
        else:
            require_tool_asset_request_write()

    def before_save(self) -> None:
        if self._is_execution_v2():
            require_tool_asset_execution_idempotency_write()
        else:
            require_tool_asset_request_write()

    def before_validate(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.project_global_id = canonical_uuid(self.project_global_id, _("Project Global ID"))
        self.request_global_id = optional_uuid(self.request_global_id, _("Tool Asset Request Global ID"))
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        self.receipt_key = required_text(self.receipt_key, _("Receipt Key"), maximum=255)
        self.actor_user_id = required_text(self.actor_user_id, _("Actor User ID"), maximum=254)
        if self._is_execution_v2():
            if int(self.schema_version or 0) != TOOL_ASSET_EXECUTION_SCHEMA_VERSION or self.operation not in TOOL_ASSET_EXECUTION_OPERATIONS:
                frappe.throw(_("Select the operation-specific Tool Asset execution command."), frappe.ValidationError)
            for fieldname, label in (
                ("source_stream_key_hash", _("Tool Asset Source Stream Key Hash")),
                ("profile_snapshot_hash", _("Tool Asset Execution Profile Snapshot Hash")),
                ("mapping_expectation_hash", _("Tool Asset Mapping Expectation Hash")),
            ):
                setattr(self, fieldname, lowercase_sha256(getattr(self, fieldname), label))
        elif self.operation != TOOL_ASSET_OPERATION:
            frappe.throw(_("Select the operation-specific Tool Asset command."), frappe.ValidationError)
        self.idempotency_key_hash = lowercase_sha256(self.idempotency_key_hash, _("Idempotency Key Hash"))
        self.payload_hash = lowercase_sha256(self.payload_hash, _("Tool Asset Request Payload Hash"))
        created_at = utc_datetime_text(self.created_at, _("Created At"))
        utc_datetime_text(self.updated_at, _("Updated At"))
        before = self.get_doc_before_save()
        if before is not None:
            immutable = (
                "global_id", "receipt_key", "tenant_id", "project_global_id", "actor_user_id",
                "operation", "idempotency_key_hash", "payload_hash", "source_stream_key_hash",
                "profile_snapshot_hash", "mapping_expectation_hash",
            )
            if (
                int(before.schema_version or 0) != int(self.schema_version or 0)
                or any(getattr(before, name) != getattr(self, name) for name in immutable)
                or utc_datetime_text(before.created_at, _("Created At")) != created_at
            ):
                frappe.throw(_("The Tool Asset command receipt identity cannot be changed."), frappe.PermissionError)
            if int(before.sealed or 0) == 1:
                frappe.throw(_("A sealed Tool Asset command receipt cannot be changed."), frappe.PermissionError)
        if self.sealed:
            if not self.request_global_id or not self.response_payload or not self.response_hash:
                frappe.throw(_("A sealed Tool Asset command receipt requires its exact response."), frappe.ValidationError)
            request = require_exact_parent(
                "NPI Tool Asset Request",
                self.request_global_id,
                {
                    "global_id": self.request_global_id,
                    "tenant_id": self.tenant_id,
                    "project_global_id": self.project_global_id,
                    "actor_user_id": self.actor_user_id,
                    "operation": self.operation,
                },
                _("The sealed Tool Asset request is unavailable."),
                extra_fields=("payload_hash",),
            )
            response = json_object(self.response_payload, _("Sealed Response Payload"))
            if self._is_execution_v2():
                response_request = response.get("request")
                response_matches = (
                    response.get("requestGlobalId") == self.request_global_id
                    and isinstance(response_request, dict)
                    and response_request.get("payloadHash")
                    == str(request.payload_hash)
                )
            else:
                response_matches = (
                    response.get("globalId") == self.request_global_id
                    and response.get("payloadHash") == str(request.payload_hash)
                )
            if not response_matches:
                frappe.throw(_("The sealed response does not match its exact Tool Asset request."), frappe.ValidationError)
            if lowercase_sha256(self.response_hash, _("Sealed Response Hash")) != sha256_json(response):
                frappe.throw(_("The sealed response hash does not match its payload."), frappe.ValidationError)
            self.response_payload = canonical_json(response)
        elif self.request_global_id or self.response_payload or self.response_hash:
            frappe.throw(_("An unsealed Tool Asset command receipt cannot contain a response."), frappe.ValidationError)

    def on_trash(self) -> None:
        if self._is_execution_v2():
            deny_tool_asset_execution_history_delete()
        else:
            deny_tool_asset_history_delete(self)

    def _is_execution_v2(self) -> bool:
        return int(getattr(self, "schema_version", 0) or 0) == TOOL_ASSET_EXECUTION_SCHEMA_VERSION or getattr(self, "operation", None) in TOOL_ASSET_EXECUTION_OPERATIONS
