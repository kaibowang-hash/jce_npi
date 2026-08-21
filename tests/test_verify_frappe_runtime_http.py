from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from email.message import Message
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_frappe_runtime.py"
TRACE_ID = "trace-" + "a" * 32


def load_verifier():
    spec = importlib.util.spec_from_file_location(
        "verify_frappe_runtime_http_contract",
        VERIFIER,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Frappe runtime verifier cannot be imported")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


def load_item_verifier():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(
        "verify_item_publish_runtime_http_contract",
        ROOT / "scripts" / "verify_item_publish_runtime.py",
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Item runtime verifier cannot be imported")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        with patch.dict(
            os.environ,
            {"NPI_DOCUMENT_RUNTIME_RUN_ID": "0" * 32},
            clear=False,
        ):
            spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


def response_headers(*, trace_id: str | None, problem: bool = True) -> Message:
    headers = Message()
    headers["Content-Type"] = (
        "application/problem+json; charset=utf-8"
        if problem
        else "application/json"
    )
    if trace_id is not None:
        headers["X-Trace-ID"] = trace_id
    return headers


class ErrorOpener:
    def __init__(self, headers: Message, body: dict[str, object]) -> None:
        self.headers = headers
        self.body = body

    def open(self, request, timeout: int):
        self.error = urllib.error.HTTPError(
            request.full_url,
            500,
            "private upstream exception message",
            self.headers,
            io.BytesIO(json.dumps(self.body).encode()),
        )
        raise self.error

    def close(self) -> None:
        error = getattr(self, "error", None)
        if error is not None:
            error.close()


class VerifyFrappeRuntimeHttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_verifier()

    def request(self, headers: Message, body: dict[str, object]):
        opener = ErrorOpener(headers, body)
        try:
            return self.module.request(
                opener,
                "http://127.0.0.1:8003",
                "/api/npi/v1/test",
            )
        finally:
            opener.close()

    def test_500_uses_real_response_trace_header(self) -> None:
        result = self.request(
            response_headers(trace_id=TRACE_ID),
            {"code": "INTERNAL_SERVER_ERROR", "privateValue": "released item"},
        )
        self.assertEqual(result.status, 500)
        self.assertEqual(result.trace_id, TRACE_ID)

    def test_matching_header_and_governed_problem_trace_are_required_equal(self) -> None:
        result = self.request(
            response_headers(trace_id=TRACE_ID),
            {"code": "INTERNAL_SERVER_ERROR", "traceId": TRACE_ID},
        )
        self.assertEqual(result.trace_id, TRACE_ID)

    def test_valid_governed_problem_trace_is_the_only_body_fallback(self) -> None:
        result = self.request(
            response_headers(trace_id=None),
            {"code": "INTERNAL_SERVER_ERROR", "traceId": TRACE_ID},
        )
        self.assertEqual(result.trace_id, TRACE_ID)
        with self.assertRaisesRegex(RuntimeError, "missing") as failure:
            self.request(
                response_headers(trace_id=None, problem=False),
                {"traceId": TRACE_ID, "privateValue": "released item"},
            )
        self.assertNotIn("released item", str(failure.exception))
        self.assertNotIn(TRACE_ID, str(failure.exception))

    def test_missing_mismatched_and_invalid_trace_fail_closed_without_leak(self) -> None:
        cases = (
            (
                response_headers(trace_id=None),
                {"code": "PRIVATE_VALUE", "privateValue": "released item"},
                "missing",
            ),
            (
                response_headers(trace_id=TRACE_ID),
                {"traceId": "trace-" + "b" * 32, "privateValue": "released item"},
                "do not match",
            ),
            (
                response_headers(trace_id="../../private/trace"),
                {"privateValue": "released item"},
                "invalid",
            ),
            (
                response_headers(trace_id=None),
                {"traceId": "bad trace /tmp/private", "privateValue": "released item"},
                "invalid",
            ),
        )
        for headers, body, reason in cases:
            with self.subTest(reason=reason), self.assertRaisesRegex(
                RuntimeError, reason
            ) as failure:
                self.request(headers, body)
            rendered = str(failure.exception)
            self.assertNotIn("released item", rendered)
            self.assertNotIn("/tmp/private", rendered)
            self.assertNotIn("PRIVATE_VALUE", rendered)


class ItemDiagnosticLookupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.http = load_verifier()
        cls.item = load_item_verifier()

    def test_allowlisted_stage_lookup_and_output_are_exact_and_sanitized(self) -> None:
        item = self.item
        code = "P803_CREATE_REQUEST_INSERT"
        with tempfile.TemporaryDirectory() as directory:
            bench_path = Path(directory).resolve()
            log_directory = bench_path / "logs"
            log_directory.mkdir()
            record = {
                "code": code,
                "exceptionType": "ValidationError",
                "traceId": TRACE_ID,
            }
            (log_directory / "npi_core.log").write_text(
                "released Item business value and private exception message "
                + json.dumps(record, separators=(",", ":"))
                + " /tmp/private\n",
                encoding="utf-8",
            )
            with patch.object(
                item.ebom_runtime, "BENCH_PATH", bench_path
            ), patch.object(item.ebom_runtime, "SITE_NAME", "npi.localhost"):
                result = self.http.HttpResult(
                    status=500,
                    headers=response_headers(trace_id=TRACE_ID),
                    body={
                        "code": "INTERNAL_SERVER_ERROR",
                        "privateValue": "released Item business value",
                        "message": "private exception message",
                    },
                    trace_id=TRACE_ID,
                )
                message = item.item_create_failure_message(result)

        self.assertEqual(
            message,
            "P8-03 Item command create failed "
            f"[diagnostic_code={code}; exception_type=ValidationError; "
            f"trace_id={TRACE_ID}]",
        )
        self.assertNotIn("released Item", message)
        self.assertNotIn("private exception", message)
        self.assertNotIn("/tmp/private", message)
        self.assertNotIn("INTERNAL_SERVER_ERROR", message)


if __name__ == "__main__":
    unittest.main()
