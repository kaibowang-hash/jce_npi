from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from npi_core.change_control.domain import (
    EngineeringChangeEvent,
    EngineeringChangeEventType,
    EngineeringChangeRevision,
    EngineeringChangeState,
)
from npi_core.change_control.request_validation import (
    closed_payload,
    parse_formal_observation,
    parse_revision_content,
)


_REVISION_FIELDS = frozenset(
    {
        "schemaVersion", "globalId", "changeGlobalId", "tenantId",
        "projectGlobalId", "revision", "predecessorGlobalId",
        "predecessorSnapshotHash", "state", "title", "reason",
        "formalChange", "impactAssessments", "affectedObjects",
        "implementationTasks", "effectivityRules", "dispositions",
        "revalidationRequirements", "costSummary", "closureEvidence",
        "readyToClose", "createdByUserId", "createdAt", "requestId",
        "traceId", "snapshotHash",
    }
)
_EVENT_FIELDS = frozenset(
    {
        "schemaVersion", "globalId", "changeGlobalId", "tenantId",
        "projectGlobalId", "revisionGlobalId", "revision",
        "revisionSnapshotHash", "eventType", "actorUserId", "occurredAt",
        "requestId", "traceId", "eventHash",
    }
)
_CHANGE_FIELDS = frozenset(
    {
        "globalId", "projectGlobalId", "title", "state", "optimisticVersion",
        "currentRevisionGlobalId", "currentRevisionNumber",
        "currentRevisionSnapshotHash", "formalChange", "readyToClose",
    }
)
_PERMISSION_FIELDS = frozenset({"canView", "canCreate", "canRevise", "canLinkFormalObservation", "canClose"})
_LIST_FIELDS = frozenset({"projectGlobalId", "items", "permissions"})
_DETAIL_FIELDS = frozenset({"projectGlobalId", "change", "currentRevision", "revisions", "events", "permissions"})
_COMMAND_FIELDS = frozenset({"operation", "change", "currentRevision"})
_OPERATIONS = frozenset({"engineering_change.create", "engineering_change.revise", "engineering_change.link_formal_observation", "engineering_change.close"})


class ChangeControlResponseInvalid(RuntimeError):
    def __init__(self) -> None:
        super().__init__("The engineering change response is invalid.")


def validate_change_list_response(value: object, *, project_global_id: str) -> dict[str, Any]:
    return _validated(lambda: _list(value, project_global_id))


def validate_change_detail_response(
    value: object,
    *,
    project_global_id: str,
    change_global_id: str,
) -> dict[str, Any]:
    return _validated(lambda: _detail(value, project_global_id, change_global_id))


def validate_change_command_response(
    operation: str,
    value: object,
    *,
    project_global_id: str,
    change_global_id: str | None = None,
) -> dict[str, Any]:
    def validate() -> dict[str, Any]:
        if operation not in _OPERATIONS:
            raise ChangeControlResponseInvalid()
        record = closed_payload(value, "", _COMMAND_FIELDS)
        if record["operation"] != operation:
            raise ChangeControlResponseInvalid()
        revision = _revision(record["currentRevision"])
        expected_change = str(revision.change_global_id)
        if change_global_id is not None and expected_change != _canonical_uuid(change_global_id):
            raise ChangeControlResponseInvalid()
        change = _change(record["change"], revision)
        if str(revision.project_global_id) != _canonical_uuid(project_global_id) or change["globalId"] != expected_change:
            raise ChangeControlResponseInvalid()
        return dict(record)

    return _validated(validate)


def validate_receipt_response(
    operation: str,
    value: object,
    *,
    project_global_id: str,
    change_global_id: str | None,
) -> dict[str, Any]:
    return validate_change_command_response(
        operation,
        value,
        project_global_id=project_global_id,
        change_global_id=change_global_id,
    )


def _list(value: object, project_global_id: str) -> dict[str, Any]:
    record = closed_payload(value, "", _LIST_FIELDS)
    project = _canonical_uuid(project_global_id)
    if record["projectGlobalId"] != project or not isinstance(record["items"], list) or len(record["items"]) > 1_000:
        raise ChangeControlResponseInvalid()
    for item in record["items"]:
        revision = _revision(closed_payload(item, "item", frozenset({"change", "currentRevision"}))["currentRevision"])
        change = _change(item["change"], revision)
        if change["projectGlobalId"] != project:
            raise ChangeControlResponseInvalid()
    _permissions(record["permissions"])
    return dict(record)


def _detail(value: object, project_global_id: str, change_global_id: str) -> dict[str, Any]:
    record = closed_payload(value, "", _DETAIL_FIELDS)
    project = _canonical_uuid(project_global_id)
    change_id = _canonical_uuid(change_global_id)
    if record["projectGlobalId"] != project:
        raise ChangeControlResponseInvalid()
    current = _revision(record["currentRevision"])
    change = _change(record["change"], current)
    if change["globalId"] != change_id or change["projectGlobalId"] != project:
        raise ChangeControlResponseInvalid()
    revisions = record["revisions"]
    events = record["events"]
    if not isinstance(revisions, list) or not revisions or len(revisions) > 1_000 or not isinstance(events, list) or not events or len(events) > 1_000:
        raise ChangeControlResponseInvalid()
    parsed_revisions = tuple(_revision(item) for item in revisions)
    parsed_events = tuple(_event(item) for item in events)
    if tuple(item.revision for item in parsed_revisions) != tuple(range(1, current.revision + 1)) or parsed_revisions[-1].snapshot_hash != current.snapshot_hash:
        raise ChangeControlResponseInvalid()
    if any(item.change_global_id != current.change_global_id for item in parsed_revisions + parsed_events):
        raise ChangeControlResponseInvalid()
    _permissions(record["permissions"])
    return dict(record)


def _revision(value: object) -> EngineeringChangeRevision:
    record = closed_payload(value, "revision", _REVISION_FIELDS)
    if record["schemaVersion"] != 1 or type(record["readyToClose"]) is not bool:
        raise ChangeControlResponseInvalid()
    content = parse_revision_content(
        {
            "title": record["title"],
            "reason": record["reason"],
            "impactAssessments": record["impactAssessments"],
            "affectedObjects": record["affectedObjects"],
            "implementationTasks": record["implementationTasks"],
            "effectivityRules": record["effectivityRules"],
            "dispositions": record["dispositions"],
            "revalidationRequirements": record["revalidationRequirements"],
            "costSummary": record["costSummary"],
            "closureEvidence": record["closureEvidence"],
        },
        require_closure=False,
    )
    result = EngineeringChangeRevision(
        global_id=_uuid(record["globalId"]),
        change_global_id=_uuid(record["changeGlobalId"]),
        tenant_id=_text(record["tenantId"]),
        project_global_id=_uuid(record["projectGlobalId"]),
        revision=_positive(record["revision"]),
        predecessor_global_id=_optional_uuid(record["predecessorGlobalId"]),
        predecessor_snapshot_hash=_optional_hash(record["predecessorSnapshotHash"]),
        state=_state(record["state"]),
        formal_change=None if record["formalChange"] is None else parse_formal_observation(record["formalChange"]),
        created_by_user_id=_text(record["createdByUserId"]),
        created_at=_datetime(record["createdAt"]),
        request_id=_uuid(record["requestId"]),
        trace_id=_text(record["traceId"]),
        **content,
    )
    if result.revision_payload() != {key: record[key] for key in _REVISION_FIELDS if key != "snapshotHash"} or result.snapshot_hash != record["snapshotHash"] or result.ready_to_close is not record["readyToClose"]:
        raise ChangeControlResponseInvalid()
    return result


def _event(value: object) -> EngineeringChangeEvent:
    record = closed_payload(value, "event", _EVENT_FIELDS)
    if record["schemaVersion"] != 1:
        raise ChangeControlResponseInvalid()
    result = EngineeringChangeEvent(
        global_id=_uuid(record["globalId"]),
        change_global_id=_uuid(record["changeGlobalId"]),
        tenant_id=_text(record["tenantId"]),
        project_global_id=_uuid(record["projectGlobalId"]),
        revision_global_id=_uuid(record["revisionGlobalId"]),
        revision=_positive(record["revision"]),
        revision_snapshot_hash=_hash(record["revisionSnapshotHash"]),
        event_type=EngineeringChangeEventType(record["eventType"]),
        actor_user_id=_text(record["actorUserId"]),
        occurred_at=_datetime(record["occurredAt"]),
        request_id=_uuid(record["requestId"]),
        trace_id=_text(record["traceId"]),
    )
    if result.event_payload() != {key: record[key] for key in _EVENT_FIELDS if key != "eventHash"} or result.event_hash != record["eventHash"]:
        raise ChangeControlResponseInvalid()
    return result


def _change(value: object, current: EngineeringChangeRevision) -> dict[str, Any]:
    record = closed_payload(value, "change", _CHANGE_FIELDS)
    expected = {
        "globalId": str(current.change_global_id),
        "projectGlobalId": str(current.project_global_id),
        "title": current.title,
        "state": current.state.value,
        "optimisticVersion": current.revision,
        "currentRevisionGlobalId": str(current.global_id),
        "currentRevisionNumber": current.revision,
        "currentRevisionSnapshotHash": current.snapshot_hash,
        "formalChange": None if current.formal_change is None else current.formal_change.payload(),
        "readyToClose": current.ready_to_close,
    }
    if record != expected:
        raise ChangeControlResponseInvalid()
    return dict(record)


def _permissions(value: object) -> None:
    record = closed_payload(value, "permissions", _PERMISSION_FIELDS)
    if any(type(item) is not bool for item in record.values()):
        raise ChangeControlResponseInvalid()


def _validated(callback):
    try:
        return callback()
    except ChangeControlResponseInvalid:
        raise
    except Exception as error:
        raise ChangeControlResponseInvalid() from error


def _canonical_uuid(value: object) -> str:
    result = _uuid(value)
    return str(result)


def _uuid(value: object) -> UUID:
    if not isinstance(value, str):
        raise ChangeControlResponseInvalid()
    result = UUID(value)
    if str(result) != value.casefold() or result.int == 0:
        raise ChangeControlResponseInvalid()
    return result


def _optional_uuid(value: object) -> UUID | None:
    return None if value is None else _uuid(value)


def _text(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ChangeControlResponseInvalid()
    return value


def _positive(value: object) -> int:
    if type(value) is not int or value < 1:
        raise ChangeControlResponseInvalid()
    return value


def _hash(value: object) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ChangeControlResponseInvalid()
    return value


def _optional_hash(value: object) -> str | None:
    return None if value is None else _hash(value)


def _datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise ChangeControlResponseInvalid()
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ChangeControlResponseInvalid()
    return result.astimezone(UTC)


def _state(value: object) -> EngineeringChangeState:
    if not isinstance(value, str):
        raise ChangeControlResponseInvalid()
    return EngineeringChangeState(value)
