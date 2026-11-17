"""Exercise a backup and restore only inside a disposable development stack."""

import gzip
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

BENCH = Path("/home/frappe/frappe-bench")
OPTION_DIRECTORY = Path("/dev/shm")


@contextmanager
def client_options(password):
    if not password or any(char in password for char in "\r\n\0"):
        raise ValueError("A nonempty single-line database password is required.")
    descriptor, filename = tempfile.mkstemp(prefix="c360-db-", dir=OPTION_DIRECTORY)
    try:
        escaped = password.replace("\\", "\\\\").replace('"', '\\"')
        with os.fdopen(descriptor, "w", encoding="utf-8") as options:
            options.write(f'[client]\npassword="{escaped}"\n')
        yield filename
    finally:
        os.unlink(filename)


def client_command(*, dump):
    import frappe
    from frappe.database import get_command

    binary, arguments, name = get_command(
        socket=frappe.conf.db_socket, host=frappe.conf.db_host, port=frappe.conf.db_port,
        user=frappe.conf.db_user, password=None, db_name=frappe.conf.db_name, dump=dump,
    )
    if not binary:
        raise RuntimeError(f"Required database client not found: {name}")
    if any(argument.startswith("--password") for argument in arguments):
        raise RuntimeError("Database client arguments unexpectedly contain a password option.")
    return binary, arguments


def secure_dump(destination):
    import frappe

    binary, arguments = client_command(dump=True)
    header = (
        "-- begin frappe metadata\n-- [frappe]\n"
        f"-- version = {frappe.__version__}\n-- branch = N/A\n"
        "-- end frappe metadata\n-- \n"
    )
    try:
        with client_options(frappe.conf.db_password) as options, tempfile.TemporaryFile() as errors:
            with gzip.open(destination, "wb") as backup:
                backup.write(header.encode("utf-8"))
                process = subprocess.Popen(
                    [binary, f"--defaults-extra-file={options}", *arguments],
                    stdout=subprocess.PIPE, stderr=errors,
                )
                try:
                    shutil.copyfileobj(process.stdout, backup)
                finally:
                    process.stdout.close()
                    status = process.wait()
                if status:
                    raise RuntimeError(f"Database backup failed with exit code {status}.")
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def secure_import(verbose, target, source, user, password):
    import frappe

    if target != frappe.conf.db_name or user != frappe.conf.db_user or not source.endswith((".sql", ".sql.gz")):
        raise RuntimeError("Unexpected restore destination or backup format.")
    binary, arguments = client_command(dump=False)
    with client_options(password) as options, tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(
            [binary, f"--defaults-extra-file={options}", *arguments],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=errors,
        )
        broken_pipe = False
        try:
            opener = gzip.open if source.endswith(".gz") else open
            with opener(source, "rb") as backup:
                for line in backup:
                    if re.search(rb"/\*!M?!999999\\- enable the sandbox mode \*/", line):
                        continue
                    if re.search(rb"/\*!\d* DEFINER=[^ ]* SQL SECURITY DEFINER \*/", line):
                        continue
                    process.stdin.write(line)
        except BrokenPipeError:
            broken_pipe = True
        finally:
            try:
                process.stdin.close()
            except BrokenPipeError:
                broken_pipe = True
            status = process.wait()
        if status or broken_pipe:
            raise RuntimeError(f"Database restore failed with exit code {status}.")
    frappe.cache.delete_keys("")


def run_drill(token):
    import pwd

    if not re.fullmatch(r"[0-9a-f]{32}", token):
        raise ValueError("A generated 32-character drill token is required.")
    root = Path("/run/secrets/db_root_password").read_text().strip()
    admin = Path("/run/secrets/admin_password").read_text().strip()
    if not root or not admin:
        raise ValueError("Disposable database and administrator secrets are required.")
    if os.getuid() != 0:
        raise RuntimeError("The disposable setup container must start as root.")
    account = pwd.getpwnam("frappe")
    os.initgroups(account.pw_name, account.pw_gid)
    os.setgid(account.pw_gid)
    os.setuid(account.pw_uid)
    os.environ["HOME"] = account.pw_dir
    os.chdir(BENCH / "sites")

    import frappe
    from frappe.commands.site import _restore, new_site
    from frappe.database.db_manager import DbManager
    from frappe.utils.backups import BackupGenerator

    DbManager.restore_database = staticmethod(secure_import)
    site = f"c360-drill-{token}.localhost"
    if Path(site).exists():
        raise RuntimeError("The disposable site already exists.")
    try:
        new_site.callback(
            site, db_root_username="root", db_root_password=root, admin_password=admin,
            mariadb_user_host_login_scope="%", install_app=("continuity360",),
        )
    finally:
        frappe.destroy()

    with tempfile.TemporaryDirectory(prefix="c360-backup-drill-") as backup_dir:
        backup_dir = Path(backup_dir)
        sql = backup_dir / "database.sql.gz"
        public_archive = backup_dir / "public.tar"
        private_archive = backup_dir / "private.tar"
        frappe.init(site)
        frappe.connect()
        try:
            frappe.set_user("Administrator")
            company = frappe.get_doc({
                "doctype": "C360 Company", "company_name": f"Restore drill {token}",
            }).insert()
            risk = frappe.get_doc({
                "doctype": "C360 Risk", "risk_title": f"Restore risk {token}",
                "company": company.name, "responsible_user": "Administrator",
                "likelihood": 4, "impact": 5,
            }).insert()
            payloads = {"public": f"public-{token}", "private": f"private-{token}"}
            file_names = {}
            file_paths = {}
            for kind, content in payloads.items():
                attachment = frappe.get_doc({
                    "doctype": "File", "file_name": f"{kind}-{token}.txt",
                    "is_private": int(kind == "private"), "content": content,
                    "attached_to_doctype": "C360 Company", "attached_to_name": company.name,
                }).insert()
                file_names[kind] = attachment.name
                file_paths[kind] = Path(frappe.get_site_path(kind, "files", Path(attachment.file_url).name))
                if file_paths[kind].read_text(encoding="utf-8") != content:
                    raise RuntimeError(f"The {kind} test file was not created correctly.")
            frappe.db.commit()
            secure_dump(sql)
            backup = BackupGenerator(
                db_name=frappe.conf.db_name, user=frappe.conf.db_user,
                password=frappe.conf.db_password, db_type="mariadb", ignore_conf=True,
                backup_path_files=str(public_archive), backup_path_private_files=str(private_archive),
            )
            backup.backup_files()
            for path in file_paths.values():
                path.unlink()
                if path.exists():
                    raise RuntimeError("A test file was not removed before restore.")
            company_name, risk_name = company.name, risk.name
        finally:
            frappe.destroy()

        frappe.init(site)
        try:
            _restore(
                site=site, sql_file_path=str(sql), db_root_username="root", db_root_password=root,
                with_public_files=str(public_archive), with_private_files=str(private_archive),
            )
        finally:
            frappe.destroy()

        frappe.init(site)
        frappe.connect()
        try:
            restored_company = frappe.get_doc("C360 Company", company_name)
            restored_risk = frappe.get_doc("C360 Risk", risk_name)
            if restored_company.company_name != f"Restore drill {token}":
                raise RuntimeError("Restored company does not match the backup.")
            if (restored_risk.company, restored_risk.score, restored_risk.rating) != (
                company_name, 20, "Critical",
            ):
                raise RuntimeError("Restored risk or its company relationship is incorrect.")
            for kind, content in payloads.items():
                attachment = frappe.get_doc("File", file_names[kind])
                if (
                    attachment.attached_to_doctype != "C360 Company"
                    or attachment.attached_to_name != company_name
                    or attachment.is_private != int(kind == "private")
                ):
                    raise RuntimeError(f"Restored {kind} attachment metadata is incorrect.")
                if file_paths[kind].read_text(encoding="utf-8") != content:
                    raise RuntimeError(f"Restored {kind} file content is incorrect.")
        finally:
            frappe.destroy()
    print("PASS: restored company, risk, public file and private file")


if __name__ == "__main__":
    run_drill(sys.argv[1])
