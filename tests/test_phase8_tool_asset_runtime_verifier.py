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
            "execution_request",
            side_effect=CommandBoundaryReached,
        ) as request:
            with self.assertRaises(CommandBoundaryReached):
                self.verifier.run_fresh(
                    "http://127.0.0.1:8003", "fixture-password"
                )
            request.assert_called_once()

    def test_enabled_collection_binds_exact_acceptance_query_and_strict_context(self):
        project_id = str(UUID(int=1))
        master_id = str(UUID(int=2))
        set_id = str(UUID(int=3))
        acceptance_id = str(UUID(int=4))
        context = {
            "projectId": project_id,
            "masterId": master_id,
            "toolingSetId": set_id,
        }
        acceptance = {"globalId": acceptance_id}
        source = {"acceptanceRevisionGlobalId": acceptance_id}
        create = {
            "source": source,
            "expectedSourceHash": "a" * 64,
            "expectedApprovalHash": "b" * 64,
            "expectedMappingExpectationHash": "c" * 64,
            "expectedProfileSnapshotHash": "d" * 64,
        }
        valid_body = {
            "items": [],
            "commandContexts": {"create_tool_asset": create},
            "executionProfile": {"targetMode": "synthetic"},
        }
        valid_environment = {
            "NPI_TOOL_ASSET_RUNTIME_PROJECT_ID": project_id,
            "NPI_TOOL_ASSET_REQUESTER_USER": self.verifier.ACTOR_USER,
            "NPI_TOOL_ASSET_WORKER_USER": "npi-inbound-worker@example.invalid",
        }
        invalid_responses = {
            "status": types.SimpleNamespace(
                status=503,
                body=valid_body,
                trace_id=None,
            ),
            "items": types.SimpleNamespace(
                status=200,
                body={**valid_body, "items": [{}]},
                trace_id=None,
            ),
            "create-context": types.SimpleNamespace(
                status=200,
                body={**valid_body, "commandContexts": None},
                trace_id=None,
            ),
            "target-profile": types.SimpleNamespace(
                status=200,
                body={
                    **valid_body,
                    "executionProfile": {"targetMode": "sandbox"},
                },
                trace_id=None,
            ),
        }

        def assert_exact_collection_call(request) -> None:
            self.assertEqual(request.call_count, 1)
            args, kwargs = request.call_args
            self.assertEqual(args[:2], (object_actor, "http://127.0.0.1:8003"))
            split = urlsplit(args[2])
            self.assertEqual(
                split.path,
                self.verifier.execution_path(project_id, master_id, set_id),
            )
            self.assertEqual(
                parse_qsl(split.query, keep_blank_values=True),
                [("acceptanceRevisionGlobalId", acceptance_id)],
            )
            self.assertEqual(
                kwargs,
                {
                    "method": "GET",
                    "query_key": "enabled",
                    "diagnostic_scope": (
                        self.verifier._TOOL_ASSET_CONTEXT_DIAGNOSTIC_SCOPE
                    ),
                },
            )

        object_actor = object()
        for name, response in invalid_responses.items():
            with self.subTest(name=name), patch.dict(
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
                return_value=(context, acceptance),
            ), patch.object(
                self.verifier, "execution_request", return_value=response
            ) as request:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "^P8-05 disposable command context is unavailable$",
                ):
                    self.verifier.run_fresh(
                        "http://127.0.0.1:8003", "fixture-password"
                    )
                assert_exact_collection_call(request)

        class PostReached(Exception):
            pass

        listed = types.SimpleNamespace(status=200, body=valid_body)
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
            return_value=(context, acceptance),
        ), patch.object(
            self.verifier,
            "execution_request",
            side_effect=(listed, PostReached),
        ) as request:
            with self.assertRaises(PostReached):
                self.verifier.run_fresh(
                    "http://127.0.0.1:8003", "fixture-password"
                )
            first_args, first_kwargs = request.call_args_list[0]
            split = urlsplit(first_args[2])
            self.assertEqual(
                split.path,
                self.verifier.execution_path(project_id, master_id, set_id),
            )
            self.assertEqual(
                parse_qsl(split.query, keep_blank_values=True),
                [("acceptanceRevisionGlobalId", acceptance_id)],
            )
            self.assertEqual(
                first_kwargs,
                {
                    "method": "GET",
                    "query_key": "enabled",
                    "diagnostic_scope": (
                        self.verifier._TOOL_ASSET_CONTEXT_DIAGNOSTIC_SCOPE
                    ),
                },
            )
            self.assertEqual(request.call_count, 2)
            post_args, post_kwargs = request.call_args_list[1]
            self.assertEqual(
                post_args[2],
                self.verifier.execution_path(project_id, master_id, set_id, ":create"),
            )
            self.assertEqual(post_kwargs["method"], "POST")

    def test_command_context_diagnostic_is_ordered_trace_bound_and_value_free(self):
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
                "P805_TOOL_ASSET_CONTEXT_STATUS",
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
                    int(code == "P805_TOOL_ASSET_CONTEXT_CREATE_SHAPE"),
                )

        create_shape = cases[2][1]
        server_tuple = (
            "ToolAssetExecutionStateConflict",
            "P805_TOOL_ASSET_CONTEXT_CREATE_MAPPING",
            trace_id,
        )
        with patch.object(
            self.verifier.item_runtime,
            "_sanitized_server_log_diagnostic",
            return_value=server_tuple,
        ) as reader:
            message = self.verifier._command_context_failure_message(
                create_shape,
                {"logs/bench.log": 0},
            )
        self.assertIn("diagnostic_code=P805_TOOL_ASSET_CONTEXT_CREATE_MAPPING", message)
        self.assertIn("exception_type=ToolAssetExecutionStateConflict", message)
        self.assertNotIn(secret, message)
        self.assertEqual(
            reader.call_args.kwargs,
            {
                "code_prefix": "P805_TOOL_ASSET_CONTEXT_",
                "allowed_codes": self.verifier._TOOL_ASSET_CONTEXT_SERVER_CODES,
            },
        )

        for invalid_trace in (None, "trace-invalid", secret):
            with self.subTest(trace=invalid_trace), patch.object(
                self.verifier.item_runtime,
                "_sanitized_server_log_diagnostic",
            ) as reader:
                invalid = types.SimpleNamespace(
                    status=200,
                    body={**valid, "commandContexts": None},
                    trace_id=invalid_trace,
                )
                self.assertEqual(
                    self.verifier._command_context_failure_message(invalid, {}),
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

        with patch.object(
            self.verifier,
            "TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier.item_runtime,
            "_sanitized_server_log_diagnostic",
        ) as reader:
            self.assertEqual(
                self.verifier._command_context_failure_message(
                    create_shape,
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
        for marker in ("run_disabled_probe", "commandContexts", '"state") == "queued"', "exercise_worker", "terminalReplayNotClaimed", "mappingHeadCount", "fieldResultCount", "_assert_no_formal_target"):
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
