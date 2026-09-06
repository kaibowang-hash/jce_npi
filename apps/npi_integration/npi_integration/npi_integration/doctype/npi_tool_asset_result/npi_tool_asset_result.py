from npi_integration.tool_asset_request.doctype_base import ToolAssetSupportDocument
from npi_integration.tool_asset_request.execution_frappe_validation import require_tool_asset_execution_result_write


class NPIToolAssetResult(ToolAssetSupportDocument):
    write_guard = staticmethod(require_tool_asset_execution_result_write)
    uuid_fields = ("global_id", "request_global_id", "outbox_event_id", "attempt_global_id")
    hash_fields = ("source_hash", "mapping_expectation_hash", "response_hash", "field_result_set_hash", "result_hash")
    positive_fields = ("attempt_number",)
    required_text_fields = ("operation", "state", "authority", "fault_kind")
    optional_text_fields = ("formal_asset_id", "target_version")
