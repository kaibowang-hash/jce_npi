from npi_integration.mbom_publish.doctype_base import MbomSupportDocument
from npi_integration.mbom_publish.frappe_validation import require_mbom_node_write


class NPIMBOMPublishNode(MbomSupportDocument):
    append_only = False
    write_guard = staticmethod(require_mbom_node_write)
    uuid_fields = ("global_id", "request_global_id", "line_global_id")
    hash_fields = ("line_hash", "node_snapshot_hash")
    optional_uuid_fields = ("result_global_id",)
    optional_hash_fields = ("assembly_source_key",)
    positive_fields = ("optimistic_version",)
    required_text_fields = (
        "stable_line_key",
        "engineering_item_id",
        "source_role",
        "state",
    )
    optional_text_fields = ("parent_line_key",)
    immutable_fields = (
        "global_id",
        "request_global_id",
        "stable_line_key",
        "line_global_id",
        "parent_line_key",
        "engineering_item_id",
        "source_role",
        "line_snapshot",
        "line_hash",
        "assembly_source_key",
        "item_readiness_snapshot",
        "mbom_expectation_snapshot",
        "node_snapshot_hash",
        "created_at",
    )
