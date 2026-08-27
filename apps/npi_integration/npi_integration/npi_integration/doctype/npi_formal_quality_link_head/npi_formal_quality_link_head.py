from frappe import _, throw, ValidationError

from npi_core.documents.frappe_validation import canonical_json, frappe_utc_datetime_text, json_object, lowercase_sha256, require_exact_parent, utc_datetime_text
from npi_integration.quality_link.doctype_base import QualityLinkSupportDocument
from npi_integration.quality_link.domain import canonical_payload_hash


class NPIFormalQualityLinkHead(QualityLinkSupportDocument):
    append_only = False
    uuid_fields = ("global_id", "project_global_id", "source_global_id", "current_revision", "current_observation_global_id", "current_projection_head_global_id")
    hash_fields = ("stream_key_hash", "head_hash")
    positive_fields = ("revision_number", "current_projection_head_version", "optimistic_version")
    immutable_fields = ("global_id", "tenant_id", "project_global_id", "source_kind", "source_global_id", "stream_key_hash")

    def validate(self) -> None:
        super().validate()
        updated_at = utc_datetime_text(self.updated_at, _("Updated At"))
        if self.source_kind not in {"trial_round", "trial_defect", "trial_review", "readiness_assessment", "controlled_quality_report"}:
            throw(_("Formal quality link source kind is unsupported."), ValidationError)
        previous = self.get_doc_before_save()
        if previous is not None:
            if self.optimistic_version != previous.optimistic_version + 1 or self.revision_number != previous.revision_number + 1:
                throw(_("Formal quality link head versions must advance exactly once."), ValidationError)
        require_exact_parent(
            "NPI Formal Quality Link Revision", self.current_revision,
            {"global_id": self.current_revision, "tenant_id": self.tenant_id, "project_global_id": self.project_global_id,
             "source_kind": self.source_kind, "source_global_id": self.source_global_id,
             "stream_key_hash": self.stream_key_hash, "revision_number": self.revision_number,
             "observation_global_id": self.current_observation_global_id,
             "head_global_id": self.current_projection_head_global_id,
             "head_optimistic_version": self.current_projection_head_version},
            _("The exact current formal quality link revision is unavailable."),
        )
        expected = {
            "schemaVersion": 1, "globalId": self.global_id, "tenantId": self.tenant_id,
            "projectGlobalId": self.project_global_id, "sourceKind": self.source_kind,
            "sourceGlobalId": self.source_global_id, "streamKeyHash": self.stream_key_hash,
            "currentRevisionGlobalId": self.current_revision, "revisionNumber": self.revision_number,
            "currentObservationGlobalId": self.current_observation_global_id,
            "currentProjectionHeadGlobalId": self.current_projection_head_global_id,
            "currentProjectionHeadVersion": self.current_projection_head_version,
            "optimisticVersion": self.optimistic_version,
            "updatedAt": updated_at,
        }
        if json_object(self.head_snapshot, _("Formal Quality Link Head Snapshot")) != expected or lowercase_sha256(self.head_hash, _("Formal Quality Link Head Hash")) != canonical_payload_hash(expected):
            throw(_("Formal quality link head snapshot does not match its fields."), ValidationError)
        self.head_snapshot = canonical_json(expected)
        self.updated_at = frappe_utc_datetime_text(updated_at, _("Updated At"))
