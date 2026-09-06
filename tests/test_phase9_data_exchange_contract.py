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


class Phase9DataExchangeContractTest(unittest.TestCase):
    def test_surface_is_closed_system_manager_bff_only(self) -> None:
        operations = {
            "/administration/data-exchange": {"get"},
            "/administration/data-exchange/profiles": {"post"},
            "/administration/data-exchange/exports": {"post"},
            "/administration/data-exchange/exports/{exportId}:content": {"post"},
            "/administration/data-exchange/retention-policies": {"post"},
            "/administration/data-exchange/archive-records": {"post"},
        }
        for path, methods in operations.items():
            block = path_block(path)
            self.assertEqual(set(re.findall(r"^    (get|post):$", block, re.MULTILINE)), methods)
            self.assertIn("tags: [Administration]", block)
            self.assertIn("System Manager", block)

    def test_commands_are_idempotent_csrf_hash_bound_and_audited(self) -> None:
        for path in (
            "/administration/data-exchange/profiles", "/administration/data-exchange/exports",
            "/administration/data-exchange/retention-policies", "/administration/data-exchange/archive-records",
        ):
            block = path_block(path)
            for parameter in ("IdempotencyKey", "RequestId", "CsrfToken"):
                self.assertIn(f"#/components/parameters/{parameter}", block)
            self.assertIn("x-transaction-boundary:", block)
            self.assertIn("x-audit-operation: data_exchange.", block)
        self.assertIn("profileHash", schema("CreateDataExchangeExport"))
        self.assertIn("policyHash", schema("CreateRetentionArchiveRecord"))
        self.assertIn("sourceHash", schema("CreateRetentionArchiveRecord"))

    def test_contract_has_no_generic_writer_or_disposition_claim(self) -> None:
        workspace = schema("DataExchangeWorkspace")
        self.assertIn("genericWriterAvailable: { type: boolean, const: false }", workspace)
        self.assertIn("automaticDispositionAvailable: { type: boolean, const: false }", workspace)
        joined = "\n".join(path_block(path) for path in (
            "/administration/data-exchange", "/administration/data-exchange/profiles",
            "/administration/data-exchange/exports", "/administration/data-exchange/archive-records",
        )).casefold()
        for forbidden in ("doctype", "sql", "target method", "automatic purge"):
            self.assertNotIn(forbidden, joined)

    def test_published_response_schemas_are_closed_without_impossible_all_of_branches(self) -> None:
        for name, fields in (
            ("DataExchangeProfile", ("datasetId", "outputs", "definitionHash")),
            ("RetentionPolicyVersion", ("scope", "retentionYears", "definitionHash")),
        ):
            block = schema(name)
            self.assertIn("additionalProperties: false", block)
            self.assertNotIn("allOf:", block)
            for field in fields:
                self.assertIn(f"{field}:", block)


if __name__ == "__main__":
    unittest.main()
