#!/usr/bin/env python3
"""Verify the fixed P9-08 controlled non-production UAT evidence manifest."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "implementation" / "uat" / "p9-08-controlled-uat.json"
TRACEABILITY = ROOT / "implementation" / "REQUIREMENT_TRACEABILITY.csv"
SCENARIOS = {"AT-01": "customer_owned_mold", "AT-02": "new_tooling"}
SURFACES = ["my_work", "project_context", "outside_context"]
FAMILIES = [
    "project_work",
    "permissions",
    "documents_baselines",
    "ebom",
    "gates",
    "tooling",
    "trial",
    "quality_readiness",
    "erp_projections",
    "erp_execution",
    "integration_operations",
    "change_control",
    "reporting_collaboration",
    "security",
    "data_exchange",
    "recovery",
    "localization_visual",
]
SAFE_ID = re.compile(r"^[A-Z0-9]+(?:-[A-Z0-9]+)+$")
PROJECT_ROUTE = re.compile(
    r"^/projects/\{projectGlobalId\}(?:"
    r"/gates/\{gateGlobalId\}|"
    r"/tooling(?:/\{toolingMasterGlobalId\})?|"
    r"/trials|"
    r"/integration-operations"
    r")?$"
)
SAFE_EVIDENCE_PATH = re.compile(
    r"^(?:tests/[A-Za-z0-9_.-]+\.py|frontend/tests/e2e/[A-Za-z0-9_.-]+\.ts)$"
)


class ControlledUatError(RuntimeError):
    """Raised when controlled-UAT evidence is incomplete or overclaims truth."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ControlledUatError(message)


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        require(key not in value, f"duplicate manifest key: {key}")
        value[key] = item
    return value


def load_manifest(path: Path = MANIFEST) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique_object,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ControlledUatError(f"cannot read controlled-UAT manifest: {exc}") from exc
    require(type(value) is dict, "controlled-UAT manifest must be an object")
    return value


def exact_keys(value: object, expected: set[str], label: str) -> dict[str, Any]:
    require(type(value) is dict, f"{label} must be an object")
    result = dict(value)
    require(set(result) == expected, f"{label} keys drifted")
    return result


def string_list(value: object, label: str) -> list[str]:
    require(type(value) is list and bool(value), f"{label} must be a non-empty list")
    result = list(value)
    require(
        all(type(item) is str and item and item.strip() == item for item in result),
        f"{label} must contain trimmed strings",
    )
    require(len(result) == len(set(result)), f"{label} must not contain duplicates")
    return result


def known_requirements() -> set[str]:
    try:
        with TRACEABILITY.open(encoding="utf-8", newline="") as stream:
            return {row["requirement_id"] for row in csv.DictReader(stream)}
    except (OSError, UnicodeError, csv.Error, KeyError) as exc:
        raise ControlledUatError(f"cannot read requirement traceability: {exc}") from exc


def verify_evidence(value: object, label: str) -> str:
    evidence = exact_keys(value, {"path", "selector"}, label)
    path = evidence["path"]
    selector = evidence["selector"]
    require(
        type(path) is str and SAFE_EVIDENCE_PATH.fullmatch(path) is not None,
        f"{label} path is outside fixed test evidence roots",
    )
    require(
        type(selector) is str
        and selector.strip() == selector
        and 8 <= len(selector) <= 200
        and "\n" not in selector,
        f"{label} selector is invalid",
    )
    evidence_path = ROOT / path
    require(evidence_path.is_file(), f"{label} evidence file is missing: {path}")
    require(
        selector in evidence_path.read_text(encoding="utf-8"),
        f"{label} selector is absent from {path}",
    )
    return path


def verify_route(surface: str, route: object, label: str) -> None:
    require(
        type(route) is str
        and route.startswith("/")
        and len(route) <= 160
        and "?" not in route
        and "#" not in route
        and "//" not in route,
        f"{label} route template is invalid",
    )
    if surface == "my_work":
        require(route == "/work", f"{label} My Work route drifted")
    elif surface == "project_context":
        require(
            PROJECT_ROUTE.fullmatch(route) is not None,
            f"{label} is not in one approved Project context",
        )
    else:
        require(route == "/reports", f"{label} outside-context route drifted")


def validate_manifest(path: Path = MANIFEST) -> dict[str, Any]:
    manifest = exact_keys(
        load_manifest(path),
        {
            "schemaVersion",
            "evidenceClass",
            "requirementId",
            "threshold",
            "claims",
            "allowedSurfaces",
            "requiredFamilies",
            "supportingEvidence",
            "scenarios",
        },
        "manifest",
    )
    require(
        manifest["schemaVersion"] == "p9-08-controlled-uat.v1",
        "controlled-UAT schema version drifted",
    )
    require(
        manifest["evidenceClass"] == "CONTROLLED_NON_PRODUCTION_TECHNICAL_UAT",
        "evidence class must remain controlled non-production technical UAT",
    )
    require(manifest["requirementId"] == "UX-003", "Requirement must be UX-003")
    require(
        type(manifest["threshold"]) is float and manifest["threshold"] == 0.8,
        "controlled workflow threshold must remain exactly 0.8",
    )
    claims = exact_keys(
        manifest["claims"],
        {"environment", "realPilot", "realProject", "realUserAdoption"},
        "claims",
    )
    require(
        claims
        == {
            "environment": "representative_non_production",
            "realPilot": False,
            "realProject": False,
            "realUserAdoption": False,
        },
        "controlled-UAT claims overstate production, pilot, project or adoption truth",
    )
    require(manifest["allowedSurfaces"] == SURFACES, "allowed surfaces drifted")
    require(manifest["requiredFamilies"] == FAMILIES, "required families drifted")

    covered_families: set[str] = set()
    supporting = manifest["supportingEvidence"]
    require(type(supporting) is list and bool(supporting), "supporting evidence is required")
    support_names: set[str] = set()
    for index, raw_support in enumerate(supporting):
        label = f"supportingEvidence[{index}]"
        support = exact_keys(raw_support, {"family", "path", "selector"}, label)
        family = support["family"]
        require(
            type(family) is str and family in FAMILIES,
            f"{label} family is not allowlisted",
        )
        require(family not in support_names, f"duplicate supporting family: {family}")
        support_names.add(family)
        covered_families.add(family)
        verify_evidence({"path": support["path"], "selector": support["selector"]}, label)

    scenarios = manifest["scenarios"]
    require(type(scenarios) is list, "scenarios must be a list")
    require(len(scenarios) == 2, "exactly two controlled scenarios are required")
    requirement_ids = known_requirements()
    activity_ids: set[str] = set()
    scenario_results: list[dict[str, Any]] = []
    total = 0
    qualifying_total = 0
    observed_scenarios: dict[str, str] = {}

    for scenario_index, raw_scenario in enumerate(scenarios):
        scenario_label = f"scenarios[{scenario_index}]"
        scenario = exact_keys(raw_scenario, {"id", "projectType", "activities"}, scenario_label)
        scenario_id = scenario["id"]
        project_type = scenario["projectType"]
        require(
            type(scenario_id) is str and scenario_id in SCENARIOS,
            f"{scenario_label} ID is not allowlisted",
        )
        require(scenario_id not in observed_scenarios, f"duplicate scenario: {scenario_id}")
        require(
            project_type == SCENARIOS[scenario_id],
            f"{scenario_id} project type drifted",
        )
        observed_scenarios[scenario_id] = project_type
        activities = scenario["activities"]
        require(
            type(activities) is list and len(activities) == 10,
            f"{scenario_id} must freeze exactly ten frequent activities",
        )
        flows: set[str] = set()
        qualifying = 0
        for activity_index, raw_activity in enumerate(activities):
            label = f"{scenario_id}.activities[{activity_index}]"
            activity = exact_keys(
                raw_activity,
                {
                    "id",
                    "flow",
                    "title",
                    "surface",
                    "routeTemplate",
                    "families",
                    "requirementIds",
                    "evidence",
                },
                label,
            )
            activity_id = activity["id"]
            require(
                type(activity_id) is str
                and SAFE_ID.fullmatch(activity_id) is not None
                and activity_id.startswith(scenario_id.replace("-", "")),
                f"{label} activity ID is invalid",
            )
            require(activity_id not in activity_ids, f"duplicate activity ID: {activity_id}")
            activity_ids.add(activity_id)
            require(
                type(activity["title"]) is str
                and activity["title"].strip() == activity["title"]
                and 12 <= len(activity["title"]) <= 120,
                f"{label} title is invalid",
            )
            flow = activity["flow"]
            require(flow in {"golden", "fault"}, f"{label} flow is invalid")
            flows.add(flow)
            surface = activity["surface"]
            require(surface in SURFACES, f"{label} surface is invalid")
            verify_route(surface, activity["routeTemplate"], label)
            if surface in {"my_work", "project_context"}:
                qualifying += 1
            families = string_list(activity["families"], f"{label}.families")
            require(set(families) <= set(FAMILIES), f"{label} has an unknown family")
            covered_families.update(families)
            anchors = string_list(activity["requirementIds"], f"{label}.requirementIds")
            require(
                set(anchors) <= requirement_ids and "UX-003" in anchors,
                f"{label} has an unknown or missing UX-003 anchor",
            )
            evidence = activity["evidence"]
            require(type(evidence) is list and bool(evidence), f"{label} evidence is required")
            for evidence_index, item in enumerate(evidence):
                verify_evidence(item, f"{label}.evidence[{evidence_index}]")
        require(flows == {"golden", "fault"}, f"{scenario_id} needs golden and fault flows")
        ratio = qualifying / len(activities)
        require(ratio >= manifest["threshold"], f"{scenario_id} workflow ratio is below 0.8")
        total += len(activities)
        qualifying_total += qualifying
        scenario_results.append(
            {"id": scenario_id, "qualifying": qualifying, "total": len(activities), "ratio": ratio}
        )

    require(observed_scenarios == SCENARIOS, "controlled scenario set drifted")
    require(covered_families == set(FAMILIES), "one or more required evidence families are missing")
    overall_ratio = qualifying_total / total
    require(overall_ratio >= manifest["threshold"], "overall workflow ratio is below 0.8")
    canonical = json.dumps(manifest, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return {
        "schemaVersion": manifest["schemaVersion"],
        "evidenceClass": manifest["evidenceClass"],
        "scenarios": scenario_results,
        "qualifying": qualifying_total,
        "total": total,
        "ratio": overall_ratio,
        "manifestSha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "productionContact": False,
    }


def main() -> int:
    try:
        result = validate_manifest()
    except (ControlledUatError, OSError, UnicodeError, csv.Error) as exc:
        print(f"P9-08 controlled UAT verification failed: {exc}", file=sys.stderr)
        return 1
    ratios = ", ".join(
        f"{item['id']}={item['qualifying']}/{item['total']}"
        for item in result["scenarios"]
    )
    print(
        "P9-08 controlled non-production technical UAT manifest passed: "
        f"{ratios}; overall={result['qualifying']}/{result['total']}; "
        f"sha256={result['manifestSha256']}; productionContact=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
