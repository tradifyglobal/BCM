import importlib.util
import os
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock, patch


scripts = Path(__file__).resolve().parents[1] / "scripts"
shared_spec = importlib.util.spec_from_file_location("restore_drill_site", scripts / "restore_drill_site.py")
shared = importlib.util.module_from_spec(shared_spec)
shared_spec.loader.exec_module(shared)
spec = importlib.util.spec_from_file_location("provision_tenant_site", scripts / "provision_tenant_site.py")
provisioner = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"restore_drill_site": shared}):
    spec.loader.exec_module(provisioner)


class TestTenantProvisioning(unittest.TestCase):
    def test_hostname_validation_rejects_paths_and_non_dns_names(self):
        provisioner.validate_site_name("customer-1.example.com")
        for site in ("../tenant", "Tenant.example.com", "tenant..example", "-bad.example",
                     "a" * 64 + ".example", "127.0.0.1", "tenant.example\n", "localhost"):
            with self.subTest(site=site), self.assertRaises(ValueError):
                provisioner.validate_site_name(site)

    def test_existing_site_or_symlink_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "customer.example").mkdir()
            exists = os.path.lexists
            with (
                patch.object(provisioner, "site_creation_lock", return_value=nullcontext()),
                patch.object(provisioner.os.path, "lexists", side_effect=lambda site: exists(root / site)),
            ):
                with self.assertRaises(FileExistsError):
                    provisioner.provision_site("customer.example", "root-secret", "admin-secret")
                if os.name == "posix":
                    (root / "link.example").symlink_to(root / "missing")
                    with self.assertRaises(FileExistsError):
                        provisioner.provision_site("link.example", "root-secret", "admin-secret")

    def test_creation_installs_app_and_always_destroys_frappe_context(self):
        frappe = types.ModuleType("frappe")
        frappe.destroy = Mock()
        commands = types.ModuleType("frappe.commands")
        site_module = types.ModuleType("frappe.commands.site")
        callback = Mock(side_effect=RuntimeError("installation failed"))
        site_module.new_site = types.SimpleNamespace(callback=callback)
        database = types.ModuleType("frappe.database")
        manager = types.ModuleType("frappe.database.db_manager")
        manager.DbManager = type("DbManager", (), {})
        modules = {
            "frappe": frappe, "frappe.commands": commands, "frappe.commands.site": site_module,
            "frappe.database": database, "frappe.database.db_manager": manager,
        }
        with (
            patch.dict(sys.modules, modules),
            patch.object(provisioner, "site_creation_lock", return_value=nullcontext()),
            patch.object(os.path, "lexists", return_value=False),
        ):
            with self.assertRaisesRegex(RuntimeError, "installation failed"):
                provisioner.provision_site("customer.example", "root-secret", "admin-secret")
        callback.assert_called_once_with(
            "customer.example", db_root_username="root", db_root_password="root-secret",
            admin_password="admin-secret", mariadb_user_host_login_scope="%",
            install_app=("continuity360",),
        )
        frappe.destroy.assert_called_once()

    def test_lock_rejects_concurrent_creation_and_releases_after_failure(self):
        child = (
            "import sys; from pathlib import Path; "
            "sys.path.insert(0, sys.argv[1]); import provision_tenant_site as p; "
            "p.LOCK_FILE = Path(sys.argv[2]); "
            "\ntry:\n"
            "    with p.site_creation_lock(): pass\n"
            "except RuntimeError as error:\n"
            "    print(error)\n"
            "    sys.exit(75)\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "provision.lock"
            with patch.object(provisioner, "LOCK_FILE", path):
                with self.assertRaisesRegex(ValueError, "setup failed"):
                    with provisioner.site_creation_lock():
                        blocked = subprocess.run(
                            [sys.executable, "-c", child, str(scripts), str(path)],
                            text=True, capture_output=True, check=False,
                        )
                        self.assertEqual(blocked.returncode, 75, blocked.stderr)
                        self.assertIn("already running", blocked.stdout)
                        raise ValueError("setup failed")
                allowed = subprocess.run(
                    [sys.executable, "-c", child, str(scripts), str(path)],
                    text=True, capture_output=True, check=False,
                )
                self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_lock_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "provision.lock"
            path.symlink_to(Path(directory) / "target")
            with patch.object(provisioner, "LOCK_FILE", path):
                with self.assertRaises(OSError):
                    with provisioner.site_creation_lock():
                        self.fail("A symlink lock was accepted")

    def test_operator_entrypoint_reads_separate_secrets_and_drops_privileges(self):
        account = types.SimpleNamespace(pw_name="frappe", pw_gid=1000, pw_uid=1000,
                                        pw_dir="/home/frappe")
        with (
            patch.object(provisioner.os, "getuid", return_value=0),
            patch.object(provisioner.pwd, "getpwnam", return_value=account),
            patch.object(provisioner.os, "initgroups") as groups,
            patch.object(provisioner.os, "setgid") as setgid,
            patch.object(provisioner.os, "setuid") as setuid,
            patch.object(provisioner.os, "chdir") as chdir,
            patch.object(Path, "read_text", side_effect=["root secret\n", " admin secret \n"]),
            patch.object(provisioner, "provision_site") as create,
            patch.dict(os.environ, {"HOME": "/original"}),
            patch("builtins.print"),
        ):
            provisioner.main("customer.example")
        groups.assert_called_once_with("frappe", 1000)
        setgid.assert_called_once_with(1000)
        setuid.assert_called_once_with(1000)
        chdir.assert_called_once_with(provisioner.BENCH / "sites")
        create.assert_called_once_with("customer.example", "root secret", " admin secret ")


if __name__ == "__main__":
    unittest.main()
