from npi_integration.tool_asset_request.doctype_base import ToolAssetSupportDocument
from npi_integration.tool_asset_request.execution_frappe_validation import require_tool_asset_execution_result_write


class NPIToolAssetFieldResult(ToolAssetSupportDocument):
    write_guard = staticmethod(require_tool_asset_execution_result_write)
    uuid_fields = ("global_id", "request_global_id", "result_global_id", "attempt_global_id")
    hash_fields = ("response_hash", "observation_hash", "field_result_hash")
    required_text_fields = ("field_code", "state", "authority", "fault_kind")
