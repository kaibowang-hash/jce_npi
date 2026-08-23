from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    actor_text,
    assert_immutable_fields,
    canonical_json,
    canonical_uuid,
    frappe_utc_datetime_text,
    json_object,
    lowercase_sha256,
    nonnegative_integer,
    positive_integer,
    required_text,
    tenant_text,
    utc_datetime_text,
)
from npi_integration.item_publish.domain import (
    ITEM_PUBLISH_OPERATION,
    ITEM_PUBLISH_SCHEMA_VERSION,
    ITEM_REQUEST_EVENT_TYPE,
    canonical_hash,
)
from npi_integration.item_publish.frappe_validation import (
    deny_item_history_delete,
    deny_item_history_update,
    deny_legacy_outbox_promotion,
    require_item_outbox_write,
    validate_one_way_transition,
)
from npi_integration.mbom_publish.domain import (
    MBOM_PUBLISH_OPERATION,
    MBOM_PUBLISH_SCHEMA_VERSION,
    MBOM_REQUEST_EVENT_TYPE,
)
from npi_integration.mbom_publish.frappe_validation import (
    deny_mbom_history_delete,
    deny_mbom_history_update,
    deny_outbox_operation_conversion,
    require_mbom_outbox_write,
)
from npi_integration.tool_asset_request.execution_domain import (
    TOOL_ASSET_EXECUTION_API_VERSION,
    TOOL_ASSET_EXECUTION_OPERATIONS,
    TOOL_ASSET_OUTBOX_SCHEMA_VERSION,
    TOOL_ASSET_REQUEST_EVENT_TYPE,
)
from npi_integration.tool_asset_request.execution_frappe_validation import (
    deny_tool_asset_execution_history_delete,
    deny_tool_asset_execution_history_update,
    deny_tool_asset_outbox_conversion,
    require_tool_asset_execution_outbox_write,
)


_ITEM_STATES = {
    "pending": frozenset({"processing", "failed_final"}),
    "processing": frozenset(
        {"pending", "succeeded", "failed_retryable", "failed_final", "uncertain"}
    ),
    "failed_retryable": frozenset(),
    "succeeded": frozenset(),
    "failed_final": frozenset(),
    "uncertain": frozenset(),
}
_ITEM_TERMINAL_STATES = frozenset(
    {"succeeded", "failed_retryable", "failed_final", "uncertain"}
)
_MBOM_STATES = {
    "pending": frozenset({"processing", "failed_final"}),
    "processing": frozenset(
        {
            "pending",
            "partially_succeeded",
            "succeeded",
            "failed_retryable",
            "failed_final",
            "uncertain",
            "mapping_conflict",
        }
    ),
    "partially_succeeded": frozenset(),
    "succeeded": frozenset(),
    "failed_retryable": frozenset(),
    "failed_final": frozenset(),
    "uncertain": frozenset(),
    "mapping_conflict": frozenset(),
}
_MBOM_TERMINAL_STATES = frozenset(
    {
        "partially_succeeded",
        "succeeded",
        "failed_retryable",
        "failed_final",
        "uncertain",
        "mapping_conflict",
    }
)
_TOOL_ASSET_STATES = {
    "pending": frozenset({"processing", "failed_final"}),
    "processing": frozenset({"pending", "partially_succeeded", "succeeded", "failed_retryable", "failed_final", "uncertain", "mapping_conflict"}),
    "partially_succeeded": frozenset(),
    "succeeded": frozenset(),
    "failed_retryable": frozenset(),
    "failed_final": frozenset(),
    "uncertain": frozenset(),
    "mapping_conflict": frozenset(),
}
_TOOL_ASSET_TERMINAL_STATES = frozenset({"partially_succeeded", "succeeded", "failed_retryable", "failed_final", "uncertain", "mapping_conflict"})
_V1_FIELDS = (
    "schema_version",
    "operation",
    "tenant_id",
    "project_global_id",
    "request_global_id",
    "profile_id",
    "profile_version",
    "profile_snapshot_hash",
    "source_stream_key_hash",
    "source_hash",
    "expected_mapping_version",
    "actor_user_id",
    "service_actor_user_id",
    "request_id",
    "idempotency_key_hash",
    "target_idempotency_key_hash",
    "semantic_source_effect_hash",
    "semantic_effect_hash",
    "event_snapshot_hash",
)
_IMMUTABLE_V1_FIELDS = (
    "event_id",
    "event_type",
    "global_id",
    "object_version",
    "trace_id",
    "payload_hash",
    "payload",
    *_V1_FIELDS,
    "expected_target_version",
)
_V2_FIELDS = (
    "schema_version",
    "operation",
    "tenant_id",
    "project_global_id",
    "mbom_request_global_id",
    "profile_id",
    "profile_version",
    "profile_snapshot_hash",
    "source_stream_key_hash",
    "source_hash",
    "mbom_topology_hash",
    "item_mapping_set_hash",
    "mbom_mapping_set_hash",
    "mbom_node_manifest_hash",
    "actor_user_id",
    "service_actor_user_id",
    "request_id",
    "idempotency_key_hash",
    "target_idempotency_key_hash",
    "semantic_effect_hash",
    "event_snapshot_hash",
)
_IMMUTABLE_V2_FIELDS = (
    "event_id",
    "event_type",
    "global_id",
    "object_version",
    "trace_id",
    "payload_hash",
    "payload",
    *_V2_FIELDS,
)
_V3_FIELDS = (
    "schema_version", "operation", "tenant_id", "project_global_id",
    "tool_asset_request_global_id", "tooling_set_global_id", "profile_id",
    "profile_version", "profile_snapshot_hash", "source_stream_key_hash",
    "source_hash", "tool_asset_mapping_expectation_hash", "actor_user_id",
    "service_actor_user_id", "request_id", "idempotency_key_hash",
    "target_idempotency_key_hash", "semantic_effect_hash", "event_snapshot_hash",
)
_IMMUTABLE_V3_FIELDS = (
    "event_id", "event_type", "global_id", "object_version", "trace_id",
    "payload_hash", "payload", *_V3_FIELDS,
)


class NPIOutboxMessage(Document):
    """Durable support projection with isolated Item-v1, MBOM-v2 and Tool-Asset-v3 branches."""

    def autoname(self) -> None:
        self.event_id = canonical_uuid(self.event_id, _("Event ID"))
        self.name = self.event_id

    def before_insert(self) -> None:
        if self._is_tool_asset_v3():
            require_tool_asset_execution_outbox_write()
        elif self._is_mbom_v2():
            require_mbom_outbox_write()
        elif self._is_item_v1():
            require_item_outbox_write()

    def before_save(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None and self._was_tool_asset_v3(previous) != self._is_tool_asset_v3() and (self._was_tool_asset_v3(previous) or self._is_tool_asset_v3()):
            deny_tool_asset_outbox_conversion()
        if self._is_tool_asset_v3() or (previous is not None and self._was_tool_asset_v3(previous)):
            require_tool_asset_execution_outbox_write()
            if previous is not None and self._was_tool_asset_v3(previous) and previous.state in _TOOL_ASSET_TERMINAL_STATES:
                deny_tool_asset_execution_history_update()
            return
        if previous is not None and (
            (self._was_item_v1(previous) and self._is_mbom_v2())
            or (self._was_mbom_v2(previous) and self._is_item_v1())
            or (not self._was_mbom_v2(previous) and self._is_mbom_v2())
        ):
            deny_outbox_operation_conversion()
        if self._is_mbom_v2() or (previous is not None and self._was_mbom_v2(previous)):
            require_mbom_outbox_write()
        if previous is not None and self._was_mbom_v2(previous):
            if previous.state in _MBOM_TERMINAL_STATES:
                deny_mbom_history_update()
            return
        if previous is not None and not self._was_item_v1(previous) and self._is_item_v1():
            deny_legacy_outbox_promotion()
        if self._is_item_v1() or (previous is not None and self._was_item_v1(previous)):
            require_item_outbox_write()
        if previous is not None and self._was_item_v1(previous) and _is_legacy_item_v1(previous):
            deny_item_history_update()
        if previous is not None and self._was_item_v1(previous):
            if previous.state in _ITEM_TERMINAL_STATES:
                deny_item_history_update()

    def before_validate(self) -> None:
        if self._is_tool_asset_v3():
            for fieldname, label in (
                ("event_id", _("Event ID")),
                ("global_id", _("Global ID")),
                ("project_global_id", _("Project Global ID")),
                ("tool_asset_request_global_id", _("Tool Asset Execution Request")),
                ("tooling_set_global_id", _("Tooling Set")),
                ("request_id", _("Request ID")),
            ):
                setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
            if self.tool_asset_last_attempt_global_id:
                self.tool_asset_last_attempt_global_id = canonical_uuid(self.tool_asset_last_attempt_global_id, _("Last Tool Asset Attempt"))
            if self.tool_asset_result_global_id:
                self.tool_asset_result_global_id = canonical_uuid(self.tool_asset_result_global_id, _("Tool Asset Result"))
            if self.claim_token:
                self.claim_token = canonical_uuid(self.claim_token, _("Tool Asset Outbox Claim Token"))
            return
        if self._is_mbom_v2():
            for fieldname, label in (
                ("event_id", _("Event ID")),
                ("global_id", _("Global ID")),
                ("project_global_id", _("Project Global ID")),
                ("mbom_request_global_id", _("MBOM Publish Request")),
                ("request_id", _("Request ID")),
            ):
                setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
            if self.mbom_last_attempt_global_id:
                self.mbom_last_attempt_global_id = canonical_uuid(
                    self.mbom_last_attempt_global_id,
                    _("Last MBOM Publish Attempt"),
                )
            if self.mbom_result_global_id:
                self.mbom_result_global_id = canonical_uuid(
                    self.mbom_result_global_id,
                    _("MBOM Publish Result"),
                )
            if self.claim_token:
                self.claim_token = canonical_uuid(
                    self.claim_token,
                    _("MBOM Outbox Claim Token"),
                )
            return
        if not self._is_item_v1():
            return
        for fieldname, label in (
            ("event_id", _("Event ID")),
            ("global_id", _("Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("request_global_id", _("Item Publish Request")),
            ("request_id", _("Request ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.tenant_id = tenant_text(self.tenant_id)
        self.actor_user_id = actor_text(self.actor_user_id, _("Actor User ID"))
        if self.service_actor_user_id:
            self.service_actor_user_id = actor_text(
                self.service_actor_user_id, _("Service Actor User ID")
            )
        if self.claim_token:
            self.claim_token = canonical_uuid(
                self.claim_token, _("Item Outbox Claim Token")
            )
        if self.last_attempt_global_id:
            self.last_attempt_global_id = canonical_uuid(
                self.last_attempt_global_id, _("Last Item Publish Attempt")
            )
        if self.result_global_id:
            self.result_global_id = canonical_uuid(
                self.result_global_id, _("Item Publish Result")
            )

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if self._is_tool_asset_v3():
            self._validate_tool_asset_v3(previous)
            return
        if previous is not None and self._was_tool_asset_v3(previous):
            deny_tool_asset_outbox_conversion()
        if self._is_mbom_v2():
            self._validate_mbom_v2(previous)
            return
        if previous is not None and self._was_mbom_v2(previous):
            deny_outbox_operation_conversion()
        if previous is not None and not self._was_item_v1(previous):
            if self._is_item_v1() or any(getattr(self, fieldname, None) for fieldname in _V1_FIELDS):
                deny_legacy_outbox_promotion()
            return
        if not self._is_item_v1():
            return
        if previous is not None:
            if previous.state in _ITEM_TERMINAL_STATES:
                deny_item_history_update()
            assert_immutable_fields(self, previous, _IMMUTABLE_V1_FIELDS)
            validate_one_way_transition(
                previous.state,
                self.state,
                allowed=_ITEM_STATES,
                label=_("Item Outbox Message"),
            )
            if int(self.attempt_count or 0) < int(previous.attempt_count or 0):
                frappe.throw(
                    _("Item Outbox attempt count cannot decrease."),
                    frappe.ValidationError,
                )
            if bool(previous.adapter_boundary_crossed) and not bool(
                self.adapter_boundary_crossed
            ):
                frappe.throw(
                    _("The adapter boundary cannot be cleared after it is crossed."),
                    frappe.ValidationError,
                )
        if (
            positive_integer(self.schema_version, _("Schema Version"))
            != ITEM_PUBLISH_SCHEMA_VERSION
            or self.event_type != ITEM_REQUEST_EVENT_TYPE
            or self.operation != ITEM_PUBLISH_OPERATION
            or positive_integer(self.object_version, _("Object Version")) != 1
        ):
            frappe.throw(
                _("The Item Outbox envelope version or operation is invalid."),
                frappe.ValidationError,
            )
        self.trace_id = required_text(self.trace_id, _("Trace ID"), 128)
        self.profile_id = required_text(
            self.profile_id, _("Item Execution Profile ID"), 128
        )
        self.profile_version = positive_integer(
            self.profile_version, _("Item Execution Profile Version")
        )
        self.expected_mapping_version = nonnegative_integer(
            self.expected_mapping_version, _("Expected Item Mapping Version")
        )
        for fieldname, label in (
            ("profile_snapshot_hash", _("Item Execution Profile Snapshot Hash")),
            ("source_stream_key_hash", _("Item Source Stream Key Hash")),
            ("source_hash", _("Item Source Hash")),
            ("idempotency_key_hash", _("Idempotency Key Hash")),
            ("payload_hash", _("Payload Hash")),
        ):
            setattr(self, fieldname, lowercase_sha256(getattr(self, fieldname), label))
        for fieldname, label in (
            ("target_idempotency_key_hash", _("Target Idempotency Key Hash")),
            ("semantic_source_effect_hash", _("Semantic Source Effect Hash")),
            ("semantic_effect_hash", _("Semantic Target Effect Hash")),
        ):
            if getattr(self, fieldname, None):
                setattr(self, fieldname, lowercase_sha256(getattr(self, fieldname), label))
        if (
            not self.target_idempotency_key_hash
            or not self.service_actor_user_id
            or not self.semantic_source_effect_hash
        ):
            frappe.throw(
                _("Executable Item Outbox messages require the exact target key and service actor."),
                frappe.ValidationError,
            )
        payload = json_object(self.payload, _("Payload"))
        if canonical_hash(payload) != self.payload_hash:
            frappe.throw(
                _("The Item Outbox payload hash does not match its exact fields."),
                frappe.ValidationError,
            )
        expected_event_hash = canonical_hash(
            {
                "schemaVersion": 1,
                "eventId": self.event_id,
                "eventType": self.event_type,
                "globalId": self.global_id,
                "objectVersion": 1,
                "tenantId": self.tenant_id,
                "projectGlobalId": self.project_global_id,
                "requestGlobalId": self.request_global_id,
                "operation": self.operation,
                "profileId": self.profile_id,
                "profileVersion": self.profile_version,
                "profileSnapshotHash": self.profile_snapshot_hash,
                "sourceStreamKeyHash": self.source_stream_key_hash,
                "sourceHash": self.source_hash,
                "expectedMappingVersion": self.expected_mapping_version,
                "expectedTargetVersion": self.expected_target_version or None,
                "actorUserId": self.actor_user_id,
                "serviceActorUserId": self.service_actor_user_id,
                "requestId": self.request_id,
                "traceId": self.trace_id,
                "idempotencyKeyHash": self.idempotency_key_hash,
                "targetIdempotencyKeyHash": self.target_idempotency_key_hash,
                "semanticSourceEffectHash": self.semantic_source_effect_hash,
                "semanticEffectHash": self.semantic_effect_hash or None,
                "payloadHash": self.payload_hash,
            }
        )
        if lowercase_sha256(
            self.event_snapshot_hash, _("Item Outbox Event Snapshot Hash")
        ) != expected_event_hash:
            frappe.throw(
                _("The Item Outbox event snapshot hash does not match its fields."),
                frappe.ValidationError,
            )
        self.payload = canonical_json(payload)
        self.attempt_count = nonnegative_integer(
            self.attempt_count or 0, _("Attempt Count")
        )
        self._validate_state_shape()

    def on_trash(self) -> None:
        if self._is_tool_asset_v3():
            deny_tool_asset_execution_history_delete()
        elif self._is_mbom_v2():
            deny_mbom_history_delete()
        else:
            deny_item_history_delete()

    def _is_item_v1(self) -> bool:
        return int(self.schema_version or 0) == 1 or self.event_type == ITEM_REQUEST_EVENT_TYPE

    def _is_mbom_v2(self) -> bool:
        return (
            int(self.schema_version or 0) == MBOM_PUBLISH_SCHEMA_VERSION
            or self.event_type == MBOM_REQUEST_EVENT_TYPE
        )

    def _is_tool_asset_v3(self) -> bool:
        return int(self.schema_version or 0) == TOOL_ASSET_OUTBOX_SCHEMA_VERSION or self.event_type == TOOL_ASSET_REQUEST_EVENT_TYPE

    @staticmethod
    def _was_item_v1(document: object) -> bool:
        return int(getattr(document, "schema_version", 0) or 0) == 1 or getattr(
            document, "event_type", None
        ) == ITEM_REQUEST_EVENT_TYPE

    @staticmethod
    def _was_mbom_v2(document: object) -> bool:
        return (
            int(getattr(document, "schema_version", 0) or 0)
            == MBOM_PUBLISH_SCHEMA_VERSION
            or getattr(document, "event_type", None) == MBOM_REQUEST_EVENT_TYPE
        )

    @staticmethod
    def _was_tool_asset_v3(document: object) -> bool:
        return int(getattr(document, "schema_version", 0) or 0) == TOOL_ASSET_OUTBOX_SCHEMA_VERSION or getattr(document, "event_type", None) == TOOL_ASSET_REQUEST_EVENT_TYPE

    def _validate_tool_asset_v3(self, previous: object | None) -> None:
        if previous is not None:
            if not self._was_tool_asset_v3(previous):
                deny_tool_asset_outbox_conversion()
            if getattr(previous, "state", None) in _TOOL_ASSET_TERMINAL_STATES:
                deny_tool_asset_execution_history_update()
            assert_immutable_fields(self, previous, _IMMUTABLE_V3_FIELDS)
            validate_one_way_transition(previous.state, self.state, allowed=_TOOL_ASSET_STATES, label=_("Tool Asset Outbox Message"))
            if int(self.attempt_count or 0) < int(previous.attempt_count or 0):
                frappe.throw(_("Tool Asset Outbox attempt count cannot decrease."), frappe.ValidationError)
            if bool(previous.adapter_boundary_crossed) and not bool(self.adapter_boundary_crossed):
                frappe.throw(_("The adapter boundary cannot be cleared after it is crossed."), frappe.ValidationError)
        if int(self.schema_version or 0) != TOOL_ASSET_OUTBOX_SCHEMA_VERSION or self.event_type != TOOL_ASSET_REQUEST_EVENT_TYPE or self.operation not in TOOL_ASSET_EXECUTION_OPERATIONS or positive_integer(self.object_version, _("Object Version")) != 1:
            frappe.throw(_("The Tool Asset Outbox envelope version or operation is invalid."), frappe.ValidationError)
        self.tenant_id = tenant_text(self.tenant_id)
        self.trace_id = required_text(self.trace_id, _("Trace ID"), 128)
        self.actor_user_id = actor_text(self.actor_user_id, _("Actor User ID"))
        self.service_actor_user_id = actor_text(self.service_actor_user_id, _("Service Actor User ID"))
        self.profile_id = required_text(self.profile_id, _("Tool Asset Execution Profile ID"), 128)
        self.profile_version = positive_integer(self.profile_version, _("Tool Asset Execution Profile Version"))
        for fieldname, label in (
            ("profile_snapshot_hash", _("Tool Asset Execution Profile Snapshot Hash")),
            ("source_stream_key_hash", _("Tool Asset Source Stream Key Hash")),
            ("source_hash", _("Tool Asset Source Hash")),
            ("tool_asset_mapping_expectation_hash", _("Tool Asset Mapping Expectation Hash")),
            ("idempotency_key_hash", _("Idempotency Key Hash")),
            ("target_idempotency_key_hash", _("Target Idempotency Key Hash")),
            ("semantic_effect_hash", _("Semantic Target Effect Hash")),
            ("payload_hash", _("Payload Hash")),
        ):
            setattr(self, fieldname, lowercase_sha256(getattr(self, fieldname), label))
        payload = json_object(self.payload, _("Payload"))
        if canonical_hash(payload) != self.payload_hash:
            frappe.throw(_("The Tool Asset Outbox payload hash does not match its exact fields."), frappe.ValidationError)
        expected_event_hash = canonical_hash({
            "schemaVersion": TOOL_ASSET_OUTBOX_SCHEMA_VERSION,
            "apiVersion": TOOL_ASSET_EXECUTION_API_VERSION,
            "eventId": self.event_id,
            "eventType": self.event_type,
            "globalId": self.global_id,
            "objectVersion": 1,
            "tenantId": self.tenant_id,
            "projectGlobalId": self.project_global_id,
            "toolAssetRequestGlobalId": self.tool_asset_request_global_id,
            "toolingSetGlobalId": self.tooling_set_global_id,
            "operation": self.operation,
            "profileId": self.profile_id,
            "profileVersion": self.profile_version,
            "profileSnapshotHash": self.profile_snapshot_hash,
            "sourceStreamKeyHash": self.source_stream_key_hash,
            "sourceHash": self.source_hash,
            "mappingExpectationHash": self.tool_asset_mapping_expectation_hash,
            "actorUserId": self.actor_user_id,
            "serviceActorUserId": self.service_actor_user_id,
            "requestId": self.request_id,
            "traceId": self.trace_id,
            "idempotencyKeyHash": self.idempotency_key_hash,
            "targetIdempotencyKeyHash": self.target_idempotency_key_hash,
            "semanticEffectHash": self.semantic_effect_hash,
            "payloadHash": self.payload_hash,
        })
        if lowercase_sha256(self.event_snapshot_hash, _("Tool Asset Outbox Event Snapshot Hash")) != expected_event_hash:
            frappe.throw(_("The Tool Asset Outbox event snapshot hash does not match its fields."), frappe.ValidationError)
        self.payload = canonical_json(payload)
        self.attempt_count = nonnegative_integer(self.attempt_count or 0, _("Attempt Count"))
        claim_values = (self.claim_token, self.claimed_at, self.lease_expires_at)
        if any(claim_values) != all(claim_values):
            frappe.throw(_("Tool Asset Outbox claim fields must be present together."), frappe.ValidationError)
        if self.claimed_at:
            claimed_at = utc_datetime_text(self.claimed_at, _("Claimed At"))
            expires_at = utc_datetime_text(self.lease_expires_at, _("Lease Expires At"))
            if expires_at <= claimed_at:
                frappe.throw(_("Tool Asset Outbox lease expiry must follow claim time."), frappe.ValidationError)
            self.claimed_at = frappe_utc_datetime_text(claimed_at, _("Claimed At"))
            self.lease_expires_at = frappe_utc_datetime_text(expires_at, _("Lease Expires At"))
        terminal = self.state in _TOOL_ASSET_TERMINAL_STATES
        if self.state not in _TOOL_ASSET_STATES:
            frappe.throw(_("The Tool Asset Outbox state shape is invalid."), frappe.ValidationError)
        if self.state == "pending" and any(claim_values):
            frappe.throw(_("A pending Tool Asset Outbox message cannot retain a live claim."), frappe.ValidationError)
        if self.state == "pending" and self.adapter_boundary_crossed:
            frappe.throw(_("A Tool Asset Outbox message cannot return to pending after the adapter boundary."), frappe.ValidationError)
        if self.state == "processing" and not all(claim_values):
            frappe.throw(_("A processing Tool Asset Outbox message requires an exact claim."), frappe.ValidationError)
        if terminal != bool(self.tool_asset_result_global_id):
            frappe.throw(_("Tool Asset Outbox terminal state and result reference must agree."), frappe.ValidationError)
        if terminal and not all(claim_values):
            frappe.throw(_("Terminal Tool Asset Outbox truth requires complete claim and result history."), frappe.ValidationError)
        if self.state == "uncertain" and not self.adapter_boundary_crossed:
            frappe.throw(_("An uncertain Tool Asset Outbox message requires a crossed adapter boundary."), frappe.ValidationError)

    def _validate_mbom_v2(self, previous: object | None) -> None:
        if previous is not None:
            if not self._was_mbom_v2(previous):
                deny_outbox_operation_conversion()
            if getattr(previous, "state", None) in _MBOM_TERMINAL_STATES:
                deny_mbom_history_update()
            assert_immutable_fields(self, previous, _IMMUTABLE_V2_FIELDS)
            validate_one_way_transition(
                previous.state,
                self.state,
                allowed=_MBOM_STATES,
                label=_("MBOM Outbox Message"),
            )
            if int(self.attempt_count or 0) < int(previous.attempt_count or 0):
                frappe.throw(
                    _("MBOM Outbox attempt count cannot decrease."),
                    frappe.ValidationError,
                )
            if bool(previous.adapter_boundary_crossed) and not bool(
                self.adapter_boundary_crossed
            ):
                frappe.throw(
                    _("The adapter boundary cannot be cleared after it is crossed."),
                    frappe.ValidationError,
                )
        if (
            positive_integer(self.schema_version, _("Schema Version"))
            != MBOM_PUBLISH_SCHEMA_VERSION
            or self.event_type != MBOM_REQUEST_EVENT_TYPE
            or self.operation != MBOM_PUBLISH_OPERATION
            or positive_integer(self.object_version, _("Object Version")) != 1
        ):
            frappe.throw(
                _("The MBOM Outbox envelope version or operation is invalid."),
                frappe.ValidationError,
            )
        self.tenant_id = tenant_text(self.tenant_id)
        self.trace_id = required_text(self.trace_id, _("Trace ID"), 128)
        self.profile_id = required_text(
            self.profile_id,
            _("MBOM Execution Profile ID"),
            128,
        )
        self.profile_version = positive_integer(
            self.profile_version,
            _("MBOM Execution Profile Version"),
        )
        self.actor_user_id = actor_text(self.actor_user_id, _("Actor User ID"))
        self.service_actor_user_id = actor_text(
            self.service_actor_user_id,
            _("Service Actor User ID"),
        )
        for fieldname, label in (
            ("profile_snapshot_hash", _("MBOM Execution Profile Snapshot Hash")),
            ("source_stream_key_hash", _("MBOM Source Stream Key Hash")),
            ("source_hash", _("MBOM Source Hash")),
            ("mbom_topology_hash", _("MBOM Topology Hash")),
            ("item_mapping_set_hash", _("Item Mapping Set Hash")),
            ("mbom_mapping_set_hash", _("MBOM Mapping Set Hash")),
            ("mbom_node_manifest_hash", _("MBOM Node Manifest Hash")),
            ("idempotency_key_hash", _("Idempotency Key Hash")),
            ("target_idempotency_key_hash", _("Target Idempotency Key Hash")),
            ("semantic_effect_hash", _("Semantic Target Effect Hash")),
            ("payload_hash", _("Payload Hash")),
        ):
            setattr(self, fieldname, lowercase_sha256(getattr(self, fieldname), label))
        payload = json_object(self.payload, _("Payload"))
        if canonical_hash(payload) != self.payload_hash:
            frappe.throw(
                _("The MBOM Outbox payload hash does not match its exact fields."),
                frappe.ValidationError,
            )
        expected_event_hash = canonical_hash(
            {
                "schemaVersion": MBOM_PUBLISH_SCHEMA_VERSION,
                "eventId": self.event_id,
                "eventType": self.event_type,
                "globalId": self.global_id,
                "objectVersion": 1,
                "tenantId": self.tenant_id,
                "projectGlobalId": self.project_global_id,
                "requestGlobalId": self.mbom_request_global_id,
                "operation": self.operation,
                "profileId": self.profile_id,
                "profileVersion": self.profile_version,
                "profileSnapshotHash": self.profile_snapshot_hash,
                "sourceStreamKeyHash": self.source_stream_key_hash,
                "sourceHash": self.source_hash,
                "topologyHash": self.mbom_topology_hash,
                "itemMappingSetHash": self.item_mapping_set_hash,
                "mbomMappingSetHash": self.mbom_mapping_set_hash,
                "nodeManifestHash": self.mbom_node_manifest_hash,
                "actorUserId": self.actor_user_id,
                "serviceActorUserId": self.service_actor_user_id,
                "requestId": self.request_id,
                "traceId": self.trace_id,
                "idempotencyKeyHash": self.idempotency_key_hash,
                "targetIdempotencyKeyHash": self.target_idempotency_key_hash,
                "semanticEffectHash": self.semantic_effect_hash,
                "payloadHash": self.payload_hash,
            }
        )
        if lowercase_sha256(
            self.event_snapshot_hash,
            _("MBOM Outbox Event Snapshot Hash"),
        ) != expected_event_hash:
            frappe.throw(
                _("The MBOM Outbox event snapshot hash does not match its fields."),
                frappe.ValidationError,
            )
        self.payload = canonical_json(payload)
        self.attempt_count = nonnegative_integer(
            self.attempt_count or 0,
            _("Attempt Count"),
        )
        claim_values = (self.claim_token, self.claimed_at, self.lease_expires_at)
        if any(claim_values) != all(claim_values):
            frappe.throw(
                _("MBOM Outbox claim fields must be present together."),
                frappe.ValidationError,
            )
        if self.claimed_at:
            claimed_at = utc_datetime_text(self.claimed_at, _("Claimed At"))
            expires_at = utc_datetime_text(
                self.lease_expires_at,
                _("Lease Expires At"),
            )
            if expires_at <= claimed_at:
                frappe.throw(
                    _("MBOM Outbox lease expiry must follow claim time."),
                    frappe.ValidationError,
                )
            self.claimed_at = frappe_utc_datetime_text(claimed_at, _("Claimed At"))
            self.lease_expires_at = frappe_utc_datetime_text(
                expires_at,
                _("Lease Expires At"),
            )
        if self.state == "pending" and any(claim_values):
            frappe.throw(
                _("A pending MBOM Outbox message cannot retain a live claim."),
                frappe.ValidationError,
            )
        if self.state == "pending" and self.adapter_boundary_crossed:
            frappe.throw(
                _("An MBOM Outbox message cannot return to pending after the adapter boundary."),
                frappe.ValidationError,
            )
        if self.state == "processing" and not all(claim_values):
            frappe.throw(
                _("A processing MBOM Outbox message requires an exact claim."),
                frappe.ValidationError,
            )
        terminal = self.state in _MBOM_TERMINAL_STATES
        if terminal != bool(self.mbom_result_global_id):
            frappe.throw(
                _("MBOM Outbox terminal state and result reference must agree."),
                frappe.ValidationError,
            )
        if self.state == "uncertain" and not self.adapter_boundary_crossed:
            frappe.throw(
                _("An uncertain MBOM Outbox message requires a crossed adapter boundary."),
                frappe.ValidationError,
            )

    def _validate_state_shape(self) -> None:
        claim_values = (self.claim_token, self.claimed_at, self.lease_expires_at)
        if any(claim_values) != all(claim_values):
            frappe.throw(
                _("Item Outbox claim fields must be present together."),
                frappe.ValidationError,
            )
        if self.claimed_at:
            claimed_at = utc_datetime_text(self.claimed_at, _("Claimed At"))
            expires_at = utc_datetime_text(
                self.lease_expires_at, _("Lease Expires At")
            )
            if expires_at <= claimed_at:
                frappe.throw(
                    _("Item Outbox lease expiry must follow claim time."),
                    frappe.ValidationError,
                )
            self.claimed_at = frappe_utc_datetime_text(claimed_at, _("Claimed At"))
            self.lease_expires_at = frappe_utc_datetime_text(
                expires_at, _("Lease Expires At")
            )
        if self.state == "pending" and any(claim_values):
            frappe.throw(
                _("A pending Item Outbox message cannot retain a live claim."),
                frappe.ValidationError,
            )
        if self.state == "pending" and self.adapter_boundary_crossed:
            frappe.throw(
                _("An Item Outbox message cannot return to pending after the adapter boundary."),
                frappe.ValidationError,
            )
        if self.state == "processing" and not all(claim_values):
            frappe.throw(
                _("A processing Item Outbox message requires an exact claim."),
                frappe.ValidationError,
            )
        terminal = self.state in _ITEM_TERMINAL_STATES
        if terminal and not self.result_global_id:
            frappe.throw(
                _("A terminal Item Outbox message requires an exact result."),
                frappe.ValidationError,
            )
        if not terminal and self.result_global_id:
            frappe.throw(
                _("A non-terminal Item Outbox message cannot reference a terminal result."),
                frappe.ValidationError,
            )
        if self.state == "uncertain" and not self.adapter_boundary_crossed:
            frappe.throw(
                _("An uncertain Item Outbox message requires a crossed adapter boundary."),
                frappe.ValidationError,
            )
        if self.last_error_at:
            self.last_error_at = frappe_utc_datetime_text(
                utc_datetime_text(self.last_error_at, _("Last Error At")),
                _("Last Error At"),
            )


def _is_legacy_item_v1(value: object) -> bool:
    """Return true when an existing 8dd Item Outbox row is not executable."""

    return any(
        not getattr(value, fieldname, None)
        for fieldname in (
            "target_idempotency_key_hash",
            "service_actor_user_id",
            "semantic_source_effect_hash",
            "semantic_effect_hash",
        )
    )
