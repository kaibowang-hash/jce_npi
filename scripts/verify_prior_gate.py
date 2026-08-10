#!/usr/bin/env python3
"""Verify that a Level 2 Site run reuses one exact successful PR Gate."""

from __future__ import annotations

import argparse
import json
import os
import re
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
    parser.add_argument("--repository", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
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
