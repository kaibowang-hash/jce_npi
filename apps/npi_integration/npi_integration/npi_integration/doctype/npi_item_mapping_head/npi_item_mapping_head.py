from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    assert_immutable_fields,
    canonical_json,
    canonical_uuid,
    frappe_utc_datetime_text,
    json_object,
    lowercase_sha256,
    positive_integer,
    require_exact_parent,
    required_text,
    tenant_text,
    utc_datetime_text,
)
from npi_integration.item_publish.domain import canonical_hash
from npi_integration.item_publish.frappe_validation import (
    deny_item_history_delete,
    require_item_mapping_write,
)


class NPIItemMappingHead(Document):
    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_item_mapping_write()

    def before_save(self) -> None:
        require_item_mapping_write()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("current_observation", _("Current Item Mapping Observation")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(
                self,
                previous,
                (
                    "global_id",
                    "tenant_id",
                    "project_global_id",
                    "source_stream_key_hash",
                    "engineering_item_id",
                    "formal_item_code",
                ),
            )
        self.source_stream_key_hash = lowercase_sha256(
            self.source_stream_key_hash, _("Item Source Stream Key Hash")
        )
        self.current_observation_hash = lowercase_sha256(
            self.current_observation_hash, _("Current Mapping Observation Hash")
        )
        self.head_hash = lowercase_sha256(
            self.head_hash, _("Item Mapping Head Hash")
        )
        self.engineering_item_id = required_text(
            self.engineering_item_id, _("Engineering Item ID"), 128
        )
        self.formal_item_code = required_text(
            self.formal_item_code, _("Observed Formal Item Code"), 140
        )
        self.target_version = required_text(
            self.target_version, _("Observed Target Version"), 140
        )
        mapping_version = positive_integer(
            self.mapping_version, _("Item Mapping Version")
        )
        expected_version = 1 if previous is None else int(previous.mapping_version) + 1
        if mapping_version != expected_version:
            frappe.throw(
                _("The Item mapping head version must advance by one."),
                frappe.ValidationError,
            )
        require_exact_parent(
            "NPI Item Mapping Observation",
            self.current_observation,
            {
                "global_id": self.current_observation,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "source_stream_key_hash": self.source_stream_key_hash,
                "engineering_item_id": self.engineering_item_id,
                "mapping_version": mapping_version,
                "formal_item_code": self.formal_item_code,
                "target_version": self.target_version,
                "authority": "authoritative_sandbox",
                "disposition": "advanced",
                "observation_hash": self.current_observation_hash,
            },
            _("The exact authoritative Item mapping observation is unavailable."),
        )
        updated_at = utc_datetime_text(self.updated_at, _("Updated At"))
        expected_snapshot = {
            "schemaVersion": 1,
            "globalId": self.global_id,
            "tenantId": self.tenant_id,
            "projectGlobalId": self.project_global_id,
            "sourceStreamKeyHash": self.source_stream_key_hash,
            "engineeringItemId": self.engineering_item_id,
            "mappingVersion": mapping_version,
            "formalItemCode": self.formal_item_code,
            "targetVersion": self.target_version,
            "currentObservationGlobalId": self.current_observation,
            "currentObservationHash": self.current_observation_hash,
            "updatedAt": updated_at,
        }
        snapshot = json_object(
            self.head_snapshot, _("Item Mapping Head Snapshot")
        )
        if snapshot != expected_snapshot:
            frappe.throw(
                _("The Item mapping head snapshot does not match its fields."),
                frappe.ValidationError,
            )
        self.head_snapshot = canonical_json(expected_snapshot)
        if canonical_hash(expected_snapshot) != self.head_hash:
            frappe.throw(
                _("The Item mapping head hash does not match its snapshot."),
                frappe.ValidationError,
            )
        self.updated_at = frappe_utc_datetime_text(updated_at, _("Updated At"))

    def on_trash(self) -> None:
        deny_item_history_delete()
