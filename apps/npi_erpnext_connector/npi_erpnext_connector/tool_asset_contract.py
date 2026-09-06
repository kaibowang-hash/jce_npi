from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from npi_erpnext_connector.item_contract import canonical_hash, canonical_json

CONTRACT_VERSION = 1
API_VERSION = "npi.erp-tool-asset.v1"
CREATE_OPERATION = "create_tool_asset"
UPDATE_OPERATION = "update_tool_asset"
OPERATIONS = (CREATE_OPERATION, UPDATE_OPERATION)
TOOL_ASSET_METHOD_PATH = (
    "/api/method/npi_erpnext_connector.tool_asset_api.upsert_npi_tool_asset_v1"
)
OWNED_FIELDS = (
    "tooling_master_title",
    "physical_set_serial",
    "tooling_requirement_kind",
    "source_tooling_revision",
    "acceptance_evidence_reference",
)
REQUIREMENT_KINDS = {
    "new_tool",
    "customer_owned_intake",
    "copy_or_additional_set",
    "modification",
    "repair",
    "capacity_need",
}
MAX_REQUEST_BYTES = 1_048_576

_HASH = re.compile(r"^[a-f0-9]{64}$")
_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,139}$")
_TRACE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_ACTOR = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_COMMAND_KEYS = {
    "contractVersion",
    "operation",
    "requestGlobalId",
    "attemptGlobalId",
    "attemptNumber",
    "targetIdempotencyKeyHash",
    "sourceHash",
    "mappingExpectation",
    "request",
    "ownedFieldsManifest",
}
_REQUEST_KEYS = {
    "schemaVersion",
    "apiVersion",
    "globalId",
    "operation",
    "tenantId",
    "projectGlobalId",
    "source",
    "approval",
    "mappingExpectation",
    "profile",
    "state",
    "actorUserId",
    "requestId",
    "traceId",
    "idempotencyKeyHash",
    "payloadHash",
    "optimisticVersion",
    "createdAt",
}
_SOURCE_KEYS = {
    "schemaVersion",
    "tenantId",
    "projectGlobalId",
    "toolingMasterGlobalId",
    "toolingMasterTitle",
    "toolingMasterSnapshotHash",
    "toolingSetGlobalId",
    "toolingSetPhysicalSerial",
    "toolingSetSnapshotHash",
    "toolingRequirementKind",
    "setRevisionBindingGlobalId",
    "setRevisionBindingSnapshotHash",
    "toolingRevisionGlobalId",
    "toolingRevisionNumber",
    "toolingRevisionLabel",
    "toolingRevisionSnapshotHash",
    "acceptanceRevisionGlobalId",
    "acceptanceGlobalId",
    "acceptanceVersion",
    "acceptancePredecessorGlobalId",
    "acceptancePredecessorSnapshotHash",
    "acceptanceSnapshotHash",
    "acceptedAt",
    "ownedFieldsManifest",
    "sourceStreamKeyHash",
    "sourceHash",
}
_APPROVAL_KEYS = {
    "state",
    "policyId",
    "policyVersion",
    "policyHash",
    "evidenceReference",
    "evidenceHash",
}
_MAPPING_KEYS = {
    "operation",
    "sourceStreamKeyHash",
    "mappingVersion",
    "formalAssetId",
    "targetVersion",
    "observationHash",
}
_PROFILE_KEYS = {
    "profileId",
    "profileVersion",
    "targetMode",
    "environmentCode",
    "projectionPolicyId",
    "projectionPolicyVersion",
    "projectionPolicyHash",
    "snapshotHash",
}


class ToolAssetContractError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ToolAssetCommand:
    raw: dict[str, object]
    operation: str
    request_global_id: str
    attempt_global_id: str
    attempt_number: int
    target_idempotency_key_hash: str
    source_hash: str
    source_stream_key_hash: str
    tenant_id: str
    project_global_id: str
    actor_user_id: str
    tooling_set_global_id: str
    tooling_master_title: str
    physical_set_serial: str
    tooling_requirement_kind: str
    tooling_revision_reference: str
    acceptance_evidence_reference: str
    accepted_at: datetime
    expected_mapping_version: int
    expected_formal_asset_id: str | None
    expected_target_version: str | None
    semantic_request_hash: str

    def owned_values(self) -> dict[str, str]:
        return {
            "tooling_master_title": self.tooling_master_title,
            "physical_set_serial": self.physical_set_serial,
            "tooling_requirement_kind": self.tooling_requirement_kind,
            "source_tooling_revision": self.tooling_revision_reference,
            "acceptance_evidence_reference": self.acceptance_evidence_reference,
        }


def decode_tool_asset_command(raw_body: bytes) -> ToolAssetCommand:
    if not isinstance(raw_body, bytes) or not 1 <= len(raw_body) <= MAX_REQUEST_BYTES:
        raise ToolAssetContractError("Tool Asset request size is invalid.")
    try:
        raw = json.loads(
            raw_body.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_float=Decimal,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ToolAssetContractError("Tool Asset request JSON is invalid.") from error
    command = _object(raw, _COMMAND_KEYS, "command")
    if command["contractVersion"] != CONTRACT_VERSION:
        raise ToolAssetContractError("Tool Asset contract version is invalid.")
    operation = _operation(command["operation"])
    request_global_id = _uuid(command["requestGlobalId"], "requestGlobalId")
    attempt_global_id = _uuid(command["attemptGlobalId"], "attemptGlobalId")
    attempt_number = _positive(command["attemptNumber"], "attemptNumber")
    target_key = _hash(
        command["targetIdempotencyKeyHash"],
        "targetIdempotencyKeyHash",
    )
    source_hash = _hash(command["sourceHash"], "sourceHash")
    if command["ownedFieldsManifest"] != list(OWNED_FIELDS):
        raise ToolAssetContractError("Tool Asset owned field manifest is invalid.")

    request = _object(command["request"], _REQUEST_KEYS, "request")
    if request["schemaVersion"] != 2 or request["apiVersion"] != API_VERSION:
        raise ToolAssetContractError("Tool Asset request version is invalid.")
    if (
        _operation(request["operation"]) != operation
        or _uuid(request["globalId"], "request.globalId") != request_global_id
        or request["state"] != "queued"
    ):
        raise ToolAssetContractError("Tool Asset request identity is invalid.")
    tenant_id = _text(request["tenantId"], "request.tenantId", 128, _KEY)
    project_global_id = _uuid(
        request["projectGlobalId"],
        "request.projectGlobalId",
    )

    source = _object(request["source"], _SOURCE_KEYS, "request.source")
    source_values = _source(source, tenant_id, project_global_id)
    if source_values["source_hash"] != source_hash:
        raise ToolAssetContractError("Tool Asset source hash binding is invalid.")

    approval = _approval(request["approval"])
    mapping = _mapping(
        request["mappingExpectation"],
        operation,
        source_values["source_stream_key_hash"],
    )
    if command["mappingExpectation"] != mapping:
        raise ToolAssetContractError("Tool Asset mapping binding is invalid.")
    profile = _profile(request["profile"])
    actor_user_id = _actor(request["actorUserId"], "request.actorUserId")
    _uuid(request["requestId"], "request.requestId")
    _text(request["traceId"], "request.traceId", 128, _TRACE)
    _hash(request["idempotencyKeyHash"], "request.idempotencyKeyHash")
    _positive(request["optimisticVersion"], "request.optimisticVersion")
    _canonical_datetime(request["createdAt"], "request.createdAt")
    expected_payload_hash = canonical_hash(
        {
            "schemaVersion": 2,
            "apiVersion": API_VERSION,
            "operation": operation,
            "source": source,
            "approval": approval,
            "mappingExpectation": mapping,
            "profile": profile,
        }
    )
    if _hash(request["payloadHash"], "request.payloadHash") != expected_payload_hash:
        raise ToolAssetContractError("Tool Asset request payload hash is invalid.")
    if canonical_json(request) != canonical_json(command["request"]):
        raise ToolAssetContractError("Tool Asset request is not canonical.")

    semantic_hash = canonical_hash(
        {
            "contractVersion": CONTRACT_VERSION,
            "operation": operation,
            "requestGlobalId": request_global_id,
            "targetIdempotencyKeyHash": target_key,
            "sourceHash": source_hash,
            "mappingExpectation": mapping,
            "request": request,
            "ownedFieldsManifest": list(OWNED_FIELDS),
        }
    )
    return ToolAssetCommand(
        dict(command),
        operation,
        request_global_id,
        attempt_global_id,
        attempt_number,
        target_key,
        source_hash,
        source_values["source_stream_key_hash"],
        tenant_id,
        project_global_id,
        actor_user_id,
        source_values["tooling_set_global_id"],
        source_values["tooling_master_title"],
        source_values["physical_set_serial"],
        source_values["requirement_kind"],
        source_values["revision_reference"],
        source_values["acceptance_reference"],
        source_values["accepted_at"],
        mapping["mappingVersion"],
        mapping["formalAssetId"],
        mapping["targetVersion"],
        semantic_hash,
    )


def _source(
    value: dict[str, object],
    tenant_id: str,
    project_global_id: str,
) -> dict[str, object]:
    if value["schemaVersion"] != 2 or value["ownedFieldsManifest"] != list(
        OWNED_FIELDS
    ):
        raise ToolAssetContractError("Tool Asset source version is invalid.")
    if (
        _text(value["tenantId"], "source.tenantId", 128, _KEY) != tenant_id
        or _uuid(value["projectGlobalId"], "source.projectGlobalId")
        != project_global_id
    ):
        raise ToolAssetContractError("Tool Asset source scope is invalid.")
    _uuid(
        value["toolingMasterGlobalId"],
        "source.toolingMasterGlobalId",
    )
    title = _text(value["toolingMasterTitle"], "source.toolingMasterTitle", 140)
    _hash(value["toolingMasterSnapshotHash"], "source.toolingMasterSnapshotHash")
    tooling_set_global_id = _uuid(
        value["toolingSetGlobalId"],
        "source.toolingSetGlobalId",
    )
    serial = _text(
        value["toolingSetPhysicalSerial"],
        "source.toolingSetPhysicalSerial",
        80,
        _CODE,
    )
    _hash(value["toolingSetSnapshotHash"], "source.toolingSetSnapshotHash")
    kind = _text(
        value["toolingRequirementKind"],
        "source.toolingRequirementKind",
        64,
    )
    if kind not in REQUIREMENT_KINDS:
        raise ToolAssetContractError("Tool Asset requirement kind is invalid.")
    _uuid(
        value["setRevisionBindingGlobalId"],
        "source.setRevisionBindingGlobalId",
    )
    _hash(
        value["setRevisionBindingSnapshotHash"],
        "source.setRevisionBindingSnapshotHash",
    )
    revision_id = _uuid(
        value["toolingRevisionGlobalId"],
        "source.toolingRevisionGlobalId",
    )
    revision_number = _positive(
        value["toolingRevisionNumber"],
        "source.toolingRevisionNumber",
    )
    revision_label = _text(
        value["toolingRevisionLabel"],
        "source.toolingRevisionLabel",
        40,
    )
    _hash(
        value["toolingRevisionSnapshotHash"],
        "source.toolingRevisionSnapshotHash",
    )
    acceptance_revision_id = _uuid(
        value["acceptanceRevisionGlobalId"],
        "source.acceptanceRevisionGlobalId",
    )
    acceptance_id = _uuid(
        value["acceptanceGlobalId"],
        "source.acceptanceGlobalId",
    )
    acceptance_version = _positive(
        value["acceptanceVersion"],
        "source.acceptanceVersion",
    )
    predecessor_id = value["acceptancePredecessorGlobalId"]
    predecessor_hash = value["acceptancePredecessorSnapshotHash"]
    if acceptance_version == 1:
        if predecessor_id is not None or predecessor_hash is not None:
            raise ToolAssetContractError(
                "Tool Asset acceptance predecessor is invalid."
            )
    else:
        _uuid(predecessor_id, "source.acceptancePredecessorGlobalId")
        _hash(predecessor_hash, "source.acceptancePredecessorSnapshotHash")
    _hash(value["acceptanceSnapshotHash"], "source.acceptanceSnapshotHash")
    accepted_at = _canonical_datetime(value["acceptedAt"], "source.acceptedAt")
    stream = canonical_hash(
        {
            "schemaVersion": 2,
            "tenantId": tenant_id,
            "projectGlobalId": project_global_id,
            "toolingSetGlobalId": tooling_set_global_id,
        }
    )
    if _hash(value["sourceStreamKeyHash"], "source.sourceStreamKeyHash") != stream:
        raise ToolAssetContractError("Tool Asset source stream hash is invalid.")
    source_payload = {
        key: value[key]
        for key in _SOURCE_KEYS
        if key not in {"sourceStreamKeyHash", "sourceHash"}
    }
    source_hash = canonical_hash(source_payload)
    if _hash(value["sourceHash"], "source.sourceHash") != source_hash:
        raise ToolAssetContractError("Tool Asset source hash is invalid.")
    return {
        "source_stream_key_hash": stream,
        "source_hash": source_hash,
        "tooling_set_global_id": tooling_set_global_id,
        "tooling_master_title": title,
        "physical_set_serial": serial,
        "requirement_kind": kind,
        "revision_reference": f"{revision_id}@{revision_number}:{revision_label}",
        "acceptance_reference": (
            f"{acceptance_id}@{acceptance_version}:{acceptance_revision_id}"
        ),
        "accepted_at": accepted_at,
    }


def _approval(value: object) -> dict[str, object]:
    approval = _object(value, _APPROVAL_KEYS, "request.approval")
    if approval["state"] != "verified":
        raise ToolAssetContractError("Tool Asset business approval is unavailable.")
    _text(approval["policyId"], "approval.policyId", 128, _CODE)
    _positive(approval["policyVersion"], "approval.policyVersion")
    _hash(approval["policyHash"], "approval.policyHash")
    _text(
        approval["evidenceReference"],
        "approval.evidenceReference",
        140,
        _CODE,
    )
    _hash(approval["evidenceHash"], "approval.evidenceHash")
    return approval


def _mapping(value: object, operation: str, stream: str) -> dict[str, object]:
    mapping = _object(value, _MAPPING_KEYS, "request.mappingExpectation")
    if (
        _operation(mapping["operation"]) != operation
        or _hash(mapping["sourceStreamKeyHash"], "mapping.sourceStreamKeyHash")
        != stream
    ):
        raise ToolAssetContractError("Tool Asset mapping scope is invalid.")
    version = _nonnegative(mapping["mappingVersion"], "mapping.mappingVersion")
    if operation == CREATE_OPERATION:
        if version != 0 or any(
            mapping[key] is not None
            for key in ("formalAssetId", "targetVersion", "observationHash")
        ):
            raise ToolAssetContractError("Tool Asset create expectation is invalid.")
    else:
        if version < 1:
            raise ToolAssetContractError("Tool Asset update expectation is invalid.")
        _text(mapping["formalAssetId"], "mapping.formalAssetId", 140, _CODE)
        _text(mapping["targetVersion"], "mapping.targetVersion", 140)
        _hash(mapping["observationHash"], "mapping.observationHash")
    return mapping


def _profile(value: object) -> dict[str, object]:
    profile = _object(value, _PROFILE_KEYS, "request.profile")
    _text(profile["profileId"], "profile.profileId", 128, _CODE)
    _positive(profile["profileVersion"], "profile.profileVersion")
    if profile["targetMode"] != "sandbox":
        raise ToolAssetContractError("Tool Asset target mode is invalid.")
    _text(profile["environmentCode"], "profile.environmentCode", 64, _CODE)
    _text(
        profile["projectionPolicyId"],
        "profile.projectionPolicyId",
        128,
        _CODE,
    )
    _positive(profile["projectionPolicyVersion"], "profile.projectionPolicyVersion")
    _hash(profile["projectionPolicyHash"], "profile.projectionPolicyHash")
    _hash(profile["snapshotHash"], "profile.snapshotHash")
    return profile


def _object(value: object, keys: set[str], path: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ToolAssetContractError(f"Tool Asset {path} fields are invalid.")
    return value


def _operation(value: object) -> str:
    if value not in OPERATIONS:
        raise ToolAssetContractError("Tool Asset operation is invalid.")
    return str(value)


def _hash(value: object, path: str) -> str:
    return _text(value, path, 64, _HASH)


def _text(
    value: object,
    path: str,
    maximum: int,
    pattern: re.Pattern[str] | None = None,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
        or any(ord(character) < 32 for character in value)
        or (pattern is not None and pattern.fullmatch(value) is None)
    ):
        raise ToolAssetContractError(f"Tool Asset {path} is invalid.")
    return value


def _actor(value: object, path: str) -> str:
    actor = _text(value, path, 254, _ACTOR)
    if actor != actor.casefold() or actor in {"guest", "administrator"}:
        raise ToolAssetContractError(f"Tool Asset {path} is invalid.")
    return actor


def _uuid(value: object, path: str) -> str:
    try:
        parsed = UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise ToolAssetContractError(f"Tool Asset {path} is invalid.") from error
    if parsed.int == 0 or str(parsed) != str(value).casefold():
        raise ToolAssetContractError(f"Tool Asset {path} is invalid.")
    return str(parsed)


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise ToolAssetContractError(f"Tool Asset {path} is invalid.")
    return value


def _nonnegative(value: object, path: str) -> int:
    if type(value) is not int or value < 0:
        raise ToolAssetContractError(f"Tool Asset {path} is invalid.")
    return value


def _canonical_datetime(value: object, path: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ToolAssetContractError(f"Tool Asset {path} is invalid.")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ToolAssetContractError(f"Tool Asset {path} is invalid.") from error
    if parsed.isoformat().replace("+00:00", "Z") != value:
        raise ToolAssetContractError(f"Tool Asset {path} is invalid.")
    return parsed


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ToolAssetContractError(
                "Tool Asset request contains duplicate fields."
            )
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ToolAssetContractError(f"Tool Asset request constant {value} is invalid.")
