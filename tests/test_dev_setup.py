import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch


def load_setup():
    spec = importlib.util.spec_from_file_location(
        "continuity360_dev_setup", Path(__file__).resolve().parents[1] / "docker" / "setup.py"
    )
    module = importlib.util.module_from_spec(spec)
    if "pwd" not in sys.modules and sys.platform == "win32":
        with patch.dict(sys.modules, {"pwd": types.ModuleType("pwd")}):
            spec.loader.exec_module(module)
    else:
        spec.loader.exec_module(module)
    return module


class TestDevSetup(unittest.TestCase):
    def setUp(self):
        self.setup = load_setup()
        self.new_site = Mock()
        frappe = types.ModuleType("frappe")
        commands = types.ModuleType("frappe.commands")
        site = types.ModuleType("frappe.commands.site")
        site.new_site = types.SimpleNamespace(callback=self.new_site)
        self.modules = {
            "frappe": frappe,
            "frappe.commands": commands,
            "frappe.commands.site": site,
        }

    def test_new_site_secrets_stay_out_of_bench_arguments(self):
        with (
            patch.dict(sys.modules, self.modules),
            patch.object(Path, "read_text", side_effect=["db-secret", "admin-secret"]),
            patch.object(Path, "exists", return_value=False),
            patch.object(self.setup.os, "getuid", return_value=1000, create=True),
            patch.object(self.setup.os, "chdir") as chdir,
            patch.object(self.setup, "run") as run,
        ):
            self.setup.create_site()

        self.new_site.assert_called_once_with(
            self.setup.SITE, db_root_username="root", db_root_password="db-secret",
            admin_password="admin-secret", mariadb_user_host_login_scope="%",
            install_app=("continuity360",), set_default=True,
        )
        self.assertEqual(chdir.call_args_list, [call(self.setup.BENCH / "sites"), call(self.setup.BENCH)])
        self.assertEqual(run.call_args_list, [
            call("--site", self.setup.SITE, "set-config", "host_name", "http://localhost:18080"),
            call("--site", self.setup.SITE, "execute", "continuity360.dev_setup.initialize"),
        ])

    def test_existing_site_is_migrated_without_recreation(self):
        with (
            patch.dict(sys.modules, self.modules),
            patch.object(Path, "read_text", side_effect=["db-secret", "admin-secret"]),
            patch.object(Path, "exists", return_value=True),
            patch.object(self.setup.os, "getuid", return_value=1000, create=True),
            patch.object(self.setup, "run") as run,
        ):
            self.setup.create_site()
        self.new_site.assert_not_called()
        self.assertEqual(run.call_args_list, [
            call("--site", self.setup.SITE, "execute", "continuity360.install.assert_installed"),
            call("--site", self.setup.SITE, "migrate"),
            call("--site", self.setup.SITE, "execute", "continuity360.dev_setup.initialize"),
        ])

    def test_failed_creation_restores_working_directory(self):
        self.new_site.side_effect = SystemExit(1)
        with (
            patch.dict(sys.modules, self.modules),
            patch.object(Path, "read_text", side_effect=["db-secret", "admin-secret"]),
            patch.object(Path, "exists", return_value=False),
            patch.object(self.setup.os, "getuid", return_value=1000, create=True),
            patch.object(self.setup.os, "chdir") as chdir,
            patch.object(self.setup, "run") as run,
        ):
            with self.assertRaises(SystemExit):
                self.setup.create_site()
        self.assertEqual(chdir.call_args_list, [call(self.setup.BENCH / "sites"), call(self.setup.BENCH)])
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
