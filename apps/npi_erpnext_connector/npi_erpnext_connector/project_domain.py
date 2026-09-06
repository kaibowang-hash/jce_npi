from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import UUID, uuid5


UTC = timezone.utc
PROJECT_EVENT_NAMESPACE = UUID("2c5a0d7c-7bbd-41c2-9f71-63207ea9dd8a")
PROJECT_OBJECT_NAMESPACE = UUID("6b9fcf6f-cf56-4715-b4b4-21c4c9e06aed")
PROJECT_CORRELATION_NAMESPACE = UUID("d877aedf-b3ce-411e-b1bb-b3c66fbb59a4")
PROJECT_REQUEST_NAMESPACE = UUID("093d7d51-7276-4578-a79c-139756fdd44c")
_REFERENCE = re.compile(r"^[^\s\x00-\x1f\x7f]{1,255}$")
_ACTOR = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")


class ProjectSenderError(ValueError):
    """Raised when an ERPNext Project cannot be represented safely."""


@dataclass(frozen=True, slots=True)
class SourceProject:
    source_project_id: str
    title: str
    status: str
    target_sop: date
    source_modified_at: datetime
    source_owner_user_id: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.source_project_id, str)
            or _REFERENCE.fullmatch(self.source_project_id) is None
        ):
            raise ProjectSenderError("ERPNext Project identity is invalid.")
        if (
            not isinstance(self.title, str)
            or not self.title
            or self.title != self.title.strip()
            or len(self.title) > 140
        ):
            raise ProjectSenderError("ERPNext Project title is invalid.")
        if self.status != "Open":
            raise ProjectSenderError("Only an open ERPNext Project can seed NPI One.")
        if type(self.target_sop) is not date:
            raise ProjectSenderError("ERPNext Project target date is invalid.")
        _aware_utc(self.source_modified_at, "ERPNext Project modified time")
        if (
            not isinstance(self.source_owner_user_id, str)
            or _ACTOR.fullmatch(self.source_owner_user_id) is None
        ):
            raise ProjectSenderError("ERPNext Project owner identity is invalid.")

    def payload(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "project_state": "open",
            "title": self.title,
            "target_sop": self.target_sop.isoformat(),
            "source_modified_at": _utc_text(self.source_modified_at),
            "source_owner_user_id": self.source_owner_user_id,
        }

    @property
    def snapshot_hash(self) -> str:
        return canonical_hash(self.payload())


@dataclass(frozen=True, slots=True)
class ProjectSourceEvent:
    event: Mapping[str, object]
    request_id: UUID
    source_project_id: str
    source_version: int
    source_snapshot_hash: str

    @property
    def event_id(self) -> UUID:
        return UUID(str(self.event["event_id"]))

    @property
    def trace_id(self) -> str:
        return str(self.event["trace_id"])

    @property
    def event_hash(self) -> str:
        return canonical_hash(self.event)


def build_project_source_event(
    source: SourceProject,
    *,
    source_version: int,
    occurred_at: datetime,
    service_actor_id: str,
) -> ProjectSourceEvent:
    if not isinstance(source, SourceProject):
        raise ProjectSenderError("ERPNext Project source is invalid.")
    if type(source_version) is not int or not 1 <= source_version <= 2_147_483_647:
        raise ProjectSenderError("ERPNext Project source version is invalid.")
    occurred = _aware_utc(occurred_at, "ERPNext Project event time")
    if not isinstance(service_actor_id, str) or _ACTOR.fullmatch(service_actor_id) is None:
        raise ProjectSenderError("ERPNext Project service actor is invalid.")
    payload = source.payload()
    payload_hash = canonical_hash(payload)
    identity = f"{source.source_project_id}:{source_version}:{payload_hash}"
    event_id = uuid5(PROJECT_EVENT_NAMESPACE, identity)
    event = {
        "event_id": str(event_id),
        "event_type": "erpnext.project.created",
        "event_version": 1,
        "occurred_at": _utc_text(occurred),
        "source_system": "ERPNEXT",
        "target_system": "NPI_ONE",
        "global_id": str(uuid5(PROJECT_OBJECT_NAMESPACE, source.source_project_id)),
        "object_type": "Project",
        "source_object_id": source.source_project_id,
        "object_version": source_version,
        "correlation_id": str(
            uuid5(PROJECT_CORRELATION_NAMESPACE, source.source_project_id)
        ),
        "trace_id": f"erp-project-{event_id.hex}",
        "actor": {"type": "service", "id": service_actor_id},
        "payload_hash": payload_hash,
        "payload": payload,
        "sensitivity": "confidential",
    }
    return ProjectSourceEvent(
        event=event,
        request_id=uuid5(PROJECT_REQUEST_NAMESPACE, identity),
        source_project_id=source.source_project_id,
        source_version=source_version,
        source_snapshot_hash=source.snapshot_hash,
    )


def restore_project_source_event(
    raw_event: object,
    *,
    request_id: object,
    source_project_id: object,
    source_version: object,
    source_snapshot_hash: object,
    event_hash: object,
) -> ProjectSourceEvent:
    if not isinstance(raw_event, str):
        raise ProjectSenderError("Stored Project event is invalid.")
    try:
        event = json.loads(raw_event)
        parsed_request_id = UUID(str(request_id))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ProjectSenderError("Stored Project event is invalid.") from error
    candidate = ProjectSourceEvent(
        event=event,
        request_id=parsed_request_id,
        source_project_id=str(source_project_id),
        source_version=int(source_version),
        source_snapshot_hash=str(source_snapshot_hash),
    )
    expected_request_id = uuid5(
        PROJECT_REQUEST_NAMESPACE,
        f"{candidate.source_project_id}:{candidate.source_version}:{candidate.source_snapshot_hash}",
    )
    if (
        not isinstance(event, Mapping)
        or canonical_json(event) != raw_event
        or candidate.request_id != expected_request_id
        or candidate.event_hash != event_hash
        or event.get("event_id") != str(candidate.event_id)
        or event.get("source_object_id") != candidate.source_project_id
        or event.get("object_version") != candidate.source_version
        or event.get("payload_hash") != candidate.source_snapshot_hash
    ):
        raise ProjectSenderError("Stored Project event binding is invalid.")
    return candidate


def canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise ProjectSenderError("Project event JSON is invalid.") from error


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _aware_utc(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ProjectSenderError(f"{name} must be timezone aware.")
    return value.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return _aware_utc(value, "Time").replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
