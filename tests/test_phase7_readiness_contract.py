from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPENAPI = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")
OWNERSHIP = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")


def schema(name: str) -> str:
    start = OPENAPI.index(f"    {name}:\n", OPENAPI.index("  schemas:\n"))
    match = re.search(r"\n    [A-Z][A-Za-z0-9]+:\n", OPENAPI[start + 1 :])
    return OPENAPI[start:] if match is None else OPENAPI[start : start + 1 + match.start()]


def path_block(path: str) -> str:
    paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
    start = paths.index(f"  {path}:\n")
    match = re.search(r"\n  /[^\n]+:\n", paths[start + 1 :])
    return paths[start:] if match is None else paths[start : start + 1 + match.start()]


def response(name: str) -> str:
    start = OPENAPI.index(f"    {name}:\n", OPENAPI.index("  responses:\n"))
    schemas_start = OPENAPI.index("  schemas:\n")
    match = re.search(r"\n    [A-Z][A-Za-z0-9]+:\n", OPENAPI[start + 1 : schemas_start])
    return OPENAPI[start:schemas_start] if match is None else OPENAPI[start : start + 1 + match.start()]


class Phase7ReadinessContractTest(unittest.TestCase):
    def test_checkpoint_two_exposes_exactly_the_seven_frozen_operations(self) -> None:
        paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
        expected = {
            "/npi-readiness/templates": {"get", "post"},
            "/npi-readiness/templates/{templateId}/versions/{templateVersion}": {"put"},
            "/npi-readiness/templates/{templateId}/versions/{templateVersion}:publish": {"post"},
            "/projects/{projectId}/npi-readiness": {"get", "post"},
            "/projects/{projectId}/npi-readiness/{instanceId}/revisions": {"post"},
        }
        readiness_paths = set(
            re.findall(r"^  (/[^\n]*readiness[^\n]*):$", paths, flags=re.MULTILINE)
        )
        self.assertEqual(readiness_paths, set(expected))
        operation_count = 0
        for path, methods in expected.items():
            with self.subTest(path=path):
                actual = set(
                    re.findall(
                        r"^    (get|post|put|patch|delete):$",
                        path_block(path),
                        flags=re.MULTILINE,
                    )
                )
                self.assertEqual(actual, methods)
                operation_count += len(actual)
        self.assertEqual(operation_count, 7)
        for operation_id in (
            "listEligibleReadinessTemplates",
            "createReadinessTemplateDraft",
            "editReadinessTemplateDraft",
            "publishReadinessTemplateVersion",
            "getProjectReadinessWorkspace",
            "initializeProjectReadiness",
            "reviseProjectReadinessItem",
        ):
            self.assertEqual(paths.count(f"operationId: {operation_id}"), 1)

    def test_readiness_response_and_domain_schemas_are_closed(self) -> None:
        for name in (
            "ReadinessApplicabilitySelector",
            "ReadinessCategoryDefinition",
            "ReadinessEvidenceRequirement",
            "ReadinessItemDefinition",
            "ReadinessTemplateVersion",
            "ReadinessExactReference",
            "ReadinessProjectSnapshot",
            "ReadinessMemberReference",
            "ReadinessGateReference",
            "ReadinessSourceReference",
            "ReadinessItemSnapshot",
            "ReadinessScore",
            "ReadinessBlocker",
            "ReadinessEvaluation",
            "ReadinessInstanceRevision",
            "CreateReadinessTemplate",
            "EditReadinessTemplate",
            "PublishReadinessTemplate",
            "ReadinessTemplateCatalog",
            "ReadinessAssignment",
            "InitializeProjectReadiness",
            "ReadinessInternalSourceSelection",
            "ReadinessExternalSourceSelection",
            "ReviseProjectReadinessItem",
            "ReadinessUnavailableProjection",
            "ReadinessPermissions",
            "ReadinessWorkspace",
        ):
            with self.subTest(name=name):
                self.assertIn("additionalProperties: false", schema(name))

    def test_commands_require_csrf_actor_bound_idempotency_and_audit(self) -> None:
        command_paths = (
            "/npi-readiness/templates",
            "/npi-readiness/templates/{templateId}/versions/{templateVersion}",
            "/npi-readiness/templates/{templateId}/versions/{templateVersion}:publish",
            "/projects/{projectId}/npi-readiness",
            "/projects/{projectId}/npi-readiness/{instanceId}/revisions",
        )
        for path in command_paths:
            block = path_block(path)
            command_start = max(block.find("\n    post:\n"), block.find("\n    put:\n"))
            command = block[command_start:]
            with self.subTest(path=path):
                self.assertIn("#/components/parameters/IdempotencyKey", command)
                self.assertIn("#/components/parameters/RequestId", command)
                self.assertIn("#/components/parameters/CsrfToken", command)
                self.assertIn("x-required-roles: [System Manager]", command)
                self.assertIn("x-transaction-boundary:", command)
                self.assertIn("x-audit-operation: readiness_", command)
        paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
        self.assertEqual(paths.count("x-audit-operation: readiness_"), 5)

    def test_template_and_project_reads_are_project_first(self) -> None:
        catalog = path_block("/npi-readiness/templates")
        workspace = path_block("/projects/{projectId}/npi-readiness")
        self.assertIn("name: projectId", catalog)
        self.assertIn("in: query", catalog)
        self.assertIn("Project-first authorization", catalog)
        self.assertIn("#/components/parameters/ProjectId", workspace)
        self.assertIn("Project-first authorization", workspace)
        self.assertIn("exact published readiness-template versions", catalog)

    def test_template_contract_is_explicit_configuration_without_defaults(self) -> None:
        template = schema("ReadinessTemplateVersion")
        for marker in (
            "projectTypes:",
            "customerReferenceKeys:",
            "industryKeys:",
            "categories:",
            "items:",
            "Metadata installs no production default row.",
        ):
            self.assertIn(marker, template if marker in template else schema("ReadinessApplicabilitySelector"))
        item = schema("ReadinessItemDefinition")
        self.assertIn("blockingLevel:", item)
        self.assertIn("gateKey:", item)
        self.assertIn("completionRule:", item)
        self.assertIn("evidenceRequirements:", item)
        self.assertIn("controlled quality report is exact evidence only", item)

    def test_external_sources_are_unavailable_without_caller_authority(self) -> None:
        source = schema("ReadinessSourceReference")
        for marker in (
            "erp_material_specification",
            "erp_quality_result",
            "erp_run_at_rate",
            "erp_hr_qualification",
            "erp_supplier_execution",
            "identity-free unavailable external provider",
        ):
            self.assertIn(marker, source)
        self.assertIn("enum: [satisfied, failed, unavailable]", source)

        selection = schema("ReadinessSourceSelection")
        internal = schema("ReadinessInternalSourceSelection")
        external = schema("ReadinessExternalSourceSelection")
        self.assertIn("oneOf:", selection)
        for exact_field in ("globalId:", "sourceVersion:", "snapshotHash:"):
            self.assertIn(exact_field, internal)
            self.assertNotIn(exact_field, external)
        for caller_truth in ("state:", "reasonCode:", "disposition:"):
            self.assertNotIn(caller_truth, internal)
            self.assertNotIn(caller_truth, external)

    def test_closed_requests_exclude_server_owned_readiness_truth(self) -> None:
        requests = "\n".join(
            schema(name)
            for name in (
                "CreateReadinessTemplate",
                "EditReadinessTemplate",
                "PublishReadinessTemplate",
                "InitializeProjectReadiness",
                "ReadinessInternalSourceSelection",
                "ReadinessExternalSourceSelection",
                "ReviseProjectReadinessItem",
            )
        )
        for forbidden in (
            "tenantId:",
            "projectGlobalId:",
            "publicationState:",
            "templateGlobalId:",
            "instanceGlobalId:",
            "applicable:",
            "gate:",
            "sourceState:",
            "disposition:",
            "reasonCode:",
            "score:",
            "scores:",
            "blocker:",
            "blockers:",
            "ready:",
            "requestId:",
            "traceId:",
            "createdByUserId:",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, requests)
        revise = schema("ReviseProjectReadinessItem")
        self.assertIn("enum: [not_started, in_progress, complete, failed]", revise)
        self.assertNotIn("not_applicable", revise)

    def test_command_and_query_responses_preserve_security_headers_and_problem_details(self) -> None:
        query_responses = (
            "ReadinessTemplateCatalogResult",
            "ReadinessQueryResult",
        )
        command_responses = (
            "ReadinessTemplateCommandResult",
            "ReadinessCommandResult",
        )
        for name in query_responses + command_responses:
            value = response(name)
            with self.subTest(name=name):
                self.assertIn("X-Request-ID:", value)
                self.assertIn("X-Trace-ID:", value)
                self.assertIn('const: "private, no-store"', value)
        for name in command_responses:
            self.assertIn("Idempotency-Replayed:", response(name))
        for name in query_responses:
            self.assertNotIn("Idempotency-Replayed:", response(name))
        self.assertIn("additionalProperties: false", schema("ProblemDetails"))
        readiness_paths = "\n".join(
            path_block(path)
            for path in (
                "/npi-readiness/templates",
                "/npi-readiness/templates/{templateId}/versions/{templateVersion}",
                "/npi-readiness/templates/{templateId}/versions/{templateVersion}:publish",
                "/projects/{projectId}/npi-readiness",
                "/projects/{projectId}/npi-readiness/{instanceId}/revisions",
            )
        )
        self.assertIn("#/components/responses/BadRequest", readiness_paths)
        self.assertIn("#/components/responses/AuthenticationError", readiness_paths)
        self.assertIn("#/components/responses/PermissionError", readiness_paths)
        self.assertIn("#/components/responses/ProjectValidationError", readiness_paths)
        self.assertIn("#/components/responses/ProjectError", readiness_paths)

    def test_score_and_blocker_contract_cannot_mutate_gate(self) -> None:
        evaluation = schema("ReadinessEvaluation")
        self.assertIn("const: readiness-score.v1", evaluation)
        self.assertIn("blockers:", evaluation)
        blocker = schema("ReadinessBlocker")
        self.assertIn("incomplete_p0", blocker)
        self.assertIn("failed_mandatory_quality", blocker)
        self.assertIn("dominant regardless of score", blocker)
        instance = schema("ReadinessInstanceRevision")
        self.assertIn("no Gate, Work Item, risk, Tooling, handover or external mutation", instance)
        workspace = schema("ReadinessWorkspace")
        self.assertIn("currentRevision:", workspace)
        self.assertIn("revisions:", workspace)
        self.assertIn("sourceOptions:", workspace)
        self.assertIn("unavailableProjections:", workspace)
        self.assertIn("permissions:", workspace)
        unavailable = schema("ReadinessUnavailableProjection")
        self.assertIn("state: { type: string, const: unavailable }", unavailable)
        self.assertIn("minItems: 5", workspace)
        self.assertIn("maxItems: 5", workspace)
        source_option = schema("ReadinessSourceOption")
        self.assertIn("const: domain_work_item", source_option)
        self.assertIn("snapshotHash:", source_option)

    def test_ownership_keeps_fact_layers_and_gate_authority_separate(self) -> None:
        for object_name in (
            "NpiReadinessTemplate",
            "NpiReadinessTemplateVersion",
            "NpiReadinessInstanceRevision",
        ):
            self.assertIn(f"  {object_name}:\n", OWNERSHIP)
        for boundary in (
            "conflict: NOT_INSTALLED_BY_METADATA",
            "conflict: CONFIGURATION_NOT_GLOBAL_HARDCODE",
            "conflict: UNAVAILABLE_NO_CALLER_STATUS",
            "conflict: EXACT_ITEM_SNAPSHOT_WINS",
            "conflict: GATE_POLICY_REMAINS_INDEPENDENT",
            "conflict: NO_AUTOMATIC_MUTATION_IN_P7_05",
        ):
            self.assertIn(boundary, OWNERSHIP)


if __name__ == "__main__":
    unittest.main()
