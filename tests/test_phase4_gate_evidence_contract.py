from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")
LINES = CONTRACT.splitlines()
OWNERSHIP = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")


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


def _schema(name: str) -> str:
    return _indented_block(f"    {name}:")


def _required(schema_name: str) -> tuple[str, ...]:
    block = _schema(schema_name)
    flow = re.search(r"^      required:\s*\[([^]]*)\]", block, re.MULTILINE)
    if flow is not None:
        return tuple(item.strip() for item in flow.group(1).split(",") if item.strip())
    lines = block.splitlines()
    try:
        start = lines.index("      required:") + 1
    except ValueError as error:
        raise AssertionError(f"{schema_name} has no required fields") from error
    result: list[str] = []
    for line in lines[start:]:
        if line.startswith("        - "):
            result.append(line.removeprefix("        - ").strip())
            continue
        if line.strip():
            break
    return tuple(result)


def _property_names(schema_name: str) -> set[str]:
    return set(
        re.findall(
            r"^        ([A-Za-z][A-Za-z0-9]*):",
            _schema(schema_name),
            re.MULTILINE,
        )
    )


class Phase4GateEvidenceContractTest(unittest.TestCase):
    def test_live_gate_routes_are_strict_business_operations(self) -> None:
        workspace = _indented_block("  /projects/{projectId}/gates/{gateId}/evidence:")
        freeze = _indented_block(
            "  /projects/{projectId}/gates/{gateId}:freeze-requirements:"
        )
        attach = _indented_block(
            "  /projects/{projectId}/gates/{gateId}/requirements/{requirementKey}/evidence:"
        )
        self.assertIn("operationId: getGateEvidenceWorkspace", workspace)
        self.assertIn("same 404 representation", workspace)
        self.assertIn("Raw private-file URLs", workspace)
        self.assertIn(
            '$ref: "#/components/schemas/GateEvidenceWorkspace"',
            workspace,
        )

        self.assertIn("operationId: freezeGateRequirements", freeze)
        self.assertIn("x-required-roles: [System Manager]", freeze)
        self.assertIn("x-audit-operation: gate.requirements.freeze", freeze)
        self.assertIn('$ref: "#/components/parameters/CsrfToken"', freeze)
        self.assertIn('$ref: "#/components/parameters/IdempotencyKey"', freeze)
        self.assertIn(
            '$ref: "#/components/schemas/FreezeGateRequirements"',
            freeze,
        )

        self.assertIn("operationId: attachGateEvidence", attach)
        self.assertIn("rejects", attach)
        self.assertIn("raw URLs", attach)
        self.assertIn("client-selected scan state", attach)
        self.assertIn(
            '$ref: "#/components/schemas/AttachGateEvidence"',
            attach,
        )

    def test_gate_command_inputs_are_closed_and_exact(self) -> None:
        freeze_fields = (
            "expectedGateVersion",
            "gateDueDate",
            "requirements",
        )
        attach_fields = (
            "expectedGateVersion",
            "evidenceKind",
            "sourceGlobalId",
            "sourceVersion",
            "sourceHash",
        )
        self.assertEqual(_required("FreezeGateRequirements"), freeze_fields)
        self.assertEqual(
            _property_names("FreezeGateRequirements"),
            set(freeze_fields),
        )
        self.assertIn(
            "additionalProperties: false",
            _schema("FreezeGateRequirements"),
        )
        self.assertEqual(_required("AttachGateEvidence"), attach_fields)
        self.assertEqual(
            _property_names("AttachGateEvidence"),
            set(attach_fields),
        )
        self.assertIn(
            "additionalProperties: false",
            _schema("AttachGateEvidence"),
        )
        self.assertIn(
            "enum: [wbs_item, file_revision, release_baseline]",
            _schema("AttachGateEvidence"),
        )
        self.assertIn(
            'pattern: "^[a-f0-9]{64}$"',
            _schema("AttachGateEvidence"),
        )
        self.assertNotIn("url", _schema("AttachGateEvidence").casefold())
        self.assertNotIn("scanstate", _schema("AttachGateEvidence").casefold())

    def test_workspace_is_closed_and_exposes_scan_truth_without_decisions(
        self,
    ) -> None:
        expected = (
            "project",
            "gate",
            "requirements",
            "baselineImpacts",
            "summary",
            "permissions",
        )
        self.assertEqual(_required("GateEvidenceWorkspace"), expected)
        self.assertEqual(
            _property_names("GateEvidenceWorkspace"),
            set(expected),
        )
        self.assertIn(
            "additionalProperties: false",
            _schema("GateEvidenceWorkspace"),
        )
        self.assertIn(
            '$ref: "#/components/schemas/DocumentBaselineImpactEvent"',
            _schema("GateEvidenceWorkspace"),
        )
        file_metadata = _schema("GateEvidenceFileMetadata")
        self.assertIn(
            "enum: [pending, clean, infected, failed]",
            file_metadata,
        )
        self.assertNotIn("url:", file_metadata.casefold())
        reference = _schema("GateEvidenceReference")
        self.assertIn(
            '$ref: "#/components/schemas/GateWbsEvidenceReference"',
            reference,
        )
        self.assertIn(
            '$ref: "#/components/schemas/GateFileEvidenceReference"',
            reference,
        )
        self.assertIn(
            '$ref: "#/components/schemas/GateBaselineEvidenceReference"',
            reference,
        )
        wbs_reference = _schema("GateWbsEvidenceReference")
        file_reference = _schema("GateFileEvidenceReference")
        baseline_reference = _schema("GateBaselineEvidenceReference")
        self.assertIn("kind: { type: string, const: wbs_item }", wbs_reference)
        self.assertIn(
            "sourceObjectType: { type: string, const: wbs_item }",
            wbs_reference,
        )
        self.assertNotIn("        file:", wbs_reference)
        self.assertIn(
            "kind: { type: string, const: file_revision }",
            file_reference,
        )
        self.assertIn(
            "sourceObjectType: { type: string, const: file_revision }",
            file_reference,
        )
        self.assertIn("file", _required("GateFileEvidenceReference"))
        self.assertIn(
            "kind: { type: string, const: release_baseline }",
            baseline_reference,
        )
        self.assertIn(
            "sourceObjectType: { type: string, const: release_baseline }",
            baseline_reference,
        )
        self.assertIn("revision: { type: integer, const: 1 }", baseline_reference)
        self.assertIn("baseline", _required("GateBaselineEvidenceReference"))
        self.assertIn(
            '$ref: "#/components/schemas/DocumentBaselineSummary"',
            baseline_reference,
        )
        self.assertIn("additionalProperties: false", wbs_reference)
        self.assertIn("additionalProperties: false", file_reference)
        self.assertIn("additionalProperties: false", baseline_reference)

        workspace = "\n".join(
            _schema(name)
            for name in (
                "GateEvidenceWorkspace",
                "GateEvidenceGate",
                "GateFrozenRequirement",
                "GateEvidenceReference",
                "GateWbsEvidenceReference",
                "GateFileEvidenceReference",
                "GateBaselineEvidenceReference",
                "GateEvidenceSummary",
            )
        ).casefold()
        for prohibited in (
            "conditional_pass",
            "waiver",
            "reopen",
            "decisionoptions",
            "satisfied",
        ):
            self.assertNotIn(prohibited, workspace)
        self.assertIn("not a gate pass", workspace)
        self.assertIn("not a gate readiness", workspace)

    def test_gate_and_file_data_ownership_is_explicit(self) -> None:
        for object_name in (
            "GateTemplate",
            "GateInstance",
            "GateEvidenceReference",
            "FileRevision",
        ):
            with self.subTest(object_name=object_name):
                self.assertIn(
                    f"  {object_name}:\n    owner_system: NPI_ONE",
                    OWNERSHIP,
                )
        self.assertIn(
            "raw_private_url: {owner: FRAPPE_FILE_SERVICE",
            OWNERSHIP,
        )
        self.assertIn(
            "conflict: NEVER_EXPOSE_AS_PROJECT_AUTHORIZATION",
            OWNERSHIP,
        )
        self.assertIn(
            "decision_state: {owner: VERSIONED_GATE_POLICY",
            OWNERSHIP,
        )


if __name__ == "__main__":
    unittest.main()
