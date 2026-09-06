from __future__ import annotations

from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    assert_immutable_fields,
    canonical_uuid,
    lowercase_sha256,
    positive_integer,
)
from npi_integration.engineering_change.frappe_validation import (
    deny_history_delete,
    deny_history_update,
    require_attempt_write,
)


_IMMUTABLE = (
    "global_id",
    "request_global_id",
    "outbox_event_id",
    "attempt_number",
    "target_idempotency_key_hash",
    "source_hash",
    "started_at",
)


class NPIEngineeringChangeSummaryAttempt(Document):
    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, "Global ID")
        self.name = self.global_id

    def before_insert(self) -> None:
        require_attempt_write("insert")

    def before_save(self) -> None:
        previous = self.get_doc_before_save()
        require_attempt_write("insert" if previous is None else "save")
        if previous is not None and str(previous.state) != "started":
            deny_history_update()

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _IMMUTABLE)
        for fieldname in ("global_id", "request_global_id", "outbox_event_id"):
            setattr(
                self,
                fieldname,
                canonical_uuid(getattr(self, fieldname), fieldname),
            )
        positive_integer(self.attempt_number, "Attempt Number")
        for fieldname in ("target_idempotency_key_hash", "source_hash"):
            setattr(
                self,
                fieldname,
                lowercase_sha256(getattr(self, fieldname), fieldname),
            )
        if self.response_hash:
            self.response_hash = lowercase_sha256(
                self.response_hash, "Response Hash"
            )

    def on_trash(self) -> None:
        deny_history_delete()
