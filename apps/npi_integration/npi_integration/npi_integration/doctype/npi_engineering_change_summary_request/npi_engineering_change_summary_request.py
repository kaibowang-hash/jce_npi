from __future__ import annotations

from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    assert_immutable_fields,
    canonical_uuid,
    lowercase_sha256,
    positive_integer,
    tenant_text,
)
from npi_integration.engineering_change.frappe_validation import (
    deny_history_delete,
    deny_history_update,
    require_request_write,
)


_IMMUTABLE = (
    "global_id",
    "tenant_id",
    "project_global_id",
    "change_global_id",
    "revision_global_id",
    "revision_number",
    "revision_snapshot_hash",
    "source_snapshot",
    "source_hash",
    "profile_id",
    "profile_version",
    "profile_snapshot_hash",
    "actor_user_id",
    "service_actor_user_id",
    "request_id",
    "trace_id",
    "idempotency_key_hash",
    "outbox_event_id",
    "created_at",
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


class NPIEngineeringChangeSummaryRequest(Document):
    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, "Global ID")
        self.name = self.global_id

    def before_insert(self) -> None:
        require_request_write("insert")

    def before_save(self) -> None:
        previous = self.get_doc_before_save()
        require_request_write("insert" if previous is None else "save")
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
            "global_id",
            "project_global_id",
            "change_global_id",
            "revision_global_id",
            "request_id",
            "outbox_event_id",
        ):
            setattr(
                self,
                fieldname,
                canonical_uuid(getattr(self, fieldname), fieldname),
            )
        if self.result_global_id:
            self.result_global_id = canonical_uuid(
                self.result_global_id, "Result ID"
            )
        self.tenant_id = tenant_text(self.tenant_id)
        positive_integer(self.revision_number, "Revision Number")
        positive_integer(self.profile_version, "Profile Version")
        for fieldname in (
            "revision_snapshot_hash",
            "source_hash",
            "profile_snapshot_hash",
            "idempotency_key_hash",
        ):
            setattr(
                self,
                fieldname,
                lowercase_sha256(getattr(self, fieldname), fieldname),
            )

    def on_trash(self) -> None:
        deny_history_delete()
