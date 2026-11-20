"""Central tenant administration for Continuity360 operators.

Runs on the Docker host next to the Compose project. Lists tenant sites, shows a
tenant's effective subscription and sets plans, wrapping bench execute so each
tenant database stays isolated.

Usage:
    python3 scripts/tenant_admin.py list
    python3 scripts/tenant_admin.py show <site>
    python3 scripts/tenant_admin.py set-plan <site> <Starter|Professional|Enterprise> \
        [licensed_users] [valid_until YYYY-MM-DD] [customer_reference]
"""

import json
import subprocess
import sys
from pathlib import Path

PROJECT = "continuity360-dev"
ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ["docker", "compose", "-p", PROJECT, "-f", str(ROOT / "compose.yaml")]
RESERVED = {"apps.txt", "common_site_config.json", "assets", ".build"}


def _bench(site: str, *args: str) -> str:
    result = subprocess.run(
        [*COMPOSE, "exec", "-T", "backend", "bench", "--site", site, *args],
        check=True, text=True, capture_output=True)
    return result.stdout.strip()


def _sites() -> list[str]:
    listing = subprocess.run(
        [*COMPOSE, "exec", "-T", "backend", "ls", "-1", "sites"],
        check=True, text=True, capture_output=True).stdout.split()
    return sorted(entry for entry in listing if entry not in RESERVED
                  and not entry.endswith((".json", ".txt", ".log")))


def _effective(site: str) -> dict:
    output = _bench(site, "execute", "continuity360.subscription.effective")
    return json.loads(output.splitlines()[-1].replace("'", '"')
                      .replace("True", "true").replace("False", "false")
                      .replace("None", "null"))


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "list"
    if command == "list":
        for site in _sites():
            try:
                state = _effective(site)
                print(f"{site}: {state['plan']} (effective {state['effective_plan']}), "
                      f"{state['licensed_users']} seats, "
                      f"valid until {state['valid_until'] or 'unset'}"
                      + (" [EXPIRED]" if state["expired"] else ""))
            except subprocess.CalledProcessError:
                print(f"{site}: no Continuity360 subscription (app missing or site error)")
        return 0
    if command == "show" and len(sys.argv) == 3:
        print(json.dumps(_effective(sys.argv[2]), indent=1))
        return 0
    if command == "set-plan" and len(sys.argv) >= 4:
        site, plan = sys.argv[2], sys.argv[3]
        licensed = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        valid_until = sys.argv[5] if len(sys.argv) > 5 else None
        reference = sys.argv[6] if len(sys.argv) > 6 else None
        args = json.dumps([plan, licensed, valid_until, reference])
        print(_bench(site, "execute", "continuity360.subscription.set_plan",
                     "--args", args))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
