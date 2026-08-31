from __future__ import annotations

import argparse
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import collect_erpnext_production_facts as collector


class ProductionFactCollectorTest(unittest.TestCase):
    def state_path(self) -> Path:
        path = Path(tempfile.gettempdir()) / f"p8-07f-test-{os.getpid()}-{id(self)}.json"
        path.unlink(missing_ok=True)
        self.addCleanup(path.unlink, missing_ok=True)
        self.addCleanup(path.with_name(path.name + ".next").unlink, missing_ok=True)
        return path

    def write_manifest(self, value: object) -> Path:
        temporary = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            delete=False,
        )
        with temporary:
            json.dump(value, temporary)
        path = Path(temporary.name)
        self.addCleanup(path.unlink, missing_ok=True)
        return path

    def write_state(self, path: Path, *, sha: str = "d" * 40, run_id: str = "101") -> None:
        collector._write_new_state(
            path,
            {
                "schema_version": 1,
                "task_id": collector.TASK_ID,
                "exact_sha": sha,
                "ordinary_run_id": run_id,
                "apps": [
                    {
                        "label": "CUSTOM_APP_01",
                        "name": "custom_one",
                        "root": "apps/custom_one",
                    }
                ],
                "tracked_paths": {"CUSTOM_APP_01": ["custom_one/hooks.py"]},
                "operation_records": [],
            },
        )

    def test_transport_is_fixed_and_noninteractive(self) -> None:
        argv = collector._ssh_argv(("bench", "version"))
        self.assertEqual(argv[0], "ssh")
        self.assertEqual(
            argv[-2:],
            ("JCE-Core", "cd frappe-bench && exec bench version"),
        )
        self.assertEqual(collector.REMOTE_BENCH_ROOT, "frappe-bench")
        for expected in (
            "BatchMode=yes",
            "RequestTTY=no",
            "StrictHostKeyChecking=yes",
            "ForwardAgent=no",
            "ClearAllForwardings=yes",
            "ControlMaster=no",
            "PasswordAuthentication=no",
            "KbdInteractiveAuthentication=no",
        ):
            self.assertIn(expected, argv)
        self.assertNotIn("-A", argv)
        self.assertNotIn("-L", argv)
        self.assertNotIn("-R", argv)
        with self.assertRaisesRegex(collector.FactCollectionError, "unsafe"):
            collector._ssh_argv(("bench", "version;whoami"))

    def test_remote_operation_allowlist_is_exact(self) -> None:
        self.assertEqual(collector._remote_command("ERP_VERSION"), ("bench", "version"))
        self.assertEqual(
            collector._remote_command("INSTALLED_APPS", site="site-one"),
            ("bench", "--site", "site-one", "list-apps"),
        )
        self.assertEqual(
            collector._remote_command("APP_HEAD", root="apps/custom_one"),
            ("git", "-C", "apps/custom_one", "rev-parse", "HEAD"),
        )
        self.assertEqual(
            collector._remote_command("APP_STATUS", root="apps/custom_one"),
            ("git", "-C", "apps/custom_one", "status", "--short", "-uno"),
        )
        self.assertEqual(
            collector._remote_command("APP_TRACKED_PATHS", root="apps/custom_one"),
            ("git", "-C", "apps/custom_one", "ls-files", "-z"),
        )
        self.assertEqual(
            collector._remote_command(
                "APP_FILE_READ",
                root="apps/custom_one",
                path="custom_one/hooks.py",
            ),
            ("git", "-C", "apps/custom_one", "show", "HEAD:custom_one/hooks.py"),
        )
        self.assertEqual(
            collector._remote_command(
                "APP_FILE_MODE",
                root="apps/custom_one",
                path="custom_one/hooks.py",
            ),
            ("git", "-C", "apps/custom_one", "ls-files", "-s", "--", "custom_one/hooks.py"),
        )
        self.assertEqual(
            collector._remote_command(
                "APP_WORKTREE_DIFF",
                root="apps/custom_one",
                path="custom_one/hooks.py",
            ),
            (
                "git",
                "-C",
                "apps/custom_one",
                "diff",
                "--no-ext-diff",
                "--no-renames",
                "--no-color",
                "--unified=1000000",
                "HEAD",
                "--",
                "custom_one/hooks.py",
            ),
        )
        runtime = collector._runtime_command("CUSTOM_FIELDS", "site-one", 0)
        self.assertEqual(runtime[:6], ("bench", "--site", "site-one", "execute", "frappe.client.get_list", "--kwargs"))
        kwargs = json.loads(runtime[6])
        self.assertEqual(kwargs["doctype"], "Custom Field")
        self.assertEqual(kwargs["limit_page_length"], 200)
        self.assertEqual(kwargs["order_by"], "name asc")
        with self.assertRaises(collector.FactCollectionError):
            collector._remote_command("CONSOLE", root="apps/custom_one")
        with self.assertRaises(collector.FactCollectionError):
            collector._remote_command("APP_HEAD", root="../custom_one")
        with self.assertRaises(collector.FactCollectionError):
            collector._remote_command(
                "APP_FILE_READ",
                root="apps/custom_one",
                path="../../site_config.json",
            )
        with self.assertRaises(collector.FactCollectionError):
            collector._runtime_command("CALLER_SELECTED", "site-one", 0)
        parent = collector._parent_document_command("site-one", "DocType", "Item")
        self.assertEqual(parent[:5], ("bench", "--site", "site-one", "execute", "frappe.client.get"))
        self.assertEqual(json.loads(parent[6]), {"doctype": "DocType", "name": "Item"})
        with self.assertRaises(collector.FactCollectionError):
            collector._parent_document_command("site-one", "User", "Administrator")

        locale = collector._site_fact_commands("SYSTEM_LOCALE", "site-one")
        self.assertEqual(len(locale), 1)
        self.assertEqual(
            locale[0][1][:6],
            ("bench", "--site", "site-one", "execute", "frappe.client.get_value", "--kwargs"),
        )
        locale_kwargs = json.loads(locale[0][1][6])
        self.assertEqual(locale_kwargs["doctype"], "System Settings")
        self.assertEqual(locale_kwargs["fieldname"], ["language", "time_zone", "country"])
        self.assertNotIn("filters", locale_kwargs)
        file_shapes = collector._site_fact_commands("FILE_URL_SHAPES", "site-one")
        self.assertEqual(
            [operation for operation, _ in file_shapes],
            [
                "FILE_URL_SHAPES_TOTAL",
                "FILE_URL_SHAPES_LOCAL_PUBLIC",
                "FILE_URL_SHAPES_LOCAL_PRIVATE",
                "FILE_URL_SHAPES_EXTERNAL_HTTP",
            ],
        )
        for _, command in file_shapes:
            self.assertEqual(
                command[:6],
                ("bench", "--site", "site-one", "execute", "frappe.client.get_count", "--kwargs"),
            )
            self.assertEqual(json.loads(command[6])["doctype"], "File")
            self.assertNotIn("sql", " ".join(command).lower())
            self.assertNotIn("console", " ".join(command).lower())
        with self.assertRaises(collector.FactCollectionError):
            collector._site_fact_commands("CALLER_SELECTED", "site-one")

    def test_every_runtime_family_uses_one_fixed_application_layer_read_shape(self) -> None:
        for family, spec in collector.RUNTIME_METADATA_SPECS.items():
            with self.subTest(family=family):
                if family in collector.PARENT_METADATA_FAMILIES:
                    continue
                command = collector._runtime_command(family, "site-one", 0)
                self.assertEqual(command[:5], ("bench", "--site", "site-one", "execute", "frappe.client.get_list"))
                self.assertEqual(command[5], "--kwargs")
                kwargs = json.loads(command[6])
                self.assertEqual(kwargs["doctype"], spec["doctype"])
                self.assertEqual(kwargs["fields"], list(spec["fields"]))
                expected_filters = json.loads(
                    json.dumps([list(row) for row in spec.get("filters", ())])
                )
                self.assertEqual(kwargs["filters"], expected_filters)
                self.assertEqual(kwargs["order_by"], "name asc")
                self.assertEqual(kwargs["limit_start"], 0)
                self.assertEqual(
                    kwargs["limit_page_length"],
                    collector.RUNTIME_PAGE_SIZE_OVERRIDES.get(
                        family, collector.RUNTIME_PAGE_SIZE
                    ),
                )
                self.assertNotIn("sql", " ".join(command).lower())
                self.assertNotIn("console", " ".join(command).lower())

        self.assertNotIn(
            "script_type",
            collector.RUNTIME_METADATA_SPECS["CLIENT_SCRIPTS"]["fields"],
        )
        self.assertIn("DMR", collector.REQUIRED_ERPNEXT_DOCTYPES)
        self.assertIn("Mold", collector.REQUIRED_ERPNEXT_DOCTYPES)
        self.assertIn("Mold Repair", collector.REQUIRED_ERPNEXT_DOCTYPES)

    def test_discover_writes_private_state_and_redacts_custom_app_name(self) -> None:
        path = self.state_path()
        args = argparse.Namespace(
            expected_sha="a" * 40,
            ordinary_run_id="123",
            state=str(path),
        )
        calls: list[tuple[str, tuple[str, ...], int]] = []

        def runner(operation: str, command: tuple[str, ...], limit: int) -> bytes:
            calls.append((operation, command, limit))
            return (
                b"erpnext 15.70.0 version-15 (1234abc)\n"
                b"frappe 15.74.2 version-15 (5678def)\n"
                b"secret_custom 1.2.3 main (90abcde)\n"
            )

        with patch.object(collector, "_preflight"), patch.dict(os.environ, {}, clear=True), patch.object(
            collector, "_emit"
        ) as emit:
            collector._discover(args, runner)

        self.assertEqual([call[0] for call in calls], ["ERP_VERSION"])
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        private = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("secret_custom", {row["name"] for row in private["apps"]})
        self.assertIn("1234abc", {row.get("commit") for row in private["apps"]})
        public = emit.call_args.args[0]
        self.assertNotIn("secret_custom", json.dumps(public))
        self.assertIn("CUSTOM_APP_01", json.dumps(public))
        self.assertEqual(public["site_inventory_status"], "UNVERIFIED_RUNTIME_SITE_PARAMETER_ABSENT")

    def test_version_rows_reject_unparenthesized_or_non_hex_commit(self) -> None:
        self.assertEqual(
            collector._parse_app_rows(b"erpnext 15.70.0 version-15 (1234abc)\n", "ERP_VERSION"),
            [
                {
                    "name": "erpnext",
                    "version": "15.70.0",
                    "branch": "version-15",
                    "commit": "1234abc",
                }
            ],
        )
        for invalid in (
            b"erpnext 15.70.0 version-15 1234abc\n",
            b"erpnext 15.70.0 version-15 (nothex)\n",
            b"erpnext 15.70.0 version-15 (1234abc) extra\n",
        ):
            with self.assertRaises(collector.FactCollectionError):
                collector._parse_app_rows(invalid, "ERP_VERSION")

    def test_discover_uses_exact_optional_site_operation(self) -> None:
        path = self.state_path()
        args = argparse.Namespace(
            expected_sha="b" * 40,
            ordinary_run_id="456",
            state=str(path),
        )
        calls: list[tuple[str, tuple[str, ...]]] = []

        def runner(operation: str, command: tuple[str, ...], limit: int) -> bytes:
            calls.append((operation, command))
            if operation == "ERP_VERSION":
                return b"erpnext 15.70.0\nfrappe 15.74.2\n"
            return b"erpnext 15.70.0\nfrappe 15.74.2\n"

        with patch.object(collector, "_preflight"), patch.dict(
            os.environ, {"NPI_P8_07F_SITE": "site-one"}, clear=True
        ), patch.object(collector, "_emit") as emit:
            collector._discover(args, runner)

        self.assertEqual([call[0] for call in calls], ["ERP_VERSION", "INSTALLED_APPS"])
        self.assertEqual(
            calls[1][1],
            ("bench", "--site", "site-one", "list-apps"),
        )
        self.assertEqual(emit.call_args.args[0]["site_inventory_status"], "VERIFIED")

    def test_tracked_paths_are_cached_and_deterministically_paged(self) -> None:
        path = self.state_path()
        collector._write_new_state(
            path,
            {
                "schema_version": 1,
                "task_id": collector.TASK_ID,
                "exact_sha": "c" * 40,
                "ordinary_run_id": "789",
                "apps": [
                    {
                        "label": "CUSTOM_APP_01",
                        "name": "custom_one",
                        "root": "apps/custom_one",
                    }
                ],
                "tracked_paths": {},
            },
        )
        args = argparse.Namespace(
            expected_sha="c" * 40,
            ordinary_run_id="789",
            state=str(path),
            label="CUSTOM_APP_01",
            operation="APP_TRACKED_PATHS",
            page=1,
            page_size=1,
        )
        calls: list[str] = []

        def runner(operation: str, command: tuple[str, ...], limit: int) -> bytes:
            calls.append(operation)
            return b"custom_one/hooks.py\x00custom_one/modules.txt\x00"

        with patch.object(collector, "_preflight"), patch.object(collector, "_emit") as emit:
            collector._app_operation(args, runner)
            collector._app_operation(args, runner)

        self.assertEqual(calls, ["APP_TRACKED_PATHS"])
        result = emit.call_args.args[0]["result"]
        self.assertEqual(result["path_entries"][0]["index"], 0)
        self.assertEqual(result["path_entries"][0]["category"], "HOOKS")
        self.assertNotIn("paths", result)
        self.assertNotIn("custom_one/hooks.py", json.dumps(result))
        self.assertFalse(emit.call_args.args[0]["result"]["remote_called"])

    def test_file_summary_requires_cached_path_and_never_returns_source_text(self) -> None:
        path = self.state_path()
        self.write_state(path)
        args = argparse.Namespace(
            expected_sha="d" * 40,
            ordinary_run_id="101",
            state=str(path),
            label="CUSTOM_APP_01",
            path_index=0,
        )

        def runner(operation: str, command: tuple[str, ...], limit: int) -> bytes:
            content = b"import frappe\n\n@frappe.whitelist()\ndef submit_item():\n    return True\n"
            if operation == "APP_HEAD_FILE_HASH":
                return (collector._git_blob_sha1(content) + "\n").encode()
            return content

        with patch.object(collector, "_preflight"), patch.object(collector, "_emit") as emit:
            collector._file_operation(args, runner)

        output = emit.call_args.args[0]
        self.assertEqual(
            output["git_object"],
            collector._git_blob_sha1(
                b"import frappe\n\n@frappe.whitelist()\ndef submit_item():\n    return True\n"
            ),
        )
        self.assertEqual(output["summary"]["format"], "python_ast")
        self.assertIn("submit_item", json.dumps(output))
        self.assertNotIn("return True", json.dumps(output))

    def test_current_file_reconstructs_dirty_tracked_source_without_emitting_raw_content_or_path(self) -> None:
        path = self.state_path()
        self.write_state(path)
        args = argparse.Namespace(
            expected_sha="d" * 40,
            ordinary_run_id="101",
            state=str(path),
            label="CUSTOM_APP_01",
            path_index=0,
        )
        head = b"import frappe\n\ndef old_name():\n    return 1\n"
        current = b"import frappe\n\ndef new_name():\n    return 1\n"
        head_object = collector._git_blob_sha1(head)
        current_object = collector._git_blob_sha1(current)
        diff = (
            f"diff --git a/custom_one/hooks.py b/custom_one/hooks.py\n"
            f"index {head_object}..{current_object} 100644\n"
            "--- a/custom_one/hooks.py\n"
            "+++ b/custom_one/hooks.py\n"
            "@@ -1,4 +1,4 @@\n"
            " import frappe\n"
            " \n"
            "-def old_name():\n"
            "+def new_name():\n"
            "     return 1\n"
        ).encode()

        def runner(operation: str, command: tuple[str, ...], limit: int) -> bytes:
            return {
                "APP_FILE_MODE": f"100644 {head_object} 0\tcustom_one/hooks.py\n".encode(),
                "APP_HEAD_FILE_HASH": f"{head_object}\n".encode(),
                "APP_FILE_READ": head,
                "APP_FILE_HASH": f"{current_object}\n".encode(),
                "APP_WORKTREE_DIFF": diff,
            }[operation]

        with patch.object(collector, "_preflight"), patch.object(collector, "_emit") as emit:
            collector._current_file_operation(args, runner)

        output = emit.call_args.args[0]
        rendered = json.dumps(output)
        self.assertEqual(output["worktree_state"], "DIRTY_TRACKED")
        self.assertEqual(output["summary"]["format"], "python_ast")
        self.assertIn("new_name", rendered)
        self.assertNotIn("old_name", rendered)
        self.assertNotIn("custom_one/hooks.py", rendered)
        self.assertNotIn("return 1", rendered)

    def test_current_file_clean_path_skips_diff(self) -> None:
        path = self.state_path()
        self.write_state(path)
        args = argparse.Namespace(
            expected_sha="d" * 40,
            ordinary_run_id="101",
            state=str(path),
            label="CUSTOM_APP_01",
            path_index=0,
        )
        head = b"def stable():\n    return True\n"
        object_id = collector._git_blob_sha1(head)
        calls: list[str] = []

        def runner(operation: str, command: tuple[str, ...], limit: int) -> bytes:
            calls.append(operation)
            return {
                "APP_FILE_MODE": f"100644 {object_id} 0\tcustom_one/hooks.py\n".encode(),
                "APP_HEAD_FILE_HASH": f"{object_id}\n".encode(),
                "APP_FILE_READ": head,
                "APP_FILE_HASH": f"{object_id}\n".encode(),
            }[operation]

        with patch.object(collector, "_preflight"), patch.object(collector, "_emit") as emit:
            collector._current_file_operation(args, runner)

        self.assertNotIn("APP_WORKTREE_DIFF", calls)
        self.assertEqual(emit.call_args.args[0]["worktree_state"], "CLEAN")

    def test_current_file_reconstruction_rejects_unsafe_diff_shapes(self) -> None:
        head = b"line\n"
        head_object = collector._git_blob_sha1(head)
        current_object = collector._git_blob_sha1(b"changed\n")
        base = (
            f"diff --git a/custom_one/hooks.py b/custom_one/hooks.py\n"
            f"index {head_object}..{current_object} 100644\n"
            "--- a/custom_one/hooks.py\n"
            "+++ b/custom_one/hooks.py\n"
            "@@ -1 +1 @@\n"
            "-line\n"
            "+changed\n"
        ).encode()
        self.assertEqual(
            collector._reconstruct_current_file(head, base, "custom_one/hooks.py"),
            b"changed\n",
        )
        unsafe = (
            base.replace(b"diff --git", b"diff --git", 1) +
            b"diff --git a/other.py b/other.py\n"
        )
        for candidate in (
            b"Binary files a/custom_one/hooks.py and b/custom_one/hooks.py differ\n",
            base.replace(b"--- a/custom_one/hooks.py", b"--- /dev/null"),
            base.replace(b"-line", b"-wrong"),
            unsafe,
        ):
            with self.assertRaises(collector.FactCollectionError):
                collector._reconstruct_current_file(head, candidate, "custom_one/hooks.py")
        with self.assertRaises(collector.FactCollectionError):
            collector._parse_file_mode(
                f"120000 {head_object} 0\tcustom_one/hooks.py\n".encode(),
                "custom_one/hooks.py",
            )

    def test_doctype_json_summary_hashes_multiline_or_sensitive_scalars(self) -> None:
        source = json.dumps(
            {
                "doctype": "DocType",
                "name": "Mold Repair",
                "module": "Mold Management",
                "fields": [
                    {
                        "fieldname": "status",
                        "fieldtype": "Select",
                        "options": "Draft\nIn Progress\nClosed",
                        "reqd": 1,
                    }
                ],
                "permissions": [{"role": "Mold Manager", "read": 1}],
            }
        )
        summary = collector._json_summary(source)
        rendered = json.dumps(summary)
        self.assertEqual(summary["name"], "Mold Repair")
        self.assertEqual(summary["fields"][0]["options"]["byte_count"], 24)
        self.assertNotIn("In Progress", rendered)

    def test_current_file_reconstruction_preserves_no_final_newline(self) -> None:
        head = b"before"
        current = b"after"
        head_object = collector._git_blob_sha1(head)
        current_object = collector._git_blob_sha1(current)
        diff = (
            f"diff --git a/custom_one/hooks.py b/custom_one/hooks.py\n"
            f"index {head_object}..{current_object} 100644\n"
            "--- a/custom_one/hooks.py\n"
            "+++ b/custom_one/hooks.py\n"
            "@@ -1 +1 @@\n"
            "-before\n"
            "\\ No newline at end of file\n"
            "+after\n"
            "\\ No newline at end of file\n"
        ).encode()
        self.assertEqual(
            collector._reconstruct_current_file(head, diff, "custom_one/hooks.py"),
            current,
        )

    def test_runtime_metadata_is_fixed_paged_and_hashes_script_content(self) -> None:
        path = self.state_path()
        self.write_state(path)
        args = argparse.Namespace(
            expected_sha="d" * 40,
            ordinary_run_id="101",
            state=str(path),
            family="SERVER_SCRIPTS",
        )
        row = {
            "name": "Approved API bridge",
            "script_type": "API",
            "reference_doctype": "Item",
            "doctype_event": None,
            "event_frequency": None,
            "api_method": "approved_bridge",
            "disabled": 0,
            "script": "frappe.get_doc('Item')",
            "modified": "2026-08-30 10:00:00.000000",
        }
        calls: list[tuple[str, tuple[str, ...]]] = []

        def runner(operation: str, command: tuple[str, ...], limit: int) -> bytes:
            calls.append((operation, command))
            return json.dumps([row]).encode()

        with patch.object(collector, "_preflight"), patch.dict(
            os.environ, {"NPI_P8_07F_SITE": "site-one"}, clear=True
        ), patch.object(collector, "_emit") as emit:
            collector._runtime_operation(args, runner)

        output = emit.call_args.args[0]
        rendered = json.dumps(output)
        self.assertEqual(len(calls), 1)
        self.assertEqual(output["row_count"], 1)
        self.assertEqual(output["rows"][0]["script"]["byte_count"], len(row["script"].encode()))
        self.assertNotIn(row["script"], rendered)
        self.assertNotIn("site-one", rendered)
        self.assertEqual(calls[0][0], "RUNTIME_SERVER_SCRIPTS")

    def test_client_script_v15_shape_hashes_script_without_nonexistent_type_field(self) -> None:
        fields = collector.RUNTIME_METADATA_SPECS["CLIENT_SCRIPTS"]["fields"]
        row = {field: None for field in fields}
        row.update(
            {
                "name": "Item validation",
                "dt": "Item",
                "view": "Form",
                "enabled": 1,
                "script": "frappe.ui.form.on('Item', {})",
                "modified": "2026-08-30 10:00:00.000000",
            }
        )
        rows, names = collector._parse_runtime_page(json.dumps([row]).encode(), "CLIENT_SCRIPTS")
        self.assertEqual(names, ["Item validation"])
        self.assertEqual(rows[0]["script"]["byte_count"], len(row["script"].encode()))
        self.assertNotIn(row["script"], json.dumps(rows))
        command = collector._runtime_command("CLIENT_SCRIPTS", "site-one", 20)
        kwargs = json.loads(command[-1])
        self.assertEqual(kwargs["limit_start"], 20)
        self.assertEqual(kwargs["limit_page_length"], 20)
        with self.assertRaises(collector.FactCollectionError):
            collector._runtime_command("CLIENT_SCRIPTS", "site-one", 21)

    def test_site_fact_parsers_are_exact_bounded_and_non_sensitive(self) -> None:
        locale = collector._parse_site_fact_output(
            "SYSTEM_LOCALE",
            {
                "SYSTEM_LOCALE": json.dumps(
                    {"language": "en", "time_zone": "Asia/Bangkok", "country": "Thailand"}
                ).encode()
            },
        )
        self.assertEqual(locale["language"], "en")
        counts = collector._parse_site_fact_output(
            "FILE_URL_SHAPES",
            {
                "FILE_URL_SHAPES_TOTAL": b"10",
                "FILE_URL_SHAPES_LOCAL_PUBLIC": b"4",
                "FILE_URL_SHAPES_LOCAL_PRIVATE": b"5",
                "FILE_URL_SHAPES_EXTERNAL_HTTP": b"1",
            },
        )
        self.assertEqual(counts["total"], 10)
        self.assertEqual(counts["external_http"], 1)
        with self.assertRaises(collector.FactCollectionError):
            collector._parse_site_fact_output(
                "SYSTEM_LOCALE",
                {"SYSTEM_LOCALE": b'{"language":"person@example.com"}'},
            )
        with self.assertRaises(collector.FactCollectionError):
            collector._parse_site_fact_output(
                "FILE_URL_SHAPES",
                {
                    "FILE_URL_SHAPES_TOTAL": b"1",
                    "FILE_URL_SHAPES_LOCAL_PUBLIC": b"1",
                    "FILE_URL_SHAPES_LOCAL_PRIVATE": b"1",
                    "FILE_URL_SHAPES_EXTERNAL_HTTP": b"0",
                },
            )

    def test_runtime_metadata_rejects_shape_and_sensitive_scalar_drift(self) -> None:
        fields = collector.RUNTIME_METADATA_SPECS["ROLES"]["fields"]
        valid = {field: None for field in fields}
        valid.update({"name": "Role A", "desk_access": 1, "is_custom": 1, "disabled": 0, "modified": "2026-08-30"})
        rows, names = collector._parse_runtime_page(json.dumps([valid]).encode(), "ROLES")
        self.assertEqual(names, ["Role A"])
        self.assertEqual(rows[0]["name"], "Role A")
        for invalid in (
            {**valid, "unexpected": 1},
            {**valid, "name": "person@example.com"},
        ):
            with self.assertRaises(collector.FactCollectionError):
                collector._parse_runtime_page(json.dumps([invalid]).encode(), "ROLES")
        descending = [{**valid, "name": "Role B"}, {**valid, "name": "Role A"}]
        descending_rows, descending_names = collector._parse_runtime_page(
            json.dumps(descending).encode(), "ROLES"
        )
        self.assertEqual(descending_names, ["Role B", "Role A"])
        self.assertEqual([row["name"] for row in descending_rows], descending_names)
        with self.assertRaises(collector.FactCollectionError):
            collector._parse_runtime_page(b"{}", "ROLES")

        custom_fields = collector.RUNTIME_METADATA_SPECS["CUSTOM_FIELDS"]["fields"]
        custom = {field: None for field in custom_fields}
        custom.update(
            {
                "name": "Project-custom_classification",
                "dt": "Project",
                "fieldname": "custom_classification",
                "fieldtype": "Select",
                "options": "One\nTwo\nThree",
                "reqd": 0,
                "read_only": 0,
                "unique": 0,
                "insert_after": "status",
                "modified": "2026-08-30",
            }
        )
        protected, _ = collector._parse_runtime_page(json.dumps([custom]).encode(), "CUSTOM_FIELDS")
        self.assertEqual(protected[0]["options"]["byte_count"], len(custom["options"].encode()))
        self.assertNotIn(custom["options"], json.dumps(protected))

    def test_runtime_metadata_stops_at_fixed_page_ceiling(self) -> None:
        path = self.state_path()
        self.write_state(path)
        args = argparse.Namespace(
            expected_sha="d" * 40,
            ordinary_run_id="101",
            state=str(path),
            family="ROLES",
        )
        fields = collector.RUNTIME_METADATA_SPECS["ROLES"]["fields"]

        def runner(operation: str, command: tuple[str, ...], limit: int) -> bytes:
            kwargs = json.loads(command[-1])
            start = kwargs["limit_start"]
            rows = []
            for index in range(collector.RUNTIME_PAGE_SIZE):
                row = {field: None for field in fields}
                row.update(
                    {
                        "name": f"Role {start + index:06d}",
                        "desk_access": 0,
                        "is_custom": 1,
                        "disabled": 0,
                        "modified": "2026-08-30",
                    }
                )
                rows.append(row)
            return json.dumps(rows).encode()

        with patch.object(collector, "_preflight"), patch.dict(
            os.environ, {"NPI_P8_07F_SITE": "site-one"}, clear=True
        ), self.assertRaisesRegex(collector.FactCollectionError, "pagination limit"):
            collector._runtime_operation(args, runner)

    def test_parent_metadata_reads_only_fixed_documents_and_projects_child_shape(self) -> None:
        path = self.state_path()
        self.write_state(path)
        state = collector._load_state(path, "d" * 40, "101")
        present_doctypes = list(collector.REQUIRED_ERPNEXT_DOCTYPES[:-1])
        state["runtime_names"] = {"DOCTYPES": present_doctypes}
        collector._replace_state(path, state)
        args = argparse.Namespace(
            expected_sha="d" * 40,
            ordinary_run_id="101",
            state=str(path),
            family="DOCFIELDS",
        )
        calls: list[tuple[str, tuple[str, ...]]] = []

        def runner(operation: str, command: tuple[str, ...], limit: int) -> bytes:
            calls.append((operation, command))
            kwargs = json.loads(command[-1])
            parent = kwargs["name"]
            return json.dumps(
                {
                    "doctype": "DocType",
                    "name": parent,
                    "modified_by": "private@example.com",
                    "fields": [
                        {
                            "name": f"{parent}-status",
                            "parent": parent,
                            "fieldname": "status",
                            "fieldtype": "Data",
                            "options": None,
                            "reqd": 0,
                            "read_only": 0,
                            "unique": 0,
                            "hidden": 0,
                            "permlevel": 0,
                            "idx": 1,
                            "modified": None,
                            "default": "do-not-record",
                        }
                    ],
                }
            ).encode()

        with patch.object(collector, "_preflight"), patch.dict(
            os.environ, {"NPI_P8_07F_SITE": "site-one"}, clear=True
        ), patch.object(collector, "_emit") as emit:
            collector._parent_metadata_operation(args, runner)

        output = emit.call_args.args[0]
        rendered = json.dumps(output)
        self.assertEqual(len(calls), len(present_doctypes))
        self.assertEqual(output["parent_count"], len(present_doctypes))
        self.assertEqual(output["row_count"], len(present_doctypes))
        self.assertEqual(
            output["missing_parent_names"],
            [collector.REQUIRED_ERPNEXT_DOCTYPES[-1]],
        )
        self.assertNotIn("private@example.com", rendered)
        self.assertNotIn("do-not-record", rendered)
        self.assertTrue(all(call[0] == "RUNTIME_DOCFIELDS_PARENT" for call in calls))

    def test_dynamic_parent_metadata_requires_prior_fixed_parent_family(self) -> None:
        path = self.state_path()
        self.write_state(path)
        args = argparse.Namespace(
            expected_sha="d" * 40,
            ordinary_run_id="101",
            state=str(path),
            family="WORKFLOW_STATES",
        )
        with patch.object(collector, "_preflight"), patch.dict(
            os.environ, {"NPI_P8_07F_SITE": "site-one"}, clear=True
        ), self.assertRaisesRegex(collector.FactCollectionError, "parent family first"):
            collector._parent_metadata_operation(args, lambda *unused: b"")

        state = collector._load_state(path, "d" * 40, "101")
        state["runtime_names"] = {"DOCTYPES": ["User"]}
        collector._replace_state(path, state)
        args.family = "DOCFIELDS"
        with patch.object(collector, "_preflight"), patch.dict(
            os.environ, {"NPI_P8_07F_SITE": "site-one"}, clear=True
        ), self.assertRaisesRegex(collector.FactCollectionError, "non-allowlisted DocType"):
            collector._parent_metadata_operation(args, lambda *unused: b"")

    def test_sensitive_path_or_content_fails_closed(self) -> None:
        self.assertTrue(collector._path_is_sensitive("sites/site_config.json"))
        self.assertTrue(collector._path_is_sensitive("private/files/a.txt"))
        with self.assertRaisesRegex(collector.FactCollectionError, "sensitive"):
            collector._source_summary(
                "custom_one/hooks.py",
                b'api_secret = "do-not-record"\n',
            )
        doctype_summary = collector._source_summary(
            "custom_one/doctype/example/example.json",
            b'{"doctype":"DocType","name":"Example","password":"do-not-record","fields":[]}',
        )
        self.assertEqual(doctype_summary["name"], "Example")
        self.assertNotIn("do-not-record", json.dumps(doctype_summary))

    def test_p9_change_metadata_commands_are_fixed_scoped_and_read_only(self) -> None:
        for family, spec in collector.P9_CHANGE_METADATA_SPECS.items():
            with self.subTest(family=family):
                if family in collector.P9_CHANGE_PARENT_FAMILIES:
                    with self.assertRaisesRegex(
                        collector.FactCollectionError,
                        "fixed parent document",
                    ):
                        collector._p9_change_metadata_command(
                            family,
                            "site-one",
                            0,
                        )
                    continue
                command = collector._p9_change_metadata_command(
                    family,
                    "site-one",
                    0,
                )
                self.assertEqual(
                    command[:5],
                    (
                        "bench",
                        "--site",
                        "site-one",
                        "execute",
                        "frappe.client.get_list",
                    ),
                )
                kwargs = json.loads(command[6])
                self.assertEqual(kwargs["doctype"], spec["doctype"])
                self.assertEqual(kwargs["fields"], list(spec["fields"]))
                self.assertEqual(
                    kwargs["filters"],
                    json.loads(json.dumps([list(row) for row in spec["filters"]])),
                )
                self.assertEqual(kwargs["order_by"], "name asc")
                self.assertEqual(kwargs["limit_start"], 0)
                self.assertEqual(
                    kwargs["limit_page_length"],
                    collector.P9_CHANGE_PAGE_SIZE,
                )
                rendered = " ".join(command).lower()
                self.assertNotIn("sql", rendered)
                self.assertNotIn("console", rendered)
                self.assertNotIn("*", rendered)
        with self.assertRaises(collector.FactCollectionError):
            collector._p9_change_metadata_command("CALLER_SELECTED", "site-one", 0)
        with self.assertRaises(collector.FactCollectionError):
            collector._p9_change_metadata_command(
                "CHANGE_DOCTYPES",
                "site-one",
                1,
            )

    def test_p9_change_metadata_operation_hashes_sensitive_values_and_stays_scoped(self) -> None:
        args = argparse.Namespace(expected_sha="d" * 40, ordinary_run_id="101")

        def row(family: str, **updates: object) -> dict[str, object]:
            value = {
                field: None
                for field in collector.P9_CHANGE_METADATA_SPECS[family]["fields"]
            }
            value.update(updates)
            return value

        raw_script = "frappe.get_doc('Engineering Change Request')"
        raw_options = "Engineering Change Request\n" * 12
        raw_condition = "doc.workflow_state == 'Open'"
        rows = {
            "CHANGE_DOCTYPES": [
                row(
                    "CHANGE_DOCTYPES",
                    name="Engineering Change Request",
                    module="Manufacturing",
                    custom=0,
                    istable=0,
                    issingle=0,
                    autoname="naming_series:",
                    track_changes=1,
                    is_submittable=1,
                    modified="2026-08-30 10:00:00.000000",
                )
            ],
            "CHANGE_DOCFIELDS": [
                row(
                    "CHANGE_DOCFIELDS",
                    name="Engineering Change Request-reason",
                    parent="Engineering Change Request",
                    fieldname="reason",
                    fieldtype="Link",
                    options=raw_options,
                    reqd=1,
                    read_only=0,
                    unique=0,
                    hidden=0,
                    permlevel=0,
                    idx=1,
                    modified="2026-08-30 10:00:00.000000",
                )
            ],
            "CHANGE_DOCPERMS": [
                row(
                    "CHANGE_DOCPERMS",
                    name="Engineering Change Request-Engineer-0",
                    parent="Engineering Change Request",
                    role="Engineer",
                    permlevel=0,
                    read=1,
                    write=1,
                    create=1,
                    delete=0,
                    submit=1,
                    cancel=0,
                    amend=0,
                    report=1,
                    export=0,
                    share=0,
                    print=1,
                    email=0,
                    if_owner=0,
                    modified="2026-08-30 10:00:00.000000",
                )
            ],
            "CHANGE_WORKFLOWS": [
                row(
                    "CHANGE_WORKFLOWS",
                    name="Engineering Change Approval",
                    document_type="Engineering Change Request",
                    is_active=1,
                    workflow_state_field="workflow_state",
                    modified="2026-08-30 10:00:00.000000",
                )
            ],
            "CHANGE_SERVER_SCRIPTS": [
                row(
                    "CHANGE_SERVER_SCRIPTS",
                    name="Engineering Change Guard",
                    script_type="DocType Event",
                    reference_doctype="Engineering Change Request",
                    doctype_event="Before Save",
                    event_frequency=None,
                    api_method=None,
                    disabled=0,
                    script=raw_script,
                    modified="2026-08-30 10:00:00.000000",
                )
            ],
        }
        calls: list[tuple[str, tuple[str, ...]]] = []

        def runner(operation: str, command: tuple[str, ...], limit: int) -> bytes:
            calls.append((operation, command))
            if operation in {
                "CHANGE_DOCFIELDS_PARENT",
                "CHANGE_DOCPERMS_PARENT",
            }:
                return json.dumps(
                    {
                        "doctype": "DocType",
                        "name": "Engineering Change Request",
                        "fields": rows["CHANGE_DOCFIELDS"],
                        "permissions": rows["CHANGE_DOCPERMS"],
                        "modified_by": "private@example.com",
                    }
                ).encode()
            if operation == "CHANGE_WORKFLOW_DOCUMENT":
                return json.dumps(
                    {
                        "doctype": "Workflow",
                        "name": "Engineering Change Approval",
                        "states": [
                            {
                                "name": "state-row-1",
                                "parent": "Engineering Change Approval",
                                "state": "Open",
                                "allow_edit": "Engineer",
                                "doc_status": "0",
                                "is_optional_state": 0,
                                "modified": "2026-08-30 10:00:00.000000",
                                "modified_by": "private@example.com",
                            }
                        ],
                        "transitions": [
                            {
                                "name": "transition-row-1",
                                "parent": "Engineering Change Approval",
                                "state": "Open",
                                "action": "Approve",
                                "next_state": "Approved",
                                "allowed": "Engineer",
                                "allow_self_approval": 0,
                                "condition": raw_condition,
                                "modified": "2026-08-30 10:00:00.000000",
                                "modified_by": "private@example.com",
                            }
                        ],
                    }
                ).encode()
            return json.dumps(rows.get(operation, [])).encode()

        with patch.object(collector, "_p9_change_preflight"), patch.dict(
            os.environ,
            {"NPI_P8_07F_SITE": "site-one"},
            clear=True,
        ), patch.object(collector, "_emit") as emit:
            collector._p9_change_metadata_operation(args, runner)

        output = emit.call_args.args[0]
        rendered = json.dumps(output)
        self.assertEqual(output["task_id"], "P9-01")
        self.assertEqual(output["operation"], "P9_CHANGE_DECLARATIVE_METADATA")
        self.assertEqual(
            output["result"]["present_doctype_names"],
            ["Engineering Change Request"],
        )
        self.assertEqual(
            output["result"]["missing_doctype_names"],
            ["Engineering Change Notice", "Engineering Change Order"],
        )
        self.assertNotIn(raw_script, rendered)
        self.assertNotIn(raw_options, rendered)
        self.assertNotIn(raw_condition, rendered)
        self.assertNotIn("private@example.com", rendered)
        self.assertNotIn("site-one", rendered)
        self.assertIn(collector._checksum(raw_script.encode()), rendered)
        self.assertIn(collector._checksum(raw_condition.encode()), rendered)
        self.assertEqual(
            [operation for operation, _ in calls].count("CHANGE_WORKFLOW_DOCUMENT"),
            1,
        )
        self.assertEqual(
            [operation for operation, _ in calls].count("CHANGE_DOCFIELDS_PARENT"),
            1,
        )
        self.assertEqual(
            [operation for operation, _ in calls].count("CHANGE_DOCPERMS_PARENT"),
            1,
        )
        self.assertFalse(
            any(
                json.loads(command[6]).get("doctype") in {"DocField", "DocPerm"}
                for _, command in calls
                if len(command) > 6 and command[4] == "frappe.client.get_list"
            )
        )
        for _, command in calls:
            self.assertEqual(command[0], "bench")
            self.assertNotIn("sql", " ".join(command).lower())
            self.assertNotIn("console", " ".join(command).lower())

    def test_p9_change_metadata_rejects_any_row_outside_exact_scope(self) -> None:
        args = argparse.Namespace(expected_sha="d" * 40, ordinary_run_id="101")
        fields = collector.P9_CHANGE_METADATA_SPECS["CHANGE_CUSTOM_FIELDS"]["fields"]
        escaped = {field: None for field in fields}
        escaped.update(
            {
                "name": "Item-extra",
                "dt": "Item",
                "fieldname": "extra",
                "fieldtype": "Data",
            }
        )

        def runner(operation: str, command: tuple[str, ...], limit: int) -> bytes:
            if operation == "CHANGE_CUSTOM_FIELDS":
                return json.dumps([escaped]).encode()
            return b"[]"

        with patch.object(collector, "_p9_change_preflight"), patch.dict(
            os.environ,
            {"NPI_P8_07F_SITE": "site-one"},
            clear=True,
        ), self.assertRaisesRegex(
            collector.FactCollectionError,
            "escaped the fixed DocType scope",
        ):
            collector._p9_change_metadata_operation(args, runner)

    def test_p9_change_preflight_requires_exact_activation_and_paths(self) -> None:
        manifest = {
            "task_id": "P9-01",
            "status": "IN_PROGRESS_FACT_DELTA_COLLECTOR",
            "allowed_paths": [
                "scripts/collect_erpnext_production_facts.py",
                "tests/test_erpnext_production_fact_collector.py",
            ],
        }
        path = self.write_manifest(manifest)

        def git(*args: str) -> str:
            return "d" * 40 if args == ("rev-parse", "HEAD") else ""

        with patch.object(collector, "MANIFEST", path), patch.object(
            collector,
            "_git",
            side_effect=git,
        ):
            self.assertEqual(
                collector._p9_change_preflight("d" * 40),
                manifest,
            )

        for key, bad_value in (
            ("task_id", "P8-07F-FACTS"),
            ("status", "IN_PROGRESS_FACT_DELTA_GOVERNANCE"),
            ("allowed_paths", ["scripts/collect_erpnext_production_facts.py"]),
        ):
            invalid = {**manifest, key: bad_value}
            invalid_path = self.write_manifest(invalid)
            with self.subTest(key=key), patch.object(
                collector,
                "MANIFEST",
                invalid_path,
            ), patch.object(collector, "_git", side_effect=git), self.assertRaises(
                collector.FactCollectionError
            ):
                collector._p9_change_preflight("d" * 40)

    def test_status_rejects_untracked_and_paths_reject_nondeterminism(self) -> None:
        with self.assertRaises(collector.FactCollectionError):
            collector._parse_status(b"?? unknown.txt\n")
        with self.assertRaises(collector.FactCollectionError):
            collector._parse_paths(b"z.py\x00a.py\x00")
        self.assertEqual(
            collector._parse_paths(b"app/a file.py\x00app/name (copy).json\x00"),
            ["app/a file.py", "app/name (copy).json"],
        )
        for invalid in (
            b"app/path.py\n",
            b"app/../path.py\x00",
            b"app/bad\npath.py\x00",
        ):
            with self.assertRaises(collector.FactCollectionError):
                collector._parse_paths(invalid)

    def test_self_check_does_not_contact_ssh(self) -> None:
        with patch.object(collector.subprocess, "run") as run, patch.object(
            collector, "_emit"
        ) as emit:
            self.assertEqual(collector.main(["self-check"]), 0)
        run.assert_not_called()
        self.assertFalse(emit.call_args.args[0]["remote_contact"])
        self.assertEqual(emit.call_args.args[0]["bench_root"], "frappe-bench")
        self.assertEqual(len(emit.call_args.args[0]["allowlisted_operations"]), 11)
        self.assertEqual(
            emit.call_args.args[0]["runtime_metadata_families"],
            list(collector.RUNTIME_METADATA_SPECS),
        )
        self.assertEqual(emit.call_args.args[0]["p9_change_task_id"], "P9-01")
        self.assertEqual(
            emit.call_args.args[0]["p9_change_doctypes"],
            list(collector.P9_CHANGE_DOCTYPES),
        )
        self.assertEqual(
            emit.call_args.args[0]["p9_change_metadata_families"],
            list(collector.P9_CHANGE_METADATA_SPECS),
        )


if __name__ == "__main__":
    unittest.main()
