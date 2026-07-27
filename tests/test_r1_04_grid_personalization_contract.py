from __future__ import annotations

import ast
import csv
import json
import re
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OPENAPI_PATH = ROOT / "contracts" / "npi-api.openapi.yaml"
OPENAPI = OPENAPI_PATH.read_text(encoding="utf-8")
OPENAPI_LINES = OPENAPI.splitlines()
BFF_PATH = ROOT / "apps" / "npi_core" / "npi_core" / "bff.py"
BFF_SOURCE = BFF_PATH.read_text(encoding="utf-8")
DOMAIN_PATH = (
    ROOT
    / "apps"
    / "npi_core"
    / "npi_core"
    / "grid_personalization"
    / "domain.py"
)
DOMAIN_SOURCE = DOMAIN_PATH.read_text(encoding="utf-8")
FRONTEND_DATA_SOURCE_PATH = (
    ROOT / "frontend" / "src" / "api" / "grid-preferences-data-source.ts"
)
FRONTEND_DATA_SOURCE = FRONTEND_DATA_SOURCE_PATH.read_text(encoding="utf-8")
LIVE_WORKLIST_PATH = (
    ROOT / "frontend" / "src" / "components" / "live-my-worklist.tsx"
)
LIVE_WORKLIST_SOURCE = LIVE_WORKLIST_PATH.read_text(encoding="utf-8")
RUNTIME_VERIFIER_PATH = ROOT / "scripts" / "verify_frappe_runtime.py"
RUNTIME_VERIFIER_SOURCE = RUNTIME_VERIFIER_PATH.read_text(encoding="utf-8")
GRID_RUNTIME_VERIFIER_PATH = (
    ROOT / "scripts" / "verify_grid_personalization_runtime.py"
)
GRID_RUNTIME_VERIFIER_SOURCE = GRID_RUNTIME_VERIFIER_PATH.read_text(
    encoding="utf-8"
)
RUNTIME_SHELL_SOURCE = (
    ROOT / "scripts" / "verify-frappe-runtime.sh"
).read_text(encoding="utf-8")

PERSONAL_PATH = "/me/preferences/my-work-grid"
FULL_PERSONAL_PATH = f"/api/npi/v1{PERSONAL_PATH}"
RECOVERY_REASON = "stored_preference_invalid"
VIEW_IDS = (
    "all",
    "today",
    "overdue",
    "approvals",
    "blockers",
    "waiting",
    "integration",
)
COLUMN_IDS = (
    "type",
    "item",
    "context",
    "assignment",
    "priority",
    "due",
    "status",
    "action",
)
COLUMN_WIDTHS = {
    "type": {"minimum": 88, "maximum": 180, "default": 112},
    "item": {"minimum": 180, "maximum": 480, "default": 260},
    "context": {"minimum": 160, "maximum": 420, "default": 240},
    "assignment": {"minimum": 140, "maximum": 320, "default": 180},
    "priority": {"minimum": 96, "maximum": 180, "default": 112},
    "due": {"minimum": 120, "maximum": 220, "default": 144},
    "status": {"minimum": 112, "maximum": 220, "default": 136},
    "action": {"minimum": 120, "maximum": 260, "default": 160},
}
CAPABILITY_FIELDS = (
    "canPublishSharedView",
    "canRollbackSharedView",
    "canExport",
    "canRunBulkActions",
    "publishUnavailableReason",
    "rollbackUnavailableReason",
    "exportUnavailableReason",
    "bulkUnavailableReason",
)

DOCTYPE_ROOT = (
    ROOT / "apps" / "npi_core" / "npi_core" / "npi_core" / "doctype"
)
DOCTYPE_CASES = {
    "npi_my_work_grid_preference": {
        "name": "NPI My Work Grid Preference",
        "roles": {"All", "System Manager"},
        "fields": {
            "global_id",
            "preference_key_hash",
            "tenant_id",
            "actor_user_id",
            "grid_id",
            "table_schema_version",
            "optimistic_version",
            "preference_snapshot",
            "snapshot_hash",
            "last_changed_by",
            "last_changed_at",
            "request_id",
            "trace_id",
        },
    },
    "npi_published_grid_view": {
        "name": "NPI Published Grid View",
        "roles": {"NPI API User", "System Manager"},
        "fields": {
            "global_id",
            "tenant_id",
            "project_global_id",
            "grid_id",
            "table_schema_version",
            "optimistic_version",
            "current_revision_global_id",
            "current_revision_number",
            "current_revision_snapshot_hash",
            "created_by",
            "created_at",
            "request_id",
            "trace_id",
        },
    },
    "npi_published_grid_view_revision": {
        "name": "NPI Published Grid View Revision",
        "roles": {"NPI API User", "System Manager"},
        "fields": {
            "global_id",
            "revision_key",
            "published_view_global_id",
            "tenant_id",
            "project_global_id",
            "grid_id",
            "table_schema_version",
            "revision_number",
            "prior_revision_global_id",
            "prior_revision_number",
            "prior_revision_snapshot_hash",
            "restored_from_revision_global_id",
            "restored_from_revision_number",
            "restored_from_revision_snapshot_hash",
            "view_name",
            "description",
            "permission_boundary",
            "definition_snapshot",
            "definition_hash",
            "published_by",
            "published_at",
            "authority_reason_code",
            "authority_evidence",
            "request_id",
            "trace_id",
            "revision_snapshot",
            "snapshot_hash",
        },
    },
}

R1_04_TRANSLATION_SOURCES = {
    "Bulk actions",
    "Export",
    "Favorite views",
    "Fixed columns",
    "Grid settings",
    "Recent views",
    "Reset grid layout",
    "Save current filters",
    "Shared view publishing",
}


def _indented_block(marker: str) -> str:
    matches = [index for index, line in enumerate(OPENAPI_LINES) if line == marker]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {marker!r} block, found {len(matches)}")
    start = matches[0]
    indent = len(marker) - len(marker.lstrip())
    end = len(OPENAPI_LINES)
    for index in range(start + 1, len(OPENAPI_LINES)):
        line = OPENAPI_LINES[index]
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            end = index
            break
    return "\n".join(OPENAPI_LINES[start:end])


def _schema(name: str) -> str:
    return _indented_block(f"    {name}:")


def _operation(method: str) -> str:
    path_lines = _indented_block(f"  {PERSONAL_PATH}:").splitlines()
    marker = f"    {method}:"
    matches = [index for index, line in enumerate(path_lines) if line == marker]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {method!r} operation")
    start = matches[0]
    end = len(path_lines)
    for index in range(start + 1, len(path_lines)):
        line = path_lines[index]
        if line.strip() and len(line) - len(line.lstrip()) <= 4:
            end = index
            break
    return "\n".join(path_lines[start:end])


def _required_fields(schema_name: str) -> tuple[str, ...]:
    match = re.search(
        r"^      required:\s*\[(.*?)\]",
        _schema(schema_name),
        re.MULTILINE | re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"{schema_name} requires a closed required list")
    return tuple(
        token.strip()
        for token in match.group(1).replace("\n", " ").split(",")
        if token.strip()
    )


def _property_names(schema_name: str) -> set[str]:
    return set(
        re.findall(
            r"^        ([A-Za-z][A-Za-z0-9]*):",
            _schema(schema_name),
            re.MULTILINE,
        )
    )


def _schema_field(schema_name: str, field_name: str) -> str:
    schema_lines = _schema(schema_name).splitlines()
    marker = f"        {field_name}:"
    matches = [
        index
        for index, line in enumerate(schema_lines)
        if line == marker or line.startswith(f"{marker} ")
    ]
    if len(matches) != 1:
        raise AssertionError(
            f"Expected one {schema_name}.{field_name} field, found {len(matches)}"
        )
    start = matches[0]
    end = len(schema_lines)
    for index in range(start + 1, len(schema_lines)):
        line = schema_lines[index]
        if line.strip() and len(line) - len(line.lstrip()) <= 8:
            end = index
            break
    return "\n".join(schema_lines[start:end])


def _flow_enum(schema_name: str) -> tuple[str, ...]:
    match = re.search(r"^      enum: \[([^]]*)\]", _schema(schema_name), re.MULTILINE)
    if match is None:
        raise AssertionError(f"{schema_name} requires a flow-style enum")
    return tuple(value.strip() for value in match.group(1).split(","))


def _literal_assignment(source: str, name: str) -> Any:
    tree = ast.parse(source)
    matches: list[ast.AST] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            matches.append(node.value)
    if len(matches) != 1:
        raise AssertionError(f"Expected one literal assignment for {name}")
    return ast.literal_eval(matches[0])


def _function_node(source: str, name: str) -> ast.FunctionDef:
    matches = [
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected one function named {name}")
    return matches[0]


def _function_source(source: str, name: str) -> str:
    return ast.unparse(_function_node(source, name))


def _class_method_node(
    source: str,
    class_name: str,
    method_name: str,
) -> ast.FunctionDef:
    classes = [
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    if len(classes) != 1:
        raise AssertionError(f"Expected one class named {class_name}")
    matches = [
        node
        for node in classes[0].body
        if isinstance(node, ast.FunctionDef) and node.name == method_name
    ]
    if len(matches) != 1:
        raise AssertionError(
            f"Expected one {class_name}.{method_name} method"
        )
    return matches[0]


def _class_method_source(
    source: str,
    class_name: str,
    method_name: str,
) -> str:
    return ast.unparse(_class_method_node(source, class_name, method_name))


def _literal_return(source: str, function_name: str) -> Any:
    function = _function_node(source, function_name)
    matches = [
        node.value
        for node in ast.walk(function)
        if isinstance(node, ast.Return) and node.value is not None
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected one literal return in {function_name}")
    return ast.literal_eval(matches[0])


def _typescript_string_array(name: str) -> tuple[str, ...]:
    match = re.search(
        rf"export const {re.escape(name)} = \[(.*?)\] as const;",
        FRONTEND_DATA_SOURCE,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"Missing TypeScript constant {name}")
    return tuple(re.findall(r'"([^"]+)"', match.group(1)))


def _backend_widths() -> dict[str, dict[str, int]]:
    matches = re.findall(
        r'"([a-z]+)": ColumnWidthSpec\((\d+), (\d+), (\d+)\)',
        DOMAIN_SOURCE,
    )
    return {
        column_id: {
            "minimum": int(minimum),
            "maximum": int(maximum),
            "default": int(default),
        }
        for column_id, minimum, maximum, default in matches
    }


def _frontend_widths() -> dict[str, dict[str, int]]:
    matches = re.findall(
        r"^\s{2}([a-z]+): Object\.freeze"
        r"\(\{ default: (\d+), maximum: (\d+), minimum: (\d+) \}\),$",
        FRONTEND_DATA_SOURCE,
        re.MULTILINE,
    )
    return {
        column_id: {
            "minimum": int(minimum),
            "maximum": int(maximum),
            "default": int(default),
        }
        for column_id, default, maximum, minimum in matches
    }


def _doctype_metadata(directory_name: str) -> dict[str, Any]:
    path = DOCTYPE_ROOT / directory_name / f"{directory_name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _catalog(language: str) -> dict[str, str]:
    path = (
        ROOT
        / "apps"
        / "npi_core"
        / "npi_core"
        / "translations"
        / f"{language}.csv"
    )
    with path.open(encoding="utf-8", newline="") as catalog_file:
        return {
            row[0]: row[1]
            for row in csv.reader(catalog_file)
            if len(row) >= 2 and row[0]
        }


class R104GridPersonalizationContractTests(unittest.TestCase):
    def test_openapi_exposes_only_fixed_personal_get_and_put(self) -> None:
        path_block = _indented_block(f"  {PERSONAL_PATH}:")
        self.assertEqual(
            set(re.findall(r"^    ([a-z]+):$", path_block, re.MULTILINE)),
            {"get", "put"},
        )

        get = _operation("get")
        self.assertIn("operationId: getMyWorkGridPreferences", get)
        self.assertIn(
            '$ref: "#/components/schemas/MyWorkGridPreferences"',
            get,
        )
        self.assertIn('const: "private, no-store"', get)
        self.assertIn('"422":', get)
        self.assertNotIn("requestBody:", get)

        put = _operation("put")
        self.assertIn("operationId: setMyWorkGridPreferences", put)
        self.assertIn('$ref: "#/components/parameters/CsrfToken"', put)
        self.assertIn(
            '$ref: "#/components/schemas/SetMyWorkGridPreferences"',
            put,
        )
        self.assertIn(
            '$ref: "#/components/schemas/MyWorkGridPreferences"',
            put,
        )
        self.assertIn('const: "private, no-store"', put)
        self.assertIn('"409":', put)
        self.assertIn('"422":', put)

    def test_openapi_personal_schema_is_closed(self) -> None:
        self.assertEqual(_flow_enum("MyWorkGridViewId"), VIEW_IDS)
        self.assertEqual(_flow_enum("MyWorkGridColumnId"), COLUMN_IDS)

        response_fields = (
            "gridId",
            "tableSchemaVersion",
            "version",
            "viewLayouts",
            "favoriteViewIds",
            "recentViewIds",
            "defaultProjectId",
            "recoveryReason",
            "capabilities",
        )
        command_fields = (
            "expectedVersion",
            "tableSchemaVersion",
            "viewId",
            "layout",
            "filter",
            "saveFilter",
            "favoriteViewIds",
            "recentViewIds",
            "defaultProjectId",
        )
        self.assertEqual(_required_fields("MyWorkGridPreferences"), response_fields)
        self.assertEqual(_property_names("MyWorkGridPreferences"), set(response_fields))
        self.assertEqual(_required_fields("SetMyWorkGridPreferences"), command_fields)
        self.assertEqual(
            _property_names("SetMyWorkGridPreferences"),
            set(command_fields),
        )
        self.assertIn(
            "additionalProperties: false",
            _schema("MyWorkGridPreferences"),
        )
        self.assertIn(
            "additionalProperties: false",
            _schema("SetMyWorkGridPreferences"),
        )
        self.assertIn(
            "const: my-work",
            _schema_field("MyWorkGridPreferences", "gridId"),
        )
        for schema_name in (
            "MyWorkGridPreferences",
            "SetMyWorkGridPreferences",
        ):
            self.assertIn(
                "const: my-work-grid-v1",
                _schema_field(schema_name, "tableSchemaVersion"),
            )
        self.assertIn(
            "minItems: 7",
            _schema_field("MyWorkGridPreferences", "viewLayouts"),
        )
        self.assertIn(
            "maxItems: 7",
            _schema_field("MyWorkGridPreferences", "viewLayouts"),
        )
        view_layouts = _schema_field("MyWorkGridPreferences", "viewLayouts")
        self.assertIn("prefixItems:", view_layouts)
        self.assertIn("items: false", view_layouts)
        self.assertEqual(
            tuple(
                re.findall(
                    r"viewId: \{ const: ([a-z]+) \}",
                    view_layouts,
                )
            ),
            VIEW_IDS,
        )
        self.assertIn(
            "maxItems: 5",
            _schema_field("MyWorkGridPreferences", "recentViewIds"),
        )
        view_preference_fields = (
            "viewId",
            "layout",
            "filter",
            "hasSavedFilter",
        )
        self.assertEqual(
            _required_fields("MyWorkGridViewPreference"),
            view_preference_fields,
        )
        self.assertEqual(
            _property_names("MyWorkGridViewPreference"),
            set(view_preference_fields),
        )
        self.assertIn(
            "type: boolean",
            _schema_field("MyWorkGridViewPreference", "hasSavedFilter"),
        )
        self.assertIn(
            "type: boolean",
            _schema_field("SetMyWorkGridPreferences", "saveFilter"),
        )
        recovery_reason = _schema_field(
            "MyWorkGridPreferences",
            "recoveryReason",
        )
        self.assertIn("oneOf:", recovery_reason)
        self.assertIn(
            f"{{ type: string, const: {RECOVERY_REASON} }}",
            recovery_reason,
        )
        self.assertIn('{ type: "null" }', recovery_reason)
        self.assertEqual(recovery_reason.count("const:"), 1)
        self.assertNotIn(
            "recoveryReason",
            _schema("SetMyWorkGridPreferences"),
        )
        self.assertEqual(
            _required_fields("MyWorkGridFilter"),
            ("projectId", "priority", "search"),
        )
        self.assertIn(
            "maxLength: 140",
            _schema_field("MyWorkGridFilter", "search"),
        )
        self.assertIn(
            "maximum: 2",
            _schema_field("MyWorkGridLayout", "fixedColumnCount"),
        )

        self.assertEqual(
            _property_names("MyWorkGridWidths"),
            set(COLUMN_IDS),
        )
        for column_id, spec in COLUMN_WIDTHS.items():
            width = _schema_field("MyWorkGridWidths", column_id)
            self.assertIn(f"minimum: {spec['minimum']}", width)
            self.assertIn(f"maximum: {spec['maximum']}", width)

    def test_capabilities_fail_closed_and_no_shared_publish_route_exists(self) -> None:
        self.assertEqual(
            _required_fields("MyWorkGridCapabilities"),
            CAPABILITY_FIELDS,
        )
        self.assertEqual(
            _property_names("MyWorkGridCapabilities"),
            set(CAPABILITY_FIELDS),
        )
        for field_name in CAPABILITY_FIELDS[:4]:
            self.assertIn(
                "const: false",
                _schema_field("MyWorkGridCapabilities", field_name),
            )
        expected_reasons = {
            "publishUnavailableReason": "publisher_authority_policy_required",
            "rollbackUnavailableReason": "publisher_authority_policy_required",
            "exportUnavailableReason": "export_contract_required",
            "bulkUnavailableReason": "bulk_action_contract_required",
        }
        for field_name, reason in expected_reasons.items():
            self.assertIn(
                f"const: {reason}",
                _schema_field("MyWorkGridCapabilities", field_name),
            )

        openapi_paths = set(
            re.findall(r"^  (/[^ ]+):$", OPENAPI, re.MULTILINE)
        )
        grid_paths = {path for path in openapi_paths if "my-work-grid" in path}
        self.assertEqual(grid_paths, {PERSONAL_PATH})
        grid_operation_ids = {
            operation_id
            for operation_id in re.findall(
                r"operationId: ([A-Za-z0-9]+)",
                OPENAPI,
            )
            if "grid" in operation_id.casefold()
        }
        self.assertEqual(
            grid_operation_ids,
            {"getMyWorkGridPreferences", "setMyWorkGridPreferences"},
        )

    def test_bff_routes_fixed_path_to_personal_handlers_only(self) -> None:
        routes = _literal_assignment(BFF_SOURCE, "_ROUTES")
        grid_routes = {
            route: handler
            for route, handler in routes.items()
            if "my-work-grid" in route[1]
        }
        self.assertEqual(
            grid_routes,
            {
                ("GET", FULL_PERSONAL_PATH): (
                    "npi_core.grid_personalization_api."
                    "get_my_work_grid_preferences"
                ),
                ("PUT", FULL_PERSONAL_PATH): (
                    "npi_core.grid_personalization_api."
                    "set_my_work_grid_preferences"
                ),
            },
        )
        request_id_function = next(
            node
            for node in ast.parse(BFF_SOURCE).body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_requires_project_request_id"
        )
        request_id_source = ast.get_source_segment(
            BFF_SOURCE,
            request_id_function,
        )
        self.assertIsNotNone(request_id_source)
        self.assertIn('method in {"GET", "PUT"}', request_id_source)
        self.assertIn(f'path == "{FULL_PERSONAL_PATH}"', request_id_source)

    def test_doctype_metadata_permissions_are_non_deletable(self) -> None:
        for directory_name, expected in DOCTYPE_CASES.items():
            with self.subTest(doctype=expected["name"]):
                metadata = _doctype_metadata(directory_name)
                self.assertEqual(metadata["doctype"], "DocType")
                self.assertEqual(metadata["name"], expected["name"])
                self.assertEqual(metadata["module"], "NPI Core")
                self.assertEqual(metadata["custom"], 0)
                self.assertEqual(metadata["allow_rename"], 0)
                self.assertEqual(metadata["read_only"], 1)
                self.assertEqual(metadata["track_changes"], 0)

                permissions = metadata["permissions"]
                self.assertEqual(
                    {permission["role"] for permission in permissions},
                    expected["roles"],
                )
                for permission in permissions:
                    self.assertEqual(permission["create"], 1)
                    self.assertEqual(permission["write"], 1)
                    for capability in ("delete", "email", "export", "print"):
                        self.assertEqual(permission[capability], 0)
                    self.assertEqual(
                        permission["read"],
                        1 if permission["role"] == "System Manager" else 0,
                    )

    def test_doctype_schema_fields_are_exact_and_read_only(self) -> None:
        for directory_name, expected in DOCTYPE_CASES.items():
            with self.subTest(doctype=expected["name"]):
                metadata = _doctype_metadata(directory_name)
                fields = {
                    field["fieldname"]: field for field in metadata["fields"]
                }
                self.assertEqual(set(fields), expected["fields"])
                self.assertTrue(
                    all(field.get("read_only") == 1 for field in fields.values())
                )
                self.assertEqual(fields["grid_id"]["options"], "my-work")
                self.assertEqual(fields["request_id"]["fieldtype"], "Data")
                self.assertEqual(fields["trace_id"]["fieldtype"], "Data")
                version_field = (
                    "revision_number"
                    if directory_name == "npi_published_grid_view_revision"
                    else "optimistic_version"
                )
                self.assertEqual(fields[version_field]["fieldtype"], "Int")

        preference = _doctype_metadata("npi_my_work_grid_preference")
        preference_fields = {
            field["fieldname"]: field for field in preference["fields"]
        }
        self.assertEqual(
            preference_fields["preference_snapshot"]["fieldtype"],
            "JSON",
        )
        self.assertEqual(preference["autoname"], "field:global_id")

        published = _doctype_metadata("npi_published_grid_view")
        self.assertEqual(published["autoname"], "field:global_id")

        revision = _doctype_metadata("npi_published_grid_view_revision")
        revision_fields = {
            field["fieldname"]: field for field in revision["fields"]
        }
        self.assertEqual(revision["autoname"], "field:revision_key")
        self.assertEqual(
            revision_fields["published_view_global_id"]["options"],
            "NPI Published Grid View",
        )
        for snapshot_field in (
            "authority_evidence",
            "definition_snapshot",
            "revision_snapshot",
        ):
            self.assertEqual(revision_fields[snapshot_field]["fieldtype"], "JSON")
        self.assertEqual(
            revision_fields["permission_boundary"]["options"],
            "project_viewers",
        )

    def test_backend_and_frontend_grid_constants_agree(self) -> None:
        self.assertEqual(_literal_assignment(DOMAIN_SOURCE, "GRID_ID"), "my-work")
        self.assertEqual(
            _literal_assignment(DOMAIN_SOURCE, "TABLE_SCHEMA_VERSION"),
            "my-work-grid-v1",
        )
        self.assertEqual(_literal_assignment(DOMAIN_SOURCE, "VIEW_IDS"), VIEW_IDS)
        self.assertEqual(_literal_assignment(DOMAIN_SOURCE, "COLUMN_IDS"), COLUMN_IDS)
        self.assertEqual(
            _literal_assignment(DOMAIN_SOURCE, "MAX_FIXED_COLUMN_COUNT"),
            2,
        )
        self.assertEqual(
            _literal_assignment(DOMAIN_SOURCE, "MAX_RECENT_VIEW_IDS"),
            5,
        )

        self.assertRegex(
            FRONTEND_DATA_SOURCE,
            r'export const myWorkGridId = "my-work" as const;',
        )
        self.assertRegex(
            FRONTEND_DATA_SOURCE,
            (
                r'export const myWorkTableSchemaVersion = '
                r'"my-work-grid-v1" as const;'
            ),
        )
        self.assertEqual(_typescript_string_array("myWorkGridViewIds"), VIEW_IDS)
        self.assertEqual(_typescript_string_array("myWorkGridColumnIds"), COLUMN_IDS)
        self.assertEqual(_backend_widths(), COLUMN_WIDTHS)
        self.assertEqual(_frontend_widths(), COLUMN_WIDTHS)

        response_method = _class_method_source(
            DOMAIN_SOURCE,
            "PersonalGridPreference",
            "response_dict",
        )
        response_node = _class_method_node(
            DOMAIN_SOURCE,
            "PersonalGridPreference",
            "response_dict",
        )
        recovery_sets = [
            ast.literal_eval(node.comparators[0])
            for node in ast.walk(response_node)
            if isinstance(node, ast.Compare)
            and any(isinstance(operator, ast.NotIn) for operator in node.ops)
            and "recovery_reason" in ast.unparse(node.left)
            and len(node.comparators) == 1
            and isinstance(node.comparators[0], ast.Set)
        ]
        self.assertEqual(recovery_sets, [{None, RECOVERY_REASON}])
        self.assertIn(
            "'recoveryReason': recovery_reason",
            response_method,
        )
        self.assertNotIn(
            "recoveryReason",
            _class_method_source(
                DOMAIN_SOURCE,
                "PersonalGridPreference",
                "storage_dict",
            ),
        )

        self.assertIn(
            (
                "readonly recoveryReason: "
                f'"{RECOVERY_REASON}" | null;'
            ),
            FRONTEND_DATA_SOURCE,
        )
        self.assertIn('"recoveryReason",', FRONTEND_DATA_SOURCE)
        self.assertIn(
            (
                "value.recoveryReason !== null &&\n"
                f'      value.recoveryReason !== "{RECOVERY_REASON}"'
            ),
            FRONTEND_DATA_SOURCE,
        )
        self.assertIn("recoveryReason: null,", FRONTEND_DATA_SOURCE)

    def test_runtime_verifier_hooks_cover_authentication_and_csrf(self) -> None:
        self.assertEqual(
            _literal_assignment(
                RUNTIME_VERIFIER_SOURCE,
                "GRID_PREFERENCE_PATH",
            ),
            FULL_PERSONAL_PATH,
        )
        self.assertEqual(
            _literal_assignment(RUNTIME_VERIFIER_SOURCE, "GRID_VIEW_IDS"),
            VIEW_IDS,
        )
        self.assertEqual(
            _literal_assignment(
                RUNTIME_VERIFIER_SOURCE,
                "GRID_PREFERENCE_KEYS",
            ),
            {
                "gridId",
                "tableSchemaVersion",
                "version",
                "viewLayouts",
                "favoriteViewIds",
                "recentViewIds",
                "defaultProjectId",
                "recoveryReason",
                "capabilities",
            },
        )
        runtime_validation = _function_node(
            RUNTIME_VERIFIER_SOURCE,
            "validate_grid_preferences",
        )
        recovery_sets = [
            ast.literal_eval(node.comparators[0])
            for node in ast.walk(runtime_validation)
            if isinstance(node, ast.Compare)
            and any(isinstance(operator, ast.In) for operator in node.ops)
            and "recoveryReason" in ast.unparse(node.left)
            and len(node.comparators) == 1
            and isinstance(node.comparators[0], ast.Set)
        ]
        self.assertEqual(recovery_sets, [{None, RECOVERY_REASON}])

        main = _function_source(RUNTIME_VERIFIER_SOURCE, "main")
        self.assertIn(
            (
                "guest_grid_preferences = request("
                "urllib.request.build_opener(), base_url, GRID_PREFERENCE_PATH)"
            ),
            main,
        )
        self.assertIn(
            (
                "validate_problem(guest_grid_preferences, 401, "
                "'AUTHENTICATION_REQUIRED')"
            ),
            main,
        )
        self.assertIn(
            (
                "guest_grid_preference_write = put_grid_preferences("
                "urllib.request.build_opener(), base_url, {}, "
                "'guest-csrf-token')"
            ),
            main,
        )
        self.assertIn(
            (
                "validate_problem(guest_grid_preference_write, 401, "
                "'AUTHENTICATION_REQUIRED')"
            ),
            main,
        )

        lifecycle = _function_source(
            RUNTIME_VERIFIER_SOURCE,
            "verify_grid_preferences_runtime",
        )
        self.assertIn(
            (
                "csrf_missing = put_grid_preferences("
                "administrator_opener, base_url"
            ),
            lifecycle,
        )
        self.assertIn(
            (
                "None, trace_id='trace-grid-csrf-missing')\n"
                "    validate_problem(csrf_missing, 403, "
                "'CSRF_TOKEN_INVALID'"
            ),
            lifecycle,
        )
        self.assertIn(
            "verify_grid_preferences_runtime(",
            main,
        )
        put_helper = _function_source(
            RUNTIME_VERIFIER_SOURCE,
            "put_grid_preferences",
        )
        self.assertIn(
            "headers['X-Frappe-CSRF-Token'] = csrf_token",
            put_helper,
        )
        self.assertIn("method='PUT'", put_helper)

    def test_runtime_verifier_keeps_persisted_state_read_only(
        self,
    ) -> None:
        lifecycle = _function_source(
            RUNTIME_VERIFIER_SOURCE,
            "verify_grid_preferences_runtime",
        )
        self.assertIn(
            (
                "stale = put_grid_preferences("
                "administrator_opener, base_url"
            ),
            lifecycle,
        )
        self.assertIn(
            "validate_problem(stale, 409, 'VERSION_CONFLICT')",
            lifecycle,
        )
        self.assertIn(
            (
                "fresh_session = login("
                "base_url, ADMINISTRATOR_USER, administrator_password)"
            ),
            lifecycle,
        )
        self.assertIn(
            (
                "fresh = request("
                "fresh_session, base_url, GRID_PREFERENCE_PATH)"
            ),
            lifecycle,
        )
        self.assertIn(
            "fresh.body == initial.body",
            lifecycle,
        )
        self.assertIn(
            (
                "invalid_schema_payload['tableSchemaVersion'] = "
                "'unsupported-grid-schema'"
            ),
            lifecycle,
        )
        self.assertIn(
            "validate_problem(invalid_schema, 422, 'VALIDATION_FAILED')",
            lifecycle,
        )
        self.assertIn(
            (
                "unchanged = request("
                "fresh_session, base_url, GRID_PREFERENCE_PATH)"
            ),
            lifecycle,
        )
        self.assertIn(
            "validate_grid_preferences(unchanged)",
            lifecycle,
        )
        self.assertIn(
            "unchanged.body == initial.body",
            lifecycle,
        )
        self.assertNotIn("changed = put_grid_preferences(", lifecycle)
        self.assertNotIn("restored = put_grid_preferences(", lifecycle)
        self.assertEqual(
            _literal_return(
                RUNTIME_VERIFIER_SOURCE,
                "verify_grid_preferences_runtime",
            ),
            {
                "gridPreferenceCsrfMissing": 403,
                "gridPreferenceReadIsolation": True,
                "gridPreferenceSchemaMismatch": 422,
                "gridPreferenceVersionConflict": 409,
            },
        )
        main = _function_source(RUNTIME_VERIFIER_SOURCE, "main")
        self.assertIn("**grid_preference_evidence", main)

    def test_runtime_verifier_denies_generic_crud_for_all_grid_doctypes(
        self,
    ) -> None:
        function_names = {
            node.name
            for node in ast.parse(RUNTIME_VERIFIER_SOURCE).body
            if isinstance(node, ast.FunctionDef)
        }
        candidates = (
            "verify_grid_generic_crud_denied",
            "verify_grid_generic_create_denied",
        )
        available = [
            function_name
            for function_name in candidates
            if function_name in function_names
        ]
        self.assertEqual(len(available), 1)
        function_name = available[0]

        generic_denial = _function_source(
            RUNTIME_VERIFIER_SOURCE,
            function_name,
        )
        for case in DOCTYPE_CASES.values():
            self.assertIn(repr(case["name"]), generic_denial)
        self.assertIn("method='POST'", generic_denial)
        self.assertIn("created.status == 403", generic_denial)
        self.assertIn(
            "request(administrator_opener, base_url, resource_path).status == 404",
            generic_denial,
        )
        if function_name == "verify_grid_generic_crud_denied":
            self.assertIn("method='PUT'", generic_denial)
            self.assertIn("method='DELETE'", generic_denial)
            self.assertGreaterEqual(generic_denial.count("status == 403"), 1)
            self.assertGreaterEqual(
                generic_denial.count("status in {403, 417}"),
                2,
            )

        main = _function_source(RUNTIME_VERIFIER_SOURCE, "main")
        assignment = re.search(
            rf"([a-z_]+) = {re.escape(function_name)}\(",
            main,
        )
        self.assertIsNotNone(assignment)
        variable_name = assignment.group(1)
        self.assertRegex(
            main,
            (
                r"'gridGeneric(?:Create|Crud)Denied': "
                + re.escape(variable_name)
            ),
        )

    def test_real_controller_probe_is_transaction_rollback_only(self) -> None:
        for controller_name in (
            "NPI My Work Grid Preference",
            "NPI Published Grid View",
            "NPI Published Grid View Revision",
        ):
            self.assertIn(controller_name, GRID_RUNTIME_VERIFIER_SOURCE)
        self.assertIn(
            "FrappePublishedGridViewRepository",
            GRID_RUNTIME_VERIFIER_SOURCE,
        )
        self.assertIn(
            "FrappeGridPersonalizationRepository",
            GRID_RUNTIME_VERIFIER_SOURCE,
        )
        self.assertIn("persist_first(", GRID_RUNTIME_VERIFIER_SOURCE)
        self.assertGreaterEqual(
            GRID_RUNTIME_VERIFIER_SOURCE.count(".append("),
            2,
        )
        self.assertIn(
            "rollback_as_new_revision(",
            GRID_RUNTIME_VERIFIER_SOURCE,
        )
        self.assertIn(
            "frappe.db.rollback()",
            GRID_RUNTIME_VERIFIER_SOURCE,
        )
        self.assertIn(
            "Grid controller runtime rollback left fixture records",
            GRID_RUNTIME_VERIFIER_SOURCE,
        )
        self.assertIn(
            '"optimistic_version",\n        0,',
            GRID_RUNTIME_VERIFIER_SOURCE,
        )
        self.assertIn(
            '"corruptVersionRepair": True',
            GRID_RUNTIME_VERIFIER_SOURCE,
        )
        self.assertIn(
            "run_grid_controller_runtime_verifier",
            RUNTIME_SHELL_SOURCE,
        )
        self.assertIn(
            "verify_grid_personalization_runtime.py",
            RUNTIME_SHELL_SOURCE,
        )

    def test_translation_source_inventory_is_symmetric_when_present(self) -> None:
        for source in R1_04_TRANSLATION_SOURCES:
            self.assertIn(f't("{source}"', LIVE_WORKLIST_SOURCE)

        simplified = _catalog("zh")
        traditional = _catalog("zh-TW")
        cataloged = R1_04_TRANSLATION_SOURCES.intersection(
            simplified.keys() | traditional.keys()
        )
        for source in cataloged:
            with self.subTest(source=source):
                self.assertIn(source, simplified)
                self.assertIn(source, traditional)
                self.assertTrue(simplified[source].strip())
                self.assertTrue(traditional[source].strip())


if __name__ == "__main__":
    unittest.main()
