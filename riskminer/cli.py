"""Maintenance commands used by local operators and container deployments."""

import argparse
import hashlib
import json
import os
import secrets
import sqlite3
from pathlib import Path

from . import db, workflow


def load_project_file(path, dataset="user"):
    from .ingest import load_file

    data = path.read_bytes()
    records = load_file(path.name, data)
    with db.connection(True) as conn:
        return workflow.import_rows(conn, path.name, data, records, "operator-import", dataset=dataset)


def seed(folder=None):
    folder = Path(folder or db.ROOT / "fixtures" / "starter")
    book = folder / "Risk_Miner_dane_projekty.xlsx"
    if not book.is_file():
        raise ValueError(f"Brak pliku startowego w katalogu {folder}.")
    ids = load_project_file(book, "public")
    with db.connection(True) as conn:
        originals = {}
        for manual in sorted((db.ROOT / "fixtures" / "knowledge").glob("*.docx")):
            originals[manual.name] = workflow.save_file(conn, manual.name, manual.read_bytes())
        conn.execute("INSERT OR REPLACE INTO settings VALUES('knowledge_files',?)", (db.dump(originals),))
    for source in sorted(folder.iterdir()):
        if source.suffix.lower() in {".pdf", ".docx"} and "material_" not in source.name:
            load_project_file(source, "public")
    snapshots = db.ROOT / "fixtures" / "real" / "cases.json"
    count = 0
    if snapshots.is_file():
        cases = json.loads(snapshots.read_text(encoding="utf-8-sig"))
        for case in cases:
            p = case["project"]
            pid = p.get("project_id") or p.get("id")
            if pid not in ids:
                continue
            with db.connection(True) as conn:
                count += workflow.add_observations(conn, pid, case["records"], "archiwum-publiczne")
    print(f"Wczytano {len(ids)} projektów. Nowe ogłoszenia w archiwum: {count}.")


def backup(target):
    target = Path(target)
    if target.exists():
        raise ValueError("Plik docelowy już istnieje.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db.path()) as source, sqlite3.connect(target) as dest:
        source.backup(dest)
        if dest.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Kopia bazy nie przeszła kontroli integralności.")
    print(target.resolve())


def bootstrap():
    env = db.ROOT / ".env"
    if env.exists():
        raise ValueError("Plik .env już istnieje. Dodaj konto w istniejącej konfiguracji.")
    token = secrets.token_urlsafe(36)
    account = {"administrator": {"role": "admin", "sha256": hashlib.sha256(token.encode()).hexdigest()}}
    with env.open("x", encoding="utf-8") as f:
        f.write(
            "RISKMINER_ENV=production\nRISKMINER_HOSTS=127.0.0.1,localhost\nRISKMINER_ACCOUNTS='"
            + db.dump(account)
            + "'\nRISKMINER_MODEL_PROVIDER=rules\n"
        )
    secret = db.ROOT / "var" / "pierwszy-dostep.txt"
    secret.parent.mkdir(parents=True, exist_ok=True)
    secret.write_text(token + "\n", encoding="utf-8")
    if os.name != "nt":
        secret.chmod(0o600)
        env.chmod(0o600)
    print("Konfiguracja gotowa. Token administratora zapisano w " + str(secret))


def main():
    parser = argparse.ArgumentParser(description="Risk Miner — obsługa instancji")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("init")
    sub.add_parser("bootstrap")
    sub.add_parser("seed").add_argument("--directory")
    sub.add_parser("import").add_argument("path", type=Path)
    sub.add_parser("backup").add_argument("target")
    monitor = sub.add_parser("monitor")
    monitor.add_argument("--project", help="Odśwież jeden wskazany projekt")
    args = parser.parse_args()
    db.initialize()
    if args.action == "seed":
        seed(args.directory)
    elif args.action == "import":
        print(", ".join(load_project_file(args.path)))
    elif args.action == "backup":
        backup(args.target)
    elif args.action == "bootstrap":
        bootstrap()
    elif args.action == "monitor":
        from .service import enrich_one

        with db.connection() as conn:
            pids = (
                [args.project]
                if args.project
                else [p["id"] for p in db.projects(conn) if p.get("status") == "active"]
            )
        for pid in pids:
            print(json.dumps(enrich_one(pid, "monitor"), ensure_ascii=False))


if __name__ == "__main__":
    main()
