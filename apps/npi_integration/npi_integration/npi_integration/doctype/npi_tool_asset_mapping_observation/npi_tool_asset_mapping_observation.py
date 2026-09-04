from npi_integration.tool_asset_request.doctype_base import ToolAssetSupportDocument
from npi_integration.tool_asset_request.execution_frappe_validation import require_tool_asset_execution_mapping_write


class NPIToolAssetMappingObservation(ToolAssetSupportDocument):
    write_guard = staticmethod(require_tool_asset_execution_mapping_write)
    uuid_fields = ("global_id", "project_global_id", "tooling_set_global_id", "request_global_id", "result_global_id", "attempt_global_id")
    hash_fields = ("source_stream_key_hash", "source_hash", "mapping_expectation_hash", "response_hash", "observation_hash")
    optional_hash_fields = ("previous_observation_hash",)
    nonnegative_fields = ("previous_mapping_version",)
    tenant_fields = ("tenant_id",)
    required_text_fields = ("operation", "authority", "disposition")
    optional_text_fields = ("previous_formal_asset_id", "previous_target_version", "observed_formal_asset_id", "observed_target_version")
