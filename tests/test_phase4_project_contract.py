from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "npi-api.openapi.yaml"
CONTRACT = CONTRACT_PATH.read_text(encoding="utf-8")
LINES = CONTRACT.splitlines()
POLICY_LABEL_SOURCES_PATH = (
    ROOT
    / "apps"
    / "npi_core"
    / "npi_core"
    / "project_work"
    / "policy_label_sources.json"
)
POLICY_LABEL_SOURCE_REGISTRY = json.loads(
    POLICY_LABEL_SOURCES_PATH.read_text(encoding="utf-8")
)
POLICY_LABEL_SOURCES = tuple(POLICY_LABEL_SOURCE_REGISTRY["labelSources"])
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


def _policy_label_source_fields() -> tuple[tuple[str, int, str], ...]:
    fields: list[tuple[str, int, str]] = []
    field_pattern = re.compile(
        r"^(?P<indent>[ ]+)"
        r"(?P<name>statusLabelSource|stateLabelSource):(?:[ ].*)?$"
    )
    for start, line in enumerate(LINES):
        match = field_pattern.fullmatch(line)
        if match is None:
            continue
        indent = len(match.group("indent"))
        end = len(LINES)
        for index in range(start + 1, len(LINES)):
            candidate = LINES[index]
            if (
                candidate.strip()
                and len(candidate) - len(candidate.lstrip()) <= indent
            ):
                end = index
                break
        fields.append(
            (
                match.group("name"),
                start + 1,
                "\n".join(LINES[start:end]),
            )
        )
    return tuple(fields)


def _response_statuses(path_block: str) -> set[str]:
    statuses: set[str] = set()
    for quoted, default in re.findall(
        r'^        (?:"([0-9]{3})"|(default)):', path_block, re.MULTILINE
    ):
        statuses.add(quoted or default)
    return statuses


def _operation(path_marker: str, method: str) -> str:
    path_block = _indented_block(path_marker)
    lines = path_block.splitlines()
    marker = f"    {method}:"
    starts = [index for index, line in enumerate(lines) if line == marker]
    if len(starts) != 1:
        raise AssertionError(
            f"Expected one {method!r} operation in {path_marker!r}, found {len(starts)}"
        )
    start = starts[0]
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.strip() and len(line) - len(line.lstrip()) <= 4:
            end = index
            break
    return "\n".join(lines[start:end])


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
            ("customer", "factory", "product", "part", "tooling", "order"),
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
        self.assertIn("DomainWorkItem", _direct_component_names("schemas"))
        self.assertIn("DomainWorkItemPage", _direct_component_names("schemas"))
        self.assertEqual(
            _flow_enum(_schema("DomainWorkItemKind")),
            ("risk", "issue", "action", "decision_request"),
        )
        self.assertEqual(
            _flow_enum(_schema("MyWorkCategory")),
            ("task", "approval", "blocker", "risk", "issue", "decision"),
        )
        self.assertEqual(
            _flow_enum(_schema("MyWorkSourceType")),
            (
                "domain_work_item",
                "gate_review_assignment",
                "gate_review_invalidation",
            ),
        )
        projection = _schema("MyWorkItemProjection")
        self.assertIn("additionalProperties: false", projection)
        self.assertIn('$ref: "#/components/schemas/MyWorkCategory"', projection)
        self.assertEqual(
            set(_required_fields("MyWorkItemProjection")),
            {
                "id",
                "category",
                "title",
                "project",
                "context",
                "source",
                "why",
                "status",
                "dueAt",
                "dueState",
                "priority",
                "blocking",
                "action",
                "target",
                "sourceStatus",
            },
        )
        self.assertEqual(
            _flow_enum(_field("MyWorkItemProjection", "dueState")),
            ("overdue", "today", "upcoming", "unscheduled"),
        )
        self.assertEqual(
            set(_required_fields("WorkPage")),
            {
                "asOf",
                "timeZone",
                "projectOptions",
                "items",
                "nextCursor",
                "counts",
            },
        )
        self.assertIn(
            '$ref: "#/components/schemas/MyWorkProject"',
            _field("WorkPage", "projectOptions"),
        )
        self.assertEqual(
            set(_required_fields("MyWorkCounts")),
            {
                "all",
                "today",
                "overdue",
                "approvals",
                "blockers",
                "waiting",
                "integration",
            },
        )
        self.assertIn(
            '$ref: "#/components/schemas/UnavailableMyWorkCount"',
            _field("MyWorkCounts", "integration"),
        )
        self.assertIn(
            "const: source_not_available",
            _schema("UnavailableMyWorkCount"),
        )
        self.assertIn(
            '$ref: "#/components/schemas/MyWorkItemProjection"',
            _schema("WorkPage"),
        )
        paths = _indented_block("paths:")
        my_work_path = _indented_block("  /me/work:")
        self.assertRegex(
            my_work_path,
            r"enum:\s*\[all, today, overdue, approvals, blockers, waiting, integration\]",
        )
        for parameter in (
            "projectId",
            "priorityScheme",
            "priorityValue",
            "search",
            "cursor",
            "limit",
        ):
            self.assertIn(f"name: {parameter}", my_work_path)
        self.assertIn("actor-bound HMAC-SHA256", my_work_path)
        self.assertIn("maximum: 100", my_work_path)
        self.assertIn("  /projects/{projectId}/domain-work-items:", paths)
        self.assertNotRegex(paths, r"(?m)^  /(?:domain-)?work-items(?:[/:{]|$)")
        self.assertNotIn(
            '$ref: "#/components/schemas/MyWorkItemProjection"',
            _schema("DomainWorkItem"),
        )
        self.assertNotIn(
            '$ref: "#/components/schemas/DomainWorkItem"',
            _schema("MyWorkItemProjection"),
        )
        self.assertNotRegex(
            paths,
            r"(?mi)^  /projects[^:]*:(?:sync|execute|export-to-erpnext)(?:$|/)",
        )

    def test_project_work_endpoints_are_explicit_authorized_and_retry_safe(self) -> None:
        expected_commands = {
            "  /projects/{projectId}:configure-team:": (
                "configureProjectTeam",
                "ConfigureProjectTeam",
                "200",
                "project.team.configure",
            ),
            "  /projects/{projectId}:apply-work-plan:": (
                "applyProjectWorkPlan",
                "ApplyProjectWorkPlan",
                "200",
                "project.work_plan.apply",
            ),
            "  /projects/{projectId}:capture-plan-baseline:": (
                "captureProjectPlanBaseline",
                "CaptureProjectPlanBaseline",
                "201",
                "project.plan_baseline.capture",
            ),
        }
        command_statuses = {
            "200",
            "400",
            "401",
            "403",
            "404",
            "409",
            "422",
            "500",
            "503",
            "default",
        }
        for marker, (
            operation_id,
            schema_name,
            success_status,
            audit_operation,
        ) in expected_commands.items():
            with self.subTest(path=marker):
                operation = _operation(marker, "post")
                self.assertIn(f"operationId: {operation_id}", operation)
                self.assertIn("x-required-roles: [System Manager]", operation)
                self.assertIn("x-transaction-boundary: project-root", operation)
                self.assertIn(
                    f"x-audit-operation: {audit_operation}",
                    operation,
                )
                for parameter in (
                    "ProjectId",
                    "IdempotencyKey",
                    "RequestId",
                    "CsrfToken",
                ):
                    self.assertIn(
                        f'$ref: "#/components/parameters/{parameter}"',
                        operation,
                    )
                self.assertIn(
                    f'$ref: "#/components/schemas/{schema_name}"',
                    operation,
                )
                self.assertIn("Idempotency-Replayed:", operation)
                expected_statuses = set(command_statuses)
                expected_statuses.discard("200")
                expected_statuses.add(success_status)
                self.assertEqual(_response_statuses(operation), expected_statuses)
                self.assertIn(f'"{success_status}":', operation)

        collection_marker = "  /projects/{projectId}/domain-work-items:"
        create = _operation(collection_marker, "post")
        self.assertIn("operationId: createProjectDomainWorkItem", create)
        self.assertIn("x-required-roles: [System Manager]", create)
        self.assertIn("x-transaction-boundary: project-root", create)
        self.assertIn(
            "x-audit-operation: project.domain_work_item.create",
            create,
        )
        for parameter in ("ProjectId", "IdempotencyKey", "RequestId", "CsrfToken"):
            self.assertIn(
                f'$ref: "#/components/parameters/{parameter}"',
                create,
            )
        self.assertIn(
            '$ref: "#/components/schemas/CreateDomainWorkItem"',
            create,
        )
        self.assertIn('$ref: "#/components/schemas/DomainWorkItem"', create)
        self.assertIn("Idempotency-Replayed:", create)
        self.assertEqual(
            _response_statuses(create),
            {
                "201",
                "400",
                "401",
                "403",
                "404",
                "409",
                "422",
                "500",
                "503",
                "default",
            },
        )

        context = _operation("  /projects/{projectId}/work-context:", "get")
        self.assertIn("operationId: getProjectWorkContext", context)
        self.assertIn('$ref: "#/components/parameters/ProjectId"', context)
        self.assertIn('$ref: "#/components/parameters/RequestId"', context)
        self.assertIn(
            '$ref: "#/components/schemas/ProjectWorkContext"',
            context,
        )
        self.assertIn("unauthorized, and tenant-mismatched Projects return the same", context)
        self.assertNotIn('"403":', context)
        self.assertEqual(
            _response_statuses(context),
            {"200", "400", "401", "404", "422", "500", "503", "default"},
        )

    def test_domain_work_query_filters_are_bounded_and_do_not_expand_access(self) -> None:
        query = _operation("  /projects/{projectId}/domain-work-items:", "get")
        self.assertIn("operationId: listProjectDomainWorkItems", query)
        self.assertIn('$ref: "#/components/parameters/ProjectId"', query)
        self.assertIn('$ref: "#/components/parameters/RequestId"', query)
        self.assertIn("mandatory Project filter", query)
        self.assertIn("never expand authorization", query)
        self.assertIn("workItemId exact-target mode", query)
        self.assertIn("only after Project authorization", query)
        self.assertIn("cannot be combined with collection filters", query)
        self.assertIn("absent, cross-Project, or", query)
        self.assertIn("cross-tenant identity", query)
        self.assertIn("bounded keyset pagination ordered by dueAt and", query)
        self.assertIn("One server-clock instant defines overdue", query)
        self.assertIn("fixed asOf on the first page", query)
        self.assertIn("non-terminal items before that instant", query)
        self.assertIn("terminal", query)
        self.assertIn("items due at or after it", query)
        self.assertRegex(
            query,
            r"ownerUserId is normalized to its\s+ASCII case-folded lowercase "
            r"identity before filtering and cursor\s+fingerprinting",
        )
        self.assertIn("owner identity matching is case-insensitive", query)
        self.assertRegex(
            query,
            r"fingerprint is the SHA-256 of canonical JSON containing\s+"
            r"projectId, nullable stageId, normalized ownerUserId, overdue "
            r"tri-state,\s+and kind",
        )
        self.assertIn("limit is intentionally excluded", query)
        self.assertRegex(
            query,
            r"domain-separated HMAC-SHA256\s+derived from the current Site's "
            r"persistent Frappe encryption key",
        )
        self.assertRegex(
            query,
            r"signs\s+the complete canonical cursor payload, including "
            r"version, fingerprint,\s+asOf, dueAt, and globalId",
        )
        self.assertRegex(
            query,
            r"Follow-up requests must\s+preserve those\s+semantic filter values",
        )
        self.assertRegex(
            query,
            r"returns\s+the 422 cursor validation representation",
        )
        self.assertRegex(
            query,
            r"missing or invalid Site encryption key fails closed\s+with the "
            r"503 service-unavailable representation",
        )
        self.assertRegex(
            query,
            r"does not freeze a\s+database\s+mutation snapshot",
        )
        self.assertRegex(
            query,
            r"concurrent creates or\s+updates may affect later\s+pages",
        )
        for filter_name in (
            "workItemId",
            "stageId",
            "ownerUserId",
            "overdue",
            "kind",
            "cursor",
            "limit",
        ):
            self.assertRegex(query, rf"(?m)^          name: {filter_name}$")
        self.assertRegex(
            query,
            r"(?ms)name: workItemId.*?only after Project\s+"
            r"authorization.*?format: uuid",
        )
        self.assertRegex(
            query,
            r"(?ms)name: stageId.*?format: uuid",
        )
        self.assertRegex(
            query,
            r"(?ms)name: ownerUserId.*?format: email.*?maxLength: 254",
        )
        self.assertRegex(
            query,
            r"(?ms)name: ownerUserId.*?case-folded lowercase form.*?"
            r"identity matching is case-insensitive",
        )
        self.assertRegex(query, r"(?ms)name: overdue.*?type: boolean")
        self.assertRegex(
            query,
            r"(?ms)name: kind.*?DomainWorkItemKind",
        )
        self.assertRegex(
            query,
            r"(?ms)name: cursor.*?minLength: 1.*?maxLength: 500"
            r'.*?pattern: "\^\[A-Za-z0-9\._~:-\]\{1,500\}\$"',
        )
        self.assertRegex(query, r"Replay it\s+with the same semantic projectId")
        self.assertIn("Site-bound, HMAC-SHA256-signed v2", query)
        self.assertIn("ownerUserId letter case may vary", query)
        self.assertIn("normalized identity is bound", query)
        self.assertRegex(query, r"limit is intentionally\s+not bound")
        self.assertRegex(
            query,
            r"(?ms)name: limit.*?minimum: 1.*?maximum: 100.*?default: 50",
        )
        self.assertNotIn('"403":', query)
        self.assertEqual(
            _response_statuses(query),
            {"200", "400", "401", "404", "422", "500", "503", "default"},
        )

    def test_project_work_policy_team_and_raci_schemas_are_closed(self) -> None:
        exact_properties = {
            "ProjectWorkPolicyRef": {"globalId", "version", "snapshotHash"},
            "ProjectMemberInput": {
                "globalId",
                "userId",
                "effectiveFrom",
                "effectiveTo",
            },
            "ProjectRoleAssignmentInput": {
                "globalId",
                "memberId",
                "roleKey",
                "effectiveFrom",
                "effectiveTo",
            },
            "ProjectSubstitutionInput": {
                "globalId",
                "roleAssignmentId",
                "substituteMemberId",
                "effectiveFrom",
                "effectiveTo",
            },
            "ProjectRaciAssignmentInput": {
                "globalId",
                "contextType",
                "contextId",
                "responsibilityKey",
                "roleAssignmentId",
                "raci",
            },
            "ConfigureProjectTeam": {
                "expectedProjectVersion",
                "workPolicyRef",
                "members",
                "roleAssignments",
                "substitutions",
                "raciAssignments",
            },
        }
        for schema_name, properties in exact_properties.items():
            with self.subTest(schema=schema_name):
                self.assertIn("additionalProperties: false", _schema(schema_name))
                self.assertEqual(_property_names(schema_name), properties)

        self.assertEqual(
            set(_required_fields("ProjectWorkPolicyRef")),
            {"globalId", "version", "snapshotHash"},
        )
        self.assertIn("format: uuid", _field("ProjectWorkPolicyRef", "globalId"))
        self.assertIn("minimum: 1", _field("ProjectWorkPolicyRef", "version"))
        self.assertIn(
            "^[a-f0-9]{64}$",
            _field("ProjectWorkPolicyRef", "snapshotHash"),
        )
        self.assertIn(
            "format: email",
            _field("ProjectMemberInput", "userId"),
        )
        for schema_name, field_name in (
            ("ProjectMemberInput", "effectiveFrom"),
            ("ProjectMemberInput", "effectiveTo"),
            ("ProjectSubstitutionInput", "effectiveFrom"),
            ("ProjectSubstitutionInput", "effectiveTo"),
        ):
            self.assertIn("format: date", _field(schema_name, field_name))
        self.assertIn(
            'type: "null"',
            _field("ProjectMemberInput", "effectiveTo"),
        )
        self.assertIn(
            'type: "null"',
            _field("ProjectRoleAssignmentInput", "effectiveTo"),
        )
        self.assertNotIn(
            'type: "null"',
            _field("ProjectSubstitutionInput", "effectiveTo"),
        )
        self.assertEqual(
            _flow_enum(_field("ProjectRaciAssignmentInput", "raci")),
            ("responsible", "accountable", "consulted", "informed"),
        )
        raci = _schema("ProjectRaciAssignmentInput")
        self.assertIn("never grants ProjectAccess.APPROVE", raci)
        self.assertNotIn("approver", _property_names("ProjectRaciAssignmentInput"))
        self.assertIn("minimum: 1", _field("ConfigureProjectTeam", "expectedProjectVersion"))

    def test_wbs_dependency_and_baseline_contracts_are_policy_bound_and_closed(self) -> None:
        exact_properties = {
            "ProjectWbsItemInput": {
                "globalId",
                "code",
                "title",
                "parentId",
                "ownerRoleAssignmentId",
                "plannedStart",
                "plannedFinish",
                "actualStart",
                "actualFinish",
                "milestone",
                "statusKey",
                "progressPercent",
                "critical",
            },
            "ProjectWbsItem": {
                "globalId",
                "projectId",
                "code",
                "title",
                "parentId",
                "ownerRoleAssignmentId",
                "plannedStart",
                "plannedFinish",
                "actualStart",
                "actualFinish",
                "milestone",
                "statusKey",
                "statusLabelSource",
                "progressPercent",
                "critical",
                "version",
            },
            "ProjectDependencyInput": {
                "globalId",
                "predecessorItemId",
                "successorItemId",
            },
            "ApplyProjectWorkPlan": {
                "expectedProjectVersion",
                "workPolicyRef",
                "items",
                "dependencies",
            },
            "CaptureProjectPlanBaseline": {
                "expectedProjectVersion",
                "workPolicyRef",
                "label",
            },
            "ProjectPlanBaseline": {
                "globalId",
                "projectId",
                "projectVersion",
                "workPolicyRef",
                "label",
                "snapshotHash",
                "capturedAt",
                "capturedBy",
                "version",
            },
        }
        for schema_name, properties in exact_properties.items():
            with self.subTest(schema=schema_name):
                self.assertIn("additionalProperties: false", _schema(schema_name))
                self.assertEqual(_property_names(schema_name), properties)

        for field_name in (
            "plannedStart",
            "plannedFinish",
            "actualStart",
            "actualFinish",
        ):
            self.assertIn("format: date", _field("ProjectWbsItemInput", field_name))
        for field_name in (
            "parentId",
            "ownerRoleAssignmentId",
            "actualStart",
            "actualFinish",
        ):
            self.assertIn(
                'type: "null"',
                _field("ProjectWbsItemInput", field_name),
            )
        status_key = _field("ProjectWbsItemInput", "statusKey")
        self.assertIn("^[a-z][a-z0-9_.-]*$", status_key)
        self.assertNotIn("enum:", status_key)
        self.assertNotIn(
            "statusLabelSource",
            _property_names("ProjectWbsItemInput"),
        )
        status_label_source = _field(
            "ProjectWbsItem",
            "statusLabelSource",
        )
        self.assertIn("Literal English source string", status_label_source)
        self.assertEqual(_flow_enum(status_label_source), POLICY_LABEL_SOURCES)
        self.assertIn(
            "statusLabelSource",
            _required_fields("ProjectWbsItem"),
        )
        progress = _field("ProjectWbsItemInput", "progressPercent")
        self.assertIn("minimum: 0", progress)
        self.assertIn("maximum: 100", progress)
        self.assertIn(
            "not a computed critical-path claim",
            _field("ProjectWbsItemInput", "critical"),
        )
        dependency = _schema("ProjectDependencyInput")
        self.assertIn("Directed predecessor edge only", dependency)
        for forbidden in ("dependencyType", "lag", "openProject", "resource"):
            self.assertNotIn(forbidden, _property_names("ProjectDependencyInput"))
        plan = _schema("ApplyProjectWorkPlan")
        self.assertIn("rejects self references", plan)
        self.assertIn("cross-Project references", plan)
        self.assertIn("cycles", plan)
        self.assertIn("Omission never deletes", plan)
        self.assertIn("^[a-f0-9]{64}$", _field("ProjectPlanBaseline", "snapshotHash"))
        self.assertIn("format: date-time", _field("ProjectPlanBaseline", "capturedAt"))
        captured_by = _field("ProjectPlanBaseline", "capturedBy")
        self.assertIn("Authenticated Frappe actor identity", captured_by)
        self.assertIn("Administrator is valid", captured_by)
        self.assertIn("minLength: 1", captured_by)
        self.assertIn("maxLength: 254", captured_by)
        self.assertNotIn("format: email", captured_by)

    def test_project_work_policy_label_sources_match_canonical_registry(self) -> None:
        self.assertEqual(POLICY_LABEL_SOURCE_REGISTRY["schemaVersion"], 1)
        self.assertEqual(
            POLICY_LABEL_SOURCES,
            ("Draft", "Identified", "Not started", "Open", "Requested"),
        )
        self.assertEqual(len(POLICY_LABEL_SOURCES), len(set(POLICY_LABEL_SOURCES)))

        label_fields = _policy_label_source_fields()
        self.assertEqual(
            tuple(name for name, _line, _block in label_fields),
            (
                "statusLabelSource",
                "stateLabelSource",
                "stateLabelSource",
                "stateLabelSource",
                "stateLabelSource",
            ),
        )
        for field_name, line, field in label_fields:
            with self.subTest(field=field_name, line=line):
                self.assertEqual(_flow_enum(field), POLICY_LABEL_SOURCES)

    def test_domain_work_item_contract_has_no_shared_or_client_selected_lifecycle(self) -> None:
        create_properties = {
            "expectedProjectVersion",
            "workPolicyRef",
            "kind",
            "title",
            "detail",
            "context",
            "ownerUserId",
            "dueAt",
            "severity",
            "blocking",
            "relatedWorkItemIds",
        }
        response_properties = {
            "globalId",
            "projectId",
            "kind",
            "title",
            "detail",
            "context",
            "ownerUserId",
            "dueAt",
            "severity",
            "blocking",
            "relatedWorkItemIds",
            "workPolicyRef",
            "stateKey",
            "stateLabelSource",
            "overdue",
            "version",
            "createdAt",
            "lastChangedAt",
            "source",
        }
        self.assertIn("additionalProperties: false", _schema("CreateDomainWorkItem"))
        self.assertIn("additionalProperties: false", _schema("DomainWorkItem"))
        self.assertEqual(_property_names("CreateDomainWorkItem"), create_properties)
        self.assertEqual(_property_names("DomainWorkItem"), response_properties)
        self.assertNotIn("stateKey", create_properties)
        self.assertNotIn("stateLabelSource", create_properties)
        self.assertNotIn("status", create_properties)
        self.assertIn("No stateKey is accepted", _schema("CreateDomainWorkItem"))
        self.assertIn(
            'type: "null"',
            _field("CreateDomainWorkItem", "detail"),
        )
        for field_name in ("stageId", "wbsItemId"):
            self.assertIn(
                'type: "null"',
                _field("CreateDomainWorkItemContext", field_name),
            )
        state_key = _field("DomainWorkItem", "stateKey")
        self.assertIn("^[a-z][a-z0-9_.-]*$", state_key)
        self.assertNotIn("enum:", state_key)
        state_label_source = _field("DomainWorkItem", "stateLabelSource")
        self.assertIn("Literal English source string", state_label_source)
        self.assertEqual(_flow_enum(state_label_source), POLICY_LABEL_SOURCES)
        self.assertIn(
            "stateLabelSource",
            _required_fields("DomainWorkItem"),
        )
        self.assertIn("kind-specific lifecycle", _schema("DomainWorkItem"))
        self.assertNotIn("category", response_properties)
        self.assertNotIn("whyMe", response_properties)
        self.assertNotIn("primaryAction", response_properties)
        create_due_at = _field("CreateDomainWorkItem", "dueAt")
        self.assertIn("format: date-time", create_due_at)
        self.assertIn("([.][0-9]{1,6})?Z$", create_due_at)
        response_due_at = _field("DomainWorkItem", "dueAt")
        self.assertIn("format: date-time", response_due_at)
        self.assertIn("([.][0-9]{1,6})?Z$", response_due_at)
        self.assertIn("format: email", _field("CreateDomainWorkItem", "ownerUserId"))
        self.assertEqual(
            _flow_enum(_field("CreateDomainWorkItem", "severity")),
            ("low", "medium", "high", "critical"),
        )
        page = _schema("DomainWorkItemPage")
        self.assertIn("additionalProperties: false", page)
        self.assertEqual(
            _property_names("DomainWorkItemPage"),
            {"projectId", "projectVersion", "items", "nextCursor"},
        )
        self.assertIn('$ref: "#/components/schemas/DomainWorkItem"', page)
        next_cursor = _field("DomainWorkItemPage", "nextCursor")
        self.assertIn('type: "null"', next_cursor)
        self.assertIn("^[A-Za-z0-9._~:-]{1,500}$", next_cursor)

    def test_project_work_context_is_exact_closed_and_preserves_permissions(self) -> None:
        expected = {
            "projectId",
            "projectVersion",
            "initialized",
            "workPolicyRef",
            "members",
            "roleAssignments",
            "substitutions",
            "raciAssignments",
            "wbsItems",
            "dependencies",
            "baselines",
            "baselineComparison",
            "permissions",
        }
        context = _schema("ProjectWorkContext")
        self.assertIn("additionalProperties: false", context)
        self.assertEqual(_property_names("ProjectWorkContext"), expected)
        self.assertEqual(set(_required_fields("ProjectWorkContext")), expected)
        self.assertIn('type: "null"', _field("ProjectWorkContext", "workPolicyRef"))
        self.assertIn(
            'type: "null"',
            _field("ProjectWorkContext", "baselineComparison"),
        )
        self.assertIn(
            '$ref: "#/components/schemas/ProjectPermissions"',
            _field("ProjectWorkContext", "permissions"),
        )
        self.assertNotIn("canApprove", _property_names("ProjectPermissions"))

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
