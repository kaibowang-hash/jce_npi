from npi_integration.mbom_publish.doctype_base import MbomSupportDocument
from npi_integration.mbom_publish.frappe_validation import require_mbom_mapping_write


class NPIMBOMMappingHead(MbomSupportDocument):
    append_only = False
    write_guard = staticmethod(require_mbom_mapping_write)
    uuid_fields = (
        "global_id",
        "project_global_id",
        "ebom_global_id",
        "current_observation",
    )
    hash_fields = (
        "assembly_source_key",
        "current_observation_hash",
        "head_hash",
    )
    positive_fields = ("mapping_version",)
    tenant_fields = ("tenant_id",)
    required_text_fields = (
        "stable_line_key",
        "formal_bom_id",
        "target_version",
        "target_submission_state",
    )
    immutable_fields = (
        "global_id",
        "tenant_id",
        "project_global_id",
        "ebom_global_id",
        "assembly_source_key",
        "stable_line_key",
    )
