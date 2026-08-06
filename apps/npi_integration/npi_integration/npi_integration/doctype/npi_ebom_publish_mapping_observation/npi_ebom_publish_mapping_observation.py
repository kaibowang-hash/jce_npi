from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    canonical_json,
    canonical_uuid,
    json_object,
    lowercase_sha256,
    nonnegative_integer,
    require_exact_parent,
    required_text,
    tenant_text,
    utc_datetime_text,
)
from npi_integration.publish_request.domain import sha256_json
from npi_integration.publish_request.frappe_validation import (
    deny_publish_history_delete,
    deny_publish_history_update,
    require_publish_request_write,
)


class NPIEBOMPublishMappingObservation(Document):
    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_publish_request_write()

    def before_save(self) -> None:
        require_publish_request_write()
        if self.get_doc_before_save() is not None:
            deny_publish_history_update()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("line_global_id", _("EBOM Line Global ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_publish_history_update()
        require_exact_parent(
            "NPI Engineering BOM Line",
            self.line_global_id,
            {
                "global_id": self.line_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "engineering_item_id": self.engineering_item_id,
            },
            _("The exact EBOM line is unavailable."),
        )
        self.engineering_item_id = required_text(
            self.engineering_item_id, _("Engineering Item ID"), maximum=128
        )
        self.mapping_version = nonnegative_integer(
            self.mapping_version, _("Mapping Version")
        )
        if (
            self.source_system != "NPI_ONE"
            or self.mapping_state != "unmapped"
            or self.mapping_version != 0
            or self.formal_item_code
            or self.formal_mbom_id
            or self.target_version
            or self.observed_at
        ):
            frappe.throw(
                _("Phase 5 can persist only an unmapped Mock observation without ERP identifiers."),
                frappe.ValidationError,
            )
        snapshot = json_object(
            self.observation_snapshot, _("Mapping Observation Snapshot")
        )
        expected = {
            "schemaVersion": 1,
            "globalId": self.global_id,
            "projectGlobalId": self.project_global_id,
            "lineGlobalId": self.line_global_id,
            "engineeringItemId": self.engineering_item_id,
            "state": "unmapped",
            "version": 0,
            "formalItemCode": None,
            "formalMbomId": None,
            "targetVersion": None,
            "observedAt": None,
            "sourceSystem": "NPI_ONE",
        }
        if snapshot != expected:
            frappe.throw(
                _("The mapping observation snapshot does not match its fields."),
                frappe.ValidationError,
            )
        self.observation_snapshot = canonical_json(expected)
        if lowercase_sha256(
            self.observation_hash, _("Mapping Observation Hash")
        ) != sha256_json(expected):
            frappe.throw(
                _("The mapping observation hash does not match its fields."),
                frappe.ValidationError,
            )
        utc_datetime_text(self.created_at, _("Created At"))

    def on_trash(self) -> None:
        deny_publish_history_delete(self, target_global_id=self.global_id)
