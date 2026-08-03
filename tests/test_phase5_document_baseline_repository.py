from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_PATH = (
    ROOT
    / "apps"
    / "npi_core"
    / "npi_core"
    / "documents"
    / "baseline_repository.py"
)
PROJECT_DOCTYPE_PATH = (
    ROOT
    / "apps"
    / "npi_core"
    / "npi_core"
    / "npi_core"
    / "doctype"
    / "npi_engineering_project"
    / "npi_engineering_project.json"
)
SOURCE = REPOSITORY_PATH.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _function(name: str) -> str:
    matches = [
        node
        for node in ast.walk(TREE)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {name!r} function, found {len(matches)}")
    value = ast.get_source_segment(SOURCE, matches[0])
    if value is None:
        raise AssertionError(f"Unable to read {name!r}")
    return value


class DocumentBaselineRepositoryTest(unittest.TestCase):
    def test_workspace_project_response_maps_exact_persisted_fields(self) -> None:
        schema = json.loads(PROJECT_DOCTYPE_PATH.read_text(encoding="utf-8"))
        fieldnames = {field["fieldname"] for field in schema["fields"]}
        self.assertIn("business_code", fieldnames)
        self.assertIn("title", fieldnames)
        self.assertNotIn("project_code", fieldnames)
        self.assertNotIn("project_name", fieldnames)

        value = _function("list_baselines")
        self.assertIn('"projectCode": str(project.business_code)', value)
        self.assertIn('"projectName": str(project.title)', value)
        self.assertNotIn("project.project_code", value)
        self.assertNotIn("project.project_name", value)

    def test_create_authorizes_exact_actor_before_protected_member_resolution(
        self,
    ) -> None:
        value = _function("create_baseline")
        order = (
            "self._locked_baseline_project(project_id)",
            "self._current_actor_member(project)",
            "self._load_exact_baseline_policy(",
            "policy.permits_baseline(self.actor)",
            "self._baseline_replay(",
            "require_mutable_project(project)",
            "self._resolve_members(project, members)",
        )
        positions = [value.index(fragment) for fragment in order]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("ignore_" "permissions", value)

    def test_policy_options_require_transport_role_and_current_membership(
        self,
    ) -> None:
        value = _function("_published_baseline_policy_options")
        order = (
            "self.principal.is_external",
            '"NPI API User" not in self.principal.roles',
            "self._current_actor_member(project) is None",
            "self._load_exact_baseline_policy(",
            "policy.permits_baseline(self.actor)",
        )
        positions = [value.index(fragment) for fragment in order]
        self.assertEqual(positions, sorted(positions))

    def test_member_resolution_locks_and_revalidates_exact_release_evidence(
        self,
    ) -> None:
        resolve_members = _function("_resolve_members")
        resolve_input = _function("_resolve_member_input")
        validate_files = _function("_validate_released_files")
        self.assertIn("for revision_id in sorted(by_id, key=str)", resolve_members)
        self.assertIn("enumerate(preconditions, start=1)", resolve_members)
        for doctype in (
            "NPI Document Revision",
            "NPI Controlled Document",
            "NPI Document Revision Lifecycle",
            "NPI Document Lifecycle Event",
            "NPI Document Review Cycle",
        ):
            with self.subTest(doctype=doctype):
                self.assertIn(doctype, resolve_input)
        self.assertGreaterEqual(resolve_input.count("for_update=True"), 5)
        self.assertIn(
            "event.evidence_snapshot_hash "
            "!= lifecycle.release_snapshot_hash",
            " ".join(resolve_input.split()),
        )
        self.assertIn(
            "lifecycle.release_snapshot_hash "
            "!= precondition.expected_release_snapshot_hash",
            " ".join(resolve_input.split()),
        )
        self.assertIn("cycle.evidence", resolve_input)
        self.assertNotIn(
            "event.evidence_snapshot_hash != cycle.evidence.snapshot_hash",
            resolve_input,
        )
        self.assertIn("self._release_file_evidence(", validate_files)
        self.assertIn("int(file_revision.released or 0) != 1", validate_files)
        self.assertIn("_stable_file_evidence_matches(observed, expected)", validate_files)

    def test_live_file_comparison_keeps_stable_identity_and_content_closed(self) -> None:
        value = _function("_stable_file_evidence_matches")
        for field in (
            "association_global_id",
            "association_snapshot_hash",
            "file_revision_global_id",
            "file_document_global_id",
            "frappe_file_id",
            "frappe_content_hash",
            "file_name",
            "mime_type",
            "size_bytes",
            "sha256",
            "uploaded_by_user_id",
            "uploaded_at",
        ):
            with self.subTest(field=field):
                self.assertIn(f"observed.{field}", value)
                self.assertIn(f"expected.{field}", value)
        self.assertEqual(value.count('scan_state == "clean"'), 2)

    def test_write_order_seals_actor_bound_receipt_last(self) -> None:
        value = _function("create_baseline")
        order = (
            "self._insert_baseline_receipt(",
            "self._insert_baseline(project, baseline)",
            "self._insert_members(project, baseline_document, baseline)",
            "self._append_audit(",
            'response = {',
            "self._seal_baseline_receipt(",
        )
        positions = [value.index(fragment) for fragment in order]
        self.assertEqual(positions, sorted(positions))
        replay = _function("_baseline_replay")
        for fragment in (
            '"tenant_id"',
            '"project_global_id"',
            '"actor_user_id"',
            '"operation"',
            '"payload_hash"',
            '"response_hash"',
            '"sealed"',
            "sha256_json(response)",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, replay)

    def test_create_diagnostic_ladder_is_closed_and_order_neutral(self) -> None:
        value = _function("create_baseline")
        codes = (
            "P503_BASELINE_CREATE_PROJECT_LOCK",
            "P503_BASELINE_CREATE_MEMBERSHIP_AUTHORITY",
            "P503_BASELINE_CREATE_POLICY_LOAD",
            "P503_BASELINE_CREATE_IDEMPOTENCY_REPLAY",
            "P503_BASELINE_CREATE_MEMBER_RESOLVE",
            "P503_BASELINE_CREATE_MEMBER_PRECONDITION_SET",
            "P503_BASELINE_CREATE_DOMAIN_BUILD",
            "P503_BASELINE_CREATE_RECEIPT_INSERT",
            "P503_BASELINE_CREATE_BASELINE_INSERT",
            "P503_BASELINE_CREATE_MEMBER_INSERT",
            "P503_BASELINE_CREATE_AUDIT_APPEND",
            "P503_BASELINE_CREATE_RESPONSE_BUILD",
            "P503_BASELINE_CREATE_RECEIPT_SEAL",
        )
        positions = [value.index(f'"{code}"') for code in codes]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(value.count("baseline_create_server_step("), len(codes))
        for forbidden in (
            "traceback",
            "exception.args",
            "request.body",
            "response.body",
            "cookie",
            "credential",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, value.casefold())

        helper_codes = {
            "P503_BASELINE_CREATE_MEMBER_RECORD_LOAD",
            "P503_BASELINE_CREATE_MEMBER_RELEASE_STATE",
            "P503_BASELINE_CREATE_MEMBER_REVIEW_LOAD",
            "P503_BASELINE_CREATE_MEMBER_RELEASE_LINEAGE",
            "P503_BASELINE_CREATE_MEMBER_PROJECT_SCOPE",
            "P503_BASELINE_CREATE_MEMBER_DOMAIN_BUILD",
            "P503_BASELINE_CREATE_MEMBER_FILE_QUERY",
            "P503_BASELINE_CREATE_MEMBER_FILE_ASSOCIATION_LOAD",
            "P503_BASELINE_CREATE_MEMBER_FILE_CARDINALITY",
            "P503_BASELINE_CREATE_MEMBER_FILE_LOAD",
            "P503_BASELINE_CREATE_MEMBER_FILE_INTEGRITY",
        }
        helper_source = "\n".join(
            (
                _function("_resolve_members"),
                _function("_resolve_member_input"),
                _function("_validate_released_files"),
            )
        )
        for code in helper_codes:
            with self.subTest(code=code):
                self.assertEqual(helper_source.count(f'"{code}"'), 1)

    def test_public_response_is_url_and_storage_identity_free(self) -> None:
        wrapper = _function("_baseline_response")
        self.assertIn("document_baseline_response(value)", wrapper)
        response = _function("document_baseline_response")
        value = response.casefold()
        for forbidden in (
            "file_url",
            "fileurl",
            "private_url",
            "download_url",
            "frappe_file_id",
            "frappe_content_hash",
            "storage_identity",
            "cookie",
            "credential",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, value)
        self.assertIn('"releaseSnapshotHash"', response)
        self.assertIn('"files"', response)

    def test_exact_public_loader_scopes_root_and_locks_member_rows(self) -> None:
        loader = _function("load_document_baseline")
        validator = _function("_validated_baseline_value")
        self.assertIn('"NPI Document Baseline"', loader)
        self.assertIn("for_update=lock", loader)
        self.assertIn("str(document.tenant_id) != str(project.tenant_id)", loader)
        self.assertIn(
            "str(document.project_global_id) != str(project.global_id)",
            loader,
        )
        self.assertIn('filters={"baseline_global_id": str(document.global_id)}', validator)
        self.assertIn("limit_page_length=MAX_BASELINE_MEMBERS + 1", validator)
        self.assertIn("for_update=lock_members", validator)
        for exact_field in (
            "row.tenant_id",
            "row.project_global_id",
            "row.document_baseline",
            "row.baseline_global_id",
            "row.member_snapshot",
            "row.member_hash",
            "row.baseline_snapshot_hash",
        ):
            with self.subTest(exact_field=exact_field):
                self.assertIn(exact_field, validator)

    def test_impact_loader_revalidates_registered_lineage_and_safe_response(
        self,
    ) -> None:
        workspace = _function("list_baselines")
        loader = _function("load_project_baseline_impacts")
        validator = _function("_validated_baseline_impact")
        response = _function("document_baseline_impact_response")
        for exact_scope in (
            '"tenant_id": str(project.tenant_id)',
            '"project_global_id": str(project.global_id)',
            'filters["gate_global_id"] = str(gate_global_id)',
        ):
            with self.subTest(exact_scope=exact_scope):
                self.assertIn(exact_scope, loader)
        for exact_parent in (
            '"NPI Baseline Gate Dependency"',
            '"NPI Gate Evidence Reference"',
            '"NPI Gate Shell"',
            '"NPI Document Revision"',
            "dependency.snapshot_payload()",
            "event.event_payload()",
            "load_document_baseline(",
            'str(evidence.evidence_kind) != "release_baseline"',
            "successor.predecessor_revision_global_id",
        ):
            with self.subTest(exact_parent=exact_parent):
                self.assertIn(exact_parent, validator)
        for forbidden in (
            "requestId",
            "traceId",
            "fileUrl",
            "privateUrl",
            "cookie",
            "credential",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden.casefold(), response.casefold())
        self.assertIn('"eventHash"', response)
        self.assertIn("impacts = load_project_baseline_impacts(project)", workspace)
        self.assertIn("document_baseline_impact_response(value)", workspace)


if __name__ == "__main__":
    unittest.main()
