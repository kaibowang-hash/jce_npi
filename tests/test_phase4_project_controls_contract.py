from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (ROOT / "contracts" / "npi-api.openapi.yaml").read_text(encoding="utf-8")
OWNERSHIP = (ROOT / "contracts" / "data-ownership.yaml").read_text(
    encoding="utf-8"
)
LINES = CONTRACT.splitlines()


def _indented_block(marker: str) -> str:
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


def _operation(path_marker: str, method: str) -> str:
    path = _indented_block(path_marker)
    path_lines = path.splitlines()
    marker = f"    {method}:"
    matches = [index for index, line in enumerate(path_lines) if line == marker]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {method!r} operation in {path_marker!r}.")
    start = matches[0]
    end = len(path_lines)
    for index in range(start + 1, len(path_lines)):
        line = path_lines[index]
        if line.strip() and len(line) - len(line.lstrip()) <= 4:
            end = index
            break
    return "\n".join(path_lines[start:end])


def _schema(name: str) -> str:
    return _indented_block(f"    {name}:")


def _component_response(name: str) -> str:
    return _indented_block(f"    {name}:")


def _response_statuses(operation: str) -> set[str]:
    return {
        quoted or default
        for quoted, default in re.findall(
            r'^        (?:"([0-9]{3})"|(default)):',
            operation,
            re.MULTILINE,
        )
    }


def _success_response(operation: str, status: str) -> str:
    lines = operation.splitlines()
    marker = f'        "{status}":'
    starts = [index for index, line in enumerate(lines) if line == marker]
    if len(starts) != 1:
        raise AssertionError(f"Expected one {status} response.")
    start = starts[0]
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.strip() and len(line) - len(line.lstrip()) <= 8:
            end = index
            break
    response = "\n".join(lines[start:end])
    reference = re.search(
        r'\$ref: "#/components/responses/([A-Za-z0-9_.-]+)"',
        response,
    )
    return (
        _component_response(reference.group(1)) if reference is not None else response
    )


def _required(schema_name: str) -> tuple[str, ...]:
    block = _schema(schema_name)
    flow = re.search(
        r"^      required:\s*\[([^]]*)\]",
        block,
        re.MULTILINE,
    )
    if flow is not None:
        return tuple(
            value.strip() for value in flow.group(1).split(",") if value.strip()
        )
    lines = block.splitlines()
    try:
        start = lines.index("      required:") + 1
    except ValueError as error:
        raise AssertionError(f"{schema_name} has no required fields.") from error
    fields: list[str] = []
    for line in lines[start:]:
        if line.startswith("        - "):
            fields.append(line.removeprefix("        - ").strip())
            continue
        if line.strip():
            break
    return tuple(fields)


def _property_names(schema_name: str) -> set[str]:
    return set(
        re.findall(
            r"^        ([A-Za-z][A-Za-z0-9]*):",
            _schema(schema_name),
            re.MULTILINE,
        )
    )


def _ownership_object(name: str) -> str:
    lines = OWNERSHIP.splitlines()
    marker = f"  {name}:"
    starts = [index for index, line in enumerate(lines) if line == marker]
    if len(starts) != 1:
        raise AssertionError(f"Expected one ownership object {name!r}.")
    start = starts[0]
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.startswith("  ") and not line.startswith("    ") and line.strip():
            end = index
            break
    return "\n".join(lines[start:end])


class Phase4ProjectControlsContractTest(unittest.TestCase):
    QUERY_OPERATIONS = (
        (
            "  /projects/{projectId}/controls:",
            "get",
            "200",
            {
                "200",
                "400",
                "401",
                "403",
                "404",
                "422",
                "500",
                "503",
                "default",
            },
        ),
        (
            "  /projects/{projectId}/activity:",
            "get",
            "200",
            {
                "200",
                "400",
                "401",
                "403",
                "404",
                "422",
                "500",
                "503",
                "default",
            },
        ),
        (
            "  /projects/{projectId}/learning:",
            "get",
            "200",
            {
                "200",
                "400",
                "401",
                "403",
                "404",
                "422",
                "500",
                "503",
                "default",
            },
        ),
        (
            "  /learning:",
            "get",
            "200",
            {
                "200",
                "400",
                "401",
                "403",
                "404",
                "422",
                "500",
                "503",
                "default",
            },
        ),
    )
    COMMAND_OPERATIONS = (
        ("  /projects/{projectId}:bind-control-policy:", "post", "200"),
        ("  /projects/{projectId}:assess-health:", "post", "200"),
        ("  /projects/{projectId}:transition:", "post", "200"),
        ("  /projects/{projectId}/comments:", "post", "201"),
        ("  /projects/{projectId}:follow:", "post", "200"),
        ("  /projects/{projectId}:unfollow:", "post", "200"),
        ("  /projects/{projectId}/learning:", "post", "201"),
    )

    def test_routes_are_explicit_business_operations(self) -> None:
        expected_operation_ids = {
            "  /projects/{projectId}/controls:": "getProjectControls",
            "  /projects/{projectId}:bind-control-policy:": (
                "bindProjectControlPolicy"
            ),
            "  /projects/{projectId}:assess-health:": "assessProjectHealth",
            "  /projects/{projectId}:transition:": ("transitionProjectLifecycle"),
            "  /projects/{projectId}/activity:": "getProjectActivity",
            "  /projects/{projectId}/comments:": "addProjectComment",
            "  /projects/{projectId}:follow:": "followProject",
            "  /projects/{projectId}:unfollow:": "unfollowProject",
            "  /projects/{projectId}/learning:": "getProjectLearning",
            "  /learning:": "searchProjectLearning",
        }
        for marker, operation_id in expected_operation_ids.items():
            with self.subTest(path=marker):
                path = _indented_block(marker)
                self.assertIn(f"operationId: {operation_id}", path)
                self.assertIn(
                    '$ref: "#/components/parameters/RequestId"',
                    path,
                )

        project_learning = _indented_block("  /projects/{projectId}/learning:")
        self.assertIn(
            "operationId: createProjectLearning",
            project_learning,
        )
        self.assertIn("name: learningId", project_learning)
        self.assertIn("Exact same-Project learning identity", project_learning)
        transition = _operation(
            "  /projects/{projectId}:transition:",
            "post",
        )
        self.assertIn("server", transition)
        self.assertIn("fails closed", transition)
        self.assertIn("handover or cost readiness is unavailable", transition)

    def test_data_ownership_keeps_controls_learning_and_projection_single_master(
        self,
    ) -> None:
        expected_owners = {
            "ProjectControlPolicy": "NPI_ONE",
            "ProjectControlBinding": "NPI_ONE",
            "ProjectHealthAssessment": "NPI_ONE",
            "ProjectActivity": "NPI_ONE",
            "ProjectFollower": "NPI_ONE",
            "ProjectLearning": "NPI_ONE",
            "MyWorkAssignmentProjection": "NPI_ONE_PROJECTION",
        }
        for object_name, owner in expected_owners.items():
            with self.subTest(object=object_name):
                self.assertIn(
                    f"owner_system: {owner}",
                    _ownership_object(object_name),
                )

        policy = _ownership_object("ProjectControlPolicy")
        self.assertIn("conflict: IMMUTABLE_SNAPSHOT", policy)
        self.assertIn("conflict: FAIL_CLOSED", policy)
        binding = _ownership_object("ProjectControlBinding")
        self.assertIn("conflict: EXACT_VERSION_REFERENCE", binding)
        self.assertIn("conflict: APPEND_ONLY", binding)
        health = _ownership_object("ProjectHealthAssessment")
        self.assertIn(
            "erp_cost_actual: {owner: ERPNEXT, editable_in: [ERPNEXT], "
            "direction: ERPNEXT_TO_NPI, conflict: FAIL_CLOSED_WHILE_UNAVAILABLE}",
            health,
        )
        activity = _ownership_object("ProjectActivity")
        follower = _ownership_object("ProjectFollower")
        for block in (activity, follower):
            self.assertIn("owner: FUTURE_NOTIFICATION_SERVICE", block)
            self.assertIn("conflict: UNAVAILABLE", block)
        learning = _ownership_object("ProjectLearning")
        self.assertIn("conflict: APPEND_ONLY", learning)
        self.assertIn("conflict: PROPOSAL_ONLY", learning)
        projection = _ownership_object("MyWorkAssignmentProjection")
        self.assertIn("owner: SOURCE_OBJECT_OWNER", projection)
        self.assertIn("direction: REFERENCE_ONLY", projection)
        self.assertIn("conflict: REBUILD_FROM_SOURCE", projection)
        self.assertIn("conflict: REVALIDATE_SOURCE", projection)

        project = _ownership_object("EngineeringProject")
        self.assertIn("owner: VERSIONED_PROJECT_CONTROL_POLICY", project)
        self.assertIn("owner: NPI_ONE_RULE_ENGINE", project)
        self.assertNotRegex(
            OWNERSHIP,
            r"editable_in:\s*\[(?:NPI_ONE,\s*ERPNEXT|ERPNEXT,\s*NPI_ONE)\]",
        )

    def test_queries_have_complete_problems_and_correlation_headers(
        self,
    ) -> None:
        for marker, method, success, expected_statuses in self.QUERY_OPERATIONS:
            with self.subTest(path=marker):
                operation = _operation(marker, method)
                self.assertEqual(
                    _response_statuses(operation),
                    expected_statuses,
                )
                response = _success_response(operation, success)
                self.assertIn("X-Request-ID:", response)
                self.assertIn("X-Trace-ID:", response)
                self.assertNotIn("Idempotency-Replayed:", response)

    def test_commands_have_complete_problems_and_replay_headers(self) -> None:
        expected_statuses = {
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
        for marker, method, success in self.COMMAND_OPERATIONS:
            with self.subTest(path=marker):
                operation = _operation(marker, method)
                self.assertEqual(
                    _response_statuses(operation),
                    expected_statuses - {"200"} | {success},
                )
                for parameter in (
                    "IdempotencyKey",
                    "RequestId",
                    "CsrfToken",
                ):
                    self.assertIn(
                        f'$ref: "#/components/parameters/{parameter}"',
                        operation,
                    )
                response = _success_response(operation, success)
                self.assertIn("X-Request-ID:", response)
                self.assertIn("X-Trace-ID:", response)
                self.assertIn("Idempotency-Replayed:", response)

    def test_commands_declare_exact_transaction_and_audit_boundaries(self) -> None:
        expected = {
            "  /projects/{projectId}:bind-control-policy:": (
                "project-root",
                "project.control_policy.bind",
            ),
            "  /projects/{projectId}:assess-health:": (
                "project-root",
                "project.health.assess",
            ),
            "  /projects/{projectId}/comments:": (
                "project-root",
                "project.comment.add",
            ),
            "  /projects/{projectId}:follow:": (
                "project-root",
                "project.follow",
            ),
            "  /projects/{projectId}:unfollow:": (
                "project-root",
                "project.unfollow",
            ),
            "  /projects/{projectId}/learning:": (
                "project-root",
                "project.learning.create",
            ),
        }
        for marker, (boundary, audit) in expected.items():
            with self.subTest(path=marker):
                operation = _operation(marker, "post")
                self.assertIn(
                    f"x-transaction-boundary: {boundary}",
                    operation,
                )
                self.assertIn(f"x-audit-operation: {audit}", operation)
        transition = _operation(
            "  /projects/{projectId}:transition:",
            "post",
        )
        self.assertIn(
            "x-transaction-boundary: project-root",
            transition,
        )
        self.assertIn(
            "x-audit-operation-prefix: project.lifecycle.",
            transition,
        )
        for action in ("pause", "cancel", "resume", "complete"):
            self.assertIn(
                f"- project.lifecycle.{action}",
                transition,
            )

    def test_commands_admit_transport_before_business_authority(self) -> None:
        bind = _operation(
            "  /projects/{projectId}:bind-control-policy:",
            "post",
        )
        self.assertIn("x-required-roles: [System Manager]", bind)
        for marker, _method, _success in self.COMMAND_OPERATIONS[1:]:
            with self.subTest(path=marker):
                self.assertIn(
                    "x-required-transport-role: NPI API User",
                    _operation(marker, "post"),
                )

    def test_control_commands_are_closed_and_exact(self) -> None:
        expected = {
            "BindProjectControlPolicy": (
                "expectedProjectVersion",
                "policyRef",
                "bindings",
            ),
            "AssessProjectHealth": (
                "expectedProjectVersion",
                "measurements",
                "reason",
                "recoveryPlan",
            ),
            "TransitionProject": (
                "expectedProjectVersion",
                "action",
                "reason",
            ),
            "AddProjectComment": (
                "body",
                "mentions",
                "attachments",
                "objectLinks",
            ),
            "ChangeProjectFollowState": ("expectedVersion",),
            "CreateProjectLearning": (
                "kind",
                "title",
                "content",
                "recommendation",
                "tags",
            ),
        }
        for schema_name, fields in expected.items():
            with self.subTest(schema=schema_name):
                self.assertEqual(_required(schema_name), fields)
                self.assertEqual(_property_names(schema_name), set(fields))
                self.assertIn(
                    "additionalProperties: false",
                    _schema(schema_name),
                )

    def test_controls_are_honest_and_policy_bound(self) -> None:
        controls = _schema("ProjectControls")
        self.assertEqual(
            _required("ProjectControls"),
            (
                "project",
                "policy",
                "binding",
                "health",
                "lifecycleActions",
                "bindingOptions",
                "permissions",
            ),
        )
        self.assertEqual(
            _property_names("ProjectControls"),
            set(_required("ProjectControls")),
        )
        self.assertIn("additionalProperties: false", controls)
        self.assertIn(
            "enum: [unassessed, unavailable, green, yellow, red]",
            _schema("ProjectHealthStatus"),
        )
        dimensions = _schema("ProjectHealthDimensionResult")
        self.assertIn(
            "enum: [progress, cost, quality, risk]",
            dimensions,
        )
        self.assertIn("maxLength: 64", dimensions)
        measurements = _schema("ProjectHealthMeasurement")
        self.assertIn("maxLength: 64", measurements)
        self.assertIn("exclusiveMinimum: -1.0e38", measurements)
        self.assertIn("exclusiveMaximum: 1.0e38", measurements)
        lifecycle = _schema("ProjectLifecycleActionAvailability")
        for reason in (
            "policy_missing",
            "project_terminal",
            "command_access_required",
            "authority_required",
            "prerequisite_unavailable",
            "prerequisite_blocked",
        ):
            self.assertIn(reason, lifecycle)
        prerequisites = _schema("ProjectLifecyclePrerequisite")
        self.assertIn(
            "enum: [open_blockers, controlled_files, handover, cost]",
            prerequisites,
        )
        self.assertIn(
            "enum: [satisfied, blocked, unavailable]",
            prerequisites,
        )
        binding_options = _schema("ProjectControlBindingOptions")
        self.assertEqual(
            _required("ProjectControlBindingOptions"),
            ("policies", "eligibleMembers"),
        )
        self.assertEqual(
            _property_names("ProjectControlBindingOptions"),
            {"policies", "eligibleMembers"},
        )
        self.assertIn("additionalProperties: false", binding_options)
        self.assertIn("maxItems: 500", binding_options)
        self.assertIn("uniqueItems: true", binding_options)
        self.assertIn(
            '$ref: "#/components/schemas/ProjectControlPolicyReference"',
            binding_options,
        )

    def test_activity_is_url_free_clean_and_uses_typed_targets(self) -> None:
        self.assertEqual(
            _required("ProjectActivityPage"),
            (
                "projectId",
                "items",
                "nextCursor",
                "permissions",
                "commentOptions",
                "following",
                "followerVersion",
            ),
        )
        self.assertEqual(
            _required("ProjectCommentOptions"),
            ("truncated", "mentions", "attachments", "objectLinks"),
        )
        self.assertEqual(
            _property_names("ProjectCommentOptions"),
            {"truncated", "mentions", "attachments", "objectLinks"},
        )
        self.assertIn("type: boolean", _schema("ProjectCommentOptions"))
        self.assertIn(
            "additionalProperties: false",
            _schema("ProjectCommentOptions"),
        )
        activity_page = _schema("ProjectActivityPage")
        self.assertIn("required: [canComment, canFollow]", activity_page)
        self.assertIn("nextCursor:", activity_page)
        self.assertIn("HMAC-SHA256-signed v1 continuation token", activity_page)
        self.assertIn('pattern: "^[A-Za-z0-9._~:-]{1,500}$"', activity_page)
        self.assertIn('- { type: "null" }', activity_page)
        activity_operation = _operation(
            "  /projects/{projectId}/activity:",
            "get",
        )
        self.assertIn("name: cursor", activity_operation)
        self.assertIn("occurredAt/globalId keyset seek", activity_operation)
        self.assertIn("limit is intentionally excluded", activity_operation)
        self.assertIn(
            "validation occurs only after Project authorization",
            activity_operation,
        )
        self.assertIn("without querying activity", activity_operation)
        self.assertIn("persistent Frappe", activity_operation)
        self.assertIn("503", activity_operation)
        attachment = _schema("ProjectActivityAttachment")
        self.assertIn("scanState: { type: string, const: clean }", attachment)
        self.assertNotIn("url:", attachment.casefold())
        self.assertNotIn("file:", attachment.casefold())

        target = _schema("ProjectObjectTarget")
        for target_kind in (
            "const: project",
            "const: gate",
            "const: project_work_item",
            "const: project_learning",
        ):
            self.assertIn(target_kind, target)
        self.assertNotIn("path:", target.casefold())
        self.assertNotIn("url:", target.casefold())

        item = _schema("ProjectActivityItem")
        self.assertIn("additionalProperties: false", item)
        self.assertNotIn("format: email", item)
        self.assertIn("Administrator is valid", item)
        self.assertIn(
            '$ref: "#/components/schemas/ProjectCommentDetail"',
            item,
        )
        self.assertIn(
            '$ref: "#/components/schemas/ProjectHealthActivityDetail"',
            item,
        )
        self.assertIn(
            '$ref: "#/components/schemas/ProjectLifecycleActivityDetail"',
            item,
        )

    def test_learning_is_immutable_exact_template_feedback(self) -> None:
        learning = _schema("ProjectLearning")
        self.assertEqual(
            set(_required("ProjectLearning")),
            _property_names("ProjectLearning"),
        )
        self.assertEqual(
            _required("ProjectLearningPage"),
            ("projectId", "items", "permissions"),
        )
        self.assertIn(
            "required: [canCreate]",
            _schema("ProjectLearningPage"),
        )
        self.assertIn("additionalProperties: false", learning)
        self.assertIn(
            "enum: [retrospective, lesson, template_improvement]",
            _schema("ProjectLearningKind"),
        )
        self.assertIn("templateRef:", learning)
        self.assertIn("snapshotHash:", learning)
        self.assertIn("target:", learning)
        self.assertNotIn("format: email", learning)
        self.assertIn("Administrator is valid", learning)
        self.assertNotIn("externalUrl", learning)
        self.assertNotIn("href:", learning)


if __name__ == "__main__":
    unittest.main()
