#!/usr/bin/env python3
"""Verify that a Level 2 Site run reuses one exact successful PR Gate."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Mapping


API_ORIGIN = "https://api.github.com"
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA = re.compile(r"^[0-9a-f]{40}$")
RUN_ID = re.compile(r"^[1-9][0-9]{0,19}$")
REQUIRED_JOBS = {"repository", "frontend", "secret_scan", "visual"}
DIAGNOSTIC_ALLOWED_PATHS = (
    "implementation/ACTIVE_EXECUTION_GOAL.md",
    "implementation/AUTOPILOT_CONTROLLER.md",
    "implementation/CURRENT_TASK.json",
    "implementation/NEXT_ACTION.md",
    "implementation/PHASE_STATUS.yaml",
    "implementation/evidence/phase-*/*diagnostic*.md",
    "scripts/verify-frappe-runtime.sh",
    "scripts/verify_*_runtime.py",
    "tests/test_current_task_verifier.py",
    "tests/test_phase*_runtime_verifier.py",
    "tests/test_phase*_security.py",
)
DIAGNOSTIC_DENIED_PREFIXES = (
    ".github/",
    "apps/",
    "contracts/",
    "frontend/",
    "patches/",
)


class PriorGateError(RuntimeError):
    """Raised when prior ordinary-Gate evidence cannot authorize reuse."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PriorGateError(message)


class ExactOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Retain authorization only across redirects on the exact API origin."""

    def redirect_request(self, request, fp, code, msg, headers, new_url):
        parsed = urllib.parse.urlsplit(new_url)
        require(
            (parsed.scheme, parsed.hostname, parsed.port) == ("https", "api.github.com", None),
            "GitHub API redirect left the exact authorized origin",
        )
        return super().redirect_request(request, fp, code, msg, headers, new_url)


def request_json(path: str, token: str) -> Mapping[str, Any]:
    require(path.startswith("/repos/"), "GitHub API path is outside the repository scope")
    require(token and token.strip() == token, "GITHUB_TOKEN is unavailable")
    request = urllib.request.Request(
        f"{API_ORIGIN}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    opener = urllib.request.build_opener(ExactOriginRedirectHandler())
    try:
        with opener.open(request, timeout=30) as response:
            require(response.status == 200, f"GitHub API returned HTTP {response.status}")
            value = json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise PriorGateError(f"cannot read prior Gate evidence: {exc}") from exc
    require(type(value) is dict, "GitHub API evidence must be one JSON object")
    return value


def validate_prior_gate(
    run: Mapping[str, Any],
    jobs_response: Mapping[str, Any],
    *,
    expected_run_id: int,
    expected_sha: str,
) -> dict[str, object]:
    require(run.get("id") == expected_run_id, "prior Gate run identity drifted")
    require(run.get("head_sha") == expected_sha, "prior Gate SHA differs from GITHUB_SHA")
    require(run.get("event") == "pull_request", "prior Gate must be a pull-request run")
    require(run.get("status") == "completed", "prior Gate is not complete")
    require(run.get("conclusion") == "success", "prior Gate did not pass")
    require(
        run.get("path") == ".github/workflows/ci.yml",
        "prior Gate used a different workflow",
    )

    jobs = jobs_response.get("jobs")
    require(type(jobs) is list, "prior Gate jobs are unavailable")
    require(jobs_response.get("total_count") == len(jobs), "prior Gate jobs were truncated")
    conclusions: dict[str, str] = {}
    for job in jobs:
        require(type(job) is dict, "prior Gate job evidence is malformed")
        name = job.get("name")
        if name not in REQUIRED_JOBS:
            continue
        require(name not in conclusions, f"duplicate prior Gate job: {name}")
        conclusion = job.get("conclusion")
        require(type(conclusion) is str, f"prior Gate job has no conclusion: {name}")
        conclusions[name] = conclusion
    require(set(conclusions) == REQUIRED_JOBS, "prior Gate is missing required ordinary jobs")
    failed = sorted(name for name, conclusion in conclusions.items() if conclusion != "success")
    require(not failed, f"prior Gate jobs did not pass: {', '.join(failed)}")
    return {
        "result": "PASS",
        "run_id": expected_run_id,
        "head_sha": expected_sha,
        "event": "pull_request",
        "workflow": ".github/workflows/ci.yml",
        "required_jobs": sorted(REQUIRED_JOBS),
    }


def classify_diagnostic_paths(paths: list[str]) -> dict[str, object]:
    """Classify without returning path values in the safe result."""
    require(len(set(paths)) == len(paths), "diagnostic changed paths contain duplicates")
    allowed = denied = unknown = 0
    for path in paths:
        require(
            path
            and path.strip() == path
            and not path.startswith(("/", "../"))
            and "/../" not in path
            and "\n" not in path,
            "diagnostic changed path is unsafe",
        )
        if any(path.startswith(prefix) for prefix in DIAGNOSTIC_DENIED_PREFIXES):
            denied += 1
        elif any(fnmatch.fnmatchcase(path, pattern) for pattern in DIAGNOSTIC_ALLOWED_PATHS):
            allowed += 1
        else:
            unknown += 1
    classification = "ALLOW" if denied == 0 and unknown == 0 else (
        "DENY" if denied else "UNKNOWN"
    )
    return {
        "classification": classification,
        "changed_path_count": len(paths),
        "allowed_path_count": allowed,
        "denied_path_count": denied,
        "unknown_path_count": unknown,
    }


def validate_diagnostic_gate(
    run: Mapping[str, Any],
    jobs_response: Mapping[str, Any],
    latest_response: Mapping[str, Any],
    *,
    expected_run_id: int,
    current_sha: str,
    current_branch: str,
    repository: str,
    changed_paths: list[str],
) -> dict[str, object]:
    prior_sha = run.get("head_sha")
    require(type(prior_sha) is str and SHA.fullmatch(prior_sha) is not None, "prior Gate SHA is invalid")
    validated = validate_prior_gate(
        run,
        jobs_response,
        expected_run_id=expected_run_id,
        expected_sha=prior_sha,
    )
    require(SHA.fullmatch(current_sha) is not None, "current SHA must be one full lowercase SHA")
    head_repository = run.get("head_repository")
    require(
        type(head_repository) is dict and head_repository.get("full_name") == repository,
        "prior Gate used a different head repository",
    )
    head_branch = run.get("head_branch")
    require(
        type(head_branch) is str
        and head_branch
        and head_branch.strip() == head_branch
        and ".." not in head_branch,
        "prior Gate branch is invalid",
    )
    require(current_branch == head_branch, "prior Gate used a different branch")
    latest_runs = latest_response.get("workflow_runs")
    require(type(latest_runs) is list and latest_runs, "latest ordinary Gate is unavailable")
    latest = latest_runs[0]
    require(type(latest) is dict, "latest ordinary Gate evidence is malformed")
    require(latest.get("id") == expected_run_id, "supplied Gate is not the latest successful ordinary run")
    require(latest.get("head_sha") == prior_sha, "latest ordinary Gate SHA drifted")

    classification = classify_diagnostic_paths(changed_paths)
    require(
        classification["classification"] == "ALLOW",
        "diagnostic changes are denied or unknown",
    )
    return {
        **validated,
        **classification,
        "result": "DIAGNOSTIC_FAST_PATH",
        "prior_head_sha": prior_sha,
        "current_head_sha": current_sha,
        "run_full": False,
        "eligible_for_merge": False,
        "eligible_for_release": False,
    }


def git_changed_paths(base_sha: str, current_sha: str, *, root: Path) -> list[str]:
    for sha in (base_sha, current_sha):
        require(SHA.fullmatch(sha) is not None, "Git comparison SHA is invalid")
        present = subprocess.run(
            ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
            cwd=root,
            check=False,
            capture_output=True,
        )
        require(present.returncode == 0, "Git comparison commit is unavailable")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", base_sha, current_sha],
        cwd=root,
        check=False,
        capture_output=True,
    )
    require(ancestor.returncode == 0, "prior ordinary Gate is not an ancestor")
    diff = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=ACMRTUXB",
            "-z",
            base_sha,
            current_sha,
        ],
        cwd=root,
        check=False,
        capture_output=True,
    )
    require(diff.returncode == 0, "cannot classify diagnostic changed paths")
    try:
        return [value.decode("utf-8") for value in diff.stdout.split(b"\0") if value]
    except UnicodeDecodeError as exc:
        raise PriorGateError("diagnostic changed path is not UTF-8") from exc


def verify_diagnostic_gate(
    *,
    repository: str,
    run_id: str,
    current_sha: str,
    current_branch: str,
    token: str,
    root: Path,
) -> dict[str, object]:
    require(REPOSITORY.fullmatch(repository) is not None, "repository identity is invalid")
    require(
        all(part not in {".", ".."} for part in repository.split("/")),
        "repository identity is invalid",
    )
    require(RUN_ID.fullmatch(run_id) is not None, "ordinary_run_id must be a positive integer")
    require(SHA.fullmatch(current_sha) is not None, "current SHA must be one full lowercase SHA")
    require(
        current_branch
        and current_branch.strip() == current_branch
        and ".." not in current_branch
        and "\n" not in current_branch,
        "current branch is invalid",
    )
    numeric_run_id = int(run_id)
    run = request_json(f"/repos/{repository}/actions/runs/{run_id}", token)
    jobs = request_json(
        f"/repos/{repository}/actions/runs/{run_id}/jobs?filter=latest&per_page=100",
        token,
    )
    prior_sha = run.get("head_sha")
    require(type(prior_sha) is str and SHA.fullmatch(prior_sha) is not None, "prior Gate SHA is invalid")
    head_branch = run.get("head_branch")
    require(type(head_branch) is str and head_branch, "prior Gate branch is invalid")
    query = urllib.parse.urlencode(
        {
            "branch": head_branch,
            "event": "pull_request",
            "status": "success",
            "per_page": "100",
        }
    )
    latest = request_json(
        f"/repos/{repository}/actions/workflows/ci.yml/runs?{query}",
        token,
    )
    paths = git_changed_paths(prior_sha, current_sha, root=root)
    return validate_diagnostic_gate(
        run,
        jobs,
        latest,
        expected_run_id=numeric_run_id,
        current_sha=current_sha,
        current_branch=current_branch,
        repository=repository,
        changed_paths=paths,
    )


def plan_diagnostic_gate(**arguments: object) -> dict[str, object]:
    try:
        return verify_diagnostic_gate(**arguments)  # type: ignore[arg-type]
    except (PriorGateError, OSError, UnicodeError):
        return {
            "result": "FULL_CI_FALLBACK",
            "reason": "PRIOR_GATE_OR_CHANGED_PATHS_UNVERIFIED",
            "run_full": True,
            "eligible_for_merge": False,
            "eligible_for_release": False,
        }


def verify_prior_gate(
    *,
    repository: str,
    run_id: str,
    sha: str,
    token: str,
) -> dict[str, object]:
    require(REPOSITORY.fullmatch(repository) is not None, "repository identity is invalid")
    require(
        all(part not in {".", ".."} for part in repository.split("/")),
        "repository identity is invalid",
    )
    require(RUN_ID.fullmatch(run_id) is not None, "ordinary_run_id must be a positive integer")
    require(SHA.fullmatch(sha) is not None, "GITHUB_SHA must be one full lowercase SHA")
    numeric_run_id = int(run_id)
    run = request_json(f"/repos/{repository}/actions/runs/{run_id}", token)
    jobs = request_json(
        f"/repos/{repository}/actions/runs/{run_id}/jobs?filter=latest&per_page=100",
        token,
    )
    return validate_prior_gate(
        run,
        jobs,
        expected_run_id=numeric_run_id,
        expected_sha=sha,
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("exact", "diagnostic"), default="exact")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--branch")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--github-output", type=Path)
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    if arguments.mode == "diagnostic":
        if arguments.branch is None:
            print("diagnostic Gate planning failed: --branch is required", file=sys.stderr)
            return 1
        result = plan_diagnostic_gate(
            repository=arguments.repository,
            run_id=arguments.run_id,
            current_sha=arguments.sha,
            current_branch=arguments.branch,
            token=os.environ.get("GITHUB_TOKEN", ""),
            root=Path(__file__).resolve().parents[1],
        )
        try:
            if arguments.output is not None:
                arguments.output.parent.mkdir(parents=True, exist_ok=True)
                arguments.output.write_text(
                    json.dumps(result, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
            if arguments.github_output is not None:
                with arguments.github_output.open("a", encoding="utf-8") as stream:
                    stream.write(f"run_full={str(result['run_full']).lower()}\n")
                    stream.write(
                        "fast_path="
                        f"{str(result['result'] == 'DIAGNOSTIC_FAST_PATH').lower()}\n"
                    )
        except (OSError, UnicodeError) as exc:
            print(f"diagnostic Gate planning failed: {exc}", file=sys.stderr)
            return 1
        print(f"diagnostic Gate plan: {result['result']}")
        return 0
    try:
        result = verify_prior_gate(
            repository=arguments.repository,
            run_id=arguments.run_id,
            sha=arguments.sha,
            token=os.environ.get("GITHUB_TOKEN", ""),
        )
        if arguments.output is not None:
            arguments.output.parent.mkdir(parents=True, exist_ok=True)
            arguments.output.write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    except (PriorGateError, OSError, UnicodeError) as exc:
        print(f"prior Gate verification failed: {exc}", file=sys.stderr)
        return 1
    print(
        "prior Gate verification passed: "
        f"run {result['run_id']} at {result['head_sha']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
