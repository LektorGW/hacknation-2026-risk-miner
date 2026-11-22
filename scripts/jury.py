"""Obsługa odizolowanego pokazu. Wszystkie polecenia Docker używają projektu jury."""

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import tempfile
from contextlib import closing
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "var" / "dostep-jury"
MATERIALS = PRIVATE / "materialy"
BASELINE = PRIVATE / "baseline" / "start.sqlite3"
COMPOSE = ["docker", "compose", "-p", "riskminer-jury", "-f", "compose.jury.yaml"]


def run(args, capture=False):
    result = subprocess.run(
        args,
        cwd=ROOT,
        check=True,
        capture_output=capture,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout if capture else None


def private_file(name, contents):
    with os.fdopen(
        os.open(PRIVATE / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
        "w",
        encoding="utf-8",
    ) as f:
        f.write(contents)


def init():
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    MATERIALS.mkdir(exist_ok=True)
    BASELINE.parent.mkdir(exist_ok=True)
    if any(
        (PRIVATE / name).exists()
        for name in ("jury.txt", "admin.txt", "htpasswd", "app.env")
    ):
        raise SystemExit("Konfiguracja dostępu już istnieje.")
    accounts = {}
    for actor, role, filename in (
        ("jury", "expert", "jury.txt"),
        ("operator-jury", "admin", "admin.txt"),
    ):
        token = secrets.token_urlsafe(36)
        private_file(filename, token + "\n")
        accounts[actor] = {
            "role": role,
            "sha256": hashlib.sha256(token.encode()).hexdigest(),
        }
        if actor == "jury":
            # nginx worker must be able to read the hash on Linux bind mounts.
            digest = base64.b64encode(hashlib.sha1(token.encode()).digest()).decode()
            (PRIVATE / "htpasswd").write_text(
                "jury:{SHA}" + digest + "\n", encoding="ascii"
            )
    private_file(
        "app.env",
        "RISKMINER_ENV=production\nRISKMINER_MODEL_PROVIDER=rules\n"
        "RISKMINER_MONITOR_HOURS=0\nRISKMINER_HOSTS=127.0.0.1,localhost,*.trycloudflare.com\n"
        + "RISKMINER_ACCOUNTS='"
        + json.dumps(accounts)
        + "'\n",
    )


def materials():
    # Publish only the current committed branch. The staging directory and credentials stay outside Git.
    with tempfile.TemporaryDirectory(dir=PRIVATE) as temp:
        staging = Path(temp)
        repo = staging / "risk-miner.git"
        run(["git", "init", "--bare", "--initial-branch=main", str(repo)])
        run(
            [
                "git",
                "-C",
                str(repo),
                "-c",
                "fetch.unpackLimit=100000",
                "fetch",
                "--no-auto-maintenance",
                "--no-tags",
                str(ROOT),
                "HEAD:refs/heads/main",
            ]
        )
        run(["git", "-C", str(repo), "update-server-info"])
        for name in ("config", "FETCH_HEAD"):
            (repo / name).unlink(missing_ok=True)
        shutil.rmtree(repo / "hooks")
        run(
            [
                "git",
                "archive",
                "--format=zip",
                "--prefix=risk-miner/",
                "-o",
                str(staging / "kod.zip"),
                "HEAD",
            ]
        )
        for source, name in (
            ("deliverables/demo-risk-miner.mp4", "film.mp4"),
            ("deliverables/opis-projektu.pdf", "opis-projektu.pdf"),
            ("deliverables/prezentacja-risk-miner.pdf", "prezentacja.pdf"),
        ):
            shutil.copyfile(ROOT / source, staging / name)
        shutil.copyfile(ROOT / "deploy" / "jury.html", staging / "index.html")
        target = MATERIALS / repo.name
        if target.exists():
            target.rename(staging / "previous.git")
        repo.rename(target)
        for file in staging.iterdir():
            if file.is_file():
                file.replace(MATERIALS / file.name)


def snapshot():
    remote = "/tmp/" + uuid4().hex + ".sqlite3"
    local = BASELINE.with_suffix(".tmp")
    try:
        run(
            COMPOSE
            + ["exec", "-T", "app", "python", "-m", "riskminer.cli", "backup", remote]
        )
        with local.open("wb") as stream:
            subprocess.run(
                COMPOSE + ["exec", "-T", "app", "cat", remote],
                cwd=ROOT,
                stdout=stream,
                check=True,
            )
        with closing(
            sqlite3.connect(
                "file:" + local.resolve().as_posix() + "?immutable=1", uri=True
            )
        ) as conn:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Uszkodzona kopia wzorcowa.")
        local.replace(BASELINE)
    finally:
        run(COMPOSE + ["exec", "-T", "app", "rm", "-f", remote])


def review():
    remote = "/tmp/decyzje-trzech-spraw.json"
    src = ROOT / "docs" / "decyzje-trzech-spraw.json"
    upload = "import sys,pathlib; pathlib.Path(sys.argv[1]).write_bytes(sys.stdin.buffer.read())"
    subprocess.run(
        COMPOSE + ["exec", "-T", "app", "python", "-c", upload, remote],
        cwd=ROOT,
        input=src.read_bytes(),
        check=True,
    )
    script = (ROOT / "scripts" / "przeglad_spraw.py").read_bytes()
    subprocess.run(
        COMPOSE + ["exec", "-T", "app", "python", "-", remote, "--apply"],
        cwd=ROOT,
        input=script,
        check=True,
    )


RESTORE = """
import os, sqlite3
from pathlib import Path
target = Path('/data/riskminer.sqlite3')
tmp = target.with_suffix('.restore')
tmp.unlink(missing_ok=True)
with sqlite3.connect('file:/baseline/start.sqlite3?mode=ro&immutable=1', uri=True) as src, sqlite3.connect(tmp) as dst:
    src.backup(dst)
    assert dst.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    assert dst.execute('SELECT count(*) FROM projects').fetchone()[0] > 0
with sqlite3.connect(target) as old:
    if old.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0]:
        raise RuntimeError('Aktywny zapis w bazie jury.')
old.close()
dst.close()
for suffix in ('-wal', '-shm'):
    Path(str(target) + suffix).unlink(missing_ok=True)
os.replace(tmp, target)
"""


def reset():
    if not BASELINE.is_file():
        raise SystemExit("Najpierw zapisz stan wzorcowy poleceniem snapshot.")
    run(COMPOSE + ["stop", "app"])
    try:
        run(
            COMPOSE + ["run", "--rm", "--no-deps", "-T", "app", "python", "-c", RESTORE]
        )
    finally:
        run(COMPOSE + ["start", "app"])


def url():
    logs = run(
        COMPOSE + ["logs", "--no-color", "--tail", "150", "tunnel"], capture=True
    )
    matches = re.findall(r"https://[a-z0-9-]+\.trycloudflare\.com\b", logs)
    if not matches:
        raise SystemExit("Tunel nie zwrócił adresu.")
    print(matches[-1])


if __name__ == "__main__":
    commands = {
        "init": init,
        "materials": materials,
        "review": review,
        "snapshot": snapshot,
        "reset": reset,
        "url": url,
    }
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=commands)
    commands[parser.parse_args().action]()
