from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_document_runtime.py"
RUNTIME_SHELL = ROOT / "scripts" / "verify-frappe-runtime.sh"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
TOOLCHAIN = ROOT / ".devcontainer" / "toolchain.env"
FIXTURE_RUN_ID = "0123456789abcdef0123456789abcdef"


def load_verifier():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(
        "verify_document_runtime_contract",
        VERIFIER,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Document runtime verifier cannot be imported")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        with patch.dict(
            os.environ,
            {"NPI_DOCUMENT_RUNTIME_RUN_ID": FIXTURE_RUN_ID},
            clear=False,
        ):
            spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


class Phase5DocumentRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_verifier()
        cls.source = VERIFIER.read_text(encoding="utf-8")
        cls.shell = RUNTIME_SHELL.read_text(encoding="utf-8")
        cls.workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    def test_fixture_namespace_and_headers_are_bounded(self) -> None:
        module = self.module
        self.assertEqual(
            module.validated_fixture_run_id(FIXTURE_RUN_ID),
            FIXTURE_RUN_ID,
        )
        for invalid in (None, "", "A" * 32, "a" * 31, "../runtime"):
            with self.subTest(invalid=invalid), self.assertRaises(RuntimeError):
                module.validated_fixture_run_id(invalid)
        self.assertRegex(
            module.PROJECT_TEMPLATE_ID,
            r"^[a-f0-9-]{36}$",
        )
        self.assertNotEqual(
            module.PROJECT_TEMPLATE_ID,
            module.DOCUMENT_POLICY_ID,
        )
        self.assertRegex(
            module.OWNER_USER,
            r"^npi-document-[a-f0-9]{20}-owner@example[.]invalid$",
        )
        self.assertRegex(
            module.UNRELATED_USER,
            r"^npi-document-[a-f0-9]{20}-unrelated@example[.]invalid$",
        )
        self.assertNotEqual(module.OWNER_USER, module.UNRELATED_USER)
        headers = module.command_headers(
            "csrf-" + ("a" * 48),
            module.DOCUMENT_CREATE_KEY,
        )
        self.assertEqual(headers["Idempotency-Key"], module.DOCUMENT_CREATE_KEY)
        self.assertRegex(
            headers["X-Request-ID"],
            r"^[a-f0-9-]{36}$",
        )
        self.assertTrue(headers["X-Trace-ID"].startswith("trace-"))

    def test_runtime_pdf_fixture_is_structurally_complete_and_safe(self) -> None:
        content = self.module.PDF_CONTENT
        self.assertEqual(content, self.module.build_synthetic_pdf())
        self.assertTrue(content.startswith(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"))
        self.assertNotIn(b"/JS", content)
        self.assertNotIn(b"/JavaScript", content)

        startxref_match = re.search(
            rb"startxref\n([0-9]+)\n%%EOF\n\Z",
            content,
        )
        self.assertIsNotNone(startxref_match)
        xref_offset = int(startxref_match.group(1))
        self.assertEqual(content[xref_offset : xref_offset + 5], b"xref\n")

        xref_match = re.search(
            rb"xref\n0 5\n0000000000 65535 f \n"
            rb"((?:[0-9]{10} 00000 n \n){4})",
            content,
        )
        self.assertIsNotNone(xref_match)
        object_offsets = re.findall(rb"([0-9]{10}) 00000 n", xref_match.group(1))
        self.assertEqual(len(object_offsets), 4)
        for number, encoded_offset in enumerate(object_offsets, start=1):
            offset = int(encoded_offset)
            self.assertTrue(
                content[offset:].startswith(f"{number} 0 obj\n".encode())
            )

    def test_runtime_schema_inventory_is_exact_and_additive(self) -> None:
        self.assertEqual(
            set(self.module.DOCUMENT_DOCTYPES),
            {
                "NPI Document Policy",
                "NPI Document Policy Version",
                "NPI Controlled Document",
                "NPI Document Revision",
                "NPI Document Revision File",
                "NPI Document Relationship",
                "NPI Document Lock Event",
                "NPI Document Command Idempotency",
                "NPI Document Share Grant",
            },
        )
        self.assertIn("frappe.db.table_exists(doctype)", self.source)
        self.assertIn("frappe.get_meta(doctype, cached=False)", self.source)
        self.assertIn('"response_snapshot"', self.source)
        self.assertIn('"response_sealed"', self.source)
        self.assertNotIn('"response_payload"', self.source)
        self.assertNotIn("drop table", self.source.casefold())
        self.assertNotIn("truncate table", self.source.casefold())

    def test_http_failure_diagnostics_are_bounded_and_sanitized(self) -> None:
        module = self.module
        result = module.HttpResult(
            status=500,
            headers=Mock(),
            body={
                "exc_type": "DataError",
                "_server_messages": json.dumps(
                    [
                        json.dumps(
                            {
                                "message": (
                                    "<strong>Incorrect datetime value</strong> "
                                    "for column published_at"
                                )
                            }
                        )
                    ]
                ),
                "exc": "traceback contains controlled-fixture-password",
                "exception": "database exception contains a request payload",
                "cookies": "sid=synthetic-secret",
                "request": {"password": "controlled-fixture-password"},
            },
        )
        detail = module.sanitized_http_failure(result)
        self.assertEqual(
            detail,
            (
                " [exc_type=DataError; message=Incorrect datetime value "
                "for column published_at]"
            ),
        )
        for forbidden in (
            "traceback",
            "payload",
            "cookie",
            "controlled-fixture-password",
            "sid=",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, detail)
        with self.assertRaisesRegex(
            RuntimeError,
            (
                r"Document policy publication returned HTTP 500 "
                r"\[exc_type=DataError; message=Incorrect datetime value "
                r"for column published_at\]"
            ),
        ):
            module.require_http_status(
                result,
                {200},
                "Document policy publication",
            )

        sensitive = module.HttpResult(
            status=500,
            headers=Mock(),
            body={
                "exc_type": "Invalid Type With Spaces",
                "message": "Authorization token=synthetic-secret",
            },
        )
        self.assertEqual(module.sanitized_http_failure(sensitive), "")

    def test_http_failure_diagnostic_message_is_length_bounded(self) -> None:
        result = self.module.HttpResult(
            status=500,
            headers=Mock(),
            body={"message": "x" * 500},
        )
        detail = self.module.sanitized_http_failure(result)
        self.assertEqual(detail, f" [message={'x' * 240}]")

    def test_document_workspace_uses_exact_sanitized_bff_log_diagnostic(
        self,
    ) -> None:
        module = self.module
        trace_id = module.fixture_trace_id(module.DOCUMENT_CHECK_OUT_KEY)
        with tempfile.TemporaryDirectory() as temporary_directory:
            bench_path = Path(temporary_directory)
            log_directory = bench_path / "logs"
            log_directory.mkdir()
            (log_directory / "npi_core.log").write_text(
                "\n".join(
                    (
                        json.dumps(
                            {
                                "code": "UNEXPECTED_BFF_EXCEPTION",
                                "exceptionType": "WrongTraceError",
                                "traceId": "trace-" + ("0" * 32),
                            }
                        ),
                        json.dumps(
                            {
                                "code": "UNEXPECTED_BFF_EXCEPTION",
                                "exceptionType": "Unsafe Type",
                                "traceId": trace_id,
                            }
                        ),
                        (
                            "2026-07-31 ERROR npi_core "
                            + json.dumps(
                                {
                                    "code": "UNEXPECTED_BFF_EXCEPTION",
                                    "exceptionType": "ValidationError",
                                    "traceId": trace_id,
                                },
                                separators=(",", ":"),
                                sort_keys=True,
                            )
                        ),
                        (
                            "request payload password="
                            "controlled-fixture-password"
                        ),
                    )
                ),
                encoding="utf-8",
            )
            result = module.HttpResult(
                status=500,
                headers=Mock(),
                body={
                    "detail": "The server could not complete the request.",
                    "request": {
                        "password": "controlled-fixture-password",
                    },
                },
                request_id=module.fixture_request_id(
                    module.DOCUMENT_CHECK_OUT_KEY
                ),
                trace_id=trace_id,
            )
            with (
                patch.object(module, "BENCH_PATH", bench_path),
                self.assertRaises(RuntimeError) as raised,
            ):
                module.validate_document_workspace(
                    result,
                    project_id=module.fixture_id("project"),
                    expected_document_id=module.fixture_id("document"),
                )
        self.assertEqual(
            str(raised.exception),
            (
                "Document workspace returned HTTP 500 "
                "[diagnostic_code=UNEXPECTED_BFF_EXCEPTION; "
                "exc_type=ValidationError; "
                f"trace_id={trace_id}]"
            ),
        )
        for forbidden in (
            "payload",
            "password",
            "controlled-fixture-password",
            "WrongTraceError",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, str(raised.exception))

    def test_document_workspace_emits_no_body_diagnostic_without_safe_record(
        self,
    ) -> None:
        module = self.module
        trace_id = module.fixture_trace_id(module.DOCUMENT_CHECK_OUT_KEY)
        result = module.HttpResult(
            status=500,
            headers=Mock(),
            body={
                "exc_type": "ValidationError",
                "message": "raw validation text",
                "request": {
                    "password": "controlled-fixture-password",
                },
            },
            request_id=module.fixture_request_id(module.DOCUMENT_CHECK_OUT_KEY),
            trace_id=trace_id,
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            bench_path = Path(temporary_directory)
            with (
                patch.object(module, "BENCH_PATH", bench_path),
                self.assertRaises(RuntimeError) as raised,
            ):
                module.validate_document_workspace(
                    result,
                    project_id=module.fixture_id("project"),
                    expected_document_id=module.fixture_id("document"),
                )
        self.assertEqual(
            str(raised.exception),
            "Document workspace returned HTTP 500",
        )
        for forbidden in (
            "ValidationError",
            "raw validation text",
            "password",
            "controlled-fixture-password",
            trace_id,
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, str(raised.exception))

    def test_checkout_stage_diagnostic_is_allowlisted_and_preferred(
        self,
    ) -> None:
        module = self.module
        expected_codes = {
            "DOCUMENT_CHECKOUT_RECEIPT_INSERT",
            "DOCUMENT_CHECKOUT_LOCK_EVENT_INSERT",
            "DOCUMENT_CHECKOUT_PROJECTION_SAVE",
            "DOCUMENT_CHECKOUT_AUDIT_APPEND",
            "DOCUMENT_CHECKOUT_RESPONSE_BUILD",
            "DOCUMENT_CHECKOUT_RECEIPT_SEAL",
        }
        self.assertEqual(module._CHECKOUT_STAGE_DIAGNOSTIC_CODES, expected_codes)
        trace_id = module.fixture_trace_id(module.DOCUMENT_CHECK_OUT_KEY)
        stage_code = "DOCUMENT_CHECKOUT_LOCK_EVENT_INSERT"
        with tempfile.TemporaryDirectory() as temporary_directory:
            bench_path = Path(temporary_directory)
            log_directory = bench_path / "logs"
            log_directory.mkdir()
            (log_directory / "npi_core.log").write_text(
                "\n".join(
                    (
                        json.dumps(
                            {
                                "code": stage_code,
                                "exceptionType": "ValidationError",
                                "traceId": trace_id,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                        json.dumps(
                            {
                                "code": "UNREVIEWED_CHECKOUT_STAGE",
                                "exceptionType": "UnsafeError",
                                "traceId": trace_id,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                        json.dumps(
                            {
                                "code": ["DOCUMENT_CHECKOUT_RECEIPT_SEAL"],
                                "exceptionType": "UnhashableCodeError",
                                "traceId": trace_id,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                        json.dumps(
                            {
                                "code": "UNEXPECTED_BFF_EXCEPTION",
                                "exceptionType": "GenericError",
                                "traceId": trace_id,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                    )
                ),
                encoding="utf-8",
            )
            result = module.HttpResult(
                status=500,
                headers=Mock(),
                body={
                    "exc_type": "BodyError",
                    "message": "server detail must not be emitted",
                    "request": {
                        "password": "controlled-fixture-password",
                    },
                },
                request_id=module.fixture_request_id(
                    module.DOCUMENT_CHECK_OUT_KEY
                ),
                trace_id=trace_id,
            )
            with patch.object(module, "BENCH_PATH", bench_path):
                detail = module.sanitized_http_failure(result)
        self.assertEqual(
            detail,
            (
                f" [diagnostic_code={stage_code}; "
                "exc_type=ValidationError; "
                f"trace_id={trace_id}]"
            ),
        )
        for forbidden in (
            "BodyError",
            "GenericError",
            "UnsafeError",
            "UnhashableCodeError",
            "server detail",
            "password",
            "controlled-fixture-password",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, detail)

    def test_revision_stage_diagnostic_is_allowlisted_and_preferred(
        self,
    ) -> None:
        module = self.module
        expected_codes = {
            "DOCUMENT_REVISION_RECEIPT_INSERT",
            "DOCUMENT_REVISION_PRIVATE_FILE_SAVE",
            "DOCUMENT_REVISION_FILE_REVISION_INSERT",
            "DOCUMENT_REVISION_DOMAIN_APPEND",
            "DOCUMENT_REVISION_RECORD_INSERT",
            "DOCUMENT_REVISION_FILE_ASSOCIATION_INSERT",
            "DOCUMENT_REVISION_PROJECTION_SAVE",
            "DOCUMENT_REVISION_AUDIT_APPEND",
            "DOCUMENT_REVISION_RESPONSE_BUILD",
            "DOCUMENT_REVISION_RECEIPT_SEAL",
        }
        self.assertEqual(module._REVISION_STAGE_DIAGNOSTIC_CODES, expected_codes)
        trace_id = module.fixture_trace_id(module.DOCUMENT_REVISION_KEY)
        stage_code = "DOCUMENT_REVISION_PRIVATE_FILE_SAVE"
        with tempfile.TemporaryDirectory() as temporary_directory:
            bench_path = Path(temporary_directory)
            log_directory = bench_path / "logs"
            log_directory.mkdir()
            (log_directory / "npi_core.log").write_text(
                "\n".join(
                    (
                        json.dumps(
                            {
                                "code": stage_code,
                                "exceptionType": "PdfStreamError",
                                "traceId": trace_id,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                        json.dumps(
                            {
                                "code": "UNREVIEWED_REVISION_STAGE",
                                "exceptionType": "UnsafeError",
                                "traceId": trace_id,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                        json.dumps(
                            {
                                "code": "UNEXPECTED_BFF_EXCEPTION",
                                "exceptionType": "GenericError",
                                "traceId": trace_id,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                    )
                ),
                encoding="utf-8",
            )
            result = module.HttpResult(
                status=500,
                headers=Mock(),
                body={
                    "exc_type": "BodyError",
                    "message": "raw PDF parser detail must not be emitted",
                    "request": {
                        "cookie": "controlled-fixture-cookie",
                    },
                },
                request_id=module.fixture_request_id(module.DOCUMENT_REVISION_KEY),
                trace_id=trace_id,
            )
            with patch.object(module, "BENCH_PATH", bench_path):
                detail = module.sanitized_http_failure(result)
        self.assertEqual(
            detail,
            (
                f" [diagnostic_code={stage_code}; "
                "exc_type=PdfStreamError; "
                f"trace_id={trace_id}]"
            ),
        )
        for forbidden in (
            "BodyError",
            "GenericError",
            "UnsafeError",
            "raw PDF parser detail",
            "cookie",
            "controlled-fixture-cookie",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, detail)

    def test_projection_validation_substage_is_closed_and_preferred(
        self,
    ) -> None:
        module = self.module
        expected_codes = {
            "DOCUMENT_CHECKOUT_PROJECTION_NORMALIZE_INPUT",
            "DOCUMENT_CHECKOUT_PROJECTION_IMMUTABLE_IDENTITY",
            "DOCUMENT_CHECKOUT_PROJECTION_POLICY_IDENTITY",
            "DOCUMENT_CHECKOUT_PROJECTION_DOMAIN_RECONSTRUCTION",
            "DOCUMENT_CHECKOUT_PROJECTION_NORMALIZE_IDENTITY",
            "DOCUMENT_CHECKOUT_PROJECTION_VERSION",
            "DOCUMENT_CHECKOUT_PROJECTION_REVISION",
            "DOCUMENT_CHECKOUT_PROJECTION_LOCK",
            "DOCUMENT_CHECKOUT_PROJECTION_NORMALIZE_PROJECTION",
            "DOCUMENT_CHECKOUT_PROJECTION_COMMAND_GUARD",
            "DOCUMENT_CHECKOUT_PROJECTION_FRAPPE_STANDARD_VALIDATION",
            "DOCUMENT_CHECKOUT_PROJECTION_POST_SAVE_HOOK",
            "DOCUMENT_CHECKOUT_PROJECTION_SAVE_LIFECYCLE",
        }
        self.assertEqual(
            module._PROJECTION_VALIDATION_DIAGNOSTIC_CODES,
            expected_codes,
        )
        trace_id = module.fixture_trace_id(module.DOCUMENT_CHECK_OUT_KEY)
        substage_code = "DOCUMENT_CHECKOUT_PROJECTION_LOCK"
        with tempfile.TemporaryDirectory() as temporary_directory:
            bench_path = Path(temporary_directory)
            log_directory = bench_path / "logs"
            log_directory.mkdir()
            (log_directory / "npi_core.log").write_text(
                "\n".join(
                    (
                        json.dumps(
                            {
                                "code": substage_code,
                                "exceptionType": "ValidationError",
                                "traceId": trace_id,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                        json.dumps(
                            {
                                "code": "DOCUMENT_CHECKOUT_PROJECTION_SAVE",
                                "exceptionType": "ValidationError",
                                "traceId": trace_id,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                        json.dumps(
                            {
                                "code": "UNEXPECTED_BFF_EXCEPTION",
                                "exceptionType": "ValidationError",
                                "traceId": trace_id,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                    )
                ),
                encoding="utf-8",
            )
            result = module.HttpResult(
                status=500,
                headers=Mock(),
                body={
                    "message": "raw validation detail must not be emitted",
                    "request": {
                        "password": "controlled-fixture-password",
                    },
                },
                request_id=module.fixture_request_id(
                    module.DOCUMENT_CHECK_OUT_KEY
                ),
                trace_id=trace_id,
            )
            with patch.object(module, "BENCH_PATH", bench_path):
                detail = module.sanitized_http_failure(result)
        self.assertEqual(
            detail,
            (
                f" [diagnostic_code={substage_code}; "
                "exc_type=ValidationError; "
                f"trace_id={trace_id}]"
            ),
        )
        for forbidden in (
            "raw validation detail",
            "password",
            "controlled-fixture-password",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, detail)

    def test_npi_request_preserves_deterministic_diagnostic_identity(
        self,
    ) -> None:
        module = self.module
        request_id = module.fixture_request_id(module.DOCUMENT_CHECK_OUT_KEY)
        trace_id = module.fixture_trace_id(module.DOCUMENT_CHECK_OUT_KEY)
        response = module.HttpResult(
            status=500,
            headers={
                "X-Request-ID": request_id,
                "Cache-Control": "private, no-store",
            },
            body={},
        )
        with patch.object(module, "request", return_value=response):
            result = module.npi_request(
                Mock(),
                "http://127.0.0.1:8003",
                "/api/npi/v1/projects/example/documents/example:check-out",
                method="POST",
                payload={"expectedDocumentVersion": 1},
                csrf_token="csrf-" + ("a" * 48),
                idempotency_key=module.DOCUMENT_CHECK_OUT_KEY,
            )
        self.assertEqual(result.request_id, request_id)
        self.assertEqual(result.trace_id, trace_id)

    def test_bff_log_diagnostic_rejects_symlink_and_stale_oversize_tail(
        self,
    ) -> None:
        module = self.module
        trace_id = module.fixture_trace_id(module.DOCUMENT_CHECK_OUT_KEY)
        safe_record = json.dumps(
            {
                "code": "UNEXPECTED_BFF_EXCEPTION",
                "exceptionType": "ValidationError",
                "traceId": trace_id,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            bench_path = root / "bench"
            log_directory = bench_path / "logs"
            log_directory.mkdir(parents=True)
            external_log = root / "external.log"
            external_log.write_text(safe_record, encoding="utf-8")
            diagnostic_log = log_directory / "npi_core.log"
            diagnostic_log.symlink_to(external_log)
            with patch.object(module, "BENCH_PATH", bench_path):
                self.assertIsNone(
                    module._sanitized_bff_log_diagnostic(trace_id)
                )
            diagnostic_log.unlink()
            diagnostic_log.write_text(
                safe_record
                + "\n"
                + ("x" * (module._DIAGNOSTIC_LOG_TAIL_LIMIT + 1)),
                encoding="utf-8",
            )
            with patch.object(module, "BENCH_PATH", bench_path):
                self.assertIsNone(
                    module._sanitized_bff_log_diagnostic(trace_id)
                )

    def test_runtime_covers_real_file_and_authorization_boundaries(self) -> None:
        required_fragments = (
            "multipart_revision_request(",
            "observe_document_file_scan",
            "FILE_SCAN_RESULT_FLAG",
            '"scanState"] == "pending"',
            '"scanState") == "clean"',
            "binary_content_request(",
            '"X-Content-Type-Options") == "nosniff"',
            '"Referrer-Policy") == "no-referrer"',
            '"Idempotency-Replayed") == "true"',
            "DOCUMENT_VERSION_CONFLICT",
            "DOCUMENT_UNAVAILABLE",
            "AUTHENTICATION_REQUIRED",
            "externalRetrieval",
            "rawPrivateUrlExposed",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.source)
        permission_bypass_token = "ignore_" + "permissions=True"
        self.assertNotIn(permission_bypass_token, self.source)
        self.assertNotIn("allow_guest=True", self.source)
        self.assertNotIn("http://core.whjichen.cn", self.source)

    def test_project_uses_the_disposable_email_owner(self) -> None:
        response = Mock(
            status=201,
            body={
                "project": {
                    "globalId": "20873131-6923-5ad4-bf35-74efdc358224",
                    "version": 1,
                }
            },
        )
        with patch.object(
            self.module,
            "post_project",
            return_value=response,
        ) as post_project:
            self.module.create_project(
                Mock(),
                "http://127.0.0.1:8003",
                "csrf-" + ("a" * 48),
            )
        payload = post_project.call_args.args[2]
        self.assertEqual(payload["ownerUserId"], self.module.OWNER_USER)
        self.assertNotEqual(payload["ownerUserId"], "Administrator")

    def test_disposable_owner_is_cleaned_on_success_and_failure(self) -> None:
        module = self.module
        created = Mock(status=201)
        expected = {"fixtureRunId": FIXTURE_RUN_ID}
        for downstream, expected_error in (
            (Mock(return_value=expected), None),
            (Mock(side_effect=RuntimeError("fixture failed")), "fixture failed"),
        ):
            with self.subTest(expected_error=expected_error):
                with (
                    patch.object(module, "verify_fresh_namespace"),
                    patch.object(
                        module,
                        "create_disposable_user",
                        return_value=created,
                    ) as create_user,
                    patch.object(module, "validate_disposable_user") as validate_user,
                    patch.object(
                        module,
                        "_run_fresh_with_owner",
                        downstream,
                    ),
                    patch.object(
                        module,
                        "delete_disposable_user",
                    ) as delete_user,
                ):
                    if expected_error is None:
                        result = module.run_fresh(
                            Mock(),
                            "http://127.0.0.1:8003",
                            "csrf-" + ("a" * 48),
                            "controlled-fixture-password",
                        )
                        self.assertEqual(
                            result,
                            {
                                **expected,
                                "ownerFixtureCleaned": True,
                            },
                        )
                    else:
                        with self.assertRaisesRegex(RuntimeError, expected_error):
                            module.run_fresh(
                                Mock(),
                                "http://127.0.0.1:8003",
                                "csrf-" + ("a" * 48),
                                "controlled-fixture-password",
                            )
                create_user.assert_called_once()
                self.assertEqual(
                    create_user.call_args.args[2],
                    module.OWNER_USER,
                )
                validate_user.assert_called_once_with(created, module.OWNER_USER)
                delete_user.assert_called_once()
                self.assertEqual(
                    delete_user.call_args.args[2],
                    module.OWNER_USER,
                )

    def test_replay_requires_the_disposable_owner_to_be_absent(self) -> None:
        owner_still_exists = Mock(status=200)
        with (
            patch.object(
                self.module,
                "request",
                return_value=owner_still_exists,
            ),
            self.assertRaisesRegex(
                RuntimeError,
                "Project owner was not cleaned",
            ),
        ):
            self.module.run_replay(
                Mock(),
                "http://127.0.0.1:8003",
                "csrf-" + ("a" * 48),
            )

    def test_runtime_shell_migrates_twice_and_restores_route_switch(self) -> None:
        required_fragments = (
            '"--document-only"',
            "for _migration_attempt in 1 2",
            'npi_p5_01_routes_disabled "${value}"',
            "run_document_runtime_verifier fresh",
            "run_document_route_probe disabled",
            "run_document_route_probe recovered",
            "run_document_runtime_verifier replay-only",
            "restore_document_route_switch",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.shell)
        self.assertIn(
            'document_route_disable_original_state}" != "absent"',
            self.shell,
        )

    def test_site_init_preserves_apps_registry_line_boundaries(self) -> None:
        site_init = (ROOT / "scripts" / "init-npi-site.sh").read_text(
            encoding="utf-8"
        )
        required_fragments = (
            'local apps_file="${bench_path}/sites/apps.txt"',
            '[[ -L "${apps_file}" || ! -f "${apps_file}" ]]',
            "Bench application registry must be a physical file: ${apps_file}",
            'tail -c 1 "${apps_file}" | od -An -tx1 | tr -d \'[:space:]\'',
            '!= "0a"',
            'printf \'\\n\' >>"${apps_file}"',
            'grep -Fqx "${application}" "${apps_file}"',
            'printf \'%s\\n\' "${application}" >>"${apps_file}"',
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, site_init)
        self.assertLess(
            site_init.index('printf \'\\n\' >>"${apps_file}"'),
            site_init.index('printf \'%s\\n\' "${application}" >>"${apps_file}"'),
        )

    def test_runtime_uses_only_the_fixed_disposable_site(self) -> None:
        required_fragments = (
            'SITE_NAME = "npi.localhost"',
            'DATABASE_NAME = "npi_one_runtime"',
            'RUNTIME_MARKER = "npi-one-local-runtime-disposable-v1"',
            "frappe.local.site == SITE_NAME",
            "frappe.conf.get(\"npi_runtime_disposable_marker\") == RUNTIME_MARKER",
            "BENCH_PATH.resolve() == BENCH_PATH",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.source)

    def test_manual_ci_lane_uses_the_pinned_disposable_runtime(self) -> None:
        toolchain = dict(
            line.split("=", 1)
            for line in TOOLCHAIN.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
        )
        runtime_job = self.workflow.split("\n  document_runtime:\n", 1)[1]
        required_fragments = (
            "if: github.event_name == 'workflow_dispatch'",
            "timeout-minutes: 45",
            f'"frappe-bench=={toolchain["BENCH_EXPECTED_VERSION"]}"',
            f'"uv=={toolchain["UV_EXPECTED_VERSION"]}"',
            'from importlib.metadata import version',
            'version("frappe-bench")',
            'version("uv")',
            f'("{toolchain["BENCH_EXPECTED_VERSION"]}", "{toolchain["UV_EXPECTED_VERSION"]}")',
            f'test "$(yarn --version)" = "{toolchain["YARN_EXPECTED_VERSION"]}"',
            "bash scripts/init-frappe-bench.sh",
            "bash scripts/init-npi-site.sh",
            "bash scripts/verify-frappe-runtime.sh --document-only",
            "site=npi.localhost",
            "database=npi_one_runtime",
            "runtime_marker=npi-one-local-runtime-disposable-v1",
            f'frappe_commit={toolchain["FRAPPE_COMMIT"]}',
            "p5-document-runtime-${{ github.run_id }}",
            "docker compose down --volumes",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, runtime_job)
        self.assertNotIn("secrets.", runtime_job)
        self.assertNotIn("continue-on-error", runtime_job)
        self.assertNotIn("core.whjichen.cn", runtime_job)
        self.assertNotIn("npm install --global", runtime_job)
        self.assertNotIn("--dangerously-allow-all-scripts", runtime_job)


if __name__ == "__main__":
    unittest.main()
