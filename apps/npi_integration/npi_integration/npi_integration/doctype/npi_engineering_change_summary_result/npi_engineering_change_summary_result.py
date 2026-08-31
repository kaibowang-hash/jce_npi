from __future__ import annotations

from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    assert_immutable_fields,
    canonical_uuid,
    lowercase_sha256,
)
from npi_integration.engineering_change.frappe_validation import (
    deny_history_delete,
    deny_history_update,
    require_result_write,
)


_IMMUTABLE = (
    "global_id",
    "request_global_id",
    "outbox_event_id",
    "attempt_global_id",
    "state",
    "fault_kind",
    "retry_directive",
    "response_hash",
    "response_authenticated",
    "response_contract_valid",
    "retry_after_seconds",
    "observed_at",
    "result_snapshot",
    "result_hash",
)


class NPIEngineeringChangeSummaryResult(Document):
    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, "Global ID")
        self.name = self.global_id

    def before_insert(self) -> None:
        require_result_write("insert")

    def before_save(self) -> None:
        previous = self.get_doc_before_save()
        require_result_write("insert" if previous is None else "save")
        if previous is not None:
            deny_history_update()

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _IMMUTABLE)
        for fieldname in (
            "global_id",
            "request_global_id",
            "outbox_event_id",
            "attempt_global_id",
        ):
            setattr(
                self,
                fieldname,
                canonical_uuid(getattr(self, fieldname), fieldname),
            )
        for fieldname in ("response_hash", "result_hash"):
            setattr(
                self,
                fieldname,
                lowercase_sha256(getattr(self, fieldname), fieldname),
            )

    def on_trash(self) -> None:
        deny_history_delete()
