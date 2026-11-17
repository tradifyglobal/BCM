"""Run an isolated, disposable Continuity360 backup/restore drill on a Docker host."""

import json
import os
import secrets
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE_SCRIPT = ROOT / "scripts" / "restore_drill_site.py"


def run(*arguments, capture=False):
    return subprocess.run(arguments, check=True, text=True, capture_output=capture)


def resources(kind, project):
    commands = {
        "containers": ("docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={project}"),
        "networks": ("docker", "network", "ls", "-q", "--filter", f"label=com.docker.compose.project={project}"),
        "volumes": ("docker", "volume", "ls", "-q", "--filter", f"label=com.docker.compose.project={project}"),
    }
    return run(*commands[kind], capture=True).stdout.splitlines()


def cleanup(compose, project):
    run(*compose, "down")
    volumes = resources("volumes", project)
    expected = {f"{project}_{name}" for name in ("database", "logs", "queue", "sites")}
    if not set(volumes).issubset(expected):
        raise RuntimeError(f"Unexpected volumes in disposable project {project}; cleanup stopped.")
    for volume in volumes:
        label = run(
            "docker", "volume", "inspect", "--format", '{{index .Labels "com.docker.compose.project"}}',
            volume, capture=True,
        ).stdout.strip()
        if label != project or run("docker", "ps", "-aq", "--filter", f"volume={volume}", capture=True).stdout.strip():
            raise RuntimeError(f"Disposable volume {volume} is not safe to remove.")
    if volumes:
        run("docker", "volume", "rm", *volumes)
    if any(resources(kind, project) for kind in ("containers", "networks", "volumes")):
        raise RuntimeError(f"Disposable project {project} was not fully removed.")


def main():
    if sys.platform != "linux":
        raise RuntimeError("Run this drill on a Linux Docker host.")
    token = uuid.uuid4().hex
    project = f"c360drill{token[:12]}"
    if any(resources(kind, project) for kind in ("containers", "networks", "volumes")):
        raise RuntimeError("The generated disposable project already exists.")

    with tempfile.TemporaryDirectory(prefix=f"{project}-") as directory:
        directory = Path(directory)
        secret_files = {}
        for name in ("db_root_password", "admin_password"):
            path = directory / name
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as secret:
                secret.write(secrets.token_urlsafe(32))
            secret_files[name] = {"file": str(path)}
        override = directory / "override.json"
        override.write_text(json.dumps({
            "secrets": secret_files,
            "networks": {"continuity360": {"internal": True}},
            "services": {
                "create-site": {"volumes": [f"{SITE_SCRIPT}:/opt/continuity360/restore_drill_site.py:ro"]},
            },
        }), encoding="utf-8")
        compose = (
            "docker", "compose", "-p", project, "-f", str(ROOT / "compose.yaml"),
            "-f", str(override),
        )
        try:
            run(*compose, "config", "--quiet")
            run(*compose, "up", "-d", "--wait", "--wait-timeout", "120", "db", "redis-cache", "redis-queue")
            run(*compose, "run", "--rm", "--no-deps", "configurator")
            run(
                *compose, "run", "--rm", "--no-deps", "-T",
                "--entrypoint", "/home/frappe/frappe-bench/env/bin/python", "create-site",
                "/opt/continuity360/restore_drill_site.py", token,
            )
        finally:
            cleanup(compose, project)


if __name__ == "__main__":
    main()
