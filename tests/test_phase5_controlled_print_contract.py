from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPENAPI = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")
OWNERSHIP = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")
BFF = (ROOT / "apps/npi_core/npi_core/bff.py").read_text(encoding="utf-8")


def _path(path: str) -> str:
    start = OPENAPI.index(f"  {path}:\n")
    next_path = OPENAPI.find("\n  /", start + 4)
    components = OPENAPI.find("\ncomponents:", start)
    end_candidates = [value for value in (next_path, components) if value >= 0]
    return OPENAPI[start : min(end_candidates)]


def _schema(name: str) -> str:
    start = OPENAPI.index(f"    {name}:\n", OPENAPI.index("  schemas:\n"))
    match = re.search(r"\n    [A-Z][A-Za-z0-9]+:\n", OPENAPI[start + 1 :])
    return OPENAPI[start:] if match is None else OPENAPI[start : start + 1 + match.start()]


def _statuses(block: str) -> set[str]:
    return set(re.findall(r'^        "([0-9]{3})":', block, re.MULTILINE))


class Phase5ControlledPrintContractTest(unittest.TestCase):
    def test_closed_foundation_paths_have_exact_operations_and_security(self) -> None:
        capability = _path("/projects/{projectId}/controlled-print/capability")
        create = _path("/projects/{projectId}/controlled-prints")
        detail = _path("/projects/{projectId}/controlled-prints/{controlledPrintId}")
        content = _path(
            "/projects/{projectId}/controlled-prints/{controlledPrintId}/content"
        )

        self.assertIn("operationId: getControlledPrintCapability", capability)
        self.assertIn("operationId: createControlledPrintSnapshot", create)
        self.assertIn("operationId: getControlledPrintSnapshot", detail)
        self.assertIn("operationId: downloadControlledPrintOutput", content)
        self.assertIn("#/components/parameters/IdempotencyKey", create)
        self.assertIn("#/components/parameters/CsrfToken", create)
        self.assertIn("x-business-authority: exact-controlled-print-policy-printer", create)
        self.assertIn(
            "x-transaction-boundary: controlled-print-snapshot-output-audit-receipt",
            create,
        )
        self.assertEqual(
            _statuses(create),
            {"201", "400", "401", "403", "404", "409", "422", "500", "503"},
        )
        self.assertEqual(
            _statuses(capability),
            {"200", "400", "401", "403", "404", "500", "503"},
        )
        self.assertIn("application/pdf", content)
        self.assertIn("format: binary", content)
        self.assertTrue(_statuses(content).isdisjoint({"302", "303", "307", "308"}))

    def test_browser_request_cannot_supply_controlled_truth(self) -> None:
        request = _schema("CreateControlledPrintSnapshot")
        required = request.split("required: [", 1)[1].split("]", 1)[0]
        self.assertEqual(
            {value.strip() for value in required.split(",")},
            {"sourceKind", "sourceGlobalId", "sourceVersion", "language"},
        )
        for forbidden in (
            "template", "printFormat", "snapshot", "watermark", "copyState",
            "actor", "printedAt", "file", "hash", "doctype", "operation",
        ):
            self.assertNotIn(f"        {forbidden}:", request)
        self.assertIn("additionalProperties: false", request)

    def test_public_response_is_url_free_and_hash_bound(self) -> None:
        source = _schema("ControlledPrintSourceReference")
        registry = _schema("ControlledPrintRegistryReference")
        output = _schema("ControlledPrintOutput")
        snapshot = _schema("ControlledPrintSnapshot")
        self.assertIn("sourceKind:", source)
        self.assertNotIn("sourceObjectType:", source)
        self.assertNotIn("printFormatName:", registry)
        self.assertNotIn("templateContent:", registry)
        self.assertNotIn("frappeFileId:", output)
        self.assertNotIn("fileUrl:", output)
        self.assertNotIn("sourceSnapshot:", snapshot)
        for marker in (
            "snapshotHash:", "verificationPayload:", "templateSha256:",
            "sha256:", "recordHash:",
        ):
            self.assertIn(marker, registry + output + snapshot)

    def test_only_controlled_pdf_and_non_numbered_foundation_are_claimed(self) -> None:
        contract = "\n".join(
            _schema(name)
            for name in (
                "ControlledPrintCapability",
                "CreateControlledPrintSnapshot",
                "ControlledPrintSnapshot",
            )
        )
        self.assertIn("controlled_pdf", contract)
        self.assertIn("not_numbered", contract)
        for forbidden in (
            "browser_print", "direct_print", "copyNumber", "signer",
            "signature", "retentionDays",
        ):
            self.assertNotIn(forbidden, contract)

    def test_ownership_is_npi_owned_and_decision_held_policy_stays_unavailable(self) -> None:
        for object_name in (
            "ControlledPrintRegistry", "ControlledPrintSnapshot",
            "ControlledPrintOutput", "ControlledPrintAccessEvent",
            "ControlledPrintCommandIdempotency",
        ):
            self.assertIn(f"  {object_name}:\n    owner_system: NPI_ONE", OWNERSHIP)
        self.assertIn(
            "exact_form_signer_retention_and_copy_policy: {owner: FUTURE_APPROVED_PRINT_POLICY, editable_in: [], direction: NONE, conflict: UNAVAILABLE}",
            OWNERSHIP,
        )
        self.assertIn("raw_private_file_url:", OWNERSHIP)
        self.assertIn("conflict: NEVER_EXPOSE", OWNERSHIP)
        self.assertIn("raw_idempotency_key:", OWNERSHIP)
        self.assertIn("conflict: NEVER_PERSIST", OWNERSHIP)

    def test_first_checkpoint_does_not_activate_a_live_bff_route(self) -> None:
        self.assertNotIn("controlled-print/capability", BFF)
        self.assertNotIn("controlled-prints", BFF)
        self.assertNotIn("controlled_print_api", BFF)


if __name__ == "__main__":
    unittest.main()
