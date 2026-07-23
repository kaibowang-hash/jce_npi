from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "npi-api.openapi.yaml"
CONTRACT = CONTRACT_PATH.read_text(encoding="utf-8")
LINES = CONTRACT.splitlines()
OWNERSHIP = (ROOT / "contracts" / "data-ownership.yaml").read_text(
    encoding="utf-8"
)


def _indented_block(marker: str) -> str:
    """Return one YAML mapping block without requiring a YAML dependency."""
    matches = [index for index, line in enumerate(LINES) if line == marker]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {marker!r} block, found {len(matches)}")
    start = matches[0]
    indent = len(marker) - len(marker.lstrip())
    end = len(LINES)
    for index in range(start + 1, len(LINES)):
        line = LINES[index]
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            end = index
            break
    return "\n".join(LINES[start:end])


def _schema(name: str) -> str:
    return _indented_block(f"    {name}:")


def _component(section: str, name: str) -> str:
    section_block = _indented_block(f"  {section}:")
    marker = f"    {name}:"
    if marker not in section_block.splitlines():
        raise AssertionError(f"Missing components.{section}.{name}")
    return _indented_block(marker)


def _direct_component_names(section: str) -> set[str]:
    block = _indented_block(f"  {section}:")
    return set(re.findall(r"^    ([A-Za-z][A-Za-z0-9_.-]*):$", block, re.MULTILINE))


def _required_fields(schema_name: str) -> tuple[str, ...]:
    match = re.search(
        r"^      required:\s*\[([^]]*)\]",
        _schema(schema_name),
        re.MULTILINE,
    )
    if match is None:
        raise AssertionError(f"{schema_name} needs a flow-style required list")
    return tuple(item.strip() for item in match.group(1).split(",") if item.strip())


def _property_names(schema_name: str) -> set[str]:
    return set(
        re.findall(
            r"^        ([A-Za-z][A-Za-z0-9]*):",
            _schema(schema_name),
            re.MULTILINE,
        )
    )


def _field(schema_name: str, field_name: str) -> str:
    schema_lines = _schema(schema_name).splitlines()
    marker = f"        {field_name}:"
    starts = [
        index
        for index, line in enumerate(schema_lines)
        if line == marker or line.startswith(f"{marker} ")
    ]
    if len(starts) != 1:
        raise AssertionError(
            f"Expected one {schema_name}.{field_name} field, found {len(starts)}"
        )
    start = starts[0]
    end = len(schema_lines)
    for index in range(start + 1, len(schema_lines)):
        line = schema_lines[index]
        if line.strip() and len(line) - len(line.lstrip()) <= 8:
            end = index
            break
    return "\n".join(schema_lines[start:end])


def _flow_enum(block: str) -> tuple[str, ...]:
    match = re.search(r"enum: \[([^]]*)\]", block)
    if match is None:
        raise AssertionError("Expected a flow-style enum")
    return tuple(item.strip() for item in match.group(1).split(","))


def _response_statuses(path_block: str) -> set[str]:
    statuses: set[str] = set()
    for quoted, default in re.findall(
        r'^        (?:"([0-9]{3})"|(default)):', path_block, re.MULTILINE
    ):
        statuses.add(quoted or default)
    return statuses


class Phase4ProjectContractTests(unittest.TestCase):
    def test_engineering_project_business_code_has_one_owner(self) -> None:
        self.assertIn(
            "business_code: {owner: NPI_ONE, editable_in: [NPI_ONE]",
            OWNERSHIP,
        )
        self.assertNotIn("project_code:", OWNERSHIP)

    def test_project_command_and_query_are_explicit_business_operations(self) -> None:
        create = _indented_block("  /projects:")
        cockpit = _indented_block("  /projects/{projectId}/cockpit:")

        self.assertIn("operationId: createProjectDraft", create)
        self.assertIn("x-required-roles: [System Manager]", create)
        self.assertIn('$ref: "#/components/parameters/IdempotencyKey"', create)
        self.assertIn('$ref: "#/components/parameters/RequestId"', create)
        self.assertIn('$ref: "#/components/parameters/CsrfToken"', create)
        self.assertIn('$ref: "#/components/schemas/CreateProjectDraft"', create)
        self.assertIn('$ref: "#/components/schemas/ProjectCockpit"', create)
        self.assertIn("Idempotency-Replayed:", create)
        self.assertIn("configured Site tenant exactly matches tenantId", create)

        self.assertIn("operationId: getProjectCockpit", cockpit)
        self.assertIn('$ref: "#/components/parameters/ProjectId"', cockpit)
        self.assertIn('$ref: "#/components/parameters/RequestId"', cockpit)
        self.assertIn('$ref: "#/components/schemas/ProjectCockpit"', cockpit)
        self.assertIn("immutable Project global_id", cockpit)
        self.assertIn("unauthorized Project both return the", cockpit)
        self.assertIn("configured Site tenant", cockpit)
        self.assertNotIn('"403":', cockpit)

    def test_project_problem_statuses_are_complete_and_non_leaking(self) -> None:
        create = _indented_block("  /projects:")
        cockpit = _indented_block("  /projects/{projectId}/cockpit:")
        self.assertEqual(
            _response_statuses(create),
            {"201", "400", "401", "403", "409", "422", "500", "503", "default"},
        )
        self.assertEqual(
            _response_statuses(cockpit),
            {"200", "400", "401", "404", "422", "500", "503", "default"},
        )

        response_names = {
            "BadRequest",
            "AuthenticationError",
            "PermissionError",
            "NotFoundError",
            "ProjectConflict",
            "ProjectValidationError",
            "InternalError",
            "ServiceUnavailable",
            "ProjectError",
        }
        for response_name in response_names:
            with self.subTest(response=response_name):
                response = _component("responses", response_name)
                self.assertIn("X-Request-ID:", response)
                self.assertIn("X-Trace-ID:", response)
                self.assertIn("application/problem+json:", response)
                self.assertIn('$ref: "#/components/schemas/ProblemDetails"', response)

    def test_create_schema_is_closed_and_matches_the_frozen_command(self) -> None:
        expected = (
            "tenantId",
            "businessCode",
            "title",
            "projectType",
            "ownerUserId",
            "targetSop",
            "templateGlobalId",
            "templateVersion",
            "expectedVersion",
            "references",
        )
        self.assertEqual(_required_fields("CreateProjectDraft"), expected)
        self.assertEqual(_property_names("CreateProjectDraft"), set(expected))
        self.assertIn("additionalProperties: false", _schema("CreateProjectDraft"))
        self.assertIn("format: email", _field("CreateProjectDraft", "ownerUserId"))
        self.assertIn("format: date", _field("CreateProjectDraft", "targetSop"))
        self.assertIn("format: uuid", _field("CreateProjectDraft", "templateGlobalId"))
        self.assertIn("minimum: 1", _field("CreateProjectDraft", "templateVersion"))
        self.assertIn("minimum: 1", _field("CreateProjectDraft", "expectedVersion"))
        self.assertIn("maxLength: 128", _field("CreateProjectDraft", "tenantId"))
        self.assertIn("maxLength: 64", _field("CreateProjectDraft", "businessCode"))

    def test_typed_reference_is_closed_and_does_not_accept_null_identity(self) -> None:
        reference = _schema("ProjectObjectReference")
        self.assertEqual(
            _required_fields("ProjectObjectReference"),
            ("type", "sourceSystem", "sourceObjectId"),
        )
        self.assertEqual(
            _property_names("ProjectObjectReference"),
            {"type", "sourceSystem", "sourceObjectId", "globalId"},
        )
        self.assertIn("additionalProperties: false", reference)
        self.assertEqual(
            _flow_enum(_field("ProjectObjectReference", "type")),
            ("customer", "product", "part", "tooling", "order"),
        )
        self.assertEqual(
            _flow_enum(_field("ProjectObjectReference", "sourceSystem")),
            ("NPI_ONE", "ERPNEXT"),
        )
        global_id = _field("ProjectObjectReference", "globalId")
        self.assertIn("format: uuid", global_id)
        self.assertNotIn("null", global_id)
        self.assertNotIn("nullable", global_id)

    def test_cockpit_response_is_exact_closed_and_contains_no_future_metrics(self) -> None:
        exact_properties = {
            "ProjectCockpit": {"project", "templateRef", "references", "gates", "permissions"},
            "ProjectCockpitProject": {
                "globalId",
                "businessCode",
                "title",
                "projectType",
                "state",
                "version",
                "tenantId",
                "ownerUserId",
                "targetSop",
                "createdAt",
                "lastChangedAt",
                "lastChangedBy",
                "source",
            },
            "ProjectTemplateReference": {"globalId", "code", "version", "snapshotHash"},
            "GateShell": {"globalId", "key", "title", "sequence", "state", "version"},
            "ProjectPermissions": {"canView", "canContribute", "canAdminister"},
            "ProjectSourceStatus": {"sourceSystem", "editableIn", "syncState"},
        }
        for schema_name, properties in exact_properties.items():
            with self.subTest(schema=schema_name):
                self.assertIn("additionalProperties: false", _schema(schema_name))
                self.assertEqual(_property_names(schema_name), properties)
                self.assertEqual(set(_required_fields(schema_name)), properties)

        cockpit = _schema("ProjectCockpit")
        self.assertIn("x-order-by: sequence", _field("ProjectCockpit", "gates"))
        for forbidden in ("metrics", "nextAction", "objectTree", "actualCost", "budget"):
            self.assertNotIn(forbidden, cockpit)
        self.assertNotIn("replayed", cockpit)
        self.assertNotIn("traceId", cockpit)

    def test_identity_date_audit_template_and_gate_constraints_are_typed(self) -> None:
        self.assertEqual(
            _flow_enum(_schema("ProjectType")),
            ("customer_owned_tool", "new_tool", "tool_change"),
        )
        self.assertIn("format: uuid", _component("parameters", "ProjectId"))
        self.assertIn("format: uuid", _component("parameters", "RequestId"))
        self.assertIn("maxLength: 255", _component("parameters", "IdempotencyKey"))
        self.assertIn("^[!-~]{16,255}$", _component("parameters", "IdempotencyKey"))

        for schema_name, field_name in (
            ("ProjectCockpitProject", "globalId"),
            ("ProjectTemplateReference", "globalId"),
            ("GateShell", "globalId"),
        ):
            with self.subTest(schema=schema_name, field=field_name):
                self.assertIn("format: uuid", _field(schema_name, field_name))
        self.assertIn("format: date", _field("ProjectCockpitProject", "targetSop"))
        self.assertIn("format: date-time", _field("ProjectCockpitProject", "createdAt"))
        self.assertIn("format: date-time", _field("ProjectCockpitProject", "lastChangedAt"))
        self.assertIn("^[a-f0-9]{64}$", _field("ProjectTemplateReference", "snapshotHash"))
        self.assertIn("minimum: 1", _field("GateShell", "sequence"))
        self.assertEqual(_flow_enum(_field("GateShell", "state")), ("not_started",))
        self.assertEqual(_flow_enum(_field("ProjectCockpitProject", "state")), ("draft",))
        self.assertIn("const: true", _field("ProjectPermissions", "canView"))

    def test_domain_work_kind_and_my_work_projection_remain_distinct(self) -> None:
        self.assertNotIn("WorkItem", _direct_component_names("schemas"))
        self.assertNotIn("DomainWorkItem", _direct_component_names("schemas"))
        self.assertEqual(
            _flow_enum(_schema("DomainWorkItemKind")),
            ("risk", "issue", "action", "decision_request"),
        )
        self.assertEqual(
            _flow_enum(_schema("MyWorkCategory")),
            ("task", "approval", "blocker", "risk", "issue", "decision", "integration"),
        )
        projection = _schema("MyWorkItemProjection")
        self.assertIn("additionalProperties: false", projection)
        self.assertIn('$ref: "#/components/schemas/MyWorkCategory"', projection)
        self.assertIn('$ref: "#/components/schemas/DomainWorkItemKind"', projection)
        self.assertIn(
            '$ref: "#/components/schemas/MyWorkItemProjection"',
            _schema("WorkPage"),
        )
        paths = _indented_block("paths:")
        self.assertNotRegex(paths, r"(?m)^  /(?:domain-)?work-items(?:[/:{]|$)")
        self.assertNotRegex(
            paths,
            r"(?mi)^  /projects[^:]*:(?:sync|execute|export-to-erpnext)(?:$|/)",
        )

    def test_problem_details_and_nested_field_errors_are_closed(self) -> None:
        problem = _schema("ProblemDetails")
        self.assertIn("additionalProperties: false", problem)
        self.assertEqual(
            set(_required_fields("ProblemDetails")),
            {"type", "title", "status", "code", "traceId", "retryable"},
        )
        self.assertIn("minimum: 400", _field("ProblemDetails", "status"))
        self.assertIn("maximum: 599", _field("ProblemDetails", "status"))
        field_errors = _field("ProblemDetails", "fieldErrors")
        self.assertIn("additionalProperties: false", field_errors)
        self.assertIn("required: [path, message]", field_errors)

    def test_operation_ids_and_all_internal_component_references_resolve(self) -> None:
        operation_ids = re.findall(
            r"^\s+operationId:\s*([A-Za-z][A-Za-z0-9_.-]*)\s*$",
            CONTRACT,
            re.MULTILINE,
        )
        self.assertTrue(operation_ids)
        self.assertEqual(len(operation_ids), len(set(operation_ids)))

        definitions = {
            section: _direct_component_names(section)
            for section in ("schemas", "parameters", "responses")
        }
        references = re.findall(
            r'\$ref:\s*(?:\{\s*)?["\']?#/components/(schemas|parameters|responses)/'
            r'([A-Za-z][A-Za-z0-9_.-]*)',
            CONTRACT,
        )
        self.assertTrue(references)
        self.assertEqual(len(references), len(re.findall(r"\$ref:", CONTRACT)))
        unresolved = sorted(
            f"{section}/{name}"
            for section, name in references
            if name not in definitions[section]
        )
        self.assertEqual(unresolved, [])


if __name__ == "__main__":
    unittest.main()
