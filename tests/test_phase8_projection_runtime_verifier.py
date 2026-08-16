from __future__ import annotations

import ast
import importlib
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "apps" / "npi_integration"))


class Phase8ProjectionRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fixture_env = "NPI_DOCUMENT_RUNTIME_RUN_ID"
        previous = os.environ.get(fixture_env)
        os.environ[fixture_env] = "80180180180180180180180180180180"
        try:
            cls.runtime = importlib.import_module("verify_projection_runtime")
        finally:
            if previous is None:
                os.environ.pop(fixture_env, None)
            else:
                os.environ[fixture_env] = previous

    def test_deterministic_runtime_identity_is_stable_uuid_v4(self) -> None:
        first = self.runtime.deterministic_uuid("observation")
        second = self.runtime.deterministic_uuid("observation")
        self.assertEqual(first, second)
        self.assertIsInstance(first, UUID)
        self.assertEqual(first.version, 4)
        sequence = self.runtime.sequence_uuid_factory("batch")
        values = [sequence(), sequence(), sequence()]
        self.assertEqual(len(set(values)), 3)
        self.assertTrue(all(value.version == 4 for value in values))

    def test_seven_runtime_values_are_closed_and_use_server_scope_ids(self) -> None:
        from npi_integration.projections.domain import ProjectionKind

        master_id = "00000000-0000-4000-8000-000000000820"
        tooling_set_id = "00000000-0000-4000-8000-000000000830"
        values = {
            kind: self.runtime.projection_values(
                kind,
                master_id=master_id,
                tooling_set_id=tooling_set_id,
            )
            for kind in ProjectionKind
        }
        self.assertEqual(
            set(kind.value for kind in values), set(self.runtime.KINDS)
        )
        self.assertEqual(self.runtime.KINDS, tuple(sorted(self.runtime.KINDS)))
        self.assertEqual(
            values[ProjectionKind.TOOLING_PROCUREMENT_COST][
                "toolingMasterGlobalId"
            ],
            master_id,
        )
        self.assertEqual(
            values[ProjectionKind.TOOLING_PROCUREMENT_COST]["rows"][0][
                "toolingMasterGlobalId"
            ],
            master_id,
        )
        self.assertEqual(
            values[ProjectionKind.TOOL_ASSET_STATUS]["toolingSetGlobalId"],
            tooling_set_id,
        )
        self.assertEqual(
            values[ProjectionKind.TOOLING_PROCUREMENT_COST]["rows"][0]["amount"],
            "1200.50",
        )

    def test_runtime_source_closes_network_authority_and_persistence_proof(self) -> None:
        source = (SCRIPTS / "verify_projection_runtime.py").read_text(
            encoding="utf-8"
        )
        ast.parse(source)
        self.assertIn('base_url="https://erp.sandbox.example.test"', source)
        self.assertIn('allowed_hostnames=("erp.sandbox.example.test",)', source)
        self.assertIn('follow_redirects=False', source)
        self.assertIn('secret_reference="secrets/p8-runtime-sandbox-read"', source)
        self.assertIn('"headCount"] == 7', source)
        self.assertIn('"observationCount"] == 25', source)
        self.assertIn('"auditCount"] == 25', source)
        for disposition in (
            "synthetic_retained",
            "unavailable_current",
            "applied_current",
            "superseded",
            "conflicted",
        ):
            self.assertIn(disposition, source)
        self.assertIn("same_process_replay", source)
        self.assertIn("cross-process replay changed retained projection truth", source)
        self.assertNotIn("ignore_mandatory", source)
        self.assertNotIn("ignore_validate", source)
        self.assertNotIn("requests.get", source)
        self.assertNotIn("requests.post", source)

    def test_http_proof_covers_auth_redaction_filters_consumers_and_switch(self) -> None:
        source = (SCRIPTS / "verify_projection_runtime.py").read_text(
            encoding="utf-8"
        )
        for marker in (
            "AUTHENTICATION_REQUIRED",
            "PROJECT_UNAVAILABLE",
            "projection_access_redacted",
            "VALIDATION_FAILED",
            "ERP_PROJECTION_ROUTES_DISABLED",
            "assert_tooling_consumers",
            "edit\": False",
            "refresh\": False",
            "private, no-store",
            "X-Request-ID",
        ):
            self.assertIn(marker, source)
        self.assertIn("sourceObjectId=forbidden", source)
        self.assertIn("zero_or_one_per_physical_set", source)

    def test_consumer_proof_uses_canonical_decimal_text(self) -> None:
        source = (SCRIPTS / "verify_projection_runtime.py").read_text(
            encoding="utf-8"
        )
        http_consumer = source[
            source.index("def assert_tooling_consumers(") : source.index(
                "def retained_context("
            )
        ]
        direct_consumer = source[
            source.index("def _assert_consumers(") : source.index(
                "def seed_projection_truth("
            )
        ]
        for consumer in (http_consumer, direct_consumer):
            self.assertIn('cost["rows"][0].get("amount") == "1200.5"', consumer)
            self.assertNotIn('cost["rows"][0].get("amount") == "1200.50"', consumer)

    def test_consumer_proof_uses_asset_payload_target_version(self) -> None:
        source = (SCRIPTS / "verify_projection_runtime.py").read_text(
            encoding="utf-8"
        )
        http_consumer = source[
            source.index("def assert_tooling_consumers(") : source.index(
                "def retained_context("
            )
        ]
        direct_consumer = source[
            source.index("def _assert_consumers(") : source.index(
                "def seed_projection_truth("
            )
        ]
        for consumer in (http_consumer, direct_consumer):
            self.assertIn(
                'asset.get("targetVersion") == "sandbox-asset-v1"', consumer
            )
            self.assertNotIn(
                'asset.get("targetVersion") == "sandbox-v1"', consumer
            )

    def test_retained_context_uses_exact_fixture_identity_not_global_cardinality(self) -> None:
        source = (SCRIPTS / "verify_projection_runtime.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('value.get("title") == "Synthetic shared front housing tool"', source)
        self.assertIn('value.get("title") == "Synthetic front housing revised"', source)
        self.assertIn('value.get("globalId") in linked_part_ids', source)
        self.assertIn('value["part"].get("partGlobalId")', source)
        self.assertIn('value.get("physicalSerial") == "P6-02-PHYSICAL-001"', source)
        self.assertNotIn(
            "tooling_revision_runtime.project_context(administrator, base_url)", source
        )

    def test_retained_context_rejects_same_title_part_not_linked_to_master(self) -> None:
        project_id = "00000000-0000-4000-8000-000000000801"
        master_id = "00000000-0000-4000-8000-000000000802"
        part_id = "00000000-0000-4000-8000-000000000803"
        part_revision_id = "00000000-0000-4000-8000-000000000804"
        unrelated_part_id = "00000000-0000-4000-8000-000000000805"
        tooling_set_id = "00000000-0000-4000-8000-000000000806"
        responses = [
            SimpleNamespace(
                status=200,
                body={
                    "references": [
                        {
                            "type": "customer",
                            "sourceSystem": "ERPNEXT",
                            "sourceObjectId": "customer-fixture",
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status=200,
                body={
                    "masters": [
                        {
                            "globalId": master_id,
                            "title": "Synthetic shared front housing tool",
                            "originatingProjectGlobalId": project_id,
                        }
                    ],
                    "parts": [
                        {
                            "globalId": unrelated_part_id,
                            "title": "Synthetic front housing revised",
                            "currentRevision": {
                                "globalId": "00000000-0000-4000-8000-000000000807",
                                "partGlobalId": unrelated_part_id,
                                "revisionNumber": 2,
                                "revisionLabel": "B",
                            },
                        },
                        {
                            "globalId": part_id,
                            "title": "Synthetic front housing revised",
                            "currentRevision": {
                                "globalId": part_revision_id,
                                "partGlobalId": part_id,
                                "revisionNumber": 2,
                                "revisionLabel": "B",
                            },
                        },
                    ],
                    "applicability": [
                        {
                            "projectGlobalId": project_id,
                            "toolingMasterGlobalId": master_id,
                            "part": {"partGlobalId": part_id},
                        }
                    ],
                },
            ),
            SimpleNamespace(
                status=200,
                body={
                    "items": [
                        {
                            "globalId": tooling_set_id,
                            "toolingMasterGlobalId": master_id,
                            "physicalSerial": "P6-02-PHYSICAL-001",
                        }
                    ]
                },
            ),
        ]
        with (
            patch.object(
                self.runtime.document_runtime,
                "fixture_project",
                return_value=(project_id, 1),
            ),
            patch.object(
                self.runtime.tooling_runtime,
                "tooling_request",
                side_effect=responses,
            ),
        ):
            context = self.runtime.retained_context(object(), "http://127.0.0.1")
        self.assertEqual(context["project_id"], project_id)
        self.assertEqual(context["master_id"], master_id)
        self.assertEqual(context["part_id"], part_id)
        self.assertEqual(context["tooling_set_id"], tooling_set_id)

    def test_fixture_context_uses_tooling_master_ownership_contract(self) -> None:
        project_id = "00000000-0000-4000-8000-000000000801"
        master_id = "00000000-0000-4000-8000-000000000802"
        part_id = "00000000-0000-4000-8000-000000000803"
        tooling_set_id = "00000000-0000-4000-8000-000000000804"
        documents = {
            ("NPI Engineering Project", project_id): SimpleNamespace(
                global_id=project_id,
                tenant_id=self.runtime.TENANT_ID,
            ),
            ("NPI Tooling Master", master_id): SimpleNamespace(
                originating_project_global_id=project_id,
                tenant_id=self.runtime.TENANT_ID,
            ),
            ("NPI Engineering Part", part_id): SimpleNamespace(
                originating_project_global_id=project_id,
                tenant_id=self.runtime.TENANT_ID,
            ),
            ("NPI Tooling Set", tooling_set_id): SimpleNamespace(
                project_global_id=project_id,
                tooling_master_global_id=master_id,
                tenant_id=self.runtime.TENANT_ID,
            ),
        }
        frappe = SimpleNamespace(
            get_doc=lambda doctype, name: documents[(doctype, name)]
        )
        with (
            patch.dict(sys.modules, {"frappe": frappe}),
            patch.object(
                self.runtime.document_runtime,
                "_validated_runtime_site",
            ),
        ):
            self.runtime._validate_fixture_context(
                fixture_run_id=self.runtime.FIXTURE_RUN_ID,
                project_id=project_id,
                master_id=master_id,
                part_id=part_id,
                tooling_set_id=tooling_set_id,
            )

    def test_shell_projection_mode_is_cumulative_and_restores_route_switch(self) -> None:
        source = (SCRIPTS / "verify-frappe-runtime.sh").read_text(encoding="utf-8")
        self.assertIn('"--projection-only"', source)
        self.assertGreaterEqual(source.count('"${verification_mode}" == "--projection-only"'), 5)
        for marker in (
            "npi_p8_01_routes_disabled",
            "projection_route_disable_original_state",
            "projection_route_disable_config_changed",
            "set_projection_route_switch",
            "restore_projection_route_switch",
            "run_projection_runtime_verifier fresh",
            "run_projection_route_probe disabled",
            "run_projection_route_probe recovered",
            "run_projection_runtime_verifier replay-only",
            "verify_projection_runtime_log_redaction",
        ):
            self.assertIn(marker, source)
        self.assertLess(
            source.index('run_released_summary_runtime_verifier fresh'),
            source.index('run_projection_runtime_verifier fresh'),
        )

    def test_level3_workflow_runs_exact_projection_mode_and_records_scope(self) -> None:
        source = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("tests.test_phase8_projection_runtime_verifier", source)
        self.assertIn(
            "bash scripts/verify-frappe-runtime.sh --projection-only", source
        )
        self.assertIn("scope=p5-01-through-p8-02", source)
        self.assertIn("predecessor_scope=p5-01-through-p8-01", source)
        self.assertIn("p8-integration-runtime-${{ github.run_id }}", source)
        self.assertIn("needs.controlled_preflight.result == 'success'", source)


if __name__ == "__main__":
    unittest.main()
