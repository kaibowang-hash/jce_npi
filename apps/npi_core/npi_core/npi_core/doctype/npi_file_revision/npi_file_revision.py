from __future__ import annotations

import hashlib
import mimetypes
import re
from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.controlled_evidence_validation import (
    canonical_uuid,
    deny_controlled_evidence_delete,
    has_controlled_file_write,
    lowercase_sha256,
    positive_integer,
    require_file_revision_command_write,
    require_file_scan_result_write,
)
from npi_core.project.frappe_validation import assert_immutable_fields


_SCAN_STATES = frozenset({"pending", "clean", "infected", "failed"})
_FRAPPE_CONTENT_HASH_PATTERN = re.compile(r"^[a-f0-9]{32}$")
_COMPLETE_IDENTITY_FIELDS = (
    "global_id",
    "tenant_id",
    "project_global_id",
    "document_global_id",
    "revision",
    "revision_key",
    "frappe_file_id",
    "frappe_content_hash",
    "file",
    "file_name",
    "mime_type",
    "size_bytes",
    "sha256",
    "is_private",
    "scan_state",
    "released",
    "optimistic_version",
)
_IMMUTABLE_CONTENT_FIELDS = (
    "global_id",
    "tenant_id",
    "project_global_id",
    "document_global_id",
    "revision",
    "revision_key",
    "frappe_file_id",
    "frappe_content_hash",
    "file",
    "file_name",
    "mime_type",
    "size_bytes",
    "sha256",
    "is_private",
)


class NPIFileRevision(Document):
    """Project-scoped administrative projection of an immutable private file."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_file_revision_command_write()

    def before_save(self) -> None:
        previous = self.get_doc_before_save()
        if previous is None or not has_complete_file_revision_identity(previous):
            require_file_revision_command_write()
            return
        if not has_controlled_file_write():
            require_file_revision_command_write()

    def on_trash(self) -> None:
        deny_controlled_evidence_delete()

    def before_validate(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        if self.project_global_id:
            self.project_global_id = canonical_uuid(
                self.project_global_id,
                _("Project Global ID"),
            )
        if self.document_global_id:
            self.document_global_id = canonical_uuid(
                self.document_global_id,
                _("Document Global ID"),
            )
        if self.document_global_id and self.revision:
            self.revision_key = f"{self.document_global_id}:{self.revision}"
        if self.is_new():
            self.scan_state = "pending"
            self.scan_observed_at = None
            self.released = 0
            self.optimistic_version = 1

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        self.optimistic_version = (
            1 if previous is None else int(previous.get("optimistic_version") or 0) + 1
        )
        if previous is None or not has_complete_file_revision_identity(previous):
            self._hydrate_complete_identity()
        else:
            assert_immutable_fields(self, previous, _IMMUTABLE_CONTENT_FIELDS)

        self._validate_complete_identity()
        self._validate_scan_and_release(previous)

    def _hydrate_complete_identity(self) -> None:
        if not self.tenant_id:
            frappe.throw(_("Tenant ID is required."), frappe.ValidationError)
        if not self.project_global_id or not self.document_global_id:
            frappe.throw(_("Enter a valid value."), frappe.ValidationError)
        self.revision = positive_integer(self.revision, _("Revision"))
        if not self.frappe_file_id:
            frappe.throw(_("Select a private file."), frappe.ValidationError)

        file_document = frappe.get_doc("File", str(self.frappe_file_id))
        if (
            int(file_document.is_private or 0) != 1
            or not isinstance(file_document.file_url, str)
            or not file_document.file_url.startswith("/private/files/")
        ):
            frappe.throw(_("Select a private file."), frappe.ValidationError)
        content = _content_bytes(file_document.get_content())
        file_name = str(file_document.file_name or "").strip()
        frappe_content_hash = str(file_document.content_hash or "").strip().lower()
        file_size = file_document.file_size
        if (
            not file_name
            or _FRAPPE_CONTENT_HASH_PATTERN.fullmatch(frappe_content_hash) is None
            or frappe_content_hash
            != hashlib.md5(content, usedforsecurity=False).hexdigest()
            or file_size is None
            or int(file_size) != len(content)
        ):
            frappe.throw(_("Enter a valid value."), frappe.ValidationError)

        self.frappe_file_id = str(file_document.name)
        self.frappe_content_hash = frappe_content_hash
        self.file = str(file_document.file_url)
        self.file_name = file_name
        self.mime_type = (
            mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        )
        self.size_bytes = len(content)
        self.sha256 = hashlib.sha256(content).hexdigest()
        self.is_private = 1
        self.revision_key = f"{self.document_global_id}:{self.revision}"

    def _validate_complete_identity(self) -> None:
        if not has_complete_file_revision_identity(self):
            frappe.throw(
                _("The file revision does not have a complete controlled identity."),
                frappe.ValidationError,
            )
        self.revision = positive_integer(self.revision, _("Revision"))
        self.optimistic_version = positive_integer(
            self.optimistic_version,
            _("Optimistic Version"),
        )
        self.sha256 = lowercase_sha256(self.sha256, _("SHA-256"))
        if int(self.size_bytes) < 0:
            frappe.throw(_("Enter a valid value."), frappe.ValidationError)
        if int(self.is_private or 0) != 1 or not str(self.file).startswith(
            "/private/files/"
        ):
            frappe.throw(_("Select a private file."), frappe.ValidationError)

        project_identity = frappe.db.get_value(
            "NPI Engineering Project",
            self.project_global_id,
            ["global_id", "tenant_id"],
            as_dict=True,
        )
        if not project_identity or (
            str(_record_value(project_identity, "global_id")) != self.project_global_id
            or str(_record_value(project_identity, "tenant_id")) != self.tenant_id
        ):
            frappe.throw(
                _("The file revision does not match its Project and tenant."),
                frappe.ValidationError,
            )

    def _validate_scan_and_release(self, previous: Any) -> None:
        if self.scan_state not in _SCAN_STATES:
            frappe.throw(_("Select a supported scan state."), frappe.ValidationError)
        if self.scan_state == "pending" and self.scan_observed_at:
            frappe.throw(
                _("A pending file cannot have a completed scan observation."),
                frappe.ValidationError,
            )
        if self.scan_state != "pending" and not self.scan_observed_at:
            frappe.throw(
                _("A completed scan state requires an observation time."),
                frappe.ValidationError,
            )
        if previous is None:
            return

        scan_changed = self.scan_state != previous.get(
            "scan_state"
        ) or self.scan_observed_at != previous.get("scan_observed_at")
        if scan_changed:
            require_file_scan_result_write()
        if int(previous.get("released") or 0) == 1 and int(self.released or 0) != 1:
            frappe.throw(
                _("A released file revision cannot be reopened."),
                frappe.ValidationError,
            )
        if int(self.released or 0) != int(previous.get("released") or 0):
            require_file_revision_command_write()
            if int(self.released or 0) == 1 and self.scan_state != "clean":
                frappe.throw(
                    _("Only a clean file revision can be released."),
                    frappe.ValidationError,
                )


def has_complete_file_revision_identity(document: Any) -> bool:
    if any(
        document.get(fieldname) in {None, ""} for fieldname in _COMPLETE_IDENTITY_FIELDS
    ):
        return False
    revision = document.get("revision")
    if type(revision) is not int or revision < 1:
        return False
    optimistic_version = document.get("optimistic_version")
    if type(optimistic_version) is not int or optimistic_version < 1:
        return False
    size_bytes = document.get("size_bytes")
    if type(size_bytes) is not int or size_bytes < 0:
        return False
    if int(document.get("is_private") or 0) != 1:
        return False
    if not str(document.get("file") or "").startswith("/private/files/"):
        return False
    if document.get("revision_key") != (
        f"{document.get('document_global_id')}:{revision}"
    ):
        return False
    scan_state = document.get("scan_state")
    scan_observed_at = document.get("scan_observed_at")
    if scan_state not in _SCAN_STATES:
        return False
    if (scan_state == "pending" and scan_observed_at) or (
        scan_state != "pending" and not scan_observed_at
    ):
        return False
    try:
        canonical_uuid(document.get("global_id"), _("Global ID"))
        canonical_uuid(document.get("project_global_id"), _("Project Global ID"))
        canonical_uuid(document.get("document_global_id"), _("Document Global ID"))
        lowercase_sha256(document.get("sha256"), _("SHA-256"))
    except (frappe.ValidationError, frappe.PermissionError):
        return False
    return True


def has_live_private_file_identity(document: Any) -> bool:
    """Fail closed when the exact Frappe File identity or privacy has drifted."""
    if not has_complete_file_revision_identity(document):
        return False
    try:
        file_document = frappe.get_doc(
            "File",
            str(document.get("frappe_file_id")),
        )
    except (frappe.DoesNotExistError, frappe.PermissionError):
        return False
    live_size = _record_value(file_document, "file_size")
    return (
        str(_record_value(file_document, "name")) == str(document.get("frappe_file_id"))
        and int(_record_value(file_document, "is_private") or 0) == 1
        and int(_record_value(file_document, "is_remote_file") or 0) == 0
        and str(_record_value(file_document, "file_url")) == str(document.get("file"))
        and str(_record_value(file_document, "file_url")).startswith("/private/files/")
        and str(_record_value(file_document, "file_name"))
        == str(document.get("file_name"))
        and live_size is not None
        and int(live_size) == int(document.get("size_bytes"))
        and str(_record_value(file_document, "content_hash") or "").lower()
        == str(document.get("frappe_content_hash"))
    )


def file_revision_source_snapshot(document: Any) -> dict[str, object]:
    """Return URL-free exact metadata for a complete File Revision."""
    if not has_complete_file_revision_identity(document):
        frappe.throw(
            _("The file revision is unavailable as controlled evidence."),
            frappe.ValidationError,
        )
    observed_at = document.get("scan_observed_at")
    return {
        "documentGlobalId": str(document.get("document_global_id")),
        "fileContentHash": str(document.get("frappe_content_hash")),
        "fileId": str(document.get("frappe_file_id")),
        "fileName": str(document.get("file_name")),
        "fileOptimisticVersion": int(document.get("optimistic_version")),
        "globalId": str(document.get("global_id")),
        "isPrivate": True,
        "mimeType": str(document.get("mime_type")),
        "released": bool(document.get("released")),
        "revision": int(document.get("revision")),
        "scanObservedAt": str(observed_at) if observed_at else None,
        "scanState": str(document.get("scan_state")),
        "sha256": str(document.get("sha256")),
        "sizeBytes": int(document.get("size_bytes")),
    }


def _content_bytes(content: object) -> bytes:
    if isinstance(content, bytes):
        return content
    if isinstance(content, str):
        return content.encode("utf-8")
    frappe.throw(_("Enter a valid value."), frappe.ValidationError)
    raise AssertionError("Frappe validation must raise an exception.")


def _record_value(record: object, fieldname: str) -> object:
    if isinstance(record, dict):
        return record.get(fieldname)
    return getattr(record, fieldname, None)
