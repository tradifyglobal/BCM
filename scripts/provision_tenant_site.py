"""Operator-only site creation building block; not a public provisioning service."""

import fcntl
import ipaddress
import os
import pwd
import re
import stat
import sys
from contextlib import contextmanager
from pathlib import Path

from restore_drill_site import BENCH, secure_import

LOCK_FILE = Path(".continuity360-provision.lock")


@contextmanager
def site_creation_lock():
    descriptor = os.open(LOCK_FILE, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise RuntimeError("The provisioning lock must be a regular file.")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("Another tenant site creation is already running.") from error
        yield
    finally:
        os.close(descriptor)


def validate_site_name(site):
    if not isinstance(site, str) or len(site) > 253:
        raise ValueError("A lowercase DNS hostname is required.")
    labels = site.split(".")
    if len(labels) < 2 or any(
        not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
        for label in labels
    ):
        raise ValueError("A lowercase DNS hostname is required.")
    try:
        ipaddress.ip_address(site)
    except ValueError:
        return
    raise ValueError("An IP address is not a tenant hostname.")


def provision_site(site, db_root_password, admin_password):
    validate_site_name(site)
    if any(not secret or any(char in secret for char in "\r\n\0")
           for secret in (db_root_password, admin_password)):
        raise ValueError("Nonempty single-line database and tenant Administrator secrets are required.")
    with site_creation_lock():
        if os.path.lexists(site):
            raise FileExistsError(f"Site path already exists: {site}")

        import frappe
        from frappe.commands.site import new_site
        from frappe.database.db_manager import DbManager

        DbManager.restore_database = staticmethod(secure_import)
        try:
            new_site.callback(
                site, db_root_username="root", db_root_password=db_root_password,
                admin_password=admin_password, mariadb_user_host_login_scope="%",
                install_app=("continuity360",),
            )
        finally:
            frappe.destroy()


def main(site):
    validate_site_name(site)
    if os.getuid() != 0:
        raise RuntimeError("The setup container must start as root to read its mounted secrets.")
    root = Path("/run/secrets/db_root_password").read_text().removesuffix("\n")
    admin = Path("/run/secrets/tenant_admin_password").read_text().removesuffix("\n")
    account = pwd.getpwnam("frappe")
    os.initgroups(account.pw_name, account.pw_gid)
    os.setgid(account.pw_gid)
    os.setuid(account.pw_uid)
    os.environ["HOME"] = account.pw_dir
    os.chdir(BENCH / "sites")
    provision_site(site, root, admin)
    print(f"Created site {site}. Routing and tenant activation are not configured.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: provision_tenant_site.py <tenant-hostname>")
    main(sys.argv[1])
