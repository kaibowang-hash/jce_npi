from frappe import _, throw, ValidationError

from npi_core.documents.frappe_validation import canonical_json, frappe_utc_datetime_text, json_object, lowercase_sha256
from npi_integration.quality_link.doctype_base import QualityLinkSupportDocument
from npi_integration.quality_link.domain import QUALITY_LINK_OPERATION, QUALITY_LINK_SCHEMA_VERSION, canonical_payload_hash


class NPIFormalQualityLinkCommandIdempotency(QualityLinkSupportDocument):
    append_only = False
    uuid_fields = ("global_id", "project_global_id")
    optional_uuid_fields = ("link_revision_global_id",)
    hash_fields = ("receipt_key_hash", "idempotency_key_hash", "payload_hash", "source_snapshot_hash", "projection_head_hash")
    optional_hash_fields = ("response_hash",)
    text_fields = ("operation",)
    actor_fields = ("actor_user_id",)
    immutable_fields = ("global_id", "schema_version", "receipt_key_hash", "tenant_id", "project_global_id", "actor_user_id", "operation", "idempotency_key_hash", "payload_hash", "source_snapshot_hash", "projection_head_hash", "created_at")

    def validate(self) -> None:
        super().validate()
        if self.schema_version != QUALITY_LINK_SCHEMA_VERSION or self.operation != QUALITY_LINK_OPERATION:
            throw(_("Formal quality link receipt identity is unsupported."), ValidationError)
        previous = self.get_doc_before_save()
        if previous is not None and int(previous.sealed or 0) == 1:
            if int(self.sealed or 0) != 1 or self.link_revision_global_id != previous.link_revision_global_id or self.response_payload != previous.response_payload or self.response_hash != previous.response_hash:
                throw(_("A sealed formal quality link receipt cannot be changed."), ValidationError)
        if int(self.sealed or 0) == 1:
            if not self.link_revision_global_id or not self.response_payload or not self.response_hash:
                throw(_("A sealed formal quality link receipt requires its exact revision and response."), ValidationError)
            response = json_object(self.response_payload, _("Sealed Response Payload"))
            if lowercase_sha256(self.response_hash, _("Sealed Response Hash")) != canonical_payload_hash(response):
                throw(_("The sealed formal quality link response hash does not match its payload."), ValidationError)
            self.response_payload = canonical_json(response)
        elif self.link_revision_global_id or self.response_payload or self.response_hash:
            throw(_("An unsealed formal quality link receipt cannot contain response truth."), ValidationError)
        self.created_at = frappe_utc_datetime_text(self.created_at, _("Created At"))
        self.updated_at = frappe_utc_datetime_text(self.updated_at, _("Updated At"))
