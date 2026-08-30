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
            collector._remote_command(
                "APP_FILE_READ",
                root="apps/custom_one",
                path="custom_one/hooks.py",
            ),
            ("git", "-C", "apps/custom_one", "show", "HEAD:custom_one/hooks.py"),
        )
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
            return b"custom_one/hooks.py\ncustom_one/modules.txt\n"

        with patch.object(collector, "_preflight"), patch.object(collector, "_emit") as emit:
            collector._app_operation(args, runner)
            collector._app_operation(args, runner)

        self.assertEqual(calls, ["APP_TRACKED_PATHS"])
        self.assertEqual(emit.call_args.args[0]["result"]["paths"], ["custom_one/hooks.py"])
        self.assertFalse(emit.call_args.args[0]["result"]["remote_called"])

    def test_file_summary_requires_cached_path_and_never_returns_source_text(self) -> None:
        path = self.state_path()
        collector._write_new_state(
            path,
            {
                "schema_version": 1,
                "task_id": collector.TASK_ID,
                "exact_sha": "d" * 40,
                "ordinary_run_id": "101",
                "apps": [
                    {
                        "label": "CUSTOM_APP_01",
                        "name": "custom_one",
                        "root": "apps/custom_one",
                    }
                ],
                "tracked_paths": {"CUSTOM_APP_01": ["custom_one/hooks.py"]},
            },
        )
        args = argparse.Namespace(
            expected_sha="d" * 40,
            ordinary_run_id="101",
            state=str(path),
            label="CUSTOM_APP_01",
            path="custom_one/hooks.py",
        )

        def runner(operation: str, command: tuple[str, ...], limit: int) -> bytes:
            if operation == "APP_FILE_HASH":
                return ("e" * 40 + "\n").encode()
            return b"import frappe\n\n@frappe.whitelist()\ndef submit_item():\n    return True\n"

        with patch.object(collector, "_preflight"), patch.object(collector, "_emit") as emit:
            collector._file_operation(args, runner)

        output = emit.call_args.args[0]
        self.assertEqual(output["git_object"], "e" * 40)
        self.assertEqual(output["summary"]["format"], "python_ast")
        self.assertIn("submit_item", json.dumps(output))
        self.assertNotIn("return True", json.dumps(output))

    def test_sensitive_path_or_content_fails_closed(self) -> None:
        self.assertTrue(collector._path_is_sensitive("sites/site_config.json"))
        self.assertTrue(collector._path_is_sensitive("private/files/a.txt"))
        with self.assertRaisesRegex(collector.FactCollectionError, "sensitive"):
            collector._source_summary(
                "custom_one/hooks.py",
                b'api_secret = "do-not-record"\n',
            )

    def test_status_rejects_untracked_and_paths_reject_nondeterminism(self) -> None:
        with self.assertRaises(collector.FactCollectionError):
            collector._parse_status(b"?? unknown.txt\n")
        with self.assertRaises(collector.FactCollectionError):
            collector._parse_paths(b"z.py\na.py\n")

    def test_self_check_does_not_contact_ssh(self) -> None:
        with patch.object(collector.subprocess, "run") as run, patch.object(
            collector, "_emit"
        ) as emit:
            self.assertEqual(collector.main(["self-check"]), 0)
        run.assert_not_called()
        self.assertFalse(emit.call_args.args[0]["remote_contact"])
        self.assertEqual(emit.call_args.args[0]["bench_root"], "frappe-bench")
        self.assertEqual(len(emit.call_args.args[0]["allowlisted_operations"]), 7)


if __name__ == "__main__":
    unittest.main()
