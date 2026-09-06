from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from npi_erpnext_connector.item_contract import canonical_hash, canonical_json

MBOM_OPERATION = "publish_released_mbom"
MBOM_METHOD_PATH = "/api/method/npi_erpnext_connector.mbom_api.publish_mbom"
MAX_MBOM_REQUEST_BYTES = 4_194_304
MAX_MBOM_LINES = 500
CREATE_INTENT = "create_draft"
UPDATE_INTENT = "update_draft"
EDITABLE_DRAFT = "editable_draft"
SUBMITTED_IMMUTABLE = "submitted_immutable"

_HASH = re.compile(r"^[a-f0-9]{64}$")
_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,139}$")
_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_UOM = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._:/-]{0,15}$")
_QUANTITY = re.compile(r"^(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,12})?$")
_ACTOR = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TOP_KEYS = {
    "contractVersion",
    "operation",
    "requestGlobalId",
    "attemptGlobalId",
    "attemptNumber",
    "targetIdempotencyKeyHash",
    "sourceHash",
    "topologyHash",
    "itemMappingSetHash",
    "mbomMappingSetHash",
    "nodeManifestHash",
    "request",
    "nodes",
}
_REQUEST_KEYS = {
    "schemaVersion",
    "apiVersion",
    "operation",
    "globalId",
    "source",
    "itemReadiness",
    "itemMappingSetHash",
    "mbomExpectations",
    "mbomMappingSetHash",
    "profile",
    "actorUserId",
    "serviceActorUserId",
    "requestId",
    "traceId",
    "idempotencyKeyHash",
    "targetIdempotencyKeyHash",
    "semanticEffectHash",
    "state",
    "dispatchAllowed",
    "createdAt",
}
_SOURCE_KEYS = {
    "schemaVersion",
    "tenantId",
    "projectGlobalId",
    "ebomGlobalId",
    "phase5PublishRequestGlobalId",
    "phase5PublishRequestPayloadHash",
    "publishPolicyGlobalId",
    "publishPolicyVersion",
    "publishPolicySnapshotHash",
    "lifecycleVersion",
    "releaseEventGlobalId",
    "releaseEventHash",
    "approvalEvidenceIds",
    "releasedAt",
    "topology",
    "sourceStreamKeyHash",
    "topologyHash",
    "sourceHash",
}
_TOPOLOGY_KEYS = {
    "revisionGlobalId",
    "revisionNumber",
    "revisionSnapshotHash",
    "lines",
}
_LINE_KEYS = {
    "lineGlobalId",
    "stableLineKey",
    "parentLineKey",
    "engineeringItemId",
    "quantity",
    "engineeringUom",
    "alternates",
    "effectivity",
    "attributes",
    "lineHash",
    "sourceRole",
}
_READINESS_KEYS = {
    "engineeringItemId",
    "disposition",
    "itemStreamKeyHash",
    "mappingVersion",
    "formalItemCode",
    "targetVersion",
    "observationHash",
    "authority",
    "responseAuthenticated",
    "syntheticItemReference",
}
_EXPECTATION_KEYS = {
    "assemblySourceKey",
    "stableLineKey",
    "mappingVersion",
    "submissionState",
    "intent",
    "formalBomId",
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
_NODE_KEYS = {"line", "itemReadiness", "mbomExpectation"}


class MbomContractError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MbomItemReadiness:
    engineering_item_id: str
    stream_key_hash: str
    mapping_version: int
    formal_item_code: str
    target_version: str
    raw: dict[str, object]


@dataclass(frozen=True, slots=True)
class MbomComponent:
    stable_line_key: str
    formal_item_code: str
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class MbomNodeCommand:
    stable_line_key: str
    assembly_source_key: str
    engineering_item_id: str
    formal_item_code: str
    intent: str
    expected_mapping_version: int
    expected_formal_bom_id: str | None
    expected_target_version: str | None
    components: tuple[MbomComponent, ...]
    raw: dict[str, object]


@dataclass(frozen=True, slots=True)
class MbomCommand:
    request_global_id: str
    attempt_global_id: str
    attempt_number: int
    target_idempotency_key_hash: str
    semantic_request_hash: str
    source_hash: str
    topology_hash: str
    item_mapping_set_hash: str
    mbom_mapping_set_hash: str
    node_manifest_hash: str
    tenant_id: str
    project_global_id: str
    ebom_global_id: str
    source_stream_key_hash: str
    actor_user_id: str
    item_readiness: tuple[MbomItemReadiness, ...]
    nodes: tuple[MbomNodeCommand, ...]
    raw: dict[str, object]


def decode_mbom_command(body: bytes) -> MbomCommand:
    if not isinstance(body, bytes) or not body or len(body) > MAX_MBOM_REQUEST_BYTES:
        raise MbomContractError("MBOM request body is invalid.")
    try:
        raw = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise MbomContractError("MBOM request JSON is invalid.") from error
    top = _object(raw, _TOP_KEYS, "MBOM command")
    if top["contractVersion"] != 1 or top["operation"] != MBOM_OPERATION:
        raise MbomContractError("MBOM command version or operation is invalid.")
    request_id = _uuid(top["requestGlobalId"], "requestGlobalId")
    attempt_id = _uuid(top["attemptGlobalId"], "attemptGlobalId")
    attempt_number = _positive_int(top["attemptNumber"], "attemptNumber")
    target_key = _hash(top["targetIdempotencyKeyHash"], "targetIdempotencyKeyHash")
    source_hash = _hash(top["sourceHash"], "sourceHash")
    topology_hash = _hash(top["topologyHash"], "topologyHash")
    item_set_hash = _hash(top["itemMappingSetHash"], "itemMappingSetHash")
    mbom_set_hash = _hash(top["mbomMappingSetHash"], "mbomMappingSetHash")
    node_manifest_hash = _hash(top["nodeManifestHash"], "nodeManifestHash")
    request = _object(top["request"], _REQUEST_KEYS, "MBOM request")
    if (
        request["schemaVersion"] != 2
        or request["apiVersion"] != "npi.erp-mbom-publish.v1"
        or request["operation"] != MBOM_OPERATION
        or request["globalId"] != request_id
        or request["targetIdempotencyKeyHash"] != target_key
        or request["itemMappingSetHash"] != item_set_hash
        or request["mbomMappingSetHash"] != mbom_set_hash
        or request["state"] != "queued"
        or request["dispatchAllowed"] is not True
    ):
        raise MbomContractError("MBOM request binding is invalid.")
    _uuid(request["requestId"], "request.requestId")
    actor_user_id = _actor(request["actorUserId"], "request.actorUserId")
    _text(request["serviceActorUserId"], "request.serviceActorUserId", 254)
    _text(request["traceId"], "request.traceId", 128)
    _hash(request["idempotencyKeyHash"], "request.idempotencyKeyHash")
    _text(request["createdAt"], "request.createdAt", 64)

    profile = _object(request["profile"], _PROFILE_KEYS, "MBOM profile")
    if profile["targetMode"] != "sandbox":
        raise MbomContractError("MBOM target mode is not an authoritative sandbox.")
    _text(profile["profileId"], "profile.profileId", 128)
    _positive_int(profile["profileVersion"], "profile.profileVersion")
    _text(profile["environmentCode"], "profile.environmentCode", 64)
    _text(profile["projectionPolicyId"], "profile.projectionPolicyId", 128)
    _positive_int(profile["projectionPolicyVersion"], "profile.projectionPolicyVersion")
    _hash(profile["projectionPolicyHash"], "profile.projectionPolicyHash")
    _hash(profile["snapshotHash"], "profile.snapshotHash")

    source = _object(request["source"], _SOURCE_KEYS, "MBOM source")
    tenant_id = _text(source["tenantId"], "source.tenantId", 128)
    project_id = _uuid(source["projectGlobalId"], "source.projectGlobalId")
    ebom_id = _uuid(source["ebomGlobalId"], "source.ebomGlobalId")
    source_stream_key_hash = _hash(
        source["sourceStreamKeyHash"], "source.sourceStreamKeyHash"
    )
    if source["schemaVersion"] != 2 or project_id != request.get("source", {}).get(
        "projectGlobalId"
    ):
        raise MbomContractError("MBOM source version is invalid.")
    for key in (
        "phase5PublishRequestGlobalId",
        "publishPolicyGlobalId",
        "releaseEventGlobalId",
    ):
        _uuid(source[key], f"source.{key}")
    for key in (
        "phase5PublishRequestPayloadHash",
        "publishPolicySnapshotHash",
        "releaseEventHash",
    ):
        _hash(source[key], f"source.{key}")
    for key in ("publishPolicyVersion", "lifecycleVersion"):
        _positive_int(source[key], f"source.{key}")
    approvals = _array(
        source["approvalEvidenceIds"], "source.approvalEvidenceIds", 1, 32
    )
    if len({_uuid(value, "source.approvalEvidenceIds") for value in approvals}) != len(
        approvals
    ):
        raise MbomContractError("MBOM approval evidence is invalid.")
    _text(source["releasedAt"], "source.releasedAt", 64)
    expected_stream = canonical_hash(
        {
            "schemaVersion": 2,
            "tenantId": tenant_id,
            "projectGlobalId": project_id,
            "ebomGlobalId": ebom_id,
        }
    )
    topology = _object(source["topology"], _TOPOLOGY_KEYS, "MBOM topology")
    lines = _lines(topology)
    expected_topology = canonical_hash(topology)
    source_payload = dict(source)
    for key in ("sourceStreamKeyHash", "topologyHash", "sourceHash"):
        source_payload.pop(key)
    expected_source = canonical_hash(source_payload)
    if (
        source_stream_key_hash != expected_stream
        or source["topologyHash"] != expected_topology
        or topology_hash != expected_topology
        or source["sourceHash"] != expected_source
        or source_hash != expected_source
    ):
        raise MbomContractError("MBOM source hash binding is invalid.")

    readiness = _readiness(request["itemReadiness"])
    readiness_by_item = {value.engineering_item_id: value for value in readiness}
    if set(readiness_by_item) != {line["engineeringItemId"] for line in lines.values()}:
        raise MbomContractError("MBOM Item readiness does not cover the topology.")
    expected_item_set = canonical_hash(
        {
            "sourceHash": source_hash,
            "targetMode": "sandbox",
            "items": [value.raw for value in readiness],
        }
    )
    if item_set_hash != expected_item_set:
        raise MbomContractError("MBOM Item mapping-set hash is invalid.")

    assembly_keys = tuple(
        sorted(key for key, line in lines.items() if line["sourceRole"] == "assembly")
    )
    expectations = _expectations(
        request["mbomExpectations"],
        source_hash=source_hash,
        topology_hash=topology_hash,
        tenant_id=tenant_id,
        project_id=project_id,
        ebom_id=ebom_id,
        assembly_keys=assembly_keys,
    )
    expected_mbom_set = canonical_hash(
        {
            "sourceHash": source_hash,
            "topologyHash": topology_hash,
            "assemblies": [expectations[key] for key in assembly_keys],
        }
    )
    if mbom_set_hash != expected_mbom_set:
        raise MbomContractError("MBOM mapping-set hash is invalid.")
    semantic = canonical_hash(
        {
            "schemaVersion": 2,
            "operation": MBOM_OPERATION,
            "sourceStreamKeyHash": source_stream_key_hash,
            "sourceHash": source_hash,
            "topologyHash": topology_hash,
            "itemMappingSetHash": item_set_hash,
            "mbomMappingSetHash": mbom_set_hash,
            "profile": profile,
        }
    )
    if request["semanticEffectHash"] != semantic or target_key != canonical_hash(
        {"operation": MBOM_OPERATION, "semanticEffectHash": semantic}
    ):
        raise MbomContractError("MBOM semantic identity is invalid.")

    raw_nodes = _array(top["nodes"], "nodes", len(assembly_keys), len(assembly_keys))
    nodes: list[MbomNodeCommand] = []
    for index, stable_key in enumerate(assembly_keys):
        node = _object(raw_nodes[index], _NODE_KEYS, "MBOM node")
        line = lines[stable_key]
        item = readiness_by_item[line["engineeringItemId"]]
        expectation = expectations[stable_key]
        expected_node = {
            "line": line,
            "itemReadiness": item.raw,
            "mbomExpectation": expectation,
        }
        if node != expected_node:
            raise MbomContractError("MBOM node snapshot is invalid.")
        components = tuple(
            MbomComponent(
                child_key,
                readiness_by_item[child["engineeringItemId"]].formal_item_code,
                _decimal_quantity(child["quantity"]),
            )
            for child_key, child in sorted(lines.items())
            if child["parentLineKey"] == stable_key
        )
        if not components:
            raise MbomContractError("MBOM assembly has no direct components.")
        nodes.append(
            MbomNodeCommand(
                stable_line_key=stable_key,
                assembly_source_key=str(expectation["assemblySourceKey"]),
                engineering_item_id=str(line["engineeringItemId"]),
                formal_item_code=item.formal_item_code,
                intent=str(expectation["intent"]),
                expected_mapping_version=int(expectation["mappingVersion"]),
                expected_formal_bom_id=_optional_code(expectation["formalBomId"]),
                expected_target_version=_optional_text(
                    expectation["targetVersion"], 140
                ),
                components=components,
                raw=node,
            )
        )
    semantic_raw = dict(top)
    semantic_raw.pop("attemptGlobalId")
    semantic_raw.pop("attemptNumber")
    return MbomCommand(
        request_id,
        attempt_id,
        attempt_number,
        target_key,
        canonical_hash(semantic_raw),
        source_hash,
        topology_hash,
        item_set_hash,
        mbom_set_hash,
        node_manifest_hash,
        tenant_id,
        project_id,
        ebom_id,
        source_stream_key_hash,
        actor_user_id,
        readiness,
        tuple(nodes),
        top,
    )


def _lines(topology: dict[str, object]) -> dict[str, dict[str, object]]:
    _uuid(topology["revisionGlobalId"], "topology.revisionGlobalId")
    _positive_int(topology["revisionNumber"], "topology.revisionNumber")
    _hash(topology["revisionSnapshotHash"], "topology.revisionSnapshotHash")
    raw_lines = _array(topology["lines"], "topology.lines", 2, MAX_MBOM_LINES)
    lines: dict[str, dict[str, object]] = {}
    for value in raw_lines:
        line = _object(value, _LINE_KEYS, "MBOM line")
        _uuid(line["lineGlobalId"], "line.lineGlobalId")
        key = _key(line["stableLineKey"], "line.stableLineKey")
        if key in lines:
            raise MbomContractError("MBOM stable line key is duplicated.")
        parent = line["parentLineKey"]
        if parent is not None:
            _key(parent, "line.parentLineKey")
        _key(line["engineeringItemId"], "line.engineeringItemId")
        _decimal_quantity(line["quantity"])
        if (
            not isinstance(line["engineeringUom"], str)
            or _UOM.fullmatch(line["engineeringUom"]) is None
        ):
            raise MbomContractError("MBOM engineering UOM is invalid.")
        _array(line["alternates"], "line.alternates", 0, 32)
        _string_map(line["effectivity"], "line.effectivity")
        _string_map(line["attributes"], "line.attributes")
        _hash(line["lineHash"], "line.lineHash")
        if line["sourceRole"] not in {"assembly", "component_only"}:
            raise MbomContractError("MBOM source role is invalid.")
        lines[key] = line
    if tuple(lines) != tuple(sorted(lines)):
        raise MbomContractError("MBOM topology is not canonical.")
    keys = set(lines)
    roots = [line for line in lines.values() if line["parentLineKey"] is None]
    if len(roots) != 1 or any(
        line["parentLineKey"] not in keys
        for line in lines.values()
        if line["parentLineKey"] is not None
    ):
        raise MbomContractError("MBOM topology parentage is invalid.")
    parents = {
        str(line["parentLineKey"])
        for line in lines.values()
        if line["parentLineKey"] is not None
    }
    for key, line in lines.items():
        expected_role = "assembly" if key in parents else "component_only"
        if line["sourceRole"] != expected_role:
            raise MbomContractError("MBOM source role does not match topology.")
        seen: set[str] = set()
        current: str | None = key
        while current is not None:
            if current in seen:
                raise MbomContractError("MBOM topology contains a cycle.")
            seen.add(current)
            parent_value = lines[current]["parentLineKey"]
            current = str(parent_value) if parent_value is not None else None
    return lines


def _readiness(value: object) -> tuple[MbomItemReadiness, ...]:
    rows = _array(value, "itemReadiness", 1, MAX_MBOM_LINES)
    result: list[MbomItemReadiness] = []
    for raw in rows:
        row = _object(raw, _READINESS_KEYS, "MBOM Item readiness")
        engineering_id = _key(
            row["engineeringItemId"], "itemReadiness.engineeringItemId"
        )
        if (
            row["disposition"] != "advanced"
            or row["authority"] != "authoritative_sandbox"
            or row["responseAuthenticated"] is not True
            or row["syntheticItemReference"] is not None
        ):
            raise MbomContractError("MBOM Item readiness is not authoritative.")
        result.append(
            MbomItemReadiness(
                engineering_id,
                _hash(row["itemStreamKeyHash"], "itemReadiness.itemStreamKeyHash"),
                _positive_int(row["mappingVersion"], "itemReadiness.mappingVersion"),
                _code(row["formalItemCode"], "itemReadiness.formalItemCode"),
                _text(row["targetVersion"], "itemReadiness.targetVersion", 140),
                row,
            )
        )
        _hash(row["observationHash"], "itemReadiness.observationHash")
    result.sort(key=lambda item: item.engineering_item_id)
    if len({item.engineering_item_id for item in result}) != len(result):
        raise MbomContractError("MBOM Item readiness is duplicated.")
    if [item.raw for item in result] != rows:
        raise MbomContractError("MBOM Item readiness is not canonical.")
    return tuple(result)


def _expectations(
    value: object,
    *,
    source_hash: str,
    topology_hash: str,
    tenant_id: str,
    project_id: str,
    ebom_id: str,
    assembly_keys: tuple[str, ...],
) -> dict[str, dict[str, object]]:
    rows = _array(value, "mbomExpectations", len(assembly_keys), len(assembly_keys))
    result: dict[str, dict[str, object]] = {}
    for raw in rows:
        row = _object(raw, _EXPECTATION_KEYS, "MBOM expectation")
        key = _key(row["stableLineKey"], "mbomExpectation.stableLineKey")
        expected_assembly_key = canonical_hash(
            {
                "schemaVersion": 2,
                "tenantId": tenant_id,
                "projectGlobalId": project_id,
                "ebomGlobalId": ebom_id,
                "stableLineKey": key,
            }
        )
        if row["assemblySourceKey"] != expected_assembly_key:
            raise MbomContractError("MBOM assembly source key is invalid.")
        version = _nonnegative_int(
            row["mappingVersion"], "mbomExpectation.mappingVersion"
        )
        _optional_hash(row["observationHash"], "mbomExpectation.observationHash")
        if version == 0:
            if (
                row["submissionState"] != "unmapped_create"
                or row["intent"] != CREATE_INTENT
                or any(
                    (row["formalBomId"], row["targetVersion"], row["observationHash"])
                )
            ):
                raise MbomContractError("MBOM create expectation is invalid.")
        else:
            if (
                row["submissionState"] != EDITABLE_DRAFT
                or row["intent"] != UPDATE_INTENT
                or _optional_code(row["formalBomId"]) is None
                or _optional_text(row["targetVersion"], 140) is None
                or row["observationHash"] is None
            ):
                raise MbomContractError("MBOM update expectation is invalid.")
        if key in result:
            raise MbomContractError("MBOM expectation is duplicated.")
        result[key] = row
    if tuple(result) != assembly_keys or set(result) != set(assembly_keys):
        raise MbomContractError("MBOM expectations are not canonical or complete.")
    del source_hash, topology_hash
    return result


def _object(value: object, keys: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise MbomContractError(f"{label} shape is invalid.")
    return value


def _array(value: object, label: str, minimum: int, maximum: int) -> list[Any]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise MbomContractError(f"{label} is invalid.")
    return value


def _string_map(value: object, label: str) -> None:
    if not isinstance(value, dict) or len(value) > 64:
        raise MbomContractError(f"{label} is invalid.")
    for key, item in value.items():
        _text(key, label, 64)
        _text(item, label, 280)


def _uuid(value: object, label: str) -> str:
    try:
        parsed = UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise MbomContractError(f"{label} is invalid.") from error
    if parsed.int == 0 or str(parsed) != str(value).casefold():
        raise MbomContractError(f"{label} is invalid.")
    return str(parsed)


def _text(value: object, label: str, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
    ):
        raise MbomContractError(f"{label} is invalid.")
    return value


def _actor(value: object, label: str) -> str:
    actor = _text(value, label, 254)
    if (
        actor != actor.casefold()
        or _ACTOR.fullmatch(actor) is None
        or actor in {"guest", "administrator"}
    ):
        raise MbomContractError(f"{label} is invalid.")
    return actor


def _key(value: object, label: str) -> str:
    text = _text(value, label, 128)
    if _KEY.fullmatch(text) is None:
        raise MbomContractError(f"{label} is invalid.")
    return text


def _code(value: object, label: str) -> str:
    text = _text(value, label, 140)
    if _CODE.fullmatch(text) is None:
        raise MbomContractError(f"{label} is invalid.")
    return text


def _optional_code(value: object) -> str | None:
    return None if value is None else _code(value, "optional code")


def _optional_text(value: object, maximum: int) -> str | None:
    return None if value is None else _text(value, "optional text", maximum)


def _hash(value: object, label: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise MbomContractError(f"{label} is invalid.")
    return value


def _optional_hash(value: object, label: str) -> str | None:
    return None if value is None else _hash(value, label)


def _positive_int(value: object, label: str) -> int:
    if type(value) is not int or value < 1:
        raise MbomContractError(f"{label} is invalid.")
    return value


def _nonnegative_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise MbomContractError(f"{label} is invalid.")
    return value


def _decimal_quantity(value: object) -> Decimal:
    if not isinstance(value, str) or _QUANTITY.fullmatch(value) is None:
        raise MbomContractError("MBOM quantity is invalid.")
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise MbomContractError("MBOM quantity is invalid.") from error
    if result <= 0 or result > Decimal("999999999999"):
        raise MbomContractError("MBOM quantity is invalid.")
    return result


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MbomContractError("MBOM JSON contains duplicate keys.")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise MbomContractError(f"MBOM JSON constant {value} is invalid.")


__all__ = [
    "CREATE_INTENT",
    "EDITABLE_DRAFT",
    "MBOM_METHOD_PATH",
    "MBOM_OPERATION",
    "SUBMITTED_IMMUTABLE",
    "UPDATE_INTENT",
    "MbomCommand",
    "MbomContractError",
    "MbomNodeCommand",
    "canonical_hash",
    "canonical_json",
    "decode_mbom_command",
]
