from npi_integration.mbom_publish.doctype_base import MbomSupportDocument
from npi_integration.mbom_publish.frappe_validation import require_mbom_request_write


class NPIMBOMPublishRequest(MbomSupportDocument):
    append_only = False
    write_guard = staticmethod(require_mbom_request_write)
    uuid_fields = (
        "global_id",
        "project_global_id",
        "phase5_publish_request_global_id",
        "ebom_global_id",
        "request_id",
    )
    optional_uuid_fields = ("outbox_event_id", "result_global_id")
    hash_fields = (
        "source_stream_key_hash",
        "source_hash",
        "topology_hash",
        "item_mapping_set_hash",
        "mbom_mapping_set_hash",
        "profile_snapshot_hash",
        "projection_policy_hash",
        "idempotency_key_hash",
        "payload_hash",
    )
    optional_hash_fields = (
        "target_idempotency_key_hash",
        "semantic_effect_hash",
    )
    positive_fields = (
        "schema_version",
        "profile_version",
        "projection_policy_version",
        "optimistic_version",
    )
    tenant_fields = ("tenant_id",)
    required_text_fields = (
        "api_version",
        "operation",
        "profile_id",
        "target_mode",
        "environment_code",
        "projection_policy_id",
        "trace_id",
    )
    actor_fields = ("actor_user_id",)
    optional_actor_fields = ("service_actor_user_id",)
    immutable_fields = (
        "global_id",
        "schema_version",
        "api_version",
        "operation",
        "tenant_id",
        "project_global_id",
        "phase5_publish_request_global_id",
        "ebom_global_id",
        "source_stream_key_hash",
        "source_snapshot",
        "source_hash",
        "topology_hash",
        "item_readiness_snapshot",
        "item_mapping_set_hash",
        "mbom_expectation_snapshot",
        "mbom_mapping_set_hash",
        "profile_id",
        "profile_version",
        "target_mode",
        "environment_code",
        "profile_snapshot_hash",
        "projection_policy_id",
        "projection_policy_version",
        "projection_policy_hash",
        "actor_user_id",
        "service_actor_user_id",
        "request_id",
        "trace_id",
        "idempotency_key_hash",
        "target_idempotency_key_hash",
        "semantic_effect_hash",
        "payload_hash",
        "created_at",
    )
