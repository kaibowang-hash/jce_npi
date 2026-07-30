import unittest
import urllib.request

from scripts.verify_devcontainer import (
    REPO_ROOT,
    ScopedAuthorizationRedirectHandler,
    VerificationError,
    parse_pinned_from,
    parse_toolchain,
    upstream_request_headers,
    validate_apt_source_sanitization,
    validate_bootstrap_vite_installation,
    validate_bootstrap_uv_installation,
    validate_ci_verification_tools,
    validate_frontend_install_policy,
    validate_local_configuration,
    validate_repository_verifier,
)


class DevcontainerVerifierTest(unittest.TestCase):
    safe_apt_prelude = """RUN set -eux; \\
    if [ -f /etc/apt/sources.list ]; then \\
        sed -i '/dl\\.yarnpkg\\.com\\/debian/d' /etc/apt/sources.list; \\
    fi; \\
    find /etc/apt/sources.list.d -maxdepth 1 -type f -iname '*yarn*' -delete; \\
    apt-get update; \\
    apt-get install -y make
"""

    def test_apt_source_cleanup_covers_both_locations(self):
        validate_apt_source_sanitization(self.safe_apt_prelude)

    def test_apt_source_cleanup_rejects_literal_invalid_url(self):
        with self.assertRaises(VerificationError):
            validate_apt_source_sanitization(
                self.safe_apt_prelude + "RUN echo https://dl.yarnpkg.com/debian\n"
            )

    def test_apt_source_cleanup_rejects_trusted_bypass(self):
        with self.assertRaises(VerificationError):
            validate_apt_source_sanitization(self.safe_apt_prelude + "RUN echo trusted=yes\n")

    def test_apt_source_cleanup_rejects_ignored_apt_failure(self):
        with self.assertRaises(VerificationError):
            validate_apt_source_sanitization(
                self.safe_apt_prelude.replace("apt-get update;", "apt-get update || true;")
            )

    def test_apt_source_cleanup_requires_fragment_removal(self):
        with self.assertRaises(VerificationError):
            validate_apt_source_sanitization(
                self.safe_apt_prelude.replace(
                    "find /etc/apt/sources.list.d -maxdepth 1 -type f -iname '*yarn*' -delete; \\\n",
                    "",
                )
            )

    def test_apt_source_cleanup_requires_main_list_sanitization(self):
        with self.assertRaises(VerificationError):
            validate_apt_source_sanitization(
                self.safe_apt_prelude.replace(
                    "        sed -i '/dl\\.yarnpkg\\.com\\/debian/d' /etc/apt/sources.list; \\\n",
                    "",
                )
            )

    def test_repository_devcontainer_is_internally_consistent(self):
        config, toolchain, base_reference = validate_local_configuration()
        self.assertEqual(config["remoteUser"], "vscode")
        self.assertEqual(toolchain["NODE_EXPECTED_VERSION"], "v24.18.0")
        self.assertEqual(toolchain["NPM_EXPECTED_VERSION"], "11.16.0")
        self.assertEqual(toolchain["YARN_EXPECTED_VERSION"], "1.22.22")
        self.assertEqual(toolchain["DOCKER_EXPECTED_VERSION"], "28.3.3")
        self.assertEqual(toolchain["UV_EXPECTED_VERSION"], "0.11.30")
        self.assertEqual(toolchain["VITE_ESBUILD_EXPECTED_VERSION"], "0.21.5")
        self.assertEqual(toolchain["VITE_FSEVENTS_EXPECTED_VERSION"], "2.3.3")
        self.assertEqual(base_reference[1], "1-3.11-bookworm")

    def test_ci_installs_ripgrep_before_the_fail_closed_repository_scan(self):
        visual_image = (
            "mcr.microsoft.com/devcontainers/python:1-3.11-bookworm"
            "@sha256:b726eb94f42fcddb10056835f2c474c9f9e12e717ba2b2d2f9a8b1d78feeb68b"
        )
        safe_workflow = """steps:
  - run: sudo apt-get update
  - run: sudo apt-get install --yes ripgrep
  - run: bash scripts/verify-dev-config.sh
    env:
      GITHUB_TOKEN: ${{ github.token }}
  - run: bash scripts/verify.sh
    env:
      GITHUB_TOKEN: ${{ github.token }}
  - uses: gitleaks/gitleaks-action@v2
    env:
      GITHUB_TOKEN: ${{ github.token }}
visual:
  container:
    image: mcr.microsoft.com/devcontainers/python:1-3.11-bookworm@sha256:b726eb94f42fcddb10056835f2c474c9f9e12e717ba2b2d2f9a8b1d78feeb68b
  steps:
    - run: |
        sudo sed -i '/dl\\.yarnpkg\\.com\\/debian/d' /etc/apt/sources.list
        sudo find /etc/apt/sources.list.d -maxdepth 1 -type f -iname '*yarn*' -delete
    - run: npx playwright install --with-deps chromium
    - run: npx playwright test tests/e2e/r1-05-panes.spec.ts tests/e2e/r1-05-field-attachments.spec.ts --grep @visual
    - uses: actions/upload-artifact@v4
      with:
        name: r1-05-linux-visual-evidence
        path: |
          implementation/evidence/phase-4/playwright-results/.last-run.json
          implementation/evidence/phase-4/playwright-results/r1-05-*/**/*-actual.png
          implementation/evidence/phase-4/playwright-results/r1-05-*/**/*-diff.png
        include-hidden-files: true
"""
        validate_ci_verification_tools(safe_workflow, visual_image)
        unsafe_variants = (
            safe_workflow.replace("sudo apt-get update\n", ""),
            safe_workflow.replace("sudo apt-get install --yes ripgrep\n", ""),
            safe_workflow.replace(
                "sudo apt-get install --yes ripgrep",
                "sudo apt-get install --yes ripgrep || true",
            ),
            safe_workflow.replace(
                "  - run: sudo apt-get install --yes ripgrep\n"
                "  - run: bash scripts/verify-dev-config.sh\n"
                "    env:\n"
                "      GITHUB_TOKEN: ${{ github.token }}\n"
                "  - run: bash scripts/verify.sh\n",
                "  - run: bash scripts/verify.sh\n"
                "    env:\n"
                "      GITHUB_TOKEN: ${{ github.token }}\n"
                "  - run: sudo apt-get install --yes ripgrep\n",
            ),
            safe_workflow.replace(
                "  - run: bash scripts/verify-dev-config.sh\n"
                "    env:\n"
                "      GITHUB_TOKEN: ${{ github.token }}\n",
                "  - run: bash scripts/verify-dev-config.sh\n",
            ),
            safe_workflow.replace(
                "  - run: bash scripts/verify.sh\n"
                "    env:\n"
                "      GITHUB_TOKEN: ${{ github.token }}\n",
                "  - run: bash scripts/verify.sh\n",
            ),
            safe_workflow.replace(
                "  - uses: gitleaks/gitleaks-action@v2\n"
                "    env:\n"
                "      GITHUB_TOKEN: ${{ github.token }}\n",
                "  - uses: gitleaks/gitleaks-action@v2\n",
            ),
            safe_workflow.replace(
                f"    image: {visual_image}\n",
                "    image: ubuntu:24.04\n",
            ),
            safe_workflow.replace(
                "        sudo find /etc/apt/sources.list.d -maxdepth 1 "
                "-type f -iname '*yarn*' -delete\n",
                "",
            ),
            safe_workflow.replace(
                "          implementation/evidence/phase-4/playwright-results/"
                "r1-05-*/**/*-actual.png\n",
                "          implementation/evidence/phase-4\n",
            ),
            safe_workflow.replace("        include-hidden-files: true\n", ""),
        )
        for unsafe_workflow in unsafe_variants:
            with self.assertRaises(VerificationError):
                validate_ci_verification_tools(unsafe_workflow, visual_image)

    def test_upstream_token_is_scoped_to_github_api(self):
        github_headers = upstream_request_headers(
            "https://api.github.com/repos/frappe/frappe/commits/example",
            "secret-token",
        )
        self.assertEqual(github_headers["Authorization"], "Bearer secret-token")
        for url in (
            "http://api.github.com/repos/frappe/frappe",
            "https://github.com/frappe/frappe",
            "https://registry.npmjs.org/vite/5.4.14",
            "https://api.github.com:444/repos/frappe/frappe",
            "https://api.github.com.evil.example/repos/frappe/frappe",
        ):
            with self.subTest(url=url):
                self.assertNotIn(
                    "Authorization",
                    upstream_request_headers(url, "secret-token"),
                )

    def test_authenticated_github_redirect_cannot_leave_exact_https_origin(self):
        handler = ScopedAuthorizationRedirectHandler()
        request = urllib.request.Request(
            "https://api.github.com/repos/frappe/frappe/commits/example",
            headers={"Authorization": "Bearer sentinel-secret"},
        )
        for url in (
            "https://example.invalid/steal",
            "http://api.github.com/steal",
            "https://api.github.com:444/steal",
            "https://api.github.com.evil.example/steal",
        ):
            with self.subTest(url=url), self.assertRaises(VerificationError):
                handler.redirect_request(request, None, 302, "Found", {}, url)

        redirected = handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://api.github.com/repositories/1/commits/example",
        )
        self.assertIsNotNone(redirected)
        assert redirected is not None
        self.assertEqual(
            redirected.get_header("Authorization"),
            "Bearer sentinel-secret",
        )

    def test_uv_installation_is_pinned_and_exposed(self):
        safe_bootstrap = """uv_command="/opt/frappe-bench/bin/uv"
uv_pip_command="/opt/frappe-bench/bin/pip"
sudo "${uv_pip_command}" install --no-cache-dir "uv==${UV_EXPECTED_VERSION}"
sudo ln -sfn "${uv_command}" /usr/local/bin/uv
"""
        validate_bootstrap_uv_installation(safe_bootstrap)
        with self.assertRaises(VerificationError):
            validate_bootstrap_uv_installation(
                safe_bootstrap.replace('"uv==${UV_EXPECTED_VERSION}"', '"uv"')
            )

    def test_vite_install_rejects_sudo_sanitized_node_path(self):
        safe_bootstrap = """installed_vite_version="${installed_vite%% *}"
installed_esbuild="$(esbuild --version 2>/dev/null || true)"
if [[
  "${installed_vite_version}" != "vite/${VITE_EXPECTED_VERSION}" ||
  "${installed_esbuild}" != "${VITE_ESBUILD_EXPECTED_VERSION}"
]]; then
npm_prefix="$("${npm_command}" prefix --global)"
[[ ! -d "${npm_prefix}" || ! -w "${npm_prefix}" ]]
"${npm_command}" install \\
    --global \\
    --strict-allow-scripts \\
    "--allow-scripts=esbuild@${VITE_ESBUILD_EXPECTED_VERSION},fsevents@${VITE_FSEVENTS_EXPECTED_VERSION}" \\
    "vite@${VITE_EXPECTED_VERSION}" \\
    "esbuild@${VITE_ESBUILD_EXPECTED_VERSION}"
fi
"""
        validate_bootstrap_vite_installation(safe_bootstrap)
        with self.assertRaises(VerificationError):
            validate_bootstrap_vite_installation(
                safe_bootstrap
                + 'sudo "${npm_command}" install --global "vite@${VITE_EXPECTED_VERSION}"\n'
            )

    def test_vite_install_rejects_longer_version_prefix(self):
        unsafe_bootstrap = """installed_vite_version="${installed_vite%% *}"
installed_esbuild="$(esbuild --version 2>/dev/null || true)"
if [[
  "${installed_vite_version}" != "vite/${VITE_EXPECTED_VERSION}"* ||
  "${installed_esbuild}" != "${VITE_ESBUILD_EXPECTED_VERSION}"
]]; then
npm_prefix="$("${npm_command}" prefix --global)"
[[ ! -d "${npm_prefix}" || ! -w "${npm_prefix}" ]]
"${npm_command}" install \\
    --global \\
    --strict-allow-scripts \\
    "--allow-scripts=esbuild@${VITE_ESBUILD_EXPECTED_VERSION},fsevents@${VITE_FSEVENTS_EXPECTED_VERSION}" \\
    "vite@${VITE_EXPECTED_VERSION}" \\
    "esbuild@${VITE_ESBUILD_EXPECTED_VERSION}"
fi
"""
        with self.assertRaises(VerificationError):
            validate_bootstrap_vite_installation(unsafe_bootstrap)

    def test_vite_install_requires_strict_exact_script_allowlist(self):
        bootstrap = (REPO_ROOT / "scripts/bootstrap-dev.sh").read_text(encoding="utf-8")
        for unsafe in (
            bootstrap.replace("--strict-allow-scripts \\\n", ""),
            bootstrap.replace(
                "--allow-scripts=esbuild@${VITE_ESBUILD_EXPECTED_VERSION},"
                "fsevents@${VITE_FSEVENTS_EXPECTED_VERSION}",
                "--dangerously-allow-all-scripts",
            ),
            bootstrap.replace('"esbuild@${VITE_ESBUILD_EXPECTED_VERSION}"', '"esbuild"'),
        ):
            with self.assertRaises(VerificationError):
                validate_bootstrap_vite_installation(unsafe)

    def test_repository_verifier_rejects_prohibited_scan_false_success(self):
        repository_verify = (REPO_ROOT / "scripts/verify.sh").read_text(encoding="utf-8")
        validate_repository_verifier(repository_verify)
        unsafe_variants = (
            repository_verify.replace(
                'node_actual="$(node --version 2>/dev/null || true)"',
                'node_actual="${NODE_EXPECTED_VERSION}"',
            ),
            repository_verify.replace("if ! command -v rg >/dev/null 2>&1; then", "if false; then"),
            repository_verify.replace("|| scan_status=$?", ""),
            repository_verify.replace('exit "${scan_status}"', "true"),
            repository_verify.replace(
                "scan_status=0\nrg -n",
                "scan_status=0\nif rg -n",
            ),
        )
        for unsafe in unsafe_variants:
            with self.assertRaises(VerificationError):
                validate_repository_verifier(unsafe)

    def test_frontend_install_policy_is_strict_and_exact(self):
        package = {
            "allowScripts": {
                "esbuild@0.25.12": True,
                "fsevents": False,
            },
            "scripts": {
                "verify:install-scripts": "bash scripts/verify-install-scripts.sh",
                "audit": (
                    "npm run verify:install-scripts && "
                    "npm audit && npm audit --omit=dev"
                ),
            },
        }
        npmrc = "engine-strict=true\nstrict-allow-scripts=true\n"
        validate_frontend_install_policy(npmrc, package)
        unsafe_variants = (
            (npmrc.replace("strict-allow-scripts=true\n", ""), package),
            (
                npmrc,
                {
                    **package,
                    "allowScripts": {
                        "esbuild@0.25.12": True,
                        "fsevents": False,
                        "unreviewed@1.0.0": True,
                    },
                },
            ),
            (
                npmrc,
                {
                    **package,
                    "scripts": {
                        **package["scripts"],
                        "audit": "npm audit",
                    },
                },
            ),
        )
        for unsafe_npmrc, unsafe_package in unsafe_variants:
            with self.assertRaises(VerificationError):
                validate_frontend_install_policy(unsafe_npmrc, unsafe_package)

    def test_toolchain_rejects_duplicate_key(self):
        with self.assertRaises(VerificationError):
            parse_toolchain("NODE_EXPECTED_VERSION=v18\nNODE_EXPECTED_VERSION=v20\n")

    def test_toolchain_rejects_missing_value(self):
        with self.assertRaises(VerificationError):
            parse_toolchain("NODE_EXPECTED_VERSION=\n")

    def test_base_image_requires_digest(self):
        with self.assertRaises(VerificationError):
            parse_pinned_from("FROM mcr.microsoft.com/devcontainers/python:1-3.11-bookworm\n")

    def test_base_image_parses_tag_and_digest(self):
        digest = "a" * 64
        self.assertEqual(
            parse_pinned_from(
                "FROM mcr.microsoft.com/devcontainers/python:1-3.11-bookworm@sha256:"
                + digest
                + "\n"
            ),
            ("mcr.microsoft.com/devcontainers/python", "1-3.11-bookworm", digest),
        )


if __name__ == "__main__":
    unittest.main()
