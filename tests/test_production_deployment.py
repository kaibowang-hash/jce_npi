from __future__ import annotations

import json
import pathlib
import re
import unittest

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy" / "production"


class ProductionDeploymentTests(unittest.TestCase):
    def test_compose_has_complete_independent_runtime(self) -> None:
        document = yaml.safe_load((DEPLOY / "compose.yml").read_text(encoding="utf-8"))
        services = document["services"]
        self.assertTrue(
            {
                "db",
                "redis-cache",
                "redis-queue",
                "backend",
                "frappe-frontend",
                "websocket",
                "scheduler",
                "queue-short",
                "queue-long",
                "spa",
                "configurator",
                "site-init",
            }.issubset(services)
        )
        self.assertNotIn("erpnext", services)
        for name in (
            "db",
            "redis-cache",
            "redis-queue",
            "backend",
            "frappe-frontend",
            "spa",
        ):
            self.assertIn("healthcheck", services[name])
        for name, service in services.items():
            if name not in {"configurator", "site-init"}:
                self.assertEqual(service.get("restart"), "unless-stopped")
        self.assertEqual(services["db"]["environment"], {"MARIADB_ROOT_PASSWORD_FILE": "/run/secrets/mariadb_root_password"})
        self.assertNotIn("ports", services["db"])
        self.assertNotIn("ports", services["redis-cache"])
        self.assertNotIn("ports", services["redis-queue"])

    def test_images_and_frappe_source_are_immutable(self) -> None:
        containerfile = (DEPLOY / "Containerfile").read_text(encoding="utf-8")
        digests = re.findall(r"sha256:[0-9a-f]{64}", containerfile)
        self.assertGreaterEqual(len(digests), 3)
        self.assertIn("a3d8090ba80cb91d3ed72ea90bec67df201db5c1", containerfile)
        self.assertIn('org.opencontainers.image.revision="${RELEASE_SHA}"', containerfile)
        compose = (DEPLOY / "compose.yml").read_text(encoding="utf-8")
        self.assertGreaterEqual(len(re.findall(r"sha256:[0-9a-f]{64}", compose)), 3)

    def test_spa_production_build_sets_the_controlled_environment_marker(self) -> None:
        containerfile = (DEPLOY / "Containerfile").read_text(encoding="utf-8")
        build_script = (DEPLOY / "scripts" / "build-release.sh").read_text(encoding="utf-8")
        self.assertIn("ARG VITE_DEPLOYMENT_ENV", containerfile)
        self.assertIn('--build-arg "VITE_DEPLOYMENT_ENV=production"', build_script)

    def test_production_init_excludes_development_and_real_erp_activation(self) -> None:
        init_script = (DEPLOY / "scripts" / "init-site.sh").read_text(encoding="utf-8")
        self.assertIn("install-app npi_core", init_script)
        self.assertIn("install-app npi_integration", init_script)
        self.assertLess(init_script.index("install-app npi_core"), init_script.index("install-app npi_integration"))
        self.assertIn("developer_mode 0", init_script)
        self.assertIn("npi_deployment_environment production", init_script)
        self.assertIn("npi_p9_04_authorization_projection_routes_disabled True", init_script)
        self.assertIn(
            "npi_core.production_setup.enforce_production_auth_settings",
            init_script,
        )
        self.assertIn('set-config --parse "${switch_name}" False', init_script)
        self.assertNotIn("frappe-site-init", init_script)
        self.assertNotRegex(init_script, r"dev-only|NPI_.*RUNTIME_ENABLED")
        self.assertNotRegex(init_script, r"install-app\s+erpnext")
        self.assertNotIn("npi_erpnext_connector", init_script)
        self.assertNotIn("npi_erpnext_connector", (DEPLOY / "compose.yml").read_text(encoding="utf-8"))
        self.assertNotIn("npi_erpnext_connector", (DEPLOY / "Containerfile").read_text(encoding="utf-8"))

    def test_production_auth_setup_closes_self_signup(self) -> None:
        setup = (
            ROOT / "apps" / "npi_core" / "npi_core" / "production_setup.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'set_single_value("Website Settings", "disable_signup", 1)',
            setup,
        )
        self.assertNotRegex(setup, r"password|signup\s*=\s*0")

    def test_server_files_do_not_contain_secret_values(self) -> None:
        prohibited = re.compile(
            r"(?i:dev-only)|MARIADB_ROOT_PASSWORD:\s*[^$]|"
            r"(?i:(?:api[_-]?key|secret[_-]?key)\s*[:=]\s*['\"][^$/{])"
        )
        for path in DEPLOY.rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(prohibited.search(text), path.as_posix())
        json.loads((DEPLOY / "host" / "docker-daemon.json").read_text(encoding="utf-8"))

    def test_https_and_spa_routes_share_one_origin(self) -> None:
        nginx = (DEPLOY / "host" / "nginx-tls.conf").read_text(encoding="utf-8")
        self.assertIn("server_name launchflow.whjichen.cn", nginx)
        self.assertIn("listen 443 ssl", nginx)
        self.assertIn("api(?:/|$)", nginx)
        self.assertIn("proxy_pass http://127.0.0.1:8080", nginx)
        self.assertIn("proxy_pass http://127.0.0.1:8081", nginx)
        spa = (DEPLOY / "nginx" / "spa.conf").read_text(encoding="utf-8")
        self.assertIn("try_files $uri $uri/ /index.html", spa)

    def test_health_gate_uses_the_pinned_frappe_scheduler_cli(self) -> None:
        health = (DEPLOY / "scripts" / "healthcheck.sh").read_text(encoding="utf-8")
        self.assertIn('scheduler status |', health)
        self.assertNotIn("scheduler get-status", health)


if __name__ == "__main__":
    unittest.main()
