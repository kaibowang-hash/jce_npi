from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

CONTRACT_VERSION = 2
SOURCE_SCHEMA_VERSION = 1
OPERATION = "publish_released_item"
CREATE_INTENT = "create_item"
UPDATE_INTENT = "update_item_engineering_fields"
MAX_REQUEST_BYTES = 262_144

_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,139}$")
_ENGINEERING_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_ATTRIBUTE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,63}$")
_HASH = re.compile(r"^[a-f0-9]{64}$")
_TENANT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_UOM = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,15}$")
_ACTOR = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ItemContractError(ValueError):
    """Raised when a remote Item command is not exactly contract-shaped."""


@dataclass(frozen=True, slots=True)
class ItemCommand:
    request_global_id: str
    attempt_global_id: str
    attempt_number: int
    target_idempotency_key_hash: str
    source_hash: str
    source_stream_key_hash: str
    actor_user_id: str
    tenant_id: str
    project_global_id: str
    engineering_item_id: str
    description: str
    engineering_uom: str
    attributes: tuple[tuple[str, str], ...]
    intent: str
    expected_mapping_version: int
    expected_target_version: str | None
    raw: Mapping[str, object]

    @property
    def semantic_request_hash(self) -> str:
        value = dict(self.raw)
        value.pop("attemptGlobalId", None)
        value.pop("attemptNumber", None)
        return canonical_hash(value)


def decode_item_command(raw_body: bytes) -> ItemCommand:
    if (
        not isinstance(raw_body, bytes)
        or not raw_body
        or len(raw_body) > MAX_REQUEST_BYTES
    ):
        raise ItemContractError("Item command body is invalid.")
    try:
        value = json.loads(
            raw_body.decode("utf-8"),
            object_pairs_hook=_unique_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ItemContractError("Item command JSON is invalid.") from error
    return parse_item_command(value)


def parse_item_command(value: object) -> ItemCommand:
    source = _closed(
        value,
        {
            "contractVersion",
            "operation",
            "requestGlobalId",
            "attemptGlobalId",
            "attemptNumber",
            "targetIdempotencyKeyHash",
            "sourceHash",
            "actorUserId",
            "source",
            "intent",
            "expectedMappingVersion",
            "expectedTargetVersion",
        },
        "Item command",
    )
    if (
        source["contractVersion"] != CONTRACT_VERSION
        or source["operation"] != OPERATION
    ):
        raise ItemContractError("Item command contract is unsupported.")
    request_id = _uuid(source["requestGlobalId"], "requestGlobalId")
    attempt_id = _uuid(source["attemptGlobalId"], "attemptGlobalId")
    attempt_number = _positive(source["attemptNumber"], "attemptNumber")
    idempotency_hash = _hash(
        source["targetIdempotencyKeyHash"],
        "targetIdempotencyKeyHash",
    )
    source_hash = _hash(source["sourceHash"], "sourceHash")
    actor_user_id = _actor(source["actorUserId"], "actorUserId")
    intent = source["intent"]
    if intent not in {CREATE_INTENT, UPDATE_INTENT}:
        raise ItemContractError("Item command intent is unsupported.")
    expected_mapping_version = _nonnegative(
        source["expectedMappingVersion"],
        "expectedMappingVersion",
    )
    expected_target_version = _optional_text(
        source["expectedTargetVersion"],
        "expectedTargetVersion",
        140,
    )
    if intent == CREATE_INTENT and (
        expected_mapping_version != 0 or expected_target_version is not None
    ):
        raise ItemContractError("Item create expectation is invalid.")
    if intent == UPDATE_INTENT and (
        expected_mapping_version < 1 or expected_target_version is None
    ):
        raise ItemContractError("Item update expectation is invalid.")

    source_snapshot = _closed(
        source["source"],
        {
            "schemaVersion",
            "tenantId",
            "projectGlobalId",
            "engineeringItemId",
            "selectedPublishNodeGlobalId",
            "itemMaster",
            "occurrences",
            "streamKeyHash",
            "sourceHash",
        },
        "Item source",
    )
    if source_snapshot["schemaVersion"] != SOURCE_SCHEMA_VERSION:
        raise ItemContractError("Item source contract is unsupported.")
    tenant_id = _pattern(source_snapshot["tenantId"], _TENANT, "tenantId")
    project_id = _uuid(source_snapshot["projectGlobalId"], "projectGlobalId")
    engineering_id = _pattern(
        source_snapshot["engineeringItemId"],
        _ENGINEERING_ID,
        "engineeringItemId",
    )
    selected_node = _uuid(
        source_snapshot["selectedPublishNodeGlobalId"],
        "selectedPublishNodeGlobalId",
    )
    item_master = _closed(
        source_snapshot["itemMaster"],
        {"description", "engineeringUom", "attributes"},
        "Item master",
    )
    description = _text(item_master["description"], "description", 280)
    engineering_uom = _pattern(
        item_master["engineeringUom"],
        _UOM,
        "engineeringUom",
    )
    attributes = _string_map(item_master["attributes"], "attributes", maximum=64)
    occurrences = source_snapshot["occurrences"]
    if (
        isinstance(occurrences, (str, bytes))
        or not isinstance(occurrences, Sequence)
        or not 1 <= len(occurrences) <= 500
    ):
        raise ItemContractError("Item occurrences are invalid.")
    seen_nodes: set[str] = set()
    seen_lines: set[str] = set()
    for occurrence in occurrences:
        item = _closed(
            occurrence,
            {
                "publishNodeGlobalId",
                "lineGlobalId",
                "engineeringItemId",
                "description",
                "engineeringUom",
                "attributes",
                "lineHash",
                "nodeInputHash",
            },
            "Item occurrence",
        )
        node_id = _uuid(item["publishNodeGlobalId"], "occurrence.publishNodeGlobalId")
        line_id = _uuid(item["lineGlobalId"], "occurrence.lineGlobalId")
        if node_id in seen_nodes or line_id in seen_lines:
            raise ItemContractError("Item occurrence identities are duplicated.")
        seen_nodes.add(node_id)
        seen_lines.add(line_id)
        if (
            _pattern(
                item["engineeringItemId"],
                _ENGINEERING_ID,
                "occurrence.engineeringItemId",
            )
            != engineering_id
            or _text(item["description"], "occurrence.description", 280) != description
            or _pattern(item["engineeringUom"], _UOM, "occurrence.engineeringUom")
            != engineering_uom
            or _string_map(item["attributes"], "occurrence.attributes", maximum=64)
            != attributes
        ):
            raise ItemContractError("Item occurrences contain divergent master data.")
        _hash(item["lineHash"], "occurrence.lineHash")
        _hash(item["nodeInputHash"], "occurrence.nodeInputHash")
    if selected_node not in seen_nodes:
        raise ItemContractError("Selected Item occurrence is unavailable.")

    stream_hash = _hash(source_snapshot["streamKeyHash"], "streamKeyHash")
    expected_stream_hash = canonical_hash(
        {
            "schemaVersion": SOURCE_SCHEMA_VERSION,
            "tenantId": tenant_id,
            "projectGlobalId": project_id,
            "engineeringItemId": engineering_id,
        }
    )
    if stream_hash != expected_stream_hash:
        raise ItemContractError("Item stream key does not match its identity.")
    nested_source_hash = _hash(source_snapshot["sourceHash"], "source.sourceHash")
    source_payload = dict(source_snapshot)
    source_payload.pop("streamKeyHash")
    source_payload.pop("sourceHash")
    if (
        source_hash != nested_source_hash
        or canonical_hash(source_payload) != source_hash
    ):
        raise ItemContractError("Item source hash does not match its snapshot.")

    return ItemCommand(
        request_id,
        attempt_id,
        attempt_number,
        idempotency_hash,
        source_hash,
        stream_hash,
        actor_user_id,
        tenant_id,
        project_id,
        engineering_id,
        description,
        engineering_uom,
        attributes,
        intent,
        expected_mapping_version,
        expected_target_version,
        source,
    )


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ItemContractError("Item command JSON contains duplicate keys.")
        value[key] = item
    return value


def _closed(value: object, keys: set[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ItemContractError(f"{label} shape is invalid.")
    return value


def _uuid(value: object, label: str) -> str:
    try:
        parsed = UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise ItemContractError(f"{label} is invalid.") from error
    if parsed.int == 0 or str(parsed) != str(value).casefold():
        raise ItemContractError(f"{label} is invalid.")
    return str(parsed)


def _actor(value: object, label: str) -> str:
    actor = _text(value, label, 254)
    if (
        actor != actor.casefold()
        or _ACTOR.fullmatch(actor) is None
        or actor in {"guest", "administrator"}
    ):
        raise ItemContractError(f"{label} is invalid.")
    return actor


def _hash(value: object, label: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise ItemContractError(f"{label} is invalid.")
    return value


def _text(value: object, label: str, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
    ):
        raise ItemContractError(f"{label} is invalid.")
    return value


def _optional_text(value: object, label: str, maximum: int) -> str | None:
    return None if value is None else _text(value, label, maximum)


def _pattern(value: object, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ItemContractError(f"{label} is invalid.")
    return value


def _positive(value: object, label: str) -> int:
    if type(value) is not int or value < 1:
        raise ItemContractError(f"{label} is invalid.")
    return value


def _nonnegative(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ItemContractError(f"{label} is invalid.")
    return value


def _string_map(
    value: object,
    label: str,
    *,
    maximum: int,
) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, Mapping) or len(value) > min(maximum, 50):
        raise ItemContractError(f"{label} is invalid.")
    result: list[tuple[str, str]] = []
    for key, item in value.items():
        result.append(
            (
                _pattern(key, _ATTRIBUTE_KEY, f"{label} key"),
                _text(item, f"{label} value", 280),
            )
        )
    return tuple(sorted(result))
