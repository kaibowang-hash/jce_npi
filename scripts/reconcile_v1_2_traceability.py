#!/usr/bin/env python3
"""Add the reconciled DOCX and clarification IDs to the live trace inventory."""

from __future__ import annotations

import argparse
import csv
import os
import tempfile
from pathlib import Path

TRACE_HEADER = (
    "requirement_id",
    "priority",
    "phase",
    "status",
    "source",
    "evidence",
    "trace_kind",
    "canonical_ids",
)
LEGACY_HEADER = TRACE_HEADER[:6]
DOCX_ONLY_PREFIXES = ("UX-", "ARCH-", "COD-", "I18N-", "FR-TX-")

ADDENDUM_REQUIREMENTS = (
    ("FR-UX-038", "P0", "5", "TECHNICAL_VERIFIED"),
    ("FR-UX-039", "P0", "5", "TECHNICAL_VERIFIED"),
    ("FR-UX-040", "P0", "5", "TECHNICAL_VERIFIED"),
    ("FR-UX-041", "P0", "5", "TECHNICAL_VERIFIED"),
    ("FR-UX-042", "P0", "5", "DECISION_REQUIRED_DR_REC_001"),
    ("FR-UX-043", "P0", "5", "TECHNICAL_VERIFIED"),
    ("FR-PRN-001", "P0", "5", "TECHNICAL_VERIFIED"),
    ("FR-PRN-002", "P0", "5", "TECHNICAL_VERIFIED"),
    ("FR-PRN-003", "P0", "5", "DECISION_REQUIRED_DR_REC_003_004"),
    ("FR-INT-015", "P1", "8", "PLANNED_NPI_SIDE_READ_ONLY_PROJECTION"),
    ("FR-BR-001", "P0", "5", "TECHNICAL_VERIFIED"),
    ("FR-BR-002", "P1", "8", "PLANNED_PHASE_8_APPROVED_JCE_CORE_ASSET"),
    ("FR-TX-019", "P0", "6", "ANCHORED_P6_05"),
    ("FR-TX-020", "P0", "6", "DECISION_REQUIRED_DR_REC_002"),
)
UX_REMEDIATION_ALLOCATION = {
    "UX-003": ("9", "PLANNED_FULL_PRODUCT_UAT"),
    "UX-004": ("6", "TECHNICAL_VERIFIED_FOUNDATION"),
    "UX-007": ("5", "TECHNICAL_VERIFIED_FOUNDATION"),
    "UX-011": ("5", "TECHNICAL_VERIFIED"),
    "UX-016": ("8", "ANCHORED_P6_07_PHASE_8_ASYNC_JOB_TRUTH"),
    "UX-018": ("5", "TECHNICAL_VERIFIED_FOUNDATION"),
    "UX-020": ("7", "PLANNED_PHASE_7_MOBILE_FIELD_ACTIONS"),
    "UX-026": ("5", "PROTOTYPE_VERIFIED_BACKEND_APPROVAL_HELD"),
    "UX-027": ("5", "TECHNICAL_VERIFIED_FOUNDATION"),
    "UX-028": ("5", "TECHNICAL_VERIFIED_FOUNDATION_AUTHORITY_HELD"),
    "UX-030": ("5", "TECHNICAL_VERIFIED_GOVERNANCE_PRODUCT_APPROVAL_HELD"),
    "UX-035": ("5", "TECHNICAL_VERIFIED_CURRENT_P0_SCOPE"),
    "UX-036": ("5", "TECHNICAL_VERIFIED_CURRENT_P0_SCOPE"),
}
P6_TOOLING_ALLOCATION = {
    "FR-TX-001": "TECHNICAL_VERIFIED_FOUNDATION",
    "FR-TX-002": "TECHNICAL_VERIFIED",
    "FR-TX-003": "ANCHORED_P6_02",
    "FR-TX-004": "ANCHORED_P6_03",
    "FR-TX-005": "ANCHORED_P6_03",
    "FR-TX-006": "ANCHORED_P6_03",
    "FR-TX-007": "ANCHORED_P6_03",
    "FR-TX-008": "ANCHORED_P6_03",
    "FR-TX-009": "ANCHORED_P6_05",
    "FR-TX-010": "ANCHORED_P6_05",
    "FR-TX-011": "ANCHORED_P6_05",
    "FR-TX-012": "ANCHORED_P6_07",
    "FR-TX-013": "ANCHORED_P6_07",
    "FR-TX-014": "ANCHORED_P6_07",
    "FR-TX-015": "ANCHORED_P6_07",
    "FR-TX-016": "ANCHORED_P6_07",
    "FR-TX-017": "ANCHORED_P6_07",
    "FR-TX-018": "ANCHORED_P6_07",
}
R1_03_EVIDENCE = {
    "FR-UX-039": (
        "apps/npi_core/npi_core/localization_api.py",
        "contracts/npi-api.openapi.yaml",
        "frontend/src/api/session.ts",
        "frontend/src/app/app-shell.tsx",
        "frontend/tests/e2e/r1-03-shell.spec.ts",
        "scripts/verify_frappe_runtime.py",
        "implementation/evidence/reconciliation/r1-03-validation.md",
    ),
    "UX-011": (
        "frontend/src/app/app-shell.tsx",
        "frontend/src/pages/project-governance-workspace.tsx",
        "frontend/tests/unit/project-governance-workspace.test.tsx",
        "frontend/tests/e2e/r1-03-shell.spec.ts",
        "implementation/evidence/reconciliation/r1-03-validation.md",
    ),
    "UX-018": (
        "frontend/src/app/command-palette.tsx",
        "frontend/src/app/router.ts",
        "frontend/tests/unit/pages-and-shell.test.tsx",
        "frontend/tests/unit/router.test.tsx",
        "frontend/tests/e2e/r1-03-shell.spec.ts",
        "implementation/evidence/reconciliation/r1-03-validation.md",
    ),
}
R1_04_EVIDENCE = {
    "FR-UX-038": (
        "apps/npi_core/npi_core/grid_personalization/domain.py",
        "apps/npi_core/npi_core/grid_personalization/frappe_repository.py",
        "apps/npi_core/npi_core/grid_personalization_api.py",
        "contracts/npi-api.openapi.yaml",
        "frontend/src/ui-adapters/dense-grid-layout.ts",
        "frontend/src/ui-adapters/dense-grid.tsx",
        "frontend/src/components/live-my-worklist.tsx",
        "frontend/tests/unit/dense-grid.test.tsx",
        "frontend/tests/e2e/r1-04-grid.spec.ts",
        "scripts/verify_grid_personalization_runtime.py",
        "implementation/evidence/reconciliation/r1-04-validation.md",
    ),
    "UX-007": (
        "frontend/src/ui-adapters/dense-grid.tsx",
        "frontend/src/components/live-my-worklist.tsx",
        "frontend/src/components/worklist.tsx",
        "frontend/tests/unit/dense-grid.test.tsx",
        "frontend/tests/e2e/r1-04-grid.spec.ts",
        "implementation/evidence/reconciliation/r1-04-validation.md",
        "implementation/phase-6-requirement-anchor.md",
        "implementation/evidence/phase-6/p6-00-validation.md",
    ),
    "UX-027": (
        "apps/npi_core/npi_core/grid_personalization/controller.py",
        "apps/npi_core/npi_core/grid_personalization/frappe_repository.py",
        "apps/npi_core/npi_core/grid_personalization_api.py",
        "apps/npi_core/npi_core/npi_core/doctype/npi_my_work_grid_preference/npi_my_work_grid_preference.json",
        "frontend/src/api/grid-preferences-data-source.ts",
        "frontend/src/components/my-work-grid-personalization.ts",
        "frontend/src/components/live-my-worklist.tsx",
        "frontend/tests/unit/grid-preferences-data-source.test.ts",
        "frontend/tests/unit/my-work-grid-personalization.test.tsx",
        "tests/test_r1_04_grid_personalization_repository_api.py",
        "frontend/tests/e2e/r1-04-grid.spec.ts",
        "scripts/verify_grid_personalization_runtime.py",
        "implementation/evidence/reconciliation/r1-04-validation.md",
    ),
    "UX-028": (
        "apps/npi_core/npi_core/grid_personalization/controller.py",
        "apps/npi_core/npi_core/grid_personalization/domain.py",
        "apps/npi_core/npi_core/grid_personalization/frappe_repository.py",
        "apps/npi_core/npi_core/npi_core/doctype/npi_published_grid_view/npi_published_grid_view.json",
        "apps/npi_core/npi_core/npi_core/doctype/npi_published_grid_view_revision/npi_published_grid_view_revision.json",
        "tests/test_r1_04_grid_personalization_domain.py",
        "tests/test_r1_04_grid_personalization_repository_api.py",
        "scripts/verify_grid_personalization_runtime.py",
        "implementation/evidence/reconciliation/r1-04-plan.md",
        "implementation/evidence/reconciliation/r1-04-validation.md",
    ),
    "UX-035": (
        "frontend/src/components/live-my-worklist.tsx",
        "frontend/src/styles/app.css",
        "frontend/tests/e2e/r1-04-grid.spec.ts",
        "frontend/tests/e2e/r1-04-grid.spec.ts-snapshots/r1-04-grid-en-1440x900-100-linux.png",
        "frontend/tests/e2e/r1-04-grid.spec.ts-snapshots/r1-04-grid-zh-1440x900-100-linux.png",
        "frontend/tests/e2e/r1-04-grid.spec.ts-snapshots/r1-04-grid-zh-TW-1440x900-100-linux.png",
        "implementation/evidence/reconciliation/r1-04-validation.md",
    ),
}
R1_05_STAGE_1_EVIDENCE = {
    "FR-UX-040": (
        "apps/npi_core/npi_core/inspector_preferences/domain.py",
        "apps/npi_core/npi_core/inspector_preferences/frappe_repository.py",
        "apps/npi_core/npi_core/inspector_preferences_api.py",
        "apps/npi_core/npi_core/bff.py",
        "contracts/npi-api.openapi.yaml",
        "frontend/src/api/my-work-inspector-preferences-data-source.ts",
        "frontend/src/ui-adapters/resizable-pane.tsx",
        "frontend/src/components/my-work-inspector-personalization.ts",
        "frontend/src/components/live-my-worklist.tsx",
        "frontend/tests/unit/resizable-pane-separator.test.tsx",
        "frontend/tests/unit/my-work-inspector-personalization.test.tsx",
        "frontend/tests/unit/my-work-inspector-preferences-data-source.test.ts",
        "tests/test_r1_05_inspector_preferences_domain.py",
        "tests/test_r1_05_inspector_preferences_api.py",
        "tests/test_r1_05_inspector_preferences_contract.py",
        "frontend/tests/e2e/r1-05-panes.spec.ts",
        "scripts/verify_frappe_runtime.py",
        "scripts/verify_project_controls_runtime.py",
        "implementation/evidence/reconciliation/r1-05-stage-1-validation.md",
    ),
}
R1_05_STAGE_2_EVIDENCE = {
    "FR-UX-041": (
        "frontend/src/components/attachment-workflow.ts",
        "frontend/src/components/field-attachment-primitives.tsx",
        "frontend/src/pages/trial-page.tsx",
        "frontend/src/pages/gate-evidence-page.tsx",
        "frontend/src/styles/app.css",
        "frontend/tests/unit/field-attachment-primitives.test.tsx",
        "frontend/tests/unit/pages-and-shell.test.tsx",
        "frontend/tests/unit/gate-evidence-page.test.tsx",
        "frontend/tests/e2e/r1-05-field-attachments.spec.ts",
        "frontend/tests/e2e/states-locales-accessibility.spec.ts",
        "apps/npi_core/npi_core/translations/zh.csv",
        "apps/npi_core/npi_core/translations/zh-TW.csv",
        "frontend/src/generated/catalogs.ts",
        "implementation/evidence/reconciliation/r1-05-stage-2-validation.md",
    ),
}
R1_05_STAGE_3_EVIDENCE = {
    "FR-UX-043": (
        "frontend/src/ui-adapters/action-policy.ts",
        "frontend/src/ui-adapters/npi-ui.tsx",
        "frontend/src/components/field-attachment-primitives.tsx",
        "frontend/src/components/object-components.tsx",
        "frontend/src/styles/app.css",
        "frontend/scripts/verify-boundaries.mjs",
        "frontend/tests/unit/action-policy.test.ts",
        "frontend/tests/unit/compact-action.test.tsx",
        "frontend/tests/e2e/r1-05-panes.spec.ts",
        "frontend/tests/e2e/r1-05-field-attachments.spec.ts",
        "implementation/evidence/reconciliation/r1-05-stage-3-validation.md",
    ),
}
R1_06_STAGE_1_EVIDENCE = {
    requirement_id: (
        "frontend/src/components/controlled-undo-prototype-model.ts",
        "frontend/src/components/controlled-undo-prototype.tsx",
        "frontend/src/pages/work-page.tsx",
        "frontend/src/styles/app.css",
        "apps/npi_core/npi_core/translations/zh.csv",
        "apps/npi_core/npi_core/translations/zh-TW.csv",
        "frontend/src/generated/catalogs.ts",
        "frontend/tests/unit/controlled-undo-prototype.test.tsx",
        "frontend/tests/e2e/r1-06-controlled-undo-prototype.spec.ts",
        "implementation/prototype-approvals/r1-06-my-work-grid-reset.json",
        "scripts/verify_prototype_approvals.py",
        "tests/test_prototype_approvals.py",
        "implementation/evidence/reconciliation/r1-06-stage-1-prototype-review.md",
        "implementation/evidence/reconciliation/r1-06-stage-1-validation.md",
    )
    for requirement_id in ("UX-026", "UX-030")
}
R1_06_STAGE_3_EVIDENCE = {
    "UX-035": R1_04_EVIDENCE["UX-035"]
    + (
        ".github/workflows/ci.yml",
        "frontend/tests/e2e/p0-visual-registry.json",
        "frontend/tests/e2e/r1-06-p0-visual-governance.spec.ts",
        "scripts/verify_devcontainer.py",
        "scripts/verify_p0_visual_governance.py",
        "tests/test_devcontainer_verifier.py",
        "tests/test_p0_visual_governance.py",
        "implementation/evidence/reconciliation/r1-06-stage-3-validation.md",
        "implementation/evidence/reconciliation/r1-06-validation.md",
    ),
    "UX-036": (
        ".github/workflows/ci.yml",
        "frontend/tests/e2e/p0-visual-registry.json",
        "frontend/tests/e2e/r1-06-p0-visual-governance.spec.ts",
        "frontend/tests/e2e/visual-matrix.spec.ts",
        "frontend/tests/e2e/states-locales-accessibility.spec.ts",
        "implementation/evidence/phase-3/visual-review.md",
        "scripts/verify_devcontainer.py",
        "scripts/verify_p0_visual_governance.py",
        "tests/test_devcontainer_verifier.py",
        "tests/test_p0_visual_governance.py",
        "implementation/evidence/reconciliation/r1-06-stage-3-validation.md",
        "implementation/evidence/reconciliation/r1-06-validation.md",
    ),
}
P5_06_PLAN_EVIDENCE = {
    "FR-PRN-001": (
        "implementation/V1_2_RECONCILIATION_DECISIONS.md",
        "implementation/phase-5-requirement-anchor.md",
        "apps/npi_core/npi_core/controlled_print/domain.py",
        "apps/npi_core/npi_core/controlled_print/frappe_repository.py",
        "apps/npi_core/npi_core/controlled_print_api.py",
        "contracts/npi-api.openapi.yaml",
        "frontend/src/components/controlled-print-action.tsx",
        "tests/test_phase5_controlled_print_repository.py",
        "scripts/verify_controlled_print_runtime.py",
        "implementation/evidence/phase-5/p5-06-validation.md",
        "implementation/phase-5-gate.md",
    ),
    "FR-PRN-002": (
        "implementation/V1_2_RECONCILIATION_DECISIONS.md",
        "implementation/phase-5-requirement-anchor.md",
        "apps/npi_core/npi_core/controlled_print/rendering.py",
        "apps/npi_core/npi_core/controlled_print/qr.py",
        "apps/npi_core/npi_core/controlled_print/frappe_repository.py",
        "frontend/src/api/controlled-print-data-source.ts",
        "tests/test_phase5_controlled_print_rendering.py",
        "tests/test_phase5_controlled_print_repository_transaction.py",
        "scripts/verify_controlled_print_runtime.py",
        "implementation/evidence/phase-5/p5-06-validation.md",
        "implementation/phase-5-gate.md",
    ),
}
P6_ANCHOR_EVIDENCE = (
    "implementation/V1_2_RECONCILIATION_DECISIONS.md",
    "implementation/phase-6-requirement-anchor.md",
    "implementation/evidence/phase-6/p6-00-validation.md",
)
P6_UX_ANCHOR_EVIDENCE = {
    requirement_id: (
        "implementation/V1_2_DOCX_PACK_COVERAGE_MATRIX.csv",
        "docs/V1_2_RECONCILIATION_ADDENDUM.md",
        "implementation/phase-6-requirement-anchor.md",
        "implementation/evidence/phase-6/p6-00-validation.md",
    )
    for requirement_id in ("UX-004", "UX-016")
}
P6_01_COMPLETED_EVIDENCE = {
    "FR-TX-001": (
        "apps/npi_core/npi_core/tooling/domain.py",
        "apps/npi_core/npi_core/tooling/frappe_repository.py",
        "tests/test_phase6_tooling_domain.py",
        "scripts/verify_tooling_runtime.py",
        "implementation/evidence/phase-6/p6-01-validation.md",
        "distinct Part Revision Requirement Master and Applicability are proven while Tooling Revision Set and Trial remain later tasks",
    ),
    "FR-TX-002": (
        "apps/npi_core/npi_core/tooling/domain.py",
        "apps/npi_core/npi_core/tooling/frappe_repository.py",
        "tests/test_phase6_tooling_repository.py",
        "scripts/verify_tooling_runtime.py",
        "frontend/src/pages/live-tooling-page.tsx",
        "implementation/evidence/phase-6/p6-01-validation.md",
        "one shared Master is reused through immutable versioned effective Applicability without cloning",
    ),
}
P6_UX_ANCHOR_EVIDENCE["UX-004"] = (
    "frontend/src/api/tooling-data-source.ts",
    "frontend/src/pages/live-tooling-page.tsx",
    "frontend/tests/unit/live-tooling-page.test.tsx",
    "frontend/tests/e2e/p6-01-tooling-live.spec.ts",
    "implementation/evidence/phase-6/p6-01-validation.md",
    "live dense identity and Applicability cockpit is proven while later Tooling sections remain honestly unavailable",
)


class TraceError(RuntimeError):
    """Raised when the reconciliation trace is incomplete or inconsistent."""


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or ()), list(reader)


def _docx_only_ids(requirement_rows: list[dict[str, str]]) -> list[str]:
    return [
        row["requirement_id"]
        for row in requirement_rows
        if row["requirement_id"].startswith(DOCX_ONLY_PREFIXES)
    ]


def _phase_and_status(requirement_id: str, coverage_status: str) -> tuple[str, str]:
    if requirement_id.startswith("UX-"):
        if coverage_status in {"PARTIAL_EXPLICIT", "OTHER_ISOLATED_CASE"}:
            try:
                return UX_REMEDIATION_ALLOCATION[requirement_id]
            except KeyError as error:
                raise TraceError(
                    f"missing executable allocation for {requirement_id}"
                ) from error
        return "3", "RECONCILED_ALIAS_LINKED_TO_CANONICAL_IDS"
    if requirement_id.startswith(("ARCH-", "COD-")):
        return "0", "RECONCILED_GOVERNANCE_LINKED_NON_PRODUCT"
    if requirement_id.startswith("I18N-"):
        return "3", "RECONCILED_ALIAS_LINKED_TO_CANONICAL_IDS"
    if requirement_id.startswith("FR-TX-"):
        try:
            return "6", P6_TOOLING_ALLOCATION[requirement_id]
        except KeyError as error:
            raise TraceError(
                f"missing Phase 6 allocation for {requirement_id}"
            ) from error
    raise TraceError(f"unexpected DOCX-only requirement ID: {requirement_id}")


def _expanded_rows(
    trace_rows: list[dict[str, str]],
    requirements: list[dict[str, str]],
    coverage_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    coverage = {row["docx_requirement_id"]: row for row in coverage_rows}
    if len(coverage) != 229:
        raise TraceError("coverage matrix must contain 229 unique DOCX IDs")

    expanded: list[dict[str, str]] = []
    for row in trace_rows:
        has_reconciled_columns = "trace_kind" in row and "canonical_ids" in row
        expanded.append(
            {
                **{key: row.get(key, "") for key in LEGACY_HEADER},
                "trace_kind": (
                    row["trace_kind"] if has_reconciled_columns else "PACK_CANONICAL"
                ),
                "canonical_ids": (
                    row["canonical_ids"]
                    if has_reconciled_columns
                    else row["requirement_id"]
                ),
            }
        )

    existing_ids = {row["requirement_id"] for row in expanded}
    expanded_by_id = {row["requirement_id"]: row for row in expanded}
    for requirement in requirements:
        requirement_id = requirement["requirement_id"]
        if not requirement_id.startswith(DOCX_ONLY_PREFIXES):
            continue
        matrix_row = coverage[requirement_id]
        phase, status = _phase_and_status(
            requirement_id,
            matrix_row["coverage_status_before_reconciliation"],
        )
        evidence = (
            "implementation/V1_2_DOCX_PACK_COVERAGE_MATRIX.csv; "
            "docs/V1_2_RECONCILIATION_ADDENDUM.md"
        )
        if requirement_id.startswith("FR-TX-"):
            evidence += "; docs/TOOLING_LIST_IMPORT_SPEC.md"
        if requirement_id in R1_03_EVIDENCE:
            evidence = "; ".join(R1_03_EVIDENCE[requirement_id])
        if requirement_id in R1_04_EVIDENCE:
            evidence = "; ".join(R1_04_EVIDENCE[requirement_id])
        if requirement_id in R1_05_STAGE_1_EVIDENCE:
            evidence = "; ".join(R1_05_STAGE_1_EVIDENCE[requirement_id])
        if requirement_id in R1_05_STAGE_2_EVIDENCE:
            evidence = "; ".join(R1_05_STAGE_2_EVIDENCE[requirement_id])
        if requirement_id in R1_05_STAGE_3_EVIDENCE:
            evidence = "; ".join(R1_05_STAGE_3_EVIDENCE[requirement_id])
        if requirement_id in R1_06_STAGE_1_EVIDENCE:
            evidence = "; ".join(R1_06_STAGE_1_EVIDENCE[requirement_id])
        if requirement_id in R1_06_STAGE_3_EVIDENCE:
            evidence = "; ".join(R1_06_STAGE_3_EVIDENCE[requirement_id])
        if requirement_id in P6_UX_ANCHOR_EVIDENCE:
            evidence = "; ".join(P6_UX_ANCHOR_EVIDENCE[requirement_id])
        if requirement_id in P6_01_COMPLETED_EVIDENCE:
            evidence = "; ".join(P6_01_COMPLETED_EVIDENCE[requirement_id])
        elif requirement_id in P6_TOOLING_ALLOCATION:
            evidence = "; ".join(
                (
                    "implementation/V1_2_DOCX_PACK_COVERAGE_MATRIX.csv",
                    "docs/V1_2_RECONCILIATION_ADDENDUM.md",
                    "docs/TOOLING_LIST_IMPORT_SPEC.md",
                    "implementation/phase-6-requirement-anchor.md",
                    "implementation/evidence/phase-6/p6-00-validation.md",
                )
            )
        normalized_row = {
            "requirement_id": requirement_id,
            "priority": requirement["priority"],
            "phase": phase,
            "status": status,
            "source": "implementation/V1_2_DOCX_REQUIREMENTS.csv",
            "evidence": evidence,
            "trace_kind": "DOCX_RECONCILED",
            "canonical_ids": matrix_row["pack_requirement_ids"],
        }
        if requirement_id in existing_ids:
            expanded_by_id[requirement_id].clear()
            expanded_by_id[requirement_id].update(normalized_row)
        else:
            expanded.append(normalized_row)
            expanded_by_id[requirement_id] = normalized_row
        existing_ids.add(requirement_id)

    for requirement_id, priority, phase, status in ADDENDUM_REQUIREMENTS:
        evidence = "implementation/V1_2_RECONCILIATION_DECISIONS.md"
        if requirement_id == "FR-BR-001":
            evidence = (
                "frontend/src/ui-adapters/display-brand.tsx; "
                "frontend/scripts/verify-display-brand.mjs; "
                "frontend/tests/unit/display-brand.test.tsx; "
                "frontend/tests/e2e/display-brand.spec.ts; "
                "implementation/evidence/reconciliation/r1-02-validation.md"
            )
        if requirement_id in R1_03_EVIDENCE:
            evidence = "; ".join(R1_03_EVIDENCE[requirement_id])
        if requirement_id in R1_04_EVIDENCE:
            evidence = "; ".join(R1_04_EVIDENCE[requirement_id])
        if requirement_id in R1_05_STAGE_1_EVIDENCE:
            evidence = "; ".join(R1_05_STAGE_1_EVIDENCE[requirement_id])
        if requirement_id in R1_05_STAGE_2_EVIDENCE:
            evidence = "; ".join(R1_05_STAGE_2_EVIDENCE[requirement_id])
        if requirement_id in R1_05_STAGE_3_EVIDENCE:
            evidence = "; ".join(R1_05_STAGE_3_EVIDENCE[requirement_id])
        if requirement_id in R1_06_STAGE_1_EVIDENCE:
            evidence = "; ".join(R1_06_STAGE_1_EVIDENCE[requirement_id])
        if requirement_id in R1_06_STAGE_3_EVIDENCE:
            evidence = "; ".join(R1_06_STAGE_3_EVIDENCE[requirement_id])
        if requirement_id in P5_06_PLAN_EVIDENCE:
            evidence = "; ".join(P5_06_PLAN_EVIDENCE[requirement_id])
        if requirement_id in {"FR-TX-019", "FR-TX-020"}:
            evidence = "; ".join(P6_ANCHOR_EVIDENCE)
        normalized_row = {
            "requirement_id": requirement_id,
            "priority": priority,
            "phase": phase,
            "status": status,
            "source": "docs/V1_2_RECONCILIATION_ADDENDUM.md",
            "evidence": evidence,
            "trace_kind": "ADDENDUM_DIRECT",
            "canonical_ids": requirement_id,
        }
        if requirement_id in existing_ids:
            expanded_by_id[requirement_id].clear()
            expanded_by_id[requirement_id].update(normalized_row)
        else:
            expanded.append(normalized_row)
            expanded_by_id[requirement_id] = normalized_row
        existing_ids.add(requirement_id)

    return expanded


def validate(
    rows: list[dict[str, str]],
    requirements: list[dict[str, str]],
    coverage_rows: list[dict[str, str]],
) -> None:
    if len(rows) != 282:
        raise TraceError(f"expected 282 reconciliation trace rows; found {len(rows)}")
    trace_ids = [row["requirement_id"] for row in rows]
    if len(set(trace_ids)) != 282:
        raise TraceError("reconciliation trace IDs are not unique")

    docx_ids = {row["requirement_id"] for row in requirements}
    if len(docx_ids) != 229 or not docx_ids.issubset(trace_ids):
        raise TraceError("the trace does not retain every one of the 229 DOCX IDs")

    addendum_ids = {row[0] for row in ADDENDUM_REQUIREMENTS}
    if not addendum_ids.issubset(trace_ids):
        raise TraceError("the trace is missing one or more clarification IDs")

    pack_only_ids = set(trace_ids) - docx_ids - addendum_ids
    if len(pack_only_ids) != 39:
        raise TraceError(
            f"expected 39 Pack-only normalized IDs; found {len(pack_only_ids)}"
        )

    kinds = {row["trace_kind"] for row in rows}
    if kinds != {"PACK_CANONICAL", "DOCX_RECONCILED", "ADDENDUM_DIRECT"}:
        raise TraceError(f"unexpected trace kinds: {sorted(kinds)}")

    by_id = {row["requirement_id"]: row for row in rows}
    coverage = {row["docx_requirement_id"]: row for row in coverage_rows}
    for requirement_id in _docx_only_ids(requirements):
        trace_row = by_id[requirement_id]
        if trace_row["trace_kind"] != "DOCX_RECONCILED":
            raise TraceError(f"{requirement_id} must be a DOCX_RECONCILED trace")
        if (
            trace_row["canonical_ids"]
            != coverage[requirement_id]["pack_requirement_ids"]
        ):
            raise TraceError(
                f"{requirement_id} canonical mapping differs from the matrix"
            )
        if not trace_row["source"] or not trace_row["evidence"]:
            raise TraceError(f"{requirement_id} lacks source/evidence")


def _write_atomic(path: Path, rows: list[dict[str, str]]) -> None:
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent, text=True
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(
                stream, fieldnames=TRACE_HEADER, lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--trace",
        type=Path,
        default=Path("implementation/REQUIREMENT_TRACEABILITY.csv"),
    )
    parser.add_argument(
        "--requirements",
        type=Path,
        default=Path("implementation/V1_2_DOCX_REQUIREMENTS.csv"),
    )
    parser.add_argument(
        "--coverage",
        type=Path,
        default=Path("implementation/V1_2_DOCX_PACK_COVERAGE_MATRIX.csv"),
    )
    parser.add_argument("--apply", action="store_true")
    arguments = parser.parse_args()

    trace_header, trace_rows = _read_csv(arguments.trace)
    if tuple(trace_header) not in {LEGACY_HEADER, TRACE_HEADER}:
        raise TraceError(f"unexpected trace header: {trace_header}")
    _, requirements = _read_csv(arguments.requirements)
    _, coverage_rows = _read_csv(arguments.coverage)

    rows = _expanded_rows(trace_rows, requirements, coverage_rows)
    validate(rows, requirements, coverage_rows)

    if arguments.apply:
        _write_atomic(arguments.trace, rows)
    elif tuple(trace_header) != TRACE_HEADER or trace_rows != rows:
        raise TraceError("traceability is not in the reconciled canonical form")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
