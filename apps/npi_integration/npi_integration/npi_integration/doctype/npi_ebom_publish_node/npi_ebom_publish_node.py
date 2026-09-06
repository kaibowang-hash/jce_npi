from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    canonical_json,
    canonical_uuid,
    json_array,
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


class NPIEBOMPublishNode(Document):
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
            ("publish_request", _("EBOM Publish Request")),
            ("request_global_id", _("Publish Request Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("ebom_global_id", _("Engineering BOM Global ID")),
            ("revision_global_id", _("EBOM Revision Global ID")),
            ("line_global_id", _("EBOM Line Global ID")),
            ("mapping_observation", _("Mapping Observation")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_publish_history_update()
        if self.publish_request != self.request_global_id:
            frappe.throw(
                _("The publish node must match its exact request Global ID."),
                frappe.ValidationError,
            )
        require_exact_parent(
            "NPI EBOM Publish Request",
            self.publish_request,
            {
                "global_id": self.request_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "ebom_global_id": self.ebom_global_id,
                "revision_global_id": self.revision_global_id,
                "target_mode": "mock",
                "dispatch_allowed": 0,
            },
            _("The exact EBOM publish request is unavailable."),
        )
        line = require_exact_parent(
            "NPI Engineering BOM Line",
            self.line_global_id,
            {
                "global_id": self.line_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "ebom_global_id": self.ebom_global_id,
                "revision_global_id": self.revision_global_id,
                "line_key": self.line_key,
                "engineering_item_id": self.engineering_item_id,
            },
            _("The exact EBOM line is unavailable."),
            extra_fields=("line_snapshot", "line_hash"),
        )
        self.line_key = required_text(self.line_key, _("EBOM Line Key"), maximum=64)
        self.engineering_item_id = required_text(
            self.engineering_item_id, _("Engineering Item ID"), maximum=128
        )
        supplied_line = json_object(
            self.line_snapshot, _("Exact EBOM Line Snapshot")
        )
        stored_line = json_object(line.line_snapshot, _("Exact EBOM Line Snapshot"))
        if supplied_line != stored_line:
            frappe.throw(
                _("The publish node does not match the exact EBOM line snapshot."),
                frappe.ValidationError,
            )
        self.line_snapshot = canonical_json(supplied_line)
        if lowercase_sha256(self.line_hash, _("EBOM Line Hash")) != str(line.line_hash):
            frappe.throw(
                _("The publish node does not match the exact EBOM line hash."),
                frappe.ValidationError,
            )
        self.mapping_version = nonnegative_integer(
            self.mapping_version, _("Mapping Version")
        )
        mapping = require_exact_parent(
            "NPI EBOM Publish Mapping Observation",
            self.mapping_observation,
            {
                "global_id": self.mapping_observation,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "line_global_id": self.line_global_id,
                "engineering_item_id": self.engineering_item_id,
                "mapping_state": self.mapping_state,
                "mapping_version": self.mapping_version,
            },
            _("The exact mapping observation is unavailable."),
            extra_fields=(
                "formal_item_code",
                "formal_mbom_id",
                "target_version",
                "observed_at",
            ),
        )
        operations = tuple(
            str(value)
            for value in json_array(self.operations, _("Server-Derived Operations"))
        )
        if self.mapping_state == "unmapped":
            expected = ("create_item", "create_or_update_mbom")
            expected_state = "validated"
        elif self.mapping_state == "current":
            expected = ("update_item_engineering_fields", "create_or_update_mbom")
            expected_state = "validated"
        elif self.mapping_state in {"stale", "conflict"}:
            expected = ()
            expected_state = "blocked_mapping"
        else:
            frappe.throw(_("Select a supported mapping state."), frappe.ValidationError)
        if operations != expected or self.result_state != expected_state:
            frappe.throw(
                _("The publish node operations do not match its mapping state."),
                frappe.ValidationError,
            )
        self.operations = canonical_json(list(operations))
        input_payload = {
            "line": {**supplied_line, "lineHash": self.line_hash},
            "mapping": {
                "state": self.mapping_state,
                "version": self.mapping_version,
                "formalItemCode": mapping.formal_item_code or None,
                "formalMbomId": mapping.formal_mbom_id or None,
                "targetVersion": mapping.target_version or None,
                "observedAt": mapping.observed_at or None,
            },
            "operations": list(operations),
        }
        if lowercase_sha256(
            self.input_hash, _("Publish Node Input Hash")
        ) != sha256_json(input_payload):
            frappe.throw(
                _("The publish node input hash does not match its exact content."),
                frappe.ValidationError,
            )
        utc_datetime_text(self.created_at, _("Created At"))

    def on_trash(self) -> None:
        deny_publish_history_delete(self, target_global_id=self.global_id)
