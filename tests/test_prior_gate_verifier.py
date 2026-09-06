from __future__ import annotations

import unittest
import urllib.request
from unittest.mock import patch

from scripts.verify_prior_gate import (
    ExactOriginRedirectHandler,
    PriorGateError,
    classify_diagnostic_paths,
    plan_diagnostic_gate,
    validate_diagnostic_gate,
    validate_prior_gate,
    verify_diagnostic_gate,
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
        "head_branch": "codex/npi-v1.2-implementation",
        "head_repository": {"full_name": "owner/repository"},
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

    def test_diagnostic_paths_are_strictly_allowed_denied_or_unknown(self) -> None:
        allowed = classify_diagnostic_paths(
            [
                "scripts/verify_item_publish_runtime.py",
                "tests/test_phase8_item_publish_runtime_verifier.py",
                "implementation/ACTIVE_EXECUTION_GOAL.md",
            ]
        )
        denied = classify_diagnostic_paths(["apps/npi_core/npi_core/change_control/domain.py"])
        unknown = classify_diagnostic_paths(["README.md"])
        self.assertEqual(allowed["classification"], "ALLOW")
        self.assertEqual(allowed["changed_path_count"], 3)
        self.assertEqual(denied["classification"], "DENY")
        self.assertEqual(unknown["classification"], "UNKNOWN")

    def test_diagnostic_gate_reuses_only_latest_successful_ordinary_run(self) -> None:
        result = validate_diagnostic_gate(
            run_fixture(),
            jobs_fixture(),
            {"workflow_runs": [{"id": RUN_ID, "head_sha": SHA}]},
            expected_run_id=RUN_ID,
            current_sha="8" * 40,
            current_branch="codex/npi-v1.2-implementation",
            repository="owner/repository",
            changed_paths=["scripts/verify_item_publish_runtime.py"],
        )
        self.assertEqual(result["result"], "DIAGNOSTIC_FAST_PATH")
        self.assertFalse(result["run_full"])
        self.assertFalse(result["eligible_for_merge"])
        self.assertNotIn("scripts/verify_item_publish_runtime.py", str(result))
        for latest in (
            {"workflow_runs": []},
            {"workflow_runs": [{"id": RUN_ID + 1, "head_sha": SHA}]},
        ):
            with self.subTest(latest=latest), self.assertRaises(PriorGateError):
                validate_diagnostic_gate(
                    run_fixture(),
                    jobs_fixture(),
                    latest,
                    expected_run_id=RUN_ID,
                    current_sha="8" * 40,
                    current_branch="codex/npi-v1.2-implementation",
                    repository="owner/repository",
                    changed_paths=["scripts/verify_item_publish_runtime.py"],
                )

    def test_product_or_unknown_diagnostic_change_falls_back_to_full_ci(self) -> None:
        for path in ("apps/npi_core/domain.py", "README.md"):
            with self.subTest(path=path), patch(
                "scripts.verify_prior_gate.verify_diagnostic_gate",
                side_effect=PriorGateError("diagnostic changes are denied or unknown"),
            ):
                result = plan_diagnostic_gate(
                    repository="owner/repository",
                    run_id=str(RUN_ID),
                    current_sha="8" * 40,
                    current_branch="codex/npi-v1.2-implementation",
                    token="token",
                    root=None,
                )
            self.assertEqual(result["result"], "FULL_CI_FALLBACK")
            self.assertTrue(result["run_full"])
            self.assertNotIn(path, str(result))

    def test_diagnostic_network_reads_and_git_diff_are_bounded(self) -> None:
        with patch(
            "scripts.verify_prior_gate.request_json",
            side_effect=[
                run_fixture(),
                jobs_fixture(),
                {"workflow_runs": [{"id": RUN_ID, "head_sha": SHA}]},
            ],
        ) as request, patch(
            "scripts.verify_prior_gate.git_changed_paths",
            return_value=["scripts/verify_item_publish_runtime.py"],
        ) as changed:
            result = verify_diagnostic_gate(
                repository="owner/repository",
                run_id=str(RUN_ID),
                current_sha="8" * 40,
                current_branch="codex/npi-v1.2-implementation",
                token="token",
                root=None,
            )
        self.assertEqual(result["result"], "DIAGNOSTIC_FAST_PATH")
        self.assertEqual(request.call_count, 3)
        changed.assert_called_once_with(SHA, "8" * 40, root=None)

    def test_diagnostic_gate_rejects_a_different_current_branch(self) -> None:
        with self.assertRaisesRegex(PriorGateError, "different branch"):
            validate_diagnostic_gate(
                run_fixture(),
                jobs_fixture(),
                {"workflow_runs": [{"id": RUN_ID, "head_sha": SHA}]},
                expected_run_id=RUN_ID,
                current_sha="8" * 40,
                current_branch="codex/other-branch",
                repository="owner/repository",
                changed_paths=["scripts/verify_item_publish_runtime.py"],
            )

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
