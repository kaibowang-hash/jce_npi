from __future__ import annotations

import ast
import base64
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD_PATH = ROOT / "scripts" / "verify_local_frappe_site.py"

spec = importlib.util.spec_from_file_location("verify_local_frappe_site", GUARD_PATH)
assert spec is not None and spec.loader is not None
guard = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = guard
spec.loader.exec_module(guard)


def controlled_site_config() -> dict[str, object]:
    return {
        "db_host": "127.0.0.1",
        "db_name": "npi_one_runtime",
        "db_password": "synthetic-secret-value",
        "db_port": 3306,
        "db_type": "mariadb",
        "developer_mode": 1,
        "encryption_key": base64.urlsafe_b64encode(b"k" * 32).decode("ascii"),
        "npi_deployment_environment": "sandbox",
        "npi_runtime_disposable_marker": "npi-one-local-runtime-disposable-v1",
        "npi_tenant_id": "runtime-tenant",
    }


class LocalFrappeRuntimeSafetyTest(unittest.TestCase):
    def test_controlled_database_configuration_is_exact_and_redacted(self) -> None:
        database = guard.parse_controlled_database(
            controlled_site_config(),
            {"redis_cache": "redis://127.0.0.1:6379/0"},
            require_runtime_config=True,
        )

        self.assertEqual(database.host, "127.0.0.1")
        self.assertEqual(database.port, 3306)
        self.assertEqual(database.name, "npi_one_runtime")
        self.assertEqual(database.user, "npi_one_runtime")
        self.assertNotIn("synthetic-secret-value", repr(database))

    def test_database_configuration_rejects_every_identity_drift(self) -> None:
        drift_cases = {
            "db_host": "localhost",
            "db_port": "3306",
            "db_name": "another_database",
            "db_user": "another_user",
            "db_type": "postgres",
            "db_socket": "/var/run/mysqld/mysqld.sock",
            "extra_config": "unsafe.dynamic.config",
        }
        for field, value in drift_cases.items():
            with self.subTest(field=field):
                site_config = controlled_site_config()
                site_config[field] = value
                with self.assertRaises(guard.SiteSafetyError):
                    guard.parse_controlled_database(
                        site_config,
                        {},
                        require_runtime_config=True,
                    )

    def test_database_configuration_rejects_common_and_runtime_drift(self) -> None:
        with self.assertRaises(guard.SiteSafetyError):
            guard.parse_controlled_database(
                controlled_site_config(),
                {"db_host": "127.0.0.1"},
                require_runtime_config=True,
            )

        for field, value in (
            ("developer_mode", 0),
            ("npi_deployment_environment", "production"),
            ("npi_runtime_disposable_marker", "another-marker"),
            ("npi_tenant_id", "another-tenant"),
        ):
            with self.subTest(field=field):
                site_config = controlled_site_config()
                site_config[field] = value
                with self.assertRaises(guard.SiteSafetyError):
                    guard.parse_controlled_database(
                        site_config,
                        {},
                        require_runtime_config=True,
                    )

        for value in (
            None,
            "",
            base64.urlsafe_b64encode(b"k" * 31).decode("ascii"),
            base64.b64encode(b"\xfb" * 32).decode("ascii"),
        ):
            with self.subTest(encryption_key=value):
                site_config = controlled_site_config()
                site_config["encryption_key"] = value
                with self.assertRaises(guard.SiteSafetyError):
                    guard.parse_controlled_database(
                        site_config,
                        {},
                        require_runtime_config=True,
                    )

    def test_database_environment_overrides_fail_closed(self) -> None:
        guard.validate_database_environment({"FRAPPE_DB_HOST": ""})
        for name in guard.DATABASE_OVERRIDE_ENVIRONMENT:
            with self.subTest(name=name):
                with self.assertRaises(guard.SiteSafetyError):
                    guard.validate_database_environment({name: "unexpected"})

    def test_live_database_and_current_user_must_match_exactly(self) -> None:
        for current_user in ("npi_one_runtime@%", "npi_one_runtime@localhost"):
            with self.subTest(current_user=current_user):
                guard.parse_live_identity_row(
                    ("npi_one_runtime", current_user, 3306),
                    expected_database="npi_one_runtime",
                    expected_user="npi_one_runtime",
                )

        invalid_rows = (
            ("another_database", "npi_one_runtime@%", 3306),
            ("npi_one_runtime", "another_user@%", 3306),
            ("npi_one_runtime", "npi_one_runtime", 3306),
            ("npi_one_runtime", "npi_one_runtime@%", "3306"),
            ("npi_one_runtime", "npi_one_runtime@%", 3307),
        )
        for row in invalid_rows:
            with self.subTest(row=row):
                with self.assertRaises(guard.SiteSafetyError):
                    guard.parse_live_identity_row(
                        row,
                        expected_database="npi_one_runtime",
                        expected_user="npi_one_runtime",
                    )

    def test_root_probe_requires_no_selected_database_and_exact_root_user(self) -> None:
        guard.parse_live_identity_row(
            (None, "root@%", 3306),
            expected_database=None,
            expected_user="root",
        )
        for row in (
            ("npi_one_runtime", "root@%", 3306),
            (None, "not-root@%", 3306),
        ):
            with self.subTest(row=row):
                with self.assertRaises(guard.SiteSafetyError):
                    guard.parse_live_identity_row(
                        row,
                        expected_database=None,
                        expected_user="root",
                    )

    def test_live_probe_executes_read_only_statements_only(self) -> None:
        source = GUARD_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        statements: list[str] = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "execute"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                statements.append(node.args[0].value)
        self.assertEqual(len(statements), 2)
        self.assertTrue(all(statement.startswith("SELECT ") for statement in statements))

    def test_site_init_and_runtime_scripts_guard_before_mutations(self) -> None:
        initializer = (ROOT / "scripts" / "init-npi-site.sh").read_text(
            encoding="utf-8"
        )
        runtime = (ROOT / "scripts" / "verify-frappe-runtime.sh").read_text(
            encoding="utf-8"
        )
        verifier = (ROOT / "scripts" / "verify_frappe_runtime.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('database_name="npi_one_runtime"', initializer)
        self.assertIn('--db-name "${database_name}"', initializer)
        self.assertIn('--db-type "${database_type}"', initializer)
        self.assertIn('--db-root-username "${database_root_user}"', initializer)
        self.assertIn('--mariadb-user-host-login-scope "%"', initializer)
        self.assertLess(
            initializer.index("run_site_guard database"),
            initializer.index('set-config npi_tenant_id "${tenant_id}"'),
        )
        self.assertIn(
            'set-config npi_deployment_environment sandbox', initializer
        )
        for marker in (
            "base64.urlsafe_b64encode(secrets.token_bytes(32))",
            'set-config -- encryption_key "${runtime_encryption_key}"',
            "unset runtime_encryption_key",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, initializer)
        self.assertLess(
            initializer.index("run_site_guard database"),
            initializer.index(
                'set-config -- encryption_key "${runtime_encryption_key}"'
            ),
        )
        self.assertLess(
            initializer.index(
                'set-config -- encryption_key "${runtime_encryption_key}"'
            ),
            initializer.index('set-config npi_tenant_id "${tenant_id}"'),
        )
        self.assertNotIn(
            'set-config encryption_key "${runtime_encryption_key}"', initializer
        )
        final_live_guard = initializer.rindex("run_site_guard live")
        self.assertGreater(final_live_guard, initializer.index("install-app"))
        self.assertLess(
            initializer.index(
                "# Re-prove the exact live target immediately before password"
            ),
            initializer.index("set-admin-password"),
        )
        self.assertLess(
            initializer.index(
                "# Re-prove the exact live target immediately before password"
            ),
            initializer.index('run_bench --site "${site_name}" migrate'),
        )

        self.assertLess(
            runtime.index("\nrun_site_guard\n"),
            runtime.index('bench --site "${site_name}" serve'),
        )
        self.assertIn('"--mode",\n                "live"', verifier)
        self.assertLess(
            verifier.index("validate_runtime_environment()"),
            verifier.index("return normalized_base_url"),
        )


if __name__ == "__main__":
    unittest.main()
