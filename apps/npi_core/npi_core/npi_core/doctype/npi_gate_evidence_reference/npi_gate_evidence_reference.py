from __future__ import annotations

from typing import Any
from uuid import UUID

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from npi_core.controlled_evidence_validation import (
    canonical_json_object,
    canonical_snapshot_hash,
    canonical_uuid,
    controlled_key,
    deny_controlled_evidence_delete,
    evidence_reference_key,
    lowercase_sha256,
    positive_integer,
    require_gate_evidence_command_write,
)
from npi_core.gate_evidence.domain import wbs_source_snapshot
from npi_core.documents.baseline_domain import DocumentBaselineInputUnavailable
from npi_core.documents.baseline_repository import load_document_baseline
from npi_core.npi_core.doctype.npi_file_revision.npi_file_revision import (
    file_revision_source_snapshot,
    has_complete_file_revision_identity,
    has_live_private_file_identity,
)


_SUPPORTED_SOURCE_TYPES = {
    "wbs_item": "wbs_item",
    "file_revision": "file_revision",
    "release_baseline": "release_baseline",
}


class NPIGateEvidenceReference(Document):
    """Append-only exact evidence identity; no file URL is persisted here."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_gate_evidence_command_write()

    def before_save(self) -> None:
        require_gate_evidence_command_write()
        if self.get_doc_before_save() is not None:
            frappe.throw(
                _("Gate evidence references cannot be changed."),
                frappe.PermissionError,
            )

    def on_trash(self) -> None:
        deny_controlled_evidence_delete()

    def before_validate(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.project_global_id = canonical_uuid(
            self.project_global_id,
            _("Project Global ID"),
        )
        self.gate_global_id = canonical_uuid(
            self.gate_global_id,
            _("Gate Global ID"),
        )
        self.requirement_global_id = canonical_uuid(
            self.requirement_global_id,
            _("Requirement Global ID"),
        )
        self.source_global_id = canonical_uuid(
            self.source_global_id,
            _("Source Global ID"),
        )
        self.requirement_key = controlled_key(
            self.requirement_key,
            _("Requirement Key"),
        )
        self.source_version = positive_integer(
            self.source_version,
            _("Source Version"),
        )
        self.source_hash = lowercase_sha256(
            self.source_hash,
            _("Source Hash"),
        )
        _snapshot, canonical_snapshot = canonical_json_object(
            self.source_snapshot,
            _("Source Snapshot"),
        )
        self.source_snapshot = canonical_snapshot
        if self.is_new():
            self.created_by = str(frappe.session.user)
            self.created_at = now_datetime()
            self.optimistic_version = 1
        self.reference_key = evidence_reference_key(
            tenant_id=str(self.tenant_id),
            project_global_id=self.project_global_id,
            gate_global_id=self.gate_global_id,
            requirement_global_id=self.requirement_global_id,
            requirement_key=self.requirement_key,
            evidence_kind=str(self.evidence_kind),
            source_object_type=str(self.source_object_type),
            source_global_id=self.source_global_id,
            source_version=self.source_version,
            source_hash=self.source_hash,
        )

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            frappe.throw(
                _("Gate evidence references cannot be changed."),
                frappe.PermissionError,
            )
        if (
            self.evidence_kind not in _SUPPORTED_SOURCE_TYPES
            or _SUPPORTED_SOURCE_TYPES[self.evidence_kind] != self.source_object_type
        ):
            frappe.throw(
                _("Select a supported evidence source."),
                frappe.ValidationError,
            )
        self.optimistic_version = positive_integer(
            self.optimistic_version,
            _("Optimistic Version"),
        )
        self.source_hash = lowercase_sha256(
            self.source_hash,
            _("Source Hash"),
        )
        snapshot, canonical_snapshot = canonical_json_object(
            self.source_snapshot,
            _("Source Snapshot"),
        )
        self.source_snapshot = canonical_snapshot
        self._validate_project_and_gate()
        self._validate_exact_source(snapshot)

    def _validate_project_and_gate(self) -> None:
        project = frappe.db.get_value(
            "NPI Engineering Project",
            self.project_global_id,
            ["global_id", "tenant_id"],
            as_dict=True,
        )
        gate = frappe.db.get_value(
            "NPI Gate Shell",
            self.gate_global_id,
            ["global_id", "project_global_id"],
            as_dict=True,
        )
        if (
            not project
            or not gate
            or (
                str(_record_value(project, "global_id")) != self.project_global_id
                or str(_record_value(project, "tenant_id")) != self.tenant_id
                or str(_record_value(gate, "global_id")) != self.gate_global_id
                or str(_record_value(gate, "project_global_id"))
                != self.project_global_id
            )
        ):
            frappe.throw(
                _("The evidence reference does not match its Project and Gate."),
                frappe.ValidationError,
            )

    def _validate_exact_source(self, supplied_snapshot: dict[str, Any]) -> None:
        if self.source_object_type == "wbs_item":
            source = frappe.get_doc("NPI WBS Item", self.source_global_id)
            expected_snapshot = wbs_item_source_snapshot(source)
            expected_version = int(source.optimistic_version)
            expected_hash = canonical_snapshot_hash(expected_snapshot)
        elif self.source_object_type == "file_revision":
            source = frappe.get_doc("NPI File Revision", self.source_global_id)
            if not has_complete_file_revision_identity(
                source
            ) or not has_live_private_file_identity(source):
                frappe.throw(
                    _("The file revision is unavailable as controlled evidence."),
                    frappe.ValidationError,
                )
            expected_snapshot = file_revision_source_snapshot(source)
            expected_version = int(source.revision)
            expected_hash = str(source.sha256)
        else:
            project = frappe.get_doc(
                "NPI Engineering Project",
                self.project_global_id,
            )
            try:
                baseline = load_document_baseline(
                    project,
                    UUID(self.source_global_id),
                    lock=False,
                )
            except DocumentBaselineInputUnavailable:
                baseline = None
            if baseline is None:
                frappe.throw(
                    _("The exact evidence source is unavailable."),
                    frappe.ValidationError,
                )
            source = baseline
            expected_snapshot = baseline.snapshot_payload()
            expected_version = baseline.version
            expected_hash = baseline.snapshot_hash

        if (
            str(source.project_global_id) != self.project_global_id
            or str(source.tenant_id) != self.tenant_id
            or expected_version != self.source_version
            or expected_hash != self.source_hash
            or expected_snapshot != supplied_snapshot
        ):
            frappe.throw(
                _("The evidence source version or hash does not match."),
                frappe.ValidationError,
            )


def wbs_item_source_snapshot(document: Any) -> dict[str, object]:
    """Return the exact mutable WBS values frozen by an evidence reference."""
    snapshot, _snapshot_hash = wbs_source_snapshot(document)
    return snapshot


def _record_value(record: object, fieldname: str) -> object:
    if isinstance(record, dict):
        return record.get(fieldname)
    return getattr(record, fieldname, None)
