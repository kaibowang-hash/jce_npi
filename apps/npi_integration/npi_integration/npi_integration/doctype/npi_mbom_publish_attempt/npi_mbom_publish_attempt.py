from npi_integration.mbom_publish.doctype_base import MbomSupportDocument
from npi_integration.mbom_publish.frappe_validation import require_mbom_attempt_write


class NPIMBOMPublishAttempt(MbomSupportDocument):
    append_only = False
    write_guard = staticmethod(require_mbom_attempt_write)
    uuid_fields = ("global_id", "request_global_id", "outbox_event_id", "claim_token")
    hash_fields = (
        "target_idempotency_key_hash",
        "source_hash",
        "topology_hash",
        "item_mapping_set_hash",
        "mbom_mapping_set_hash",
        "node_manifest_hash",
        "request_snapshot_hash",
        "attempt_hash",
    )
    optional_hash_fields = ("response_hash",)
    positive_fields = ("attempt_number", "profile_version")
    required_text_fields = ("profile_id", "state")
    optional_text_fields = (
        "transport_disposition",
        "fault_kind",
        "safe_error_code",
    )
    immutable_fields = (
        "global_id",
        "request_global_id",
        "outbox_event_id",
        "attempt_number",
        "claim_token",
        "target_idempotency_key_hash",
        "source_hash",
        "topology_hash",
        "item_mapping_set_hash",
        "mbom_mapping_set_hash",
        "node_manifest_hash",
        "profile_id",
        "profile_version",
        "request_snapshot",
        "request_snapshot_hash",
        "started_at",
    )
