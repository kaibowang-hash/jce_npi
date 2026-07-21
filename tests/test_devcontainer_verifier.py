import unittest

from scripts.verify_devcontainer import (
    VerificationError,
    parse_pinned_from,
    parse_toolchain,
    validate_local_configuration,
)


class DevcontainerVerifierTest(unittest.TestCase):
    def test_repository_devcontainer_is_internally_consistent(self):
        config, toolchain, base_reference = validate_local_configuration()
        self.assertEqual(config["remoteUser"], "vscode")
        self.assertEqual(toolchain["NPM_EXPECTED_VERSION"], "10.8.2")
        self.assertEqual(base_reference[1], "1-3.11-bookworm")

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
