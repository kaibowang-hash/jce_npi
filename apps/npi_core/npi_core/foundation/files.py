from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from enum import StrEnum
from uuid import UUID, uuid4


class ScanState(StrEnum):
    PENDING = "pending"
    CLEAN = "clean"
    INFECTED = "infected"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class FileRevision:
    revision_id: UUID
    document_global_id: UUID
    revision: int
    file_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    is_private: bool
    scan_state: ScanState = ScanState.PENDING
    released: bool = False

    @classmethod
    def from_content(cls, document_global_id: UUID, revision: int, file_name: str,
                     mime_type: str, content: bytes) -> "FileRevision":
        if revision < 1 or not file_name.strip() or not mime_type.strip():
            raise ValueError("Valid revision, file name and MIME type are required.")
        return cls(uuid4(), document_global_id, revision, file_name, mime_type, len(content),
                   hashlib.sha256(content).hexdigest(), True)

    def mark_scanned(self, state: ScanState) -> "FileRevision":
        if self.released:
            raise ValueError("Released file revisions are immutable.")
        return replace(self, scan_state=state)

    def release(self) -> "FileRevision":
        if self.scan_state is not ScanState.CLEAN:
            raise ValueError("Only a clean file revision can be released.")
        return replace(self, released=True)

    def verify(self, content: bytes) -> bool:
        return hashlib.sha256(content).hexdigest() == self.sha256
