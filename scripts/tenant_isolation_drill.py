"""Run a disposable two-site Frappe isolation drill on a Linux Docker host."""

import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from restore_drill import ROOT, cleanup, resources, run


def verify_existing_site_rejected(compose, label, site):
    try:
        run(*compose, "run", "--rm", "--no-deps", "-T", f"provision-{label}", site, capture=True)
    except subprocess.CalledProcessError as error:
        if f"FileExistsError: Site path already exists: {site}" not in (error.stderr or ""):
            raise RuntimeError(f"Duplicate site check failed unexpectedly (exit {error.returncode}).") from error
    else:
        raise RuntimeError("Provisioning unexpectedly accepted an existing site.")


def gateway_config(token):
    if not re.fullmatch(r"[0-9a-f]{32}", token):
        raise ValueError("A generated 32-character drill token is required.")
    sites = [f"c360-tenant-{token}-{label}.localhost" for label in ("a", "b")]
    return f"""
pid /tmp/c360-nginx.pid;
events {{}}
http {{
    map_hash_bucket_size 128;
    map $host $tenant_site {{
        default "";
        {sites[0]} {sites[0]};
        {sites[1]} {sites[1]};
    }}
    server {{
        listen 8080 default_server;
        server_name _;
        root /home/frappe/frappe-bench/sites;
        if ($tenant_site = "") {{ return 404; }}
        location ~ ^/protected/(.*) {{
            internal;
            try_files /$tenant_site/$1 =404;
        }}
        location /files/ {{
            try_files /$tenant_site/public$uri =404;
        }}
        location / {{
            proxy_set_header Host $host;
            proxy_set_header X-Frappe-Site-Name $tenant_site;
            proxy_set_header X-Forwarded-Host $host;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Use-X-Accel-Redirect True;
            proxy_pass http://backend:8000;
        }}
    }}
}}
"""


def main():
    if sys.platform != "linux":
        raise RuntimeError("Run this drill on a Linux Docker host.")
    token = uuid.uuid4().hex
    project = f"c360tenant{token[:12]}"
    if any(resources(kind, project) for kind in ("containers", "networks", "volumes")):
        raise RuntimeError("The generated disposable project already exists.")

    with tempfile.TemporaryDirectory(prefix=f"{project}-") as directory:
        directory = Path(directory)
        secret_files = {}
        for name in ("db_root_password", "admin_password", "tenant_a_password", "tenant_b_password"):
            path = directory / name
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as secret:
                secret.write(secrets.token_urlsafe(32))
            secret_files[name] = {"file": str(path)}
        gateway = directory / "gateway.conf"
        gateway.write_text(gateway_config(token), encoding="utf-8")
        override = directory / "override.json"
        override.write_text(json.dumps({
            "secrets": secret_files,
            "networks": {"continuity360": {"internal": True}},
            "services": {
                "backend": {"healthcheck": {"disable": True}},
                "create-site": {
                    "volumes": [f"{ROOT / 'scripts'}:/opt/continuity360:ro"],
                    "secrets": ["tenant_a_password", "tenant_b_password"],
                },
                **{
                    f"provision-{label}": {
                        "image": "continuity360:dev",
                        "user": "0:0",
                        "entrypoint": [
                            "/home/frappe/frappe-bench/env/bin/python",
                            "/opt/continuity360/provision_tenant_site.py",
                        ],
                        "volumes": [
                            "sites:/home/frappe/frappe-bench/sites",
                            f"{ROOT / 'scripts'}:/opt/continuity360:ro",
                        ],
                        "networks": ["continuity360"],
                        "secrets": [
                            "db_root_password",
                            {"source": f"tenant_{label}_password", "target": "tenant_admin_password"},
                        ],
                    }
                    for label in ("a", "b")
                },
                "drill-gateway": {
                    "image": "continuity360:dev",
                    "entrypoint": ["nginx", "-g", "daemon off;", "-c", "/opt/continuity360-gateway.conf"],
                    "volumes": [
                        "sites:/home/frappe/frappe-bench/sites",
                        f"{gateway}:/opt/continuity360-gateway.conf:ro",
                    ],
                    "networks": ["continuity360"],
                },
            },
        }), encoding="utf-8")
        compose = (
            "docker", "compose", "-p", project, "-f", str(ROOT / "compose.yaml"),
            "-f", str(override),
        )
        script = "/opt/continuity360/tenant_isolation_drill_site.py"
        try:
            run(*compose, "config", "--quiet")
            run(*compose, "up", "-d", "--wait", "--wait-timeout", "120", "db", "redis-cache", "redis-queue")
            run(*compose, "run", "--rm", "--no-deps", "configurator")
            for label in ("a", "b"):
                site = f"c360-tenant-{token}-{label}.localhost"
                run(*compose, "run", "--rm", "--no-deps", "-T", f"provision-{label}", site)
                verify_existing_site_rejected(compose, label, site)
            for stage in ("setup", "verify"):
                if stage == "verify":
                    run(*compose, "up", "-d", "--no-deps", "backend", "worker")
                    run(*compose, "up", "-d", "--no-deps", "drill-gateway")
                run(
                    *compose, "run", "--rm", "--no-deps", "-T",
                    "--entrypoint", "/home/frappe/frappe-bench/env/bin/python", "create-site",
                    script, stage, token,
                )
        finally:
            cleanup(compose, project)


if __name__ == "__main__":
    main()
