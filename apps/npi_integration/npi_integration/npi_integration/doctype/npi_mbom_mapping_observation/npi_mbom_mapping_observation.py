from npi_integration.mbom_publish.doctype_base import MbomSupportDocument
from npi_integration.mbom_publish.frappe_validation import require_mbom_mapping_write


class NPIMBOMMappingObservation(MbomSupportDocument):
    write_guard = staticmethod(require_mbom_mapping_write)
    uuid_fields = (
        "global_id",
        "project_global_id",
        "ebom_global_id",
        "request_global_id",
        "outbox_event_id",
        "attempt_global_id",
        "result_global_id",
        "node_result_global_id",
    )
    hash_fields = (
        "assembly_source_key",
        "target_result_hash",
        "observation_hash",
    )
    optional_hash_fields = ("previous_observation_hash",)
    positive_fields = ("profile_version",)
    nonnegative_fields = ("previous_mapping_version",)
    tenant_fields = ("tenant_id",)
    required_text_fields = (
        "stable_line_key",
        "environment_code",
        "authority",
        "disposition",
    )
    optional_text_fields = (
        "formal_bom_id",
        "target_version",
        "target_submission_state",
    )
