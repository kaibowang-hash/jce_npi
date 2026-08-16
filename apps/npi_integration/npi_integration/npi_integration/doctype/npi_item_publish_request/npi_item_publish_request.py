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
    ITEM_PUBLISH_API_VERSION,
    ITEM_PUBLISH_OPERATION,
    ITEM_PUBLISH_SCHEMA_VERSION,
    ItemPublishIntent,
    ItemPublishRequestState,
    ItemTargetMode,
    canonical_hash,
)
from npi_integration.item_publish.frappe_validation import (
    deny_item_history_delete,
    require_item_request_write,
    validate_one_way_transition,
)


_REQUEST_TRANSITIONS = {
    "validated_mock": frozenset(),
    "queued": frozenset({"processing", "failed_final"}),
    "processing": frozenset(
        {
            "synthetic_verified",
            "succeeded",
            "failed_retryable",
            "failed_final",
            "uncertain_after_timeout",
            "mapping_conflict",
        }
    ),
    "synthetic_verified": frozenset(),
    "succeeded": frozenset(),
    "failed_retryable": frozenset(),
    "failed_final": frozenset(),
    "uncertain_after_timeout": frozenset(),
    "mapping_conflict": frozenset(),
}
_IMMUTABLE_FIELDS = (
    "global_id",
    "schema_version",
    "api_version",
    "operation",
    "tenant_id",
    "project_global_id",
    "source_stream_key_hash",
    "engineering_item_id",
    "selected_publish_node_global_id",
    "source_snapshot",
    "source_hash",
    "released_evidence_snapshot",
    "released_evidence_hash",
    "profile_id",
    "profile_version",
    "profile_snapshot_hash",
    "target_mode",
    "environment_code",
    "intent",
    "expected_mapping_version",
    "expected_formal_item_code",
    "expected_target_version",
    "expected_mapping_observation_hash",
    "dispatch_allowed",
    "actor_user_id",
    "request_id",
    "trace_id",
    "idempotency_key_hash",
    "payload_hash",
    "created_at",
)


class NPIItemPublishRequest(Document):
    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_item_request_write()

    def before_save(self) -> None:
        require_item_request_write()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("selected_publish_node_global_id", _("Selected Publish Node Global ID")),
            ("request_id", _("Request ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        if self.outbox_event_id:
            self.outbox_event_id = canonical_uuid(
                self.outbox_event_id, _("Item Outbox Event ID")
            )
        if self.result_global_id:
            self.result_global_id = canonical_uuid(
                self.result_global_id, _("Item Publish Result")
            )
        self.tenant_id = tenant_text(self.tenant_id)
        self.actor_user_id = actor_text(self.actor_user_id, _("Actor User ID"))

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _IMMUTABLE_FIELDS)
            validate_one_way_transition(
                previous.state,
                self.state,
                allowed=_REQUEST_TRANSITIONS,
                label=_("Item Publish Request"),
            )
            if bool(previous.outbox_event_id) and self.outbox_event_id != previous.outbox_event_id:
                frappe.throw(
                    _("The Item publish Outbox reference cannot be replaced."),
                    frappe.ValidationError,
                )
            if bool(previous.result_global_id) and self.result_global_id != previous.result_global_id:
                frappe.throw(
                    _("The Item publish result reference cannot be replaced."),
                    frappe.ValidationError,
                )
        if (
            positive_integer(self.schema_version, _("Schema Version"))
            != ITEM_PUBLISH_SCHEMA_VERSION
            or self.api_version != ITEM_PUBLISH_API_VERSION
            or self.operation != ITEM_PUBLISH_OPERATION
        ):
            frappe.throw(
                _("The Item publish request version or operation is invalid."),
                frappe.ValidationError,
            )
        try:
            mode = ItemTargetMode(self.target_mode)
            intent = ItemPublishIntent(self.intent)
            state = ItemPublishRequestState(self.state)
        except ValueError as error:
            frappe.throw(
                _("The Item publish request state, intent, or target mode is invalid."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.") from error
        self.engineering_item_id = required_text(
            self.engineering_item_id, _("Engineering Item ID"), 128
        )
        self.profile_id = required_text(
            self.profile_id, _("Item Execution Profile ID"), 128
        )
        self.environment_code = required_text(
            self.environment_code, _("Target Environment Code"), 64
        )
        self.profile_version = positive_integer(
            self.profile_version, _("Item Execution Profile Version")
        )
        mapping_version = nonnegative_integer(
            self.expected_mapping_version, _("Expected Item Mapping Version")
        )
        for fieldname, label in (
            ("source_stream_key_hash", _("Item Source Stream Key Hash")),
            ("source_hash", _("Item Source Hash")),
            ("released_evidence_hash", _("Released Item Evidence Hash")),
            ("profile_snapshot_hash", _("Item Execution Profile Snapshot Hash")),
            ("idempotency_key_hash", _("Idempotency Key Hash")),
            ("payload_hash", _("Item Publish Request Payload Hash")),
        ):
            setattr(self, fieldname, lowercase_sha256(getattr(self, fieldname), label))
        source = json_object(self.source_snapshot, _("Exact Item Source Snapshot"))
        evidence = json_object(
            self.released_evidence_snapshot, _("Exact Released Item Evidence")
        )
        source_payload = dict(source)
        source_payload.pop("streamKeyHash", None)
        source_payload.pop("sourceHash", None)
        if canonical_hash(source_payload) != self.source_hash:
            frappe.throw(
                _("The exact Item source snapshot hash does not match its fields."),
                frappe.ValidationError,
            )
        if canonical_hash(evidence) != self.released_evidence_hash:
            frappe.throw(
                _("The released Item evidence hash does not match its fields."),
                frappe.ValidationError,
            )
        exact_source = {
            "tenantId": self.tenant_id,
            "projectGlobalId": self.project_global_id,
            "engineeringItemId": self.engineering_item_id,
            "selectedPublishNodeGlobalId": self.selected_publish_node_global_id,
            "streamKeyHash": self.source_stream_key_hash,
            "sourceHash": self.source_hash,
        }
        if any(source.get(key) != value for key, value in exact_source.items()):
            frappe.throw(
                _("The exact Item source snapshot does not match its identities."),
                frappe.ValidationError,
            )
        forbidden = {
            "quantity",
            "parentLineGlobalId",
            "alternateGroup",
            "effectivity",
            "mbom",
        }
        if _contains_forbidden_key(source, forbidden):
            frappe.throw(
                _("Item publish source contains MBOM-owned fields."),
                frappe.ValidationError,
            )
        expected_values = (
            self.expected_formal_item_code,
            self.expected_target_version,
            self.expected_mapping_observation_hash,
        )
        if mapping_version == 0:
            if any(expected_values) or intent is not ItemPublishIntent.CREATE_ITEM:
                frappe.throw(
                    _("An unmapped Item request must use the create intent without target identity."),
                    frappe.ValidationError,
                )
        elif not all(expected_values) or intent is not ItemPublishIntent.UPDATE_ITEM_ENGINEERING_FIELDS:
            frappe.throw(
                _("A mapped Item request requires exact update target truth."),
                frappe.ValidationError,
            )
        if self.expected_mapping_observation_hash:
            self.expected_mapping_observation_hash = lowercase_sha256(
                self.expected_mapping_observation_hash,
                _("Expected Mapping Observation Hash"),
            )
        initial_state = (
            ItemPublishRequestState.VALIDATED_MOCK
            if mode is ItemTargetMode.MOCK
            else ItemPublishRequestState.QUEUED
        )
        if previous is None and state is not initial_state:
            frappe.throw(
                _("The initial Item publish request state does not match its target mode."),
                frappe.ValidationError,
            )
        if mode is ItemTargetMode.MOCK:
            if self.dispatch_allowed or self.outbox_event_id or state is not ItemPublishRequestState.VALIDATED_MOCK:
                frappe.throw(
                    _("Mock Item publish requests cannot dispatch or report target progress."),
                    frappe.ValidationError,
                )
        elif not self.dispatch_allowed:
            frappe.throw(
                _("Executable Item publish requests must retain dispatch authority."),
                frappe.ValidationError,
            )
        payload = {
            "schemaVersion": 1,
            "apiVersion": self.api_version,
            "operation": self.operation,
            "source": source,
            "releasedEvidence": evidence,
            "profile": {
                "profileId": self.profile_id,
                "profileVersion": self.profile_version,
                "targetMode": mode.value,
                "environmentCode": self.environment_code,
                "snapshotHash": self.profile_snapshot_hash,
            },
            "mappingExpectation": {
                "mappingVersion": mapping_version,
                "formalItemCode": self.expected_formal_item_code or None,
                "targetVersion": self.expected_target_version or None,
                "observationHash": self.expected_mapping_observation_hash or None,
            },
            "intent": intent.value,
        }
        if canonical_hash(payload) != self.payload_hash:
            frappe.throw(
                _("The Item publish request payload hash does not match its fields."),
                frappe.ValidationError,
            )
        expected_version = 1 if previous is None else int(previous.optimistic_version) + 1
        if positive_integer(self.optimistic_version, _("Optimistic Version")) != expected_version:
            frappe.throw(
                _("The Item publish request optimistic version must advance by one."),
                frappe.ValidationError,
            )
        self.source_snapshot = canonical_json(source)
        self.released_evidence_snapshot = canonical_json(evidence)
        self.trace_id = required_text(self.trace_id, _("Trace ID"), 128)
        self.created_at = frappe_utc_datetime_text(
            utc_datetime_text(self.created_at, _("Created At")), _("Created At")
        )
        self.updated_at = frappe_utc_datetime_text(
            utc_datetime_text(self.updated_at, _("Updated At")), _("Updated At")
        )

    def on_trash(self) -> None:
        deny_item_history_delete()


def _contains_forbidden_key(value: object, forbidden: set[str]) -> bool:
    if isinstance(value, dict):
        return any(
            key in forbidden or _contains_forbidden_key(item, forbidden)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_key(item, forbidden) for item in value)
    return False
