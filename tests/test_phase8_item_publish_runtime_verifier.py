from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_item_publish_runtime.py"
SHELL = ROOT / "scripts" / "verify-frappe-runtime.sh"
FIXTURE = (
    ROOT
    / "apps"
    / "npi_integration"
    / "npi_integration"
    / "item_publish"
    / "runtime_fixture.py"
)


_LEGACY_SQL_FUNCTIONS = {"seed_legacy", "inspect_legacy", "cleanup_legacy"}
_LEGACY_TABLES = {
    "NPI Item Publish Request",
    "NPI Outbox Message",
    "NPI Item Publish Stream Guard",
    "NPI Item Publish Result",
}
_LEGACY_NEW_COLUMNS = {
    "service_actor_user_id",
    "target_idempotency_key_hash",
    "semantic_source_effect_hash",
    "semantic_effect_hash",
}
_TRACE_ID = "trace-0123456789abcdef0123456789abcdef"
_FIXTURE_RUN_ID = "0123456789abcdef0123456789abcdef"


def load_verifier():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    saved = {
        name: sys.modules.pop(name, None)
        for name in (
            "verify_document_runtime",
            "verify_ebom_runtime",
            "verify_publish_request_runtime",
            "verify_item_publish_runtime_contract",
        )
    }
    spec = importlib.util.spec_from_file_location(
        "verify_item_publish_runtime_contract",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Item publish runtime verifier cannot be imported")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        with patch.dict(
            os.environ,
            {"NPI_DOCUMENT_RUNTIME_RUN_ID": _FIXTURE_RUN_ID},
            clear=False,
        ):
            spec.loader.exec_module(module)
    finally:
        for name in tuple(saved):
            sys.modules.pop(name, None)
        for name, value in saved.items():
            if value is not None:
                sys.modules[name] = value
    return module


def _is_frappe_db_sql(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "sql"
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "db"
        and isinstance(node.func.value.value, ast.Name)
        and node.func.value.value.id == "frappe"
    )


def _sql_literals(node: ast.AST) -> str:
    return " ".join(
        str(value.value)
        for value in ast.walk(node)
        if isinstance(value, ast.Constant) and isinstance(value.value, str)
    )


def _function_nodes(tree: ast.AST) -> dict[str, ast.FunctionDef]:
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def _legacy_sql_contract_violations(source: str) -> list[str]:
    tree = ast.parse(source)
    functions = _function_nodes(tree)
    violations: list[str] = []
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    for node in ast.walk(tree):
        if not _is_frappe_db_sql(node):
            continue
        current: ast.AST | None = node
        owner = None
        while current is not None:
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                owner = current.name
                break
            current = parents.get(current)
        if owner not in _LEGACY_SQL_FUNCTIONS:
            violations.append(f"SQL escaped the legacy fixture allowlist: {owner}")
    for name in _LEGACY_SQL_FUNCTIONS:
        function = functions.get(name)
        if function is None:
            violations.append(f"missing {name}")
            continue
        calls = [node for node in ast.walk(function) if _is_frappe_db_sql(node)]
        guard_lines = [
            node.lineno
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_require_disposable_legacy_fixture"
        ]
        if not guard_lines or not calls or min(guard_lines) >= min(node.lineno for node in calls):
            violations.append(f"{name} has no first SQL identity guard")
        for call in calls:
            text = _sql_literals(call.args[0]) if call.args else ""
            tables = set(re.findall(r"tab([A-Za-z0-9 ]+)", text))
            if tables - _LEGACY_TABLES:
                violations.append(f"{name} touches an unapproved table")
            if "SELECT * FROM" in text:
                violations.append(f"{name} copies a row with SELECT *")
            if "UPDATE `tabNPI Outbox Message`" in text:
                violations.append(f"{name} updates an Outbox copy")
            if "DELETE FROM" in text and (
                "WHERE" not in text or "project_global_id" not in text
            ):
                violations.append(f"{name} has an unbounded delete")
            if "INSERT INTO `tabNPI Item Publish Request`" in text:
                if len(call.args) < 2 or not (
                    isinstance(call.args[1], ast.Name)
                    and call.args[1].id == "legacy_request_values"
                ):
                    violations.append(f"{name} Request INSERT args drifted")
            if "INSERT INTO `tabNPI Outbox Message`" in text:
                if len(call.args) < 2 or not (
                    isinstance(call.args[1], ast.Name)
                    and call.args[1].id == "legacy_outbox_values"
                ):
                    violations.append(f"{name} Outbox INSERT args drifted")
    seed = functions.get("seed_legacy")
    if seed is not None:
        seed_text = ast.unparse(seed)
        for name in (
            "legacy_request_columns",
            "legacy_request_values",
            "legacy_request_placeholders",
            "legacy_outbox_columns",
            "legacy_outbox_values",
            "legacy_outbox_placeholders",
        ):
            if name not in seed_text:
                violations.append(f"missing explicit {name}")
        if "%s" not in seed_text or "for _ in legacy_request_columns" not in seed_text:
            violations.append("Request placeholders are not generated from columns")
        if "%s" not in seed_text or "for _ in legacy_outbox_columns" not in seed_text:
            violations.append("Outbox placeholders are not generated from columns")
        if "_legacy_event_snapshot(" not in seed_text:
            violations.append("8dd event snapshot is not reconstructed")
        for name in ("legacy_request_columns", "legacy_outbox_columns"):
            assignments = [
                node
                for node in ast.walk(seed)
                if isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == name
                    for target in node.targets
                )
            ]
            if not assignments or not isinstance(assignments[0].value, ast.Tuple):
                violations.append(f"{name} is not an explicit tuple")
                continue
            values = {
                value.value
                for value in assignments[0].value.elts
                if isinstance(value, ast.Constant) and isinstance(value.value, str)
            }
            if name == "legacy_request_columns" and values & _LEGACY_NEW_COLUMNS:
                violations.append("Request INSERT includes post-8dd columns")
            if name == "legacy_outbox_columns" and values & _LEGACY_NEW_COLUMNS:
                violations.append("Outbox INSERT includes post-8dd columns")
            if name == "legacy_outbox_columns" and "event_snapshot_hash" not in values:
                violations.append("Outbox INSERT omits event_snapshot_hash")
    helper = functions.get("_require_disposable_legacy_fixture")
    if helper is not None:
        helper_text = ast.unparse(helper)
        if "document_runtime._validated_runtime_site()" not in helper_text:
            violations.append("legacy helper lost the validated Site guard")
        if "frappe.session" not in helper_text or "Administrator" not in helper_text:
            violations.append("legacy helper lost the Administrator guard")
    return violations


class Phase8ItemPublishRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_verifier()

    def test_legacy_collection_diagnostic_is_exact_and_response_neutral(self) -> None:
        module = self.module
        result = SimpleNamespace(
            status=503,
            body={"privateValue": "released Item status value"},
            trace_id=_TRACE_ID,
        )
        with patch.object(
            module,
            "LEGACY_QUERY_SERVER_DIAGNOSTICS_ENABLED",
            True,
        ), patch.object(
            module,
            "_sanitized_legacy_query_diagnostic",
            return_value=(
                "RuntimeError",
                "P803_LEGACY_QUERY_ROWS",
                _TRACE_ID,
            ),
        ):
            rendered = module.legacy_collection_failure_message(
                result,
                {"logs/npi_core.log": 0},
            )
        self.assertEqual(
            rendered,
            "P8-03 migrated legacy Item collection check failed "
            "[diagnostic_code=P803_LEGACY_QUERY_ROWS; "
            f"exception_type=RuntimeError; trace_id={_TRACE_ID}]",
        )
        for forbidden in ("503", "private", "released Item", "actual_count"):
            self.assertNotIn(forbidden, rendered)

        complete = SimpleNamespace(
            status=200,
            body={"items": [{}, {}, {}]},
            trace_id=_TRACE_ID,
        )
        self.assertIsNone(module.legacy_collection_failure_message(complete))

    def test_legacy_collection_diagnostic_falls_back_closed(self) -> None:
        module = self.module
        private = "released Item /tmp/private actor payload hash target"
        failures = (
            SimpleNamespace(
                status=500,
                body={"privateValue": private},
                trace_id=None,
            ),
            SimpleNamespace(
                status=200,
                body={"items": [{"privateValue": private}]},
                trace_id="trace-private-value",
            ),
        )
        for result in failures:
            with self.subTest(trace_id=result.trace_id):
                rendered = module.legacy_collection_failure_message(result)
                self.assertEqual(rendered, module._LEGACY_COLLECTION_FAILURE)
                self.assertNotIn(private, rendered)
                self.assertNotIn("diagnostic_code", rendered)
                self.assertNotIn("trace-private-value", rendered)

        with patch.object(module, "LEGACY_QUERY_SERVER_DIAGNOSTICS_ENABLED", False):
            rendered = module.legacy_collection_failure_message(
                SimpleNamespace(
                    status=500,
                    body={"privateValue": private},
                    trace_id=_TRACE_ID,
                )
            )
        self.assertEqual(rendered, module._LEGACY_COLLECTION_FAILURE)
        self.assertNotIn(_TRACE_ID, rendered)

    def test_legacy_query_server_diagnostic_activation_is_exact(self) -> None:
        module = self.module
        self.assertFalse(module.LEGACY_COLLECTION_DIAGNOSTICS_ENABLED)
        self.assertFalse(module.LEGACY_QUERY_SERVER_DIAGNOSTICS_ENABLED)
        self.assertFalse(module.ITEM_CREATE_DIAGNOSTICS_ENABLED)
        self.assertFalse(module.REPLAY_TERMINAL_DIAGNOSTICS_ENABLED)
        source = SCRIPT.read_text(encoding="utf-8")
        run_legacy = source.split("def run_legacy(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn(
            "legacy_query_diagnostic=LEGACY_QUERY_SERVER_DIAGNOSTICS_ENABLED",
            run_legacy,
        )
        self.assertIn("diagnostic_cursors", run_legacy)
        self.assertNotIn("_sanitized_server_diagnostic", run_legacy)
        self.assertEqual(source.count("legacy_query_diagnostic=True"), 0)

    def test_legacy_query_scope_header_requires_exact_collection_request(self) -> None:
        module = self.module
        captured: list[dict[str, str]] = []

        def request(*_args, request_headers, **_kwargs):
            captured.append(dict(request_headers))
            return SimpleNamespace(
                status=500,
                body={},
                trace_id=_TRACE_ID,
                headers={
                    "X-Request-ID": request_headers["X-Request-ID"],
                    "Cache-Control": "private, no-store",
                },
            )

        path = module.item_publish_path("00000000-0000-4000-8000-000000000001")
        with patch.object(module.document_runtime, "request", side_effect=request):
            module.item_publish_request(
                object(),
                "https://example.invalid",
                path,
                query_key="legacy-list",
                legacy_query_diagnostic=True,
            )
        self.assertEqual(
            captured[0][module._CREATE_DIAGNOSTIC_HEADER],
            module._LEGACY_QUERY_DIAGNOSTIC_SCOPE,
        )
        with patch.object(module.document_runtime, "request", side_effect=request):
            module.item_publish_request(
                object(),
                "https://example.invalid",
                path,
                query_key="legacy-list",
            )
        self.assertNotIn(module._CREATE_DIAGNOSTIC_HEADER, captured[1])
        invalid = (
            {"method": "POST", "query_key": "legacy-list"},
            {"query_key": "legacy-detail"},
            {"query_key": "legacy-list", "path": path + "/detail"},
            {"query_key": "legacy-list", "payload": {"private": "value"}},
        )
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(RuntimeError):
                module.item_publish_request(
                    object(),
                    "https://example.invalid",
                    values.pop("path", path),
                    legacy_query_diagnostic=True,
                    **values,
                )
        self.assertEqual(len(captured), 2)

    def test_replay_diagnostic_checkpoint_is_dormant_with_closed_create_scope(self) -> None:
        module = self.module
        self.assertFalse(module.ITEM_CREATE_DIAGNOSTICS_ENABLED)
        self.assertFalse(module.REPLAY_TERMINAL_DIAGNOSTICS_ENABLED)
        self.assertEqual(
            module._REPLAY_TERMINAL_DIAGNOSTIC_CODES,
            {
                "P803_REPLAY_FIXTURE_VALIDATE",
                "P803_REPLAY_REQUESTER_SESSION",
                "P803_REPLAY_BEFORE_SNAPSHOT",
                "P803_REPLAY_PROCESS_OUTBOX",
                "P803_REPLAY_SESSION_RESTORE",
                "P803_REPLAY_AFTER_SNAPSHOT",
                "P803_REPLAY_TERMINAL_OUTCOME",
                "P803_REPLAY_RECOVERABLE_SET",
                "P803_REPLAY_STRUCTURAL_EQUALITY",
            },
        )
        source = SCRIPT.read_text(encoding="utf-8")
        replay = source.split("def replay_terminal(", 1)[1].split("\ndef ", 1)[0]
        for code in module._REPLAY_TERMINAL_DIAGNOSTIC_CODES:
            self.assertIn(code, replay)
            self.assertEqual(replay.count(f'"{code}"'), 1)
        self.assertIn('"diagnostic_trace_id": diagnostic_trace_id', source)
        self.assertIn("diagnostic_trace_id = listed.trace_id", source)

    def test_replay_diagnostic_step_records_only_closed_tuple_and_reraises(self) -> None:
        module = self.module
        records: list[dict[str, object]] = []
        package = types.ModuleType("npi_core")
        package.__path__ = []
        api = types.ModuleType("npi_core.api")
        api.record_safe_diagnostic = lambda **values: records.append(values)
        original = RuntimeError("private released Item value /tmp/private")
        with patch.object(
            module,
            "REPLAY_TERMINAL_DIAGNOSTICS_ENABLED",
            True,
        ), patch.dict(
            sys.modules,
            {"npi_core": package, "npi_core.api": api},
        ), self.assertRaises(RuntimeError) as failure:
            with module.replay_terminal_diagnostic_step(
                "P803_REPLAY_PROCESS_OUTBOX",
                _TRACE_ID,
            ):
                raise original
        self.assertIs(failure.exception, original)
        self.assertEqual(
            records,
            [
                {
                    "code": "P803_REPLAY_PROCESS_OUTBOX",
                    "title": "NPI Item publish terminal replay stage failed",
                    "exception_type": "RuntimeError",
                    "trace_id": _TRACE_ID,
                }
            ],
        )
        self.assertNotIn("private released Item value", str(records))
        self.assertNotIn("/tmp/private", str(records))

    def test_replay_diagnostic_step_is_closed_when_disabled_or_invalid(self) -> None:
        module = self.module
        cases = (
            (False, "P803_REPLAY_PROCESS_OUTBOX", _TRACE_ID),
            (True, "P803_REPLAY_NOT_ALLOWED", _TRACE_ID),
            (True, "P803_REPLAY_PROCESS_OUTBOX", "trace-private-value"),
        )
        for enabled, code, trace_id in cases:
            records: list[dict[str, object]] = []
            package = types.ModuleType("npi_core")
            package.__path__ = []
            api = types.ModuleType("npi_core.api")
            api.record_safe_diagnostic = lambda **values: records.append(values)
            original = RuntimeError("private exception message")
            with self.subTest(enabled=enabled, code=code, trace_id=trace_id), patch.object(
                module,
                "REPLAY_TERMINAL_DIAGNOSTICS_ENABLED",
                enabled,
            ), patch.dict(
                sys.modules,
                {"npi_core": package, "npi_core.api": api},
            ), self.assertRaises(RuntimeError) as failure:
                with module.replay_terminal_diagnostic_step(code, trace_id):
                    raise original
            self.assertIs(failure.exception, original)
            self.assertEqual(records, [])

    def test_replay_log_reader_requires_one_exact_logical_record(self) -> None:
        module = self.module

        def read(
            records: list[dict[str, object]],
            site_records: list[dict[str, object]] | None = None,
            trace_id: str = _TRACE_ID,
        ):
            with tempfile.TemporaryDirectory() as directory:
                bench_path = Path(directory).resolve()
                paths = (
                    bench_path / "logs" / "npi_core.log",
                    bench_path
                    / "sites"
                    / module.SITE_NAME
                    / "logs"
                    / "npi_core.log",
                )
                for path in paths:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("prior safe log\n", encoding="utf-8")
                with patch.object(module, "BENCH_PATH", bench_path):
                    cursors = module._replay_diagnostic_log_cursors()
                    for path, source_records in zip(
                        paths,
                        (records, site_records or []),
                    ):
                        with path.open("a", encoding="utf-8") as log_file:
                            for record in source_records:
                                log_file.write(
                                    "private value /tmp/private "
                                    + json.dumps(record, separators=(",", ":"))
                                    + "\n"
                                )
                    return module._sanitized_replay_terminal_diagnostic(
                        trace_id,
                        cursors,
                    )

        valid = {
            "code": "P803_REPLAY_PROCESS_OUTBOX",
            "exceptionType": "RuntimeError",
            "traceId": _TRACE_ID,
        }
        self.assertEqual(
            read([valid]),
            ("RuntimeError", "P803_REPLAY_PROCESS_OUTBOX", _TRACE_ID),
        )
        self.assertEqual(
            read([valid], [valid]),
            ("RuntimeError", "P803_REPLAY_PROCESS_OUTBOX", _TRACE_ID),
        )
        self.assertIsNone(read([valid, valid]))
        self.assertIsNone(
            read(
                [valid],
                [{**valid, "code": "P803_REPLAY_AFTER_SNAPSHOT"}],
            )
        )
        invalid_cases = (
            [],
            [{**valid, "traceId": "trace-ffffffffffffffffffffffffffffffff"}],
            [{**valid, "code": "P803_REPLAY_NOT_ALLOWED"}],
            [{**valid, "exceptionType": "Bad Type /tmp/private"}],
            [{**valid, "privateValue": "released Item"}],
        )
        for records in invalid_cases:
            with self.subTest(records=records):
                self.assertIsNone(read(records))
        self.assertIsNone(read([valid], trace_id="trace-private-value"))

    def test_legacy_query_log_reader_requires_one_exact_logical_record(self) -> None:
        module = self.module

        def read(
            records: list[dict[str, object]],
            site_records: list[dict[str, object]] | None = None,
            trace_id: str = _TRACE_ID,
        ):
            with tempfile.TemporaryDirectory() as directory:
                bench_path = Path(directory).resolve()
                paths = (
                    bench_path / "logs" / "npi_core.log",
                    bench_path / "sites" / module.SITE_NAME / "logs" / "npi_core.log",
                )
                for path in paths:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("prior safe log\n", encoding="utf-8")
                with patch.object(module, "BENCH_PATH", bench_path):
                    cursors = module._replay_diagnostic_log_cursors()
                    for path, source_records in zip(
                        paths,
                        (records, site_records or []),
                    ):
                        with path.open("a", encoding="utf-8") as log_file:
                            for record in source_records:
                                log_file.write(
                                    "private actor /tmp/private "
                                    + json.dumps(record, separators=(",", ":"))
                                    + "\n"
                                )
                    return module._sanitized_legacy_query_diagnostic(
                        trace_id,
                        cursors,
                    )

        valid = {
            "code": "P803_LEGACY_QUERY_ROWS",
            "exceptionType": "RuntimeError",
            "traceId": _TRACE_ID,
        }
        expected = ("RuntimeError", "P803_LEGACY_QUERY_ROWS", _TRACE_ID)
        self.assertEqual(read([valid]), expected)
        self.assertEqual(read([valid], [valid]), expected)
        self.assertIsNone(read([valid, valid]))
        self.assertIsNone(
            read(
                [valid],
                [{**valid, "code": "P803_LEGACY_QUERY_PROFILE"}],
            )
        )
        for records in (
            [],
            [{**valid, "traceId": "trace-ffffffffffffffffffffffffffffffff"}],
            [{**valid, "code": "P803_LEGACY_QUERY_NOT_ALLOWED"}],
            [{**valid, "exceptionType": "Bad Type /tmp/private"}],
            [{**valid, "privateValue": "released Item"}],
        ):
            with self.subTest(records=records):
                self.assertIsNone(read(records))
        self.assertIsNone(read([valid], trace_id="trace-private-value"))

    def test_failed_child_output_is_never_read_or_rendered(self) -> None:
        module = self.module
        private = "released Item /tmp/private actor payload hash target"
        completed = SimpleNamespace(returncode=1)
        kwargs = {
            "diagnostic_trace_id": _TRACE_ID,
            "project_id": private,
            "bindings": [{"request_id": private, "outbox_id": private}],
        }
        with patch.object(
            module,
            "_replay_diagnostic_log_cursors",
            return_value={"logs/npi_core.log": 0},
        ), patch.object(
            module,
            "REPLAY_TERMINAL_DIAGNOSTICS_ENABLED",
            True,
        ), patch.object(
            module.subprocess,
            "run",
            return_value=completed,
        ) as failed_run, patch.object(
            module,
            "_sanitized_replay_terminal_diagnostic",
            return_value=(
                "RuntimeError",
                "P803_REPLAY_PROCESS_OUTBOX",
                _TRACE_ID,
            ),
        ), self.assertRaises(RuntimeError) as failure:
            module.run_bench_fixture("replay_terminal", kwargs)
        run_kwargs = failed_run.call_args.kwargs
        self.assertNotIn("capture_output", run_kwargs)
        self.assertIs(run_kwargs["stderr"], module.subprocess.DEVNULL)
        self.assertNotIn("stdout", vars(completed))
        self.assertNotIn("stderr", vars(completed))
        rendered = str(failure.exception)
        self.assertEqual(
            rendered,
            "P8-03 Bench fixture replay_terminal failed with a withheld diagnostic "
            "[diagnostic_code=P803_REPLAY_PROCESS_OUTBOX; "
            f"exception_type=RuntimeError; trace_id={_TRACE_ID}]",
        )
        self.assertNotIn(private, rendered)

        with patch.object(
            module,
            "_replay_diagnostic_log_cursors",
            return_value=None,
        ), patch.object(
            module.subprocess,
            "run",
            return_value=completed,
        ), self.assertRaises(RuntimeError) as closed:
            module.run_bench_fixture("replay_terminal", kwargs)
        self.assertEqual(
            str(closed.exception),
            "P8-03 Bench fixture replay_terminal failed with a withheld diagnostic",
        )
        self.assertNotIn(private, str(closed.exception))

    def test_successful_child_result_is_read_only_after_zero_exit(self) -> None:
        module = self.module
        expected = {"fixture": "complete", "count": 2}

        def complete_successfully(*_args, **kwargs):
            kwargs["stdout"].write("bench prelude\n")
            kwargs["stdout"].write(json.dumps(expected) + "\n")
            kwargs["stdout"].flush()
            return SimpleNamespace(returncode=0)

        with patch.object(
            module.subprocess,
            "run",
            side_effect=complete_successfully,
        ) as successful_run:
            result = module.run_bench_fixture("capture_project", {})
        self.assertEqual(result, expected)
        run_kwargs = successful_run.call_args.kwargs
        self.assertNotIn("capture_output", run_kwargs)
        self.assertIs(run_kwargs["stderr"], module.subprocess.DEVNULL)

    def test_replay_log_reader_rejects_unsafe_log_boundaries(self) -> None:
        module = self.module
        valid = {
            "code": "P803_REPLAY_PROCESS_OUTBOX",
            "exceptionType": "RuntimeError",
            "traceId": _TRACE_ID,
        }

        with tempfile.TemporaryDirectory() as directory:
            bench_path = Path(directory).resolve()
            log_path = bench_path / "logs" / "npi_core.log"
            site_log_path = (
                bench_path / "sites" / module.SITE_NAME / "logs" / "npi_core.log"
            )
            for path in (log_path, site_log_path):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("prior safe log\n", encoding="utf-8")
            with patch.object(module, "BENCH_PATH", bench_path):
                cursors = module._replay_diagnostic_log_cursors()
                self.assertIsNotNone(cursors)

                log_path.unlink()
                external = bench_path.parent / f"{bench_path.name}-outside.log"
                try:
                    external.write_text(json.dumps(valid) + "\n", encoding="utf-8")
                    log_path.symlink_to(external)
                    self.assertIsNone(
                        module._sanitized_replay_terminal_diagnostic(
                            _TRACE_ID,
                            cursors,
                        )
                    )
                finally:
                    log_path.unlink(missing_ok=True)
                    external.unlink(missing_ok=True)

                log_path.write_text("prior safe log\n", encoding="utf-8")
                with log_path.open("a", encoding="utf-8") as log_file:
                    log_file.write("x" * (module._REPLAY_DIAGNOSTIC_LOG_LIMIT + 1))
                self.assertIsNone(
                    module._sanitized_replay_terminal_diagnostic(
                        _TRACE_ID,
                        cursors,
                    )
                )

                log_path.write_text(
                    "prior safe log\n" + json.dumps(valid) + "\n",
                    encoding="utf-8",
                )
                original_resolve = Path.resolve

                def resolve_outside(path, *, strict=False):
                    if path == log_path:
                        return bench_path.parent / "simulated-outside.log"
                    return original_resolve(path, strict=strict)

                with patch.object(
                    Path,
                    "resolve",
                    autospec=True,
                    side_effect=resolve_outside,
                ):
                    self.assertIsNone(
                        module._sanitized_replay_terminal_diagnostic(
                            _TRACE_ID,
                            cursors,
                        )
                    )

    def test_runtime_verifier_covers_command_claim_boundary_and_restart(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        ast.parse(source)
        for marker in (
            "ITEM_EXECUTION_PROFILE_UNAVAILABLE",
            "live claim was not excluded",
            "expired pre-boundary claim was not recovered",
            "durable adapter boundary was not sealed",
            "crossed-boundary recovery blindly redispatched",
            "synthetic_verified",
            "uncertain_after_timeout",
            "target_idempotency_key_hash",
            "NPI_P8_03_RUNTIME_WORKER",
            "frozen service actor binding drifted",
            "distinct retained actors",
            "enabled internal NPI API User",
            "cross-process replay changed terminal truth",
            "recoverable_outbox_event_ids",
            '"mappingCount": 0',
            '"adapterCalls": synthetic_adapter_call_count()',
        ):
            self.assertIn(marker, source)

    def test_create_diagnostic_is_disabled_and_remains_closed_and_structural(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("ITEM_CREATE_DIAGNOSTICS_ENABLED = False", source)
        self.assertIn('label == "synthetic"', source)
        self.assertIn('"p803-item-create-v1"', source)
        self.assertIn("_sanitized_server_diagnostic", source)
        self.assertIn("_CREATE_SERVER_DIAGNOSTIC_CODES", source)
        self.assertNotIn('trace_id=headers["X-Trace-ID"]', source)
        diagnostic_block = source.split("if created.status != 201", 1)[1].split(
            "require(", 1
        )[0]
        self.assertNotIn("created.body", diagnostic_block)
        self.assertIn("item_create_failure_message(created)", diagnostic_block)
        failure_helper = source.split(
            "def item_create_failure_message", 1
        )[1].split("\ndef ", 1)[0]
        self.assertIn("sanitized_problem_code(result)", failure_helper)

    def test_runtime_is_network_free_and_never_claims_formal_truth(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("urllib.request", source)
        self.assertIn("_assert_no_formal_target", source)
        self.assertIn('== {"synthetic", "none"}', source)
        self.assertIn('row["formal_item_code"] is None', source)
        self.assertIn('row["target_version"] is None', source)
        for forbidden in (
            "requests.",
            "httpx.",
            "erpnext.com",
            "core.whjichen.cn",
            "ignore_mandatory",
            "ignore_validate",
        ):
            self.assertNotIn(forbidden, source)

    def test_runtime_trace_is_structured_and_backed_by_persisted_queries(self) -> None:
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }
        structural = functions["_structural_context"]
        structural_text = ast.unparse(structural)
        for persisted_field in (
            "'owner'",
            "'modified_by'",
            "'service_actor_user_id'",
            "'semantic_effect_hash'",
            "'guards'",
            "'auditEvents'",
        ):
            self.assertIn(persisted_field, structural_text)
        exercise = functions["exercise_worker"]
        exercise_text = ast.unparse(exercise)
        for trace_key in (
            "'callerRestoredAfterSynthetic'",
            "'callerRestoredAfterUncertain'",
            "'adapterSessionWorkerOnly'",
        ):
            self.assertIn(trace_key, exercise_text)
        runtime_text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"ITEM_PUBLISH_STREAM_ACTIVE"', runtime_text)
        self.assertIn('"ITEM_PUBLISH_EFFECT_RETAINED"', runtime_text)
        trace = {
            "adapterSessionWorkerOnly": True,
            "callerRestoredAfterSynthetic": True,
            "callerRestoredAfterUncertain": True,
            "ownerAndAuditBindingsVerified": True,
        }
        decoded = json.loads(json.dumps(trace, sort_keys=True))
        self.assertEqual(decoded, trace)

    def test_worker_actor_is_bound_before_use_and_process_runs_from_requester(self) -> None:
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        exercise = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "exercise_worker"
        )
        assigned = {
            node.id
            for node in ast.walk(exercise)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
        }
        loaded = {
            node.id
            for node in ast.walk(exercise)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        }
        self.assertIn("worker_user", assigned)
        self.assertIn("worker_user", loaded)
        self.assertNotIn("frappe.set_user(worker_user)", ast.unparse(exercise))
        self.assertIn("process_outbox_message", ast.unparse(exercise))

    def test_disposable_adapter_registry_is_exactly_marker_gated(self) -> None:
        source = FIXTURE.read_text(encoding="utf-8")
        ast.parse(source)
        for marker in (
            '"npi-one-item-publish-disposable-v1"',
            'os.environ.get("NPI_P8_03_RUNTIME_ENABLED") == "1"',
            'os.environ.get("NPI_P8_03_RUNTIME_MARKER") == _RUNTIME_MARKER',
            "ItemTargetMode.SYNTHETIC",
            "synthetic_adapter_call_count",
            "network-free-synthetic-v1",
            "synthetic_adapter_session_users",
            "Disposable Item adapter session actor drifted",
        ):
            self.assertIn(marker, source)
        for forbidden in (
            "base_url=",
            "secret_reference=",
            "ItemTargetMode.SANDBOX",
            "requests.",
            "httpx.",
        ):
            self.assertNotIn(forbidden, source)

    def test_shell_runs_default_disabled_fresh_and_cross_process_replay(self) -> None:
        source = SHELL.read_text(encoding="utf-8")
        for marker in (
            "capture_item_publish_runtime_project_id",
            "export_item_publish_runtime_environment",
            "clear_item_publish_runtime_environment",
            "run_item_publish_runtime_verifier disabled",
            "run_item_publish_runtime_verifier fresh",
            "run_item_publish_runtime_verifier replay-only",
            "verify_item_publish_runtime_log_redaction",
            "item_publish_runtime_environment_active=true",
        ):
            self.assertIn(marker, source)
        disabled = source.rindex("run_item_publish_runtime_verifier disabled")
        enabled = source.rindex("export_item_publish_runtime_environment")
        fresh = source.rindex("run_item_publish_runtime_verifier fresh")
        replay = source.rindex("run_item_publish_runtime_verifier replay-only")
        self.assertLess(disabled, enabled)
        self.assertLess(enabled, fresh)
        self.assertLess(fresh, replay)

    def test_migration_fixture_is_marker_gated_and_runs_after_replay(self) -> None:
        verifier = SCRIPT.read_text(encoding="utf-8")
        shell = SHELL.read_text(encoding="utf-8")
        for marker in (
            "def seed_legacy(",
            "def inspect_legacy(",
            "def cleanup_legacy(",
            '"preMigrationShape": "8dd"',
            '"newBindingsNull": True',
            '"preMigrationDuplicateAttemptCount": duplicate_attempt_count',
            'resultAttemptIndexUnique',
            '"ITEM_PUBLISH_STREAM_RECONCILIATION_REQUIRED"',
            "--legacy-only",
            "tabNPI Item Publish Stream Guard",
            "def _require_disposable_legacy_fixture(",
            "document_runtime._validated_runtime_site()",
            '"npi.localhost"',
            '"npi_one_runtime"',
            '"npi-one-local-runtime-disposable-v1"',
            '"Administrator"',
            "legacy_request_columns",
            "legacy_outbox_columns",
            "LEGACY_OUTBOX_PAYLOAD_KEYS",
            "legacy_event_snapshot_hash",
        ):
            self.assertIn(marker, verifier)
        self.assertIn("seed_item_publish_runtime_legacy", shell)
        self.assertIn("bench --site \"${site_name}\" migrate", shell)
        self.assertIn("run_item_publish_runtime_verifier legacy-only", shell)
        self.assertLess(
            shell.rindex("run_item_publish_runtime_verifier replay-only"),
            shell.rindex("seed_item_publish_runtime_legacy"),
        )
        self.assertLess(
            shell.rindex("seed_item_publish_runtime_legacy"),
            shell.rindex("run_item_publish_runtime_verifier legacy-only"),
        )

    def test_legacy_fixture_sql_is_exactly_guarded_and_8dd_shaped(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(_legacy_sql_contract_violations(source), [])
        tree = ast.parse(source)
        functions = _function_nodes(tree)
        for name in _LEGACY_SQL_FUNCTIONS:
            function = functions[name]
            sql_calls = [
                node for node in ast.walk(function) if _is_frappe_db_sql(node)
            ]
            self.assertTrue(sql_calls, name)
            self.assertLess(
                min(
                    node.lineno
                    for node in ast.walk(function)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "_require_disposable_legacy_fixture"
                ),
                min(node.lineno for node in sql_calls),
            )
        self.assertNotIn("SELECT * FROM", source)
        self.assertNotIn("UPDATE `tabNPI Outbox Message`", source)
        seed_text = ast.unparse(functions["seed_legacy"])
        self.assertIn("disposition", seed_text)
        self.assertIn("ready", seed_text)
        self.assertIn("_TRACE_PATTERN.fullmatch(legacy_trace_id)", seed_text)
        self.assertIn("trace_id=legacy_trace_id", seed_text)
        seed = functions["seed_legacy"]
        assignments = {
            target.id: node.value
            for node in seed.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        request_columns = assignments["legacy_request_columns"]
        request_values = assignments["legacy_request_values"]
        outbox_columns = assignments["legacy_outbox_columns"]
        outbox_values = assignments["legacy_outbox_values"]
        self.assertIsInstance(request_columns, ast.Tuple)
        self.assertIsInstance(request_values, ast.Tuple)
        self.assertIsInstance(outbox_columns, ast.Tuple)
        self.assertIsInstance(outbox_values, ast.Tuple)

        def value_for(columns: ast.Tuple, values: ast.Tuple, fieldname: str):
            names = [
                value.value
                for value in columns.elts
                if isinstance(value, ast.Constant)
            ]
            return values.elts[names.index(fieldname)]

        request_trace = value_for(
            request_columns,
            request_values,
            "trace_id",
        )
        outbox_trace = value_for(
            outbox_columns,
            outbox_values,
            "trace_id",
        )
        self.assertIsInstance(request_trace, ast.Name)
        self.assertIsInstance(outbox_trace, ast.Name)
        self.assertEqual(request_trace.id, "legacy_trace_id")
        self.assertEqual(outbox_trace.id, "legacy_trace_id")
        event_helper = functions["_legacy_event_snapshot"]
        event_return = next(
            node
            for node in ast.walk(event_helper)
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict)
        )
        event_keys = {
            key.value
            for key in event_return.value.keys
            if isinstance(key, ast.Constant)
        }
        self.assertEqual(
            event_keys,
            {
                "schemaVersion",
                "eventId",
                "eventType",
                "globalId",
                "objectVersion",
                "tenantId",
                "projectGlobalId",
                "requestGlobalId",
                "operation",
                "profileId",
                "profileVersion",
                "profileSnapshotHash",
                "sourceStreamKeyHash",
                "sourceHash",
                "expectedMappingVersion",
                "expectedTargetVersion",
                "actorUserId",
                "requestId",
                "traceId",
                "idempotencyKeyHash",
                "payloadHash",
            },
        )

    def test_legacy_result_unique_index_uses_exact_mariadb_marker(self) -> None:
        verifier = load_verifier()
        for value in (0, "0"):
            with self.subTest(value=value):
                self.assertTrue(verifier._mariadb_index_is_unique(value))
        invalid_values = (1, "1", None, True, False, "", "00", "invalid", object())
        for value in invalid_values:
            with self.subTest(value=value):
                self.assertFalse(verifier._mariadb_index_is_unique(value))
        self.assertFalse(verifier._mariadb_index_is_unique({}.get("Non_unique")))

        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        inspect_function = _function_nodes(tree)["inspect_legacy"]
        helper_calls = [
            node
            for node in ast.walk(inspect_function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_mariadb_index_is_unique"
        ]
        self.assertEqual(len(helper_calls), 1)
        helper_argument = helper_calls[0].args[0]
        self.assertIsInstance(helper_argument, ast.Call)
        self.assertIsInstance(helper_argument.func, ast.Attribute)
        self.assertEqual(helper_argument.func.attr, "get")
        self.assertEqual(len(helper_argument.args), 1)
        self.assertIsInstance(helper_argument.args[0], ast.Constant)
        self.assertEqual(helper_argument.args[0].value, "Non_unique")
        inspect_source = ast.unparse(inspect_function)
        self.assertNotIn('index.get("Non_unique") or 1', inspect_source)
        self.assertNotIn("index.get('Non_unique') or 1", inspect_source)

        for peer in (
            ROOT / "scripts" / "verify_project_controls_runtime.py",
            ROOT / "scripts" / "verify_gate_review_runtime.py",
        ):
            self.assertIn(
                'int(row.get("Non_unique")) == 0',
                peer.read_text(encoding="utf-8"),
            )

    def test_legacy_cleanup_remains_after_successful_inspection(self) -> None:
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        run_legacy = _function_nodes(tree)["run_legacy"]
        calls = {
            node.args[0].value: node.lineno
            for node in ast.walk(run_legacy)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "run_bench_fixture"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        }
        self.assertLess(calls["inspect_legacy"], calls["cleanup_legacy"])

    def test_legacy_fixture_sql_negative_variants_fail_closed(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        variants = {
            "deleted_validated_site": source.replace(
                "    document_runtime._validated_runtime_site()\n"
                "    require(\n"
                "        frappe.local.site == SITE_NAME",
                "    require(\n        frappe.local.site == SITE_NAME",
                1,
            ),
            "deleted_legacy_guard": source.replace(
                "    _require_disposable_legacy_fixture(fixture_run_id, project_id)\n"
                "    rows = _rows(",
                "    _require_enabled_runtime_marker(project_id)\n    rows = _rows(",
                1,
            ),
            "external_table": source.replace(
                "tabNPI Outbox Message",
                "tabExternal Outbox Message",
                1,
            ),
            "unbounded_delete": source.replace(
                "WHERE name = %s AND project_global_id = %s",
                "WHERE name = %s",
                1,
            ),
            "wrong_insert_args": source.replace(
                "        legacy_request_values,\n",
                "        legacy_outbox_values,\n",
                1,
            ),
            "copy_then_update": source.replace(
                "    legacy_outbox_columns = (",
                "    " + "frappe" + ".db.sql(\"INSERT INTO `tabNPI Outbox Message` "
                "SELECT * FROM `tabNPI Outbox Message` WHERE name = %s\", "
                "(source_outbox.name,))\n    legacy_outbox_columns = (",
                1,
            ),
            "outbox_update": source.replace(
                "    legacy_outbox_columns = (",
                "    " + "frappe" + ".db.sql(\"UPDATE `tabNPI Outbox Message` SET name = %s "
                "WHERE name = %s\", (legacy_outbox_id, legacy_outbox_id))\n"
                "    legacy_outbox_columns = (",
                1,
            ),
        }
        for name, variant in variants.items():
            with self.subTest(name=name):
                self.assertTrue(_legacy_sql_contract_violations(variant))

    def test_controlled_workflow_retains_p8_03_as_current_p8_04_predecessor(
        self,
    ) -> None:
        source = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("tests.test_phase8_item_publish_runtime_verifier", source)
        self.assertIn(
            "bash scripts/verify-frappe-runtime.sh --projection-only", source
        )
        self.assertIn(
            "# Preserved P8-03 scope: scope=p5-01-through-p8-03", source
        )
        self.assertIn(
            "# Preserved P8-03 predecessor_scope=p5-01-through-p8-02", source
        )
        self.assertIn("printf 'scope=p5-01-through-p8-04\\n'", source)
        self.assertIn(
            "printf 'predecessor_scope=p5-01-through-p8-03\\n'", source
        )
        self.assertIn("p8-integration-runtime-${{ github.run_id }}", source)
        self.assertIn("needs.controlled_preflight.result == 'success'", source)


if __name__ == "__main__":
    unittest.main()
