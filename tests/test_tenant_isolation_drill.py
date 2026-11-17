import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


scripts = Path(__file__).resolve().parents[1] / "scripts"
shared_spec = importlib.util.spec_from_file_location("restore_drill", scripts / "restore_drill.py")
shared = importlib.util.module_from_spec(shared_spec)
shared_spec.loader.exec_module(shared)
spec = importlib.util.spec_from_file_location("tenant_isolation_drill", scripts / "tenant_isolation_drill.py")
host = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"restore_drill": shared}):
    spec.loader.exec_module(host)


class TestTenantIsolationDrill(unittest.TestCase):
    def test_gateway_rejects_untrusted_site_tokens(self):
        for token in ("bad", "a" * 31 + ";", "a" * 32 + "\n"):
            with self.subTest(token=token):
                with self.assertRaises(ValueError):
                    host.gateway_config(token)

    def test_failed_verification_cleans_up_disposable_project(self):
        def fail_on_verification(*arguments, **kwargs):
            if "verify" in arguments:
                raise RuntimeError("verification failed")
            return Mock(stdout="")

        with (
            patch.object(host.sys, "platform", "linux"),
            patch.object(host, "resources", return_value=[]),
            patch.object(host, "run", side_effect=fail_on_verification),
            patch.object(host, "verify_existing_site_rejected"),
            patch.object(host, "cleanup") as cleanup,
        ):
            with self.assertRaisesRegex(RuntimeError, "verification failed"):
                host.main()
        cleanup.assert_called_once()

    def test_sites_use_separate_secrets_and_operator_entrypoint(self):
        config = {}

        def capture_run(*arguments, **kwargs):
            if "config" in arguments:
                override = Path(arguments[arguments.index("-f", arguments.index("-f") + 1) + 1])
                config.update(json.loads(override.read_text()))
                a = Path(config["secrets"]["tenant_a_password"]["file"]).read_text()
                b = Path(config["secrets"]["tenant_b_password"]["file"]).read_text()
                self.assertNotEqual(a, b)
            return Mock(stdout="")

        with (
            patch.object(host.sys, "platform", "linux"),
            patch.object(host, "resources", return_value=[]),
            patch.object(host, "run", side_effect=capture_run) as run,
            patch.object(host, "verify_existing_site_rejected"),
            patch.object(host, "cleanup"),
        ):
            host.main()

        for label in ("a", "b"):
            service = config["services"][f"provision-{label}"]
            self.assertEqual(service["secrets"][1], {
                "source": f"tenant_{label}_password", "target": "tenant_admin_password",
            })
            self.assertEqual(service["entrypoint"][-1], "/opt/continuity360/provision_tenant_site.py")
            calls = [call.args for call in run.call_args_list if f"provision-{label}" in call.args]
            self.assertEqual(len(calls), 1)
            self.assertRegex(calls[0][-1], rf"^c360-tenant-[0-9a-f]{{32}}-{label}\.localhost$")

    def test_duplicate_check_requires_the_expected_failure(self):
        site = "customer.example"
        duplicate = subprocess.CalledProcessError(
            1, "compose", stderr=f"FileExistsError: Site path already exists: {site}",
        )
        with patch.object(host, "run", side_effect=duplicate):
            host.verify_existing_site_rejected(("docker", "compose"), "a", site)
        with patch.object(host, "run", return_value=Mock()):
            with self.assertRaisesRegex(RuntimeError, "accepted an existing site"):
                host.verify_existing_site_rejected(("docker", "compose"), "a", site)
        with patch.object(host, "run", side_effect=subprocess.CalledProcessError(1, "compose", stderr="other")):
            with self.assertRaisesRegex(RuntimeError, "failed unexpectedly"):
                host.verify_existing_site_rejected(("docker", "compose"), "a", site)


if __name__ == "__main__":
    unittest.main()
