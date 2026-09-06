from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.grid_personalization.domain import (
    GRID_ID,
    TABLE_SCHEMA_VERSION,
    GridPersonalizationValidationError,
    PersonalGridPreference,
    canonical_hash,
    canonical_json,
    preference_key,
)
from npi_core.grid_personalization.frappe_validation import (
    deny_grid_personalization_delete,
    frappe_utc_datetime_text,
    normalize_uuid_fields,
    require_actor,
    require_grid_personalization_write,
    require_immutable_fields,
    require_positive_integer,
    require_trace_id,
    throw_domain_validation,
)
from npi_core.project.frappe_validation import ensure_uuid


class NPIMyWorkGridPreference(Document):
    _IDENTITY_FIELDS = (
        "global_id",
        "preference_key_hash",
        "tenant_id",
        "actor_user_id",
        "grid_id",
        "table_schema_version",
    )

    def before_insert(self) -> None:
        require_grid_personalization_write()

    def before_save(self) -> None:
        require_grid_personalization_write()

    def on_trash(self) -> None:
        deny_grid_personalization_delete()

    def validate(self) -> None:
        normalize_uuid_fields(self, ("global_id",))
        self.actor_user_id = require_actor(self.actor_user_id, _("User"))
        expected_key = preference_key(self.tenant_id, self.actor_user_id)
        if self.preference_key_hash != expected_key:
            frappe.throw(
                _("Preference Key Hash does not match its identities."),
                frappe.ValidationError,
            )
        if self.grid_id != GRID_ID or self.table_schema_version != (
            TABLE_SCHEMA_VERSION
        ):
            frappe.throw(
                _("Select the supported My Work grid schema."),
                frappe.ValidationError,
            )
        version = require_positive_integer(
            self.optimistic_version,
            _("Optimistic Version"),
        )
        try:
            snapshot = (
                json.loads(self.preference_snapshot)
                if isinstance(self.preference_snapshot, str)
                else self.preference_snapshot
            )
            preference = PersonalGridPreference.from_storage(
                version=version,
                value=snapshot,
            )
        except (
            GridPersonalizationValidationError,
            TypeError,
            json.JSONDecodeError,
        ) as error:
            throw_domain_validation(error)
            return
        canonical_snapshot = preference.storage_dict()
        expected_hash = canonical_hash(canonical_snapshot)
        if self.snapshot_hash != expected_hash:
            frappe.throw(
                _("Preference Snapshot Hash does not match its canonical snapshot."),
                frappe.ValidationError,
            )
        self.preference_snapshot = canonical_json(canonical_snapshot)
        self.snapshot_hash = expected_hash
        self.last_changed_by = require_actor(
            self.last_changed_by,
            _("Last Changed By"),
        )
        self.last_changed_at = frappe_utc_datetime_text(
            self.last_changed_at,
            _("Last Changed At"),
        )
        self.request_id = ensure_uuid(self.request_id, _("Request ID"))
        self.trace_id = require_trace_id(self.trace_id)

        previous = self.get_doc_before_save()
        if previous is None:
            if version != 1:
                frappe.throw(
                    _("The first preference version must be one."),
                    frappe.ValidationError,
                )
            return
        require_immutable_fields(self, previous, self._IDENTITY_FIELDS)
        previous_version = previous.optimistic_version
        if (
            type(previous_version) is not int
            or previous_version < 1
        ):
            if version == 1:
                return
        elif version == previous_version + 1:
            return
        frappe.throw(
            _("Preference Version must advance one version at a time."),
            frappe.ValidationError,
        )
