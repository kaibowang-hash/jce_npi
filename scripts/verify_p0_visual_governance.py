#!/usr/bin/env python3
"""Verify the exact R1-06 P0 1440 visual-governance contract."""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "frontend/tests/e2e/p0-visual-registry.json"
SPEC = ROOT / "frontend/tests/e2e/r1-06-p0-visual-governance.spec.ts"
SNAPSHOT_DIRECTORY = (
    ROOT
    / "frontend/tests/e2e/r1-06-p0-visual-governance.spec.ts-snapshots"
)

EXPECTED_REGISTRY_KEYS = {
    "schemaVersion",
    "catalogVisualVersion",
    "viewport",
    "scenario",
    "locales",
    "screens",
}
EXPECTED_VIEWPORT = {"width": 1440, "height": 900, "zoomPercent": 100}
EXPECTED_LOCALES = ["en", "zh", "zh-TW"]
EXPECTED_SCREENS = [
    {
        "id": "work",
        "path": "/demo/work",
        "pageClass": "page--work",
        "contextSelector": ".page-heading",
        "workSurfaceSelector": ".worklist-panel",
        "propertiesSelector": ".docked-inspector",
    },
    {
        "id": "project",
        "path": "/demo/projects/PJ-26018",
        "pageClass": "page--object",
        "contextSelector": ".object-header",
        "workSurfaceSelector": ".engineering-layout--project",
        "propertiesSelector": ".docked-inspector",
    },
    {
        "id": "gate",
        "path": "/demo/projects/PJ-26018/gates/G5",
        "pageClass": "page--object",
        "contextSelector": ".object-header",
        "workSurfaceSelector": ".review-layout",
        "propertiesSelector": "#gate-decision",
    },
    {
        "id": "tooling",
        "path": "/tooling/TL-26018-01",
        "pageClass": "page--object",
        "contextSelector": ".object-header",
        "workSurfaceSelector": ".engineering-layout",
        "propertiesSelector": "#tooling-properties",
    },
    {
        "id": "trial",
        "path": "/trials/T1",
        "pageClass": "page--object",
        "contextSelector": ".object-header",
        "workSurfaceSelector": ".trial-layout",
        "propertiesSelector": ".docked-inspector",
    },
    {
        "id": "execution",
        "path": "/execution",
        "pageClass": "page--execution",
        "contextSelector": ".page-heading",
        "workSurfaceSelector": ".execution-layout",
        "propertiesSelector": ".execution-layout > .panel:last-child",
    },
]
REQUIRED_SPEC_FRAGMENTS = (
    "for (const screen of p0VisualRegistry.screens)",
    "for (const locale of p0VisualRegistry.locales)",
    "scenario: p0VisualRegistry.scenario",
    "await expectNoMixedLanguage(page, locale);",
    "await expectNoDocumentOverflow(page);",
    "await expectP0Density(page, screen);",
    'page.locator(".status-bar__catalog code")',
    "await expect(catalogFingerprint).toHaveText(catalogVersion);",
    "}, p0VisualRegistry.catalogVisualVersion);",
    """page.locator('[data-visual-primary="true"]:visible')""",
    "expect(contextGeometry.height).toBeLessThanOrEqual(210);",
    "expect(workGeometry.width).toBeGreaterThanOrEqual(560);",
    "expect(workGeometry.height).toBeGreaterThanOrEqual(240);",
    "expect(propertiesGeometry.width).toBeGreaterThanOrEqual(220);",
    "expect(propertiesGeometry.height).toBeGreaterThanOrEqual(180);",
    "await expect(page).toHaveScreenshot(`${name}.png`, {",
    "fullPage: false",
)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024


class VisualGovernanceError(RuntimeError):
    """Raised when the governed P0 visual contract has drifted."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VisualGovernanceError(message)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise VisualGovernanceError(f"duplicate JSON key: {key}")
        document[key] = value
    return document


def load_registry(path: Path = REGISTRY) -> dict[str, Any]:
    try:
        document = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VisualGovernanceError(f"cannot read P0 visual registry: {exc}") from exc
    _require(type(document) is dict, "P0 visual registry must be a JSON object")
    _require(
        set(document) == EXPECTED_REGISTRY_KEYS,
        "P0 visual registry must use the exact governed top-level keys",
    )
    _require(
        type(document["schemaVersion"]) is int
        and document["schemaVersion"] == 2,
        "P0 visual registry schemaVersion must be integer 2",
    )
    _require(
        type(document["catalogVisualVersion"]) is str
        and len(document["catalogVisualVersion"]) == 16
        and all(
            character in "0123456789abcdef"
            for character in document["catalogVisualVersion"]
        ),
        "P0 catalog visual version must be one stable 16-character lowercase hash",
    )
    _require(
        type(document["viewport"]) is dict
        and document["viewport"] == EXPECTED_VIEWPORT,
        "P0 visual registry viewport must be exactly 1440x900 at 100%",
    )
    _require(
        document["scenario"] == "normal",
        "P0 visual registry scenario must be exactly normal",
    )
    _require(
        document["locales"] == EXPECTED_LOCALES,
        "P0 visual registry locales must be exactly en, zh and zh-TW",
    )
    _require(
        document["screens"] == EXPECTED_SCREENS,
        "P0 visual registry screens or selectors drifted",
    )
    return document


def expected_case_names(registry: dict[str, Any]) -> tuple[str, ...]:
    viewport = registry["viewport"]
    names = tuple(
        (
            f"r1-06-p0-normal-{screen['id']}-{locale}-"
            f"{viewport['width']}x{viewport['height']}-{viewport['zoomPercent']}"
        )
        for screen in registry["screens"]
        for locale in registry["locales"]
    )
    _require(len(names) == 18, "P0 visual registry must yield exactly 18 cases")
    _require(len(set(names)) == 18, "P0 visual case names must be unique")
    return names


def verify_spec(path: Path = SPEC) -> None:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise VisualGovernanceError(f"cannot read P0 visual spec: {exc}") from exc
    for fragment in REQUIRED_SPEC_FRAGMENTS:
        _require(
            source.count(fragment) == 1,
            f"P0 visual spec must contain one exact governed fragment: {fragment}",
        )
    _require(
        source.count("toHaveScreenshot(") == 1,
        "P0 visual spec must use one registry-driven screenshot assertion",
    )
    _require(
        "--update-snapshots" not in source,
        "P0 visual spec must not update accepted snapshots",
    )


def read_png_dimensions(path: Path) -> tuple[int, int]:
    _require(not path.is_symlink(), f"visual baseline must not be a symlink: {path.name}")
    try:
        file_size = path.stat().st_size
        with path.open("rb") as stream:
            header = stream.read(24)
    except OSError as exc:
        raise VisualGovernanceError(
            f"cannot read visual baseline {path.name}: {exc}"
        ) from exc
    _require(
        24 <= file_size <= MAX_SNAPSHOT_BYTES,
        f"visual baseline file size is unsafe: {path.name}",
    )
    _require(
        header[:8] == PNG_SIGNATURE
        and header[8:12] == struct.pack(">I", 13)
        and header[12:16] == b"IHDR",
        f"visual baseline is not a canonical PNG: {path.name}",
    )
    return struct.unpack(">II", header[16:24])


def verify_snapshots(
    registry: dict[str, Any],
    directory: Path = SNAPSHOT_DIRECTORY,
) -> tuple[str, ...]:
    _require(directory.is_dir(), "P0 Linux snapshot directory is missing")
    expected_names = tuple(f"{name}-linux.png" for name in expected_case_names(registry))
    expected_set = set(expected_names)
    actual_paths = tuple(
        path
        for path in directory.iterdir()
        if path.is_file() and path.name.endswith("-linux.png")
    )
    actual_set = {path.name for path in actual_paths}
    missing = sorted(expected_set - actual_set)
    extra = sorted(actual_set - expected_set)
    _require(
        not missing and not extra,
        f"P0 Linux snapshot set drifted; missing={missing}, extra={extra}",
    )
    for path in actual_paths:
        _require(
            read_png_dimensions(path) == (1440, 900),
            f"P0 Linux snapshot dimensions must be 1440x900: {path.name}",
        )
    return expected_names


def verify_visual_governance(
    registry_path: Path = REGISTRY,
    spec_path: Path = SPEC,
    snapshot_directory: Path = SNAPSHOT_DIRECTORY,
) -> tuple[str, ...]:
    registry = load_registry(registry_path)
    verify_spec(spec_path)
    return verify_snapshots(registry, snapshot_directory)


def main() -> int:
    try:
        expected = verify_visual_governance()
    except VisualGovernanceError as exc:
        print(f"R1-06 P0 visual governance failed: {exc}", file=sys.stderr)
        return 1
    print(
        "R1-06 P0 visual governance passed: "
        f"{len(expected)} Linux baselines at 1440x900"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
