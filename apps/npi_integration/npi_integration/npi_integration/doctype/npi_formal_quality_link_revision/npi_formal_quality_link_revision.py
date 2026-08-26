from frappe import _, throw, ValidationError

from npi_core.documents.frappe_validation import (
    canonical_json, frappe_utc_datetime_text, json_object, lowercase_sha256,
    require_exact_parent, required_text,
)
from npi_integration.quality_link.doctype_base import QualityLinkSupportDocument
from npi_integration.quality_link.domain import QUALITY_LINK_SCHEMA_VERSION, canonical_payload_hash


class NPIFormalQualityLinkRevision(QualityLinkSupportDocument):
    uuid_fields = ("global_id", "project_global_id", "source_global_id", "observation_global_id", "head_global_id", "scope_global_id")
    optional_uuid_fields = ("predecessor_global_id",)
    hash_fields = ("source_snapshot_hash", "stream_key_hash", "projection_payload_hash", "observation_hash", "projection_head_hash", "link_hash")
    positive_fields = ("source_version", "revision_number", "head_optimistic_version")
    text_fields = ("source_state", "source_object_type", "source_object_id", "source_object_version", "raw_status_code", "freshness_policy_ref", "trace_id")
    actor_fields = ("actor_user_id",)
    immutable_fields = (
        "global_id", "schema_version", "tenant_id", "project_global_id", "source_kind", "source_global_id", "source_version", "source_state", "source_snapshot_hash", "stream_key_hash", "revision_number", "predecessor_global_id", "observation_global_id", "head_global_id", "head_optimistic_version", "scope_kind", "scope_global_id", "source_object_type", "source_object_id", "source_object_version", "record_kind", "raw_status_code", "raw_result_code", "projection_payload_hash", "observation_hash", "projection_head_hash", "freshness_policy_ref", "link_state", "source_snapshot", "formal_observation_snapshot", "link_snapshot", "link_hash", "actor_user_id", "trace_id", "created_at",
    )

    def validate(self) -> None:
        super().validate()
        if self.schema_version != QUALITY_LINK_SCHEMA_VERSION:
            throw(_("Formal quality link schema version is unsupported."), ValidationError)
        if self.source_kind not in {"trial_round", "trial_defect", "trial_review", "readiness_assessment", "controlled_quality_report"}:
            throw(_("Formal quality link source kind is unsupported."), ValidationError)
        if self.scope_kind not in {"project", "trial_round", "readiness"} or self.record_kind not in {"quality_inspection", "ncr", "capa"} or self.link_state not in {"linked", "superseded"}:
            throw(_("Formal quality link state or record kind is unsupported."), ValidationError)
        if (self.revision_number == 1) != (not self.predecessor_global_id):
            throw(_("Formal quality link predecessor does not match its revision number."), ValidationError)
        if self.raw_result_code:
            self.raw_result_code = required_text(self.raw_result_code, _("Formal Quality Raw Result Code"), 128)
        expected_source = {
            "tenantId": self.tenant_id, "projectGlobalId": self.project_global_id,
            "sourceKind": self.source_kind, "sourceGlobalId": self.source_global_id,
            "sourceVersion": self.source_version, "sourceState": self.source_state,
            "sourceSnapshotHash": self.source_snapshot_hash,
        }
        expected_observation = {
            "tenantId": self.tenant_id, "projectGlobalId": self.project_global_id,
            "scopeKind": self.scope_kind, "scopeGlobalId": self.scope_global_id,
            "projectionKind": "formal_quality_status", "sourceSystem": "ERPNEXT",
            "availability": "available", "freshness": "fresh", "disposition": "applied_current",
            "observationGlobalId": self.observation_global_id, "headGlobalId": self.head_global_id,
            "headOptimisticVersion": self.head_optimistic_version,
            "sourceObjectType": self.source_object_type, "sourceObjectId": self.source_object_id,
            "sourceVersion": self.source_object_version, "recordKind": self.record_kind,
            "statusCode": self.raw_status_code, "resultCode": self.raw_result_code or None,
            "payloadHash": self.projection_payload_hash, "observationHash": self.observation_hash,
            "headHash": self.projection_head_hash, "freshnessPolicyRef": self.freshness_policy_ref,
        }
        if json_object(self.source_snapshot, _("Exact Quality Link Source Snapshot")) != expected_source or json_object(self.formal_observation_snapshot, _("Exact Formal Quality Observation Snapshot")) != expected_observation:
            throw(_("Formal quality link source or observation snapshot does not match its fields."), ValidationError)
        require_exact_parent(
            "NPI ERP Projection Observation", self.observation_global_id,
            {"global_id": self.observation_global_id, "tenant_id": self.tenant_id, "project_global_id": self.project_global_id,
             "scope_kind": self.scope_kind, "scope_global_id": self.scope_global_id, "projection_kind": "formal_quality_status",
             "source_object_type": self.source_object_type, "source_object_id": self.source_object_id,
             "source_version": self.source_object_version, "payload_hash": self.projection_payload_hash,
             "observation_hash": self.observation_hash, "availability": "available", "freshness": "fresh", "disposition": "applied_current"},
            _("The exact current formal quality observation is unavailable."),
        )
        require_exact_parent(
            "NPI ERP Projection Head", self.head_global_id,
            {"global_id": self.head_global_id, "tenant_id": self.tenant_id, "project_global_id": self.project_global_id,
             "scope_kind": self.scope_kind, "scope_global_id": self.scope_global_id, "projection_kind": "formal_quality_status",
             "source_object_type": self.source_object_type, "source_object_id": self.source_object_id,
             "current_observation": self.observation_global_id, "current_source_version": self.source_object_version,
             "current_payload_hash": self.projection_payload_hash, "availability": "available", "freshness": "fresh",
             "freshness_policy_ref": self.freshness_policy_ref, "optimistic_version": self.head_optimistic_version,
             "head_hash": self.projection_head_hash},
            _("The exact current formal quality projection head is unavailable."),
        )
        expected = {
            "schemaVersion": 1, "globalId": self.global_id, "streamKeyHash": self.stream_key_hash,
            "revisionNumber": self.revision_number, "predecessorGlobalId": self.predecessor_global_id or None,
            "source": expected_source, "formalObservation": expected_observation, "linkState": self.link_state,
            "actorUserId": self.actor_user_id, "traceId": self.trace_id,
            "createdAt": frappe_utc_datetime_text(self.created_at, _("Created At")),
        }
        if json_object(self.link_snapshot, _("Formal Quality Link Snapshot")) != expected or lowercase_sha256(self.link_hash, _("Formal Quality Link Hash")) != canonical_payload_hash(expected):
            throw(_("Formal quality link snapshot does not match its immutable fields."), ValidationError)
        self.source_snapshot = canonical_json(expected_source)
        self.formal_observation_snapshot = canonical_json(expected_observation)
        self.link_snapshot = canonical_json(expected)
        self.created_at = expected["createdAt"]
