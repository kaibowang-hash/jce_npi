from __future__ import annotations

from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    assert_immutable_fields,
    canonical_uuid,
    lowercase_sha256,
    nonnegative_integer,
    positive_integer,
    tenant_text,
)
from npi_integration.engineering_change.domain import SUMMARY_EVENT_TYPE
from npi_integration.engineering_change.frappe_validation import (
    deny_history_delete,
    deny_history_update,
    require_outbox_write,
)


_IMMUTABLE = (
    "event_id",
    "schema_version",
    "event_type",
    "request_global_id",
    "tenant_id",
    "project_global_id",
    "change_global_id",
    "revision_global_id",
    "source_hash",
    "payload",
    "payload_hash",
    "profile_snapshot_hash",
    "service_actor_user_id",
    "trace_id",
    "target_idempotency_key_hash",
)
_TERMINAL = {
    "synthetic_verified",
    "succeeded",
    "failed_retryable",
    "failed_final",
    "partially_succeeded",
    "uncertain_after_timeout",
    "identity_conflict",
}


class NPIEngineeringChangeSummaryOutbox(Document):
    def autoname(self) -> None:
        self.event_id = canonical_uuid(self.event_id, "Event ID")
        self.name = self.event_id

    def before_insert(self) -> None:
        require_outbox_write("insert")

    def before_save(self) -> None:
        previous = self.get_doc_before_save()
        require_outbox_write("insert" if previous is None else "save")
        if (
            previous is not None
            and str(previous.state) in _TERMINAL
            and str(self.state) != str(previous.state)
        ):
            deny_history_update()

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _IMMUTABLE)
        for fieldname in (
            "event_id",
            "request_global_id",
            "project_global_id",
            "change_global_id",
            "revision_global_id",
        ):
            setattr(
                self,
                fieldname,
                canonical_uuid(getattr(self, fieldname), fieldname),
            )
        for fieldname in (
            "claim_token",
            "last_attempt_global_id",
            "result_global_id",
        ):
            if getattr(self, fieldname, None):
                setattr(
                    self,
                    fieldname,
                    canonical_uuid(getattr(self, fieldname), fieldname),
                )
        if self.event_type != SUMMARY_EVENT_TYPE:
            raise ValueError("Outbox event type is invalid.")
        self.tenant_id = tenant_text(self.tenant_id)
        positive_integer(self.schema_version, "Schema Version")
        nonnegative_integer(self.attempt_count, "Attempt Count")
        for fieldname in (
            "source_hash",
            "payload_hash",
            "profile_snapshot_hash",
            "target_idempotency_key_hash",
        ):
            setattr(
                self,
                fieldname,
                lowercase_sha256(getattr(self, fieldname), fieldname),
            )

    def on_trash(self) -> None:
        deny_history_delete()
