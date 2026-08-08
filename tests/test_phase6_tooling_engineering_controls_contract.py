from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPENAPI = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")
OWNERSHIP = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")
BFF = (ROOT / "apps/npi_core/npi_core/bff.py").read_text(encoding="utf-8")
API = (ROOT / "apps/npi_core/npi_core/tooling_api.py").read_text(encoding="utf-8")
SECURITY = (ROOT / "apps/npi_core/npi_core/request_security.py").read_text(
    encoding="utf-8"
)


def _schema(name: str) -> str:
    start = OPENAPI.index(f"    {name}:\n", OPENAPI.index("  schemas:\n"))
    match = re.search(r"\n    [A-Z][A-Za-z0-9]+:\n", OPENAPI[start + 1 :])
    return OPENAPI[start:] if match is None else OPENAPI[start : start + 1 + match.start()]


class Phase6ToolingEngineeringControlsContractTest(unittest.TestCase):
    OBJECT_SCHEMAS = (
        "ToolingDefectDetectionContext",
        "ToolingDefectFileEvidence",
        "ToolingDefectAction",
        "ToolingDefectTrialUnavailable",
        "ToolingDefectRevision",
        "ToolingProcessContextEvidence",
        "ToolingProcessComparisonRule",
        "ToolingProcessMetric",
        "ToolingProcessProfileRevision",
        "ToolingProcessComparison",
        "ToolingCapacityInputProvenance",
        "ToolingCapacityLineInput",
        "ToolingCapacityLineResult",
        "ToolingCapacityScenarioResult",
        "ToolingCapacityScenarioRevision",
        "ToolingEngineeringUnavailableField",
        "ToolingHealthUnavailable",
        "ToolingDefectFileEvidenceInput",
        "ToolingDefectActionInput",
        "CreateToolingDefectRevision",
        "ToolingProcessContextInput",
        "ToolingProcessComparisonRuleInput",
        "ToolingProcessMetricInput",
        "CreateToolingProcessProfileRevision",
        "ToolingCapacityLineInputRequest",
        "CreateToolingCapacityScenarioRevision",
        "ToolingEngineeringControlsPermissions",
        "ToolingEngineeringProcessContext",
        "ToolingEngineeringControlsContext",
        "ToolingDefectRevisionCommand",
        "ToolingProcessProfileRevisionCommand",
        "ToolingCapacityScenarioRevisionCommand",
    )

    def test_schemas_and_four_project_first_routes_are_closed_and_active(self) -> None:
        for name in self.OBJECT_SCHEMAS:
            with self.subTest(name=name):
                self.assertIn("additionalProperties: false", _schema(name))
        paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
        for marker in (
            "/engineering-controls:",
            "/defect-revisions:",
            "/process-profile-revisions:",
            "/capacity-scenario-revisions:",
            "getToolingEngineeringControls",
            "createToolingDefectRevision",
            "createToolingProcessProfileRevision",
            "createToolingCapacityScenarioRevision",
        ):
            self.assertIn(marker, paths)
        combined = BFF + API
        for command in (
            "get_tooling_engineering_controls",
            "create_tooling_defect_revision",
            "create_tooling_process_profile_revision",
            "create_tooling_capacity_scenario_revision",
        ):
            self.assertIn(command, BFF)
            self.assertIn(command, API)
        self.assertIn("npi_p6_05_routes_disabled", SECURITY)
        self.assertIn("return value is not False", SECURITY)
        self.assertIn("_p6_05_routes_disabled(command)", BFF)

    def test_command_inputs_exclude_server_owned_and_future_authority(self) -> None:
        defect = _schema("CreateToolingDefectRevision")
        process = _schema("CreateToolingProcessProfileRevision")
        metric = _schema("ToolingProcessMetricInput")
        capacity = _schema("CreateToolingCapacityScenarioRevision")
        line = _schema("ToolingCapacityLineInputRequest")
        self.assertIn("Explicit caller intent only", defect)
        self.assertNotIn("trialReference:", defect)
        self.assertNotIn("layer:", process)
        self.assertNotIn("trial_measurement", _schema("ToolingProcessContextInput"))
        self.assertNotIn("globalId:", metric)
        self.assertNotIn("result:", capacity)
        self.assertNotIn("formulaVersion:", capacity)
        self.assertNotIn("roundingRule:", capacity)
        self.assertNotIn("globalId:", line)

    def test_defect_contract_is_sequential_explicit_and_does_not_mutate_gates(self) -> None:
        defect = _schema("ToolingDefectRevision")
        context = _schema("ToolingDefectDetectionContext")
        trial = _schema("ToolingDefectTrialUnavailable")
        for state in (
            "open", "assigned", "in_progress", "ready_for_verification",
            "closed", "reopened",
        ):
            self.assertIn(state, defect)
        self.assertIn("Explicit intent only; severity never sets it", defect)
        self.assertIn("categoryKey:", defect)
        self.assertIn("maxLength: 128", defect)
        self.assertIn("unavailable_trial_context", context)
        self.assertIn("const: trial_context_unavailable", trial)
        combined = (defect + context + trial).casefold()
        for forbidden in (
            "gateid", "gatepassed", "gateblocked", "workitemid",
            "trialglobalid", "toolinglifecyclestate",
        ):
            self.assertNotIn(forbidden, combined)

    def test_process_contract_separates_layers_and_keeps_color_policy_unavailable(self) -> None:
        profile = _schema("ToolingProcessProfileRevision")
        comparison = _schema("ToolingProcessComparison")
        context = _schema("ToolingProcessContextEvidence")
        self.assertIn("enum: [customer_standard, trial_actual, approved_baseline]", profile)
        self.assertIn("released_document", context)
        self.assertIn("approved_trial", context)
        self.assertIn(
            "enum: [not_measured, within_tolerance, outside_tolerance, unavailable]",
            comparison,
        )
        self.assertIn("ruleSnapshotHash:", comparison)
        self.assertIn("const: variance_exception_color_policy_unavailable", comparison)
        self.assertNotIn("callerStatus", profile + comparison)

    def test_capacity_contract_has_explicit_inputs_formula_and_read_only_results(self) -> None:
        line = _schema("ToolingCapacityLineInput")
        result = _schema("ToolingCapacityScenarioResult")
        scenario = _schema("ToolingCapacityScenarioRevision")
        for marker in (
            "availableHoursPerDay:", "workingDaysPerMonth:", "oeeRatio:",
            "yieldRatio:", "cycleSeconds:", "cavityCount:",
            "usagePerAssembly:", "effectiveSetCount:",
            "selectedToolingSetGlobalIds:", "cycleProvenance:",
            "cavityProvenance:", "usageProvenance:", "setProvenance:",
        ):
            self.assertIn(marker, line)
        for marker in (
            "const: capacity.v1", "const: decimal-6-half-even",
            "parts_per_day", "assembly_units_per_month", "minimum",
            "maximum", "bottleneckLineGlobalIds:", "gap:",
        ):
            self.assertIn(marker, result)
        self.assertIn("readOnly: true", scenario)
        self.assertIn("Deterministically derived by the server", scenario)
        self.assertNotIn("default:", line + result + scenario)
        self.assertNotIn("callerResult", scenario)

    def test_health_projection_is_read_only_unavailable_without_fake_values(self) -> None:
        health = _schema("ToolingHealthUnavailable")
        field = _schema("ToolingEngineeringUnavailableField")
        self.assertIn("const: ERPNEXT", health)
        self.assertIn("const: unavailable", health)
        for reason in (
            "erp_shot_count_unavailable",
            "shot_count_calibration_policy_unavailable",
            "erp_maintenance_projection_unavailable",
            "tooling_health_policy_unavailable",
        ):
            self.assertIn(reason, field)
        combined = (health + field).casefold()
        for forbidden in ("shotcountvalue", "scorevalue", "warning", "recommendation"):
            self.assertNotIn(forbidden, combined)

    def test_ownership_contract_separates_npi_trial_erp_and_policy_authority(self) -> None:
        for object_name in (
            "ToolingDefectRevision",
            "ToolingProcessProfileRevision",
            "ToolingCapacityScenarioRevision",
            "ToolingHealthProjection",
        ):
            self.assertIn(f"  {object_name}:\n", OWNERSHIP)
        self.assertIn("owner: NPI_ONE_TOOLING_ENGINEERING_CONTROLS_COMMAND", OWNERSHIP)
        self.assertIn("owner: FUTURE_PHASE_7_TRIAL_COMMAND", OWNERSHIP)
        self.assertIn("owner: FUTURE_PHASE_7_TRIAL_APPROVAL_COMMAND", OWNERSHIP)
        self.assertIn("owner: ERPNEXT", OWNERSHIP)
        self.assertIn("owner: FUTURE_APPROVED_TOOLING_HEALTH_POLICY", OWNERSHIP)


if __name__ == "__main__":
    unittest.main()
