from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    canonical_json,
    canonical_uuid,
    json_object,
    lowercase_sha256,
    positive_integer,
    required_text,
    tenant_text,
    utc_datetime_text,
)
from npi_integration.projections.domain import (
    PROJECTION_ADAPTER_CONTRACT_VERSION,
    PROJECTION_DEFINITIONS,
    PROJECTION_SCHEMA_VERSION,
    AdapterMode,
    ApplicationDisposition,
    ProjectionAvailability,
    ProjectionContext,
    ProjectionFreshness,
    ProjectionKind,
    ProjectionReaderResult,
    ProjectionScopeKind,
    ProjectionSensitivity,
    canonical_payload_hash,
)
from npi_integration.projections.frappe_validation import (
    deny_projection_history_delete,
    deny_projection_observation_update,
    require_projection_observation_write,
)


class NPIERPProjectionObservation(Document):
    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_projection_observation_write()

    def before_save(self) -> None:
        require_projection_observation_write()
        if self.get_doc_before_save() is not None:
            deny_projection_observation_update()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("event_id", _("Event ID")),
            ("correlation_id", _("Correlation ID")),
            ("project_global_id", _("Project Global ID")),
            ("scope_global_id", _("Projection Scope Global ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_projection_observation_update()
        if positive_integer(self.schema_version, _("Schema Version")) != PROJECTION_SCHEMA_VERSION:
            frappe.throw(_("Select the supported projection schema version."), frappe.ValidationError)
        if positive_integer(self.event_version, _("Event Version")) != 1:
            frappe.throw(_("Select the supported projection event version."), frappe.ValidationError)
        if self.source_system != "ERPNEXT" or self.target_system != "NPI_ONE":
            frappe.throw(_("ERP projection system ownership is invalid."), frappe.ValidationError)
        if self.adapter_contract_version != PROJECTION_ADAPTER_CONTRACT_VERSION:
            frappe.throw(_("Select the supported projection adapter contract."), frappe.ValidationError)
        try:
            kind = ProjectionKind(self.projection_kind)
            mode = AdapterMode(self.adapter_mode)
            availability = ProjectionAvailability(self.availability)
            ProjectionFreshness(self.freshness)
            disposition = ApplicationDisposition(self.disposition)
            ProjectionSensitivity(self.sensitivity)
            scope_kind = ProjectionScopeKind(self.scope_kind)
            context = ProjectionContext(
                tenant_id=self.tenant_id,
                project_global_id=self.project_global_id,
                scope_kind=scope_kind,
                scope_global_id=self.scope_global_id,
            )
            payload = json_object(self.payload, _("Projection Payload"))
            source_modified_at = (
                utc_datetime_text(
                    self.source_modified_at,
                    _("Source Modified At"),
                )
                if self.source_modified_at
                else None
            )
            result = ProjectionReaderResult(
                kind=kind,
                adapter_mode=mode,
                source_environment=self.source_environment,
                source_object_id=self.source_object_id,
                source_version=self.source_version or None,
                source_modified_at=source_modified_at,
                availability=availability,
                values=payload.get("values"),
                unavailable_reason_code=self.unavailable_reason_code or None,
            )
            received_at = utc_datetime_text(self.received_at, _("Received At"))
            expected_payload = result.event_payload(context=context, received_at=received_at)
        except (ValueError, TypeError) as error:
            frappe.throw(_("The ERP projection input is invalid."), frappe.ValidationError)
            raise AssertionError("Frappe validation must raise.") from error
        definition = PROJECTION_DEFINITIONS[kind]
        self.source_environment = result.source_environment
        self.source_object_id = result.source_object_id
        self.source_version = result.source_version
        self.source_modified_at = result.source_modified_at
        self.unavailable_reason_code = result.unavailable_reason_code
        if self.event_type != definition.event_type or self.source_object_type != definition.source_object_type:
            frappe.throw(_("The projection event does not match its operation-specific kind."), frappe.ValidationError)
        if payload != expected_payload:
            frappe.throw(_("The projection payload does not match its exact fields."), frappe.ValidationError)
        self.payload = canonical_json(expected_payload)
        payload_hash = lowercase_sha256(self.payload_hash, _("Projection Payload Hash"))
        if payload_hash != canonical_payload_hash(expected_payload):
            frappe.throw(_("The projection payload hash does not match its fields."), frappe.ValidationError)
        expected_event_key_hash = canonical_payload_hash(
            {"eventId": self.event_id, "payloadHash": payload_hash}
        )
        if lowercase_sha256(self.event_key_hash, _("Event Key Hash")) != expected_event_key_hash:
            frappe.throw(_("The projection event key hash does not match its fields."), frappe.ValidationError)
        if availability is ProjectionAvailability.AVAILABLE and disposition is ApplicationDisposition.UNAVAILABLE_CURRENT:
            frappe.throw(_("An available projection cannot use an unavailable disposition."), frappe.ValidationError)
        if availability is ProjectionAvailability.SYNTHETIC and disposition is not ApplicationDisposition.SYNTHETIC_RETAINED:
            frappe.throw(_("Synthetic projection proof must remain non-authoritative."), frappe.ValidationError)
        if availability is ProjectionAvailability.UNAVAILABLE and disposition is ApplicationDisposition.APPLIED_CURRENT:
            frappe.throw(_("An unavailable projection cannot become confirmed current truth."), frappe.ValidationError)
        created_at = utc_datetime_text(self.created_at, _("Created At"))
        trace_id = required_text(self.trace_id, _("Trace ID"), 128)
        self.trace_id = trace_id
        expected_snapshot = {
            "schemaVersion": PROJECTION_SCHEMA_VERSION,
            "globalId": self.global_id,
            "eventId": self.event_id,
            "eventKeyHash": expected_event_key_hash,
            "eventType": self.event_type,
            "eventVersion": 1,
            "sourceSystem": "ERPNEXT",
            "targetSystem": "NPI_ONE",
            "sourceObjectType": self.source_object_type,
            "payload": expected_payload,
            "payloadHash": payload_hash,
            "traceId": trace_id,
            "correlationId": self.correlation_id,
            "sensitivity": self.sensitivity,
            "freshness": self.freshness,
            "disposition": self.disposition,
            "createdAt": created_at,
        }
        snapshot = json_object(self.observation_snapshot, _("Projection Observation Snapshot"))
        if snapshot != expected_snapshot:
            frappe.throw(_("The projection observation snapshot does not match its fields."), frappe.ValidationError)
        self.observation_snapshot = canonical_json(expected_snapshot)
        if lowercase_sha256(self.observation_hash, _("Projection Observation Hash")) != canonical_payload_hash(expected_snapshot):
            frappe.throw(_("The projection observation hash does not match its fields."), frappe.ValidationError)

    def on_trash(self) -> None:
        deny_projection_history_delete()
