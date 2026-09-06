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
from npi_integration.projections.domain import (
    PROJECTION_DEFINITIONS,
    ProjectionAvailability,
    ProjectionContext,
    ProjectionFreshness,
    ProjectionKind,
    ProjectionScopeKind,
    canonical_payload_hash,
)
from npi_integration.projections.frappe_validation import (
    deny_projection_history_delete,
    require_projection_head_write,
)


class NPIERPProjectionHead(Document):
    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_projection_head_write()

    def before_save(self) -> None:
        require_projection_head_write()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("scope_global_id", _("Projection Scope Global ID")),
            ("last_refresh_observation", _("Last Refresh Projection Observation")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        if self.current_observation:
            self.current_observation = canonical_uuid(
                self.current_observation, _("Current Projection Observation")
            )
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(
                self,
                previous,
                (
                    "global_id",
                    "stream_key_hash",
                    "tenant_id",
                    "project_global_id",
                    "scope_kind",
                    "scope_global_id",
                    "projection_kind",
                    "source_object_type",
                    "source_object_id",
                ),
            )
        try:
            kind = ProjectionKind(self.projection_kind)
            scope_kind = ProjectionScopeKind(self.scope_kind)
            ProjectionContext(
                tenant_id=self.tenant_id,
                project_global_id=self.project_global_id,
                scope_kind=scope_kind,
                scope_global_id=self.scope_global_id,
            )
            availability = ProjectionAvailability(self.availability)
            freshness = ProjectionFreshness(self.freshness)
        except (ValueError, TypeError) as error:
            frappe.throw(_("The ERP projection input is invalid."), frappe.ValidationError)
            raise AssertionError("Frappe validation must raise.") from error
        definition = PROJECTION_DEFINITIONS[kind]
        if scope_kind not in definition.scopes or self.source_object_type != definition.source_object_type:
            frappe.throw(_("The projection head does not match its operation-specific stream."), frappe.ValidationError)
        source_object_id = required_text(self.source_object_id, _("Source Object ID"), 255)
        self.source_object_id = source_object_id
        current_values = (
            self.current_observation,
            self.current_source_version,
            self.current_source_modified_at,
            self.current_payload_hash,
        )
        if any(current_values) != all(current_values):
            frappe.throw(_("Current projection fields must be present together."), frappe.ValidationError)
        current_source_modified_at = None
        current_payload_hash = None
        if self.current_observation:
            self.current_source_version = required_text(
                self.current_source_version, _("Current Source Version"), 255
            )
            current_source_modified_at = utc_datetime_text(
                self.current_source_modified_at, _("Current Source Modified At")
            )
            current_payload_hash = lowercase_sha256(
                self.current_payload_hash, _("Current Projection Payload Hash")
            )
        elif availability is ProjectionAvailability.AVAILABLE:
            frappe.throw(_("An available projection head requires confirmed current truth."), frappe.ValidationError)
        if freshness is not ProjectionFreshness.UNKNOWN and not self.freshness_policy_ref:
            frappe.throw(_("Fresh or stale projection truth requires a policy reference."), frappe.ValidationError)
        freshness_policy_ref = (
            required_text(self.freshness_policy_ref, _("Freshness Policy Reference"), 128)
            if self.freshness_policy_ref
            else None
        )
        optimistic_version = positive_integer(
            self.optimistic_version, _("Optimistic Version")
        )
        previous_version = int(previous.optimistic_version) if previous is not None else 0
        if optimistic_version != previous_version + 1:
            frappe.throw(
                _("The projection head optimistic version must advance by one."),
                frappe.ValidationError,
            )
        stream_identity = {
            "tenantId": self.tenant_id,
            "projectGlobalId": self.project_global_id,
            "scopeKind": self.scope_kind,
            "scopeGlobalId": self.scope_global_id,
            "projectionKind": self.projection_kind,
            "sourceObjectType": self.source_object_type,
            "sourceObjectId": source_object_id,
        }
        expected_observation_stream = {
            "tenant_id": self.tenant_id,
            "project_global_id": self.project_global_id,
            "scope_kind": self.scope_kind,
            "scope_global_id": self.scope_global_id,
            "projection_kind": self.projection_kind,
            "source_object_type": self.source_object_type,
            "source_object_id": source_object_id,
        }
        require_exact_parent(
            "NPI ERP Projection Observation",
            self.last_refresh_observation,
            {
                "global_id": self.last_refresh_observation,
                **expected_observation_stream,
            },
            _("The exact last refresh projection observation is unavailable."),
        )
        if self.current_observation:
            require_exact_parent(
                "NPI ERP Projection Observation",
                self.current_observation,
                {
                    "global_id": self.current_observation,
                    **expected_observation_stream,
                    "source_version": self.current_source_version,
                    "source_modified_at": current_source_modified_at,
                    "payload_hash": current_payload_hash,
                    "availability": "available",
                    "disposition": "applied_current",
                },
                _("The exact current projection observation is unavailable."),
            )
        expected_stream_hash = canonical_payload_hash(stream_identity)
        if lowercase_sha256(self.stream_key_hash, _("Projection Stream Key Hash")) != expected_stream_hash:
            frappe.throw(_("The projection stream key hash does not match its fields."), frappe.ValidationError)
        updated_at = utc_datetime_text(self.updated_at, _("Updated At"))
        expected_snapshot = {
            "schemaVersion": 1,
            "globalId": self.global_id,
            **stream_identity,
            "streamKeyHash": expected_stream_hash,
            "currentObservationGlobalId": self.current_observation or None,
            "lastRefreshObservationGlobalId": self.last_refresh_observation,
            "currentSourceVersion": self.current_source_version or None,
            "currentSourceModifiedAt": current_source_modified_at,
            "currentPayloadHash": current_payload_hash,
            "availability": availability.value,
            "freshness": freshness.value,
            "freshnessPolicyRef": freshness_policy_ref,
            "optimisticVersion": optimistic_version,
            "updatedAt": updated_at,
        }
        snapshot = json_object(self.head_snapshot, _("Projection Head Snapshot"))
        if snapshot != expected_snapshot:
            frappe.throw(_("The projection head snapshot does not match its fields."), frappe.ValidationError)
        self.head_snapshot = canonical_json(expected_snapshot)
        if lowercase_sha256(self.head_hash, _("Projection Head Hash")) != canonical_payload_hash(expected_snapshot):
            frappe.throw(_("The projection head hash does not match its fields."), frappe.ValidationError)
        self.current_source_modified_at = (
            frappe_utc_datetime_text(
                current_source_modified_at,
                _("Current Source Modified At"),
            )
            if current_source_modified_at is not None
            else None
        )
        self.updated_at = frappe_utc_datetime_text(updated_at, _("Updated At"))

    def on_trash(self) -> None:
        deny_projection_history_delete()
