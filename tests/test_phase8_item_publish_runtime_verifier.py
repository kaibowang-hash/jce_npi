from __future__ import annotations

import ast
import json
import re
import unittest
from pathlib import Path


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

    def test_create_diagnostic_is_first_request_only_closed_and_structural(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("ITEM_CREATE_DIAGNOSTICS_ENABLED = True", source)
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

    def test_controlled_workflow_records_cumulative_p8_03_scope(self) -> None:
        source = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("tests.test_phase8_item_publish_runtime_verifier", source)
        self.assertIn(
            "bash scripts/verify-frappe-runtime.sh --projection-only", source
        )
        self.assertIn("scope=p5-01-through-p8-03", source)
        self.assertIn("predecessor_scope=p5-01-through-p8-02", source)
        self.assertIn("p8-integration-runtime-${{ github.run_id }}", source)
        self.assertIn("needs.controlled_preflight.result == 'success'", source)


if __name__ == "__main__":
    unittest.main()
