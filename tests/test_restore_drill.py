import gzip
import importlib.util
import io
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


spec = importlib.util.spec_from_file_location(
    "restore_drill_site", Path(__file__).resolve().parents[1] / "scripts" / "restore_drill_site.py"
)
drill = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drill)
host_spec = importlib.util.spec_from_file_location(
    "restore_drill", Path(__file__).resolve().parents[1] / "scripts" / "restore_drill.py"
)
host = importlib.util.module_from_spec(host_spec)
host_spec.loader.exec_module(host)


class TestRestoreDrill(unittest.TestCase):
    def test_client_options_are_private_and_removed_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(drill, "OPTION_DIRECTORY", Path(directory)):
                with self.assertRaisesRegex(RuntimeError, "test failure"):
                    with drill.client_options('example-"\\password') as filename:
                        self.assertEqual(Path(filename).read_text(), '[client]\npassword="example-\\"\\\\password"\n')
                        if os.name == "posix":
                            self.assertEqual(os.stat(filename).st_mode & 0o777, 0o600)
                        raise RuntimeError("test failure")
                self.assertFalse(Path(filename).exists())

    def test_client_options_reject_invalid_passwords(self):
        for password in ("", "line\nbreak", "line\rbreak", "null\0byte"):
            with self.subTest(password=repr(password)):
                with self.assertRaises(ValueError):
                    with drill.client_options(password):
                        self.fail("Invalid password was accepted")

    def test_database_client_never_receives_password_argument(self):
        frappe = types.ModuleType("frappe")
        frappe.conf = types.SimpleNamespace(db_socket=None, db_host="db", db_port=3306,
                                            db_user="testuser", db_name="testdb")
        database = types.ModuleType("frappe.database")

        def get_command(**kwargs):
            self.assertIsNone(kwargs["password"])
            return "/usr/bin/mariadb", ["--user=testuser", "testdb"], "mariadb"

        database.get_command = get_command
        with patch.dict(sys.modules, {"frappe": frappe, "frappe.database": database}):
            self.assertEqual(drill.client_command(dump=False),
                             ("/usr/bin/mariadb", ["--user=testuser", "testdb"]))

    def test_import_supports_framework_and_compressed_backups_without_password_arguments(self):
        frappe = types.ModuleType("frappe")
        frappe.conf = types.SimpleNamespace(db_name="testdb", db_user="testuser")
        frappe.cache = types.SimpleNamespace(delete_keys=lambda prefix: None)
        captured = []

        class CaptureInput(io.BytesIO):
            def close(self):
                captured.append(self.getvalue())
                super().close()

        class FakeProcess:
            def __init__(self):
                self.stdin = CaptureInput()

            def wait(self):
                return 0

        def start_process(arguments, **kwargs):
            self.assertNotIn("sensitive-password", " ".join(arguments))
            self.assertTrue(arguments[1].startswith("--defaults-extra-file="))
            return FakeProcess()

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            sql = b"SELECT 1;\n/*!999999 DEFINER=user SQL SECURITY DEFINER */\nSELECT 2;\n"
            for name in ("framework.sql", "backup.sql.gz"):
                source = path / name
                if name.endswith(".gz"):
                    with gzip.open(source, "wb") as stream:
                        stream.write(sql)
                else:
                    source.write_bytes(sql)
                with (
                    patch.dict(sys.modules, {"frappe": frappe}),
                    patch.object(drill, "OPTION_DIRECTORY", path),
                    patch.object(drill, "client_command", return_value=("/usr/bin/mariadb", ["testdb"])),
                    patch.object(drill.subprocess, "Popen", side_effect=start_process),
                ):
                    drill.secure_import(False, "testdb", str(source), "testuser", "sensitive-password")
        self.assertEqual(captured, [b"SELECT 1;\nSELECT 2;\n"] * 2)

    def test_failed_drill_attempts_project_cleanup(self):
        def fail_on_start(*arguments, **kwargs):
            if "up" in arguments:
                raise RuntimeError("startup failed")
            return Mock(stdout="")

        with (
            patch.object(host.sys, "platform", "linux"),
            patch.object(host, "resources", return_value=[]),
            patch.object(host, "run", side_effect=fail_on_start),
            patch.object(host, "cleanup") as cleanup,
        ):
            with self.assertRaisesRegex(RuntimeError, "startup failed"):
                host.main()
        cleanup.assert_called_once()

    def test_cleanup_refuses_unexpected_volumes(self):
        with (
            patch.object(host, "resources", return_value=["continuity360-dev_sites"]),
            patch.object(host, "run") as run,
        ):
            with self.assertRaisesRegex(RuntimeError, "Unexpected volumes"):
                host.cleanup(("docker", "compose", "-p", "c360drilltest"), "c360drilltest")
        self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
