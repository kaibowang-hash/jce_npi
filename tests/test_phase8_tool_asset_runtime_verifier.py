from __future__ import annotations

import importlib
import os
import sys
import types
import unittest
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit
from unittest.mock import patch
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "apps/npi_integration")]


class Phase8ToolAssetRuntimeVerifierTest(unittest.TestCase):
    def setUp(self):
        fake = sys.modules.setdefault("frappe", types.ModuleType("frappe"))
        fake.session = types.SimpleNamespace(user="worker@example.invalid")
        self.fixture = importlib.reload(importlib.import_module("npi_integration.tool_asset_request.runtime_fixture"))
        self.verifier = importlib.reload(importlib.import_module("verify_tool_asset_execution_runtime"))
        self.environment = {"NPI_TOOL_ASSET_RUNTIME_MARKER":"npi-one-tool-asset-disposable-v1", "NPI_TOOL_ASSET_REQUESTER_USER":"engineer@example.invalid", "NPI_TOOL_ASSET_WORKER_USER":"worker@example.invalid"}

    def test_disabled_by_default_installs_no_profile_or_adapter(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(self.fixture.resolve_profile("tenant-a", str(UUID(int=1))))
            self.assertIsNone(self.fixture.resolve_adapter_registry())

    def test_disposable_configuration_is_network_free_and_shell_governed(self):
        source = (ROOT / "apps/npi_integration/npi_integration/tool_asset_request/runtime_fixture.py").read_text(encoding="utf-8")
        self.assertNotIn("requests", source)
        self.assertNotIn("httpx", source)
        shell = (ROOT / "scripts/verify-frappe-runtime.sh").read_text(encoding="utf-8")
        for marker in ("run_tool_asset_runtime_verifier disabled", "run_tool_asset_runtime_verifier fresh", "NPI_TOOL_ASSET_RUNTIME_MARKER=npi-one-tool-asset-disposable-v1", "verify_tool_asset_execution_runtime.py"):
            self.assertIn(marker, shell)

    def test_shell_binds_exact_retained_p6_requester_and_distinct_worker(self):
        shell = (ROOT / "scripts" / "verify-frappe-runtime.sh").read_text(
            encoding="utf-8"
        )
        expected_requester = (
            f"npi-tooling-manufacturing-{self.verifier.FIXTURE_RUN_ID[:12]}-"
            "manager@example.invalid"
        )
        self.assertEqual(self.verifier.ACTOR_USER, expected_requester)
        self.assertIn(
            'tool_asset_runtime_requester="npi-tooling-manufacturing-'
            '${document_runtime_run_id:0:12}-manager@example.invalid"',
            shell,
        )
        export_source = shell[
            shell.index("export_tool_asset_runtime_environment() {") :
            shell.index("\n}\n\nclear_tool_asset_runtime_environment()")
        ]
        self.assertIn(
            'NPI_TOOL_ASSET_REQUESTER_USER="${tool_asset_runtime_requester}"',
            export_source,
        )
        self.assertIn(
            'NPI_TOOL_ASSET_WORKER_USER="${inbound_project_runtime_actor}"',
            export_source,
        )
        self.assertNotIn("item_publish_runtime_actor", export_source)
        self.assertNotEqual(
            expected_requester,
            f"npi-inbound-{self.verifier.FIXTURE_RUN_ID[:12]}@example.invalid",
        )

    def test_retained_requester_is_enabled_internal_and_not_cleaned_up(self):
        manufacturing = (
            ROOT / "scripts/verify_tooling_manufacturing_runtime.py"
        ).read_text(encoding="utf-8")
        prepare = manufacturing[
            manufacturing.index("def prepare_manufacturing_actor(") :
            manufacturing.index("\ndef active_member(")
        ]
        for marker in (
            '"enabled": 1',
            '"user_type": "System User"',
            '{"role": "NPI API User"}',
            '{"role": "System Manager"}',
            'data.get("enabled") == 1',
            'data.get("user_type") == "System User"',
            '{"NPI API User", "System Manager"} <= roles',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, prepare)
        self.assertNotIn("delete_disposable_user", prepare)
        shell = (ROOT / "scripts" / "verify-frappe-runtime.sh").read_text(
            encoding="utf-8"
        )
        self.assertLess(
            shell.index("run_tooling_manufacturing_runtime_verifier fresh"),
            shell.index("run_tool_asset_runtime_verifier fresh"),
        )

    def test_runtime_actor_predicates_fail_before_command_without_relaxation(self):
        project_id = str(UUID(int=1))
        context = {
            "projectId": project_id,
            "masterId": str(UUID(int=2)),
            "toolingSetId": str(UUID(int=3)),
        }
        worker = "npi-inbound-worker@example.invalid"
        valid = {
            "NPI_TOOL_ASSET_RUNTIME_PROJECT_ID": project_id,
            "NPI_TOOL_ASSET_REQUESTER_USER": self.verifier.ACTOR_USER,
            "NPI_TOOL_ASSET_WORKER_USER": worker,
        }
        invalid = {
            "project": {**valid, "NPI_TOOL_ASSET_RUNTIME_PROJECT_ID": str(UUID(int=4))},
            "requester": {**valid, "NPI_TOOL_ASSET_REQUESTER_USER": "different@example.invalid"},
            "worker-missing": {
                key: value
                for key, value in valid.items()
                if key != "NPI_TOOL_ASSET_WORKER_USER"
            },
            "worker-empty": {**valid, "NPI_TOOL_ASSET_WORKER_USER": ""},
            "worker-equals-requester": {
                **valid,
                "NPI_TOOL_ASSET_WORKER_USER": self.verifier.ACTOR_USER,
            },
        }
        for name, environment in invalid.items():
            with self.subTest(name=name), patch.dict(
                os.environ, environment, clear=True
            ), patch.object(
                self.verifier,
                "secret_from_environment",
                return_value="administrator-password",
            ), patch.object(self.verifier, "login", return_value=object()), patch.object(
                self.verifier, "bootstrap_csrf", return_value="csrf"
            ), patch.object(
                self.verifier, "_retained_context", return_value=(context, {})
            ), patch.object(self.verifier, "execution_request") as request:
                with self.assertRaisesRegex(
                    RuntimeError, "^P8-05 runtime actors are not exactly bound$"
                ):
                    self.verifier.run_fresh(
                        "http://127.0.0.1:8003", "fixture-password"
                    )
                request.assert_not_called()

        class CommandBoundaryReached(Exception):
            pass

        with patch.dict(os.environ, valid, clear=True), patch.object(
            self.verifier,
            "secret_from_environment",
            return_value="administrator-password",
        ), patch.object(
            self.verifier, "login", return_value=object()
        ), patch.object(
            self.verifier, "bootstrap_csrf", return_value="csrf"
        ), patch.object(
            self.verifier, "_retained_context", return_value=(context, {})
        ), patch.object(
            self.verifier,
            "_execution_state_snapshot",
            return_value={"NPI Tool Asset Request": 0},
        ), patch.object(
            self.verifier,
            "execution_request",
            side_effect=CommandBoundaryReached,
        ) as request:
            with self.assertRaises(CommandBoundaryReached):
                self.verifier.run_fresh(
                    "http://127.0.0.1:8003", "fixture-password"
                )
            request.assert_called_once()

    def test_mapped_collection_is_read_only_before_distinct_unmapped_create(self):
        self.assertFalse(self.verifier.TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED)
        self.assertFalse(
            self.verifier.POST_QUERY_TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier._post_query_command_context_diagnostics_enabled()
        )
        self.assertTrue(
            self.verifier.TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTICS_ENABLED
        )
        self.assertTrue(
            self.verifier._tool_asset_create_response_diagnostics_enabled()
        )
        project_id = str(UUID(int=1))
        retained_master_id = str(UUID(int=2))
        retained_set_id = str(UUID(int=3))
        retained_acceptance_id = str(UUID(int=4))
        disposable_master_id = str(UUID(int=5))
        disposable_set_id = str(UUID(int=6))
        disposable_acceptance_id = str(UUID(int=7))
        retained = {
            "projectId": project_id,
            "masterId": retained_master_id,
            "toolingSetId": retained_set_id,
        }
        retained_acceptance = {"globalId": retained_acceptance_id}
        disposable = {
            **retained,
            "masterId": disposable_master_id,
            "toolingSetId": disposable_set_id,
        }
        disposable_acceptance = {"globalId": disposable_acceptance_id}
        source = {"acceptanceRevisionGlobalId": disposable_acceptance_id}
        create = {
            "source": source,
            "expectedSourceHash": "a" * 64,
            "expectedApprovalHash": "b" * 64,
            "expectedMappingExpectationHash": "c" * 64,
            "expectedProfileSnapshotHash": "d" * 64,
        }
        valid_environment = {
            "NPI_TOOL_ASSET_RUNTIME_PROJECT_ID": project_id,
            "NPI_TOOL_ASSET_REQUESTER_USER": self.verifier.ACTOR_USER,
            "NPI_TOOL_ASSET_WORKER_USER": "npi-inbound-worker@example.invalid",
        }
        with patch.dict(os.environ, valid_environment, clear=True):
            profile = self.verifier._expected_synthetic_profile(project_id)
        mapped_body = {
            "projectGlobalId": project_id,
            "toolingMasterGlobalId": retained_master_id,
            "toolingSetGlobalId": retained_set_id,
            "items": [],
            "commandContexts": None,
            "executionProfile": profile,
        }
        disposable_body = {
            **mapped_body,
            "toolingMasterGlobalId": disposable_master_id,
            "toolingSetGlobalId": disposable_set_id,
            "commandContexts": {"create_tool_asset": create},
        }
        object_actor = object()
        class PostReached(Exception):
            pass

        mapped = types.SimpleNamespace(status=200, body=mapped_body)
        listed = types.SimpleNamespace(status=200, body=disposable_body)
        with patch.dict(
            os.environ, valid_environment, clear=True
        ), patch.object(
            self.verifier,
            "secret_from_environment",
            return_value="administrator-password",
        ), patch.object(
            self.verifier, "login", return_value=object_actor
        ), patch.object(
            self.verifier, "bootstrap_csrf", return_value="csrf"
        ), patch.object(
            self.verifier,
            "_retained_context",
            return_value=(retained, retained_acceptance),
        ), patch.object(
            self.verifier,
            "_execution_state_snapshot",
            side_effect=(
                {"NPI Tool Asset Request": 0},
                {"NPI Tool Asset Request": 0},
            ),
        ) as snapshots, patch.object(
            self.verifier,
            "_create_disposable_execution_context",
            return_value=(disposable, disposable_acceptance),
        ) as create_fixture, patch.object(
            self.verifier.item_runtime,
            "_replay_diagnostic_log_cursors",
            return_value={"logs/bench.log": 0},
        ) as cursor_reader, patch.object(
            self.verifier.item_runtime,
            "_sanitized_server_log_diagnostic",
        ) as diagnostic_reader, patch.object(
            self.verifier,
            "execution_request",
            side_effect=(mapped, listed, PostReached),
        ), patch.object(
            self.verifier,
            "_assert_no_formal_target",
        ):
            with self.assertRaises(PostReached):
                self.verifier.run_fresh(
                    "http://127.0.0.1:8003", "fixture-password"
                )
            self.assertEqual(snapshots.call_count, 2)
            create_fixture.assert_called_once_with(
                object_actor,
                "http://127.0.0.1:8003",
                "csrf",
                retained,
            )
            cursor_reader.assert_called_once_with()
            diagnostic_reader.assert_not_called()
            first_args, first_kwargs = self.verifier.execution_request.call_args_list[0]
            split = urlsplit(first_args[2])
            self.assertEqual(
                split.path,
                self.verifier.execution_path(
                    project_id,
                    retained_master_id,
                    retained_set_id,
                ),
            )
            self.assertEqual(
                parse_qsl(split.query, keep_blank_values=True),
                [("acceptanceRevisionGlobalId", retained_acceptance_id)],
            )
            self.assertEqual(
                first_kwargs,
                {
                    "method": "GET",
                    "query_key": "enabled-retained-mapped",
                },
            )
            second_args, second_kwargs = self.verifier.execution_request.call_args_list[1]
            second_split = urlsplit(second_args[2])
            self.assertEqual(
                second_split.path,
                self.verifier.execution_path(
                    project_id,
                    disposable_master_id,
                    disposable_set_id,
                ),
            )
            self.assertEqual(
                parse_qsl(second_split.query, keep_blank_values=True),
                [("acceptanceRevisionGlobalId", disposable_acceptance_id)],
            )
            self.assertEqual(
                second_kwargs,
                {
                    "method": "GET",
                    "query_key": "enabled-disposable-unmapped",
                },
            )
            self.assertEqual(self.verifier.execution_request.call_count, 3)
            post_args, post_kwargs = self.verifier.execution_request.call_args_list[2]
            self.assertEqual(
                post_args[2],
                self.verifier.execution_path(
                    project_id,
                    disposable_master_id,
                    disposable_set_id,
                    ":create",
                ),
            )
            self.assertEqual(post_kwargs["method"], "POST")
            self.assertEqual(
                post_kwargs["diagnostic_scope"],
                self.verifier.TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_SCOPE,
            )

    def test_create_response_parent_codes_are_ordered_value_free_and_server_wins(self):
        trace_id = "trace-" + "e" * 32
        valid = {
            "requestGlobalId": str(UUID(int=21)),
            "outboxEventId": str(UUID(int=22)),
            "request": {"state": "queued"},
        }
        secret = "private-create-response-value"
        cases = (
            ("P805_TOOL_ASSET_CREATE_HTTP_STATUS", types.SimpleNamespace(status=503, body={"opaque": secret}, trace_id=trace_id)),
            ("P805_TOOL_ASSET_CREATE_BODY_SHAPE", types.SimpleNamespace(status=201, body=secret, trace_id=trace_id)),
            ("P805_TOOL_ASSET_CREATE_REQUEST_SHAPE", types.SimpleNamespace(status=201, body={**valid, "request": secret}, trace_id=trace_id)),
            ("P805_TOOL_ASSET_CREATE_REQUEST_STATE", types.SimpleNamespace(status=201, body={**valid, "request": {"state": secret}}, trace_id=trace_id)),
            ("P805_TOOL_ASSET_CREATE_REQUEST_ID", types.SimpleNamespace(status=201, body={**valid, "requestGlobalId": secret}, trace_id=trace_id)),
            ("P805_TOOL_ASSET_CREATE_OUTBOX_ID", types.SimpleNamespace(status=201, body={**valid, "outboxEventId": secret}, trace_id=trace_id)),
        )
        for code, result in cases:
            with self.subTest(code=code), patch.object(
                self.verifier.item_runtime,
                "_sanitized_server_log_diagnostic",
                return_value=None,
            ) as reader:
                message = self.verifier._tool_asset_create_response_failure_message(
                    result,
                    {"logs/bench.log": 0},
                )
            self.assertIn(f"diagnostic_code={code}", message)
            self.assertIn("exception_type=RuntimeError", message)
            self.assertIn(f"trace_id={trace_id}", message)
            self.assertNotIn(secret, message)
            self.assertNotIn("503", message)
            reader.assert_called_once_with(
                trace_id,
                {"logs/bench.log": 0},
                code_prefix="P805_TOOL_ASSET_CREATE_",
                allowed_codes=self.verifier.TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_CODES,
            )

        with patch.object(
            self.verifier.item_runtime,
            "_sanitized_server_log_diagnostic",
            return_value=(
                "RequestValidationFailed",
                "P805_TOOL_ASSET_CREATE_INPUT_PARSE",
                trace_id,
            ),
        ):
            message = self.verifier._tool_asset_create_response_failure_message(
                cases[0][1],
                {},
            )
        self.assertIn("diagnostic_code=P805_TOOL_ASSET_CREATE_INPUT_PARSE", message)
        self.assertIn("exception_type=RequestValidationFailed", message)
        self.assertNotIn(secret, message)

    def test_create_response_diagnostic_is_closed_for_success_off_and_bad_trace(self):
        trace_id = "trace-" + "f" * 32
        valid = {
            "requestGlobalId": str(UUID(int=31)),
            "outboxEventId": str(UUID(int=32)),
            "request": {"state": "queued"},
        }
        with patch.object(
            self.verifier.item_runtime,
            "_sanitized_server_log_diagnostic",
        ) as reader:
            self.assertIsNone(
                self.verifier._tool_asset_create_response_failure_message(
                    types.SimpleNamespace(status=201, body=valid, trace_id=trace_id),
                    {},
                )
            )
            reader.assert_not_called()

        failure = types.SimpleNamespace(status=500, body={}, trace_id=trace_id)
        with patch.object(
            self.verifier,
            "TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier.item_runtime,
            "_sanitized_server_log_diagnostic",
        ) as reader:
            self.assertEqual(
                self.verifier._tool_asset_create_response_failure_message(failure, {}),
                self.verifier._TOOL_ASSET_CREATE_RESPONSE_FAILURE,
            )
            reader.assert_not_called()

        for invalid_trace in (None, "trace-invalid", "private-trace-value"):
            with self.subTest(trace=invalid_trace), patch.object(
                self.verifier.item_runtime,
                "_sanitized_server_log_diagnostic",
            ) as reader:
                self.assertEqual(
                    self.verifier._tool_asset_create_response_failure_message(
                        types.SimpleNamespace(status=500, body={}, trace_id=invalid_trace),
                        {},
                    ),
                    self.verifier._TOOL_ASSET_CREATE_RESPONSE_FAILURE,
                )
                reader.assert_not_called()

    def test_create_response_scope_is_exact_and_uses_shared_http_trace_result(self):
        payload = {
            "acceptanceRevisionGlobalId": str(UUID(int=41)),
            "expectedSourceHash": "a" * 64,
            "expectedApprovalHash": "b" * 64,
            "expectedMappingExpectationHash": "c" * 64,
            "expectedProfileSnapshotHash": "d" * 64,
            "acknowledgement": self.verifier.ACKNOWLEDGEMENT,
        }
        response = types.SimpleNamespace(
            status=500,
            body={},
            trace_id="trace-" + "a" * 32,
            headers={"X-Request-ID": "p805-create", "Cache-Control": "private, no-store"},
        )
        path = self.verifier.execution_path(
            str(UUID(int=42)),
            str(UUID(int=43)),
            str(UUID(int=44)),
            ":create",
        )
        with patch.object(
            self.verifier.document_runtime,
            "command_headers",
            return_value={"X-Request-ID": "p805-create"},
        ), patch.object(
            self.verifier.document_runtime,
            "request",
            return_value=response,
        ) as request:
            observed = self.verifier.execution_request(
                object(),
                "http://127.0.0.1:8003",
                path,
                method="POST",
                payload=payload,
                csrf_token="csrf",
                idempotency_key="fixed-key",
                diagnostic_scope=self.verifier.TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_SCOPE,
            )
        self.assertIs(observed, response)
        self.assertEqual(
            request.call_args.kwargs["request_headers"]["X-NPI-Diagnostic-Scope"],
            "p805-tool-asset-create-response-v1",
        )
        source = (ROOT / "scripts/verify_tool_asset_execution_runtime.py").read_text(encoding="utf-8")
        self.assertNotIn('headers.get("X-Trace-ID")', source)

        defaults = {
            "path": path,
            "method": "POST",
            "payload": payload,
            "csrf_token": "csrf",
            "idempotency_key": "fixed-key",
        }
        for change in (
            {"method": "GET"},
            {"path": path + "?extra=wrong"},
            {"payload": {**payload, "extra": "wrong"}},
            {"csrf_token": None},
            {"idempotency_key": None},
        ):
            values = {**defaults, **change}
            candidate_path = values.pop("path")
            with self.subTest(change=change), self.assertRaisesRegex(
                RuntimeError,
                self.verifier._TOOL_ASSET_CREATE_RESPONSE_FAILURE,
            ):
                self.verifier.execution_request(
                    object(),
                    "http://127.0.0.1:8003",
                    candidate_path,
                    diagnostic_scope=self.verifier.TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_SCOPE,
                    **values,
                )

    def test_create_response_server_allowlist_matches_unique_lexical_contexts(self):
        diagnostics = importlib.import_module(
            "npi_integration.tool_asset_request.diagnostics"
        )
        self.assertEqual(
            self.verifier.TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_CODES,
            diagnostics.TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_CODES,
        )
        source = "\n".join(
            (
                (ROOT / "apps/npi_integration/npi_integration/tool_asset_request_api.py").read_text(encoding="utf-8"),
                (ROOT / "apps/npi_integration/npi_integration/tool_asset_request/frappe_repository.py").read_text(encoding="utf-8"),
            )
        )
        for code in diagnostics.TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_CODES:
            with self.subTest(code=code):
                self.assertEqual(source.count(f'"{code}"'), 1)

    def test_disposable_fixture_is_exact_distinct_and_fail_closed(self):
        project_id = str(UUID(int=1))
        retained_master_id = str(UUID(int=2))
        retained_set_id = str(UUID(int=3))
        retained_tooling_revision_id = str(UUID(int=4))
        part_id = str(UUID(int=7))
        part_revision_id = str(UUID(int=8))
        existing_applicability_id = str(UUID(int=9))
        part_context = (part_id, part_revision_id, existing_applicability_id)
        administrator = object()
        retained = {
            "projectId": project_id,
            "masterId": retained_master_id,
            "toolingSetId": retained_set_id,
            "engineeringRevisionId": retained_tooling_revision_id,
            "member": {"globalId": str(UUID(int=5))},
            "fileEvidence": {
                "fileRevisionGlobalId": str(UUID(int=6)),
                "fileOptimisticVersion": 1,
                "frappeContentHash": "a" * 64,
                "sha256": "b" * 64,
            },
        }
        command_result = types.SimpleNamespace(body={})
        master = {
            "globalId": str(UUID(int=10)),
            "title": self.verifier._DISPOSABLE_MASTER_TITLE,
            "originatingProjectGlobalId": project_id,
            "snapshotHash": "1" * 64,
        }
        requirement = {
            "globalId": str(UUID(int=11)),
            "title": self.verifier._DISPOSABLE_REQUIREMENT_TITLE,
            "kind": "customer_owned_intake",
        }
        applicability = {
            "globalId": str(UUID(int=12)),
            "toolingMasterGlobalId": master["globalId"],
            "part": {"globalId": part_revision_id},
        }
        revision = {
            "globalId": str(UUID(int=13)),
            "snapshotHash": "2" * 64,
        }
        tooling_set = {
            "globalId": str(UUID(int=14)),
            "physicalSerial": self.verifier._DISPOSABLE_PHYSICAL_SERIAL,
            "requirementKind": "customer_owned_intake",
            "snapshotHash": "3" * 64,
        }
        binding = {
            "globalId": str(UUID(int=15)),
            "snapshotHash": "4" * 64,
        }
        binding_result = types.SimpleNamespace(
            body={"toolingSet": {"sourceRevision": binding}}
        )
        acceptance = {"globalId": str(UUID(int=16))}

        for name, invalid_context in (
            ("missing", None),
            ("malformed-shape", (part_id, part_revision_id)),
            ("malformed-revision", (part_id, None, existing_applicability_id)),
            (
                "reused-tooling-revision",
                (
                    part_id,
                    retained_tooling_revision_id,
                    existing_applicability_id,
                ),
            ),
        ):
            with self.subTest(part_context=name), patch.object(
                self.verifier.tooling_revision,
                "dedicated_part_context",
                return_value=invalid_context,
            ) as dedicated_part_context, patch.object(
                self.verifier.tooling_base,
                "command",
            ) as command, patch.object(
                self.verifier.tooling_revision,
                "command",
            ) as revision_command, patch.object(
                self.verifier.tooling_runtime,
                "command",
            ) as acceptance_command:
                with self.assertRaises(RuntimeError):
                    self.verifier._create_disposable_execution_context(
                        administrator,
                        "http://127.0.0.1:8003",
                        "csrf",
                        retained,
                    )
                dedicated_part_context.assert_called_once_with(
                    administrator,
                    "http://127.0.0.1:8003",
                    project_id,
                )
                command.assert_not_called()
                revision_command.assert_not_called()
                acceptance_command.assert_not_called()

        for name, masters in (
            ("missing", []),
            ("duplicate", [master, dict(master)]),
            ("retained-identity", [{**master, "globalId": retained_master_id}]),
        ):
            with self.subTest(name=name), patch.object(
                self.verifier.tooling_base,
                "assert_workspace",
                return_value={"masters": masters},
            ) as assert_workspace, patch.object(
                self.verifier.tooling_base,
                "command",
                return_value=command_result,
            ) as command, patch.object(
                self.verifier.tooling_revision,
                "dedicated_part_context",
                return_value=part_context,
            ):
                with self.assertRaises(RuntimeError):
                    self.verifier._create_disposable_execution_context(
                        administrator,
                        "http://127.0.0.1:8003",
                        "csrf",
                        retained,
                    )
                command.assert_called_once()
                self.assertEqual(
                    assert_workspace.call_args.kwargs,
                    {
                        "expected_revision_mode": (
                            self.verifier.tooling_base.ExpectedToolingRevisionCapabilityMode.AVAILABLE
                        )
                    },
                )

        with patch.object(
            self.verifier.tooling_base,
            "command",
            side_effect=(command_result,) * 4,
        ) as base_command, patch.object(
            self.verifier.tooling_base,
            "assert_workspace",
            side_effect=(
                {"masters": [master]},
                {"requirements": [requirement]},
                {"applicability": [applicability]},
            ),
        ) as assert_workspace, patch.object(
            self.verifier.tooling_revision,
            "dedicated_part_context",
            return_value=part_context,
        ) as dedicated_part_context, patch.object(
            self.verifier.tooling_revision,
            "project_context",
            return_value=(project_id, retained_master_id, "part", (), retained_set_id, {"type": "customer", "sourceSystem": "ERPNEXT", "sourceObjectId": "SYNTHETIC"}),
        ), patch.object(
            self.verifier.tooling_revision,
            "command",
            side_effect=(command_result, binding_result),
        ), patch.object(
            self.verifier.tooling_revision,
            "assert_revision_item",
            return_value=revision,
        ), patch.object(
            self.verifier.tooling_revision,
            "assert_set_binding",
        ), patch.object(
            self.verifier.tooling_base,
            "assert_tooling_set_collection",
            return_value={"items": [tooling_set]},
        ), patch.object(
            self.verifier.tooling_runtime,
            "command",
            return_value=types.SimpleNamespace(
                body={"acceptanceEvidence": acceptance}
            ),
        ), patch.object(
            self.verifier.tooling_runtime,
            "assert_acceptance_revision",
            return_value=acceptance,
        ):
            disposable, observed_acceptance = (
                self.verifier._create_disposable_execution_context(
                    administrator,
                    "http://127.0.0.1:8003",
                    "csrf",
                    retained,
                )
            )
        self.assertEqual(base_command.call_count, 4)
        dedicated_part_context.assert_called_once_with(
            administrator,
            "http://127.0.0.1:8003",
            project_id,
        )
        requirement_payload = base_command.call_args_list[1].args[4]
        applicability_payload = base_command.call_args_list[2].args[4]
        self.assertEqual(
            requirement_payload["targetPartRevisionGlobalId"],
            part_revision_id,
        )
        self.assertEqual(
            applicability_payload["partRevisionGlobalId"],
            part_revision_id,
        )
        self.assertNotEqual(part_revision_id, retained_tooling_revision_id)
        self.assertEqual(
            disposable["engineeringRevisionId"],
            retained_tooling_revision_id,
        )
        self.assertEqual(assert_workspace.call_count, 3)
        expected_revision_mode = (
            self.verifier.tooling_base.ExpectedToolingRevisionCapabilityMode.AVAILABLE
        )
        for call in assert_workspace.call_args_list:
            self.assertEqual(
                call.kwargs,
                {"expected_revision_mode": expected_revision_mode},
            )
        self.assertEqual(disposable["projectId"], project_id)
        self.assertNotEqual(disposable["masterId"], retained_master_id)
        self.assertNotEqual(disposable["toolingSetId"], retained_set_id)
        self.assertEqual(disposable["requirementKind"], "customer_owned_intake")
        self.assertEqual(observed_acceptance, acceptance)

    def test_execution_state_snapshot_is_count_only_and_profile_is_exact(self):
        frappe = sys.modules["frappe"]
        calls: list[str] = []
        frappe.db = types.SimpleNamespace(
            count=lambda doctype: calls.append(doctype) or len(calls)
        )
        snapshot = self.verifier.execution_state_snapshot(
            self.verifier.FIXTURE_RUN_ID
        )
        self.assertEqual(tuple(snapshot), self.verifier._EXECUTION_STATE_DOCTYPES)
        self.assertEqual(calls, list(self.verifier._EXECUTION_STATE_DOCTYPES))
        self.assertTrue(all(type(value) is int for value in snapshot.values()))
        with self.assertRaisesRegex(
            RuntimeError,
            "^P8-05 execution snapshot fixture identity drifted$",
        ):
            self.verifier.execution_state_snapshot("wrong")

        environment = {
            "NPI_TOOL_ASSET_RUNTIME_MARKER": self.verifier.RUNTIME_MARKER,
            "NPI_TOOL_ASSET_REQUESTER_USER": self.verifier.ACTOR_USER,
            "NPI_TOOL_ASSET_WORKER_USER": "worker@example.invalid",
        }
        with patch.dict(os.environ, environment, clear=True):
            actual = self.fixture.resolve_profile(
                self.verifier.document_runtime.TENANT_ID,
                str(UUID(int=1)),
            )
            expected = self.verifier._expected_synthetic_profile(str(UUID(int=1)))
        self.assertIsNotNone(actual)
        self.assertEqual(actual.reference.canonical_mapping(), expected)

    def test_collection_contract_rejects_identity_items_profile_and_context_drift(self):
        project_id = str(UUID(int=1))
        master_id = str(UUID(int=2))
        set_id = str(UUID(int=3))
        environment = {
            "NPI_TOOL_ASSET_REQUESTER_USER": self.verifier.ACTOR_USER,
            "NPI_TOOL_ASSET_WORKER_USER": "worker@example.invalid",
        }
        with patch.dict(os.environ, environment, clear=True):
            profile = self.verifier._expected_synthetic_profile(project_id)
            base = {
                "projectGlobalId": project_id,
                "toolingMasterGlobalId": master_id,
                "toolingSetGlobalId": set_id,
                "items": [],
                "executionProfile": profile,
                "commandContexts": None,
            }
            self.verifier._assert_collection(
                types.SimpleNamespace(status=200, body=base),
                project_id=project_id,
                master_id=master_id,
                set_id=set_id,
                command_contexts=None,
            )
            invalid = (
                (503, base),
                (200, {**base, "projectGlobalId": str(UUID(int=4))}),
                (200, {**base, "items": [{}]}),
                (200, {**base, "executionProfile": {**profile, "targetMode": "sandbox"}}),
                (200, {**base, "commandContexts": {"create_tool_asset": {}}}),
            )
            for status, body in invalid:
                with self.subTest(status=status, keys=tuple(body)), self.assertRaisesRegex(
                    RuntimeError,
                    "^P8-05 disposable command context is unavailable$",
                ):
                    self.verifier._assert_collection(
                        types.SimpleNamespace(status=status, body=body),
                        project_id=project_id,
                        master_id=master_id,
                        set_id=set_id,
                        command_contexts=None,
                    )

    def test_retained_query_snapshot_drift_stops_before_disposable_fixture(self):
        project_id = str(UUID(int=1))
        retained = {
            "projectId": project_id,
            "masterId": str(UUID(int=2)),
            "toolingSetId": str(UUID(int=3)),
        }
        acceptance = {"globalId": str(UUID(int=4))}
        environment = {
            "NPI_TOOL_ASSET_RUNTIME_PROJECT_ID": project_id,
            "NPI_TOOL_ASSET_REQUESTER_USER": self.verifier.ACTOR_USER,
            "NPI_TOOL_ASSET_WORKER_USER": "worker@example.invalid",
        }
        with patch.dict(os.environ, environment, clear=True):
            body = {
                "projectGlobalId": project_id,
                "toolingMasterGlobalId": retained["masterId"],
                "toolingSetGlobalId": retained["toolingSetId"],
                "items": [],
                "executionProfile": self.verifier._expected_synthetic_profile(
                    project_id
                ),
                "commandContexts": None,
            }
            with patch.object(
                self.verifier,
                "secret_from_environment",
                return_value="administrator-password",
            ), patch.object(
                self.verifier,
                "login",
                return_value=object(),
            ), patch.object(
                self.verifier,
                "bootstrap_csrf",
                return_value="csrf",
            ), patch.object(
                self.verifier,
                "_retained_context",
                return_value=(retained, acceptance),
            ), patch.object(
                self.verifier,
                "_execution_state_snapshot",
                side_effect=(
                    {"NPI Tool Asset Request": 0},
                    {"NPI Tool Asset Request": 1},
                ),
            ), patch.object(
                self.verifier,
                "execution_request",
                return_value=types.SimpleNamespace(status=200, body=body),
            ) as request, patch.object(
                self.verifier,
                "_create_disposable_execution_context",
            ) as create_fixture:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "^P8-05 retained mapped collection query changed execution truth$",
                ):
                    self.verifier.run_fresh(
                        "http://127.0.0.1:8003",
                        "fixture-password",
                    )
                request.assert_called_once()
                create_fixture.assert_not_called()

    def test_command_context_diagnostic_is_ordered_trace_bound_and_value_free(self):
        self.assertFalse(self.verifier.TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED)
        self.assertFalse(
            self.verifier.POST_QUERY_TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED
        )
        activation = patch.object(
            self.verifier,
            "POST_QUERY_TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED",
            True,
        )
        activation.start()
        self.addCleanup(activation.stop)
        trace_id = "trace-" + "a" * 32
        secret = "private-command-context-value"
        create = {"opaque": secret}
        valid = {
            "items": [],
            "commandContexts": {"create_tool_asset": create},
            "executionProfile": {"targetMode": "synthetic"},
        }
        cases = (
            (
                "P805_TOOL_ASSET_CONTEXT_HTTP_SERVER_CLASS",
                types.SimpleNamespace(status=503, body=valid, trace_id=trace_id),
            ),
            (
                "P805_TOOL_ASSET_CONTEXT_ITEMS",
                types.SimpleNamespace(
                    status=200,
                    body={**valid, "items": [{"opaque": secret}]},
                    trace_id=trace_id,
                ),
            ),
            (
                "P805_TOOL_ASSET_CONTEXT_CREATE_SHAPE",
                types.SimpleNamespace(
                    status=200,
                    body={**valid, "commandContexts": None},
                    trace_id=trace_id,
                ),
            ),
            (
                "P805_TOOL_ASSET_CONTEXT_TARGET_MODE",
                types.SimpleNamespace(
                    status=200,
                    body={
                        **valid,
                        "executionProfile": {"targetMode": secret},
                    },
                    trace_id=trace_id,
                ),
            ),
        )
        for code, result in cases:
            with self.subTest(code=code), patch.object(
                self.verifier.item_runtime,
                "_sanitized_server_log_diagnostic",
                return_value=None,
            ) as reader:
                message = self.verifier._command_context_failure_message(
                    result,
                    {"logs/bench.log": 0},
                )
                self.assertIn(f"diagnostic_code={code}", message)
                self.assertIn("exception_type=RuntimeError", message)
                self.assertIn(f"trace_id={trace_id}", message)
                self.assertNotIn(secret, message)
                self.assertEqual(
                    reader.call_count,
                    int(
                        code
                        == "P805_TOOL_ASSET_CONTEXT_CREATE_SHAPE"
                        or code.startswith("P805_TOOL_ASSET_CONTEXT_HTTP_")
                    ),
                )

        status = cases[0][1]
        create_shape = cases[2][1]
        server_tuple = (
            "ToolAssetExecutionStateConflict",
            "P805_TOOL_ASSET_CONTEXT_CREATE_MAPPING",
            trace_id,
        )
        for result in (status, create_shape):
            with self.subTest(server_result=result.status), patch.object(
                self.verifier.item_runtime,
                "_sanitized_server_log_diagnostic",
                return_value=server_tuple,
            ) as reader:
                message = self.verifier._command_context_failure_message(
                    result,
                    {"logs/bench.log": 0},
                )
            self.assertIn(
                "diagnostic_code=P805_TOOL_ASSET_CONTEXT_CREATE_MAPPING",
                message,
            )
            self.assertIn(
                "exception_type=ToolAssetExecutionStateConflict",
                message,
            )
            self.assertNotIn(secret, message)
            self.assertEqual(
                reader.call_args.kwargs,
                {
                    "code_prefix": "P805_TOOL_ASSET_CONTEXT_",
                    "allowed_codes": (
                        self.verifier._TOOL_ASSET_CONTEXT_SERVER_CODES
                    ),
                },
            )

        for invalid_trace in (None, "trace-invalid", secret):
            for invalid_status in (200, 503):
                with self.subTest(
                    trace=invalid_trace,
                    status=invalid_status,
                ), patch.object(
                    self.verifier.item_runtime,
                    "_sanitized_server_log_diagnostic",
                ) as reader:
                    invalid = types.SimpleNamespace(
                        status=invalid_status,
                        body={**valid, "commandContexts": None},
                        trace_id=invalid_trace,
                    )
                    self.assertEqual(
                        self.verifier._command_context_failure_message(
                            invalid,
                            {},
                        ),
                        self.verifier._TOOL_ASSET_CONTEXT_FAILURE,
                    )
                    reader.assert_not_called()

        success = types.SimpleNamespace(status=200, body=valid, trace_id=trace_id)
        with patch.object(
            self.verifier.item_runtime,
            "_sanitized_server_log_diagnostic",
        ) as reader:
            self.assertIsNone(
                self.verifier._command_context_failure_message(success, {})
            )
            reader.assert_not_called()

    def test_server_reader_allowlist_exactly_matches_unique_lexical_contexts(self):
        diagnostics = importlib.import_module(
            "npi_integration.tool_asset_request.diagnostics"
        )
        self.assertEqual(
            self.verifier._TOOL_ASSET_CONTEXT_SERVER_CODES,
            diagnostics.TOOL_ASSET_CONTEXT_DIAGNOSTIC_CODES,
        )
        self.assertEqual(len(self.verifier._TOOL_ASSET_CONTEXT_SERVER_CODES), 31)
        source = "\n".join(
            (
                (
                    ROOT
                    / "apps/npi_integration/npi_integration/tool_asset_request_api.py"
                ).read_text(encoding="utf-8"),
                (
                    ROOT
                    / "apps/npi_integration/npi_integration/tool_asset_request/frappe_repository.py"
                ).read_text(encoding="utf-8"),
            )
        )
        for code in self.verifier._TOOL_ASSET_CONTEXT_SERVER_CODES:
            with self.subTest(code=code):
                self.assertEqual(source.count(f'"{code}"'), 1)

    def test_http_failure_classes_are_closed_value_free_and_always_read_server_log(self):
        self.assertFalse(self.verifier.TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED)
        self.assertFalse(
            self.verifier.POST_QUERY_TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED
        )
        activation = patch.object(
            self.verifier,
            "POST_QUERY_TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED",
            True,
        )
        activation.start()
        self.addCleanup(activation.stop)
        trace_id = "trace-" + "c" * 32
        secret = "private-http-status-value"
        cases = (
            (401, "P805_TOOL_ASSET_CONTEXT_HTTP_AUTHORIZATION_CLASS"),
            (403, "P805_TOOL_ASSET_CONTEXT_HTTP_AUTHORIZATION_CLASS"),
            (404, "P805_TOOL_ASSET_CONTEXT_HTTP_NOT_FOUND_CLASS"),
            (409, "P805_TOOL_ASSET_CONTEXT_HTTP_CLIENT_CLASS"),
            (503, "P805_TOOL_ASSET_CONTEXT_HTTP_SERVER_CLASS"),
            (302, "P805_TOOL_ASSET_CONTEXT_HTTP_OTHER_CLASS"),
            (700, "P805_TOOL_ASSET_CONTEXT_HTTP_OTHER_CLASS"),
        )
        for status, code in cases:
            result = types.SimpleNamespace(
                status=status,
                body={"opaque": secret},
                trace_id=trace_id,
            )
            with self.subTest(code=code), patch.object(
                self.verifier.item_runtime,
                "_sanitized_server_log_diagnostic",
                return_value=None,
            ) as reader:
                message = self.verifier._command_context_failure_message(
                    result,
                    {"logs/bench.log": 0},
                )
            self.assertIn(f"diagnostic_code={code}", message)
            self.assertIn("exception_type=RuntimeError", message)
            self.assertIn(f"trace_id={trace_id}", message)
            self.assertNotIn(secret, message)
            self.assertNotIn(str(status), message)
            reader.assert_called_once_with(
                trace_id,
                {"logs/bench.log": 0},
                code_prefix="P805_TOOL_ASSET_CONTEXT_",
                allowed_codes=self.verifier._TOOL_ASSET_CONTEXT_SERVER_CODES,
            )

        server_tuple = (
            "PermissionDenied",
            "P805_TOOL_ASSET_CONTEXT_PROJECT_AUTHORIZE",
            trace_id,
        )
        with patch.object(
            self.verifier.item_runtime,
            "_sanitized_server_log_diagnostic",
            return_value=server_tuple,
        ):
            message = self.verifier._command_context_failure_message(
                types.SimpleNamespace(status=403, body={}, trace_id=trace_id),
                {},
            )
        self.assertIn(
            "diagnostic_code=P805_TOOL_ASSET_CONTEXT_PROJECT_AUTHORIZE",
            message,
        )
        self.assertIn("exception_type=PermissionDenied", message)

        status_result = types.SimpleNamespace(
            status=503,
            body={"opaque": secret},
            trace_id=trace_id,
        )
        create_shape_result = types.SimpleNamespace(
            status=200,
            body={
                "items": [],
                "commandContexts": None,
                "executionProfile": {"targetMode": "synthetic"},
            },
            trace_id=trace_id,
        )

        with patch.object(
            self.verifier,
            "POST_QUERY_TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier.item_runtime,
            "_sanitized_server_log_diagnostic",
        ) as reader:
            self.assertEqual(
                self.verifier._command_context_failure_message(
                    status_result,
                    {"logs/bench.log": 0},
                ),
                self.verifier._TOOL_ASSET_CONTEXT_FAILURE,
            )
            reader.assert_not_called()

        with patch.object(
            self.verifier,
            "TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED",
            True,
        ), patch.object(
            self.verifier.item_runtime,
            "_sanitized_server_log_diagnostic",
        ) as reader:
            self.assertFalse(
                self.verifier._post_query_command_context_diagnostics_enabled()
            )
            self.assertEqual(
                self.verifier._command_context_failure_message(
                    status_result,
                    {"logs/bench.log": 0},
                ),
                self.verifier._TOOL_ASSET_CONTEXT_FAILURE,
            )
            reader.assert_not_called()

        with patch.object(
            self.verifier,
            "POST_QUERY_TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier.item_runtime,
            "_sanitized_server_log_diagnostic",
        ) as reader:
            self.assertEqual(
                self.verifier._command_context_failure_message(
                    create_shape_result,
                    {"logs/bench.log": 0},
                ),
                self.verifier._TOOL_ASSET_CONTEXT_FAILURE,
            )
            reader.assert_not_called()

    def test_enabled_request_adds_only_exact_diagnostic_scope_header(self):
        response = types.SimpleNamespace(
            status=200,
            body={},
            headers={
                "X-Request-ID": "p805-enabled",
                "Cache-Control": "private, no-store",
            },
        )
        with patch.object(
            self.verifier.document_runtime,
            "query_headers",
            return_value={"X-Request-ID": "p805-enabled"},
        ), patch.object(
            self.verifier.document_runtime,
            "request",
            return_value=response,
        ) as request:
            self.verifier.execution_request(
                object(),
                "http://127.0.0.1:8003",
                "/api/npi/v1/projects/fixed/tooling/fixed/sets/fixed/asset-execution-requests?acceptanceRevisionGlobalId=fixed",
                method="GET",
                query_key="enabled",
                diagnostic_scope=(
                    self.verifier._TOOL_ASSET_CONTEXT_DIAGNOSTIC_SCOPE
                ),
            )
        headers = request.call_args.kwargs["request_headers"]
        self.assertEqual(
            headers,
            {
                "X-Request-ID": "p805-enabled",
                "X-NPI-Diagnostic-Scope": "p805-tool-asset-command-context-v1",
            },
        )

        invalid_requests = (
            {
                "path": "/api/npi/v1/projects/fixed/asset-execution-requests?acceptanceRevisionGlobalId=fixed",
                "method": "GET",
                "query_key": "enabled",
            },
            {
                "path": "/api/npi/v1/projects/fixed/tooling/fixed/sets/fixed/asset-execution-requests?acceptanceRevisionGlobalId=fixed",
                "method": "POST",
                "query_key": "enabled",
            },
            {
                "path": "/api/npi/v1/projects/fixed/tooling/fixed/sets/fixed/asset-execution-requests?acceptanceRevisionGlobalId=fixed&extra=wrong",
                "method": "GET",
                "query_key": "enabled",
            },
            {
                "path": "/api/npi/v1/projects/fixed/tooling/fixed/sets/fixed/asset-execution-requests?acceptanceRevisionGlobalId=fixed",
                "method": "GET",
                "query_key": "wrong",
            },
        )
        for request_values in invalid_requests:
            with self.subTest(request_values=request_values):
                with self.assertRaisesRegex(
                    RuntimeError,
                    self.verifier._TOOL_ASSET_CONTEXT_FAILURE,
                ):
                    self.verifier.execution_request(
                        object(),
                        "http://127.0.0.1:8003",
                        diagnostic_scope=(
                            self.verifier._TOOL_ASSET_CONTEXT_DIAGNOSTIC_SCOPE
                        ),
                        **request_values,
                    )

    def test_runtime_profile_preserves_exact_requester_and_service_actor(self):
        environment = {
            "NPI_TOOL_ASSET_RUNTIME_MARKER": "npi-one-tool-asset-disposable-v1",
            "NPI_TOOL_ASSET_REQUESTER_USER": self.verifier.ACTOR_USER,
            "NPI_TOOL_ASSET_WORKER_USER": "npi-inbound-worker@example.invalid",
        }
        with patch.dict(os.environ, environment, clear=True):
            profile = self.fixture.resolve_profile("tenant-a", str(UUID(int=1)))
        self.assertIsNotNone(profile)
        self.assertEqual(profile.requester_user_ids, (self.verifier.ACTOR_USER,))
        self.assertEqual(
            profile.service_actor_user_id,
            "npi-inbound-worker@example.invalid",
        )

    def test_synthetic_adapter_preserves_operation_and_returns_no_formal_identity(self):
        from tests.test_phase8_tool_asset_adapters import command
        with patch.dict(os.environ, self.environment, clear=True):
            response = self.fixture.synthetic_adapter(command())
        self.assertIsNone(response.formal_asset_id)
        self.assertIsNone(response.target_version)

    def test_runtime_covers_default_off_create_worker_replay_and_zero_mapping(self):
        source = (ROOT / "scripts/verify_tool_asset_execution_runtime.py").read_text(encoding="utf-8")
        for marker in ("run_disabled_probe", "commandContexts", 'request.get("state") != "queued"', "exercise_worker", "terminalReplayNotClaimed", "mappingHeadCount", "fieldResultCount", "_assert_no_formal_target"):
            self.assertIn(marker, source)
        self.assertIn("stderr=subprocess.DEVNULL", source)
        self.assertIn("tempfile.TemporaryFile", source)
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("P5 controlled runtime through P8-05 Tool Asset command and Outbox worker", workflow)
        self.assertIn("printf 'scope=p5-01-through-p8-05\\n'", workflow)
        self.assertIn("printf 'predecessor_scope=p5-01-through-p8-04\\n'", workflow)
        self.assertIn("tests/e2e/p8-05-tool-asset-execution-live.spec.ts", workflow)
        self.assertIn(
            "frontend/tests/e2e/p8-05-tool-asset-execution-live.spec.ts-snapshots/p8-05-*-linux.png",
            workflow,
        )

    def test_disabled_probe_runs_after_retained_p6_export_fixture(self):
        shell = (ROOT / "scripts/verify-frappe-runtime.sh").read_text(encoding="utf-8")
        self.assertLess(
            shell.index("run_tooling_import_runtime_verifier replay-only"),
            shell.index("run_tool_asset_runtime_verifier disabled"),
        )
        self.assertLess(
            shell.index("run_tooling_export_runtime_verifier replay-only"),
            shell.index("run_tool_asset_runtime_verifier disabled"),
        )
        revision = (ROOT / "scripts/verify_tooling_revision_runtime.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("exact_retained_master", revision)
        self.assertIn("exact_retained_part", revision)
        self.assertIn("originatingProjectGlobalId", revision)
        retained_part_source = revision[
            revision.index("def exact_retained_part(") : revision.index("\ndef command(")
        ]
        self.assertNotIn("originatingProjectGlobalId", retained_part_source)
        project_context_source = revision[
            revision.index("def project_context(") : revision.index("\ndef dedicated_part_context(")
        ]
        self.assertLess(
            project_context_source.index("exact_retained_master("),
            project_context_source.index("exact_retained_part("),
        )
        self.assertIn(
            'workspace.body.get("applicability")',
            project_context_source,
        )

    def test_retained_context_explicitly_requires_available_erp_projection(self):
        retained = ({"projectId": str(UUID(int=1))}, object(), object(), object())
        with patch.object(
            self.verifier.tooling_runtime,
            "replay_context",
            return_value=retained,
        ) as replay:
            context, second = self.verifier._retained_context(
                object(),
                "http://127.0.0.1:8003",
            )
        self.assertIs(context, retained[0])
        self.assertIs(second, retained[2])
        self.assertEqual(
            replay.call_args.kwargs,
            {
                "expected_erp_projection_mode": (
                    self.verifier.tooling_runtime.ExpectedErpProjectionMode.AVAILABLE
                ),
                "expected_asset_projection_mode": (
                    self.verifier.tooling_runtime.ExpectedAssetProjectionMode.AVAILABLE
                ),
            },
        )

    def test_projection_mode_is_explicitly_forwarded_through_p6_chain(self):
        manufacturing = (
            ROOT / "scripts" / "verify_tooling_manufacturing_runtime.py"
        ).read_text(encoding="utf-8")
        engineering = (
            ROOT / "scripts" / "verify_tooling_engineering_controls_runtime.py"
        ).read_text(encoding="utf-8")
        acceptance = (
            ROOT / "scripts" / "verify_tooling_acceptance_runtime.py"
        ).read_text(encoding="utf-8")
        tool_asset = (
            ROOT / "scripts" / "verify_tool_asset_execution_runtime.py"
        ).read_text(encoding="utf-8")
        for source in (manufacturing, engineering, acceptance):
            with self.subTest(source=source[:40]):
                self.assertIn("ExpectedErpProjectionMode.UNAVAILABLE", source)
                self.assertIn(
                    "expected_erp_projection_mode=expected_erp_projection_mode",
                    source,
                )
        self.assertIn("ExpectedErpProjectionMode.AVAILABLE", tool_asset)
        self.assertIn("ExpectedAssetProjectionMode.AVAILABLE", tool_asset)
        self.assertIn("ExpectedAssetProjectionMode.UNAVAILABLE", acceptance)
        self.assertEqual(
            sum(
                source.count("ExpectedErpProjectionMode.AVAILABLE")
                for source in (manufacturing, engineering, acceptance, tool_asset)
            ),
            1,
        )
        self.assertEqual(tool_asset.count("ExpectedAssetProjectionMode.AVAILABLE"), 1)
        self.assertNotIn("ExpectedAssetProjectionMode.AVAILABLE", manufacturing)
        self.assertNotIn("ExpectedAssetProjectionMode.AVAILABLE", engineering)

    def test_disposable_fixture_explicitly_uses_available_revision_capability(self):
        tooling = (
            ROOT / "scripts" / "verify_tooling_runtime.py"
        ).read_text(encoding="utf-8")
        tool_asset = (
            ROOT / "scripts" / "verify_tool_asset_execution_runtime.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "ExpectedToolingRevisionCapabilityMode.UNAVAILABLE",
            tooling,
        )
        self.assertEqual(
            tool_asset.count(
                "ExpectedToolingRevisionCapabilityMode.AVAILABLE"
            ),
            3,
        )
        self.assertEqual(
            tool_asset.count("expected_revision_mode="),
            3,
        )

    def test_p8_01_replay_precedes_dual_available_p8_05_retained_probe(self):
        shell = (ROOT / "scripts" / "verify-frappe-runtime.sh").read_text(
            encoding="utf-8"
        )
        self.assertLess(
            shell.index("run_projection_runtime_verifier replay-only"),
            shell.index("run_tool_asset_runtime_verifier disabled"),
        )
        retained_source = (
            ROOT / "scripts/verify_tool_asset_execution_runtime.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(retained_source.count("ExpectedErpProjectionMode.AVAILABLE"), 1)
        self.assertEqual(retained_source.count("ExpectedAssetProjectionMode.AVAILABLE"), 1)


if __name__ == "__main__":
    unittest.main()
