from npi_integration.tool_asset_request.doctype_base import ToolAssetSupportDocument
from npi_integration.tool_asset_request.execution_frappe_validation import require_tool_asset_execution_attempt_write


class NPIToolAssetAttempt(ToolAssetSupportDocument):
    append_only = False
    write_guard = staticmethod(require_tool_asset_execution_attempt_write)
    uuid_fields = ("global_id", "request_global_id", "outbox_event_id", "claim_token")
    hash_fields = ("target_idempotency_key_hash", "source_hash", "mapping_expectation_hash", "profile_snapshot_hash", "request_snapshot_hash", "attempt_hash")
    optional_hash_fields = ("response_hash",)
    positive_fields = ("attempt_number", "profile_version")
    required_text_fields = ("operation", "state")
    optional_text_fields = ("transport_disposition", "fault_kind", "safe_error_code")
    immutable_fields = (
        "global_id", "request_global_id", "outbox_event_id", "attempt_number",
        "claim_token", "operation", "target_idempotency_key_hash", "source_hash",
        "mapping_expectation_hash", "profile_id", "profile_version",
        "profile_snapshot_hash", "request_snapshot", "request_snapshot_hash",
        "started_at",
    )
