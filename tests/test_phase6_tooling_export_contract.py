from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPENAPI = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")
OWNERSHIP = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")
BFF = (ROOT / "apps/npi_core/npi_core/bff.py").read_text(encoding="utf-8")
API = (ROOT / "apps/npi_core/npi_core/tooling_export_api.py").read_text(encoding="utf-8")
def _block(marker: str) -> str:
    lines = OPENAPI.splitlines()
    indexes = [index for index, line in enumerate(lines) if line == marker]
    if len(indexes) != 1:
        raise AssertionError(f"expected one {marker!r}, found {len(indexes)}")
    start = indexes[0]
    indent = len(marker) - len(marker.lstrip())
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            end = index
            break
    return "\n".join(lines[start:end])


def _ownership_block(name: str) -> str:
    marker = f"  {name}:\n"
    start = OWNERSHIP.index(marker)
    match = re.search(r"\n  [A-Z][A-Za-z0-9]+:\n", OWNERSHIP[start + len(marker) :])
    return (
        OWNERSHIP[start:]
        if match is None
        else OWNERSHIP[start : start + len(marker) + match.start()]
    )


class Phase6ToolingExportContractTests(unittest.TestCase):
    def test_four_project_first_routes_are_fixed_and_content_is_post_only(self) -> None:
        paths = {
            "/projects/{projectId}/tooling-list": ("get:",),
            "/projects/{projectId}/tooling-list/preferences/{viewId}": ("get:", "put:"),
            "/projects/{projectId}/tooling-exports": ("post:",),
            "/projects/{projectId}/tooling-exports/{packageId}:content": ("post:",),
        }
        for path, methods in paths.items():
            with self.subTest(path=path):
                block = _block(f"  {path}:")
                self.assertEqual(
                    tuple(
                        line.strip()
                        for line in block.splitlines()[1:]
                        if re.fullmatch(r"    (get|put|post|patch|delete):", line)
                    ),
                    methods,
                )
                self.assertIn("#/components/parameters/ProjectId", block)
                self.assertIn('"503"', block)
        content = _block(
            "  /projects/{projectId}/tooling-exports/{packageId}:content:"
        )
        self.assertIn("application/zip", content)
        self.assertIn("#/components/parameters/IdempotencyKey", content)
        self.assertIn("#/components/parameters/CsrfToken", content)
        self.assertNotIn("get:", content)

    def test_all_request_and_response_schemas_are_closed_and_bounded(self) -> None:
        for name in (
            "ToolingListFilterSnapshot",
            "ToolingListRow",
            "ToolingListPermissions",
            "ToolingListPage",
            "ToolingListPreferenceSnapshot",
            "ToolingListPreference",
            "SetToolingListPreference",
            "ToolingListSelectionReference",
            "ToolingExportSelectionRequest",
            "ToolingExportFilteredRequest",
            "ToolingExportPackage",
            "ToolingExportPackageCommand",
            "DownloadToolingExportPackage",
        ):
            with self.subTest(schema=name):
                self.assertIn("additionalProperties: false", _block(f"    {name}:"))
        self.assertIn("maximum: 100", _block("    ToolingListPage:"))
        self.assertIn("maxItems: 100", _block("    ToolingExportSelectionRequest:"))
        self.assertIn("maximum: 1000000", _block("    ToolingExportPackage:"))
        self.assertIn("const: internal_project", _block("    ToolingExportPackage:"))

    def test_contract_and_adapter_cannot_be_turned_into_generic_export(self) -> None:
        public_surface = API + "\n".join(
            _block(marker)
            for marker in (
                "  /projects/{projectId}/tooling-list:",
                "  /projects/{projectId}/tooling-list/preferences/{viewId}:",
                "  /projects/{projectId}/tooling-exports:",
                "  /projects/{projectId}/tooling-exports/{packageId}:content:",
                "    ToolingListPage:",
                "    ToolingListPreference:",
                "    ToolingExportRequest:",
                "    ToolingExportPackage:",
                "    DownloadToolingExportPackage:",
            )
        )
        for forbidden in (
            "rawFileUrl",
            "fileUrl:",
            "doctype:",
            "fieldList",
            "filterExpression",
            "reportName",
            "frappeFileId:",
        ):
            self.assertNotIn(forbidden, public_surface)
        for allowed in (
            "viewId",
            "search",
            "sortKey",
            "sortDirection",
            "groupKey",
            "pageSize",
            "cursor",
        ):
            self.assertIn(f"name: {allowed}", _block("  /projects/{projectId}/tooling-list:"))
        self.assertIn("OMITTED_FIELD_CLASSES", (
            ROOT / "apps/npi_core/npi_core/tooling/export_rendering.py"
        ).read_text(encoding="utf-8"))

    def test_export_authority_and_ownership_remain_separate_and_npi_owned(self) -> None:
        for route in (
            "  /projects/{projectId}/tooling-exports:",
            "  /projects/{projectId}/tooling-exports/{packageId}:content:",
        ):
            block = _block(route)
            self.assertIn("x-required-roles: [System Manager]", block)
        self.assertIn('principal.is_external or "System Manager" not in principal.roles', API)
        self.assertIn("authorize_scope(project_id, administer=True)", API)
        for object_name in (
            "ToolingListPreference",
            "ToolingExportPackage",
            "ToolingExportCommandIdempotency",
        ):
            self.assertIn("owner: NPI_ONE", _ownership_block(object_name))
        self.assertIn("conflict: NEVER_INCLUDE_IN_PACKAGE", OWNERSHIP)


if __name__ == "__main__":
    unittest.main()
