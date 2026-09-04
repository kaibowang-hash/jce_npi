from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class GlobalIdentity:
    global_id: UUID
    source_system: str
    source_object_type: str
    source_object_id: str

    @classmethod
    def create(cls, source_object_type: str, source_object_id: str) -> "GlobalIdentity":
        if not source_object_type.strip() or not source_object_id.strip():
            raise ValueError("Source object type and ID are required.")
        return cls(uuid4(), "NPI_ONE", source_object_type, source_object_id)


def assert_global_id_immutable(original: UUID, candidate: UUID) -> None:
    if original != candidate:
        raise ValueError("Global ID is immutable.")
