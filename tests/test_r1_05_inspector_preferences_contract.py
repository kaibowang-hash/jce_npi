from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPENAPI = (
    ROOT / "contracts" / "npi-api.openapi.yaml"
).read_text(encoding="utf-8")
OPENAPI_LINES = OPENAPI.splitlines()
BFF_SOURCE = (
    ROOT / "apps" / "npi_core" / "npi_core" / "bff.py"
).read_text(encoding="utf-8")
LOCALIZATION_API_SOURCE = (
    ROOT / "apps" / "npi_core" / "npi_core" / "localization_api.py"
).read_text(encoding="utf-8")
RUNTIME_VERIFIER_SOURCE = (
    ROOT / "scripts" / "verify_frappe_runtime.py"
).read_text(encoding="utf-8")

PREFERENCE_PATH = "/me/preferences/my-work-inspector"
FULL_PREFERENCE_PATH = f"/api/npi/v1{PREFERENCE_PATH}"


def _indented_block(marker: str) -> str:
    matches = [
        index
        for index, line in enumerate(OPENAPI_LINES)
        if line == marker
    ]
    if len(matches) != 1:
        raise AssertionError(
            f"Expected one {marker!r} block, found {len(matches)}"
        )
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
    path_lines = _indented_block(f"  {PREFERENCE_PATH}:").splitlines()
    marker = f"    {method}:"
    matches = [
        index
        for index, line in enumerate(path_lines)
        if line == marker
    ]
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
            (
                f"Expected one {schema_name}.{field_name} field, "
                f"found {len(matches)}"
            )
        )
    start = matches[0]
    end = len(schema_lines)
    for index in range(start + 1, len(schema_lines)):
        line = schema_lines[index]
        if line.strip() and len(line) - len(line.lstrip()) <= 8:
            end = index
            break
    return "\n".join(schema_lines[start:end])


class InspectorPreferenceContractTest(unittest.TestCase):
    def test_openapi_exposes_only_fixed_get_and_put(self) -> None:
        path_block = _indented_block(f"  {PREFERENCE_PATH}:")
        self.assertEqual(
            set(re.findall(r"^    ([a-z]+):$", path_block, re.MULTILINE)),
            {"get", "put"},
        )

        get = _operation("get")
        self.assertIn("operationId: getMyWorkInspectorPreference", get)
        self.assertNotIn("requestBody:", get)
        self.assertIn(
            '$ref: "#/components/schemas/MyWorkInspectorPreference"',
            get,
        )
        self.assertIn('const: "private, no-store"', get)
        self.assertIn("X-Request-ID:", get)
        self.assertIn("X-Trace-ID:", get)
        self.assertIn('"401":', get)
        self.assertIn('"403":', get)
        self.assertIn('"422":', get)
        self.assertIn('"503":', get)

        put = _operation("put")
        self.assertIn("operationId: setMyWorkInspectorPreference", put)
        self.assertIn('$ref: "#/components/parameters/CsrfToken"', put)
        self.assertIn(
            '$ref: "#/components/schemas/SetMyWorkInspectorPreference"',
            put,
        )
        self.assertIn(
            '$ref: "#/components/schemas/MyWorkInspectorPreference"',
            put,
        )
        self.assertIn('const: "private, no-store"', put)
        self.assertIn('"400":', put)
        self.assertIn('"401":', put)
        self.assertIn('"403":', put)
        self.assertIn('"422":', put)
        self.assertIn('"503":', put)

    def test_request_and_response_schemas_are_exact_and_bounded(self) -> None:
        response_fields = (
            "paneId",
            "schemaVersion",
            "widthPx",
            "collapsed",
            "recoveryReason",
        )
        request_fields = ("schemaVersion", "widthPx", "collapsed")

        self.assertEqual(
            _required_fields("MyWorkInspectorPreference"),
            response_fields,
        )
        self.assertEqual(
            _property_names("MyWorkInspectorPreference"),
            set(response_fields),
        )
        self.assertEqual(
            _required_fields("SetMyWorkInspectorPreference"),
            request_fields,
        )
        self.assertEqual(
            _property_names("SetMyWorkInspectorPreference"),
            set(request_fields),
        )
        for schema_name in (
            "MyWorkInspectorPreference",
            "SetMyWorkInspectorPreference",
        ):
            schema = _schema(schema_name)
            self.assertIn("additionalProperties: false", schema)
            self.assertIn(
                "const: my-work-inspector-v1",
                _schema_field(schema_name, "schemaVersion"),
            )
            width = _schema_field(schema_name, "widthPx")
            self.assertIn("type: integer", width)
            self.assertIn("minimum: 260", width)
            self.assertIn("maximum: 480", width)
            self.assertIn(
                "type: boolean",
                _schema_field(schema_name, "collapsed"),
            )

        self.assertIn(
            "const: my-work-inspector",
            _schema_field("MyWorkInspectorPreference", "paneId"),
        )
        recovery = _schema_field(
            "MyWorkInspectorPreference",
            "recoveryReason",
        )
        self.assertIn("const: stored_preference_invalid", recovery)
        self.assertIn('type: "null"', recovery)

    def test_bff_route_is_fixed_actor_bound_and_session_bootstrap_is_unchanged(
        self,
    ) -> None:
        self.assertEqual(BFF_SOURCE.count(f'"{FULL_PREFERENCE_PATH}"'), 3)
        self.assertIn(
            (
                '("GET", "/api/npi/v1/me/preferences/my-work-inspector"): '
                "(\n"
                '        "npi_core.inspector_preferences_api.'
                'get_my_work_inspector_preference"\n'
                "    ),"
            ),
            BFF_SOURCE,
        )
        self.assertIn(
            (
                '("PUT", "/api/npi/v1/me/preferences/my-work-inspector"): '
                "(\n"
                '        "npi_core.inspector_preferences_api.'
                'set_my_work_inspector_preference"\n'
                "    ),"
            ),
            BFF_SOURCE,
        )
        self.assertNotIn("my-work-inspector", LOCALIZATION_API_SOURCE)
        self.assertNotIn(
            "npi_one_my_work_inspector_layout_v1",
            LOCALIZATION_API_SOURCE,
        )

    def test_runtime_verifier_covers_live_recovery_and_cleanup(self) -> None:
        self.assertIn(
            (
                'INSPECTOR_PREFERENCE_PATH = (\n'
                '    "/api/npi/v1/me/preferences/my-work-inspector"\n'
                ")"
            ),
            RUNTIME_VERIFIER_SOURCE,
        )
        self.assertIn(
            (
                'INSPECTOR_PREFERENCE_KEY = '
                '"npi_one_my_work_inspector_layout_v1"'
            ),
            RUNTIME_VERIFIER_SOURCE,
        )
        self.assertIn(
            "def verify_inspector_preference_runtime(",
            RUNTIME_VERIFIER_SOURCE,
        )
        self.assertIn(
            'expected_recovery_reason="stored_preference_invalid"',
            RUNTIME_VERIFIER_SOURCE,
        )
        self.assertIn(
            'trace_id="trace-inspector-csrf-missing"',
            RUNTIME_VERIFIER_SOURCE,
        )
        self.assertIn(
            "create_disposable_inspector_user(",
            RUNTIME_VERIFIER_SOURCE,
        )
        self.assertIn(
            "delete_disposable_user(\n"
            "                    cleanup_opener,\n"
            "                    base_url,\n"
            "                    INSPECTOR_DISPOSABLE_USER,",
            RUNTIME_VERIFIER_SOURCE,
        )
        self.assertIn(
            "guest_inspector_preference = request(",
            RUNTIME_VERIFIER_SOURCE,
        )
        self.assertIn(
            '"inspectorPreferenceActorIsolation": True',
            RUNTIME_VERIFIER_SOURCE,
        )


if __name__ == "__main__":
    unittest.main()
