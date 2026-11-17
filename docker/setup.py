"""One-shot setup for the isolated development stack, not a SaaS provisioning API."""

import os
import pwd
import subprocess
import sys
from pathlib import Path

SITE = "continuity360.localhost"
BENCH = Path("/home/frappe/frappe-bench")


def run(*arguments: str) -> None:
    subprocess.run(["bench", *arguments], check=True, cwd=BENCH)


def configure() -> None:
    settings = {
        "db_host": "db", "db_port": 3306,
        "redis_cache": "redis://redis-cache:6379",
        "redis_queue": "redis://redis-queue:6379",
        "redis_socketio": "redis://redis-queue:6379",
        "socketio_port": 9000,
        "webserver_host": "backend",
        "webserver_port": 8000,
    }
    for key, value in settings.items():
        arguments = ["set-config", "-g", key, str(value)]
        if isinstance(value, int):
            arguments.insert(2, "-p")
        run(*arguments)
    apps = BENCH / "sites" / "apps.txt"
    installed = list(dict.fromkeys([*apps.read_text().split(), "continuity360"]))
    apps.write_text("\n".join(installed) + "\n")


def create_site() -> None:
    root = Path("/run/secrets/db_root_password").read_text().strip()
    admin = Path("/run/secrets/admin_password").read_text().strip()
    if not root or not admin:
        raise ValueError("Nonempty database and Administrator secrets are required.")
    if os.getuid() == 0:
        user = pwd.getpwnam("frappe")
        os.initgroups(user.pw_name, user.pw_gid)
        os.setgid(user.pw_gid)
        os.setuid(user.pw_uid)
        os.environ["HOME"] = user.pw_dir
    config = BENCH / "sites" / SITE / "site_config.json"
    if config.exists():
        # A partial failed installation must fail visibly rather than masquerade as success.
        run("--site", SITE, "execute", "continuity360.install.assert_installed")
        run("--site", SITE, "migrate")
        run("--site", SITE, "execute", "continuity360.dev_setup.initialize")
        return
    from frappe.commands.site import new_site

    os.chdir(BENCH / "sites")
    try:
        new_site.callback(
            SITE, db_root_username="root", db_root_password=root, admin_password=admin,
            mariadb_user_host_login_scope="%", install_app=("continuity360",), set_default=True,
        )
    finally:
        os.chdir(BENCH)
    run("--site", SITE, "set-config", "host_name", "http://localhost:18080")
    run("--site", SITE, "execute", "continuity360.dev_setup.initialize")


if __name__ == "__main__":
    os.chdir(BENCH)
    {"configure": configure, "create-site": create_site}[sys.argv[1]]()
