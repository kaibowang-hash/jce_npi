from npi_integration.mbom_publish.doctype_base import MbomSupportDocument
from npi_integration.mbom_publish.frappe_validation import require_mbom_result_write


class NPIMBOMPublishResult(MbomSupportDocument):
    write_guard = staticmethod(require_mbom_result_write)
    uuid_fields = ("global_id", "request_global_id", "outbox_event_id", "attempt_global_id")
    hash_fields = (
        "source_hash",
        "topology_hash",
        "item_mapping_set_hash",
        "mbom_mapping_set_hash",
        "response_hash",
        "node_result_set_hash",
        "result_hash",
    )
    positive_fields = ("attempt_number",)
    required_text_fields = ("state", "authority", "fault_kind")

