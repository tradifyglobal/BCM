"""Generate development-only secrets locally. Never print or overwrite credentials."""

import os
import secrets
from pathlib import Path


def main() -> None:
    directory = Path(__file__).resolve().parents[1] / ".secrets"
    directory.mkdir(mode=0o700, exist_ok=True)
    for filename in ("db_root_password", "admin_password"):
        path = directory / filename
        if path.exists():
            if not path.read_text().strip():
                raise ValueError(f"{filename} exists but is empty; fix it before starting the stack.")
            continue
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(secrets.token_urlsafe(32) + "\n")
    print("Development secrets are ready in .secrets. Existing credentials were preserved.")


if __name__ == "__main__":
    main()
