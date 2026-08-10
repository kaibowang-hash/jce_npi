from __future__ import annotations

import unittest
import urllib.request
from unittest.mock import patch

from scripts.verify_prior_gate import (
    ExactOriginRedirectHandler,
    PriorGateError,
    validate_prior_gate,
    verify_prior_gate,
)


RUN_ID = 31380834335
SHA = "7" * 40


def run_fixture(**changes: object) -> dict[str, object]:
    return {
        "id": RUN_ID,
        "head_sha": SHA,
        "event": "pull_request",
        "status": "completed",
        "conclusion": "success",
        "path": ".github/workflows/ci.yml",
        **changes,
    }


def jobs_fixture(**conclusions: str) -> dict[str, object]:
    values = {
        "repository": "success",
        "frontend": "success",
        "secret_scan": "success",
        "visual": "success",
        **conclusions,
    }
    jobs = [{"name": name, "conclusion": result} for name, result in values.items()]
    return {"total_count": len(jobs), "jobs": jobs}


class PriorGateVerifierTest(unittest.TestCase):
    def test_exact_successful_pull_request_gate_passes(self) -> None:
        result = validate_prior_gate(
            run_fixture(),
            jobs_fixture(),
            expected_run_id=RUN_ID,
            expected_sha=SHA,
        )
        self.assertEqual(result["result"], "PASS")
        self.assertEqual(
            result["required_jobs"],
            ["frontend", "repository", "secret_scan", "visual"],
        )

    def test_run_identity_sha_trigger_and_conclusion_fail_closed(self) -> None:
        variants = (
            {"id": RUN_ID + 1},
            {"head_sha": "8" * 40},
            {"event": "workflow_dispatch"},
            {"status": "in_progress"},
            {"conclusion": "failure"},
            {"path": ".github/workflows/other.yml"},
        )
        for changes in variants:
            with self.subTest(changes=changes), self.assertRaises(PriorGateError):
                validate_prior_gate(
                    run_fixture(**changes),
                    jobs_fixture(),
                    expected_run_id=RUN_ID,
                    expected_sha=SHA,
                )

    def test_missing_failed_duplicate_or_truncated_job_fails_closed(self) -> None:
        missing = jobs_fixture()
        missing["jobs"] = missing["jobs"][:-1]
        missing["total_count"] = len(missing["jobs"])
        duplicate = jobs_fixture()
        duplicate["jobs"].append({"name": "repository", "conclusion": "success"})
        duplicate["total_count"] = len(duplicate["jobs"])
        truncated = jobs_fixture()
        truncated["total_count"] = 5
        for jobs in (missing, jobs_fixture(frontend="failure"), duplicate, truncated):
            with self.subTest(jobs=jobs), self.assertRaises(PriorGateError):
                validate_prior_gate(
                    run_fixture(),
                    jobs,
                    expected_run_id=RUN_ID,
                    expected_sha=SHA,
                )

    def test_input_validation_happens_before_network(self) -> None:
        for repository, run_id, sha in (
            ("../escape", str(RUN_ID), SHA),
            ("owner/repository", "0", SHA),
            ("owner/repository", str(RUN_ID), "short"),
        ):
            with self.subTest(repository=repository, run_id=run_id, sha=sha):
                with patch("scripts.verify_prior_gate.request_json") as request:
                    with self.assertRaises(PriorGateError):
                        verify_prior_gate(
                            repository=repository,
                            run_id=run_id,
                            sha=sha,
                            token="token",
                        )
                    request.assert_not_called()

    def test_network_evidence_is_validated_after_two_scoped_reads(self) -> None:
        with patch(
            "scripts.verify_prior_gate.request_json",
            side_effect=[run_fixture(), jobs_fixture()],
        ) as request:
            result = verify_prior_gate(
                repository="owner/repository",
                run_id=str(RUN_ID),
                sha=SHA,
                token="token",
            )
        self.assertEqual(result["run_id"], RUN_ID)
        self.assertEqual(request.call_count, 2)

    def test_authorized_redirect_is_confined_to_exact_github_api_origin(self) -> None:
        handler = ExactOriginRedirectHandler()
        request = urllib.request.Request(
            "https://api.github.com/repos/owner/repository/actions/runs/1",
            headers={"Authorization": "Bearer sentinel-token"},
        )
        redirected = handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://api.github.com/repos/owner/repository/actions/runs/2",
        )
        self.assertEqual(
            redirected.get_header("Authorization"),
            "Bearer sentinel-token",
        )
        for unsafe_url in (
            "http://api.github.com/steal",
            "https://api.github.com:443/steal",
            "https://api.github.com.evil.example/steal",
            "https://github.com/steal",
        ):
            with self.subTest(url=unsafe_url), self.assertRaises(PriorGateError):
                handler.redirect_request(
                    request,
                    None,
                    302,
                    "Found",
                    {},
                    unsafe_url,
                )


if __name__ == "__main__":
    unittest.main()
