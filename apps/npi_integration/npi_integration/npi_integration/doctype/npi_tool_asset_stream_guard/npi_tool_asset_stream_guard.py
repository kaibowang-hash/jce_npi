from npi_integration.tool_asset_request.doctype_base import ToolAssetSupportDocument
from npi_integration.tool_asset_request.execution_frappe_validation import require_tool_asset_execution_stream_write


class NPIToolAssetStreamGuard(ToolAssetSupportDocument):
    identity_field = "source_stream_key_hash"
    identity_is_hash = True
    append_only = False
    write_guard = staticmethod(require_tool_asset_execution_stream_write)
    uuid_fields = ("project_global_id", "tooling_set_global_id")
    optional_uuid_fields = ("active_request_global_id", "last_request_global_id")
    hash_fields = ("source_stream_key_hash",)
    optional_hash_fields = ("active_target_idempotency_key_hash", "last_target_idempotency_key_hash")
    positive_fields = ("optimistic_version",)
    tenant_fields = ("tenant_id",)
    optional_text_fields = ("active_state", "last_state", "blocked_reason_code")
    immutable_fields = ("source_stream_key_hash", "tenant_id", "project_global_id", "tooling_set_global_id")
