from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any
from uuid import UUID

from npi_core.project_work.policy_labels import POLICY_LABEL_SOURCES
from npi_core.readiness.domain import (
    ReadinessInstanceRevision,
    ReadinessPublicationState,
    ReadinessTemplateVersion,
    instance_from_snapshot,
    template_from_snapshot,
    validate_readiness_successor,
)
from npi_core.readiness.source_resolver import (
    EXTERNAL_SOURCE_KINDS,
    EXTERNAL_UNAVAILABLE_REASON_CODES,
)


_HASH = re.compile(r"^[0-9a-f]{64}$")
_TEMPLATE_VERSION_FIELDS = frozenset(
    {
        "globalId",
        "templateGlobalId",
        "templateCode",
        "templateVersion",
        "optimisticVersion",
        "title",
        "publicationState",
        "applicability",
        "categories",
        "items",
        "changedByUserId",
        "changedAt",
        "requestId",
        "traceId",
        "snapshotHash",
    }
)
_INSTANCE_REVISION_FIELDS = frozenset(
    {
        "globalId",
        "instanceGlobalId",
        "tenantId",
        "project",
        "templateRevision",
        "instanceVersion",
        "predecessorGlobalId",
        "predecessorSnapshotHash",
        "categories",
        "items",
        "evaluation",
        "createdByUserId",
        "createdAt",
        "requestId",
        "traceId",
        "versionKeyHash",
        "snapshotHash",
    }
)
_WORKSPACE_FIELDS = frozenset(
    {
        "projectGlobalId",
        "currentRevision",
        "revisions",
        "sourceOptions",
        "unavailableProjections",
        "permissions",
    }
)
_SOURCE_OPTION_FIELDS = frozenset(
    {
        "kind",
        "globalId",
        "sourceVersion",
        "snapshotHash",
        "label",
        "stateLabelSource",
        "stateTerminal",
    }
)
_PERMISSION_FIELDS = frozenset(
    {"canManageTemplates", "canInitialize", "canRevise"}
)
_TEMPLATE_OPERATIONS = frozenset(
    {
        "readiness_template.create",
        "readiness_template.edit",
        "readiness_template.publish",
    }
)
_INSTANCE_OPERATIONS = frozenset(
    {"readiness_instance.initialize", "readiness_instance.revise"}
)


class ReadinessResponseInvalid(RuntimeError):
    """Fail closed without retaining or exposing an invalid response value."""

    def __init__(self) -> None:
        super().__init__("The NPI Readiness response is invalid.")


def validate_template_version_response(value: object) -> dict[str, Any]:
    """Return one exact canonical template response or fail closed."""

    return _validated(lambda: _template_version(value)[0])


def validate_template_catalog_response(
    value: object,
    *,
    project_global_id: object | None = None,
) -> dict[str, Any]:
    """Return the exact closed published-template catalog or fail closed."""

    return _validated(
        lambda: _template_catalog(
            value,
            project_global_id=project_global_id,
        )
    )


def validate_workspace_response(
    value: object,
    *,
    project_global_id: object | None = None,
) -> dict[str, Any]:
    """Return the exact closed Project readiness workspace or fail closed."""

    return _validated(
        lambda: _workspace(
            value,
            project_global_id=project_global_id,
        )
    )


def validate_command_response(
    operation: object,
    value: object,
    *,
    project_global_id: object | None = None,
    template_global_id: object | None = None,
    template_version: object | None = None,
    instance_global_id: object | None = None,
) -> dict[str, Any]:
    """Validate one command or replay against its exact route semantics."""

    return _validated(
        lambda: _command_response(
            operation,
            value,
            project_global_id=project_global_id,
            template_global_id=template_global_id,
            template_version=template_version,
            instance_global_id=instance_global_id,
        )
    )


def validate_receipt_response(
    operation: object,
    value: object,
    *,
    target_global_id: object,
    project_global_id: object | None = None,
) -> dict[str, Any]:
    """Validate a sealed or replayed receipt against its operation response type."""

    if operation in _TEMPLATE_OPERATIONS:
        response = validate_command_response(
            operation,
            value,
        )
        expected_target = (
            response["templateGlobalId"]
            if operation == "readiness_template.create"
            else response["globalId"]
        )
        if _canonical_uuid(target_global_id) != expected_target:
            raise ReadinessResponseInvalid()
        return response
    if operation in _INSTANCE_OPERATIONS:
        response = validate_command_response(
            operation,
            value,
            project_global_id=project_global_id,
        )
        current = response["currentRevision"]
        if not isinstance(current, dict):
            raise ReadinessResponseInvalid()
        if _canonical_uuid(target_global_id) != current["globalId"]:
            raise ReadinessResponseInvalid()
        return response
    raise ReadinessResponseInvalid()


def _validated(validate: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return validate()
    except ReadinessResponseInvalid:
        raise
    except Exception as error:
        raise ReadinessResponseInvalid() from error


def _command_response(
    operation: object,
    value: object,
    *,
    project_global_id: object | None,
    template_global_id: object | None,
    template_version: object | None,
    instance_global_id: object | None,
) -> dict[str, Any]:
    if operation in _TEMPLATE_OPERATIONS:
        response, _template = _template_version(value)
        expected_state = (
            ReadinessPublicationState.PUBLISHED.value
            if operation == "readiness_template.publish"
            else ReadinessPublicationState.DRAFT.value
        )
        if response["publicationState"] != expected_state:
            raise ReadinessResponseInvalid()
        if (
            template_global_id is not None
            and _canonical_uuid(template_global_id)
            != response["templateGlobalId"]
        ):
            raise ReadinessResponseInvalid()
        if template_version is not None and (
            type(template_version) is not int
            or template_version != response["templateVersion"]
        ):
            raise ReadinessResponseInvalid()
        return response
    if operation in _INSTANCE_OPERATIONS:
        response = _workspace(
            value,
            project_global_id=project_global_id,
        )
        current = response["currentRevision"]
        if not isinstance(current, dict):
            raise ReadinessResponseInvalid()
        version = current["instanceVersion"]
        if (
            (operation == "readiness_instance.initialize" and version != 1)
            or (operation == "readiness_instance.revise" and version < 2)
            or (
                instance_global_id is not None
                and _canonical_uuid(instance_global_id)
                != current["instanceGlobalId"]
            )
        ):
            raise ReadinessResponseInvalid()
        return response
    raise ReadinessResponseInvalid()


def _template_catalog(
    value: object,
    *,
    project_global_id: object | None,
) -> dict[str, Any]:
    record = _closed_record(value, frozenset({"projectGlobalId", "templates"}))
    project_id = _canonical_uuid(record["projectGlobalId"])
    if (
        project_global_id is not None
        and _canonical_uuid(project_global_id) != project_id
    ):
        raise ReadinessResponseInvalid()
    templates = _bounded_list(record["templates"], maximum=1_000)
    parsed: list[ReadinessTemplateVersion] = []
    canonical: list[dict[str, Any]] = []
    for item in templates:
        response, template = _template_version(item)
        if template.publication_state is not ReadinessPublicationState.PUBLISHED:
            raise ReadinessResponseInvalid()
        canonical.append(response)
        parsed.append(template)
    identities = tuple(item.global_id for item in parsed)
    if len(set(identities)) != len(identities):
        raise ReadinessResponseInvalid()
    expected = {"projectGlobalId": project_id, "templates": canonical}
    if record != expected:
        raise ReadinessResponseInvalid()
    return expected


def _template_version(
    value: object,
) -> tuple[dict[str, Any], ReadinessTemplateVersion]:
    record = _closed_record(value, _TEMPLATE_VERSION_FIELDS)
    snapshot = {key: item for key, item in record.items() if key != "snapshotHash"}
    parsed = template_from_snapshot(snapshot)
    if not parsed.categories or not parsed.items:
        raise ReadinessResponseInvalid()
    expected = {**parsed.snapshot_payload(), "snapshotHash": parsed.snapshot_hash}
    if record != expected:
        raise ReadinessResponseInvalid()
    return expected, parsed


def _workspace(
    value: object,
    *,
    project_global_id: object | None,
) -> dict[str, Any]:
    record = _closed_record(value, _WORKSPACE_FIELDS)
    project_id = _canonical_uuid(record["projectGlobalId"])
    if (
        project_global_id is not None
        and _canonical_uuid(project_global_id) != project_id
    ):
        raise ReadinessResponseInvalid()
    revision_records = _bounded_list(record["revisions"], maximum=1_000)
    revisions: list[ReadinessInstanceRevision] = []
    canonical_revisions: list[dict[str, Any]] = []
    for item in revision_records:
        response, revision = _instance_revision(item)
        if str(revision.project.global_id) != project_id:
            raise ReadinessResponseInvalid()
        canonical_revisions.append(response)
        revisions.append(revision)
    for current, successor in zip(revisions, revisions[1:]):
        validate_readiness_successor(current, successor)

    current_record = record["currentRevision"]
    if current_record is None:
        if revisions:
            raise ReadinessResponseInvalid()
        canonical_current = None
    else:
        canonical_current, current = _instance_revision(current_record)
        if not revisions or current != revisions[-1]:
            raise ReadinessResponseInvalid()

    source_options = [
        _source_option(item)
        for item in _bounded_list(record["sourceOptions"], maximum=1_000)
    ]
    source_identities = tuple(
        (item["kind"], item["globalId"], item["sourceVersion"])
        for item in source_options
    )
    if len(set(source_identities)) != len(source_identities):
        raise ReadinessResponseInvalid()

    unavailable = [
        {
            "kind": kind.value,
            "state": "unavailable",
            "reasonCode": EXTERNAL_UNAVAILABLE_REASON_CODES[kind],
        }
        for kind in sorted(EXTERNAL_SOURCE_KINDS, key=lambda item: item.value)
    ]
    if record["unavailableProjections"] != unavailable:
        raise ReadinessResponseInvalid()

    permissions = _closed_record(record["permissions"], _PERMISSION_FIELDS)
    if any(type(permissions[field]) is not bool for field in _PERMISSION_FIELDS):
        raise ReadinessResponseInvalid()

    expected = {
        "projectGlobalId": project_id,
        "currentRevision": canonical_current,
        "revisions": canonical_revisions,
        "sourceOptions": source_options,
        "unavailableProjections": unavailable,
        "permissions": dict(permissions),
    }
    if record != expected:
        raise ReadinessResponseInvalid()
    return expected


def _instance_revision(
    value: object,
) -> tuple[dict[str, Any], ReadinessInstanceRevision]:
    record = _closed_record(value, _INSTANCE_REVISION_FIELDS)
    snapshot = {key: item for key, item in record.items() if key != "snapshotHash"}
    parsed = instance_from_snapshot(snapshot)
    if len(parsed.project.customer_reference_keys) > 100:
        raise ReadinessResponseInvalid()
    expected = {**parsed.snapshot_payload(), "snapshotHash": parsed.snapshot_hash}
    if record != expected:
        raise ReadinessResponseInvalid()
    return expected, parsed


def _source_option(value: object) -> dict[str, Any]:
    record = _closed_record(value, _SOURCE_OPTION_FIELDS)
    if record["kind"] != "domain_work_item":
        raise ReadinessResponseInvalid()
    global_id = _canonical_uuid(record["globalId"])
    version = record["sourceVersion"]
    if type(version) is not int or version < 1:
        raise ReadinessResponseInvalid()
    snapshot_hash = record["snapshotHash"]
    if not isinstance(snapshot_hash, str) or _HASH.fullmatch(snapshot_hash) is None:
        raise ReadinessResponseInvalid()
    label = _bounded_text(record["label"], maximum=280)
    state_label = _bounded_text(record["stateLabelSource"], maximum=140)
    if (
        state_label not in POLICY_LABEL_SOURCES
        or type(record["stateTerminal"]) is not bool
    ):
        raise ReadinessResponseInvalid()
    expected = {
        "kind": "domain_work_item",
        "globalId": global_id,
        "sourceVersion": version,
        "snapshotHash": snapshot_hash,
        "label": label,
        "stateLabelSource": state_label,
        "stateTerminal": record["stateTerminal"],
    }
    if record != expected:
        raise ReadinessResponseInvalid()
    return expected


def _closed_record(value: object, fields: frozenset[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise ReadinessResponseInvalid()
    return dict(value)


def _bounded_list(value: object, *, maximum: int) -> list[object]:
    if type(value) is not list or len(value) > maximum:
        raise ReadinessResponseInvalid()
    return list(value)


def _canonical_uuid(value: object) -> str:
    if not isinstance(value, str):
        raise ReadinessResponseInvalid()
    try:
        parsed = UUID(value)
    except (AttributeError, TypeError, ValueError) as error:
        raise ReadinessResponseInvalid() from error
    if str(parsed) != value:
        raise ReadinessResponseInvalid()
    return value


def _bounded_text(value: object, *, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
    ):
        raise ReadinessResponseInvalid()
    return value
