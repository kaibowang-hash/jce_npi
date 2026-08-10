from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
BENCH_PATH = ROOT / "tmp" / "frappe-bench"
SITES_PATH = BENCH_PATH / "sites"
SITE_NAME = "npi.localhost"
SITE_PATH = SITES_PATH / SITE_NAME

DATABASE_HOST = "127.0.0.1"
DATABASE_PORT = 3306
DATABASE_NAME = "npi_one_runtime"
DATABASE_USER = DATABASE_NAME
DATABASE_TYPE = "mariadb"
TENANT_ID = "runtime-tenant"
RUNTIME_MARKER = "npi-one-local-runtime-disposable-v1"

DATABASE_OVERRIDE_ENVIRONMENT = (
    "FRAPPE_DB_HOST",
    "FRAPPE_DB_PORT",
    "FRAPPE_DB_SOCKET",
    "FRAPPE_DB_TYPE",
)
COMMON_DATABASE_KEYS = {
    "db_host",
    "db_name",
    "db_password",
    "db_port",
    "db_socket",
    "db_type",
    "extra_config",
}


class SiteSafetyError(RuntimeError):
    pass


@dataclass(frozen=True)
class ControlledDatabase:
    host: str
    port: int
    name: str
    user: str
    password: str = field(repr=False)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SiteSafetyError(message)


def _read_json_object(path: Path, description: str) -> dict[str, Any]:
    require(
        path.is_file() and not path.is_symlink(),
        f"{description} is unavailable or is not a physical file",
    )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise SiteSafetyError(f"{description} is invalid") from None
    require(isinstance(payload, dict), f"{description} must be a JSON object")
    return payload


def validate_database_environment(environment: Mapping[str, str]) -> None:
    configured_overrides = [
        name for name in DATABASE_OVERRIDE_ENVIRONMENT if environment.get(name)
    ]
    require(
        not configured_overrides,
        "Frappe database environment overrides are forbidden for the local runtime",
    )


def has_canonical_encryption_key(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        encoded = value.encode("ascii")
        decoded = base64.b64decode(encoded, altchars=b"-_", validate=True)
    except (binascii.Error, UnicodeError, ValueError):
        return False
    return len(decoded) == 32 and base64.urlsafe_b64encode(decoded) == encoded


def parse_controlled_database(
    site_config: Mapping[str, Any],
    common_config: Mapping[str, Any],
    *,
    require_runtime_config: bool,
) -> ControlledDatabase:
    require(
        not COMMON_DATABASE_KEYS.intersection(common_config),
        "Common Site configuration must not override the local runtime database",
    )
    require(
        site_config.get("db_type") == DATABASE_TYPE,
        "Controlled local Frappe database type drifted",
    )
    require(
        site_config.get("db_host") == DATABASE_HOST,
        "Controlled local Frappe database host drifted",
    )
    port = site_config.get("db_port")
    require(
        isinstance(port, int) and not isinstance(port, bool) and port == DATABASE_PORT,
        "Controlled local Frappe database port drifted",
    )
    require(
        site_config.get("db_name") == DATABASE_NAME,
        "Controlled local Frappe database name drifted",
    )
    require(
        site_config.get("db_user", DATABASE_USER) == DATABASE_USER,
        "Controlled local Frappe database user drifted",
    )
    require(
        site_config.get("db_socket") in {None, ""},
        "Controlled local Frappe runtime must use the fixed TCP endpoint",
    )
    require(
        "extra_config" not in site_config,
        "Dynamic Frappe Site configuration is forbidden for the local runtime",
    )
    password = site_config.get("db_password")
    require(
        isinstance(password, str)
        and len(password) >= 16
        and not {"\x00", "\n", "\r"}.intersection(password),
        "Controlled local Frappe database credential is unavailable",
    )
    if require_runtime_config:
        require(
            site_config.get("developer_mode") == 1
            and site_config.get("npi_tenant_id") == TENANT_ID
            and site_config.get("npi_runtime_disposable_marker") == RUNTIME_MARKER,
            "Controlled local Frappe runtime safety configuration drifted",
        )
        require(
            has_canonical_encryption_key(site_config.get("encryption_key")),
            "Controlled local Frappe Site encryption key is unavailable",
        )
    return ControlledDatabase(
        host=DATABASE_HOST,
        port=DATABASE_PORT,
        name=DATABASE_NAME,
        user=DATABASE_USER,
        password=password,
    )


def load_controlled_database(
    *,
    require_runtime_config: bool,
    environment: Mapping[str, str] | None = None,
) -> ControlledDatabase:
    validate_database_environment(os.environ if environment is None else environment)
    require(
        not (ROOT / "tmp").is_symlink()
        and BENCH_PATH.is_dir()
        and not BENCH_PATH.is_symlink()
        and BENCH_PATH.resolve(strict=True) == BENCH_PATH,
        "Controlled local Frappe Bench must be the fixed physical repository path",
    )
    require(
        SITES_PATH.is_dir()
        and not SITES_PATH.is_symlink()
        and SITES_PATH.resolve(strict=True) == SITES_PATH,
        "Controlled local Frappe sites path must be physical",
    )
    require(
        SITE_PATH.is_dir()
        and not SITE_PATH.is_symlink()
        and SITE_PATH.resolve(strict=True) == SITE_PATH,
        "Controlled local Frappe Site must be the fixed physical repository path",
    )
    common_config = _read_json_object(
        SITES_PATH / "common_site_config.json",
        "Common Site configuration",
    )
    site_config = _read_json_object(
        SITE_PATH / "site_config.json",
        "Runtime Site configuration",
    )
    return parse_controlled_database(
        site_config,
        common_config,
        require_runtime_config=require_runtime_config,
    )


def parse_live_identity_row(
    row: Sequence[Any],
    *,
    expected_database: str | None,
    expected_user: str,
) -> None:
    require(len(row) == 3, "Live database identity response drifted")
    live_database, live_current_user, live_port = row
    if expected_database is None:
        require(
            live_database in {None, ""},
            "Local database server probe unexpectedly selected a database",
        )
    else:
        require(
            live_database == expected_database,
            "Live Frappe connection resolved to an unexpected database",
        )
    require(
        isinstance(live_current_user, str) and "@" in live_current_user,
        "Live MariaDB current-user identity is invalid",
    )
    live_user, live_host_scope = live_current_user.split("@", 1)
    require(
        live_user == expected_user and bool(live_host_scope),
        "Live MariaDB connection resolved to an unexpected database user",
    )
    require(
        isinstance(live_port, int)
        and not isinstance(live_port, bool)
        and live_port == DATABASE_PORT,
        "Live MariaDB connection resolved to an unexpected server port",
    )


def _open_connection(
    *,
    user: str,
    password: str,
    database: str | None,
) -> Any:
    try:
        import pymysql
    except ImportError:
        raise SiteSafetyError(
            "Pinned Bench database driver is unavailable for the live identity probe"
        ) from None
    try:
        return pymysql.connect(
            host=DATABASE_HOST,
            port=DATABASE_PORT,
            user=user,
            password=password,
            database=database,
            charset="utf8mb4",
            connect_timeout=5,
            read_timeout=5,
            write_timeout=5,
            autocommit=False,
        )
    except Exception:
        raise SiteSafetyError(
            "Controlled local MariaDB connection could not be established"
        ) from None


def _query_live_identity(connection: Any) -> tuple[Any, Any, Any]:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT DATABASE(), CURRENT_USER(), @@port")
            row = cursor.fetchone()
    except Exception:
        raise SiteSafetyError("Live MariaDB identity query failed") from None
    require(
        isinstance(row, (tuple, list)),
        "Live database identity response is invalid",
    )
    return tuple(row)


def verify_live_site_database(*, require_runtime_config: bool) -> None:
    database = load_controlled_database(
        require_runtime_config=require_runtime_config,
    )
    connection = _open_connection(
        user=database.user,
        password=database.password,
        database=database.name,
    )
    try:
        parse_live_identity_row(
            _query_live_identity(connection),
            expected_database=database.name,
            expected_user=database.user,
        )
    finally:
        connection.close()


def verify_local_database_server() -> None:
    validate_database_environment(os.environ)
    root_password = os.environ.pop("NPI_LOCAL_DATABASE_ROOT_PASSWORD", None)
    require(
        isinstance(root_password, str)
        and len(root_password) >= 12
        and not {"\x00", "\n", "\r"}.intersection(root_password),
        "Controlled local MariaDB root credential is unavailable",
    )
    connection = _open_connection(
        user="root",
        password=root_password,
        database=None,
    )
    root_password = ""
    try:
        parse_live_identity_row(
            _query_live_identity(connection),
            expected_database=None,
            expected_user="root",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.schemata "
                "WHERE schema_name = %s",
                (DATABASE_NAME,),
            )
            row = cursor.fetchone()
        require(
            isinstance(row, (tuple, list))
            and len(row) == 1
            and row[0] == 0,
            "Dedicated local runtime database already exists without its Site",
        )
    except SiteSafetyError:
        raise
    except Exception:
        raise SiteSafetyError("Controlled local MariaDB server probe failed") from None
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("config", "database", "live", "server"),
        required=True,
    )
    arguments = parser.parse_args()

    if arguments.mode == "config":
        load_controlled_database(require_runtime_config=True)
    elif arguments.mode == "database":
        verify_live_site_database(require_runtime_config=False)
    elif arguments.mode == "live":
        verify_live_site_database(require_runtime_config=True)
    else:
        verify_local_database_server()
    print("controlled local Frappe database identity passed")


if __name__ == "__main__":
    try:
        main()
    except SiteSafetyError as error:
        raise SystemExit(str(error)) from None
