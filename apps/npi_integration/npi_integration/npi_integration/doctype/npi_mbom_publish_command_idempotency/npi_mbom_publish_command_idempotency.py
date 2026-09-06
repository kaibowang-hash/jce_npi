from npi_integration.mbom_publish.doctype_base import MbomSupportDocument
from npi_integration.mbom_publish.frappe_validation import require_mbom_idempotency_write


class NPIMBOMPublishCommandIdempotency(MbomSupportDocument):
    identity_field = "scope_key_hash"
    identity_is_hash = True
    write_guard = staticmethod(require_mbom_idempotency_write)
    uuid_fields = ("project_global_id", "request_global_id")
    hash_fields = (
        "scope_key_hash",
        "idempotency_key_hash",
        "request_payload_hash",
        "response_hash",
    )
    tenant_fields = ("tenant_id",)
    required_text_fields = ("operation",)
    actor_fields = ("actor_user_id",)
