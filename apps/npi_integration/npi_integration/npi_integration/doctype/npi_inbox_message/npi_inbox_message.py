from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    assert_immutable_fields,
    canonical_json,
    canonical_uuid,
    frappe_utc_datetime_text,
    json_object,
    lowercase_sha256,
    positive_integer,
    required_text,
    tenant_text,
    utc_datetime_text,
)
from npi_integration.inbound_project.domain import (
    PROJECT_SOURCE_EVENT_SCHEMA_VERSION,
    ProjectSourceContractError,
    SourceStreamIdentity,
    canonical_json_hash,
    parse_project_source_event,
    raw_body_hash,
)
from npi_integration.inbound_project.frappe_validation import (
    deny_inbound_project_delete,
    deny_legacy_inbox_update,
    require_inbox_write,
)
from npi_integration.integration_operations.frappe_validation import (
    integration_operation_manual_replay_is_active,
)


_IMMUTABLE_V1_FIELDS = (
    "receipt_id",
    "schema_version",
    "authenticated",
    "tenant_id",
    "profile_id",
    "profile_version",
    "policy_snapshot",
    "policy_hash",
    "event_id",
    "event_type",
    "event_version",
    "source_system",
    "target_system",
    "global_id",
    "source_object_type",
    "source_object_id",
    "source_key_hash",
    "object_version",
    "event_snapshot",
    "canonical_event_hash",
    "payload",
    "payload_hash",
    "raw_body",
    "raw_body_hash",
    "signing_key_id",
    "signed_at",
    "received_at",
    "request_id",
    "trace_id",
    "correlation_id",
    "actor_id",
    "sensitivity",
    "receipt_snapshot",
    "receipt_hash",
)
_PROCESSING_FIELDS = (
    "state",
    "disposition",
    "claim_token",
    "claimed_at",
    "lease_expires_at",
    "attempt_count",
    "last_error_code",
    "last_error_at",
    "project_global_id",
    "project_result_hash",
)
_TERMINAL_STATES = frozenset(
    {
        "succeeded",
        "failed_retryable",
        "failed_final",
        "quarantined",
        "superseded",
        "received_after_creation",
    }
)


class NPIInboxMessage(Document):
    """Support projection for a durable inbound integration message."""

    def autoname(self) -> None:
        if self.receipt_id:
            self.receipt_id = canonical_uuid(self.receipt_id, _("Receipt ID"))
            self.name = self.receipt_id

    def before_insert(self) -> None:
        require_inbox_write()

    def before_save(self) -> None:
        require_inbox_write()
        previous = self.get_doc_before_save()
        if previous is not None and not _is_v1(previous):
            deny_legacy_inbox_update()
        if (
            previous is not None
            and str(previous.state) in _TERMINAL_STATES
            and str(self.state) != str(previous.state)
            and not (
                str(previous.state) == "failed_retryable"
                and str(self.state) == "pending"
                and integration_operation_manual_replay_is_active(
                    "receive_project_submission"
                )
            )
        ):
            deny_legacy_inbox_update()

    def before_validate(self) -> None:
        if not _is_v1(self):
            if self.get_doc_before_save() is None:
                frappe.throw(
                    _("Select the supported authenticated Inbox schema version."),
                    frappe.ValidationError,
                )
            return
        for fieldname, label in (
            ("receipt_id", _("Receipt ID")),
            ("event_id", _("Event ID")),
            ("global_id", _("Global ID")),
            ("request_id", _("Request ID")),
            ("correlation_id", _("Correlation ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        if self.project_global_id:
            self.project_global_id = canonical_uuid(
                self.project_global_id, _("Project Global ID")
            )
        if self.claim_token:
            self.claim_token = canonical_uuid(self.claim_token, _("Claim Token"))
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None and not _is_v1(previous):
            deny_legacy_inbox_update()
        if not _is_v1(self):
            return
        if previous is not None:
            assert_immutable_fields(self, previous, _IMMUTABLE_V1_FIELDS)
        if positive_integer(self.schema_version, _("Schema Version")) != 1:
            frappe.throw(
                _("Select the supported authenticated Inbox schema version."),
                frappe.ValidationError,
            )
        if int(self.authenticated or 0) != 1:
            frappe.throw(
                _("An authenticated Inbox receipt requires verified signature evidence."),
                frappe.ValidationError,
            )
        try:
            event_snapshot = json_object(self.event_snapshot, _("Event Snapshot"))
            event = parse_project_source_event(
                canonical_json(event_snapshot).encode("utf-8")
            )
            if (
                not isinstance(self.raw_body, str)
                or not 2 <= len(self.raw_body.encode("utf-8")) <= 262_144
            ):
                raise ProjectSourceContractError("raw body size is invalid.")
            raw_body = self.raw_body.encode("utf-8")
            raw_event = parse_project_source_event(raw_body)
        except (ProjectSourceContractError, UnicodeEncodeError) as error:
            frappe.throw(
                _("The authenticated Inbox event is invalid."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.") from error
        if raw_event.canonical_event_hash != event.canonical_event_hash:
            frappe.throw(
                _("The raw Inbox body does not match its canonical event."),
                frappe.ValidationError,
            )
        expected_scalars = {
            "event_id": str(event.event_id),
            "event_type": event.event_type.value,
            "event_version": PROJECT_SOURCE_EVENT_SCHEMA_VERSION,
            "source_system": "ERPNEXT",
            "target_system": "NPI_ONE",
            "global_id": str(event.global_id),
            "source_object_type": event.object_type.value,
            "source_object_id": event.source_object_id,
            "object_version": event.object_version,
            "payload_hash": event.payload_hash,
            "trace_id": event.trace_id,
            "correlation_id": str(event.correlation_id),
            "actor_id": event.actor_id,
            "sensitivity": "confidential",
        }
        for fieldname, expected in expected_scalars.items():
            actual = getattr(self, fieldname)
            if type(expected) is int:
                matches = type(actual) is int and actual == expected
            else:
                matches = str(actual) == str(expected)
            if not matches:
                frappe.throw(
                    _("The Inbox receipt fields do not match the signed event."),
                    frappe.ValidationError,
                )
        payload = json_object(self.payload, _("Payload"))
        if payload != event.payload.canonical_mapping():
            frappe.throw(
                _("The Inbox payload does not match the signed event."),
                frappe.ValidationError,
            )
        self.payload = canonical_json(payload)
        self.event_snapshot = canonical_json(event.canonical_mapping())
        source_identity = SourceStreamIdentity(
            tenant_id=self.tenant_id,
            profile_id=self.profile_id,
            object_type=event.object_type,
            source_object_id=event.source_object_id,
        )
        if lowercase_sha256(
            self.source_key_hash, _("Source Key Hash")
        ) != source_identity.key_hash:
            frappe.throw(
                _("The Project source key hash does not match its identity."),
                frappe.ValidationError,
            )
        if lowercase_sha256(
            self.canonical_event_hash, _("Canonical Event Hash")
        ) != event.canonical_event_hash:
            frappe.throw(
                _("The canonical event hash does not match the signed event."),
                frappe.ValidationError,
            )
        if lowercase_sha256(self.raw_body_hash, _("Raw Body Hash")) != raw_body_hash(
            raw_body
        ):
            frappe.throw(
                _("The raw body hash does not match the signed body."),
                frappe.ValidationError,
            )
        policy = json_object(self.policy_snapshot, _("Intake Policy Snapshot"))
        self.policy_snapshot = canonical_json(policy)
        if lowercase_sha256(self.policy_hash, _("Intake Policy Hash")) != canonical_json_hash(
            policy
        ):
            frappe.throw(
                _("The intake policy hash does not match its snapshot."),
                frappe.ValidationError,
            )
        self.profile_id = required_text(self.profile_id, _("Source Profile ID"), 128)
        positive_integer(self.profile_version, _("Source Profile Version"))
        self.signing_key_id = required_text(
            self.signing_key_id, _("Signing Key ID"), 128
        )
        signed_at = utc_datetime_text(self.signed_at, _("Signed At"))
        received_at = utc_datetime_text(self.received_at, _("Received At"))
        receipt = json_object(self.receipt_snapshot, _("Receipt Snapshot"))
        expected_receipt = {
            "schema_version": 1,
            "receipt_id": self.receipt_id,
            "tenant_id": self.tenant_id,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "policy_hash": self.policy_hash,
            "source_key_hash": self.source_key_hash,
            "event_id": self.event_id,
            "canonical_event_hash": self.canonical_event_hash,
            "raw_body_hash": self.raw_body_hash,
            "signing_key_id": self.signing_key_id,
            "signed_at": signed_at,
            "received_at": received_at,
            "request_id": self.request_id,
        }
        if receipt != expected_receipt:
            frappe.throw(
                _("The Inbox receipt snapshot does not match its immutable fields."),
                frappe.ValidationError,
            )
        self.receipt_snapshot = canonical_json(expected_receipt)
        if lowercase_sha256(self.receipt_hash, _("Receipt Hash")) != canonical_json_hash(
            expected_receipt
        ):
            frappe.throw(
                _("The Inbox receipt hash does not match its snapshot."),
                frappe.ValidationError,
            )
        self.signed_at = frappe_utc_datetime_text(signed_at, _("Signed At"))
        self.received_at = frappe_utc_datetime_text(received_at, _("Received At"))
        _validate_processing_state(self, previous)

    def on_trash(self) -> None:
        deny_inbound_project_delete()


def _is_v1(document: object) -> bool:
    try:
        return int(getattr(document, "schema_version", 0) or 0) == 1
    except (TypeError, ValueError):
        return False


def _validate_processing_state(document: NPIInboxMessage, previous: object | None) -> None:
    state = str(document.state or "")
    disposition = str(document.disposition or "")
    try:
        attempt_count = int(document.attempt_count or 0)
    except (TypeError, ValueError):
        _invalid_processing_state()
        return
    claim_values = (
        document.claim_token,
        document.claimed_at,
        document.lease_expires_at,
    )
    result_values = (document.project_global_id, document.project_result_hash)
    error_values = (document.last_error_code, document.last_error_at)
    has_claim = all(claim_values)
    has_result = all(result_values)
    has_error = all(error_values)
    if any(claim_values) != has_claim or any(result_values) != has_result or any(
        error_values
    ) != has_error:
        _invalid_processing_state()

    if has_claim:
        claimed_at = utc_datetime_text(document.claimed_at, _("Claimed At"))
        lease_expires_at = utc_datetime_text(
            document.lease_expires_at, _("Lease Expires At")
        )
        if lease_expires_at <= claimed_at:
            _invalid_processing_state()
        document.claimed_at = frappe_utc_datetime_text(claimed_at, _("Claimed At"))
        document.lease_expires_at = frappe_utc_datetime_text(
            lease_expires_at, _("Lease Expires At")
        )
    if has_result:
        document.project_result_hash = lowercase_sha256(
            document.project_result_hash, _("Project Result Hash")
        )
    if has_error:
        document.last_error_code = required_text(
            document.last_error_code, _("Last Error Code"), 128
        )
        last_error_at = utc_datetime_text(
            document.last_error_at, _("Last Error At")
        )
        document.last_error_at = frappe_utc_datetime_text(
            last_error_at, _("Last Error At")
        )

    valid = False
    if state == "pending":
        manual_replay = integration_operation_manual_replay_is_active(
            "receive_project_submission"
        )
        valid = (
            disposition == "pending"
            and (
                attempt_count == 0
                or (manual_replay and previous is not None and attempt_count >= 1)
            )
            and not any((has_claim, has_result, has_error))
        )
    elif state == "processing":
        valid = (
            disposition == "pending"
            and attempt_count >= 1
            and has_claim
            and not has_result
            and not has_error
        )
    elif state == "succeeded":
        valid = (
            disposition in {"project_created", "project_replayed"}
            and attempt_count >= 1
            and has_claim
            and has_result
            and not has_error
        )
    elif state in {"failed_retryable", "failed_final"}:
        valid = (
            disposition == state
            and attempt_count >= 1
            and has_claim
            and has_error
            and not has_result
        )
    elif state in {"superseded", "quarantined"}:
        valid = (
            disposition == ("superseded" if state == "superseded" else "conflicted")
            and not has_result
            and not has_error
            and (
                (attempt_count == 0 and not has_claim)
                or (attempt_count >= 1 and has_claim)
            )
        )
    elif state == "received_after_creation":
        valid = (
            disposition == "received_after_creation"
            and attempt_count == 0
            and not any((has_claim, has_result, has_error))
        )
    if not valid:
        _invalid_processing_state()

    if previous is None:
        return
    previous_state = str(getattr(previous, "state", "") or "")
    if previous_state in _TERMINAL_STATES:
        assert_immutable_fields(document, previous, _PROCESSING_FIELDS)
        return
    allowed = {
        "pending": {"processing"},
        "processing": {
            "processing",
            "succeeded",
            "failed_retryable",
            "failed_final",
            "quarantined",
            "superseded",
        },
    }
    if state not in allowed.get(previous_state, set()):
        frappe.throw(
            _("The Inbox processing transition is not allowed."),
            frappe.ValidationError,
        )
    previous_attempt = int(getattr(previous, "attempt_count", 0) or 0)
    if previous_state == "pending" and attempt_count != previous_attempt + 1:
        frappe.throw(
            _("The Inbox processing transition is not allowed."),
            frappe.ValidationError,
        )
    if previous_state == state == "processing":
        previous_expiry = utc_datetime_text(
            getattr(previous, "lease_expires_at", None), _("Lease Expires At")
        )
        if (
            attempt_count != previous_attempt + 1
            or str(document.claim_token) == str(getattr(previous, "claim_token", ""))
            or utc_datetime_text(document.claimed_at, _("Claimed At"))
            < previous_expiry
        ):
            frappe.throw(
                _("The Inbox processing transition is not allowed."),
                frappe.ValidationError,
            )
    elif previous_state == "processing":
        if (
            attempt_count != previous_attempt
            or str(document.claim_token) != str(getattr(previous, "claim_token", ""))
            or utc_datetime_text(document.claimed_at, _("Claimed At"))
            != utc_datetime_text(getattr(previous, "claimed_at", None), _("Claimed At"))
            or utc_datetime_text(document.lease_expires_at, _("Lease Expires At"))
            != utc_datetime_text(
                getattr(previous, "lease_expires_at", None), _("Lease Expires At")
            )
        ):
            frappe.throw(
                _("The Inbox processing transition is not allowed."),
                frappe.ValidationError,
            )


def _invalid_processing_state() -> None:
    frappe.throw(
        _("The Inbox processing state is invalid."),
        frappe.ValidationError,
    )
