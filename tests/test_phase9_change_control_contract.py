from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPENAPI = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")


def path_block(path: str) -> str:
    paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
    start = paths.index(f"  {path}:\n")
    match = re.search(r"\n  /[^\n]+:\n", paths[start + 1 :])
    return paths[start:] if match is None else paths[start : start + 1 + match.start()]


def schema(name: str) -> str:
    start = OPENAPI.index(f"    {name}:\n", OPENAPI.index("  schemas:\n"))
    match = re.search(r"\n    [A-Z][A-Za-z0-9]+:\n", OPENAPI[start + 1 :])
    return OPENAPI[start:] if match is None else OPENAPI[start : start + 1 + match.start()]


class Phase9ChangeControlContractTest(unittest.TestCase):
    def test_exact_six_project_first_operations_are_exposed(self) -> None:
        expected = {
            "/projects/{projectId}/engineering-changes": {"get", "post"},
            "/projects/{projectId}/engineering-changes/{changeId}": {"get"},
            "/projects/{projectId}/engineering-changes/{changeId}/revisions": {"post"},
            "/projects/{projectId}/engineering-changes/{changeId}:link-formal-observation": {"post"},
            "/projects/{projectId}/engineering-changes/{changeId}:close": {"post"},
        }
        for path, methods in expected.items():
            with self.subTest(path=path):
                self.assertEqual(
                    set(re.findall(r"^    (get|post):$", path_block(path), flags=re.MULTILINE)),
                    methods,
                )
                self.assertIn("#/components/parameters/ProjectId", path_block(path))
        self.assertEqual(sum(map(len, expected.values())), 6)

    def test_commands_are_csrf_idempotent_audited_and_project_contained(self) -> None:
        for path in (
            "/projects/{projectId}/engineering-changes",
            "/projects/{projectId}/engineering-changes/{changeId}/revisions",
            "/projects/{projectId}/engineering-changes/{changeId}:link-formal-observation",
            "/projects/{projectId}/engineering-changes/{changeId}:close",
        ):
            block = path_block(path)
            command = block[block.index("\n    post:\n") :]
            for parameter in ("IdempotencyKey", "RequestId", "CsrfToken"):
                self.assertIn(f"#/components/parameters/{parameter}", command)
            self.assertIn("x-transaction-boundary: engineering-change", command)
            self.assertIn("x-audit-operation: engineering_change.", command)

    def test_closed_requests_exclude_erp_and_server_owned_truth(self) -> None:
        create = path_block("/projects/{projectId}/engineering-changes")
        revise = path_block("/projects/{projectId}/engineering-changes/{changeId}/revisions")
        close = path_block("/projects/{projectId}/engineering-changes/{changeId}:close")
        content = schema("EngineeringChangeContent")
        for forbidden in (
            "formalChange:", "rawStatus:", "internalState:", "readyToClose:",
            "tenantId:", "projectGlobalId:", "changeGlobalId:", "snapshotHash:",
            "createdByUserId:", "requestId:", "traceId:",
        ):
            self.assertNotIn(forbidden, content)
        self.assertIn("Formal ERP change truth cannot be supplied here", create)
        self.assertIn("ERP formal observation fields remain server-owned", revise)
        self.assertIn("server-derived closeout predicate", close)

    def test_formal_observation_is_one_explicit_erp_ecr_raw_projection(self) -> None:
        observation = schema("FormalEngineeringChangeObservation")
        self.assertIn("const: Engineering Change Request", observation)
        self.assertIn("rawStatus:", observation)
        self.assertIn("sourceVersion:", observation)
        self.assertIn("sourceHash:", observation)
        self.assertIn("never translated into LaunchFlow truth", observation)
        command = path_block(
            "/projects/{projectId}/engineering-changes/{changeId}:link-formal-observation"
        )
        self.assertIn("x-required-roles: [System Manager, NPI API User]", command)

    def test_revision_content_covers_every_change_control_dimension(self) -> None:
        content = schema("EngineeringChangeContent")
        for field in (
            "impactAssessments", "affectedObjects", "implementationTasks",
            "effectivityRules", "dispositions", "revalidationRequirements",
            "costSummary", "closureEvidence",
        ):
            self.assertIn(f"{field}:", content)
        impacts = schema("EngineeringChangeImpactAssessment")
        for category in (
            "product", "drawing", "ebom", "mbom", "tooling", "process",
            "quality", "inventory_wip", "supplier", "cost", "delivery", "customer",
        ):
            self.assertIn(category, impacts)
        self.assertIn("minItems: 12", content)
        self.assertIn("maxItems: 12", content)

    def test_responses_are_closed_versioned_and_append_only(self) -> None:
        for name in (
            "EngineeringChangeRevision", "EngineeringChangeCurrent",
            "EngineeringChangePermissions", "EngineeringChangeList",
            "EngineeringChangeEvent", "EngineeringChangeDetail",
            "EngineeringChangeCommand",
        ):
            self.assertIn("additionalProperties: false", schema(name))
        revision = schema("EngineeringChangeRevision")
        self.assertIn("schemaVersion: { type: integer, const: 1 }", revision)
        self.assertIn("predecessorSnapshotHash:", revision)
        self.assertIn("snapshotHash:", revision)
        response = OPENAPI[
            OPENAPI.index("    EngineeringChangeCommandResult:\n", OPENAPI.index("  responses:\n")) :
            OPENAPI.index("    IntegrationOperationCollectionResult:\n", OPENAPI.index("  responses:\n"))
        ]
        self.assertIn("Idempotency-Replayed", response)
        self.assertIn('const: "private, no-store"', response)


if __name__ == "__main__":
    unittest.main()
