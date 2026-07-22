#!/usr/bin/env python3
"""Validate the pinned NPI One devcontainer without third-party Python packages."""

from __future__ import annotations

import gzip
import io
import json
import re
import shlex
import subprocess
import tarfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEVCONTAINER_DIR = REPO_ROOT / ".devcontainer"
USER_AGENT = "npi-one-devcontainer-verifier/1.0"
OCI_ACCEPT = ", ".join(
    (
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    )
)


class VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"Invalid JSON in {path.relative_to(REPO_ROOT)}: {exc}") from exc
    require(isinstance(value, dict), f"{path.relative_to(REPO_ROOT)} must contain a JSON object")
    return value


def parse_toolchain(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        require("=" in line, f"Invalid toolchain line {line_number}")
        key, value = line.split("=", 1)
        require(bool(key) and bool(value), f"Empty toolchain key or value on line {line_number}")
        require(key not in values, f"Duplicate toolchain key: {key}")
        values[key] = value
    return values


def parse_pinned_from(dockerfile: str) -> tuple[str, str, str]:
    match = re.search(
        r"^FROM\s+([^\s@:]+(?:/[^\s@:]+)+):([^\s@]+)@sha256:([0-9a-f]{64})\s*$",
        dockerfile,
        re.MULTILINE,
    )
    require(match is not None, "Dockerfile FROM must use an explicit tag and sha256 digest")
    assert match is not None
    return match.group(1), match.group(2), match.group(3)


def validate_apt_source_sanitization(dockerfile: str) -> None:
    apt_update = dockerfile.find("apt-get update")
    main_list_cleanup = dockerfile.find("sed -i '/dl\\.yarnpkg\\.com\\/debian/d' /etc/apt/sources.list")
    fragment_cleanup = dockerfile.find(
        "find /etc/apt/sources.list.d -maxdepth 1 -type f -iname '*yarn*' -delete"
    )
    require(apt_update >= 0, "Dockerfile must refresh APT package indexes")
    require(
        0 <= main_list_cleanup < apt_update,
        "The Yarn repository must be removed from /etc/apt/sources.list before apt-get update",
    )
    require(
        0 <= fragment_cleanup < apt_update,
        "Yarn source fragments must be deleted before apt-get update",
    )

    lowered = dockerfile.lower()
    prohibited = {
        "dl.yarnpkg.com": "The invalid Yarn APT URL must not appear literally in the build",
        "trusted=yes": "APT trusted=yes is prohibited",
        "--allow-unauthenticated": "Unauthenticated APT packages are prohibited",
        "allowinsecurerepositories": "Insecure APT repositories are prohibited",
        "allowunauthenticated": "Unauthenticated APT configuration is prohibited",
    }
    for pattern, message in prohibited.items():
        require(pattern not in lowered, message)
    for command in re.findall(r"apt-get\s+(?:update|install)[^;\n]*", dockerfile):
        require("|| true" not in command, "APT failures must not be ignored")


def git_mode(path: Path) -> str:
    relative = path.relative_to(REPO_ROOT).as_posix()
    result = subprocess.run(
        ["git", "ls-files", "--stage", "--", relative],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    require(bool(result.stdout.strip()), f"Required script is not tracked: {relative}")
    return result.stdout.split()[0]


def validate_bootstrap_vite_installation(bootstrap: str) -> None:
    require(
        'installed_vite_version="${installed_vite%% *}"' in bootstrap,
        "Bootstrap must isolate the Vite version token",
    )
    require(
        '[[ "${installed_vite_version}" != "vite/${VITE_EXPECTED_VERSION}" ]]' in bootstrap,
        "Bootstrap must compare the complete Vite version token",
    )
    require(
        'npm_prefix="$("${npm_command}" prefix --global)"' in bootstrap,
        "Bootstrap must resolve the Node Feature npm global prefix",
    )
    require(
        '[[ ! -d "${npm_prefix}" || ! -w "${npm_prefix}" ]]' in bootstrap,
        "Bootstrap must reject a non-writable npm global prefix",
    )
    require(
        '"${npm_command}" install --global "vite@${VITE_EXPECTED_VERSION}"' in bootstrap,
        "Pinned Vite installation path is missing",
    )
    require(
        'sudo "${npm_command}"' not in bootstrap,
        "Vite installation must not run npm with a sudo-sanitized Node PATH",
    )


def validate_bootstrap_uv_installation(bootstrap: str) -> None:
    require('/opt/frappe-bench/bin/uv' in bootstrap, "Bootstrap must use Bench's uv dependency")
    require('/opt/frappe-bench/bin/pip' in bootstrap, "Bootstrap must use Bench's pinned pip")
    require(
        '"uv==${UV_EXPECTED_VERSION}"' in bootstrap,
        "Bootstrap must enforce the selected uv version",
    )
    require('/usr/local/bin/uv' in bootstrap, "Bootstrap must expose uv on the lifecycle PATH")


def validate_local_configuration() -> tuple[dict[str, Any], dict[str, str], tuple[str, str, str]]:
    config_path = DEVCONTAINER_DIR / "devcontainer.json"
    lock_path = DEVCONTAINER_DIR / "devcontainer-lock.json"
    toolchain_path = DEVCONTAINER_DIR / "toolchain.env"
    config = read_json(config_path)
    lock = read_json(lock_path)
    toolchain = parse_toolchain(toolchain_path.read_text(encoding="utf-8"))

    required_toolchain = {
        "PYTHON_EXPECTED_MAJOR_MINOR",
        "NODE_EXPECTED_VERSION",
        "NPM_EXPECTED_VERSION",
        "YARN_EXPECTED_VERSION",
        "DOCKER_EXPECTED_VERSION",
        "BENCH_EXPECTED_VERSION",
        "UV_EXPECTED_VERSION",
        "VITE_EXPECTED_VERSION",
        "FRAPPE_BRANCH",
        "FRAPPE_COMMIT",
    }
    require(toolchain.keys() >= required_toolchain, "Toolchain definition is incomplete")
    require(toolchain["FRAPPE_BRANCH"] == "version-15", "Frappe branch must remain version-15")
    require(bool(re.fullmatch(r"[0-9a-f]{40}", toolchain["FRAPPE_COMMIT"])), "Invalid Frappe commit")

    build = config.get("build")
    require(isinstance(build, dict), "devcontainer.json requires a build object")
    dockerfile_value = build.get("dockerfile")
    context_value = build.get("context")
    require(isinstance(dockerfile_value, str), "build.dockerfile must be a path")
    require(isinstance(context_value, str), "build.context must be a path")
    dockerfile_path = (DEVCONTAINER_DIR / dockerfile_value).resolve()
    context_path = (DEVCONTAINER_DIR / context_value).resolve()
    require(dockerfile_path.is_file(), f"Dockerfile does not exist: {dockerfile_value}")
    require(context_path.is_dir(), f"Build context does not exist: {context_value}")
    require(context_path == REPO_ROOT, "Devcontainer build context must be the repository root")
    require(dockerfile_path.is_relative_to(context_path), "Dockerfile must be inside the build context")

    require(config.get("remoteUser") == "vscode", "remoteUser must be vscode")
    require(config.get("postCreateCommand") == "bash scripts/bootstrap-dev.sh", "Unexpected postCreateCommand")
    require(
        config.get("containerEnv", {}).get("NPI_TOOLCHAIN_FILE")
        == "${containerWorkspaceFolder}/.devcontainer/toolchain.env",
        "NPI_TOOLCHAIN_FILE must resolve inside the workspace",
    )

    command = shlex.split(config["postCreateCommand"])
    require(command == ["bash", "scripts/bootstrap-dev.sh"], "postCreateCommand must invoke the bootstrap script")
    script_paths = sorted((REPO_ROOT / "scripts").glob("*.sh")) + [
        REPO_ROOT / "scripts/verify_devcontainer.py"
    ]
    required_scripts = {
        REPO_ROOT / "scripts/bootstrap-dev.sh",
        REPO_ROOT / "scripts/init-frappe-bench.sh",
        REPO_ROOT / "scripts/verify-dev-config.sh",
        REPO_ROOT / "scripts/verify-dev-environment.sh",
        REPO_ROOT / "scripts/verify.sh",
        REPO_ROOT / "scripts/verify_devcontainer.py",
    }
    require(set(script_paths) >= required_scripts, "A required development script is missing")
    for script_path in script_paths:
        require(git_mode(script_path) == "100755", f"Script is not executable in Git: {script_path.name}")

    features = config.get("features")
    require(isinstance(features, dict), "devcontainer.json requires a features object")
    node_ref = "ghcr.io/devcontainers/features/node:2.1.0"
    docker_ref = "ghcr.io/devcontainers/features/docker-in-docker:3.0.1"
    require(set(features) == {node_ref, docker_ref}, "Unexpected or missing Dev Container Feature")
    node_options = features[node_ref]
    require(node_options.get("version") == toolchain["NODE_EXPECTED_VERSION"].removeprefix("v"), "Node pin mismatch")
    require(node_options.get("npmVersion") == toolchain["NPM_EXPECTED_VERSION"], "npm pin mismatch")
    require(node_options.get("nodeGypDependencies") is True, "node-gyp dependencies must be enabled")
    require(node_options.get("installYarnUsingApt") is False, "Yarn APT installation must remain disabled")
    docker_options = features[docker_ref]
    require(docker_options.get("version") == toolchain["DOCKER_EXPECTED_VERSION"], "Docker pin mismatch")
    require(docker_options.get("dockerDashComposeVersion") == "v2", "Docker Compose v2 must be selected")
    require(docker_options.get("moby") is True, "The approved Moby distribution must be explicit")

    locked_features = lock.get("features")
    require(isinstance(locked_features, dict), "Dev Container Feature lockfile is incomplete")
    require(set(locked_features) == set(features), "Feature lockfile does not match devcontainer.json")
    for feature_ref, locked in locked_features.items():
        require(bool(re.fullmatch(r"sha256:[0-9a-f]{64}", locked.get("integrity", ""))), f"Invalid lock digest for {feature_ref}")
        require(locked.get("resolved", "").endswith("@" + locked["integrity"]), f"Resolved digest mismatch for {feature_ref}")

    dockerfile = dockerfile_path.read_text(encoding="utf-8")
    base_reference = parse_pinned_from(dockerfile)
    validate_apt_source_sanitization(dockerfile)
    require(
        f"ARG BENCH_VERSION={toolchain['BENCH_EXPECTED_VERSION']}" in dockerfile,
        "Bench Dockerfile pin does not match toolchain.env",
    )
    require(
        'pip install --no-cache-dir "frappe-bench==${BENCH_VERSION}"' in dockerfile,
        "Bench must be installed at the pinned version",
    )
    require("chmod -R a+rX /opt/frappe-bench" in dockerfile, "Bench must be readable and executable by vscode")
    require("/usr/local/bin/bench" in dockerfile, "Bench must be available to the remote user on PATH")

    bootstrap = (REPO_ROOT / "scripts/bootstrap-dev.sh").read_text(encoding="utf-8")
    require('NPI_DOCKER_WAIT_SECONDS:-120' in bootstrap, "Docker readiness wait must default to 120 seconds")
    require("docker version >&2" in bootstrap, "Docker timeout diagnostics are missing")
    validate_bootstrap_vite_installation(bootstrap)
    validate_bootstrap_uv_installation(bootstrap)

    dynamic_check = (REPO_ROOT / "scripts/verify-dev-environment.sh").read_text(encoding="utf-8")
    require('"${npm_actual}" == "${NPM_EXPECTED_VERSION}"' in dynamic_check, "Dynamic npm check must be exact")
    require('"${yarn_actual}" == "${YARN_EXPECTED_VERSION}"' in dynamic_check, "Dynamic Yarn check must be exact")
    require('docker_runtime_pattern=' in dynamic_check, "Dynamic Docker package-revision pattern is missing")
    require(
        dynamic_check.count('=~ ${docker_runtime_pattern}') == 2,
        "Dynamic Docker client and server checks must match the selected version",
    )
    require(
        '"${compose_actual}" == 2.*' in dynamic_check,
        "Dynamic Docker Compose check must require the configured v2 major",
    )
    require(
        'vite_version_actual="${vite_actual%% *}"' in dynamic_check,
        "Dynamic check must isolate the Vite version token",
    )
    require(
        '"${vite_version_actual}" == "vite/${VITE_EXPECTED_VERSION}"' in dynamic_check,
        "Dynamic Vite check must compare the complete version token",
    )
    require(
        '"${uv_version_actual}" == "${UV_EXPECTED_VERSION}"' in dynamic_check,
        "Dynamic uv check must compare the complete version token",
    )
    bench_init = (REPO_ROOT / "scripts/init-frappe-bench.sh").read_text(encoding="utf-8")
    require(
        "--skip-redis-config-generation" in bench_init,
        "Bench initialization must use the approved Compose Redis boundary",
    )
    require("--no-backups" in bench_init, "Bench initialization must not modify the user crontab")
    require("--skip-assets" in bench_init, "Bench initialization must not require an unapproved Yarn path")
    require("--no-procfile" in bench_init, "Bench initialization must not duplicate Compose process control")
    require("UV_LINK_MODE=copy" in bench_init, "Bench initialization must use a cross-filesystem uv mode")
    require(
        'checkout -q -b "${FRAPPE_BRANCH}" FETCH_HEAD' in bench_init,
        "Pinned Frappe checkout must expose the selected local branch to Bench",
    )
    return config, toolchain, base_reference


def registry_request(url: str, accept: str | None = None) -> urllib.response.addinfourl:
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    request = urllib.request.Request(url, headers=headers)
    try:
        return urllib.request.urlopen(request, timeout=60)
    except urllib.error.HTTPError as exc:
        if exc.code != 401:
            raise VerificationError(f"Registry request failed ({exc.code}): {url}") from exc
        challenge = exc.headers.get("WWW-Authenticate", "")
        parameters = dict(re.findall(r'(\w+)="([^"]+)"', challenge))
        realm = parameters.pop("realm", None)
        require(bool(realm), f"Registry did not provide a bearer-token realm: {url}")
        token_url = str(realm) + "?" + urllib.parse.urlencode(parameters)
        token_request = urllib.request.Request(token_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(token_request, timeout=60) as token_response:
            token = json.load(token_response)["token"]
        headers["Authorization"] = "Bearer " + token
        return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60)


def registry_json(url: str, accept: str | None = None) -> tuple[dict[str, Any], str | None]:
    try:
        with registry_request(url, accept) as response:
            return json.load(response), response.headers.get("Docker-Content-Digest")
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        raise VerificationError(f"Unable to read registry metadata: {url}: {exc}") from exc


def validate_base_image(reference: tuple[str, str, str]) -> None:
    image, tag, digest = reference
    registry, repository = image.split("/", 1)
    base_url = f"https://{registry}/v2/{repository}"
    tagged, tagged_digest = registry_json(base_url + "/manifests/" + tag, OCI_ACCEPT)
    require(tagged_digest == "sha256:" + digest, "Base image tag no longer resolves to the pinned digest")
    manifest = tagged
    if "manifests" in tagged:
        amd64 = next(
            (
                item
                for item in tagged["manifests"]
                if item.get("platform", {}).get("os") == "linux"
                and item.get("platform", {}).get("architecture") == "amd64"
            ),
            None,
        )
        require(amd64 is not None, "Pinned base image has no linux/amd64 manifest")
        manifest, _ = registry_json(base_url + "/manifests/" + amd64["digest"], OCI_ACCEPT)
    config_digest = manifest.get("config", {}).get("digest")
    require(bool(config_digest), "Pinned base image manifest has no config blob")
    config, _ = registry_json(base_url + "/blobs/" + str(config_digest))
    metadata_text = config.get("config", {}).get("Labels", {}).get("devcontainer.metadata", "[]")
    metadata = json.loads(metadata_text)
    remote_users = [item.get("remoteUser") for item in metadata if isinstance(item, dict) and item.get("remoteUser")]
    metadata_features = [item.get("id") for item in metadata if isinstance(item, dict) and item.get("id")]
    require("vscode" in remote_users, "Pinned base image does not define the vscode remote user")
    require(
        any(feature.startswith("ghcr.io/devcontainers/features/common-utils:") for feature in metadata_features),
        "Pinned base image does not provide the common remote-user utilities",
    )
    print(f"base_image=sha256:{digest}")


def feature_metadata(registry: str, repository: str, manifest: dict[str, Any]) -> dict[str, Any]:
    base_url = f"https://{registry}/v2/{repository}"
    for layer in manifest.get("layers", []):
        try:
            with registry_request(base_url + "/blobs/" + layer["digest"]) as response:
                payload = response.read()
            with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
                for member in archive.getmembers():
                    if member.name.rsplit("/", 1)[-1] == "devcontainer-feature.json":
                        extracted = archive.extractfile(member)
                        require(extracted is not None, "Feature metadata layer could not be read")
                        value = json.load(extracted)
                        require(isinstance(value, dict), "Feature metadata must be a JSON object")
                        return value
        except tarfile.TarError:
            continue
    raise VerificationError("Feature artifact has no devcontainer-feature.json")


def validate_features(config: dict[str, Any]) -> None:
    lock = read_json(DEVCONTAINER_DIR / "devcontainer-lock.json")["features"]
    for feature_ref, options in config["features"].items():
        image, tag = feature_ref.rsplit(":", 1)
        registry, repository = image.split("/", 1)
        manifest, digest = registry_json(
            f"https://{registry}/v2/{repository}/manifests/{tag}", OCI_ACCEPT
        )
        require(digest == lock[feature_ref]["integrity"], f"Feature registry digest mismatch: {feature_ref}")
        metadata = feature_metadata(registry, repository, manifest)
        require(metadata.get("version") == tag, f"Feature metadata version mismatch: {feature_ref}")
        supported_options = set((metadata.get("options") or {}).keys())
        require(set(options) <= supported_options, f"Unsupported option in {feature_ref}")
        print(f"feature={feature_ref}@{digest}")


def request_json(url: str) -> Any:
    try:
        request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"Unable to read upstream metadata: {url}: {exc}") from exc


def validate_tool_versions(toolchain: dict[str, str]) -> None:
    node_releases = request_json("https://nodejs.org/dist/index.json")
    node = next((item for item in node_releases if item.get("version") == toolchain["NODE_EXPECTED_VERSION"]), None)
    require(node is not None, "Pinned Node release does not exist")
    require(node.get("npm") == toolchain["NPM_EXPECTED_VERSION"], "Pinned npm is not bundled with the pinned Node release")
    yarn = request_json(f"https://registry.npmjs.org/yarn/{toolchain['YARN_EXPECTED_VERSION']}")
    require(yarn.get("version") == toolchain["YARN_EXPECTED_VERSION"], "Pinned Yarn release does not exist")

    bench = request_json(f"https://pypi.org/pypi/frappe-bench/{toolchain['BENCH_EXPECTED_VERSION']}/json")
    require(bench.get("info", {}).get("version") == toolchain["BENCH_EXPECTED_VERSION"], "Pinned Bench release does not exist")
    uv = request_json(f"https://pypi.org/pypi/uv/{toolchain['UV_EXPECTED_VERSION']}/json")
    require(uv.get("info", {}).get("version") == toolchain["UV_EXPECTED_VERSION"], "Pinned uv release does not exist")
    vite = request_json(f"https://registry.npmjs.org/vite/{toolchain['VITE_EXPECTED_VERSION']}")
    require(vite.get("version") == toolchain["VITE_EXPECTED_VERSION"], "Pinned Vite release does not exist")

    package_index_url = "https://packages.microsoft.com/debian/12/prod/dists/bookworm/main/binary-amd64/Packages.gz"
    try:
        request = urllib.request.Request(package_index_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=60) as response:
            packages = gzip.decompress(response.read()).decode("utf-8", "replace")
    except OSError as exc:
        raise VerificationError(f"Unable to read Moby package index: {exc}") from exc
    docker_version = toolchain["DOCKER_EXPECTED_VERSION"]
    for package in ("moby-engine", "moby-cli"):
        versions = []
        for stanza in packages.split("\n\n"):
            fields = dict(
                line.split(": ", 1)
                for line in stanza.splitlines()
                if ": " in line and not line.startswith((" ", "\t"))
            )
            if fields.get("Package") == package:
                versions.append(fields.get("Version", ""))
        require(
            any(version.startswith(docker_version + "-") for version in versions),
            f"Pinned {package} release does not exist",
        )

    frappe = request_json(
        "https://api.github.com/repos/frappe/frappe/commits/" + toolchain["FRAPPE_COMMIT"]
    )
    require(frappe.get("sha") == toolchain["FRAPPE_COMMIT"], "Pinned Frappe commit does not exist")
    print(
        "toolchain="
        + ",".join(
            (
                toolchain["NODE_EXPECTED_VERSION"],
                "npm-" + toolchain["NPM_EXPECTED_VERSION"],
                "yarn-" + toolchain["YARN_EXPECTED_VERSION"],
                "docker-" + toolchain["DOCKER_EXPECTED_VERSION"],
                "bench-" + toolchain["BENCH_EXPECTED_VERSION"],
                "uv-" + toolchain["UV_EXPECTED_VERSION"],
                "vite-" + toolchain["VITE_EXPECTED_VERSION"],
            )
        )
    )


def main() -> int:
    try:
        config, toolchain, base_reference = validate_local_configuration()
        validate_base_image(base_reference)
        validate_features(config)
        validate_tool_versions(toolchain)
    except (VerificationError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"devcontainer verification failed: {exc}")
        return 1
    print("development container configuration and registry verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
