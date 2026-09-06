from __future__ import annotations

from frappe.model.document import Document

from npi_core.documents.frappe_validation import assert_immutable_fields, canonical_uuid, lowercase_sha256, positive_integer, required_text, tenant_text
from npi_integration.engineering_change.frappe_validation import deny_history_delete, deny_history_update, require_inbox_write


_IMMUTABLE = ("receipt_id", "schema_version", "tenant_id", "project_global_id", "change_global_id", "event_id", "object_version", "source_key_hash", "canonical_event_hash", "raw_body_hash", "event_snapshot", "profile_id", "profile_version", "profile_snapshot_hash", "signing_key_id", "signed_at", "received_at", "request_id", "trace_id")
_TERMINAL = {"succeeded", "failed_final", "quarantined", "superseded"}


class NPIEngineeringChangeInbox(Document):
    def autoname(self) -> None:
        self.receipt_id = canonical_uuid(self.receipt_id, "Receipt ID")
        self.name = self.receipt_id

    def before_insert(self) -> None:
        require_inbox_write("insert")

    def before_save(self) -> None:
        previous = self.get_doc_before_save()
        require_inbox_write("insert" if previous is None else "save")
        if previous is not None and str(previous.state) in _TERMINAL and str(self.state) != str(previous.state):
            deny_history_update()

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _IMMUTABLE)
        for fieldname in ("receipt_id", "project_global_id", "change_global_id", "event_id", "request_id"):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), fieldname))
        if self.claim_token:
            self.claim_token = canonical_uuid(self.claim_token, "Claim Token")
        self.tenant_id = tenant_text(self.tenant_id)
        positive_integer(self.schema_version, "Schema Version")
        positive_integer(self.object_version, "Object Version")
        positive_integer(self.profile_version, "Integration Profile Version")
        for fieldname in ("source_key_hash", "canonical_event_hash", "raw_body_hash", "profile_snapshot_hash"):
            setattr(self, fieldname, lowercase_sha256(getattr(self, fieldname), fieldname))
        for fieldname in ("profile_id", "signing_key_id", "trace_id"):
            setattr(self, fieldname, required_text(getattr(self, fieldname), fieldname, 140))

    def on_trash(self) -> None:
        deny_history_delete()
