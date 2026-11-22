"""Generate a per-person access token. Its value is never printed."""

import argparse
import hashlib
import json
import os
import secrets
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Nowe konto Risk Miner")
    parser.add_argument("name")
    parser.add_argument("role", choices=["viewer", "expert", "admin"])
    parser.add_argument("secret_file", type=Path)
    a = parser.parse_args()
    token = secrets.token_urlsafe(36)
    fd = os.open(a.secret_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(token + "\n")
    print(
        json.dumps(
            {a.name: {"role": a.role, "sha256": hashlib.sha256(token.encode()).hexdigest()}},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
