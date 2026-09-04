from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE_PATH = ROOT / "apps/npi_core/npi_core/tooling/acceptance_repository.py"
ASSET_PATH = (
    ROOT
    / "apps/npi_integration/npi_integration/tool_asset_request/frappe_repository.py"
)
CORE = CORE_PATH.read_text(encoding="utf-8")
ASSET = ASSET_PATH.read_text(encoding="utf-8")
CORE_TREE = ast.parse(CORE)
ASSET_TREE = ast.parse(ASSET)
DIAGNOSTICS_PATH = (
    ROOT / "apps/npi_integration/npi_integration/tool_asset_request/diagnostics.py"
)


def method(source: str, tree: ast.AST, name: str) -> str:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(source, node) or ""
    raise AssertionError(f"missing method: {name}")


class Phase6ToolingAcceptanceRepositoryTest(unittest.TestCase):
    def test_queries_are_project_first_master_bounded_and_non_leaking(self) -> None:
        for source, tree, name in (
            (CORE, CORE_TREE, "tooling_acceptance_context"),
            (ASSET, ASSET_TREE, "list_asset_requests"),
            (ASSET, ASSET_TREE, "asset_request_detail"),
        ):
            with self.subTest(name=name):
                body = method(source, tree, name)
                project = body.index("self._authorized_project(project_id)")
                master = body.index(
                    "self._master_for_project(project, tooling_master_id)"
                )
                self.assertLess(project, master)
                self.assertIn("return None", body)
        self.assertIn("_MAX_ACCEPTANCE_REVISIONS = 500", CORE)
        self.assertIn("_MAX_REQUESTS = 500", ASSET)
        self.assertIn("self._bounded_documents(", method(CORE, CORE_TREE, "_acceptance_revisions"))
        asset_requests = method(ASSET, ASSET_TREE, "_asset_requests")
        self.assertIn("self._bounded_documents(", asset_requests)
        self.assertIn('order_by="created_at desc, global_id asc"', asset_requests)

    def test_acceptance_append_revalidates_every_exact_containment_edge(self) -> None:
        body = method(
            CORE,
            CORE_TREE,
            "create_tooling_acceptance_evidence_revision",
        )
        lock = body.index("self._locked_authorized_project(project_id)")
        receipt_context = body.index("self._command_context(")
        master = body.index("self._master_for_project(project, tooling_master_id)")
        tooling_set = body.index("self._tooling_set_for_project(")
        binding = body.index("self._binding_for_set(project, tooling_set)")
        revision = body.index("self._tooling_revision_for_project(")
        predecessor = body.index("self._acceptance_predecessor(")
        self.assertLess(lock, receipt_context)
        self.assertLess(receipt_context, master)
        self.assertLess(master, tooling_set)
        self.assertLess(tooling_set, binding)
        self.assertLess(binding, revision)
        self.assertLess(revision, predecessor)
        for marker in (
            "binding.global_id != binding_id",
            "binding.snapshot_hash != binding_snapshot_hash",
            "binding.tooling_revision_global_id != tooling_revision_id",
            "tooling_revision.revision_number != tooling_revision_number",
            "tooling_revision.snapshot_hash != tooling_revision_snapshot_hash",
            "self._exact_engineering_member(",
            "self._file_revision_for_project(",
            "validate_acceptance_successor",
        ):
            self.assertIn(marker, CORE)

    def test_acceptance_append_is_one_audited_sealed_transaction(self) -> None:
        body = method(
            CORE,
            CORE_TREE,
            "create_tooling_acceptance_evidence_revision",
        )
        transaction = body.index("with tooling_command_write():")
        receipt = body.index("self._insert_receipt(", transaction)
        insert = body.index("self._insert_acceptance_revision(value)", receipt)
        audit = body.index("self._append_audit(", insert)
        seal = body.index("self._seal_receipt(", audit)
        self.assertLess(receipt, insert)
        self.assertLess(insert, audit)
        self.assertLess(audit, seal)
        self.assertIn('target_type="tooling_acceptance_evidence_revision"', body[seal:])
        self.assertNotIn(".commit(", body)
        self.assertNotIn(".rollback(", body)

    def test_mock_request_resolves_server_input_and_seals_request_audit_receipt(self) -> None:
        body = method(ASSET, ASSET_TREE, "create_asset_request")
        ordered = (
            "self._locked_authorized_project(project_id)",
            "self._master_for_project(project, tooling_master_id)",
            "self._tooling_set_for_project(",
            "self._binding_for_set(project, tooling_set)",
            "self._tooling_revision_for_project(",
            "self._acceptance_revision_for_project(",
            "ToolAssetRequestInput(",
            "self._asset_receipt_replay(",
            "create_mock_tool_asset_request(",
            "with tool_asset_request_write():",
            "self._insert_asset_receipt(",
            "self._insert_asset_request(value)",
            "self._append_audit(",
            "self._seal_asset_receipt(",
        )
        positions = [body.index(marker) for marker in ordered]
        self.assertEqual(positions, sorted(positions))
        for exact_marker in (
            "acceptance.tooling_set_global_id != tooling_set.global_id",
            "acceptance.set_revision_binding_global_id != binding.global_id",
            "acceptance.tooling_revision_global_id != tooling_revision.global_id",
            '"actorUserId": self.actor.casefold()',
            '"operation": TOOL_ASSET_OPERATION',
            '"targetMode": "mock"',
            '"dispatchState": "prohibited"',
            '"targetResultState": "not_requested"',
        ):
            self.assertIn(exact_marker, body)
        self.assertNotIn(".commit(", body)
        self.assertNotIn(".rollback(", body)

        seal = method(ASSET, ASSET_TREE, "_seal_asset_receipt")
        mutations = (
            "receipt.request_global_id =",
            "receipt.response_payload =",
            "receipt.response_hash =",
            "receipt.sealed = 1",
            "receipt.updated_at =",
            "receipt.save()",
        )
        positions = [seal.index(marker) for marker in mutations]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(seal.count("receipt.save()"), 1)
        self.assertNotIn(".commit(", seal)
        self.assertNotIn(".rollback(", seal)

    def test_asset_create_diagnostic_stages_are_unique_and_inner_write_boundaries_win(self) -> None:
        body = method(ASSET, ASSET_TREE, "create_asset_request")
        codes = (
            "P805_P606_ASSET_PROJECT_LOCK",
            "P805_P606_ASSET_MASTER_RESOLVE",
            "P805_P606_ASSET_SET_RESOLVE",
            "P805_P606_ASSET_BINDING_RESOLVE",
            "P805_P606_ASSET_REVISION_RESOLVE",
            "P805_P606_ASSET_ACCEPTANCE_RESOLVE",
            "P805_P606_ASSET_INPUT_BUILD",
            "P805_P606_ASSET_PAYLOAD_BUILD",
            "P805_P606_ASSET_RECEIPT_REPLAY",
            "P805_P606_ASSET_DOMAIN_BUILD",
            "P805_P606_ASSET_RESPONSE_BUILD",
            "P805_P606_ASSET_TRANSACTION_SCOPE",
            "P805_P606_ASSET_RECEIPT_INSERT",
            "P805_P606_ASSET_REQUEST_INSERT",
            "P805_P606_ASSET_AUDIT_APPEND",
            "P805_P606_ASSET_RECEIPT_SEAL",
        )
        for code in codes:
            with self.subTest(code=code):
                self.assertEqual(body.count(f'"{code}"'), 1)
        transaction = body.index('"P805_P606_ASSET_TRANSACTION_SCOPE"')
        ordered = [
            body.index(f'"P805_P606_ASSET_{suffix}"', transaction)
            for suffix in (
                "RECEIPT_INSERT",
                "REQUEST_INSERT",
                "AUDIT_APPEND",
                "RECEIPT_SEAL",
            )
        ]
        self.assertEqual(ordered, sorted(ordered))
        diagnostics = DIAGNOSTICS_PATH.read_text(encoding="utf-8")
        self.assertIn('state["recorded"] = True', diagnostics)
        self.assertIn("raise\n", diagnostics)
        for forbidden in ("str(error)", "repr(error)", "traceback", "payload="):
            self.assertNotIn(forbidden, diagnostics)

    def test_runtime_slice_has_no_erp_dispatch_outbox_or_formal_target_identity(self) -> None:
        legacy_names = {
            "acceptance_asset_context",
            "list_asset_requests",
            "asset_request_detail",
            "create_asset_request",
            "_asset_requests",
            "_asset_request_for_scope",
            "_asset_receipt_replay",
            "_insert_asset_receipt",
            "_seal_asset_receipt",
            "_insert_asset_request",
        }
        asset_tree = ast.parse(ASSET)
        legacy = "\n".join(
            source
            for node in ast.walk(asset_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in legacy_names
            if (source := ast.get_source_segment(ASSET, node)) is not None
        )
        combined = CORE + legacy
        for forbidden in (
            "requests.",
            "httpx.",
            "urllib.",
            "urlopen(",
            '"doctype": "NPI Outbox',
            '"doctype": "NPI Integration Outbox',
            '"formal_asset_id"',
            '"endpoint"',
            '"credential"',
            ".commit(",
            ".rollback(",
        ):
            self.assertNotIn(forbidden, combined)
        for truth in (
            '"state": "unavailable"',
            '"reasonCode": "erp_asset_projection_unavailable"',
            '"mappingCardinality": "zero_or_one_per_physical_set"',
            '"dispatchState": "prohibited"',
            '"targetResultState": "not_requested"',
        ):
            self.assertIn(truth, combined)


if __name__ == "__main__":
    unittest.main()
