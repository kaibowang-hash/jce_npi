#!/usr/bin/env python3
"""Generate the reviewed DOCX-to-Pack reconciliation coverage matrix."""

from __future__ import annotations

import argparse
import csv
import io
import os
import tempfile
from collections import Counter
from pathlib import Path

MATRIX_HEADER = (
    "docx_requirement_id",
    "docx_priority",
    "coverage_status_before_reconciliation",
    "pack_requirement_ids",
    "pre_reconciliation_sources",
    "pre_reconciliation_checkpoint",
    "reconciliation_action",
    "post_reconciliation_state",
    "notes",
)
PRE_RECONCILIATION_CHECKPOINT = "930b5a28cb995df12f251994a36f7502525ed94a"

EXPECTED_COVERAGE_COUNTS = {
    "EXPLICIT_SAME_ID": 134,
    "EXPLICIT_EQUIVALENT": 23,
    "GOVERNANCE_COVERED_NOT_REQUIREMENT_TRACEABLE": 22,
    "NARRATIVE_EXPLICIT_NOT_TRACEABLE": 12,
    "EXPLICIT_CONSOLIDATED_NO_ALIAS": 7,
    "PARTIAL_EXPLICIT": 9,
    "PARTIAL_NARRATIVE": 5,
    "NARRATIVE_ONLY_HIGH_RISK": 5,
    "MISSING_UNIQUE_REQUIREMENT": 7,
    "OTHER_ISOLATED_CASE": 5,
}

UX_EQUIVALENT = {
    "UX-001": "FR-UX-001",
    "UX-002": "FR-UX-002",
    "UX-005": "FR-UX-005",
    "UX-006": "FR-UX-006; FR-UX-010",
    "UX-008": "FR-UX-008",
    "UX-009": "FR-UX-018",
    "UX-010": "FR-UX-004",
    "UX-012": "FR-UX-014",
    "UX-013": "FR-UX-009",
    "UX-014": "NFR-AUD-001",
    "UX-015": "FR-UX-014",
    "UX-017": "FR-UX-013",
    "UX-019": "FR-UX-010; FR-UX-011",
    "UX-021": "FR-UX-017",
    "UX-022": (
        "FR-UX-021; FR-UX-026; FR-UX-034; FR-UX-035; FR-UX-036; "
        "NFR-LOC-001; NFR-LOC-002"
    ),
    "UX-023": "FR-UX-020; FR-UX-033; FR-UX-037",
    "UX-024": "FR-UX-022; FR-UX-023; FR-UX-024; FR-UX-033",
    "UX-025": "FR-UX-003",
    "UX-029": "FR-UX-030; NFR-PER-001; NFR-PER-002",
    "UX-031": "FR-UX-023; NFR-UX-002",
    "UX-032": "FR-UX-024; NFR-UX-002",
    "UX-033": "FR-UX-025",
    "UX-034": "FR-UX-022; FR-UX-023; FR-UX-024",
}

UX_PARTIAL = {
    "UX-003": "FR-UX-005; FR-UX-006; FR-UX-025",
    "UX-004": "FR-UX-006; FR-UX-025",
    "UX-007": "FR-UX-007; FR-UX-025; FR-UX-030",
    "UX-016": "FR-UX-012",
    "UX-020": "FR-UX-016; NFR-UX-001",
    "UX-027": "FR-UX-007",
    "UX-035": "FR-UX-025; FR-UX-030",
    "UX-036": "FR-UX-026; FR-UX-036",
}

UX_ISOLATED = {
    "UX-011": "Context-filtered quick create was not explicit in the Pack.",
    "UX-018": "The command palette and keyboard-first action model were omitted.",
    "UX-026": "Timed undo for low-risk bulk changes was omitted.",
    "UX-028": "Versioned, permissioned, audited published shared views were omitted.",
    "UX-030": "The prototype-before-business-implementation rule was not preserved.",
}

ARCH_SOURCES = {
    "ARCH-001": "docs/decisions/ADR-001-target-boundary.md",
    "ARCH-002": (
        "docs/decisions/ADR-001-target-boundary.md; "
        "docs/decisions/ADR-003-frontend-stack.md"
    ),
    "ARCH-003": (
        "docs/decisions/ADR-003-frontend-stack.md; "
        "docs/decisions/ADR-004-industrial-ui.md"
    ),
    "ARCH-004": "docs/ARCHITECTURE.md; contracts/npi-api.openapi.yaml",
    "ARCH-005": (
        "docs/decisions/ADR-007-auth-security.md; "
        "docs/decisions/ADR-009-erp-integration.md"
    ),
    "ARCH-006": (
        "docs/decisions/ADR-009-erp-integration.md; "
        "contracts/integration-event.schema.json"
    ),
    "ARCH-007": "docs/decisions/ADR-008-files-audit-jobs.md",
    "ARCH-008": "docs/DOMAIN_MODEL.md; docs/decisions/ADR-007-auth-security.md",
    "ARCH-009": "docs/ARCHITECTURE.md; docs/decisions/ADR-008-files-audit-jobs.md",
    "ARCH-010": "docs/ARCHITECTURE.md",
    "ARCH-011": "contracts/data-ownership.yaml",
    "ARCH-012": (
        "implementation/QUALITY_GATE.md; " "docs/decisions/ADR-010-ci-quality.md"
    ),
}

I18N_MAPPINGS = {
    "I18N-001": "FR-UX-021; FR-UX-027; NFR-LOC-001",
    "I18N-002": "FR-UX-021; FR-UX-035; NFR-LOC-001",
    "I18N-003": "FR-UX-026; FR-UX-034; NFR-LOC-002",
    "I18N-004": "FR-UX-028",
    "I18N-005": "FR-UX-021; NFR-LOC-001",
    "I18N-006": "FR-UX-027; FR-UX-035; FR-UX-037; NFR-LOC-002",
    "I18N-007": "FR-UX-026; FR-UX-036; NFR-LOC-002",
}

TX_PARTIAL_MAPPINGS = {
    "FR-TX-004": "FR-TL-003; FR-TL-010",
    "FR-TX-007": "",
    "FR-TX-008": "",
    "FR-TX-009": "",
    "FR-TX-010": "",
    "FR-TX-011": "",
}


class MatrixError(RuntimeError):
    """Raised when the reconciliation matrix is incomplete or stale."""


def _read_requirements(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 229:
        raise MatrixError(f"expected 229 DOCX requirement rows; found {len(rows)}")
    if len({row["requirement_id"] for row in rows}) != 229:
        raise MatrixError("DOCX requirement IDs are not unique")
    return rows


def _coverage_for(
    requirement_id: str,
) -> tuple[str, str, str, str, str, str]:
    if not requirement_id.startswith(("UX-", "ARCH-", "COD-", "I18N-", "FR-TX-")):
        return (
            "EXPLICIT_SAME_ID",
            requirement_id,
            "docs/DETAILED_REQUIREMENTS.md",
            "RETAIN_EXISTING_TRACE",
            "RETAINED",
            "The DOCX ID was already present in the Pack requirement inventory.",
        )

    if requirement_id in UX_EQUIVALENT:
        return (
            "EXPLICIT_EQUIVALENT",
            UX_EQUIVALENT[requirement_id],
            "docs/DETAILED_REQUIREMENTS.md; docs/UX_INTERACTION_SPEC.md",
            "ADD_ORIGINAL_ID_ALIAS_TRACE",
            "ADDED_TO_MACHINE_TRACE",
            "The Pack preserved the acceptance substantially under consolidated IDs.",
        )
    if requirement_id in UX_PARTIAL:
        return (
            "PARTIAL_EXPLICIT",
            UX_PARTIAL[requirement_id],
            "docs/DETAILED_REQUIREMENTS.md; docs/UX_INTERACTION_SPEC.md",
            "ADD_DIRECT_REQUIREMENT_AND_REMEDIATION_ACCEPTANCE",
            "ADDED_TO_MACHINE_TRACE",
            "The broad pattern existed, but one or more measurable details were diluted.",
        )
    if requirement_id in UX_ISOLATED:
        return (
            "OTHER_ISOLATED_CASE",
            "",
            "docs/UX_INTERACTION_SPEC.md",
            "ADD_DIRECT_REQUIREMENT_AND_SCHEDULE_BY_DEPENDENCY",
            "ADDED_TO_MACHINE_TRACE",
            UX_ISOLATED[requirement_id],
        )

    if requirement_id.startswith("ARCH-"):
        return (
            "NARRATIVE_EXPLICIT_NOT_TRACEABLE",
            "",
            ARCH_SOURCES[requirement_id],
            "ADD_ORIGINAL_ID_GOVERNANCE_TRACE",
            "ADDED_TO_MACHINE_TRACE",
            "The architecture rule was explicit in narrative/contract evidence but had no row.",
        )

    if requirement_id.startswith("COD-"):
        return (
            "GOVERNANCE_COVERED_NOT_REQUIREMENT_TRACEABLE",
            "",
            (
                "AGENTS.md; implementation/AUTOPILOT_CONTROLLER.md; "
                "implementation/QUALITY_GATE.md; .agents/skills"
            ),
            "ADD_ORIGINAL_ID_GOVERNANCE_TRACE",
            "ADDED_TO_MACHINE_TRACE",
            "Repository governance covered the rule without its DOCX requirement ID.",
        )

    if requirement_id.startswith("I18N-"):
        return (
            "EXPLICIT_CONSOLIDATED_NO_ALIAS",
            I18N_MAPPINGS[requirement_id],
            (
                "docs/LOCALIZATION_SPEC.md; contracts/terminology-allowlist.yaml; "
                "docs/decisions/ADR-005-localization.md"
            ),
            "ADD_ORIGINAL_ID_ALIAS_TRACE",
            "ADDED_TO_MACHINE_TRACE",
            "The localization rule was consolidated into Pack UX/NFR IDs without an alias.",
        )

    if requirement_id in {
        "FR-TX-001",
        "FR-TX-002",
        "FR-TX-003",
        "FR-TX-005",
        "FR-TX-006",
    }:
        return (
            "NARRATIVE_ONLY_HIGH_RISK",
            "",
            "docs/DOMAIN_MODEL.md; docs/TOOLING_AND_TRIAL.md",
            "ADD_DIRECT_REQUIREMENT_AND_PHASE_6_TASK",
            "ADDED_TO_MACHINE_TRACE",
            "The high-risk Tooling invariant existed only as insufficient narrative.",
        )

    if requirement_id == "FR-TX-004":
        return (
            "PARTIAL_EXPLICIT",
            TX_PARTIAL_MAPPINGS[requirement_id],
            "docs/DETAILED_REQUIREMENTS.md; docs/TOOLING_AND_TRIAL.md",
            "ADD_DIRECT_REQUIREMENT_AND_PHASE_6_ACCEPTANCE",
            "ADDED_TO_MACHINE_TRACE",
            "Cavity traceability existed broadly but sealed-cavity and cavity-result detail did not.",
        )

    if requirement_id in {
        "FR-TX-007",
        "FR-TX-008",
        "FR-TX-009",
        "FR-TX-010",
        "FR-TX-011",
    }:
        return (
            "PARTIAL_NARRATIVE",
            TX_PARTIAL_MAPPINGS[requirement_id],
            "docs/DOMAIN_MODEL.md; docs/TOOLING_AND_TRIAL.md",
            "ADD_DIRECT_REQUIREMENT_AND_PHASE_6_ACCEPTANCE",
            "ADDED_TO_MACHINE_TRACE",
            "The concept was mentioned but lacked complete executable acceptance.",
        )

    if requirement_id in {
        "FR-TX-012",
        "FR-TX-013",
        "FR-TX-014",
        "FR-TX-015",
        "FR-TX-016",
        "FR-TX-017",
        "FR-TX-018",
    }:
        return (
            "MISSING_UNIQUE_REQUIREMENT",
            "",
            "",
            "ADD_DIRECT_REQUIREMENT_AND_SPECIALIZED_IMPORT_TASK",
            "ADDED_TO_MACHINE_TRACE",
            "The unique Tooling List import behavior was absent from the Pack.",
        )

    raise MatrixError(f"no coverage classification for {requirement_id}")


def build_matrix(requirements_path: Path) -> list[tuple[str, ...]]:
    requirements = _read_requirements(requirements_path)
    rows: list[tuple[str, ...]] = []
    for requirement in requirements:
        (
            coverage_status,
            pack_requirement_ids,
            pre_reconciliation_sources,
            reconciliation_action,
            post_reconciliation_state,
            notes,
        ) = _coverage_for(requirement["requirement_id"])
        rows.append(
            (
                requirement["requirement_id"],
                requirement["priority"],
                coverage_status,
                pack_requirement_ids,
                pre_reconciliation_sources,
                PRE_RECONCILIATION_CHECKPOINT,
                reconciliation_action,
                post_reconciliation_state,
                notes,
            )
        )

    counts = Counter(row[2] for row in rows)
    if dict(sorted(counts.items())) != EXPECTED_COVERAGE_COUNTS:
        raise MatrixError(
            f"coverage counts differ from the accepted report: {dict(sorted(counts.items()))}"
        )
    if len(rows) != 229 or len({row[0] for row in rows}) != 229:
        raise MatrixError("coverage matrix must contain 229 unique DOCX IDs")
    return rows


def _render(rows: list[tuple[str, ...]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(MATRIX_HEADER)
    writer.writerows(rows)
    return output.getvalue()


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent, text=True
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--requirements",
        type=Path,
        default=Path("implementation/V1_2_DOCX_REQUIREMENTS.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("implementation/V1_2_DOCX_PACK_COVERAGE_MATRIX.csv"),
    )
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()

    content = _render(build_matrix(arguments.requirements))
    if arguments.check:
        if not arguments.output.exists():
            raise MatrixError(f"coverage matrix is missing: {arguments.output}")
        if arguments.output.read_text(encoding="utf-8") != content:
            raise MatrixError(f"coverage matrix is stale: {arguments.output}")
    else:
        _write_atomic(arguments.output, content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
