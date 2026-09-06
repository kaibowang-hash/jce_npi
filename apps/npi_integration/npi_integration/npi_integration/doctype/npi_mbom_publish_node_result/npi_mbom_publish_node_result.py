from npi_integration.mbom_publish.doctype_base import MbomSupportDocument
from npi_integration.mbom_publish.frappe_validation import require_mbom_result_write


class NPIMBOMPublishNodeResult(MbomSupportDocument):
    write_guard = staticmethod(require_mbom_result_write)
    uuid_fields = (
        "global_id",
        "request_global_id",
        "result_global_id",
        "attempt_global_id",
        "node_global_id",
    )
    hash_fields = ("assembly_source_key", "response_hash", "node_result_hash")
    required_text_fields = ("stable_line_key", "state", "authority", "fault_kind")
    optional_text_fields = (
        "formal_bom_id",
        "target_version",
        "target_submission_state",
    )
