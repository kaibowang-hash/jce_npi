import unittest

from scripts.verify_devcontainer import (
    VerificationError,
    parse_pinned_from,
    parse_toolchain,
    validate_apt_source_sanitization,
    validate_bootstrap_vite_installation,
    validate_bootstrap_uv_installation,
    validate_local_configuration,
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
        self.assertEqual(toolchain["NPM_EXPECTED_VERSION"], "10.8.2")
        self.assertEqual(toolchain["YARN_EXPECTED_VERSION"], "1.22.22")
        self.assertEqual(toolchain["DOCKER_EXPECTED_VERSION"], "28.3.3")
        self.assertEqual(toolchain["UV_EXPECTED_VERSION"], "0.11.30")
        self.assertEqual(base_reference[1], "1-3.11-bookworm")

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
if [[ "${installed_vite_version}" != "vite/${VITE_EXPECTED_VERSION}" ]]; then
npm_prefix="$("${npm_command}" prefix --global)"
[[ ! -d "${npm_prefix}" || ! -w "${npm_prefix}" ]]
"${npm_command}" install --global "vite@${VITE_EXPECTED_VERSION}"
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
if [[ "${installed_vite_version}" != "vite/${VITE_EXPECTED_VERSION}"* ]]; then
npm_prefix="$("${npm_command}" prefix --global)"
[[ ! -d "${npm_prefix}" || ! -w "${npm_prefix}" ]]
"${npm_command}" install --global "vite@${VITE_EXPECTED_VERSION}"
fi
"""
        with self.assertRaises(VerificationError):
            validate_bootstrap_vite_installation(unsafe_bootstrap)

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
