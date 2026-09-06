from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    canonical_json,
    canonical_uuid,
    frappe_utc_datetime_text,
    json_object,
    lowercase_sha256,
    nonnegative_integer,
    positive_integer,
    required_text,
    tenant_text,
    utc_datetime_text,
)
from npi_integration.item_publish.domain import (
    ItemResultAuthority,
    canonical_hash,
)
from npi_integration.item_publish.frappe_validation import (
    deny_item_history_delete,
    deny_item_history_update,
    require_item_mapping_write,
)


class NPIItemMappingObservation(Document):
    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_item_mapping_write()

    def before_save(self) -> None:
        require_item_mapping_write()
        if self.get_doc_before_save() is not None:
            deny_item_history_update()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("request_global_id", _("Item Publish Request")),
            ("outbox_event_id", _("Item Outbox Event ID")),
            ("attempt_global_id", _("Item Publish Attempt")),
            ("result_global_id", _("Item Publish Result")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_item_history_update()
        self.engineering_item_id = required_text(
            self.engineering_item_id, _("Engineering Item ID"), 128
        )
        self.profile_id = required_text(
            self.profile_id, _("Item Execution Profile ID"), 128
        )
        self.environment_code = required_text(
            self.environment_code, _("Target Environment Code"), 64
        )
        self.profile_version = positive_integer(
            self.profile_version, _("Item Execution Profile Version")
        )
        previous_version = nonnegative_integer(
            self.previous_mapping_version, _("Previous Item Mapping Version")
        )
        self.source_stream_key_hash = lowercase_sha256(
            self.source_stream_key_hash, _("Item Source Stream Key Hash")
        )
        for fieldname, label in (
            ("target_result_hash", _("Exact Target Result Hash")),
            ("observation_hash", _("Item Mapping Observation Hash")),
        ):
            setattr(self, fieldname, lowercase_sha256(getattr(self, fieldname), label))
        if self.previous_observation_hash:
            self.previous_observation_hash = lowercase_sha256(
                self.previous_observation_hash,
                _("Previous Mapping Observation Hash"),
            )
        try:
            authority = ItemResultAuthority(self.authority)
        except ValueError as error:
            frappe.throw(
                _("The Item mapping observation authority is invalid."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.") from error
        if self.disposition not in {
            "advanced",
            "non_authoritative",
            "observed_conflict",
        }:
            frappe.throw(
                _("The Item mapping observation disposition is invalid."),
                frappe.ValidationError,
            )
        if authority is ItemResultAuthority.SYNTHETIC:
            if (
                self.disposition != "non_authoritative"
                or self.mapping_version not in (None, "", 0)
                or self.formal_item_code
                or self.target_version
            ):
                frappe.throw(
                    _("Synthetic Item proof cannot contain or advance a formal mapping."),
                    frappe.ValidationError,
                )
            mapping_version = None
        else:
            if authority is not ItemResultAuthority.AUTHORITATIVE_SANDBOX:
                frappe.throw(
                    _("Only Sandbox authority can produce a formal Item mapping observation."),
                    frappe.ValidationError,
                )
            if self.disposition == "non_authoritative":
                frappe.throw(
                    _("An authoritative Item mapping observation cannot be non-authoritative."),
                    frappe.ValidationError,
                )
            mapping_version = positive_integer(
                self.mapping_version, _("Item Mapping Version")
            )
            self.formal_item_code = required_text(
                self.formal_item_code, _("Observed Formal Item Code"), 140
            )
            self.target_version = required_text(
                self.target_version, _("Observed Target Version"), 140
            )
            if self.disposition == "advanced" and mapping_version != previous_version + 1:
                frappe.throw(
                    _("An advanced Item mapping observation must increment its version by one."),
                    frappe.ValidationError,
                )
        if previous_version == 0 and self.previous_observation_hash:
            frappe.throw(
                _("An initial Item mapping observation cannot reference previous mapping truth."),
                frappe.ValidationError,
            )
        if previous_version > 0 and not self.previous_observation_hash:
            frappe.throw(
                _("An updated Item mapping observation requires previous mapping truth."),
                frappe.ValidationError,
            )
        target_result = json_object(
            self.target_result_snapshot, _("Exact Target Result Snapshot")
        )
        if canonical_hash(target_result) != self.target_result_hash:
            frappe.throw(
                _("The exact target result hash does not match its snapshot."),
                frappe.ValidationError,
            )
        observed_at = utc_datetime_text(self.observed_at, _("Observed At"))
        expected_snapshot = {
            "schemaVersion": 1,
            "globalId": self.global_id,
            "tenantId": self.tenant_id,
            "projectGlobalId": self.project_global_id,
            "sourceStreamKeyHash": self.source_stream_key_hash,
            "engineeringItemId": self.engineering_item_id,
            "mappingVersion": mapping_version,
            "formalItemCode": self.formal_item_code or None,
            "targetVersion": self.target_version or None,
            "requestGlobalId": self.request_global_id,
            "outboxEventId": self.outbox_event_id,
            "attemptGlobalId": self.attempt_global_id,
            "resultGlobalId": self.result_global_id,
            "profileId": self.profile_id,
            "profileVersion": self.profile_version,
            "environmentCode": self.environment_code,
            "authority": authority.value,
            "disposition": self.disposition,
            "previousMappingVersion": previous_version,
            "previousObservationHash": self.previous_observation_hash or None,
            "targetResultHash": self.target_result_hash,
            "observedAt": observed_at,
        }
        snapshot = json_object(
            self.observation_snapshot, _("Item Mapping Observation Snapshot")
        )
        if snapshot != expected_snapshot:
            frappe.throw(
                _("The Item mapping observation snapshot does not match its fields."),
                frappe.ValidationError,
            )
        self.target_result_snapshot = canonical_json(target_result)
        self.observation_snapshot = canonical_json(expected_snapshot)
        if canonical_hash(expected_snapshot) != self.observation_hash:
            frappe.throw(
                _("The Item mapping observation hash does not match its snapshot."),
                frappe.ValidationError,
            )
        self.observed_at = frappe_utc_datetime_text(observed_at, _("Observed At"))

    def on_trash(self) -> None:
        deny_item_history_delete()
