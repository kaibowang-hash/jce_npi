from npi_integration.tool_asset_request.doctype_base import ToolAssetSupportDocument
from npi_integration.tool_asset_request.execution_frappe_validation import require_tool_asset_execution_mapping_write


class NPIToolAssetMappingHead(ToolAssetSupportDocument):
    append_only = False
    write_guard = staticmethod(require_tool_asset_execution_mapping_write)
    uuid_fields = ("global_id", "project_global_id", "tooling_set_global_id", "current_observation")
    hash_fields = ("source_stream_key_hash", "current_observation_hash", "head_hash")
    positive_fields = ("mapping_version",)
    tenant_fields = ("tenant_id",)
    required_text_fields = ("formal_asset_id", "target_version")
    immutable_fields = ("global_id", "tenant_id", "project_global_id", "tooling_set_global_id", "source_stream_key_hash")
