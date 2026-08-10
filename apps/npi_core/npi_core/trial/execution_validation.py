from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from frappe import _

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.trial.execution_domain import TrialEvidenceRole


PREPARE_FIELDS = frozenset(
    {
        "expectedRoundOptimisticVersion",
        "references",
        "material",
        "parameterDefinitions",
        "reason",
    }
)
START_FIELDS = frozenset(
    {
        "expectedRoundOptimisticVersion",
        "expectedInputLockRevisionGlobalId",
        "expectedInputLockVersion",
        "resources",
        "material",
        "environment",
        "parameters",
        "operatorUserId",
        "executionStartedAt",
        "reason",
    }
)
ACTUAL_FIELDS = frozenset(
    {
        "expectedRoundOptimisticVersion",
        "expectedActualRevisionGlobalId",
        "expectedActualVersion",
        "resources",
        "material",
        "environment",
        "parameters",
        "operatorUserId",
        "executionStartedAt",
        "reason",
    }
)
CREATE_SAMPLE_FIELDS = frozenset(
    {
        "expectedRoundOptimisticVersion",
        "expectedInputLockRevisionGlobalId",
        "sample",
        "reason",
    }
)
REVISE_SAMPLE_FIELDS = frozenset(
    {
        "expectedRoundOptimisticVersion",
        "expectedRevisionGlobalId",
        "expectedSampleVersion",
        "sample",
        "reason",
    }
)
BIND_EVIDENCE_FIELDS = frozenset(
    {
        "expectedRoundOptimisticVersion",
        "role",
        "fileRevisionGlobalId",
        "expectedFileOptimisticVersion",
        "sampleBatchRevisionGlobalId",
        "expectedSampleVersion",
    }
)
UPLOAD_FIELDS = frozenset({"expectedRoundOptimisticVersion"})

_REFERENCE_FIELDS = frozenset(
    {"globalId", "kind", "expectedOptimisticVersion"}
)
_MATERIAL_FIELDS = frozenset(
    {
        "sourceSystem",
        "sourceObjectId",
        "lotBatchCode",
        "label",
        "color",
        "additive",
        "observedAt",
    }
)
_MATERIAL_REQUIRED = frozenset(
    {"sourceSystem", "sourceObjectId", "lotBatchCode", "label", "observedAt"}
)
_DEFINITION_FIELDS = frozenset(
    {
        "key",
        "category",
        "valueKind",
        "required",
        "unit",
        "targetValue",
        "lowerLimit",
        "upperLimit",
    }
)
_DEFINITION_REQUIRED = frozenset({"key", "category", "valueKind", "required"})
_RESOURCE_FIELDS = frozenset({"kind", "sourceSystem", "sourceObjectId", "label"})
_ENVIRONMENT_FIELDS = frozenset({"key", "value", "unit", "observedAt"})
_ENVIRONMENT_REQUIRED = frozenset({"key", "value", "observedAt"})
_PARAMETER_FIELDS = frozenset(
    {"definitionKey", "state", "value", "unit", "source", "observedAt"}
)
_SAMPLE_FIELDS = frozenset(
    {
        "label",
        "cavityGlobalIds",
        "quantity",
        "unit",
        "packaging",
        "destination",
        "feedbackText",
        "feedbackSource",
        "feedbackObservedAt",
    }
)
_SAMPLE_REQUIRED = frozenset(
    {"label", "cavityGlobalIds", "quantity", "unit", "packaging", "destination"}
)
_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")


def prepare_values(values: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "expected_round_optimistic_version": positive(
            values["expectedRoundOptimisticVersion"],
            "expectedRoundOptimisticVersion",
        ),
        "references": references(values["references"]),
        "material": material(values["material"]),
        "parameter_definitions": parameter_definitions(
            values["parameterDefinitions"]
        ),
        "reason": text(values["reason"], "reason", 500),
    }


def start_values(values: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "expected_round_optimistic_version": positive(
            values["expectedRoundOptimisticVersion"],
            "expectedRoundOptimisticVersion",
        ),
        "expected_input_lock_revision_global_id": uuid_value(
            values["expectedInputLockRevisionGlobalId"],
            "expectedInputLockRevisionGlobalId",
        ),
        "expected_input_lock_version": positive(
            values["expectedInputLockVersion"],
            "expectedInputLockVersion",
        ),
        **actual_context(values),
    }


def actual_values(values: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "expected_round_optimistic_version": positive(
            values["expectedRoundOptimisticVersion"],
            "expectedRoundOptimisticVersion",
        ),
        "expected_actual_revision_global_id": uuid_value(
            values["expectedActualRevisionGlobalId"],
            "expectedActualRevisionGlobalId",
        ),
        "expected_actual_version": positive(
            values["expectedActualVersion"],
            "expectedActualVersion",
        ),
        **actual_context(values),
    }


def create_sample_values(values: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "expected_round_optimistic_version": positive(
            values["expectedRoundOptimisticVersion"],
            "expectedRoundOptimisticVersion",
        ),
        "expected_input_lock_revision_global_id": uuid_value(
            values["expectedInputLockRevisionGlobalId"],
            "expectedInputLockRevisionGlobalId",
        ),
        "sample": sample(values["sample"]),
        "reason": text(values["reason"], "reason", 500),
    }


def revise_sample_values(values: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "expected_round_optimistic_version": positive(
            values["expectedRoundOptimisticVersion"],
            "expectedRoundOptimisticVersion",
        ),
        "expected_revision_global_id": uuid_value(
            values["expectedRevisionGlobalId"],
            "expectedRevisionGlobalId",
        ),
        "expected_sample_version": positive(
            values["expectedSampleVersion"],
            "expectedSampleVersion",
        ),
        "sample": sample(values["sample"]),
        "reason": text(values["reason"], "reason", 500),
    }


def bind_evidence_values(values: Mapping[str, Any]) -> dict[str, Any]:
    sample_id = optional_uuid(
        values.get("sampleBatchRevisionGlobalId"),
        "sampleBatchRevisionGlobalId",
    )
    sample_version = optional_positive(
        values.get("expectedSampleVersion"),
        "expectedSampleVersion",
    )
    if (sample_id is None) != (sample_version is None):
        raise field(
            "sampleBatchRevisionGlobalId",
            _("Select one complete Sample Batch revision."),
        )
    try:
        role = TrialEvidenceRole(str(values["role"]))
    except ValueError as error:
        raise field("role", _("Select a supported value.")) from error
    return {
        "expected_round_optimistic_version": positive(
            values["expectedRoundOptimisticVersion"],
            "expectedRoundOptimisticVersion",
        ),
        "role": role,
        "file_revision_global_id": uuid_value(
            values["fileRevisionGlobalId"],
            "fileRevisionGlobalId",
        ),
        "expected_file_optimistic_version": positive(
            values["expectedFileOptimisticVersion"],
            "expectedFileOptimisticVersion",
        ),
        "sample_batch_revision_global_id": sample_id,
        "expected_sample_version": sample_version,
    }


def actual_context(values: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "resources": actual_resources(values["resources"]),
        "material": material(values["material"]),
        "environment": environment(values["environment"]),
        "parameters": parameter_observations(values["parameters"]),
        "operator_user_id": text(values["operatorUserId"], "operatorUserId", 254),
        "execution_started_at": datetime_value(
            values["executionStartedAt"],
            "executionStartedAt",
        ),
        "reason": text(values["reason"], "reason", 500),
    }


def references(value: object) -> list[dict[str, Any]]:
    result = []
    for index, item in enumerate(array(value, "references", 8, 100)):
        path = f"references[{index}]"
        record = closed(item, path, _REFERENCE_FIELDS, _REFERENCE_FIELDS)
        result.append(
            {
                "globalId": uuid_value(record["globalId"], f"{path}.globalId"),
                "kind": choice(
                    record["kind"],
                    f"{path}.kind",
                    {
                        "design_baseline",
                        "part_revision",
                        "tooling_revision",
                        "tooling_set",
                        "tooling_set_binding",
                        "cavity",
                        "process_chain",
                        "inspection_document",
                    },
                ),
                "expectedOptimisticVersion": positive(
                    record["expectedOptimisticVersion"],
                    f"{path}.expectedOptimisticVersion",
                ),
            }
        )
    identities = {(item["kind"], item["globalId"]) for item in result}
    if len(identities) != len(result):
        raise field("references", _("Locked Trial references must be unique."))
    return result


def material(value: object) -> dict[str, Any]:
    record = closed(value, "material", _MATERIAL_FIELDS, _MATERIAL_REQUIRED)
    return {
        "sourceSystem": choice(
            record["sourceSystem"], "material.sourceSystem", {"NPI_ONE", "ERPNEXT"}
        ),
        "sourceObjectId": key(record["sourceObjectId"], "material.sourceObjectId"),
        "lotBatchCode": key(record["lotBatchCode"], "material.lotBatchCode"),
        "label": text(record["label"], "material.label", 140),
        "color": optional_text(record.get("color"), "material.color", 80),
        "additive": optional_text(record.get("additive"), "material.additive", 140),
        "observedAt": datetime_value(record["observedAt"], "material.observedAt"),
    }


def parameter_definitions(value: object) -> list[dict[str, Any]]:
    result = []
    for index, item in enumerate(array(value, "parameterDefinitions", 1, 250)):
        path = f"parameterDefinitions[{index}]"
        record = closed(item, path, _DEFINITION_FIELDS, _DEFINITION_REQUIRED)
        result.append(
            {
                "key": key(record["key"], f"{path}.key"),
                "category": text(record["category"], f"{path}.category", 80),
                "valueKind": choice(
                    record["valueKind"],
                    f"{path}.valueKind",
                    {"decimal", "integer", "text", "boolean"},
                ),
                "required": boolean(record["required"], f"{path}.required"),
                "unit": optional_text(record.get("unit"), f"{path}.unit", 32),
                "targetValue": optional_text(
                    record.get("targetValue"), f"{path}.targetValue", 280
                ),
                "lowerLimit": optional_text(
                    record.get("lowerLimit"), f"{path}.lowerLimit", 64
                ),
                "upperLimit": optional_text(
                    record.get("upperLimit"), f"{path}.upperLimit", 64
                ),
            }
        )
    if len({item["key"] for item in result}) != len(result):
        raise field("parameterDefinitions", _("Trial parameter keys must be unique."))
    return result


def actual_resources(value: object) -> list[dict[str, Any]]:
    result = []
    for index, item in enumerate(array(value, "resources", 1, 25)):
        path = f"resources[{index}]"
        record = closed(item, path, _RESOURCE_FIELDS, _RESOURCE_FIELDS)
        result.append(
            {
                "kind": choice(
                    record["kind"], path + ".kind", {"machine", "auxiliary_equipment"}
                ),
                "sourceSystem": choice(
                    record["sourceSystem"], path + ".sourceSystem", {"NPI_ONE", "ERPNEXT"}
                ),
                "sourceObjectId": key(record["sourceObjectId"], path + ".sourceObjectId"),
                "label": text(record["label"], path + ".label", 140),
            }
        )
    return result


def environment(value: object) -> list[dict[str, Any]]:
    result = []
    for index, item in enumerate(array(value, "environment", 0, 50)):
        path = f"environment[{index}]"
        record = closed(item, path, _ENVIRONMENT_FIELDS, _ENVIRONMENT_REQUIRED)
        result.append(
            {
                "key": key(record["key"], path + ".key"),
                "value": text(record["value"], path + ".value", 140),
                "unit": optional_text(record.get("unit"), path + ".unit", 32),
                "observedAt": datetime_value(record["observedAt"], path + ".observedAt"),
            }
        )
    return result


def parameter_observations(value: object) -> list[dict[str, Any]]:
    result = []
    for index, item in enumerate(array(value, "parameters", 1, 250)):
        path = f"parameters[{index}]"
        record = closed(
            item,
            path,
            _PARAMETER_FIELDS,
            frozenset({"definitionKey", "state"}),
        )
        state = choice(
            record["state"], path + ".state", {"measured", "not_measured"}
        )
        measured = state == "measured"
        required_values = ("value", "source", "observedAt")
        if measured and any(record.get(name) is None for name in required_values):
            raise field(path, _("Enter one complete measured parameter observation."))
        if not measured and any(
            record.get(name) is not None
            for name in ("value", "unit", "source", "observedAt")
        ):
            raise field(
                path,
                _("A not-measured parameter cannot contain a measured value."),
            )
        result.append(
            {
                "definitionKey": key(record["definitionKey"], path + ".definitionKey"),
                "state": state,
                "value": optional_text(record.get("value"), path + ".value", 280),
                "unit": optional_text(record.get("unit"), path + ".unit", 32),
                "source": (
                    choice(record.get("source"), path + ".source", {"manual"})
                    if measured
                    else None
                ),
                "observedAt": (
                    datetime_value(record.get("observedAt"), path + ".observedAt")
                    if measured
                    else None
                ),
            }
        )
    return result


def sample(value: object) -> dict[str, Any]:
    record = closed(value, "sample", _SAMPLE_FIELDS, _SAMPLE_REQUIRED)
    feedback_values = (
        record.get("feedbackText"),
        record.get("feedbackSource"),
        record.get("feedbackObservedAt"),
    )
    if any(item is not None for item in feedback_values) and not all(
        item is not None for item in feedback_values
    ):
        raise field("sample.feedbackText", _("Enter one complete feedback observation."))
    return {
        "label": key(record["label"], "sample.label"),
        "cavityGlobalIds": uuid_array(
            record["cavityGlobalIds"], "sample.cavityGlobalIds", 128
        ),
        "quantity": positive(record["quantity"], "sample.quantity"),
        "unit": text(record["unit"], "sample.unit", 32),
        "packaging": text(record["packaging"], "sample.packaging", 280),
        "destination": text(record["destination"], "sample.destination", 280),
        "feedbackText": optional_text(
            record.get("feedbackText"), "sample.feedbackText", 4000
        ),
        "feedbackSource": optional_text(
            record.get("feedbackSource"), "sample.feedbackSource", 140
        ),
        "feedbackObservedAt": (
            datetime_value(
                record.get("feedbackObservedAt"), "sample.feedbackObservedAt"
            )
            if record.get("feedbackObservedAt") is not None
            else None
        ),
    }


def closed(
    value: object,
    path: str,
    allowed: frozenset[str],
    required: frozenset[str],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise field(path, _("Enter a valid object."))
    unexpected = sorted(set(value) - allowed)
    if unexpected:
        raise RequestValidationFailed(
            [
                {"path": f"{path}.{name}", "message": _("This field is not allowed.")}
                for name in unexpected
            ]
        )
    missing = sorted(required - set(value))
    if missing:
        raise RequestValidationFailed(
            [
                {"path": f"{path}.{name}", "message": _("This field is required.")}
                for name in missing
            ]
        )
    return dict(value)


def array(value: object, path: str, minimum: int, maximum: int) -> list[Any]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or not minimum <= len(value) <= maximum
    ):
        raise field(path, _("Enter a valid bounded list."))
    return list(value)


def uuid_array(value: object, path: str, maximum: int) -> tuple[UUID, ...]:
    result = tuple(
        uuid_value(item, f"{path}[{index}]")
        for index, item in enumerate(array(value, path, 1, maximum))
    )
    if len(result) != len(set(result)):
        raise field(path, _("Global IDs must be unique."))
    return result


def uuid_value(value: object, path: str) -> UUID:
    try:
        parsed = UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise field(path, _("Enter a valid global ID.")) from error
    if str(parsed) != str(value).casefold():
        raise field(path, _("Enter a valid global ID."))
    return parsed


def optional_uuid(value: object, path: str) -> UUID | None:
    return None if value in (None, "") else uuid_value(value, path)


def positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise field(path, _("Enter a positive integer."))
    return value


def optional_positive(value: object, path: str) -> int | None:
    return None if value in (None, "") else positive(value, path)


def boolean(value: object, path: str) -> bool:
    if type(value) is not bool:
        raise field(path, _("Select true or false."))
    return value


def choice(value: object, path: str, values: set[str]) -> str:
    if not isinstance(value, str) or value not in values:
        raise field(path, _("Select a supported value."))
    return value


def key(value: object, path: str) -> str:
    result = text(value, path, 128)
    if _KEY.fullmatch(result) is None:
        raise field(path, _("Enter a valid value."))
    return result


def text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise field(path, _("Enter a value."))
    result = value.strip()
    if len(result) > maximum:
        raise field(path, _("Enter a shorter value."))
    return result


def optional_text(value: object, path: str, maximum: int) -> str | None:
    return None if value is None else text(value, path, maximum)


def datetime_value(value: object, path: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise field(path, _("Enter a valid date and time.")) from error
    else:
        raise field(path, _("Enter a valid date and time."))
    if parsed.tzinfo is None:
        raise field(path, _("Enter a valid date and time."))
    return parsed.astimezone(UTC)


def field(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
