from npi_integration.mbom_publish.doctype_base import MbomSupportDocument
from npi_integration.mbom_publish.frappe_validation import require_mbom_stream_guard_write


class NPIMBOMPublishStreamGuard(MbomSupportDocument):
    identity_field = "source_stream_key_hash"
    identity_is_hash = True
    append_only = False
    write_guard = staticmethod(require_mbom_stream_guard_write)
    uuid_fields = ("project_global_id", "ebom_global_id")
    hash_fields = ("source_stream_key_hash",)
    optional_uuid_fields = ("active_request_global_id", "last_request_global_id")
    optional_hash_fields = (
        "active_target_idempotency_key_hash",
        "last_target_idempotency_key_hash",
    )
    optional_text_fields = ("active_state", "last_state", "blocked_reason_code")
    positive_fields = ("optimistic_version",)
    tenant_fields = ("tenant_id",)
    immutable_fields = (
        "source_stream_key_hash",
        "tenant_id",
        "project_global_id",
        "ebom_global_id",
    )
